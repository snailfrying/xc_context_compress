import importlib
from typing import Any, Callable


class LazyLoader:
    """懒加载模块"""

    def __init__(self, module_name: str):
        self.module_name = module_name
        self._module = None

    def __getattr__(self, name: str) -> Any:
        if self._module is None:
            self._module = importlib.import_module(self.module_name)
        return getattr(self._module, name)


class EnvManager:
    """环境管理器 - 懒依赖加载隔离"""

    _loaded_modules = {}

    @classmethod
    def lazy_import(cls, module_name: str) -> LazyLoader:
        """懒加载模块"""
        if module_name not in cls._loaded_modules:
            cls._loaded_modules[module_name] = LazyLoader(module_name)
        return cls._loaded_modules[module_name]

    @classmethod
    def require_gpu(cls, func: Callable) -> Callable:
        """装饰器：标记需要GPU的函数"""
        def wrapper(*args, **kwargs):
            torch = cls.lazy_import("torch")
            if not torch.cuda.is_available():
                raise RuntimeError("GPU required but not available")
            return func(*args, **kwargs)
        return wrapper
