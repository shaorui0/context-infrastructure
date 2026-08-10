# Doris 存算分离宽表点查优化调研报告

- **调研日期**: 2026-07-24
- **对象**: `sofi.event_result` —— 3727 列、5.47B 行、4.0TB 的宽表点查(`WHERE eventId=... LIMIT 10`)
- **集群**: preprod,`doris-4.0.5-rc01`,存算分离(cloud mode),数据在 S3
- **方法**: 现场抓真实 profile + 配置(readonly)+ 5 路并行文献调研,交叉验证。用户先期实测数据一并纳入。

---

## 0. 一句话结论

**冷慢的表象是"S3 IO 慢",真正的根因是"扇出太大":一次 `WHERE eventId=` 要探遍全部 566 个 tablet / 6689 个 segment 的倒排索引。** 现场抓的**暖查询(缓存全命中、几乎 0 次 S3)仍然要 1.12s**,证明扇出本身就是成本地板,S3 只是冷路径上叠加的乘数。因此:

- **加带宽 / 调 IO 速度 = 找错方向**(冷读聚合吞吐只有 ~1MB/s,NIC 带宽用不到 1%;暖读根本不碰 S3)。
- **加 BE / 调 scan 线程 = 对点查基本无效**(LIMIT 点查并发被强制为 1;单 tablet 单 BE)。
- **唯一同时治冷 + 暖的杠杆 = `proc_date` 剪枝**,把扇出从 566 tablet 砍到 ~28(实测 69s→0.9s)。这是免费的、纯查询层的、最大的杠杆。
- 其次是**减列 / row store**(只对宽 SELECT 有用)和**暖缓存 / 升 4.1**(治冷读复发)。

---

## 1. 集群实测事实(现场 readonly 抓取)

| 项 | 值 |
|---|---|
| Doris 版本 | `doris-4.0.5-rc01`(FE×3 / BE×8 / MetaService×2 / FDB) |
| 存储模式 | 存算分离确认:`s3_default_vault`,bucket `datavisor-preprod-us-west-2-iceberg`,prefix `cre-6630/preprod/doris-internal`,us-west-2 |
| 计算组 | `cg_default`,8 个 BE,`TabletNum` 239–258 / BE |
| 表大小 | **4.002 TB**,**5,471,146,590 行**,**566 tablet**,`ReplicationNum=1` |
| 分区 | 20 个月分区 `p202412..p202607`,单分区 8–65 bucket(随数据量增长),`estimate_partition_size=300G` |
| 单 tablet | ~8.7GB / ~11.9M 行(在 1–10GB 推荐区间偏上) |
| 单行宽度 | `avgRowSize` ≈ **4021 bytes**(3727 列,~1 byte/列) |
| **segment 存储格式** | **`storage_format=V2`**(注意:schema 里的 `inverted_index_storage_format=V3` 是**倒排索引**格式,不是 segment 格式) |
| 表模型 | **DUPLICATE KEY(`user_id`, `proc_date`, `eventId`, `time`)** —— 排序键**首列是 user_id**;**无 row store**(`store_row_column` 未设) |
| 分桶键 | `HASH(user_id)` —— 而查询谓词在 `eventId` 上 |
| 每 BE 本地缓存盘 | **1.3TB nvme**(`/dev/nvme2n1` → `file_cache`),聚合 **8×1.3 = 10.4TB > 4TB 表**(装得下) |
| 缓存现状 | 仅用 ~7.5GB(~2%);BE 约 50 分钟前重启,缓存基本是冷的 |

> **纠正 1**:实际排序键是 `(user_id, proc_date, eventId, time)`,首列是 `user_id`(原始描述写的是 proc_date 首列)。不影响结论 —— eventId 仍是第 3 列,无法前缀 seek。
> **纠正 2**:`parallel_scan_type`(fixed/auto)在 Doris **不存在**,那是 StarRocks 的概念。Doris 用 `enable_parallel_scan` + `parallel_scan_min_rows_per_scanner` 控制。

---

## 2. 根因模型:扇出是地板,S3 是冷路径乘数

### 2.1 现场暖查询 profile(最关键的证据)

查询:`SELECT proc_date,user_id,eventId,event_type,ip FROM sofi.event_result WHERE eventId='10001514-IPH-1783218459337' LIMIT 10`(禁 SQL cache 的真实扫描):

```
Total: 1sec119ms      Is Cached: No     Workload Group: wg_light
OLAP_SCAN: partitions = 20/20   tablets = 566/566   ← 全分区全 tablet,零剪枝
  ExecTime: avg 205ms | max 1067ms | min 71ms       ← 一个 straggler BE 拖尾 15×
  ScanBytes: 423.75 MB(8 BE 合计)   ScanRows: 1   RowsProduced: 1
  Σ NumSegmentTotal = 6,689   Σ RowsInvertedIndexFiltered ≈ 5.47B → 1
  BytesFromRemote(S3): ~139KB 总计(7/8 BE 为 0)  ← 暖:几乎不碰 S3
  InvertedIndexSearcherCacheHit: 6687 / Miss: 0     ← searcher 缓存全命中
单 instance 分解(852 segment):
  InvertedIndexSearcherSearchInitTime: 31.8ms  ← 主导项:打开 searcher
  BlockInitSeekTime: 42.4ms(7081 次 seek)
  RowsShortCircuitPredFiltered: 0               ← 短路点查未触发
```

**读法**:这次查询 file cache 全命中、几乎零 S3,但**仍然 1.12s**。时间全在「跨 8 BE 扇出到 566 tablet / 6689 segment,逐个打开倒排 searcher、做 5.47B 行的索引过滤」。**这就是扇出成本地板,与 S3 无关。**

### 2.2 冷 vs 暖 —— 用户先期实测(补上 S3 那一层)

| 查询 | 带 proc_date | 列数 | 冷查时间 | remote 字节 |
|---|:---:|---:|---:|---:|
| SELECT * | ✗ | 3727 | 62s | 65.7MB |
| SELECT * | ✓ | 3727 | 25s | 9.8MB |
| 窄查(3列) | ✗ | 3 | 69s | 162MB |
| 窄查(3列) | ✓ | 3 | **0.9s** | **0.6MB** |

冷读聚合吞吐 ~1MB/s → **带宽富余,瓶颈 = GET 延迟 × GET 数量**。暖化后 S3 那一层消失,剩下 §2.1 的扇出地板。

### 2.2b `SELECT *` 冷查分解矩阵(现场实测,每条用不同新 eventId,profile 确认冷)

| 变体 | 剪枝 | 列数 | 冷查时间 |
|---|---|---:|---:|
| A naive `SELECT *` | 566/566 tablet | 3727 | **144s** |
| C 带 user_id+proc_date `SELECT *` | 1 tablet | 3727 | **11–31s**(典型 ~30s) |
| D 带 key 窄查(5列) | 1 tablet | 5 | **0.55s** |
| 冷→暖:同 id 剪枝 `SELECT *` | 1 tablet | 3727 | **31.8s → 0.46s(69×)** |

**两个成本可叠加、可分离**:

- **A − C ≈ 114s = 扇出成本**(naive 多出的 565 tablet 从 S3 冷探倒排)。
- **C − D ≈ 29.5s = SELECT\* 列读放大税**(同 1 tablet、同冷,仅因 3727 列页 vs 5 列页)——**剪枝治不了这一层**。
- **冷→暖 31.8s→0.46s**:那 30s 全是冷 S3 列读,命中 file cache 即塌成亚秒。

⟹ `SELECT *` 要快需**两个正交动作**:①剪枝(user_id+proc_date)干掉 114s 扇出;②暖缓存 / row store / 升 4.1 V3 干掉 30s 冷列读。两者齐做 = 0.46s(实测)。窄查询(常用列)则全集群热驻留、基本恒亚秒——**能列出所需列 + 剪枝是最省的路,不必上 row store 或升级**。

> eventId 可同时解析出 user_id(field[0])与 proc_date(field[2] 的 ms 时间戳),查询 (C) 无需映射表、也无需先跑 discovery 查询。

### 2.3 三层成本(官方文档印证)

- **(A) tablet/segment 扇出** —— 冷暖共有的地板,主导项。
  - 分桶键是 `user_id`,谓词在 `eventId` → **无法裁剪 bucket**;无 `proc_date` 谓词 → **无法裁剪 partition**。于是全部 20 分区 / 566 tablet 存活到倒排探测层。
  - 官方 data-pruning 五层裁剪 + "Without pruning, the planner fans the query out across every partition and every tablet";倒排索引是 per-segment 的局部索引,**无全局索引**("There is no global index to rebuild")。
- **(B) 列读放大** —— 只在扇出被剪掉后才显现,且只影响宽 SELECT。
  - 官方 columnar-storage 原话:"**Each column is a separate read, so a wide-row point query pays N times the I/O.**" 实测 SELECT*+PD 25s vs 窄+PD 0.9s。
  - 注意:窄查询(如现场 5 列)`RowsRead=0`、成本全在倒排过滤 → **row store 对窄查询无用**,只救 SELECT* / 宽 SELECT。
- **(C) Segment V2 footer 元数据税** —— 潜在隐藏项。
  - 官方 4.1 release:老 V2 格式把所有列 `ColumnMetaPB` 塞 footer,"even if a SQL statement only queries 2 columns, Doris still has to read the metadata of all columns... before scanning can begin"。7000 列 / 10000 segment 例子:开 segment 65s / 峰值 60GB。
  - 你们 3727 列在这个"数百到数千列"敏感带内,但现场 profile 里 `SegmentCreateColumnReadersTimer≈28ms`,占比不算爆炸(因为 segment 尚不算多)。**V3 是 4.1+ 特性,当前 4.0.5 用不了**。

---

## 3. 各优化方向裁决(逐一回应)

| 方向(你提的) | 裁决 | 依据 |
|---|:---:|---|
| **额外建 eventId→user_id+proc_date 映射表** | ⚠️ **大概率不必要,有更省的替代** | eventId 内嵌时间戳可直接推 proc_date,查询层注入即可剪枝(见 §4.1),省一张 5B 行映射表 + 双写。映射表只多给 user_id(28→1 tablet),而 0.9s 已够。若真要单 tablet,可考虑映射表建成 **Unique+MoW+row store** 以吃到 KV 短路。 |
| **注入 proc_date 剪掉大量 tablet** | 🥇 **最大、免费、治本** | 治 (A)。566→~28 tablet。实测 69s→0.9s、270× 字节。冷暖通杀。 |
| **减列 / SELECT 少列** | 🥈 有效(仅宽查询) | 治 (B)。列读按列数线性。窄查询本就不受此限。 |
| **row store(整行点查)** | 🥈 有条件上 | 治 (B) 的宽 SELECT。你任意选 30–500/3000 列 → **只有全行存 `store_row_column=true` 覆盖得了**(部分行存 `row_store_columns` 官方明确**不支持 Duplicate 表**)。代价:~2× 存储(4T→~8T)+ 写放大;需配 `disable_storage_row_cache=false`。短路快路径**不会触发**(Duplicate + 非 key 谓词,profile 已证实)。 |
| **全装 local EBS(5T)** | ✅ 硬件已就位,做的是 warm | 每 BE 1.3T×8=10.4T > 4T,装得下。治**冷读**(GET 变本地盘 ~100μs)。但暖读仍 1.12s(扇出地板不动)。**4.0.5 无持久化缓存元数据 → 每次重启缓存清零、冷读复发**;需 warmup 或升 4.1。 |
| **4 / 8 / 16 BE(资源减半/四分之一)** | ❌ 点查无效 | 单 tablet 点查跑在 1 个 BE;LIMIT 强制并发=1。加 BE 只助全表冷扫(你实测 4→16BE=1.5×),且 rebalance 会制造更多冷缓存。你实测点查 scale-out≈0,一致。 |
| **scan 片切更多 + scan 线程提升** | ❌/⚠️ 点查基本无效 | 官方明确"single-table point queries... parallelism can be set to 1";parallel scan 按**行数**切(~2.1M 行/scanner,48 线程上限),LIMIT 点查行数不够切。你实测 session knob 单独=0。remote scanner 池 48→128 只 1.19×(治冷读并发,不治扇出)。 |
| **本质是 tablets 并发 + tablet internal 并发** | ⚠️ 框架对,但结论相反 | 两级并发治的是"并发",治不了"一次查询要扇出 566 tablet"这个**数量**问题。数量只能靠剪枝。 |

---

## 4. 推荐修复栈(按 ROI + 版本门槛排序)

### 4.1 【立刻做,免费】查询层注入 `proc_date` —— 治扇出地板

eventId 形如 `10001514-IPH-1783218459337`,尾部 `1783218459337` 是毫秒时间戳。应用/查询层解析出时间 → 拼 `WHERE proc_date = date_trunc(from_unixtime(ts/1000),'day')`(或月),把查询从 20 分区剪到 1 分区、566→~28 tablet。

- **验证**:`EXPLAIN` 必须显示 `partitions=1/20`、`tablets≈28/566`。
- ⚠️ **陷阱**:`AUTO PARTITION BY RANGE(date_trunc(...))` 有已知裁剪正确性 bug(apache/doris#65606,date_trunc 表达式分区 + 手工分区谓词可能错误返回空)。上线前务必用已知存在的 eventId 验证结果非空 + 命中正确分区。
- 若还想进一步到单 tablet:同时注入 `user_id`(需映射表提供),但收益从 0.9s→更低,边际不大,先不做。

### 4.2 【缓存已持久,基本不用操心】暖缓存现状 —— 修正

> **重要修正**(现场核实):早前担心的"4.0.5 重启缓存清零、冷读周期复发" **不成立**。实测三重证据:
> - `clear_file_cache = false`(重启不删缓存数据)。
> - LRU dump/replay 已启用(`file_cache_background_lru_dump_interval_ms=60000` 等)→ **元数据已持久化**(该 build 已 backport,非 4.1 独有)。
> - **缓存盘 `nvme2n1` 是 EBS 持久卷**(model=`Amazon Elastic Block Store`,XFS),不是 instance-store 临时盘 → pod 换 node 重挂 EBS,缓存不丢(除非 PVC 被删)。
> - 铁证:同一块盘从重启后 2%(7.5G)累积到 61%(781G),缓存持续自暖、未被清。

- **结论**:缓存**持久且自暖**,无需重启后手动 warmup,也无需为"持久化缓存"而升 4.1。
- 冷读只在两种情况发生:(a) 全新/久未访问的 eventId、冷分区;(b) 未剪枝时的**扇出地板**(暖查未剪枝仍 ~1.12s,开 6689 searcher)。**两者都只有剪枝能治**,缓存治不了扇出。
- 需要时的可选项:`WARM UP COMPUTE GROUP cg_default WITH TABLE ...`(整表/按热分区,内部表 warmup **无列级**);TTL pin 热分区(`file_cache_ttl_seconds`);Cache Query Limit(`enable_file_cache_query_limit`,4.0.3+)防大查询挤占。
- **升 4.1 的性价比下调**:持久化缓存你们已有,升级只剩 `storage_format=V3`(治 (C) footer 元数据税)一个理由,而 (C) 对你不是主线 → 4.1 可延后,非当务之急。

### 4.3 【仅当宽 SELECT 无法避免】上全行存

若确实有大量"取整行 / 几百列"的点查,`store_row_column=true`(全列),配 `disable_storage_row_cache=false` + `row_cache_mem_limit`。接受 ~2× 存储 + 写放大。`row_store_page_size` 默认 16KB,点查敏感可调 4KB(存储换延迟)。

### 4.4 【小杠杆,别当主力】

- `SET GLOBAL enable_snapshot_point_query=false`:cloud 模式点查省一次 Meta Service RPC(现为 true)。低风险微收益。
- remote/prefetch 池(`doris_max_remote_scanner_thread_pool_thread_num`、`num_buffered_reader_prefetch_thread_pool_max_thread` 默认 64)只在**冷、多列多段扫**时有用;`doris_scanner_thread_pool_thread_num` 是本地池,对 S3 无效。

---

## 5. 风险与陷阱

- 🔴 **remote scanner 池线程泄漏(apache/doris#65416)**:4.1.1-rc 上 `rs_normal` 池线程不回收、涨到 27k+ 直接冻 BE,且 cap 参数据报失效。**你实测的 ">512 会 hang" 大概率就是撞这个** —— 别把 remote 池往大调,升级前先在该版本验证 cap 是否真生效。
- 🔴 **date_trunc 表达式分区裁剪正确性(#65606)**:注入 proc_date 后**必须验证返回结果非空**,别默默剪出空集。
- 🟡 **straggler BE 拖尾**:现场 profile 一个 BE 1067ms vs 最快 71ms,15× 差。全 566-tablet 扇出时,最慢 BE 的 ~70 tablet 决定墙钟。剪枝后每 BE tablet 数下降,尾也随之收窄。
- 🟡 **升 4.1 前先在 preprod 验**:V3 需重建/新写数据才生效(`storage_format` 是建表/新 rowset 属性),要评估迁移成本。

---

## 6. 收敛结论

1. **先做 §4.1(proc_date 注入)** —— 一步吃掉冷暖两种慢的主因,零成本。
2. **再做 §4.2(warm + 排期升 4.1)** —— 消除重启后 69s 冷读复发,4.1 顺带拿 V3。
3. **仅在宽 SELECT 不可避免时做 §4.3(全行存)**,想清楚 2× 存储值不值。
4. **加 BE / 调线程池不是点查的解**,别投入。scale-out 只留给全表扫场景。

---

## 7. 引用来源

**官方文档 (doris.apache.org)**
- Data Pruning(五层裁剪 / 扇出): https://doris.apache.org/docs/dev/key-features/data-pruning
- Inverted Index(局部索引 / 无全局索引): https://doris.apache.org/docs/dev/key-features/inverted-index
- Columnar Storage(每列一次 IO / 宽行 N 倍): https://doris.apache.org/docs/dev/key-features/columnar-storage
- Row Store(store_row_column / row_store_columns / page_size): https://doris.apache.org/docs/4.x/table-design/row-store
- High-Concurrency Point Query(短路条件 / cloud 旋钮 / row cache): https://doris.apache.org/docs/dev/query-acceleration/high-concurrent-point-query
- Wide Table Storage Format V3(footer 元数据税,4.1+): https://doris.apache.org/docs/4.x/table-design/storage-format
- File Cache(多队列 LRU / TTL / 指标 / warmup): https://doris.apache.org/docs/4.x/compute-storage-decoupled/file-cache
- Data Cache & Page Cache(层次 / profile 字段): https://doris.apache.org/docs/dev/key-features/data-cache-page-cache
- WARM UP 语法: https://doris.apache.org/docs/dev/sql-manual/sql-statements/cluster-management/storage-management/WARM-UP
- Parallelism Tuning(点查 parallelism=1): https://doris.apache.org/docs/2.1/query-acceleration/tuning/tuning-execution/parallelism-tuning
- Pipeline Execution(parallel scan 按行切): https://doris.apache.org/docs/3.x/query-acceleration/optimization-technology-principle/pipeline-execution-engine
- Data Bucketing(分桶剪枝需等值谓词 / tablet sizing): https://doris.apache.org/docs/dev/table-design/data-partitioning/data-bucketing
- Prefix Index(仅对 key 前缀有效): https://doris.apache.org/docs/3.x/table-design/index/prefix-index
- file_cache_statistics 系统表(hits_ratio): https://doris.apache.org/docs/3.x/admin-manual/system-tables/information_schema/file_cache_statistics
- 高并发点查(中文,cloud 旋钮): https://doris.apache.org/zh-CN/docs/dev/query-acceleration/high-concurrent-point-query

**GitHub (apache/doris)**
- #65416 remote scanner 池线程泄漏冻 BE: https://github.com/apache/doris/issues/65416
- #65606 date_trunc 表达式分区裁剪返回空: https://github.com/apache/doris/issues/65606
- #1236 宽表(100+列)查询性能: https://github.com/apache/doris/issues/1236
- config.h(BE 配置默认值): https://github.com/apache/doris/blob/master/be/src/common/config.h

**厂商博客(VeloDB / SelectDB,已标注)**
- 并发提升 20 倍(短路 / row store / PreparedStatement): https://doris.apache.org/blog/How-We-Increased-Database-Query-Concurrency-by-20-Times
- SelectDB 3.0 缓存 TPC-DS(全命中=存算一体持平,全 miss ~35% 损耗): https://www.selectdb.com/blog/1058
- Deep Dive: Data Pruning(LIMIT 并发=1 / TopN 局部堆剪): https://www.velodb.io/blog/deep-dive-data-pruning-apache-doris
- Apache Doris 4.1(持久化缓存元数据 / file_cache_info): https://www.velodb.io/blog/apache-doris-4-1-unified-storage-and-retrieval-for-ai-and-search
