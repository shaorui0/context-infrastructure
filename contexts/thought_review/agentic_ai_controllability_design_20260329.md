# Agentic AI 可控性设计：从第一性原理到生产级实现

Session: 2026-03-29

## Key Insights

**Agent 的一句话定义**：行为空间开放、运行边界受限的自主执行系统。两个条件缺一个都不成立——没有开放性是脚本，没有约束是灾难。

**Agent 工程与 SRE 可靠性工程是同构问题。** 不可预测性的来源不同（分布式系统 vs LLM 概率采样），但解法是同构的：RBAC → Scope Declaration，blast radius → Authorized 范围限制，audit log → Execution Log，observability → reasoning trace。这是一个有 SRE 背景的人做 agent 的真正优势所在。

**Skill/Agent 定义 vs Prompt 的本质区别不在格式（都是 markdown），在于系统角色。** Prompt 是一次性指令（kubectl 命令），Agent 定义是声明式系统规格（Pod spec）。Skill 介于两者之间，是带输入输出契约的 SOP。

**Agent 完整组件表比通常理解的多两项。** 除了 LLM + Tools + Memory + Permissions，还需要 Goal Decomposition（plan agent 模式）和 Feedback Loop（结果回流到决策）。前者让 agent 能自己拆任务，后者让 agent 真正成为闭环。

**Agent 频繁停下来问用户的根因是不确定自己有没有权做下一步。** 解法不是"别问"，是提前消除不确定性。三层手段递进：Scope Declaration（预授权一个范围）→ Execution Contract（明确什么条件停什么条件继续）→ Sub-agent Parallelism（拆小 scope，每个 sub-agent 决策空间更窄）。

**Plan File 是整个设计的枢纽，一个文件三重身份**：执行计划（tracking progress）+ RBAC Policy（scope-gate 读它判断权限）+ Audit Log（execution log 追加在底部）。为什么必须持久化到文件：context window 会被压缩，文件不会。

## Open Questions

- **Scope Declaration 的粒度怎么把握？** 当前用命令前缀匹配（`kubectl --kubeconfig=... get`），对于复杂场景（比如"可以 apply 但只能 apply 某个 namespace"）可能不够。需要更精细的 scope DSL，还是用 hook 链叠加解决？
- **Re-plan 的触发条件和成本。** 当前设计是"执行偏离时重新派 Plan agent"，但频繁 re-plan 会消耗大量 token。什么时候 re-plan，什么时候在已有计划上微调？
- **Multi-agent orchestration 的实际价值边界在哪？** Session 中确认了"90% 的价值在 single-agent + good tools + constraints"。那剩下 10% 真正需要 multi-agent 的场景具体是什么？
- **Observability 层还没有具体实现。** Execution Log 解决了审计问题，但 reasoning trace（agent 为什么做了这个决策）目前只存在于 context window，没有持久化方案。

## Concrete Artifacts

### 1. 文件产出

| 文件 | 位置 | 作用 |
|------|------|------|
| workflow_autonomous_execution.md | `rules/skills/` | 三阶段自主执行 skill 定义 |
| scope-gate.py | `~/.claude/hooks/` | PreToolUse hook，读 plan file scope 自动放行/拦截 |
| plan-k8s-health-check.md | `tmp/` | 验证用的 plan 文件实例 |
| settings.json (updated) | `~/.claude/` | 注册 scope-gate 到 Bash/Edit/Write hook chain |

### 2. Agent 组件表

| 组件 | 作用 | Claude Code 对应 |
|------|------|-----------------|
| LLM | 决策引擎 | Claude model |
| Tools | 执行能力 | Bash, Read, Edit, MCP servers |
| Memory | 状态持续 | Context window + MEMORY.md + CLAUDE.md |
| Permissions/Hooks | 行为约束 | Permission mode, hooks, sandbox |
| Goal Decomposition | 目标拆解 | Plan mode, TaskCreate, Plan agent |
| Feedback Loop | 结果回流 | Tool results → next LLM call |

### 3. 面试核心叙事（三层递进）

**30 秒版**："Agent = 行为空间开放 + 运行边界受限。缺一个都不成立。"

**1 分钟版**（加 SRE 同构论）："Agent 工程和 SRE 面对的是同构问题：都是在给不可预测的系统建立可靠性保证。解法也同构：RBAC、blast radius、audit log、observability。"

**2 分钟版**（加具体设计）："Plan File 三重身份（计划 + 权限 + 审计），Scope Declaration 预授权模式，hook chain 自动执行门禁，在 dev 集群上端到端验证通过。"

### 4. 记忆锚点：GCORF

- **G** — Goal Decomposition
- **C** — Controllability
- **O** — Observability
- **R** — Reversibility
- **F** — Feedback Loop

五个维度覆盖 agent 系统设计所有核心问题。面试时按场景从中抽取。
