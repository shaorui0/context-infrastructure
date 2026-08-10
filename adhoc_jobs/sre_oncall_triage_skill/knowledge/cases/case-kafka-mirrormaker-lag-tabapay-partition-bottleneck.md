---
metadata:
  kind: case
  status: stable
  summary: "MirrorMaker lag spike on tabapay topics in aws-uswest2-prod; tenant QPS increased while topic only had 3 partitions, mirror throughput hit per-partition ceiling. 短期 lag 自然收敛，长期需扩 partition。"
  tags: ["kafka", "mirrormaker", "lag", "partition", "tabapay", "tenant-qps"]
  first_action: "区分是消费者 lag 还是 mirrormaker lag → 看 mirrorlag-v2 dashboard"
  related:
    - ./case-kafka-lag-issues.md
---

# Kafka MirrorMaker Lag: tabapay tenant QPS spike vs partition count

## 症状

- Alertmanager: `aws-useast1-prod-b` kafka-exporter 报 consumer group `cg_velocity_detail_tabapay` 在多个 tabapay 相关 topic 上 lag 偏高
- 时间：2026-04-30 13:43 JST
- Grafana kafka-exporter dashboard 显示 lag 持续高位、缓慢下降

## 最有可能的是什么

按概率排序：
1. **下游消费者处理慢**（最常见，参见 case-kafka-lag-issues.md：ClickHouse parts 爆炸 → 写入 backpressure）
2. **MirrorMaker 复制瓶颈**（跨集群复制场景；本 case 命中）
3. **Broker / 网络问题**
4. **Consumer pod 资源不足 / OOM / 重启**

## 查什么

按这个顺序排：

1. **先区分 lag 类型** — 是消费者 lag 还是 mirrormaker lag？
   - kafka-exporter dashboard 看 consumer group
   - mirrorlag-v2 dashboard：`https://grafana-mgt.dv-api.com/d/-N7cUPZNk/mirrorlag-v2`
   - 如果 mirrormaker lag 也高 → 是复制端瓶颈，不是下游消费端
2. **MirrorMaker pod 资源**：CPU / memory / 重启 / error log
3. **Topic 流量与 partition 数**：源 cluster 的 tabapay topic QPS 和 partition count
4. **下游消费者健康**（如果第 1 步指向消费端）：参见 case-kafka-lag-issues.md

## 这次是什么

- mirrorlag-v2 显示 mirrormaker lag 在缓慢下降，没有 error → 不是 mirrormaker 崩溃
- MirrorMaker pod 资源使用正常（无 OOM / restart）
- 关键发现：**tabapay tenant QPS 上涨**
- 关键约束：**tabapay topic 只有 3 个 partition**
- 单 partition 复制吞吐有上限，QPS 上涨触顶 → mirrormaker 追不上 → 表现为 lag 高位 + 缓慢消化

## 结论是什么

- **根因**：tenant QPS 增长超过 tabapay topic 当前 partition 数（3）支撑的 mirror 复制吞吐上限
- 不是消费者侧 backpressure（区别于 case-kafka-lag-issues.md 的 ClickHouse parts 模式）
- 不是 mirrormaker 故障，是容量不足
- 短期 lag 在自然消化（生产端波峰过后能追上），但下次同样规模 QPS spike 仍会复发

## 要做什么行动

短期：
- 观察 lag 是否完全收敛（≥ 15-30 分钟稳定回基线）
- 不需要重启 mirrormaker（资源正常、无 error）

长期（follow-up）：
- **扩 tabapay topic partition 数**（owner: Zhenglan Hou + Caiwei Li）
  - partition 数与 mirrormaker 并发度直接相关
  - `#MANUAL`：扩 partition 是不可逆操作（不能缩回），需评估 key 分布与 consumer rebalance 影响
- 给 mirrormaker lag 配独立告警（区分消费者 lag vs 复制 lag）
- 给 tenant QPS 增长配 capacity review（tabapay 这种大客户跑量增长应触发 partition 评审）

## 经验沉淀（与已有 case 的 delta）

和 `case-kafka-lag-issues.md` 对比：
- 那个 case：lag 高 → 查下游 ClickHouse parts → 重启 async-consumer 恢复
- 本 case：lag 高 → **先要分清是 consumer lag 还是 mirrormaker lag**
- 新增决策分支：mirrormaker dashboard 是 kafka lag triage 必查的第二个面板
- 新增容量信号：partition 数 vs tenant QPS 是 mirrormaker 复制能力的硬约束

## Evidence

- Source thread: <https://datavisor.slack.com/archives/CJT8ZPRJL/p1777524187189579>
- MirrorMaker dashboard: `https://grafana-mgt.dv-api.com/d/-N7cUPZNk/mirrorlag-v2`
- Affected consumer group: `cg_velocity_detail_tabapay`
- Affected cluster: `aws-useast1-prod-b` → `aws-uswest2-prod`（mirror 方向）
- Topic partition count at incident: 3
