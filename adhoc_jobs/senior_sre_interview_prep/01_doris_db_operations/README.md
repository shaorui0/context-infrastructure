# 方向 01：Doris / DB 运维 / HA / 存算分离 / 数据层监控

> 本方向是资产最厚的方向，面试时当主力讲。
> 所有数字后面的 `(src: ...)` 是相对 workspace 根 `/Users/rshao/work/context-infrastructure` 的路径。
> 私人备考材料，不脱敏。四件套：本文件 + `story_bank.md` + `fundamentals.md` + `questions.md`。

---

## 0. 这个方向我的一句话定位

我是一个把 OLAP 存算分离从引擎内部改到基础设施弹性、两端都动过手的 SRE。我负责的这层是反欺诈平台的事件存储，同时要服务毫秒级点查的 serving 流量和越来越多由 AI agent 产生的不可预测 ad-hoc 分析。旧的 ClickHouse shared-nothing 层对后者既不能隔离也不能弹性伸缩，我实测过一条 `SELECT * LIMIT 10` 墙钟排了 61 秒而 CPU 只用了 60 毫秒，排在一个 bulk insert 后面 `(src: adhoc_jobs/dynamic_resume_site/content/case_study_ch_to_doris.md)`。所以我做的不是一次迁移，是把这一层重建在存算分离上，并且把查询路由做进了 Doris frontend 本身：每条查询在执行前 6 到 8 毫秒判定 heavy/light，heavy 判定驱动一个 spot 计算池从 0 拉起、用完缩回 0。

用面试的语言说，我的能力形状不是「会运维某个数据库」，而是三段连起来：**能读引擎源码判断信号在哪里失真、能把这个信号变成准入控制策略、能把策略接到基础设施的弹性控制面上**。我扛得住的追问深度是优化器的统计置信度、compaction 的债务模型、对象存储上的扇出成本这一层；我明确不扛的是 MySQL 的 failover 谱系和 Kafka broker 层的容量工程，那些我按理论答并主动交代边界。

一句话的自我介绍版本（30 秒可直接用）：

> 我在 Datavisor 负责反欺诈平台的数据层可靠性。最近一年最主要的工作是把一张 3,700 列、约 52 亿行的事件宽表从 ClickHouse 重建到 Apache Doris 存算分离，并且为了让 serving 和 ad-hoc 分析共存，我在 Doris fork 的 FE 里实现了两条新的 EXPLAIN 语句做执行前的准入路由，同时在基础设施侧做了对应的 scale-to-zero 弹性计算控制面。这条线让我把 OLAP 的引擎内部和运维外部打通了。

---

## 1. 核心圈三环

### 内核（一手做过，扛得住 5 层追问）

| 环 | 能力条目 | 一句话说明 | evidence 路径 |
|---|---|---|---|
| 内核 | 存算分离 OLAP 架构选型与落地 | Doris 4.0.5 shared-data：S3 storage vault + MetaService + FoundationDB + 无状态 BE + 本地 EBS 做 file cache；能讲清「存算分离不是消除状态，是把状态集中到一层，而那一层从此不能偷工减料」 | `adhoc_jobs/dynamic_resume_site/content/case_study_ch_to_doris.md`、`contexts/survey_sessions/clickhouse_vs_doris_storage_compute_ai_load_survey_20260716.md` |
| 内核 | 超宽表大规模迁移的内存工程 | 3,700 列把「导出 Parquet 再 bulk load」在四个地方压爆内存（footer 爆炸、不受 `exec_mem_limit` 约束的 scanner、export buffer 跷跷板、内存随表增长而非随批次增长），加硬件一个都解决不了 | `adhoc_jobs/dynamic_resume_site/content/case_study_ch_to_doris.md`、`contexts/survey_sessions/ch_to_doris_migration_interview_arsenal_20260717.md` |
| 内核 | 引擎级查询路由与准入控制 | 在 Apache Doris fork 的 FE 里实现 `EXPLAIN ESTIMATE PLAN`（只读遍历定稿物理计划，吐 CBO 已算好的逐算子估算）+ `EXPLAIN ROUTE PLAN`（15 条规则分类器，6-8ms 出 verdict）；核心判断是「路由是准入控制不是性能优化」 | `adhoc_jobs/dynamic_resume_site/content/projects/p_engine_routing.md`、`contexts/resume_highlights_doris_dcluster.md` §3/§4 |
| 内核 | 弹性计算控制面（scale-to-zero） | heavy 池常驻 0 副本，verdict 判 heavy 则 JSON-patch 算子 CR 的 `replicas`，节点约 66s、backend 注册约 2min，空闲 reaper 回收到 0；at-least-once 调用下的幂等扩缩语义 + 队列去抖状态机 | `adhoc_jobs/dynamic_resume_site/content/projects/p_elastic_compute.md`、`contexts/resume_highlights_doris_dcluster.md` §2 |
| 内核 | Doris compaction / tablet / rowset 运维 | 两次独立事故的根因链都能讲到机制层：score ~2,500 的死亡螺旋（三因连乘）和 score ~4,504 的孤儿 tablet 卡死（三条独立证据链收敛） | `adhoc_jobs/dynamic_resume_site/content/case_study_ch_to_doris.md`、`adhoc_jobs/dynamic_resume_site/content_plan.md` |
| 内核 | OLAP 点查性能工程 | 能把点查慢分解成三层可叠加、可分离的成本：tablet/segment 扇出（冷暖共有的地板）、列读放大、segment V2 footer 元数据税；结论是「扇出是地板不是 S3」，最大杠杆是分区剪枝而不是加带宽加 BE | `contexts/survey_sessions/doris_wide_table_point_query_optimization_survey_20260724.md` |
| 内核 | ClickHouse 生产运维与事故定位 | system 表取证（`system.metric_log` 1 秒粒度、`system.processes` + `top -H` 交叉验证、`system.query_log` 74.7M 行负载画像挖掘）、亚秒级 OOM、升级残留僵尸表、逐跳定位 connection refused | `adhoc_jobs/dynamic_resume_site/content/incidents/w_zombie_oom.md`、`adhoc_jobs/dynamic_resume_site/content/integration/oncall_track_record.md`、`adhoc_jobs/dynamic_resume_site/content/integration/case_cards.json` |
| 内核 | 数据迁移的正确性工程 | 三层保证（每月无损行数门禁 + watchdog kill 的原子 abort + Unique Key/MoW 去重）；99.945% 行级对账，0.055% 缺口逐行归因到去重语义；对账方法本身要为安全性重新设计（朴素 `COUNT(*)` 打挂过 8 台 BE） | `adhoc_jobs/dynamic_resume_site/content/case_study_ch_to_doris.md`、`contexts/survey_sessions/ch_to_doris_migration_interview_arsenal_20260717.md` |

内核共 **8 条**。

### 中环（做过但浅，或只碰过一次，每条附被追问时的标准口径）

| 环 | 能力条目 | 一句话说明 | evidence + 标准口径 |
|---|---|---|---|
| 中环 | Iceberg / StarRocks lakehouse | Kafka Connect + 自研 SMT 落 S3 Iceberg，StarRocks 存算分离查询 + MV 预聚合；小文件 619→49、热查询 12.2s→247ms | src: `work-contexts/career/interview/interview-6-starrocks-lakehouse.md`。**口径**：「部署和性能工程是我做的，运维成熟度上我自己在 FY2026 self-assessment 里就写了要从 deployment proficiency 走到 full lifecycle ownership，maintenance pattern 和 failure mode 的 runbook 还不完整」`(src: contexts/fy2026_self_assessment.md Q2)` |
| 中环 | 备份恢复 / DR | 跨集群 ClickHouse 恢复走 EBS snapshot + PV/PVC 置换 + 重启 + 校验，恢复量级 ~5.2B 行 | src: `adhoc_jobs/dynamic_resume_site/content/integration/case_cards.json` (dr-restore-false-failure)、`adhoc_jobs/dynamic_resume_site/content_plan.md`。**口径**：「这是一次性演练不是制度化的 DR，RPO 是 snapshot 周期隐含的约 24 小时，我们没有做过定期恢复演练，也没有把 RTO 写成 SLO。我能讲的是那次恢复里控制面报失败而数据面其实已经好了这个判断，以及为什么把校验门槛从 pod-ready 改成 TCP 9000 加真实 SQL 探测」 |
| 中环 | OLAP SLI/SLO 体系 | 定过监控指标和 SLA 规范，四支柱（查询可用性 / 查询延迟分冷热 / 导入成功率 / 数据新鲜度）；StarRocks 侧做过两视角 SLI（全局聚合 = infra 视角，label 切片 = 用户视角） | src: `contexts/survey_sessions/ch_to_doris_migration_interview_arsenal_20260717.md` §3.B、`work-contexts/career/interview/interview-6-starrocks-lakehouse.md` §5。**口径**：「指标定义和阈值论证是我做的，51 个 infra SLI 里 64% 可用、32% 缺 instrumentation，用户视角覆盖不到 10%。error budget policy 和多窗口 burn rate 告警我是按设计写的，没有跑满一个季度形成制度」 |
| 中环 | 存算分离的 HA 拓扑与恢复链路 | 组件层（FE / MetaService / FoundationDB / Recycler）× 业务层（compute group / workload group）两层正交；元数据恢复链路多一跳 FE BDB-JE → MS → FDB | src: `work-contexts/career/interview/interview-8-doris-query-routing-oom.md` §Q8。**口径**：「拓扑和失败域我能画清楚，MS/FDB 都是 ≥3。但 `fdbrestore` from S3 我没有实际演练过，RTO 小时级是我的推断不是实测。这是我知道的最大一块没验证的地方」 |
| 中环 | Kafka / MirrorMaker 运维 | 做过 mirror lag 的容量归因（大租户 QPS 增长超过 topic 3 个 partition 能承载的复制吞吐，per-partition 吞吐是硬天花板）、KRaft liveness probe 误杀 quorum 的修复 | src: `adhoc_jobs/dynamic_resume_site/content/integration/oncall_track_record.md` §4/§6、`adhoc_jobs/dynamic_resume_site/content/integration/case_cards.json`。**口径**：「Kafka 我是从 oncall 和归因进去的，不是从 broker 调优进去的。partition 扩容我标成了不可逆操作、要先评 key 分布，评审是我提的，执行不是我做的」 |
| 中环 | ClickHouse 集群拓扑与复制层 | shard + replica 拓扑、ReplicatedMergeTree 依赖 ZK/Keeper 做元数据协调、TTL 与冷热分层、part 数与 merge 压力 | src: `work-contexts/career/interview/interview-clickhouse-sre.md`。**口径**：「我是在既有拓扑上做运维、调优和事故定位，不是从零设计 shard/replica 布局。Keeper 层我能讲它挂了会怎样，但没做过 Keeper 自身的容量规划和迁移」 |
| 中环 | Arrow Flight 传输 | 路由 verdict 里带 transport hint（Arrow Flight vs MySQL 协议） | src: `contexts/resume_highlights_doris_dcluster.md` §0。**口径（必须一字不差）**：「ROUTE PLAN 分类器是我在 Doris fork 里实现的；Arrow Flight 传输是我定的输出契约和 fallback 行为设计，实现是伙伴团队做的」 |
| 中环 | 上游开源参与 | `EXPLAIN ESTIMATE PLAN` 打成 8 commit 的干净 PR，对着 synthetic base branch，diff 恰好是 feature 本身；分类器刻意不提议 merge | src: `adhoc_jobs/dynamic_resume_site/content/projects/p_engine_routing.md`。**口径**：「这是 engine-level work on an Apache Doris fork, prepared as an upstream PR / proposed as DSIP。PR 没 merge 之前我不说 contributed to Apache Doris」 |
| 中环 | spot 用于数据层 | heavy 池在构造上容忍中断（FE 约 2s 心跳检测、锁约 7s 释放、失败查询重试一次，全落在 spot 2 分钟回收窗口内），spot 价格比 on-demand 低约 62% | src: `adhoc_jobs/dynamic_resume_site/content/projects/p_elastic_compute.md`。**口径**：「serving 池永远不上 spot。heavy 池的实际决策是装好 node-termination handler 之前先用 on-demand，之后才切 spot 优先的混合 ASG。所以我讲的是决策框架和实测 node-hours，不是已经跑在 spot 上」 |

中环共 **9 条**。

### 外环（需补课，对应内容在 `fundamentals.md`）

| 环 | 能力条目 | 一句话说明 | 补课标记 |
|---|---|---|---|
| 外环 | MySQL 深度运维 | 复制拓扑（异步 / semi-sync / Group Replication）、failover 方案谱系（MHA / Orchestrator / ProxySQL / RDS 托管）、xtrabackup 物理备份与 PITR、buffer pool 与双 1 配置 | 需补课。现有材料 `work-contexts/career/interview/interview-mysql-sre.md` 是纯理论框架，文末 STAR 模板明确写着「根据自己的实际经历调整」，**不是他的真实经历，绝不能当故事讲**。他的一手 MySQL 经验只有 oncall 侧：MySQL connect timeout 跟着某个 worker 节点走（节点级 DNS/出网故障）、CDC 上游 DDL 从 4 列改 2 列引发三连崩 `(src: adhoc_jobs/dynamic_resume_site/content/integration/case_cards.json)` |
| 外环 | Kafka broker 层深度调优与容量规划 | `num.io.threads` / retention / `min.insync.replicas` 与 `acks=all` 的取舍、page cache 主导的内存模型、磁盘容量公式 | 需补课。`work-contexts/career/interview/interview-kafka-sre.md` 是理论框架，STAR 模板同样是待填空模板 |
| 外环 | DB HA 的通用谱系 | 主从复制 / 共识协议（Raft、Paxos、Group Replication）/ 无共享 + 共享存储三类的一致性与可用性边界，托管服务（RDS/Aurora）failover 语义 | 需补课。他的一手 quorum 经验是 BDB-JE（3 FE 容忍 1 故障，`floor(N/2)+1`）和 Kafka KRaft controller 选举，都是「被它咬过」而不是「设计过」 `(src: work-contexts/career/interview/interview-6-starrocks-lakehouse.md §9)` |
| 外环 | Doris 之外的存算分离实操 | ClickHouse Cloud SharedMergeTree、StarRocks shared-data、Snowflake/Databricks 的弹性模型 | 需补课，但**调研深度已经足够答选型题**：SharedMergeTree 闭源不进开源、AI 负载真正的三个命门是计费/唤醒粒度、多租户 blast radius、对象存储冷查询延迟 `(src: contexts/survey_sessions/clickhouse_vs_doris_storage_compute_ai_load_survey_20260716.md)`。缺的是实操 |
| 外环 | Doris 优化器本身（cost model / 统计推导 / 优化规则） | 他做的是观测层，明确没改 cost model、没加优化规则、没改 plan 选择 | 需补课且**必须主动划界**：「ESTIMATE 是读取 CBO 自身状态并修正它已知的谎言，不改 CBO」 `(src: contexts/resume_highlights_doris_dcluster.md §3 深度定级)` |
| 外环 | 数据库安全与合规 | 静态/传输加密、审计日志、行列级权限、SOC2/PCI 场景下的数据库控制项 | 需补课。九域雷达里安全与合规 40 分是最低分，且 SOC2/PCI/IAM 的真实经历还是 pending 状态 `(src: adhoc_jobs/dynamic_resume_site/content_plan.md)` |

外环共 **6 条**。

---

## 2. 本方向 3 个最强 headline（开场 30 秒选一个）

1. **我在 Apache Doris fork 的 frontend 里加了两条 SQL 语句，让每条查询在执行前 6 到 8 毫秒判定 heavy 还是 light，heavy 召回率从原生 EXPLAIN 的 7% 做到 100%。** 承重的不是 100%，是我先证明了静态方案结构性不可能：同一个模板换参数，EXPLAIN 输出逐字节相同，而真实内存差 23 倍。这是 signal problem 不是 rule problem。`(src: adhoc_jobs/dynamic_resume_site/content/projects/p_engine_routing.md)`

2. **我把一张 3,700 列、约 52 亿行、约 4 TiB 的事件宽表重建到存算分离上，99.945% 行级对账，点查从约 8 秒做到约 20 毫秒，并且证明了这个延迟在数据涨 19 倍时保持平坦。** 分布键是唯一 ALTER 不了的决策，所以我在提交之前跑了同数据镜像键的两表 A/B、四次测量，再在 15M / 107M / 286M 三个检查点各复测一次。`(src: adhoc_jobs/dynamic_resume_site/content/case_study_ch_to_doris.md)`

3. **我证明过一个反直觉的结论：宽表点查慢的地板不是 S3，是扇出。** 一个活跃用户的行散落在 2,044 个分区文件里，bloom filter 砍掉 73% 的扫描行而墙钟一动不动，因为地板是 file-open 次数不是扫描行数。后来在 Doris 侧我又抓到同一个模式的暖查询证据：缓存全命中、几乎零 S3，仍然要 1.12 秒，时间全花在跨 8 个 BE 扇出到 566 个 tablet、6,689 个 segment 逐个打开倒排 searcher。索引修不了布局问题。`(src: adhoc_jobs/dynamic_resume_site/content/case_study_ch_to_doris.md、contexts/survey_sessions/doris_wide_table_point_query_optimization_survey_20260724.md)`

---

## 3. 开场纪律（`research/interview_story.md` 已定稿，不许违反）

来源：`adhoc_jobs/dynamic_resume_site/research/interview_story.md` §不要讲（负面清单）。

- **不以 99.945% 对账开场或展开。** 那是尽职信号（P7），不是架构信号。降级为追问弹药。
- **不背 K8s 救火清单。** operator 信号，收进弹药库，问到再抛。
- **不在前 60 秒交代 preprod-only。** 放结尾，配「10T 生产化推进中」顶回去。
- **不过度渲染 AI agent。** 必须立刻钉在实测的 61s/60ms 饥饿案例上，防止「具体哪个 agent、上线了吗」的追问悬空。
- **不主动打开 benchmark 诚实性长征。** 被问「你的数字可信吗」时才抛，那时它是满分答案。
- **删掉一切「I also」「顺手」这类 scope-diminishing 措辞。** 三张王牌（改引擎本身、设计允许分类器不完美的两层安全架构、改变 leadership 的开源决策）不许放在从句位置。

3 分钟版排序（照抄执行）：why-now 钩子 20s → 结构性问题框定 30s（明说论证不建立在 CH 慢上）→ 两件最硬的事 headline 先行 40s → 引擎级 war story 选 compaction 死亡螺旋 30s → 判断力 headline（决定什么不该开源）20s → 边界加结果收尾 20s。

---

## 4. ⚠️ 口径漂移清单（3-6 月材料 vs 7 月材料，一律以 7 月为准）

1. ⚠️ 口径漂移：分类器规则数 13 条 → **15 条**，以 7 月为准。`(旧: work-contexts/career/interview/interview-8-doris-query-routing-oom.md; 新: adhoc_jobs/dynamic_resume_site/content/projects/p_engine_routing.md)`
2. ⚠️ 口径漂移：ESTIMATE PLAN 补丁体量 7 files / +589 / -0、`PlanEstimateCollector` 454 行 → **PR 形态 15 files / +1,310 行、`PlanEstimateCollector` 792 行**，以 7 月为准（6 月是早期 commit 口径，7 月是打包成 8-commit PR 并经过后续加固的口径）。零删除这一点两版一致，可以放心讲。`(旧: interview-8-...; 新: p_engine_routing.md、contexts/resume_highlights_doris_dcluster.md §3)`
3. ⚠️ 口径漂移：golden corpus 189/189 → **189 起步、演进到 197**，断言下限逐次抬高。对外说「189/189 在任何集群存在之前就全过，后来加到 197」。`(src: p_engine_routing.md、contexts/resume_highlights_doris_dcluster.md §4)`
4. ⚠️ 口径漂移：准确率表述「ad-hoc 准确率 45%→86%」→ **统一说「heavy recall 7%→100%（15/15），light precision 86%」**，以 7 月为准。承重数字是 27% 的 heavy-miss 率（安全问题），不是 45% 这个头条。`(旧: interview-8-...; 新: p_engine_routing.md)`
5. ⚠️ 口径漂移：测试套件条数 66→70 条 × 9 series → **52 条真实工作负载 eval suite（三角验证：约 1,900 列真实 schema、平台真实生产 SQL 模板、业务查询 taxonomy）**，以 7 月为准。66/70 是更早一版的覆盖套件计数，问到再展开。`(旧: interview-8-...; 新: p_engine_routing.md、contexts/resume_highlights_doris_dcluster.md §4)`
6. ⚠️ 表规模的时间差（不是冲突，是表在长）：迁移对账口径是 **~5.2B 行 / ~4 TiB source / ~3,700 列**（精确值 5,170,688,484 of 5,173,508,562，2026-07 完成对账时）；2026-07-24 现场实测已长到 5,471,146,590 行 / 4.002 TB / 566 tablet。**对外统一用 ~5.2B / ~4 TiB / ~3,700 列**，被问增长时才用 5.47B。用户口述的 6B/6T 无出处，不用。`(src: case_study_ch_to_doris.md、doris_wide_table_point_query_optimization_survey_20260724.md、content_plan.md)`
7. ⚠️ 集群数全站统一 **50**，不用其他数。`(src: adhoc_jobs/dynamic_resume_site/content_plan.md)`
8. ⚠️ 「存储成本降 90%」是 **Doris 官方口径不是自测**，讲的时候必须带这句限定。官方另一个口径是 100TB 在线数据从三副本约 3.7 万美元/月降到单副本约 2.2 万（约 40%），历史冷数据可降 90%+。`(src: contexts/survey_sessions/clickhouse_vs_doris_storage_compute_ai_load_survey_20260716.md、ch_to_doris_migration_interview_arsenal_20260717.md §3.D)`
9. ⚠️ 两次 compaction 事故**必须分开讲**：score ~2,500 是 disable_auto_compaction 造成的死亡螺旋，score ~4,504 是 DROP 表留下的孤儿 tablet 卡死。用户记忆里的「5k」指的是后者。`(src: adhoc_jobs/dynamic_resume_site/content_plan.md)`

---

## 5. ⚠️ 待确认清单（找不到出处，不许用常识补全）

1. ⚠️ 待确认：FY2026 self-assessment 里「Cloud cost optimization：reduced cloud spend without degrading throughput or reliability」是已达成目标，但**具体做了什么动作、省了多少、口径是什么，evidence 里没有**。dcluster heavy 池 floor-0 的省 92%/97% 是架构级测算，不等于公司级账单降本。面试被问「你做过降本吗」时，只讲 dcluster 那笔算术，公司级降本不主动提。`(src: contexts/fy2026_self_assessment.md Q1.5)`
2. ⚠️ 待确认：`p_elastic_compute.md` 提到「缩到 0 的 compute group 可能在元数据服务里留下一个 orphan lease，在过期之前阻塞其他 group 的 compaction」，但**lease 的过期时长、当时的影响面、最终怎么处置的**都没有记录。只能讲到「这是踩过的坑，所以 idle 状态需要专门的运维审视」这一层，被追细节要说没记全。
3. ⚠️ 待确认：ClickHouse 侧的「集群部署与复制拓扑」到底是他建的还是他接手运维的，`interview-clickhouse-sre.md` 的 opening 写的是 "I own the deployment and cluster topology"，但那是 4 月写的答题框架而不是事实记录，其他 evidence 里没有印证。**按中环口径讲（在既有拓扑上运维），不声称从零设计。**
4. ⚠️ 待确认：Iceberg 部署的边界。`fy2026_self_assessment.md` 只写了 "Deployed Iceberg and StarRocks"，`interview-6` 里有 nightly `rewrite_data_files` / `expire_snapshots` / `remove_orphan_files` 三件套和 `iceberg_data_file_count < 10000` 的 SLO，但**这套 maintenance job 是设计还是已经在跑，没有记录**。按「部署到位、lifecycle 维护是设计态」讲。
5. ⚠️ 待确认：`interview-8` 说 L2 的 Workload Group 硬限「部分仍是设计/配置态，动态 `MOVE_TO_GROUP` 未实测」，而 `case_study_ch_to_doris.md` 说漏网 heavy「死在约 404 MB/query 的固定槽位硬限里、约 3 秒内被杀、自动升级到 heavy 池」并称端到端验证过。**两者哪个是最终状态没有明确记录**，按 7 月为准（已验证），但被追问「MOVE_TO_GROUP 跑通了吗」时要如实说动态 DDL 那条路我没依赖。
6. ⚠️ 待确认：DR 那次恢复的 RTO 实测时长、snapshot 的实际周期。只有「RPO≈24h 隐含」这个标注，没有数字。
