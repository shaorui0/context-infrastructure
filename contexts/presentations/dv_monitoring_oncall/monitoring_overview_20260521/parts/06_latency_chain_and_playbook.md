# Latency Chain & Alert Playbook

> Cross-cutting "how do I actually use the monitoring stack when an alert fires" doc.
> Sibling parts 01–05 inventory individual dashboards (SLA / logging / pod & node / DB / VM&alerts).
> This part stitches them together along the request path.

---

## 完整 latency chain 图与每段责任 dashboard

Canonical request path (real-time detection traffic, internal & external):

```
                                                                           ┌──────────────┐
                                                                       ┌──▶│  YugabyteDB  │  (YCQL: features, sessions)
                                                                       │   └──────────────┘
   client ──▶ APISIX ──▶ Ingress(nginx) ──▶ Feature Platform (fp) ─────┤
   (HTTP)    (gateway)  (k8s edge)         (JVM, per-tenant pods)      │   ┌──────────────┐
                                                                       └──▶│   MySQL      │  (rules, config, async update)
                                                                           └──────────────┘
                                                              │
                                                              └─── ext data sources, Hotspot agg, Kafka (async)
```

Three latency "envelopes" you must keep straight (this is the bisection axis):

| Envelope | What it measures | Where it lives |
|----------|------------------|----------------|
| **E2E (client-perceived)** | `client → fp → client` round-trip as observed at our edge | SLA dashboard, Ingress access log `request_time` |
| **Upstream (fp work)** | Time fp pod actually spent on the request | SLA panel "Upstream latency", `upstream_response_time` in ingress log, fp's own `Request duration` histogram |
| **Waiting (network)** | `request_time − upstream_response_time` = network/client side | SLA panel "Waiting Latency between Ingress and Upstream", ingress log derived |

> The "Waiting" envelope is the load-bearing concept. It is computed inside the SLA dashboard
> (`p1KqfRAMk` panel id 373) and is your fast bisection: if Waiting is high but Upstream is flat,
> the bug is *not* ours (client network / ingress LB). See `feedback_sre_triage_workflow.md` —
> first determine nginx vs FP, then branch.

### Per-hop responsibility table

| Hop | Canonical dashboard (UID) | Canonical panel / SLI | "It's this hop" signature | Common root causes |
|-----|--------------------------|-----------------------|---------------------------|--------------------|
| **client → APISIX** | `Apisix Logging` (`0lpCu9kHk`) | "Response time based on Apisix log P99" (panel 8); QPS (panel 6) | APISIX P99 high, but ingress `request_time` flat for the same client. APISIX 4xx/5xx spike upstream of ingress. | APISIX route misconfig, plugin (rate-limit / jwt) latency, APISIX pod CPU saturated, TLS handshake regression. |
| **APISIX → Ingress(nginx)** | `NGINX Ingress controller` (`nginx`); `Debug logs for Ingress-nginx controller` (`HFAlVh2Nz`) | "Ingress Percentile Response Times" (panel 75); `P95/P99 Request Latency` from log (panel 23) | `nginx_ingress_controller_request_duration_seconds` P99 elevated; ingress controller CPU/mem pressure; config-reload failed (`Last Config Failed` panel 83). | Ingress controller pod OOM/restart, recent config reload broken, upstream endpoint list stale (svc churn), `worker_connections` saturated. |
| **Ingress → Feature Platform (waiting)** | `SLA - Batch & RealTime` (`p1KqfRAMk`) panel 373 "Waiting Latency between Ingress and Upstream" | `request_time − upstream_response_time` per client | Waiting envelope > Upstream envelope. Often paired with elevated `Non-200 QPS` panel 194 (esp. 499 = client cancel). | Network between fp and ingress (overlay/VPC), DNS resolution slow, mTLS handshake, client connection-reuse off. |
| **Feature Platform (work)** | `Feature Platform Metrics` (`EP_yHg7Gk`) | "Request duration - Cluster Overview" (panel 6); "Request duration of tenant $tenant" (panel 73); per-pod panel 72 | FP `Request duration` P99 climbing; matches SLA panel 371 "Upstream latency graph (Feature platform)". | GC pause (panel 41), JVM heap pressure (panel 11), thread pool saturated (panels 35/62), tenant-specific rule explosion (panel 9 detection per ruleId), downstream DS slow (panel 69 "External DataSource Query Latency"). |
| **Feature Platform → YugabyteDB** | `YugabyteDB` (`1IGjQaiMk`); `YugaByteDB Connection` (`2nSI2C-Sk`); `YugabyteDB Logging` (`-Sp_UzySz`) | YCQL Op Latency P99 (panel 64); YCQL Inbound Connections (panel 77); RPC queue sizes (panel 71); Reactor Delays (panel 73) | FP `External DataSource Query Latency` (EP_yHg7Gk panel 69) climbs in lockstep with YCQL P99; YCQL `RPC queue sizes` non-zero. | Hot tablet/shard, tserver compaction, tserver CPU saturation, reactor backlog, FP connection-pool exhaustion (EP_yHg7Gk panel 13). |
| **Feature Platform → MySQL** | `MySQL Overview` (`MQWgroiiz`); `MySQL Logging` (`JBBljUMDk`) | "MySQL Connections" (panel 92); "MySQL Client Thread Activity" (panel 10); "MySQL Slow Queries" (panel 48); InnoDB Buffer Pool (panel 51) | FP "FP MySQL Active Connections" (EP_yHg7Gk panel 59) flat at the max, MySQL `Threads_running` spike, slow-query rate up. | Connection pool exhaustion on fp side, slow query without index, replica lag (`mysql_slave_status_seconds_behind_master` panel 401), buffer pool too small for working set. |

> Note on "echo server" vs "internal" SLA dashboards: `p1KqfRAMk` is the multi-cluster shared template;
> per-cluster variants (`Zv5gfxmDz` useast1-prod-a, `LrvYqTiDz` useast1-prod-b, `4igjS1Rvk` uswest2-preprod,
> `b0MtArMvz` useast1-preprod-internal, etc.) are clones with cluster pre-bound. Use the cluster-bound
> one when paged — fewer variables to set.

---

## 5 步通用 oncall 工作流

When ANY alert lands, do exactly these 5 steps before forming a hypothesis. (Aligns with
`bestpractice_traditional_sre_methodology.md` USE/RED method and the `sre-oncall-init` skeleton.)

### Step 1 — Read the alert (no queries yet)

Extract and write down these fields. **If any are missing, STOP and ask** (see
`feedback_sre_triage_workflow.md` — don't guess defaults):

- Severity (P1/P2/P3) and SLO it ties to.
- Cluster (e.g. `useast1-prod-a`, `uswest2-preprod`, `apsoutheast-prod`).
- Namespace + service (e.g. `fea-tenantA`, `ingress-nginx`, `yb-tserver`).
- Event timestamp (epoch). Compute **investigation window = ts ± 3min** (not `now-6h`).
- Affected client / tenant / endpoint if present.
- Metric and threshold from the rule (look it up in `VictoriaMetrics - vmalert` `LzldHAVnz` or
  `Alertmanager View` `asfasqwe2r` if unclear).

### Step 2 — Open the top-of-funnel dashboard

Choose by alert family (always set `cluster`/`namespace` variables first; never browse with defaults):

- Latency / SLA alert → `SLA - Batch & RealTime` (`p1KqfRAMk`), select cluster + client.
- Resource / CrashLoop / OOM alert → `Pod Resources` (`b_XlLjRMz`) or regional `Pod Resources Overview` (`fZQLJjlVz`).
- Error-rate alert → `Debug logs for Ingress-nginx controller` (`HFAlVh2Nz`).
- DB alert → DB-specific (`MQWgroiiz` for MySQL, `1IGjQaiMk` for Yuga).
- Otherwise → `Alertmanager View` (`asfasqwe2r`) to see the firing population first.

### Step 3 — Bisect the latency chain (3-step decision tree)

Walk the SLA dashboard panels in this **order** — the order is the decision tree, not just a checklist. Earlier signals are cheaper to read and can short-circuit later steps.

**Step 3a · Panel 373 "Waiting Latency between Ingress and Upstream"** — your first read.
This panel's literal title says "High latency likely means network issue between client and datavisor." One glance tells you (1) impact magnitude and (2) whether you're in network territory.
- **HIGH** → network / client-side hop. Go straight to Step 4 with `HFAlVh2Nz` + client-side traces. **Do not bother checking Upstream** — the path is already chosen.
- **LOW** → continue to Step 3b.

**Step 3b · Panel 371 "Upstream latency graph (Feature platform)"** — is fp itself slow?
- **HIGH** → FP / DB hop. Drill into `EP_yHg7Gk` (FP Metrics) for pod CPU/GC/connection pool; cross-check `EP_yHg7Gk` panel 69 "External DataSource Query Latency" against DB dashboards.
- **LOW** → continue to Step 3c.

**Step 3c · Infra layer** — Waiting clean + Upstream clean + E2E (panels 192/359) still high.
The latency lives between client→ingress / ingress→FP, i.e., the infra hop itself:
- Ingress controller — `HFAlVh2Nz` + `nginx` controller dashboard (CPU, connections, recent config reloads)
- APISIX — `0lpCu9kHk`
- Triage suspects: recent reload / config push, controller pod CPU saturation, worker_connections exhausted.

**Then Panel 194 "Non-200 QPS"** — orthogonal check: is the SLA dip latency or 5xx/499 ratio? 499 means client gave up (often correlates with high Waiting from Step 3a); 5xx means we failed.

**Why a tree and not a matrix**: Waiting is the cheapest read. When Waiting is high you've already routed yourself; checking Upstream becomes redundant. The old 4-quadrant matrix below is still valid as a static reference, but the tree is the actual oncall flow.

**4-quadrant reference (for cross-validation after the tree)**:

| Upstream high | Waiting high | Interpretation |
|---------------|--------------|----------------|
| Y | N | **FP/DB hop** → go to `EP_yHg7Gk` |
| N | Y | **Network/ingress hop** → go to `nginx` + `HFAlVh2Nz` |
| Y | Y | Backpressure: fp slow → ingress queues fill. Treat as FP first. |
| N | N | Not a real latency event at our edge → look upstream of ingress (APISIX, client side) or it's a false alert (cf. `feedback_loki_metric_debug.md` — disaggregate by `status_code` before alarming). |

### Step 4 — Drill into logs

Pick the log dashboard for the hop you bisected to:

- Ingress 5xx/4xx → `HFAlVh2Nz` panels 40/41, filter by `cluster`+`client`+`interface`, set
  `request_time_operator > X` to capture only slow ones.
- FP application logs → `Feature Platform Log` (`CFAzjjGGz`), narrow to `pod` from step 3.
- APISIX → `Apisix Logging` (`0lpCu9kHk`).
- DB errors → `YugabyteDB Logging` (`-Sp_UzySz`) or `MySQL Logging` (`JBBljUMDk`).
- Generic last resort → `Logging` (`9aBY8rWMz`) with cluster/namespace/pod variables.

**Always use ±3min window**, never the dashboard default. Time-pinned link >> live link.

For programmatic log queries: `rules/skills/dv_loki_fetch.md` (`loki_fetch.py` CLI bypasses
Grafana MCP — needed when you want a full result set, not paginated UI).

### Step 5 — Hypothesis → resources / DB / config

With "where" pinned, ask "why":

- Resources? → `Pod Resources` (`b_XlLjRMz`) for that pod: CPU throttling panel 15, OOM indicator panel 14, restarts panel 7.
- JVM? → `Feature Platform GC Enhanced` (`fp-gc-enhanced-v2`) — GC pause is a top-3 fp latency cause.
- DB? → corresponding DB dashboard, drill from cluster → table → query.
- Config / deploy? → check restart/deploy timeline (panel 7 in `b_XlLjRMz`) and ingress config reloads (`nginx` panel 81/83). Recent deploy within ±15min of event ts is suspect #1.
- VM/alert pipeline itself? → `VictoriaMetrics - vmalert` (`LzldHAVnz`) — is the metric even being scraped reliably? (Loki-derived rule failure is a classic false-alert source.)

Form ONE hypothesis, write it in the incident channel, then verify with one query. Don't action
until verified. K8s mutating ops follow the `# INTENT:` convention in `CLAUDE.md`.

---

## Alert → Dashboard 决策树（每类 alert 一条 playbook）

Each playbook: 3–5 steps, with exact dashboard UID + variables to set + what you're looking for.

### A. "P99 latency SLA breach for client X"

1. Open `SLA - Batch & RealTime` `p1KqfRAMk` → set `client=X`, time window = alert ts ±15min.
2. Compare panel 371 (Upstream) vs panel 373 (Waiting) → bisect FP vs network (Step 3 quadrant table).
3. If FP: open `Feature Platform Metrics` `EP_yHg7Gk` → set `cluster`+`namespace`+`tenant=X`. Check panel 6 (cluster), panel 73 (tenant), panel 72 (per-pod) to localize to a pod. Then check panel 41 GC pause and panel 13 connection pool.
4. If network/waiting: open `Debug logs for Ingress-nginx controller` `HFAlVh2Nz` → set `client=X`, `request_time_operator=>`, `request_time_prerequisite=1`. Look at panel 31 Top 10 Slowest Endpoints.
5. Cross-check the client wasn't sending an unusual payload mix: SLA panels 347/357 "Total QPS by EventType".

### B. "5xx rate from ingress"

1. Open `Debug logs for Ingress-nginx controller` `HFAlVh2Nz` → set `cluster` + leave `client=all`, `interface=all`. Panel 22 "5xx Error Rate", panel 32 "Top 10 Most 5xx Errors", panel 40 raw 5xx logs.
2. Cross-check `NGINX Ingress controller` `nginx` → panel 87 "Ingress Success Rate", panel 83 "Last Config Failed" (recent reload broken?), panel 79/77 CPU/mem on the controller.
3. If 5xx originates upstream (fp), open `Feature Platform Log` `CFAzjjGGz` → narrow to the pod name appearing as upstream in the ingress log. Filter `level=ERROR`.
4. If 502/504 specifically: it's upstream-unreachable / upstream-timeout — jump to playbook **H** (FP upstream timeout).
5. Confirm scope: is it one ingress / one upstream service / one client? If all three, suspect ingress controller itself; if one client, suspect client-specific config.

### C. "Pod CrashLoopBackOff"

1. Open `Pod Resources` `b_XlLjRMz` → set `cluster`+`namespace`+`pod`. Panel 5 "Containers' statuses" + panel 7 "Containers' restarts" — confirm the loop and find restart cadence.
2. Panel 14 "Memory Advance View (OOM Indicator)" — was it OOMKilled? Panel 15 "CPU Throttling" — was it CPU starved into liveness-probe failure?
3. Open `Logging` `9aBY8rWMz` → set same `cluster`/`namespace`/`pod`. Window ts ±5min around last restart. Look at last log lines before crash (panel 2 logs view).
4. If OOM: bump request/limit OR investigate leak (FP → `fp-gc-enhanced-v2` for heap trend).
5. If config/startup error: check most recent deploy via `kubectl rollout history` in that namespace; correlate with restart timestamp.

### D. "Node memory > 90%"

1. Open `Node Exporter Full` `rYdddlPWk` (or `External Node Exporter 0.16+` `9CWBz0bik`) → set `instance=<node>`. Confirm sustained vs spike.
2. Open `Mixin / Compute Resources / Node (Pods)` `200ac8fdbfbb74b39aff88118e4d1c2c` → set node. Identifies top memory-consuming pods on that node.
3. For top offenders: open `Pod Resources` `b_XlLjRMz` per pod → panel 14 OOM indicator. Is one pod leaking?
4. Check pending eviction / system reserve: node-exporter `node_memory_MemAvailable_bytes` vs allocatable. If available > 5%, alert may be noisy (request/limit-based, not actual).
5. Decide: scale node group, cordon+drain, or tune the leaking pod. Never `kubectl delete pod` on prod without `# INTENT:` comment per CLAUDE.md K8s rules.

### E. "ClickHouse / FP CPU spike"

1. FP CPU: open `Pod Resources` `b_XlLjRMz` → set `namespace=fea-*`. Panel 2 CPU + panel 15 throttling. Identify spiking pods.
2. ClickHouse CPU: open `ClickHouse Performance Monitor` `TFajSstMk2` (us-west default) or `TFajSstMk22sdf` (us-east-b). Look for query queue + slow queries.
3. Open `Altinity ClickHouse Operator Dashboard` `clickhouse-operator` for replica / shard health.
4. For FP: cross with `EP_yHg7Gk` panel 35 "Thread Pool Size/Usage" + panel 62 "Thread Tasks Queued" + panel 9 detection-per-ruleId. CPU spike often = rule explosion on one tenant.
5. If correlated with a tenant deploy, roll back the rule change first; tune CPU second.

### F. "Yuga read latency spike"

1. Open `YugabyteDB` `1IGjQaiMk` → set `cluster`+`dbcluster`. Panel 64 "YCQL Op Latency (P99)" — confirm. Panel 33/16 "Select - Op/Sec / Latency / Tserver" — pinpoint hot tserver.
2. Panel 71 "RPC queue sizes (YCQL)" + panel 73 "Reactor Delays" — backpressure signature.
3. Open `YugaByteDB Connection` `2nSI2C-Sk` → panel 8 "Reads IOPS By table" + panel 11/13 Compaction graphs. Hot table or compaction backlog?
4. Open `YugabyteDB Logging` `-Sp_UzySz` for tserver errors around event ts ±3min.
5. Cross with FP side: `EP_yHg7Gk` panel 69 "External DataSource Query Latency" — does it match? If fp's view shows higher latency than tserver's view, suspect network or fp connection-pool, not DB.

### G. "MySQL connection saturation"

1. Open `MySQL Overview` `MQWgroiiz` → set `mysql` instance. Panel 92 "MySQL Connections" — is `Threads_connected` near `max_connections`? Panel 10 "Client Thread Activity" — `Threads_running` spike?
2. Panel 47 "MySQL Aborted Connections" — clients failing handshake (network) vs killed mid-query (timeout)?
3. Cross with FP: `EP_yHg7Gk` panel 59 "FP MySQL Active Connections" + panel 13 "Connection Pool Usage". Pool exhausted on fp side = fp throws and reconnects = MySQL sees churn.
4. Open `MySQL Logging` `JBBljUMDk` window ±5min for "Too many connections" / "Aborted connection" messages.
5. Panel 48 "MySQL Slow Queries" — a single slow query holding connections is a common trigger. Find it via `performance_schema` or slow log.

### H. "FP upstream timeout" (from ingress, e.g. 504)

1. Open `HFAlVh2Nz` → set `client`+`interface` from the alert. Panel 22 5xx rate, panel 40 5xx logs. Confirm code is 504 (upstream timeout) vs 502 (upstream unreachable).
2. Open `EP_yHg7Gk` → set same `cluster`/`namespace`/`tenant`. Panel 6/73 Request duration — is fp actually slow OR returning fast but ingress reading slow?
3. If fp is slow: walk panels 67/71 (AsyncUpdater / Transformer execution time), 69 (External DataSource Query Latency), 47/52 (Hotspot subquery / agg). One of these will spike.
4. If fp looks fast but ingress times out: suspect long-tail tail (fp p99 vs p999) OR slow response body (large payload), OR ingress `proxy_read_timeout` too tight after a recent fp behavior change.
5. Check `Pod Resources` for fp pod restarts during the timeout window (panel 7) — pod restart = in-flight requests time out.

### I. "Ingress → upstream waiting latency high" (network)

1. Open `SLA - Batch & RealTime` `p1KqfRAMk` panel 373 — confirm Waiting envelope is the one elevated. Panel 371 Upstream should be flat.
2. Open `NGINX Ingress controller` `nginx` panels 32 (Network I/O pressure), 82 (Controller Connections). Saturated NIC or connection pool on the controller?
3. Open `Pod Resources` for the ingress-nginx pod itself (namespace `ingress-nginx`) — CPU throttling or restarts?
4. Check overlay/CNI: `External Node Exporter` `9CWBz0bik` per node for the node hosting fp pods — `node_network_*_dropped`, conntrack saturation.
5. If only one client: client-side connection-reuse off (forces TCP+TLS each request). Confirm via APISIX log `Apisix Logging` `0lpCu9kHk` — short-lived connections show as high "Response time" with low fp work.

### Quick-reference table

| Alert family | First dashboard (UID) | Bisect with | Drill log dashboard |
|--------------|----------------------|-------------|---------------------|
| SLA P99 breach | `p1KqfRAMk` | panel 371 vs 373 | `HFAlVh2Nz` |
| Ingress 5xx | `HFAlVh2Nz` | panels 22/32 | `HFAlVh2Nz` panel 40 |
| CrashLoop | `b_XlLjRMz` | panel 5/7/14 | `9aBY8rWMz` |
| Node mem >90% | `rYdddlPWk` | top pods on node | `200ac8fdbfbb74b39aff88118e4d1c2c` |
| FP CPU spike | `b_XlLjRMz` + `EP_yHg7Gk` | panel 35/62/9 | `CFAzjjGGz` |
| ClickHouse CPU | `TFajSstMk2` / `clickhouse-operator` | slow queries | – |
| Yuga read latency | `1IGjQaiMk` | panel 64/71/73 | `-Sp_UzySz` |
| MySQL conn saturation | `MQWgroiiz` | panel 92/10 | `JBBljUMDk` |
| FP upstream timeout | `HFAlVh2Nz` → `EP_yHg7Gk` | panel 69/67/71 | `CFAzjjGGz` |
| Ingress→upstream waiting | `p1KqfRAMk` panel 373 | `nginx` panel 32/82 | `9aBY8rWMz` (ingress-nginx ns) |

---

## 其他值得知道的 dashboard（top N）

Beyond the six core dashboards covered in parts 01–05, these are the most useful auxiliary
dashboards on this Grafana instance. (Discovered via `mcp__grafana__search_dashboards`.)

1. **`Alertmanager View`** (`asfasqwe2r`) — global view of currently firing alerts. Step 1 sanity check: am I the only one paged, or is this a fleet event?
2. **`VictoriaMetrics - vmalert`** (`LzldHAVnz`) — vmalert rule health: which rules are firing, which are errored. **Critical when you suspect a false alert** (recording-rule pipeline issue — cf. `feedback_loki_metric_debug.md`).
3. **`VictoriaMetrics - Alert statistics`** (`ehXxUsGSk`) — historical alert volume, useful for retro and trend analysis.
4. **`Alert Management Latency`** (`aOCPPCzIz`) — measures how long alerts take to flow through; useful when you suspect "I was paged late".
5. **`Feature Platform GC Enhanced`** (`fp-gc-enhanced-v2`) — JDK17 GC deep-dive. Reach for this any time FP latency P99 has long-tail spikes that don't correlate with QPS.
6. **`Feature Platform Log`** (`CFAzjjGGz`) — fp application logs, pre-filtered (vs generic `Logging`). Default drill-down when FP is the suspect hop.
7. **`Horizontal Pod Autoscaler (HPA)`** (`nonVosiNk`) — when traffic spikes and you wonder why autoscaling didn't catch up.
8. **`NGINX Log Metrics`** (`4aBQsjSmz`) — alternative ingress view derived from logs (vs metric-derived `nginx`); good when controller `/metrics` is unreliable.
9. **`Ingress Traffic Report`** (`fomKvtMSz`) — traffic share by client/endpoint, useful for capacity discussions and noisy-neighbor detection.
10. **`Mixin / Compute Resources / Node (Pods)`** (`200ac8fdbfbb74b39aff88118e4d1c2c`) — node-to-pod mapping with resource usage. The right dashboard for "which pod is eating this node's memory".
11. **`Pod Resources Overview`** (`fZQLJjlVz`) and regional variants (`f3qP_u_4k` US-East, `9DWRXX_Vk` US-West, `RiZfbC_Vz` EU-West, `IRTZfX_4k` AP-SouthEast, `LKtobj_Vz` CA-Central) — fleet view; faster than picking a single pod when triaging "which one's broken".
12. **`Dapp Kafka`** (`bFRArXtIz`) and `Kafka Exporter for all` (`cluster_kafkfa_exporter`) — for async pipelines (postback, detection result fan-out). Consumer lag is a classic delayed-symptom of an upstream problem.
13. **`ClickHouse Performance Monitor` / `Performance 2`** (`TFajSstMk2`, `TFajSstMk22`) — when CI / analytics layer is the suspect.
14. **`Logging SC`** (`YBAKRjENk`) — service-component-scoped logging view; useful when you have a service name but not a pod.

---

## 与已有 skill / memory 的对接点

This playbook is the "top of the funnel". Hand off to existing skills as soon as the alert is
classified.

### Skills (rules/skills/)

- **`rules/skills/bestpractice_traditional_sre_methodology.md`** — USE / RED / Golden Signals. Step 3 bisection table is the RED method applied to our latency chain.
- **`rules/skills/bestpractice_sre_reliability_models.md`** — error budgets, SLI/SLO. Reference when deciding whether an alert is worth waking someone up vs ticket-only.
- **`rules/skills/dv_loki_fetch.md`** — `loki_fetch.py` CLI for direct Loki queries when Grafana MCP is too slow or you need a full result set (e.g., dumping all 5xx logs in a 10-min window for offline grep).
- **`rules/skills/workflow-oncall-spike`** (file: `rules/skills/workflow-oncall-spike.md` if present, otherwise the Phase-1/Phase-2 pattern from the feedback memory) — two-phase triage: Phase 1 determines nginx vs FP, Phase 2 deep-dive on the chosen branch. Use directly after Step 3 bisection above.
- **`rules/skills/sre-vm-query.md`** — VictoriaMetrics MCP usage patterns (label filter rules, step floor, time ceiling). Apply to every PromQL query you write in Step 3/5.

### Archived `sre-oncall-*` family

Per `ls archives/skills/` the archived SRE-oncall skills directory was not found at the time of
this writing; if you create one, the natural home for:

- `sre-oncall-init` — Layer-0 skeleton creation (extract signals → route to type skill).
- `sre-oncall-acceptance-criteria` — the 8 convergence conditions for closing an investigation.
- `sre-oncall-output-format` — 9-section output format.
- `sre-oncall-query-safety` — label-filter / step-floor / retry-budget rules.
- `sre-oncall-compound-learning` — post-investigation knowledge flywheel.

These are listed in the active skill catalog (slash-commands like `/sre-oncall-init` are
documented in the global skill index) but not under `rules/skills/` or `archives/skills/` on
disk. Treat them as the runtime layer that wraps this playbook.

### Memory (auto-loaded)

- **`feedback_sre_triage_workflow.md`** — plan-first, ±3min windows, stop on missing fields, fast/slow phases. **This drives Step 1 of the universal workflow.**
- **`feedback_loki_metric_debug.md`** — disaggregate by `status_code` before alarming on a Loki-derived metric. **This drives Step 5 when the suspect is the alert pipeline itself.** Sequence: rule health → raw counter smoothness → per-`status_code` rate → burst cadence.
- **`feedback_subagent_write_tool.md`** — operational reminder when delegating any sub-step of this workflow to a subagent.
- **`reference_loki_config.md`** — tenant → cluster mapping; needed whenever Step 4 (log drill) crosses regions.

### How they chain in practice

```
alert fires
  └─ feedback_sre_triage_workflow.md  → Step 1 (signals, ±3min, stop-if-missing)
       └─ this playbook              → Steps 2–3 (top-of-funnel, bisect)
            └─ playbook A–I          → 3–5 step drill for the alert family
                 └─ dv_loki_fetch    → bulk log pull if Grafana UI insufficient
                 └─ sre-vm-query     → safe PromQL/VM queries for Step 5
                 └─ feedback_loki_metric_debug → if metric itself is suspect
            └─ sre-oncall-output-format → write up the 9-section report
            └─ sre-oncall-compound-learning → distill new feedback memory if novel
```

Keep the loop tight: every novel finding from a real incident should land back as a new
`feedback_*.md` in `contexts/memory/` so the next on-call gets the benefit.
