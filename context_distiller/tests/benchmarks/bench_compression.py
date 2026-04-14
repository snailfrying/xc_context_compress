"""压缩率 & 速度基准测试

运行: pytest context_distiller/tests/benchmarks/bench_compression.py -v -s
"""
import time
import pytest


SAMPLE_TEXT_SHORT = "The quick brown fox jumps over the lazy dog. " * 10
SAMPLE_TEXT_MEDIUM = "这是一段中等长度的测试文本，用于评估不同压缩级别的效果。" * 50
SAMPLE_TEXT_LONG = (
    "In the realm of artificial intelligence, large language models have revolutionized "
    "how we interact with technology. These models, trained on vast corpora of text data, "
    "can generate human-like responses, translate languages, write code, and perform "
    "complex reasoning tasks. However, the cost of running these models is directly "
    "proportional to the number of input tokens processed. "
) * 20


class TestL0Benchmark:
    def test_throughput(self):
        from context_distiller.prompt_distiller.processors.text.cpu_regex import CPURegexProcessor
        processor = CPURegexProcessor()

        start = time.time()
        iterations = 100
        for _ in range(iterations):
            processor.process(SAMPLE_TEXT_LONG)
        elapsed = time.time() - start

        ops_per_sec = iterations / elapsed
        print(f"\nL0 throughput: {ops_per_sec:.1f} ops/sec ({elapsed*1000/iterations:.1f} ms/op)")
        assert ops_per_sec > 10

    def test_compression_ratio(self):
        from context_distiller.prompt_distiller.processors.text.cpu_regex import CPURegexProcessor
        processor = CPURegexProcessor()
        result = processor.process(SAMPLE_TEXT_LONG)
        ratio = result["stats"].compression_ratio
        print(f"\nL0 compression ratio: {ratio:.2%}")
        assert ratio > 0


class TestL1Benchmark:
    def test_compression_ratio(self):
        from context_distiller.prompt_distiller.processors.text.cpu_selective import CPUSelectiveProcessor
        processor = CPUSelectiveProcessor(reduce_ratio=0.5)
        result = processor.process(SAMPLE_TEXT_LONG)
        ratio = result["stats"].compression_ratio
        print(f"\nL1 compression ratio: {ratio:.2%}")
        assert ratio > 0


class TestMemoryBenchmark:
    def test_store_throughput(self):
        from context_distiller.memory_gateway.backends.openclaw import OpenClawBackend
        from context_distiller.schemas.memory import MemoryChunk
        backend = OpenClawBackend({"db_path": ":memory:"})

        start = time.time()
        for i in range(1000):
            chunk = MemoryChunk(content=f"Fact number {i} about testing", source=f"bench.md#L{i}")
            backend.store(chunk, user_id="bench_user")
        elapsed = time.time() - start

        ops_per_sec = 1000 / elapsed
        print(f"\nMemory store: {ops_per_sec:.0f} ops/sec ({elapsed*1000:.1f} ms total)")
        assert ops_per_sec > 100

    def test_search_throughput(self):
        from context_distiller.memory_gateway.backends.openclaw import OpenClawBackend
        from context_distiller.schemas.memory import MemoryChunk
        backend = OpenClawBackend({"db_path": ":memory:"})

        for i in range(100):
            chunk = MemoryChunk(content=f"Knowledge item {i} about topic {i % 10}", source=f"kb.md#L{i}")
            backend.store(chunk, user_id="bench_user")

        start = time.time()
        iterations = 100
        for i in range(iterations):
            backend.search(f"topic {i % 10}", top_k=5, user_id="bench_user")
        elapsed = time.time() - start

        ops_per_sec = iterations / elapsed
        print(f"\nMemory search: {ops_per_sec:.0f} ops/sec ({elapsed*1000/iterations:.1f} ms/op)")
        assert ops_per_sec > 10
