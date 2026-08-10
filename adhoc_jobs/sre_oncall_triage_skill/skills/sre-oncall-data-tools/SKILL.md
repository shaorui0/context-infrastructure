---
name: sre-oncall-data-tools
description: "SRE oncall investigation 的 5 个 MCP 数据源参考（VictoriaMetrics, Loki, Slack, Grafana, Pod Discovery）"
---

# Data Tools

Investigation 中使用的 5 个数据源。查询前先读 `query_safety_rules.md`。

## 1. VictoriaMetrics (metrics) → MCP

`mcp__victoriametrics__*` MCP tools:
- `mcp__victoriametrics__query_range` — time-series range queries
- `mcp__victoriametrics__query` — instant queries
- `mcp__victoriametrics__series` — list matching series + labels
- `mcp__victoriametrics__rules` — inspect recording/alerting rule health
- `mcp__victoriametrics__metrics` — browse available metric names

### YugabyteDB 节点状态查询（常用）

当告警涉及 YB node down 时，用 VM MCP 查询节点状态：
```promql
# 查指定集群所有 YB 节点 up/down
up{kubernetes_cluster="<cluster>", kubernetes_namespace="<dbcluster>"}

# 查具体 IP 的节点
up{instance="<ip>:<port>"}
```

告警字段 → 查询参数映射：`Cluster` → `kubernetes_cluster`，`namespace` → `kubernetes_namespace`，`instance IP:port` → `instance`。

### 节点 IP 定位（awsf）

用 `awsf <region> <keyword>` 把告警 IP 映射到 EC2 实例名。集群名 → region 映射见 `knowledge/references/reference-aws-cli.md`。
```bash
# 示例：aws-uswest2-prod-a → us-west-2
awsf us-west-2 prod-a yb
# 输出：aws-uswest2-prod-a-prod-yb-prod-0  i-xxx  running  172.31.35.20
```

详细查询模板见 `knowledge/cards/card-yugabyte-metrics-fast-checks.md`。

## 2. Loki (logs) → /dv_loki_fetch skill

调用 `/dv_loki_fetch` skill — 它 wrap 了 `tools/loki_fetch/loki_fetch.py` CLI，含 LogQL pattern、stream selector 安全规则、Grafana URL 解析。
不要直接调 tools/loki_fetch/loki_fetch.py，用 skill。

## 3. VM Metrics + Pod Discovery → /sre-vm-query skill

调用 `/sre-vm-query` skill — 它 wrap 了 VM MCP tools 和 `tools/vm_lookup.py`，含 DV label 约定、常用 query pattern、retry 策略。

## 4. Grafana (dashboards) — 手动参考

**Grafana MCP 当前不可用。** Dashboard 查找通过以下方式：
- `knowledge/references/reference-grafana_dashboards.md` — 常用 dashboard URL 列表
- `knowledge/references/reference-link_templates.md` — URL 模板（含 Grafana deep-link）
- 手动构造 Grafana URL 给用户点击

**不使用任何 `mcp__grafana__*` 工具。** PromQL 查询用 VictoriaMetrics MCP，LogQL 查询用 `/dv_loki_fetch` skill。

## 5. Slack (alert messages) → MCP

```bash
# Step 1 — parse Slack URL
python3 ./tools/slack_link.py "<slack_url>"
```
```
# Step 2 — fetch message
mcp__slack__slack_list_messages(channel=<channel_id>, oldest=<message_ts>, latest=<message_ts>, inclusive=true, limit=1)
```
```
# Step 3 (optional) — fetch thread replies
mcp__slack__slack_list_messages(channel=<channel_id>, thread_ts=<thread_ts>, limit=50)
```

Available Slack MCP tools:
- `mcp__slack__slack_list_messages` — fetch messages (supports thread_ts)
- `mcp__slack__slack_get_channel_info` — channel metadata
- `mcp__slack__slack_search_messages` — search by keyword
- `mcp__slack__slack_list_threads` — list threads
- `mcp__slack__slack_get_user_info` — resolve user IDs

**Slack MCP 安全规则**：只读，所有调用经 mcp-audit.sh 审计，仅获取当前告警相关消息。

详细流程参见 `facets/slack_alert_intake.md`。

## 6. Agent SLO Metrics

```bash
python3 ./tools/agent_ops/slo.py [--since YYYY-MM-DD] [--json]
```

追踪 investigation 质量指标：debug tree 使用率、verdict 分布、步骤到结论的距离、验证通过率。
