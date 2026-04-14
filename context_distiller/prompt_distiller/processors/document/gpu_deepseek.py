import time
import logging
from typing import Dict, Any
from ..base import BaseProcessor

logger = logging.getLogger(__name__)


class GPUDeepSeekProcessor(BaseProcessor):
    """L2: DeepSeek-OCR 旗舰 OCR — 极端手写体/扫描件兜底

    通过 OpenAI 兼容 vision 接口调用 DeepSeek-VL 模型进行 OCR。
    """

    def __init__(
        self,
        model_url: str = "http://localhost:11434/v1",
        model_name: str = "deepseek-vl",
    ):
        self.model_url = model_url.rstrip("/")
        self.model_name = model_name
        self._session = None

    def _get_session(self):
        if self._session is None:
            import httpx
            self._session = httpx.Client(timeout=120.0)
        return self._session

    def process(self, data: str, **kwargs) -> Dict[str, Any]:
        start = time.time()

        try:
            text = self._call_ocr(data)
        except Exception as e:
            logger.warning("DeepSeek OCR failed, using fallback: %s", e)
            text = self._fallback_ocr(data)

        output_tokens = self.estimate_tokens(text)
        latency = (time.time() - start) * 1000
        
        logger.info(f"[DeepSeek-OCR] Result length: {len(text)} chars, Latency: {latency:.2f}ms")
        
        return {
            "text": text,
            "raw_length": len(text), # For OCR, raw=compressed initially
            "compressed_length": len(text),
            "stats": self.get_stats(0, output_tokens, latency),
        }

    def _call_ocr(self, filepath: str) -> str:
        """通过 Ollama 原生 chat 接口进行 OCR (对应官方使用手册)"""
        import base64
        import json
        from pathlib import Path

        file_path = Path(filepath)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {filepath}")

        with open(file_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode()

        session = self._get_session()
        # 使用 Ollama 官方示例中的简洁指令
        instruction = "Free OCR."
        
        # 切换到 Ollama 原生 /api/chat 路径，避免 OpenAI 桥接层解析错误
        base_url = self.model_url.replace("/v1", "") # 从 http://host:11434/v1 转为 http://host:11434
        payload = {
            "model": self.model_name,
            "messages": [
                {
                    "role": "user",
                    "content": instruction,
                    "images": [img_b64]
                }
            ],
            "stream": False,
            "options": {
                "temperature": 0.1,
                "num_ctx": 8192
            }
        }

        try:
            resp = session.post(f"{base_url}/api/chat", json=payload)
            resp.raise_for_status()
            data = resp.json()
            
            content = data.get("message", {}).get("content", "")
            if not content:
                logger.warning(f"[DeepSeek-OCR] Content is empty! Raw response: {data}")
            
            return content
        except Exception as e:
            logger.error(f"DeepSeek OCR native call failed: {e}")
            raise e

    def _fallback_ocr(self, filepath: str) -> str:
        """降级到 PyMuPDF 文本提取"""
        try:
            import fitz
            doc = fitz.open(filepath)
            text_parts = [page.get_text() for page in doc]
            doc.close()
            return "\n".join(text_parts)
        except Exception as e:
            logger.warning("Fallback OCR also failed: %s", e)
            return f"[OCR failed for {filepath}]"

    def estimate_tokens(self, data: str) -> int:
        return len(data) // 4
