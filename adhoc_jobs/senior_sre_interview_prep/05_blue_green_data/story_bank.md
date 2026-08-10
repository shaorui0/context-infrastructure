# Story Bank：切换类故事 × 方法论骨架

> 每个故事显式标注它落在 `methodology.md` 的哪几个环节（E01-E12），以及**哪些环节当时没做**。没做的部分必须自己先说，不能等面试官挖出来。
>
> 环节编号速查：E01 选型 / E02 green 构建 / E03 验证信号 / E04 数据同步 / E05 追平判定 / E06 对账 / E07 影子读 / E08 读切换 / E09 写切换 / E10 回滚点与窗口 / E11 baseline diff / E12 退役清理

---

## S01. 50 集群 K8s 1.24→1.29：集群级 blue/green 加跨集群 Kafka 复制的暂停与追平

**Headline（一句话）**：50 个自管理集群从 1.24 升到 1.29 零事故零回滚，支撑模式是双集群流量前置转移：先把流量整体转到对侧、暂停跨集群 Kafka 复制、升级已经变 dark 的一侧、恢复复制并等 lag 降回阈值以下、按 checklist 验证、再把流量切回 (src: `adhoc_jobs/dynamic_resume_site/content/projects/p_k8s_upgrade.md`)。

**适用题型**：blue/green 集群实践 / 大规模变更管理 / 有状态工作负载的升级 / 回滚设计 / 「零事故」怎么证明 / 跨集群数据一致性。

**在方法论里的位置**：
- **用了**：E01（集群级 blue/green + 集群内 worker 不可变 rolling，两种策略按「有无本地权威状态」分治）、E02（sibling 集群就是现成的 green，不需要临时开一套）、E03（check 阶段把健康基线显式化，且验证覆盖业务层正确性不止 infra）、E04（Kafka MirrorMaker 双向复制就是数据同步层）、E05（恢复复制后等 lag 降回阈值，这是标准的追平判定）、E08+E09（流量整体切走再切回，读写一起）、E10（三层回滚路径 + 触发条件事前声明）、E11（post-verify 重跑完整 check 与落盘 baseline 做 diff）
- **没做**：E06（跨集群没有做行级对账，追平判定停在 lag 阈值这一层）、E07（无影子读，因为切走的是全量流量）、E12（旧侧不退役，两个集群长期成对存在）
- **诚实边界**：**这不是「为升级临时构建一套 green 环境」**，而是「利用本来就成对存在的双集群互为对侧」。资源成本没有翻倍，因为它本来就是双份。被问「blue/green 的资源成本你怎么解决的」，正确答案是「我没有解决这个问题，我利用了一个已有的双活拓扑」，而不是把它包装成成本优化。

**情境**：1.24 即将脱离支持窗口，每落后一个 minor 版本 CVE 暴露面和合规风险都在累积。集群规模是 50 个 AWS 上的自管理集群，kubeadm control plane 加 ASG worker。存量升级方式单集群 18-21 小时纯手工且必须两人结对，因为真正的风险模型只存在于资深工程师脑子里；再乘上 kubeadm 一次只能升一个 minor 的约束（1.24 到 1.29 每个中间版本都要走一遍，每一跳覆盖 control plane、worker、addon 三层），手工执行在数学上就不成立 (src: `p_k8s_upgrade.md`)。

决定项目走向的一次重新定义：根本问题不是「手动还是自动」，而是**系统可解释性缺失**。任何一步都没人能回答「我凭什么确信现在可以进入下一步」(src: 同上)。

**动作**：
1. **Upgrade Safety System：`check → plan(dry-run) → apply + evidence` 三段流水线**，Python CLI 编排 Ansible、boto3、kubectl，所有 stdout/stderr 全量落 evidence 存储 (src: 同上)。
2. **check 把健康基线显式化**。etcd quorum 查三件事：member list（奇数个且全在线）、raft index lag（follower 落后 leader 超过 1000 直接 fail，因为 quorum 名义存在不代表复制健康）、leader 唯一性。node Ready 数、kube-system pod 状态、外部活跃告警同样走门禁，fail 条件全部写成规则。etcd snapshot 是任何变更前的强制动作 (src: 同上)。
3. **blast radius 在执行前用 quorum math 量化**。3 台 master 恰好容忍 1 台不可用，`serial: 1` 保证每次只动一台，最坏情况被限定在单节点 (src: 同上)。
4. **两种切换策略按有无本地权威状态分治**。control plane 原地升级（etcd 在本地，有状态），worker 不可变替换（新 AMI、更新 Launch Template、ASG Instance Refresh 按 20% batch 滚动、失败即暂停）(src: 同上)。
5. **双集群流量前置切换（本故事的 blue/green 核心）**。流量全部切到对侧集群 → 暂停跨集群复制（`kubectl scale deployment mirrormaker-a-to-b --replicas=0` 与 `mirrormaker-b-to-a --replicas=0`）→ 升级已变 dark 的一侧 → **恢复复制时先启动接收流量那一侧的 MirrorMaker** → 等 lag 降回阈值以下（切回流量的前置 checklist 里写的是 B→A lag < 1000）→ 按 checklist 验证 → 把流量切回 → 恢复双向复制 (src: `p_k8s_upgrade.md`；操作细节 src: `adhoc_jobs/dynamic_resume_site/knowledge_raw/runbooks/runbook-k8s-upgrade-plan-runbook.md` §1.4 / §6.2-6.5)。在这个模式下，worker 的 20% batch **不再是保护用户的机制而是节奏控制机制**：足够小，出现异常能快速暂停 (src: `p_k8s_upgrade.md`)。
6. **addon 按依赖顺序升级并各自设 gate**：先 AWS cloud-controller-manager（CCM 不健康会让新 worker 卡在 `uninitialized` taint 上），再 CNI（`maxUnavailable: 1`，用跨节点 pod 连通性验证），最后 Cluster Autoscaler（drain 一个节点观察 scale-out 成功即通过）(src: 同上)。
7. **回滚按层设计、触发条件事前写死**。control plane 回滚 = etcd snapshot 恢复加二进制降级（因为 snapshot 恢复的是数据不是二进制）；worker 回滚 = 停止 Instance Refresh 并回退 Launch Template；addon 回滚 = `kubectl rollout undo`。触发条件：master 升级失败、超过 50% pod 非 Running、关键服务不可达、告警洪水 (src: 同上)。
8. **fleet 推进顺序**：dev → preprod → prod 金丝雀 → 其余 prod → 管理集群最后（blast radius 最大）。任何一个集群失败，全局暂停，人工批准才继续 (src: 同上)。

**结果**：两套生产集群（master、control-plane 组件、worker 全覆盖）完成升级，**零客户可感知停机、零回滚**；单集群从 18-21 小时两人结对降到 6-8 小时单人加系统，自动化路线图目标 3-4 小时（预期降幅 60-80%）(src: `p_k8s_upgrade.md`、`work-contexts/career/profile/resume.tex:93`)。沉淀下来的不是工具：checklist 与 evidence 模式在项目结束后外溢为日常 infra health check (src: `p_k8s_upgrade.md`)。

### 5 层追问防线

**L1｜为什么这算 blue/green 而不是 rolling？**
两个层次同时存在，这个区分本身就是答案。**集群之间是 blue/green**：一整个集群的流量被整体切走，dark 集群升级期间不承载任何用户流量，回退路径是把流量切回对侧，秒级。**集群内部的 worker 是不可变 rolling**：ASG Instance Refresh 按 20% batch 换新 AMI 的节点。control plane 两者都不是，它是原地升级加 `serial: 1`，因为 etcd 的状态在本地，没有办法 blue/green 一个 quorum 成员。

一句话概括我的选型逻辑：**有本地权威状态的层只能原地升级并靠 quorum math 封顶 blast radius；无本地权威状态的层用不可变替换；整套环境有对侧可用时用 blue/green 把用户流量完全移出变更范围。** 三种策略在一次变更里并存，依据是每一层的状态性质。

**L2｜dark 集群意味着零风险吗？升级期间数据怎么办？**
不意味着。两个具体反例都是我踩过的。

第一，**PDB 在 dark 集群上依然诚实**：违规不会伤害用户（没有用户流量），但依然会卡住 drain。处理方式是等 PDB 满足或者显式调低 `minAvailable`，绝不强制驱逐 (src: `p_k8s_upgrade.md`)。这条经常被人当成「反正没流量，force 一下」，那是错的，因为 PDB 保护的还有数据副本的完整性。

第二，**数据不会因为集群 dark 就停止流动**。跨集群 Kafka 复制（MirrorMaker 双向）在流量转移后被显式停掉，因为 A 侧写入已被阻断、继续跑 B→A 复制没有意义且会持续积压。停复制期间 **B→A 方向的 lag 会持续上升，这是预期行为**（写入都进 B 了）(src: `runbook-k8s-upgrade-plan-runbook.md` §1.4）。所以升级窗口的长度实际上被「停复制期间积压多少、恢复后追平要多久」约束着，这是一个容量问题而不是时间问题。

第三，**恢复复制有顺序**：先启动**接收流量那一侧**的 MirrorMaker（即先 `mirrormaker-b-to-a`）(src: `runbook-k8s-upgrade-plan-runbook.md` §6.2)。理由是先把新数据往刚升级完的那侧灌，让它的数据新鲜度先追上来，然后才是反向。

**L3｜「等 lag 降回阈值」这个判定，凭什么说它够了？**
先给一手事实：切回流量的前置 checklist 里的条件是 **MirrorMaker B→A lag < 1000**，并配合 `kafka-consumer-groups.sh --describe --group <group>` 观察 offset 变化和 velocity 消费速率从 0 回升 (src: `runbook-k8s-upgrade-plan-runbook.md` §6.3 / §6.5)。

然后诚实说明这个判定的强度和它的位置。用 `methodology.md` §4.2 的四层收敛判定来对照：我做到了**第一层（lag 阈值 + 消费速率恢复的双信号）**，没做第二层（哨兵写入测端到端延迟）、没做第三层（跨集群行级对账）、没做第四层（业务语义比对）。

为什么在这个场景下第一层是够的，这才是关键论证：
1. 这不是一次「迁移」，两侧的 topic 与 consumer group 是**长期并存的稳态结构**，不存在「切完就把源侧扔掉」的不可逆点，所以对账的价值远低于迁移场景。
2. 消费侧的模型对短暂 lag 是容忍的（异步 velocity 计算路径），lag 表现为特征新鲜度下降而不是数据丢失。
3. 更重要的是，MirrorMaker 的告警判据本身不是绝对阈值而是**下降速率**：`decline_ratio < 0.3`（5 分钟内 lag 下降不到 30%）且 `L_now > 500` 持续 20 分钟才 fire。一次 burst 把 lag 推到 5 万都不告警，只要它在追；lag 卡在 800 一直不降就告警 (src: `contexts/presentations/dv_monitoring_oncall/monitoring_overview_20260521/parts/08_kafka_mirrorlag.md`)。这个判据设计说明这条链路的正确性判定标准是**「在收敛」而不是「已收敛到零」**，所以切回门禁用 lag < 1000 是和监控体系一致的口径。

如果面试官继续压「那你怎么知道没丢消息」，诚实答案是：**我依赖的是 Kafka 与 MirrorMaker 自身的投递语义，没有做独立的跨集群对账。** 要加强的话，正确做法是周期性对两侧同名 topic 做分区级 offset 高水位与消息数比对，这是我会补的一环。

**L4｜MirrorMaker 的 offset 在两侧是同一套吗？切换时 consumer 从哪继续消费？**
这题问得很准，答案里有一个必须讲清楚的机制。

镜像 topic 是**改名的**：MirrorMaker 把 A 的 `topic` 复制成 B 的 `cluster_a.topic`，前缀常量是 `cluster_`；消费侧在反序列化时剥掉前缀，所以 `cluster_a.foo` 和 `foo` 走同一段业务逻辑。消费者同时订阅 local 加 mirror 两套：A 上的 fp-async 主力吃 local，B 上的 fp-async 主力吃 mirror (src: `learn_fp/knowledge/topology/mirrormaker.md（跨仓库：work-harness/code_repos/infra/cre6630-infra/）`，位于 `work-harness/code_repos/infra/cre6630-infra/`，仓库外路径)。

关键事实：**consumer group 与 offset 在两个集群是完全独立的两份 state**，同名 group 在 A 和 B 各自维护自己的 offset (src: 同上)。也就是说切换不需要「把 offset 搬过去」，因为 B 侧的消费者一直在消费 `cluster_a.*` 这套镜像 topic 并维护自己的进度；流量转移只是改变了哪一侧是 local 写入方。

⚠️ **待确认 / 边界**：我**没有**使用 MirrorMaker 2 的 offset translation（checkpoint topic / `RemoteClusterUtils` 那套把源集群 offset 映射到目标集群的机制）。一手记录里完全没有这方面的操作痕迹。所以被问「你怎么做 offset translation」，正确答案是「我们的拓扑不需要它，因为两侧消费者各自独立消费各自视角的 topic 集合；如果要做的是「同一个 consumer group 从 A 无缝续到 B」，那才需要 offset translation，那是我没做过的场景」。这个区分不能含糊。

**L5｜零事故怎么证明？以及你算错过什么？**
「零事故」只有在**事前约定的标准**下才有意义，否则它只是「没人投诉」。我的做法是四件事：
1. 每道门禁归结为**版本 × 健康四象限**判定（目标版本且健康则继续；旧版本且健康则重跑；任何不健康则人工介入）
2. post-verify 对比的是**落盘的 baseline**，不是工程师的记忆
3. check 结果与**外部监控交叉验证**，专门防御「baseline 本身就是错的」这一失效模式
4. 验证范围覆盖**业务层正确性**，不止 infra 健康 (src: `p_k8s_upgrade.md`)

算错过 / 显式接受的代价：
- **drift 不追求消灭**。50 个集群必然漂移，处理方式是按 `cluster_type` 分类（workload / management / dev-staging），残余例外用 per-cluster feature flag 表达（例如已知驱逐慢的集群把 drain timeout 从 300 秒调到 600 秒）。drift 只是在每次升级前的 check baseline 里变得可见，而且**flag 数量增长本身被当作分类失准的信号** (src: 同上)。
- **PSA 迁移是独立工作线不是升级的一步**。1.25 移除 PodSecurityPolicy，而日志监控类 DaemonSet 合法地需要 privileged 权限，namespace 若被草率打上 `enforce: restricted` 会被直接拦截。解法是流程化：升级前完成存量扫描与迁移，PSA 先 warn/audit 观察，零违规才切 enforce，infra namespace 显式保持 privileged (src: 同上)。**「升级」和「升级带来的 API 不兼容」是两个项目**，混在一起做是我见过最常见的翻车原因。
- ⚠️ **证据强度边界**：升级方法论 runbook 本身标注为 draft 状态，且我手上**没有带具体日期或事件编号的单次执行日志/复盘文档**。可断言的是项目总结层面的结果（两套生产集群完成、零客户可感知停机、零回滚）。被问「给我讲一次最接近出事的时刻」时，我不能编，只能讲设计上被门禁挡住的场景（例如 raft lag 超 1000 时 check 直接 fail）。

**归属边界**：项目由我主导（reframing、系统设计、fleet 推进）。runbook 里的 MirrorMaker 操作与 dashboard 属团队共有运维资产。⚠️ 一处已知的来源标注失真：`p_k8s_upgrade.md` 的 SOURCES 表把「复制暂停/恢复/lag 回落」标为出自 `interview-1_reference Q5`，但该段原文实际只在 runbook §1.4 / §6.2-6.5，Q5 只讲了双集群流量前置转移和 PDB/HPA/readiness 三层保护。引用时以 runbook 为准。

**可复用到**：方向 04（IaC/CICD 的 evidence-driven 变更）、方向 02（baseline diff 与交叉验证的监控思维）、方向 07（AWS ASG/LT/Instance Refresh 的不可变基础设施实践）、方向 90（行为面：把隐式资深经验转成显式门禁是一个影响力故事）。

---

## S02. ClickHouse → Doris：51.7 亿行超宽表迁移与 99.945% 可解释对账

**Headline（一句话）**：51.7 亿行、3,727 列的超宽表跨引擎重建，我交付的不是「搬完了」，而是 99.945% 的**可解释**对账率：差的那 2,820,078 行被逐行归因到去重语义，而不是被当成误差糊过去 (src: `adhoc_jobs/dynamic_resume_site/content/case_study_ch_to_doris.md`)。

**适用题型**：零停机数据库迁移 / 怎么验证迁移后数据是对的 / 大规模数据工程 / 不可逆决策的风险控制 / 「你怎么定义完成」。

**在方法论里的位置**：
- **用了**：E01（选型：一次性批量迁移而非双写，理由是宽表双写成本远高于对账）、E02（backfill 按切片 + checkpoint）、E03（验证信号：逐月无损门禁）、E05（每月门禁即追平判定）、E06（对账，本故事核心）、E08（读切换：两表 A/B 决定不可逆的分布键后才提交布局）、E11（三个检查点重测延迟，15M → 107M → 286M 行）
- **没做**：E04（**没有做双写**，这是这个故事和标准数据迁移谱系最大的差异，必须主动说）、E07（没有影子读机制；用「挖 14 天生产 query_log」这个替代手段拿到了真实流量分布）、E09/E10（写切换与回滚窗口不适用，因为源侧 ClickHouse 在迁移期间继续服务，Doris 是新建的目标；⚠️ 一手材料是 preprod 阶段，最终生产读写切换的执行记录不在我手上的 evidence 里）
- **诚实边界**：⚠️ 项目状态是 preprod（src: `contexts/survey_sessions/ch_to_doris_migration_interview_arsenal_20260717.md` 附录 A），所以这是「迁移工程 + 对账验证」的故事，**不是「生产切换已完成」的故事**。被问「切过去之后线上表现如何」，我要说清这个边界。

**情境**：反欺诈分析的事件层同时服务两种日益冲突的负载：serving 路径上的毫秒级点查，以及越来越多由 AI agent 面向的产品功能（而非人类分析师）生成的不可预测 ad-hoc 分析。旧的 ClickHouse shared-nothing 层既无法隔离第二类负载也无法为它扩容：一条重查询就会饿死共享池，我们实测到一条 `SELECT * LIMIT 10` 在 60 毫秒 CPU 上等了 61 秒 wall-clock，排在一次 bulk insert 后面 (src: `case_study_ch_to_doris.md`)。

**动作**（只保留与切换/对账相关的部分，引擎细节归方向 01）：
1. **不做双写，做一次性批量迁移加逐月门禁**。源是 ClickHouse 超宽表、瓶颈在内存而非算力，所以走「CH 导出成分片 Parquet 对象 + Doris 侧按对象 load」，把 export 和 load 解耦、各自独立调内存和并发。这个选择的边界我要主动给：如果表不宽、行数不极端，直接 `INSERT INTO SELECT` 或 Stream Load 攒批更省事；正是 3,727 列把 footer 和 buffer 问题放大，才需要这套切片管线 (src: `ch_to_doris_migration_interview_arsenal_20260717.md`)。
2. **切片边界一遍扫出来，不用 OFFSET**。源表 `ORDER BY (user_id, ...)` 且 user_id 分布倾斜，所以不按值等分而按均匀行偏移切：一遍扫描每 `SLICE_ROWS` 行取一个 user_id 作边界，构造无缝、不相交、半开区间的完整覆盖。OFFSET 是 O(K²)，越到后面越慢。这个方法在 415M 行的月份上 11 秒扫出边界 (src: 同上)。
3. **逐月无损校验门禁**。每个月的迁移做门禁：各切片行数之和必须等于重新计算的当月 ClickHouse 总数，对不上就响亮告警且这个月不标记完成（实测 30M 行的月份切 5 片，差值为 0）。月份从 `system.parts` 的所有 active 分区发现，不会漏月 (src: 同上)。
4. **三层不丢不重保证**。行数层面是上面的门禁；原子性层面是被内存 watchdog 杀掉的 load 提交为空、不留半条数据；去重层面是目标表 Unique Key + Merge-on-Write，重复导入靠主键去重 (src: 同上)。
5. **对账方法本身要为安全性做工程设计**。一条朴素的 `COUNT(*)` 审计打挂了全部 8 个 backend (src: `case_study_ch_to_doris.md`)，根因是几十亿行的宽 MoW 表上 `COUNT(*)` 要合并 delete-bitmap。改成按月分区分别计数并调高 `query_timeout` (src: `ch_to_doris_migration_interview_arsenal_20260717.md`)。
6. **不可逆决策额外买保险**。分布键是唯一一个后续不能 ALTER 的决策，所以做了两表 A/B：同样的数据、镜像的键、四次测量，然后才提交。并在迁移过程中的三个检查点（15M → 107M → 286M 行）重测延迟，证明表增长 19 倍延迟仍然平坦 (src: `case_study_ch_to_doris.md`)。
7. **用真实流量分布而不是 benchmark 定设计**。原本的 serving 表方案建立在 50 条精选查询的 benchmark 上；在提交不可逆布局之前我挖了 14 天生产 `system.query_log`（7,470 万条日志行），结论直接反转：**超过 90% 的流量是点查**，键在一个高基数用户标识上，且大多是无法加时间过滤的「最新值」重建。第二张 serving 表从「也许要」变成「必须要」(src: 同上)。

**结果**：迁移完整性认证为 **99.945%，5,173,508,562 行中的 5,170,688,484 行**，差额逐行归因到去重语义；点查延迟从约 8 秒降到约 20 毫秒，并证明在 19 倍数据增长下保持平坦 (src: `case_study_ch_to_doris.md`)。锁定后的配置在单个 25.9 GiB part 上以约 90K 行/秒稳定导入、峰值内存约 18 GiB/BE、零崩溃 (src: `ch_to_doris_migration_interview_arsenal_20260717.md`)。

### 5 层追问防线

**L1｜0.055% 的差异到底是什么？**
先给绝对数不给百分比：差的是 **2,820,078 行**，源侧 5,173,508,562 行。我主动给出更难听的那个说法，因为「0.055%」听起来像误差、「282 万行」听起来像事故，而我需要先建立可信度再解释。

构成机制：目标表是 Unique Key 加 Merge-on-Write、按主键去重；源侧 ClickHouse 的 MergeTree 不做主键唯一约束，同一主键的多行可以共存。所以源侧同键的 N 行在目标侧收敛成 1 行。**这个差异是设计意图，不是数据丢失**：差额是「源侧存在的重复」，不是「目标侧缺失的信息」(src: `case_study_ch_to_doris.md` 记录为「attributed line-by-line to deduplication semantics」)。

**L2｜你怎么证明它是这个原因，而不是别的原因？**
光有解释不够，必须能证伪其他假设。可证明的路径是在源侧按主键分组统计 `count(*) > 1` 的超出行数总和，看它是否等于差额。差额能被这个数字完整解释掉，才叫「逐行归因」；解释不掉的余量必须单独调查。**「归因」和「找了个理由」的分界线就在这里。**

同时我要主动列出一张「合法差异清单」，这些是跨引擎迁移中会被误当成丢数据的东西，必须在对账**之前**声明、对账时逐项排除：
- 迁移窗口内源侧仍在写入（移动中的靶子），所以对账只对**已封闭的分区**（已完结月份）做，不对开放分区做
- 类型精度截断（浮点、decimal 标度、时间戳精度）
- `NULL` 与空字符串/零值在两个引擎里的默认行为差异
- 稀疏宽表里源侧不存在的列在目标侧被填了默认值

**先声明再对账，而不是对完账再找理由**，这两者在面试官眼里是完全不同的成熟度。

**L3｜对账口径怎么定？为什么不做 checksum、为什么不采样？**
分层来说，我实际做到的和我知道该做的要分开。

实际做到的是**行数口径的全量对账，按月分区拆开**。选它的理由有三个：能抓住「整片丢失」这个最主要的风险；差异定位一步到位（哪个月对不上就查那个月）；在几十亿行宽表上它是唯一跑得动的口径。

没做 checksum 的诚实理由：3,727 列的宽表上做行级 hash 或列级聚合校验，成本量级和重新迁一遍相当；而且做之前必须先对齐两个引擎的类型语义（浮点聚合顺序、NULL 语义、时区），否则产出的全是假差异。这是一个成本收益判断，不是没想到。**如果重来，我会在少数关键列上做 checksum 抽样**，覆盖「行数对但值错了」这一类风险。

没做采样的理由：这是一次性迁移的终态门禁，我要的是「没有一整片数据丢失」这个强保证，采样给不了。采样的位置是持续双写期间的常态巡检，不是迁移终验。

**L4｜对账本身怎么不打挂生产？发现差异后怎么定位？**
一条朴素的 `COUNT(*)` 打挂了全部 8 个 backend (src: `case_study_ch_to_doris.md`)，这是我这部分最好的一课：**对账是一次生产变更，要按生产变更来设计，不是「跑个 SQL 看看」。**

根因是几十亿行的宽 MoW 表上 `COUNT(*)` 要合并 delete-bitmap，内存与耗时都失控。修正后的方法是按月分区分别计数并调高 `query_timeout`，把一个大查询拆成一串有界查询 (src: `ch_to_doris_migration_interview_arsenal_20260717.md`)。

定位路径是分层收窄：月份门禁失败 → 该月内哪个切片的行数对不上（切片边界是已知的半开区间，所以能精确定位到 user_id 区间）→ 该切片的 export 日志与 load 日志 → 具体是导出少了还是导入少了。这条路径能走通的前提是**切片边界是无缝、不相交、完整覆盖的**，所以边界设计不只是性能考虑，也是可定位性的前提。

**L5｜为什么不做到 100%？你算错过什么？**
做到 100% 行数相等只有两条路，两条都更糟：
- 目标侧不去重：那就把源侧的数据质量问题一起搬过来，而且点查会返回多行，业务语义直接错了。
- 源侧先清洗去重再迁：那是一次独立的、有业务影响的数据治理项目，不该塞进迁移的关键路径。

所以正确的目标不是「行数相等」，而是「**差异可完整归因，且归因结果符合设计意图**」。我交付的是后者。反过来说，如果归因不完整、剩一个解释不掉的余量，那就必须停下来。**可接受差异的定义是「机制已知且已量化」，不是「比例足够小」。** 这句话是这个故事的方法论内核，也是我最想让面试官记住的一句。

算错过什么（这部分我主动给，因为它比结果更能说明我怎么工作）：
1. **「小切片等于小内存」这个直觉是错的**。内存等于 row-group 行数乘列数，不等于切片或对象大小。如果重来，我会更早做单切片端到端验证（export、检查 footer 可加载、load 不 OOM、对账，约 10 到 15 分钟），再信任全量，而不是先大规模跑再发现读侧 footer 的问题 (src: `ch_to_doris_migration_interview_arsenal_20260717.md`)。
2. **backfill 的资源占用随已迁入总量增长，不随批次大小**。约 1.7B 行时 MoW delete-bitmap 加宽表 compaction 让每个 load 在约 40 GiB baseline 上再加约 25 GiB，2 并发反复冲破 90 GiB 硬顶并在某个月份 livelock；钳到 1 并发解决，且吞吐本来就是 export-paced 的，没损失 (src: 同上、`case_study_ch_to_doris.md`)。通用教训：**backfill 的容量规划不能用前 10% 的实测外推。**
3. **一个我自己撤回过的数字**。早期 benchmark 显示 Doris 在聚合上比 ClickHouse 快 3-5 倍，我红队了自己的结果，发现混淆变量（一台有负载的 8 核生产节点对一台隔离的 14 核 benchmark 节点），撤回了这个倍数 (src: `case_study_ch_to_doris.md`)。这条我会主动讲，因为对账故事的可信度来自「我对自己的数字更苛刻」这个习惯，而不是来自 99.945% 这个数好看。

**归属边界**：infra 侧端到端 owner（引擎选型、迁移管线、查询路由含引擎级 Doris FE 工作、弹性、可观测性）(src: `case_study_ch_to_doris.md` 头部 Role 声明)。⚠️ 引擎级工作在 Apache Doris fork 上，`EXPLAIN ESTIMATE PLAN` 机制准备为 upstream PR，**PR merge 前不说 contributed to Apache Doris**，口径是「engine-level work on an Apache Doris fork, proposed as DSIP」(src: `adhoc_jobs/senior_sre_interview_prep/PLAN.md` §4.3)。

**可复用到**：方向 01（Doris/DB 运维主战场）、方向 02（对账与门禁的可观测性设计）、方向 06（存算分离的成本论证）、方向 90（「当一个数字每次重测都变得更不好看，通常说明你在逼近真相」这句可作为价值观陈述）。

---

## S03. Prometheus Federation → VictoriaMetrics：双写并行两周 + diff 门禁切换（加送，本方向最纯粹的数据层 blue/green）

**Headline（一句话）**：50 集群的监控栈换引擎，我用双写并行两周加逐规则 diff 作为切换门禁，切换全程没丢一条告警，旧栈一直保留为 fallback 直到门禁通过 (src: `adhoc_jobs/dynamic_resume_site/content/projects/p_vm_platform.md`)。

**适用题型**：零停机迁移一个有状态系统 / 怎么验证新系统语义等价 / 切换门禁怎么定 / 切换期间监控自身的盲区。

**在方法论里的位置**：这个故事**几乎跑满了整条骨架**，是本目录里方法论覆盖度最高的一个。
- **用了**：E01（双写并行 + 整体切通知路由）、E02（新栈全量建起来）、E03（验证信号 = 每条告警规则在两侧的触发行为 + dashboard 查询结果等价性）、E04（**dual-write 双写**）、E05（并行两周即追平与稳定观察期）、E06（**diff 即对账，口径是业务语义级：告警触发行为**）、E08+E09（切的是「通知路由」，这是读写切换在这个场景下的等价物）、E10（旧 federation 栈保留为 fallback，回滚 = 把通知路由切回）、E11（切换后持续三信号验证）、E12（旧栈下线）
- **没做**：E07（无影子读，但双写并行 + 两侧同时评估规则在效果上覆盖了影子验证的目的）

**情境**：federation 拓扑顶端的 global Prometheus 每周 OOM 两三次，head block 承载 1.2M series、维护成本 5-10 GB 内存，每次崩溃重启都在数据里留缺口，而这些缺口会为不存在的故障呼叫值班。延迟侧是结构性问题：federation 叠加两层 scrape 间隔（集群级 15 秒加全局层 30 秒），全局视图最多落后现实 45 秒，P0 期间被叫起来的人看的是过去。50 集群规模下 `/federate` 端点在抓取压力下超时，Grafana 出现缺口 (src: `p_vm_platform.md`)。

**动作**：
1. 引擎选型跑了 VictoriaMetrics vs Thanos 的 POC（写吞吐、压缩、运维复杂度），团队认可结果后落地 (src: 同上)。
2. **切换门禁 = 双写并行两周 + 逐规则 diff**。VictoriaMetrics 用 MetricsQL，与 PromQL 有边界差异，所以「规则照常触发」不能靠假设。两套栈以双写配置并行运行两周，**每条告警规则在两侧同时评估、diff 触发行为，修完所有分歧才切换通知路由**；dashboard 查询也必须在 MetricsQL 下返回等价结果 (src: 同上)。
3. **旧栈保留为 fallback 直到门禁通过**（src: 同上）。这就是回滚点：门禁没过就不动通知路由，回滚代价为零。
4. **push 模型的丢数据风险单独工程化**。remote_write 意味着网络抖动可能丢数据，所以每个 vmagent 在本地磁盘跑 persistent queue，remote 断连期间缓冲、恢复后回放 (src: 同上)。
5. **切换期间监控自身的盲区靠 out-of-band 兜底**。vmalert 持续输出心跳，deadman's switch 加 out-of-band 探针把「监控失联」在分钟级转化为一条明确的 page，而不是一个安静的盲区 (src: 同上)。
6. **inhibition 规则在 staging 用人工触发上游故障验证**，检查哪些下游告警被正确抑制，触发历史留存供复盘 (src: 同上)。

**结果**：1.2M active series，数据延迟 45 秒降到 5 秒以内，消除每周 OOM，**切换全程零告警缺口**；新集群接入从「写 federation 规则、改全局 scrape config」变成「部署 vmagent、指向 remote_write 地址」；上线后靠三个信号持续验证（deadman 心跳、PAGER action rate、漏报事故追踪）(src: `p_vm_platform.md`、`work-contexts/career/profile/resume.tex:78`)。

### 5 层追问防线

**L1｜为什么门禁是「两周」和「逐规则 diff」，而不是跑通就切？**
因为要验的不是「新栈能查」，是「**语义等价**」。MetricsQL 与 PromQL 在边界情况上有差异（区间选择、缺失值处理、聚合语义），这类差异只在特定数据形状下暴露，不是跑几条查询能覆盖的。所以验证对象必须是**全量告警规则的实际触发行为**，而不是抽样查询。两周是为了让规则覆盖到低频路径（周末、月末、周期性作业窗口）至少一次。

用方法论的语言说：**这里的对账口径不是行数也不是 checksum，是业务语义级对账**。对一个监控平台，「数据正确」的业务定义就是「该响的告警响、不该响的不响」，所以我直接对齐最终语义，跳过中间口径。

**L2｜双写期间的一致性风险在哪？**
双写在这里是「同一份 scrape 数据写两个后端」，不是「两个数据库互相同步」，所以没有分叉风险，但有三个真实风险：
1. **两侧数据不完全相同也可能是正常的**。采集时间戳、抖动、乱序容忍度不同，所以 diff 的判据不能是「数值逐点相等」，只能是「规则触发行为一致」。这也是我把口径定在语义层而不是数据层的原因。
2. **push 模型可能丢数据**（federation 是 pull，缺口是可见的；remote_write 断连是静默的），所以每个 vmagent 必须有本地 persistent queue 缓冲加回放。
3. **成本翻倍期**。两周内两套栈都在跑，存储和计算是双份。这是 blue/green 的标准代价，两周是一个显式的时长预算。

**L3｜切换的原子性在哪？回滚点是什么？**
切换的原子动作是**移动通知路由**，不是移动数据、也不是移动查询。这是这个故事最值得讲的设计选择：数据双写、规则双评估都可以长期共存，唯一必须二选一的是「谁的告警发到 PagerDuty/Alertmanager 下游」。把不可逆点压缩到一个配置项上，回滚就是把这个配置项改回去。

回滚点是 **federation 栈保持 live**（不是保留快照、不是保留配置，是整套还在跑）。回滚窗口在旧栈真正下线时才关闭。

**L4｜切换期间监控自己坏了怎么办？**
这是切换监控系统特有的问题：「没有告警」既可能是一切正常，也可能是全都坏了，指标层面无法区分这两者。所以必须有 out-of-band 的判定手段。我的做法是 vmalert 持续输出心跳 + deadman's switch + out-of-band 探针，把「监控失联」在分钟级转化为一条明确的 page (src: `p_vm_platform.md`)。

推广成通用原则：**任何切换都要问一句「验证这次切换的那个系统，本身在切换范围内吗」。** 如果在，就需要一条独立于被切换系统的验证通路。

**L5｜你算错过什么？**
一手材料里我自己写下的复盘：**cardinality budget 应该从第一天就存在，而不是等增长曲线逼出来才补。** 加租户维度会成倍放大 series 数，label rollout 之后 series 增长很快；补上的控制是租户级 recording rule 只覆盖核心 SLI、基础设施指标完全不带租户 label、分层保留（租户 SLA series 90 天 / 排障 series 30 天 / 基础设施 15 天）、周期性 cardinality review (src: `p_vm_platform.md`)。

放到切换方法论里看，这是一个 **E01 阶段的遗漏**：新架构引入了一个旧架构没有的维度（多租户），而这个维度的容量成本在选型时没有被量化。**切换到一个能力更强的系统时，新增能力的容量成本必须在切换前就定预算**，否则它会以「切换很成功但一个月后开始告警」的形式回来找你。

**归属边界**：我在一个 3-4 人 SRE 团队内端到端 owner 可观测性域（设计、评估、rollout）；引擎选型我跑了 VictoriaMetrics vs Thanos 的 POC，团队认可结果 (src: `p_vm_platform.md`)。措辞上「I owned the observability domain end-to-end」是原文口径，可以直接用。

**可复用到**：方向 02（监控体系，这是该方向的主线故事）、方向 05（本方向数据层切换的骨架示范）、方向 04（变更门禁设计）。

---

## S04. 跨集群 mirror 复制积压：追平能力是切换窗口的硬约束（加送，短故事）

**Headline（一句话）**：一次跨集群 Kafka 复制积压里，复制服务本身完全健康，重启不解决任何问题，真正的约束是「每分区吞吐是复制并行度的硬天花板」，而修复动作（扩分区）本身是不可逆操作 (src: `adhoc_jobs/dynamic_resume_site/content/integration/oncall_track_record.md` 案例 4)。

**适用题型**：为什么重启不管用 / 容量约束与故障的区分 / 不可逆操作的处理 / 「切换依赖复制追平时怎么保证窗口够」。

**在方法论里的位置**：E05（追平判定）与 F10（失败模式：复制追不上导致切换窗口超时）的直接实例。它是 S01 的容量前提：**如果切换依赖复制追平，那么复制的并行度上限就是切换窗口的硬约束。**

**情境 / 动作 / 结果**：
跨集群 mirror 复制积压持续高位，而复制服务本身健康：无报错、无重启、资源正常，所以重启不解决任何问题。真正的约束是容量：某大租户 QPS 增长超过了 topic 仅有 3 个分区所能承载的复制吞吐，**每分区吞吐是 mirror 并行度的硬天花板**。峰值过后 lag 自然收敛；长期修复是分区扩容评审，并**标注为不可逆操作，需先评估 key 分布** (src: `oncall_track_record.md` 案例 4)。带时间戳的一手记录：2026-04-30 13:43 JST，consumer group `cg_velocity_detail_tabapay`，事发时 topic partition 数 3，方向 `aws-useast1-prod-b → aws-uswest2-prod`，follow-up 是扩 partition 并标记 `#MANUAL`（不可逆，需评估 key 分布与 consumer rebalance 影响）(src: `adhoc_jobs/dynamic_resume_site/knowledge_raw/cases/case-kafka-mirrormaker-lag-tabapay-partition-bottleneck.md`)。

### 5 层追问防线（压缩版）

**L1｜怎么判断这不是复制服务的故障？** 三个信号同时为负：无报错、无重启、资源正常。这三条同时成立时「重启」这个动作的期望收益为零，而副作用为正（MirrorMaker 重启会导致 lag 短暂上升，看到上升就再重启是一个已知的错误循环）。

**L2｜怎么定位到分区数？** lag 的形状。如果是消费能力不足，加副本/加线程会有效；如果是分区吞吐触顶，扩副本无效，因为**一个分区只能被一个 consumer 实例消费**，分区数就是并行度上限。判定方法是看单分区的复制速率是否已经贴住上限而分区数又很少。

**L3｜为什么扩分区是不可逆的？** Kafka 分区数只能增不能减，且扩分区会改变 key 到分区的映射，历史数据的分区归属不变但新数据会走新映射，因此**同一个 key 的消息顺序在扩容点前后可能不再保序**。所以要先评估 key 分布与依赖顺序的下游逻辑，这就是「标注为不可逆、需先评估」的实际含义。

**L4｜这对切换设计意味着什么？** 切换前必须做一次算术：待追平数据量 ÷（每分区吞吐 × 分区数）是否落在切换窗口内。加机器不解决分区数不够。这条直接约束 S01 里「停复制多久是安全的」这个决策。

**L5｜告警应该怎么定，才能既抓住这个又不吵？** 一手做法是判据用**下降速率**而不是绝对阈值：`decline_ratio < 0.3`（5 分钟内 lag 下降不到 30%）且 `L_now > 500`，持续 20 分钟才 fire。一次 burst 把 lag 推到 5 万都不告警，只要它在追；lag 卡在 800 一直不降就告警 (src: `contexts/presentations/dv_monitoring_oncall/monitoring_overview_20260521/parts/08_kafka_mirrorlag.md`)。这个设计的洞见是：**对追赶型系统，正确的健康定义是「在收敛」而不是「已收敛」。**

**归属边界**：oncall 处理的一手事故；follow-up 的分区扩容 owner 是 Zhenglan Hou 与 Caiwei Li，不是我 (src: `case-kafka-mirrormaker-lag-tabapay-partition-bottleneck.md`)。讲这个故事时说「我定位并给出修复方案，执行由 topic owner 团队做」。

**可复用到**：方向 01（Kafka 运维）、方向 02（告警判据设计：速率型而非阈值型）、方向 05（追平判定与不可逆操作）。

---

## 故事到方法论环节的覆盖矩阵

| 环节 | S01 K8s | S02 CH→Doris | S03 VM | S04 MirrorLag |
|---|:---:|:---:|:---:|:---:|
| E01 选型 | 是 | 是 | 是 | 间接 |
| E02 green 构建 | 是（sibling 现成） | 是 | 是 | 无 |
| E03 验证信号 | **强** | 是 | **强** | 是 |
| E04 数据同步 | 是（MirrorMaker） | **无（不双写）** | **是（dual-write）** | 是 |
| E05 追平判定 | 是（lag<1000） | 是（逐月门禁） | 是（两周） | **强** |
| E06 对账 | **无** | **强（99.945%）** | **强（语义 diff）** | 无 |
| E07 影子读 | 无 | 无（用日志挖掘替代） | 无（双评估覆盖） | 无 |
| E08 读切换 | 是 | 是（A/B 定布局） | 是 | 无 |
| E09 写切换 | 是 | ⚠️ preprod | 是（通知路由） | 无 |
| E10 回滚点/窗口 | **强（三层回滚）** | 部分 | **强（旧栈 live）** | 无 |
| E11 baseline diff | **强** | 是（三检查点） | 是（三信号） | 无 |
| E12 退役清理 | 不退役 | ⚠️ 未覆盖 | 是 | 无 |

**这张矩阵的用法**：面试官问到某个环节，直接查列找最强的那个故事。E04/E06 问数据双写与对账 → S03 加 S02；E10 问回滚 → S01 加 S03；E03 问验证信号 → S01 加 S03。空白格是我的真实 gap，被问到就承认并给出「如果重来我会怎么补」。
