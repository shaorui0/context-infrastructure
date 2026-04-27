# Traditional SRE Methodology — 7 层工具箱参考

## When to Use

- 做 AI 系统 / agent 架构设计，判断生产就绪度
- 学习 SRE 心智（尤其是之前没做过大规模系统运维的 AI 工程师）
- 做 eval framework / observability stack / reliability pattern 时查参照
- 面试/招聘 AI 系统工程师时做 checklist
- 复盘 AI 系统事故时找"缺了哪一层"

## Core Thesis

传统分布式系统 SRE 方法论是过去 20-30 年沉淀的"可工程化可靠性"的语言。它不是一套工具，是一套**把可靠性从直觉变成可协商对象的认知框架**。对 AI 系统尤其重要，因为 AI 本身是概率性 component，需要这层外壳把它包成可运维产品。

配套 axiom：[T12. 第一性 SRE 是 AI 系统的外壳](../axioms/t12_sre_as_ai_outer_shell.md)

---

## Layer 1: 度量与谈判层（SLI / SLO / Error Budget）

### 来源
Google SRE book（2016）。Ben Treynor 2003 年内部推动，2014 年后公开化。

### 核心概念

**SLI (Service Level Indicator)** — 选什么指标代表"好"
- 关键不是"测什么"，是**"不测什么"**——测错指标比不测更糟
- 经典 SLI：可用性、延迟、吞吐、正确率、新鲜度
- 好的 SLI 标准：用户可感知 + 可度量 + 稳定不漂移

**SLO (Service Level Objective)** — 给 SLI 设定目标值
- 格式：`<SLI> 在 <时间窗口> 内达到 <目标百分比>`
- 例：`P99 延迟 < 500ms，30 天内满足 99.9%`
- 窗口选择：滚动窗口 vs 日历窗口，各有场景

**SLA (Service Level Agreement)** — 对外合同
- SLA = SLO + 违约赔偿条款。SLA 通常比 SLO 宽 1-2 个数量级

**Error Budget** — `1 - SLO` 就是允许失败的预算
- **SRE 最重要的发明**：把可靠性从道德议题变成经济议题
- 预算没花完 → 产品团队可以激进发版
- 预算烧光 → 冻结发布，修稳定性
- 关键是 error budget policy **写下来**，成为产品-SRE 契约

**Burn Rate Alerting** — 按预算消耗速度告警
- 不再对瞬时错误率告警（噪声太大）
- 而是对"按当前速度会多快烧光月预算"告警
- 多窗口多阈值（Google 推荐 2h+5min 组合）

### 映射到 AI 系统

| 传统 SLI | AI 系统对偶 |
|---------|----------|
| HTTP 成功率 | Task 完成率（按 eval dataset 判定）|
| P99 延迟 | Token 首字延迟 / 整体任务延迟 |
| 错误率 | 幻觉率 / 拒答率 / 人工评分低分率 |
| 数据新鲜度 | 知识截止日期 / 检索结果 recency |

**AI SLO 的难点**：成功定义很难客观化。常用策略：rubric 人工打分 + LLM-as-judge + 用户反馈信号（点赞/重试）三源交叉。

### 经典读物
- *Site Reliability Engineering*（Google, 2016）第 4 章 "Service Level Objectives"
- *The Site Reliability Workbook*（Google, 2018）第 2 章 "Implementing SLOs"
- Alex Hidalgo *Implementing Service Level Objectives*（O'Reilly, 2020）

---

## Layer 2: 过载与控制层（Overload / Backpressure）

### 来源
排队论（1950s，Erlang）→ Jeffrey Dean 的分布式系统课 → Netflix Hystrix（2012）→ Google 内部 RPC 框架。

### 核心概念

**Little's Law** — `L = λW`
- 并发数 = 吞吐率 × 平均延迟
- 任何容量规划的第一性原理
- 推论：延迟上升时并发必增，容量规划必须看**延迟分布**不是均值

**排队论基础**
- M/M/1、M/M/c 告诉你：**利用率超过 70% 时，尾延迟（P99）指数爆炸**
- 所以容量规划的经验法则是"留 30% 余量"——不是保守，是数学

**Load Shedding** — 过载时主动拒绝
- 比让所有请求一起烂要好得多
- 优先级 shedding：保关键流量，丢低优先级
- 实现：admission control + 限流（令牌桶 / 漏桶）

**Backpressure** — 下游把压力反传给上游
- TCP 窗口是最经典的 backpressure
- gRPC flow control、Reactive Streams、Akka Streams 都是这个思想
- 反面教材：火而忘返的 retry 风暴

**Circuit Breaker** — Hystrix 模式
- 失败率高于阈值 → 短路一段时间 → half-open 试探 → 恢复
- 核心价值：**给下游恢复的时间**，不让雪崩变永久故障

**Admission Control + Deadline Propagation**
- 请求带着 deadline 传递，中途超时直接抛弃
- 避免"幽灵请求"——客户端已经放弃但服务端还在算
- gRPC 原生支持，HTTP 要自己做

**Retry with Exponential Backoff + Jitter**
- **没有 jitter 就会同步风暴**（所有客户端同时重试打爆下游）
- 退避公式：`min(cap, base * 2^attempt) + random(0, jitter)`
- AWS SDK 的默认实现值得抄

### 映射到 AI 系统

| 传统问题 | AI 场景对偶 |
|---------|----------|
| 服务过载 | LLM API 被并发 agent 请求打爆 |
| 级联延迟放大 | Agent 嵌套调用（5 层嵌套 = 5× 延迟）|
| 幽灵请求 | Agent 任务用户已关闭但 LLM 还在推理 |
| Retry 风暴 | LLM 超时后客户端同步重试打爆 provider |

**AI 特有的过载问题**：
- LLM 调用延迟方差极大（1-60 秒），Little's Law 告诉你并发数必须很大才能跑满 QPS
- Token 成本 × 并发 × 重试 = 预算爆炸
- Agent loop 可能无限递归，需要 hard budget cap（token + wall time）

### 经典读物
- Jeff Dean *Designs, Lessons and Advice from Building Large Distributed Systems*（2009 slides）
- *The Tail at Scale*（Dean & Barroso, CACM 2013）
- AWS *Architecture Blog: Exponential Backoff and Jitter*（2015）
- Michael Nygard *Release It!* 第 5 章 "Stability Patterns"

---

## Layer 3: 可观测性层（Observability）

### 来源
- **Google Golden Signals**：SRE book（2016）
- **RED**：Tom Wilkie at Weaveworks（2015）
- **USE**：Brendan Gregg（2012）
- **Tail at Scale**：Dean & Barroso（2013）
- **可观测性三支柱**：Cindy Sridharan *Distributed Systems Observability*（2018）

### 核心概念

**Golden Signals** — Google 版本
- **Latency** / **Traffic** / **Errors** / **Saturation**
- 面向服务，4 个维度覆盖 80% 诊断需求

**RED Method** — 面向服务
- **Rate**（请求速率）/ **Errors**（错误率）/ **Duration**（延迟分布）
- 比 Golden Signals 更简，适合快速搭建

**USE Method** — 面向资源
- **Utilization**（利用率）/ **Saturation**（饱和度）/ **Errors**
- 查 infra 瓶颈时用

**Tail Latency**
- **平均值骗人。P99/P99.9 才是用户感受。**
- 1 次慢调用 + 100 次调用 = 用户 99% 概率至少遇到一次慢
- Fan-out 场景下尾延迟指数放大（见 *Tail at Scale*）
- 实战启发：如果尾延迟在某个精确整数秒（如 1.00s）出现尖峰，优先怀疑链路中某处触发了显式 timeout（网关/插件/依赖连接），而不是上游自然变慢；用 access log 与 error log 的时间戳/请求维度对齐验证

**三支柱：Metrics / Logs / Traces**
- **Metrics**：低基数聚合，用于告警和趋势
- **Logs**：高基数文本，用于事后取证
- **Traces**：请求级因果链，用于跨服务诊断
- 三者不可互相替代，但可以有公共上下文（trace ID）

**可观测性哲学**
- "你能回答的问题由你采集的数据决定"
- 事前设计 > 事后挖掘——生产出事才发现没采集正确的 dimension 是最常见事故
- 高基数 vs 低基数的取舍：Honeycomb/Axiom 等新一代工具鼓励高基数

### 映射到 AI 系统

| 传统可观测对象 | AI 系统对偶 |
|-----------|----------|
| HTTP 状态码 | Task 成功/失败/部分成功 |
| P99 延迟 | 首 token 延迟 + 整 task 延迟 |
| Throughput | Task/minute, tokens/sec |
| 错误堆栈 | Agent trace（tool call 序列 + 中间推理）|
| 资源利用率 | Token 消耗 / GPU 利用率 / 上下文窗口占用 |

**AI 特有的可观测维度**：
- **语义层**：输出质量（rubric score）、confidence、一致性
- **链路层**：tool call graph、重试次数、分支深度
- **经济层**：token cost per task、每种 model 的调用次数

**AI observability 难点**：输出是自然语言，没有天然的"错误码"。需要投资 LLM-as-judge 或 rubric eval 把输出量化成信号。

### 经典读物
- Cindy Sridharan *Distributed Systems Observability*（2018, O'Reilly 免费 ebook）
- Charity Majors *Observability Engineering*（2022）
- Brendan Gregg *Systems Performance*（2020 第 2 版）
- *The Tail at Scale*（Dean & Barroso, 2013）

---

## Layer 4: 发布工程层（Progressive Delivery）

### 来源
Facebook / Google / Netflix 内部实践（2010s），近十年产品化：LaunchDarkly（feature flag）、Argo Rollouts（K8s canary）、Spinnaker（Netflix canary）。

### 核心概念

**Canary Release**
- 发版时先放 1% 流量，观察指标，再 10% / 50% / 100%
- 带**自动回归判断**（Canary Analysis Service, CAS）
- 判断基础：新旧版本的 golden signals 对比

**Blue/Green Deployment**
- 两套完整环境（blue 现行，green 新版）
- 切流量瞬间完成，回滚也瞬间
- 成本高（两套 infra），适合关键系统

**Shadow Traffic / Dark Launch**
- 生产流量**复制**到新版本，但不返回用户
- 用于验证新版本的性能、正确性，不影响用户
- AI 场景极其有用（shadow 新模型，对比输出）

**Feature Flag**
- 代码部署 ≠ 功能启用
- 功能启用通过配置开关控制，可以按 user / region / % 细粒度
- 出事 → 关 flag，不用回滚代码

**Automated Rollback**
- 指标恶化 → 自动回滚，不等人
- 关键是阈值定义（SLO burn rate 是天然候选）

**Blast Radius Containment**
- 按 region / cell / shard 逐步铺开
- 一个 cell 炸了不波及其他
- Google cell-based architecture 是极致

**Small Batches**
- 每次发布变更最小化
- 大批量发布 = 调试空间指数爆炸

### 映射到 AI 系统

| 传统发布动作 | AI 场景对偶 |
|-----------|----------|
| 代码发布 | 模型版本升级 / prompt 升级 / tool schema 变更 |
| Canary | 小比例流量跑新模型，对比旧模型输出 |
| Shadow | Shadow 模式跑新模型，对比输出但返回旧版本 |
| Feature flag | Model flag / prompt flag，出事秒关 |
| Auto-rollback | 质量指标恶化自动切回旧模型 |

**AI 特有问题**：
- Prompt 改一个字可能导致大范围回归，必须 treat prompt as code
- 模型版本是黑盒，canary 判断只能靠输出对比 + eval
- Shadow 模式成本翻倍（两个模型都要跑），但对 AI 是必需的

### 经典读物
- *Site Reliability Engineering*（Google, 2016）第 8 章 "Release Engineering"
- *Accelerate*（Nicole Forsgren et al., 2018）
- Martin Fowler *Feature Toggles*（博客长文）

---

## Layer 5: 故障工程层（Chaos Engineering）

### 来源
- Netflix **Chaos Monkey**（2011）→ Simian Army → Chaos Kong
- Google **DiRT**（Disaster Recovery Testing, 2006 起内部）
- Amazon **GameDay**（Jesse Robbins 提出，2000s）
- Principles of Chaos Engineering（principlesofchaos.org, 2015）

### 核心概念

**Chaos Engineering 四原则**
1. 构建关于系统稳定状态的**假设**
2. 使用真实世界的**真实故障**（不是玩具场景）
3. 在**生产环境**运行（或尽可能接近）
4. 最小化**爆炸半径**，出事能迅速终止

**Failure Injection 类型**
- 网络：延迟注入、丢包、分区
- 进程：kill 进程、OOM、慢启动
- 资源：磁盘满、CPU 饱和、内存压力
- 依赖：下游超时、错误响应、慢响应
- 数据：损坏、延迟、过期

**Gameday** — 演练全团队响应
- 故意触发事故
- 不是测试系统，**是测试团队**
- 检验 runbook、on-call、沟通、决策

**Hypothesis-Driven Chaos**
- 每次 chaos 实验前写假设：X 故障时 Y 系统应该 Z 表现
- 实验结果验证或证伪假设
- 证伪就是一个 finding，就该修

**Blast Radius Containment**
- 从 staging → 单个 cell → 1% 生产 → 全量
- 有 big red button 随时中止

### 映射到 AI 系统

| 传统 Chaos | AI 场景对偶 |
|---------|----------|
| Kill 进程 | 杀掉 tool call，模拟 tool 返回 error |
| 网络延迟 | 人为延长 LLM 响应时间 |
| 错误响应 | 让 tool 返回错误/误导数据 |
| 依赖消失 | RAG 返回空结果 / 检索失败 |
| 数据损坏 | 往 prompt 里注入矛盾信息 |

**AI 专属 chaos 模式**（还没被充分开发的领域）：
- **模型降级**：切到更弱的模型，看 agent 是否察觉并兜底
- **毒输入**：prompt injection 测试、对抗样本
- **历史篡改**：修改 agent memory / conversation history
- **语义漂移**：同义词替换、上下文无关重述
- **工具误用**：让 agent 看到错误的 tool 文档

**为什么 AI chaos 更重要**：AI 系统的失败模式比传统系统更多样、更语义化。不主动 chaos 测试，上线后就是用户给你 chaos。

### 经典读物
- Casey Rosenthal *Chaos Engineering*（O'Reilly, 2020）
- Netflix *Chaos Monkey* 开源仓库（https://github.com/Netflix/chaosmonkey）
- Principles of Chaos Engineering（principlesofchaos.org）

---

## Layer 6: 事件响应层（Incident Management）

### 来源
- **ICS** (Incident Command System)：美国消防/应急管理体系，1970s
- **Google IMAG** (Incident Management At Google)
- **PagerDuty** 推广 on-call 文化（2010s）
- **Etsy** *Blameless PostMortems and a Just Culture*（John Allspaw, 2012）

### 核心概念

**Severity 分级 + 响应 SLA**
- SEV1-5 或 P0-P4，每级有明确响应时间
- 关键是**定义一致**——分级漂移会导致团队都在"SEV2 疲劳"

**Incident Command 制**
- **一个人指挥，其他人执行**
- 不要"民主讨论"——出事时最差的是所有人一起猜
- 角色：IC（指挥）+ Communicator（对外沟通）+ Tech Lead（执行）+ Scribe（记录）

**On-Call 轮值**
- Follow-the-sun 或本地轮值
- On-call 补贴（小时级 or 班次级）
- **on-call 负担上限**：Google 建议每班不超过 2 个非重大事件 / 周
- Toil 削减：50% 时间必须用来消灭 on-call toil

**Blameless Postmortem**
- Etsy 2012 那篇经典：**"我们预设每个人出于善意做了当时信息下最合理的决策"**
- 找系统缺陷，不找人为背锅
- **blameless ≠ accountability-less**：能问"系统为什么让这个错误成为可能"，不问"谁犯错"

**因果链分析工具**
- **5 Why**：每个结论再问一次 why，追到根因
- **Causal Chain**：A → B → C 的显式因果
- **Swiss Cheese Model**：多层防御都有洞，洞对齐就事故
- **Contributing Factors**（贡献因素，不是"根因"）：承认多因素共同导致

**Action Items 闭环**
- 没闭环的 postmortem 等于没做
- 每个 AI（action item）有 owner + deadline
- 定期审查 AI 完成率（这是 SRE 团队健康度指标）

**事件指标**
- **MTTD** (Mean Time to Detect)：事故发生到发现
- **MTTR** (Mean Time to Respond / Recover)：发现到恢复
- **MTBF** (Mean Time Between Failures)：故障间隔
- 长期趋势比绝对值重要

### 映射到 AI 系统

| 传统事件 | AI 场景对偶 |
|--------|---------|
| 服务宕机 | Agent 大面积失败 |
| 数据错误 | 模型输出系统性错误（新版本引入）|
| 安全事件 | Prompt injection 成功 / 敏感数据泄露 |
| 性能回归 | 新模型 P99 延迟上升 |

**AI 事件响应的特殊性**：
- **根因常在 prompt/数据/模型**，而不是代码
- **无法"重启"模型** → 降级策略必须预设
- **用户感知主观** → 量化事故规模很难
- **postmortem 需要 AI 专家参与** → 传统 SRE 看不懂失败链

**建议**：AI 团队尽早建立 incident review 机制，哪怕每周一次 30 分钟，blameless 文化要先于技术建立。

### 经典读物
- *Site Reliability Engineering*（Google, 2016）第 13-14 章
- John Allspaw *Blameless PostMortems*（2012 博客，必读）
- PagerDuty *Incident Response Documentation*（response.pagerduty.com）
- Richard Cook *How Complex Systems Fail*（1998 短文，18 条警句）

---

## Layer 7: 可靠性设计模式层（Resilience Patterns）

### 来源
- Michael Nygard *Release It!*（2007 第 1 版，2018 第 2 版）
- Martin Fowler 博客（microservices patterns）
- Netflix 工程博客（Hystrix / Resilience4j）

### 核心概念

**Idempotency（幂等）** — 重试安全的前提
- 同一操作执行 N 次和执行 1 次效果相同
- 实现：idempotency key + 去重
- 没有幂等就不能安全重试

**Timeout Budget**
- 每层调用预算递减：10s total → 8s to A → 6s to A's B
- 不传 deadline 就会让整条链路都堵死

**Bulkhead（舱壁隔离）**
- 单个依赖失败不拖垮整体
- 实现：独立线程池 / 连接池 / rate limit
- 源自造船舱壁——一个舱进水不沉船

**Graceful Degradation（优雅降级）**
- 主路径失败 → 走 fallback（缓存、简化版、默认值）
- 关键是**预设降级路径**，事中不临时设计
- 降级不是"功能消失"，是"功能降质"

**Fail-Open vs Fail-Closed**
- **Fail-Open**：失败时放行（如 rate limiter 挂了放所有请求）
- **Fail-Closed**：失败时拒绝（如认证服务挂了拒绝所有请求）
- 选择取决于**安全 vs 可用性**的优先级

**Hedged Request（对冲请求）**
- 并发发送多个请求到不同实例，取最快的
- 成本是多倍流量，收益是 P99 延迟大幅下降
- 见 *Tail at Scale*

**Fallback Chain**
- 多级降级：Primary → Secondary → Cached → Default
- 每级都要有明确触发条件

**Speculative Execution**
- 提前执行可能需要的操作（如预取）
- 如果真需要，延迟降低；不需要，浪费计算
- 数据库索引是一种 speculative execution

### 映射到 AI 系统

| 传统模式 | AI 场景对偶 |
|---------|----------|
| Idempotency | Agent task 可以安全重试（不会重复下单）|
| Timeout budget | LLM 调用预算 + tool call 预算 + 总 task 预算 |
| Bulkhead | 每种 tool 独立限流，一个 tool 慢不阻塞其他 |
| Graceful degradation | 强模型不可用 → 弱模型；弱模型不可用 → 规则引擎 |
| Fail-open vs closed | 生成内容过滤器挂了：放行 or 拒绝？|
| Hedged request | 同时问两个模型，取更快/更好的答案 |
| Fallback chain | GPT-4 → Claude → GPT-3.5 → cached → static response |

**AI 系统特别要关注**：
- **Token budget as bulkhead**：单 task token 预算是 bulkhead 的一种
- **Semantic fallback**：降级不只是"返回默认值"，可以是"用更简单的方式解决"
- **Human-in-the-loop as fallback**：最终的 graceful degradation 是升级给人

### 经典读物
- Michael Nygard *Release It!* 第二版（2018）— **最重要的一本**
- Uwe Friedrichsen *Resilience Patterns*（博客系列）
- Resilience4j 文档（开源实现，配合 Java 生态）
- Netflix *Hystrix Wiki*（已停止更新但概念经典）

---

## 横向元层：可工程化协商的哲学

7 层之上还有一个贯穿的元层——**这是第一性 SRE 思维最稀缺的部分**。

### 可靠性是产品决策
- **不是越高越好**，是和 feature velocity 的 tradeoff
- 99.9% → 99.99% 成本指数上升，是否值得要看用户
- SLO 谈判是 SRE 和产品的核心对话

### Toil 削减
- Google 定义：**重复 + 手动 + 可自动化 + 无长期价值**
- On-call 工程师 toil 占比 > 50% → 触发干预
- 剩余 50% 必须用于工程化（消灭 toil）

### Risk Budget 心智
- 每个架构决策都是拿预算换速度或反过来
- 可量化的 tradeoff 才能和 stakeholder 谈

### Contract over Heroics
- 可靠性靠**契约**（SLO、capacity plan、runbook）
- 不靠英雄救火
- 英雄文化是反模式——意味着系统性问题被个人兜底

### 渐进式保守主义
- 新系统：激进发布，快速学习
- 成熟系统：保守发布，小步迭代
- 关键系统：极度保守 + 完整 chaos 覆盖

---

## 学习路径建议

### Level 1: 概念入门（1-2 周）
- 读 *SRE book* 前 5 章（免费：sre.google/sre-book/）
- 读 John Allspaw 的 Blameless Postmortem 博客
- 读 *The Tail at Scale*

### Level 2: 工具实操（1-2 月）
- 搭一套 Prometheus + Grafana，监控一个真实服务
- 给自己的 agent 定义 3 个 SLI + 1 个 SLO
- 写一次 blameless postmortem（哪怕小事故）

### Level 3: 深度（3-6 月）
- 读 *Release It!*（第二版）
- 做一次 gameday / chaos 实验
- 设计一个 canary + auto-rollback pipeline

### Level 4: 第一性（持续）
- 把每个 SRE 概念翻译到 AI 场景
- 写自己的 AI SRE runbook
- 在真实 AI 系统里落地 7 层
- 沉淀成工具 / 框架 / 方法论

---

## 与本 workspace 其他内容的关联

- **配套 Axiom**：[T12 第一性 SRE 是 AI 系统的外壳](../axioms/t12_sre_as_ai_outer_shell.md)
- **姐妹 Skill**：[Agent Reliability Engineering (SRE Framing)](./bestpractice_agent_reliability_engineering.md) — 3 支柱简版，面向 agent 设计
- **相关 Axioms**：A04（可靠性是管理问题）、V02（可验证性）、T11（Hard leads, Cheap lags）、M09（AI 时代管理范式）
- **相关实践**：agent failure taxonomy、eval framework、observability stack

---

## 快速自检清单

面对任何 AI 系统，用这 7 个问题快速识别"缺了哪一层"：

1. [ ] **SLO**: 你的 agent "好/不好"的定义可以写成一行吗？
2. [ ] **过载**: 同时来 100 个请求会怎样？有 backpressure 吗？
3. [ ] **观测**: 任务失败了，你能在 1 分钟内定位到哪一步挂的吗？
4. [ ] **发布**: 换 prompt/模型是全量 vs canary？有回滚预案吗？
5. [ ] **Chaos**: 主动测过模型变笨、tool 返回错误结果吗？
6. [ ] **事件**: 线上出事谁指挥？有没有 blameless postmortem 机制？
7. [ ] **弹性**: 一个 tool 挂了，整个 task 降级还是崩溃？

**一个 ❌ = 一个下一次事故的来源。**
