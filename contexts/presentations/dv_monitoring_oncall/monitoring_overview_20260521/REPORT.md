# DataVisor 监控体系总览 (2026-05-21)

> 给新 oncall / 想接手监控的人看的入口文档。覆盖：监控栈架构、6 大核心 dashboard、latency 链条诊断、alert→dashboard playbook、典型坑、知识盲点。
>
> 详细到 panel/查询级别的内容拆分在 [parts/](./parts/) 下，本文是导航与决策骨架。

---

## 0. 接到第一次 page 之前

**Grafana**：`https://grafana-mgt.dv-api.com` — SSO 登录（用工作邮箱）。如果在外网，需要 VPN。手机能用但 dashboard 比较挤，建议笔电。

**vmui**（备用查询）：`https://vm-mgt-a.dv-api.com/vmui/`

**Loki 日志**：通过 Grafana 数据源 `Loki` (uid `mwGzR0VDz`) 访问，或用 [`dv_loki_fetch`](../../../rules/skills/dv_loki_fetch.md) CLI。

**Severity → 响应 SLA**（DV 内部约定，确认见 parts/05）：

| Severity | 响应时间 | 路由 |
|----------|----------|------|
| `CRITICAL` | 立刻 | 仅 1 条 (`LokiPanics`) |
| `PAGER` | **5 分钟** | PagerDuty / oncall page |
| `HIGH` | 30 分钟 | Slack 高优 channel |
| `MEDIUM` / `WARNING` | 工作时间内 | Slack 普通 channel |
| 无 severity（91 条 rule） | 默认 route，常被吃掉 — **看到这类 alert 优先怀疑配置缺失** |

**Ack / silence**：DV 没启用 Grafana managed alerting，告警走独立 alertmanager。
- **Alertmanager UI**: `https://k8s-us-mgt-a.dv-api.com/alertmanager/` —— 看 active alert / silence / inhibit
- **配置文件**（route / receiver / Slack channel 映射）：`infra` repo 的 `core/src/monitorV3/prometheus/alertmanager/config.yml`
- **实操**：Slack alert thread 里 react / bot ack；要 silence 进 alertmanager UI

**升级**：alert label 里的 `team` 决定 channel 归属（`fp` / `infra` / `decision`）。**升级路径：在 alert thread 里 @ 对应 team oncall**。

**Cluster 命名速查**（不完全列表，详见 parts/02 Loki tenant 表）：
- `aws-<region>-prod-*`、`aws-<region>-pci-*`、`aws-<region>-mgt-*`、`aws-<region>-sandbox-*` → Loki tenant = `prod`
- `aws-<region>-dev-*`、`aws-<region>-preprod-*`、**`gcp-uswest1-prod-a`**（注意：名字带 prod 但 tenant 是 nonprod）→ Loki tenant = `nonprod`

---

## 0.5 如何改 / 加 alert（source of truth）

**Repo**: `infra` ←→ 本地 `/Users/rshao/work/work-harness/code_repos/infra`

**目录布局**：

```
core/src/monitorV3/
├── victoriametrics/alerts/        ← 主 alert rule（vmalert 实际跑这套）
│   ├── system.rules.yml           ← 通用 system 告警
│   ├── feature_platform_alert_rules.yml
│   ├── k8s_system_alert_rules.yml
│   ├── rt_sla.rules.yml
│   ├── ...（33 个 yaml 文件，按主题分；完整清单见 parts/05）
│   └── recored.yaml               ← Recording rule（注意拼写就是 recored，typo 保留）
├── prometheus/
│   ├── alerts/                    ← Prom 兼容备份，改 alert 必须同步改这一份
│   │   └── system.rules.yml       ← 与 VM 那份对应
│   ├── alertmanager/config.yml    ← Receiver / route / Slack channel 映射
│   ├── alert_generator.py         ← 业务方 alert 自动生成（self_add_rules.yml）
│   └── ...
└── scripts/
    ├── generate_victoriametrics_alerts.py  ← VM 侧 sync 入口
    └── generate_prometheus_alerts.sh       ← Prom 侧 sync 入口
```

**改 alert 流程**：
1. 同步改两个目录的对应 yaml（VM 是主，Prometheus 是兼容备份）
2. PR + lint CI → merge 到 main
3. CI 自动 sync 到线上 vmalert，几分钟内 [vmui Alerts/Groups](https://vm-mgt-a.dv-api.com/vmui/#/groups) 能看到新 rule
4. 验证 alert 已加载：vmui Alerts tab 搜 alertname；如果改阈值，等 eval 窗口跑完一轮看 state

**坑**：
- 加新 rule **必须**带 `severity` 和 `team` label（当前 91 条没 severity、79 条没 team，会落到 default channel 被吃掉）
- per-client 不要 `_Affirm` / `_Nasa` 这种 alertname 后缀分裂；用 `client` label + 一条模板 rule
- `recored.yaml` 已收录 `record:loki_*` / `record:feature_platform_*` / `record:kubernetes_monitoring_*` 等全部 recording rule；改 SLA dashboard 的 panel 192 / 130 时配合改这里
- Recording rule 里 `record:loki_kubernetes_monitoring_request_1m_*` 那段的 client 过滤是 long regex 黑名单（剔除 `dashboard|cluster|metrics|...`），加新内部"伪 client"时记得加进去

---

## 1. 监控栈架构（一句话版）

```
各 k8s 集群的 exporters / vmagent
        │ remote_write
        ▼
VictoriaMetrics (vm-mgt-a.dv-api.com)  ← 主 metrics 后端（另有 Deepflow-Prometheus 数据源，指标命名不同）
    │  ├─ Grafana datasources: PromDs (UID CA5qZASHz 是主)
    │  ├─ vmui (https://vm-mgt-a.dv-api.com/vmui/)  ← Grafana 缺面板时的 escape hatch
    │  └─ vmalert: 540 条 alerting rule 跑这里  ← 告警全部走 vmalert，Grafana managed alerting 没启用
    ▼
告警出口：vmalert → 独立 alertmanager (k8s ConfigMap, MCP 看不到) → Slack
```

日志另起一套：**Loki** (`Loki` uid=`mwGzR0VDz`)，多租户 (`auth_enabled=true`)，
tenant=`prod` 或 `nonprod`（**`gcp-uswest1-prod-a` 是 nonprod，最大的命名陷阱**）。

---

## 2. 六大核心 Dashboard 速查表

| # | Dashboard | UID | 何时打开（一句话） | 详细 |
|---|-----------|-----|--------------------|------|
| 1 | **SLA - Batch & RealTime** | `p1KqfRAMk` | **任何客户面 / latency / SLA 类问题，永远第一站**。被 page 时优先用 cluster-bound 变体（`Zv5gfxmDz` useast1-prod-a / `LrvYqTiDz` useast1-prod-b / `4igjS1Rvk` uswest2-preprod 等，少选一个变量）—— 这些 UID 来自命名推断，第一次使用先 `mcp__grafana__search_dashboards` 验证 | [01](parts/01_sla_dashboard.md) |
| 2 | Logging (generic) | `9aBY8rWMz` | 任意 pod 日志探索 | [02](parts/02_logging_dashboards.md) |
|   | Debug logs for Ingress-nginx | `HFAlVh2Nz` | 按 client / status / latency 维度看 nginx access log | [02](parts/02_logging_dashboards.md) |
| 3 | Pod Resources | `b_XlLjRMz` | 单个 pod 的 CPU/内存/restart/IO | [03](parts/03_pod_node_resources.md) |
|   | Node Resource | `sNt6IXzGk` | 节点级压力、noisy neighbor | [03](parts/03_pod_node_resources.md) |
| 4 | YugabyteDB | `1IGjQaiMk` | YCQL 延迟、tserver 过载 | [04](parts/04_db_dashboards.md) |
|   | MySQL Overview | `MQWgroiiz` | MySQL 连接、慢查询、复制延迟 | [04](parts/04_db_dashboards.md) |
| 5 | vmui + alert 体系 | – | vmalert rule、cardinality、慢查询 | [05](parts/05_vm_and_alerts.md) |
| 6 | Latency 链路 & playbook（本文核心） | – | 知道某段慢之后，下一步去哪 | [06](parts/06_latency_chain_and_playbook.md) |
| 7 | Multi-Cluster Traffic Distribution | `X2qhqpjSk` | latency triage 的 Phase-2：判断 client 当前打哪个物理 cluster（-a / -b / -c）。Loki 驱动，1m/5m/10m timeFrom，非实时 | [07](parts/07_multi_cluster_traffic.md) |
| 8 | MirrorLag v2 | `-N7cUPZNk` | 双集群 Kafka MirrorMaker2 同步 lag。alert `MirrorMakerConsumerLagDecliningTooSlow` 第一站 | [08](parts/08_kafka_mirrorlag.md) |
| 9 | Kafka Exporter for all | `cluster_kafkfa_exporter` | 业务消费组 lag。alert `Kafka_*_consumergroup_lag_High` 第一站 | [09](parts/09_kafka_exporter.md) |

**值得知道的辅助 dashboard**（按价值排）：
- `Alertmanager View` (`asfasqwe2r`) — 现在到底有多少 alert firing
- `VictoriaMetrics - vmalert` (`LzldHAVnz`) — rule 自身健康，怀疑是误报时第一站
- `Feature Platform Metrics` (`EP_yHg7Gk`) — FP work 段的细节（fp 自己的 P99/GC/连接池）
- `Feature Platform GC Enhanced` (`fp-gc-enhanced-v2`) — FP 长尾 latency 不跟 QPS 相关时
- `NGINX Ingress controller` (`nginx`) — controller 自身（CPU、连接、reload）
- `Pod Resources Overview` (`fZQLJjlVz`) + 区域变体 — fleet 视图
- `ClickHouse Performance Monitor` (`TFajSstMk2`)
- HPA / Kafka exporter / Mixin Node-Pods 见 [parts/06 §其他 dashboard](parts/06_latency_chain_and_playbook.md)

---

## 3. Latency 链条（核心心智模型）

完整 RT 请求路径：

```
client ──▶ APISIX ──▶ Ingress(nginx) ──▶ Feature Platform (fp) ──┬──▶ YugabyteDB
                                                                   └──▶ MySQL
```

**SLA dashboard 上的三个 latency envelope 就是 bisection 的轴：**

| Envelope | 含义 | SLA panel |
|----------|------|-----------|
| **E2E (Total request_time)** | client 视角的总耗时 | 192 / 359 |
| **Upstream** | fp 实际工作时间 | 371 |
| **Waiting** | `request_time − upstream_response_time`，nginx↔client 这段 | 373 |

> ⚠️ Panel 371/373 的 LogQL `pattern` 在 MCP 拉取时被截断，unwrap 的具体字段名是**从语义推断**（两个 panel selector 完全相同，唯一差异在 unwrap 字段；371 取 upstream time、373 取差值）。这是整个诊断决策的根基 panel —— **第一次用之前去 Grafana UI 看一眼 raw query 确认**，不要盲信本文。

**3-step 决策树**（Step 3 的核心 —— **不是同时看 3 个 panel，是按顺序看，因为顺序就是触发顺序**）：

```
Latency alert fires
        │
        ▼
Step 3a · 看 Waiting Latency (panel 373)
          "Waiting Latency between Ingress and Upstream"
          ── 这是最便宜的读数，一眼看「影响多大 + 是否网络问题」
          │
          ├── HIGH ──▶  网络 / client 侧
          │            原因：client ↔ datavisor 网络、ELB / CDN、client timeout
          │            Drill: ingress-nginx logs (HFAlVh2Nz), client-side traces
          │            （不需要继续看 Upstream）
          │
          └── LOW ───▶  Step 3b
                        │
                        ▼
                  Step 3b · 看 Upstream latency (panel 371)
                  "Upstream latency graph (Feature platform)"
                  ── FP 自己的工作时间
                  │
                  ├── HIGH ──▶  FP / DB 慢 → 去 EP_yHg7Gk
                  │            Drill: FP pod metrics, GC, 连接池, DB latency
                  │
                  └── LOW ───▶  Step 3c · Infra 层
                                Waiting 干净 + Upstream 干净 + Response Percentiles 还高
                                → 延迟夹在 client→ingress / ingress→FP 之间
                                ├─ Ingress (nginx) — HFAlVh2Nz
                                └─ APISIX — 0lpCu9kHk
                                常见：最近 reload / config push、controller CPU / 连接饱和
```

**为什么是树不是 4 象限**：实操上你先看 Waiting，只看一眼就能决定是不是网络分支；Waiting 高就直接走 client/网络 drill，不必再看 Upstream。4 象限是状态组合的全集（适合做参考表），但 oncall 真正走的是这条树。

**4 象限参考表**（看完树后做交叉验证用）：

| Upstream 高 | Waiting 高 | 结论 | 下一站 |
|:--:|:--:|---|---|
| Y | N | FP/DB 慢 | `EP_yHg7Gk` (FP Metrics) |
| N | Y | 网络 / ingress 慢 | `nginx` + `HFAlVh2Nz` |
| Y | Y | 后端慢 → ingress 排队倒灌 → 当 FP 处理 | 先看 FP |
| N | N | 不是 edge 真延迟事件 | 看 APISIX / client 侧 / 是不是误报（先去 vmalert dashboard） |

**关键 status code 语义**（容易误判）：
- `499` = client 主动断开 → **不计入 SLA**，但 panel 194 会显示。499 暴涨先怀疑客户网络
- `5xx` = backend 故障，**和 SLA 一起跌**
- `200|400|429` 都算成功口径（4xx 是请求格式 / 限流，不归责）
- `proxy_upstream_name=~".*backup.*"` 被剔除（backup 链上的失败不算 SLA）

---

## 4. 通用 5 步 oncall 工作流

接到 alert 必走，不要跳步。对应 [feedback_sre_triage_workflow.md](../../memory/feedback_sre_triage_workflow.md)。

**Step 1 — 读 alert（先不查任何东西）**
- 抓字段：severity / cluster / namespace / 事件时间戳 / client / metric+阈值
- **缺字段就停，问，不要 guess 默认值**
- 算调查窗口：默认 `ts ± 3min`（与多数 rule 的 `[5m]` eval 窗口对齐）。**例外**：rule 自身用更大窗口（`[10m]` / `[1h]` / batch SLA / `K8sMasterPatchSucceed` 30 天）时，调查窗口至少覆盖 rule eval 窗口的 2 倍，否则会看到空数据误判为「假报」
- **Step 1.5 — 点 Slack alert message 里的 `source` 链接**，vmalert 直接给你打开 vmui 并填好 alert 当时的 PromQL；是最快的「现在还 firing 吗 / 当前值是阈值的几倍」检查

**Step 2 — 打开「漏斗顶端」dashboard**
- Latency / SLA → `p1KqfRAMk`
- Resource / CrashLoop / OOM → `b_XlLjRMz`
- Error rate / 5xx → `HFAlVh2Nz`
- DB → `MQWgroiiz` / `1IGjQaiMk`
- 不确定 → `asfasqwe2r` (Alertmanager View) 看整体 firing 局面

**Step 3 — Bisect latency 链条**（用上面 §3 决策树）
SLA dashboard 上**按这个顺序看 panel**：**373 (Waiting) → 371 (Upstream) → 192/359 (E2E) → 194 (Non-200)**。Waiting 是最便宜的读数 + 网络问题信号，先看它能省一半时间。

**Step 4 — 钻日志**
按 Step 3 定位到的 hop 选日志面板（ingress 用 `HFAlVh2Nz`，fp 用 `CFAzjjGGz`，APISIX 用 `0lpCu9kHk`，DB 用 `-Sp_UzySz` / `JBBljUMDk`，兜底 `9aBY8rWMz`）。
**窗口永远 ±3min**，永远 time-pinned link。
要批量拉日志 → [`dv_loki_fetch`](../../../rules/skills/dv_loki_fetch.md)。

**Step 5 — 假设 → 验证**
资源？JVM/GC？DB？最近 deploy？metric pipeline 本身？
**先写一句话假设到事故频道，再用一条 query 验证，不要先操作。**
K8s mutating ops 必须前缀 `# INTENT:` 注释（见 CLAUDE.md）。

---

## 5. Alert → Dashboard Playbook（10 类）

每条 3–5 步。详细版本见 [parts/06](parts/06_latency_chain_and_playbook.md) §3。

| # | Alert family | 第一站 | Bisect | 钻日志 |
|---|--------------|--------|--------|--------|
| A | P99 latency SLA breach (client X) | `p1KqfRAMk` (设 client) | panel 371 vs 373 → FP or 网络 | `HFAlVh2Nz` |
| B | Ingress 5xx rate | `HFAlVh2Nz` | panel 22/32 → 一客户 / 一 upstream / 全局？ | panel 40 + `CFAzjjGGz` |
| C | Pod CrashLoopBackOff | `b_XlLjRMz` | panel 5/7 (restarts) + 14 (OOM) + 15 (throttle) | `9aBY8rWMz` |
| D | Node mem >90% | `sNt6IXzGk` (Node Resource，DV 主用) — 跨集群通用面板备选 `rYdddlPWk` (Node Exporter Full) / `9CWBz0bik` (External Node Exporter) | 节点 → top pods (Mixin `200ac8fdbfbb74b39aff88118e4d1c2c`) → 单 pod (`b_XlLjRMz` panel 14) | – |
| E | ClickHouse / FP CPU spike | `b_XlLjRMz` + `EP_yHg7Gk` | FP: panel 35/62/9（线程池 + rule explosion） | `CFAzjjGGz` |
| F | Yuga read latency spike | `1IGjQaiMk` | panel 64 (P99) + 71 (RPC queue) + 73 (Reactor delays) → hot tserver | `-Sp_UzySz` |
| G | MySQL connection saturation | `MQWgroiiz` | panel 92 (connections) + 10 (threads_running) + 47 (aborted) | `JBBljUMDk` |
| H | FP upstream timeout (504) | `HFAlVh2Nz` → `EP_yHg7Gk` | panel 69 (external DS) / 67 / 71 / pod restart | `CFAzjjGGz` |
| I | Ingress→upstream waiting latency 高 | `p1KqfRAMk` panel 373 | `nginx` panel 32/82（NIC / 连接） + ingress pod 自身 | `9aBY8rWMz` (ns=ingress-nginx) |
| J | "误报 / metric 不稳" | `LzldHAVnz` (vmalert) | rule 健康 → raw counter → 按 status_code 拆 → burst 节奏 | – |
| K | **`FPTopicsOffsetIncreaseZero` 类**（占当前 firing 的 50%+） | vmui (点 alert source URL) | 看 topic 是不是真的没消费：1) `kafka_topic_partition_current_offset{topic="<>"}` 30min 是否真平；2) 对应 producer pod 还活着吗（`b_XlLjRMz`）；3) 这个 topic 是不是已经废弃但 rule 没删 | `9aBY8rWMz` ns=fp |

**关于 K / chronic noise**：当前 932 条 firing 里 469 条是 `FPTopicsOffsetIncreaseZero`，97 条是 `KafkaEventExporterApplicationStderrErrors`，59 条是 `FPRuleCountZero` —— TOP 3 占 67%。**接到这类 alert 第一步是判断「我这条是新的吗」**：在 vmui 里把 source query 的时间窗拉到 24h / 7d，如果一直在 firing → 是 chronic 噪音，去 alert thread 看历史 ack / silence 状态；只有最近才出现的才按 fp 真故障处理。**Per-client 变种**（`*_Dci_tuesday_to_saturday` / `*_Nasa` / `*_Syncbank` / `*_Fedex…`）规则相同。

J 的 4 步序列来自 [feedback_loki_metric_debug.md](../../memory/feedback_loki_metric_debug.md)。

**Alertname → playbook 反查**：Slack message 里看到的真实 alertname 形如 `RTIngressP99ResponseTime_Affirm` / `FPTopicsOffsetIncreaseZero_Nasa`。**通用规则**：
- `RTIngress*` / `Apisix*` / `IngressNginx*` / `IngressSLA*` / `Aws(Alb|ApiGateway)*` → **A**
- `*5xx*` / `*Non200*` / `*4..*` 走 ingress 路径 → **B**
- `K8sPod*Killed` / `K8sPod*Restarted*` / `K8sPodUnableToStart` / `KubernetesContainerOomKiller` → **C**
- `K8sNode*` / `Node*` / `HighCpuUsageOfContainer*` → **D** 或 **E**（mem/disk 类 D，CPU 类 E）
- `Yuga*` / `yugabytedb*` → **F**
- `Mysql*` / `Hikari*` / `MySQLReplication*` → **G**
- `K8sFP*` 含 `Non200` / `Error` / 504 → **H**
- `FPTopicsOffsetIncreaseZero*` / `KafkaEventExporter*` / `FPRuleCountZero` → **K**（噪音判别优先）
- 其余 `FP*` / `RuleEngine*` / `BatchJob*` → 走 §5 playbook 找最近的家族，或直接进 [parts/05 §告警目录](parts/05_vm_and_alerts.md#告警目录按类别--真实-rule-名--严重度--应对-dashboard)

完整 alertname 清单 + severity + dashboard 对照见 [parts/05 §告警目录](parts/05_vm_and_alerts.md)。

---

## 5b. Worked Example — Kafka Lag / MirrorMaker 双集群同步

第二常见的 alert 家族（仅次于 latency）。**两个 alertname，两个 dashboard，搞混是第一坑**。

**架构**：双集群 Kafka（`cluster_a` / `cluster_b`），MirrorMaker2 (MM2 / Kafka Connect) 在两边之间双向复制。

> **DV-specific topology**：DV **不用** MM2 默认的 `<source>.<topic>` 重命名 —— 同名 topic 在两个 cluster 上都存在，方向通过 `source` / `target` label 区分。复制是双向的（a→b 也 b→a）。
> 核心 metric：`kafka_mirror_sync_lag{source, target, topic, partition}` —— 单位是 **record 数**，不是秒。

**两类 alertname**（容易搞混）：

| Alertname pattern | Severity | 含义 | First dashboard |
|---|---|---|---|
| `MirrorMakerConsumerLagDecliningTooSlow` | PAGER | MM2 复制变慢。**衰减率**判定（不是绝对阈值）：`(L_5min前 − L_now) / L_5min前 < 0.3` AND `L_now > 500`。定义在 `kafka_rules.yml` group `kafka`，`for=20m` | **MirrorLag v2** (`-N7cUPZNk`) |
| `Kafka_*_consumergroup_lag_High`（cm / fp / detection / VelocityDetail_per-client / …） | HIGH | 业务消费组追不上 topic 生产速度。Per-client 变体：galileo / onefinance / tabapay / wex … | **Kafka Exporter for all** (`cluster_kafkfa_exporter`) |

**4 步 triage 流程**：

```
Step 1 · 看 alertname
    ├─ MirrorMaker*                       → MirrorLag v2 (-N7cUPZNk)
    └─ Kafka_*_consumergroup_lag_High     → Kafka Exporter (cluster_kafkfa_exporter)

Step 2 · 设变量
    MirrorLag v2: cluster (group prefix, 无 -a/-b) / namespace / topic
    Exporter:     pod (绑定到一个 Kafka 集群) / topic / consumergroup

Step 3 · 看主 panel
    MirrorLag v2: panel 1 (MM2 pod up 状态) + panels 2/3 (lag a→b, b→a 时间序列)
    Exporter:     panel 12 "Lag by Consumer Group" (per cg + topic + partition)

Step 4 · 定位根因
    ① MM2 pod 挂了 → 重启（最常见）
    ② Lag 不动 + consumer offset rate ≈ 0 → consumer 崩了
    ③ Lag 在涨 + producer rate > consumer rate → consumer 跟不上
       (downstream FP 慢 / CPU / GC) — 对比 Exporter panel 3 (produce) vs 4 (consume)
```

**坑**：
- `MirrorMakerConsumerLagDecliningTooSlow` 的 namespace filter 硬编码 `prod|pci|gov|demo` —— `useastprod` 这种命名空间**不在覆盖范围内**，MM2 那里挂了也不会触发这个告警
- MirrorLag v2 默认时间窗 30m —— 接到 20-30min 前触发的 alert 时，要先拉宽到 1h，否则看不到触发时的趋势
- MirrorLag v2 的 `cluster` 变量是 `kubernetes_cluster_groups`（如 `aws-uswest2-prod`），**不带** `-a` / `-b` 后缀

详见 [parts/08_kafka_mirrorlag.md](parts/08_kafka_mirrorlag.md) + [parts/09_kafka_exporter.md](parts/09_kafka_exporter.md)。

---

## 5c. Latency Triage 的 Phase-2 — 判断 client 打哪个 cluster

接到 latency alert 后，**走完 SLA dashboard 决策树之前**，先确认 client 当前的物理 cluster 落点：

- **Dashboard**：`Multi-Cluster Traffic Distribution` (`X2qhqpjSk`)
- **关键 panel**：panel 9（piechart `by (cluster)`）—— 一眼看 client 流量在 cluster A vs B vs C 的分布
- **变量**：`cluster` 是 group prefix（如 `aws-apsoutheast1-prod`），dashboard 自己在 panel 里通过 regex 追加 `-a` / `-b` / `-c`

**坑 / caveat**：
- Loki 驱动（不是 Prom），并且 panel 内带 `timeFrom=1m/5m/10m` offset，**非实时**。当"流量去哪了"的事后取证用，不当 latency root-cause 工具
- panel 7（cluster-c）默认隐藏，且数据源是不同的 Loki (`M2q8i3Q7z`)，需要的时候手动开
- fp-ui / fp-rt 流量在所有 panel 都被过滤掉

详见 [parts/07_multi_cluster_traffic.md](parts/07_multi_cluster_traffic.md)。

---

## 6. 告警体系关键数字（采样 2026-05-21）

- **540 条 alerting rule，0 条 recording rule**（recording rule 在别处定义，rules API 拉不到）
- 49 个 rule group，分布在 33 个 yaml 文件
- Severity 分布：PAGER 142、HIGH 283、MEDIUM 18、WARNING 6、CRITICAL **1**（`LokiPanics`）、**无 severity 91 条** ← 路由不准的来源
- Team 分布：fp 276、infra 181、decision 5、**无 team 79 条** ← 不知道找谁
- **当前 firing 932 条**，TOP 3 占 67%：
  - `FPTopicsOffsetIncreaseZero` × 469 ← 噪音税最大来源
  - `KafkaEventExporterApplicationStderrErrors` × 97
  - `FPRuleCountZero` × 59

完整 alert 目录（A–I 9 大类、所有真实 rule 名 + 严重度 + 应对 dashboard）见 [parts/05 §告警目录](parts/05_vm_and_alerts.md#告警目录按类别--真实-rule-名--严重度--应对-dashboard)。

---

## 7. 高频踩坑速记

### SLA dashboard
1. 没选 `client` → panel 全空，不是监控挂了
2. `Batch_Pipeline` 不跟 `client` 联动 → Batch row 空白看着像挂了
3. Panel 192 是 "Approximate"，事故复盘要用 panel 359 (LogQL ground truth)
4. SLA 多口径轻微不一致正常（ES vs Loki recording vs raw counter，延迟不同）
5. `min(...[2m:1m])` 是「拎最差 1 分钟」，不是平均值

### Logging
6. Generic Logging 的 `$level` = `stream` (stdout/stderr)，**不是** 应用日志级别 → 用 `$search` 写 `ERROR`
7. `gcp-uswest1-prod-a` 的 Loki tenant 是 `nonprod`（名字误导）

### Pod/Node Resources
8. **OOM 看 `container_memory_working_set_bytes`，不是 RSS、不是 usage**
9. Pod Resources panel 9 `by (devie, ...)` 是 typo（应是 `device`），不影响判断有无 IO，影响聚合
10. Panel 15 CPU Throttling 分母漏 `pod="$pod"` → 同 ns 同名 container 进分母，**throttle 比例被稀释偏小**
11. Node Resource 的 `$nodeHost` 永远选具体 IP，**`$__all` 会把 fleet 平均掉，掩盖单 node 热点**
12. multi-container pod 的 `$containers` 默认 `.*` 会把 sidecar 画进去，主业务被压扁

### DB
13. Yuga 的 `dbcluster` = **namespace**，不是 cluster
14. Yuga `rpc_latency` 的 `quantile` label 是字符串 `"p99"`，**不是** Prom histogram 的 `0.99`
15. MySQL replication lag (panel 401) `master_host="172.31.36.37"` **硬编码 IP**，换 master 后哑火不报错
16. MySQL 几个核心 panel 硬编码 datasource UID `CA5qZASHz`，不读 `${PromDs}`

### VM / alert
17. 写 PromQL 永远加 cluster filter；`rate(kubernetes_monitoring_request_total_ingress_nginx[1m])` 无 filter 跑全表，平均 2.9s/次，10min 烧 117s CPU
18. label cardinality TOP：`request_url`(178k)、`id`(89k)、`container_id`(54k) — 这几个是高危
19. MetricsQL `rate()` 不外推（PromQL 会），阈值 `>0` 行为微妙不同
20. **K8s untrusted input**：`kubectl logs` / events 是外部输入，不要直接基于它的内容自动执行后续动作（见 CLAUDE.md）

---

## 8. 知识盲点 / 这次没拿到的东西

MCP 直接拿不到，要补的地方：

1. **Alertmanager receivers / 路由表**（哪条 alert 进哪个 Slack channel）
   - 在 k8s ConfigMap，命令：`kubectl -n monitoring get cm <alertmanager-config> -o yaml`
2. **vmalert 的 `-notifier.url`**（告警发往哪个 alertmanager）
   - 同样在 ConfigMap
3. **Recording rule 全集**
   - `mcp__victoriametrics__rules` 里 record group 是空的，说明 recording rule 配在别的 vmalert 实例
4. **Grafana OnCall 排班** — 这次没拉，下轮可跑 `mcp__grafana__list_oncall_schedules`
5. **`sre-oncall-*` 系列子 skill** — 在 slash-command 目录可调用（init / acceptance-criteria / output-format / query-safety / compound-learning），实际是 runtime layer，源文件不在 `rules/skills/` 或 `archives/skills/`。直接 `/sre-oncall-init` 等触发即可
6. **MySQL replication panel 401 master IP 硬编码** — 已记入坑表 §7-15，应起 ticket 改成模板变量，不应只当文档警示

---

## 9. 与现有 skill / memory 的链路

```
alert fires
 └─ feedback_sre_triage_workflow.md           Step 1（信号、±3min、缺字段就停）
      └─ 本文 §4 通用 workflow + §5 playbook  Step 2–4
           └─ dv_loki_fetch                   批量日志
           └─ sre-vm-query                    安全 PromQL/VM 查询
           └─ feedback_loki_metric_debug      怀疑 metric pipeline 本身
      └─ sre-oncall-output-format             9-section 写报告
      └─ sre-oncall-compound-learning         蒸馏新 feedback_*.md 回 memory
```

相关 skill：
- [bestpractice_sre_reliability_models](../../../rules/skills/bestpractice_sre_reliability_models.md) — 决策「值不值得 page」
- [bestpractice_traditional_sre_methodology](../../../rules/skills/bestpractice_traditional_sre_methodology.md) — RED/USE 方法
- [dv_loki_fetch](../../../rules/skills/dv_loki_fetch.md) — Loki 批量
- [sre-vm-query](../../../rules/skills/sre-vm-query.md) — VM MCP 安全用法

相关 memory（auto-loaded）：
- `feedback_sre_triage_workflow.md` — plan-first、±3min、缺字段就停
- `feedback_loki_metric_debug.md` — rule health → raw counter → 按 status_code 拆 → burst 节奏
- `reference_loki_config.md` — tenant / cluster mapping（含 `gcp-uswest1-prod-a` = nonprod 陷阱）

---

## 10. 给别人讲这套监控时的 30 秒版本

> 我们的监控分三层：metrics 全在 VictoriaMetrics（vm-mgt-a），告警全走 vmalert（不是 Grafana managed），日志全在 Loki（多租户，tenant=prod/nonprod）。
>
> 出事看 dashboard 的顺序由 latency 链条决定：client → APISIX → ingress(nginx) → fp → yuga/mysql。
>
> 第一站永远是 **SLA dashboard** (`p1KqfRAMk`)，用它的三个 panel（371 upstream、373 waiting、194 non-200）做 bisection：fp 慢、网络慢、还是 client 自己 close。
>
> 定位到 hop 之后再去对应 dashboard：fp 用 `EP_yHg7Gk`，ingress 用 `HFAlVh2Nz`，pod 用 `b_XlLjRMz`，DB 用 `1IGjQaiMk` / `MQWgroiiz`。
>
> 写 PromQL 一定加 cluster filter。OOM 看 working_set 不是 RSS。Node 变量永远选具体 IP 不要 All。
>
> 告警目录看 [parts/05](parts/05_vm_and_alerts.md)；alert→dashboard playbook 看 [parts/06](parts/06_latency_chain_and_playbook.md)。
