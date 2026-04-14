from abc import ABC, abstractmethod
from typing import Optional, List
from ...schemas.memory import MemoryChunk, SearchResult


class MemoryBackend(ABC):
    """记忆后端抽象接口

    所有操作按 (user_id, agent_id) 二元组隔离。
    user_id 标识自然人用户，agent_id 标识 Agent 实例。
    同一用户在不同 Agent 下可以拥有各自独立的记忆空间。
    """

    @abstractmethod
    def search(
        self, query: str, top_k: int = 5,
        user_id: Optional[str] = None, agent_id: Optional[str] = None,
        category: Optional[str] = None,
    ) -> SearchResult:
        pass

    @abstractmethod
    def store(
        self, chunk: MemoryChunk,
        user_id: Optional[str] = None, agent_id: Optional[str] = None,
    ) -> str:
        pass

    @abstractmethod
    def update(
        self, chunk_id: str, content: str,
        user_id: Optional[str] = None, agent_id: Optional[str] = None,
    ) -> bool:
        pass

    @abstractmethod
    def forget(
        self, chunk_id: str,
        user_id: Optional[str] = None, agent_id: Optional[str] = None,
    ) -> bool:
        pass

    @abstractmethod
    def get(
        self, source: str,
        user_id: Optional[str] = None, agent_id: Optional[str] = None,
    ) -> Optional[MemoryChunk]:
        pass

    @abstractmethod
    def list_memories(
        self,
        user_id: Optional[str] = None, agent_id: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 50, offset: int = 0,
    ) -> SearchResult:
        """列出指定作用域下的所有记忆条目"""
        pass
