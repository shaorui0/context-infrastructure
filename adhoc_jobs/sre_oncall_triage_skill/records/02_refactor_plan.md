# Refactor Plan — Phase 2 产出

**Based on**: `records/audit/aggregated.jsonl`（147 md files audited，100% converge PASS）
**生成**: 2026-04-18 Phase 2，opus 主 agent 综合

---

## 0. 执行摘要

| 类别 | 数量 | 占比 |
|---|---|---|
| keep（保留原样 / 轻微更新） | 110 | 75% |
| rewrite（精简、删通用） | 14 | 10% |
| merge（合入其他文件） | 20 | 14% |
| prune（直接删） | 16 | 11% |

净结果：~147 md → **~110 md + 1 个新 reference** (SLA dashboard) + 1 个新 skill (vm-query)。
约 **~36 个文件减少**（20 merge + 16 prune），另有 14 个 rewrite。

Score 分布（md only，147）:
- 0-1: 4 / 2-3: 22 / 4-5: 31 / 6-7: 37 / 8-9: 38 / 10: 15

**用户的直觉成立**：有 **26 个 md（0-3 分）** 本质上是 general knowledge / dev-scratch，应当削减。

---

## 1. Prune List (16 files)

直接 `git rm`。理由都在 `records/audit/aggregated.jsonl`。

| # | 路径 | score | 理由 |
|---|---|---:|---|
| 1 | `facets/compute_pods.md` | 1 | 纯通用 K8s pod 检查 |
| 2 | `facets/logs_evidence.md` | 1 | 纯通用日志调查思路 |
| 3 | `knowledge/runbooks/runbook-nginx-debugging-runbook.md` | 1 | 完全通用的 nginx 手册 |
| 4 | `knowledge/references/reference-iac-first-principles.md` | 1 | IaC 哲学文章，零 DV 内容 |
| 5 | `facets/alert_quality.md` | 2 | 通用误报/抖动原则 |
| 6 | `facets/client_mapping.md` | 2 | 通用 name matching 原则，无 DV 客户列表 |
| 7 | `knowledge/runbooks/runbook-aws-iam-access-denied-troubleshooting.md` | 2 | 通用 AWS IAM 4-layer 分析 |
| 8 | `knowledge/references/reference-dns-configuration-reference.md` | 2 | 通用 CoreDNS/Route53 文档 |
| 9 | `knowledge/README.template.md` | 2 | 早期 scaffolding，README.md 已成熟 |
| 10 | `facets/sla_pipeline.md` | 3 | 提到 batch/realtime 但无 DV pipeline 名 |
| 11 | `todo.md`（agent 根目录） | 3 | dev-scratch，运行时无价值 |
| 12 | `knowledge/runbooks/runbook-k8s-resource-exhaustion.md` | 3 | 全通用（crictl/EBS resize） |
| 13 | `knowledge/runbooks/runbook-mysql-backup-restore-runbook.md` | 3 | 通用 mysqldump+kubectl |
| 14 | `tools/knowledge.md` | 3 | 全注释 curl，被 MCP 替代 |
| 15 | `knowledge/cases/case-onefinance-qps-spike-joint-mitigation.incident.md` | 8 | 与 large-tenant 完全重复 |
| 16 | `knowledge/cases/case-onefinance-qps-spike-joint-mitigation.md` | 8 | 与 large-tenant 完全重复 |

**验证项（Phase 5 做）**：item 15/16（onefinance = large-tenant 重复）需要 `diff` 确认真的是字符级相同；如果不是，downgrade 为 merge。

---

## 2. Merge Groups (20 files → 6 targets)

### 2.1 Case `.incident.md` 合并入主 `.md`（13 pairs）

`.incident.md` 是主 case 的格式化摘要副本。策略：把 incident 内容作为 **"## Incident Overview"** section 并入主 `.md`，然后 `git rm` incident 文件。

合并 13 个 incident 文件到对应主 case：
- `case-aws-asg-scale-out-node-join-failure`
- `case-clickhouse-connection-refused-troubleshooting`
- `case-clickhouse-copydata-recovery-failure`
- `case-clickhouse-pod-pending-scheduling-resource-nodegroup`
- `case-fp-latency-waiting-latency-prod-qps-spike`
- `case-k8s-pod-evicted-diskpressure-asg-fast-mitigation`
- `case-kafka-kraft-livenessprobe-restart-loop`
- `case-kafka-lag-issues`
- `case-large-tenant-qps-spike-joint-mitigation`
- `case-monitoring-alert-delay-histogram-skew`
- `case-mysql-connect-timeout-fp-dns-node`
- `case-qa-deployment-failure-disk-cleanup`
- `case-spark-job-pending-not-running`

**注意**：如果主 `.md` 内容比 `.incident.md` 更全，**不要覆盖**，只把 incident 里独有的 incident-date / client / alertname / resolution-summary 字段 append 过去。

### 2.2 DB incident → ClickHouse disk space runbook
- `runbook-database-incident-troubleshooting.md` → `runbook-clickhouse-disk-space-exhaustion.md`（作为入口 checklist）

### 2.3 K8s ingress setup → DNS URL creation
- `runbook-k8s-ingress-setup-runbook.md` → `runbook-dns-url-creation-runbook.md`（合并为 ingress+DNS 创建一体化 runbook）

### 2.4 YB runbooks 三合一 ★ 冲突已解决 ★

Audit 里有循环引用（bootstrapping ↔ debug-process）。决策：**全部合入 `runbook-yugabyte-connection-bootstrapping.md`**（最完整），然后 `git mv` 重命名为 `runbook-yugabyte-oncall.md`（反映扩展后的覆盖面）。

- `runbook-yugabyte-debug-process.md`（35 行端口笔记）→ `runbook-yugabyte-oncall.md` 的 "## Common Ports" section
- `runbook-yugabyte-incident-recovery-steps.md`（生产恢复序列）→ `runbook-yugabyte-oncall.md` 的 "## Incident Recovery" section
- `runbook-yugabyte-connection-bootstrapping.md` → rename → `runbook-yugabyte-oncall.md`（保留 "## Diagnosis" section）

### 2.5 YB debug-ports card → metrics-fast-checks card
- `card-yugabyte-debug-ports-commands.md` → `card-yugabyte-metrics-fast-checks.md` 的 "## Ports & Master UI" section

### 2.6 knowledge-base-index → README.md
- `reference-knowledge-base-index.md`（alert pattern table + 旧 blog 链接） → `knowledge/README.md`（alert pattern 表合入），旧 blog 链接如果 dead 直接去掉

---

## 3. Rewrite Targets (14 files)

精简冗余 general knowledge，保留 DV 特有部分。按优先级从高到低：

### 3.1 高价值但被稀释（>400 行需砍）

| 文件 | 当前 | 目标 | 保留 |
|---|---|---|---|
| `knowledge/references/reference-request-routing-flow.md` | 688 行 | ~150 行 | TL;DR + flow diagram + DV-specific monitoring |
| `knowledge/references/reference-k8s-storage-affinity-scheduling.md` | 425 行 | ~50 行 | TL;DR + EBS AZ-mismatch diagnosis |
| `knowledge/references/reference-kubectl-describe-node-analysis.md` | ~400 行 | ~80 行 | TL;DR + DV-node example + diagnosis table |
| `README.md`（agent 根目录） | 300+ 行 | ~100 行 | 架构图 + 核心路由，删四原语/GCORF 理论推导 |

### 3.2 runbooks 需要削掉通用部分

| 文件 | 动作 |
|---|---|
| `runbook-clickhouse-disk-space-exhaustion.md` | 删通用 kubectl 基础；保留 DV namespace、联系人、告警阈值、PVC StorageClass |
| `runbook-jenkins-s3-permission-troubleshooting.md` | 删通用 AWS IAM 教学；保留 JENKINS_14635 案例、DV bucket 名、VPC/VPN 限制 |
| `runbook-jenkins-selenium-dns-failures.md` | 删通用 DNS 教学；保留 kwestproda、qaautotest namespace、admin-demo2.dv-api.com |
| `runbook-k8s-node-notready-runbook.md` | 删通用 K8s Node 故障诊断；保留 $CLUSTER_ALIAS、CLUSTER_EASTPRODA 案例、calico 特有步骤 |
| `runbook-site-outage-access-troubleshooting.md` | 删通用 AWS/K8s；保留 DV cluster alias 映射表、主要 Ingress 路径、常见 DV 服务 |

### 3.3 facets 补 DV context

| 文件 | 动作 |
|---|---|
| `facets/signal_extraction.md` | 补 DV alertname 枚举 + cluster 列表；删通用原则 |
| `facets/state_database.md` | 补 DV cluster 连接信息、dashboard URL、ClickHouse/MySQL 查询模板 |

### 3.4 references 补体 / 或者 prune

| 文件 | 动作 |
|---|---|
| `reference-mysql-multi-region-arch.md` | 当前 6 行太空。扩充 DV 实际 topology（cluster 名、replication setup），或 降级为 prune |

### 3.5 高价值但 hardcoded

| 文件 | 动作 |
|---|---|
| `knowledge/checklists/checklist-fp-latency-uswest-preprod-checklist.md` | 移除 hardcoded `/Users/rshao/...` 路径；templatize cluster/env；保留 phased checklist 结构 |

### 3.6 skill：CLI → skill reference 改写

| 文件 | 动作 |
|---|---|
| `skills/sre-oncall-data-tools/SKILL.md` | Section 2 (Loki) 改为 "调用 `/dv_loki_fetch` skill"；Section 3 (vm_lookup) 改为 "调用 `/sre-vm-query` skill"（新建，见 §4） |
| `skills/workflow-oncall-spike/SKILL.md` | 同上，内嵌的 `python3 ./tools/loki_fetch/loki_fetch.py` → 改为 `/dv_loki_fetch` skill 引用 |

---

## 4. New Content (2 files)

### 4.1 `knowledge/references/reference-sla-dashboard.md` ✅ 已完成
Phase 3 产出。抽取自 `tmp/sla.json`。含 5 variables、7 panel rows、~40 核心 SLI PromQL、SLA 阈值、label/metric 约定。

### 4.2 `skills/sre-vm-query/SKILL.md` ← Phase 4 待建
Wrap VM MCP (`mcp__victoriametrics__*`) + `tools/vm_lookup.py`，给 agent:
- 何时用 instant vs range
- label filter / step / window / regex 约束（query-safety 的 specialization）
- DV cluster label 约定（`kubernetes_cluster` vs `cluster` 哪个用）
- 常用 pod discovery pattern
- 常见失败模式 & retry

---

## 5. Index / Route Updates

### 5.1 `knowledge/README.md`
- 合入 `reference-knowledge-base-index.md` 的 alert pattern 表
- 清理已归档行（~~reference-db-issue-quick-reference.md~~ 等）
- 对应到 prune/merge 的文件路径失效 → 全部删除引用
- 新加 `reference-sla-dashboard.md` 条目

### 5.2 `knowledge/agent-routing-table.md`
- 新加 SLA-related alerts 的 cluster 映射条目（指向 reference-sla-dashboard）
- 如果 YB runbook 重命名，更新任何引用
- Phase 5 之后再重新校验

### 5.3 `facets/index.md`
- 去掉 5 个 prune 的 facet：alert_quality / client_mapping / compute_pods / logs_evidence / sla_pipeline
- 保留：index / slack_alert_intake / signal_extraction（rewritten） / state_database（rewritten） / traffic_interface

### 5.4 `tools/index.md`
- 去掉对 `tools/knowledge.md` 的引用
- 新增对 `/sre-vm-query` 和 `/dv_loki_fetch` skill 的指向
- `vm_lookup.py` 的 usage 段改为 "推荐通过 `/sre-vm-query` skill 调用，原始 CLI 仍可用作 fallback"

### 5.5 `CLAUDE.md`（agent 根 + skills manifest）
- 删除对 todo.md 的任何引用
- 精简 "Workflow" 段（已经臃肿）— 目标从 ~270 行 减到 ~150 行
- 如果 data-tools skill 里引用了 /sre-vm-query，确保 CLAUDE.md 的 File Manifest 表里也有

---

## 6. 执行顺序（Phase 5）

每个大块做完 → commit → 跑 converge.py → 再进下一块。

**建议批次**：
1. **Batch A — Prune（低风险）**：16 个 prune 文件一次性 `git rm`（用户的 `diff` 验证 onefinance 是否真的重复后执行）
2. **Batch B — Merge cases（13 incident → main）**：脚本化，可并发
3. **Batch C — Merge runbooks（db→ch / ingress→dns / YB 三合一 / YB ports card）**：人工（模型合并）
4. **Batch D — Rewrite（14 files）**：按优先级分 3 批，大的（>400 行）单独，small 批量。每批用 sonnet subagent 并行处理（Rewrite = 读原文 + 删 general + 返回新内容）
5. **Batch E — New skill + index updates**：最后做，因为要等 Batch A-D 稳定
6. **Batch F — `converge.py --phase 5`** 必须 exit 0

**并发点**：Batch D 的 14 个 rewrite 可以 3-4 个 sonnet subagent 并发。

---

## 7. Risks / Open Questions

| 风险 | 缓解 |
|---|---|
| onefinance 和 large-tenant 可能不是完全重复（只是相似） | Phase 5 开始前 `diff` 两对文件；若差异显著，改为 merge |
| YB runbook 三合一后单文件会 >500 行，臃肿？ | 允许有三个 section：Diagnosis / Ports / Recovery；500 行 acceptable for oncall runbook |
| Rewrite 把内容砍得太狠，丢掉 subtle DV signals | Rewrite subagent prompt 必须强调 "keep 所有 client 名 / cluster 名 / 内部 service 名 / 真实 IP / 历史 case 引用" |
| Verify.py 对某些旧 triage output 不再 PASS（因 routing-table 变化） | Phase 5 后跑 `slo.py --since 2026-04-01` 看历史 case 验证率是否倒退 |
| `/dv_loki_fetch` 全局 skill 失效时 workflow 断裂 | 保留 `tools/loki_fetch/README.md` 作为 fallback pointer；skill 也保留 CLI 写法作为 "debug mode" |

---

## 8. Phase 5 后的 converge 预期

运行 `python3 records/converge.py --phase 5` 必须 exit 0。预期输出：
```
CONVERGE @ phase=5
  inventoried: 160
  audited:     160/160
  matches:     160/160  (100%)
PASS
```

如果 matches < 160：需要 drill-down 到 `records/converge_report.jsonl`，找 `matches=false` 的行，补做。

---

## 9. 记录到 records/

本次 audit 过程中发现的观察已写到 `records/observations.md`：
- Explore subagent 只读限制 → 下次 batch audit 用 general-purpose
- 个别 subagent 返回只给 summary 不给 JSONL → prompt 需明确 "必须 include JSONL"
- YB merge 循环冲突 → 本 plan §2.4 解决
