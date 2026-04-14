from typing import Optional, Dict, Any, List, Literal
from pydantic import BaseModel, Field


MemoryCategory = Literal[
    "fact",        # 关键事实 (e.g. "用户是素食者")
    "preference",  # 偏好设定 (e.g. "偏好暗色主题")
    "rule",        # 项目规则 (e.g. "项目用 Python 3.12")
    "profile",     # 用户画像 (e.g. "后端工程师, 5年经验")
    "note",        # 通用笔记
    "system",      # 系统级 (.md 同步写入)
]

VALID_CATEGORIES = list(MemoryCategory.__args__)


class MemoryChunk(BaseModel):
    """记忆片段 — OpenClaw 核心数据单元

    每条记忆绑定 (user_id, agent_id) 二元组实现多租户隔离。
    category 字段支持按类型检索/过滤。
    """
    id: Optional[str] = Field(default=None, description="存储层分配的唯一 ID")
    content: str
    source: str = Field(default="", description="来源标记 path#L{line}")
    category: str = Field(default="fact", description="记忆类别")
    user_id: Optional[str] = Field(default=None, description="所属用户")
    agent_id: Optional[str] = Field(default=None, description="所属 Agent")
    metadata: Dict[str, Any] = Field(default_factory=dict)
    embedding: Optional[list] = None


class SearchResult(BaseModel):
    """检索结果"""
    chunks: List[MemoryChunk]
    scores: List[float]
    total: int = Field(default=0, description="匹配总数 (可能 > len(chunks))")
