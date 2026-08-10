# Infra Tools

Small, read-only helpers for oncall workflows. These tools may query monitoring endpoints but never mutate production systems.

## Tool Overview

| Tool | Purpose | When to use |
|---|---|---|
| `vm_lookup.py` | Discover pods/namespaces from VictoriaMetrics (fallback CLI) | Missing `namespace`/`pod`; prefer `/sre-vm-query` skill |
| `loki_fetch/` | Query Loki HTTP API directly (bypass Grafana MCP) | All LogQL queries — prefer `/dv_loki_fetch` skill; raw CLI available as fallback |
| `agent_ops/` | K8s/AWS safety gate + audit trail | Always active via Claude Code hooks (`~/.claude/hooks/`) |
| `agent_ops/verify.py` | Verify investigation output completeness and quality | Run after writing output file (mandatory) |
| `agent_ops/slo.py` | Aggregate investigation quality metrics | Periodic review of agent effectiveness |

> **Metrics queries** (PromQL/MetricsQL) → use the **`/sre-vm-query` skill** (wraps `mcp__victoriametrics__*` MCP tools with query safety checks). `vm_lookup.py` is only for pod/namespace discovery and is available as a raw CLI fallback.
> **Log queries** (LogQL) → use the **`/dv_loki_fetch` skill**. `loki_fetch/loki_fetch.py` CLI remains available as a fallback.

---

## `vm_lookup.py`

推荐通过 `/sre-vm-query` skill 调用，原始 CLI 仍可用作 fallback。

Queries VictoriaMetrics via the Prometheus-compatible API:

- Base: `$VM_BASE_URL` (set in `.env` or environment)
- Endpoint: `/prometheus/api/v1/query`

Examples:

```bash
# List candidate FP pods in a cluster (returns JSON)
python3 skills/.infra/tools/vm_lookup.py pods --cluster aws-useast1-prod-b --service fp

# Same, but prefer prod namespace in ranking (does not hide other namespaces)
python3 skills/.infra/tools/vm_lookup.py pods --cluster aws-useast1-prod-b --service fp --prefer-namespace prod

# Get namespace for a known pod
python3 skills/.infra/tools/vm_lookup.py namespace-from-pod --pod fp-deployment-957745bf6-wdrqx
```

---

## `agent_ops/verify.py`

Deterministic verifier for investigation output files. Checks schema completeness, debug tree step completion, conclusion-evidence consistency, Slack language conservatism, and link validity.

```bash
# Verify an output file (mandatory after every investigation)
python3 tools/agent_ops/verify.py tmp/sre-triage-2026-03-31_14-23-45.md

# JSON output for programmatic use
python3 tools/agent_ops/verify.py tmp/sre-triage-2026-03-31_14-23-45.md --json
```

Exit codes: 0=PASS, 1=WARN, 2=FAIL.

---

## `agent_ops/slo.py`

Aggregates quality metrics from investigation output files. Tracks debug tree usage rate, verdict distribution, steps to conclusion, verification pass rate, and more.

```bash
# All investigations
python3 tools/agent_ops/slo.py

# Since a specific date
python3 tools/agent_ops/slo.py --since 2026-03-01

# JSON output
python3 tools/agent_ops/slo.py --json
```
