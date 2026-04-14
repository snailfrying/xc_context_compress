# 快速开始指南

## 一键安装（推荐）

```bash
# 1. 创建conda环境
conda env create -f environment.yml
conda activate context_distiller

# 2. 安装项目
pip install -e .

# 3. 验证安装
python verify_installation.py --mode basic
```

## 使用示例

### 1. Python SDK

```python
from context_distiller.sdk import DistillerClient

# 创建客户端
client = DistillerClient(profile="balanced")

# 文本压缩
result = client.process(data=["长文本内容..."])
print(f"压缩率: {result.stats.compression_ratio:.2%}")

# 记忆管理
client.store_memory(content="重要信息", source="file.py#L10")
results = client.search_memory("查询关键词", top_k=5)
```

### 2. REST API

```bash
# 启动服务
python -m context_distiller.api.server.app

# 调用API
curl -X POST http://localhost:8080/v1/distill \
  -H "Content-Type: application/json" \
  -d '{"data": ["测试文本"], "profile": "balanced"}'
```

### 3. CLI命令行

```bash
# 压缩文件
python -m context_distiller.api.cli.main distill file.txt --profile speed

# 检索记忆
python -m context_distiller.api.cli.main search "关键词"
```

## 配置本地LLM（可选）

如果需要L3级压缩，配置Ollama服务：

```yaml
# config/default.yaml
prompt_distiller:
  text:
    llm_url: "http://172.16.10.201:11434"
    llm_model: "qwen2.5:7b"
```

## 故障排查

```bash
# 检查Python版本
python --version  # 需要 3.9+

# 检查依赖
pip list | grep pydantic

# 重新安装
pip install -e . --force-reinstall
```
