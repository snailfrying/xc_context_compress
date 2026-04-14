import logging
from typing import Dict, Any, Optional, Tuple
from ..schemas.events import EventPayload, ProcessedResult, TokenStats
from ..schemas.config import ProfileConfig
from .router import DispatchRouter
from .processors.base import BaseProcessor

logger = logging.getLogger(__name__)

_PROCESSOR_REGISTRY: Dict[str, str] = {
    "cpu_regex": "context_distiller.prompt_distiller.processors.text.cpu_regex.CPURegexProcessor",
    "cpu_selective": "context_distiller.prompt_distiller.processors.text.cpu_selective.CPUSelectiveProcessor",
    "npu_llmlingua": "context_distiller.prompt_distiller.processors.text.npu_llmlingua.NPULLMLinguaProcessor",
    "gpu_summarizer": "context_distiller.prompt_distiller.processors.text.gpu_summarizer.GPUSummarizerProcessor",
    "cpu_native": "context_distiller.prompt_distiller.processors.document.cpu_native.CPUNativeProcessor",
    "gpu_docling": "context_distiller.prompt_distiller.processors.document.gpu_docling.GPUDoclingProcessor",
    "gpu_deepseek": "context_distiller.prompt_distiller.processors.document.gpu_deepseek.GPUDeepSeekProcessor",
    "gpu_vlm_direct": "context_distiller.prompt_distiller.processors.document.gpu_vlm_direct.GPUVLMDirectProcessor",
    "cpu_opencv": "context_distiller.prompt_distiller.processors.vision.cpu_opencv.CPUOpenCVProcessor",
    "gpu_vlm_roi": "context_distiller.prompt_distiller.processors.vision.gpu_vlm_roi.GPUVLMROIProcessor",
    "cpu_whisper": "context_distiller.prompt_distiller.processors.audio.cpu_whisper.CPUWhisperProcessor",
    "cpu_video": "context_distiller.prompt_distiller.processors.video.cpu_video.CPUVideoProcessor",
}


def _lazy_load_processor(dotted_path: str) -> type:
    module_path, class_name = dotted_path.rsplit(".", 1)
    import importlib
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


class PromptDistillerEngine:
    """Stateless compression engine — supports all 9 processors + URL auto-download.

    For documents, the pipeline is:
      extract text -> smart chunk -> compress each chunk via text processor -> structured output
    """

    def __init__(self, profile: ProfileConfig, config: Optional[Dict] = None):
        self.profile = profile
        self.config = config or {}
        self.router = DispatchRouter(profile)
        self._processors: Dict[str, BaseProcessor] = {}

    def process(self, payload: EventPayload) -> ProcessedResult:
        results = []
        stats_list = []

        for item in payload.data:
            data_type = self._detect_type(item, vision_mode=payload.vision_mode)
            actual_data = item

            if data_type == "data_uri":
                actual_data, data_type = self._resolve_data_uri(item, vision_mode=payload.vision_mode)
            elif data_type == "url":
                actual_data, data_type = self._resolve_url(item, vision_mode=payload.vision_mode)

            processor = self._get_processor(data_type, payload=payload)
            result = processor.process(actual_data, rate=payload.compression_rate if payload else 0.4)

            content = self._build_content(data_type, result)
            results.append({"type": data_type, "content": content})
            if result.get("stats"):
                stats_list.append(result["stats"])

        final_stats = self._aggregate_stats(stats_list)
        return ProcessedResult(
            optimized_prompt=results,
            stats=final_stats,
            metadata={
                "profile": self.profile.name,
                "text_level": self.profile.text_level,
                "vision_mode": payload.vision_mode,
            }
        )

    # ---- Internal Logic ----

    def _detect_type(self, item: str, vision_mode: str = "pixel") -> str:
        if item.startswith("data:"):
            return "data_uri"
        if item.startswith(("http://", "https://")):
            return "url"

        lower = item.lower()

        # Check audio files
        audio_exts = {".mp3", ".wav", ".flac", ".m4a", ".ogg", ".wma", ".aac", ".opus"}
        if any(lower.endswith(ext) for ext in audio_exts):
            return "audio"

        # Check video files
        video_exts = {".mp4", ".avi", ".mov", ".mkv", ".webm", ".flv", ".wmv", ".m4v", ".ts"}
        if any(lower.endswith(ext) for ext in video_exts):
            return "video"

        # Check if it's a file path with image extension
        img_exts = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tiff", ".tif"}
        if any(lower.endswith(ext) for ext in img_exts):
            # In semantic mode, images are treated as documents for OCR
            return "document" if vision_mode == "semantic" else "image"

        # Check if it's a document file
        doc_exts = {".pdf", ".docx", ".xlsx", ".pptx", ".doc", ".xls", ".ppt",
                    ".csv", ".html", ".htm", ".rtf", ".md", ".txt", ".epub", ".odt"}
        if any(lower.endswith(ext) for ext in doc_exts):
            return "document"

        return "text"

    def _resolve_data_uri(self, uri: str, vision_mode: str = "pixel") -> Tuple[str, str]:
        # Handle Base64 decoding and temp file saving? 
        # For simplicity, if vision_mode is semantic, we might need a temp file for OCR.
        # But most OCR processors here handle files.
        return uri, "image" # Placeholder

    def _resolve_url(self, url: str, vision_mode: str = "pixel") -> Tuple[str, str]:
        # URL detection for images
        img_exts = {".png", ".jpg", ".jpeg", ".webp"}
        is_img = any(url.lower().endswith(ext) for ext in img_exts)
        
        if is_img:
            return url, ("document" if vision_mode == "semantic" else "image")
        return url, "text"

    def _build_content(self, data_type: str, result: Dict) -> Any:
        if data_type == "text":
            return result.get("text", "")
        if data_type == "document":
            return {
                "text": result.get("text", ""),
                "chunks": result.get("chunks", []),
                "chunk_count": len(result.get("chunks", [])),
                "raw_length": result.get("raw_length"),
                "compressed_length": result.get("compressed_length")
            }
        if data_type == "image":
            return {"images": result.get("images", []), "summary": result.get("text", "")}
        if data_type == "audio":
            return {
                "text": result.get("text", ""),
                "segments": result.get("segments", []),
                "duration": result.get("duration", 0)
            }
        if data_type == "video":
            return {
                "text": result.get("text", ""),
                "frames": result.get("frames", []),
                "grid_path": result.get("grid_path"),
                "audio_path": result.get("audio_path"),
                "video_info": result.get("video_info", ),
                "frame_count": result.get("frame_count", 0)
            }
        return result

    def _get_processor(self, data_type: str, payload: EventPayload = None) -> BaseProcessor:
        if data_type == "text":
            key = self.router.route_text_processor()
        elif data_type == "document":
            key = self.router.route_document_processor()
        elif data_type == "image":
            key = self.router.route_vision_processor()
        elif data_type == "audio":
            key = "cpu_whisper"
        elif data_type == "video":
            key = "cpu_video"
        else:
            key = "cpu_regex"

        if key not in self._processors:
            self._processors[key] = self._create_processor(key, data_type, payload)
        return self._processors[key]

    def _create_processor(self, key: str, data_type: str = "", payload: Optional[EventPayload] = None) -> BaseProcessor:
        dotted = _PROCESSOR_REGISTRY.get(key)
        if dotted:
            try:
                import inspect
                cls = _lazy_load_processor(dotted)
                
                # Dynamic wiring: pass LLM/VLM settings to processors that need them
                llm_cfg = self.config.get("llm_server", {})
                base_url = llm_cfg.get("base_url", "http://localhost:11434")
                openai_url = f"{base_url.rstrip('/')}/v1"
                
                # Model selection strategy: user override > specific type > global default
                model_name = payload.model_name if payload and payload.model_name else None
                if not model_name:
                    if "summarizer" in key:
                        model_name = llm_cfg.get("model_text", "qwen2.5:7b")
                    elif "deepseek" in key:
                        # DeepSeek specific OCR
                        model_name = llm_cfg.get("model_ocr", "deepseek-ocr:latest")
                    elif any(x in key for x in ("vlm", "roi", "vision")):
                        # General purpose VLM identification
                        model_name = llm_cfg.get("model_vision", "qwen2.5vl:7b")
                    else:
                        model_name = llm_cfg.get("model_text", "qwen2.5:7b")

                use_vlm = payload.use_vlm if payload else True

                # Check constructor signature
                sig = inspect.signature(cls.__init__)
                args = {}
                if "model_url" in sig.parameters:
                    args["model_url"] = openai_url
                if "model_name" in sig.parameters:
                    args["model_name"] = model_name
                if "use_vlm" in sig.parameters:
                    args["use_vlm"] = use_vlm
                
                proc = cls(**args)

                # Wire document processors with a text compressor
                if data_type == "document" and hasattr(proc, "set_text_compressor"):
                    text_key = self.router.route_text_processor()
                    if text_key != "cpu_regex":
                        text_proc = self._create_processor(text_key, "text", payload)
                        proc.set_text_compressor(text_proc)

                return proc
            except Exception as e:
                logger.warning("Failed to load processor %s: %s, falling back", key, e)

        from .processors.text.cpu_regex import CPURegexProcessor
        return CPURegexProcessor()

    def _aggregate_stats(self, stats_list) -> TokenStats:
        if not stats_list:
            return TokenStats(input_tokens=0, output_tokens=0, compression_ratio=0.0, latency_ms=0.0)

        total_in = sum(s.input_tokens for s in stats_list)
        total_out = sum(s.output_tokens for s in stats_list)
        total_lat = sum(s.latency_ms for s in stats_list)
        ratio = 1 - (total_out / total_in) if total_in > 0 else 0.0
        return TokenStats(
            input_tokens=total_in,
            output_tokens=total_out,
            compression_ratio=ratio,
            latency_ms=total_lat,
        )
