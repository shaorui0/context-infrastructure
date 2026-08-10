# 事实基线卡（面试前必读，所有数字以此为准）

面试自相矛盾是最廉价的失分方式。口头说 30 个集群、简历写 50 个，面试官会立刻怀疑所有数字。这张卡是唯一口径源，任何材料与它冲突，改材料不改卡；卡要改先在这里改。

最后核对：2026-07-29。

---

## 1. 规模数字（可以主动说的）

| 项 | 口径 | 出处 |
|---|---|---|
| AWS region | 6 | resume.tex |
| K8s 集群 | **50**（生产） | resume.tex；2026-07-20 全站裁决 |
| 节点 | 600+ | resume.tex |
| 租户数 | **不主动说** | 「40 tenants」在 2026-07-20 被移除（监控素材无出处）。被问就说 multi-tenant SaaS，按 tenant 做隔离与 SLA 追踪 |
| active series | ⚠️ **口径冲突，面试前必须核实**，见 §2.5 | resume.tex 写 ~1.2M |
| samples/sec | ~80K | resume.tex |
| SRE 团队规模 | 4 人，负责全公司基础设施层 | intro.md |
| 我的分工 | cluster lifecycle / observability / 分析数据平台（Doris 存算分离 + 引擎内查询路由 + 弹性算力控制面）三块；另三人做 oncall 轮值、runbook、tenant onboarding。我做 L3（建系统消灭 L1-L2 问题） | intro.md（原文第二块写的是 traffic control，已按 §5.1 替换） |

## 2. 项目数字（每条都能指到 evidence）

| 项目 | 数字 | 出处 |
|---|---|---|
| K8s 升级 | 1.24→1.29，跨 50 集群，单集群 **18-21h（两人）→ 6-8h（一人 + 系统）**，零事故。3-4h 是路线图目标，见 §2.8 | p_k8s_upgrade.md |
| 可观测性迁移 | Prometheus Federation → VictoriaMetrics；OOM 每周 2-3 次 → 零；查询延迟/数据滞后 45s → <5s | resume.tex, intro.md |
| 告警体系 | 三层告警 + per-tenant SLI recording rules（租户级故障隔离与 SLA 追踪） | resume.tex |
| oncall | 20+ P1/P2，平均 MTTR ~30min | resume.tex |
| CH→Doris | ~5.2B 行 / ~4 TiB source / ~3,700 列；99.945% 对账 | content_plan.md 数字口径备忘 |
| 弹性算力降本 | burst 场景省 92%（On-Demand）到 97%（spot） | interview_story.md |
| 单查询成本比 | 1,240×（一条窗口查询 ≈ 1,240 条点查） | interview_story.md |
| compaction 事故 A | score ~2,500，disable_auto_compaction 死亡螺旋 | content_plan.md |
| compaction 事故 B | score ~4,504，DROP 表孤儿 tablet 卡死 | content_plan.md |
| Doris FE 引擎工作 | 两个新 SQL 语句（`EXPLAIN ESTIMATE PLAN` / `EXPLAIN ROUTE PLAN`），**15 files / +1,310**，路由规则 15 条 | 01 方向整编实测（旧口径 7 files/+589 已过时） |
| 路由分类器效果 | heavy recall 7% → 100%；light precision 86%；golden corpus **197** 条 | 同上（旧口径 189 已过时） |
| 存储降幅 | 90%（官方口径，非自测） | 01 方向纪律提醒 |

⚠️ **Doris 补丁体量与 golden corpus 的旧数字仍印在 dynamic_resume_site 与部分材料里**（+589/−0、189 parity）。对外讲用新口径 15 files/+1,310、197 条，并考虑回头同步站点。

**两次 compaction 事故分开讲，不许混成一个。** 用户记忆里的「5k」是 B 那次。

## 2.5 🔴 VictoriaMetrics 拓扑与规模：面试前必须本人核实

这是目前发现的最高风险项。两套材料互相矛盾，而其中一个数字已经印在简历上。

| 项 | 说法 A（简历 + 7 月材料） | 说法 B（4/2 实测运维复盘） |
|---|---|---|
| 部署模式 | cluster 模式：vminsert×2 / vmstorage×3 / vmselect×2 | **Single 模式，单 Pod** |
| active series | ~1.2M | **~793k** |
| 磁盘 | 未记 | 4.7TB / 6.2TB |
| 出处 | `resume.tex`、`p_vm_platform.md` | `contexts/thought_review/victoriametrics_ops_review_20260402.md` |

旁证偏向说法 B：6/26 的 galileo 调查报告里 Grafana datasource 名仍是 `vms-victoria-metrics-single-server`。而且 `p_vm_platform.md:169` 的作者注自己也承认两个口径不一致。

**风险**：如果口头讲「我部署了 cluster 模式，做了 vminsert/vmstorage/vmselect 三层分离」，面试官往下问分片策略、replication factor、vmstorage 扩容怎么做，而实际是 single 节点，这会被识别为编造。single 模式与 cluster 模式的运维差异是资深面试官一问就知道的。

**行动**：面试前跑一次确认当前真实拓扑与 series 数。核实前的安全说法是描述能力而不是拓扑：「我把 Prometheus Federation 迁到了 VictoriaMetrics，消除了每周 OOM，数据滞后从 45 秒进到 5 秒内」。这三个数字没有争议。**核实后回来改这一节和简历。**

如果确认是 single 模式，这件事本身可以变成加分项：选 single 而不是 cluster 是一个有意识的取舍（在这个规模下 single 的运维复杂度低得多），能讲清什么时候必须上 cluster 才是真懂。

## 2.6 ⚠️ 告警体系的成熟度口径

4 月材料把三层告警写成已建成体系；7 月的实测 baseline 是 367 条规则、每天约 960 条告警、85% 落在默认 P3、还存在旁路脚本。

简历写的是 designed 3-tier alerting with per-tenant SLI recording rules，这个措辞站得住（设计和 recording rules 是真做了）。但**不要顺势说「我们的告警体系已经很健康」**。被问告警质量时的安全说法：我建了分级结构和 per-tenant SLI 记录规则，然后我自己做了一次 30 天审计，发现约 80% 的 page 不可操作、85% 落在默认 P3，所以我现在推的是准入门槛与 owner 归属这一层。这个答法把弱项变成了「我度量了自己的系统」的信号。

⚠️ 两个数字不要混说：「80% 不可操作」是可操作性口径，「85% 默认 P3」是分级失效口径。

⚠️ 通知平台：4 月材料写 PagerDuty，7 月写 OpsGenie。面试前确认现用哪个。

## 2.7 🔴 `resume-expand.tex` 的 Cost Optimization 小节：投出去之前必须改

`work-contexts/career/profile/resume-expand.tex:86-90` 写了两条降本 bullet。逐条核对 workspace 全部素材后，里面有四个具体机制找不到任何支撑。

| 简历原文声明 | 支撑状态 |
|---|---|
| `Spot for tolerant workloads` | ✅ 有。StarRocks 的 refresh_wh / adhoc_wh 真跑在 spot 上；Doris heavy 池是 spot 设计 |
| `On-Demand scaling` | ✅ 有 |
| `Reserved baseline` | ❌ 零支撑。没有任何 RI/SP 采购参与、coverage/utilization 查看的记录 |
| `storage lifecycle policies` | ❌ 零支撑。没有 S3 生命周期策略落地记录 |
| `reducing unnecessary cross-AZ data transfer` | ❌ 零支撑 |
| `optimizing log retention` | ⚠️ 只有间接。retention 分层确实做了（90d/30d/15d），但动机是 cardinality 治理与 OOM，不是降本 |

**为什么这条最危险**：面试官顺着简历问一句「你们 RI 覆盖率多少」或者「S3 生命周期策略是怎么分层的」，答不上来的失分位置是**诚信**，而不是能力。技术答不出可以说没做过，简历上写了却答不出是另一回事。

**处置选择（二选一，面试前必须做）**：

1. 如果这些事其实做过但没落盘：补事实，把动作、时点、数字写下来，然后这一节可以留。
2. 如果确实没做过：改措辞，把 bullet 收缩到有支撑的部分。安全的重写方向是从「运营级降本」改成「架构级降本」，后者他有真东西且更高级：

> Cut steady-state cost of the analytics tier by restructuring capacity rather than renegotiating pricing: pushed query classification into the engine so a heavy-query compute pool runs at zero replicas until demand arrives, and split warehouses by business semantics so only latency-critical paths stay on On-Demand while refresh and ad-hoc workloads run on Spot.

注意 `resume.tex`（主简历）与 `resume_agent*.tex` 里**没有** cost bullet，所以这个风险只在 expand 版。投哪一版要清楚。

⚠️ 顺带核查：同文件 `:81` 写 `blue-green validation and progressive traffic warm-up using SLO`，K8s 升级的执行证据目前只到 `status: draft` 的 runbook，没有带日期的执行日志或复盘。这条不算无支撑（设计确实有），但被追问「哪次升级、哪天、当时的 SLO 读数是多少」要能答。

## 2.8 🔴 K8s 升级耗时：简历把已达成和路线图目标合并了

`resume.tex:93` 写 `18-21h to 3-4h`。但 7 月的 `p_k8s_upgrade.md:33` 原文是：

> 18–21 hours with a two-person pair became 6–8 hours with one operator plus the system; the automation roadmap (external alert gating, synthetic health checks, auto-promotion after canary) targets 3–4 hours per cluster, a projected 60–80% reduction.

也就是说 **6-8h 是已达成，3-4h 是三项尚未实施的自动化（外部告警门控、synthetic health check、canary 自动放行）的目标值**。这三项在 `interview-1-k8s_upgrade_reference.md:177` 也确认是 roadmap。

**为什么这条一定会被拆穿**：面试官问「那 3-4 小时里还剩哪几步需要人」，答不上来，因为差额全在没做的部分里。

**正确口径，而且比原来更强**：口述统一说 6-8h。要放大战果就换算人时：原来是两个人做 18 到 21 小时，也就是 36 到 42 人时；现在是一个人加系统做 6 到 8 小时。**人时降了大约 5 倍**，这个说法既诚实又比「18-21 到 3-4」更有说服力，而且自然带出「省的是人的注意力不只是墙钟时间」这层判断。

**简历建议改成**：`18–21h (two-person) to 6–8h (single operator), with automation roadmap to 3–4h`。

⚠️ 同源风险：`resume-expand.tex:108` 的 `IaC (GitOps/Ansible)` 里 GitOps 无任何支撑（全库无 ArgoCD/Flux 证据），建议改成 git-declared desired state。

⚠️ 「零事故」的归因要主动交代：最大一份来自升级时集群 dark 这个架构条件，而不只是操作纪律。主动说这句是加分，被问出来是减分。

## 3. 已废弃口径（说出来就是自伤）

| 别再说 | 说什么 | 为什么 |
|---|---|---|
| 30+ K8s clusters | 50 clusters | intro.md 是 3 月写的，已过时。resume.tex 与全站已统一 50 |
| 40 tenants / 40 clients | 不提数字，说 multi-tenant per tenant | 2026-07-20 裁决移除，无出处 |
| 3 years as SRE | 4+ 年全职工程经验（2022/06 起），其中 SRE 约 2.5 年（Datavisor 2025/03 起） | intro.md 有「more than 3 years as a SRE」，与实际任期不符，被追问会露 |
| 6B 行 / 6T | ~5.2B 行 / ~4 TiB source | 口述数字无出处，evidence 值才可用 |
| contributed to Apache Doris | engine-level work on an Apache Doris fork, proposed as DSIP | patch 未进 upstream |
| 「我做了 spot 中断回退 / 容量准入 / 多集群锁」 | 见 §5 归属边界 | git 作者是别人 |

## 4. 任期与个人信息

| 项 | 口径 |
|---|---|
| Datavisor | Senior SRE (Japan) 2025/10 至今；SRE (China) 2025/03 - 2025/10 |
| Intel | Cloud Software Development Engineer 2022/06 - 2025/02 |
| 全职年限 | 约 4 年（2022/06 起） |
| 实习 | Tencent / ByteDance / App Annie / Baidu（2020-2021） |
| 学历 | 硕士 北京科技大学 计算机（2019/09-2022/06，三年制是中国标准）；本科 文华学院 电子信息工程 |
| 签证 | 高度人材（HSP），5 年有效 |
| 日语 | 无 JLPT，工作全程英文 |
| 现居 | 神户（Kobe） |
| notice period | 内部 transfer 流程约 1 个月；拿到 offer 后 3 周到 1 个月可入职 |
| 现薪 | ⚠️ 待确认：intro.md 正文写 ~9M 日元、注释里写 10M。面试前必须定一个数，期望值报 10M+ |
| 合同状态 | 内部 transfer 的合同制，公司口头承诺一年后转正 |
| 离职动因 | 三条：想要正式雇佣（现为合同制）；想要更大 scope（日本办公室小、公司重心在北美）；想要更强的工程文化环境 |

## 5. 归属边界（说错会被追问穿，比数字更硬）

### 5.1 🔴 自动切流系统不是我做的（2026-08-02 本人确认）

那套跨 4 层后端（ALB / API Gateway / Global Accelerator / K8s Ingress）的 Master-Detector 自动切流控制面、5-15 分钟到秒级那个项目，**不是瑞哥做的，细节也不掌握**。已从全部备考材料移除，不作为可讲的故事。

⚠️ **但它仍印在旧材料上**：`resume.tex:86` 写 `Designed and built auto traffic-switch system`，`resume-expand.tex` 与 `intro.md` 也有（intro 还带了「I defined the problem scope, designed the service, built it」的 ownership 注解）。bullet 体系计划重做，重做时这条不要带过去。在重做完成之前，如果用旧版简历面试，被问到就直说那是团队里另一位同事的系统，我不是作者。

原「三块职责」里的第二块是它，已替换为分析数据平台（Doris 存算分离 + 引擎内查询路由 + 弹性算力控制面），见 §1 分工行与 `behavioral_and_recruiter.md` §5。

保留的一处：`01_doris_db_operations/story_bank.md` 的大租户 QPS 联合止血故事里有「流量 50/50 分流」这个止血动作。那是 oncall 时**使用**切流能力，与**建设**那套系统是两回事，可以讲，但别顺势把系统归到自己名下。

**dcluster 平台可靠性那批不是我做的。** spot 中断回退、容量准入、多集群锁修复、审计日志，git 作者是 junhan.ouyang / Runzi Yang。我做的是弹性 CN 控制面的幂等扩缩语义、monitor 队列/空闲驱动闭环、与 Doris FE 的读信号契约。

**Arrow Flight 与 FE memory-kill backstop 是伙伴团队做的。** 标准答法：ROUTE PLAN 分类器是我在 Doris fork 里实现的；Arrow Flight 传输是我定输出契约、伙伴团队实现；FE 侧内存 kill 兜底同理。

**Intel BKC 那段按 p_bkc.md 的 SOURCES 分栏。** 只有「自研常驻 daemon、~30 台多集群、E810、systemd 层、before 是文档加手工脚本、L1 审计层」能说「我做了」；L2-L4 能力层、隔离核 jitter、跨重启状态机、reboot token、签名 profile、具体 SKU 全是设计口径，不许升格。

**preprod 边界。** CH→Doris 是 preprod 生产规模验证，10T 生产化推进中。绝不在开场自曝，放结尾讲，配「10T 生产化推进中」顶回去。被直接问就直说，不遮掩。

**重查询 <1% 流量是设计假设，不是实测。** 引用必须标明。

## 6. 面试前 5 分钟自检

1. 集群数说 50 了吗
2. 年限说 4 年（不是 3 年 SRE）了吗
3. 租户数忍住没说数字吗
4. 两次 compaction 事故没混吗
5. 说 fork 不说 contributed 了吗
6. dcluster 归属没越线吗
7. preprod 留到结尾了吗
