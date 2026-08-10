# SLA Dashboard

> **Dashboard**: `SLA - Batch & RealTime`
> **UID**: `p1KqfRAMk`
> **URL**: https://grafana-mgt.dv-api.com/d/p1KqfRAMk/sla-batch-and-realtime
> **Folder**: `F e a` (UID `9VPSGH_7k`)
> **Panel count**: 28 top-level panels (rows expand to ~60+ leaf panels)
> **Default time range**: `now-6h` → `now`
> **Owner / Last edit**: rui.shao@datavisor.com (created), runzi.yang@datavisor.com (last update 2026-05-20)

This is the **first dashboard to open** for any client-facing latency or availability incident in DataVisor's real-time stack. It combines Prometheus-based SLA (success/total counters) with Loki LogQL-based latency percentiles, and lets you walk the request path from K8s Ingress (nginx) → upstream (Feature Platform / `fp`) → backend detectors.

---

## 何时打开（典型 alert / 场景）

打开这个 dashboard 的典型触发：

1. **客户报实时 API 慢 / 超时** — "我们在 `/clientEvent` 或 `/detection` 看到 P99 飙升"
2. **Ingress / Feature Platform p99 latency spike alert** — VM/Grafana alert 关于 `kubernetes_monitoring_request_total_ingress_nginx` 5xx 或 latency
3. **SLA breach（10m / 1h / 12h / 24h SLO 跌破阈值）** — 几乎所有 SLA stat panel 都用 `client` 维度，复盘时第一眼看这里
4. **499 暴涨** — "Non-200 QPS returned to client" 显示 499（client close），用来区分是不是「客户端 timeout」而不是服务端故障（499 不计入 SLA）
5. **客户端报 timeout / 网络问题** — 用 "Waiting Latency between Ingress and Upstream" 区分是 datavisor 内部还是网络层问题
6. **Batch 没出结果 / 出晚了** — 翻到 Batch row，看 `End 2 End (good if <24 hours)` 和每个 batch job 的 start/finish 时间
7. **RT vs Batch 检测一致性问题** — 翻到 Batch row 下的 "Real-time and Batch Detected Users" 系列
8. **APISIX 灰度切换后 SLA 异常** — `E2E for APISIX` row 单独展示 APISIX 数据源

**不适合**这个 dashboard 的场景：
- 单个 pod 的 CPU/Memory（去 K8s pod dashboard）
- DB / queue 内部健康（去对应组件 dashboard）
- Loki/Promtail 抓取健康（去 Loki monitoring dashboard）

---

## 变量与前置选择

5 个 template variables，**进 dashboard 第一件事是选对它们**，否则所有 panel 要么空、要么把所有 client 叠加成一坨：

| 变量 | 类型 | 作用 | 典型值 / 选错的后果 |
|---|---|---|---|
| `PromDs` | datasource | 选 Prometheus datasource（VictoriaMetrics）。Realtime / Batch / Sandbox 分布在不同集群，选错会"没数据" | `prod-vm`, `nonprod-vm` etc. **客户在哪个 cluster 就选哪个** |
| `client` | query | 主 client（tenant）筛选。99% 的 panel 用 `{client="$client"}` 硬绑定 | 客户名（如 `acme`, `wepay`）。**选错 → 整页空白或拉别人的数据** |
| `sandbox_client` | query | 仅用于 **Sandbox row** 内的 panel（`*_sandbox_*` metric / `apisix_monitoring_sandbox_*`） | 沙盒 client 名；prod 调试不需要管 |
| `pipeline` | query | UML / SML / Detection row 用的 pipeline 维度（区分一个 client 的多个 pipeline） | `prod`, `default`, or 客户特定 pipeline 名 |
| `Batch_Pipeline` | query | Batch row 专用 pipeline，与 `pipeline` 不同（batch 通常独立 pipeline） | `prod_batch` 等 |

**Gotcha**：`client` 和 `Batch_Pipeline` 没联动。如果只切了 `client`，`Batch_Pipeline` 还停在上一个 client 的值，Batch row 会空白且 panel 不报错 —— 容易让人误以为 batch 挂了。**切 client 后必须重新挑 `Batch_Pipeline` 和 `pipeline`**。

---

## Dashboard 结构

按 row 从上到下的逻辑顺序（顶层 panel 顺序来自 `mcp__grafana__get_dashboard_summary`）：

```
┌─ E2E (row 155)
│   ├─ Text: "E2E (K8s Ingress) for $client"  (panel 142)
│   ├─ SLA stat panels (10m / 1h / 12h / 24h / yesterday / 7d / 30d / 60d / 90d)
│   ├─ QPS from Ingress           (131, timeseries)
│   ├─ SLA from Ingress           (130, 12 queries — 不同 window)
│   ├─ Total QPS by EventType     (347)
│   ├─ Total QPS by EventType with API (357)
│   ├─ Non-200 QPS returned to client (194) ← 看 499 / 5xx
│   ├─ Response Percentiles from Ingress (192, Prometheus recording rule)
│   ├─ Debug links                (text)
│   ├─ Response Percentiles from Ingress … from logql (359, LogQL)
│   ├─ Upstream latency graph (Feature platform) (371, LogQL)
│   └─ Waiting Latency between Ingress and Upstream (373, LogQL) ← 网络层 gap
├─ E2E for APISIX (row 397)        ← APISIX (灰度替代 ingress-nginx 的网关)
├─ Sandbox (row 361)               ← 用 $sandbox_client
├─ UML (row 157)                   ← User Modeling Layer (realtime detectors)
├─ SML (row 325)                   ← Stream Modeling Layer
├─ Detection (row 198)             ← 检测结果统计
└─ Batch (row 218)                 ← Batch pipeline 端到端时间 + RT vs Batch
```

---

## 关键 panel 解读

下面只挑 oncall 真正会看的 panel；每条给出：**名字 / 查询（sanitized） / 看什么 / 红线**。

### 1. SLA stat panels（10m / 1h / 12h / 24h / yesterday / 7d / 30d / 60d / 90d）

每个 stat panel 都跑 **多个并行 query 互相对照**（Prometheus 物化指标 + Loki recording rule + raw counter），因为同一个 SLA 数字有多套口径（Elasticsearch 历史指标、Loki 派生指标、ingress-nginx counter）。

**典型 query（SLA last 10m，最常用）**：

```promql
# A: Elasticsearch 历史口径（老的 SLA 物化指标）
sum(sum_over_time(es_ingress_1m_sla_count_client_upstream_succeed_value{client="$client"}[10m]))
/ sum(sum_over_time(es_ingress_1m_sla_count_client_upstream_total_value{client="$client"}[10m]))

# B: Loki 派生 recording rule（min 是为了抓最差的 1 分钟）
min(
  sum_over_time(record:loki_kubernetes_monitoring_request_1m_success_total_ingress_nginx{client="$client"}[2m:1m])
  / sum_over_time(record:loki_kubernetes_monitoring_request_1m_total_ingress_nginx{client="$client"}[2m:1m])
)

# C: Loki recording rule 聚合（剔除 backup upstream）
sum(sum_over_time(record:loki_kubernetes_monitoring_request_1m_success_total_ingress_nginx{client=~"$client", proxy_upstream_name!~".*backup.*"}[10m]))
/ sum(sum_over_time(record:loki_kubernetes_monitoring_request_1m_total_ingress_nginx{client=~"$client", proxy_upstream_name!~".*backup.*"}[10m]))

# D: Raw ingress counter（最贴近实时；剔除 dev、sandbox、demo、fp-ui、fp-rt）
sum by (client, job) (rate(kubernetes_monitoring_request_total_ingress_nginx{
  kubernetes_cluster!~".*dev.*",
  proxy_upstream_name!~".*(sandbox|demo).*",
  proxy_upstream_name=~"(prod|pci).*-fp.*",
  request_url!~"fp-(ui|rt).*",
  status_code!~"5..",
  client=~"$client"
}[10m]))
/
sum by (client, job) (rate(kubernetes_monitoring_request_total_ingress_nginx{
  kubernetes_cluster!~".*dev.*",
  proxy_upstream_name!~".*(sandbox|demo).*",
  proxy_upstream_name=~"(prod|pci).*-fp.*",
  request_url!~"fp-(ui|rt).*",
  client=~"$client"
}[10m]))
```

**SLA 成功口径**（重要 — 决定什么算「失败」）：
- **2xx / 200**：成功
- **4xx / 400 / 429**：通常算成功（客户端请求格式问题或限流，不归责给 datavisor）
- **499**：客户端主动断开（**不计入 SLA**，但会在 "Non-200 QPS" 显示）
- **5xx**：失败
- `proxy_upstream_name!~".*backup.*"`：剔除 backup upstream（fallback 链上的失败不算）

**看什么 / 红线**：
- A/B/C/D 几个并行数字**应该接近**。差距大说明某条数据管道（ES / Loki / raw）落后或漏数据
- < 99.9%（三个 9）通常是 SLO 红线；< 99% 已经是事故级
- 10m 跌 + 1h 没跌 = 短暂尖刺；10m 和 1h 都跌 = 持续性故障
- 12h / 24h 长时段也跌 = 必须发事故复盘 + 对客户解释

### 2. SLA (data referring last 24 hours of the date) — table 形式

`stat` 之外还有 1 个 **table panel (129)** 把多个口径并排展示，table 里有 A/B/C 三列（ES / Loki recording / raw ingress 按 proxy_upstream_name 拆分）。**oncall 用这个 panel 看「是哪个 upstream 拖低 SLA」**，因为 raw query 里有 `sum by (..., proxy_upstream_name, ...)`。

### 3. QPS from Ingress（131, timeseries）

```promql
sum by (request_url, proxy_upstream_name) (
  record:loki_kubernetes_monitoring_request_1m_qps_ingress_nginx{client="$client"}
)
```

**看什么**：QPS 趋势、突增突降。
- 突降 + SLA 跌 → 客户侧或 ingress 侧入口断了
- 突增 + SLA 跌 → 容量不足 / upstream 来不及处理
- 按 `request_url` 拆，能看出是不是某个 endpoint 单点暴涨（如 `/detection` vs `/clientEvent`）

### 4. SLA from Ingress（130, timeseries — 12 queries 不同 window 叠加）

把 10m / 1h / 12h / 1d / 7d / 30d 多个滚动窗口的 SLA 画在同一张图，**用来看 SLA 是「最近才跌」还是「一直在跌」**。

样例 query：

```promql
sum_over_time(record:loki_kubernetes_monitoring_request_1m_success_total_ingress_nginx{client="$client"}[10m])
/ sum_over_time(record:loki_kubernetes_monitoring_request_1m_total_ingress_nginx{client="$client"}[10m])
```

红线：和 stat panel 一致，看 10m 线突然脱离长 window 基线 → 实时事故。

### 5. Non-200 QPS returned to client（194）

```promql
record:loki_kubernetes_monitoring_request_1m_non_200_qps_ingress_nginx{client="$client"}
```

**Panel 标题强调**："499 error will show here but doesn't count in SLA"。
**看什么**：
- 499 暴涨 → 客户端 timeout / 主动取消，**通常是客户侧或网络问题**，不是 datavisor backend
- 5xx 暴涨 → datavisor 端故障，**和 SLA 一起跌**
- 4xx 暴涨 → 客户请求格式 / 鉴权问题

### 6. Response Percentiles from Ingress for $client (Approximate)（192, Prometheus recording rule）

```promql
record:loki_kubernetes_monitoring_requests_percentage_time_ingress_nginx_P50{
  client="$client",
  request_url=~".*(clientEvent|detection|update)"
}
# 同样的 metric, P75 / P90 / P95 / P99 / P999 / P100
```

这是**近似值**（recording rule 预聚合，便宜但精度有限）。Panel 标题写「Wait below graph for actual value」就是叫你滚到下面那张 LogQL panel 看精确值。

**看什么**：
- P50/P75 反映多数请求体验
- P99/P999 暴涨而 P50 稳定 → tail latency 问题（GC / 慢实例 / 个别 upstream pod 慢）
- 三条线一起涨 → 系统整体过载

**红线（DataVisor 内部惯例，需和团队 confirm 具体数字）**：
- `/clientEvent` 这类查询型 API：P99 < 300ms 通常 OK；> 1s 严重
- `/detection` 同步 detection 调用：P99 < 500ms，> 2s 严重

### 7. Response Percentiles from Ingress for $client from logql（359, LogQL）

**精确值版本**，6 条 query（P50/P75/P90/P95/P99/P100）跑在 Loki 原始日志上。这是 panel 192 的「actual value」对照。

完整 query（P50 为例）：

```logql
quantile_over_time(0.50,
  {namespace="ingress-nginx", client="$client",
   request_url=~".*(clientEvent|detection|update)",
   proxy_upstream_name!~".*sandbox.*|.*demo.*"}
  | pattern "<_> - <_> <_> \"<method> /<client>/<request_url> <protocol>\" <status> <_> <_> \"<_>\" <_> <request_time> [<proxy_upstream_name>] "
  | __error__ = ""
  | unwrap request_time
  [1m]
) by (client, proxy_upstream_name, request_url)
```

**怎么读**：
- `request_time` = nginx 记录的**总响应时间**（从收到 client 请求第一个字节到 nginx 把最后一个字节返回给 client，单位秒）
- 按 `proxy_upstream_name` 拆 → 看是哪个 upstream（prod-fp、pci-fp 等）慢
- 按 `request_url` 拆 → 看是哪个 endpoint 慢
- **比 panel 192 慢**（每次查 Loki 原始 log），但是 ground truth

**和 panel 192 不一致时**：相信 LogQL 的（recording rule 可能滞后或被聚合粗化）。

### 8. Upstream latency graph (Feature platform)（371, LogQL）

Panel description（dashboard 里直接写的）：
> "This graph to be used to monitor the latency between upstream and ingress, therefore infra team can quickly isolate the suspicious point to look at."

完整 query（P50）：

```logql
quantile_over_time(0.50,
  {client="$client", pod=~".*", stream=~"stdout|stderr",
   container="controller", namespace="ingress-nginx",
   request_url=~".*(clientEvent|detection|update)",
   proxy_upstream_name!~".*sandbox.*|.*demo.*"}
  | pattern "<_> - <_> <_> \"<method> /<client>/<request_url> <protocol>\" <status> <_> <_> \"<_>\" <request_times> <external_latency> <proxy_upstream_name> <_> <internal_endpoint> ..."
  | __error__ = ""
  | unwrap <upstream_response_time_field>
  [1m]
) by (client, proxy_upstream_name, request_url)
```

> **Note**：完整 pattern 在 MCP 返回中被截断，但 query 用同样的 `pattern` 解析 ingress-nginx controller 日志的 `request_times` / `external_latency` / `internal_endpoint` 字段，unwrap 出 **upstream response time**（nginx 转发到 fp upstream 收到完整响应的时间）。

**看什么**：
- **这是 Feature Platform（fp）upstream 自身的处理时间**，不包含 nginx 处理、不包含 client ↔ nginx 网络
- 如果这条线高 → **bottleneck 在 fp（backend）**，去 Feature Platform dashboard / fp pod 日志
- 如果这条线低，但 panel 7（总 request_time）高 → bottleneck 不在 fp，**在 client ↔ ingress 的网络**或 nginx 本身（→ 看下一个 panel）

### 9. Waiting Latency between Ingress and Upstream（373, LogQL）

Panel 标题完整名：「Waiting Latency between Ingress and Upstream (High latency likely means network issue between client and datavisor)」 —— **这是诊断 client 网络问题的金钥匙**。

Query 结构和 panel 8 几乎一样（同样 6 个 quantile），但 unwrap 的是 **`request_time - upstream_response_time` 的差值**（基于同一条 pattern 提取的多个字段相减），代表 nginx 在 client ↔ nginx 这段「等数据/等连接」的时间。

**完整 query（P50）**：
```logql
quantile_over_time(0.50,
  {client="$client", pod=~".*", stream=~"stdout|stderr",
   container="controller", namespace="ingress-nginx",
   request_url=~".*(clientEvent|detection|update)",
   proxy_upstream_name!~".*sandbox.*|.*demo.*"}
  | pattern "<_> - <_> <_> \"<method> /<client>/<request_url> <protocol>\" <status> <_> <_> \"<_>\" <request_times> <external_latency> <proxy_upstream_name> <_> <internal_endpoint> ..."
  | __error__ = ""
  | unwrap <waiting_latency_field>
  [1m]
) by (client, proxy_upstream_name, request_url)
```

**怎么读**（核心诊断逻辑）：

| 三个 panel 的状态 | 结论 |
|---|---|
| Total (panel 7) ↑, Upstream (panel 8) ↑, Waiting (panel 9) 平 | Backend / fp 慢 → 查 Feature Platform |
| Total ↑, Upstream 平, Waiting ↑ | **客户端 ↔ datavisor 网络问题**（客户网络 / CDN / 客户侧 timeout / TCP retransmit） |
| Total ↑, Upstream 平, Waiting 平 | nginx / ingress 自身（CPU/连接池/queue），去 ingress-nginx pod 看 |
| 所有都平，但 SLA 跌 | 是 5xx/499 占比问题，不是延迟问题 → 回去看 panel 5 |

---

## Latency 链条诊断流程

完整的 client → backend 链条：

```
 Client (browser/SDK)
    │   (client network, CDN, customer-side DNS/TCP)
    ▼
 K8s Ingress (nginx, namespace=ingress-nginx, container=controller)
    │   [request_time 从这里开始计数]
    │   (内部 LB / kube-proxy / service)
    ▼
 Upstream = Feature Platform (proxy_upstream_name 如 prod-*-fp-*)
    │   [upstream_response_time = nginx 等 fp 的时间]
    ▼
 Backend Detectors (UML / SML / rule_engine / user_stats / ...)
```

**Oncall triage step（5 分钟内）**：

1. **变量选对**：`PromDs` = 正确集群 (`prod-vm`)，`client` = 报障客户名。
2. **看 SLA stat 10m / 1h**：确认是否真的跌（注意 A/B/C/D 几个口径是否一致；不一致说明 recording rule / ES 落后，不一定是真事故）。
3. **看 QPS from Ingress**：QPS 突变 vs SLA 跌 → 流量类故障 vs 服务质量故障。
4. **看 Non-200 QPS**：分清 499（客户端 timeout）/ 5xx（backend 故障）。499 暴涨先怀疑客户网络。
5. **看 Response Percentiles from Ingress (logql)**：确认 latency 是不是真的高，哪个 `request_url` / `proxy_upstream_name` 最差。
6. **比 panel 7 vs panel 8 vs panel 9**：用上面那张表定位 backend / network / nginx 哪一段。
7. **下钻**：根据结论跳到具体 dashboard（见最后一节）。

---

## 常见误读 & 坑

1. **没选 `client` 就开看** — 大部分 panel 是 `{client="$client"}`，空 client 等于空数据 / 全集叠加，看到一堆 0 或一坨混线，**不是「监控挂了」**。
2. **`Batch_Pipeline` 没跟着 `client` 切** — Batch row 单独空白，会让人误判 batch 离线。
3. **499 当成事故** — 499 是 client 主动断开（客户端 timeout / 浏览器关页面），**不计入 SLA**。dashboard 上的 SLA 数字不会因为 499 跌；但 "Non-200 QPS" panel 会显示 499，容易让人误以为 backend 出事。
4. **多个 SLA 口径轻微不一致 ≠ 故障** — A（ES）/ B（Loki min）/ C（Loki sum）/ D（raw counter）四套口径有不同延迟与聚合方式。差 0.01% 正常；差 1% 以上才值得查 recording rule 落后。
5. **Panel 192（recording rule percentile）不是 ground truth** — 标题已写 "Approximate"。判事故和对客户解释**必须**用 panel 359（LogQL ground truth）。
6. **Upstream latency (panel 371) 只覆盖 fp upstream** — 名字写 "Feature platform"，过滤 `proxy_upstream_name=~"(prod|pci).*-fp.*"`。其他 upstream（rtcontroller、apisix sandbox）不在这张图里 → 去对应 row 看。
7. **APISIX row 是新网关，部分 cluster 才有** — 老 cluster 还是 ingress-nginx，APISIX query 会空。看到 APISIX row 全空不要慌，先确认客户所在 cluster 是否启用了 APISIX。
8. **`record:loki_*` 是 Loki recording rule 物化成 Prometheus metric** — 不是查 Loki，是查 Prometheus（datasource `PromDs`）。如果 Loki 那套 ruler 挂了，所有 `record:loki_*` panel 会冻结；这时去看 raw `kubernetes_monitoring_request_total_ingress_nginx`。
9. **`min(... [2m:1m])` 是按 1 分钟 subquery 然后取最差** — 一些 SLA stat 的 B query 用 min，**故意把最差的 1 分钟拎出来**。这意味着你看到的"SLA = 99.2%"可能是 10 分钟里有 1 分钟 92%，其余 9 分钟 100%。不是平均值。
10. **`status_code=~"200|400|429"` 把 400/429 算成功** — 看到 4xx 暴涨但 SLA 没跌，正常。如果客户特别在意 4xx，要换 panel 看 raw status code 分布。
11. **`proxy_upstream_name!~".*backup.*"` 剔除了 backup upstream** — 主 upstream 死、流量打 backup 上去成功，**SLA 仍可能 OK**。要看真实 backup 触发，去 ingress-nginx pod 日志 grep。
12. **dev cluster 数据被刻意排除**（`kubernetes_cluster!~".*dev.*"`）—— dev 环境跑 SLA 测试看不到，正常。

---

## 与其他 dashboard 的接力

诊断到某一段后，往这些地方下钻：

| SLA dashboard 上的现象 | 下一站 dashboard / 工具 |
|---|---|
| Upstream latency (panel 371) 高 | **Feature Platform dashboard**（fp pod CPU/mem、GC、connection pool） |
| Waiting latency (panel 373) 高 | client 侧网络排查；如果是同一 region 多 client 同时 → CDN/ELB dashboard |
| nginx 自身慢（Total ↑, Upstream/Waiting 平） | **Ingress-Nginx dashboard**（controller pod CPU、active connections、reload 频率） |
| UML/SML row 中 detection rate 异常 | **rule_engine / user_stats / controller pod logs**（Loki），及 detector 专属 dashboard |
| Batch row "End 2 End > 24h" 红 | 每个 Batch job (rawlogconverter / userstats / campaign / resultagg / frontendresultwriter) 单独 panel 看哪个 stage 卡，跳 **Spark / batch job dashboard** 看 executor logs |
| RT vs Batch 检测差异大（Batch row 后半段） | **rtbatchcomparison** detail dashboard（如有），或拉 batch detection result 与 RT 对账 |
| 499 暴涨而 fp / nginx 都没事 | 客户侧：拉对应 client 的 client-side log / 联系 customer success |
| APISIX row 异常 | **APISIX dashboard**（apisix monitoring 单独一套指标 `apisix_monitoring_*`） |
| Sandbox row 异常 | Sandbox 是测试环境，通常不 page；同 dashboard，把 `sandbox_client` 选对即可 |

**手边常用命令**（配合 dashboard 一起用）：

```bash
# 拉 ingress-nginx controller pod 实时日志 (Loki)
# tenant = nonprod-* 或 prod-*；见 reference_loki_config.md
{namespace="ingress-nginx", client="<CLIENT>", request_url=~".*(clientEvent|detection|update)"}
  | pattern "<_> - <_> <_> \"<method> /<client>/<request_url> <protocol>\" <status> <_> <_> \"<_>\" <_> <request_time> [<proxy_upstream_name>] "
  | request_time > 1
  | line_format "{{.request_time}}s  {{.status}}  {{.request_url}}  {{.proxy_upstream_name}}"

# raw ingress 5xx 拆 upstream
sum by (proxy_upstream_name, status_code) (
  rate(kubernetes_monitoring_request_total_ingress_nginx{
    client="<CLIENT>", status_code=~"5..", kubernetes_cluster!~".*dev.*"
  }[5m])
)
```

---

## 附：完整 panel 清单（按 row 排）

为了完整性，下面列出 dashboard 里所有 panel 的标题（来自 `get_dashboard_summary` + `get_dashboard_panel_queries`），不属于 oncall 第一现场但写代码 / 写 alert 时可能要参考：

**E2E row**：SLA (10m/1h/12h/24h/yesterday/7d/30d/60d/90d), QPS from Ingress, SLA from Ingress, Total QPS by EventType (with/without API), Non-200 QPS, Response Percentiles from Ingress (Prom approx + LogQL exact), Upstream latency (FP), Waiting Latency between Ingress and Upstream.

**E2E for APISIX row**：SLA (1d/7d/30d), QPS for APISIX, SLA from apisix, Response Percentiles from Apisix (`histogram_quantile` on `apisix_monitoring_requests_percentage_time_apisix_bucket`).

**Sandbox row**：Response Percentiles from Ingress for `$sandbox_client` (Prometheus recording rule), QPS from APISIX (sandbox), Response Percentiles from APISIX for `$sandbox_client` (histogram_quantile).

**UML row**：QPS from Nginx UML (es_nginx + loki recording rule), SLA from Nginx UML, Non-200 QPS from Nginx UML, Response Percentiles from Nginx UML (es_nginx_* + histogram_quantile on `promtail_custom_nginx_requests_time_percentage_bucket`), RTUserstat ExceedTimeLimit rate, JVM Memory Usage Percentage (user_stats_1/2, rule_engine_1/2/3, controller, yes_box), QPS Reported by Detectors (Ack/NonAck Events from each detector pod), UML Events Detected Per Minute, UML Detection Rate (Percentage), UML Total Detected Events Per Day, UML Avg Detection Rate Per day, UML Fail_Events (rtclientqueueferry Writes_Fail/Requests_Fail/Backend_Events_Ok), UML Events Received Since Last Reload, UML Number of Users Since Start, UML Number of Users Loaded on Reload.

**SML row**：（与 UML 类似的 detector / batch ferry 指标 — 详见 dashboard 内）

**Detection row**：`$client` Cron & Batch FPFerry Total Events / Error %, `$client` Total Rule Detection Per 2 min, `$client` Detection Number Per 2min For each ruleId.

**Batch row**：
- Stage 监控：Rawlog Size, Detection Result Size, Detection (dedupped_detecteduser), Event.Ok / Event.Skip / Event.Error, Userstats.NewEvent / Userstats.Detection, Group.Detection.Conf / Size / Type, Reasoncode, Userstats.Signal, Campaign.User
- RT vs Batch 对比：Real-time and Batch Detected Users, Precision and Recall of RT vs Batch, Detection Category - Detected Only in Batch / Only in RT (Stacked), Breakdown of Users only Detected in Batch, Detection Category RT vs Batch, Daily Detected User Score Distribution, RT Detected Group Sizes, Event Types Processed, Precision and Recall (NO ATO GROUPS)
- 端到端时间：**End 2 End (good if <24 hours)** + 每个 stage 的 start/finish 时间和耗时（RawLog, UserStats, Campaign, ResultAgg, FrontendResultWriter），所有都用 `prod_job_start_time{job="..."}` / `prod_job_finish_time{job="..."}`。

> Batch row 的 "good if <24 hours" 是 SLO：从 raw log 收到 → 检测结果写回，应当 < 24 小时；超过就是 batch SLA breach。

---

## 调查记录（这次提取的 caveat）

- 工具：`mcp__grafana__get_dashboard_summary` + `mcp__grafana__get_dashboard_panel_queries`（后者返回 108KB JSON，按 panel title 分组提取）。
- `get_dashboard_panel_queries` 返回的 query 字符串对很长的 PromQL 在 ~400 字符处被本地分析脚本截断（为了控制 context），但**所有 query 的核心结构、metric 名、label filter 都已经看到**。如果以后需要某个 query 的完整原文，重跑 `mcp__grafana__get_dashboard_panel_queries(uid="p1KqfRAMk", panelId=<id>)` 即可。
- Panel 371 / 373 的 LogQL `pattern` 在返回里被截到 `<internal_endpo` 截断；从两个 panel unwrap 的字段不同但 stream selector 完全一致这一点可以推断：371 unwrap 的是 upstream response time 字段，373 unwrap 的是 `request_time - upstream_response_time`（i.e. 「等数据」时间）。如果需要 100% 确认字段名，去 Grafana UI 看 panel 371/373 的 raw query 即可。
- 没用到 VictoriaMetrics MCP（这次只做 dashboard 静态分析；如果要验证某条 query 在当前数据上的实际值，下一步可以用 `mcp__victoriametrics__query` / `query_range`）。
