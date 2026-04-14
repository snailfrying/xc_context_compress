import json
import logging
import sqlite3
import threading
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class TelemetryMetrics:
    """遥测指标"""
    token_count: int = 0
    compression_ratio: float = 0.0
    latency_ms: float = 0.0
    oom_fallback_count: int = 0
    processor: str = ""
    profile: str = ""
    timestamp: float = field(default_factory=time.time)


class Telemetry:
    """可观测性遥测 — 内存 + SQLite 持久化 + Prometheus exporter"""

    def __init__(self, persist_path: Optional[str] = None, max_memory: int = 10000):
        self._metrics: List[TelemetryMetrics] = []
        self._lock = threading.Lock()
        self._max_memory = max_memory
        self._db_path = persist_path
        if self._db_path:
            self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self._db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS telemetry (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                token_count INTEGER,
                compression_ratio REAL,
                latency_ms REAL,
                oom_fallback_count INTEGER,
                processor TEXT,
                profile TEXT,
                timestamp REAL
            )
        """)
        conn.commit()
        conn.close()

    def record(self, metrics: TelemetryMetrics):
        with self._lock:
            self._metrics.append(metrics)
            if len(self._metrics) > self._max_memory:
                self._metrics = self._metrics[-self._max_memory:]

        if self._db_path:
            self._persist(metrics)

    def _persist(self, metrics: TelemetryMetrics):
        try:
            conn = sqlite3.connect(self._db_path)
            conn.execute(
                "INSERT INTO telemetry (token_count, compression_ratio, latency_ms, "
                "oom_fallback_count, processor, profile, timestamp) VALUES (?,?,?,?,?,?,?)",
                (metrics.token_count, metrics.compression_ratio, metrics.latency_ms,
                 metrics.oom_fallback_count, metrics.processor, metrics.profile, metrics.timestamp),
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.warning("Telemetry persist failed: %s", e)

    def get_stats(self, since: Optional[float] = None) -> Dict:
        with self._lock:
            data = self._metrics
            if since:
                data = [m for m in data if m.timestamp >= since]

        if not data:
            return {}

        return {
            "count": len(data),
            "total_tokens": sum(m.token_count for m in data),
            "avg_compression": sum(m.compression_ratio for m in data) / len(data),
            "avg_latency_ms": sum(m.latency_ms for m in data) / len(data),
            "oom_count": sum(m.oom_fallback_count for m in data),
            "time_range": {
                "from": min(m.timestamp for m in data),
                "to": max(m.timestamp for m in data),
            },
        }

    def get_stats_by_processor(self) -> Dict[str, Dict]:
        with self._lock:
            data = self._metrics

        by_proc: Dict[str, List[TelemetryMetrics]] = {}
        for m in data:
            by_proc.setdefault(m.processor or "unknown", []).append(m)

        result = {}
        for proc, metrics in by_proc.items():
            result[proc] = {
                "count": len(metrics),
                "avg_compression": sum(m.compression_ratio for m in metrics) / len(metrics),
                "avg_latency_ms": sum(m.latency_ms for m in metrics) / len(metrics),
                "total_tokens": sum(m.token_count for m in metrics),
            }
        return result

    def export_prometheus(self) -> str:
        """导出 Prometheus text exposition 格式"""
        stats = self.get_stats()
        if not stats:
            return ""

        lines = [
            "# HELP context_distiller_tokens_total Total tokens processed",
            "# TYPE context_distiller_tokens_total counter",
            f"context_distiller_tokens_total {stats.get('total_tokens', 0)}",
            "",
            "# HELP context_distiller_compression_ratio Average compression ratio",
            "# TYPE context_distiller_compression_ratio gauge",
            f"context_distiller_compression_ratio {stats.get('avg_compression', 0):.4f}",
            "",
            "# HELP context_distiller_latency_ms Average latency in milliseconds",
            "# TYPE context_distiller_latency_ms gauge",
            f"context_distiller_latency_ms {stats.get('avg_latency_ms', 0):.2f}",
            "",
            "# HELP context_distiller_oom_fallback_total Total OOM fallback count",
            "# TYPE context_distiller_oom_fallback_total counter",
            f"context_distiller_oom_fallback_total {stats.get('oom_count', 0)}",
            "",
        ]

        by_proc = self.get_stats_by_processor()
        for proc, pstats in by_proc.items():
            lines.append(
                f'context_distiller_processor_latency_ms{{processor="{proc}"}} {pstats["avg_latency_ms"]:.2f}'
            )
            lines.append(
                f'context_distiller_processor_compression{{processor="{proc}"}} {pstats["avg_compression"]:.4f}'
            )

        return "\n".join(lines) + "\n"

    def reset(self):
        with self._lock:
            self._metrics.clear()
