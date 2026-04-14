import re
import time
from typing import Dict, Any
from ..base import BaseProcessor


class CPURegexProcessor(BaseProcessor):
    """L0: 正则清洗 + 停用词过滤"""

    def __init__(self):
        self.stopwords = {"the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for"}

    def process(self, data: str, **kwargs) -> Dict[str, Any]:
        """处理文本"""
        start = time.time()
        input_tokens = self.estimate_tokens(data)

        # 清洗
        text = re.sub(r'\s+', ' ', data)
        text = re.sub(r'[^\w\s\u4e00-\u9fff.,!?;:]', '', text)

        # 简单停用词过滤
        words = text.split()
        filtered = [w for w in words if w.lower() not in self.stopwords]
        result = ' '.join(filtered)

        output_tokens = self.estimate_tokens(result)
        latency = (time.time() - start) * 1000

        return {
            "text": result,
            "stats": self.get_stats(input_tokens, output_tokens, latency)
        }

    def estimate_tokens(self, data: str) -> int:
        """估算token数"""
        return len(data) // 4
