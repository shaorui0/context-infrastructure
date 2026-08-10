---
metadata:
  kind: case
  status: final
  summary: "Nginx ingress waiting_latency periodic P100 spikes to exactly 1.00s every 5-10 minutes. Root cause: global_throttle Lua rate-limiting plugin makes a synchronous memcached call per request; single-replica memcached (10 threads) saturates under concurrent connections, causing connect/read timeouts that block nginx workers. upstream_response_time stays normal throughout."
  tags: ["serving", "latency", "production", "ingress", "nginx", "waiting-latency", "memcached", "rate-limit", "lua", "k8s", "ingress-nginx"]
  first_action: "Decompose request_time vs upstream_response_time — if waiting dominates and upstream is healthy, check nginx error log for lua/memcached timeout errors"
  related: []
---

# Nginx Waiting Latency Root Cause: global_throttle Lua → Memcached Timeout

## TL;DR (Do This First)
1. Confirm latency decomposition: `waiting_duration = request_time - upstream_response_time` dominates; upstream is healthy.
2. Check nginx error log (stderr) for `global_throttle.lua` / `lua tcp socket` / `timed out` / `11211`.
3. Cross-correlate error log timestamp + client IP with access log slow request — if they match, root cause is memcached.
4. Check memcached pod health: single replica? low thread count? FD spike?
5. Mitigations: scale memcached replicas, increase threads, lower Lua read timeout — all `#MANUAL`.

## Safety Boundaries
- Read-only: Loki log queries, VictoriaMetrics/PromQL, `kubectl get/describe/logs/top`.
- `#MANUAL`: memcached scaling, nginx ConfigMap changes, Lua timeout tuning.

## One-line Essence
> Upstream is fine; nginx worker is blocked waiting on a single-instance memcached called synchronously by the Lua rate-limit plugin.

## Context
- **Date**: 2026-04-08
- **Cluster**: `aws-uswest2-prod-a` (prod.awsus)
- **Affected clients**: sofi (47.5% of errors), bdc, syncbank, navan, cuoc, rippling, pefcu, taskrabbit
- **Service**: Serving API behind ingress-nginx with global rate-limiting enabled

## Trigger / Symptoms
- Grafana "SLA - Batch & RealTime" panel "Waiting Latency between Ingress and Upstream" shows P100 = exactly 1.00s, periodic spikes every 5-10 minutes.
- P50–P95 completely normal (1–2ms). Only tail latency affected.
- `upstream_response_time` stays at baseline (~20–30ms). Waiting absorbs 100% of the extra time.

## Triage

### Step 1 — Confirm waiting_latency dominates, upstream healthy

```promql
-- Check fp pod health
increase(kube_pod_container_status_restarts_total{namespace="prod", container="fp"}[5m])
rate(container_cpu_usage_seconds_total{namespace="prod", pod=~"fp-deployment.*"}[5m])
container_memory_working_set_bytes{namespace="prod", pod=~"fp-deployment.*"}
kube_horizontalpodautoscaler_status_current_replicas{horizontalpodautoscaler="fp-hpa"}
```

Expected result: fp pods healthy, 0 restarts, CPU/memory stable → upstream eliminated.

### Step 2 — Find slow requests in nginx access log

```logql
{cluster="aws-uswest2-prod-a", namespace="ingress-nginx", container="controller", client="sofi", proxy_upstream_name="prod-fp-8080"}
  | regexp "(?P<request_time>\\d+\\.\\d+) \\[prod-fp-8080\\]"
  | request_time >= 1
```

Key signal: multiple requests with `waiting ≈ 1.00s` arriving in the **same second** from different client IPs → infrastructure-side block, not client-side.

### Step 3 — Check nginx error log for memcached timeout

```logql
{cluster="aws-uswest2-prod-a", namespace="ingress-nginx", container="controller", stream="stderr"} |= "timeout"
```

Look for:
```
[error] global_throttle.lua:105: throttle(): error while processing key: 'get' failed for ... timeout
[error] lua tcp socket connect timed out, when connecting to <memcached-ip>:11211
[error] lua tcp socket read timed out
```

### Step 4 — Cross-correlate access log + error log

Match on `timestamp` + `client IP` + `request path`. If a slow access log entry (high `request_time`) aligns with a memcached timeout error log entry at the same second and same client IP, causality is established.

**Example from this incident:**
```
# Access log
08:07:11 | 192.168.212.64 | POST /sofi/detection | request_time=0.609 upstream_response_time=0.095
#                                                   waiting = 0.514s

# Error log (same second, same client IP)
08:07:11 [error] lua tcp socket connect timed out, when connecting to 10.96.150.232:11211
         client: 192.168.212.64, request: POST /sofi/detection
```

### Step 5 — Check memcached pod health

```promql
-- CPU and memory
rate(container_cpu_usage_seconds_total{namespace="ingress-nginx", pod=~"memcached.*"}[5m])
container_memory_working_set_bytes{namespace="ingress-nginx", pod=~"memcached.*"}

-- File descriptors (proxy for connection count since no exporter)
container_file_descriptors{namespace="ingress-nginx", pod=~"memcached.*"}

-- Thread count
container_threads{namespace="ingress-nginx", pod=~"memcached.*"}

-- Restarts / OOM
kube_pod_container_status_restarts_total{namespace="ingress-nginx", container="memcached"}
container_oom_events_total{namespace="ingress-nginx", pod=~"memcached.*"}
```

Red flags in this incident:
- Single replica, 10 threads
- FD normal=24, spike=54 (2x → timeouts begin)
- No memcached exporter (blind to `current_connections`, `listen_disabled_num`)
- Deprecated image (`bitnamilegacy/memcached:1.6.21`)

### Step 6 — Check memcached timeout frequency

```logql
count_over_time({namespace="ingress-nginx", cluster="aws-uswest2-prod-a"} |= "tcp socket" |= "timed out" [1m])
```

Correlate spikes with memcached FD/CPU spikes.

## Root Cause Chain

```
Client request → nginx ingress controller (multi-pod, multi-worker)
  → global_throttle Lua plugin (synchronous memcached call per request)
    → memcached pod (single replica, 10 threads) at :11211
      → concurrent connections exceed thread capacity
        → accept queue overflow
          → connect timed out (50ms) OR read timed out (default ~1000ms)
            → Lua plugin blocks nginx worker for 0.3–1.0s
              → request_time increases; upstream_response_time unchanged
                → waiting_duration = request_time - upstream_response_time spikes
                  → Grafana P100 = exactly 1.00s
```

**Why 1.00s exactly**: the `lua-resty-memcached` read timeout (or `global_throttle.lua` explicit setting) is 1000ms. Connect timeout is 50ms (ConfigMap `global-rate-limit-memcached-connect-timeout`). The 1.00s tail represents the read timeout ceiling.

## What Was Ruled Out

| Hypothesis | How ruled out |
|---|---|
| nginx proxy timeout misconfiguration | All proxy timeouts are 5s / 60s / 0 (unlimited). No 1s value anywhere except `global-rate-limit-window=1s` (rate window, not timeout). |
| fp (upstream service) unhealthy | 0 restarts, 0 OOM, CPU 2% of limit, memory stable, all 200 responses. |
| Client-side problem | 7/9 slow requests in same second from different IPs → infra-side. |

## Mitigations (`#MANUAL`)

| Priority | Action | Expected effect |
|---|---|---|
| P0 | Scale memcached to 2+ replicas | Eliminate SPOF, distribute connection load |
| P0 | Increase memcached threads (10 → 32+) | More concurrent connections before saturation |
| P1 | Lower Lua read timeout (1000ms → 100–200ms) | Reduce worst-case waiting from 1s to 200ms |
| P1 | Deploy memcached exporter sidecar | Get `current_connections`, `listen_disabled_num` visibility |
| P2 | Review `pool_size=10000` in ConfigMap | May be excessive for current memcached capacity |
| P2 | Upgrade memcached image (deprecated bitnamilegacy → current) | Security + bug fixes |
| P3 | Investigate periodic burst trigger (every :10–:13s within minute) | Find external cause of connection burst |

## Appendix: Nginx Config Audit (What Was Checked)

ConfigMap global defaults: `proxy_connect_timeout=5s`, `proxy_read_timeout=60s`, `proxy_send_timeout=60s`.  
Per-ingress overrides: some internal tools set 3600s. **No ingress sets 1s timeout.**  
Only `1s` in config: `global-rate-limit-window=1s` (sliding window size, not a proxy timeout).

Memcached-related ConfigMap keys: `global-rate-limit-memcached-connect-timeout=50ms`, `pool_size=10000`.
