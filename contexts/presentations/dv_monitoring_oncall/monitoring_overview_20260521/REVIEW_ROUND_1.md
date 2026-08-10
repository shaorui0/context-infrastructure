# Review Round 1

> Reviewer perspective: a freshly-paged oncall (DataVisor-experienced but new to this doc) reads REPORT.md + parts/01-06 in the dark at 03:00. Question: can they actually fix things?

## Verdict
**NEEDS MINOR FIXES**

The doc is unusually strong for a first cut: dashboard UIDs are concrete, the latency-chain mental model is load-bearing, the 4-quadrant bisect table is genuinely actionable, and the parts/ files cite real panel IDs + sanitized PromQL/LogQL. The "10 alert families" map cleanly onto the workflow. The remaining gaps are about **bridging from a Slack alert to the doc** (the first 30 seconds) and a handful of factual things to verify. None are showstoppers.

If the goal is "engineer wakes up to Slack alert and triages with this doc," the doc handles minute 3 through minute 30 well, but minute 0–2 is missing.

---

## Critical gaps (must fix before usable)

1. **No "from Slack to dashboard" first-mile.** The doc never says:
   - What does an alert message look like in Slack? Which fields are guaranteed vs optional?
   - How do you ack? (REPORT §8 admits Alertmanager routing is unknown; parts/05 §"Ack / silence" hand-waves "Slack bot has react / button, ask SRE for alertmanager URL".) A brand-new oncall has nowhere to ack.
   - **What is the Grafana URL? How do I log in?** `grafana-mgt.dv-api.com` appears in parts/01 but never in REPORT.md. SSO? VPN required? On call from phone — does it work?
   - Where is the on-call rotation defined? Who's secondary? How do I page secondary?

2. **Alert → playbook mapping is by alert *family*, not alert *name*.** The §5 table uses generic English ("P99 latency SLA breach"), but the real Slack message says `RTIngressP99ResponseTime_Affirm` or `FPTopicsOffsetIncreaseZero_Dci_tuesday_to_saturday`. parts/05 has the rule name → family mapping buried in 9 tables (A–I) — a paged oncall will not find it under stress. **Need a flat "alertname → playbook letter" index, sorted alphabetically.**

3. **"FPTopicsOffsetIncreaseZero" — the single biggest noise source (469 firing, 50% of all firing alerts) has no playbook.** Playbook J covers "false alert / metric unstable" generically. But the practical first question a new oncall faces is "this alert fires 50 times a day, is mine real?" Need a dedicated entry: how to tell a real Kafka offset stall vs the chronic noise; suggested silence pattern; who owns dedup.

4. **`investigation window = ts ± 3min`** is repeated 4 times as gospel, but the doc never explains *why 3 minutes and not 5/10*, nor what to do when the alert's evaluation window is longer than 3min (e.g. `K8sMasterPatchSucceed` checks 30 days; many SLA rules use `[10m]`/`[1h]`). New oncall will apply ±3min to an alert with a 1h aggregation window and see flat data → conclude "false alarm" wrongly. Either clarify the rule (window = alert eval window, not 3min) or add an exception list.

5. **Severity SLA timings appear once, in parts/05 line 506: "PAGER 5min, HIGH 30min".** This is the only place in the doc — not in REPORT, not in §4 workflow, not in the playbooks. Should be in REPORT §4 Step 1, since it determines whether you pause to investigate or page secondary immediately.

---

## Nice-to-have improvements

1. **Playbook J ordering issue.** §5 puts "metric instability" as alert family J (last). In practice, given 932 firing alerts of which TOP-3 are likely all metric-pipeline noise, the *first* question on any alert should be "is this real?" Consider hoisting "Step 0: is this chronic noise?" before Step 1 — or at least cross-link J from every other playbook.

2. **Per-cluster SLA dashboard variants** are mentioned in parts/06 line 50 (`Zv5gfxmDz`, `LrvYqTiDz`, `4igjS1Rvk`, `b0MtArMvz`) with the helpful tip "use the cluster-bound one when paged — fewer variables to set." This advice should be in REPORT §2 right next to `p1KqfRAMk`, not buried in parts/06.

3. **Missing "DataVisor cluster name decoder ring".** A new oncall will see `gcp-uswest1-prod-a`, `aws-uswest2-mgt-a`, `aws-uswest2-preprod-a`, `useast1-prod-b`, `apsoutheast-prod`, `aws-*-pci-*`. parts/02 has a partial table (cluster → Loki tenant) but no overall "what's prod / what's mgt / what's PCI / which region serves which customer". The `gcp-uswest1-prod-a = nonprod` trap is called out twice but the broader naming convention is never explained.

4. **MCP-only escape hatches not in §4 workflow.** parts/05 explains vmui beautifully ("alert source URL opens vmui with the alert query prefilled"), but §4 Step 1 doesn't say "click the source link in the Slack message first." This is the fastest possible first action and should be Step 1.5.

5. **No "how to write a status update in the incident channel" template.** Step 5 says "write a hypothesis to the incident channel" but doesn't show what good vs bad looks like. One-line example would help.

6. **§5 playbook D (Node mem >90%) cites `rYdddlPWk` (Node Exporter Full)** but parts/03 documents `sNt6IXzGk` (Node Resource). Are these the same dashboard, or different? If different, which one do I open? (parts/06 line 163 actually references both, confusingly: `rYdddlPWk` "or `9CWBz0bik`"). Pick one canonical UID per use case in §5.

7. **MySQL playbook G references `mysql` instance variable, but parts/04 doesn't show MySQL Overview variable list** (I only read first 100 lines of parts/04, but if the variables aren't there it's a gap). Make sure parts/04 enumerates MQWgroiiz variables the same way 01 and 03 do.

8. **REPORT §10 (30-second elevator pitch) is great** but should reference §4 Step numbers explicitly so the new oncall can use the 30-sec version as a navigation TOC.

9. **No screenshots.** A few annotated screenshots of (a) what a Slack alert looks like, (b) the SLA dashboard's three latency panels side-by-side, (c) the 4-quadrant decision in action would 10x onboarding speed. Not blocking, but high-leverage.

10. **Playbook H step 4 mentions `proxy_read_timeout`** changed by "recent fp behavior change" without saying where to find ingress config or who can change it. Hanging pointer.

---

## Things the doc gets right (worth preserving)

- **Concrete dashboard UIDs everywhere.** Every dashboard mentioned has a UID; this is rare and excellent.
- **Latency 4-quadrant table** (REPORT §3, parts/01, parts/06) is *the* mental model. Repeated in three places with consistent semantics. This is the load-bearing concept of the whole doc and it lands.
- **Status code semantics callout** (499 not in SLA; 400/429 are success; backup upstream excluded) — these are the kind of "fingers-burned" knowledge that takes years to acquire, captured cleanly.
- **Calling out panel-level bugs as gotchas** (panel 9 `devie` typo, panel 15 throttling denominator missing `pod`, panel 401 hardcoded master IP, MySQL panels hardcoded datasource UID) — extraordinarily valuable for a new oncall who'd otherwise trust the panel and miscount.
- **§8 explicitly lists what wasn't covered** (Alertmanager routing, recording rules, OnCall schedules) — intellectually honest, sets expectations.
- **Cross-links to skills and memory** (REPORT §9, parts/06 §与已有 skill) — embeds the doc in the existing tooling rather than orphaning it.
- **parts/01 dashboard-level investigation caveats** at the very end (panel queries truncated at 400 chars, LogQL pattern truncated at `<internal_endpo`) — future maintainer knows exactly what to re-pull.
- **§7 high-frequency pitfalls (20 items)** is the doc's hidden gem. Every bullet looks like it cost someone a real incident.

---

## Specific factual claims to verify

| Location | Claim | Why to verify |
|---|---|---|
| REPORT §1, line 18 | "vmalert → 独立 alertmanager (k8s ConfigMap, MCP 看不到)" | Confirm via `kubectl -n monitoring get cm` whether it's actually one alertmanager or HA pair; whether vmalert -notifier.url points to a service DNS. §8 admits this gap; should be closed before the doc is shipped to new hires. |
| REPORT §3 / parts/01 panel 373 | "Waiting = `request_time − upstream_response_time`" | parts/01 line 395 admits the LogQL `pattern` was truncated at `<internal_endpo` — the unwrapped field name is **inferred**, not seen. Confirm in Grafana UI. If wrong, the central diagnostic table is wrong. |
| REPORT §7 #14 | "Yuga `rpc_latency` quantile label is string `\"p99\"`" | parts/04 confirms this, good. But verify it's still true after any YB upgrade — Yugabyte changed metric exposure format in past versions. |
| REPORT §7 #15 | "MySQL replication lag panel 401 has hardcoded `master_host=172.31.36.37`" | If true, this needs a fix ticket filed, not just a doc warning. The doc currently treats it as immutable. |
| REPORT §6 | "540 alerting rules, 0 recording rules; recording rules defined elsewhere" | parts/05 §"recording rule 看起来被搬空了" speculates they moved. Find where they actually live before claiming `record:loki_*` is reliable to read. |
| REPORT §5 row D | Dashboard for "Node mem >90%" = `rYdddlPWk` (Node Exporter Full) | parts/03 canonical Node dashboard is `sNt6IXzGk` (Node Resource). Conflict — pick one. |
| parts/06 line 50 | Per-cluster SLA dashboard UIDs listed | Were these actually verified to exist via `mcp__grafana__search_dashboards`, or inferred from naming pattern? If inferred, mark as needing verification. |
| parts/06 line 263 | "Per `ls archives/skills/` the archived SRE-oncall skills directory was not found" | But the system reminder lists `sre-oncall-init`, `sre-oncall-acceptance-criteria`, `sre-oncall-output-format`, `sre-oncall-query-safety`, `sre-oncall-compound-learning` as available skills. They DO exist as runtime skills — the doc should link them, not say "not found." |
| REPORT §1 | "vm-mgt-a.dv-api.com ← 唯一 metrics 后端" | parts/05 lists `Deepflow-Prometheus` as a separate datasource with different metric names — strictly speaking VM is not the only backend. Soften to "primary." |
| parts/05 line 412 | "RTFrontendResultGeneratorERRORLog (no sev)" | If no severity, where does this alert route? If it's into the default channel with 91 others, what happens to it operationally? Same applies to all "(no sev)" entries — worth one sentence on the practical effect. |

---

## Onboarding test answer

If a brand-new SRE who joined yesterday were paged at 03:00 with `RTIngressP99ResponseTime_Affirm`, the FIRST thing that would confuse them is:

> "How do I log into Grafana? What URL? Do I need VPN? My phone — does the SLA dashboard even load on mobile?"

Followed by:

> "The alert says client=Affirm, cluster=aws-useast1-prod-a. The doc says open `p1KqfRAMk` and 'set cluster + client.' But the dashboard has variables `PromDs` / `client` / `sandbox_client` / `pipeline` / `Batch_Pipeline` — which `PromDs` value corresponds to `aws-useast1-prod-a`? The doc says 'prod-vm' as an example but doesn't promise that's the actual datasource name."

Both are 30-second fixes (add a "Grafana access + cluster→datasource map" preflight section to REPORT §0).

---

## Recommended fix order (if time-constrained)

1. Add REPORT §0 "Before your first page" — Grafana URL, login, ack mechanism, severity SLA, on-call escalation. (~30 min)
2. Add a flat alphabetical `alertname → playbook letter` table in parts/05 or a new parts/07. (~1 hr)
3. Resolve the `rYdddlPWk` vs `sNt6IXzGk` conflict in §5 row D. (~5 min)
4. Verify the panel 373 unwrap field via Grafana UI; lock in the diagnostic table. (~10 min)
5. Add explicit `FPTopicsOffsetIncreaseZero` triage entry (real vs noise). (~30 min)
6. Either close §8 gaps (alertmanager config, recording rules) or convert them into filed tickets. (~1 hr or async)

Everything else is polish.
