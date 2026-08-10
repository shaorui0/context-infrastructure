---
metadata:
  kind: case
  status: draft
  summary: "Debezium MySQL CDC connector: schema change → crash → full snapshot → _sign null → ClickHouse writes rejected"
  tags: ["debezium", "cdc", "mysql", "clickhouse", "sink-connector", "schema", "snapshot", "release"]
  first_action: "grep 'internal schema size\\|_sign Int8\\|Maximum retries' pod logs，确认是 schema mismatch 崩溃还是 _sign 写入失败"
  related: ["runbooks/runbook-debezium-cdc-connector-troubleshooting.md"]
  derived_from: "code_repos/feature-platform/reqs/cre-6630/fp-starrocks-deployment/input.txt"
---

## TL;DR（5 步）

1. **告警信号**: CA Release 发布后，`sink-connector` pod 日志出现 `internal schema size 4, but row size 2`，connector 崩溃重启；重启后大量 `Cannot set null to non-nullable column #15 [_sign Int8]`
2. **关键发现**: Release 改变了 `report_category` 表结构（列数 4→2），Debezium 缓存旧 schema，binlog 解析失败；重启触发全量 Snapshot，Snapshot 事件 op_type=`r`，`_sign` 未被赋值 → null
3. **根因**: Schema change → Debezium 崩溃 → 重启触发全量 Snapshot → Snapshot 模式 `_sign` 映射缺失 → ClickHouse NOT NULL 约束拒绝写入
4. **修复**: 无需手动干预，Snapshot 完成（03:33）后 connector 自动恢复；Side B MySQL 连接超时需重启 connector
5. **后续**: 检查 03:10~03:33 window 内 ClickHouse 数据是否有缺口，评估是否需要补数

## 信号

- `ERROR: internal schema size 4, but row size 2` — Debezium schema 缓存与 MySQL 实际不符
- `Retrying - try number: 6 ... Maximum retries reached ... Shutting down` — connector 达到最大重试后停止
- 重启后：大量 `Cannot set null to non-nullable column #15 [_sign Int8]` — Snapshot 期间写 ClickHouse 失败
- 二次问题：`CommunicationsException: The last packet successfully received from the server was 431,432 milliseconds ago` — Side B 空闲连接被网络层 kill

## Evidence Chain

**问题 1：Schema mismatch 崩溃（02:28）**
```
[connector-mysql-0] ERROR DebeziumChangeEventCapture - Error processing row in report_category,
  internal schema size 4, but row size 2, restart connector with schema recovery mode.
[connector-mysql-0] ERROR - Maximum retries reached
[connector-mysql-0] ERROR - Shutting down
```

**问题 2：Snapshot 期间 _sign = null（03:10~03:33）**
```
[Sink Connector thread-pool-4] ERROR - ERROR inserting Batch
java.sql.SQLException: Cannot set null to non-nullable column #15 [_sign Int8]
```

配置根因：
```
replacingmergetree.delete.column: _sign
```
Snapshot 事件 op_type = `r`（read），connector 逻辑只映射了 `c`→1 和 `d`→-1，`r` 未映射 → `_sign` = null。

**问题 3：Side B MySQL 连接超时（03:26，流量切到 Side A 后约 431s）**
```
[blc-ui-mysql:3306] ERROR DatabaseHeartbeatImpl - Could not execute heartbeat action (Error: 08S01)
CommunicationsException: Communications link failure
Caused by: java.io.IOException: Socket is closed.
```
431 秒 ≈ 网络中间层（ALB/防火墙）idle TCP timeout，不是 MySQL wait_timeout（8h）。

## 结论

**根因链（likely）**:
```
CA Release 改 report_category schema（4列→2列）
        ↓
Debezium 缓存旧 schema → binlog 解析失败 → 崩溃（02:28）
        ↓
K8s 重启 pod，进入 schema recovery 模式 → 触发全量 Snapshot（03:08）
        ↓
Snapshot op_type="r"，_sign 未被映射 → null
        ↓
ClickHouse _sign Int8 NOT NULL → 拒绝写入（03:10~03:33）
        ↓
Snapshot 完成，切回 streaming CDC → _sign 正常填充 → 自动恢复（03:33）
```

**Side B MySQL 连接超时**：流量切 Side A 后 Side B connector 空闲，~431s 后网络层 kill TCP 连接，heartbeat 尝试时发现 socket 已关闭 → crash。

## 建议操作

### 立即处理

```bash
# 确认 connector 当前状态
kcaproda logs -nprod <connector-pod> --since=1h 2>&1 | \
  grep -E "ERROR inserting Batch|EXECUTED BATCH Successfully" | tail -5

# 如果 connector 还在 FAILED：重启（不丢数据，从上次 committed offset 继续）
# 需人工确认后执行：
# kubectl exec <connector-pod> -- curl -X POST http://localhost:8083/connectors/<name>/restart?includeTasks=true
```

### 数据缺口检查

检查 03:10~03:33 window 内 ClickHouse 写入失败的表（`report_category` 及相关表），与 MySQL 比对行数是否有缺口。

### 根本修复（防复发）

**1. Snapshot 期间 _sign 映射问题**（connector 配置）：
```json
{
  "snapshot.mode": "schema_only_recovery",
  "replacingmergetree.delete.column.default": "1"
}
```
或在 ClickHouse 建表时给 `_sign` 加 DEFAULT 值：
```sql
ALTER TABLE <table> MODIFY COLUMN _sign Int8 DEFAULT 1;
```

**2. Side B MySQL 连接超时**（防止网络层 idle kill）：
```json
{
  "heartbeat.interval.ms": "30000",
  "database.jdbc.url.properties": "autoReconnect=true&tcpKeepAlive=true",
  "connect.timeout.ms": "30000"
}
```
核心：heartbeat 间隔（30s）远小于网络 idle timeout（~431s），保持连接活跃。

## 关键教训

- **Release 前检查 CDC schema**：MySQL DDL 变更前必须通知 Debezium connector，否则 binlog 解析失败 → 全量 Snapshot → 数据延迟/缺口
- **Snapshot op_type=`r` 不同于 streaming**：配置了 `replacingmergetree.delete.column` 的表，必须处理 Snapshot 事件的 `_sign` 默认值
- **431s 不是 MySQL wait_timeout（8h）**：是网络中间层（ALB/NAT）idle TCP timeout，需 TCP keepalive 或 heartbeat 绕过
- **自定义 sink-connector pod 不走标准 Kafka Connect REST API（port 8083）**：先 `ss -tlnp` 或 `/proc/net/tcp6` 确认实际端口
- **connector 自恢复不代表数据完整**：Snapshot 期间写失败的 batch 需要手动验证数据缺口
