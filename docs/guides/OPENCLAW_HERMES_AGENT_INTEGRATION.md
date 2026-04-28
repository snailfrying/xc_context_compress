# OpenClaw & Hermes Agent 架构适配教程

> **将 Context Distiller v2.0 集成到 OpenClaw / Hermes Agent 及类似 Agent 架构中，用于 API 服务的完整指南**

---

## 目录

- [1. 概述与背景](#1-概述与背景)
  - [1.1 什么是 OpenClaw 记忆架构](#11-什么是-openclaw-记忆架构)
  - [1.2 什么是 Hermes Agent 架构](#12-什么是-hermes-agent-架构)
  - [1.3 为什么需要 Context Distiller 适配](#13-为什么需要-context-distiller-适配)
  - [1.4 整体架构总览](#14-整体架构总览)
- [2. 环境准备与安装](#2-环境准备与安装)
  - [2.1 前置条件](#21-前置条件)
  - [2.2 安装 Context Distiller](#22-安装-context-distiller)
  - [2.3 启动 Ollama 推理服务](#23-启动-ollama-推理服务)
  - [2.4 验证安装](#24-验证安装)
- [3. 核心概念映射](#3-核心概念映射)
  - [3.1 OpenClaw 概念与 Context Distiller 对应关系](#31-openclaw-概念与-context-distiller-对应关系)
  - [3.2 Hermes Agent 概念与 Context Distiller 对应关系](#32-hermes-agent-概念与-context-distiller-对应关系)
  - [3.3 多租户隔离模型](#33-多租户隔离模型)
- [4. 适配方案一：REST API 网关模式](#4-适配方案一rest-api-网关模式)
  - [4.1 架构图](#41-架构图)
  - [4.2 启动 Context Distiller API 服务](#42-启动-context-distiller-api-服务)
  - [4.3 Hermes Agent 调用上下文压缩](#43-hermes-agent-调用上下文压缩)
  - [4.4 Hermes Agent 调用记忆系统](#44-hermes-agent-调用记忆系统)
  - [4.5 Hermes Agent 完整会话流程](#45-hermes-agent-完整会话流程)
- [5. 适配方案二：Python SDK 嵌入模式](#5-适配方案二python-sdk-嵌入模式)
  - [5.1 架构图](#51-架构图)
  - [5.2 创建 Agent 上下文管理器](#52-创建-agent-上下文管理器)
  - [5.3 集成 Hermes Agent Tool Calling](#53-集成-hermes-agent-tool-calling)
  - [5.4 完整 Agent Loop 实现](#54-完整-agent-loop-实现)
- [6. 适配方案三：OpenAI 兼容代理模式](#6-适配方案三openai-兼容代理模式)
  - [6.1 架构图](#61-架构图)
  - [6.2 透明代理层实现](#62-透明代理层实现)
  - [6.3 集成到现有 Agent 框架](#63-集成到现有-agent-框架)
- [7. OpenClaw 记忆系统深度集成](#7-openclaw-记忆系统深度集成)
  - [7.1 记忆生命周期管理](#71-记忆生命周期管理)
  - [7.2 六种记忆分类实战](#72-六种记忆分类实战)
  - [7.3 混合检索调优](#73-混合检索调优)
  - [7.4 自定义记忆后端](#74-自定义记忆后端)
- [8. 会话压缩与 Agent 记忆协同](#8-会话压缩与-agent-记忆协同)
  - [8.1 三层压缩机制详解](#81-三层压缩机制详解)
  - [8.2 会话摘要自动存入长期记忆](#82-会话摘要自动存入长期记忆)
  - [8.3 跨会话知识传递](#83-跨会话知识传递)
  - [8.4 压缩策略选择与调优](#84-压缩策略选择与调优)
- [9. 多模态 Agent 支持](#9-多模态-agent-支持)
  - [9.1 文档附件处理](#91-文档附件处理)
  - [9.2 图像理解集成](#92-图像理解集成)
  - [9.3 多模态 Tool Calling](#93-多模态-tool-calling)
- [10. 生产部署最佳实践](#10-生产部署最佳实践)
  - [10.1 API 服务配置](#101-api-服务配置)
  - [10.2 性能调优](#102-性能调优)
  - [10.3 监控与可观测性](#103-监控与可观测性)
  - [10.4 高可用部署](#104-高可用部署)
- [11. 完整项目示例](#11-完整项目示例)
  - [11.1 Hermes Agent + Context Distiller 客服系统](#111-hermes-agent--context-distiller-客服系统)
  - [11.2 多 Agent 协作知识库系统](#112-多-agent-协作知识库系统)
- [12. 常见问题与排障](#12-常见问题与排障)
- [13. 附录：API 快速参考](#13-附录api-快速参考)

---

## 1. 概述与背景

### 1.1 什么是 OpenClaw 记忆架构

OpenClaw 是 Context Distiller v2.0 内置的**本地优先**长期记忆后端，其核心设计理念是：

- **数据不出网**：所有记忆存储在本地 SQLite 数据库中，适合隐私敏感场景
- **混合检索**：FTS5 全文索引 (30%) + BGE-M3 向量搜索 (70%) 双轨融合
- **多租户隔离**：通过 `(user_id, agent_id)` 复合键实现租户级别的数据隔离
- **六种记忆分类**：`fact` / `preference` / `rule` / `profile` / `note` / `system`

OpenClaw 的存储模型：

```
┌─────────────────────────────────────────────────┐
│                  SQLite 数据库                     │
│                                                   │
│  memories 表                                      │
│  ├── id (主键)                                    │
│  ├── user_id + agent_id (复合隔离键)               │
│  ├── category (fact/preference/rule/...)           │
│  ├── content (记忆内容)                            │
│  ├── source (来源标记)                             │
│  ├── metadata (JSON 扩展字段)                      │
│  ├── embedding (向量, BLOB)                        │
│  └── created_at / updated_at (时间戳)              │
│                                                   │
│  memories_fts (FTS5 全文索引虚拟表)                 │
│  memories_vec (sqlite-vec 向量索引虚拟表)           │
└─────────────────────────────────────────────────┘
```

### 1.2 什么是 Hermes Agent 架构

Hermes Agent 是基于 NousResearch Hermes 模型系列（如 Hermes-2-Pro、Hermes-3 等）构建的 Agent 架构范式。其核心特征包括：

- **结构化 Tool Calling**：使用 `<tool_call>` 标签定义工具调用，支持 JSON Schema 参数
- **System Prompt 驱动**：通过精心设计的 System Prompt 控制 Agent 行为
- **多轮 ReAct 循环**：思考 (Think) → 行动 (Act) → 观察 (Observe) → 回复 (Reply) 的循环模式
- **函数注册机制**：通过 `tools` 参数在 Chat Completions API 中注册可调用函数

典型的 Hermes Agent 工具调用格式：

```json
{
  "role": "assistant",
  "content": null,
  "tool_calls": [
    {
      "id": "call_abc123",
      "type": "function",
      "function": {
        "name": "memory_search",
        "arguments": "{\"query\": \"用户偏好\", \"top_k\": 3}"
      }
    }
  ]
}
```

### 1.3 为什么需要 Context Distiller 适配

在实际 Agent 系统中，你会面临以下痛点：

| 痛点 | Context Distiller 的解决方案 |
|------|---------------------------|
| Agent 多轮对话 Token 爆炸 | 三层会话压缩 (Micro/Auto/Manual) 自动管理 |
| 长文档/多附件超出窗口 | 四档压缩 (L0-L3) + 文档管道 + 智能分块 |
| Agent 跨会话"失忆" | OpenClaw 长期记忆持久化 + 自动召回 |
| 多 Agent 记忆冲突 | `(user_id, agent_id)` 多租户隔离 |
| 记忆检索不精准 | 向量 + 全文混合检索，可调权重 |
| LLM 推理成本高 | 压缩后 Token 直接减少 40-80%，降低 API 费用 |

### 1.4 整体架构总览

```
┌────────────────────────────────────────────────────────────────┐
│                        客户端 / 前端                            │
│                  (Web / App / CLI / 第三方系统)                  │
└────────────────────────┬───────────────────────────────────────┘
                         │ HTTP / WebSocket
┌────────────────────────▼───────────────────────────────────────┐
│              你的 API 服务 (Hermes Agent 宿主)                   │
│                                                                 │
│  ┌─────────────────┐  ┌──────────────────┐  ┌───────────────┐  │
│  │  Agent Router    │  │  Tool Executor    │  │  Session Mgr  │  │
│  │  (路由/分发)     │  │  (工具执行器)      │  │  (会话管理)   │  │
│  └────────┬────────┘  └────────┬─────────┘  └──────┬────────┘  │
│           │                    │                     │           │
│  ┌────────▼────────────────────▼─────────────────────▼────────┐ │
│  │              Context Distiller v2.0 (SDK / API)             │ │
│  │                                                             │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │ │
│  │  │ Prompt        │  │ Session      │  │ User Memory      │  │ │
│  │  │ Distiller     │  │ Compactor    │  │ Manager          │  │ │
│  │  │ (上下文压缩)  │  │ (会话压缩)   │  │ (长期记忆)       │  │ │
│  │  └──────────────┘  └──────────────┘  └──────────────────┘  │ │
│  └─────────────────────────────────────────────────────────────┘ │
└────────────────────────┬───────────────────────────────────────┘
                         │
              ┌──────────▼──────────┐
              │    Ollama Server     │
              │  qwen2.5:7b (文本)   │
              │  bge-m3 (Embedding)  │
              └─────────────────────┘
```

---

## 2. 环境准备与安装

### 2.1 前置条件

| 组件 | 版本要求 | 用途 |
|------|---------|------|
| Python | 3.9+ | 运行时 |
| Ollama | 最新版 | LLM 推理 + 向量嵌入 |
| Node.js | 18+ (可选) | 前端 UI |

### 2.2 安装 Context Distiller

```bash
# 克隆项目
git clone <your-repo-url> context_compress
cd context_compress

# 创建虚拟环境
python -m venv .venv
# Windows PowerShell:
.\.venv\Scripts\activate
# macOS / Linux:
# source .venv/bin/activate

# 安装核心依赖
pip install -r requirements.txt
pip install -e .

# 可选：GPU 加速
# pip install -e ".[gpu]"

# 可选：Mem0 集成
# pip install -e ".[mem0]"

# 可选：全部功能
# pip install -e ".[full]"
```

### 2.3 启动 Ollama 推理服务

```bash
# 拉取必要模型
ollama pull qwen2.5:7b        # 文本推理 & 摘要 (必需)
ollama pull bge-m3             # 向量嵌入 (记忆搜索必需)

# 可选模型
ollama pull qwen2.5vl:7b      # 视觉语言模型 (图像理解)
ollama pull deepseek-ocr       # OCR 识别 (文档扫描)

# 确认 Ollama 运行
curl http://localhost:11434/api/tags
```

### 2.4 验证安装

```bash
# 运行安装验证脚本
python verify_installation.py

# 启动 API 服务验证
python -m context_distiller.api.server.app
# 另开终端检查
curl http://localhost:8085/health
# 应返回: {"status": "ok", "version": "2.0.0"}
```

---

## 3. 核心概念映射

### 3.1 OpenClaw 概念与 Context Distiller 对应关系

| OpenClaw 概念 | Context Distiller 实现 | 说明 |
|--------------|----------------------|------|
| Memory Store | `UserMemoryManager` + `OpenClawBackend` | 长期记忆存储层 |
| Memory File (.md) | `MemoryChunk.source` 字段 | 来源追溯 |
| Silent Turn | `SessionCompactor.micro_compact()` | 旧 tool_result 替换为占位符 |
| Dreaming Phase 1 | `SessionCompactor.auto_compact()` | 超阈值自动摘要 |
| Dreaming Phase 2 | 自动存入长期记忆 | compact 摘要持久化 |
| Dreaming Phase 3 | `UserMemoryManager.search()` | 下次会话自动召回 |
| Hybrid Search | `OpenClawBackend._hybrid_fuse()` | 向量 70% + FTS 30% 融合 |
| Multi-tenant | `(user_id, agent_id)` 复合键 | 记忆隔离 |

### 3.2 Hermes Agent 概念与 Context Distiller 对应关系

| Hermes Agent 概念 | Context Distiller 对应 | 集成方式 |
|------------------|----------------------|---------|
| System Prompt | 记忆召回注入 system message | 自动拼接 `memory_hits` 到 system prompt |
| Tool Definition | REST API / SDK 方法 | 注册为 Agent 可调用工具 |
| Tool Call Result | API 响应 / SDK 返回值 | 作为 `tool` role 消息回传 |
| Conversation History | `_sessions[sid]` 会话缓存 | 自动管理 + 三层压缩 |
| Function Calling | `/v1/distill`, `/v1/memory/*` | HTTP 调用或 SDK 直接调用 |
| ReAct Loop | Agent Chat 端点 | `/v1/chat` 已内置完整循环 |

### 3.3 多租户隔离模型

Context Distiller 使用三级隔离键：

```
user_id    ──→ 自然人用户（如: "alice", "bob"）
agent_id   ──→ Agent 实例（如: "customer_service", "code_assistant"）
session_id ──→ 会话生命周期（如: "sess_20260428_001"）
```

隔离效果示意：

```
alice + customer_service + sess_001  →  独立记忆空间 + 独立会话
alice + code_assistant   + sess_002  →  独立记忆空间 + 独立会话
bob   + customer_service + sess_003  →  独立记忆空间 + 独立会话
```

同一 `user_id` 下不同 `agent_id` 的记忆**互相独立**，不会交叉污染。

---

## 4. 适配方案一：REST API 网关模式

> **适用场景**：你的 Agent 系统是任意语言 (Python/Node.js/Go/Java 等)，通过 HTTP 调用 Context Distiller 作为独立微服务。

### 4.1 架构图

```
┌──────────────┐    HTTP     ┌──────────────────────────┐
│ Hermes Agent │ ──────────→ │ Context Distiller API    │
│ (任意语言)    │ ←────────── │ http://localhost:8085    │
│              │             │                          │
│ tool_call:   │             │ /v1/distill   (压缩)      │
│  - distill   │             │ /v1/chat      (对话)      │
│  - memory_*  │             │ /v1/memory/*  (记忆CRUD)  │
│  - compact   │             │ /v1/settings  (配置)      │
└──────────────┘             └──────────────────────────┘
```

### 4.2 启动 Context Distiller API 服务

```bash
# 方式一：直接启动
python -m context_distiller.api.server.app
# 默认监听 http://0.0.0.0:8085

# 方式二：指定端口
CONTEXT_DISTILLER_PORT=8080 python -m context_distiller.api.server.app

# 方式三：使用 uvicorn（推荐生产环境）
uvicorn context_distiller.api.server.app:app --host 0.0.0.0 --port 8085 --workers 4
```

### 4.3 Hermes Agent 调用上下文压缩

当 Agent 需要处理长文本或多模态内容时，先调用 `/v1/distill` 压缩再送入 LLM：

**Python 示例（requests）**：

```python
import requests

DISTILLER_URL = "http://localhost:8085"

def compress_context(texts: list, profile: str = "balanced") -> dict:
    """调用 Context Distiller 压缩上下文"""
    resp = requests.post(f"{DISTILLER_URL}/v1/distill", json={
        "data": texts,
        "profile": profile,          # speed / selective / balanced / accuracy
        "compression_rate": 0.4,     # 目标压缩率 (保留 40% 内容)
    })
    resp.raise_for_status()
    return resp.json()

# ---- 在 Hermes Agent 中使用 ----
# 假设用户发送了一段很长的文本
user_message = "请帮我分析以下论文内容：..." + "很长的论文内容..." * 100

# 压缩后再送入 LLM
result = compress_context([user_message])
compressed_text = result["optimized_prompt"][0]["content"]
stats = result["stats"]

print(f"原始 Token: {stats['input_tokens']}")
print(f"压缩后 Token: {stats['output_tokens']}")
print(f"压缩率: {stats['compression_ratio']:.2%}")
print(f"耗时: {stats['latency_ms']:.1f}ms")
```

**Node.js 示例（fetch）**：

```javascript
const DISTILLER_URL = "http://localhost:8085";

async function compressContext(texts, profile = "balanced") {
  const resp = await fetch(`${DISTILLER_URL}/v1/distill`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      data: texts,
      profile: profile,
      compression_rate: 0.4,
    }),
  });
  if (!resp.ok) throw new Error(`Distiller error: ${resp.status}`);
  return resp.json();
}

// 在 Hermes Agent 中使用
const longText = "一段很长的用户输入...".repeat(200);
const result = await compressContext([longText]);
const compressed = result.optimized_prompt[0].content;
console.log(`压缩率: ${(result.stats.compression_ratio * 100).toFixed(1)}%`);
```

**cURL 示例**：

```bash
curl -X POST http://localhost:8085/v1/distill \
  -H "Content-Type: application/json" \
  -d '{
    "data": ["一段需要压缩的很长提示词内容..."],
    "profile": "balanced",
    "compression_rate": 0.4
  }'
```

### 4.4 Hermes Agent 调用记忆系统

将 Context Distiller 的记忆端点注册为 Hermes Agent 的工具：

```python
import requests

DISTILLER_URL = "http://localhost:8085"

# ==========================================
# 1. 存储记忆
# ==========================================
def tool_memory_store(content: str, source: str, category: str = "fact",
                      user_id: str = "default", agent_id: str = "default") -> dict:
    """Hermes Agent 工具: 存储一条记忆到 OpenClaw"""
    resp = requests.post(f"{DISTILLER_URL}/v1/memory/store", json={
        "content": content,
        "source": source,
        "category": category,   # fact / preference / rule / profile / note / system
        "user_id": user_id,
        "agent_id": agent_id,
    })
    return resp.json()

# ==========================================
# 2. 搜索记忆
# ==========================================
def tool_memory_search(query: str, top_k: int = 5,
                       user_id: str = "default", agent_id: str = "default") -> dict:
    """Hermes Agent 工具: 从 OpenClaw 搜索相关记忆"""
    resp = requests.post(f"{DISTILLER_URL}/v1/memory/search", json={
        "query": query,
        "top_k": top_k,
        "user_id": user_id,
        "agent_id": agent_id,
    })
    return resp.json()

# ==========================================
# 3. 更新记忆
# ==========================================
def tool_memory_update(chunk_id: str, content: str,
                       user_id: str = "default", agent_id: str = "default") -> dict:
    """Hermes Agent 工具: 更新已存在的记忆内容"""
    resp = requests.post(f"{DISTILLER_URL}/v1/memory/update", json={
        "chunk_id": chunk_id,
        "content": content,
        "user_id": user_id,
        "agent_id": agent_id,
    })
    return resp.json()

# ==========================================
# 4. 删除记忆
# ==========================================
def tool_memory_forget(chunk_id: str,
                       user_id: str = "default", agent_id: str = "default") -> dict:
    """Hermes Agent 工具: 删除指定记忆"""
    resp = requests.post(f"{DISTILLER_URL}/v1/memory/forget", json={
        "chunk_id": chunk_id,
        "user_id": user_id,
        "agent_id": agent_id,
    })
    return resp.json()

# ==========================================
# 5. 列出记忆
# ==========================================
def tool_memory_list(user_id: str = "default", agent_id: str = "default",
                     category: str = None, limit: int = 50) -> dict:
    """Hermes Agent 工具: 列出所有记忆"""
    payload = {
        "user_id": user_id,
        "agent_id": agent_id,
        "limit": limit,
    }
    if category:
        payload["category"] = category
    resp = requests.post(f"{DISTILLER_URL}/v1/memory/list", json=payload)
    return resp.json()
```

### 4.5 Hermes Agent 完整会话流程

下面展示一个完整的 Hermes Agent 工作流，包含记忆召回、上下文压缩和响应生成：

```python
import requests
import json

DISTILLER_URL = "http://localhost:8085"
OLLAMA_URL = "http://localhost:11434"

class HermesAgentWithDistiller:
    """集成 Context Distiller 的 Hermes Agent"""

    def __init__(self, user_id: str, agent_id: str, model: str = "qwen2.5:7b"):
        self.user_id = user_id
        self.agent_id = agent_id
        self.model = model
        self.session_id = f"sess_{user_id}_{agent_id}"

        # 注册 Agent 可用工具 (OpenAI function calling 格式)
        self.tools = [
            {
                "type": "function",
                "function": {
                    "name": "memory_search",
                    "description": "搜索用户的长期记忆，查找相关的历史信息、偏好和规则",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "搜索关键词"},
                            "top_k": {"type": "integer", "description": "返回结果数", "default": 3},
                        },
                        "required": ["query"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "memory_store",
                    "description": "存储重要信息到用户的长期记忆中",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "content": {"type": "string", "description": "要存储的内容"},
                            "category": {
                                "type": "string",
                                "enum": ["fact", "preference", "rule", "profile", "note"],
                                "description": "记忆分类",
                            },
                        },
                        "required": ["content", "category"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "compress_text",
                    "description": "压缩长文本以减少 Token 消耗",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "text": {"type": "string", "description": "需要压缩的长文本"},
                            "profile": {
                                "type": "string",
                                "enum": ["speed", "balanced", "accuracy"],
                                "default": "balanced",
                            },
                        },
                        "required": ["text"],
                    },
                },
            },
        ]

    def chat(self, user_message: str, files: list = None) -> str:
        """完整的 Agent 对话流程"""

        # ---- Step 1: 自动记忆召回 ----
        memory_context = self._recall_memories(user_message)

        # ---- Step 2: 构建 System Prompt ----
        system_prompt = self._build_system_prompt(memory_context)

        # ---- Step 3: 处理文件附件（压缩） ----
        file_context = ""
        if files:
            file_context = self._process_files(files)

        # ---- Step 4: 构建完整的用户消息 ----
        full_message = user_message
        if file_context:
            full_message += f"\n\n[附件内容]:\n{file_context}"

        # ---- Step 5: 调用 LLM (带 Tool Calling) ----
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": full_message},
        ]

        response = self._call_llm(messages)

        # ---- Step 6: 处理 Tool Calls (ReAct 循环) ----
        while response.get("tool_calls"):
            for tool_call in response["tool_calls"]:
                tool_result = self._execute_tool(tool_call)
                messages.append({
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [tool_call],
                })
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call["id"],
                    "content": json.dumps(tool_result, ensure_ascii=False),
                })
            response = self._call_llm(messages)

        return response.get("content", "")

    def _recall_memories(self, query: str) -> list:
        """从 OpenClaw 召回相关记忆"""
        try:
            resp = requests.post(f"{DISTILLER_URL}/v1/memory/search", json={
                "query": query,
                "top_k": 5,
                "user_id": self.user_id,
                "agent_id": self.agent_id,
            })
            data = resp.json()
            return data.get("chunks", [])
        except Exception as e:
            print(f"记忆召回失败: {e}")
            return []

    def _build_system_prompt(self, memories: list) -> str:
        """构建包含记忆上下文的 System Prompt"""
        base = (
            "You are a helpful AI assistant powered by Hermes architecture. "
            "You can use tools to search and store memories. "
            "Answer in the same language as the user."
        )

        if memories:
            mem_lines = []
            for m in memories:
                mem_lines.append(f"- [{m['category']}] {m['content']} (来源: {m['source']})")
            base += f"\n\n已知的用户相关记忆:\n" + "\n".join(mem_lines)

        return base

    def _process_files(self, files: list) -> str:
        """通过 Distiller 压缩文件内容"""
        try:
            resp = requests.post(f"{DISTILLER_URL}/v1/distill", json={
                "data": files,
                "profile": "balanced",
            })
            data = resp.json()
            parts = []
            for item in data.get("optimized_prompt", []):
                content = item.get("content", {})
                if isinstance(content, dict):
                    parts.append(content.get("text", ""))
                else:
                    parts.append(str(content))
            return "\n".join(parts)
        except Exception as e:
            print(f"文件处理失败: {e}")
            return ""

    def _call_llm(self, messages: list) -> dict:
        """调用 Ollama LLM"""
        resp = requests.post(f"{OLLAMA_URL}/v1/chat/completions", json={
            "model": self.model,
            "messages": messages,
            "tools": self.tools,
            "temperature": 0.7,
        })
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]

    def _execute_tool(self, tool_call: dict) -> dict:
        """执行工具调用"""
        func_name = tool_call["function"]["name"]
        args = json.loads(tool_call["function"]["arguments"])

        if func_name == "memory_search":
            return self._tool_memory_search(**args)
        elif func_name == "memory_store":
            return self._tool_memory_store(**args)
        elif func_name == "compress_text":
            return self._tool_compress_text(**args)
        else:
            return {"error": f"Unknown tool: {func_name}"}

    def _tool_memory_search(self, query: str, top_k: int = 3) -> dict:
        resp = requests.post(f"{DISTILLER_URL}/v1/memory/search", json={
            "query": query, "top_k": top_k,
            "user_id": self.user_id, "agent_id": self.agent_id,
        })
        return resp.json()

    def _tool_memory_store(self, content: str, category: str = "fact") -> dict:
        resp = requests.post(f"{DISTILLER_URL}/v1/memory/store", json={
            "content": content,
            "source": f"agent_chat:{self.session_id}",
            "category": category,
            "user_id": self.user_id,
            "agent_id": self.agent_id,
        })
        return resp.json()

    def _tool_compress_text(self, text: str, profile: str = "balanced") -> dict:
        resp = requests.post(f"{DISTILLER_URL}/v1/distill", json={
            "data": [text], "profile": profile,
        })
        data = resp.json()
        return {
            "compressed": data["optimized_prompt"][0]["content"],
            "stats": data["stats"],
        }


# ==========================================
# 使用示例
# ==========================================
if __name__ == "__main__":
    agent = HermesAgentWithDistiller(
        user_id="alice",
        agent_id="customer_service",
        model="qwen2.5:7b",
    )

    # 第一轮对话
    reply = agent.chat("你好，我是 Alice，我喜欢 Python 编程")
    print(f"Agent: {reply}")

    # 第二轮对话 (Agent 应能回忆起 Alice 的偏好)
    reply = agent.chat("你还记得我的编程偏好吗？")
    print(f"Agent: {reply}")

    # 带文件附件的对话
    reply = agent.chat("帮我分析这份文档", files=["uploads/report.pdf"])
    print(f"Agent: {reply}")
```

---

## 5. 适配方案二：Python SDK 嵌入模式

> **适用场景**：你的 Agent 系统是 Python 编写的，希望直接在进程内调用 Context Distiller，无需额外的 HTTP 服务。

### 5.1 架构图

```
┌──────────────────────────────────────────────────┐
│              Python 进程 (Agent 宿主)              │
│                                                    │
│  ┌──────────────┐    直接函数调用                   │
│  │ Hermes Agent │ ──────────────→ DistillerClient  │
│  │              │ ←────────────── UserMemoryManager │
│  │              │                 SessionCompactor  │
│  └──────────────┘                                  │
└────────────────────────┬───────────────────────────┘
                         │ HTTP (嵌入/推理)
              ┌──────────▼──────────┐
              │    Ollama Server     │
              └─────────────────────┘
```

### 5.2 创建 Agent 上下文管理器

```python
from context_distiller.sdk.client import DistillerClient
from context_distiller.memory_gateway.user_memory.manager import UserMemoryManager
from context_distiller.memory_gateway.session.compactor import SessionCompactor
from context_distiller.schemas.memory import MemoryChunk


class AgentContextManager:
    """Agent 上下文管理器 — 封装 Context Distiller 核心能力

    职责:
    1. 用户消息预处理 (压缩长文本/文档)
    2. 记忆召回 (自动搜索相关记忆注入 system prompt)
    3. 记忆存储 (从对话中提取重要信息持久化)
    4. 会话压缩 (管理对话历史，防止 Token 膨胀)
    """

    def __init__(
        self,
        user_id: str,
        agent_id: str,
        session_id: str = None,
        ollama_url: str = "http://localhost:11434",
        embedding_model: str = "bge-m3",
        profile: str = "balanced",
    ):
        self.user_id = user_id
        self.agent_id = agent_id
        self.session_id = session_id or f"sess_{user_id}_{agent_id}"

        # 初始化 Prompt Distiller (无状态压缩)
        self.distiller = DistillerClient(
            profile=profile,
            config={
                "llm_server": {
                    "base_url": ollama_url,
                    "model_text": "qwen2.5:7b",
                }
            },
            user_id=user_id,
            agent_id=agent_id,
            session_id=self.session_id,
        )

        # 初始化 Memory Manager (OpenClaw 后端)
        self.memory_mgr = UserMemoryManager({
            "backend": "openclaw",
            "openclaw": {
                "db_path": "memory.db",
                "embedding_provider": "ollama",
                "embedding_base_url": ollama_url,
                "embedding_model": embedding_model,
            },
        })

        # 初始化 Session Compactor (三层压缩)
        self.compactor = SessionCompactor(
            {
                "transcript_dir": ".transcripts",
                "micro_compact": {"enabled": True, "keep_recent": 3},
                "auto_compact": {"enabled": True, "token_threshold": 50000},
                "summarize": {
                    "strategy": "lingua",
                    "lingua_level": "L2",
                    "lingua_rate": 0.3,
                    "llm_base_url": f"{ollama_url}/v1",
                    "llm_model": "qwen2.5:7b",
                },
            },
            memory_mgr=self.memory_mgr,
        )

    def compress(self, texts: list, profile: str = None) -> dict:
        """压缩文本/文档列表"""
        return self.distiller.process(data=texts)

    def recall(self, query: str, top_k: int = 5) -> list:
        """召回相关记忆"""
        result = self.memory_mgr.search(
            query, top_k=top_k,
            user_id=self.user_id, agent_id=self.agent_id,
        )
        return [
            {
                "id": c.id,
                "content": c.content,
                "source": c.source,
                "category": c.category,
            }
            for c in result.chunks
        ]

    def remember(self, content: str, category: str = "fact", source: str = "") -> str:
        """存储一条新记忆"""
        return self.memory_mgr.store(
            content=content,
            source=source or f"chat:{self.session_id}",
            category=category,
            user_id=self.user_id,
            agent_id=self.agent_id,
        )

    def compact_session(self, messages: list) -> list:
        """压缩会话历史"""
        # L1: 微压缩 (替换旧 tool_result)
        compacted = self.compactor.micro_compact(messages)
        # L2: 自动压缩 (超阈值时生成摘要)
        compacted = self.compactor.auto_compact(compacted, self.session_id)
        return compacted

    def build_context(self, user_message: str, history: list = None) -> list:
        """构建完整上下文: 记忆召回 + 历史压缩 + 用户消息

        Returns:
            处理后的 messages 列表，可直接传给 LLM
        """
        # 1. 召回相关记忆
        memories = self.recall(user_message, top_k=3)

        # 2. 构建 system prompt
        system_parts = ["You are a helpful AI assistant. Answer in the same language."]
        if memories:
            mem_text = "\n".join(
                f"- [{m['category']}] {m['content']}" for m in memories
            )
            system_parts.append(f"\nRelevant user memories:\n{mem_text}")

        # 3. 压缩历史消息
        msgs = [{"role": "system", "content": "\n".join(system_parts)}]
        if history:
            compacted = self.compact_session(history)
            msgs.extend(compacted)

        # 4. 追加当前用户消息
        msgs.append({"role": "user", "content": user_message})

        return msgs
```

### 5.3 集成 Hermes Agent Tool Calling

将 Context Distiller 能力注册为 Hermes Agent 的工具函数：

```python
import json
import httpx


class HermesToolRegistry:
    """Hermes Agent 工具注册表 — 将 Context Distiller 封装为 Agent 工具"""

    def __init__(self, ctx: AgentContextManager):
        self.ctx = ctx

    def get_tool_definitions(self) -> list:
        """返回 OpenAI function calling 格式的工具定义列表"""
        return [
            {
                "type": "function",
                "function": {
                    "name": "search_memory",
                    "description": "搜索用户的长期记忆。用于查找用户的偏好、历史决策、项目规则等。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "搜索查询文本",
                            },
                            "category": {
                                "type": "string",
                                "enum": ["fact", "preference", "rule", "profile", "note"],
                                "description": "按分类过滤 (可选)",
                            },
                        },
                        "required": ["query"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "store_memory",
                    "description": "将重要信息存储为长期记忆。用于记住用户偏好、关键决策、项目规则等。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "content": {
                                "type": "string",
                                "description": "要存储的记忆内容",
                            },
                            "category": {
                                "type": "string",
                                "enum": ["fact", "preference", "rule", "profile", "note"],
                                "description": "记忆分类",
                                "default": "fact",
                            },
                        },
                        "required": ["content"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "compress_content",
                    "description": "压缩长文本内容以节省 Token。当输入超过 2000 字符时建议使用。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "text": {
                                "type": "string",
                                "description": "需要压缩的长文本",
                            },
                        },
                        "required": ["text"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "list_memories",
                    "description": "列出用户的所有记忆或按分类筛选。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "category": {
                                "type": "string",
                                "enum": ["fact", "preference", "rule", "profile", "note", "system"],
                                "description": "按分类过滤 (可选)",
                            },
                        },
                    },
                },
            },
        ]

    def execute(self, tool_name: str, arguments: dict) -> str:
        """执行工具调用并返回 JSON 字符串结果"""
        handlers = {
            "search_memory": self._search_memory,
            "store_memory": self._store_memory,
            "compress_content": self._compress_content,
            "list_memories": self._list_memories,
        }

        handler = handlers.get(tool_name)
        if not handler:
            return json.dumps({"error": f"Unknown tool: {tool_name}"})

        result = handler(**arguments)
        return json.dumps(result, ensure_ascii=False)

    def _search_memory(self, query: str, category: str = None) -> dict:
        memories = self.ctx.recall(query, top_k=5)
        if category:
            memories = [m for m in memories if m["category"] == category]
        return {"memories": memories, "count": len(memories)}

    def _store_memory(self, content: str, category: str = "fact") -> dict:
        chunk_id = self.ctx.remember(content, category=category)
        return {"status": "stored", "chunk_id": chunk_id}

    def _compress_content(self, text: str) -> dict:
        result = self.ctx.compress([text])
        return {
            "compressed": result.optimized_prompt[0]["content"],
            "ratio": result.stats.compression_ratio,
        }

    def _list_memories(self, category: str = None) -> dict:
        result = self.ctx.memory_mgr.list_memories(
            user_id=self.ctx.user_id,
            agent_id=self.ctx.agent_id,
            category=category,
        )
        return {
            "memories": [
                {"id": c.id, "content": c.content, "category": c.category, "source": c.source}
                for c in result.chunks
            ],
            "total": result.total,
        }
```

### 5.4 完整 Agent Loop 实现

```python
import httpx
import json


class HermesAgentLoop:
    """完整的 Hermes Agent 循环，集成 Context Distiller"""

    def __init__(
        self,
        user_id: str,
        agent_id: str,
        model: str = "qwen2.5:7b",
        ollama_url: str = "http://localhost:11434",
        max_tool_rounds: int = 5,
    ):
        self.model = model
        self.ollama_url = ollama_url
        self.max_tool_rounds = max_tool_rounds
        self.history = []

        # 初始化上下文管理器和工具注册表
        self.ctx = AgentContextManager(
            user_id=user_id,
            agent_id=agent_id,
            ollama_url=ollama_url,
        )
        self.tools = HermesToolRegistry(self.ctx)

    def run(self, user_input: str) -> str:
        """执行一次完整的 Agent ReAct 循环

        流程:
        1. 构建上下文 (记忆召回 + 历史压缩)
        2. 调用 LLM
        3. 如果 LLM 返回 tool_calls，执行工具并回传结果
        4. 重复 2-3 直到 LLM 给出最终回复
        5. 将对话存入历史
        """
        # Step 1: 构建上下文
        messages = self.ctx.build_context(user_input, self.history)

        # Step 2-4: ReAct 循环
        for _ in range(self.max_tool_rounds):
            response = self._call_llm(messages)

            # 没有工具调用 → 最终回复
            if not response.get("tool_calls"):
                reply = response.get("content", "")
                # 更新历史
                self.history.append({"role": "user", "content": user_input})
                self.history.append({"role": "assistant", "content": reply})
                return reply

            # 有工具调用 → 执行并继续
            messages.append({
                "role": "assistant",
                "content": response.get("content"),
                "tool_calls": response["tool_calls"],
            })

            for tc in response["tool_calls"]:
                func_name = tc["function"]["name"]
                args = json.loads(tc["function"]["arguments"])
                result = self.tools.execute(func_name, args)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": result,
                })

        return "抱歉，工具调用轮次已达上限，请重新提问。"

    def _call_llm(self, messages: list) -> dict:
        """调用 Ollama Chat Completions API"""
        with httpx.Client(timeout=120.0) as client:
            resp = client.post(
                f"{self.ollama_url}/v1/chat/completions",
                json={
                    "model": self.model,
                    "messages": messages,
                    "tools": self.tools.get_tool_definitions(),
                    "temperature": 0.7,
                },
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]


# ==========================================
# 使用示例
# ==========================================
if __name__ == "__main__":
    agent = HermesAgentLoop(
        user_id="alice",
        agent_id="hermes_assistant",
    )

    # 多轮对话
    print(agent.run("你好！我叫 Alice，我是一名后端工程师，主要用 Python 和 Go"))
    print(agent.run("我最近在做一个微服务项目，用的 FastAPI 框架"))
    print(agent.run("你还记得我的技术栈吗？"))
```

---

## 6. 适配方案三：OpenAI 兼容代理模式

> **适用场景**：你希望在不修改现有 Agent 代码的情况下，透明地插入上下文压缩和记忆管理能力。

### 6.1 架构图

```
┌──────────────┐              ┌──────────────────────┐              ┌───────────┐
│ Hermes Agent │  OpenAI API  │ Context Distiller    │  Ollama API  │  Ollama   │
│ (不感知压缩)  │ ────────────→│ 透明代理层            │ ────────────→│  Server   │
│              │ ←────────────│                      │ ←────────────│           │
│              │   标准响应    │ 1. 拦截请求           │   原始响应    │           │
│              │              │ 2. 压缩长消息          │              │           │
│              │              │ 3. 注入记忆            │              │           │
│              │              │ 4. 转发到 Ollama       │              │           │
│              │              │ 5. 返回响应            │              │           │
└──────────────┘              └──────────────────────┘              └───────────┘
```

### 6.2 透明代理层实现

```python
"""
Context Distiller 透明代理层

将 Context Distiller 作为 OpenAI 兼容的代理服务器，
在 Agent 和 LLM 之间透明地插入上下文压缩和记忆管理。

启动: uvicorn proxy_server:app --port 8090
Agent 只需将 base_url 改为 http://localhost:8090/v1
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import httpx
import json

from context_distiller.sdk.client import DistillerClient
from context_distiller.memory_gateway.user_memory.manager import UserMemoryManager
from context_distiller.memory_gateway.session.compactor import SessionCompactor

app = FastAPI(title="Context Distiller Proxy")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# 配置
OLLAMA_URL = "http://localhost:11434"
COMPRESS_THRESHOLD = 2000  # 超过此字符数的消息触发压缩

# 初始化组件
memory_mgr = UserMemoryManager({
    "backend": "openclaw",
    "openclaw": {
        "db_path": "memory.db",
        "embedding_provider": "ollama",
        "embedding_base_url": OLLAMA_URL,
        "embedding_model": "bge-m3",
    },
})

distiller = DistillerClient(profile="balanced", config={
    "llm_server": {"base_url": OLLAMA_URL, "model_text": "qwen2.5:7b"},
})

compactor = SessionCompactor({
    "transcript_dir": ".transcripts",
    "micro_compact": {"enabled": True, "keep_recent": 3},
    "auto_compact": {"enabled": True, "token_threshold": 50000},
    "summarize": {"strategy": "lingua", "lingua_level": "L2"},
}, memory_mgr=memory_mgr)


@app.post("/v1/chat/completions")
async def proxy_chat_completions(request: Request):
    """透明代理 Chat Completions — 在请求到达 LLM 前自动处理"""
    body = await request.json()
    messages = body.get("messages", [])

    # ---- 1. 自动压缩长消息 ----
    processed_messages = []
    for msg in messages:
        content = msg.get("content", "")
        if isinstance(content, str) and len(content) > COMPRESS_THRESHOLD:
            result = distiller.process(data=[content])
            compressed = result.optimized_prompt[0]["content"]
            processed_messages.append({**msg, "content": compressed})
        else:
            processed_messages.append(msg)

    # ---- 2. 自动注入记忆上下文 ----
    # 从最后一条 user 消息提取查询
    user_msgs = [m for m in processed_messages if m.get("role") == "user"]
    if user_msgs:
        last_user = user_msgs[-1].get("content", "")
        if isinstance(last_user, str) and last_user.strip():
            # 提取 user_id (从 header 或使用默认值)
            user_id = request.headers.get("X-User-Id", "default")
            agent_id = request.headers.get("X-Agent-Id", "default")

            try:
                result = memory_mgr.search(
                    last_user, top_k=3,
                    user_id=user_id, agent_id=agent_id,
                )
                if result.chunks:
                    mem_text = "\n".join(
                        f"- [{c.category}] {c.content}" for c in result.chunks
                    )
                    # 注入到 system 消息
                    if processed_messages and processed_messages[0].get("role") == "system":
                        processed_messages[0]["content"] += f"\n\nUser memories:\n{mem_text}"
                    else:
                        processed_messages.insert(0, {
                            "role": "system",
                            "content": f"User memories:\n{mem_text}",
                        })
            except Exception:
                pass  # 记忆搜索失败不影响主流程

    # ---- 3. 会话压缩 ----
    processed_messages = compactor.micro_compact(processed_messages)

    # ---- 4. 转发到 Ollama ----
    body["messages"] = processed_messages
    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            f"{OLLAMA_URL}/v1/chat/completions",
            json=body,
        )
        return resp.json()


# 透传其他端点
@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def proxy_passthrough(path: str, request: Request):
    """其他请求直接透传到 Ollama"""
    body = await request.body()
    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.request(
            method=request.method,
            url=f"{OLLAMA_URL}/{path}",
            content=body,
            headers={"Content-Type": "application/json"},
        )
        return resp.json()
```

### 6.3 集成到现有 Agent 框架

使用代理模式后，**无需修改任何 Agent 代码**，只需更改 `base_url`：

```python
# ---- 方式一: OpenAI Python SDK ----
from openai import OpenAI

# 将 base_url 指向代理层而非直接指向 Ollama
client = OpenAI(
    base_url="http://localhost:8090/v1",  # Context Distiller 代理
    api_key="not-needed",
)

response = client.chat.completions.create(
    model="qwen2.5:7b",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "一段很长的文本..." * 100},
    ],
    extra_headers={
        "X-User-Id": "alice",       # 传递用户身份
        "X-Agent-Id": "assistant",   # 传递 Agent 身份
    },
)
print(response.choices[0].message.content)

# ---- 方式二: LangChain ----
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(
    base_url="http://localhost:8090/v1",
    model="qwen2.5:7b",
    api_key="not-needed",
)

# ---- 方式三: LlamaIndex ----
from llama_index.llms.openai_like import OpenAILike

llm = OpenAILike(
    api_base="http://localhost:8090/v1",
    model="qwen2.5:7b",
    api_key="not-needed",
)
```

---

## 7. OpenClaw 记忆系统深度集成

### 7.1 记忆生命周期管理

OpenClaw 中一条记忆的完整生命周期：

```
创建 (store) → 检索 (search) → 更新 (update) → [可选] 删除 (forget)
     ↑                                    │
     └────── 会话摘要自动存入 ─────────────┘
```

**生命周期管理示例**：

```python
from context_distiller.memory_gateway.user_memory.manager import UserMemoryManager

mgr = UserMemoryManager({
    "backend": "openclaw",
    "openclaw": {
        "db_path": "memory.db",
        "embedding_provider": "ollama",
        "embedding_base_url": "http://localhost:11434",
        "embedding_model": "bge-m3",
    },
})

USER = "alice"
AGENT = "assistant"

# ---- 1. 创建记忆 ----
chunk_id = mgr.store(
    content="Alice 是高级 Python 工程师，擅长 FastAPI 和微服务架构",
    source="onboarding:2026-04-28",
    category="profile",
    user_id=USER,
    agent_id=AGENT,
)
print(f"Created memory: {chunk_id}")

# ---- 2. 检索记忆 ----
result = mgr.search("Python 工程师", top_k=3, user_id=USER, agent_id=AGENT)
for chunk, score in zip(result.chunks, result.scores):
    print(f"  [{chunk.category}] {chunk.content} (score: {score:.3f})")

# ---- 3. 按分类检索 ----
prefs = mgr.search(
    "偏好", top_k=10,
    user_id=USER, agent_id=AGENT,
    category="preference",
)
print(f"Found {prefs.total} preference memories")

# ---- 4. 更新记忆 ----
mgr.update(
    chunk_id=chunk_id,
    content="Alice 是高级全栈工程师，擅长 Python (FastAPI) 和 Go (Gin)，有 5 年微服务经验",
    user_id=USER,
    agent_id=AGENT,
)

# ---- 5. 列出所有记忆 ----
all_memories = mgr.list_memories(user_id=USER, agent_id=AGENT, limit=100)
print(f"Total memories: {all_memories.total}")

# ---- 6. 删除记忆 ----
mgr.forget(chunk_id=chunk_id, user_id=USER, agent_id=AGENT)
```

### 7.2 六种记忆分类实战

Context Distiller 预定义了 6 种记忆分类，每种有不同的用途：

| 分类 | 用途 | 示例 |
|------|------|------|
| `fact` | 客观事实 | "公司用 PostgreSQL 14 作为主数据库" |
| `preference` | 用户偏好 | "用户喜欢暗色主题，代码风格用 Black 格式化" |
| `rule` | 项目规则/约束 | "所有 API 必须加 JWT 认证，不能用 root 权限" |
| `profile` | 用户画像 | "后端工程师，5 年经验，主语言 Python/Go" |
| `note` | 通用笔记 | "2026-04-28 讨论了新的缓存策略，等待评审" |
| `system` | 系统级信息 | "Agent 配置变更记录" |

**在 Agent 中智能分类存储**：

```python
def auto_categorize_and_store(mgr, content: str, user_id: str, agent_id: str):
    """根据内容自动推断分类并存储"""
    # 简单的规则匹配 (生产中建议用 LLM 辅助分类)
    content_lower = content.lower()

    if any(kw in content_lower for kw in ["喜欢", "偏好", "prefer", "习惯", "主题", "风格"]):
        category = "preference"
    elif any(kw in content_lower for kw in ["规则", "必须", "不能", "禁止", "rule", "must", "cannot"]):
        category = "rule"
    elif any(kw in content_lower for kw in ["工程师", "经验", "职位", "角色", "engineer", "role"]):
        category = "profile"
    elif any(kw in content_lower for kw in ["讨论", "会议", "计划", "待办", "todo"]):
        category = "note"
    else:
        category = "fact"

    chunk_id = mgr.store(
        content=content,
        source=f"auto:{category}",
        category=category,
        user_id=user_id,
        agent_id=agent_id,
    )
    return {"chunk_id": chunk_id, "category": category}
```

### 7.3 混合检索调优

OpenClaw 的核心检索机制是**向量搜索 + 全文搜索的加权融合**。默认权重为向量 70% + FTS 30%：

```yaml
# context_distiller/config/default.yaml
memory_gateway:
  user_memory:
    openclaw:
      search_weights:
        vector: 0.7    # 语义相似度 (通过 BGE-M3 嵌入)
        fts: 0.3       # 关键词匹配 (通过 SQLite FTS5)
```

**何时调整权重**：

| 场景 | 推荐权重 | 原因 |
|------|---------|------|
| 模糊语义搜索 (如 "用户的技术背景") | vector: 0.8, fts: 0.2 | 语义理解更重要 |
| 精确关键词搜索 (如 "PostgreSQL 版本") | vector: 0.3, fts: 0.7 | 关键词精确匹配更重要 |
| 中英文混合场景 | vector: 0.6, fts: 0.4 | FTS 在中文分词上效果稍弱 |
| 通用场景 | vector: 0.7, fts: 0.3 | 默认平衡 |

**通过 API 动态调整**：

```python
import requests

# 读取当前配置
settings = requests.get("http://localhost:8085/v1/settings").json()

# 修改记忆后端为 openclaw (通常已经是默认)
settings["memory_backend"] = "openclaw"

# 应用配置
requests.put("http://localhost:8085/v1/settings", json=settings)
```

### 7.4 自定义记忆后端

如果你有企业自有的知识库系统，可以实现自定义后端：

```python
from context_distiller.memory_gateway.backends.base import MemoryBackend
from context_distiller.schemas.memory import MemoryChunk, SearchResult
from typing import Dict, Optional, List


class MyEnterpriseBackend(MemoryBackend):
    """对接企业知识库的自定义后端

    实现步骤:
    1. 继承 MemoryBackend
    2. 实现所有抽象方法
    3. 在 UserMemoryManager 中注册
    """

    def __init__(self, config: Dict):
        self.api_url = config.get("api_url", "http://knowledge-base:9000")
        self.api_key = config.get("api_key", "")
        # 初始化你的企业知识库客户端...

    def search(
        self, query: str, top_k: int = 5,
        user_id: Optional[str] = None, agent_id: Optional[str] = None,
        category: Optional[str] = None,
    ) -> SearchResult:
        """实现搜索逻辑，调用企业知识库 API"""
        # resp = httpx.post(f"{self.api_url}/search", json={...})
        # 转换为 SearchResult 格式
        return SearchResult(chunks=[], scores=[], total=0)

    def store(
        self, chunk: MemoryChunk,
        user_id: Optional[str] = None, agent_id: Optional[str] = None,
    ) -> str:
        """实现存储逻辑"""
        # resp = httpx.post(f"{self.api_url}/store", json={...})
        return "enterprise_chunk_id"

    def update(
        self, chunk_id: str, content: str,
        user_id: Optional[str] = None, agent_id: Optional[str] = None,
    ) -> bool:
        """实现更新逻辑"""
        return True

    def forget(
        self, chunk_id: str,
        user_id: Optional[str] = None, agent_id: Optional[str] = None,
    ) -> bool:
        """实现删除逻辑"""
        return True

    def get(
        self, source: str,
        user_id: Optional[str] = None, agent_id: Optional[str] = None,
    ) -> Optional[MemoryChunk]:
        """实现按 source 获取逻辑"""
        return None

    def list_memories(
        self,
        user_id: Optional[str] = None, agent_id: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 50, offset: int = 0,
    ) -> SearchResult:
        """实现列表逻辑"""
        return SearchResult(chunks=[], scores=[], total=0)
```

注册自定义后端到 `UserMemoryManager`：

```python
# 修改 context_distiller/memory_gateway/user_memory/manager.py 的 _create_backend 方法
# 添加新的后端类型判断：

def _create_backend(self) -> MemoryBackend:
    backend_type = self.config.get("backend", "openclaw")
    if backend_type == "openclaw":
        return OpenClawBackend(self.config.get("openclaw", {}))
    if backend_type == "mem0":
        from ..backends.mem0_backend import Mem0Backend
        return Mem0Backend(self.config.get("mem0", {}))
    if backend_type == "enterprise":
        from ..backends.enterprise import MyEnterpriseBackend
        return MyEnterpriseBackend(self.config.get("enterprise", {}))
    if backend_type == "custom":
        from ..backends.custom import CustomBackend
        return CustomBackend(self.config.get("custom", {}))
    raise ValueError(f"Unknown memory backend: {backend_type}")
```

---

## 8. 会话压缩与 Agent 记忆协同

### 8.1 三层压缩机制详解

Context Distiller 的 `SessionCompactor` 提供三层渐进式压缩：

```
┌──────────────────────────────────────────────────────────────┐
│                     Agent 对话消息流                           │
│                                                               │
│  msg_1 → msg_2 → ... → msg_N                                │
│                                                               │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ L1 Micro-Compact (始终开启)                             │  │
│  │                                                        │  │
│  │ 策略: 将旧的 tool_result 替换为占位符                    │  │
│  │ 效果: "[Previous: used search_memory]"                  │  │
│  │ 保留: 最近 3 条 tool_result 不压缩                      │  │
│  │ 触发: 每次构建 messages 时自动执行                      │  │
│  └────────────────────────────────────────────────────────┘  │
│                          ↓                                    │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ L2 Auto-Compact (Token > 50K 时触发)                   │  │
│  │                                                        │  │
│  │ 策略:                                                  │  │
│  │   1. 保存完整 transcript 到磁盘                        │  │
│  │   2. 生成会话摘要 (lingua / llm / fallback)            │  │
│  │   3. 用摘要替换所有历史消息                            │  │
│  │   4. 自动将摘要存入长期记忆 (OpenClaw)                 │  │
│  └────────────────────────────────────────────────────────┘  │
│                          ↓                                    │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ L3 Manual (API / 工具主动触发)                         │  │
│  │                                                        │  │
│  │ 由 Agent 或用户主动调用:                               │  │
│  │   - SDK: client.context_compact(messages, session_id)  │  │
│  │   - API: POST /v1/session/compact                      │  │
│  └────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

### 8.2 会话摘要自动存入长期记忆

当 L2 Auto-Compact 触发时，系统会自动将生成的摘要存入 OpenClaw 长期记忆：

```python
# SessionCompactor.auto_compact() 内部逻辑 (简化)

def auto_compact(self, messages, session_id, ...):
    # 估算 Token 数
    total_tokens = self._estimate_tokens(messages)
    if total_tokens < self._ac_threshold:
        return messages  # 未超阈值，不压缩

    # 保存完整 transcript
    self._save_transcript(session_id, messages)

    # 生成摘要 (降级链: lingua → llm → fallback)
    summary = self._summarize(messages, ...)

    # 自动存入长期记忆
    if self.memory_mgr:
        self.memory_mgr.store(
            content=summary,
            source=f"summary:{session_id}",
            category="session_history",
        )

    # 用摘要替换历史消息
    return [{"role": "system", "content": f"Previous conversation summary: {summary}"}]
```

这意味着即使当前会话被压缩，关键信息仍然存储在长期记忆中，可在未来的会话中被召回。

### 8.3 跨会话知识传递

通过 OpenClaw 长期记忆，Agent 可以在不同会话之间传递知识：

```python
# ---- 会话 A (2026-04-28 上午) ----
agent_a = HermesAgentLoop(user_id="alice", agent_id="assistant")
agent_a.run("我们决定使用 Redis 作为缓存层，过期时间设为 1 小时")
# → Agent 存储: fact: "使用 Redis 作为缓存层, TTL=1h"

# ---- 会话 B (2026-04-29 下午, 新会话) ----
agent_b = HermesAgentLoop(user_id="alice", agent_id="assistant")
reply = agent_b.run("我们之前定的缓存方案是什么来着？")
# → Agent 自动召回: "使用 Redis 作为缓存层, TTL=1h"
# → Reply: "之前讨论决定使用 Redis 作为缓存层，过期时间设为 1 小时"
```

### 8.4 压缩策略选择与调优

三种摘要策略的对比：

| 策略 | 压缩质量 | 延迟 | 依赖 | 适用场景 |
|------|---------|------|------|---------|
| `lingua` | 高 | 中 (100-500ms) | LLMLingua-2 模型 | **推荐默认**，兼顾质量与速度 |
| `llm` | 最高 | 高 (2-10s) | Ollama 在线 | 需要最好的摘要质量 |
| `fallback` | 基本 | 极低 (<1ms) | 无 | 离线/无 GPU 环境 |

**通过 API 动态切换**：

```python
import requests

# 读取设置
settings = requests.get("http://localhost:8085/v1/settings").json()

# 切换压缩策略
settings["session_summarize_strategy"] = "llm"    # lingua / llm / fallback
settings["session_summarize_lingua_level"] = "L2"  # L0 / L1 / L2 / L3
settings["session_summarize_lingua_rate"] = 0.3    # 保留率 (0.3 = 保留 30%)
settings["session_token_threshold"] = 30000        # 触发阈值

requests.put("http://localhost:8085/v1/settings", json=settings)
```

---

## 9. 多模态 Agent 支持

### 9.1 文档附件处理

Hermes Agent 处理用户上传的文档时，通过 Distiller 管道自动提取和压缩：

```python
# ---- 通过 REST API 处理文档 ----
import requests

# 1. 上传文件
with open("report.pdf", "rb") as f:
    upload_resp = requests.post(
        "http://localhost:8085/v1/upload",
        files={"file": ("report.pdf", f, "application/pdf")},
    )
    saved_path = upload_resp.json()["path"]

# 2. 压缩文档内容
distill_resp = requests.post("http://localhost:8085/v1/distill", json={
    "data": [saved_path],
    "profile": "balanced",
    "document_backend": "markitdown",  # markitdown / docling / deepseek / pymupdf
})

result = distill_resp.json()
# result["optimized_prompt"][0]["content"]["text"]   → 提取的全文
# result["optimized_prompt"][0]["content"]["chunks"]  → 分块压缩结果

# 3. 将压缩后的内容发给 Agent
for chunk in result["optimized_prompt"][0]["content"]["chunks"]:
    print(f"原始: {chunk['text'][:50]}...")
    print(f"压缩: {chunk['compressed'][:50]}...")
```

文档提取后端选择指南：

| 后端 | 适合文档 | 特点 |
|------|---------|------|
| `markitdown` (微软) | DOCX, XLSX, PPTX, HTML | 通用格式首选，Office 文档效果好 |
| `docling` (IBM) | 复杂排版 PDF, 表格密集型 | 论文、技术报告 |
| `pymupdf` | 通用 PDF | 速度快，适合简单 PDF |
| `deepseek` | 扫描件, 手写体, 截图 | OCR 场景首选 |

### 9.2 图像理解集成

Context Distiller 支持两种图像处理模式：

```python
import requests
import base64

# ---- Pixel 模式: 保留视觉信息，缩放后作为 Base64 发送 ----
distill_resp = requests.post("http://localhost:8085/v1/distill", json={
    "data": ["uploads/screenshot.png"],
    "vision_mode": "pixel",      # 保留原始图像（缩放至 ≤1024px）
})

# ---- Semantic 模式: 转换为文字描述 ----
distill_resp = requests.post("http://localhost:8085/v1/distill", json={
    "data": ["uploads/screenshot.png"],
    "vision_mode": "semantic",   # 通过 OCR/VLM 转换为文本
})
```

### 9.3 多模态 Tool Calling

在 Hermes Agent 的工具定义中集成多模态处理：

```python
# 在 HermesToolRegistry 中添加多模态工具

{
    "type": "function",
    "function": {
        "name": "analyze_document",
        "description": "分析文档内容，支持 PDF/DOCX/XLSX 等格式",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "文档文件路径",
                },
                "backend": {
                    "type": "string",
                    "enum": ["markitdown", "docling", "pymupdf", "deepseek"],
                    "default": "markitdown",
                    "description": "文档提取后端",
                },
                "compress": {
                    "type": "boolean",
                    "default": True,
                    "description": "是否压缩提取的文本",
                },
            },
            "required": ["file_path"],
        },
    },
},
{
    "type": "function",
    "function": {
        "name": "analyze_image",
        "description": "分析图片内容（截图、图表、照片等）",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "图片文件路径",
                },
                "mode": {
                    "type": "string",
                    "enum": ["pixel", "semantic"],
                    "default": "semantic",
                    "description": "pixel=保留视觉, semantic=转换文字",
                },
            },
            "required": ["file_path"],
        },
    },
}
```

---

## 10. 生产部署最佳实践

### 10.1 API 服务配置

**推荐的生产环境配置** (`context_distiller/config/default.yaml`)：

```yaml
# ---- LLM 推理服务 ----
llm_server:
  base_url: "http://your-ollama-server:11434"
  model_text: "qwen2.5:7b"
  model_vision: "qwen2.5vl:7b"
  model_ocr: "deepseek-ocr:latest"

# ---- 向量嵌入 ----
embedding_server:
  provider: "ollama"
  model: "bge-m3"
  base_url: "http://your-ollama-server:11434"

# ---- Prompt Distiller ----
prompt_distiller:
  profile: "balanced"
  text:
    default_level: "L2"
    onnx_quantization: "int8"
  document:
    default_backend: "markitdown"

# ---- Memory Gateway ----
memory_gateway:
  session_memory:
    micro_compact:
      enabled: true
      keep_recent: 3
    auto_compact:
      enabled: true
      token_threshold: 50000
      transcript_dir: "/data/transcripts"     # 生产环境用持久化路径
      summary_max_tokens: 2000
    summarize:
      strategy: "lingua"
      lingua_level: "L2"
      lingua_rate: 0.3

  user_memory:
    backend: "openclaw"
    openclaw:
      db_path: "/data/memory.db"              # 生产环境用持久化路径
      search_weights:
        vector: 0.7
        fts: 0.3
```

**生产启动命令**：

```bash
# 使用 Gunicorn + Uvicorn workers (Linux/macOS)
gunicorn context_distiller.api.server.app:app \
  -w 4 \
  -k uvicorn.workers.UvicornWorker \
  -b 0.0.0.0:8085 \
  --timeout 120 \
  --access-logfile /var/log/distiller/access.log \
  --error-logfile /var/log/distiller/error.log

# 使用 Uvicorn (Windows / 开发环境)
uvicorn context_distiller.api.server.app:app \
  --host 0.0.0.0 \
  --port 8085 \
  --workers 4 \
  --timeout-keep-alive 120
```

### 10.2 性能调优

**压缩性能优化**：

| 优化项 | 配置/方法 | 效果 |
|-------|----------|------|
| 使用 L0 做初筛 | `profile: "speed"` | 延迟 <1ms，但压缩率较低 |
| L2 使用 INT8 量化 | `onnx_quantization: "int8"` (默认) | 速度提升 ~2x |
| 跳过短文本压缩 | `compress_threshold_chars: 2000` | 减少不必要的处理 |
| 文档分块大小 | 默认 ≤1200 字符/块 | 过大会超 LLMLingua 的 512 token 限制 |

**记忆检索优化**：

| 优化项 | 方法 | 效果 |
|-------|------|------|
| 限制 top_k | `top_k: 3` (而非 10) | 减少不相关记忆干扰 |
| 按分类过滤 | `category="preference"` | 精准召回 |
| 调整权重 | 根据场景调整 vector/fts 比例 | 提高检索质量 |
| 定期清理 | 删除过期/无用记忆 | 减少噪音 |

**会话压缩优化**：

| 优化项 | 配置 | 说明 |
|-------|------|------|
| 降低 auto_compact 阈值 | `token_threshold: 30000` | 更早触发压缩，减少峰值内存 |
| 使用 lingua 策略 | `strategy: "lingua"` | 比 llm 快 5-20x |
| 增加 keep_recent | `keep_recent: 5` | 保留更多近期 tool 结果 |

### 10.3 监控与可观测性

每次 API 调用都会返回性能指标，建议接入监控系统：

```python
# /v1/distill 返回的 stats
{
    "input_tokens": 5000,
    "output_tokens": 2000,
    "compression_ratio": 0.60,     # 越低越好 (保留比例)
    "latency_ms": 243.5
}

# /v1/chat 返回的 debug info
{
    "mode": "full",
    "compact": "auto_compact triggered",  # 压缩触发状态
    "files_compressed": 2,
    "file_compression_ratio": 0.45,
    "images_attached": 1
}
```

**建议监控的指标**：

| 指标 | 阈值 | 说明 |
|------|------|------|
| `compression_ratio` | < 0.5 正常 | 压缩率异常高可能信息丢失 |
| `latency_ms` (L2) | < 500ms | 超过可能是模型加载慢 |
| `memory_hits` 数量 | > 0 | 长期为 0 说明记忆未正常存储 |
| `compact_triggered` 频率 | 适度 | 过频说明阈值太低 |
| Ollama 推理延迟 | < 10s | 超过检查 GPU 利用率 |

### 10.4 高可用部署

```
                    ┌──────────────┐
                    │   Nginx /    │
                    │  API Gateway │
                    └──────┬───────┘
                           │ 负载均衡
              ┌────────────┼────────────┐
              │            │            │
     ┌────────▼──┐  ┌──────▼──┐  ┌──────▼──┐
     │ Distiller │  │ Distiller│  │ Distiller│
     │ Instance 1│  │ Instance 2│  │ Instance 3│
     └────┬──────┘  └────┬─────┘  └────┬─────┘
          │              │              │
          └──────────────┼──────────────┘
                         │ 共享存储
              ┌──────────▼──────────┐
              │  共享 SQLite / NFS   │
              │  或迁移到 PostgreSQL  │
              └──────────┬──────────┘
                         │
              ┌──────────▼──────────┐
              │    Ollama Cluster    │
              │  (多 GPU 节点)       │
              └─────────────────────┘
```

> **注意**：SQLite 在高并发写入场景下有限制。如果需要多实例部署，建议：
> 1. 使用 NFS/共享存储挂载 SQLite 文件
> 2. 或实现自定义后端对接 PostgreSQL/MySQL
> 3. 或使用 Mem0 后端 (支持外部 Qdrant + Neo4j)

---

## 11. 完整项目示例

### 11.1 Hermes Agent + Context Distiller 客服系统

```python
"""
完整示例: 基于 Hermes Agent + Context Distiller 的智能客服系统

功能:
- 多轮对话 + 上下文压缩 (防止 Token 爆炸)
- 长期记忆 (记住客户偏好和历史问题)
- 文档附件处理 (分析客户上传的截图/文档)
- 多租户隔离 (每个客户 + 客服 Agent 独立记忆)
"""

import requests
import json
import time


class CustomerServiceAgent:
    """智能客服 Agent"""

    DISTILLER_URL = "http://localhost:8085"
    OLLAMA_URL = "http://localhost:11434"

    def __init__(self, customer_id: str):
        self.customer_id = customer_id
        self.agent_id = "customer_service_v1"
        self.session_id = f"cs_{customer_id}_{int(time.time())}"

    def handle_message(self, message: str, attachments: list = None) -> dict:
        """处理客户消息

        使用 Context Distiller /v1/chat 端点，它已内置:
        - 自动记忆召回
        - 会话压缩
        - 文件处理
        - LLM 推理
        """
        payload = {
            "message": message,
            "user_id": self.customer_id,
            "agent_id": self.agent_id,
            "session_id": self.session_id,
            "mode": "full",                    # 完整 Agent 模式
            "files": attachments or [],
        }

        resp = requests.post(f"{self.DISTILLER_URL}/v1/chat", json=payload)
        resp.raise_for_status()
        data = resp.json()

        return {
            "reply": data["reply"],
            "memory_recalled": len(data.get("memory_hits", [])),
            "memory_stored": len(data.get("memory_stored", [])),
            "compact_triggered": data.get("compact_triggered", False),
            "tokens_used": data.get("token_estimate", 0),
        }

    def store_customer_info(self, info: str, category: str = "fact"):
        """主动存储客户信息"""
        requests.post(f"{self.DISTILLER_URL}/v1/memory/store", json={
            "content": info,
            "source": f"cs_agent:{self.session_id}",
            "category": category,
            "user_id": self.customer_id,
            "agent_id": self.agent_id,
        })

    def get_customer_profile(self) -> list:
        """获取客户画像记忆"""
        resp = requests.post(f"{self.DISTILLER_URL}/v1/memory/list", json={
            "user_id": self.customer_id,
            "agent_id": self.agent_id,
            "category": "profile",
        })
        return resp.json().get("chunks", [])

    def reset_session(self):
        """重置当前会话"""
        requests.post(f"{self.DISTILLER_URL}/v1/chat/reset", json={
            "session_id": self.session_id,
        })


# ==========================================
# 使用示例
# ==========================================
if __name__ == "__main__":
    agent = CustomerServiceAgent(customer_id="C10086")

    # 首次接入，存储客户基本信息
    agent.store_customer_info("VIP 客户，月消费 > 5000 元", category="profile")
    agent.store_customer_info("偏好中文沟通，喜欢简洁回复", category="preference")

    # 模拟多轮对话
    conversations = [
        "你好，我的订单 ORD-20260428 还没到",
        "我已经等了 3 天了，能催一下吗？",
        "另外，我之前反馈的退款问题解决了吗？",
    ]

    for msg in conversations:
        print(f"\n客户: {msg}")
        result = agent.handle_message(msg)
        print(f"客服: {result['reply']}")
        print(f"  [记忆召回: {result['memory_recalled']} 条, "
              f"Token: {result['tokens_used']}, "
              f"压缩触发: {result['compact_triggered']}]")
```

### 11.2 多 Agent 协作知识库系统

```python
"""
多 Agent 协作示例: 不同职能的 Agent 共享同一用户的不同维度记忆

Agent 1: 技术助手 (技术问题解答)
Agent 2: 项目管理助手 (进度跟踪)

两个 Agent 通过 (user_id, agent_id) 隔离，
同一用户下记忆互不干扰，但可以通过显式跨 Agent 查询共享知识。
"""

import requests

DISTILLER_URL = "http://localhost:8085"


def store_memory(content, category, user_id, agent_id, source=""):
    return requests.post(f"{DISTILLER_URL}/v1/memory/store", json={
        "content": content,
        "source": source or f"{agent_id}:auto",
        "category": category,
        "user_id": user_id,
        "agent_id": agent_id,
    }).json()


def search_memory(query, user_id, agent_id, top_k=5):
    return requests.post(f"{DISTILLER_URL}/v1/memory/search", json={
        "query": query,
        "top_k": top_k,
        "user_id": user_id,
        "agent_id": agent_id,
    }).json()


# ---- 场景: Alice 同时使用两个 Agent ----
USER = "alice"

# Agent 1 (技术助手) 存储技术相关记忆
store_memory("项目使用 Python 3.12 + FastAPI", "rule", USER, "tech_assistant")
store_memory("数据库已迁移到 PostgreSQL 16", "fact", USER, "tech_assistant")
store_memory("Alice 偏好使用 Type Hints", "preference", USER, "tech_assistant")

# Agent 2 (项目管理助手) 存储项目相关记忆
store_memory("Sprint 23 截止日期: 2026-05-15", "fact", USER, "pm_assistant")
store_memory("当前 Sprint 目标: 完成用户认证模块", "note", USER, "pm_assistant")
store_memory("Alice 负责后端 API 开发", "profile", USER, "pm_assistant")

# ---- 各自搜索只能看到自己 Agent 下的记忆 ----
print("=== 技术助手搜索 'Python' ===")
tech_results = search_memory("Python", USER, "tech_assistant")
for chunk in tech_results["chunks"]:
    print(f"  [{chunk['category']}] {chunk['content']}")

print("\n=== 项目助手搜索 'Python' ===")
pm_results = search_memory("Python", USER, "pm_assistant")
for chunk in pm_results["chunks"]:
    print(f"  [{chunk['category']}] {chunk['content']}")
# → 项目助手搜索不到技术助手存储的 Python 相关记忆

# ---- 跨 Agent 知识共享 (显式查询) ----
print("\n=== 项目助手显式查询技术助手的记忆 ===")
cross_results = search_memory("技术栈", USER, "tech_assistant")  # 指定 tech_assistant
for chunk in cross_results["chunks"]:
    print(f"  [{chunk['category']}] {chunk['content']}")
```

---

## 12. 常见问题与排障

### Q1: Ollama 连接失败

```
HTTPConnectionPool: Max retries exceeded with url: /v1/chat/completions
```

**解决**：
1. 确认 Ollama 运行中: `curl http://localhost:11434/api/tags`
2. 检查配置中的 `ollama_base_url` 是否正确
3. 如果 Ollama 在远程服务器，检查防火墙

### Q2: 记忆搜索返回空结果

**排查步骤**：
1. 确认 `bge-m3` 模型已拉取: `ollama list | grep bge-m3`
2. 检查 `user_id` 和 `agent_id` 是否与存储时一致
3. 先用 `list_memories` 确认有记忆存在
4. 检查 `memory.db` 文件是否在正确路径

### Q3: 会话压缩未触发

**排查步骤**：
1. 检查 `session_token_threshold` 设置 (默认 50000)
2. 在 chat 返回的 `token_estimate` 中确认当前 Token 量
3. 确认 `mode` 为 `"full"` 或 `"session_only"`
4. 降低阈值测试: `PUT /v1/settings` 设 `session_token_threshold: 1000`

### Q4: 文档提取质量差

**解决**：
- PDF 扫描件 → 切换到 `deepseek` 后端 (OCR)
- Office 文档 → 使用 `markitdown` 后端
- 复杂排版 → 使用 `docling` 后端
- 通过 API 切换: `PUT /v1/settings` 设 `document_backend: "deepseek"`

### Q5: 压缩率不理想

**解决**：
- 文本太短 (<500 字符) → 压缩效果有限，这是正常的
- 切换到更高档位: `speed` → `balanced` → `accuracy`
- 调低 `compression_rate` (如 0.3 = 保留 30%)
- L3 (accuracy) 可达 60-80% 压缩率，但延迟较高

### Q6: sqlite-vec 未启用

```
sqlite-vec not available, FTS-only mode
```

**解决**：
```bash
pip install sqlite-vec
```
无 sqlite-vec 时系统自动降级为 FTS-only 模式，搜索仍可用但没有向量语义搜索。

---

## 13. 附录：API 快速参考

### 核心端点

| 端点 | 方法 | 说明 | 示例负载 |
|------|------|------|---------|
| `/health` | GET | 健康检查 | — |
| `/v1/distill` | POST | 多模态压缩 | `{"data": ["text"], "profile": "balanced"}` |
| `/v1/chat` | POST | Agent 对话 | `{"message": "hi", "user_id": "u1", "mode": "full"}` |
| `/v1/chat/reset` | POST | 重置会话 | `{"session_id": "default"}` |
| `/v1/memory/search` | POST | 搜索记忆 | `{"query": "偏好", "user_id": "u1"}` |
| `/v1/memory/store` | POST | 存储记忆 | `{"content": "...", "category": "fact", "user_id": "u1"}` |
| `/v1/memory/update` | POST | 更新记忆 | `{"chunk_id": "1", "content": "new...", "user_id": "u1"}` |
| `/v1/memory/forget` | POST | 删除记忆 | `{"chunk_id": "1", "user_id": "u1"}` |
| `/v1/memory/list` | POST | 列出记忆 | `{"user_id": "u1", "category": "preference"}` |
| `/v1/settings` | GET/PUT | 读写配置 | `{"ollama_base_url": "...", "profile": "..."}` |
| `/v1/upload` | POST | 上传文件 | multipart/form-data |

### 压缩 Profile 对照

| Profile | 级别 | 压缩率 | 延迟 | 适用场景 |
|---------|------|--------|------|---------|
| `speed` | L0 | 10-20% | <1ms | 实时交互，低延迟要求 |
| `selective` | L1 | 30-40% | 50-200ms | 一般在线场景 |
| `balanced` | L2 | 40-50% | 100-500ms | **推荐默认** |
| `accuracy` | L3 | 60-80% | 2-10s | 离线批处理，最高质量 |

### 记忆分类

| 分类 | 用途 | 场景示例 |
|------|------|---------|
| `fact` | 客观事实 | 技术栈、配置、数据 |
| `preference` | 用户偏好 | 主题、风格、习惯 |
| `rule` | 约束规则 | 编码规范、安全要求 |
| `profile` | 用户画像 | 角色、经验、背景 |
| `note` | 笔记 | 会议记录、临时备忘 |
| `system` | 系统信息 | Agent 配置变更 |

---

## 参考链接

- [Context Distiller REST API 文档](../api/REST_API.md)
- [Python SDK API 参考](../api/API_REFERENCE.md)
- [配置参数详解](../api/CONFIGURATION.md)
- [OpenClaw 记忆系统深度解析](../openclaw_memory_deep_dive.md)
- [上下文压缩技术教程](../teaching_context_compression.md)

---

> **文档版本**: v1.0 | **更新日期**: 2026-04-28 | **适用版本**: Context Distiller v2.0+
