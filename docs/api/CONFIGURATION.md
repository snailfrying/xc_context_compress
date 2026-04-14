# 配置参数完整说明

## 配置文件位置

- **默认配置**: `context_distiller/config/default.yaml`
- **Speed模式**: `context_distiller/config/profiles/speed.yaml`
- **Balanced模式**: `context_distiller/config/profiles/balanced.yaml`
- **Accuracy模式**: `context_distiller/config/profiles/accuracy.yaml`

---

## 配置结构

### 1. Prompt Distiller 配置

文本压缩引擎配置。

```yaml
prompt_distiller:
  profile: "balanced"              # 预设模式

  text:
    default_level: "L2"            # 压缩级别
    onnx_quantization: "int8"      # ONNX量化策略
    llm_url: "http://localhost:11434"  # LLM服务地址
    llm_model: "qwen2.5:7b"        # LLM模型名称

  document:
    cpu_backend: "markitdown"      # CPU文档解析器

  vision:
    dedup_enabled: true            # 启用图像去重
    tile_adaptive: true            # 自适应Tile降档
```

**参数详解**:

#### profile
- **类型**: string
- **可选值**: "speed", "balanced", "accuracy"
- **默认值**: "balanced"
- **说明**: 预设配置模式，影响压缩级别和性能

#### text.default_level
- **类型**: string
- **可选值**: "L0", "L1", "L2", "L3"
- **默认值**: "L2"
- **说明**:
  - L0: 正则清洗，<10ms，压缩率20-30%
  - L1: SelectiveContext，~100ms，压缩率40-50%
  - L2: LLMLingua-2，~200ms，压缩率60-80%
  - L3: GPU摘要，1-3s，压缩率80-95%

#### text.onnx_quantization
- **类型**: string
- **可选值**: "int8", "fp16", "fp32"
- **默认值**: "int8"
- **说明**: ONNX模型量化策略，int8最快但精度略低

#### text.llm_url
- **类型**: string
- **默认值**: "http://localhost:11434"
- **说明**: 本地LLM服务地址（用于L3压缩）

#### text.llm_model
- **类型**: string
- **默认值**: "qwen2.5:7b"
- **说明**: LLM模型名称

#### document.cpu_backend
- **类型**: string
- **可选值**: "markitdown", "pymupdf"
- **默认值**: "markitdown"
- **说明**:
  - markitdown: 支持更多格式，体积较大
  - pymupdf: 仅PDF，体积小速度快

#### vision.dedup_enabled
- **类型**: boolean
- **默认值**: true
- **说明**: 启用pHash图像去重

#### vision.tile_adaptive
- **类型**: boolean
- **默认值**: true
- **说明**: 根据目标模型自适应调整图像尺寸

---

### 2. Memory Gateway 配置

记忆网关配置。

```yaml
memory_gateway:
  # 会话记忆配置
  session_memory:
    backend: "builtin"

    micro_compact:
      enabled: true                # 启用微压缩
      keep_recent: 3               # 保留最近N轮
      min_content_length: 100      # 最小内容长度

    auto_compact:
      enabled: true                # 启用自动压缩
      token_threshold: 50000       # Token阈值
      transcript_dir: ".transcripts/"  # 历史保存目录
      summary_max_tokens: 2000     # 摘要最大tokens

    manual_compact:
      enabled: true                # 暴露手动压缩工具

    persist_on_close: true         # 关闭时持久化

  # 用户长久记忆配置
  user_memory:
    backend: "openclaw"            # 后端类型

    openclaw:
      storage: "sqlite"            # 存储类型
      db_path: "memory.db"         # 数据库路径
      memory_paths:                # 记忆文件路径
        - "MEMORY.md"
        - "memory/*.md"
      sync_trigger: "on_search"    # 同步触发时机
      search_weights:              # 检索权重
        vector: 0.7
        fts: 0.3

    mem0:
      llm_provider: "ollama"       # LLM提供商
      llm_model: "qwen2.5:7b"      # LLM模型
      embedder: "BAAI/bge-m3"      # 嵌入模型
      vector_store: "chroma"       # 向量存储
      enable_graph: false          # 启用图谱
```

**参数详解**:

#### session_memory.micro_compact.keep_recent
- **类型**: integer
- **默认值**: 3
- **说明**: 保留最近N轮的完整tool_result

#### session_memory.auto_compact.token_threshold
- **类型**: integer
- **默认值**: 50000
- **说明**: 超过此token数时触发自动压缩

#### user_memory.backend
- **类型**: string
- **可选值**: "openclaw", "mem0", "custom"
- **默认值**: "openclaw"
- **说明**:
  - openclaw: 本地SQLite，轻量级
  - mem0: 生产级，支持实体消歧
  - custom: 自定义后端

#### user_memory.openclaw.sync_trigger
- **类型**: string
- **可选值**: "on_search", "on_session_start", "interval"
- **默认值**: "on_search"
- **说明**:
  - on_search: 检索时同步
  - on_session_start: 会话开始时同步
  - interval: 定时同步

---

### 3. API 配置

API服务配置。

```yaml
api:
  gateway: "litellm"               # 网关类型
  port: 8080                       # 服务端口
  cost_tracking: true              # 成本追踪
  load_balancing: true             # 负载均衡
```

---

### 4. Telemetry 配置

可观测性配置。

```yaml
telemetry:
  enabled: true                    # 启用遥测
  metrics:                         # 指标列表
    - token_count
    - compression_ratio
    - latency_ms
    - oom_fallback_count
```

---

## 配置优先级

1. 代码中传入的参数（最高优先级）
2. 环境变量
3. 自定义配置文件
4. Profile配置文件
5. 默认配置文件（最低优先级）

---

## 自定义配置示例

### 创建自定义配置

```yaml
# my_config.yaml
prompt_distiller:
  profile: "speed"
  text:
    default_level: "L0"

memory_gateway:
  session_memory:
    auto_compact:
      token_threshold: 30000
```

### 使用自定义配置

```python
import yaml
from context_distiller.sdk import DistillerClient

with open("my_config.yaml") as f:
    config = yaml.safe_load(f)

client = DistillerClient(config=config)
```
