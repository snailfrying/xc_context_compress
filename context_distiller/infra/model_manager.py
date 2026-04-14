from typing import Dict, Any, Optional
from collections import OrderedDict
import threading


class ModelManager:
    """模型管理器 - 显存LRU缓存"""

    def __init__(self, max_cache_size: int = 3):
        self._cache: OrderedDict[str, Any] = OrderedDict()
        self._max_size = max_cache_size
        self._lock = threading.Lock()

    def load(self, model_key: str, loader_fn: callable) -> Any:
        """加载模型（带LRU缓存）"""
        with self._lock:
            if model_key in self._cache:
                self._cache.move_to_end(model_key)
                return self._cache[model_key]

            if len(self._cache) >= self._max_size:
                self._evict_oldest()

            model = loader_fn()
            self._cache[model_key] = model
            return model

    def _evict_oldest(self):
        """驱逐最旧的模型"""
        if self._cache:
            key, model = self._cache.popitem(last=False)
            del model

    def clear(self):
        """清空缓存"""
        with self._lock:
            self._cache.clear()
