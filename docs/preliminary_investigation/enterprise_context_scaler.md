# ContextScaler: 企业级全模态统一上下文预处理与压缩引擎架构设计

## 1. 架构总览与核心设计理念 (Executive Summary)

现有的许多大模型外围工具往往针对单一场景（如只做文档解析的 RAG），难以在复杂的企业级 AI 业务中做到**通用适配与高鲁棒性**。随着 Vision Language Models (VLMs) 和多模态大模型的普及，以及长周期 Agent 业务的爆发，对于图像、视音频的分辨率和时序 Token 压榨，以及连贯聊天记忆的管理成为了关键痛点。

针对“业务不一定是最顶尖，但数据类型极度繁杂，且要求高度连贯性”的现实情况，我们需要一个高度解耦、即插即用、且能自适应各类脏数据的统一数据流引擎。

我们将其命名为 **ContextScaler**。该引擎的**核心设计理念**是：

1. **统一数据抽象层 (Universal Representation)**：文本、表格、高分辨率图像、视频流或长音频，进入引擎后即刻被转化为统一的 `ContextChunk` 表征。
2. **渐进式宽容度与降级 (Progressive Tolerance)**：流水线绝不因为某个前置格式错误而崩溃。对脏数据有极强的宽容度。
3. **多模态与时序Token压榨 (Multimodal Token Squeezing)**：针对 VLM、Audio 和 Video 引入专业的 Token 缩减策略，将非结构化的冗余信息物理性压缩。
4. **Agent 记忆生命周期管理 (Agentic Memory Continuity)**：不仅仅处理单次请求的数据，更外挂对长时间、多轮次连贯聊天的线程级上下文调度机制。

---

## 2. 系统核心架构：自适应全模态管线 (Adaptive Multimodal Pipeline)

我们将系统解耦为四个核心子系统，加上专为 Agent 设计的外部记忆路由层：

### 2.1 零层：Agent 会话记忆路由库 (Layer 0: Agent Thread & Memory Router)

*“不只是单次请求，更是生命周期管理。”这是为连贯聊天场景设计的记忆调度层。*

对于连续聊天的 Agent，数据不是一次性塞入的，必须维护连续性：

- **短时缓冲 (Conversation Buffer & Sliding Window)**: 维持最近 N 轮对话的高精度原文，确保当下语境绝不丢失。
- **动态截断与滚动摘要 (Rolling Summary)**: 当缓存池达到预警线（如 2K Token），后端异步触发摘要模型，将最旧的 M 轮对话凝练为几十个字的情境摘要（Summary Memory），并永久驻留在 System Prompt 之前。
- **实体与插曲记忆 (Entity & Episodic Memory)**: 使用向量数据库（Vector DB）记录用户提及的长期偏好（如“我喜欢深色模式”）、工具调用的长返回结果（如巨大的 API JSON）。在下一次对话时，仅靠语义检索抽出必要的 Chunk，而非全部保留在上下文。
- **上下文隔离 (Context Isolation)**: Agent 在调用外部工具（Tool Use）时产生的中间思考（Reasoning steps）和观察（Observations），在任务完成后立即被“折叠”或剔除，保持主线的清爽。

### 2.2 第一层：全模态摄入与预对齐层 (Layer 1: Multimodal Ingestion & Alignment)

*“不挑食”的多模态入口，将一切格式转换为标准化基石。*

- **文本与结构化网关 (Text & Structural)**
  - 解析纯文本、Markdown、文档(PDF/Word)。对 JSON/XML 等展平树状结构，提取键值。
- **高分辨率图像网关 (Vision/Image Modality)**
  - **原生分辨率适配与分块 (NativeRes / Sub-image partitioning)**: 针对需要看清细节的图（如报表）。将 4K 大图切分为多个低分辨率的子区块（Crops），加上一张全局缩略图。
  - **视觉 Token 物理池化 (Spatial Pooling)**: 如果业务仅需判断“图里有几个人”，在送入 VLM 之前，在模型早期层触发平均池化合并相邻视觉 Token（降维 70%）。
- **视音频网序网关 (Audio/Video Temporal Modality)**
  - **视频时序压榨 (Temporal Token Reduction / STORM)**: 视频就是高频的图片流。使用时序采样机制（如每秒抽 1 帧），并利用时序均值池化（Temporal Pooling）消除相邻帧的冗余 Token。
  - **音频神经编码转录 (Audio Codec & Whisper)**: 将长音频通过轻量级 Whisper 转成带精确时间戳的文本，或经由 HuBERT 等声学编码器（Vocoder）离散化为极低比特率的 Audio Tokens。

> **统一输出标准 (Standardized Artifact)**: 本层所有输出都被包裹为一个统一的 `ContextChunk` 对象，附带 Metadata（模态标签、时间戳、空间坐标、分块来源）。

### 2.3 第二层：健壮的安全清洗与正则基带 (Layer 2: Robust Regex & Security Baseband)

*针对文本化后的产物，用最低的算力解决最脏的数据。*

- **降噪核心 (Boilerplate Eraser)**: 自适应消除 HTML 标签、Base64 干扰、去除极长且重复的控制台日志。
- **合规与脱敏 (PII Sanitization)**: 自动用占位符 (如 `<EMAIL>`, `<CREDIT_CARD>`) 替换敏感信息，这是企业级生命线。纯正则无依赖，含看门狗机制防止正则回溯超时。

### 2.4 第三层：基于传统规则的特征提取 (Layer 3: NLP & Statistical Subsampling)

*用传统特征工程，为 LLM 减负降本。*

- **业务字典替换 (Lexicon Mapping)**: 将超长特定业务短语，替换为唯一缩写（如“中国人民代表大会” -> “人大”），全局生效，大幅度省 Token。
- **停用词与虚词剔除 (Stopword Pruning)**: 针对 RAG 检索回来的巨大块，踢掉“的/地/得”或无效连接词，退化为硬核的“电报体”（LLM 完全有能力理解）。
- **统计过滤 (Statistical Sieve)**: 大批量文档输入时，使用端侧 BM25 算法计算各个 Chunk 与用户当前 Query 的相关度，果断舍弃底层相关性（< 30%）的内容。

### 2.5 第四层：自适应智能语义预算压缩 (Layer 4: Adaptive Semantic Compression)

*兜底策略，只有当数据依然超载上限时启动，解决终极的 TTFT 难题。*

- **困惑度评估模型 (Perplexity Scorer, e.g., LLMLingua-2)**: 加载极轻量级模型。找出并剔除文本中极易被预测的词汇（困惑度极低），保留高信息熵词汇。
- **VLM 视觉注意力裁剪 (FlexAttention / Visual Pruning)**: （对于图像）基于用户问题（Query），通过一个轻型注意力机制评估哪些图像 Patch 对于回答该问题毫无用处（比如背景的天空），在最后一步将其剔除（LLM-VTP 策略）。
- **动态预算分配 (Dynamic Budgeting)**: 根据业务限定的 `max_ttft_ms`（首字延迟上限），动态计算当前需压缩的 Token 量，决定是否启动重度裁剪。

---

## 3. 企业级鲁棒性设计与自适应调度 (Robustness & Routing)

### 3.1 基于“容忍度”的错误降级树 (Failure Degradation Tree)

- **多媒体解析溃败**：当复杂格式视频无法抽取帧，流水线不会阻断：
  - \*\*Fallback 1\*\*: 仅尝试提取音频流转文本。
  - \*\*Fallback 2\*\*: 若全炸，提取文件 Metadata（时长、名称、格式）接进上下文，日志报 Warning，大模型依然能说出“这是一个无法解析的 X 分钟视频文件”。
- **L4智能模型内存熔断 (OOM)**：手机端加载 LLMLingua 失败时，立刻降级为 L3 级的 BM25 强截断，并在结尾增加 `...[System Notice: Context truncated]`，确保流程走通。

### 3.2 业务场景预设环境 (Standardized Scene Targeting)

针对单次请求与连续会话的差异，引擎内置一键化通用预设：

```python
# 初始化 ContextScaler (支持传入长期记忆管家)
scaler = ContextScaler(memory_manager=AgentRedisMemory())

# 场景 1：多模态 Agent 连续会话 (Agent Continuous Chat)
# 策略：开启短时 Buffer + 滚动摘要。跨模态工具产生的冗余数据在 L2+L3 进行强力收缩。
agent_context = scaler.process(
    query="帮我看看这个报表截图和这个录音说明了什么", 
    data=[image_path, audio_path], 
    profile="agent_continuity"
)

# 场景 2：离线单次复杂财报或长视频分析 (High-Fidelity Offline)
# 策略：视觉上开启全分块(Crops)无损保留，视频抽帧不合并，开启极大深度的困惑度压缩。准确率优先。
accurate_context = scaler.process(query, raw_data, profile="high_fidelity")

# 场景 3：端侧设备极限低迟模式 (Edge Speed First)
# 策略：视觉强力 Pooling (变极小图)，文本扔停用词变电报体，关闭消耗内存的 L4 模型压缩。
edge_context = scaler.process(query, raw_data, profile="edge_compute_speed")
```

---

## 4. 商业化交付与标准化接口规范 (Standardized Interfaces)

ContextScaler 作为一个“数据进，纯净 Token 出”的标准化黑盒，接口定义极其简洁统一。

**输入签命 (Input Signature):**

1. `session_id: str` (用于 Agent 对接 L0 的历史记忆，若是单次任务传 None)
2. `Query: str` (主驱动问题，压缩算法将以此为靶向)
3. `UnstructuredData: List[Any]` (支持混传：PDF路径、视频URL、PIL Image、乱码 JSON字符串)
4. `Constraints` (最大Token数上限，或最高容忍的毫秒时延)

**输出签命 (Output Signature):**

1. `Optimized_Prompt: list[dict]` (提供给大模型原生的统一格式，如 OpenAI format 或 LLaVA multi-modal format，已消除任何信息冗余)
2. `Token_Saving_Stats: dict` (记录本次剔除了%多少的冗余视音频Token、文本Token，为企业成本监控提供精确报表)

## 5. 总结

全新的 **ContextScaler 架构** 完全打破了传统“只能压文本”的束缚。通过引入 **L0 层的 Agent 记忆编排机制**，解决了对话连贯性；通过 **L1 和 L4 层的视音频特化 Token 均值池化与注意力裁剪**，解决了多模态吞噬显存的顽疾。

结合经典的数据流水线宽容度与重试机制，ContextScaler 成为了一个能适应无论是最前沿 Agent 体系，还是最下沉端侧芯片的通用级底座。只需配置标准化接口，即可实现 AI 业务数据管道的“标准化和工业化”降本增效。
