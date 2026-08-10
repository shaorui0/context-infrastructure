---
name: sre-vm-query
description: "Query VictoriaMetrics for SRE oncall investigation. Covers MCP tools (instant/range/series/labels), pod/namespace discovery via vm_lookup.py, DV label conventions, and common query patterns."
---

# VM Query Skill — DV VictoriaMetrics

DataVisor VictoriaMetrics 查询入口。不是 CLI 手册 —— 是**使用指南**：什么时候选哪个查询、label 约定、常见坑。

## Standalone Mode（默认）

> **本 skill 可直接调用，不依赖 oncall triage workflow。** 用户说"查个 metric / VM 看一下 / 看看 prod-a 的 CPU"等数据查询意图，直接进入本 skill 即可，**无需**加载 `sre-oncall-init` / `sre-oncall-acceptance-criteria` / 任何 phase lock。
>
> - **输出**：结果直接回对话（或用户指定文件），**不**写 `tmp/oncall/.../report.md`，**不**走 verification gate。
> - **安全约束**：本文件 §"Query Safety Rules" 自包含，足以独立使用。
> - **何时升级到 oncall workflow**：用户的查询结果暴露真实事故迹象（持续 SLA 异常 / 多服务联动失败），主动建议切到 `/sre-oncall-triage`（不要自动切，问用户）。

## When to Use

- 调查需要**数值/时序数据**（QPS、latency、error rate、pod count、resource 饱和）
- 需要**定位 pod/namespace**（从 service 名或 client 名反查）
- 需要**核对 alert 是否还在 firing**（查 rule/alert 状态）
- 查 SLA 指标（配合 `knowledge/references/reference-sla-dashboard.md`）

**不适合**：log 调查（→ `/dv_loki_fetch`）；dashboard 截图（→ 手动 Grafana URL）；schema discovery（→ `mcp__victoriametrics__metrics_metadata`）。

---

## Tool Inventory

### MCP tools（首选）
| Tool | 用途 | 典型参数 |
|---|---|---|
| `mcp__victoriametrics__query` | Instant query（某时刻值） | `query`, `time` |
| `mcp__victoriametrics__query_range` | 时序 range | `query`, `start`, `end`, `step` |
| `mcp__victoriametrics__series` | 列出匹配的 series（找 label 值） | `match`, `start`, `end` |
| `mcp__victoriametrics__labels` | 列出可用 labels | `match[]` |
| `mcp__victoriametrics__label_values` | 某 label 的全部值 | `label`, `match[]` |
| `mcp__victoriametrics__metrics` | 浏览 metric 名 | `match` |
| `mcp__victoriametrics__rules` | alerting/recording rule 状态 | (none) |
| `mcp__victoriametrics__alerts` | 当前 firing alerts | (none) |
| `mcp__victoriametrics__explain_query` | 分析 PromQL 执行计划 | `query` |

### CLI fallback（当 MCP 不可用 / 需要脚本化）
```bash
# Pod/namespace discovery —— 给 service 名，返回 candidate pods
python3 tools/vm_lookup.py pods --cluster aws-uswest2-prod-a --service fp --prefer-namespace prod

# 从 pod 名反查 namespace
python3 tools/vm_lookup.py namespace-from-pod --pod fp-0
```

环境变量：`VM_BASE_URL`（必需）。

---

## Query Safety Rules（self-contained）

> 本节自包含，standalone 调用时直接生效。oncall workflow 模式下另有 `sre-oncall-query-safety` 做交叉校验，但**不再依赖**它注入。

| 规则 | 细则 |
|---|---|
| 必须 label filter | 每个 PromQL 至少一个 label（`namespace` / `job` / `service` / `client` / `kubernetes_cluster`） |
| Step floor | `query_range` 的 `step` ≥ 30s |
| Time window ceiling | `query_range` ≤ 24h（Loki 是 6h，那是 loki_fetch 的事） |
| 禁止高基数 regex wildcard | `=~".*"` 不能用在 `pod` / `instance` / `container` label |
| Retry budget | 单条 query 最多 2 次重试；失败就换思路 |
| 精确时间窗 | event_ts ± 3min，不要 `now()-6h` 模糊窗口 |

违规 → MCP 可能 timeout，浪费 agent budget。

---

## DV Label Conventions

> 这是 agent 最容易搞错的地方 —— metric 的 label 名 DV 和通用 Prometheus 不完全一样。

| 想查的东西 | DV label 名 | 备注 |
|---|---|---|
| Cluster | `kubernetes_cluster` (主) / `cluster` (某些 APISIX metrics) | vm_lookup.py 会依次试 `kubernetes_cluster` → `cluster` |
| Namespace | `kubernetes_namespace` / `namespace` | Ingress Loki 是 `namespace="ingress-nginx"` |
| Pod | `pod` | Regex 匹配时注意 prefix（`fp-.*`、`chi-.*-0-0-0`） |
| Container | `container` | Nginx ingress pod 里是 `container="controller"` |
| Client/tenant | `client`（主）/ `tenant`（某些）| `rule_count_total` 用 `tenant` 不是 `client` |
| Instance | `instance`（`<ip>:<port>`） | 禁止 regex wildcard |
| Ingress upstream | `proxy_upstream_name` | Prod: `(prod\|pci).*-fp.*`；排除 `.*sandbox.*\|.*demo.*` |
| Request URL | `request_url` | 生产 URL 匹配 `.*(clientEvent\|detection\|update)` |
| HTTP status | `status_code` | Success = `200`/`400`/`429`；排除 `5xx`、`499` |
| Batch job | `job` | `rawlogconverter`、`userstats`、`campaign`、`resultagg`、`frontendresultwriter` |

---

## Common Query Patterns

### Pattern 1 — 核对 pod/namespace

用 `vm_lookup.py`（比一次次试 MCP 更快）:
```bash
python3 tools/vm_lookup.py pods --cluster aws-uswest2-prod-a --service fp --prefer-namespace prod
```

返回 JSON:
```json
{"ok": true, "pods": [{"namespace": "prod", "pod": "fp-0"}, ...]}
```

MCP 等价：
```
mcp__victoriametrics__query  query='topk(200, max by (namespace, pod) (kube_pod_info{pod=~"fp-.*", kubernetes_cluster="aws-uswest2-prod-a"}))'
```

### Pattern 2 — Alert 是否还在 firing

```
mcp__victoriametrics__alerts
# 返回当前所有 firing alerts。按 alertname/cluster 过滤。
```

### Pattern 3 — Ingress QPS (事后回看)

```
mcp__victoriametrics__query_range
  query='sum by (client, request_url) (record:loki_kubernetes_monitoring_request_1m_qps_ingress_nginx{client="affirm"})'
  start=<event_ts - 10m>
  end=<event_ts + 10m>
  step=30s
```

> 更多 SLI queries：见 `reference-sla-dashboard.md` §5。

### Pattern 4 — P99 latency (recording rule 首选)

```
mcp__victoriametrics__query_range
  query='record:loki_kubernetes_monitoring_requests_percentage_time_ingress_nginx_P99{client="affirm", request_url=~".*(clientEvent|detection|update)"}'
  start=<event_ts - 30m>
  end=<event_ts + 5m>
  step=1m
```

如果要更精确（recording rule 是约值），转 Loki LogQL（见 reference-sla-dashboard §5.1 "Actual response latency via LogQL"）。

### Pattern 5 — YB 节点 up/down

```
mcp__victoriametrics__query
  query='up{kubernetes_cluster="aws-uswest2-prod-a", kubernetes_namespace="prod-yb"}'
```

或通过 IP 定位具体节点：
```
mcp__victoriametrics__query
  query='up{instance="10.50.216.15:7000"}'
```

节点 IP ↔ instance 名映射，用 `awsf <region> <keyword>`（见 `reference-aws-cli.md`）。

### Pattern 6 — ClickHouse merge pressure

```
mcp__victoriametrics__query
  query='ClickHouseProfileEvents_MergedRows{kubernetes_cluster="aws-uswest2-prod-a", pod=~"chi-dv-datavisor.*"}'
```

### Pattern 7 — Kafka consumer lag

```
mcp__victoriametrics__query
  query='kafka_consumergroup_lag{kubernetes_cluster="aws-uswest2-prod-a", consumergroup=~"cg\\..*"}'
```

### Pattern 8 — Batch job E2E 完成时间

```
mcp__victoriametrics__query
  query='max(prod_job_finish_time{job="frontendresultwriter", client="affirm"}) - max(prod_job_start_time{job="rawlogconverter", client="affirm"})'
```

SLO：< 86400s（24h）。

---

## Common Pitfalls

| 症状 | 原因 | 解决 |
|---|---|---|
| MCP query 超时 / 返回 5xx | Window 太大 / 高基数 label regex | 缩小 window 到 ±10min；去掉 `=~".*"` |
| `cluster` vs `kubernetes_cluster` | APISIX metrics 用 `cluster`，其他用 `kubernetes_cluster` | `vm_lookup.py` 会轮询试；手写 query 时先 `labels` 看 |
| 查 tenant 无数据 | 用了 `client` 但 metric 要求 `tenant` | 看 `rule_count_total` / `endpoint_metric_eventtype_total` 这类 |
| Recording rule `record:loki_...` 值突然为 0 | 对应 Loki 流 missing label / Loki down | 切到 raw `kubernetes_monitoring_request_total_ingress_nginx` |
| pod regex 带 `-*` 不 match | 需要 escape `.` → `-.*` 写成 `.*\\-.*`？  | vm_lookup.py 里有 `_pod_regex_for_service` 处理 FP 系列，其他用 `{prefix}-.*` |
| APISIX query 没数据 | 忘记排除 sandbox | 加 `cluster!~"aws-uswest2-sandbox"` |

---

## Retry / Fallback Protocol

1. MCP query timeout → 缩 window 一半重试一次
2. 两次失败 → 换 `query_range` → `query` (instant)
3. 仍失败 → fallback to `vm_lookup.py` CLI（直连 VM HTTP API）
4. 仍失败 → 在 investigation log 标 `UNKNOWN`，不阻塞其他 branch

---

## Integration with Other Skills

> 这些都是**可选**的拓展，standalone 调用本 skill 时不需要加载它们。

- **`/dv_loki_fetch`**（全局 skill）— log 查询；metric 查询用本 skill。两者对称，互不依赖。
- **`knowledge/references/reference-sla-dashboard.md`**— 核心 SLI PromQL 模板库（用户问 SLA 时按需 Read）
- **`knowledge/references/reference-grafana-dashboards.md`**— dashboard URL 模板，查完 VM 后链给用户查看趋势
- **`sre-oncall-query-safety` / `sre-oncall-data-tools`**— 仅在 oncall triage workflow 内启用；standalone 用不到

---

## Example End-to-End Flow

**Alert**: `FP P99 latency spike on aws-uswest2-prod-a at 2026-04-18 10:30 UTC`.

1. `vm_lookup.py pods --cluster aws-uswest2-prod-a --service fp` → 确认 `prod/fp-0..N`
2. `mcp__victoriametrics__query_range` 查 `record:...P99_ingress_nginx{client="...", request_url=~".*(clientEvent|detection|update)"}` 在 event_ts ± 3min
3. 值确实飙升 → 进 debug-tree `latency-breakdown.md` → 决定查 upstream vs ingress vs waiting
4. 用 `/dv_loki_fetch` 拉对应 Nginx 日志（本 skill 管不到）
5. 结论汇入 `tmp/oncall/.../report.md`
