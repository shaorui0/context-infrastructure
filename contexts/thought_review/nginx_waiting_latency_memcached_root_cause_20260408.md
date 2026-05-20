# Nginx Waiting Latency Root Cause Analysis

> **Date**: 2026-04-08
> **Cluster**: aws-uswest2-prod-a (prod.awsus)
> **Affected client**: sofi (47.5% of errors), plus bdc, syncbank, navan, cuoc, rippling, pefcu, taskrabbit
> **Symptom**: Waiting Latency between Ingress and Upstream P100 = exactly 1.00s, periodic spikes every 5-10 minutes

## 1. 问题现象

Grafana dashboard "SLA - Batch & RealTime" 的 "Waiting Latency between Ingress and Upstream" panel 显示 sofi/detection 和 sofi/update 两条线的 P100 周期性跳到精确 1.00s。P50-P95 完全正常（1-2ms），只有尾部延迟受影响。

该 panel 的计算逻辑：`waiting_duration = request_time - upstream_response_time`，即请求在 nginx ingress 层本身消耗的时间，不含 upstream 处理时间。

## 2. 调查思路

初始假设有三个方向：nginx 基础设施问题、客户端问题、fp（upstream service）问题。设计了三条并行调查线路同时推进。

### 调查线路 1：Loki 查 nginx 原始日志

目标：找到 waiting_duration > 500ms 的具体请求，看 status code、upstream addr、时间分布。

查询范围：`{namespace="ingress-nginx", container="controller", cluster="aws-uswest2-prod-a"}` 中包含 sofi 和 fp-8080 的日志行。

### 调查线路 2：检查 nginx ingress timeout 配置

目标：确认是否存在某个 timeout 配置值 = 1s。

方法：通过 Loki 查 nginx controller 的 ConfigMap 内容、nginx.conf 生成结果、per-ingress annotation overrides。

### 调查线路 3：VictoriaMetrics 查 fp pod 健康

目标：排除 upstream 本身不健康导致无法 accept connection 的可能。

方法：查 kube_pod_container_status_restarts_total、CPU、memory、HPA replicas。

## 3. 调查过程与发现

### 3.1 排除 fp（upstream service）

| 指标 | 结果 |
|------|------|
| Pod 数量 | 4 pods，HPA 稳定，无扩缩事件 |
| Restart | 0 |
| OOM | 0 |
| CPU | 平均 0.12-0.15 cores / limit 7 cores（利用率 2%） |
| Memory | ~22GB / 24GB limit，稳定无波动（JVM 大堆） |

fp 在 Kubernetes 层面完全健康。access log 中慢请求的 `upstream_response_time` 也正常（如 0.095s），HTTP 状态全部 200。等待时间全部发生在 nginx 层，不在 upstream。

**结论：fp 排除。**

### 3.2 排除 nginx proxy timeout 配置

从三个层级检查了所有 timeout 值：

**ConfigMap（全局默认）**：
- proxy_connect_timeout = 5s
- proxy_read_timeout = 60s
- proxy_send_timeout = 60s（默认）
- keepalive = 300s

**nginx.conf（实际生效）**：
- proxy_connect_timeout = 5s
- proxy_send_timeout = 60s
- proxy_read_timeout = 60s
- proxy_next_upstream_timeout = 0（unlimited）

**Per-Ingress Annotations**：
- 部分 ingress override 到 3600s（内部工具）
- 无任何 ingress 设置 1s timeout

**唯一出现 "1s" 的地方**：`global-rate-limit-window = 1s`，这是限流滑动窗口大小，不是 proxy timeout。

**结论：nginx proxy timeout 配置中不存在 1s 值。1s 不来自 proxy 层。**

### 3.3 发现真正根因：memcached timeout

#### 3.3.1 确认存在 request_time >= 1s 的请求

初次调查使用 `--from now-3h` 窗口（覆盖 05:21-08:21 UTC），未发现 request_time >= 1s 的请求（最大 0.634s）。扩大到 6h 窗口后，Grafana Explore 中执行以下查询：

```logql
{cluster="aws-uswest2-prod-a", namespace="ingress-nginx", container="controller", client="sofi", proxy_upstream_name="prod-fp-8080"}
  | regexp "(?P<request_time>\\d+\\.\\d+) \\[prod-fp-8080\\]"
  | request_time >= 1
```

返回 **9 条结果**，集中在 03:08-03:34 UTC：

| 时间 | client IP | request_time | upstream_response_time | waiting |
|------|-----------|-------------|----------------------|---------|
| 03:08:59.939 | 192.168.10.192 | 1.030 | 0.024 | 1.006 |
| 03:08:59.939 | 192.168.179.128 | 1.030 | 0.023 | 1.007 |
| 03:08:59.940 | 192.168.212.64 | 1.030 | 0.024 | 1.006 |
| 03:08:59.942 | 192.168.95.64 | 1.030 | 0.026 | 1.004 |
| 03:08:59.942 | 172.31.48.122 | 1.030 | 0.027 | 1.003 |
| 03:08:59.944 | 192.168.116.192 | 1.036 | 0.028 | 1.008 |
| 03:08:59.951 | 192.168.179.128 | 1.041 | 0.036 | 1.005 |
| 03:33:17.999 | 192.168.198.5 | 1.021 | 0.019 | 1.002 |
| 03:34:13.514 | 192.168.198.5 | 1.023 | ~0.02 | ~1.00 |

关键信号：
- 每条请求的 **waiting 都是精确 1.00x 秒**，upstream 处理时间（0.02-0.03s）完全正常
- 7/9 条发生在 **同一秒**（03:08:59），来自不同 client IP，说明是基础设施侧同时阻塞
- 时间点对应 memcached Event 1 CPU spike（03:10-04:12 UTC）的起始阶段
- **1.00s 是真实的 timeout 值，不是聚合效应**

#### 3.3.2 Error log 定位 memcached timeout

Loki error log 中发现了关键线索：

```logql
{cluster="aws-uswest2-prod-a", namespace="ingress-nginx", container="controller", stream="stderr"} |= "timeout"
```

```
[error] global_throttle.lua:105: throttle(): error while processing key: 'get' failed for ... timeout
[error] lua tcp socket connect timed out, when connecting to 10.96.150.232:11211
[error] lua tcp socket read timed out
```

#### 3.3.3 交叉验证：access log + error log timestamp/IP 对齐

```
# Access log（高延迟请求）
2026-04-08 08:07:11 | 192.168.212.64 | "POST /sofi/detection HTTP/1.1" 200 | request_time=0.609 upstream_response_time=0.095
                      → waiting = 0.609 - 0.095 = 0.514s

# Error log（同一秒、同一 client IP、同一请求路径）
2026/04/08 08:07:11 [error] lua tcp socket connect timed out, when connecting to 10.96.150.232:11211
                     client: 192.168.212.64, request: "POST /sofi/detection HTTP/1.1"
```

nginx ingress 的 `global_throttle` Lua 限流插件在每个请求上同步调用 memcached 来检查限流计数器。当 memcached 响应超时，nginx worker 被阻塞，等待时间直接叠加到 request_time。

**1s timeout 的来源**：ConfigMap 设了 `global-rate-limit-memcached-connect-timeout = 50ms`，但这只影响 connect 阶段。实际 waiting 精确为 1.00x 秒，说明某个 socket timeout 配置为 1000ms（大概率是 `lua-resty-memcached` 的 read timeout 默认值或 `global_throttle.lua` 中的显式设置），需查 Lua 源码确认具体是哪个参数。

## 4. 深入调查 memcached

确认根因指向 memcached 后，继续调查 memcached 本身的健康状态。

### Memcached 部署现状

| 项目 | 值 | 问题 |
|------|-----|------|
| Pod | `memcached-644b99bc-m75tm`，namespace `ingress-nginx` | **单副本** |
| 线程数 | 10 | 面对上千并发连接远远不够 |
| 镜像 | `bitnamilegacy/memcached:1.6.21-debian-11-r38` | deprecated image |
| CPU | 峰值 0.012 cores / request 1 core | 不是 CPU 瓶颈 |
| Memory | 4 MiB working set / request 1 GiB | 几乎没存东西 |
| FD | 正常 24，spike 时跳到 54 | 连接数翻倍就开始 timeout |
| Exporter | 无 | 无内部指标，完全飞盲 |

### Spike 事件

当天两次明显 spike：
1. 03:10-04:12 UTC：CPU 80x 增长，FD 24→54，持续约 60 分钟
2. 07:30 UTC 至今：CPU 40x 增长，FD 24→35

这些 spike 与 Loki 中的 memcached timeout 错误时间完美对齐。

### 核心矛盾

ConfigMap 配了 `pool_size=10000`（每个 nginx worker 维护的连接池大小），但只有 1 个 memcached pod、10 个线程来承接所有连接。当并发连接稍微上升，memcached 的 accept queue 就溢出，导致 connect timeout 和 read timeout 级联发生。

## 5. 根因链（完整）

```
Client request → nginx ingress controller (多 pod, 多 worker 进程)
  → global_throttle Lua plugin (每请求同步调 memcached)
    → memcached 10.96.150.232:11211 (单 pod, 10 threads)
      → 并发连接超过 memcached 处理能力
        → accept queue 溢出
          → connect timed out (50ms) 或 read timed out (默认 1000ms)
            → Lua plugin 阻塞 nginx worker 0.3-1.0s
              → request_time 增加，upstream_response_time 不变
                → waiting_duration = request_time - upstream_response_time 飙升
                  → Grafana panel P100 = 1.00s
```

不是 nginx proxy timeout，不是 fp，不是客户端。是全局限流插件依赖的单实例 memcached 连接饱和。

## 6. 修复建议

| 优先级 | 行动 | 预期效果 |
|--------|------|----------|
| P0 | memcached 扩展到 2+ 副本 | 消除 SPOF，分摊连接负载 |
| P0 | 增加 memcached 线程数（10 → 32+） | 提升并发连接处理能力 |
| P1 | 确认并降低 Lua read timeout（1000ms → 100-200ms） | worst-case waiting 从 1s 降到 200ms |
| P1 | 部署 memcached exporter sidecar | 获取 current_connections、listen_disabled_num 等内部指标 |
| P2 | 评估 pool_size=10000 是否合理 | 减少同时打到 memcached 的连接数 |
| P2 | 升级 memcached 镜像（deprecated bitnamilegacy → 当前版本） | 安全 + bug fix |
| P3 | 调查每分钟 :10-:13 秒窗口的周期性触发源 | 找到连接 burst 的外部触发因素 |

## 7. 调查方法论

本次调查使用三线并行排查法：

1. **Loki 原始日志分析**（access log + error log 交叉比对）确定了 memcached timeout 与慢请求的因果关系
2. **nginx 配置全量审计**（ConfigMap → nginx.conf → per-ingress annotations）排除了 proxy timeout 假设
3. **VictoriaMetrics pod 指标**排除了 upstream 服务问题，并确认了 memcached 资源状态

关键转折点：access log 中 `upstream_response_time` 正常（排除 fp），error log 中出现 `global_throttle.lua` memcached timeout（定位真因），两者的 timestamp + client IP 完美对齐（建立因果关系）。

## Appendix: 实际使用的 Loki / VictoriaMetrics 查询

所有 Loki 查询通过 `loki_fetch.py` 执行，指向 `LOKI_URL=https://loki.dv-api.com`，`LOKI_ORG_ID=prod`。

### A1. Nginx access log：定位慢请求

```logql
# 拉取 sofi → fp-8080 的全量 access log
{cluster="aws-uswest2-prod-a", namespace="ingress-nginx", container="controller"} |= "sofi" |= "fp-8080"

# 过滤 request_time > 0.5s 的慢请求（正则匹配 access log 中的 request_time 字段）
{cluster="aws-uswest2-prod-a", namespace="ingress-nginx", container="controller"} |= "sofi" |= "fp-8080" |~ " 0\\.[5-9][0-9]{2} \\[prod-fp-8080\\]"

# 过滤 request_time >= 1s
{cluster="aws-uswest2-prod-a", namespace="ingress-nginx", container="controller"} |= "sofi" |= "fp-8080" |~ " [1-9]\\.[0-9]{3} \\[prod-fp-8080\\]"

# 使用 regexp 解析后过滤（更精确）
{cluster="aws-uswest2-prod-a", namespace="ingress-nginx", container="controller", client="sofi", proxy_upstream_name="prod-fp-8080"}
  | regexp "(?P<request_time>\\d+\\.\\d+) \\[prod-fp-8080\\]"
  | request_time > 0.3

# 检查 5xx 错误
{cluster="aws-uswest2-prod-a", namespace="ingress-nginx", container="controller"} |= "sofi" |= "fp-8080" |~ "\" (502|503|504) "
```

### A2. Nginx error log：发现 memcached timeout

```logql
# 查所有 timeout 错误（stderr 流）
{cluster="aws-uswest2-prod-a", namespace="ingress-nginx", container="controller", stream="stderr"} |= "timeout"

# 缩小到 global_throttle Lua 插件的 timeout
{cluster="aws-uswest2-prod-a", namespace="ingress-nginx", container="controller", stream="stderr"} |= "global_throttle" |= "timeout"

# 进一步缩小到 sofi 相关
{cluster="aws-uswest2-prod-a", namespace="ingress-nginx", container="controller", stream="stderr"} |= "lua tcp socket" |= "sofi" |= "timed out"

# 精确定位 memcached 11211 端口的 connect timeout
{cluster="aws-uswest2-prod-a", namespace="ingress-nginx", container="controller", stream="stderr"} |= "connect timed out" |= "11211"

# sofi 的 throttle 相关错误
{cluster="aws-uswest2-prod-a", namespace="ingress-nginx", container="controller", stream="stderr"} |= "sofi" |= "throttle"
```

### A3. Nginx config reload 事件

```logql
{cluster="aws-uswest2-prod-a", namespace="ingress-nginx", container="controller"} |= "reload" |~ "success|config|backend"
```

### A4. Memcached 容器日志（均返回空，确认采集盲区）

```logql
# 以下查询全部返回 [no logs found]，说明 memcached 容器日志未被 promtail 采集
{namespace="ingress-nginx", container="memcached", cluster="aws-uswest2-prod-a"}
{namespace="ingress-nginx", pod=~"memcached.*"}
{namespace="ingress-nginx", app="memcached"}

# 用户提供的 query（待验证是否有数据）
count_over_time({cluster="aws-uswest2-prod-a", namespace="ingress-nginx", pod=~"memcached-644b99bc-m75tm", stream=~".*", container="memcached"}[1m] |~ "error")
```

### A5. Memcached timeout 频率统计

```logql
count_over_time({namespace="ingress-nginx", cluster="aws-uswest2-prod-a"} |= "tcp socket" |= "timed out" [1m])
```

### A6. VictoriaMetrics 查询：fp upstream pod 健康

```promql
# Pod restart
increase(kube_pod_container_status_restarts_total{namespace="prod", container="fp"}[5m])

# CPU 使用
rate(container_cpu_usage_seconds_total{namespace="prod", pod=~"fp-deployment.*"}[5m])

# Memory working set
container_memory_working_set_bytes{namespace="prod", pod=~"fp-deployment.*"}

# HPA replica 数
kube_horizontalpodautoscaler_status_current_replicas{horizontalpodautoscaler="fp-hpa"}
```

### A7. VictoriaMetrics 查询：memcached pod 健康

```promql
# CPU（注意：memcached 在 ingress-nginx namespace）
rate(container_cpu_usage_seconds_total{namespace="ingress-nginx", pod=~"memcached.*"}[5m])

# Memory
container_memory_working_set_bytes{namespace="ingress-nginx", pod=~"memcached.*"}

# File descriptors（连接数的代理指标，因为没有 memcached exporter）
container_file_descriptors{namespace="ingress-nginx", pod=~"memcached.*"}

# OOM events
container_oom_events_total{namespace="ingress-nginx", pod=~"memcached.*"}

# Restarts
kube_pod_container_status_restarts_total{namespace="ingress-nginx", container="memcached"}

# 线程数
container_threads{namespace="ingress-nginx", pod=~"memcached.*"}

# 注意：无 memcached_* exporter metrics（未部署 exporter）
```
