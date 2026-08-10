# Database Dashboards

后端 DB 层是延迟链路 `client → apisix → ingress(nginx) → fp → yuga/mysql` 的最末端。
两块仪表盘分别覆盖 YugabyteDB（YCQL 主要流量）和 MySQL（Percona PMM 风格 overview）。

数据源：默认 `${PromDs}` 变量（Prometheus），MySQL 部分面板硬编码到 `CA5qZASHz`。
共同的 label key：`kubernetes_cluster`、`kubernetes_namespace`。

---

## YugabyteDB（1IGjQaiMk）

- 标题：YugabyteDB
- 标签：YugabyteDB / yugabytedb / ysql / ycql / yedis
- Panel 数：29（5 个 row + 24 个面板）
- 默认时间窗：`now-3h`
- 最近编辑：runzi.yang，2026-03-24
- URL: https://grafana-mgt.dv-api.com/d/1IGjQaiMk/yugabytedb

### 变量

| 变量 | 类型 | label | 用途 |
| --- | --- | --- | --- |
| `PromDs` | datasource | — | Prometheus 数据源选择 |
| `cluster` | query | — | `kubernetes_cluster`，物理 / k8s 集群 |
| `dbcluster` | query | YB DB Cluster | `kubernetes_namespace`，YB 实例所在 namespace（一个 YB 集群对应一个 namespace） |
| `node` | query | node | master 节点过滤 |
| `nodeInstance` | query | tmaster | master 节点的具体 instance |
| `serverNode` | query | tserver | tserver 节点过滤 |
| `serverNodeInstance` | query | tserver | tserver instance |

关键点：`dbcluster` 是 namespace（不是 cluster），filter 时要写 `kubernetes_namespace="$dbcluster"`，不是 cluster label。`cluster` 是 k8s cluster。`node` / `nodeInstance` 切 master，`serverNode` / `serverNodeInstance` 切 tserver（即 master vs tserver 通过两组变量区分）。

### 面板分组

行（rows）：
- Master Node Status（100）
- Tserver Node Status（103）
- Yugabyte Connections（166）
- Master（144）
- YCQL Ops & Latency（8）
- Tablet Server（24）
- RocksDB（79）

YCQL Ops & Latency 行下的核心面板：

| ID | 标题 | 看什么 |
| --- | --- | --- |
| 14 | Total YCQL Ops / Sec | 总 QPS（Select/Insert/Update/Delete/Others/Transaction 6 类汇总） |
| 74 | YCQL Op Latency (Avg) | 平均延迟（6 类语句分项） |
| 21 | YCQL Op Latency (P95) | P95 延迟 |
| 64 | YCQL Op Latency (P99) | P99 延迟（最常用） |
| 162 | YCQL Op Latency (max) | 最坏单条延迟 |
| 33/32/31/30/2/34 | per-stmt Op/sec/Tserver | 按语句类型 + 按 tserver 拆分 QPS（找热点 tserver） |
| 16/37/36/38/35/39 | per-stmt Avg latency / Tserver | 按语句类型 + tserver 拆分延迟 |
| 73 | Reactor Delays | RPC reactor 三段时间：incoming queue、outbound transfer、outbound call queue |
| 72 | YCQL Latency Breakdown | ProcessRequest / ParseRequest / AnalyzeRequest / ExecuteRequest 四段时间，判断慢在解析/分析/执行 |
| 77 | YCQL Inbound Connections | rpc_connections_alive、rpc_connections_created（连接抖动 / 短连暴增） |
| 71 | RPC queue sizes (YCQL) | `rpcs_in_queue_yb_cqlserver_CQLServerService`，max 和 per-pod，**排队就是过载** |
| 26 | Response Size (bytes) | 返回字节，大 payload 排查 |

Tablet Server / RocksDB / Master / Connections 行在 dashboard 中以 row 形式存在但具体子面板列表未在 summary 里展开（要点开 row 才能看 tablet load / compaction / WAL 这些指标）。**因此 task prompt 里提到的 "tablet load / compaction / WAL / master vs tserver split" 需要展开对应 row 才能确认，summary 中没法直接证实有专门 panel。**

### Top-3 最常用 panel 的 PromQL

1. **YCQL Op Latency (P99)** (id=64)，6 条 series（Select/Insert/Update/Delete/Others/Transaction），都形如：
   ```
   max(rpc_latency{kubernetes_cluster="$cluster", kubernetes_namespace="$dbcluster",
                    quantile="p99",
                    saved_name="handler_latency_yb_cqlserver_SQLProcessor_SelectStmt"})
   ```
   注意 quantile 是字符串 `"p99"`，不是 Prom histogram 的 0.99；这是 YB 自己暴露的 summary。

2. **RPC queue sizes (YCQL)** (id=71)：
   ```
   max(rpcs_in_queue_yb_cqlserver_CQLServerService{kubernetes_cluster="$cluster", kubernetes_namespace="$dbcluster"})
   rpcs_in_queue_yb_cqlserver_CQLServerService{kubernetes_cluster="$cluster", kubernetes_namespace="$dbcluster"}
   ```
   一条 max（整体），一条 per-pod（找受害 tserver）。**队列 > 0 持续即说明 tserver CPU / IO 跟不上**。

3. **YCQL Latency Breakdown** (id=72)，4 段：
   ```
   sum(irate(rpc_latency_sum{..., saved_name="handler_latency_yb_cqlserver_CQLServerService_ProcessRequest_sum"}[5m]))
   / sum(irate(rpc_latency_count{..., saved_name="..._ProcessRequest_count"}[5m]))
   ```
   同样形式的 ParseRequest / AnalyzeRequest / ExecuteRequest。**Execute 占大头通常意味着真正 IO/replication 慢；Parse/Analyze 占大头通常是大量首次出现的 query 文本**。

### 4️⃣ Reactor Delays（id=73）也很重要

三条 series：
- `rpc_incoming_queue_time_*`：入队等待
- `handler_latency_outbound_transfer_*`：出站传输
- `handler_latency_outbound_call_queue_time_*`：出站调用队列

入队延迟高 = tserver 接收侧拥塞；出站队列高 = tserver 之间互相 RPC（replication / leader → follower）拥堵。

---

## MySQL Overview（MQWgroiiz）

- 标题：MySQL Overview（来自 Percona PMM 模板）
- Panel 数：53（多个 row + 大量 graph + 几个 singlestat）
- 默认时间窗：`now-15m`，自动刷新 1m
- 最近编辑：runzi.yang，2026-01-05
- URL: https://grafana-mgt.dv-api.com/d/MQWgroiiz/mysql-overview

### 变量

| 变量 | 类型 | label | 用途 |
| --- | --- | --- | --- |
| `PromDs` | datasource | — | 注意：部分面板硬编码 `CA5qZASHz` 不读这个变量 |
| `interval` | interval | Interval | rate 时间窗（默认 `$__interval`） |
| `cluster` | query | — | `kubernetes_cluster` |
| `namespace` | query | — | `kubernetes_namespace`（regex 匹配，写 `=~`） |
| `mysql` | custom | — | mysql 实例 id；面板里同时尝试 `app="$mysql"` 和 `instance_name="$mysql"` 两种 label，因为不同 exporter 时代字段不一样 |

### 面板分组（按 row）

| Row | 关键面板 | 关注点 |
| --- | --- | --- |
| (顶部，无 row) | IO_thread status (397), SQL_thread status (399), InnoDB Buffer Pool Size (51), Buffer Pool % of RAM (52), MySQL Uptime (12), Current QPS (13) | 复制状态 + 容量基线 |
| Connections (383) | MySQL Connections (92), mysql_slave_status_seconds_behind_master (401), MySQL Client Thread Activity (10) | **连接数耗尽 / 复制延迟 / threads_running 暴涨** |
| Table Locks (384) | MySQL Questions (53), Thread Cache (11) | Questions 是 client 提交量基线 |
| Temporary Objects (385) | MySQL Temporary Objects (22), MySQL Select Types (311) | 全表扫 / 内存临时表暴涨 |
| Sorts (386) | MySQL Sorts (30), **MySQL Slow Queries (48)** | 慢查询计数 |
| Aborted (387) | MySQL Aborted Connections (47), MySQL Table Locks (32) | 连接被踢、锁等待 |
| Network (388) | Network Traffic (9), Network Usage Hourly (381) | 出入流量异常 |
| Memory (389) | MySQL Internal Memory Overview (50) | buffer pool / key buffer / query cache 分布 |
| Command, Handlers, Processes (390) | Top Command Counters (14/39), Handlers (8), Transaction Handlers (28), Process States (40/49) | 命令类型分布、handler read 模式（`read_rnd_next` 高 = 全表扫多） |
| Query Cache (391) | Query Cache Memory (46), Activity (45) | 旧版 query_cache 争用 |
| Files and Tables (392) | File Openings (43), Open Files (41) | fd 耗尽 |
| Table Openings (393) | Table Open Cache Status (44), Open Tables (42) | table_open_cache 撞顶 |
| Table Definition Cache (394) | Table Definition Cache (54) | 定义缓存 |
| System Charts (395) | I/O Activity (31), Memory Distribution (37), CPU Usage / Load (2), Disk Latency (36), Network Traffic (21), Swap Activity (38) | OS 层指标（node_exporter 类） |

### Top-3 最常用 panel 的 PromQL

1. **Current QPS** (id=13)：
   ```
   rate(mysql_global_status_queries{kubernetes_cluster="$cluster", kubernetes_namespace=~"$namespace", app="$mysql"}[$interval])
   or irate(...[5m])
   or rate(... instance_name="$mysql" ...)
   ```
   `or` 兜底语法：先 `app=` 再 `instance_name=`，两种 exporter 标签都覆盖。

2. **MySQL Connections** (id=92)，3 条 series：
   ```
   max(max_over_time(mysql_global_status_threads_connected{...}[$interval]) or mysql_global_status_threads_connected{...})
   mysql_global_status_max_used_connections{...}
   mysql_global_variables_max_connections{...}
   ```
   把当前 / 历史最大 / 配置上限三条画在一起，**接近上限就要扩 max_connections 或排查泄露**。

3. **MySQL Slow Queries** (id=48)：
   ```
   rate(mysql_global_status_slow_queries{kubernetes_cluster="$cluster", kubernetes_namespace=~"$namespace", app="$mysql"}[$interval])
   ```
   依赖 mysqld `long_query_time` 阈值；只是计数，**不告诉你哪条 SQL，需要去 slow log / pt-query-digest**。

### Replication lag panel (id=401)

```
mysql_slave_status_seconds_behind_master{master_host="172.31.36.37"}
```

**注意：master_host 硬编码 `172.31.36.37`，没用变量。** 如果有多个 master 或者 IP 换了，这个 panel 就是哑的。改造时要把 host 改成模板变量。

### Threads_running (id=10)

```
max_over_time(mysql_global_status_threads_running{...}[$interval])
```

threads_running 暴涨往往比 threads_connected 更能预警：连接还在但都在等锁 / IO，QPS 不一定降。

---

## 判断 DB 是不是瓶颈（与 SLA dashboard 联动）

按链路 client → apisix → ingress → fp → DB 自下而上排除：

1. **先看 SLA dashboard 的 fp → DB 段延迟**（fp 侧 client metrics）。如果 fp 端没看到 DB 调用变慢 → DB 不是瓶颈，问题在 fp 之前。
2. **YB 侧三件套同时升高**：
   - YCQL P99 (panel 64) 升
   - RPC queue size (panel 71) > 0 且持续
   - Reactor Delays (panel 73) 的 incoming queue time 升
   → 基本可以判定 YB tserver 真过载。
3. **YCQL P99 升 + queue 不升 + Latency Breakdown (panel 72) 的 ExecuteRequest 占大头** → 慢在底层 RocksDB / replication，看 Tablet Server / RocksDB row（compaction、WAL）。
4. **MySQL 侧三件套**：
   - QPS (panel 13) 正常或下降，但 threads_running (panel 10) 暴涨 → 锁/IO 卡住
   - Slow Queries (panel 48) 速率突增 → 出现长 SQL
   - Connections (panel 92) 撞 max → 客户端层重连风暴或泄露
5. **Replication lag (panel 401)** 升而 master 写 QPS 没变 → slave IO/SQL thread 卡住（看 397/399 的 IO/SQL_thread status）。
6. **DB 指标全正常但 fp 看到 DB 调用慢** → 上行链路（fp ↔ DB 网络、连接池、DNS）。这时回到 fp 自己的 client metrics、apisix / ingress dashboard。

经验顺序：**SLA dashboard 看是不是 fp → DB 段慢 → 看 YB/MySQL 的 latency 面板 → 看 queue / threads_running 决定是 DB 自身过载还是其它**。

---

## 典型 alert → 看哪个 panel

| 现象 / Alert | 主看面板 | 辅助 |
| --- | --- | --- |
| FP timeout / fp 报 DB call 超时（YCQL 侧） | YCQL P99 (64)、RPC queue (71) | Reactor Delays (73)、Latency Breakdown (72) per-tserver 分布 (16/37/...) 找热点 |
| YCQL 整体 P99 抖但 QPS 没变 | Latency Breakdown (72) ExecuteRequest 段 | RocksDB / Tablet Server row（compaction、WAL） |
| YCQL 单 tserver 慢 | per-stmt Avg latency / Tserver (16/37/36/38/35/39) | per-stmt Op/Sec/Tserver (33/32/...) 看是不是 hot shard |
| Compaction storm（YB） | RocksDB row 下的 compaction 面板（需要展开 row 确认，summary 未列出） | YCQL P99 同时上扬印证 |
| MySQL connection 耗尽 | MySQL Connections (92) | Aborted Connections (47)、Thread Cache (11) |
| MySQL slow query spike | Slow Queries (48) | Top Command Counters (14)、Select Types (311)、Handlers (8) `read_rnd_next` |
| MySQL replication lag | mysql_slave_status_seconds_behind_master (401) | IO_thread status (397)、SQL_thread status (399) |
| MySQL threads_running 暴涨 | Client Thread Activity (10) | Table Locks (32) waited 数、Process States (40) |
| MySQL "too many open files" | Open Files (41)、File Openings (43) | Table Open Cache Status (44) |
| MySQL buffer pool 压力 | Buffer Pool Size / % RAM (51/52) | Internal Memory Overview (50)、Swap Activity (38) |

---

## 选择变量的坑

### YugabyteDB

- `dbcluster` 实质是 **namespace**，不是 cluster；过滤用 `kubernetes_namespace="$dbcluster"`。一个 k8s cluster 里可能跑多个 YB 集群（多个 namespace），不要把 `cluster` 和 `dbcluster` 搞混。
- Master / tserver 用两组完全独立的变量：`node` + `nodeInstance` 是 master，`serverNode` + `serverNodeInstance` 是 tserver。`Master Node Status` / `Tserver Node Status` 两个 row 分别消费这两组变量。**调错变量会出现"面板空白但 metric 存在"。**
- `rpc_latency` 的 `quantile` label 是字符串 `"p99"` / `"p95"` / `"p50"`，不是 Prom histogram 的 `0.99`；自己写 ad-hoc query 容易踩。
- saved_name 拼写区分大小写：`SelectStmt` / `InsertStmt` / `UpdateStmt` / `DeleteStmt` / `OtherStmts`（注意 Others 是复数 `OtherStmts`）/ `Transaction`。

### MySQL

- `namespace` 用 regex 匹配（`kubernetes_namespace=~"$namespace"`），可以多选；`cluster` 是精确匹配。
- `mysql` 变量在面板里**同时尝试 `app="$mysql"` 和 `instance_name="$mysql"`**，用 `or` 链式兜底。这是适配新旧两版 mysqld-exporter 的产物。如果你写自己的 query，建议两个都覆盖：
  ```
  metric{... app="$mysql"} or metric{... instance_name="$mysql"}
  ```
- 数据源混用：默认 `${PromDs}` 由变量决定，但 Connections、Threads、Slow Queries、Aborted、Table Locks 等核心面板**硬编码 datasource UID `CA5qZASHz`**。如果未来 datasource 重命名 / 迁移，这些面板要单独改。
- Replication lag panel (401) 的 `master_host="172.31.36.37"` **硬编码 IP**，没用 cluster/namespace/mysql 变量。换 master IP 后此 panel 会变空白且不会自动报错。
- 默认时间窗只有 15 分钟，自动刷新 1m；做事后回溯（postmortem）时一定先把时间窗拉宽到事件覆盖区。
- `interval` 变量影响所有 `rate(...[$interval])`：interval 太小（如 30s）在低流量 MySQL 上会出现锯齿；interval 太大会平滑掉 spike。
