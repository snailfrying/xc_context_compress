import platform
import psutil
from typing import Dict, Literal, Optional


class HardwareProbe:
    """运行时算力探针"""

    def __init__(self):
        self._cache: Optional[Dict] = None

    def detect(self) -> Dict[str, any]:
        """检测硬件能力"""
        if self._cache:
            return self._cache

        result = {
            "cpu_count": psutil.cpu_count(),
            "memory_gb": psutil.virtual_memory().total / (1024**3),
            "has_gpu": self._detect_gpu(),
            "has_npu": False,  # 暂不支持
            "platform": platform.system()
        }
        self._cache = result
        return result

    def _detect_gpu(self) -> bool:
        """检测GPU"""
        try:
            import torch
            return torch.cuda.is_available()
        except ImportError:
            return False

    def get_device_type(self) -> Literal["cpu", "gpu", "npu"]:
        """获取设备类型"""
        info = self.detect()
        if info["has_gpu"]:
            return "gpu"
        return "cpu"
