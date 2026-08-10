# SRE Oncall Full Triage Pipeline

## 元数据

- **类型**: Workflow
- **适用场景**: 完整 SRE oncall triage 流程，把 Phase Lock + Iron Laws + Subagent Isolation + Quote-the-line 串成 idempotent re-runnable pipeline
- **创建日期**: 2026-05-28
- **设计来源**: `contexts/survey_sessions/gstack_design_philosophy_survey_20260527.md` + `tmp_sre_oncall_upgrade_plan_20260528.md`
- **关系**:
  - 编排（不替代）`/sre-oncall-init` / `/sre-oncall-triage` / `/sre-oncall-output-format` / `/sre-oncall-acceptance-criteria` 等子 skill
  - 与 `/sre-oncall-quick-check` 互斥（quick 模式走另一条路径，不进本 pipeline）

---

## When to Use

- 用户说 `/workflow_oncall_full_triage` 或 "完整 triage" / "正式 triage"
- 接到 P1/P2 alert 且需要持久化 + 多 phase 调查
- 中断后续跑：上一次 session 的 `${WORKDIR}/plan.md` 存在 → 读 `step_*_done` 字段从断点继续

**不适用**：quick check（用 `/sre-oncall-quick-check`）、纯查询（用 `/sre-vm-query` / `/dv_loki_fetch`）

---

## 核心设计

**Idempotent**：每 step 完成在 `plan.md` 写 `step_N_done: <ts>`。重跑时若 `step_N_done` 已存在则跳过——这是 session 断了能续跑的保证（≈ gstack `{branch}-ship-state.yaml` 设计）。

**Phase-locked**：step 1-6 在 Phase A，step 7-9 在 Phase B，step 10-11 在 Phase C。phase 切换有前置条件，违反 = Iron Law 3 触发。

**Subagent-isolated**：主 agent 不直调 raw data MCP，所有 raw query 派 sonnet subagent。

---

## 11-Step Pipeline

### Step 0 — Init（Phase A 起点）

调用 `/sre-oncall-init`：
- 创建 `${WORKDIR}` + plan.md/log.md/report.md/evidence/ skeleton
- Fork fast-path subagent 搜历史 case
- 提取信号、计算时间窗、路由 Layer 1

完成条件：plan.md 顶部 `phase: A` 已写入，`hypothesis_log: []` 已初始化。

写：`step_0_done: <ts>`

---

### Step 1 — Phase A Gate（assert）

读 `plan.md` 确认：
- `phase: A`
- Mode = full（quick 不进本 pipeline）
- 主 agent 当前 session **未 Read 过** `runbooks/` / `historial_operations/`（自检）

不通过 → 报错并停。

写：`step_1_done: <ts>`

---

### Step 2 — Initial Metrics Pull（subagent）

派 sonnet subagent 拉初始指标摘要：

```
Agent(subagent_type="general-purpose", run_in_background=false, prompt="
  查 {cluster}/{service} 在 {time_window} 的核心指标：
  - P99/P95 latency
  - error rate (5xx)
  - request rate (QPS)
  - resource (CPU/mem/pod restart)

  只返回结构化摘要（≤500 token）：
  - 每个指标的 max/min/baseline_ratio/有无 step jump
  - 关键 outlier ts（≤3 个）
  禁止返回原始时序数据。
")
```

主 agent 把摘要写入 `report.md` Section 6（Investigation Log）。

写：`step_2_done: <ts>`

---

### Step 3 — Initial Logs Pull（subagent）

派 sonnet subagent 拉错误日志摘要：

```
Agent(subagent_type="general-purpose", run_in_background=false, prompt="
  查 Loki 日志 {cluster}/{service} 在 {time_window} 的 ERROR/WARN：
  使用 loki_fetch.py（见 /dv_loki_fetch）。
  只返回：
  - 错误总数
  - Top 3 错误 message pattern + 出现次数
  - 最早/最晚的错误时间戳
  - 关键 stack trace ≤3 行 quote
  禁止返回完整日志。
")
```

写：`step_3_done: <ts>`

---

### Step 4 — Hypothesis Generation（主 agent）

基于 step 2-3 摘要，主 agent 写 1-3 个候选 hypothesis 到 `plan.md` 的 `hypothesis_log:`：

```yaml
hypothesis_log:
  - ts: "<now>"
    hypothesis: "<one line>"
    test: "<具体的 PromQL/LogQL/kubectl query>"
    result: "?"  # 待 step 5 验证
```

写：`step_4_done: <ts>`

---

### Step 5 — Hypothesis Verification（subagent loop）

对每个 `result: "?"` 的 hypothesis：
- 派 subagent 跑 `test:` 中指定的 query
- 主 agent 根据 subagent 返回的结构化结果，把 `result:` 改成 `✓` / `✗` / `?`

**3-strike gate**：每次更新后立即检查 `result: ✗` 计数：
- < 3 → 继续，可以加新 hypothesis 回 step 4
- ≥ 3 → **触发 Iron Law 2**：
  - 在 `plan.md` 顶部写 `escalation: <reason>`
  - 在 Slack 主动发 "need second opinion"
  - 可选：派 `/codex challenge` subagent
  - 跳到 Step 11 写 retro

写：`step_5_done: <ts>`（当至少有一条 ✓ 或触发了 escalation）

---

### Step 6 — Phase A → B Transition Gate

前置条件：
- `root_cause_hypothesis:` 非空（取 step 5 中 `✓` 的 hypothesis）
- 至少一条 `result: ✓`

满足 → 修改 `plan.md`：
```yaml
phase: B
phase_transitions:
  - ts: "<now>"
    from: A
    to: B
    reason: "<rebut/confirm details>"
```

不满足 → 停在 Phase A，回 step 4 加 hypothesis。

写：`step_6_done: <ts>`

---

### Step 7 — Historical Case Match（Phase B, subagent）

合并 step 0 fast-path 结果 + 主动派 subagent 在 `knowledge/cases/` 找 best match：

```
Agent(subagent_type="general-purpose", run_in_background=false, prompt="
  在 ~/.claude/skills/sre-oncall-triage/knowledge/cases/ 找匹配 case：
  - root cause: {root_cause_hypothesis}
  - cluster: {cluster}
  - service: {service}

  返回 ≤2 个最相关 case：filename + summary + first_action + 是否引用 runbook slug。
")
```

主 agent 把匹配写入 `report.md` Section 7（Historical Pattern Matches），每条遵守 quote-the-line：`> file:line: knowledge/cases/<file>:<line>`。

写：`step_7_done: <ts>`

---

### Step 8 — Confidence Gate（assert）

读 `report.md`，对每条 Root cause / Symptom / Recommendation 检查：
- 紧接是否有 `> evidence:` / `> file:line:` / `> historical:` / `> user-provided:` 之一
- 无 → confidence 强制 ≤ 3，且 Slack 措辞降级到 "possibly"

可以用 `verify.py` 自动检查（如已实现 Iron Law 检查）。

不通过 → 回填 evidence 或降级措辞。

写：`step_8_done: <ts>`

---

### Step 9 — Phase B → C Transition Gate

前置条件：用户在 Slack 或对话中显式确认根因（"yes proceed" / "go" / "执行" / "approve hypothesis"）。

**不要主动跳到 Phase C。** 必须等用户回应。

满足 → 修改 `plan.md`：
```yaml
phase: C
phase_transitions:
  - ts: "<now>"
    from: B
    to: C
    reason: "user confirmed root cause: ..."
```

写：`step_9_done: <ts>`

---

### Step 10 — Generate Commands（Phase C）

现在 phase=C，解锁 `historial_operations/<runbook>/` 全部内容。主 agent：
- 读对应 runbook
- 生成 `# INTENT: <why>\n<command>` 命令草稿到 `report.md` Section 8（操作命令方案）
- 严格遵守 `/sre-oncall-output-format` 的 alias-first 和 quote-the-line

**Mutation Approval Gate 仍生效**：命令只生成不执行。

写：`step_10_done: <ts>`

---

### Step 11 — Verify + Compound Learning

- 跑 `python3 tools/agent_ops/verify.py ${WORKDIR}/report.md`
- 通过 → 调用 `/sre-oncall-compound-learning` 蒸馏到 `knowledge/`
- 如果触发了 escalation → 写 retro 到 `report.md` 末尾：哪些 hypothesis 错了、为何错、未来 debug tree 怎么改

写：`step_11_done: <ts>`

---

## Resume from Crash

新 session 接手时：

```bash
cat ${WORKDIR}/plan.md | grep "step_.*_done"
```

最大的 N 即为已完成的 step。直接从 step N+1 继续。所有 phase / hypothesis_log / escalation 状态都在 plan.md 里——单文件 grok 完整状态。

---

## Failure Modes & Mitigations

| Failure mode | 触发条件 | 缓解 |
|---|---|---|
| Phase A 偷看 runbook | 主 agent 在 step 1 前已 Read runbook 路径 | step 1 gate 自检 + Iron Law 3 拒绝 |
| Hypothesis 死循环 | 反复提同一类 hypothesis 都 ✗ | step 5 3-strike → escalate |
| Slack 发出无 evidence 结论 | quote-the-line 没贴 | step 8 gate + verify.py |
| Session 断了上下文丢 | context 蒸发 | 单文件 plan.md，新 session cat 即可续 |
| Subagent 返回 token 爆炸 | prompt 没写 ≤500 token 限制 | 每个 subagent prompt 模板必含"只返回 X Y Z，禁止原始数据" |
| 用户没等 phase B 就强推命令 | step 9 被跳过 | gate 不允许 step 10 在 phase=B 执行 |

---

## 设计来源（Why this pipeline exists）

直接对应 4 个 gstack 启示（详见 [survey](../../contexts/survey_sessions/gstack_design_philosophy_survey_20260527.md)）：

| Gstack 启示 | 本 pipeline 落地点 |
|---|---|
| `/investigate` Iron Law: no fix without root cause | Step 9 gate 必须等根因确认 |
| `/investigate` Scope Lock: hypothesis 后限制编辑范围 | Phase A/B/C File Access Boundary |
| `/review` quote-the-line confidence gate | Step 8 + `/sre-oncall-output-format` Finding Confidence Rule |
| `/investigate` 3-strike rule | Step 5 + Iron Law 2 |
| `/ship` idempotent re-runnable + state.yaml handoff | `step_N_done` 字段 + plan.md 单文件 |
| Anthropic context engineering: subagent return condensed summary | Step 2/3/5/7 subagent ≤500 token rule |

**不抄的**：CEO/Designer role / 23 个 slash command / LOC vanity metric。

---

## Acceptance（pipeline 完成条件）

- `step_0_done` 到 `step_11_done` 全部写入（或 step_5 触发 escalation 后直接到 step 11）
- `verify.py` exit 0 或 1
- Iron Law 1-3 全部满足
- 所有 Phase 切换在 `plan.md` 有日志
- `${WORKDIR}/report.md` self-contained 可读
