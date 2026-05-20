# Orchestration Redistribution 与 Harness 分类学

**日期**: 2026-04-17  
**触发**: 对杨博「如何看待 Devin AI」一文的深度调研（[survey report](../survey_sessions/llm_orchestration_transitional_crutch_survey_20260417.md)）  
**类型**: 概念综合（把调研的实证结论提升为可迁移的思考框架）

---

## 这轮对话产生的概念链

起点是一个经验问题（Devin 是否有前途），终点是几条可迁移的认知原则。概念跃迁有五次：

```
实证 survey  →  层次思维作为激活器  →  反向耦合定律
     ↓                                      ↓
Absorption criterion  ←  Cheap/Hard 指标  ←  Harness 七分类
```

---

## 1. 层次思维作为"激活器"

**观察**: 瑞哥提出"层次思维可能是最重要的思维能力"。

**修正**: 它不是最重要的单一能力，而是 **让其他思维能力在复杂系统里生效的前提**。

第一性原理、系统思维、因果推理在简单系统里可以直接用。但面对 AI 栈这样的复杂系统，不先做层次划分就上第一性原理，会混淆不同层级的抽象。**层次思维向横切，第一性原理向下切，两者必须配合。**

杨博的误判就是例证：他没有区分 "KV-cache 架构机制"（单次推理内优化）和 "prefix caching 基础设施"（跨请求复用）。一旦混淆层级，再严密的第一性原理推演都会得出错误结论。

**可迁移原则**: 做复杂系统的判断前，先用层次思维切出清晰的 layer。每一层有自己的语言、约束、失败模式。跨层的论证极易出错。

---

## 2. 反向耦合定律：上层越简单，底层越复杂

**核心**: 易用的 user-facing 抽象，必然由更复杂的底层 infrastructure 支撑。两者 **反向耦合**，不是独立的。

**证据链**:
- SQL 一行查询 ↔ Postgres 查询优化器（博士级复杂度）
- `pip install` ↔ HTTP/2 + TLS + DNS + TCP + IP 完整栈
- `git push` ↔ 分布式一致性 + 冲突检测
- iPhone "It Just Works" ↔ iOS + Secure Enclave + 几千人工程团队
- Claude Code 一个 prompt ↔ 29,000+ 行 harness

**机制** 有四条结构性原因：
1. **用户越多，需求越杂** —— 抽象易用 → 用户量爆炸 → 需求维度爆炸 → 底层必须覆盖所有奇葩 case
2. **失败模式组合爆炸** —— 每多一层抽象，就多一组"是 A 还是 B 还是接口"的排查空间
3. **向下兼容的累积税** —— 上层接口一旦稳定就不能动，底层所有变化都要伪装成"接口不变"
4. **可靠性期望单调递增** —— 基础越"基础"，挂掉越是灾难，可靠性 bar 永远在升

**反直觉的结论**: 如果你的软件"用起来很简单"，不是因为问题简单，而是因为有人替你承担了复杂度。**易用性是一种由底层工程师偿还的 debt。**

→ 提炼为公理 T10 [反向耦合定律](../../rules/axioms/t10_inverse_coupling_law.md)

---

## 3. Cheap 是滞后指标，Hard 是领先指标

**观察**: 瑞哥指出"CRUD 变得非常 cheap，但 harness 仍然很难"。

**推广**:

- **"便宜"是 lagging indicator** —— 意味着 20-40 年基础设施投资的累积，被压缩进了一个 `pip install`。你在消费过去被凝结的复杂度化石燃料。
- **"难"是 leading indicator** —— 意味着当前是文明工程前沿，没有累积的抽象可以站上去，每一家都在重新解决相同的问题。

**时序化的例子**:

| 阶段 | 难度 | 示例时代 |
|------|-----|---------|
| 前沿 | 博士论文级 | Codd 1970s 关系代数 |
| 框架 | 专家领域 | SQL 标准化 1980s |
| 标准 | 多数人可用 | MySQL/Postgres 1990s |
| 基础设施 | 不可见 | Rails/Django 2000s |
| 商品化 | 小时级搭建 | 2020s CRUD |

**推论**: 
- CRUD 今天 cheap = 40 年投资的结果 
- Harness 今天 hard = 下一代的 CRUD 的来源 
- 今天的 hard，就是 2040 年的 `pip install`

**对个人定位的意义**: 
- 押注 cheap 的东西 = 消费过去的复杂度 = 边际价值递减
- 押注 hard 的东西 = 生产未来的复杂度 = 边际价值递增但波动大

→ 提炼为公理 T11 [Cheap 与 Hard 作为文明投资指标](../../rules/axioms/t11_hard_leads_cheap_lags.md)

---

## 4. Harness 七分类法

把 Claude Code 的 29,000 行 harness 拆开，得到七类功能。每一类都有一个"为什么不能被模型吸收"的结构性理由：

| 类别 | 典型功能 | 为什么不可吸收 |
|------|---------|--------------|
| **A. 外部世界接口** | Bash、Read/Write、Git、MCP、IDE | 物理鸿沟：模型产文本不产 syscall |
| **B. 信任边界** | Permission、approval、sandbox、白黑名单 | 架构原理：不能让被审计者当审计员 |
| **C. 跨会话状态** | 会话持久化、Task 跟踪、CLAUDE.md、git state 注入 | 时间维度：状态要超越任何单次 context |
| **D. 多 Agent 协调** | Sub-agent 派发、worktree 隔离、消息路由 | 分布式系统问题，与模型能力正交 |
| **E. 经济管理** | Token budget、prompt caching、model routing | 模型看不到全局成本 |
| **F. 人机界面** | Terminal rendering、diff、hooks、slash commands | Agent 之外的接口，不是推理问题 |
| **G. 工程脚手架** | Schema 验证、工具搜索、重试 | 理论可吸收但目前不划算 |

**关键观察**: A-F 都涉及 "模型之外的东西"——物理、信任、时间、协调、经济、人。G 是唯一 "随成本下降会被吸收" 的类别。

---

## 5. Absorption Criterion（吸收判别准则）

从 harness 七分类中抽出一个判别式：

> **能被压缩成"更好的 next-token-prediction"的能力 → 会被模型吸收**  
> **涉及模型外部世界的能力（物理/信任/时间/协调/经济/人机）→ 会留在 harness**

**已被吸收的证据**（都是纯推理模式）：
- CoT prompting → 推理模型内置推理（Wharton 研究：+2.9% 准确率 / +20-80% 时间成本）
- Output parser / retry loop → Structured Outputs（合规率 35% → 100%）
- Few-shot template → 零样本能力
- ReAct pattern → 原生 function calling
- 显式 DAG 工作流 → extended thinking

**未被吸收的证据**: Harness 七分类里 A-F 没有一个是纯推理问题。

**这个准则可以用于**:
- 判断 AI 基础设施哪些技术会短命，哪些会持久
- 押注技术方向（押持久层，不押易被模型吸收的层）
- 反向检验：如果你在做的事情"可以压缩成更好的提示词模式"，它大概率会被下一代模型消灭

---

## 6. Orchestration 的真实命运：Redistribution 而非 Extinction

杨博的错误不是方向错误，而是 **级别错误**：把"部分 orchestration pattern 被淘汰"升级成了"orchestration 整体消失"。

**实际发生的是三重重新分布**:

1. **吸收进模型权重** —— Cursor Composer 2、Cognition SWE-1.5 通过 RL 把 orchestration 行为烘焙进专用模型。Scaffold 没消失，变成了训练信号。
2. **标准化为协议** —— MCP 从 N×M 集成简化为 N+M。Orchestration 基础设施化（类似 HTTP 之于 web）。
3. **极简化为 thin harness** —— Claude Code 的 ~50 行 agent loop + 29,000 行 infrastructure。心脏变薄，骨架变厚。

**总账**: orchestration 的总量在增加，不是减少。只是位置变了。

---

## 7. 对个人定位的启示

瑞哥的背景（SRE + AI 交叉）正好处在当前 hard 的前沿：

**当前 hard，未来会变 cheap 的领域**:
- Agent observability / cost control / debuggability
- Multi-agent orchestration at production scale
- AI system reliability engineering（= 下一代 SRE）
- Evaluation as measurement system
- Harness engineering for long-running agents

**押注策略**:
- 今天在这些领域做对的事情，就是 2035 年基础常识的来源
- 第一批把它做对的人，会定义这个学科的语言

**避免的陷阱**:
- 不要被"Agent 编排框架"的热潮骗进 LangChain 式的重型编排 —— 那一层正在被 thin harness + 更强模型吃掉
- 不要低估看起来"太底层"的 infra 工作 —— 它是下一代 `pip install` 的母体

---

## 8. 可复用的判断原则（本轮对话的提纯）

1. **做复杂系统判断前，先做层次切分。** 跨层的第一性原理推演极易出错。
2. **上层简单必然伴随底层复杂。** 两者反向耦合，不独立。
3. **便宜是滞后指标，难是领先指标。** 今天的难定义明天的基础设施。
4. **复杂度守恒，但会在抽象层间迁移。** 它从一个层消失时，另一个层必然在变厚。
5. **能压缩成 next-token-prediction 的会被吸收；涉及模型外部世界的留存。**
6. **Orchestration 的形态在分化：一部分进模型权重，一部分变协议，一部分留在 thin harness。** 总量增加。

---

## 关联

- 实证基础: [LLM Orchestration 是否是过渡期拐杖 - Survey](../survey_sessions/llm_orchestration_transitional_crutch_survey_20260417.md)
- 衍生公理:
  - [T10. 反向耦合定律](../../rules/axioms/t10_inverse_coupling_law.md)
  - [T11. Cheap 与 Hard 作为文明投资指标](../../rules/axioms/t11_hard_leads_cheap_lags.md)
- 相关公理:
  - [T01. 基础设施优于组件](../../rules/axioms/t01_infrastructure_over_components.md) — 本文给 T01 提供了机制解释
  - [T05. 认知是资产，代码是消耗品](../../rules/axioms/t05_cognition_asset.md) — 对照组，本文补上了"基础设施"视角
  - [X01. 约束悖论](../../rules/axioms/x01_constraint_paradox.md) — 复杂度守恒定律的另一个表述
  - [T08. 第一性原理方法论设计](../../rules/axioms/t08_first_principles_methodology.md) — 层次思维是第一性原理的激活器
