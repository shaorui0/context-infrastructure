# 调研报告：LLM Orchestration 是否是过渡期的临时拐杖？

> 对杨博「如何看待 Devin AI software engineer」一文核心论点的深度验证

**调研日期**: 2026-04-17  
**调研方法**: 5 维度并行调研 + 交叉验证  
**调研维度**: 技术论证验证 / Orchestration 价值分解 / 行业实证 / 模型能力边界 / 反面论据（steel-man）

---

## 核心结论

**杨博的判断方向部分正确，但结论严重夸大。**

他说对了：2023-2024 年发明的许多 orchestration 模式（CoT prompting、output parsers、复杂 DAG 工作流）确实正在被模型进步淘汰。他说错了：Orchestration 层整体并没有在消失——它在 **重新分布**（redistribution）。一部分被吸收进模型权重（通过 RL 训练），一部分变成协议标准（MCP），一部分留在 harness 里但变得更薄。系统中 orchestration 的总量在增加，而不是减少。

用一句话概括：**Orchestration 不是在消亡，而是在进化——从显式的框架代码，变成模型原生能力 + 极简 harness + 协议标准的组合。**

---

## 一、杨博的三层论证逐一验证

### 1.1 第一层：工程架构的脆弱性（KV-cache 冲突）

**原文论点**: 开发者通过裁剪历史对话来节省 token 时，实际上破坏了 transformer 架构中最宝贵的 KV-cache 前缀缓存优势，在 DeepSeek 等支持动态缓存的模型上反而可能导致计算资源浪费。

**验证结果: 部分正确，但严重夸大。**

**正确的部分：**
- Prefix caching 确实要求逐 token 精确匹配。如果 prompt 开头的哪怕一个 token 改变，整个缓存链就失效。这在 OpenAI、Anthropic 文档和 vLLM 的自动前缀缓存设计中都有确认。（[vLLM Prefix Caching Design](https://docs.vllm.ai/en/stable/design/prefix_caching/)）
- DeepSeek 的缓存系统使用 64-token 块，明确说明"只有从第 0 个 token 开始完全相同的前缀才视为重复"。（[DeepSeek Context Caching API](https://api-docs.deepseek.com/guides/kv_cache)）
- Anthropic 对缓存读取提供 90% 的价格折扣——丢失缓存意味着支付全价。（[Anthropic Prompt Caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)）

**错误的部分：**
- **混淆了两个不同概念**：KV-cache（单次推理内部的注意力优化，避免对已处理 token 重复计算）和 prefix caching（跨请求复用缓存的 KV 状态，是基础设施优化）。裁剪历史不会"破坏 transformer 架构的 KV-cache"——它破坏的是跨请求的前缀缓存。
- **智能裁剪策略已经存在**：保持稳定的 system prompt 前缀、从中间而非开头裁剪、使用一致的排序——这些工程实践可以在管理 context 长度的同时保留前缀缓存命中。
- **"更多计算浪费"是错误的**：即使缓存未命中，你计算的 token 数量也等于或少于未裁剪的版本。最坏情况是"没有获得缓存折扣"，而不是"比未缓存基线消耗更多计算"。
- DeepSeek 的 Multi-Head Latent Attention (MLA) 将 KV cache 压缩了 57 倍（每 token 从 4MB 降至 70KB），大幅降低了缓存未命中的成本。

### 1.2 第二层：技术路线的短视性（推理模型使 Orchestration 过时）

**原文论点**: 现有 agentic coding 原型大多定型于推理模型技术普及之前。笨重的 Orchestration 层在推理模型提升后不仅无法带来增益，还会因为过度干预模型的自主决策而降低输出质量。

**验证结果: 方向部分正确，但"过度约束"假说缺乏实证。**

**推理模型确实提高了 floor：**
- OpenAI 特别强调 o3 在 SWE-bench 上的结果是"without building a custom model-specific scaffold"。（[OpenAI o3 发布](https://openai.com/index/introducing-o3-and-o4-mini/)）
- Claude Code 的架构故意极简：单线程 agent 循环（`while(tool_call) → execute → feed results → repeat`），18 个工具，没有多 agent swarm。Anthropic 明确选择了这种方式而非复杂编排。（[Claude Code Architecture](https://www.zenml.io/llmops-database/claude-code-agent-architecture-single-threaded-master-loop-for-autonomous-coding)）
- Wharton GAIL 研究发现，对推理模型使用 CoT prompting 仅带来 2.9-3.1% 的准确率提升，却增加 20-80% 的时间消耗。（[Wharton GAIL — Decreasing Value of CoT](https://gail.wharton.upenn.edu/research-and-insights/tech-report-chain-of-thought/)）

**但 scaffold 仍然重要：**
- 同一模型在不同 scaffold 下仍有 **12-30 分的差距**。SWE-bench Pro 显示，基础和优化 scaffold 之间有 22+ 分的 swing。（[Epoch AI — Why Benchmarking is Hard](https://epochai.substack.com/p/why-benchmarking-is-hard)）
- Epoch AI 的核心发现："一个优秀的模型配上平庸的 scaffold，会输给一个良好的模型配上出色的 scaffold。"这在 2026 年仍然成立。
- **没有已发表的 benchmark 显示推理模型在有 orchestration 时表现更差**。"过度约束"说是理论假设，不是实证结论。

**关键区分：** 坏的 orchestration（僵化的、过度规定性的工作流）确实有害；好的 orchestration（轻量的、自适应的、最小约束的）仍然有益。这不是二元对立。

### 1.3 第三层：技术代差（NSA+ / 长 Context 消除外部 Context 管理）

**原文论点**: NSA+（Native Sparse Attention）等新一代注意力机制正在改写游戏规则。模型可以通过稀疏注意力自主管理 context，外部上下文管理规则变得毫无必要。超长上下文窗口 + 动态稀疏计算将历史管理内化为模型自身能力。

**验证结果: 错误。**

**"NSA+" 在公开文献中不存在。** 实际发表的工作是 NSA（2025 年 2 月，[arXiv 2502.11089](https://arxiv.org/abs/2502.11089)，ACL 2025 最佳论文）和 DSA（DeepSeek Sparse Attention，2025 年 9 月部署在 V3.2 中）。后续论文 NOSA（2025 年 10 月）也不叫 "NSA+"。杨博可能引用了一个不存在的术语。

**NSA 是计算效率优化，不是语义理解提升：**
- NSA 论文自身指出："可训练的稀疏注意力只能缓解 memory-bound 瓶颈，不能减少 KV cache 大小。因此，可训练的稀疏注意力对最大可达到的 batch size 没有改善。"（[arXiv 2502.11089](https://arxiv.org/abs/2502.11089)）
- NSA 在稀疏阶段每个 query 只选择 ~2048 个 KV 条目——它在做近似，不是保证模型"理解"所有 context。

**Context Rot 是普遍现象：**
- Chroma 2025 年的研究测试了 18 个前沿模型（GPT-4.1, Claude Opus 4, Gemini 2.5 等），发现：
  > "As you add tokens to an LLM's input, the quality of its output decreases... every [model] exhibits this behavior at every input length increment tested."
  
  200K 窗口的模型在约 130K token 时变得不可靠，显著退化出现得更早。（[Chroma — Context Rot](https://research.trychroma.com/context-rot)）

- "Lost in the Middle" 现象持续存在：模型对 context 开头和结尾的处理较好，但对中间部分的处理显著退化，准确率下降 30%+，即使是明确为长 context 设计的模型也如此。（[MIT Press/TACL — Lost in the Middle](https://direct.mit.edu/tacl/article/doi/10.1162/tacl_a_00638/119630/Lost-in-the-Middle-How-Language-Models-Use-Long)）

- **有效 context 远小于广告 context**：最高可达 99% 的差距。有些顶级模型在 context 仅有 100 token 时就开始失败。（[OAJAIML — Maximum Effective Context Window](https://www.oajaiml.com/uploads/archivepdf/643561268.pdf)）

- **行业正在转向更好的 context 管理，而不是更大的 context 窗口**。Zylos Research 2026 年分析："Context windows are expected to stay fairly constant in 2026... the industry shifts focus to inference-time scaling, better context management, and hybrid approaches."（[Zylos Research](https://zylos.ai/research/2026-01-19-llm-context-management)）

---

## 二、Orchestration 层的价值分解：什么会消亡，什么会留存

| 类别 | 当前重要性 | 模型进步威胁 | 持久性判断 | 关键证据 |
|------|----------|------------|-----------|---------|
| **Context Management** | 高 | 中等 | **持久** — 形式变，需求在 | RAG 比长 context 便宜 8-82x（[Meilisearch](https://www.meilisearch.com/blog/rag-vs-long-context-llms)）；混合方案在 7/8 企业场景中胜出 |
| **Tool Integration (MCP)** | 高且快速增长 | 低（反而放大需求）| **非常持久** | MCP SDK 下载：2M → 68M/月（[MCP Wiki](https://en.wikipedia.org/wiki/Model_Context_Protocol)）；加入 Linux Foundation |
| **Safety & Oversight** | 关键 | 低 | **非常持久** | 结构性不信任：不能让被审计的实体自己当审计员。企业信任度仅 0-20% |
| **Workflow Coordination** | 高 | 中高 | **混合** | 简单 plan-execute 循环被推理模型吸收；多会话协调、跨边界错误恢复留存 |
| **System Boundary Mgmt** | 高且增长中 | 极低 | **最持久** | Git、CI/CD、部署本质上是模型外部的状态机，模型产生文本而非系统调用 |

Anthropic 自己的工程博客给出了最精准的定义："the principal deficit of agentic systems is not the model's intelligence but the quality of the world assembled for it."（[Anthropic — Effective Context Engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)）

**"Context Engineering"** 正在成为 "Prompt Engineering" 的继任学科——而它本质上就是 orchestration 的另一个名字。问题没有消失，只是被重新定义了。

---

## 三、行业实证：市场告诉我们什么

### 3.1 Devin 的命运

杨博说"Devin AI 没有前途"——**作为产品形态的判断部分正确，作为公司判断完全错误。**

- Answer.AI 2025 年 1 月评估：20 个真实任务中 14 个失败，3 个成功（[Wikipedia — Devin AI](https://en.wikipedia.org/wiki/Devin_AI)）
- 但 Cognition 迅速转型：ARR 从 ~$1M（2024.09）增长到 **~$73M**（2025.06）
- 以 $250M 收购 Windsurf，转向"agent-powered IDE"而非纯自主 agent（[Cognition — Windsurf Acquisition](https://cognition.ai/blog/windsurf)）
- Goldman Sachs 在 12,000 人编程团队中试点 Devin，报告重复性任务 3-4x 生产力提升

**Cognition 的转型恰好验证了杨博说对的部分**："纯自主 agent"形态确实有问题——但解决方案不是"去 orchestration"，而是更好的 orchestration（human-in-the-loop IDE）。

### 3.2 市场增长方向

| 指标 | 数据 |
|------|------|
| AI 编码工具市场规模 | $7B+/年（2026.04） |
| Cursor 估值 | $29.3B → 传闻 $60B |
| Cursor ARR | $2B（2026.03） |
| 开发者使用率 | 85% 定期使用 AI 编码工具 |
| 多 Agent 系统咨询量 | Gartner 报告 Q1 2024 → Q2 2025 增长 **1,445%** |

**关键发现：两家头部公司正在训练自己的编码专用模型。**
- Cursor 推出 **Composer 2**：CursorBench 61.3 分（vs Opus 4.6 的 58.2），$0.50/M tokens（Anthropic 的 1/10）。Cursor 不再只是 IDE 公司，而是模型公司。（[Cursor Composer 2 Benchmarks](https://topaiproduct.com/2026/03/19/cursor-composer-2-takes-on-anthropic-and-openai-with-a-0-50-m-token-coding-model-and-the-benchmarks-back-it-up/)）
- Cognition 训练 **SWE-1.5**：通过端到端 RL 在真实任务环境中训练，本质上是把 orchestration 逻辑烘焙进模型权重。（[Cognition — SWE-1.5](https://cognition.ai/blog/swe-1-5)）

**这是杨博论点最有力的间接验证**：orchestration 确实在被"吸收"——但不是通过去除 scaffold，而是通过 **RL 训练将 orchestration 行为内化到模型权重中**。

### 3.3 SWE-bench 告诉我们什么

SWE-bench Verified 排行榜（2026.04）：
1. Claude Mythos Preview: 93.9%（可能是专门化系统）
2. GPT-5.3 Codex: 85%
3. Claude Opus 4.5: 80.9%
4. Claude Opus 4.6: 80.8%

但 **SWE-bench Pro**（更困难、更接近真实场景）最高分仅 ~23%，显示 curated benchmark 和真实场景之间存在巨大鸿沟。（[Scale AI — SWE-bench Pro](https://labs.scale.com/leaderboard/swe_bench_pro_public)）

**架构独立于模型发挥作用**：Scale AI 的标准化测试（相同工具、250 轮限制）显示同一模型在不同 agent 框架下可以有 **30 分的差距**。更好的 context 检索单独就能增加 4-10 分。

---

## 四、Steel-Man：杨博说对了什么

公平地说，杨博的论点有几个方面获得了实证支持：

### 4.1 确实被淘汰的 Orchestration 模式

| 被淘汰的模式 | 替代方案 | 证据强度 |
|-------------|---------|---------|
| CoT prompting | 推理模型内置推理 | **强** — Wharton 研究，+2.9% 准确率 / +20-80% 时间 |
| Output parsers / retry loops | Structured Outputs API | **强** — 合规率 35% → 100% |
| Few-shot template 机制 | 零样本能力提升 | **中等** — 某些任务 few-shot 反而降低性能 |
| 基本 tool calling 编排 | 原生 function calling API | **强** — 已成所有主要 API 的标准参数 |
| 视觉 OCR pipeline | 多模态输入 | **强** — GPT-4V/Claude 3/Gemini 原生支持 |

### 4.2 "简单胜于复杂"有权威背书

Anthropic 自己的官方指南（[Building Effective Agents](https://www.anthropic.com/research/building-effective-agents)）明确说：

> "Consistently, the most successful implementations weren't using complex frameworks or specialized libraries. Instead, they were building with **simple, composable patterns**."

> "**Do the simplest thing that works** will likely remain the best advice for teams building agents on top of Claude."

### 4.3 成本趋势确实在削弱经济论证

a16z 的"LLMflation"数据（[a16z — LLMflation](https://a16z.com/llmflation-llm-inference-cost/)）：
- 等效质量推理成本：**每年下降 10 倍**（比摩尔定律快）
- GPT-3 质量水平：2025 年比 2021 年便宜 **1,000 倍**
- GPT-4 等效性能：从 $20/M tokens（2022 年底）降至 $0.40/M tokens（2025 年）

**但关键的 caveat**：前沿推理模型的定价保持相对稳定。成本暴跌主要发生在旧的、非推理模型上。（[Epoch AI — Inference Price Trends](https://epoch.ai/data-insights/llm-inference-price-trends/)）

---

## 五、最终判断：Orchestration 的真实命运

### 5.1 杨博的框架 vs 实际发生的事情

| 杨博的预测 | 实际发生的事情 |
|-----------|-------------|
| Orchestration 是过渡期拐杖 | Orchestration 是在进化，不是在消亡 |
| 模型进步会消除 orchestration 需求 | 模型进步消除了部分 pattern，但创造了新的 orchestration 需求 |
| 过渡期比大多数人预期更短暂 | 市场规模和投资在加速增长（Cursor $60B，Gartner +1,445%） |
| 模型厂商可以把裸模型变成原生 Agent | 确实在发生（SWE-1.5, Composer 2），但通过 RL 训练而非去 scaffold |
| Token 计费模式不可持续 | 计算成本不会归零，推理模型定价相对稳定 |

### 5.2 更准确的描述

**Orchestration 不是在消亡，而是在发生三重 redistribution：**

1. **吸收进模型权重**：通过 RL 训练，orchestration 行为（plan-execute 循环、错误恢复、工具选择）被烘焙进专用模型（SWE-1.5, Composer 2）。这是杨博论点最有力的验证——但实现方式不是"去 scaffold"，而是"scaffold → 训练数据 → 模型权重"。

2. **标准化为协议**：MCP 将 N×M 的 tool 集成问题简化为 N+M。这不是 orchestration 消失，而是 orchestration 基础设施化——就像 HTTP 之于 web。

3. **极简化为 harness**：Claude Code 的 ~50 行 TAOR 循环、Codex CLI 的 Responses API + AGENTS.md。Orchestration 仍然存在，但从数千行 LangChain 代码变成了几十行 agent loop。

### 5.3 杨博犯的核心错误

**他把 infrastructure 当成了 workaround。**

Orchestration 层中确实有一部分是 workaround（context 裁剪、CoT prompting、output parsing），这部分正在被淘汰。但另一部分是 **essential complexity**（tool integration、safety gates、system boundary management、workflow coordination），这部分随模型进步而演化，不会消失。

用软件工程的类比：这就像说"因为 CPU 越来越快，所以操作系统会消失"。CPU 变快确实消除了一些 OS 层的优化（早期的内存覆盖技术、手动 DMA 管理），但 OS 的核心功能（进程管理、权限控制、设备驱动、文件系统）不仅没有消失，反而随着硬件进步变得更加重要。

### 5.4 杨博那篇文章最有价值的洞察

尽管结论夸大，杨博的文章有一个深刻的洞察值得保留：

**"任何依赖中间层抽象来填补底层缺陷的方案，最终都会被底层技术的进步淘汰。"**

这个原则是对的。它准确描述了 CoT prompting、output parsers、few-shot templates 的命运。错误在于把 **所有** orchestration 都归类为"填补底层缺陷"。Tool integration、safety oversight、system boundary management 不是在填补模型的缺陷——它们在管理模型与外部世界的 **接口**。接口问题不会因为任何一方变强而消失。

---

## 附录：数据来源完整列表

### 技术论证验证 (D1)
- [vLLM Automatic Prefix Caching Design](https://docs.vllm.ai/en/stable/design/prefix_caching/)
- [DeepSeek Context Caching API](https://api-docs.deepseek.com/guides/kv_cache)
- [DeepSeek MLA KV Cache Optimization](https://medium.com/@zdj0712/naive-vs-optimized-attention-caching-in-transformers-why-kv-cache-saves-so-much-memory-68b1858f3943)
- [NSA Paper (arXiv 2502.11089)](https://arxiv.org/abs/2502.11089)
- [NSA at ACL 2025](https://aclanthology.org/2025.acl-long.1126/)
- [Sparse Attention from NSA to DSA](https://champaignmagazine.com/2025/09/30/ai-on-ai-sparse-attention-from-nsa-to-dsa/)
- [DeepSeek-V3.2 Sparse Attention](https://developers.redhat.com/articles/2025/10/03/deepseek-v32-exp-vllm-day-0-sparse-attention-long-context-inference)
- [Context Rot (Chroma Research)](https://research.trychroma.com/context-rot)
- [Lost in the Middle (MIT Press/TACL)](https://direct.mit.edu/tacl/article/doi/10.1162/tacl_a_00638/119630/Lost-in-the-Middle-How-Language-Models-Use-Long)
- [Maximum Effective Context Window (OAJAIML)](https://www.oajaiml.com/uploads/archivepdf/643561268.pdf)
- [LLM Context Management 2026 (Zylos Research)](https://zylos.ai/research/2026-01-19-llm-context-management)
- [Anthropic Prompt Caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)
- [OpenAI Prompt Caching 201](https://developers.openai.com/cookbook/examples/prompt-caching-201)
- [NOSA (arXiv)](https://arxiv.org/html/2510.13602v1)

### Orchestration 价值分解 (D2)
- [Anthropic — Effective Context Engineering for AI Agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
- [Anthropic — Effective Harnesses for Long-Running Agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)
- [Anthropic — Writing Effective Tools for Agents](https://www.anthropic.com/engineering/writing-tools-for-agents)
- [Anthropic 2026 Agentic Coding Trends Report](https://resources.anthropic.com/hubfs/2026%20Agentic%20Coding%20Trends%20Report.pdf)
- [Addy Osmani — Conductors to Orchestrators](https://addyosmani.com/blog/future-agentic-coding/)
- [Claude Code Architecture (ZenML)](https://www.zenml.io/llmops-database/claude-code-agent-architecture-single-threaded-master-loop-for-autonomous-coding)
- [OpenHands SDK (arXiv)](https://arxiv.org/html/2511.03690v1)
- [MCP Technical Deep Dive](https://dasroot.net/posts/2026/04/model-context-protocol-mcp-technical-deep-dive/)
- [MCP Wikipedia](https://en.wikipedia.org/wiki/Model_Context_Protocol)
- [RAGFlow — From RAG to Context](https://ragflow.io/blog/rag-review-2025-from-rag-to-context)
- [RAG vs Long Context 2026](https://markaicode.com/vs/rag-vs-long-context/)
- [Meilisearch — RAG vs Long Context LLMs](https://www.meilisearch.com/blog/rag-vs-long-context-llms)
- [n8n — AI Agent Development Tools 2026](https://blog.n8n.io/we-need-re-learn-what-ai-agent-development-tools-are-in-2026/)
- [Simon Willison — 2025 The Year in LLMs](https://simonwillison.net/2025/Dec/31/the-year-in-llms/)

### 行业实证 (D3)
- [Codegen Blog — Best AI Coding Agents 2026](https://codegen.com/blog/best-ai-coding-agents/)
- [Devin AI — Wikipedia](https://en.wikipedia.org/wiki/Devin_AI)
- [Cognition — Devin 2025 Performance Review](https://cognition.ai/blog/devin-annual-performance-review-2025)
- [Cognition — Windsurf Acquisition](https://cognition.ai/blog/windsurf)
- [Cognition — SWE-1.5](https://cognition.ai/blog/swe-1-5)
- [Cursor Composer 2 Benchmarks](https://topaiproduct.com/2026/03/19/cursor-composer-2-takes-on-anthropic-and-openai-with-a-0-50-m-token-coding-model-and-the-benchmarks-back-it-up/)
- [Anysphere $29.3B Valuation](https://techfundingnews.com/anysphere-soars-to-29-3b-valuation-with-2-3b-funding-redefining-the-future-of-coding/)
- [Stack Overflow 2025 Developer Survey — AI](https://survey.stackoverflow.co/2025/ai)
- [JetBrains AI Coding Tools Survey 2026](https://blog.jetbrains.com/research/2026/04/which-ai-coding-tools-do-developers-actually-use-at-work/)
- [SWE-bench Verified (Epoch AI)](https://epoch.ai/benchmarks/swe-bench-verified)
- [SWE-bench Pro (Scale AI)](https://labs.scale.com/leaderboard/swe_bench_pro_public)
- [VentureBeat — Agentic Coding at Enterprise Scale](https://venturebeat.com/orchestration/agentic-coding-at-enterprise-scale-demands-spec-driven-development/)

### 模型能力边界 (D4)
- [OpenAI — Introducing o3 and o4-mini](https://openai.com/index/introducing-o3-and-o4-mini/)
- [OpenAI — Unrolling the Codex Agent Loop](https://openai.com/index/unrolling-the-codex-agent-loop/)
- [Anthropic — Building Effective Agents](https://www.anthropic.com/research/building-effective-agents)
- [Anthropic — The Think Tool](https://www.anthropic.com/engineering/claude-think-tool)
- [Claude Code — How It Works](https://code.claude.com/docs/en/how-claude-code-works)
- [Epoch AI — Why Benchmarking is Hard](https://epochai.substack.com/p/why-benchmarking-is-hard)
- [SWE-bench Verified Leaderboard](https://www.swebench.com/verified.html)
- [Claude Opus 4.7](https://www.anthropic.com/claude/opus)
- [DeepSeek R1-0528 Analysis](https://medium.com/@leucopsis/deepseeks-new-r1-0528-performance-analysis-and-benchmark-comparisons-6440eac858d6)
- [Multi-Agent Orchestration Clinical Workloads (Nature)](https://www.nature.com/articles/s44401-026-00077-0)

### 反面论据 / Steel-Man (D5)
- [Wharton GAIL — Decreasing Value of CoT](https://gail.wharton.upenn.edu/research-and-insights/tech-report-chain-of-thought/)
- [OpenAI — Structured Outputs](https://openai.com/index/introducing-structured-outputs-in-the-api/)
- [LangChain — Deep Agents](https://blog.langchain.com/deep-agents/)
- [Yann LeCun AMI Labs (MIT Technology Review)](https://www.technologyreview.com/2026/01/22/1131661/yann-lecuns-new-venture-ami-labs/)
- [Karpathy — 2025 LLM Year in Review](https://karpathy.bearblog.dev/year-in-review-2025/)
- [a16z — LLMflation](https://a16z.com/llmflation-llm-inference-cost/)
- [Epoch AI — Inference Price Trends](https://epoch.ai/data-insights/llm-inference-price-trends/)
- [知乎 — 2025 开源 AI Agent 工具全景图](https://zhuanlan.zhihu.com/p/1992410866923091778)
