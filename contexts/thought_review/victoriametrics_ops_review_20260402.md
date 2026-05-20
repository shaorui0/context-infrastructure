# VictoriaMetrics 运维现状与优化方向

日期：2026-04-02

---

## 架构现状

### 拓扑

```
Workload Clusters (×N)          MGT Cluster (monitoring-vm ns)
──────────────────────          ──────────────────────────────
vma-victoria-metrics-agent  ──remote_write──►  vms-victoria-metrics-single-server-0
  (per cluster)                                  (Single 模式，写+存+查合一)
                                                      │
                                              ┌───────┴────────┐
                                         vmalert          alertmanager
                                              │
                                         alertlogger

MGT 自身指标采集：
  vma-victoria-metrics-agent (MGT)  ──► vms-single (self-scrape)
  vma-aws-cloud-victoria-metrics-agent + cloudwatch-exporter ──► vms-single
```

### 部署模式

- VictoriaMetrics **Single 模式**（非 Cluster），单 Pod 承担所有角色
- Workload cluster 上只部署 vmagent，无本地存储
- MGT 上 vmagent 写出到 3 个 remote_write 地址（2 个 Prometheus endpoint + 1 个 VM endpoint）

---

## 当前规模（2026-04-02 实测）

| 指标 | 数值 |
|------|------|
| Active time series | ~793,000（min 787k / max 798k） |
| Retention | 3 个月 |
| vms-single CPU limit | 15 cores |
| vms-single Memory | 120Gi (request = limit) |
| WAL maxDiskUsagePerURL | 1GB × 3 endpoints = 3GB |
| Storage 磁盘总量 | 6.2TB (NVMe) |
| Storage 已用 | 4.7TB（**76%**） |
| Storage 剩余 | 1.5TB |

**规模评估**：Single 模式上限约 500-1000 万 series，目前仅用 ~8%，短期无压力。

**磁盘风险**：已用 76%，剩余 1.5TB。按当前写入速率估算剩余时间：
```
3个月 retention × 4.7TB = ~1.57TB/月 增量（粗估）
→ 1.5TB 剩余 ≈ 不足 1 个月
```
**这是当前最高优先级风险。**

---

## 现有配置

### vms-single 关键参数

```bash
--retentionPeriod=3                    # 3 个月
--storageDataPath=/storage
--maxInsertRequestSize=1073741824       # 1GB（异常，见下）
--maxLabelsPerTimeseries=100
--vmalert.proxyURL=https://vmalert-mgt-a.dv-api.com
--search.maxQueryLen=500MB
```

### vmagent (MGT) 关键参数

```bash
--remoteWrite.maxDiskUsagePerURL=1GB
--remoteWrite.tmpDataPath=/tmpData     # 有持久化，重启不丢数据
--remoteWrite.url=...                  # 3 个 endpoint
--remoteWrite.label=kubernetes_cluster=aws-uswest2-mgt-a
```

---

## 发现的问题

### P1：无磁盘写满保护

`/storage` PVC 没有配置 `--storage.minFreeDiskSpaceBytes`。

**风险**：磁盘写满时 vms-single 直接崩溃，而非优雅停止写入。

**修复**：
```bash
--storage.minFreeDiskSpaceBytes=10GB
```

---

### P1：maxInsertRequestSize 过大（1GB）

正常合理值为 32MB。1GB 允许单个 HTTP 请求传入超大 payload，在 vmagent 批次失控或 relabel 配置出错时，可能导致 vms-single OOM。

**修复**：
```bash
--maxInsertRequestSize=32MB
```

---

### P2：WAL 缓冲时间偏短

```
1GB ÷ (约 5,000 samples/s × 20 bytes) ≈ 2.8 小时
```

MGT 集群自身的监控链路，断连容忍度应更高。

**建议**：
```bash
--remoteWrite.maxDiskUsagePerURL=5GB   # 约 14 小时缓冲
```

---

### P3：内存超配

80 万 active series 理论需要内存约：
```
793,000 × 500 bytes ≈ 400MB（工作集）
```

120Gi 是极度超配（约 300 倍）。实际峰值估计在 8-15Gi（含查询缓存、操作系统 page cache 等）。

**建议**：先通过 `container_memory_working_set_bytes` 观察实际用量 1 周后再调整，target 40-60Gi。

---

## 必须监控的指标

```promql
# 磁盘剩余（P0 告警）
vm_free_disk_space_bytes / vm_data_size_bytes < 0.2

# WAL 积压（P1 告警）
vmagent_remotewrite_pending_data_bytes > 2e9

# 写入失败（P1）
rate(vmagent_remotewrite_requests_total{status_code!~"2.."}[5m]) > 0

# Active series 暴增（P2，cardinality 爆炸前兆）
rate(vm_new_timeseries_created_total[5m]) > 1000

# 慢查询（P2）
vm_slow_queries_total
```

---

## 优化路线图

| 优先级 | 操作 | 预期效果 |
|--------|------|---------|
| **P0** | **扩容 /storage PVC 或清理旧数据** | **当前 76%，估计不足 1 个月** |
| P1 | 加 `--storage.minFreeDiskSpaceBytes=10GB` | 防磁盘满崩溃 |
| P1 | `maxInsertRequestSize` 改为 32MB | 防 OOM |
| P2 | `maxDiskUsagePerURL` 从 1GB 改到 5GB | WAL 缓冲 14h |
| P2 | 配置 active series 暴增告警 | 提前发现 cardinality 问题 |
| P3 | 观察内存真实用量后降配到 40-60Gi | 节省资源 |
| 长期 | active series 超 300 万时评估迁移至 Cluster 模式 | 水平扩展能力 |

---

## 扩容触发条件

如果出现以下任意一项，评估迁移到 Cluster 模式：

- Active series 持续 > 300 万
- vms-single CPU 持续 > 10 cores（limit 的 67%）
- 单次查询响应时间 P95 > 10s
- 工作集群数量超过 30 个且写入速率 > 500k samples/s
