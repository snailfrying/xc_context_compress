from typing import Dict, Callable, Optional, List


class MemoryTools:
    """Agent 工具接口 — 8 个工具覆盖会话记忆 + 用户长久记忆

    所有 User Memory 工具通过 (user_id, agent_id) 做多租户隔离。
    store 支持 category 分类写入，search/list 支持 category 过滤。
    """

    def __init__(self, memory_manager, session_compactor):
        self.memory_manager = memory_manager
        self.session_compactor = session_compactor

    def get_tools(self) -> Dict[str, Callable]:
        return {
            "memory_search": self.memory_search,
            "memory_get": self.memory_get,
            "memory_store": self.memory_store,
            "memory_update": self.memory_update,
            "memory_forget": self.memory_forget,
            "memory_list": self.memory_list,
            "session_summary": self.session_summary,
            "context_compact": self.context_compact,
        }

    # ---- User Memory (read) ----

    def memory_search(
        self, query: str, top_k: int = 5,
        user_id: Optional[str] = None, agent_id: Optional[str] = None,
        category: Optional[str] = None,
    ) -> Dict:
        result = self.memory_manager.search(
            query, top_k,
            user_id=user_id, agent_id=agent_id, category=category,
        )
        return {
            "chunks": [
                {"id": c.id, "content": c.content, "source": c.source,
                 "category": c.category}
                for c in result.chunks
            ],
            "scores": result.scores,
            "total": result.total,
        }

    def memory_get(
        self, source: str,
        user_id: Optional[str] = None, agent_id: Optional[str] = None,
    ) -> Dict:
        chunk = self.memory_manager.get(source, user_id=user_id, agent_id=agent_id)
        if chunk:
            return {
                "id": chunk.id, "content": chunk.content,
                "source": chunk.source, "category": chunk.category,
            }
        return {"error": "Not found"}

    def memory_list(
        self,
        user_id: Optional[str] = None, agent_id: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 50, offset: int = 0,
    ) -> Dict:
        result = self.memory_manager.list_memories(
            user_id=user_id, agent_id=agent_id,
            category=category, limit=limit, offset=offset,
        )
        return {
            "chunks": [
                {"id": c.id, "content": c.content, "source": c.source,
                 "category": c.category}
                for c in result.chunks
            ],
            "total": result.total,
        }

    # ---- User Memory (write) ----

    def memory_store(
        self, content: str, source: str,
        metadata: Dict = None, category: str = "fact",
        user_id: Optional[str] = None, agent_id: Optional[str] = None,
    ) -> Dict:
        chunk_id = self.memory_manager.store(
            content, source, metadata, category=category,
            user_id=user_id, agent_id=agent_id,
        )
        return {"chunk_id": chunk_id, "status": "stored"}

    def memory_update(
        self, chunk_id: str, content: str,
        user_id: Optional[str] = None, agent_id: Optional[str] = None,
    ) -> Dict:
        success = self.memory_manager.update(
            chunk_id, content, user_id=user_id, agent_id=agent_id,
        )
        return {"status": "updated" if success else "failed"}

    def memory_forget(
        self, chunk_id: str,
        user_id: Optional[str] = None, agent_id: Optional[str] = None,
    ) -> Dict:
        success = self.memory_manager.forget(
            chunk_id, user_id=user_id, agent_id=agent_id,
        )
        return {"status": "forgotten" if success else "failed"}

    # ---- Session Memory ----

    def session_summary(self, session_id: str) -> Dict:
        summary = self.session_compactor.get_summary(session_id)
        return {"session_id": session_id, "summary": summary}

    def context_compact(self, messages: list, session_id: str) -> Dict:
        compacted = self.session_compactor.auto_compact(messages, session_id)
        return {"messages": compacted, "status": "compacted"}
