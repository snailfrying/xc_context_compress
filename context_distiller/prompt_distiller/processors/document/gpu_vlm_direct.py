import time
import logging
from typing import Dict, Any, Optional
from ..base import BaseProcessor

logger = logging.getLogger(__name__)


class GPUVLMDirectProcessor(BaseProcessor):
    """L3: VLM 直接识别 — 将图像作为上下文传入视觉大模型进行全量理解"""

    def __init__(
        self,
        model_url: str = "http://localhost:11434/v1",
        model_name: str = "qwen2.5vl:7b",
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
        """直接调用 VLM 进行端到端识别"""
        start = time.time()
        
        try:
            text = self._call_vlm(data)
        except Exception as e:
            logger.error("VLM Direct call failed: %s", e)
            text = f"[VLM Identification failed: {e}]"

        output_tokens = self.estimate_tokens(text)
        latency = (time.time() - start) * 1000
        
        logger.info(f"[VLM-Direct] Result length: {len(text)} chars, Latency: {latency:.2f}ms")
        
        return {
            "text": text,
            "raw_length": len(text),
            "compressed_length": len(text),
            "stats": self.get_stats(0, output_tokens, latency),
        }

    def _call_vlm(self, filepath: str) -> str:
        """端到端 VLM 识别逻辑"""
        import base64
        from pathlib import Path

        file_path = Path(filepath)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {filepath}")

        with open(file_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode()

        suffix = file_path.suffix.lower()
        mime = {
            ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
            ".gif": "image/gif", ".webp": "image/webp", ".bmp": "image/bmp",
        }.get(suffix, "image/png")

        session = self._get_session()
        payload = {
            "model": self.model_name,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime};base64,{img_b64}"},
                        },
                        {
                            "type": "text",
                            "text": (
                                "Extract the core content from this image and organize it into a concise, "
                                "intuitive Markdown format. Focus solely on the key data points."
                            ),
                        },
                    ],
                }
            ],
            "max_tokens": 4096,
            "temperature": 0.2,
        }

        resp = session.post(f"{self.model_url}/chat/completions", json=payload)
        resp.raise_for_status()
        data = resp.json()
        print(f"DEBUG [VLM-Direct] response keys: {data.keys()}")
        content = data["choices"][0]["message"]["content"]
        if not content:
            print(f"DEBUG [VLM-Direct] Content is empty! full dict: {data}")
        return content

    def estimate_tokens(self, data: str) -> int:
        return len(data) // 4
