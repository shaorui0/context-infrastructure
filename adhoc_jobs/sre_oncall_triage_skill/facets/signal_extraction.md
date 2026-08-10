# Signal Extraction

## Purpose

Extract signals from alert text. Alert message is the sole truth source — do not infer or expand scope.

## Core Principles

- Extract entities exactly as they appear: client names, cluster names, metrics, timestamps
- Do NOT assume causality or expand scope beyond what's stated
- Flag ambiguous matches as uncertain; prefer "unknown" over guessing
- Missing timestamp/cluster/(namespace or service) → stop and ask user, do not fill in

## Required Fields

| Field | Source in alert | Notes |
|-------|----------------|-------|
| `alertname` | Subject line / first tag | e.g. `[PAGER][YUGABYTE]`, `HighCPUOnFP`, `ClickHouseDiskUsage` |
| `cluster` | Alert body or channel name | Must match DV cluster enum below |
| `event_ts` | Alert trigger time (RFC3339) | Missing → ask user |
| `namespace` | Alert body or default | Assumption if missing: mark as `assumption` |
| `service` | Alert body | e.g. `fp`, `yugabyte`, `clickhouse`, `kafka` |
| `severity` | Alert tag | `pager` / `warning` / `info` |
| `client` | Alert body or tag | Tenant name if present |
| `pod` | Alert body | If pod-specific |

## DV Cluster Enumeration

```
# Production
aws-useast1-prod-a      aws-useast1-prod-b
aws-useast2-prod-a
aws-uswest2-prod-a      aws-uswest2-prod-b
aws-cacentral1-prod-a

# Preprod
aws-useast1-preprod-a   aws-useast1-preprod-b
aws-uswest2-preprod-a   aws-uswest2-preprod-b

# Sandbox / Dev
aws-uswest2-sandbox
```

Cluster name → region mapping: `aws-uswest2-*` → us-west-2, `aws-useast1-*` → us-east-1, `aws-useast2-*` → us-east-2, `aws-cacentral1-*` → ca-central-1.

## Common DV Alert Names (examples, not exhaustive)

| Pattern | Service | Typical cluster |
|---------|---------|----------------|
| `[PAGER][YUGABYTE] Cluster <cluster>: external tserver down` | YugabyteDB | any prod |
| `High CPU on FP` / `HighCPUOnFP` | Feature Platform | any |
| `ClickHouseDiskUsage` / `ClickHouse High CPU` | ClickHouse | any |
| `[PAGER] Kafka consumer lag` | Kafka | any |
| `FP P99 latency` / `SLA latency spike` | FP ingress | any |
| `CrashLoopBackOff` / `OOMKilled` | any pod | any |
| `Debezium connector failed` | CDC | any |
| `StarRocks FE down` | StarRocks | any |

## Extraction Process

1. Parse alert text for the required fields above
2. Match cluster name against DV cluster enum — if not in enum, flag as uncertain
3. Compute `event_ts ± 3min` as the precise query window
4. Output structured signals:
   - All extracted fields with values
   - Fields not found → `MISSING` (do not infer)
   - Ambiguous matches → note uncertainty

## Missing Field Gate

If **timestamp**, **cluster**, or **(namespace OR service)** is missing → stop investigation and ask user. Do not guess or default-fill.
