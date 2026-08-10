# Senior SRE 面试备考体系

七个方向各自画出核心圈，把散在三处的素材整编成可直接用于面试的体系。共 40 个文件、约 10,700 行，61 个战 story（每个带 5 层追问防线）、174 道面试题（每题带答题骨架）。

建于 2026-07-29，2026-08-02 移除自动切流系统（非本人项目）。执行计划与盘点见 `PLAN.md`。

---

## 先做这两件事

**一、`90_cross_cutting/ownership_audit.md` 填 B 组八条裁决。** 2026-08-02 确认自动切流系统不是本人项目之后建的。此前所有归属判断主要依据简历与 `intro.md` 的自述，而那两份自述本身可能不准。简历 bullet 要重做，bullet 只能装真正属于自己的东西，所以归属先于一切。判断标准只有一条：被追到第三层实现细节时能不能答。

**二、`90_cross_cutting/number_baseline.md` 是唯一数字口径源，面试前必读。** 里面有五件必须本人处理的事，其中两处直接印在简历上。见下面的 §3。

---

## 1. 怎么用

**T-7 天**：读七个方向的 `README.md`（每份约 100 到 160 行），确认三环划分和你自己的判断一致。不一致的地方改材料，因为面试时你会按自己的判断说话，材料要跟着你走。

**T-3 天**：按目标岗位选主线（`90_cross_cutting/opening_story.md` 有选主线的判据表），背该方向的 `story_bank.md`。重点不是背故事本身，是背 L3 到 L5 那三层，因为 L1/L2 你本来就答得出。

**T-1 天**：过 `questions.md` 的答题骨架，跑一套 `90_cross_cutting/mock_interview.md`。弱方向读 `fundamentals.md`。

**T-1 小时**：只读两份，`number_baseline.md` 的自检清单和主线方向的三个 headline。

---

## 2. 七方向核心圈总图

| 方向 | 一句话定位 | 内核 | 中环 | 外环 | story |
|---|---|---|---|---|---|
| [01 Doris / DB / 存算分离](01_doris_db_operations/) | 向下改过引擎、向上建过控制面，并让两端咬合 | 8 | 9 | 6 | 15 |
| [02 监控 / SLO](02_monitoring_slo/) | 建了度量基础设施，SLO 的制度层是明确的下一步 | 8 | 7 | 7 | 10 |
| [03 AIOps](03_aiops/) | 判断力交给模型，红线交给 `exit 2` | 18 | 8 | 7 | 13 |
| [04 IaC / CI-CD / K8s](04_iac_cicd_k8s/) | 自动化的目标是可控可审计可回滚，不是省时间 | 9 | 8 | 8 | 11 |
| [05 蓝绿与数据切换](05_blue_green_data/) | 差异化在有状态与数据层的切换，不是无状态 canary | 6 | 5 | 7 | 4 |
| [06 成本 / FinOps](06_aws_cost_finops/) | 做的是架构级降本（让成本随负载归零），运营级 FinOps 是补课项 | 9 | 13 | 15 | 8 |
| [07 AWS fundamentals](07_aws_fundamentals/) | 通过 50 集群运维反向学 AWS，深度在与 K8s 的接缝处 | 5 | 5 | 6 | 卷 |

内核合计 63 条、中环 55 条、外环 56 条。外环占比接近三分之一是刻意的：这份材料的价值一半在于知道哪里不能装懂。

**三个方向可以当主力打**（01 / 02 / 03），02 和 04 的规模数字最直观，03 的市场稀缺度最高，06 和 07 是补课后能守住不失分的方向。

### 每个方向都有的四件套

`README.md` 三环图与最强 headline · `story_bank.md` 战 story 加 5 层追问防线 · `fundamentals.md` 从真实场景出发的基础回顾 · `questions.md` 高频题答题骨架。

两个方向有额外交付物：`04/terraform_honest_answer.md`（零生产经验但要答得比有经验的人更亮眼）、`05/methodology.md`（12 环节切换骨架 E01-E12 加 20 条失败模式 F01-F20，可以在白板上画出来）。07 的基础卷按 compute / storage / network / IAM 拆成四份。

---

## 3. 🔴 必须你本人处理的五件事

整编的副产品是发现材料之间互相矛盾。下面按紧急度排，前两条涉及简历，**投出去之前必须解决**。

| # | 问题 | 为什么紧急 | 详见 |
|---|---|---|---|
| 1 | `resume-expand.tex:86-90` 的 Cost Optimization 小节，`Reserved baseline` / `storage lifecycle policies` / `reducing cross-AZ data transfer` 三条在全库零支撑，`optimizing log retention` 只有间接支撑（动机是 cardinality 与 OOM，不是降本） | 面试官问一句「你们 RI 覆盖率多少」，失分位置是诚信不是能力。要么补事实，要么改措辞 | `number_baseline.md` §2.7（含改写建议） |
| 2 | K8s 升级耗时。简历写 `18-21h → 3-4h`，7 月材料明确 **6-8h 是已达成、3-4h 是三项未实施自动化的目标** | 追问「那 3-4 小时里还剩哪几步要人」必然答不上。正确口径反而更强：按人时算是 36-42 人时降到 6-8 人时，约 5 倍 | `number_baseline.md` §2.8 |
| 3 | VictoriaMetrics 拓扑与规模。简历与 7 月材料写 cluster 模式加 ~1.2M series，4/2 的实测运维复盘写 **single 模式单 Pod 加 ~793k series**，6/26 报告里 datasource 名仍是 `single-server` | single 与 cluster 的运维差异资深面试官一问就知道。核实前的安全说法已备好 | `number_baseline.md` §2.5 |
| 4 | 口头稿 `intro.md` 仍在用 30+ clusters / 40 tenants / more than 3 years as a SRE，与简历的 50 clusters 冲突；另外薪资口径正文写 9M、注释写 10M | 口头说 30、简历写 50 会被当场抓住 | `number_baseline.md` §3、§4 |
| 5 | 「最接近出事的一次」K8s 升级没有素材。`p_k8s_upgrade.md:160` 自己记录了这一点 | 零事故越强调，这道题被问的概率越高。而且「零事故」最大一份归因来自升级时集群 dark 这个架构条件，主动交代是加分、被问出来是减分 | `04_iac_cicd_k8s/story_bank.md` |

另有约 65 条 `⚠️ 待确认` 分散在各方向（06 最多，22 条，因为 FY2026 那条「Cloud cost optimization」在全库找不到任何具体动作、金额或时点）。这些不影响开口，但填掉能让追问防线从「方法正确」升级到「结果可验」。

### 两处已知的旧口径需要同步回站点

Doris 引擎补丁体量实测是 15 files / +1,310（旧口径 7 files / +589），golden corpus 197 条（旧 189），路由规则 15 条（旧 13）。`p_agentops.md` 的知识库数字写 130+ 文件，实测 108。dynamic_resume_site 是对外产物，改不改由你定。

### 一条新的安全发现

除了已知的 `jenkins-config/jenkins.yaml`，`cilium values.yaml.j2` 里也有明文 AWS key。两处都需要轮换密钥、清理 git 历史、排查是否活跃。

---

## 4. 目录

```
senior_sre_interview_prep/
├── README.md                    本文件
├── PLAN.md                      执行计划与素材盘点（含 Phase 0 修订日志）
├── 01_doris_db_operations/      README · story_bank · fundamentals · questions
├── 02_monitoring_slo/           同上
├── 03_aiops/                    同上
├── 04_iac_cicd_k8s/             同上 + terraform_honest_answer.md
├── 05_blue_green_data/          同上 + methodology.md
├── 06_aws_cost_finops/          README · story_bank · finops_fundamentals · questions
├── 07_aws_fundamentals/         README · questions + fundamentals_{compute,storage,network,iam}.md
└── 90_cross_cutting/
    ├── ownership_audit.md       🔴 归属裁决表，重做 bullet 之前先填 B 组
    ├── number_baseline.md       🔴 唯一数字口径源，面试前必读
    ├── positioning.md           目标身份、三条差异化论证、自我介绍脚本
    ├── opening_story.md         四条主线的开场逐字稿与选主线判据
    ├── behavioral_and_recruiter.md  五个影响力故事、行为面题库、recruiter 问答
    ├── story_matrix.md          23 个故事 × 7 方向的复用矩阵
    └── mock_interview.md        三套混合 mock
```

---

## 5. 纪律

**这是私人备考材料，不脱敏**（客户名、CRE-6630、内部集群名可以出现，方便记忆），但**永不进任何公开产物**。往 `dynamic_resume_site` 搬内容要走 `content_plan.md` 的脱敏规则。

**归属诚实比脱敏更硬。** dcluster 平台可靠性那批（spot 中断回退、容量准入、多集群锁）作者是 junhan.ouyang / Runzi Yang；Arrow Flight 与 FE memory-kill backstop 是伙伴团队；Intel BKC 按 `p_bkc.md` 的 SOURCES 分栏。完整边界在 `number_baseline.md` §5，每个方向的 story 里也逐条标了。

**三环划分宁可把内核画小。** 中环的每一条都配了「被追问时的标准口径」，那些口径的写法统一是先给事实、再给我为什么这样选、最后给我知道差在哪。不吹也不自贬，这个结构本身就是 senior 信号。

**每个数字能指到 evidence。** 全库 922 条 `(src: 路径)` 引用已机器验证可解析。找不到出处的一律标成 `⚠️ 待确认`，没有静默保留。
