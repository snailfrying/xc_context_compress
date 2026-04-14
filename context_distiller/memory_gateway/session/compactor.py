from typing import Dict, List, Optional, Any
import json
import logging
from pathlib import Path
import httpx

logger = logging.getLogger(__name__)


class SessionCompactor:
    """会话三层压缩器 — micro_compact / auto_compact / manual (context_compact tool)

    摘要策略 (summarize_strategy) 支持三种模式, 用户可在配置中独立选择:
        - "lingua":   直接调用 Prompt Distiller 文本压缩 (LLMLingua/SelectiveContext/Regex)
        - "llm":      调用 OpenAI 兼容接口让 LLM 生成摘要
        - "fallback":  纯规则提取 (零依赖)

    降级链: lingua 失败 → llm 失败 → fallback
    """

    def __init__(self, config: Dict, memory_mgr: Optional[Any] = None):
        self.config = config
        self.memory_mgr = memory_mgr
        self.transcript_dir = Path(config.get("transcript_dir", ".transcripts"))
        self.transcript_dir.mkdir(parents=True, exist_ok=True)

        # ---- L1 micro_compact ----
        mc_cfg = self.config.get("micro_compact", {})
        self._mc_enabled = mc_cfg.get("enabled", True)
        self._mc_keep_recent = mc_cfg.get("keep_recent", 3)
        self._mc_min_content_length = mc_cfg.get("min_content_length", 100)

        # ---- L2 auto_compact ----
        ac_cfg = self.config.get("auto_compact", {})
        self._ac_enabled = ac_cfg.get("enabled", True)
        self._ac_threshold = ac_cfg.get("token_threshold", 50000)
        self._ac_summary_max_tokens = ac_cfg.get("summary_max_tokens", 2000)

        # ---- summarize strategy (独立配置) ----
        sum_cfg = self.config.get("summarize", {})
        self._strategy = sum_cfg.get("strategy", "lingua")
        self._lingua_level = sum_cfg.get("lingua_level", "L2")
        self._lingua_rate = sum_cfg.get("lingua_rate", 0.3)
        self._llm_base_url = sum_cfg.get("llm_base_url") or config.get("llm_base_url")
        self._llm_model = sum_cfg.get("llm_model") or config.get("llm_model")

        self._lingua_processor = None

    # ================================================================ L1
    def micro_compact(self, messages: List[Dict], keep_recent: int = None) -> List[Dict]:
        """L1: 替换旧 tool_result 为占位符，保留消息结构"""
        if not self._mc_enabled:
            return messages

        keep = keep_recent if keep_recent is not None else self._mc_keep_recent
        tool_indices = [
            i for i, m in enumerate(messages)
            if m.get("role") == "tool"
        ]

        result = []
        for i, msg in enumerate(messages):
            if i in tool_indices[:-keep] if keep else tool_indices:
                content = str(msg.get("content", ""))
                if len(content) >= self._mc_min_content_length:
                    result.append({
                        **msg,
                        "content": f"[Previous: used {msg.get('name', 'tool')}]",
                    })
                else:
                    result.append(msg)
            else:
                result.append(msg)
        return result

    # ================================================================ L2
    def auto_compact(self, messages: List[Dict], session_id: str, strategy: str = None, lingua_level: str = None, lingua_rate: float = None, token_threshold: int = None, summary_max_tokens: int = None) -> List[Dict]:
        """L2: token > threshold 时保存 transcript 并用摘要替换"""
        if not self._ac_enabled:
            return messages

        threshold = token_threshold if token_threshold is not None else self._ac_threshold
        total_tokens = self._estimate_tokens(messages)
        if total_tokens < threshold:
            return messages

        self._save_transcript(session_id, messages)
        summary = self._summarize(messages, strategy=strategy, lingua_level=lingua_level, lingua_rate=lingua_rate, max_tokens=summary_max_tokens)
        
        # New: Automatically store this summary in LTM when compaction happens
        if self.memory_mgr:
            try:
                self.memory_mgr.store(summary, source=f"summary:{session_id}", category="session_history")
                logger.info("Auto-compact summary stored in LTM for session %s", session_id)
            except Exception as e:
                logger.error("Failed to store compact summary: %s", e)
        
        return [{"role": "system", "content": f"Previous conversation summary: {summary}"}]

    def load_history(self, session_id: str) -> List[Dict]:
        """尝试从磁盘加载最近的会话历史记录"""
        transcripts = sorted(self.transcript_dir.glob(f"{session_id}_*.jsonl"))
        if not transcripts:
            return []
        
        latest = transcripts[-1]
        history = []
        try:
            with open(latest, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        history.append(json.loads(line))
            logger.info("Loaded %d messages for session %s from %s", len(history), session_id, latest.name)
            return history
        except Exception as e:
            logger.error("Failed to load history from %s: %s", latest, e)
            return []

    # ================================================================ read-only summary
    def get_summary(self, session_id: str) -> str:
        """生成当前会话摘要（不替换消息），供 session_summary 工具使用"""
        transcripts = sorted(self.transcript_dir.glob(f"*{session_id}*"))
        if not transcripts:
            return f"No transcript found for session {session_id}"

        latest = transcripts[-1]
        messages = []
        with open(latest, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    messages.append(json.loads(line))

        if not messages:
            return f"Empty transcript for session {session_id}"
        return self._summarize(messages)

    # ================================================================ internals
    def _extract_text_content(self, content) -> str:
        """从内容(字符串或OpenAI的多模态数组)中智能提取纯文本，过滤掉Base64等图片负载"""
        if isinstance(content, str):
            return content
        elif isinstance(content, list):
            texts = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    texts.append(str(item.get("text", "")))
            return "\n".join(texts)
        return str(content)

    def _estimate_tokens(self, messages: List[Dict]) -> int:
        """估算文本Token，安全剥离多模态Base64以免触发不必要的长度警报"""
        tokens = 0
        for m in messages:
            text = self._extract_text_content(m.get("content", ""))
            tokens += len(text) // 4
        return tokens

    def _save_transcript(self, session_id: str, messages: List[Dict]):
        import time
        filepath = self.transcript_dir / f"{session_id}_{int(time.time())}.jsonl"
        with open(filepath, "w", encoding="utf-8") as f:
            for msg in messages:
                f.write(json.dumps(msg, ensure_ascii=False) + "\n")

    # ================================================================ strategy router
    def _summarize(self, messages: List[Dict], strategy: str = None, lingua_level: str = None, lingua_rate: float = None, max_tokens: int = None) -> str:
        """按配置策略生成摘要，失败自动降级

        降级链: lingua → llm → fallback
        """
        text = self._messages_to_text(messages)
        cur_strategy = strategy if strategy is not None else self._strategy
        cur_rate = lingua_rate if lingua_rate is not None else self._lingua_rate

        if cur_strategy == "lingua":
            return self._try_chain(text, [
                lambda t: self._lingua_compress(t, level=lingua_level, rate=cur_rate),
                lambda t: self._llm_summarize_text(t, max_tokens=max_tokens),
                self._fallback_extract,
            ])
        elif cur_strategy == "llm":
            return self._try_chain(text, [
                lambda t: self._llm_summarize_text(t, max_tokens=max_tokens),
                lambda t: self._lingua_compress(t, level=lingua_level, rate=cur_rate),
                self._fallback_extract,
            ])
        else:
            return self._fallback_extract(text)

    def _try_chain(self, text: str, strategies) -> str:
        """依次尝试策略列表，直到某个成功"""
        for fn in strategies:
            try:
                result = fn(text)
                if result and result.strip():
                    return result
            except Exception as e:
                logger.warning("%s failed: %s, trying next", fn.__name__, e)
        return self._fallback_extract(text)

    def _messages_to_text(self, messages: List[Dict]) -> str:
        parts = []
        for m in messages[-50:]:
            role = m.get("role", "unknown")
            # 智能提取文本，保留对话的真实语义，直接丢弃图片等重量级视觉负载
            text = self._extract_text_content(m.get("content", ""))
            if text.strip():
                parts.append(f"[{role}] {text}")
        return "\n".join(parts)

    # ================================================================ lingua (Prompt Distiller 文本压缩)
    def _lingua_compress(self, text: str, level: str = None, rate: float = None) -> str:
        """通过 Prompt Distiller 文本处理器做压缩式摘要"""
        cur_rate = rate if rate is not None else self._lingua_rate
        processor = self._get_lingua_processor(level=level)
        result = processor.process(text, rate=cur_rate)
        compressed = result.get("text", "")
        stats = result.get("stats")
        if stats:
            logger.info(
                "Lingua compress (level=%s): ratio=%.2f, latency=%.1fms",
                level or self._lingua_level, stats.compression_ratio, stats.latency_ms,
            )
        return compressed

    def _get_lingua_processor(self, level: str = None):
        """懒加载文本压缩处理器，按 level 选择档位"""
        cur_level = level if level is not None else self._lingua_level
        
        # If level is overridden and different from cached, re-create it locally
        # Otherwise use/update the instance level cache
        if level is not None and level != self._lingua_level:
            return self._create_processor_by_level(cur_level)
            
        if self._lingua_processor is not None:
            return self._lingua_processor

        self._lingua_processor = self._create_processor_by_level(cur_level)
        return self._lingua_processor

    def _create_processor_by_level(self, level: str):
        if level == "L0":
            from ...prompt_distiller.processors.text.cpu_regex import CPURegexProcessor
            return CPURegexProcessor()
        elif level == "L1":
            from ...prompt_distiller.processors.text.cpu_selective import CPUSelectiveProcessor
            return CPUSelectiveProcessor()
        elif level == "L2":
            from ...prompt_distiller.processors.text.npu_llmlingua import NPULLMLinguaProcessor
            return NPULLMLinguaProcessor()
        elif level == "L3":
            from ...prompt_distiller.processors.text.gpu_summarizer import GPUSummarizerProcessor
            return GPUSummarizerProcessor()
        return self._create_processor_by_level("L2")

    # ================================================================ LLM 摘要
    def _llm_summarize_text(self, text: str, max_tokens: int = None) -> str:
        """通过 OpenAI 兼容接口调用 LLM 生成摘要"""
        if not self._llm_base_url:
            raise RuntimeError("No llm_base_url configured")

        cur_max = max_tokens if max_tokens is not None else self._ac_summary_max_tokens
        payload = {
            "model": self._llm_model or "default",
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a conversation summarizer. Produce a concise summary "
                        "of the following conversation in the same language as the conversation. "
                        "Focus on key decisions, facts, and action items."
                    ),
                },
                {"role": "user", "content": text},
            ],
            "max_tokens": cur_max,
            "temperature": 0.3,
        }

        resp = httpx.post(
            f"{self._llm_base_url.rstrip('/')}/chat/completions",
            json=payload,
            timeout=30.0,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]

    # ================================================================ fallback
    def _fallback_extract(self, text: str) -> str:
        """零依赖降级：截取关键内容"""
        lines = text.strip().split("\n")
        kept = [l for l in lines if l.startswith("[user]") or l.startswith("[assistant]")]
        if not kept:
            kept = lines
        header = f"Conversation summary ({len(lines)} lines total):\n"
        return header + "\n".join(kept[-10:])
