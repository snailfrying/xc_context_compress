# CLI 命令行参考文档

## 基础用法

```bash
python -m context_distiller.api.cli.main [COMMAND] [OPTIONS]
```

或安装后使用：
```bash
context-distiller [COMMAND] [OPTIONS]
```

---

## 命令列表

### 1. distill - 压缩文件

压缩一个或多个文件。

**语法**:
```bash
python -m context_distiller.api.cli.main distill [FILES...] [OPTIONS]
```

**参数**:

| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| FILES | path | 是 | 一个或多个文件路径 |
| --profile | string | 否 | 压缩模式 (speed/balanced/accuracy) |
| --output, -o | path | 否 | 输出文件路径 |

**示例**:

```bash
# 压缩单个文件
python -m context_distiller.api.cli.main distill document.pdf

# 压缩多个文件
python -m context_distiller.api.cli.main distill file1.txt file2.pdf file3.docx

# 指定压缩模式
python -m context_distiller.api.cli.main distill document.pdf --profile speed

# 指定输出文件
python -m context_distiller.api.cli.main distill input.txt -o output.txt
```

**输出示例**:
```
Processing document.pdf...
Compression ratio: 65.30%
Done!
```

---

### 2. search - 检索记忆

检索用户记忆库。

**语法**:
```bash
python -m context_distiller.api.cli.main search QUERY [OPTIONS]
```

**参数**:

| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| QUERY | string | 是 | 检索查询文本 |
| --top-k | integer | 否 | 返回结果数量（默认5） |

**示例**:

```bash
# 基础检索
python -m context_distiller.api.cli.main search "Python版本"

# 限制结果数
python -m context_distiller.api.cli.main search "配置" --top-k 3

# 多词查询
python -m context_distiller.api.cli.main search "数据库 配置"
```

**输出示例**:
```
config.py#L1:
项目使用Python 3.10

settings.yaml#L5:
数据库使用PostgreSQL
```

---

## 全局选项

| 选项 | 说明 |
|------|------|
| --help, -h | 显示帮助信息 |
| --version | 显示版本信息 |

**示例**:
```bash
# 查看帮助
python -m context_distiller.api.cli.main --help

# 查看命令帮助
python -m context_distiller.api.cli.main distill --help

# 查看版本
python -m context_distiller.api.cli.main --version
```

---

## 批量处理示例

### 处理目录下所有PDF
```bash
# Linux/Mac
python -m context_distiller.api.cli.main distill *.pdf --profile balanced

# Windows PowerShell
Get-ChildItem *.pdf | ForEach-Object {
    python -m context_distiller.api.cli.main distill $_.FullName
}
```

### 批量压缩并保存结果
```bash
for file in *.txt; do
    python -m context_distiller.api.cli.main distill "$file" -o "compressed_$file"
done
```

---

## 环境变量

可通过环境变量配置默认行为：

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| DISTILLER_PROFILE | 默认压缩模式 | balanced |
| DISTILLER_CONFIG | 配置文件路径 | config/default.yaml |

**示例**:
```bash
export DISTILLER_PROFILE=speed
python -m context_distiller.api.cli.main distill document.pdf
```

---

## 退出码

| 退出码 | 说明 |
|--------|------|
| 0 | 成功 |
| 1 | 一般错误 |
| 2 | 参数错误 |
| 3 | 文件不存在 |
