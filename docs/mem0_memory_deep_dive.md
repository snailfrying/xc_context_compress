# Mem0 记忆系统深度解析

> **定位**：详细介绍 Mem0 的记忆架构、两阶段流水线、存储后端与使用方法
> **GitHub**：https://github.com/mem0ai/mem0
> **官方文档**：https://docs.mem0.ai
> **论文**：["Mem0: Building Production-Ready AI Agents with Scalable Long-Term Memory"](https://arxiv.org/html/2504.19413v1) (arXiv:2504.19413)

---

## 一、核心设计哲学

Mem0 的记忆系统遵循一个根本原则：

> **"Don't stuff the context window, extract what matters."**
> 不要塞满上下文窗口，而是提炼真正重要的内容。

与 OpenClaw 的"文件优先"哲学不同，Mem0 把记忆定位为 LLM 之上的**独立服务层**：每一条对话消息都会经过 LLM 驱动的**事实提取**与**冲突消解**，最终只把高密度的原子事实写入向量库（可选写入图库），检索时再通过语义搜索注入到下游 Agent 的上下文中。

这种设计带来三个关键优势：

| 优势 | 说明 |
|------|------|
| **上下文精简** | 论文实测每轮对话只注入 ~7k token，较 Full-Context 方案减少 91% |
| **跨会话持久** | 记忆按 `user_id` / `agent_id` / `run_id` 隔离，永久可检索 |
| **结构化扩展** | 原子事实 + 知识图谱双轨存储，兼顾语义召回与关系推理 |

---

## 二、记忆对象模型

### 2.1 记忆单元（Memory Unit）

Mem0 把每一条记忆抽象为"原子事实"（atomic fact）—— 一句自然语言陈述加上一组元数据：

```json
{
  "id": "8f9e...c1",
  "memory": "User prefers Python type hints and uses Black with line width 88",
  "hash": "sha256:...",
  "metadata": {"category": "coding_preference"},
  "user_id": "alice",
  "agent_id": "code_assistant",
  "run_id": null,
  "created_at": "2026-04-14T08:21:33Z",
  "updated_at": "2026-04-14T08:21:33Z"
}
```

### 2.2 三层作用域（Scope）

Mem0 的每条记忆最多可同时绑定到四个标识符，用于隔离与过滤：

| 字段 | 含义 | 典型用途 |
|------|------|---------|
| `user_id` | 终端用户 ID | 跨会话的用户画像、偏好 |
| `agent_id` | Agent 实例 ID | 同一用户的不同助手共享或隔离记忆 |
| `app_id` | 应用 ID | 多租户产品隔离 |
| `run_id` | 本次运行/会话 ID | 单次任务的短期状态 |

`add` / `search` / `get_all` / `delete` 都接受相同的标识符作为过滤器。**隐式行为**：只传 `{"user_id": "alice"}` 会自动限制到 `agent_id/app_id/run_id` 为 NULL 的记录上——这是 Mem0 实现"用户级长期记忆"与"会话级短期记忆"自然分层的关键。

### 2.3 记忆类型

| 类型 | 范围 | 说明 |
|------|------|------|
| **Short-term** | 当前会话内 | 对话历史、工具输出、注意力上下文 |
| **Long-term Factual** | 跨会话 | 用户偏好、账户信息、领域事实 |
| **Long-term Episodic** | 跨会话 | 过往交互的摘要、已完成任务的回顾 |
| **Long-term Semantic** | 跨会话 | 概念间的关系，供后续推理使用 |
| **Procedural**（可选）| 跨会话 | 通过 `memory_type="procedural_memory"` 显式创建，记录"如何做某件事" |

默认情况下 `memory_type=None`，Mem0 会自动在短期与长期（语义 + 事件）之间分配。

---

## 三、两阶段流水线

Mem0 最核心的设计是把"写入记忆"拆成两个串行阶段：**Extraction（提取）** 与 **Update（更新）**。每一次 `memory.add(messages, user_id=...)` 都会完整跑一遍这条流水线。

### 3.1 Extraction Phase：从对话中提炼事实

提取阶段的输入由三部分拼装而成：

```
┌─────────────────────────────────────────────────┐
│ 1. Rolling Summary  S                           │
│    ── 数据库中维护的对话滚动摘要                   │
├─────────────────────────────────────────────────┤
│ 2. Recent Window  (m = 10)                      │
│    ── 最近 10 条消息构成的窗口                    │
├─────────────────────────────────────────────────┤
│ 3. Current Exchange                             │
│    ── 本轮新进入的 user / assistant 消息对         │
└─────────────────────────────────────────────────┘
            │
            ▼
    LLM Extractor  φ
            │
            ▼
    Ω = {ω₁, ω₂, …, ωₙ}   候选原子事实集合
```

LLM 会过滤掉客套、工具调用过程、确认性回复等噪声，只输出可跨会话复用的陈述句（"User lives in Berlin"，"User dislikes verbose comments"）。

### 3.2 Update Phase：冲突消解与工具调用

对每一条候选事实 ωᵢ，Mem0 从向量库中召回 **top s = 10** 条语义最相似的已有记忆，然后让 LLM 从四种操作中选一种（以 Tool Call 的形式返回）：

```
            候选事实  ωᵢ
                │
                ▼
      top-10 semantically similar memories
                │
                ▼
        ┌─────────────────────┐
        │   Update LLM 决策    │
        └──────────┬──────────┘
                   │
     ┌─────────┬───┴────┬─────────┐
     ▼         ▼        ▼         ▼
   ADD       UPDATE   DELETE     NOOP
新增原子   合并补充   删除已  无需变更
 事实      信息    过时/矛盾
```

| 操作 | 触发条件 |
|------|---------|
| **ADD** | 新事实与已有记忆无语义重合 |
| **UPDATE** | 已有记忆不完整，可用新事实补充 |
| **DELETE** | 新事实与已有记忆相互矛盾，或已过时 |
| **NOOP** | 新事实已被完全覆盖，无需任何变更 |

**为什么必须走 LLM 决策而不是简单去重？**
因为同一事实会用不同措辞反复出现（"I love dark mode" vs "Please enable dark theme"），而矛盾信息也无法用相似度阈值判别（"I moved from Berlin to Munich" 与旧记录 "lives in Berlin" 语义高度相似却必须触发 DELETE）。让 LLM 参与消解，是 Mem0 在 LOCOMO 基准上超越纯 RAG 方案的关键。

### 3.3 完整数据流

```
user / assistant 消息
        │
        ▼
┌──────────────────────┐
│ 1. memory.add()       │
│    入口调用            │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ 2. Extraction LLM     │  输入：rolling summary + 最近 10 轮 + 当前对
│    提取候选事实        │  输出：Ω = {ω₁, …, ωₙ}
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ 3. Embedding 计算     │  对每个 ωᵢ 生成向量
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ 4. 相似记忆召回        │  向量库中取 top s=10 最相似项
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ 5. Update LLM 决策    │  Tool Call：ADD / UPDATE / DELETE / NOOP
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ 6. 持久化              │
│    ─ 向量库：写入/修改/删除原子事实 │
│    ─ 图库（Mem0g）：更新实体与关系  │
│    ─ 历史表：记录变更审计              │
└──────────────────────┘
```

---

## 四、检索流程

### 4.1 基础语义检索

```
memory.search("what does the user prefer for Python formatting?")
        │
        ▼
┌──────────────────────┐
│ 1. Query 向量化        │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ 2. 向量库相似度查询     │  基于 user_id / agent_id / run_id 过滤
│    （Qdrant / Chroma…）│  返回 top-K 候选
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ 3. （可选）Reranker    │  Cross-Encoder 重排
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ 4. （可选）Graph 扩展  │  并行查询图库，补充 relations 字段
└──────────┬───────────┘
           │
           ▼
   {"results": [...], "relations": [...]}
```

**重要行为**：当启用 Graph Memory 时，图库查询与向量查询是**并行**执行的；图库返回的关联实体只会追加到 `relations` 数组里作为上下文丰富化，**不会重新排序**向量召回结果。最终排序仍由向量相似度（+ 可选 reranker）决定。

### 4.2 检索结果如何注入上游

Mem0 本身**不管**结果怎么塞进下游 Agent 的 Prompt —— 这是库用户的职责。典型模式是：

```python
results = memory.search(query=user_msg, user_id="alice", limit=5)
relevant_facts = "\n".join(f"- {m['memory']}" for m in results["results"])

system_prompt = f"""You are Alice's assistant.
Known facts about Alice:
{relevant_facts}
"""
```

这与 OpenClaw 把记忆当作文件注入 system prompt 的做法形成鲜明对比：Mem0 更像一个**外置 RAG 服务**，而不是 Agent 内部的状态。

---

## 五、存储后端

### 5.1 双轨存储架构

```
┌──────────────────────────────────────────────┐
│              memory.add(...)                 │
└────────────────────┬─────────────────────────┘
                     │
         ┌───────────┴───────────┐
         ▼                       ▼
  ┌─────────────┐         ┌─────────────┐
  │ Vector Store │         │ Graph Store │
  │ （主脑）      │         │（可选，平行） │
  │              │         │              │
  │ 存储：        │         │ 存储：        │
  │ ─ 原子事实文本 │         │ ─ 实体节点    │
  │ ─ Embedding   │         │ ─ 关系边      │
  │ ─ 元数据      │         │ ─ 语义类型标签 │
  └─────────────┘         └─────────────┘
```

**设计要点**：向量库是"主脑"，持有富文本；图库是一个**完全独立并行**的系统，只保存薄三元组（`entity → relation_type → entity`）。两者之间没有事务一致性保证 —— 这也是 GitHub issue mem0ai/mem0#3245 报告"删除记忆不会清理 Neo4j 图数据"的根源。

### 5.2 支持的向量存储

| 存储 | 特点 |
|------|------|
| **Qdrant** | 默认推荐，开源高性能 |
| **Chroma** | 轻量，本地优先 |
| **Pinecone** | 托管服务 |
| **FAISS** | 纯内存/本地文件 |
| **Weaviate / Milvus / pgvector** | 其他受支持选项 |

### 5.3 支持的图存储（Mem0g）

| 存储 | 说明 |
|------|------|
| **Neo4j** | 最成熟，Bolt 协议 |
| **Memgraph** | Neo4j 兼容，内存优先 |
| **Amazon Neptune** | AWS 托管 |
| **Kuzu** | 嵌入式图数据库 |
| **Apache AGE** | PostgreSQL 扩展 |

### 5.4 可插拔的 LLM 与 Embedding

Mem0 的 Extraction / Update 阶段都需要调用 LLM，同样是可插拔的：

| 组件 | 支持的提供者 |
|------|-------------|
| **LLM** | OpenAI, Anthropic, Gemini, Groq, Together, Ollama, LM Studio, Azure OpenAI, AWS Bedrock, … |
| **Embedding** | OpenAI, Gemini, HuggingFace, Ollama, VoyageAI, Azure OpenAI, … |

---

## 六、Mem0g：图增强变体

论文中把带图存储的版本单独命名为 **Mem0g**，其形式化定义是：

```
G = (V, E, L)

V  ── 实体节点（人、地点、概念…）
E  ── 关系边
L  ── 语义类型标签函数
```

### 6.1 构建流程

```
┌──────────────────────────────────┐
│ Phase 1: Entity Extraction        │
│ ── 从消息中识别关键实体              │
│    ("Alice", "Python", "Berlin") │
└──────────────┬───────────────────┘
               │
               ▼
┌──────────────────────────────────┐
│ Phase 2: Relationship Generation │
│ ── 推导实体之间的语义关系            │
│    (Alice)-[PREFERS]->(Python)   │
│    (Alice)-[LIVES_IN]->(Berlin)  │
└──────────────┬───────────────────┘
               │
               ▼
┌──────────────────────────────────┐
│ Phase 3: Conflict Resolution      │
│ ── 与图中已有子图对比                │
│ ── 检测矛盾/重复，触发更新           │
│    (Alice)-[LIVES_IN]->(Munich)  │
│       ↑ 将旧边 Berlin 标记为过时      │
└──────────────────────────────────┘
```

### 6.2 双路召回

Mem0g 的检索结合两种方式：

1. **Entity-Centric Exploration**：从查询中抽取实体，在图上做 BFS/DFS 获取 k-hop 邻居
2. **Semantic Triplet Matching**：将查询编码后与图中三元组的 embedding 做相似度匹配

两路结果合并后再与向量检索结果一起返回给调用方。

---

## 七、API 使用示例

### 7.1 最小可用例

```python
from mem0 import Memory

m = Memory()

# 写入：一次调用走完整两阶段流水线
m.add(
    messages=[
        {"role": "user", "content": "I'm a senior Go engineer, been using Go for 10 years"},
        {"role": "assistant", "content": "Got it! I'll tailor my answers for experienced Go developers."},
    ],
    user_id="alice",
)

# 检索：向量相似度召回
results = m.search(query="What's alice's background?", user_id="alice", limit=3)
for r in results["results"]:
    print(r["memory"], r["score"])
```

### 7.2 启用 Graph Memory

```python
from mem0 import Memory

config = {
    "vector_store": {
        "provider": "qdrant",
        "config": {"host": "localhost", "port": 6333, "collection_name": "mem0"},
    },
    "graph_store": {
        "provider": "neo4j",
        "config": {
            "url": "bolt://localhost:7687",
            "username": "neo4j",
            "password": "password",
        },
    },
    "llm": {
        "provider": "openai",
        "config": {"model": "gpt-4o-mini", "temperature": 0.0},
    },
    "embedder": {
        "provider": "openai",
        "config": {"model": "text-embedding-3-small"},
    },
}

m = Memory.from_config(config)
```

### 7.3 多作用域隔离

```python
# 用户级长期记忆（跨会话）
m.add(messages=[...], user_id="alice")

# 单次任务的短期状态
m.add(messages=[...], user_id="alice", run_id="task-2026-04-14-001")

# 只检索长期记忆：run_id 隐式为 NULL
long_term = m.search("preferences", user_id="alice")

# 只检索本次任务的状态
session_state = m.search("progress", user_id="alice", run_id="task-2026-04-14-001")
```

### 7.4 指定记忆类型

```python
# 创建过程性记忆（"如何做某件事"）
m.add(
    messages=[{"role": "user", "content": "To deploy, run `make deploy` then check Grafana"}],
    user_id="alice",
    memory_type="procedural_memory",
)
```

---

## 八、性能表现

Mem0 团队在 **LOCOMO** 基准（长上下文多轮对话问答）上做了系统评测：

### 8.1 准确度（J Score, 越高越好）

| 问题类型 | Mem0 | Mem0g |
|---------|------|-------|
| Single-Hop | **67.13** | 65.71 |
| Multi-Hop | **51.15** | 47.19 |
| Open-Domain | 72.93 | **75.71** |
| Temporal | 55.51 | **58.13** |

**观察**：Mem0g 在需要关系推理的 Open-Domain 和 Temporal 问题上优于纯向量方案；而对于直接事实查找（Single-Hop / Multi-Hop），向量检索的 Mem0 反而更准 —— 与图扩展带来的召回噪声有关。

### 8.2 部署指标

| 指标 | Mem0 | Full-Context 基线 | 相对收益 |
|------|------|------------------|---------|
| p95 延迟 | **1.44 s** | ~15 s | -91% |
| 每轮 token 消耗 | **~7k** | ~26k | -73% |
| 跨会话准确度 | +26% | 基线 | +26% |

这些数字是 Mem0 相对于"把整个对话历史塞进 LLM"这一朴素方案的核心卖点。

---

## 九、与 OpenClaw 记忆系统的对比

| 维度 | OpenClaw | Mem0 |
|------|----------|------|
| **定位** | Agent 内建记忆系统 | 外置 RAG 服务层 |
| **存储介质** | 纯 Markdown 文件 + SQLite 索引 | 向量库（+ 可选图库） |
| **可读性** | 人类可直接阅读/编辑/Git 管理 | 结构化记录，需 API 访问 |
| **写入触发** | 模型主动 tool call | 每次 `add()` 自动走提取+更新流水线 |
| **冲突处理** | Dreaming 后台扫描周期性整理 | 每次写入时同步 LLM 决策 |
| **检索方式** | 70/30 向量 + BM25 加权融合 | 向量检索（+ 可选 reranker + 图扩展） |
| **压缩机制** | Silent Turn + Compaction | Rolling Summary 喂给提取器 |
| **隔离粒度** | 按工作空间目录 | 按 user/agent/app/run_id 四维标签 |
| **部署复杂度** | 零依赖，本地即可 | 需向量库（可能还需图库 + LLM API） |

一句话概括：**OpenClaw 是"把记忆写进文件让模型读"，Mem0 是"把记忆变成原子事实让模型检索"**。

---

## 十、架构特点总结

| 特性 | 实现方式 |
|------|---------|
| 两阶段流水线 | Extraction → Update，每次 add 都同步运行 |
| 冲突消解 | LLM Tool Call 决定 ADD/UPDATE/DELETE/NOOP |
| 滚动摘要 | 长对话通过 rolling summary 压缩后喂给提取器 |
| 双轨存储 | 向量库持有富文本，图库持有薄三元组，二者并行 |
| 多作用域隔离 | user_id / agent_id / app_id / run_id 四维标签 |
| 可插拔后端 | 向量/图/LLM/Embedding 提供者全部可替换 |
| 低 token 消耗 | 每轮只注入检索到的原子事实，约 7k token |
| 图增强 | Mem0g 在开放域和时序问题上准确度更高 |

---

## 参考资料

1. [Mem0 GitHub 仓库](https://github.com/mem0ai/mem0)
2. [Mem0 官方文档](https://docs.mem0.ai)
3. [Mem0 Graph Memory 文档](https://docs.mem0.ai/open-source/features/graph-memory)
4. [Mem0 Entity-Scoped Memory 文档](https://docs.mem0.ai/platform/features/entity-scoped-memory)
5. [论文：Mem0: Building Production-Ready AI Agents with Scalable Long-Term Memory](https://arxiv.org/html/2504.19413v1)
6. [DeepWiki 代码分析](https://deepwiki.com/mem0ai/mem0)
7. [Dwarves Memo: Mem0 & Mem0-Graph Breakdown](https://memo.d.foundation/breakdown/mem0)
8. [MarkTechPost: Scalable Memory Architecture for Long-Term AI Conversations](https://www.marktechpost.com/2025/04/30/mem0-a-scalable-memory-architecture-enabling-persistent-structured-recall-for-long-term-ai-conversations-across-sessions/)
9. [Qdrant × Mem0 集成文档](https://qdrant.tech/documentation/frameworks/mem0/)
10. [Mem0 Research Page: 26% Accuracy Boost](https://mem0.ai/research)

---

**文档版本**: v1.0
**最后更新**: 2026-04-14
**作者**: Context Distiller Team
