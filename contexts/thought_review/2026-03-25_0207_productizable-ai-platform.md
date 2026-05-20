# 可产品化 AI 平台

**日期**：2026-03-25
**来源**：Claude Code 对话

## 关键结论

- 能卖钱的 AI 平台本质上是工程基础设施，不是聊天助手。核心由 agent runtime、状态与证据系统、skill 生态、验证与安全、control plane 组成。
- 企业真正愿意付费的是可控自动化、可审计执行和明确 ROI，不是更炫的模型界面。
- 最值得切入的方向是 AI SRE 或 Infra 场景，因为价值闭环最清晰；通用 agent 平台和通用助手平台过于泛化。

## 思维与偏好

- 一贯把 AI 当作 infra 组件来设计，而不是把 prompt 当产品本体。
- 很强调流程外部化、可验证优先、可恢复优先、可审计优先和人类可控。这些要求说明判断标准已经是平台级而不是 feature 级。
- 明确认为长期护城河来自 skill/tool 生态和状态控制，而不是模型本身，也不是 UI 包装。

## 工作上下文

- 五层架构：L1 Agent Runtime，L2 State & Artifact，L3 Skill / Tool Registry，L4 Verifier & Safety，L5 Control Plane。
- L2 需要保存 run state、step state、artifact、trace log、decision log，并提供 resume 能力。
- 企业付费能力集中在自动排障、infra 分析、cost 优化、repo 级分析、自动 review、安全合规。

## 可复用方法

- 评估一个 AI 平台是否具备产品化潜力时，逐层检查五层架构是否齐全，尤其关注状态恢复和 verifier 机制是否落地。
- 在高风险自动化场景使用统一流程：read、diagnose、propose、verify、approve、apply、verify。
- 做 MVP 时只抓五件事：runtime、run 状态系统、skill registry、verifier、审计日志。先不要把时间花在复杂 UI、花哨 agent 或通用聊天能力上。
