# Dashboard 设计哲学：从 Golden Signals 到因果驱动的故障定位路径

- 日期：2026-08-06
- 类型：讨论 review + 方法论
- 来源：与 Claude 关于 Four Golden Signals / Saturation / Dashboard 设计的讨论，含两轮外部 reviewer 反馈整合
- 关联：`rules/skills/bestpractice_sre_reliability_models.md`（lambda/mu 排队模型、SLI 四层拆分）、`rules/skills/workflow_dv_monitoring_oncall.md`、`contexts/memory/project_alert_governance_datavisor.md`、`contexts/memory/project_senior_sre_interview_prep.md`

---

## Part 1 — Summary：讨论走了三轮

第一轮：把 Four Golden Signals 从「背下来的四个词」拆成两层因果结构——Latency/Traffic/Errors 是用户感知的结果指标，Saturation 是系统内部的能力指标，中间由 headroom 耗尽 → 排队 → 延迟上升 → 超时 → 错误 这条链条串起来。

第二轮：把这个因果结构落到 dashboard 设计上，提出三层（SLA / 三剑客分解 / Saturation drill-down）加一个正交轴（业务侧 vs infra 侧），以及「dashboard 要不要为 AI 消费而设计」这个问题。

第三轮（本次要吸收的内容）：把三层扩成五层故障定位路径，补上了两个此前缺失的环节——Blast Radius（影响范围判定）和 Historical Trend（趋势对 AI 推理的价值），并且给 Saturation 层的指标选型给出了具体规则。

---

## Part 2 — 核心模型：五层故障定位路径

整个 dashboard 不是面板的集合，是一条 troubleshooting path，每一层只回答一个问题，回答不了就不该属于这一层。

**第一层 SLA / Golden Signals：用户有没有受影响。** Panel 数量刻意做少：p99 latency、QPS、success rate。这一层全绿时的正确动作是停止往下看，不是习惯性地把资源面板也扫一遍。「Don't debug healthy systems」值得作为一条显式的设计原则写进 dashboard 的使用规范，而不只是个人经验——它同时是「less is more」的执行标准和 alert fatigue 的预防手段：分层的意义不止是给面板归类，更是明确「什么时候可以不往下看」。

**第二层 Blast Radius：影响范围有多大。** 这是此前的讨论里缺失的一环。SLA 破了之后，下一步不是看 CPU，是看影响谁：哪个 region、哪个 API、哪个租户。这决定了这是单点问题还是全局问题，也决定了后续排查该往哪个方向切。对多租户 SaaS 场景，这一层的价值被低估了——见 Part 3。

**第三层 Saturation：为什么坏了，瓶颈在哪。** 这里的关键修正是指标选型规则：不是 Resource Usage Dashboard，是 Bottleneck Dashboard。选「是否开始等待」类指标，不选「用量」类指标——CPU Run Queue 不是 CPU Usage，Kafka Lag 不是 Kafka Message Count，DB Connection Wait 不是 Connection Count，GC Pause 不是 Heap Usage，Disk IO Wait 不是 Disk Usage。这条规则和此前提出的「headroom」概念是同一件事在指标选型层面的具体执行版本：headroom 是抽象定义（还有多少余量），「选等待类指标」是把这个定义翻译成「该在 dashboard 里放哪个 metric name」的可操作规则。

**第四层 Trace：请求卡在哪一跳。** Metrics 告诉你坏了，Trace 告诉你坏在哪个依赖节点。这一层是很多 dashboard 缺失的部分——只有聚合指标，没有 request flow 视图，导致「知道慢」和「知道哪一跳慢」之间有一个人肉排查的空隙。

**第五层 Historical Trend：是不是越来越坏。** 当前值和趋势提供的信息量不对等：CPU 95% 是一个静态事实，CPU 从 50%→60%→75%→95% 是一条可以外推的曲线。这一层对 AI 消费尤其重要，因为「持续上涨」这个模式比单点阈值更适合作为自动推理的前提条件——但这里需要一个修正，见 Part 3。

---

## Part 3 — Review：需要根据实际场景修正或补充的地方

**一，Trace 层默认假设了完整的分布式追踪覆盖，这个假设在很多真实栈里不成立。** 这一层的论述隐含前提是系统已经有 Jaeger/Tempo 级别的 tracing 基础设施，调用链每一跳的耗时都能拆出来。如果现有可观测性栈是 Loki + VictoriaMetrics + Grafana 这类组合（没有强制打通分布式 tracing），这一层需要退化成替代方案：靠 request_id/trace_id 做跨服务的 log correlation，在 Loki 里按同一个 request_id 拉出跨服务的日志序列，人工或者用 LogQL 拼出耗时分布。这个退化方案精度更低（拿不到精确的 span 耗时，只能拿到日志时间戳的粗略间隔），但在没有 tracing 基建的团队里，这才是能落地的版本。设计 dashboard 之前要先确认这一层的基础设施前提是否成立，不能照抄模型就假设它存在。

**二，Blast Radius 层对多租户 SaaS 系统的价值被低估了，这一层理应是四层里最贴近 DataVisor 场景的一层。** 反欺诈这类多租户系统，故障的影响范围判定几乎等价于「是某个租户自己的数据/流量模式导致的，还是平台级的问题」——这个判断直接决定后续动作是找那个租户沟通还是拉全员排查。这一层如果做得好,可以直接复用同一套 tenant 维度标签体系用在 Blast Radius 和 Saturation 两层(某个租户的异常查询把连接池打满,是先在 Blast Radius 层看到"只有租户 A 受影响",再在 Saturation 层看到"DB connection wait 在租户 A 的 workload 上出现堆积"),两层用同一个 tenant_id 维度串起来,而不是各自独立的标签体系。

**三，Historical Trend 层「趋势比当前值更重要」这个判断是对的,但缺一个前提:趋势需要配基线,不能只看斜率。** 单纯的斜率上升在多租户系统里会有大量假阳性——某个租户的自然流量增长(业务在扩张、新客户上线)也会表现为同样的上升曲线,和真正的资源枯竭前兆在形状上区分不开。需要给每个组件/每个租户建历史基线(比如同比上周同时段、或者过去 N 天的分布),用"偏离基线多少倍"而不是"斜率是否为正"来判断,这一点接的是此前 SLO 笔记里"用 fingerprint 相对自身历史基线的劣化倍数"的同一个原则,在这里是同一套方法论的复用。

**四,AI Dashboard 部分,两轮讨论的表述可以合并成一个更完整的论述。** 第二轮讲的是"面板要带语义标签+和告警绑定+归一化的 headroom score",第三轮讲的是"面板的排列顺序本身编码因果链,AI 沿着链条推理"。这两者不是竞争关系,是同一个目标的两个必要条件:因果链的编码解决的是"AI 应该往哪个方向推理"(结构),语义标签和归一化指标解决的是"AI 在每一步读到的是不是可比较、可运算的数字"(内容)。只有结构没有干净的语义层,AI 知道该往哪看但读不懂看到的是什么;只有语义标签没有因果结构,AI 能读懂每个数字但不知道该把哪两个数字联系起来做推理。两者合起来才是把 dashboard 从"给人看的可视化"升级成"给 agent 用的结构化决策图"的完整方案。

---

## Part 4 — 可以对外表述的版本(面试/写作素材)

核心论点:一个优秀 dashboard 体现的不是监控了什么(What),是如何思考(How to Think)。Dashboard 不是 metrics 的集合,是一个逐层缩小故障范围的认知模型,每一层对应 oncall 时按时间顺序会问的一个具体问题——用户是否受影响、影响范围有多大、系统哪个能力接近极限、请求卡在哪一跳、趋势是不是在恶化。这五个问题排好序,面板的组织方式就该跟着这条因果链走,而不是按组件类型(把所有 CPU 面板放一起,所有 DB 面板放一起)分类摆放。

延伸论点,AI 时代的差异化:传统 dashboard 的目标是让人找到问题,面向 agent 消费的 dashboard 需要让机器沿着因果关系自动推理——这要求 panel 的组织方式本身编码因果链,并且每个面板携带可运算的语义(选等待类指标而不是用量类指标、按 tenant/component 维度打统一标签、和告警规则显式绑定),而不是停留在给人看的可视化层面。

措辞上的边界,对齐 `contexts/memory/project_alert_governance_datavisor.md` 里已经踩过的教训:这是一套设计原则和思考框架,不是已经落地并测过 MTTR 改善数据的既成事实。表述用"设计这套分层模型的原因是……"、"这条原则的取舍是……",不要用"降低了 MTTR X%"这类需要 before/after 数据支撑的句式,除非真的拿到了数据。

---

## Part 5 — 如果要落地到 DataVisor 现有 dashboard,下一步怎么核对

对着现有 Grafana dashboard 逐层检查缺口,而不是推倒重建:

第一步,盘点现有面板分别落在五层里的哪一层,标出完全缺失的层——大概率 Blast Radius(按 tenant 拆分的视图)和 Historical Trend(基线对比而非纯当前值)是两个最可能缺失的层。

第二步,检查 Saturation 层现有面板的指标选型,把"用量类"指标换成或补充上"等待类"指标——尤其是 DB connection wait、Kafka consumer lag 这两个,是否已经作为一等指标呈现,还是只有连接数和 message count。

第三步,确认 Trace 层的现实基础设施状况:是否有分布式 tracing 覆盖,如果没有,明确落地的是 request_id log correlation 这个退化方案,不要设计一个依赖不存在的基础设施的面板。

第四步,如果要往"AI 可消费"方向做,先从最小可行的一步开始:给现有面板的 dashboard JSON model 加语义标签(signal_type / layer / component / tenant),不需要一次做完因果链编码和 headroom score 归一化,标签是后续两者的前提。
