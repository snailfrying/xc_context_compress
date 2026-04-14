"""
Context Distiller v2.0 功能验证脚本
"""
import sys
import argparse
from pathlib import Path

# 设置UTF-8编码
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')


def check_basic_imports():
    """检查基础导入"""
    print("\n[1/6] 检查基础模块导入...")
    try:
        from context_distiller.schemas import EventPayload, ProfileConfig, TokenStats
        from context_distiller.infra import HardwareProbe, EnvManager
        print("[PASS] 基础模块导入成功")
        return True
    except Exception as e:
        print(f"[FAIL] 基础模块导入失败: {e}")
        return False


def check_hardware():
    """检查硬件探测"""
    print("\n[2/6] 检查硬件探测...")
    try:
        from context_distiller.infra import HardwareProbe
        probe = HardwareProbe()
        info = probe.detect()
        print(f"[PASS] CPU核心: {info['cpu_count']}")
        print(f"[PASS] 内存: {info['memory_gb']:.1f} GB")
        print(f"[PASS] GPU: {'可用' if info['has_gpu'] else '不可用'}")
        return True
    except Exception as e:
        print(f"[FAIL] 硬件探测失败: {e}")
        return False


def check_text_processor():
    """检查文本处理器"""
    print("\n[3/6] 检查文本处理器...")
    try:
        from context_distiller.prompt_distiller.processors.text.cpu_regex import CPURegexProcessor

        processor = CPURegexProcessor()
        test_text = "This is a test text with some stopwords and extra spaces."
        result = processor.process(test_text)

        print(f"[PASS] L0处理器工作正常")
        print(f"  输入tokens: {result['stats'].input_tokens}")
        print(f"  输出tokens: {result['stats'].output_tokens}")
        print(f"  压缩率: {result['stats'].compression_ratio:.2%}")
        return True
    except Exception as e:
        print(f"[FAIL] 文本处理器失败: {e}")
        return False


def check_sdk_client():
    """检查SDK客户端"""
    print("\n[4/6] 检查SDK客户端...")
    try:
        from context_distiller.sdk import DistillerClient

        client = DistillerClient(profile="speed")
        test_data = ["Hello world, this is a test."]
        result = client.process(data=test_data)

        print(f"[PASS] SDK客户端工作正常")
        print(f"  处理结果数: {len(result.optimized_prompt)}")
        return True
    except Exception as e:
        print(f"[FAIL] SDK客户端失败: {e}")
        return False


def check_memory_backend():
    """检查记忆后端"""
    print("\n[5/6] 检查记忆后端...")
    try:
        from context_distiller.memory_gateway.backends.openclaw import OpenClawBackend
        from context_distiller.schemas.memory import MemoryChunk

        backend = OpenClawBackend({"db_path": ":memory:"})

        # 测试存储
        chunk = MemoryChunk(content="测试记忆", source="test#L1")
        chunk_id = backend.store(chunk)

        # 测试检索
        result = backend.search("测试", top_k=1)

        print(f"[PASS] 记忆后端工作正常")
        print(f"  存储ID: {chunk_id}")
        print(f"  检索结果数: {len(result.chunks)}")
        return True
    except Exception as e:
        print(f"[FAIL] 记忆后端失败: {e}")
        return False


def check_gpu_features():
    """检查GPU功能"""
    print("\n[6/6] 检查GPU功能...")
    try:
        import torch
        print(f"[PASS] PyTorch已安装: {torch.__version__}")
        print(f"[PASS] CUDA可用: {torch.cuda.is_available()}")
        if torch.cuda.is_available():
            print(f"[PASS] GPU设备: {torch.cuda.get_device_name(0)}")
        return True
    except ImportError:
        print("[WARN] PyTorch未安装（GPU功能不可用）")
        return None
    except Exception as e:
        print(f"[FAIL] GPU检查失败: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="验证Context Distiller安装")
    parser.add_argument("--mode", choices=["basic", "gpu", "all"], default="basic",
                       help="验证模式: basic(基础), gpu(GPU), all(全部)")
    args = parser.parse_args()

    print("=" * 60)
    print("Context Distiller v2.0 功能验证")
    print("=" * 60)

    results = []

    # 基础检查
    results.append(("基础导入", check_basic_imports()))
    results.append(("硬件探测", check_hardware()))
    results.append(("文本处理", check_text_processor()))
    results.append(("SDK客户端", check_sdk_client()))
    results.append(("记忆后端", check_memory_backend()))

    # GPU检查
    if args.mode in ["gpu", "all"]:
        gpu_result = check_gpu_features()
        if gpu_result is not None:
            results.append(("GPU功能", gpu_result))

    # 总结
    print("\n" + "=" * 60)
    print("验证总结")
    print("=" * 60)

    passed = sum(1 for _, r in results if r is True)
    total = len(results)

    for name, result in results:
        status = "[PASS]" if result else "[FAIL]"
        print(f"{name}: {status}")

    print(f"\n总计: {passed}/{total} 项通过")

    if passed == total:
        print("\n[SUCCESS] 所有功能验证通过！")
        return 0
    else:
        print("\n[WARNING] 部分功能验证失败，请检查安装")
        return 1


if __name__ == "__main__":
    sys.exit(main())
