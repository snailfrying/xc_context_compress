import json
import logging
import os
import time
from pathlib import Path
import uuid
from typing import Dict, Any, Optional, List
import base64
import mimetypes
from fastapi import FastAPI, HTTPException, Request, Response, UploadFile, File, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
import uvicorn
import yaml
import httpx

from ...sdk.client import DistillerClient
from ...schemas.events import EventPayload, ProcessedResult
from ...memory_gateway.user_memory.manager import UserMemoryManager
from ...memory_gateway.session.compactor import SessionCompactor
from ...memory_gateway.session.transcript import TranscriptManager

logger = logging.getLogger(__name__)

app = FastAPI(title="Context Distiller API", version="2.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# Mount uploads directory to serve images/files
uploads_dir = Path(os.environ.get("CONTEXT_DISTILLER_UPLOAD_DIR", "uploads"))
uploads_dir.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(uploads_dir)), name="uploads")


# =====================================================================
# Runtime settings (mutable via /v1/settings)
# =====================================================================

class RuntimeSettings(BaseModel):
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b"
    ollama_model_vision: str = "qwen2.5vl:7b"
    ollama_model_ocr: str = "qwen2.5vl:7b"
    embedding_base_url: str = "http://localhost:11434"
    embedding_model: str = "bge-m3"
    profile: str = "balanced"
    compress_threshold_chars: int = 2000
    session_token_threshold: int = 50000
    session_summarize_strategy: str = "lingua"
    session_summarize_lingua_level: str = "L2"
    session_summarize_lingua_rate: float = 0.3
    memory_backend: str = "openclaw"
    memory_auto_search: bool = True
    memory_auto_store: bool = True
    document_backend: str = "markitdown"

def _load_settings_from_yaml() -> RuntimeSettings:
    """Load configuration from default.yaml into RuntimeSettings"""
    config_path = Path(__file__).resolve().parents[2] / "config" / "default.yaml"
    s = RuntimeSettings()
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
                
                # LLM
                llm = data.get("llm_server", {})
                if llm.get("base_url"): s.ollama_base_url = llm["base_url"]
                if llm.get("model_text"): s.ollama_model = llm["model_text"]
                if llm.get("model_vision"): s.ollama_model_vision = llm["model_vision"]
                if llm.get("model_ocr"): s.ollama_model_ocr = llm["model_ocr"]
                
                # Embedding
                emb = data.get("embedding_server", {})
                if emb.get("base_url"): s.embedding_base_url = emb["base_url"]
                if emb.get("model"): s.embedding_model = emb["model"]
                
                # Session
                mem = data.get("memory_gateway", {}).get("session_memory", {})
                if mem.get("auto_compact", {}).get("token_threshold"): 
                    s.session_token_threshold = mem["auto_compact"]["token_threshold"]
                
                summ = mem.get("summarize", {})
                if summ.get("strategy"): s.session_summarize_strategy = summ["strategy"]
                if summ.get("lingua_level"): s.session_summarize_lingua_level = summ["lingua_level"]
                if summ.get("lingua_rate"): s.session_summarize_lingua_rate = float(summ["lingua_rate"])
                
                # LTM
                user_mem = data.get("memory_gateway", {}).get("user_memory", {})
                if user_mem.get("backend"): s.memory_backend = user_mem["backend"]
                
                # Document Tooling
                doc = data.get("prompt_distiller", {}).get("document", {})
                if doc.get("default_backend"): s.document_backend = doc["default_backend"]
                
            logger.info(f"Loaded configuration from {config_path}")
        except Exception as e:
            logger.error(f"Failed to load config file: {e}")
    return s

_settings = _load_settings_from_yaml()

@app.get("/v1/settings")
async def get_settings():
    return _settings.model_dump()

@app.put("/v1/settings")
async def put_settings(s: RuntimeSettings):
    global _settings
    _settings = s
    return _settings.model_dump()


# =====================================================================
# Agent Chat — 核心对话端点 (连接 Ollama + Memory Gateway + Session Compactor)
# =====================================================================

_sessions: Dict[str, List[Dict]] = {}
_memory_mgr: Optional[UserMemoryManager] = None
_memory_mgr_backend: Optional[str] = None
_compactors: Dict[str, SessionCompactor] = {}


def _get_memory_mgr() -> UserMemoryManager:
    global _memory_mgr, _memory_mgr_backend
    # 当 settings 中的 memory_backend 改变时，自动重建 UserMemoryManager，
    # 以便在不中断进程的情况下切换 OpenClaw / mem0 等实现。
    if _memory_mgr is None or _memory_mgr_backend != _settings.memory_backend:
        _memory_mgr = UserMemoryManager({
            "backend": _settings.memory_backend,
            "openclaw": {
                "db_path": "memory.db",
                "embedding_provider": "ollama",
                "embedding_base_url": _settings.embedding_base_url,
                "embedding_model": _settings.embedding_model,
            },
            "mem0": _settings.model_dump().get("mem0_config", {}),  # 预留扩展位
        })
        _memory_mgr_backend = _settings.memory_backend
    return _memory_mgr


def _get_compactor(session_id: str) -> SessionCompactor:
    if session_id not in _compactors:
        _compactors[session_id] = SessionCompactor({
            "transcript_dir": ".transcripts",
            "micro_compact": {"enabled": True, "keep_recent": 3, "min_content_length": 100},
            "auto_compact": {"enabled": True, "token_threshold": _settings.session_token_threshold, "summary_max_tokens": 2000},
            "summarize": {
                "strategy": _settings.session_summarize_strategy,
                "lingua_level": _settings.session_summarize_lingua_level,
                "lingua_rate": _settings.session_summarize_lingua_rate,
                "llm_base_url": f"{_settings.ollama_base_url}/v1",
                "llm_model": _settings.ollama_model,
            },
        }, memory_mgr=_get_memory_mgr())
    return _compactors[session_id]


class ChatRequest(BaseModel):
    message: str
    user_id: str = "default"
    agent_id: str = "default"
    session_id: str = "default"
    files: List[str] = Field(default_factory=list)
    mode: str = "full"   # full | memory_only | session_only | plain
    compress_strategy: Optional[str] = None
    compress_level: Optional[str] = None
    keep_recent: Optional[int] = None
    token_threshold: Optional[int] = None
    document_backend: Optional[str] = None
    vision_mode: str = "pixel"  # pixel | semantic


class ChatResponse(BaseModel):
    reply: str
    session_id: str
    message_count: int
    memory_hits: List[Dict[str, Any]] = Field(default_factory=list)
    memory_stored: List[str] = Field(default_factory=list)
    compact_triggered: bool = False
    token_estimate: int = 0
    attached_files: List[str] = Field(default_factory=list)
    debug: Dict[str, Any] = Field(default_factory=dict)


def _clean_content_for_token_est(content: Any) -> str:
    """Helper to extract text only for token estimation (strips base64)"""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        texts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                texts.append(str(item.get("text", "")))
        return "\n".join(texts)
    return str(content)

def _scale_image_for_vlm(fpath: str, max_size: int = 1024) -> bytes:
    """Read image, scale down for VLM to reduce Base64 payload size and latency"""
    from PIL import Image
    import io
    try:
        with Image.open(fpath) as img:
            img = img.convert("RGB")
            # Preserve aspect ratio
            w, h = img.size
            if max(w, h) > max_size:
                scale = max_size / max(w, h)
                img = img.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)
            
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=80)
            return buf.getvalue()
    except Exception as e:
        logger.warning("Scaling failed for %s: %s", fpath, e)
        with open(fpath, "rb") as bf:
            return bf.read()

@app.post("/v1/chat", response_model=ChatResponse)
async def agent_chat(req: ChatRequest):
    """Agent chat endpoint with mode-based feature toggling.

    Modes:
      full         — memory recall + session compaction + LLM + auto-store
      memory_only  — memory recall + LLM + auto-store, no session compaction
      session_only — session compaction + LLM, no memory
      plain        — direct LLM chat, no memory or compaction
    """
    import httpx

    sid = req.session_id
    uid = req.user_id
    aid = req.agent_id
    mode = req.mode

    use_memory = mode in ("full", "memory_only")
    use_session = mode in ("full", "session_only")

    if sid not in _sessions:
        _sessions[sid] = []
    messages = _sessions[sid]

    debug_info: Dict[str, Any] = {"mode": mode}
    memory_hits: List[Dict[str, Any]] = []
    memory_stored: List[str] = []
    compact_triggered = False

    # ---- 1. Memory recall (if enabled)
    t0 = time.time()
    if use_memory and _settings.memory_auto_search and req.message.strip():
        try:
            mgr = _get_memory_mgr()
            result = mgr.search(req.message, top_k=3, user_id=uid, agent_id=aid)
            memory_hits = [{"content": c.content, "source": c.source, "category": c.category} for c in result.chunks]
            logger.info(f"[{sid}] Memory recall took {(time.time()-t0)*1000:.1f}ms (hits: {len(memory_hits)})")
        except Exception as e:
            debug_info["memory_search_error"] = str(e)
            logger.error(f"[{sid}] Memory recall error: {e}")

    # ---- 2. Build system prompt
    system_parts = ["You are a helpful AI assistant. Answer in the same language as the user."]
    if memory_hits:
        mem_text = "\n".join(f"- [{h['category']}] {h['content']} (source: {h['source']})" for h in memory_hits)
        system_parts.append(f"\nRelevant memories about this user:\n{mem_text}")

    system_msg = {"role": "system", "content": "\n".join(system_parts)}

    # ---- 3. Handle file attachments (Documents via Distiller, Images via Base64 for VL)
    t_files = time.time()
    file_context = ""
    image_b64s = []
    attached_files = req.files.copy() if req.files else []
    if req.files:
        doc_files = []
        image_exts = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}

        for fpath in req.files:
            ext = Path(fpath).suffix.lower()
            is_image = ext in image_exts

            if is_image and req.vision_mode == "pixel":
                # PIXEL mode: send as Base64 for VLM directly
                try:
                    img_bytes = _scale_image_for_vlm(fpath)
                    b64 = base64.b64encode(img_bytes).decode("utf-8")
                    mime = "image/jpeg"
                    image_b64s.append(f"data:{mime};base64,{b64}")
                except Exception as e:
                    debug_info["image_encode_error"] = str(e)
            else:
                # SEMANTIC mode (images) or NON-IMAGE files (docs/audio/video): send to Distiller
                doc_files.append(fpath)

        if doc_files:
            try:
                prof = req.compress_level if req.compress_level else _settings.profile
                backend = req.document_backend if req.document_backend else _settings.document_backend
                
                # Pass full config for LLM/Ollama consistency
                client_cfg = {
                    "llm_server": {
                        "base_url": _settings.ollama_base_url,
                        "model_text": _settings.ollama_model,
                        "model_vision": _settings.ollama_model_vision,
                        "model_ocr": _settings.ollama_model_ocr
                    }
                }
                client = DistillerClient(profile=prof, document_backend=backend, config=client_cfg)
                result = client.process(data=doc_files, vision_mode=req.vision_mode)
                parts = []
                for item in result.optimized_prompt:
                    c = item.get("content", {})
                    text = c.get("text", str(c)) if isinstance(c, dict) else str(c)
                    parts.append(text)
                file_context = "\n".join(parts)
                debug_info["files_compressed"] = len(doc_files)
                debug_info["file_compression_ratio"] = result.stats.compression_ratio
            except Exception as e:
                debug_info["file_compress_error"] = str(e)
                logger.error(f"[{sid}] Document distillation error: {e}")

    logger.info(f"[{sid}] File processing took {(time.time()-t_files)*1000:.1f}ms (docs: {len(req.files) if req.files else 0}, imgs: {len(image_b64s)})")

    # ---- 4. Append user message
    user_text = req.message
    if file_context:
        user_text = f"{req.message}\n\n[Attached document content]:\n{file_context}"
    
    if image_b64s:
        # Construct multimodal input using OpenAI specification formatting
        content_arr = [{"type": "text", "text": user_text}]
        raw_images = []
        for img_data in image_b64s:
            content_arr.append({
                "type": "image_url",
                "image_url": {"url": img_data}
            })
            # Also extract the raw base64 (minus prefix) for native Ollama fallback
            if "," in img_data:
                raw_images.append(img_data.split(",", 1)[1])
        
        messages.append({"role": "user", "content": content_arr, "images": raw_images})
        debug_info["images_attached"] = len(image_b64s)
    else:
        messages.append({"role": "user", "content": user_text})

    # ---- 5. Session compaction (if enabled)
    t_comp = time.time()
    messages_for_llm = messages
    if use_session:
        compactor = _get_compactor(sid)
        messages_for_llm = compactor.micro_compact(messages, keep_recent=req.keep_recent)
        compacted = compactor.auto_compact(
            messages_for_llm,
            sid,
            strategy=req.compress_strategy,
            lingua_level=req.compress_level,
            token_threshold=req.token_threshold
        )
        if len(compacted) < len(messages_for_llm):
            compact_triggered = True
            messages_for_llm = compacted
            logger.info(f"[{sid}] Auto-compaction triggered and completed.")
    
    logger.info(f"[{sid}] Session logic took {(time.time()-t_comp)*1000:.1f}ms")
    if compact_triggered:
        debug_info["compact"] = "auto_compact triggered"

    # ---- 6. Call Ollama (Dynamic model routing: Text vs Vision)
    t_llm = time.time()
    llm_messages = [system_msg] + messages_for_llm
    token_est = sum(len(_clean_content_for_token_est(m.get("content", ""))) // 4 for m in llm_messages)

    # Auto-switch based on presence of images
    selected_model = _settings.ollama_model_vision if image_b64s else _settings.ollama_model
    logger.info(f"[{sid}] Routing to model: {selected_model} (mode: {'vision' if image_b64s else 'text'})")

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{_settings.ollama_base_url}/v1/chat/completions",
                json={"model": selected_model, "messages": llm_messages, "temperature": 0.7},
            )
            resp.raise_for_status()
            data = resp.json()
            reply = data["choices"][0]["message"]["content"]
            logger.info(f"[{sid}] LLM Inference took {(time.time()-t_llm)*1000:.1f}ms")
    except Exception as e:
        logger.error(f"[{sid}] LLM Inference error: {e}")
        raise HTTPException(status_code=502, detail=f"Ollama error: {e}")

    messages.append({"role": "assistant", "content": reply})
    _sessions[sid] = messages

    return ChatResponse(
        reply=reply,
        session_id=sid,
        message_count=len(messages),
        memory_hits=memory_hits,
        memory_stored=memory_stored,
        compact_triggered=compact_triggered,
        token_estimate=token_est,
        attached_files=attached_files,
        debug=debug_info,
    )

class ChatResetRequest(BaseModel):
    session_id: str = "default"

@app.post("/v1/chat/reset")
async def chat_reset(req: ChatResetRequest):
    _sessions.pop(req.session_id, None)
    _compactors.pop(req.session_id, None)
    return {"status": "reset", "session_id": req.session_id}


# =====================================================================
# Prompt Distiller (one-shot tool)
# =====================================================================

@app.post("/v1/distill", response_model=ProcessedResult)
async def distill(payload: EventPayload) -> ProcessedResult:
    try:
        # Pass full config for LLM/Ollama consistency
        client_cfg = {
            "llm_server": {
                "base_url": _settings.ollama_base_url,
                "model_text": _settings.ollama_model,
                "model_vision": _settings.ollama_model_vision,
                "model_ocr": _settings.ollama_model_ocr
            }
        }
        client = DistillerClient(
            profile=payload.profile, 
            document_backend=payload.document_backend or _settings.document_backend,
            user_id=payload.user_id, 
            agent_id=payload.agent_id, 
            session_id=payload.session_id,
            config=client_cfg
        )
        return client.process(
            data=payload.data, 
            vision_mode=payload.vision_mode,
            model_name=payload.model_name,
            use_vlm=payload.use_vlm,
            compression_rate=payload.compression_rate
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/v1/upload")
async def upload(file: UploadFile = File(...)) -> Dict[str, Any]:
    uploads_dir = Path(os.environ.get("CONTEXT_DISTILLER_UPLOAD_DIR", "uploads"))
    uploads_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(file.filename or "").suffix
    safe_name = f"{uuid.uuid4().hex}{suffix}"
    target = uploads_dir / safe_name
    content = await file.read()
    with open(target, "wb") as f:
        f.write(content)
    return {"filename": file.filename, "saved_as": safe_name, "path": str(target)}


# =====================================================================
# Memory CRUD (direct access, also used by chat internally)
# =====================================================================

class MemorySearchRequest(BaseModel):
    query: str
    top_k: int = 5
    user_id: Optional[str] = None
    agent_id: Optional[str] = None
    category: Optional[str] = None

class MemoryStoreRequest(BaseModel):
    content: str
    source: str
    metadata: Optional[Dict[str, Any]] = None
    category: str = "fact"
    user_id: Optional[str] = None
    agent_id: Optional[str] = None

class MemoryUpdateRequest(BaseModel):
    chunk_id: str
    content: str
    user_id: Optional[str] = None
    agent_id: Optional[str] = None

class MemoryForgetRequest(BaseModel):
    chunk_id: str
    user_id: Optional[str] = None
    agent_id: Optional[str] = None

class MemoryListRequest(BaseModel):
    user_id: Optional[str] = None
    agent_id: Optional[str] = None
    category: Optional[str] = None
    limit: int = 50
    offset: int = 0


@app.post("/v1/memory/search")
async def memory_search(req: MemorySearchRequest) -> Dict:
    mgr = _get_memory_mgr()
    result = mgr.search(req.query, req.top_k, user_id=req.user_id, agent_id=req.agent_id, category=req.category)
    return {"chunks": [{"id": c.id, "content": c.content, "source": c.source, "category": c.category} for c in result.chunks], "scores": result.scores, "total": result.total}

@app.post("/v1/memory/store")
async def memory_store(req: MemoryStoreRequest) -> Dict:
    mgr = _get_memory_mgr()
    chunk_id = mgr.store(req.content, req.source, req.metadata, category=req.category, user_id=req.user_id, agent_id=req.agent_id)
    return {"chunk_id": chunk_id, "status": "stored"}

@app.post("/v1/memory/update")
async def memory_update(req: MemoryUpdateRequest) -> Dict:
    mgr = _get_memory_mgr()
    ok = mgr.update(req.chunk_id, req.content, user_id=req.user_id, agent_id=req.agent_id)
    return {"status": "updated" if ok else "failed"}

@app.post("/v1/memory/forget")
async def memory_forget(req: MemoryForgetRequest) -> Dict:
    mgr = _get_memory_mgr()
    ok = mgr.forget(req.chunk_id, user_id=req.user_id, agent_id=req.agent_id)
    return {"status": "forgotten" if ok else "failed"}

@app.post("/v1/memory/list")
async def memory_list(req: MemoryListRequest) -> Dict:
    mgr = _get_memory_mgr()
    result = mgr.list_memories(user_id=req.user_id, agent_id=req.agent_id, category=req.category, limit=req.limit, offset=req.offset)
    return {"chunks": [{"id": c.id, "content": c.content, "source": c.source, "category": c.category} for c in result.chunks], "total": result.total}


# =====================================================================
# Health + Config
# =====================================================================

@app.get("/health")
async def health():
    return {"status": "ok", "version": "2.0.0"}

@app.get("/v1/config")
async def get_config():
    import yaml
    config_path = Path(__file__).resolve().parents[2] / "config" / "default.yaml"
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    return {"error": "config not found"}


def start_server(host: str = "0.0.0.0", port: int = 8085):
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    start_server()
