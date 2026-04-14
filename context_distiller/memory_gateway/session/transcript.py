import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class TranscriptManager:
    """.transcripts/ 持久化与回溯管理器"""

    def __init__(self, transcript_dir: str = ".transcripts"):
        self.transcript_dir = Path(transcript_dir)
        self.transcript_dir.mkdir(parents=True, exist_ok=True)

    def save(self, session_id: str, messages: List[Dict], user_id: Optional[str] = None) -> Path:
        """持久化完整对话到 .transcripts/{user_id}/{session_id}_{ts}.jsonl"""
        import time

        if user_id:
            target_dir = self.transcript_dir / user_id
        else:
            target_dir = self.transcript_dir
        target_dir.mkdir(parents=True, exist_ok=True)

        filepath = target_dir / f"{session_id}_{int(time.time())}.jsonl"
        with open(filepath, "w", encoding="utf-8") as f:
            for msg in messages:
                f.write(json.dumps(msg, ensure_ascii=False) + "\n")

        logger.info("Transcript saved: %s (%d messages)", filepath, len(messages))
        return filepath

    def load(self, session_id: str, user_id: Optional[str] = None) -> List[Dict]:
        """加载某会话最新的 transcript"""
        files = self._find_session_files(session_id, user_id)
        if not files:
            return []
        return self._read_jsonl(files[-1])

    def load_all(self, session_id: str, user_id: Optional[str] = None) -> List[List[Dict]]:
        """加载某会话所有 transcript 快照"""
        files = self._find_session_files(session_id, user_id)
        return [self._read_jsonl(f) for f in files]

    def list_sessions(self, user_id: Optional[str] = None) -> List[str]:
        """列出某用户的所有会话 ID"""
        if user_id:
            search_dir = self.transcript_dir / user_id
        else:
            search_dir = self.transcript_dir

        if not search_dir.exists():
            return []

        session_ids = set()
        for f in search_dir.glob("*.jsonl"):
            parts = f.stem.rsplit("_", 1)
            if parts:
                session_ids.add(parts[0])
        return sorted(session_ids)

    def replay(self, session_id: str, from_turn: int = 0, user_id: Optional[str] = None) -> List[Dict]:
        """回溯到某轮对话（from_turn 为 0-based 消息索引）"""
        messages = self.load(session_id, user_id)
        return messages[from_turn:]

    def delete(self, session_id: str, user_id: Optional[str] = None) -> int:
        """删除某会话的所有 transcript"""
        files = self._find_session_files(session_id, user_id)
        for f in files:
            f.unlink(missing_ok=True)
        return len(files)

    def _find_session_files(self, session_id: str, user_id: Optional[str] = None) -> List[Path]:
        if user_id:
            search_dir = self.transcript_dir / user_id
        else:
            search_dir = self.transcript_dir

        if not search_dir.exists():
            return []
        return sorted(search_dir.glob(f"{session_id}_*.jsonl"))

    @staticmethod
    def _read_jsonl(filepath: Path) -> List[Dict]:
        messages = []
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    messages.append(json.loads(line))
        return messages
