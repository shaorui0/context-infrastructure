# K8s SRE Agent 可控性模型蒸馏

**Date**: 2026-03-30
**Source**: ChatGPT 对话分析 + 结构化梳理

## Key Insights

- **SRE 和 Agentic AI 不是类比，是同构。** 两者共享同一个控制论底座：不可靠组件构建可靠系统。区别仅在于对象从"系统行为"变成"决策过程"。这意味着 SRE 经验可以直接平移，而不是"跨界学习"。

- **Agent 的本质身份是"概率性 controller"。** K8s controller 是确定性的，所以不需要 guardrail；Agent 是概率性的，所以 Policy 层（admission controller 等价物）是生产级的硬性前提，不是可选项。

- **K8s 映射的精确度比想象的更高。** Prompt=spec（模糊版），Skill=controller（不是 function call，是带收敛逻辑的控制单元），Tool call=kubectl（一次性、无状态），Agent loop=reconciliation loop。这套映射可以直接用于系统设计和面试表达。

- **"乱来"的精确工程定义：行为偏离目标 + 违反约束 + 不可收敛。** 对应的控制手段分五维：限空间（RBAC）、限过程（plan validation）、限结果（invariant check）、限影响（blast radius）、限节奏（rate limit）。

- **框架地位下降的根本原因：框架从"能力本身"变成"Agent 编排的执行层"。** 面试中如果被问框架选型，正确回答是：Tool 层复用框架，Policy 层和 Control Loop 必须自己设计——没有现成方案能满足生产级的 verify + rollback 需求。

- **工程师价值的重新定位：从"构建系统"到"定义约束空间和收敛规则"。** 只要 trade-off 存在（autonomy vs safety, efficiency vs reliability），就需要人来决定偏向哪边以及何时调整。这件事 AI 做不了，因为它缺乏业务上下文和风险偏好。

## Open Questions

- Kubernetes-native Agent Controller 的最小实现是什么样的？CRD（AgentTask）+ Controller + Policy Engine 的具体代码架构还没有落地。
- "认知可观测性"（Cognitive Observability）的 trace 标准怎么定义？现有的 OpenTelemetry 模型能不能直接扩展，还是需要全新的 schema？
- Agent SLO 怎么定义才有意义？task success rate 和 convergence time 是否足够，还是需要更细粒度的指标（比如 plan quality score、rollback frequency）？
- 从 demo 到生产的四阶段路径（工具化→沙箱自主化→Policy+Obs 完善→受限 prod 自主化），每个阶段的 exit criteria 是什么？

## Concrete Artifacts

### 三支柱记忆锚点

> **限制它、看见它、让它回正。**

### 面试核心表达（15秒版）

> 我把 SRE 的核心从"系统可靠性"抽象成"控制不确定系统的能力"，然后把这个模型直接应用到 Agent。LLM 只是一个不可靠组件，关键不是让它永远正确，而是让它出错时仍然可控、可见、可收敛。

### 五层工程架构

```
Tool Layer（执行）→ Policy Layer（拦截）→ Control Loop（核心）→ State Layer（记忆）→ Observability Layer（追责）
```

### 主题树型结构

```
控制不确定系统的能力
├─ 看见它（Observability）
│   ├─ plan trace
│   ├─ action log
│   └─ decision rationale
├─ 限制它（Controllability）
│   ├─ 限空间：RBAC / allowlist / env isolation
│   ├─ 限过程：plan validation / dry-run
│   ├─ 限结果：invariant / post-check
│   ├─ 限影响：blast radius / rollback
│   └─ 限节奏：rate limit / action budget
└─ 让它回正（Convergence）
    ├─ 偏差检测：state vs goal diff
    ├─ 可验证动作：act 后必须 verify
    ├─ 回滚机制：checkpoint / undo
    └─ 持续循环：observe→plan→act→verify→loop
```
