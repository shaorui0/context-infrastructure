# ClickHouse → Doris 存算分离迁移:国内大厂基础架构面试军火库

> 生成日期:2026-07-17
> 定位:把 CRE-6630(SoFi 表 CH→Doris 存算分离迁移)这个项目,武装成国内大厂「基础架构 / 存储 / 数据库 / SRE」方向面试可以正面硬刚的完整素材。
> 内容:项目价值定位 + STAR/CARL 主叙事 + 技术深挖 Q&A 防守 + 减分项自查。
> 素材来源:内部项目 skill(`rules/skills/sofi_ch_to_doris_migration/`)、已有选型调研(`clickhouse_vs_doris_storage_compute_ai_load_survey_20260716.md`)、8 路并行外部调研(监控/SLO/调优/架构/迁移/面试信号,均带 URL 交叉验证)。

---

## 0. 先对齐一件事:你的招牌数字

面试里最容易翻车的不是难题,是自己的数字对不上、拆不开。这个项目有两组数字,先锁死口径再进考场。

你口述的是 **10TB / 100 亿行**。项目 skill(CRE-6630)里落到纸面、可复现的核心事实是:单张源表 `sofi.event_result`,**51.7 亿行 × 3727 列**的超宽表,迁到 Doris native 表 `sofi_native.event_result`。

两者可以并存:10TB 大概率是物理/裸数据体量,51.7 亿行是这张核心宽表的行数,100 亿行可能是跨表或全量口径。但面试建议这样处理:

把 **「51.7 亿行 × 3727 列的超宽表」作为招牌**,因为它每个字都能从你自己的记录里拆出来、复现出来,面试官越追越显你扎实。如果要用 10TB / 100 亿的总量口径,你必须能当场拆解:这 10TB 是压缩前还是压缩后、几张表、每张多少行、宽表占多少。调研里有一条铁律直接适用:**Never use a metric you cannot explain in an interview**(任何写出来的数字都要能当场解释,[Resumly](https://www.resumly.ai/blog/quantifiable-metrics-for-process-improvement-on-your-resume))。数字含糊或拆不开,是面经里反复出现的红旗。

而且 3727 列这个细节本身就是最好的素材:它把「迁移」从一件搬运的体力活,变成了一个内存工程问题。下面整份叙事都围绕这个转变展开。

---

## 第一部分:这个项目把你定位到什么 level

### 1.1 一句话定位

这不是一个「我按方案把数据从 A 导到 B」的执行项目。它是一个**由你 own 全生命周期的基础设施选型 + 落地 + 运维建设项目**:从生产级集群方案设计、benchmark、迁移工程、真实 workload 压测,到监控指标与 SLA 规范。用面试的语言说,它同时覆盖了「技术选型判断力 + 大规模数据工程 + 存算分离架构理解 + 可观测性/SLO 体系建设」四个通常分散在不同人身上的能力面。

### 1.2 它天然证明了哪些高价值信号

国内大厂在基础架构方向区分 senior(P7)和 staff(P8)时,听的不是「你会不会」,而是「决策是不是你做的、影响面有多大、有没有沉淀成标准」。参考 [interviewing.io 对 Meta 行为面的拆解](https://interviewing.io/blog/how-software-engineering-behavioral-interviews-are-evaluated-meta),分水岭是影响面:junior 影响自己的模块,senior 影响整个团队(通常要 3 人以上协作),staff 影响整个 org(通常跨 2 个以上团队)。

这个项目能端出的信号,按含金量排序:

**技术选型判断力(最稀缺,直接指向 senior+)。** 你不是被指定用 Doris,你理解了为什么在「AI 前端接入后产生海量不可预测查询」这个背景下,存算分离架构是必要条件。更强的是,你手上那份选型调研已经把命题里的三个错误假设拆开了:存算分离不是 Doris 独有(CH Cloud、StarRocks、Snowflake 全是默认架构)、AI 负载真正的命门是计费粒度和 blast radius 而非架构本身。能讲到这一层,你就从「用了个新数据库」跃迁到「理解了这个赛道的架构演化和取舍」。

**大规模数据工程的深度(硬核,经得起追问)。** 3727 列超宽表 + 51.7 亿行的迁移,你踩过并解决了一串非直觉的内存问题:Parquet footer 爆炸、row-group buffer 与 footer 互相拉扯、column reader 不受 `exec_mem_limit` 约束、MoW delete-bitmap 随表增长。这些不是查文档能背出来的,是真在生产上打过才有的判断。

**可观测性与 SLA 体系建设(SRE 核心职能)。** 你定义了监控指标、制定了 SLA 规范。调研里一条直接的表述:SRE 的核心职能之一就是定义和完善 SLO 和 SLI([知乎 SRE 复盘](https://zhuanlan.zhihu.com/p/265002048))。你做的正是这件事。

**工程韧性设计(容量规划 + 风控)。** in-cluster、断线自愈、自动降并发、无损校验门禁,这套设计体现的是「一次跑几天的大迁移怎么保证不出错、出错能自己恢复」的工程成熟度。

### 1.3 对你职业主线的赋能

你的长期主线是 AI Infrastructure Engineering,定位 Agent Reliability Specialist(见 `2026-05-09_ai_sre_career_architecture_plan.md`)。这个项目恰好落在主线上:它的起因就是「AI 接入前端后产生的海量查询冲击底层 DB」,你解决的是 AI-native 负载下的数据基础设施可扩展性。这让你在讲这个项目时可以自然收束到一个更大的叙事:你不是在维护一个数据库,你在为 AI 驱动的负载模式重建底层数据设施。这正是 FY2026 self-assessment 里你给自己定的成长方向,即把 StarRocks / Iceberg 从「部署熟练」升级到「全生命周期 ownership」,而 CRE-6630 就是这个升级的落地证据。

---

## 第二部分:主叙事(2–3 分钟口述版)

面试深挖项目的标准结构是先 Why 再 How,不要一上来讲实现([Swediary](https://swediary.substack.com/p/preparing-for-the-technical-deep))。对 senior 级别推荐用 CARL 而非纯 STAR:把 Situation 和 Task 合并成 Context,末尾加一句 Learning 体现资深([Eng Leadership](https://newsletter.eng-leadership.com/p/how-to-nail-big-tech-behavioral-interviews))。下面是可以直接改口语的版本。

**Context(背景与为什么值得做)。** 我们是一家 SaaS 风控公司,把 AI 接入前端后,客户经由 agent 和 text-to-SQL 发起的查询量级和突发性都上了一个台阶,这些查询直接打到底层 OLAP。原来用 ClickHouse 自建,扩容靠加实例、手动 reshard,不够动态,高并发下重查询延迟劣化明显。所以问题不是「换个更快的库」,而是「底层数据设施要能应对 AI 驱动的、不可预测的高并发负载」。我 own 了从选型到落地运维的整个方案。

**Action(我的关键决策与动作,注意说「我 decided」而非「我们做了」)。** 

第一,选型判断。我评估后选了 Doris 存算分离,理由不是它更先进,而是它同时满足开源无云锁定、高并发点查、实时更新和弹性伸缩这个组合。我也想清楚了存算分离不是银弹:它解决算力独立伸缩,但 AI 突发负载真正的成本命门在计费/唤醒粒度和多租户 blast radius,这部分我在方案里单独做了隔离设计。

第二,这是整个项目里我最想讲的一点。迁移的核心表 `event_result` 是一张 3727 列的超宽表,我很快意识到这不是一个搬运问题,是一个内存工程问题。宽表在四个非直觉的地方会压爆内存,而且同样的硬件靠正确配置就能跑通。比如 Parquet 的 footer 大小等于 row_group 数乘以列数,列数一多,小 row group 会产生 GB 级 footer,导致 Doris 在读任何一行数据之前、光解析 footer 就 OOM,连一个 `COUNT(*)` 都跑不出来。再比如每条导出流的内存等于 row-group 行数乘以列数,而不是切片或对象大小。我把这几个内存来源拆开定位,用「切小对象 + 小 row group」同时压住 footer 和 export buffer,再在 Doris 侧把 scanner 并发降到 1、开 spill、按表增长动态降低导入并发。

第三,正确性保证。源表按 user_id 排序且分布倾斜,我用一遍扫描按均匀行偏移取边界来切片,而不是用 OFFSET(那是 O(K²)),415M 行的月份 11 秒扫出边界。每个月做无损校验门禁:各切片行数之和必须等于重新计算的当月 CH 总数,对不上就响亮告警、这个月不标记完成。

第四,工程韧性。整个迁移跑在集群内的 K8s Job 里,断线安全、checkpoint 落 PVC、自动降并发自愈,靠 CH 的 OvercommitTracker 加 Doris 侧的内存 watchdog 避免被 OOMKill,被杀的导入是原子的,配合 MoW 去重保证不产生脏数据或重复。

**Result(结果,百分比和绝对值双写,并说清价值)。** 锁定后的配置在 2026-07-12 验证:单个 25.9 GiB 的 part 以约 90K 行/秒稳定导入,峰值内存约 18 GiB/BE,零崩溃。存算分离相比存算一体三副本,存储成本官方口径最高降 90%,compaction 只需处理单副本副本、资源大幅下降。更重要的是,我把这套东西沉淀成了可复用的迁移 skill 和运维监控规范,不是一次性交付。

**Learning(复盘,体现资深)。** 最大的收获是「小切片等于小内存」这个直觉是错的,内存等于 row-group 乘列数。如果重来,我会更早做单切片端到端验证(export、检查 footer 可加载、load 不 OOM、对账,约 10 到 15 分钟),再信任全量,而不是先大规模跑再发现读侧 footer 的问题。

---

## 第三部分:技术深挖 Q&A 防守

国内大厂基础架构深挖的骨架是 What → Why → What if 三层([OA VO Service](https://oavoservice.com/articles/openai-interview-breakdown-four-interviewer-styles-project-deep-dive))。Why 层必须端出「没选的方案 + 数据对比 + 失效边界」,只说「A 比 B 好」直接扣分。凡简历写「精通/熟练」的点必被往死里问([aylei/interview](https://github.com/aylei/interview))。下面按你列的三个维度 + 架构选型,把最可能被追问的问题和强答案备齐。

### 3.A 迁移本身

**Q:10TB / 几十亿行怎么迁?为什么不直接 `INSERT INTO SELECT` 或用现成工具?**

先给方案全景,再讲你的选择。Doris 的导入方式和适用场景:

| 方式 | 适用 | 说明 |
|---|---|---|
| Stream Load | 中小批量、实时 | HTTP 同步返回,可直接判定批次成功 |
| Broker Load / S3 Load | 大批量对象存储文件 | 走通用事务体系,`SHOW LOAD` 看进度 |
| Spark Load | 超大批量、需外部算力预处理 | 借 Spark 做分布式排序/聚合 |
| Routine Load | Kafka 持续消费 | 有 `routine_load_lag` 消费延迟指标 |
| INSERT INTO SELECT / 外表 | 湖仓直读、跨 catalog | 通过 Multi-Catalog 读 Iceberg/Hive 再落内表 |

你的选择:因为源是 CH 的超宽表、瓶颈在内存而非算力,你走的是「CH 导出成分片 Parquet 对象 + Doris 侧按对象 load」的路径,把 export 和 load 解耦,各自独立调内存和并发。这个选择的边界:如果表不宽、行数不极端,直接 `INSERT INTO SELECT` 或 Stream Load 攒批更省事;正是因为 3727 列把 footer 和 buffer 问题放大,才需要这套切片管线。

**Q:切片边界怎么定?为什么不用 OFFSET / 不按时间切?**

源表 `ORDER BY (user_id, ...)`,只有按 user_id 的 range 能做分区剪枝,按 time range 会全表扫。user_id 分布倾斜,所以不能按 user_id 值等分,要按均匀行偏移切:一遍扫描 `rowNumberInAllBlocks()`,每 SLICE_ROWS 行取一个 user_id 当边界,构造无缝、不相交、半开区间的完整覆盖。不用 OFFSET 是因为它 O(K²),扫到后面越来越慢。这个方法 415M 行的月份 11 秒出边界。

**Q:怎么保证迁完数据不丢不重?**

三层保证。行数层面:每月做无损门禁,各切片 CH 行数之和等于重新计算的当月总数,不符就告警且不标记完成(实测 30M 行的月份切 5 片,差值为 0)。原子性层面:被 watchdog 杀掉的 load 提交为空、不留半条数据。去重层面:目标表是 Unique Key + Merge-on-Write,重复导入靠主键去重。月份从 `system.parts` 的所有 active 分区发现,不会漏月。

**Q:最终怎么对账?直接 `COUNT(*)` 比一下?**

这里有个坑可以主动点出:几十亿行的宽 MoW 表上,朴素 `COUNT(*)` 会因为要合并 delete-bitmap 而超时。所以对账用按月分区计数、并调高 query_timeout,而不是一把梭全表 count。

### 3.B 监控与 SLO

**Q:这套 Doris 上生产,你监控哪些指标?**

按四个类别讲最清晰,指标名以官方 [Monitor Metrics](https://doris.apache.org/docs/3.x/admin-manual/maint-monitor/metrics/) 为准。先说一个能体现你读过一手文档的点:官方绝大多数指标是 Counter 累积值,要按间隔采样算斜率才有意义;而且官方的告警阈值页面明确标着 TODO,即阈值是社区经验不是官方推荐。

查询侧四大件:`doris_fe_query_latency_ms{quantile="0.99"/"0.999"}`(分位延迟)、`doris_fe_qps`、`doris_fe_query_err_rate`(或 query_err 算斜率)、`doris_fe_connection_total`(逼近 max_connections 要警觉)。慢查询官方没有独立 metric,走 audit log 和 Query Profile。

导入侧:FE 看 `doris_fe_routine_load_lag`(消费延迟)和 `doris_fe_txn_status`(用 visible/aborted 比值算成功率);BE 看 `doris_be_load_rows`/`load_bytes`(tablet sink 吞吐)、`load_channel_count`、`flush_thread_pool_queue_size`(flush 队列堆积说明落盘瓶颈)。

Compaction 与 tablet 健康(这块最该讲深,因为直接关系迁移期稳定性):集群级报警挂 `doris_fe_max_tablet_compaction_score`(FE 聚合所有 BE 的最大值),单机排障看 `doris_be_tablet_base_max_compaction_score` 和 `cumulative_max_compaction_score`。副本健康看 `doris_fe_tablet_status_count{type="unhealthy"}`,正常趋近 0。存算分离下副本健康的重要性大幅下降,因为数据在共享存储、BE 无状态,这本身就是从 CH 三副本迁过来的价值点之一。

存算分离特有:file cache 命中率、对象存储 IO、compute node 资源。

一个诚实加分点:关于「compaction score = -1 表示健康」这个说法,我没找到官方出处,官方真正的健康信号是 score 低且平稳、tablet 版本数远低于 2000。面试如果自己没把握的口径,就这样如实说,反而加分。

**Q:SLO 怎么定?**

OLAP 的 SLO 和 OLTP 不一样,按四支柱讲,方法论锚 [Google SRE Book](https://sre.google/sre-book/service-level-objectives/):

| SLI | 典型目标 | 要点 |
|---|---|---|
| 查询可用性 | 99.9%(单区)~ 99.95%+(核心) | 成功查询/总查询,把 5XX/429/超时算失败 |
| 查询延迟 | P99 缓存命中 <10s,冷/miss <60s | 用分位不用均值,分冷热、分点查/聚合/大扫描 |
| 导入成功率 | 99%+ | `SELECT COUNT(*) FILTER(WHERE state='CANCELLED')/COUNT(*) FROM LOADS` |
| 数据新鲜度 | P99 端到端 lag < 60s | OLTP 没有这一维,拆成采集+Kafka lag+计算+可见性 |

可以背的对标数字:AWS Redshift 多 AZ 承诺 99.99%、单节点只承诺 99.5%,说明架构冗余度直接决定可承诺的可用性等级,这正是存算分离加多副本的价值。阿里云 ClickHouse 社区版单区 99.9%、多区 99.95%。云厂商 SLA 普遍用「连接层可用 + 1 分钟粒度」这种宽口径便于自动统计,而内部 SLO 应该用更严的「查询成功率」口径,并且内部 SLO 要比对外 SLA 更严、留缓冲。

Error Budget = 1 − SLO,99.9% 约等于每月 43 分钟,99.99% 约 4.3 分钟。告警用多窗口多燃烧率兼顾误报和检测延迟。

一个可以主动带出的私货(来自你自己的 latency 定位经验):t-digest 类分位估计对 P100 极端长尾失明,定 P999 时要注意统计方法本身的误差。

**Q:延迟 SLO 你怎么落到这个场景?**

分冷热双 SLO:`P99(cache hit) < 10s` 且 `P99(cache miss/cold) < 60s`。业界锚点:Doris 官方 observability 案例 MiniMax 10 亿条日志 2 秒内返回;StarRocks 存算分离在京东物流 cache 命中 P95/P99 < 10s、miss < 1 分钟。存算分离下冷查询延迟是固有代价,所以延迟 SLO 必须分冷热,不能定一个全局阈值。

### 3.C 调优参数(面试官在这里追得最狠)

**Q:你这张表分了多少桶?为什么?(可能直接问「51 亿行为什么只有 16 个 bucket」)**

这是最可能被追的问题,先讲定容原则再讲你的取值。官方 [Data Bucketing](https://doris.apache.org/docs/3.x/table-design/data-partitioning/data-bucketing/) 的原则:单个 tablet 保持在 1–10GB(3.0 放宽到 1–20GB,Unique Key 表仍建议 <10GB,这个数字不同版本有冲突,主动点破更显专业)。分桶数两条硬约束:最好是 BE 节点数的整数倍(数据均匀)、单分区一般不超过 128。按分区数据量:<1GB 用 1 桶,1–10GB 用 10 桶,10–200GB 用 10–20 桶,超 200GB 先分区。

你的取值可以这样自洽:表用了 `AUTO PARTITION BY RANGE day` 按天分区、`DISTRIBUTED BY HASH(user_id) BUCKETS 16`。关键论证是,16 桶是针对单个日分区的,不是针对 51 亿行全表。只要每个日分区落在 10–200GB 这个区间,16 桶正好卡在官方建议的 10–20 桶范围里,且是 BE 数的整数倍。用 user_id 做分桶键是因为它是高基数、查询常用的过滤/join 键,能避免数据倾斜和扫全表。如果面试官说「那要是某天数据暴涨呢」,答案是 AUTO PARTITION 保证分区粒度可控、单分区不会无限膨胀,必要时可以配 AUTO BUCKET 让桶数按前 7 个分区的 EMA 自动调整。

顺带秀一下 AUTO BUCKET(1.2.2 起)的算法:数据侧桶数 N 用 `estimate_partition_size/5`(按 5:1 压缩比,每 GB 一桶),容量侧 M = BE 数 × (盘容量/50GB) × 盘数,最终取 `min(M, N, 128)`,`estimate_partition_size` 默认 10GB。

**Q:rowset 和 segment 是什么关系?和你说的内存问题怎么联系?**

一次导入,每个 tablet 生成一个 rowset,一个 rowset 含 0 到 n 个 segment,每个 segment 是磁盘上一个有序文件,rowset 用版本区间标识。两个上限要记住:单 rowset 的 segment 数超过 `max_segment_num_per_rowset`(默认 200)报 -238;单 tablet 版本数超过 `max_tablet_version_num`(默认 2000)报 -235。这两个都和「导入太快、compaction 跟不上」直接相关。

**Q:碎片整理(compaction)怎么调?导入期怎么防止 -235?**

先讲清 compaction score:它衡量 tablet 内互相重叠的 rowset 数量,约等于查询时的归并路数,健康值高并发下稳定在 50 左右。score 飙升就是 compaction 跟不上写入。

`max_tablet_version_num`(默认 2000)是 -235 TOO_MANY_VERSION 的直接触发线。因果链是:导入频率 > compaction 速度,rowset/version 持续堆积,撞到 2000 就拒写报 -235。标准答法是「-235 是果,compaction score 上涨是因」。

组合拳:治本是攒批、降导入频率、用 Group Commit,减少 rowset 生成速率;治标是把 `max_tablet_version_num` 调大(官方建议不超过 5000);提 compaction 并行靠 `max_cumu_compaction_threads`(默认 -1 即每盘 1 线程,显式调到 8/10)和 `compaction_task_num_per_disk`(默认 4);全程保持 `enable_vertical_compaction`(默认开,按列组合并,内存只有原来的 1/10、速率提升约 15%,对宽表尤其关键)和 `enable_segcompaction` 开启。-238 的根因常常绕回分桶:建表桶数太小或数据倾斜,所以先查分桶再调 segment 上限。

参数速查:

| 参数 | 默认 | 作用 |
|---|---|---|
| `max_tablet_version_num` | 2000 | 单 tablet 版本上限,触发 -235,可调至 ≤5000 |
| `max_segment_num_per_rowset` | 200 | 单 rowset segment 上限,触发 -238 |
| `max_cumu_compaction_threads` | -1(每盘1) | cumulative compaction 线程,提速首选 |
| `compaction_task_num_per_disk` | 4(HDD)/8(SSD) | 每盘并行 compaction 任务 |
| `cumulative_compaction_max_deltas` | 1000 | 单次 cumu 最多合并 rowset 数(旧名 `max_cumulative_compaction_num_singleton_deltas`) |
| `enable_vertical_compaction` | true | 按列组合并,宽表内存降 90% |
| `write_buffer_size` | 200MB | memtable flush 阈值,调大减少小文件 |
| `flush_thread_num_per_store` | 2 | 每盘 memtable 落盘线程 |
| `load_process_max_memory_limit_percent` | 50% | 单节点导入内存天花板 |

一个术语防坑:`max_cumulative_compaction_num_singleton_deltas` 是旧参数名,新版本改叫 `cumulative_compaction_max_deltas`,别在新集群上找旧名字。

**Q:你在导入时具体怎么控内存的?**

这是你最有货的地方,讲真实配置:Doris 侧 `max_file_scanners_concurrency=1`、`parallel_pipeline_task_num=1`、`enable_spill=true`、`exec_mem_limit=64G`,内存 watchdog 软阈值约 78 GiB、硬阈值约 90 GiB,跑在 110Gi 的 BE 上,超硬阈值就 kill 所有 in-flight 导入连接做干净 abort、超软阈值就停止启动新导入。为什么把 scanner 并发降到 1:因为 Parquet 向量化 column reader 的内存不受 `exec_mem_limit` 约束,列一多就失控。CH 导出侧 `output_format_parquet_use_custom_encoder=0`(避免整对象缓冲导致 OOM)、`CH_ROWGROUP=65536`。还有一个生产事故可以讲:大约 1.7B 行时,MoW 的 delete-bitmap 加宽表 compaction 让每个 load 在约 40 GiB baseline 上再加约 25 GiB,2 并发反复冲破 90 GiB 硬顶并在某个月份 livelock,于是把并发钳到 1(baseline 加 1 个 load 约 65 GiB,安全)。吞吐是 export-paced 的,1 并发仍跟得上。

### 3.D 架构与选型判断(拉开 level 的地方)

**Q:为什么是 Doris 存算分离,不是继续用 ClickHouse 或上 CH Cloud?**

这是最能体现判断力的问题,按 What → Why → What if 展开,一定要端出没选的方案和边界。

存算分离本身不构成换 Doris 的理由,因为它是 2026 现代 OLAP 的默认架构,CH Cloud(SharedMergeTree)、StarRocks、Snowflake 全是。所以真正的分水岭不是 CH vs Doris,是「开源自建 vs 云托管/存算分离」。

换 Doris 的正当理由是这个组合:开源无云锁定 + 高并发点查(YCSB 16C64G 单机 30000+ QPS/节点)+ 多表 JOIN(CH 复杂 JOIN 弱,TPC-DS 约一半跑不出)+ 实时 UPSERT(Unique Key + Merge-on-Write)。

诚实的边界(这句话最加分):如果核心痛点只是「自建 CH 扩容太重、要弹性」,那最小动作其实是迁到 ClickHouse Cloud 拿 SharedMergeTree 弹性、SQL 零改写,而不是跨引擎迁 Doris。我们选 Doris 是因为同时要那个组合能力,不是单纯图弹性。而且要清醒:Doris 4.0 的弹性是分钟级不是秒级,新加节点因本地 cache 为空要 warmup 预热才达稳态,缓存部分命中约降 10%、完全 miss 约降 35%。

**Q:AI 负载对数据库到底提了什么新要求?存算分离能解决吗?**

这题答得好直接体现你不是只会调库、而是理解负载模式变迁。业界把 agent 驱动的分析称为十年来数据库负载模式的最大变迁:一个 prompt 炸裂成一串并发查询,分析负载开始长得像面向客户的生产流量,高并发、低延迟、交互式。

关键判断:存算分离是必要条件但远不充分。AI 突发负载真正的三个命门是,第一计费/唤醒粒度(冷启动超 1 分钟加 60 秒最小计费,一个 agent 每天打 1 万条 2 秒的短查询,最高 30 倍成本惩罚,Together AI 因此弃用 CH);第二多租户 blast radius 隔离(一个租户失控的 agent 查询不能拖垮整仓,要 compute group 级隔离);第三对象存储冷查询延迟。存算分离只解决了算力能独立伸缩,这三点一个都不自动解决,所以我在方案里单独做了隔离和缓存预热设计。

**Q:Iceberg 在你这套里扮演什么角色?存算分离的内表和 Iceberg 外表都在 S3,有什么区别?**

先讲清一个最容易被追的区分点:两者都在 S3 是表象,抽象层完全不同。Doris 存算分离内表的存储层叫 Storage Vault,是 Doris 自有格式(Segment + Rowset),元数据由 Meta Service 加 FoundationDB 自管,只有 Doris 能写,BE 本地 cache 热数据。Iceberg 外表是开放格式(Parquet/ORC + manifest/snapshot),元数据在外部 catalog(HMS/REST/Glue),Doris 通过 Multi-Catalog 只做元数据代理、不落地数据,任意引擎(Spark/Flink/Trino/Doris)都能写。一句话:内表是 Doris 独占的封闭格式换性能和事务,外表是开放共享格式换中立和跨引擎。

Iceberg 在迁移中的价值:作为跨引擎中立的 single source of truth,Spark 做 ETL、Flink 做实时写、Doris/Trino 做查询共享同一份表,写入通过 catalog API commit 保证其他引擎立即可见,这是 CH 私有 MergeTree 格式做不到的。典型冷热分层:热数据(高频、需实时更新)进 Doris 内表,冷数据/历史全量留 Iceberg on S3 用 external catalog 直查、不占内表存储,迁移过渡期可以先外表查通再对热表 `INSERT INTO SELECT` 提到内表。

版本防守(容易答错):读 Iceberg 外表 1.2 起;INSERT/CTAS 写入 2.1 起;行级 DML(UPDATE/DELETE/MERGE INTO)要 4.1.0 且 format-version ≥ 2。这个口径按 4.1.0 答最稳,因为不同官方页面对行级 DML 起始版本表述不一致。

**Q:存算分离下 compaction 和存算一体有什么不一样?**

存算一体每个 BE 独立跑 compaction、要处理 3 个副本各自的数据。存算分离下 compaction 由 compute node 执行、只需处理共享存储上的单副本、结果写回 S3、由 Meta Service 协调,资源消耗和副本数成正比所以大幅下降。这也是成本降幅的来源之一:官方口径 100TB 在线数据从三副本约 3.7 万美元/月降到单副本约 2.2 万(约 40%),历史冷数据可降 90%+。一个差异点可以加分:存算分离下 MoW 表更新 delete-bitmap 要抢分布式锁 `delete_bitmap_update_lock`,导入、compaction、schema change 竞争同一把锁,高并发导入下容易长等待,这正是你在 1.7B 行 livelock 事故里踩到的机制。

---

## 第四部分:减分项自查与面试节奏

调研里反复出现的红旗,逐条对照:

只讲执行不讲结果、数字含糊。对策:每个数字都能拆。你的招牌数字用 51.7 亿行 × 3727 列(可复现),别用拆不开的总量口径。

疯狂罗列技术名词却说不清为什么用。对策:每个技术选择都配一句「为什么用它、没选什么、边界在哪」。你的 Doris 选型、切片策略、scanner 并发降到 1,都要能答出 why。

边界不清,分不清「你做的」和「团队做的」。对策:讲的时候明确说「我 decided」而非「我们做了」。ownership 信号是 staff 级的核心评估点,面试官specifically 在听是不是你个人做的决策。

选型只说「A 比 B 好」。对策:一定端出没选的方案加数据对比加失效边界。模板是「Y 在数据规模 N 之下确实更好,但我们已经超过 Y 的 sweet spot」。你的「如果只图弹性其实该上 CH Cloud」就是教科书级的边界表达。

影响面不够。对策:主动点出这个项目沉淀成了可复用 skill 和监控 SLA 规范,不是一次性交付,并且它的起因是公司级的 AI 负载问题,影响面到业务线而非只是一张表。

节奏建议:每个大块先准备一个 1 分钟的「结论一句、展开两点、诚实边界一句」口述版。诚实边界指主动说清哪里只做到 preprod、哪里只读过文档没上生产、哪个数字是官方口径需自测。这种主动暴露边界的表达在面经里是明确加分项,比假装什么都做过强。

一个可以主动准备的「What if 全失败」问题:如果迁移中途发现 Doris 存算分离在你们的负载下扛不住,plan B 是什么。答案框架:先降级(热数据留 Doris 内表、冷数据退回 Iceberg 外表直查减压)、再重定义问题(区分是弹性不够还是 blast radius 没隔离好,分别对应加 compute group 还是上 serverless 方案)。

---

## 附录 A:关键数字与参数速查卡

项目规模:`sofi.event_result`,51.7 亿行 × 3727 列超宽表,CH → Doris native,preprod,AWS us-west-2,项目代号 CRE-6630。

验证过的性能:单个 25.9 GiB part 约 90K 行/秒导入,峰值约 18 GiB/BE,零崩溃(2026-07-12)。415M 行月份 11 秒扫出切片边界。

生产事故:约 1.7B 行时 MoW delete-bitmap + 宽表 compaction 使每 load 在 40 GiB baseline 上加 25 GiB,2 并发冲破 90 GiB 硬顶 livelock,钳到 1 并发解决。

关键配置:导入 `max_file_scanners_concurrency=1`、`parallel_pipeline_task_num=1`、`exec_mem_limit=64G`、`enable_spill=true`、watchdog 软 78/硬 90 GiB(BE 110Gi);导出 `custom_encoder=0`、`CH_ROWGROUP=65536`、`SLICE_ROWS=7,000,000`;目标表 Unique Key + Merge-on-Write、`DISTRIBUTED BY HASH(user_id) BUCKETS 16`、`AUTO PARTITION BY RANGE day`。

错误码:-235 = tablet 版本数超 `max_tablet_version_num`(2000,可调 ≤5000);-238 = 单 rowset segment 超 `max_segment_num_per_rowset`(200)。健康 compaction score ~50。

存算分离成本:存储最高降 90%,100TB 在线数据三副本约 40% 降;弹性分钟级非秒级,cache 部分命中降 10%、完全 miss 降 35%。

高并发点查:YCSB 16C64G 单机 30000+ QPS/节点。CH→Doris SQL 自动转换约 98%(sql_dialect=clickhouse)。

## 附录 B:核心来源

内部:`rules/skills/sofi_ch_to_doris_migration/`(项目一手事实)、`contexts/survey_sessions/clickhouse_vs_doris_storage_compute_ai_load_survey_20260716.md`(选型判断力弹药)。

监控与调优官方:[Monitor Metrics](https://doris.apache.org/docs/3.x/admin-manual/maint-monitor/metrics/)、[BE Config](https://doris.apache.org/docs/3.x/admin-manual/config/be-config/)、[Data Bucketing](https://doris.apache.org/docs/3.x/table-design/data-partitioning/data-bucketing/)、[Compaction Principles](https://doris.apache.org/docs/dev/admin-manual/trouble-shooting/compaction-principles/)、[Load FAQ](https://doris.apache.org/docs/3.x/faq/load-faq/)、[SelectDB 分区分桶](https://www.selectdb.com/blog/44)、[SelectDB Compaction 优化](https://www.selectdb.com/blog/47)。

SLO 方法论:[Google SRE Book](https://sre.google/sre-book/service-level-objectives/)、[AWS Redshift SLA](https://aws.amazon.com/redshift/sla/)、[腾讯云 SLA/SLO 实践](https://cloud.tencent.com/developer/article/2615042)。

架构与 Iceberg:[Doris 存算分离部署/Storage Vault](https://doris.apache.org/docs/4.x/install/deploy-manually/separating-storage-compute-deploy-manually/)、[Iceberg Catalog](https://doris.apache.org/docs/dev/lakehouse/catalogs/iceberg-catalog/)、[SelectDB 存算分离](https://www.selectdb.com/blog/1380)、[快手 CH→Doris](https://www.selectdb.com/blog/1004)、[MotherDuck AI 负载](https://motherduck.com/learn/best-analytics-db-llm-ai-agents)。

面试信号:[interviewing.io Meta 评估](https://interviewing.io/blog/how-software-engineering-behavioral-interviews-are-evaluated-meta)、[OA VO Service 项目深挖](https://oavoservice.com/articles/openai-interview-breakdown-four-interviewer-styles-project-deep-dive)、[Eng Leadership CARL](https://newsletter.eng-leadership.com/p/how-to-nail-big-tech-behavioral-interviews)、[木鸟杂记 存储面经](https://www.qtmuniao.com/2021/04/17/storage-interview/)、[aylei/interview](https://github.com/aylei/interview)。
