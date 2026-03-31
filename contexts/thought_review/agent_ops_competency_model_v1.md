# Agent Ops 核心能力模型 v1

**日期**: 2026-03-31
**来源**: RAG/Agent Ops 岗位能力讨论

---

## 背景

传统 SRE 有清晰的能力考察点（Linux 内核、网络、分布式系统、监控、incident response），源自几十年 postmortem 积累出的共识。Agent Ops 还在"积累事故"的阶段，尚未收敛出公认的能力模型。

本文是基于个人实践提炼的 v1 框架，预期随积累持续演化。

---

## 六柱框架

### Pillar 1: Evaluation（评估体系设计）

地位：基础设施。没有评估，其他五个柱子都是在凭感觉优化。

核心能力：为 agent 系统设计可量化的质量指标，并建立自动化 eval pipeline。

**四层评估模型（由易到难）：**

**Layer 1 — Task Completion（任务完成率）。** agent 是否完成了被要求做的事。实操方法：构建 eval dataset（50-200 个有明确预期结果的任务），每次改动后跑一遍算通过率。这是 agent 领域的回归测试。

**Layer 2 — Output Quality（输出质量）。** 完成了不等于做得好。三种评估方法：
- 人工评审：设计评分维度（准确性、完整性、简洁性、格式），让人打分。最可靠，不可扩展。适合低频高价值场景，比如每周抽检 20 个 case。
- LLM-as-Judge：用另一个模型按 rubric 打分。成本低、可扩展。核心难点是 judge 偏见：verbosity bias（倾向给长回答高分）、self-preference bias（倾向给自家模型高分）、format bias（倾向给列表格式高分）。设计 rubric 时要有意识地对抗这些偏见。
- 基于信号的自动评估：从输出中提取可计算信号（是否有 citation、代码是否通过 lint、JSON 是否 valid、回答长度是否合理），组合成 proxy score。

**Layer 3 — Process Quality（过程质量）。** 不只看最终输出，还看到达答案的路径。关注：tool call 次数（效率）、是否调用了正确的工具（决策质量）、是否出现无效循环（robustness）、token 消耗量（成本）。做法是 trace logging + 指标提取，和分布式系统的 distributed tracing 完全同构，span 从"服务调用"变成"tool call"。

**Layer 4 — Behavioral Consistency（行为一致性）。** 同类任务在不同条件下表现是否稳定。测试方法是 perturbation set：同一任务换措辞、加干扰、改上下文顺序，看 agent 表现是否稳定。在安全敏感场景尤其重要。

**与 SRE 概念的映射：**

| Agent 评估层 | SRE 等价物 |
|---|---|
| Task Completion | Availability SLI |
| Output Quality | Quality SLI（错误率、准确率） |
| Process Quality | Latency SLI + Cost SLI |
| Behavioral Consistency | Resilience testing |

**从零开始的优先级：** eval dataset（Layer 1）→ trace logging（Layer 3）→ LLM-as-Judge rubric（Layer 2）→ perturbation set（Layer 4）。

---

### Pillar 2: Failure Mode Taxonomy（故障模式分类学）

地位：反哺 Evaluation 指标设计的知识积累。

核心能力：对着 agent 的烂输出，30 秒内判断根因属于哪一类，知道对应的修复方向。

已建立完整的分类体系和记录工作流，详见 `rules/skills/workflow_agent_failure_taxonomy.md`。6 大类 25 种故障模式：

| 类别 | 覆盖范围 |
|---|---|
| C: Context Failures | 上下文溢出、饥饿、过期、投毒、粒度错误 |
| R: Retrieval Failures | 检索未命中、检索噪声、路由错误 |
| T: Tool Use Failures | 工具选错、参数编造、结果误读、调用循环、级联错误 |
| P: Planning Failures | 目标漂移、过早承诺、范围蔓延、拆分失败、顺序错误 |
| G: Generation Failures | Hallucination、迎合、冗长、格式错误、置信度失准 |
| S: System Failures | Agent 冲突、交接丢失、编排死锁、Token 耗尽、模型路由错误 |

关键区分能力举例：agent 给了一个不存在的 API endpoint，是 C2（Context Starvation，没给够信息）、R1（Retrieval Miss，信息存在但没被检索到）还是 G1（Hallucination，信息给够了但模型就是编）？能区分这三个，就能高效修复而不是乱调 prompt 碰运气。

---

### Pillar 3: Context Engineering（上下文工程）

地位：日常工作的主要内容之一，决定 agent 的信息输入质量。

核心能力：设计知识的组织方式和注入策略，让 agent 在生成时看到正确的、足够的、不过多的信息。

**三层能力：**

**Prompt Architecture。** 系统 prompt 的分层设计：always-load（核心规则）、on-demand（按需加载的 skill）、per-query dynamic（基于查询动态注入的 memory/knowledge）。这不是写 prompt 的能力，是设计 prompt 加载策略的能力。context-infrastructure 的 CLAUDE.md → rules/ → skills/ 三层结构就是一个 prompt architecture 实例。

**Tool Schema Design。** agent 工具定义的质量直接决定调用正确率。参数命名是否清晰、description 是否准确描述使用场景、返回值格式是否便于 agent 解析。本质是 API design，但消费者从人变成了 LLM。

**Knowledge Routing。** 知识库的组织和检索策略。小规模：手动路由（WORKSPACE.md 式的目录索引）。大规模：RAG（chunking 策略、embedding 模型选择、hybrid search、reranking）。核心判断力：什么时候手动路由够用，什么时候必须上 RAG。信号是"我不知道该让 agent 读哪个文件"。

**手动路由 vs RAG 的分界：**
- 手动路由 = compile-time context injection（人在 query 前决定读什么）
- RAG = runtime context injection（系统在 query 时自动选择读什么）
- RAG 解决的是 scale 问题，不是 capability 问题。知识库小到能放进 context window、路由确定性高时，手动路由更好。

---

### Pillar 4: Agent Architecture（系统设计）

地位：日常工作的主要内容之一，决定 agent 系统的结构。

核心能力：给定业务需求，设计合理的 agent 拓扑，解释 tradeoff。

**关键设计决策：**

单 agent vs 多 agent。判断标准：任务是否可拆分为独立子任务、是否需要不同能力（不同工具集或不同模型）、context window 是否够用。

编排模式选择：
- Orchestrator pattern：一个主 agent 调度多个子 agent。适合子任务异构、需要动态决策的场景。
- Pipeline pattern：agent 串行处理。适合步骤固定、前一步输出是后一步输入的场景。
- Parallel fan-out：多个 agent 并行执行后汇总。适合子任务独立、需要多视角或加速的场景。

Agent 间 handoff 设计：传递完整 context 还是摘要？谁负责 error handling？子 agent 失败后主 agent 怎么兜底？

状态管理：短期记忆（当前 conversation context）、中期记忆（session 级 memory）、长期记忆（持久化存储），各自适合什么信息、什么时候写入和清理。

---

### Pillar 5: Cost & Latency Optimization（成本与延迟优化）

地位：把 agent 从"能跑"变成"能上生产"的工程能力。

核心能力：理解 token 经济学，在质量、成本、速度三者间做合理 tradeoff。

**三个优化杠杆：**

**模型路由。** 最大的杠杆。什么任务必须用最强模型，什么任务用弱模型就够。路由错了要么浪费钱要么质量不达标。实例：Opus 做设计和质量把关、Sonnet 做执行和调研、Haiku 做轻量分类和格式化。

**Token 经济学。** 任务成本 = input tokens + output tokens + tool call overhead。优化方向：减少不必要的 context（只给相关段落而非整个文件）、减少无效 tool call（做一次对的比试三次错的便宜）、缓存重复查询结果。

**Latency 结构分析。** 任务延迟 = 模型推理时间 + 工具调用时间 + 编排开销。瓶颈通常在工具调用的串行等待。可并行的 tool call 并行执行、可预取的 context 提前加载。

---

### Pillar 6: Safety & Trust Boundary（安全与信任边界）

地位：上生产的门槛。

核心能力：设计 agent 系统的信任模型和权限边界。

**三个层面：**

**执行权限分级。** 哪些操作 agent 可以自主执行，哪些需要 human approval，哪些绝对不能做。原则是"外部行动谨慎，内部行动大胆"。生产系统中更精细：read-only 自动执行、mutating 需要审批、destructive 需要二次确认。

**Prompt Injection 防御。** Agent 从外部系统读取的内容（日志、用户输入、API 响应）都是不可信的。防御手段：输入输出分离（不把 tool output 直接拼进 system prompt）、权限最小化（agent 只能访问完成任务所需的最小资源集）、关键操作的 intent 验证。

**Audit Trail 设计。** 事后可追溯：每一步决策是什么、基于什么信息、产生了什么 side effect。既是 debug 工具，也是合规要求。在金融、医疗、运维领域，"agent 为什么做了这个操作"是必须能回答的问题。

---

## 六柱关系

```
         ┌─────────────┐
         │  Evaluation  │ ← 基础设施，其他五柱都依赖它判断效果
         └──────┬───────┘
                │ 反哺指标
         ┌──────┴───────┐
         │   Failure    │
         │  Taxonomy    │ ← 知识积累，驱动评估维度的精细化
         └──────┬───────┘
        ┌───────┴────────┐
   ┌────┴─────┐    ┌─────┴──────┐
   │ Context  │    │   Agent    │ ← 日常工作的两个主战场
   │Engineering│   │Architecture│
   └────┬─────┘    └─────┬──────┘
        └───────┬────────┘
        ┌───────┴────────┐
   ┌────┴─────┐    ┌─────┴──────┐
   │  Cost &  │    │  Safety &  │ ← 上生产的两道门槛
   │ Latency  │    │   Trust    │
   └──────────┘    └────────────┘
```

Evaluation 是基础设施，没有它其他五个都是在凭感觉优化。Failure Taxonomy 反哺 Evaluation 的指标设计。Context Engineering 和 Agent Architecture 是日常工作的主要内容。Cost 和 Safety 是上生产的门槛。

---

## 类比总结

| 柱子 | 军事类比 | SRE 等价物 |
|---|---|---|
| Evaluation | 战后复盘体系 | SLI/SLO 设计 |
| Failure Taxonomy | 战损分析分类 | Postmortem 知识库 |
| Context Engineering | 情报系统 | 配置管理 + 服务发现 |
| Agent Architecture | 编制设计与指挥链 | 系统设计 |
| Cost & Latency | 后勤补给效率 | 性能优化 |
| Safety & Trust | 军纪与交战规则 | 安全合规 |

---

## 演化计划

这是 v1，基于个人实践和讨论提炼。预期随以下积累持续更新：
- `contexts/agent_failure_cases/` 中的故障案例积累
- 实际 agent 系统的运营经验
- 行业共识的逐步形成（类似 Google SRE Book 对传统 SRE 知识的固化）

---

## 变更日志

| 日期 | 变更 |
|---|---|
| 2026-03-31 | v1 初始版本 |
