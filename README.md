# Context Distiller v2.0

> **全模态统一上下文预处理与 Agent 记忆网关**
> 即插即用 · 端侧可控 · 多租户隔离

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688.svg)](https://fastapi.tiangolo.com/)

```
Prompt Distiller (无状态压缩)  +  Memory Gateway (有状态记忆)  +  Web UI (React)
```

---

## 为什么需要 Context Distiller？

| 痛点 | Context Distiller 的解决方案 |
|------|---------------------------|
| LLM 上下文窗口有限，长文档被截断 | 四档文本压缩 (L0–L3)，40%–80% 压缩率 |
| Token 费用高昂 | 压缩后 Token 减少，直接降低调用成本 |
| 长上下文推理慢、注意力稀释 | 去噪后更短更精，TTFT 显著降低 |
| Agent 多轮对话膨胀，超出窗口 | 三层会话压缩自动管理对话生命周期 |
| Agent 跨会话"失忆" | 长期记忆系统 (OpenClaw / Mem0) 持久化用户知识 |
| 多模态输入处理碎片化 | 文本/文档/图像/URL/data URI 统一管道，自动识别 |

---

## 系统架构

```
                    ┌──────────────────────────────────────┐
                    │           Web UI (React + Vite)       │
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
           │ L0 Regex      │   │ L1 Micro     │  │ OpenClaw    │
           │ L1 Selective  │   │ L2 Auto      │  │ (SQLite+FTS │
           │ L2 LLMLingua  │   │ L3 Manual    │  │  +向量)     │
           │ L3 LLM摘要    │   │              │  │             │
           │               │   │ 策略链:       │  │ Mem0        │
           │ Doc Pipeline  │   │ lingua→llm   │  │ (可选)      │
           │ Vision Pipeline│  │ →fallback    │  │             │
           └───────┬───────┘   └──────┬───────┘  └──────┬─────┘
                   │                  │                  │
                   └──────────────────┼──────────────────┘
                                      │
                            ┌─────────▼─────────┐
                            │   Ollama Server    │
                            │  qwen2.5:7b (文本) │
                            │  qwen2.5vl:7b (VLM)│
                            │  deepseek-ocr (OCR)│
                            │  bge-m3 (Embedding)│
                            └────────────────────┘
```

---

## 主要能力

### Prompt Distiller — 无状态多模态压缩

**四档文本压缩 (L0–L3)**

| 档位 | Profile | 算法 | 压缩率 | 延迟 | 说明 |
|------|---------|------|--------|------|------|
| L0 | `speed` | Regex 清洗 + 停用词过滤 | 10–20% | < 1ms | 纯规则，零依赖 |
| L1 | `selective` | GPT-2 自信息量过滤 | 30–40% | 50–200ms | 句子级筛选，保留高信息量内容 |
| L2 | `balanced` | LLMLingua-2 (ONNX + INT8) | 40–50% | 100–500ms | Token 级分类，多语言，**推荐默认** |
| L3 | `accuracy` | LLM 摘要重写 (Qwen2.5) | 60–80% | 2–10s | 语义级重写，最高压缩率 |

**文档压缩管道**

```
文档文件 → 文本提取 → 智能分块 (≤1200字符) → 逐块压缩 (L0–L3) → 结构化输出
```

支持 4 种提取后端：

| 后端 | 擅长场景 |
|------|---------|
| **MarkItDown** (微软) | Office 文档 (DOCX/XLSX/PPTX)、HTML、通用格式 |
| **Docling** (IBM) | 复杂排版论文、表格密集型 PDF |
| **PyMuPDF** | 通用 PDF 快速提取（文本层） |
| **DeepSeek-OCR** | 扫描件、手写体、截图 OCR |

**图像处理**

| 模式 | 方式 | 适用场景 |
|------|------|---------|
| Pixel | pHash 去重 + 自适应缩放 (≤1024px) | 需保留视觉信息（图表、UI 截图） |
| Semantic | OCR / VLM 描述 / CLIP ROI 裁剪 | 需转为纯文本（文档扫描、标注图） |

### Memory Gateway — 有状态记忆管理

**会话记忆 (SessionCompactor)** — 三层渐进式压缩

| 层级 | 触发条件 | 机制 |
|------|---------|------|
| L1 Micro-Compact | 始终开启 | 将旧 tool_result 替换为占位符，保留最近 3 条 |
| L2 Auto-Compact | Token > 50K 阈值 | 保存 transcript → 生成摘要 → 替换历史 → 自动存入长期记忆 |
| L3 Manual | API / 工具调用 | 主动触发压缩或归档 |

摘要策略支持三选一 + 自动降级链：`lingua` → `llm` → `fallback`

**长期记忆** — 可插拔双后端

| 后端 | 特点 |
|------|------|
| **OpenClaw** (内置) | 本地 SQLite + FTS5 全文索引 + BGE-M3 向量搜索，混合检索 (向量 70% + FTS 30%)，数据不出网 |
| **Mem0** (可选) | 自动记忆提取 + 智能去重 + 冲突检测，可接 Neo4j 图谱，支持 Qdrant/Chroma 等向量库 |

多租户隔离模型：`(user_id, agent_id)` 复合键，6 种记忆分类 (fact / preference / rule / profile / note / system)

---

## 快速开始

### 前置条件

- Python 3.9+
- Node.js 18+ (前端)
- [Ollama](https://ollama.com) 运行中，并已拉取所需模型：

```bash
ollama pull qwen2.5:7b        # 文本推理 & 摘要
ollama pull bge-m3             # 向量嵌入
# 可选
ollama pull qwen2.5vl:7b      # 视觉语言模型
ollama pull deepseek-ocr       # OCR 识别
```

### 1. 安装

```bash
cd context_compress

# 创建虚拟环境
python -m venv .venv
.\.venv\Scripts\activate       # Windows PowerShell
# source .venv/bin/activate    # macOS / Linux

# 安装依赖
pip install -r requirements.txt
pip install -e .

# 可选：GPU 加速 & Mem0
# pip install -e ".[gpu]"      # torch + transformers + onnxruntime-gpu + docling
# pip install -e ".[mem0]"     # mem0ai
# pip install -e ".[full]"     # 以上全部
```

### 2. 启动后端

```bash
python -m context_distiller.api.server.app
# 默认监听 http://localhost:8080
```

### 3. 启动前端

```bash
cd context_distiller_ui
npm install
npm run dev
# 默认 http://localhost:5173，Backend URL 指向 localhost:8080（右上角可改）
```

---

## 使用方式

### Python SDK

```python
from context_distiller.sdk.client import DistillerClient

client = DistillerClient(profile="balanced", user_id="alice", agent_id="assistant")

# ---- Prompt Distiller: 文本/文档/URL 混合传入，逐条独立压缩 ----
result = client.process(data=["一段很长的提示词...", "uploads/paper.pdf"])
print(f"压缩率: {result.stats.compression_ratio:.2%}")
# optimized_prompt[0] → {"type": "text", "content": "压缩后文本..."}
# optimized_prompt[1] → {"type": "document", "content": {"text": "...", "chunks": [...]}}

# ---- 长期记忆 CRUD ----
client.store_memory(content="用户偏好暗色主题", source="chat#42", category="preference")
hits = client.search_memory("主题偏好", top_k=3)

# ---- 会话压缩 ----
client.context_compact(messages=[...], session_id="sess_001")
```

### REST API

**Prompt Distiller**

```bash
curl -X POST http://localhost:8080/v1/distill \
  -H "Content-Type: application/json" \
  -d '{
    "profile": "balanced",
    "data": ["一段需要压缩的提示词", "uploads/report.pdf"]
  }'
```

响应中 `optimized_prompt[i]` 为独立条目，每项包含：
- `type`: `"text"` | `"document"` | `"image"`
- `content.text`: 压缩后文本
- `content.chunks` (文档): 智能分块列表，每块含 `title / index / text / compressed`

**Agent Chat**

```bash
curl -X POST http://localhost:8080/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "帮我分析这个项目的架构",
    "user_id": "alice",
    "agent_id": "assistant",
    "session_id": "sess_001",
    "mode": "full"
  }'
```

**完整端点列表**

| 端点 | 方法 | 说明 |
|------|------|------|
| `/health` | GET | 健康检查 |
| `/v1/distill` | POST | 多模态一键压缩 |
| `/v1/chat` | POST | Agent 对话（自动整合记忆 + 会话压缩） |
| `/v1/chat/reset` | POST | 重置会话 |
| `/v1/memory/search` | POST | 搜索长期记忆 |
| `/v1/memory/store` | POST | 存储记忆 |
| `/v1/memory/update` | POST | 更新记忆 |
| `/v1/memory/forget` | POST | 删除记忆 |
| `/v1/memory/list` | POST | 列出记忆（支持分类过滤） |
| `/v1/settings` | GET / PUT | 读取 / 修改运行时配置 |

### Web UI

**Agent Chat** — 4 种聊天模式

| 模式 | 长期记忆 | 会话压缩 | 自动存储 | 用途 |
|------|---------|---------|---------|------|
| Full Agent | 开 | 开 | 开 | 完整 Agent 体验，日常使用 |
| Memory Only | 开 | 关 | 开 | 测试长期记忆效果 |
| Session Only | 关 | 开 | 关 | 测试会话压缩效果 |
| Plain | 关 | 关 | 关 | 纯 LLM 基线对照 |

- 顶部 `user_id / agent_id / session_id` 三层隔离
- 右侧标签实时展示：记忆召回/写入条数、compact 触发状态、Token 估算

**Distill Tool** — 独立压缩工具
- `Prompt text`：提示词压缩
- `Context items`：每行一个文件/URL/data URI，逐条独立压缩
- 支持选择 Profile 和文档提取后端

**Memory Explorer** — 在当前 `user_id / agent_id` 作用域下操作长期记忆

**Settings** — 动态调整 Ollama 地址、模型、压缩策略、记忆后端等

---

## 配置

主配置文件：`context_distiller/config/default.yaml`

```yaml
# LLM / VLM 推理服务
llm_server:
  base_url: "http://172.16.10.201:11434"
  model_text: "qwen2.5:7b"           # 文本推理 & L3 摘要
  model_vision: "qwen2.5vl:7b"       # 视觉语言模型
  model_ocr: "deepseek-ocr:latest"   # OCR 专用模型

# 向量嵌入
embedding_server:
  provider: "ollama"
  model: "bge-m3"

# Prompt Distiller
prompt_distiller:
  profile: "balanced"                 # speed / selective / balanced / accuracy
  text:
    default_level: "L2"              # L0 / L1 / L2 / L3
    onnx_quantization: "int8"
  document:
    default_backend: "deepseek"      # deepseek / markitdown / docling / pymupdf

# Memory Gateway
memory_gateway:
  session_memory:
    micro_compact:
      enabled: true
      keep_recent: 3                 # 保留最近 N 个 tool_result
    auto_compact:
      enabled: true
      token_threshold: 50000         # 超过此阈值触发自动压缩
      transcript_dir: ".transcripts/"
      summary_max_tokens: 2000
    summarize:
      strategy: "lingua"             # lingua / llm / fallback
      lingua_level: "L2"
      lingua_rate: 0.3

  user_memory:
    backend: "openclaw"              # openclaw / mem0
    openclaw:
      db_path: "memory.db"
      search_weights:
        vector: 0.7                  # 向量搜索权重
        fts: 0.3                     # 全文检索权重
```

---

## 项目结构

```
context_compress/
├── context_distiller/                    # 主 Python 包
│   ├── api/
│   │   ├── server/app.py                # FastAPI 服务 (所有端点)
│   │   └── cli/main.py                  # CLI 入口
│   ├── prompt_distiller/                # 无状态压缩引擎
│   │   ├── engine.py                    # 编排器：类型检测 → 路由 → 处理 → 聚合
│   │   ├── router.py                    # 硬件感知路由 (Profile → Processor)
│   │   └── processors/                  # 9 个处理器实现
│   │       ├── text/                    # L0 Regex / L1 Selective / L2 LLMLingua / L3 Summarizer
│   │       ├── document/                # MarkItDown / Docling / DeepSeek-OCR / VLM-Direct
│   │       └── vision/                  # OpenCV 降维去重 / CLIP ROI 抠图
│   ├── memory_gateway/                  # 有状态记忆系统
│   │   ├── session/compactor.py         # 三层会话压缩器
│   │   ├── user_memory/manager.py       # 长期记忆管理 (可插拔后端接口)
│   │   └── backends/                    # OpenClaw (SQLite) / Mem0 / Custom
│   ├── schemas/                         # Pydantic 数据模型
│   ├── infra/                           # 硬件探测、环境管理
│   ├── sdk/client.py                    # Python SDK
│   └── config/default.yaml              # 全局配置
├── context_distiller_ui/                # React + TypeScript 前端
│   ├── src/App.tsx                      # 主组件
│   └── src/lib/api.ts                   # API 客户端
├── docs/                                # 文档
├── setup.py                             # 包配置 (支持 pip install -e ".[gpu/mem0/full]")
├── requirements.txt                     # 核心依赖
└── README.md
```

---

## 技术栈

| 层 | 技术 |
|-----|------|
| 后端框架 | FastAPI + Uvicorn + Pydantic 2.0 |
| LLM 推理 | Ollama (Qwen2.5-7B / Qwen2.5-VL / DeepSeek-OCR) |
| 文本压缩 | LLMLingua-2 (ONNX) / GPT-2 / Regex |
| 向量嵌入 | BGE-M3 (via Ollama) |
| 文档提取 | MarkItDown / Docling / PyMuPDF |
| 图像处理 | OpenCV + CLIP (ROI) |
| 长期记忆 | SQLite + FTS5 + sqlite-vec / Mem0 |
| 前端 | React 19 + TypeScript + Vite |
| CLI | Click 8.0 |

---

## 相关论文与资源

| 主题 | 链接 |
|------|------|
| LLMLingua-2 (Token 级压缩) | [arXiv:2403.12968](https://arxiv.org/abs/2403.12968) |
| SelectiveContext (自信息量过滤) | [arXiv:2310.06201](https://arxiv.org/abs/2310.06201) |
| Lost in the Middle (长上下文注意力) | [arXiv:2307.03172](https://arxiv.org/abs/2307.03172) |
| MemGPT / Letta (Agent 记忆架构) | [arXiv:2310.08560](https://arxiv.org/abs/2310.08560) |
| CLIP (视觉-语言对比学习) | [arXiv:2103.00020](https://arxiv.org/abs/2103.00020) |
| Mem0 | [docs.mem0.ai](https://docs.mem0.ai) |
| LLMLingua GitHub | [github.com/microsoft/LLMLingua](https://github.com/microsoft/LLMLingua) |
| MarkItDown | [github.com/microsoft/markitdown](https://github.com/microsoft/markitdown) |

---

## License

MIT License

欢迎通过 Issue / PR 提交反馈与改进建议。
