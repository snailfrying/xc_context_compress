import pytest
from context_distiller.memory_gateway.backends.openclaw import OpenClawBackend
from context_distiller.schemas.memory import MemoryChunk


@pytest.fixture
def backend():
    return OpenClawBackend({"db_path": ":memory:"})


class TestStoreAndGet:
    def test_basic_store_get(self, backend):
        chunk = MemoryChunk(content="user prefers Python", source="MEMORY.md#L1", category="preference")
        cid = backend.store(chunk, user_id="u1", agent_id="a1")
        assert cid is not None

        retrieved = backend.get("MEMORY.md#L1", user_id="u1", agent_id="a1")
        assert retrieved is not None
        assert retrieved.content == "user prefers Python"
        assert retrieved.id == cid
        assert retrieved.category == "preference"
        assert retrieved.user_id == "u1"
        assert retrieved.agent_id == "a1"

    def test_store_default_category(self, backend):
        chunk = MemoryChunk(content="some fact", source="f.md#L1")
        backend.store(chunk, user_id="u1", agent_id="a1")
        got = backend.get("f.md#L1", user_id="u1", agent_id="a1")
        assert got.category == "fact"


class TestUserAgentIsolation:
    def test_user_isolation(self, backend):
        chunk = MemoryChunk(content="secret for u1", source="p.md#L1")
        backend.store(chunk, user_id="u1", agent_id="a1")

        assert backend.get("p.md#L1", user_id="u1", agent_id="a1") is not None
        assert backend.get("p.md#L1", user_id="u2", agent_id="a1") is None

    def test_agent_isolation(self, backend):
        """同一 user 下不同 agent 的记忆互不可见"""
        backend.store(
            MemoryChunk(content="agent1 memory", source="x.md#L1"),
            user_id="u1", agent_id="agent_coding",
        )
        backend.store(
            MemoryChunk(content="agent2 memory", source="x.md#L1"),
            user_id="u1", agent_id="agent_writing",
        )
        got1 = backend.get("x.md#L1", user_id="u1", agent_id="agent_coding")
        got2 = backend.get("x.md#L1", user_id="u1", agent_id="agent_writing")

        assert got1.content == "agent1 memory"
        assert got2.content == "agent2 memory"

    def test_search_isolation_by_agent(self, backend):
        backend.store(
            MemoryChunk(content="Python coding rules", source="a.md#L1"),
            user_id="u1", agent_id="coder",
        )
        backend.store(
            MemoryChunk(content="Python poetry analysis", source="b.md#L1"),
            user_id="u1", agent_id="writer",
        )
        result = backend.search("Python", top_k=10, user_id="u1", agent_id="coder")
        contents = [c.content for c in result.chunks]
        assert "Python coding rules" in contents
        assert "Python poetry analysis" not in contents


class TestCategory:
    def test_list_by_category(self, backend):
        backend.store(MemoryChunk(content="likes dark mode", source="a.md#L1", category="preference"),
                      user_id="u1", agent_id="a1")
        backend.store(MemoryChunk(content="is vegetarian", source="b.md#L1", category="fact"),
                      user_id="u1", agent_id="a1")
        backend.store(MemoryChunk(content="use Python 3.12", source="c.md#L1", category="rule"),
                      user_id="u1", agent_id="a1")

        prefs = backend.list_memories(user_id="u1", agent_id="a1", category="preference")
        assert len(prefs.chunks) == 1
        assert prefs.chunks[0].content == "likes dark mode"

        all_mem = backend.list_memories(user_id="u1", agent_id="a1")
        assert all_mem.total == 3

    def test_search_by_category(self, backend):
        backend.store(MemoryChunk(content="prefer dark mode", source="a.md#L1", category="preference"),
                      user_id="u1", agent_id="a1")
        backend.store(MemoryChunk(content="dark history of Rome", source="b.md#L1", category="fact"),
                      user_id="u1", agent_id="a1")

        result = backend.search("dark", top_k=10, user_id="u1", agent_id="a1", category="preference")
        assert all(c.category == "preference" for c in result.chunks)


class TestUpdateForget:
    def test_update_preserves_isolation(self, backend):
        cid = backend.store(
            MemoryChunk(content="old", source="t.md#L1"),
            user_id="u1", agent_id="a1",
        )
        backend.update(cid, "new", user_id="u1", agent_id="a1")
        assert backend.get("t.md#L1", user_id="u1", agent_id="a1").content == "new"

    def test_forget(self, backend):
        cid = backend.store(
            MemoryChunk(content="bye", source="t.md#L1"),
            user_id="u1", agent_id="a1",
        )
        backend.forget(cid, user_id="u1", agent_id="a1")
        assert backend.get("t.md#L1", user_id="u1", agent_id="a1") is None


class TestListMemories:
    def test_pagination(self, backend):
        for i in range(10):
            backend.store(
                MemoryChunk(content=f"item {i}", source=f"m.md#L{i}"),
                user_id="u1", agent_id="a1",
            )
        page1 = backend.list_memories(user_id="u1", agent_id="a1", limit=3, offset=0)
        page2 = backend.list_memories(user_id="u1", agent_id="a1", limit=3, offset=3)
        assert len(page1.chunks) == 3
        assert len(page2.chunks) == 3
        assert page1.total == 10
        ids_1 = {c.id for c in page1.chunks}
        ids_2 = {c.id for c in page2.chunks}
        assert ids_1.isdisjoint(ids_2)
