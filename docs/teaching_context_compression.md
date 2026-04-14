# 上下文压缩技术教程

> **主题 2：上下文压缩**
> 主讲人：伍梓樟 | 课程形式：线上 + 线下 | 课程时间：30–60 min × 2 节

---

## 目录

- [第一节 单节点上下文压缩](#第一节-单节点上下文压缩)
  - [1.1 为什么需要上下文压缩](#11-为什么需要上下文压缩)
  - [1.2 文本压缩：四档算法详解 (L0–L3)](#12-文本压缩四档算法详解-l0l3)
  - [1.3 文档压缩：从 PDF/Word 到精炼文本](#13-文档压缩从-pdfword-到精炼文本)
  - [1.4 图像压缩：像素模式 vs 语义模式](#14-图像压缩像素模式-vs-语义模式)
  - [1.5 使用 Context Distiller 进行单节点压缩](#15-使用-context-distiller-进行单节点压缩)
  - [1.6 参考资料](#16-参考资料)
- [第二节 会话压缩与长期记忆](#第二节-会话压缩与长期记忆)
  - [2.1 为什么需要会话级记忆管理](#21-为什么需要会话级记忆管理)
  - [2.2 三层会话压缩架构](#22-三层会话压缩架构)
  - [2.3 长期记忆：OpenClaw 本地方案](#23-长期记忆openclaw-本地方案)
  - [2.4 长期记忆：Mem0 云端方案](#24-长期记忆mem0-云端方案)
  - [2.5 OpenClaw vs Mem0 对比与选型](#25-openclaw-vs-mem0-对比与选型)
  - [2.6 业务组合方案：四种聊天模式](#26-业务组合方案四种聊天模式)
  - [2.7 使用 Context Distiller 进行记忆管理](#27-使用-context-distiller-进行记忆管理)
  - [2.8 参考资料](#28-参考资料)

---

# 第一节 单节点上下文压缩

> 核心问题：如何把**一段提示词、一个文件、一张图片**在送入 LLM 之前变"短"变"精"？

## 1.1 为什么需要上下文压缩

### 问题背景

| 痛点 | 说明 |
|------|------|
| **上下文窗口有限** | 主流模型窗口 4K–128K tokens，超长输入直接截断丢失关键信息 |
| **Token 费用高** | GPT-4 等按 token 计费，10 万字文档单次调用可能花费数十元 |
| **推理速度受限** | 输入越长，首 token 延迟（TTFT）越高，端侧 7B 模型尤为明显 |
| **注意力稀释** | *Lost in the Middle* 效应 —— LLM 对长上下文中间部分的关注度显著下降 |

### 压缩带来的好处

```
┌─────────────────┐     上下文压缩      ┌─────────────────┐
│  原始上下文       │  ──────────────→   │  精炼上下文       │
│  50,000 tokens   │   压缩率 40-60%    │  20,000 tokens   │
│  延迟 8s          │                    │  延迟 3s          │
│  费用 ¥5.0       │                    │  费用 ¥2.0       │
│  可能丢失中段信息  │                    │  关键信息保留      │
└─────────────────┘                     └─────────────────┘
```

- **降本**：减少 40%–80% 的 token 消耗
- **提速**：缩短推理延迟，提升用户体验
- **增效**：去除噪声后，LLM 回答精度反而提升（*less is more*）
- **兼容**：让长文档能"塞进"小窗口模型

### 名词解释

| 术语 | 含义 |
|------|------|
| **Token** | LLM 处理文本的最小单位。1 个中文字 ≈ 1.5–2 tokens，1 个英文词 ≈ 1–1.5 tokens |
| **上下文窗口 (Context Window)** | 模型单次能处理的最大 token 数量 |
| **压缩率 (Compression Ratio)** | `1 - 输出tokens / 输入tokens`，例如 0.6 = 压缩掉了 60% |
| **TTFT** | Time to First Token，首个 token 的响应延迟 |

---

## 1.2 文本压缩：四档算法详解 (L0–L3)

Context Distiller 提供从简单到复杂的四个压缩档位，对应四种不同的算法原理：

### 总览

| 档位 | Profile 名称 | 算法 | 压缩率 | 延迟 | 适用场景 |
|------|-------------|------|--------|------|---------|
| **L0** | `speed` | 正则清洗 + 停用词过滤 | 10–20% | < 1ms | 实时对话、低延迟要求 |
| **L1** | `selective` | GPT-2 自信息量过滤 | 30–40% | 50–200ms | 快速 + 保留核心语义 |
| **L2** | `balanced` | LLMLingua-2 (ONNX) | 40–50% | 100–500ms | **默认推荐**，平衡质量与速度 |
| **L3** | `accuracy` | LLM 摘要重写 | 60–80% | 2–10s | 高质量摘要、对延迟不敏感 |

---

### L0：正则清洗（规则方法）

**原理**：纯规则处理，不涉及任何模型。

```
输入文本 → 正则去除多余空白/特殊字符 → 移除英文停用词 → 输出
```

- **停用词 (Stop Words)**：对语义贡献极低的高频词（如 the, a, an, and, or, but...）
- 中文场景下效果有限，主要用于清理格式噪声
- **优势**：零依赖、零延迟、确定性输出

---

### L1：SelectiveContext（自信息量过滤）

**核心论文**：[*Selective Context*](https://arxiv.org/abs/2310.06201) (Li et al., 2023)

**原理**：用 GPT-2 小模型计算每个句子的"自信息量"，保留信息密度高的句子，丢弃低信息量内容。

```
                    GPT-2
输入文本 → 按句分割 ──→ 计算每句自信息量 → 按分数排序 → 保留 Top-K → 输出
```

**什么是自信息量 (Self-Information)？**

> 给定上下文，一个 token 出现的概率越**低**，它携带的信息量就越**高**。
>
> 公式：`I(token) = -log₂ P(token | context)`
>
> 直觉：**"今天天气"**后面跟**"很好"**概率高（低信息量），跟**"导致航班取消"**概率低（高信息量）。

- 句子级平均自信息 = 该句所有 token 自信息的均值
- 按降序排列，保留信息量最高的 `(1 - reduce_ratio)` 比例的句子
- **优势**：轻量（GPT-2 仅 124M 参数），保留原文关键语句不改写

---

### L2：LLMLingua-2（Token 级压缩）

**核心论文**：[*LLMLingua-2*](https://arxiv.org/abs/2403.12968) (Microsoft, 2024)

**原理**：使用专门训练的 XLM-RoBERTa 分类器，对每个 token 做二分类——"保留"还是"丢弃"。

```
输入文本 → XLM-RoBERTa (ONNX) → 每个 token 的保留概率 → 按 rate 阈值过滤 → 拼接保留 tokens → 输出
```

**关键技术点**：

| 要素 | 说明 |
|------|------|
| 训练数据 | 用 GPT-4 生成"压缩-原文"对，标注每个 token 是否应保留 |
| 模型 | XLM-RoBERTa-Large（多语言支持，中英文效果均好） |
| 推理方式 | 导出为 ONNX 格式 + INT8 量化，CPU 即可运行 |
| 粒度 | **Token 级别**，比 L1 的句子级更精细 |
| `rate` 参数 | 目标保留比例，如 `rate=0.4` 表示保留 40% 的 tokens |

- **优势**：Token 级精细控制，多语言支持，ONNX 推理速度快
- **限制**：单次最大处理约 512 tokens（≈1800 字符），超长文本需分块

---

### L3：LLM 摘要重写

**原理**：直接调用大语言模型（如 Qwen2.5-7B）理解原文语义，生成精炼摘要。

```
输入文本 → System Prompt（压缩指令） → LLM (Qwen2.5:7b via Ollama) → 摘要文本
```

**System Prompt 设计要点**：
- 保留所有关键事实、数字、人名、逻辑结构
- 使用与输入相同的语言
- 去除冗余和填充内容
- 温度设为 0.2（低随机性，保真度优先）

- **优势**：压缩率最高，语义理解最深，可跨段落整合信息
- **限制**：延迟最高（需完整推理），输出非确定性，可能引入幻觉

---

### 四档对比图示

```
精度 ↑                                    ★ L3 (LLM 摘要)
     │                           ★ L2 (LLMLingua-2)
     │                  ★ L1 (SelectiveContext)
     │        ★ L0 (正则)
     └────────────────────────────────→ 延迟
```

**选型建议**：
- 日常 Vibe Coding / Agent 对话 → **L2 (balanced)**
- 批量文档预处理、离线分析 → **L3 (accuracy)**
- 实时对话中间件、流式处理 → **L0 (speed)** 或 **L1 (selective)**

---

## 1.3 文档压缩：从 PDF/Word 到精炼文本

文档压缩是一个**两阶段流水线**：先提取文本，再逐块压缩。

### 第一阶段：文本提取

支持四种提取后端：

| 后端 | 擅长类型 | 原理 |
|------|---------|------|
| **MarkItDown** | Office 文档 (DOCX/XLSX/PPTX)、HTML | 微软开源工具，解析文档结构，输出 Markdown 格式 |
| **Docling** | 学术论文、复杂排版 PDF | IBM 开源，深度理解文档布局（表格、图注、公式） |
| **PyMuPDF** | 通用 PDF | 直接提取 PDF 内嵌文本层，速度快但不识别扫描件 |
| **DeepSeek-OCR** | 扫描件、手写体、截图 | 通过 VLM（视觉语言模型）对页面图像做 OCR 识别 |

### 第二阶段：智能分块 + 逐块压缩

```
原始文档
  ↓
文本提取（MarkItDown / Docling / PyMuPDF / DeepSeek-OCR）
  ↓
智能分块（按标题/段落边界切分，每块 ≤ 1200 字符，最小 200 字符）
  ↓
逐块压缩（使用当前 Profile 对应的文本压缩等级 L0–L3）
  ↓
输出：每块包含 { 标题, 原文, 压缩文本 }
```

**智能分块策略**：
- 优先在 Markdown 标题（`#`, `##`, `###`）处切分
- 其次在双换行（段落边界）处切分
- 超长段落做强制等分
- 保证每块有足够的上下文长度（≥ 200 字符）

---

## 1.4 图像压缩：像素模式 vs 语义模式

图像进入 LLM 时会消耗大量 token（一张 1024×1024 的图 ≈ 765 tokens）。两种处理思路：

### 像素模式 (Pixel Mode)

> 目标：在保留视觉信息的前提下减小图像体积

```
原始图像 → pHash 去重 → 自适应缩放（≤1024px）→ 输出优化后图像
```

| 技术 | 作用 |
|------|------|
| **pHash (感知哈希)** | 对图像做 8×8 灰度化 → 比较均值 → 生成指纹。近似图直接去重，避免重复上传 |
| **自适应缩放** | 按最长边缩放至 1024px 以内，减少 VLM 视觉 token 消耗 |

### 语义模式 (Semantic Mode)

> 目标：将图像转换为文本描述，彻底消除视觉 token

**方案 A：OCR 提取** → 用 DeepSeek-OCR 将截图/文档图转为纯文本
**方案 B：VLM 描述** → 用 Qwen2.5-VL 生成图像的自然语言描述
**方案 C：CLIP ROI 裁剪** → 只保留图像中与 query 相关的区域

**CLIP ROI 原理**（Region of Interest 抠图）：

```
原图 → 网格切分(4×4=16块) → CLIP 计算每块与 query 的相似度 → 保留高分区域 → 裁剪拼合
```

> **CLIP** (OpenAI, 2021)：对比学习训练的视觉-语言模型，能计算任意图像与文本的语义相似度。

---

## 1.5 使用 Context Distiller 进行单节点压缩

### Web UI 操作

1. 启动服务后访问前端页面
2. 进入 **Distill Tool** 标签页
3. 操作方式：
   - **Prompt text**：直接输入一段文本，选择 Profile（speed/selective/balanced/accuracy），点击 Distill
   - **Context items**：每行填一个文件路径 / URL / data URI，逐条独立压缩
   - **Document backend**：选择文档提取后端（MarkItDown / Docling / PyMuPDF / DeepSeek）
4. 结果面板展示：压缩前后文本、Token 统计、压缩率、延迟

### REST API 调用

通过 `POST /v1/distill` 接口：

- 请求参数：
  - `profile`：压缩档位（speed / selective / balanced / accuracy）
  - `data`：字符串数组，每项可以是文本 / 文件路径 / URL
  - `document_backend`：文档提取后端（可选）
- 返回：`optimized_prompt[]` 数组，每项包含 type、压缩文本、Token 统计

### Python SDK

通过 `DistillerClient` 类：

- `client = DistillerClient(profile="balanced")`
- `result = client.process(data=["文本...", "文件路径"])`
- `result.stats.compression_ratio` → 压缩率

---

## 1.6 参考资料

| 资源 | 链接 |
|------|------|
| LLMLingua-2 论文 | https://arxiv.org/abs/2403.12968 |
| SelectiveContext 论文 | https://arxiv.org/abs/2310.06201 |
| LLMLingua GitHub | https://github.com/microsoft/LLMLingua |
| Lost in the Middle 论文 | https://arxiv.org/abs/2307.03172 |
| MarkItDown (Microsoft) | https://github.com/microsoft/markitdown |
| Docling (IBM) | https://github.com/DS4SD/docling |
| CLIP (OpenAI) | https://arxiv.org/abs/2103.00020 |
| Ollama 官网 | https://ollama.com |

---

# 第二节 会话压缩与长期记忆

> 核心问题：对话越来越长怎么办？如何让 Agent **跨会话**记住用户的偏好和知识？

## 2.1 为什么需要会话级记忆管理

### 单节点压缩 vs 会话压缩

| 维度 | 单节点压缩（第一节） | 会话/记忆管理（第二节） |
|------|-------------------|---------------------|
| 输入 | 单个提示词 / 文件 / 图片 | 整段对话历史 + 跨会话知识 |
| 状态 | **无状态**，每次独立处理 | **有状态**，需要维护上下文演进 |
| 目标 | 缩短单次输入 | 管理对话生命周期 + 持久化知识 |

### Agent 记忆的三层抽象

```
┌─────────────────────────────────────────────────────┐
│  Working Memory（工作记忆）                           │
│  = 当前上下文窗口中的 messages 数组                    │
│  生命周期：本轮对话                                    │
├─────────────────────────────────────────────────────┤
│  Session Memory（会话记忆）                           │
│  = 对话历史的压缩版本                                  │
│  生命周期：单次会话（可持久化 transcript）               │
├─────────────────────────────────────────────────────┤
│  Long-term Memory（长期记忆）                         │
│  = 用户偏好、事实、规则等持久化知识                      │
│  生命周期：跨会话、跨 Agent，永久保留                   │
└─────────────────────────────────────────────────────┘
```

---

## 2.2 三层会话压缩架构

Context Distiller 的 **SessionCompactor** 实现了三层渐进式会话压缩：

### L1 Micro-Compact：工具结果占位

**问题**：Agent 调用工具（搜索、代码执行等）会产生大量 `tool_result` 消息，迅速膨胀上下文。

**方案**：将旧的工具返回结果替换为占位符，只保留最近 N 条（默认 3 条）。

```
Before:
  [user] 帮我查一下天气
  [tool_result] {"city":"上海","temp":"22°C","wind":"东南风3级","humidity":"65%",...} ← 保留
  [assistant] 上海今天 22°C...
  [user] 再查北京
  [tool_result] {"city":"北京","temp":"18°C","wind":"北风2级","humidity":"45%",...} ← 保留
  [user] 再查广州
  [tool_result] {"city":"广州","temp":"28°C",...}                                  ← 保留（最近3条）

After (当工具调用超过3次后):
  [user] 帮我查一下天气
  [tool_result] [Previous: used weather_tool]    ← 占位符，节省 token
  [assistant] 上海今天 22°C...
  ...后续保持不变
```

- **触发条件**：始终开启（每次对话前自动执行）
- **参数**：`keep_recent: 3`（保留最近 3 个工具结果）
- **效果**：对工具密集型对话（如 Vibe Coding）效果显著

---

### L2 Auto-Compact：阈值触发压缩

**问题**：对话持续进行，总 token 数接近或超过模型窗口限制。

**方案**：当总 token 超过阈值（默认 50,000），自动触发：
1. **保存 transcript**：将完整对话历史写入 `.transcripts/` 目录（JSONL 格式），防止信息丢失
2. **生成摘要**：对历史对话进行压缩摘要
3. **替换上下文**：用一条 system 消息替换全部历史

```
Token 估算 > 50,000?
  ├── 否 → 不做任何处理
  └── 是 →
       ├── 1. 保存完整历史到 .transcripts/{session_id}_{timestamp}.jsonl
       ├── 2. 用摘要策略生成精炼摘要
       └── 3. 替换为: [system] "Previous conversation summary: {摘要内容}"
```

### 摘要策略（三选一 + 自动降级链）

| 策略 | 说明 | 降级 |
|------|------|------|
| **lingua** | 复用第一节的文本压缩器（L0–L3），对对话文本做直接压缩 | 失败 → llm → fallback |
| **llm** | 调用 LLM 生成对话摘要（"总结关键决策、事实和待办"） | 失败 → lingua → fallback |
| **fallback** | 零依赖规则提取：只保留最后 10 条 user/assistant 消息 | 最终兜底 |

> 降级链确保了**任何环境下都能工作**，即使模型服务不可用。

---

### L3 Manual Compact（手动触发）

通过 API 或工具调用 `context_compact` 主动触发压缩，用于：
- Agent 主动决定"这段对话可以归档了"
- 用户手动清理对话上下文

---

### 会话压缩自动转存长期记忆

**亮点设计**：当 Auto-Compact 触发时，生成的摘要会自动存入长期记忆系统，分类为 `session_history`。

```
Auto-Compact 触发
  → 生成摘要
  → 写入 Long-term Memory (source: "summary:{session_id}", category: "session_history")
```

这意味着即使会话结束，核心信息也不会丢失——下次对话可以从长期记忆中召回。

---

## 2.3 长期记忆：OpenClaw 本地方案

**OpenClaw** 是 Context Distiller 内置的本地长期记忆后端，基于 SQLite 构建。

### 架构

```
┌──────────────────────────────────────────────┐
│  OpenClaw Backend                            │
│                                              │
│  ┌──────────┐  ┌──────────┐  ┌───────────┐  │
│  │ SQLite   │  │ FTS5     │  │ sqlite-vec│  │
│  │ 主表      │  │ 全文索引  │  │ 向量索引   │  │
│  └──────────┘  └──────────┘  └───────────┘  │
│       ↑              ↑              ↑        │
│       └──────────────┼──────────────┘        │
│                      ↓                       │
│            Hybrid Search（混合搜索）           │
│         向量 70% + 全文 30% 加权融合           │
└──────────────────────────────────────────────┘
```

### 核心概念

**多租户隔离**：

```
记忆 = (user_id, agent_id, category, content, source)
```

- `user_id`：自然人用户标识（如 "alice"）
- `agent_id`：Agent 实例标识（如 "code_assistant"、"analyzer"）
- 同一用户下不同 Agent 的记忆**互相独立**

**记忆分类 (Category)**：

| 分类 | 用途 | 示例 |
|------|------|------|
| `fact` | 客观事实 | "项目使用 Python 3.12" |
| `preference` | 用户偏好 | "用户偏好暗色主题" |
| `rule` | 业务规则 | "代码提交前必须跑 lint" |
| `profile` | 用户画像 | "高级后端工程师，Go 专家" |
| `note` | 备注信息 | "Q2 需要完成认证系统重构" |
| `system` | 系统生成 | Auto-Compact 生成的会话摘要 |

### 混合搜索算法

当 Agent 需要召回记忆时，执行两路并行搜索：

```
查询 "Python 版本要求"
  ├── 路径 A: FTS5 全文检索
  │   → 关键词匹配: "Python" AND "版本"
  │   → 返回 [(记忆ID, BM25分数), ...]
  │
  ├── 路径 B: 向量语义搜索
  │   → BGE-M3 生成查询向量 → cosine 相似度检索
  │   → 返回 [(记忆ID, 向量距离), ...]
  │
  └── 融合: score = 0.7 × 向量分 + 0.3 × FTS分
       → 排序取 Top-K 返回
```

**为什么用混合搜索？**

| 搜索方式 | 优势 | 劣势 |
|---------|------|------|
| 全文检索 (FTS) | 精确关键词匹配、零漏召 | 无法理解同义词和语义相关 |
| 向量搜索 | 语义理解（"Python" ≈ "编程语言"） | 关键词精确匹配可能丢失 |
| **混合搜索** | **两者互补** | 需要维护双索引 |

### 向量嵌入 (Embedding)

> **Embedding**：将文本映射为一个高维向量（如 384/1024 维浮点数组），语义相近的文本在向量空间中距离相近。

Context Distiller 使用 **BGE-M3**（BAAI 出品）作为 Embedding 模型：
- 多语言支持（中英文效果优秀）
- 通过 Ollama 服务调用，无需本地 GPU
- 输出 384 维向量，存储为 SQLite BLOB

---

## 2.4 长期记忆：Mem0 云端方案

**Mem0** 是一个开源的 AI 记忆层框架，提供了更丰富的存储和检索能力。

### Mem0 核心特性

| 特性 | 说明 |
|------|------|
| **自动提取** | 传入一段对话，Mem0 自动识别并提取出值得记忆的信息 |
| **智能去重** | 自动判断新记忆是否与已有记忆冲突，执行更新而非重复存储 |
| **图谱记忆** | 可选接入 Neo4j 图数据库，构建实体间的关系网络 |
| **多后端** | 向量库支持 Qdrant / Chroma / Pinecone 等，灵活部署 |

### Mem0 工作原理

```
用户对话: "我是做 Go 后端的，项目用 PostgreSQL"
           ↓
       Mem0.add()
           ↓
   ┌───────────────────────────────────┐
   │  1. LLM 提取结构化记忆              │
   │     → "用户擅长 Go 后端开发"         │
   │     → "项目数据库为 PostgreSQL"      │
   │                                    │
   │  2. 冲突检测（与已有记忆比对）         │
   │     → 发现已有 "用户擅长 Python"     │
   │     → 判断：更新（不是新增）           │
   │                                    │
   │  3. 向量化 + 存储                    │
   │     → Embedding → Vector DB         │
   └───────────────────────────────────┘
```

### 在 Context Distiller 中的集成

Context Distiller 将 Mem0 封装为可插拔后端，与 OpenClaw 使用**相同的接口**：

- `search(query, top_k, user_id, agent_id)` → 搜索记忆
- `store(content, category, user_id, agent_id)` → 存储记忆
- `update(chunk_id, content)` → 更新记忆
- `forget(chunk_id)` → 删除记忆

通过配置 `memory_backend: "mem0"` 一键切换，业务层代码无需修改。

---

## 2.5 OpenClaw vs Mem0 对比与选型

| 维度 | OpenClaw | Mem0 |
|------|----------|------|
| **部署** | 纯本地 SQLite，零外部依赖 | 需要 LLM + 向量数据库 |
| **隐私** | 数据完全本地，不出网 | 取决于部署方式（可自托管） |
| **智能度** | 手动存储，搜索基于 FTS + 向量 | **自动提取 + 智能去重 + 冲突检测** |
| **存储成本** | 几乎为零（SQLite 文件） | 需向量数据库资源 |
| **图谱能力** | 无 | 可选 Neo4j 图谱存储 |
| **适用场景** | 端侧部署、离线环境、对隐私敏感 | 云端部署、需要自动记忆管理 |
| **多租户** | (user_id, agent_id) 复合键 | (user_id, agent_id) 作用域 |

**选型建议**：

- **推荐 OpenClaw**：在公司内网部署、数据不能出网、需要精确控制记忆内容
- **推荐 Mem0**：需要自动化记忆提取能力、构建知识图谱、云端部署

---

## 2.6 业务组合方案：四种聊天模式

Context Distiller Web UI 提供四种聊天模式，对应不同的业务场景：

| 模式 | 长期记忆 | 会话压缩 | 自动存储 | 适用场景 |
|------|---------|---------|---------|---------|
| **Full Agent** | 开启 | 开启 | 开启 | 完整 Agent 体验，推荐日常使用 |
| **Memory Only** | 开启 | 关闭 | 开启 | 测试/调试长期记忆效果 |
| **Session Only** | 关闭 | 开启 | 关闭 | 测试/调试会话压缩效果 |
| **Plain** | 关闭 | 关闭 | 关闭 | 纯 LLM 对话，作为基线对比 |

### Full Agent 模式完整数据流

```
用户发送消息
  ↓
1. 记忆召回
   → 用用户消息作为 query，搜索长期记忆 (top_k=3)
   → 将命中的记忆注入 System Prompt
  ↓
2. 文件处理（如有附件）
   → 文档类：走 Prompt Distiller 压缩
   → 图像类：缩放编码为 Base64
  ↓
3. 会话压缩
   → L1: Micro-Compact (替换旧工具结果)
   → L2: Auto-Compact (超阈值触发摘要替换)
  ↓
4. LLM 推理
   → 将 [System + 压缩后历史 + 用户消息] 发送至 Ollama
   → 收到 Assistant 回复
  ↓
5. 响应返回
   → 附带指标：记忆命中数、是否触发 compact、估算 token 数
```

---

## 2.7 使用 Context Distiller 进行记忆管理

### Web UI 操作

**Agent Chat**：
1. 在顶部设置 `user_id` / `agent_id` / `session_id`（三层隔离作用域）
2. 选择聊天模式（Full / Memory Only / Session Only / Plain）
3. 对话过程中右侧标签自动展示：记忆召回条数、写入记忆条数、是否触发 compact

**Memory Explorer**：
1. 进入 Memory Explorer 标签页
2. 在当前 user_id / agent_id 作用域下：
   - **Search**：语义搜索记忆
   - **List**：浏览所有记忆（支持按 Category 过滤）
   - **Store**：手动添加记忆（选择 category）
   - **Update**：修改已有记忆内容
   - **Forget**：删除记忆

**Settings**：
- 切换记忆后端：`openclaw` ↔ `mem0`
- 调整会话压缩参数：策略、阈值、压缩档位
- 配置 Ollama 连接地址和模型

### REST API

| 端点 | 方法 | 用途 |
|------|------|------|
| `/v1/memory/search` | POST | 搜索记忆 |
| `/v1/memory/store` | POST | 存储新记忆 |
| `/v1/memory/update` | POST | 更新记忆 |
| `/v1/memory/forget` | POST | 删除记忆 |
| `/v1/memory/list` | POST | 列出所有记忆 |
| `/v1/chat` | POST | Agent 聊天（自动整合记忆） |
| `/v1/chat/reset` | POST | 重置会话 |
| `/v1/settings` | GET/PUT | 读取/修改运行时配置 |

---

## 2.8 参考资料

| 资源 | 链接 |
|------|------|
| Mem0 官方文档 | https://docs.mem0.ai |
| Mem0 GitHub | https://github.com/mem0ai/mem0 |
| BGE-M3 Embedding 模型 | https://huggingface.co/BAAI/bge-m3 |
| SQLite FTS5 文档 | https://www.sqlite.org/fts5.html |
| MemGPT / Letta 论文 (Agent 记忆架构) | https://arxiv.org/abs/2310.08560 |
| Cognitive Architecture for Language Agents | https://arxiv.org/abs/2309.02427 |
| BM25 算法介绍 | https://en.wikipedia.org/wiki/Okapi_BM25 |
| 向量数据库科普 | https://www.pinecone.io/learn/vector-database/ |

---

## 附录 A：Context Distiller 快速启动

```
1. 启动后端：python -m context_distiller.api.server.app   → http://localhost:8080
2. 启动前端：cd context_distiller_ui && npm run dev        → http://localhost:5173
3. 确保 Ollama 服务运行中（qwen2.5:7b + bge-m3 模型已拉取）
```

## 附录 B：关键术语速查表

| 术语 | 全称 | 一句话解释 |
|------|------|-----------|
| Token | — | LLM 处理文本的最小单位，约 0.7 个中文字 |
| Embedding | 嵌入向量 | 将文本映射为数字向量，语义相近则向量相近 |
| FTS | Full-Text Search | 全文检索，基于关键词倒排索引的搜索 |
| BM25 | Best Matching 25 | FTS 中最常用的相关性评分算法 |
| ONNX | Open Neural Network Exchange | 开放神经网络交换格式，支持跨框架高效推理 |
| VLM | Vision-Language Model | 视觉语言模型，同时理解图像和文本 |
| OCR | Optical Character Recognition | 光学字符识别，从图像中提取文字 |
| CLIP | Contrastive Language-Image Pre-training | OpenAI 的视觉-语言对比学习模型 |
| pHash | Perceptual Hash | 感知哈希，基于视觉内容生成图像指纹 |
| RAG | Retrieval-Augmented Generation | 检索增强生成，先检索再回答 |
| Ollama | — | 本地 LLM 推理框架，一键部署开源模型 |
| Transcript | — | 对话历史的完整文件备份 |

## 附录 C：系统架构总览

```
                    ┌──────────────────────────────────────┐
                    │           Web UI (React)              │
                    │  Distill Tool │ Agent Chat │ Memory   │
                    └─────────┬────────────────────────────┘
                              │ HTTP
                    ┌─────────▼────────────────────────────┐
                    │         FastAPI Server (:8080)        │
                    │  /v1/distill  /v1/chat  /v1/memory/* │
                    └──┬──────────────┬────────────────┬───┘
                       │              │                │
           ┌───────────▼──┐   ┌──────▼──────┐  ┌──────▼──────┐
           │ Prompt        │   │ Session      │  │ User Memory │
           │ Distiller     │   │ Compactor    │  │ Manager     │
           │               │   │              │  │             │
           │ L0 Regex      │   │ L1 Micro     │  │ ┌─────────┐│
           │ L1 Selective  │   │ L2 Auto      │  │ │OpenClaw ││
           │ L2 LLMLingua  │   │ L3 Manual    │  │ │(SQLite) ││
           │ L3 LLM摘要    │   │              │  │ ├─────────┤│
           │               │   │ lingua/llm/  │  │ │  Mem0   ││
           │ Doc Pipeline  │   │ fallback     │  │ │(可选)   ││
           │ Vision Pipeline│  │              │  │ └─────────┘│
           └───────┬───────┘   └──────┬───────┘  └──────┬─────┘
                   │                  │                  │
                   └──────────────────┼──────────────────┘
                                      │
                            ┌─────────▼─────────┐
                            │   Ollama Server    │
                            │  qwen2.5:7b        │
                            │  qwen2.5vl:7b      │
                            │  deepseek-ocr      │
                            │  bge-m3 (embed)    │
                            └────────────────────┘
```
