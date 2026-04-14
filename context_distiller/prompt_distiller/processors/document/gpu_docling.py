import time
from typing import Dict, Any
from ..base import BaseProcessor


class GPUDoclingProcessor(BaseProcessor):
    """L1: Docling AI版面分析"""

    def __init__(self):
        self._converter = None

    def _load_converter(self):
        """懒加载Docling"""
        if self._converter is None:
            from docling.document_converter import DocumentConverter
            self._converter = DocumentConverter()
        return self._converter

    def process(self, data: str, **kwargs) -> Dict[str, Any]:
        """处理文档"""
        start = time.time()

        converter = self._load_converter()
        result = converter.convert(data)
        text = result.document.export_to_markdown()

        output_tokens = self.estimate_tokens(text)
        latency = (time.time() - start) * 1000

        return {
            "text": text,
            "stats": self.get_stats(0, output_tokens, latency)
        }

    def estimate_tokens(self, data: str) -> int:
        return len(data) // 4
