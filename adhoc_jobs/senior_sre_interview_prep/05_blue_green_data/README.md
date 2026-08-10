# 05 · Blue/Green 集群与数据层切换

## 这个方向我的一句话定位

我真正的差异化不在无状态服务的 canary，那是人人都会讲的一层。我的战场是**有状态系统与数据层的切换**：以集群为单位的 blue/green 加跨集群 Kafka 复制的暂停与追平、51.7 亿行超宽表跨引擎迁移的可解释对账、以及一次监控栈换引擎时用双写并行加逐规则语义 diff 做切换门禁。这三件事共享同一套设计判断：**切换的难点从来不在「怎么切」，而在「凭什么证明可以切」和「切错了还能不能回来」。** 我能在白板上画出一套十二环节的切换骨架，说清每一环的判据，也能诚实地指出我的每个故事各自跳过了哪几环、为什么跳、如果重来会怎么补。

配套文件：`methodology.md`（切换方法论骨架，本目录的核心原创产物）、`story_bank.md`（3 个主故事 + 1 个短故事，各配 5 层追问防线）、`questions.md`（17 题答题骨架）。

---

## 核心圈三环

### 内核（一手 evidence，能扛住 5 层追问）

| 环 | 能力条目 | 一句话说明 | evidence 路径 |
|---|---|---|---|
| 内核 | 集群级 blue/green（K8s 升级） | 双集群流量前置转移：流量整体转到对侧、暂停跨集群 Kafka 复制、升级已 dark 的一侧、恢复复制等 lag 降回阈值、验证后切回；50 集群 1.24→1.29 零事故零回滚 | `adhoc_jobs/dynamic_resume_site/content/projects/p_k8s_upgrade.md`、`adhoc_jobs/dynamic_resume_site/knowledge_raw/runbooks/runbook-k8s-upgrade-plan-runbook.md` §1.4 / §6.2-6.5 |
| 内核 | 数据双跑对账与可接受差异的定义 | 99.945%（5,170,688,484 / 5,173,508,562 行）差异逐行归因到去重语义；逐月无损校验门禁；对账方法本身要为安全性做工程设计（朴素 `COUNT(*)` 打挂全部 8 个 backend） | `adhoc_jobs/dynamic_resume_site/content/case_study_ch_to_doris.md`、`contexts/survey_sessions/ch_to_doris_migration_interview_arsenal_20260717.md` |
| 内核 | 双写并行 + 语义 diff 作为切换门禁 | 监控栈换引擎时双写并行两周、每条告警规则两侧同时评估并 diff 触发行为、修完分歧才切通知路由，旧栈全程 live 作为 fallback，切换零告警缺口 | `adhoc_jobs/dynamic_resume_site/content/projects/p_vm_platform.md` |
| 内核 | 切换的可观测性与回滚设计 | 两层验证（infra 健康 + 业务正确性）、post-verify 与落盘 baseline 做 diff、baseline 与外部监控交叉验证、三层回滚路径 + 触发条件事前写死 | `p_k8s_upgrade.md` |
| 内核 | 存算分离降低有状态切换难度的论证 | BE 无本地权威数据使节点替换安全（杀 spot 不需 `DECOMMISSION`）、扩容零数据搬迁（2→4 台移动零字节，tablet 归属 rebalance 成 131/128/128/125）、compaction 只处理单副本；同时能说清三条边界（状态被浓缩到 MetaService/FDB/S3 recycler、orphan lease、冷 cache 税） | `contexts/resume_highlights_doris_dcluster.md` §1、`adhoc_jobs/dynamic_resume_site/content/projects/p_elastic_compute.md` |
| 内核 | 复制追平能力是切换窗口的硬约束 | 跨集群 mirror 积压定位为容量而非故障（每分区吞吐是复制并行度硬天花板，3 分区不够，加机器无效）；扩分区标为不可逆操作需先评估 key 分布 | `adhoc_jobs/dynamic_resume_site/content/integration/oncall_track_record.md` 案例 4、`knowledge_raw/cases/case-kafka-mirrormaker-lag-tabapay-partition-bottleneck.md` |

**内核 6 条。**

### 中环（做过但浅或形态不同，被追问时的标准口径）

| 环 | 能力条目 | 一句话说明 | 标准口径 |
|---|---|---|---|
| 中环 | feature flag / kill switch | 有运维配置开关，没有产品级 flag 平台 | 「有三类：K8s 升级按 `cluster_type` 分类 + per-cluster feature flag 表达残余例外（如 drain timeout 300s→600s）；Doris fork 每个 feature 带 kill-switch 默认 parity-safe、约 21 个阈值全部可热调（`ADMIN SET FRONTEND CONFIG`）；弹性控制面两个 reconciler cron 默认关闭可灰度开。**这些是运维开关与 kill switch，不是按用户维度定向的 flag 平台**，我没做过 flag 债务治理与实验平台结合。」 |
| 中环 | Kafka MirrorMaker 跨集群复制运维 | 有拓扑事实、切换 runbook、告警判据、一次带时间戳的容量事故 | 「镜像 topic 改名为 `cluster_<src>.<topic>`、消费侧反序列化剥前缀、消费者同时订阅 local + mirror；**consumer group 与 offset 在两集群是完全独立的两份 state**，所以切换不需要搬 offset。⚠️ 我**没有**用 MM2 的 offset translation；要做「同一个 group 从 A 无缝续到 B」才需要它，那是我没做过的场景。告警判据是下降速率（`decline_ratio < 0.3` 且 `L_now > 500` 持续 20 分钟）不是绝对阈值。」 |
| 中环 | 影子读 / dark launch | 没有标准影子读机制，有同一论点的替代实践 | 「没做过影子读。做过的是在提交不可逆表布局之前挖 14 天生产 `system.query_log`（7,470 万条日志行）拿真实流量分布，结论把原设计推翻（超过 90% 是点查）。论点是同一个：**真实流量分布是设计输入，不是验证阶段的确认项。**」 |
| 中环 | 应用层双写与 CDC 迁移 | 做过监控数据的双写并行；CDC 只在 oncall 里排障过别人的链路 | 「双写我做过的形态是同一份 scrape 数据写两个后端加语义 diff 门禁（无分叉风险）。**没有在核心 OLTP 上做过应用层双写，也没用 CDC 做过迁移**。CDC 我踩过的是它的失效链：上游把表从 4 列改 2 列 → connector 缓存 schema 不匹配崩溃 → 重启触发全量 snapshot → snapshot 读类型事件未映射 `_sign` 列被下游 NOT NULL 拒绝，一条链跨三跳。」 |
| 中环 | 生产读写切换的执行 | CH→Doris 一手材料是 preprod 阶段 | 「迁移工程与对账验证是我做的、可复现；⚠️ 项目状态是 preprod，**最终生产读写切换的执行记录不在我的一手材料里**。问线上切换后的表现，我会说清这个边界。」 |

**中环 5 条。**

### 外环（纯知识，需要补课）

| 环 | 补课项 | 为什么在外环 | 补课要点 |
|---|---|---|---|
| 外环 | Service mesh 流量治理 | evidence 里零证据，没用过 | Istio/Linkerd 的 subset routing、traffic mirroring、retry/timeout/circuit-breaking policy、mTLS；重点是理解「mesh 把流量策略从基础设施层下移到 sidecar」这个转变解决了什么、代价是什么（延迟、运维复杂度、控制面自身成为 SPOF）。要能说清它和 LB / Ingress 层做流量治理在定位上的差异 |
| 外环 | Argo Rollouts / Flagger 等渐进交付工具 | 没上过；这是 Q4 的直接短板 | AnalysisTemplate 与 metric provider 的接法、自动 promote/abort 的判据设计、和 HPA/PDB 的交互、blue-green 与 canary 两种 strategy 的字段差异；重点是「把门禁写成声明式资源」这个模式 |
| 外环 | 数据库 online schema change 工具生态 | 只有引擎侧机制知识，没用过工具 | gh-ost（binlog 追平、无触发器）vs pt-online-schema-change（触发器）的机制差异与各自陷阱、原子 rename、pg_repack、Vitess 在线 DDL；重点是理解它们本质上都是 expand-contract 的自动化实现 |
| 外环 | CDC 双向同步与冲突解决 | 只排障过单向 CDC | 回环抑制（loop prevention，如 Debezium 的 origin 标记）、冲突解决策略（last-write-wins、版本向量、CRDT）、双向同步为什么在多数场景应该被避免；重点是要能论证「什么时候双向同步是错的答案」 |
| 外环 | 数据库级切换工具的语义 | 没用过 | Vitess 的 MoveTables + VDiff + SwitchTraffic（读写切换分离、VDiff 做行级对账）、AWS DMS 的 full load + CDC + data validation；重点是拿它们的抽象来校准我自己那套十二环节骨架，看有哪一环是我漏掉的 |
| 外环 | DNS / GSLB 层切换 | 没有一手配置经验，属于知识边界 | Route 53 health check + failover / weighted / latency routing 的语义、TTL 的现实约束（客户端库缓存、递归解析器不遵守小 TTL、连接池不会因记录变化而主动重连）、GSLB 与 Anycast 的取舍；重点是能论证「DNS 层故障切换的时间下限为什么是分钟级，以及生产系统为什么普遍把切换点放在 LB / 网关层」 |
| 外环 | Feature flag 平台 | 有运维开关，没有平台 | 按用户/租户分群定向、渐进 rollout 与实验平台的关系、flag 债务治理（flag 的生命周期管理）、flag 与配置管理的边界 |

**外环 7 条。**

---

## 本方向 2 个最强 headline

1. **「我做过一次 51.7 亿行、3,727 列超宽表的跨引擎迁移，交付的不是『搬完了』，而是 99.945% 的可解释对账率：剩下的 282 万行我能逐行归因到去重语义。可接受差异的定义是机制已知且已量化，不是比例足够小。」**
   往下钻的方向：怎么证明归因完整而不是找了个理由、合法差异清单为什么必须在对账之前声明、对账本身怎么不打挂生产（朴素 `COUNT(*)` 打挂全部 8 个 backend 那一课）。

2. **「50 集群 K8s 1.24→1.29 零事故零回滚，靠的是双集群流量前置转移：先把流量整体转到对侧、暂停跨集群 Kafka 复制、升级已经变 dark 的一侧、恢复复制并等 lag 降回阈值以下、验证后再切回。同一次变更里 control plane 原地升级、worker 不可变替换、集群之间 blue/green，三种策略并存，依据是每一层有没有本地权威状态。」**
   往下钻的方向：dark 集群不等于零风险（PDB 依然卡 drain、停复制期间反向 lag 上升是预期行为）、恢复复制为什么先启动接收流量那一侧、「零事故」怎么变成可验证的声明（版本 × 健康四象限 + baseline diff + 与外部监控交叉验证）。

---

## ⚠️ 待确认清单

1. **CH→Doris 的生产读写切换执行记录**：一手材料是 preprod（`ch_to_doris_migration_interview_arsenal_20260717.md` 附录 A）。生产切换后的线上表现没有 evidence。
2. **K8s 升级双集群切换的单次执行证据强度**：runbook 本身标注 `status: draft`，且没有带具体日期或事件编号的单次执行日志与复盘。可断言的是项目总结层面的结果（两套生产集群完成、零客户可感知停机、零回滚）。被问「讲一次最接近出事的时刻」时不能编，只能讲设计上被门禁挡住的场景。
3. **`p_k8s_upgrade.md` SOURCES 表的一处来源标注失真**：该表把「复制暂停/恢复/lag 回落」标为出自 `interview-1_reference Q5`，但原文实际只在 `runbook-k8s-upgrade-plan-runbook.md` §1.4 / §6.2-6.5；Q5 只讲了双集群流量前置转移与 PDB/HPA/readiness 三层保护。引用以 runbook 为准。
4. **fp skill 路径不在本 workspace**：任务给的 `rules/skills/fp/` 在 `context-infrastructure` 里不存在。MirrorMaker 拓扑事实的真实路径是 `work-harness/code_repos/infra/cre6630-infra/learn_fp/knowledge/topology/mirrormaker.md（跨仓库：work-harness/code_repos/infra/cre6630-infra/）`（另一个仓库）。切换 runbook 与告警判据在本 workspace 内可查（`knowledge_raw/runbooks/` 与 `contexts/presentations/dv_monitoring_oncall/`）。
5. **MirrorMaker 2 的 offset translation**：全库零证据，未使用过。中环口径已写明。
6. **consumer group 跨集群迁移的操作步骤**：只有「两侧 group/offset 各自独立」这一事实陈述，没有迁移过程记录。
7. **99.945% 差额的验证 SQL 未落盘**：`case_study_ch_to_doris.md` 写的是「attributed line-by-line to deduplication semantics」，但**具体的归因查询与其输出数字不在 evidence 里**。`story_bank.md` S02 的 L2 给的是可执行的证明路径（源侧按主键分组统计 `count(*) > 1` 的超出行数总和），标注为「可证明的路径」而非「已跑过的结果」。若能补上这个数字，S02 的 L2 会从「方法正确」升级为「结果可验」，建议实际去跑一次。
