# 过程观察（执行中记录）

## 2026-04-18 — Phase 1 dispatch

### Explore subagent 是只读的
- Dispatch 了 6 个 `Agent(subagent_type=Explore, model=sonnet)` 做 audit
- Explore 没有 Write 工具 → subagent 无法直接写 `records/audit/bucket-N.jsonl`
- 它们会把 JSONL 内容回传到 message 里，我（主 agent）从消息里 Write 落盘
- **流程可优化**：下次 batch audit 这种需要写文件的任务，用 `subagent_type=general-purpose` 而不是 Explore
- 但这次事后落盘也 OK，读-only 反而避免了 subagent 写坏内容的风险

### Bucket 1 初步发现（facets + 顶层 md）
- 10 个 facet 里 **6 个标 prune**（通用 K8s/nginx 原则，LLM 自带）
- 只有 3 个 facet 是 DV 特定的：`index.md`、`slack_alert_intake.md`、`traffic_interface.md`
- `CLAUDE.md` / `signal_extraction.md` 需要 rewrite（CLAUDE.md 臃肿，signal_extraction 太通用需补 DV alert 字段）
- `todo.md` 应该 prune（dev-only，不该进 agent 运行时 context）
- `README.md` 需要精简：四原语/GCORF 理论删掉，架构图保留
- 用户的直觉对了：**facets 里确实堆了太多通用 knowledge**

### Bucket 1 的 recommendation 分布
- keep: 4（index, slack_alert_intake, traffic_interface, CLAUDE.md）
- rewrite: 3（signal_extraction, state_database, README.md）
- prune: 6
- merge: 0
- move: 0

## 2026-04-18 — Phase 5 Batch A (prune 16 files)

### Audit 判定准确性问题
- Bucket 2 subagent 说 `case-onefinance-qps-spike-joint-mitigation.md` 和 `case-large-tenant-qps-spike-joint-mitigation.md` "完全相同"
- 实际 `diff -q` 显示两者**不同**：onefinance.md 96 行，large-tenant.md 115 行；incident 版本也不同
- 内容差异：large-tenant 加了 stability window + closeout checklist（更成熟的生产版本）
- 决策：仍 prune onefinance（被 large-tenant 超集了），但记一笔：**subagent 对 "内容相似" 的判断 ≠ 字节相同**
- **教训**：未来 audit prompt 里 "完全相同" 要求 subagent 真跑 diff，否则说 "重叠度高" 或 "被 X 超集"

### Gitignore 复杂度
- `knowledge/references/` 整个目录 gitignored（`*` + `!README.md`）→ references 删除不会进 git history
- Case 文件有 pattern gitignore：`*-tenant-qps-spike*.md`、`*-qps-spike-joint-mitigation.md` 等
- `.incident.md` 后缀通常不匹配那些 `.md` 结尾 pattern → 仍被 tracked
- 结果：Phase 5 的删除里，**约一半不会出现在 git log** — 但对 agent 行为的影响是真实的
- 追踪办法：Phase 6 converge.py 依赖 filesystem 状态，不依赖 git

## 2026-04-18 — Batch B partial
- `card-yugabyte-debug-ports-commands.md` → ports table + 3 minimal commands merged into `card-yugabyte-metrics-fast-checks.md`，原 card 已删
- `runbook-database-incident-troubleshooting.md` → downgrade 到 keep（多 DB 通用入口，和 CH-specific 不该合并）
- `runbook-k8s-ingress-setup-runbook.md` → downgrade 到 prune（全通用 placeholder，DV 用 dns-url 那套 pattern）
- 13 incident→main case merge 完成（10 absorbed + 3 appended "## Incident Overview"）
- `reference-knowledge-base-index.md` → deferred（文件过大 25K tokens，不值本 session 读入；knowledge/README.md 已经是 canonical index）
- YB 三合一（bootstrapping + debug-process + incident-recovery）— 后台 subagent 执行中
