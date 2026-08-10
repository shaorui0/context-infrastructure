---
metadata:
  kind: reference
  status: stable
  summary: "Card: Yugabyte metrics quick checks - VM MCP queries for node up/down, curl /metrics, and awsf node identification."
  tags: ["card", "yugabyte", "monitoring", "metrics", "debugging", "oncall", "victoriametrics", "awsf"]
  first_action: "Query VM MCP for YB node up/down status, then awsf to identify the node"
---

# Card: Yugabyte Metrics - Quick Checks

## TL;DR (Do This First)
1. **VM MCP 查询** — 确认哪些 YB 节点 up/down
2. **awsf 定位节点** — 用告警集群名找到同集群所有 EC2 实例 IP
3. **YB Master UI** — 用健康节点的 IP 访问 `:7000` 查看集群全貌
4. Curl `/metrics` 确认进程状态
5. Before touching the cluster, decide if you need to reduce blast radius (traffic/MM) (`#MANUAL`)

## Step 1: VictoriaMetrics MCP 查询 YB 节点状态

### YB Master Up/Down（Grafana 原始 query）
```promql
avg(up{kubernetes_cluster=~"$cluster",kubernetes_namespace="$dbcluster",instance=~"${node}.yb-masters.$dbcluster.svc.cluster.local:7000"})
or
avg(up{kubernetes_cluster=~"$cluster",kubernetes_namespace="$dbcluster",instance=~"$serverNodeInstance"})
```

### Triage 实用查询模板

**查指定集群所有 tserver/master 的 up 状态：**
```promql
up{kubernetes_cluster="<cluster>", kubernetes_namespace="<dbcluster>"}
```

**查所有 down 的外部 YB 节点：**
```promql
up{job=~"yugabytedb.*external", export_type=~"tserver_export|master_export"} == 0
```

**查指定 IP 的节点状态：**
```promql
up{instance=~"<ip>:.*"}
```

### 变量映射（告警 → 查询参数）

| 告警字段 | 查询变量 | 示例 |
|---------|---------|------|
| Cluster name | `$cluster` / `kubernetes_cluster` | `aws-uswest2-prod-a` |
| Namespace | `$dbcluster` / `kubernetes_namespace` | `prod-external-new-1` |
| Instance IP:port | `$serverNodeInstance` / `instance` | `172.31.35.20:9000` |

### 实际 Case 示例（2026-04-10）

告警：`[PAGER][YUGABYTE] Cluster aws-uswest2-prod-a: external tserver down — 172.31.35.20:9000`

```promql
# 查该集群所有 YB 节点状态
up{kubernetes_cluster="aws-uswest2-prod-a", kubernetes_namespace="prod-external-new-1"}

# 查具体 down 的节点
up{instance="172.31.35.20:9000"}
```

## Step 2: awsf 定位同集群所有 YB 节点

告警中的 IP 是 EC2 private IP。**关键操作：用 `awsf` 找到同集群所有 YB 实例**，不仅能确认告警节点身份，还能拿到其他健康节点的 IP 用于访问 YB UI。

```bash
# 从告警中的集群名映射到 region（参考 reference-aws-cli.md）
# aws-uswest2-* → us-west-2
awsf us-west-2 prod-a yb

# 输出示例（5 个节点）：
# aws-uswest2-prod-a-prod-yb-prod-0  i-0d76ab2c7da24bfb2  running  172.31.35.20   ← 告警节点（down）
# aws-uswest2-prod-a-prod-yb-prod-1  i-047e75d3b0a7f05ce  running  172.31.42.16   ← 健康节点
# aws-uswest2-prod-a-prod-yb-prod-2  i-0de31c9a58113a2c3  running  172.31.36.59
# aws-uswest2-prod-a-prod-yb-prod-3  i-01fbc53afe412d207  running  172.31.47.178
# aws-uswest2-prod-a-prod-yb-prod-4  i-053b27c9f7f86e4e1  running  172.31.37.59
#
# → 告警 IP 172.31.35.20 = prod-yb-prod-0
# → 可用健康节点 IP: 172.31.42.16, 172.31.36.59, 172.31.47.178, 172.31.37.59
```

### 集群 → Region → awsf 快查表

| 告警集群名 | Region | awsf 命令 |
|-----------|--------|----------|
| `aws-uswest2-prod-a` | us-west-2 | `awsf us-west-2 prod-a yb` |
| `aws-uswest2-prod-b` | us-west-2 | `awsf us-west-2 prod-b yb` |
| `aws-useast1-prod-a` | us-east-1 | `awsf us-east-1 prod-a yb` |
| `aws-useast1-prod-b` | us-east-1 | `awsf us-east-1 prod-b yb` |
| `aws-cacentral1-prod-a` | ca-central-1 | `awsf ca-central-1 prod-a yb` |

## Step 3: YB Master UI 查看集群全貌

**用健康节点的 IP 访问 YB Master UI（`:7000`）**，可以看到集群级别的状态信息：

```
http://<healthy-master-ip>:7000
```

> **要求**：需要 VPN 连接（private IP）。从 Step 2 的 awsf 输出中选一个非告警节点的 IP。

### UI 关键页面

| 页面 | URL | 查看内容 |
|------|-----|---------|
| **主页/集群概览** | `http://<ip>:7000/` | 集群健康状态、master/tserver 列表、Dead Nodes |
| **Tablet Servers** | `http://<ip>:7000/tablet-servers` | 所有 tserver 状态、tablet 分布、load 情况 |
| **Tables** | `http://<ip>:7000/tables` | 表和 tablet 状态 |
| **Utilities** | `http://<ip>:7000/utilities` | 集群配置、flags |

### 在 triage 报告中的使用

分析报告的「操作命令方案」或「Next Steps」中应包含：
1. `awsf` 命令 — 列出同集群所有 YB 节点及其 IP
2. YB UI 链接 — 用健康节点 IP 构造 `http://<ip>:7000/` 和 `http://<ip>:7000/tablet-servers`
3. 指出可以在 UI 的 Tablet Servers 页面确认 dead node 数量和 tablet under-replication 状态

### 实际 Case 示例（2026-04-10）

告警：`aws-uswest2-prod-a` tserver down `172.31.35.20:9000`

```
# Step 1: awsf 找到所有节点
awsf us-west-2 prod-a yb
# → 告警节点: prod-yb-prod-0 (172.31.35.20)
# → 健康节点: prod-yb-prod-1 (172.31.42.16)

# Step 2: 用健康节点 IP 访问 YB Master UI
# http://172.31.42.16:7000/              ← 集群概览，看 Dead Nodes
# http://172.31.42.16:7000/tablet-servers ← tserver 列表，确认哪些 down
```

## Step 4: Curl /metrics 确认进程状态

```bash
curl -m 2 http://<master-ip>:7000/metrics | head
curl -m 2 http://<tserver-ip>:9000/metrics | head
```

> **注意**：tserver 默认 scrape 端口是 9000，不是 9100。

## Common Ports (Environment-Dependent)

| Role | Port | 用途 |
|------|------|------|
| Master UI | `7000` | **集群概览 / Dead Nodes / tablet servers**（最重要的诊断入口） |
| Master RPC | `7100` | Master 内部 RPC |
| tserver UI | `9000` | tserver 状态页（scrape `/metrics` 默认也是 9000） |
| tserver RPC | `9100` | tserver 内部 RPC |
| YCQL | `9042` 或 `12000` | Cassandra-compatible interface |
| YSQL | `5433` | Postgres-compatible interface |

### Minimal Local Checks（已登录节点时）

```bash
ss -lntp | grep -i yb || true
curl -m 2 http://<tserver-ip>:9000/ | head
curl -m 2 http://<tserver-ip>:9100/metrics | head
```

## Further Reading (Deep Doc)
- Full reference: [reference-yugabyte-monitoring-commands-reference.md](../references/reference-yugabyte-monitoring-commands-reference.md)
- AWS CLI tools: [../references/reference-aws-cli.md](../references/reference-aws-cli.md)
