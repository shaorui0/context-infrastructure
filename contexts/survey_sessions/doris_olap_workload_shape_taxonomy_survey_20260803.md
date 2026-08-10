# OLAP 查询 Workload 形态分类:按瓶颈家族而非按资源名

- **整理日期**: 2026-08-03
- **对象**: preprod Doris 4.0.5-rc01 存算分离集群,核心表 `sofi.event_result`(3727 列 / 5.47B 行 / 4.0TB / 566 tablet),以及与之共用资源池的写路径
- **定位**: 把「这个 OLAP 有哪些形态的 workload、各自瓶颈在哪」这个问题收敛成一张可用于容量规划、workload group 划分和面试防守的分类表
- **素材来源**: 现场 profile 实测(见下方引用的两份调研)+ 迁移项目一手事实,凡未实测的条目已在 §6 明确标注

---

## 0. 先修正分类轴

直觉上会把 OLAP workload 分成「高 CPU / 高 memory / 高网络 IO」三类。这个轴套在这个集群上会把人带偏,因为**目前最贵的两类查询都不是资源饱和型**。

最硬的一条反证来自现场抓的暖点查:file cache 全命中、`BytesFromRemote` 总计 139KB、CPU 也远未打满,墙钟仍然 1.12s,时间全花在打开 6689 个倒排 searcher 上。这个查询在任何资源饱和度面板上都是绿的,而加 CPU、加带宽、加 BE 对它一律无效。

所以下面按**瓶颈家族**分类,四个家族的区分标准是「什么动作能让它变快」:

| 家族 | 本质 | 唯一有效的治法 | 加资源 |
|---|---|---|---|
| 调用次数型 | 单次操作便宜,但要做几千上万次 | 减少次数(剪枝 / 减列) | 无效 |
| 延迟型 | 每次往返都要等,次数也不少 | 消除往返(缓存 / SQL cache / 少一跳 RPC) | 带宽无效,缓存有效 |
| 资源饱和型 | CPU / 内存 / 磁盘吞吐真的被打满 | 扩容 + 并发控制 + spill | 有效 |
| 串行化型 | 并发被强制压到 1,或抢同一把锁 | 减少工作量、降低竞争 | 无效 |

---

## 1. 汇总表

「外部表现」一列指不看 profile、只看监控面板和用户反馈能观察到的症状,是分类的入口;精确定位要走 §6 的 profile 字段映射。

| # | Workload 形态 | 外部表现(症状) | 主导瓶颈 | 瓶颈家族 | 实测锚点 | 加资源有效？ |
|---|---|---|---|---|---|---|
| 1 | 未剪枝宽表点查(`WHERE eventId=` + LIMIT) | 延迟卡在秒级,冷暖差别不大;各 BE CPU 都有活但都不满,带宽几乎为零;延迟随 segment 增长持续恶化 | segment 元数据 / 倒排 searcher 打开次数 | 调用次数 | 暖查 1.12s,20/20 分区、566/566 tablet、6689 segment | 无效 |
| 2 | 剪枝后的窄点查,高 QPS | 单条很快,QPS 上去后整体延迟抬升;FE CPU 高、连接数堆积逼近上限,而 BE 侧近乎空闲 | FE planner + meta service RPC + 连接数 | 延迟 / 协调 | 单条 0.55–0.9s;SQL cache 把解析 400ms 降到 2ms | 加 FE 有效 |
| 3 | 宽 `SELECT *` / 取几百列的点查 | 墙钟与列数近似成正比;冷时 remote 字节数暴涨,暖时本地盘读吞吐与解压 CPU 同时抬高 | 列读放大,每列一次独立 IO | 调用次数 | 同 1 tablet 同冷,3727 列比 5 列多 29.5s | 无效 |
| 4 | 冷分区首访 / 全新 eventId | 首查几十秒、同一 id 重跑亚秒;S3 请求数尖峰而带宽平坦在低位,file cache 命中率下掉 | 对象存储 GET 往返延迟 | 延迟 | 冷读聚合吞吐 ~1MB/s,NIC 带宽用不到 1% | 带宽无效 |
| 5 | 大范围聚合扫描 / 报表类 | BE CPU 全核打满、本地缓存盘读吞吐打满;并发一上来墙钟线性劣化 | CPU(解压 + 向量化算子)+ 本地缓存盘吞吐 | 资源饱和 | 4→16 BE 全表冷扫提升 1.5× | 有效 |
| 6 | 多表 JOIN / 大 shuffle / text-to-SQL 生成的失控查询 | BE 内存曲线陡升后 OOM 或 spill 落盘量暴涨,BE 间网络流量尖峰;同组的无关查询被牵连变慢 | 内存(hash build side)+ BE 间 exchange 网络 | 资源饱和 | 本集群未实测,见 §8 | 有效,但要 spill 兜底 |
| 7 | 宽 MoW 表上的 `COUNT(*)` / 对账查询 | 查询长时间不返回直到撞 timeout;单 BE 内存与 CPU 缓慢爬升,扫描字节数与返回行数严重不成比例 | delete-bitmap 合并的 CPU 与内存 | 资源饱和 | 朴素全表 count 会超时,需按月分区计数 | 部分有效 |
| 8 | 批量导入(写路径,与查询抢同一 BE 内存池) | BE 内存逼近 limit,被 OOMKill 或 watchdog kill;导入速率锯齿抖动,同期查询延迟一起变差 | 内存,第一约束 | 资源饱和 + 串行化 | baseline 40GiB + 每 load 25GiB,硬顶 90GiB | 无效,只能降并发 |
| 9 | Compaction 后台流 | compaction score 持续上涨不回落、磁盘 IO 高位;进一步恶化会出现 -235 / -238 直接拒写 | 磁盘 IO + CPU + 内存 | 资源饱和 | 健康 score ~50;vertical compaction 省 90% 内存 | 有效 |

**症状容易混淆的三组,区分办法:**

延迟高但 CPU 和带宽都不满的,是 #1 或 #4;区分看重跑同一条查询,#4 第二次会塌成亚秒,#1 第二次仍然是秒级。

BE 内存告警的,是 #6 或 #8;区分看这段时间有没有在跑导入,以及内存曲线的形状,#6 是单查询陡升,#8 是在 40GiB baseline 上按并发数阶梯式叠加。

查询变慢但自己没做任何改动的,是 #9 拖累(score 上涨导致归并路数变多)或 #8 抢内存(邻居效应),这两个都要先看写侧再看查询侧。

---

## 2. 调用次数型:#1 未剪枝点查、#3 宽 SELECT

这是当前的主线成本,也是最反直觉的一类。两个成本可叠加也可分离。

**#1 扇出。** 分桶键是 `HASH(user_id)`,谓词打在 `eventId` 上,既剪不掉 bucket;查询里没有 `proc_date`,也剪不掉 partition。于是 20 个分区、566 个 tablet、6689 个 segment 全部存活到倒排探测层,逐个打开 searcher 做 5.47B 行的索引过滤。单 instance 分解里 `InvertedIndexSearcherSearchInitTime` 是主导项。倒排索引是 per-segment 的局部索引,没有全局索引可用,所以「探测次数」这个量只能靠剪枝压。

**#3 列读放大。** 官方 columnar-storage 的原话是每列一次独立读,宽行点查付 N 倍 IO。实测在同一个 tablet、同样冷的条件下,3727 列比 5 列多花 29.5s,剪枝对这一层完全没有作用。

**叠加关系(实测分解)。** 冷 naive `SELECT *` 的 144s = 扇出 114s + 冷列读 30s。带 key 剪到 1 tablet 后仍要 ~30s,那 30s 全是冷列读;同一个 id 冷转暖是 31.8s → 0.46s,69 倍。带 key 的 5 列窄查 0.55s。

结论:`SELECT *` 要快需要两个正交动作,剪枝去扇出、暖缓存或 row store 去冷列读。能列出所需列时,剪枝加窄查是最省的路。

---

## 3. 延迟型:#2 高 QPS 点查、#4 冷分区首访

**#4 是存算分离的固有税,特征极好认:** 吞吐低到 ~1MB/s,带宽用不到 1%,说明瓶颈是 GET 数量乘 RTT 而不是管道粗细。这一类只有缓存能治,而这个集群的 file cache 已确认持久:`clear_file_cache=false`、LRU dump/replay 元数据持久化已 backport、缓存盘 `nvme2n1` 是 EBS 持久卷,实测从 2% 自暖到 61%。因此 #4 只在真正的新数据和久未访问的冷分区上出现,不会因为重启而周期性复发。

**#2 是 QPS 爬上来之后才显形的形态。** 单条查询轻到可以忽略,成本转移到三个地方:FE 的解析与规划、连接数逼近 `max_connections`、cloud 模式下每次点查多出的一次 meta service RPC。杠杆是 SQL cache、PreparedStatement、`enable_snapshot_point_query=false`,全部属于减少往返而不是加算力。AI agent 打出的海量短查询会精确落在这一类,所以它的重要性会随 AI 前端接入而上升。

---

## 4. 资源饱和型:#5 #6 #7 #9,以及写路径 #8

这是「高 CPU / 高 memory」传统语义唯一生效的区域,也是 scale-out 唯一有回报的区域。

**#5 是唯一能同时吃满带宽和 CPU 的查询形态**,跟点查完全相反。点查的 scale-out 收益实测约等于零,而全表冷扫 4→16 BE 有 1.5× 提升,所以扩容预算应该只对着这一类花。

**#6 是 AI 接入之后风险最高的一类。** agent 和 text-to-SQL 生成的 SQL 无法预先审查,一个 JOIN 顺序错误就能把 build side 撑爆。这一类必须靠 `enable_spill` 加 workload group 内存上限兜底,而不是指望查询本身规矩。选型调研里反复强调的 blast radius 隔离,针对的就是这个形态。

**#7 是迁移对账时实际撞到的。** 几十亿行的宽 MoW 表上朴素 `COUNT(*)` 要合并 delete-bitmap,会超时,所以对账走按月分区计数加调高 `query_timeout`。

**#8 虽然是写路径,但它和查询抢同一个 BE 内存池,且内存模型有几个非直觉点:** Parquet footer 大小等于 row group 数乘列数,所以列一多、row group 一小就会产生 GB 级 footer,读侧在读任何一行之前就 OOM;导出侧每条流的内存等于 row-group 行数乘列数,跟切片大小无关,「小切片等于小内存」这个直觉是错的;Doris 侧 Parquet 向量化 column reader 的内存不受 `exec_mem_limit` 约束,所以要把 `max_file_scanners_concurrency` 压到 1。锁定后的配置在 25.9 GiB 的 part 上稳定跑 ~90K 行/秒,峰值约 18 GiB/BE,零崩溃。

**#9 的健康判据是 score 低且平稳、tablet 版本数远低于 2000。** score 飙升等于 compaction 跟不上写入,再往下走就是 -235;`enable_vertical_compaction` 对宽表尤其关键,按列组合并把内存降到原来的十分之一。

---

## 5. 串行化型:#1 的尾部、#8 的锁

这一类既不是资源不够也不是延迟高,而是并发被强制压到 1。

LIMIT 点查的 parallelism 被强制为 1,单 tablet 只跑在单个 BE 上,所以对点查加 BE、调 scan 线程池基本无效。parallel scan 按行数切分,LIMIT 点查的行数不够切。

#1 还叠了一层 straggler:现场 profile 里最慢的 BE 是 1067ms、最快 71ms,相差 15 倍;全 566-tablet 扇出时,墙钟由最慢那台负责的 ~70 个 tablet 决定。剪枝后每 BE 的 tablet 数下降,尾也随之收窄。

写路径上对应的是 MoW 的 `delete_bitmap_update_lock`,导入、compaction、schema change 抢同一把锁。这正是 1.7B 行时 2 并发 livelock 的机制:每个 load 在 40 GiB baseline 上再加 25 GiB,反复冲破 90 GiB 硬顶,最后钳到 1 并发解决,吞吐仍然是 export-paced 的,跟得上。

这个家族的共同特点是加机器加线程一律无效,只能减少工作量或降低竞争。

---

## 6. 一眼分类:观测信号映射

§1 的「外部表现」负责从监控面板缩小到两三个候选,这一节负责坐实是哪一个。单查询层面看 profile 字段组合:

| 观测到的组合 | 落在哪类 |
|---|---|
| `tablets = 566/566` 且 `BytesFromRemote` 接近零 | #1 扇出 |
| `tablets = 1/566` 但 `RowsRead` 大、`SegmentCreateColumnReadersTimer` 明显 | #3 列读放大 |
| `BytesFromRemote` 大,而字节除墙钟只有个位数 MB/s | #4 冷读延迟 |
| `ScanRows` 上亿,CPU time 接近墙钟 | #5 聚合扫描 |
| 出现 spill 或 memory limit exceeded | #6 内存饱和 |
| BE 之间 `ExecTime` 差一个数量级 | straggler(#1 的尾部) |

集群层面,`doris_fe_query_latency_ms{quantile}` 要分冷热看(存算分离下冷热必须两条 SLO,不能设单一全局阈值);`doris_fe_connection_total` 逼近上限对应 #2;`doris_fe_max_tablet_compaction_score` 对应 #9 是否跟得上写入。注意官方绝大多数指标是 Counter 累积值,要按间隔算斜率才有意义。

---

## 7. 直接可用的推论:workload group 按瓶颈家族划分

拿这份分类去设 workload group 时,**按瓶颈家族分组比按业务线分组有效得多**,因为同一个家族的旋钮是同一套。

点查类(#1 #2 #3)的特征是单查询内存需求极低、并发需求极高,该限的是并发数和连接数,不必给大内存。分析类(#5 #6 #7)的特征是单查询内存可能爆炸、并发天然不高,该限的是内存占比并强制开 spill。导入和 compaction(#8 #9)应该拿到独立的内存配额,避免和查询互相踩。

现场 profile 显示点查已经跑在 `wg_light` 上,说明分组骨架已经存在。缺口是把 #6 这种 AI 生成的不可预测重查询单独关进一个有内存硬上限的组,这一步同时也是 blast radius 隔离的落地动作。

配套的固定动作:对 #1 在查询层注入 `user_id` + `proc_date`(两者都能从 eventId 解析,field[0] 是 user_id、field[2] 的毫秒时间戳可推 proc_date),这是唯一同时治冷和暖的杠杆,且零成本。上线前必须用已知存在的 eventId 验证结果非空,因为 `date_trunc` 表达式分区有裁剪返回空集的已知 bug(apache/doris#65606)。

---

## 8. 证据边界

实测且可复现:#1 #3 #4 #8,数字来自现场 readonly 抓的 profile 与配置,加上迁移项目的一手记录。

只有间接锚点:#5 仅有「4→16 BE 全表冷扫 1.5×」一个数据点,没有做过分层压测。

未在本集群实测:#6 完全是从 Doris 机制加 ClickHouse 侧已知短板推出来的;#7 的超时现象在迁移对账时撞到过,但没有量化过阈值。

如果这份分类要用于容量规划或面试防守,**#6 应该补一次真实压测**,因为它恰好是 AI 负载场景里最需要拿出数字的一类,也是唯一既涉及内存又涉及 BE 间网络的形态。压测清单可以直接沿用选型调研末尾那份:冷节点 warmup 后的稳态延迟、cache miss 抖动幅度、多租户并发下的隔离效果、突发负载下的实际扩缩容耗时。

---

## 9. 来源

内部一手:
- `contexts/survey_sessions/doris_wide_table_point_query_optimization_survey_20260724.md`(现场 profile、冷暖分解矩阵、集群事实)
- `contexts/survey_sessions/clickhouse_vs_doris_storage_compute_ai_load_survey_20260716.md`(AI 负载三大命门、blast radius、缓存命中三档)
- `contexts/survey_sessions/ch_to_doris_migration_interview_arsenal_20260717.md`(导入内存模型、compaction 参数、SLO 四支柱、MoW 锁竞争)
- `rules/skills/sofi_ch_to_doris_migration/`(迁移项目一手事实)

官方文档:
- Data Pruning(五层裁剪 / 扇出): https://doris.apache.org/docs/dev/key-features/data-pruning
- Columnar Storage(每列一次 IO): https://doris.apache.org/docs/dev/key-features/columnar-storage
- Inverted Index(局部索引,无全局索引): https://doris.apache.org/docs/dev/key-features/inverted-index
- High-Concurrency Point Query: https://doris.apache.org/docs/dev/query-acceleration/high-concurrent-point-query
- File Cache(TTL / warmup / query limit): https://doris.apache.org/docs/4.x/compute-storage-decoupled/file-cache
- Parallelism Tuning(点查 parallelism=1): https://doris.apache.org/docs/2.1/query-acceleration/tuning/tuning-execution/parallelism-tuning
- Compaction Principles: https://doris.apache.org/docs/dev/admin-manual/trouble-shooting/compaction-principles/
- Monitor Metrics: https://doris.apache.org/docs/3.x/admin-manual/maint-monitor/metrics/
