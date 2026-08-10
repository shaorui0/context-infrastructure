---
name: sre-oncall-acceptance-criteria
description: "SRE oncall triage 验收标准：8 条收敛条件，定义 investigation 的终态"
---

# Acceptance Criteria

任务完成的定义。Agent 从第一步就应该知道终态长什么样。

## 收敛条件

以下条件全部满足，investigation 才算完成：

1. **`${WORKDIR}/report.md` 文件**存在且包含全部 required sections（Investigation Plan, Scope, Slack Response, Internal Notes, Extracted Signals, Links, Investigation Log, 操作命令方案）。分析结果必须写入此文件，不允许只返回到对话。
2. **verify.py** exit code = 0（PASS）或 1（WARN）
3. 每个 **conclusion** 有对应的 evidence chain（不为空）
4. **Slack response** 无 assertion pattern violation（no "root cause is", "definitely", "all users" 等）
5. 所有 MCP 查询结果记录在 **investigation log** 中（不只是 debug tree 步骤，包括所有自由查询）
6. **Investigation plan** 在第一次 MCP 查询之前已写入输出文件
7. Investigation log 的每一行都有 **Decision** 字段（基于这个结果，下一步做什么）
8. Investigation log 是**实时写入**的（查一个写一个），不是结束后回填

## 🛑 Iron Laws（任何一条违反 = investigation 未完成）

### Iron Law 1: No conclusion without root cause hypothesis

Slack response（Section 2）**不能发送**当 `plan.md` 的 `root_cause_hypothesis:` 字段为空。

- "Need more time, still investigating" 不是 conclusion，可以发
- "Likely caused by X" 是 conclusion 类语句 → 必须先在 plan.md 写下 hypothesis
- "Impact: unknown, status: ongoing" 是事实陈述，不是 conclusion，可以发

### Iron Law 2: 3-strike escalation rule

每条 hypothesis 提出后立即在 `plan.md` 的 `hypothesis_log` 写一行：

```yaml
hypothesis_log:
  - ts: "14:23:18"
    hypothesis: "GC pause caused P99 spike"
    test: "vm__query jvm_gc_pause_seconds p99 @14:22"
    result: "✗"  # ✓ confirmed / ✗ refuted / ? inconclusive
  - ts: "14:25:42"
    hypothesis: "Kafka consumer lag"
    test: "vm__query kafka_consumer_lag @14:22"
    result: "✗"
```

**累计 3 个 ✗ 后必须**（按顺序执行）：
1. **停止当前调查路径**，不继续提新 hypothesis
2. 在 `plan.md` 顶部写 `escalation: <one-line reason>`
3. 在 Slack 主动发："need second opinion, root cause unclear after N hypotheses tested" + 列出已排除的方向
4. 或调起 `/codex challenge` subagent 派 GPT 验证已排除假设是否真的排除

**例外**：Quick check 模式（`/sre-oncall-quick-check`）不算 strike，只 full triage 计数。

### Iron Law 3: Phase access boundary（与 Phase Lock 联动）

`plan.md` 的 `phase:` 字段决定当前可读资源（见 `sre-oncall-init` Step 2 的 phase 定义）：

- **phase: A**（调查者）→ 禁 Read `runbooks/`、`historial_operations/`、deploy history
- **phase: B**（决策者）→ 解锁 `knowledge/cases/` 和 deploy diff，仍禁 runbook 实际命令体
- **phase: C**（操作员）→ 解锁全部 runbook + `# INTENT:` 命令模板

切换 phase 必须满足前置条件（见 init Step 2）。违反 = Iron Law 3 违反。

## 不约束过程

以上 Iron Laws 约束的是终态边界，不是过程顺序。Agent 可以用任何顺序到达终态：先查 metrics 再做 case matching，或反过来，或并行——只要最终输出满足全部条件，且过程中没违反 Iron Laws。

## 自动验证

verify.py 检查条件 1-5、Iron Law 1（hypothesis 字段非空）、Iron Law 2（hypothesis_log ✗ 计数 < 3 或有 escalation 字段）、Iron Law 3（phase 字段存在且与 Read 历史匹配）。条件 6-8 仍依赖 agent 自律。
