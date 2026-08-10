# META
id: w-inc-oom
kicker_en: INCIDENT
kicker_cn: 事故
title_en: Zombie System Tables: the Sub-Second OOM That 30-Second Monitoring Could Not See
title_cn: 僵尸系统表：30 秒采集看不见的亚秒级 OOM
sub_en: A Kafka consumer-lag alert that was really a terabyte of upgrade residue inside ClickHouse, detonated by a one-second background merge
sub_cn: 一条 Kafka 消费积压告警，真因是 ClickHouse 里超过 1 TiB 的升级残留，被一次一秒内完成的后台 merge 引爆

# EN

## Symptoms: the alert fires three systems away from the cause

The visible signal was Kafka consumer lag: a downstream ingestion consumer group's lag rising monotonically across multiple tenants at once, with no traffic spike to explain it. The consumer itself looked guilty and was not. Its inserts into ClickHouse were being rejected with `Code 241 MEMORY_LIMIT_EXCEEDED`; each failed batch sent the consumer into a 30-second sleep-and-rebalance retry loop, replaying the same records into the same failure. The distance between symptom and cause was the defining feature of this incident: the pager said Kafka, the root cause lived in ClickHouse's own system tables.

## Investigation: when the failure is faster than the scrape

Point-in-time inspection found nothing. By the time anyone exec'd into the pod, `SHOW PROCESSES` and `system.merges` were clean, and memory sat at its ~2 GiB baseline. The metrics platform, scraping at 30-second intervals, showed the same flat line. Even the error text misled: `current RSS: 8.85 GiB` reads like a slow leak. It was not. The case broke open on ClickHouse's internal 1-second-granularity metric log, which showed the true shape: baseline ~2 GiB, a single-second spike to the 21.60 GiB server ceiling, an OvercommitTracker kill, then straight back to baseline. A sub-second failure is invisible to a 30-second scrape by construction; only an in-engine time series could prove it.

With the spike established, the question became what allocated 20 GiB in one shot. The answer was upgrade residue. When a ClickHouse upgrade changes a system log table's schema, it renames the old table with a numeric suffix and creates a fresh one; it never drops the old data. This fleet had been upgraded repeatedly, and the corpses had accumulated: a renamed trace log at 1.21 TiB, a renamed profiling log at 308 GiB. These zombie tables receive no writes and have no readers, but their parts still participate in background merges. One such merge on a 1+ TiB zombie allocated its way from 2 GiB to the 21.60 GiB cap within a second, got killed, and took the concurrent insert queries down with it.

## Fix and prevention

The fix was deletion, with the right scope. Truncating the active system logs relieved forward pressure but touched nothing: TRUNCATE only acts on the current no-suffix tables. The zombies had to be dropped explicitly, past ClickHouse's 50 GB drop guard, via a per-query override; a 1+ TiB drop completed in 1-3 minutes with the server serving throughout. Because the tables had no writers and no readers, the operation was risk-free by construction. Consumer lag did not drain on its own; the consumer needed a restart to break the rebalance loop.

Prevention went three ways. First, configuration: TTLs on the internal log tables that ship without one, the highest-volume log disabled outright, and the server memory ceiling pinned explicitly. Second, process: the upgrade runbook now ends with an audit of system tables for new suffixed residue, because this is a latent defect every upgrade re-creates. Third, fleet scope: one confirmed diagnosis triggered an immediate cross-cluster audit, which found 1.65 TiB of zombies on the worst cluster and 250 GiB on a sibling in another region, already producing 3 OOMs per day and climbing the same curve.

## Lessons

- Monitoring granularity must match failure timescale. A 30-second scrape cannot testify about a one-second spike; for engines that keep 1-second internal metrics, that log is the primary evidence source after any OOM.
- Raising the pod's memory limit was the obvious knob and the wrong one: it delays an unbounded-growth failure, it does not stop it.
- Upgrade residue is a horizontal defect. If an upgrade left debris on one cluster, it left debris on every cluster with the same history: diagnose once, then audit the fleet.

# CN

## 症状：告警与真因隔着三个系统

可见信号是 Kafka 消费积压：下游摄取服务的 consumer group 在多个租户上同时出现单调上涨的 lag，却没有任何流量尖峰可以解释。消费者看起来像肇事者，实际是受害者：它向 ClickHouse 的写入被 `Code 241 MEMORY_LIMIT_EXCEEDED` 拒绝，每个失败批次触发 30 秒 sleep 加 rebalance 的重试循环，同一批数据反复撞上同一个失败。表象与真因之间的距离是这次事故的核心特征：告警指向 Kafka，根因在 ClickHouse 自己的系统表里。

## 调查：故障比采集更快时怎么办

即时检查一无所获。等人 exec 进 pod 时，`SHOW PROCESSES` 和 `system.merges` 都是干净的，内存停在约 2 GiB 的基线。监控平台 30 秒一次的采集同样是一条平线。连报错文本都在误导：`current RSS: 8.85 GiB` 读起来像慢性泄漏，其实不是。破案靠的是 ClickHouse 内部 1 秒粒度的 metric log，它还原了真实形状：基线约 2 GiB，一秒之内冲到 21.60 GiB 的服务上限，被 OvercommitTracker 杀掉，随即回落基线。亚秒级故障对 30 秒采集在构造上就是不可见的，只有引擎内部的时间序列能作证。

尖刺坐实之后，问题变成：什么东西一次性分配了 20 GiB。答案是升级残留。ClickHouse 升级改变系统日志表 schema 时，会把旧表改名加数字后缀、另建新表，从不删除旧数据。这个集群群经历过多次升级，尸体越积越多：一张改名后的 trace 日志表 1.21 TiB，一张改名后的 profiling 日志表 308 GiB。这些僵尸表没有写入者也没有读取者，但它们的 parts 仍会参与后台 merge。一次针对 1 TiB 级僵尸表的 merge 在一秒内把内存从 2 GiB 顶到 21.60 GiB 上限，自己被杀，同时把并发的写入查询一起击落。

## 修复与预防

修复是删除，但要删对范围。TRUNCATE 活跃系统日志表只能缓解增量压力，对僵尸表毫无作用：TRUNCATE 只作用于当前无后缀的表。僵尸表必须显式 DROP，用单查询参数绕过 ClickHouse 的 50 GB 删表保护；1 TiB 级的 DROP 在 1-3 分钟内完成，期间服务不中断。因为这些表既无写入者也无读取者，操作在构造上零风险。消费积压不会自愈：需要重启消费者才能打破 rebalance 循环。

预防分三路。配置层：给默认无 TTL 的内部日志表加 TTL，把数据量最大的日志直接关闭，显式钉死服务器内存上限。流程层：升级 runbook 末尾新增一步，审计系统表中是否出现新的带后缀残留，因为每次升级都会重新制造这个隐患。舰队层：一处确诊立即触发跨集群审计，最严重的集群查出 1.65 TiB 僵尸表，另一 region 的同类集群查出 250 GiB，已经每天产生 3 次 OOM，正沿着同一条曲线爬升。

## 教训

- 监控采集粒度必须匹配故障时间尺度。30 秒采集无法为 1 秒尖刺作证；对内置 1 秒粒度指标的引擎，OOM 之后它的内部日志就是第一证据源。
- 调大 pod 内存上限是最顺手也最错误的旋钮：它只能推迟无界增长型故障，不能阻止。
- 升级残留是横向缺陷。一个集群有残渣，所有同升级史的集群都有：一处确诊，全舰队扫描。

# SOURCES
- agents/sre_oncall_triage_skill/knowledge/cases/case-clickhouse-system-log-zombie-tables-oom.md
