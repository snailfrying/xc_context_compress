# 使用示例集合

## 目录

1. [基础示例](#基础示例)
2. [进阶示例](#进阶示例)
3. [集成示例](#集成示例)
4. [实战案例](#实战案例)

---

## 基础示例

### 示例1: 文本压缩

```python
from context_distiller.sdk import DistillerClient

# 创建客户端
client = DistillerClient(profile="balanced")

# 压缩文本
text = """
人工智能技术正在快速发展，深度学习、自然语言处理、
计算机视觉等领域取得了重大突破。大语言模型的出现
更是推动了AI应用的普及。
""" * 10

result = client.process(data=[text])

print(f"原始长度: {len(text)} 字符")
print(f"输入tokens: {result.stats.input_tokens}")
print(f"输出tokens: {result.stats.output_tokens}")
print(f"压缩率: {result.stats.compression_ratio:.2%}")
print(f"处理时间: {result.stats.latency_ms:.2f}ms")
```

---

### 示例2: 文档解析

```python
# 解析PDF文档
result = client.process(data=["report.pdf"])
text_content = result.optimized_prompt[0]['content']

# 解析Word文档
result = client.process(data=["document.docx"])

# 批量解析
files = ["file1.pdf", "file2.docx", "file3.pptx"]
result = client.process(data=files)
```

---

### 示例3: 记忆存储与检索

```python
# 存储配置信息
client.store_memory(
    content="项目使用Python 3.10",
    source="config.py#L1"
)

client.store_memory(
    content="数据库使用PostgreSQL 14",
    source="settings.yaml#L10"
)

# 检索记忆
results = client.search_memory("Python版本", top_k=3)
for chunk in results['chunks']:
    print(f"{chunk['source']}: {chunk['content']}")
```

---

## 进阶示例

### 示例4: 不同压缩级别对比

```python
import time

text = "测试文本内容" * 100
profiles = ["speed", "balanced", "accuracy"]

for profile in profiles:
    client = DistillerClient(profile=profile)
    start = time.time()
    result = client.process(data=[text])
    elapsed = (time.time() - start) * 1000

    print(f"\n{profile.upper()} 模式:")
    print(f"  压缩率: {result.stats.compression_ratio:.2%}")
    print(f"  延迟: {elapsed:.2f}ms")
```

---

### 示例5: 批量文档处理

```python
import os
from pathlib import Path

# 获取所有PDF文件
pdf_dir = Path("documents")
pdf_files = list(pdf_dir.glob("*.pdf"))

client = DistillerClient(profile="balanced")

# 批量处理并保存结果
results = {}
for pdf in pdf_files:
    result = client.process(data=[str(pdf)])
    results[pdf.name] = {
        "compression": result.stats.compression_ratio,
        "tokens": result.stats.output_tokens
    }

# 输出统计
for name, stats in results.items():
    print(f"{name}: {stats['compression']:.2%} ({stats['tokens']} tokens)")
```

---

### 示例6: 图像去重

```python
# 处理多张截图，自动去重
images = [
    "screenshot1.png",
    "screenshot2.png",  # 与screenshot1相似
    "screenshot3.png",
    "screenshot4.png"   # 与screenshot3相似
]

result = client.process(data=images)
print(f"输入图像: {len(images)}")
print(f"去重后: {len(result.optimized_prompt)}")
```

---

## 集成示例

### 示例7: 集成到RAG系统

```python
from context_distiller.sdk import DistillerClient

class RAGSystem:
    def __init__(self):
        self.client = DistillerClient(profile="balanced")
        self.vector_db = None  # 你的向量数据库

    def query(self, question, top_k=5):
        # 1. 向量检索
        docs = self.vector_db.search(question, top_k=top_k)

        # 2. 压缩检索结果
        doc_texts = [doc['content'] for doc in docs]
        result = self.client.process(data=doc_texts)
        compressed_context = result.optimized_prompt[0]['content']

        # 3. 构建prompt
        prompt = f"Context: {compressed_context}\n\nQuestion: {question}"

        return prompt

# 使用
rag = RAGSystem()
prompt = rag.query("什么是人工智能？")
```

---

### 示例8: Agent记忆系统

```python
class AgentWithMemory:
    def __init__(self, agent_id):
        self.agent_id = agent_id
        self.client = DistillerClient()

    def remember(self, content, category):
        """存储记忆"""
        self.client.store_memory(
            content=content,
            source=f"agent_{self.agent_id}#{category}",
            metadata={"agent_id": self.agent_id}
        )

    def recall(self, query, top_k=5):
        """回忆记忆"""
        results = self.client.search_memory(query, top_k=top_k)
        return [c['content'] for c in results['chunks']]

    def process_conversation(self, user_input):
        # 1. 回忆相关记忆
        memories = self.recall(user_input, top_k=3)
        context = "\n".join(memories)

        # 2. 处理对话
        response = f"基于记忆: {context}\n回答: ..."

        # 3. 存储新记忆
        self.remember(
            content=f"用户询问: {user_input}",
            category="conversation"
        )

        return response

# 使用
agent = AgentWithMemory("agent_001")
agent.remember("用户喜欢简洁的回答", "preference")
response = agent.process_conversation("如何使用Python?")
```

---

### 示例9: FastAPI集成

```python
from fastapi import FastAPI, HTTPException
from context_distiller.sdk import DistillerClient
from pydantic import BaseModel

app = FastAPI()
client = DistillerClient()

class CompressRequest(BaseModel):
    text: str
    profile: str = "balanced"

@app.post("/compress")
async def compress_text(request: CompressRequest):
    try:
        result = client.process(data=[request.text])
        return {
            "compressed": result.optimized_prompt[0]['content'],
            "stats": {
                "compression_ratio": result.stats.compression_ratio,
                "latency_ms": result.stats.latency_ms
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 运行: uvicorn main:app --reload
```

---

## 实战案例

### 案例1: 智能客服系统

```python
class CustomerServiceBot:
    def __init__(self):
        self.client = DistillerClient(profile="speed")
        self.conversation_history = []

    def add_message(self, role, content):
        self.conversation_history.append(f"{role}: {content}")

    def get_context(self):
        # 压缩对话历史
        if len(self.conversation_history) > 10:
            history_text = "\n".join(self.conversation_history)
            result = self.client.process(data=[history_text])
            return result.optimized_prompt[0]['content']
        return "\n".join(self.conversation_history)

    def respond(self, user_input):
        self.add_message("用户", user_input)
        context = self.get_context()

        # 生成回复（这里简化）
        response = f"基于上下文回复: {user_input}"
        self.add_message("客服", response)

        return response

# 使用
bot = CustomerServiceBot()
bot.respond("我想查询订单")
bot.respond("订单号是12345")
```

---

### 案例2: 文档知识库

```python
import os
from pathlib import Path

class DocumentKnowledgeBase:
    def __init__(self, docs_dir):
        self.docs_dir = Path(docs_dir)
        self.client = DistillerClient(profile="balanced")
        self.index = {}

    def build_index(self):
        """构建文档索引"""
        for doc_file in self.docs_dir.glob("**/*.pdf"):
            # 解析文档
            result = self.client.process(data=[str(doc_file)])
            content = result.optimized_prompt[0]['content']

            # 存储到记忆
            self.client.store_memory(
                content=content,
                source=f"docs/{doc_file.name}",
                metadata={"type": "document"}
            )

            print(f"已索引: {doc_file.name}")

    def search(self, query, top_k=5):
        """搜索文档"""
        results = self.client.search_memory(query, top_k=top_k)
        return results['chunks']

# 使用
kb = DocumentKnowledgeBase("./documents")
kb.build_index()
results = kb.search("人工智能应用")
```

---

### 案例3: 多语言文档处理

```python
class MultilingualProcessor:
    def __init__(self):
        self.client = DistillerClient()

    def process_document(self, file_path, language="auto"):
        # 解析文档
        result = self.client.process(data=[file_path])
        content = result.optimized_prompt[0]['content']

        # 存储带语言标签
        self.client.store_memory(
            content=content,
            source=f"docs/{Path(file_path).name}",
            metadata={"language": language}
        )

        return content

    def search_by_language(self, query, language):
        # 检索特定语言的文档
        results = self.client.search_memory(query, top_k=10)
        # 过滤语言（需要扩展后端支持）
        return results['chunks']

# 使用
processor = MultilingualProcessor()
processor.process_document("report_en.pdf", language="en")
processor.process_document("报告_zh.pdf", language="zh")
```
