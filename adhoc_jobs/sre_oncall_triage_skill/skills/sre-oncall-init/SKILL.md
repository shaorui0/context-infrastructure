---
name: sre-oncall-init
description: "Layer 0 入口：创建工作目录 + skeleton files → 信号提取 → 路由到 Layer 1 type skill。每次 triage 的第一个动作。"
---

# SRE Oncall Init（Layer 0 Entry）

**每次 triage 的第一个动作。在任何 MCP 查询之前执行。**

物理文件结构 = gate — 先建骨架，再填内容。

## 按需加载的姊妹文件

> 本文件保持 lean。详细内容在两个 sibling 文件，**按需读，不预加载**：
>
> - **`phase_lock.md`** — Phase A/B/C 访问边界详细定义、转换语法、escape hatch、output gate。**在 plan.md 创建后 / phase 切换时**读。
> - **`skeletons.md`** — plan.md / log.md / report.md 三个完整 skeleton。**仅在 Step 2-4 写文件那一刻**读。
>
> Standalone `/sre-vm-query` 和 `/dv_loki_fetch` 不进入本流程，**不需要**读上述文件。

---

## Step 0: Fast Path Fork（与 Step 1 同时启动）

**在创建目录之前就 fork fast path。** 只需从 alert text 提取最小信号。

```
Agent(model="sonnet", run_in_background=true, prompt="
  在 knowledge/ 目录下搜索匹配当前告警的历史 case、card、pattern。

  当前告警信号：
  - alertname: {alertname}
  - cluster: {cluster}
  - client: {client}
  - keywords: {从 alert text 提取的关键词}

  搜索步骤：
  1. 读 knowledge/README.md 获取索引
  2. Grep knowledge/cases/*.md frontmatter 的 tags/summary 搜索匹配
  3. Grep knowledge/cards/*.md 搜索匹配的 fast-triage card
  4. Grep knowledge/patterns/*.md 搜索匹配的 root cause pattern

  输出：最相关的 1-2 个匹配（filename + summary + first_action），或 'No match found'
")
```

**不等 fast path 完成，立即进入 Step 1。** Fast path 结果在 Step 9 合并。

## Step 1: 创建工作目录

```bash
TIMESTAMP=$(date +%Y%m%d_%H%M)
LABEL="<从 alert 提取的简短标签，如 westernunion-p99-spike>"
WORKDIR="/Users/rshao/work/work-harness/tmp/oncall/${TIMESTAMP}_${LABEL}"
mkdir -p "${WORKDIR}/evidence"
```

## Step 2-4: 创建 plan.md / log.md / report.md

**Read `skeletons.md`**（按需加载），把里面的 3 个 skeleton 写入对应文件。Skeleton 内容写完即可，**不需要保留在 context**。

文件用途：
- `plan.md` — Investigation plan + signals + scope + routing + Phase Lock state
- `log.md` — Investigation log（实时写入，每查一个写一行）
- `report.md` — 最终输出（Slack response + internal notes + 操作命令方案）

## Step 4.5: Skeleton Checkpoint

```bash
ls -la "${WORKDIR}/plan.md" "${WORKDIR}/log.md" "${WORKDIR}/report.md" "${WORKDIR}/evidence/"
```

任一缺失 → 立即重建，不继续 Step 5。Write 工具失败用 Bash `cat <<'EOF'`。**不允许跳过文件创建把内容返回到对话**。

## Step 4.6: 加载 Phase Lock（plan.md 写入 phase: A 后立即生效）

**Read `phase_lock.md`**。Phase A 起始约束此刻生效：禁读 `runbooks/`、`historial_operations/`、`knowledge/cases/` 完整内容、deploy history。违反 = Iron Law 3。

## Step 5: 信号提取

从 alert text 提取信号，填入 `plan.md` 的 Extracted Signals 表。

- 输入是 Slack link → 先 parse + fetch（参考 `facets/slack_alert_intake.md`）
- 提取规则参考 `facets/signal_extraction.md`
- **只提取，不推断**。缺失字段填 `<missing>`

## Step 6: Missing Field Gate

检查 plan.md 中的 Missing Field Gate checklist：

- `event_ts` 有值？
- `cluster` 有值？
- `namespace` 或 `service` 至少一个有值？

**任一缺失 → 停下向用户要信息**。展示已提取的信号，说明缺什么、为什么需要。

## Step 7: 计算时间窗口

从 event_ts 计算精确时间窗口，填入 plan.md：

```python
event_epoch_ms = <event_ts as epoch milliseconds>
start_ms = event_epoch_ms - 180000   # -3 min
end_ms   = event_epoch_ms + 180000   # +3 min
# RFC3339 for MCP queries
# epoch_ms for Grafana links
```

## Step 8: 路由到 Layer 1 Skill

基于信号和 `knowledge/agent-routing-table.md` 做路由决策，填入 plan.md 的 Routing Decision。

### 路由表（快速版）

| Signal Pattern | Layer 1 Skill | Fallback |
|----------------|--------------|----------|
| P99/P95 latency spike | `/workflow-oncall-spike` | `debug-tree-latency-breakdown.md` |
| P99 spike + error_rate normal | 先跑 `debug-tree-false-p99-histogram-skew.md` | — |
| Connection refused / timeout | _(TBD)_ | `debug-tree-connection-refused-layered.md` |
| Kafka consumer lag | _(TBD)_ | `debug-tree-kafka-lag-downstream.md` |
| OOMKilled / CrashLoopBackOff | _(TBD)_ | Cluster 2 policy |
| Error rate spike (5xx) | _(TBD)_ | service-specific |

## Step 9: 合并 Fast Path 结果

Step 0 的 sonnet subagent 此时通常已完成（< 30s）。检查结果：

- **匹配 case**：写入 report.md 的 `## Historical Pattern Matches`；case 的 `first_action` 加入 plan.md Planned Queries；立即展示给用户："找到匹配的历史 case：{filename} — {summary}"
- **匹配 card**：记录到 plan.md 作为参考
- **无匹配**：记录 "No historical match found"，继续正常流程
- **subagent 未完成**：不等待，继续 Step 10，结果在 Layer 1 异步合并

**Fast path 不替代 slow path**：历史 case 提供方向，当前调查仍需新鲜证据。

## Step 10: 展示 Plan + 确认

展示给用户：
1. Fast path 结果（如有匹配）
2. 提取到的信号
3. 时间窗口
4. 路由决策（哪个 Layer 1 skill）
5. 计划查什么

用户确认后 → 调用对应 Layer 1 skill。

## 完成条件

- [ ] `${WORKDIR}/{plan,log,report}.md` + `evidence/` 全部存在
- [ ] plan.md 顶部 `phase: A` 已写入，phase_lock.md 已 read
- [ ] Extracted Signals 已填
- [ ] Missing Field Gate 通过（或已向用户确认）
- [ ] Time window 已计算
- [ ] Routing decision 已填入 plan.md
- [ ] Fast path subagent 已启动（结果可异步合并）
- [ ] Plan 已展示给用户
