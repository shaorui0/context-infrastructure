# Senior SRE Interview Prep：执行计划

> **修订 2026-08-02：自动切流系统整体移除。** 瑞哥确认那套跨 4 层后端的 Master-Detector 自动切流控制面（5-15min→秒级）**不是他做的**，细节也不掌握。已从 05、07、90 三处彻底移除，不作为可讲故事。本文件下方 Phase 1/2 的盘点与任务描述里凡提到 traffic switch 的均已失效，以 `90_cross_cutting/number_baseline.md` §5.1 为准。方向 05 的支柱改为三条自有故事：集群级 blue/green 加 Kafka 复制暂停追平、51.7 亿行跨引擎迁移对账、监控栈双写并行加逐规则语义 diff 门禁。「三块职责」的第二块由切流换成分析数据平台。
>
> 简历 bullet 体系计划整体重做（2026-08-02 决定），因此本轮不改 `resume.tex` / `resume-expand.tex` / `intro.md`，只在 number_baseline 记录风险。
>
> **状态 2026-07-29：全部 Phase 完成。** 39 文件 / 约 10,750 行 / 62 story / 178 题。成果导航见 `README.md`，数字口径见 `90_cross_cutting/number_baseline.md`。
>
> 修订 (Phase 1-3 完成后)：盘点有四处漏项，已由执行阶段补上并写进对应方向。
> (1) 方向 6 漏了两个真实成本故事：**StarRocks 三 warehouse 按业务语义分 OD/spot**（spot CN 省约 70%）与 **Iceberg 小文件治理由 S3 请求计费模型驱动**（619→49 files、FSIOTime 125×），另有 ClickHouse 僵尸表清理（1.21 TiB）。均已进 06 内核。
> (2) 方向 6 漏了最贴骨架的数据层 blue/green 故事：**VictoriaMetrics 迁移的双写并行两周 + 逐条告警规则两侧语义 diff 门禁 + 旧栈 live 作 fallback**，跑满 12 环节里的 11 个。已进 05。
> (3) 方向 6 的 MirrorMaker 素材远超预期：`knowledge_raw/runbooks/` 有完整跨集群切换 runbook（双向 scale 0、先启动接收侧、切回门禁 lag<1000）。已进 05。
> (4) `rules/skills/fp/` 在本 workspace 不存在，真实路径是 `work-harness/code_repos/infra/cre6630-infra/learn_fp/knowledge/`（跨仓库）。
>
> **执行阶段发现的五处事实风险**（两处涉及简历，详见 `README.md` §3）：resume-expand.tex 的 Cost Optimization 四条声明零支撑；K8s 升级 3-4h 实为路线图目标（已达成是 6-8h）；VM 拓扑 cluster vs single 与 1.2M vs 793k series 冲突；intro.md 口头稿数字过时；K8s 升级「最接近出事的一次」无素材。
>
> 修订 2026-07-29 (Phase 0)：核对通过，所有引用路径存在。三项盘点补充：
> (1) `contexts/fy2026_self_assessment.md` 把「Cloud cost optimization：reduced cloud spend without degrading throughput or reliability」列为 FY2026 已达成目标，说明方向 1 有真实的公司级降本故事，不止 dcluster 架构级降本，执行时需挖出具体动作（06 目录的首要待确认项）。
> (2) 两个未盘点项目：**Iceberg 部署**（与 StarRocks 同批）、**Customer Insight 多源数据管道**（给客户支持团队做统一分析入口）。前者进 01，后者可作数据集成素材备用。
> (3) Self-assessment 的 Q2/Q4 自陈弱项 = 告警噪音与 alert governance，与 `p_alert_gov.md` 同源，是行为面「发现问题并推动改进」的现成素材（进 90）。
> (4) `resume.tex` 事实基线：50 clusters / 6 AWS regions / 600+ nodes / ~1.2M active series / ~80K samples/sec / Prometheus Federation→VM 使 lag 45s→<5s 且消除每周 OOM / traffic-switch 跨 4 后端 5-15min→秒级 / K8s 1.24→1.29 18-21h→3-4h / 20+ P1P2 MTTR ~30min。任期：Datavisor SRE 2025/03→2025/10，Senior SRE (Japan) 2025/10→present；Intel 2022/06→2025/02（全职约 4 年）。

> 写于 2026-07-29（Fable 5 规划），由后续 session 的执行模型按此文档执行。
> 目标：把 7 个方向整编成一个体系化的 interview prep folder，每个方向有明确的「核心圈」（我能讲到什么深度、边界在哪），故事可溯源、归属诚实、基础知识补齐。

---

## 0. 背景与成功标准

瑞哥准备 senior SRE role 面试。素材分散在三处，已有大量一手内容，但缺「面试视角的体系」：

1. `adhoc_jobs/dynamic_resume_site/`：16 篇长文（content/projects, growth, incidents, perspectives）、9 域雷达分数、featured case study（CH→Doris）、oncall track record、`research/interview_story.md`（开场故事定稿骨架）
2. `work-contexts/career/interview/`：2026 年 3-6 月的 8 组面试稿（k8s upgrade / traffic switch / monitoring / oncall / cicd / starrocks lakehouse / agent harness / doris routing OOM / k8s cluster build，另有 clickhouse/kafka/mysql SRE 单页 + intro.md + 英文表达模板）
3. `contexts/`：3 篇 Doris survey（migration arsenal 20260717、CH vs Doris 存算分离 20260716、宽表点查优化 20260724）、`resume_highlights_doris_dcluster.md`（含归属边界）、`fy2026_self_assessment.md`

**成功标准（执行完成的定义）：**

- 输出一个 folder：`adhoc_jobs/senior_sre_interview_prep/`，7 个方向各一个子目录 + 各自 README + 顶层 README 总纲
- 每个方向画出「核心圈」三环：内核（一手 evidence、能扛住 5 层追问）/ 中环（做过但浅，有标准口径）/ 外环（纯知识，需回顾补课）
- 每个故事的数字能指到 evidence 文件；归属边界不越线（见 §4 纪律）
- 弱方向（FinOps 体系、AWS fundamentals、blue/green 方法论、Terraform）有系统性的基础回顾材料，不是空目录
- 有一张跨方向的 story 复用矩阵：一个故事在哪几个方向可以讲、各方向的切入角度

**这不是公开产物。** 不需要脱敏（客户名、内部代号可以出现，方便自己记忆），但**归属诚实**是硬约束，比脱敏更重要：面试时说错归属会被追问穿。

---

## 1. 七方向资产盘点与差距

按「资产厚度」排序，先说强的。

### 方向 2：Doris / DB 运维 / HA / 存算分离 / 监控（最强，整编为主）

内核素材：
- `dynamic_resume_site/content/case_study_ch_to_doris.md`：featured case study，99.945% 对账
- `contexts/survey_sessions/ch_to_doris_migration_interview_arsenal_20260717.md`：已经是面试武器库形态
- `contexts/survey_sessions/clickhouse_vs_doris_storage_compute_ai_load_survey_20260716.md`：引擎级四支柱论证
- `contexts/survey_sessions/doris_wide_table_point_query_optimization_survey_20260724.md` + memory `reference_doris_event_result_point_query`：点查优化，「扇出是地板不是 S3」
- `work-contexts/career/interview/interview-8-doris-query-routing-oom.md`（23KB，最新 6/17）
- `contexts/resume_highlights_doris_dcluster.md`：ESTIMATE/ROUTE PLAN 两个 FE feature + dcluster 幂等扩缩语义，git-attributed
- 事故素材：两次 compaction 事故（score ~2500 / ~4504 要分开讲）、四 OOM 点、1.7B livelock、EBS snapshot 恢复 5.2B 行（DR，RPO≈24h 隐含、一次性演练非制度）
- `work-contexts/career/interview/interview-6-starrocks-lakehouse.md`、`interview-clickhouse-sre.md`、`interview-mysql-sre.md`、`interview-kafka-sre.md`

差距：素材多但散，缺一个「按面试题形态组织」的索引（HA 专题、备份恢复专题、监控指标专题各自的答题骨架）。MySQL/Kafka 单页较旧（4/1），按需刷新即可，不是重点。

### 方向 4：监控体系 / SLO（强，整编为主）

内核素材：
- `work-contexts/career/interview/interview-3-monitoring_architecture.md`（29KB，最厚的一篇）+ reference
- `dynamic_resume_site/content/projects/p_vm_platform.md`：VM+Grafana+Loki，50 集群 / 1.2M series
- `dynamic_resume_site/content/projects/p_alert_gov.md`：告警治理，熵增分析
- `dynamic_resume_site/content/growth/g_slo_topdown.md`：从 CPU 到 SLO
- skill `bestpractice_sre_reliability_models`（Availability 概率分解 / Overload λ vs μ / SLI-Histogram-Quantile-SLO 四层分离）+ `bestpractice_traditional_sre_methodology`（7 层工具箱）
- memory `reference_dv_ingress_latency_decomposition`（t-digest 对 P100 失明等一线细节）

差距：SLO 的「制度落地」部分（error budget policy、burn rate 告警的多窗口设计）实践偏浅，属于中环，需要标准口径而非编故事。

### 方向 5：AIOps（强，且是差异化卖点）

内核素材：
- `dynamic_resume_site/content/projects/p_agentops.md`：四控制原语 Spec/Loop/Hook/Fork，背书代码 `agents/sre_oncall_triage_skill/`
- `work-contexts/career/interview/interview-7-agent-harness-engineering.md`
- `dynamic_resume_site/content/perspectives/v4_ai_agents.md`
- skills：`bestpractice_agent_reliability_engineering`、`bestpractice_agent_observability`、`bestpractice_agent_harness_architecture`
- 真实运行的 oncall triage pipeline（Phase Lock / Iron Laws / Subagent Isolation / Quote-the-line）

差距：需要把「个人工程」翻译成「团队/组织价值」的 senior 叙事，以及准备对面质疑（幻觉怎么办、审计怎么做、和 Runbook automation 有什么本质区别）的防线。业界对标（PagerDuty/incident.io 的 AI、K8sGPT 等）要一次轻调研。

### 方向 3：IaC / Jenkins / TF / Packer / K8s 升级（中强，Jenkins+K8s 强，TF 弱）

内核素材：
- `dynamic_resume_site/content/projects/p_k8s_upgrade.md` + `work-contexts/career/interview/interview-1-k8s_upgrade(.md/_reference.md)`：1.24→1.29 跨 50 集群，18-21h→3-4h 零事故
- `work-contexts/career/interview/interview-8-k8s-cluster-build.md`（16KB，6/17 新）
- `dynamic_resume_site/content/projects/p_jenkins.md`（幂等/可监控/配置即代码三判据）+ `content/integration/jenkins_facts.md`
- `work-contexts/career/interview/interview-5-cicd_reliability.md`
- IaC 四层：Packer+Ansible+kubeadm；`p_bkc.md`（Intel 时期，注意真实性边界已写在文内 SOURCES 分栏）

差距：**Terraform 是明确的外环**。他的栈是 Packer+Ansible+kubeadm，TF 需要基础回顾（state 管理、plan/apply 语义、module 设计、drift、和 Ansible 的边界），并准备「为什么我们没用 TF、如果引入怎么做」的诚实答法。

### 方向 6：Blue/green clusters / data（中，故事有、方法论散）

内核素材：
- `dynamic_resume_site/content/projects/p_traffic_switch.md` + `work-contexts/career/interview/interview-2_traffic_switch(.md/_reference.md)`
- K8s 升级本质上是 blue/green cluster 模式的实例，可以并线讲
- 数据层素材：MirrorMaker（fp skill 里有运维事实）、CH→Doris 迁移的双跑对账（99.945% 本身就是 data blue/green 验证故事）

差距：缺方法论骨架：blue/green vs canary vs rolling 的选型判据、**数据层切换**的完整谱系（双写一致性、backfill、对账、回滚点设计、有状态服务的切换）。这块是面试高频，需要一篇体系化整理，把已有的三个故事挂到骨架上。

### 方向 1：AWS / cost / FinOps（弱-中，有一个好故事，缺体系）

内核素材：
- dcluster 弹性算力的成本故事：heavy 池 `replicas:0` 零成本、spot 上弹起、存算分离使杀 spot 安全（`resume_highlights_doris_dcluster.md` §1）、1,240× 单查询成本比（doc 71）
- `fy2026_self_assessment.md` 有 cost 相关内容（执行时读一遍提取）
- ASG/LT 层「消费修补」深度（诚实边界：别写过头）

差距：**FinOps 体系是外环**：CUR/Cost Explorer/tagging 策略、RI vs Savings Plans、unit economics（cost per query / per tenant）、showback/chargeback、S3 存储分层与生命周期、数据传输费陷阱（NAT/跨 AZ）。需要一次系统性基础调研 + 把 dcluster 故事改写成 FinOps 语言（他实际做的是「架构级降本」，这是比「买 RI」更高级的答法，要把这个定位讲清楚）。

### 方向 7：AWS fundamentals（compute/storage/network/IAM）（弱，纯补课方向）

内核素材（散点）：
- EBS snapshot DR（5.2B 行恢复）、ASG/LT、spot 生命周期
- `dynamic_resume_site/knowledge_raw/patterns/pattern-aws-k8s-networking-troubleshooting-pattern.md`
- `work-contexts/toy-proj/kindle_syncer/fintech-prod-aws_plus_k8s.md`（旧材料，执行时评估可用性）

差距：这是 7 个方向里唯一的纯基础回顾方向。需要按 compute（EC2 家族/placement/spot 中断处理）、storage（EBS 类型与 IOPS 模型/S3 一致性与分层/EFS 边界）、network（VPC/子网/路由/SG vs NACL/ENI/负载均衡器谱系/PrivateLink/跨 AZ 流量）、IAM（policy 评估顺序/role assumption/IRSA/最小权限落地）四块出复习卷，并且**每块都从他的真实场景出发**（例：IRSA 在 50 集群怎么管、Doris BE 的 EBS 选型为什么是 gp3）。

---

## 2. 输出 folder 结构

```
adhoc_jobs/senior_sre_interview_prep/
├── PLAN.md                      # 本文件
├── README.md                    # 总纲：7 方向核心圈总图 + story 复用矩阵 + 进度表
├── 01_doris_db_operations/      # 方向 2（最强的排最前，编号按优先级不按用户列举顺序）
├── 02_monitoring_slo/           # 方向 4
├── 03_aiops/                    # 方向 5
├── 04_iac_cicd_k8s/             # 方向 3
├── 05_blue_green_data/          # 方向 6
├── 06_aws_cost_finops/          # 方向 1
├── 07_aws_fundamentals/         # 方向 7
└── 90_cross_cutting/            # intro/opening story、英文表达、senior 行为面、mock 题库
```

每个方向子目录统一四件套（缺哪件补哪件，已有的链接过去不重复复制）：

1. `README.md`：核心圈三环图（文本表格即可，不用画图）：内核/中环/外环各列 3-8 条，每条标注 evidence 路径或「需补课」；再加一段「这个方向我的一句话定位」
2. `story_bank.md`：该方向的战story，每个故事：情境→动作→结果（数字带出处）→ 5 层追问防线（面试官会怎么钻，每层怎么答）→ 归属边界提示
3. `fundamentals.md`：基础知识回顾，Q&A 形态，从他的真实场景出发组织，不是教科书目录
4. `questions.md`：该方向高频面试题清单 + 每题的答题骨架（一句定位 + 展开结构 + 挂哪个故事）

`90_cross_cutting/` 放：opening story（基于 `research/interview_story.md`，AI 负载钩子 + 61s/60ms 饥饿案例）、story 复用矩阵、senior 行为面（影响力域是雷达最弱的 52 分，行为面要用告警治理倡议、内部培训、跨团队契约设计这几个素材撑）、英文表达（`expression_training_template.md` 已有模板）。

---

## 3. 执行阶段

### Phase 0：核对与骨架（半小时级）

1. 重新核对本 PLAN 引用的所有路径存在（材料在动，7/29 之后可能有变化）
2. 建 folder 骨架 + 顶层 README 占位
3. 读 `fy2026_self_assessment.md` 和 `work-contexts/career/interview/intro.md`，提取本 plan 未覆盖的素材，回填盘点

### Phase 1：强方向整编（方向 2/4/5 → 目录 01/02/03）

性质是**整编不是创作**：读已有材料，重组成四件套。可以并行派 3 个 subagent（一方向一个），执行前先读 `rules/skills/workflow_parallel_subagents.md`。给 subagent 的约束：

- 只准从列出的 evidence 文件取材，不许发明数字和故事
- story_bank 的 5 层追问防线是主要增量产出（已有材料大多只写到故事本身）
- 产出必须带 evidence 路径引用

### Phase 2：弱方向补课（方向 3 的 TF 部分、6、1、7 → 目录 04/05/06/07）

两类工作混合：

- **方法论/基础调研**（可用 `workflow_deep_research_survey` 的轻量版，或直接 WebSearch）：FinOps 体系、AWS fundamentals 四块复习卷、blue/green 数据层切换谱系、Terraform 核心概念。每份 fundamentals 都必须回答「这个知识点在我的 50 集群 / Doris / spot 弹性场景下长什么样」，否则就是又一份网上抄来的 cheatsheet，没价值。
- **故事重写**：dcluster 成本故事翻译成 FinOps 语言；K8s 升级 + traffic switch + CH→Doris 双跑对账挂到 blue/green 骨架上。

### Phase 3：跨方向整合（目录 90 + 顶层 README）

1. story 复用矩阵：行 = 故事（约 12-15 个），列 = 7 方向，格 = 该方向的切入角度一句话
2. 顶层 README 的核心圈总图：7 方向各一行，内核/中环/外环一览
3. senior 行为面素材整理
4. mock 题库：每方向抽 5 题混合成一套，标注难度

### 验收门禁（每 phase 结束自查）

- 每个数字有出处路径；找不到出处的标 ⚠️ 待确认，不许静默保留
- 归属边界零违规（见 §4）
- 每方向 README 的三环各至少 3 条，外环条目有对应的 fundamentals 内容
- 抽 3 个故事模拟追问 5 层，防线答案在 story_bank 里真实存在

---

## 4. 纪律（硬约束，抄给每个 subagent）

1. **归属边界**（源：`contexts/resume_highlights_doris_dcluster.md` §0）：dcluster 平台可靠性那批（spot 中断回退/容量准入/多集群锁修复）git 作者是 junhan.ouyang / Runzi Yang，不是瑞哥，不入主线故事。Arrow Flight 传输、FE memory-kill backstop 是伙伴团队的，瑞哥的说法是「ROUTE PLAN 分类器是我实现的，Arrow Flight 是我定契约、伙伴团队实现」。BKC/Intel 的真实性边界按 `p_bkc.md` SOURCES 分栏执行。
2. **数字口径**：行数/容量用 evidence 值（~5.2B 行 / ~4 TiB source / ~3,700 列），集群数统一 50，用户口述 6B/6T 无出处不用。两次 compaction 事故（~2500 / ~4504）分开讲不混。
3. **开源措辞**：fork 口径（"engine-level work on an Apache Doris fork, proposed as DSIP"），PR merge 前不说 contributed to Apache Doris。
4. **诚实分环**：做过但浅的进中环并写标准口径，没做过的进外环补课。宁可环画小，不许把外环的东西包装成内核。SLO 制度落地、ASG/LT 深度、DR 的一次性演练性质，都按此处理。
5. 本 folder 是私人备考材料，不脱敏（客户名可出现），但**永不进公开产物**；如果日后往 dynamic_resume_site 搬，走 content_plan.md 的脱敏规则。

---

## 5. 执行提示

- Phase 1 的三个方向互相独立，适合并行；Phase 2 的调研类任务也可并行，但 FinOps 故事重写依赖方向 1 的调研产出，注意次序
- interview-N 系列文件是 3-6 月写的，和 dynamic_resume_site 7 月的材料有口径漂移的可能，以 7 月材料和 content_plan.md 数字口径为准
- 执行过程中发现本 plan 盘点有错漏，直接改 PLAN.md 并在顶部记一行修订日志
- 全部完成后更新 `rules/WORKSPACE.md` 快速查询区（规划 session 已加了一行占位）
