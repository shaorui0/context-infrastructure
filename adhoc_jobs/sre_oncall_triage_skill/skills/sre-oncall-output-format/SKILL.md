---
name: sre-oncall-output-format
description: "SRE oncall triage 输出格式：9 个 section（Investigation Plan → 操作命令方案）+ 持久化要求"
---

# Output Format

输出文件路径：`${WORKDIR}/report.md`（由 `sre-oncall-init` Step 4 创建 skeleton，investigation 结束后填充完整内容）

- WORKDIR = `/Users/rshao/work/work-harness/tmp/oncall/<YYYYMMDD_HHMM>_<label>/`
- 文件必须 self-contained，独立可读
- **必须写入文件**：所有分析结果写入 `report.md`，不允许只返回到对话。Write 失败时用 Bash `cat <<'EOF'` fallback。对话中只输出摘要 + 文件路径。

## ⚠️ Command Style（硬约束 — 每次写命令都先看这里）

**所有 kubectl 命令必须使用 cluster alias（`kwestproda`、`keastproda` 等），禁止裸 `kubectl`**。

```
✅ kwestproda get pods -n prod -l app=fp
❌ kubectl get pods -n prod -l app=fp       # 不知道是哪个 cluster，用户还要自己切 context
❌ kubectl --context=aws-uswest2-prod-a ... # 冗长
```

- 从 alert 抓 `aws-uswest2-prod-a` → 查 `knowledge/references/reference-clusters.md` "Alert Cluster Name → Alias" 表 → 拿到 alias `kwestproda` → 写到命令里
- 如果 alert 的 cluster 全名不在表里 → **不要降级到 `kubectl`**，而是在 report Internal Notes 里标 `cluster_alias_unknown: <full_name>`，并要求用户补 alias 到 .zshrc + reference-clusters.md
- 例外：不依赖集群的命令（`aws cli`、`helm repo list`）可以不带 alias
- 工具侧 alias（`awsf`、`awsssh`）参见 `reference-aws-cli.md` — 同样优先用 alias 而非原始 `aws ec2 describe-instances ...`

## 输出必须满足的条件

不规定步骤顺序，只规定终态：

- Investigation Scope 声明了 cluster / services / tools / out_of_scope
- 如果存在匹配的历史 case，在 Historical Pattern Matches 中引用
- 如果存在匹配的 debug tree，investigation log 包含完整的 step execution
- 所有 conclusion 有 evidence chain 支撑
- Investigation plan 在第一次 MCP 查询前已写入

## ⚠️ Finding Confidence Rule（quote-or-suppress）

每条 **Root cause / Symptom / Recommendation / Hypothesis 结论** 写进 `report.md` 前必须满足下列**至少一项**，否则 confidence 强制 ≤ 3 且 Slack 措辞必须降级到 "possibly" / "candidate"：

1. 紧接一行 `> evidence:` 引用具体 PromQL / LogQL / MetricsQL 返回值 + 时间戳
   例：`> evidence: vm__query rate(http_requests_total{status=~"5.."}[1m]) = 14.2/s @ 14:23:18`
2. 紧接一行 `> file:line:` 引用 `knowledge/` 下具体 case 文件 + 行号
   例：`> file:line: knowledge/cases/ch_oom_2025q4.md:42`
3. 紧接一行 `> historical:` 引用 fast-path subagent 返回的具体 case slug
   例：`> historical: case_kafka_lag_westernunion_20260301`
4. 紧接一行 `> user-provided:` 引用用户贴的 kubectl/SQL 输出（必须 quote 关键行）
   例：`> user-provided: "0/3 Running" from kwestproda get pods 14:25:00`

**机制**：
- Section 3 Internal Notes 的 Hypothesis tree 每条 mechanism 必须有 `> evidence:` 标注；无证据的写 `> evidence: none (speculation)` 并打 `confidence: 1`
- Section 2 Slack Response 的 Impact / Current status / Immediate Action **不能引用** confidence ≤ 3 的 finding
- verify.py 增加检查：每个 `Root cause:` / `Symptom:` 行后 3 行内必须出现 `> evidence:` / `> file:line:` / `> historical:` / `> user-provided:` 之一

**反模式**（这些会被 verify 拒）：
- ❌ "Root cause: GC pause caused P99 spike"（无 evidence quote）
- ❌ "Symptom: pods OOMKilled" 没有 metric/log 证据
- ✅ "Root cause hypothesis: GC pause caused P99 spike\n> evidence: vm__query jvm_gc_pause_seconds p99 = 4.2s @ 14:22:30, baseline 0.1s"

---

## Section 0: Investigation Plan（执行前写）

在开始任何 MCP 查询之前，先写出 investigation plan。这是 plan 的持久化：让用户在 agent 执行前就能看到方向，有问题可以提前纠正。

### MCP Queries Planned

| # | Tool | Query / Action | Purpose | Expected Result |
|---|------|---------------|---------|----------------|

### Commands for User to Execute

Agent 无法直接执行的命令（PROD tier kubectl 等），列出来让用户并行去做：

| # | Command | Purpose | Why agent cannot execute |
|---|---------|---------|------------------------|

**规则**：
- Plan 不需要完美，可以在执行过程中更新（在 Investigation Log 的 Decision 列记录变更）
- 但第一次 MCP 查询之前必须有一个初始 plan
- 如果用户提供了 kubectl 输出，将结果记录到 Investigation Log

## Section 1: Investigation Scope

```yaml
cluster: <Cluster N — Name from routing table>
services: [<service names that will be queried>]
namespaces: [<namespace names, or "to-be-discovered" if unknown>]
tools: [<MCP tool prefixes to be used: victoriametrics, grafana, loki_fetch>]
time_window: <start> to <end>
out_of_scope: [<what this investigation will NOT look at>]
```

- Scope 从 routing table + extracted signals 派生
- 如果需要扩展 scope，更新声明并说明原因
- `out_of_scope` 是安全信号：verifier 检查查询不触碰 out_of_scope 项

## Section 2: Slack Response (ready to send)

英文。Oncall reply 使用固定模板：

- **Impact**: 只写已确认的影响；未知写 unknown
- **Current status**: ongoing / recovered / intermittent，带时间窗口
- **Immediate Action**: 最多一个低风险动作，或 "wait and observe"
- **Next steps**: 1-3 个具体的检查或行动
- **Escalation criteria**: 明确的升级条件

**语气**：calm, concise, operational. 不用 "definitely", "clearly", "all users". Root cause 只在有直接证据时才说，用 "consistent with" / "evidence suggests"。

## Section 3: Internal Notes (for oncaller only)

### a) Triage result
`IGNORE_DEV` / `KNOWN_ISSUE` / `NON_ACTIONABLE_NOISE` / `NEEDS_ATTENTION` + 一句话理由

### a1) Conclusion
一句话总结。用 "likely", "possibly", "unclear" 表达不确定性。

### b) Event type
availability / latency / crashloop / dependency / deploy-config / data-queue / infra / other

### c) Hypothesis tree
3-6 个可能原因，每个包含 mechanism + 支持/反驳的证据

### d) Evidence checklist
最小有序的 logs / metrics / events 检查列表

### d1) Next Verification
一个最重要的下一步验证信号

### e) Guardrail check
识别 Slack response 中基于假设的句子，改写为保守语言

### e1) Uncertainty Note
明确说明什么是未知或不确定的

## Section 4: Extracted Signals

从原始告警文本提取，不推断。参考 `facets/signal_extraction.md`。

字段：alertname, severity, cluster, client, namespace, pod, container, service, time_window, raw_labels, missing_fields

## Section 5: Links (Ready / Templates / Lookups)

参考文件：
- `knowledge/references/reference-link_templates.md`
- `knowledge/references/reference-grafana_dashboards.md`
- `knowledge/references/reference-clients.md` + `reference-clusters.md`

规则：
- 参数完整 → Ready URL（可点击）
- 参数缺失 → Template URL（`{placeholder}`）+ missing list
- 缺失参数可通过 metrics 发现 → Lookups（MetricsQL + VMUI deep-link）
- namespace/pod 缺失时自动运行 `vm_lookup.py`
- **时间参数精度**：Grafana link 必须使用精确 epoch_ms（`from=<epoch_ms>&to=<epoch_ms>`），不使用 `from=now-6h&to=now` 等相对时间。时间窗口 = event_ts ± 3min（首轮）或 ± 30min（趋势）

## Section 6: Investigation Log（实时写入）

**关键要求：每完成一个查询就立即写入一行，不要等结束后回填。**

覆盖所有查询（debug tree 步骤 + 自由查询 + 用户提供的 kubectl 输出），不只是 debug tree。

| Step | Tool | Query | Result | Interpretation | Decision | Timestamp |
|------|------|-------|--------|----------------|----------|-----------|
| 1 | `mcp__victoriametrics__rules` | `rule_names=[...]` | health=ok | Rule healthy | → 查 series 确认 label 可用 | 14:23:05 |
| 2 | `mcp__victoriametrics__series` | `match="..."` | status_code exists | Can disaggregate | → 按 status_code 拆分查询 | 14:23:18 |
| 3 | user-provided | `kwestproda get pods -n prod` | 3/3 Running | All pods healthy | → 排除 pod 层面问题，转查 ingress | 14:25:00 |

**Decision 字段**：记录"基于这个结果，下一步做什么"。这是 plan 的实时更新版。

**Debug tree 路径**：
- 输出 "**Debug tree**: `{tree_file}`" 
- 执行每个 step，按 branch logic 决定走向
- 在 terminal state（CONCLUSION / ESCALATE / MANUAL）停止
- 工具调用失败按 on_error 处理（RETRY_ONCE → MARK_UNKNOWN → FALLBACK_QUERY → ESCALATE）

**无 debug tree 路径**：
- 生成 facets-based checklist
- 每项：What / Where / How / Expected evidence / Notes

## Section 7: Historical Pattern Matches (optional)

- Routing cluster
- Matched case family + 为什么匹配
- Related knowledge 文件（带相对路径）
- Suggested investigation path

## Section 8: 操作命令方案（中文）

### 诊断命令（只读，可直接执行）

| # | 命令 | 目的 | 预期输出 |
|---|------|------|---------|

### 修复命令（需人工确认后执行）

| # | 命令 | 目的 | 风险评估 | 回滚方案 |
|---|------|------|---------|---------|

### 命令说明

逐条解释：为什么执行、执行顺序、观察点、升级条件

**规则**：
- 诊断命令标记为"可直接执行"
- 修复命令标记为"需人工确认"，包含风险评估和回滚方案
- 使用 investigation 中获取的真实 namespace/pod/service 名称
- 缺失参数用 `<placeholder>` 标记并说明获取方式
- 不生成破坏性命令除非 investigation 明确证明必要
- **所有 kubectl 命令使用 cluster alias**（见本 skill 开头的 "⚠️ Command Style" 节）— 用 `kwestproda` 不是 `kubectl`；alert cluster 全名 → alias 映射见 `knowledge/references/reference-clusters.md` 顶部表
- 所有 AWS CLI 命令优先用 DV 内部 helper（`awsf`、`awsssh`）— 见 `reference-aws-cli.md`
