# 基于传统规则与NLP特征工程的上下文预处理插件设计方案

## 1. 背景与动机 (Motivation)

虽然深度学习和基于小模型的提示词压缩技术（如LLMLingua）在保留语义方面表现出色，但它们依然需要额外的端侧计算资源（甚至需要加载一个几十兆到几百兆的小语言模型）。在极度受限的端侧设备、或是对抗极端首字延迟（TTFT）的场景下，**基于传统规则（Rule-based）与经典NLP（Traditional NLP）**的预处理方案具备不可替代的优势：

- **零显存占用（Zero VRAM）**：完全基于CPU的字符串和数组操作。
- **极速执行（Lightning Fast）**：处理几千Token的文本仅需毫秒级，处理速度远高于任何神经网络。
- **高确定性与可控性（High Determinism）**：通过明确的规则进行正则替换或过滤，避免了“黑盒”压缩可能导致的幻觉或关键信息意外丢失。

因此，我们提出构建一套**类似 `scikit-learn` Pipeline 风格的 LLM 上下文预处理和特征提取工具库**，允许开发者像组装数据清洗流水线一样，组装大模型的上下文压缩规则。

---

## 2. 核心架构设计 (Architecture: The API)

设计理念完全借鉴成熟的 `sklearn.pipeline.Pipeline` 以及 `TransformerMixin`。开发者可以通过组合不同的 `BaseContextPreprocessor` 构建属于自己的压缩流。

### 2.1 整体 Pipeline 示例

```python
from context_compress.pipeline import ContextPipeline
from context_compress.preprocessing import (
    BoilerplateStripper,
    StopwordRemover,
    JSONMinifier,
    TFIDFFilter
)

# 构建一个端侧极速上下文压缩流水线
compress_pipeline = ContextPipeline([
    # 1. 结构清洗：去除HTML、多余空行、特殊无意义符号
    ('regex_cleaner', BoilerplateStripper(remove_html=True, collapse_whitespace=True)),
    
    # 2. 格式压缩：将散乱的JSON或Markdown过度格式化的部分进行紧凑化
    ('format_minifier', JSONMinifier()),
    
    # 3. 停用词/无用词过滤：基于轻量级词典
    ('stopword_remover', StopwordRemover(language='zh', aggressive=False)),
    
    # 4. 基于传统NLP的信息摘要：只保留TF-IDF权重最高的K个句子
    ('tfidf_sentence_filter', TFIDFFilter(top_k_sentences=10))
])

# 使用流水线：像传统机器学习一样 fit_transform
raw_context = "<div>这是一个非常长的...而且包含很多冗余格式和废话的原始输入数据...</div>"
compressed_context = compress_pipeline.transform(raw_context)
```

---

## 3. 具体处理模块设计 (Core Modules)

### 3.1 规则清洗层 (Rule-based Strippers)

利用强大的**正则表达式（Regex）**进行“硬压缩”。

- **`BoilerplateStripper`**：针对网页或特定系统的原始抓取数据。去除标签、导航栏残留、版权信息、连续换行符等。
- **`AbbreviationReplacer`**：缩写/别名替换器。利用哈希表字典，将冗长的专有名词替换为极简代称（如将“中国人民代表大会”替换为“人大”，将“人工智能微调”替换为“SFT”），这可以在几乎不丢信息的情况下降低Token消耗。

### 3.2 停用词与实体过滤层 (Lexical Filtering)

结合分词（如 `jieba` 或轻量级正则分词）与词典映射。

- **`StopwordRemover`**：虽然现代LLM依赖停用词理解语气（如“可能”、“不是”），但在长文档问答（RAG）作为背景知识注入时，背景知识中的过度修饰词（如“的”、“地”、“得”、“其实”、“然后”）可以被大胆剔除。
  - *策略参数 `aggressive=True/False`*：开启Aggressive时，甚至剔除虚词和标点，仅保留名词和动词核心实体组合，变成“电报体”（Telegram Style）。LLM依然具备从电报体中还原语义的强大能力。

### 3.3 传统机器学习/NLP打分层 (Statistical/Traditional ML)

这部分直接对标 `sklearn.feature_extraction.text`。

- **`TFIDFFilter` / `BM25Filter`**：
  - 当上下文特别长（例如一本手册），且没有算力对这本手册做向量嵌入（Embedding）时。
  - 直接在内存中使用 `CountVectorizer` 和 `TfidfTransformer`，将长文档按句/段切割。计算 Query 和每一段的 TF-IDF 相似度（余弦相似度），或使用传统的 BM25 算法进行文本匹配。
  - **优势**：这是完全无需神经网络的硬提取，将与 Query 无关的自然段提前丢弃，实现降维打击。

### 3.4 结构化压缩层 (Structural Minification)

端侧模型经常需要处理结构化数据（如JSON API的返回结果或表格）。

- **`JSONMinifier` / `XMLMinifier`**：去掉JSON的缩进、换行甚至某些不重要的Keys。
- **`TableCompressor`**：将Markdown表格转化为紧凑的CSV样板，使用特定的分隔符（如 `|` 变成 `,`），减少空白 Token 的过度消耗。

---

## 4. 与深度学习压缩方案的对比 (Pros & Cons)

| 维度 | `sklearn`风格规则处理 | 基于小型LLM的压缩(LLMLingua) |
| :--- | :--- | :--- |
| **计算资源需求** | **极低 (纯CPU，数MB内存)** | 中等 (需小模型部署，数GB显存) |
| **执行速度 (TTFT贡献)** | **极快 (毫秒级, <10ms)** | 较快 (几百毫秒 - 1秒) |
| **压缩率** | 较低至中等 (20% - 50%减少) | **极高 (可达 80% - 90%减少)** |
| **语义保留能力** | 依赖规则设计，存在丢失细节风险 | **根据信息困惑度智能保留核心语义** |
| **多模态扩展性** | 弱（仅能处理文本与格式） | 较强（可基于多模态模型设计） |

## 5. 总结与开发建议

在构建我们自己的上下文压缩框架时，我们不应只依赖高级模型。最完美的端侧架构应该是**混合式的（Hybrid）**：

1. **第一炮 (L0级压缩)**：使用本套 `sklearn` 风格的轻量化 Pipeline 瞬间清洗掉无用格式和绝对废话。
2. **第二炮 (L1级压缩)**：如果清洗后依然超长，再触发基于小语言模型（如 Token Entropy 困惑度算法）的智能压缩。
3. **最终流向大模型**。

采用这种漏斗式过滤，既确保了最大的灵活性，又能在极致压缩下保护端侧极为珍贵的计算资源。我们将这套规则引擎实现在 `context_compress.preprocessing` 包中。
