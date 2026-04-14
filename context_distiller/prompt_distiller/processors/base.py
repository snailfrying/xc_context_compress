from abc import ABC, abstractmethod
from typing import Any, Dict
from ...schemas.events import TokenStats


class BaseProcessor(ABC):
    """处理器基类"""

    @abstractmethod
    def process(self, data: Any, **kwargs) -> Dict[str, Any]:
        """处理数据"""
        pass

    @abstractmethod
    def estimate_tokens(self, data: Any) -> int:
        """估算token数"""
        pass

    def get_stats(self, input_tokens: int, output_tokens: int, latency_ms: float) -> TokenStats:
        """生成统计信息"""
        ratio = 1 - (output_tokens / input_tokens) if input_tokens > 0 else 0
        return TokenStats(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            compression_ratio=ratio,
            latency_ms=latency_ms
        )
