import hashlib
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional
from glob import glob as globfn

logger = logging.getLogger(__name__)


class MemoryFileSync:
    """事件驱动的 .md 文件同步器

    将 MEMORY.md / memory/*.md 中的内容按 heading/段落分 chunk，
    通过 content hash 增量写入 MemoryBackend。

    触发模式:
    - on_search: 每次 search 前自动同步
    - on_session_start: 会话开始时同步
    - interval: 外部定时器驱动

    .md 同步的记忆 category 固定为 "system"。
    """

    def __init__(self, backend, config: Dict):
        self.backend = backend
        self.memory_paths = config.get("memory_paths", ["MEMORY.md"])
        self.sync_trigger = config.get("sync_trigger", "on_search")
        self._synced_hashes: Dict[str, str] = {}

    def sync(self, user_id: Optional[str] = None, agent_id: Optional[str] = None) -> int:
        total = 0
        for pattern in self.memory_paths:
            for filepath in self._resolve_paths(pattern):
                total += self._sync_file(filepath, user_id, agent_id)
        return total

    def should_sync_before_search(self) -> bool:
        return self.sync_trigger == "on_search"

    def should_sync_on_session_start(self) -> bool:
        return self.sync_trigger == "on_session_start"

    def _resolve_paths(self, pattern: str) -> List[Path]:
        matches = globfn(pattern, recursive=True)
        return [Path(m) for m in matches if Path(m).is_file()]

    def _sync_file(
        self, filepath: Path,
        user_id: Optional[str] = None, agent_id: Optional[str] = None,
    ) -> int:
        if not filepath.exists():
            return 0

        content = filepath.read_text(encoding="utf-8")
        file_hash = hashlib.md5(content.encode()).hexdigest()

        cache_key = f"{user_id or ''}:{agent_id or ''}:{filepath}"
        if self._synced_hashes.get(cache_key) == file_hash:
            return 0

        chunks = self._split_into_chunks(content, str(filepath))
        changed = 0
        for chunk_content, source in chunks:
            existing = self.backend.get(source, user_id=user_id, agent_id=agent_id)
            if existing is None:
                from ...schemas.memory import MemoryChunk
                chunk = MemoryChunk(
                    content=chunk_content, source=source,
                    category="system",
                )
                self.backend.store(chunk, user_id=user_id, agent_id=agent_id)
                changed += 1
            elif existing.content != chunk_content:
                self.backend.update(
                    existing.id, chunk_content,
                    user_id=user_id, agent_id=agent_id,
                )
                changed += 1

        self._synced_hashes[cache_key] = file_hash
        logger.info("Synced %s: %d changed chunks", filepath, changed)
        return changed

    def _split_into_chunks(self, content: str, filepath: str) -> List[tuple]:
        """按 markdown heading 分 chunk，每个 chunk 附带 source = filepath#L{line}"""
        lines = content.split("\n")
        chunks = []
        current_lines = []
        current_start = 1

        for i, line in enumerate(lines, 1):
            if re.match(r"^#{1,3}\s", line) and current_lines:
                chunk_text = "\n".join(current_lines).strip()
                if chunk_text:
                    chunks.append((chunk_text, f"{filepath}#L{current_start}"))
                current_lines = [line]
                current_start = i
            else:
                current_lines.append(line)

        if current_lines:
            chunk_text = "\n".join(current_lines).strip()
            if chunk_text:
                chunks.append((chunk_text, f"{filepath}#L{current_start}"))

        return chunks
