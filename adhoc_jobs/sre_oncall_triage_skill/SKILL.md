---
name: sre-oncall-triage
description: SRE oncall triage skill. Slack 告警链接或原始文本 → 自主调查 → 生成带中文注释的操作命令方案。Read-only 调查；所有 kubectl/helm/aws 触线上命令必须 user approve 后才执行。
allowed-tools: Read, Write, Edit, Bash, Grep, Glob, Skill, Agent
---

# SRE Oncall Triage — Skill Entry (MAP)

> Oncall 告警进来时**先读本文件**。3 张路由表定位 sub-skill 或外部 runbook，按需加载，一次 ≤ 5 chunk。
> 详细工作流、调查方法、case 库都在子文件里，本入口只做导航 + 护栏。

## 0. Hard Constraints — Global（任何模式都适用）

这 6 条护栏对**所有**调用路径生效（triage workflow、standalone `/sre-vm-query`、`/dv_loki_fetch`）：

- **🛑 Mutation Approval Gate**：任何 `kubectl apply/create/delete/patch/scale/drain/exec`、`helm install/upgrade/uninstall`、`aws ... create/modify/delete/terminate`、SQL `DROP/UPDATE/DELETE/ALTER` 命令一律**只生成不执行**。展示给用户 + 中文意图说明（`# INTENT:` 一行）+ 等待显式 "approve" / "执行" / "go" 后才用 Bash 跑。无 approval 直接跑 = 严重违规。
- **🟢 Read-only 自由区**：MCP 查询（Grafana / VictoriaMetrics / Loki / Slack 读）、`kubectl get/describe/logs`、`aws ... describe/list/get`、`SELECT` SQL 不需要 approval，可直接执行。**但见下条 Subagent Isolation——主 agent 直调 MCP 数据查询是受限的。**
- **🛡️ Subagent Isolation**：主 agent **禁止直调** `mcp__victoriametrics__query` / `query_range` / `series`、`mcp__grafana__query_*` / `query_loki_*` / `get_dashboard_*`、以及任何返回 raw 时序 / log 行的工具。这些一律 `Agent(subagent_type="general-purpose" 或 sre-vm-query, run_in_background=false)` 派 sonnet subagent，subagent 返回 **≤500 token 结构化摘要**（max value + ts、是否 step jump、与 baseline ratio、关键日志 ≤3 行）。例外（主 agent 可直调）：`mcp__victoriametrics__labels` / `label_values` / `metrics` / `metrics_metadata`、`mcp__grafana__list_*` / `search_*` —— 这些是元数据，返回小。**理由**：context = LLM 的 RAM；一次 raw 查询 30K token 占用直接把主 agent 在 phase B/C 的判断力榨干。
- **Alias-first commands**：生成的 kubectl 命令必须用 cluster alias（`kwestproda`, `keastproda` …），禁止裸 `kubectl` 或 `--context=...`。映射见 `knowledge/references/reference-clusters.md`。
- **Evidence-backed**：所有结论必须有 MCP 查询结果支撑；缺 timestamp / cluster / (namespace|service) 时停下问用户，不猜测填充。
- **Slack response 措辞**："consistent with" / "evidence suggests" — 不用 "definitely" / "clearly"。不确定时说 "unknown"。

### Triage-Specific Constraints（仅 full triage workflow 适用）

> 仅当进入 `/sre-oncall-init` workflow 时生效。Standalone 数据查询 skill **不受这些约束**。
>
> - **Phase Lock + File Access Boundary**：`plan.md` 的 `phase: A/B/C` 字段限制可读资源（debug-trees vs cases vs runbook 命令体）。详见 `skills/sre-oncall-init/phase_lock.md`（按需加载）。违反 = Iron Law 3（见 `sre-oncall-acceptance-criteria`）。
> - **Output to files**：triage 分析写入 `tmp/oncall/<YYYYMMDD_HHMM>_<label>/report.md`，对话只输出摘要 + 路径。Standalone 查询输出回对话即可。

## 1. Mode Selection（入口必做）

| 用户输入特征 | 模式 | 动作 |
|---|---|---|
| 含 `quick` / `快查` / `先看一眼` / `--quick` | **Quick Check** | 直接 `/sre-oncall-quick-check`，fan-out 事实收集 → 5-section summary → 问继续/升级/止步。不持久化。 |
| 含 `full` / `完整` / `正式`，或默认 | **Full Triage** | Fast/Slow fork + Layered Architecture，持久化到 `tmp/oncall/`。 |
| 模式不明 | 主动问 | "要 quick check（~60s）还是 full triage（根因 + 命令方案）？" |

## 2. Workflow Architecture

```
Alert → 提最小信号（alertname, cluster, client, tags）
  │
  ├─ FAST (sonnet subagent, background)
  │   └─ 搜 knowledge/{cases,cards,patterns}/ → 历史 case 匹配 → 写入 report Historical Pattern Matches
  │
  └─ SLOW (main)
      ├─ Layer 0: /sre-oncall-init       — mkdir + skeleton + 信号 + 路由 + missing-field gate
      ├─ Layer 1: 类型特定调查（见表 3）
      └─ Layer 2: query-safety + acceptance-criteria（auto-injected）
```

**进门即 fork**：fast path 与 slow path 同时启动，fast 结果合并到 report 不替代 slow。

## 3. 诊断路由（Alert Type → Layer 1 chunk）

| Alert 类型 | Layer 1 Skill |
|---|---|
| P99/P95 latency spike | `/workflow-oncall-spike` |
| False signal（P99 飙但 error 正常） | `knowledge/debug-trees/debug-tree-false-p99-histogram-skew.md` |
| Connection refused / timeout | debug tree fallback（`knowledge/debug-trees/`） |
| Kafka consumer lag | debug tree fallback |
| OOMKilled / CrashLoop | debug tree fallback |
| Error rate spike (5xx) | service-specific（查 `knowledge/cases/`） |

未命中 → 走 debug tree fallback + 让 fast path subagent 在 `knowledge/cases/` / `knowledge/cards/` 找历史 case。

## 4. 操作路由（Task → 外部 runbook）

调查结论指向**确定性操作**时，按此表导航到 `~/work/work-harness/code_repos/historial_operations/`。记住：**展示命令 → 等 approve → 才执行**（见 §0）。

| 关键词 / 症状 | 外部 runbook |
|---|---|
| ClickHouse 内存 / merge OOM / system log 僵尸表 | `clickhouse_system_log_cleanup/` |
| CH pod 资源调整 / 节点扩容 / ASG | `clickhouse_node_resize/` |
| CH 升级 / 回滚 / 数据拷贝 | `upgrade_rollback_clickhouse/` |
| CH 数据回填 / 快照提取 | `clickhouse_data_extract/` |
| RBAC / cluster-developer / Kyverno | `cluster-developer/` |
| ybprod ns exec/secrets 权限 | `ybprod_cluster_developer_rbac/` |
| 跨 cluster MySQL 访问 | `cross_cluster_mysql_via_nginx_tcp/` |
| Helm chart push 到 Harbor | `push_helm_to_harbor/` |
| CronJob _SUCCESS 标记 + Slack | `create_cronjob_upload_success_file/` |
| S3 上传 / 下载 / jumpserver 拷贝 | `upload_to_s3/`, `download_from_s3/`, `copy_data_in_jumpserver/` |
| 磁盘清理 / docker prune | `clear_space/` |
| Alert 路由 / OpsGenie / 噪声治理 | `alert_gov/` |
| AWS EC2 / ASG / 网络发现 | `scripts/{aws_helpers.sh, discover_aws_arch.sh}` |
| kubeconfig 多 region / PEM | `kubeconfig/`（**敏感，只读引用，不复制内容**） |

**排除**：`k8s_upgrade/`（不进路由表）。

## 5. 关键词路由（Knowledge 内部）

| Keyword | Chunks |
|---|---|
| histogram skew / quantile 抖 | `knowledge/debug-trees/debug-tree-false-p99-histogram-skew.md` + `bestpractice_sre_reliability_models.md` |
| consumer lag | `knowledge/cases/` 搜 lag + Layer 1 debug tree |
| MetricsQL / PromQL safety | `/sre-vm-query` |
| LogQL / Loki | `/dv_loki_fetch` |
| cluster alias / DV cluster naming | `knowledge/references/reference-clusters.md` |
| AWS CLI helpers (`awsf`, `awsssh`) | `knowledge/references/reference-aws-cli.md` |

## 6. 文件清单（按需 Read）

**自动注入（始终在 context）**：仅 `/sre-oncall-init` —— 它是 Layer 0 入口，但本身已瘦身，详细 phase lock + skeleton 模板挪到 sibling 文件按需读。

**按需加载子 skill**（用 `Skill` 工具显式调用）：

| Skill | When |
|---|---|
| `/sre-oncall-quick-check` | Quick mode 触发 |
| `/workflow-oncall-spike` | P99/P95 spike 路由后 |
| `/sre-oncall-acceptance-criteria` | 写 report.md / verification 前（Iron Laws 细则） |
| `/sre-oncall-query-safety` | 主 agent 自己跑 MCP 元数据查询时（vm-query / loki-fetch 已 self-contained，subagent 内部用不到） |
| `/sre-oncall-output-format` | 写 report.md 前 |
| `/sre-vm-query` | 任何 PromQL/MetricsQL 查询（含 safety，**可 standalone**） |
| `/dv_loki_fetch` | 任何 LogQL 查询（**可 standalone**） |
| `/sre-oncall-data-tools` | Data tools 总览参考 |
| `/sre-oncall-compound-learning` | 调查结束沉淀知识 |

**按需 Read**（用 `Read` 工具显式打开）：
- `skills/sre-oncall-init/phase_lock.md` — plan.md 写入 `phase: A` 后立即读，phase 切换时复读
- `skills/sre-oncall-init/skeletons.md` — Step 2-4 写 plan/log/report 那一刻读
- `facets/signal_extraction.md` — 每次 triage
- `facets/slack_alert_intake.md` — 输入是 Slack link 时
- `knowledge/agent-routing-table.md` — 路由细节
- `knowledge/README.md` — case matching

## 7. Verification

```bash
python3 tools/agent_ops/verify.py /Users/rshao/work/work-harness/tmp/oncall/<YYYYMMDD_HHMM>_<label>/report.md
```

- PASS (0) → append `## Verification: PASS`
- WARN (1) → append `## Verification: WARN` + details
- FAIL (2) → 修复重跑直到 PASS/WARN

验证后问："要沉淀到知识库吗？" → `/sre-oncall-compound-learning`。

## 8. Setup（首次或 skill 更新后）

```bash
bash agents/sre_oncall_triage_skill/tools/agent_ops/setup.sh
```

## 9. Model Tier Strategy & Subagent Isolation

主流程继承上层 model（通常 opus），负责**路由 / 综合分析 / 命令生成 / 决策**。**所有原始数据获取一律 delegate 给 sonnet subagent**（与 §0 Subagent Isolation 联动）：

| 任务 | Agent 类型 | 主 agent 直调？ | Subagent 返回格式 |
|---|---|---|---|
| Slack 消息读取 | sonnet subagent | ❌ | 5 行内 alert 摘要 + raw_labels |
| VM/Loki **raw query**（query/query_range/series） | sonnet subagent | ❌ | ≤500 token: max/ts/baseline_ratio/step_jump |
| VM metadata（labels/label_values/metrics） | 主 agent 可直调 | ✅ | （结果本身小） |
| `knowledge/` 搜 case/pattern/runbook | sonnet subagent | ❌ | 1-2 个匹配 filename + summary |
| 信号提取 / log 关键行整理 | sonnet subagent | ❌ | YAML signals |
| 路由表 / debug tree 路径决策 | 主 agent | ✅ | （决策本身） |
| Hypothesis 评估 / 命令生成 | 主 agent | ✅ | report.md sections |

**Subagent prompt 模板**（保证 ≤500 token 返回）：

```
Agent(subagent_type="general-purpose", run_in_background=false, prompt="
  查 {cluster}/{service} P99 latency {time_window}。
  **只返回 4 个数**：(1) max value + ts，(2) 是否 step jump（前后窗口 >2x），
  (3) 与前 1 小时 baseline 对比 ratio，(4) 关键 outlier ts ≤3 个。
  禁止返回原始时序数据。
")
```

**反模式**：主 agent 自己 `mcp__victoriametrics__query_range` 拿回 200 个数据点 → 主 context 被淹没 → phase B 决策时已经 token-exhausted。

---

## Acceptance Criteria（终态，详见 `/sre-oncall-acceptance-criteria`）

1. report.md 含全部 required sections（Plan, Scope, Slack Response, Internal Notes, Extracted Signals, Links, Investigation Log, 操作命令方案）
2. `verify.py` exit 0 或 1
3. 每个 conclusion 有 evidence chain
4. Slack response 无 assertion 违规
5. 所有 MCP 查询入 investigation log
6. **Phase 1 gate**：plan 在首次 MCP 查询前已写入文件
7. **Missing field gate**：timestamp / cluster / (namespace|service) 缺失停下问
8. **Time precision**：event_ts ± 3min 精确窗口
9. **🛑 Mutation gate**（本 skill 新增）：所有 mutating 命令零自动执行，approval 痕迹必须出现在 investigation log
