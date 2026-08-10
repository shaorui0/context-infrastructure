# 方向 02 基础回顾：监控 / 可观测性 / SLO

> 组织形态：`面试官会怎么问` + `我从 50 集群实战里怎么答`。
> 每条标 `[一手]`（有真实经验背书，可以扛追问）或 `[理论]`（通用知识，不要伪装成经验）。
> 混合标记 `[一手+理论]` 表示核心判断有一手经验，但完整体系是补的理论。
> 数字口径：50 clusters / ~1.2M active series / ~80K samples/sec / lag 45s→<5s。

---

## 一、指标类型与聚合陷阱

### Q1. counter / gauge / histogram / summary 分别什么时候用？`[理论]`

**counter** 是单调递增的累积量，只能被 reset（进程重启）不能减。用它的原因是它对采集丢点是鲁棒的：中间丢了几个点，只要两端还在，`rate()` 算出来的速率仍然近似正确。所有「发生了多少次」的量都应该是 counter：请求数、错误数、字节数。**永远不要自己在应用里算速率再暴露成 gauge**，那会把丢点变成不可恢复的误差，而且不同窗口的重算能力全部丧失。

**gauge** 是可增可减的瞬时值：内存占用、队列长度、当前连接数、副本数。它的弱点是采集时刻之外的信息完全丢失，所以 gauge 天生看不见采集间隔之间的尖峰。

**histogram** 在服务端预定义 bucket 边界，暴露的是每个 bucket 的累积计数（`_bucket{le="..."}`）加 `_sum` 和 `_count`。它可跨实例聚合（bucket 计数是加法），分位数在查询时用 `histogram_quantile` 从 bucket 插值算出来。

**summary** 在客户端就把分位数算好暴露成 `{quantile="0.99"}`，好处是精度不依赖 bucket 边界，坏处是致命的：**分位数不可跨实例聚合**。三个实例各自的 P99 平均一下不等于整体 P99，这在数学上没有意义。

我的实战选择是 histogram 为主。但我要说明我们有一个用 summary 形态的关键指标，见 Q4。

### Q2. `rate()` 和 `irate()` 的区别，什么时候踩坑？`[理论]`

`rate()` 在整个时间窗口上做线性拟合式的平均（实际实现是取窗口内首尾样本的差值并做 extrapolation 外推到窗口边界），输出是窗口的平均速率，平滑，适合告警和趋势。`irate()` 只用窗口内最后两个样本算瞬时速率，敏感，适合看尖峰，但在告警里几乎一定是错的选择，因为它对单个采集抖动完全没有抵抗力。

三个坑。第一，**窗口必须至少是 scrape interval 的 4 倍**，否则窗口内可能只有一两个样本，`rate()` 的外推会给出剧烈波动甚至空值。我们 15s 间隔，所以最小窗口用 1m，常规用 5m。第二，`rate()` 的外推机制会让 counter 刚出生或刚 reset 时产生虚高的尖刺。第三，也是我踩过的：**`rate()` 之后再 `sum()`，不要 `sum()` 之后再 `rate()`**，因为 `sum()` 会把不同实例的 counter reset 混在一起，`rate()` 就无法识别 reset 了。

### Q3. `histogram_quantile` 的插值误差从哪来？`[一手+理论]`

误差来自一个根本事实：**histogram 只知道每个桶里有多少个样本，不知道它们在桶内怎么分布**。`histogram_quantile` 假设桶内均匀分布做线性插值，所以当大量样本挤在一个宽桶里，插值出来的分位数误差可以很大。极端情况：如果 P99 落在最后一个有界桶和 `+Inf` 之间，Prometheus 只能返回最后一个有界桶的上界，这时候分位数**系统性偏低**。

我的一手证据是这个偏差在两个方向都咬过我。**偏高方向**：一条延迟告警声称 P99 越限，而同一时间窗的应用日志和 APM 显示没有慢请求、错误率也没波动，最后定位是多实例采集时间错位叠加 histogram 分桶聚合偏差把 P99 算虚高了，以假告警结案 (src: `adhoc_jobs/dynamic_resume_site/content/integration/oncall_track_record.md` case 7)。**偏低方向**：我们遇到过 histogram 报 P99 = 800ms 而从原始 access log 用 LogQL 算出 P99 = 2.3s 的情况，桶边界 [0.1, 0.5, 1.0, 2.0] 而大量请求集中在 0.5 到 1.0 之间 (src: `work-contexts/career/interview/interview-3-monitoring_reference.md:113-114`)。

所以我的做法是把 histogram 当发现工具、把原始日志当验证工具，并且**不把 quantile 当 SLI 本体**（见 Q17）。

### Q4. 为什么你说分位数对 P100 天然失明？`[一手]`

这是我最看重的一条一手洞察。我们的 `http-sla-exporter` 暴露的是 gauge 加 `quantile` label（0.95 / 0.99 / 0.999 / 1.0）的形态，内部用 t-digest 做近似分位。t-digest 的设计目标是用很小的内存在中间区间保持较好精度、在尾部做压缩，代价就是**单点极值会被压掉**。实测结果：一个真实 5 秒的单点尖刺，在 `quantile="1.0"` 上被抹成大约 0.3 秒 (src: memory `reference_dv_ingress_latency_decomposition.md`)。

这意味着如果我只信 VM 里的聚合指标，我会得出「最大延迟 300 毫秒，一切正常」的结论，而真实值是 5.067 秒 (src: `contexts/galileo_latency_investigation_20260626/REPORT.md`)。**这类偏差比假警报危险得多，因为它不会有人来叫你。**

推广成一条原理：**P100 是一个单点统计量，而任何压缩型的分位数近似（t-digest、histogram 分桶、HDR histogram 的精度分级）本质上都在用「牺牲单点精度」换「有界内存」。所以 P100 和聚合指标在设计上就是矛盾的。** 查极值必须回到逐条记录：我们的做法是查原始 nginx access log，或者用 dashboard 上 ClickHouse 侧的 `observable.http_access_parsed.req_time_max` 字段 (src: memory `reference_dv_ingress_latency_decomposition.md`)。

推论还有一条：**P100 也不应该被用来做 SLO**，因为它对单个异常样本无限敏感，没有统计稳定性。它的正确用途是排障时的「有没有出现过病态的慢请求」这个是非题。

### Q5. 对一个 gauge 形态的分位数指标怎么做时间维度的统计？`[一手]`

这是我们指标形态特殊带来的实战技巧。因为 `http_access_ingress_sla_*` 是 gauge 带 `quantile` label 而不是原生 histogram，我不能用 `histogram_quantile`，只能对已经算好的 `quantile="0.99"` 这条序列做二次时间统计：

```promql
quantile_over_time(0.95, (http_access_ingress_sla_request_duration_seconds{quantile="0.99"} > 0)[24h:5m])
```

三个设计点。`quantile_over_time(0.5, ...)` 取活跃期的**典型值**，`quantile_over_time(0.95, ...)` 取**持续最差值**，两个一起看才能区分「偶发尖刺」和「持续变慢」。`[24h:5m]` 是 subquery，把 24 小时按 5 分钟采样成一个序列再统计。`> 0` 这个过滤是最容易漏掉且最致命的一步：我们的 A/B 集群通过 autoswitch 交替服务，不服务的一侧指标是 0，不过滤会让空闲期的零值把分位数拉低，得出「B 其实很快」的完全错误结论 (src: memory `reference_dv_ingress_latency_decomposition.md`, `contexts/galileo_latency_investigation_20260626/REPORT.md`)。

---

## 二、Prometheus 数据模型与 cardinality 治理

### Q6. 一条 time series 是什么？series 爆炸从哪来？`[一手+理论]`

一条 series 由 metric name 加全部 label 的键值组合唯一确定，任何一个 label 值变化就是一条新 series。所以 series 总数 ≈ 各 label 基数的**笛卡尔积**，这是所有 cardinality 问题的根。

爆炸的典型来源，按我见过的危险程度排：

1. **把无界的东西塞进 label**：user_id、request_id、trace_id、完整 URL path（尤其带 ID 段）、error message、pod IP。这类 label 的基数随时间无限增长，不是「大」而是「无界」。
2. **多个中等基数 label 相乘**：单看每个都只有几十个值，乘起来就是几万。`tenant` × `endpoint` × `status_code` × `cluster` × `method` 很容易失控。
3. **高频重建的资源作为 label**：pod name 在 CrashLoop 或频繁滚动时基数会持续膨胀，虽然旧 series 会变成 inactive，但 index 和 head block 的压力是真实的。
4. **histogram 的隐藏乘数**：一个 histogram 有 N 个 bucket 就是 N+2 条 series，所以给 histogram 加一个基数 20 的 label，实际增加的是 20 × (N+2) 条。**这是最容易低估的一项。**

### Q7. series 爆炸怎么止血，怎么长期治理？`[一手]`

止血（分钟到小时级）：先定位，用 VM 或 Prometheus 的 TSDB status / cardinality 接口找 top metric 和 top label；然后在**采集侧**用 relabel 的 `labeldrop` / `metric_relabel_configs` 的 `drop` 动作把凶手切掉。关键是止血必须在采集侧做，在查询侧做没有用，因为存储压力已经产生了。

长期治理我落的是四条 (src: `adhoc_jobs/dynamic_resume_site/content/projects/p_vm_platform.md` Hard parts, `interview-3-monitoring_reference.md:130`)：

1. **tenant 级 recording rules 只覆盖核心 SLI**，不是所有指标都下钻到租户维度。
2. **基础设施指标一律不带 tenant label**。node、kubelet 这些天然不属于任何租户，加上去纯粹是笛卡尔积。
3. **retention 分层**：tenant SLA 序列 90 天，排障序列 30 天，基础设施 15 天。
4. **定期 cardinality 审查**，清理意外的高基数 label。

诚实的复盘：这四条是被增长曲线逼出来的，**cardinality budget 应该在第一天就存在** (src: `p_vm_platform.md` Hard parts)。如果重做，我会在采集侧加一道硬门禁：新指标上线前必须声明预期 series 数，超过预算的 label 组合直接拒绝，这和我在告警治理里用的准入控制是同一个思路。

### Q8. recording rules 为什么要先物化 SLI？`[一手]`

三个理由。**成本**：dashboard 和 alert rules 都消费预计算结果，不在现场跑重查询。一个跨 50 集群按 tenant 聚合的 P99 查询如果每次现场算，vmselect 会被 dashboard 刷新和告警评估同时打。**一致性**：SLI 的定义只写一遍。如果 dashboard 和 alert rule 各写一套 PromQL，它们迟早会漂移，然后你会遇到「dashboard 是绿的但告警在响」这种最消耗信任的情况。**可组合**：物化出来的 `sli:error_ratio:5m{tenant}` 这种序列可以被更高层的规则和 burn-rate 计算直接复用。

我物化的 SLI 族是 QPS、error ratio、P95/P99 latency、saturation、per-tenant SLI，全部按 `{tenant, cluster_group}` 键控 (src: `interview-3-monitoring.md:57`, `interview-3-monitoring_architecture.md:73-78`)。

命名上我用 `level:metric:operation` 这个约定（Prometheus 社区惯例），比如 `sli:error_ratio:5m`，好处是一眼能看出这是派生序列不是原始采集。

一个规模上的坑：**vmalert 规则多了之后评估周期会跟不上**，我们的缓解是把 tenant 级和全局 recording rules 拆到不同 rule group 分开评估 (src: `interview-3-monitoring_reference.md:153`)。

---

## 三、拉取 vs 推送、Federation、remote write、存储选型

### Q9. pull 和 push 各自的结构性优劣？`[一手+理论]`

pull 的好处：采集端天然知道 target 是否存活（`up` 指标是免费的服务发现健康检查）；采集频率和超时由中心控制，不会被被监控方打爆；配置集中，target 列表就是真相。坏处：中心需要网络可达每个 target，跨网络边界和 NAT 后面的短生命周期任务（batch job、Lambda）很难；pull 天然是分层的，而**分层就意味着延迟叠加**。

push 的好处：延迟低（采到就推）；穿透网络边界容易；短生命周期任务天然适配。坏处：中心可能被打爆需要 rate limit；**丢数据的风险从「中心拉不到」变成「客户端推不出」**，需要客户端侧的持久化缓冲。

我们的架构是「集群内 pull、跨集群 push」的混合：每集群一个 vmagent 在集群内 pull（保留服务发现和 `up` 的好处），然后 remote_write 推到中心（消掉分层延迟）。这个组合是我认为多集群场景的正解 (src: `p_vm_platform.md` How 节)。

push 侧的必要工程是 persistent queue：每个 vmagent 在本地磁盘上跑持久化队列，remote 断连期间缓冲、恢复后回放。**「真正需要工程投入的不是快，而是不丢」** (src: `p_vm_platform.md` Hard parts)。

### Q10. Prometheus Federation 的结构性问题到底是什么？`[一手]`

四条，全部是架构属性不是配置属性 (src: `interview-3-monitoring_reference.md:42-49`)：

1. **可靠性**：global Prometheus 要在内存里维护全局的 head block，我们是 1.2M series 占 5 到 10 GB，每周 OOM 两到三次，每次崩溃重启在数据上留下空洞，而空洞会以「不存在的故障」的形式误报 oncall。加内存只是把 OOM 周期拉长。
2. **延迟**：两层 scrape 周期叠加，集群本地 15s 加全局层 30s，全局视图最多滞后现实 45 秒。这是拓扑决定的下界，任何调参到不了 5 秒。
3. **扩展性**：50 集群的负载下 `/federate` 接口频繁 scrape timeout，Grafana 出现数据断点。`/federate` 是一个同步的、把大量 series 序列化成文本再传输的接口，它没有为这个规模设计。
4. **运维复杂度**：每个集群各自维护一套 federation rules，新集群接入要手工改 global Prometheus 的 scrape 配置。

**面试答这题的关键是那句判断**：「Federation 的 45s 延迟和每周 OOM 是架构属性而不是配置属性，任何调参预算都修不好」(src: `p_vm_platform.md` Takeaways)。这句话展示的是判断力而不是工具熟练度。

### Q11. remote_write 的关键参数和失败模式？`[一手+理论]`

关键机制是 WAL 加 shard 加队列。发送端从 WAL 读样本，按 series hash 分到若干 shard，每个 shard 独立批量发送。核心参数是队列容量、批大小、最大 shard 数、重试退避。

失败模式三类。**背压**：远端慢或者 429，发送端队列堆积，最后开始丢样本；症状是发送端的 `pending samples` 和 `dropped samples` 上升。**磁盘**：WAL 或 persistent queue 有上限，我们的配置里 `maxDiskUsagePerURL` 是 1GB × 3 个 endpoint = 3GB (src: `contexts/thought_review/victoriametrics_ops_review_20260402.md`)，超过上限就开始丢，所以这个上限决定了你能容忍多长的远端中断。**乱序与重复**：重试会产生重复样本，接收端要能幂等处理（同 timestamp 同值幂等）。

监控 remote_write 本身是必须的：队列长度、丢样本数、发送延迟、远端返回码分布，这四个是最小集。这一条属于「监控监控系统」，很容易被漏掉。

### Q12. VictoriaMetrics 和 Thanos / Mimir 怎么取舍？`[一手+理论]`

我做过 VM 与 Thanos 的 POC，维度是写入吞吐、压缩率、运维复杂度，最终团队共识选 VM (src: `interview-3-monitoring_architecture.md:226`)。我没有在生产运维过 Thanos 或 Mimir，所以下面的架构对比是理论加 POC，不是两边都跑过一年。

| 维度 | VictoriaMetrics | Thanos | Mimir |
|---|---|---|---|
| 核心模型 | 自有存储格式，vminsert/vmstorage/vmselect 三层可独立扩展；`[一手]` | Prometheus block 传到 object storage，sidecar + store gateway + querier fan-out + compactor；`[理论]` | Prometheus 代码演化，ingester 分片 + object storage，组件多但一体化程度高；`[理论]` |
| 长期存储 | 本地 SSD 热 + S3 降采样冷；我们是热 3 月 ~250GB、冷 180 天 ~25GB `[一手]` | object storage 原生，理论无限廉价 `[理论]` | object storage 原生 `[理论]` |
| 压缩 | 实测约 4 倍，同一 3 月窗口 930GB → 250GB `[一手]` | Prometheus TSDB 压缩 `[理论]` | 同 Thanos 血统 `[理论]` |
| 查询语言 | MetricsQL，PromQL 超集但有边界差异，这是我们迁移必须双写验证的原因 `[一手]` | PromQL `[理论]` | PromQL `[理论]` |
| 运维复杂度 | 组件少，小团队可控 `[一手]` | 组件多、故障面大 `[理论]` | 组件最多，需要专职投入 `[理论]` |
| 多租户 | vminsert/vmselect 支持 tenant 隔离 `[理论]` | 靠 label + query 层 `[理论]` | 原生多租户是它的主打 `[理论]` |

**我的决策逻辑（这是答这题的重点）**：Thanos 那套复杂度换来的核心价值是「无限廉价的长期存储」和「跨集群 PromQL 全局查询」。我们的实际需求是热 3 个月加冷 180 天降采样，这个体量本地 SSD 加 S3 就覆盖了，买不到对应价值。而我们是 3 到 4 人的 SRE 团队，**运维复杂度对我们不是次要维度，是主要维度**。这是一个规模匹配的决策，不是「VM 比 Thanos 好」。如果我在一个有专职 observability 团队、需要保留两年原始精度数据、且已有 Prometheus 生态深度绑定的组织，我会重新评估。

### Q13. VM 挂了告警还能工作吗？`[一手]`

诚实的答案是：**目标不是「VM 挂了告警照常」，而是分钟级告诉 oncall 数据不可信，走降级路径** (src: `interview-3-monitoring_reference.md:63`)。

两层保障。第一层，Alertmanager HA 双实例加通知通道冗余。第二层是关键：**deadman's switch**。vmalert 持续输出一个必然为真的心跳告警，下游（外部的 watchdog 或者 Alertmanager 的 heartbeat receiver）如果在预期窗口内收不到这条心跳，就触发「监控失联」告警。再加一个 out-of-band 探针独立监控关键接口，它不依赖 VM 这条链路。

这个设计的一般原理是：**一个监控系统必须能报告自己的失效，否则「没有告警」和「一切正常」在信号上不可区分**。这和我在 Loki pattern 静默失效上学到的是同一件事：失败倾向于表现为「没有数据」，而「没有数据」很容易被误读成「没有问题」(src: `story_bank.md` S06)。

---

## 四、SLI / SLO / Error Budget 完整理论

> 这是我的中环。下面的标准答案我讲得出，但我要明确说明我落地了哪一半、没落地哪一半。

### Q14. SLI、SLO、SLA 的区别？`[一手+理论]`

`[理论]` 定义：SLI 是选来代表「好」的指标；SLO 是给 SLI 设的目标，格式是「<SLI> 在 <时间窗口> 内达到 <目标百分比>」；SLA 是对外合同，等于 SLO 加违约赔偿条款，通常比内部 SLO 宽 1 到 2 个数量级（src: `rules/skills/bestpractice_traditional_sre_methodology.md` Layer 1）。

`[一手]` 我的理解是从压力里长出来的，不是从书里：在 demo 环境 SLO 是个概念，系统挂了重启就好，没人真的损失什么，「99.9%」是 PPT 上的数字。到了 production 背后站着一个真实客户，这时候才明白 **SLA 是一个承诺，是对客户签字画押的那条线**；它是稳定性的具象化，抽象的「稳定」被翻译成「月度可用性 ≥ 99.9%，否则赔偿」；而 infra 被推到前台，它的抖动直接变成客户的损失、电话、流失 (src: `adhoc_jobs/dynamic_resume_site/content/growth/g_slo_topdown.md`)。

为什么 SLA 要比 SLO 宽：因为你需要在违约之前有时间反应。SLO 被击穿是一个内部警报，SLA 被击穿是一次赔偿。

### Q15. SLI 怎么规格化？event-based 和 time-based 的区别？`[理论]`

一个完整的 SLI 规格必须写清五件事：

1. **好事件的定义**（什么算成功）
2. **有效事件的定义**（分母范围，哪些请求不算，比如健康检查、内部流量、客户端 4xx）
3. **测量点**（在哪一层测：客户端、负载均衡器、服务端）
4. **聚合窗口**
5. **计算公式**

**event-based（请求驱动）**：`SLI = 好事件数 / 有效事件数`。适合有明确请求单位的服务。优点是可加、可按维度切分、和用户体验直接对应。

**time-based（时间驱动）**：把时间切成等长的小片（比如 1 分钟），每片按某个条件判定「好」或「坏」，`SLI = 好时间片 / 总时间片`。适合没有明显请求单位的场景（批处理、数据新鲜度、有状态系统的可用性），也更接近合同里「月度可用性」的表述方式。

坑在于两者不可互换：一个每分钟只有 1 个请求失败的服务，event-based 看是 99.9% 好，time-based 看可能是「每分钟都有坏事件」所以接近 0%。**选哪一种取决于用户感受的是「我的请求成功了吗」还是「服务当时可用吗」。**

`[一手]` 我落地的 SLI 是 event-based 的：QPS、error ratio、P95/P99 latency、saturation、per-tenant SLI (src: `interview-3-monitoring.md:57`)。分母范围（有效事件）这一层我做得不够严格，这是一个我知道的短板。

### Q16. error budget 是什么？为什么它是 SRE 最重要的发明？`[理论]`

`1 - SLO` 就是允许失败的预算。它把可靠性从道德议题变成经济议题：预算没花完，产品团队可以激进发版；预算烧光，冻结发布去修稳定性 (src: `rules/skills/bestpractice_traditional_sre_methodology.md` Layer 1)。

关键是 **error budget policy 必须写下来**，成为产品与 SRE 之间的契约，否则它就只是一个 dashboard 上的数字，没有牙齿。一份完整的 policy 至少要写：SLO 目标值与窗口、预算的计算方式、消耗到不同水位时的行动（比如剩 50% 时暂停高风险变更、剩 0% 时冻结所有非修复性发布）、谁有权豁免、豁免怎么记录。

数字例子 `[一手，来自我的材料]`：SLO 99.9%、30 天窗口 → 预算 = 43,200 分钟 × 0.1% = 43.2 分钟。burn rate 14 倍意味着预算在约 2.14 天内烧完，也就是每小时烧掉约 2% 的月预算 (src: `interview-3-monitoring_reference.md:80-81`)。

### Q17. Latency 的 SLI 应该是 P99 还是比例？`[一手+理论]`

这是我认为最值得讲清楚的一个概念区分，我用的是四层分离的框架 (src: `rules/skills/bestpractice_sre_reliability_models.md` §3)：

- **SLI**：衡量什么
- **Histogram**：怎么记录分布
- **Quantile**：怎么查看分布中的统计值
- **SLO**：对该指标在时间窗口内施加什么目标

推荐口径是 `SLI = requests_under_threshold / valid_requests`，`SLO = SLI ≥ target over time window`；**`P99 ≤ Xms` 更适合作为观测视角或补充视角，不要默认把 quantile 当成 SLI 本体** (src: 同上)。

理由是三条，而且我有一手证据支撑：第一，比例型 SLI 只需要读 bucket 边界上的一个累积计数，**不需要插值**，所以它不受桶内分布假设的影响；第二，它**天然可跨实例聚合**，因为分子分母都是加法，而分位数不可加；第三，它和 error budget 是同一种数学对象（都是「坏事件占比」），可以直接进 burn-rate 计算，而分位数进不去。我的一手教训在 Q3 和 Q4：分位数被算高会造成假警报（histogram skew 那次假告警），被算低会造成假信心（t-digest 把 5 秒抹成 0.3 秒）。

实操上这意味着**SLO 的阈值要在 histogram 的 bucket 边界上**。如果 SLO 是「99% 的请求在 500ms 内」，那么 500 必须是一个 bucket 边界，否则你只能插值，又回到了同一个问题。这是设计 bucket 时最重要的约束，而它经常被忽略。

### Q18. 多窗口多燃烧率告警怎么设计？Google 那套 2% / 5% / 10% 是什么？`[理论]`

`[理论]` Google SRE Workbook 的完整方案是把「预算消耗速度」和「确认窗口」两个维度组合起来。核心公式是 `burn rate = 实际错误率 / (1 - SLO)`，burn rate = 1 意味着刚好在月末用完预算。

以 30 天窗口为例，canonical 的三档配置：

| 消耗比例 | 消耗时长 | burn rate | 长窗口 | 短窗口 | 动作 |
|---|---|---|---|---|---|
| 2% | 1 小时 | 14.4 | 1h | 5m | page |
| 5% | 6 小时 | 6 | 6h | 30m | page |
| 10% | 3 天 | 1 | 3d | 6h | ticket |

三个设计要点。**为什么要两个窗口**：长窗口决定「这个消耗速度是否严重」，短窗口决定「现在是否还在发生」。只有长短窗口同时超阈值才触发，长窗口防抖动，短窗口保证**告警能自动恢复**（问题停止后短窗口很快回落，不用等长窗口滑出）。**为什么短窗口是长窗口的 1/12**：这是一个在灵敏度和误报之间的经验取值。**为什么快慢要分层**：14.4 那一档抓快速烧穿，1 那一档抓缓慢退化，后者不该 page 但必须有人处理，所以走 ticket。

`[一手]` 我实际落地的是 fast burn 的双窗口确认：**5m 和 30m 两个窗口都超阈值才升级为 PAGER**，作用是滤掉瞬时抖动同时保留持续恶化的检测能力；slow burn 的 1h/6h 一档我在材料里写了设计但没有在生产跑满 (src: `interview-3-monitoring.md:61`, `interview-3-monitoring_reference.md:77-78`)。

**诚实边界（必须说）**：我没有跑满完整的三档体系，前置条件是每条链路都有确定的 SLO 目标值，而我们当时的阈值有一部分是经验值。另外 `p_alert_gov.md` 的 baseline 显示 pager 侧仍有大量静态阈值规则在运行，所以我不能说「我们的告警都是 burn-rate 驱动的」(src: `adhoc_jobs/dynamic_resume_site/content/projects/p_alert_gov.md`)。

### Q19. error budget policy 怎么真正落地？`[理论 + 我的诚实边界]`

`[理论]` 落地路径我认为是五步：

1. **挑一个有明确 owner 的服务做试点**。SLO 的前置条件是 service ownership，没有 owner 的服务定 SLO 是空的。
2. **先只做测量**。SLI 物化、budget 消耗上 dashboard、跑够一个完整窗口（至少 3 个月），让所有人看到真实数字。这一步不带任何惩罚性条款，目的是建立数据可信度。
3. **拿真实数据谈目标值**。目标值应该来自「用户能感知到的差别在哪」加「历史实际达成水平」，不是拍一个 99.9%。一个常见的正确结论是把目标定得比现状略紧但可达。
4. **写 policy，从软条款开始**。剩 50% 暂停高风险变更，剩 0% 冻结非修复性发布，谁能豁免、豁免怎么记录。软条款先跑，有牙齿的条款后加。
5. **建 review 回路**。固定周期的 SLO review，看的不只是「有没有达标」，还包括「这个 SLO 是否还代表用户体验」，因为 SLI 会随系统演化而语义失效，这和告警规则的腐化是同一个机制。

`[我的诚实边界]` 这五步我做到的是第二步的技术部分：SLI 的 recording rule 物化、per-tenant SLA 追踪、以及「PAGER 必须有 SLO 基准」这条准入规则。**我们没有一份写下来的 error budget policy，没有把「预算烧光就冻结发布」变成正式契约，也没有固定的 SLO review 会议。** 归因是 SLO 定义需要 service ownership 支撑，在我们的组织结构里这不是我能单方面推成的，我当时选择先把可测量性做实 (src: `interview-3-monitoring.md:89`「SLO 定义需要 service ownership 支撑」是我自己写下的约束)。这条边界我在面试里会主动说，因为把它包装成已建成的体系，一个追问就穿。

---

## 五、告警哲学

### Q20. symptom-based 和 cause-based 告警怎么选？`[一手+理论]`

`[理论]` 原则是**对症状告警，用原因辅助诊断**。理由是症状的数量有限（用户能感知的坏事情就那么几类）而原因是无穷的，对每个可能的原因加一条告警必然导致规则数爆炸和覆盖不全同时发生。

`[一手]` 我做这个转变的过程是可量化的。对 30 天告警历史做审计，方法是拉 Alertmanager 的 firing 历史，对每条标记「是否导致了实际的用户操作（acknowledge → investigate → action）还是被 silence 或忽略」，结论是约 80% 的 page 是 CPU / memory / disk 抖动触发的 resource-centric 告警，值班人的典型反应是「看了一眼，没事，关掉」(src: `interview-3-monitoring_architecture.md:288-293`)。

然后重新定义 PAGER 准入：必须指示可观测的用户影响，具体三条之一是 error ratio 超过 SLO budget burn rate（不是单纯的 error count spike）、latency P99 突破 SLA 定义的阈值（不是「比昨天高」）、关键业务流程 QPS 归零或断崖式下降。不满足的全部降级为 HIGH 或 MEDIUM (src: `interview-3-monitoring_architecture.md:297-302`)。

**但 cause-based 有一类必须保留**：先兆型指标。磁盘即将写满、证书即将过期、连接池即将耗尽，这类「不处理必然在可预测的时间点变成用户影响」的信号，价值恰恰在于用户还没受影响。所以我的分类不是「资源指标一律降级」，是「不能指导行为的降级，能指导行为且有明确时间窗的保留」。

### Q21. page 和 ticket 怎么划线？`[一手]`

我的三层划线 (src: `interview-3-monitoring_reference.md:69-73`)：

- **PAGER**：用户可感知的错误或延迟，且需要立即人工介入。量极少，每一条必须是真实用户问题。
- **HIGH**：高风险但当下用户不一定受影响（consumer lag、replica 数不足、replication down）→ Slack。
- **MEDIUM**：趋势类、容量预警 → 工单。

划线的判据不是「严重程度」而是**「需要多快的人工介入」**，这是一个更可操作的问法。判断一条告警该 page 还是该 ticket，问三个问题：现在不处理会怎样？处理动作是什么，有没有 runbook？这个动作必须由人做还是可以自动化？三个问题都答不上来的，它不该 page。

`[一手]` 我在告警治理里把这条推进了一层，用**偏离基线的倍数**做量化判据：低于 2 倍不告警，2 到 4 倍 P2 进 channel 不 @，高于 4 倍 P1 page 并 @ owner 且附 runbook (src: `p_alert_gov.md` How 节)。这个判据的价值是它把「严重程度」变成了可以写进 rule 的表达式，而不是靠作者的感觉。它的来源是一个真实的荒谬案例：超出平均 28% 的 job 和超出 300% 的 job 拿到同一个 P1。

### Q22. 告警质量怎么衡量？`[一手]`

两个信号，我在 VM 平台项目里用的 (src: `interview-3-monitoring_architecture.md:318-322`)：

1. **每条 PAGER 的 action rate**：page 之后是否导致了有意义的操作。这是防噪声的。
2. **漏报追踪**：用户反馈了问题但没有对应的 PAGER。这是防盲区的。

缺任何一个都会跑偏：只看 action rate 会导致越来越保守直到漏报，只看漏报会导致越来越激进直到 fatigue。

`[一手]` 我在告警治理里把这个升级成了一个更强的提法：**把 pager 本身变成 SLO 对象**。告警总量、priority 分布、dedup 比例不上 dashboard，它们的退化就不可见，而这正是熵第一次溜进来的方式 (src: `p_alert_gov.md` Takeaways)。诚实边界：这两个信号在 VM 平台时期是人工统计的，做成常设 dashboard 是我在治理方案里才提出的（Phase 0 的 baseline dashboard 保留为长期 alert SLO dashboard）。

### Q23. inhibition 和 grouping 的分工？`[一手]`

**inhibition 解决因果派生噪声，grouping 解决规模噪声，两件事不要混** (src: `interview-3-monitoring_reference.md:93-94`)。

inhibition 的原则是只做因果关系明确的抑制：`NodeNotReady` 抑制同节点的 `PodUnableToStart`，因为节点没 Ready 那个节点上的 pod 起不来一定是这个原因。不做「服务 A down 抑制服务 B 的告警」，因为因果不确定，B 完全可能同时有一个独立故障，被抑制掉就是盲区 (src: `interview-3-monitoring_architecture.md:312-314`)。**inhibition 的失败模式不对称**：做窄了多看几条告警，做宽了掩盖真实故障。

技术前提：Alertmanager 的 inhibition 用 `source_match` / `target_match` 加 `equal` 字段，`equal` 要求 source 和 target 有相同的 label 值。所以**label 一致性是 inhibition 能工作的硬前提**，这也是我把统一 relabel 模板当平台基础设施来做的原因之一 (src: `interview-3-monitoring_reference.md:90-91`)。

验证方式：在 staging 人工触发上游故障，检查哪些下游告警被抑制，并保留 firing 历史供 postmortem 回溯 (src: `interview-3-monitoring_reference.md:88`)。

datacenter 级故障几百条告警怎么办，三件事配合 (src: `interview-3-monitoring_reference.md:94`)：`group_by` 按 cluster / datacenter / service / alertname 折叠成少量 group；`group_wait` 30 到 60 秒聚齐再发；检测到系统性故障模式时 PAGER 只发一条「全局事故」，症状类降级或静默。

### Q24. dedup 为什么重要？`[一手]`

因为没有 dedup，**同一个问题每次重新 firing 都会生成一条新告警**，一个持续 3 小时的卡住 job 会 page 三次，问题只有一个。这在我的审计里是 960 条每天里的重要来源 (src: `p_alert_gov.md` Why / How 节)。

技术手段是在 receiver 上配 dedup alias 加 `update_alerts`，让重复触发变成计数递增而不是新建告警。配套还需要 auto-close 策略，否则告警会永远挂着。

一个隐藏的坑：**绕过 Alertmanager 的旁路发送对 dedup 和 inhibition 完全不可见**。我审计出来的四个结构性根因之一就是一条旁路脚本直接向 pager 平台写入、priority 硬编码，所有路由和抑制对它无效 (src: 同上)。这提醒一个原则：**降噪机制的有效性取决于是否所有告警都必须经过它**，存在旁路就等于机制不存在。

---

## 六、USE / RED / 四大黄金信号

### Q25. 三套方法论各自的适用边界？`[一手+理论]`

| 方法 | 维度 | 面向 | 适用 | 盲区 |
|---|---|---|---|---|
| **Golden Signals**（Google） | Latency / Traffic / Errors / Saturation | 服务 | 通用服务监控，4 个维度覆盖大部分诊断需求 | 对资源层瓶颈不够细；Saturation 在应用层往往难定义 |
| **RED**（Weaveworks / Tom Wilkie） | Rate / Errors / Duration | 服务，尤其微服务 | 快速搭建，每个服务三个面板就够 | 完全没有饱和度维度，看不到「还能撑多久」 |
| **USE**（Brendan Gregg） | Utilization / Saturation / Errors | 资源 | 查 infra 瓶颈：CPU、内存、磁盘、网卡、连接池 | 不面向用户体验，全绿也可能客户在投诉 |

（src: `rules/skills/bestpractice_traditional_sre_methodology.md` Layer 3）

`[一手]` 我的用法是分层配合，这正好对应我 top-down 的四个主体：**客户和业务那层用 Golden Signals 的 Latency / Errors**（这是 SLI 的来源）；**服务 owner 那层用 RED**（每个服务一致的三件套，便于横向对比）；**平台容量那层用 USE**（这也是 CPU 内存真正该出现的地方）。

关键判断：**USE 全绿不代表用户没事**。我在 g_slo_topdown 里写的原话是「一堆指标都绿，客户却在投诉，因为绿的是主机，痛的是请求」(src: `adhoc_jobs/dynamic_resume_site/content/growth/g_slo_topdown.md`)。所以 USE 不能作为顶层信号，它是诊断层。

### Q26. Saturation 到底怎么测？`[一手+理论]`

`[理论]` Saturation 是四大信号里最难的一个，因为它问的是「还剩多少余量」而不是「现在用了多少」。Gregg 的定义是「工作排队等待的程度」，所以最好的 saturation 指标往往是**队列长度或等待时间**，不是利用率。CPU 的 saturation 是 run queue 长度（load average）而不是 CPU%；磁盘的 saturation 是 I/O 等待队列而不是吞吐量；线程池的 saturation 是排队任务数而不是活跃线程数。

`[理论]` 为什么利用率不够：排队论告诉我们利用率超过大约 70% 之后尾延迟指数爆炸（M/M/1、M/M/c），所以「留 30% 余量」这条经验法则不是保守，是数学 (src: `rules/skills/bestpractice_traditional_sre_methodology.md` Layer 2)。这意味着 CPU 70% 和 CPU 90% 对用户体验的差别远不是线性的。

`[一手]` 我踩过的一个具体形态：memcached 没有 exporter，`current_connections` 和 `listen_disabled_num` 这些真正的 saturation 指标完全飞盲，我只能用 `container_file_descriptors` 做连接数的代理指标（正常 24，spike 时 54，连接数翻倍就开始 timeout）(src: `contexts/thought_review/nginx_waiting_latency_memcached_root_cause_20260408.md` §4)。这个案子的教训是**关键路径上的依赖如果没有 saturation 可观测性，它就是一个隐藏的容量天花板**，而你只能在它被撞穿之后才发现。

另一个 `[一手]` 的 K8s 具体坑：容器内存的 saturation 要看 `container_memory_working_set_bytes`，不是 RSS 也不是 usage，因为 OOM killer 的判据是 working set (src: `rules/skills/workflow_dv_monitoring_oncall.md` 高频踩坑 1)。

---

## 七、三支柱的成本模型与选型

### Q27. metrics / logs / traces 的成本模型分别是什么？`[一手+理论]`

| 支柱 | 成本随什么增长 | 主要成本项 | 我的一手数字 |
|---|---|---|---|
| **Metrics** | series 数（label 基数的笛卡尔积）× 采集频率 × retention | 内存（active series 的 index 与 head）+ 磁盘 | 1.2M active series、~80K samples/sec；热存储 3 月 ~250GB（约 4 倍压缩），冷存储 S3 5 分钟降采样 180 天 ~25GB (src: `interview-3-monitoring.md:52-53`) |
| **Logs** | 原始字节数 × retention，加查询时的扫描量 | 存储 + 查询计算 | 已知瓶颈：Loki 在高流量下全量扫描慢 (src: `interview-3-monitoring_reference.md:153`) |
| **Traces** | 请求数 × span 数 × 采样率 | 存储 + 采集侧开销 | `[理论]` 我没有跑 trace，这是外环 |

`[理论]` 三者的关键区别不是价格而是**成本随什么维度增长**：metrics 的成本和请求量几乎无关（1 QPS 和 10K QPS 的 series 数一样），logs 和 traces 的成本和请求量成正比。这决定了它们的用法：metrics 可以全量常开，logs 和 traces 必须做采样或保留期取舍。

`[一手]` 我的分工原则是一句话：**metrics 负责发现，logs 负责证明**。metrics 触发告警，LogQL 从原始 access log 提取请求级真实延迟做交叉验证。LogQL 明确不做实时告警的基础，因为它依赖日志格式稳定、全量扫描慢、高流量下采样影响准确性 (src: `interview-3-monitoring_reference.md:116-117`)。

### Q28. 为什么选 Loki 而不是 ELK？`[一手]`

两个理由。第一，**label-based indexing 契合已有的 Prometheus label 体系**：我们的 metrics 侧已经统一了 `cluster` / `namespace` / `pod` / `app` / `tenant`，Loki 用同一套 label 做索引，Grafana 上从 metric 面板跳到对应日志几乎零摩擦，ELK 需要另建一套 mapping (src: `interview-3-monitoring_architecture.md:227-228`)。第二，**成本模型**：Loki 只索引 label 不索引正文，存储和索引开销远小于 Elasticsearch 的全文倒排。

代价我清楚：不做全文索引意味着**没有 label 约束的查询会变成暴力扫描**，所以 LogQL 的查询纪律（先用 label selector 收窄范围，再用 line filter）比在 ELK 里重要得多。这也是「Loki 在高流量下全量扫描慢」这个已知瓶颈的直接来源。

`[一手]` Loki 的多租户实现：`auth_enabled: true`，每个查询必须带 `X-Scope-OrgID` header，我们分了 `prod` 和 `nonprod` 两个 tenant，规则是 dev/preprod 归 nonprod、prod/mgt/sandbox 归 prod (src: memory `reference_loki_config.md`)。为什么不按客户租户分 tenant：tenant 在 Loki 里是一个比较重的隔离单位，我们需要的 per-client 下钻是查询维度不是隔离维度，用 label 加 line filter 就够，每个客户一个 tenant 会让运维复杂度爆炸。

一个命名误导的坑：`gcp-uswest1-prod-a` 的 Loki tenant 是 `nonprod`（src: 同上， `rules/skills/workflow_dv_monitoring_oncall.md` 高频踩坑 3）。

### Q29. 没有 trace 你怎么做跨层定位？`[一手]`

诚实的前提：**trace 全链路是我的外环，我没有跑 OpenTelemetry**。我的替代方案是利用 ingress 这一跳天然携带的分段字段。

nginx 的 access log 和对应的 exporter 指标提供了四个时间字段：`request_time`（总）、`upstream_connect_time`（建连）、`upstream_header_time`（首字节 TTFB）、`upstream_response_time`（后端响应总耗时）。这等于在 ingress 这一跳免费拿到了一个粗粒度的 span 分解，而且覆盖率是 100% 不是采样，不需要应用改代码 (src: memory `reference_dv_ingress_latency_decomposition.md`)。

分段等式和判别规则：

```
request_time ≈ front_gap + upstream_connect_time + upstream_response_time

upstream_connect_time 高（>50ms）        → 网络链路 / 建连问题
request_time − upstream_response_time 高  → client 到 nginx 的前段
request_time ≈ upstream_response_time     → 时间全在后端（ratio ≈ 1.00）
```

它的局限我讲得很清楚 (src: `interview-3-monitoring_reference.md:103-104`)：多 upstream 时 `upstream_response_time` 是总和，分不出哪个慢；connection reuse 可能让 waiting 偏低；这是 ingress 视角，看不到后端内部；ingress 之前的代理层延迟不在 log 里。所以它是**第一层诊断工具而不是最终结论**。

补课方向：OTel Collector 架构、trace context propagation（W3C traceparent）、head sampling 与 tail sampling 的取舍、以及 exemplars 这个把 metric 直接关联到具体 trace 的机制，后者正好能补上我现在「metric 报了高延迟但找不到具体是哪条请求」的缺口。

---

## 八、Grafana dashboard 设计

### Q30. 一个面向排障的 dashboard 应该怎么组织信息层次？`[一手]`

我的答案是 **minimal good page** 标准，核心是用问题做准入而不是用指标做罗列 (src: `interview-3-monitoring_reference.md:136-137`)。

值班人看完首屏必须能回答三个问题：

1. 用户有没有受影响，严重程度多少
2. 最可能在哪一层（edge / 服务 / 依赖）
3. 最近有没有变更

超出这三个问题的都是 drill-down，不放首屏。执行上的关键动作是**先列 question 再想 panel，说不出这个 panel 回答什么问题就不加**。

「最近有没有变更」的集成方式很具体：用 Grafana annotation API，CI/CD 部署完成时打标记，ArgoCD 或 Flux 走 webhook 同理，panel 开启 annotation 显示之后所有图表自动出现部署竖线 (src: `interview-3-monitoring_reference.md:139-140`)。这一条的性价比被严重低估，因为「最近有没有变更」在真实事故里的命中率极高，而它是纯工程可以自动化的。

`[一手]` 更上一层的原则来自我的 top-down 观：**dashboard 的存在意义是回答问题不是展示数据，答不上问题的曲线就是噪声**；每个主体的 dashboard 不同，给客户看的面板上不该有 CPU，给 oncall 看的面板不该只有一条总可用率 (src: `adhoc_jobs/dynamic_resume_site/content/growth/g_slo_topdown.md`)。

### Q31. 你们实际的 dashboard 分层是什么样的？`[一手]`

按主体分层 (src: `interview-3-monitoring_architecture.md:100-117`)：

- **Minimal Good Page**：oncall 第一响应
- **Tenant SLA Overview**：per-tenant、per-region，客户视角
- **Service Drill-down**：app → pod → container
- **Latency Decomposition**：upstream vs waiting time
- **Cluster Capacity**：容量主体，CPU 内存在这里才登场

`[一手]` 排障时的实际决策树是**串行而不是并行**看的，这是一个我认为很重要的设计细节 (src: `rules/skills/workflow_dv_monitoring_oncall.md`)：

1. 先看 Waiting Latency（ingress 到 upstream 之间的等待），因为**这是最便宜的读数**，一眼就能同时回答「影响有多大」和「是不是网络问题」。高就直接走网络分支，不用再看 Upstream。
2. Waiting 干净再看 Upstream latency，高就是后端或 DB 慢。
3. 两者都干净但 Response Percentiles 还高，那就是夹在中间的 infra 层（ingress controller 本身、APISIX），常见原因是最近 reload 或 config push、controller CPU、连接饱和。

**为什么强调顺序**：dashboard 的价值不只在于有哪些 panel，还在于它是否隐含了一条正确的排查路径。三个面板并排放着让人自己挑，和明确写出「先看哪个、看到什么就分叉」，对新 oncall 的价值差一个量级。

### Q32. dashboard 有哪些常见的坑？`[一手]`

从我维护的踩坑清单里挑几条通用性最强的 (src: `rules/skills/workflow_dv_monitoring_oncall.md` 高频踩坑)：

- **模板变量选 `$__all` 会掩盖单点热点**。Node 资源面板必须选具体节点，选全部会得到 fleet 平均值，一个 node 打满在平均里完全看不见。这是「聚合掩盖局部」在 dashboard 层的形态，和我的 per-tenant 指标要解决的是同一类问题。
- **切换了一个模板变量之后，联动的其他变量可能失效**，导致某一行面板假性空白。假性空白比错误数据更危险，因为它看起来像「没问题」。
- **PromQL 永远加 cluster filter**。无 filter 的 `rate(...[1m])` 在 VM 上会跑全表。
- **Loki 驱动的面板不是实时的**（我们有一个流量分布面板带 1m/5m/10m 的 timeFrom），可以作 evidence 不能作 root cause。

---

## 九、三个第一性模型（用我自己的框架）

> 来源：`rules/skills/bestpractice_sre_reliability_models.md`。这三个模型是我用来收敛讨论的工具，下面写的是我怎么把它们用在自己的场景上。

### Q33. Availability 的概率分解，以及它为什么把 Detection 放在中心位置？`[一手+理论]`

分解式：

```
Availability = P(不出故障)
             + P(出了故障但快速检测) × P(检测后快速恢复或有损降级)
```

关键点是 **Detection（监控加告警）是容易被遗漏但不可或缺的环节，没有检测，recovery 和 degrade 都无从触发** (src: `rules/skills/bestpractice_sre_reliability_models.md` §1)。

`[一手]` 这个模型对我这个方向的意义是它给了监控工作一个**可以量化论证的位置**：可用性的第二项整个是乘在检测概率上的，所以一个检测不到的故障，你所有的 failover、降级、回滚投资在这次故障里的收益都是零。这是我向上论证 observability 投入时用的框架，比「监控很重要」有说服力得多。

它也解释了两件我做过的事为什么必要。**deadman's switch**：如果监控自己失效而不报告，`P(快速检测)` 会在你不知道的时候塌到 0，而 dashboard 上看起来一切正常。**假告警治理**：`P(快速检测)` 不只是「能不能检测到」，还包括「检测到之后人是否相信它」，一个 85% 是默认 P3 的 pager 会让真信号被当成噪声，这在数学上等价于检测概率下降 (src: `p_alert_gov.md`)。

手段按目标归类（这四类我用来做事故复盘的 action item 分类）：防故障发生用冗余和消除单点；控制故障半径用 isolation 和限流丢弃保护核心路径；缩短故障持续时间用 fast fail 和 recovery（重启、failover、回滚）；故障期间维持部分价值用 degrade，有损服务优于无服务 (src: 同上)。

### Q34. Overload 的 λ vs μ 坐标系，怎么用它区分 latency 问题和 capacity 问题？`[一手+理论]`

`[理论]` 第一个判定就是：**这是 latency 问题还是 capacity 问题**。用 λ（到达率）对 μ（处理率）作为统一坐标。当 λ > μ 时 queue 必然出现，此时要问四件事：queue 在哪里、有没有 retry amplification 或 retry storm、有没有 backpressure 或 rate limit、failure 如何传播（队列、级联超时、依赖放大）(src: `rules/skills/bestpractice_sre_reliability_models.md` §2)。

配套的分层模型用来收敛讨论：physical limits（latency / capacity / failure）→ system behavior（load / queue / propagation）→ control mechanisms（cache / queue / rate limit / retry / redundancy）→ abstraction leakage（跨层排障成本）(src: 同上)。

`[一手]` 我用这个坐标系解释过两个真实案子，它们正好是坐标系的两个不同区域。

**memcached 那个案子是 λ > μ 的典型**：ConfigMap 配了 `pool_size=10000`（每个 nginx worker 的连接池），后端只有 1 个 pod、10 个线程来接，λ 远大于 μ。queue 出现的位置是 memcached 的 accept queue，溢出后表现为 connect timeout 和 read timeout，然后通过「Lua 插件同步阻塞 nginx worker」这条路径把 failure 传播到了每一个请求的 `request_time` 上。这个案子里 control mechanism 完全缺失：没有 backpressure，没有 fail-open，超时值（1 秒）比它保护的请求的正常耗时（20 到 30 毫秒）大了一个多数量级 (src: `contexts/thought_review/nginx_waiting_latency_memcached_root_cause_20260408.md`)。

**galileo 那个案子恰恰不是 capacity 问题**：三段分解显示 connect 全程 1ms、ratio = 1.00，也就是 λ 和 μ 在网络链路这一层完全没有紧张，时间全花在后端单请求的处理上，这是一个 latency 问题不是 capacity 问题 (src: `contexts/galileo_latency_investigation_20260626/REPORT.md`)。**先做这个判定的价值是它决定了后面所有动作**：capacity 问题的解法是扩容、限流、backpressure，latency 问题的解法是优化单请求路径，两条路完全不同，判定错了所有努力都白费。

`[理论]` 我要补的一块是 Little's Law（`L = λW`，并发数 = 吞吐率 × 平均延迟）和排队论的 70% 利用率拐点，这两个在容量规划里比我目前用的经验法则更有力 (src: `rules/skills/bestpractice_traditional_sre_methodology.md` Layer 2)。

### Q35. Latency SLI 的四层分离，为什么它是我最常用的一个框架？`[一手+理论]`

四层：**SLI**（衡量什么）→ **Histogram**（怎么记录分布）→ **Quantile**（怎么查看分布中的统计值）→ **SLO**（对该指标在时间窗口内施加什么目标）(src: `rules/skills/bestpractice_sre_reliability_models.md` §3)。

推荐口径：`SLI = requests_under_threshold / valid_requests`，`SLO = SLI ≥ target over time window`；`P99 ≤ Xms` 更适合作为观测视角或补充视角，不要默认把 quantile 当成 SLI 本体 (src: 同上)。

`[一手]` 为什么这个分离对我特别有用：因为我踩过的两次分位数事故本质上都是**把不同层混在一起**造成的。

那次假 P99 告警把 Quantile 当成了 SLI 本体，于是一个纯计算产物（多实例采集错位加分桶插值偏差）被当成了系统行为，触发了 page (src: `oncall_track_record.md` case 7)。t-digest 把 5 秒尖刺抹成 0.3 秒那次是把 Histogram 层的实现细节（近似算法的尾部压缩）当成了透明的，于是在 Quantile 层读到的值和真实分布严重脱节 (src: memory `reference_dv_ingress_latency_decomposition.md`)。

一旦四层分开，每一层都有自己该问的问题：SLI 层问「这个指标是否代表用户体验」；Histogram 层问「bucket 边界是否覆盖了我关心的阈值、聚合算法有没有近似损失」；Quantile 层问「这个统计值可不可加、对极值敏感到什么程度」；SLO 层问「目标值和窗口是否可达、是否能算 error budget」。**这四个问题混在一起问就会得出「P99 高了所以出事了」这种既可能对也可能错的结论。**

一个具体推论我在 Q17 说过但值得重复，因为它是这个框架最实用的输出：**SLO 的阈值必须落在 histogram 的 bucket 边界上**，否则你的 SLI 计算里就永远含着一次插值。

---

## 附：本方向的一手 / 理论边界一览

| 主题 | 状态 |
|---|---|
| 指标类型与 rate 语义 | `[理论]` 扎实，无一手争议 |
| histogram 插值误差 | `[一手]` 两个方向都踩过 |
| t-digest / P100 失明 | `[一手]` 这是我最独特的洞察 |
| cardinality 治理 | `[一手]` 四条手段，但自陈是事后补的 |
| pull vs push / Federation 结构性问题 | `[一手]` 最强的一块 |
| remote_write 参数与失败模式 | `[一手+理论]` 机制清楚，参数级细节偏理论 |
| VM vs Thanos / Mimir | `[一手]` POC 加架构分析，`[理论]` Thanos/Mimir 无运维经验 |
| deadman's switch | `[一手]` |
| SLI / SLO / SLA 定义 | `[一手]` 理解来自 production 压力 |
| SLI 规格化（event vs time based） | `[理论]`，我的分母定义做得不严格 |
| error budget 数学 | `[一手]` 有具体数字例子 |
| 多窗口燃烧率完整体系 | `[一手]` 只落了 5m+30m 双窗口，`[理论]` 三档体系 |
| error budget policy 落地 | `[理论]` 五步路径，**制度侧完全没建成，这是中环** |
| symptom vs cause / page vs ticket | `[一手]` 有 30 天审计做支撑 |
| inhibition / grouping / dedup | `[一手]` |
| USE / RED / Golden Signals | `[一手+理论]` |
| Saturation 的正确测法 | `[理论]` 排队论，`[一手]` memcached 飞盲案 |
| 三支柱成本模型 | `[一手]` metrics 和 logs，`[理论]` traces |
| Loki vs ELK | `[一手]` |
| trace / OTel | `[理论]`，**外环补课项** |
| dashboard 设计与排障层次 | `[一手]` |
| Availability 概率分解 | `[一手+理论]` 我用它做投入论证 |
| Overload λ vs μ | `[一手]` 两个案子分别落在两个区域 |
| Latency 四层分离 | `[一手]` 两次事故都是混层造成的 |
| Little's Law / 70% 拐点 | `[理论]` 待补 |
