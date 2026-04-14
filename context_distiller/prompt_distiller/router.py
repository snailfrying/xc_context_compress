from typing import Literal, Dict, Any
from ..infra.hardware_probe import HardwareProbe
from ..schemas.config import ProfileConfig


class DispatchRouter:
    """动态分发路由器"""

    def __init__(self, profile: ProfileConfig):
        self.profile = profile
        self.probe = HardwareProbe()

    def route_text_processor(self) -> str:
        """路由文本处理器

        L0 → cpu_regex       (regex 清洗, 最快)
        L1 → cpu_selective    (GPT-2 self-information 筛选)
        L2 → npu_llmlingua    (LLMLingua-2, CPU/NPU/GPU 均可)
        L3 → gpu_summarizer   (LLM 摘要重写, 通过 Ollama/vLLM 等 HTTP 接口)
        """
        level = self.profile.text_level

        mapping = {
            "L0": "cpu_regex",
            "L1": "cpu_selective",
            "L2": "npu_llmlingua",
            # 注意: gpu_summarizer 只是调用 HTTP LLM, 不依赖本机 GPU,
            # 所以这里不再根据 device 降级, 始终使用 L3 路径以体现差异。
            "L3": "gpu_summarizer",
        }
        return mapping.get(level, "cpu_regex")

    def route_document_processor(self) -> str:
        """路由文档处理器"""
        backend = self.profile.document_backend
        device = self.probe.get_device_type()

        if backend in ["markitdown", "pymupdf"]:
            return "cpu_native"
        elif backend == "docling" and device == "gpu":
            return "gpu_docling"
        elif backend == "vlm":
            return "gpu_vlm_direct"
        elif backend == "deepseek":
            return "gpu_deepseek"
        return "cpu_native"

    def route_vision_processor(self) -> str:
        """路由图像处理器"""
        device = self.probe.get_device_type()
        return "gpu_vlm_roi" if device == "gpu" else "cpu_opencv"
