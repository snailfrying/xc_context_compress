# 文档结构说明

## 目录组织

```
docs/
├── INDEX.md                    # 📚 文档中心主页（从这里开始）
├── QUICKSTART.md              # 🚀 5分钟快速开始
├── INSTALL.md                 # 📦 详细安装教程
├── DEPLOYMENT_REPORT.md       # ✅ 部署验证报告
├── QUICK_REFERENCE.md         # ⚡ 快速参考卡
├── CHECKLIST.md               # ☑️ 使用检查清单
├── PROJECT_SUMMARY.md         # 📋 项目架构总结
│
├── api/                       # API参考文档
│   ├── API_REFERENCE.md       # Python SDK完整API
│   ├── REST_API.md            # HTTP接口文档
│   ├── CLI_REFERENCE.md       # 命令行工具
│   └── CONFIGURATION.md       # 配置参数详解
│
├── guides/                    # 使用指南
│   └── USER_GUIDE.md          # 用户完整指南
│
└── examples/                  # 示例代码
    └── EXAMPLES.md            # 完整使用示例
```

## 文档分类

### 入门文档（必读）
1. **README.md** - 项目概述和快速开始
2. **docs/QUICKSTART.md** - 5分钟上手指南
3. **docs/INSTALL.md** - 安装教程

### API文档（开发必备）
1. **docs/api/API_REFERENCE.md** - Python SDK API
2. **docs/api/REST_API.md** - REST API
3. **docs/api/CLI_REFERENCE.md** - CLI命令
4. **docs/api/CONFIGURATION.md** - 配置参数

### 使用指南（深入学习）
1. **docs/guides/USER_GUIDE.md** - 功能详解
2. **docs/examples/EXAMPLES.md** - 代码示例

### 参考文档（速查）
1. **docs/QUICK_REFERENCE.md** - 常用命令
2. **docs/CHECKLIST.md** - 使用清单

### 其他文档
1. **docs/DEPLOYMENT_REPORT.md** - 部署报告
2. **docs/PROJECT_SUMMARY.md** - 项目总结

## 阅读建议

### 新手路径
```
README.md → QUICKSTART.md → INSTALL.md → USER_GUIDE.md → EXAMPLES.md
```

### 开发者路径
```
README.md → INSTALL.md → API_REFERENCE.md → EXAMPLES.md → CONFIGURATION.md
```

### 运维路径
```
INSTALL.md → DEPLOYMENT_REPORT.md → REST_API.md → CONFIGURATION.md
```

## 快速查找

### 我想知道...

**如何安装？**
→ [INSTALL.md](INSTALL.md)

**如何使用Python SDK？**
→ [api/API_REFERENCE.md](api/API_REFERENCE.md)

**如何调用REST API？**
→ [api/REST_API.md](api/REST_API.md)

**如何配置系统？**
→ [api/CONFIGURATION.md](api/CONFIGURATION.md)

**有哪些使用示例？**
→ [examples/EXAMPLES.md](examples/EXAMPLES.md)

**常用命令是什么？**
→ [QUICK_REFERENCE.md](QUICK_REFERENCE.md)

## 文档维护

- **创建日期**: 2026-03-11
- **版本**: 2.0.0
- **状态**: ✅ 完整

## 文档统计

- 总文档数: 13个
- API文档: 4个
- 指南文档: 1个
- 示例文档: 1个
- 参考文档: 7个
