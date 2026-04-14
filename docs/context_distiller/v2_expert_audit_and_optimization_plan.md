# Context Distiller v2.0 架构专家审计与优化计划

> 以企业级 Agent Context Engineering 引擎开发专家视角，对当前架构文档进行逐层审视，结合 2025~2026 业界最新成熟开源生态，提出最佳优化路线。

---

## 一、总体评价

当前架构在"双擎解耦（Prompt Distiller / Memory Gateway）"、"动态硬件路由"和"懒依赖隔离"三个维度上已达到**优秀的工程骨架水平**。但在以下关键领域存在可量化的优化空间：

| 审计维度 | 当前评级 | 目标评级 | 核心差距 |
|---|---|---|---|
| 文档解析工具链匹配度 | B | A | 缺少 MinerU 混合方案；Docling 单引擎覆盖不足 |
| 文本压缩算法栈深度 | B+ | A | 仅覆盖 LLMLingua-2，缺少 SelectiveContext 等轻量替代 |
| 记忆管理框架成熟度 | B | A | 自研 Memory 模块风险高；应对标 mem0/Letta 成熟方案 |
| API 网关透明代理能力 | B- | A | 自建 FastAPI 代理缺少负载均衡/多模型路由/成本追踪 |
| 可观测性与运维 | C | B+ | 缺少 Token 消耗统计、压缩率指标、延迟监控 |
| 目录结构与抽象粒度 | B+ | A | memory 模块嵌套在 core/ 下不够独立；缺少 schemas/ |

---

## 二、逐模块深度审计与优化建议

### 2.1 文档解析管道 (Document Pipeline) — CPU 层工具过于笨重

**当前方案**：CPU 用 Docling/Marker，GPU 用 DeepSeek-OCR。

**核心问题：Marker / MinerU / Docling 三者在默认形态下与"轻量化"毫无关系。**

这三个工具的核心卖点都是基于深度学习（视觉模型）的版面分析。底层强依赖 PyTorch（仅依赖包就超过 2GB），且需要下载数 GB 的视觉模型。在纯 CPU 环境下解析一页复杂 PDF 可能需要数秒到十几秒。即便关闭所有 AI 模型，安装时依然会拉入 PyTorch 等数百 MB 依赖。这与插件"即插即用"的核心理念严重冲突。

**优化方案：CPU 层用零模型原生库，AI 工具全部归入可选 GPU 层**

| 层级 | 硬件 | 推荐工具 | 依赖体积 | 理由 |
| :--- | :--- | :--- | :--- | :--- |
| L0 极速 (默认) | CPU | **MarkItDown** (微软) | 几十 MB | 零模型依赖，整合 pdfminer/python-docx/BeautifulSoup，覆盖 PDF/Word/PPT/HTML/Excel/CSV/JSON |
| L0 极致性能 | CPU | **PyMuPDF** + python-docx + python-pptx | 几 MB | C 底层极速解析，体积最小，覆盖 80%+ 常规文件 |
| L1 AI 版面分析 | GPU | **Docling** / **MinerU** | 2 GB+ | AI 驱动的表格/公式/版面精细解析，中文财报首选 MinerU |
| L2 旗舰 OCR | GPU | **DeepSeek-OCR** | 4 GB+ | 极端复杂手写体/扫描件兜底 |

**工程改进**：

- `processors/document/cpu_native.py`：基于 MarkItDown 或 PyMuPDF 组合实现，零 PyTorch 依赖。
- `processors/document/gpu_docling.py`：Docling/MinerU 作为可选 GPU 层，通过 `pip install context-distiller[gpu]` 才安装。
- 对于无法解析的复杂扫描件，CPU 层返回元信息并提示用户启用 GPU 模式。

---

### 2.2 文本压缩算法栈 (Text Compression) — 缺少轻量级中间档

**当前方案**：CPU 用 TF-IDF/BM25，NPU 用 LLMLingua-2，GPU 用 Qwen 摘要。

**问题**：

1. **CPU 档到 NPU 档之间跳跃过大**：TF-IDF 是纯统计方法（压缩率 ~30%），LLMLingua-2 需要加载 ~2GB 的 XLM-RoBERTa 模型。中间缺乏**轻量但语义感知的方案**。
2. **SelectiveContext 被遗漏**：这是一个纯 Python 实现的 Token 级过滤器，利用小型 GPT-2 级别模型（~500MB）计算自信息量(self-information)来剔除低价值 Token。它比 TF-IDF 好得多，但比 LLMLingua-2 轻得多。
3. **LLMLingua-2 的 ONNX 推理未被充分规划**：项目已有 `convert_to_onnx.py` 和 2.2GB 的 ONNX 模型，但架构文档未明确 ONNX Runtime 的集成路径和量化策略（INT8 可将模型降至 ~600MB）。

**优化方案（四档渐进式压缩栈）**：

| 档位 | 硬件 | 方案 | 模型大小 | 压缩率 | 延迟 |
|---|---|---|---|---|---|
| L0 极速 | CPU | 正则清洗 + 停用词 + BM25 句级截断 | 0 MB | ~20-30% | <10ms |
| L1 轻量 | CPU | **SelectiveContext** (GPT-2 自信息量过滤) | ~500 MB | ~40-50% | ~100ms |
| L2 标准 | CPU/NPU | LLMLingua-2 (**ONNX INT8 量化**) | ~600 MB | ~60-80% | ~200ms |
| L3 极致 | GPU | Qwen2.5 摘要重写 / SAC 锚点压缩 | ~4 GB+ | ~80-95% | ~1-3s |

**工程改进**：新增 `processors/text/cpu_selective.py`，并在 `npu_llmlingua.py` 中明确集成 `onnxruntime` + INT8 量化推理。

---

### 2.3 记忆管理系统 (Memory Gateway) — 自研风险需对标成熟方案

**当前方案**：自研 SQLite + sqlite-vec + FTS5，借鉴 OpenClaw。

**问题**：

1. **自研 Memory 模块的维护成本极高**：从零实现 Chunking、Embedding Cache、Hybrid Search、Temporal Decay、MMR 重排等功能，工程量巨大。
2. **业界已有生产就绪方案**：
   - **mem0**：生产级混合记忆层，支持 user/session/agent 三级记忆，已有 arXiv 论文验证可降低 91% Token 成本。Python SDK 可直接嵌入。
   - **Letta (原 MemGPT)**：UC Berkeley 出品，模型不可知，支持 Core/Archival/Recall 三层记忆，Agent 可自主决定"记什么/忘什么"。
   - **Zep**：时序知识图谱驱动，自动将对话转化为动态知识图谱。
3. **OpenClaw 的记忆系统是只读设计**（Agent 仅有 `memory_search` + `memory_get`，写入依赖人工编辑 .md 文件）。如果我们的系统要支持 Agent **自主写入记忆**，需要额外设计 `memory_store` / `memory_update` / `memory_forget` 工具。

**优化方案**：

> [!IMPORTANT]
> **推荐采用 mem0 作为记忆管理的核心引擎**，而非完全自研。理由：
>
> 1. mem0 已有生产验证，Paper 证明在准确率、延迟、Token 消耗上全面优于 full-context 方案。
> 2. mem0 的 Python SDK 轻量级，可直接作为 `core/memory/` 模块的底层驱动。
> 3. 我们在其上层包装 OpenClaw 风格的 `.md` 文件生态和 `memory_search` / `memory_get` / `memory_store` 工具接口即可。

如果坚持自研（完全离线、零云端依赖），则应参考 mem0 的架构模式，但用 SQLite 替代其 Qdrant 后端。

---

### 2.4 API 网关代理层 — 应集成 LiteLLM 而非完全自建

**当前方案**：自建 FastAPI 服务，手动伪装 OpenAI 协议。

**问题**：

1. **LiteLLM 已是该领域的事实标准**：支持 100+ 模型统一接口、内置成本追踪、负载均衡、限速、日志、虚拟 API Key 管理。
2. **Headroom**（2026 年新项目）：定位为"Context Compression Platform"，本身就是一个 OpenAI 兼容透明代理 + 上下文压缩中间件，与我们的定位高度吻合。
3. 自建 FastAPI 代理需要自己处理流式 SSE 转发、错误重试、多模型 Fallback 等复杂逻辑。

**优化方案**：

- 将 `api/server/` 作为 **LiteLLM 的自定义中间件（Middleware/Hook）** 来实现，而非从头重写 OpenAI 协议兼容层。
- 我们的核心价值在于"压缩层"，网关协议层应尽可能复用成熟基建。

---

### 2.5 图像处理管道 (Vision Pipeline) — 基本合理，细节可优化

**当前方案**：CPU 用 OpenCV，GPU 用 CLIP/VL-Nano。

**评价**：方向正确，但建议补充：

1. **Pillow + 感知哈希 (pHash)**：用于图片去重（多张相似截图只保留一张），纯 CPU，在这之前应该做前端去重。
2. **分辨率自适应降档**：不同 VLM API 的计费分辨率阈值不同（如 OpenAI GPT-4o 以 512x512 为一个 tile 单位），应根据目标模型的 tile 策略做精准降分辨率，而非粗暴缩放。

---

### 2.6 工程目录结构 — 需要更精细的抽象

**当前问题**：

1. `core/memory/` 嵌套在 `core/` 下，但 Memory Gateway 是一个独立引擎，应提升为顶层模块。
2. 缺少 `schemas/` 目录定义统一的数据契约（如 `ProcessedResult`, `MemoryChunk`, `EventPayload`）。
3. 缺少 `tests/` 目录规划。

**优化后的目录结构**：

```text
context_distiller/
├── api/                    # 表现层
│   ├── server/             # LiteLLM 中间件 + FastAPI 扩展路由
│   └── cli/
├── sdk/
│   └── client.py
├── schemas/                # 统一数据契约 (Pydantic Models)
│   ├── events.py           # EventPayload, ProcessedResult
│   ├── memory.py           # MemoryChunk, SearchResult
│   └── config.py           # ProfileConfig, RouterConfig
├── prompt_distiller/       # 引擎一：无状态压缩 (原 core/ + processors/)
│   ├── engine.py           # Pipeline Orchestrator
│   ├── router.py           # DispatchRouter
│   └── processors/
│       ├── base.py
│       ├── text/ (cpu_regex, cpu_selective, npu_llmlingua, gpu_summarizer)
│       ├── vision/ (cpu_opencv, gpu_vlm_roi)
│       └── document/ (cpu_native, gpu_docling, gpu_deepseek)
├── memory_gateway/         # 引擎二：有状态记忆 (独立顶层模块)
│   ├── manager.py          # 记忆管理器 (基于 mem0 或自研 SQLite)
│   ├── search.py           # 混合检索 (Vector + FTS5)
│   ├── sync.py             # 事件驱动同步
│   └── tools.py            # Agent 工具接口 (memory_search/get/store)
├── infra/
│   ├── hardware_probe.py
│   ├── env_manager.py
│   ├── model_manager.py
│   └── telemetry.py        # 新增：Token 消耗/压缩率/延迟指标采集
├── config/
│   ├── default.yaml
│   └── profiles/
└── tests/                  # 新增：分层测试
    ├── unit/
    ├── integration/
    └── benchmarks/          # 压缩率 & 速度基准测试
```

---

## 三、分阶段优化执行计划

### Phase 1：基座加固（1~2 周）

- [ ] 提升目录结构：将 memory 从 `core/` 独立为 `memory_gateway/`；新增 `schemas/`。
- [ ] 集成 LLMLingua-2 ONNX INT8 量化推理路径（复用现有 `models/llmlingua2.onnx`）。
- [ ] 新增 `infra/telemetry.py`，为所有 Processor 输出统一的 `TokenStats`（原始/压缩/比率/耗时）。

### Phase 2：压缩算法补全（2~3 周）

- [ ] 新增 `cpu_selective.py`（SelectiveContext 轻量压缩，填补 L0 到 L2 的中间档）。
- [ ] 实现 `cpu_native.py`（基于 MarkItDown/PyMuPDF + python-docx 的零模型文档解析）。
- [ ] 图像管道补充感知哈希去重 + 模型 Tile 精准降档。

### Phase 3：记忆网关生产化（3~4 周）

- [ ] 评估并集成 mem0 作为 `memory_gateway/` 的底层引擎（或参考其架构用 SQLite 自研）。
- [ ] 实现 `memory_store` / `memory_update` / `memory_forget` 写入工具，突破 OpenClaw "只读" 限制。
- [ ] 实现 Pre-compaction Flush 预压缩触发器（Session Token 超阈值时自动摘要）。

### Phase 4：网关与可观测性（2~3 周）

- [ ] 将 `api/server/` 重构为 LiteLLM 自定义中间件，复用其多模型路由 + 成本追踪能力。
- [ ] 接入 Prometheus/Grafana 或轻量 StatsD 指标看板，覆盖压缩率/TTFT/Token 节省量/OOM 降级次数。

---

## 四、关键技术选型决策矩阵

| 技术领域 | 当前选择 | 推荐升级 | 升级理由 |
|---|---|---|---|
| 文档解析 (CPU) | Docling 单引擎 | **MarkItDown** (零模型) / PyMuPDF + python-docx | 零 PyTorch 依赖，毫秒级，符合即插即用理念 |
| 文档解析 (GPU 可选) | 无 | Docling + MinerU + DeepSeek-OCR | AI 版面/公式/OCR 三引擎互补，按需加载 |
| 文本压缩 (轻量) | 直接跳到 LLMLingua-2 | 新增 SelectiveContext (L1 档) | 填补 0~2GB 的算力真空带 |
| LLMLingua-2 推理 | PyTorch 原生 | ONNX Runtime + INT8 量化 | 模型体积从 2.2GB 降至 ~600MB，推理提速 2~3x |
| 记忆管理 | 完全自研 SQLite | 集成 mem0 为底层引擎 | 生产验证，91% Token 成本降低 |
| API 网关 | 自建 FastAPI | 基于 LiteLLM 中间件扩展 | 100+ 模型兼容，内置成本追踪/负载均衡 |
| 可观测性 | 无 | 新增 telemetry 模块 | 企业级必备，量化压缩效果 |
