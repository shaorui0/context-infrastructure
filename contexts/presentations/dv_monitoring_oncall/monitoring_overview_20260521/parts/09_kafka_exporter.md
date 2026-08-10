# Kafka Exporter for all (`cluster_kafkfa_exporter`)

**URL**: https://grafana-mgt.dv-api.com/d/cluster_kafkfa_exporter/kafka-exporter-for-all
**Folder**: General · **Tag**: `Kafka` · **Owner (last edit)**: runzi.yang · **Updated**: 2026-05-19
**Data source**: VictoriaMetrics single (`vms-victoria-metrics-single-server`), 来源指标全部由 `kafka-exporter` pod (e.g. `kafka3-exporter-*`) 暴露，被 `job=kubernetes-pods` 抓取。

UID 里的 `kafkfa` 是历史拼写错误，URL/链接都得保留这个拼写。

---

## 与 MirrorLag v2 的分工

| 维度 | MirrorLag v2 | Kafka Exporter for all（本 dashboard） |
| --- | --- | --- |
| 监控对象 | 仅 MirrorMaker（跨集群复制 lag） | **任意 consumer group** 的 lag |
| 指标来源 | mirror-maker JMX / 复制 offset diff | `kafka_exporter` pod 拉 Kafka admin API |
| 视角 | 源 topic vs 镜像 topic 偏移差 | 每个 consumergroup × topic × partition 的 lag |
| 适用告警 | `MirrorLag_*` 系列 | `Kafka_*_consumergroup_lag_High`（per-customer 多个变种，见 parts/05） |
| 局限 | 只看复制链路 | 看不到 MM2 内部复制健康，只能看 MM2 作为 consumer 的 lag |

**一句话**：MirrorLag v2 答「复制有没有跟上」，Kafka Exporter 答「某 consumer group 有没有跟上」。

---

## 变量

按层级 cascading：`PromDs → job → cluster → namespace → pod → topic → consumergroup`。

| 变量 | 作用 | 取值查询 | 备注 |
| --- | --- | --- | --- |
| `PromDs` | Prometheus 数据源 | datasource(regex=`vms-victoria-metrics-single-server`) | 默认 `prometheus-services` |
| `job` | 抓取 job | `label_values(kafka_consumergroup_current_offset, job)` | 实际只有 `kubernetes-pods` |
| `cluster` | DV K8s 集群 | `label_values(... , kubernetes_cluster)` | 例 `aws-uswest2-prod-b` |
| `namespace` | 命名空间 | `label_values(... , kubernetes_namespace)` | 例 `prod` |
| `pod` | exporter pod 名（= **绑定一个 Kafka 集群**） | `label_values(kafka_brokers{...}, kubernetes_pod_name)` | 例 `kafka3-exporter-788587b949-7bwxg`；**关键变量**，一个 exporter pod 对应一个 Kafka 集群 |
| `topic` | topic（multi + All） | `label_values(kafka_topic_partition_current_offset{pod=...,topic!='__consumer_offsets',topic!='--kafka'}, topic)` | 排除内部 topic |
| `consumergroup` | 消费组（单选） | `label_values(kafka_consumergroup_current_offset{pod=...,topic=~$topic}, consumergroup)` | 在过滤后的 topic 集合内列出 |

注意 panel 查询里所有过滤都收敛到 `kubernetes_pod_name="$pod"`，**没有用 cluster/namespace 直接过滤指标**，因为 exporter pod 名已经唯一定位了 Kafka 集群。换 Kafka 集群 = 换 `pod` 变量。

---

## 关键 panel + 查询

6 个 panel，左右双栏（生产侧 vs 消费侧）+ 底部一行（绝对 offset / partition 分布）。

### 1. Message in per second（id=14, 左上）
```
sum(rate(kafka_topic_partition_current_offset{
  kubernetes_pod_name="$pod", topic=~"$topic", topic!="__consumer_offsets"
}[1m])) by (topic)
```
**含义**：topic 写入速率（producer 侧 throughput）。判断 producer 还在不在 pump。

### 2. Lag by Consumer Group（id=12, 右上）★核心 panel
```
kafka_consumergroup_lag{
  kubernetes_pod_name="$pod", topic=~"$topic",
  consumergroup=~"$consumergroup", consumergroup!~".*console-consumer.*"
}
legendFormat: {{consumergroup}} (topic: {{topic}} partition: {{partition}})
```
**含义**：每个 consumergroup × topic × **partition** 的瞬时 lag（messages）。排除 `console-consumer.*`（人手 kafka-console-consumer 调试用，乱噪音）。
**读法**：legend 一行一个 partition，按 Last 降序排，第一行就是 lag 最大的 (group, topic, partition)。

### 3. Message in per minute（id=16, 左中）
```
sum(delta(kafka_topic_partition_current_offset{
  kubernetes_pod_name="$pod", topic=~"$topic", topic!="__consumer_offsets"
}[5m])/5) by (topic)
```
**含义**：5min delta / 5 = 每分钟写入条数（topic 维度）。和 panel 1 是同一信息的不同尺度，更适合看趋势。

### 4. Message consume per minute（id=18, 右中）
```
sum(delta(kafka_consumergroup_current_offset{
  kubernetes_pod_name="$pod", topic=~"$topic",
  consumergroup!~".*console-consumer.*", consumergroup=~"$consumergroup"
}[5m])/5) by (consumergroup, topic)
```
**含义**：consumer 每分钟实际推进的 offset 数。与 panel 3 (生产) 对比就是「追不追得上」。

### 5. Topic Current Offset（id=20, 左下）
```
kafka_topic_partition_current_offset{kubernetes_pod_name="$pod", topic="$topic"}
legendFormat: {{topic}}-{{partition}}
```
**含义**：每个 partition 的绝对 offset，判断是否单调上涨（producer 活着）。

### 6. Partitions per Topic（id=8, 右下, bargauge）
```
sum by(topic) (kafka_topic_partitions{kubernetes_pod_name="$pod", topic=~"$topic"})
```
**含义**：每个 topic 的 partition 数，定位「lag 是只在某些 partition 还是全打」要先知道总 partition 数。

> 没有专门的 broker 数 panel，但 `kafka_brokers` 被用在 `$pod` 的 query 中。要看 broker 数直接在 Explore 里 `kafka_brokers{kubernetes_pod_name="$pod"}`。

---

## consumergroup lag 定位流程（4 步）

**前置**：从告警拿到 `consumergroup`、`topic`（如果 alert 带），或从 customer 名反推 group。

### Step 1 — 进 dashboard 选好 scope
- `cluster` / `namespace` 选 prod-b 之类。
- `pod` 选对应 Kafka 集群的 `kafka*-exporter-*`（同一 namespace 通常多个 Kafka 集群 = 多个 exporter pod，别选错）。
- `topic` = All，`consumergroup` 选告警里的 group。

### Step 2 — 看 Lag by Consumer Group（panel 2）判断「growing / stuck / spike」
- **斜率 > 0 持续涨** → 消费跟不上生产，进 Step 3。
- **平的高位** → 消费完全卡住（consumer 挂了 / rebalance / 死锁），跳到 Step 4 partition 分析。
- **尖峰回落** → producer burst，consumer 正在追，观察是否收敛。

### Step 3 — 对比生产 vs 消费速率（panel 3 vs panel 4）
- panel 3「Message in / min」(topic 维) 和 panel 4「Message consume / min」(group×topic 维) 同时间段对比：
  - 生产 > 消费 → 真 backlog，要扩 consumer 或调优处理逻辑。
  - 生产 = 0 但 lag 不掉 → consumer 停了（看 panel 4 是否归零）。
  - 生产正常、消费也正常但 lag 涨 → 长期容量不够（持续 producer > consumer）。

### Step 4 — Partition 级别下钻（panel 2 的 legend + panel 5）
- panel 2 按 partition 一行一条 → 看是**所有 partition 同涨**（容量问题/全局卡死）还是**单个 partition 涨**（该 partition 的 consumer instance 挂 / 数据倾斜 / hot key）。
- panel 5 `Topic Current Offset` 单个 partition 是不是还在涨 → 确认 producer 仍在写到该 partition。
- panel 6 看 topic 有多少 partition，估算 consumer 并发上限。

### Step 5（可选）— 跳到上下游
- consumer pod 健康 → 切到 namespace dashboard / 该服务的 application dashboard。
- broker 侧异常 → MirrorLag v2 / Kafka cluster 自身 dashboard。

---

## 何时该看这里 vs MirrorLag v2

**先看 Kafka Exporter for all**：
- 告警名是 `Kafka_*_consumergroup_lag_High`（包括 per-customer 变种）。
- 客户/内部服务反馈「数据延迟」「队列堆积」但不涉及跨集群复制。
- 业务消费侧（feature, velocity, scoring 等 consumer group）lag。

**先看 MirrorLag v2**：
- 告警名是 `MirrorLag_*` / mirror-maker 相关。
- 现象是「源集群有数据但目标集群没看到」「跨 region 复制延迟」。
- 涉及 `mirror-maker` / MM2 consumer group。

**两个都要看的场景**：
- MM2 作为 consumer 也会出现在 Kafka Exporter for all 的 `consumergroup` 列表里（`consumergroup` 名通常带 `mirror-maker` 前缀）。当 MirrorLag v2 报警时，可以在本 dashboard 看 MM2 作为 consumer 对源 topic 的 lag、生产速率、追赶速度，比 MirrorLag v2 的纯 offset diff 更直观。
- 反过来，本 dashboard 看到某非 MM2 group lag 涨，但同 topic 的 MM2 也 lag → 大概率 broker / topic 容量问题，要联看 MirrorLag v2 排除复制层。

---

## 已知坑

- **UID 拼写**：`cluster_kafkfa_exporter`（`kafkfa` 非 `kafka`），别手敲错。
- **`pod` 变量绑定 Kafka 集群**：一个 namespace 多个 Kafka 集群时，要确认选对了 exporter pod，否则看到的是别人家的 topic。
- **`__consumer_offsets` / `--kafka` 已过滤**：变量层就排除了，panel 也再排一次，看不到这俩内部 topic 是预期行为。
- **`console-consumer.*` 被过滤**：临时 `kafka-console-consumer` 调试不会污染 lag panel，但如果你自己在 debug 用 console-consumer 想看 lag，本 dashboard 看不到。
- **legend 限宽 480**：partition 多时 legend 会很长，用「Sort by Last desc」抓 top N。
- **rate() over `kafka_topic_partition_current_offset`**：这是 counter 累加（kafka offset 单调增），`rate` 语义合理；但 partition 重建/topic 重置会有断点，看到瞬时跌零 + 重涨别误判为消费完成。
