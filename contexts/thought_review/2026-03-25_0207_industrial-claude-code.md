# 工业级 Claude Code

**日期**：2026-03-25
**来源**：Claude Code 对话

## 关键结论

- Claude Code 的工业级形态不是 AI 写代码工具，而是一个可治理的软件生产系统。
- 最小可用架构至少包含四层：Orchestrator 负责任务编排，Worker 负责执行，Verifier/Gatekeeper 负责质量门，Audit/Trace 负责证据与回溯。
- 真正可落地的关键不在提示词，而在 workorder、patch、状态机、权限边界、自动验证和失败恢复闭环。

## 思维与偏好

- 对 AI 编程系统的要求明显偏治理和生产安全：最小权限、显式 scope、可回滚、可审计、未通过不合并。
- 把 AI 视为外包工程师而不是魔法工具，因此强调工单驱动和交付物验收，而不是让模型自由改 repo。
- 偏好小步快跑和小批并发，反对大爆炸式修改。长期任务必须允许失败、降级和人工接管。

## 工作上下文

- 推荐工作区：`workorders/`、`artifacts/`、`patches/`、`evidence/`、`status/`、`guardrails/`。核心思想是产物与 repo 隔离。
- 四个必须存在的运行回路：PDCA、Quality Gate、Failure Recovery、Audit。
- 权限模型：默认允许读，写入限定目录，repo 改动通过 patch，shell 走 allowlist，网络默认禁用，secrets 永久禁止。

## 可复用方法

- 用标准 workorder 定义任务边界：`scope`、`denylist`、`acceptance`、`plan`、`done_definition`、`rollback`、`evidence_required`。
- 给 AI coding 流程强制加质量门：代码生成后必须经过 test、lint、review，再决定是否 merge。
- 长任务失败时采用四级处理：先记录原因，再有限重试，必要时降级为只产出 patch，最后输出人工可执行建议而不是硬停。
