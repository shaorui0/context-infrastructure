# RAG & LangGraph 概念澄清

**Date:** 2026-03-30

---

## Key Insights

- **RAG 的本质是分工**：检索器做"找"，LLM 做"答"。两者都干不好对方的活——LLM 在海量文本里找重点能力很差，检索器不会生成语言。RAG 是补短板，不是叠加。

- **LangGraph 的核心价值不在"图"，在状态持久化**：循环和分支自己写 while 也行，真正难自己做的是 Checkpointer（断点续跑）、interrupt（人工介入节点）、可视化调试。没有这些需求，LangGraph 是过度设计。

- **Claude Code 和 LangGraph 目的层不同**：Claude Code 是"用 Agent 的工具"，LangGraph 是"造 Agent 的框架"。混淆这两个层级是常见误判。

- **Agent 产品开发的正确路径**：先裸写 Anthropic SDK 的 tool_use 循环（真正理解机制），复杂度上来再引入框架。跳过裸写直接用框架会导致不理解框架在解决什么问题。

---

## Open Questions

- Anthropic 自己的 Agent SDK（非 Claude Code）和 LangGraph 的定位对比——什么情况下选哪个？
- LangGraph 的 Checkpointer 在生产环境怎么选存储后端（Redis vs Postgres）？

---

## Concrete Artifacts

**LangGraph 价值判断矩阵：**

| 场景 | 用 LangGraph | 不用 |
|------|-------------|------|
| 简单问答/单次调用 | 过度设计 | 直接调 API |
| 多步 Agent（工具调用循环） | 省心 | 自己写循环也行 |
| 复杂多 Agent 协作 | 强项（子图、并行节点） | 很麻烦 |
| 生产级断点续跑/审计 | 内置 Checkpointer | 需自己实现 |

**Agent 产品开发优先级：**
1. Anthropic SDK 裸写（理解 tool_use 循环）
2. 复杂度上来后 → LangGraph 或 Claude Agent SDK
3. LangGraph 真正价值：持久化 + 人工确认 + 可视化调试
