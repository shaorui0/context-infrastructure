---
metadata:
  kind: case
  status: draft
  summary: "ClickHouse upgrade leaves `_N` suffixed zombie system log tables (trace_log_2 at 1.21 TiB, processors_profile_log_0 at 308 GiB). Background merge on these zombies spikes memory from 2 GiB baseline to 21.60 GiB max in one second, killing FP-Async insert queries with Code 241 MEMORY_LIMIT_EXCEEDED. Consumer group velocity.preprod_a lag rises because failed batches enter 30s sleep + rebalance retry loop."
  tags: ["clickhouse", "memory", "oom", "system-log", "upgrade-residue", "trace_log", "fp-async", "consumer-lag", "preprod"]
  first_action: "SELECT name, total_bytes FROM system.tables WHERE database='system' AND total_bytes > 1e8 — names ending in _0/_1/_2/... are zombie tables from prior CH upgrades"
  related:
    - "cases/case-clickhouse-ttl-merge-cpu-saturation.md"
    - "cases/case-clickhouse-copydata-recovery-failure.md"
    - "runbooks/runbook-clickhouse-disk-space-exhaustion.md"
---

# ClickHouse System Log Zombie Tables → OOM → FP-Async Consumer Lag

## TL;DR (Do This First)

1. **Check for `_N` suffix zombie tables** (the giveaway):
   ```sql
   SELECT name, total_rows, formatReadableSize(total_bytes)
   FROM system.tables
   WHERE database='system' AND total_bytes > 100000000
   ORDER BY total_bytes DESC;
   ```
   Names like `trace_log_2`, `processors_profile_log_0`, `metric_log_3` (with numeric suffix) are **dead schema-version residues from prior CH upgrades**. The active table is the one with no suffix.

2. **Check memory tracking history** for spike pattern:
   ```sql
   SELECT event_time, formatReadableSize(CurrentMetric_MemoryTracking)
   FROM system.metric_log ORDER BY event_time DESC LIMIT 30;
   ```
   Diagnostic signature: baseline 1-3 GiB, **one-second spike to max_server_memory_usage**, then back to baseline. NOT steady-state growth.

3. **Confirm OOM count**:
   ```sql
   SELECT count(), max(event_time) FROM system.query_log
   WHERE event_time > now() - INTERVAL 30 MINUTE AND exception_code = 241;
   ```

If all three signals present → this case applies. Skip to "Mitigation."

## The Misleading Diagnostic Signal

The error message lies:
```
memory limit exceeded: would use 21.60 GiB ... current RSS: 8.85 GiB,
maximum: 21.60 GiB
```

`current RSS: 8.85 GiB` makes it look like a memory leak slowly built up. **It is not.** Memory tracker baseline is ~2 GiB; merge for a 1+ TiB zombie part allocates 20+ GiB in one shot, blows the cap, gets killed by OvercommitTracker, then memory drops back to 2 GiB. By the time you exec in, the spike is gone.

→ **Do not trust point-in-time `SHOW PROCESSES` or `system.merges`** — the offending merge already aborted. Look at `system.metric_log` time series for spike evidence.

## Why It Happens

ClickHouse 25.x (and earlier) **does not drop old system log tables** when an upgrade changes their schema. The old data gets renamed to `<table>_N` (e.g. `trace_log` → `trace_log_2`), and a fresh empty `trace_log` is created. The old `_N` tables:

- Receive no new writes
- Have no readers (unless someone runs flamegraph against them by name)
- **Still have parts on disk that participate in background merges**

Combined with the default lack of TTL on `trace_log` / `processors_profile_log` / `metric_log` / `asynchronous_metric_log` (only `query_log` typically has TTL configured), these old tables grow unbounded across upgrade cycles. After 2-3 upgrades you can have terabytes of dead trace data ticking time-bombing your CH.

## Downstream Blast Radius (FP-Async)

When ClickHouse rejects `INSERT` with Code 241:
- `ConsumerForCH.run` throws → batch marked failed
- AsyncKafkaConsumer enters **30s sleep + rebalance + retry** loop
- The same records replay, hit OOM again, fail again
- **Consumer lag on `preprod_fp_velocity-al-.<tenant>` rises monotonically**
- Visible across multiple tenants concurrently (galileo, onefinance, etc.)

Therefore: alerts may fire as "Kafka consumer lag" but the root cause is upstream in ClickHouse.

## Detection / Alert Correlation

Likely alert chain:
1. **Kafka consumer lag** on `velocity.preprod_a` (the user-visible symptom)
2. **ClickHouse insert error rate** (if monitored)
3. **CH memory tracker** brief spike (often missed by 30s scrape — too fast)

If you see (1) without obvious traffic spike, immediately check CH for (2) and (3).

## Mitigation

### Phase 1: Stop the bleeding (read-safe diagnostic)

```bash
# Find zombies
<kubectl-alias> exec -n preprod chi-dv-datavisor-0-0-0 -c clickhouse -- \
  clickhouse-client --query "
    SELECT name, total_rows, formatReadableSize(total_bytes)
    FROM system.tables
    WHERE database='system' AND total_bytes > 100000000
    ORDER BY total_bytes DESC FORMAT PrettyCompact"
```

### Phase 2: TRUNCATE the active (no-suffix) tables — partial relief

```bash
<kubectl-alias> exec -n preprod chi-dv-datavisor-0-0-0 -c clickhouse -- clickhouse-client --query "TRUNCATE TABLE system.trace_log SYNC"
<kubectl-alias> exec -n preprod chi-dv-datavisor-0-0-0 -c clickhouse -- clickhouse-client --query "TRUNCATE TABLE system.processors_profile_log SYNC"
<kubectl-alias> exec -n preprod chi-dv-datavisor-0-0-0 -c clickhouse -- clickhouse-client --query "TRUNCATE TABLE system.metric_log SYNC"
<kubectl-alias> exec -n preprod chi-dv-datavisor-0-0-0 -c clickhouse -- clickhouse-client --query "TRUNCATE TABLE system.asynchronous_metric_log SYNC"
```

⚠️ **TRUNCATE only hits the no-suffix tables. The `_N` zombies are untouched.** This step reduces forward pressure but does not fix the root cause.

### Phase 3: DROP the `_N` zombie tables — the actual fix

CH guards against dropping > 50 GB tables. Bypass per-query (preferred):

```bash
<kubectl-alias> exec -n preprod chi-dv-datavisor-0-0-0 -c clickhouse -- \
  clickhouse-client --query "DROP TABLE system.trace_log_2 SYNC SETTINGS max_table_size_to_drop=0"

# Repeat for every _N table found in Phase 1
```

If the CH version rejects `SETTINGS` clause on DROP (older versions):
```bash
<kubectl-alias> exec -n preprod chi-dv-datavisor-0-0-0 -c clickhouse -- \
  bash -c "touch /var/lib/clickhouse/flags/force_drop_table && chmod 666 /var/lib/clickhouse/flags/force_drop_table"
# Then run plain DROP. The flag file is one-shot — re-touch before each DROP.
```

A 1+ TiB DROP takes 1-3 minutes (per-part metadata deletion). CH continues serving during DROP; only disk IO rises briefly.

### Phase 4: Verify

- `system.tables` should show only no-suffix log tables, each MiB-sized
- `CurrentMetric_MemoryTracking` should stay flat at baseline
- New OOM count over the last 5 min should be 0
- **FP-Async consumer lag may NOT drain automatically** — if it stays high, restart the FP-Async pod to break the rebalance loop

## Safety Boundaries

- **Phase 1, 2 (TRUNCATE)**: zero risk — these are CH's own debug logs, no business read/write
- **Phase 3 (DROP `_N` tables)**: zero risk — these tables have no writers (CH already migrated to no-suffix tables) and no readers (no business code references them by name)
- **#MANUAL gate**: only if dropping a CURRENT (no-suffix) `query_log` or similar that a Grafana dashboard might be querying — confirm with team before
- **Do NOT increase pod memory as primary fix** — root cause is unbounded zombie tables, not undersized pod

## Signals

- **Cluster**: any preprod/prod with CH upgrade history
- **Service**: `clickhouse.<ns>:8123` (ClickHouseInstallation operator-managed)
- **Affected app**: FP-Async (`ConsumerForCH`), velocity-* topics
- **Error code**: `Code: 241. DB::Exception: (total) memory limit exceeded ... OvercommitTracker decision: Query was selected to stop`
- **Versions seen**: 25.11.6.11 (likely affects all 24.x+ with multiple upgrades)

## Long-term Fix (in CHI YAML `config.d/config-custom.xml`)

```xml
<!-- Disable trace_log entirely on preprod (sampling profiler not needed) -->
<trace_log remove="1"/>

<!-- TTL the other internal logs -->
<processors_profile_log>
  <engine>ENGINE = MergeTree PARTITION BY event_date ORDER BY event_time
          TTL event_date + INTERVAL 3 DAY DELETE</engine>
  <flush_interval_milliseconds>7500</flush_interval_milliseconds>
</processors_profile_log>
<metric_log>
  <engine>ENGINE = MergeTree PARTITION BY event_date ORDER BY event_time
          TTL event_date + INTERVAL 3 DAY DELETE</engine>
  <flush_interval_milliseconds>7500</flush_interval_milliseconds>
</metric_log>
<asynchronous_metric_log>
  <engine>ENGINE = MergeTree PARTITION BY event_date ORDER BY event_time
          TTL event_date + INTERVAL 3 DAY DELETE</engine>
  <flush_interval_milliseconds>7500</flush_interval_milliseconds>
</asynchronous_metric_log>

<!-- Pin max_server_memory_usage independent of cgroup auto-detection -->
<max_server_memory_usage_to_ram_ratio>0.75</max_server_memory_usage_to_ram_ratio>
```

Add to **upgrade runbook**: after every CH version bump, audit `system.tables` for new `_N` zombies and drop them.

## Lessons Learned

1. **CH upgrades leave breadcrumbs.** Schema-changed system log tables are renamed, not dropped. Without explicit cleanup, they accumulate forever and the next merge bomb is just a matter of time.
2. **TRUNCATE is not equivalent to DROP for this pattern** — TRUNCATE only acts on the no-suffix active table.
3. **Memory tracker spike is sub-second.** Prometheus scrape at 30s interval will miss it. Always check `system.metric_log` (1s granularity) for spike evidence after an OOM event.
4. **Pod memory limit is not the right knob.** Raising pod memory delays the failure but does not stop unbounded zombie growth.
5. **Downstream consumer lag may be the only visible alert.** When investigating Kafka lag on insert-heavy consumers, check the sink (CH) memory before tuning the consumer.

## Cross-Environment Audit Pattern

This is a **fleet-wide latent issue**. After confirming in one cluster, immediately check siblings:

```bash
# us-east preprod
keastpreprod exec -n preprod chi-dv-datavisor-0-0-0 -c clickhouse -- \
  clickhouse-client --query "SELECT name, formatReadableSize(total_bytes) FROM system.tables WHERE database='system' AND total_bytes > 1e8 ORDER BY total_bytes DESC FORMAT PrettyCompact"

# sg preprod
ksgb exec -n preprod chi-dv-datavisor-0-0-0 -c clickhouse -- \
  clickhouse-client --query "SELECT name, formatReadableSize(total_bytes) FROM system.tables WHERE database='system' AND total_bytes > 1e8 ORDER BY total_bytes DESC FORMAT PrettyCompact"

# Repeat across all CH-bearing clusters (prod regions, dev, etc.)
```

In ONCALL-21816 (2026-05-27): east preprod had 1.65 TiB zombies (most severe, P0); SG preprod had 250 GiB zombies (3 OOM/24h, not yet paging but on the curve).

## Related Tickets

- **ONCALL-21816** (2026-05-27) — Preprod ClickHouse OOM causing FP-Async velocity-al consumer lag
- **CRE-6630** — ClickHouse pod memory 16Gi → 24Gi (predecessor context — node resize was already done; this case shows resize alone was insufficient)

## Historical Operation Reference

`code_repos/historial_operations/clickhouse_system_log_cleanup/cmd.md` — full command sequence with east + sg examples
