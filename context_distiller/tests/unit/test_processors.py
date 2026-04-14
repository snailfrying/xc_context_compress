import pytest
from context_distiller.prompt_distiller.processors.text.cpu_regex import CPURegexProcessor


class TestCPURegexProcessor:
    def test_process_basic(self):
        processor = CPURegexProcessor()
        text = "This is a test text with some stopwords and extra spaces."
        result = processor.process(text)
        assert "text" in result
        assert "stats" in result
        assert result["stats"].compression_ratio >= 0

    def test_process_empty(self):
        processor = CPURegexProcessor()
        result = processor.process("")
        assert "text" in result

    def test_process_whitespace(self):
        processor = CPURegexProcessor()
        result = processor.process("   lots   of   spaces   here   ")
        assert "text" in result

    def test_token_estimation(self):
        processor = CPURegexProcessor()
        text = "Hello world this is a test"
        tokens = processor.estimate_tokens(text)
        assert tokens > 0

    def test_get_stats(self):
        processor = CPURegexProcessor()
        stats = processor.get_stats(100, 60, 5.0)
        assert stats.compression_ratio == pytest.approx(0.4)
        assert stats.latency_ms == 5.0


class TestCPUSelectiveProcessor:
    def test_fallback_compress(self):
        from context_distiller.prompt_distiller.processors.text.cpu_selective import CPUSelectiveProcessor
        processor = CPUSelectiveProcessor(reduce_ratio=0.5)
        text = "First sentence is important. Second one has details. Third adds context. Fourth is filler."
        result = processor.process(text)
        assert "text" in result
        assert "stats" in result
        assert len(result["text"]) <= len(text)

    def test_empty_input(self):
        from context_distiller.prompt_distiller.processors.text.cpu_selective import CPUSelectiveProcessor
        processor = CPUSelectiveProcessor()
        result = processor.process("")
        assert "text" in result


class TestGPUSummarizerProcessor:
    def test_fallback(self):
        from context_distiller.prompt_distiller.processors.text.gpu_summarizer import GPUSummarizerProcessor
        processor = GPUSummarizerProcessor(model_url="http://invalid:9999")
        text = "这是一段很长的测试文本。" * 20
        result = processor.process(text)
        assert "text" in result
        assert "stats" in result
        assert len(result["text"]) < len(text)


class TestCPUNativeProcessor:
    def test_process_nonexistent_file(self):
        from context_distiller.prompt_distiller.processors.document.cpu_native import CPUNativeProcessor
        processor = CPUNativeProcessor()
        result = processor.process("nonexistent_file.pdf")
        assert "text" in result or "stats" in result


class TestGPUDeepSeekProcessor:
    def test_fallback_on_nonexistent(self):
        from context_distiller.prompt_distiller.processors.document.gpu_deepseek import GPUDeepSeekProcessor
        processor = GPUDeepSeekProcessor(model_url="http://invalid:9999")
        result = processor.process("nonexistent.png")
        assert "text" in result
        assert "stats" in result
