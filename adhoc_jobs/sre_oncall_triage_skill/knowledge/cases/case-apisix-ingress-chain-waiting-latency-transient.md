---
metadata:
  kind: case
  status: draft
  summary: "External apisix P99 spike where apisix upstream_response_time looks high, but the actual bottleneck is nginx ingress waiting_latency. Detection backend was healthy (15ms). Must drill to nginx ingress layer logs to see true decomposition."
  tags: ["serving", "latency", "production", "ingress", "apisix", "nginx", "waiting-latency", "multi-layer", "standardbank", "afsouth1"]
  first_action: "Do NOT stop at apisix layer — drill to nginx ingress access log to decompose request_time vs upstream_response_time at ingress level"
  related:
    - "knowledge/cases/case-nginx-waiting-latency-memcached-timeout.md"
    - "knowledge/cases/case-fp-latency-waiting-latency-prod-qps-spike.md"
    - "knowledge/patterns/pattern-fp-latency-waiting-latency-pattern.md"
    - "knowledge/references/reference-latency-metrics-ingress-apisix.md"
  derived_from: "tmp/oncall/20260419_1342_standardbank-p99-apisix-afsouth1/report.md"
---

# External Apisix P99 Spike: Ingress waiting_latency Hidden Behind upstream_response_time

## TL;DR (Do This First)

1. Alert: External apisix P99 spike on `/standardbank/detection`, P99=5960ms
2. Key finding: Apisix access log showed `upstream_response_time=5.022s` — looks like upstream slow, but this is a **red herring**
3. Root cause: nginx ingress pod had `waiting_duration≈5.001s`; detection backend responded in 15ms
4. Fix: Self-healed, no action. Pod-level transient (no error logs found)
5. Follow-up: Monitor for recurrence; if repeated, investigate Lua plugin / pod restart

## The Multi-Layer Chain Trap

```
Client
  → External Apisix (e.g. apigateway-auth-afsouth1-prod-3)
      upstream_response_time = 5.022s  ← MISLEADING: includes all downstream time
  → Internal Nginx Ingress (e.g. ingress-nginx-controller-798c55d66f-v8bsn)
      request_time = 5.016s
      upstream_response_time = 0.015s  ← TRUE upstream latency
      waiting_duration = 5.001s        ← ACTUAL bottleneck
  → Detection Pod (prod-fp-8080)
      responded in 0.015s              ← HEALTHY
```

**Critical rule**: External apisix's `upstream_response_time` = total time for the entire downstream chain (nginx ingress + detection pod). It does NOT reflect the detection service health alone. Always drill to nginx ingress layer logs before concluding "upstream slow".

## 信号

| Field | Value |
|-------|-------|
| alertname | Apisix Cluster Ingress Request Time Too High |
| cluster | aws-afsouth1-prod (→ aws-afsouth1-prod-a in practice) |
| client | standardbank |
| endpoint | /standardbank/detection |
| P99 (alert) | 5960ms |
| nginx ingress pod | ingress-nginx-controller-798c55d66f-v8bsn |
| spike timestamp | 2026-04-19T04:40:29Z UTC |
| waiting_duration | 5.001s at nginx ingress |
| detection pod latency | 15ms (healthy) |
| error rate | 0% |

## Evidence Chain

### Step 1 — VM: Confirm spike is single apisix instance

```promql
histogram_quantile(0.99, sum(rate(
  apisix_monitoring_requests_percentage_time_apisix_bucket{
    cluster="aws-afsouth1-prod",
    client="standardbank",
    request_url="detection",
    job="promtail-apisix-http-sd"
  }[5m]
)) by (le, instance_name))
```

Result: only `apigateway-auth-afsouth1-prod-3` spiked (P99=5.85s); prod-1/prod-2 normal. P50=25ms throughout → not systemic.

**Note on VM metric labels**: cluster label = `aws-afsouth1-prod` (no -a/-b suffix). Metrics derived from Loki access logs via promtail (`job="promtail-apisix-http-sd"`).

### Step 2 — Loki: External apisix access log (misleading layer)

```logql
{cluster="aws-afsouth1-prod", job=~"apisix.*"} |= "detection"
```

Shows: `request_time=5.033s, upstream_response_time=5.022s` — initial read: upstream slow.
**This is wrong.** The "upstream" from apisix's view is the nginx ingress endpoint, not the detection service.

### Step 3 — Loki: Nginx ingress access log (correct layer)

```logql
{namespace="ingress-nginx", cluster=~"aws-afsouth1-prod-.*", client="standardbank", request_url=~".*(detection|update)", proxy_upstream_name!~".*sandbox.*|.*demo.*"} |= "detection"
```

Shows at 04:40:29:
```
request_time=5.016s  upstream_response_time=0.015s  [prod-fp-8080]  192.168.237.132:8080
```

**waiting_duration = 5.016 - 0.015 = 5.001s** at nginx ingress pod `v8bsn`.
Same upstream pod (`192.168.237.132:8080`) on other nginx pods: 16–18ms. Upstream is healthy.

### Step 4 — Loki: Nginx ingress error logs (confirmed clean)

```logql
-- pod-level search
{namespace="ingress-nginx", cluster=~"aws-afsouth1-prod-.*", pod="ingress-nginx-controller-798c55d66f-v8bsn"} |~ "error|warn|lua|memcached|timeout"

-- cluster-wide stderr, wider window (04:00–05:30 UTC)
{namespace="ingress-nginx", cluster=~"aws-afsouth1-prod-.*", stream="stderr"} |~ "error|Error|ERROR"

-- memcached/lua specific
{namespace="ingress-nginx", cluster=~"aws-afsouth1-prod-.*"} |~ "memcach|lua|timed out|11211|global_throttle"
```

**Results**: Zero memcached/lua/timeout errors in aws-afsouth1-prod-a for the entire 04:00–05:30 UTC window. Only unrelated health-check error on prod-b at 04:17.

**Implication**: memcached timeout hypothesis ruled out. The 5s waiting_latency was silent — either a Lua call that was slow but successful (no timeout logged), or an nginx worker OS-level scheduling stall. Cannot determine exact mechanism from logs alone.

## 结论

Evidence is consistent with a transient nginx ingress worker stall on pod `v8bsn`. The detection backend was healthy throughout. Possible causes (unranked, no error evidence to confirm):
- Silent Lua plugin delay (global_throttle → slow memcached call that completed without timeout)
- Nginx worker OS-level scheduling preemption
- Transient connection pool issue on that specific pod

## Contrast with Known Cases

| Dimension | This Case | case-nginx-waiting-latency-memcached-timeout |
|-----------|-----------|----------------------------------------------|
| Pattern | waiting_latency dominates, upstream healthy | same |
| Error logs | None found | Explicit lua/memcached timeout errors |
| Spike shape | Single request | Periodic P100 every 5-10min |
| Affected pods | Single pod (v8bsn) | Multiple pods simultaneously |
| Root cause confirmed | No (transient, unlogged) | Yes (memcached saturation) |

## 建议操作

### 诊断（只读，复发时执行）

```bash
# 检查 nginx ingress pod 状态
kafsouthproda kubectl get pod -n ingress-nginx | grep ingress-nginx-controller

# 检查慢请求
# Loki: request_url="detection", 过滤 request_time > 1
{namespace="ingress-nginx", cluster=~"aws-afsouth1-prod-.*", client="standardbank"} 
  | pattern "<_> <request_time> [<proxy_upstream_name>]"
  | request_time > 1

# 检查 nginx ingress error log (lua/memcached)
{namespace="ingress-nginx", cluster=~"aws-afsouth1-prod-.*", pod=~"ingress-nginx-controller-.*"} 
  |~ "lua|memcached|timed out|11211"
```

### 修复（需人工确认，仅复发时考虑）

```bash
# 重启 nginx ingress deployment（若单 pod 反复出现 waiting_latency）
# kafsouthproda kubectl rollout restart deployment/ingress-nginx-controller -n ingress-nginx
```
