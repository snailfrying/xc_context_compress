"""测试LLMLingua-2集成"""
import pytest

try:
    from llmlingua import PromptCompressor
    HAS_LLMLINGUA = True
except ImportError:
    HAS_LLMLINGUA = False


@pytest.mark.skipif(not HAS_LLMLINGUA, reason="llmlingua not installed")
def test_llmlingua2_processor():
    """测试L2处理器"""
    from context_distiller.prompt_distiller.processors.text.npu_llmlingua import NPULLMLinguaProcessor

    processor = NPULLMLinguaProcessor()

    test_text = (
        "【背景说明】这是一份关于公司内部项目管理系统升级的会议纪要。"
        "会议时间：2023年10月25日 上午10:00。"
        "参会人员：张三（后端组长）、李四（前端组长）、王五（产品经理）、赵六（测试组长）。"
        "【会议内容】王五：今天我们主要讨论一下新的项目管理系统 v2.0 版本的上线计划。"
        "目前需求已经全部确定，大家汇报一下进度吧。"
        "张三：后端接口已经开发完毕，目前正在进行内部的单元测试。预计下周三可以全部联调完。"
        "不过在数据库迁移的过程中，发现一些历史遗留的脏数据，处理起来需要多花半天时间。"
    )

    result = processor.process(test_text, rate=0.4)

    assert "text" in result
    assert "stats" in result
    assert result["stats"].input_tokens > 0
    assert result["stats"].output_tokens > 0
    assert result["stats"].compression_ratio > 0


@pytest.mark.skipif(not HAS_LLMLINGUA, reason="llmlingua not installed")
def test_llmlingua2_fallback():
    """测试L2处理器降级"""
    from context_distiller.prompt_distiller.processors.text.npu_llmlingua import NPULLMLinguaProcessor

    processor = NPULLMLinguaProcessor()
    result = processor.process("short text")

    assert "text" in result
    assert result["stats"].latency_ms >= 0
