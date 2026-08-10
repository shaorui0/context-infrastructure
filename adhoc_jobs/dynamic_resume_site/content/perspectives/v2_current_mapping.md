# META

id: w-v-mapping
kicker_en: PERSPECTIVE
kicker_cn: 视角
title_en: An audit of my own radar
title_cn: 我当前做了什么，匹配什么能力
sub_en: How the nine scores were derived from evidence density, what each one means, and a behavioral record that independently cross-checks the shape.
sub_cn: 九个分数如何从证据密度推导、每个分数意味着什么，以及一份独立交叉验证雷达形状的行为记录。
domains: [data, obs, dist, platform, incident, infra, release, influence, security]

# EN

## How the scores are produced

The method comes first, because without it the numbers are noise. Each depth score on the radar is derived from evidence density: the count and depth of flagship artifacts (incident write-ups with quoted evidence, measured results that survived re-measurement), the amount of methodology distilled out of the work (runbooks, debug trees, standing rules), and whether anything is publicly verifiable. It is explicitly not self-assessment.

The reason: a self-rated score carries no information for a reader. Self-ratings are uncalibrated across people, and the incentive to inflate is structural. An 82 backed by a certified migration is a claim you can audit; an 82 backed by confidence is a mood. Deriving scores from evidence also means they can be wrong in inspectable ways — the property that makes them worth publishing.

## The nine domains, one paragraph each

**Data & State — 82/90.** Flagship: a ClickHouse-to-Doris migration of ~5.2B rows and ~3,700-column tables, certified 99.945% row-complete over the full unsampled dataset, with four non-obvious OOM classes and a livelock root-caused at engine level. Separately, a full-scale restore drill: 5.2B rows recovered from snapshot and verified by query. 82 is the tallest axis because the evidence goes deepest — into engine code. It is not 90 because the depth is concentrated in one engine family and the restore drill was episodic, not institutional.

**Observability — 80/85.** A multi-tenant monitoring platform (50 clusters, 1.2M active series) built and operated; forensic use of telemetry, including 74.7M rows of production query logs mined to reverse a table-design decision; latency decomposition that proved a suspected layer innocent. The gap to 85 is not tooling — it is SLO operation, covered under incident.

**Distributed Systems — 78/88.** Compute-storage separation argued as a trade (state concentrates rather than disappears) and then operated; a two-tier admission-control design whose safety never depends on its classifier being right; the finding that point-lookup latency was file-open-bound, not scan-bound. The distance to 88 is honest: I operate and reason about consensus and replication layers; I have not designed one.

**Platform & Automation — 76/85.** Controllers preferred over scripts, and the standard applied in reverse: a bespoke scaler collapsed to a single JSON-patch once the platform operator matured. An AI-agent triage harness and an agent control plane, plus upgrade automation. The gap: none of this has yet been operated as a product with users beyond my own team.

**Incident & Reliability — 72/82.** 20+ production P1/P2 incidents as primary on-call with MTTR around 30 minutes; two compaction incidents taken to engine-level root cause; a tail-latency investigation that ended in a timeout constant masquerading as physics. 72 scores response strength. What it deliberately does not include — because the record does not — is a season of SLO and error-budget operation. That is most of the distance to 82.

**Infra & Capacity — 70/80.** A four-layer IaC pipeline (image baking, orchestration, configuration, control-plane bootstrap); 50 clusters, 600+ nodes, 6 regions operated as primary on-call; capacity decisions from measurement, including proving scale-out useless before money was spent. One boundary stated plainly: my autoscaling-group and launch-template depth is consume-and-patch, not from-scratch fleet design.

**Release & Change — 68/78.** Production Kubernetes upgrades 1.24 to 1.29 across 50 clusters with zero incidents, per-cluster time cut from 18–21 hours with two people to 6–8 with one operator plus purpose-built automation; a dry-run render-diff that caught a chart upgrade silently resetting a serving pool from 4 replicas to 1. The gap: progressive delivery at the service level as routine practice, not as upgrade-project discipline.

**Influence & Communication — 52/75.** An internal training deck and guided onboarding for the monitoring stack; an alert-governance initiative; bilingual technical writing; one line-by-line audit that reversed a leadership decision on open-source scope. All real, all local. 52 says exactly that: the record contains persuasion and teaching, but no initiative I originated that crossed team boundaries with committed resources.

**Security & Compliance — 40/65.** The real work is agent-side: deny-by-default sealed tools, write attestation, blast-radius-tiered execution gates. The traditional face — IAM design, audit frameworks of the SOC 2 class — is essentially absent from the record. 40 is a statement of fact, not modesty.

## A behavioral cross-check

The scores above were assigned top-down, from reviewing evidence. There is also a bottom-up signal produced independently: my on-call knowledge base, accumulated as a side effect of working incidents, not built for this site. It currently holds 21 documented investigations (more than 20 of them production P1/P2), 16 runbooks, 15 fast-triage cards, 7 debug trees, and 4 recurring root-cause patterns.

Tagging those entries by domain gives: incident 14, data 8, observability 6, infra 6, distributed systems 5, release 5, platform 2, security 0, influence 0.

Two honest notes on the denominator before reading anything into it. First, these are *documented* investigations — the counts measure documentation discipline as much as exposure. Second, "21 investigations" and "20+ P1/P2" overlap but are not the same series; investigations are the subset that got written down with evidence.

With those caveats, the cross-check holds. Incident leads by construction — it is an incident knowledge base. Among the subject-matter domains, data dominates at 8, matching data being the tallest radar axis; observability, infra, distributed systems, and release cluster in the middle, matching the mid-height axes; security and influence sit at zero, matching the two lowest axes. The radar shape and the triage record were produced by different processes, and they agree. If I had inflated any axis, this record is where the contradiction would show.

# CN

## 分数是怎么产生的

方法放在最前面，因为没有方法，数字就是噪音。雷达上每个 depth 分数都由证据密度推导：旗舰 artifact 的数量与深度（带证据引用的事故复盘、经受住重测的实测结果）、从工作中沉淀出的方法论体量（runbook、debug tree、固化的规则），以及是否存在公开可验证之物。它明确不是自评。

原因是：自评分数对读者没有信息量。自评在人与人之间没有校准，夸大的激励是结构性的，而且当你不同意时无处可查。一个由认证过的迁移支撑的 82 是可以审计的声明；一个由自信支撑的 82 只是一种心情。从证据推导分数还带来一个性质：它们可能以可检查的方式出错。这正是让它们值得发布的性质。

## 九个域，每域一段

**数据与状态：82/90。**旗舰证据：一次 ClickHouse 到 Doris 的迁移，约 52 亿行、约 3,700 列的表，在全量无采样数据集上认证 99.945% 行级完整，四类非直觉 OOM 和一次 livelock 的根因追到引擎层。另有一次全量恢复演练：52 亿行从快照恢复到独立卷并用查询验证。82 是最高的轴，因为证据钻得最深，深到引擎代码。不是 90，因为深度集中在一个引擎家族，且恢复演练是一次性的，尚未制度化。

**可观测性：80/85。**建设并运营一个多租户监控平台（50 集群、120 万活跃序列）；规模化的遥测取证，包括挖掘 7,470 万行生产 query log 并逆转了一个表设计决策；分段延迟归因证明了被怀疑的一层无罪。到 85 的差距不在工具，在 SLO 运营，见事件响应一节。

**分布式系统：78/88。**把存算分离当成一笔交易来论证（状态是被集中了，不是消失了），然后实际运营它；一套两层准入控制设计，其安全性从不依赖分类器判断正确；以及「点查瓶颈是打开文件数、不是扫描行数」这个发现。到 88 的距离是诚实的那种：我运营并推理 consensus 与复制层，但没有设计过一个。

**平台与自动化：76/85。**用 controller 替代脚本，并且这条标准反向也执行：平台 operator 成熟后，把自研 scaler 收缩成一次 JSON-patch。一套 AI agent triage harness 和一个 agent 控制面，加上升级自动化。差距在于：这些还没有一个作为产品被本团队之外的用户使用过。

**事件响应与可靠性：72/82。**作为 primary oncall 处置 20+ 生产 P1/P2，MTTR 约 30 分钟；两次 compaction 事故根因到引擎层；一次尾延迟调查最终追到一个伪装成物理规律的超时常量。72 度量的是响应能力。它刻意不包含的（因为记录里确实没有）是一个季度的 SLO 与 error budget 运营。这是到 82 的大部分距离。

**基础设施与容量：70/80。**一条四层 IaC 流水线（镜像烘焙、编排、配置、控制面引导）；作为 primary oncall 运维 50 集群、600+ 节点、6 个 region；容量决策来自实测，包括在花钱之前证明加节点无效。一条边界如实写明：我在 autoscaling group 和 launch template 层的深度是消费与修补，不是从零设计整个舰队。

**发布与变更：68/78。**生产 Kubernetes 从 1.24 升到 1.29，覆盖 50 集群零事故，自建自动化把单集群耗时从 18 至 21 小时压到 3 至 4 小时；一次 dry-run render-diff 拦下了 chart 升级把 serving 池从 4 副本静默重置为 1 的地雷。差距：服务级的渐进式交付作为日常实践，而不只是升级项目里的纪律。

**影响力与沟通：52/75。**监控栈的内部培训 deck 和引导式 onboarding；一项告警治理倡议；双语技术写作；一份逐行审计改变了 leadership 关于开源范围的决策。全部真实，全部局部。52 说的正是这个：记录里有说服和教学，但没有一个由我发起、跨越团队边界、带资源投入的项目。

**安全与合规：40/65。**真实的工作在 agent 一侧：默认拒绝的封装工具、写入 attestation、按爆炸半径分级的执行闸门。传统面（IAM 设计、SOC 2 类审计框架）在记录里基本缺席。40 是事实陈述，不是谦虚。

## 一次行为层面的交叉验证

上面的分数是自上而下、从证据评审中给出的。还存在一个独立产生的自下而上信号：我的 oncall 知识库。它是长期处置事故的副产品，不是为这个站点准备的。目前包含 21 篇 documented investigation（其中 20+ 为生产 P1/P2）、16 篇 runbook、15 张 fast-triage card、7 棵 debug tree、4 个反复出现的根因模式。

按域给这些条目打标签，得到：incident 14、data 8、obs 6、infra 6、dist 5、release 5、platform 2、security 0、influence 0。

在解读之前，先对分母做两点诚实说明。第一，这些是「写下来的」调查：计数衡量的既是暴露度，也是文档纪律，没写下来的工作在这里不可见。第二，「21 篇 investigation」和「20+ P1/P2」有重叠但不是同一个序列：investigation 是被带证据写下来的那个子集。

在这两条限定下，交叉验证是成立的。incident 领先是结构使然，它本来就是一个事故知识库。在主题域里，data 以 8 领跑，正好对应 data 是雷达最高的轴；obs、infra、dist、release 聚在中段，对应中等高度的轴；security 和 influence 是零，对应最低的两个轴。雷达形状和 triage 记录由不同过程在不同时间产生，而它们互相印证。如果我夸大了任何一个轴，矛盾会在这份记录里显形。

# SOURCES

- `adhoc_jobs/dynamic_resume_site/content_plan.md` — 九域 depth/target 分数表与旗舰 evidence
- `adhoc_jobs/dynamic_resume_site/research/mining_notes.md` — 诚实边界（ASG/launch template 消费与修补口径）、evidence 交叉验证结论
- `adhoc_jobs/dynamic_resume_site/content/case_study_ch_to_doris.md` — data/dist/obs 域旗舰证据原文
- oncall 知识库统计（2026-07 口径）：21 investigations / 16 runbooks / 15 fast-triage cards / 7 debug-trees / 4 root-cause patterns；域触达 incident 14 / data 8 / obs 6 / infra 6 / dist 5 / release 5 / platform 2 / security 0 / influence 0
