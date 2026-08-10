# DataVisor 监控导览 & Oncall 入口 Skill

## 元数据

- **类型**: Workflow / Reference
- **适用场景**: 接到 alert / 想了解 DV 监控体系 / 给新人讲监控 / 写新 alert 前看看应该挂哪个 dashboard
- **创建日期**: 2026-05-21
- **数据快照**: 来自 `contexts/survey_sessions/monitoring_overview_20260521/`

---

## When to Use

- 接到 Slack alert，不知道该看哪个 dashboard → 直接打开本 skill 的「Alert 路由」
- 新接手 DV oncall，要快速建立监控心智模型 → 读 [REPORT.md](../../contexts/survey_sessions/monitoring_overview_20260521/REPORT.md) §0–§4
- 给别人讲 DV 监控架构 → 用 REPORT §10 的 30 秒版本
- 写新 alert rule 前 → 看 [parts/05](../../contexts/survey_sessions/monitoring_overview_20260521/parts/05_vm_and_alerts.md) 现有 rule 分布避免重复 + 检查 severity / team label

## Prerequisites

- Grafana 访问：`https://grafana-mgt.dv-api.com`（SSO + VPN）
- MCP 工具：`mcp__grafana__*`, `mcp__victoriametrics__*`
- 相关 skill：[`dv_loki_fetch`](./dv_loki_fetch.md), [`sre-vm-query`](./sre-vm-query.md), [`bestpractice_traditional_sre_methodology`](./bestpractice_traditional_sre_methodology.md), [`bestpractice_sre_reliability_models`](./bestpractice_sre_reliability_models.md)

---

## 核心资产

完整文档（不要在 skill 里复制粘贴，按需打开）：

| 文件 | 内容 |
|------|------|
| [REPORT.md](../../contexts/survey_sessions/monitoring_overview_20260521/REPORT.md) | 导航 + decision tree + 30 秒版本 |
| [parts/01_sla_dashboard.md](../../contexts/survey_sessions/monitoring_overview_20260521/parts/01_sla_dashboard.md) | SLA dashboard (`p1KqfRAMk`) 全 panel 细节 |
| [parts/02_logging_dashboards.md](../../contexts/survey_sessions/monitoring_overview_20260521/parts/02_logging_dashboards.md) | Generic Logging + Nginx Debug Logs |
| [parts/03_pod_node_resources.md](../../contexts/survey_sessions/monitoring_overview_20260521/parts/03_pod_node_resources.md) | Pod Resources + Node Resource 全坑 |
| [parts/04_db_dashboards.md](../../contexts/survey_sessions/monitoring_overview_20260521/parts/04_db_dashboards.md) | Yuga + MySQL Overview |
| [parts/05_vm_and_alerts.md](../../contexts/survey_sessions/monitoring_overview_20260521/parts/05_vm_and_alerts.md) | VM + vmalert 体系 + 完整告警目录（按 9 大类） |
| [parts/06_latency_chain_and_playbook.md](../../contexts/survey_sessions/monitoring_overview_20260521/parts/06_latency_chain_and_playbook.md) | Latency 链条 + 10 个 alert 家族的详细 playbook |

---

## 标准 oncall 流程（5 步 + 决策点）

详细版在 REPORT §4，这里是 skill 形式的可执行版：

```
1. 读 alert：抓 severity / cluster / namespace / ts / client / metric+阈值
   ├─ 缺字段 → 停，问，不要 guess
   └─ 算调查窗口：ts ± 3min（rule eval 窗口大于 5min 时按 2x 放宽）

1.5 点 Slack alert message 里的 source URL → 直接进 vmui 看当前值
    如果时间窗拉到 24h 仍持续 firing → 大概率 chronic 噪音，走 Playbook K

2. 用 alertname 决定第一站 dashboard（见下方路由表）

3. 在 SLA dashboard 走「3-step 决策树」（Waiting → Upstream → Infra 顺序，不是并行看）：

   Step 3a. 看 Waiting Latency (panel 373, "Waiting Latency between Ingress and Upstream")
            └─ 这是「一眼看影响有多少」+ 是否网络问题的最便宜读数
            HIGH? → 网络 / client 侧（ELB / CDN / client timeout）
                    drill: ingress-nginx logs, client-side traces
            LOW?  → 继续 Step 3b

   Step 3b. 看 Upstream latency (panel 371, "Upstream latency graph (Feature platform)")
            HIGH? → FP / DB 慢 → 去 EP_yHg7Gk
                    drill: FP pod metrics, GC, connection pool, DB latency
            LOW?  → 继续 Step 3c

   Step 3c. Waiting 干净 + Upstream 干净 + 但 Response Percentiles 还高
            → infra 层问题（夹在 client→ingress 和 ingress→FP 之间）
            ├─ Ingress (nginx) — HFAlVh2Nz
            └─ APISIX — 0lpCu9kHk
            常见原因：最近 reload / config push、controller CPU、连接饱和

   关键：先 Waiting 是因为它最便宜，一眼就能 scope 出"影响多大 + 是不是网络"；
   Waiting 高就直接走网络分支，不用再看 Upstream。

4. 钻日志（窗口 ±3min，time-pinned link）

5. 形成单一假设 → 写到事故频道 → 用一条 query 验证 → 再操作
   K8s mutating ops 必须前缀 # INTENT:
```

---

## Alert → Playbook 路由表

| Alertname 模式 | Playbook | First dashboard |
|----------------|----------|-----------------|
| `RTIngress*` / `Apisix*` / `IngressNginx*` / `IngressSLA*` / `Aws(Alb\|ApiGateway)*P9*` | A | `p1KqfRAMk` |
| `*5xx*` / `*Non200*` / `*4..*` | B | `HFAlVh2Nz` |
| `K8sPod*Killed` / `*Restarted*` / `K8sPodUnableToStart` / `KubernetesContainerOomKiller` | C | `b_XlLjRMz` |
| `K8sNode*` / `Node*Disk*` / `Node*Memory*` | D | `sNt6IXzGk` |
| `HighCpuUsageOfContainer*` / `K8s*Cpu*` / FP CPU spike | E | `b_XlLjRMz` + `EP_yHg7Gk` |
| `Yuga*` / `yugabytedb*` | F | `1IGjQaiMk` |
| `Mysql*` / `MySQLReplication*` / `Hikari*` | G | `MQWgroiiz` |
| `K8sFP*Non200` / FP 504 | H | `HFAlVh2Nz` → `EP_yHg7Gk` |
| Ingress→upstream waiting | I | `p1KqfRAMk` panel 373 |
| 怀疑 metric 不稳 / 假报 | J | `LzldHAVnz` |
| **`FPTopicsOffsetIncreaseZero*` / `KafkaEventExporter*` / `FPRuleCountZero`**（占当前 firing 67%） | **K**（先判噪音） | vmui source URL |
| **`MirrorMakerConsumerLagDecliningTooSlow`** | **L** (MM2 replication 慢) | `-N7cUPZNk` (MirrorLag v2) |
| **`Kafka_*_consumergroup_lag_High`**（业务消费组 lag，区分 MM2 alert） | **M** (consumer group lag) | `cluster_kafkfa_exporter` (Kafka Exporter) |

每个 playbook 的 3–5 步详细操作 → [parts/06 §3](../../contexts/presentations/dv_monitoring_oncall/monitoring_overview_20260521/parts/06_latency_chain_and_playbook.md#alert--dashboard-决策树每类-alert-一条-playbook) 或 REPORT §5。

**Playbook L vs M（最容易搞混的两类 Kafka 告警）**：

| 项目 | L: MirrorMaker lag | M: Consumer group lag |
|---|---|---|
| Alertname | `MirrorMakerConsumerLagDecliningTooSlow` | `Kafka_*_consumergroup_lag_High` |
| Severity | PAGER | HIGH |
| Dashboard | `-N7cUPZNk` MirrorLag v2 | `cluster_kafkfa_exporter` Kafka Exporter |
| 关键 panel | 1 (MM2 pod up) + 2/3 (lag a→b, b→a) | panel 12 "Lag by Consumer Group" |
| Root 排查 | MM2 pod 挂了 → 重启（最常见） | producer 还在推但 consumer 跟不上 → 看下游 |
| 触发条件 | 衰减率 `(L5m - Lnow)/L5m < 0.3` AND `Lnow > 500` | 绝对值阈值（per consumer group） |

**DV-specific Kafka 拓扑提醒**：不用 MM2 默认的 `<source>.<topic>` 重命名 —— 同名 topic 在 cluster_a / cluster_b 都存在，方向通过 `source` / `target` label 区分。Lag 单位是 record 数，不是秒。

**Latency triage 的 Phase-2 dashboard**：`X2qhqpjSk` Multi-Cluster Traffic Distribution —— 接到 latency alert 后，**进 SLA dashboard 之前**先开这个看 panel 9 piechart，确认 client 当前流量打 cluster A / B / C 哪一边。注意 Loki 驱动 + 1m/5m/10m timeFrom，非实时，作 evidence 不作 root-cause。

---

## 6 大核心 Dashboard 速记

| UID | 名字 | 用途 |
|-----|------|------|
| `p1KqfRAMk` | SLA - Batch & RealTime | **第一站**：所有客户面 / latency / SLA |
| `HFAlVh2Nz` | Debug logs for Ingress-nginx | 按 client/status/latency 看 nginx access log |
| `9aBY8rWMz` | Logging (generic) | 任意 pod 日志探索 |
| `b_XlLjRMz` | Pod Resources | 单 pod CPU/mem/restart/IO |
| `sNt6IXzGk` | Node Resource | 节点级压力 |
| `1IGjQaiMk` | YugabyteDB | YCQL 延迟、tserver 过载 |
| `MQWgroiiz` | MySQL Overview | 连接 / 慢查询 / 复制延迟 |
| `EP_yHg7Gk` | Feature Platform Metrics | FP 自己的 P99 / GC / 连接池 |
| `X2qhqpjSk` | Multi-Cluster Traffic Distribution | latency triage Phase-2：client 流量打哪个物理 cluster（-a/-b/-c），piechart panel 9 |
| `-N7cUPZNk` | MirrorLag v2 | MM2 双集群同步 lag，`MirrorMakerConsumerLagDecliningTooSlow` 第一站 |
| `cluster_kafkfa_exporter` | Kafka Exporter for all | 任意 consumer group lag，`Kafka_*_consumergroup_lag_High` 第一站 |
| `LzldHAVnz` | VictoriaMetrics - vmalert | rule 自身健康（怀疑假报时） |
| `asfasqwe2r` | Alertmanager View | 现在到底多少 alert firing |

辅助 dashboard 完整列表 → REPORT §2。

---

## 高频踩坑（必读，按主题分组）

完整 20 条 → REPORT §7。最高频 5 条：

1. **OOM 看 `container_memory_working_set_bytes`，不是 RSS、不是 usage**（Pod Resources panel 14）
2. **SLA dashboard 切 `client` 后必须重新挑 `Batch_Pipeline` / `pipeline`**，否则 Batch row 假性空白
3. **`gcp-uswest1-prod-a` Loki tenant 是 `nonprod`**（名字误导）
4. **写 PromQL 永远加 cluster filter**；无 filter 的 `rate(...[1m])` 在 VM 上跑全表
5. **Node Resource `$nodeHost` 永远选具体 IP，不能 `$__all`**（否则 fleet 平均，掩盖单 node 热点）

---

## 已知数据盲点（写文档时未拿到）

- ~~Alertmanager receivers / route 表~~ → `infra` repo `core/src/monitorV3/prometheus/alertmanager/config.yml`；UI `https://k8s-us-mgt-a.dv-api.com/alertmanager/`
- vmalert `-notifier.url` → 在 vmalert helm values / ConfigMap
- ~~Recording rule 全集~~ → `core/src/monitorV3/victoriametrics/alerts/recored.yaml`（注意 typo）
- Grafana OnCall 排班 → 下次跑 `mcp__grafana__list_oncall_schedules`

## 改 / 加 alert 入口

Repo: `infra` (`~/work/work-harness/code_repos/infra`)
- VM 主 alert: `core/src/monitorV3/victoriametrics/alerts/*.yml`
- Prom 兼容备份: `core/src/monitorV3/prometheus/alerts/*.yml`（**必须同步改**）
- Recording rules: `victoriametrics/alerts/recored.yaml`
- Alertmanager 路由: `prometheus/alertmanager/config.yml`
- Sync 脚本: `core/src/monitorV3/scripts/generate_victoriametrics_alerts.py`

流程：改两份 yaml → PR + lint CI → merge → 几分钟后 vmui Alerts/Groups 看到。**新 rule 必带 `severity` + `team` label**；不要 per-client 后缀分裂 alertname，用 label。详见 REPORT §0.5。

---

## 与其他 skill 的协作

```
alert
 └─ feedback_sre_triage_workflow.md      Step 1（plan-first / ±3min / 缺字段就停）
      └─ 本 skill 的路由表 + REPORT       Step 2–4
           └─ dv_loki_fetch               批量拉日志
           └─ sre-vm-query                安全 PromQL/VM 查询
           └─ feedback_loki_metric_debug  怀疑 metric pipeline 本身
      └─ /sre-oncall-output-format        9-section 报告
      └─ /sre-oncall-compound-learning    novel 发现回写 memory
```

---

## 维护

- 数据快照日期：2026-05-21；如果 dashboard 大改 / 新增告警类 / 加新组件（Milvus、LiteLLM 已收录），重跑 6 并行 subagent 流程更新 `contexts/survey_sessions/monitoring_overview_<date>/`
- 这条 skill 是导航入口，**不要把 panel 级细节复制进来**；细节永远去 parts/
- 发现 REPORT 错了 → 直接改 REPORT.md + 在 [parts/06 §与已有 skill](../../contexts/survey_sessions/monitoring_overview_20260521/parts/06_latency_chain_and_playbook.md#与已有-skill--memory-的对接点) 留一句维护记录
