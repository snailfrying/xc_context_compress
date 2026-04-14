from typing import Dict, Optional
from ..backends.base import MemoryBackend
from ..backends.openclaw import OpenClawBackend
from ...schemas.memory import MemoryChunk, SearchResult


class UserMemoryManager:
    """用户长久记忆管理器

    可插拔后端，按 (user_id, agent_id) 复合键隔离。
    支持 category 过滤。
    """

    def __init__(self, config: Dict):
        self.config = config
        self.backend = self._create_backend()

    def _create_backend(self) -> MemoryBackend:
        backend_type = self.config.get("backend", "openclaw")
        if backend_type == "openclaw":
            return OpenClawBackend(self.config.get("openclaw", {}))
        if backend_type == "mem0":
            from ..backends.mem0_backend import Mem0Backend
            return Mem0Backend(self.config.get("mem0", {}))
        if backend_type == "custom":
            from ..backends.custom import CustomBackend
            return CustomBackend(self.config.get("custom", {}))
        raise ValueError(f"Unknown memory backend: {backend_type}")

    def search(
        self, query: str, top_k: int = 5,
        user_id: Optional[str] = None, agent_id: Optional[str] = None,
        category: Optional[str] = None,
    ) -> SearchResult:
        return self.backend.search(query, top_k,
                                   user_id=user_id, agent_id=agent_id,
                                   category=category)

    def store(
        self, content: str, source: str,
        metadata: Dict = None, category: str = "fact",
        user_id: Optional[str] = None, agent_id: Optional[str] = None,
    ) -> str:
        chunk = MemoryChunk(
            content=content, source=source,
            category=category,
            metadata=metadata or {},
        )
        return self.backend.store(chunk, user_id=user_id, agent_id=agent_id)

    def update(
        self, chunk_id: str, content: str,
        user_id: Optional[str] = None, agent_id: Optional[str] = None,
    ) -> bool:
        return self.backend.update(chunk_id, content,
                                   user_id=user_id, agent_id=agent_id)

    def forget(
        self, chunk_id: str,
        user_id: Optional[str] = None, agent_id: Optional[str] = None,
    ) -> bool:
        return self.backend.forget(chunk_id, user_id=user_id, agent_id=agent_id)

    def get(
        self, source: str,
        user_id: Optional[str] = None, agent_id: Optional[str] = None,
    ) -> Optional[MemoryChunk]:
        return self.backend.get(source, user_id=user_id, agent_id=agent_id)

    def list_memories(
        self,
        user_id: Optional[str] = None, agent_id: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 50, offset: int = 0,
    ) -> SearchResult:
        return self.backend.list_memories(
            user_id=user_id, agent_id=agent_id,
            category=category, limit=limit, offset=offset,
        )
