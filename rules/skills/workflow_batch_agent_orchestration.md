# 批处理 Agent 执行: Orchestrator-Worker-StateMachine

## 元数据

- 类型: Workflow
- 适用场景: 大批量独立目标处理, repo 扫描修复, 批量转换/校验, 长任务可恢复执行
- 创建日期: 2026-03-26
- 来源: 多次对话 + 实战复盘

---

## 核心原则

- Orchestrator 独占全局决策权: 分发目标, 判断 done, 控制重试与停止。
- Worker 只处理分配目标: 不做停止判断, 不询问是否继续。
- 状态必须外置: 依赖对话续航会导致提前停止/随机停止/跑偏。
- Verifier 是必需层: 根因通常不是模型不聪明, 而是缺少可验证的 done 条件。

## 最小可运行分层

- L1 Orchestrator: 读队列, 派发, 收敛停止条件
- L2 Worker: 执行 target, 写结果
- L3 Verifier: 验证结果, 决定 done/retry/failed
- L4 Scribe(可选): 汇总报告与统计

## 文件契约(推荐)

- `queue.jsonl`: 一行一个 task, 形如 `{ "id": "...", "target": "...", "state": "todo", "attempt": 0 }`
- `results.jsonl`: 一行一个成功结果, 记录输入摘要 + 输出制品引用
- `failures.jsonl`: 一行一个失败记录, 记录错误类型 + 证据 + 可重试性
- `run.md`: 本次运行配置, 版本, 停止条件, 验收口径
- `summary.md`(可选): 面向人类的汇总

## 标准状态机

- `todo` -> `doing` -> `done`
- `doing` -> `failed`(不可重试)
- `doing` -> `retry` -> `todo`(可重试, attempt+1)

## 停止条件(不要只用队列清空)

- `queue.jsonl` 中 `todo/doing/retry` 清零
- 失败率超过阈值(例如连续 N 个失败或失败占比 > X%)
- 达到最大重试次数
- 达到最大运行时间

## Worker 硬协议(建议写进 run.md)

- 输入: 单个 task + 明确的验收标准
- 输出: 只写 `results.jsonl` 或 `failures.jsonl`, 不修改全局策略
- 禁止: 自行决定跳过/停止, 自行改变目标范围, 以闲聊替代结构化输出
