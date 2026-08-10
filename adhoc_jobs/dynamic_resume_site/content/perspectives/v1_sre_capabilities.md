# META

id: w-v-capabilities
kicker_en: PERSPECTIVE
kicker_cn: 视角
title_en: What I understand SRE to require
title_cn: 我所理解的 SRE 需要的能力
sub_en: Why the radar has nine axes — a capability model built on problem classes, not tool inventories, and where the moat actually is.
sub_cn: 雷达为什么是九个轴：一个按问题类别而不是工具清单构建的能力模型，以及护城河到底在哪里。
domains: []

# EN

## From tool inventories to problem classes

There are two ways to slice SRE skill. The first is by tools: Kubernetes, Terraform, Prometheus, a cloud provider. That is the entry-level view, and its weakness is immediate — `kubectl apply` is a commodity. The second slice is by problem classes: which categories of failure can I close, end to end, under time pressure. That is the view this site's radar is built on.

The test I use for mastery is specific: **when the abstraction leaks, can you drill down?** Deploying a service is entry level. Tracing a pod stuck in Pending through scheduling constraints, allocatable arithmetic, and node conditions — or tracing an OOM into a memory buffer the engine does not even track — is mastery. Every capability claim on this site should be read against that criterion, which is also why every claim links to an artifact: mastery asserted without a drill-down record is just confidence.

## Why these nine axes

The radar's nine domains are not a taxonomy I found; they are a derivation from what the job is — keeping a system delivering its contract.

**Four steady-state delivery domains** — Observability, Release & Change, Platform & Automation, Infra & Capacity — together constitute "operating a system": can you see it, change it without breaking it, automate what repeats, and size it for what is coming. These are the domains with the most mature industry practice, which makes them necessary but not differentiating.

**Distributed systems** is the intellectual core rather than an operating domain: understanding *why* systems break in the specific ways they do. Partial failure, overload as arrival rate exceeding service rate, retry amplification, cascading timeouts. Availability itself decomposes into P(no fault) + P(fault) × P(detected fast) × P(recovered or degraded fast) — and that one decomposition quietly justifies half the radar: detection is observability's term in the product, recovery is incident response's, and the often-forgotten middle factor is why monitoring can never be a nice-to-have.

**Incident response** is the time dimension of the whole loop. Everything the delivery domains prepare over weeks gets consumed in minutes, by one person, with incomplete information.

**Security** is the implicit second contract. Availability promises the system serves; security promises it is not breached. Different threat model, different failure model, and a failure that no rollback undoes — it earns its own axis even on a reliability-centric map.

**Data & state** is where irreversibility lives. Moving data fails completely differently from moving machines: a bad deploy rolls back, a lost byte does not, and load-time behavior can depend on the accumulated size of the table rather than the size of the batch. Applying stateless reflexes to stateful systems is, in my book, a named anti-pattern.

**Influence** is the hard gate above senior. Root-cause and prevention work is structurally under-visible, so the capability that unlocks organizational investment is translation: stating technical debt in the organization's own cost language, with evidence. Engineers who cannot do this cap out at personal excellence regardless of how tall their other axes are.

## Why incident response is the moat

Deployment, capacity planning, and toil automation all have mature patterns you can copy — reference architectures, vendor blueprints, other people's postmortems. What cannot be copied or outsourced is: the service is down at three in the morning, and the question is whether you can localize and recover within twenty minutes. That capability is a compound of every other axis executed under time pressure, which is exactly why it gets its own axis instead of dissolving into the others — the compound is the thing employers are actually buying.

## The SRE subset of database operations

Operating stateful engines looks like DBA work but has a clean boundary: **the DBA owns the engine's internals; the SRE owns the service that runs the engine.** "Why is this query slow" is DBA territory. "Why is this cluster down, and why won't it hold the load" is SRE territory.

The SRE side reduces to a five-part skeleton that is deliberately engine-agnostic: (1) deployment topology — what dies when a node dies; (2) failure modes and recovery — the core of the core; (3) the capacity and resource model — where the bottleneck is and what scaling costs; (4) backup with rehearsed restore — an unrehearsed backup is a hypothesis, not a backup; (5) observability — replication lag, queue depth, memory and disk watermarks wired to alerts. Master these five answers for one engine and the next engine is a checklist, not a career change.

There is one grey zone I deliberately claim for SRE: **query-level resource governance** — memory isolation, queueing, per-query limits. It looks like query tuning, but its purpose is stability (prevent one query from taking down the service), not optimization (make that query faster). Stability mechanisms belong to whoever owns the pager.

## Operating monitoring versus building monitoring

The last split corrects a common mislabeling of monitoring as optional infrastructure work. Building the monitoring platform — federation, ingestion pipelines, custom exporters — is a specialist item; it is fine to not master it. Operating monitoring — reading metrics under pressure, writing the query that localizes the fault, designing SLIs, SLOs, and alerts that page on symptoms — is core, full stop. An SRE who cannot read their own telemetry is blind at exactly the moment sight matters most.

One design conviction inside that core: keep four concepts separate — the SLI (what you measure), the histogram (how the distribution is recorded), the quantile (one view into it), and the SLO (the target over a window). I prefer SLI = requests-under-threshold / valid-requests; a bare "P99 ≤ X ms" is a useful observation lens, not the SLI itself.

This framework is what the radar's nine axes mean. The next two pages apply it: where the evidence says I actually stand, and what I know I cannot do yet.

# CN

## 从工具清单到问题类别

切分 SRE 技能有两种方式。第一种按工具切：Kubernetes、Terraform、Prometheus、某家云。这是入门视角，弱点一眼可见：`kubectl apply` 是大宗商品，谁都会。第二种按问题类别切：哪几类故障我能在时间压力下端到端搞定。本站的雷达就建立在第二种视角上。

我判断「精通」的标准很具体：**抽象泄漏时，你能不能往下钻？**会部署一个服务是入门。把一个卡在 Pending 的 pod 沿着调度约束、allocatable 的算术、节点状态一层层追下去，或者把一次 OOM 追进引擎根本不统计的内存缓冲区里，才是精通。本站上每一条能力声明都应该用这条判据来读。这也是每条声明都链接到 artifact 的原因：没有下钻记录支撑的「精通」只是自信。

## 为什么是这九个轴

雷达的九个域不是我从哪里抄来的分类法，而是从「这份工作是什么」推导出来的：让一个系统持续兑现它的契约。

**四个稳态交付域**（可观测性、发布与变更、平台与自动化、基础设施与容量）合起来构成「运维一个系统」：你能不能看见它、在不弄坏它的前提下改它、把重复的事自动化、并为将要到来的负载定容。这四个域的行业实践最成熟，所以它们是必要项，但不是区分项。

**分布式系统**不是运维域，而是智识内核：理解系统为什么会以这些具体的方式坏掉。Partial failure、到达率超过处理率意义上的过载、retry 放大、级联超时。可用性本身可以分解为 P(不出故障) + P(出故障) × P(快速检测) × P(快速恢复或有损降级)。这一个分解悄悄论证了半张雷达图：乘积里的「检测」对应可观测性这个轴，「恢复」对应事件响应这个轴，而中间那个最常被遗忘的因子，正是监控永远不可能是 nice-to-have 的原因。

**事件响应**是整个回路的时间维度。交付域用几周准备好的一切，会在几分钟内、由一个人、在信息不全的情况下被消耗掉。

**安全**是那条隐性的第二契约。可用性承诺系统在提供服务，安全承诺它没有被攻破。威胁模型不同，失败模型不同，而且这种失败没有任何回滚能撤销。即使在一张以可靠性为中心的地图上，它也配得上自己的轴。

**数据与状态**是不可逆性所在。搬数据的失败模式和搬机器完全不同：一次坏的发布可以回滚，一个丢掉的字节不能；导入时的内存行为可能取决于表的累计体积而不是批次大小。对有状态系统使用无状态式的条件反射，在我这里是一个有名字的反模式。

**影响力**是 senior 以上的硬门槛。根因分析和预防性工作在组织里天然低可见，所以真正撬动组织投入的能力是翻译：用组织自己的成本语言、带着证据，把技术债讲清楚。做不到这一点的工程师，无论其他轴多高，上限都是个人卓越。

## 为什么事故响应是护城河

部署、容量规划、消除 toil，这些都有成熟模式可抄：参考架构、厂商蓝图、别人的复盘。抄不来也外包不掉的是：凌晨三点服务挂了，你能不能在二十分钟内定位并恢复。这项能力是其他所有轴在时间压力下的化合物，这正是它单独成轴而不是溶解进其他域的原因：雇主真正购买的就是这个化合物。

## DB 运维的 SRE 子集

运维有状态引擎看起来像 DBA 的活，但边界很干净：**DBA 管引擎内部，SRE 管跑引擎的那个服务。**「这条查询为什么慢」是 DBA 的领地；「这个集群为什么挂、为什么撑不住」是 SRE 的领地。

SRE 这一侧可以归结为一套刻意与具体引擎无关的五件套：（1）部署拓扑，挂一个节点会死什么；（2）失败模式与恢复，核心中的核心；（3）容量与资源模型，瓶颈在哪、扩容的代价是什么；（4）备份与演练过的恢复，没演练过的备份只是一个假设，不是备份；（5）可观测性，复制延迟、队列深度、内存与磁盘水位全部接上告警。把这五个问题对一个引擎回答透，换下一个引擎就是过一遍 checklist，不是换一次职业。

有一个灰色地带我刻意划给 SRE：**查询级资源治理**（内存隔离、排队、单查询限制）。它看起来像查询调优，但它的目的（防止一条查询打爆整个服务）是稳定性，不是优化（让这条查询更快）。稳定性手段属于持有 pager 的那个人。

## 运营监控与建设监控

最后这个拆分纠正一个常见的错误标签：把监控当成可选的基础设施工作。建设监控平台（federation、采集管道、自研 exporter）是专家项，不精通没有问题。运营监控（压力下读 metrics、写出定位故障的那条查询、设计对症状告警的 SLI/SLO 和告警体系）是核心，没有余地。读不懂自己遥测数据的 SRE，恰好在最需要视力的时刻是盲的。

这个核心里有一条设计信念：把四个概念分开。SLI 是你衡量什么，histogram 是分布如何被记录，quantile 是看分布的一个视角，SLO 是时间窗口内对指标施加的目标。我偏好 SLI = 达标请求数 / 有效请求数；一句裸的「P99 ≤ X ms」是有用的观测视角，不是 SLI 本体。

这套框架就是雷达九个轴的含义。接下来两页是它的应用：证据表明我现在实际站在哪里，以及我知道自己还不会什么。

# SOURCES

- `work-harness/code_repos/infra/cre6630-infra/SRE-core-skill-map.md` — 视角转换、四能力、DB 划界五件套、监控拆分的原始骨架
- `context-infrastructure/rules/skills/bestpractice_sre_reliability_models.md` — availability 概率分解、lambda/mu 过载坐标系、SLI/SLO 四层分离
- `adhoc_jobs/dynamic_resume_site/content_plan.md` — 九域框架与雷达结构
