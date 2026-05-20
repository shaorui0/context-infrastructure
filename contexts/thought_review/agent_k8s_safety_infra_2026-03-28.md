# Agent K8s Safety Infrastructure — Session Distill

**Date**: 2026-03-28 ~ 2026-03-30
**Scope**: 从 ChatGPT 文档分析 → 设计 → 实现完整的 K8s agent 安全基础设施

---

## Key Insights

- **Agent 的核心风险不是 availability，是 control。** 传统 metrics 回答"活没活着"，agent observability 要回答"是否在正确地活着"。它不会 crash，但会 reasoning drift — 没有 error code 的偏航。

- **"信任从模型能力转移到系统约束"是整个设计的第一性原理。** 不赌 agent 永远做对，设计成即使它错了系统依然可控。这不是防御性编程，是控制系统工程。

- **个人 SRE 的 AI infra ≠ 企业 observability platform。** MCP server、OPA policy engine、subagent 分层——架构原则对，但实现复杂度对一个人来说 ROI 不够。你需要的是 "sudo + audit log"，不是 platform。

- **`# INTENT:` convention 是这个 session 最有创造性的产出。** Hooks 拿不到 Claude 的对话上下文（架构限制），但可以让 Claude 把 reasoning 写成 bash 注释嵌入命令本身。零额外 tool call，零临时文件，audit hook 正则提取。这个模式解决了 "audit log 只有 what 没有 why" 的本质问题。

- **PreToolUse hook exit code 语义是关键 API 设计：** exit 0 = 放行（仍走 permission flow），exit 2 = 硬拦（Claude 看到 stderr 反馈）。这两个值的区分让同一个 hook 能同时做"软提醒"和"硬阻断"。

- **Prompt injection through kubectl logs/events 是当前最被低估的风险。** Agent 有执行权限，且读取不可信外部数据（pod logs/annotations）。对策不是技术过滤，而是 CLAUDE.md 规则 + 人工确认 gate。

- **Claude Code 的 6 种权限模式不是选一个用，而是按阶段切换。** plan（调研）→ default + allowlist（执行）→ acceptEdits（本地开发）。auto 模式的 classifier 不懂你的集群语义，不如你自己当 classifier。

- **Cluster 分级是 gate 设计的核心抽象：** dev/preprod（弹确认）→ prod（额外 WARNING + delete 全拦）→ PCI（写操作全拦）。分级不是按 K8s RBAC verb，而是按"失控成本"。

---

## Open Questions

- **Memory hygiene for ops context 还没落地。** 如果 agent 记住了 "cluster A 的 HPA 上限是 10"，但上限改了，agent 会基于错误前提操作。Ops-related memory 需要更短 TTL 和 provenance 标记，但具体机制没设计。

- **多 session 审计日志的 correlation。** 当前 audit log 是 per-session JSONL。跨 session 追踪同一个 incident 的操作链（比如"上周那次 scale + 这周的 rollback"）还没有机制。

- **自然语言 reasoning ≠ 真实因果机制。** ChatGPT 文档里指出 CoT 可能是事后合理化。`# INTENT:` convention 让 agent 说出 reasoning，但说出来的 reasoning 是否真的是它做决策的原因？这是一个不可解问题，但影响 audit 的可信度。

- **Agent 操作后的验证闭环目前是"建议级"。** k8s-gate 在 stderr 提示 VERIFY 命令，CLAUDE.md 规则要求验证。但如果 Claude 忽略了？没有技术强制。一个潜在方向：PostToolUse hook 检查上一个 mutating 命令后是否跟了验证命令，如果没有就提醒。

---

## Concrete Artifacts

### 文件清单（全部可工作）

```
context-infrastructure/
  tools/agent_ops/
    hooks/
      k8s-gate.sh       # PreToolUse: 权限分级 + 危险操作拦截
      audit-log.sh       # PostToolUse: 执行结果记录 (phase: post)
      audit-pre.sh       # PreToolUse: 意图记录 + INTENT 提取 (phase: pre)
    audit-view.py        # CLI 审计查看器 (PRE/POST badge, why 继承, cmd 清洗)
    setup.sh             # 一条命令安装: symlink + patch settings.json
    logs/                # JSONL 审计日志 (gitignored, demo 文件手动 git add -f)
  CLAUDE.md              # K8s Safety 规则 (untrusted input / INTENT / verify)
  .gitignore             # 忽略 logs/*.jsonl
```

### K8s Gate 分级逻辑

| Cluster 类型 | Read | Mutating (apply/scale/create) | Delete 资源 | Delete namespace |
|---|---|---|---|---|
| dev/preprod/demo | 放行 | NOTICE + 弹确认 | 弹确认 | **BLOCK** |
| prod (`*proda/b`) | 放行 | WARNING + 弹确认 | **BLOCK** | **BLOCK** |
| PCI (`keastpci[ab]`) | 放行 | **BLOCK** | **BLOCK** | **BLOCK** |

### INTENT Convention 示例

```bash
# INTENT: 2 pods OOM crashlooping, scaling down to reduce memory pressure
kwestproda scale deploy payments-api --replicas=1 -n payments
```

audit-view.py 输出：
```
[PRE]  why  2 pods OOM crashlooping, scaling down to reduce memory pressure
       cmd  scale deploy payments-api --replicas=1 -n payments

[POST] why  ↳ 2 pods OOM crashlooping, scaling down...  [PRE]
       cmd  scale deploy payments-api --replicas=1 -n payments
       out  deployment.apps/payments-api scaled
```

### 面试 30 秒核心表述

> "我给自己的 SRE 工作流搭了一套 AI agent 安全基础设施。核心思想：**不赌模型永远做对，设计成即使它错了系统依然可控**。三层：Action Boundary（K8s 集群按 dev/prod/PCI 分级，hook 做语义 gate）、Audit Trail（`# INTENT:` convention 把 reasoning 嵌进命令，pre/post pair 捕获完整因果链）、系统约束 > 模型聪明（最后防线永远是 IAM/RBAC，不是 prompt）。"
