from typing import List, Dict, Any, Optional, Literal
from pydantic import BaseModel, Field


class TokenStats(BaseModel):
    """Token统计信息"""
    input_tokens: int
    output_tokens: int
    compression_ratio: float
    latency_ms: float


class EventPayload(BaseModel):
    """输入事件载荷"""
    data: List[str] = Field(description="URL/base64/文本列表")
    profile: Literal["speed", "selective", "balanced", "accuracy"] = "balanced"
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    agent_id: Optional[str] = None
    vision_mode: Literal["pixel", "semantic"] = "pixel"
    document_backend: Optional[str] = None
    model_name: Optional[str] = None
    use_vlm: bool = False
    compression_rate: float = 0.4


class ProcessedResult(BaseModel):
    """处理结果"""
    optimized_prompt: List[Dict[str, Any]]
    stats: TokenStats
    metadata: Dict[str, Any] = Field(default_factory=dict)
