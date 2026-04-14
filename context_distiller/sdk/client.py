from typing import Dict, Any, Optional
from ..schemas.events import EventPayload, ProcessedResult
from ..schemas.config import ProfileConfig
from ..prompt_distiller.engine import PromptDistillerEngine
from ..memory_gateway.user_memory.manager import UserMemoryManager
from ..memory_gateway.session.compactor import SessionCompactor
from ..memory_gateway.tools import MemoryTools


class DistillerClient:
    """Python SDK 客户端

    支持 (user_id, session_id, agent_id) 三级隔离:
    - user_id:   自然人用户
    - session_id: 会话生命周期
    - agent_id:  Agent 实例 (同一用户下可有多个 Agent)
    """

    _PROFILE_MAP = {
        "speed": "L0",
        "selective": "L1",
        "balanced": "L2",
        "accuracy": "L3",
    }

    def __init__(
        self,
        profile: str = "balanced",
        document_backend: str = "markitdown",
        config: Dict = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        agent_id: Optional[str] = None,
    ):
        self.config = config or {}
        text_level = self._PROFILE_MAP.get(profile, "L2")
        self.profile = ProfileConfig(name=profile, text_level=text_level, document_backend=document_backend)
        self.user_id = user_id
        self.session_id = session_id
        self.agent_id = agent_id

        self.engine = PromptDistillerEngine(self.profile, config=self.config)

        memory_config = self.config.get("memory_gateway", {})
        self.memory_manager = UserMemoryManager(memory_config.get("user_memory", {}))
        self.session_compactor = SessionCompactor(memory_config.get("session_memory", {}))
        self.tools = MemoryTools(self.memory_manager, self.session_compactor)

    def _uid(self, user_id: str = None) -> str:
        return user_id or self.user_id

    def _aid(self, agent_id: str = None) -> str:
        return agent_id or self.agent_id

    # ---- Prompt Distiller ----

    def process(
        self, query: str = None, data: list = None,
        user_id: str = None, session_id: str = None, agent_id: str = None,
        vision_mode: str = "pixel",
        **kwargs,
    ) -> ProcessedResult:
        payload = EventPayload(
            data=data or [],
            profile=self.profile.name,
            user_id=user_id or self.user_id,
            session_id=session_id or self.session_id,
            agent_id=agent_id or self.agent_id,
            vision_mode=vision_mode,
            document_backend=kwargs.get("document_backend"),
            model_name=kwargs.get("model_name"),
            use_vlm=kwargs.get("use_vlm", False),
            compression_rate=kwargs.get("compression_rate", 0.4),
        )
        return self.engine.process(payload)

    # ---- User Memory ----

    def search_memory(
        self, query: str, top_k: int = 5,
        user_id: str = None, agent_id: str = None,
        category: str = None,
    ) -> Dict:
        return self.tools.memory_search(
            query, top_k,
            user_id=self._uid(user_id), agent_id=self._aid(agent_id),
            category=category,
        )

    def store_memory(
        self, content: str, source: str,
        metadata: Dict = None, category: str = "fact",
        user_id: str = None, agent_id: str = None,
    ) -> Dict:
        return self.tools.memory_store(
            content, source, metadata, category=category,
            user_id=self._uid(user_id), agent_id=self._aid(agent_id),
        )

    def update_memory(
        self, chunk_id: str, content: str,
        user_id: str = None, agent_id: str = None,
    ) -> Dict:
        return self.tools.memory_update(
            chunk_id, content,
            user_id=self._uid(user_id), agent_id=self._aid(agent_id),
        )

    def forget_memory(
        self, chunk_id: str,
        user_id: str = None, agent_id: str = None,
    ) -> Dict:
        return self.tools.memory_forget(
            chunk_id,
            user_id=self._uid(user_id), agent_id=self._aid(agent_id),
        )

    def get_memory(
        self, source: str,
        user_id: str = None, agent_id: str = None,
    ) -> Dict:
        return self.tools.memory_get(
            source,
            user_id=self._uid(user_id), agent_id=self._aid(agent_id),
        )

    def list_memories(
        self,
        user_id: str = None, agent_id: str = None,
        category: str = None,
        limit: int = 50, offset: int = 0,
    ) -> Dict:
        return self.tools.memory_list(
            user_id=self._uid(user_id), agent_id=self._aid(agent_id),
            category=category, limit=limit, offset=offset,
        )

    # ---- Session Memory ----

    def session_summary(self, session_id: str = None) -> Dict:
        sid = session_id or self.session_id
        return self.tools.session_summary(sid)

    def context_compact(self, messages: list, session_id: str = None) -> Dict:
        sid = session_id or self.session_id
        return self.tools.context_compact(messages, sid)
