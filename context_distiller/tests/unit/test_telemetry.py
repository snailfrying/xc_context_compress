import pytest
import time
from context_distiller.infra.telemetry import Telemetry, TelemetryMetrics


@pytest.fixture
def telemetry(tmp_path):
    return Telemetry(persist_path=str(tmp_path / "telemetry.db"))


class TestTelemetry:
    def test_record_and_stats(self, telemetry):
        telemetry.record(TelemetryMetrics(
            token_count=1000, compression_ratio=0.6,
            latency_ms=50.0, processor="cpu_regex",
        ))
        telemetry.record(TelemetryMetrics(
            token_count=2000, compression_ratio=0.4,
            latency_ms=100.0, processor="npu_llmlingua",
        ))
        stats = telemetry.get_stats()
        assert stats["total_tokens"] == 3000
        assert stats["count"] == 2
        assert stats["avg_compression"] == pytest.approx(0.5)

    def test_stats_by_processor(self, telemetry):
        telemetry.record(TelemetryMetrics(processor="cpu_regex", latency_ms=10.0))
        telemetry.record(TelemetryMetrics(processor="cpu_regex", latency_ms=20.0))
        telemetry.record(TelemetryMetrics(processor="npu_llmlingua", latency_ms=100.0))

        by_proc = telemetry.get_stats_by_processor()
        assert by_proc["cpu_regex"]["count"] == 2
        assert by_proc["npu_llmlingua"]["count"] == 1

    def test_prometheus_export(self, telemetry):
        telemetry.record(TelemetryMetrics(
            token_count=500, compression_ratio=0.7,
            latency_ms=30.0, processor="cpu_regex",
        ))
        output = telemetry.export_prometheus()
        assert "context_distiller_tokens_total" in output
        assert "context_distiller_compression_ratio" in output

    def test_empty_stats(self, telemetry):
        assert telemetry.get_stats() == {}
        assert telemetry.export_prometheus() == ""

    def test_reset(self, telemetry):
        telemetry.record(TelemetryMetrics(token_count=100))
        telemetry.reset()
        assert telemetry.get_stats() == {}

    def test_persistence(self, tmp_path):
        db_path = str(tmp_path / "persist.db")
        t1 = Telemetry(persist_path=db_path)
        t1.record(TelemetryMetrics(token_count=42, processor="test"))

        import sqlite3
        conn = sqlite3.connect(db_path)
        rows = conn.execute("SELECT token_count FROM telemetry").fetchall()
        conn.close()
        assert len(rows) == 1
        assert rows[0][0] == 42
