import sqlite3
import json
import struct
import logging
import httpx
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from .base import MemoryBackend
from ...schemas.memory import MemoryChunk, SearchResult

logger = logging.getLogger(__name__)


def _serialize_f32(vec: List[float]) -> bytes:
    return struct.pack(f"{len(vec)}f", *vec)


class OpenClawBackend(MemoryBackend):
    """OpenClaw 风格后端: SQLite + FTS5 + sqlite-vec (可选) + .md 文件

    隔离模型:
        memories 表通过 (user_id, agent_id) 复合键做多租户隔离。
        - user_id:  自然人用户标识
        - agent_id: Agent 实例标识
        - category: 记忆类型 (fact / preference / rule / profile / note / system)

    同一 user_id 下不同 agent_id 的记忆互相独立。
    """

    def __init__(self, config: Dict):
        db_path = config.get("db_path", "memory.db")
        self.memory_paths = config.get("memory_paths", ["MEMORY.md"])
        self.search_weights = config.get("search_weights", {"vector": 0.7, "fts": 0.3})
        self._embedding_model_name = config.get("embedding_model", "bge-m3")
        self._embedding_provider = config.get("embedding_provider", "ollama")
        self._embedding_base_url = config.get("embedding_base_url", "http://localhost:11434")
        self._embedding_model = None
        self._vec_enabled = False

        self.is_memory = db_path == ":memory:"
        if self.is_memory:
            self._conn = sqlite3.connect(db_path, check_same_thread=False)
            self.db_path = db_path
        else:
            self.db_path = Path(db_path)
            self._conn = None

        self._init_db()

    # ================================================================ connection
    def _get_conn(self):
        if self.is_memory:
            return self._conn
        return sqlite3.connect(self.db_path)

    def _close_conn(self, conn):
        if not self.is_memory:
            conn.close()

    # ================================================================ schema
    def _init_db(self):
        conn = self._get_conn()
        # Create the newest schema for fresh DBs.
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id   TEXT NOT NULL DEFAULT '',
                agent_id  TEXT NOT NULL DEFAULT '',
                category  TEXT NOT NULL DEFAULT 'fact',
                content   TEXT NOT NULL,
                source    TEXT NOT NULL DEFAULT '',
                metadata  TEXT DEFAULT '{}',
                embedding BLOB DEFAULT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # Auto-migrate older DBs that were created before multi-tenant isolation.
        # SQLite doesn't support IF NOT EXISTS for ADD COLUMN, so we must probe.
        try:
            cols = {r[1] for r in conn.execute("PRAGMA table_info(memories)").fetchall()}
            if "user_id" not in cols:
                conn.execute("ALTER TABLE memories ADD COLUMN user_id TEXT NOT NULL DEFAULT ''")
            if "agent_id" not in cols:
                conn.execute("ALTER TABLE memories ADD COLUMN agent_id TEXT NOT NULL DEFAULT ''")
            if "category" not in cols:
                conn.execute("ALTER TABLE memories ADD COLUMN category TEXT NOT NULL DEFAULT 'fact'")
            if "metadata" not in cols:
                conn.execute("ALTER TABLE memories ADD COLUMN metadata TEXT DEFAULT '{}'")
            if "embedding" not in cols:
                conn.execute("ALTER TABLE memories ADD COLUMN embedding BLOB DEFAULT NULL")
            if "created_at" not in cols:
                # ALTER TABLE 不允许非常量默认值（如 CURRENT_TIMESTAMP），先加列再用 UPDATE 补值。
                conn.execute("ALTER TABLE memories ADD COLUMN created_at TIMESTAMP")
                conn.execute("UPDATE memories SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL")
            if "updated_at" not in cols:
                conn.execute("ALTER TABLE memories ADD COLUMN updated_at TIMESTAMP")
                conn.execute("UPDATE memories SET updated_at = CURRENT_TIMESTAMP WHERE updated_at IS NULL")
        except Exception as e:
            # If migration fails, the DB is likely corrupted or of an unexpected schema.
            logger.warning("OpenClaw schema migration skipped/failed: %s", e)

        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_mem_user_agent "
            "ON memories(user_id, agent_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_mem_category "
            "ON memories(user_id, agent_id, category)"
        )
        conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts
            USING fts5(content, source, content_rowid=id)
        """)
        self._try_init_vec(conn)
        conn.commit()
        self._close_conn(conn)

    def _try_init_vec(self, conn):
        try:
            import sqlite_vec
            conn.enable_load_extension(True)
            sqlite_vec.load(conn)
            conn.enable_load_extension(False)
            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS memories_vec
                USING vec0(embedding float[384])
            """)
            self._vec_enabled = True
            logger.info("sqlite-vec enabled for vector search")
        except Exception as e:
            logger.debug("sqlite-vec not available, FTS-only mode: %s", e)
            self._vec_enabled = False

    # ================================================================ embedding
    def _get_embedding(self, text: str) -> Optional[List[float]]:
        if not self._embedding_model_name:
            return None
        
        try:
            if self._embedding_provider == "ollama":
                # Use centralized Ollama server for embeddings
                url = f"{self._embedding_base_url.rstrip('/')}/api/embeddings"
                resp = httpx.post(url, json={
                    "model": self._embedding_model_name,
                    "prompt": text
                }, timeout=10.0)
                if resp.status_code == 200:
                    return resp.json().get("embedding")
                else:
                    logger.warning(f"Ollama embedding failed (HTTP {resp.status_code}): {resp.text}")
                    return None
            
            # Fallback to local sentence-transformers
            if self._embedding_model is None:
                from sentence_transformers import SentenceTransformer
                self._embedding_model = SentenceTransformer(self._embedding_model_name)
            return self._embedding_model.encode(text).tolist()
        except Exception as e:
            logger.warning("Embedding computation failed: %s", e)
            return None

    # ================================================================ helpers
    def _scope_where(self, uid: str, aid: str, category: Optional[str] = None) -> Tuple[str, list]:
        """构建 (user_id, agent_id[, category]) 的 WHERE 子句"""
        clause = "m.user_id = ? AND m.agent_id = ?"
        params: list = [uid, aid]
        if category:
            clause += " AND m.category = ?"
            params.append(category)
        return clause, params

    def _row_to_chunk(self, row, include_id: bool = True) -> MemoryChunk:
        """row: (id, user_id, agent_id, category, content, source, metadata)"""
        return MemoryChunk(
            id=str(row[0]) if include_id else None,
            user_id=row[1] or None,
            agent_id=row[2] or None,
            category=row[3],
            content=row[4],
            source=row[5],
            metadata=json.loads(row[6] or "{}"),
        )

    _SELECT_COLS = "m.id, m.user_id, m.agent_id, m.category, m.content, m.source, m.metadata"

    # ================================================================ search
    def search(
        self, query: str, top_k: int = 5,
        user_id: Optional[str] = None, agent_id: Optional[str] = None,
        category: Optional[str] = None,
    ) -> SearchResult:
        uid, aid = user_id or "", agent_id or ""
        fts_results = self._fts_search(query, top_k * 2, uid, aid, category)

        if self._vec_enabled and self._embedding_model_name:
            vec_results = self._vec_search(query, top_k * 2, uid, aid, category)
            fused = self._hybrid_fuse(vec_results, fts_results, top_k)
        else:
            fused = [(cid, score) for cid, score in fts_results[:top_k]]

        return self._load_chunks_by_ids(fused, uid, aid)

    def _fts_search(
        self, query: str, limit: int,
        uid: str, aid: str, category: Optional[str],
    ) -> List[Tuple[int, float]]:
        conn = self._get_conn()
        scope, params = self._scope_where(uid, aid, category)
        try:
            sql = f"""
                SELECT m.id, f.rank
                FROM memories_fts f
                JOIN memories m ON m.id = f.rowid
                WHERE memories_fts MATCH ? AND {scope}
                ORDER BY f.rank
                LIMIT ?
            """
            cursor = conn.execute(sql, [query] + params + [limit])
            rows = cursor.fetchall()
            return [(r[0], abs(r[1]) if r[1] else 0.0) for r in rows]
        except Exception as e:
            logger.warning("FTS search failed: %s", e)
            return []
        finally:
            self._close_conn(conn)

    def _vec_search(
        self, query: str, limit: int,
        uid: str, aid: str, category: Optional[str],
    ) -> List[Tuple[int, float]]:
        embedding = self._get_embedding(query)
        if embedding is None:
            return []
        conn = self._get_conn()
        scope, params = self._scope_where(uid, aid, category)
        try:
            self._try_init_vec(conn)
            sql = f"""
                SELECT v.rowid, v.distance
                FROM memories_vec v
                JOIN memories m ON m.id = v.rowid
                WHERE {scope}
                ORDER BY v.distance
                LIMIT ?
            """
            cursor = conn.execute(sql, [_serialize_f32(embedding)] + params + [limit])
            return [(r[0], 1.0 / (1.0 + r[1])) for r in cursor.fetchall()]
        except Exception as e:
            logger.warning("Vector search failed: %s", e)
            return []
        finally:
            self._close_conn(conn)

    def _hybrid_fuse(
        self,
        vec_results: List[Tuple[int, float]],
        fts_results: List[Tuple[int, float]],
        top_k: int,
    ) -> List[Tuple[int, float]]:
        from ..user_memory.search import HybridSearcher
        searcher = HybridSearcher(weights=self.search_weights)
        vec_pairs = [(str(cid), score) for cid, score in vec_results]
        fts_pairs = [(str(cid), score) for cid, score in fts_results]
        fused = searcher.fuse(vec_pairs, fts_pairs, top_k)
        return [(int(cid), score) for cid, score in fused]

    def _load_chunks_by_ids(
        self, id_scores: List[Tuple[int, float]], uid: str, aid: str,
    ) -> SearchResult:
        if not id_scores:
            return SearchResult(chunks=[], scores=[], total=0)

        conn = self._get_conn()
        chunks, scores = [], []
        for cid, score in id_scores:
            cursor = conn.execute(
                f"SELECT {self._SELECT_COLS} FROM memories m "
                "WHERE m.id = ? AND m.user_id = ? AND m.agent_id = ?",
                (cid, uid, aid),
            )
            row = cursor.fetchone()
            if row:
                chunks.append(self._row_to_chunk(row))
                scores.append(score)
        self._close_conn(conn)
        return SearchResult(chunks=chunks, scores=scores, total=len(chunks))

    # ================================================================ store
    def store(
        self, chunk: MemoryChunk,
        user_id: Optional[str] = None, agent_id: Optional[str] = None,
    ) -> str:
        conn = self._get_conn()
        uid = user_id or chunk.user_id or ""
        aid = agent_id or chunk.agent_id or ""
        cat = chunk.category or "fact"
        embedding = self._get_embedding(chunk.content)
        embedding_blob = _serialize_f32(embedding) if embedding else None

        cursor = conn.execute(
            "INSERT INTO memories "
            "(user_id, agent_id, category, content, source, metadata, embedding) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (uid, aid, cat, chunk.content, chunk.source,
             json.dumps(chunk.metadata, ensure_ascii=False), embedding_blob),
        )
        row_id = cursor.lastrowid
        conn.execute(
            "INSERT INTO memories_fts (rowid, content, source) VALUES (?, ?, ?)",
            (row_id, chunk.content, chunk.source),
        )
        if self._vec_enabled and embedding_blob:
            try:
                conn.execute(
                    "INSERT INTO memories_vec (rowid, embedding) VALUES (?, ?)",
                    (row_id, embedding_blob),
                )
            except Exception as e:
                logger.warning("Vec insert failed: %s", e)
        conn.commit()
        self._close_conn(conn)
        return str(row_id)

    # ================================================================ update
    def update(
        self, chunk_id: str, content: str,
        user_id: Optional[str] = None, agent_id: Optional[str] = None,
    ) -> bool:
        conn = self._get_conn()
        uid, aid = user_id or "", agent_id or ""
        rid = int(chunk_id)
        embedding = self._get_embedding(content)
        embedding_blob = _serialize_f32(embedding) if embedding else None

        conn.execute(
            "UPDATE memories SET content = ?, embedding = ?, updated_at = CURRENT_TIMESTAMP "
            "WHERE id = ? AND user_id = ? AND agent_id = ?",
            (content, embedding_blob, rid, uid, aid),
        )
        conn.execute("UPDATE memories_fts SET content = ? WHERE rowid = ?", (content, rid))
        if self._vec_enabled and embedding_blob:
            try:
                conn.execute("DELETE FROM memories_vec WHERE rowid = ?", (rid,))
                conn.execute(
                    "INSERT INTO memories_vec (rowid, embedding) VALUES (?, ?)",
                    (rid, embedding_blob),
                )
            except Exception as e:
                logger.warning("Vec update failed: %s", e)
        conn.commit()
        self._close_conn(conn)
        return True

    # ================================================================ forget
    def forget(
        self, chunk_id: str,
        user_id: Optional[str] = None, agent_id: Optional[str] = None,
    ) -> bool:
        conn = self._get_conn()
        uid, aid = user_id or "", agent_id or ""
        rid = int(chunk_id)
        conn.execute("DELETE FROM memories_fts WHERE rowid = ?", (rid,))
        if self._vec_enabled:
            try:
                conn.execute("DELETE FROM memories_vec WHERE rowid = ?", (rid,))
            except Exception:
                pass
        conn.execute(
            "DELETE FROM memories WHERE id = ? AND user_id = ? AND agent_id = ?",
            (rid, uid, aid),
        )
        conn.commit()
        self._close_conn(conn)
        return True

    # ================================================================ get
    def get(
        self, source: str,
        user_id: Optional[str] = None, agent_id: Optional[str] = None,
    ) -> Optional[MemoryChunk]:
        conn = self._get_conn()
        uid, aid = user_id or "", agent_id or ""
        cursor = conn.execute(
            f"SELECT {self._SELECT_COLS} FROM memories m "
            "WHERE m.source = ? AND m.user_id = ? AND m.agent_id = ?",
            (source, uid, aid),
        )
        row = cursor.fetchone()
        self._close_conn(conn)
        if row:
            return self._row_to_chunk(row)
        return None

    # ================================================================ list
    def list_memories(
        self,
        user_id: Optional[str] = None, agent_id: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 50, offset: int = 0,
    ) -> SearchResult:
        conn = self._get_conn()
        uid, aid = user_id or "", agent_id or ""

        where = "WHERE m.user_id = ? AND m.agent_id = ?"
        params: list = [uid, aid]
        if category:
            where += " AND m.category = ?"
            params.append(category)

        count_row = conn.execute(
            f"SELECT COUNT(*) FROM memories m {where}", params
        ).fetchone()
        total = count_row[0] if count_row else 0

        cursor = conn.execute(
            f"SELECT {self._SELECT_COLS} FROM memories m {where} "
            "ORDER BY m.updated_at DESC LIMIT ? OFFSET ?",
            params + [limit, offset],
        )
        chunks = [self._row_to_chunk(r) for r in cursor.fetchall()]
        self._close_conn(conn)
        return SearchResult(
            chunks=chunks,
            scores=[1.0] * len(chunks),
            total=total,
        )
