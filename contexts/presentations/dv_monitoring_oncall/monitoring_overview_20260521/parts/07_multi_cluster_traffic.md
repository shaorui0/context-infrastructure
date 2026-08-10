# Multi-Cluster Traffic Distribution (`X2qhqpjSk`)

Title: **Multi-cluster traffic distribution** · Folder: General · Owner: runzi.yang@datavisor.com
Created 2024-08-15, last updated 2026-01-17 (v26). Default time range `now-1h`, refresh off.
Datasource: 全部 panel 都是 **Loki**（主 uid `mwGzR0VDz`，cluster-c panel 走 `M2q8i3Q7z`，疑似 backup / 跨 region Loki）。**没有任何 Prometheus 流量 metric** —— 所有 QPS / 分布数据都是从 `ingress-nginx` access log 里 `rate()` 出来的。

## 何时打开（典型 alert / 场景）

主用例不是 "latency alert for client X → which cluster" —— 而是 **"这个 client 的流量在 cluster A / B（同 region 双 cluster）之间是怎么分的"**。具体触发：

1. **客户报某 region 延迟 / 错误异常**，但 SLA 看板按 cluster 看不出单边问题 → 用这块看是不是流量被 ingress 路由到了非预期 cluster（如 cluster-b 全部流量切到 cluster-a）。
2. **Cluster A↔B 切流 / failover 验证**：人工切 traffic 或自动 failover 后，确认流量分布符合预期（A:B 比例、是否有残留）。
3. **客户 onboarding / interface 上线**：确认 `$interface`（request_url）实际打到的 cluster 和 upstream service。
4. **ingress-nginx upstream / alternative upstream（canary / mirror）调试**：FP / ASYNC 两个 panel 拆出 `proxy_upstream_name` vs `proxy_alternative_upstream_name`，看 Group0（主）vs Group1（alternative）的占比。

**确认/refine 原始假设**：原假设 "latency alert → which cluster serves X" 部分对。dashboard 能告诉你 client X 当前**流量**打到了哪些 cluster 以及占比，但 latency 归因要配合最下方的 P999 panel。它不替代 SLA dashboard，是一个"流量去哪了"的视角。

## 变量

| 变量 | 类型 | 来源 | 作用 |
|---|---|---|---|
| `cluster` | query (Prometheus `CA5qZASHz`) | `kube_node_info{kubernetes_cluster=~".*(a|b)"}` regex `kubernetes_cluster_groups="([^"]*)"` | 选 **cluster group**（一对 a/b cluster 的逻辑组，例如 `aws-apsoutheast1-prod`）。**不是单个 cluster**，是 group prefix，下方 `$cluster-a` / `$cluster-b` panel 会拼接 `-a` / `-b` 后缀。 |
| `client` | query (Prometheus `BXkAnTSNz`) multi+All | `label_values({__name__=~"(controller:Health_UpTime|record:loki_kubernetes_monitoring_request_1m_qps_ingress_nginx|prod_job_finish_time)", kubernetes_cluster=~"$cluster.*"}, client)` | 筛 client（默认 All）。注意 datasource 是 BXkAnTSNz（和 panel 的 Loki 不同 —— 是 mgt VM）。 |
| `interface` | query (Prometheus `CA5qZASHz`) multi+All | `label_values(... , request_url)`, regex `^(?!.*fp-ui).+$` | 筛 API path / 接口名，屏蔽 fp-ui*。 |

`$cluster` 这个变量名很关键 —— 它代表 **cluster group prefix**（如 `aws-apsoutheast1-prod`），底下三个时序 panel 标题是 `$cluster-a`、`$cluster-b`、`$cluster-c`，靠正则 `cluster=~"$cluster-a"` 等做匹配。

## 关键 panel + 查询

所有查询都基于 Loki 的 `ingress-nginx` 命名空间日志。共同过滤：
- `cluster!~".*sandbox-a|.*mgt.*"` —— 排除 sandbox 和 mgt cluster
- `namespace="ingress-nginx"`
- `client=~"$client"`
- `request_url!~"fp-[ui|rt].*"` —— 排除 fp-ui / fp-rt 实时 UI 流量
- 后两个 piechart + ASYNC + 时序 panel 还加上 `request_url=~"$interface"`

### Panel 9 · `Traffic distribution map on cluster` (piechart, 1m offset, 1m window)
最上方左侧。**整体 client 流量在各 cluster 上的占比**（不卡 interface）。
```
sum(rate({cluster!~".*sandbox-a|.*mgt.*", namespace="ingress-nginx",
          client=~"$client", request_url!~"fp-[ui|rt].*"}[1m])) by (cluster)
```
图例 `{{cluster}}`。**这是判断 "client X 当前打哪个 cluster" 的第一眼 panel**。

### Panel 11 · `[SVC][FP] Traffic distribution diagram within the cluster` (piechart, 5m offset/window)
拆到 **service / upstream 粒度**，两 query：
- A (Group0): `proxy_alternative_upstream_name=""`, `proxy_upstream_name!~".*-fp-async.*"`, group by `cluster, client, request_url, status_code, proxy_upstream_name`
- B (Group1): `proxy_alternative_upstream_name!=""`, 同样过滤 async, group by `... , proxy_alternative_upstream_name`

Group0 = 流量打到主 upstream；Group1 = 流量打到 alternative upstream（canary / mirror / failover）。**看 ingress 是否在做 alternative upstream 切流**。

### Panel 10 · `All Traffic distribution map on cluster` (piechart, 5m)
和 panel 9 类似但加了 `request_url=~"$interface"` 和 status_code 维度（不排除 alternative upstream）。
```
sum(rate({cluster!~".*sandbox-a|.*mgt.*", namespace="ingress-nginx",
          client=~"$client", request_url=~"$interface"}[1m]))
  by (cluster, client, request_url, status_code)
```
按 interface 过滤后的全量分布（含 status_code）。

### Panel 14 · `[SVC][ASYNC] Traffic distribution diagram within the cluster` (piechart, 5m)
和 Panel 11 同结构，但 `proxy_upstream_name=~".*-fp-async.*"` —— 只看 **fp-async** 服务。Group0 (refId A) 是 hide=true（默认隐藏），只显示 Group1（alternative upstream）。

### Panels 4, 6, 7 · `$cluster-a` / `$cluster-b` / `$cluster-c` (timeseries, 10m offset, unit reqps)
**这是 dashboard 的核心** —— 三个并列时序图，分别对应 group 内的 a / b / c cluster。
```
# panel 4 ($cluster-a)
sum(rate({cluster=~"$cluster-a", namespace="ingress-nginx",
          client=~"$client", request_url!~"fp-[ui|rt].*",
          request_url=~"$interface"}[1m]))
  by (cluster, client, request_url, status_code)
```
panel 6 同 with `cluster=~"$cluster-b"`；panel 7（cluster-c）查询是
```
sum(rate({cluster!~"$cluster-[a|b]", cluster=~".*-c", ...}[1m])) by (...)
```
**注意 panel 7 数据源是 `M2q8i3Q7z`（不同于 a/b 的 `mwGzR0VDz`）**，并且查询的 A 有 `hide:true` —— c cluster 数据默认不渲染，看起来是历史遗留 / 备用 region。

### Panel 13 · `Total traffic distribution latency` (timeseries, 10m, unit s)
最下方，按 `cluster, client, proxy_upstream_name, request_url` 计算 `request_time`（从 nginx access log 用 LogQL `pattern` 拆出来）的 P999 (refId A) 和 P100/Max (refId B)。
```
quantile_over_time(0.999,
  {namespace="ingress-nginx", client=~"$client",
   request_url!~"fp-[ui|rt].*",
   proxy_upstream_name!~".*sandbox.*|.*demo.*",
   request_url=~"$interface"}
  | pattern "<_> - <_> <_> \"<method> /<client>/<request_url> <protocol>\" <status> <_> <_> \"<_>\" <_> <request_time> [<proxy_upstream_name>] "
  | __error__ = "" | unwrap request_time [1m]) by (cluster, client, proxy_upstream_name, request_url)
```
这是**纯 access-log 派生的延迟**，独立于 SLA dashboard 的 controller-side latency，可用来交叉验证。

## 如何判断 client 当前打哪个 cluster

**主路径**：
1. 选 `cluster` group（如 `aws-apsoutheast1-prod`），选 `client`（如 `clientX`），interface 用 All。
2. **看 Panel 9 (Traffic distribution map on cluster)** 的 piechart —— legend / 切片名 = `{{cluster}}` 标签值，比例 = 该 cluster 的 ingress QPS 占比。
3. **看 Panel 4 vs Panel 6 ($cluster-a vs $cluster-b)** —— 两条时序 reqps 直接对比；如果其中一条接近 0、另一条吃掉全部，就是单边切流（或单边故障 + failover）。
4. **Panel 10** 加 status_code 维度，能进一步判断分到 a 的请求是不是大量 5xx（"流量在 a，但都失败了"）。

**关键 label**：`cluster`（ingress-nginx pod 上的 Loki stream label，形如 `aws-apsoutheast1-prod-a` / `-b`）。**没有显式阈值** —— 所有 piechart / timeseries 的 thresholds 都是默认的 `green / red 80` 模板配色，**没有业务含义**。判断要靠目视比例。

**间接信号**：Panel 11 / 14 的 `proxy_upstream_name` vs `proxy_alternative_upstream_name` 能告诉你 cluster 内 ingress 是否在做 canary / 切流（Group1 不为 0 即说明有 alternative upstream 在分流）。

## 接入 SLA latency triage 的位置

oncall 流程里这块是 **Phase 2 / 3** 的工具（不是 P0 入口）：

1. **Phase 0 入口**：SLA dashboard 看延迟报警在哪个 cluster / client。
2. **Phase 1 故障范围**：如果 SLA 报某 client 延迟但 cluster 维度看不出独占，**切到本 dashboard**：
   - Panel 9 / 4 / 6：流量是不是只打到了一侧 cluster？（隐性 failover）
   - Panel 13：access-log 派生 P999 vs SLA 的 controller P999 是否一致？不一致说明问题在 controller 之后（应用层）vs ingress 之前（网络 / DNS / SLB）。
3. **Phase 2 路由验证**：Panel 11 / 14 看 `proxy_upstream_name` 有没有意外漂移（比如 canary 没回滚、alternative upstream 拿了大头）。

**适用 alert 类型**：
- `latency_p99_high` for client X → 用 Panel 13 验证是不是 ingress 层就慢，用 4/6 看流量分布
- `5xx_rate_high` → Panel 10 (含 status_code) + Panel 11 (FP svc 维度)
- `failover_triggered` / 单 cluster 容量预警 → Panel 9 整体占比

## 已知坑 / caveat

- **不替代 SLA dashboard**：这里所有指标都来自 ingress-nginx access log 的 `rate()` / LogQL pattern unwrap，Loki 日志有摄入延迟（通常 30s–几分钟），不要用于秒级 triage。多个 panel 配了 `timeFrom: 1m/5m/10m` 的 offset，**默认看的就是过去某窗口的数据，不是 "now"**。
- **`$cluster` 变量是 group prefix，不是 cluster 全名**：第一次用容易误以为是单 cluster。底下三个时序 panel 靠拼 `-a/-b/-c` 后缀做 regex 匹配。
- **Panel 7 (`$cluster-c`) 默认 hide=true 且数据源是另一个 Loki (`M2q8i3Q7z`)**：很可能是历史遗留或跨 region backup，多数 group 没有 c cluster。不要因为 c panel 空就以为有问题。
- **Panel 14 ASYNC 的 refId A (Group0) hide=true**：只渲染 Group1（alternative upstream）。判断 async 主流量要手动取消隐藏 A。
- **变量 datasource 跨 VM**：`cluster` 和 `interface` 用 `CA5qZASHz`，`client` 用 `BXkAnTSNz`（mgt VM）。如果某个变量空了，先确认对应 VM 是否 reachable，不要怀疑 Loki。
- **过滤掉了 `fp-[ui|rt]`**：fp-ui / fp-rt 实时接口流量完全不在这个 dashboard 范围内，相关问题要去别处看。
- **没有 cross-region / failover 直接信号**：dashboard 只看同 group 内 a/b/c 分布。**跨 region failover（如 apsoutheast1 → useast1）这里看不到**，需要其他 dashboard 配合。最接近 failover 信号的是 Panel 9 占比突变 + Panel 11 alternative upstream 出现非零 Group1。
- **`proxy_upstream_name` 没排除所有 internal**：Panel 13 排除了 `sandbox|demo`，但其它 panel 没有；客户 demo 流量可能污染 piechart。
- **Loki `rate()` 在低 QPS client 上抖动大**：1m 窗口 + 小客户 = piechart 比例会跳动，看分布趋势别看瞬时切片。
