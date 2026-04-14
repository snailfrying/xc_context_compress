import pytest
from context_distiller.memory_gateway.session.transcript import TranscriptManager


@pytest.fixture
def tm(tmp_path):
    return TranscriptManager(transcript_dir=str(tmp_path / ".transcripts"))


class TestTranscriptManager:
    def test_save_and_load(self, tm):
        messages = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi there"},
        ]
        path = tm.save("sess1", messages, user_id="u1")
        assert path.exists()

        loaded = tm.load("sess1", user_id="u1")
        assert len(loaded) == 2
        assert loaded[0]["content"] == "hello"

    def test_list_sessions(self, tm):
        tm.save("sess_a", [{"role": "user", "content": "a"}], user_id="u1")
        tm.save("sess_b", [{"role": "user", "content": "b"}], user_id="u1")

        sessions = tm.list_sessions(user_id="u1")
        assert "sess_a" in sessions
        assert "sess_b" in sessions

    def test_replay(self, tm):
        messages = [
            {"role": "user", "content": "q1"},
            {"role": "assistant", "content": "a1"},
            {"role": "user", "content": "q2"},
            {"role": "assistant", "content": "a2"},
        ]
        tm.save("sess_r", messages)
        replayed = tm.replay("sess_r", from_turn=2)
        assert len(replayed) == 2
        assert replayed[0]["content"] == "q2"

    def test_delete(self, tm):
        tm.save("sess_del", [{"role": "user", "content": "x"}])
        count = tm.delete("sess_del")
        assert count >= 1
        assert tm.load("sess_del") == []

    def test_load_empty(self, tm):
        assert tm.load("nonexistent") == []

    def test_user_isolation(self, tm):
        tm.save("sess1", [{"role": "user", "content": "for u1"}], user_id="u1")
        tm.save("sess1", [{"role": "user", "content": "for u2"}], user_id="u2")

        u1_data = tm.load("sess1", user_id="u1")
        u2_data = tm.load("sess1", user_id="u2")
        assert u1_data[0]["content"] == "for u1"
        assert u2_data[0]["content"] == "for u2"
