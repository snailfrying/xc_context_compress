# Context Distiller v2.0 快速参考

## 一、快速启动

```bash
# 1. 激活环境
conda activate context_distiller

# 2. 验证安装
python verify_installation.py --mode basic

# 3. 运行示例
python examples/complete_demo.py
```

## 二、核心API

### Python SDK
```python
from context_distiller.sdk import DistillerClient

# 创建客户端
client = DistillerClient(profile="balanced")  # speed/balanced/accuracy

# 文本压缩
result = client.process(data=["长文本内容"])
print(f"压缩率: {result.stats.compression_ratio:.2%}")

# 存储记忆
client.store_memory(content="重要信息", source="file.py#L10")

# 检索记忆
results = client.search_memory("查询关键词", top_k=5)
```

### REST API
```bash
# 启动服务
python -m context_distiller.api.server.app

# 压缩请求
curl -X POST http://localhost:8080/v1/distill \
  -H "Content-Type: application/json" \
  -d '{"data": ["文本"], "profile": "balanced"}'

# 记忆检索
curl -X POST http://localhost:8080/v1/memory/search?query=关键词&top_k=5
```

### CLI命令
```bash
# 压缩文件
python -m context_distiller.api.cli.main distill file.txt --profile speed

# 检索记忆
python -m context_distiller.api.cli.main search "关键词" --top-k 5
```

## 三、配置文件

位置: `context_distiller/config/default.yaml`

```yaml
# 文本压缩级别
prompt_distiller:
  profile: "balanced"  # speed/balanced/accuracy
  text:
    default_level: "L2"  # L0/L1/L2/L3

# 记忆配置
memory_gateway:
  user_memory:
    backend: "openclaw"  # openclaw/mem0/custom
```

## 四、压缩级别对比

| 级别 | 硬件 | 延迟 | 压缩率 | 依赖 |
|------|------|------|--------|------|
| L0 | CPU | <10ms | 20-30% | 无 |
| L1 | CPU | ~100ms | 40-50% | transformers |
| L2 | CPU/NPU | ~200ms | 60-80% | onnxruntime |
| L3 | GPU | 1-3s | 80-95% | torch + LLM |

## 五、常用命令

```bash
# 环境管理
conda activate context_distiller
conda deactivate

# 验证功能
python verify_installation.py --mode basic
python verify_installation.py --mode gpu

# 运行测试
pytest context_distiller/tests/ -v

# 启动API服务
python -m context_distiller.api.server.app
# 或
uvicorn context_distiller.api.server.app:app --host 0.0.0.0 --port 8080
```

## 六、故障排查

```bash
# 重新安装
pip install -e . --force-reinstall

# 检查依赖
pip list | grep pydantic

# 查看日志
python -c "from context_distiller.infra import HardwareProbe; print(HardwareProbe().detect())"
```

## 七、扩展安装

```bash
# GPU支持
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118
pip install transformers>=4.30.0

# 文档AI解析
pip install docling

# mem0记忆后端
pip install -e .[mem0]
```

## 八、项目文件

```
重要文件:
├── verify_installation.py      # 验证脚本
├── examples/complete_demo.py   # 完整示例
├── INSTALL.md                  # 安装教程
├── QUICKSTART.md              # 快速开始
├── DEPLOYMENT_REPORT.md       # 部署报告
└── context_distiller/
    ├── config/default.yaml    # 配置文件
    └── sdk/client.py          # SDK客户端
```

## 九、支持的数据格式

- **文本**: 直接字符串
- **文档**: PDF, Word, PPT, Excel, HTML, Markdown
- **图像**: JPG, PNG, BMP (自动去重)
- **URL**: 自动下载并处理

## 十、性能建议

| 场景 | 推荐配置 | Profile |
|------|----------|---------|
| 实时对话 | CPU 2核+ | speed |
| 文档处理 | CPU 4核+ | balanced |
| 批量分析 | GPU 6GB+ | accuracy |

---

**当前状态**: ✅ 已安装并验证
**环境**: context_distiller (Python 3.10)
**模式**: CPU (可扩展GPU)
