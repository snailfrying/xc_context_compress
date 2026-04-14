# Context Distiller v2.0 文档中心

欢迎使用 Context Distiller v2.0 - 全模态统一上下文预处理与 Agent 记忆网关

---

## 📚 文档导航

### 快速开始
- [README](../README.md) - 项目概述
- [快速开始指南](QUICKSTART.md) - 5分钟上手
- [安装教程](INSTALL.md) - 详细安装步骤
- [部署报告](DEPLOYMENT_REPORT.md) - 部署验证结果

### API 参考
- [Python SDK API](api/API_REFERENCE.md) - Python客户端完整API
- [REST API](api/REST_API.md) - HTTP接口文档
- [CLI命令行](api/CLI_REFERENCE.md) - 命令行工具使用
- [配置参数](api/CONFIGURATION.md) - 配置文件详解

### 使用指南
- [用户指南](guides/USER_GUIDE.md) - 功能详解与最佳实践
- [使用示例](examples/EXAMPLES.md) - 完整代码示例
- [快速参考](QUICK_REFERENCE.md) - 常用命令速查

### 其他
- [项目总结](PROJECT_SUMMARY.md) - 架构与实现
- [使用检查清单](CHECKLIST.md) - 日常使用清单

---

## 🚀 快速链接

### 我想...

**开始使用**
- [安装环境](INSTALL.md#一conda环境安装推荐) → [验证安装](INSTALL.md#13-验证安装) → [第一个示例](guides/USER_GUIDE.md#第一个示例)

**压缩文本**
- [Python SDK](api/API_REFERENCE.md#方法-process) | [REST API](api/REST_API.md#2-文本文档压缩) | [CLI](api/CLI_REFERENCE.md#1-distill---压缩文件)

**解析文档**
- [支持格式](guides/USER_GUIDE.md#2-文档解析) | [使用示例](examples/EXAMPLES.md#示例2-文档解析)

**管理记忆**
- [存储记忆](api/API_REFERENCE.md#方法-store_memory) | [检索记忆](api/API_REFERENCE.md#方法-search_memory)

**配置系统**
- [配置文件](api/CONFIGURATION.md#配置文件位置) | [参数说明](api/CONFIGURATION.md#配置结构)

**集成到项目**
- [RAG系统](examples/EXAMPLES.md#示例7-集成到rag系统) | [Agent系统](examples/EXAMPLES.md#示例8-agent记忆系统) | [FastAPI](examples/EXAMPLES.md#示例9-fastapi集成)

---

## 📖 按角色阅读

### 开发者
1. [安装教程](INSTALL.md)
2. [Python SDK API](api/API_REFERENCE.md)
3. [使用示例](examples/EXAMPLES.md)
4. [配置参数](api/CONFIGURATION.md)

### 运维人员
1. [部署报告](DEPLOYMENT_REPORT.md)
2. [REST API](api/REST_API.md)
3. [配置参数](api/CONFIGURATION.md)

### 最终用户
1. [快速开始](QUICKSTART.md)
2. [用户指南](guides/USER_GUIDE.md)
3. [CLI命令行](api/CLI_REFERENCE.md)

---

## 🎯 按场景阅读

### 场景1: 文本压缩
- [功能介绍](guides/USER_GUIDE.md#1-文本压缩)
- [API文档](api/API_REFERENCE.md#方法-process)
- [使用示例](examples/EXAMPLES.md#示例1-文本压缩)
- [压缩级别选择](api/CONFIGURATION.md#textdefault_level)

### 场景2: 文档处理
- [功能介绍](guides/USER_GUIDE.md#2-文档解析)
- [支持格式](guides/USER_GUIDE.md#支持格式)
- [批量处理](examples/EXAMPLES.md#示例5-批量文档处理)

### 场景3: RAG优化
- [使用场景](guides/USER_GUIDE.md#场景1-rag系统优化)
- [集成示例](examples/EXAMPLES.md#示例7-集成到rag系统)

### 场景4: Agent记忆
- [功能介绍](guides/USER_GUIDE.md#4-记忆管理)
- [使用场景](guides/USER_GUIDE.md#场景4-agent记忆系统)
- [集成示例](examples/EXAMPLES.md#示例8-agent记忆系统)

---

## 🔧 常见问题

### 安装问题
- [导入错误](DEPLOYMENT_REPORT.md#常见问题)
- [环境配置](INSTALL.md#11-创建基础环境)
- [依赖安装](INSTALL.md#12-分层安装策略)

### 使用问题
- [压缩效果不理想](guides/USER_GUIDE.md#压缩级别选择)
- [性能优化](guides/USER_GUIDE.md#性能优化)
- [错误处理](api/API_REFERENCE.md#错误处理)

### 配置问题
- [Profile选择](api/CONFIGURATION.md#profile)
- [自定义配置](api/CONFIGURATION.md#自定义配置示例)
- [参数说明](api/CONFIGURATION.md#参数详解)

---

## 📊 功能对比表

| 功能 | Python SDK | REST API | CLI |
|------|-----------|----------|-----|
| 文本压缩 | ✅ | ✅ | ✅ |
| 文档解析 | ✅ | ✅ | ✅ |
| 图像处理 | ✅ | ✅ | ✅ |
| 记忆管理 | ✅ | ✅ | ✅ |
| 批量处理 | ✅ | ✅ | ✅ |
| 自定义配置 | ✅ | ❌ | ⚠️ |

---

## 🎓 学习路径

### 初级（1-2小时）
1. 阅读 [README](../README.md)
2. 完成 [快速开始](QUICKSTART.md)
3. 运行 [基础示例](examples/EXAMPLES.md#基础示例)

### 中级（3-5小时）
1. 学习 [用户指南](guides/USER_GUIDE.md)
2. 理解 [配置参数](api/CONFIGURATION.md)
3. 实践 [进阶示例](examples/EXAMPLES.md#进阶示例)

### 高级（1-2天）
1. 深入 [API参考](api/API_REFERENCE.md)
2. 研究 [集成示例](examples/EXAMPLES.md#集成示例)
3. 阅读 [项目总结](PROJECT_SUMMARY.md)

---

## 📝 文档更新日志

- **2026-03-11**: 初始版本发布
  - 完整API文档
  - 用户指南
  - 使用示例
  - 配置说明

---

## 🤝 贡献文档

发现文档问题或有改进建议？欢迎提交Issue或PR。

---

## 📞 获取帮助

- 查看 [常见问题](#常见问题)
- 阅读 [用户指南](guides/USER_GUIDE.md)
- 运行 [验证脚本](../verify_installation.py)
- 查看 [示例代码](examples/EXAMPLES.md)
