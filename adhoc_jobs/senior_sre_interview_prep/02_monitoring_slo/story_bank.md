# 方向 02 战 story 库：监控体系 / 可观测性 / SLO

> 每个故事的数字都带 `(src: 路径)`。归属边界一栏是防止被追问穿的护栏。
> 5 层追问防线的设计意图：L1 是开场问，L2/L3 往细节钻，L4 问设计权衡（为什么不选别的），L5 是最深的一层（你算错过什么 / 边界在哪 / 重做怎么做）。
> 数字口径统一：集群数 50，~1.2M active series，~80K samples/sec，lag 45s→<5s。

**故事索引**

| ID | 故事名 | 主打能力 | 强度 |
|---|---|---|---|
| S01 | Prometheus Federation → VictoriaMetrics 平台重建 | 架构判断 + 迁移工程 | ★★★★★ |
| S02 | 三层告警 + per-tenant SLI recording rules | 信号设计 + 多租户隔离 | ★★★★★ |
| S03 | 告警治理倡议：熵增分析与准入控制 | 系统性思维 + 影响力 | ★★★★★ |
| S04 | galileo latency 三段分解：是 FP 不是网络 | 排障方法论 | ★★★★☆ |
| S05 | nginx waiting P100 = 精确 1.00s 的 memcached 根因 | 深度 RCA | ★★★★☆ |
| S06 | Loki 多租户日志侧与 LogQL 实战踩坑 | 日志工程 + 自我纠错 | ★★★☆☆ |
| S07 | 用 `system.query_log` 做负载画像取证 | telemetry 驱动决策 | ★★★★☆ |
| S08 | 从标 CPU 到设计 SLO：监控观的重建 | 成长叙事 / senior 分界 | ★★★★★ |
| S09 | 先证伪再解释：histogram skew 造成的假 P99 告警 | disproof 设计 | ★★★★☆ |
| S10 | CPU 92% 的多信号归因：查询是真凶，merge 只是在场证明 | 指标归因纪律 | ★★★☆☆ |
| S11 | Dashboard 五层故障定位路径与 Saturation 选型规则 | 设计哲学 + 前瞻视角 | ★★★★☆ |

---

## S01. Prometheus Federation → VictoriaMetrics 平台重建

**Headline（一句话，先给结论）**：Federation 的 45 秒延迟和每周 OOM 是架构属性不是配置属性，所以我没有去调参，我把 50 个集群的监控换成了推送式中心架构，1.2M active series、约 80K samples/sec，数据延迟降到 5 秒以内，切换全程没丢一条告警。

**适用题型**：讲一个你主导的架构决策 / 讲一次高风险迁移 / 你怎么做技术选型 / 大规模系统的可观测性怎么设计 / 你怎么在不停服的前提下换掉一个核心组件。

**情境**：Federation 拓扑顶端的 global Prometheus 每周 OOM 两到三次，head block 维护 1.2M series 占 5 到 10 GB 内存，每次崩溃重启在数据上留下空洞，而空洞会以「不存在的故障」的形式把 oncall 从床上叫醒 (src: `adhoc_jobs/dynamic_resume_site/content/projects/p_vm_platform.md`, `work-contexts/career/interview/interview-3-monitoring_reference.md:46`)。延迟这一半是结构性的：Federation 叠了两层 scrape 周期，集群本地 15s 加全局层 30s，全局视图最多滞后现实 45 秒，P0 时被 page 的人看到的是过去 (src: `interview-3-monitoring_reference.md:47`)。规模让两个问题都无解：50 集群的负载下 `/federate` 接口频繁 scrape timeout，Grafana 上出现数据断点；每个集群各自维护一套 federation rules，新集群接入要手工改 global Prometheus 的 scrape 配置 (src: `interview-3-monitoring_reference.md:48-49`)。同时平台没有可用的多租户维度，指标跨租户聚合，单租户的局部故障被平均值掩盖 (src: `p_vm_platform.md` Why 节)。

**动作**：我在 3 到 4 人的 SRE 团队里 own 这个领域的设计、选型和落地。引擎选型上我做了 VictoriaMetrics 与 Thanos 的 POC 对比，维度是写入吞吐、压缩率、运维复杂度，结论由团队共识确认 (src: `interview-3-monitoring_architecture.md:226`)。替代方案是推送式中心架构：每集群一个 vmagent 就地采集，relabel 阶段注入 `cluster` 与 cluster group 标签，remote_write 到中心 VM（vminsert ×2 挂 LB，vmstorage ×3 副本因子 2，vmselect ×2），vmalert 在同一存储上评估 recording 与 alert rules，Alertmanager HA 双实例做路由，Grafana 加 Loki 构成读取与验证面 (src: `p_vm_platform.md` How 节， `interview-3-monitoring_architecture.md:55-57`)。容量按实测输入设计：50 集群 × 约 12 节点 ≈ 600 节点，每节点约 2,000 series，合计约 1.2M active series、约 80,000 samples/s（15s 间隔）(src: `interview-3-monitoring.md:52`)。真正需要工程投入的不是快而是不丢：推送意味着网络抖动会丢数据，所以每个 vmagent 在本地磁盘跑 persistent queue，断连期间缓冲、恢复后回放 (src: `p_vm_platform.md` Hard parts)。切换门禁是两周双写窗口：每条告警规则在两套栈同时评估、diff 触发行为，dashboard 查询在 MetricsQL 下结果等价，才允许迁通知路由，门禁通过前 Federation 栈一直在线做 fallback (src: `p_vm_platform.md` Production 节， `interview-3-monitoring_reference.md:60`)。

**结果**：数据延迟最大 45s → <5s；OOM 每周 2-3 次 → 0；热存储 3 个月 ~930 GB → ~250 GB（约 4 倍压缩），冷存储走 S3、5 分钟降采样、180 天约 25 GB；新集群接入从「写 federation rules 加改全局 scrape 配置」收缩为「部署 vmagent，配一个 remote_write 地址」(src: `interview-3-monitoring_reference.md:53-58`, `interview-3-monitoring.md:53`)。简历口径：serving 50 clusters，~1.2M active series，~80K samples/sec (src: `work-contexts/career/profile/resume.tex:76-78`)。

**5 层追问防线**：

- **L1** 面试官问「为什么要迁？Prometheus 不是够用吗」→ 答：够用与不够用要分层看。单集群 Prometheus 完全够用，我们迁的是 Federation 这个**全局聚合层**。它有两个问题是配置改不动的：第一，global Prometheus 的 head block 要在内存里维护全局 1.2M series，占 5 到 10 GB，这是它每周 OOM 两三次的直接原因，加内存只是把 OOM 周期拉长；第二，Federation 是两层 pull 叠加，15s 加 30s，全局视图最多滞后 45 秒，这是拓扑决定的下界，任何调参都到不了 5 秒。我判断这是架构属性不是配置属性，所以没有花调参预算。

- **L2** 追问「45 秒延迟真的有那么严重吗？大部分告警窗口都是 5 分钟」→ 答：对告警触发的影响确实有限，5 分钟窗口容得下 45 秒。真正的代价在两个地方。一是 P0 期间的人：oncall 在做止血决策时看的是 45 秒前的数据，「我刚才那个操作起效了吗」这个问题要等一分钟才能回答，这直接拉长 MTTR。二是**数据空洞造成的假告警**，这个比延迟更贵：global Prometheus 崩溃重启留下的空洞会让基于 `absent()` 或者 rate 的规则误触发，oncall 被叫起来发现「不存在的故障」，这是 alert fatigue 的直接来源。所以我讲这个项目时把可靠性放在延迟前面。

- **L3** 追问「你怎么保证切换过程中不丢告警？双写具体怎么做的」→ 答：门禁是两周的双写窗口，具体三件事。第一，vmagent 的 remote_write 同时写新旧两侧，两套栈都有完整数据，Federation 栈保持在线作为 fallback。第二，每条 alert rule 在两侧同时评估，diff firing 行为。这一步是必须的，因为 VM 用 MetricsQL，和 PromQL 有边界差异，「规则照常触发」不能靠假设。我们把所有分歧修完才动通知路由。第三，dashboard 查询在 MetricsQL 下要返回等价结果。只有这三条都过，通知路由才迁移。另外平台本身必须响亮地失败：vmalert 持续输出心跳，deadman's switch 加一个 out-of-band 探针，把「监控失联」在分钟级变成一条明确的 page，而不是一个安静的盲区。

- **L4** 追问「为什么选 VictoriaMetrics 而不是 Thanos 或 Mimir？」→ 答：我做了 VM 与 Thanos 的 POC，维度是写入吞吐、压缩率、运维复杂度，最后是团队共识选了 VM。决定性的是第三条。Thanos 的模型是 sidecar 把 block 传到 object storage，全局查询靠 querier fan-out 到 store gateway，再加 compactor 做降采样和合并，组件多、故障面大，而它换来的核心好处是「无限廉价长期存储」。我们的实际需求是热数据 3 个月、冷数据 180 天降采样，这个体量 VM 的本地 SSD 加 S3 就覆盖了，Thanos 那套复杂度买不到对应的价值。而且我们是 3 到 4 人的团队，运维复杂度对我们不是次要维度，是主要维度。VM 的另外两个实际收益是压缩比约 4 倍（同一个 3 月窗口 930GB 降到 250GB）和 vmagent 这个专职采集器，它不带本地存储、自带 persistent queue，比 Prometheus 的 remote_write 重试机制稳。我要诚实的是，我没有在生产运维过 Thanos，所以我的对比是 POC 加架构分析，不是两边都跑过一年。

- **L5** 追问「重新做一次你会改什么？这套架构的下一个瓶颈在哪」→ 答：两件事我会改。第一，**cardinality budget 应该在第一天就存在**。我们是加了 tenant 维度之后才发现 series 增长很快，然后才补上四条治理手段（tenant 级 recording rules 只覆盖核心 SLI、基础设施指标不带 tenant label、retention 分层 90d/30d/15d、定期 cardinality 审查）。这是被增长曲线逼出来的，不是设计出来的。第二，**SLO 应该在搭采集之前定义**。我们先搭了采集再补 SLO，导致早期的告警阈值有一部分是经验值而不是有根据的目标值。至于下一个瓶颈，我判断有三个：Loki 在高流量下全量扫描慢，这是我们已经踩到的；高 cardinality 下 vmstorage 压力大；vmalert 规则多了之后评估周期跟不上，我们的缓解是把 tenant 级和全局 recording rules 拆到不同 rule group 分开评估。真正的架构性下一步是 cluster 模式的水平扩展和 vmselect 侧的查询缓存。

**归属边界**：设计、评估、落地是我 own 的（3-4 人团队里没有专职 observability engineer）。**引擎选型的最终决策是团队共识，不是我一个人拍的**，我做的是 POC 和推荐，这一点必须主动说明，因为说成「我决定用 VM」在追问下会露。应用侧的 `tenant` label 埋点是应用团队做的，我做的是推动收敛和写统一的 relabel 模板。⚠️ 见 README 待确认 A：**线上实际部署模式（cluster vs single）面试前必须核实**。

**可复用到**：04_iac_cicd_k8s（50 集群的配置分发与统一模板）、05_blue_green_data（双写窗口 + 等价性门禁 + fallback 是数据层 blue/green 的完整模式）、06_aws_cost_finops（930GB→250GB 的存储成本，S3 冷存分层）、90_cross_cutting（3-4 人团队里独立 own 一个领域，senior 的 ownership 叙事）。

---

## S02. 三层告警 + per-tenant SLI recording rules

**Headline**：我把告警从「资源阈值」重构成「服务影响优先」：先用 recording rules 把 SLI 族物化成 `{tenant, cluster_group}` 键控的预计算序列，再让 PAGER 这一层只接受可观测的用户影响，从而第一次让「哪个租户在受影响」成为可回答的问题。

**适用题型**：告警怎么设计 / 怎么减少告警噪声 / 多租户平台怎么做故障隔离 / SLI 怎么落地 / 你怎么定义什么该 page。

**情境**：原有告警是 resource-centric 的（CPU / 内存 / 磁盘抖动），触发后无法回答「用户有没有受影响」；告警响了还得手工拼日志、变更记录和依赖关系才能判断；aggregate 指标掩盖局部故障，单个租户的问题消失在平均值里 (src: `interview-3-monitoring.md:28-33`, `p_vm_platform.md` Why 节)。我在自评里把代价写得很直接：低信号 page 造成的 alert fatigue 恰恰在响应质量最重要的时刻拖慢 triage (src: `contexts/fy2026_self_assessment.md:25`)。

**动作**：分四步。第一步，**先物化 SLI 再谈告警**。recording rules 定义一族 SLI：QPS、error ratio、P95/P99 latency、saturation、per-tenant SLI，全部按 `{tenant, cluster_group}` 键控；dashboard 和 alert rules 都消费预计算结果，不在现场跑重查询 (src: `interview-3-monitoring.md:57`, `interview-3-monitoring_architecture.md:73-78`)。第二步，**label 一致性当平台基础设施做**。tenant 身份有两条注入路径：应用在自己的 metrics 上打 `tenant`（只有应用知道在处理谁的请求），vmagent 在 scrape 时 relabel 注入 `cluster` 与 `kubernetes_cluster_groups`。项目之前各集群 relabel 配置各自为政，cluster 命名不统一，部分团队用 `client` 而不是 `tenant`，这会悄无声息地破坏告警路由、drill-down 和 inhibition 的 label 相等匹配。我写了统一的 relabel 模板分发到所有集群，并推动应用侧收敛到 `tenant` (src: `interview-3-monitoring_architecture.md:122-282`, `p_vm_platform.md` How 节)。第三步，**三层分级加准入控制**。PAGER 走 pager 通道只留给确认的用户影响，HIGH 进 Slack，MEDIUM 归工单；PAGER 准入标准是三条之一：SLO burn rate 超标、SLA latency 击穿、关键链路 QPS 断崖；静态阈值全部换成 multi-window burn-rate，5m 和 30m 两个窗口同时超阈值才触发 (src: `interview-3-monitoring_reference.md:69-79`, `interview-3-monitoring_architecture.md:297-308`)。第四步，**inhibition 只做因果明确的抑制**，NodeNotReady 抑制同节点的 PodUnableToStart，跨服务的推测性抑制刻意排除，因为配错方向的 inhibition 会掩盖真实故障；在 staging 人工触发上游故障验证下游是否被正确抑制，并保留 firing 历史供 postmortem 回溯 (src: `interview-3-monitoring_reference.md:88`, `p_vm_platform.md` Production 节)。

**结果**：简历口径是「设计 3-tier alerting 配 per-tenant SLI recording rules，使租户级故障隔离与 per-tenant SLA 追踪成为可能」(src: `work-contexts/career/profile/resume.tex:79`)。落地的生产告警包括 Kafka tenant offset 停滞、MySQL replication down、Apisix per-client SLA drop (src: `interview-3-monitoring.md:16`)。上线后用两个反馈信号持续调参：每条 PAGER 的 action rate，以及用户报了问题但没有对应 page 的漏报 (src: `interview-3-monitoring_architecture.md:318-322`)。
⚠️ **这里不要说「告警量下降了 X%」**，那是 S03 的门禁目标，不是这个故事的实测结果。

**5 层追问防线**：

- **L1** 面试官问「三层怎么划线？什么算 PAGER」→ 答：PAGER 是用户可感知的错误或延迟，且需要立即人工介入，量极少，每一条都必须是真实用户问题。HIGH 是高风险但当下用户不一定受影响，比如 consumer lag、replica 数不足、replication down，进 Slack。MEDIUM 是趋势类和容量预警，归工单。判据的核心是一句话：**page 的准入条件是可观测的用户影响，不是资源压力**。具体三条之一：SLO burn rate 超标、SLA 定义的 latency 阈值被击穿、关键业务流程 QPS 断崖或归零。

- **L2** 追问「PAGER 这么少，漏报怎么办？你偏 precision 还是 recall」→ 答：这一层我明确偏 precision，理由是 PAGER fatigue 让 oncall 麻木比偶尔漏一个慢速退化更危险。但我不是靠「少发」来控制风险的，是靠三个结构：第一，PAGER 必须有 SLO 基准，不是凭感觉设阈值；第二，multi-window burn-rate，5m 和 30m 都异常才升级，这滤掉抖动但不放过持续恶化；第三，**HIGH 是前哨**，持续未恢复会升级到 PAGER。也就是说慢速退化走的是 HIGH 通道，不是完全没有覆盖。另外我用漏报作为显式的反馈信号：用户报了问题但没有对应 page，这条会被记下来去调阈值。

- **L3** 追问「per-tenant recording rules 会不会把 cardinality 打爆？」→ 答：会，而且我们踩到了，加了 tenant 维度之后 series 增长很快。四条控制：第一，**只对核心 SLI 做 tenant 级 recording rules**，不是所有指标都下钻到租户；第二，基础设施指标一律不带 tenant label（node、kubelet 这些天然不属于任何租户）；第三，retention 分层，tenant SLA 序列 90 天、排障序列 30 天、基础设施 15 天；第四，定期 cardinality 审查清理意外的高基数 label。我诚实的复盘是这四条是事后补的，cardinality budget 应该在第一天就存在。

- **L4** 追问「inhibition 为什么不做跨服务？服务 A 挂了明显会带崩 B，抑制掉不是更干净吗」→ 答：因为 inhibition 的失败模式不对称。做窄了的代价是降噪不够，多看几条告警；做宽了的代价是**掩盖一个独立故障**，而这是不可接受的。`NodeNotReady → 同节点 PodUnableToStart` 是因果明确的，节点没 Ready 那个节点上的 pod 起不来一定是这个原因。但「A down 抑制 B 的告警」不是因果明确的，B 完全可能同时有一个独立故障，被抑制掉就变成了盲区。所以我的原则是**只做因果关系明确的抑制**。降噪的另外两个手段承担规模问题：grouping（`group_by` cluster/service/alertname，`group_wait` 30 到 60 秒聚齐再发）解决 datacenter 级故障几百条告警的问题，以及检测到系统性故障模式时 PAGER 只发一条「全局事故」，症状类降级或静默。inhibition 解决因果派生噪声，grouping 解决规模噪声，两件事不要混。

- **L5** 追问「你怎么知道这套告警是有效的？拿什么衡量」→ 答：两个信号，而且都是我上线后才补的。第一是**每条 PAGER 的 action rate**：page 之后是否导致了有意义的操作（acknowledge → investigate → action），还是被 silence 掉了。这个指标本质上是把「告警质量」变成一个可回归测试的量。第二是**漏报追踪**：用户反馈了问题但没有对应 PAGER。这两个信号一个防噪声一个防盲区，缺任何一个都会跑偏。我要承认的边界是：这两个信号当时是人工统计的，没有做成自动化 dashboard；把它们变成常设测量是我在后来的告警治理方案里才提出来的（把 pager 本身变成 SLO 对象）。如果重做，我会在第一天就把 action rate 上 dashboard，因为不上 dashboard 的指标退化是不可见的。

**归属边界**：三层分级体系、inhibition 因果链设计、recording rules 的 SLI 物化策略是我从零构思的（`interview-3-monitoring_architecture.md:214-219` 列在 "I designed" 项下）。「从 resource-centric 转向 service-impact-first」是我 **proposed and drove**，团队采纳，不是我一个人执行的。应用侧 `tenant` label 埋点属于应用团队。⚠️ 口径漂移：不要把这个故事和 S03 的 baseline 数字混讲，见 README 漂移 1。

**可复用到**：01_doris_db_operations（DB 层告警的 symptom vs cause 分级）、03_aiops（告警准入控制的思路直接映射到 agent 的 policy gate）、90_cross_cutting（proposed and drove 是行为面「推动改变」的素材）。

---

## S03. 告警治理倡议：熵增分析与准入控制

**Headline**：我审计了一个每天产出约 960 条告警、约 85% 是默认 P3、背后有 367 条 paging 规则的 pager，定位了四个结构性根因，然后我认为这个项目真正的核心不是清掉了多少条规则，而是论证了「告警系统是一个不做功就必然熵增的系统」，所以解法必须是准入控制而不是大扫除。

**适用题型**：讲一个你发现并推动解决的问题（行为面高频）/ 你怎么处理 alert fatigue / 讲一次你的技术判断和别人不同 / 你怎么做系统性思考 / 你怎么在没有正式授权的情况下推动改变。

**情境**：baseline 是实测出来的。367 条 alert rule 打着进 pager 的路由 label，散落在 30 个规则文件里；全局 pager channel 每天吞下约 960 条告警，其中约 85% 是 P3，原因很简单，不写 priority 时 P3 就是默认值；仅 infra 团队的 channel 就以每小时约 12 条运行，一天约 290 条 (src: `adhoc_jobs/dynamic_resume_site/content/projects/p_alert_gov.md` Why 节)。细看比总量更糟：一条 `for: 0m` 的 OOM-kill 规则因为 18 个 pod 连锁 crash，三天产出 80 条告警，Top 3 规则在同一窗口合计 145 条 page；一条 ALB QPS 归零告警单次触发同时 fan-out 到 6 个 Slack channel，两分钟后又来一轮；一个 channel 在 6 分钟内收到 8 条告警；批处理调度器的超时告警对同一个卡住的 job 每小时 page 一次，三小时三条问题只有一个，而且超出平均 28% 的 job 和超出 300% 的 job 拿到同一个 P1，采样那天仅这一族就产出 10 条以上 P1，每条都 @ subteam 且没有一条带诊断链接；基础设施相关的告警 channel 有 12 个，其中 2 个早已无消息也没人察觉 (src: 同上)。我在年度自评里把最不满意的一项写成 alert fatigue，并把「季度告警评审、owner 分配、明确 severity 阈值」作为建议向上提出 (src: `contexts/fy2026_self_assessment.md:14, 25-27`)。

**动作**：治理的第一性原则先于一切动作确定，并且始终只有一句：**不能指导行为的 alert，关掉或降级**。方法是一棵决策树逐条过判定，每个结论都能追溯到一条采集的真实告警样本或一段规则定义，而不是感觉：能否指导行为，不能就关掉或去 @ 或降级到信息类 channel；能，就看偏离基线多少，低于 2 倍不告警，2 到 4 倍 P2 进 channel 不 @，高于 4 倍 P1 page 并 @ owner 且附 runbook (src: `p_alert_gov.md` How 节)。审计定位四个结构性根因：进 pager 的 label 是一行代码的免费开关没有任何准入门槛；Alertmanager 里多条 `continue: true` 的重叠路由把一条告警扇出到多个 receiver；所有 receiver 都没配 dedup alias，同一问题每次重新 firing 都生成一条新告警；还有一条旁路脚本直接向 pager 平台写入、priority 硬编码 P3，对所有路由和 inhibition 完全不可见 (src: 同上)。执行按阶段推进，测量先于改动：Phase 0 建 baseline dashboard；Phase 1 是 config 止血，打包成两个可 review 的 PR，带 promtool/amtool lint 预检、分步 apply 和回滚手册，内容是给最吵的规则加去抖窗口（`for: 0m` 改 10m）、加硬准入门槛只有 P1/P2 才允许进 pager、批处理告警按偏离倍数分级、所有 receiver 加 dedup alias 并开 `update_alerts` 使重复触发变成计数递增；Phase 2 拆分共享 api_key 为按团队独立 integration、合并冗余路由、补因果 inhibition、配 auto-close；Phase 3 把旁路脚本改道走 Alertmanager，每条规则强制携带 `team` ownership label (src: 同上)。

**结果（口径必须精确）**：**baseline 是实测值，下降数字全部是我设的分阶段验收门禁目标，不是已达成结果** (src: `p_alert_gov.md` 脱敏与省略说明：「素材只有 baseline 实测值与各 Phase 的目标/验收门禁，没有治理落地后的实测对比数据」)。门禁表：pager 日总量 960 先降到 400 以下再到 200 以下；Top 3 噪声源从 3 天 145 条降到 40 以下再到 15 以下；P3 占比从 85% 降到 50% 以下再到 30% 以下；oncall 从盯 12 个 channel 收敛到 3 个 (src: 同上)。同一轮治理还把部署审批这类 toil 下放了：两天 11 条 @ infra oncall 的审批请求全部来自 preprod，而系统里已存在的自动通过路径证明 infra 审批在这里不产生任何价值，于是委托给 team lead (src: 同上)。反熵机制三类已建立或明确：准入控制（pager 前的 P1/P2 门槛、每条规则强制 ownership label、规划中的 CI lint 拒绝不带 `runbook_url` 的 paging 规则）、常设测量（baseline dashboard 保留为长期 alert SLO dashboard，加自动化 weekly toil report）、review 回路（按 owner 分配、带明确 severity 阈值的季度告警评审，作为团队级流程向上提出）(src: 同上)。

**5 层追问防线**：

- **L1** 面试官问「你怎么发现这个问题的？」→ 答：从我自己的 oncall 体验出发，但我没有停在体验上。我在年度自评里把「低信号 page 造成的 alert fatigue 在响应质量最重要的时刻拖慢 triage」写成了我最不满意的一项，同时提了一个具体建议：季度告警评审，owner 分配，明确 severity 阈值。然后我做了 Phase 0，把体验变成数字：367 条 paging 规则散在 30 个文件里，每天约 960 条，85% 是默认 P3。**测量先于改动**这条我是刻意的，因为如果我拿不出 baseline，任何「告警太多」的说法都是一个人的抱怨，改完也证明不了变好。

- **L2** 追问「960 条一天听起来夸张，具体是怎么产生的？举个例子」→ 答：我可以举四种典型形态，它们对应四个不同的机制。第一种是**没有去抖**：一条 `for: 0m` 的 OOM-kill 规则，18 个 pod 连锁 crash，三天出 80 条。第二种是**扇出**：Alertmanager 里多条 `continue: true` 的重叠路由，一条 ALB QPS 归零告警单次触发同时进 6 个 channel，两分钟后又来一轮。第三种是**没有 dedup**：所有 receiver 都没配 dedup alias，同一个卡住的 job 每小时 page 一次，三小时三条，问题只有一个。第四种是**分级失效**：超出平均 28% 的 job 和超出 300% 的 job 拿到同一个 P1。四种机制都不是「有人写了坏规则」，是系统缺了对应的结构。

- **L3** 追问「你怎么决定哪条留哪条删？删错了漏一个故障谁负责」→ 答：我用的不是「删不删」这个二元判断，是一棵三层决策树，这样每个结论都可追溯。第一层是**能否指导行为**：不能就关掉，或者去掉 @，或者降级到信息类 channel。举两个真实例子：一条 300Mbps 的流量 page，流量高本身不是故障，oncall 看了也无事可做；一条 90% 阈值的节点内存告警，这个阈值诞生于 90% 还不是 Kubernetes 节点正常水位的年代。第二层是**偏离基线多少**：低于 2 倍不告警，2 到 4 倍 P2 进 channel 不 @，高于 4 倍 P1 page 并 @ owner。第三层是**质量阶梯**：Level 0 纯症状，Level 1 预填诊断链接，Level 2 附 runbook，Level 3 自动修复。关于责任，我的处理是每个判定都绑一条采集的真实告警样本或规则定义作为证据，Phase 1 打包成两个可 review 的 PR 带 lint 预检和回滚手册，分步 apply。也就是说这不是我一个人删的，是走 review 的。

- **L4** 追问「为什么不直接做一轮大清理就完事？为什么强调准入控制」→ 答：因为**清理改变的是状态，准入控制改变的是速率**。一次性清理只是把熵拉回低点，如果产生机制不变，一年后你会得到同一个 pager。这个项目我认为真正的核心是那个机制论证：激励是不对称的。加告警便宜且可见，出过一次事故加一行 label 就把新规则路由进 pager，没有任何准入门槛，作者还显得尽责，367 条就是这样累积出来的。删告警有风险且不可见，删错了要为漏掉的故障负责，删对了什么可观测的事情都不会发生。所以流量只朝一个方向走。与此同时每条规则的语义随着脚下系统的演化静默失效，而失效不产生任何信号。这不是任何人的失误，是「加免费、删受罚、失效无声」这三个条件下的默认轨迹。得出这个结论之后，解法就必然是三类持续做功的结构：准入控制（pager 前的 P1/P2 门槛、强制 ownership label、CI lint 拒绝不带 runbook_url 的规则）、常设测量（把 pager 本身变成 SLO 对象，告警总量、priority 分布、dedup 比例都上 dashboard）、review 回路（季度评审，按 owner 分配）。设计意图是让腐化必须对抗系统，而不是搭系统默认值的便车。

- **L5** 追问「这套治理落地了吗？效果怎么样」→ 答：我要在这里说清楚状态，因为这是这个项目最容易被我自己讲过头的地方。**baseline 是实测的，下降数字全部是我设的验收门禁目标，不是已达成的实测结果。** Phase 1 的 config 止血打包成了两个可 review 的 PR。季度告警评审我是作为团队级流程向上提出的建议，不是我已经建成的机制。如果你问我这个项目的价值在哪，我认为在两处：一是那份带证据的 baseline，它把「告警太多」从抱怨变成了可谈判的对象；二是熵增机制的论证，这个结论我可以迁移到任何一个有「加便宜删受罚」结构的系统。如果你要我自我批评，最大的问题是我**把分析做得比落地扎实**，一个更 senior 的做法是先只做一个 channel 的闭环、拿到真实的前后对比，再用这个证据去谈全局治理，因为有实测降幅的说服力远大于一份门禁表。

**归属边界**：审计、机制分析、决策树、分阶段方案是我做的。**「季度告警评审」是我向上提出的建议（proposed），不是已建成的流程。** 部署审批下放属于同一轮治理的另一条线。⚠️ 硬约束：本故事一律按「目标 / 验收门禁」口径讲，**任何场合不得声称降幅已达成**。⚠️ 通知平台名称见 README 待确认 B，对外用 "the paging channel" 更安全。

**可复用到**：90_cross_cutting（这是「影响力」域最强的素材：从个人痛点到量化 baseline 到机制论证到团队级流程提案，是完整的自下而上推动改变的叙事）、03_aiops（准入控制 / 门槛 / ownership label 直接映射 agent policy gate 与 spec 设计）、01_doris_db_operations（DB 告警的分级同样适用）。

---

## S04. galileo latency 三段分解：是 FP 不是网络

**Headline**：怀疑「流量切到 B 集群就变慢」的时候，我用三段耗时分解在一天内定案：每一条多秒请求的 `upstream_response / request_time = 1.00`，`upstream_connect` 两边都是 1ms，所以时间 100% 在后端应用内部，网络链路零贡献，对 infra 侧这是误报。

**适用题型**：讲一次你排查的疑难问题 / 怎么判断延迟问题在哪一层 / 怎么做跨团队的责任界定 / 你怎么用数据反驳一个假设。

**情境**：tenant galileo，production，AB East 是 `aws-useast1-prod-a` / `-b` 两个集群通过 autoswitch 交替服务。怀疑是流量在 cluster B 时 latency 变慢，需要判定是后端 FP 还是 infra 网络链路（链路是 APISIX → AWS NLB Target Group → 集群内 nginx ingress → Node Pod → FP）(src: `contexts/galileo_latency_investigation_20260626/REPORT.md`, memory `reference_dv_ingress_latency_decomposition.md`)。

**动作**：核心是一个分段等式：`request_time`（总）≈ `front_gap` + `upstream_connect_time`（建连 / 网络链路）+ `upstream_response_time`（后端处理）。判别规则是三条：`upstream_connect_time` 高（>50ms）指向网络链路或建连问题；`request_time − upstream_response_time`（front gap）高指向 client 到 nginx 的前段；`request_time ≈ upstream_response_time`（ratio ≈ 1.00）说明时间全在后端 (src: memory `reference_dv_ingress_latency_decomposition.md`)。然后从三个独立角度取证。第一，**逐请求分段**：从 Loki 原始 nginx access log 逐条解析多秒请求。第二，**A/B 持续分位对比**：用 `http_access_ingress_sla_*` 指标族（gauge 带 quantile label），做法是 `quantile_over_time(0.5或0.95, (metric{quantile="0.99"} > 0)[24h:5m])` 取各 cluster 活跃期典型值和持续最差值，`> 0` 用来排除空闲期。第三，**dashboard 自洽性检查**：SLA dashboard 上「Waiting Latency between Ingress and Upstream」这个面板的标题就写明 high = network issue，它全程 ≤50ms 且不与尖刺时间对齐，而「Upstream latency (FP)」面板与总延迟同步尖刺 (src: `galileo_latency_investigation_20260626/REPORT.md` §1b-d)。

**结果**：结论一句话，是 FP 后端响应时间的问题不是 infra 网络链路的问题，对网络侧是误报。证据：单点尖刺里最大那条 5.067s，`upstream_response` = 5.066s，ratio = 1.00，front gap 0.001s，connect ≈ 0；A/B 持续分位 P99 典型值 A 60ms vs B 66ms，持续最差 A 70ms vs B 81ms，其中差距全部落在 `upstream_response`（70 vs 80ms），而 `upstream_connect` 两边完全相同都是 1ms (src: 同上 §1b)。另外一个重要的量级澄清：**不存在「B 500-600ms vs A 100-200ms」那种系统性差距**，两边都在几十毫秒，B 只有约 10ms 的持续尾部惩罚，而且同样在 FP 侧 (src: 同上)。当天最大的两条延迟尖刺发生在切换之前，也就是在 cluster A 上，并不在 B (src: 同上 §1a)。

**5 层追问防线**：

- **L1** 面试官问「延迟高了，你第一步看什么」→ 答：我不先看「慢不慢」，我先做分段。总耗时 `request_time` 拆成三段：前段（client 到 nginx）、建连段 `upstream_connect_time`、后端处理段 `upstream_response_time`。这三段的比例本身就是答案。connect 段高就是网络链路或建连问题，front gap 高就是前段或 client 侧，`request_time` 和 `upstream_response_time` 的 ratio 接近 1.00 就说明时间全在后端，网络链路没贡献。这一步的价值是它**几乎零成本就能把责任范围砍掉三分之二**，在跨团队场景里这比「谁的锅」的争论快得多。

- **L2** 追问「你怎么确认 ratio 1.00 不是巧合？只看一条请求够吗」→ 答：不够，我用了三个独立角度而且要求它们互相自洽。角度一是逐请求分段，我看的不是一条，是当天所有多秒请求，包括 5.067s 那条和 03:06 那一簇，全部 ratio = 1.00、connect 和 front gap 都在 0 到 1ms。角度二是 A/B 的持续分位对比，用 24 小时窗口取活跃期的典型值和持续最差值，看的是趋势不是单点，结论同样是差距全在 `upstream_response`、connect 两边都是 1ms。角度三是 dashboard 自洽：那个专门指示网络问题的 Waiting Latency 面板全程毫秒级，而且和尖刺的时间点不对齐。三个角度都指向 FP，我才敢定案。**单一信号源不能做归因**，这条我在别的事故里也吃过教训。

- **L3** 追问「A/B 对比的查询你具体怎么写的？为什么要加 `> 0`」→ 答：`quantile_over_time(0.95, (http_access_ingress_sla_request_duration_seconds{quantile="0.99"} > 0)[24h:5m])`。三个设计点。第一，这个指标是 gauge 带 quantile label（0.95/0.99/0.999/1.0），不是原生 histogram，所以我不能用 `histogram_quantile`，只能对 `quantile="0.99"` 这条时间序列做二次统计。第二，`quantile_over_time(0.5)` 取活跃期的典型值，`quantile_over_time(0.95)` 取「持续最差」，两个一起看能区分「偶发尖刺」和「持续变慢」。第三，`> 0` 是关键，因为 autoswitch 让 A 和 B 交替服务，不服务的那一侧指标是 0，如果不过滤，空闲期的 0 会把分位数拉低，得出「B 其实很快」的错误结论。这是这个查询里最容易错的地方。

- **L4** 追问「为什么不上分布式 trace？那样一眼就能看到哪一跳慢」→ 答：如果有 trace，这个判断确实更直接，我要诚实说明我们**没有跑 trace 全链路，这是我这个方向的补课项**。但我想说的是这个替代方案不是凑合，它有它的适用性：nginx 的 access log 天然携带 `upstream_connect_time` / `upstream_header_time` / `upstream_response_time` 三个字段，这等于在 ingress 这一跳免费拿到了一个粗粒度的 span 分解，覆盖率是 100% 而不是采样，而且不需要应用改代码。它的边界很清楚：多 upstream 时 `upstream_response_time` 是总和，分不出哪个慢；connection reuse 会让 waiting 偏低；这是 ingress 视角，看不到后端内部；ingress 之前的代理层延迟不在 log 里。所以我把它定位成**第一层诊断工具而不是最终结论**：它能把问题定位到「后端内部」，但要继续追「FP 为什么偶发卡秒级」，就得进 FP 的 GC、CPU、线程池、单请求 rule+feature 计算耗时，那一层我这次调查明确写成了下一步，不属于本次网络定位范围。

- **L5** 追问「这次调查有什么是你差点搞错的」→ 答：有两个，都值得说。第一个是**指标聚合对 P100 的失明**。我们的 exporter 用 t-digest 算分位，`quantile="1.0"` 会把一个 5 秒的单点尖刺抹成大约 0.3 秒。也就是说如果我只信 VM 里的聚合指标，我会得出「最大延迟 300 毫秒，没什么问题」的结论，而真实值是 5.067 秒。查 P100 尖刺必须回到原始 nginx 日志或者 dashboard 的 ClickHouse `req_time_max` 字段。第二个是**量级本身被夸大了**。调查前的说法接近「B 500-600ms 对 A 100-200ms」，实测是两边都在几十毫秒、B 只有约 10ms 的尾部惩罚。我在报告里专门写了一节做量级澄清，因为如果不纠正这个前提，后面所有的容量和架构讨论都会建立在一个假的数量级上。另外一个反直觉的发现是：当天最大的两条尖刺发生在切换之前，也就是在被认为「快」的 A 集群上。**先验假设是「B 慢」，数据说的是「都不慢，而且最慢的在 A」**，这提醒我调查的第一步应该是验证问题陈述本身，而不是直接去找原因。

**归属边界**：这是我 own 的调查，结论和证据链都是我的。FP 应用层的后续深挖（GC / 线程池 / rule 计算耗时）明确不在本次范围，属于应用团队，不要讲成我做了 FP 内部的优化。`http-sla-exporter` 是既有组件。

**可复用到**：01_doris_db_operations（分段定位法迁移到查询链路）、03_aiops（这套三角互证的取证纪律是 agent triage 的 Iron Law 原型）、07_aws_fundamentals（NLB / Target Group / 跨 AZ 链路的延迟归因）。

---

## S05. nginx waiting P100 = 精确 1.00s 的 memcached 根因

**Headline**：一个 P100 精确等于 1.00 秒、P50 到 P95 完全正常的周期性尖刺，最后定位到 nginx 的全局限流 Lua 插件每请求同步调用一个单副本 10 线程的 memcached，连接饱和后 socket read timeout 把 nginx worker 阻塞了整整一秒。

**适用题型**：讲一次最难的排查 / 你怎么建立因果关系而不只是相关性 / 一个「精确的数字」告诉你什么 / 尾延迟问题怎么查 / 你怎么发现监控盲区。

**情境**：Grafana「SLA - Batch & RealTime」的「Waiting Latency between Ingress and Upstream」面板显示某租户的 detection 和 update 两条线 P100 周期性跳到精确 1.00s，每 5 到 10 分钟一次，而 P50 到 P95 完全正常（1 到 2ms），只有尾部受影响。集群是 `aws-uswest2-prod-a`，受影响客户里 sofi 占错误的 47.5%，另有 bdc、syncbank、navan 等 (src: `contexts/thought_review/nginx_waiting_latency_memcached_root_cause_20260408.md` §1)。该面板的计算逻辑是 `waiting_duration = request_time - upstream_response_time`，即请求在 nginx ingress 层本身消耗的时间。

**动作**：三线并行排查，因为三个假设方向（nginx 基础设施 / 客户端 / upstream 服务）的排除成本都不高，串行会浪费时间。**线路一排除 upstream**：查 fp pod 的 restart、OOM、CPU、memory、HPA replicas，结果是 4 个 pod、HPA 稳定无扩缩、0 restart、0 OOM、CPU 平均 0.12 到 0.15 核对 limit 7 核（利用率 2%）、memory 稳定；access log 里慢请求的 `upstream_response_time` 也正常（例如 0.095s），HTTP 状态全部 200 (src: 同上 §3.1)。**线路二做 nginx 配置全量审计**：从 ConfigMap 全局默认、实际生效的 nginx.conf、per-ingress annotation 三个层级把所有 timeout 值过一遍，`proxy_connect_timeout` 5s、`proxy_read_timeout` 60s、`proxy_send_timeout` 60s、`proxy_next_upstream_timeout` 0 无限，部分内部工具的 ingress override 到 3600s，没有任何 ingress 设 1s；**配置里唯一出现 "1s" 的地方是 `global-rate-limit-window = 1s`，那是限流滑动窗口大小不是 proxy timeout** (src: 同上 §3.2)。**线路三从原始日志找证据**。这里有一个关键的方法失误和纠正：初次用 `--from now-3h` 窗口没找到任何 `request_time >= 1s` 的请求（最大 0.634s），扩大到 6h 窗口后才拿到 9 条，集中在 03:08 到 03:34 UTC (src: 同上 §3.3.1)。然后是定案动作：在 error log 里找到 `global_throttle.lua:105: throttle(): error while processing key: 'get' failed for ... timeout`、`lua tcp socket connect timed out, when connecting to 10.96.150.232:11211`、`lua tcp socket read timed out`，再把 access log 的慢请求和 error log 按**时间戳加 client IP 加请求路径三重对齐**，同一秒、同一 IP、同一路径，因果关系成立 (src: 同上 §3.3.2-3.3.3)。

**结果**：根因链完整闭合：client 请求进 nginx ingress，`global_throttle` Lua 插件每请求同步调 memcached，memcached 是单 pod 10 线程，并发连接超过处理能力导致 accept queue 溢出，触发 connect timeout（50ms）或 read timeout（默认约 1000ms），Lua 插件阻塞 nginx worker 0.3 到 1.0 秒，`request_time` 增加而 `upstream_response_time` 不变，于是 `waiting_duration` 飙升，Grafana P100 = 1.00s (src: 同上 §5)。9 条慢请求的 waiting 全部是精确 1.00x 秒而 upstream 处理时间只有 0.02 到 0.03 秒；**7 条中的 7 条发生在同一秒（03:08:59）且来自不同 client IP，这证明是基础设施侧同时阻塞而不是客户端问题** (src: 同上 §3.3.1)。顺带查出的监控盲区：memcached 没有 exporter，`current_connections` 和 `listen_disabled_num` 这些内部指标完全飞盲，只能用 `container_file_descriptors` 做连接数的代理指标（正常 24，spike 时 54，连接数翻倍就开始 timeout）；memcached 容器日志也没被 promtail 采集，所有相关 LogQL 查询返回空；镜像还是 deprecated 的 `bitnamilegacy/memcached:1.6.21` (src: 同上 §4, Appendix A4/A7)。核心矛盾：ConfigMap 配了 `pool_size=10000` 而后端只有 1 个 pod 10 线程 (src: 同上 §4)。
**⚠️ 修复后数据缺失**：素材只有修复建议表（P0 扩到 2+ 副本、P0 线程数 10 → 32+、P1 把 Lua read timeout 从 1000ms 降到 100-200ms、P1 部署 memcached exporter、P2 评估 pool_size、P2 升级镜像、P3 查每分钟 :10-:13 秒窗口的周期性触发源），**没有任何修复后的 P100 实测对比**。讲这个故事只能讲到根因定案和建议，不能声称「修完从 1.00s 降到 X」(src: 同上 §6；README 待确认 C)。

**5 层追问防线**：

- **L1** 面试官问「P100 是 1.00 秒，你从这个数字里读到什么」→ 答：读到「这不是自然变慢，这是一个 timeout 被打满了」。自然的性能退化会给出一个分布，P100 会是 0.87 或者 1.34 这种数，不会反复精确落在 1.00。一个精确的整数秒意味着链路里某处有一个显式的超时配置，请求撞在天花板上被截断。所以我的第一个动作不是去查「什么变慢了」，是去**把链路上所有等于 1 秒的配置项找出来**。这个思路让我一开始就绕过了 upstream 变慢这个最直觉的假设。另一个同样重要的读数是 P50 到 P95 完全正常，只有尾部受影响，这说明触发条件是偶发的、不是持续负载。

- **L2** 追问「你怎么排除是 upstream 服务慢的？」→ 答：两层证据。指标层：fp 的 4 个 pod、0 restart、0 OOM、CPU 只用到 limit 的 2%、memory 稳定、HPA 无扩缩事件，Kubernetes 层面完全健康。日志层更直接，也是决定性的：慢请求的 access log 里 `upstream_response_time` 是 0.095s 这个量级，HTTP 状态全部 200。也就是说**后端不但没慢，还正常返回了**，多出来的一秒全部落在 `request_time - upstream_response_time` 这个差值里。这就是 latency 分解的价值，它把「谁慢」这个问题变成一个减法。

- **L3** 追问「配置里没有 1 秒，那你怎么找到 memcached 的」→ 答：配置审计做完之后我确认 1 秒不来自 proxy 层，这时候我手上唯一还没穷尽的是 nginx 自己的 error log。我去查 stderr 流里的 timeout，拿到三行关键日志：`global_throttle.lua:105` 报 memcached get 失败、`lua tcp socket connect timed out` 指向 `10.96.150.232:11211`、以及 `lua tcp socket read timed out`。到这一步我有了嫌疑人但还只是相关性，因为 error log 和慢请求可能只是同时发生。**建立因果我用的是三重对齐**：同一秒（08:07:11）、同一 client IP（192.168.212.64）、同一请求路径（POST /sofi/detection），access log 那条 `request_time=0.609 upstream_response_time=0.095` 的慢请求和 error log 那条 memcached connect timeout 完全对上。这一步之后我才敢说是 memcached。这个方法我后来当成通用纪律：**指标定位范围，access log 与 error log 的时间戳加身份对齐定因果**。

- **L4** 追问「为什么一个限流插件要同步调 memcached？这个设计本身有问题吗」→ 答：这是这个案子最有意思的一层。全局限流需要一个跨 nginx worker、跨 pod 的共享计数器，而 nginx 的 worker 是多进程的、每个 pod 又是独立的，所以必须有一个外部共享状态，memcached 是很自然的选择。问题不在选 memcached，问题在于**这条同步调用在请求的关键路径上，而它的依赖被当成了一个可以忽略的组件来部署**：单副本，10 线程，没有 exporter，镜像还是 deprecated 的。也就是说一个「非核心」的限流辅助组件成了每一个请求的 SPOF。这里有一个更普遍的设计教训：**关键路径上的同步依赖，其可用性等级必须不低于主路径**，否则它就是一个隐藏的串联可靠性项。还有一个具体的配置矛盾很典型：ConfigMap 配了 `pool_size=10000`，这是每个 nginx worker 维护的连接池大小，而后端只有 1 个 pod 10 线程来接，供需完全不匹配。如果要我给结构性的修法，我不会只扩副本，我会问这条调用能不能不同步：本地先做一层近似计数、异步同步到共享存储，牺牲一点限流精度换掉关键路径上的阻塞；或者至少把 read timeout 从 1 秒压到 100 到 200 毫秒并加 fail-open，让限流组件挂掉时放行而不是把请求拖死。

- **L5** 追问「这次调查你犯过什么错？还有什么没查清」→ 答：三件，我都记下来了。第一，**我差点得出一个错误的否定结论**。初次调查我用 3 小时窗口，没找到任何 `request_time >= 1s` 的请求，最大只有 0.634s。如果我停在那里，结论会是「日志里没有 1 秒的请求，所以 P100 是聚合造成的假象」，方向就全错了。扩到 6 小时窗口才拿到那 9 条。这件事之后我把「下结论说没有数据之前，先确认查询窗口和管道本身」变成了固定动作，因为我在另一次排查里踩过一个同源的坑：LogQL 里字面点写成 `\.` 会被 Loki 当成非法字符转义返回 HTTP 400，结果是 0 行，看起来像没数据，实际查询根本没跑，而我当时用 `2>/dev/null` 把错误吞掉了，于是错误地下了「48 小时内没有超过 1 秒的请求」的结论，后来发现明明有 5 秒。第二，**1.00 秒的确切来源我没查到源码级证据**。我定位到这是一个 1000 毫秒量级的 socket read timeout，大概率是 `lua-resty-memcached` 的默认 read timeout 或者 `global_throttle.lua` 里的显式设置，但我没有把它落到具体的配置项上，这是这次调查留下的尾巴。第三，**修复后的数据我没有**。建议表里 P0 是扩副本和加线程，但我手上没有修复后的 P100 对比，所以这个故事我只能讲到根因定案，讲不到效果。还有一个 P3 项也没查：每分钟 :10 到 :13 秒这个窗口的周期性触发源到底是什么，那才是连接 burst 的外部原因。另外这次调查暴露的监控盲区本身是一个独立的 finding：memcached 既没有 exporter 也没有被 promtail 采集，我只能用 file descriptor 数当连接数的代理指标，这种「关键依赖零可观测性」的情况应该是一条准入检查，不该等到出事才发现。

**归属边界**：调查、根因定案、建议表都是我的。**修复动作与修复后效果无素材支撑，不要讲成已修复。** `global_throttle` 限流插件与 memcached 的部署形态是既有系统状态，不是我引入的。

**可复用到**：05_blue_green_data（关键路径同步依赖的可靠性等级）、07_aws_fundamentals（连接饱和与 accept queue）、03_aiops（「下结论前先验证查询本身有没有跑」是 agent 取证的 Iron Law）、01_doris_db_operations（尾延迟的 timeout 天花板识别法）。

---

## S06. Loki 多租户日志侧与 LogQL 实战踩坑

**Headline**：我把日志侧定位成「指标的证伪工具」而不是第二套告警源：histogram 快速发现，LogQL 从原始 access log 提取请求级真实延迟做交叉验证，而这套用法有三个坑我全踩过，其中一个让我下过一个完全错误的结论。

**适用题型**：metrics 和 logs 怎么分工 / 日志成本怎么控 / 多租户日志怎么隔离 / 讲一次你自己犯的错 / 怎么保证排查结论可信。

**情境**：histogram 的精度受 bucket 边界限制。bucket 是 [0.1, 0.5, 1.0, 2.0] 时，如果大量请求集中在 0.5 到 1.0 之间，P99 的插值误差很大，典型场景是 histogram 报 P99 = 800ms 而 LogQL 从原始日志算出 P99 = 2.3s (src: `interview-3-monitoring_reference.md:113-114`)。也就是说光看 histogram 会产生**假信心**。

**动作**：架构上把 Loki 定为验证层而不是告警层。Loki 部署在 mgt 集群（`aws-uswest2-mgt-a`）的 `loki-scalable` namespace，`auth_enabled: true` 所以每个查询必须带 `X-Scope-OrgID` header，两个 tenant 是 `prod` 和 `nonprod`，规则是 dev/preprod 归 nonprod，prod/mgt/sandbox 归 prod；promtail 打的 label 是 `cluster` / `namespace` / `pod` / `container` / `app` (src: memory `reference_loki_config.md`)。日志源包括所有 prod 集群的 ingress access log、应用 stdout/stderr、K8s audit log；LogQL 的三个主要用途是从 access log 提取 latency 分位数交叉验证 histogram、per-tenant error rate 拆分、以及 tail latency disproof（histogram 说没事而日志说有事）(src: `interview-3-monitoring_architecture.md:100-117`)。工具层面日志查询走 `loki_fetch.py` 脚本而不是 Grafana MCP，用 `--json` 取原始行 (src: memory `reference_dv_ingress_latency_decomposition.md`, `reference_loki_config.md`)。

**结果 / 三个实战教训**：

第一，**LogQL 的正则转义坑，代价是一个错误结论**。`|~ "...\.[0-9]"` 里的 `\.` 会被当成非法字符转义，Loki 返回 `HTTP 400: parse error ... invalid char escape`，结果是 0 行，看起来像「没数据」实则查询根本没跑。我在一次 galileo latency 排查里用 `|~ " [1-9][0-9]*\.[0-9]{3} "` 扫 48 小时慢请求，全程报 400 但被 `2>/dev/null` 吞掉，于是错误地下了「48 小时内没有超过 1 秒的请求」的结论，后来发现明明有 5 秒的。三条纪律：字面点用字符类 `[.]` 不用 `\.`；**永远别给会真正报错的命令加 `2>/dev/null`**；下「没有数据」这种结论之前先用一条无过滤的 sanity query 确认管道确实有数据流过 (src: memory `feedback_logql_regex_escape.md`)。

第二，**Loki 派生指标的锯齿要按 status_code 拆解**。当 Loki-derived recording rule 的 QPS 图出现锯齿或周期性尖峰跌落，有效的调试顺序是：先查 rule 自身健康（`health` / `lastError` / `lastSamples`），再看原始 counter 的单调性（单调增是健康，缺口是 promtail 投递问题，重置是 counter reset），**第三步是关键：按 `status_code` 拆开分别 `rate()`，不要先看聚合的 sum**，因为 recording rules 通常 `sum` 掉了 `status_code`，把突发的非 200 折进总量，平滑的 200 基线加突发的 429 在总和里就是锯齿，看起来吓人但服务其实是健康的；第四步看突发节奏，规则间隔（例如每 4 分钟）指向客户端批处理调度器，不规则指向 promtail flush 或日志轮转追赶。这套方法在一次实际案例里验证过：某租户的 EU detection 每 4 分钟一波突发 429 来自客户端批量重试，200 全程平滑 (src: memory `feedback_loki_metric_debug.md`)。

第三，**LogQL pattern 是最大的技术债**。ingress 配置和 LogQL pattern 由两个团队维护，没有强绑定，出现过 ingress 更新后 pattern 静默失效。缓解是 pattern 版本化管理并和 ingress 配置放同一个 repo、定期 probe query 监控 `SampleExtractionErr`、ingress 格式变更走 change management 同步更新 pattern，根本解法是 CI 检验 (src: `interview-3-monitoring_reference.md:119-120`, `interview-3-monitoring.md:80`, `interview-3-monitoring_reference.md:147`)。另外一个容易踩的租户映射坑：`gcp-uswest1-prod-a` 的 Loki tenant 是 `nonprod`，名字有误导性 (src: `rules/skills/workflow_dv_monitoring_oncall.md` 高频踩坑 3, memory `reference_loki_config.md`)。

**5 层追问防线**：

- **L1** 面试官问「metrics 和 logs 你怎么分工」→ 答：一句话，**metrics 负责发现，logs 负责证明**。metrics 是低基数聚合，便宜、可以高频评估、适合做告警和趋势。logs 是高基数文本，贵、扫描慢，但保留了请求级的真实值。所以我的设计是 histogram 触发告警，LogQL 确认真假。反过来做是错的：LogQL 不适合当实时告警的基础，因为它依赖日志格式稳定、全量扫描比查预计算指标慢得多、而且高流量下采样会影响准确性。

- **L2** 追问「为什么 histogram 不够？举个具体的数」→ 答：因为 histogram 的分位数是从 bucket 里插值出来的，精度受 bucket 边界限制。假设 bucket 边界是 [0.1, 0.5, 1.0, 2.0]，大量请求落在 0.5 到 1.0 这个桶里，那么落在这个桶里的 P99 只能靠线性插值猜，误差可以很大。我们遇到的典型量级是 histogram 报 P99 = 800ms 而 LogQL 从原始日志算出 P99 = 2.3s。这不是 bug 是数学，而且它的危险性在于**它产生的是假信心而不是假警报**：dashboard 上一片绿，客户在投诉。所以我把 LogQL 交叉验证当成一条常规动作而不是特殊手段。

- **L3** 追问「auth_enabled 的多租户具体怎么用？为什么不一个 tenant 了事」→ 答：`auth_enabled: true` 之后每个查询都必须带 `X-Scope-OrgID` header，Loki 按 tenant 做完整的数据与索引隔离。我们分了 `prod` 和 `nonprod` 两个 tenant，规则是 dev/preprod 归 nonprod，prod/mgt/sandbox 归 prod。分开的理由有三个：一是**爆炸半径**，nonprod 的日志量经常是不受控的（有人开 debug level 刷日志），单 tenant 会让它挤占 prod 的查询资源和 ingestion 配额；二是 retention 和配额可以按 tenant 分别配；三是权限边界，prod 日志的访问面应该比 nonprod 窄。为什么不按每个客户租户分？因为 tenant 在 Loki 里是一个比较重的隔离单位，而我们需要的 per-client 下钻是查询维度不是隔离维度，用 label（`cluster` / `namespace` / `pod` / `container` / `app`）加 line filter 就够了，把每个客户做成 Loki tenant 会让运维复杂度爆炸。一个真实的坑：`gcp-uswest1-prod-a` 这个集群名字里有 prod，但它的 tenant 是 `nonprod`，这种命名误导我专门记进了 skill 的高频踩坑清单。

- **L4** 追问「为什么选 Loki 而不是 ELK？」→ 答：核心理由是 label-based indexing 更契合我们已有的 Prometheus label 体系。我们的 metrics 侧已经把 `cluster` / `namespace` / `pod` / `app` / `tenant` 这套 label 统一好了，Loki 用同一套 label 做索引意味着 Grafana 上从一个 metric 面板跳到对应日志几乎是零摩擦，而 ELK 需要另建一套 mapping 和索引策略。第二个理由是成本模型：Loki 只索引 label 不索引日志正文，存储和索引开销远小于 Elasticsearch 的全文倒排，这对我们的日志量是决定性的。代价我也清楚：不做全文索引意味着**没有 label 约束的查询会变成暴力扫描**，所以 LogQL 的查询纪律（先用 label selector 把范围收窄，再用 line filter）比 ELK 里重要得多，这也是我们「Loki 在高流量下全量扫描慢」这个已知瓶颈的来源。我要说明的是这个选型我做的是评估和推荐，最终是团队共识。

- **L5** 追问「这套日志方案最大的技术债是什么？」→ 答：LogQL pattern 的维护成本，而且它的失败模式是**静默的**。ingress 的日志格式配置和 LogQL 的解析 pattern 由两个团队维护，之间没有强绑定，出现过 ingress 更新之后 pattern 静默失效的情况：查询不报错，只是 `SampleExtractionErr` 上升、提取出来的字段变空，dashboard 上看到的是「没有慢请求」而不是「解析失败」。这和我踩过的 LogQL 正则 400 坑是同一类问题：**日志侧的失败倾向于表现为「没有数据」，而「没有数据」很容易被误读成「没有问题」**。缓解手段是三条：pattern 版本化并和 ingress 配置放同一个 repo、定期跑 probe query 监控 `SampleExtractionErr`、ingress 格式变更走 change management 同步更新 pattern。根本解法是 CI 检验，format 变更必须同时更新 pattern 才允许 merge。如果重做，我会在设计第一天就加一条不变量：**每一条依赖解析的日志查询都必须有一个配套的 canary 查询，用来证明管道活着**，因为一个只会静默返空的检测手段本身就是盲区。

**归属边界**：Loki 选型是我评估推荐、团队共识。ingress 日志格式由另一个团队维护，pattern 的两团队边界问题是客观状态而不是我的疏漏，但把它变成 CI 门禁是我提的解法（尚未落地）。

**可复用到**：04_iac_cicd_k8s（配置与解析 pattern 同 repo + CI 门禁）、06_aws_cost_finops（Loki 的索引成本模型对比 ELK）、03_aiops（「静默失败要有 canary 证明管道活着」是 agent observability 的核心原则）。

---

## S07. 用 `system.query_log` 做负载画像取证

**Headline**：一个不可逆的表结构设计原本要基于一份 50 条精选查询的 benchmark 来做，我先去挖了 14 天生产 `system.query_log`、7,470 万条日志行，画面完全反过来：超过 90% 的流量是点查，于是第二张服务表从「也许要」变成「必须要」。

**适用题型**：你怎么用数据支撑一个不可逆决策 / 讲一次你挑战了既有方案 / 可观测性数据除了告警还能干什么 / 怎么做容量或负载规划 / 讲一次你避免了一个大错。

**情境**：CH 到 Doris 迁移中服务表的布局设计。原始方案建立在一份精选的 50 条查询 benchmark 上，而分布键这类决策一旦落地就不能 ALTER (src: `adhoc_jobs/dynamic_resume_site/content/case_study_ch_to_doris.md:43`)。

**动作**：在提交这个不可逆布局之前，我去挖了 14 天的生产 `system.query_log`，7,470 万条日志行，做真实负载画像 (src: 同上)。

**结果**：画面反转。绝大多数流量（远超 90%）是点查，键是一个高基数的用户标识，而且其中大部分是无界的「取最新值」重建，没有任何时间过滤条件可以事后加上去。结论是第二张服务表从「也许」变成必须，而且它的设计随之加宽。原文的判断是：**按 benchmark 来设计会优化错的负载** (src: 同上)。相关的取证纪律在另一处也有体现：52 条真实工作负载的 eval suite 里，有 6 条最重的生产查询（32 到 76 GiB）是从 ClickHouse `system.query_log` 里拉出来的真实查询，不是构造的 (src: `contexts/resume_highlights_doris_dcluster.md:122`)。

**5 层追问防线**：

- **L1** 面试官问「为什么不信 benchmark」→ 答：因为 benchmark 是人挑的，而人挑查询的时候会不自觉地挑「有代表性的」和「有意思的」，这两个标准都不等于「按频次加权后占流量的」。这个案子里 benchmark 有 50 条，很体面，但真实流量里超过 90% 是一种它没充分覆盖的形态。我的原则是：**决策不可逆的时候，负载画像必须来自生产实测的全量日志而不是采样或精选**。

- **L2** 追问「14 天 7,470 万行，你具体统计了什么维度」→ 答：我要精确说明素材支持的结论范围。我得到的结论是三条：流量构成上绝大多数（远超 90%）是点查而不是分析型扫描；点查的键是一个高基数的用户标识；这些点查里大部分是无界的「取最新值」重建，也就是没有时间范围谓词，因此无法事后补一个时间过滤来剪枝。这三条正好对应设计上要回答的三个问题：要不要单独的服务表、分布键选什么、能不能靠分区剪枝救。至于更细的分布（比如按小时的 QPS 曲线、每条查询的字节数分位），那部分我没有写进结论，我不会临场编。

- **L3** 追问「这个结论怎么改变了设计？」→ 答：改了两处。第一，第二张服务表从「也许要」变成必须要，而且它的设计随之加宽，因为点查要取的列范围比预期宽。第二，也是更重要的一处：既然点查的键是一个高基数用户标识，那么正确的物理布局是**按这个用户键做 hash 分布**，让一个用户的行物理聚在一起。这一步之后还有一个教训值得连着讲：直觉的修法是加 bloom filter，实测把扫描行数砍了 73%，墙钟时间一点没动，因为一个活跃用户的行散落在 2,044 个分区文件里，下界是**文件打开次数而不是扫描行数**。索引修不了布局问题。所以负载画像不只是告诉我「要不要建表」，它告诉我「瓶颈在哪个物理量上」，这才是它值 7,470 万行的地方。

- **L4** 追问「用 query_log 做这件事的代价和局限是什么」→ 答：三个局限。第一，`system.query_log` 是**当前系统上的负载画像**，它反映的是客户端在既有能力约束下发出的查询，不是客户真正想问的问题。如果旧系统有一个查询慢到没人敢用，它在 query_log 里就是低频的，迁移后可能爆发，这是一个系统性的盲区。第二，扫 14 天全量 log 本身有成本，query_log 表通常很大，查询要小心不要把生产打慢，而且 query_log 自己也有 retention 和采样配置，要先确认它是全量记录还是采样的。第三，log 里的 SQL 是文本，做形态归类需要模板化（把参数抽掉归到 query template），这一步的归类口径会影响结论，比如「点查」的定义边界。所以我把它当成**决定性证据但不是唯一证据**：后续还做了两表 A/B（同数据、镜像键、四次测量）才提交分布键，并在迁移过程中的三个数据量检查点（15M / 107M / 286M 行）重测延迟，证明表长大 19 倍延迟仍然平的。

- **L5** 追问「如果 query_log 没开或者被清了，你怎么办」→ 答：那我会按证据强度往下退，而且会明确告诉 stakeholder 我退了几档。第一档退到入口侧的 access log，ingress 或者应用层的请求日志通常能给出 endpoint 加参数形态的分布，虽然拿不到 SQL 但拿得到调用模式，对于「点查为主还是分析为主」这个层次的判断往往够用。第二档退到抽样：开一段时间的 query log 或者 slow log，但这时候必须处理**采样偏差**，slow log 会系统性偏向重查询，用它来推断流量构成会得出完全相反的结论，这个陷阱很致命。第三档才是访谈加 benchmark，也就是原始方案。关键是我会把决策的可逆性和证据强度挂起来：**证据只有第三档的时候，我不会去做不可逆的决策**，我会先选一个可以 ALTER 的保守布局，同时把 query_log 打开，等两周拿到真实画像再做那个不可逆的选择。这个案子最值钱的地方不是我挖了 7,470 万行，是我在提交不可逆决策之前先问了「我的证据够不够支撑不可逆」。

**归属边界**：query_log 挖掘、负载画像结论、以及由此改变的表设计判断是我的。这个故事在 01 目录（Doris/DB）是主线，在本目录只取「用 telemetry 做取证与决策」这个切面，**不要在监控面试里展开 Doris 引擎层的工作**（ROUTE PLAN / ESTIMATE PLAN 的归属边界见 `contexts/resume_highlights_doris_dcluster.md` §0）。

**可复用到**：01_doris_db_operations（主线故事）、06_aws_cost_finops（负载画像是 unit economics 的输入）、05_blue_green_data（两表 A/B + 三检查点重测是数据层验证模式）。

---

## S08. 从标 CPU 到设计 SLO：监控观的重建

**Headline**：junior 时期我把指标横着切成 system 和 application 两类，以为把 CPU 标到 dashboard 上监控就做完了；真正的转折是学会自上而下设计，因为不同主体关心不同指标，每个主体的 SLO 不同、dashboard 不同，而 dashboard 存在的意义是回答问题。

**适用题型**：你从 junior 到 senior 最大的变化是什么 / 讲一个你改变了看法的技术观点 / 你怎么定义好的监控 / 你怎么设计 dashboard / 为什么你觉得自己够 senior（这是**回答「你凭什么是 senior」的最佳素材**）。

**情境**：我真正开始懂 SLO 不是因为读了 Google SRE 那本书，而是因为换了个位置，从 Intel 的 demo 环境到 DataVisor 的 production (src: `adhoc_jobs/dynamic_resume_site/content/growth/g_slo_topdown.md`)。在 demo 环境里 SLO 是个概念，系统挂了重启就好，没人真的因此损失什么，「可用性 99.9%」是 PPT 上的数字，感性上是空的。到了 production 背后站着一个真实的客户，这时候才明白 SLA 是一个承诺，是对客户签字画押的那条线；它是系统稳定性的具象化，抽象的「稳定」被翻译成「月度可用性 ≥ 99.9%，否则赔偿」；而 infra 被推到了前台，以前它躲在业务后面，现在它的抖动直接变成客户的损失、客户的电话、客户的流失 (src: 同上)。

**动作 / 认知转变**：我曾经这样理解监控，分两类，system metrics（CPU、内存、磁盘、网络）和 application metrics（QPS、错误率、延迟），把它们都采下来标到 dashboard 上，监控就算做完了。这个划分错在它是一个**水平切分**：它按「指标长在系统的哪一层」分类，而不是按「谁需要它、用它回答什么问题」分类。结果是 dashboard 上摆满 CPU 曲线但没人能从一屏里看出客户现在有没有在受影响；一堆指标都绿而客户在投诉，因为绿的是主机、痛的是请求；出事时 dashboard 帮不上忙，因为它不是为回答问题建的，是为「把能采的都采上」建的。横切的监控本质是仪表堆砌不是监控设计 (src: 同上)。真正的做法是 top-down，从最上层从 user 的视角往下推，核心一句话：**不同的主体关心不同的指标**。客户和业务关心我的请求成功吗、够快吗、数据当天到了吗，这是 SLA/SLO 层；服务 owner 关心哪个接口在烧 error budget、哪个依赖在拖后腿，这是黄金信号层；oncall 关心现在哪里坏了、坏在哪一层、怎么止血，这是排障链路层；平台和容量关心资源够不够撑到下个季度，这才轮到 CPU 和内存登场。CPU 不是不重要，是它属于最下面那个主体，把它摆到最上层给客户看是层级错位 (src: 同上)。

**结果 / 三条推论**：每个主体的 SLO 不同，客户的 SLO 是可用性和延迟，容量团队的目标是利用率和余量，别用一套指标假装服务所有人；每个主体的 dashboard 不同，一块面板服务一个主体回答一类问题，给客户看的面板上不该有 CPU，给 oncall 看的面板不该只有一条总可用率；**dashboard 的存在意义是回答问题不是展示数据**，建之前先问这块板要回答谁的什么问题，答不上来的曲线就是噪声 (src: 同上)。这个观点在我的告警治理项目里有一个同构的表述：不能指导行为的 alert 是噪声 (src: `p_alert_gov.md`)。落到具体产物就是 minimal good page 标准：值班人看完能回答三个问题，用户有没有受影响和严重程度、最可能在哪一层（edge / 服务 / 依赖）、最近有没有变更；超出这三个问题的都是 drill-down 不放首屏；方法是**先列 question 再想 panel，说不出 panel 回答什么问题就不加** (src: `interview-3-monitoring_reference.md:136-137`)。

**5 层追问防线**：

- **L1** 面试官问「你觉得自己从 junior 到 senior 的分界线在哪」→ 答：在监控这件事上我有一条很清楚的线，就是设计的方向反过来了。以前我是自下而上：能采什么就采什么，采完标到 dashboard 上，觉得监控做完了。现在是自上而下：先想清楚谁在看、他要回答什么问题，再决定标什么、怎么标、给谁看。这个顺序反过来的那一刻我知道我过线了。触发这个转变的不是读书，是位置变了，从 demo 环境到 production，背后站着一个签了 SLA 的真实客户，SLO 从 PPT 上的数字变成了一种压力。

- **L2** 追问「四个主体的分层具体怎么落到产物上」→ 答：落成不同的 dashboard 和不同的告警等级。客户和业务那层落成 Tenant SLA Overview，per-tenant per-region 的可用性和延迟，这一层的告警是 PAGER。服务 owner 那层落成 Service Drill-down 和黄金信号，app 到 pod 到 container，这一层多数是 HIGH。oncall 那层落成 minimal good page 加 Latency Decomposition，回答「坏在哪一层」。平台容量那层落成 Cluster Capacity，CPU 内存磁盘在这里才登场，告警是 MEDIUM 走工单。关键是**一块面板服务一个主体**，给客户看的面板上不该有 CPU，给 oncall 看的面板不该只有一条总可用率，因为一条总可用率回答不了「怎么止血」。

- **L3** 追问「minimal good page 的 minimal 具体怎么定？」→ 答：用三个问题做准入。值班人看完这一屏必须能回答：一，用户有没有受影响、严重程度多少；二，最可能在哪一层，edge、服务还是依赖；三，最近有没有变更。超出这三个问题的都是 drill-down，不放首屏。执行上的关键动作是**先列 question 再想 panel**，说不出一个 panel 回答什么问题就不加。变更这一项的集成方式很具体：用 Grafana 的 annotation API，CI/CD 部署完成时打标记，ArgoCD 或 Flux 走 webhook 同理，panel 开启 annotation 显示之后所有图表自动出现部署竖线。这一条的价值被低估了，因为「最近有没有变更」在真实事故里的命中率极高，而它是纯工程可以自动化的。

- **L4** 追问「这个 top-down 的说法听起来对，但 CPU 告警你就完全不要了吗？」→ 答：不是不要，是**降级和换位置**。CPU 告警的问题不是它没用，是它被摆在了 PAGER 这个位置上，而它回答不了「用户有没有受影响」。我的处理是：CPU、内存这类资源指标下沉到平台容量这个主体，告警等级降到 MEDIUM 走工单，用途是容量规划和趋势预警，这是它真正有价值的场景。同时我要说清楚这个原则的边界：**有些资源指标是先兆而不是症状**，比如磁盘即将写满、证书即将过期、连接池即将耗尽，这类「不处理必然在可预测的时间点变成用户影响」的指标应该保留在较高等级，因为它们的价值恰恰在于「用户还没受影响」。所以我的分类不是「资源指标一律降级」，是「不能指导行为的降级，能指导行为且有明确时间窗的保留」。这也是我的告警治理里质量阶梯那一条的来源：一条告警的等级应该和它能触发的动作明确性挂钩。

- **L5** 追问「这个转变里你有没有走过弯路，或者现在还没做到的部分」→ 答：有两件，都是这个观点的未完成部分。第一件是**顺序上我自己也违反过**：我在 VM 平台项目里是先搭采集再补 SLO，导致早期的告警阈值有一部分是经验值不是有根据的目标值。这跟我讲的 top-down 是矛盾的，如果重做我会先定义 SLO 再搭采集。第二件更根本：top-down 的最上层是「客户关心什么」，而这一层要真正落地需要的不只是 dashboard，是**制度**，也就是 error budget policy 写下来、成为产品和 SRE 之间的契约、预算烧光就冻结发布。这部分我没有建成。我把这个归因说清楚：SLO 定义需要 service ownership 支撑，在我们的组织结构里这不是我能单方面推成的，我当时的选择是先把可测量性做实。但我不会把这解释成「所以做不了」，因为一个更 senior 的做法是先挑一个有明确 owner 的服务做试点，把 budget 消耗上 dashboard 跑三个月，用真实数据去谈冻结发布这种有牙齿的条款。也就是说我的 top-down 目前只走完了工程侧那一半，制度侧那一半我知道怎么走但没走。

**归属边界**：这是个人认知叙事，没有归属风险。原始素材是我自己的博客草稿。⚠️ 唯一要小心的是 L5 里的诚实点必须说，否则这个故事听起来会像「我已经把 SLO 体系建成了」，那和 README 中环第一条冲突。

**可复用到**：90_cross_cutting（这是回答「你凭什么 senior」和「你的技术观」的核心素材）、03_aiops（把「谁在关心什么」推到 agent observability 上）、所有方向的 dashboard 设计题。

---

## S09. 先证伪再解释：histogram skew 造成的假 P99 告警

**Headline**：一条延迟告警声称 P99 越限，但同一时间窗的应用日志和 APM 显示没有任何慢请求、错误率也没波动，我的第一个动作不是解释指标，是先证伪真实用户影响，然后才去解释这个 P99 是怎么被算高的。

**适用题型**：怎么判断告警是真的 / 你怎么处理假告警 / 讲一次你的排查顺序和别人不同 / 指标可信度怎么保证。

**情境**：一条延迟告警声称 P99 正在越限，而同一时间窗口的应用日志与 APM 显示没有慢请求、错误率也无波动 (src: `adhoc_jobs/dynamic_resume_site/content/integration/oncall_track_record.md` case 7)。

**动作**：调查第一步是**先证伪真实用户影响**，再解释指标。证伪之后的解释是：多实例采集时间错位叠加 histogram 分桶聚合偏差，把计算出的 P99 虚高了 (src: 同上)。

**结果**：以假告警结案并附完整证据链，随后加固告警规则，让同一偏差模式无法再次呼叫值班 (src: 同上)。这个案子所属的失败域在我的 case 库里叫「可观测性 / 假信号」，核心问题一句话是「告警看到的是否等于用户体验到的」，这个域下有 3 个 case (src: 同上 INDEX_TABLE)。整个 obs 域累计 6 次调查、7 棵 debug-tree、4 个根因模式 (src: 同上 STATS)。

**5 层追问防线**：

- **L1** 面试官问「告警响了，你第一步做什么」→ 答：判断它是不是真的。具体动作是找一个**独立于告警数据源**的信号来确认用户影响：告警来自 metrics，那我就去看日志和 APM。如果日志里没有慢请求、错误率没动，那么用户没受影响，这条告警的优先级立刻从「止血」降到「解释指标」，这是两种完全不同的工作模式。顺序很重要：**先证伪影响，再解释指标**。反过来做的代价是你会花很长时间去解释一个不存在的问题，而且在真有事故的时候这个顺序还会让你误判严重程度。

- **L2** 追问「P99 为什么会被算高？」→ 答：两个机制叠加。第一个是**多实例采集时间错位**：同一个服务的多个实例被 scrape 的时刻不同，聚合的时候把不同时间点的快照当成同一时刻的分布，这本身就引入偏差。第二个是 **histogram 分桶聚合偏差**：`histogram_quantile` 是在 bucket 边界之间做线性插值的，当大量样本集中在某一个桶里，插值出来的分位数误差可以很大，而且跨实例聚合 bucket 之后这个误差会被放大。两者叠加就得到一个比真实值明显高的 P99。这类偏差有一个共同特征：**它是计算产物而不是系统行为**，所以它在独立数据源上找不到对应。

- **L3** 追问「你怎么加固规则，让它不再误报」→ 答：思路是不让单一信号独自决定 page。可以用的手段有几层：把告警条件从「分位数越限」改成同时要求一个**与用户影响更直接相关的信号**动起来（比如 error ratio 或者慢请求计数），这样纯计算偏差不足以触发；用 multi-window 确认，短窗和长窗同时越限才升级，因为采集错位造成的偏差往往不能在两个不同长度的窗口上同时稳定成立；以及在规则里对样本量设下界，样本太少的时候分位数本身不可信。我要诚实的是素材写的是「加固告警规则使同一偏差模式无法再次呼叫值班」，具体改了哪几条我不会临场编细节，我讲的是我会用的手段。

- **L4** 追问「那你为什么不干脆不用 histogram 的分位数做 SLI？」→ 答：这正是我认同的方向，而且它是一个概念分离的问题。我现在的口径是把四层分开：SLI 是衡量什么，histogram 是怎么记录分布，quantile 是怎么查看分布里的统计值，SLO 是对这个指标在时间窗口内施加什么目标。推荐的 SLI 口径是 `SLI = requests_under_threshold / valid_requests`，也就是**基于事件计数的比例而不是分位数**，理由正是这个案子：比例型 SLI 只需要 bucket 边界上的一个计数值，不需要插值，所以它不受桶内分布和跨实例聚合的插值误差影响，跨实例聚合也只是加法，天然可加。`P99 ≤ Xms` 更适合作为观测视角或者补充视角，不要默认把 quantile 当成 SLI 本体。这个区分我是吃过这类误报之后才真正内化的。

- **L5** 追问「同一类问题你还在别的地方踩到过吗？」→ 答：踩过，而且是相反的方向，这对我来说是更深的一课。这个案子里聚合把 P99 算**高**了，产生假警报。但在 galileo 那次延迟调查里，聚合把 P100 算**低**了：exporter 用 t-digest 算分位，`quantile="1.0"` 把一个真实 5 秒的单点尖刺抹成大约 0.3 秒。也就是说同一类「聚合与真实分布的偏差」既可以制造假警报也可以制造假信心，而后者危险得多，因为它不会有人来叫你。这两个案子合起来给我的纪律是三条：任何分位数指标都要知道它是怎么被算出来的（原生 histogram 插值还是 t-digest 近似还是精确排序）；**查极值一定回原始记录**，我们查 P100 尖刺的做法是回 nginx 原始日志或 ClickHouse 的 `req_time_max` 字段，不信聚合；以及归因永远不能只用单一信号源，这条在我的 case 库里被写成了一条明确规则。

**归属边界**：这是我 oncall 处理的真实事故，蒸馏在 case 库里。素材是 `oncall_track_record.md` 的 note 级摘要，**细节颗粒度有限，被追问具体规则改动时要说明「手段我讲得出，具体改了哪几条我不编」**。

**可复用到**：01_doris_db_operations（DB 指标的可信度）、03_aiops（agent 的 eval 信号同样有「计算产物 vs 真实行为」的区分）、90_cross_cutting（排查顺序体现判断力）。

---

## S10. CPU 92% 的多信号归因：查询是真凶，merge 只是在场证明

**Headline**：一个 ClickHouse 节点 CPU 跑到 92%，第一眼看 `system.merges` 得出的初判是 merge 欠债，交叉验证 `system.processes` 和线程级 `top -H` 之后结论反转：三条并发全表扫描占了约 67% CPU，merge 只占约 10%。

**适用题型**：怎么做资源归因 / 讲一次你推翻了自己的初判 / 相关性和因果性 / 为什么单看一个 dashboard 不够。

**情境**：一个 ClickHouse 节点 CPU 跑到 92%（30 核用掉 27.6 核）(src: `adhoc_jobs/dynamic_resume_site/content/integration/oncall_track_record.md` case 1)。

**动作**：先看 `system.merges`，得出的初判是 merge 欠债。然后用 `system.processes` 与线程级 `top -H` 做交叉验证 (src: 同上)。

**结果**：结论反转。3 条并发的 `SELECT *` 全表扫描（每条约 7 亿行）占约 67% CPU，merge 只占约 10%。沉淀为一条规则：**CPU 归因不许只看单一信号源，查询视图与线程视图必须互证** (src: 同上)。

**5 层追问防线**：

- **L1** 面试官问「CPU 高你怎么定位」→ 答：至少两个视角互证，而且这两个视角要来自不同的抽象层。一个是**工作负载视角**（在数据库里就是 `system.processes` 这类当前执行的查询），一个是**线程视角**（`top -H` 或者 per-thread 的 CPU 归属）。原因是工作负载视角告诉你「有什么在跑」，线程视角告诉你「CPU 实际花在哪」，这两个可以不一致，而不一致的地方就是答案。我这个案子里就是不一致的：merge 在跑（所以 `system.merges` 有内容），但 CPU 主要不在 merge 上。

- **L2** 追问「为什么第一眼会看错？」→ 答：因为 `system.merges` 有内容这件事是**真的**，它只是不是主因。merge 确实在进行、确实占了约 10% 的 CPU，所以它看起来完全像一个合理的解释，这是最危险的一类错误：不是数据错了，是我用一个真实但不充分的信号解释了一个现象。这里的认知陷阱是**先看到的信号会成为锚**，尤其当它在直觉上是一个已知的常见原因（ClickHouse 的 merge 压力确实是经典问题）。我沉淀下来的纪律是：一个能解释现象的信号出现时，**先问它能解释多少百分比**，而不是问它能不能解释。10% 和 67% 的区别不在于哪个是真的，在于哪个决定了墙钟。

- **L3** 追问「那你怎么量化到 67% 和 10% 的？」→ 答：靠线程级归属。`top -H` 给出的是每个线程的 CPU 占用，而数据库的线程通常是按用途命名或者可以关联到 query id 的，把线程的 CPU 加总按用途归类，就能得到「查询执行线程占多少、后台 merge 线程占多少」。这一步是把「有什么在跑」变成「谁吃掉了 CPU」的关键。同时 `system.processes` 提供了佐证：3 条并发的 `SELECT *`，每条约 7 亿行，这个量级本身就能解释 67%。两个视角在数量级上互相支持，我才敢定案。

- **L4** 追问「定案之后你的处理和如果按 merge 处理有什么不同」→ 答：完全不同的方向，这也是为什么归因错了代价很大。如果按 merge 欠债处理，动作是调 merge 相关的并发和资源配额、或者调整分区和 TTL 策略降低 merge 压力，这些改动会作用在后台任务上，而且大多是配置级的、生效慢。真实原因是三条并发的 `SELECT *` 全表扫描，动作就完全不一样：短期是治当前这几条查询（限流、kill、或者给发起方一个更好的查询形态），中期是问「这种 `SELECT *` 全表扫是谁在发、是否应该被允许」，也就是变成一个**准入控制**问题而不是资源配额问题。这和我在告警治理里的判断是同构的：能不能在源头限制比在下游扩容更值钱。如果一直按 merge 处理，CPU 会持续在 92%，而且下一次同样的查询进来还会复现。

- **L5** 追问「这条规则你怎么落到别人身上，不只是你自己记住」→ 答：我把它写进了 case 库并变成一条明确的规则文本：**CPU 归因不许只看单一信号源，查询视图与线程视图必须互证**。我认为这比写一份「ClickHouse CPU 高怎么查」的 runbook 更有价值，因为 runbook 是场景绑定的，而这条规则是可迁移的：它在 nginx 上的形态是 access log 与 error log 必须按时间戳和身份对齐，在 latency 上的形态是三段分解必须和 dashboard 的网络指示面板自洽，在延迟指标上的形态是 histogram 与原始日志互证。我要承认的边界是：把它写进 case 库和把它变成团队的实际习惯是两件事，我做到的是前者加上在 oncall 交接和 skill 文档里反复讲，我没有做到把它变成一道机械的门禁（比如 triage 模板里强制填两个信号源）。如果重做，我会把它做成模板里的必填字段，因为依赖记性的纪律会随人员流动衰减。

**归属边界**：我 oncall 处理的真实事故，蒸馏在 case 库。素材是 note 级摘要，颗粒度有限。这个故事在 01 目录也会出现（ClickHouse 运维），本目录只取「指标归因纪律」这个切面。

**可复用到**：01_doris_db_operations（主线之一）、03_aiops（多信号互证是 agent triage 的核心约束）、90_cross_cutting（推翻自己初判是行为面素材）。

---

## S11. Dashboard 的分层不是给面板归类，是定义「什么时候可以停止往下看」

**Headline**：我们的排障入口不是面板集合，是一条按提问顺序排列的路径，每一层只回答一个问题，答不出这个问题的面板就不该放在这一层；SLA 层全绿时的正确动作是停下不看，而不是习惯性地把资源面板也扫一遍。

**适用题型**：你怎么设计 dashboard / 出问题第一步看哪个 / 为什么不把所有指标都摊上去 / 什么是好的可观测性设计 / 你怎么看 AI 进入运维（延伸）。

**情境**：常见的 dashboard 是按组件类型摆的，所有 CPU 面板一屏、所有 DB 面板一屏。这种组织方式的问题是它把「监控了什么」当成了组织原则，而 oncall 真正需要的是「按什么顺序问问题」。我在实际 oncall 里已经在用一个更收敛的入口：minimal good page 的三问准入（用户有没有受影响 / 问题在哪一层 / 最近有没有变更），以及 SLA dashboard 上的 Waiting → Upstream → Infra 三步决策树 (src: `work-contexts/career/interview/interview-3-monitoring_reference.md:134-142`；`rules/skills/workflow_dv_monitoring_oncall.md:59`，panel 373 "Waiting Latency between Ingress and Upstream" 在 dashboard `p1KqfRAMk` 上)。这套东西有效但没有理论化，也没有覆盖全部排障场景。

**动作**：我把它扩展成一条五层故障定位路径，每层锚定一个具体问题 (src: `contexts/thought_review/2026-08-06_observability_dashboard_causal_troubleshooting_path.md`)。第一层 SLA / Golden Signals 回答用户有没有受影响，面板刻意做少，只有 p99 latency、QPS、success rate。第二层 Blast Radius 回答影响范围有多大，按 region / API / tenant 拆，这一层决定后续是找某个租户沟通还是拉全员排查。第三层 Saturation 回答瓶颈在哪。第四层 Trace 回答请求卡在哪一跳。第五层 Historical Trend 回答是不是在持续恶化。

Saturation 层我给了一条可执行的选型规则：这一层是 Bottleneck Dashboard 而不是 Resource Usage Dashboard，选「是否开始等待」类指标而不是「用量」类指标。CPU Run Queue 不是 CPU Usage，Kafka Lag 不是 Message Count，DB Connection Wait 不是 Connection Count，GC Pause 不是 Heap Usage，Disk IO Wait 不是 Disk Usage。这条规则的理论根据是两位权威对 saturation 的定义并不兼容：Brendan Gregg 的 USE 方法把 saturation 严格定义为排不进去、被迫排队的那部分多余工作，把资源忙碌时间占比单独叫 utilization；Google SRE Book 的定义里根本没有出现 queue 这个词，讲的是 how full 和 utilization target。两套术语给出的操作结论是一致的：要测的是等待，不是用量 (src: `contexts/survey_sessions/ai_agent_observability_interface_gap_survey_20260806.md` §2.1)。

Trace 层我明确标了基础设施前提。我们的栈是 VictoriaMetrics + Loki + Grafana，没有 Jaeger / Tempo 级别的分布式追踪，所以这一层落地的是退化方案：靠 request_id 在 Loki 里做跨服务日志关联，拿到的是日志时间戳的粗略间隔而不是精确 span 耗时。设计时先确认前提成立，不设计一个依赖不存在基建的面板。

**结果**：五层模型和 Saturation 选型规则成文，Trace 层的退化方案和 Historical Trend 层需要配基线（避免把租户自然增长误判成资源枯竭前兆）这两个修正也一并定下来。**必须诚实的部分：这是设计原则，没有对现有 Grafana dashboard 做过逐层缺口核对，也没有改前改后的 MTTR 对比数据。** 已落地的是三问准入和三步决策树，五层模型是它们的理论化扩展。

**5 层追问防线**：

- **L1** 「你们 dashboard 具体怎么分层？」→ 先讲已落地的部分：三问准入和 Waiting → Upstream → Infra 三步决策树，能报出具体 panel。然后说我把这套原则扩展成了五层路径，下一步是拿现有面板逐层核对缺口。**不要说现在的 Grafana 就是按五层组织的。**

- **L2** 「出问题第一步看哪个？为什么不摊开所有指标？」→ SLA 层，p99 latency / QPS / success rate，全绿就停。分层的意义不止是给面板归类，是明确什么时候可以不往下看，这同时是 less is more 的执行标准和 alert fatigue 的预防手段。有实证支撑：唯一一项直接对比 dashboard 与对话式界面的研究显示，dashboard 在已知问题的例行检查上速度、精度、认知负荷全面占优，对话式界面只在探索性未知问题上有优势 (src: 调研报告 §5.2，GI 2026)。这条和 Charity Majors 的观察互补，她说 dashboard 对见过的问题有效、对 unknown-unknowns 无效。

- **L3** 「Saturation 层具体怎么落地？」→ 讲选型规则（等待类不选用量类），举有出处的例子：per-tenant SLI recording rules 里 saturation 本来就是被物化的一族信号（QPS / error ratio / P95 / P99 / saturation / tenant SLI），Kafka consumer lag 是真实的告警对象和 playbook。**不要举 DB connection wait 说成已有面板，那条没核实过。** 补一句 Google 的原文依据：saturation 必须直接在子系统本身测量，无法从服务边界观察，所以这一层必然是按组件定制的，做不出统一模板 (src: 调研报告 §2.6)。

- **L4** 「为什么按因果链排而不是按组件类型排？高利用率不就说明有问题吗？」→ 按组件排的组织原则是「监控了什么」，按链条排的组织原则是「按什么顺序提问」，后者才对应 oncall 的真实动作。关于利用率：高利用率本身是成本效率的目标而不是风险信号，Google SRE Book 明确把 utilization 当成控制总成本的杠杆。判断风险要靠 headroom 或排队指标，不能靠利用率本身 (src: 调研报告 §2.5)。

- **L5** 「这个分层怎么验证是对的？」→ **诚实作答，这是最容易穿的一层。** 没有做过改前改后的 MTTR 对比。支撑是三层：理论上有 USE 方法和 Google SRE Book 的定义；实证上有 GI 2026 那项已知/未知问题分工的间接印证；实践上有 galileo 那次三步决策树一步排除网络嫌疑的案例。如果给我这个职责，第一步是盘点现有面板落在五层的哪一层、标出完全缺失的层（我预判 Blast Radius 和 Historical Trend 最可能缺），而不是先推倒重建。

**延伸问：AI 时代 dashboard 会不会消失。** 这题可以答但必须全程用未来时。核心判断：dashboard 从调查的前置条件变成调查的产物，而不是消失。给 agent 用的那一层需要的是结构化状态和因果关系，而不是把曲线截图再翻译回文字。有几个具体依据可以引：原始时间序列对 LLM 不友好，tokenizer 把每个数字切成 4 到 8 个 token；真实复杂图表理解基准上 GPT-4o 只有 47.1% 而人类 80.5%；加入服务依赖图后 RCA accuracy@1 从 14.44% 提升到 42.22% (src: 调研报告 §3.1、§3.2、§6.1)。**必须让步的部分**：有独立实验（ClickHouse）指出瓶颈是上下文和领域接地而非数据表示形式，所以正确的说法是状态表示层是必要条件而不是充分条件 (src: 调研报告 §3.4、§8.5)。

**归属边界**：五层模型、Saturation 选型规则、Trace 层退化方案是我的设计。已落地的三问准入和三步决策树是我在 oncall 实践里建的。**没有做过现有 dashboard 的逐层核对，没有 MTTR 数据。** tenant 维度的应用侧埋点是应用团队做的，讲多租户 Blast Radius 例子时要带上这条边界（与 S01、S02 同一条护栏）。「面向 AI 消费的 dashboard」这一块**完全没有实现**，annotation API 加部署标记是给人看的，不是语义层，讲的时候必须整段用「我认为下一步该做的方向是」。

**⚠️ 命名地雷**：我有两套都叫「五层」的模型。本故事的 dashboard 五层（SLA / Blast Radius / Saturation / Trace / Historical Trend）回答的是排障认知路径；告警治理五层（准入 / 判定 / 身份 / 投递 / 载荷）回答的是寻呼权限怎么分配 (src: `contexts/daily_records/2026-08-05_2350_alert-governance-first-principles.md`)。**同一段话里说串会被追着问，然后撞到告警治理 Phase 1 未落地那一块。** 如果面试官顺着问到告警治理，切回 S03 的口径。

**可复用到**：03_aiops（给 agent 用的状态表示层是这个方向的核心素材）、90_cross_cutting（「优秀的 dashboard 体现的是如何思考而不是监控了什么」是技术观类问题的好答案）、02 本方向的 S02（tenant 维度串起 Blast Radius 和 Saturation 两层）、S04（三步决策树的实战案例）。

---

## 附：本方向故事与题型的映射速查

| 题型 | 首选故事 | 备选 |
|---|---|---|
| 讲一个你主导的架构决策 | S01 | S02 |
| 讲一次高风险迁移 / 怎么不停服换核心组件 | S01 | S07 |
| 告警怎么设计 / 什么该 page | S02 | S03 |
| 怎么减少 alert fatigue | S03 | S02 |
| 讲一个你发现并推动解决的问题（行为面） | S03 | S08 |
| 讲一次最难的排查 | S05 | S04 |
| 延迟问题怎么定位到层 | S04 | S05 |
| 怎么建立因果而不只是相关 | S05 | S10 |
| 怎么判断告警是真的 | S09 | S04 |
| metrics / logs / trace 怎么分工 | S06 | S09 |
| 讲一次你自己犯的错 | S06（LogQL 400 吞错误） | S10（初判反转） |
| 你怎么用数据支撑不可逆决策 | S07 | S01（双写门禁） |
| 你凭什么是 senior / 技术观 | S08 | S03 |
| SLO 怎么落地（含诚实边界） | S08 | S02 |
| 多租户怎么做隔离 | S02 | S06 |
| 监控成本怎么控 | S06 | S01 |
| dashboard 怎么设计 / 第一步看哪个 | S11 | S02 |
| AI 进入运维你怎么看 | S11（延伸问） | S03 |
