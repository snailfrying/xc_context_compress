# Context Distiller v2.0 用户指南

## 目录

1. [快速开始](#快速开始)
2. [核心功能](#核心功能)
3. [使用场景](#使用场景)
4. [最佳实践](#最佳实践)
5. [性能优化](#性能优化)

---

## 快速开始

### 安装

```bash
# 创建环境
conda env create -f environment.yml
conda activate context_distiller

# 安装项目
pip install -e .

# 验证安装
python verify_installation.py --mode basic
```

### 第一个示例

```python
from context_distiller.sdk import DistillerClient

# 创建客户端
client = DistillerClient(profile="balanced")

# 压缩文本
result = client.process(data=["这是一段很长的文本..."])
print(f"压缩率: {result.stats.compression_ratio:.2%}")
```

---

## 核心功能

### 1. 文本压缩

**功能**: 压缩长文本，保留关键信息

**适用场景**:
- RAG系统上下文优化
- 对话历史压缩
- 文档摘要生成

**使用方法**:

```python
# 基础压缩
client = DistillerClient(profile="speed")
result = client.process(data=["长文本内容"])

# 查看压缩效果
print(f"输入: {result.stats.input_tokens} tokens")
print(f"输出: {result.stats.output_tokens} tokens")
print(f"压缩率: {result.stats.compression_ratio:.2%}")
print(f"延迟: {result.stats.latency_ms:.2f}ms")
```

**压缩级别选择**:

| 场景 | 推荐级别 | Profile | 说明 |
|------|----------|---------|------|
| 实时对话 | L0 | speed | 极速响应 |
| 文档预处理 | L2 | balanced | 平衡性能 |
| 离线分析 | L3 | accuracy | 最佳质量 |

---

### 2. 文档解析

**功能**: 解析各类文档格式为文本

**支持格式**: PDF, Word, PPT, Excel, HTML, Markdown

**使用方法**:

```python
# 解析单个文档
result = client.process(data=["report.pdf"])

# 批量解析
result = client.process(data=[
    "doc1.pdf",
    "doc2.docx",
    "doc3.pptx"
])

# 解析后压缩
client = DistillerClient(profile="balanced")
result = client.process(data=["large_document.pdf"])
```

**文档类型对比**:

| 格式 | 解析器 | 速度 | 质量 | 说明 |
|------|--------|------|------|------|
| PDF | PyMuPDF | 快 | 高 | 推荐 |
| PDF | MarkItDown | 中 | 高 | 更多功能 |
| Word | python-docx | 快 | 高 | 原生支持 |
| PPT | MarkItDown | 中 | 中 | 提取文本 |

---

### 3. 图像处理

**功能**: 图像预处理和去重

**特性**:
- pHash去重（自动识别相似图像）
- 自适应降维（减少token消耗）
- Tile优化（按模型计费策略调整）

**使用方法**:

```python
# 批量处理图像
result = client.process(data=[
    "screenshot1.png",
    "screenshot2.png",
    "screenshot3.png"
])

# 自动去重
# 如果screenshot2和screenshot3相似，只保留一张
```

---

### 4. 记忆管理

**功能**: 跨会话持久化记忆

**使用场景**:
- 用户偏好存储
- 项目配置记录
- 知识库构建

**使用方法**:

```python
# 存储记忆
client.store_memory(
    content="用户偏好使用深色主题",
    source="user_profile#preferences"
)

# 检索记忆
results = client.search_memory("主题偏好", top_k=3)
for chunk in results['chunks']:
    print(f"{chunk['source']}: {chunk['content']}")
```

**记忆组织建议**:

```
记忆类型          source格式              示例
配置信息          config.yaml#L行号       config.yaml#L10
用户偏好          user_profile#类别       user_profile#theme
项目规则          rules.md#章节           rules.md#coding_style
API文档           api_docs#端点名         api_docs#/v1/users
```

---

## 使用场景

### 场景1: RAG系统优化

**问题**: 检索到的文档过长，超出模型上下文限制

**解决方案**:

```python
from context_distiller.sdk import DistillerClient

# 初始化
client = DistillerClient(profile="balanced")

# RAG检索后压缩
retrieved_docs = ["文档1内容...", "文档2内容...", "文档3内容..."]
result = client.process(data=retrieved_docs)

# 使用压缩后的内容
compressed_context = result.optimized_prompt[0]['content']
```

**效果**: 压缩率60-80%，保留关键信息

---

### 场景2: 对话历史管理

**问题**: 长对话历史导致token消耗过大

**解决方案**:

```python
# 定期压缩对话历史
conversation_history = [
    "用户: 问题1",
    "助手: 回答1",
    "用户: 问题2",
    "助手: 回答2",
    # ... 更多对话
]

# 压缩历史
history_text = "\n".join(conversation_history)
result = client.process(data=[history_text])
compressed_history = result.optimized_prompt[0]['content']
```

---

### 场景3: 文档批量处理

**问题**: 需要处理大量PDF文档

**解决方案**:

```python
import os

# 获取所有PDF文件
pdf_files = [f for f in os.listdir(".") if f.endswith(".pdf")]

# 批量处理
client = DistillerClient(profile="speed")
for pdf in pdf_files:
    result = client.process(data=[pdf])
    print(f"{pdf}: 压缩率 {result.stats.compression_ratio:.2%}")
```

---

### 场景4: Agent记忆系统

**问题**: Agent需要记住用户偏好和历史交互

**解决方案**:

```python
# 会话开始时加载记忆
results = client.search_memory("用户偏好", top_k=5)
user_context = "\n".join([c['content'] for c in results['chunks']])

# 会话中存储新信息
client.store_memory(
    content="用户喜欢简洁的回答",
    source="session_2024_03_11#preference"
)

# 会话结束时总结
client.store_memory(
    content="讨论了Python项目架构",
    source="session_2024_03_11#summary"
)
```

---

## 最佳实践

### 1. Profile选择

```python
# 实时场景 - 使用speed
client = DistillerClient(profile="speed")

# 批量处理 - 使用balanced
client = DistillerClient(profile="balanced")

# 离线分析 - 使用accuracy（需GPU）
client = DistillerClient(profile="accuracy")
```

### 2. 批量处理优化

```python
# ❌ 不推荐：逐个处理
for text in texts:
    result = client.process(data=[text])

# ✅ 推荐：批量处理
result = client.process(data=texts)
```

### 3. 错误处理

```python
try:
    result = client.process(data=["document.pdf"])
except FileNotFoundError:
    print("文件不存在")
except Exception as e:
    print(f"处理失败: {e}")
    # 降级处理
    result = client.process(data=["备用文本"])
```

### 4. 记忆管理

```python
# 使用有意义的source标识
client.store_memory(
    content="API密钥存储在环境变量",
    source="security_guide#api_keys"  # ✅ 清晰
    # source="note1"  # ❌ 不清晰
)

# 添加元数据便于过滤
client.store_memory(
    content="使用pytest进行测试",
    source="dev_guide#testing",
    metadata={"category": "development", "priority": "high"}
)
```

---

## 性能优化

### 1. 硬件配置建议

| 场景 | CPU | 内存 | GPU | 说明 |
|------|-----|------|-----|------|
| 轻量级 | 2核 | 4GB | 无 | L0压缩 |
| 标准 | 4核 | 8GB | 无 | L2压缩 |
| 高性能 | 8核 | 16GB | 6GB+ | L3压缩 |

### 2. 配置优化

```yaml
# 极速配置
prompt_distiller:
  profile: "speed"
  text:
    default_level: "L0"

# 平衡配置
prompt_distiller:
  profile: "balanced"
  text:
    default_level: "L2"
```

### 3. 缓存策略

```python
# 使用缓存避免重复处理
cache = {}

def process_with_cache(text):
    text_hash = hash(text)
    if text_hash in cache:
        return cache[text_hash]

    result = client.process(data=[text])
    cache[text_hash] = result
    return result
```
