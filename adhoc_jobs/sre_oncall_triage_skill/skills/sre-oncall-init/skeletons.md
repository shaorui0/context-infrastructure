# Triage File Skeletons

> **按需加载**。仅在 Step 2-4 创建 plan.md / log.md / report.md 时读本文件。这些 skeleton 写一次就够，后续不需要在 context 中保留。

工作目录结构（由 `SKILL.md` Step 1 创建）：

```
tmp/oncall/<YYYYMMDD_HHMM>_<label>/
├── plan.md          # Investigation plan + signals + scope + routing
├── log.md           # Investigation log（实时写入，每查一个写一行）
├── report.md        # 最终输出（Slack response + internal notes + 操作命令方案）
└── evidence/        # Raw query results
```

## plan.md skeleton

```markdown
# Investigation Plan

Created: <YYYY-MM-DD HH:MM:SS>
Alert source: <Slack link or raw text>

## State（Phase Lock + Iron Law fields）

```yaml
phase: A                          # A 调查者 / B 决策者 / C 操作员（见 phase_lock.md）
root_cause_hypothesis: ""         # Iron Law 1: Slack conclusion 前必须填
escalation: ""                    # Iron Law 2: 3 strike 后填 reason
mode: full                        # full | quick
```

## Hypothesis Log（Iron Law 2: 累计 3 个 ✗ 强制 escalate）

```yaml
hypothesis_log: []
# 模板：
#   - ts: "14:23:18"
#     hypothesis: "GC pause caused P99 spike"
#     test: "vm__query jvm_gc_pause_seconds p99 @14:22"
#     result: "✗"   # ✓ confirmed / ✗ refuted / ? inconclusive
```

## Extracted Signals

| Field | Value | Source | Confidence |
|-------|-------|--------|------------|
| alertname | | alert text | |
| severity | | alert text | |
| cluster | | alert text | |
| namespace | | alert text | |
| client | | alert text | |
| service | | alert text | |
| event_ts | | alert text | |
| endpoint | | alert text | |
| raw_value | | alert text | |
| missing_fields | | — | |

## Missing Field Gate

以下字段**必须有值**才能继续。缺失 → 停下问用户：
- [ ] event_ts（没有时间就无法定位窗口）
- [ ] cluster（不知道查哪个集群就不要查）
- [ ] namespace 或 service（至少一个，否则查询没有 label filter）

## Time Window

- event_ts: <epoch_ms>
- query_window: <event_ts - 3min> to <event_ts + 3min>
- query_window_rfc3339: <start> to <end>
- grafana_from: <epoch_ms>
- grafana_to: <epoch_ms>

## Scope

```yaml
cluster:
services: []
namespaces: []
tools: []
time_window:
out_of_scope: []
```

## Routing Decision

- Triage cluster: <from agent-routing-table.md>
- Layer 1 skill: <skill name or "none — use debug tree">
- Debug tree: <if applicable>
- Rationale: <one sentence>

## Planned Queries

| # | Tool | Query | Purpose | Expected Result |
|---|------|-------|---------|-----------------|

## Commands for User to Execute

| # | Command | Purpose | Why agent cannot execute |
|---|---------|---------|------------------------|
```

## log.md skeleton

```markdown
# Investigation Log

Workdir: <WORKDIR path>
Started: <YYYY-MM-DD HH:MM:SS>

| Step | Tool | Query | Result | Interpretation | Decision | Timestamp |
|------|------|-------|--------|----------------|----------|-----------|
```

## report.md skeleton

```markdown
# SRE Oncall Triage Report

Workdir: <WORKDIR path>
Created: <YYYY-MM-DD HH:MM:SS>

## Slack Response

_To be filled after investigation_

## Internal Notes

### Triage Result
### Conclusion
### Event Type
### Hypothesis Tree
### Evidence Checklist
### Uncertainty Note

## 操作命令方案

### 诊断命令（只读）

| # | 命令 | 目的 | 预期输出 |
|---|------|------|---------|

### 修复命令（需人工确认）

| # | 命令 | 目的 | 风险评估 | 回滚方案 |
|---|------|------|---------|---------|
```
