# Skill: Agent 故障分类学（Agent Failure Taxonomy）

## 元数据

- **类型**: Workflow
- **适用场景**: Agent 产出质量不达标时，系统性记录、分类、命名故障模式
- **创建日期**: 2026-03-31
- **来源**: RAG/Agent Ops 核心能力讨论中提炼

---

## Why

传统 SRE 的知识体系（cascading failure, split brain, thundering herd）是从几十年的 postmortem 中归纳出来的。Agent Ops 领域还没有这样的共识词汇。这个 skill 的目标：通过持续积累故障案例，逐步建立你自己的 agent failure taxonomy，让"agent 怎么会出错"从模糊直觉变成可检索、可教学、可面试的硬知识。

---

## When to Use

- Agent 给出了明显不对的结果（不是"不够好"，是"错了"或"废了"）
- 你花了时间排查一个 agent 行为问题，找到了根因
- 你发现某类 agent 失败反复出现，值得命名

不需要每次都记。只记有命名价值的，即：你下次遇到同类问题时，能靠这个名字一秒定位。

---

## 故障分类体系（v1）

六大类，每类下有具体故障模式。这个分类本身会随积累演化。

### C: Context Failures（上下文故障）

agent 看到的信息有问题，导致输出偏离。

| ID | 名称 | 描述 |
|----|------|------|
| C1 | **Context Overflow** | 塞了太多信息，关键内容被淹没，模型抓不住重点 |
| C2 | **Context Starvation** | 关键信息没给够，模型被迫猜测或 hallucinate |
| C3 | **Stale Context** | 给的信息是过期的（代码已改、状态已变），模型基于旧世界做决策 |
| C4 | **Context Poisoning** | 上下文中混入了误导性信息（错误的注释、过时的文档、prompt injection） |
| C5 | **Wrong Granularity** | 该给摘要时给了原文，该给原文时给了摘要 |

### R: Retrieval Failures（检索故障）

RAG 或知识路由选错了内容。

| ID | 名称 | 描述 |
|----|------|------|
| R1 | **Retrieval Miss** | 相关知识存在但没被检索到（embedding 相似度不够、关键词不匹配） |
| R2 | **Retrieval Noise** | 检索回来的内容相关度低，干扰了生成质量 |
| R3 | **Routing Error** | 手动知识路由指向了错误的文件/skill |

### T: Tool Use Failures（工具调用故障）

agent 在使用工具时出错。

| ID | 名称 | 描述 |
|----|------|------|
| T1 | **Tool Misselection** | 选了错误的工具（该用 grep 时用了 glob，该查日志时查了 metrics） |
| T2 | **Parameter Hallucination** | 工具参数编造（不存在的文件路径、错误的 API 字段） |
| T3 | **Result Misinterpretation** | 工具返回了正确结果，但 agent 解读错了 |
| T4 | **Tool Loop** | 反复调用同一工具期望不同结果，陷入死循环 |
| T5 | **Cascading Tool Error** | 一个工具调用失败，后续步骤基于错误结果继续执行 |

### P: Planning Failures（规划故障）

agent 的任务分解或执行策略有问题。

| ID | 名称 | 描述 |
|----|------|------|
| P1 | **Goal Drift** | 执行过程中偏离了原始目标，做了很多正确但无关的事 |
| P2 | **Premature Commitment** | 过早锁定方案，没有探索替代路径 |
| P3 | **Scope Creep** | 自行扩大任务范围（修 bug 时顺手重构，改一个文件时改了十个） |
| P4 | **Decomposition Failure** | 任务拆分粒度不对（太粗无法执行，太细丢失全局视角） |
| P5 | **Sequencing Error** | 步骤顺序错误（先改代码后读需求，先部署后测试） |

### G: Generation Failures（生成故障）

模型输出本身的质量问题。

| ID | 名称 | 描述 |
|----|------|------|
| G1 | **Hallucination** | 编造事实（不存在的 API、错误的语法、虚构的引用） |
| G2 | **Sycophancy** | 迎合用户的错误前提，不纠正反而顺着说 |
| G3 | **Verbosity Bloat** | 输出过于冗长，关键信息密度极低 |
| G4 | **Format Mismatch** | 输出格式不符合要求（要 JSON 给了 YAML，要代码给了说明） |
| G5 | **Confidence Miscalibration** | 对不确定的事情表现得很确定，或对确定的事情过度 hedge |

### S: System Failures（系统级故障）

不是单个 agent 的问题，是多 agent 协作或系统层面的问题。

| ID | 名称 | 描述 |
|----|------|------|
| S1 | **Agent Collision** | 多个 agent 同时修改同一资源，产生冲突 |
| S2 | **Information Loss at Handoff** | agent 之间交接时丢失关键上下文 |
| S3 | **Orchestration Deadlock** | 多 agent 互相等待，系统停滞 |
| S4 | **Token Budget Exhaustion** | context window 用尽，关键信息被截断 |
| S5 | **Model Routing Mismatch** | 任务派给了能力不匹配的模型（用 Haiku 做架构设计） |

---

## 记录模板

每条故障记录存放在 `contexts/agent_failure_cases/` 下，文件名格式：`<ID>_<日期>_<简述>.md`

例：`T2_20260331_kubectl_nonexistent_namespace.md`

```markdown
# <ID>: <故障名称> — <一句话描述>

- **日期**: YYYY-MM-DD
- **分类**: <C/R/T/P/G/S> — <具体 ID 和名称>
- **严重度**: low / medium / high / critical
- **agent 类型**: Claude Code / sub-agent / cron agent / 其他
- **模型**: opus / sonnet / haiku / gemini

## 现象

agent 做了什么，输出了什么，哪里不对。

## 根因

为什么会这样。追到最底层的原因。

## 触发条件

什么条件下容易复现这个问题。

## 修复/预防

这次怎么解决的，以后怎么避免。

## 启发

这个 case 对 agent 设计、prompt 设计、或工作流设计有什么启发。
```

---

## 执行步骤

### 遇到故障时

1. 判断是否值得记录（标准：你觉得这个故障有名字，或者你见过类似的不止一次）
2. 对照分类体系，找到最匹配的 ID
3. 如果现有分类不覆盖，先记录，再考虑是否需要扩展分类
4. 用模板写一条记录，存到 `contexts/agent_failure_cases/`
5. 如果发现新的故障模式值得命名，更新本文件的分类表

### 定期回顾（建议月度）

1. 扫描 `contexts/agent_failure_cases/` 下的所有记录
2. 统计各类别频次，识别高频故障模式
3. 高频模式 → 考虑写成 bestpractice 或更新 prompt/workflow 来预防
4. 更新分类体系（合并、拆分、新增）

---

## 与其他 Skill 的关系

- 配合 `bestpractice_ai_debugging_diagnosis.md`：debugging 决策树用于定位问题，本 skill 用于分类和积累
- 配合 `workflow_parallel_subagents.md`：S 类（系统级故障）多出现在多 agent 场景
- 配合 `bestpractice_ai_programming_mindset.md`：很多 C 类和 P 类故障的根因是人类侧的问题定义不清

---

## 演化原则

这个分类体系是 v1，预期会随积累演化。演化规则：

- 某个 ID 下积累了 5+ cases 且呈现明显子类 → 拆分
- 两个 ID 的 cases 高度重叠 → 合并
- 发现全新的故障模式 → 新增 ID，先放到最接近的大类下
- 每季度审视一次分类体系是否仍然 MECE

---

## 变更日志

| 日期 | 变更 |
|------|------|
| 2026-03-31 | v1 初始版本，6 大类 25 个故障模式 |
