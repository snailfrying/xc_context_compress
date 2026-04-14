import pytest
from context_distiller.memory_gateway.user_memory.manager import UserMemoryManager
from context_distiller.memory_gateway.session.compactor import SessionCompactor
from context_distiller.memory_gateway.tools import MemoryTools


@pytest.fixture
def tools(tmp_path):
    manager = UserMemoryManager({"backend": "openclaw", "openclaw": {"db_path": ":memory:"}})
    compactor = SessionCompactor({
        "transcript_dir": str(tmp_path / ".transcripts"),
        "micro_compact": {"enabled": True},
        "auto_compact": {"enabled": True, "token_threshold": 100},
    })
    return MemoryTools(manager, compactor)


class TestMemoryToolsCRUD:
    def test_store_and_search(self, tools):
        result = tools.memory_store(
            "user likes dark mode", "prefs.md#L1",
            category="preference", user_id="u1", agent_id="a1",
        )
        assert result["status"] == "stored"
        assert "chunk_id" in result

        search = tools.memory_search("dark mode", user_id="u1", agent_id="a1")
        assert len(search["chunks"]) >= 1
        assert search["chunks"][0]["category"] == "preference"

    def test_store_and_get(self, tools):
        tools.memory_store(
            "project uses Python 3.12", "rules.md#L5",
            category="rule", user_id="u1", agent_id="a1",
        )
        result = tools.memory_get("rules.md#L5", user_id="u1", agent_id="a1")
        assert result["content"] == "project uses Python 3.12"
        assert result["category"] == "rule"

    def test_get_not_found(self, tools):
        result = tools.memory_get("nonexistent.md#L1", user_id="u1", agent_id="a1")
        assert "error" in result

    def test_update(self, tools):
        store_result = tools.memory_store("old fact", "test.md#L1", user_id="u1", agent_id="a1")
        chunk_id = store_result["chunk_id"]
        update_result = tools.memory_update(chunk_id, "new fact", user_id="u1", agent_id="a1")
        assert update_result["status"] == "updated"

    def test_forget(self, tools):
        store_result = tools.memory_store("temp", "temp.md#L1", user_id="u1", agent_id="a1")
        chunk_id = store_result["chunk_id"]
        tools.memory_forget(chunk_id, user_id="u1", agent_id="a1")
        assert "error" in tools.memory_get("temp.md#L1", user_id="u1", agent_id="a1")


class TestMemoryList:
    def test_list_all(self, tools):
        tools.memory_store("f1", "a.md#L1", category="fact", user_id="u1", agent_id="a1")
        tools.memory_store("p1", "b.md#L1", category="preference", user_id="u1", agent_id="a1")
        result = tools.memory_list(user_id="u1", agent_id="a1")
        assert result["total"] == 2

    def test_list_by_category(self, tools):
        tools.memory_store("f1", "a.md#L1", category="fact", user_id="u1", agent_id="a1")
        tools.memory_store("p1", "b.md#L1", category="preference", user_id="u1", agent_id="a1")
        result = tools.memory_list(user_id="u1", agent_id="a1", category="fact")
        assert result["total"] == 1
        assert result["chunks"][0]["category"] == "fact"


class TestAgentIsolation:
    def test_different_agents_different_memory(self, tools):
        tools.memory_store("coding rule", "r.md#L1", user_id="u1", agent_id="coder")
        tools.memory_store("writing rule", "r.md#L1", user_id="u1", agent_id="writer")

        r1 = tools.memory_get("r.md#L1", user_id="u1", agent_id="coder")
        r2 = tools.memory_get("r.md#L1", user_id="u1", agent_id="writer")
        assert r1["content"] == "coding rule"
        assert r2["content"] == "writing rule"


class TestSessionTools:
    def test_context_compact(self, tools):
        messages = [{"role": "user", "content": "x" * 500}]
        result = tools.context_compact(messages, "sess1")
        assert result["status"] == "compacted"

    def test_session_summary_no_transcript(self, tools):
        result = tools.session_summary("nonexistent")
        assert "summary" in result

    def test_get_tools_dict(self, tools):
        tool_dict = tools.get_tools()
        expected_keys = {
            "memory_search", "memory_get", "memory_store",
            "memory_update", "memory_forget", "memory_list",
            "session_summary", "context_compact",
        }
        assert set(tool_dict.keys()) == expected_keys
