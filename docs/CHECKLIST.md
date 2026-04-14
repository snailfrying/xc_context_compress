# Context Distiller v2.0 使用检查清单

## ✅ 安装验证

- [x] Conda环境已创建 (context_distiller)
- [x] 项目已安装 (pip install -e .)
- [x] 所有依赖已安装
- [x] 基础功能验证通过 (5/5)

## 📋 每次使用前

```bash
# 1. 激活环境
conda activate context_distiller

# 2. 验证环境（可选）
python verify_installation.py --mode basic
```

## 🎯 核心使用场景

### 场景1: 文本压缩
```python
from context_distiller.sdk import DistillerClient

client = DistillerClient(profile="speed")
result = client.process(data=["长文本内容"])
print(f"压缩率: {result.stats.compression_ratio:.2%}")
```

### 场景2: 文档解析
```python
client = DistillerClient()
result = client.process(data=["document.pdf"])
# 自动识别并解析PDF/Word/PPT等
```

### 场景3: 记忆管理
```python
# 存储
client.store_memory(content="重要信息", source="file.py#L10")

# 检索
results = client.search_memory("关键词", top_k=5)
```

### 场景4: REST API服务
```bash
# 启动服务
python -m context_distiller.api.server.app

# 访问: http://localhost:8080/health
```

## 🔍 故障排查

### 问题1: 导入错误
```bash
pip install -e . --force-reinstall
```

### 问题2: 环境未激活
```bash
conda activate context_distiller
```

### 问题3: 依赖缺失
```bash
pip install -r requirements.txt
```

## 📊 性能参考

| 操作 | 预期延迟 | 说明 |
|------|----------|------|
| L0文本压缩 | <10ms | CPU正则清洗 |
| 文档解析 | 100-500ms | 取决于文件大小 |
| 记忆检索 | <50ms | SQLite FTS5 |
| API响应 | <100ms | 不含处理时间 |

## 🎓 学习资源

1. **基础使用**: examples/basic_usage.py
2. **完整演示**: examples/complete_demo.py
3. **安装指南**: INSTALL.md
4. **快速参考**: QUICK_REFERENCE.md

## 🚀 生产部署

### Docker部署（可选）
```bash
docker build -t context-distiller:2.0 .
docker run -p 8080:8080 context-distiller:2.0
```

### 系统服务（可选）
```bash
# 使用systemd或supervisor管理API服务
```

## 📝 配置文件位置

- 默认配置: `context_distiller/config/default.yaml`
- Speed模式: `context_distiller/config/profiles/speed.yaml`
- Balanced模式: `context_distiller/config/profiles/balanced.yaml`
- Accuracy模式: `context_distiller/config/profiles/accuracy.yaml`

## 🔧 常用命令速查

```bash
# 验证安装
python verify_installation.py --mode basic

# 运行示例
python examples/complete_demo.py

# 启动API
python -m context_distiller.api.server.app

# 运行测试
pytest context_distiller/tests/ -v

# CLI压缩
python -m context_distiller.api.cli.main distill file.txt

# CLI检索
python -m context_distiller.api.cli.main search "关键词"
```

## ⚡ 性能优化建议

1. **文本压缩**: 使用speed模式获得最快响应
2. **批量处理**: 一次处理多个文件以分摊开销
3. **记忆检索**: 限制top_k值以提高速度
4. **API服务**: 使用uvicorn的worker参数并发处理

## 🎯 当前状态

```
✅ 环境: context_distiller (Python 3.10)
✅ 模式: CPU (可扩展GPU)
✅ 状态: 生产就绪
✅ 验证: 5/5 通过

可用功能:
- 文本压缩 (L0)
- 文档解析 (CPU)
- 图像处理 (CPU)
- 记忆管理 (完整)
- API服务 (完整)
```

## 📞 获取帮助

- 查看文档: INSTALL.md, QUICKSTART.md
- 运行示例: examples/
- 验证功能: verify_installation.py
- 查看配置: context_distiller/config/

---

**最后更新**: 2026-03-11
**版本**: 2.0.0
**状态**: ✅ 已验证
