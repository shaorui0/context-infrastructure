---
name: sre-oncall-compound-learning
description: "调查结束后的知识复利流程：判断 delta → 写入知识库 → 更新索引"
---

# Compound Learning（知识复利）

调查结束后，根据 case 的新颖程度，将经验沉淀回 agent 知识库。

## 判断标准

是否有 delta：和已有 knowledge 相比，这次学到了什么新东西？

- 这个 case 匹配已有 pattern 吗？→ 如果完全匹配，不新建，考虑更新已有文件
- 有新的根因路径吗？→ 新建 case + 可能新建 debug tree
- 有新的告警类型/信号吗？→ 考虑更新 `agent-routing-table.md`
- 有新的工具用法/检查方法吗？→ 考虑新建或更新 facet

## 沉淀类型

| 类型 | 目标目录 | 适用场景 | 文件命名 |
|------|---------|---------|---------|
| **Case 记录** | `knowledge/cases/` | 完整 incident 记录（症状 → 根因 → fix） | `case-<description>.md` |
| **Pattern 提取** | `knowledge/patterns/` | 新的根因模式或 failure pattern | `pattern-<description>.md` |
| **Debug Tree** | `knowledge/debug-trees/` | investigation 走了新路径，值得固化为决策树 | `debug-tree-<description>.md` |
| **Card 快查** | `knowledge/cards/` | 新类型告警的 first-2-min 快速响应 | `card-<description>.md` |
| **Runbook 步骤** | `knowledge/runbooks/` | 新的操作流程（带 `#MANUAL` gate） | `runbook-<description>.md` |
| **Facet 补充** | `facets/` | 新的结构化知识维度 | `<dimension>.md` |

## Frontmatter Schema

所有新文件必须遵循：

```yaml
metadata:
  kind: case | pattern | debug-tree | card | runbook | checklist
  status: draft
  summary: "<一行描述>"
  tags: ["tag1", "tag2"]
  first_action: "<第一个诊断步骤>"
  related: ["<相关文件路径>"]
  derived_from: "<本次 triage 输出文件路径>"
```

## Case 文件结构

```markdown
## TL;DR（5 步）
1. 告警信号
2. 关键发现
3. 根因
4. 修复动作
5. 后续跟进

## 信号
<从 triage 输出的 Extracted Signals 复制>

## Evidence Chain
<关键 MCP 查询结果和解读>

## 结论
<hedged language: "likely", "consistent with">

## 建议操作
<从 triage 输出的操作命令方案复制>
```

## 流程

1. 写入知识库文件
2. 更新 `knowledge/README.md` 索引
3. 如果发现新路径，更新 `knowledge/agent-routing-table.md`

## 原则

- **优先更新已有文件**：和已有 pattern/case 相似时，补充而非新建
- **只记 delta**：不重复已有知识
- **status: draft**：新文件初始状态为 `draft`，人工 review 后提升为 `stable`
