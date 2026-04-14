# Context Distiller v2.0 安装部署教程

## 环境要求

- Python 3.9+
- Conda (推荐) 或 pip
- 操作系统: Windows/Linux/macOS

## 一、Conda环境安装（推荐）

### 1.1 创建基础环境

```bash
# 创建conda环境
conda create -n context_distiller python=3.10 -y
conda activate context_distiller

# 进入项目目录
cd C:\Users\zizhang.wu\PycharmProjects\context_compress
```

### 1.2 分层安装策略

Context Distiller 采用分层安装设计，根据需求选择：

#### 方案A：CPU基础版（推荐入门）
**适用场景**: 轻量级文档处理、文本压缩、无GPU环境
**依赖体积**: ~200MB
**功能**: L0/L1文本压缩、文档解析、图像预处理

```bash
# 安装基础依赖
pip install -e .
```

#### 方案B：GPU完整版
**适用场景**: 需要AI增强处理、有GPU环境
**依赖体积**: ~4GB+
**功能**: 全部功能（L0-L3压缩、AI文档解析、VLM图像处理）

```bash
# 先安装基础版
pip install -e .

# 再安装GPU扩展
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118
pip install transformers>=4.30.0
pip install onnxruntime-gpu>=1.15.0
```

#### 方案C：记忆增强版
**适用场景**: 需要mem0记忆后端

```bash
pip install -e .[mem0]
```

### 1.3 验证安装

```bash
# 验证基础功能
python verify_installation.py --mode basic

# 验证GPU功能（如果安装了GPU版）
python verify_installation.py --mode gpu

# 验证全部功能
python verify_installation.py --mode all
```

## 二、本地Ollama模型服务配置

Context Distiller 可以调用本地Ollama服务进行L3级压缩。

### 2.1 安装Ollama

```bash
# Windows: 下载安装包
# https://ollama.ai/download

# Linux
curl -fsSL https://ollama.ai/install.sh | sh

# 启动服务（默认端口11434）
ollama serve
```

### 2.2 拉取推荐模型

```bash
# 轻量级模型（推荐）
ollama pull qwen2.5:7b

# 或使用您服务器上的模型
# 服务地址: http://172.16.10.201:11434
```

### 2.3 配置模型地址

编辑 `context_distiller/config/default.yaml`:

```yaml
prompt_distiller:
  text:
    llm_url: "http://172.16.10.201:11434"  # 您的Ollama服务地址
    llm_model: "qwen2.5:7b"
```

## 三、功能模块使用指南

### 3.1 文本压缩

```python
from context_distiller.sdk import DistillerClient

# 创建客户端
client = DistillerClient(profile="balanced")

# 压缩长文本
long_text = "..." * 1000
result = client.process(data=[long_text])
print(f"压缩率: {result.stats.compression_ratio:.2%}")
```

**依赖**: 基础版即可
**性能**: L0 <10ms, L1 ~100ms, L2 ~200ms

### 3.2 文档解析

```python
# CPU版本（零模型）
result = client.process(data=["document.pdf"])

# GPU版本（需要安装docling）
# pip install docling
```

**支持格式**: PDF, Word, PPT, Excel, HTML, Markdown

### 3.3 图像处理

```python
# 批量处理图像（自动去重）
result = client.process(data=["img1.jpg", "img2.png", "img3.jpg"])
```

**功能**: pHash去重、自适应降维、Tile优化

### 3.4 记忆管理

```python
# 存储记忆
client.store_memory(
    content="项目使用Python 3.10",
    source="config.py#L1"
)

# 检索记忆
results = client.search_memory("Python版本", top_k=5)
```

### 3.5 REST API服务

```bash
# 启动服务器
python -m context_distiller.api.server.app

# 或使用uvicorn
uvicorn context_distiller.api.server.app:app --host 0.0.0.0 --port 8080
```

**API端点**:
- `POST /v1/distill` - 压缩处理
- `POST /v1/memory/search` - 记忆检索
- `POST /v1/memory/store` - 存储记忆
- `GET /health` - 健康检查

### 3.6 CLI命令行

```bash
# 批量压缩文件
python -m context_distiller.api.cli.main distill file1.pdf file2.txt --profile speed

# 检索记忆
python -m context_distiller.api.cli.main search "关键词" --top-k 5
```

## 四、性能优化建议

### 4.1 硬件配置推荐

| 场景 | CPU | 内存 | GPU | 说明 |
|------|-----|------|-----|------|
| 轻量级 | 2核+ | 4GB | 无 | L0/L1压缩 |
| 标准 | 4核+ | 8GB | 无 | L2压缩 + 文档解析 |
| 高性能 | 8核+ | 16GB | 6GB+ | L3压缩 + AI增强 |

### 4.2 配置调优

```yaml
# config/default.yaml

# 极速模式（<50ms）
prompt_distiller:
  profile: "speed"
  text:
    default_level: "L0"

# 平衡模式（~200ms）
prompt_distiller:
  profile: "balanced"
  text:
    default_level: "L2"

# 精准模式（1-3s）
prompt_distiller:
  profile: "accuracy"
  text:
    default_level: "L3"
```

## 五、常见问题

### 5.1 导入错误

```bash
# 如果遇到 ModuleNotFoundError
pip install -e . --force-reinstall
```

### 5.2 GPU不可用

```python
# 检查GPU状态
from context_distiller.infra import HardwareProbe
probe = HardwareProbe()
print(probe.detect())
```

### 5.3 内存不足

```yaml
# 降低缓存大小
memory_gateway:
  session_memory:
    auto_compact:
      token_threshold: 30000  # 降低阈值
```

## 六、开发模式

```bash
# 安装开发依赖
pip install pytest pytest-cov black flake8

# 运行测试
pytest context_distiller/tests/ -v

# 代码格式化
black context_distiller/

# 类型检查
# pip install mypy
# mypy context_distiller/
```

## 七、Docker部署（可选）

```dockerfile
# Dockerfile
FROM python:3.10-slim

WORKDIR /app
COPY . .

RUN pip install -e .

EXPOSE 8080
CMD ["python", "-m", "context_distiller.api.server.app"]
```

```bash
# 构建镜像
docker build -t context-distiller:2.0 .

# 运行容器
docker run -p 8080:8080 context-distiller:2.0
```
