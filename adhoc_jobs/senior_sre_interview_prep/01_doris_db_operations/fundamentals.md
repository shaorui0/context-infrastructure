# 方向 01 基础回顾：从我的真实场景出发的 Q&A

> 组织方式不是教科书目录，是「面试官会怎么问 + 我从 Doris/ClickHouse 实战里怎么答」。
> 每条标了 **【一手】**（做过，能扛追问）/ **【半一手】**（碰过一次或只碰到某个面）/ **【理论】**（只读过，答的时候必须交代边界）。
> 数字后的 `(src: ...)` 是相对 workspace 根的路径。理论条目的作用是**答得体面并且不吹**，不是背下来当经验讲。

---

## 一、MPP / OLAP 架构：shared-nothing 与存算分离

### Q1. 存算分离和 shared-nothing 的本质区别是什么？【一手】

我不会从「计算和存储解耦」这句话开始答，因为那是结论不是机制。我的答法是三个可观测的差别：

**第一，扩容时数据动不动。** shared-nothing 里数据 locality 是性能的来源，所以加 shard 必须 reshard 加 rebalance，而 ClickHouse 不自动 rebalance，加 replica 很轻、加 shard 永远很重 `(src: contexts/survey_sessions/clickhouse_vs_doris_storage_compute_ai_load_survey_20260716.md §1.1)`。存算分离里 tablet 在 S3 上，扩容只是元数据里的归属重分配。我实测过：serving 池从 2 台扩到 4 台 backend，移动了零字节数据，tablet 归属 rebalance 成 131/128/128/125 `(src: adhoc_jobs/dynamic_resume_site/content/projects/p_elastic_compute.md)`。

**第二，状态去哪了。** 这是我认为最容易讲漏的一点：**存算分离不消除状态，它把状态集中到一层，而那一层从此不能偷工减料。** Doris shared-data 模式下是三个新的有状态失败域替换了「每台机器挂盘」：MetaService、FoundationDB、Recycler（S3 GC）`(src: adhoc_jobs/dynamic_resume_site/content/case_study_ch_to_doris.md)`。

**第三，成本曲线的形状。** shared-nothing 把计算耦合在本地盘上，空闲期和峰值期付同样的常驻硬件钱。Snowflake 自己的 Snowset 论文里，弹性用户的算力节点数在生命周期内可以变动两个数量级，而平均利用率很低（CPU 约 51%、内存约 19%），那就是「为峰值常驻」的浪费 `(src: contexts/survey_sessions/clickhouse_vs_doris_storage_compute_ai_load_survey_20260716.md §3.3)`。

### Q2. 存算分离是 Doris 的独门武器吗？【一手，且是我最喜欢的一个纠正】

不是，而且这个纠正很重要。2026 年存算分离已经是现代 OLAP 的**默认架构**：ClickHouse Cloud（SharedMergeTree）、StarRocks v3.0 shared-data、Snowflake、Databricks 全是。所以「要存算分离」这件事本身不构成「必须换 Doris」的理由，真正的分水岭是「开源自建 vs 云托管」`(src: contexts/survey_sessions/clickhouse_vs_doris_storage_compute_ai_load_survey_20260716.md 核心结论)`。

关键的一条硬事实是 SharedMergeTree **闭源、Cloud 独占、官方明确不进开源**，所以自建 ClickHouse 想要真正的无状态弹性算力是拿不到的，这是架构缺口不是配置缺口。Doris 的差异化要这样说：开源就自带存算分离（无云厂商锁定）+ MySQL 协议 + 多表 JOIN + 实时 UPSERT + 原生高并发点查。

### Q3. 存算分离的代价有哪些？【一手】

四条，都能给数字：

1. **冷查询延迟。** 官方自测三档：缓存部分命中比存算一体差约 10%，完全 miss 差约 35% `(src: contexts/survey_sessions/clickhouse_vs_doris_storage_compute_ai_load_survey_20260716.md §2.4)`。
2. **弹性是分钟级不是秒级。** 官方唯一的硬数字在 4.1，措辞是「百万级 tablet 分钟级扩缩容」，没有任何秒级 autoscaling 的承诺。我实测的链路是节点约 66 秒、backend 注册约 2 分钟，加起来约 3 到 4 分钟 `(src: adhoc_jobs/dynamic_resume_site/content/projects/p_elastic_compute.md)`。
3. **新增运维面。** decoupled 模式最少要 3 台跑 FoundationDB 加 MetaService 加 Recycler；对象存储有高延迟、QPS 与带宽上限、按请求计费三个固有问题。
4. **点查多一跳。** cloud 模式点查会多一次到 MetaService 的 RPC，高 QPS 下容易成瓶颈（官方旋钮是 `enable_snapshot_point_query=false`，牺牲可见性换性能）`(src: contexts/survey_sessions/clickhouse_vs_doris_storage_compute_ai_load_survey_20260716.md §2.5)`。

### Q4. AI 驱动的查询负载对数据库提了什么新要求？【一手（判断）+ 理论（业界数据）】

业界把 agent 驱动的分析称为十年来数据库负载模式的最大变迁：一个 prompt 炸裂成一串并发查询，分析负载开始长得像面向客户的生产流量，高并发、低延迟、交互式 `(src: contexts/survey_sessions/clickhouse_vs_doris_storage_compute_ai_load_survey_20260716.md §3.1)`。

我的判断是存算分离是必要条件但远不充分，真正的三个命门是：

1. **计费和唤醒粒度。** 冷启动超 1 分钟加 60 秒最小计费，一个 agent 每天打 1 万条 2 秒的短查询，最高 30 倍成本惩罚。Together AI 就是因为这个弃用了 ClickHouse Cloud（它的冷启动超一分钟，导致生产部署必须 24/7 常驻来躲冷启动，对不可预测的 agentic 流量等于全天付闲置算力钱）。
2. **多租户 blast radius 隔离。** 一个租户失控的 agent 查询不能拖垮整仓。
3. **对象存储冷查询延迟。**

我自己场景里的实测钩子是：一条 `SELECT * LIMIT 10` 墙钟排了 61 秒而 CPU 只用 60 毫秒，排在一个 bulk insert 后面 `(src: adhoc_jobs/dynamic_resume_site/content/case_study_ch_to_doris.md)`。讲 AI 动机必须立刻钉在这个实测案例上。

---

## 二、LSM 与 compaction 的通用模型

### Q5. 讲讲 LSM 的写放大与读放大，以及 compaction 在其中的角色。【一手】

我不背定义，我讲我踩过的那个债务模型：**compaction 的债欠的时候按段数计息，还的时候按 S3 round-trip 计费** `(src: adhoc_jobs/dynamic_resume_site/research/interview_story.md 复杂度锚点)`。

拆开说，LSM 写路径是内存 buffer 满了 flush 成一个不可变文件，所以写是顺序的、写放大来自后续的 merge；读路径要在多个重叠的文件里归并，所以读放大等于重叠文件数。compaction 就是用写放大换读放大。三个可观测量：

- **重叠度。** Doris 叫 compaction score，衡量 tablet 内互相重叠的 rowset 数量，约等于查询时的归并路数，高并发下健康值稳定在 50 左右 `(src: contexts/survey_sessions/ch_to_doris_migration_interview_arsenal_20260717.md §3.C)`。ClickHouse 的对应量是 part count。
- **拒写阈值。** Doris 的 `max_tablet_version_num` 默认 2000，超了报 -235；ClickHouse 有 `max_parts_in_total` 作为表级硬限，超了拒写 `(src: work-contexts/career/interview/interview-clickhouse-sre.md §3)`。这两个都是安全阀而不是调优参数。
- **单任务的成本。** 我这边最极端的一次是单个 compaction 任务要合并约 2,506 个 segment × 3,727 列，被内存 guard 在 43 GB 处 abort（task 级 abort 不是进程崩溃）`(src: adhoc_jobs/dynamic_resume_site/content/case_study_ch_to_doris.md)`。

### Q6. 写入被拒（-235 / parts too many）怎么处理？【一手】

因果链先说清：**-235 是果，compaction score 上涨是因。** 链条是导入频率大于 compaction 速度、rowset 和 version 持续堆积、撞到阈值就拒写。

治本是减少 rowset 生成速率：攒批、降导入频率、用 Group Commit。治标是调大版本上限（官方建议不超过 5000）并提高 compaction 并行（`max_cumu_compaction_threads` 默认 -1 即每盘 1 线程，显式调到 8 或 10；`compaction_task_num_per_disk`）。宽表上必须保持 `enable_vertical_compaction` 开启，它按列组合并，内存只有原来的十分之一 `(src: contexts/survey_sessions/ch_to_doris_migration_interview_arsenal_20260717.md §3.C)`。

-238（单 rowset 的 segment 数超 `max_segment_num_per_rowset`，默认 200）的根因常常绕回分桶：桶数太小或数据倾斜，所以**先查分桶再调 segment 上限**。

### Q7. 加机器能不能解决 compaction 积压？【一手，这是我最强的一个反直觉答案】

不一定，而且我有过一次明确证明不能的经历。判据是看**空转的 worker 有多少**：那次日志里是 632 次 no-op 唤醒对 9 次真实 merge，说明 worker 不缺、任务缺，而任务缺是因为单个 tablet 的 compaction 在机制上不能拆到多个节点。这是 concentration-bound 不是 resource-bound `(src: adhoc_jobs/dynamic_resume_site/content/case_study_ch_to_doris.md)`。

**在任何人花钱之前把这件事证明掉，是我认为 SRE 在容量问题上最该做的事。**

### Q8. 宽表在 compaction 上有什么特殊之处？【一手】

一个不在任何 sizing 文档里的量：稀疏宽表在内存写 buffer 和落盘 segment 之间有约 **46 倍的压缩衰减**。所以「调大 write buffer 到 1 GB」这个直觉解法直接被否掉，要产出 1 GB 的段需要 46 GB 的 memtable `(src: adhoc_jobs/dynamic_resume_site/research/interview_story.md)`。真正的修法只能走另外两个维度：bucket 数（控制单 tablet 体积到约 10 GB）和 column group 宽度（减少 S3 重扫次数）。

如果重做，我会把「宽表的 memtable-to-segment 压缩比」当成建表前必测的量，因为它同时决定 write buffer、bucket 数和 compaction 的可行性。

---

## 三、tablet / 分桶 / 分区设计

### Q9. 这张 50 亿行的表你分了多少桶？为什么？【一手】

先讲定容原则再讲取值，否则听起来像拍的。官方原则是单个 tablet 保持在 1 到 10 GB（3.0 放宽到 1 到 20 GB，Unique Key 表仍建议小于 10 GB，这个数字不同版本有冲突，主动点破更显专业）。两条硬约束：桶数最好是 BE 节点数的整数倍（数据均匀）、单分区一般不超过 128 `(src: contexts/survey_sessions/ch_to_doris_migration_interview_arsenal_20260717.md §3.C)`。

我的取值是 `AUTO PARTITION BY RANGE day` 加 `DISTRIBUTED BY HASH(user_id) BUCKETS 16`。关键论证是：**16 桶是针对单个日分区的，不是针对 50 亿行全表**，只要每个日分区落在 10 到 200 GB 这个区间，16 桶正好在官方建议的 10 到 20 桶范围里，而且是 BE 数的整数倍。用 `user_id` 做分桶键是因为它高基数、是查询常用的过滤和 join 键，能避免倾斜。

被追问「某天数据暴涨呢」：AUTO PARTITION 保证分区粒度可控，必要时配 AUTO BUCKET 让桶数按前 7 个分区的 EMA 自动调整。AUTO BUCKET（1.2.2 起）的算法是数据侧 `N = estimate_partition_size/5`（按 5:1 压缩比、每 GB 一桶），容量侧 `M = BE 数 × (盘容量/50GB) × 盘数`，最终取 `min(M, N, 128)`。

后来这张表的实际形状我也测过：20 个月分区、单分区 8 到 65 bucket（随数据量增长）、`estimate_partition_size=300G`、566 tablet、单 tablet 约 8.7 GB / 约 1,190 万行，落在推荐区间偏上 `(src: contexts/survey_sessions/doris_wide_table_point_query_optimization_survey_20260724.md §1)`。

### Q10. rowset 和 segment 是什么关系？【一手】

一次导入在每个 tablet 生成一个 rowset，一个 rowset 含 0 到 n 个 segment，每个 segment 是磁盘上一个有序文件，rowset 用版本区间标识 `(src: contexts/survey_sessions/ch_to_doris_migration_interview_arsenal_20260717.md §3.C)`。

和内存问题的联系：segment 数决定 compaction 的归并路数（S06 那次是每 tablet 约 2,500 段），而 segment 的大小由 memtable flush 阈值和压缩衰减共同决定。所以「导入太快」这个症状最终会以三种不同的错误码呈现（-235 版本数、-238 段数、compaction 内存 abort），根因是同一个。

### Q11. 分区剪枝和分桶剪枝各自的前提是什么？【一手，这是我踩过最贵的一课】

分桶剪枝需要**分桶键上的等值谓词**，分区剪枝需要**分区键上的谓词**。两个都不满足的时候，查询会扇出到全部分区的全部 tablet。

我的实测反例：那张宽表的分桶键是 `HASH(user_id)` 而点查谓词在 `eventId` 上，所以分桶剪不掉；查询没有 `proc_date` 谓词，所以分区也剪不掉。结果全部 20 个分区、566 个 tablet 都活到倒排探测层，`OLAP_SCAN: partitions = 20/20, tablets = 566/566`，零剪枝 `(src: contexts/survey_sessions/doris_wide_table_point_query_optimization_survey_20260724.md §2.1)`。

修法是在查询层注入 `proc_date`（eventId 里内嵌了毫秒时间戳，可以直接解析出来），扇出从 566 砍到约 28，窄查询 69 秒到 0.9 秒。**验证方式必须是 `EXPLAIN` 里确认 `partitions=1/20`、`tablets≈28/566`**，而且要用已知存在的 id 验证结果非空，因为 `AUTO PARTITION BY RANGE(date_trunc(...))` 有已知的裁剪正确性 bug（apache/doris#65606），可能默默剪出空集。

---

## 四、Bloom filter 与索引的作用边界

### Q12. 点查慢，加索引就好了吧？【一手，我最强的反直觉结论】

**索引修不了布局问题。** 我有两次独立的证据。

第一次在 Iceberg 布局上：点查跑 7 到 13 秒（对比 ClickHouse 的 21 毫秒），条件反射的修法是 bloom filter，它把扫描行数砍了 73% 而**墙钟一动不动**。原因是一个活跃用户的行散落在 2,044 个分区文件里，地板是文件打开次数不是扫描行数。修法是物理重聚簇，按用户键 hash 分布，结果 16 到 24 毫秒 `(src: adhoc_jobs/dynamic_resume_site/content/case_study_ch_to_doris.md)`。顺手还在字节层面（parquet 元数据检查）证明了两条常见 Iceberg writer 路径会**静默忽略**声明的 bloom filter 表属性。

第二次在 Doris 倒排索引上：暖查询缓存全命中、几乎零 S3，仍然 1.12 秒。时间全在跨 8 个 BE 扇出到 566 tablet / 6,689 segment 逐个打开倒排 searcher，主导项是 `InvertedIndexSearcherSearchInitTime` 31.8 毫秒和 7,081 次 `BlockInitSeek`。倒排索引把 5.47B 行过滤到 1 行，代价是每个 segment 开一次 searcher，因为**倒排索引是 per-segment 的局部索引，Doris 没有全局索引** `(src: contexts/survey_sessions/doris_wide_table_point_query_optimization_survey_20260724.md §2.1/§2.3)`。

所以我的判据是：先看成本的**单位**是什么。如果成本单位是「打开多少个东西」，那减少「扫多少行」的索引就是无效的。

### Q13. 前缀索引 / 排序键的边界？【一手】

只对 key 前缀有效。我这张表的排序键是 `DUPLICATE KEY(user_id, proc_date, eventId, time)`，`eventId` 是第 3 列，所以无法前缀 seek `(src: contexts/survey_sessions/doris_wide_table_point_query_optimization_survey_20260724.md §1 纠正 1)`。这是一个很好的例子说明「表设计没错但查询路径没被算进设计」：`user_id` 首列对主查询路径是对的，`eventId` 这条路径是后来长出来的。

### Q14. row store 什么时候值得上？【一手】

只治宽 `SELECT *` 的列读放大，不治扇出，而且有三个坑：

1. 部分行存 `row_store_columns` 官方明确**不支持 Duplicate 表**，只能全行存 `store_row_column=true`。
2. 代价是约 2 倍存储（4T 到约 8T）加写放大，还要配 `disable_storage_row_cache=false`。
3. 高并发点查的短路快路径**不会触发**（Duplicate 表加非 key 谓词），我的 profile 里 `RowsShortCircuitPredFiltered = 0` 已经证实了。

而窄查询本来就 `RowsRead=0`、成本全在倒排过滤，row store 对它完全无用。所以结论是：**能列出所需列加剪枝是最省的路，不必上 row store 也不必升级** `(src: contexts/survey_sessions/doris_wide_table_point_query_optimization_survey_20260724.md §3/§4.3)`。

### Q15. 列存的读放大模型是什么？【一手】

官方原话是每一列是一次独立的读，所以宽行点查付 N 倍 IO。我的实测分解把这一层和扇出层分开了：同一个 tablet、同样冷，3,727 列对 5 列的差是约 29.5 秒；而剪枝治不了这一层 `(src: contexts/survey_sessions/doris_wide_table_point_query_optimization_survey_20260724.md §2.2b)`。

还有一个潜在的第三层：老的 segment V2 格式把所有列的 `ColumnMetaPB` 塞在 footer 里，即使只查 2 列也要先读全部列的元数据才能开始扫描（官方 4.1 release 举的例子是 7,000 列 / 10,000 segment 时开 segment 要 65 秒、峰值 60 GB）。我们 3,727 列在这个敏感带里，但现场 profile 显示 `SegmentCreateColumnReadersTimer` 约 28 毫秒，占比不算爆炸，所以这不是我的主线。V3 是 4.1+ 特性。

---

## 五、副本与一致性

### Q16. Doris 存算分离下的副本模型是什么？【一手】

`ReplicationNum=1`。副本冗余由 S3 提供，BE 无状态，所以「副本健康」这个传统指标的重要性大幅下降，这本身就是从 ClickHouse 三副本迁过来的价值点之一 `(src: contexts/survey_sessions/ch_to_doris_migration_interview_arsenal_20260717.md §3.B)`。

但一致性问题换了位置，出现在两个地方：

1. **MoW 的 delete bitmap 锁。** 存算分离下 Merge-on-Write 表更新 delete bitmap 要抢分布式锁 `delete_bitmap_update_lock`，导入、compaction、schema change 竞争同一把锁，高并发导入下容易长等待。这正是我在约 17 亿行那次 livelock 事故里踩到的机制 `(src: contexts/survey_sessions/ch_to_doris_migration_interview_arsenal_20260717.md §3.D)`。
2. **版本默认值的破坏性变更。** Doris 4.0.6 把 cloud 模式的 `enable_strict_consistency_dml` **默认关掉**（为性能牺牲严格一致性），升级后依赖强一致 DML 的要手动开回 `(src: contexts/survey_sessions/clickhouse_vs_doris_storage_compute_ai_load_survey_20260716.md §2.3)`。这类「默认值变更」是升级审查里我最先查的一类。

### Q17. ClickHouse 的副本模型？【半一手】

shard 加 replica，shard 扩容量、replica 保可用，典型拓扑是 3 shard × 2 replica；分布式表（Distributed engine）做查询路由，底层是 ReplicatedMergeTree；复制依赖 ZooKeeper 或 ClickHouse Keeper 做元数据协调和 leader election，ZK 出问题等于 ClickHouse 出问题 `(src: work-contexts/career/interview/interview-clickhouse-sre.md §1)`。

**边界口径**：我是在既有拓扑上做运维、调优和事故定位，不是从零设计 shard/replica 布局；Keeper 层我能讲它挂了会怎样，但没做过 Keeper 自身的容量规划和迁移。观测点我熟：`system.replication_queue` 队列深度、`system.replicas` 的 `is_leader`/`queue_size`/`inserts_in_queue`、`ReplicatedMergeTreePartCount`。

### Q18. quorum 型组件的副本数怎么定？【半一手，被咬过】

`floor(N/2)+1`。3 个 FE 容忍 1 台故障，2 个 FE 容忍 0 台，也就是说从 1 台加到 2 台**不提高可用性反而降低**，因为多了一个故障源却没有多数派 `(src: work-contexts/career/interview/interview-6-starrocks-lakehouse.md §9)`。

我被这个咬过的具体形态是配置不一致：`electionNumber` 默认 3 而 `replicas=1`，BDB-JE 永远等不到多数派，pod 起来了、日志在刷、只是永远选不出 leader `(src: work-contexts/career/interview/interview-8-doris-query-routing-oom.md §Q6)`。所以副本数和 quorum 参数必须当一对约束一起管，最好由 operator 派生。

### Q19. quorum 系统的探针该怎么配？【一手】

反直觉但很重要：**liveness 必须保守，readiness 保持敏感。** readiness 只摘流量，liveness 会直接杀进程，而对基于 quorum 的有状态系统，每次误杀都会强制一轮重新选举，不稳定被层层放大。

我的实测案例是 KRaft 模式的 Kafka broker 轮流重启，每次重启都与 `Liveness probe failed` 事件对齐而不是任何自身崩溃信号，controller 频繁重选举。修法是把 liveness 调保守（`failureThreshold 99`、`periodSeconds 50`、`initialDelay 50s`），readiness 保持灵敏，重启计数立刻停止上涨 `(src: adhoc_jobs/dynamic_resume_site/content/integration/case_cards.json (kraft-liveness-restart-loop))`。

---

## 六、备份恢复与 RPO / RTO

### Q20. 你们的备份恢复方案是什么？RPO / RTO 多少？【半一手，边界必须先说】

**先划边界**：我做过的是一次跨集群 ClickHouse 恢复（EBS snapshot、PV/PVC 置换、重启、校验），恢复量级约 5.2B 行，但那是**一次性演练不是制度化的 DR**。RPO 是 snapshot 周期隐含的约 24 小时；我们没有做过定期恢复演练，也没有把 RTO 写成 SLO `(src: adhoc_jobs/dynamic_resume_site/content/integration/case_cards.json、adhoc_jobs/dynamic_resume_site/content_plan.md)`。⚠️ 待确认：实测 RTO 时长和 snapshot 实际周期我没有记录，所以不给数字。

我能讲深的是那次的判断：流程被数据拷贝服务标记为失败，眼看要触发破坏性重跑，我先独立验证数据面（TCP 9000 可连、`select 1` 成功），证明数据库其实已经恢复了，根因是自动化用 pod-ready 当就绪门槛、校验跑得太早。**控制面的「任务失败」不等于数据面的事实**，尤其当下一步是破坏性操作时，举证责任在「要重跑」那一边。

### Q21. 块级快照做数据库备份有什么结构性弱点？【一手（判断）】

三条：

1. **snapshot 是块级一致不是应用级一致。** 不停写或不 flush 的话恢复出来可能需要 crash recovery，恢复时长因此不可预测。
2. **粒度是整卷。** 做不了表级或分区级恢复，一个逻辑误删（DROP 错表）要恢复整个集群，代价和时间都不成比例。
3. **跨集群依赖 PV/PVC 置换。** 这是有状态编排里最容易出错的一步，而我们的自动化恰好就在这一步的判定上出了错。

所以正确的设计是把「逻辑误删」和「集群级损毁」当两类故障配不同手段。存算分离之后这个问题的形状会变，因为数据在 S3 上，恢复对象从块设备变成元数据，这是存算分离在 DR 上的真实红利。

### Q22. 存算分离的元数据怎么恢复？【中环，理论 + 拓扑一手】

链路比存算一体深一跳：FE BDB-JE → MetaService → FoundationDB。MetaService 和 FDB 都要 ≥3，Recycler ≥2。FDB 损坏要 `fdbrestore` from S3 `(src: work-contexts/career/interview/interview-8-doris-query-routing-oom.md §Q8)`。

**边界口径**：拓扑和失败域我能画清楚，但 `fdbrestore` 我没有实际演练过，小时级 RTO 是我的推断不是实测。这是我知道的最大一块没验证的地方，我会主动说。

### Q23. MySQL 的备份恢复方案有哪些？【理论】

逻辑备份 `mysqldump`/`mydumper` 适合小库、恢复慢；物理备份 `xtrabackup` 适合大库、支持增量和热备；PITR 是全量备份加 binlog 重放恢复到任意时间点 `(src: work-contexts/career/interview/interview-mysql-sre.md §1)`。

**边界口径**：这块我只有理论。我的一手 MySQL 经验全在 oncall 侧（connect timeout 跟着某台 worker 节点走的节点级 DNS 故障、上游 DDL 从 4 列改 2 列引发的 CDC 三连崩），不包括备份恢复。被问到我会直接说「MySQL 的备份恢复我按理论答，实际经验在 ClickHouse 和 Doris 上」。有一句我确实认同并且在自己场景里执行过的原则：**备份没验证过等于没有备份**，这也是为什么我把「定期恢复演练进日历」列成我下一步要补的制度。

---

## 七、慢查询定位方法论

### Q24. 一条查询变慢了，你的定位顺序是什么？【一手】

六步闭环，可以迁移到任何系统 `(src: work-contexts/career/interview/interview-6-starrocks-lakehouse.md §4)`：

1. **Profile 先行，排除法优于猜测。** `EXPLAIN ANALYZE` 一张图能同时排掉三个方向：我那次看到 CPU 只用 137 毫秒、99% 时间在 Scan-I/O，于是加 CPU、改 SQL、加内存全部出局。**没有 profile 的调参是迷信。**
2. **建立成本模型，找到系统的「计费单位」。** S3 按请求次数收延迟税不按数据量，所以头号敌人是小文件不是数据量。每个系统都有自己的计费单位（Kafka 是 partition、JVM 是 GC pause），找到它优化方向就唯一了。
3. **识别 bound 类型。** I/O 并发是藏延迟可以远超核数，计算并发受核数硬约束。我实测过 `connector_io_tasks` 从 4 到 32 有效（12.2 秒到 8.9 秒），而 dop=8 在 2 核上跑出 21 秒、比 dop=2 慢 4 倍。
4. **按真实 workload 分布权衡，不是把每个数字调到最大。** 唯一一个我实测到最优值随瓶颈类型反转的参数：冷查询 dop=4 快 2.2 倍，热查询 dop=2 反而快，最终按主场景（热缓存是生产主路径）定 dop=2。
5. **瓶颈守恒 + 边际收益止损。** Scan 从 8.5 秒砍到 145 毫秒之后 ScheduleTime 的 268 毫秒浮上来成最大头，那是框架固有开销，433 毫秒收工。
6. **固化成机制，否则会腐烂。** 小文件是写入侧持续产生的，一次性合并没用，nightly maintenance job 加 `iceberg_data_file_count < 10000` 的 SLO 加 page cache hit 告警，三件套才叫调优完成。**这是 SRE 和 DBA 调参的本质区别。**

### Q25. 集群 CPU 打满，怎么归因？【一手】

**绝不从单一信号源给 CPU 定根因。** 我那次的实例：一个 ClickHouse 节点跑到 92%（30 核用掉 27.6 核），只看 `system.merges` 得出的初判是 merge 欠债；用 `system.processes` 配合线程级 `top -H` 交叉验证后结论反转：3 条并发的 `SELECT *` 全表扫描（每条约 7 亿行）占约 67% CPU，merge 只占约 10% `(src: adhoc_jobs/dynamic_resume_site/content/integration/oncall_track_record.md §1)`。

沉淀成规则：**查询视图和线程视图必须互证。** 短期止血是压低 `max_threads` 并把 `SELECT *` 改成按需列，长期是给谓词列加 projection 或 bloom filter skip index 让点查不再扫 7 亿行。

### Q26. 慢查询的证据源有哪些？【一手】

分三层，而且**采集粒度必须匹配故障的时间尺度**：

- **引擎内部时间序列（最高分辨率）。** ClickHouse 的 `system.metric_log` 是 1 秒粒度，这是唯一能为亚秒级尖刺作证的东西。30 秒的 Prometheus 采集对 1 秒尖刺在构造上就不可见，这不是配置没调好而是采样定理 `(src: adhoc_jobs/dynamic_resume_site/content/incidents/w_zombie_oom.md)`。
- **查询级日志与 profile。** ClickHouse 的 `system.query_log`（耗时、扫描行数、内存峰值）和 `system.processes`；Doris 的 Query Profile 和 audit log（官方**没有**独立的慢查询 metric，要走 audit log 和 profile）`(src: contexts/survey_sessions/ch_to_doris_migration_interview_arsenal_20260717.md §3.B)`。
- **聚合指标。** 官方绝大多数 Doris 指标是 Counter 累积值，要按间隔采样算斜率才有意义；而且官方的告警阈值页面明确标着 TODO，也就是说阈值是社区经验不是官方推荐。

一个容易被忽略的坑：报错文本里的内存数字往往是「报错那一刻」不是「峰值那一刻」。我那次 `current RSS: 8.85 GiB` 读起来像慢性泄漏，实际是一秒内从 2 GiB 冲到 21.60 GiB 再回落。

### Q27. Doris 上线你监控哪些指标？【一手】

按四类讲，指标名以官方 Monitor Metrics 为准 `(src: contexts/survey_sessions/ch_to_doris_migration_interview_arsenal_20260717.md §3.B)`：

- **查询侧四大件**：`doris_fe_query_latency_ms{quantile="0.99"/"0.999"}`、`doris_fe_qps`、`doris_fe_query_err_rate`、`doris_fe_connection_total`（逼近 `max_connections` 要警觉）。
- **导入侧**：FE 看 `doris_fe_routine_load_lag` 和 `doris_fe_txn_status`（用 visible/aborted 比值算成功率）；BE 看 `doris_be_load_rows`/`load_bytes`、`load_channel_count`、`flush_thread_pool_queue_size`（flush 队列堆积说明落盘瓶颈）。
- **compaction 与 tablet 健康（最该讲深）**：集群级告警挂 `doris_fe_max_tablet_compaction_score`（FE 聚合所有 BE 的最大值），单机排障看 `doris_be_tablet_base_max_compaction_score` 和 `cumulative_max_compaction_score`；副本健康看 `doris_fe_tablet_status_count{type="unhealthy"}`，正常趋近 0。
- **存算分离特有**：file cache 命中率、对象存储 IO、compute node 资源。

一个诚实加分点：网上流传的「compaction score = -1 表示健康」这个说法我找不到官方出处，官方真正的健康信号是 score 低且平稳、tablet 版本数远低于 2000。自己没把握的口径就这样如实说。

### Q28. OLAP 的 SLO 怎么定？【中环，指标定义一手，制度落地是设计态】

四支柱，方法论锚 Google SRE Book `(src: contexts/survey_sessions/ch_to_doris_migration_interview_arsenal_20260717.md §3.B)`：

| SLI | 典型目标 | 要点 |
|---|---|---|
| 查询可用性 | 99.9%（单区）到 99.95%+（核心） | 成功查询/总查询，5XX/429/超时算失败 |
| 查询延迟 | P99 缓存命中 <10s，冷/miss <60s | 用分位不用均值，**分冷热**、分点查/聚合/大扫描 |
| 导入成功率 | 99%+ | 从 `LOADS` 表算 CANCELLED 比例 |
| 数据新鲜度 | P99 端到端 lag < 60s | OLTP 没有这一维，拆成采集 + Kafka lag + 计算 + 可见性 |

**延迟 SLO 必须分冷热**，因为存算分离下冷查询延迟是固有代价，定一个全局阈值一定是错的。阈值论证不能拍：我在 StarRocks 侧的 P95 <2s 是三条交叉验证得到的（MV 命中路径实测 p95 亚秒到 1.5s 留 buffer、ClickHouse baseline p95 约 1.5s 迁移不能让体感退化、人因研究 2 秒是 BI 交互注意力阈值）`(src: work-contexts/career/interview/interview-6-starrocks-lakehouse.md §5)`。

Error budget = 1 − SLO，99.9% 约等于每月 43 分钟，99.99% 约 4.3 分钟；告警用多窗口多燃烧率兼顾误报和检测延迟。

**边界口径**：指标定义和阈值论证是我做的；error budget policy 的分级动作（快烧 page 加扩容加限流保关键路径、慢烧冻结发布开复盘、耗尽硬冻结加对超预算 user/resource_group 配额降级）我是按设计写的，没有跑满一个季度形成制度。诚实的覆盖率账：51 个 infra SLI 里 64% 可用、32% 缺 instrumentation，用户视角覆盖不到 10%。**讲「我知道缺什么」比讲「我都有」更可信。**

一个可以主动带出的私货：t-digest 类的分位估计对 P100 这种极端长尾是失明的，定 P999 的时候要注意统计方法本身的误差。

---

## 八、连接池与准入控制

### Q29. 过载治理的第一性原理是什么？【一手】

两句话。第一句：**HPA 是分钟级的，OOM 是秒级的。** 所以弹性只能做余量、不能做主防线，主防线必须是进程内硬限加秒级熔断 `(src: work-contexts/career/interview/interview-8-doris-query-routing-oom.md §4 亮点 4)`。第二句：**路由是准入控制不是性能优化**，所以分类器不必完美，因为真正的保证在运行时那一层。

这两句合起来给出三层防御：L1 主动分类（plan 期准入路由）、L2 反应式硬限（workload group `overcommit=false` 超限即 reject、`max_query_time` 秒级熔断、query queue）、L3 恢复（reject 之后升级 heavy 池重试并 audit）。

### Q30. 为什么追 recall 而不是 accuracy？【一手】

因为两类错的代价不对称：**漏判 heavy 等于 OOM 等于安全事故，误判 light 只是浪费容量。** 所以我宁可让分类器悲观。想通这一点之后分类器可以「够用就停」，可以用规则不用 ML，可以接受阈值不完美 `(src: work-contexts/career/interview/interview-8-doris-query-routing-oom.md §4 亮点 1/3)`。

具体的悲观策略是：统计 degraded 或置信度 LOW 时默认强制 heavy，但一刀切悲观会把约一半的套件判废，所以配了 4 条窄逃生路径（limit-pushed tiny、all-tiny、degraded-zero-scan、tiny-peak）把真正小的捞回来 `(src: contexts/resume_highlights_doris_dcluster.md §4)`。

### Q31. 阈值怎么锚定，换个部署还能用吗？【一手】

两层资源分类学，不是一堆常数：**内存类阈值锚定被保护池子的预算（随部署缩放），CPU/IO 类是绝对量或每核量。** 因为「太占内存」是相对被保护的池子而言的，「太耗 CPU」是硬件属性，naive 的写法会把这两类混为一谈 `(src: contexts/resume_highlights_doris_dcluster.md §4)`。

一个生产反馈打磨出来的细节我很喜欢：内存决策原来是对整个 light 池的预算（约 16.5 GiB）判的，但查询实际进的是**一个并发 slot**（约 554 MB）。装得下半个池却撑爆单 slot 的查询被判 light，然后被 slot-kill 加重试，形成一个循环。改成按 `slot × safety` 判之后修掉了这个 loop，而结果物化的 volume 阈值故意保持锚定整池（那是另一种资源）。

更进一步，`routing_light_pool_cores > 0` 时行数类阈值按 `perCore × cores` 派生，所以**同一条查询会随池子大小改判**：60M 行扫描在 8 核池是 heavy、在 84 核池是 light。这就是路由策略与弹性容量的正确耦合，也是这两条工作线真正的咬合点，讲清它就从「实现者」升到「系统设计者」`(src: contexts/resume_highlights_doris_dcluster.md §1)`。

### Q32. 连接数和连接池怎么管？【理论 + 一个一手侧面】

理论部分：连接数逼近 `max_connections` 要告警，连接池的作用是把「无界的客户端并发」收敛成「有界的服务端并发」，设太大会导致内存和线程切换开销 `(src: work-contexts/career/interview/interview-mysql-sre.md §3、interview-clickhouse-sre.md §2)`。Doris 侧的对应指标是 `doris_fe_connection_total`。

我的一手经验是从另一个角度进的，是**空闲连接被中间层掐断**：一次故障里连接在空闲约 431 秒后被杀，而 MySQL 的 `wait_timeout` 是 8 小时，所以凶手不可能是数据库，是中间网络层的 TCP idle 超时；绕法是 30 秒 heartbeat 加 TCP keepalive `(src: adhoc_jobs/dynamic_resume_site/content/integration/case_cards.json (cdc-schema-snapshot-sign-null))`。**这个推理模式（用超时数量级反推是哪一层的常量）我用过好几次**，比如 P100 精确卡在 1.00 秒那次，1000ms 正好是限流 Lua 插件对 memcached 的读超时常量。

### Q33. 大租户把某一层打满，处置顺序是什么？【一手】

**先降级再限额扩容。** 因为扩容会把压力传导到还没有余量的那一层：数据库已经逼近饱和时加 serving 容量等于加大打向数据库的 QPS。降级是减少需求（λ），扩容是增加供给（μ），多层同时饱和时先降 λ 再抬 μ 才安全。

而且每个应急旋钮都要有明确上限加成文的回滚方案（我那次给消费线程池写的是 40 核心 / 80 上限），恢复限速要逐级（0 到 2 到 5 到 10）不能一把恢复，否则等于再造一次尖峰 `(src: adhoc_jobs/dynamic_resume_site/content/integration/case_cards.json (tenant-qps-joint-mitigation))`。

判断是不是单租户主导的手法是延迟分解：`request_time` 减 `upstream_response_time` 得到 waiting latency，waiting 占主导就是入口的连接或队列饱和而不是应用变慢。**先证明是 waiting latency 主导再去动应用层。**

---

## 九、DB HA 的通用谱系

### Q34. 数据库 HA 有哪几类，各自的边界在哪？【理论为主，Doris/SR 那一格一手】

我把它分成四类来答，并且明说哪一格是我的一手：

| 类别 | 机制 | 一致性 | 失败模式 | 我的位置 |
|---|---|---|---|---|
| 异步主从 | binlog/WAL 单向复制 | 最终，主挂可能丢数据 | 延迟、丢数据、脑裂 | 【理论】 |
| 半同步 | 至少一个副本确认才返回 | 折中 | 副本慢会拖主库；会静默降级为异步（要监控 `Rpl_semi_sync_master_no_tx`） | 【理论】 |
| 共识型 | Raft / Paxos / Group Replication | 强，多数派可写 | 多数派丢失即不可写；探针误杀放大不稳定 | 【半一手：BDB-JE、KRaft 都被咬过】 |
| 共享存储 + 无状态计算 | 数据在 S3/分布式存储，计算无状态 | 由存储层保证 | 状态集中层（MetaService/FDB）成为新单点 | 【一手】 |

`floor(N/2)+1` 这条规则适用于第三、第四类的元数据层，所以 3 个 FE 容忍 1 台、2 个 FE 容忍 0 台。

MySQL 的 failover 方案谱系（MHA、Orchestrator、ProxySQL/MySQL Router 在连接层做读写分离和故障转移、RDS/Aurora 由平台处理）我按理论答，并且会主动说「托管服务下 SRE 真正要关心的是 failover 时间和连接中断对应用的影响，而不是 failover 本身怎么实现」`(src: work-contexts/career/interview/interview-mysql-sre.md §1)`。

### Q35. 存算分离下 HA 要怎么设计？【一手】

**两层正交，缺一不可**：组件层（FE / MetaService / FoundationDB / Recycler，MS 和 FDB 都要 ≥3）× 业务层（compute group 做节点池级硬隔离、workload group 做 cgroup 级软隔离配额）`(src: work-contexts/career/interview/interview-8-doris-query-routing-oom.md §Q8)`。

这两层解决的是不同的问题：组件层解决「整个系统还在不在」，业务层解决「一个租户或一条查询能不能拖垮别人」。我认为后者在 SaaS 场景下更常被忽略，而它恰好是 AI 负载下最关键的那一条（blast radius）。

### Q36. 有状态系统在 K8s 上的典型 HA 陷阱？【一手，这是我最有货的一格】

四个，我都踩过，而且它们是同一个抽象的四个面貌：**每一层都有自己的「活着」定义，跨层复用会说谎，而且没有任何一层负责检查它们是否一致。**

1. **`SELECT 1` 探针被 FE 常量折叠**，从不下发到 backend，空的 compute group 也会被报告健康。真正的数据面探针是 `SHOW BACKENDS` 的 Alive 加一条触达存储的 canary 查询 `(src: adhoc_jobs/dynamic_resume_site/content/projects/p_elastic_compute.md)`。
2. **pod-ready 当就绪门槛**，导致恢复流程在 ClickHouse 真正起来之前就判失败，差点触发破坏性重跑 `(src: adhoc_jobs/dynamic_resume_site/content/integration/case_cards.json)`。
3. **用 IP 注册集群成员**：某 OLAP 引擎的 frontend 在 PVC 上的 BerkeleyDB 元数据里记了旧 pod IP，重启后 IP 变了、角色停在 UNKNOWN、查询端口不开、liveness 每 60 秒杀一次，累计 285 次重启，而 `kubectl logs` 完全为空（进程只写文件不写 stdout）。永久修法是 headless Service 加 FQDN 注册 `(src: adhoc_jobs/dynamic_resume_site/content/integration/case_cards.json (olap-fe-crashloop-ip-binding))`。
4. **operator 用 label 做 endpoints 门控**：pod 异常重启后 readiness label 没刷回来，Service selector 匹配 0 个 pod，`kubectl get endpoints` 返回 `<none>`，外部报 connection refused 而 pod 全是 Running `(src: adhoc_jobs/dynamic_resume_site/content/integration/case_cards.json (clickhouse-connection-refused))`。

我从这四个提炼出的机制性建议是：把「两个应该一致的信号不一致」做成指标（`endpoints == 0 而 pod ready > 0`、`pod RUNNING 但 SHOW BACKENDS 的 Alive 数不够`），这类检查不需要阈值也不会误报，是可观测性里性价比最高的一类。

### Q37. Kafka 的 HA 关键指标和取舍？【理论 + 两个一手侧面】

理论：under-replicated partitions 是最关键的健康指标，其次 ISR shrink/expand rate、active controller count（应该始终为 1）、request handler idle ratio；`min.insync.replicas=2` 配 `replication.factor=3` 加 `acks=all` 能在一个 broker 挂时不丢数据，但两个 broker 同时挂写入会阻塞 `(src: work-contexts/career/interview/interview-kafka-sre.md)`。容量维度上 Kafka 是磁盘密集型，replication 放大网络流量（RF=3 意味着写入流量 ×3），内存主要给 page cache 不给 heap。

**边界口径**：broker 层调优和容量规划我是理论。我的一手在两个侧面：一是 partition 数是复制吞吐的硬天花板（大租户 QPS 增长超过 topic 3 个 partition 能承载的 mirror 吞吐，而 MirrorMaker pod 完全健康，所以重启不解决任何问题），二是 quorum 系统的 liveness 必须保守（见 Q19）。还有一条 triage 的必答第一题：**分清是 consumer lag 还是 mirror lag**，两者的处置完全不同 `(src: adhoc_jobs/dynamic_resume_site/content/integration/oncall_track_record.md §4)`。

---

## 十、数据层的变更与升级（我的一手最多的一格）

### Q38. 数据库大版本升级你怎么做？【一手】

三条我实际执行过的原则：

1. **先查默认值变更，不是先查 SQL 兼容性。** Doris 4.0.6 把 cloud 模式的 `enable_strict_consistency_dml` 默认关掉，这是破坏性变更；4.0.5 修 file cache 并发崩溃、4.0.7 还在修数据丢失和挂起类问题。所以我的结论是**关键业务钉在 4.0.7 不用 4.0.0/4.0.1**，4.1 线先在非核心链路验证 `(src: contexts/survey_sessions/clickhouse_vs_doris_storage_compute_ai_load_survey_20260716.md §2.3)`。
2. **升级 runbook 末尾必须有审计步骤。** ClickHouse 升级改系统日志表 schema 时会把旧表改名加数字后缀、从不删除旧数据，多次升级之后累积出 1.21 TiB 的僵尸表，被一次一秒内完成的 merge 引爆 OOM。所以 runbook 末尾加一步「审计系统表是否出现新的带后缀残留」，因为**这是每次升级都会重新制造的隐患** `(src: adhoc_jobs/dynamic_resume_site/content/incidents/w_zombie_oom.md)`。
3. **一处确诊，全 fleet 扫。** 升级残留是横向缺陷，成因是升级动作本身，所以任何有相同升级史的集群一定有相同的残渣。那次一扫查出最严重集群 1.65 TiB、另一 region 的兄弟集群 250 GiB 且已经每天 3 次 OOM。

### Q39. 配置变更怎么保证生效且可回退？【一手】

三条：

1. **读回真实生效值，不是读回你提交的 manifest。** 我踩过 `confOverrides` 是整个 `fe.conf` 替换而不是 diff overlay 的坑，以为只改了一个参数、实际把其他参数改回了默认。Doris 侧的读回方式是 `SHOW FRONTEND CONFIG` `(src: work-contexts/career/interview/interview-8-doris-query-routing-oom.md §Q6)`。
2. **能热调的东西不要靠重启。** 我把约 21 个路由阈值全部声明为 `@ConfField(mutable=true)`，通过 `ADMIN SET FRONTEND CONFIG` 热调，默认值等于参考实现的常量。配合别的改进，「改一个调参值」从 44 分钟 rebuild 变成一条 SQL `(src: adhoc_jobs/dynamic_resume_site/content/projects/p_engine_routing.md)`。
3. **每个 feature 带 kill-switch 且默认 parity-safe**，verdict 暴露 `key_metrics` 可在线 debug `(src: contexts/resume_highlights_doris_dcluster.md §4)`。

### Q40. 不可逆的数据层操作怎么管？【一手】

先列清哪些是不可逆的，然后按「不做的代价是否持续且用户可见」决定当场做还是走评审。

我的实例对照：Kafka partition 扩容在 MirrorMaker lag 那次我**没做**，因为峰值过后 lag 会自然收敛，所以标成不可逆、要先评 key 分布和 rebalance 影响、走评审 `(src: adhoc_jobs/dynamic_resume_site/content/integration/oncall_track_record.md §4)`；在大租户 QPS 尖峰那次我**做了**，因为在场的是持续的用户可见影响 `(src: adhoc_jobs/dynamic_resume_site/content/integration/case_cards.json)`。

Doris 侧最典型的不可逆决策是**分布键**，它是唯一 ALTER 不了的东西，所以我在提交之前跑了同数据镜像键的两表 A/B、四次测量，再在 15M / 107M / 286M 三个检查点各复测一次 `(src: adhoc_jobs/dynamic_resume_site/content/case_study_ch_to_doris.md)`。

### Q41. 跨引擎迁移的人工成本主要在哪？【一手 + 理论】

四块 `(src: contexts/survey_sessions/clickhouse_vs_doris_storage_compute_ai_load_survey_20260716.md §4、ch_to_doris_migration_interview_arsenal_20260717.md)`：

1. **SQL 方言改写。** Doris SQL Convertor（2.1+，`set sql_dialect="clickhouse"`）实测约 98% 自动转换成功，剩下的是 `COUNTIF` → `SUM(CASE WHEN)`、`uniq()` → `APPROX_COUNT_DISTINCT()`、`quantile()` → `PERCENTILE_APPROX()`、子查询必须加别名这类。
2. **建表模型重设计。** 分区、分桶、Key 类型；动态分区需要预设历史分区数否则报 "No Partition"。
3. **上游写入程序适配**（Flink 等）。
4. **入库阶段的 compaction 和批量写调优。**

典型周期是改写加双跑约两周校验一致性然后切换。**诚实的信息空白**：我查过，找不到任何「从 Doris 迁回 ClickHouse」的具名生产案例，但这可能只是因为迁移案例的话语权集中在 VeloDB/Doris 侧，不能当成 Doris 一定不会被迁回的证据。这种「我知道我的信息源有立场偏差」的表述我认为比装作中立更可信。

---

## 附：外环补课清单（这份文件还没覆盖的，需要另外读）

1. **MySQL**：Group Replication / InnoDB Cluster 的实际运维、Orchestrator 的拓扑管理、`pt-online-schema-change` 与 `gh-ost` 的差别与风险、GTID 与位点管理。目前只有一份理论框架 `(src: work-contexts/career/interview/interview-mysql-sre.md)`。
2. **Kafka**：broker 层的容量模型（page cache 命中与磁盘吞吐的关系）、cruise-control 类的自动均衡、tiered storage。
3. **共识协议**：Raft 的 leader election、log replication、membership change 三段，以及它和 Paxos 的工程差别。目前是「被 BDB-JE 和 KRaft 咬过」的水平。
4. **PostgreSQL**：完全空白，如果目标岗位提到就要补 MVCC、vacuum、流复制、逻辑复制。
5. **数据库安全**：静态与传输加密、审计日志、行列级权限、SOC2/PCI 场景下的数据库控制项。九域雷达里安全与合规 40 分是最低分 `(src: adhoc_jobs/dynamic_resume_site/content_plan.md)`。
6. **Doris 优化器本身**：cost model 的公式、统计推导、优化规则重写。我做的是观测层，明确没改 CBO，被问深了要主动划界 `(src: contexts/resume_highlights_doris_dcluster.md §3 深度定级)`。
