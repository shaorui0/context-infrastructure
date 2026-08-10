# Pod & Node Resources

DataVisor 在 Grafana `kubernetes` folder 下的两块 K8s 资源仪表盘，是 oncall 看「单 pod 健康」和「节点级压力」的主入口。Pod Resources 给「这个 pod 怎么了」的答案，Node Resource 给「这台机器有没有被打爆」的答案。

- Pod Resources：UID `b_XlLjRMz` · <https://grafana-mgt.dv-api.com/d/b_XlLjRMz/pod-resources>（13 panel, 最新更新 2026-04-02）
- Node Resource：UID `sNt6IXzGk` · <https://grafana-mgt.dv-api.com/d/sNt6IXzGk/node-resource>（49 panel, 最新更新 2025-06-09）

两块都是 cadvisor / kube-state-metrics / node-exporter 三件套的数据，PromDs 都是变量，可以在 nonprod / prod 之间切。

---

## Pod Resources（b_XlLjRMz）—— 变量、关键 panel、查询

### 变量

| 变量 | 类型 | 作用 |
|---|---|---|
| `PromDs` | datasource | 选 Prometheus / VictoriaMetrics 源（nonprod vs prod） |
| `cluster` | query | `kubernetes_cluster` 标签值，例如 `dv-prod-…` |
| `namespace` | query | 命名空间，承载 cluster 选择 |
| `pod` | query | 单个 pod 名 |
| `containers` | query | 同一 pod 内的容器名（适配 multi-container pod） |

注意：dashboard 同时兼容老的 cadvisor 标签（`pod_name` / `container_name`）和新的 (`pod` / `container`)，几乎每个 query 都是 `A or B` 的 union。

### 关键 panel 与查询

13 个 panel，按用途排：

**1. Pod Up Time（stat, id 11）** —— pod 起活时长。

**2. Host Node（stat, id 13）** —— 显示 pod 落在哪台 node 上，用的是从 `container_cpu_usage_seconds_total{...}` 里提取的 instance/node label：
```
container_cpu_usage_seconds_total{kubernetes_cluster=~"$cluster",namespace=~"$namespace",pod=~"$pod"}
```
这是从 pod 跳到 Node Resource 的核心入口。

**3. Memory usage（timeseries, id 1）** —— 三条线：RSS / request / limit
```
# RSS (实际使用)
container_memory_rss{kubernetes_cluster="$cluster", namespace="$namespace", pod="$pod", container!="", container!="POD", container=~"$containers"}
  or container_memory_rss{...pod_name="$pod", container_name!="POD", container_name=~"$containers"}

# Request / Limit
kube_pod_container_resource_requests{...resource="memory", unit="byte"}
kube_pod_container_resource_limits{...resource="memory", unit="byte"}
```

**4. CPU Usage（timeseries, id 2）** —— rate(usage) vs request vs limit
```
sum(rate(container_cpu_usage_seconds_total{...pod=~"$pod", container!="POD", container=~"$containers"}[2m])) by (pod)
  or sum(rate(container_cpu_usage_seconds_total{...pod_name=~"$pod", container_name!="POD", container_name=~"$containers"}[2m])) by (pod_name)

kube_pod_container_resource_requests{...resource="cpu", unit="core"}
kube_pod_container_resource_limits{...resource="cpu", unit="core"}
```

**5. Memory Advance View（OOM Indicator, Memory Tuning）（timeseries, id 14）** —— OOM 调参的主图，5 条线：request / limit / RSS / working_set / usage_bytes
```
container_memory_working_set_bytes{...}   # ← OOMKiller 判定依据
container_memory_usage_bytes{...}         # cgroup memory.usage_in_bytes
container_memory_rss{...}
kube_pod_container_resource_requests{...resource="memory"}
kube_pod_container_resource_limits{...resource="memory"}
```
**OOMKill 看 working_set 贴近 limit 的程度**，不是看 RSS 也不是 usage。

**6. CPU Throttling（timeseries, id 15）** —— throttle 占比
```
sum(increase(container_cpu_cfs_throttled_periods_total{container=~"$containers",namespace="$namespace",kubernetes_cluster="$cluster", pod="$pod"}[10m])) by (kubernetes_cluster, container, pod, namespace)
/
sum(increase(container_cpu_cfs_periods_total{container=~"$containers",namespace="$namespace",kubernetes_cluster="$cluster"}[10m])) by (kubernetes_cluster, container, pod, namespace)
```
分子分母都是 10m 窗口的 increase。值 >0.25 一般就是「明显被限流」。

**7. Traffic transmit / receive（timeseries, id 3 / 4）**
```
irate(container_network_transmit_bytes_total{...pod="$pod"}[3m])
  or irate(container_network_transmit_bytes_total{...pod_name="$pod"}[3m])
irate(container_network_receive_bytes_total{...}[3m]) or ...
```

**8. Containers' statuses（timeseries, id 5）** —— 4 个 series 叠在一起：
```
kube_pod_container_status_ready{...container=~"$containers"}
kube_pod_container_status_running{...}
kube_pod_container_status_waiting{...}    # ← CrashLoopBackOff 时这个 = 1
kube_pod_container_status_terminated{...}
```

**9. Containers' restarts total（stat, id 6）** —— 累计重启次数（聚合）
```
sum(kube_pod_container_status_restarts_total{namespace="$namespace", container=~"$containers", pod="$pod"})
```

**10. Containers' restarts（timeseries, id 7）** —— 按 container 拆开看重启时间线
```
kube_pod_container_status_restarts_total{kubernetes_cluster="$cluster", namespace="$namespace", container=~"$containers", pod="$pod"}
```

**11. Read IOPS / Write IOPS（timeseries, id 8 / 9）**
```
sum by (device, pod, container) (
  rate(container_fs_reads_total{...pod=~"$pod", container!="POD"}[5m])
  or label_replace(label_replace(rate(container_fs_reads_total{...pod_name=~"$pod", container_name!="POD"}[5m]),
                                 "pod", "$1", "pod_name", "(.*)"),
                   "container", "$1", "container_name", "(.*)")
)
```
注意：Write IOPS 的 `by (devie, pod, container)` 是 dashboard 里的 typo（应该是 `device`），label 名不存在会导致每条 series 单独显示——不影响判断，但聚合不会发生。

### 没有的东西

这个 dashboard **不直接显示 OOMKill 计数和 fd 数量**：
- OOMKill 需要从 alertmanager / kube_pod_container_status_last_terminated_reason{reason="OOMKilled"} 或 events 看。Pod Resources 上看的是「working_set 触顶 + restart 计数 +1」的间接证据。
- File descriptor 在 Pod 维度没板子；只有 Node Resource 有 `process_open_fds` / `node_filefd_allocated`。

---

## Node Resource（sNt6IXzGk）—— 变量、关键 panel、查询

### 变量

| 变量 | 作用 |
|---|---|
| `PromDs` | 同上 |
| `cluster` | `kubernetes_cluster` |
| `job` | node-exporter 的 prometheus job 名，instance selector 用 |
| `node` | node 名（kube_node_* 系列用），形如 `ip-10-x-x-x.ec2.internal` |
| `nodeHost` | node 的 IP，配合 `port` 拼成 `instance="$nodeHost:$port"`（node-exporter selector） |
| `port` | node-exporter 端口（典型 9100） |

**关键差异**：
- `kube_*` 指标（kube-state-metrics）用 `node=~"$node"` 过滤
- `node_*` 指标（node-exporter）用 `instance=~"$nodeHost:$port"` 过滤
- 跨源拼接的 panel（Node CPU/Memory Allocation）用 `instance=~"$node|$nodeHost.*"` 同时兼容两种 label。这是经常踩坑的根源（见最后一节）。

### 关键 panel（49 个，挑 oncall 最常看的）

**Server Stats 行（gauge）**：
- `CPU Busy`（101）：`(总核数 - idle核数) / 总核数 * 100`
- `RAM Used`（102）：两条 query，一条用 `MemTotal-MemFree`，一条用 `100 - MemAvailable/MemTotal`
- `Sys Load (5m/15m avg)`（105/106）：`avg(node_load5) / cpu_count * 100`

**Server Info 行**：CPU Cores / RAM Total / Uptime / Sys Load 1m 等单值。

**Node Stats 行（kube-state-metrics 视角）** —— 这一行是**容量规划/调度压力**的关键：
- `Node CPU Allocation`（301）：
  ```
  (sum(rate(container_cpu_usage_seconds_total{instance=~'$node|$nodeHost.*', id='/'}[2m])) / sum(kube_node_status_allocatable_cpu_cores{node=~'$node'})) * 100
  ```
- `Node Memory Allocation`（302）：实际占用 / allocatable
- `Node Pods Allocation`（303）：`kubelet_running_pod_count / kube_node_status_allocatable_pods`
- `Node "$node" CPU/Memory Requested`（304/305）：所有 pod 的 request 总和 / allocatable，**反映调度压力，不是真实负载**。Requested 高 + Usage 低 = 资源被抢占但没用上。

**Node Info 行**：Capacity / Allocatable / Requested / 实际 Usage 四条线叠在一起的 CPU、Memory、Pods 三张图。最容易看清「这台 node 有没有空间再接新 pod」。

**Basic CPU / Memory Graph 行**：CPU 按 mode（system/user/iowait/irq/idle）拆，Memory Basic 给 Total / Used / Buffers+Cached / Free / Swap。

**CPU / Memory / Net / Disk 行**（深度细节）：
- `CPU`（3）：9 条线，全 mode（system/user/nice/idle/iowait/irq/softirq/steal/guest）
- `Memory Stack`（24）：9 条线的 stacked memory breakdown
- `Network Traffic`（84）：bits/s
- `Disk Space Used`（156）、`Disk IOps`（229）、`I/O Usage Read/Write`（42）、`I/O Usage Times`（127）

**System Misc 行**：
- `File Descriptors`：`process_max_fds` vs `process_open_fds`（这是 node-exporter 进程自己的 fd，不是全机）
- `Processes State`：blocked / running
- `Context Switches / Interrupts`、`System Load`、`Entropy`

**Network 部分**：sockstat TCP/UDP、netstat TCP retrans / listen drops、NF conntrack（`node_nf_conntrack_entries` vs `_limit`，conntrack 满了是常见疑难杂症）。

**File system 部分**：`Filesystem space available`、`File Nodes Free`（inode）、`File Descriptor`（机器级 `node_filefd_allocated` vs `_maximum`，**这才是 OS 级 fd 用量**）。

---

## 典型场景 playbook

### 场景 1：Pod CrashLoopBackOff / 重启飙升

1. 进 **Pod Resources**，定位 `cluster` / `namespace` / `pod` / `containers`。
2. 看 **Containers' restarts total** 和 **Containers' restarts**（panel 6/7）：哪个 container 在重启？多频繁？
3. 看 **Containers' statuses**（panel 5）：`waiting=1` 持续高 → CrashLoopBackOff；`terminated` 偶发尖峰 → 正常退出/被 evict。
4. 时间对齐 **Memory Advance View**（panel 14）：重启前 working_set 是否撞 limit？撞了就是 OOM。
5. 再看 **CPU Throttling**（panel 15）：throttle >50% 长期持续，可能是 liveness probe 超时被 kill。
6. 如果上述都正常 → 去 Loki / pod logs 看 application 错误（不在本 dashboard 内）。

### 场景 2：服务高 CPU（clickhouse / fp 之类）

1. **Pod Resources → CPU Usage**：usage 是否贴近 limit？
2. **CPU Throttling** panel：throttle 比例。
   - usage < limit 但 throttle 高 → CFS quota 配错（period vs quota 不匹配），或多核没分均匀
   - usage ≈ limit 且 throttle 高 → 真的需要提 limit
3. 跳到 **Node Resource**（用 panel 13 "Host Node" 拿到 nodeHost IP）：
   - **Node CPU Allocation** / **CPU Basic** 看节点整体压力
   - 如果 node 也满 → 「noisy neighbor」或 node 整体调度过密
4. 如果是 service 级（多 pod），用 service-level dashboard 看 P99 latency 配合判断。

### 场景 3：OOMKill 调查

1. **Pod Resources → Memory Advance View**（panel 14）是核心图：
   - **看 `working_set_bytes` 是不是贴 limit**，不要看 RSS
   - working_set 包含 active anonymous + active file cache，是 cgroup OOM killer 的实际判定指标
   - usage_bytes 通常 > working_set（包含 inactive cache），但 OOM 不看它
2. **Containers' restarts**（panel 7）：是否在 working_set 触顶后 +1？
3. 看 request 和 limit 的差距：
   - request == limit（Guaranteed QoS）：被 kill 是自己用超了
   - request < limit（Burstable）：可能被 node 压力驱赶（看 Node Resource）
4. **Node Resource → RAM Used / Memory Stack**：node 整体内存是否也压顶？是的话可能不是 pod 自己超 limit，是 node level eviction。
5. 直接确认 OOMKilled 原因（dashboard 外）：
   ```promql
   kube_pod_container_status_last_terminated_reason{reason="OOMKilled", namespace="...", pod="..."}
   ```

### 场景 4：Noisy neighbor / 节点压力

1. 已知 host node（Pod Resources panel 13 给的 instance）。
2. **Node Resource** 切到该 node：
   - **CPU Busy** + **Node CPU Allocation**：整体使用率
   - **Memory Stack** + **RAM Used**：内存饱和度
   - **CPU Basic** 按 mode 看：iowait 高 → 磁盘瓶颈；steal 高 → 虚拟化层抢 CPU；softirq 高 → 网络/中断风暴
   - **Disk IOps** / **I/O Usage Times**：磁盘 I/O 瓶颈
   - **NF Contrack**：conntrack 表满会导致连接随机丢
3. 想知道是谁在抢资源？本 dashboard 没有 per-pod 拆分。需要去 cadvisor 维度：
   ```promql
   topk(10, sum by (pod, namespace)(rate(container_cpu_usage_seconds_total{instance="<nodeHost>:<port>"}[5m])))
   topk(10, sum by (pod, namespace)(container_memory_working_set_bytes{instance="<nodeHost>:<port>"}))
   ```

---

## Pod → Node drill 顺序

标准的「从 pod 告警出发」路径：

```
1. Alert: pod X 内存使用 >90%
        ↓
2. Pod Resources (b_XlLjRMz)
   选 cluster / namespace / pod / containers
        ↓
3. 看 Memory Advance View
   - working_set 贴 limit? → OOM 路径（场景 3）
   - usage < limit 但仍然告警? → 告警阈值用错指标
        ↓
4. 看 panel 13 "Host Node" 拿到落在哪个 node (instance = nodeIP:port)
        ↓
5. Node Resource (sNt6IXzGk)
   把 nodeHost 设为该 IP, port 设 9100 (典型), 选对应 cluster
        ↓
6. 判断 node-level 是否同时有压力:
   - RAM Used > 85% → 是节点级压力，可能需要 cordon + drain
   - CPU Busy < 60% 且只有该 pod 单点高 → 应用问题，看代码 / 重启 / 增 limit
        ↓
7. 如果是节点级 → 找 noisy neighbor (上面 topk 查询)
   如果是 pod 自身 → 调 limit / 看代码 / 看 GC
```

反向 drill（先发现 node 异常 → 找罪魁 pod）：Node Resource 不直接给 per-pod breakdown，必须手写 topk PromQL，或者去 cluster-level dashboard。

---

## 坑：container 过滤、`$__all`、nodeHost 选择

### 坑 1：multi-container pod 的 container 过滤

每个 query 都带 `container!="", container!="POD", container=~"$containers"`：
- `container=""` 是 pod-level 聚合 series（cadvisor 给的整 pod 累加），不过滤掉会重复计数。
- `container="POD"` 是 pause 容器，不过滤掉会污染 CPU/内存数据。
- `$containers` 默认 `.*` 选全部，**但如果 pod 有 sidecar（如 envoy / istio-proxy / log-shipper）会把它们一起画进图里**，业务容器的曲线被压扁不显眼。
  - 排查业务问题时手动把 `$containers` 收窄到主容器名（如 `clickhouse`、`fp`）。

### 坑 2：变量选 `$__all` 的影响

- `$pod` 选 All：所有 pod 的 series 全画，timeseries 会爆，stat 类（restarts total）变成跨 pod 求和，没有诊断价值。**几乎永远不要 All。**
- `$containers` 选 All：上面坑 1 的放大版，叠加 sidecar 噪音。
- `$cluster` / `$namespace` 选 All：跨 cluster 跨 ns 拉数据，PromDs 压力大、图无意义。
- Node Resource 的 `$nodeHost` 选 All：会把整个集群所有 node 的指标平均/求和，**RAM Used / CPU Busy 这种 gauge 会显示成 fleet 均值，掩盖单 node 热点**。Oncall 时永远选具体 node。

### 坑 3：nodeHost 用 IP，不是 node name

- `$node` = K8s node name（`ip-10-1-2-3.ec2.internal` 或 GKE 风格）
- `$nodeHost` = IP（`10.1.2.3`），配合 `$port`（9100）拼 `instance="10.1.2.3:9100"`
- 两个变量**不会自动联动**。从 Pod Resources panel 13 拿到的 host node 是带 IP 的（cadvisor 的 instance label），跳到 Node Resource 时要：
  1. `$node` 选对应的 node name
  2. `$nodeHost` 单独再选一次对应 IP
- 一些拼接 panel（`Node CPU Allocation` 等）用 `instance=~"$node|$nodeHost.*"` 做兼容，**两边都不选会出空图，且不会报错**。
- 不同集群上 node-exporter 端口可能不是 9100（比如 daemonset 改过）：选 port 前先在 explore 里 `node_load1{...}` 看下实际 instance 长啥样。

### 坑 4：老/新 cadvisor label 共存

Pod Resources 几乎每个 cadvisor 查询都是 `metric{pod="$pod", container=~...} or metric{pod_name="$pod", container_name=~...}`。
- 老集群 cadvisor 用 `pod_name` / `container_name`，新版本用 `pod` / `container`。
- 这个 `or` 在大多数情况下 OK，但如果只有一边匹配上，**legend 会有两套 series 命名风格，画图时颜色/排序看着混乱**。debug 时不要被这个误导以为是数据双倍。

### 坑 5：Read/Write IOPS 的 `devie` typo

panel 9 Write IOPS 的 `by (devie, pod, container)` 是拼错的 label（应该是 `device`），结果是不按 device 聚合，每个 series 单独显示。**不影响判断有无 IO，影响聚合数值**。看 device 维度去 Node Resource 的 `Disk IOps`（node-exporter）更准。

### 坑 6：CPU Throttling 分母没带 pod

panel 15 的分母 `container_cpu_cfs_periods_total{container=~"$containers",namespace=...}` 漏了 `pod="$pod"`。同一 namespace + 同名 container 的其他 pod 会进分母，**throttle 比例被稀释偏小**。如果你看到 throttle 很低但应用确实卡 CPU，手动加 `pod="$pod"` 重算。

---

## 一句话总结

- Pod 告警先开 **Pod Resources**（b_XlLjRMz），13 个 panel 覆盖 mem/cpu/throttle/restart/network/io，**OOM 看 working_set 不是 RSS**。
- Pod 看不出问题就跳 **Node Resource**（sNt6IXzGk）确认是不是节点级压力，**nodeHost 必须手动选具体 IP，不能 All**。
- 两个 dashboard 都不给 per-pod-on-node 的 ranking，需要 topk PromQL 自己跑。
- container 过滤记得排除 `""` 和 `"POD"`，multi-container pod 看主容器要把 `$containers` 收窄。
