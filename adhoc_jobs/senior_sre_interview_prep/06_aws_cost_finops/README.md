# 06 AWS 成本 / FinOps

**目录四件套**：本文（核心圈三环 + 定位）· `finops_fundamentals.md`（体系补课，本目录最大交付物）· `story_bank.md`（8 个成本故事 + 5 层追问防线）· `questions.md`（24 题 + 答题骨架）

---

## 这个方向我的一句话定位

我做的是**架构级降本**：改变系统的结构，让成本随负载归零，而不是在既有结构上找更便宜的价格。这两件事的差别不是程度差别，是层级差别。运营级降本（买 RI、rightsizing、清僵尸资源、换存储类）动的是账单公式里的「单价」那一项，天花板被折扣率封住；架构级降本动的是「用量」和「时长」，天花板是数量级。我的三个主力案例都在后者：把重查询算力池从静态 2 节点常驻改成 floor-0 弹性池，同一 burst 形状下 on-demand 约 $63/月对静态池约 $772/月；把 Iceberg 那条链上「S3 按请求次数计费」这个模型算清楚之后，动作是把文件数从 619 压到 49 而不是去加带宽；把算力按业务语义切成三个 warehouse，用户面钉在 on-demand、夜间 MV 刷新和 ad-hoc 跑 spot。这几件事的共同点是**起点都是一笔算术，不是一个直觉**：单查询成本比 1,240 倍这个数字先出来，分池和弹性才被推导出来。

我不打算把这个定位讲成「我比做 FinOps 的人更高级」。真实情况是：架构级降本更难被质疑，因为它有明确的因果链和物理依据（存算分离让 BE 无本地数据，所以杀 spot 节点安全，所以 spot 是合法选项）；但它的覆盖面窄，只作用在我亲手设计的系统上。**FinOps 的制度化运营我是明确的补课项**，而且缺的不是知识而是一手落地：成本分配标签的治理与覆盖率、CUR 到 Athena 的归因分析流程、承诺折扣的组合决策（coverage 与 utilization 的持续管理）、预算与异常检测的机制建设、showback 与 chargeback 的组织落地，这几件我能讲清机制和决策框架，但没有管过一个真实的成本实践。

有一个自我批评我打算主动讲，因为它比任何包装都有力：Inform → Optimize → Operate 这三个阶段，我是**从 Optimize 开始做的，跳过了 Inform**。代价有一次很具体地打在脸上：ClickHouse 上 TB 级的无主僵尸表在多个集群持续增长、访问量是零，这本来是最干净的成本异常信号，但我们是被一次亚秒级 OOM 发现它的，不是被账单发现的。这件事之后我对成本可见性的看法变了：成本异常检测不只是省钱工具，它是一类独立于业务指标的浪费探测器。

---

## 三环

### 内核（一手 evidence，能扛住 5 层追问）

| 环 | 能力条目 | 一句话说明 | evidence |
|---|---|---|---|
| 内核 | **scale-to-zero 弹性算力池的完整设计** | heavy 池平时 0 副本、路由判定 heavy 才弹起、空闲 reaper 30 分钟回收到 0；静态 2 节点池 ~$772/月 vs 实测 burst ~$63/月（OD）/ ~$24/月（spot） | `p_elastic_compute.md:17,23,25,73`；`resume_highlights_doris_dcluster.md` §2.2；故事 S01 |
| 内核 | **存算分离下 spot 安全性的完整论证** | BE 无本地数据 → 杀节点不搬数据、不需要 DECOMMISSION；FE 心跳 2s 检测失联 + 锁 7s 释放 + 重试一次，全落在 spot 2 分钟回收窗口内；serving 池永远不上 spot | `case_study_ch_to_doris.md:26`；`p_elastic_compute.md:51`；`resume_highlights_doris_dcluster.md` §1；故事 S01 L3 |
| 内核 | **unit economics 思维（cost per query）** | 生产 query log 挖掘出单查询成本比约 1,240×（196,354ms vs 158ms），18 次窗口查询 ≈ 21,755 条点查总算力；用这个分布推导分池、floor-0、recall-first 风险姿态 | `p_elastic_compute.md:15,67`；故事 S02 |
| 内核 | **从计费模型反推优化动作（S3 请求费）** | profile 出 99% 时间在 OpenFile → 建「S3 按请求次数计费」模型 → 动作是减文件数不是加带宽；619 → 49 files，FSIOTime 7.9s → 63ms（125×） | `interview-6-starrocks-lakehouse.md:53,70`；故事 S04 |
| 内核 | **按业务语义匹配定价模型** | 三 warehouse：`query_wh`（OD always-on 保 50ms SLA）/ `refresh_wh`（spot，01:50 UTC 刷完销毁）/ `adhoc_wh`（spot 按需）；硬约束「OD 与 spot 不可混」；spot CN 省 ~70% | `interview-6-starrocks-lakehouse.md:157,161`；故事 S05 |
| 内核 | **存算分离对存储成本结构的改变与新成本科目** | 4TB 迁移零额外 BE 盘、扩容 2→4 台零数据搬迁；但 EBS 容量费换成了 S3 容量费 + 请求费；冷读瓶颈是 GET 延迟 × GET 数量（吞吐仅 ~1MB/s，NIC 用不到 1%）；暖查询仍 1.12s 证明扇出是地板 | `interview_story.md:41`；`p_elastic_compute.md:23`；`doris_wide_table_point_query_optimization_survey_20260724.md:12,63,74`；故事 S03 |
| 内核 | **可观测性自身的成本治理** | 同窗口热存储 930GB → 250GB（4× 压缩）+ 冷数据 5min 降采样 S3 180 天 ~25GB；cardinality 治理四条 + retention 分层 90/30/15 天 | `p_vm_platform.md:25,62,147`；故事 S08 |
| 内核 | **「在增长但没有访问者」的浪费判据（数据层）** | ClickHouse 升级残留僵尸表：1.21 TiB + 308 GiB，跨集群审计另查出最严重集群 1.65 TiB、另一 region 250 GiB；三层预防（TTL / 升级 runbook 审计步骤 / 舰队级审计） | `w_zombie_oom.md:20,24,26`；故事 S06 |
| 内核 | **弹性与成本的权衡实验与边界判断** | 冷启动 66s + 2min 注册的代价只摊给延迟容忍负载；离散伸缩而非 per-query 精确（扩容分钟级，很多查询在 BE 就绪前已跑完）；去抖 + cooldown 匹配 3-4min 执行延迟；idle 不等于免费（缩到 0 留 orphan lease 阻塞别人 compaction） | `p_elastic_compute.md:17,25,49`；`resume_highlights_doris_dcluster.md` §2.2；故事 S01 L2/L5 |

### 中环（做过但浅，只讲标准口径，不深挖）

| 环 | 能力条目 | 被追问时的标准口径 |
|---|---|---|
| 中环 | **公司级降本（FY2026 自评达成项）** | ⚠️ **具体动作缺失，未补完前不主动提。** 临时口径：「我做的成本工作主要是架构级的，有三个能讲透的案例；FinOps 的制度化运营那一侧我是有知识但缺一手落地经验的。」补完需要瑞哥回答 S07 的 22 条提问清单 |
| 中环 | **ASG / Launch Template 深度** | 我的深度是**消费修补**，不是设计者：改 request 从 cpu=8 到 7、补 node-template label/taint tag 让 CA 能从 0 扩。被问混合实例策略、capacity-rebalance 配置细节 → 答机制 + 承认没做过配置层的深度设计（src: `p_elastic_compute.md:45`） |
| 中环 | **spot 中断处理的实现** | 「spot 中断回退、容量准入、多集群锁的实现是团队另一位同事做的（git 作者 junhan.ouyang / Runzi Yang）。我负责的是控制面幂等扩缩语义、queue/idle 驱动的伸缩闭环、以及 spot 在存算分离下为什么安全这个论证和按池分治的决策。」说到这里就停（src: `resume_highlights_doris_dcluster.md` §0） |
| 中环 | **spot 的 97% 省幅** | 那是**投影不是已实现**：当时的决策是「装好 node-termination handler 之前用 on-demand，之后再切 spot 优先混合 ASG」。StarRocks 那边的 spot 是真的在跑，两个场景要分清（src: `p_elastic_compute.md:51`） |
| 中环 | **92% / 97% 的数据性质** | 是按实测 node-hours + list price 建的**成本模型**，不是账单 A/B。repo 里没有池利用率 / 重试率 / 账单 A/B（src: `resume_highlights_doris_dcluster.md:138`） |
| 中环 | **重查询占比** | 「<1% 是设计假设不是实测；query log 挖掘给出的是重查询类占执行数 3% 以下、点查约 97%。」两个口径不混（src: `resume_highlights_doris_dcluster.md` §1 vs `p_elastic_compute.md:15`） |
| 中环 | **存储成本降 90%** | **Doris 官方口径不是自测。** 官方另一口径是 100TB 在线数据从三副本约 $37K/月降到单副本约 $22K（约 40%），冷数据可降 90%+（src: `clickhouse_vs_doris_..._20260716.md:84-86`；`ch_to_doris_..._20260717.md:211`）。与 `01_doris_db_operations/README.md:103` 同纪律 |
| 中环 | **EBS 卷类型（gp2/gp3）** | 机制答透（IOPS/吞吐解耦、gp2 是 3 IOPS/GB 所以「为 IOPS 买容量」的浪费可回收），但**卷类型迁移生产上没做过**。一手的是 PVC 在线扩容与 volumeClaimTemplates 不可变这类坑 |
| 中环 | **跨架构（arm64）构建** | Doris FE 从 QEMU 模拟 amd64 换原生 arm64：build 43:55 → ~3min，镜像 747MB → 43MB。**这是开发效率不是云成本**，不要说成做过 Graviton 成本迁移（src: `p_engine_routing.md:42`） |
| 中环 | **日志成本治理** | 有零散动作没有体系：给 ClickHouse 默认无 TTL 的内部日志表加 TTL、把数据量最大的日志直接关闭（驱动是 OOM 不是账单）。Loki 侧的采样与分级保留没落地过（src: `w_zombie_oom.md:26`） |
| 中环 | **K8s 成本工具** | 公司环境里部署了 Kubecost（有 `kubecost-*.dv-api.com` 痕迹，同记录列了 29 个集群），但**我没深入用过它做决策**。⚠️ 待瑞哥确认实际使用情况 |
| 中环 | **VM 内存 rightsizing** | 120Gi → 40-60Gi 是一条 **P3 建议，没有证据说执行了**，不要当 rightsizing 实绩（src: `contexts/thought_review/victoriametrics_ops_review_20260402.md:167`） |
| 中环 | **自管 K8s 省 EKS control plane 费** | $0.10/cluster/hr × 50 ≈ $3,600/月，但这是**继承的历史决策不是我的动作**，而且我的结论是这笔省钱不划算（50 集群控制面全自运维，工程师时间比这笔钱贵）。这条的正确用法是答「成本优化的边界在哪」，展示懂 TCO 不只看账单（src: `interview-1-k8s_upgrade_reference.md:161`） |

### 外环（明确补课，答机制为止，不装经历）

| 环 | 能力条目 | 补课内容位置 |
|---|---|---|
| 外环 | **CUR / Cost Explorer 的分析流程** | `finops_fundamentals.md` §1：五个工具各管一段、Cost Explorer 到 CUR 的那道坎、CUR 2.0 vs legacy、FOCUS 1.x、Athena 建表路径 |
| 外环 | **成本分配标签的策略与治理** | §1.3：回溯窗口 12 个月的机制与限制、500 个 tag key 上限、AWS-generated vs user-defined、覆盖率四步治理法（含 LT TagSpecifications 这个正确注入点） |
| 外环 | **RI vs Savings Plans 的组合决策** | §2：四种 SP（含 2025-12 新增的 Database SP）、AWS 官方 SP 优先立场、RI 剩下的两个价值（Marketplace / zonal 容量预留）、Standard vs Convertible 的 exchange 规则、coverage 与 utilization 的反向拉扯、期限与业务确定性匹配 |
| 外环 | **弹性架构如何改变承诺策略** | §2.4：这是外环知识与内核经历的接缝，也是最能拉分的一段。「先架构后承诺」的顺序问题 + spot 化会吃掉 SP 可覆盖基数的组织冲突 |
| 外环 | **预算、异常检测与成本护栏** | §1.1 + `questions.md` Q5：Budgets 抓绝对值越线 vs Anomaly Detection 抓形状变化，为什么增长期只有前者会误报 |
| 外环 | **showback / chargeback 的组织落地** | §7.2：共享成本怎么分、idle 归谁、归因精度必须匹配后果严重性（不要为了「更严格」过早上 chargeback） |
| 外环 | **FinOps Framework 与成熟度模型** | §0 + §7.1：4 个 Domain、Inform/Optimize/Operate 三阶段（仍是官方说法）、2025-03 加入的 Scopes、2026-03 的 Technology Category（含 AI）与 Executive Strategy Alignment、FOCUS 1.4 |
| 外环 | **网络成本的隐形陷阱** | §5：NAT 双重收费、跨 AZ 仍是 $0.01/GB 单向（没免费）、egress 100GB/月免费额度（2021-12 起）、S3 Gateway Endpoint 免费所以「省 NAT」不需要算盈亏平衡点、多 AZ 高可用与跨 AZ 成本的四步权衡框架 |
| 外环 | **rightsizing 方法论** | §3.1：为什么只看 CPU 会犯错（五条判据）、Compute Optimizer 14 天回看窗口的盲区、有硬约束的负载不能按利用率降配 |
| 外环 | **实例族现代化与 Graviton** | §3.2：Graviton5（约 2026-06 GA）的收益口径、四个迁移摩擦点（含「一个 x86-only DaemonSet 能阻止整个集群」这条 50 集群下的真实阻塞点） |
| 外环 | **容器成本分摊与 bin-packing** | §3.4：`节点成本 ≥ Σrequests ≥ Σusage` 的两个 gap、requests/limits 的成本语义与 QoS 权衡、OpenCost（CNCF Incubating）/ Kubecost（2024-09 被 IBM 收购）、EKS split cost allocation data（⚠️ 我们是 kubeadm 自建不是 EKS，用不了）、`max(request, usage)` 分摊语义、idle cost 是核心指标 |
| 外环 | **S3 存储类与生命周期** | §4.2：完整存储类列表与最短存储时长、取回费反超的判据、Intelligent-Tiering 的 128KB 门槛（小文件场景无效） |
| 外环 | **EBS 存储成本细节** | §4.1：gp3 超额计费、io2 Block Express 定位、快照严格增量但「删快照未必降本」、Snapshot Archive tier 的 90 天最短期 |
| 外环 | **FinOps for AI** | §7.3：cost-per-token / cost-per-inference / GPU 利用率 / commitment coverage。对他有战略价值，因为 Doris 项目本来就是为 AI agent 负载做的 |
| 外环 | **Karpenter** | §3.5：比 CA 在碎片治理上结构性更强（按 pod 形状选实例 + consolidation），但他们的 Packer + Ansible + kubeadm AMI 流水线上它需要不小的改造。答理论 + 说清为什么没上 |

---

## 本方向 3 个最强 headline

**1. 「我做的降本是架构级的：把成本结构从固定容量改成按需容量。」**
> 重查询负载只占执行数的个位数百分比却承载不成比例的算力，所以我把这层的成本 baseline 归了零：heavy 池平时 0 副本，路由判定 heavy 才在几分钟内弹起，用完自动回收。静态 2 节点池约 $772/月，实测 burst 形状 on-demand 约 $63/月、spot 约 $24/月。而这个模式能成立的前提不是 autoscaling，是存算分离：BE 不持有本地数据，所以杀节点是安全的。
（口径纪律：这是成本建模不是账单 A/B；spot 那档当时是投影。）

**2. 「优化的起点是一笔算术，不是一个直觉：我先算出单查询成本比是 1,240 倍。」**
> 挖生产 query log 之后发现最贵的那条月度窗口查询平均 196,354 ms，频率最高的点查平均 158 ms；那条窗口查询跑 18 次约等于 21,755 条点查的总算力。频率和成本指向完全相反的方向。这个分布直接否掉了「一个池子服务所有查询」，也直接推导出了「重查询池必须是弹性的」，甚至定了路由分类器的风险姿态（误判 heavy 只浪费，误判 light 会被内存硬限杀掉重试，代价不对称，所以宁可多判 heavy）。

**3. 「我不从参数入手，我从计费模型入手。」**
> Iceberg on S3 那条链上我 profile 出 99% 的时间花在 OpenFile 上，于是建的第一个模型是「S3 按请求次数计费，不是按带宽计费」，所有动作从这个模型推导，文件数 619 降到 49，FSIOTime 7.9s 降到 63ms。同一套方法用在 Doris 点查上结论完全不同：那边我实测出暖查询全命中缓存仍然 1.12s，证明扇出是成本地板、S3 只是冷路径上的乘数，所以最大杠杆是分区剪枝而不是文件合并。方法一样，结论不同，这才是方法有效的证据。

---

## 搜索记录：公司级降本动作的挖掘结果

**结论：FY2026 self-assessment 里那句降本没有任何配套细节，全 workspace 确认找不到。**

**搜索范围**：`contexts/`（含 survey_sessions、thought_review、memory）、`adhoc_jobs/dynamic_resume_site/`（content、research、knowledge_raw）、`work-contexts/`（career/profile 的四份 resume tex、career/interview 的 8 组面试稿、toy-proj）、`periodic_jobs/`。
**关键词**：cost / spend / spending / saving(s) / bill(ing) / budget / FinOps / rightsiz / spot / reserved instance / RI / savings plan / graviton / idle / zombie / unused / gp2 / gp3 / EBS volume / snapshot / lifecycle / storage class / intelligent-tiering / NAT gateway / cross-AZ / egress / data transfer / cardinality / retention / instance family / ASG，以及中文的 成本 / 降本 / 省钱 / 费用 / 账单 / 节省 / 闲置 / 浪费 / 预算。

### 找到了什么（意外收获三条，都已写进 story_bank）

| 发现 | 出处 | 处置 |
|---|---|---|
| **StarRocks 三 warehouse 按业务语义分 on-demand/spot，spot CN 省 ~70%** | `work-contexts/career/interview/interview-6-starrocks-lakehouse.md:157,159,160,161` | 新增故事 **S05**，进内核 |
| **Iceberg 小文件治理明确由「S3 按请求次数计费」的成本模型驱动，619→49 files / FSIOTime 125×** | 同上 `:53,70` | 新增故事 **S04**，进内核，也是 headline 3 |
| **ClickHouse 僵尸表清理回收 TB 级存储 + TTL/关日志/升级审计三层预防** | `adhoc_jobs/dynamic_resume_site/content/incidents/w_zombie_oom.md:20,24,26` | 新增故事 **S06**，带诚实 reframe（原文全程是 OOM 事故治理，零成本表述） |
| 自管 K8s 省 EKS control plane 费 $3,600/月（继承决策，且他判断不划算） | `work-contexts/career/interview/interview-1-k8s_upgrade_reference.md:161` | 进中环，用于答「成本优化的边界」 |
| VM 内存 120Gi → 40-60Gi | `contexts/thought_review/victoriametrics_ops_review_20260402.md:167` | **只是 P3 建议，未执行**，进中环禁用清单 |

### 确认找不到什么

1. **RI / Savings Plans 的任何实际采购、覆盖率、承诺量、续约决策**：零。全 workspace 的 RI/SP 命中**全部**在 AWS 认证备考材料里（`work-contexts/toy-proj/okr/**/refer/*.md`、`SAP_2026*.md`），是考题选项和知识表。
2. **公司级云账单的绝对金额或降幅百分比**：零。唯一的绝对金额是 EKS control plane 的 $3,600/月（非他的动作）；唯一的 $ 数字是 `p_elastic_compute.md:17` 的 $772/$63/$24（单个 heavy pool 的建模）。
3. **FinOps 流程/工具工作**：零。无 Cost Explorer 使用记录、无 CUR 分析、无 tagging 策略落地、无 showback/chargeback、无 budget alert 配置。
4. **gp2 → gp3 迁移动作**：零。gp2/gp3 只在「知识/选型」语境出现。
5. **Graviton / ARM 实例迁移**：零。唯一 arm64 命中是 Doris FE 本地编译（开发效率，非云成本）。
6. **NAT Gateway 成本优化 / VPC Endpoint 替换 / egress 治理**：零。NAT Gateway 只在 `interview-8-k8s-cluster-build.md:20,144` 作为拓扑事实出现，无成本视角。
7. **cross-AZ 流量削减的实际动作**：零（除 `resume-expand.tex:89` 自称外无任何佐证）。
8. **S3 Intelligent-Tiering / Standard-IA / Glacier 分层落地**：零，只在认证考题里。
9. **EBS 快照清理 / 孤儿卷 / 未关联 EIP / 云资源僵尸盘点**：零。"zombie" 的全部命中都是 ClickHouse 僵尸系统表（数据层，非云资源）。
10. **实例类型/家族 rightsizing、ASG 容量 rightsizing、node group 缩容**：零实际动作。
11. **Kubecost / OpenCost 的部署、配置、报表产出**：零。只有一段浏览器 cookie 残留证明公司环境里有 Kubecost。
12. **`work-contexts/toy-proj/kindle_syncer/cost_adjustment_five_levers_model.md` 与 `production_cost_analysis_framework.md`** 是通用方法论文档，里面的百分比是示意性举例，**不是 DataVisor 真实账单**，不可当 evidence。`gig_who_are_you.md` 里的「对月度云成本负责」是**目标身份画像不是履历**，同样不可用。

### 🚨 搜索中发现的一个必须处理的风险

`work-contexts/career/profile/resume-expand.tex:86-90` 有两条 Cost Optimization bullet，其中**四个具体声明在 workspace 里零支撑**：

| 声明 | 支撑 |
|---|---|
| Spot for tolerant workloads | ✅ 有（S01、S05） |
| **Reserved baseline** | ❌ 零支撑 |
| **storage lifecycle policies** | ❌ 零支撑 |
| optimizing log retention | ⚠️ 只有间接（VM retention 分层动机是 cardinality；CH 日志 TTL 动机是 OOM），无一处连到降本 |
| **reducing cross-AZ data transfer** | ❌ 零支撑 |

`resume.tex` / `resume_agent.tex` / `resume_agent-cn.tex` 则**完全没有 cost bullet**。

**行动项**：投 `resume-expand.tex` 这一版之前，这四条要么由瑞哥补出真实经历，要么改措辞。**带着查不到支撑的 bullet 进面试，比「没做过 FinOps」严重得多**，面试官顺着简历问一句「你们 RI 覆盖率多少」就会当场断，而且断在一个诚信位置上，不是能力位置上。

---

## ⚠️ 待瑞哥补充（汇总，详细版在 `story_bank.md` S07）

**最高优先级（影响简历能不能投）**
1. RI / Savings Plans 你参与过采购决策吗？看过 coverage / utilization 吗？（决定 `resume-expand.tex:88` 的 "Reserved baseline" 是留还是删）
2. storage lifecycle policies 具体做过什么？（S3 生命周期？快照归档？gp2→gp3？）
3. cross-AZ data transfer 具体减了什么？（topology aware routing？pod 收到同 AZ？关 cross-zone LB？）
4. log retention 的优化里有哪些是**以降本为目标**做的（而不是 OOM 或 cardinality）？

**FY2026 那条降本的实质（22 条完整清单在 S07）**
5. 降幅是百分比还是绝对金额？基线和结果各是什么时候的数？数字从哪来（Cost Explorer / CUR / Kubecost / 财务）？
6. 具体动作是哪几类：rightsizing / 僵尸资源清理 / 实例族更换 / 存储分层 / 提高 spot 占比 / 关闭闲置环境 / 数据层容量调整？
7. 这件事是谁提出的？你主导还是执行？有没有需要说服人的环节？
8. `without degrading throughput or reliability` 你**怎么证明的**？有 before/after 的延迟或错误率对比吗？有没有踩过「省了钱结果出问题」的坑？
9. 做成机制了还是一次性清理？

**环境事实确认（影响答题细节）**
10. 「Cost saving dashboard」（DV-25Q1 那条记录）到底是什么？你建的吗？展示什么？数据源是什么？还在用吗？
11. 公司的 Kubecost 你用过吗？谁维护？有没有从它拿数据做过决策？内部服务 `cloud-cost-calculator` 是谁的？
12. **Doris/S3 那条链上配了 S3 Gateway Endpoint 吗？** 还是 S3 流量走 NAT？（这条直接影响 `questions.md` Q19 怎么答）
13. StarRocks 三 warehouse 和 Iceberg 小文件治理，当时是生产还是 preprod/dev？（`interview-6` 的 gap 清单提到「dev 单 FE」，讲之前要确认，不要含糊说生产）
14. 成本能不能拆到 team / tenant / 环境粒度？有没有参与过 tag 规范或治理？
