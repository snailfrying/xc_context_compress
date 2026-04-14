# OpenClaw 记忆系统深度解析

> **定位**：详细介绍 OpenClaw 的记忆架构、数据流程、存储机制与使用方法
> **GitHub**：https://github.com/openclaw/openclaw （⭐ ~346K，截至 2026 年 4 月）
> **官方文档**：https://docs.openclaw.ai/concepts/memory

---

## 一、核心设计哲学

OpenClaw 的记忆系统遵循一个根本原则：

> **"If it's not written to a file, it doesn't exist."**
> 如果没有写入文件，就不存在。

所有记忆都是**纯 Markdown 文件**，存储在本地磁盘上。模型只"记住"被显式保存到文件中的内容——没有隐藏状态，没有黑盒数据库。这种设计带来三个关键优势：

| 优势 | 说明 |
|------|------|
| **人类可读** | 所有记忆都是 Markdown，用户可以直接阅读、编辑、审计 |
| **Git 可控** | 记忆文件可以纳入版本控制，追踪变更历史 |
| **完全透明** | 没有隐藏的向量数据库或不可见的内部状态 |

---

## 二、记忆文件体系

### 2.1 三大核心记忆文件

| 文件 | 用途 | 自动加载行为 |
|------|------|-------------|
| **`MEMORY.md`** | 长期记忆：持久化的事实、偏好、决策、约定 | 每次私聊会话启动时加载；群组上下文中不加载（隐私保护） |
| **`memory/YYYY-MM-DD.md`** | 每日笔记：当天的运行上下文、观察、活跃任务 | 今天 + 昨天的文件在会话启动时自动加载 |
| **`DREAMS.md`** | 实验性梦境日记：Dreaming 扫描的摘要，供人类审阅 | 由后台 Dreaming 子代理写入 |

### 2.2 引导文件（Bootstrap Files）

除记忆文件外，OpenClaw 在每次会话启动时还会从 `~/.openclaw/workspace` 加载以下引导文件：

```
~/.openclaw/workspace/
├── SOUL.md          # Agent 人格、沟通风格、伦理边界
├── AGENTS.md        # 操作规则、决策框架、工具约定
├── USER.md          # 用户项目、优先级、沟通偏好
├── TOOLS.md         # 工具定义和使用模式
├── IDENTITY.md      # 身份定义（可选）
├── HEARTBEAT.md     # 心跳配置（可选）
└── BOOTSTRAP.md     # 自定义引导内容（可选）
```

**限制**：单文件上限 20,000 字符，所有引导文件合计上限 150,000 字符。

### 2.3 会话转录（Session Transcripts）

- **位置**：`sessions/YYYY-MM-DD-<slug>.md`
- 带时间戳的对话转录，文件名由 LLM 生成描述性 slug
- 当 `experimental.sessionMemory: true` 时可被索引和搜索
- 使用增量 delta 索引 + 防抖后台同步

---

## 三、四层记忆模型

OpenClaw 的记忆系统分为四个层次，从持久到临时：

```
┌─────────────────────────────────────────────────┐
│  Layer 1: Bootstrap Files（引导文件）              │
│  ── 永久层：每轮对话从磁盘重新加载                   │
├─────────────────────────────────────────────────┤
│  Layer 2: Session Transcript（会话转录）           │
│  ── 半永久层：受 Compaction 压缩影响               │
├─────────────────────────────────────────────────┤
│  Layer 3: LLM Context Window（上下文窗口）         │
│  ── 临时层：固定 ~200K token 容器                  │
├─────────────────────────────────────────────────┤
│  Layer 4: Retrieval Index（检索索引）              │
│  ── 永久层：通过 memory_search 可搜索              │
└─────────────────────────────────────────────────┘
```

---

## 四、完整数据流

### 4.1 消息处理 → 记忆存储

```
用户发送消息
    │
    ▼
┌──────────────────────┐
│ 1. 加载 Bootstrap     │  从磁盘读取 MEMORY.md、每日笔记、
│    Files              │  SOUL.md、AGENTS.md 等
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ 2. 构建 System        │  Bootstrap 内容 + 工具定义 +
│    Prompt             │  检索到的记忆 → 组装系统提示词
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ 3. LLM 处理消息       │  模型基于完整上下文生成回复
│                       │  可能调用 memory 工具
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ 4. 记忆工具调用        │  模型主动决定是否需要：
│   （由模型触发）        │  - 写入 MEMORY.md（长期事实）
│                       │  - 写入每日笔记（当天上下文）
│                       │  - 搜索已有记忆
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ 5. 写入 Markdown      │  纯文本追加/更新到对应 .md 文件
│    文件               │  同时触发索引更新
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ 6. 索引同步           │  后台异步：
│   （后台异步）         │  - 文本分块（~400 token，80 token 重叠）
│                       │  - 生成 Embedding 向量
│                       │  - 写入 SQLite FTS5 索引
│                       │  - SHA-256 去重（相同内容不重复嵌入）
└──────────────────────┘
```

### 4.2 记忆检索流程

```
memory_search("用户的 API 偏好")
    │
    ▼
┌──────────────────────┐
│ 1. 查询向量化          │  将查询文本通过 Embedding 模型
│                       │  转换为高维向量
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ 2. 双路检索            │
│  ┌─────────────────┐  │
│  │ 向量检索 (70%)   │  │  余弦相似度匹配语义相近的记忆
│  └─────────────────┘  │
│  ┌─────────────────┐  │
│  │ FTS5 检索 (30%) │  │  BM25 关键词精确匹配
│  └─────────────────┘  │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ 3. 加权融合            │  score = 0.7 × vector_sim
│                       │        + 0.3 × keyword_score
│                       │  （非 RRF，避免量级扁平化问题）
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ 4. 排序 & 返回         │  按融合分数降序排列
│                       │  返回 Top-K 结果 + 来源文件路径
└──────────────────────┘
```

**为什么用加权融合而非 RRF（Reciprocal Rank Fusion）？**

RRF 只使用排名位置，丢弃了实际相似度分数信息。OpenClaw 的加权融合保留了分数的量级差异——一个 0.95 相似度的结果和一个 0.51 的结果在 RRF 中可能只差一个排名位，但在加权融合中差距会被保留。

### 4.3 Compaction（上下文压缩）流程

当对话接近上下文窗口限制时，OpenClaw 执行 Compaction：

```
上下文接近 200K token 限制
    │
    ▼
┌──────────────────────────────────┐
│ Phase 1: Silent Turn（静默轮次）    │
│                                   │
│ 系统注入一个隐藏提示：               │
│ "你的上下文即将被压缩。              │
│  请立即将所有重要的、尚未保存的       │
│  信息写入记忆文件。"                 │
│                                   │
│ → 模型自动调用记忆工具保存关键信息    │
└──────────────┬───────────────────┘
               │
               ▼
┌──────────────────────────────────┐
│ Phase 2: Summarization（摘要生成）  │
│                                   │
│ LLM 将长对话历史压缩为简洁摘要       │
│ 保留关键决策、结论、未完成任务        │
└──────────────┬───────────────────┘
               │
               ▼
┌──────────────────────────────────┐
│ Phase 3: Context Rebuild（上下文重建）│
│                                   │
│ 新上下文 = Bootstrap Files          │
│           + 压缩后的摘要             │
│           + 最近几轮对话              │
│                                   │
│ 释放出的空间用于继续对话              │
└──────────────────────────────────┘
```

**Silent Turn 的关键意义**：这是 OpenClaw 的核心创新之一。在压缩发生之前，给模型一个"最后机会"来保存重要信息，防止关键上下文在压缩中丢失。

---

## 五、存储与索引机制

### 5.1 SQLite + FTS5 全文检索

OpenClaw 使用 SQLite 作为本地索引数据库，利用 FTS5 扩展实现全文检索：

```sql
-- 记忆块表
CREATE TABLE memory_chunks (
    id          INTEGER PRIMARY KEY,
    source      TEXT NOT NULL,        -- 来源文件路径
    content     TEXT NOT NULL,        -- 文本内容（~400 token 块）
    embedding   BLOB,                 -- 向量嵌入（二进制存储）
    hash        TEXT UNIQUE,          -- SHA-256 内容哈希（去重用）
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- FTS5 全文索引
CREATE VIRTUAL TABLE memory_fts USING fts5(
    content,
    source,
    content=memory_chunks,
    content_rowid=id
);
```

### 5.2 Embedding 向量生成

OpenClaw 支持多种 Embedding 提供者，按优先级自动降级：

```
优先级链：本地模型 → OpenAI → Gemini → 纯 BM25（无向量）
```

| 提供者 | 模型 | 维度 | 说明 |
|--------|------|------|------|
| 本地 | 取决于配置 | 可变 | 无需网络，最快 |
| OpenAI | text-embedding-3-small | 1536 | 质量好，需 API Key |
| Gemini | embedding-001 | 768 | Google 提供 |
| 降级模式 | 无 | — | 仅使用 BM25 关键词检索 |

### 5.3 SHA-256 缓存去重

```
文件内容变更
    │
    ▼
计算 SHA-256(chunk_content)
    │
    ├── 哈希已存在 → 跳过嵌入，复用缓存
    │
    └── 哈希不存在 → 生成 Embedding → 存入索引
```

同一内容永远不会被嵌入两次，即使跨文件出现。

### 5.4 文本分块策略

```
原始 Markdown 文件
    │
    ▼
按 ~400 token 分块，80 token 重叠
    │
    ▼
每个块独立嵌入和索引
```

- **块大小 ~400 token**：平衡检索精度和上下文完整性
- **重叠 80 token**：防止关键信息被切断在块边界

---

## 六、Dreaming 系统（实验性）

OpenClaw 借鉴生物学睡眠机制，实现了三阶段"做梦"系统：

### 6.1 三阶段架构

```
┌─────────────────────────────────────────┐
│  Phase 1: Light Sleep（浅睡眠）           │
│                                          │
│  扫描所有每日笔记和会话转录                 │
│  识别候选记忆条目                          │
│  初步评分：相关性 × 新颖性                  │
└──────────────────┬──────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────┐
│  Phase 2: REM Sleep（快速眼动睡眠）        │
│                                          │
│  对候选记忆进行深度评估                     │
│  交叉引用已有 MEMORY.md 内容               │
│  检测冲突、重复、过时信息                    │
│  加权评分：重要性 × 持久性 × 独特性          │
└──────────────────┬──────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────┐
│  Phase 3: Deep Sleep（深度睡眠）           │
│                                          │
│  超过阈值的候选记忆 → 提升到 MEMORY.md      │
│  过时的记忆 → 标记或移除                    │
│  生成 DREAMS.md 摘要供人类审阅              │
└─────────────────────────────────────────┘
```

### 6.2 评分机制

每个候选记忆的最终得分：

```
final_score = w₁ × importance + w₂ × persistence + w₃ × uniqueness
```

只有超过预设阈值的记忆才会被"提升"（promote）到长期记忆 `MEMORY.md`。

---

## 七、记忆工具 API

### 7.1 内置记忆工具

| 工具 | 功能 | 说明 |
|------|------|------|
| `memory_search` | 语义搜索记忆 | 混合检索（向量 + FTS5），即使措辞不同也能找到相关记忆 |
| `memory_get` | 读取特定记忆文件 | 支持指定文件路径和行范围 |
| 文件写入工具 | 创建/更新记忆 | 通过标准文件操作写入 MEMORY.md 或每日笔记 |

### 7.2 memory_search 使用示例

模型在对话中自动调用：

```
memory_search("用户对 Python 代码风格的偏好")
```

返回结果包含：
- 匹配的文本片段
- 来源文件路径
- 相关性分数
- 上下文窗口（前后文）

### 7.3 记忆写入模式

模型通过标准文件操作管理记忆：

```markdown
<!-- 写入 MEMORY.md 示例 -->
## 用户偏好
- 偏好 Python type hints
- 使用 Black 格式化器，行宽 88
- 测试框架：pytest，不使用 mock

## 项目约定
- API 路由使用 kebab-case
- 数据库迁移使用 Alembic
```

---

## 八、插件生态

OpenClaw 的记忆系统支持通过插件扩展：

| 插件 | GitHub | 特点 |
|------|--------|------|
| **Engram** | [joshuaswarren/openclaw-engram](https://github.com/joshuaswarren/openclaw-engram) | 本地优先，LLM 驱动提取，Markdown 存储，QMD 混合搜索 |
| **Supermemory** | [supermemoryai/openclaw-supermemory](https://github.com/supermemoryai/openclaw-supermemory) | 长期记忆和召回增强 |
| **Redis Agent Memory** | [redis-developer/openclaw-redis-agent-memory](https://github.com/redis-developer/openclaw-redis-agent-memory) | Redis 向量搜索，跨会话持久化 |
| **LanceDB Pro** | [CortexReach/memory-lancedb-pro](https://github.com/CortexReach/memory-lancedb-pro) | 混合检索（Vector + BM25），Cross-Encoder 重排序 |
| **Memory Architecture** | [coolmanns/openclaw-memory-architecture](https://github.com/coolmanns/openclaw-memory-architecture) | 12 层记忆架构，知识图谱（3K+ 事实），激活/衰减系统 |

---

## 九、安装与使用

### 9.1 安装

```bash
# 推荐方式（安装脚本）
curl -fsSL https://openclaw.ai/install.sh | bash

# 或通过 npm
npm install -g openclaw@latest
openclaw onboard --install-daemon

# 或通过 pnpm
pnpm add -g openclaw@latest
pnpm approve-builds -g
openclaw onboard --install-daemon
```

**系统要求**：Node.js 24（推荐）或 Node.js 22.14+

### 9.2 记忆配置

在 `~/.openclaw/workspace` 目录下创建记忆文件：

```bash
# 创建工作空间目录
mkdir -p ~/.openclaw/workspace/memory

# 创建长期记忆文件
touch ~/.openclaw/workspace/MEMORY.md

# 创建今日笔记
touch ~/.openclaw/workspace/memory/$(date +%Y-%m-%d).md
```

### 9.3 记忆搜索配置

```json
// ~/.openclaw/settings.json
{
  "memory": {
    "search": {
      "enabled": true,
      "vectorWeight": 0.7,
      "keywordWeight": 0.3,
      "topK": 10
    }
  },
  "experimental": {
    "sessionMemory": true,
    "dreaming": true
  }
}
```

### 9.4 MEMORY.md 编写最佳实践

```markdown
# 长期记忆

## 用户信息
- 角色：高级后端工程师，10 年 Go 经验
- 当前项目：电商平台微服务重构
- 偏好：简洁代码，不喜欢过度抽象

## 技术约定
- Go 项目使用 standard layout
- API 设计遵循 RESTful 规范
- 错误处理使用 pkg/errors 包装

## 重要决策
- 2026-03-15：决定从 gRPC 迁移到 Connect-Go
- 2026-03-20：选择 PostgreSQL 替代 MongoDB 作为主数据库
```

---

## 十、架构特点总结

| 特性 | 实现方式 |
|------|---------|
| 文件优先 | 纯 Markdown，人类可读，Git 可控 |
| 混合检索 | 70/30 向量/关键词加权融合 |
| 预压缩保存 | Silent Turn 机制防止信息丢失 |
| 三阶段做梦 | Light/REM/Deep Sleep 仿生记忆整理 |
| 自动降级 | 本地 → OpenAI → Gemini → 纯 BM25 |
| 内容去重 | SHA-256 哈希，相同内容不重复嵌入 |
| 多代理隔离 | 每个 Agent 独立 SQLite 存储 |
| 插件扩展 | Engram、Supermemory、Redis、LanceDB 等 |

---

## 参考资料

1. OpenClaw GitHub: https://github.com/openclaw/openclaw
2. OpenClaw Memory 文档: https://docs.openclaw.ai/concepts/memory
3. OpenClaw Dreaming 文档: https://docs.openclaw.ai/concepts/dreaming
4. OpenClaw 记忆系统深度分析: https://snowan.gitbook.io/study-notes/ai-blogs/openclaw-memory-system-deep-dive
5. OpenClaw 记忆大师课: https://velvetshark.com/openclaw-memory-masterclass
6. SQLite RAG 分析: https://www.pingcap.com/blog/local-first-rag-using-sqlite-ai-agent-memory-openclaw/
7. DeepWiki 代码分析: https://deepwiki.com/openclaw/openclaw/7.3-memory-search
8. LanceDB Pro 博客: https://www.lancedb.com/blog/openclaw-memory-from-zero-to-lancedb-pro
9. 架构概览: https://ppaolo.substack.com/p/openclaw-system-architecture-overview

---

**文档版本**: v1.0
**最后更新**: 2026-04-09
**作者**: Context Distiller Team
