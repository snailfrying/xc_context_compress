"""
Context Distiller v2.0 完整使用示例
演示所有核心功能
"""

from context_distiller.sdk import DistillerClient
from context_distiller.schemas.config import ProfileConfig
import time


def demo_text_compression():
    """示例1: 文本压缩 - 不同压缩级别"""
    print("=" * 60)
    print("示例1: 文本压缩")
    print("=" * 60)

    # 测试文本
    long_text = """
    人工智能（Artificial Intelligence，AI）是计算机科学的一个分支，
    它企图了解智能的实质，并生产出一种新的能以人类智能相似的方式做出反应的智能机器。
    该领域的研究包括机器人、语言识别、图像识别、自然语言处理和专家系统等。
    人工智能从诞生以来，理论和技术日益成熟，应用领域也不断扩大。
    可以设想，未来人工智能带来的科技产品，将会是人类智慧的"容器"。
    """ * 5

    # L0 极速压缩
    print("\n[L0 极速模式]")
    client_speed = DistillerClient(profile="speed")
    start = time.time()
    result = client_speed.process(data=[long_text])
    print(f"压缩率: {result.stats.compression_ratio:.2%}")
    print(f"延迟: {(time.time() - start) * 1000:.2f}ms")

    # L2 平衡模式
    print("\n[L2 平衡模式]")
    client_balanced = DistillerClient(profile="balanced")
    start = time.time()
    result = client_balanced.process(data=[long_text])
    print(f"压缩率: {result.stats.compression_ratio:.2%}")
    print(f"延迟: {(time.time() - start) * 1000:.2f}ms")


def demo_memory_management():
    """示例2: 记忆管理"""
    print("\n" + "=" * 60)
    print("示例2: 记忆管理")
    print("=" * 60)

    client = DistillerClient()

    # 存储多条记忆
    memories = [
        ("项目使用Python 3.10", "config.py#L1"),
        ("数据库使用PostgreSQL", "settings.py#L15"),
        ("API端口设置为8080", "config.yaml#L3"),
    ]

    print("\n[存储记忆]")
    for content, source in memories:
        result = client.store_memory(content, source)
        print(f"存储: {content} -> {result['status']}")

    # 检索记忆
    print("\n[检索记忆]")
    queries = ["Python版本", "数据库", "端口"]
    for query in queries:
        results = client.search_memory(query, top_k=2)
        print(f"\n查询: {query}")
        for chunk in results['chunks']:
            print(f"  - {chunk['content']} ({chunk['source']})")


def demo_batch_processing():
    """示例3: 批量处理"""
    print("\n" + "=" * 60)
    print("示例3: 批量处理多种数据类型")
    print("=" * 60)

    client = DistillerClient(profile="balanced")

    # 模拟批量数据
    data = [
        "这是第一段文本内容，包含一些重要信息。",
        "这是第二段文本内容，也包含一些关键数据。",
        "这是第三段文本内容，需要进行压缩处理。",
    ]

    print("\n[批量压缩]")
    result = client.process(data=data)
    print(f"处理数据数: {len(result.optimized_prompt)}")
    print(f"总压缩率: {result.stats.compression_ratio:.2%}")
    print(f"总延迟: {result.stats.latency_ms:.2f}ms")


def demo_hardware_detection():
    """示例4: 硬件检测"""
    print("\n" + "=" * 60)
    print("示例4: 硬件检测与自适应路由")
    print("=" * 60)

    from context_distiller.infra import HardwareProbe

    probe = HardwareProbe()
    info = probe.detect()

    print("\n[系统信息]")
    print(f"CPU核心数: {info['cpu_count']}")
    print(f"内存大小: {info['memory_gb']:.1f} GB")
    print(f"GPU可用: {info['has_gpu']}")
    print(f"设备类型: {probe.get_device_type()}")


def demo_performance_comparison():
    """示例5: 性能对比"""
    print("\n" + "=" * 60)
    print("示例5: 不同Profile性能对比")
    print("=" * 60)

    test_text = "人工智能技术正在改变世界。" * 100

    profiles = ["speed", "balanced", "accuracy"]
    results = []

    for profile in profiles:
        client = DistillerClient(profile=profile)
        start = time.time()
        result = client.process(data=[test_text])
        elapsed = (time.time() - start) * 1000

        results.append({
            "profile": profile,
            "compression": result.stats.compression_ratio,
            "latency": elapsed
        })

    print("\n{:<12} {:<15} {:<15}".format("Profile", "压缩率", "延迟(ms)"))
    print("-" * 45)
    for r in results:
        print("{:<12} {:<15.2%} {:<15.2f}".format(
            r["profile"], r["compression"], r["latency"]
        ))


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("Context Distiller v2.0 完整功能演示")
    print("=" * 60)

    try:
        demo_text_compression()
        demo_memory_management()
        demo_batch_processing()
        demo_hardware_detection()
        demo_performance_comparison()

        print("\n" + "=" * 60)
        print("所有示例运行完成！")
        print("=" * 60)

    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()
