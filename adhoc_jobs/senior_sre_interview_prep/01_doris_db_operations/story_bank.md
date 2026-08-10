# 方向 01 战 story 库：Doris / DB 运维 / HA / 存算分离 / 数据层监控

> 15 个故事，每个带 5 层追问防线。数字后的 `(src: ...)` 是相对 workspace 根的路径。
> 使用方式：面试前扫 headline 和「适用题型」两栏选牌；被追问时按 L1→L5 逐层放。
> 纪律：开场不用 S09（对账）、不用 S12-S15 那批 oncall 清单，它们是弹药不是开场。归属边界那一栏被问到才主动说，但**绝不撒谎**。

**故事索引**

| 编号 | 故事 | 一句话 | 主战场 |
|---|---|---|---|
| S01 | CH→Doris 存算分离重构主线 | 我做的不是迁移，是把这一层重建在存算分离上 | 架构设计 / 选型判断 |
| S02 | 3,700 列宽表迁移的四个内存断点 + 1.7B livelock | 迁移不是搬运问题，是内存工程问题 | 大规模数据工程 |
| S03 | 74.7M 行 query_log 推翻团队的设计假设 | 从 benchmark 设计会优化错误的负载 | 数据驱动决策 |
| S04 | 引擎级查询路由 ESTIMATE / ROUTE PLAN | signal problem 不是 rule problem，所以我改了引擎 | 引擎深度 / 准入控制 |
| S05 | dcluster 弹性 CN 控制面 0→N→0 | 平台拥有状态时，自建工具应该缩小到一个字段 | 控制面设计 / 弹性 |
| S06 | compaction 死亡螺旋（score ~2,500） | 三因连乘，且加机器无效因为单 tablet 不可拆 | 事故根因 / 引擎机制 |
| S07 | 孤儿 tablet 卡死（score ~4,504） | 一条推理链会被带偏，三条独立证据链才是判决 | 调查方法论 |
| S08 | 宽表点查：扇出是地板不是 S3 | 暖查询缓存全命中仍要 1.12 秒，证明地板与 S3 无关 | 性能工程 / 反直觉 |
| S09 | 99.945% 对账与验证方法本身的工程化 | 对账方法自己会打挂集群，所以要重新设计 | 正确性工程 |
| S10 | EBS snapshot 跨集群恢复 ~5.2B 行 | 控制面说失败不等于数据面的事实 | DR / 备份恢复 |
| S11 | Iceberg + StarRocks lakehouse 与 49× 性能工程 | 找到系统的计费单位，优化方向就唯一了 | 湖仓 / 调优方法论 |
| S12 | ClickHouse 僵尸系统表的亚秒级 OOM | 30 秒采集无法为 1 秒尖刺作证 | 监控粒度 / 横向缺陷 |
| S13 | Doris FE crashloop：Xmx 8G vs cgroup 4Gi | 症状链不是因果链，exit 137 且无 JVM 栈是关键分叉 | RCA / K8s + JVM |
| S14 | ClickHouse connection refused 八跳定位 | refused 意味着某一跳没人监听，停在第一个失败的跳 | 逐层定位 |
| S15 | 大租户 QPS 尖峰联合止血 | 先降级再限额扩容，数据库没余量时加 serving 是把事故推下悬崖 | 过载治理 |

---

## S01. CH→Doris 存算分离重构主线

**Headline（一句话，先给结论）**：我们的反欺诈事件层要同时服务毫秒级点查和越来越多 AI agent 驱动的不可预测 ad-hoc 分析，旧的 ClickHouse shared-nothing 层对后者既不能隔离也不能弹性伸缩，所以我做的不是一次迁移，而是把这一层重建在存算分离上，并且把查询路由做进了引擎本身。

**适用题型**：讲一个你主导的最复杂项目 / 技术选型怎么做 / 架构设计题（同时服务点查和分析的数据层）/ 你怎么说服别人 / 存算分离的取舍。

**情境**：事件层是一张约 3,700 列的宽表，约 52 亿行、约 4 TiB 源数据 `(src: adhoc_jobs/dynamic_resume_site/content/case_study_ch_to_doris.md)`。业务上有两类冲突负载：serving 路径的毫秒级点查，和越来越多由 AI agent 面向产品功能生成的 ad-hoc 分析，而不是人类分析师手写的查询。ClickHouse 当时在我们自己的一手 benchmark 上打平表扫描还快 1.2 到 2.5 倍，所以「新引擎更快」这个故事根本不成立，我从一开始就把它排除掉了。

**动作**：我把决策论证钉在四个结构性妥协上，而不是性能上：

1. 没有 workload 隔离。一条重查询饿死共享节点，我实测过一条 `SELECT * LIMIT 10` 墙钟等了 61 秒、CPU 只用 60 毫秒，排在一个 bulk insert 后面。
2. 算力刚性常驻。shared-nothing 把计算耦合在本地盘上，空闲期和重查询突发期付一样的常驻硬件钱。真正无状态的弹性算力在 ClickHouse 生态里只存在于闭源托管服务，这是架构缺口不是配置缺口。
3. 宽 schema 演进脆弱。每租户 schema 动态演进，落成数千稀疏列，靠脆弱的 `ALTER ADD COLUMN` 维护。
4. 采样是正确性税。分析查询默认只采 1M 行，因为全扫太贵，用正确答案换延迟。

最承重、且在最新 ClickHouse 版本上依然成立的那条论证是**硬内存隔离**：Doris workload group 是 cgroup 支撑的每池硬限，ClickHouse 的对应机制仍是 best-effort。

目标架构是 Doris 4.0.5 shared-data 模式：tablet 数据在 S3 storage vault，元数据在 MetaService 背后的 FoundationDB，backend 是无状态计算、本地 EBS 只做 file cache。算力物理切成 compute group（on-demand 上的常驻 serving 池 + spot 上常驻 0 副本的弹性 heavy 池），池内再用 workload group 管 CPU、内存、并发。Iceberg 在同一个 S3 上做开放湖层。

**结果**：迁移认证 99.945% 行完整（5,170,688,484 / 5,173,508,562），点查从约 8 秒到约 20 毫秒并证明在数据涨 19 倍时保持平坦 `(src: adhoc_jobs/dynamic_resume_site/content/case_study_ch_to_doris.md)`。线上把 serving 池从 2 台扩到 4 台 backend，**移动了零字节数据**，tablet 归属以元数据操作 rebalance 成 131/128/128/125 `(src: adhoc_jobs/dynamic_resume_site/content/projects/p_elastic_compute.md)`。

**5 层追问防线**：

- **L1 面试官问「为什么不继续用 ClickHouse，或者上 ClickHouse Cloud？」** → 答：这是我最先自我拷问的问题，而且答案很诚实。如果我们的核心痛点只是「自建 CH 扩容太重、要弹性」，那最小动作确实是迁到 ClickHouse Cloud 拿 SharedMergeTree 的弹性、SQL 零改写，而不是跨引擎迁 Doris。我们选 Doris 是因为要的是一个组合：开源无云锁定 + 高并发点查 + 多表 JOIN + 实时 UPSERT。单要弹性不构成换引擎的理由，因为存算分离在 2026 已经是现代 OLAP 的默认架构，CH Cloud、StarRocks、Snowflake、Databricks 全是 `(src: contexts/survey_sessions/clickhouse_vs_doris_storage_compute_ai_load_survey_20260716.md)`。
- **L2 追问「那 Trino / Snowflake / StarRocks 呢？」** → 答：五约束的交集把它们排掉。Trino 没有自己的存储布局，而我这个场景的核心问题恰好是布局（见 S03，点查的地板是文件打开数）。Snowflake 是云锁定。StarRocks 更接近，但它的强隔离 Multi-Warehouse 是 EE 付费功能，OSS 版是 stub 直接抛 `DdlException`，OSS 替代要么走软隔离成本涨 50 到 100%，要么外表 MV 退化让延迟差 10 倍 `(src: work-contexts/career/interview/interview-8-doris-query-routing-oom.md §Q7)`。另外还有一条不是技术取舍的硬约束：合规要求必选 Apache 基金会项目，StarRocks 核心是 ELv2 不是 OSI 开源 `(src: work-contexts/career/interview/interview-6-starrocks-lakehouse.md §6)`。
- **L3 追问「存算分离引入了哪些新的失败域？」** → 答：这是我认为这个架构最容易被讲漏的一点。存算分离**不消除状态，它把状态集中到一层，而那一层从此不能偷工减料**。三个新的有状态失败域替换了「每台机器挂盘」：MetaService（≥3，挂了内表全停）、FoundationDB（≥3，损坏要 `fdbrestore` from S3）、Recycler（≥2，负责 S3 GC）。元数据恢复链路也深了一跳：FE BDB-JE → MS → FDB。所以 HA 必须组件层和业务层两层正交 `(src: work-contexts/career/interview/interview-8-doris-query-routing-oom.md §Q8)`。诚实边界：`fdbrestore` 我没有实际演练过，小时级 RTO 是我的推断。
- **L4 追问「AI 负载这个动机，存算分离真的能解决吗？」** → 答：不能，它是必要条件但远远不充分，这点我在方案里单独处理了。AI 突发负载真正的三个命门是：计费和唤醒粒度（冷启动超 1 分钟加 60 秒最小计费，一个 agent 每天打 1 万条 2 秒的短查询，最高 30 倍成本惩罚，Together AI 就是因为这个弃用 ClickHouse）、多租户 blast radius 隔离、对象存储冷查询延迟 `(src: contexts/survey_sessions/clickhouse_vs_doris_storage_compute_ai_load_survey_20260716.md §3.2)`。存算分离只解决了「算力能独立伸缩」，这三点它一个都不自动解决。我的对应设计是 compute group 级物理隔离 + 执行前准入路由 + file cache 与 warmup。
- **L5 追问「如果这个架构在你们负载下扛不住，plan B 是什么？你算错过什么？」** → 答：plan B 分两步，先降级再重定义问题。降级是热数据留 Doris 内表、冷数据退回 Iceberg 外表直查减压；重定义是先分清到底是弹性不够还是 blast radius 没隔离好，前者加 compute group，后者才需要考虑 serverless 方案 `(src: contexts/survey_sessions/ch_to_doris_migration_interview_arsenal_20260717.md §4)`。算错过的最典型一件：早期 benchmark 显示 Doris 在聚合上打赢 ClickHouse 3 到 5 倍，我自己 red-team 了这个结果，发现混淆变量（一台负载中的 8 核生产节点对一台隔离的 14 核 benchmark 节点），主动撤回了这个倍数。而且我查过，公开的「Doris beats ClickHouse 6-40×」全部溯源到厂商自己，一手的 ClickBench 数据说 ClickHouse 在平表扫描上仍然领先 `(src: adhoc_jobs/dynamic_resume_site/content/case_study_ch_to_doris.md)`。底下那个习惯是：一个数字每次重测都变得更不好看，通常说明你正在收敛到真相。

**归属边界**：Iceberg 和 StarRocks 的部署我做过，但按 FY2026 self-assessment 我自己的写法，那是 deployment proficiency 还没到 full lifecycle ownership `(src: contexts/fy2026_self_assessment.md)`。整体交付状态是 preprod 生产规模验证 + 10T 生产化推进中，这一句放结尾说，绝不在前 60 秒自曝。

**可复用到**：02 监控 SLO（四支柱 SLI 定义）、05 blue/green data（双跑对账即数据层切换）、06 AWS cost（架构级降本）。

---

## S02. 3,700 列宽表迁移的四个内存断点 + 1.7B 行 livelock

**Headline**：这不是一个搬运问题，是一个内存工程问题。一张约 3,700 列的表在四个非直觉的地方把「导出 Parquet 再 bulk load」这条路压爆，而且加硬件一个都解决不了。

**适用题型**：讲一个技术上最难的问题 / 大规模数据迁移怎么做 / 你怎么定位内存问题 / 讲一个你的直觉是错的例子。

**情境**：源表在 ClickHouse，按 `(user_id, ...)` 排序且分布倾斜。目标是 Doris native 表，Unique Key + Merge-on-Write。总量约 52 亿行 / 约 4 TiB / 约 3,700 列 `(src: adhoc_jobs/dynamic_resume_site/content/case_study_ch_to_doris.md)`。

**动作**：我把四个内存来源逐个拆开定位：

1. **footer 炸弹。** Parquet footer 的大小是 `row_groups × columns`。我们早期的对象带着 2.12 GB 的 footer，reader 在碰到任何一行数据之前就把 8 台 backend 全 OOM 了。判别信号很干净：连一个裸的 `COUNT(*)` 都死，证明爆的是元数据解析不是数据扫描。修法是重构对象结构（每个切片更少更大的 row group），footer 降约 9 倍。
2. **不受追踪的 scanner。** Doris 的向量化 Parquet 列读器在 `exec_mem_limit` 之外分配内存。内存随 `scanner_concurrency × columns` 增长，默认配置下每台 backend 约 78 GB。查询级内存限制对引擎自己不追踪的 buffer 毫无作用，所以我把 `max_file_scanners_concurrency` 压到 1。
3. **导出 buffer 跷跷板。** 每条导出流缓冲 `row_group_size × columns`。切片切小对导出内存没有任何帮助；而 row group 切小又会炸 footer。只有两个都切（小对象**且**小 row group）才能解耦这个跷跷板。
4. **导入内存随表增长而不是随批次增长。** 这是最晚暴露、最反直觉的一个。迁到约 17 亿行时，同样的导入任务开始撞内存上限并 livelock：Merge-on-Write 的 delete bitmap 维护和宽表 compaction 是随累积表大小增长的，不随这一批的大小增长。具体量级是每个 load 在约 40 GiB baseline 上再加约 25 GiB，2 并发反复冲破 90 GiB 硬顶 `(src: contexts/survey_sessions/ch_to_doris_migration_interview_arsenal_20260717.md §3.C)`。

保护机制是一个内存 watchdog：软阈值约 78 GiB（停止启动新导入）、硬阈值约 90 GiB（kill 所有 in-flight 导入连接做干净 abort），跑在 110Gi 的 BE 上。被 kill 的 load 提交为空、不留半条数据，配合 MoW 主键去重保证重试幂等。最终把并发钳到 1 解决，零数据丢失，因为吞吐本来就是 export-paced 的。

**结果**：流水线是按字节预算调度、每个对象 checkpoint、任何时刻可安全 kill 的，在四台 backend 上跑到约 19,500 行/秒，比小批量方案快约 50 倍 `(src: adhoc_jobs/dynamic_resume_site/content/case_study_ch_to_doris.md)`。锁定后的配置在 2026-07-12 验证：单个 25.9 GiB 的 part 以约 90K 行/秒稳定导入，峰值约 18 GiB/BE，零崩溃 `(src: contexts/survey_sessions/ch_to_doris_migration_interview_arsenal_20260717.md 附录 A)`。

一个我没在任何地方见过发表的结论：在这么宽的 schema 上，**列数本身能让写吞吐摆动约 5 倍，而完整的正确性栈（MoW 去重、三个倒排索引、ZSTD）总共只花 4% 到 12%** `(src: adhoc_jobs/dynamic_resume_site/content/case_study_ch_to_doris.md)`。看起来贵的功能几乎免费，宽度才是成本。

**5 层追问防线**：

- **L1「切片边界怎么定的？为什么不用 OFFSET，或者按时间切？」** → 答：源表 `ORDER BY (user_id, ...)`，只有按 user_id 的 range 能做剪枝，按时间切会全表扫。user_id 分布倾斜所以不能按值等分，要按均匀行偏移切：一遍扫描用 `rowNumberInAllBlocks()`，每 SLICE_ROWS 行取一个 user_id 当边界，构造无缝、不相交、半开区间的完整覆盖。不用 OFFSET 是因为它是 O(K²)，扫到后面越来越慢。这个方法在 4.15 亿行的月份上 11 秒扫出边界 `(src: contexts/survey_sessions/ch_to_doris_migration_interview_arsenal_20260717.md §3.A)`。
- **L2「你怎么知道是 footer 炸而不是数据扫爆？」** → 答：因为一个裸的 `COUNT(*)` 也死。`COUNT(*)` 不需要读任何数据列，它只需要读元数据。这一个观察就把整个假设空间从「数据太大」切到「元数据太大」，然后 footer 的公式 `row_groups × columns` 直接给出量级。这是我在这个项目里最喜欢的一个判别实验，因为它零成本。
- **L3「为什么不加内存 / 加机器就好？」** → 答：三个不同的理由，正好对应三种失败。footer 那一个是单次分配 2.12 GB 级别的元数据结构，加内存只是把 OOM 推迟；scanner 那一个的内存根本不在 `exec_mem_limit` 的追踪范围里，你调查询级限制它不看；livelock 那一个的内存随累积表大小增长，所以只要继续导入就一定会再撞上，加内存只是换个撞的时间点。**无界增长型故障调大上限永远不是解**，这个判断我在 ClickHouse 僵尸表那次事故里也用过（S12）。
- **L4「为什么 4 并发换 1 并发不影响总时间？这不是牺牲吞吐吗？」** → 答：因为整条流水线是 export-paced 的，瓶颈在 ClickHouse 侧的导出，不在 Doris 侧的导入。1 并发的导入速率仍然高于导出速率，所以降并发的代价是 0。这是我做这个决策的依据，不是「先降下来看看」。反过来说，如果瓶颈在导入侧，正确的做法就不是降并发而是切分区、加 BE。
- **L5「如果重做，你会怎么做？」** → 答：最大的收获是「小切片等于小内存」这个直觉是错的，内存等于 `row_group 行数 × 列数`。如果重来，我会先做一个单切片的端到端验证，大概 10 到 15 分钟：export、检查 footer 能不能加载、load 不 OOM、对账，全绿之后才信任全量 `(src: contexts/survey_sessions/ch_to_doris_migration_interview_arsenal_20260717.md §第二部分 Learning)`。我实际的顺序是先大规模跑，然后才发现读侧的 footer 问题，这是可以避免的返工。另一个边界：这套切片管线是因为 3,700 列把 footer 和 buffer 问题放大了才需要，如果表不宽、行数不极端，直接 `INSERT INTO SELECT` 或 Stream Load 攒批更省事，我不会为了显得复杂而上这套。

**归属边界**：这条线全部是我一手做的。唯一要说清的是 Doris 侧的向量化 Parquet 列读器不受 `exec_mem_limit` 约束是引擎的既有行为，我做的是定位和规避，不是修引擎那部分。

**可复用到**：05 blue/green data（可 kill 可重放的 checkpoint 管线）、07 AWS fundamentals（EBS 与内存 sizing）。

---

## S03. 74.7M 行 query_log 推翻团队的设计假设

**Headline**：原本的 serving 表方案建立在一份精挑的 50 条 benchmark 上，我在提交不可逆的布局决策之前挖了 14 天生产 `system.query_log`、74.7M 条日志行，结论整个反过来了。从 benchmark 设计会优化错误的负载。

**适用题型**：讲一次你用数据改变了设计 / 你怎么做不可逆决策 / 讲一个反直觉的性能结论 / 索引与布局的边界。

**情境**：serving 表要定分布键，而分布键是唯一 ALTER 不了的决策。团队的假设来自一份 50 条查询的 benchmark。

**动作**：我先挖生产 `system.query_log`，14 天、74.7M 条日志行。画像完全反过来：**绝大多数流量（远超 90%）是点查**，keyed 在一个高基数用户标识上，而且大部分是无界的「取最新值」重建，没有任何时间过滤器能事后加上去 `(src: adhoc_jobs/dynamic_resume_site/content/case_study_ch_to_doris.md)`。第二张 serving 表从「也许要」变成必须要，设计也随之变宽。

然后是物理课。点查在 Iceberg 布局上跑 7 到 13 秒，对比 ClickHouse 的 21 毫秒。条件反射的修法是 bloom filter，它把扫描行数砍了 73%，而墙钟时间**一动不动**：一个活跃用户的行散落在 2,044 个分区文件里，地板是文件打开次数，不是扫描行数。我们还在字节层面用 parquet 元数据检查证明了，两条常见的 Iceberg writer 路径会静默忽略声明的 bloom filter 表属性。

**索引修不了布局问题。** 修法是物理重聚簇：一张按用户键 hash 分布的 Doris native 表。因为分布键是唯一不能 ALTER 的决策，我在提交之前跑了两表 A/B（同样的数据、镜像的键、四次测量）。

**结果**：16 到 24 毫秒暖查询，并且在实际迁移过程中在 15M、107M、286M 行三个检查点各复测一次，证明表长 19 倍延迟保持平坦 `(src: adhoc_jobs/dynamic_resume_site/content/case_study_ch_to_doris.md)`。

**5 层追问防线**：

- **L1「74.7M 行日志你怎么挖的，会不会挖挂生产？」** → 答：`system.query_log` 是 ClickHouse 自己的表，挖它的代价是可控的，但我确实踩过相邻的坑：一次朴素的 `COUNT(*)` 审计把 8 台 backend 全打挂过（见 S09），所以我的规矩是任何取证查询都要先想清楚它自己的资源画像。挖 query_log 我是按时间分片、只取需要的列做的。
- **L2「你怎么定义『点查』这一类？分类会不会有偏？」** → 答：按查询形状分类，不是按 SQL 文本。判据是有没有打在高基数用户键上的等值谓词、有没有时间边界、返回行数量级。我特意保留了「无界的取最新值重建」这一子类单独统计，因为它是最难优化的一类：没有任何时间过滤器能事后加上去，所以它决定了布局必须按用户键聚簇。分类的粗糙度我承认，但结论的量级（远超 90%）远大于分类误差。
- **L3「bloom filter 砍了 73% 行数却不省时间，你是怎么定位到 file-open 的？」** → 答：先看两个数字对不上：rows scanned 降 73%，wall clock 不动。这说明成本不在 rows 这个维度上。然后数文件：一个活跃用户的行散在 2,044 个分区文件里。既然每个文件都要 open 一次、读 footer 一次，那成本单位就是文件数不是行数。顺手还发现两条 Iceberg writer 路径静默忽略了声明的 bloom filter 属性，这是我用 parquet 元数据在字节层面验证出来的，不是看文档。**这个模式后来在 Doris 侧又出现了一次**，形式是 tablet/segment 扇出（见 S08），所以它不是一次巧合而是一类问题。
- **L4「为什么是 hash 分布，不是按时间分区加排序键？」** → 答：因为负载画像不允许。主流量是无界的「取最新值」，没有时间谓词，所以时间分区剪不掉任何东西。要让点查只碰一个 bucket，必须让分布键等于查询谓词的键。这也是为什么我坚持在提交之前做 A/B：分布键是唯一 ALTER 不了的决策，其他都能改。同样的教训在 S08 里以另一个面貌出现：那张表的分桶键是 `user_id` 而谓词在 `eventId` 上，于是分桶剪枝完全失效。
- **L5「三个检查点复测，你在防什么？如果它不平坦你会怎么办？」** → 答：我在防的是「小数据上快」这个最常见的自欺。点查延迟随表增长的曲线形状才是要证明的东西，单点数字不是。15M、107M、286M 三个点是量级递进而不是等距，因为我要看的是斜率有没有出现。如果它不平坦，那说明剪枝没有真正生效（比如 bucket 数随分区变化、或者有 straggler tablet），下一步会去看 EXPLAIN 里的 `tablets=x/y` 而不是去加机器。这个判断后来在 S08 里被验证是对的。

**归属边界**：query_log 挖掘、A/B 设计、三点复测都是我做的。原方案的 50 条 benchmark 是团队既有的，我推翻它的时候讲的是「benchmark 会让我们优化错误的负载」，不是「他们错了」。

**可复用到**：02 监控 SLO（用生产日志反推 SLI 定义）、05 blue/green data（不可逆决策的 A/B 门禁）。

---

## S04. 引擎级查询路由：EXPLAIN ESTIMATE PLAN + EXPLAIN ROUTE PLAN

**Headline**：serving 和分析收敛到一套平台之后，不到 1% 的重查询必须在执行前被拦住，因为扩容是分钟级机制而 OOM 是秒级事件。我先证明了静态方案在结构上不可能，然后在 Apache Doris fork 的 FE 里加了两条 SQL 语句，heavy 召回率从 7% 到 100%。

**适用题型**：你做过最有技术深度的事 / 过载与准入控制怎么设计 / 你怎么说服 leadership / 开源怎么参与 / 为什么不用 ML。

**情境**：迁移把 serving 和分析收敛到同一套 Doris 上。重查询不到 1% 流量，但一条被误放进共享轻池的重查询足以拖垮整个池子。事后弹性救不了这个场景：**扩一个计算池是分钟级操作，内存打爆是秒级事件**，所以路由判定唯一安全的位置是 plan time，在任何 backend 碰到数据之前 `(src: adhoc_jobs/dynamic_resume_site/content/projects/p_engine_routing.md)`。

**动作**：第一步是量化原生够不够。我搭了一条闭环可行性流水线（SQL 输入、解析 EXPLAIN 并分类、真实执行作为 ground truth），套件 52 条，代表性做了三角验证：一个真实的约 1,900 列 schema、平台真实的生产 SQL 模板、业务查询 taxonomy。结果原生 EXPLAIN 路由准确率 45%、**heavy-miss 率 27%**，最坏一条漏判跑了 188 秒、吃掉 800 MB，约等于单台 backend 内存的 10%。

两个测量决定了方向：同一条 SQL 模板换参数（时间窗从 1 小时扫到 36 天），**EXPLAIN 输出逐字节相同，而真实内存差 23 倍、耗时差 6 倍**；另一条刻意打在最高基数键上的点查真实执行 32 毫秒，EXPLAIN 却预测全表扫描。这个负载的本质是固定模板加参数摆动，成本随参数摆 50 到 2,000 倍，所以任何基于查询文本打标签的方案在结构上都无解。

这是 signal problem 不是 rule problem。所以我在 fork 上做了两件事：

- **`EXPLAIN ESTIMATE PLAN`**：一个只读 visitor（`PlanEstimateCollector`）后序遍历已定稿的物理计划，把 CBO 本来就算出的逐算子估算以结构化 JSON 输出。纯加法，零删除，不改 cost model 和统计模块。首个单测返回 `estimated_filter_selectivity = 0.9867`，恰好等于 4933/5000，这本身就证明它是在暴露既有数学而不是新建估算逻辑。
- **`EXPLAIN ROUTE PLAN`**：估算加一步，15 条规则的分类器返回 verdict JSON（label、confidence、目标 compute group、目标 workload group、transport），6 到 8 毫秒，与数据量无关（13M 行和 102M 行都是约 8 毫秒，因为估算读的是 CBO 缓存统计、零 I/O）。全部约 21 个阈值声明为 `@ConfField(mutable=true)`，通过 `ADMIN SET FRONTEND CONFIG` 热调，调阈值永远不需要 rebuild。

分类器**被允许不完美**，因为安全保证从来不依赖它：漏判的重查询在轻池撞上固定槽位的内存硬限（约 404 MB/query、不允许 overcommit），约 3 秒内死掉并自动升级到 heavy 池 `(src: adhoc_jobs/dynamic_resume_site/content/case_study_ch_to_doris.md)`。

**结果**：在生产规模的 preprod 集群上，canonical 套件 heavy recall 从 7% 到 100%（15/15），light precision 86%；六条最重的真实生产查询（最大 76 GiB、约 30 亿行扫描）6/6 路由正确、零漏判 `(src: adhoc_jobs/dynamic_resume_site/content/projects/p_engine_routing.md)`。⚠️ 口径漂移：规则数 13 条 → 15 条，补丁体量 7 files/+589 → PR 形态 15 files/+1,310 行，`PlanEstimateCollector` 454 行 → 792 行，一律以 7 月为准 `(旧: work-contexts/career/interview/interview-8-doris-query-routing-oom.md; 新: p_engine_routing.md、contexts/resume_highlights_doris_dcluster.md §3)`。

**5 层追问防线**：

- **L1「为什么非要动引擎？不能用现成的 EXPLAIN 或者 hint 吗？」** → 答：三个证据。一，同模板换参数 EXPLAIN 逐字节相同而真实内存差 23 倍，任何基于文本的方案看到的是同样的字节对应天差地别的成本。二，我 v1 版本真的用 263 行 regex 去抠 `EXPLAIN VERBOSE` 文本，只能做三分类而且大量落进 borderline 兜底桶。三，Doris 的 plugin 框架只有 audit hook，拿不到 plan 期的结构化数据 `(src: adhoc_jobs/dynamic_resume_site/research/interview_story.md 追问弹药路由)`。优化器内部本来就算了 cardinality、selectivity、行宽、scan bytes、sort/agg 状态大小，只是折进一个不透明的 cost 数字后丢弃了。正确的动作是 expose 不是 compute。
- **L2「分类器不完美，你怎么保证不 OOM？」** → 答：分类器不是防 OOM 保证，它是准入控制的第一道筛。真正的保证是运行时的 workload group 硬限：`overcommit=false` 超内存即 reject，约 404 MB 的固定槽位，约 3 秒内熔断，然后自动升级到 heavy 池重跑。所以我追的指标是 recall 不是 overall accuracy，因为**两类错的代价不对称**：漏判 heavy 等于 OOM 等于安全事故，误判 light 只是浪费容量。想通这点之后分类器可以「够用就停」，可以用规则不用 ML，可以接受阈值不完美 `(src: work-contexts/career/interview/interview-8-doris-query-routing-oom.md §4 亮点 3)`。诚实边界：动态 `MOVE_TO_GROUP` 的 Workload Policy DDL 我没实测，所以我的兜底建立在已验证的静态 WG 硬限上，这是 fail-safe 取舍不是没做完。
- **L3「你这个补丁会不会引入估算回归？怎么验证的？」** → 答：diff 是纯加法零删除，我没碰 cost model 系数、统计计算器、plan 选择、ANALYZE、现有 EXPLAIN 输出，也没碰整个 BE。它是计划定稿之后的只读 visitor，复杂度 O(算子数)，不在 hot path，整体加每算子都有 try-catch，异常降级成 `notes[]` 加 `totals.degraded=true`，永不抛错。跨语言那一层的验证是把 Python 参考实现当**可执行规范**而不是文档：189 条真实估算 JSON 组成 golden corpus 同时喂两边，断言 label 逐条一致，在任何集群和镜像存在之前 189/189 全过，后来加到 197 条并逐次抬高断言下限。最脆弱的表面是容错 accessor 语义：null、-1、"unknown" 在两种语言里必须映射到同一个三态，而且「字段缺失」绝不能和「值为零」混为一谈 `(src: adhoc_jobs/dynamic_resume_site/content/projects/p_engine_routing.md、contexts/resume_highlights_doris_dcluster.md §4)`。
- **L4「阈值怎么定的？换个部署还能用吗？为什么不用 ML？」** → 答：阈值是两层资源分类学，不是一堆常数。内存类阈值锚定 light workload group 的预算，随部署缩放；CPU/IO 类是绝对量或每核量。因为「太占内存」是相对被保护的池子而言的，「太耗 CPU」是硬件属性，naive 的写法会把这两类混为一谈 `(src: contexts/resume_highlights_doris_dcluster.md §4)`。更进一步，`routing_light_pool_cores > 0` 时行数类阈值按 `perCore × cores` 派生，所以**同一条查询会随池子大小改判**：60M 行扫描在 8 核池是 heavy、在 84 核池是 light。这就是路由策略与弹性容量的正确耦合，也是这两条工作线真正的咬合点。不用 ML 的三个理由：准入控制是安全关键，不可解释在这里是负债，而规则能输出 reasons 数组供 SRE 审计；规则零训练数据可冷启；真正「本质不可预测」的那一部分（运行时数据倾斜、并发、cache、UDF、spill、正则 CPU 炸弹）ML 也救不了 `(src: work-contexts/career/interview/interview-8-doris-query-routing-oom.md §Q2)`。
- **L5「最深的一层：你算错过什么？你怎么决定什么该上游？」** → 答：两件事。第一件是我最喜欢的 bug：上线后暴露一个 LIMIT 盲区，计划里任何位置出现 LIMIT 都会压制「扫描过大」的 heavy 信号，但 LIMIT 只约束 hash aggregation 这类 blocking 算子的输出，不约束底层扫描量。这个 bug parity 网兜不住，因为 parity 只证明 Java 等于 Python、不证明规范本身正确。它是靠把分类器 verdict 与真实生产行为交叉验证抓到的，修法是结构性的（blocking 算子不再豁免，纯 scan 加 limit 仍豁免），然后作为新 fixture 反哺进 golden corpus。教训是**规范级 bug 需要生产行为交叉验证，corpus 只负责让它不再复发**。第二件是开源决策。Leadership 最初想把分类器一起贡献上游，我逐行读完分类器列出七个具体的业务耦合点：workload group 锚定的内存阈值、5,000 万行 heavy 判定线这类校准常数、recall 优先的风险姿态、公司特有的查询形状、私有 fork 字段。反驳用的是第一个 PR 自己的原则：engine emits data, caller decides policy，把 policy 塞进上游会自相矛盾。结果是 mechanism 打成 8 commit 的干净 PR 对着 synthetic base branch，policy 留内部归档、从不提议 merge。**判断什么不该贡献也是贡献的一部分**，这个论证改变了决策 `(src: adhoc_jobs/dynamic_resume_site/content/projects/p_engine_routing.md)`。

**归属边界（必须一字不差）**：ROUTE PLAN 分类器是我在 Doris fork 里实现的；Arrow Flight 传输是我定的输出契约和 fallback 行为设计，实现是伙伴团队做的；FE 侧的 memory-kill backstop 也属于伙伴团队的 repo `(src: contexts/resume_highlights_doris_dcluster.md §0)`。另外必须主动划的界：我**没改** Doris 的 cost model、统计推导、优化规则、plan 选择，ESTIMATE 是观测层。内存字节数（16B/8KB/1.5×）是粗启发式不是标定模型，被追问就说「量级，给路由阈值用，明确不做 admission control 的精确计算」。Java 分类器是 Python oracle 的忠实移植，移植本身机械，功劳在策略设计和调试不在写 400 行 Java `(src: contexts/resume_highlights_doris_dcluster.md §6)`。开源措辞：engine-level work on an Apache Doris fork, prepared as an upstream PR，PR merge 前不说 contributed to Apache Doris。

**可复用到**：03 AIOps（把优化器信号当可观测性来设计）、05 blue/green（shadow 模式对账）、06 cost（路由是成本控制的入口）。

---

## S05. dcluster 弹性 CN 控制面：0→N→0

**Headline**：heavy 池常驻零副本，路由 verdict 判 heavy 之后约三分钟扩出来、用完自己缩回零。这个 controller 我重写了三次，每次都在**移除** dcluster 的职责，最终它只做一件事：JSON-patch 一个 CR 字段。

**适用题型**：设计一个弹性伸缩控制面 / 幂等 API 怎么设计 / 你怎么做 scoping 判断 / 讲一个静默失败 / 为什么不用 HPA。

**情境**：调用方（fp 引擎）是 at-least-once 的 REST 调用，重试和并发是常态。要控制的是 Doris compute group 的副本数，节点由 Cluster Autoscaler 供给，BE 由 doris-operator 部署和注册。

**动作**：

**成本论证先行。** 生产 query log 挖掘定下问题形状：点查约占捕获执行数的 97%，重查询类不到 3% 但集中承载不成比例的算力，单查询成本比约 1,240 倍（月度累计窗口查询平均 196,354 毫秒，最高频点查平均 158 毫秒）；更直观的对照是那条窗口查询执行 18 次约等于 21,755 条点查的总算力。静态 2 节点 heavy 池 on-demand 约 $772/月；实测 burst 模式（平均每天 2 台跑约 2 小时）on-demand 约 $63/月、spot 约 $24/月，即省约 92% 和约 97% `(src: adhoc_jobs/dynamic_resume_site/content/projects/p_elastic_compute.md)`。这笔算术就是整个模式的全部理由。

**三次重写做减法。** v1 是 dcluster 自己管 AWS Spot Fleet 加 helm；v2 砍掉 Spot Fleet 管理交给 Cluster Autoscaler 给 Pending pod 供节点；终态再砍掉 helm chart（删掉整个 191 行的 `helm/doris-cn`）和 backend 注册，dcluster 只 patch CR 的 `replicas` `(src: contexts/resume_highlights_doris_dcluster.md §2.4)`。第一版设计自己部署 BE 再用 `ALTER SYSTEM ADD BACKEND` 注册，我在实现之前就否掉了：那是把 shared-nothing 的心智模型套在 shared-data 上，cloud 模式下任何没在 operator CR 里声明的 compute group，下一次 reconcile 会被直接抹掉。自建部署逻辑不只是多余，它建立的状态会被平台主动摧毁。

**幂等语义。** launch 是声明式、raise-only：一个 `(namespace, computeGroup)` 只有一个 active handle，同 N 重复调用是 no-op，并发 launch coalesce 到一个 handle 取 `max(N)`。三层并发 guard：每 `(ns,cg)` 的 ShedLock 分布式锁（有界 5 次重试）保证跨副本正确；分布式锁不可用时在 interned `ns:cg` key 上用 JVM monitor 兜底；锁内再 re-scan 做权威复核。所以分布式锁降级时仍然能去重。scale-up 默认幂等（`target=max(workers,increment)`），`force=true` 是唯一显式 opt-in 的非幂等操作；超目标请求 clamp 到 `dorisCNMaxReplicas` 而不是硬拒绝，这样重试不会堆积 Pending pod 越过 ASG 上限 `(src: contexts/resume_highlights_doris_dcluster.md §2.1)`。

**队列去抖 + 空闲 reaper。** scale-up 侧 `QueueScaleDecider` 是纯函数（无 Spring 无 IO，可直接单测）：只有 `waiting_query_num ≥ K` 持续 W 秒才扩，扩完 arm 一个 cooldown。默认 K=3、W=120s、cooldown=5min，对应 BE 冷启动约 3 到 4 分钟。控制论洞见是：**执行有 3 到 4 分钟延迟的系统必须对持续压力反应，不能以快于生效速度的节奏堆叠修正**。scale-down 侧是保守 reaper，每 5 分钟一次，仅当某 compute group 的**所有** BE `currentFragmentNum==0` 且无 fragment 活动超过 `idleScaleDownMinutes`（默认 30）才回收到 0。两个 cron 默认关闭、可灰度开 `(src: contexts/resume_highlights_doris_dcluster.md §2.2)`。

**fail-safe 按操作分方向。** 队列读和 readiness 读出错返回 0 或 -1（绝不误报 ready、绝不因不确定而扩）；idle 判定出错返回 false（绝不因不确定而回收）。fail-safe 不是一个方向，而是**对该操作避免代价高的那个错误动作**的方向。

**结果**：完整链路在生产规模的 preprod 集群上跑通：verdict 判 heavy → controller patch 0→N → ASG 约 66 秒起节点 → backend 约 2 分钟注册 → 分层就绪检查通过 → 查询在 heavy 池执行 → idle reaper 缩回 0。controller 以 34/34 测试通过合入 `(src: adhoc_jobs/dynamic_resume_site/content/projects/p_elastic_compute.md)`。

**5 层追问防线**：

- **L1「为什么不用 HPA？」** → 答：两个层面。第一，HPA 只看 CPU 和内存，它识别不了「这条查询要不要大池子」这种业务语义，只有持有 plan 期估算的那一侧能在执行前判断。第二，也是更根本的：HPA 是分钟级机制，OOM 是秒级事件，所以弹性只能做余量、不能做主防线，主防线必须是进程内硬限加秒级熔断。想清楚这一点之后，我这个 controller 的正确角色就是纯 HPA 角色（把副本数拨到位），安全性由别的层负责 `(src: work-contexts/career/interview/interview-8-doris-query-routing-oom.md §4 亮点 4)`。
- **L2「scale-from-zero 有什么特别的？」** → 答：它的典型失败模式是**静默**，我踩了两个。第一个：BE 请求 `cpu=8`，而 8 vCPU 节点扣掉 kube-reserved 后 allocatable 只有约 7.9，调度模拟永远报 Insufficient cpu，没有任何事件指向那 0.1 核的差距；改成 `cpu=7` 立即扩出，「request 必须严格小于节点 vCPU」进了部署 checklist 的 P0。第二个：ASG 处于字面 0 节点时，autoscaler 没有真实节点可查，只能靠 ASG 的 node-template label 和 taint tag 在内存里构造一个 virtual node 做匹配；缺 tag 时它直接判定这个组永远装不下该 pod 并跳过，pod 永远 Pending 且没有任何报错提到缺失的 tag `(src: adhoc_jobs/dynamic_resume_site/content/projects/p_elastic_compute.md)`。
- **L3「怎么判断池子真的可用了？」** → 答：分层，因为每个单独的信号都会说谎，而且它们各自都真的谎报过。controller 的 RUNNING 只是 pod 计数；`SELECT 1` 探针会被 FE 常量折叠、从不下发到任何 backend，空池也会被它报告健康；所以真正的门槛是解析 `SHOW BACKENDS`，精确匹配 `Tag.compute_group_name` 且 `Alive==true` 的行数 ≥ N，再加一条真正触达存储的 canary 查询。三个细节都写在代码里：pod 起了不等于向 FE 心跳注册了；compute group 必须精确匹配不能用 pod-name 前缀子串；要数到 N 不是数到 1，否则查询会以降低的并行度落地 `(src: contexts/resume_highlights_doris_dcluster.md §2.3)`。
- **L4「讲一个你抓到的最有代表性的 bug。」** → 答：C4，preprod 压测才抓到的，教科书级的静默 no-op。`wg_heavy` 这个 workload group 同时绑了 `cg_default` 和 `cg_query_heavy` 两个 compute group，而 `SHOW WORKLOAD GROUPS` 是每 compute group 返回一行。原代码只按 `Name` 匹配，于是拿到的是空闲的 `cg_default` 那一行（`waiting=0`），结果**队列 backlog 永远看不到、永不扩容**，而且完全不报错。修复是读 `compute_group` 列，按 `(Name AND compute_group==目标CG)` 匹配，并补了回归测试 `(src: contexts/resume_highlights_doris_dcluster.md §2.3)`。我喜欢这个 bug 是因为它三个特征全齐：静默、只有真实压测才现形、根因干净。
- **L5「最深一层：这个设计你会怎么改？还有什么没做对？」** → 答：三件。第一，容量是离散分层的不是连续伸缩的，我刻意不为每条查询算精确目标，因为扩容是分钟级、很多查询在新 backend 就绪之前就跑完了，per-query 弹性大多是表演。sizing 要按瓶颈分类：scan-bound 形状适合 scale-out（更多 backend、更多 S3 拉取并行度），memory-bound 形状（高基数 distinct 聚合、窗口、join 膨胀）适合 scale-up 加 spill，因为它们的状态必须装进单台 backend 的内存。第二，缩到 0 不是免费的：一个停在 0 副本的 compute group 会让 operator 的聚合集群健康字段读成红色（这是监控 quirk 不是故障），而且更尖锐的是它可能在元数据服务里留下一个 orphan lease，在过期之前阻塞其他 group 的 compaction。⚠️ 待确认：这个 lease 的过期时长和当时的影响面我没记全，只能讲到「idle 状态需要专门的运维审视、不能默认免费」这一层 `(src: adhoc_jobs/dynamic_resume_site/content/projects/p_elastic_compute.md)`。第三，spot 的决策我到现在也没上：serving 池永远不上 spot（一次回收等于查询中断加缓存清空），heavy 池在构造上容忍中断（FE 约 2 秒心跳检测、锁约 7 秒释放、失败查询重试一次，全落在 spot 2 分钟回收窗口内，spot 价格低约 62%），但 floor-0 已经让 on-demand 的绝对成本很小，而一条 60 到 500 秒的重查询中途被回收浪费的是已完成的工作加约 3 到 4 分钟的重新扩容。所以决策是装好 node-termination handler 之前先用 on-demand，锚定实测 node-hours 不锚定「spot 便宜」的教条。

**归属边界（重要）**：dcluster 的 Doris 弹性 CN 控制面（CRE-6630）这条线 git-attributed 到我，包含幂等语义、队列/空闲 reconciler、与 Doris FE 的读信号契约、约 700 行端到端集成设计文档。但 dcluster 那批**平台可靠性**工作（spot 中断回退、容量准入、多集群锁修复、审计日志）git 作者是 junhan.ouyang / Runzi Yang，**不是我**，被问到就直说那是平台组同事的工作、我的范围是 Doris CN 弹性这一条线 `(src: contexts/resume_highlights_doris_dcluster.md §0)`。另外「部署相对锚定」仍部分手动（light workload group 的内存锚是部署配置，有 TODO 要自动派生），不能讲成全自动容量感知。

**可复用到**：04 IaC/K8s（operator + CR + CA 的职责边界）、06 cost（架构级降本的标准案例）、07 AWS fundamentals（ASG / spot 生命周期 / scale-from-zero）。

---

## S06. compaction 死亡螺旋（score ~2,500）

**Headline**：迁移后宽表冻在每个 tablet 约 2,500 个 segment，手动 compaction 静默失败，冷点查 40 到 68 秒。根因是三个因素相乘，而且我在任何人花钱之前就证明了加机器无效。

**适用题型**：讲一次最难的故障定位 / LSM 与 compaction 的原理 / 为什么加机器不管用 / 你怎么防止复发。

**情境**：迁移刚完成的 Doris 存算分离宽表，约 3,727 列。表面症状是 compaction score 卡在约 2,500 不动、手动触发 compaction 静默失败、冷点查 40 到 68 秒 `(src: adhoc_jobs/dynamic_resume_site/content/case_study_ch_to_doris.md)`。

**动作与根因（三因连乘）**：

1. **债务累积。** bulk load 期间关掉了 auto-compaction，债一路欠着，直到单个 compaction 任务需要合并约 2,506 个 segment × 3,727 列，被内存 guard 在 43 GB 处 abort。注意这是 task 级 abort 不是进程崩溃，这个区分很重要，因为它决定了你去哪里找证据。
2. **cloud 模式没有 peer cache。** 每个 segment 都是一次约 7 秒的冷 S3 读。compaction 的债**欠的时候按段数计息，还的时候按 S3 round-trip 计费**。
3. **segment 一开始就太小。** 稀疏宽表在内存写 buffer 和落盘 segment 之间有 **46 倍的压缩衰减**，所以想靠 buffer 顶出 1 GB 的段需要 46 GB 的 memtable，不可行 `(src: adhoc_jobs/dynamic_resume_site/research/interview_story.md 复杂度锚点)`。

**加 BE 无效的证明**：单个 tablet 的 compaction 不能跨节点拆分，日志显示 632 次 no-op 唤醒对 9 次真实 merge。这是 concentration-bound 不是 resource-bound。

**结果**：验证过的配方是四件一起（auto-compaction 永远开、写 buffer 放大 4 倍、按月的 bucket 数把 tablet 控制在约 10 GB、更宽的 column group 把 S3 重扫减少约 40 倍），冷点查从 40 秒降到服务端 100 毫秒以内 `(src: adhoc_jobs/dynamic_resume_site/content/case_study_ch_to_doris.md)`。

**5 层追问防线**：

- **L1「compaction score 到底是什么？多少算健康？」** → 答：它衡量 tablet 内互相重叠的 rowset 数量，约等于查询时的归并路数，高并发下健康值稳定在 50 左右 `(src: contexts/survey_sessions/ch_to_doris_migration_interview_arsenal_20260717.md §3.C)`。顺带一个诚实点：网上流传「score = -1 表示健康」这个说法我找不到官方出处，官方真正的健康信号是 score 低且平稳、tablet 版本数远低于 2000。自己没把握的口径就这样如实说。
- **L2「-235 和 -238 是什么，和这个事故什么关系？」** → 答：-235 是单 tablet 版本数超过 `max_tablet_version_num`（默认 2000，官方建议可调到不超过 5000），-238 是单 rowset 的 segment 数超过 `max_segment_num_per_rowset`（默认 200）。因果链要说清：**-235 是果，compaction score 上涨是因**，链条是导入频率大于 compaction 速度、rowset 和 version 持续堆积、撞到 2000 就拒写。组合拳是治本先攒批降导入频率或用 Group Commit 减少 rowset 生成速率，治标再调大版本上限，同时提 compaction 并行（`max_cumu_compaction_threads` 默认 -1 即每盘 1 线程，显式调到 8 或 10；`compaction_task_num_per_disk`）并保持 `enable_vertical_compaction` 开启（按列组合并，宽表上内存只有原来的十分之一）。而 -238 的根因常常绕回分桶：建表桶数太小或数据倾斜，所以先查分桶再调 segment 上限 `(src: contexts/survey_sessions/ch_to_doris_migration_interview_arsenal_20260717.md §3.C)`。
- **L3「关 auto-compaction 是个错误决策吗？」** → 答：在 bulk load 期间关掉它有真实收益（导入不和 compaction 抢资源），错的不是关，是**没有把它当成一笔要还的债来管理**。正确的做法是要么不关，要么关的时候就定好还债的窗口和监控（score 的斜率而不是绝对值）。这也是为什么修复配方里第一条就是「auto-compaction 永远开」：我宁可导入慢一点，也不要一个会指数恶化的债务池。
- **L4「你怎么知道加机器没用？很多人会先扩容试试。」** → 答：因为我先去数了日志里的两个数：632 次 no-op 唤醒对 9 次真实 merge。这说明 worker 不缺、任务缺，而任务缺是因为单 tablet 的 compaction 在机制上不能拆到多个节点。所以这是 concentration-bound。分辨 concentration-bound 和 resource-bound 的通用方法就是看「空转的 worker 有多少」，如果 worker 大量空转而积压仍在，加 worker 一定没用。**在任何人花钱之前把这件事证明掉，是我认为 SRE 在容量问题上最该做的事。**
- **L5「46 倍压缩衰减这个数你怎么得到的？如果重做怎么防？」** → 答：对比同一批数据在内存写 buffer 里的大小和落盘 segment 的大小得到的。它之所以关键，是因为它把「调大 write buffer 到 1 GB」这个直觉解法直接否掉了：要产出 1 GB 的段需要 46 GB 的 memtable。所以真正的修法必须走另外两个维度，bucket 数（控制单 tablet 体积到约 10 GB）和 column group 宽度（减少 S3 重扫次数）。如果重做，我会把「宽表的 memtable-to-segment 压缩比」当成建表前必测的一个量，因为它同时决定 write buffer、bucket 数和 compaction 的可行性，而它不在任何 sizing 文档里。另外要注意这次是**两次独立事故里的第一次**，第二次（score ~4,504）根因完全不同，别混着讲。

**归属边界**：全部一手。要说清 43 GB 那个 abort 是 Doris 自己的内存 guard 起了作用，不是我写的机制。

**可复用到**：02 监控（score 的斜率型 SLI）、07 AWS fundamentals（S3 请求延迟主导的成本模型）。

---

## S07. 孤儿 tablet 卡死（score ~4,504）

**Headline**：第二次 compaction 事故，score 钉在约 4,504，扩容和重启都不动。三条互相独立的只读调查线索收敛到同一个已删除表遗留的孤儿 tablet，它在结构上被排除在调度之外。一条推理链可以被带偏，三条独立证据链指向同一个东西才是判决。

**适用题型**：讲一次你的调查方法论 / 怎么在生产上做只读取证 / AI 辅助排障 / 讲两个看起来一样但根因不同的故障。

**情境**：另一次 compaction score 异常，约 4,504，用扩容和重启都不动 `(src: adhoc_jobs/dynamic_resume_site/content/case_study_ch_to_doris.md、adhoc_jobs/dynamic_resume_site/content_plan.md)`。注意这和 S06 是两次独立事故，用户记忆里的「5k」指的是这一次。

**动作**：三条互相独立的**只读**调查线并行推进：日志枚举、tablet-meta 的 HTTP 端点、catalog 的回收站。三条线收敛到同一个孤儿 tablet，它属于一张已经被 DROP 的表，因此在结构上被排除在 compaction 调度之外，于是它的 score 永远挂在聚合指标里不下来。这次调查是以并行 AI agent 扇出到各个诊断面执行的，这也是我现在做取证的常规方式。

**结果**：定位到唯一根因（一个已删除表的孤儿 tablet），并且全程只读、没有在诊断阶段做任何写操作 `(src: adhoc_jobs/dynamic_resume_site/content/case_study_ch_to_doris.md)`。

**5 层追问防线**：

- **L1「为什么坚持三条独立线，而不是顺着最像的那条查到底？」** → 答：因为 compaction score 是个聚合指标，它天然会把你的注意力引向「哪个 BE 忙」这个方向，而这次的真相是「没有任何 BE 在忙，因为这个 tablet 根本没被调度」。一条推理链在这种情况下很容易被带偏。三条线的价值不是三倍的覆盖率，是**互相否证**：日志能证明有没有 merge 被发起，HTTP 端点能证明 tablet 的 meta 状态，回收站能证明它的表还存在不存在。三个不同层面同时指向一个 tablet 才叫判决。
- **L2「为什么全程只读？重启不是更快吗？」** → 答：因为重启已经试过了没用，而且更重要的是重启会毁掉证据。这次的关键证据是 tablet meta 和回收站的状态，重启和 rebalance 都可能改变它们。我的规矩是诊断阶段严格只读，写操作要有明确的假设和预期效果才做。这个规矩在 S10（DR 恢复被误判失败）里救过一次更大的场面：当时下一步就是破坏性重跑。
- **L3「score ~4,504 和上次的 ~2,500 都是 compaction score，你怎么第一时间分辨？」** → 答：分辨点是「它动不动」和「有没有真实 merge 在跑」。S06 那次 score 是高但系统在挣扎（有 merge、有 abort、有冷 S3 读），配方是减债和改布局。这次 score 是**钉住不动**，扩容重启都无效，且没有对应的 merge 活动，这指向的是调度层面的排除而不是资源层面的不足。**同一个指标的两种形状对应两类完全不同的根因，这是我觉得最值得讲的一点**，所以这两个故事必须分开讲不能合并。
- **L4「孤儿 tablet 这类问题怎么防？」** → 答：机制上它属于「删除路径没有闭合」这一类，和 S12 的 ClickHouse 升级残留僵尸表是同构的：删除动作只做了一半，留下的东西没有写者没有读者但仍然参与后台流程或仍然计入聚合指标。防法是两条，一是在聚合指标里区分「活跃对象的 score」和「全部对象的 score」，否则一个不可调度的对象会永久污染告警；二是删除类操作后要有审计步骤，S12 里我就是把这一步加进了升级 runbook 的末尾。
- **L5「用 AI agent 并行扇出做取证，怎么保证它不幻觉？」** → 答：这正是我把它设计成「三条独立线 + 全程只读」的原因，两个约束都是针对 agent 的失败模式的。只读把最坏后果封顶在「浪费时间」而不是「破坏生产」；三条独立线让任何单线的幻觉都无法单独成为结论，因为收敛必须发生在三个不同的证据面上。换句话说，我不是靠让 agent 更准来保证正确，而是靠让错误无法通过验收。这套东西在我的 oncall triage harness 里是成文规则（Quote-the-line、Subagent Isolation 这类），属于方向 03 的内容。

**归属边界**：全部一手。

**可复用到**：03 AIOps（多 agent 并行取证的正确姿势）、02 监控（聚合指标被不可调度对象污染）。

---

## S08. 宽表点查：扇出是地板，S3 只是冷路径上的乘数

**Headline**：现场抓的暖查询缓存全命中、几乎零 S3，仍然要 1.12 秒。这一个证据就把「S3 慢」这个假设推翻了：真正的成本地板是一次 `WHERE eventId=` 要探遍全部 566 个 tablet、6,689 个 segment 的倒排索引。所以加带宽、加 BE、调 scan 线程全是错方向，唯一同时治冷和暖的杠杆是分区剪枝。

**适用题型**：性能问题怎么定位 / 索引与布局的边界 / 一个你否掉了多个方案的例子 / OLAP 表设计。

**情境**：Doris 4.0.5 存算分离（cloud mode），preprod，表是 4.002 TB / 5,471,146,590 行 / 566 tablet / `ReplicationNum=1`，20 个月分区，单 tablet 约 8.7 GB / 约 1,190 万行，单行宽度约 4,021 字节（3,727 列，约 1 字节/列）。表模型是 `DUPLICATE KEY(user_id, proc_date, eventId, time)`，分桶键是 `HASH(user_id)`，而查询谓词在 `eventId` 上 `(src: contexts/survey_sessions/doris_wide_table_point_query_optimization_survey_20260724.md §1)`。

**动作**：先抓一条禁掉 SQL cache 的真实暖查询 profile 作为最关键证据：

- 总耗时 1sec119ms，`OLAP_SCAN: partitions = 20/20, tablets = 566/566`，零剪枝。
- `BytesFromRemote(S3)` 总计约 139 KB，8 台 BE 里有 7 台是 0，也就是说**几乎不碰 S3**。
- 倒排 searcher 缓存命中 6687 / miss 0。
- 单 instance 分解里主导项是 `InvertedIndexSearcherSearchInitTime` 31.8 毫秒（打开 searcher）和 `BlockInitSeekTime` 42.4 毫秒（7,081 次 seek）。
- 一个 straggler BE 1067 毫秒对最快的 71 毫秒，15 倍拖尾。

然后把冷路径的成本分解成可叠加、可分离的三层（每条用不同的新 eventId，profile 确认冷）：

| 变体 | 剪枝 | 列数 | 冷查时间 |
|---|---|---:|---:|
| A 朴素 `SELECT *` | 566/566 tablet | 3727 | 144s |
| C 带 user_id+proc_date 的 `SELECT *` | 1 tablet | 3727 | 11-31s（典型约 30s） |
| D 带 key 的窄查（5 列） | 1 tablet | 5 | 0.55s |
| 冷→暖：同 id 剪枝 `SELECT *` | 1 tablet | 3727 | 31.8s → 0.46s（69×） |

`A − C ≈ 114s` 是扇出成本，`C − D ≈ 29.5s` 是 `SELECT *` 的列读放大税（剪枝治不了这一层），冷→暖的 30 秒全是冷 S3 列读 `(src: contexts/survey_sessions/doris_wide_table_point_query_optimization_survey_20260724.md §2)`。

**关键设计发现**：eventId 形如 `10001514-IPH-1783218459337`，尾部是毫秒时间戳，还能解析出 user_id。所以 proc_date 可以在查询层直接从 eventId 推出来注入，**不需要额外建一张 50 亿行的 eventId→user_id+proc_date 映射表，也不需要先跑一次 discovery 查询**。

**结果**：注入 `proc_date` 把扇出从 566 tablet 砍到约 28，实测窄查询 69 秒 → 0.9 秒、字节数降 270 倍；剪枝加暖缓存两个正交动作齐做，`SELECT *` 是 0.46 秒 `(src: contexts/survey_sessions/doris_wide_table_point_query_optimization_survey_20260724.md §0/§4.1)`。

**5 层追问防线**：

- **L1「你怎么证明不是 S3 慢？」** → 答：一条暖查询就够了。缓存全命中、`BytesFromRemote` 总计约 139 KB、7 台 BE 是 0，仍然 1.12 秒。如果瓶颈是 S3，这条查询应该是毫秒级。另一个旁证是冷读的聚合吞吐只有约 1 MB/s，NIC 带宽用不到 1%，所以瓶颈是「GET 延迟 × GET 数量」而不是带宽。**这是我做性能定位的标准手法：找一个能让候选变量消失的实验，而不是逐个调参数看变化。**
- **L2「那为什么加 BE 和调 scan 线程都没用？」** → 答：因为点查的并发结构决定了它们没有作用面。单 tablet 的点查跑在 1 个 BE 上，而 LIMIT 点查的 parallelism 被强制为 1；Doris 的 parallel scan 是按**行数**切的（约 210 万行一个 scanner，48 线程上限），LIMIT 点查的行数根本不够切。我实测 4→16 BE 只对全表冷扫有 1.5 倍收益，对点查约等于 0，而且 rebalance 还会制造更多冷缓存。remote scanner 池 48→128 只有 1.19 倍，那治的是冷读并发不是扇出 `(src: contexts/survey_sessions/doris_wide_table_point_query_optimization_survey_20260724.md §3)`。两级并发（tablet 间并发、tablet 内并发）治的是「并发」，治不了「一次查询要扇出 566 个 tablet」这个**数量**问题，数量只能靠剪枝。
- **L3「为什么分桶剪枝没生效？表设计错了吗？」** → 答：分桶键是 `user_id` 而谓词在 `eventId` 上，所以无法裁剪 bucket；没有 `proc_date` 谓词，所以无法裁剪 partition。于是全部 20 个分区、566 个 tablet 都活到倒排探测层。而倒排索引是 per-segment 的局部索引，Doris 没有全局索引，所以它能把 5.47B 行过滤到 1 行，但代价是每个 segment 都要开一次 searcher。表设计不算错（`user_id` 是主查询路径的键，也是抗倾斜的键），错的是这条 `eventId` 点查路径没有被算进表设计的时候。这和 S03 是同一个教训的另一面：**布局必须匹配真实的谓词分布，索引补不上布局的账。**
- **L4「你为什么否掉建映射表和上 row store 这两个方案？」** → 答：映射表被否是因为有更省的等价物，eventId 内嵌了时间戳可以直接推 proc_date，省掉一张 50 亿行的表加双写；而且它只多给一个 user_id（28 tablet 降到 1 tablet），0.9 秒已经够了，边际收益很小。row store 是有条件上：它治的是 `SELECT *` 的列读放大，但代价是约 2 倍存储（4T 到约 8T）加写放大，而且部分行存 `row_store_columns` 官方明确不支持 Duplicate 表，只能全行存。更关键的是短路快路径**不会触发**（Duplicate 表 + 非 key 谓词，profile 里 `RowsShortCircuitPredFiltered = 0` 已经证实了），所以别指望它。窄查询本来就 `RowsRead=0`、成本全在倒排过滤，row store 对窄查询完全无用 `(src: contexts/survey_sessions/doris_wide_table_point_query_optimization_survey_20260724.md §3/§4.3)`。**能列出所需列加剪枝是最省的路，不必上 row store 也不必升级。**
- **L5「最深一层：这个修法有什么风险？还有什么你不确定的？」** → 答：三个风险我都写进去了。一，`AUTO PARTITION BY RANGE(date_trunc(...))` 有已知的裁剪正确性 bug（apache/doris#65606），date_trunc 表达式分区加手工分区谓词可能错误返回空集，所以上线前必须用已知存在的 eventId 验证结果非空、并且 `EXPLAIN` 里确认 `partitions=1/20`、`tablets≈28/566`。**默默剪出一个空集比慢查询危险得多。** 二，remote scanner 池有线程泄漏 issue（apache/doris#65416），4.1.1-rc 上 `rs_normal` 池线程不回收涨到 27k+ 直接冻 BE，我实测的「大于 512 会 hang」大概率就是撞这个，所以别把 remote 池往大调。三，straggler BE 那个 15 倍拖尾在全扇出时决定墙钟（最慢 BE 的约 70 个 tablet 说话），剪枝之后每 BE 的 tablet 数下降、尾也随之收窄，但我没有单独治 straggler。还有一个我主动纠正过的错误认知：我一开始担心 4.0.5 没有持久化缓存元数据、重启后缓存清零导致冷读周期复发，现场核实之后这个担心**不成立**（`clear_file_cache=false`、LRU dump/replay 已 backport、缓存盘是 EBS 持久卷不是 instance-store），铁证是同一块盘从重启后 2% 累积到 61%。所以升 4.1 的性价比被我下调了，只剩 `storage_format=V3` 治 footer 元数据税一个理由，而那对我们不是主线。

**归属边界**：现场 profile 抓取、成本分解、方案裁决都是我做的，全程 readonly。`SELECT *` 的分解矩阵里有一部分是我先期的实测数据，一并纳入了同一份分析。

**可复用到**：02 监控（profile 字段作为一手证据源）、06 cost（S3 按请求计费的成本模型）。

---

## S09. 99.945% 对账与「验证方法本身要工程化」

**Headline**：迁移完整性认证在 99.945%，5,170,688,484 / 5,173,508,562，0.055% 的缺口逐行归因到去重语义。但这个故事真正的点不是那个百分比，是对账方法本身要为安全性重新设计，因为一次朴素的 `COUNT(*)` 审计把 8 台 backend 全打挂过。

**适用题型**：数据一致性怎么保证 / 你怎么设计验证 / 讲一次你的工具伤到了生产 / 迁移的回滚点设计。**不要用这个开场**，它是尽职信号不是架构信号。

**情境**：约 52 亿行、约 3,700 列的宽表跨引擎迁移，目标表是 Unique Key + Merge-on-Write。

**动作**：三层保证：

1. **行数层。** 每个月做无损校验门禁：各切片在 ClickHouse 侧的行数之和必须等于重新计算的当月总数，对不上就响亮告警并且**不标记这个月完成**。月份从 `system.parts` 的所有 active 分区发现，所以不会漏月。实测 3,000 万行的月份切 5 片，差值为 0 `(src: contexts/survey_sessions/ch_to_doris_migration_interview_arsenal_20260717.md §3.A)`。
2. **原子性层。** 被内存 watchdog kill 的 load 提交为空，不留半条数据。
3. **去重层。** 目标表是 Unique Key + Merge-on-Write，重复导入靠主键去重，所以重试是幂等的。

对账方法本身的工程化：几十亿行的宽 MoW 表上，朴素 `COUNT(*)` 要合并 delete bitmap，会超时甚至打挂集群（这件事真发生过，8 台 BE 全挂）。所以最终对账是按月分区计数并调高 `query_timeout`，不是一把梭全表 count `(src: contexts/survey_sessions/ch_to_doris_migration_interview_arsenal_20260717.md §3.A、adhoc_jobs/dynamic_resume_site/content/case_study_ch_to_doris.md)`。

**结果**：99.945% 行完整（5,170,688,484 / 5,173,508,562），0.055% 的缺口逐行归因到去重语义 `(src: adhoc_jobs/dynamic_resume_site/content/case_study_ch_to_doris.md)`。

**5 层追问防线**：

- **L1「99.945% 不是 100%，那 0.055% 是丢数据吗？」** → 答：不是丢，是去重语义的必然结果。源表允许存在按目标表主键定义重复的行，目标表是 Unique Key + Merge-on-Write，所以这部分行在写入时被主键去重折叠了。我是逐行归因的，不是估算的。这个区分很重要：**「差异」和「丢失」是两件事，能把差异逐条解释掉才叫对账完成**，报一个 99.945% 而解释不了缺口等于没对账。
- **L2「为什么按月分区对账，不做逐行 checksum？」** → 答：成本和收益不匹配。逐行 checksum 在 3,700 列宽表上要读全部列，等于把整个迁移的 IO 再付一遍，而且它检出的问题类型（单列值损坏）在这条链路上概率极低，因为中间格式是 Parquet 有自己的校验、写入路径是原子提交。行数门禁加去重语义归因能覆盖真正的风险（切片漏了、切片重了、load 半提交）。如果这是金融账务系统我会选不同的答案，但这是分析表。
- **L3「一次 COUNT(*) 打挂 8 台 BE，这件事你怎么复盘？」** → 答：教训是**验证工具也是生产负载**。我当时的心智是「审计是只读的所以安全」，这是错的：只读查询照样能耗尽内存。它在宽 MoW 表上贵的原因很具体，`COUNT(*)` 要合并 delete bitmap。改法有三层：查询层按分区切小并调 timeout，配置层给审计走独立的 workload group 有自己的内存预算，流程层是审计查询也要过 EXPLAIN。这个事故后来直接喂进了 S04 那条线的动机：如果连我自己写的审计查询都会打挂集群，那业务侧的 ad-hoc 查询显然需要执行前的准入控制。
- **L4「迁移的回滚点是怎么设计的？」** → 答：粒度是「月」。每个月是一个独立可重跑的单元，完成才标记，没完成就重跑整月而不是从头开始；流水线是按字节预算调度、每个对象 checkpoint、任何时刻可安全 kill 的。所以回滚不是「回到迁移前」，是「这个月没标记完成，重跑它」。这个设计的代价是要维护月份级的状态，收益是任何时刻中断的损失上限是一个月的进度，而且因为 MoW 去重，重跑天然幂等。
- **L5「最深一层：你会怎么改这套验证？它有什么它证明不了的？」** → 答：它证明不了三件事，我都清楚。一，它证明行数对得上，不证明**语义对得上**（比如某列的类型转换有精度损失，行数一分不差）。二，它不覆盖迁移之后的持续双写一致性，我们的模式是一次性迁移不是长期双跑。三，它不覆盖查询结果等价性，也就是同一条业务 SQL 在两个引擎上返回一样的答案。第三点其实是我认为下次最该补的：正确的做法是抓 top N 条真实业务 SQL 在两边跑做结果 diff，这才是用户真正感知的一致性。我在 StarRocks 到 Doris 的验收里用过这个方法（抓 top 50 BI SQL 到 Doris 复刻 MV 看 EXPLAIN 命中率，≥80% 即过，1 到 2 人天），但迁移对账里没做 `(src: work-contexts/career/interview/interview-6-starrocks-lakehouse.md §6)`。

**归属边界**：全部一手。数字精确到个位的两个大数（5,170,688,484 / 5,173,508,562）在私人材料里可以用，如果日后搬到公开产物要按脱敏规则处理 `(src: adhoc_jobs/dynamic_resume_site/content_plan.md)`。

**可复用到**：05 blue/green data（双跑对账与切换门禁）、02 监控（导入成功率 SLI）。

---

## S10. EBS snapshot 跨集群恢复约 5.2B 行

**Headline**：跨集群 ClickHouse 恢复流程被数据拷贝服务标记为失败，眼看要触发破坏性重跑。我先独立验证数据面本身：TCP 9000 能连、`select 1` 成功，数据库其实已经恢复了。**控制面说「任务失败」不等于数据面的事实。**

**适用题型**：备份恢复 / DR 怎么做 / 讲一次你没有按流程走 / 自动化的判定逻辑有什么坑。**这个故事的边界必须主动说清。**

**情境**：跨集群 ClickHouse 恢复走 EBS snapshot、PV/PVC 置换、重启、校验四步，恢复量级约 5.2B 行 `(src: adhoc_jobs/dynamic_resume_site/content/integration/case_cards.json (dr-restore-false-failure)、adhoc_jobs/dynamic_resume_site/content_plan.md)`。流程被数据拷贝服务判定失败，下一步是破坏性重跑。

**动作**：先看 status API 的时间戳加日志，显示各阶段其实都已完成。然后**直接探测数据面**：TCP 9000 可连、`select 1` 成功，证明数据库已经恢复了。根因是自动化用 pod-ready 当就绪门槛，校验跑得太早，在 ClickHouse 真正起来之前就判了失败。

**结果**：没有执行任何破坏性回滚或重跑；扩容回来等真正就绪后重新校验通过；把流程的失败判定从 pod-ready 改成必须等 TCP 9000 加一条真实 SQL 探测 `(src: adhoc_jobs/dynamic_resume_site/content/integration/case_cards.json)`。

**5 层追问防线**：

- **L1「你们的 DR 方案是什么？RPO / RTO 多少？」** → 答：**这里我要先划边界。** 这是一次跨集群恢复演练，不是一套制度化的 DR。RPO 是 EBS snapshot 周期隐含的，约 24 小时；我们没有做过定期的恢复演练，也没有把 RTO 写成 SLO `(src: adhoc_jobs/dynamic_resume_site/content_plan.md)`。⚠️ 待确认：那次恢复的实测 RTO 时长和 snapshot 的实际周期我没有记录，所以我不会给数字。我能讲的是这次恢复里的判断，和它暴露出的自动化缺陷。这个边界我宁可自己先说。
- **L2「为什么敢不执行重跑？万一数据真的不完整呢？」** → 答：因为我的验证顺序是「先证明数据面状态，再决定动作」，而不是「先信控制面，再动手」。三个证据同向：status API 的阶段时间戳全部完成、日志无错误、数据库自己能应答 SQL。而下一步动作是**破坏性且不可逆**的，所以举证责任在「要重跑」那一边而不是在「不重跑」这一边。这是我在 S07 里也用的规矩：诊断阶段严格只读，写操作要有明确假设和预期效果。
- **L3「pod-ready 当就绪门槛，为什么是个坑？」** → 答：因为 pod-ready 是编排层的事实，不是应用层的事实。这类坑我见过好几个同构版本：`SELECT 1` 探针被 Doris FE 常量折叠、从不下发到 backend，所以空池也报健康（S05）；controller 的 RUNNING 只是 pod 计数；StarRocks CN 的 init container 用 `|| echo "Already registered"` 吞掉 DNS 错误，pod Running 但 FE 完全不感知，结果所有 scan 查询报 `Warehouse not available` `(src: work-contexts/career/interview/interview-6-starrocks-lakehouse.md §7)`。共同的规律是：**每一层都有自己的「活着」定义，跨层复用会说谎。** 数据面的门槛必须是数据面的探针。
- **L4「如果要把这件事做成制度，你会怎么做？」** → 答：四步，而且我会明确说这是我还没做的。一，定义 RPO/RTO 目标并且反推 snapshot 频率，而不是反过来接受 snapshot 频率隐含的 RPO。二，恢复演练进日历，按季度跑，演练的验收标准是数据面探针加一次业务 SQL 结果 diff（这一点和 S09 的 L5 是同一个缺口）。三，恢复流程里所有「判定失败」的分支都要有独立的数据面复核，因为下一步往往是破坏性的。四，把恢复时长作为一个被记录的指标，否则 RTO 永远是拍的。
- **L5「最深一层：这套 EBS snapshot 方案本身有什么结构性弱点？」** → 答：三个。一，snapshot 是块级一致而不是应用级一致，如果不停写或者不 flush，恢复出来的可能是一个需要 crash recovery 的状态，恢复时长因此不可预测。二，它的粒度是整卷，所以做不了表级或分区级恢复，一个逻辑误删（比如 DROP 错表）用这套方案要恢复整个集群，代价和恢复时间都不成比例。三，它跨集群依赖 PV/PVC 置换，这一步是有状态编排里最容易出错的地方，而我们的自动化恰好就在这一步的判定上出了错。所以如果重新设计，我会把「逻辑误删」和「集群级损毁」当两类不同的故障配不同的手段，而不是用一套 snapshot 覆盖两者。存算分离之后这个问题的形状会变，因为数据在 S3 上，恢复的对象从块设备变成元数据，这也是我认为存算分离在 DR 上的真实红利。

**归属边界**：这是 oncall 处理的一次事件，恢复流程和数据拷贝服务是既有的自动化，我做的是判断和事后的判定逻辑修正。不能讲成「我设计了 DR 方案」。

**可复用到**：05 blue/green data（切换的就绪门槛设计）、07 AWS fundamentals（EBS snapshot 语义）、04 IaC（自动化的判定分支设计）。

---

## S11. Iceberg + StarRocks lakehouse 与 49× 性能工程

**Headline**：为风控客户做 30/90/180 天大窗口、动态多维度的 OLAP 聚合，我把分析链路迁到 Iceberg + StarRocks，端到端把一个 270 万行 × 约 1,900 列的查询从 12.2 秒做到 247 毫秒。核心不是堆硬件，是 profile 定位到 S3 按请求计费、所以头号敌人是小文件而不是数据量。

**适用题型**：性能调优方法论 / 湖仓架构 / 你怎么知道该停 / 调优怎么固化成机制。

**情境**：ClickHouse 在动态维度加大窗口预聚合上不合适（没有引擎级 MV 自动改写，要手写物化链路），存算一体扩容也贵 `(src: work-contexts/career/interview/interview-6-starrocks-lakehouse.md §6)`。

**动作**：架构跃迁的本质是**数据真源从引擎私有格式变成开放格式 Iceberg on S3，计算引擎降级为可插拔的无状态查询层**。取舍三角是开放格式 + 引擎级 MV（CBO 透明改写）+ 弹性算力（spot CN），同时满足三条的排掉 Druid/Pinot/BigQuery/Trino+dbt。链路是 FP → Kafka → Kafka Connect 加自研 SMT（featureMap 的整数 key 查 FP MySQL 解析成命名列）→ S3 Iceberg → StarRocks FE/CN 存算分离。

调优按价值分级，S 级只有两项：

- **小文件合并 619 → 49 个文件。** FSIOTime 从 7.9 秒到 63 毫秒（125 倍），冷查询 7.5 秒到 744 毫秒。这不是「调了个参数」，是理解 S3 按请求次数收延迟税之后做的数据布局治理，参数（`BATCH_SIZE` 50K→500K、`target-file-size` 512MB→1GB、`commit.interval` 60s→10min）只是手段。
- **dop=2 对 dop=4 的对照实验。** 冷查询 dop=4 快 2.2 倍（542ms vs 1175ms），热查询 dop=2 反而快（196ms vs 220ms），最终保持 dop=2。这是唯一一个同一参数最优值随瓶颈类型反转的实测：冷查询 I/O bound、热查询 CPU bound。按主场景（热缓存是生产主路径）定值，接受冷查询劣化。

**结果**：热查询 12.2 秒 → 247 毫秒（49 倍），冷查询 16 倍；MV 预聚合把 270 万行压到每天几百行、257 毫秒 `(src: work-contexts/career/interview/interview-6-starrocks-lakehouse.md §3)`。

**5 层追问防线**：

- **L1「你怎么知道该往小文件这个方向查？」** → 答：`EXPLAIN ANALYZE` 显示 CPU 只用了 137 毫秒、99% 时间在 Scan-I/O。这一张图同时排除了加 CPU、改 SQL、加内存三个方向。然后关键的一步不是继续调参数，是问「这个系统的计费单位是什么」：S3 按请求次数收延迟税不按数据量，所以头号敌人是小文件不是数据量。每个系统都有自己的计费单位（Kafka 是 partition、JVM 是 GC pause），找到它优化方向就唯一了。**没有 profile 的调参是迷信。**
- **L2「dop 调大不是通常都更快吗？」** → 答：取决于这个并行占不占 CPU。I/O 并发是在藏延迟，可以远超核数（`connector_io_tasks` 从 4 到 16 到 32，12.2 秒到 8.9 秒）；计算并发受核数硬约束，dop=8 在 2 核上跑出 21 秒，比 dop=2 慢 4 倍。所以「能不能调大」这个问题本身要先分类。而且最终取值要按真实 workload 分布做权衡，不是把每个数字调到最大：dop=2 的依据是热查询是生产主场景。**调优是分布问题不是单点问题。**
- **L3「你怎么知道什么时候停？」** → 答：瓶颈守恒加边际收益止损。Scan 从 8.5 秒砍到 145 毫秒之后，ScheduleTime 的 268 毫秒浮上来成了最大头，那是框架固有开销，于是 433 毫秒收工。知道何时停和知道怎么调一样重要。这也是我给调优价值分级的原因：判断有价值的标准是有 profile 证据、有对照实验、有 trade-off 决策、原理可迁移，缺任何一条降级。版本升级和 CN 扩容这类没有区分度的动作我放 B 级，不当主菜。
- **L4「调优做完了怎么保证不腐烂？」** → 答：这是 SRE 和 DBA 调参的本质区别。小文件是写入侧持续产生的，一次性合并没有用，所以三件套才叫「调优完成」：nightly `rewrite_data_files` 加 `expire_snapshots` 加 `remove_orphan_files` 的 maintenance job、`iceberg_data_file_count < 10000` 的 SLO、page cache hit 的告警 `(src: work-contexts/career/interview/interview-6-starrocks-lakehouse.md §4)`。⚠️ 待确认：这套 maintenance job 是设计还是已经在跑，我的记录里没写清，所以我按「部署到位、lifecycle 维护是设计态」讲。另外 `commit.interval` 从 60 秒改到 10 分钟是和业务确认过 10 分钟的可见性延迟可接受之后才定的，不是我单方面优化写侧文件数。
- **L5「最深一层：这个架构一年后怎么样了？你会怎么评价这个决策？」** → 答：一年后因为合规要求必选 Apache 基金会项目（StarRocks 核心是 ELv2 不是 OSI 开源），我们要评估换到 Doris。**而正因为数据已经在开放格式上，换引擎只是换查询层，验收变成了一道 1 到 2 人天的实测题而不是一次数据迁移项目**：抓 top 50 条 BI SQL 在 Doris 上复刻 MV，看 `EXPLAIN` 的 MV 命中率，≥80% 就过。这是我认为架构决策价值的正确评价方式：它的价值要在一年后、在你没预料到的那个约束出现时才显现。反过来说的诚实边界是，我当时选开放格式的理由里并没有「合规可能要求换引擎」这一条，所以这一半是设计红利、一半是运气。

**归属边界**：部署和性能工程是我做的。运维成熟度按我自己在 FY2026 self-assessment 里的写法，是 deployment proficiency 还没到 full lifecycle ownership `(src: contexts/fy2026_self_assessment.md Q2)`。Iceberg 的部署只写到 "Deployed Iceberg and StarRocks"，lifecycle 维护按设计态讲。

**可复用到**：05 blue/green data（引擎可插拔即数据层切换能力）、06 cost（三 warehouse on-demand/spot 分层）、02 监控（两视角 SLI）。

---

## S12. ClickHouse 僵尸系统表引爆的亚秒级 OOM

**Headline**：告警指向 Kafka 消费积压，真因在三个系统之外的 ClickHouse 自己的系统表里：多次升级留下的 1.21 TiB 改名残留表，被一次一秒内完成的后台 merge 引爆。**30 秒采集在构造上无法为 1 秒尖刺作证。**

**适用题型**：讲一次最难的 oncall / 监控粒度 / 告警与真因隔了几跳 / 升级残留 / 为什么调大内存上限是错的。

**情境**：可见信号是 Kafka consumer lag，多个租户同时单调上涨，没有任何流量尖峰可以解释 `(src: adhoc_jobs/dynamic_resume_site/content/incidents/w_zombie_oom.md)`。

**动作**：消费者看起来像肇事者其实是受害者：它向 ClickHouse 的写入被 `Code 241 MEMORY_LIMIT_EXCEEDED` 拒绝，每个失败批次触发 30 秒 sleep 加 rebalance 的重试循环，同一批数据反复撞同一个失败。

即时检查一无所获：`SHOW PROCESSES` 和 `system.merges` 都是干净的，内存停在约 2 GiB 基线，30 秒采集的监控平台也是一条平线。连报错文本都在误导，`current RSS: 8.85 GiB` 读起来像慢性泄漏。破案靠 ClickHouse 内部 1 秒粒度的 `system.metric_log`：基线约 2 GiB，一秒之内冲到 21.60 GiB 的服务上限，被 OvercommitTracker 杀掉，随即回落基线。

尖刺坐实之后问题变成「什么东西一次性分配了 20 GiB」。答案是升级残留：ClickHouse 升级改系统日志表 schema 时会把旧表改名加数字后缀、另建新表，**从不删除旧数据**。这个集群群经历过多次升级，尸体越积越多，一张改名后的 trace 日志表 1.21 TiB、一张 profiling 日志表 308 GiB。这些表没有写入者也没有读取者，但它们的 parts 仍然参与后台 merge。

**结果**：修复是删除但要删对范围。TRUNCATE 只作用于当前无后缀的表，对僵尸表毫无作用，必须显式 DROP 并用单查询参数绕过 50 GB 删表保护；1 TiB 级的 DROP 在 1 到 3 分钟内完成，期间服务不中断，而且因为无写者无读者，操作在构造上零风险。消费积压不会自愈，需要重启消费者打破 rebalance 循环。预防分三路：配置层给默认无 TTL 的内部日志表加 TTL、把数据量最大的日志直接关掉、显式钉死服务器内存上限；流程层给升级 runbook 末尾加一步审计系统表的后缀残留；舰队层一处确诊立即触发跨集群审计，最严重的集群查出 1.65 TiB，另一个 region 的同类集群查出 250 GiB 且已经每天产生 3 次 OOM `(src: adhoc_jobs/dynamic_resume_site/content/incidents/w_zombie_oom.md)`。

**5 层追问防线**：

- **L1「告警在 Kafka，你怎么想到去看 ClickHouse？」** → 答：看错误类型。consumer lag 单调上涨但没有流量尖峰，而且是多个租户同时，这两个特征合起来指向下游而不是消费者自己。然后看消费者的日志，错误是 `Code 241 MEMORY_LIMIT_EXCEEDED`，那是 ClickHouse 返回的错误码而不是消费者自己的问题。**Kafka lag 通常是症状而不是病灶**，我另一次事故里也是这个模式：lag 加上 ClickHouse 日志里的 `Delaying inserting block by 10 ms because there are 1015 parts`，那次的病灶是 parts 爆炸导致写入被 backpressure `(src: adhoc_jobs/dynamic_resume_site/content/integration/case_cards.json (kafka-lag-parts-explosion))`。
- **L2「点查什么都看不到的时候怎么办？」** → 答：换证据源，而且要找一个时间分辨率高于故障时间尺度的证据源。30 秒采集对 1 秒尖刺在构造上就是不可见的，这不是配置没调好，是采样定理。ClickHouse 自己有 1 秒粒度的 `system.metric_log`，那才是唯一能作证的时间序列。所以我的规则是：**对内置高频指标的引擎，OOM 之后它的内部日志就是第一证据源，不是 Prometheus。** 同理，`current RSS: 8.85 GiB` 这个报错文本是最误导的东西，因为它记录的是「报错那一刻」而不是「峰值那一刻」。
- **L3「为什么不直接调大 pod 内存上限？」** → 答：因为这是无界增长型故障。僵尸表的体积会随每次升级继续增长，调大上限只是把下一次 OOM 推迟到表更大的时候，而且推迟期间你还多付了内存钱。我的判据很简单：**先分类故障是有界还是无界，有界的可以加余量，无界的必须切断增长源。** 同样的判断我在宽表迁移的 livelock 上用过（S02 的 L3），那次内存随累积表大小增长，所以降并发是解、加内存不是。
- **L4「一处确诊为什么要全 fleet 扫？」** → 答：因为**升级残留是横向缺陷**。它的成因是升级动作本身，所以任何有相同升级史的集群一定有相同的残渣，这跟运气无关。一处确诊之后立即扫，最严重的集群 1.65 TiB、另一个 region 的兄弟集群 250 GiB 且已经每天 3 次 OOM，正沿着同一条曲线爬。这个判断的价值是把一次 P2 从「修好了一个集群」变成「消掉了一类隐患」，而且它的成本极低，就是一条 `system.tables` 的查询乘以集群数。识别横向缺陷的信号是：根因是不是由一个所有集群都执行过的动作产生的。
- **L5「最深一层：这类问题的机制性防法是什么？」** → 答：三层，从弱到强。最弱的是加 TTL 和关掉高量日志，那是治当前这一批。中间的是把审计加进升级 runbook 的末尾，那是治流程，但它依赖人执行。最强的、我认为真正对的做法是把「删除路径没有闭合」当成一类问题来监控：任何有名字模式的残留对象（`_N` 后缀的系统表、已 DROP 表的孤儿 tablet）都应该有一个巡检把它们暴露成指标，而不是等它们引爆。这和 S07 的孤儿 tablet 是同构问题，都是「没有写者没有读者但仍然参与后台流程或仍然计入聚合指标」。这个抽象是我从这两次事故里提出来的，不是从文档里学的。

**归属边界**：全部一手 oncall 处理。

**可复用到**：02 监控（采集粒度必须匹配故障时间尺度）、04 IaC/K8s（升级 runbook 的收尾审计步骤）。

---

## S13. Doris FE crashloop：JVM Xmx 8G 对 cgroup limit 4Gi

**Headline**：FE 在 22 小时内被 OOMKill 142 次，平均每 9 分钟一次。症状是 startup probe failed 加 CrashLoopBackOff，但那是结果不是原因。关键分叉是 exit 137 加上日志里**没有** JVM OOMError 栈，这说明是 cgroup 外部 kill 而不是 JVM 内部 OOM。

**适用题型**：RCA 方法论 / JVM 在 K8s 上的坑 / 症状链与因果链的区别 / 有状态组件的配置管理。

**情境**：Doris FE（Java 进程）在 K8s 上 CrashLoopBackOff，22 小时内 142 次 OOMKill `(src: work-contexts/career/interview/interview-8-doris-query-routing-oom.md §Q6)`。

**动作**：先区分症状链和因果链。症状链是 startup probe failed → CrashLoopBackOff，那是被观测到的顺序。因果链要靠两个证据确定：exit code 137 等于 SIGKILL，而且日志里**没有** JVM 的 OutOfMemoryError 栈。两者合起来指向 cgroup 层的外部 kill，不是 JVM 堆自己不够。根因是 JVM 配了 `-Xmx8192m` 而 K8s 的 `memory.limit` 只给了 4Gi，JVM 一涨到 4Gi 就被 OS kill。

修复过程踩了两个坑：`confOverrides` 是整个 `fe.conf` 的替换而不是 diff overlay；`electionNumber` 默认 3 而 `replicas=1`，BDB-JE 等不到 quorum。

**结果**：RESTART 归零 `(src: work-contexts/career/interview/interview-8-doris-query-routing-oom.md §8)`。

**5 层追问防线**：

- **L1「exit 137 和 JVM OOM 怎么区分？」** → 答：三个信号一起看。exit 137 是 128+9 即 SIGKILL，JVM 自己的堆溢出不会以 SIGKILL 结束，它会抛 OutOfMemoryError 并留下栈；`kubectl describe` 里 Last State 的 Reason 会写 OOMKilled；容器的 `memory.max_usage_in_bytes` 会贴着 limit。反过来如果是 JVM 内部 OOM，你会看到 OOMError 栈、heap dump（如果配了）、而且 RSS 不一定贴着 cgroup limit。**这个区分决定了你去改 JVM 参数还是改 K8s limit，方向完全相反。**
- **L2「为什么 Xmx 等于 limit 也不行？」** → 答：因为 JVM 的总内存不只有堆。metaspace、code cache、线程栈、直接内存、GC 自身的开销都在堆外，所以 `Xmx = limit` 一定会被 kill。正确的做法是 Xmx 留出堆外余量（经验上堆占 limit 的 50% 到 75%，取决于线程数和直接内存用量），或者用容器感知的 `MaxRAMPercentage` 让 JVM 自己按 cgroup limit 算。这类问题在 Java 中间件上非常普遍，Doris FE、Kafka broker、StarRocks FE 都会踩。
- **L3「142 次 / 22 小时这个频率本身告诉你什么？」** → 答：平均每 9 分钟一次，这个规律性本身是证据。随机性故障不会这么均匀；均匀的重启间隔说明这是一个确定性过程在重复：进程启动、内存单调涨到 4Gi、被 kill、重启。所以我不需要抓现场，只需要解释「为什么它总是在这个内存点死」。**故障的时间规律性是一个被低估的证据维度**，S12 那次也是靠时间形状（一秒内的尖刺加回落）定性的。
- **L4「`confOverrides` 是整体替换这个坑，一般化的教训是什么？」** → 答：配置合并语义必须先验证再依赖。我以为它是 diff overlay，实际是整个 `fe.conf` 替换，结果我以为只改了一个参数，实际把其他参数全部改回了默认。这类坑的通用防法是改完之后**读回真实生效值**而不是读回你提交的 manifest，对 Doris 就是 `SHOW FRONTEND CONFIG`。这也是为什么我在 S04 里把所有路由阈值做成 `@ConfField(mutable=true)` 并且 verdict 暴露 `key_metrics`：能在线读回真实生效值的系统才是可运维的。
- **L5「最深一层：有状态组件的 quorum 配置为什么容易出这种错？」** → 答：因为 quorum 参数和副本数是两个独立的旋钮，而它们必须一致。`electionNumber` 默认 3 但 `replicas=1`，BDB-JE 永远等不到多数派。同类的规律是 3 FE 才容忍 1 台故障（`floor(N/2)+1`），2 FE 容忍 0 台，也就是说从 1 台加到 2 台**不提高可用性反而降低**，因为你多了一个故障源却没有多数派 `(src: work-contexts/career/interview/interview-6-starrocks-lakehouse.md §9)`。所以有状态组件的正确做法是把副本数和 quorum 参数当一对约束一起管，最好由 operator 派生而不是各配一处。而且这类失败在部署阶段是静默的：pod 起来了、日志在刷、只是永远选不出 leader。这和 S05 的 scale-from-zero 静默失败、S10 的 pod-ready 说谎是同一族问题。

**归属边界**：全部一手。⚠️ 注意这个故事的组件是 Doris FE，出处只有 6 月的 `interview-8`，7 月材料里没有复述，所以细节按 6 月记录讲，不要和 7 月的路由数字混在一起说。

**可复用到**：04 IaC/K8s（JVM 在容器里的内存模型、operator 配置合并语义）、02 监控（重启频率的规律性作为证据）。

---

## S14. ClickHouse connection refused：八跳定位

**Headline**：外部客户端连 ClickHouse 报 connection refused，pod 却全是 Running。refused 意味着链路上某一跳没人监听，所以要沿链路逐跳走并**停在第一个失败的跳**上。这次停在 `kubectl get endpoints` 返回 `<none>`。

**适用题型**：网络类问题怎么定位 / 你的排查方法论 / K8s Service 的坑。

**情境**：外部客户端连 ClickHouse 对外端口报 connection refused，pod 本身一切 Running `(src: adhoc_jobs/dynamic_resume_site/content/integration/case_cards.json (clickhouse-connection-refused))`。

**动作**：沿 Client、DNS、NLB、NodePort、ingress-nginx、Service、Endpoints、进程逐跳排查。断点在 Endpoints：`kubectl get endpoints` 返回 `<none>`。原因是 pod 异常重启后 operator 没有刷新 readiness label（停在 `no`），Service 的 selector 因此匹配不到任何 pod。

**结果**：对 ClickHouse StatefulSet 做 rollout restart，让 operator 重新评估并写回 ready label；endpoints 重新填充，外部连接恢复 `(src: adhoc_jobs/dynamic_resume_site/content/integration/case_cards.json)`。

**5 层追问防线**：

- **L1「refused、timeout、reset 你怎么分？」** → 答：三种错误对应三个完全不同的假设空间，这是我排查的第一个分叉。refused 是有人回了 RST，说明包到了但那一跳没有进程监听，所以查监听方和转发规则；timeout 是包没有回来，说明中间某一跳丢了或者对端不响应，所以查路由、SG/NACL、节点级出网；reset 是连上之后被断，查应用层和中间件的超时常量。我另一次 MySQL connect timeout 的故障就是靠先把 timeout 和 refused/认证类错误分开，才发现失败集中在某一台 worker 节点上、指向节点级 DNS 或出网故障 `(src: adhoc_jobs/dynamic_resume_site/content/integration/case_cards.json (mysql-timeout-node-dns))`。
- **L2「为什么停在第一个失败的跳？」** → 答：因为下游的所有现象都是这一跳的后果，继续往后看只会看到一堆一致的假象。这次如果不停在 Endpoints 而是继续去 exec 进 pod 看 ClickHouse 进程，会发现进程健康、端口在听，然后就会得出「ClickHouse 没问题所以是客户端问题」这个错误结论。**逐跳的价值在于它给出一个可判定的停止条件。**
- **L3「pod Running 但 endpoints 为空，机制上是怎么发生的？」** → 答：Service 的 selector 匹配 pod 的 label，而这个 operator 用一个 readiness label 做 endpoints 的门控。pod 异常重启之后 operator 没有把这个 label 从 `no` 刷回去，于是 selector 匹配 0 个 pod，Service 悄悄失去全部后端。这是一个「控制器状态没有收敛」的经典形态：期望状态和实际状态都没错，是中间那个派生字段停在了旧值。检查手法很简单，`kubectl get endpoints` 和 `kubectl get pod --show-labels` 对一下就出来了。
- **L4「rollout restart 是正确的修法吗？有没有更小的动作？」** → 答：更小的动作是直接 patch 那个 label 回去，代价更低。我选 rollout restart 是因为要让 operator 自己重新评估并写回，避免我手改的值下一次 reconcile 又被覆盖，也避免我改错。这是一个取舍：手改 label 恢复更快但可能和 operator 打架，rollout restart 慢一点但让状态由所有者收敛。判据是「这个字段的所有者是谁」，所有者是 operator 的字段就让 operator 写。
- **L5「最深一层：怎么让这类问题不再需要人来查？」** → 答：加一条针对性的可观测性，而不是加一条告警。`endpoints == 0 而 pod ready > 0` 这个组合是一个明确的矛盾状态，它可以直接做成指标，一旦出现就说明门控逻辑坏了，不需要等外部客户报错。这类「两个应该一致的信号不一致」的检查是我认为可观测性里性价比最高的一类，因为它不需要阈值，也不会误报。同族的例子有 S05 的「pod RUNNING 但 `SHOW BACKENDS` 里 Alive 数不够」、S10 的「控制面报失败但数据面能应答 SQL」、S11 里 StarRocks 的「CN Running 但 FE 不感知」。这四个故障其实是同一个抽象：**跨层的活性定义不一致，且没有任何一层负责检查它们是否一致。**

**归属边界**：全部一手 oncall 处理。

**可复用到**：02 监控（矛盾状态型指标）、04 IaC/K8s（operator 状态收敛）。

---

## S15. 大租户 QPS 尖峰的联合止血

**Headline**：一个大租户的 QPS 尖峰把实时 serving 链路整体拖垮，瓶颈同时压在 serving、异步消费、租户专属 Kafka topic 和数据库上，单层修复兜不住。处置顺序是**先降级再限额扩容**，因为数据库没有余量时加 serving 容量只会把事故推下悬崖。

**适用题型**：过载治理 / 多层同时饱和怎么处置 / 应急变更的纪律 / 多租户隔离。

**情境**：单个大租户 QPS 尖峰，错误率与 p95/p99 上升，Kafka 积压增长，数据库逼近饱和 `(src: adhoc_jobs/dynamic_resume_site/content/integration/case_cards.json (tenant-qps-joint-mitigation))`。

**动作**：先沿入口路径（客户端、流量切换层、网关、serving）追踪尖峰的进入路径，确认瓶颈同时压在四层上，所以任何单层修复都兜不住。然后按顺序：流量 50/50 分流；通过租户配置在线把非关键的 recompute/backfill 限速清零（不需要重启）；在**明确上限内**扩 serving 和异步的 HPA（消费线程池 40 核心 / 80 上限）；把该租户 topic 的 Kafka partition 翻倍并临时把 DB 实例规格翻倍；稳定之后按 0 到 2 到 5 到 10 逐级恢复限速。

**结果**：链路恢复，每个应急旋钮都有明确上限和成文的回滚方案 `(src: adhoc_jobs/dynamic_resume_site/content/integration/case_cards.json)`。

**5 层追问防线**：

- **L1「为什么先降级不先扩容？」** → 答：因为扩容会把压力传导到还没有余量的那一层。这次数据库已经逼近饱和，加 serving 容量等于加大打向数据库的 QPS，把事故推下悬崖。降级的作用是把非关键负载（recompute、backfill）的额度让给关键路径，它是**减少需求**而扩容是增加供给，而在多层同时饱和的场景里减少需求的传导方向是安全的。用 λ 和 μ 的语言说：先降 λ 再抬 μ，反过来会在中间某一层制造新的饱和点。
- **L2「怎么确认是单租户主导而不是整体增长？」** → 答：分租户的 QPS 曲线，加上延迟分解。延迟分解那一步是关键：`request_time` 减 `upstream_response_time` 得到 waiting latency，如果 waiting 占主导那就是入口的连接或队列饱和而不是应用变慢。这次三组信号同向：waiting latency 主导、单租户 QPS 主导、ingress 的饱和信号（连接数、CPU、重试）全部吻合。**先证明是 waiting latency 主导再去动应用层**，这是我在这类事故上的固定顺序 `(src: adhoc_jobs/dynamic_resume_site/content/integration/case_cards.json (waiting-latency-qps-spike))`。
- **L3「Kafka partition 翻倍这种不可逆操作，你在事故中怎么敢做？」** → 答：分两种情况，我在另一次 MirrorMaker lag 的事故里就没做。那次 lag 高位但复制服务完全健康（无报错、无重启、资源正常），真正的约束是 topic 只有 3 个 partition 而 per-partition 吞吐是 mirror 并行度的硬天花板；因为峰值过后 lag 会自然收敛，我把 partition 扩容标成不可逆、需要先评 key 分布和 rebalance 影响，走评审而不是当场做 `(src: adhoc_jobs/dynamic_resume_site/content/integration/oncall_track_record.md §4)`。这次做了，是因为在场的是持续的用户可见影响而不是可自愈的积压。**判据是「不做的代价是否持续且用户可见」，而不是「这个动作有多方便」。**
- **L4「每个旋钮都要有上限，为什么？」** → 答：因为应急状态下的 HPA 是最容易造成二次事故的东西。不设上限的扩容会在下游制造新的饱和点（数据库连接数、Kafka 分区吞吐、连接池），而这些下游的失败往往比原始故障更难恢复。所以我给消费线程池明确写了 40 核心 / 80 上限，给每个旋钮写了回滚方案。恢复的时候也是逐级（0 到 2 到 5 到 10）而不是一把恢复到原值，因为一把恢复等于再造一次尖峰。
- **L5「最深一层：这次之后该做什么机制性改进？」** → 答：三件，按价值排。一，租户级的准入控制和配额，让单个租户的突发不能吃掉共享容量。这和我在 Doris 侧做的事是同一个思路（S04 的执行前准入路由、compute group 级物理隔离），只不过在 serving 链路上做的是 QPS 维度、在 OLAP 上做的是内存维度。二，把「非关键负载可在线降级」做成一等公民能力而不是应急手段：这次能在线清零 recompute/backfill 的限速且不用重启，那是运气好而不是设计好，它应该是每个租户配置里有明确语义的旋钮。三，把错误预算的成本回压给制造问题的一方而不是全体用户：我在 StarRocks 的 SLO 设计里写过这个动作（预算耗尽就对超预算的 user/resource_group 做配额降级），但在 serving 链路上没有落地 `(src: work-contexts/career/interview/interview-6-starrocks-lakehouse.md §5)`。

**归属边界**：oncall 处置是我做的。DB 实例规格翻倍、Kafka partition 翻倍这类动作在事故中通常是多人协作，我讲的时候说「我们」的部分要说「我」的具体判断（顺序、上限、回滚），不要把整个联合处置都说成一个人做的。

**可复用到**：02 监控（waiting latency 分解、burn rate 分级动作）、05 blue/green（50/50 分流）、06 cost（配额回压）。

---

## 附：跨方向复用速查

| 故事 | 01 Doris/DB | 02 监控 SLO | 03 AIOps | 04 IaC/K8s | 05 blue/green | 06 cost | 07 AWS |
|---|---|---|---|---|---|---|---|
| S01 | 主线 | 四支柱 SLI | | | 引擎可插拔 | 架构级降本 | S3/EBS 角色 |
| S02 | 主线 | | | | 可 kill 管线 | | 内存 sizing |
| S03 | 主线 | 日志反推 SLI | | | 不可逆 A/B | | |
| S04 | 主线 | | 信号即观测 | | shadow 对账 | 路由即成本闸门 | |
| S05 | 主线 | | | operator/CR 边界 | | 主案例 | ASG/spot/scale-from-zero |
| S06 | 主线 | 斜率型 SLI | | | | S3 请求计费 | |
| S07 | 主线 | 聚合污染 | 并行取证 | | | | |
| S08 | 主线 | profile 取证 | | | | S3 请求计费 | |
| S09 | 主线 | 导入成功率 | | | 双跑门禁 | | |
| S10 | 中环 | | | 判定分支 | 就绪门槛 | | EBS snapshot |
| S11 | 中环 | 两视角 SLI | | | 换引擎 | warehouse 分层 | |
| S12 | 主线 | 采集粒度 | | 升级 runbook | | | |
| S13 | 主线 | 重启规律性 | | JVM in container | | | |
| S14 | 主线 | 矛盾状态指标 | | operator 收敛 | | | SG/NLB 链路 |
| S15 | 主线 | burn rate 动作 | | | 50/50 分流 | 配额回压 | |
