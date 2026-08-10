# gstack 设计哲学深度调研

> 调研时间：2026-05-27
> 调研范围：gstack 架构与实现 / 设计哲学 / Karpathy 思想关联 / Claude Code harness 与 Skill 系统
> 调研方法：4 个并行 sub-agent，维度间有 ≥50% overlap 用于交叉验证
> 输出层级：**TL;DR → 三大思想脉络 → 分维度深入 → 交叉验证与矛盾 → 给瑞哥的迁移建议**

---

## TL;DR（120 秒读完）

1. **gstack 是什么**：Garry Tan（YC CEO）的 23 个 Claude Code skill 套件。每个 skill 是 `~/.claude/skills/gstack/<name>/SKILL.md`，把 Claude 切换到一个"角色 + 约束 + 输出"组合（CEO / Eng Manager / Designer / QA / Security / Release / Doc / Retro）。
2. **核心赌注**：**结构化角色 + 流程顺序 > 单个全能 prompt**。Pulumi blog 的最干净 framing："gstack 约束的是 *decision-making authority*；engineer role 看不到 product roadmap，QA role 看不到 implementation details。"
3. **与 Karpathy 思想的关系**：gstack 显式实现 Karpathy 2026-01-26 推文里的 **3 条 AI coding 失败模式**（wrong assumptions / overcomplexity / orthogonal edits），加上社区衍生的第 4 条 imperative→declarative。**"四大失败模式"是社区 framing，Karpathy 原帖只有 3 条**——重要纠偏。
4. **与 Claude Code harness 的关系**：gstack 完全跑在 Anthropic 官方 Skill 系统的 progressive disclosure 机制上（metadata → SKILL.md body → referenced files），不发明新协议。`/browse` 是少数例外——绕过 MCP，直接 localhost daemon + Bun binary 实现 100ms 响应。
5. **设计哲学的两个面**：
   - **正面**：把"sprint as org chart"工程化，解决 wrong assumptions / scope drift / context rot
   - **反面**：23 是 emergent 不是 axiom（演化轨迹 6→13→23/28）；"process over prompts" 不是 Tan 写的口号，是社区 reverse-engineer；10K LOC/week 全部 self-reported，critic 已用 commit 级数据反驳
6. **给瑞哥的迁移启示**（见末尾）：你的 `rules/skills/` 已经有同形结构，但比 gstack 更克制；缺的不是 skill 数量，是 **handoff 文件 + 跨 session 状态持久化**（gstack 的 `~/.gstack/projects/{slug}/{branch}-ship-state.yaml` 模式）。

---

## 三大思想脉络的关系（一张图）

```
       Karpathy（哲学家）             Anthropic（平台方）              gstack（应用层）
       ───────────────              ──────────────────              ─────────────────
       Software 3.0       ────►    Skills 系统               ────►  23 个 role skill
       English = program          (progressive disclosure)         (each = persona)

       4 failure modes    ────►    Harness 设计原则            ────►  /office-hours
       (wrong assumption,         (context engineering,             治 wrong assumptions
        overcomplexity,            sub-agent isolation,             /review 治 overcomplexity
        orthogonal edits,          context resets,                  /investigate Iron Law
        imperative→declarative)    code execution > MCP)            治 orthogonal edits

       Context engineering ────►   /v1/skills, SKILL.md       ────►  preamble-tier
       > prompt engineering       3-level loading                   YAML frontmatter

       Autonomy slider     ────►   per-model harness tuning   ────►  /careful, /freeze
                                                                     scope declaration
```

**核心一致点**：三者都把 **"context window 是稀缺资源"** 当作设计起点。Karpathy 提供哲学（"context engineering"），Anthropic 提供机制（progressive disclosure），gstack 提供 workflow（role-based handoff）。

**核心张力**：
- Karpathy 倾向**"autonomy slider 向中间"**（autocomplete > full agent），因为他亲手写 nanochat 时 agent 拖后腿
- gstack 倾向**"autonomy slider 偏右 + 边界约束"**，用 scope declaration 换自主度
- Anthropic 官方在 2025-2026 间倾向 gstack 一侧（Claude Agent SDK = "给 agent 一台电脑"）

---

## 维度 A：gstack 架构与实现机制

### A.1 Repo 物理结构

顶层每个 skill 是独立目录（[repo root](https://github.com/garrytan/gstack)）：

```
/office-hours    /qa            /review         /browse
/investigate     /ship          /plan-ceo-review /plan-eng-review
/plan-design-review /design-shotgun /design-html /design-consultation
/design-review   /cso           /canary         /retro
/learn           /codex         /careful        /freeze
/guard           /unfreeze      /land-and-deploy ...
```

文档层：`CLAUDE.md` / `ARCHITECTURE.md` / `ETHOS.md` / `DESIGN.md` / [`docs/skills.md`](https://raw.githubusercontent.com/garrytan/gstack/main/docs/skills.md)。

**Per-skill 两种形态**：
- **纯 prompt 类**（如 `office-hours`）：只有 `SKILL.md` + `SKILL.md.tmpl`
- **代码后端类**（如 `browse`）：`SKILL.md` + `SKILL.md.tmpl` + `bin/` + `src/` + `scripts/` + `test/`

**SKILL.md.tmpl** 用 `{{PREAMBLE}}` / `{{BROWSE_SETUP}}` / `{{SNAPSHOT_FLAGS}}` 等占位符，build 时 substitution——DRY 共享 preamble。

### A.2 YAML Frontmatter 规范

```yaml
name: browse
preamble-tier: 1            # 1 = 高优先级被自动加载到 system prompt; 4 = 仅显式触发
version: 1.1.0
description: Fast headless browser for QA testing and site dogfooding. (gstack)
triggers:
  - browse a page
  - headless browser
  - take page screenshot
allowed-tools:
  - Bash
  - Read
  - AskUserQuestion
```

`preamble-tier` 是 gstack 自创的字段（不是 Anthropic 官方 SKILL.md 字段），用来控制加载激进度。`triggers` 是自然语言短语，给 Claude 自动 invoke 决策用。

### A.3 `/browse` —— 架构上最值得抄的设计

这是整个 gstack 唯一**绕过 MCP 协议**的 skill。关键事实（来自 [ARCHITECTURE.md](https://raw.githubusercontent.com/garrytan/gstack/main/ARCHITECTURE.md)）：

| 维度 | gstack `/browse` | Chrome DevTools MCP / Playwright MCP |
|---|---|---|
| Chromium 生命周期 | 长驻 daemon，首次 ~3s，后续 100ms | 每次调用 spawn/attach |
| 通信路径 | CLI → localhost HTTP (random port 10000-60000) → Chromium | LLM → MCP server → CDP |
| Tool schema 占用 | 0 token（就是 shell 命令） | 大 MCP schema dump 进 system prompt |
| State 持久化 | `.gstack/browse.json`（PID + port + bearer token, mode 0o600） | 各家 MCP 自管 |
| 元素引用 | `@e1` `@e2` 映射到 **Playwright Locator**（accessibility role+name），抗 CSP / 抗 hydration | 多为 DOM selector |
| 部署 | `bun build --compile` 出 ~58MB 单文件 binary，无 runtime 依赖 | 需要 Node + MCP server |

**为什么这设计重要**：Anthropic 在 [Code execution with MCP](https://www.anthropic.com/engineering/code-execution-with-mcp) 自己承认 5 server / 58 tool 的 MCP 配置开局就吃掉 ~55,000 tokens（150K → 2K 优化案例）。`/browse` 直接走 shell 命令，把这部分 tax 降到 0。

### A.4 State sharing 是**文件 + prompt chain 的混合**

不是纯 prompt chain。durable 状态走文件，session 内编排走 prompt。

- **项目级状态目录**：`~/.gstack/projects/{slug}/`
- **分支级 handoff YAML**（`/ship` 写，`/land-and-deploy` 读）：

```yaml
ship_completed: true
version_bumped: "1.2.3"
changelog_generated: true
commits_created: N
branch: feature-branch
base_branch: main
pr_url: https://github.com/owner/repo/pull/123
tests_run: true
coverage_pct: 82
plan_items_done: 12/14
```

- **Review log**（`/review` 写，`/ship` 读做 gate 校验）
- **QA reports** `.gstack/qa-reports/` 含 baseline JSON 做 regression 对比
- **`/learn`** 累积跨 session 的 pattern/pitfall/tool/operational tag
- **`/context-save` / `/context-restore`** 显式 snapshot git 状态 + 决策 + remaining work

### A.5 多 host 支持

`./setup --host <name>` 自动检测：

| Host | 安装路径 |
|---|---|
| Claude Code (default) | `~/.claude/skills/gstack` |
| OpenAI Codex CLI | `~/.codex/skills/gstack-*/` |
| OpenCode | `~/.config/opencode/skills/gstack-*/` |
| Cursor | `~/.cursor/skills/gstack-*/` |
| Factory Droid / Slate / Kiro / Hermes / GBrain | 各自 `~/.<host>/skills/gstack-*/` |

**Prompt-only skill 完全可移植**；binary-backed（`/browse`、`/qa`）需要目标 host 能跑 shell。

### A.6 几个值得抄的 skill 设计

- **`/office-hours`**: Six Forcing Questions + 反讨好规则（"Never say 'interesting approach' or 'many ways to think'; take positions. Quote user words back to them"）+ Builder profile tracking（session 4+ 切换 framing）
- **`/investigate`**: **Iron Law**: "no fixes without root cause investigation first"；**3-strike rule** 后强制 escalate；**Scope Lock**: 假设根因后限制编辑范围到 affected dir，>5 file edits 要 user confirm
- **`/review`**: 6 阶段含 **Specialist Dispatch** —— ≥50 行 diff 自动并行派 subagent（Testing/Maintainability/Security/Performance/Data Migration/API Contract/Design），每个返回 `{severity, confidence, file:line}`；**Confidence Calibration Gate**: finding 必须 quote 具体代码行，否则 confidence 被压到 4-5
- **`/qa`**: 11 阶段，**WTF-likelihood heuristic** 5 reverts 或 50 fixes 后强制停

---

## 维度 B：gstack 设计哲学与对比

### B.1 "Roles beat prompts" —— 真正的论点

[Pulumi blog](https://www.pulumi.com/blog/claude-code-orchestration-frameworks/) 给的最干净 framing：

> **gstack 约束的是 "decision-making authority"。The engineer role does not see the product roadmap. The QA role does not see the implementation details.**

这是 **role isolation**，不是简单多 hat。每个 role 都被人为剥夺一部分 context，强制专注。

[mager.co](https://www.mager.co/blog/2026-03-28-gstack-garry-tan-claude-plugin/) 的总结：**"Planning is not review. Review is not shipping. He wanted explicit gears."**

### B.2 "Process over prompts" 的真实出处

**没有一条 Tan 原文 tweet 直接说 "process over prompts"**。这个 framing 是分析者（Augment Code、mager.co、SitePoint）reverse-engineer 出来的。最接近的一手 Tan 言论：

- [Tan tweet](https://x.com/garrytan/status/2020072098635665909): *"I use a very specific prompt to push Claude to check its work and do a lot of testing and thinking about perf and refactoring. I find I can do big features (4K LOC+ with full testing) in about an hour."*
- [Tan tweet](https://x.com/garrytan/status/2015540619855425959): *"I don't know why this isn't just in Claude Code's system prompt"* —— 暗示他认为这套 process 该是 default

**这是一个被广泛传播但没有 manifesto 锚定的口号**。当你听到"process over prompts"，要记住它是社区给 gstack 的 artifact 写的 caption，不是 Tan 的纲领。

### B.3 三框架对比（Superpowers / gstack / GSD）

[Pulumi blog](https://www.pulumi.com/blog/claude-code-orchestration-frameworks/) 给的最干净矩阵：

| Framework | 维护者 | **约束什么层** | 解决的失败模式 |
|---|---|---|---|
| [**Superpowers**](https://github.com/obra/superpowers) | Jesse Vincent (obra) | **动作层**：mandatory TDD + 7-phase workflow with gates | "Code breaks tomorrow" —— 没测试纪律，plausible code 静默崩坏 |
| [**gstack**](https://github.com/garrytan/gstack) | Garry Tan | **身份层**：23 个 role 之间的 isolation + handoff | "Shipping unwanted features" —— scope drift |
| [**GSD**](https://github.com/gsd-build/get-shit-done) | TÂCHES | **记忆层**：每个 phase 一个 fresh orchestrator，<50% context | "Quality degrades over time" —— context rot |

[dev.to/imaginex](https://dev.to/imaginex/a-claude-code-skills-stack-how-to-combine-superpowers-gstack-and-gsd-without-the-chaos-44b3) 的另一层 framing：
- **gstack 管 thinking**（要不要做、做什么）
- **Superpowers 管 doing**（怎么做，TDD 循环）
- **GSD 管 long context**（多 session 不漂移）

三者**互补不竞争**。理论组合：gstack 起步 stress-test 需求 → GSD 跨 session 锚定 spec → Superpowers 稳态执行 TDD。

### B.4 23 这个数字是 emergent 的，不是先验设计

**演化轨迹**：launch 时 6 → TechCrunch 报道时 13 → 2026-05 时 23（部分文章引 28）。

这意味着 Tan **没有一个先验的"必须 N 个"论证**。这削弱了"23 不多不少正合适"的论证强度——它更像 founder mode 持续 ship 自然涨出来的。

### B.5 Shipping cadence 数字的可信度

| 数字 | 出处 | 可信度 |
|---|---|---|
| 10K LOC/week, 100 PRs/week, 50 天 | gstack README + 多家报道 | self-reported |
| 升级到 10-15K LOC/**day** | [Tan tweet](https://x.com/garrytan/status/2018368316033946021) | self-reported |
| 37,000 lines/day across 5 projects, 72-day streak | Fast Company 报道 | self-reported |

**Critic 的具体反驳**：
- **Gregorein**（资深 game dev）拆了 Tan 的 commit：平均每 commit 2K lines added / 450 removed。核心质疑：*"AI lets you generate code faster than any human can review it, and the answer from people like Garry seems to be 'so stop reviewing.'"*
- TechCrunch 引匿名 founder：*"Garry should be embarrassed for tweeting this. If it's true, that CTO should be fired."*
- HN user **zippolyon** 真实事故：agent 在 70 分钟循环里"repeatedly injecting a staging URL into a production config file"还报 success exit code
- [andrew.ooo](https://andrew.ooo/posts/gstack-garry-tan-claude-code-setup/): *"10K LOC/day is a red flag, not a feature"*

**结论**：LOC 数字全是 self-reported，没第三方审计。把它当 marketing 数字读，不要当工作流截面。

### B.6 主要批评 (6 轴)

1. **"Just a bunch of prompts"**（[GitHub issue #1088](https://github.com/garrytan/gstack/issues/1088)、Mo Bitar）—— 没跑任何 novel infra，每个 skill 就是 markdown
2. **Token bloat / overengineering**（r/ClaudeCode）—— "bloated and token-hungry when fully enabled"；单个 execution skill 写代码前消耗 10K+ tokens
3. **Celebrity bias**（Sherveen Mashayekhi, andrew.ooo）—— *"if you weren't the CEO of YC, this wouldn't be on PH"*
4. **Layer 1 vs Layer 3 critique**（[Medium Rentier](https://medium.com/@rentierdigital/y-combinators-ceo-shared-his-claude-code-prompt-it-solves-the-wrong-problem-c1d0c7a245c3)）—— Tan 方案是 post-hoc review (Layer 1)，真正的 leverage 在 Layer 3 (intent specification / prompt contracts)。引言：*"Last week I spent more time approving Claude's suggestions than actually building. Four review stages. Twelve issues flagged. Thirty minutes of 'yes, option B, proceed' before a single line of production code changed."*
5. **多 repo 不扩展**（HN dmppch）—— git-clone-and-copy 模型在 monorepo / 多 repo 不同 review gate 场景 buckle
6. **Autonomy + 多 persona handoff 放大事故 blast radius**（zippolyon 70-min loop incident）

### B.7 Garry Tan 个人背景如何渗透到 gstack 形状

- **YC 训练 → `/office-hours`**：Six Forcing Questions 是 YC partner 给 founder 做 office hours 的 ritual 直接编码
- **Designer-engineer 双身份 → `/plan-design-review`, `/design-shotgun`, `/design-html`**：一般工程师写的 framework 不会把"designer 治 AI slop"作为 first-class concern
- **VC 视角 → "should we build this" 提到 "how do we build this" 之前**：founder/investor 本能思维
- **Sprint-as-org-chart 抽象**：把开发周期想成 mini-startup 是 YC 看了 5000 家公司后的 default mental model

**这也解释了"love and hate"的人群分化**：对常年思考 startup org design 的人，gstack 自然；对 solo IC，是 overhead。

---

## 维度 C：Karpathy 思想关联

### C.1 Software 3.0 与 LLM 当 OS

[Karpathy YC AI Startup School 演讲（2025-06-17）](https://www.ycombinator.com/library/MW-andrej-karpathy-software-is-changing-again):

> **"Software 1.0 is the code you write. Software 2.0 are the weights of a neural network... Software 3.0... the prompts are now programs. And remarkably, these prompts are written in English."**

类比：**context window = RAM，LLM = CPU，prompt = program**。"English is the hottest new programming language."

**与 gstack 的对应**：每个 SKILL.md 就是一个"Software 3.0 程序"。`bestpractice_agent_harness_architecture` 类的 skill 是把 LLM 当 CPU 外面包 OS-like harness 的工程化实例。

### C.2 ⚠️ AI Coding 四大失败模式 —— 重要纠偏

**媒体常称"四大"，但 [Karpathy 2026-01-26 X post](https://github.com/multica-ai/andrej-karpathy-skills) 原帖明确列了 3 条。第四条 imperative→declarative 是 Forrest Chang 在 CLAUDE.md 里从 Karpathy 推文衍生的"Goal-Driven Execution"，不是 Karpathy 原话。**

| # | Karpathy 原话 | 反例 | gstack 实现 |
|---|---|---|---|
| 1 | **Wrong Assumptions**: "make wrong assumptions on your behalf and just run along with them without checking, not managing their confusion, not seeking clarifications, not surfacing inconsistencies, and not pushing back when they should" | 用户说 fix auth bug，agent 脑补 JWT 过期就改 token expiry，真因是 cookie SameSite | `/office-hours` Six Forcing Questions, `/investigate` Iron Law, `bestpractice_ai_debugging_diagnosis` 第一问 |
| 2 | **Overcomplexity**: "overcomplicate code and APIs, bloat abstractions, don't clean up dead code, and implement a bloated construction over 1000 lines when 100 would do" | 让 agent 加 retry → RetryStrategyFactory + ExponentialBackoffPolicyBuilder + CircuitBreakerInterceptor | `/review`, `bestpractice_ai_programming_mindset` 的 axiom T05 "认知是资产，代码是消耗品" |
| 3 | **Orthogonal Edits**: "change or remove comments in code that they don't like or don't sufficiently understand as side effects... even if it is orthogonal to the task at hand" | 你让加 CSV 参数，它顺手删了 `# TODO: handle BOM` 注释 | `/investigate` Scope Lock, `workflow_autonomous_execution` Scope Declaration, `bestpractice_staged_approach` Dry Run |
| 4 ⚠️ | **(社区衍生)** Imperative → Declarative: "LLMs are exceptionally good at looping until they meet specific goals" → 不给命令式步骤，给 acceptance criteria + 可验证回路 | "fix this bug" → "write a failing test that reproduces the bug, modify code until the test passes" | `bestpractice_agentic_control_primitives` (Spec/Loop/Hook/Fork), `bestpractice_agent_reliability_engineering` |

### C.3 Context engineering > prompt engineering

[Karpathy X, 2025-06-25](https://x.com/karpathy/status/1937902205765607626):

> **"+1 for 'context engineering' over 'prompt engineering'. People associate prompts with short task descriptions you'd give an LLM in your day-to-day use. When in every industrial-strength LLM app, context engineering is the delicate art and science of filling the context window with just the right information for the next step."**

为什么 context 比 prompt 重要：
- Prompt = 单步指令；context = 整个 working set
- Context window 是稀缺资源（≈ LLM OS 的 RAM）
- 太少 → 模型胡编；太多 → 注意力稀释、context rot
- Context engineering 是**系统设计问题**：检索、压缩、淘汰、隔离、re-hydration

### C.4 Vibe coding / Agentic coding 的态度演变（反复多次）

| 时间 | 立场 | 来源 |
|---|---|---|
| 2025-02-02 | 提出 "vibe coding"，"fully give in to the vibes" | [X tweet 1886192184808149383](https://x.com/karpathy/status/1886192184808149383) |
| 2025-06-17 | YC 演讲："decade of agents"，强调 autonomy slider | YC AI Startup School |
| 2025-10 | 写 nanochat 时基本不用 agent ——"intellectually intense code, out-of-distribution" | [Dwarkesh interview](https://www.dwarkesh.com/p/andrej-karpathy) |
| 2025-10 (Dwarkesh) | **反向修正**："decade of agents, not year of agents" | 同上 |
| 2026-01-26 | **再反向**：转到 80% agent-driven coding，并列出 3 大失败模式 | X post → [CLAUDE.md](https://github.com/multica-ai/andrej-karpathy-skills) |
| 2026-01 后 | "mostly codes in English" | [The Decoder](https://the-decoder.com/former-tesla-ai-chief-andrej-karpathy-now-codes-mostly-in-english-just-three-months-after-calling-ai-agents-useless/) |

**核心立场**：不是非黑即白。Agent 对 boilerplate / 高频代码非常好用；对独特、精确编排的代码（如 nanochat）人类亲手写更快。**"Autonomy slider"是关键设计思想——让人决定哪一档自主度。**

### C.5 Karpathy 工作流 vs gstack 工作流 关键差异

| 维度 | Karpathy | gstack | 差异 |
|---|---|---|---|
| 自主度 | "Autonomy slider" 倾向中等档 | `workflow_autonomous_execution` 默认较高档 + scope declaration | gstack 更激进；用 scope 边界换自主度 |
| Plan 形态 | CLAUDE.md：write a brief plan before code | 持久化到 `tmp/plan-*.md`，明确 Phase 1/2/3 | gstack 更结构化，引入"对话外持久化"应对 context 蒸发 |
| Verification | "test that reproduces the bug becomes the closing criterion" | 多一层 SRE 框架（SLI/SLO/eval），`bestpractice_agent_reliability_engineering` | gstack 工程化更彻底 |
| Context | Context engineering 是 "art" | 把 context 当 K8s 资源：scope / fork isolation / plan re-hydration | gstack 把 art 做成 process |
| Boilerplate vs novel | agent 做 boilerplate，自己写 novel | Opus 工作模式："设计 + 写作 + 质量把关自己做，调研 / 脚本 / 检索 delegate" | **高度一致** |

---

## 维度 D：Claude Code harness / Skill 系统

### D.1 "Harness" —— Anthropic 的核心架构论点

Anthropic 把 "harness" 当 first-class 工程概念。[Claude Agent SDK 发布博客](https://claude.com/blog/building-agents-with-the-claude-agent-sdk)（2026-01-28，从 Claude Code SDK 改名）：

> **"The Claude Agent SDK... functions as an 'agent harness'... The key design principle is to give your agents a computer, allowing them to work like humans do."**

**Agent tool loop**：`gather context → take action → verify work → repeat`。

[2026-04 post-mortem](https://www.anthropic.com/engineering/april-23-postmortem) 明确：**"each model behaves slightly differently, and Anthropic spends time before each release optimizing the harness and product for it"** —— harness 是 per-model 工程产物，不是一次性投资。

### D.2 Context engineering 四策略

[Effective context engineering for AI agents（2025-09）](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents):

> **"Context must be treated as a finite resource with diminishing marginal returns."**
> **"Find the smallest possible set of high-signal tokens that maximize the likelihood of some desired outcome."**

四个命名策略：
1. **Compaction**：context 满了 summarize 历史
2. **Structured note-taking**：状态持久化到 context 之外
3. **Just-in-time retrieval**：按需通过轻量 identifier 加载
4. **Sub-agent architectures**：专业化 agent + 干净 context + 浓缩 summary 返回

### D.3 Long-running harness：context resets > compaction

[Harness design for long-running apps（2026-03）](https://www.anthropic.com/engineering/harness-design-long-running-apps):

> **"Compaction... doesn't give the agent a clean slate, which means context anxiety can still persist."**
> **"Claude Sonnet 4.5 exhibited context anxiety strongly enough that compaction alone wasn't sufficient."**

[Effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents) 引入 **`claude-progress.txt`** pattern（结构化 handoff 文件，让 fresh-context agent 快速 grok 项目状态）+ **Planner / Generator / Evaluator** 三 agent 分离：

> **"When agents self-evaluate, they tend to respond by confidently praising the work — even when, to a human observer, the quality is obviously mediocre."**

### D.4 Skills 系统（2025-10-16 上线）

[Equipping agents for the real world with Agent Skills](https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills) + [Introducing Agent Skills](https://claude.com/blog/skills):

**SKILL.md spec**：YAML frontmatter 必含 `name` + `description`。启动时**只有** name+description 进 system prompt——full content 不进。

**Progressive Disclosure 3 级**：
1. **Metadata** (name + description) —— 永远加载
2. **Full SKILL.md body** —— Claude 判断相关时 Read 进来
3. **Referenced files**（forms.md, reference.md, scripts/）—— 进一步需要时 Bash/Read 加载

> **"Like a well-organized manual that starts with a table of contents, then specific chapters, and finally a detailed appendix."**
> **"The amount of context that can be bundled into a skill is effectively unbounded."**

**Model autonomy**：Claude 自己判断 skill 相关性（读 metadata），用 Bash/Read 触发加载。**没有 router，没有 orchestrator，没有必须的 slash command**。

### D.5 Skills vs MCP vs Subagents vs Prompts vs Projects

[Skills explained](https://claude.com/blog/skills-explained):

| | 角色 |
|---|---|
| **Prompts** | "Ephemeral, conversational, and reactive." 反复输入 → 转 Skill |
| **Projects** | 静态参考。"Projects say 'here's what you need to know.'" |
| **Skills** | 程序化、可执行。"Skills say 'here's how to do things.'" |
| **MCP** | 外部系统连接 |
| **Subagents** | 独立 agent，隔离 context + tool permission |

> **"MCP for connectivity, Skills for procedural knowledge."**

**Skills × Subagents** 是互补：subagent 可以 leverage skill 做专业化，同时保持 context 独立。

### D.6 MCP context bloat 与 code execution 解法

[Code execution with MCP](https://www.anthropic.com/engineering/code-execution-with-mcp):

> **"Tool definitions occupy more context window space, increasing response time and costs."**

具体：典型 5 server / 58 tool MCP 开局吃掉 **~55,000 tokens**。Anthropic 建议的解法是把 MCP server 当 **code-API filesystem** 让 agent 按需探索：**"From 150,000 tokens to 2,000 tokens — a time and cost saving of 98.7%."**

这是 progressive disclosure 在 MCP 维度的应用——和 Skills 是同一个设计原则。

### D.7 gstack 如何利用（或绕开）官方 harness

- **直接用**：每个 skill 是 SKILL.md，吃 progressive disclosure 红利；`/learn` 是 `claude-progress.txt` pattern 的第三方版；`/review` 的 Specialist Dispatch 是 sub-agent architecture 的直接应用。
- **绕开**：`/browse` 走 localhost daemon + shell binary，**完全跳过 MCP**——直接享受 zero schema tax。

> **gstack 的所有 skill 都是 SKILL.md（小），把重操作 delegate 给独立进程——完全匹配 Anthropic "give the agent a computer" 原则，同时绕开 MCP token tax。**

---

## Phase 3：交叉验证与发现的矛盾

### 一致点（≥2 agent 印证）

| 论点 | 印证维度 |
|---|---|
| Context window 是稀缺资源 = 一切架构起点 | A (preamble-tier), C (Karpathy context engineering), D (progressive disclosure) |
| `/browse` 通过绕 MCP 节省 context tax | A (架构), D (MCP bloat 论文) |
| gstack 是 sub-agent fanout 的应用层 | A (Specialist Dispatch in `/review`), D (Anthropic sub-agent architecture 策略) |
| Karpathy 的 "Opus 写 novel code, agent 写 boilerplate" 与 gstack Opus 工作模式高度一致 | B, C |
| Skill 之间靠**文件 + prompt** 混合传状态 | A (`{branch}-ship-state.yaml`), D (`claude-progress.txt`) |

### 矛盾点（必须显式标注）

| # | 矛盾 | 解读 |
|---|---|---|
| 1 | **"四大失败模式" vs Karpathy 原帖只有 3 条** | 维度 B/A 提到"Karpathy 的四大失败模式"，C 显式纠偏：第四条是社区衍生。**信 C，记得给别人讲时说"Karpathy 3 条 + 衍生 1 条"** |
| 2 | **"Process over prompts" 出处** | A/D 的官方叙事把它当 gstack 哲学；B 揭示这不是 Tan 写的 manifesto。**信 B，这是社区 framing** |
| 3 | **"23 是合理数量"** | gstack 文档与多数报道暗示这是设计选择；B 的演化数据（6→13→23/28）显示是 emergent。**信 B** |
| 4 | **gstack token bloat vs context-frugal** | B 引 r/ClaudeCode 说"bloated and token-hungry"；D 强调 `/browse` 是 zero schema tax 典范。**实际是**：`/browse` 节俭，但 23 个 skill 一起开 preamble-tier 1 会把 metadata 全部塞进 system prompt → 启动就背一大坨 description。这是 progressive disclosure 的副作用 |
| 5 | **10K LOC/week 是工作流截面 vs marketing 数字** | A/D 提到的 cadence 是 framework 卖点；B 引 critic 用 commit 级数据反驳。**信 B**——这是 self-reported marketing |
| 6 | **Karpathy 推荐自主度档位 vs gstack 默认档位** | C 显示 Karpathy 倾向中档，gstack 倾向高档 + scope 约束。**这不是真矛盾，是 design trade-off**：gstack 用 scope declaration 换 autonomy |

---

## 给瑞哥的迁移建议（基于你 `rules/skills/` 已有结构）

你现有的 `rules/skills/` 已经是 SKILL pack 形态（看 INDEX.md），覆盖很广（workflow_*、bestpractice_*、dapp_*、sre_*、fp_*）。和 gstack 比对：

### 你比 gstack 更克制的地方（不需要改）
- **不强行 role 化所有 skill**：你的 `bestpractice_*` 是方法论而不是 persona，更贴近 Anthropic Skills 设计原则
- **不堆 LOC 数字 marketing**：你的 OBSERVATIONS.md 是真观察，不是 dashboard
- **领域 skill (FP / dApp CI / DV monitoring) 比 role skill 多**——这对一个内部工程师比"扮演 CEO"更值

### gstack 值得抄的 3 个具体点

1. **分支级 handoff YAML**：`~/.context/projects/{repo}/{branch}-{phase}-state.yaml`
   - 让 `/ship` → `/land-and-deploy` 这种链式 skill 有 durable handoff（你现在多半靠 plan 文件，但没有结构化字段）
   - 对应 Anthropic `claude-progress.txt` pattern

2. **`preamble-tier` 字段**：你的 INDEX.md 现在所有 skill 平权。给 `workflow_*` 加 tier 区分：
   - tier 1：每次 session 加载（如 `workflow_parallel_subagents`、`bestpractice_ai_programming_mindset`）
   - tier 4：仅显式触发（如 `workflow_dcluster_starrocks_cn_deployment`）
   - 直接削减 system prompt 占用

3. **Specialist Dispatch with quote-the-line gate**：你做 review/调研类工作时，gstack `/review` 的"finding 必须 quote 具体代码行，否则 confidence 压到 4-5"是简单粗暴但有效的反幻觉机制。建议加进你的 `red-team` 或新建一个 `quote-or-suppress` skill。

### 不建议抄的 2 个点

1. **角色化 CEO/Designer/Eng Manager**：你是 SRE，不是 founder；你的 sub-agent 已经按"能力"切（Explore / librarian / Plan），按"身份"再切是 overhead
2. **23 个 slash command 的扩张**：gstack 的 23 是 founder workflow 的截面，你是 oncall + 调研 workflow 的截面。INDEX.md 现在的密度刚好

---

## Sources（≥40 个独立来源）

### gstack 一手
- [garrytan/gstack repo root](https://github.com/garrytan/gstack)
- [docs/skills.md](https://raw.githubusercontent.com/garrytan/gstack/main/docs/skills.md)
- [README.md](https://raw.githubusercontent.com/garrytan/gstack/main/README.md)
- [ARCHITECTURE.md](https://raw.githubusercontent.com/garrytan/gstack/main/ARCHITECTURE.md)
- [office-hours/SKILL.md](https://raw.githubusercontent.com/garrytan/gstack/main/office-hours/SKILL.md)
- [browse/SKILL.md](https://raw.githubusercontent.com/garrytan/gstack/main/browse/SKILL.md)
- [qa/SKILL.md](https://raw.githubusercontent.com/garrytan/gstack/main/qa/SKILL.md)
- [review/SKILL.md](https://raw.githubusercontent.com/garrytan/gstack/main/review/SKILL.md)
- [investigate/SKILL.md](https://raw.githubusercontent.com/garrytan/gstack/main/investigate/SKILL.md)
- [ship/SKILL.md](https://raw.githubusercontent.com/garrytan/gstack/main/ship/SKILL.md)
- [issue #1088 "just a bunch of prompts"](https://github.com/garrytan/gstack/issues/1088)

### gstack 三方分析（正面）
- [GStack — Turn Claude Code into a Virtual Software Development Team](https://gstacks.org/)
- [Pulumi: Superpowers, GSD, and GSTACK](https://www.pulumi.com/blog/claude-code-orchestration-frameworks/)
- [Augment Code: gstack hits 89.7K stars](https://www.augmentcode.com/learn/garry-tan-gstack-hits-89.7K-stars)
- [Augment Code: gstack analysis](https://www.augmentcode.com/learn/garry-tan-gstack-claude-code)
- [MindStudio: What Is GStack?](https://www.mindstudio.ai/blog/what-is-gstack-gary-tan-claude-code-framework)
- [SitePoint Tutorial](https://www.sitepoint.com/gstack-garry-tan-claude-code/)
- [mager.co: gstack plugin](https://www.mager.co/blog/2026-03-28-gstack-garry-tan-claude-plugin/)
- [dev.to/imaginex: Skills Stack combo](https://dev.to/imaginex/a-claude-code-skills-stack-how-to-combine-superpowers-gstack-and-gsd-without-the-chaos-44b3)
- [Codex Knowledge Base](https://codex.danielvaughan.com/2026/03/30/gstack-garry-tan-production-skills-toolkit/)
- [explainx.ai analysis](https://explainx.ai/blog/gstack-garry-tan-claude-code-skills-factory)
- [Medium: Each framework constrains what](https://medium.com/@tentenco/superpowers-gsd-and-gstack-what-each-claude-code-framework-actually-constrains-12a1560960ad)

### gstack 批评视角
- [TechCrunch: love and hate](https://techcrunch.com/2026/03/17/why-garry-tans-claude-code-setup-has-gotten-so-much-love-and-hate/)
- [Medium Rentier: solves the wrong problem](https://medium.com/@rentierdigital/y-combinators-ceo-shared-his-claude-code-prompt-it-solves-the-wrong-problem-c1d0c7a245c3)
- [andrew.ooo: gstack red flags](https://andrew.ooo/posts/gstack-garry-tan-claude-code-setup/)
- [HN discussion 47355173](https://news.ycombinator.com/item?id=47355173)
- Fast Company on Gregorein critique

### 对照框架
- [obra/superpowers](https://github.com/obra/superpowers)
- [gsd-build/get-shit-done](https://github.com/gsd-build/get-shit-done)

### Karpathy 一手
- [Software Is Changing (Again) — YC 2025](https://www.ycombinator.com/library/MW-andrej-karpathy-software-is-changing-again)
- [Karpathy on context engineering](https://x.com/karpathy/status/1937902205765607626)
- [Karpathy vibe coding tweet](https://x.com/karpathy/status/1886192184808149383)
- [Dwarkesh × Karpathy: AGI decade away](https://www.dwarkesh.com/p/andrej-karpathy)
- [multica-ai/andrej-karpathy-skills (CLAUDE.md, 4 rules)](https://github.com/multica-ai/andrej-karpathy-skills)
- [karpathy/nanochat](https://github.com/karpathy/nanochat)
- [The Decoder: codes mostly in English](https://the-decoder.com/former-tesla-ai-chief-andrej-karpathy-now-codes-mostly-in-english-just-three-months-after-calling-ai-agents-useless/)
- [Simon Willison: not all AI coding is vibe coding](https://simonwillison.net/2025/Mar/19/vibe-coding/)
- [Pebblous: Karpathy coding pitfalls](https://blog.pebblous.ai/report/karpathy-coding-skills-2026-04/en/)
- [PureAI: context at the core](https://pureai.com/articles/2025/09/23/karpathy-puts-context-at-the-core-of-ai-coding.aspx)
- [Menon Lab: Karpathy CLAUDE.md 4 rules](https://themenonlab.blog/blog/karpathy-claude-md-four-rules-ai-coding-agents)

### Anthropic 一手（harness / Skills）
- [Equipping agents with Skills](https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills)
- [Introducing Agent Skills (2025-10-16)](https://claude.com/blog/skills)
- [Skills explained: vs prompts/projects/MCP/subagents](https://claude.com/blog/skills-explained)
- [Effective context engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
- [Building agents with Claude Agent SDK](https://claude.com/blog/building-agents-with-the-claude-agent-sdk)
- [Harness design for long-running apps](https://www.anthropic.com/engineering/harness-design-long-running-apps)
- [Effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)
- [Code execution with MCP](https://www.anthropic.com/engineering/code-execution-with-mcp)
- [Building Effective Agents (Dec 2024)](https://www.anthropic.com/research/building-effective-agents)
- [April 23 post-mortem on Claude Code quality](https://www.anthropic.com/engineering/april-23-postmortem)
- [Complete Guide to Building Skills (PDF)](https://resources.anthropic.com/hubfs/The-Complete-Guide-to-Building-Skill-for-Claude.pdf)

### Tan 一手 tweets
- [On big features in an hour](https://x.com/garrytan/status/2020072098635665909)
- [10-15K LOC/day](https://x.com/garrytan/status/2018368316033946021)
- [Should be in Claude Code system prompt](https://x.com/garrytan/status/2015540619855425959)
- [Knowing how to prompt is the real unlock](https://x.com/garrytan/status/2021445200024092943)

### Tan 背景
- [Wikipedia: Garry Tan](https://en.wikipedia.org/wiki/Garry_Tan)
- [YC profile](https://www.ycombinator.com/people/garry-tan)
