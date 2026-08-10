# FP Dashboard 设计规范草案：五层模型的落地版 + 给 agent 读的那一层

- 日期：2026-08-10
- 类型：设计规范草案
- 上游：`contexts/thought_review/2026-08-06_observability_dashboard_causal_troubleshooting_path.md`（五层认知模型）、`contexts/survey_sessions/ai_agent_observability_interface_gap_survey_20260806.md`（证据基础，下文小节号均指该报告）
- 已核实的本地事实来源：`rules/skills/workflow_dv_monitoring_oncall.md`、`adhoc_jobs/sre_oncall_triage_skill/knowledge/references/reference-fp-service-infra-reference.md`、`contexts/thought_review/2026-07-20_slo_dimensions_and_fp_worked_example.md`、`contexts/daily_records/2026-08-05_2350_alert-governance-first-principles.md`

---

## 0. 术语声明（先立规矩，否则后面每一句都会歧义）

本文的 saturation 采用 Google SRE Book 的宽定义，即「还有多少余量（headroom）」。队列类信号（Kafka lag、YugabyteDB RPC queue、MySQL threads_running）按 Brendan Gregg 的严格定义单独读作「已经在排队」。两套定义不混用，因为它们互不兼容（§2.1）。

实际操作上这个区分很有用：`utilization 逼近上限` 是领先信号，`已经在排队` 是滞后信号。前者用于容量决策，后者用于故障判定。

---

## 1. 认知模型五层，dashboard 分组四组

08-06 的五层模型（SLA / Blast Radius / Saturation / Trace / Historical Trend）是**提问顺序**，保持不变。但在当前技术栈上落成 dashboard 分组时，五层压成四组，原因是两处现实约束。

Blast Radius 在 FP 这个多租户场景里不需要独立一屏，它就是 SLA 层按 `client + api` 维度拆开的那个视图。合并的收益是第一屏就能同时回答「破了没有」和「谁破了」，代价是这一屏的 panel 数会涨，需要靠 ≤4 的硬上限约束住。

Trace 层在当前栈上没有分布式追踪基建，退化成 request_id 的日志关联，它天然属于可查询界面而不是固定面板，所以归入组件下钻组。这一点 08-06 已经写明，此处只是把它落到分组上。

Historical Trend 不做独立分组，改为每个 saturation panel 自带基线对比。理由是趋势脱离基线会在多租户环境里产生大量假阳性（某租户业务自然增长和资源枯竭前兆在斜率上无法区分），这也是 08-06 Part 3 第三条修正的要求。

| 分组 | 判定问题 | 目的 | panel 上限 | 依据 |
|---|---|---|---|---|
| SLA + Blast Radius | 对客户的承诺破没破，破在谁身上 | 决定是否升级、是否冻结变更 | ≤4，按 client + api 拆 | §8.2；SLA 应比 SLO 松一档（`2026-07-20_slo_dimensions_and_fp_worked_example.md:56`） |
| Golden Signals | 延迟、流量、错误哪个先动 | 定位到 client / ingress / FP / DB 哪一段 | ≤6 | §2.2 |
| Saturation | 哪个组件先耗尽余量 | 领先预警，不参与 SLO 判定 | 每组件 ≤3，**不设全局统一上限** | §2.6：无法模板化是结论而非缺陷 |
| 组件下钻 | 该组件内部具体哪里坏 | 确认根因 | 不设上限，走可查询界面 | §8.2：已知问题用固定 panel，未知问题用可查询界面 |

`panel 上限` 这一列是准入规则而不是审美偏好。答不出该组判定问题的面板，不进这一组。

## 1.1 分流树直接复用已实测的三步法

不新建。`workflow_dv_monitoring_oncall.md:57-77` 的三步法已经在 galileo 那次实战中用过：

```
SLA 告警
  → Waiting Latency（panel 373，dashboard p1KqfRAMk）高？
      是 → 网络或 client 侧，停在这一层
      否 ↓
  → Upstream latency（panel 371）高？
      是 → FP 或 DB 段。排查优先级 YugabyteDB(P0) > Ekata(P1) > MySQL(P2) > App(P3)
            （src: `reference-fp-service-infra-reference.md:115`）
      否 ↓
  → Response Percentiles 仍高？
      是 → ingress-nginx（HFAlVh2Nz）或 APISIX（0lpCu9kHk）
```

业务侧与 infra 侧的分流靠告警的 `team` 标签，不需要额外 panel。但这条路径**目前不可靠**：79 条规则缺 `team` 标签、91 条缺 `severity`（src: `2026-08-05_2350_alert-governance-first-principles.md:222`）。这是第 4 节列为地基工作的原因之一。

---

## 2. Saturation 层的组件级落地

**组件清单以本地权威文档为准，不采信记忆。** 已核实在 FP 栈内的组件（src: `reference-fp-service-infra-reference.md:22-56`）：MySQL、YugabyteDB（主备）、ClickHouse、Kafka（消费组 `velocity.prod_a`）。

**Redis 与 Doris/StarRocks 在 FP 权威参考文档里没有证据，不纳入本规范。** Redis 只出现在一份无关的 ingress NLB 端口配置里（`runbook-ingress-nginx-tcp-services-nlb-port-config.md:165`），Doris/StarRocks 只出现在 dcluster 那个独立项目里。这一条推翻了此前口头清单里的「据说涉及 Redis、Doris」。

| 组件 | 测什么 | Gregg 类型 | headroom 表达 | 现状 |
|---|---|---|---|---|
| K8s Pod / Node | working_set / limit；CFS throttle 比例 | utilization | limit − used | 已有，但不是 headroom 式呈现 |
| MySQL | threads_running / max_connections | 队列 | max_conn − current | 已有 |
| YugabyteDB | `yb_connection_pool_usage`；RPC queue | 前者 utilization，后者队列 | RPC queue = 0 即无饱和 | 已有（`reference-fp-service-infra-reference.md:101`），未做 headroom |
| Kafka | `kafka_consumer_lag{group="velocity.prod_a"}` | 队列（教科书典型） | lag → 0 | 已有，且是当前 firing 占比最高的家族（FPTopicsOffsetIncreaseZero 479 条，src: `2026-08-05_2350_...:278`） |
| FP 应用 JVM heap / 线程池 | heap 使用率（上限 20GB，src: `reference-fp-service-infra-reference.md:65`） | utilization | heap headroom | **未找到独立 panel** |
| ClickHouse | 待定 | 待定 | 待定 | **未找到 saturation 类指标** |
| 磁盘 IO | IO wait / IOPS | 队列 | 待定 | **未找到，只有容量告警** |

CFS throttle 比例这一项值得单独说：它是 K8s 场景下最接近 Gregg 定义的 saturation 指标，因为被 throttle 的时间就是「有活但拿不到 CPU」的直接度量，比 CPU usage 有信息量得多。

高利用率本身是成本效率目标而不是风险信号（§2.5）。YugabyteDB CPU 高和它是否真的在排队是两件事，现有告警多为绝对阈值，没有区分这两者。这是把「用量类」换成「等待类」这条选型规则最该先落地的地方。

另有一条从 memory 带过来的坑需要写进 runbook：YB/RocksDB 重启后头 60 到 120 秒 mmap 造成 working_set 接近 limit 的假象，要等 2 到 3 分钟看真实 steady state。saturation panel 如果直接按阈值告警，重启期间必然误报。

---

## 3. 给 agent 读的那一层

按 §8.3 的三条修正设计：做成 agent **按需调用的工具**，不做前置压缩管道；因果留给确定性组件；补入维度特征。

| 工具 | 输入 | 输出字段 | 回答什么 |
|---|---|---|---|
| `get_outcome_state` | service, client, window | current / baseline / delta / trend / slope / severity | 这个 outcome 算不算异常 |
| `get_saturation_state` | component, instance | current / headroom_to_threshold / class(utilization\|queue) / trend | 这个组件还有多少余量 |
| `get_causal_context` | alert 名或 service 名 | upstream_candidates / inhibited_by（确定性边表） | 谁是根因，谁是被波及的下游 |
| `get_dimensional_outliers` | metric, window | dimension / value / over_representation_ratio | 哪个维度值在异常子集里过度出现 |

`class` 这个字段是术语声明的落地：明确告诉 agent 这个数字是 utilization 还是队列，因为两者的解读方式不同（前者高不一定有问题，后者非零就有问题）。

`get_causal_context` 的定位是**替 agent 做掉因果推理**，不是给它推理素材（§6.2、§6.3）。`get_dimensional_outliers` 补的是 BubbleUp 式维度特征，与时序特征正交（§4.2）。

### 3.1 最省力的实现路径：因果图已经存在

**alertmanager 的 `inhibit_rules` 本身就是一张系统因果图。** 它沿数据管道逐级抑制，例如 `ClientRawlogUploadTime` 抑制 `DatavisorResultFeedbackTime`（src: `2026-08-05_2350_...:38-51`）。再加上部署依赖顺序 MySQL → YugabyteDB → ClickHouse → Kafka → FP（src: 同上 `:82-84`），解析成边表即可。

这意味着 `get_causal_context` 不需要新建因果图，数据已经在配置里，只是从来没有被暴露成结构化接口。这是整个设计里投入产出比最高的一项。

### 3.2 缓解 PromQL 标签错误

§5.5 显示 agent 写 PromQL 只有 69.1% 准确率，最大失败类别是标签用错。四个工具的内部实现固定使用已核实的查询模板，agent 只传 service / component / client 这类业务参数，不自己拼 label。这等价于把标签语义预先编码进工具签名，把 agent 最容易错的那一步移出它的职责范围。

### 3.3 实现位置

在现有 VictoriaMetrics MCP 与 Grafana MCP 之上加一层薄封装，不改动它们的配置。§4.1 已确认这两个 MCP 目前都是原样返回查询结果，本节的工具层正是补上缺失的特征提取层。

---

## 4. 与现有资产的差距，以及第一步做什么

可直接复用：SLA dashboard（`p1KqfRAMk`）的 outcome 层查询、第 1.1 节的三步分流树、alertmanager `inhibit_rules`（因果图种子）、已接入的两个 MCP。

缺口按严重度排序：

第一，**SLA 口径不统一**。同一个 stat panel 上挂了 4 条口径不同的查询（src: `2026-07-20_slo_dimensions_and_fp_worked_example.md:107`）。这是地基问题，因为第 3 节所有工具返回的数字都依赖它，不修则工具层从第一天就在输出错误答案。

第二，**告警元数据缺失让分流树不可靠**。79 条无 `team`、91 条无 `severity`。

第三，saturation 层多数组件缺 headroom 式指标，FP 应用层、ClickHouse、磁盘 IO 的 saturation 完全未找到。

第四，状态表示层完全不存在。

**第一步：把 SLA 的 4 套口径收敛成一对 recording rule** `fp:sli:good_total` 与 `fp:sli:valid_total`（`2026-07-20_...:109` 已提出这个方案）。地基，先做。

**第二步：`get_causal_context`**。成本最低（因果图数据已在 inhibit_rules 里），收益依据是本次调研最硬的正面证据：加入依赖图后 RCA accuracy@1 从 14.44% 提升到 42.22%（§6.1）。

---

## 5. 需要人来确认的不确定项

1. FP 是否真的使用 Redis 与 Doris/StarRocks。本地权威文档无证据，本规范按「不使用」处理。
2. ClickHouse 与磁盘 IO 的 saturation 指标是否存在但未被本次搜索命中。
3. 生产 SLO 数字是否已正式采纳。`2026-07-20_...` 里给的是「建议起点」而非已确认目标。
4. 「2410 条常态 firing」是 2026-08-05 的实测值，可能已变化，落地前需重测。
5. FP 应用层的线程池与连接池是否有独立于 MySQL Hikari 之外的监控点。

---

## 6. 与面试材料的关系

本规范是设计草案，**没有落地，没有 MTTR 对比数据**。面试口径见 `adhoc_jobs/senior_sre_interview_prep/02_monitoring_slo/story_bank.md` S11 与 README 中环条目，那里已按证据等级分级。特别注意 README 的「命名冲突」章节：本文的分层与告警治理五层是两套独立模型。
