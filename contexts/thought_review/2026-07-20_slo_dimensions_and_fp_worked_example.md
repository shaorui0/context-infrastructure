# SLO 全局维度框架 + Feature Platform 实战推演

- 日期：2026-07-20
- 类型：方法论 / 复盘
- 关联 skill：`rules/skills/bestpractice_sre_reliability_models.md`（该 skill 目前只覆盖 latency SLI 四层拆分，本文补上「按服务形态选 SLI」这一层全局分类 + 一个完整落地案例）

---

## Part 1 — 全局视角：availability/latency 之外还有哪些 SLI

一句话结论：availability 和 latency 只是「请求驱动型服务」里最显眼的两个。完整的 SLI 谱系还有一批，**该关注哪些取决于服务形态（请求型 / 数据管道型 / 存储型）**。与其记「还有哪些指标」，不如记这套决策法：

> 先问服务是哪一类 → 再从 {availability, latency, throughput, correctness, freshness, coverage, durability, consistency} 里挑出对这类服务「用户真正会痛」的 2–4 个立 SLO，其余降为观测视角。

Google SRE 原则仍然成立：**SLI 宁缺毋滥**，指标越少、越贴近用户体验，SLO 才越有约束力。

### 1.1 请求驱动型服务：被 availability/latency 掩盖的维度

- **正确性 / 质量（Correctness / Quality）**：返回 200 且够快 ≠ 结果对。推荐乱序、风控漏判、缓存脏数据，在 availability+latency 上全绿。口径 `正确响应数 / 有效响应数`，通常靠离线对账 / 采样标注测，不能只靠在线指标。（FP 场景：detection API「返回了」和「判对了」是两回事。）
- **吞吐量 / 容量（Throughput）**：与 latency 正交，不是对立面。可以延迟达标但吞吐撑不住峰值。接 λ vs μ 坐标系——要不要对「峰值 QPS 下仍满足 latency SLO」立目标，是容量治理入口。
- **饱和度（Saturation）**：Golden Signals 第四个。CPU/内存/连接池/队列深度水位。是**领先指标**（先爆，availability/latency 才劣化），适合做早期预警而非终态 SLO。

### 1.2 数据管道 / 异步系统：主导维度换掉

（Kafka consumer、ReplayTask、MirrorMaker、监控 pipeline 等，不该用 request-latency 当核心 SLI）

- **新鲜度（Freshness）**：数据从产生到可用的延迟。consumer lag、端到端时延本质都是 freshness SLO。
- **覆盖度 / 完整性（Coverage）**：`成功处理量 / 应处理总量`。丢事件、跳分区、replay 漏段，availability 看不出来，coverage 才抓得到。
- **正确性**：处理逻辑对不对，同样是独立维度。

### 1.3 存储 / 有状态系统：再加两个

- **持久性（Durability）**：写进去的数据不丢。存储系统头号 SLI，和 availability 两码事（可用但丢数据 vs 不可用但不丢）。
- **一致性（Consistency）**：副本间、跨区、读写之间的一致程度。YB / CH / Redis 多副本直接相关。

### 1.4 两个「元维度」（比单个 SLI 更全局）

- **Detection（可检测性）**：`Availability = P(不出故障) + P(出故障但快检测)·P(快恢复/降级)`。没有检测，前面所有 SLI 都是事后诸葛；它不是业务 SLI，但决定所有 SLI 的 MTTR。
- **成本 / 效率（Cost Efficiency）**：现代 SRE 把「单位请求成本」「资源利用率」当准 SLO。可靠性可以无限堆冗余买到但不可持续，效率是给可靠性加的预算约束。

---

## Part 2 — 实战推演：Feature Platform 的 SLA/SLI/SLO/Error Budget

> 背景：分析 `agents/sre_oncall_triage_skill/tmp/sla.json`（SLA - Batch & RealTime dashboard，308KB）。dashboard 已把原材料摆出来：realtime 侧是 ingress/APISIX 的 success ratio + 延迟分位数；batch 侧是五个 job 的 start/finish 时间 + E2E < 24h 判定。

### 2.0 先纠正一个概念错位

dashboard 名叫 SLA，但测的**全部是 SLI**。四个概念是一条链：

- **SLI** = 测什么
- **SLO** = 内部目标
- **SLA** = 对客户的合同承诺
- **Error Budget** = SLO 的补集 + 一套消费政策

关键约束：**SLA 必须比 SLO 松**（SLO 99.95% → 对外只承诺 99.9%）。这个 gap 就是在客户投诉之前自我修正的缓冲区。

### 2.1 SLI：FP 应该测四条

FP 有两个形态，SLI 天然分两组。

**Realtime（Detection / Update API）：**

1. **可用性** = `good requests / valid requests`，在 ingress 层测（离客户最近，dashboard 位置对）。关键是把 good/valid 定义钉死：
   - `5xx` → failure
   - `400` → 客户端错误，从 valid 剔除，而非算成功
   - `429` → 若是客户超合同 QPS，剔除出 valid 合理
   - `499` → 最危险，客户端提前断开往往是你太慢；panel 现在把它排除在 SLA 外 = 给自己留盲区，至少要单独盯
2. **延迟** = `阈值内完成请求 / valid requests`（如 detection < 300ms 比例）。按四层模型，`P99 ≤ Xms` 只是观测视角，不要拿 quantile 当 SLI 本体。阈值按 API 分开定，detection 和 update 延迟预算不该同一个数。

**Batch：**

3. **Freshness** = E2E（rawlogconverter 开始 → frontendresultwriter 结束）在 24h 内完成的天数比例。dashboard 现在是 `good if <24h` 的布尔表格，**缺时间窗口上的比例化**，没有比例就没法挂 SLO。
4. **正确性（可选）**：rt-batch comparison 的 precision/recall 已在测。更像产品质量指标，第一版 SLO 可先不纳入，但这是 FP 区别于普通 API 服务的地方，长期值得升格。

### 2.2 SLO：一组可直接讨论的起点数字

| SLI | SLO 建议 | 窗口 |
|---|---|---|
| Detection API 可用性 | ≥ 99.95% | rolling 30d，per client |
| Detection API 延迟 | ≥ 99% 请求 < 300ms | rolling 30d |
| Update API 可用性 | ≥ 99.9% | rolling 30d |
| Batch freshness | 30 天内 ≥ 29 天 E2E < 24h | calendar month |

- 数字要用 **6–12 个月历史数据校准**：取历史表现的合理下沿，而非拍理想值。dashboard 里 90d stat panel 已有，拉出分布看一眼，SLO 定在「正常月份轻松达到、事故月份会击穿」的位置。
- **per client 维度必须保留**：FP 是多租户，聚合 SLI 会把小客户的完全不可用稀释成看不见的小数点。

### 2.3 SLA：对外承诺，比 SLO 降一档

SLA 是商务文件，不是监控产物。三件事：

- **承诺指标**：如 Detection API 月度可用性 ≥ 99.9%
- **测量口径**：以 DataVisor 侧数据为准，除去客户侧网络和超合同 QPS 流量 —— 最易被忽略，但决定扯皮时用谁的数据
- **违约补偿**：service credit 阶梯

延迟通常不进 SLA，或只进很松的版本，因为控制不了客户到你的网络链路（dashboard 里 `Waiting Latency between Ingress and Upstream` panel 的意义就是切分这个责任边界）。

### 2.4 Error Budget：SLO 的补集 + 消费政策

- 99.95% / 30d → 折算 **21.6 分钟**不可用，或 0.05% 请求量。Batch 侧更直观：**每月允许 1 天迟到**。
- 光有数字没用，价值在两个机制：
  - **Burn rate 告警替代静态阈值**：1h 窗口烧 14.4× 速率 → page；6h 窗口 6× 速率 → ticket。
  - **预算耗尽后果事先约定**：当月预算烧完 → feature/rule/config 变更冻结，只允许可靠性修复。FP 特有问题：**客户配置变更导致的 SLO 击穿算谁的预算**，需在政策里写明白。

### 2.5 现状最该修的一件事

同一个 `SLA (last 1h)` stat panel 挂了 4 条口径互不相同的查询（ES 计数、Loki recording rule、`status!~"5.."`、某组 12h panel 甚至把 499 算进成功）。四个查询给四个数 = **现在其实没有一个 canonical SLI**。

建议收敛成一对 recording rule：`fp:sli:good_total` / `fp:sli:valid_total`（按 client + api 打标签），dashboard、告警、月度 SLA 报告全部从这一对派生。**口径统一是 SLO 体系的地基，先做这个，再谈上面的数字。**
