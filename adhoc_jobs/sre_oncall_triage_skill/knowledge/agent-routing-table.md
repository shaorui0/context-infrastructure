---
metadata:
  kind: agent-routing-table
  status: v0.1-draft
  schema_version: "0.1"
  derived_from:
    - cases/case-monitoring-alert-delay-histogram-skew.trace.md
    - cases/case-clickhouse-connection-refused-troubleshooting.trace.md
    - cases/case-kafka-lag-issues.trace.md
---

# Agent Routing Table

> This is the orchestrator's first decision layer.
> Given an incoming alert signal, route to the correct cluster triage policy.
> Each cluster has its own decision trace and triage policy (see `.trace.md` files).

---

## Step 0: Input Intake

| Input Type | Action | Then |
|------------|--------|------|
| Slack link (`*.slack.com/archives/*/p*`) | Parse URL → fetch message via Slack MCP (`mcp__slack__slack_list_messages`) → extract alert text. See `facets/slack_alert_intake.md`. | Proceed to Signal → Cluster Routing with extracted text |
| Raw alert text / Slack message paste | Use directly | Proceed to Signal → Cluster Routing |

---

## Signal → Cluster Routing

| Signal Pattern | Key Discriminator | → Cluster | → Triage Policy |
|----------------|-------------------|-----------|-----------------|
| P99 latency high, error_rate normal | latency without errors = suspect observability | Cluster 4 — False signals | `histogram-skew-false-p99` |
| P99 latency high, error_rate elevated | real user impact | Cluster 1 or 3 | service-specific policy |
| connection refused (TCP) | "refused" = nothing listening | Cluster 1 — Routing/DNS/Ingress | `connection-refused-layered-triage` |
| connection timeout (TCP) | "timeout" = packet lost | Cluster 1 — Routing/LB/Network | `connection-timeout-routing-triage` (TBD) |
| kafka consumer lag, multi-topic same CG | systemic → check sink first | Cluster 3 — Stateful pressure | `kafka-lag-downstream-write-bottleneck` |
| kafka consumer lag, single topic/partition | isolated → check consumer/broker | Cluster 3 variant | `kafka-lag-consumer-partition-triage` (TBD) |
| pod Pending / FailedScheduling | can't place workload | Cluster 2 — Scheduling/Capacity | `pod-scheduling-failure-triage` (TBD) |
| pod Evicted / DiskPressure | node pressure | Cluster 2 — Node pressure | `node-disk-pressure-triage` (TBD) |
| AccessDenied / 403 / UnauthorizedOperation | identity/permissions | Cluster 5 — Identity/Access | `iam-access-denied-triage` (TBD) |
| post-upgrade regression | change management | Cluster 6 — Upgrades/Changes | `upgrade-regression-triage` (TBD) |
| single-tenant QPS spike, request_time up but upstream flat / per-partition throughput ceiling | demand > a layer's provisioned capacity | Cluster 7 — Overload/Capacity | `large-tenant-qps-joint-mitigation` — stop bleeding (limit/degrade/split) then scale within caps; see `cases/case-large-tenant-qps-spike-joint-mitigation.md` |
| multi-tenant helm install fails + `x509: certificate signed by unknown authority` + webhook name | admission webhook caBundle stale post-upgrade | Cluster 6 — Change Management | see `cases/case-ingress-nginx-admission-webhook-cabundle-stale.md` + `cards/card-admission-webhook-failure-fast-triage.md` |
| OOMKilled / CrashLoopBackOff | container-level failure, check resources + logs | Cluster 2 — Scheduling/Capacity | `container-crash-triage` → check Events, `kubectl logs --previous`, resource limits |
| CPUThrottling / high memory | resource pressure without eviction | Cluster 2 — Node pressure | `node-resource-pressure-triage` → `kubectl top`, check requests vs limits |
| NodeNotReady | node-level failure | Cluster 2 — Node pressure | `node-notready-triage` → see `runbook-k8s-node-notready-runbook.md` |
| ImagePullBackOff / ErrImagePull | image pull failure, check registry/tag/secret | Cluster 2 — Scheduling/Capacity | `image-pull-triage` → describe pod Events, check imagePullSecrets |
| PVC Pending / volume mount failure | storage scheduling | Cluster 2 — Scheduling/Capacity | `storage-scheduling-triage` → see `reference-k8s-storage-affinity-scheduling.md` |
| ClickHouse CPU / merge pressure | query vs merge superposition | Cluster 3 — Stateful pressure | see `debug-tree-kafka-lag-downstream.md`, `pattern-clickhouse-merge-cpu-root-cause.md` |
| ClickHouse `Code 241 MEMORY_LIMIT_EXCEEDED` + FP-Async velocity lag | post-upgrade zombie `_N` system log tables (`trace_log_2`, `processors_profile_log_0`, ...) trigger merge OOM | Cluster 3 — Stateful pressure | see `cases/case-clickhouse-system-log-zombie-tables-oom.md` — diagnose via `system.tables` for names with `_N` suffix, fix via `DROP TABLE ... SETTINGS max_table_size_to_drop=0` |
| cert expiring / TLS error | certificate lifecycle | Cluster 1 — Routing/DNS/Ingress | check cert-manager, `kubectl get cert` |

---

## Routing Decision Logic

```
STEP 0: intake
  IF input is Slack link → fetch via Slack MCP → extract alert text
  ELSE → use raw text directly

STEP 1: classify error type
  IF connection_refused → Cluster 1, policy: connection-refused-layered-triage
  IF connection_timeout → Cluster 1, policy: timeout variant (TBD)
  IF cert_expiring OR TLS_error → Cluster 1, check cert-manager

STEP 2: if latency alert
  IF error_rate == normal → Cluster 4, policy: histogram-skew-false-p99
  IF error_rate elevated  → route to service-specific investigation

STEP 3: if lag/throughput/stateful alert
  IF multi_topic, same_CG → Cluster 3, policy: kafka-lag-downstream-write-bottleneck
  IF single_topic         → Cluster 3 variant (TBD)
  IF clickhouse_cpu       → Cluster 3, check merge vs query (system.processes + top -H)

STEP 4: if scheduling/node/container alert
  IF pod_pending OR failed_scheduling → Cluster 2
  IF evicted OR disk_pressure         → Cluster 2 node variant
  IF OOMKilled OR CrashLoopBackOff    → Cluster 2, check logs --previous + resource limits
  IF NodeNotReady                     → Cluster 2, see runbook-k8s-node-notready
  IF ImagePullBackOff                 → Cluster 2, describe pod Events
  IF PVC_pending                      → Cluster 2, check topology/affinity

STEP 5: if access/permission alert
  IF AccessDenied OR 403 → Cluster 5 (TBD)

STEP 6: if regression post-change
  IF correlates with recent deploy/upgrade → Cluster 6 (TBD)
  IF multi-tenant helm install fails + x509 unknown authority + webhook name
    → Cluster 6, admission-webhook-cabundle path
    → see cards/card-admission-webhook-failure-fast-triage.md
    → likely root cause: ValidatingWebhookConfiguration.caBundle stale vs Secret CA

STEP 7: if overload / capacity
  IF single-tenant QPS spike OR request_time up while upstream flat → Cluster 7
  IF per-partition throughput ceiling (lag despite healthy consumer) → Cluster 7
    → stop bleeding first (limit / degrade / traffic split), then scale within caps
    → see references/reference-case-taxonomy.md §Cluster 7
```

---

## Key Discriminators (Cross-Cluster)

These are the signal pairs that most commonly cause misrouting:

| Pair | Discriminator | Wrong assumption |
|------|---------------|-----------------|
| refused vs timeout | refused = no listener; timeout = no route | Treating timeout as refused → wrong layer |
| P99 spike vs real latency | check error_rate + logs before trusting metric | Trusting P99 directly → false escalation |
| Kafka lag root cause | multi-topic = sink; single-topic = consumer/broker | Restarting broker when sink is broken |
| stateful "alive but not serving" | check state pressure, not just up/down | Declaring service down when it's backpressured |

---

## Cluster Coverage Status

| Cluster | Status | Trace File |
|---------|--------|------------|
| 1 — Routing / DNS / Ingress | DONE | `case-clickhouse-connection-refused-troubleshooting.trace.md` |
| 2 — Scheduling / Node Pressure | DONE | `cluster2-scheduling-node-pressure.trace.md` |
| 3 — Stateful Write Pressure | DONE | `case-kafka-lag-issues.trace.md` |
| 4 — Observability / False Signals | DONE | `case-monitoring-alert-delay-histogram-skew.trace.md` |
| 5 — Identity / Access Control | DONE | `cluster5-identity-access.trace.md` |
| 6 — Change Management / Upgrades | DONE | `cluster6-change-management.trace.md` |
| 7 — Overload / Capacity / Large-tenant QPS | DONE (promoted 2026-07-12) | see `references/reference-case-taxonomy.md` §Cluster 7 |

---

## Supplemental Routing Notes

| Signal Pattern | Key Discriminator | → Reference |
|----------------|-------------------|-------------|
| YugabyteDB connection refused / bootstrapping / incident recovery | tserver pressure, raft catchup, blast radius | `runbook-yugabyte-oncall.md` (replaces `-connection-bootstrapping`, `-debug-process`, `-incident-recovery-steps`) |
| SLA breach alert / latency SLO | dashboard panel triage | `reference-sla-dashboard.md` |

---

## Invariants (Apply to All Clusters)

These rules apply regardless of which cluster the signal routes to:

1. **Read-only first**: all diagnostic steps are read-only until root cause is confirmed
2. **Human gate before action**: any state-changing action requires explicit approval
3. **Blast radius before fix**: always assess blast radius before applying mitigation
4. **Evidence chain required**: verifier must check evidence chain before closing
5. **Structural fix != mitigation**: short-term restart ≠ long-term fix; always file follow-ups
6. **Timeline correlation required**: causal claims must be supported by time-aligned evidence
