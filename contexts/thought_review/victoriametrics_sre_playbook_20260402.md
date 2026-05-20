# VictoriaMetrics SRE Playbook

适用：当前架构（Single 模式，~80万 active series，50 workload clusters）
日期：2026-04-02

---

## 一、关键架构决策点

### 决策 1：Single vs Cluster 模式

| | Single | Cluster |
|--|--------|---------|
| 适用规模 | < 500万 active series | > 500万 |
| 运维复杂度 | 低（1个Pod） | 高（3种组件） |
| 水平扩展 | 不能 | 能 |
| 单点风险 | 有 | 无 |
| **当前选择** | ✅ 合适（80万 series） | 超过300万时评估切换 |

**触发切换的信号**：
- active series 持续 > 300万
- CPU 持续 > 10 cores（limit 的 67%）
- 查询 P95 > 10s

---

### 决策 2：WAL 磁盘大小

WAL 保护的是：**remote 断连期间数据不丢**。

```
WAL 能撑多久 = maxDiskUsagePerURL ÷ (samples/sec × 20 bytes)

当前：1GB ÷ (5,000 × 20) ≈ 2.8 小时
建议：5GB ÷ (5,000 × 20) ≈ 14 小时
```

**原则**：WAL 至少能覆盖一次 oncall 响应周期（工作时间内发现+处理 ≈ 4-8 小时）。

---

### 决策 3：Retention 周期

当前：3 个月（`--retentionPeriod=3`，单位默认为月）

磁盘消耗公式：
```
retention(月) × 月均写入量 = 磁盘占用

当前：4.7TB / 3个月 ≈ 1.57TB/月
→ 扩容或缩短 retention 二选一
```

**调整 retention 影响**：缩短到 2 个月可释放 ~1.5TB，但失去历史对比能力。

---

### 决策 4：maxLabelsPerTimeseries

```bash
--maxLabelsPerTimeseries=100  # 当前配置
```

这是防 cardinality 爆炸的最后一道硬性防线。超出的 label 被截断并记录日志，不崩溃。

**建议降到 30-50**：正常业务 metrics 很少超过 15 个 label，100 过于宽松，无法拦截动态 label 注入。

---

## 二、部署关键配置

### vms-single 必须配置的参数

```bash
# 数据保护
--storage.minFreeDiskSpaceBytes=10GB   # 磁盘快满时停止写入，不崩溃
--retentionPeriod=3                    # 根据磁盘容量决定

# 写入限制
--maxInsertRequestSize=32MB            # 防单请求 OOM（当前 1GB 有风险）
--maxLabelsPerTimeseries=30            # 防 cardinality 爆炸

# 查询保护
--search.maxConcurrentRequests=16      # 防慢查询打挂
--search.maxQueryDuration=30s          # 超时保护
--search.maxUniqueTimeseries=500000    # 防单查询全量扫描
```

### vmagent (workload cluster) 必须配置的参数

```bash
# WAL 持久化（必须挂 PVC，否则重启丢数据）
--remoteWrite.tmpDataPath=/tmpData

# WAL 大小（按 oncall 响应时间计算）
--remoteWrite.maxDiskUsagePerURL=5GB

# 并发写入
--remoteWrite.queues=4                 # 小集群 2-4，大集群 4-8

# 内存保护
--memory.allowedPercent=60
```

### vmagent relabel（workload cluster）防 cardinality

```yaml
metric_relabel_configs:
  # 删除已知高基数 label
  - action: labeldrop
    regex: "pod_template_hash|request_id|trace_id|session_id|uuid|le"

  # 截断过长的 label value（动态 label 通常很长）
  - source_labels: [pod]
    regex: ".{64,}"
    target_label: pod
    replacement: "__dynamic__"
```

---

## 三、监控指标 & 告警

### 告警分级

| 级别 | 条件 | 含义 |
|------|------|------|
| P0 | 磁盘剩余 < 10% | 不到 2 周写满，数据即将丢失 |
| P0 | vms-single pod 不在 Running | 监控全断 |
| P1 | 磁盘剩余 < 20% | 需要扩容或调整 retention |
| P1 | write 失败率持续 5min | 数据正在丢失 |
| P1 | WAL 积压 > 5GB | remote 写入堵塞 |
| P2 | active series 1h 内涨 50% | cardinality 爆炸前兆 |
| P2 | 慢查询 > 10/min | 查询压力过大 |

### PromQL 告警规则

```yaml
groups:
  - name: victoriametrics.critical
    rules:
      - alert: VMDiskCritical
        expr: vm_free_disk_space_bytes / vm_data_size_bytes < 0.1
        for: 5m
        labels:
          severity: P0

      - alert: VMDiskWarning
        expr: vm_free_disk_space_bytes / vm_data_size_bytes < 0.2
        for: 15m
        labels:
          severity: P1

      - alert: VMWriteFailure
        expr: rate(vmagent_remotewrite_requests_total{status_code!~"2.."}[5m]) > 0
        for: 5m
        labels:
          severity: P1

      - alert: VMWALBackpressure
        expr: vmagent_remotewrite_pending_data_bytes > 5e9
        for: 10m
        labels:
          severity: P1

      - alert: VMCardinalitySpike
        expr: rate(vm_new_timeseries_created_total[5m]) > 1000
        for: 5m
        labels:
          severity: P2
```

### 日常巡检 PromQL

```promql
# 当前规模
vm_number_of_active_timeseries
rate(vm_rows_added_to_storage_total[5m])

# 磁盘健康
vm_free_disk_space_bytes
vm_data_size_bytes

# 写入链路健康
vmagent_remotewrite_pending_data_bytes
rate(vmagent_remotewrite_requests_total[5m])

# 查询健康
vm_slow_queries_total
vm_concurrent_queries
```

---

## 四、如何防止「把系统打坏」

### 风险 1：Cardinality 爆炸（最常见）

**触发**：新服务上线带动态 label（pod name、request id 等）

**防线**（按顺序）：
1. vmagent relabel 在采集时删掉动态 label
2. `--maxLabelsPerTimeseries=30` 硬截断
3. `vm_new_timeseries_created_total` 告警提前发现
4. 发现后用 API 定位元凶：
   ```bash
   curl 'http://vms-single:8428/api/v1/status/tsdb?topN=20'
   ```

---

### 风险 2：磁盘写满

**当前状态**：76%，剩余 ~1.5TB，约 1 个月内触发

**防线**：
1. `--storage.minFreeDiskSpaceBytes=10GB`（停写不崩溃）
2. P0 告警在 10% 时触发
3. 扩容前临时手段：缩短 retention
   ```bash
   # 改为 2 个月，立即释放约 1.5TB
   --retentionPeriod=2
   ```

---

### 风险 3：慢查询打挂 vms-single

**触发**：Grafana 大盘 refresh 跑全量时间范围查询

**防线**：
1. `--search.maxConcurrentRequests=16`
2. `--search.maxQueryDuration=30s`
3. `--search.maxUniqueTimeseries=500000`
4. Grafana 侧：默认时间范围不超过 6h，避免 `rate()[30d]` 类查询

---

### 风险 4：vmagent 重启丢数据

**触发**：pod 重启但没有挂 WAL PVC，或磁盘被清理

**防线**：
1. `--remoteWrite.tmpDataPath` 必须挂 PVC（不能用 emptyDir）
2. `maxDiskUsagePerURL` 设置合理上限
3. 重启前检查 `vmagent_remotewrite_pending_data_bytes` 是否为 0

---

## 五、紧急操作手册

### 磁盘快满时

```bash
# 1. 确认当前用量
kubectl -n monitoring-vm exec vms-victoria-metrics-single-server-0 -- df -h /storage

# 2. 临时缩短 retention（立即生效，旧数据被清理）
# 修改 --retentionPeriod=2 并重启 pod

# 3. 扩容 PVC（需要 StorageClass 支持在线扩容）
kubectl -n monitoring-vm patch pvc <pvc-name> -p '{"spec":{"resources":{"requests":{"storage":"10Ti"}}}}'
```

### 写入链路断了

```bash
# 1. 检查 vmagent 状态
kubectl -n monitoring-vm get pod -l app=vmagent

# 2. 查看 WAL 积压
# Grafana: vmagent_remotewrite_pending_data_bytes

# 3. 检查 vms-single 是否在接收写入
kubectl -n monitoring-vm logs vms-victoria-metrics-single-server-0 --tail=50

# 4. 查看 vms-single 是否拒绝请求（429）
rate(vm_http_requests_total{path=~".*/insert.*", code="429"}[5m])
```

### Cardinality 爆炸时

```bash
# 1. 找出元凶
curl 'http://vms-single:8428/api/v1/status/tsdb?topN=20' | jq .

# 2. 找出是哪个 job 在写入
sum by (job) (rate(vmagent_rows_inserted_total[5m]))

# 3. 在 vmagent 的 metric_relabel_configs 里 drop 掉问题 label
# 修改 ConfigMap 并 rollout restart vmagent
```
