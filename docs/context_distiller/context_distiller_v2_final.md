# Context Distiller v2.0 — 最终技术方案

> 全模态统一上下文预处理与 Agent 记忆网关 · 即插即用 · 端侧可控

---

## 1. 架构总览与设计理念

Context Distiller v2.0 从"文本/图像瘦身工具"升级为**企业级大模型端侧输入预处理与 Agent 记忆网关**。

**核心流水线**：`事件(Event) → 数据类型(DataType) → 算法引擎(Algorithm) → 硬件设备(Hardware)`

无论宿主机是仅含 CPU 的轻量级设备，还是具备 GPU/NPU 的高性能节点，系统通过 `HardwareProbe` 算力探针 + `DispatchRouter` 动态路由，自动选择最优算法链路，兼顾**极速 TTFT（首字延迟）**与**最佳语义保真度**。

**四大设计原则**：

| 原则 | 含义 |
| :--- | :--- |
| **极端解耦** | Prompt 即时压缩 (Stateless) 与 Memory 记忆管理 (Stateful) 物理隔离为两个独立引擎 |
| **即插即用** | CPU 层零模型依赖（MarkItDown/PyMuPDF），AI 工具全部为 GPU 可选层（`pip install [gpu]`） |
| **动态分发** | 运行时自动感知硬件算力，按 Profile 配置动态路由，支持自动 Fallback 降级 |
| **懒依赖隔离** | 未触发高阶动作时绝不 `import torch`，内存占用长期百兆级别 |

---

## 2. 工程目录结构 (Final)

```text
context_distiller/
├── api/                        # 【表现层】
│   ├── server/                 # LiteLLM 中间件 + FastAPI 扩展路由
│   └── cli/                    # 命令行工具，批量离线文件清洗
├── sdk/
│   └── client.py               # Python Client SDK (本地直调/远程路由)
├── schemas/                    # 【数据契约层】统一 Pydantic Models
│   ├── events.py               # EventPayload, ProcessedResult, TokenStats
│   ├── memory.py               # MemoryChunk, SearchResult
│   └── config.py               # ProfileConfig, RouterConfig
├── prompt_distiller/           # 【引擎一】无状态即时压缩
│   ├── engine.py               # Pipeline Orchestrator
│   ├── router.py               # DispatchRouter (类型 + 硬件 动态路由)
│   └── processors/
│       ├── base.py             # 抽象基类 BaseProcessor
│       ├── text/
│       │   ├── cpu_regex.py    # L0: 正则清洗 + 停用词 + BM25 (0 MB)
│       │   ├── cpu_selective.py# L1: SelectiveContext GPT-2 自信息量过滤 (~500 MB)
│       │   ├── npu_llmlingua.py# L2: LLMLingua-2 ONNX INT8 量化 (~600 MB)
│       │   └── gpu_summarizer.py# L3: Qwen2.5 摘要重写 / SAC 锚点压缩 (4 GB+)
│       ├── vision/
│       │   ├── cpu_opencv.py   # 降维/裁剪 + pHash 去重 + Tile 精准降档
│       │   └── gpu_vlm_roi.py  # CLIP/VL-Nano 显著性 ROI 抠图
│       └── document/
│           ├── cpu_native.py   # L0: MarkItDown / PyMuPDF + python-docx (零模型)
│           ├── gpu_docling.py  # L1: Docling / MinerU AI 版面分析 (需 PyTorch)
│           └── gpu_deepseek.py # L2: DeepSeek-OCR 旗舰 OCR (极端场景兜底)
├── memory_gateway/             # 【引擎二】有状态记忆网关 (独立顶层模块)
│   ├── session/
│   │   ├── compactor.py        # 三层压缩: micro_compact / auto_compact / manual
│   │   └── transcript.py       # .transcripts/ 持久化与回溯
│   ├── user_memory/
│   │   ├── manager.py          # 记忆管理器 (可插拔后端)
│   │   ├── search.py           # 混合检索 (Vector + FTS5)
│   │   └── sync.py             # 事件驱动同步 (文件系统/会话/定时)
│   ├── backends/
│   │   ├── base.py             # MemoryBackend 抽象接口
│   │   ├── openclaw.py         # OpenClaw 风格: SQLite + sqlite-vec + FTS5 + .md
│   │   ├── mem0_backend.py     # mem0 Hybrid Datastore 后端
│   │   └── custom.py           # 企业自有知识库桥接
│   └── tools.py                # Agent 工具接口 (memory_search/get/store/update/forget)
├── infra/                      # 【基础设施基座】
│   ├── hardware_probe.py       # 运行时算力探针 (VRAM/CPU/NPU)
│   ├── env_manager.py          # 懒依赖加载隔离 (Lazy Import)
│   ├── model_manager.py        # 显存 LRU 缓存 + 量化自适应
│   └── telemetry.py            # Token 消耗 / 压缩率 / 延迟 / OOM 降级指标
├── config/
│   ├── default.yaml            # 默认配置
│   └── profiles/               # 场景策略 (speed / balanced / accuracy)
└── tests/
    ├── unit/
    ├── integration/
    └── benchmarks/              # 压缩率 & 速度基准测试
```

---

## 3. 多模态处理与软硬件路由矩阵

`DispatchRouter` 通过 `config/profiles/` + `HardwareProbe` 运行时探测，自动路由数据到最优处理链。支持自动降级 (Fallback) 对抗 OOM。

### 3.1 文本压缩 — 四档渐进式压缩栈

| 档位 | 硬件 | 实现模块 | 方案 | 模型体积 | 压缩率 | 延迟 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| L0 极速 | CPU | `cpu_regex.py` | 正则清洗 + 停用词 + BM25 句级截断 | 0 MB | ~20-30% | <10ms |
| L1 轻量 | CPU | `cpu_selective.py` | SelectiveContext (GPT-2 自信息量过滤) | ~500 MB | ~40-50% | ~100ms |
| L2 标准 | CPU/NPU | `npu_llmlingua.py` | LLMLingua-2 ONNX INT8 量化推理 | ~600 MB | ~60-80% | ~200ms |
| L3 极致 | GPU | `gpu_summarizer.py` | Qwen2.5 摘要重写 / SAC 锚点压缩 | ~4 GB+ | ~80-95% | ~1-3s |

### 3.2 文档解析 — CPU 零模型 + GPU 可选 AI

| 层级 | 硬件 | 实现模块 | 方案 | 依赖体积 | 说明 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| L0 极速 (默认) | CPU | `cpu_native.py` | **MarkItDown** (微软) | 几十 MB | 零模型，覆盖 PDF/Word/PPT/HTML/Excel/CSV/JSON |
| L0 极致性能 | CPU | `cpu_native.py` | **PyMuPDF** + python-docx | 几 MB | C 底层极速，体积最小 |
| L1 AI 版面 | GPU | `gpu_docling.py` | **Docling** / **MinerU** | 2 GB+ | 表格/公式/版面精细解析，中文财报首选 MinerU |
| L2 旗舰 OCR | GPU | `gpu_deepseek.py` | **DeepSeek-OCR** | 4 GB+ | 极端手写体/扫描件兜底 |

### 3.3 图像处理

| 层级 | 硬件 | 实现模块 | 方案 | 说明 |
| :--- | :--- | :--- | :--- | :--- |
| 基础预处理 | CPU | `cpu_opencv.py` | OpenCV 降维/裁剪 + **pHash 去重** | 多张相似截图仅保留一张；按目标模型 Tile 策略精准降档 |
| 智能聚焦 | GPU/NPU | `gpu_vlm_roi.py` | CLIP/VL-Nano ROI 抠图 | 按 Prompt 提取兴趣区，剥离无效背景 |

---

## 4. 双擎架构：极致解耦 (The Dual-Engine)

核心业务切分为两个完全独立但可协同的子引擎：

### 4.1 引擎一：Prompt Distiller (无状态即时压缩)

**定位**：纯无状态 (Stateless) 的流式打磨机。服务于 RAG 召回物、用户临时投递的文档、待解析的图片/视频帧。

* **极度即时性**：拦截 Payload 后，打满本地算力，追求极端低 TTFT。
* **零状态持久化**：除临时文件 Hash 缓存外，绝不写库、不记录会话、不知晓用户身份。
* **I/O 契约**：

```json
// 请求
{ "data": ["url_to_pdf", "base64_img", "long_text"], "profile": "speed" }
// 响应
{ "optimized_prompt": [{ "type": "text", "text": "精炼后的高密文本" }] }
```

### 4.2 引擎二：Memory Gateway (双作用域可插拔记忆网关)

**定位**：带状态 (Stateful) 的长期大脑。将记忆严格划分为两个作用域，提供可插拔后端供用户按场景选择。

#### 4.2.1 作用域一：会话记忆 (Session Memory) — 三层递进式压缩

**核心原则**：*"上下文总会满，要有办法腾地方"*。激进程度递增的三层压缩，确保永不触及模型 Length 极限，完整历史通过 Transcript 持久化到磁盘（信息不丢失，只移出活跃上下文）。

```text
每次 LLM 调用前:
+------------------+
| Tool call result |     ← 原始工具调用返回 / 对话消息
+------------------+
        |
        v
[Layer 1: micro_compact]           (静默, 每轮自动)
  超过 N 轮的旧 tool_result → "[Previous: used {tool}]"
        |
        v
[tokens > threshold?]
   |             |
   no           yes
   |             |
   v             v
continue  [Layer 2: auto_compact]
            保存完整对话到 .transcripts/
            LLM 摘要 → 替换全部旧消息
                  |
                  v
          [Layer 3: compact tool]
            Agent 可主动调用 (按需)
```

| Layer | 名称 | 触发 | 行为 |
| :--- | :--- | :--- | :--- |
| L1 | `micro_compact` | 每轮 LLM 调用前自动 | 将 >N 轮旧 tool_result 替为占位符，仅改 content，保留消息结构 |
| L2 | `auto_compact` | Token > 阈值（如 50000） | 完整对话存 `.transcripts/{ts}.jsonl`，LLM 摘要替换全部旧消息 |
| L3 | `compact tool` | Agent 主动调用 `context_compact` | 与 L2 相同机制，由 Agent 自主判断触发时机 |

**生命周期**：绑定 `Session ID`，会话结束可归档/销毁，完整历史永久保存在 `.transcripts/`。

#### 4.2.2 作用域二：用户长久记忆 (User Long-term Memory) — 跨会话知识沉淀

**目标**：跨越多个会话周期，持续积累用户画像、偏好设定、关键事实、项目规则。

* **生命周期**：绑定 `User ID` / `Agent ID`，**永久存活**，跨会话持久化。
* **数据来源**：
  * **自动抽取**：LLM 在会话结束时自动提炼关键事实（如"用户是素食者"、"项目用 Python 3.12"）。
  * **人工编辑**：开发者直接编辑 `MEMORY.md` / `memory/*.md` 文件，固化规则与偏好。
  * **Agent 主动写入**：通过 `memory_store` / `memory_update` / `memory_forget` 工具接口，Agent 自主决定记什么、更新什么、遗忘什么。
* **存储**：持久化到本地 SQLite + 向量索引 + FTS5，或通过 mem0 Hybrid Datastore 管理。
* **检索**：下次会话开始时通过 `memory_search`（混合检索）召回，经 Prompt Distiller 浓缩后注入 System Prompt。

#### 4.2.3 可插拔记忆后端 (Pluggable Memory Backend)

| 后端 | 适用场景 | 优势 | 注意事项 |
| :--- | :--- | :--- | :--- |
| **OpenClaw 风格** (默认) | 纯离线、零云端、开发者友好 | 100% 本地，.md 人可读可编辑，极简部署 | 需自研 Chunking/Search |
| **mem0** | 生产级 Agent、需要实体消歧 | 自动提取/更新/消歧事实，arXiv 验证（91% Token 成本降低） | 依赖 LLM 做裁判，写入 2~5s |
| **custom** | 企业自有知识库集成 | 完全自定义存储与检索 | 需实现 `MemoryBackend` 抽象接口 |

#### 4.2.4 Agent 工具接口

| 工具名 | 类型 | 作用域 | 描述 |
| :--- | :--- | :--- | :--- |
| `memory_search` | 只读 | User Memory | 混合语义+关键词检索历史事实 |
| `memory_get` | 只读 | User Memory | 按文件路径+行号精确读取片段 |
| `memory_store` | 写入 | User Memory | 存入新的事实/偏好/规则 |
| `memory_update` | 写入 | User Memory | 更新已有事实（自动消歧冲突） |
| `memory_forget` | 写入 | User Memory | 主动遗忘已过期的记忆条目 |
| `session_summary` | 只读 | Session Memory | 获取当前会话的压缩摘要 |
| `context_compact` | 写入 | Session Memory | Agent 主动触发 Layer 3 上下文压缩 |

工作流：Memory Gateway 不硬拦截请求路径，作为大模型可主动呼叫的工具链。召回的记忆片段会**先经 Prompt Distiller 浓缩**，再以 `Source: path#L{line}` 格式注入 System Prompt。

### 4.3 双引擎边界矩阵

| 维度 | Prompt Distiller (引擎一) | Memory Gateway (引擎二) |
| :--- | :--- | :--- |
| **核心职责** | 给**本次输入**"减肥" | 为**未来提问**"存钱" (Session 压缩 + User 记忆沉淀) |
| **状态** | 无状态 (Stateless) | 双作用域：Session 临时态 + User 永久态 |
| **后端依赖** | LLMLingua, OCR, Vision 处理流 | 可插拔：OpenClaw / mem0 / Custom |
| **隔离机制** | 文件 Hash 缓存防重复转换 | `Session_ID` / `User_ID` / `Agent_ID` 数据屏障 |
| **介入时机** | 请求发给大模型**之前** | 请求到达**之后** (作为 Tools 供 LLM 调用) |

---

## 5. 统一配置 (YAML)

```yaml
# config/default.yaml

# ===== 引擎一：Prompt Distiller =====
prompt_distiller:
  profile: "balanced"                      # speed | balanced | accuracy
  text:
    default_level: "L2"                    # L0(regex) | L1(selective) | L2(llmlingua) | L3(gpu_sum)
    onnx_quantization: "int8"              # LLMLingua-2 量化策略
  document:
    cpu_backend: "markitdown"              # markitdown | pymupdf
  vision:
    dedup_enabled: true                    # pHash 去重
    tile_adaptive: true                    # 按目标模型 Tile 策略精准降档

# ===== 引擎二：Memory Gateway =====
memory_gateway:
  # --- 会话记忆 (三层压缩) ---
  session_memory:
    backend: "builtin"
    micro_compact:
      enabled: true
      keep_recent: 3                       # 保留最近 N 轮的完整 tool_result
      min_content_length: 100
    auto_compact:
      enabled: true
      token_threshold: 50000
      transcript_dir: ".transcripts/"
      summary_max_tokens: 2000
    manual_compact:
      enabled: true                        # 暴露 context_compact 工具给 Agent
    persist_on_close: true

  # --- 用户长久记忆 ---
  user_memory:
    backend: "openclaw"                    # openclaw | mem0 | custom
    openclaw:
      storage: "sqlite"                   # SQLite + sqlite-vec + FTS5
      memory_paths: ["MEMORY.md", "memory/*.md"]
      sync_trigger: "on_search"           # on_search | on_session_start | interval
      search_weights: { vector: 0.7, fts: 0.3 }
    mem0:
      llm_provider: "ollama"
      llm_model: "qwen2.5:7b"
      embedder: "BAAI/bge-m3"
      vector_store: "chroma"
      enable_graph: false

# ===== API 网关 =====
api:
  gateway: "litellm"                       # LiteLLM 中间件模式
  port: 8080
  cost_tracking: true
  load_balancing: true

# ===== 可观测性 =====
telemetry:
  enabled: true
  metrics: ["token_count", "compression_ratio", "latency_ms", "oom_fallback_count"]
```

---

## 6. 部署模式 (Deployment)

### 6.1 Python SDK (本地直调)

```python
from context_distiller.sdk import DistillerClient

client = DistillerClient(profile="balanced")
result = client.process(
    query="分析会议图片和财报",
    data=["chart.jpg", "Q3_report.pdf"]
)
```

### 6.2 REST API 透明代理

基于 **LiteLLM 中间件**扩展，复用其 100+ 模型兼容 / 成本追踪 / 负载均衡能力：

1. 业务方设置 `base_url = "http://localhost:8080/v1"`
2. 网关截获 `/chat/completions`，提取超长 `messages`
3. 分发：图片 → Vision Pipeline，长文 → Text Pipeline，文件 → Document Pipeline
4. 浓缩后转发至云端/本机推理服务器，原路返回

### 6.3 懒加载与隔离安装

```bash
pip install context-distiller           # 仅 CPU 核心 (几十 MB)
pip install context-distiller[vision]   # + OpenCV / Pillow
pip install context-distiller[gpu]      # + PyTorch + Docling + DeepSeek-OCR
pip install context-distiller[mem0]     # + mem0 记忆后端
pip install context-distiller[full]     # 全家桶
```

`infra/env_manager.py` 保证：未触发 GPU 动作时**绝不执行** `import torch`。

---

## 7. 关键技术选型总览

| 技术领域 | 选型方案 | 选型理由 |
| :--- | :--- | :--- |
| 文档解析 (CPU 默认) | **MarkItDown** / PyMuPDF + python-docx | 零 PyTorch，毫秒级，即插即用 |
| 文档解析 (GPU 可选) | Docling + MinerU + DeepSeek-OCR | 三引擎互补，按需安装 |
| 文本压缩 L0 | 正则 + BM25 | 零依赖，<10ms |
| 文本压缩 L1 | **SelectiveContext** | GPT-2 级别轻量语义过滤 (~500MB) |
| 文本压缩 L2 | **LLMLingua-2 ONNX INT8** | 模型从 2.2GB 降至 ~600MB，提速 2-3x |
| 文本压缩 L3 | Qwen2.5 / SAC 锚点压缩 | GPU 级极致压缩 |
| 图像预处理 | OpenCV + **pHash 去重** + Tile 降档 | 按目标模型计费策略精准缩放 |
| 会话记忆 | 三层压缩 (micro/auto/manual compact) | 参考 s06 Context Compact 最佳实践 |
| 用户长久记忆 | **OpenClaw** (默认) / **mem0** (可选) | OpenClaw 极简离线；mem0 生产级实体管理 |
| API 网关 | **LiteLLM** 中间件扩展 | 100+ 模型，内置成本追踪/负载均衡 |
| 可观测性 | `telemetry.py` → Prometheus/StatsD | Token 消耗 / 压缩率 / TTFT / OOM 降级 |

---

## 8. 分阶段实施路线

### Phase 1：基座加固（1~2 周）

* [ ] 搭建目录结构：`prompt_distiller/` + `memory_gateway/` + `schemas/` + `tests/`
* [ ] 集成 LLMLingua-2 ONNX INT8 量化推理路径
* [ ] 新增 `infra/telemetry.py`，所有 Processor 输出统一 `TokenStats`

### Phase 2：压缩算法补全（2~3 周）

* [ ] 实现 `cpu_selective.py` (SelectiveContext L1 轻量压缩)
* [ ] 实现 `cpu_native.py` (MarkItDown/PyMuPDF 零模型文档解析)
* [ ] 图像管道实现 pHash 去重 + 目标模型 Tile 精准降档

### Phase 3：记忆网关生产化（3~4 周）

* [ ] 实现三层会话压缩 (`micro_compact` / `auto_compact` / `compact tool`)
* [ ] 实现 OpenClaw 风格后端 (SQLite + sqlite-vec + FTS5 + .md 文件同步)
* [ ] 评估并集成 mem0 后端 (或参考其架构用 SQLite 自研)
* [ ] 实现 `memory_store/update/forget` 写入工具

### Phase 4：网关与运维（2~3 周）

* [ ] 将 `api/server/` 重构为 LiteLLM 中间件
* [ ] 接入 Prometheus 或 StatsD 指标看板
* [ ] 编写分层测试 (unit / integration / benchmarks)
