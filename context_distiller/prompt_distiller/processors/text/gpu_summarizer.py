import time
import logging
from typing import Dict, Any
from ..base import BaseProcessor

logger = logging.getLogger(__name__)


class GPUSummarizerProcessor(BaseProcessor):
    """L3: GPU 摘要重写 — 通过 OpenAI 兼容接口调用本地 LLM (Ollama/vLLM/etc)

    支持 Qwen2.5 摘要重写。API 不可用时自动降级到 L2 (LLMLingua)。
    """

    def __init__(
        self,
        model_url: str = "http://localhost:11434/v1",
        model_name: str = "qwen2.5:7b",
    ):
        self.model_url = model_url.rstrip("/")
        self.model_name = model_name
        self._session = None

    def _get_session(self):
        if self._session is None:
            import httpx
            self._session = httpx.Client(timeout=60.0)
        return self._session

    def process(self, data: str, **kwargs) -> Dict[str, Any]:
        start = time.time()
        input_tokens = self.estimate_tokens(data)

        try:
            result = self._llm_summarize(data)
        except Exception as e:
            logger.warning("LLM summarize failed, using fallback: %s", e)
            result = self._fallback(data)

        output_tokens = self.estimate_tokens(result)
        latency = (time.time() - start) * 1000
        return {
            "text": result,
            "stats": self.get_stats(input_tokens, output_tokens, latency),
        }

    def _llm_summarize(self, text: str) -> str:
        session = self._get_session()

        if len(text) > 16000:
            text = text[:16000]

        payload = {
            "model": self.model_name,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a text compressor. Rewrite the user's text into a highly condensed version "
                        "that preserves all key facts, numbers, names, and logical structure. "
                        "Use the same language as the input. Remove redundancy and filler."
                    ),
                },
                {"role": "user", "content": text},
            ],
            "temperature": 0.2,
            "max_tokens": max(len(text) // 8, 200),
        }

        resp = session.post(f"{self.model_url}/chat/completions", json=payload)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]

    def _fallback(self, text: str) -> str:
        """降级：提取前 20% 内容"""
        sentences = text.split("。")
        keep = max(1, len(sentences) // 5)
        return "。".join(sentences[:keep]) + "。" if sentences else text

    def estimate_tokens(self, data: str) -> int:
        return len(data) // 4
