# SRE Oncall Triage Agent — 优化执行计划

**触发**: task.txt（2026-04-18）
**主模型**: opus（规划 / 决策 / 综合）
**子模型**: sonnet（fetch / summary / 分类判定）
**范围**: agent 目录下 facets / knowledge / skills / tools + 顶层 md，共 **160 files**（147 md + 13 code）

---

## 用户诉求（改写）

1. 全局注册只看到一个 markdown — 担心 agent 调不到 → **已确认**：`~/.claude/agents/sre-oncall-triage.md` 是 `CLAUDE.md` 的 absolute-path symlink，能用。
2. tools 不应直接裸露给 agent — 应该在更上层包一层 skill（比如 `loki_fetch.py` 需要一个 `/toolog` skill，VM CLI 也要）。
3. `tmp/sla.json` 是最核心 dashboard — 含 SLI query、client 列表、变量，需要抽成 domain knowledge。
4. 目录里有些内容是 general knowledge（LLM 自带），不是 domain-specific — 需要 prune。
5. over-engineered，需要精简。
6. 需要一套流程：**并行 audit → 合并 → 决策 → 执行 → 收敛验证 → 跑 case 验证**。
7. 必须保证 **每个 md 都被看过**，用 `.py` 收敛脚本做硬门。
8. 过程观察写进 `records/`，可以循环迭代。

---

## 七阶段流程

### Phase 0 — 基础设施（已在做）
- `records/inventory.json` — 全量文件清单（160 条）
- `records/00_plan.md` — 本文件
- `records/converge.py` — 收敛校验脚本 skeleton

### Phase 1 — 并行 audit（sonnet subagents, background=true）
把 147 个 md 拆 **6 个 bucket**（按目录切分，size 大致均衡）：
1. facets/ + agent 顶层 md（~12）
2. knowledge/cases/（~30）
3. knowledge/runbooks/（~21）
4. knowledge/references/（~27）
5. knowledge/cards/ + patterns/ + debug-trees/ + checklists/（~30）
6. skills/ + tools/ md + 其他（~15）

每个 bucket 启一个 `Agent(subagent_type=Explore, model=sonnet, run_in_background=true)`，prompt 要求对每个 md 输出一行 JSON：
```json
{"path": "...", "kind": "case|runbook|card|pattern|debug-tree|reference|facet|skill|tool|index|other",
 "one_line": "做什么，一句话",
 "dv_specific_score": 0-10,     // 0=通用，10=DataVisor 公司强相关
 "recommendation": "keep|prune|merge|move|rewrite",
 "merge_target": "...",          // 如果 merge
 "notes": "为什么这么判，重点信号"}
```

Bucket 输出到 `records/audit/bucket-<N>.jsonl`。6 个 bucket 并行，walltime 估 2-5 min。

### Phase 2 — 汇总 + refactor plan（opus, 主 agent）
- `records/audit/aggregated.jsonl` = concat 所有 bucket
- 主 agent 读全量 → 产出 `records/02_refactor_plan.md`：
  - **Prune list**：dv_specific_score ≤ 3 且 recommendation=prune 的 md
  - **Merge groups**：同主题多文件（e.g. 多个 yugabyte cards）→ 合并目标
  - **Move list**：位置不对的文件
  - **Tool-skill 缺口**：需要新建的 skill wrapper
  - **SLA 抽取**：从 sla.json 要提炼的 dashboard variables / client / SLO / query
  - **CLAUDE.md 精简项**：agent 入口冗余段落

### Phase 3 — SLA dashboard 抽取（sonnet）
- sonnet subagent 解析 `tmp/sla.json` → `knowledge/references/reference-sla-dashboard.md`
- 结构化抽取：
  - dashboard variables（cluster, client, PromDs, tier, ...）
  - SLI queries（E2E availability、P99 latency、error rate）
  - client 列表 + 分层
  - 对应 panel 指向的 job/namespace 约定
- 这块是纯 domain knowledge，能节省 agent 以后每次查的时间。

### Phase 4 — tool→skill wrapper
- `skills/sre-vm-query/SKILL.md`（新建）：wrap `tools/vm_lookup.py` + VM MCP 查询 best-practice（label filter / step / 时间窗 / 避免高基数 regex）
- 可选：`skills/sre-slack-alert-intake/SKILL.md` — wrap `slack_link.py` + Slack MCP 的标准取消息流程
- `loki_fetch` 已有 `/dv_loki_fetch` 全局 skill — 只做一致性核对，不新建

**关键**：skill 是对 agent 的"使用说明书"（when to use, how to query, 常见 pitfalls），不是 CLI 实现。

### Phase 5 — 执行 refactor
按 02_refactor_plan.md 执行：
- `git rm` prune 文件
- merge 文件内容
- `git mv` move 文件
- 更新 `knowledge/README.md`、`facets/index.md`、`knowledge/agent-routing-table.md`
- 精简 `CLAUDE.md`（移除冗余段落、更准确反映当前 workflow）

每个大动作一次 checkpoint（写入 `records/checkpoints/<N>_<label>.md`），方便回滚。

### Phase 6 — 收敛（converge.py）
`converge.py` 读 inventory + audit aggregated + 当前 FS → 对每个 inventoried file 输出状态：

| 列 | 含义 |
|---|---|
| path | 原始路径 |
| audited | 是否在 audit 结果里 |
| recommendation | keep / prune / merge / move / rewrite |
| action_taken | still_present / deleted / merged_into:X / moved_to:Y |
| matches | 1 = recommendation 和 action 一致；0 = 不一致 |

- exit 0 = 全部 audited + action_taken 一致
- exit 1 = 有 gap → 报具体文件

这是**硬门**：脚本必须 0 才算完成。

### Phase 7 — cases 验证
从 `/Users/rshao/work/work-harness/cases/` 选 3 个不同类型：
- `2026-04-16_1223_useast1-prod-transient-p99-spike.md` — P99 spike，测 fast path
- `2026-03-31_0000_clickhouse-cpu-oncall-investigation.md` — 资源/CPU，测 slow path
- `2026-04-16_1500_flink-batch-cabundle-failure.md` — 变更管理 / deploy 类，测 routing

对每个 case：
1. 提取 raw alert 段（或构造告警）
2. `Agent(subagent_type=general-purpose, ...)` fork 一个 session 跑 SRE agent（既可 quick-check 又可 full triage）
3. 对比输出与原 case 结论（不要求一致，要求方向合理）
4. `verify.py` 必须 PASS / WARN
5. 记录到 `records/07_case_validation.md`

---

## Checkpoint 设计

每个 phase 结束 / 每个大 refactor 动作 commit 一次：
- `records/checkpoints/phase<N>_<label>.md` — 改了什么 + 为什么 + 下一步
- git commit（用户确认后执行）

失败/中断 → 从最后一个 checkpoint 恢复。`converge.py` 既是门禁也是恢复点：它告诉你还有多少 gap。

---

## 不会做的事（避免 over-engineering 反复）

- **不新增**"quality 维度评分系统"、"multi-dimension audit framework"这种元结构
- **不重写**已经 stable 的 knowledge files（只 prune / merge / move）
- **不拆分**现有 skills（已经 8 个 skill，够了）
- **不搞**新的 hook 类型（3 层防线 + 审计已成熟）
- **不做**UI 层的事情

---

## 执行模式

1. 当前文档就是 plan，等你看过后我开 Phase 1（6 个并行 sonnet subagent）
2. Phase 1 起来后立刻做 Phase 3（SLA 抽取，sonnet）和 Phase 4（tool→skill，我自己写）
3. Phase 2 等 Phase 1 全部返回 → 汇总决策
4. Phase 5 + 6 串行
5. Phase 7 最后 fork 新 agent 验证

并行点：Phase 1（6 个 bucket 并发）+ Phase 3（SLA 抽取与 Phase 1 同时）+ Phase 4（skill 编写与 Phase 1-3 同时）。

---

## 确认项

请确认：
1. 7 个 phase 的切分是否合理？
2. Phase 1 的 6-bucket 拆分（见上）OK 吗？
3. Phase 4 要不要建 `slack-alert-intake` skill？现在 Slack 链接流程已在 `facets/slack_alert_intake.md` 里（可能够用，不一定要升成 skill）
4. Phase 7 用的 3 个 case 代表性够吗？还是你指定其他 case？
5. 是否允许我每个 phase 结束后直接 commit？（不推送）
