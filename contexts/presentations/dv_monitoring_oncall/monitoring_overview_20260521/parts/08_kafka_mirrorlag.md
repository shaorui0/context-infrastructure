# Kafka MirrorMaker & MirrorLag (`-N7cUPZNk`)

> Dashboard: <https://grafana-mgt.dv-api.com/d/-N7cUPZNk/mirrorlag-v2>
> Title: `MirrorLag V2`  ·  Folder: General  ·  Datasource: VictoriaMetrics (`BXkAnTSNz` / `CA5qZASHz`)
> 创建: zhenglan.hou (2024-11-01)  ·  最近更新: runzi.yang (2026-05-14)
> Panel 数: 3   ·   默认时间窗: `now-30m`

非常精简的一个 dashboard（只有 3 个 panel），但它对应的是一类 P1 PAGER 告警 (`MirrorMakerConsumerLagDecliningTooSlow`)，所以 oncall 时一定会被打开。

---

## 架构：双集群 Kafka 同步

DataVisor 的每个 region（e.g. `aws-uswest2-prod`）下面有两个 Kubernetes cluster，命名为 `*-a` 和 `*-b`：

```
aws-uswest2-prod-a   ←──── MirrorMaker2 ────→   aws-uswest2-prod-b
   (cluster_a)                                       (cluster_b)
```

两个 cluster 各自跑一套 Kafka，**互为镜像**。replication 由 **MirrorMaker 2 (MM2)** 完成，部署形态是 namespace 里的 `mirrormaker2-*` deployment（实测 prod 里看到：`mirrormaker2-5457d68748-*` 跑在 `*-prod-a`，`mirrormaker2-57c685c687-*` 跑在 `*-prod-b`，namespace 既有 `prod` 也有 `useastprod` / `apsoutheastprod`）。指标暴露走 sidecar `mirrormaker-exportor-v2-*` Pod，通过 `prom_apps` scrape job (`export_type="prom_apps"`) 进 VictoriaMetrics。

**topic 命名**：和 MM2 默认 `DefaultReplicationPolicy`（带集群前缀）不同，DV 这边**保留原 topic 名**——也就是 `prod_fp_velocity.taskrabbit` 这个 topic 同时存在于 cluster_a 和 cluster_b，由 `source` / `target` label 区分方向，而**不是**重命名成 `cluster_a.prod_fp_velocity.taskrabbit`。从 metric label 也能直接验证：

```
kafka_mirror_sync_lag{topic="prod_fp_velocity.sofi", source="cluster_a", target="cluster_b", partition="23"} 63
```

含义就是：cluster_a 上 `prod_fp_velocity.sofi` partition 23 的当前 offset，比 cluster_b 上**已经同步过去**的 offset 高 63 条 message。**Lag = offset_source − offset_target_replicated**，单位是 record 条数（不是字节、不是秒）。`kafka_mirror_sync_offset` 是同一个 series 的绝对 offset（典型量级几百万到几千万），`kafka_mirror_sync_lag` 是差值。

**双向 mirror**：实测 `source` / `target` 各自的 label values 都是 `{cluster_a, cluster_b}`，也就是 a→b 和 b→a 两条流同时存在。这就是为什么 dashboard 有两个对称的 panel。

---

## 何时打开（典型 alert）

这个 dashboard 是 alert `MirrorMakerConsumerLagDecliningTooSlow` 的 runbook landing page——alert annotation 里硬编码了带变量的 deeplink：

```
Click https://grafana-mgt.dv-api.com/d/-N7cUPZNk/mirrorlag-v2?orgId=1
  &var-cluster={{ $labels.kubernetes_cluster }}
  &var-namespace={{ $labels.kubernetes_namespace }}
  &var-source={{ $labels.source }}
  &var-target={{ $labels.target }}
  &var-topic={{ $labels.topic }}
  &from=now-1h&to=now
```

也会在以下场景被引用：
- **`Kafka_*_consumergroup_lag_High`** 系列 alert（`Kafka_fp_consumergroup_lag_High`, `Kafka_cm_consumergroup_lag_High`, `Kafka_detection_consumergroup_lag_High`, `Kafka_fp_al/extds/backfill_lag_High`, `Kafka_fp_consumergroup_lag_VelocityDetailHigh` 等）——这些是 **consumer group 消费滞后** 告警，不是 mirror 告警，但 oncall 经常需要先排除 mirror 是否同步不上，因此一并打开此 dashboard。
- **MM2 pod down / `up{kubernetes_pod_name=~"mirrormaker2.*"} == 0`**——dashboard 第一个 panel 就是为此。

> **重要区分**：
> - `MirrorMakerConsumerLagDecliningTooSlow` = **MM2 跨集群复制慢**（这个 dashboard 直接覆盖）
> - `Kafka_*_consumergroup_lag_High` = **业务 consumer group 消费慢**（要看 Kafka Exporter dashboard，mirror 只是诸多 consumer group 之一）

---

## 变量

| 变量 | 类型 | 默认 | 数据来源 | 作用 |
|------|------|------|----------|------|
| `cluster` | query (single) | `aws-uswest2-prod` | `label_values(kafka_mirror_sync_lag, kubernetes_cluster_groups)` | 选 region。注意是 **cluster_groups**（去掉 `-a/-b` 后缀的 region 名），匹配时 query 用 `kubernetes_cluster=~"${cluster}.*"` 同时覆盖 a/b |
| `cluster_label` | query (multi, hidden) | `$__all` | `label_values(kube_pod_info{kubernetes_cluster_groups="$cluster"}, kubernetes_cluster)` | 展开成具体的 `-a` / `-b`，用于 panel 4 的 `repeat`，每个 cluster 一个 stat 块 |
| `namespace` | query (single) | `prod` | `label_values(kafka_mirror_sync_lag{kubernetes_cluster=~"$cluster.*"}, kubernetes_namespace)` | 选 namespace。可能取值：`prod`, `pci`, `gov`, `demo`, `useastprod`, `apsoutheastprod` 等 |
| `topic` | query (multi, all) | `$__all` | `label_values(kafka_mirror_sync_lag{kubernetes_cluster=~"$cluster|.*", kubernetes_namespace="$namespace"}, topic)` | 选 topic，可多选。默认 all 时会画出所有 topic 的 partition 一起，partition 多时会很糊 |

URL 里看到的 `source=cluster_a` / `target=cluster_b` **不是 dashboard 变量**——两个 timeseries panel 里 `source` / `target` 是**硬编码**的（`source="cluster_a", target="cluster_b"` 和反向），URL 上的 `var-source` / `var-target` 只是 alert template 加上去的，dashboard 不会消费。

---

## 关键 panel + 查询

### Panel 4 (`stat`) — Mirror maker status - ${cluster_label}

```promql
up{kubernetes_cluster=~"(${cluster_label})",
   kubernetes_pod_name=~"mirrormaker2.*",
   kubernetes_namespace=~"$namespace"}
```

- 用 `repeat="cluster_label"` 横向展开成多个 stat block（一个 `-a`、一个 `-b`，外加可能的 `useastprod` 等额外 namespace）。
- value mapping：`>=0.51` → "Running" (dark-green)，`<0.51` → "Not Running" (dark-red)。
- 数据源 UID `CA5qZASHz`（与 lag 那两个面板 `BXkAnTSNz` 不同——这里是 infra prom、lag 是 app prom）。

### Panel 2 (`timeseries`) — Mirror Lag cluster_a →→ cluster_b

```promql
kafka_mirror_sync_lag{
  kubernetes_cluster=~"${cluster}.*",
  kubernetes_namespace="$namespace",
  source="cluster_a", target="cluster_b",
  topic=~"$topic"
}
```

- Legend: `{{source}} -> {{target}}: {{topic}}-{{partition}}`
- legend table 同时显示 `lastNotNull` 和 `max`，便于快速定位"哪条线在飙"。
- unit: `short`（裸条数）；阈值色：green @ 0、red @ 80（仅 panel 边框提示，**不是**告警阈值）。

### Panel 3 (`timeseries`) — Mirror Lag cluster_b →→ cluster_a

同上，`source="cluster_b", target="cluster_a"`，反向流。

---

## 健康 / 告警阈值

### Panel 自身的视觉阈值（弱信号）

两个 timeseries panel 的色阶都是 green @ 0、red @ 80。**80 这个数字不是告警阈值**，只是 panel 视觉提示，意思是"个位/十位的 lag 完全正常，过百开始要警觉"。

### 真正的告警阈值（强信号）— `MirrorMakerConsumerLagDecliningTooSlow`

定义在 `/config/kafka_rules.yml`，group `kafka`，state pending 时已经 P1 PAGER：

```promql
(
  sum by (kubernetes_cluster,kubernetes_namespace,source,target,topic) (
    max_over_time(kafka_mirror_sync_lag{kubernetes_namespace=~"prod|pci|gov|demo"}[5m] offset 5m)
  )
  -
  sum by (kubernetes_cluster,kubernetes_namespace,source,target,topic) (
    kafka_mirror_sync_lag{kubernetes_namespace=~"prod|pci|gov|demo"}
  )
)
/
  sum by (kubernetes_cluster,kubernetes_namespace,source,target,topic) (
    max_over_time(kafka_mirror_sync_lag{kubernetes_namespace=~"prod|pci|gov|demo"}[5m] offset 5m)
  )
< 0.3
AND
  sum by (...) (kafka_mirror_sync_lag{...}) > 500
```

`for: 1200s`（20 分钟）持续才 fire。labels: `priority=P1`, `severity=PAGER`, `team=infra`, `fp=1, infra=1, oncall=1`。

**人话翻译**：
- 取 **5 分钟前** 的 lag 作为"过去高水位" `L_past`；
- 取 **现在** 的 lag `L_now`；
- 计算 `decline_ratio = (L_past - L_now) / L_past`；
- 如果 `decline_ratio < 0.3`（即 5 分钟内 lag 下降不到 30%）**且** `L_now > 500`，持续 20 分钟，则 fire。

也就是说告警不关心"lag 多高"本身，而关心"**lag 是否在以足够的速度被消化**"。这是个比绝对阈值更合理的设计：一次 burst 把 lag 推到 5 万都不会告，只要 MM2 在追；但如果 lag 卡在 800 一直不降，就告。

实测里 namespace filter 是 `prod|pci|gov|demo`，所以 `useastprod` / `apsoutheastprod` 这类 namespace 不会触发这个告警——属于已知盲区（见"已知坑"）。

---

## Lag-high alert 的完整 triage 步骤（5 步）

```
Alert: MirrorMakerConsumerLagDecliningTooSlow
  labels: kubernetes_cluster=aws-uswest2-prod-b
          namespace=prod
          source=cluster_a, target=cluster_b
          topic=prod_fp_velocity.standardbank
```

**Step 1 — 跟 alert 链接打开 MirrorLag V2**（链接里已经把 cluster/namespace/topic 填好）。把时间范围从默认 30m 拉宽到 **1h+**，先看 lag 曲线的形状：
- **斜率向下但慢** → 真的复制不动，进 Step 3
- **平台 / 缓慢上升** → MM2 完全卡住，进 Step 2
- **已经回落到接近 0** → 已自愈，确认 5 分钟无回升后 ack
- **尖锐 spike 然后秒回** → 单次 burst，业务上游瞬时洪峰，记一笔

**Step 2 — 先看 MM2 自己活着没**。Panel 4 (Mirror maker status) 应该全绿。如果哪个 cluster 的 stat 是 "Not Running"（红）：
- `kubectl -n <ns> get pods -l app=mirrormaker2 -o wide` 看 pod 状态；
- 检查 `kafka_mirrormaker_async_error`（高基数 series，~1500 个 series，要用聚合查）；
- 这种情况按 MM2 pod down 处理，重启 / 看 OOM / 看 broker 连接。

**Step 3 — 区分"单 topic 故障" vs "系统性故障"**。把 `topic` 变量改成 `All`，看 panel 2/3：
- **所有 topic 都在飙** → 大概率 **target 集群 broker / 磁盘** 问题（写入端撑不住），去看对应 cluster_b 的 Kafka broker dashboard（disk/CPU/under-replicated partitions）；
- **只有这一个 topic 飙** → topic 级问题，进 Step 4。

**Step 4 — 定位到 partition**。legend 里的 `{{topic}}-{{partition}}` 会告诉你是哪个 partition 拖后腿。常见原因：
- 该 partition 的 leader broker 慢 / hot；
- producer 把 key 打偏，单 partition 流量暴涨（看 panel 上是不是只有 1~2 个 partition 在涨，其他持平）；
- target cluster 上该 topic 的 partition leader 不健康。

**Step 5 — 看反向 panel 做交叉验证**。如果 a→b 严重、b→a 正常，倾向 target (cluster_b) 写入端问题；如果两个方向都有问题，倾向网络 / MM2 自身 / 共享依赖（Schema Registry、ZK/KRaft）问题。

**收尾**：alert 用的是 *declining too slow* 判据，所以"看到 lag 在下降"还不够，要看到 `decline_ratio` 重新爬过 30%。最稳的判定：等 lag 回到 < 500，alert 自动 resolve。

---

## 与 Kafka Exporter dashboard 的协作

这个 dashboard **不覆盖** 业务 consumer group 的消费滞后。当 oncall 收到 `Kafka_fp_consumergroup_lag_High` / `Kafka_cm_consumergroup_lag_High` 这类告警时：

1. **先看业务 consumer group 的 Kafka Exporter dashboard**（`kafka_consumergroup_lag` 系列，DV 内部另一个 dashboard），定位是哪个 consumer group（不是 MM2 这个 consumer group）；
2. 如果发现告警的 consumer group 正好是 **mirror-maker** 自己（MM2 在 source cluster 上以 consumer 身份消费），那么 lag 本质就是 mirror lag，跳到本 dashboard 用 Step 1~5；
3. 否则是业务 consumer 自己消费不动，跟 mirror 无关，去找对应业务 pod。

简单分工：
- **MirrorLag V2 (本文件)** → 关心 "source→target offset gap"
- **Kafka Exporter dashboard** → 关心 "任意 consumer group → topic 的 committed offset gap"

两者的相同点：单位都是 record 条数；不同点：本 dashboard 的 series 维度是 `(source, target, topic, partition)`，Exporter 的维度是 `(consumergroup, topic, partition)`。

---

## 已知坑

1. **`source` / `target` 不是 dashboard 变量**——URL 里有 `var-source` / `var-target` 是 alert annotation 拼出来的，dashboard 收到也没用。panel 2 / panel 3 永远画固定方向。想看 b→a 看 panel 3，不要去改 URL。
2. **`mark`=`useastprod` / `apsoutheastprod` 等 namespace 不在告警范围内**。Alert query 写死 `kubernetes_namespace=~"prod|pci|gov|demo"`，其他 namespace 的 mirror 失败**不会触发告警**，只能靠 dashboard 主动巡检。
3. **`cluster` 变量是 `kubernetes_cluster_groups`，不是 `kubernetes_cluster`**。也就是 `aws-uswest2-prod`（无 `-a/-b` 后缀）。panel 里用 `=~"${cluster}.*"` 同时匹配两边。直接复制 alert label 里的 `kubernetes_cluster` 值（如 `aws-uswest2-prod-b`）到这个变量会**搜不到**。alert 模板里走的是 `var-cluster={{ $labels.kubernetes_cluster }}`，所以从 alert 跳链接进来时，变量是 `aws-uswest2-prod-b`，dashboard 靠 `=~"$cluster.*"` 仍然能匹配（因为 `.` 通配），但下拉里选不到这个值；要"切到另一个 region"必须改回 group 名。
4. **lag 单位是条数，不是时间**。dashboard 里 "lag = 63" 是 63 条 message，不是 63 秒。要换算成时间延迟，需要看该 topic 的 produce rate（去 Kafka Exporter dashboard 看 `kafka_topic_partition_current_offset` 的 rate）。
5. **默认时间窗 30m 偏短**。`MirrorMakerConsumerLagDecliningTooSlow` 的判定窗是 5m offset 5m + `for=20m`，意味着 alert fire 时事件其实已经存在 ~25 分钟。打开 dashboard 第一件事先把时间拉到 `now-1h` 或 `now-2h`，否则看不到事件起点。
6. **panel 视觉阈值 (red @ 80) 跟告警阈值无关**。看到 red 不代表告警，看到 green 也不代表没事——告警判据是"下降率"，可能整条线在 1000 但在快速下降，告警不响；也可能整条线在 600 平着不动，告警就响了。
7. **legend `lastNotNull` 在 lag 已 resolve 时会显示一个很小的值**。看 lag 历史最高一定要看 legend table 里的 `max` 列，不是 `lastNotNull`。
8. **panel 4 的 datasource UID 与 panel 2/3 不同**（`CA5qZASHz` vs `BXkAnTSNz`）。两个数据源都通向 VictoriaMetrics，但 scrape 路径不同（infra prom vs app prom）。Mirror maker pod up 走 infra prom，`kafka_mirror_sync_lag` 走 `export_type="prom_apps"`。如果其中一个 datasource 出问题，可能 panel 4 全 N/A 但 panel 2/3 正常，或反过来。
