# Context Distiller v2.0 API 完整参考文档

## 目录

1. [Python SDK API](#python-sdk-api)
2. [REST API](#rest-api)
3. [CLI命令行](#cli命令行)
4. [配置参数](#配置参数)
5. [数据模型](#数据模型)

---

## Python SDK API

### 1. DistillerClient

主客户端类，提供所有核心功能。

#### 初始化

```python
from context_distiller.sdk import DistillerClient

client = DistillerClient(
    profile="balanced",  # 可选: "speed", "balanced", "accuracy"
    config=None          # 可选: 自定义配置字典
)
```

**参数说明**:

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| profile | str | "balanced" | 预设配置模式 |
| config | dict | None | 自定义配置，覆盖默认值 |

**Profile 选项**:

- `speed`: 极速模式，使用L0压缩，<10ms延迟
- `balanced`: 平衡模式，使用L2压缩，~200ms延迟
- `accuracy`: 精准模式，使用L3压缩，1-3s延迟

#### 方法: process()

处理输入数据（文本/文档/图像）。

```python
result = client.process(
    query=None,          # 可选: 查询文本
    data=["text"],       # 必需: 数据列表
    profile=None         # 可选: 覆盖初始化的profile
)
```

**参数说明**:

| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| query | str | 否 | 查询上下文（保留字段） |
| data | list[str] | 是 | 待处理的数据列表 |
| profile | str | 否 | 临时覆盖profile设置 |

**返回值**: `ProcessedResult`

```python
{
    "optimized_prompt": [
        {"type": "text", "content": "压缩后的文本"}
    ],
    "stats": {
        "input_tokens": 1000,
        "output_tokens": 400,
        "compression_ratio": 0.6,
        "latency_ms": 150.5
    },
    "metadata": {"profile": "balanced"}
}
```

**使用示例**:

```python
# 示例1: 压缩单个文本
result = client.process(data=["这是一段很长的文本..."])
print(f"压缩率: {result.stats.compression_ratio:.2%}")

# 示例2: 批量处理
result = client.process(data=[
    "文本1",
    "文本2",
    "文本3"
])

# 示例3: 处理文档
result = client.process(data=["document.pdf"])

# 示例4: 处理图像
result = client.process(data=["image1.jpg", "image2.png"])

# 示例5: 混合处理
result = client.process(data=[
    "文本内容",
    "report.pdf",
    "chart.png"
])
```

#### 方法: search_memory()

检索用户长久记忆。

```python
results = client.search_memory(
    query="关键词",      # 必需: 检索查询
    top_k=5             # 可选: 返回结果数
)
```

**参数说明**:

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| query | str | - | 检索查询文本 |
| top_k | int | 5 | 返回的最大结果数 |

**返回值**: dict

```python
{
    "chunks": [
        {
            "content": "记忆内容",
            "source": "file.py#L10"
        }
    ],
    "scores": [0.95, 0.87]
}
```

**使用示例**:

```python
# 示例1: 基础检索
results = client.search_memory("Python版本")
for chunk in results['chunks']:
    print(f"{chunk['source']}: {chunk['content']}")

# 示例2: 限制结果数
results = client.search_memory("配置", top_k=3)

# 示例3: 检查是否有结果
results = client.search_memory("不存在的内容")
if not results['chunks']:
    print("未找到相关记忆")
```

#### 方法: store_memory()

存储新的记忆片段。

```python
result = client.store_memory(
    content="记忆内容",   # 必需: 要存储的内容
    source="file.py#L10", # 必需: 来源标识
    metadata=None         # 可选: 元数据字典
)
```

**参数说明**:

| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| content | str | 是 | 记忆内容文本 |
| source | str | 是 | 来源标识（建议格式: file#L行号） |
| metadata | dict | 否 | 附加元数据 |

**返回值**: dict

```python
{
    "chunk_id": "123",
    "status": "stored"
}
```

**使用示例**:

```python
# 示例1: 存储配置信息
client.store_memory(
    content="项目使用Python 3.10",
    source="config.py#L1"
)

# 示例2: 带元数据存储
client.store_memory(
    content="API端口8080",
    source="settings.yaml#L5",
    metadata={"type": "config", "priority": "high"}
)

# 示例3: 存储用户偏好
client.store_memory(
    content="用户偏好使用深色主题",
    source="user_profile#preferences"
)
```

---

## 数据类型自动识别

`process()` 方法会自动识别数据类型：

| 数据特征 | 识别为 | 处理方式 |
|----------|--------|----------|
| 以 http:// 或 https:// 开头 | URL | 下载后处理 |
| 以 .pdf 结尾 | PDF文档 | 使用文档处理器 |
| 以 .docx 结尾 | Word文档 | 使用文档处理器 |
| 以 .jpg/.png 结尾 | 图像 | 使用图像处理器 |
| 其他 | 纯文本 | 使用文本处理器 |

**支持的文件格式**:

- **文档**: PDF, DOCX, PPTX, XLSX, HTML, MD
- **图像**: JPG, PNG, BMP, GIF
- **文本**: TXT, JSON, XML, CSV

---

## 错误处理

```python
from context_distiller.sdk import DistillerClient

client = DistillerClient()

try:
    result = client.process(data=["test.pdf"])
except FileNotFoundError:
    print("文件不存在")
except ValueError as e:
    print(f"参数错误: {e}")
except Exception as e:
    print(f"处理失败: {e}")
```

**常见错误**:

- `FileNotFoundError`: 文件路径不存在
- `ValueError`: 参数格式错误
- `RuntimeError`: 处理器运行失败
