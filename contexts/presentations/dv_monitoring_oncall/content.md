# Content — DataVisor Monitoring Tour & Oncall Onboarding

> Reverse-extracted from `slides_*.html` as the canonical text source.
> **Workflow**: edit this file → re-run Phase 3 subagents to re-render HTML.
> See [workflow_presentation_slides_v2.md](../../../rules/skills/workflow_presentation_slides_v2.md) Phase 2.5.

- **Audience**: DV engineers / new oncall / anyone inheriting monitoring (assumes k8s + Prometheus basics)
- **Core thesis**: DV's monitoring stack isn't complex — three things get you to oncall productivity: (1) where the entry points are, (2) how to bisect the chain, (3) how alerts route
- **Length**: ~20-25 min, 12 slides
- **Source**: `contexts/survey_sessions/monitoring_overview_20260521/REPORT.md`

---

## Slide 1: DataVisor Monitoring Tour

**Layout**: title-slide
**Core claim**: 20 minutes covers three things — architecture, latency chain bisection, alert→playbook routing. After this you can handle 80% of alerts on your own.
**Subtitle**: From Slack alert to root cause — an onboarding deck for new oncall
**Footer**: 2026-05-21 · Based on monitoring_overview_20260521 survey
**Visual**: Three icon columns under the title — (1) stacked-rectangles icon labeled "Monitoring Architecture", (2) three-circle chain icon labeled "Latency Chain Bisection", (3) home/box icon labeled "Alert → Playbook Routing"
**Notes**: This is the cover. Opener: "Today's 20 minutes is three things — architecture, chain, routing. By the end you can independently handle 80% of alerts."

---

## Slide 2: Monitoring Stack Architecture (one picture)

**Layout**: split (3fr left diagram / 2fr right cards)
**Core claim**: Metrics all live in VictoriaMetrics, alerts all go through **vmalert** (NOT Grafana managed alerting), logs all live in Loki with multi-tenancy.
**Visual**: Top row — six k8s cluster boxes (aws-prod-a, aws-prod-b, aws-pci, gcp-prod-a, aws-mgt, sandbox) feeding orange arrows down into a navy VictoriaMetrics box (`vm-mgt-a.dv-api.com`, "primary metrics backend", "+ Deepflow-Prometheus as fallback DS"). vmalert sidecar attached to VM ("540 rules"). vmalert → alertmanager box → Slack. Grafana box pulls from VM. Loki sits as a side branch at the bottom ("multi-tenant: prod / nonprod", "logs path independent · does not go through vmalert"), with dashed lines from the cluster row.
**Right cards**:
- **Metrics backend** — VictoriaMetrics @ `vm-mgt-a.dv-api.com`. Deepflow-Prometheus as backup datasource.
- **Alerting** — **540 rules** running on vmalert. Grafana managed alerting is not enabled.
- **Logs** — Loki multi-tenant. tenant = `prod` / `nonprod`.
**Notes**: Emphasize "alerts all go through vmalert" — this is the #1 misconception for new oncall. Grafana's left-sidebar Alerting is empty; check vmalert UI or alertmanager for alert state.

---

## Slide 3: Before Your First Page

**Layout**: 3-column grid (1fr / 1.2fr / 1fr)
**Core claim**: Three things to memorize before pager goes off — entry URLs, severity SLAs, and the cluster-name → tenant trap.
**Column 1 — Entry URLs**:
- **Grafana** — `grafana-mgt.dv-api.com` (SSO + VPN)
- **VictoriaMetrics** — `vm-mgt-a.dv-api.com/vmui/` (raw queries)
- **Alertmanager** — `k8s-us-mgt-a.dv-api.com/alertmanager/` (silence ops)

**Column 2 — Severity → Response SLA** (table):
| Severity | Response | Routing |
|---|---|---|
| CRITICAL | Immediate | Single rule: `LokiPanics` |
| PAGER | 5 min | PagerDuty |
| HIGH | 30 min | Slack high-priority |
| MEDIUM / WARNING | Business hours | Slack default |
| No severity (91 rules) | default | Often dropped |

**Column 3 — Cluster naming trap**:
- `aws-*-prod-*`, `*-pci-*`, `*-mgt-*`, `*-sandbox-*` → Loki tenant **prod**
- `aws-*-dev-*`, `*-preprod-*` → tenant **nonprod**
- ⚠️ **Biggest trap**: `gcp-uswest1-prod-a` has `prod` in its name but tenant is **nonprod**

**Notes**: This is the one slide in the deck worth printing and taping to your monitor.

---

## Slide 4: Latency Chain Mental Model

**Layout**: single full-width SVG, navy banner at bottom
**Core claim**: Every request crosses client → APISIX → Ingress(nginx) → Feature Platform → YugabyteDB / MySQL. Each hop has a dashboard. Memorize the chain; bisection becomes mechanical.
**Visual**: Horizontal flow — 5 boxes in a row (client → APISIX → Ingress(nginx) → Feature Platform(fp) → branching to YugabyteDB(YCQL) above and MySQL below). Under each box, the data source label and the dashboard UID in monospace orange:
- APISIX → `Apisix Logging` → `0lpCu9kHk`
- Ingress → `nginx` → `HFAlVh2Nz`
- Feature Platform → `Feature Platform Metrics` → `EP_yHg7Gk`
- YugabyteDB → `1IGjQaiMk`
- MySQL → `MQWgroiiz`

Orange arrows between boxes. Navy banner at bottom (white text):
> Every hop has a dashboard · the SLA dashboard is the top entry — it tells you which hop is slow

**Notes**: This diagram is the skeleton for every playbook that follows. Next slide shows how the SLA dashboard does bisection along this chain.

---

## Slide 5: Core — SLA Dashboard 3 Panels + Decision Tree

**Layout**: single column. Top: segment-map SVG (~280px tall) showing which panel measures which hop. Middle: decision tree (~420px tall). Bottom: caveat card.
**Core claim**: The 3 SLA panels each measure a **specific segment** of the request path, based on nginx access-log fields `request_time` and `upstream_response_time`. Knowing which segment each panel covers tells you exactly where the slowdown lives.
**Subtitle**: Three panels, three questions, in order — that's the whole latency triage.

**Panel → segment map** (top section, SVG horizontal timeline):

Visualize the request path left-to-right as boxes connected by arrows:
```
client ──[A: net+TLS]──▶ Ingress(nginx) ──[B: nginx work + net C]──▶ FP pod ──[D: DB call]──▶ Yuga/MySQL
        ◀───────────── all measured AT nginx ──────────────────────◀
```

Then under the chain, three colored horizontal bars showing each panel's measured range:

| Panel (logql field) | Measures (segments) | What it tells you |
|---|---|---|
| **Response Percentiles `request_time`** (192/359) | **A + B + C + D + C' + B' + A'** — the full round-trip at nginx vantage (from receiving client's first byte to writing the last byte back) | "Is there actually a latency event at the edge?" |
| **Upstream latency `upstream_response_time`** (371) | **C + D + C'** — only the part where nginx is waiting for FP (network nginx↔FP + FP work + FP's own DB calls) | "Is FP (+ its DB) slow?" Note: includes DB time, not just FP CPU |
| **Waiting Latency `request_time − upstream_response_time`** (373) | **A + B + B' + A'** — everything OUTSIDE the upstream call (client↔nginx network + nginx's own work + slow consumer) | "Is the client/network the bottleneck?" One glance gauges impact + network suspicion |
| **E2E real-time (ALB + ApiGateway)** | Extends the chain LEFT to include AWS load balancer (ALB) + ApiGateway. Use when client traffic goes through AWS edge before hitting our ingress | "Is the latency added at AWS layer, before our nginx?" |

**Critical nuance**: `upstream_response_time` (panel 371) **includes FP's downstream DB calls** because FP holds the request until DB returns. So panel 371 spiking + Yuga/MySQL panels also spiking → DB is the root, not FP code itself.

**Phase-2 evidence**: before going deep, also open `Multi-Cluster Traffic Distribution` (UID `X2qhqpjSk`) — panel 9 piechart `by (cluster)` tells you whether this client's traffic is currently hitting cluster A or B (or split). Useful when alerts say "cluster=aws-apsoutheast1-prod" but the underlying physical cluster is `-a` vs `-b`. Caveat: this dashboard is Loki-driven with 1m/5m/10m `timeFrom` offsets — not real-time, treat as a "where did the traffic go" sanity check, not a latency root-cause tool.

**Decision tree** (the actual oncall flow — render as SVG with three branches):

```
Latency alert fires
        │
        ▼
┌──────────────────────────────────────────────────────┐
│ Step 1: Waiting Latency (panel 373) — one glance     │
│ "How much impact, and is it network?"                │
└──────────────────────────────────────────────────────┘
        │
        ├─── HIGH ──▶  Network / client side
        │              (client ↔ datavisor net, ELB, CDN, client timeout)
        │              Drill: ingress-nginx logs, client-side traces
        │
        └─── LOW ───▶  Step 2: Upstream latency (panel 371)
                       "Is FP slow?"
                              │
                              ├─── HIGH ──▶  FP / DB slow
                              │              Go to EP_yHg7Gk
                              │              Drill: FP pod metrics, GC,
                              │              connection pool, DB latency
                              │
                              └─── LOW ───▶  Step 3: Infra layer
                                             (FP fast + network fast)
                                             • Ingress (nginx) — HFAlVh2Nz
                                             • APISIX — 0lpCu9kHk
                                             • Recent reload / config push?
                                             • Controller CPU / connection saturation?
```

**Caveat card** (orange, below the tree):
- 499 = client disconnected, **not counted in SLA**, suspect client network first
- 200/400/429 all count as success (4xx = request format issue, not our fault)
- `proxy_upstream_name=~".*backup.*"` is excluded
- ⚠️ Panel 371/373 unwrap fields are inferred from semantics (pattern was truncated by MCP); confirm in Grafana UI before first use

**Notes**: This is the deck's most-used slide. The tree is the actual order an experienced oncall walks. Start with Waiting because it's the cheapest read — high Waiting immediately scopes you to network/client side, no need to look at the other two. Only when Waiting is clean do you check Upstream. If both are clean but Response Percentiles is high, the latency is happening BETWEEN client→ingress and ingress→FP — that means infra layer (ingress controller, APISIX, recent config push).

---

## Slide 6 (NEW): Example 2 — Kafka Lag / MirrorMaker Triage

**Layout**: top-half architecture diagram + middle alert-family table + bottom 4-step triage flow
**Core claim**: The second most common alert family. Two alertnames sit on **two different dashboards** — getting these mixed up is the #1 mistake. MirrorLag v2 is for replication (MM2 between clusters); Kafka Exporter is for any business consumer group.

**Architecture** (top SVG, ~200px tall):
Two Kafka clusters side-by-side with MirrorMaker2 (MM2) in the middle, arrows in BOTH directions (bidirectional replication):
```
┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
│  Kafka cluster  │ ◀──── │  MirrorMaker2   │ ────▶ │  Kafka cluster  │
│   cluster_a     │ ────▶ │  (Kafka Connect)│ ◀──── │   cluster_b     │
│  (source side)  │       └─────────────────┘       │  (target side)  │
└─────────────────┘                                 └─────────────────┘
```
Below the diagram, key facts:
- **DV-specific topology**: NO `<source>.<topic>` renaming. Same topic name lives on BOTH clusters; direction is encoded in `source` / `target` labels.
- Metric: `kafka_mirror_sync_lag{source, target, topic, partition}` (record count, NOT seconds)
- Direction: bidirectional (a→b AND b→a are both monitored)

**Two alert families** (middle table — easy to confuse):

| Alertname pattern | Severity | What it means | First dashboard |
|---|---|---|---|
| `MirrorMakerConsumerLagDecliningTooSlow` | PAGER | MM2 replication slow. Decline-rate check: `(L_5m_ago − L_now) / L_5m_ago < 0.3` AND `L_now > 500`. Group `kafka` in `kafka_rules.yml`. | **MirrorLag v2** (`-N7cUPZNk`) |
| `Kafka_*_consumergroup_lag_High` (cm/fp/detection/VelocityDetail*/etc.) | HIGH | Business consumer group can't keep up with topic. Per-client variants exist (galileo/onefinance/tabapay/wex…). | **Kafka Exporter for all** (`cluster_kafkfa_exporter`) |

**4-step triage flow** (bottom):

```
Step 1 · Read alertname
    ├─ MirrorMaker* → MirrorLag v2 (`-N7cUPZNk`)
    └─ Kafka_*_consumergroup_lag_High → Kafka Exporter (`cluster_kafkfa_exporter`)

Step 2 · Set variables
    MirrorLag v2: cluster (group prefix), namespace, topic
    Exporter:    pod (binds to one Kafka cluster), topic, consumergroup

Step 3 · Read the primary panel
    MirrorLag v2: panel 1 (MM2 pod `up`) + panels 2/3 (lag a→b, b→a timeseries)
    Exporter:    panel 12 "Lag by Consumer Group" (per cg+topic+partition)

Step 4 · Diagnose root
    ① MM2 pod down → restart (check k8s pod state, this is most common)
    ② Lag stuck + consumer offset rate ≈ 0 → consumer crashed
    ③ Lag growing + producer rate > consumer rate → consumer can't keep up
       (downstream FP slow / CPU / GC). Compare exporter panel 3 (produce) vs 4 (consume).
```

**Caveat card** (orange, ~3 bullets):
- Alert `MirrorMakerConsumerLagDecliningTooSlow` namespace filter is hardcoded `prod|pci|gov|demo` — `useastprod`-style namespaces are NOT covered. If MM2 is failing there, this alert won't fire.
- Default MirrorLag dashboard window is 30m — for alerts that fired 20-30min ago, expand to 1h to actually see the trend that triggered.
- `cluster` variable in MirrorLag v2 is `kubernetes_cluster_groups` (e.g. `aws-uswest2-prod`), without the `-a`/`-b` suffix.

**Notes**: This is the second most common alert family — see slide 9 stats, Kafka-related firings account for a large slice. The #1 mistake is opening Kafka Exporter for a MirrorMaker alert (or vice versa) and seeing the wrong picture. Always reverse-match alertname first.

---

## Slide 7: 6 Core Dashboards Quick Reference

**Layout**: split-2-1 (table left, cards right)
**Core claim**: Six dashboards cover 80% of daily entry points; four more for deep-dive.
**Subtitle**: 80% daily entries + 4 deep-dive helpers.

**Main table**:
| UID | Name | When to use |
|---|---|---|
| `p1KqfRAMk` | SLA - Batch & RealTime | **Always first** (customer-facing / latency / SLA) |
| `HFAlVh2Nz` | Debug logs for Ingress-nginx | Slice nginx access log by client/status/latency |
| `9aBY8rWMz` | Logging (generic) | Free-form pod log exploration |
| `b_XlLjRMz` | Pod Resources | Single pod CPU/mem/restart/IO |
| `sNt6IXzGk` | Node Resource | Node-level pressure |
| `1IGjQaiMk` | YugabyteDB | YCQL latency, tserver overload |
| `MQWgroiiz` | MySQL Overview | Connections / slow queries / replication lag |

**Right — Helper dashboards** (cards):
- `EP_yHg7Gk` — Feature Platform Metrics (FP P99 / GC / connection pool)
- `LzldHAVnz` — vmalert (when you suspect false firing)
- `asfasqwe2r` — Alertmanager View (how many firing now)
- `fp-gc-enhanced-v2` — FP GC deep dive

**Footer**: Treat the UID as the dashboard's real name — the URL is `grafana-mgt.dv-api.com/d/<UID>`.
**Notes**: The first 6 cover 80% of daily entries. The 4 helpers are deep-dive only. UID is the dashboard's real name; just paste it after `/d/`.

---

## Slide 8: 5-Step Universal Oncall Workflow

**Layout**: single full-height SVG with vertical numbered flow
**Core claim**: Build muscle memory for 1 → 1.5 → 2 → 3 → 4 → 5. Step 1.5 is the most-skipped, most-time-saving step.
**Subtitle**: Muscle memory: 1 → 1.5 → 2 → 3 → 4 → 5.

**Steps** (numbered circles down the left, text to the right):
1. **Read the alert (don't query yet)** — Grab severity / cluster / namespace / ts / client / metric + threshold. Stop if any field is missing. Compute window: ts ± 3min (widen 2× if rule eval interval > 5min).
1.5. **Click the alert's source URL** (orange) — Drops you straight into vmui with the current value; pull window to 24h to check if it's chronic noise.
2. **Open the funnel-top dashboard** — Decided by alertname (see routing table on Slide 8).
3. **Bisect on the SLA dashboard using the 4 quadrants** — Order: panel 192/359 → 371 → 373 → 194.
4. **Drill into logs** — Window ±3min, use a time-pinned link.
5. **Write one-sentence hypothesis → one query to verify → then act** (teal) — Any K8s mutating op must be prefixed with `# INTENT:`.

**Notes**: These 5 steps are muscle memory. Step 1.5 is the easiest to skip but the biggest time-saver — vmalert's source URL drops you into vmui with the exact PromQL the alert was firing on.

---

## Slide 9: Alert → Playbook Routing Table

**Layout**: full-width table + orange note card below
**Core claim**: Eleven alert families map to playbook letters A-K, each with a first-dashboard. K (noise judgment) handles the majority of current firings.
**Subtitle**: alertname pattern → playbook letter → first dashboard.

**Routing table**:
| Alertname pattern | Playbook | First dashboard |
|---|---|---|
| `RTIngress*` / `Apisix*` / `IngressNginx*` / `Aws(Alb|ApiGateway)*P9*` | A | `p1KqfRAMk` |
| `*5xx*` / `*Non200*` | B | `HFAlVh2Nz` |
| `K8sPod*Killed` / `*Restarted*` / `OomKiller` | C | `b_XlLjRMz` |
| `K8sNode*` / `Node*Disk*` / `Node*Memory*` | D | `sNt6IXzGk` |
| `HighCpuUsageOfContainer*` / FP CPU spike | E | `b_XlLjRMz` + `EP_yHg7Gk` |
| `Yuga*` / `yugabytedb*` | F | `1IGjQaiMk` |
| `Mysql*` / `MySQLReplication*` / `Hikari*` | G | `MQWgroiiz` |
| `K8sFP*Non200` / FP 504 | H | `HFAlVh2Nz` → `EP_yHg7Gk` |
| Ingress → upstream waiting | I | `p1KqfRAMk` panel 373 |
| Suspect false firing / unstable metric | J | `LzldHAVnz` |
| **`FPTopicsOffsetIncreaseZero*`** etc. (67% of firings) | **K** (noise check first) | vmui source URL |

**Orange note**:
> Of the current 932 firing alerts, 469 (50%) are `FPTopicsOffsetIncreaseZero` + per-client variants. **Judge whether it's chronic noise first**: pull the vmui source URL window to 24h to see persistence, then decide whether to act.

**Notes**: Slack shows real alertnames like `RTIngressP99ResponseTime_Affirm` — reverse-match by pattern to the playbook letter, then go to the first dashboard. Full playbook steps live in REPORT §5 and parts/06.

---

## Slide 10: Alerting System — Current State

**Layout**: 5-stat row on top, horizontal bar chart below
**Core claim**: 540 rules, 932 firing — but 67% of firings come from TOP 3 alerts. 91 rules have no severity label, 79 have no team label. Noise tax is concentrated.
**Stats row** (5 columns):
- **540** — alerting rules (navy)
- **0** — recording rules (in recored.yaml) (orange)
- **932** — currently firing (orange)
- **67%** — TOP 3 alerts' share of firings (orange)
- **91** — rules missing severity label (yellow)

**Bar chart** (horizontal bars, descending):
- `FPTopicsOffsetIncreaseZero` — **469** (orange, full opacity)
- `KafkaEventExporterApplicationStderrErrors` — **97** (orange, 0.7 opacity)
- `FPRuleCountZero` — **59** (orange, 0.5 opacity)
- `QpsZero` — **32** (navy, 0.5 opacity)
- `yugabytedbExternalLocalDiskUsageHigh` — **25** (navy, 0.5 opacity)

**Footer**:
- Severity distribution: PAGER 142 / HIGH 283 / MEDIUM 18 / WARNING 6 / CRITICAL 1 (LokiPanics) / **no severity 91**
- Team distribution: fp 276 / infra 181 / decision 5 / **no team 79** (source of routing inaccuracy)

**Notes**: 67% of alert volume concentrates in TOP 3, mostly `FPTopicsOffsetIncreaseZero` alone. This is the single biggest source of oncall noise tax — see Playbook K, judge noise before triage.

---

## Slide 11: TOP 5 Pitfalls

**Layout**: 2×2 grid + 1 full-width card at bottom
**Core claim**: Five highest-step-rate pitfalls across SLA dashboard, Loki, PromQL, and Node Resource panels.
**Cards** (all orange-tinted):
1. **OOM uses `container_memory_working_set_bytes`** — Not RSS, not usage. Pod Resources panel 14. working_set includes active anonymous + active file cache, which is what the cgroup OOM killer judges against.
2. **After switching `client` on SLA dashboard, re-pick `Batch_Pipeline`** — Switching `client` requires re-picking `Batch_Pipeline`/`pipeline`. The two variables aren't linked; the Batch row goes falsely blank and makes you think batch is offline.
3. **`gcp-uswest1-prod-a`'s Loki tenant is `nonprod`** — The name misleads. When you script a query and forget `LOKI_ORG_ID=nonprod`, you get empty results.
4. **Always add a cluster filter to PromQL** — Unfiltered `rate(kubernetes_monitoring_request_total_ingress_nginx[1m])` scans the whole table on VM, averaging 2.9 seconds per call — 117s of CPU per 10min.
5. **Node Resource's `$nodeHost` must select a specific IP, not `$__all`** (full width) — Otherwise it averages/sums all node metrics across the cluster, hiding single-node hot spots. Node-dimension panels are almost all aggregated by instance; `All` is self-deception.

**Notes**: These 5 have the highest step-rate. Full list of 20 pitfalls in REPORT §7, spanning SLA dashboard, Logging, Pod/Node, DB, and VM/alert — 5 domains.

---

## Slide 12: How to Edit / Add Alerts

**Layout**: split-2-3
**Core claim**: Alerts live in the `infra` repo. VM is primary, Prometheus is the compatibility backup — you must edit both. Always include `severity` and `team` labels.

**Left — Repo paths** (code block):
```
infra repo:
~/work/work-harness/code_repos/infra

core/src/monitorV3/
├── victoriametrics/alerts/
│   ├── *.yml  (33 files, by topic)
│   └── recored.yaml      ← Recording rule
│                           (typo preserved)
├── prometheus/
│   ├── alerts/           ← Compatibility backup
│   │                       must sync-edit
│   └── alertmanager/
│       └── config.yml    ← Receiver
│                           / route / Slack
└── scripts/
    generate_*_alerts.{py,sh}
```
**Caption**: VM primary / Prom backup. vmalert actually runs the VM set.

**Right — Edit-alert workflow** (numbered list):
1. Sync-edit both yamls (VM primary, Prom backup)
2. PR + lint CI → merge to main
3. CI auto-syncs; visible in vmui Alerts/Groups within minutes
4. Verify: search alertname in the vmui Alerts tab

**Required labels for new rules** (orange card):
- `severity` — currently 91 rules missing
- `team` — currently 79 rules missing
- Don't use alertname suffixes for per-client splits (e.g. `_Affirm`, `_Nasa`) — use the `client` label

**Notes**: VM is the primary alert rule set, Prom is compatibility backup — historical reason, you must edit both. New rules without severity/team labels route inaccurately and get dropped into the default channel.

---

## Slide 13: 30-Second Elevator Summary

**Layout**: full-width blockquote on top, 3-card row below, centered Q&A footer
**Core claim**: Three-layer stack, latency chain decides dashboard order, SLA dashboard is always first, and four lifelong rules (PromQL filter, working_set, specific IP).

**Blockquote** (orange left border, 4 paragraphs):
> Monitoring is three layers: metrics all in **VictoriaMetrics**, alerts all through **vmalert** (not Grafana managed), logs all in **Loki** multi-tenant.
>
> When things break, dashboard order is decided by the **latency chain**: client → APISIX → ingress → fp → yuga/mysql.
>
> First stop is always the **SLA dashboard** (`p1KqfRAMk`) — use panels 371 / 373 / 194 for bisection: fp slow, network slow, or client closed early.
>
> Always add a cluster filter to PromQL. OOM uses working_set, not RSS. Node variables always pick a specific IP.

**3 cards** (teal):
- **Full report** — `contexts/survey_sessions/monitoring_overview_20260521/REPORT.md` (10 sections + 11 playbooks + 20 pitfalls)
- **Skill entry** — `/workflow_dv_monitoring_oncall` (`rules/skills/workflow_dv_monitoring_oncall.md`)
- **Coming next** — alertmanager `-notifier.url`, Grafana OnCall scheduling, recording-rule online reload validation

**Footer**: Questions? (centered, light)
**Notes**: This single slide is the 30-second takeaway. All details have indexes in REPORT.md; the skill entry is invocable via `/workflow_dv_monitoring_oncall`.
