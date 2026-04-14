"""
Context Distiller v2.0 使用示例
"""

from context_distiller.sdk import DistillerClient
from context_distiller.schemas.events import EventPayload
from context_distiller.schemas.config import ProfileConfig


def example_text_compression():
    """示例：文本压缩"""
    print("=== 文本压缩示例 ===")

    client = DistillerClient(profile="balanced")

    long_text = """
    这是一段很长的文本，包含了大量的信息。
    Context Distiller 可以自动压缩这些内容，
    保留关键信息，去除冗余部分。
    """ * 10

    result = client.process(data=[long_text])
    print(f"压缩率: {result.stats.compression_ratio:.2%}")
    print(f"延迟: {result.stats.latency_ms:.2f}ms")


def example_memory_operations():
    """示例：记忆操作"""
    print("\n=== 记忆操作示例 ===")

    client = DistillerClient()

    # 存储记忆
    result = client.store_memory(
        content="项目使用Python 3.12",
        source="project_config#L1",
        metadata={"type": "config"}
    )
    print(f"存储结果: {result}")

    # 检索记忆
    search_result = client.search_memory("Python版本", top_k=3)
    print(f"检索到 {len(search_result['chunks'])} 条记忆")


if __name__ == "__main__":
    example_text_compression()
    example_memory_operations()
