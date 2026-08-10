# Logging Dashboards

DataVisor 在 Grafana (`grafana-mgt.dv-api.com`) 上有两条主要 logging dashboard 路径：

- **通用日志面板** `Logging` (UID `9aBY8rWMz`) —— 任意 pod 日志的探索入口
- **Ingress-nginx 调试面板** `Debug logs for Ingress-nginx controller` (UID `HFAlVh2Nz`) —— HTTP 维度（client / status / latency）的入口

两者都跑在同一个 Loki 数据源：`Loki` (uid `mwGzR0VDz`)。还有一个 `Loki-legacy` (uid `M2q8i3Q7z`) 仅作历史备份。

---

## Generic Logging（9aBY8rWMz）

- URL: https://grafana-mgt.dv-api.com/d/9aBY8rWMz/logging
- 默认 time range: `now-5m → now`（很短，drill 时根据需要拉宽）
- 4 个 panel + 8 个 variable

**Variables**

| name | type | 作用 |
|---|---|---|
| `LogDs` | datasource | Loki 数据源选择（默认 `Loki` = mwGzR0VDz） |
| `PromDs` | datasource | Prometheus 数据源（给 `Pods Selected` 用） |
| `cluster` | query | k8s 集群（label `cluster`） |
| `namespace` | query | 命名空间 |
| `pod` | query | pod 名（支持 regex，默认 `.*`） |
| `container` | query | 容器名 |
| `level` | custom | 日志 stream，对应 Loki label `stream`（`stdout` / `stderr`），用来粗粒度过滤 level |
| `search` | textbox | 自由文本，传给 `|~` 做 regex grep |

**Panels & 查询**

1. `Pods Selected` (stat, Prom)
   ```
   count(kube_pod_info{kubernetes_cluster="$cluster", namespace="$namespace", pod=~"$pod"})
   ```
   纯计数：当前过滤匹配多少 pod，避免你输错 regex 把所有 pod 都拉进来。

2. `Log timeline` (timeseries, Loki)
   ```
   count_over_time(
     {cluster="$cluster", namespace="$namespace", pod=~"$pod",
      stream=~"$level", container="$container"}[1m] |~ "$search"
   )
   ```
   1m bucket 的日志条数；用于一眼看出日志爆发/停滞。

3. `Click me and then "Explore" to check details` (logs, Loki)
   ```
   {cluster="$cluster", namespace="$namespace", pod=~"$pod",
    stream=~"$level", container="$container"} |~ "$search"
   ```
   原始日志面板。标题在提示：选中后点 `Explore` 跳到 Loki Explore，灵活性最大。

**注意**：这个面板用 `stream=~"$level"` 来当 level 过滤，但 `stream` 只是 stdout/stderr 这种 IO 级别，**不是真正的应用日志等级**（INFO/WARN/ERROR）。要按应用级别过滤，得在 `$search` 框里写 `ERROR` / `WARN` 之类的 regex。

---

## Nginx Ingress Debug Logs（HFAlVh2Nz）

- URL: https://grafana-mgt.dv-api.com/d/HFAlVh2Nz/debug-logs-for-ingress-nginx-controller
- Tags: `ingress-nginx`, `loki`, `debug`
- 默认 time range: `now-1h → now`
- Owner: runzi.yang（2026-05-08 最近一次更新）

**Variables**

| name | type | 说明 |
|---|---|---|
| `cluster` | query | 来自 Loki label `cluster` |
| `client` | query | 来自 nginx ingress 日志解析出的客户标识（label `client`） |
| `interface` | query | 接口/路由维度（label `interface`，由 pattern 提取） |
| `request_time_operator` | custom | 用于阈值比较的操作符（`>`, `<`, `>=`...） |
| `request_time_prerequisite` | textbox | 阈值数值（秒），配合上面的 operator 例如 `> 1` |
| `upstream_response_time_operator` | custom | 同上，对 upstream 时间 |
| `upstream_response_time_prerequisite` | textbox | 同上 |

**共用 base selector**：所有面板都先按这个套路缩范围（注意排除了 `fp-ui`/`fp-rt` 类前端流量和 `sandbox`/`demo` upstream）：
```
{cluster=~"$cluster", namespace="ingress-nginx", client=~"$client",
 request_url!~"fp-(ui|rt).*",
 proxy_upstream_name!~".*sandbox.*|.*demo.*"}
```

**Panels**

| Panel | 类型 | 关键 query 形态 |
|---|---|---|
| Request Rate | timeseries | `sum by (client) (rate({...}[5m]))` |
| 5xx Error Rate | timeseries | 同上 + `status_code=~"5[0-9][0-9]"` |
| P95 / P99 Request Latency | timeseries | `quantile_over_time(0.95\|0.99, {...} | pattern "..." | __error__="" | unwrap request_time [5m]) by (client)` |
| Top 10 Slowest Endpoints (Avg Latency) | table | `topk(10, avg by (request_url) (avg_over_time({...} | pattern ... | unwrap request_time [$__range])))` |
| Top 10 Most 5xx Errors | table | `topk(10, sum by (request_url) (count_over_time({..., status_code=~"5[0-9][0-9]"}[$__range])))` |
| 5xx Logs | logs | base + `status >= 500 and request_time $request_time_operator $request_time_prerequisite` |
| 4xx Logs | logs | base + `status >= 400 and status < 500` + 同样阈值过滤 |

**Pattern 表达式**（所有 latency / status 查询都依赖它）：
```
<_> - <_> <_> "<method> /<client_back>/<request_url_back> <protocol>" <status> <_> <_> "<_>" <_> <request_time> [<proxy_upstream_name>] [<proxy_alternative_upstream_name>] <_> <_> <upstream_response_time> <upstream_status>
```
这是标准 ingress-nginx access log 格式，pattern 解析出 `request_time`、`upstream_response_time`、`status`、`upstream_status`、`proxy_upstream_name` 等字段，然后用 `unwrap` 转成数值做聚合。

---

## request_time vs upstream_response_time（核心区分）

这是排查慢请求时最容易踩的坑：

- **`request_time`** = 从 nginx 接到客户端**第一个字节** → 把响应**最后一个字节**写回客户端的总耗时。**包含**：
  - client → nginx 的网络 RTT / TLS / 慢客户端读取（slow consumer）
  - nginx 自己的处理
  - nginx → upstream 的所有时间
- **`upstream_response_time`** = 从 nginx 发出 upstream 请求 → 收到 upstream 完整响应的耗时。**只反映** nginx 后面的后端（FastAPI / Java 服务等）的真实时间。

**诊断启发法**：

| 现象 | 解释 |
|---|---|
| `request_time` 高，`upstream_response_time` 低 | 后端没事，问题在客户端网络/TLS/慢消费者，或者 nginx 自己卡 |
| 两者都高，且差不多相等 | 后端慢，去查 backend pod 的 logs / metrics |
| `upstream_response_time` 高但只有一部分 endpoint 高 | 看 `Top 10 Slowest Endpoints`，定位是哪个 API |
| `upstream_response_time = -` (空) | 请求根本没到 upstream（4xx 拒绝、upstream 不可达），看 `upstream_status` |

`P95 / P99 Request Latency` 这个 panel **只 unwrap 了 `request_time`**，所以单看它会把客户端慢算进去。怀疑后端慢时，把 query 复制到 Explore 改成 `unwrap upstream_response_time` 再跑一遍，更干净。

---

## 从 SLA dashboard drill 进来的流程

典型 oncall 路径（接 SLA 告警时）：

1. **SLA dashboard** 报某个 client / 接口 P99 超阈值或 5xx 抖动 → 拿到 `client`, `cluster`, 时间窗口
2. 跳到 **Nginx Ingress Debug Logs (HFAlVh2Nz)**，把 `$cluster`, `$client` 填进去，time range 对齐 SLA 报警的 ±5min
3. 先看 `5xx Error Rate` + `P95/P99 Latency` 两个 timeseries，确认 SLA 报警和这里能对上
4. `Top 10 Slowest Endpoints` 和 `Top 10 Most 5xx Errors` 定位**具体 URL**
5. 在 `5xx Logs` 面板设 `request_time_operator => `, `request_time_prerequisite => 1`（>1s 的请求）拿到样本日志
6. 看 `upstream_response_time` 判断锅在 nginx 还是 backend：
   - backend 慢 → 跳 **Generic Logging (9aBY8rWMz)**，把 `namespace` 填 backend 命名空间、`pod` 填解析出的 upstream pod，搜 ERROR/timeout
   - client/边缘慢 → 查 ingress controller 自身 metrics + 同集群网络

**什么时候用 SLA dashboard，什么时候切到 logging？**
- SLA dashboard 回答 **"出没出问题、严重程度多大"**（指标聚合视角）
- Logging dashboard 回答 **"哪些具体请求、为什么"**（日志样本视角）
- 一旦 SLA 报警，**几乎一定**要切 Nginx Debug Logs 拿样本，否则只有 P99 数字没有 root cause

---

## Loki tenant 选择陷阱

Loki 是 **多租户** 部署 (`auth_enabled: true`)，必须带 `X-Scope-OrgID` header。Grafana 数据源 `Loki` (uid `mwGzR0VDz`) 已经配好对应 header，所以 dashboard 里看不到，但**自己用 `loki_fetch.py` 或 curl 时要手动指定**。

| 集群 | tenant (`LOKI_ORG_ID`) |
|---|---|
| `aws-uswest2-dev-a/b`, `aws-*-preprod-*`, `gcp-uswest1-prod-a` | `nonprod` |
| `aws-uswest2-mgt-a`, `aws-*-prod-*`, `aws-*-pci-*`, `aws-*-sandbox-*` | `prod` |

**Rule of thumb**：dev / preprod → `nonprod`；prod / mgt / sandbox → `prod`。

**典型陷阱**：
- 在 Grafana dashboard 里选了 prod 集群，但用脚本复刻 query 时忘了切 `LOKI_ORG_ID=prod` → 直接返回空，以为日志没了
- `gcp-uswest1-prod-a` 名字带 `prod` 但 tenant 是 `nonprod`（历史原因），是最大的陷阱
- `Loki-legacy` (uid `M2q8i3Q7z`) 是旧实例，新告警/dashboard 不要再绑它

更详细的映射、curl 模板见 `~/.claude/projects/-Users-rshao-work-context-infrastructure/memory/reference_loki_config.md`。

---

## 典型 alert → 该看哪个面板

| 告警 | 第一站 | 第二站 |
|---|---|---|
| `IngressNginx5xxRate` / 客户 SLA 5xx | Nginx Debug Logs → `5xx Error Rate` + `Top 10 Most 5xx Errors` | 跳 backend Generic Logging |
| `IngressNginxLatencyP99` | Nginx Debug Logs → `P95/P99 Latency` + `Top 10 Slowest Endpoints` | 看 `upstream_response_time` 决定走 backend 还是网络 |
| Pod CrashLoopBackOff / Restart 告警 | Generic Logging：`namespace` + `pod`，`search` 填 `panic\|error\|fatal` | `kubectl describe` 看 events |
| 某 backend 服务报错率上升 | Generic Logging：`container=<svc>`，`search="ERROR"` | 必要时回到 Nginx Debug Logs 看入口流量分布 |
| 客户报告"接口慢但我没看到 5xx" | Nginx Debug Logs：把 `request_time_prerequisite` 设到客户 SLA（比如 `> 2`） | 对比 `upstream_response_time` 排除客户端网络 |
| 完全没日志 / 日志断流 | 检查 Loki tenant 是不是选错；检查 promtail pod 在不在 | `Log timeline` panel 看是不是真断了还是 selector 太严 |

**Generic Logging 不擅长的事**：按 HTTP 状态码、URL、客户维度聚合 —— 这些都用 Nginx Debug Logs，因为只有它 pattern 解析了 access log。反过来，Nginx Debug Logs 只看 `namespace="ingress-nginx"`，看不到后端 pod 日志，需要切回 Generic Logging。
