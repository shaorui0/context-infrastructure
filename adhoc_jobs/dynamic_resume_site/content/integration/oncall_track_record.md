# META
id: w-oncall-track
kicker_en: TRACK RECORD
kicker_cn: 值班记录
title_en: On-Call Track Record: a Distilled Production Incident Library
title_cn: On-call 值班记录：生产事故蒸馏知识库
domains: [incident, data, obs, infra, dist, release, platform]

# EVIDENCE

## 1. ClickHouse CPU saturation: multi-signal attribution [data, incident]
name_en: CPU at 92%: queries were the culprit, merges were the alibi
name_cn: CPU 92%：查询是真凶，merge 只是在场证明
note_en: A ClickHouse node ran at 92% CPU (27.6 of 30 cores) and the first look at `system.merges` said "merge debt". Cross-checking `system.processes` against per-thread `top -H` reversed the verdict: three concurrent `SELECT *` full-table scans, each reading ~700M rows, consumed ~67% of CPU while merges contributed ~10%. Conclusion codified as a rule: never attribute CPU from one signal source; query view and thread view must agree.
note_cn: 一个 ClickHouse 节点 CPU 跑到 92%（30 核用掉 27.6 核），先看 `system.merges` 得出的初判是 merge 欠债。用 `system.processes` 与线程级 `top -H` 交叉验证后结论反转：3 条并发的 `SELECT *` 全表扫描（每条约 7 亿行）占约 67% CPU，merge 只占约 10%。沉淀为规则：CPU 归因不许只看单一信号源，查询视图与线程视图必须互证。

## 2. Admission webhook broke every deploy at once [release, infra, incident]
name_en: One upgrade blocked all deployments cluster-wide
name_cn: 一次升级阻断全集群部署
note_en: An ingress-nginx helm upgrade rebuilt the ValidatingWebhookConfiguration without its caBundle, so the API server could no longer verify the webhook's TLS and every helm install carrying an Ingress failed with `x509: certificate signed by unknown authority`. The routing insight: multiple tenants failing in the same minute through the same mechanism is a cluster-level infrastructure signal, so investigation skipped the application layer entirely. Fix was patching the CA back from the Secret; long-term, webhook certificates moved off one-shot helm hooks.
note_cn: 一次 ingress-nginx helm 升级重建了 ValidatingWebhookConfiguration 但丢失 caBundle，API server 无法验证 webhook TLS，所有包含 Ingress 的 helm install 全部报 `x509: certificate signed by unknown authority` 失败。定位关键：多个租户同一分钟以同一机制失败，这是集群级基础设施信号，调查直接跳过应用层。修复是从 Secret 把 CA patch 回去；长期方案是让 webhook 证书脱离一次性 helm hook 管理。

## 3. A schema change three hops upstream [data, release, incident]
name_en: An upstream table change broke data landing three hops away
name_cn: 上游三跳之外的表结构变更打断数据落地
note_en: A release changed a MySQL table from 4 columns to 2; the CDC connector's cached schema no longer matched the binlog, so it crashed and its restart triggered a full snapshot, whose read-type events left the `_sign` column unmapped and rejected by ClickHouse's NOT NULL constraint. A second failure in the same window was closed by a network-layer argument: a connection dying after 431 seconds of idle cannot be MySQL's 8-hour wait_timeout, so the killer was an intermediate TCP idle timeout, bypassed with heartbeats and keepalive.
note_cn: 一次 release 把 MySQL 某表从 4 列改成 2 列，CDC connector 缓存的旧 schema 与 binlog 不再匹配，崩溃重启后触发全量 snapshot，snapshot 的读类型事件没有映射 `_sign` 列，被 ClickHouse 的 NOT NULL 约束拒绝写入。同窗口的第二个故障靠网络层论证收案：连接在空闲 431 秒后被杀，不可能是 MySQL 的 8 小时 wait_timeout，凶手是中间网络层的 TCP idle 超时，用 heartbeat 加 keepalive 绕开。

## 4. The lag that restarts could not fix [data, dist, incident]
name_en: Replication lag with a per-partition throughput ceiling
name_cn: 重启修不好的复制积压：每分区吞吐天花板
note_en: Cross-cluster mirror replication lag stayed high with the mirroring service healthy: no errors, no restarts, normal resource usage, so restarting it would have fixed nothing. The binding constraint was capacity: a large tenant's QPS had grown past what the topic's 3 partitions could replicate, since per-partition throughput is a hard ceiling on mirror parallelism. Lag self-converged after the peak; the durable fix was a partition expansion review, flagged as irreversible and gated on key-distribution analysis.
note_cn: 跨集群 mirror 复制积压持续高位，而复制服务本身健康：无报错、无重启、资源正常，重启不解决任何问题。真正的约束是容量：某大租户 QPS 增长超过了 topic 仅有的 3 个分区所能承载的复制吞吐，每分区吞吐是 mirror 并行度的硬天花板。峰值过后 lag 自然收敛；长期修复是分区扩容评审，并标注为不可逆操作，需先评估 key 分布。

## 5. The CrashLoop with empty logs [data, infra, incident]
name_en: Metadata pinned to a Pod IP that no longer existed
name_cn: 元数据钉死在一个已消失的 Pod IP 上
note_en: The frontend of another OLAP engine sat in CrashLoopBackOff at 285 restarts with `kubectl logs` completely empty, because the process logs to a file, not stdout; the real evidence required exec-ing into the container. The log showed the internal metadata store had registered the node under an old Pod IP; after restart the IP changed, the node's role stuck at UNKNOWN, its query port never opened, and the liveness probe killed it every 60 seconds (exit 143). Permanent fix: headless Service plus FQDN registration, so identity survives IP churn.
note_cn: 另一款 OLAP 引擎的 frontend 陷入 CrashLoopBackOff，重启 285 次而 `kubectl logs` 完全为空：进程把日志写文件不写 stdout，真正的证据要 exec 进容器才能拿到。日志显示内部元数据库用旧 Pod IP 注册了节点；重启后 IP 变化，节点角色停留在 UNKNOWN，查询端口始终不开，liveness probe 每 60 秒杀一次（exit 143）。永久修复：headless Service 加 FQDN 注册，让节点身份不随 IP 漂移。

## 6. Liveness probes versus quorum systems [dist, infra, incident]
name_en: The probe that kept killing a healthy quorum
name_cn: 把健康的 quorum 系统反复误杀的探针
note_en: Kafka brokers in KRaft mode restarted in rotation, each restart lining up with a `Liveness probe failed` event rather than any crash signal, and every false kill forced another controller re-election, compounding the instability. The fix inverted the usual instinct: for quorum-based stateful systems, liveness must be conservative (high failure threshold, long periods) while readiness stays sensitive to shed traffic. The restart storm stopped once the probe stopped outrunning the system's own recovery.
note_cn: KRaft 模式的 Kafka broker 轮流重启，每次重启都与 `Liveness probe failed` 事件对齐，而非任何自身崩溃信号；每次误杀又强制一轮 controller 重选举，不稳定被层层放大。修复反直觉：对基于 quorum 的有状态系统，liveness 必须保守（高失败阈值、长周期），readiness 保持敏感用于摘流量。探针不再抢在系统自愈之前动手，重启风暴即停。

## 7. Prove the alert false first [obs, incident]
name_en: A P99 alert disproven before it was explained
name_cn: 先证明告警是假的，再解释它
note_en: A latency alert claimed P99 was breaching while application logs and APM in the same time window showed no slow requests and no error-rate movement. The investigation's first move was to disprove real user impact, then explain the metric: scrape-time misalignment across instances plus histogram bucket aggregation skew had inflated the computed P99. Closed as a false alert with the evidence chain attached, and hardened with rule guardrails so the same skew pattern cannot page again.
note_cn: 一条延迟告警声称 P99 越限，但同一时间窗口的应用日志与 APM 显示没有任何慢请求，错误率也无波动。调查第一步是先证伪真实用户影响，再解释指标：多实例采集时间错位叠加 histogram 分桶聚合偏差，把计算出的 P99 虚高。以假告警结案并附完整证据链，随后加固告警规则，让同一偏差模式无法再次呼叫值班。

## 8. Scale-out nodes that never joined [infra, incident]
name_en: Layered isolation, then roll back to known-good
name_cn: 分层隔离定位，先回滚到已知良好版本
note_en: Autoscaling brought up EC2 instances that either died immediately or booted without ever joining the Kubernetes cluster. The method was strict layer isolation: ASG activity and launch template first, then user-data and cloud-init results, then the kubeadm join path, then kubelet logs, because launch failure and join failure have entirely different owners. The operational rule it distilled: when capacity is impacted, restore it first by rolling back to a known-good launch template or AMI, and only then pursue root cause.
note_cn: 自动扩容拉起的 EC2 实例要么立即被终止，要么启动后始终无法加入 Kubernetes 集群。方法是严格分层隔离：先看 ASG 活动记录与 launch template，再查 user-data 与 cloud-init 结果，然后是 kubeadm join 路径，最后是 kubelet 日志，因为启动失败与加入失败的归属完全不同。沉淀的操作规则：容量受损时先回滚到已知良好的 launch template 或 AMI 恢复容量，然后再追根因。

# INDEX_TABLE

## EN

| Failure domain | Core problem | Cases | Representative signals |
|---|---|:---:|---|
| Routing / DNS / ingress edge path | Which hop along the path is the request dying at | 2 | connection refused, timeout, 502/503, LB health-check failures, DNS resolves but traffic broken |
| Scheduling / capacity / node pressure | Why the workload cannot be placed, or the node is no longer fit to carry it | 4 | Pending, FailedScheduling, insufficient CPU/memory, DiskPressure, Evicted, OOMKilled |
| Stateful systems under pressure | Alive, but no longer serving stably | 6 | consumer lag, merge CPU high, recovery failures, connect failures with a healthy process, MEMORY_LIMIT_EXCEEDED |
| Observability / false signals | Whether what the alert sees equals what users experience | 3 | P99 high but logs clean, latency metric high while upstream is normal, alert firing after impact is gone |
| Identity / access control | Whose identity is the request under, and which layer rejects it (runbooks only, no distilled case yet) | 0 | AccessDenied, 403, works in dev but not in prod |
| Change management / post-change regression | How to make large changes without breaking production | 3 | post-upgrade regression, version skew, component change breaking downstream, schema change |
| Overload / large-tenant QPS spike | Demand saturating one layer's rated capacity | 3 | single-tenant QPS spike, per-partition throughput ceiling, connection/queue saturation |

## CN

| 失败域 | 核心问题 | case 数 | 代表性信号 |
|---|---|:---:|---|
| 路由 / DNS / 入口链路 | 请求到底死在哪一跳 | 2 | connection refused、timeout、502/503、LB 健康检查失败、DNS 可解析但流量不通 |
| 调度 / 容量 / 节点压力 | workload 为什么放不上去，或节点为什么不再适合承载 | 4 | Pending、FailedScheduling、CPU/内存不足、DiskPressure、Evicted、OOMKilled |
| 有状态系统承压 | 还活着，但不再稳定服务 | 6 | consumer lag、merge CPU 高、恢复失败、进程健康但连接失败、MEMORY_LIMIT_EXCEEDED |
| 可观测性 / 假信号 | 告警看到的是否等于用户体验到的 | 3 | P99 高但日志干净、延迟指标高但上游正常、影响消失后告警仍在触发 |
| 身份 / 权限 / 访问控制 | 请求以谁的身份发起，在哪一层被拒（目前仅有 runbook，尚无蒸馏 case） | 0 | AccessDenied、403、dev 可用 prod 不可用 |
| 变更管理 / 变更后回归 | 如何在不打穿生产的前提下做大变更 | 3 | 升级后回归、版本偏差、组件变更打断下游、schema 变更 |
| 过载 / 大租户 QPS 尖峰 | 需求打满了某一层的额定容量 | 3 | 单租户 QPS 尖峰、每分区吞吐天花板、连接数或队列饱和 |

# STATS

## Library totals
stats_en: 21 documented investigations (20+ of them production P1/P2) · 16 runbooks · 15 fast-triage cards · 7 debug-trees · 4 root-cause patterns · 3 checklists
stats_cn: 21 份完整调查记录（其中 20+ 为生产 P1/P2）· 16 份 runbook · 15 张快速分诊卡 · 7 棵 debug-tree · 4 个根因模式 · 3 份 checklist

## Per-domain stat lines
> Investigation counts are per-domain (one investigation can touch multiple domains); runbook / card / tree / pattern / checklist counts are library-wide totals.
> investigation 计数按域统计（一次调查可触及多个域）；runbook、分诊卡、debug-tree、模式、checklist 为全库总数。

- incident: `14 investigations · 16 runbooks · 7 debug-trees`
- data: `8 investigations · 15 fast-triage cards · 4 root-cause patterns`
- obs: `6 investigations · 7 debug-trees · 4 root-cause patterns`
- infra: `6 investigations · 16 runbooks · 3 checklists`
- dist: `5 investigations · 15 fast-triage cards · 7 debug-trees`
- release: `5 investigations · 16 runbooks · 3 checklists`
- platform: `2 investigations · 16 runbooks`

(security: 0 · influence: 0 — no touching investigations; not displayed on the site / 无触及调查，站点不展示)

## Explanation
explain_en: Every record in this library is a real production incident handled on call, distilled into four sections: symptom, localization, fix, and lesson. The causal evidence chain is preserved; all customer, cluster, and internal service identifiers are removed.
explain_cn: 库中每条记录都是 on-call 处理过的真实生产事故，蒸馏成症状、定位、修复、教训四段。因果证据链完整保留；全部客户、集群与内部服务标识已去除。

# SOURCES
- agents/sre_oncall_triage_skill/knowledge/cases/case-clickhouse-ttl-merge-cpu-saturation.md
- agents/sre_oncall_triage_skill/knowledge/cases/case-ingress-nginx-admission-webhook-cabundle-stale.md
- agents/sre_oncall_triage_skill/knowledge/cases/case-debezium-schema-change-snapshot-sign-null.md
- agents/sre_oncall_triage_skill/knowledge/cases/case-kafka-mirrormaker-lag-<tenant>-partition-bottleneck.md
- agents/sre_oncall_triage_skill/knowledge/cases/case-starrocks-fe-crashloop-bdb-ip-binding.md
- agents/sre_oncall_triage_skill/knowledge/cases/case-kafka-kraft-livenessprobe-restart-loop.md
- agents/sre_oncall_triage_skill/knowledge/cases/case-monitoring-alert-delay-histogram-skew.md
- agents/sre_oncall_triage_skill/knowledge/cases/case-aws-asg-scale-out-node-join-failure.md
- agents/sre_oncall_triage_skill/knowledge/references/reference-case-taxonomy.md
