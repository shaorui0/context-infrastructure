# 定位与自我介绍（面试的第一层）

面试的前 60 秒决定后面所有内容被放进哪个框。素材硬度已经够了，问题从来在排序和封装（`research/interview_story.md` 的核心诊断）。这份文件定的是全局那一层框，Doris 项目自己的开场骨架在 `opening_story.md`。

---

## 1. 目标身份

他自己已经写过一版目标身份，不用另起（`work-contexts/career/interview/gig_who_are_you.md`）：

> 可对外承担生产系统结果的 AWS 分布式架构者

能力优先级也是他自己排的：系统设计 > 可靠性建模 > 成本建模 > 自动化与可观测。这个排序值得保留，因为它把自动化和工具深度放在了最后，避免面试时滑进「我会用什么工具」的执行者框架。

七个准备方向服务于这个身份的方式：

| 方向 | 在目标身份里的角色 |
|---|---|
| 01 Doris / DB / 存算分离 | 系统设计的主场：读写路径、状态放哪、瓶颈在哪 |
| 02 监控 / SLO | 可靠性建模的度量层：把用户影响翻译成可管理的信号 |
| 03 AIOps | 前瞻性与工程品味：他怎么想下一代 ops 的控制结构 |
| 04 IaC / CI-CD / K8s | 交付与变更的确定性，自动化在这里是手段不是卖点 |
| 05 Blue/green 与数据切换 | 高风险变更的设计方法论，最能体现取舍能力 |
| 06 成本 / FinOps | 成本建模，他的架构级降本正好是这条轴的高阶形态 |
| 07 AWS fundamentals | L1 基础层，守住不被问穿的底线 |

---

## 2. 差异化论证（为什么不是又一个 SRE 候选人）

三条支柱，每条都有 evidence 撑，面试里挑两条讲就够。

**第一条：我向下动过引擎，向上建过控制面，而且让两端咬合。** 多数 SRE 停在运维数据库这一层：调参、扩容、处理故障。他在 Doris fork 里实现了 `EXPLAIN ESTIMATE PLAN` 和 `EXPLAIN ROUTE PLAN` 两个 SQL 语句，把查询路由做进了引擎；同时在 dcluster 里写了弹性 CN 控制面的幂等扩缩语义。最值得讲的是咬合点：FE 分类器的 capacity-relative 阈值随弹性池子大小变化，同一条查询在 8 核小池判 heavy、在 84 核大池判 light。这说明路由策略与弹性容量是协同设计的，而不是两个独立系统碰巧接在一起。讲清这个闭环，身份就从实现者升到系统设计者。

**第二条：SDE 与 SRE 双背景，事故能从用户影响一路走到代码。** 这条 intro.md 里已经在讲，是真的：Intel 时期写 Go 微服务与 K8s operator，Tencent 时期写 gRPC 服务，现在能改 Doris 引擎。所以定位不是「运维会写脚本」，而是遇到事故不需要跨团队交接就能下钻到代码层根因。

**第三条：我把可靠性工程的方法论迁移到了 AI agent 上。** 这条是市场稀缺度最高的。他建的 oncall triage harness 有 phase gate、mutation approval gate、证据律、iron law，本质是把 SRE 的变更控制思路用在了 LLM 上。面试如果对方是 AI 相关公司，这条提到第一位。

---

## 3. 自我介绍脚本（数字已按事实基线卡修正）

⚠️ `intro.md` 的现有脚本有过时数字（30+ clusters、40 tenants、3 years as SRE），**不要直接背那份**。用下面这版。

### 15 秒电梯版

I'm Rui, a Senior SRE at DataVisor Japan. I own the infrastructure layer for a multi-region AWS and Kubernetes platform: 6 regions, 50 production clusters, 600-plus nodes, with a 4-person SRE team. My focus is the parts of reliability that need design rather than operations.

### 60 秒标准版

I'm Rui, a Senior SRE at DataVisor Japan, working on large-scale AWS and Kubernetes production systems. To give you the scale: 6 AWS regions, 50 production Kubernetes clusters, 600-plus nodes, multi-tenant SaaS. Our SRE team is 4 people and we own the infrastructure layer for the whole company.

What makes my profile different is that I work at both ends of the stack. On one end I build platform control planes: cluster upgrade automation across 50 clusters, an observability platform migration, and an elastic compute control plane that scales a query pool from zero. On the other end I go into the engine itself: for our analytics layer I implemented query routing inside a Doris fork, so the engine classifies a query as heavy or light before execution and the compute pool comes up on demand.

That combination comes from a dual background in backend engineering and SRE. When an incident happens I can go end to end, from user impact down to code-level root cause, without waiting on a cross-team handoff.

Happy to go deep on any of these.

### 3 分钟版的骨架

前 60 秒用标准版。然后按对方的岗位侧重选一条主线展开：

- 岗位偏数据基础设施 → 走 01 方向，用 `opening_story.md` 的 Doris 开场
- 岗位偏平台 / K8s / 交付 → 走 04 方向，K8s 跨 50 集群升级做主线，落在「自动化的目标是可控可审计可回滚，不是省时间」
- 岗位偏可观测性 / SLO → 走 02 方向，Prometheus Federation 到 VictoriaMetrics 的架构决策做主线，落在从资源指标到 SLO 的认知转变
- 岗位偏 AI / 平台工程前瞻 → 走 03 方向，harness 设计做主线

收尾统一落在能力主轴而不是工具清单：我关心的是让生产系统可预测、可控制，自动化是手段。

### 工具栈问答（被问 tech stack 时）

Python 与 Go 为主。云上是 AWS 加 Kubernetes 与 Docker。可观测性是我从零建的：Prometheus、VictoriaMetrics、Grafana、Alertmanager、Loki，含 SLO 导向的告警。IaC 用 Ansible 做 provisioning 与配置管理、Packer 做镜像、kubeadm 自建集群。CI/CD 用 Jenkins。数据层有 MySQL、Redis、ClickHouse、Kafka、Doris 的生产经验。

⚠️ 这段里**不要主动提 Terraform**。被问到按 `04_iac_cicd_k8s/terraform_honest_answer.md` 的答法走。

---

## 4. 弱点的主动框定

弱点被动暴露是扣分，主动框定是加分。三个已知弱项的框定方式：

**Terraform 没有生产经验。** 框定为技术选型的历史结果而不是能力缺口：他们的栈是 Packer 加 Ansible 加 kubeadm，这个组合在自建控制面的场景下成立。然后立刻转向「如果引入我会怎么做」，把话题从记忆题变成判断题。详见 04 目录。

**SLO 的制度化落地偏浅。** 指标层和告警层他建得很实（per-tenant SLI recording rules、三层告警），但 error budget policy、多窗口燃烧率、SLO review 会议机制这套制度他没跑起来。框定为「我建了度量基础，制度层是我下一步要推的，我知道它长什么样」，并能讲出多窗口燃烧率的设计。详见 02 目录。

**AI harness 是个人工程，不是团队平台。** 不要吹推广度和 MTTR 改善。框定为「我先用自己的 oncall 当实验场，把控制结构验证清楚」，然后讲 phase gate 和 approval gate 的设计理由。详见 03 目录。

**日本办公室 scope 有限。** 这是他的离职动因，也是面试官会探的点。框定为对更大 scope 的主动追求，避免说成对现公司的抱怨。

---

## 5. 反向提问（准备 3 个，问出层次）

`intro.md` 已有三个，够用但偏常规。建议换成能体现 senior 视角的：

1. 团队现在最大的技术债是什么，你们希望这个岗位在头 6 个月里动它哪一块
2. oncall 的轮值结构是怎样的，告警质量目前是什么状态（这个问题本身就在展示他关心什么）
3. 基础设施的变更决策是怎么做的：谁能拍板引入一个新组件，怎么退役旧的

第 2 个问题如果对方吐槽告警噪音，直接接他的告警治理故事，是天然的话题咬合。
