"""端到端集成测试: SDK -> Engine -> Memory (含 agent_id + category 隔离)"""
import pytest
from context_distiller.sdk.client import DistillerClient


@pytest.fixture
def client(tmp_path):
    return DistillerClient(
        profile="balanced",
        config={
            "memory_gateway": {
                "user_memory": {
                    "backend": "openclaw",
                    "openclaw": {"db_path": ":memory:"},
                },
                "session_memory": {
                    "transcript_dir": str(tmp_path / ".transcripts"),
                    "micro_compact": {"enabled": True, "keep_recent": 2},
                    "auto_compact": {"enabled": True, "token_threshold": 200},
                },
            }
        },
        user_id="test_user",
        session_id="test_session",
        agent_id="test_agent",
    )


class TestE2EDistill:
    def test_process_text(self, client):
        result = client.process(data=["This is a test sentence with some content."])
        assert result.optimized_prompt is not None
        assert result.stats is not None

    def test_process_empty_data(self, client):
        result = client.process(data=[])
        assert result.optimized_prompt == []

    def test_process_multiple_items(self, client):
        result = client.process(data=["Text one.", "Text two.", "Text three."])
        assert len(result.optimized_prompt) == 3


class TestE2EMemory:
    def test_store_search_cycle(self, client):
        client.store_memory("User prefers Python 3.12", "rules.md#L1", category="rule")
        client.store_memory("Project uses FastAPI", "rules.md#L5", category="rule")

        results = client.search_memory("Python")
        assert len(results["chunks"]) >= 1

    def test_store_update_get(self, client):
        result = client.store_memory("old fact", "test.md#L1")
        chunk_id = result["chunk_id"]

        client.update_memory(chunk_id, "new fact")
        got = client.get_memory("test.md#L1")
        assert got["content"] == "new fact"

    def test_store_forget_get(self, client):
        result = client.store_memory("temp data", "temp.md#L1")
        chunk_id = result["chunk_id"]

        client.forget_memory(chunk_id)
        got = client.get_memory("temp.md#L1")
        assert "error" in got

    def test_list_memories(self, client):
        client.store_memory("fact 1", "a.md#L1", category="fact")
        client.store_memory("pref 1", "b.md#L1", category="preference")
        client.store_memory("rule 1", "c.md#L1", category="rule")

        all_mem = client.list_memories()
        assert all_mem["total"] == 3

        facts = client.list_memories(category="fact")
        assert facts["total"] == 1

    def test_search_by_category(self, client):
        client.store_memory("Python is great", "a.md#L1", category="fact")
        client.store_memory("prefer Python over Java", "b.md#L1", category="preference")

        result = client.search_memory("Python", category="preference")
        assert all(c["category"] == "preference" for c in result["chunks"])


class TestE2EAgentIsolation:
    def test_two_agents_same_user(self, tmp_path):
        """同一用户下两个 Agent 的记忆互不可见"""
        base_config = {
            "memory_gateway": {
                "user_memory": {"backend": "openclaw", "openclaw": {"db_path": ":memory:"}},
                "session_memory": {"transcript_dir": str(tmp_path / ".transcripts")},
            }
        }
        coder = DistillerClient(config=base_config, user_id="u1", agent_id="coder")
        writer = DistillerClient(config=base_config, user_id="u1", agent_id="writer")

        coder.store_memory("use black formatter", "r.md#L1", category="rule")
        writer.store_memory("use AP style guide", "r.md#L1", category="rule")

        coder_mem = coder.get_memory("r.md#L1")
        writer_mem = writer.get_memory("r.md#L1")
        assert coder_mem["content"] == "use black formatter"
        assert writer_mem["content"] == "use AP style guide"


class TestE2ESession:
    def test_context_compact(self, client):
        messages = [{"role": "user", "content": "x" * 1000}]
        result = client.context_compact(messages)
        assert result["status"] == "compacted"

    def test_session_summary(self, client):
        result = client.session_summary()
        assert "summary" in result
