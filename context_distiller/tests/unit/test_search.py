import pytest
from context_distiller.memory_gateway.user_memory.search import HybridSearcher


class TestHybridSearcher:
    def test_weighted_fuse(self):
        searcher = HybridSearcher(weights={"vector": 0.7, "fts": 0.3})
        vec = [("1", 0.9), ("2", 0.5), ("3", 0.3)]
        fts = [("2", 1.0), ("4", 0.8), ("1", 0.2)]

        result = searcher.fuse(vec, fts, top_k=3)
        ids = [cid for cid, _ in result]
        assert "1" in ids
        assert "2" in ids

    def test_rrf_fuse(self):
        searcher = HybridSearcher(strategy="rrf")
        vec = [("a", 0.9), ("b", 0.7)]
        fts = [("b", 1.0), ("c", 0.5)]

        result = searcher.fuse(vec, fts, top_k=3)
        ids = [cid for cid, _ in result]
        assert "b" in ids

    def test_empty_inputs(self):
        searcher = HybridSearcher()
        result = searcher.fuse([], [], top_k=5)
        assert result == []

    def test_single_source(self):
        searcher = HybridSearcher()
        result = searcher.fuse([("x", 1.0)], [], top_k=5)
        assert len(result) == 1
        assert result[0][0] == "x"
