# REST API 参考文档

## 基础信息

**Base URL**: `http://localhost:8080`

**Content-Type**: `application/json`

---

## 端点列表

### 1. 健康检查

**GET** `/health`

检查服务状态。

**请求**: 无参数

**响应**:
```json
{
  "status": "ok"
}
```

**示例**:
```bash
curl http://localhost:8080/health
```

---

### 2. 文本/文档压缩

**POST** `/v1/distill`

压缩处理输入数据。

**请求体**:
```json
{
  "data": ["文本或文件路径"],
  "profile": "balanced",
  "user_id": "user123",
  "session_id": "session456"
}
```

**参数说明**:

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| data | array[string] | 是 | - | 待处理的数据列表 |
| profile | string | 否 | "balanced" | 压缩模式: speed/balanced/accuracy |
| user_id | string | 否 | null | 用户标识 |
| session_id | string | 否 | null | 会话标识 |

**响应**:
```json
{
  "optimized_prompt": [
    {
      "type": "text",
      "content": "压缩后的内容"
    }
  ],
  "stats": {
    "input_tokens": 1000,
    "output_tokens": 400,
    "compression_ratio": 0.6,
    "latency_ms": 150.5
  },
  "metadata": {
    "profile": "balanced"
  }
}
```

**示例**:
```bash
# 压缩文本
curl -X POST http://localhost:8080/v1/distill \
  -H "Content-Type: application/json" \
  -d '{
    "data": ["这是一段很长的文本内容..."],
    "profile": "speed"
  }'

# 处理文档
curl -X POST http://localhost:8080/v1/distill \
  -H "Content-Type: application/json" \
  -d '{
    "data": ["document.pdf"],
    "profile": "balanced"
  }'
```

---

### 3. 记忆检索

**POST** `/v1/memory/search`

检索用户记忆。

**Query参数**:

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| query | string | 是 | - | 检索查询文本 |
| top_k | integer | 否 | 5 | 返回结果数量 |

**响应**:
```json
{
  "chunks": [
    {
      "content": "记忆内容",
      "source": "file.py#L10"
    }
  ],
  "scores": [0.95, 0.87]
}
```

**示例**:
```bash
curl -X POST "http://localhost:8080/v1/memory/search?query=Python版本&top_k=5"
```

---

### 4. 存储记忆

**POST** `/v1/memory/store`

存储新的记忆片段。

**Query参数**:

| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| content | string | 是 | 记忆内容 |
| source | string | 是 | 来源标识 |
| metadata | object | 否 | 元数据（JSON字符串） |

**响应**:
```json
{
  "chunk_id": "123",
  "status": "stored"
}
```

**示例**:
```bash
curl -X POST "http://localhost:8080/v1/memory/store" \
  -d "content=项目使用Python 3.10" \
  -d "source=config.py#L1"
```

---

## 错误响应

所有端点在出错时返回标准错误格式：

```json
{
  "detail": "错误描述信息"
}
```

**HTTP状态码**:

| 状态码 | 说明 |
|--------|------|
| 200 | 成功 |
| 400 | 请求参数错误 |
| 404 | 资源不存在 |
| 500 | 服务器内部错误 |

---

## 启动服务

```bash
# 方式1: 直接启动
python -m context_distiller.api.server.app

# 方式2: 使用uvicorn
uvicorn context_distiller.api.server.app:app --host 0.0.0.0 --port 8080

# 方式3: 后台运行
nohup python -m context_distiller.api.server.app > api.log 2>&1 &
```

---

## 完整示例

### Python requests
```python
import requests

# 压缩文本
response = requests.post(
    "http://localhost:8080/v1/distill",
    json={
        "data": ["长文本内容"],
        "profile": "balanced"
    }
)
result = response.json()
print(f"压缩率: {result['stats']['compression_ratio']:.2%}")

# 检索记忆
response = requests.post(
    "http://localhost:8080/v1/memory/search",
    params={"query": "Python", "top_k": 3}
)
results = response.json()
for chunk in results['chunks']:
    print(chunk['content'])
```

### JavaScript fetch
```javascript
// 压缩文本
fetch('http://localhost:8080/v1/distill', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({
    data: ['长文本内容'],
    profile: 'balanced'
  })
})
.then(res => res.json())
.then(data => console.log(data.stats.compression_ratio));
```
