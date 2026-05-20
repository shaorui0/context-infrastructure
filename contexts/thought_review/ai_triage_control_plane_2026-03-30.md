# AI Triage Control Plane: From Theory to Structured Artifacts

Date: 2026-03-27 ~ 2026-03-30
Trigger: Garry Tan "Boil the Ocean" → 什么是值得煮沸的湖

---

## Key Insights

- **恐惧 ∝ 1/野心**：不是 AI 太强你该怕，是你的目标太小所以 AI 对你是威胁。这不是励志，是逻辑——如果你的计划是"继续做现在做的事"，那更快更便宜的机器当然让你多余。

- **Agent 的工程挑战是 controllability，不是 capability**：市场在追模型能力，但生产系统买单的是可审计、可回放、可中断。这是 SRE 思维迁移到 agent 设计的核心 leverage。

- **Verifier 检查的不是"答案对不对"，而是"evidence chain 完不完整"**：一个对的答案如果没有证据支撑，在生产环境里和错的答案一样不可接受。这区分了 demo 和 infra。

- **Structured Triage Trace 是 case → agent 的桥梁**：人写的 incident case 是叙事；agent 需要的是 Signal → Routing → Decision Trace → Evidence Chain → Policy → Verifier。这两者之间差一个结构化转换，而不是差一个 fine-tuning。

- **Routing table 从真实 case 长出来，不是凭空设计**：6 个 failure domain cluster 不是分类学练习——每个 cluster 的 routing logic 和 triage policy 都从具体 incident trace 中提取。反过来说：没有 trace 就没有 routing table。

- **Jevons Paradox 需要有人把野心升级才能激活**：效率提升不会自动带来需求扩张，需要 capital/management 主动提高目标。这解释了为什么大多数 AI 落地停在 cost reduction 而不是 value creation。

---

## Open Questions

- **Human gate boundary 随时间怎么移动？** 现在 verifier checklist 全过才能关，但随着 policy 被验证的次数增多，某些 cluster 的 triage 可以逐步变成 auto-close。移动的条件是什么？case 数量？准确率？两者都要？

- **跨 cluster 的级联 triage 怎么处理？** Cluster 6 (change regression) 经常同时触发 Cluster 1, 2, 3。单 cluster policy 能处理当前 case，但跨 cluster 的 orchestrator 还没设计。

- **Verifier 的 minimum viable 实现是什么？** 目前 verifier 是 markdown checklist，人工检查。要变成 agent 可执行的 verifier，需要什么——structured output schema？LLM-as-judge？rule engine？

- **这个系统的 portfolio 展示形态是什么？** 6 个 trace + routing table 证明了 design thinking，但面试或 demo 时需要一个 live loop。Cluster 4 (histogram skew) 全链路可通过 Grafana/VM MCP 跑通——值得做成第一个 demo。

---

## Concrete Artifacts

### 产出文件

```
work-contexts/oncall/cases/
  case-monitoring-alert-delay-histogram-skew.trace.md    ← Cluster 4
  case-clickhouse-connection-refused-troubleshooting.trace.md  ← Cluster 1
  case-kafka-lag-issues.trace.md                         ← Cluster 3
  cluster2-scheduling-node-pressure.trace.md             ← Cluster 2
  cluster5-identity-access.trace.md                      ← Cluster 5
  cluster6-change-management.trace.md                    ← Cluster 6

work-contexts/oncall/agent-routing-table.md              ← orchestrator 决策层
```

### Structured Triage Trace Schema (v0.1)

每个 trace 包含：

1. **Signal** — alert 类型 + failure signature + routing 到哪个 cluster
2. **Routing Logic** — IF/THEN 条件，agent 第一步路由依据
3. **Decision Trace** — 表格：Step → Action → Tool → Observation → Inference → Confidence
4. **Evidence Chain** — root cause + mechanism + supporting evidence + ruled out
5. **Triage Policy** — YAML 格式的可执行策略，IF/THEN/GATE
6. **Verifier Checklist** — close 前的硬门：全过才能关，任何一项失败 → escalate
7. **Blast Radius** — action surface + human gates + rollback path
8. **Pattern Cross-Reference** — cluster rule + anti-patterns + related cases

### 三层架构（面试表述）

```
Orchestrator  — Signal → failure signature → route to cluster policy
Worker        — bounded MCP call, input/output contract, stateless
Verifier      — evidence chain audit, NOT answer correctness
Human Gate    — 不可逆操作前的强制停止点，是设计原语不是补丁
```

### 6 Cluster 记忆钩子

```
1. 哪一跳断了？（Routing — refused vs timeout, hop-by-hop）
2. 为什么调度不上？（Scheduling — requests vs allocatable, placement）
3. 下游堵住了？（Stateful — sink pressure, not source）
4. 信号是真的吗？（False signal — disprove first, then investigate metric）
5. 谁没权限？（Identity — L1→L4, explicit deny wins）
6. 什么变了？（Change — change is the suspect, rollback before root cause）
```

### 面试一句话核心

> "我把 AI agent 可靠性当成控制问题，不是能力问题。工程挑战是 controllability——有界自主、显式失败形状、可验证的推理链——而不是让模型更聪明。"
