# State Database

## Purpose

Quick-access entry points for DV database health checks. Jump directly to the right tool per DB type.

---

## YugabyteDB

**DV deployment**: StatefulSet per cluster, namespace pattern `prod-external-new-1` / `preprod-*`.

**Fast check — VM MCP**:
```promql
# All YB nodes up/down in a cluster
up{kubernetes_cluster="<cluster>", kubernetes_namespace="<dbcluster>"}

# All externally-scraped nodes that are down
up{job=~"yugabytedb.*external", export_type=~"tserver_export|master_export"} == 0

# Specific IP
up{instance=~"<ip>:.*"}
```

**Node identification**:
```bash
# Map alert IP to EC2 instance name; get healthy node IPs for YB UI
awsf <region> <cluster-suffix> yb
# e.g. awsf us-west-2 prod-a yb
```

**YB Master UI** (requires VPN, use a healthy node IP):
```
http://<healthy-master-ip>:7000/               # cluster overview, Dead Nodes
http://<healthy-master-ip>:7000/tablet-servers # tserver list, tablet distribution
```

**Common ports**: Master UI `:7000`, Master RPC `:7100`, tserver UI/metrics `:9000`, tserver RPC `:9100`, YSQL `:5433`, YCQL `:9042` or `:12000`.

**Full reference**: `knowledge/cards/card-yugabyte-metrics-fast-checks.md`, `knowledge/cards/card-yugabyte-debug-ports-commands.md`, `knowledge/references/reference-yugabyte-monitoring-commands-reference.md`

---

## ClickHouse

**DV deployment**: pod name pattern `chi-dv-datavisor-0-0-0`, namespace `prod` or `preprod`.

**Fast check — exec into pod**:
```bash
kubectl exec -it -n <namespace> chi-dv-datavisor-0-0-0 -- bash
clickhouse-client
```

**Key diagnostic queries**:
```sql
-- Running merges (CPU saturation check)
SELECT database, `table`, num_parts, elapsed, progress, is_mutation
FROM system.merges;

-- Table sizes and part counts (find merge debt)
SELECT `table`, sum(rows) AS rows,
    ((sum(bytes_on_disk)/1024)/1024)/1024 AS gb, count() AS parts
FROM system.parts WHERE active = 1
GROUP BY `table` ORDER BY gb DESC LIMIT 10;

-- Active queries
SELECT query_id, elapsed, query FROM system.processes;
```

**CPU saturation pattern**: `top -H` showing `MergeMutate` threads = merge debt, not query CPU. Check `system.parts` for large part counts on `trace_log` / `query_log` / `processors_profile_log` tables.

**Full reference**: `knowledge/patterns/pattern-clickhouse-merge-cpu-root-cause.md`

---

## MySQL (fp-mysql-0)

**DV deployment**: StatefulSet `fp-mysql`, namespace `prod`, pod `fp-mysql-0`. Used by Feature Platform.

**Fast check — DB size**:
```bash
kubectl exec -n prod fp-mysql-0 -it -- bash
mysql -u root -p"$MYSQL_ROOT_PASSWORD" \
  -e "SELECT table_schema AS 'Database', ROUND(SUM(data_length+index_length)/1024/1024, 2) AS 'Size (MB)' FROM information_schema.tables GROUP BY table_schema;"
```

**VM MCP metrics**:
```promql
# Slow queries trend
mysql_global_status_slow_queries{kubernetes_cluster="<cluster>"}

# Connection count
mysql_global_status_threads_connected{kubernetes_cluster="<cluster>"}
```

**Full reference**: `knowledge/references/reference-mysql-database-size-backup-notes.md`
