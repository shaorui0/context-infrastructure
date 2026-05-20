# Agentic 系统的四个控制论原语

**Date**: 2026-04-13

---

## 起点：角色分工是错误的抽象层

当前 agentic 框架普遍用角色（PM、Engineer、QA、Reviewer）来组织多 agent 协作。这是把人类组织结构直接搬过来的 skeuomorphism。问题不在于这样做"不能工作"，而在于它把注意力引向了错误的设计维度。

当你在设计一个 agent pipeline 时，问"这个 agent 应该扮演 PM 还是 Engineer"是一个低信息量的问题。它没有告诉你 context 怎么隔离、状态怎么持久化、错误怎么收敛、危险操作怎么拦截。而这四件事才是决定系统能否可靠运行的关键。

更好的问法是：这个子任务需要什么样的 spec、什么样的收敛条件、什么样的准入控制、什么样的 context 边界。


## 四个原语

### 1. Spec（声明式意图）

Spec 是持久化的终态描述。它可以被 diff，可以被 validate，可以在 context 压缩后完整恢复。

Spec 解决的核心问题是：当 agent 的 context window 被压缩、当 session 中断重启、当任务在多个 subagent 之间流转时，意图不丢失。Memory（无论是 in-context memory 还是外部向量存储）做不到这一点，因为 memory 没有 schema，不可 diff，不可 validate。Memory 是 best-effort recall，spec 是 declarative contract。

这个认知在实践中已经有了对应物。`workflow_autonomous_execution` 里的 scope declaration 持久化到 plan 文件，本质就是 spec。但目前这个 spec 是非结构化的自然语言，尚未发展到可机器验证的程度。下一步的演化方向是：spec 本身要有足够的结构，使得 loop 的每一轮可以自动判断"是否已经收敛到 spec 描述的终态"。

对应 K8s：Desired State（YAML manifest）。

### 2. Loop（收敛循环）

Loop 不是"重复执行同一段逻辑"。Loop 是以 spec 为终点、带反馈的收敛过程。每轮 loop 执行后，系统检查当前状态与 spec 的偏差，决定下一步动作。这和 K8s controller 的 reconciliation loop 是同一个结构。

Loop 能工作的前提条件是：终点必须是机器可验证的。"帮我把代码写完"不是一个可验证终点。"帮我把代码写完，编译通过，UT 全绿"是。终点条件越具体、越可自动检查，loop 越能自主收敛。

这揭示了一条渐进链条，每一级的终点验证手段不同：

```
写代码        → 文件存在、语法正确（AST parse）
编译通过      → exit code 0
UT 通过       → test runner exit code 0 + coverage threshold
Sandbox 验证  → mocked traffic 下无 error log、响应符合 schema
Ops ready     → lint/security scan pass、资源配置合理
K8s deploy    → rollout status succeed、health check pass
```

这条链条的每一步都把"AI 做完了"转化成"机器确认做对了"。以前这些验证步骤是人工 review 的杂活，现在它们成了 loop 的自动收敛检查点。这就是"让 AI 走最后一公里"的真正含义：不是让 AI 做更多，而是让 AI 的产出可以被机器验证，从而消除人工确认的瓶颈。

对应 K8s：Reconciliation Loop（Controller pattern）。

### 3. Hook（准入控制）

Loop 如果不加约束就是危险的：一个能自主收敛的系统也能自主走向灾难。Hook 在 loop 的关键节点做拦截，分三类：

**审计型**：记录 agent 做了什么，不阻断执行。对应 K8s 的 audit logging。实现简单，但本身不能阻止错误，只能事后追溯。

**禁止型**：某些操作直接禁止（force push、drop table、删除 production namespace）。Fail-closed。对应 OPA / Gatekeeper。

**HITL 型**：对高风险但非绝对禁止的操作，暂停 loop 等待人类确认。对应 K8s 的 manual approval gate。这类 hook 的设计难点在于阈值：太敏感会变成每步都要人确认（退化为手动模式），太宽松等于没有。

Red team / challenge 也是 hook 的一种形式。它的特殊之处在于不是基于规则拦截，而是用另一个 agent 做对抗性审查。这对应 K8s 的 ValidatingWebhook：mutation 发生后、commit 之前，由外部逻辑决定是否放行。

一个重要的设计选择：red team challenge 应该发生在两个点，而不只是产出完成后。第一个是 spec 定稿时（spec 本身合理吗？目标是否正确？），第二个是产出完成时（实现是否符合 spec？是否引入了新问题？）。如果只在终点 challenge，spec 层面的错误会导致整个 loop 白跑。

对应 K8s：Admission Controller + OPA + ValidatingWebhook。

### 4. Fork（context 隔离）

Subagent 存在的理由不是"需要一个不同角色的 agent"，而是需要 context 隔离。

一个常见的误区是把 fork subagent 类比为开线程。线程的动机是 +throughput（CPU-bound，多核真并行）和 -latency（I/O-bound，重叠等待）。很多人照搬这个思路到 agent 系统，看到能并行就 fork，就像 Java 早期到处 new Thread 一样。

但这个类比在关键处是错的。线程共享内存，subagent 不共享 context。Subagent 是进程，不是线程。每个 subagent 有独立的地址空间（context window），启动时需要显式传递信息（IPC），完成后只返回结果。Fork 的开销不是微秒级的 context switch，而是信息损耗：parent 知道的东西必须压缩成一段 prompt 传过去，这个过程必然有丢失。

所以 fork 的决策框架不是"能不能并行"，而是：**隔离带来的收益是否大于信息传递的损耗。**

#### 三种 bound

**Attention-bound（注意力绑定）。** 这是 subagent 独有的 fork 动机，线程没有对应物。Transformer 的 attention 随 context 长度退化。当一个 agent 的 context 里同时装着调研原始资料、代码片段、用户需求、中间讨论，它对每条信息的关注度都在下降。表现就是"偷懒"：产出变笼统、遗漏细节、开始 hallucinate。Fork 的目的是给子任务一个干净的 context，只包含它需要的信息。不是为了快，是为了好。最接近的系统类比是 CPU cache locality：working set 在 L1 里运算就快，溢出到 main memory 性能断崖下降。Context window 就是 agent 的 cache，fork 是在保证子任务的 working set 完整放进 L1。

**Capacity-bound（容量绑定）。** 单 context window 物理装不下任务所需的全部信息。最直观的 fork 理由。注意"有效承载量"远小于标称 context length：128K token 的 window 在 80K+ 时 attention 质量已经显著下降。

**Latency-bound（延迟绑定）。** 多个独立任务并行，重叠 wall-clock time。这才是线程类比成立的部分。但前提是任务必须真正独立：如果两个 subagent 的产出最终需要复杂合并（不是简单拼接），并行带来的时间节省可能被协调成本吃掉。

**Independence-bound（独立性绑定）。** 有些任务需要隔离不是因为 context 太大或太杂，而是因为共享 context 会引入系统性偏见，降低验证价值。

最典型的例子是代码审查。如果 reviewer 和 developer 共享 context，reviewer 看到了 developer 的所有试错过程、考虑过的替代方案、做出某个选择的理由。这让 reviewer 系统性地倾向于认同开发者的决策，因为它"理解了 why"。但 review 的价值恰恰在于不知道 why 的情况下，纯粹从产出层面判断：需求有没有被完整实现、方案有没有被正确落地、有没有引入新问题。

测试同理。测试 Agent 如果知道开发者"觉得这个边界条件没问题"，它会倾向于不测那个边界条件。测试的价值在于它不知道开发者的假设，从外部视角验证。

Red team 也属于这个类别。Challenger 和 producer 如果读了同样的推理过程，challenge 就退化为 echo chamber。

这是人类组织里早已确立的原则：code review 不能自己 review 自己的代码，审计必须独立于被审计方。不是能力问题，是独立性问题。Agent 系统里是同一个道理。

Independence-bound 和 attention-bound 的区别：attention-bound 是"context 太杂导致质量下降"，解决方法是给子任务干净的 context；independence-bound 是"共享 context 导致判断偏见"，解决方法是 reviewer/tester 只看 spec + 产出，不看过程。前者是信噪比问题，后者是认知独立性问题。

#### 七个角色 vs 三个隔离边界

以腾讯光子 JK Launcher 的七个 Agent 角色为例，用隔离本质重新分析：

| 角色 | 需要独立 Agent 吗 | 真正的本质 |
|---|---|---|
| PM（路由调度） | 不需要 | Orchestration logic，不是 context holder |
| 需求分析 | 视规模而定 | Spec 编写的前半段 |
| 方案设计 | 视规模而定 | Spec 编写的后半段 |
| 闸门总控 | 不需要 | Hook（准入检查），不需要持久 context |
| 开发实现 | 需要 | 主工作 context，积累大量中间状态（attention-bound） |
| 代码审查 | 需要 | 必须 context 独立，否则审查有偏见（independence-bound） |
| 测试验证 | 需要 | 必须 context 独立，否则测试覆盖有偏见（independence-bound） |

七个"角色 Agent"实际上是：1 个调度逻辑 + 1 个 spec 编写 context + 1 个 hook + 3 个需要隔离的工作 context。真正需要 fork 的是 3 个，不是 7 个。Fork 的判据不是"你扮演什么角色"，是"你是否需要 context 隔离来保证产出质量或判断独立性"。

#### 什么时候不该 fork

**任务小。** Fork 有固定开销：构造 prompt、传递上下文、等待启动、收取结果。子任务只需要 3-5 个 tool call 的话，fork 的开销超过任务本身。为了加两个数开一个进程。

**共享可变状态。** 两个子任务需要编辑同一个文件或持续共享中间结果。Fork 出去没有共享内存，每次同步都是显式 IPC。在 agent 世界里表现为 merge conflict（字面意义上的 git conflict，或逻辑上的决策冲突）。

**串行依赖。** B 依赖 A 的完整输出。Fork 只是串行执行加了一层 IPC 开销。

**没法充分 brief。** Parent agent 脑子里有大量隐含上下文（之前的讨论、用户偏好、已排除的方案），如果这些没法压缩成 prompt 传给 subagent，subagent 就是 going in blind。产出质量不是变好了，是变差了。这是 fork 最隐蔽的成本。

#### Fork 决策优先级

```
1. 该子任务是否需要判断独立性？
   （审查、测试、red team）→ fork，independence-bound

2. 当前 context 是否 attention-bound？
   （大量无关信息稀释注意力）→ fork，给子任务干净 context

3. 信息量是否 capacity-bound？
   （单 window 物理装不下）→ fork，按信息维度拆分

4. 是否有可并行的独立子任务？
   （无数据依赖，结果可简单聚合）→ fork，-latency

5. 以上都不满足？→ 不 fork
```

优先级 1 > 2 > 3 > 4。Independence-bound 是硬性要求（不隔离 = 验证失效），attention-bound 影响产出质量，capacity-bound 是物理限制，latency-bound 只是时间优化。

对应 K8s：Pod isolation + namespace + resource limits。


## 推论：约束结果，不约束过程

四原语模型隐含了一个重要的设计原则：**声明式约束优于命令式约束。**

命令式约束告诉 agent"怎么做"：每次改完代码必须编译，编译完必须跑测试，测试完必须事后验证。这是过程约束，用 Rule 规定每一步行为。问题在于 agent 会绕路：它不是违反规则，是找到了规则没覆盖的路径。"这次只改了文档不用编译"、"这个测试失败是历史遗留"、"我已经做了等价验证"。

声明式约束告诉 agent"done 长什么样"：实现这个功能，验收标准是编译通过、UT 全绿、lint 无新增 warning。不管 agent 用什么路径到达，只要终态满足这些条件。

区别在于收敛动力的来源。当任务定义是"帮我实现这个功能"，agent 的隐含理解是"代码写完 = done"。编译和测试在它看来是额外负担，所以有动机跳过。你用 Rule 强制它做，它就找理由绕过。当任务定义是"实现这个功能，且编译通过、UT 全绿"，编译和测试就是收敛条件的一部分。Agent 不需要被告知"你要编译"，它会自主编译，因为不编译就到不了终态。收敛动力从外部强制变成了内生驱动。

这就是 K8s 声明式 vs 命令式的核心区别。你不写 `kubectl run` + `kubectl expose` + `kubectl scale` 的脚本，你写一个 YAML 声明终态，controller 自己决定怎么到达。Pod 挂了 controller 自动拉起来，不需要 Rule 说"Pod 挂了必须重启"。

这个原则对 spec 编写的直接指导是：**spec 必须包含验收标准（acceptance criteria），而且验收标准必须是机器可验证的。** "帮我实现登录功能"是一个不完整的 spec。"实现登录功能，验收标准：(1) 编译通过 (2) 登录成功/失败两条路径的 UT 全绿 (3) lint 无新增 warning (4) 无 hardcoded credentials"是一个可以驱动 loop 自动收敛的 spec。

验收标准本身就是 checkpoint。但这里的 checkpoint 不是"过程中的检查点"（Step 1 完成后检查，Step 2 完成后检查），而是多个独立的结果条件。Agent 可以先写测试再写代码（TDD），也可以先写代码再补测试，只要最终所有条件都满足。不规定顺序，只规定终态。

腾讯光子的 JK Launcher 项目走的是命令式路线：Rule 约束行为 → Rule 被忽略 → 升级到 Scripts 强制验证 → 用基线对比兜底。整条链路都在给过程加锁。如果他们从一开始就在 spec 里定义清晰的验收标准，很多后续的 Rule 和 Script 层就不需要了。Scripts 只需要做验收标准的自动化执行，不需要承担定义"什么叫做完"的职责。

这也解释了一个反直觉的现象：约束越多，系统越脆弱。因为每条过程约束都是一个 agent 可以绕过的点。而结果约束只有一个判断：终态是否满足。绕不过去。


## 四原语的组合

这四个原语不是独立工作的，它们组合成一个完整的控制回路：

```
Spec 定义终态
  ↓
Fork 按 context 需求拆分子任务
  ↓
Loop 驱动每个子任务向 spec 收敛
  ↓
Hook 在 loop 的关键节点做准入控制
  ↓
Loop 检查整体是否收敛到 spec → 未收敛则继续
```

Skill（领域知识，比如 production analysis、code lint、security scan、performance benchmark）不是第五个原语，而是 loop 内部的工具。Skill 告诉 loop "怎么验证这一步是否做对了"。对应 K8s 里的 Operator：把领域知识编码进 controller，使 reconciliation loop 能够处理该领域特有的收敛逻辑。


## Harness Engineer 的本质

如果 agentic 系统的正确抽象是四个控制论原语，那"harness engineer"这个角色的本质就清晰了：**控制平面工程师**。

Harness engineer 不写 application logic（那是 agent 干的事）。Harness engineer 做的是：

- 写 spec：把意图编码成可 diff、可验证的声明式描述
- 设计 loop：定义收敛条件、checkpoint 策略、退出判据
- 配置 hook：设定 policy（什么允许、什么禁止、什么需要审批）
- 决定 fork 边界：判断哪些子任务需要独立 context，如何 brief subagent

这和 K8s platform engineer 的工作完全同构。Platform engineer 不写业务代码，写的是 controller、admission policy、namespace 规划、resource quota。业务逻辑跑在 Pod 里（agent 里），platform engineer 确保这些 Pod 在约束下可靠收敛。

换个角度看：传统软件工程的分工是"写代码的人"和"跑代码的人"（dev vs ops）。Agentic 时代的分工变成了"被 agent 替代的执行"和"设计 agent 如何执行的控制平面"。Harness engineer 站在控制平面这一侧。核心能力不是写代码能力（agent 可以写），而是三件事：定义"什么叫做对"（spec + acceptance criteria），设计"怎么确认做对了"（loop + verification），以及划定"什么不能做"（hook + policy）。

这跟 SRE 的能力模型高度重合。SRE 的核心也不是写代码，是定义 SLI/SLO（什么叫好）、设计 monitoring/alerting（怎么发现不好）、配置 safeguard（怎么防止变坏）。所以 harness engineer 可以理解为 SRE 在 agentic 时代的自然延伸：运维对象从"服务"变成了"agent workflow"，方法论内核没变。


## Agent 通信：文件，不是 Session

一个延伸问题：多个 agent 之间怎么共享信息？

当前很多框架的做法是 share session，即让多个 agent 共享同一段对话历史，或者把一个 agent 的 session 输出喂给另一个。这本质上是共享内存模型：把运行时状态（session context）当作通信介质。

这条路是错的，原因和操作系统里共享内存的问题一样：

**脆弱。** Session context 会被压缩、截断、遗忘。它是运行时的 volatile state，不是持久化的 durable state。在 session 的第 5 轮还能准确 recall 第 1 轮的细节，到第 50 轮就不行了。

**不可检视。** 你没法对一个 session 做 diff。你没法 review 一个 session 里到底传递了什么信息。它是黑盒。

**紧耦合。** Share session 要求 agent 在时间上同步存在。Agent A 必须在 Agent B 还活着的时候把信息传过去。Session 结束，信息消失。

**不可恢复。** Session 挂了，中间状态全丢。没有 checkpoint，没有 replay 能力。

正确的 agent 通信方式是通过 spec，也就是持久化的文件。这是 Unix 哲学的直接应用：进程之间通过文件系统和管道通信，不通过共享内存。也是 K8s 的做法：Pod 之间通过 API server（etcd = 持久化状态存储）通信，不通过 shared memory。

具体到 agent 系统：

- Agent A 的产出写入文件（spec、report、code）
- Agent B 启动时读取这些文件作为输入
- 文件是 git-tracked 的，可以 diff、可以 review、可以 rollback
- 任何 agent 都可以在任何时间点 pick up 另一个 agent 的产出继续工作

这就是 spec 原语在 agent 通信中的延伸：spec 不仅是"意图的持久化"，也是"agent 间信息传递的介质"。Agent 之间的接口契约就是文件格式和目录约定，不是 session context。

已经在实践中验证的例子：`workflow_autonomous_execution` 把 plan 写到文件里，sub-agent 读文件获取上下文，完成后把结果写回文件。没有 session 共享，任何一个 sub-agent 挂掉都可以重启重来。这比 share session 可靠得多。

更远一步：如果 agent 间的通信全部通过文件，那 agent 系统的调试就变成了"看文件改了什么"，也就是 git diff。这让 agent workflow 的可观测性从"看 log 猜发生了什么"变成了"看 diff 知道发生了什么"。Observability 从 log-based 变成了 state-based。


## 与现有框架的关系

`bestpractice_agent_harness_architecture`（Policy Runtime + Stateful Workflow + Orchestrator）是实现层的三层架构。本文的四原语是更底层的抽象。映射关系：

- Policy Runtime 实现了 Hook（准入控制）
- Stateful Workflow 实现了 Spec（通过 checkpoint）和 Loop（通过 state machine + retry）
- Orchestrator 实现了 Fork（通过 sub-agent fanout + routing）

`bestpractice_agent_reliability_engineering` 的三支柱（Constraints, Observability, Convergence）也可以用四原语重新表述：Constraints = Hook，Convergence = Loop + Spec，Observability 是跨 hook 和 loop 的横切关注点。

四原语提供了一个更精确的语言来谈论 agent 系统设计，避免了角色比喻带来的歧义。当有人说"我需要一个 PM agent"时，真正需要回答的问题是：你需要什么样的 spec 格式？loop 的收敛条件是什么？哪些操作需要 hook？子任务是否需要独立 context？


## 类比完整映射

| Agentic 概念 | K8s 等价物 | 共同本质 |
|---|---|---|
| Spec + acceptance criteria | Desired State (YAML) | 声明式意图，持久化，可 diff，包含收敛条件 |
| Loop | Reconciliation Loop | 持续检测偏差，驱动收敛 |
| Hook | Admission Controller + OPA | 在 mutation 路径上做准入控制 |
| Fork (attention-bound) | Pod + resource limits | 资源隔离防止退化 |
| Fork (independence-bound) | 独立审计方 / 外部 admission | 判断独立性保证验证有效性 |
| Skill | Operator | 领域知识编码进 controller |
| Red Team | ValidatingWebhook | 外部逻辑做对抗性验证 |
| 声明式约束 > 命令式约束 | Declarative YAML > imperative kubectl | 约束终态而非过程 |

这不是牵强的类比。K8s 和 agentic systems 面对的是同一类问题：如何让一个不完全可靠的执行组件（Pod / LLM agent）在声明式终态约束下可靠收敛。K8s 用了二十年沉淀出了 controller pattern 这套方法论。Agentic 系统不需要重新发明，可以直接继承这个认知框架。


## 三个独立来源的交叉验证

这个四原语模型不是从单一来源推导出来的。三个完全独立的实践（OpenAI Codex、腾讯光子 JK Launcher、本文的控制论推导）收敛到了同一个结构：

| 维度 | OpenAI (Codex) | 腾讯光子 (JK Launcher) | 四原语模型 |
|---|---|---|---|
| Spec 载体 | docs/ + execution plans，repo 是 system of record | SPEC 设计规格文档 | 声明式意图，持久化，可 diff |
| Loop 机制 | Ralph Wiggum Loop（agent-to-agent review 循环） | 七轮迭代修正 + Scripts 验证 | 以 spec 为终点的收敛循环 |
| Hook 实现 | linters + CI + approval gate + doc-gardening agent | 闸门总控 + 代码审查 + 测试验证 | 准入控制三类（审计/禁止/HITL） |
| Fork 方式 | git worktree per task + ephemeral observability stack | 七个固定角色 Agent | context 隔离（四种 bound） |
| 通信方式 | repo-local versioned artifacts | 阶段文档交接 | 文件，不是 session |
| 工程师角色 | "design environments, specify intent, build feedback loops" | "人负责设计系统，AI 负责高强度执行" | 控制平面工程师 |

三条路径，同一个终点。这不是巧合，是问题域的结构性约束决定的：当执行者是不完全可靠的 agent 时，你必然需要声明意图（spec）、驱动收敛（loop）、约束边界（hook）、隔离 context（fork）。和 K8s 面对不完全可靠的 container 时收敛到 controller pattern 是同一个道理。

各来源的差异点也有价值：

OpenAI 比腾讯和本文多出的 insight：**agent legibility**。让 codebase 对 agent 可读，比让 agent 变聪明更有杠杆。boring technology 优于 fancy technology，因为 agent 更容易推理。"give Codex a map, not a 1,000-page instruction manual"。

腾讯比 OpenAI 多出的 insight：**基线对比（baseline diff）**。开发前跑一次验证，开发后再跑一次，对比差异。这让验证从"通过/不通过"变成了"变好了/变差了"，可以捕捉 agent 偷偷引入的退化。

本文比两者多出的 insight：**independence-bound** 作为 fork 的独立维度，以及 **声明式约束优于命令式约束** 作为 spec 设计的核心原则。


## Open Questions

**Spec 的结构化程度**。目前 spec 多为自然语言。要让 loop 自动判断"是否已收敛到 spec 描述的终态"，spec 需要多结构化？完全形式化会丧失灵活性，完全自然语言又没法机器验证。可能的中间态：自然语言 spec + 机器可验证的 acceptance criteria checklist。

**Hook policy 如何自身 spec 化**。Hook 的规则（什么操作需要审批、什么操作被禁止）本身也是一种 spec。但这个 meta-spec 放在哪里？怎么版本管理？怎么在不同任务间复用？目前的实现是散落在各 skill 和 CLAUDE.md 里的规则，尚未统一。

**Red team 的有效性条件**。让一个 agent challenge 另一个 agent 的产出，有效的前提是 challenger 有独立的 context 和判断基准。如果 challenger 和 producer 读的是同一份 spec、用的是同一个 prompt 模板，challenge 就会退化为 echo chamber。怎么保证 red team agent 有足够的"独立性"？

**Agent 通信的文件格式标准化**。如果 agent 间通过文件通信，文件格式就是接口契约。目前是 ad-hoc 的 markdown，没有 schema。是否需要定义一套 agent interchange format？还是 markdown + 目录约定已经够用？过度标准化会引入不必要的复杂度，但完全没有约定会导致 agent 之间互相误读。

**State-based observability 的实操**。"看 git diff 知道发生了什么"在理论上优于"看 log 猜发生了什么"。但实操中，agent 的 diff 可能很大很杂。需要什么样的 diff 摘要/可视化工具才能让 state-based observability 真正可用？

**基线对比（baseline diff）的系统化**。腾讯光子的"开发前跑一次、开发后再跑一次、做 diff"是一个值得系统化的模式。它让验证从 pass/fail 变成了 delta，可以捕捉 agent 偷偷引入的退化。如何在不增加太多开销的前提下，把 baseline diff 集成进 loop 的每一轮？
