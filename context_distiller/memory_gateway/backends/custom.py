from typing import Dict, Optional
from .base import MemoryBackend
from ...schemas.memory import MemoryChunk, SearchResult


class CustomBackend(MemoryBackend):
    """企业自有知识库桥接模板

    使用方法:
        1. 继承此类
        2. 实现全部抽象方法 (search/store/update/forget/get/list_memories)
        3. 在 config 中设置 backend: "custom"
    """

    def __init__(self, config: Dict):
        self.config = config

    def search(self, query: str, top_k: int = 5,
               user_id: Optional[str] = None, agent_id: Optional[str] = None,
               category: Optional[str] = None) -> SearchResult:
        raise NotImplementedError("CustomBackend.search() must be implemented by subclass.")

    def store(self, chunk: MemoryChunk,
              user_id: Optional[str] = None, agent_id: Optional[str] = None) -> str:
        raise NotImplementedError("CustomBackend.store() must be implemented by subclass.")

    def update(self, chunk_id: str, content: str,
               user_id: Optional[str] = None, agent_id: Optional[str] = None) -> bool:
        raise NotImplementedError("CustomBackend.update() must be implemented by subclass.")

    def forget(self, chunk_id: str,
               user_id: Optional[str] = None, agent_id: Optional[str] = None) -> bool:
        raise NotImplementedError("CustomBackend.forget() must be implemented by subclass.")

    def get(self, source: str,
            user_id: Optional[str] = None, agent_id: Optional[str] = None) -> Optional[MemoryChunk]:
        raise NotImplementedError("CustomBackend.get() must be implemented by subclass.")

    def list_memories(self,
                      user_id: Optional[str] = None, agent_id: Optional[str] = None,
                      category: Optional[str] = None,
                      limit: int = 50, offset: int = 0) -> SearchResult:
        raise NotImplementedError("CustomBackend.list_memories() must be implemented by subclass.")
