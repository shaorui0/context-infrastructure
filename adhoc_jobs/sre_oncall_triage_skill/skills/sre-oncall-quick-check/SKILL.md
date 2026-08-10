---
name: sre-oncall-quick-check
description: "快速态势感知：并行 fan-out 收集事实基座，不执行完整 debug tree。用于主 session 已有上下文时的轻量查询，或 full triage 的 Phase 0 前置步骤。"
---

# SRE Oncall Quick Check

## When to Use

- 用户已经在和 agent 讨论某个服务，想快速查一眼现状
- Full triage 太重，只需要一个事实基座
- 作为 full triage 的 Phase 0 前置（并行铺开事实后再 routing）
- 用户明确说 "quick check" / "快查" / "先看一眼" / "简单查一下"

## When NOT to Use

- 需要给出根因假设和操作命令 → 走 full triage
- 需要写入知识库 / 沉淀 case → 走 full triage
- 需要 verify.py 验证 → quick-check 不产生完整 report.md
- 需要多假设深度调查 → 走 full triage

## 核心设计：Fan-out Parallel Collection

不是先 routing 再查，是并行铺开事实基座再做判断。

**关键原则**：
- Phase 2 的 5 个 sub-agent 必须 `run_in_background=true` 并发启动，不是顺序调用
- 主 session 只做信号提取 + 汇总综合，不直接跑 MCP 查询
- 每个 sub-agent 返回简洁 bullet（3-5 行），不返回原始数据
- 总 wall-clock 目标 < 90s

## Phase 1: Minimal Signal Extraction（< 10s）

从输入中提取：
- **alertname** / 主题词
- **cluster** / **namespace** / **service**
- **event_ts**（告警时间戳，如有）
- 2-3 个 keywords（如 P99, OOMKilled, connection refused）

**Missing Field Gate**：如果 cluster / namespace / service 缺失 → 停下问用户，不猜测。

## Phase 2: Parallel Fan-out（5 个 sub-agent 并行，< 60s）

5 个 sub-agent 同时启动：

### Sub-agent 1: Current State

```
Agent(
  subagent_type="general-purpose",
  model="sonnet",
  run_in_background=true,
  description="current-state",
  prompt="""
  查服务当前状态（namespace={ns}, service={svc}, event_ts={ts}）：

  1. Pod phase 分布：mcp__victoriametrics__query
     kube_pod_status_phase{namespace="${ns}", pod=~"${svc}.*"}

  2. 关键指标 last 5min（event_ts ± 3min）：
     - QPS: rate(http_requests_total{service="${svc}"}[1m])
     - Error rate: rate(http_requests_total{service="${svc}", status=~"5.."}[1m])
     - P99 latency: histogram_quantile(0.99, ...)

  返回格式（不超过 5 行 bullet）：
  - Pod state: {Running}/{Pending}/{CrashLoop} counts
  - QPS: {value}
  - Error rate: {value}
  - P99: {value}
  - UNKNOWN 字段标 UNKNOWN，不猜
  """
)
```

### Sub-agent 2: Recent Changes

```
Agent(
  subagent_type="general-purpose",
  model="sonnet",
  run_in_background=true,
  description="recent-changes",
  prompt="""
  查最近 2h 变更（namespace={ns}, service={svc}）：

  1. Deployment restart / generation 变化
  2. Image tag / digest 变化
  3. ConfigMap / Secret 变化时间戳

  返回（不超过 5 行）：
  - Last deploy: {timestamp} — {image tag}
  - Config changes: {count} in last 2h
  - 如果没变化：No changes in last 2h
  """
)
```

### Sub-agent 3: Historical Context

```
Agent(
  subagent_type="general-purpose",
  model="sonnet",
  run_in_background=true,
  description="historical-context",
  prompt="""
  查历史上下文：

  1. Grep knowledge/cases/ frontmatter tags/summary 匹配 alertname="${alertname}" 或关键词
  2. 过去 24h 相同告警触发频次（VM ALERTS metric）
  3. Best match case 的 first_action

  返回（不超过 5 行）：
  - Best match case: {filename} — {summary}
  - first_action: {from case frontmatter}
  - 24h frequency: {count} firings
  - No match → 明确说 No historical match
  """
)
```

### Sub-agent 4: Correlated Alerts

```
Agent(
  subagent_type="general-purpose",
  model="sonnet",
  run_in_background=true,
  description="correlated-alerts",
  prompt="""
  查同时间窗其他告警（event_ts ± 10min）：

  1. 同 cluster 其他 firing alerts：ALERTS{cluster="${cluster}", alertstate="firing"}
  2. 同 namespace 其他 service 异常

  返回（不超过 5 行 bullet）：
  - Other firing alerts in cluster: {list top 3}
  - Same-namespace anomalies: {list}
  - 无相关 → 明确说 No correlated signals
  """
)
```

### Sub-agent 5: Topology Snapshot

```
Agent(
  subagent_type="general-purpose",
  model="sonnet",
  run_in_background=true,
  description="topology",
  prompt="""
  查上下游依赖（namespace={ns}, service={svc}）：

  1. 同 namespace 直接依赖的其他 service（service discovery / DNS）
  2. 上下游服务的错误率和延迟

  返回（不超过 5 行）：
  - Upstream services: {list} — status
  - Downstream services: {list} — status
  - 任何 cascading failure 迹象
  """
)
```

**并发执行**：所有 5 个 sub-agent 用 `run_in_background=true` 同时启动，**不要串行等待**。主 session 继续等待所有返回或超时。

## Phase 2.5: Timeout & Logging Contract

### 超时策略（60s hard ceiling）

Claude Code 的 background agent 没有内置超时机制，主 session 必须自己管理：

1. **启动后立即记录 start_ts**：所有 sub-agent 通过 `run_in_background=true` 启动后，主 session 立刻记录 `start_ts` 到 log.md（见下方 Logging Contract）
2. **每 10s 轮询一次状态**：用 SendMessage 检查 background agent 是否返回
3. **到达 60s 仍未返回**：
   - 将该 sub-agent 的 Result 标为 `UNKNOWN: timeout after 60s`
   - **不 kill**（让它在后台继续跑，日志可追溯）
   - 主 session 继续汇总其他已返回的 sub-agent
4. **部分返回可接受**：5 个中只要返回 ≥3 个即可进入 Phase 3 Synthesis（不足时明确标注「X 维度 UNKNOWN」）
5. **全部超时**：主 session 停下报告「All fan-out sub-agents timed out，建议 full triage 序贯模式」

### Logging Contract（sub-agent 条目必须写入 log.md）

即使 quick-check 默认不写 report.md，如果 Full Triage 以 quick-check 作为 Phase 0 跑，`tmp/oncall/<ts>_<label>/log.md` 必须包含 fan-out sub-agent 的调用记录，供 verify.py 检查并发性。

每个 sub-agent 一行，使用现有 Investigation Log 表格格式：

```markdown
| Step | Action | Tool | Query | Result | Decision | Timestamp |
|------|--------|------|-------|--------|----------|-----------|
| fanout-1 | current-state | Agent(sonnet) | (see skill) | {≤5 行 bullet summary} | inherit to plan.md | 2026-04-18T16:25:03Z |
| fanout-2 | recent-changes | Agent(sonnet) | (see skill) | {≤5 行 bullet summary} | inherit to plan.md | 2026-04-18T16:25:03Z |
| fanout-3 | historical-context | Agent(sonnet) | (see skill) | {≤5 行 bullet summary} | inherit to plan.md | 2026-04-18T16:25:03Z |
| fanout-4 | correlated-alerts | Agent(sonnet) | (see skill) | {≤5 行 bullet summary} | inherit to plan.md | 2026-04-18T16:25:03Z |
| fanout-5 | topology | Agent(sonnet) | (see skill) | {≤5 行 bullet summary} | inherit to plan.md | 2026-04-18T16:25:04Z |
```

**关键字段**：
- `Step`: 必须以 `fanout-` 开头（verify.py 用前缀识别 fan-out 行）
- `Action`: 5 个固定 sub-agent 名称之一（current-state / recent-changes / historical-context / correlated-alerts / topology）
- `Timestamp`: ISO8601 格式的 **启动时间**（不是返回时间）
- **5 行的 Timestamp 相邻差值应 ≤ 5s**，否则 verify.py `check_fan_out_parallelism` 会 WARN

超时的 sub-agent 仍要写入一行，Result 字段填 `UNKNOWN: timeout after 60s`。

## Phase 3: Synthesis（< 30s）

汇总 5 个 sub-agent 的返回，直接在对话中输出简洁 situational awareness：

```markdown
## Quick Check Summary

**Signal**: {alertname} @ {cluster}/{ns}/{svc}, event_ts={ts}

### Current State
- {from sub-agent 1}

### Recent Changes
- {from sub-agent 2}

### Historical Context
- {from sub-agent 3}

### Correlated Signals
- {from sub-agent 4}

### Topology
- {from sub-agent 5}

### Routing Hint（可选）
{如果事实基座明确指向某个故障域}
- 建议 Layer 1 skill: `/workflow-oncall-{type}`
- 或：信号不明确，建议走 full triage

### Next Step
选择：
(A) 继续某个维度深挖（告诉 agent 方向）
(B) 升级到 full triage（`/sre_oncall_triage` + 本次 quick-check 基座）
(C) 止步（信息足够）
```

## Acceptance Criteria（终态）

1. Phase 2 所有 sub-agent **并发启动**（`run_in_background=true`，不是顺序）
2. 每个 sub-agent 的 start_ts 记录到 log.md，5 个 Timestamp 相邻差值 ≤ 5s（verify.py 可检）
3. Phase 2 总耗时 ≤ 60s（超时的 sub-agent 标 `UNKNOWN: timeout after 60s`，其他正常继续）
4. 部分返回可接受：≥3 个 sub-agent 返回即可进入 Synthesis；全部超时则停下报告
5. 输出包含 5 个 section（Current State / Recent Changes / Historical Context / Correlated Signals / Topology）
6. 每个 section 内容 ≤ 5 行 bullet（sub-agent Result 字段 ≤ 500 字符，无代码块、无 JSON、无连续 >5 行数字序列）
7. **不生成操作命令方案**
8. 如果作为独立使用：**不创建 tmp/oncall/** 完整目录结构；**不运行 verify.py**；**不触发 compound learning**
9. 如果作为 Full Triage 的 Phase 0：log.md 必须包含 fan-out 行（Step 以 `fanout-` 开头，详见 Logging Contract）

## 输出去向

默认**只输出到对话**，不产生 tmp/oncall/ 目录。

如果用户明确说「保存这个 quick check」，写入：
```
tmp/oncall/<YYYYMMDD_HHMM>_quickcheck_<label>/summary.md
```
只写 summary section，不写完整 report.md schema。

## 与 Full Triage 的三种关系

### 1. 独立使用（默认）
用户显式调用 `/sre-oncall-quick-check`，用完即止。不进入 full triage 流程。

### 2. 作为 Full Triage 的 Phase 0
Agent 被调用时先跑 quick-check 收集事实基座，再进入 Layer 0 init。Plan.md 的 Routing Decision 直接基于 quick-check 结果而不是从零路由。

### 3. 升级路径
Quick-check 完成后，用户说「升级到 full」→ agent 进入 Layer 0，已有事实基座作为 plan.md 的 Planned Queries 预填充，避免重复查询。

## 反模式

- ❌ Sub-agent 返回整块 log / 指标时间序列 — 应该返回摘要 bullet
- ❌ 主 session 自己跑 MCP 查询 — 应该全部 delegate 到 sub-agent
- ❌ Sub-agent 之间有依赖（A 的输出作为 B 的输入） — 破坏并行性
- ❌ 输出操作命令（kubectl scale ...） — 这是 full triage 的职责
- ❌ 超过 5 个 sub-agent — attention cost 超过并行收益
