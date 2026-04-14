import logging
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class HybridSearcher:
    """混合检索器: Vector + FTS5 双路检索与分数融合

    支持两种融合策略:
    - weighted: 加权求和 (默认)
    - rrf: Reciprocal Rank Fusion
    """

    def __init__(self, weights: Dict[str, float] = None, strategy: str = "weighted"):
        self.weights = weights or {"vector": 0.7, "fts": 0.3}
        self.strategy = strategy

    def fuse(
        self,
        vector_results: List[Tuple[str, float]],
        fts_results: List[Tuple[str, float]],
        top_k: int = 5,
    ) -> List[Tuple[str, float]]:
        """融合两路检索结果

        Args:
            vector_results: [(chunk_id, score), ...] 按相似度降序
            fts_results: [(chunk_id, score), ...] 按 FTS rank 降序
            top_k: 返回条数
        """
        if self.strategy == "rrf":
            return self._rrf_fuse(vector_results, fts_results, top_k)
        return self._weighted_fuse(vector_results, fts_results, top_k)

    def _weighted_fuse(
        self,
        vector_results: List[Tuple[str, float]],
        fts_results: List[Tuple[str, float]],
        top_k: int,
    ) -> List[Tuple[str, float]]:
        scores: Dict[str, float] = {}
        w_vec = self.weights.get("vector", 0.7)
        w_fts = self.weights.get("fts", 0.3)

        vec_max = max((s for _, s in vector_results), default=1.0) or 1.0
        for cid, score in vector_results:
            scores[cid] = scores.get(cid, 0.0) + w_vec * (score / vec_max)

        fts_max = max((s for _, s in fts_results), default=1.0) or 1.0
        for cid, score in fts_results:
            scores[cid] = scores.get(cid, 0.0) + w_fts * (score / fts_max)

        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return ranked[:top_k]

    def _rrf_fuse(
        self,
        vector_results: List[Tuple[str, float]],
        fts_results: List[Tuple[str, float]],
        top_k: int,
        k: int = 60,
    ) -> List[Tuple[str, float]]:
        """Reciprocal Rank Fusion: score = sum(1 / (k + rank))"""
        scores: Dict[str, float] = {}

        for rank, (cid, _) in enumerate(vector_results):
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank + 1)

        for rank, (cid, _) in enumerate(fts_results):
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank + 1)

        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return ranked[:top_k]
