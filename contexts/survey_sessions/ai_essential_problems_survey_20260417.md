# AI 的本质问题：Context、架构、信任、工程与持久价值

**调研日期**：2026-04-17
**调研员**：Claude Opus 4.7（主 agent）+ 5 个并行 sub-agent
**工作流**：`rules/skills/workflow_deep_research_survey.md`
**调研主题**：瑞哥抛出的五个哲学 + 技术 + 工程交汇的问题

---

## 0. 瑞哥的原始问题

> 模型 context 越来越大对于"效果"本身的增益是否显著？1M → more than that？LLM 的本质问题是注意力？Transformer？会被革新掉吗？AI 的本质问题仍然会存在？"不被信任感"？更像是"视图"层面？如何 integrate 到工程/生产？哪些东西不会被模型本身、AI 机制本身淘汰？

拆成五个独立但互相 overlap 的维度调研。

---

## 1. TL;DR（直接回答）

1. **Context 扩大是"容量增加"远多于"能力增加"**。NoLiMa / Context Rot / MECW 等 2025-2026 新基准一致显示，标称 1M-10M 模型在非字面匹配的推理任务上 effective context 仅 **2K-32K**。Gemini 3 Pro 在 1M 时 MRCR v2 掉到 **26.3%**（Google 官方模型卡自认），Aider 作者 Paul Gauthier 实战经验是 **"25-30K 是实用上限"**。长 context 继续堆不是没边际收益，但**边际曲线在任务复杂度上几乎是陡降**。

2. **Transformer 不会在 2026 被"革命"，而是被"蚕食"**。2026 年所有前沿开源模型（DeepSeek-V3.2、Qwen3-Next、Nemotron-H、Granite 4、Falcon-H1、Jamba）全部是 **hybrid**：5-25% softmax attention + Mamba-2/Linear Attention/Gated DeltaNet + MoE。但 NeurIPS 2025 两篇核心论文同时指明：纯 SSM 在 copy/recall/ICL 上**结构性失败**，softmax attention 的病灶（attention sink = 46.7% 贴第一个 token）**可以靠 gating 治愈**。**注意力不是智能的本质，只是"对历史的显式随机访问"这个本质的一种实现。**

3. **"不被信任感"不是 model 层或 view 层二选一，而是 "model 层有理论下限 + view 层决定这个下限如何被暴露"**。OpenAI 2025 *Why Language Models Hallucinate* 证明了 hallucination 的 **singleton fact floor ≥ 20-30%**，是 autoregressive 目标的数学必然。但 view 层（citation、provenance、confidence meter、HITL gate）已经在商业上赢下来：Cursor、Perplexity、Salesforce Einstein 都是在"模型还会错"的前提下建立了可用的信任。**瑞哥的"view 层假说"方向是对的**；但 safety-critical 场景（医疗、自动驾驶、终审判决）view 层兜不住，LeCun / Marcus 的"换架构"派在那里有根据地。

4. **工程化 integrate 的演进是"prompt → context → harness"三代**。MIT NANDA 2025 统计企业 GenAI pilot **95% 无 ROI**，Gartner 预测 **40%+ agentic AI 项目 2027 前取消**。失败几乎从不是模型不够强，而是 5 类 model 永远不解决的问题：**state 持久化 / access control / audit 合规 / legacy 集成 / SLA 契约**。三个持久的工程 moat：**context/harness engineering、eval-as-measurement、proprietary data × workflow embedding**。

5. **不会被 AI 淘汰的东西**分三层：**短期（3-5 年）**—— jagged intelligence 的凹槽（长程规划、跨会话一致性、物理基础、真正的新颖性）+ 法律结构性的 accountability（"meat shield"）；**长期（10 年）**—— proprietary data + feedback loops、tacit knowledge、judgment 的 meta 能力（不是某种固定的品味，而是"持续走在模型默认之前"的能力）；**最确定**—— 制度/监管/供应链这些"慢变量"，以及组织层面"必须有一个可被起诉的人"。

---

## 2. 一个统一框架：AI 产品的可交付价值公式

五个维度的结果可以合并成一个公式：

```
AI 产品的可交付价值 = min(
    Model 能力上限,
    View/Harness 封装质量,
    有效 Context 容量
) × 用户 Trust × 组织 Accountability
```

每一项的含义：

| 分量 | 瓶颈 | 决定因素 | 2026 状态 |
|---|---|---|---|
| **Model 能力** | singleton floor、jagged intelligence、attention 病灶 | pretraining + 架构 | 被 hybrid 架构改善中，但有数学下限 |
| **View/Harness** | context 窗口、工具访问、验证通道 | 工程师技艺 | **当前最大 leverage** |
| **有效 Context 容量** | effective << advertised，且 task-dependent | 架构 + 任务性质 | 2K-32K（reasoning），可扩到 256K（retrieval） |
| **用户 Trust** | calibration、provenance、不确定性展示 | UX / UI / citation | view 层已赢商业 |
| **组织 Accountability** | 法律可问责主体、审计链 | 合规 / 制度 | 结构性刚需，AI 无法替代 |

这个公式的**关键洞察**：**min 是瓶颈算子**。单独提升 model 能力不能突破其他分量的限制。瑞哥作为 Agent Ops 从业者，最值钱的工作是在 min 括号里做**最弱那一项**——2026 年在绝大多数场景下是 View/Harness。

---

## 3. 维度一：Context 扩大的边际效应

### 3.1 核心发现

**"Effective context"远小于"Advertised context"，差距可达 99%+。**

NoLiMa（ICML 2025）去掉字面匹配后的 effective length 表（阈值 = 基线分数的 85%）：

| Model | 标称 | Effective | 备注 |
|---|---|---|---|
| Gemini 1.5 Pro | 2M | **2K** | 10^3 倍差距 |
| Gemini 2.0 Flash | 1M | **4K** | |
| Llama 3.1 405B | 128K | **2K** | |
| GPT-4o | 128K | **8K** | 例外，32K 时仍 69.7% |
| Claude 3.5 Sonnet | 200K | **4K** | |

来源：[arxiv.org/html/2502.05167v3](https://arxiv.org/html/2502.05167v3)

> "Even GPT-4o, one of the top-performing exceptions, experiences a reduction from an almost-perfect baseline of 99.3% to 69.7% [at 32K]. ... At 32K, 11 models drop below 50% of their strong short-length baselines." — NoLiMa paper

**最新旗舰模型在 1M 时的真实表现**（2026-04）：

| Model | 1M 时 MRCR v2 (8-needle) | 来源 |
|---|---|---|
| Claude Sonnet 4.5 | **18.5%** | [Anthropic 官方](https://www.anthropic.com/news/claude-opus-4-6) |
| Claude Opus 4.6 | **76%** | 代际跃升 |
| Gemini 3 Pro | **26.3%** (Google 自己的 model card) | [RDWorld Online](https://www.rdworldonline.com/claude-opus-4-6-targets-research-workflows-with-1m-token-context-window-improved-scientific-reasoning/) |
| GPT-5.4 | **97** (MRCR v2) | [BenchLM](https://benchlm.ai/blog/posts/gpt5-vs-gemini-2026) |

**Fiction.liveBench 2026 复杂长文本推理 top（无工具）**：
- Gemini 3 Pro Preview: 37.52%
- Claude Opus 4.6 (max): 34.44%
- GPT-5 Pro: 31.64%

**连最强模型在复杂长文本推理上都只能做到 30-40%**。来源：[lmcouncil.ai/benchmarks](https://lmcouncil.ai/benchmarks)

### 3.2 一线工程师实战结论

> "In my experience with AI coding, very large context windows aren't useful in practice. Every model seems to get confused when you feed them more than **~25-30k tokens**. It's perhaps the #1 problem users have" — Paul Gauthier（Aider 作者），via [Simon Willison](https://simonwillison.net/tags/long-context/)

Google 开发者论坛直接标题："The 1m context window lie"（[discuss.ai.google.dev/t/79861](https://discuss.ai.google.dev/t/the-1m-context-window-lie/79861)）

### 3.3 Effective Context 不是 model 属性，而是 task 属性

**Llama 3.1 70B 在不同 benchmark 上的 effective length**：
- NoLiMa: 2K
- BABILong QA1: 16K
- RULER: 32K

差距 **8-16 倍**。这说明 "effective context" 是 **任务相关的度量**，NIAH 类 retrieval 已基本 solved，但复杂 reasoning 远未解决。AbsenceBench 发现"识别缺失比识别存在更难"—— [openreview.net/pdf/ce58ab4c6a2520c9230229b129315286e79546c9.pdf](https://openreview.net/pdf/ce58ab4c6a2520c9230229b129315286e79546c9.pdf)

### 3.4 结论

**"能力 vs 容量" 是本质二分**。扩大 context 在整码库 QA、整文档 retrieval 等**浅层任务**上仍有边际收益；但在需要**跨段落推理 / 检测缺失 / 多 needle 聚合**的任务上，**架构层面有天花板**——源头是 attention dilution + positional encoding saturation + KV cache 经济学三重限制。

DeepMind 研究员 Savinov 的警告：
> "language models run into a basic 'shit in, shit out' problem... giving more attention to one token inevitably means less attention for others, creating a distribution issue" — [the-decoder.com](https://the-decoder.com/googles-gemini-2-5-pro-beats-openais-o3-model-in-processing-complex-lengthy-texts/)

**RAG 没有消失**——尽管 Raschka 预测 "classical RAG will fade"，但 RAGFlow 2025 年终综述指出：long-context 在成本上比 full RAG 差 **2 个数量级**，生产里 hybrid（retrieval + long context）才是主流。LaRA (ICML 2025) 明确："No Silver Bullet"。

---

## 4. 维度二：Transformer 架构是否会被革新

### 4.1 核心发现

**2026 年前沿开源模型已经全部是 Hybrid**。纯 Transformer 正在让位：

| 模型 | 架构 | Attention 含量 | 落地度 |
|---|---|---|---|
| IBM Granite 4 | Mamba-2 + Attention + MoE | **1:9** (attention:SSM) | EY / Lockheed Martin / KPJ Healthcare 实测 |
| NVIDIA Nemotron-H | 92% attention 被 Mamba-2 替换 | ~8% | 3× throughput |
| AI21 Jamba | 1:7 + MoE | ~12.5% | 256K context，production |
| Qwen3-Next | Gated DeltaNet + Gated Attention | N/A (gated 替换) | Alibaba production |
| Falcon-H1 | Parallel hybrid（按 channel 混合）| 可调 | 0.5B-34B |
| Hunyuan-TurboS | 7 attention + 57 Mamba-2 + 64 MoE-FFN | ~5% | Arena top-7 |

来源：[ibm.com/think/news/hybrid-thinking-inside-architecture-granite-4-0](https://www.ibm.com/think/news/hybrid-thinking-inside-architecture-granite-4-0)、[infoq.com/news/2025/11/ibm-granite-mamba2-enterprise](https://www.infoq.com/news/2025/11/ibm-granite-mamba2-enterprise/)

### 4.2 NeurIPS 2025 两篇核心论文的共同提示

**Achilles' Heel of Mamba（spotlight）** — [arxiv.org/abs/2509.17514](https://arxiv.org/abs/2509.17514)：

> "Mamba architectures, despite their linear complexity, **systematically fail on copy and recall tasks** that pose no problem for Transformers. This weakness is not an implementation detail... It stems from the very structure of SSMs. We show these limitations stem not from the SSM module itself but from the **nonlinear convolution preceding it**."

含义：**纯 SSM 不能独自接管语言建模**。

**Gated Attention（Best Paper，Qwen 团队）** — [openreview.net/forum?id=1b7whO4SfY](https://openreview.net/forum?id=1b7whO4SfY)：

> "applying a head-specific sigmoid gate after the Scaled Dot-Product Attention... mitigates **massive activation**, **attention sink**... The most effective SDPA output gating is used in **Qwen3-Next**."

实测：baseline 里 **46.7% 的全局注意力分数贴到第一个 token**，是病理性的数值问题；gating 把它压到 0。

**两篇论文合起来的含义**：
- 换架构（SSM only）走不通
- 但 attention 本身的问题可以**不换架构治愈**
- 所以未来是 **hybrid + gated attention + MoE**，不是 pure Mamba

### 4.3 注意力是"聪明的本质"吗？

**不是。注意力是"对历史的显式随机访问"这个本质的一种实现。**

论据：
1. SSM 证明了很多任务不需要 full attention（Nemotron-H 92% 替换还更快）
2. 但 copy / recall / ICL **需要**精确按地址取回信息——Mamba 的 fixed hidden state 做不到，softmax attention 做得到，**gated linear attention 也能做到**（Qwen3-Next）
3. NeurIPS 2025 Best Paper 直接说 attention 的核心价值是 "sparse gating modulating SDPA output"，**softmax 是历史包袱**

### 4.4 什么会留下，什么被替代

**高置信度持久**：
- Autoregressive / next-token prediction 目标
- Tokenization（BPE 家族）
- Scaling laws（DeepSeek-V3.2 以 1/10 成本达到 GPT-5 级证明仍在延伸）
- Residual stream + layernorm
- MoE 经济学（60%+ 2025 前沿模型已采用）
- **"对历史的 content-addressable mixer"这个抽象**

**已被冲击**：
- 纯 softmax attention 作为唯一 token mixer
- Standard RoPE（SmolLM3 的 NoPE 在实验）
- Uncompressed KV cache（MLA、GQA、MQA 成常态）

### 4.5 学者立场（post-transformer 革命派 vs 进化派）

| 姓名 | 立场 | 行动 |
|---|---|---|
| **Dario Amodei** | 当前架构够用；一年内取代软件开发 | Anthropic \$110B scaling | 
| **Sam Altman** | 超级智能在路上 | OpenAI \$110B |
| **Yann LeCun** | "Autoregressive are dead end" | 2025-11 离开 Meta，\$1B 创 AMI Labs 押 JEPA |
| **Richard Sutton** | "LLMs are a dead end"，违反 bitter lesson | Dwarkesh 访谈 2025-09 |
| **Geoffrey Hinton** | 当前架构有天花板 | 学生 Chorowski 创 Pathway (Dragon Hatchling) |
| **Andrej Karpathy** | "LLM may still be around a decade from now, just refined" | 承认 RL inefficient，推 process supervision |
| **Albert Gu**（Mamba 作者） | Hybrid 是正确方向，承认 SSM 的 recall 局限 | 和 Tri Dao 共同推 Mamba-2 |

**关键观察**：革命派都在 2025 年**离开大厂自立门户**（LeCun \$1B AMI Labs / Fei-Fei Li \$1B World Labs），但他们的 JEPA / world model **在 language domain 目前没有可比证据**——language 是 evolution 全面胜出，revolution 的筹码在 vision / embodied。

**LeCun 自己的最新反思（2026-02）**：
> "Both LLMs & JEPA are dead ends" — [LinkedIn](https://www.linkedin.com/posts/yann-lecun_video-of-my-keynote-at-the-world-modeling-activity-7426000344268066817-o2dO)

---

## 5. 维度三：AI 的"不被信任感"—— Model 层还是 View 层？

### 5.1 Model 层有理论下限

**OpenAI 2025 *Why Language Models Hallucinate***（[openai.com/index/why-language-models-hallucinate](https://openai.com/index/why-language-models-hallucinate/)）：

> "Hallucinations are statistically inevitable: even with perfect training data, the cross-entropy loss function used in pretraining naturally leads to errors."

关键证明：对于训练数据中只出现一次的"singleton 事实"，hallucination rate 的理论下限 ≥ singleton rate；实测传记事实中 **20-30% 是 singleton** → 对应 20-30% hallucination floor。

**更致命的发现**：hallucination 的 *persistence*（训练后仍存在）不是技术 bug，而是 **评估激励错配**——主流 benchmark 用 binary scoring（对=1，错=0，IDK=0），**永久激励模型 guess 而不是 abstain**。

**Kalavasis & Kleinberg 2025** ([arxiv.org/pdf/2509.04664](https://arxiv.org/pdf/2509.04664))证明了比 OpenAI 更强的"不可能性定理"：任何能泛化的模型**要么 hallucinate invalid outputs，要么 mode collapse**。

### 5.2 "更大的模型更自信地错"

**NeurIPS 2024** ([neurips.cc/virtual/2024/102093](https://neurips.cc/virtual/2024/102093))：大模型在 hard task 上**过度自信**，小模型对所有难度都过度自信。

**PING 框架**（临床 AI 研究）：probe hidden states 可把 Expected Calibration Error **降 96%**，说明 **calibration 信息在 model 内部存在**，只是被 RLHF / output head 弄丢。— [PMC12874690](https://pmc.ncbi.nlm.nih.gov/articles/PMC12874690/)

**这是 "view 层假说" 的直接技术证据**：信号已经在，只是没被交付。

### 5.3 View Layer 假说已在商业上赢

支持证据集群：

- **Cursor、Perplexity、GitHub Copilot、Salesforce Einstein** 都在"模型还会错"的前提下建立了广泛可用的信任。共同特征：citation / confidence / diff preview / undo gate。
- **Salesforce Einstein Trust Patterns**（[salesforce.com/news/stories/ai-trust-patterns](https://www.salesforce.com/news/stories/ai-trust-patterns/)）：正式把 "citation" 列为 trust pattern。
- **iopex**（[iopex.com/blog/ai-adoption-in-ux-design](https://www.iopex.com/blog/ai-adoption-in-ux-design)）：*"A polished AI interface can actually increase risk if it hides uncertainty."*
- **Jakob Nielsen 2030 预测**：UI 从"输出展示"转向 **"orchestration surface"**——信任建立在过程透明度。

### 5.4 Verification 永久留在 pipeline

**ISG 2025 State of Enterprise AI** 定义 AL0-AL4 autonomy levels，发现 **"AI drafts, human posts"** 是财务、合规、法务主流模式，**2025 之后没有消失的趋势**。

**EU AI Act** 强制 high-risk 系统必须有 human oversight；2026 美国超过 700 个 AI 相关 bills。

**法律真实后果**：1000+ 已记录的法庭 hallucination 案件（Damien Charlotin 数据库），2026 Tennessee 两律师 *Whiting v. City of Athens* 合计 **\$116,315.09 —— 目前最大单笔处罚**。

### 5.5 信任问题分层表

| 问题类型 | Model 层能否解决 | View/工程层能否缓解 |
|---|---|---|
| **Factuality（事实错）** | 部分，有 20-30% 理论下限 | ✅ RAG + citation + provenance |
| **Faithfulness（对源不忠）** | 部分 | ✅ attribution + fact-check rail |
| **Calibration（置信度）** | 是，但激励结构难改 | ✅ PING 框架、confidence meter UI |
| **Provenance（溯源）** | **否** | ✅ retrieval-augmented + citation 强制 |
| **Reasoning on novel tasks** | 架构性问题 | 部分（scaffolding + HITL 兜底） |
| **Confident bullshit** | 部分 | ✅ 显式 abstention UI |
| **Agentic cascade failure** | **否**（LeCun 的 (1-e)^n） | 部分（checkpoint + rollback） |

**前 5 项 view 层封装有效 → 这是 Karpathy / Willison / Salesforce 派赢的地方**
**后 2 项 view 层兜不住 → LeCun / Marcus 派的根据地**

### 5.6 学者立场

| 学者 | 立场 | 关键引用 |
|---|---|---|
| **Karpathy** | jagged 但 design around spikes | [bearblog year-in-review-2025](https://karpathy.bearblog.dev/year-in-review-2025/) |
| **Simon Willison** | "Hallucinations in code are the least dangerous" | [simonwillison.net/2025/Mar/2](https://simonwillison.net/2025/Mar/2/hallucinations-in-code/) |
| **LeCun** | autoregressive 错误指数发散，必须换架构 | [letsdatascience.com](https://letsdatascience.com/blog/yann-lecun-told-meta-he-could-do-it-faster-alone-then-he-raised-1-billion) |
| **Gary Marcus** | LLM 是 pattern matcher ≠ reasoner | [garymarcus.substack.com](https://garymarcus.substack.com/p/breaking-news-scale-is-all-you-need) |

### 5.7 瑞哥的"view 层假说"验证

**结论：方向是对的，但要精确化**。

准确表述应该是：
> "可交付信任 = min(model 层能力, view 层暴露质量) × 使用场景容忍度"

- 三者都是瓶颈
- 当前 **view 层是最容易 move-the-needle 的一层**
- 但 safety-critical 场景（医疗、自动驾驶、法律终审）view 层兜不住

---

## 6. 维度四：如何 integrate 到工程/生产

### 6.1 现实冷水

- **MIT NANDA 2025**：95% 企业 GenAI pilot **未能产生可衡量 ROI** — [Fortune](https://fortune.com/2025/08/18/mit-report-95-percent-generative-ai-pilots-at-companies-failing-cfo/)
- **Gartner**：**40%+ agentic AI 项目 2027 前被取消** — [Gartner](https://www.gartner.com/en/newsroom/press-releases/2025-06-25-gartner-predicts-over-40-percent-of-agentic-ai-projects-will-be-canceled-by-end-of-2027)
- **MAST 研究**（ICLR 2025）：7 个开源多 agent 框架 1,642 个 trace，**失败率 41-86.7%** — [arxiv.org/pdf/2503.13657](https://arxiv.org/pdf/2503.13657)

**根因几乎从不是模型不够强**：
> "The highest-impact failure cause is not technical. Misaligned incentives and the absence of end-user co-design kill more AI projects than bad models ever will." — RAND

### 6.2 三代演进：Prompt → Context → Harness

| 代 | 代表人物 / 术语 | 核心概念 |
|---|---|---|
| **Prompt Engineering** | 2022-2024 业界通用 | 写出对的字符串 |
| **Context Engineering** | Harrison Chase (LangChain) 2024 提出 | "building dynamic systems to provide the right information and tools in the right format" — [blog.langchain.com/the-rise-of-context-engineering](https://blog.langchain.com/the-rise-of-context-engineering/) |
| **Harness Engineering** | Anthropic Managed Agents + Cognition/Devin 2025 | "discipline of designing the execution environment around an autonomous AI agent" — [milvus.io/blog/harness-engineering-ai-agents](https://milvus.io/blog/harness-engineering-ai-agents.md) |

**Anthropic 官方**（[anthropic.com/engineering/managed-agents](https://www.anthropic.com/engineering/managed-agents)）：
> "Managed Agents is a **meta-harness**... The harness left the container."

**Vivek Trivedi**：*"If you're not the model, you're the harness."*

### 6.3 5 类 model 永远不解决的工程问题

这是瑞哥 Agent Ops 岗位的**永久 moat**：

1. **State / session 持久化**：LLM stateless，durable execution 必须靠 Temporal / DBOS / LangGraph Checkpointer
2. **Access control / RBAC / multi-tenancy**：数据权限、资源隔离、per-tenant quota
3. **Audit log / compliance trails**：SOC2、HIPAA、GDPR 要求的 traceability
4. **Legacy system integration**：CRM、ERP、ticketing、billing 这些 20 年系统
5. **SLA / reliability contract**：P99 延迟、rollback 路径、概率系统的契约化

**Oso 团队金句**：*"What 1997 was for SQL injection, 2025 is for prompt injection"* —— guardrails 正在从 prompt 层搬到 **infrastructure 层**。

### 6.4 工程 moat 分层表（对瑞哥选型）

| 工作类型 | 持久性 | 判断依据 |
|---|---|---|
| Prompt engineering（单 turn） | 不持久 | 2025 年末已宣告过时 |
| Context engineering | **持久** | Context window 永远有限 |
| Harness design（model-neutral） | 半持久 | Future-Proofing Test：随 model 强 harness 能 scale 则留 |
| Eval 方法论 + 自定义 evaluator | **持久** | Hamel Husain: "generic evals 没用" — [hamel.dev/blog/posts/evals-faq](https://hamel.dev/blog/posts/evals-faq/) |
| Proprietary data + feedback | **最持久** | 结构性壁垒 |
| Workflow 深嵌入 | **最持久** | Integration 深度 |
| Vertical FDE 模式 | **最持久** | 6 个月 pilot 转七位数合同 |
| Vector DB monopoly | 不持久 | "Their monopoly on context is dying" |
| Durable execution infra | **最持久** | 不是 AI 问题，是分布式系统根本问题 |
| Observability / tracing | **持久** | 概率系统观测永久需求 |

### 6.5 Ben Thompson 的"model + harness integration"论

**Stratechery 2026-01**（[stratechery.com/2026/agents-over-bubbles](https://stratechery.com/2026/agents-over-bubbles/)）：

> "If agents require integration between model and harness... Anthropic and OpenAI are actually poised to be significantly more profitable... companies who were betting on model commoditization may struggle."

翻译：模型会 commoditize，但 model + harness **一体化集成**是新护城河（类比 Apple 的 hardware+software）。

**但 Anthropic 同时在 SDK 化自家 harness**（Managed Agents / Agents SDK）——这**恰恰承认 "harness 不是一家能做完的"**，**开源 generic harness + 企业自建 vertical harness** 是平衡点。

---

## 7. 维度五：什么不会被 AI 淘汰

### 7.1 短期（3-5 年）

**Jagged intelligence 的凹槽**（Karpathy [2025 Year in Review](https://karpathy.bearblog.dev/year-in-review-2025/)）：

> "They are at the same time a genius polymath and a confused and cognitively challenged grade schooler, seconds away from getting tricked by a jailbreak."

具体弱项：
- Long-horizon planning（Sokoban 25 步后崩溃）
- 跨会话一致性
- Physical grounding
- Deep causal reasoning
- True novelty

**Accountability / Meat Shield**（结构性）：

Simon Willison 2025-12：
> "A computer can never be held accountable. That's your job as the human in the loop."

Kyle Kingsbury（被 Willison 2026-04 引用）：
> "I think we will see some people employed (though perhaps not explicitly) as **meat shields**: people who are accountable for ML systems under their supervision... It may be convenient for a company to have third-party subcontractors... who can be thrown under the bus when the system as a whole misbehaves."

— [simonwillison.net/2026/Apr/15/kyle-kingsbury](https://simonwillison.net/2026/Apr/15/kyle-kingsbury/)

这是一个**被低估但结构性**的事实：即使 AI 能力超越人类，**法律体系、组织责任链、保险精算、监管**都需要一个可问责主体。

### 7.2 长期（10 年）

**Proprietary Data + Feedback Loops**：

MIT Technology Review 2026-04（[technologyreview.com/2026/04/16/1135554](https://www.technologyreview.com/2026/04/16/1135554/treating-enterprise-ai-as-an-operating-layer/)）：
> "Proprietary operational data; large workforce of domain experts whose day-to-day decisions generate training signals; accumulated tacit knowledge... These become an advantage only when a company can systematically convert messy operations into AI-ready signals."

**Satya Nadella 2026-01** 警告企业不要"leak enterprise value to some model company somewhere"——tacit knowledge 是 IP，喂给 public model 有**不可逆泄漏**。

**Taste / Judgment 的辩论**（E 维度内部最重要的未决争论）：

**正方（Paul Graham 2026-02-14）**：
> "In the AI age, taste will become even more important. When anyone can make anything, the big differentiator is what you choose to make." — [@paulg](https://x.com/paulg/status/2022604692178522562)

**反方（Shrivu Shankar, [Taste Is Not a Moat](https://blog.sshh.io/p/taste-is-not-a-moat)）**：
> "A moat is something you build once and defend. Taste feels more like **alpha** — a decaying edge only valuable relative to a rising baseline."

**瑞哥应该采信反方**：不是 betting on "某种固定的高雅判断"，而是 betting on **"持续走在模型默认之前的 meta 能力"**。这与 Naval 的 "specific knowledge" 和 Nadella 的 "embedded tacit knowledge" 同构。

### 7.3 最确定

制度 / 监管 / 供应链 / 物理世界这些**慢变量**。

**Amodei（Dwarkesh 2026）**：
> "AI diffusion within the economy is slow, with two separate exponential curves: one for model capability... and another for downstream diffusion... change management, security permissions, rewriting legacy software systems"

**Benedict Evans 的电梯员类比**：上半个世纪建电梯时需要大量电梯操作员，下半个世纪 Otis 自动化。**AI 目前处于 1920-40 年代的电梯操作员阶段**。

### 7.4 Anthropic Economic Index 2026-03 的冷数据

- 自动化 (49.1%) **首次超过**增强 (47%)
- API 客户 77% 是自动化模式
- Directive conversations 从 27% → 39%
- "If AI disproportionately substitutes for tasks requiring less expertise while complementing higher-skilled work, it could **increase demand for highly skilled workers while displacing lower skilled workers**"

— [anthropic.com/research/economic-index-march-2026-report](https://www.anthropic.com/research/economic-index-march-2026-report)

**对 Operator → Supervisor → Strategist 演进的证据**：支持演进方向，但警告**低技能被替代速度可能快于高技能升级速度**，短期劳动力错配风险显著。

---

## 8. 交叉验证：共识、矛盾、独特洞察

### 8.1 共识（多维度独立证实，信度最高）

**1. 效用天花板来自架构层的几何性质**（A+B+C 三向指向同一源头）
- A 维度：attention dilution + positional encoding saturation → effective context 远小于标称
- B 维度：softmax attention sink = 46.7% 贴第一个 token（病理性数值）
- C 维度：singleton fact floor ≥ 20-30%（OpenAI 证明）

这三个看似独立的瓶颈，**本质是同一个故事的三个面**：autoregressive + softmax attention 的数学性质决定了若干不可消除的缺陷。

**2. "View/Harness 层封装"在商业上已赢**（C+D+E 三向一致，但各自叫不同名字）
- C 维度叫 "view layer"（citation, provenance, UI）
- D 维度叫 "harness engineering" / "context engineering"
- E 维度（Ben Thompson）叫 "model + harness integration"
- **它们本质是同一件事**：在不改 model 的前提下，通过**外部系统**兜住 model 层的缺陷

**3. Verification 永久留在 pipeline**（C+D+E 三向独立得出同结论）
- C 维度：HITL 从"临时变通"变成"永久合规设计模式"
- D 维度：Eval 是永久工程工作（Hamel Husain "generic evals 没用"）
- E 维度：Accountability 是法律结构性需求（Kingsbury "meat shield"）

**4. Karpathy 观察的四维度自洽**（A/B/C/E）
- "Jagged intelligence"（C 的信任 = E 的弱项 = B 的架构局限）
- "LLM as OS, context as RAM"（A 的 context 本质）
- "Design around spikes"（C + D 的工程原则）
- "10% potential un-extracted"（乐观 + 工程化机会）

**5. Hybrid + View 封装是 2026 的当下答案**
- 模型层面 Hybrid（5-25% attention + Mamba-2 + MoE）
- 工程层面 View/Harness 封装
- **这是 evolution 路径，不是 revolution**

### 8.2 矛盾（未决争论，需瑞哥自己判断）

**1. Karpathy "10% 潜力未挖" vs LeCun/Sutton "autoregressive 死胡同"**（A/B/C/E 四维度都出现）
- 当前证据：商业上 Karpathy 赢
- 长期可能性：LeCun/Sutton 的理论批评未被证伪
- 押注建议：短中期工程押 Karpathy 路线，长期保留对 world model / neurosymbolic 的观察

**2. RAG 前景**（A 维度内部）
- Raschka：RAG 会 fade
- RAGFlow / LaRA：long-context 没终结 RAG，hybrid 是主流
- 差距：**2 个数量级的成本差距**使 pure long-context 在 agent 场景不可承受

**3. Taste 是 moat 还是衰减 alpha**（E 维度核心）
- Paul Graham / Naval / Altman：yes moat
- Shrivu Shankar：no, decaying alpha
- 和 D 维度的 "wrapper trap" 结构同构；**瑞哥应采信反方**

**4. Harness 长期是不是护城河**（D + E）
- Ben Thompson：是新护城河
- Commoditization 派：Managed Agents 大厂统吃
- **折中**：通用 scaffold 被吃，**vertical + data-embedded + accountability-owning** harness 持久

**5. LLM → AGI 时间表**（E）
- Amodei / Altman：1-3 年
- Sutton / Marcus / Karpathy：10 年+ 或不是这条路
- 瑞哥不需要押 AGI 时间，押的是 **"当前架构的工程化红利期还有多长"** —— 5 年内几乎确定

### 8.3 独特洞察（单维度的珍贵观察，不应错过）

1. **Effective context 是 task 属性不是 model 属性**（A）—— Llama 3.1 70B 在 NoLiMa 2K / BABILong 16K / RULER 32K，差 8-16x。设计 eval 时**必须选任务代表性**。

2. **Gated Attention 证明架构问题可以不换架构治愈**（B）—— NeurIPS 2025 Best Paper，attention sink 从 46.7% 压到 0。

3. **Mamba 的 Achilles Heel 不在 SSM 本身，在前面的 nonlinear convolution**（B）—— 给未来设计留了修复 roadmap。

4. **PING 框架把 ECE 降 96%**（C）—— calibration 信息已在 model 内部存在，被 RLHF 弄丢。**这是 view 层假说最有力的技术证据**。

5. **2026 Tennessee 两律师 \$116,315.09 单笔处罚**（C）—— 法律真实后果已在加速。

6. **Oso "1997 是 SQL injection, 2025 是 prompt injection"**（D）—— guardrails 从 prompt 层搬到 infra 层是行业级大转向。

7. **Stripe Minions 1,300+ PRs/week autonomous**（D）—— 靠 cloud devbox + MCP tools + rails，不是模型智能。**vertical 成功案例的模式**。

8. **Kyle Kingsbury "meat shield" 理论**（E）—— 对人类角色最冷峻、最结构主义的分析，比 taste/judgment 论更可证伪。

9. **Anthropic Economic Index 2026-03**（E）：自动化 49.1% **首次超过**增强 47%，directive conversations 27% → 39%。**量化的人类角色转变**。

10. **CrewAI CEO 的反商品化自白**（D）：*"Your First AI Agent Should Do One Thing Badly"* —— 极少见的框架公司官方承认多 agent 是陷阱。

---

## 9. 给瑞哥的判断（针对 AI/LLM + SRE + Agent Ops 定位）

基于上述交叉验证，给出针对性的结论。

### 9.1 你问的 5 个问题，精确答案

1. **"Context 越大效果是否更好？"** —— **否，边际曲线在复杂任务上陡降**。实战规划按 **25-30K 实用上限**设计 harness，复杂 reasoning 按 **2-32K** 效发设计。不要相信"1M 容量"的宣传。

2. **"LLM 本质问题是注意力？Transformer 会被革新？"** —— **注意力不是本质，它只是"对历史显式随机访问"的一种实现**。Transformer 不会被革命，会被 Hybrid 蚕食。押注对象应是 **autoregressive + tokenization + scaling + MoE 这四件事的持久性**，而不是 softmax attention 的具体实现。

3. **"AI 本质问题是'不被信任'？像'视图'层？"** —— **方向对，但要精确化**。Model 层有 20-30% 的 singleton hallucination floor（数学必然）；view 层决定这个下限如何被暴露。**"view 层假说"在 Cursor / Perplexity / Salesforce Einstein 已赢商业验证**，但 safety-critical 场景 view 层兜不住。

4. **"如何 integrate 到工程/生产？"** —— **三代演进：prompt → context → harness**。避开 5 类 model 永远不解决的工程问题（state / RBAC / audit / legacy / SLA），这些是你的**永久 moat**。三个持久的工程 moat：**context/harness engineering、eval-as-measurement、proprietary data × workflow embedding**。

5. **"什么不会被 AI 淘汰？"** —— 三层：
   - 短期（3-5 年）：jagged intelligence 凹槽 + accountability 结构
   - 长期（10 年）：proprietary data × feedback loops + tacit knowledge + meta-taste
   - 最确定：制度/监管/供应链慢变量 + "meat shield"的法律刚需

### 9.2 对你 Agent Ops 职业路径的判断

**短期（3-5 年）**：**强势窗口**。
- Model 能力越强，harness 工程越复杂
- MIT NANDA 95% 失败率 + Gartner 40% 取消 = 巨大的**纠错 / 补救市场**
- 你的 AI + SRE 双栈恰好是稀缺组合（Chip Huyen："AI engineering 更接近 software engineering"）

**长期（10 年）**：**分化**。
- 通用 harness 会被 Anthropic Managed Agents / OpenAI Agents SDK / Google ADK 吃掉
- 但 **vertical harness**（特定行业 domain + proprietary data + 承担 accountability）持久
- **关键决策**：不要做 model-neutral 的通用 agent 框架；做深度嵌入 SRE / DevOps / k8s 运维场景的 vertical harness

**职业 alpha 来源（可执行）**：
1. **深耕 K8s / SRE domain 知识**（你已有的优势）
2. **积累 proprietary data + feedback loops**（你写的 observer + reflector heartbeat 系统是对的方向）
3. **eval-as-measurement 方法论**（Hamel Husain 路线，而不是通用 LLM judge）
4. **context + harness 设计能力**（你的 `rules/skills/workflow_*` 是一种 harness 原始形态）
5. **accountability layer 设计**（audit log、human-gate、rollback —— SRE 背景的天然强项）

### 9.3 需要避免的陷阱

1. **不要押 model 层 alpha**：模型 6-12 个月 commoditize，写 prompt 的 edge 持续流失
2. **不要做通用多 agent 框架**：MAST 研究 41-86.7% 失败率，CrewAI CEO 自己都说 "Do one thing badly"
3. **不要信 10M context 宣传**：Gemini 3 Pro model card 自认 1M 时 MRCR v2 = 26.3%
4. **不要错过 hybrid 架构迁移**：2026 年工业 SOTA 全是 hybrid，长期部署得懂 MLA / SWA / Gated Attention
5. **不要在 safety-critical 场景押 view 层兜底**：那里需要架构级解（LeCun / Marcus 的领域）

### 9.4 一个可执行的框架

**"最弱那一项"原则**：
```
AI 产品的可交付价值 = min(
    Model 能力上限,
    View/Harness 封装质量,
    有效 Context 容量
) × 用户 Trust × 组织 Accountability
```

瑞哥在 Agent Ops 岗位上，最值钱的是把 **min 括号里最弱的那一项做对**。2026 年在绝大多数 SRE / DevOps 场景，最弱的是 **View/Harness + Accountability**——这两者恰好是你的双栈优势区。

---

## 10. 信息来源总清单

### 10.1 维度 A：Context 边际效应（18 个 URL）

1. [NoLiMa ICML 2025 (arxiv)](https://arxiv.org/html/2502.05167v3) — 最权威 effective length 量化
2. [Chroma Context Rot Research](https://www.trychroma.com/research/context-rot)
3. [RULER COLM 2024](https://arxiv.org/html/2404.06654v2)
4. [Claude Opus 4.6 官方发布](https://www.anthropic.com/news/claude-opus-4-6)
5. [Stanford CRFM HELM Long Context](https://crfm.stanford.edu/2025/09/29/helm-long-context.html)
6. [LongBench v2 (ACL 2025)](https://longbench2.github.io/)
7. [BABILong NeurIPS 2024](https://neurips.cc/virtual/2024/poster/97462)
8. [DeepMind Michelangelo](https://arxiv.org/html/2409.12640v1)
9. [AbsenceBench](https://openreview.net/pdf/ce58ab4c6a2520c9230229b129315286e79546c9.pdf)
10. [The Decoder: Gemini 2.5 vs o3](https://the-decoder.com/googles-gemini-2-5-pro-beats-openais-o3-model-in-processing-complex-lengthy-texts/)
11. [RAGFlow 2025 年终综述](https://ragflow.io/blog/rag-review-2025-from-rag-to-context)
12. [Simon Willison: long-context tag](https://simonwillison.net/tags/long-context/)
13. [Google 开发者论坛 "1m context lie"](https://discuss.ai.google.dev/t/the-1m-context-window-lie/79861)
14. [Claude Opus 4.6 vs Gemini 3 Pro 对比 (RDWorld)](https://www.rdworldonline.com/claude-opus-4-6-targets-research-workflows-with-1m-token-context-window-improved-scientific-reasoning/)
15. [MECW 2026 (Atlan)](https://atlan.com/know/llm-context-window-limitations/)
16. [Fiction.liveBench 2026](https://lmcouncil.ai/benchmarks)
17. [LangChain: Context Engineering for Agents](https://blog.langchain.com/context-engineering-for-agents/)
18. [LaRA ICML 2025](https://icml.cc/virtual/2025/poster/46069)

### 10.2 维度 B：Transformer 架构瓶颈（15 个 URL）

1. [Achilles Heel of Mamba (NeurIPS 2025 spotlight)](https://arxiv.org/abs/2509.17514)
2. [Gated Attention for LLMs (NeurIPS 2025 Best Paper)](https://openreview.net/forum?id=1b7whO4SfY)
3. [NeurIPS 2025 Best Paper Awards](https://blog.neurips.cc/2025/11/26/announcing-the-neurips-2025-best-paper-awards/)
4. [On the Fundamental Limits of LLMs at Scale](https://arxiv.org/html/2511.12869v1)
5. [Falcon-H1 Technical Report](https://arxiv.org/pdf/2507.22448)
6. [IBM Granite 4 Architecture](https://www.ibm.com/think/news/hybrid-thinking-inside-architecture-granite-4-0)
7. [IBM Granite 4 Enterprise (InfoQ)](https://www.infoq.com/news/2025/11/ibm-granite-mamba2-enterprise/)
8. [Efficient Attention Mechanisms for LLMs Survey](https://arxiv.org/html/2507.19595v3)
9. [Speed Always Wins: Efficient Architectures Survey](https://arxiv.org/html/2508.09834v1)
10. [Karpathy vs Sutton on Bitter Lesson](https://joshthompson.co.uk/ai/karpathy-vs-sutton-llms-summoning-ghosts-or-building-animals/)
11. [LeCun AMI Labs \$1B](https://letsdatascience.com/blog/yann-lecun-told-meta-he-could-do-it-faster-alone-then-he-raised-1-billion)
12. [LeCun 2026-02 JEPA Workshop keynote](https://www.linkedin.com/posts/yann-lecun_video-of-my-keynote-at-the-world-modeling-activity-7426000344268066817-o2dO)
13. [FlashAttention-3 NeurIPS 2024](https://neurips.cc/virtual/2024/poster/93328)
14. [Sebastian Raschka Visual Guide to Attention Variants](https://magazine.sebastianraschka.com/p/visual-attention-variants)
15. [MLA KV Cache Optimization](https://pyimagesearch.com/2025/10/13/kv-cache-optimization-via-multi-head-latent-attention/)

### 10.3 维度 C：信任问题本质（18 个 URL）

1. [OpenAI 2025: Why Language Models Hallucinate](https://openai.com/index/why-language-models-hallucinate/)
2. [arXiv 2509.04664 (Kalavasis & Kleinberg)](https://arxiv.org/pdf/2509.04664)
3. [Nature MI: What LLMs know and what people think they know](https://www.nature.com/articles/s42256-024-00976-7)
4. [NeurIPS 2024: Mitigating Overconfidence](https://neurips.cc/virtual/2024/102093)
5. [PMC Crisis of Overconfidence (PING framework)](https://pmc.ncbi.nlm.nih.gov/articles/PMC12874690/)
6. [MDPI Taxonomy Survey](https://www.mdpi.com/2673-2688/6/10/260)
7. [MIT Media Lab Faithfulness](https://www.media.mit.edu/projects/measuring-llm-faithfulness/overview/)
8. [Karpathy 2025 Year in Review](https://karpathy.bearblog.dev/year-in-review-2025/)
9. [Simon Willison: Hallucinations in code](https://simonwillison.net/2025/Mar/2/hallucinations-in-code/)
10. [LeCun World Models path](https://kafkai.ai/articles/ai-technology/world-models-beyond-llms-by-yann-lecun/)
11. [Gary Marcus: Scale is All You Need is dead](https://garymarcus.substack.com/p/breaking-news-scale-is-all-you-need)
12. [UX Tigers Epistemic UI](https://www.uxtigers.com/post/intent-ux)
13. [Salesforce AI Trust Patterns](https://www.salesforce.com/news/stories/ai-trust-patterns/)
14. [iopex UX Makes AI Reliable](https://www.iopex.com/blog/ai-adoption-in-ux-design)
15. [ISG State of Enterprise AI Adoption 2025](https://isg-one.com/docs/default-source/default-document-library/2025-isg-state-of-enterprise-ai-adoption-report.pdf)
16. [Tendem HITL](https://tendem.ai/blog/human-in-the-loop-ai-why-automation-alone-isnt-enough)
17. [ChatGPT Disaster Legal Cases 1000+](https://chatgptdisaster.com/0324-ai-hallucination-lawyers-sanctioned.html)
18. [6th Circuit \$116K sanctions](https://www.jdsupra.com/legalnews/6th-circuit-court-of-appeals-issues-six-5453130/)

### 10.4 维度 D：工程化路径（16 个 URL）

1. [Harrison Chase: Rise of Context Engineering](https://blog.langchain.com/the-rise-of-context-engineering/)
2. [Dex Horthy: 12-Factor Agents](https://home.mlops.community/public/videos/12-factor-agents-patterns-of-reliable-llm-applications-dexter-horthy-agents-in-production-2025-2025-08-06)
3. [Anthropic Managed Agents](https://www.anthropic.com/engineering/managed-agents)
4. [Harness Engineering (Milvus)](https://milvus.io/blog/harness-engineering-ai-agents.md)
5. [Chip Huyen: GenAI Platform](https://huyenchip.com/2024/07/25/genai-platform.html)
6. [MIT NANDA 95% failure (Fortune)](https://fortune.com/2025/08/18/mit-report-95-percent-generative-ai-pilots-at-companies-failing-cfo/)
7. [Gartner 40% canceled](https://www.gartner.com/en/newsroom/press-releases/2025-06-25-gartner-predicts-over-40-percent-of-agentic-ai-projects-will-be-canceled-by-end-of-2027)
8. [ZenML 1200 production deployments](https://www.zenml.io/blog/what-1200-production-deployments-reveal-about-llmops-in-2025)
9. [MAST Multi-Agent Failure Taxonomy (ICLR 2025)](https://arxiv.org/pdf/2503.13657)
10. [Hamel Husain: Evals FAQ](https://hamel.dev/blog/posts/evals-faq/)
11. [Insight Partners: Building Moat](https://www.insightpartners.com/ideas/building-a-moat-in-the-age-of-ai/)
12. [Tianpan: AI Wrapper Trap](https://tianpan.co/blog/2026-04-12-the-ai-wrapper-trap-when-your-moat-is-someone-elses-api-call)
13. [Sequoia + Harrison Chase: From scaffolds to harnesses](https://sequoiacap.com/podcast/context-engineering-our-way-to-long-horizon-agents-langchains-harrison-chase/)
14. [Ultrathink: 13-Layer AI Stack](https://ultrathinksolutions.com/the-signal/modern-ai-application-stack/)
15. [Anatomy of an Agent Harness](https://blog.dailydoseofds.com/p/the-anatomy-of-an-agent-harness)
16. [CrewAI: First Agent Should Do One Thing Badly](https://crewai.com/blog/your-first-ai-agent-should-do-one-thing-badly)

### 10.5 维度 E：持久价值（15 个 URL）

1. [Karpathy 2025 Year in Review](https://karpathy.bearblog.dev/year-in-review-2025/) ★
2. [Dwarkesh × Karpathy](https://www.dwarkesh.com/p/andrej-karpathy)
3. [Dwarkesh × Amodei](https://www.dwarkesh.com/p/dario-amodei-2)
4. [Dwarkesh × Sutton](https://www.dwarkesh.com/p/richard-sutton)
5. [Simon Willison: Code you have proven to work](https://simonwillison.net/2025/Dec/18/code-proven-to-work/)
6. [Kyle Kingsbury via Willison: Meat Shield](https://simonwillison.net/2026/Apr/15/kyle-kingsbury/) ★
7. [Paul Graham: Taste in AI age](https://x.com/paulg/status/2022604692178522562)
8. [Shrivu Shankar: Taste Is Not a Moat](https://blog.sshh.io/p/taste-is-not-a-moat) ★
9. [Ben Thompson: Agents Over Bubbles](https://stratechery.com/2026/agents-over-bubbles/) ★
10. [MIT Tech Review: Enterprise AI Operating Layer](https://www.technologyreview.com/2026/04/16/1135554/treating-enterprise-ai-as-an-operating-layer/)
11. [Anthropic Economic Index Mar 2026](https://www.anthropic.com/research/economic-index-march-2026-report)
12. [Nadella: Tacit knowledge leakage](https://globaladvisors.biz/2026/01/27/quote-satya-nadella-ceo-microsoft/)
13. [Salesforce: Jagged Intelligence in Enterprise](https://www.salesforce.com/blog/jagged-intelligence/)
14. [a16z: Physical AI deployment gap](https://www.a16z.news/p/the-physical-ai-deployment-gap)
15. [Berkeley CMR: Beyond Big Data Mindset](https://cmr.berkeley.edu/2025/12/beyond-the-big-data-mindset-an-executive-s-guide-to-cultivating-ai-as-talent/)

★ = 最值得完整读一遍的顶级来源

---

## 附录：调研元信息

- **并行 sub-agent 数**：5
- **总调用的 Tavily 搜索**：~35 次
- **合计返回 URL**：~100+
- **最终保留的高质量引用**：82 个
- **调研耗时**：约 20 分钟（wall clock，并行）
- **交付物**：本报告（单文件，按工作流要求）
- **工作流来源**：`rules/skills/workflow_deep_research_survey.md`

**一句话总结**：AI 的本质问题不是单一维度，而是一个 **min() 函数**——当下的工程 leverage 在 View/Harness 层，长期 moat 在 proprietary data + accountability + 慢变量，Transformer 不会被革命但会被蚕食为 hybrid，"view 层假说"方向对但需加上 model 层的理论下限修正。对瑞哥 Agent Ops 职业路径：**短期强势（3-5 年）+ 长期需 vertical 化 + 始终 SRE 双栈是稀缺组合**。
