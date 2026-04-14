# 上下文压缩算法全景：从 1958 到 2026

> 一份覆盖 NLP 领域 70 年文本压缩/摘要/Prompt 压缩技术演进的系统性技术梳理
> 配合 Context Distiller v2.0 四档压缩 (L0–L3) 的设计决策说明

---

## 目录

- [一、总论：为什么要压缩上下文](#一总论为什么要压缩上下文)
- [二、算法演进全景时间线](#二算法演进全景时间线)
- [三、第一代：启发式抽取 (1958–1970s)](#三第一代启发式抽取-19581970s)
- [四、第二代：统计与信息检索方法 (1990s–2000s)](#四第二代统计与信息检索方法-1990s2000s)
- [五、第三代：矩阵分解与代数方法 (2000s)](#五第三代矩阵分解与代数方法-2000s)
- [六、第四代：图排序方法 (2004–2010s)](#六第四代图排序方法-20042010s)
- [七、第五代：主题建模 (2003–2010s)](#七第五代主题建模-20032010s)
- [八、第六代：神经抽取式摘要 (2015–2019)](#八第六代神经抽取式摘要-20152019)
- [九、第七代：Seq2Seq 生成式摘要 (2015–2018)](#九第七代seq2seq-生成式摘要-20152018)
- [十、第八代：预训练模型摘要 (2019–2021)](#十第八代预训练模型摘要-20192021)
- [十一、第九代：硬提示词压缩 (2023–2025)](#十一第九代硬提示词压缩-20232025)
- [十二、第十代：软提示/嵌入空间压缩 (2023–2025)](#十二第十代软提示嵌入空间压缩-20232025)
- [十三、第十一代：KV Cache 压缩 (2023–2026)](#十三第十一代kv-cache-压缩-20232026)
- [十四、第十二代：LLM 原生与 Agent 压缩 (2024–2026)](#十四第十二代llm-原生与-agent-压缩-20242026)
- [十五、全景对比与 Context Distiller 映射](#十五全景对比与-context-distiller-映射)
- [十六、业务选型决策树](#十六业务选型决策树)
- [十七、参考文献](#十七参考文献)

---

## 一、总论：为什么要压缩上下文

### 核心矛盾

大语言模型 (LLM) 的能力与其上下文窗口之间存在根本性矛盾：

```
信息供给侧                              信息消费侧
┌─────────────┐                      ┌─────────────┐
│ 用户输入      │                      │   LLM       │
│ - 长文档 10万字│     窗口瓶颈          │ - 窗口 4K~128K│
│ - 多轮对话    │  ──────────→         │ - 注意力稀释  │
│ - 工具返回值   │  需要压缩 !!          │ - 按Token计费 │
│ - 图片/截图   │                      │ - 延迟正比长度 │
└─────────────┘                      └─────────────┘
```

### 压缩的四重收益

| 收益维度 | 具体表现 |
|---------|---------|
| **降本** | 减少 40%–80% Token 消耗，直接降低 API 调用费用 |
| **提速** | 输入越短，首 Token 延迟 (TTFT) 越低，端侧 7B 模型体感明显 |
| **增效** | 去除噪声后 LLM 注意力更集中，回答精度反而提升 (*less is more*) |
| **扩容** | 让超长内容"塞进"小窗口模型，突破物理限制 |

### 压缩的核心挑战

> **在缩短文本的同时，不丢失对下游任务至关重要的信息。**

压缩率越高，信息损失风险越大，需要越强的语义理解能力来判断"什么该留、什么该丢"。整部 NLP 压缩史就是围绕这个取舍展开的。

### 两大范式：抽取式 vs 生成式

在进入具体算法之前，需要理解贯穿全文的两大范式：

```
抽取式 (Extractive):  从原文中挑选片段，不改动原始措辞
生成式 (Abstractive):  理解语义后用新措辞重写

原文: "上海今天22度，东南风3级，湿度65%。明天可能转阴。建议带伞。紫外线偏高注意防晒。"

抽取式 → "上海今天22度。建议带伞。"          (原句子集，信息可能不连贯)
生成式 → "上海今日22度晴，明天转阴有雨，注意带伞防晒。" (信息更密，但措辞全新)
```

| 维度 | 抽取式 | 生成式 |
|------|-------|-------|
| 忠实度 | 高——原文不变 | 有幻觉风险 |
| 压缩率上限 | 受限于原句粒度 | 理论无上限 |
| 确定性 | 高 | 低（同输入可能不同输出） |

第一代到第九代主要是**抽取式**，第七代起出现**生成式**，第十二代两者融合。

---

## 二、算法演进全景时间线

```
1958      1990s      2000s       2004      2003-10s    2015-19
  │         │          │          │          │           │
  ▼         ▼          ▼          ▼          ▼           ▼
┌─────┐ ┌───────┐ ┌────────┐ ┌───────┐ ┌───────┐ ┌──────────┐
│ G1  │ │  G2   │ │  G3    │ │  G4   │ │  G5   │ │ G6 & G7  │
│启发式│ │统计/IR│ │矩阵分解│ │图排序 │ │主题建模│ │神经网络  │
│Luhn │ │TF-IDF │ │LSA/SVD │ │Text-  │ │LDA    │ │Extractive│
│Edm. │ │BM25   │ │        │ │Rank   │ │       │ │& Seq2Seq │
│     │ │MMR    │ │        │ │LexRank│ │       │ │Abstractive│
└──┬──┘ └──┬────┘ └───┬────┘ └──┬────┘ └──┬────┘ └────┬─────┘
   │       │          │         │         │            │
   └───────┴──────────┴─────────┴─────────┴────────────┘
   "文本摘要" 时代 (Summarization) ── 问题定义相对稳定


2019-21    2023-24        2023-25         2023-26       2024-26
  │          │              │               │             │
  ▼          ▼              ▼               ▼             ▼
┌──────┐ ┌─────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
│  G8  │ │   G9    │ │   G10    │ │   G11    │ │   G12    │
│预训练 │ │硬Prompt │ │软Prompt  │ │KV Cache  │ │LLM/Agent │
│BART  │ │压缩     │ │嵌入压缩  │ │压缩      │ │原生压缩  │
│T5    │ │Selective│ │Gist     │ │Streaming │ │LLM 摘要  │
│PEGASUS││LLMLingua│ │AutoComp │ │LLM/H2O  │ │ACON     │
│      │ │LLMLingua│ │ICAE    │ │SnapKV   │ │Sliding  │
│      │ │-2      │ │500x    │ │         │ │Window   │
└──┬───┘ └───┬────┘ └────┬────┘ └────┬────┘ └────┬─────┘
   │         │           │           │            │
   └─────────┴───────────┴───────────┴────────────┘
   "上下文压缩" 时代 (Context Compression) ── LLM 驱动的新需求
```

**演进的核心逻辑**：从"不理解文本"到"浅层统计"到"深度语义"，每一代用更强的理解能力换取更高的压缩率和更低的信息损失。2023 年是分水岭——问题从"如何做文本摘要"转变为"如何让 LLM 用更少的 Token 获得同样的信息"。

---

## 三、第一代：启发式抽取 (1958–1970s)

> 这是自动文本摘要的**起源**。文档的原版本错误地将这一代等同于"停用词过滤 + 正则清洗"——实际上，停用词过滤只是 Luhn 方法的一个子步骤，而非独立的一代。

### 3.1 Luhn 方法 (1958) — 自动摘要的鼻祖

**论文**：*The Automatic Creation of Literature Abstracts* (H.P. Luhn, IBM, 1958)

这是人类历史上**第一个自动文本摘要系统**，运行在 IBM 704 上。

**核心思想**：一个句子如果包含越多的"重要词汇"且这些词汇越集中，这个句子就越重要。

**算法流程**：

```
Step 1: 预处理
        原文 → 分词 → 移除停用词 → 词干还原 (stemming)

Step 2: 计算词频
        统计每个词的出现次数，高频词 = "重要词"
        (排除过高频的通用词 和 过低频的罕见词)

Step 3: 句子打分 — "显著因子" (Significance Factor)
        对每个句子：
        - 找出所有"重要词"的位置
        - 计算重要词之间的"距离"
        - 重要词越密集 → 得分越高

Step 4: 排序取 Top-K
        按得分降序，取前 N 个句子作为摘要
```

**业务逻辑**：Luhn 的直觉是——如果一个句子里重要词扎堆出现（密度高），那这个句子大概率是在讨论文章的核心议题。

**历史意义**：确立了抽取式摘要的基本范式——"给句子打分 → 排序 → 取 Top-K"，此后 60 多年的大部分抽取式方法都遵循这个框架。

---

### 3.2 Edmundson 方法 (1969) — 多特征融合

**论文**：*New Methods in Automatic Extracting* (H.P. Edmundson, JACM, 1969)

Edmundson 发现仅靠词频不够，提出了**四特征打分法**：

| 特征 | 权重 | 含义 |
|------|------|------|
| **线索词 (Cue words)** | 高 | 包含 "结论"、"重要"、"总之" 等指示性词汇的句子更重要 |
| **标题词 (Title words)** | 高 | 与文章标题/小标题共享关键词的句子更重要 |
| **位置 (Location)** | 中 | 段落首句/末句、文章开头/结尾的句子更重要 |
| **词频 (Frequency)** | 低 | Luhn 的词频方法（实验发现其贡献最小） |

```
句子得分 = w₁ × 线索词分 + w₂ × 标题词分 + w₃ × 位置分 + w₄ × 词频分
```

**关键发现**：实验表明**线索词和位置**比纯词频更有效。这一洞察至今仍有价值——BERT 等现代模型的注意力机制中也隐式地学到了"位置很重要"这一先验。

---

### 3.3 规则清洗：作为预处理步骤的延续

停用词过滤和正则清洗**不是独立的一代算法**，而是从 Luhn 开始就存在的预处理步骤，并延续至今：

| 技术 | 用途 | 角色 |
|------|------|------|
| 停用词过滤 | 移除 "the/a/的/了" 等高频低义词 | 所有后续方法的前置步骤 |
| 正则清洗 | 合并空白、去除 HTML/Markdown 标签 | 数据清洗，非压缩算法 |
| 词干还原 (Stemming) | running → run | 减少词形变体 |

**Context Distiller L0 (speed)** 将这些预处理步骤独立为一个档位，不是因为它本身是一代完整的压缩算法，而是工程上对**"零模型依赖、零延迟"**场景的兜底方案。

---

## 四、第二代：统计与信息检索方法 (1990s–2000s)

> 核心转变：从"手工定义什么重要"到"用数学计算什么更重要"。

### 4.1 TF-IDF (1972/1988)

**全称**：Term Frequency - Inverse Document Frequency

**核心思想**：一个词在当前文档中高频出现 (TF 高)，但在语料库中罕见 (IDF 高)，则对当前文档更重要。

```
TF-IDF(t, d, D) = TF(t, d) × IDF(t, D)
                = (词t在文档d中出现次数 / 文档d总词数) × log(语料库文档总数 / 含词t的文档数)
```

| 词语 | TF | IDF | TF-IDF | 判断 |
|------|-----|-----|--------|------|
| "的" | 高 | 低 (到处都有) | 低 | 不重要 |
| "量子计算" | 中 | 高 (罕见) | **高** | **重要** |

**局限**：需要语料库计算 IDF；不理解词义（"苹果公司" = "苹果水果"）；忽略词序。

---

### 4.2 BM25 (1994/2009)

**全称**：Okapi Best Matching 25

TF-IDF 的改进版，增加了两个关键改进：

| 改进 | 说明 |
|------|------|
| **词频饱和** | 一个词出现 100 次不比 10 次重要 10 倍——引入饱和函数 |
| **长度归一化** | 长文档天然 TF 高——引入文档长度归一化消除偏见 |

BM25 至今仍是 Elasticsearch、SQLite FTS5 等搜索引擎的核心排序算法。在 Context Distiller 中用于 OpenClaw 长期记忆的全文检索召回。

---

### 4.3 MMR — 最大边际相关 (1998)

**论文**：*The Use of MMR, Diversity-Based Reranking for Reordering Documents and Producing Summaries* (Carbonell & Goldstein, SIGIR 1998)

**核心思想**：选句子时不仅要**和查询相关**，还要**和已选句子不同**——平衡相关性与多样性。

```
MMR = arg max [ λ × Sim(s, Query) - (1-λ) × max Sim(s, 已选句子) ]
        s∈候选集

λ = 1.0: 纯相关性（可能选出高度重复的句子）
λ = 0.0: 纯多样性（可能选出不相关的句子）
λ = 0.7: 常用值，偏向相关但避免冗余
```

**历史意义**：首次系统性地提出了**反冗余**机制。现代 RAG 管道中的去重、LLM 检索中的 diversity re-ranking 都可以追溯到 MMR。

---

### 4.4 SumBasic (2007) 与 KL-Sum (2009)

| 方法 | 核心思想 |
|------|---------|
| **SumBasic** | 贪心选择"平均词概率最高"的句子，选后降低已选词的概率以避免冗余。极其简单但效果出奇好的基线 |
| **KL-Sum** | 贪心添加句子，使摘要的词分布与原文的词分布之间的 **KL 散度**最小化。信息论视角的摘要方法 |

---

### 4.5 句子压缩 — 删减而非选择 (2000–2002)

**论文**：*Statistics-Based Summarization* (Knight & Marcu, 2000/2002)

**核心思想**：不是选择完整句子，而是**修剪单个句子**——删除修饰语、从句等非核心成分，保留句子骨架。

```
原句: "昨天在上海举行的一场非常重要的国际会议上，多位知名专家讨论了气候变化问题。"
       ↓ 句法树剪枝
压缩: "会议上专家讨论了气候变化问题。"
```

**方法**：解析句法树 (parse tree)，用统计模型或噪声信道模型决定删除哪些子树。

**历史意义**：桥接了抽取式和生成式——输出不是原句子集合，但也不是全新生成的，而是原句的"剪枝版"。这一思路是后来 Token 级压缩 (LLMLingua-2) 的精神前驱。

---

## 五、第三代：矩阵分解与代数方法 (2000s)

### 5.1 LSA/LSI 摘要 (2001/2004)

**论文**：*Automatic Text Summarization Using Latent Semantic Analysis* (Gong & Liu, 2001; Steinberger & Jezek, 2004)

**核心思想**：用线性代数发现文本中的**潜在语义结构**——哪些词经常一起出现？哪些句子代表了相似的主题？

**算法流程**：

```
Step 1: 构建 "词-句子" 矩阵 A
        行 = 词汇表中的每个词
        列 = 文档中的每个句子
        A[i][j] = 词i在句子j中的 TF-IDF 权重

Step 2: 奇异值分解 (SVD)
        A = U × Σ × V^T
        Σ 中的奇异值从大到小排列，对应潜在"主题"的重要性
        V 的每一行表示一个句子在各主题上的分布

Step 3: 选择句子
        对每个主要主题（前 k 个奇异值），选择在该主题上
        得分最高的句子，确保摘要覆盖所有重要主题
```

**直觉理解**：想象一篇论文讨论了 3 个主题——SVD 发现这 3 个主题，然后从每个主题中各选出最有代表性的句子。

**业务逻辑**：解决了 TF-IDF 的一个根本问题——TF-IDF 只看词频，无法发现"深度学习"和"神经网络"语义相关。LSA 通过矩阵分解捕捉了这种**潜在语义关联**。

**局限**：SVD 计算开销大 O(mn²)；无法处理多义词；结果可解释性差。

---

## 六、第四代：图排序方法 (2004–2010s)

### 6.1 TextRank (2004)

**论文**：*TextRank: Bringing Order into Texts* (Mihalcea & Tarau, 2004)

**核心思想**：把 Google PageRank 搬到文本上——句子是节点，句子间相似度是边，通过迭代投票找出最"中心"的句子。

```
Step 1: 句子切分 → S1, S2, S3, S4, S5
Step 2: 计算每对句子的相似度（词重叠率）→ 构建图
Step 3: 迭代 PageRank 算法 → 每个句子获得一个"重要性得分"
Step 4: 取 Top-K 句子
```

**PageRank 直觉**：如果很多"重要的"句子都和你相似，那你也很重要。

---

### 6.2 LexRank (2004) — TextRank 的"实力对手"

**论文**：*LexRank: Graph-based Lexical Centrality as Salience in Text Summarization* (Erkan & Radev, JAIR 2004)

**与 TextRank 的区别**：

| 维度 | TextRank | LexRank |
|------|---------|---------|
| 相似度计算 | 词重叠归一化 | **TF-IDF 向量的余弦相似度** |
| 相似度阈值 | 无 | 设定阈值，低于阈值的边不连 |
| 多文档 | 单文档 | **多文档**（设计目标） |
| 冗余处理 | 无 | 考虑信息覆盖 |

LexRank 在 DUC 2004 评测中获得第一名，是 2000 年代最具影响力的摘要方法之一。

---

### 6.3 DivRank (2010)

**论文**：Mei, Guo & Radev (2010)

在 PageRank 基础上引入**时变随机游走**，同时优化中心性和多样性——避免选出的句子高度重复。

---

## 七、第五代：主题建模 (2003–2010s)

### 7.1 LDA 摘要

**论文**：*Latent Dirichlet Allocation* (Blei, Ng & Jordan, 2003)

**核心思想**：假设每篇文档是多个"潜在主题"的混合物，每个主题是一组词的概率分布。LDA 发现这些潜在主题，然后选择最能代表各主题的句子。

```
文档 = 主题A (40%) + 主题B (35%) + 主题C (25%)

主题A ("技术"): [深度学习:0.3, 模型:0.2, 训练:0.15, ...]
主题B ("商业"): [收入:0.25, 市场:0.2, 增长:0.18, ...]
主题C ("政策"): [监管:0.3, 合规:0.2, 法规:0.15, ...]

→ 从每个主题选出最具代表性的句子 → 摘要覆盖所有主题
```

**与 LSA 的对比**：

| 维度 | LSA | LDA |
|------|-----|-----|
| 数学框架 | 线性代数 (SVD) | 概率图模型 (贝叶斯) |
| 主题表示 | 实数向量（可能为负） | **概率分布**（可解释为"词的概率"） |
| 可解释性 | 差 | **好**（每个主题是一组词） |
| 生成模型 | 否 | **是**（可以生成新文档） |

**业务逻辑**：LDA 的最大优势是可解释性——你可以看到"这篇文档 40% 在讲技术、35% 在讲商业"，然后从每个主题中挑选句子，确保摘要的主题多样性。

---

## 八、第六代：神经抽取式摘要 (2015–2019)

> 核心转变：从手工设计特征到**让神经网络自动学习什么是"好的摘要句"**。

### 8.1 SummaRuNNer (2017)

**论文**：*SummaRuNNer: A Recurrent Neural Network based Sequence Model for Extractive Summarization* (Nallapati et al., AAAI 2017)

**核心思想**：将抽取式摘要建模为**序列二分类问题**——按顺序读取每个句子，对每个句子预测"选 (1) / 不选 (0)"。

```
文档: [S1, S2, S3, S4, S5]
        ↓ 双向 RNN 编码
编码: [h1, h2, h3, h4, h5]   ← 每个句子获得一个向量表示
        ↓ 二分类器
预测: [ 1,  0,  1,  0,  1]   ← 选中 S1, S3, S5 组成摘要
```

**关键创新**：分类时不仅考虑句子本身的内容，还考虑：
- 句子与文档整体的相关性
- 句子的位置信息（首段权重更高）
- 与已选句子的冗余度（新颖性）

---

### 8.2 BertSum / PreSumm (2019)

**论文**：*Fine-tuning BERT for Extractive Summarization* (Liu & Lapata, EMNLP 2019)

**核心思想**：在句子之间插入 `[CLS]` 标记，让 BERT 同时理解所有句子，然后用 `[CLS]` 位置的表示来做句子级分类。

```
输入: [CLS] S1 [SEP] [CLS] S2 [SEP] [CLS] S3 [SEP] ...
                ↓ BERT 编码
         对每个 [CLS] 位置的输出做二分类 → 选/不选
```

**历史意义**：首次将**预训练表示** (BERT) 引入摘要任务。证明了大规模预训练学到的语义表示可以显著提升下游抽取任务。这一思路直接启发了后来 LLMLingua-2 使用 XLM-RoBERTa（BERT 家族）做 Token 级分类。

---

## 九、第七代：Seq2Seq 生成式摘要 (2015–2018)

> 范式转折点：从"从原文中选"到"让模型自己写"。

### 9.1 注意力摘要 (2015) — 神经生成式摘要的起点

**论文**：*A Neural Attention Model for Abstractive Sentence Summarization* (Rush, Chopra & Weston, EMNLP 2015)

**核心思想**：用编码器-解码器 (Encoder-Decoder) 架构，编码器读取原文，解码器生成新的摘要句。引入**注意力机制**让解码器在生成每个词时"回看"原文的不同部分。

```
原文: "上海今天天气晴朗，气温22度，东南风3级"
        ↓ 编码器 (LSTM/GRU)
        ↓ 注意力: 生成"气温"时重点关注原文中的"22度"
        ↓ 解码器 (LSTM/GRU)
摘要: "上海今日22度晴"    ← 全新生成的句子
```

**历史意义**：证明了神经网络可以生成**原文中不存在的新表达**，开启了生成式摘要时代。

---

### 9.2 Pointer-Generator Network (2017) — 解决事实准确性

**论文**：*Get to the Point: Summarization with Pointer-Generator Networks* (See, Liu & Manning, ACL 2017)

**核心问题**：纯生成式模型有两大毛病：
1. **事实错误**：生成"32度"而原文是"22度"（因为"32"也在词汇表中）
2. **重复生成**：反复输出相同的短语

**核心创新 — 混合架构**：

```
                     ┌─── 生成器: 从词汇表中选词 (创造新表达)
解码每个词时 →  切换门 p_gen ─┤
                     └─── 指针: 直接从原文中复制词 (保证事实准确)

p_gen ≈ 1.0 → 用自己的话说 (适合连接词、虚词)
p_gen ≈ 0.0 → 直接复制 (适合人名、数字、专有名词)
```

**覆盖机制 (Coverage)**：维护一个"注意力历史"向量，已经被关注过的位置在后续步骤中被降权，避免重复关注同一段文本导致重复生成。

**历史意义**：成为此后数年生成式摘要的主流基线。"复制 + 生成"的混合思路影响了大量后续工作。

---

## 十、第八代：预训练模型摘要 (2019–2021)

> 核心转变：不再从头训练，而是在大规模预训练模型上做微调 (fine-tuning)。

### 10.1 BART (2019)

**论文**：*BART: Denoising Sequence-to-Sequence Pre-training for Natural Language Generation, Translation, and Comprehension* (Lewis et al., Facebook AI, 2019)

**核心思想**：将文本**打乱/破坏**（遮盖、删除、重排句子），然后训练模型恢复原文。预训练阶段就在学习"理解和重写"。

```
预训练噪声策略:
  - Token 遮盖:   "上海[MASK]22度"     → 恢复 "上海今天22度"
  - Token 删除:   "上海22度"           → 恢复 "上海今天22度"
  - 句子重排:     "带伞。今天22度。"    → 恢复 "今天22度。带伞。"
  - 文本填充:     "上海___度"           → 恢复 "上海今天22度"
```

**架构**：双向编码器 (类 BERT) + 自回归解码器 (类 GPT)，结合两者优势。

---

### 10.2 T5 (2019/2020)

**论文**：*Exploring the Limits of Transfer Learning with a Unified Text-to-Text Transformer* (Raffel et al., Google, 2020)

**核心思想**：将**所有 NLP 任务统一为文本到文本的格式**。摘要任务只需在输入前加上前缀 `"summarize: "`。

```
输入: "summarize: 上海今天天气晴朗，气温22度..."
输出: "上海今日22度晴，注意防晒。"
```

---

### 10.3 PEGASUS (2020) — 专为摘要设计的预训练

**论文**：*PEGASUS: Pre-training with Extracted Gap-sentences for Abstractive Summarization* (Zhang et al., Google/ICL, 2020)

**核心创新 — Gap Sentence Generation (GSG)**：

```
预训练目标: 从文档中随机删除整个句子，训练模型生成这些被删掉的句子

原文:  "S1. S2. S3. S4. S5."
输入:  "S1. [MASK]. S3. [MASK]. S5."
目标:  "S2. S4."
```

**直觉**：预训练时学习"补全缺失的句子" ≈ 微调时学习"生成文档摘要"——两个任务本质相似。

**效果**：在低资源场景下（仅数百条标注数据）就能达到很好的摘要效果。

---

### 10.4 这一代与"LLM 摘要"的区别

| 维度 | 预训练摘要模型 (BART/T5/PEGASUS) | LLM 直接摘要 (GPT-4/Qwen) |
|------|-------------------------------|--------------------------|
| 模型规模 | 400M–11B 参数 | 7B–数千亿参数 |
| 训练方式 | 在摘要数据集上**专门微调** | 零样本/少样本，**无需微调** |
| 部署成本 | 可本地部署 | 大模型需强大 GPU 或 API |
| 摘要质量 | 在特定领域表现优秀 | 泛化能力更强 |
| 可控性 | 模型固定，难调控风格 | 通过 Prompt 灵活控制 |

---

## 十一、第九代：硬提示词压缩 (2023–2025)

> 2023 年的分水岭：问题从"文本摘要"变为"**Prompt 压缩**"——目标不再是生成人类可读的摘要，而是生成**LLM 可理解且信息无损的压缩文本**。

### 11.1 SelectiveContext (2023) — 自信息量过滤

**论文**：*Compressing Context to Enhance Inference Efficiency of LLMs* (Li et al., EMNLP 2023)

**核心思想**：用 GPT-2 小模型计算每个句子的"自信息量" (self-information)，低信息量（可预测）的内容对 LLM 理解贡献小，可安全移除。

**信息论基础 — 自信息量**：

```
I(token) = -log₂ P(token | context)

P 越高 (越可预测) → I 越低 → 可删除
P 越低 (越意外)   → I 越高 → 必须保留
```

| 上下文 | 下一个词 | 概率 P | 自信息 I | 判断 |
|--------|---------|--------|----------|------|
| "今天天气" | "很好" | 0.4 | 1.3 bits | 低信息量，可预测 |
| "今天天气" | "导致航班取消" | 0.001 | 10 bits | 高信息量，意外 |

**算法流程**：

```
输入文本 → 按句切分 → GPT-2 计算每句平均自信息 → 降序排列 → 保留 Top-(1-ratio) → 输出
```

**为什么用 GPT-2？** 只需要它的概率分布，不需要它的生成能力。124M 参数的小模型完全够用。

**Context Distiller L1 (selective)** 实现了此算法。

---

### 11.2 LLMLingua (2023) — 粗到细压缩

**论文**：*LLMLingua: Compressing Prompts for Accelerated Inference of LLMs* (Jiang et al., EMNLP 2023)

相比 SelectiveContext 的关键改进：

| 改进 | 说明 |
|------|------|
| **预算控制器** | 在 instruction / demonstration / question 之间智能分配压缩预算 |
| **Token 级迭代** | 不只是句子级，支持 Token 级别的细粒度压缩 |
| **分布对齐** | 通过指令微调让小模型（LLaMA-7B）的概率分布对齐大模型 |

---

### 11.3 LLMLingua-2 (2024) — 从间接推断到直接学习

**论文**：*LLMLingua-2: Data Distillation for Efficient and Faithful Task-Agnostic Prompt Compression* (Pan et al., ACL 2024)

**本质突破**：前面的方法都是"间接利用"语言模型的概率来推断重要性。LLMLingua-2 直接训练一个分类器回答"这个 token 该保留还是丢弃"。

**训练过程**：

```
Step 1: 数据蒸馏
        原文 → GPT-4 → "请压缩为原来的 50%"
        GPT-4 返回压缩版本

Step 2: Token 级标注
        原文:   "今天 上海 的 天气 非常 好 ， 温度 大约 22 度 左右"
        压缩版: "上海 天气 好 温度 22 度"
        标签:    0    1    0   1    0   1  0   1    0   1  1   0
                              (保留=1, 丢弃=0)

Step 3: 训练分类器
        模型: XLM-RoBERTa-Large (355M, 多语言)
        任务: Token 二分类
        损失: 二元交叉熵
```

**推理过程**：

```
输入文本 → XLM-RoBERTa (ONNX + INT8) → 每 Token 保留概率 p → 按 rate 保留 → 拼接输出
```

**相比前代的质的飞跃**：

```
SelectiveContext (间接)          LLMLingua-2 (直接)
┌──────────────────┐           ┌──────────────────┐
│ 用语言模型的概率    │           │ 专门训练分类器      │
│ 间接推断重要性      │    →      │ 直接判断保留/丢弃  │
│ 句子级             │           │ Token 级          │
│ 英文主导           │           │ 多语言            │
└──────────────────┘           └──────────────────┘
```

**Context Distiller L2 (balanced)** 实现了此算法，是默认推荐档位。

---

### 11.4 LongLLMLingua (2024) — 长上下文 + 查询感知

**论文**：*LongLLMLingua: Accelerating and Enhancing LLMs in Long Context Scenarios via Prompt Compression* (Jiang et al., ACL 2024)

针对 RAG (检索增强生成) 场景的改进：

| 改进 | 说明 |
|------|------|
| **查询感知压缩** | 压缩时考虑用户的问题，保留与问题最相关的内容 |
| **文档重排** | 将最相关文档放在前面和后面，缓解"Lost in the Middle"效应 |
| **动态压缩比** | 不同文档按相关性分配不同的压缩预算 |
| **子序列恢复** | 压缩后可恢复原始 token 位置映射 |

---

### 11.5 CPC — 上下文感知 Prompt 压缩 (2025)

**论文**：*Context-aware Prompt Compression* (Liskavets et al., AAAI 2025)

**核心思想**：训练一个上下文感知的句子编码器，根据给定问题对句子做相关性打分，比 LLMLingua 系列快 10x+。

---

## 十二、第十代：软提示/嵌入空间压缩 (2023–2025)

> 与前面所有方法根本不同：不是删减离散 token，而是将文本压缩成**连续向量表示**。

### 12.1 为什么需要"软压缩"？

硬压缩（删 token）有天然上限——删太多就不像人话了，LLM 也读不懂。如果能把信息编码到向量空间中，理论上一个向量可以代表无限长的文本。

```
硬压缩: "上海今天22度晴" (离散 tokens, 人类可读)
软压缩: [0.23, -0.41, 0.87, ...] (连续向量, 仅 LLM 可读)
```

---

### 12.2 Gist Tokens (2023)

**论文**：*Learning to Compress Prompts with Gist Tokens* (Mu et al., 2023)

**核心思想**：在指令末尾添加几个特殊的 "gist" token，微调 LLM 让它把整个指令的信息"压缩"到这几个 token 的激活状态中。

```
原始: "You are a helpful assistant that answers concisely..." (30 tokens)
       ↓ 微调后
压缩: [GIST_1] [GIST_2]  (2 tokens, 信息等效)
```

**局限**：只能压缩短指令（约 30 tokens），需要微调 LLM。

---

### 12.3 AutoCompressor (2023)

**论文**：*Adapting Language Models to Compress Contexts* (Chevalier et al., 2023)

**核心思想**：递归地将长文本分段，每段压缩成"摘要向量"，前传给下一段。

```
文档 (30K tokens) → 分为 6 段 × 5K tokens
段1 → 压缩为 summary_vec_1 → 传给段2处理 → 压缩为 summary_vec_2 → ...
最终: [summary_vec_1, summary_vec_2, ..., summary_vec_6] (几百维代替 30K tokens)
```

---

### 12.4 ICAE — 上下文自编码器 (2024)

**论文**：*In-context Autoencoder for Context Compression in a Large Language Model* (Ge et al., 2024)

**核心思想**：用 LoRA 微调的编码器将上下文压缩成紧凑的 "memory slots"，原始 LLM（冻结）作为解码器使用这些 slots。不改变 LLM 权重，只加适配层。

---

### 12.5 500xCompressor (2025)

**论文**：*500xCompressor: Generalized Prompt Compression for Large Language Models* (Li et al., ACL 2025)

**核心突破**：将 500 个 token 压缩成**1 个**特殊 token，实现极端压缩比。

```
500 tokens → 1 个 [COMP] token (KV-value 表示, 非简单 embedding)
压缩比: 6x ~ 500x
额外参数: 仅 0.3%
```

**关键技术**：不仅存储 token embedding，还存储 KV-value 表示（键值对），保留更多信息。

---

### 12.6 软压缩的局限

| 局限 | 说明 |
|------|------|
| **不可读** | 压缩结果是向量，人类无法审查 |
| **需要微调** | 大部分方法需要微调 LLM 或训练适配层 |
| **不兼容黑盒 API** | 无法通过 GPT-4/Claude API 使用（API 只接受文本） |
| **跨模型不通用** | 为 LLaMA 训练的压缩器不能用在 Qwen 上 |

**Context Distiller 为什么不用软压缩？** 因为我们的目标场景是通过 Ollama API 与 LLM 交互，只能传递离散文本。但软压缩是一个值得关注的前沿方向。

---

## 十三、第十一代：KV Cache 压缩 (2023–2026)

> 完全不同的切入角度：不是压缩"输入了什么"，而是压缩"推理时记住什么"。

### 13.1 背景：KV Cache 是什么？

Transformer 推理时，每一层的注意力机制需要存储之前所有 token 的 Key 和 Value 向量（称为 KV Cache）。上下文越长，KV Cache 越大，GPU 显存越紧张。

```
推理过程:
Token 1 → 存 KV₁
Token 2 → 存 KV₂, 注意力看 [KV₁, KV₂]
Token 3 → 存 KV₃, 注意力看 [KV₁, KV₂, KV₃]
...
Token N → 存 KVₙ, 注意力看 [KV₁, KV₂, ..., KVₙ]  ← 显存 O(N)
```

### 13.2 StreamingLLM (2023)

**论文**：*Efficient Streaming Language Models with Attention Sinks* (Xiao et al., 2023)

**核心发现**："注意力沉没" (Attention Sink) 现象——LLM 会把大量注意力分配给**序列最开头的几个 token**，无论它们的实际内容是什么。

**算法**：保留"沉没 token"（开头几个）+ 滑动窗口（最近的几百个），驱逐中间的 KV 缓存。支持理论上无限长的流式推理。

```
保留: [Sink₁, Sink₂, Sink₃, Sink₄] + [... 最近 1024 个 token 的 KV ...]
驱逐: 中间所有 token 的 KV
```

---

### 13.3 H2O — 重要 Token Oracle (2023)

**论文**：*H2O: Heavy-Hitter Oracle: Efficient Generative Inference of Large Language Models with Heavy Hitters* (Zhang et al., 2023)

**核心思想**：动态追踪每个 KV 条目的**累积注意力得分**，驱逐得分最低的条目。经常被关注的 token ("heavy hitters") 一定重要，保留它们。

---

### 13.4 SnapKV (2024)

**论文**：*SnapKV: LLM Knows What You are Looking for Before Generation* (Li et al., 2024)

**核心思想**：在正式生成之前，先用一个"观察窗口"分析注意力模式，确定哪些 KV 条目在后续生成中最可能被用到，提前筛选。

**效果**：在 1024 token 预算下实现 92% 的 KV 压缩率，准确率几乎无损。

---

### 13.5 KV Cache 压缩与 Prompt 压缩的关系

```
Prompt 压缩                    KV Cache 压缩
  ↓                               ↓
减少"输入了什么"                 减少"记住了什么"
  ↓                               ↓
在模型外部操作                   在模型内部操作
(修改输入文本)                  (修改注意力缓存)
  ↓                               ↓
适用于黑盒 API                  需要控制推理引擎
  ↓                               ↓
  └───────── 互补关系 ──────────┘
  可以同时使用: 先压缩输入，再压缩 KV Cache
```

**Context Distiller 不直接涉及 KV Cache 压缩**（因为推理引擎是 Ollama/vLLM），但理解这个维度对于完整认知上下文压缩问题空间是必要的。

---

## 十四、第十二代：LLM 原生与 Agent 压缩 (2024–2026)

### 14.1 LLM 直接摘要重写

**核心思想**：利用大语言模型的**深度语义理解能力**，直接阅读原文后用自己的话重写一个精炼版本。

```
System: "You are a text compressor. Preserve all key facts, numbers, names.
         Remove redundancy. Use the same language as input."
User:   <原文>
LLM:    <精炼摘要>

控制参数:
  temperature: 0.2 (低随机性，保真度优先)
  max_tokens: len(原文) / 8
```

**LLM 摘要能做到前面所有方法做不到的事**：

| 能力 | 示例 |
|------|------|
| 跨句信息合并 | "A收入100亿。A利润20亿。" → "A收入100亿、利润20亿。" |
| 冗余消除 | "非常非常重要的、极其关键的" → "关键的" |
| 隐含推断 | "他周一请假，周五回来" → "他请假5天" |
| 格式重构 | 散文 → 要点列表 |

**核心风险 — 幻觉**：可能编造原文不存在的内容（"约20度" → "22度"）。

**Context Distiller L3 (accuracy)** 通过 Ollama 调用本地 Qwen2.5:7b 实现此方案。

---

### 14.2 Agent 系统中的实战方案 (2025–2026)

随着 AI Agent 的大规模落地，上下文压缩从学术问题变成了工程刚需。业界收敛出了一套**滑动窗口 + 摘要**的混合方案：

```
Agent 对话管理:
┌────────────────────────────────────────────────┐
│  最近 N 轮: 保留完整原文 (保证即时上下文精度)      │
│  较早历史: LLM 压缩成摘要 (保留关键信息、释放窗口)  │
│  更早历史: 存入长期记忆 (跨会话持久化)              │
└────────────────────────────────────────────────┘
```

**这正是 Context Distiller SessionCompactor 的设计理念**：
- L1 Micro-Compact: 替换旧工具结果为占位符（保留最近 3 条）
- L2 Auto-Compact: 超阈值时用摘要替换历史（transcript 保底）
- 降级链: lingua → llm → fallback

---

### 14.3 前沿研究

| 方法 | 年份 | 核心思想 |
|------|------|---------|
| **ACON** | 2025 | 将压缩建模为优化问题，用成对轨迹分析做梯度无关优化，兼容任何 API 模型 |
| **Perception Compressor** | 2025 | 免训练的 Prompt 压缩框架，利用 LLM 自身的注意力模式指导压缩 |
| **AttnComp** | 2025 | 注意力引导的自适应上下文压缩，专为 RAG 场景设计 |
| **COMI** | 2026 | 粗到细压缩，基于边际信息增益 |

---

## 十五、全景对比与 Context Distiller 映射

### 十二代算法完整对比

| 代 | 时期 | 代表方法 | 理解深度 | 压缩粒度 | 输出类型 |
|----|------|---------|---------|---------|---------|
| G1 | 1958–70s | Luhn, Edmundson | 无/启发式 | 句子 | 抽取 |
| G2 | 1990s–2000s | TF-IDF, BM25, MMR | 浅层统计 | 词/句子 | 抽取 |
| G3 | 2000s | LSA/SVD | 潜在语义 | 句子 | 抽取 |
| G4 | 2004+ | TextRank, LexRank | 图结构 | 句子 | 抽取 |
| G5 | 2003–10s | LDA | 主题概率 | 句子 | 抽取 |
| G6 | 2015–19 | SummaRuNNer, BertSum | 神经表示 | 句子 | 抽取 |
| G7 | 2015–18 | Pointer-Generator | 序列理解 | 词 | **生成** |
| G8 | 2019–21 | BART, T5, PEGASUS | 预训练语义 | 词 | **生成** |
| G9 | 2023–25 | SelectiveContext, LLMLingua-2 | 信息论/学习 | **Token** | 抽取 |
| G10 | 2023–25 | Gist Tokens, 500xCompressor | 嵌入空间 | 向量 | **软表示** |
| G11 | 2023–26 | StreamingLLM, SnapKV | 注意力模式 | KV 条目 | 内部表示 |
| G12 | 2024–26 | LLM 摘要, Agent 压缩 | 全语义 | 全文 | **生成** |

### Context Distiller 四档映射

Context Distiller 从十二代算法中选取了**最适合端侧 Agent 场景**的四种，形成 L0–L3：

```
                  G1          G9/SelectiveContext    G9/LLMLingua-2      G12/LLM摘要
                   │                  │                    │                  │
                   ▼                  ▼                    ▼                  ▼
              L0 speed          L1 selective          L2 balanced       L3 accuracy
              正则+停用词        GPT-2 自信息量        XLM-RoBERTa        Qwen2.5:7b
                                                    Token 分类          摘要重写

精度 ↑         ★ L3 (60–80% 压缩, 2–10s, 有幻觉)
     │    ★ L2 (40–50% 压缩, 100–500ms, 多语言) ← 推荐默认
     │  ★ L1 (30–40% 压缩, 50–200ms, 句子级)
     │★ L0 (10–20% 压缩, <1ms, 零依赖)
     └─────────────────────────────────────→ 延迟
```

**为什么没有选用 G2–G8 的方法？**

| 跳过的代 | 原因 |
|---------|------|
| G2 (TF-IDF/BM25) | 需要语料库，单条 Prompt 无法计算 IDF；已用于记忆检索而非压缩 |
| G3 (LSA/SVD) | 计算开销大，不适合实时场景；被 G9 全面超越 |
| G4 (TextRank/LexRank) | 句子级抽取，被 G9 Token 级方法超越；短文本效果差 |
| G5 (LDA) | 需要训练或大规模推理，延迟高；主题粒度过粗 |
| G6 (BertSum) | 句子级分类，被 G9 Token 级分类超越 |
| G7 (Pointer-Generator) | 需要专门训练的 Seq2Seq 模型，部署复杂 |
| G8 (BART/T5/PEGASUS) | 需要微调 + 专用模型服务，不如直接用 G12 LLM 通用 |
| G10 (软压缩) | 需要微调 LLM，不兼容 API 调用方式 |
| G11 (KV Cache) | 需要控制推理引擎内部，Ollama 不暴露此接口 |

**选型的核心原则**：
1. 端侧可控——不依赖外部 API
2. 即插即用——不需要微调或特殊训练
3. 渐进式降级——从快到慢、从简到繁
4. 覆盖核心需求——规则兜底 + 语义过滤 + 精细压缩 + 摘要重写

---

## 十六、业务选型决策树

```
                    你的场景是什么？
                         │
        ┌────────────────┼────────────────┐
        │                │                │
   实时对话/流式       文档预处理         Agent 日常
   中间件             批量分析          Vibe Coding
        │                │                │
        ▼                ▼                ▼
  延迟 < 10ms?      质量优先?         平衡体验?
        │                │                │
   ┌────┴────┐     ┌────┴────┐           │
  YES       NO    YES       NO          │
   │         │     │         │           │
   ▼         ▼     ▼         ▼           ▼
L0 speed  L1     L3       L2        L2 balanced
         selective accuracy            (推荐)
```

| 场景 | 推荐档位 | 理由 |
|------|---------|------|
| 实时对话中间件 / Token 转发 | **L0** | 零延迟，确定性输出 |
| Vibe Coding 日常开发 | **L2** | 平衡压缩率与速度，多语言 |
| Agent 对话上下文管理 | **L2** | 配合 SessionCompactor 最优 |
| 长文档/论文批量处理 | **L3** | 高压缩率，跨段合并 |
| 隐私敏感 / 离线边缘 | **L0–L2** | 不依赖 LLM 服务 |
| 对幻觉零容忍 | **L0–L2** | 抽取式不引入新内容 |
| 会话摘要归档 | **L3** | 跨轮合并，可读性好 |

---

## 十七、参考文献

### 第一代：启发式

| # | 文献 |
|---|------|
| [1] | Luhn, H.P. (1958). *The Automatic Creation of Literature Abstracts*. IBM Journal of Research and Development. |
| [2] | Edmundson, H.P. (1969). *New Methods in Automatic Extracting*. JACM, 16(2), 264–285. |

### 第二代：统计/IR

| # | 文献 |
|---|------|
| [3] | Salton, G. & Buckley, C. (1988). *Term-weighting approaches in automatic text retrieval*. Information Processing & Management. |
| [4] | Robertson, S. et al. (1994/2009). *The Probabilistic Relevance Framework: BM25 and Beyond*. Foundations and Trends in IR. |
| [5] | Carbonell, J. & Goldstein, J. (1998). *The Use of MMR, Diversity-Based Reranking*. SIGIR 1998. |
| [6] | Vanderwende, L. et al. (2007). *Beyond SumBasic: Task-Focused Summarization with Sentence Simplification and Lexical Expansion*. Information Processing & Management. |
| [7] | Haghighi, A. & Vanderwende, L. (2009). *Exploring Content Models for Multi-Document Summarization*. NAACL 2009. |
| [8] | Knight, K. & Marcu, D. (2002). *Summarization beyond sentence extraction*. Artificial Intelligence. |

### 第三代：矩阵分解

| # | 文献 |
|---|------|
| [9] | Gong, Y. & Liu, X. (2001). *Generic text summarization using relevance measure and latent semantic analysis*. SIGIR 2001. |
| [10] | Steinberger, J. & Jezek, K. (2004). *Using Latent Semantic Analysis in Text Summarization and Summary Evaluation*. ISIM 2004. |

### 第四代：图排序

| # | 文献 |
|---|------|
| [11] | Mihalcea, R. & Tarau, P. (2004). *TextRank: Bringing Order into Texts*. EMNLP 2004. |
| [12] | Erkan, G. & Radev, D.R. (2004). *LexRank: Graph-based Lexical Centrality as Salience*. JAIR, 22, 457–479. |
| [13] | Mei, Q., Guo, J. & Radev, D. (2010). *DivRank: the Interplay of Prestige and Diversity in Information Networks*. KDD 2010. |

### 第五代：主题建模

| # | 文献 |
|---|------|
| [14] | Blei, D.M., Ng, A.Y. & Jordan, M.I. (2003). *Latent Dirichlet Allocation*. JMLR, 3, 993–1022. |

### 第六代：神经抽取

| # | 文献 |
|---|------|
| [15] | Nallapati, R. et al. (2017). *SummaRuNNer: A Recurrent Neural Network based Sequence Model for Extractive Summarization*. AAAI 2017. |
| [16] | Liu, Y. & Lapata, M. (2019). *Text Summarization with Pretrained Encoders (BertSum)*. EMNLP 2019. |

### 第七代：Seq2Seq 生成式

| # | 文献 |
|---|------|
| [17] | Rush, A., Chopra, S. & Weston, J. (2015). *A Neural Attention Model for Abstractive Sentence Summarization*. EMNLP 2015. |
| [18] | See, A., Liu, P. & Manning, C. (2017). *Get to the Point: Summarization with Pointer-Generator Networks*. ACL 2017. |

### 第八代：预训练模型

| # | 文献 |
|---|------|
| [19] | Lewis, M. et al. (2019). *BART: Denoising Sequence-to-Sequence Pre-training*. ACL 2020. |
| [20] | Raffel, C. et al. (2020). *Exploring the Limits of Transfer Learning with a Unified Text-to-Text Transformer (T5)*. JMLR. |
| [21] | Zhang, J. et al. (2020). *PEGASUS: Pre-training with Extracted Gap-sentences for Abstractive Summarization*. ICML 2020. |

### 第九代：硬 Prompt 压缩

| # | 文献 |
|---|------|
| [22] | Li, Y. et al. (2023). *Compressing Context to Enhance Inference Efficiency of LLMs (SelectiveContext)*. EMNLP 2023. arXiv:2310.06201. |
| [23] | Jiang, H. et al. (2023). *LLMLingua: Compressing Prompts for Accelerated Inference of LLMs*. EMNLP 2023. arXiv:2310.05736. |
| [24] | Pan, Z. et al. (2024). *LLMLingua-2: Data Distillation for Efficient and Faithful Task-Agnostic Prompt Compression*. ACL 2024. arXiv:2403.12968. |
| [25] | Jiang, H. et al. (2024). *LongLLMLingua: Accelerating and Enhancing LLMs in Long Context Scenarios*. ACL 2024. arXiv:2310.06839. |
| [26] | Liskavets et al. (2025). *CPC: Context-aware Prompt Compression*. AAAI 2025. arXiv:2409.01227. |

### 第十代：软压缩

| # | 文献 |
|---|------|
| [27] | Mu, J. et al. (2023). *Learning to Compress Prompts with Gist Tokens*. NeurIPS 2023. |
| [28] | Chevalier, A. et al. (2023). *Adapting Language Models to Compress Contexts (AutoCompressor)*. EMNLP 2023. |
| [29] | Ge, T. et al. (2024). *In-context Autoencoder for Context Compression (ICAE)*. ICLR 2024. |
| [30] | Li, Z. et al. (2025). *500xCompressor: Generalized Prompt Compression for LLMs*. ACL 2025. arXiv:2408.03094. |

### 第十一代：KV Cache 压缩

| # | 文献 |
|---|------|
| [31] | Xiao, G. et al. (2023). *Efficient Streaming Language Models with Attention Sinks (StreamingLLM)*. ICLR 2024. |
| [32] | Zhang, Z. et al. (2023). *H2O: Heavy-Hitter Oracle*. NeurIPS 2023. |
| [33] | Li, Y. et al. (2024). *SnapKV: LLM Knows What You are Looking for Before Generation*. arXiv:2404.14469. |

### 其他关键参考

| # | 文献 |
|---|------|
| [34] | Shannon, C.E. (1948). *A Mathematical Theory of Communication*. Bell System Technical Journal. |
| [35] | Liu, N. et al. (2023). *Lost in the Middle: How Language Models Use Long Contexts*. arXiv:2307.03172. |
| [36] | Radford, A. et al. (2019). *Language Models are Unsupervised Multitask Learners (GPT-2)*. OpenAI. |
| [37] | Conneau, A. et al. (2020). *Unsupervised Cross-lingual Representation Learning at Scale (XLM-RoBERTa)*. ACL 2020. |

---

> **文档版本**：v2.0
> **最后更新**：2026-03-26
> **配套项目**：Context Distiller v2.0
