# 06 成本故事库：把技术故事翻译成 FinOps 语言

> 用法：先读每个故事的 Headline 和「翻译要点」，那是把工程语言换成成本语言的开关。数字全部带出处，出处路径相对 workspace 根 `/Users/rshao/work/context-infrastructure`。
> 硬规则：本目录任何百分比都不许口头加工。92% / 97% / 1,240× / 70% / 125× 只按下面写的原始口径说，多一个字都不加。
> 故事清单：S01 弹性算力池 · S02 unit economics 1,240× · S03 存算分离的存储成本结构 · S04 Iceberg 小文件与 S3 请求费 · S05 StarRocks 三 warehouse 按业务语义分 spot · S06 僵尸表清理与 TTL 治理 · S07 公司级降本（⚠️ 骨架待补） · S08 可观测性自身的成本

---

## S01 弹性算力池：把固定容量成本改成按需容量成本（主力故事）

**Headline**
> 我们的重查询负载只占执行数的个位数百分比，却承载了不成比例的算力。我把这层的成本结构从「按峰值常驻」改成「按 burst 弹起」：重查询池平时停在 0 副本，路由判定 heavy 才拉起、用完自动回收到 0。同一 burst 形状下，静态 2 节点池约 $772/月，实测 burst 模式 on-demand 约 $63/月、spot 约 $24/月。这个模式能成立的前提不是 autoscaling，是存算分离：BE 不持有本地数据，所以节点可以被随时杀掉。

**适用题型**
讲一个你做的成本优化 / 你怎么给云账单降本 / 讲一个架构决策及其依据 / 不牺牲可靠性怎么省钱 / scale-to-zero 怎么落地 / spot 敢用在什么负载上

**翻译要点（工程语言 → FinOps 语言）**

| 工程说法 | FinOps 说法 |
|---|---|
| heavy 池 `replicas: 0` | baseline capacity 归零，成本从 fixed 变成 variable |
| 路由判定 heavy 才弹起 | 需求信号驱动供给，而不是按峰值预置 |
| 存算分离，BE 无本地数据 | 消除 stateful 约束，让 spot 这类可中断容量变成合法选项 |
| 冷启动 66s + 2min 注册 | 弹性的单位代价是延迟，这笔账要对着 SLO 记 |
| 空闲 reaper 30 分钟 | 防止「弹起来忘了缩」的成本泄漏，是机制不是流程 |
| 单查询成本比 1,240× | unit economics：cost per query 的分布是重尾的 |

**情境（S）**

事件表上同时跑两种冲突负载：毫秒级点查的 serving 流量，和越来越多由 AI agent 产品功能打出的不可预测 ad-hoc 分析（src: `adhoc_jobs/dynamic_resume_site/content/case_study_ch_to_doris.md:9`）。生产 query log 挖掘的结论是点查类占捕获执行数约 97%，重查询类（跨日期聚合、大 GROUP BY、窗口查询）占执行数 3% 以下，却集中承载不成比例的算力（src: `adhoc_jobs/dynamic_resume_site/content/projects/p_elastic_compute.md:15`）。

老的 ClickHouse shared-nothing 层结构上无解：shared-nothing 把算力绑在本地盘上，空闲期和 burst 期付同一份常驻硬件；真正 stateless 的弹性算力在 ClickHouse 生态里只以闭源托管服务形态存在，这是架构缺口不是配置缺口（src: `case_study_ch_to_doris.md:18`）。

**动作（A）**

1. **先算账再动手。** 静态 2 节点重查询池 on-demand 约 $772/月；实测 burst 形状是「平均每天 2 台重节点跑约 2 小时」，on-demand 约 $63/月、spot 约 $24/月，即 on-demand 省约 92%、spot 省约 97%（src: `p_elastic_compute.md:17`、`:69`）。这笔算术是整个模式的全部理由，不是事后包装。
2. **让弹性在架构上合法。** Doris 4.0.5 shared-data 模式：tablet 数据在 S3 storage vault，元数据在 MetaService + FoundationDB，BE 是 stateless 算力，本地 EBS 只做 file cache（src: `case_study_ch_to_doris.md:26`）。所以扩缩容不搬数据：线上把池子 2→4 台 backend，零数据迁移，归属以元数据操作 rebalance 成 131/128/128/125（src: `p_elastic_compute.md:23`）。
3. **控制面收敛到一个写原语。** 第一版设计自己 Helm 装 BE 再 `ALTER SYSTEM ADD BACKEND`，我在实现前否掉了：那是把 shared-nothing 心智模型套在 shared-data 上，operator 下一次 reconcile 会把没在 CR 里声明的 compute group 直接抹掉。重写后 controller 只做一件事：读 CR、定位目标 compute group 下标、JSON-patch `spec.computeGroups[i].replicas`（src: `p_elastic_compute.md:21`、`:73`）。
4. **容量做成离散的，不做 per-query 精确。** 池子在 floor 0 和一个不大的上限之间按固定增量伸缩：扩容是分钟级，很多查询在新 backend 就绪前就跑完了，per-query 弹性大多是表演（src: `p_elastic_compute.md:25`、`:77`）。
5. **回收做成机制。** 空闲 reaper 每 5 分钟扫，仅当某 compute group **所有** BE 的 `currentFragmentNum == 0` 且无 fragment 活动超过 `idleScaleDownMinutes`（默认 30）才回收到 0（src: `contexts/resume_highlights_doris_dcluster.md` §2.2）。
6. **扩容侧做去抖 + cooldown 匹配执行延迟。** 只有 `waiting_query_num ≥ K` 持续 W 秒才扩，扩完 arm 一个 cooldown，防止单次 burst 在 BE 冷启动（约 3-4 分钟）期间反复触发扩容。默认 K=3、W=120s、cooldown=5min（src: `resume_highlights_doris_dcluster.md` §2.2）。

**结果（R，带出处）**

- 成本口径：静态 2 节点池 ~$772/月 → 实测 burst 形状 ~$63/月（on-demand）/ ~$24/月（spot），省约 92% / 97%（src: `p_elastic_compute.md:17`）。
- 存储侧：4TB 迁移零额外 BE 盘（src: `adhoc_jobs/dynamic_resume_site/research/interview_story.md:41`）。
- 完整闭环在生产规模 preprod 集群跑通：verdict 判 heavy → controller patch 0→N → ASG 约 66s 起节点 → backend 约 2min 注册 → 分层就绪检查 → 查询在重池执行 → idle reaper 回 0（src: `p_elastic_compute.md:23`）。
- Takeaway 一句话（可以直接背）：静态池约 92% 到 97% 的成本纯粹是空转时间（src: `p_elastic_compute.md:59`、`:111`）。

**⚠️ 引用纪律**

- 「重查询 <1% 流量」是**设计假设不是实测**（src: `resume_highlights_doris_dcluster.md` §1；`90_cross_cutting/number_baseline.md` §5）。query log 挖掘给出的是**≤3% of executions / 点查约 97%**（src: `p_elastic_compute.md:15`）。**两个口径不一样，别混。** 安全说法：「生产 query log 挖掘的结论是重查询类占执行数 3% 以下；方案里用的规划假设更保守，按 <1% 写的。」
- $772 / $63 / $24 是**成本建模数字**，不是 AWS 账单 A/B。resume_highlights §5 明确写：repo 里没有端到端生产指标，没有池利用率 / 重试率 / 账单 A/B（src: `resume_highlights_doris_dcluster.md:138`）。被问「这是账单上省下来的钱吗」→ 直说是按实测 node-hours 和 list price 建的模型，不是对账后的账单差额。
- 97%（spot）当前是**投影不是已实现**：决策是「装好 node-termination handler 之前用 on-demand，之后再切 spot 优先的混合 ASG 加 on-demand 兜底」（src: `p_elastic_compute.md:51`、`:103`）。**注意**：这与 S05 的 StarRocks 场景不同，那边 spot 是真的在跑。

**5 层追问防线**

**L1「省了多少？口径是什么？」**
静态 2 节点常驻重池 on-demand 约 $772/月是 baseline；实测 burst 形状（平均每天 2 台节点跑约 2 小时）on-demand 约 $63/月、spot 约 $24/月，省约 92% / 97%。口径要主动交代三件事：只算重查询池这一层，不含 serving 常驻池，不是整个账单；burst 形状来自实测 node-hours，不是猜的；这是按 list price 建的成本模型，不是账单前后对比。我们那时候还没把成本归因做到 compute-group 粒度，这也是我认为该补的东西。

**L2「代价是什么？为什么可以接受？」**
弹性的代价是冷启动：节点约 66 秒，backend 向 FE 注册约 2 分钟，外加第一次冷读 S3 的扫描税（src: `p_elastic_compute.md:17`）。可以接受的理由不是「用户忍一忍」，是**这条延迟只加在一个本来就延迟容忍的类别上**：被路由成 heavy 的查询本身是 60 到 500 秒量级的分析查询，加 3 分钟在相对量级上可谈；serving 路径的点查一条都不会经过这个池子，物理隔离。反过来说，如果重查询也有毫秒级 SLO，这个模式直接不成立，那就得付常驻成本。

**L3「为什么 spot 是安全的？」**
关键不在 spot 便宜，在存算分离让「杀节点」这个动作变廉价。BE 是 stateless 算力，tablet 在 S3，本地 EBS 只是 file cache，所以杀掉一台 BE 不丢数据、不需要 `DECOMMISSION` 搬数据下线（src: `case_study_ch_to_doris.md:26`、`resume_highlights_doris_dcluster.md` §1）。时间预算也算过：FE 心跳约 2 秒检测到 backend 失联，锁约 7 秒释放，失败查询重试一次，全部落在 spot 2 分钟回收窗口之内（src: `p_elastic_compute.md:51`、`:103`）。同一套论证也解释了**为什么 serving 池永远不上 spot**：一次回收等于查询中断加缓存清空。按池分治，不是全站一刀切。

**L4「spot 拿不到容量 / 中途被回收怎么办？」**（⚠️ 归属边界最紧的一层）
先讲我做的推理：一条 60 到 500 秒的重查询中途被回收，浪费的是已完成的工作，加约 3 到 4 分钟的重新扩容。所以决策是**装好 node-termination handler 之前用 on-demand，装好之后切 spot 优先的混合 ASG 加 on-demand 兜底**，锚定实测 node-hours 而不是「spot 便宜」的教条（src: `p_elastic_compute.md:51`、`:103`）。
诚实边界：**dcluster 里 spot 中断回退、容量准入这批平台可靠性代码的 git 作者不是我**（src: `resume_highlights_doris_dcluster.md` §0）。标准答法：「spot 中断回退的实现是团队另一位同事做的；我负责的是控制面的幂等扩缩语义、队列/空闲驱动的伸缩闭环，以及 spot 在存算分离下为什么安全这个论证和按池分治的决策。」说到这里就停，不要接着描述回退实现细节。

**L5「这个模式的适用边界在哪？什么负载不能这么做？」**
四条边界，讲两到三条就够：
1. **状态在本地就不能做。** 只要节点持有唯一副本，杀节点就要先搬数据，弹性的边际成本就从「冷启动延迟」变成「数据迁移」，账立刻不成立。
2. **SLO 不容忍冷启动就不能做。** 冷启动 3-4 分钟只能摊给延迟容忍的负载。
3. **请求间隔比冷启动短的高频负载反而会更贵。** 业界现成的反例：agent 每天打 1 万条 2 秒的短查询，遇上冷启动超 1 分钟加 60 秒最小计费，最高是 30 倍成本惩罚，Together AI 就因此弃用了 ClickHouse Cloud（src: `contexts/survey_sessions/clickhouse_vs_doris_storage_compute_ai_load_survey_20260716.md:166`、`:172`）[理论/业界]。所以「scale-to-zero 一定更省」是错的，省不省取决于 burst 的稀疏度和计费粒度。
4. **零副本不等于零运维成本。** 我们踩到过：缩到 0 的 compute group 会在元数据服务里留下 orphan lease，在过期前阻塞其他 group 的 compaction（src: `p_elastic_compute.md:49`、`:101`）。idle 状态需要专门的运维审视，不能默认免费。

**归属边界**
- 能理直气壮说：控制面幂等扩缩语义（声明式 raise-only launch、三层并发 guard、默认幂等/opt-in 增量的 scale-up）、queue/idle 驱动的伸缩闭环、与 Doris FE 的读信号契约、三次重写做减法的 scoping 判断、spot 按池分治的决策与论证。
- **不能说**：spot 中断回退 / 容量准入 / 多集群锁修复 / 审计日志（git 作者 junhan.ouyang / Runzi Yang）（src: `resume_highlights_doris_dcluster.md` §0）。
- ASG / Launch Template 层我的深度是**消费修补**（改 request 从 cpu=8 到 7、补 node-template label/taint tag 让 CA 能从 0 扩），不是 ASG 体系的设计者。被追问 ASG 混合实例策略、capacity-rebalance 细节，答机制 + 承认没做过配置层的深度设计。
- preprod 边界：完整闭环是在生产规模的 preprod 集群跑通，10T 生产化推进中。放结尾讲，不在开场自曝（src: `interview_story.md:29`、`:49`）。

**可复用到**
01 Doris/DB 运维（存算分离角度）/ 04 IaC-K8s（CA scale-from-zero 两类静默拒绝）/ 07 AWS fundamentals（spot 生命周期、ASG/LT、CA 虚拟节点模板）/ 90 行为面（在实现前否掉自己第一版设计 = senior taste）

---

## S02 单查询成本比 1,240×：用 unit economics 做架构决策

**Headline**
> 我没有从「CPU 利用率高不高」入手，而是先算了 cost per query。生产 query log 挖掘的结论是：最贵的那条月度累计窗口查询平均 196,354 ms，频率最高的点查平均 158 ms，单查询成本比约 1,240 倍；那条窗口查询跑 18 次，总算力约等于 21,755 条点查。频率和成本指向完全相反的方向，这个数字直接否掉了「一个池子服务所有查询」，也直接推导出了「重查询池必须是弹性的」。

**适用题型**
你怎么衡量一个系统的成本效率 / 你怎么决定优化哪里 / 讲一个你用数据推翻团队假设的例子 / 什么是 unit economics

**翻译要点**
这是本方向**最高阶**的素材，因为它做到了 FinOps 里最难的那一步：从「总额」下到「单位成本」。绝大多数候选人讲成本只会讲「账单降了 X%」，讲不出「一个单位的业务动作花多少钱、分布是什么形状」。要讲成**方法论**：先测单位成本的分布，再决定架构，最后才谈价格手段（spot / 承诺折扣）。

**情境（S）**
迁移把 serving 和分析收敛到一套 Doris 之后，要决定算力怎么切。团队的默认假设是按频率设计容量。

**动作（A）**
1. 挖生产 query log，按查询形状分类，统计执行次数和真实耗时，而不是看聚合的 CPU 曲线。
2. 算出三个数：点查类约占捕获执行数 97%，重查询类占执行数 3% 以下但集中承载不成比例的算力；单查询成本比约 1,240×（月度累计窗口查询平均 196,354 ms vs 频率最高点查平均 158 ms）；18 次窗口查询 ≈ 21,755 条点查的总算力（src: `p_elastic_compute.md:15`、`:67`）。
3. 用这个分布推结论：为轻查询多数派设计的池子，优化目标是吞吐和并发，与重尾完全不匹配，重尾也绝不能与 serving 池共享机器（src: `p_elastic_compute.md:15`）。
4. 把同一个分布用到成本侧：既然重尾稀疏且延迟容忍，就不该常驻 → 弹性池 → S01 那笔 $772 vs $63/$24 的账（src: `p_elastic_compute.md:17`）。
5. 同一套「用数据推翻假设」的动作还有一个平行例子：94.2% 点查比例推翻了团队关于负载画像的假设（src: `interview_story.md:22`）。

**结果（R）**
- 架构决策：算力按 compute group 物理分池（常驻 serving 池在 on-demand，弹性重查询池停在 0 副本），池内再用 workload group 管 CPU / 内存 / 并发（src: `case_study_ch_to_doris.md:26`）。
- 成本结论：这笔算术就是整个弹性模式的全部理由（src: `p_elastic_compute.md:17`）。

**5 层追问防线**

**L1「1,240× 这个数怎么算出来的？」**
分子是那条月度累计窗口查询的平均执行耗时 196,354 ms，分母是频率最高的点查形状平均 158 ms，都从生产 query log 里按查询形状聚合出来的（src: `p_elastic_compute.md:15`）。要主动交代这是**墙钟耗时比，不是美元比**：严格说 cost per query 应该是「资源占用 × 时间 × 单价」，我用墙钟做代理，是因为两类查询跑在同规格节点上，且我要的是量级不是精度。真要做美元化，正确做法是给 compute group 打成本分配标签，用 node-hours 反推每类查询的摊销成本，这是我当时没做完的一步。

**L2「墙钟做代理不严谨，凭什么信？」**
不用它做精算，只用它做**排序和量级**。1,240 倍这个量级足够支撑「不能共享池子」这个决策，就算误差一个数量级，结论不变。这是我选指标的原则：先问这个数要支撑什么决策，再决定精度要到哪。如果决策是「跟财务对账」，我不敢用墙钟；决策是「要不要物理隔离」，量级就够了。

**L3「用它做了什么决策？」**
三个：否掉了「一个池子服务所有查询」，改成 compute group 物理分池；否掉了「常驻重查询池」，改成 floor-0 弹性池；定了路由分类器的**风险姿态**是 recall-first，因为误判 heavy 只浪费一点算力、误判 light 会被内存硬限杀掉再重试，代价不对称，所以宁可多判 heavy（src: `resume_highlights_doris_dcluster.md` §4.4）。第三条是成本思维直接决定了可靠性设计，这是这个数字最值钱的地方。

**L4「你怎么持续监控这个单位成本？做成看板了吗？」**（诚实边界）
没有做成常态看板，这是缺口。当时是一次性的 query log 挖掘加建模，不是持续度量。如果现在补，我会这么做：路由分类器的 verdict 本来就暴露 `key_metrics`（src: `resume_highlights_doris_dcluster.md` §4 rigor 证据），把 verdict 打点进指标，按 compute group 和 workload group 聚合，再配上 node-hours，就能得到 per-query-class 的成本时间序列；再往上一层才是 per-tenant 的 showback。从「一次分析」到「一条度量」这步我没走完。

**L5「如果这个分布变了怎么办？AI 负载起来之后重查询占比会涨。」**
这正是最有意思的地方，而且设计里已经考虑了：路由分类器的阈值是**capacity-relative** 的，`routing_light_pool_cores > 0` 时行数和 CPU 阈值按 `perCore × cores` 派生，同一条查询会随池子大小改判（60M 行扫描在 8 核池判 heavy、84 核池判 light）（src: `resume_highlights_doris_dcluster.md` §4.3）。也就是说路由策略和弹性容量是耦合协同的，不是两个独立系统。成本角度说：重查询占比涨到某个点，弹性的账会翻转成常驻更便宜，那时候正确动作是把 baseline 抬起来，并用承诺折扣覆盖这部分新 baseline。这个翻转点应该被算出来当触发条件，而不是等账单异常了才发现。

**归属边界**
query log 挖掘、单位成本分析、分池决策、recall-first 风险姿态都是我做的。阈值 capacity-relative 化是我在 Doris fork 里实现的分类器逻辑（src: `resume_highlights_doris_dcluster.md` §0 第 2 条）。

**可复用到**
01（负载画像）/ 02（指标选取原则）/ 90（用数据改变设计）

---

## S03 存算分离改变了存储的成本结构（以及它引入的新成本科目）

**Headline**
> 存算分离最直观的收益是存储：4TB 的表迁过去零额外 BE 盘，扩容 2→4 台 backend 零数据搬迁。但真正值得讲的是它**换了成本科目**：本地 EBS 从「数据盘」降级成「cache」，省下的容量费变成了 S3 的存储费加请求费。我实测过冷读的瓶颈根本不是带宽，是 GET 的次数乘延迟：冷读聚合吞吐只有约 1MB/s，NIC 带宽用不到 1%。所以在存算分离上，「减少要打开多少文件」既是性能优化也是成本优化。

**适用题型**
存储成本怎么优化 / S3 有什么坑 / 缓存策略怎么定 / 冷热分层 / 成本与延迟怎么权衡

**情境（S）**
CH shared-nothing 下每节点挂本地盘存数据；迁到 Doris shared-data 后 tablet 数据在 S3 storage vault，本地 EBS 只做 file cache（src: `case_study_ch_to_doris.md:26`）。表规模 ~5.2B 行 / ~4 TiB source / 最多 ~3,700 列（src: `case_study_ch_to_doris.md:9`）。

**动作与结果（A/R）**

1. **容量费侧的直接收益。** 4TB 迁移零额外 BE 盘（src: `interview_story.md:41`）。线上扩容 2→4 台 backend 零数据搬迁，tablet 归属以元数据操作 rebalance（src: `p_elastic_compute.md:23`）。
2. **厂商口径可以引用但必须标明来源。** 相比存算一体三副本，存储成本最高降 90%；100TB 在线数据从三副本约 $37K/月降到单副本约 $22K/月（约 40%），历史冷数据可降 90%+（src: `contexts/survey_sessions/clickhouse_vs_doris_storage_compute_ai_load_survey_20260716.md:84-86`、`contexts/survey_sessions/ch_to_doris_migration_interview_arsenal_20260717.md:211`）[**Doris 官方口径，非我实测**]。`01_doris_db_operations/README.md:103` 已经立了同一条纪律，两处保持一致。
3. **cache 层的容量决策。** 每 BE 本地 1.3TB nvme 做 `file_cache`，8 台聚合 10.4TB > 4TB 表，也就是**整表装得下**（src: `contexts/survey_sessions/doris_wide_table_point_query_optimization_survey_20260724.md:35`、`:117`）。这是一次显式的成本-延迟权衡：花本地盘的钱买掉 S3 冷读的延迟和请求费。
4. **S3 侧的隐形成本科目被实测出来了。** 冷读聚合吞吐只有约 1MB/s，NIC 带宽用不到 1%，瓶颈是 **GET 延迟 × GET 数量**（src: 同上 `:74`、`:14`）。一次 `WHERE eventId=` 的点查要探遍全部 566 个 tablet / 6689 个 segment 的倒排索引（src: 同上 `:12`）。
5. **但结论要诚实：S3 不是根因。** 现场抓的暖查询（缓存全命中、几乎 0 次 S3）仍然要 1.12s，证明**扇出本身就是成本地板，S3 只是冷路径上叠加的乘数**（src: 同上 `:12`、`:63`）。两个成本可叠加可分离：`A − C ≈ 114s` 是扇出成本（naive 多出的 565 个 tablet 从 S3 冷探倒排）（src: 同上 `:87`）。
6. **所以最大杠杆是剪枝，不是买缓存也不是加带宽。** 加带宽 / 调 IO 速度是找错方向；`proc_date` 注入做分区剪枝一步吃掉冷暖两种慢的主因，零成本（src: 同上 `:14`、`:169`）。

**5 层追问防线**

**L1「存算分离省了多少存储成本？」**
我能负责的是两条事实：4TB 表迁过去零额外 BE 盘；扩容不搬数据。百分比我只引用厂商口径并明确标是厂商口径（三副本到单副本约 40%、冷数据 90%+）。我们自己没做过账单 A/B（src: `resume_highlights_doris_dcluster.md:138`）。要主动补一句诚实的话：存算分离不是净省，它把 EBS 的容量费换成了 S3 的容量费加请求费，净收益取决于副本数和访问形态。

**L2「S3 的请求费在你们场景里是多少？」**
Doris 这条链上我没拿到过按 operation 维度的账单明细，这是缺口。但我有实测的物理量可以推：一次未剪枝的点查要开 6689 个 segment 的倒排 searcher，冷路径上那就是 6689 量级的 GET；冷读聚合吞吐只有 1MB/s，说明每个 GET 都很小。小文件加高扇出等于请求费敏感型访问形态。**而在 Iceberg 那条链上我是真的把这个模型落到动作上了**，见 S04：profile 显示 99% 时间在 OpenFile，我从「S3 按请求次数计费」这个模型推导出所有动作，把文件数 619 降到 49（src: `work-contexts/career/interview/interview-6-starrocks-lakehouse.md:53`、`:70`）。

**L3「那你为什么不直接把所有数据都缓存到本地？」**
我们确实做到了「装得下」（10.4TB cache > 4TB 表）。但这解决的只是冷读，暖查询仍然 1.12s，因为扇出地板不动（src: `doris_wide_table_point_query_optimization_survey_20260724.md:117`）。这是我在这件事上学到最重要的一条：**缓存治不了扇出**。花钱买缓存能消掉一个乘数，消不掉那个加数。所以优先级是先剪枝（改变要打开多少文件），再暖缓存（改变每个文件打开多贵）。反过来做就是花了钱、指标不动。

**L4「file_cache 重启会不会清零？那缓存投资不是白费了？」**
这个我查过，而且推翻了自己早前的判断。早前担心的「4.0.5 重启缓存清零、冷读周期复发」不成立，三重证据：`clear_file_cache = false`（重启不删缓存数据）；LRU dump/replay 已启用（`file_cache_background_lru_dump_interval_ms=60000`），元数据已持久化，该 build 已 backport（src: 同上 `:136-138`）。可选手段还有 `WARM UP COMPUTE GROUP` 做整表或热分区预热、`file_cache_ttl_seconds` 把热分区 pin 住、`enable_file_cache_query_limit` 防大查询挤占缓存（src: 同上 `:144`）。最后一条其实是成本治理思维：防止一条大查询把别人的缓存投资冲掉。

**L5「换个场景，如果表是 100TB，本地装不下，成本策略怎么变？」**
装不下就必须做分层，策略从「全量暖」变成「按访问概率分配缓存预算」。三条会变：分区剪枝的重要性从「重要」升级为「唯一可行」，因为缓存命中率注定低；热分区用 TTL pin、冷分区接受 S3 延迟，而这个热窗口长度应该由访问分布决定，不是拍脑袋；S3 侧要开始考虑存储类和生命周期，冷分区往低频类走。我们的 4TB 场景还没到必须做这件事的规模，所以这部分我是理论加迁移期的规划，不是运维过的。

**归属边界**
点查优化的实测与根因分析（扇出是地板、缓存治不了扇出、proc_date 剪枝是最大杠杆）是我做的（src: memory `reference_doris_event_result_point_query`、survey 20260724）。存储成本百分比全部是厂商口径，明确标注。

**可复用到**
01（存算分离运维）/ 07（S3 与 EBS 基础）/ 05（迁移期的数据层决策）

---

## S04 Iceberg 小文件治理：从「S3 按请求次数计费」这个成本模型推导出全部动作

**Headline**
> StarRocks + Iceberg on S3 这条链上，我 profile 出 99% 的时间花在 OpenFile 上，于是没有去调并发或加带宽，而是先建了一个成本模型：**S3 是按请求次数计费的，不是按带宽计费的**。所有动作都从这个模型推导：把写侧的文件数压下来。结果文件数 619 降到 49，FSIOTime 从 7.9s 降到 63ms（125 倍），冷查询 7.5s 降到 744ms。这是我最喜欢的一个例子，因为它同时是性能优化和成本优化，而且它们是同一个原因。

**适用题型**
S3 成本有什么坑 / 你怎么做性能调优（senior 版答法）/ 小文件问题 / 数据湖运维 / 讲一个你从第一性原理推导出方案的例子

**翻译要点**
这个故事的杀伤力在于**因果方向**：不是「我调好了性能，顺便省了钱」，而是「我先建了计费模型，性能提升是这个模型的推论」。面试官听「我把参数从 4 调到 32」没感觉；听「我 profile 发现 99% 时间在 OpenFile，推出 S3 按请求计费的成本模型，所有动作从这个模型推导」才给 senior 评级（这句话原文就在 evidence 里，src: `work-contexts/career/interview/interview-6-starrocks-lakehouse.md:70`）。

**情境（S）**
Iceberg on S3 的测试表约 270 万行 × 约 1900 列；生产 fact 表积累到 130K+ data files，导致 FE plan 时间从 200ms 涨到 8s+（src: `interview-6-starrocks-lakehouse.md:169`、`:171`）。冷查询 7.5s、热查询 1.4s（datacache 4G mem + 20G disk）（src: 同上 `:62`）。

**动作（A）**
1. **先 profile 再动手。** 99% 时间在 OpenFile，不在 Scan、不在网络吞吐（src: 同上 `:70`）。
2. **建计费模型。** S3 按请求次数计费，所以「打开多少个文件」直接决定这条链的成本和延迟，「传了多少字节」反而不是主项。这个模型一旦立住，就同时排除了两类常见错误动作：加带宽、提 scan 并发。
3. **从模型推导动作（三个参数，都是手段不是核心）：** `BATCH_SIZE` 50K→500K、Iceberg `target-file-size` 512MB→1GB、`commit.interval` 60s→10min（src: 同上 `:53`）。
4. **`commit.interval` 那一条不是技术决策，是业务决策。** 60s→10min 让写侧文件数降约 3 倍，代价是端到端可见性变成约 10 分钟。这条是**和业务确认「10 分钟可接受」之后才定的**（src: 同上 `:60`）。
5. **做了对照实验，也留下了反例。** `dop=2` vs `dop=4`：冷查询 dop=4 快 2.2 倍（542ms vs 1175ms），热查询 dop=2 反而更快（196ms vs 220ms），最终按主场景（热缓存是生产主路径）保持 dop=2，接受冷查询劣化（src: 同上 `:55`）。`dop=8` 在 2 核上跑出 21s，比 dop=2 慢 4 倍，是过度并行的负面实验（src: 同上 `:58`、`:169`）。

**结果（R）**
- 文件数 619 → 49；FSIOTime 7.9s → 63ms（**125×**）；冷查询 7.5s → 744ms（src: 同上 `:53`）。
- 端到端：热查询 12.2s → 247ms（49×），冷查询 16×（src: 同上 `:167`）。
- `connector_io_tasks` 4→16→32：12.2s → 8.9s，原理是 latency hiding（I/O 任务等网络时不占 CPU，可以远超核数）（src: 同上 `:59`）。

**5 层追问防线**

**L1「S3 请求费具体省了多少钱？」**
诚实答：**我没有把它换算成美元，也没有从账单侧验证过**。我能证明的是请求次数这个物理量降了一个数量级以上（619 个文件降到 49，FSIOTime 降 125 倍），以及这个物理量与 S3 计费是线性相关的。如果要补这一步，正确做法是从 CUR 里按 bucket 和 operation 维度拉 `Requests-Tier1/Tier2` 的用量做前后对比。我承认我停在了物理量层面，没走到账单层面。

**L2「文件数降下来了，那 compaction / rewrite 本身的成本呢？」**
这是对的，小文件合并不是免费的：它自己要读一遍写一遍，产生 GET 加 PUT。我处理的方式是**从写侧治本而不是靠事后合并**：`target-file-size` 和 `commit.interval` 是让文件一开始就不要那么碎，而不是先碎了再合。这两条的边际成本几乎是零（只是配置），而事后 rewrite 是持续付费的。原则是：能在写路径解决的碎片，不要留给读路径和后台任务。

**L3「`commit.interval` 从 60s 拉到 10min，用户不抱怨吗？」**
这正是我认为这个故事最像 senior 的一段：这不是我能单方面定的参数。文件数降 3 倍换来端到端可见性约 10 分钟，我先把这个 trade-off 量化成「你们能接受数据晚 10 分钟看到吗」，跟业务确认可接受之后才定（src: 同上 `:60`）。如果业务说不行，正确动作不是硬调这个参数，而是回到别的杠杆（比如 `target-file-size` 或写侧批大小）。成本优化里最常见的错误就是工程师自己替业务接受了 SLA 降级。

**L4「dop 你为什么最后选了慢的那个？」**
因为最优值随瓶颈类型反转，这是我在这次调优里最有意思的发现：冷查询是 I/O bound，所以 dop=4 更快（542ms vs 1175ms）；热查询是 CPU bound，dop=2 反而更快（196ms vs 220ms）（src: 同上 `:55`）。生产主路径是热缓存，所以按主场景定值，接受冷查询劣化。成本视角讲这件事：不存在「全局最优参数」，只有「对主场景最优」，而主场景要用真实流量分布来定，不是用 benchmark 定。

**L5「这个方法论怎么迁移到别的地方？」**
迁移的是**「先建计费模型，再推导动作」这个顺序**，不是参数。同一个方法我在 Doris 那条链上也用了，但结论不同：Doris 点查那边我实测出瓶颈不是 S3 而是扇出（暖查询全命中缓存仍然 1.12s），所以最大杠杆是分区剪枝而不是文件合并（见 S03）。两条链的动作完全不同，但方法一样：先 profile，再问「这个瓶颈在账单上对应哪个计费维度」，再从那个维度找杠杆。反面例子也留着：在 Doris 那边如果按直觉去加带宽，冷读聚合吞吐只有 1MB/s、NIC 用不到 1%，钱花了指标不动。

**归属边界**
Iceberg / StarRocks 部署是 FY2026 已达成目标之一（src: `contexts/fy2026_self_assessment.md:8`），性能调优与成本模型推导有完整 profile 与对照实验记录（src: `interview-6-starrocks-lakehouse.md` §3）。**⚠️ 待确认**：这条链当时的运行环境（preprod 还是生产）在 evidence 里没有明确写；`interview-6` 提到「FE 主备切换未演练（dev 单 FE）、千万行级压测未做」，说明至少部分工作在 dev/preprod。讲之前先自己确认，不要含糊说「生产」。

**可复用到**
01（数据湖运维）/ 07（S3 请求费与对象布局）/ 90（第一性原理推导 + 跟业务谈 trade-off）

---

## S05 StarRocks 三 warehouse：按业务语义把 on-demand 和 spot 分开

**Headline**
> 同一套 StarRocks 上我把算力切成三个 warehouse，切分依据不是资源用量而是**业务语义**：`query_wh` 跑用户面 MV 查询，on-demand 常驻，保 50ms 级 SLA；`refresh_wh` 跑夜间 MV 刷新，spot，刷完直接销毁；`adhoc_wh` 跑 ad-hoc，spot，按需拉起。spot CN 省约 70%。这个故事最能讲的是那条硬约束：**on-demand 与 spot 不可混**，因为 spot 回收等于 in-flight query 失败，用户面流量必须钉在 on-demand。

**适用题型**
spot 怎么用才安全 / 怎么在不影响 SLO 前提下降本 / 容量管理怎么做 / 为什么不用 HPA / 讲一个成本与可靠性权衡的决策

**翻译要点**
S01 是「时间维度」的降本（把 baseline 归零）；这个故事是「工作负载维度」的降本（把不同风险容忍度的负载放到不同定价模型上）。两个一起讲能形成体系感：**先按业务语义分池，再给每个池选定价模型**，这正是 FinOps 里 workload-to-pricing-model 匹配的标准做法。而且「夜间用便宜算力预计算、白天用结果」本身就是一个时移套利的成本模式。

**情境与动作（S/A）**

1. **三 warehouse 物理隔离**（src: `work-contexts/career/interview/interview-6-starrocks-lakehouse.md:157`）：
   - `query_wh`：on-demand，always-on，白天 MV 查询约 50ms，保 SLA
   - `refresh_wh`：spot，nightly 01:50 UTC 启动，刷完销毁
   - `adhoc_wh`：spot，按需拉起
2. **硬约束写在明面上**：on-demand 与 spot 不可混。spot 回收等于 in-flight query 失败，所以用户面流量必须钉在 on-demand（src: 同上 `:157`）。
3. **池内再加一层 resource group 防线**：`rg_mv`（`cpu_weight=10`）vs `rg_adhoc`（`cpu_weight=1`、`big_query_cpu_second_limit=120`），防 ad-hoc 打爆 CN（src: 同上 `:158`）。
4. **弹性是 proactive 不是 reactive**，五步：fp-async 的 QueryClassifier 查 `cube_mv` 状态预判 ad-hoc → POST launch spot EC2 → CN 启动后 3-5 分钟轮询 → `ALTER SYSTEM ADD COMPUTE NODE ... TO WAREHOUSE` → 查询完 teardown（src: 同上 `:159`）。
5. **为什么不用 HPA（必被追问，三条）**（src: 同上 `:160`）：CN 冷启动 3-5 分钟，reactive 永远落后于秒级查询期望；HPA 只看 CPU/mem，识别不了「无 MV 命中的 ad-hoc 重查询」这种业务语义，只有 fp-async 持有 cube coverage 信息、能在执行前判断；proactive 加前端「数据处理中」吸收等待才是合理取舍。

**结果（R）**
- spot CN 省约 70%（src: 同上 `:161`）。
- MV 夜间用便宜算力预计算，白天用结果（src: 同上 `:161`）。
- MV 路径 Infra SLO：p95 <2s / p99 <5s / 错误率 <1%（src: 同上 `:173`）。

**5 层追问防线**

**L1「70% 是怎么来的？」**
是 spot 相对 on-demand 的价格折扣在那个实例档位上的量级，落到 CN 这类算力节点上。要主动交代边界：这是**单价折扣**，不是账单降幅，因为 refresh_wh 和 adhoc_wh 的 node-hours 本来就不大；真正的降本是两件事的乘积，spot 单价折扣乘上「刷完就销毁」带来的时长压缩。同一套逻辑在 Doris 那边我算得更细：$772 常驻 vs $63 on-demand burst vs $24 spot burst（见 S01）。

**L2「spot 被回收，MV 刷新失败了怎么办？」**
这是这个设计里最舒服的一点：MV 刷新是**可重跑的批任务**，失败的代价是「今晚这批晚一点」，不是「用户看到错误」。所以 spot 的风险恰好落在一个能承受它的负载上。反过来 `query_wh` 一秒都不敢上 spot，因为一次回收等于 in-flight query 失败，直接命中用户面 SLA。**风险容忍度决定定价模型**，这就是我做这个切分的判据。要诚实补一句：spot 中断的自动重试和回退机制我不是实现者（见归属边界）。

**L3「为什么不用 HPA？这不是标准做法吗？」**
三条理由，前两条是硬的：CN 冷启动 3-5 分钟，而查询侧的期望是秒级，reactive 伸缩在时间尺度上永远追不上；HPA 的输入只有 CPU 和内存，它看不到「这条查询有没有 MV 命中」这个业务语义，而这恰好是判断要不要拉起 ad-hoc 算力的唯一有效信号，只有 fp-async 持有 cube coverage 信息（src: 同上 `:160`）。第三条是取舍：proactive 预拉起加上前端「数据处理中」的提示来吸收等待，比让用户在一个反应不过来的 HPA 后面干等更合理。这一条和 Doris 那边的结论是一致的：**执行有分钟级延迟的系统，必须对持续压力反应，不能用秒级信号驱动**（src: `resume_highlights_doris_dcluster.md` §2.2）。

**L4「三个 warehouse 意味着三份闲置容量，会不会反而更贵？」**
不会，因为三个池子里只有一个是常驻的。`query_wh` 是唯一 always-on 的，另外两个都是零基线：`refresh_wh` 只在 01:50 UTC 那个窗口存在，刷完销毁；`adhoc_wh` 按需拉起。所以隔离的成本代价不是「三份容量」，而是「多一套配置和多一条冷启动路径」。真正需要警惕的是隔离粒度切太细：每多一个零基线池子就多一条冷启动路径和一份 orphan 状态的风险（Doris 那边我们踩过缩到 0 留下 orphan lease 阻塞别人 compaction 的坑，src: `p_elastic_compute.md:49`）。所以我的判据是按业务语义切，不按团队或按表切。

**L5「这个模式和 Doris 那套是什么关系？重复建设吗？」**
不是重复，是同一个判断在两个引擎上的两次落地，而且第二次做得更简单。共同的骨架是三步：按业务语义物理分池 → 按每个池的风险容忍度选定价模型 → 用一个外部信号（不是资源指标）驱动伸缩。差别在信号来源：StarRocks 这边信号是 fp-async 的 cube coverage（业务侧知识），Doris 那边信号是 FE 里的 `EXPLAIN ROUTE PLAN` 判定（引擎侧知识），后者更彻底，因为它不需要调用方懂业务。这个演进本身就是答案：**如果外部信号能拿到，就不要去改引擎；只有当判定必须发生在 plan time 才值得动引擎。**

**归属边界**
- 能说：三 warehouse 的切分设计与判据、resource group 二层防线、proactive scaling 的流程设计、为什么不用 HPA 的论证。
- **不能说**：spot 中断回退 / 容量准入 / 多集群锁这批 dcluster 平台可靠性代码（git 作者 junhan.ouyang / Runzi Yang）（src: `resume_highlights_doris_dcluster.md` §0）。「dcluster StarRocks CN scaling design & development」在 FY2026 self-assessment 里是我的目标条目（src: `contexts/fy2026_self_assessment.md:8`），所以设计与开发能说，平台可靠性那批不能说。
- **⚠️ 待确认**：`interview-6` 的 gap 清单提到「FE 主备切换未演练（dev 单 FE）」，说明部分环境是 dev。这套三 warehouse 是已上生产还是 preprod 设计，讲之前自己确认清楚。

**可复用到**
01（StarRocks/Iceberg 运维）/ 02（SLO 与容量）/ 07（spot 生命周期）/ 90（跨团队信号契约）

---

## S06 僵尸表清理：一次可靠性事故顺手回收了 TB 级存储（诚实 reframe）

**Headline**
> 一条 Kafka 消费积压告警，真因在三个系统之外：ClickHouse 每次升级改系统日志表 schema 时会把旧表改名保留、从不删除，多次升级之后攒下一张 1.21 TiB 的 trace 日志和一张 308 GiB 的 profiling 日志。这些表没有读者也没有写者，但它们的 parts 仍然参与后台 merge，一次 merge 在一秒内把内存从 2 GiB 顶到 21.60 GiB 上限被杀，把并发写入一起击落。一处确诊之后我立刻做了跨集群审计，最严重的集群查出 1.65 TiB 僵尸表，另一个 region 的同类集群 250 GiB。

**⚠️ 这个故事的 framing 纪律（先读）**
evidence 里这件事**从头到尾是作为 OOM 事故治理写的，没有一处提成本或降本**（src: `adhoc_jobs/dynamic_resume_site/content/incidents/w_zombie_oom.md`）。所以：
- **不要**说「我做了一次存储降本，回收了 3 TB」。那是事后重新包装，被追问「你当时是为了省钱做的吗」会露。
- **可以**说「这件事的主因是可靠性，但它顺带回收了 TB 级存储，而且预防措施本质上就是存储生命周期治理」。诚实的 reframe 是加分的，粉饰过的 reframe 是扣分的。
- 这个故事在成本方向的正确定位是：**「僵尸资源」这个 FinOps 概念我有一手经历，只是发现路径是事故而不是账单审计。** 这恰好能引出一个很好的自我批评：如果有成本异常检测，这 TB 级存储的增长曲线本来应该先被账单发现，而不是等它 OOM。

**适用题型**
清理僵尸资源做过吗 / 讲一个存储成本的例子 / 成本与可靠性的关系 / 一次性清理和建机制的区别 / 一个跨舰队的横向缺陷

**情境与动作（S/A）**
1. 可见信号是 Kafka consumer lag 多租户同时单调上涨，没有流量尖峰可解释；实际是写入 ClickHouse 被 `Code 241 MEMORY_LIMIT_EXCEEDED` 拒绝，每个失败批次触发 30 秒 sleep + rebalance 重试循环（src: `w_zombie_oom.md:14`、`:38`）。
2. 30 秒采集看不见亚秒级故障，靠 ClickHouse 内部 1 秒粒度 metric log 还原真实形状：基线约 2 GiB → 一秒冲到 21.60 GiB 上限 → OvercommitTracker 杀掉 → 回落基线（src: 同上 `:18`、`:42`）。
3. 根因是升级残留：改名后的 trace 日志 1.21 TiB、profiling 日志 308 GiB，无读者无写者，但 parts 仍参与后台 merge（src: 同上 `:20`、`:44`）。
4. 修复要删对范围：`TRUNCATE` 只作用于当前无后缀的表，对僵尸表无效；僵尸表必须显式 `DROP`，用单查询参数绕过 ClickHouse 的 50 GB 删表保护，1 TiB 级 DROP 在 1-3 分钟完成、期间服务不中断（src: 同上 `:24`、`:48`）。
5. **预防分三路（这三条就是这个故事的成本价值所在）**（src: 同上 `:26`、`:50`）：
   - **配置层**：给默认无 TTL 的内部日志表加 TTL；把数据量最大的日志直接关闭；显式钉死服务器内存上限。
   - **流程层**：升级 runbook 末尾新增一步，审计系统表是否出现新的带后缀残留，因为每次升级都会重新制造这个隐患。
   - **舰队层**：一处确诊立即触发跨集群审计，最严重的集群查出 1.65 TiB、另一 region 同类集群 250 GiB，后者已经每天 3 次 OOM 并沿同一曲线爬升。

**结果（R）**
- 回收的存储量：初始集群 1.21 TiB + 308 GiB；跨集群审计另查出最严重集群 1.65 TiB、另一 region 同类集群 250 GiB（src: 同上 `:20`、`:26`）。⚠️ **这几个数字不要相加**，evidence 没写清「最严重的集群」是否就是初始那个，加总会造出一个没有出处的数。
- 机制侧：TTL + 关闭最大量日志 + 升级 runbook 增加审计步骤 + 舰队级审计动作。

**5 层追问防线**

**L1「这算成本优化吗？」**
主动定性，不等他质疑：**主因是可靠性，成本是副产品。** 但我认为它在成本视角有两个真实价值：一是回收了 TB 级的无主存储，那是纯浪费，没有任何人在用；二是预防措施（给无 TTL 的内部日志表加 TTL、把最大量的日志直接关闭）本质上就是数据保留策略治理，那是标准的存储成本手段，只是我当时的驱动是内存而不是账单。

**L2「为什么是 OOM 发现它，而不是账单发现它？」**（这是这个故事最好的一层，要主动往这儿引）
这正是我复盘时最扎心的一条。1 TB 级存储在多个集群持续增长，本来应该是一条很干净的成本异常信号：增长在涨、访问量是零。但我们没有把存储用量做成成本维度的可观测项，所以它一直藏着，直到被一次后台 merge 引爆。这件事之后我对成本可见性的看法变了：成本异常检测不只是省钱工具，它是一类**独立于业务指标的浪费探测器**，能发现「没人在用但一直在长」这种可靠性和成本双风险的东西。这条也是我认为自己在 FinOps 上最该补的能力。

**L3「删 1 TB 级的表你怕不怕？怎么保证安全？」**
安全性在这个案例里是**结构性的，不是靠小心**：这些表既无写入者也无读取者，所以操作在构造上零风险（src: 同上 `:24`）。这比「我很小心地删」强得多。具体做法是绕过 ClickHouse 的 50 GB 删表保护（单查询参数覆盖，不是改全局配置），1 TiB 级 DROP 在 1-3 分钟完成，期间服务持续在线。另外要注意的坑是删对范围：`TRUNCATE` 只作用于当前无后缀的表，对改名后的僵尸表完全无效，这是很容易误以为已经处理了的地方。

**L4「你做的是一次性清理还是建了机制？」**（反模式题，正面回答）
两个都做了，而且我认为只做前者是这类工作最常见的失败：僵尸表是**每次升级都会重新制造的横向缺陷**，清一次没有意义。所以机制是三层：配置层给无 TTL 的表加 TTL（让它自己不再无界增长），流程层把「审计带后缀残留」写进升级 runbook 的最后一步（让下一次升级不再重新埋雷），舰队层定了「一处确诊立即全舰队审计」的动作（因为同升级史的集群必然有同样的残渣）。诚实补一句：这三层里我最不满意的是没有把它做成自动化的检测项，仍然依赖 runbook 里的人工步骤。

**L5「同样的思路还能在哪里找到浪费？」**
判据是同一个：**「在增长但没有访问者」的资源**。云上对应的清单我心里有：未挂载的 EBS 卷、老快照、没有目标的 ELB、未关联的 EIP、空的 ASG、长期不动的 dev/staging 环境、S3 上没有生命周期策略的中间产物、以及监控栈自己的高基数 series。诚实边界：这些云资源侧的清理我**没有系统性做过一遍**（见 S07 的提问清单），我做过的是数据层的这一次。所以我会把它讲成「我在数据层验证了这个判据有效，云资源层是我要补的」。

**归属边界**
诊断、修复、三层预防、跨集群审计都是我做的（src: `w_zombie_oom.md`，SOURCES 指向 `agents/sre_oncall_triage_skill/knowledge/cases/case-clickhouse-system-log-zombie-tables-oom.md`）。**不要把这件事说成成本项目。**

**可复用到**
01（ClickHouse 运维 / 事故）/ 02（监控粒度必须匹配故障时间尺度）/ 90（横向缺陷与舰队级审计）

---

## S07 公司级云成本优化（FY2026 目标达成）：⚠️ 骨架，细节待瑞哥补充

**当前 evidence 状态（先读，很重要）**

`contexts/fy2026_self_assessment.md:9` 把 Cloud cost optimization 列为 FY2026 已达成目标，原文只有一句：

> **Cloud cost optimization**：Reduced cloud spend without degrading throughput or reliability.

全 workspace 搜索确认：**这句话没有任何配套的动作、金额、百分比、时间线或归属信息**（搜索范围与关键词见本目录 `README.md` 的「搜索记录」一节）。self-assessment 的 Q2/Q3/Q4 全部零 cost 内容。

**🚨 更要紧的一件事：`resume-expand.tex` 有两条 cost bullet，其中四个具体声明在 workspace 里查不到支撑**

原文（src: `work-contexts/career/profile/resume-expand.tex:86-90`）：

> *Cost Optimization*
> - Reduced cloud spend by optimizing compute models (**Reserved** baseline, On-Demand scaling, **Spot** for tolerant workloads) while maintaining reliability guardrails and fallback capacity for production services.
> - Improved cost efficiency across compute, storage, and network layers by implementing **storage lifecycle policies**, optimizing **log retention**, and reducing unnecessary **cross-AZ data transfer** in a multi-cluster Kubernetes environment.

支撑度核查：

| bullet 里的声明 | workspace 支撑情况 | 面试风险 |
|---|---|---|
| Spot for tolerant workloads | ✅ 有，两处（S01 Doris heavy 池、S05 StarRocks refresh_wh/adhoc_wh） | 低，可以放心讲 |
| Reserved baseline | ❌ **零支撑**。全 workspace 唯一出现 RI/SP 的地方是 AWS 认证备考材料里的考题与知识表 | **高**。被问「RI 买了多少、覆盖率多少、谁做的决策」会当场断 |
| storage lifecycle policies | ❌ **零支撑**。S3 lifecycle 只出现在认证备考材料 | **高** |
| optimizing log retention | ⚠️ 只有间接：VM retention 分层 90/30/15d（动机是 cardinality，见 S08）、CH 内部日志表加 TTL 与关闭最大量日志（动机是 OOM，见 S06）。**没有任何一处把 log retention 和降本连起来** | 中。能接，但必须诚实说动机不是成本 |
| reducing cross-AZ data transfer | ❌ **零支撑** | **高** |

**行动项（在投这份简历之前必须处理）**：这四条要么瑞哥补出真实经历（回答下面提问清单），要么改简历措辞。**带着查不到支撑的 bullet 进面试，是这个方向最大的单点风险**，面试官只要顺着简历问一句「你们的 RI 覆盖率大概多少」，就会暴露一个比「没做过 FinOps」严重得多的问题。

**其他搜到的弱线索（都需要瑞哥确认）**

1. **「Cost saving dashboard」** 出现在 `contexts/thought_review/career-evolution-diary-22q3-26q1.md:68-72` 的 DV-25Q1 条目里，只有这五个字，零展开。这是全 workspace 唯一暗示他做过成本可视化的记录。
2. **内部服务 `cloud-cost-calculator`** 真实存在（`adhoc_jobs/dynamic_resume_site/knowledge_raw/runbooks/runbook-dns-url-creation-runbook.md:129-145`，ingress `cloud-cost-west-mgt.dv-api.com`，namespace `monitoring`），但那份 runbook 只是拿它当 DNS/ingress 创建流程的举例对象，没有一句说是他建的。
3. **公司环境里部署了 Kubecost**（`periodic_jobs/cross_workspace_daily/extracted/2026-04-27/...` 里一段 curl 的 cookie 带 `kubecostToken` 和 `kubecost-awsapsoutheast1proda.dv-api.com`，同 cookie 列了 29 个集群）。这只证明公司有 Kubecost，不证明他做过 Kubecost 相关工作。
4. **自管 K8s 省下 EKS control plane 费用**：`work-contexts/career/interview/interview-1-k8s_upgrade_reference.md:161` 写「自管理省掉 EKS control plane 费用（$0.10/cluster/hr × 50 ≈ $3,600/month），但 infra 省的钱远不如工程师时间值钱」。这是全 workspace 唯一的公司级绝对金额，但它是**继承的历史决策不是他的动作**，而且他的结论是这笔省钱不划算。**这条反而是很好的素材**：可以拿来答「成本优化的边界在哪」，答法是「省 $3,600/月的基础设施费，代价是 50 个集群的控制面全自己运维，工程师时间比这笔钱贵得多，所以我不认为这是一个好的成本决策」。这展示的是懂得算总成本（TCO）而不只是账单。
5. **VictoriaMetrics 内存降配 120Gi → 40-60Gi** 是 `contexts/thought_review/victoriametrics_ops_review_20260402.md:167` 里的一条 **P3 建议，没有证据说执行了**。别当成 rightsizing 实绩。

**为什么必须补上（不是可选项）**
这是唯一一个公司级、经理认可、写进 self-assessment 的成本成果。S01-S06 都是单个系统的架构级降本，格局高但范围窄；面试官问「你有没有做过跨系统的成本治理 / 你怎么给一个云账单降本」时，只有这个故事能接。而且它带一句极好的措辞（`without degrading throughput or reliability`），那正是「成本与可靠性权衡」这道高频题的答案形状。

**在补上之前的临时口径（面试真被问到就这么说）**
「我做的成本工作主要是架构级的：改变系统结构让成本随负载归零，而不是在既有结构上做运营优化。这一块我有三个能讲透的案例（弹性算力池、按业务语义分 spot、S3 请求费驱动的数据布局治理）。FinOps 的制度化运营那一侧：承诺折扣的组合决策、tagging 治理、showback、账单异常检测：我是有知识但缺一手落地经验的，这是我明确的补课项。」**不要主动提 FY2026 那条自评**，因为讲不深。

**补充完成后的目标形态（写给未来的自己）**
- Headline：一句话说清「哪个成本科目、降了多少、代价是什么」
- 动作分层讲：**先架构后运营**（有架构级动作先讲），运营级的按「归因 → 定位浪费 → 改 → 验证 → 防回退」讲
- 结果必须有 before/after，并说明数字来自哪里（Cost Explorer / CUR / 财务账单 / 自己算的）
- 必须有一条「怎么证明没伤到 throughput 和 reliability」的验证证据，否则那句话是空的

**⚠️ 提问清单（请瑞哥逐条回答，回答完这个故事就能立起来）**

*A. 规模与结果*
1. 降幅是百分比还是绝对金额？大概多少？是月度总账单还是某个服务的账单？
2. 基线和结果分别是什么时候的数？（例如 FY2026 Q1 对比 Q4）
3. 这个数字你从哪里看到的：Cost Explorer、CUR、Kubecost、财务给的账单，还是自己算的？

*B. 动作（可多选，请标出哪几条真的做了，以及做到什么程度）*
4. rightsizing：调过实例规格还是调过 K8s requests/limits？针对什么？判断可以调小的依据是什么指标（只看 CPU 还是也看内存/网络/burst）？
5. 清理僵尸资源：未挂载 EBS 卷、老快照、闲置 ELB、未关联 EIP、空 ASG、废弃 dev/test 环境，有没有做过一遍盘点？
6. 实例族更换：老代次换新代次？x86 换 Graviton？如果换过 Graviton，遇到什么兼容问题（镜像、二进制、JVM、CNI）？
7. 存储分层：S3 生命周期策略、Glacier、gp2 → gp3、快照归档，做过哪些？
8. 提高 spot 占比：除了 Doris heavy 池和 StarRocks refresh/adhoc warehouse，还有别的 workload 上了 spot 吗？
9. 关闭闲置环境：非工作时间关 dev/staging？做成自动化了吗（定时 scale-to-zero / suspend ASG）？
10. **承诺折扣（这条最关键，因为简历上写了 Reserved baseline）**：RI 或 Savings Plans 是你参与决策的吗？还是财务/别人买的？你有没有看过 coverage 和 utilization 这两个数？如果没参与，简历那条 bullet 要改。
11. 监控自身的成本：指标 retention、series cardinality、日志量，VictoriaMetrics 那次迁移有没有算过成本收益？（现在 evidence 里驱动都是可靠性）
12. **网络成本（简历上写了 cross-AZ）**：做过流量成本审计吗？NAT Gateway 处理费看过吗？加过 VPC Endpoint 吗？跨 AZ 流量具体减了什么（是把 pod 调度收到同 AZ，还是加了 topology aware routing，还是别的）？
13. 数据层降本：ClickHouse / Kafka / MySQL / YugabyteDB 的容量、副本数、保留期有没有调过？
14. **「Cost saving dashboard」（DV-25Q1）那条到底是什么？** 是你建的吗？展示什么数据？数据源是 Cost Explorer、CUR 还是 Kubecost？还在用吗？
15. **公司的 Kubecost 你用过吗？** 谁维护的？有没有从它拿过数据做决策？

*C. 过程与归属（面试最爱追问这块）*
16. 这件事是谁提出的？你自己发现的，还是老板/财务派下来的任务？
17. 你是主导（定方向、拆任务、推进）还是执行（别人定了你做）？
18. 有没有需要说服别人的环节？谁反对？理由是什么？怎么说服的？
19. 有没有做成机制（周期性 review、告警、看板），还是一次性清理？
20. `without degrading throughput or reliability` 这句你**怎么证明的**？有 before/after 的延迟或错误率对比吗？有没有踩过「省了钱结果出问题」的坑（哪怕差点）？

*D. 加分项*
21. tagging / 成本归因：公司的成本能拆到 team / tenant / 环境粒度吗？你参与过 tag 规范或治理吗？
22. 有没有把某个成本数字变成常态化的可观测指标（进 Grafana 那种）？

---

## S08 可观测性自身的成本：一次「资源省了、可靠性还变好了」的重构

**Headline**
> 全局 Prometheus 在 federation 拓扑顶端每周 OOM 两三次，head block 里 1.2M series 要 5-10GB 内存维持。换成 VictoriaMetrics 之后，同一个 3 个月窗口的热存储从约 930GB 降到约 250GB（约 4× 压缩），冷数据用 5 分钟降采样存 S3，180 天只要约 25GB。这个故事的价值在于它同时是可靠性故事和成本故事：省资源不是靠砍数据，是靠换存储引擎加显式的 retention 分层。

**适用题型**
可观测性成本怎么控 / 既提升可靠性又降低成本的例子 / 指标 cardinality 怎么治 / 数据保留策略怎么定

**情境与动作（S/A）**
- 痛点：federation 顶端全局 Prometheus 每周 OOM 2-3 次，head block 1.2M series 花 5-10GB 内存；崩溃重启留数据空洞，空洞又 page 出不存在的故障。延迟侧是结构性的：federation 叠两层 scrape interval（集群 15s + 全局 30s），全局视图最多滞后 45 秒（src: `adhoc_jobs/dynamic_resume_site/content/projects/p_vm_platform.md:15`）。
- 容量从实测输入设计：50 集群 × 约 12 节点 ≈ 600 节点，每节点约 2,000 series → 约 1.2M active series、15s scrape 下约 80,000 samples/s（src: 同上 `:25`）。
- **热存储：3 个月约 250GB SSD，约 4× 压缩；同一窗口在 federation 下要约 930GB**（src: 同上 `:25`、`:147`）。
- **冷存储：5 分钟降采样放 S3，180 天约 25GB**（src: 同上 `:25`）。
- **cardinality 治理四条**：tenant 级 recording rules 只覆盖核心 SLI；基础设施指标一律不带 tenant label；retention 分层（tenant SLA 序列 90 天 / 排障序列 30 天 / 基础设施 15 天）；定期 cardinality 审查清理意外的高基数 label（src: 同上 `:62`、`:127`；另 `work-contexts/career/interview/interview-3-monitoring_reference.md:130`）。
- recording rules 本身也降查询成本（src: `work-contexts/career/interview/interview-3-monitoring.md:68`）。

**结果（R）**
- OOM 每周 2-3 次 → 零；数据滞后 45s → <5s（src: `90_cross_cutting/number_baseline.md` §2）。
- 热存储同窗口体积 930GB → 250GB（src: `p_vm_platform.md:25`、`:147`）。
- 运维面收缩：新集群接入从「写 federation rules 加改全局 scrape 配置」变成「部署 vmagent，配一个 remote_write 地址」（src: 同上 `:133`）。

**5 层追问防线**

**L1「这算成本优化吗？算过省了多少钱吗？」**
诚实答：**我没有把它当成本项目做，也没有算过美元金额**，当时的驱动是可靠性（OOM 和数据空洞）加延迟（45s 滞后）。但它确实带来成本收益，而且方向可量化：同一个 3 个月窗口的热存储从约 930GB 降到约 250GB，冷数据落 S3 后 180 天只占约 25GB。要美元化就是 SSD 容量费差额加一份很小的 S3 费用。事后看这是我的一个遗憾：一个天然带成本收益的项目，我只汇报了可靠性收益。

**L2「retention 分层的分界线怎么定的？90/30/15 有依据吗？」**
依据是**这份数据被用来做什么决策、那个决策的时间窗口有多长**：tenant SLA 序列要支撑月度和季度的 SLA 对话，所以 90 天；排障序列服务事后复盘，一个月足够覆盖「上次这样是什么时候」；基础设施指标基本只在当下排障用，15 天。这不是精算，是按用途分层，但比「统一存一年」省得多且不牺牲用途。诚实补一句：这三个数当时没有做「删了之后有没有人来找」的验证，更稳的做法是留一个降采样档而不是直接删。

**L3「cardinality 怎么防它涨回来？」**
三个显式约束加一次定期动作：核心 SLI 才做 tenant-level recording rules（不是所有指标都加租户维度）；基础设施指标一律不带 tenant label（这条最省，因为节点级指标乘租户数是最大的爆炸源）；定期 cardinality 审查抓意外的高基数 label（src: `p_vm_platform.md:62`）。**但我的诚实复盘是：cardinality budget 应该在第一天就存在，而不是等增长曲线逼出来**（src: 同上 `:62`、`:127`）。这句话我会主动说，因为它是这个故事里最有价值的一课：成本护栏要在系统上线前定，事后治理永远是被动的。

**L4「有没有为了省成本丢过需要的数据？」**
我知道的范围内没出过事，但也承认没做过「删除影响」的正式验证（见 L2）。我做的一件事是把冷数据降采样而不是删除：5 分钟粒度的 180 天数据只占约 25GB，代价是丢了秒级细节。这是有意识的取舍：长周期趋势不需要秒级，短周期排障不需要 180 天。真正危险的是把这两种需求用同一份数据、同一个 retention 去满足。
另外有一个反面教训可以配着讲（来自 S06）：ClickHouse 那次事故里，一张 1 TB 级的僵尸日志表在多个集群持续增长，没人读也没人写，最后是 OOM 发现它而不是账单发现它。所以我对「删数据有风险」的看法是分两类的：删有人用的数据要验证，清理无主的数据是纯收益。

**L5「日志侧呢？日志通常比指标贵得多。」**（诚实边界）
我们的栈里 Loki 是有的（src: `p_vm_platform.md` 覆盖 VM + Grafana + Loki），但**日志的采样和保留策略我没有系统性做过**，这是明确的补课项。理论上我知道该做什么：按 stream 分级保留、结构化字段进 label 但高基数字段留在 body（Loki 的 label 基数直接决定索引成本和查询成本）、error 级别长留 debug 级别短留、对高频重复日志采样。我做过的最接近的是 ClickHouse 那次给无 TTL 的内部日志表加 TTL、把数据量最大的日志直接关闭（src: `w_zombie_oom.md:26`），但那次的驱动是 OOM 不是账单。所以我会说：日志的成本治理我有零散动作，没有体系，不装。

**归属边界**
Prometheus Federation → VictoriaMetrics 迁移、容量设计、cardinality 治理四条、retention 分层都是我做的（src: `p_vm_platform.md`、`resume.tex`）。**没做过日志成本治理，没算过美元收益**，两条都主动承认。VM 内存 120Gi → 40-60Gi 降配是一条 P3 建议，**没有证据说执行了**（src: `contexts/thought_review/victoriametrics_ops_review_20260402.md:167`），不要当成 rightsizing 实绩。

**可复用到**
02 监控/SLO（主场）/ 90（既提升可靠性又降成本的行为面素材）

---

## 故事选用速查

| 面试官问什么 | 主打 | 备选 |
|---|---|---|
| 讲一个你做的成本优化 | S01 | S04、S05 |
| 你怎么给一个云账单降本（方法论题） | 先答方法论骨架（见 `questions.md` Q11），故事挂 S01 + S04 | S05 |
| 你怎么衡量成本效率 | S02 | S04 |
| 存储成本怎么优化 | S03 + S04 | S06、S08 |
| S3 有什么成本坑 | S04 | S03 |
| 不影响 SLO 怎么降本 | S05（按风险容忍度分池）+ S01 的 L2 | S04 的 L3（跟业务谈 trade-off） |
| spot 敢不敢用 / 怎么用 | S05 + S01 的 L3/L4 | 无 |
| 清理僵尸资源做过吗 | S06（带诚实 reframe） | 无 |
| 可观测性成本 | S08 | S06 |
| 跨系统的成本治理做过吗 | ⚠️ S07 补完前只能用临时口径 | S05（两个引擎上做过同一套模式） |
| 用数据改变决策 | S02 | S04 |
| RI / Savings Plans 怎么选 | ⚠️ 无一手经验，答理论 + 承认边界（见 `questions.md` Q6-Q8） | 无 |
