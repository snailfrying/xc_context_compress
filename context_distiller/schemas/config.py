from typing import Literal, Dict, Any
from pydantic import BaseModel, Field


class ProfileConfig(BaseModel):
    """场景配置

    Profiles:
      speed    → L0 (regex clean)
      balanced → L2 (LLMLingua-2)
      accuracy → L3 (LLM summarize)
      custom   → any text_level the caller sets
    """
    name: str = "balanced"
    text_level: Literal["L0", "L1", "L2", "L3"] = "L2"
    document_backend: Literal["markitdown", "pymupdf", "docling", "deepseek", "vlm"] = "markitdown"
    vision_dedup: bool = True


class RouterConfig(BaseModel):
    """路由配置"""
    hardware_probe_enabled: bool = True
    fallback_enabled: bool = True
    cache_enabled: bool = True
