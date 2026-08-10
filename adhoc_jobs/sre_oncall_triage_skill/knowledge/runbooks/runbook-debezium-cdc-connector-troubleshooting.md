---
metadata:
  kind: runbook
  status: draft
  summary: "Debezium MySQL CDC Sink Connector 故障排查（schema mismatch / _sign null / MySQL 连接超时）"
  tags: ["debezium", "cdc", "mysql", "clickhouse", "sink-connector", "kafka-connect", "snapshot"]
  first_action: "grep 'internal schema size\\|_sign Int8\\|Maximum retries\\|CommunicationsException' pod logs 定位问题类型"
  related: ["cases/case-debezium-schema-change-snapshot-sign-null.md"]
  derived_from: "code_repos/feature-platform/reqs/cre-6630/fp-starrocks-deployment/input.txt"
---

# Debezium CDC Connector Troubleshooting Runbook

## 快速定位

```bash
# 找 connector pod
kubectl get pods -n <ns> | grep -E "sink-connector|kafka-connect"

# 定位问题类型
kubectl logs -n <ns> <pod> --since=2h 2>&1 | \
  grep -E "internal schema size|_sign Int8|Maximum retries|CommunicationsException|ERROR inserting Batch" | \
  head -20
```

**注意**：自定义 sink-connector 可能不走标准 Kafka Connect REST port 8083。先确认端口：
```bash
kubectl exec -n <ns> <pod> -- sh -c "cat /proc/net/tcp6" | awk '{print $2}' | cut -d: -f2 | \
  while read hex; do printf "%d\n" 0x$hex; done | sort -u
# 或
kubectl exec -n <ns> <pod> -- ss -tlnp 2>/dev/null
```

---

## 问题 1：Schema Mismatch 崩溃

**症状**:
```
ERROR: internal schema size 4, but row size 2, restart connector with schema recovery mode.
Maximum retries reached → Shutting down
```

**原因**: MySQL 表结构变更（DDL），Debezium 缓存旧 schema，binlog 解析失败。

**处理**:
```bash
# connector 会自动重启（pod 重启 or K8s restart policy）
# 重启后会进入 schema recovery 模式，触发全量 Snapshot

# 监控恢复状态
kubectl logs -n <ns> <pod> --since=30m -f 2>&1 | \
  grep -E "ERROR inserting Batch|EXECUTED BATCH Successfully|snapshot"
```

**注意**: 重启后的 Snapshot 可能引发 **问题 2**（_sign null）。

---

## 问题 2：Snapshot 期间 _sign = null → ClickHouse 写入失败

**症状**（connector 重启后，schema recovery + 全量 Snapshot 期间）:
```
ERROR inserting Batch
java.sql.SQLException: Cannot set null to non-nullable column #15 [_sign Int8]
```

**原因**: 
- connector 配置了 `replacingmergetree.delete.column: _sign`
- Snapshot 事件 op_type = `r`（read），connector 只映射 `c`→1 / `d`→-1，`r` 无映射 → `_sign` = null
- ClickHouse `_sign Int8 NOT NULL` → 拒绝写入

**处理**:
- 通常无需手动干预，等待 Snapshot 完成即可自动恢复
- 确认恢复时间线：
```bash
kubectl logs -n <ns> <pod> --since=2h 2>&1 | \
  grep -E "ERROR inserting Batch|EXECUTED BATCH Successfully" | \
  grep -E "时间窗口" | head -10
```

**Snapshot 完成后（切回 streaming CDC）自动恢复**。

**数据缺口评估**: Snapshot 期间写失败的 batch 可能有缺口：
```bash
# 确认失败 window
kubectl logs -n <ns> <pod> --since=4h 2>&1 | \
  grep -E "ERROR inserting Batch|EXECUTED BATCH Successfully" | \
  awk '/ERROR inserting/{start=$2} /EXECUTED BATCH Successfully/ && start{print "ERROR window:", start, "→", $2; start=""}'
```
对应时间段需与 MySQL 数据比对，评估是否需要补数。

**根本修复（防复发）**:
```json
// 方案 A：ClickHouse 表加 DEFAULT
// ALTER TABLE <table> MODIFY COLUMN _sign Int8 DEFAULT 1;

// 方案 B：connector 配置 snapshot 模式
{
  "snapshot.mode": "schema_only_recovery"
}
```

---

## 问题 3：MySQL 连接超时（空闲 TCP kill）

**症状**（流量切换到另一集群后，约 400~600s 后）:
```
CommunicationsException: The last packet successfully received from the server was 431,432ms ago.
DatabaseHeartbeatImpl - Could not execute heartbeat action (Error: 08S01)
Caused by: java.io.IOException: Socket is closed.
```

**原因**: 非 MySQL wait_timeout（默认 8h），是网络中间层（ALB/NAT Gateway）idle TCP timeout（通常 350s~600s）。流量切走 → connector 空闲 → TCP 连接被中间层 kill → heartbeat 发现 socket 关闭 → crash。

**立即处理**（重启 connector，不丢数据）:
```bash
# 通过 REST API 重启（标准 Kafka Connect）
kubectl exec -n <ns> <pod> -- \
  curl -X POST http://localhost:8083/connectors/<connector-name>/restart?includeTasks=true

# 监控恢复
kubectl exec -n <ns> <pod> -- \
  watch -n 5 'curl -s http://localhost:8083/connectors/<connector-name>/status | jq .connector.state'
```

**根本修复**（connector config 加保活参数）:
```json
{
  "heartbeat.interval.ms": "30000",
  "database.jdbc.url.properties": "autoReconnect=true&tcpKeepAlive=true",
  "connect.timeout.ms": "30000"
}
```
核心：heartbeat 间隔（30s）< 网络 idle timeout（~431s），保持 TCP 连接活跃。

---

## 常用诊断命令

```bash
# 查 connector 当前状态（最新日志）
kubectl logs -n <ns> <pod> --since=10m 2>&1 | tail -30

# 确认 connector 进程监听端口
kubectl exec -n <ns> <pod> -- sh -c "cat /proc/net/tcp6" | \
  awk 'NR>1{print $2}' | cut -d: -f2 | while read h; do printf "%d\n" 0x$h; done | sort -u

# 确认 MySQL 可达（Side B 环境）
kubectl exec -n <ns> <pod> -- nc -zv <mysql-host> 3306

# 过滤 ERROR/恢复 时间线
kubectl logs -n <ns> <pod> --since=2h 2>&1 | \
  grep -E "ERROR inserting Batch|EXECUTED BATCH Successfully|Maximum retries|Shutting down|schema recovery" | \
  head -30

# 查 connector 配置（确认 _sign 列名 / heartbeat 配置）
kubectl logs -n <ns> <pod> --since=4h 2>&1 | grep -E "replacingmergetree|heartbeat.interval|delete.column" | head -5
```
