import pytest
from context_distiller.schemas.events import EventPayload, TokenStats, ProcessedResult
from context_distiller.schemas.config import ProfileConfig, RouterConfig
from context_distiller.schemas.memory import MemoryChunk, SearchResult


def test_event_payload_basic():
    payload = EventPayload(data=["test.txt"], profile="balanced")
    assert payload.profile == "balanced"
    assert len(payload.data) == 1
    assert payload.user_id is None
    assert payload.session_id is None
    assert payload.agent_id is None


def test_event_payload_with_ids():
    payload = EventPayload(
        data=["doc.pdf"],
        profile="speed",
        user_id="u123",
        session_id="s456",
        agent_id="a789",
    )
    assert payload.user_id == "u123"
    assert payload.session_id == "s456"
    assert payload.agent_id == "a789"


def test_event_payload_invalid_profile():
    with pytest.raises(Exception):
        EventPayload(data=[], profile="invalid_profile")


def test_profile_config():
    config = ProfileConfig(name="speed", text_level="L0")
    assert config.name == "speed"
    assert config.text_level == "L0"


def test_profile_config_defaults():
    config = ProfileConfig(name="balanced")
    assert config.text_level == "L2"
    assert config.document_backend == "markitdown"
    assert config.vision_dedup is True


def test_router_config_defaults():
    config = RouterConfig()
    assert config.hardware_probe_enabled is True
    assert config.fallback_enabled is True
    assert config.cache_enabled is True


def test_token_stats():
    stats = TokenStats(
        input_tokens=1000,
        output_tokens=400,
        compression_ratio=0.6,
        latency_ms=100.0,
    )
    assert stats.compression_ratio == 0.6
    assert stats.input_tokens == 1000


def test_memory_chunk():
    chunk = MemoryChunk(content="test fact", source="MEMORY.md#L10")
    assert chunk.content == "test fact"
    assert chunk.metadata == {}
    assert chunk.embedding is None
    assert chunk.id is None
    assert chunk.category == "fact"
    assert chunk.user_id is None
    assert chunk.agent_id is None


def test_memory_chunk_full():
    chunk = MemoryChunk(
        id="42",
        content="user prefers dark mode",
        source="memory/prefs.md#L5",
        category="preference",
        user_id="u1",
        agent_id="coding_agent",
        metadata={"confidence": 0.95},
    )
    assert chunk.id == "42"
    assert chunk.category == "preference"
    assert chunk.user_id == "u1"
    assert chunk.agent_id == "coding_agent"


def test_search_result():
    chunks = [
        MemoryChunk(content="fact1", source="a.md#L1"),
        MemoryChunk(content="fact2", source="b.md#L2"),
    ]
    result = SearchResult(chunks=chunks, scores=[0.9, 0.7])
    assert len(result.chunks) == 2
    assert result.scores[0] > result.scores[1]
    assert result.total == 0


def test_search_result_with_total():
    result = SearchResult(chunks=[], scores=[], total=100)
    assert result.total == 100


def test_processed_result():
    stats = TokenStats(input_tokens=100, output_tokens=40, compression_ratio=0.6, latency_ms=50.0)
    result = ProcessedResult(
        optimized_prompt=[{"type": "text", "content": "compressed"}],
        stats=stats,
    )
    assert len(result.optimized_prompt) == 1
    assert result.metadata == {}
