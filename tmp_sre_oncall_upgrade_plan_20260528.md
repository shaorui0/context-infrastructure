# SRE Oncall Triage 升级 Plan（基于 gstack 调研）

> 日期：2026-05-28
> 范围：`~/.claude/skills/sre-oncall-*` + `workflow-oncall-spike` + `workflow_dv_monitoring_oncall`
> 调研依据：`contexts/survey_sessions/gstack_design_philosophy_survey_20260527.md`
> 核心思想：**不加新角色，给现有 skill 补 "isolation + handoff + confidence" 三件套**

---

## 0. 现状审计（已有的不抄）

✅ **你已经做到的**（gstack 同形 / 比 gstack 更克制）：
- Layer 0/1/2 架构 + 路由表（≈ gstack 的 SKILL.md tier 概念）
- Workdir 结构 `tmp/oncall/<ts>_<label>/{plan,log,report,evidence}/` （≈ gstack `{branch}-ship-state.yaml` handoff）
- Fast/slow fork（subagent 搜历史 case） + Read-only / Mutation gate
- knowledge/{cases,cards,patterns,debug-trees,runbooks} 知识库（≈ gstack `/learn`）
- Evidence-backed + alias-first + Slack 措辞规范

❌ **可以从 gstack 学的 4 个缺口**：
1. **Role-phase isolation**：主 agent 一开始就看到全部信号；gstack `/investigate` 是 hypothesis 锁定后**才解锁 deploy history**
2. **Quote-the-line confidence gate**：结论没强制锚定到具体 metric 值 / log 行号
3. **Iron Law + 3-strike rule**：没有"3 次假设失败后强制 escalate"硬刹车
4. **Sub-agent context isolation 不够激进**：fast path 派了 subagent，slow path 主 agent 自己跑 MCP 查询 → context 仍被原始结果污染

---

## 1. 升级清单（按优先级）

### P1. Phase Lock：从"调查者 / 决策者 / 操作员"3 角色重新切 phase

**Problem**：现在主 agent 在 Layer 1 调查时已经能看到 runbook 路由表 + 操作命令模板，可能"边查边规划修复方案"，违反 Karpathy wrong-assumption 模式。

**Patch**：把 triage 强制拆 3 phase，**phase 之间用文件 gate 而不是 prompt gate**。

| Phase | 身份 | 可读 | 不可读 |
|---|---|---|---|
| **Phase A 调查者** | 只看指标 / 日志 / 拓扑 | knowledge/{debug-trees, patterns}, MCP read-only | `runbooks/`, `historial_operations/`, deploy history（先验偏见） |
| **Phase B 决策者** | 看根因 + 历史 case + deploy diff | + `knowledge/cases/`, deploy history, `historial_operations/` 索引 | runbook 实际命令（避免提前抄命令） |
| **Phase C 操作员** | 生成命令 + 等 approve | + 完整 runbook + `# INTENT:` + alias 映射 | (无新限制) |

**机制**：
- 在 `plan.md` 加 `phase: A / B / C` 字段，每次切换写时间戳
- 在 `sre-oncall-init` 第一步显式 inject："Phase A 期间禁止 Read `runbooks/` 和 `historial_operations/`，需要时升级到 Phase B"
- Phase 切换需要 user 显式 "next phase" 或写出 Phase A 完结条件（根因假设 ≥1）

**验收**：Phase A 的 log.md 不应该出现任何 `historial_operations/` 路径

---

### P2. Quote-the-line Confidence Gate

**Problem**：现在 report.md 可以写 "P99 spike due to GC pause" 而不强制贴 GC pause 的实际 metric 截图 / 数值。Karpathy wrong-assumption + overcomplexity 模式高发地。

**Patch**：在 `sre-oncall-output-format` 加一条硬规则：

```markdown
## Finding Confidence Rule（quote-or-suppress）

每条 "Root cause / Symptom / Recommendation" 必须满足下列之一才能写进 report.md：
1. 紧接一行 `> evidence:` 引用具体 PromQL/LogQL 返回值 + 时间戳
2. 紧接一行 `> file:line:` 引用 knowledge/ 下具体 case file:line
3. 紧接一行 `> historical:` 引用 fast-path subagent 返回的具体 case slug

不满足 → confidence 字段强制 ≤ 3，且 Slack response 里只能用 "possibly" / "candidate" 措辞。
```

**实现**：在 `report.md` 模板里加 `confidence: 1-5` 字段，模板注释里写明 quote 规则。

---

### P3. Iron Law + 3-strike Escalation

**Problem**：现在没有"调查走死循环"硬刹车，可能在错误假设上深挖 30 分钟。

**Patch**：参考 gstack `/investigate`，在 `sre-oncall-acceptance-criteria` 增加 2 条 Iron Law：

```markdown
## Iron Laws

1. **No conclusion without root cause hypothesis**
   Slack 回复不能在 `plan.md` 的 `root_cause_hypothesis:` 字段为空时发送。

2. **3-strike rule**
   每次写 log.md 一行 hypothesis 后，标记 ✓/✗。累计 3 个 ✗ 必须：
   - 停止当前调查路径
   - 在 plan.md 写 `escalation: <reason>`
   - 在 Slack 主动说 "need second opinion, root cause unclear after N hypotheses"
   - 或调起 `/codex` 第二意见 subagent
```

**实现**：
- `plan.md` skeleton 加 `hypothesis_log: []` 字段
- 每条 hypothesis 一行 `- {ts}: {hypothesis} | result: ✓/✗`
- log.md 写一个 `count_failed_hypotheses` 计数

---

### P4. Sub-agent Context Isolation 升级

**Problem**：slow path 主 agent 现在自己跑 `vm__query` + `loki__query` + `grafana__*`——返回的 raw 时序数据 / 日志行直接进主 context。一次 P99 调查可以吃掉 30K token raw output。

**Patch**：主 agent **不直接调 MCP**，全部 delegate 给 sonnet subagent，subagent 只返回结构化总结。

```
主 agent (Opus) → Agent(subagent_type="sre-vm-query", run_in_background=false, prompt="
  查 westernunion-prod P99 latency 2026-05-28 14:00-14:15，3min step。
  只返回：(1) max value + ts，(2) 是否有 step 跳变（>2x），(3) 与前 1 小时 baseline 对比 ratio。
  不要返回原始时序。
")
```

**实现**：
- 在 `sre-oncall-triage` SKILL.md "Workflow Architecture" 加一行 hard rule："Slow path 主 agent **禁止**直接调 `mcp__victoriametrics__*` / `mcp__grafana__*` / `loki_fetch.py`。一律 Agent 派发，subagent 返回 ≤500 token 结构化摘要。"
- 例外：`mcp__victoriametrics__labels` / `mcp__grafana__list_*` 这种 metadata 调用（返回小）可以主 agent 直接调

**预期收益**：单次 triage 主 context 占用从 ~40K → ~8K，使主 agent 在 Phase B/C 仍有清晰判断力

---

### P5. Workflow 化：把 3 phase + 4 gate 用一个 wrapper skill 串起来

**Problem**：现在 `sre-oncall-init` / `sre-oncall-triage` / `workflow-oncall-spike` / `sre-oncall-acceptance-criteria` 是松散组合，靠 prompt chaining 触发，容易漏 step。

**Patch**：新增 `workflow_oncall_full_triage.md`，类似 gstack `/ship` 的 idempotent re-runnable pipeline：

```markdown
---
name: workflow_oncall_full_triage
description: SRE oncall 完整 triage 流水线。Phase A 调查 → Phase B 决策 → Phase C 操作。
---

# 11-step pipeline

0. /sre-oncall-init → 创建 workdir + 信号提取 + fast path fork
1. **[Phase A gate]** confirm: phase=A, no runbook access
2. 派 sre-vm-query subagent 拉初始指标摘要
3. 派 dv_loki_fetch subagent 拉错误日志摘要
4. 主 agent 写 hypothesis 到 plan.md
5. **[3-strike gate]** 检查 count_failed_hypotheses < 3，否则 escalate
6. **[Phase B gate]** root_cause_hypothesis 非空 → 切 phase=B，解锁 cases/ + deploy history
7. 派 historical case match subagent
8. **[Confidence gate]** report.md 每条 finding 必须 quote-the-line
9. **[Phase C gate]** user 确认根因 → 切 phase=C，加载 runbook
10. 生成 # INTENT: 命令方案 + 等 approve
11. 操作完 → /sre-oncall-compound-learning 蒸馏 → 更新 knowledge/
```

每个 step 完成在 plan.md 写 `step_N_done: <ts>`，断 session 后下一个 session 读 plan.md 即可续跑（≈ gstack handoff YAML）。

---

## 2. 实施顺序 & 依赖

```
P4 (subagent isolation)  ─┐
                          ├─→ P1 (phase lock)  ─┐
P2 (quote-the-line)     ──┘                     ├─→ P5 (workflow wrapper)
P3 (Iron Law + 3-strike) ──────────────────────┘
```

**P2/P3/P4 是独立小补丁，可并行做**。每个 ≤ 1 小时改动。
**P1 依赖 P4**（subagent 隔离后 phase lock 才有意义）。
**P5 是 capstone**，等前 4 个稳定后做。

---

## 3. 验证 / 测试方案

每个升级都要在**一次真实 triage** 上验证，不要纸面验收：

| 升级 | 验证方法 |
|---|---|
| P1 phase lock | 故意在 Phase A 提示 "看看最近 deploy"，主 agent 应该拒绝并说 "需要先切到 Phase B" |
| P2 quote-the-line | 故意写一条无 evidence 的 finding，检查 confidence 是否被强制压到 ≤3 |
| P3 3-strike | 用一个真实但难定位的 alert，看是否在第 3 次假设失败后主动 escalate |
| P4 subagent isolation | 跑一次 triage，记录主 agent token 占用，应 < 10K |
| P5 workflow | 中途 Ctrl-C，新 session 只 cat plan.md，能否从断点续跑 |

---

## 4. 不抄 gstack 的 3 件事（明确划界）

1. ❌ **不加 CEO/Designer/Eng Manager role**：你是 SRE 不是 founder
2. ❌ **不拆成 23 个 slash command**：现有 9 个 oncall skill 密度刚好
3. ❌ **不追求 "10K LOC/week" 类 vanity metric**：oncall 的 success metric 是 MTTR + 误判率，不是数量

---

## 5. 风险

| 风险 | 缓解 |
|---|---|
| Phase lock 太严，紧急时反而拖慢 | 加 `--bypass-phase-lock` 显式 escape hatch，但用了要写 retro |
| Subagent isolation 后主 agent 失去"手感" | 保留 metadata 调用直通权；提供 `--show-raw <query>` debug 模式 |
| 3-strike rule 在已知简单 case 触发过早 | 区分 quick check（不算 strike）vs full triage（算 strike） |
| Workflow wrapper 与现有 init/triage 重复 | wrapper 只编排不重写，每 step 仍调 sub-skill |

---

## 6. 后续（可选 / 远期）

- **Compound learning automation**：每完成一次 triage，自动 diff knowledge/ 看是否需要新增 case（你已有 `sre-oncall-compound-learning`，可强制注入到 P5 step 11）
- **Cross-incident pattern detection**：跑 batch agent 扫历史 30 天 report.md，找 recurring root cause（gstack 没这个，你可以做出差异点）
- **Codex 第二意见集成**：P3 escalate 时自动调 `/codex challenge` 派 GPT 验证根因假设

---

## 7. TL;DR（给未来的自己 / 同事看）

**3 个改动 + 1 个 wrapper，让 oncall triage 从"靠主 agent 自觉"变成"靠文件 gate 强制"**：

1. **Phase lock**（Phase A/B/C 文件 gate）→ 防 wrong-assumption
2. **Quote-the-line gate** → 防幻觉结论
3. **3-strike escalation** → 防死循环深挖
4. **Subagent isolation 升级**（主 agent 不直调 MCP）→ 防 context 污染

落地后，主 agent 在每个 phase 只看见它**该看见**的东西——这就是 gstack 给你的唯一核心启示。
