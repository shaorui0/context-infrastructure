---
metadata:
  kind: runbook
  status: draft
  summary: "StarRocks + Iceberg REST Catalog + Kafka Connect 部署常见故障排查手册（CRE-6630 preprod E2E 实战总结）"
  tags: ["starrocks", "iceberg", "kafka-connect", "helm", "deployment", "preprod"]
  first_action: "按故障现象匹配下面的坑编号，直接跳对应 section"
  related: ["cases/case-starrocks-fe-crashloop-bdb-ip-binding.md"]
  derived_from: "code_repos/feature-platform/reqs/cre-6630/fp-starrocks-deployment/docs/PITFALLS-preprod-e2e.md"
---

# StarRocks + Iceberg Deployment Runbook

快速定位：看 **connector task 状态** + **catalog pod 状态** + **FE pod 状态**。

---

## 坑 1: Iceberg REST Catalog JDBC 连接超时（静默失败）

**现象**（运行 2-3 天后出现）:
```
Kafka Connect task FAIL:
  ServiceFailureException: UncheckedSQLException:
    Failed to get table <tenant>.event_result from catalog rest_backend
Catalog pod 日志:
  CommunicationsException: The last packet successfully received from the server
  was 236,409,373 milliseconds ago ... is longer than server configured value of 'wait_timeout'
```

**根因**: Catalog JDBC URL 是裸连接字符串，无保活参数。MySQL 默认 `wait_timeout=28800` (8h)，空闲连接被 server 端断开，catalog 不感知。

**临时绕过**:
```bash
kubectl rollout restart deploy/iceberg-rest-catalog
```

**永久修复**: JDBC URL 加参数：
```
jdbc:mysql://fp-mysql.<ns>:3306/iceberg_catalog?autoReconnect=true&useSSL=false&connectTimeout=10000&socketTimeout=60000
```

---

## 坑 2: StarRocks builtin_storage_volume S3 路径错误

**现象**（创建 MV/表时报错）:
```
fail to create tablet: [Not found: Put object s3://cre-6630/preprod/...
  error: The specified bucket does not exist]
```

**根因**: StarRocks 自动创建的 `builtin_storage_volume` 路径只用了 `aws_s3_path`，没拼 `aws_s3_bucket`，导致 bucket 名在路径里。

**修复**: 在 init job 里显式创建 storage volume 并设为 default：
```sql
CREATE STORAGE VOLUME default_sv TYPE = S3
LOCATIONS = ('s3://<bucket>/<path>/starrocks-data/')
PROPERTIES (
  'aws.s3.region' = 'us-west-2',
  'aws.s3.use_instance_profile' = 'true',
  'aws.s3.endpoint' = 's3.us-west-2.amazonaws.com'
);
SET default_sv AS DEFAULT STORAGE VOLUME;
```

**验证**:
```sql
DESC STORAGE VOLUME builtin_storage_volume;
-- Location 应为 s3://<correct-bucket>/<path>/
```

---

## 坑 3: 多 Tenant Connector 共享 control topic 互相干扰

**现象**（注册第二个 connector 后）:
```
Commit timeout reached. Commit ID: xxx
committed to 0 table(s), valid-through null
-- 日志中出现两个 START_COMMIT（不同 commit ID，间隔几秒）
```

**根因**: 多个 connector coordinator 共享默认 `control-iceberg` topic，互相干扰 commit 协议。

**修复**: 注册 connector 时设置独立 control topic：
```json
{
  "iceberg.control.topic": "control-iceberg-{tenant}"
}
```
Control topic 由 Iceberg connector 启动时自动创建，Helm/基础设施无需改动。

---

## 坑 4: 单 Broker 环境 __transaction_state ISR 不匹配

**现象**（新环境 connector 启动反复 FAIL）:
```
TimeoutException: Timeout expired after 60000ms while awaiting InitProducerId
```

**根因**: 只有 1 个 Kafka broker，但 `__transaction_state` topic 配了 `min.insync.replicas=2`。Iceberg connector 强制使用 Kafka 事务，transactional producer 初始化失败。

**修复**（热生效，不重启 broker）:
```bash
kafka-configs.sh --bootstrap-server <kafka>:9092 \
  --entity-type topics --entity-name __transaction_state \
  --alter --add-config min.insync.replicas=1
```

**验证**:
```bash
kafka-configs.sh --bootstrap-server <kafka>:9092 \
  --entity-type topics --entity-name __transaction_state --describe
# min.insync.replicas=1
```

**Rollback**: 同命令改回 `min.insync.replicas=2`

---

## 坑 5: Cleanup 必须包含 Iceberg Catalog 元数据

**现象**（清理环境后重建 connector）:
```
ServiceFailureException: NotFoundException:
  Location does not exist: s3://.../metadata/00007-xxx.metadata.json
```

**根因**: S3 文件和 connector 都删了，但 Iceberg Catalog 的 MySQL 元数据没删。Catalog 记住 table 存在，新 connector 启动时 `loadTable()` 去 S3 找已删除的 metadata file。

**正确 cleanup 顺序**:
```bash
# 1. 删 connector
curl -X DELETE http://<kafka-connect>/connectors/<connector-name>

# 2. 删 Iceberg catalog 注册（关键！）
curl -X DELETE http://<catalog>/v1/namespaces/<tenant>/tables/event_result
curl -X DELETE http://<catalog>/v1/namespaces/<tenant>

# 3. 删 S3
aws s3 rm s3://<bucket>/<path>/<tenant>/ --recursive
```

---

## 坑 6: iceberg-catalog-init Job 静默失败，Catalog CrashLoop

**现象**（新环境首次部署）:
```
iceberg-rest-catalog pod: CrashLoopBackOff（99+ 次重启）
日志: CJException: Unknown database 'iceberg_catalog'
helm hook job 找不到（hook-delete-policy: hook-succeeded,before-hook-creation）
```

**根因**: Helm hook job 负责 `CREATE DATABASE iceberg_catalog`，失败后被 policy 清掉，不留痕迹。Catalog pod 启动时连 MySQL 发现数据库不存在 → 崩溃。

常见失败原因:
- init job secret 里的密码与实际 MySQL root 密码不一致
- init job 创建时 MySQL pod 还没 ready
- 网络策略阻止 init job 连 MySQL

**修复**:
```bash
# 手动创建数据库
kubectl exec starrocks-fe-0 -- mysql -h fp-mysql.<ns> -P 3306 -u root -p<PASS> -e "
  CREATE DATABASE IF NOT EXISTS iceberg_catalog CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
"
# 重启 catalog
kubectl rollout restart deploy/iceberg-rest-catalog
```

**排查思路**: Catalog CrashLoop 时，先看日志关键字 `Unknown database`。如果有，是 init job 问题；如果没有，是 MySQL 连通性问题。

---

## 坑 7: 单 Broker Coordinator Consumer Group 不稳定

**现象**（单 broker 环境运行一段时间后）:
```
新注册的 connector commit 永远 timeout（committed to 0 table(s)）
The coordinator is not aware of this member → re-join → fail（反复循环）
```

**根因**: 单 broker 环境 Kafka consumer group coordinator 不稳定，KC pod 内部状态变脏后新 connector control topic consumer 无法 join group。

**解决**: 重启 KC pod（3-broker 生产环境不会有此问题）：
```bash
kubectl rollout restart deploy/iceberg-kafka-connect
```

**缓解配置**（已加到 kafka-connect.yaml）:
```yaml
CONNECT_OFFSET_FLUSH_INTERVAL_MS: "10000"
CONNECT_SESSION_TIMEOUT_MS: "30000"
CONNECT_HEARTBEAT_INTERVAL_MS: "10000"
```

---

## StarRocks 性能调优参考

CN sizing 和 session 变量调优（来自 CRE-6630 benchmark 实测）：

| 配置 | 效果 |
|------|------|
| CN replicas: 1→2，CPU: 2→4 cores | 文件扫描分摊，pipeline_dop auto 从 1→2 |
| `connector_io_tasks_per_scan_operator=32` | 并发 S3 请求数，大于核数反而慢（dop 限制） |
| `datacache_disk_path` + `datacache_mem_size=4GB` + `datacache_disk_size=20GB` | 热数据命中本地 cache，冷→热从 8.9s 降到 4.3s |
| `--add-opens=java.base/java.util=ALL-UNNAMED` | Java 17 + Kryo 序列化兼容性 bug fix |

**经验**: `pipeline_dop` 不能超过 CN CPU 核数，否则线程争抢反而更慢。
