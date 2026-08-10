# Final Checkpoint — Phase 7 Complete

**时间**: 2026-04-18
**Git log**: 4 commits from this session + pre-existing
**converge.py --phase 5**: EXIT 0 ✅
**verify.py on 3 cases**: all WARN (within acceptance) ✅

## 全部完成

| Phase | 状态 | 产出 |
|---|---|---|
| 0 infra | ✅ | inventory / converge.py / records/ |
| 1 audit | ✅ | 6 bucket × sonnet subagent，147 md 全覆盖 |
| 2 plan | ✅ | `records/02_refactor_plan.md` |
| 3 SLA | ✅ | `knowledge/references/reference-sla-dashboard.md`（gitignored, on disk） |
| 4 vm-query skill | ✅ | `skills/sre-vm-query/SKILL.md` + symlink `~/.claude/skills/` |
| 5 refactor | ✅ | A prune 16 + B merge 20 + D rewrite 14 + E index 5 |
| 6 converge | ✅ | 162/162 matches, EXIT 0 |
| 7 case validation | ✅ | 3/3 cases WARN (acceptance)，1 gap（ingress caBundle 无历史 case，应 compound-learning 沉淀） |

## 数字

- 启动时 md: 147
- 结束时 md: 147 - 17 prune - 17 merged (13 incident + 3 YB + 1 ports card) + 2 new (sla-dashboard, vm-query) + 1 new yb-oncall = **116 md**
- rewrite 压缩：`reference-*`（688→131 / 425→60 / 382→116）、`README.md`（511→120）、`CLAUDE.md`（236→184）、5 runbooks（907→349）等
- 净代码行减少 **~3000+ 行**（保守估计）

## 关键架构改动

1. **Tool→skill wrapper**：`/sre-vm-query`（新）+ `/dv_loki_fetch`（全局）取代裸 CLI 调用。`sre-oncall-data-tools` + `workflow-oncall-spike` 已改为 skill reference。
2. **Domain knowledge 抽取**：`reference-sla-dashboard.md` 从 `tmp/sla.json` 结构化提炼 — 5 variables / 7 panel rows / ~40 SLI PromQL / SLA 阈值约定。
3. **YB 3-way 统一**：bootstrapping + debug-process + incident-recovery → 单文件 `runbook-yugabyte-oncall.md`（419 行）。
4. **General knowledge 清理**：17 个 score ≤3 的通用 md 删除（IaC philosophy / 通用 DNS / 通用 nginx / 通用 AWS IAM 等）。
5. **Case postmortem 合并**：13 `.incident.md` 合并进主 case（10 absorbed + 3 appended section with unique metadata）。
6. **索引重建**：knowledge/README.md / facets/index.md / tools/index.md / agent-routing-table / CLAUDE.md 全部更新。

## Observations（记在 `records/observations.md`）

- Explore subagent 是 read-only → batch audit 应该用 general-purpose
- Sonnet subagent 偶尔只返回 summary，prompt 要强制 "必须用 Write tool" 或 "必须 include JSONL in message"
- Audit subagent 对 "内容相同" 判断不可靠（onefinance vs large-tenant 实际不同）→ 未来 audit 让它真跑 diff
- 循环 merge 冲突（YB 三角）需要 plan 阶段手工裁决
- Gitignore 复杂：`knowledge/references/` 全部 gitignored；结果 ~半数文件变更只在 filesystem，不在 git log
- Phase 7 subagent 被 rate limit 打断 → 未来拆更多更小 subagent

## Phase 7 发现的 Gap（记在 `records/07_case_validation.md`）

1. `verify.py` 的 verdict regex 不兼容 `**Verdict**: X` markdown bold 格式
2. `fan_out_parallelism` 要求 ISO8601 timestamp 但 sub-agent 常漏
3. `baseline_diff` 基线只有 4 samples，可能过松
4. 缺 ingress-nginx admission webhook 类 case，应 compound-learning 沉淀
5. Subagent rate-limit 需要拆成更小的任务

## 遗留的 Deferred Work

- `reference-knowledge-base-index.md`（25K+ tokens）的 alert pattern table 合并进 `knowledge/README.md` — 延期到下次有精力读时做
- `runbook-database-incident-troubleshooting.md` — 降级 keep，但长期看应该 merge 或重构为 multi-DB card
- Layer 1 skill 补全：connrefused / kafka-lag / crashloop / errorrate 目前 fallback 到 debug tree，未来应写成独立 workflow skill
- 上述 verify.py 和 fan_out prompt 的 fix

## 回滚指引

如果发现回归，按顺序 revert：
```
git log --oneline | head  # 看最近几个 commit
# 最新 3 个 commit 是本次 refactor:
#   sre-agent: Phase 5 Batch D+E
#   sre-agent: Phase 5 Batch B — merge
#   sre-agent: Phase 5 Batch A — prune
#   sre-agent: Phase 0-4 refactor plan + vm-query skill

git revert <sha>  # 单个 batch
# 或
git reset --hard <pre-refactor-sha>  # nuclear，只在必要时
```

`~/.claude/skills/sre-vm-query` symlink 是 safe — 删除或保留都不影响现有 agent 行为（未引用该 skill 时不加载）。

`~/.claude/agents/sre-oncall-triage.md` symlink 依然指向 `CLAUDE.md`（absolute path），重构后的 CLAUDE.md 更精简，全局 agent 定义自动更新。

---

**Done.**
