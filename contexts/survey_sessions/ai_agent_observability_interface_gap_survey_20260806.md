# AI Agent 与传统监控系统的接口鸿沟

调研日期：2026-08-06
调研方法：5 个并行调研维度（刻意保留重叠）+ 1 轮针对性矛盾核查
输出定位：可留存、可追溯的事实基础，用于后续写作、dashboard 设计与技术选型

---

## 0. 调研问题与边界

本次调研围绕三个递进的问题展开。

第一，Four Golden Signals 中的 Saturation 究竟是什么，它和 Latency / Traffic / Errors 是并列关系还是层次关系，「每个组件都是一个有限容量的 Service Center」这个抽象在理论上站不站得住。

第二，当 AI agent 成为监控数据的消费者，它适合读什么形态的数据。原始时间序列、dashboard 截图、结构化状态对象，三者的实证效果差距有多大。

第三，Prometheus 的查询语言没问题而展示层有问题这个判断是否成立。如果 Grafana 这套面向人眼的可视化不再是正确的抽象，替代物是什么。

**明确排除的范围**：本报告不涉及 LLM Observability，即监控 LLM 应用本身（LangSmith、Langfuse、Arize、token 追踪、prompt tracing）。搜索这个主题时该类内容占比极高但与本题无关。本报告讨论的是反方向：让 AI 去读你的监控。

---

## 1. 核心结论

**结论一：Saturation 的术语混乱有明确的历史根源，两位权威给出的定义互不兼容。** Google SRE Book 的定义里完全没有出现 queue 这个词，讲的是「how full」和「utilization target」。Brendan Gregg 的 USE 方法则严格把 saturation 定义为「排不进去、被迫排队的那部分多余工作」，并把「资源忙的时间占比」单独叫 utilization。同一个词指两件事。任何关于 saturation 的讨论如果不先声明用的是哪一支定义，都会滑向鸡同鸭讲。

**结论二：「每个组件是一个有限容量的 Service Center，系统是它们组成的网络」不是比喻，是排队论的标准模型。** service center 是教科书术语，网络形态叫 queueing network / Jackson network，有 product-form 解。这个抽象可以直接当理论基石使用。

**结论三：把原始时间序列直接喂给 LLM 在实证上是低效且不可靠的，这一点证据充分。** 数字被 tokenizer 切成每个 4 到 8 个 token；专门的基准测试显示 SOTA 模型在「读一串数值找最大值」这类任务上仍会出错。截图路线同样不乐观：真实复杂图表理解基准 CharXiv 上 GPT-4o 只有 47.1%，人类 80.5%。

**结论四：目前主流 MCP server 全部原样返回查询结果，特征提取层在工程上基本是空白。** Grafana、VictoriaMetrics、Datadog 的 MCP 都是把 PromQL 结果直接交给 LLM。做了转换的只有少数例外（k8sgpt 先规则化分析、HolmesGPT 明确做 LLM-friendly 转换）。这一层存在真实的空位。

**结论五：但「预先压缩成状态对象」这条路有一个已被验证的失败模式，需要精确区分。** Datadog 公开复盘了 fan-in 摘要架构的失败。关键在于失败的是「把多个 tool call 的原始响应一起塞进摘要 prompt」这种有损压缩，而不是「对单个指标做特征提取」。这两件事必须分开评价。

**结论六：结构化的拓扑与因果信息带来的提升是本次调研中最硬的正面证据。** GALA 的 ablation 显示加入服务依赖图后 accuracy@1 从 14.44% 升到 42.22%。Praxis 报告准确率提升最高 6.3 倍同时 token 消耗降低 5.3 倍。准确率与成本同时改善。

**结论七：业界最成熟的因果产品都不让 LLM 推因果。** Causely 和 Dynatrace 的架构都是确定性拓扑图先做因果推断，LLM 只负责自然语言表达。这与「把因果链喂给 LLM 让它推理」是不同的路线。

**结论八：「查询层没问题」这个判断需要修正。** text-to-PromQL 的首个基准研究显示，即便配合知识图谱描述系统上下文，GPT-4 生成 PromQL 的准确率也只有 69.1%，最大失败类别是标签用错。查询语言的表达力没问题，agent 缺的是标签语义和拓扑上下文。

---

## 2. 理论根基：Saturation 到底在说什么

### 2.1 两个权威，两个定义

Google SRE Book 第六章 Monitoring Distributed Systems 的原文（[sre.google](https://sre.google/sre-book/monitoring-distributed-systems)）：

> "Saturation: How 'full' your service is. A measure of your system fraction, emphasizing the resources that are most constrained (e.g., in a memory-constrained system, show memory; in an I/O-constrained system, show I/O). Note that many systems degrade in performance before they achieve 100% utilization, so having a utilization target is essential."

注意这段话里没有 queue。它讲的是「有多满」，讲的是「很多系统在到 100% 利用率之前性能就开始劣化，所以必须设利用率目标」。这正是 headroom 的语义。

Brendan Gregg 的 USE Method（[brendangregg.com](https://www.brendangregg.com/usemethod.html)）：

> "utilization: the average time that the resource was busy servicing work; saturation: the degree to which the resource has extra work which it can't service, often queued; errors: the count of error events"

> "Saturation: any degree of saturation can be a problem (non-zero). This may be measured as the length of a wait queue, or time spent waiting on the queue."

Gregg 明确把 saturation 定位为排队本身，并且把「资源忙碌的时间占比」单独命名为 utilization。按他的术语体系，CPU 跑到 95% 是 utilization 高、saturation 仍为零。他之所以要把 U 和 S 拆开，恰恰是为了捕捉「资源很忙但还没开始排队」这个中间状态。

**这是本报告在理论部分最重要的发现**：谈论「CPU 95% 但还没排队，headroom 已经耗尽」这个观察时，Google 的术语体系会把它叫 saturation，Gregg 的术语体系会把它叫 utilization 接近上限。观察是同一个，命名相反。讨论时应当显式声明采用哪一支。

### 2.2 Four Golden Signals 是不是两个层次

Google 没有在书里明说「前三个是 outcome、第四个是 capacity」，但书中有两处论述在结构上支持这个划分。

一是 symptom / cause 的二分。书中 Table 6-1 给的例子是 Symptom 为「I'm serving HTTP 500s」，Cause 为「Database servers are refusing connections」。同章结论段：

> "A healthy monitoring and alerting pipeline...focuses primarily on symptoms for paging, reserving cause-oriented heuristics to serve as aids to debugging problems. Monitoring symptoms is easier the further 'up' your stack you monitor, though monitoring saturation and performance of subsystems...often must be performed directly on the subsystem itself."

二是这段话本身指出 saturation 在**测量方式上**与另外三个信号本质不同：它必须直接在子系统上测，无法从服务边界观察得到。这是一个层次差异的实质性证据。

判定：**部分印证**。分层直觉与 Google 的框架结构一致，但 Google 本人没有明说，引用时应表述为「Google 的 symptom/cause 框架支持这样理解」而非「Google 把四信号分成两层」。

### 2.3 RED 为什么没有 Saturation

一个值得澄清的小细节。不少二手博客把 RED 方法缺少 saturation 解释为设计哲学（说 per-service saturation 不好泛化）。Tom Wilkie 本人的说法（[YouTube](https://www.youtube.com/watch?v=TJLpYXbnfQ4)）是：

> "if you're familiar with Google's four golden signals it includes saturation and when I came up with this I forgot about that one"

就是忘了。不宜过度解读为「设计者认为 saturation 不重要」。

### 2.4 排队论提供的形式化支撑

**Little's Law**（[Wikipedia](https://en.wikipedia.org/wiki/Little%27s_law)）：`L = λW`，稳态系统中的平均排队数等于到达率乘以平均停留时间。这是「排队 → 等待时间」这一环的基础工具。

**M/M/1 的响应时间公式**（[UW-Madison CS547 讲义](https://pages.cs.wisc.edu/~dsmyers/cs547/lecture_12_mm1_queue.pdf)）：

> "R = s/(1-U)...Residence time increases very rapidly at utilizations beyond 80%...In practice, 70% utilization is considered a good operating level."

这条公式解释了为什么容量劣化不是线性的：QPS 100 时毫无等待、500 时开始等待、1000 时崩溃，这个形态来自 `1/(1-U)` 在 U 趋近 1 时的发散。

但需要一处降调。CMG 的文章 [Does the Knee](https://www.cmg.org/2023/06/does-the-knee) 指出，70% 这个数字**没有严格统一的数学推导**，业界对 knee 的定义从 67% 到 90% 都有。安全的表述是「拐点存在且非线性」，不宜写成「拐点在 70%」。

**Universal Scalability Law**（Neil Gunther）：`C(N) = N/[1+α(N-1)+βN(N-1)]`，其中 α 为 contention 系数、β 为 coherency 系数。它为「资源竞争」在因果链中的位置提供了形式化。

**Queueing Network / Service Center**：这是对「每个组件都是有限容量 Service Center」这一抽象的直接印证。DTIC 学术文档（[ADA081257](https://apps.dtic.mil/sti/tr/pdf/ADA081257.pdf)）直接使用该术语：

> "define: W_ni − the total time unit n spends waiting in service center i...There are I ≤ M service centers...These M servers are arbitrarily connected by arcs"

[Jackson network](https://en.wikipedia.org/wiki/Jackson_network) 是这类模型的标准形态：多个互联队列节点、外部到达、内部路由、product-form 解。结论是这个抽象属于教科书内容，可以直接作为理论基石引用。

**Headroom 的正式定义**：ICPE 的 CapPredictor 论文（[PDF](https://cloudintelligenceworkshop.org/2020/content/CapPredictor.pdf)）：

> "we measure the capacity of a stateful service by its headroom, the percentage increase in workload a service could hold while satisfying its Service Level Objective (SLO)...H_Xi = max(x_i|y<SLO) − x_0)/x_0"

这个定义的关键特征是它绑定 SLO 而非绑定资源利用率。这正好接上「capacity metric 服务于 outcome metric」的层次关系。

### 2.5 高利用率本身不是问题

Google SRE Book 引言章（[sre.google](https://sre.google/sre-book/introduction)）：

> "Efficient use of resources is important any time a service cares about money...paying close attention to the provisioning strategy for a service, and therefore its utilization, provides a very, very big lever on the service's total costs."

这一条补强了区分 utilization 与 headroom 的必要性：高利用率是成本效率的目标，不能简单等同于风险信号。判断风险需要独立的 headroom 或排队指标。

### 2.6 Saturation 在实践中最难测

多个来源指向同一结论。invgate 的总结（[blog.invgate.com](https://blog.invgate.com/sre-signals)）：

> "There's no universal way to measure saturation; it's challenging because the type of application you're running affects the saturation metrics."

配合 Google「必须直接测子系统本身」的论述，可以确认 saturation 是四信号中最难标准化、最容易在实践中被忽略的一个。这个事实对 dashboard 设计有直接含义：saturation 层的 panel 必然是按组件类型定制的，无法像 SLO 层那样统一模板化。

### 2.7 四信号的适用边界

对非请求驱动的系统，四信号需要调整。novaaiops 的表述（[novaaiops.com](https://novaaiops.com/golden-signals)）指出 batch job、数据管道、事件流系统需要 queue depth、lag、freshness 这类替代信号。Dynatrace 的知识库（[dynatrace.com](https://www.dynatrace.com/knowledge-base/golden-signals)）也列出了分布式系统中的复杂性局限。

---

## 3. Agent 消费监控数据的实证边界

### 3.1 原始数字序列

**Token 效率**。arXiv 2510.01111（[HTML](https://arxiv.org/html/2510.01111v1)）给出具体数字：

> "current LLMs split numbers into multiple small tokens... with each number using four to eight tokens including delimiters"

按每个数字 4 到 8 个 token 计算，一个 1 小时、15 秒采样间隔的 panel 是 240 个点，仅数值本身就是 1000 到 2000 token。一个 20 panel 的 dashboard 轻易超过 30000 token。

**准确性**。INLG 2025 的专门基准《Evaluating LLMs' Ability to Understand Numerical Time Series》（[ACL Anthology](https://aclanthology.org/2025.inlg-main.16.pdf)）：

> "even state-of-the-art LLMs still struggle with multi-step reasoning, lose accuracy when the calculation must stay within a specific range... models... fails to identify the maximum value accurately"

「找出峰值在哪」正是读监控图时最基础的操作。

**机制层面的解释**。PMC 论文《The first step is the hardest: pitfalls of representing and tokenizing temporal data for LLMs》（[PMC11339515](https://pmc.ncbi.nlm.nih.gov/articles/PMC11339515)）：

> "The tokenizers employed by LLMs appear to stumble when grappling with numerical inputs... repetitive patterns, an inherent characteristic of time-series data, can confound tokenizers, leading to the unintentional fragmentation of continuous sequences into disjointed tokens."

时间序列的重复性模式恰好是 tokenizer 的弱项。这说明问题在表示层而非模型规模，扩大模型难以根治。

### 3.2 图像路线

**真实复杂图表**。CharXiv（NeurIPS 2024，[GitHub](https://github.com/princeton-nlp/CharXiv)）：

> "the strongest proprietary model (i.e., GPT-4o), which achieves 47.1% accuracy, and the strongest open-source model (i.e., InternVL Chat V1.5), which achieves 29.2%. All models lag far behind human performance of 80.5%"

同时该工作指出既有基准存在虚高（[NeurIPS poster](https://neurips.cc/virtual/2024/poster/97598)）：

> "a simple stress test with slightly different charts or questions deteriorates performance by up to 34.5%"

**简单模板化图表**。ChartQA 榜单（[llm-stats.com](https://llm-stats.com/benchmarks/chartqa)）上 Claude 3.5 Sonnet 达到 90.8%。

这两个数字之间的落差本身就是结论：图表理解能力高度依赖图表复杂度。Grafana 面板属于多曲线、log scale、带注释、多 panel 并置的类型，更接近 CharXiv 一端而非 ChartQA 一端。

**间接旁证**。Viaduct.ai 的工程博客（[viaduct.ai](https://www.viaduct.ai/blog/why-off-the-shelf-llms-dont-work-for-time-series-data)）：

> "adding visual input representations (e.g., converting time series data into images) can help LLMs perform slightly better in anomaly detection, this approach adds complexity and still doesn't provide the level of accuracy seen with models specifically built for time series."

**证据缺口需明确标注**：本次调研**没有找到**「LLM 读 Grafana 截图 vs 读同一数据的 JSON」的直接对照实验。上述图表基准只能作为间接类比，不应当作直接证据引用。

### 3.3 端到端 RCA 的真实成绩

这是判断整条路线成熟度最直接的证据。

| Benchmark | 设定 | 成绩 |
|---|---|---|
| OpenRCA（Microsoft, ICLR'25） | 335 个真实故障，64GB 多模态 telemetry | **11.34%**（RCA-agent 多 agent 系统） |
| ITBench（IBM, ICML 2025） | 102 个真实 IT 场景 | SRE **13.8%**、CISO 25.2%、FinOps **0%** |
| ITBench-AA（Artificial Analysis × IBM, 2026） | average precision at full recall | Claude Opus 4.7 **47%**，GPT-5.5 46%，`All frontier models score below 50%` |
| AIOpsLab（Microsoft, arXiv:2407.12165） | 48 个 DeathStarBench 故障 | Detection 最高 100%，Localization 46-62%，**RCA 仅 36-45%**，Mitigation 27-55% |
| RCACopilot（Microsoft, EuroSys'24, arXiv:2305.15778） | 微软内部一年真实 incident | micro F1 **0.766**（注：这是根因**分类**任务，比精确定位容易） |

AIOpsLab 的原文结论（[微软 PDF](https://www.microsoft.com/en-us/research/wp-content/uploads/2024/10/arxiv_AIOpsLab.pdf)）：

> "The RCA and mitigation tasks prove to be the most challenging for the agents."

这张表最值得注意的规律是**任务难度阶梯**：检测容易（最高 100%），定位中等，根因分析最难，缓解措施更难。这与直觉一致，但数字的绝对水平比多数人预期低得多。

ITBench-AA 还附带一句对整个 AI SRE 品类的观察，来自第三方评测方而非厂商：

> "No AI SRE vendor has submitted its own product to an independent third-party benchmark."

### 3.4 独立第三方的负面实验

ClickHouse 在 2025 年 8 月做了一个动机干净的实验（他们不销售 AI SRE 产品）。方法是往 OpenTelemetry demo 应用注入 4 个合成异常，让包括 GPT-5 在内的 4 个前沿模型仅凭 telemetry 找根因。

> "no model reliably identified causes without follow-up human guidance, and several fixated on a single early hypothesis even with full telemetry access"
> （[clickhouse.com/resources/engineering/ai-sre-agents](https://clickhouse.com/resources/engineering/ai-sre-agents)）

> "The bottleneck isn't model IQ; it's missing context, weak grounding, and no domain specialization... We also tried a newer frontier model (GPT-5). It didn't outperform the original contenders."
> （[clickhouse.com/blog/llm-observability-challenge](https://clickhouse.com/blog/llm-observability-challenge)）

**这条证据对「换个表示形式就能解决」的主张构成实质挑战**，需要正面回应。ClickHouse 的诊断是瓶颈在上下文、接地和领域专门化，而非数据的表示形式。两者并非完全对立（更好的表示确实提供更好的接地），但不能假定表示形式的改进能自动解决锚定偏差这类推理层面的失败。

同方向的一手证据来自 Anthropic 工程师 Alex Palcuie 在 QCon London 2026 的现场发言，经 Forbes 专栏（2026-05-04）转述：

> "AI is good at reading logs but poor at reasoning about system dependencies that are different in every organization... it repeatedly misattributed a KV cache failure to a capacity shortage, mistaking the symptom for the cause."
> （[forbes.com](https://www.forbes.com/councils/forbesbusinesscouncil/2026/05/04/what-the-industry-gets-wrong-about-building-an-ai-sre)）

同文引用 Catchpoint SRE Report 2026（418 名 SRE 受访）：中位 toil 为 34%，其中 49% 认为 toil 下降、35% 认为无变化、**16% 认为 AI 的引入反而增加了 toil**。

### 3.5 安全维度

arXiv 2508.06394《When AIOps Become "AI Oops": Subverting LLM-driven IT Operations via Telemetry Manipulation》（RSA Conference 2025，[HTML](https://arxiv.org/html/2508.06394v2)）展示了通过操纵遥测数据诱导 LLM 生成自信但完全错误的根因诊断。这一点与既有的 K8s 输出不可信原则一致：从集群读到的内容属于外部不可信输入。

---

## 4. 语义层 / 状态表示层：业界现状

### 4.1 MCP 层几乎是空白

逐个核实的结果一致：主流 observability MCP server 都是把查询结果原样交给 LLM，没有特征提取层。

**Grafana MCP**（[github.com/grafana/mcp-grafana](https://github.com/grafana/mcp-grafana)）：`query_prometheus` 接受 `expr`、`startTime`、`endTime`、`stepSeconds`，文档描述为 "Execute PromQL queries (supports both instant and range metric queries) against Prometheus datasources."

**VictoriaMetrics MCP**（[github.com/VictoriaMetrics/mcp-victoriametrics](https://github.com/VictoriaMetrics/mcp-victoriametrics)）：定位是暴露 "almost all read-only APIs of VictoriaMetrics"。

**Datadog MCP**：官方视频《Building the Datadog MCP Server》（2026-04-07，[YouTube](https://www.youtube.com/watch?v=5PzqNwOTMEc)）中工程师明确把 token 效率列为核心设计痛点：

> "LLMs have like a pretty limited context window and we need to be really careful with it. We need to be as efficient as possible, use up very few tokens because that'll help any agent out, any LLM really. So, context efficiency is a big deal"

厂商已经意识到问题，但没有公开说明已经实现了聚合层。

**两个例外**。k8sgpt 的做法是先用规则对 K8s 资源做状态机检测，把**结构化的分析结果**而非原始 metrics 交给 LLM 做自然语言解释（[squer.io](https://www.squer.io/blog/k8sgpt-essentials-unlocking-kubernetes-insights-with-ai)）。HolmesGPT 是唯一在文档中明确写出这一设计理念的项目（[holmesgpt.dev](https://holmesgpt.dev/dev/why-holmesgpt)）：

> "Holmes automatically transforms these raw endpoints to be LLM-friendly"

并允许通过 `llm_instructions` 字段人工标注该 API 的用法。

### 4.2 厂商侧已有的特征提取

**Datadog Watchdog RCA** 是字段结构最明确的商业产品之一（[docs.datadoghq.com/watchdog/rca](https://docs.datadoghq.com/watchdog/rca)）。它的输出有固定三组件：`root cause, critical failure, and impact`，且根因类型被限定为封闭集合（Version changes、Traffic increases、AWS instance failures、Running out of disk space 等）。Watchdog Alert 字段包含 `Root Cause / Team / Log Anomaly Type / Log Source / Log Status`。

**Grafana Sift** 是「自动检查 + 结构化发现」模式，各检查各自产出结构，**没有公开统一 schema**（[grafana.com/docs](https://grafana.com/docs/grafana-cloud/ai-tools/dynamic-alerting/sift/analyses)）。已确认的检查类型包括 Error Pattern Logs（"groups of similar log lines... highlighting groups with significantly increased log rates"）与 Kube Crashes（"Detects recent container crashes by analyzing Kubernetes metrics and provides information on the cause of the crash (Error, OOMKill)"）。HTTP Error Series 有明确的可配置阈值字段（Cut off time 默认 90 分钟、Threshold 为相对滚动平均的最小变化百分比）。

**Honeycomb BubbleUp** 做的是统计对比式特征提取（[Medium](https://medium.com/honeycombio/bubbleup-meets-tracing-and-other-odd-shaped-data-honeycomb-5863022c1410)）：

> "takes each and every dimension in your data and compares its distribution between the selected points and the rest of your dataset"

值得注意的是它提取的是**维度分布差异**（哪个维度值在异常子集里过度出现），而非时序特征（trend / slope / forecast）。这两类特征是正交的，一个完整的状态表示层需要同时具备。

**Dynatrace Davis** 的 Analyzer API 确实提供正式 JSON Schema 能力（[developer.dynatrace.com](https://developer.dynatrace.com/develop/sdks/client-davis-analyzers)）：

> "The JSON schema defines a standardized declaration of the output structure"

但这是分析器框架的元 schema，而非某个固定的「系统状态对象」。

**Chronosphere** 的 DDx 与 Lens 基于 Temporal Knowledge Graph，2025 年 11 月发布 AI-Guided Troubleshooting（[chronosphere.io](https://chronosphere.io/learn/ai-in-observability)）：

> "Each suggestion shows its reasoning, the data it considered, and the alternatives it ruled out"

**Causely** 是理论最完整的一家，直接把问题定义为「给 LLM 原始遥测不够，需要预计算因果结构」。详见 4.3 的可信度评估。

### 4.3 Datadog 的反例，及其真实边界

这是本次调研中最需要精确处理的一条证据。原文经抓取核实，来自《How we built an AI SRE agent that investigates like a team of engineers》，作者 Daniel Shan 与 Tristan Ratchford，发布于 **2026-01-12**（[datadoghq.com](https://www.datadoghq.com/blog/building-bits-ai-sre)）。注意产品现名是 **Bits Investigation**，URL slug 沿用旧命名。

失败机制的原文：

> "Early SRE agents scaled by performing more tool calls across the platform and prompting an LLM to summarize the responses. This approach, however, proved to have a notable shortcoming: Increasing the number of tool calls caused the input token count for the summarization prompt to scale linearly. This meant incorporating additional telemetry data slowly degraded model performance or exceeded the context window limit."

具体失败案例：

> "An early version of Bits Investigation issued 12 tool calls across logs, traces, and metrics. One of the tool calls correctly pinpointed the root cause. But because other tool responses included suspicious signals like critical application errors in an upstream service, the summarization prompt returned an incorrect root cause."

新架构：

> "Formulate hypotheses about the root cause, Validate or reject hypotheses using data from targeted queries, Repeat this process until it reaches a root cause."

唯一披露的效果数字是 "Bits Investigation is already helping teams decrease time to resolution by up to 95."（MTTR 类指标）。文中提到用真实事故构建了 benchmark 数据集，但未披露准确率分数。

**边界澄清（关键）**：原文对失败机制的描述无歧义，Datadog 放弃的是 **fan-in 摘要**，即把多个 tool call 的原始响应一起塞进一个摘要 prompt。这与「对单个指标做特征提取」是完全不同的事。把这条证据用作「反对一切预处理」的论据属于误读。

它真正证明的命题更窄也更有价值：**压缩的时机如果早于 agent 确定要找什么，压缩就会丢掉决定性信息**。12 个 tool call 里已经有一个命中根因，摘要环节把它淹没了。

### 4.4 Causely 论文的可信度评估

arXiv 2605.18327，《Causely: A Causal Intelligence Layer for Enterprise AI — A Benchmark Study on SRE and Reliability Workflows》，提交于 2026-05-18。

核心主张（Section 3.2，原文核实）：

> "Causely improves diagnostic accuracy because it removes the need for Ops AI agents to reconstruct causal state from raw telemetry and instead provides direct access to pre-computed causal structure."

摘要报告的数字：诊断时间下降 63%、token 消耗下降 60%、tool call 数下降 78%、单次运行 API 成本下降 57%、根因诊断准确率从 75% 升至 100%。分 agent 看，token 降幅区间为 -53.7% 至 -71.7%（Table 5），tool-call 降幅为 -70.7% 至 -83.6%（Table 6）。部分 agent 准确率从 83% 到 100%，Claude Code 本就 100% 无变化。

**可信度必须打折**。五位作者（Dhairya Dalal、Endre Sara、Ben Yemini、Christine Miller、Shmuel Kliger）邮箱全部为 @causely.ai，无学术机构挂名，属**厂商自评基准**。实验规模为 24 微服务的 OpenTelemetry demo 应用（Astronomy Shop），2 个场景，4 种 agent 配置，共 72 次运行。样本量与场景真实度都有限。

### 4.5 Datadog 与 Causely 并不矛盾

经核查，这两条证据针对的是**不同的问题**，被「预处理」这个词绑在一起产生了表面冲突。

Datadog 失败的是有损压缩：把 N 个原始 tool 响应扁平化成一段摘要，信噪比下降、上下文线性膨胀。Causely 提供的是信息增益：额外的、预计算好的结构化因果层，让 agent 不必从原始 telemetry 重建因果状态。方向相反。

更根本的是架构层面的差异。Datadog 弃用的是「一次性 fan-in 摘要」；Causely 测试的四个 agent（Claude Code、Codex、HolmesGPT）本身就是迭代式按需查询架构，与 Datadog 的**新**架构同类型。Causely 只是给这些迭代 agent 多加了一个查因果拓扑的工具。

**这个辨析给出一条可操作的设计原则**：状态表示层应当作为 agent **可按需调用的工具**存在，而不是作为 agent 推理前的**强制预处理管道**。前者是信息增益，后者是过早压缩。

### 4.6 命名现状

**OpenTelemetry Semantic Conventions 与状态特征提取是两件事**，这一判断经调研确认成立。semconv 解决的是字段命名一致性（[uptrace.dev](https://uptrace.dev/opentelemetry/semconv)）：

> "Semantic conventions eliminate ambiguity in telemetry by defining: Attribute names... Attribute values... Required vs optional attributes"

它不涉及从时序推导 trend、baseline、severity。

数据领域在 2026 年已经开始区分 semantic layer 与 context layer（[datahub.com](https://datahub.com/blog/context-layer-components)）：

> "A semantic layer standardizes how metrics are calculated for consistent analytics. A context layer extends that foundation with the operational state, governance signals, and provenance an AI agent needs to reason and act reliably."

**可观测性领域没有对等的成熟命名**。各厂商各用各的名字：Sift、Davis、Watchdog、DDx、Lens。没有收敛到统一术语。这是一个真实的命名空位。

时序特征库（tsfresh、catch22、TSFEL）确实存在且在 AIOps 论文中被验证有效（arXiv 2501.07999，[HTML](https://arxiv.org/html/2501.07999v2)）：

> "TSFRESH... calculates up to 800 features (basic statistics, autocorrelations, entropy, Fourier coefficients, etc.)... for Isolation Forest, across 16 results... the proposed FE method always obtains the best mean rank"

但它们的输出是给分类器用的高维特征向量，不是给 LLM 用的语义状态。**未找到**把 tsfresh 输出直接接入 LLM prompt 的公开工程案例。

### 4.7 反面意见

Mezmo 明确指出摘要的信息损失风险：

> "truncation or summarization loses fidelity. In the end, critical anomalies may be dropped before the model even sees them."

（注：Mezmo 销售 context engineering 产品，该博客中的 90%+ 成本下降、27K vs 500K token 等数字为厂商自称，未经独立验证。）

---

## 5. 展示层之争

### 5.1 主张 dashboard 退场的一方

这一方声音密集且论证细致。

**Charity Majors**（Honeycomb CTO），[charity.wtf](https://charity.wtf/p/notes-on-the-perfidy-of-dashboards)：

> "every dashboard is a sunk cost / every dashboard is an answer to some long-forgotten question... Dashboards can be fairly effective at surfacing the causes of problems you've seen before... but they're all but useless for novel problems, your unknown-unknowns."

> "Nothing < Dashboards < a Queryable, Exploratory Interface"

需要注意她的立场比标题党更精确：她反对的是**静态**仪表盘，终点是「可查询、可探索」，而非「无界面」。

**Spiros Xanthos**（OpenTelemetry 联合创建者，前 Splunk Observability SVP，现 Resolve AI CEO），[LinkedIn](https://www.linkedin.com/posts/spiros_observability-dashboards-are-dead-their-activity-7330994187850481664-2cVi)：

> "Observability dashboards are dead. Their current abstraction level will be quickly outdated by modern cloud environments... Low-level agent AI that does the data scouting, only bringing back the data that matters."

**Andrew Lee**（NeuBird AI），[neubird.ai](https://neubird.ai/blog/telemetry-dashboards-are-obsolete)。这段话直接命中「展示层是为人眼设计的」这一论点：

> "Dashboard vendors know the model is breaking... their big AI innovation is to convert all of that visual data back into plain English sentences. It's like creating an elaborate art piece and then hiring someone to stand next to it and describe the intricacies. If you need a translator for your translator, the original medium has failed."

**Tudor Golubenco**（Xata），[xata.io](https://xata.io/blog/are-ai-agents-the-future-of-observability)：

> "The AI agent UI can display graphs and visualizations client-side, showing only what's relevant. That means you don't need to maintain dashboards as much, because the agent can create them on the fly."

**groundcover**（Max Levin），2026-04，[groundcover.com](https://www.groundcover.com/blog/agent-first-observability)。这条给出了最温和也可能最准确的表述：

> "Dashboards, monitors, and saved queries are still important, but they stop being the only entry points into the system... observability artifacts become outputs of investigation, not only prerequisites for starting one."

### 5.2 反方

**Martin Mao**（Chronosphere CEO，前 Uber 可观测性负责人），[YouTube](https://www.youtube.com/watch?v=p2RIYzdn4FM)：

> "there hasn't been like overnight magically all you need is an observability agent and that's it. You don't need dashboards or anything... we haven't found that to be the truth."

**Mirko Novakovic**（Dash0 CEO，Instana 创始人），[dash0.com](https://www.dash0.com/blog/beyond-observability)：

> "To be clear about what this is not: it is not a pivot away from observability... Beyond observability doesn't mean instead of it."

**唯一的直接实证对比**，GI 2026 会议论文（[PDF](https://cs.uwaterloo.ca/~dvogel/gi2026/papers/1054b.pdf)）：

> "the dashboard excelled in speed, precision, and lower cognitive demand, and the chatbot offered greater flexibility for exploratory and open-ended queries... several reported that repeatedly typing prompts was slower than using dashboard controls for routine tasks."

这条结论符合直觉但值得重视：**在已知问题的例行检查上，dashboard 在速度、精度和认知负荷上都胜过自然语言界面**。这与 Charity Majors 的观察互补（她说 dashboard 对已见过的问题有效、对 unknown-unknowns 无效）。两条合起来给出一个清晰的分工边界。

**Fred Hebert** 的态势感知类比（经 Charity 文章引用）：

> "I like to compare the dashboards to the big display in a hospital room... If all we have is the display but none of the rest, we're not getting anywhere close to an accurate picture."

### 5.3 Grafana 的立场：正面回避

Grafana **没有**公开承认 dashboard 对 agent 是错误的接口。官方叙事是「MCP 让 agent 帮你更快造 dashboard」，最终消费者仍是人。

GrafanaCON 2025（[grafana.com](https://grafana.com/events/grafanacon/2025/ai-agent-driven-grafana)）：

> "it generates a complete, multi-panel dashboard in your Grafana instance with a single command. In seconds, a dashboard appears, created from scratch with no manual effort."

GrafanaCON 2026 keynote（[YouTube](https://www.youtube.com/watch?v=UazoZQHW0kI)）：

> "the new Grafana schema... locks down the definition for a Grafana dashboard... in the agentic world, it's particularly important because that means that agents are going to be able to more easily build Grafana dashboards and then test and validate them using the schema."

考虑到 Grafana 是最大的既得利益方，这种回避本身是一个信号，但也应当承认它可能确实认为双通道是对的。

### 5.4 替代形态的提案

**MCP 作为新展示层**：唯一直接命中这一说法的是 Shahar Azulay（Quesma CEO）在 Dash0 播客中的一句话（[dash0.com](https://www.dash0.com/podcast/34-rethinking-observability-shahar-azulay)）：

> "If you look at the whole AI, SRE agent category, which is connecting to observability to provide value, in a sense, it could be that that becomes the new user interface and we become only a database."

这仅是一句非正式表述，**目前没有正式论文或白皮书系统论述这个主张**。

**Ephemeral dashboards**：Oodle AI（[blog.oodle.ai](https://blog.oodle.ai/dashboards-are-dead)）：

> "Can Metric dashboards be ephemeral - created, used and discarded dynamically - just like logs and traces?"

**双通道的产品化落地**：Elastic 的 MCP Apps（[elastic.co](https://www.elastic.co/search-labs/blog/mcp-apps-elastic)）是目前最具体的实现：

> "A tool can now return an interactive UI alongside its text summary... The model keeps the compact text for reasoning. The human gets a live, clickable interface right next to the chat."

这正是「agent 用文本推理、人看可视化」的工程形态。

### 5.5 查询层的隐藏问题

这一条**直接修正**了「查询层没问题、只有展示层有问题」的判断。

PromCopilot（arXiv 2503.03114，提交于 2025-03-05，[abs](https://arxiv.org/abs/2503.03114)）是首个 text-to-PromQL 研究，构建了 280 题的基准数据集。摘要原文：

> "PromCopilot first uses a knowledge graph to describe the complex context of a cloud native online service system... When using GPT-4 as the backbone LLM, PromCopilot achieves an accuracy of 69.1% in translating natural language questions to PromQL queries."

论文对错误原因的分析：

> "the causes of these errors included: incorrect use of labels, incorrect use of functions, calculation logic errors, syntax errors... Therefore, directly using LLMs to generate a PromQL query is likely to get the PromQL query which is syntactically correct, but with the wrong context information."

**这个数字的关键在于它的实验设定**：PromCopilot 已经用知识图谱描述了系统上下文，仍然只有 69.1%，且最大失败类别是标签用错（76 例中 22 例）。

由此得出的修正结论：查询**语言**的表达力对 agent 是够用的，PromQL 本身没有问题。有问题的是查询**接口**：agent 缺少标签语义、指标含义和拓扑上下文，因此写不对查询。这个缺口与展示层的缺口是同源的，都属于「系统的语义没有被表示出来，只有原始数据被暴露出来」。

阿里云的工程实践博客也印证了类似问题，其解法是预跑加自我修复（[alibabacloud.com](https://www.alibabacloud.com/blog/dont-understand-promql-ai-agents-help-you-with-large-scale-metric-data-analysis_602420)）。

---

## 6. 因果与预测

### 6.1 拓扑信息带来的提升：本次调研最硬的正面证据

**GALA**（arXiv:2508.12472，2025）做了最干净的 ablation，在 RCAEval 基准上加入 service dependency graph：

> "our SURE-Score evaluation framework reveals... accuracy@1 reaching 42.22% compared to 14.44% for the baseline"

从 14.44% 到 42.22%，接近三倍。

**Praxis**（arXiv:2512.22113，2026）同时加入 service dependency graph 与 program dependence graph：

> "Praxis improves RCA accuracy by up to 6.3× while reducing token consumption by 5.3×"

准确率与 token 消耗同时改善，这是「压缩但不丢信息」最直接的实证。

**TopoEvo**（arXiv:2605.15611）给出了一个精准的术语描述失败模式：**symptom-amplification bias**。不带拓扑的 LLM 倾向于把下游被波及的服务误判为根因，因为下游的症状信号最强烈。

这个术语与 3.4 中 Anthropic 工程师描述的「把 KV cache 故障误判成容量不足」是同一个失败模式，也与 Google SRE Book 的 symptom / cause 二分直接对应。**它同时解释了为什么 saturation 层的可观测性对 agent 尤其重要**：链条末端的 error 信号最强，agent 天然会锚定在那里，除非有结构化信息告诉它链条的上游在哪。

**Dynatrace 自报数字**（Perform 2026，经 [diginomica](https://diginomica.com) 转述），确定性拓扑优先对比 LLM-only：

> "Benchmark results show 12 times higher success rates, three times faster resolution, and half the token costs compared to LLM-only approaches."

厂商自测，但方向与前两条学术 ablation 一致。

### 6.2 业界做因果的实际架构：deterministic first, LLM last

这一发现对「把因果链喂给 LLM 让它推理」的构想构成实质修正。

**Causely**（[causely.ai](https://causely.ai)）：

> "Causely creates a deterministic model of how services interact... LLMs do come into the picture, but only after the causal model has already identified the issue... The heavy lifting — the understanding — remains deterministic."

**Dynatrace Davis + Smartscape**（经 [techtarget](https://www.techtarget.com) 转述）：

> "Dynatrace's causal AI (Davis) is a reasoning engine that traverses the topology map (Smartscape) to establish causality... in a deterministic manner... not simply based on statistical correlations."

Davis 被称为 hypermodal：causal AI（确定性）+ predictive AI + generative AI（LLM 仅做自然语言层）。

**证据缺口**：未找到 Netflix、Uber、LinkedIn 公开的自动化因果图 RCA 系统。Netflix 的 Computational Causal Inference 团队做的是产品实验与用户行为分析，不是故障 RCA，不应张冠李戴。

### 6.3 LLM 的原生因果能力

严肃文献一致指向能力有限。

《LLM Cannot Discover Causality...》（arXiv:2506.00844，2025）：

> "LLMs' autoregressive, correlation-driven modeling inherently lacks the theoretical grounding for causal reasoning... deliberate prompt engineering... could overstate their performance."

《Unveiling Causal Reasoning in LLMs》（NeurIPS 2024）：

> "current LLMs are limited to level-1 causal reasoning... primarily attributed to the causal knowledge embedded in their parameters, but they lack the capacity for genuine human-like (level-2) causal reasoning."

「causal parrots」这一批评（经 IJCAI 2025 survey 引用）：

> "LLMs may function more as pattern-matching systems reciting embedded knowledge rather than understanding true causality... 'causal parrots' without deeper understanding."

这些论文合起来支持一个结论：**因果图应当作为确定性组件提供给 agent，而不是期待 agent 从数据中推出因果**。

### 6.4 预测能力的现状

`predict_linear` 是 Prometheus 生态中最常用的容量预测手段，2015 年起已用于磁盘容量告警（[robustperception.io](https://www.robustperception.io)）：

> "The `predict_linear()` function in Prometheus allows you to... alert if the disk was going to fill up in 4 hours time."

已知口碑问题（[GitHub discussion 11705](https://github.com/prometheus/prometheus/discussions/11705)）：

> "I tried to use the Prometheus function `predict_linear`, but the end of the predicted data are always wrong and weird"

本质是线性外推对非线性增长与窗口语义容易误用，更多属于使用姿势问题而非函数缺陷。

**证据缺口**：Grafana ML forecasting 的独立评测未检索到。Dynatrace Predictive AI 的宣称未见独立验证。

### 6.5 失败模式的系统性分析

IBM 与 Berkeley 合作在 ITBench 上应用 MAST 失败分类（2026，[HuggingFace blog](https://huggingface.co/blog/ibm-research/itbenchandmast)）：

Verification 失败（FM-3.3）是最强的失败预测因子，Gemini-3-Flash 的失败 trace 中该模式高出 52%。Reasoning-Action Mismatch 出现在 Kimi-K2 失败案例的 92%、GPT-OSS-120B 的 94%。

ITBench-AA 还观察到一个反直觉现象：

> "Models that over-investigate tend to surface upstream fault-injection mechanisms or co-occurring symptoms as false positives."

调查越久误判越多。这对「让 agent 自由迭代查询直到收敛」这一架构提出了警告：迭代深度需要有界。

**基准自身的局限**，来自 Traversal 的评论（[traversal.com](https://www.traversal.com)）：

> "the hardest parts of RCA—causation, scale, and system structure—lie largely outside what benchmarks measure... Treating OpenRCA scores as a proxy for enterprise RCA capability conflates benchmark reasoning with system-level diagnosis."

---

## 7. 交叉验证：一致、矛盾、空白

### 7.1 多来源一致的高可信结论

以下结论有两个及以上独立来源支持，可信度高。

**原始时间序列不适合直接作为 LLM 输入**。来自 tokenization 机制分析（PMC）、专门的数值理解基准（INLG 2025）、token 膨胀测量（arXiv 2510.01111）三个独立角度。

**结构化拓扑信息显著提升 RCA 效果**。来自两篇学术 ablation（GALA、Praxis）加一份厂商基准（Dynatrace），方向完全一致。

**纯 LLM 在真实规模 telemetry 上的 RCA 能力低于多数人预期**。OpenRCA 11.34%、ITBench 13.8%、ITBench-AA 全部低于 50%、AIOpsLab RCA 子任务 36-45%，四个独立基准互相印证。ClickHouse 的独立实验从定性角度给出同样结论。

**症状被误判为根因是最典型的失败模式**。TopoEvo 命名为 symptom-amplification bias，Anthropic 工程师给出 KV cache 的具体案例，Google SRE Book 的 symptom/cause 框架早就预示了这个风险。三个来源、三种语境、同一个现象。

### 7.2 表面矛盾，经核查后化解

**Datadog 弃用摘要 vs Causely 主张预计算结构**。经原文核查确认两者针对不同问题：前者是 fan-in 有损压缩，后者是结构化信息增益；前者是一次性摘要架构，后者是给迭代 agent 增加工具。不构成矛盾。详见 4.5。

**Google 与 Gregg 对 saturation 的定义冲突**。这是真实存在的术语分歧，无法调和，只能显式声明采用哪一支。详见 2.1。

### 7.3 真实的证据缺口

以下问题本次调研**没有**找到可靠证据，任何相关论断都应标注为推测。

第一，**没有**「LLM 读 Grafana 截图 vs 读同一数据的结构化文本」的直接对照实验。图表理解基准只能作为间接类比。

第二，**没有**任何人正式论证「agent 也需要看图、vision 不可替代」。检索到的相关材料全部反向而行，即 agent 生成图给人看。这个论点目前在公开讨论中没有对手，但也意味着没有经过检验。

第三，**没有**正式论文或白皮书系统论述「MCP 是新展示层」，只有一句非正式播客表述。

第四，**没有**找到把时序特征库（tsfresh 等）输出直接接入 LLM prompt 的公开工程案例。

第五，Grafana 官方**从未**公开评价 dashboard 对 agent 是否是正确接口。

第六，Netflix / Uber / LinkedIn 的自动化因果 RCA 系统**没有**公开材料。

第七，Kubiya、Deductive AI、Wave Autoscale 等 AI SRE 产品的 metrics 到 LLM 架构细节只有营销页面，不足以作为证据。

---

## 8. 结论与建议

### 8.1 对 Saturation 论述的修正建议

理论部分整体成立，需要三处精修。

**术语声明前置**。在讨论 saturation 之前先声明采用 Google 的宽泛定义（how full / headroom）还是 Gregg 的严格定义（排队本身）。指出这两者不兼容，本身就是比复述定义更有说服力的内容。「CPU 95% 但还没排队」这个观察在 Google 体系里叫 saturation，在 Gregg 体系里叫 utilization 接近上限；观察相同，命名相反。

**Service Center 抽象可以直接升格为理论基石**。它不是类比，是排队论标准模型（Jackson network）。引用 service center 这个术语时可以明确说这是教科书术语。

**拐点数字降调**。`R = S/(1-U)` 的非线性发散是数学事实，但「拐点在 70-80%」是经验共识，CMG 指出业界定义从 67% 到 90% 不等。表述为「拐点存在」而非「拐点在 70%」。

另外，Headroom 已有绑定 SLO 的正式定义（CapPredictor），比自行定义更有分量，且它绑定 SLO 而非资源利用率这一点正好支撑「capacity metric 服务于 outcome metric」的层次关系。

### 8.2 对 Dashboard 设计的建议

调研支持分层设计，但对分层的依据可以更明确。

**已知问题与未知问题需要不同界面**，这是 GI 2026 实证研究与 Charity Majors 观察的交集。Dashboard 在例行检查上速度快、精度高、认知负荷低；面对 unknown-unknowns 则基本无效。因此 SLO 层与 Golden Signals 层适合固定 panel，saturation 层与下钻分析更适合可查询界面。

**Saturation 层必然无法模板化**。Google 明确指出 saturation 必须直接在子系统上测，多个来源确认它是四信号中最难标准化的。按组件类型（DB、Kafka、线程池、连接池）定制 panel 是必然结果，这不是设计缺陷。

**每个 panel 对应一个可判定的问题**这一原则在调研中没有找到直接对应的文献支撑，但它与 Charity Majors「every dashboard is an answer to some long-forgotten question」的批评正好互补：她批评的是问题被遗忘，而在 panel 上显式写出它回答的问题正是对这个批评的直接回应。这可以作为一个原创的设计主张提出。

### 8.3 对状态表示层构想的修正

构想方向获得支持，但实现路径需要三处调整。

**从预处理管道改为按需工具**。这是 Datadog 案例给出的最重要教训，也是化解 Datadog 与 Causely 表面矛盾的关键。状态表示层应当是 agent 可以调用的工具，而不是 agent 推理之前的强制压缩环节。原因在于压缩的时机如果早于 agent 确定要找什么，就会丢掉决定性信息。

**五类特征中 Relation 的定位需要改变**。Current / Change / Trend / Prediction 四类是对 agent 的信息供给，Relation 则应当是**替 agent 做掉推理**的确定性组件。Causely 与 Dynatrace 的架构一致证明了这一点，NeurIPS 2024 关于 LLM 只具备 level-1 因果推理的论文从反面支持同一结论。把因果图当作给 LLM 的推理材料，是在让它做它最不擅长的事。

**BubbleUp 式的维度特征需要补入**。Honeycomb 提取的是「哪个维度值在异常子集里过度出现」，与 trend / slope / forecast 这类时序特征正交。一个完整的状态表示层需要同时具备这两类。

**命名空位是真实的**。可观测性领域没有收敛出统一术语，各家各叫各的。数据领域已经开始区分 semantic layer 与 context layer，这个区分可以借鉴。State Representation Layer 这个命名在语义上比 Semantic Layer 更准确，因为它做的是状态表示而非语言翻译。

### 8.4 对「展示层该换掉」这一判断的修正

判断方向成立，但需要扩大范围。

**问题不止在展示层，查询接口有同等严重的缺口**。PromCopilot 的 69.1% 说明即便配备知识图谱，agent 写 PromQL 仍有三成失败，且主要失败在标签语义。更准确的表述是：Prometheus 暴露的是**原始数据与查询能力**，缺的是**系统语义**。展示层的问题（把语义编码成人眼可读的曲线）和查询层的问题（agent 不知道标签含义与拓扑）是同一个缺口的两面。

**最可能正确的落点是双通道，而非替换**。groundcover 的表述最接近调研支持的结论：dashboard 从调查的**前置条件**变成调查的**产物**。Elastic 的 MCP Apps 给出了工程形态：模型拿紧凑文本推理，人拿交互界面查看。Chronosphere CEO 的反驳（实践中还没验证 agent 单独够用）目前没有被任何实证推翻。

**「image → text 只说对了一半」这个判断在公开讨论中没有对手**。没有任何人正式论证过 vision 读图对 agent 不可替代。NeuBird 的那句 `If you need a translator for your translator, the original medium has failed` 是目前对这一论点最精炼的公开表述。这意味着这个方向有原创空间，但也意味着它未经检验。

### 8.5 需要正面回应的最强反驳

ClickHouse 的独立实验结论是 `The bottleneck isn't model IQ; it's missing context, weak grounding, and no domain specialization`。它指向上下文与领域接地，而非数据的表示形式。

这不是致命反驳，但必须处理。可用的回应路径是：表示形式与接地并非对立，结构化的状态表示恰恰是提供接地的手段之一，GALA 从 14.44% 到 42.22% 的提升就是接地带来的。但同时必须承认，表示形式的改进无法解决锚定偏差、verification 失败、over-investigation 这类推理层面的问题，ITBench 的 MAST 失败分析已经把这些量化了。

诚实的立场是：**状态表示层是必要条件而非充分条件**。

---

## 附录 A：证据可信度分级

**A 级（学术同行评审 / 独立第三方实验 / 一手原文核实）**
Google SRE Book、Brendan Gregg USE Method、Tom Wilkie 本人表述、排队论标准文献、CapPredictor（ICPE）、CharXiv（NeurIPS 2024）、INLG 2025 数值时序基准、OpenRCA（ICLR'25）、AIOpsLab、ITBench（ICML 2025）、ITBench-AA（Artificial Analysis 独立评测）、RCACopilot（EuroSys'24）、GALA、Praxis、PromCopilot（arXiv 2503.03114，已抓取原文核实）、NeurIPS 2024 因果推理论文、ClickHouse 独立实验、GI 2026 dashboard vs chatbot 研究、Datadog Bits Investigation 博客（已抓取 HTML 核实）。

**B 级（厂商官方技术文档 / 具名从业者公开表述）**
Grafana MCP / Sift 文档、Datadog MCP 视频、VictoriaMetrics MCP、HolmesGPT 文档、Datadog Watchdog RCA 文档、Honeycomb BubbleUp、Dynatrace Davis Analyzer 文档、Charity Majors、Spiros Xanthos、Martin Mao、Mirko Novakovic、Shahar Azulay、Andrew Lee、Tudor Golubenco、Alex Palcuie（经 Forbes 转述）、Catchpoint SRE Report 2026。

**C 级（厂商自评基准 / 营销内容，方向可参考，数字需打折）**
Causely arXiv 2605.18327（全部作者 @causely.ai，72 次 run）、Dynatrace Perform 2026 自报数字、Mezmo context engineering 博客、Traversal 的 DigitalOcean 案例数字、各 AI SRE 厂商产品页。

**D 级（未能核实 / 存疑）**
RCAgent 与 mABC 的精确准确率数字（论文存在，数字未核实到）、ITBench 不同版本间的数字差异（ICML poster 版与 blog 版不一致）、上一代 AIOps 失败教训的学术复盘（多为厂商内容）。

---

## 附录 B：主要来源清单

**理论根基**
- https://sre.google/sre-book/monitoring-distributed-systems
- https://sre.google/sre-book/introduction
- https://www.brendangregg.com/usemethod.html
- https://www.youtube.com/watch?v=TJLpYXbnfQ4 （Tom Wilkie RED）
- https://en.wikipedia.org/wiki/Little%27s_law
- https://pages.cs.wisc.edu/~dsmyers/cs547/lecture_12_mm1_queue.pdf
- https://www.cmg.org/2023/06/does-the-knee
- https://en.wikipedia.org/wiki/Jackson_network
- https://apps.dtic.mil/sti/tr/pdf/ADA081257.pdf
- https://cloudintelligenceworkshop.org/2020/content/CapPredictor.pdf
- https://tangowhisky37.github.io/PracticalPerformanceAnalyst/pages/spe_fundamentals/what_is_universal_scalability_law
- https://blog.invgate.com/sre-signals
- https://novaaiops.com/golden-signals
- https://www.dynatrace.com/knowledge-base/golden-signals

**LLM 读数据的能力边界**
- https://arxiv.org/html/2510.01111v1
- https://aclanthology.org/2025.inlg-main.16.pdf
- https://pmc.ncbi.nlm.nih.gov/articles/PMC11339515
- https://github.com/princeton-nlp/CharXiv
- https://neurips.cc/virtual/2024/poster/97598
- https://llm-stats.com/benchmarks/chartqa
- https://www.viaduct.ai/blog/why-off-the-shelf-llms-dont-work-for-time-series-data

**MCP 与工程实现**
- https://github.com/grafana/mcp-grafana
- https://github.com/VictoriaMetrics/mcp-victoriametrics
- https://www.youtube.com/watch?v=5PzqNwOTMEc （Building the Datadog MCP Server）
- https://holmesgpt.dev/dev/why-holmesgpt
- https://github.com/HolmesGPT/holmesgpt
- https://www.squer.io/blog/k8sgpt-essentials-unlocking-kubernetes-insights-with-ai
- https://www.elastic.co/search-labs/blog/mcp-apps-elastic

**厂商语义层实现**
- https://docs.datadoghq.com/watchdog/rca
- https://docs.datadoghq.com/watchdog/alerts
- https://grafana.com/docs/grafana-cloud/ai-tools/dynamic-alerting/sift/analyses
- https://grafana.com/docs/grafana-cloud/machine-learning/machine-learning/sift/analyses/http-error-series
- https://medium.com/honeycombio/bubbleup-meets-tracing-and-other-odd-shaped-data-honeycomb-5863022c1410
- https://developer.dynatrace.com/develop/sdks/client-davis-analyzers
- https://chronosphere.io/learn/ai-in-observability
- https://www.datadoghq.com/blog/building-bits-ai-sre
- https://arxiv.org/abs/2605.18327 （Causely，厂商自评）
- https://uptrace.dev/opentelemetry/semconv
- https://datahub.com/blog/context-layer-components
- https://arxiv.org/html/2501.07999v2 （tsfresh in AIOps）

**展示层之争**
- https://charity.wtf/p/notes-on-the-perfidy-of-dashboards
- https://www.honeycomb.io/blog/its-the-end-of-observability-as-we-know-it-and-i-feel-fine
- https://news.ycombinator.com/item?id=44243050
- https://xata.io/blog/are-ai-agents-the-future-of-observability
- https://www.linkedin.com/posts/spiros_observability-dashboards-are-dead-their-activity-7330994187850481664-2cVi
- https://neubird.ai/blog/telemetry-dashboards-are-obsolete
- https://www.groundcover.com/blog/agent-first-observability
- https://grafana.com/events/grafanacon/2025/ai-agent-driven-grafana
- https://www.youtube.com/watch?v=UazoZQHW0kI （GrafanaCON 2026 keynote）
- https://www.youtube.com/watch?v=p2RIYzdn4FM （Martin Mao）
- https://www.dash0.com/blog/beyond-observability
- https://www.dash0.com/podcast/34-rethinking-observability-shahar-azulay
- https://cs.uwaterloo.ca/~dvogel/gi2026/papers/1054b.pdf
- https://blog.oodle.ai/dashboards-are-dead

**查询层**
- https://arxiv.org/abs/2503.03114 （PromCopilot）
- https://www.alibabacloud.com/blog/dont-understand-promql-ai-agents-help-you-with-large-scale-metric-data-analysis_602420

**RCA 实证与因果**
- https://arxiv.org/abs/2407.12165 （AIOpsLab）
- https://www.microsoft.com/en-us/research/wp-content/uploads/2024/10/arxiv_AIOpsLab.pdf
- https://github.com/microsoft/OpenRCA
- https://arxiv.org/abs/2305.15778 （RCACopilot）
- https://arxiv.org/abs/2301.03797 （ICSE 2023 Microsoft incident RCA）
- https://huggingface.co/blog/ibm-research/itbench-aa
- https://huggingface.co/blog/ibm-research/itbenchandmast
- https://arxiv.org/abs/2508.12472 （GALA）
- https://arxiv.org/abs/2512.22113 （Praxis）
- https://arxiv.org/abs/2506.00844 （LLM Cannot Discover Causality）
- https://arxiv.org/html/2508.06394v2 （AI Oops，telemetry manipulation）
- https://causely.ai
- https://clickhouse.com/resources/engineering/ai-sre-agents
- https://clickhouse.com/blog/llm-observability-challenge
- https://www.forbes.com/councils/forbesbusinesscouncil/2026/05/04/what-the-industry-gets-wrong-about-building-an-ai-sre
- https://github.com/prometheus/prometheus/discussions/11705
