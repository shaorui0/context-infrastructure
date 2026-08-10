# Phase Lock — Triage-Specific Access Boundary

> **按需加载**。仅在 plan.md 创建后 / phase 切换时读本文件。Phase Lock 是 triage workflow 专有，**不**适用于 standalone `/sre-vm-query` 或 `/dv_loki_fetch` 调用。

`plan.md` 顶部的 `phase:` 字段强制限制主 agent 可读资源。**违反 = Iron Law 3 违反**（见 `sre-oncall-acceptance-criteria`）。

## Phase A — 调查者（默认起始 phase）

**身份**：只看症状，不看修复方案。防止 Karpathy wrong-assumption 失败模式（"看到 deploy 就脑补根因"）。

- ✅ 可读：`knowledge/{debug-trees, patterns, references}/`、MCP read-only（label/metric/log）、用户提供的 kubectl get/describe 输出
- ❌ 禁读：`~/work/work-harness/code_repos/historial_operations/`（runbook 源）、`knowledge/cases/` 完整内容（只允许 fast-path subagent 返回的 case slug + summary）、deploy history、helm release diff

**切换到 B 的前置**：`root_cause_hypothesis` 字段非空，且 `hypothesis_log` 至少有 1 条 `result: ✓` 或 `?`。

## Phase B — 决策者

**身份**：已有根因假设，要找历史先例 + 验证修复方向。

- ✅ 新解锁：`knowledge/cases/`（完整内容）、deploy history（`kubectl rollout history` / helm diff）、`historial_operations/<dir>/README.md`（**只读 overview，不读命令体**）
- ❌ 仍禁：`historial_operations/<dir>/` 下的具体 `.sh` / `.yaml` / 命令模板文件

**切换到 C 的前置**：用户在 Slack 或对话中显式确认根因（"yes proceed" / "go with this hypothesis"）。

## Phase C — 操作员

**身份**：根因已确认，生成操作命令方案 + 等 approve。

- ✅ 新解锁：`historial_operations/<dir>/` 全部内容（命令体、yaml、helm chart）、生成 `# INTENT: ...` 命令草稿
- ⚠️ 仍受 Mutation Approval Gate：命令只生成不执行，等用户 approve

## 显式切换语法

切换 phase 时在 `plan.md` 顶部写一条日志：

```yaml
phase_transitions:
  - ts: "14:30:15"
    from: A
    to: B
    reason: "GC pause hypothesis confirmed via jvm_gc_pause_seconds p99 = 4.2s"
  - ts: "14:42:08"
    from: B
    to: C
    reason: "user approved: 'yes, proceed with heap dump runbook'"
```

## Escape Hatch

紧急 P0 场景可以用 `--bypass-phase-lock`（用户在对话里显式说），但 retro 必须复盘为何 bypass。

## Output Gate（triage 专有）

所有 triage 分析必须写入 `${WORKDIR}/report.md`（`tmp/oncall/<YYYYMMDD_HHMM>_<label>/report.md`），对话只输出摘要 + 路径。这条**不**适用于 standalone 数据查询 skill。
