# Agent + SRE + 生产级系统：方法论合成

**Date**: 2026-03-30

---

## 一、上层框架：三个同心圆

**内圈：控制论基底。** Agent 工程和 SRE 是同构问题。不可靠组件构建可靠系统，这个命题在分布式系统和 LLM agent 中完全成立。区别仅在于不确定性的来源从系统行为变成了决策过程。

**中圈：工程实现层。** 围绕控制论基底，衍生出三组工程问题：约束设计（怎么限制 agent 的行为空间）、可观测性（怎么看见 agent 的决策过程）、收敛机制（agent 偏航后怎么回正）。

**外圈：产业和个人定位。** Agent 时代的稀缺性在哪里、工程师的价值怎么重新定义、市场处于什么阶段。这一层为内两层提供"为什么现在做这件事"的 context。

这三层不是选择题，是同一个人需要同时具备的三个维度：能设计控制系统（内圈）、能落地工程实现（中圈）、能判断什么值得做（外圈）。


## 二、核心主题

### 主题 1：SRE ↔ Agent 同构

SRE 的本质不是"管理服务器的可靠性"，而是"控制不确定系统的能力"。把这个抽象层级提上来之后，agent 工程就是 SRE 的自然延伸，不是跨界。

具体映射：

| SRE 概念 | Agent 等价物 | 对应关系 |
|-----------|-------------|----------|
| RBAC | Scope Declaration / Allowlist | 限制行为空间 |
| Blast Radius | Authorized 范围限制 | 限制影响面 |
| Audit Log | Execution Log + INTENT convention | 追溯因果 |
| Observability | Reasoning Trace / Decision Rationale | 看见决策过程 |
| SLI/SLO | Task success rate / Convergence time | 定义"好" |
| Error Budget | 容忍偏航的额度 | 何时人工介入 |
| Reconciliation Loop | Agent loop (observe→plan→act→verify) | 持续收敛 |


### 主题 2：Controllability > Capability

市场在追模型能力，但生产系统买单的是可审计、可回放、可中断。

假亮区（agent 自信地错）比暗区（agent 不知道）更危险，因为不触发不确定性信号。控制能力强的系统能在假亮区插入强制确认点；只追求模型能力的系统在假亮区没有防线。

行业数据支撑这个判断：88% 的 agent PoC 失败不在模型层，在系统层（集成、治理、数据质量）。


### 主题 3：三支柱的多种表述

约束、可观测、收敛这三个支柱有不同粒度的表述形式：

| 表述形式 | 适用场景 |
|---------|------|
| 限制它、看见它、让它回正 | 口头沟通 |
| GCORF: Goal / Controllability / Observability / Reversibility / Feedback Loop | 系统设计文档 |
| Action Boundary + Audit Trail + System Constraints > Model Intelligence | 设计哲学陈述 |
| Orchestrator + Worker + Verifier + Human Gate | 垂直场景落地 |

这四种表述本质上在说同一件事，粒度不同，不是互相竞争的框架，是同一个框架的不同视角。

关键修饰语："系统约束 > 模型聪明"。最后防线永远是 IAM/RBAC 这样的硬约束，不是 prompt 或者 guardrail model。


### 主题 4：持久化结构文档作为系统枢纽

Plan File 有三重身份：执行计划 + RBAC Policy + Audit Log。核心论据：context window 会被压缩，文件不会。

Structured Triage Trace 是同一个 pattern 在 oncall 场景的体现，包含 Signal → Routing → Decision Trace → Evidence Chain → Policy → Verifier。把 agent 的推理过程物化成可查询、可审计的持久化文档，这是底层架构需求，不是场景特异的。


### 主题 5：Human Gate 是设计原语

Human Gate 是设计原语，不是补丁。

具体落地：K8s 按集群分级（dev/prod/PCI），不同级别不同 gate 强度。假亮区只能靠人工识别，这是 Human Gate 存在的根本原因。

Human Gate 和 Scope Declaration 看起来矛盾，实际是互补：Scope Declaration 减少噪音（确定性范围内不问），Human Gate 保留信号（不确定或高风险时必须问）。两者组合的效果是"问得少但问得对"。


### 主题 6：评估成为核心工程学科

传统软件中生成贵、验证便宜（写代码贵、跑测试便宜）。AI 系统中生成便宜、评估贵。这个成本关系反转意味着 evaluation design 正在成为和 system design 同等重要的工程学科。

可操作化方向：Verifier 检查的不是答案对不对，而是 evidence chain 完不完整。这回避了"判断 LLM 输出质量"这个近乎不可解的问题，转而检查推理过程的完整性。

行业数据：当前 eval 实践大多是 benchmark + vibe check，有系统化评估框架的组织 agent 生产化成功率高 6 倍。


## 三、张力（未收敛的矛盾）

### 张力 1：架构完备性 vs 个人 ROI

MCP server、OPA policy engine、subagent 分层，架构原则对，但实现复杂度对一个人来说 ROI 不够。务实落地版本是 hooks + INTENT + 集群分级，理想架构是完整的多层 policy engine。两者之间的差距是"当前最小可行"vs"目标终态"，但没有明确的分阶段路径连接两端。

**需要回答：从 sudo + audit log 到完整 policy engine，中间的里程碑是什么？每个里程碑的触发条件是什么？**


### 张力 2：确定性控制机制 vs 非确定性行为

hooks 用正则匹配命令、cluster 按名字分级、RBAC 用命令前缀匹配——这些确定性控制机制假设 agent 的可控性可以通过分析其外部行为（tool calls）来实现。

但自然语言 reasoning 不等于真实因果机制。CoT 可能是事后合理化。INTENT convention 让 agent 说出 reasoning，但说出来的 reasoning 是否真的是它做决策的原因？假亮区的存在意味着 agent 的内部状态（confidence）和外部表现（自信的回答）可能不一致。

这是根本性张力：我们在用确定性工具控制一个内部状态不可观测的概率系统。当前的解法（审计外部行为 + 高风险时强制人工）是可行的工程妥协，但不是理论上完备的。

**这个张力可以接受，但"接受"本身需要量化边界，否则是工程放弃，不是工程决策。** SRE 接受系统不会 100% 可靠，是因为有 error budget 精确定义"多少不可靠可以承受"——error budget 耗尽就停止发布。

agent 工程目前缺少这个等价物。如果 Agent SLO（task success rate + convergence time）定义不出来，张力 2 就不是"接受"，而是"无法评估"：我们甚至不知道当前的控制机制是否足够好。

**结论条件化**：当 Agent SLO 可以量化时，张力 2 进入"工程妥协"阶段（类比 SRE 的 error budget 框架）；当 Agent SLO 仍无法定义时，张力 2 停在"开放问题"状态，不应该被当成已接受的结论来使用。


### 张力 3：框架重要性的矛盾评估

框架选型是不可逆决策，中途迁移 50-80% 代码重写。但框架地位在下降——Tool 层复用框架，Policy 层必须自己设计。LangGraph 的真正价值在状态持久化，不在图结构。

三者不完全矛盾：框架作为 execution layer 确实在降级，但作为 state management layer 仍然重要。迁移成本高说的是现状，框架降级说的是趋势。

实际决策：用 SDK 裸写理解机制，但从第一天就把 state persistence 和 policy 层设计为框架无关。这样即使后来引入框架，核心抽象不需要重写。


### 张力 4：Single-agent vs Multi-agent 的价值边界

90% 的价值在 single-agent + good tools + constraints。但这留下了一个问题：剩下 10% 真正需要 multi-agent 的场景具体是什么？

oncall triage 系统可能正好是那 10%：不同 failure cluster 需要不同领域知识，routing + 专业化 worker + 独立 verifier 的分工有明确价值。

**初步结论：** Multi-agent 的价值在于"角色分离"场景，比如决策者和执行者需要不同的约束（verifier 不应该有 mutating 权限）、不同 domain 需要不同工具集。不是"任务复杂就需要多 agent"，而是"职责需要隔离时才需要多 agent"。


## 四、已收敛结论 vs 待验证假设

### 已收敛

1. **SRE 和 Agent 工程是同构问题**，SRE 经验可以直接迁移而非跨界学习
2. **Controllability > Capability** 是生产级 agent 的设计第一性原理
3. **系统约束 > 模型聪明**：最后防线永远是 IAM/RBAC，不是 prompt
4. **Human Gate 是设计原语**，结合 Scope Declaration 实现"问得少但问得对"
5. **持久化结构文档**（plan file / trace）是 agent 系统的协调枢纽
6. **评估成本反转**：生成便宜，判断贵，evaluation design 成为核心工程学科
7. **INTENT convention** 解决了 audit 只有 what 没有 why 的问题
8. **集群分级 gating**：按"失控成本"分级，不是按 K8s verb 分级

### 待验证假设

**[load-bearing]** = 该假设被证伪会拆穿框架的核心支柱，证伪只影响局部的未标注。

| 假设 | 验证方向 | 权重 |
|------|----------|------|
| Agent SLO 可以用 task success rate + convergence time 定义 | 在真实 agent workload 上测试这两个指标是否有区分度 | **[load-bearing]** 证伪则三支柱中"收敛"支柱失去可度量性，张力 2 的"工程妥协"结论无法成立，整个框架降级为定性框架 |
| Verifier 的 minimum viable 形态是 structured output schema + rule engine | 在 Cluster 4 (histogram skew) 上端到端实现一次 | **[load-bearing]** 证伪则 evidence chain 完整性这个 evaluation 方案无法操作化，主题 6 缺少可落地路径 |
| 从 sudo+audit 到完整 policy engine 存在可行的分阶段路径 | 定义具体里程碑和 exit criteria | **[load-bearing]** 证伪（= 中间路径不存在，必须一步到位）则张力 1 无解，Agent as Code 演进路径失去现实性 |
| Plan file triple identity 在多日跨任务中仍然 work | 在超过 3 天的任务上验证 plan drift 问题 | 局部：证伪只影响持久化文档这个 pattern，不影响三支柱主体 |
| Cognitive Observability 可以扩展 OpenTelemetry 来实现 | 调研 OTel 社区是否有 agent trace 的 proposal | 局部：证伪只影响可观测性支柱的实现路径，不影响其必要性 |
| K8s-native Agent Controller (CRD) 有实际价值 | 评估 vs 简单的 hook chain，复杂度是否 justified | 局部：Phase 3 的实现细节，不影响 Phase 1/2 |
| MCP 供应链安全可以参考 npm/pip 的包签名方案 | OWASP MCP Top 10 刚建立，需要跟踪进展 | 局部：约束设计的一个子问题 |
| Agent 长任务（天级 horizon）需要 Temporal 级别的 durable execution | 评估当前 session 级别的使用场景是否真的需要 | 局部：使用场景相关，大多数当前 workload 不触发 |


## 五、不做什么：Controllability > Capability 的逆命题

Controllability > Capability 这个第一性原理有一个逆命题，需要被显式推导出来：

**如果一个场景的 controllability 成本高于直接人工执行成本，就不应该用 agent。**

不该用 agent 的场景特征：
- 操作序列短（≤3 步），人工执行比设计 agent 行为边界更快
- 失控代价极高且不可逆，而当前 Agent SLO 尚未定义（无法量化"多少失控可以接受"）
- 任务本身的"正确"标准难以形式化：如果 Verifier 无法检查 evidence chain 完整性，agent 的输出质量等于不可评估
- 上下文切换成本极低（人类专家在场，立即可执行）且 agent 的主要价值在于异步/并发，同步场景下价值消失

不该现在投入资源验证的假设：三个 load-bearing 假设（Agent SLO、Verifier MVF、演进路径）优先级最高。以下两个可以推迟：
- Agent 长任务需要 Temporal：当前使用场景集中在 session 级别，优先级不匹配
- CRD-based Agent Controller：Phase 3 的问题，Phase 1 没出 bug 之前验证是过早优化

**与三支柱的关系：** 三支柱说的是"用 agent 时怎么做"，这一节说的是"是否应该用 agent"。决策顺序：先判断场景是否适合 agent，再设计三支柱。


## 六、上层抽象：Agent as Code

### 核心命题

IaC 的本质不是"用代码管服务器"，而是把期望状态声明出来，让自动化去收敛。Agent as Code 是同一个 pattern：把 agent 的行为空间、约束、领域知识声明为可版本控制、可 review、可审计的 spec，agent 本身只是执行这些 spec 的 runtime。

**Agent 不是产品，Spec 才是。** 就像没人说 Terraform binary 是他们的基础设施——HCL 文件才是。

### Spec 的精确定义

**区分标准**：agent 的 control loop 读什么来决定行为？那个东西是 spec。其他的即使在 git 里、即使跟 agent 相关，也不是 spec。

Spec 分三层，按变更频率和硬度递增排列：

**Layer 1 — Identity Spec**（agent 是谁）

`SOUL.md`, `COMMUNICATION.md`, `USER.md`。声明式地定义 agent 的人格、沟通风格、与用户的关系。变更频率极低，跟"你是什么样的人"同频。IaC 等价物：provider configuration。

**Layer 2 — Capability Spec**（agent 能做什么、怎么做）

`rules/skills/*.md`, plan file（执行时生成）。带输入输出契约的 SOP。Skill 介于 Prompt 和 Agent 定义之间。变更频率中等，新 skill 添加或 SOP 更新时改。IaC 等价物：Terraform modules。

**Layer 3 — Constraint Spec**（agent 不能做什么）

hooks (`k8s-gate.sh`, `audit-*.sh`), 集群分级规则, RBAC allowlist, `settings.json` 中的 hook 注册。变更频率低，跟风险模型同频。**这是 spec 中最硬的部分**：Identity spec 影响 agent 的判断倾向，Constraint spec 直接拦截行为。IaC 等价物：Sentinel/OPA policy。

**不是 Spec 的东西：**

| 资产 | 性质 | IaC 类比 | 为什么不是 spec |
|------|------|----------|----------------|
| Memory (`contexts/memory/`) | Runtime state | Terraform state file | 记录 agent 对世界的理解，不定义 agent 应该怎么做 |
| Domain knowledge (axioms, survey results) | Reference material | Runbook | Agent 查阅但不被它驱动 |
| Tools (`tools/` 下的 Python 脚本) | Runtime implementation | Provider plugin 源码 | 工具是执行能力的实现，不是行为的声明 |
| Execution plan (`tmp/` 下的临时 plan file) | Ephemeral artifact | `terraform plan` 输出 | 一次性的，用完即弃 |

### Spec 与 Prompt 的关系

当一个 Claude Code session 启动时，它加载 CLAUDE.md → 读 SOUL.md → 读 USER.md → 读 WORKSPACE.md → 读 skills/INDEX.md。Claude 实际看到的 prompt 是这些 spec 文件编译后的结果。

- Spec 文件是 source of truth（`.tf` 文件）
- Prompt 是 compiled artifact（`terraform plan` 输出）

Prompt 是 spec 的一种退化形态。当没有显式的 spec 文件时，prompt 同时承担了 source 和 compiled artifact 两个角色，改动缺乏结构保障。Agent as Code 的工程主张是把这两层分开。

这也解释了 prompt engineering 为什么感觉脆弱：你在编辑编译产物而不是源文件。

### IaC ↔ Agent as Code 映射

| Infrastructure as Code | Agent as Code |
|---|---|
| Terraform HCL 声明期望状态 | Spec 文件（三层）声明 agent 的身份、能力、约束 |
| Provider configuration | Identity Spec (SOUL.md, USER.md) |
| Terraform modules | Capability Spec (skills/*.md) |
| Policy as Code (OPA/Sentinel) | Constraint Spec (hooks, 集群分级 gating) |
| State file | Memory (contexts/memory/) |
| `terraform plan` 输出 | Prompt（spec 编译后的产物） |
| Plan → Apply → State file | Plan file triple identity（执行计划 + RBAC + Audit） |
| `terraform plan` 先看 diff 再执行 | Human Gate：先审再做 |
| State drift detection | Agent 偏航检测 + reconciliation loop |
| Version controlled, reviewable | 所有 spec 进 git，可 review、可回滚 |

### 演进路径

**张力 1（架构完备性 vs 个人 ROI）** 通过分阶段演进化解：

- **Phase 0**：领域知识在对话里，每次重说（= 手动 SSH 改配置）
- **Phase 1**：hooks + INTENT + CLAUDE.md（= shell scripts + cron）——**当前阶段**
- **Phase 2**：结构化 spec 文件 + scope-gate.py（= Chef/Ansible，声明式但不完全 declarative）
- **Phase 3**：CRD-based Agent Controller，spec 驱动 reconciliation（= Terraform/K8s operator）

每个 phase 的 exit criteria 不是"架构不够好"，而是"当前 spec 管理方式开始出 bug 了"——跟 IaC 演进的触发条件一致。

**张力 3（框架选型）** 通过 Spec 与 Runtime 分离化解。如果 spec 是核心资产，框架只是 runtime，那框架选型降级为实现细节。Spec 是 portable 的，换 runtime 不需要重写 spec。"裸写理解机制"和"迁移代价高"不再矛盾——迁移的是 runtime，不是 spec。

### 与三支柱的关系

三支柱（约束、可观测、收敛）描述的是 agent 可靠性的**机制**。Agent as Code 描述的是这些机制的**交付形态**。三支柱回答"可靠的 agent 需要什么"，Agent as Code 回答"这些东西以什么形式存在和演进"。


## 七、下一步行动

1. **选定 canonical 三支柱表述**。四种表述服务不同场景，对外沟通需要一个主版本。建议用"限制它、看见它、让它回正"作为口头版，GCORF 作为设计文档版。

2. **验证 Cluster 4 端到端 demo**。histogram skew 这个 cluster 可以用 Grafana/VM MCP 跑通全链路，这是把理论变成可展示 demo 的最快路径。

3. **定义 Agent as Code 演进路径的 Phase 1→2 边界**。当前 hooks + INTENT + CLAUDE.md 是 Phase 1。明确什么信号触发向 Phase 2 迁移——可能是：spec 散落在多个文件导致不一致、或者 hook chain 的组合爆炸开始出 bug。

4. **跟踪 Agent SLO 和 Cognitive Observability 的社区进展**。这两个是待验证假设中最可能影响长期方向的。
