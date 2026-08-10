---
name: workflow-oncall-spike
description: "Latency spike (P99/P95) 快速 triage：两阶段结构化调查，Phase 1 判断 FP vs Infra，sonnet subagent 拉 metrics"
---

# Workflow: Oncall Latency Spike Triage

P99/P95 ingress latency spike 的结构化调查流程。核心：**先判断是 FP/backend 慢还是 infra/gateway 慢**，再深入。

## 触发条件

- Alert 涉及 P99、P95、latency、response time、SLA 退化
- Alert 涉及 `request_time`、`upstream_response_time`、waiting latency
- Client 反馈 API 响应慢

**不适用**：纯 error-rate (5xx 无 latency)、kafka lag、batch pipeline。P99 spike 但 error rate 正常 → 先跑 `debug-tree-false-p99-histogram-skew.md` 排除假警报。

## Prerequisites: 信号提取

| Signal | Required | Fallback |
|--------|----------|----------|
| `client` | **yes** | `reference-defaults.md` cluster→client |
| `cluster` | **yes** | 从 Slack channel 或 alert text 提取 |
| `event_ts` | **yes** | alert 触发时间。**缺失 → 停下问用户** |
| `namespace` | recommended | 默认 `prod`（标记为 assumption） |
| `endpoint` | optional | `All` |

**缺字段门禁**：client / cluster / event_ts 任一缺失 → 停下向用户要，不猜测。

---

## Phase 1: Branch Decision（目标 < 2 分钟）

**目标**：判断 latency 是 FP/backend 慢还是 infra/gateway 慢。不做深入调查。

### Step 1.0: Alert 是否仍在 firing

**Sonnet subagent**:
```
Agent(model="sonnet", prompt="
  Use mcp__victoriametrics__alerts to check if there is a currently firing latency alert
  for client={client}. Also use mcp__victoriametrics__rules with the alert rule name
  to check its state. Return: alert_state (firing/pending/inactive), current_value.
  Follow query safety rules.
")
```

- `inactive` 且从未 `firing` → 可能假警报，先跑 `debug-tree-false-p99-histogram-skew.md`。**STOP this workflow。**
- `pending` 或 `firing` → **CONTINUE**

### Step 1.1 + 1.2 + 1.3: 三个查询并行（Sonnet subagent × 3）

**时间窗口**：`event_ts - 3min` 到 `event_ts + 3min`（RFC3339），`step=30s`

**Subagent A（request_time P95）**:
```
Agent(model="sonnet", prompt="
  Use mcp__victoriametrics__query_range:
  query: histogram_quantile(0.95, sum by (le) (rate(record:loki_kubernetes_monitoring_request_time_ingress_nginx_bucket{client='{client}'}[5m])))
  start: {event_ts - 3min}, end: {event_ts + 3min}, step: 30s
  Return time series values. Follow query safety rules.
")
```

**Subagent B（upstream_response_time P95）**:
```
Agent(model="sonnet", prompt="
  Use mcp__victoriametrics__query_range:
  query: histogram_quantile(0.95, sum by (le) (rate(record:loki_kubernetes_monitoring_upstream_response_time_ingress_nginx_bucket{client='{client}'}[5m])))
  start: {event_ts - 3min}, end: {event_ts + 3min}, step: 30s
  Return time series values. Follow query safety rules.
")
```

**Subagent C（QPS + Error rate）**:
```
Agent(model="sonnet", prompt="
  Use mcp__victoriametrics__query_range, TWO queries:
  Query 1 (QPS): sum(rate(kubernetes_monitoring_request_total_ingress_nginx{client='{client}'}[1m]))
  Query 2 (Error rate): sum(rate(kubernetes_monitoring_request_total_ingress_nginx{client='{client}', status_code=~'5..'}[1m])) / sum(rate(kubernetes_monitoring_request_total_ingress_nginx{client='{client}'}[1m]))
  start: {event_ts - 10min}, end: {event_ts + 3min}, step: 30s
  Return both. Note any QPS spike (>2x baseline) and error rate changes. Follow query safety rules.
")
```

### Step 1.4: Branch Decision（Opus 判断，不 delegate）

收到三个 subagent 结果后计算：

```
waiting_latency = request_time_p95 - upstream_response_time_p95
ratio = upstream_response_time_p95 / request_time_p95
```

| Condition | Classification | Branch |
|-----------|---------------|--------|
| `ratio > 0.7`（upstream ≈ total） | **FP/Backend 慢** | → Branch A |
| `ratio < 0.3`（upstream << total） | **Infra/Gateway 问题** | → Branch B |
| `0.3–0.7` 且 waiting > upstream | Mixed, infra 主导 | → Branch B (primary) |
| `0.3–0.7` 且 upstream > waiting | Mixed, FP 主导 | → Branch A (primary) |
| Both elevated + QPS spike > 2x | 系统性过载 | → Branch C |

**立即写入输出文件**：

```markdown
## Phase 1 Result (Latency Decomposition)
- request_time P95: {value}ms
- upstream_response_time P95: {value}ms
- waiting_latency (derived): {value}ms
- ratio (upstream/total): {value}
- QPS at alert time: {value} (baseline: {value})
- Error rate: {value}
- **Classification**: {FP/Backend | Infra/Gateway | Systemic}
- **Branch**: {A | B | C}
```

### 参考阈值

| Metric | Normal (P95) | Warning | Alert |
|--------|-------------|---------|-------|
| Total Response Time | < 300ms | 300–500ms | > 500ms |
| Upstream Response | < 150ms | 150–300ms | > 300ms |
| Waiting Latency | < 100ms | 100–200ms | > 200ms |

---

## Phase 2: Branch Investigation

Phase 1 完成、用户确认方向后执行。Sonnet subagent 拉数据，Opus 做判断。

**时间窗口**：`event_ts ± 5min`（Phase 2 稍宽），`step=30s`

### Branch A: FP/Backend 慢

upstream_response_time 主导 request_time。问题在后端服务。

#### A.1: FP Pod 资源（Sonnet subagent）

```
Agent(model="sonnet", prompt="
  Use mcp__victoriametrics__query_range (event_ts ± 5min, step=30s):
  1. CPU: sum(rate(container_cpu_usage_seconds_total{namespace='{namespace}', pod=~'fp.*', container='fp'}[5m])) by (pod)
  2. Memory: sum(container_memory_working_set_bytes{namespace='{namespace}', pod=~'fp.*', container='fp'}) by (pod)
  3. CPU throttle: sum(rate(container_cpu_cfs_throttled_seconds_total{namespace='{namespace}', pod=~'fp.*', container='fp'}[5m])) by (pod)
  4. Restarts: sum(kube_pod_container_status_restarts_total{namespace='{namespace}', pod=~'fp.*'}) by (pod)
  Flag: CPU > 80% limit, memory > 80% limit, throttling > 0, restarts during window.
  Follow query safety rules.
")
```

#### A.2: 数据库依赖（Sonnet subagent，按优先级）

```
Agent(model="sonnet", prompt="
  Use mcp__victoriametrics__query_range (event_ts ± 5min, step=30s), check dependencies in order:
  P0 — YugabyteDB: histogram_quantile(0.95, sum by (le) (rate(rpc_latency_bucket{exported_instance=~'.*yugabyte.*', server_type='yb_tserver'}[5m])))
  P1 — External API: rate(http_client_requests_seconds_sum{uri=~'.*ekata.*'}[5m]) (if exists)
  P2 — MySQL: mysql_global_status_slow_queries{kubernetes_cluster='{cluster}'}
  P3 — ClickHouse: ClickHouseProfileEvents_FailedQuery{kubernetes_cluster='{cluster}'}
  Return each dependency's status. Always include namespace or cluster label.
  Follow query safety rules.
")
```

#### A.3: FP 应用日志（Sonnet subagent）

```
Agent(model="sonnet", prompt="
  Use the /dv_loki_fetch skill to query Loki logs:
  LogQL: {cluster=\"{cluster}\", namespace=\"{namespace}\", pod=~\"fp-deployment.*\", container=\"fp\"} |~ \"slow|timeout|deadline|Exception|Error|GC pause|thread pool|OOM\"
  Time window: {event_ts - 3min} to {event_ts + 3min}, limit 50, direction backward.
  Group results by error type. Follow query safety rules.
")
```

**Branch A 判断（Opus）**：
- CPU throttle → 容量问题
- DB latency 升高 → 数据库瓶颈
- GC pause / thread pool → JVM 资源
- 都正常 → `MANUAL`（需要更深 APM 排查）

---

### Branch B: Infra/Gateway 问题

waiting_latency 主导。问题在 nginx/apisix/网络层。

#### B.1: Ingress Controller 健康（Sonnet subagent）

```
Agent(model="sonnet", prompt="
  Use mcp__victoriametrics__query_range (event_ts ± 5min, step=30s):
  1. Ingress CPU: sum(rate(container_cpu_usage_seconds_total{namespace='ingress-nginx', container='controller'}[5m])) by (pod)
  2. Ingress memory: sum(container_memory_working_set_bytes{namespace='ingress-nginx', container='controller'}) by (pod)
  3. Active connections: nginx_ingress_controller_nginx_process_connections{state='active'}
  4. Waiting connections: nginx_ingress_controller_nginx_process_connections{state='waiting'}
  Flag: CPU/memory > 80%, connection count significantly above baseline.
  Follow query safety rules.
")
```

#### B.2: Ingress Error Logs（Sonnet subagent）

```
Agent(model="sonnet", prompt="
  Use the /dv_loki_fetch skill to query Loki logs (run two queries):
  Query 1:
  LogQL: {cluster=\"{cluster}\", namespace=\"ingress-nginx\", container=\"controller\"} |~ \"upstream timed out|connect() failed|no live upstreams|502|504|connection refused\"
  Time window: {event_ts - 3min} to {event_ts + 3min}, limit 50.
  Query 2:
  LogQL: {cluster=\"{cluster}\", namespace=\"ingress-nginx\", container=\"controller\"} |~ \"{client}\" | pattern \"<_> <_> <_> [<_>] \\\"<method> <path> <_>\\\" <status> <_> <_> <_> <_> <_> <_> <_> <_> <_> <_> <request_time> <_> <_>\" | request_time > 0.5
  Time window: {event_ts - 3min} to {event_ts + 3min}, limit 50.
  Follow query safety rules.
")
```

#### B.3: Node 级指标（Sonnet subagent）

```
Agent(model="sonnet", prompt="
  Use mcp__victoriametrics__query_range (event_ts ± 5min, step=30s):
  1. Node CPU: 1 - avg(rate(node_cpu_seconds_total{mode='idle', kubernetes_cluster='{cluster}'}[5m])) by (node)
  2. Network errors: sum(rate(node_network_receive_errs_total{kubernetes_cluster='{cluster}'}[5m])) by (node)
  3. IO wait: avg(rate(node_cpu_seconds_total{mode='iowait', kubernetes_cluster='{cluster}'}[5m])) by (node)
  Flag: CPU > 85%, network errors > 0, iowait > 10%.
  Follow query safety rules.
")
```

#### B.4: 爆炸半径 — 其他 client 是否受影响（Sonnet subagent）

```
Agent(model="sonnet", prompt="
  Use mcp__victoriametrics__query_range (event_ts ± 3min, step=30s):
  topk(10, histogram_quantile(0.95, sum by (client, le) (rate(record:loki_kubernetes_monitoring_request_time_ingress_nginx_bucket[5m]))))
  Return top clients by P95. Follow query safety rules.
")
```

**Branch B 判断（Opus）**：
- Ingress CPU 饱和 → ingress 容量
- upstream timed out → upstream pod not ready
- 多 client 受影响 → 系统性 infra 问题
- 只有一个 client → client 特定（QPS spike / routing）
- 都正常 → 查 APISIX（如果请求走 APISIX path）

---

### Branch C: 系统性过载

两边都升高 + QPS spike。执行 Branch A + Branch B 查询，额外查：

#### C.1: 最近部署（Sonnet subagent）

```
Agent(model="sonnet", prompt="
  Use mcp__victoriametrics__query_range (event_ts - 15min to event_ts + 5min, step=60s):
  changes(kube_deployment_status_observed_generation{namespace='{namespace}'}[10m])
  Return any deployments that changed within the window.
  Follow query safety rules.
")
```

#### C.2: Per-pod 分布（Sonnet subagent）

```
Agent(model="sonnet", prompt="
  Use mcp__victoriametrics__query_range (event_ts ± 3min, step=30s):
  histogram_quantile(0.95, sum by (pod, le) (rate(record:loki_kubernetes_monitoring_upstream_response_time_ingress_nginx_bucket{client='{client}'}[5m])))
  Return per-pod P95. Check if all pods affected or just one.
  Follow query safety rules.
")
```

**Branch C 判断（Opus）**：
- 单 pod → pod 级问题（OOM/GC/hot partition）
- 全 pod + deployment change → 部署回归
- 全 pod + no change → 系统性压力（DB/network/node）

---

## Sonnet Subagent 规则

1. **必须指定 `model: "sonnet"`**
2. Subagent 只做数据拉取和提取，**不做 root cause 判断**
3. Opus 做：branch decision、correlation、verdict、命令生成
4. 重试：subagent 查询失败 → 扩大窗口到 ± 5min 重试一次。仍失败 → MARK_UNKNOWN
5. **并行**：Step 1.1/1.2/1.3 并行。Branch 内独立查询并行（A.1+A.2, B.1+B.3）
6. 每个 subagent prompt 包含 "Follow query safety rules"

## 时间窗口策略

| Phase | Window | 用途 |
|-------|--------|------|
| Phase 1 初始 | event_ts ± 3min | 信号提取 |
| Phase 1 重试 | event_ts ± 5min | 初始返回空时 |
| Phase 2 调查 | event_ts ± 5min | root cause 上下文 |
| QPS baseline | event_ts - 10min → event_ts + 3min | 需要 alert 前基线对比 |
| 部署关联 | event_ts - 15min → event_ts + 5min | 更宽窗口查变更 |

## 关联知识文件

| File | Relevance |
|------|-----------|
| `debug-trees/debug-tree-latency-breakdown.md` | 完整 latency decomposition tree（本 skill 是快速版） |
| `debug-trees/debug-tree-false-p99-histogram-skew.md` | 假警报排除（Phase 1 前置） |
| `references/reference-latency-metrics-ingress-apisix.md` | 核心延迟模型和指标语义 |
| `patterns/pattern-fp-latency-waiting-latency-pattern.md` | Ingress waiting_latency pattern |
| `cards/card-fp-infra-fast-entrypoints.md` | FP 依赖快速入口 |
| `cards/card-nginx-fast-triage.md` | Nginx 5 分钟快速 triage |
| `references/reference-fp-service-infra-reference.md` | FP 基础设施拓扑 |
