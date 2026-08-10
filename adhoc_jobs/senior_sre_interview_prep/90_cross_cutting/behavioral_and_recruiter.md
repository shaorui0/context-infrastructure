# 行为面与 recruiter 问答

技术面靠七个方向的材料撑。这份文件解决两件另外的事：senior 级别的行为面（他的九域雷达里影响力只有 52 分，是最弱的一环），以及 recruiter 轮的标准问答。

---

## 1. Senior 与 mid 的判据差异

行为面在考的不是「你做过什么」，而是四件事：影响范围超出自己的任务边界、在信息不足时做决策并承担结果、说服别人改变做法、以及主动发现问题而不是等着被派活。

他的技术素材很硬，但大部分是「我把一个系统建好了」。行为面需要的是另一类叙事。下面五个素材是他手上真实存在的影响力故事，`content_plan.md` 的雷达里影响力域列的就是这几项。

---

## 2. 影响力素材（五个，每个都能扛住追问）

### B01. 决定什么不该开源，并改变了 leadership 的决定

这是他最强的判断力故事，`interview_story.md` 把它列为 P8 王牌之一。他在 Doris fork 里做的引擎工作，最后的结论是 mechanism 走上游、policy 留内部，并且这个结论改变了 leadership 原本的决定。

行为面价值：技术判断转化成组织决策，而且是向上影响。追问会落在「你怎么说服的」和「如果他们不同意你怎么办」，答案要落在论证结构上（哪部分是通用机制、哪部分是业务耦合，逐行列出 7 个业务耦合点），而不是落在沟通技巧上。

⚠️ 边界：开源措辞用 fork 口径，patch 未进 upstream，别说 contributed to Apache Doris。

### B02. 用数据推翻团队的设计假设

query_log 取证做出负载画像，发现点查占绝对多数（口径：well over 90%），这个结论推翻了团队原有的假设，成为架构选型的依据（`interview_story.md` 的 3 分钟版排序里把它作为「用数据改变设计」的 beat）。

行为面价值：不接受未经验证的共识，先取证再论证。这是 senior 最核心的行为特征。

### B03. 提出并推动告警治理

FY2026 self-assessment 里他把告警噪音写成自己最不满的一点，并主动提出季度 alert review 机制的建议：owner 归属、严重度阈值、覆盖缺口（`contexts/fy2026_self_assessment.md` Q2/Q4）。`p_alert_gov.md` 是配套的熵增分析。

行为面价值：从自己的痛点出发提出制度性改进，而不是忍着或者只修自己那一块。

⚠️ 边界：这是倡议与目标口径，**不要说成已建成的机制**。诚实答法：我做了熵增分析、定了门禁目标，制度落地是我在推的事。

### B04. 跨团队定契约

ROUTE PLAN 分类器的输出契约与 fallback 行为是他定的，Arrow Flight 传输由伙伴团队实现（`contexts/resume_highlights_doris_dcluster.md` §0）。

行为面价值：这正好是「归属边界」变成加分项的例子。主动说清哪部分是自己做的、哪部分是定契约让别人做的，展示的是协作的成熟度。面试官对能划清边界的候选人信任度更高。

### B05. 发现并上报安全风险

他在工作 repo 里发现 jenkins.yaml 有明文 AWS AccessKey/SecretKey 且已进 git 历史，判断需要轮换密钥、清理 git 历史、排查是否活跃。

行为面价值：不在自己任务范围内的问题也上报，这是 ownership 的直接证据。也是讲最小权限与密钥管理的自然入口。

⚠️ 这件事涉及公司内部安全问题，面试里讲的时候抽象成「我在一次代码审查中发现凭证硬编码进了版本历史」，不要点名 repo 与具体 key 前缀。

### 另外两条可用的辅助素材

内部培训 deck 与双语技术写作（`contexts/presentations/`、他的博客）：证明知识外化能力。做辅助不做主线，因为面试官更关心组织内影响。

---

## 3. 高频行为面题与素材路由

| 题 | 挂哪个素材 | 一句定位 |
|---|---|---|
| 讲一次你影响了别人的技术决定 | B01 | 我把一个开源范围问题拆成机制与策略两层，结论改变了 leadership 的决定 |
| 讲一次你和团队意见不一致 | B02 | 我不反驳假设，我去取证，然后让数据说话 |
| 讲一次你主动发现并解决了没人让你管的问题 | B05 或 B03 | 两个都可以，B05 更硬 |
| 讲一次你推动了流程改进 | B03 | 从我自己的 oncall 痛点出发，提了季度告警审查机制 |
| 讲一次失败 / 你算错的事 | 见下 | 必须准备，见 §4 |
| 怎么和别的团队协作 | B04 | 我的做法是先把契约定清楚，边界明确了协作才快 |
| 怎么处理紧急事故的压力 | 01/02 的 oncall 故事 | 20+ P1/P2，MTTR ~30min，讲流程不讲英雄主义 |
| 怎么带新人 / 知识传递 | 培训 deck + runbook + harness | 我倾向把知识写成可执行的东西而不是口头传授 |

---

## 4. 「讲一次你算错了」的三个备选

这道题几乎必问，而且是区分 senior 的关键题。他有三个真实的、已经公开撤回过的错误（`interview_story.md` 追问弹药路由）：

**benchmark 撤回**：他做过一次 benchmark，后来发现方法有问题，公开撤回了结论。这是最好的一个，因为它展示的是对自己数据的诚实。

**sizing 算错 5GB → 610MB**：容量估算错了一个量级，后来自己发现并修正。

**NoSuchKey 自埋雷**：自己埋的坑自己踩了，公开撤回。

用法：选 benchmark 那个当主答案，因为「主动撤回自己已经发出去的结论」比「算错了后来修正」更能证明工程诚实。答案结构落在：我怎么发现的、我怎么处理的（公开撤回而不是悄悄改）、之后我改了什么方法。

⚠️ `interview_story.md` 明确写了：不要主动打开 benchmark 诚实性这个话题。被问「你的数字可信吗」或者「讲一次你算错的」时才拿出来，那时它是满分答案。

---

## 5. Recruiter 轮标准问答

数字已按 `number_baseline.md` 修正。原始版本在 `work-contexts/career/interview/intro.md`，那份的数字是 3 月的，已过时。

**团队规模与职责**
> Our SRE team is 4 people and we own the infrastructure layer for the entire company: AWS across 6 regions, 50 production Kubernetes clusters, 600-plus nodes, multi-tenant SaaS. We cover cluster lifecycle, observability, traffic management, and incident response.
>
> My own scope is three areas. First, Kubernetes cluster lifecycle: I built the upgrade automation across 50 clusters covering control plane, workers, and addons, taking a single cluster from 18-21 hours with a two-person pair down to 6-8 hours with one operator and the system, with zero incidents. Second, the observability platform: I led the migration from federated Prometheus to VictoriaMetrics and designed the 3-tier alerting with per-tenant SLI recording rules. Weekly OOMs went to zero and data lag went from 45 seconds to under 5. Third, the analytics data platform: I restructured our event layer onto disaggregated storage and compute, implemented query routing inside the engine so heavy queries are classified before execution, and built the control plane that brings a compute pool up from zero and reaps it back to zero when idle.
>
> The other three members carry the day-to-day on-call rotation, runbook maintenance, and tenant onboarding. I focus on the layer above that: building the systems that stop L1 and L2 problems from happening.

**为什么想离开**
> Three reasons. First, I'd prefer a permanent role; my current position is on a contract basis through an internal transfer. Second, I'm looking for broader scope: our Japan office is small and the company's center of gravity is North America, which caps what I can own here. Third, I want to be in a stronger engineering culture where infrastructure decisions get made locally.

避免的说法：抱怨公司、抱怨同事、说现在的工作没意思。scope 是中性且真实的理由。

**薪资期望**
> I'm currently at around [⚠️ 面试前定一个数：intro.md 正文写 9M、注释写 10M，必须统一] million yen. For the right role I'm flexible, since I care more about the scope of the position than optimizing a number. If you need a range, I'd say 10 million yen or above, and I'd expect it to reflect the level of responsibility.

**合同形式能否接受**
> I prefer a permanent role. I'm flexible if the scope is right, but permanent employment is one of the reasons I'm looking.

**签证与语言**
> Highly Skilled Professional visa, 5-year validity. I don't hold a JLPT certificate; I work entirely in English.

如果对方在意日语：可以说在学（他确实在做 N2 备考），但不要承诺工作语言能力。

**notice period**
> The internal transfer process takes about a month. Once I have an offer I can resign promptly and be ready to onboard within three weeks to a month.

**为什么在日本 / 长期计划**
> I came for the technology ecosystem and international experience, and what I found valuable was the depth: infrastructure work here takes reliability seriously, which matches how I think. I've been able to go deep on complex problems instead of context-switching constantly. I hold an HSP visa, Japan is my base, and I plan to stay long term. What I'm looking for now is a bigger scale or a stronger engineering culture to apply what I've built.

**硕士为什么三年**
> Three years is the standard program length in Chinese universities.

---

## 6. 小 talk 与收尾

`intro.md` §small talk 那部分可以直接用，不需要改。收尾统一用：Anyway, shall we get started? 或者反向提问（见 `positioning.md` §5）。
