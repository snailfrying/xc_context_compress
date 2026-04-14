import logging
from typing import Dict, Optional
from .base import MemoryBackend
from ...schemas.memory import MemoryChunk, SearchResult

logger = logging.getLogger(__name__)


class Mem0Backend(MemoryBackend):
    """mem0 Hybrid Datastore 后端

    懒导入 mem0，从 config 读取 llm/embedder/vector_store 配置。
    通过 (user_id, agent_id) 实现跨会话多租户隔离。

    安装: pip install context-distiller[mem0]  or  pip install mem0ai
    """

    def __init__(self, config: Dict):
        self.config = config
        self._client = None

    def _get_client(self):
        if self._client is not None:
            return self._client

        try:
            from mem0 import Memory
        except ImportError:
            raise ImportError(
                "mem0 is required for Mem0Backend. "
                "Install with: pip install context-distiller[mem0]  or  pip install mem0ai"
            )

        mem0_config = {}

        llm_provider = self.config.get("llm_provider")
        llm_model = self.config.get("llm_model")
        if llm_provider:
            mem0_config["llm"] = {
                "provider": llm_provider,
                "config": {"model": llm_model or "qwen2.5:7b"},
            }

        embedder = self.config.get("embedder")
        if embedder:
            mem0_config["embedder"] = {
                "provider": "huggingface",
                "config": {"model": embedder},
            }

        vector_store = self.config.get("vector_store")
        if vector_store:
            mem0_config["vector_store"] = {
                "provider": vector_store,
                "config": {"collection_name": "context_distiller_memories"},
            }

        if self.config.get("enable_graph"):
            mem0_config["graph_store"] = {
                "provider": "neo4j",
                "config": self.config.get("graph_config", {}),
            }

        self._client = Memory.from_config(mem0_config) if mem0_config else Memory()
        return self._client

    def _build_scope(self, user_id: Optional[str], agent_id: Optional[str]) -> Dict:
        scope = {}
        if user_id:
            scope["user_id"] = user_id
        if agent_id:
            scope["agent_id"] = agent_id
        return scope

    def search(
        self, query: str, top_k: int = 5,
        user_id: Optional[str] = None, agent_id: Optional[str] = None,
        category: Optional[str] = None,
    ) -> SearchResult:
        client = self._get_client()
        kwargs = {"query": query, "limit": top_k}
        kwargs.update(self._build_scope(user_id, agent_id))

        results = client.search(**kwargs)
        chunks, scores = [], []
        entries = results.get("results", results) if isinstance(results, dict) else results
        for entry in entries:
            if isinstance(entry, dict):
                meta = entry.get("metadata", {})
                cat = meta.get("category", "fact")
                if category and cat != category:
                    continue
                chunks.append(MemoryChunk(
                    id=str(entry.get("id", "")),
                    content=entry.get("memory", entry.get("text", "")),
                    source=f"mem0:{entry.get('id', '')}",
                    category=cat,
                    user_id=user_id,
                    agent_id=agent_id,
                    metadata=meta,
                ))
                scores.append(entry.get("score", 1.0))
        return SearchResult(chunks=chunks, scores=scores, total=len(chunks))

    def store(
        self, chunk: MemoryChunk,
        user_id: Optional[str] = None, agent_id: Optional[str] = None,
    ) -> str:
        client = self._get_client()
        meta = {**chunk.metadata, "category": chunk.category}
        kwargs = {"data": chunk.content, "metadata": meta}
        kwargs.update(self._build_scope(
            user_id or chunk.user_id,
            agent_id or chunk.agent_id,
        ))
        result = client.add(**kwargs)
        if isinstance(result, dict):
            return str(result.get("id", ""))
        return str(result)

    def update(
        self, chunk_id: str, content: str,
        user_id: Optional[str] = None, agent_id: Optional[str] = None,
    ) -> bool:
        client = self._get_client()
        try:
            client.update(memory_id=chunk_id, data=content)
            return True
        except Exception as e:
            logger.warning("mem0 update failed: %s", e)
            return False

    def forget(
        self, chunk_id: str,
        user_id: Optional[str] = None, agent_id: Optional[str] = None,
    ) -> bool:
        client = self._get_client()
        try:
            client.delete(memory_id=chunk_id)
            return True
        except Exception as e:
            logger.warning("mem0 forget failed: %s", e)
            return False

    def get(
        self, source: str,
        user_id: Optional[str] = None, agent_id: Optional[str] = None,
    ) -> Optional[MemoryChunk]:
        client = self._get_client()
        mem_id = source.replace("mem0:", "") if source.startswith("mem0:") else source
        try:
            result = client.get(memory_id=mem_id)
            if result:
                entry = result if isinstance(result, dict) else {"memory": str(result)}
                return MemoryChunk(
                    id=mem_id,
                    content=entry.get("memory", entry.get("text", "")),
                    source=f"mem0:{mem_id}",
                    category=entry.get("metadata", {}).get("category", "fact"),
                    user_id=user_id,
                    agent_id=agent_id,
                    metadata=entry.get("metadata", {}),
                )
        except Exception as e:
            logger.warning("mem0 get failed: %s", e)
        return None

    def list_memories(
        self,
        user_id: Optional[str] = None, agent_id: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 50, offset: int = 0,
    ) -> SearchResult:
        client = self._get_client()
        kwargs = self._build_scope(user_id, agent_id)
        try:
            results = client.get_all(**kwargs)
            entries = results.get("results", results) if isinstance(results, dict) else results
            chunks = []
            for entry in entries:
                if isinstance(entry, dict):
                    meta = entry.get("metadata", {})
                    cat = meta.get("category", "fact")
                    if category and cat != category:
                        continue
                    chunks.append(MemoryChunk(
                        id=str(entry.get("id", "")),
                        content=entry.get("memory", entry.get("text", "")),
                        source=f"mem0:{entry.get('id', '')}",
                        category=cat,
                        user_id=user_id, agent_id=agent_id,
                        metadata=meta,
                    ))
            sliced = chunks[offset:offset + limit]
            return SearchResult(chunks=sliced, scores=[1.0] * len(sliced), total=len(chunks))
        except Exception as e:
            logger.warning("mem0 list_memories failed: %s", e)
            return SearchResult(chunks=[], scores=[], total=0)
