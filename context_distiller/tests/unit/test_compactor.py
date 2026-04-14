import json
import pytest
from pathlib import Path
from context_distiller.memory_gateway.session.compactor import SessionCompactor


def _make_compactor(tmp_path, **overrides):
    config = {
        "transcript_dir": str(tmp_path / ".transcripts"),
        "micro_compact": {"enabled": True, "keep_recent": 2, "min_content_length": 50},
        "auto_compact": {"enabled": True, "token_threshold": 100},
    }
    config.update(overrides)
    return SessionCompactor(config)


@pytest.fixture
def compactor(tmp_path):
    return _make_compactor(tmp_path)


# ================================================================ L1 micro_compact
class TestMicroCompact:
    def test_replaces_old_tool_results(self, compactor):
        messages = [
            {"role": "user", "content": "q1"},
            {"role": "tool", "name": "search", "content": "A" * 100},
            {"role": "user", "content": "q2"},
            {"role": "tool", "name": "calc", "content": "B" * 100},
            {"role": "user", "content": "q3"},
            {"role": "tool", "name": "read", "content": "C" * 100},
        ]
        result = compactor.micro_compact(messages, keep_recent=2)
        assert "[Previous: used search]" in result[1]["content"]
        assert result[3]["content"] == "B" * 100
        assert result[5]["content"] == "C" * 100

    def test_preserves_short_content(self, compactor):
        messages = [
            {"role": "tool", "name": "ping", "content": "ok"},
            {"role": "tool", "name": "calc", "content": "D" * 200},
            {"role": "tool", "name": "read", "content": "E" * 200},
        ]
        result = compactor.micro_compact(messages, keep_recent=1)
        assert result[0]["content"] == "ok"
        assert "[Previous: used calc]" in result[1]["content"]

    def test_disabled(self, tmp_path):
        c = _make_compactor(tmp_path, micro_compact={"enabled": False})
        messages = [{"role": "tool", "content": "x" * 200}]
        assert c.micro_compact(messages) == messages


# ================================================================ L2 auto_compact
class TestAutoCompact:
    def test_no_compact_below_threshold(self, compactor):
        messages = [{"role": "user", "content": "short"}]
        result = compactor.auto_compact(messages, "sess1")
        assert result == messages

    def test_compact_above_threshold(self, compactor):
        messages = [{"role": "user", "content": "x" * 500}]
        result = compactor.auto_compact(messages, "sess1")
        assert len(result) == 1
        assert result[0]["role"] == "system"

    def test_saves_transcript(self, compactor, tmp_path):
        messages = [{"role": "user", "content": "x" * 500}]
        compactor.auto_compact(messages, "sess_test")
        transcript_dir = tmp_path / ".transcripts"
        files = list(transcript_dir.glob("sess_test_*.jsonl"))
        assert len(files) == 1


# ================================================================ get_summary
class TestGetSummary:
    def test_no_transcript(self, compactor):
        summary = compactor.get_summary("nonexistent")
        assert "No transcript found" in summary

    def test_with_transcript(self, compactor):
        messages = [{"role": "user", "content": "x" * 500}]
        compactor.auto_compact(messages, "sess_sum")
        summary = compactor.get_summary("sess_sum")
        assert len(summary) > 0


# ================================================================ summarize strategies
class TestSummarizeStrategyLingua:
    """strategy=lingua 直接走 Prompt Distiller 文本压缩"""

    def test_lingua_l0_compress(self, tmp_path):
        """L0 (regex) 应该能压缩并返回非空结果"""
        c = _make_compactor(tmp_path, summarize={
            "strategy": "lingua",
            "lingua_level": "L0",
            "lingua_rate": 0.5,
        })
        messages = [
            {"role": "user", "content": "Please analyze the quarterly revenue report for Q3."},
            {"role": "assistant", "content": "The Q3 revenue was 5.2M, up 15% from Q2."},
            {"role": "user", "content": "What about the expenses breakdown?"},
            {"role": "assistant", "content": "Operating expenses were 3.1M, R&D 1.2M."},
        ]
        result = c.auto_compact(messages * 5, "sess_lingua_l0")
        assert len(result) == 1
        assert result[0]["role"] == "system"
        assert len(result[0]["content"]) > 0

    def test_lingua_l2_fallback_on_no_model(self, tmp_path):
        """L2 (llmlingua) 若模型不可用应降级而不崩溃"""
        c = _make_compactor(tmp_path, summarize={
            "strategy": "lingua",
            "lingua_level": "L2",
            "lingua_rate": 0.3,
        })
        messages = [{"role": "user", "content": "test " * 200}]
        result = c.auto_compact(messages, "sess_lingua_l2")
        assert len(result) == 1
        assert len(result[0]["content"]) > 0

    def test_default_strategy_is_lingua(self, tmp_path):
        """未配置 summarize 时默认为 lingua"""
        c = _make_compactor(tmp_path)
        assert c._strategy == "lingua"


class TestSummarizeStrategyLLM:
    """strategy=llm 调用 LLM API（无可用 API 时降级）"""

    def test_llm_no_url_falls_back(self, tmp_path):
        c = _make_compactor(tmp_path, summarize={
            "strategy": "llm",
        })
        messages = [{"role": "user", "content": "hello " * 200}]
        result = c.auto_compact(messages, "sess_llm")
        assert len(result) == 1
        assert len(result[0]["content"]) > 0


class TestSummarizeStrategyFallback:
    """strategy=fallback 纯规则提取"""

    def test_fallback_extract(self, tmp_path):
        c = _make_compactor(tmp_path, summarize={"strategy": "fallback"})
        messages = [
            {"role": "user", "content": "What is the weather today in this region? " * 10},
            {"role": "assistant", "content": "It is currently sunny with a high of 28 degrees. " * 10},
        ] * 5
        result = c.auto_compact(messages, "sess_fb")
        assert len(result) == 1
        assert len(result[0]["content"]) > 0
