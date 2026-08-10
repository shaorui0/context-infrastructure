# 方向 02：监控体系 / 可观测性 / SLO

> 私人备考材料，不脱敏。数字口径以 2026-07 的 `dynamic_resume_site` 与 `resume.tex` 为准，与 4 月 `interview-3-*` 冲突处已标 `⚠️ 口径漂移`。

---

## 这个方向我的一句话定位

我在一个 3 到 4 人的 SRE 团队里独立 own 可观测性这个领域，从零把 50 个 Kubernetes 集群的监控平台重建了一遍：把每周 OOM 两三次、全局视图最多滞后 45 秒的 Prometheus Federation 拓扑换成 VictoriaMetrics 推送式中心架构，1.2M active series、约 80K samples/sec，数据延迟压到 5 秒以内，切换全程没丢一条告警。但我认为这个方向真正值钱的不是搭栈，是两件认知：第一，监控设计必须自上而下从「谁在关心什么问题」推下来，把 CPU 摆到第一屏是层级错位；第二，告警系统是一个不做功就必然熵增的系统，所以治理的重点是准入控制而不是大扫除。我的短板也很清楚，SLO 的制度化落地（error budget policy、SLO review 会议）我只做到了工程侧的一半，制度侧偏浅。

面试时的一句话开场（可直接说）：

> "I owned the observability domain end to end in a 3–4 person SRE team: I replaced a Prometheus federation topology that OOMed weekly and trailed reality by up to 45 seconds with a VictoriaMetrics push-based platform across 50 Kubernetes clusters, 1.2M active series at ~80K samples per second, data lag under 5 seconds, and zero alert gaps through the cutover. The part I care more about is the alerting side: I audited the pager, found the entropy mechanism behind it, and rebuilt admission control instead of just deleting rules."

---

## 核心圈三环

### 内核：一手做过，扛得住 5 层追问

| 环 | 能力条目 | 一句话说明 | evidence 路径 |
|---|---|---|---|
| 内核 | Prometheus Federation → VictoriaMetrics 平台重建 | 50 集群、~1.2M active series、~80K samples/sec；lag 45s→<5s，消除每周 OOM；热存储 3 月 930GB→250GB；两周双写等价性门禁 | `adhoc_jobs/dynamic_resume_site/content/projects/p_vm_platform.md`；`work-contexts/career/profile/resume.tex:76-79`；`work-contexts/career/interview/interview-3-monitoring_reference.md:42-60` |
| 内核 | per-tenant SLI recording rules 与 label 一致性治理 | 先物化 SLI 族（QPS / error ratio / P95 / P99 / saturation / tenant SLI），按 `{tenant, cluster_group}` 键控；写统一 relabel 模板分发 50 集群，推动应用侧从 `client` 收敛到 `tenant` | `p_vm_platform.md`（How / Hard parts）；`interview-3-monitoring_architecture.md:122-282` |
| 内核 | 三层告警分级 + inhibition 因果链设计 | PAGER / HIGH / MEDIUM 三层与路由；PAGER 准入必须是可观测的用户影响；inhibition 只沿因果明确的链条做，刻意排除跨服务推测性抑制 | `interview-3-monitoring_reference.md:69-94`；`interview-3-monitoring_architecture.md:214-232, 284-322` |
| 内核 | 告警熵增机制分析（诊断与设计层） | 367 条 paging 规则 / 约 960 条每天 / 约 85% 默认 P3 的量化 baseline，四个结构性根因，以及「加告警免费、删告警受罚、失效无声」的机制论证 | `adhoc_jobs/dynamic_resume_site/content/projects/p_alert_gov.md` |
| 内核 | Latency 三段分解定位法 | `request_time ≈ front_gap + upstream_connect_time + upstream_response_time`，用 connect 段判网络链路、front gap 判前段、ratio≈1.00 判后端；galileo 实测 connect 全程 ~1ms、ratio=1.00，一句话定案「是 FP 不是网络」 | memory `reference_dv_ingress_latency_decomposition.md`；`contexts/galileo_latency_investigation_20260626/REPORT.md` |
| 内核 | 分位数与 t-digest 的失明边界 | exporter 的 `quantile="1.0"` 被 t-digest 把 5s 尖刺抹成 ~0.3s，查 P100 必须回原始 nginx 日志或 ClickHouse `req_time_max`，不能信聚合 | memory `reference_dv_ingress_latency_decomposition.md`（两个大坑之一） |
| 内核 | Loki 多租户日志侧与 LogQL 实战 | `auth_enabled: true` 双 tenant（prod / nonprod），promtail 打 `cluster/namespace/pod/container/app`；access log 与 error log 按时间戳 + client IP 对齐建立因果；LogQL 字面点用 `[.]` 不用 `\.`，永不用 `2>/dev/null` 吞查询错误 | memory `reference_loki_config.md`、`feedback_logql_regex_escape.md`、`feedback_loki_metric_debug.md`；`contexts/thought_review/nginx_waiting_latency_memcached_root_cause_20260408.md` |
| 内核 | 面向排障的 dashboard 层次与 disproof 设计 | minimal good page 的三问准入（用户受影响吗 / 哪一层 / 最近有变更吗）；SLA dashboard 的 Waiting → Upstream → Infra 三步决策树；把「快速证伪假告警」当成显式设计目标 | `interview-3-monitoring_reference.md:134-142`；`rules/skills/workflow_dv_monitoring_oncall.md`；`adhoc_jobs/dynamic_resume_site/content/integration/oncall_track_record.md`（case 7） |

### 中环：做过但浅，被追问时用这个口径

| 环 | 能力条目 | 一句话说明 | 被追问时的标准口径 |
|---|---|---|---|
| 中环 | **SLO 的制度化落地（本方向最大的诚实点）** | error budget policy 成文、烧光预算冻结发布、SLO review 会议机制，这三件我都没有建成 | 「我落地的是 SLO 的工程侧：SLI 的 recording rule 物化、per-tenant SLA 追踪、PAGER 必须有 SLO 基准这条准入规则。制度侧我没有建成，我们没有一份写下来的 error budget policy，也没有把「预算烧光就冻结发布」变成产品与 SRE 之间的正式契约，SLO review 也没有固定会议。原因是 SLO 定义需要 service ownership 支撑，这在我们的组织结构里不是我能单方面推成的，我当时选择先把可测量性做实。如果给我这个职责，我的第一步不是写 policy 文档，而是先挑一个有明确 owner 的服务做试点，把 SLI 规格化、budget 消耗上 dashboard、review 会议跑三个月，有了可信数据再谈冻结发布这种有牙齿的条款。」 |
| 中环 | 多窗口多燃烧率告警的完整工程化 | 我落的是 5m + 30m 双窗口都超阈值才升级 PAGER，不是 Google workbook 的 2% / 5% / 10% 三档完整体系 | 「我实现的是 fast burn 的双窗口确认：5 分钟窗口和 30 分钟窗口同时超阈值才升级为 PAGER，作用是滤掉瞬时抖动同时保留持续恶化的检测能力。理论上完整方案还要配 slow burn（1h/6h）做缓慢退化的提前预警，以及按预算消耗比例分档（2% / 5% / 10%）对应 page / ticket / 忽略。这部分我知道怎么设计，但没有在生产里跑满，因为前置条件是每条链路都有确定的 SLO 目标值，而我们当时的阈值有一部分是经验值。」 |
| 中环 | 告警治理的落地结果 | 我有实测 baseline 和分阶段验收门禁，没有治理后的对比实测 | 「我要说清楚这是什么状态：baseline 是实测的（367 条规则、约 960 条每天、约 85% P3、Top 3 三天 145 条），下降数字全部是我设的验收门禁目标（960 先到 400 以下再到 200 以下，P3 占比 85% 到 50% 以下再到 30% 以下），不是已达成的结果。Phase 1 的 config 止血打包成了两个可 review 的 PR。我更愿意讲这个项目的分析章而不是数字，因为熵增机制本身是可迁移的。」 |
| 中环 | VM 部署模式与容量规模的一致性 | 见下方 `⚠️ 待确认 A`，cluster 模式设计与 single 模式实测两个口径并存 | 「我的设计目标拓扑是 cluster 模式（vminsert ×2 / vmstorage ×3 副本因子 2 / vmselect ×2），容量按 50 集群 × 约 12 节点 × 约 2000 series/node 推出约 1.2M active series 和约 80K samples/sec。如果你要问某个时点线上实际跑的是哪种模式，我需要先确认再回答，我不想给你一个记错的拓扑。」（面试前必须自己核实清楚） |
| 中环 | Thanos / Mimir 的对比 | 做过 VM vs Thanos 的 POC 评估（写入吞吐、压缩率、运维复杂度），但没有运维过 Thanos | 「我做了 POC 对比，维度是写入吞吐、压缩率和运维复杂度，结论是在我们的规模下 VM 的运维成本更低，最终是团队共识决策。我没有在生产运维过 Thanos，所以我能讲清楚它的架构（sidecar + object storage + store gateway + compactor，全局查询靠 querier fan-out）和它为什么在我们这个规模显得重，但我不会假装有 Thanos 的一线运维经验。」 |
| 中环 | cardinality budget 的前置治理 | 我的治理手段是事后补的，自己在复盘里承认了 | 「治理手段是四条：tenant 级 recording rules 只覆盖核心 SLI、基础设施指标一律不带 tenant label、retention 分层 90d/30d/15d、定期 cardinality 审查。诚实的复盘是这些是被增长曲线逼出来的，cardinality budget 应该在第一天就存在。」 |
| 中环 | 五层故障定位路径（dashboard 设计模型） | SLA / Blast Radius / Saturation / Trace / Historical Trend 五层，每层只回答一个问题；Saturation 层的选型规则是选等待类指标不选用量类（Run Queue 不是 Usage，Lag 不是 Count） | 「已落地的是 minimal good page 三问准入和 SLA dashboard 的 Waiting → Upstream → Infra 三步决策树，这两个有真实 panel。五层模型是我把它们理论化之后的扩展，**我没有对现有 Grafana dashboard 做过逐层缺口核对，也没有改前改后的 MTTR 数据**。它的支撑是理论加一次间接实证：USE 方法和 Google SRE Book 对 saturation 的定义（两者术语不兼容但操作结论一致，都指向测等待而不是测用量），以及 GI 2026 那项 dashboard 与对话式界面的对比研究。如果给我这个职责，第一步是盘点现有面板落在五层的哪一层、标出缺失的层，我预判 Blast Radius 和 Historical Trend 最可能缺。」详见 `story_bank.md` S11 |
| 中环 | Alertmanager 的进阶特性 | dedup alias + `update_alerts`、per-team integration 拆分、auto-close 策略，这些我设计了但属于 Phase 2/3 | 「设计层面我很清楚为什么需要：没有 dedup alias 时同一个问题每次重新 firing 都生成一条新告警，这是 960 条每天里很大一块。四个 receiver 共享同一个 OpsGenie api_key 也让按团队路由不可能。这些是我方案里的 Phase 2，我不声称已经全部上线。」 |

### 外环：补课项，只讲理论不讲经验

| 环 | 能力条目 | 一句话说明 | 补课标记 |
|---|---|---|---|
| 外环 | OpenTelemetry 与分布式 trace 全链路 | 三支柱里 trace 这一支我是空的，我的跨层定位靠 metrics 分段 + 日志时间戳对齐替代 | 需补课：OTel Collector 架构、trace context propagation、sampling（head vs tail）、exemplars 把 metric 打通到 trace |
| 外环 | eBPF 可观测性 | Pixie / Cilium Hubble / Parca-agent 这类无侵入采集我没用过 | 需补课：kprobe/uprobe/tracepoint 差异、内核版本与 CO-RE、开销模型、和 sidecar 方案的取舍 |
| 外环 | Continuous profiling | Pyroscope / Parca / pprof 的常态化采集我没在生产跑过 | 需补课：CPU/heap profile 的采样原理、profile 与 metric 的关联方式、成本 |
| 外环 | Prometheus 长期存储的其他方案实操 | Thanos / Mimir / Cortex 都只有理论，object storage 上的索引与 compaction 模型没有一线经验 | 需补课：Thanos store gateway 的 index cache、Mimir 的 blocks + ingester 分片、和 VM 的取舍表 |
| 外环 | SLO 工具化生态 | Sloth / OpenSLO / Nobl9 这类把 SLO 声明式生成告警规则的工具我没用过 | 需补课：SLO as code 的规格（OpenSLO spec）、burn-rate 规则自动生成的模板 |
| 外环 | Grafana unified alerting | 我的告警在 vmalert + Alertmanager，Grafana 自带 alerting 的模型差异没实操 | 需补课：Grafana Alerting 的 rule/contact point/notification policy 模型与 Alertmanager 的映射关系 |
| 外环 | RUM 与端到端用户体验监控 | 我的 SLI 最外层止步于 ingress，真实用户侧（浏览器/客户端）没有覆盖 | 需补课：Core Web Vitals、client-side error 上报、真实用户视角与服务端 SLI 的差值来源 |

---

## 本方向 3 个最强 headline

**Headline 1：「Federation 的 45 秒延迟和每周 OOM 是架构属性，不是配置属性，任何调参预算都修不好。」**
承接 50 集群平台重建，1.2M active series、80K samples/sec，lag 45s→<5s，热存储 930GB→250GB，两周双写等价性门禁保证切换不丢告警。这句话的价值在于它展示的是「先判断问题在哪一层」的判断力，不是工具熟练度。
（src: `adhoc_jobs/dynamic_resume_site/content/projects/p_vm_platform.md`, `work-contexts/career/profile/resume.tex:76-79`）

**Headline 2：「告警系统服从热力学第二定律：加告警便宜且可见，删告警有风险且不可见，所以没有持续做功就必然积累噪声。治理就是把这份功制度化。」**
承接 367 条 paging 规则 / 约 960 条每天 / 约 85% 默认 P3 的实测 baseline，四个结构性根因，以及「清理改变状态，准入控制改变速率」这个区分。
（src: `adhoc_jobs/dynamic_resume_site/content/projects/p_alert_gov.md`）

**Headline 3：「先证明告警是假的，再解释它。」**
承接三段耗时分解（connect / front gap / upstream ratio）、t-digest 对 P100 天然失明、access log 与 error log 按时间戳加 client IP 对齐建立因果。这是我把「disproof 作为显式设计目标」这个观点变成方法的地方。
（src: memory `reference_dv_ingress_latency_decomposition.md`, `contexts/thought_review/nginx_waiting_latency_memcached_root_cause_20260408.md`, `adhoc_jobs/dynamic_resume_site/content/integration/oncall_track_record.md` case 7）

---

## ⚠️ 待确认（面试前必须自己核实）

**A. VM 部署模式与 active series 规模的两个口径并存。**
`p_vm_platform.md` 与 `interview-3-monitoring_architecture.md:55-57` 描述的是 cluster 模式（vminsert ×2 / vmstorage ×3 repl=2 / vmselect ×2）、~1.2M active series；而 `contexts/thought_review/victoriametrics_ops_review_20260402.md`（2026-04-02 实测）写的是 **Single 模式，单 Pod 承担所有角色，~793,000 active series，磁盘 4.7TB/6.2TB 已用 76%**；2026-06-26 的 galileo 调查报告里 Grafana datasource 名仍是 `vms-victoria-metrics-single-server`。`p_vm_platform.md:169` 的作者注也明确说这两个口径不同、没有混写。**面试如果被问「你们的 VM 拓扑」，必须先确认线上实际形态**，否则一个反问就穿。安全答法见中环第 4 条。

**B. 告警通知平台是 PagerDuty 还是 OpsGenie。**
4 月材料写 PAGER → PagerDuty（`interview-3-monitoring.md:45`），7 月的告警治理项目通篇是 OpsGenie（`p_alert_gov.md`）。两者可能是不同时期或不同团队通道，需确认。对外可以只说 "the paging channel"，避免说错产品名。

**C. nginx P100 memcached 案的修复后数据缺失。**
`nginx_waiting_latency_memcached_root_cause_20260408.md` §6 是修复建议表（P0 扩副本 / 加线程，P1 降 Lua read timeout、部署 exporter），**素材里没有任何修复后的 P100 实测对比**。讲这个故事只能讲到根因定案与建议，不能声称「修完 P100 从 1.00s 降到 X」。

**D. `1.00s` timeout 的确切来源未查到源码级证据。**
素材推断是 `lua-resty-memcached` 的 read timeout 默认值或 `global_throttle.lua` 里的显式设置，原文写明「需查 Lua 源码确认具体是哪个参数」。被追问时要说「我定位到 1000ms 这个量级的 socket read timeout，但没有把它落到具体配置项，这是这次调查留下的尾巴」。

**E. 「约 80% 的 page 不可操作」的口径。**
这个数字来自 30 天 Alertmanager 告警历史的人工标注审计（`interview-3-monitoring_architecture.md:288-293`），判定标准是「是否导致了 acknowledge → investigate → action」。它和 7 月材料里的「85% 是默认 P3」是两个不同指标，不能混着说成「85% 不可操作」。

---

## ⚠️ 命名冲突（面试中最容易口误的一处）

**两套都叫「五层」的模型，不要在同一段话里混用。**

- **dashboard 五层**：SLA / Blast Radius / Saturation / Trace / Historical Trend。回答的是排障时的认知路径，即按什么顺序提问。见 `story_bank.md` S11 与 `contexts/thought_review/2026-08-06_observability_dashboard_causal_troubleshooting_path.md`。
- **告警治理五层**：准入 / 判定 / 身份 / 投递 / 载荷。回答的是寻呼权限怎么分配。见 `contexts/daily_records/2026-08-05_2350_alert-governance-first-principles.md`。

说串的代价很具体：dashboard 这题本身是安全的（设计原则，无需数字支撑），但一旦被面试官顺着「五层」这个词带到告警治理，就会撞上 Phase 1 实测未落地、线上仍有约 2410 条常态 firing 这块。切回 S03 的口径（建立 / 识别 / 归因 / 设计，一个「降低了」都不说）。

---

## ⚠️ 口径漂移（旧 → 新，一律以 7 月为准）

**漂移 1：告警体系的成熟度。**
`⚠️ 口径漂移：4 月 interview-3 系列把三层告警（PAGER/HIGH/MEDIUM）+ multi-window burn-rate + inhibition 写成已建成的体系 → 7 月 p_alert_gov 的实测 baseline 显示 pager 侧仍是 367 条规则、约 960 条每天、约 85% 默认 P3、存在绕过 Alertmanager 的旁路脚本，准入门槛与 dedup 是待落地的 Phase 1/2。`
这是本方向最危险的一处。安全叙事：**设计与部分实现是我做的，全面收敛是进行中的治理工作**。不要把两份材料合并成「我建成了一个干净的三层告警体系」。

**漂移 2：severity 命名体系。**
`⚠️ 口径漂移：4 月 PAGER / HIGH / MEDIUM 三层 → 7 月告警治理材料里的实际字段是 OpsGenie priority P1 / P2 / P3，且严重度判据换成了偏离基线倍数（<2x 不告警 / 2-4x P2 不 @ / >4x P1 附 runbook）。`
讲的时候按主题选一套，不要在同一段话里混用两套词。

**漂移 3：告警噪声的度量口径。**
`⚠️ 口径漂移：4 月「约 80% 的 page 是 resource-centric 不可操作」（30 天人工审计）→ 7 月「约 85% 的告警是默认 P3」（priority 字段分布统计）。`
两个数字接近但含义完全不同，前者是可操作性，后者是分级失效。

**漂移 4：冷存储 retention 表述。**
`⚠️ 口径漂移：interview-3-monitoring_reference.md:20 写「cold 6mo ~25GB S3」→ 统一口径为 180 天、5 分钟降采样、约 25GB（interview-3-monitoring.md:53 与 p_vm_platform 一致）。`
量级相同，用 180 天这个说法。

---

## 同目录其他文件

- `story_bank.md`：10 个故事 + 每个 5 层追问防线（本方向最重要的增量）
- `fundamentals.md`：Q&A 形态基础回顾，每条标 `[一手]` / `[理论]`
- `questions.md`：24 题答题骨架，分 4 组
