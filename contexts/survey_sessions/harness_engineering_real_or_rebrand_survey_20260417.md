# Harness Engineering：是真的工程升级，还是文字游戏？

**调研日期**：2026-04-17
**方法**：Tavily 初步扫描 → 5 维度并行 sub-agent 调研 → 交叉验证 → 整合
**维度**：术语起源 / 技术实质 / 批评质疑 / 演化脉络 / 实证证据

---

## TL;DR（核心结论）

**不是纯文字游戏，但营销泡沫确实存在。诚实的描述是"70-90% 老东西 + 10-30% 新原语 + 100% 的重新框架化"。**

三件事可以确认：

1. **"Agent = Model + Harness" 这个公式是 2026 Q1 的新行业共识**，由 Mitchell Hashimoto（2026-02-05 命名）、OpenAI（2026-02-11）、LangChain（2026-03-10）、Martin Fowler（2026-04-02）在 8 周内集中输出完成。但**连这些核心提出者都主动承认定义过宽、边界模糊**——Fowler 自己在 memo 里自嘲"用不了多久就会有人把单 prompt 的 code review agent 也叫 harness"。

2. **技术上真正 2025-2026 才成熟的原语只有 3-4 个**：Progressive-disclosure Skills（markdown-only harness）、Lifecycle Hooks 作为 deterministic control layer、Agent-aware auto-compaction、Harness-model co-training（Codex `apply_patch`、Claude `bash` tool 在 post-training 阶段固化）。其余（system prompt + tool loop、subagent、sandbox、state graph、guardrails）在 ReAct（2022）/ AutoGPT（2023）/ LangChain / CrewAI 时代就有。

3. **硬数据严重不足**：Anthropic 自己的 "Effective harnesses for long-running agents" 博客 0 个 before/after 数字；OpenAI 的 "1M LOC / 5 个月 / 0% 人写代码" 是 N=1 自述、前 1.5 个月还比手写慢 10 倍；Mitchell Hashimoto 在 Ghostty 上拒绝给硬数字。唯一可复现的硬证据是 **Terminal-Bench 2.0 同模型跨 harness 3.3-6.5pp 差距**和 **SWE-bench Pro 5-12pp swing**——但 Scale AI SWE-Atlas 反声这是 "essentially noise within margin of error"。

**判断框架**：这和 "DevOps 只是系统管理员改名"的争论同构。技术组件高度重叠，但**工程 scope、治理关切、用例规模**确实发生了质变——长时 autonomous、多 session、十亿 token/天、需要 tool permission pipeline 和 verification loop。老词 "scaffold" 的 PoC 味扛不起这些新关切，于是业界需要一个新词。这是"量变积累成质变的重命名"，不是纯营销。

---

## 1. 起源时间线：一个新词的 8 周诞生史

根据 Andrew Maynard 学术追溯 ([PDF](https://andrewmaynard.net/papers/Rapid_Adoption_Harness_Metaphor_AI_V1.pdf)) 和多源交叉验证：

| 时间 | 事件 | 关键出处 |
|---|---|---|
| **2025-11** | Anthropic "Effective Harnesses for Long-Running Agents" 首次把 Claude Agent SDK 称为 "a powerful, general-purpose agent harness"。已知最早正式用法。 | Anthropic eng blog |
| **2026-01** | Phil Schmid、Aakash Gupta 断言 "2025 was agents. 2026 is agent harnesses" | 推文/博客 |
| **2026-02-05** | **Mitchell Hashimoto 《My AI Adoption Journey》正式命名 "harness engineering"** | [mitchellh.com](https://mitchellh.com/writing/my-ai-adoption-journey) |
| **2026-02-11** | OpenAI 官方 "Harness engineering: leveraging Codex in an agent-first world" 采纳术语 | [openai.com/index/harness-engineering](https://openai.com/index/harness-engineering/) |
| **2026-02-17** | Martin Fowler 博客 memo 初版（Birgitta Böckeler） | [Fowler memo](https://martinfowler.com/articles/exploring-gen-ai/harness-engineering-memo.html) |
| **2026-02-18** | Ethan Mollick 把 AI 框架组织为 "Models, Apps, and Harnesses" | Mollick substack |
| **2026-03-10** | LangChain Vivek Trivedy "The Anatomy of an Agent Harness"，给出最被引用的组件清单 | [blog.langchain.com](https://blog.langchain.com/the-anatomy-of-an-agent-harness/) |
| **2026-04-02** | Fowler/Böckeler 扩写为正式文章，引入 Guides+Sensors 二元结构 | [martinfowler.com](https://martinfowler.com/articles/harness-engineering.html) |
| **2026-04-04** | Sebastian Raschka "Components of a Coding Agent" 给出 6 组件版本 | [sebastianraschka.com](https://magazine.sebastianraschka.com/p/components-of-a-coding-agent) |
| **2026-04-08** | Anthropic 发布 Claude Managed Agents，harness 产品化 | anthropic.com/engineering/managed-agents |

**Hashimoto 命名时的原话**（关键引用）：

> "I don't know if there is a broad industry-accepted term for this yet, but I've grown to calling this 'harness engineering.' It is the idea that anytime you find an agent makes a mistake, you take the time to engineer a solution such that the agent never makes that mistake again. I don't need to invent any new terms here; if another one exists, I'll jump on the bandwagon."
>
> — Mitchell Hashimoto, [My AI Adoption Journey](https://mitchellh.com/writing/my-ai-adoption-journey), 2026-02-05

注意 Hashimoto 的定义是**行为论/过程论**的（"犯错 → 永久修复"的闭环），不是结构论的（"harness 由什么组件组成"）。他自己也承认命名带有偶发性。

Maynard 在学术追溯里给出精辟观察：

> "What is striking about this sequence is not just the speed but the layering. The metaphor was already embedding itself into engineering practice before anyone named it as a formal approach. By the time Hashimoto gave it a label, the conceptual commitments the metaphor carries were already in place — which made the naming feel natural rather than contested."

**换句话说**：不是 Hashimoto 发明了新概念，而是 2025 下半年积累的实践到了"必须命名"的压力点，他顺手贴了个标签。

---

## 2. 权威定义的混战：中心共识、边缘争议

### 2.1 核心公式（基本共识）

**"Agent = Model + Harness"** — LangChain Trivedy 2026-03-10：

> "Agent = Model + Harness. If you're not the model, you're the harness. A harness is every piece of code, configuration, and execution logic that isn't the model itself."
>
> — [blog.langchain.com](https://blog.langchain.com/the-anatomy-of-an-agent-harness/)

Martin Fowler、Sebastian Raschka、Anthropic 均采用此公式。Anthropic 在 [Demystifying evals for AI agents](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents) 里**直接把 harness 和 scaffold 并列为同义词**（唯一做出等价声明的权威来源）：

> "An agent harness (or scaffold) is the system that enables a model to act as an agent."

### 2.2 边界争议（硬矛盾）

**层次关系上存在至少三种互斥定义**：

| 主张 | 谁提的 | 出处 |
|---|---|---|
| harness = runtime | Salesforce | [salesforce.com](https://www.salesforce.com/agentforce/ai-agents/agent-harness/) |
| harness ≠ runtime（framework/runtime/harness 三者分立） | Harrison Chase / LangChain | [Sequoia podcast](https://www.sequoiacap.com/podcast/context-engineering-our-way-to-long-horizon-agents-langchains-harrison-chase/) |
| harness ⊂ context engineering | HumanLayer | [humanlayer.dev](https://www.humanlayer.dev/blog/skill-issue-harness-engineering-for-coding-agents) |
| context engineering ⊂ harness | Louis Bouchard / Data Science Dojo | [louisbouchard.ai](https://www.louisbouchard.ai/harness-engineering/), [datasciencedojo.com](https://datasciencedojo.com/blog/harness-engineering/) |

**同一个词 harness vs context engineering 的层次关系在主流文献里至少有三种互相矛盾的定义**——这是概念不稳定的硬伤。Atlan 的调研[直接承认](https://atlan.com/know/harness-engineering-vs-prompt-engineering/)："That definitional instability is real."

### 2.3 核心提出者自己都承认定义模糊

- **Trivedy**：_"There are many messy ways to split the boundaries of an agent system between the model and the harness."_
- **Fowler/Böckeler**：_"That is a very wide definition, and therefore worth narrowing down."_（并在 memo 里调侃 _"I can probably hold my metaphorical breath until somebody calls their one-prompt, LLM-based code review agent a harness…"_）
- **Harrison Chase**（LinkedIn 原帖，Sequoia 转述）：_"I don't think there is yet a super clear definition of any of these."_

⚠️ **来源失效警告**：Harrison Chase 原文 `blog.langchain.com/agent-frameworks-runtimes-and-harnesses-oh-my/` **目前返回 404**。只能通过 Sequoia 播客、VentureBeat 转述、LinkedIn 帖子还原。这是一个重要权威来源不可永久引用的问题。

---

## 3. 技术实质：老组件 + 少数真新原语

### 3.1 权威组件清单（LangChain Trivedy + Sebastian Raschka + Fowler 三方合并）

| 组件 | 具体内容 | 新旧判断 |
|---|---|---|
| System prompt / persona | 核心身份、工具使用协议 | **旧**（ReAct 2022） |
| Tools & descriptions | Bash/Read/Edit/Write 等原生工具 | **旧**（function calling 2023-06） |
| **Skills（procedural markdown + progressive disclosure）** | SKILL.md + YAML frontmatter，body 按需读 | **⭐ 新**（Anthropic 2025-10） |
| MCPs（外部 tool 协议） | OAuth、lazy discovery | 旧瓶新酒 |
| Bundled infrastructure | filesystem、sandbox、headless browser | **旧** |
| Orchestration logic | subagent spawning、handoffs、model routing | **旧**（AutoGen/CrewAI 2023-24） |
| **Hooks / middleware（PreToolUse/PostToolUse 等）** | 12+ lifecycle 事件，deterministic 代码劫持 LLM 决策 | **⭐ 新**（Claude Code 2025-26） |
| **Context engineering（auto-compaction, observation masking）** | ACON 26-54% token 缩减，保 95%+ 精度 | **⭐ 新**（2025 Q3 以后） |
| Memory / state persistence | AGENTS.md/CLAUDE.md 作为跨 session 记忆 | 旧瓶新酒 |
| Guides vs Sensors（Fowler 二元结构） | Computational（linter/type checker）vs Inferential（LLM-as-judge） | 旧，但新提出分类 |
| Verification loops | 测试、lint 自动重试 | **旧**（test harness 本就是） |
| **Harness-model co-training** | Codex `apply_patch`、Claude `bash` 在 post-training 固化 | **⭐ 新**（2025-26） |

**2024 年之前就有的**：system prompt + tool use loop、subagent orchestration、sandbox、guardrails、memory file、verification loop、test harness 基础概念。

**2025-2026 真正涌现的 4 个新原语**：
1. Progressive-disclosure Skills（filesystem-as-RAM，LLM 语义路由 vs regex 匹配）
2. Lifecycle Hooks 作为 deterministic control layer（类比"Express 中间件 for agent decisions"）
3. Agent-aware auto-compaction（server-side API，`clear_tool_uses_20250919`）
4. Harness-model co-training（harness 和 model 不再正交——Codex 的 apply_patch 格式在模型训练时就固化）

### 3.2 实例对比：Claude Code vs DeepAgents vs Codex vs OpenCode

| 组件 | Claude Code | DeepAgents | Codex CLI | OpenCode | Cursor |
|---|---|---|---|---|---|
| System prompt | 闭源 | 开放可配 | 开源 Rust | 开放 | 闭源 + `.cursor/rules` |
| Tool set | edit/write/bash | 同 | **apply_patch 专属** | 双模式 mimic | IDE-native |
| Skills | ✅ 原生 | ✅ SkillsMiddleware | ✅（2026 Q1 添加） | ✅ | 部分 |
| Hooks/middleware | ✅ 12+ events | ✅ LangGraph middleware | ✅ | ✅ | ❌ |
| Subagent spawning | Task tool | task tool | subagents | ✅ | ❌ |
| Sandbox | seatbelt/bwrap | 后端可插拔 | **三档显式**（read-only / workspace-write / danger-full-access） | 可选 | 编辑器内 |
| Memory markdown | CLAUDE.md | AGENTS.md | AGENTS.md | AGENTS.md | `.cursor/rules` + AGENTS.md |
| LSP integration | 弱 | 无 | 无 | **⭐ 差异化** | ⭐ 原生 IDE |

**关键观察**（HumanLayer [原话](https://www.humanlayer.dev/blog/skill-issue-harness-engineering-for-coding-agents)）：

> "The Codex models are so tightly coupled with the Codex harness's `apply_patch` tool that OpenCode... had to add an `apply_patch` tool specifically for GPT/Codex models to mimic the Codex harness."

这是 **harness-model co-training 的实证**——harness 不再是可自由替换的外部 scaffold。

### 3.3 Markdown Harness（CLAUDE.md / AGENTS.md / Skills）的新旧

**概念旧（`.editorconfig`、`.eslintrc` 就这么做），格式和加载机制新**：
- **运行时 by-LLM 语义路由**（Skills description 交给模型自己判断是否触发）
- **Progressive disclosure 作为 context 管理策略**（metadata → instructions → reference files 三层按需加载）
- **AGENTS.md 作为跨 harness 标准**（2026 Q1 Cursor/Codex/Claude Code 统一支持）

---

## 4. 批评声音谱系：四种质疑

### 4.1 "90% 老 + 10% 新" 派（最锋利）

**Akshay Kokane**, ["Agent Harness is Just System Design with a New Name"](https://levelup.gitconnected.com/agent-harness-is-just-system-design-with-a-new-name-d91be4a648c5)：

> "90% of agent harness engineering is systems design you already know, applied to a new substrate. The remaining 10% is genuinely novel: designing around non-deterministic outputs and finite, degradable context windows... So yes, agent harness is just system design. But it's system design for a runtime that hallucinates."

**值得承认的 10% 新**：非确定性 runtime + 降级的 context window 作为一等公民资源。剩余 90% 是 retries、state machines、idempotency、observability 这种老工程师的基础技能。

### 4.2 术语通胀派（整条链都在换名字）

**Serge Liatko**, [OpenAI Community Forum](https://community.openai.com/t/prompt-engineering-is-dead-and-context-engineering-is-already-obsolete-why-the-future-is-automated-workflow-architecture-with-llms/1314011)：

> "Hey guys, usually I rather stay silent on 'new' buzz-words... the 'context' is something most of you already knew the importance of and used the 'new' approach for years... both prompt and context engineering have already become outdated. They are, at best, transitional scaffolding."

Liatko 反对的不是某个具体术语，而是**"每隔几个月发明一个新词"这个游戏本身**。

**Epsilla** 的自我背刺文章 ["Beyond the Harness"](https://www.epsilla.com/blogs/the-end-of-harness-engineering-enterprise-environment-agents)：

> "The lexicon of AI engineering is experiencing a kind of hyperinflation. We've been on a dizzying treadmill of terminology, accelerating from Prompt Engineering in 2023 to Context Engineering, and then to Harness Engineering in late 2025. Now, a new term is dominating engineering discourse in Silicon Valley: 'Environment Engineering.'"

**bits-bytes-nn** 博客直接预言 ["2027 再出新名字"](https://bits-bytes-nn.github.io/insights/agentic-ai/2026/04/05/evolution-of-ai-agentic-patterns-en.html)：

> "'prompt engineering' became a household term in 2023, 'harness engineering' will be by 2027 or so. And by then, someone will show up with yet another new name. That's this industry."

### 4.3 商业博弈派（Latent.Space 最诚实）

**swyx**, ["Is Harness Engineering real?"](https://www.latent.space/p/ainews-is-harness-engineering-real)：

> "The central tension is between **Big Model and Big Harness**. [An AI framework founder you all know] once confided in me at an OpenAI event: 'I'm not even sure these guys want me to exist.' Obviously Big Harness guys are trying to sell you their Harness, Big Model guys are trying to sell you their Model."

**Big Harness 阵营**：LangChain、HumanLayer、Factory、Cursor、Cognition——需要 harness 概念存在才能卖东西。
**Big Model 阵营**：Anthropic Boris Cherny 原话 "我们每 3-4 周就把 harness 从头重写一次" / OpenAI 的 harness engineering 博客里 "harness" 一词只出现 1 次。

这是对 harness engineering 叙事最诚实的元观察：**叙事战争是商业利益博弈，不是纯技术问题**。

### 4.4 定义混乱派（概念不稳定）

- Harrison Chase 自己承认 "not super clear definition"
- Simon Willison 在 [HN 讨论](https://news.ycombinator.com/item?id=45429410) 里明确拒绝用 "agentic harness" 作为技能名
- HN "Ask HN: AI Agents vs. Gateways vs. Harnesses"（[47397737](https://news.ycombinator.com/item?id=47397737)）发帖人困惑："when I look at the available options, it's generally not clear to me which components I am getting"

### 4.5 资深工程师的冷静质疑

HN 讨论 Claude Managed Agents（[47699450](https://news.ycombinator.com/item?id=47699450)）：

> "We saw what Claude Code looks like inside, and it's objectively bad-to-mediocre work... The harness is kind of buggy. The LLM still wanders and cycles in it sometimes. It's a monolithic LLM herding machine." — steve_adams_86

连被鼓吹为范例的 Claude Code 本身的 harness 实现也**不像宣传的那样成熟**。

### 4.6 **伪批评**：Data Science Dojo

标题 ["Genuine Breakthrough or Rebranded Context Engineering?"](https://datasciencedojo.com/blog/harness-engineering/) 是 SEO clickbait，**正文完全没有讨论 rebrand 的可能性**，结论 100% 倒向 "Breakthrough"。这本身是术语营销化的一个样本。

---

## 5. 实证证据：硬数据 vs 软 claim 的比例

### 5.1 硬数据（benchmark/survey/ARR）

| 指标 | 具体数字 | 出处 |
|---|---|---|
| **Terminal-Bench 2.0 同模型跨 harness**（Opus 4.6） | Capy 75.3% → ForgeCode 81.8%，**6.5 pp** | [tbench.ai](https://www.tbench.ai/leaderboard/terminal-bench/2.0) |
| 同上（Gemini 3.1 Pro） | 5.4 pp | 同上 |
| 同上（GPT-5.3-Codex） | 3.3 pp | 同上 |
| SWE-bench Pro 同模型跨 harness（Opus 4.5） | SWE-Agent 45.89% vs Auggie 51.8%，**6 pp** | [Scale SWE-bench Pro](https://labs.scale.com/leaderboard/swe_bench_pro_public) |
| Blitzy harness vs 裸 GPT-5.4（SWE-bench Pro） | 66.5% vs 57.7%，**8.8 pp** | [dev.to](https://dev.to/teamquesma/compare-harnesses-not-models-blitzy-vs-gpt-54-on-swe-bench-pro-5d7) |
| Claude 4 Sonnet with advanced context management（SWE-bench） | 42.0% → 48.6%，**6.6 pp** | [arxiv 2512.10398](https://arxiv.org/html/2512.10398) |
| Stack Overflow 2025 agent 用户任务缩时率 | 70%；69% 报告产出提升 | [survey.stackoverflow.co/2025/ai](https://survey.stackoverflow.co/2025/ai) |
| AI 信任度 | 40% → 29%（下降） | 同上 |
| Cursor ARR / 估值 | $2B / $60B | [TechFundingNews](https://techfundingnews.com/anysphere-soars-to-29-3b-valuation-with-2-3b-funding-redefining-the-future-of-coding/) |
| Cognition Devin ARR | $1M (2024.09) → $73M (2025.06) | [cognition.ai](https://cognition.ai/blog/windsurf) |

### 5.2 软 claim（无对照组、N=1、访谈自述）

| 叙事 | 问题 |
|---|---|
| OpenAI Frontier "1M LOC / 5 个月 / 0% 人写代码" | **N=1 自我报告**。5 个月前 1.5 个月比手写慢 10 倍；所谓 "production" 是"内部 beta"不是真 production；"0% human review pre-merge" 有 post-merge review。"5x productivity" 没有计算方法。 |
| Anthropic "Effective harnesses for long-running agents" | **0 个 before/after 数字**。全文 qualitative。 |
| Anthropic SWE-bench "custom harness +10pp" | 厂商 marketing number，无独立复现 |
| Mitchell Hashimoto Ghostty | **完全没有硬数字**。原文亲口说 "我不知道是不是真的更快，大部分时间在 babysit agent" |
| Goldman Sachs Devin "3-4x" 生产力 | 新闻引用，无 GS 原始报告公开 |
| Claude Code rework 少 30%、token 少 5.5x | 第三方博客（Faros），来源不明 |

### 5.3 反面证据（同样值得严肃对待）

**Scale AI SWE-Atlas 研究**（经 [Latent Space AINews](https://www.latent.space/p/ainews-is-harness-engineering-real) 引用）认为 harness 间差距 **"essentially noise within margin of error"**。这是一个主流讨论里**刻意被忽略**的反声。

**Wharton GAIL** 研究：对推理模型用 CoT 提升仅 2.9-3.1%，却增加 20-80% 时间（[链接](https://gail.wharton.upenn.edu/research-and-insights/tech-report-chain-of-thought/)）——harness 做过头反而是负资产。

**Anthropic 自己的实证**：从 multi-agent 转回 **single-agent** Claude Code，在 [Building Effective Agents](https://www.anthropic.com/research/building-effective-agents) 明说 "the most successful implementations weren't using complex frameworks"。这是反对"harness 越复杂越好"的厂商自述。

### 5.4 结构性短缺

- **没有论文做 harness/model contribution decomposition**
- **没有 RCT-style 开发者产品对比**
- **没有 DORA/权威机构 harness 专题**
- Mitchell Hashimoto 本人"ghostty/ghostty2/ghostty3 并行跑不同 agent"是**唯一明确的受控对比方法**，但他**没有发布结果数字**

---

## 6. 演化脉络的 meta 判断

### 6.1 prompt → context → harness 的三阶段叙事是真的吗？

**叙事作者**：2026 Q1 由 Epsilla、OpenAI、Anthropic、Martin Fowler、Philipp Schmid、LangChain 同步输出，是**叙事共识**而非单一原创。

**每一跳的实质判断**：

| 跳跃 | 支持（质变） | 质疑（rebrand） | 判断 |
|---|---|---|---|
| prompt → context engineering | 4K→1M context window、server-side compaction API、memory file 外部化 | "RAG 2.0 换皮"（[The New Stack](https://thenewstack.io/rag-isnt-dead-but-context-engineering-is-the-new-hotness/)）；Hacker News 批评为 hype | **质变 60% / rebrand 40%** |
| context → harness engineering | Tool permission pipeline（deny-first）、multi-session state、verification loop、十亿 token/天规模 | 2023 BabyAGI 就有 "loop + memory + tool"；核心架构高度重叠；swyx "Is harness engineering real?" 自省 | **质变 70% / rebrand 30%** |

### 6.2 为什么需要新词（即便组件重叠）

三个工程属性的跃迁让老词 "scaffold" 扛不起新 scope：

1. **规模级跃迁**：2023 scaffold 是 PoC（最多几分钟几十步），2026 harness 是生产（数小时、数千 session、十亿 token/天）。"scaffold" 的 PoC 味太重。

2. **治理层（Governance）是 scaffold 时代完全没有的**：tool permission pipeline、sandbox 三档模式、verification middleware、CI-enforced linters。scaffold 是"能跑"，harness 是"能安全可靠地跑、跑错了能自纠"。

3. **Multi-session & persistence 是主流用例**：2023 AutoGPT 设计为单次目标；Claude Code 设计为持续数周的跨 session 开发伙伴。

**这和 "DevOps 只是系统管理员新名字"的争论同构**——技术组件高度重叠，但工程文化、治理 scope、典型用例已经不一样了。

---

## 7. 交叉验证：一致发现 vs 互斥矛盾

### 7.1 五个 agent 都独立印证的发现（高可信度）

1. **起源时间线** — Hashimoto 2026-02-05 命名是多方独立证实的 tipping point
2. **"Agent = Model + Harness" 公式** — LangChain/Fowler/Raschka/Anthropic 统一使用
3. **权威自己承认定义过宽** — Fowler/Trivedy/Chase 都明说
4. **硬数据严重不足** — 无论哪个角度查，都找不到 decomposition 研究
5. **三阶段叙事存在，但是"连续演化打了三个标签"** — 不是三次断层飞跃

### 7.2 硬矛盾（单一来源，需要标注）

| 矛盾点 | A 方 | B 方 |
|---|---|---|
| 层次关系 | harness = runtime（Salesforce） | framework/runtime/harness 三者分立（Chase） |
| harness ↔ context engineering | harness ⊂ CE（HumanLayer） | CE ⊂ harness（Data Science Dojo, Bouchard） |
| Benchmark 差距意义 | 3-10pp 可测差距（Terminal-Bench, SWE-bench Pro） | "noise within margin of error"（Scale SWE-Atlas） |
| 新旧比例 | 90% 旧 + 10% 新（Kokane） | 70% 旧 + 30% 新（维度2），70% 质变 + 30% rebrand（维度4） |

### 7.3 单点重要发现（需要验证）

- ⚠️ **Harrison Chase 原文 `blog.langchain.com/agent-frameworks-runtimes-and-harnesses-oh-my/` 返回 404**——核心术语分层定义的原始出处已失效
- **Latent.Space 的"Big Model vs Big Harness 商业博弈"视角**是独家观察
- **Anthropic Boris Cherny "每 3-4 周把 harness 从头重写一次"** 只在 Latent.Space 转述中出现
- **Epsilla 自己发反向文章 "Why Anthropic is Telling Us to Delete Our Agent Harnesses"**——当模型变强，刚性 harness 变负资产

---

## 8. 最终判断

### 8.1 是真升级还是文字游戏？

**两者都是，且不矛盾。**

**真升级的部分**：
- 4 个 2025-2026 才成熟的技术原语（Skills progressive disclosure、Lifecycle hooks、Auto-compaction、Harness-model co-training）
- 治理层（permission pipeline、sandbox 分级、verification loop）是 scaffold 时代完全没有的
- 用例规模级跃迁（十亿 token/天、多 session 连续数周）
- Terminal-Bench 2.0 上可复现的 3-7pp 跨 harness 差距

**文字游戏的部分**：
- 70-90% 的组件是 2023-2024 年的老东西（system prompt + tool loop + memory + subagent + sandbox）
- "context engineering ⊂/⊃/= harness engineering" 三种互斥定义并存——术语定义不稳定
- "5x productivity"、"1M LOC 零人类代码" 这类叙事**没有可复现的 ablation**
- Epsilla 自己讽刺 "hyperinflation"，Fowler 自己调侃"再过不久会有人把单 prompt 当 harness"
- Latent.Space 承认这是 Big Model vs Big Harness 商业博弈

### 8.2 给做 Agent Ops / SRE agent 的人的判断

瑞哥你在做 context-infrastructure 和 SRE agent，harness engineering 对你的意义不是"要不要追这个术语"，而是**三件具体的事**：

1. **Hooks + tool permission pipeline 是真基础设施**——这是 SRE agent 唯一真正能落地 governance 的地方。你的 K8s 操作 `INTENT:` 约定、mutating op 后的 verification 步骤，本质就是 Fowler 所说的 "Guides + Sensors + steering loop"。把它写到 skills 里，就是 harness 真正有价值的部分。

2. **闭源 harness 的 memory lock-in 风险是真的**。LangChain 已公开批评 Claude Agent SDK "closed harness = 你不拥有自己的 memory"。如果你做 Agent Ops 控制平面，**memory 和 hooks 层是主战场**，不能把它交给 vendor 的黑盒。AGENTS.md / CLAUDE.md 这种 markdown harness 是你保持 vendor-neutrality 的护城河。

3. **harness 的价值随模型能力反比递减**——Boris Cherny "每 3-4 周把 harness 从头重写"的原话和 Anthropic 回归 single-agent 的实证都指向这个。对你的 SRE agent 成立：**今天需要的大量 guard/sensor，下代模型可能就不需要了**。所以 harness 不是一次性基础设施，是**持续 refactor 的手艺**——别过度设计。

### 8.3 一个可落地的认知锚点

**只看三类东西判断 harness 是真升级还是营销话术**：
1. **看 API**（Anthropic `clear_tool_uses_20250919` compaction block、Claude Code hooks 12+ events 这种是真 feature）
2. **看 benchmark delta**（Terminal-Bench 2.0 同模型跨 harness 3-7pp 是硬证据）
3. **看 token 规模**（十亿 token/天的用例在 prompt engineering 时代不存在）

**别看**：manifesto、口号、"第三代 AI 工程技能"这类定性叙事——那些 100% 是社交传播产物。

---

## 附录 A：关键 URL 一览

**核心提出者原文**
- Mitchell Hashimoto: https://mitchellh.com/writing/my-ai-adoption-journey
- LangChain Trivedy: https://blog.langchain.com/the-anatomy-of-an-agent-harness/
- OpenAI: https://openai.com/index/harness-engineering/
- Martin Fowler/Böckeler: https://martinfowler.com/articles/harness-engineering.html
- Fowler memo: https://martinfowler.com/articles/exploring-gen-ai/harness-engineering-memo.html
- Sebastian Raschka: https://magazine.sebastianraschka.com/p/components-of-a-coding-agent
- Anthropic evals: https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents
- Anthropic Claude Agent SDK: https://anthropic.com/engineering/building-agents-with-the-claude-agent-sdk
- Anthropic Managed Agents: https://anthropic.com/engineering/managed-agents
- Harrison Chase (Sequoia): https://www.sequoiacap.com/podcast/context-engineering-our-way-to-long-horizon-agents-langchains-harrison-chase/
- ⚠️ Harrison Chase 原帖 **404**: blog.langchain.com/agent-frameworks-runtimes-and-harnesses-oh-my/
- Salesforce: https://www.salesforce.com/agentforce/ai-agents/agent-harness/
- Andrew Maynard 学术追溯: https://andrewmaynard.net/papers/Rapid_Adoption_Harness_Metaphor_AI_V1.pdf

**批评声音**
- Akshay Kokane "90% 旧 10% 新": https://levelup.gitconnected.com/agent-harness-is-just-system-design-with-a-new-name-d91be4a648c5
- Serge Liatko (OpenAI community): https://community.openai.com/t/prompt-engineering-is-dead-and-context-engineering-is-already-obsolete-why-the-future-is-automated-workflow-architecture-with-llms/1314011
- Epsilla "Beyond the Harness": https://www.epsilla.com/blogs/the-end-of-harness-engineering-enterprise-environment-agents
- bits-bytes-nn: https://bits-bytes-nn.github.io/insights/agentic-ai/2026/04/05/evolution-of-ai-agentic-patterns-en.html
- HumanLayer "Skill Issue": https://www.humanlayer.dev/blog/skill-issue-harness-engineering-for-coding-agents
- Latent.Space "Is Harness Engineering real?": https://www.latent.space/p/ainews-is-harness-engineering-real
- HN Simon Willison 讨论: https://news.ycombinator.com/item?id=45429410
- HN 困惑发帖: https://news.ycombinator.com/item?id=47397737
- HN "Claude Code is bad-to-mediocre": https://news.ycombinator.com/item?id=47699450

**实证证据**
- Latent Space Lopopolo (1M LOC): https://www.latent.space/p/harness-eng
- Terminal-Bench 2.0: https://www.tbench.ai/leaderboard/terminal-bench/2.0
- Scale SWE-bench Pro: https://labs.scale.com/leaderboard/swe_bench_pro_public
- Stack Overflow 2025: https://survey.stackoverflow.co/2025/ai
- Anthropic SWE-bench: https://www.anthropic.com/research/swe-bench-sonnet
- Anthropic Building Effective Agents: https://www.anthropic.com/research/building-effective-agents
- SWE-bench context management paper: https://arxiv.org/html/2512.10398
- Wharton GAIL (CoT 成本): https://gail.wharton.upenn.edu/research-and-insights/tech-report-chain-of-thought/
- Blitzy vs GPT-5.4: https://dev.to/teamquesma/compare-harnesses-not-models-blitzy-vs-gpt-54-on-swe-bench-pro-5d7

**演化脉络**
- Karpathy context engineering 推文: https://x.com/karpathy/status/1937902205765607626
- Simon Willison context engineering: https://simonwillison.net/2025/jun/27/context-engineering/
- Anthropic effective context engineering: https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents
- BabyAGI: https://github.com/yoheinakajima/babyagi
- beren.io Scaffolded LLMs (2023): https://beren.io/2023-04-11-Scaffolded-LLMs-natural-language-computers/
- The New Stack "RAG isn't dead": https://thenewstack.io/rag-isnt-dead-but-context-engineering-is-the-new-hotness/

---

## 附录 B：证据缺口（诚实交代）

1. **Tobi Lütke 原始推文 URL 未定位到**（2025-06-19 context engineering 起源）；目前经 Willison 转述作为二级来源。
2. **Harrison Chase 原 framework/runtime/harness 帖已 404**，定义只能经 Sequoia 播客、VentureBeat、LinkedIn 还原。
3. **没有任何公开论文做 harness/model contribution decomposition**——这是整个领域最大的实证缺口。
4. **没有 RCT-style 开发者产品对比**——Cursor vs Claude Code 的所有对比都是 anecdotal。
5. **DORA 2026 未返回 harness 专题结果**——可能未出或未索引。
6. **Scale AI SWE-Atlas 原报告未定位到**——只经 Latent.Space AINews 转述；"essentially noise within margin of error" 这句关键引用需要进一步验证原始出处。

---

**报告完成 2026-04-17。所有引用 URL 在本文内。**
