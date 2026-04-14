# Context Distiller v2.0: 全模态统一上下文预处理与记忆网关技术架构设计文档

## 1. 架构总览与核心设计理念

基于**“极端解耦与动态分发”**的理念，Context Distiller v2.0 从一个单纯的“文本/图像瘦身工具”，升级为**“大模型端侧输入预处理与记忆网关”**。

系统突破性地抽象出 **“事件(Event) -> 数据类型(DataType) -> 算法引擎(Algorithm) -> 硬件设备(Hardware)”** 的处理流水线。无论宿主机是仅含 CPU 的轻量级设备，还是具备 GPU/NPU 的高性能计算节点，系统都能根据当前配置与算力探针，动态路由到最优模型或传统算法链路，兼顾**极速 TTFT（首字延迟）**与**最佳语义保真度**。

---

## 2. 工程代码逻辑架构 (Directory & Module Structure)

为了保证“前后端解耦”与“即插即用”，项目需采用严谨的分层架构设计。以下是推荐的工程目录结构与核心模块划分：

```text
context_distiller/
├── api/                    # 【表现层】暴露服务接口
│   ├── server/             # REST API (FastAPI), 提供 100% 兼容 OpenAI/DeepSeek 协议的网关
│   └── cli/                # 命令行工具，支持大批量离线文件清洗与压缩
├── sdk/                    # 【表现层】提供给业务方的 Python Client SDK
│   └── client.py           # 封装底层调用，实现本地直调或远程路由
├── core/                   # 【路由与引擎层】系统的中枢大脑
│   ├── router.py           # DispatchRouter: 动态类型与硬件路由分发
│   ├── engine.py           # 核心流水线调度器 (Pipeline Orchestrator)
│   └── memory/             # 会话片段与记忆管理 (借鉴 OpenClaw)
│       ├── sliding_window.py
│       └── pre_compactor.py # Pre-compaction Flush 预压缩触发器
├── processors/             # 【算法实现层】各模态的具体压缩处理器 (横向解耦)
│   ├── base.py             # 抽象基类 BaseProcessor (定义 process 和 fallback 接口)
│   ├── text/
│   │   ├── cpu_tfidf.py    # 传统 NLP: TF-IDF / BM25 截断 (Zero VRAM)
│   │   ├── npu_llmlingua.py# NPU/ONNX: LLMLingua-2 语义熵压缩
│   │   └── gpu_llm_sum.py  # GPU: 大模型强力摘要构建
│   ├── vision/
│   │   ├── cpu_opencv.py   # 图片物理降维/抽帧池化
│   │   └── gpu_vlm_roi.py  # VLM 显著性抠图
│   └── document/
│       ├── cpu_native.py   # CPU 零模型: MarkItDown / PyMuPDF + python-docx (极轻量)
│       ├── gpu_docling.py  # GPU 可选: Docling AI 版面分析 (需 PyTorch)
│       └── gpu_deepseek.py # GPU 可选: DeepSeek-OCR 旗舰级 OCR
├── infra/                  # 【基础设施基座】
│   ├── hardware_probe.py   # 运行时硬件资源监控与探针 (VRAM/CPU/NPU)
│   ├── env_manager.py      # 依赖懒加载隔离 (Lazy Import 阻断炸库的风险)
│   └── model_manager.py    # 显存 LRU 缓存、模型生命周期与量化自适应管理
└── config/                 # 【配置中心】
    ├── default.yaml        # 默认参数预设
    └── profiles/           # 针对不同场景的动态配置策略 (Speed vs Accuracy)
```

---

## 3. 多模态处理与软硬件路由矩阵 (Modality Routing)

通过配置文件与 Infra 层的 `HardwareProbe`，`DispatchRouter` 动态规划数据的流向。支持自动降级（Fallback）以对抗 OOM 或资源枯竭。

| 模态 / 数据类型 | 场景配置 (Profile) | 承载硬件 | 核心实现方案 | 业务能力与效果评测 |
| :--- | :--- | :--- | :--- | :--- |
| **文本 (Text)** | 极速降级模式 | CPU | \`cpu_tfidf.py\` (正则清洗/BM25) | 速度极快，防异常宕机，适合极低端设备。 |
| | 标准算法模式 | NPU/CPU | \`npu_llmlingua.py\` (LLMLingua-2) | 极低延迟，保留 90%+ 核心语义，词级别压缩。 |
| | 深度理解模式 | GPU | \`gpu_llm_sum.py\` (Qwen2.5 摘要) | 重写提炼，极度精简，但需要消耗一定 GPU 算力。 |
| **图片 (Vision)** | 基础预处理 | CPU | \`cpu_opencv.py\` (降维/裁剪) | 物理降维，有效降低多模态调用的计费/Token阈值。 |
| | 智能聚焦模式 | GPU/NPU | \`gpu_vlm_roi.py\` (CLIP/VL-Nano) | 按 Prompt 提取 ROI（兴趣区），智能剥离无效背景。 |
| **文件 (Office)** | 极速轻量模式 | CPU | \`cpu_native.py\` (MarkItDown/PyMuPDF) | **零模型依赖**，毫秒级解析，覆盖 80%+ 常规文件。 |
| | AI 版面分析模式 | GPU | \`gpu_docling.py\` (Docling/MinerU) | AI 驱动的表格/公式/版面解析，需 PyTorch + 模型。 |
| | 旗舰 OCR 模式 | GPU | \`gpu_deepseek.py\` (DeepSeek-OCR) | 极端复杂手写体/扫描件兜底，占用极高显存。 |

---

## 4. 极致解耦：双擎架构设计 (The Dual-Engine Decoupling)

基于现代 Context Engineering 理念，我们需要将**即时数据压缩**与**会话状态管理**在物理和架构层面上彻底解耦。Context Distiller v2.0 将核心业务切分为两个完全独立但可协同工作的子引擎：**Prompt Distiller (无状态压缩引擎)** 与 **Memory Gateway (有状态记忆网关)**。

### 4.1 引擎一：Prompt Distiller (无状态通用压缩管线)

**定位**：纯无状态 (Stateless) 的流式打磨机。主要服务于 RAG 系统的单次检索召回物、用户临时投递的飞书/PDF文档、或者待解析的图片/视频帧。

* **特性**：
  * **极度即时性**：拦截 Payload 后，打满本地软硬件算力（CPU/NPU/GPU 动态路由），追求极端低延迟 (TTFT)。
  * **零状态持久化**：除了图片/文件特征的**临时本地缓存 (Temp Hash Cache)**以防重复解析外，**绝对不写库、不记录会话、不知晓用户身份**。
  * **输入输出 (I/O) 契约**：

        ```json
        // 请求
        { "data": ["url_to_pdf", "base64_img", "long_text_string"], "profile": "speed" }
        // 响应 (高度精炼的 Prompt 数组，Token大幅消减)
        { "optimized_prompt": [{ "type": "text", "text": "精炼后的高密文本" }] }
        ```

### 4.2 引擎二：Memory Gateway (双作用域可插拔记忆管家)

**定位**：带状态 (Stateful) 的长期大脑。系统将记忆严格划分为两个独立的**作用域 (Scope)**，并提供**可插拔后端 (Pluggable Backend)** 供用户按场景选择。

#### 4.2.1 作用域一：会话记忆 (Session Memory) — 三层递进式压缩策略

**目标**：解决单次会话中多轮对话无限增长导致的 Token 爆炸。核心原则：**"上下文总会满，要有办法腾地方"**。

采用**激进程度递增的三层压缩**，确保会话永远不触及模型 Length 极限，同时完整历史通过 Transcript 持久化到磁盘，信息没有真正丢失，只是移出了活跃上下文。

```text
每次 LLM 调用前:
+------------------+
| Tool call result |     ← 原始的工具调用返回 / 对话消息
+------------------+
        |
        v
[Layer 1: micro_compact]           (静默, 每轮自动执行)
  将超过 N 轮的旧 tool_result
  替换为 "[Previous: used {tool_name}]" 占位符
        |
        v
[Check: tokens > threshold?]
   |               |
   no              yes
   |               |
   v               v
continue    [Layer 2: auto_compact]
              保存完整对话到 .transcripts/
              LLM 摘要, 替换全部旧消息为 [summary]
                    |
                    v
            [Layer 3: compact tool]
              Agent 可主动调用 compact 工具
              触发同样的摘要机制 (按需)
```

* **Layer 1 — micro_compact（静默微压缩）**：每次 LLM 调用前自动执行。将超过 `keep_recent` 轮的旧 `tool_result`（如文件读取结果、命令输出等）替换为轻量占位符 `"[Previous: used {tool_name}]"`。单轮操作仅影响 `content` 字段，不丢失消息结构。
* **Layer 2 — auto_compact（自动深度压缩）**：当 `estimate_tokens(messages)` 超过 `token_threshold`（如 50000）时自动触发。系统先将完整对话序列保存到 `.transcripts/{timestamp}.jsonl` 文件，然后调用 LLM 对整段对话做高度浓缩摘要，最终用 `[Compressed Summary]` 替换全部旧消息。
* **Layer 3 — compact tool（Agent 手动压缩）**：暴露为标准 Agent 工具 `context_compact`，Agent 可在任何时刻主动触发与 Layer 2 相同的摘要机制。适用于 Agent 自主判断"当前上下文已经过长但尚未达到自动阈值"的场景。

**YAML 配置**：

```yaml
memory_gateway:
  session_memory:
    backend: "builtin"
    # --- Layer 1: micro_compact ---
    micro_compact:
      enabled: true
      keep_recent: 3                       # 保留最近 3 轮的完整 tool_result
      min_content_length: 100              # 仅压缩超过 100 字符的结果
    # --- Layer 2: auto_compact ---
    auto_compact:
      enabled: true
      token_threshold: 50000              # Token 阈值触发
      transcript_dir: ".transcripts/"     # 完整对话持久化路径
      summary_max_tokens: 2000            # 摘要最大长度
    # --- Layer 3: compact tool ---
    manual_compact:
      enabled: true                        # 暴露 compact 工具给 Agent
    # --- 通用 ---
    persist_on_close: true                 # 会话结束时持久化为 .jsonl
```

* **生命周期**：绑定 `Session ID`，会话结束即可归档或销毁。完整历史永久保存在 `.transcripts/` 目录中，支持事后回溯与审计。

#### 4.2.2 作用域二：用户长久记忆 (User Long-term Memory) — 跨会话的知识沉淀

**目标**：跨越多个会话周期，持续积累用户画像、偏好设定、关键事实、项目规则。

* **生命周期**：绑定 `User ID` 或 `Agent ID`，**永久存活**，跨会话持久化。
* **数据来源**：
  * **自动抽取**：由 LLM 在会话结束时自动从对话中提炼关键事实（如"用户是素食者"、"项目用 Python 3.12"）。
  * **人工编辑**：开发者或用户直接编辑工作区的 `MEMORY.md` / `memory/*.md` 文件，固化规则与偏好。
  * **Agent 主动写入**：通过 `memory_store` / `memory_update` / `memory_forget` 工具接口，Agent 可自主决定记什么、更新什么、遗忘什么。
* **存储要求**：需要持久化到本地数据库（SQLite + 向量索引 + FTS5）或通过 mem0 的 Hybrid Datastore 管理。
* **检索方式**：下次会话开始时，通过 `memory_search`（混合检索）召回最相关的历史事实，经 Prompt Distiller 浓缩后注入 System Prompt。

#### 4.2.3 可插拔记忆后端 (Pluggable Memory Backend)

系统提供**配置级别的后端切换**，用户通过 `config/default.yaml` 按需选择：

```yaml
memory_gateway:
  # session_memory 配置详见 4.2.1 三层压缩策略的 YAML 配置块

  user_memory:
    backend: "openclaw"                   # 可选: "openclaw" | "mem0" | "custom"
    # --- OpenClaw 风格后端 ---
    openclaw:
      storage: "sqlite"                  # SQLite + sqlite-vec + FTS5
      memory_paths: ["MEMORY.md", "memory/*.md"]
      sync_trigger: "on_search"          # "on_search" | "on_session_start" | "interval"
      search_weights: { vector: 0.7, fts: 0.3 }
    # --- Mem0 后端 (可选) ---
    mem0:
      llm_provider: "ollama"             # 或 "openai" / "deepseek"
      llm_model: "qwen2.5:7b"
      embedder: "BAAI/bge-m3"
      vector_store: "chroma"
      enable_graph: false                # 图记忆 (需 Neo4j，按需开启)
```

| 后端 | 适用场景 | 优势 | 注意事项 |
| :--- | :--- | :--- | :--- |
| **OpenClaw 风格** (默认) | 纯离线、零云端、开发者友好 | 100% 本地，.md 文件人可读可编辑，极简部署 | 需自研 Chunking/Search，无实体消歧 |
| **mem0** | 生产级 Agent、需要实体管理 | 自动提取/更新/消歧事实，arXiv 级验证 | 依赖 LLM 做裁判，写入有 2~5s 延迟 |
| **custom** | 企业自有知识库集成 | 完全自定义存储与检索逻辑 | 需实现 `MemoryBackend` 抽象接口 |

#### 4.2.4 Agent 工具接口与工作流集成

引擎为接入的 Agent 统一包装以下标准工具接口：

| 工具名 | 类型 | 作用域 | 描述 |
| :--- | :--- | :--- | :--- |
| `memory_search` | 只读 | User Memory | 混合语义+关键词检索历史事实 |
| `memory_get` | 只读 | User Memory | 按文件路径+行号精确读取片段 |
| `memory_store` | 写入 | User Memory | 存入新的事实/偏好/规则 |
| `memory_update` | 写入 | User Memory | 更新已有事实（自动消歧冲突） |
| `memory_forget` | 写入 | User Memory | 主动遗忘已过期的记忆条目 |
| `session_summary` | 只读 | Session Memory | 获取当前会话的压缩摘要 |
| `context_compact` | 写入 | Session Memory | Agent 主动触发 Layer 3 上下文压缩 |

* 工作流无缝融合：Memory Gateway 不在用户的单次请求路径上"硬拦截"。它作为大模型可主动呼叫的工具链，查到的关键记忆片段会**首先被送入 Prompt Distiller（引擎一）** 进行即时浓缩，最后再以 `Source: path#L{line}` 格式无缝注入 System Prompt。

### 4.3 双引擎物理与逻辑边界矩阵

| 维度 | Prompt Distiller (引擎一：即时压缩) | Memory Gateway (引擎二：记忆网关) |
| :--- | :--- | :--- |
| **核心职责** | 给**本次输入**"减肥"（提取高密价值信息） | 为**未来提问**"存钱"（Session 压缩 + User 记忆沉淀） |
| **状态(State)** | 无状态 (Stateless)，用完扫地出门 | 双作用域：Session 临时态 + User 永久态 |
| **后端算子依赖** | LLMLingua 模型, OCR 引擎, Vision 处理流 | 可插拔：OpenClaw(SQLite) / mem0(Hybrid) / Custom |
| **隔离与缓存** | 基于文件 Hash 缓存解析结果 (防重复转换) | 强依赖 `Session_ID` / `User_ID` / `Agent_ID` 做数据屏障 |
| **介入系统的时机** | 请求发给大模型**之前** (前置预处理管道) | 收到请求**之后** (作为 Tools 供 LLM 主动调用) |

---

## 5. 解耦与应用部署模式设计 (Deployment & Decoupling)

为了满足企业级“即插即用”和“前后端解耦”，系统提供三种平级入口，共享核心 `Engine`，彻底隔离网络 I/O、业务代码与底层算法算法：

### 5.1 Python 本地 SDK (Local SDK Direct Integration)

适用于拥有自己独立 Python 服务，希望以库级别的粒度嵌入压缩能力。

```python
from context_distiller.sdk import DistillerClient

# 零侵入整合，自动感知硬件
client = DistillerClient(profile="performance_first")

optimized_context = client.process(
    query="分析这些会议图片和财报的主要问题",
    data=["chart.jpg", "Q3_report.pdf"]
)
```

### 5.2 兼容标准 API 的中继网关 (REST API Server)

适用于前后端分离应用，前端 (Web/iOS) 不可部署大模型，必须通过网络桥接。或者业务已绑定在 OpenAI 规范。
Context Distiller 作为部署在宿主机端口（例如 8080）的 **API 透明代理**。

1. **伪装接入**：业务方将 OpenAI SDK 的 Base URL 修改为 `http://localhost:8080/v1`。
2. **劫持与压缩**：网关截获 `POST /chat/completions` 请求，提取超长的 `messages`。
3. **分发打点**：将图片剥离给 Vision Pipeline，长文剥离给 Text Pipeline。
4. **代理转发**：浓缩完成后，再将精简短小的 Payload 真实发往云端 DeepSeek / OpenAI 或本机 vLLM 服务器，拿到结果后再原路返给客户端。

### 5.3 生产环境懒加载与隔离部署 (Lazy Deployment & Packaging)

为保证基础依赖（如只需要文本压缩的用户，不被迫安装 `torch` 和 `transformers`），采取极其严格的依赖隔离：

* 提供不同的安装组包机制：`pip install context-distiller[cpu]` / `[core,vision,gpu]`。
* **Lazy Dependency Injection**：通过 `infra/env_manager.py`。即便运行了 REST API，只要请求中未触发高阶 OCR 与 GPU 动作，系统**绝对不执行** `import torch`，保障内存占用长期在百兆级别，实现真·端侧可控。

---

## 6. 系统执行流程示意图与后续优化步骤

1. **步骤一 (基础架构搭建)**：建立核心 `Engine`, `Router`, 和 SDK / API 路由接口骨架。
2. **步骤二 (接入核心算子)**：集成现有跑通的算法，如将 `demo_llmlingua2.py` 和 ONNX 模块接入 `npu_llmlingua.py`；引入轻量级的正则与 TF-IDF 处理并实现 Fallback 机制。
3. **步骤三 (记忆网关升级)**：集成与引入 OpenClaw 风格的 Memory 机制，实现 Pre-compaction 预裁剪线程。
4. **步骤四 (多模态完善)**：针对 DeepSeek-OCR / Docling 以及图像 OpenCV 的逐步挂载测试。
