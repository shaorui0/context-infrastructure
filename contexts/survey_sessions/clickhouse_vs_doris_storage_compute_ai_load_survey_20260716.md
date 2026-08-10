# ClickHouse vs Doris 存算分离:AI 驱动查询负载下的 OLAP 选型调研

> 调研日期:2026-07-16
> 场景:SaaS 企业接入 AI 后,客户经由 AI(agent / text-to-SQL)发起大量、突发、不可预测的查询,全部打到底层 OLAP。现用 ClickHouse(列存),扩展靠"加实例",不够动态。问:换成 Doris 这类存算分离架构,迁移是否会越来越高效?以及 Doris 的适用场景 / 为何 ClickHouse 应用更广。
> 方法:4 个维度 + 1 个场景维度并行调研,交叉验证。所有引用保留 URL 与原文摘录。

---

## 核心结论(TL;DR)

**你的直觉方向对,但命题里藏着三个会导致错误决策的假设,必须先拆掉:**

1. **"ClickHouse = 存算一体、不能动态扩展"——只对开源自建版成立,对 ClickHouse Cloud 已经过时。** Cloud 版早已全面切到 SharedMergeTree(无状态 compute + 对象存储),加副本秒级、无需搬数据。但关键在于:**SharedMergeTree 闭源、Cloud 独占,官方明确不进开源**。所以真正的分水岭不是"ClickHouse vs Doris",而是"开源自建 vs 云托管/存算分离"。

2. **"存算分离是 Doris 的独门武器"——错。** 2026 年存算分离已是现代 OLAP 的**默认架构**:ClickHouse Cloud、StarRocks、Snowflake、Databricks 全都是。Doris 的真正差异化是**"开源就自带存算分离(无云厂商锁定)+ MySQL 协议 + 多表 JOIN + 实时 UPSERT + 原生高并发点查"**,而不是"存算分离"这个词本身。

3. **"AI 突发负载靠存算分离就能解决"——存算分离是必要条件,但远不充分。** 对 AI agent 打出的海量短查询,真正的命门是**①计费/唤醒粒度(冷启动 >1 分钟 + 60 秒最小计费 = 最高 30x 成本惩罚)、②多租户 blast radius 隔离、③对象存储冷查询延迟**。存算分离只解决了"算力能不能独立伸缩",没解决"伸缩够不够快、够不够便宜、会不会互相拖垮"。

**一句话回答:** 换 Doris 在"开源可弹性 + 高并发点查 + 多表 JOIN + 实时更新"这个组合上确有真实收益,且 CH→Doris 迁移工具链已成熟;但如果你的核心痛点是"AI 突发负载下的动态弹性",那么把 ClickHouse 自建迁到 **ClickHouse Cloud** 可能是更小的动作就能拿到同样的存算分离弹性,而 Doris 4.0 的弹性也只是**"分钟级"而非"秒级"**,并且新加节点要靠 cache warmup 预热才不抖。选型应按**负载画像**(见文末决策表)而不是"谁更先进"来定。

---

## 一、ClickHouse 扩展性:命题对开源成立,对 Cloud 已过时

### 1.1 开源自建:加 shard 确实是"重"操作

ClickHouse 经典架构是 shared-nothing + 列存,分片(shard)扩容量、副本(replica)保可用。**痛点在于加 shard 必须手动 reshard + rebalance,而 ClickHouse 不自动 rebalance:**

> "In ClickHouse, the scaling operation is made of two parts. You first need to **reshard** (adding new shards), then **rebalance**... The issue we faced was that **ClickHouse doesn't automatically rebalance data** in the cluster when we add new shards."
> — [Contentsquare Engineering: How we scale out our ClickHouse cluster](https://engineering.contentsquare.com/2022/scaling-out-clickhouse-cluster)

ClickHouse 贡献者本人也承认弹性故事落后:

> "**ClickHouse elasticity story lags behind. It is hard to scale a cluster (add more shards, remove shards) after it was created**... there is no coordination between different cluster shards. There is no centralized metadata store."
> — [nvartolomei: Rebalancing data in shared-nothing distributed systems](https://nvartolomei.com/rebalancing-data-shared-nothing)

补充:加 **replica** 很轻,重的永远是加 **shard**(改变数据 locality,要动集群配置和表结构)。所以"扩展不动态"这个说法对开源自建**基本成立**。

### 1.2 ClickHouse Cloud:SharedMergeTree 已让"存算分离弹性"成立(但闭源)

**转折点是 SharedMergeTree —— ReplicatedMergeTree 的云原生替代,数据放对象存储、副本之间不通信、可无 shard 动态扩到数百副本:**

> "The SharedMergeTree table engine family is a **cloud-native replacement of the ReplicatedMergeTree**... **SharedMergeTree doesn't require replicas to communicate with each other**... metadata doesn't need to be replicated as your service scales up and down... SharedMergeTree allows for **hundreds of replicas for each table, making it possible to dynamically scale without shards**."
> — [ClickHouse Docs: SharedMergeTree table engine](https://clickhouse.com/docs/cloud/reference/shared-merge-tree)

> "All new services have used SharedMergeTree... **all existing services have been migrated too.**"
> — [ClickHouse Blog: No more disks — stateless compute in ClickHouse Cloud](https://clickhouse.com/blog/clickhouse-cloud-stateless-compute)

**但关键鸿沟:SharedMergeTree 闭源,不进开源。**

> "ClickHouse Inc. made their own solution to this with the **SharedMergeTree storage engine, which is not going to be released in open source.**"
> — [GitHub Issue #54644: MergeTree over S3 improvements (RFC)](https://github.com/ClickHouse/ClickHouse/issues/54644)

官方明确:开源自建**可以**用 S3-backed MergeTree 近似存算分离,但更复杂,并直接推荐用 Cloud:

> "implementing and managing a **separation of storage and compute architecture is more complicated** compared to standard ClickHouse deployments... we recommend using ClickHouse Cloud."
> — [ClickHouse Docs: Separation of storage and compute](https://clickhouse.com/docs/guides/separation-storage-compute)

弹性现状对照(自建 vs Cloud):Cloud 有 autoscaling(**纵向自动、横向偏配置驱动**),自建几乎没有真正弹性、靠手动:

> "Auto-scaling | Self-Hosted: **Manual** | ClickHouse Cloud: **Tier-dependent (automatic vertical scaling; horizontal scaling is manual or enabled by configuration)**"
> — [OneUptime: ClickHouse Cloud vs Self-Hosted](https://oneuptime.com/blog/post/2026-01-21-clickhouse-cloud-vs-self-hosted/view)

### 1.3 高并发短板:无硬性上限,但重查询高并发下延迟劣化

ClickHouse 官方反驳"100 并发上限"是误解(`max_concurrent_queries` 默认 0=无限),提并发的手段是"加副本":

> "**Is ClickHouse limited to 100 concurrent queries? No.** ...ClickHouse has **no fixed architectural ceiling for concurrent queries**." — [ClickHouse: concurrency sizing](https://clickhouse.com/resources/engineering/high-concurrency-sizing-user-analytics)
> "There is a **limit of 1000 concurrent queries per replica**... you can **easily increase concurrency by adding more replicas**." — [ClickHouse Cloud architecture](https://clickhouse.com/docs/cloud/reference/architecture)

**但真实短板是:每个查询默认吃满多核,并发上来后延迟急剧劣化。** 实测 30 并发下单查询从 383ms 劣化到 10s([GitHub Discussion #85925](https://github.com/ClickHouse/ClickHouse/discussions/85925));Tinybird 花一年修锁争用才把 ~200 QPS 提到 ~1000 QPS([Tinybird: lock contention](https://www.tinybird.co/blog/clickhouse-lock-contention))。它是**为高吞吐分析、不是为高并发点查**设计的。

---

## 二、Doris 存算分离 + 4.0 生产成熟度

### 2.1 架构:存算分离是 3.0 的能力,不是 4.0 的头条

三层架构:FE(SQL 层元数据)+ **Meta Service**(数据层元数据,无状态,底层依赖 **FoundationDB**)+ 无状态 BE(compute)+ 共享存储(S3/HDFS),BE 用本地 SSD 做 file cache:

> "**Introduced in version 3.0**, this architecture fully separates the compute layer from the storage layer... BE nodes are stateless... use a local SSD to cache hot data (LRU)."
> — [Doris System Architecture](https://doris.apache.org/docs/dev/features-architecture/system-architecture)

相比 2.x 存算一体(3 副本),存算分离单副本 + 共享存储,**存储成本最高降 90%**:

> "Compared to the compute-storage coupled mode with three data replicas, the storage cost can be reduced by up to **90%**."
> — [Doris Release note 3.0.0](https://doris.apache.org/blog/release-note-3.0.0)

血统提示:这套存算分离其实是 **VeloDB(商业公司,Doris 主要贡献者)把 VeloDB Cloud 贡献回社区**的成果。

### 2.2 Doris 4.0:时间线、GA、头条特性

**关键事实:**
- **4.0.0 于 2025-10-14 开源发布**;最新稳定 patch **4.0.7(2026-07-12)**;另有更新的 **4.1 线(4.1.0 于 2026-04-21,4.1.2 于 2026-06-17)**。([Doris Core Release Notes](https://doris.apache.org/releases/core))
- **开源 4.0.0 即正式版,但厂商背书的"生产可用"要到 2026-Q1**:VeloDB 直到 **2026-03-31** 才宣布 4.0 GA,措辞是"经开源社区几个月反馈 + VeloDB 硬化(4.0.0→4.0.4)"。([VeloDB Doris 4.0 GA](https://www.velodb.io/events/doris4-ga-velodb-20260331))

**4.0 的头条不是存算分离,而是"AI/搜索一体化引擎"(HSAP):**

> "focused on improving four main areas: 1) new AI capabilities **vector search, and AI functions**, 2) stronger **full-text search**, 3) better ETL/ELT processing, and 4) performance optimization with TopN lazy materialization and SQL cache."
> — [Release 4.0.0](https://doris.apache.org/releases/v4.0/release-4.0.0)

其中与本场景相关的:HNSW 向量索引 GA、`SEARCH()` 全文检索(对齐 ES Query String 语法,降低从 ES/CH 迁移日志检索的改写成本)、SQL Cache 把某查询解析从 **400ms 降到 2ms**(利好高并发)、Spill-to-disk(解锁大 ETL)。

### 2.3 存算分离生产成熟度:能上,但要钉在最新 patch

**正面证据:**
- 存算分离整体已有 **2000+ 企业**生产采用([Release 4.1.0](https://doris.apache.org/releases/v4.1/release-4.1.0));
- 4.0.6 官方定位为稳定性维护版,且 cloud 模式收益最大:
  > "It focuses on stability and operational experience. All 4.0.x users are advised to upgrade, and **users running the compute-storage decoupled (cloud) mode benefit the most**." — [Release 4.0.6](https://doris.apache.org/releases/v4.0/release-4.0.6)

**负面证据(4.0.x 密集修 cloud/存算分离缺陷,说明早期版本坑不少):**
- 4.0.5 修 **file cache 并发崩溃**、segment corruption 不触发 cache retry;([Release 4.0.5](https://doris.apache.org/releases/v4.0/release-4.0.5))
- 4.0.6 修 **Recycler OOM**、动态分区与建 MV 的竞态、内部事务态 `KV_TXN_MAYBE_COMMITTED` 泄漏给客户端、cloud 下 meta service 日志不打印;并**把 cloud 模式 `enable_strict_consistency_dml` 默认关掉**(为性能牺牲严格一致性,属破坏性变更,升级后依赖强一致 DML 的要手动开回);([4.0.6 Release Notes](https://github.com/apache/doris/issues/64065))
- 4.0.7 仍在修数据丢失/挂起类问题 + 调整对象存储 SlowDown/429 重试。([4.0.7 Release Notes](https://github.com/apache/doris/issues/65399))

**成熟度判断:**
- **存算分离本身**(3.0 引入、3.x 打磨、2000+ 企业用)**相对成熟**,可以上生产,但**务必钉在 4.0.7,不要用 4.0.0/4.0.1**——4.0.5→4.0.7 的修复清单说明早期 4.0.x 的 cloud 模式仍在收敛。
- **4.1 线**(含"百万级 tablet 分钟级扩缩容")弹性更强但发布更晚、patch 更少,属**观望/预发验证**档,不建议直接压核心生产。
- 稳妥策略:关键业务用 **3.0 稳定线或 4.0.7** 跑存算分离;要 4.0 的 AI/检索能力上 4.0.7;4.1 先在非核心链路验证。

### 2.4 弹性是"分钟级"不是"秒级",且有 warmup 代价

官方唯一的弹性硬数字在 4.1,措辞是"分钟级",**没有任何"秒级 autoscaling"承诺**:

> "it can quickly complete capacity expansion and contraction of a **million-scale within minutes**. Balance scheduling no longer depends on the global number of tablets."
> — [Release 4.1.0](https://doris.apache.org/releases/v4.1/release-4.1.0)

而且新加的 compute 节点因本地 cache 为空,首查要回源对象存储,需 **cache warmup** 预热才达稳态——"加节点即刻满速"不成立。缓存命中三档(官方自测):

> "When the cache is **partially hit**... about **10% lower** than coupled mode. When the cache is **completely missed**... performance loss is **around 35%**."
> — [Doris Release note 3.0.0](https://doris.apache.org/blog/release-note-3.0.0)

对象存储三大固有问题(高延迟 / QPS 与带宽上限 / 按请求计费)+ 多 compute group 下 cache miss 抖动,是存算分离的主要运维负担,需配 cache warmup + 单查询缓存配额(4.0.3+)。运维复杂度也上升:decoupled 模式最少要 3 台跑 FoundationDB + Meta Service + Recycler。

### 2.5 高并发点查:Doris 有明确数字优势

高并发点查栈(Unique Key + Merge-on-Write + row store + short-circuit + PreparedStatement + row cache)在 YCSB / 16C64G 单机达 **30,000+ QPS/节点**,平均延迟降 96%:

> "reaches **30,000+ QPS per node** on YCSB on a 16-core / 64GB machine, with average latency cut by 96%." — [Prepared Statement](https://doris.apache.org/docs/dev/key-features/prepared-statement)

⚠️ 注意这是**点查专属**(不是通用分析),且存算分离下点查还多一次到 meta service 的 RPC,高 QPS 下易成瓶颈(官方建议 `enable_snapshot_point_query=false`,牺牲可见性换性能)。

---

## 三、AI 驱动查询负载:真正的命门不只是存算分离

**这是本次调研最有价值、也最能修正原始命题的维度。**

### 3.1 业界共识:agent 分析是"十年来最大的负载模式变迁"

一个自然语言 prompt 会炸裂成一串并发查询,分析负载开始长得像面向客户的生产流量:

> "One prompt turns into a burst of concurrent queries. **Analyst workloads start to resemble customer-facing production traffic: high concurrency, low latency, interactive response times.**"
> "**The move from human-driven to agent-driven analytics may be the biggest shift in database workload patterns in the last decade.**"
> — [The New Stack: The hidden reason your AI assistant feels so sluggish](https://thenewstack.io/why-ai-feels-sluggish)

学术界把这种负载正式定义为三特征:**iterative(多步循环)、concurrent(突发高并发)、shareable(可跨迭代复用计算)**:

> "**Concurrent.** An AI agent often issues AI×DB workloads in parallel... resulting in **bursty and high-rate arrivals at the database engine.**"
> — [arXiv: Towards Effective Orchestration of AI × DB Workloads](https://arxiv.org/html/2603.03772)

### 3.2 关键反证:存算分离 ≠ 应对 AI 负载的银弹

**最重要的一条(直接冲击"换存算分离就行"的假设):对不可预测的 agentic 突发流量,ClickHouse Cloud 因冷启动 >1 分钟被迫 24/7 常驻,反而变成成本问题——Together AI 因此弃用 ClickHouse:**

> "ClickHouse Cloud... **Its startup time exceeds a minute, so production deployments run 24/7 to dodge cold starts. For unpredictable agentic traffic, that means paying for idle compute around the clock.**" —— Together AI 数据工程总监 Pablo Ferrari 称 "agent-driven queries would create a serious cost problem",最终选 MotherDuck 而非 Redshift/Athena/ClickHouse。
> "That isolation also caps the **blast radius. A runaway query from one agent can't drain the shared budget or take down the warehouse.**"
> — [MotherDuck: The fastest OLAP databases compared](https://motherduck.com/learn/fastest-olap-databases-compared)

**计费粒度陷阱(AI 打海量短查询的场景最致命):**

> "For an agent firing **10,000 short queries per day at 2 seconds each, a 60-second minimum can represent up to a 30x cost multiplier**."
> — [MotherDuck: Best Analytics Database for LLM & AI Agents (2026)](https://motherduck.com/learn/best-analytics-db-llm-ai-agents)

**所以 AI 突发负载的三个真正命门:**
1. **计费/唤醒粒度** —— 冷启动 >1 分钟 + 60 秒最小计费 → 要么被迫常驻(付闲置费),要么被 30x 乘数惩罚。按秒计费 + 快速唤醒才是刚需。
2. **多租户 blast radius 隔离** —— SaaS 场景下"一个租户失控的 agent 查询不能拖垮整仓",独立 compute group / warehouse 是刚需。
3. **对象存储冷查询延迟** —— 存算分离引入的固有代价,需本地缓存 + region 内 co-location + 尾延迟工程补偿。

存算分离只解决了"算力能独立伸缩",上面三点它一个都不自动解决。

### 3.3 成本模型:存算一体"为峰值常驻"的浪费是真实的

存算分离降本的量化案例(方向可信,数字来自厂商需打折):
- StarRocks:月末突发 QPS 场景,存算一体要按峰值常驻 14 节点,存算分离只在峰值周部署 14 节点、平时 3 节点 → **等效 5.75 节点、算力效率提升 2.43x**;冷数据场景"硬件成本降 78%"([StarRocks blog](https://www.starrocks.io/blog/separation-of-storage-and-compute-an-architecture-that-cuts-costs-and-enhances-efficiency/index.html))。
- Snowflake 生产数据(Snowset 论文):弹性用户算力节点数生命周期内可变动**两个数量级**,但平均利用率很低(CPU ~51%、内存 ~19%)——这正是"为峰值常驻"的浪费([Cornell Snowset](https://www.cs.cornell.edu/~ragarwal/pubs/snowset.pdf))。

### 3.4 趋势:存算分离已是 2026 现代 OLAP 的默认架构

> "**Most modern OLAP databases now separate storage and compute by default** rather than tightly coupling them."
> — [Tinybird: OLAP databases in 2026](https://www.tinybird.co/blog/best-database-for-olap)

ClickHouse Cloud(Idler/Scaler 做 serverless 弹性 + compute-compute 分离)、Doris 3.0+、StarRocks v3.0 shared-data、Snowflake、Databricks Lakebase(专为 agent 波动流量做 ephemeral compute)全都走这条路。**换言之,"要存算分离"不构成"必须换 Doris"的理由。**

---

## 四、迁移可行性与成本:ClickHouse → Doris

**结论:工具链成熟,但案例几乎全是中国大厂 + VeloDB/官方来源,有立场偏差。**

**迁移工具:Doris SQL Convertor(2.1+)** —— `set sql_dialect="clickhouse"` 即可跑 CH 方言,实测 **98% 的 ClickHouse SQL 自动转换成功**([velodb.io](https://www.velodb.io/blog/sql-convertor-easy-migration-presto-trino))。

**真实案例:**
| 案例 | 规模/结果 | 来源 |
|---|---|---|
| 腾讯音乐 TME | 万亿日志/日(峰值 6GB/s),50 台 2PB;两周并行验证一致性后完全替换 | [velodb.io](https://www.velodb.io/blog/clickhouse-apache-doris-powering-trillion-log-scale) |
| 某电信巨头 | 单表 13PB / 534 万亿行,117 节点;压测中解决批量写失败/Compaction 过载/导入错误,省 28% 入库服务器 | [velodb.io](https://www.velodb.io/blog/leading-telecommunication-company-replaced-clickhouse-apache-doris) |
| 快手 Kwai | 迁 Doris 升级 lakehouse,免数据导入直查数据湖 | [doris.apache.org](https://doris.apache.org/docs/2.1/gettingStarted/alternatives/alternative-to-clickhouse) |

**主要人工成本:** SQL 方言改写(CH `COUNTIF`→`SUM(CASE WHEN)`、`uniq()`→`APPROX_COUNT_DISTINCT()`、`quantile()`→`PERCENTILE_APPROX()`;子查询必须加别名)、建表模型重设计(分区/分桶/Key 类型、动态分区需预设历史分区数否则报 "No Partition")、上游写入程序(Flink 等)适配、入库阶段 Compaction/批量写调优。典型周期:改写 + 双跑约 2 周校验一致性 → 切换。

**诚实的信息空白:未找到任何"从 Doris 迁回 ClickHouse"的具名生产案例。** 这可能因为迁移案例的话语权集中在 VeloDB/Doris 侧,而非 Doris 一定不会被迁回。

---

## 五、采用度:为什么 ClickHouse 应用更广,Doris 的场景

### 5.1 硬指标:ClickHouse 全面领先(证据来自中立第三方,可信度高)

- **GitHub star:46,727 vs 15,154**(约 3 倍);近 30 天 523 vs 127([communium.ai](https://communium.ai/compare/apache-doris-vs-clickhouse-clickhouse))。
- **Docker 下载量:1 亿+**;2024 新增 star "more than doubling" Doris([pracdata.io《State of Open Source Real-Time OLAP 2025》](https://www.pracdata.io/p/state-of-open-source-read-time-olap-2025))。
- **资本 + 客户:** ClickHouse 2026-01 Series D、估值约 **$150 亿**、4000 客户;客户含 IBM/微软/Spotify/Cloudflare/eBay,AI 时代新增 **Anthropic、OpenAI、Tesla、LangChain**([sacra.com](https://sacra.com/c/clickhouse))。
- **200+ 集成**,主动绑定 OpenTelemetry / MCP / Iceberg 等开放标准。

### 5.2 为什么西方主流是 CH、Doris/StarRocks 主要在中国

**最硬的单一证据:地域集中度。**

> "StarRocks and Doris receiving substantial backing from major Chinese technology companies including Baidu, Tencent, and Alibaba. **Over 80% of contributions to these repositories originate from China.**"
> — [pracdata.io](https://www.pracdata.io/p/state-of-open-source-read-time-olap-2025)

加上先发优势(CH 2010 起步 2016 开源,Doris 2017-2018 才由百度开源)、单表分析极致性能口碑、单一二进制运维简单、云托管 + 资本驱动 GTM。

### 5.3 各自的场景(去偏见后的中立共识)

| 选 ClickHouse | 选 Doris / StarRocks |
|---|---|
| 单表海量扫描吞吐、append-only 日志/时序/事件分析 | 多表 JOIN(CH 复杂 JOIN 弱,TPC-DS 约 50% 跑不出) |
| 极致压缩率、单机极简运维、小团队 | 实时 UPSERT / 可变数据(Unique Key + Merge-on-Write) |
| 可观测性事实标准(ClickStack) | 高并发点查、面向客户 dashboard |
| 生态/集成成熟度护城河 | MySQL 协议低门槛、开源自带存算分离(无云锁定)、lakehouse 联邦 |

中立第三方([OneUptime](https://oneuptime.com/blog/post/2026-03-31-clickhouse-clickhouse-vs-apache-doris-for-real-time-analytics/view))原话:"**Doris wins for mutable data; ClickHouse wins for immutable append workloads.** For pure analytics workloads, ClickHouse typically wins on performance and operational simplicity."

---

## 六、交叉验证与可信度标注

| 结论 | 可信度 | 说明 |
|---|---|---|
| CH 采用度 / 生态 / 资本全面领先;Doris 80%+ 贡献来自中国 | **高** | pracdata / Contrary / Sacra / HN 等中立源多方一致 |
| 存算分离是 2026 OLAP 默认架构,非 Doris 独有 | **高** | Tinybird / ClickHouse / StarRocks / 学术论文一致 |
| CH 命题"扩展不动态"对开源成立、对 Cloud 过时(SharedMergeTree 闭源) | **高** | ClickHouse 官方文档 + 第三方 + GitHub RFC 三方印证 |
| AI 负载真正命门是计费粒度/冷启动/blast radius(非仅存算分离) | **高** | MotherDuck + Together AI 实名 + 学术论文;方向一致 |
| Doris 4.0 存算分离要钉 4.0.7、弹性是分钟级非秒级 | **高** | 官方 release notes 逐版本修复清单 + 4.1 明确"minutes" |
| Doris 性能倍数(2-10x、"CH fails 50% TPC-DS"、18-34x) | **低,方向可信** | 几乎全来自 Doris/VeloDB 官方;第三方仅在"CH 弱多表 JOIN/弱可变数据"定性方向上一致,**数字须自测** |
| CH→Doris 迁移"顺利/更省" | **中,有偏差** | 案例全为中国大厂 + VeloDB 来源;未找到 Doris→CH 迁回案例 |

---

## 七、给这个场景的选型建议

**先问三个问题,再决定动作:**

1. **你的痛点到底是"存算分离"还是"运维/成本/弹性"?**
   - 如果只是"自建 CH 扩容太重、要动态弹性",**最小动作是迁到 ClickHouse Cloud**(拿到 SharedMergeTree 弹性,SQL/生态零改写),而不是跨引擎迁 Doris。
   - 如果同时想要**开源无云锁定 + 多表 JOIN + 实时更新 + 高并发点查**,Doris 才有跨引擎迁移的正当理由。

2. **AI 负载画像是"海量短查询"还是"少量重分析"?**
   - **海量短查询(agent 高频探查):** 命门是计费粒度 + 快速唤醒 + 多租户隔离。Doris/CH 自建的常驻 compute 反而比 serverless(MotherDuck 类)更省心,但都要认真做 **compute group / warehouse 级隔离**防 blast radius。
   - **少量重分析(复杂 JOIN):** Doris 的 CBO + 多表 JOIN 优势明显,CH 会 OOM。

3. **团队能吃下存算分离的运维复杂度吗?** FoundationDB + Meta Service + Recycler(最少 3 台)、cache warmup、对象存储冷查询抖动都是新增运维面。小团队 + 纯日志场景,CH 单二进制反而更省心。

**落地压测清单(无论选谁,存算分离都要压这几项):** 冷 compute 节点 warmup 后的稳态延迟、cache miss 抖动幅度、多租户并发下的 blast radius 隔离效果、突发负载下的实际扩缩容耗时(是"分钟级"还是更慢)、以及按真实查询画像算的 TCO(算力闲置时间 + 计费增量,不只看存储降本)。

**一句话:** 换 Doris 不是"因为存算分离更先进"(CH Cloud 也有),而是"因为要开源无锁定 + JOIN + 实时更新 + 高并发点查"。若核心诉求是 AI 突发弹性,先看 ClickHouse Cloud 能不能用更小代价满足,再评估 Doris 4.0(钉 4.0.7)的跨引擎迁移值不值。

---

*调研方法:4 维度并行 sub-agent(ClickHouse 架构 / Doris 4.0 架构 / AI 负载场景 / 采用度+迁移)+ 交叉验证。所有量化数字凡来自 Doris/VeloDB 或 ClickHouse 官方处均已标注利益相关性,建议关键数字在自己的数据和查询画像上实测。*
