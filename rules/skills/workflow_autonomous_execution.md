# 自主执行工作流（Autonomous Execution）

## 元数据

- **类型**: Workflow
- **适用场景**: 需要持续自主执行的多步骤任务，减少不必要的人工中断
- **前置依赖**: `workflow_parallel_subagents.md`（并行 sub-agent 调度）
- **创建日期**: 2026-03-29

---

## 核心理念

Agent 频繁停下来问用户，根因是不确定自己是否有权执行下一步。解决方法不是"别问了"，而是**提前消除不确定性**：在任务开始时声明作用域，agent 在范围内自主执行，超出范围才 escalate。

---

## 三阶段流程

```
Phase 1: Plan（规划）→ Phase 2: Execute（执行）→ Phase 3: Report（汇报）
```

### Phase 1: Plan

派出 Plan sub-agent，输出结构化计划并持久化。

**触发方式：**

```
Agent(
  subagent_type="Plan",
  prompt="""
  目标：{用户原始目标}

  输出要求：
  1. 将目标分解为可独立验证的步骤（每步有明确的完成标准）
  2. 标注步骤间的依赖关系（哪些可并行）
  3. 标注每步需要的权限级别（只读 / 写文件 / 执行命令 / 外部调用）
  4. 输出为 markdown checklist 格式

  约束：
  - 每步粒度：一个可验证的中间状态（不是代码行级别）
  - 步骤数：3-8 步（太细失去灵活性，太粗无法追踪）
  """
)
```

**Plan 文件格式**（写入 `tmp/plan-{task-name}.md`）：

```markdown
# Plan: {目标}

Created: {timestamp}
Status: in_progress

## Scope Declaration

### Authorized（自动执行，无需确认）
- 读写：{目录/文件范围}
- 命令：{允许执行的命令列表}
- 操作：{允许的操作类型}

### Restricted（必须停下来确认）
- {禁止的操作，如 git push, 删除文件, 生产环境操作}

### Escalation Trigger（遇到以下情况立即停止）
- 连续两次相同步骤失败
- 发现问题范围超出原始目标
- 需要执行 Restricted 中的操作

## Steps

- [ ] **Step 1**: {描述} | 权限: read-only | 可并行: no
  - 完成标准: {具体标准}
  - 验证方式: {如何确认完成}
- [ ] **Step 2**: {描述} | 权限: read-write | 可并行: yes (with Step 3)
  - 完成标准: {具体标准}
  - 验证方式: {如何确认完成}
- [ ] ...

## Execution Log

（执行过程中追加）
```

**关键设计决策：Scope Declaration 放在 plan 文件里，而不是对话上下文里。** 原因：对话上下文会被压缩，plan 文件不会。Agent 在每一步执行前读取 plan 文件，就能重新获取自己的权限边界。

### Phase 2: Execute

主 Agent 读取 plan 文件，逐步执行。

**执行逻辑：**

```
for each step in plan:
    1. 读取 plan 文件，确认当前步骤和 scope
    2. 判断该步骤是否在 Authorized 范围内
       - 是 → 直接执行（或派 sub-agent）
       - 否 → 停下来，向用户展示要做什么、为什么、预期结果
    3. 执行后，按"验证方式"检查结果
    4. 更新 plan 文件：标记完成 + 追加 execution log
    5. 如果结果偏离预期 → 触发 re-plan（见下方）
```

**并行执行：** plan 中标记 `可并行: yes` 的步骤，用 `run_in_background=True` 同时派出多个 sub-agent。遵循 `workflow_parallel_subagents.md` 的规则。

**Re-plan 机制：** 当执行到某步发现前提不成立时，不要硬做，重新派 Plan agent：

```
Agent(
  subagent_type="Plan",
  prompt="""
  原始目标：{目标}
  已完成步骤：{从 plan 文件提取}
  当前状态：{Step N 的执行结果和发现的问题}

  请基于当前状态修订后续计划。已完成的步骤不要动。
  """
)
```

修订后的 plan 覆盖写入同一文件，保留已完成步骤的状态。

### Phase 3: Report

所有步骤完成后，输出执行摘要：
- 完成了什么
- 跳过/修改了什么（如果有 re-plan）
- 需要用户后续关注的事项

---

## Scope Declaration 设计指南

Scope 写得越精确，agent 停下来的次数越少。

**好的 scope：**
```
Authorized:
- 读写：src/service-a/ 下所有 .go 文件
- 命令：go test ./..., go build, curl localhost:8080
- Git：git add, git commit（不 push）
```

**差的 scope：**
```
Authorized:
- 可以改代码
- 可以跑命令
```

前者像精确的 RBAC role，后者像 cluster-admin。你不会给 service account 发 cluster-admin，也不应该给 agent 模糊的授权。

---

## Execution Log 格式

每步执行后追加到 plan 文件底部：

```markdown
### Step 2 — 2026-03-29T14:30:00+09:00
- Action: 修改 handler.go，添加 /health endpoint
- Result: 文件已修改，go build 通过
- Verification: curl localhost:8080/health → 200 OK
- Next: 继续 Step 3
```

这个 log 有两个作用：
1. 如果 context window 被压缩，agent 读 plan 文件就能恢复完整进度
2. 事后审计：人可以回溯 agent 做了什么、为什么

---

## 与其他 Skill 的关系

- **workflow_parallel_subagents.md**：Phase 2 中并行步骤的调度规则
- **bestpractice_staged_approach.md**：破坏性操作前的 dry-run 原则仍然适用
- **bestpractice_ai_programming_mindset.md**：每步的"完成标准"对应"成功标准"原则

---

## 适用与不适用

**适用：**
- 多步骤实现任务（feature 开发、bug 修复、重构）
- 调研后执行的混合任务
- 任何你希望 agent 持续跑 10 分钟以上不停的场景

**不适用：**
- 单步操作（直接做，不需要 plan）
- 纯对话/讨论（没有执行步骤）
- 高风险生产操作（需要逐步人工确认，不应该自主执行）
