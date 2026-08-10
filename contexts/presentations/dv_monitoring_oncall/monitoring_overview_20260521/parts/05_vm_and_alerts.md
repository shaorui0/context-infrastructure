# VictoriaMetrics & Alert 体系

> 数据采集时间：2026-05-21
> 数据来源：MCP `victoriametrics.*`（rules / alerts / tsdb_status / top_queries / docs）+ MCP `grafana.*`（alerting_manage_rules / alerting_manage_routing / list_datasources）
> 目标对象：DataVisor 主 VM 实例 `vm-mgt-a.dv-api.com`，挂在 Grafana 上的 4 个 Prometheus DS

---

## VictoriaMetrics 角色（PromDs / vmui / 何时直接查 vm）

### VM 在监控栈中的位置

DataVisor 的 metric pipeline 大致是：

```
各 k8s 集群 (vmagent / prom exporters / node-exporter / kafka-exporter / mysql-exporter / yuga-exporter / 各自服务的 /metrics)
    │  remote_write
    ▼
vm-mgt-a.dv-api.com (VictoriaMetrics 集群)         ←──┐ vmalert evaluate rules
    ├── /api/v1/query, /query_range  (PromQL/MetricsQL) │
    ├── /vmui/                       (Web UI)           │
    ├── /api/v1/status/tsdb          (cardinality)      │
    └── /api/v1/alerts, /rules       (vmalert proxy) ───┘
            │
            ▼
        Slack / 其他 webhook
```

vmalert 是 VM 自带的告警 evaluator，它周期性跑 PromQL，生成 `firing/pending` 告警，发到 alertmanager / webhook。VM 上 alertmanager 的 receiver 配置不在 Grafana 一侧——见下文 "Alert 路由"。

### Grafana 里的 Prometheus 数据源（PromDs 变量解析）

通过 `mcp__grafana__list_datasources type=prometheus` 拿到的 4 个 datasource（全部 type=prometheus，实际后端都是 VM）：

| name | uid | 说明 |
|---|---|---|
| `vms-victoria-metrics-single-server` | `CA5qZASHz` | 主 DS。Dashboard 里 `$PromDs` 默认解析到这里 |
| `prometheus-pods` | `_n_1eKINz` | 单独配置的视图（pod 维度） |
| `prometheus-services` | `BXkAnTSNz` | 单独配置的视图（service 维度） |
| `Deepflow-Prometheus` | `NxPzlV3Hk` | DeepFlow 提供的额外 metrics |

> Dashboard variable `$PromDs` 多数情况下等价于 `CA5qZASHz`。当你看到一个 panel 用了 `${PromDs}` 又看不到数据，先确认变量没被切到 `Deepflow-Prometheus`（它 metric 命名不一样）。

### 什么时候直接打 vmui（而不是 Grafana）

vmui = VictoriaMetrics 自带的 web 查询 UI，地址：`https://vm-mgt-a.dv-api.com/vmui/`。

它是 Grafana 之外的 escape hatch。在以下场景比 Grafana 更顺手：

1. **Dashboard 没有这个 metric / 没有合适的 panel** —— 直接 vmui 写一句 MetricsQL。
2. **要快速看 raw 时间序列**（例：`my_metric[10m]` instant query 拿原始点）—— Grafana 必须挂 panel，vmui 一行搞定。
3. **调试 alert query**：firing alert 的 `source` 字段就是 vmui 链接，点进去直接复现 alert 的 PromQL。比如刚从 MCP 拿到的一条 firing `FPTopicsOffsetIncreaseZero`：
   ```
   source = https://vm-mgt-a.dv-api.com/vmui/#/?g0.expr=sum+by+%28kubernetes_cluster_groups%2C+kubernetes_namespace%2C+topic%29+%28increase%28kafka_topic_partition_current_offset%7B...%7D%5B30m%5D%29%29+%3C+1
   ```
   点开就是 alert 的当前求值结果。
4. **排查 cardinality / 高内存查询** —— vmui 顶部 tab 有 `Cardinality`、`Top queries`、`Active queries`、`Trace`。
5. **想看 metric metadata（type / help）** —— vmui 的 `Metrics Explorer` 直接列。

### vmui 主要 tab 速查

| Tab | 用途 | 等价 API（MCP 工具同源） |
|---|---|---|
| Query | PromQL/MetricsQL 查询 | `/api/v1/query`, `/api/v1/query_range` |
| Explore → Metrics | 列所有 metric name + metadata | `mcp__victoriametrics__metrics`, `metrics_metadata` |
| Explore → Cardinality | 高 cardinality metric / label / pair | `tsdb_status` |
| Explore → Top queries | 最慢 / 最频繁 / 总耗时最高的 query | `top_queries` |
| Explore → Active queries | 当前正在跑的 query | `active_queries` |
| Alerts / Groups | vmalert 当前 alert 与 rule | `alerts`, `rules` |
| Trace | 查询执行 trace（哪一步慢） | URL 参数 `trace=1` |

### MetricsQL ≠ 严格 PromQL（容易踩的坑）

VM 用的是 **MetricsQL**，向后兼容 PromQL 但有几处差异（来自官方 doc）：

- `rate()` / `increase()` **不做外推**，所以 `increase(counter[5m])` 在 slow-changing counter 上返回整数（Prometheus 会返回带小数的"估算"值）。意味着你写的 alert 阈值 `> 0` 在 VM 上不会因为外推误触发。
- `step` 小于 scrape interval 时 VM 还能给出 rate（Prometheus 会空）。
- MetricsQL 把 `scalar` 和无 label 的 `instant vector` 视为同一类型。
- MetricsQL 会丢掉 `NaN`（Prometheus 保留）——所以 `(-1)^0.5` 在 vmui 上返回空。
- MetricsQL **保留 metric name** 经过 `min_over_time(foo)` / `round(foo)` 后名字还是 `foo`。

---

## vmui 基本使用 + top_queries / cardinality 排查

### Cardinality 排查 —— `tsdb_status` / vmui Cardinality tab

当前实例规模（2026-05-21 采样）：

```
totalSeries          = 42,742,881   (~ 4270 万 active series)
totalLabelValuePairs = 730,498,786
```

**单个 metric 名 series 数 TOP 10**（来自 `tsdb_status`，按 `seriesCountByMetricName` 排序）：

| metric | series 数 | 说明 |
|---|---:|---|
| `kubernetes_monitoring_requests_percentage_time_ingress_nginx_bucket` | 3,457,929 | 自研 nginx histogram，request_url 维度炸 |
| `kubelet_runtime_operations_duration_seconds_bucket` | 899,488 | kubelet histogram |
| `storage_operation_duration_seconds_bucket` | 711,050 | kubelet storage histogram |
| `apiserver_request_duration_seconds_bucket` | 673,252 | k8s apiserver |
| `kubernetes_feature_enabled` | 620,716 | feature gate 矩阵 |
| `container_tasks_state` | 571,811 | cadvisor |
| `etcd_request_duration_seconds_bucket` | 563,679 | etcd |
| `apiserver_request_sli_duration_seconds_bucket` | 468,766 | apiserver SLI |
| `container_memory_failures_total` | 457,259 | cadvisor mem failures |
| `kafka_topic_partition_*` (5 个 metric) | ~330k each | partition 数 × 集群数 |

**Label cardinality TOP 5**（按 `labelValueCountByLabelName`，即该 label 不同值的数量）：

| label | 不同值数量 | 危险等级 |
|---|---:|---|
| `request_url` | 177,815 | 高。url path 里嵌业务参数会爆 |
| `id` | 89,043 | 高。哪个 metric 加了 `id={uuid}` |
| `name` | 70,380 | 中。需 drilldown 看是哪个 metric |
| `container_id` | 54,343 | 高。每次 pod 重建变 |
| `path` | 52,745 | 高 |

**判断 label 是否炸的标准动作**：

1. vmui → Explore → Cardinality
2. 选 `Top labels` 或 `Top label=value pairs`
3. 圈出值 >5万 的 label，进 `focusLabel=<label>` 看是哪个 metric 贡献的
4. 找到 metric → 找产生它的 exporter / scrape job → 在 vmagent 上加 `metric_relabel_configs.drop` 或在源端去掉这个 label

**对应 MCP 调用**（agent 友好）：
```
mcp__victoriametrics__tsdb_status(topN=20)
mcp__victoriametrics__tsdb_status(focusLabel="request_url", topN=20)
mcp__victoriametrics__tsdb_status(match='{__name__="kubernetes_monitoring_requests_percentage_time_ingress_nginx_bucket"}', topN=20)
```

### Top queries / Active queries —— 找慢查询

`mcp__victoriametrics__top_queries(topN=15)` 返回 3 个排序：

- `topByCount` —— 最高频。当前 TOP 1 是 alert rule 反复求值的 `kube_persistentvolumeclaim_status_phase{phase="Pending", ...} == 1`（80 次 / 10 分钟），完全正常。
- `topByAvgDuration` —— 平均最慢。当前 TOP 1 是 `rate(kubernetes_monitoring_request_total_ingress_nginx[1m])` **2.9 秒平均**（注意这个 query 完全没有 label filter，扫全表）—— 这是一类典型的 "naive 写法"，应该加 `{kubernetes_cluster=~"..."}` 或者改用 recording rule。
- `topBySumDuration` —— 总耗时炸的。同样这个无 filter 的 nginx rate 排第一，10 分钟内累计耗了 **117 秒 CPU**。

排查指南：
- 看到 alert latency 高 / VM CPU 飙 → 先 `top_queries(topN=20)`，按 `sumDurationSeconds` 排序
- 在调试时如果 vmui 卡住 → `active_queries` 看是不是有人在跑 `rate(...[24h])` 这种巨型 range query

### 关键 metric metadata（用 `metrics_metadata` 反查）

新接手 oncall 时不知道某 metric 是什么 type / 单位，直接：
```
mcp__victoriametrics__metrics_metadata(search="kafka")
mcp__victoriametrics__metrics_metadata(metric="kube_pod_container_status_restarts_total")
```

vmui 上对应 Explore → Metrics → 点击 metric。

---

## Alert 路由：Grafana managed vs VM alertmanager

### 关键判断：DataVisor 的告警 **完全** 走 vmalert，不走 Grafana managed alerts

MCP 验证：

```python
mcp__grafana__alerting_manage_rules(operation="list", rule_limit=200, limit_alerts=0)
# → null   ← 没有任何 Grafana-managed rule
mcp__grafana__alerting_manage_routing(operation="get_contact_points", limit=100)
# → []     ← Grafana 一侧没有 contact point
mcp__grafana__alerting_manage_routing(operation="get_notification_policies")
# → {"group_by":["grafana_folder","alertname"], "receiver":"empty", "routes":null}
#   只有一个默认 root policy 指到 "empty" receiver，等于没接
```

结论：

- **Grafana alerting 模块在 DataVisor 没启用。** 看 alert 不要去 Grafana 左边栏的 "Alerting"。
- **所有 alerting rule 都跑在 vmalert 上**（VM 实例自带的 evaluator），数量 ~540（见下一节）。
- **告警出口（webhook → Slack / 其他）** 由 vmalert 配置里的 `-notifier.url` 指到一个独立 alertmanager（MCP 拿不到这个 alertmanager 的 receiver 列表——`get_contact_points(datasource_uid=...)` 也返回空）。要看 receiver / route 必须直接看 alertmanager 的 ConfigMap / Helm values。

### Rule 来源（按 file 分布）

通过 `mcp__victoriametrics__rules` 拿到全部 49 个 rule group，分布在 33 个 yaml 文件里：

| 文件 | alert 数 | 主题 |
|---|---:|---|
| `self_add_rules.yml` | 78 | 业务方临时加的，rule_engine / batch / 客户级 SLA |
| `feature_platform_alert_rules.yml` | 68 | FP 子系统（FP Async/Cron/Batch/Stderr/...） |
| `rt_sla.rules.yml` | 63 | RT 业务 SLA（per-client RT detection rate 等） |
| `k8s_system_alert_rules.yml` | 49 | K8sPod*, K8sNode*, K8sDeployment*, K8sJob*, K8sPersistentVolume* |
| `base_promtail_rt_rules.yaml` | 42 | Apisix / Ingress P95/P99 (基于 Loki 派生 metric) |
| `base_aws_ingress_alert_rules.yml` | 37 | AwsAlb*, AwsApiGateway*, AwsLambda* |
| `batch_sla_alert_rules.yml` | 27 | Batch 任务 SLA |
| `kafka_rules.yml` | 19 | Kafka_* (consumer lag, exporter down, offline partition) |
| `system.rules.yml` | 18 | 通用 system |
| `node_alert_rules.yml` | 17 | Node*（disk/cpu/mem/network） |
| `litellm_alert_rules.yaml` | 16 | LiteLLM proxy（这个是新接的 LLM 网关） |
| `rule_engine_v3_rules.yml` | 13 | RuleEngineV3* |
| `milvus_rules.yml` | 12 | Milvus*（向量库） |
| `mysql_rules.yml` | 11 | Mysql* / Hikari* |
| `loki_rules.yaml` | 11 | Loki*（Loki 自己的健康度，LokiPanics=CRITICAL） |
| `batch_abnormal_alert_rules.yml` | 10 | batch_abnormal.* |
| `yugabytedb_rules.yml` | 6 | yugabyetdb*（注意拼写：原 yaml 就是 typo） + YugabyteDB* |
| `nginx_postback_rules.yml` | 5 | AllClientNginxPostbackFailure |
| `cluster_monitor_v2.yml` | 5 | cluster_monitor_v2 |
| `blackbox_alert_rules.yml` | 5 | Blackbox_Up_Check / Http_* / SSL |
| `cpu_rules.yml` | 4 | HighCpuUsageOfContainer* |
| `ui_alert_rules.yml` | 4 | ui.* |
| `sink-connector.yml` | 4 | Connector* (Kafka Connect) |
| `redis_rules.yml` | 3 | redis-cluster |
| `clickhouse_rules.yml` | 2 | ClickHouse* |
| `batch_event_time_alert_rules.yml` | 2 | batch_event_time |
| `base_dapp_alert_rules.yml` | 2 | DappKafka* |
| `test_rules.yml` | 2 | （测试，不该 firing） |
| `ssl_expiry.rules.yml` | 1 | SSLCertExpiringSoon |
| `pushgateway.yml` | 1 | PushgatewayDown |
| `sml_abnormal_alert_rules.yml` | 1 | SMLScoreFeatureHighPSI |
| `dash_cluster_alert_rules.yml` | 1 | DaskClusterDown 类 |
| `aws_cloudwatch_alert_rules.yml` | 1 | AwsLoadBalancerTargetGroupUnhealthy |

**合计 540 条 alerting rule，0 条 recording rule**（注意：`record.yaml` 里 group 存在但 rules 为空——`rules:[]`，意味着 recording rule 可能配在别的地方，或者已经被搬走了）。

### Severity 分布

| severity label | 条数 | 含义（DV 约定） |
|---|---:|---|
| `PAGER` | 142 | 触发 PagerDuty / oncall page |
| `HIGH` | 283 | Slack 高优通道 |
| `MEDIUM` | 18 | Slack 普通通道 |
| `WARNING` | 6 | 信息 |
| `CRITICAL` | 1 | `LokiPanics`（独占） |
| `(无 severity 标签)` | 91 | 注意：~17% 的 rule 没设 severity，会按 alertmanager 的 default route 走 |

### Team 分布（决定路由到哪个 Slack channel / oncall）

| team label | 条数 |
|---|---:|
| `fp` | 276 |
| `infra` | 181 |
| `decision` | 5 |
| `(无 team 标签)` | 79 |

> `team` label 是 alertmanager route 的分流键。没标 team 的 79 条会进 default channel —— 这些就是 oncall 经常吐槽 "不知道该谁处理" 的来源。

---

## 告警目录（按类别）—— 真实 rule 名 + 严重度 + 应对 dashboard

> 下面所有 rule 名都来自 `mcp__victoriametrics__rules` 实拉。`*` 表示存在多个 per-client 变种（如 `_Affirm`, `_Tabapay`, `_Bookingcom`, `_Pinterest`, `_CCInfra`, `_Neo`, `_ForEWS` 等后缀，全是同一个模板按客户/集群分裂出来的）。

### A. Latency / SLA / Ingress

| Rule | Severity | 含义 | FIRST dashboard |
|---|---|---|---|
| `RTIngressP95ResponseTime*` (多客户变种) | PAGER | k8s ingress nginx 报的 RT P95 延迟过高（Loki 派生） | RT SLA dashboard / Ingress nginx |
| `RTIngressP99ResponseTime*` / `RTIngressP999ResponseTime` | PAGER | RT P99/P999 延迟过高 | 同上 |
| `RTIngress500Response` | PAGER | RT ingress 5xx 比例上升 | RT SLA / Loki ingress logs |
| `IngressNginxNon200` | HIGH | 通用 ingress non-200 | nginx ingress dashboard |
| `IngressNginx429` | HIGH | rate limit 触发 | nginx + 客户端 QPS |
| `IngressNginx499` | PAGER | client 端断开（典型上游慢） | nginx + 上游 RT |
| `IngressSLADropped` | HIGH | RT SLA 跌破 99.95% | RT SLA |
| `ApisixP95ResponseTime*` / `ApisixP99ResponseTime*` | PAGER | Apisix 入口 P95/P99 延迟 | Apisix dashboard |
| `ApisixSLADropped` | HIGH | Apisix SLA 跌破 99.95% | Apisix dashboard |
| `ApisixQpsZero` | PAGER | Apisix 某 endpoint QPS=0 | Apisix dashboard |
| `EastRTIngressP95/P99ResponseTime*` | PAGER | East region ingress 延迟 | RT SLA (region 切到 east) |
| `EastHighRTIngressP95/P99ResponseTime` | PAGER | east region 高 QPS ingress 延迟 | 同上 |
| `AwsAlbP95LatencyHigh*` / `AwsAlbP99LatencyHigh*` (含 `_Neo`, `_CCInfra`) | PAGER | AWS ALB P95/P99 高 | AWS ALB CloudWatch dashboard |
| `AwsAlbP95TargetGroupsLatencyHigh*` / `AwsAlbP99TargetGroupsLatencyHigh*` | HIGH | ALB target group 延迟（区分 ALB 自己 vs 后端） | 同上 |
| `AwsAlbP95RequestLatencyHigh` / `AwsAlbP95ResponseLatencyHigh` / 99 同 | HIGH | request vs response 分阶段延迟 | 同上 |
| `AwsAlbNon200` / `AwsAlb499` / `AwsAlb429` | PAGER / HIGH | ALB 错误码 | 同上 |
| `AwsAlbQpsZero` | PAGER | ALB QPS=0（很可能上游全挂） | 同上 |
| `AwsApiGatewayP95LatencyHigh*` / `AwsApiGatewayP99LatencyHigh*` | PAGER | API Gateway 延迟 | API Gateway dashboard |
| `AwsApiGatewayAuthorizerP95/P99LatencyHigh` | HIGH | Lambda authorizer 延迟 | 同上 |
| `AwsApiGatewayIntegrationP95/P99LatencyHigh*` | HIGH | API Gateway → backend integration 延迟 | 同上 |
| `AwsApiGatewayNon200` / `AwsApiGateway499` / `AwsApiGateway429` | PAGER / HIGH | API Gateway 错误 | 同上 |
| `AwsApiGatewayQpsZero` | PAGER | API Gateway QPS=0 | 同上 |
| `AwsLoadBalancerTargetGroupUnhealthy` | PAGER | NLB target group unhealthy | AWS NLB dashboard |
| `AWSLambdaDuration` / `AWSLambdaErrors` | HIGH | Lambda 时延 / 错误 | Lambda dashboard |
| `SubtenantP99LatencyHigh` | HIGH | 子租户级 P99 高 | RT SLA per-tenant |
| `IngressSLADropped` | HIGH | ingress SLA 跌破 | RT SLA |
| `K8sFPQpsHigh` / `K8sFPQpsZero` / `K8sFPErrorQpsHigh` | HIGH / PAGER | FP 通道 QPS 异常 | FP dashboard |
| `K8sFPUpdateDetectionNon200` | PAGER | FP detection / update endpoint 非 200 | FP dashboard |
| `K8sIngressNginxFPNon200` / `K8sIngressFPNginx400` | HIGH | FP ingress 错误 | FP / ingress nginx |
| `IngressRecordingRuleNoData` / `IngressSandboxRecordingRuleNoData` | HIGH | recording rule 断流（自监控） | VM rules health |
| `QpsZero` / `QpsZeroNasa` | PAGER | 关键 endpoint QPS=0 | 业务 ingress |

### B. Resource：CPU / Memory / Disk / Network（Pod 和 Node 两层）

| Rule | Severity | 含义 | FIRST dashboard |
|---|---|---|---|
| `K8sPodCpuUsageTooHigh` | PAGER | Pod CPU 使用率超阈值 | k8s pod dashboard |
| `K8sPodMemoryUsageTooHigh` | PAGER | Pod 内存超阈值 | k8s pod dashboard |
| `HighCpuUsageOfContainer` | PAGER | 容器 CPU 高（通用） | k8s container |
| `HighCpuUsageOfContainerInChi` / `HighCpuUsageOfContainerInChiUsWest2Prod` | PAGER | ClickHouse instance（CHI=ClickHouseInstaller）CPU 高 | ClickHouse dashboard |
| `K8sNodeMemoryUsageHigh` | HIGH | Node 内存 > 阈值 | node-exporter dashboard |
| `K8sNodeMemoryPressure` | HIGH | k8s 报 MemoryPressure condition | 同上 |
| `K8sNodeDiskPressure` | HIGH | k8s DiskPressure condition | node disk |
| `K8sNodeDiskUsageHigh` | PAGER | 某磁盘使用率高 | node disk |
| `K8sNodeLocalDiskUsageHigh` / `...WithMountpoint` | PAGER | local disk 高（区分 mountpoint） | node disk |
| `NodeLowRootDisk` / `NodeLowRootFile` | PAGER | root 分区 / inode 不够 | node-exporter |
| `NodeLowMntDisk` / `NodeLowMntFile` | PAGER | /mnt 分区 / inode 不够 | node-exporter |
| `NodeCPUUsage` | (no sev) | Node CPU > 90% 5min | node-exporter |
| `NodeMemoryUsage` | (no sev) | Node 内存高 | node-exporter |
| `NodeInputTraffic_1000Mbps` / `NodeOutputTraffic_1000Mbps` | HIGH | 网卡入/出 > 1000Mbps | node network |
| `NodeHighTCPConnection` | PAGER | 高 TCP CLOSE_WAIT | node network |
| `NodeReboot` (2 个变种：node-exporter & k8s) | HIGH | node 重启 | node lifecycle |
| `K8sNodeNotReady` | PAGER | Node NotReady > 7min | k8s nodes |
| `K8sNodeStatusUnknown` | HIGH | Node 状态 Unknown | 同上 |
| `K8sNodeNetworkUnavailable` | HIGH | Node 网络条件 false | 同上 |
| `K8sMasterPatchSucceed` | HIGH | master node 30 天没打 patch | infra patch dashboard |

### C. Pod health：restart / OOM / waiting / unable to start

| Rule | Severity | 含义 | FIRST dashboard |
|---|---|---|---|
| `K8sPodKilled` | HIGH | pod 被 kill | k8s pod state |
| `K8sPodRestartedTooManyTime` | HIGH | pod restart 次数多 | k8s pod state |
| `K8sPodInitContainerKilled` / `K8sPodInitContainerWaiting` / `K8sPodInitContainerRestartedTooManyTime` | HIGH | init container 三种异常 | k8s pod state |
| `K8sPodUnableToStart` | HIGH | pod 起不来 | k8s pod state + events |
| `KubernetesContainerOomKiller` | (in system.rules) | OOMKilled 事件 | k8s pod memory dashboard |
| `K8sDeploymentReplicasMismatch` | HIGH | deployment ready != desired | k8s deployments |
| `K8sJobFailed` / `K8sJobFailedApiserver` / `K8sJobFailedFp` | HIGH | k8s Job 失败 | k8s jobs |
| `K8sPersistentVolumeClaimLost` / `K8sPersistentVolumeClaimPending` | HIGH | PVC lost / pending | k8s PV/PVC |
| `K8sPersistentVolumeFailed` / `K8sPersistentVolumePending` / `K8sPersistentVolumePendingSparkJob` | HIGH | PV 状态异常 | 同上 |
| `K8sKafkaCassandraMysqlPodRestarted` | HIGH | 这三类有状态 pod 重启（单列出来比普通 pod 重要） | DB / Kafka dashboard |
| `K8sKafkaClusterFailover` | PAGER | Kafka 完成 failover | Kafka dashboard |
| `InstanceDown` | (system.rules) | 通用 instance down（10 个 firing 中） | 看 instance label 路由 |

### D. Database：MySQL / YugabyteDB / Redis / ClickHouse

**MySQL**
| Rule | Severity | 含义 | FIRST dashboard |
|---|---|---|---|
| `MysqlDown` | PAGER | mysql server down | MySQL dashboard |
| `MySQLExporterDown` | PAGER | exporter 自身 down | MySQL exporter health |
| `MysqlServiceDown` | PAGER | service-level down（kube_service） | MySQL service |
| `MySQLReplicationDown` | PAGER | 主从复制断 | MySQL replication |
| `MySQLReplicationDelay` | HIGH | 主从延迟过大 | 同上 |
| `HikariConnectionPendingHigh` | PAGER | 应用侧 Hikari 连接池 pending 高 | FP connection pool |
| `HikariConnectionTimeoutsDetected` | PAGER | Hikari 连接超时 | 同上 |
| `fp-mysql_exporter_status` group / `mysql_exporter_status` group | — | exporter 状态 | MySQL exporter |

**YugabyteDB**（注意 group 名 `yugabyetdb` 是 typo，alert 名是正确的 `Yugabyte*` / `yugabytedb*`）
| Rule | Severity | 含义 | FIRST dashboard |
|---|---|---|---|
| `yugabytedbExternalMasterNodeDown` | PAGER | external master node down | Yugabyte cluster overview |
| `yugabytedbExternalTserverNodeDown` | PAGER | external tserver down | 同上 |
| `yugabytedbExternalLocalDiskUsageHigh` | PAGER | 高 disk 使用率 | Yugabyte disk |
| `YugabyteDBNodeCPUUsage` | PAGER | node CPU 高 | Yugabyte node |
| `YugabyteDBNodeMemoryUsage` | PAGER | node mem 高 | Yugabyte node |
| `YugabyteDBSystemLoad10minHigh` | PAGER | 10min load 高 | Yugabyte node |

**ClickHouse**
| Rule | Severity | 含义 | FIRST dashboard |
|---|---|---|---|
| `ClickHouseFailedInsert` | PAGER | insert 失败 | ClickHouse dashboard |
| `ClickHouseFailedQuery` | PAGER | query 失败 | 同上 |

**Redis**
| Rule | Severity | 含义 | FIRST dashboard |
|---|---|---|---|
| `redis-cluster` group (3 rules) | — | redis cluster health | redis dashboard |

**Milvus**
| Rule | Severity | 含义 |
|---|---|---|
| `MilvusPodDown` / `MilvusPodNotReady` | HIGH | Milvus pod 状态 |
| `MilvusCpuUsageHigh` / `MilvusMemoryUsageHigh` | HIGH | 资源使用 |
| `MilvusMutationLatencyHigh` | HIGH | mutation 延迟（写） |

### E. Kafka

| Rule | Severity | 含义 |
|---|---|---|
| `Kafka_ExporterDown` | HIGH | kafka exporter down > 5min |
| `Kafka_ControllerDown` | HIGH | controller 缺失 |
| `Kafka_offlinepartition` | HIGH | offline partition > 0 |
| `Kafka_cm_consumergroup_lag_High` / `Kafka_fp_consumergroup_lag_High` / `Kafka_detection_consumergroup_lag_High` | HIGH | 多个 consumer group lag |
| `Kafka_fp_bucketstream_consumergroup_lag_High` / `Kafka_fp_al/extds/backfill_lag_High` | HIGH | 特定 stream lag |
| `Kafka_fp_consumergroup_lag_VelocityDetailHigh{_galileo,_onefinance,_tabapay,_wex}` | HIGH | per-client velocity detail lag |
| `KafkaEventExporterApplicationStderrErrors` | PAGER | kafka event exporter stderr 报错（当前 97 条 firing，最多） |
| `FPTopicsOffsetIncreaseZero` / `..._Dci_tuesday_to_saturday` / `..._Nasa` / `..._Syncbank` / `..._Fedex...` | HIGH | FP 关键 topic offset 不动（当前 469+ 条 firing，最多的告警类型） |
| `DappKafkaFailover` / `DappKafkaHeartbeat` | PAGER | DApp 侧 kafka failover/heartbeat |
| `connector` group (4 rules) | — | Kafka Connect / sink connector |

### F. Feature Platform / RT business logic

| Rule | Severity | 含义 |
|---|---|---|
| `FPAsyncExceptionCount>1000` / `>60` / `>1000ForEWS` | HIGH | FP async 异常 |
| `FPAsyncStderrCount>5` / `>100` / `>1000` / `*ForEWS` | HIGH | FP async stderr |
| `FPCronExceptionCount>60` / `>1000` / `>2000` / `*ForEWS` | HIGH | FP cron 异常 |
| `FPAsyncWriteKafkaFail` | HIGH | FP 写 Kafka 失败 |
| `FPStderrCount>5` | HIGH | FP 通用 stderr |
| `FPQpsZero` / `FPErrorQpsHigh` | HIGH | FP QPS 异常 |
| `FPBatchFlinkTaskFailCount>0` / `*ForEWS` | HIGH | batch Flink 任务失败 |
| `FPBatchJobInvalidFileInputCount>0` / `*ForEWS` | HIGH | UI batch 无效 input |
| `FP314aFuzzyMatchTaskFailCount>0` | HIGH | 314a 模糊匹配任务失败 |
| `FPRuleCountZero` | HIGH | rule_count_total=0（59 条 firing，明显是误报 / 业务调整后没清） |
| `RuleEngineHealth` | PAGER | 所有 RuleEngine 都不健康（最高危） |
| `RuleEngineSla` | PAGER | 所有 RuleEngine heartbeat 停（同上） |
| `RuleEngineHeartbeat` | HIGH | 某个 RuleEngine heartbeat 停 |
| `RuleEngineV3Heartbeat` | HIGH | V3 版本 heartbeat 停 |
| `RuleEngineV3InternalError` | PAGER | V3 internal error 激增 |
| `RuleEngineV3JVMMemoryUsage` | HIGH | V3 JVM 内存 > 90% |
| `rule_engine_1_internal_error` / `rule_engine_1_non_rt_error` | HIGH | 老版 rule_engine_1 错误 |
| `rule_engine_1_Reload` / `rule_engine_2_Reload` | HIGH | reload 失败 > 5h |
| `rule_engine_1_User_Load_Number` / `rule_engine_2_User_Load_Number` | MEDIUM | 加载用户数偏少 |
| `rule_engine_3_non_rt_error` | HIGH | rule_engine_3 错误 |
| `RTDetectionRateHigh` / `RTDetectionRateLow` | HIGH | 检测率偏高/偏低 |
| `RTAbsoluteDetectionRateHigh{Airasia,Bookingcom,Pinterest,Westernunion}` | HIGH | 客户级绝对检测率上限 |
| `RTAbsoluteDetectionRateLowPinterest` | HIGH | 客户级绝对检测率下限 |
| `RTFrontendResultGeneratorERRORLog` | (no sev) | RTFrontend error log spike |
| `SMLScoreFeatureHighPSI` | HIGH | SML feature PSI 漂移 |
| `BatchJobLongRun` / `BatchJobNoInputFiles` / `BatchJobNotRunAsScheduled` | HIGH | batch 任务 SLA |
| `ClientRawlogUploadTime` | (system.rules) | 客户上传 raw log 时间异常（12 条 firing） |
| `RawLogConverterNotStart` | — | raw log converter 没起来 |
| `UserstatsRTHeartbeat` / `UserstatsRTSla` | — | userstats RT 心跳/SLA |
| `user_stats_1_Reload` / `user_stats_no_reload` | — | userstats reload |
| `AllClientNginxPostbackFailure` group (5 rules) | — | 各客户 nginx postback 失败 |

### G. LiteLLM（新接的 LLM gateway）

| Rule | Severity | 含义 |
|---|---|---|
| `LiteLLMModelDown` | HIGH | 某模型 5min 不可达 |
| `LiteLLMExporterDown` | HIGH | exporter down |
| `LitellmDependencyDown` | HIGH | StatefulSet 副本不齐 |
| `LiteLLMHighAPILatencyP95` | HIGH | P95 > 60s |
| `LiteLLMHighTimeToFirstToken` | WARNING | TTFT P95 > 30s |
| `LiteLLMHighProxyErrorRate` | WARNING (5%) / `LiteLLMCriticalProxyErrorRate` HIGH (10%) | proxy 错误率 |
| `LiteLLMHighRateLimitErrorRate` WARNING / `LiteLLMCriticalRateLimitErrorRate` HIGH | model 429 比例 |
| `LiteLLMInputTokenSurge` / `LiteLLMOutputTokenSurge` | WARNING | token 速率 > 1.5x 历史 |
| `LiteLLMDeploymentCooledDown` | HIGH | 进入 cool-down 状态 |
| `LiteLLMAPIKeyBudgetLow` | HIGH | 单 key 用了 80% budget |
| `LiteLLMAPIKeyNoBudgetLimit` | WARNING | key 没配 budget |
| `LiteLLMDatabaseHighMemoryUsage` | PAGER | DB pod 内存高 |
| `LitellmPGSqlPodReschedule` | PAGER | PG pod 5min 内被 reschedule |

### H. Loki 自监控

| Rule | Severity | 含义 |
|---|---|---|
| `LokiPanics` | **CRITICAL** | Loki pod panic（全局唯一 CRITICAL） |
| `LokiUnavailability` | HIGH | Loki pod down > 5min |
| `LokiClusterNoNewLogs` | HIGH | 某 tenant 30min 无新 log（当前 3 条 firing） |
| `LokiDeploymentReplicasMismatch` / `LokiStatefulSetReplicasMismatch` | HIGH | 副本不齐 |
| `LokiHighRequestErrorRate` | HIGH | 请求错误率高 |
| `LokiIngesterFlushFailures` | HIGH | ingester chunk flush 失败 |

### I. Blackbox / SSL / 通用 probe

| Rule | Severity | 含义 |
|---|---|---|
| `Blackbox_Up_Check` | PAGER | blackbox probe job down |
| `Http_Connection` | HIGH | HTTP probe 连不上 |
| `Http_Status_Code` | HIGH | HTTP probe 非 200 |
| `SSLCertExpiringSoon` | HIGH | SSL 即将过期 |
| `PushgatewayDown` | HIGH | pushgateway down > 60min |

### J. 当前 firing TOP（来自 `mcp__victoriametrics__alerts state=firing`，共 932 条 firing）

| firing 数 | alertname | 解读 |
|---:|---|---|
| 469 | `FPTopicsOffsetIncreaseZero` | 主要来源。大量 topic offset 不动；要么真有 producer 死，要么是过期 topic 没清理 |
| 97 | `KafkaEventExporterApplicationStderrErrors` | exporter stderr 报错 |
| 59 | `FPRuleCountZero` | 大概率历史规则没清，看实际客户 |
| 32 | `QpsZero` | 关键 endpoint QPS=0 |
| 25 | `yugabytedbExternalLocalDiskUsageHigh` | 磁盘扩容信号 |
| 18 | `K8sPodKilled` | pod 反复被 kill |
| 16 | `FPTopicsOffsetIncreaseZeroDci_tuesday_to_saturday` | DCI 客户定时业务 |
| 15 | `MySQLReplicationDown` | 注意：可能是少量集群常年红，需要去 ack 而不是修 |
| 12 | `ClientRawlogUploadTime` | 客户上传时间异常 |
| 12 | `UserstatsRTHeartbeat` | userstats 心跳 |
| 11 | `FPTopicsOffsetIncreaseZeroNasa` | Nasa 客户 |
| 11 | `UserstatsRTSla` | userstats SLA |
| 10 | `InstanceDown` | 通用 instance down |
| 9 | `FPQpsZero` | FP 通道 QPS=0 |
| 7 | `QpsZeroNasa` | Nasa QPS=0 |
| 7 | `yugabytedbExternalMasterNodeDown` | yuga master |
| 7 | `yugabytedbExternalTserverNodeDown` | yuga tserver |
| 6 | `KubernetesContainerOomKiller` | OOMKilled |
| 6 | `alert_system_auto_gen_112_fedexato:_FPTopicsOffsetIncreaseZero_>=24H` | 自动生成的客户级 24h 持续告警 |
| 5 | `K8sDeploymentReplicasMismatch` | deployment 副本不齐 |
| 4 | `Http_Connection` | HTTP probe 失败 |
| 4 | `Kafka_fp_al/extds/backfill_lag_High` | backfill lag |
| 4 | `LiteLLMDatabaseHighMemoryUsage` | LiteLLM DB 内存 |
| 4 | `RawLogConverterNotStart` | converter 没起 |
| 4 | `RuleEngineHeartbeat` / `RuleEngineSla` | 注意 RuleEngineSla 是 PAGER 级 |
| 3 | `LokiClusterNoNewLogs` | Loki 断流 |
| 3 | `ApisixSLADropped` / 其他 |

> 观察：firing 集中度极高—— **TOP 3 alert 占了所有 firing 的 67%**。Oncall 主要"噪音税"在 `FPTopicsOffsetIncreaseZero` 一条上。

---

## 从 Slack alert 到 dashboard 的标准动作

DataVisor 没有 Grafana managed alerts，也没有 Grafana OnCall（`mcp__grafana__list_alert_groups` 这条工具针对的是 Grafana OnCall plugin，但 routing API 显示 receiver=`empty`，说明 OnCall plugin 没起作用）。所以"ack"是在 alertmanager / Slack 上完成的，不是在 Grafana UI 上。

### 标准 triage 5 步（Slack → vmui → dashboard → 决策）

**1. 在 Slack 上看 alert message，记下三个字段**

每条 vmalert 发出的 message 一般有：
- `alertname` —— 决定走哪个 dashboard
- `severity` —— PAGER 必须 5min 内响应，HIGH 30min
- `labels`（`kubernetes_cluster` / `kubernetes_namespace` / `client` / `topic` / `pod` 等）—— 进 dashboard 当 filter

**2. 点 alert message 里的 source URL**

vmalert 给的 `source` 字段 = 直接打开 vmui 并自动填好 alert 的 PromQL（前面 `FPTopicsOffsetIncreaseZero` 的例子就是这种 URL）。

- 当前值是 firing 阈值的多少倍？1.1x（边缘）还是 100x（严重）？
- 把 time range 拉到 6h / 24h —— 是新出问题还是常年红？

如果常年红 → 不是新事件，去看是否已经有 silence / 是否需要降 severity / 是否需要彻底 dedupe（典型例子：`MySQLReplicationDown` 当前 15 条，绝大概率是 N 个 cluster 常年 backup-only 状态）。

**3. 从 alertname 反查应对 dashboard**

按上面 A–I 表格定位。如果 alertname 含 `K8s*` → k8s 系列 dashboard；含 `Yuga*` → Yugabyte；含 `Kafka_*` → Kafka cluster；含 `Apisix*` / `Ingress*` / `RTIngress*` → RT SLA dashboard；含 `FP*` / `RuleEngine*` → FP / RuleEngine dashboard。

在 dashboard 上把 alert 里的 label（cluster / namespace / client）作为变量值套上去。

**4. 用 vmui 做 ad-hoc query 补足 dashboard 缺失的角度**

dashboard 一般是 "运营视图"，看不到的细节去 vmui 自由查。常用动作：

- 看某 metric 的 raw points：`my_metric{<labels from alert>}[10m]` (instant query)
- 看 5xx 分布按 status code 拆：`sum by (status_code) (rate(...[5m]))`
- 看 lag 增长趋势：`max_over_time(kafka_consumergroup_lag{...}[1h])`
- 找相邻指标：vmui Explore → Metrics 搜关键词

**5. Ack / silence / 升级**

vmalert 不像 Prometheus 自带 Alertmanager web UI 那么完整。在 DataVisor 这套：
- Slack 上 alert 一般有 react / button 给 ack（具体看 bot 配置）
- 真要 silence，去 alertmanager UI（部署在哪自己问 SRE，MCP 这里看不到）
- 升级 = 在 alert thread 里 @ on-call 对应 team（fp / infra / decision），team label 已经决定了应该找谁

### 常见反模式（这次数据里能直接看到）

1. **没设 severity / team 标签的 alert（91 条 / 79 条）** —— 路由不准，常被吃掉。新加 rule 时务必带这两个 label。
2. **per-client 把同一个模板分裂成几十个 rule**（`*Affirm`, `*Bookingcom`, `*Pinterest`, `*Tabapay`, `*CCInfra`, `*Neo`, `*ForEWS`...）—— 维护成本高。理想做法是 `client` 做 label，单条 rule。
3. **无 label filter 的 query 进 alert / dashboard**（top_queries 显示 `rate(kubernetes_monitoring_request_total_ingress_nginx[1m])` 平均 2.9s 跑全表）—— 写 PromQL 时永远加 `{kubernetes_cluster=~"..."}` 或 `{kubernetes_cluster_groups=~"..."}`，否则压死 VM。
4. **recording rule 看起来被搬空了**（`/config/recored.yaml` group 存在但 rules 数=0）—— 当前 0 条 recording rule。说明所有 `record:loki_*` / `record:kubernetes_monitoring_*` 是别处定义的，需要单独追。

---

## 附：MCP 数据盲点（这次拿不到的东西）

- **alertmanager receiver / route 配置**：`mcp__grafana__alerting_manage_routing(get_contact_points)` 返回 `[]`（Grafana 一侧没配）。VM 自己的 alertmanager 配置在 k8s ConfigMap，MCP 没暴露——要看 Slack channel 映射必须直接 `kubectl -n monitoring get cm <alertmanager-config> -o yaml`。
- **vmalert 实例自身的 `-notifier.url`**：同样不在 MCP 范围。
- **recording rule 全集**：rules API 里全空，说明 recording rule 跑在另一个 vmalert / 另一个 ConfigMap。
- **历史告警 timeline / Grafana OnCall shifts**：`list_oncall_*` 这次没拉（如果 oncall guide 需要排班数据，下一轮单独跑 `mcp__grafana__list_oncall_schedules`）。
