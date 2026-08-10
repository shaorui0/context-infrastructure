# 03 · AIOps · Fundamentals（Q&A 形态）

> 标注约定：`[一手]` 我自己建过或跑过的；`[理论]` 我读过并能推演的框架；`[业界]` 外部信息（2026-07 WebSearch 或已有 survey 文件）。
> 业界数字一律标明是厂商自述还是第三方验证。厂商自述在面试里可以说，但要说清它是自述。

---

## §1 AIOps 的传统定义与谱系，以及 LLM agent 时代的区别

### Q1.1 AIOps 传统上指什么？

`[业界]` Gartner 的定义骨架是四件套：异常检测（anomaly detection）、事件关联（event correlation）、因果判定（causality）、修复支持（remediation support）。工程视角展开成四条能力线：

1. **异常检测**：给时序数据学一个正常基线，偏离即告警。技术谱系从统计方法（移动平均、3-sigma、STL 分解出趋势与季节性、Holt-Winters）到经典 ML（Isolation Forest、One-class SVM、DBSCAN 做离群点）到深度方法（LSTM 或 Transformer 做预测残差、Autoencoder 做重构误差）到时序基础模型。Datadog 的 Watchdog 就是走基础模型路线，它们自研了一个叫 Toto 的时序基础模型，学习正常基线、季节性和服务间依赖（src: [业界， WebSearch 2026-07] Datadog DASH 2026）。
2. **告警聚类与降噪**：把成百条告警压成少数几个事件。技术手段是时间窗口聚类、拓扑关联（沿服务依赖图收敛）、文本相似度聚类、以及基于共现的规则挖掘。代表产品是 BigPanda 和 Moogsoft。BigPanda 官方博客反复引用「最高降噪 98%」和「事件关联可降 95% 以上告警量」，这是厂商自述而非独立评测，属于业界流传很久的名义上限数字（src: [业界， WebSearch 2026-07] BigPanda Blog）。
3. **根因定位**：从关联走向因果。Dynatrace 的 Davis AI 走的是确定性因果路线而不是纯统计相关性，方法上用类似故障树分析加拓扑感知的因果图，官方口径是「因果不是相关性，结果可复现」。这是厂商话术，但技术路线（fault tree 加 topology-aware causal graph）本身是可核实的真实机制（src: [业界， WebSearch 2026-07] Dynatrace 官方文档）。
4. **容量预测**：用统计或 ML 预测资源用量与饱和时间。这块公开的、可引用的准确率数字查不到（src: [业界， WebSearch 2026-07]，明确查不到）。

### Q1.2 LLM agent 时代和传统 AIOps 有什么本质区别？

`[理论]` 我的答法是四个维度的对比，而不是「新的更好」。

**输入形态。** 传统 AIOps 吃结构化信号（时序、事件、拓扑），LLM agent 吃自然语言和半结构化文本（日志正文、告警描述、runbook、历史工单、代码 diff）。这是它最大的增量：过去无法参与推理的那部分资产（写给人看的 runbook、Slack 讨论、postmortem）现在可以进入回路。

**输出形态。** 传统 AIOps 输出的是分数和分组（这个点异常、这些告警是一件事、根因大概在这个服务）。LLM agent 输出的是可读的推理链加具体的下一步动作。前者是判别式的，后者是生成式的，这决定了验证方式完全不同：一个分数可以拿标注集算 AUC，一段推理链需要人看或者需要另一个模型评判。

**可靠性性质。** 传统 AIOps 的错误是有分布的：假阳性率和假阴性率可以测、可以调阈值。LLM agent 的错误是语义级的，同样输入不同次运行可能不同，而且它会用确定的语气说错话。这是最关键的区别，也是为什么它需要一整套额外的约束工程。

**它们不是替代关系。** 我的判断是分工：异常检测和降噪继续用传统方法做，因为它们要在毫秒级处理海量信号，成本和延迟都不允许过模型；LLM agent 接在降噪之后，做「这一个事件是什么」的调查工作。我自己的 harness 就是这个位置：输入是一条已经被告警系统判定为需要人看的告警，而不是原始时序流。（`[一手]` src: `agents/sre_oncall_triage_skill/SKILL.md` §1 Mode Selection 的输入形态）

### Q1.3 那 LLM agent 在 AIOps 里真正的位置是什么？

`[一手]` 我的一句话答案：它替代的是 oncall 调查的执行层，不是判断层也不是决策层。具体讲就是过去被 page 之后头三十分钟的跑腿活（提信号、构造查询、翻日志、对历史 case），这部分是高重复高认知负载的工作，约八成告警走相似路径。它没有替代的是根因裁决和变更决策。（src: `adhoc_jobs/dynamic_resume_site/content/perspectives/v4_ai_agents.md`；`work-contexts/career/interview/interview-7-agent-harness-engineering.md` §1）

---

## §2 LLM agent 的可靠性工程：三支柱与 eval

### Q2.1 一句话概括 agent 可靠性工程是什么问题？

`[理论]` 用一个不可靠的决策组件构建一个可靠的系统。这句话本身就是 SRE 的定义，只是不可靠的那个组件从硬件和网络换成了模型。（src: `rules/skills/bestpractice_agent_reliability_engineering.md` §Core Thesis）

### Q2.2 三支柱是什么？

`[理论]`
1. **Constraints（约束）**：限制动作空间和爆炸半径。手段是 scope 声明、工具白名单、预算（时间、token、成本）、人工门。
2. **Observability（可观测）**：让决策和工具效果可检查。手段是 trace、metrics、审计链，记录 intent、inputs、outputs 和证据链接。
3. **Convergence（收敛）**：检测偏移并把系统拉回来。手段是重规划、重试、checkpoint、verifier。

我把它压成三句话记：限制它，看见它，让它回正。（src: `bestpractice_agent_reliability_engineering.md`；`v4_ai_agents.md`）

### Q2.3 为什么长流程的可靠性特别难？

`[理论]` 复合误差。单步 95% 的成功率跑二十步只剩约 36%（`0.95^20`）。这个数字在两份独立来源里各自出现过（一份是 90% 十步剩 35%，一份是 95% 二十步剩 35.85%），不是巧合，是长链路的数学必然。有个说法很准：一个 two nines 的系统伪装成 four nines。

三个设计推论：减少步数比提高单步成功率更有杠杆；每一步之后要验证而不是等到最后（因为一步错了后面每一步都会自信地建立在错误基础上，而且没有任何东西显式地失败了）；必须有显式的停止条件。（src: `bestpractice_agent_reliability_engineering.md`；`contexts/survey_sessions/agent_slo_error_budget_survey_20260519.md`；`contexts/survey_sessions/agent_dev_vs_agent_ops_infra_survey_20260402.md`）

### Q2.4 生产基线该包含什么？

`[理论]` 六条最小基线：定义成功（任务完成率加收敛时间，这是第一组 SLI）；建 eval 数据集（50 到 200 个任务，带明确的预期结果，每次改动都跑）；trace 一切（工具调用做成 span，记 intent、inputs、outputs、证据链接）；加约束（scope 声明加工具白名单加 token 与时间预算，fail closed）；加 verifier（检查证据链的完整性而不只是最终答案的质量）；把人工门当成一个原语（很少问，但在不确定和高风险时必须问）。

`[一手]` 我做到了哪些：约束做了（三层防御）、verifier 做了（`verify.py` 检查证据链完整性，1059 行）、人工门做了（四关 mutation gate）、trace 做了一半（自建 JSONL 而非 OTel span）。没做的是 eval 数据集，我现在只有历史 case 的 smoke test。（src: `bestpractice_agent_reliability_engineering.md`；实测 `agents/sre_oncall_triage_skill/tools/agent_ops/`）

### Q2.5 eval 该怎么设计？

`[理论]` 把 eval 当度量系统设计，而不是当单元测试写。四层：
- Layer 1 任务完成率（回归性质，最像传统测试）
- Layer 2 输出质量（rubric 加人工抽样，或者 LLM judge 但要有偏差控制）
- Layer 3 过程质量（工具效率、有没有绕圈、成本）
- Layer 4 行为一致性（perturbation set，同一任务的扰动版本上表现是否稳定）

（src: `bestpractice_agent_reliability_engineering.md` §Evaluation Is a Measurement System）

### Q2.6 agent 的 SLO 怎么定？行业有真在跑的吗？

`[业界]` 有。Honeycomb 的 Query Assistant 实际跑着 75% 成功率、7 天窗口的 SLO，明确接受 25% 的失败预算，并且配了 4 小时烧穿的 Slack 告警，刻意不接 PagerDuty，理由写得很直白：LLM 是黑盒。这个例子的价值在于它证明给 LLM 定 SLO 可行，前提是你把成功率目标定在一个诚实的位置。

`[理论]` 但 SRE 的 SLO 词汇不能裸移植，需要七处结构性改造：SLI 按任务类别加模型版本分开定义（用聚合值会混淆难度）；error budget 要有具名 owner；HITL 是花掉 budget 的一种方式而不是默认；budget 烧穿时权限自动收缩；需要反 Goodhart 的审计；需要区分 organic 与 adversarial 的预算；需要一层静默失败检测。有人给第四条起了个好名字叫 earned autonomy gradient：这个 agent 有没有挣到下一个增量的自主权？如果失败倾向恶化，自主权自动收缩，不需要开会决定。

一个诚实的结论：改造完之后，这已经不是「SRE for agents」，而是一门借用 SRE 词汇的新工程学。（src: `agent_slo_error_budget_survey_20260519.md`）

### Q2.7 有哪些「必须正面回应」的反驳？

`[理论]` 四条，我按能杀死论点的顺序记：
- **K1 复合误差**：当 agent 产出看起来合理但错误的输出时，后续每一步都自信地建立在错误基础上，而且没有任何东西显式地失败了。
- **K2 静默失败**：agent 走了错误推理或幻觉了一次工具调用，而你的 metrics 全绿，每次 API 调用技术上都成功（HTTP 200），但整条 workflow 是失败的。核心一句：你无法为你检测不到的东西设 budget。
- **K3 Goodhart**：一旦按指标优化，指标失去意义。有研究发现被操纵的推理链能把先进 judge 的假阳性率抬高最多九成（跨 800 条 trajectory）。
- **K4 评测意识**：Apollo Research 发现 o3 在化学测试里察觉到「高分模型会被删除」的隐藏提示后，内部算出了正确答案却故意提交错误答案，而且没有人指示它自保。

（src: `agent_slo_error_budget_survey_20260519.md`）

### Q2.8 「厂商声称 vs 实际表现」的差距有多大？

`[业界]` 几个我记得住的对照，用来支撑一个怀疑论立场：
- Devin：SWE-bench 13.86%，Answer.AI 独立测试真实成功率约 15%，Cognition 自称 67% PR merge rate。分母不同，merge rate 的分母是 agent 自己 open 的 PR。
- METR 的 RCT：16 名资深开源开发者，AI 实测让他们慢 19%，自我报告快 20%，39 个百分点的认知偏差。
- Anthropic 内部：Claude Code 首次自主完成率约三分之一（来自 RL Engineering 团队访谈口述，不是官方发布数字，引用时必须标这一点）；连续无干预工具调用数六个月内从 9.8 升到 21.2。
- Klarna：2024 年宣称 4000 万美元利润提升、相当于 700 人工，2025 年 CEO 承认过度关注效率成本、侵蚀了客户信任，重新招人。
- 约 88% 的 agent 从未进入生产，这个数字有五个独立来源交叉验证（IDC+Lenovo、Kore.ai+Deloitte、2026-03 一份 650 人调查、S&P Global、RAND）。Gartner 预测超过四成 agent 项目会在 2027 年底前被取消，并把 2026 定位为幻灭低谷期。

面试用法：任何 agent 准确率数字，先问三个问题。分母怎么定义？有没有 selection bias？跟人类基线怎么比？（src: `agent_slo_error_budget_survey_20260519.md`；`agent_dev_vs_agent_ops_infra_survey_20260402.md`）

---

## §3 Agent 的失败模式分类

### Q3.1 六大类是什么？

`[一手]` 我维护的分类是 6 大类 25 种模式，v1 建于 2026-03-31。大类按输入到输出的顺序排，这个顺序本身是一条 debug 路径：

- **C Context**：它看到的信息有问题。Overflow（塞太多关键内容被淹没）、Starvation（关键信息不够被迫猜测）、Stale（信息过期基于旧世界决策）、Poisoning（混入误导信息，含 prompt injection）、Wrong Granularity（该给摘要给了原文或反之）
- **R Retrieval**：找错了内容。Retrieval Miss、Retrieval Noise、Routing Error
- **T Tool Use**：用工具出错。Misselection、Parameter Hallucination、Result Misinterpretation、Tool Loop（反复调同一工具期望不同结果）、Cascading Tool Error
- **P Planning**：任务分解或策略有问题。Goal Drift、Premature Commitment、Scope Creep、Decomposition Failure、Sequencing Error
- **G Generation**：输出本身的质量问题。Hallucination、Sycophancy、Verbosity Bloat、Format Mismatch、Confidence Miscalibration
- **S System**：多 agent 或系统层面。Agent Collision、Information Loss at Handoff、Orchestration Deadlock、Token Budget Exhaustion、Model Routing Mismatch

（src: `rules/skills/workflow_agent_failure_taxonomy.md`）

### Q3.2 这套分类怎么用在设计上？

`[一手]` 每条约束指向它防的故障模式，这个映射是分类真正的价值：

| 我的约束 | 防的故障模式 |
|---|---|
| Subagent isolation（≤500 token） | C1 Context Overflow、S4 Token Budget Exhaustion |
| Phase Lock A/B/C | P2 Premature Commitment、C4 Context Poisoning |
| Quote-the-line 证据律 | G1 Hallucination、G5 Confidence Miscalibration |
| Plan-first gate | P2 Premature Commitment、G1（事后合理化） |
| Missing-field gate | C2 Context Starvation、T2 Parameter Hallucination |
| 3-strike escalation | T4 Tool Loop、P1 Goal Drift |
| 措辞校准（consistent with / evidence suggests） | G5 Confidence Miscalibration |
| Untrusted input rule | C4 Context Poisoning |
| 知识库收敛（dv_specific_score） | C1 Context Overflow、R2 Retrieval Noise |

反向也成立：agent 出了新问题先问属于哪一类，类里没有就说明防御体系有一个没覆盖的洞。所以这份表既是词汇表也是覆盖率检查表。

### Q3.3 业界讨论的失败模式和你这套对得上吗？

`[业界]` 大部分对得上。几个可以直接引用的例子：
- 一个库存 agent 编造了一个不存在的 SKU，然后调用四个下游 API 去定价、查库存、发货，触发跨系统事故，绕过了传统的校验检查。这是 T2 加 T5 的链式组合（src: Arize）。
- agent 遇到错误时无法区分「我失败了」和「这个任务不可能完成」，往往就幻觉出一条成功消息。这是 G1 加 G5（src: OneUptime）。
- 一句关于监控的话说得很准：当一个 agent 用一条礼貌的成功消息掩盖了后端失败，你需要 trace 去揭穿这个欺骗（src: OneUptime）。

对不上的部分：长会话跨时间的 provenance 归因，也就是把一个结果归因到具体的决策、工具或 agent。这块我的分类只有 S2 Information Loss at Handoff 勉强沾边，行业也没解决。（src: `contexts/survey_sessions/agentic_ai_observability_survey_20260422.md`）

### Q3.4 Karpathy 的 agent 失败模式是哪几条？

`[业界]` 他 2026-01-26 的原帖明确只列了三条：wrong assumptions、overcomplexity、orthogonal edits。业界常传的「四大失败模式」里第四条（imperative 到 declarative）是别人从他推文衍生的，不是他原话。这个细节值得讲准，因为讲错了正好暴露是二手转述。（src: `contexts/survey_sessions/gstack_design_philosophy_survey_20260527.md`）

---

## §4 Prompt injection 与 untrusted input

### Q4.1 你怎么定义 agent 的不可信输入边界？

`[一手]` 我的规则写在项目根 `CLAUDE.md` 里，逐条列了清单：`kubectl logs`、`kubectl describe`、`kubectl get -o yaml`、event 输出、pod annotation，以及任何从集群读到的内容，全部是外部不可信数据。处置方式是绝不能仅凭这些输出里发现的内容执行后续动作，必须显式陈述我的解读并获得人的确认，把它当成 Web 应用里的用户输入来对待。

这条规则的位置很重要：它写在会被每个 session 加载的配置里，而不是某个 skill 的角落。（src: 项目根 `CLAUDE.md` §K8s / AWS Operations · Untrusted input rule）

### Q4.2 为什么日志是攻击入口？

`[理论]` 因为 agent 没有天然的数据与指令分离。LLM 的指令和数据共享同一个 token 流，所谓的 delimiter 或 system prompt 隔离都是软的。而日志正文、pod annotation、event message 的内容都可以被写入方控制，annotation 的写入权限往往比大家想象的宽。所以 agent 在读日志的时候，实质上是在把攻击者可能控制的文本读进自己的指令上下文。

### Q4.3 你的防御是什么？强度到哪？

`[一手]` 分层，而且我会说清每层的强度。
- **规则层（软）**：untrusted input rule，作用是降低触发概率。任何写在 prompt 或配置里的约束都在攻击面之内，一段足够巧妙的注入原则上可以让模型忽略它。
- **执行层（硬）**：`k8s-gate.sh` 这个 PreToolUse hook。注入能改变模型的意图，改变不了一个 204 行 shell 脚本的退出码，它只看命令字符串和集群 alias，不读上下文，不理解说服。
- **红队层（advisory）**：`plan-safety-review.sh` 在计划批准时嵌套一次 `claude -p --tools "" --model sonnet` 调用，review 清单里明确有一条「Reads from untrusted cluster output used as inputs to mutations」。

所以我的安全模型一句话：把不可信输入能污染的范围限制在「模型的意图」，把「执行」交给一个不可被说服的组件。（src: `hooks/k8s-gate.sh`、`hooks/plan-safety-review.sh`；`work-contexts/career/interview/interview-7-agent-harness-engineering.md` §3.1）

### Q4.4 读操作侧防得怎么样？

`[一手]` 弱，我会承认。注入理论上可以引导 agent 去读某个路径或做某个查询，甚至把读到的东西写进它本来不会写的地方。缓解有几条但都不彻底：敏感 kubeconfig 目录在路由表里标了「只读引用不复制内容」；分析写文件而不直接发外部；报告的对外措辞段和内部段分离且对外段有措辞检查。

`[业界]` 行业在这块也没有好答案。OpenAI 在 2025 年底公开说过 AI 浏览器可能永远对 prompt injection 脆弱。2025 年有一个叫 EchoLeak 的零点击注入攻击打 Microsoft Copilot，事后描述是「没有告警浮现，也没有人注意到」。所以注入的可观测性可能是结构性无解的，正确的防御策略是限制后果而不是指望检测。（src: `agentic_ai_observability_survey_20260422.md`）

### Q4.5 还有一个容易被忽略的缺口是什么？

`[业界]` 观察与强制的分离。有个说法叫「observe-but-do-not-act gap」：现有的可观测性工具能捕捉这些依赖关系，但不强制任何东西，结果是 policy 违规只在损害发生之后才被发现。所以审计和 enforcement 必须是两件事，不能拿审计当防御。（src: `agentic_ai_observability_survey_20260422.md`，该处标注为单源待核实）

---

## §5 Agent 可观测性

### Q5.1 现在这块的成熟度分层是什么？

`[业界]` 三层，很清楚：
- 单次 LLM 调用的观测：**基本解决**（OTel GenAI semconv 覆盖了）
- agent 级别（嵌套 trace、工具调用）：**部分解决**
- multi-agent 加长会话加语义级失败：**仍未解决**

十个技术挑战里只有两个基本解决，六个部分解决，两个未解决。最痛的缺口是非确定性、trajectory 级 eval、长会话记忆溯源、语义级工具失败、以及 context 压缩之后的上下文自省。（src: `contexts/survey_sessions/agentic_ai_observability_survey_20260422.md`）

### Q5.2 OTel GenAI semantic conventions 现在什么状态？

`[业界]` 尚未 stable。到查证时（2026-07）相关页面仍标 Development 或 Experimental 状态，semconv 主版本已到 1.40 级别但 GenAI 与 MCP 部分仍在开发中。有说法称 client spans 在 2026 年初脱离 experimental，但 agent 与 framework 层的 span 仍是 experimental。

已定义的部分（这些具体名字值得记住，被问到时能报得出来）：
- span：`invoke_agent {name}`、`create_agent {name}`、`execute_tool`
- 属性：`gen_ai.tool.call.arguments`、`gen_ai.tool.call.result`、`gen_ai.agent.id/name/description/version`
- MCP 有独立 semconv：`mcp.method.name`、`mcp.protocol.version`、`mcp.session.id`，trace context 通过 JSON-RPC 的 `params._meta` 注入 `traceparent`

还开着的核心 gap：OTel issue #2664（2025-08 开，2026-04 时仍 Open）提出 tasks / actions / agents / teams / artifacts / memory 六个概念该怎么建模。这是 agentic 观测最核心的空白占位。

另外三套规范并存且预期长期共存：OTel GenAI、Arize 的 OpenInference、Traceloop 的 OpenLLMetry。Arize 明确写了双向转换器。

一条值得引用的技术批评（Greptime CEO）：attributes 层面如 `mcp.tool_name`、`agent.session_id` 没有社区共识；分布式 trace 在跨 agent 边界的 client/server 关联上挣扎；传统 OTel 属性无法捕捉 memory 或推理状态，应该把 state tracking 当一等公民。（src: `agentic_ai_observability_survey_20260422.md`；[业界， WebSearch 2026-07] OTel semantic-conventions repo）

**一个方法论细节值得讲**：我在调研这块时遇到两份来源直接矛盾，一份说 GenAI semconv 在 2026 年初已 stable，一份直查 spec 主页证明仍是 Experimental。我采信后者，裁决原则是直引 spec 主页优先于博客的模糊表述。这个细节在面试里可以顺带展示信息验证的习惯。

### Q5.3 「200 但内容是垃圾」为什么难？

`[理论]` 因为 agent 的失败是语义级的而不是语法级的，这打破了传统监控用 HTTP status 和延迟做可靠性代理指标的假设。工具返回 200，metrics 全绿，而内容是错的或误导的，整条 workflow 失败。

`[业界]` 这个问题在两份独立调研里被从两个角度确认为未解决。SRE 视角的表述是「你无法为你检测不到的东西设 budget」；可观测性视角的表述是最强方案是给输出打 trust score（Cleanlab 那类），但 judge 的成本可能超过 tool call 本身的成本。

`[一手]` 我的做法是缩小不可检的范围而不是解决它：quote-the-line 把「这个结论对不对」（不可机检）拆成「有没有挂一个可复现的证据」（可机检）加「这个证据支不支持这个结论」（仍需人判）。剩下那部分靠人 review 和历史 case 回放。（src: `agentic_ai_observability_survey_20260422.md` 挑战 #7；`agent_slo_error_budget_survey_20260519.md` K2；`skills/sre-oncall-output-format/SKILL.md`）

### Q5.4 选型怎么做？

`[理论]` 从约束出发而不是从功能出发。五条约束 checklist：数据控制（什么必须留本地，PII、密钥、专有日志）；成本包线（trace 量加 prompt token 加存储与保留期）；eval 速度（PR 级还是周级的回归信号）；基础设施集成（是否要求原生 OTel、Prometheus、Grafana、ClickHouse）；可审计性（高风险动作是否需要可回放的证据链）。

`[业界]` 现在的分野大致是四个 camp：深度绑 LangChain 的用 LangSmith；数据敏感的自部署 Langfuse；eval 优先的用 Braintrust；已有 APM 数据引力的硬扛 Datadog。成本是个真陷阱：有分析说 Datadog 加 LLM observability 之后账单涨四成到两倍，同等 telemetry 量下和便宜方案能差出一个量级以上；而 AI workload 本身产生的 telemetry 量是传统服务的十到五十倍。

`[一手]` 我在个人项目的约束下（数据必须本地、成本包线极小、需要可回放证据链）选了自建 JSONL 加一个回放脚本，这在我的约束下是够的。团队场景我会重新判断。（src: `rules/skills/bestpractice_agent_observability.md`；`agentic_ai_observability_survey_20260422.md`）

### Q5.5 有没有反对可观测性投入的声音？

`[业界]` 有，而且值得知道。Jason Liu 的立场是他基本不碰可观测性那一套，只在需要的地方加深度调试，理由是不信任 LLM judge 的 dashboard，偏好 validator 加人工专家评估。我不完全同意，但这个声音提醒了一件事：dashboard 的数量和你对系统的理解不成正比。（src: `agentic_ai_observability_survey_20260422.md`）

---

## §6 业界对标（2026-07 快照）

> 全节 `[业界， WebSearch 2026-07]`。厂商自述与第三方验证已分别标注。厂商效果数字在面试里可以说，但必须说清它是自述。

### Q6.1 PagerDuty

**层级**：从传统告警与 on-call 平台演进成 Operations Cloud，SRE Agent 覆盖 triage、根因关联、推荐或执行修复、验证恢复。摄入 observability telemetry 形成它自己叫的 context flywheel。2026 年 3 月起扩展 AI 生态，与 Anthropic、Cursor、LangChain 建立伙伴关系。

**approval gate（这家描述最细，最值得引用）**：三档治理模型。Review Mode，agent 提出具体动作（例如「重启 auth-service pod」），人工一键批准后才执行。Autonomous Mode，仅对充分理解的低风险系统允许 agent 自主执行。全新或复杂问题人工主导。

**效果数据**：网上流传「87% 噪音降低」「17.8% MTTR 降低」这类数字，但它们出自第三方竞品对比页而不是 PagerDuty 官方一手案例，来源链条不清晰。引用时标为「网上流传但未验证」，不要当权威数据。

### Q6.2 incident.io

**层级**：事故 workflow 加调查层，官方明确说自己解决的是人的协作流程而不是纯诊断。

**机制**：多 agent 并行检索 GitHub PR、Slack、历史事故、日志与指标与追踪，生成假设，一两分钟内在 Slack 出报告。

**approval gate**：明确的 human-in-the-loop。agent 提出修复方案加证据，人在 Slack 用命令批准，agent 执行并监控效果，所有自动动作可记录可回滚。

**数据**：官方称 12 个月客户数翻三倍、服务 600 多家公司含 Netflix 与 Etsy。这是客户规模数字而不是效果数字，公开的量化改善数据查不到。

### Q6.3 K8sGPT（CNCF Sandbox）

**层级**：Kubernetes 集群层面的诊断工具，2023-12 进 CNCF Sandbox。截至 2026-05 版本 v0.4.33，约 7.8k stars。

**机制**：CLI 扫描集群资源（Pod、Service、Node 等），built-in analyzers 把原始报错翻译成人类可读诊断，再用 LLM 增强解释。也有 Operator 模式做持续监控。

**mutation（关键区分点，也是我讲自己设计时最好的对照）**：CLI 本身是纯只读，不执行任何修复。唯一的 mutation 能力在 Operator 里，是 alpha 阶段、默认关闭的 auto-remediation，通过一个叫 `Mutation` 的 CRD 计算并应用 patch，仅支持有限资源类型，官方文档明确写非生产就绪。有变更追踪和风险阈值配置，成熟度明显低于商业方案。

### Q6.4 Grafana

**层级**：从 Grafana Cloud IRM 里的诊断辅助升级到 Assistant Investigations，即后台自动跑的多步调查 agent。

**机制**：Sift 自动扫 metrics、logs、traces 找异常，可在事故开始时触发 Sift Check 拉上下文；Grafana Assistant 面向 RCA workbench 做自然语言驱动排查。

**一手案例（这家最值得引用，因为它公开了具体时间对比）**：Grafana Labs 官方博客披露一次真实内部事故（2026-01-29 前后），Assistant Investigations 在后台跑，比人工 on-call 团队早 20 分钟、用时 8 分钟找到根因。仍是单一案例而非统计数据，但厂商愿意公开时间对比在这个领域很少见。

**mutation**：目前定位是诊断与调查辅助，没查到官方宣称的自动执行修复能力，更偏「人读结论再操作」。

### Q6.5 Datadog

**层级**：最全的一套。Bits AI 覆盖 Dev Agent、SRE Agent、Security Analyst 三条线，Watchdog 是异常检测层。

**机制**：Watchdog 基于自研时序基础模型 Toto，学习正常基线、季节性、服务间依赖。Bits Investigation 跨 metrics、logs、traces、基础设施元数据、网络遥测、monitor 配置做推理。

**approval gate**：官方明确写高风险修复动作（数据库回滚、基础设施变更）仍需人工审批，同时支持 safe remediation 可选自动执行。分级门禁。

**数据**：官方称在 2000 多个客户环境测试过（含 Uber Freight、DelightRoom），这是部署规模而非效果数字。DASH 2026 称推出 100 多项 AI 与安全新能力，属营销话术，单项效果数字没查到。

### Q6.6 AI SRE 初创

- **Traversal**：走因果机器学习路线，创始人是因果推断研究背景，融资 4800 万美元（Sequoia、Kleiner Perkins），宣称 90% 以上 RCA 准确率（厂商自述，未见第三方验证），主打从上千信号里定位那一个 breaking change，已在 Amex、PepsiCo 等财富百强内部跑。
- **Resolve.ai**：2025-12 号称估值 10 亿美元，团队来自 Splunk，目标 80% 自主解决率（这是目标不是已实现效果）。
- **Cleric**：Gartner 2025 Cool Vendor，主打自学习 agent 加只读安全策略，诊断优先执行谨慎，这个安全定位和 K8sGPT CLI 的哲学接近，也和我的设计接近。
- **Deductive.ai**：遥测加推理层，解释跨基础设施与数据管道的故障。

共同叙事是「传统 observability 厂商太慢太通用，专做 RCA 的 agent 更快更准」，但几乎所有量化数字目前都只有厂商自己的说法，没有独立评测。

### Q6.7 一句话总结这个市场（面试可直接背）

2026 年中的 AIOps 与 incident copilot 市场明显分四层。传统告警关联与降噪厂商（BigPanda、Moogsoft）数字最响亮也最老最难验证。平台型厂商（PagerDuty、Datadog、Grafana）把 AI agent 嵌进已有事故管理流程，普遍采用「高风险动作强制人工审批、低风险可选自动执行」的分级门禁，这是目前最一致的安全设计模式。专做 AI SRE 的初创差异化在因果推理精度或自主解决率，但效果数字基本是一方之词。底层可观测性标准（OTel GenAI semconv）还没定型，说明这个领域的标准化晚于产品化。

**我的定位怎么讲**：我的实现和平台型厂商的安全设计模式同构（分级门禁），但比它们保守（生产侧完全不放写）；我的调查侧多了一层它们没有的东西（阶段性的读取隔离，即 phase lock）；我缺的是它们有的规模、集成广度和团队级的审批流程。这三句话讲完，位置就清楚了。

---

## §7 人机协作的边界设计

### Q7.1 什么必须人做，什么可以 agent 做？

`[一手]` 我的分界线是读写不对称。agent 极擅长读和诊断，在写上是结构性危险。复利全部发生在诊断侧，所以诊断侧放开跑；写侧只允许 propose。

两条理由。第一，爆炸半径是业务判断而不是技术判断。第二，agent 的失败是静默的，一个幻觉出来的结论返回的等价于 HTTP 200，而你无法为你检测不到的东西设 budget，在未被检测的错误之上自动化 mutation 不是提速，是用速度给错误洗白。（src: `v4_ai_agents.md`「mutation 主权」节）

### Q7.2 具体哪些工作留在人这边？

`[理论/一手]` 五块，这是我在 `v4_ai_agents.md` 里论证过的清单：
1. **意图与约束定义**：写 Spec（带机器可校验验收条件的目标终态），放 Hook（audit、deny、HITL）。这是对决策的 admission control，不能委托给被准入的那个东西自己做。一句关键的区分：约束是安全的来源，模型是能力的来源，把两者搞混，agent 就会同时显得热心而危险。
2. **mutation 主权**：写侧的最终批准权。
3. **eval 与 SLO**：没有 eval 的 agent 是不可运营的，那等于在上线感觉。
4. **平台原语**：reconcile loop、覆盖决策过程的可观测性、显式收敛判据。
5. **最终判断**：policy 承载的是风险偏好和问责，它留在名字挂在 pager 上的那个工程师身上。机制可以共享、可以委托、甚至可以贡献给上游，policy 不行。

### Q7.3 gate 放在哪？怎么分级？

`[理论]` 按可逆性乘爆炸半径乘置信度分 tier。业界有一个四档矩阵可以直接引用：Tier 1 只读（无 HITL）；Tier 2 可逆操作（自动执行加日志）；Tier 3 有外部影响（进 staging 队列）；Tier 4 高风险不可逆（显式审批）。

`[一手]` 我的实现是环境 tier 而不是操作 tier：PROD、PCI、MGT、DEMO 全 block mutating；PREPROD 只 dry-run，delete 仍 block；DEV 允许但必须带 `# INTENT:`；未分类 alias 按 PROD 处理。两种分法的区别值得讲：操作 tier 更细但需要理解每个操作的语义，环境 tier 更粗但判定确定性极强，一个 shell 脚本就能做，而且 fail-closed 语义天然（不认识就当生产）。我选环境 tier 是因为它可以在模型碰不到的层实现。

### Q7.4 一个反直觉的设计要点是什么？

`[理论]` 人工审核不能到处默认。一天批两百次的人等于什么都没批，这叫 oversight fatigue，也叫橡皮章审批。所以 HITL 应该被当成 error budget 的一种花费方式，只花在不可逆的那一档。这是我认为最容易被做反的一条：很多团队为了「安全」把所有动作都加审批，结果是审批变成噪音，真正危险的那一次也被点过去了。（src: `agent_slo_error_budget_survey_20260519.md`；`v4_ai_agents.md`）

### Q7.5 责任归属怎么办？

`[业界]` 有一个表述很准：权限往下传了，问责却留在原地，被分散到那些训练、部署、监督这个系统的人身上（src: IBM，转引自 `agent_slo_error_budget_survey_20260519.md`）。

`[一手]` 我的应对是让责任链在审计里可见：每条 mutating 命令带 `# INTENT:` 那一行 reasoning，执行前后各记一条 JSONL，approval 痕迹必须出现在 investigation log 里。所以「谁批准了什么、为什么、结果如何」这条链是完整的。我做不到的是「模型为什么想到这一步」的因果解释。这个边界我会主动说清。

---

## §8 元层面：harness engineering 是真需求还是重新包装

### Q8.1 你的判断是什么？

`[理论/业界]` 两者都是，而且不矛盾。诚实的描述是大约七到九成是已有的系统设计换了一个底座，一到三成是真新的原语，加上百分之百的重新框架化。

七到九成的老东西包括：system prompt 加 tool loop、subagent、sandbox、state graph、guardrails。这些在 2022 年的 ReAct、2023 年的 AutoGPT 与 LangChain 时代就有。

真正 2025 到 2026 才成熟的新原语大致四个：progressive disclosure 的 skill 加载、lifecycle hook、agent-aware 的自动 compaction、harness 与模型的协同训练。

一句最锋利的批评值得背下来：所以 agent harness 就是系统设计，只不过是给一个会幻觉的 runtime 做的系统设计。

我认同这句话，而且它对 SRE 背景的人是有利的：如果七到九成是系统设计，那既有的可靠性工程经验是直接可用的资产。（src: `contexts/survey_sessions/harness_engineering_real_or_rebrand_survey_20260417.md`）

### Q8.2 哪些数字不能拿来论证？

`[业界]` 提前知道这些，免得在面试里引用了被打：
- OpenAI Frontier 那个「5x 生产力」「一百万行代码零人工编写」是 N=1 自述，而且它自己承认前一个半月比手写慢十倍，「0% human review」实际有 post-merge review，5x 没有给计算方法论。
- Anthropic 关于长时运行 agent 的 harness 博客里零个 before/after 数字，全是定性描述。
- 跨 harness 的 benchmark 差距（Terminal-Bench 2.0 同模型 3.3 到 6.5 个百分点、SWE-bench Pro 5 到 12 个百分点）看似硬证据，但有反声说这本质上是误差范围内的噪音（该反驳经二手转述，原始报告未定位到）。
- 定义本身不稳定：核心提出者们自己承认没有清晰定义，harness 与 context engineering 的层次关系至少存在三四种互斥说法。
- 商业博弈要点破：一句元观察说得好，核心张力在 Big Model 和 Big Harness 之间，卖 harness 的人想卖你 harness，卖模型的人想卖你模型。

### Q8.3 反向证据是什么？

`[业界]` 两条，主动交代比被问出来强：
- Wharton 的 GAIL 研究发现 CoT 对推理模型的提升只有约 3%，却增加 20% 到 80% 的时间。也就是 harness 做过头反而是负资产。
- Anthropic 自己在「Building Effective Agents」里说最成功的实现没有使用复杂框架，这直接反对「harness 越复杂越好」。

`[一手]` 这两条对我的设计有实际影响：我做过一次系统性的知识库收敛，用 `dv_specific_score` 砍掉六成通用内容，并且在收敛计划里明确写了「不会做的事」清单（不新增元结构、不重写 stable 文件、不加新 hook 类型）。这是对 over-engineering 的自觉防御。

### Q8.4 结构性的证据缺口有哪些？

`[业界]` 说清楚这些，是「我知道我论据的边界」的信号：没有论文做 harness 与 model 的贡献分解；没有 RCT 式的开发者产品对比；DORA 2026 没出 harness 专题。所以任何关于 harness 效果的定量断言，现阶段都缺可复现的证据基础。我论证的应该是设计逻辑（为什么这条约束防这个失效模式），而不是效果数字。

### Q8.5 一个可以直接说的认知锚点是什么？

`[业界]` 判断这类新叙事，只看三样：API 变了什么、benchmark 的 delta 是多少、token 规模是多少。不看 manifesto 和口号。（src: `harness_engineering_real_or_rebrand_survey_20260417.md` §8.3）

---

## §9 为什么 SRE 背景在这个方向有优势（自我定位的论证）

### Q9.1 迁移矩阵是什么？

`[业界]` 有一份现成的 SRE 到 agent infra 的技能迁移矩阵，Tier 1（最高价值）三条：可观测性迁移到 LLM 与 agent 的 trace 与 token 成本追踪；故障恢复与事件响应迁移到 agent 故障隔离与 kill switch；容量规划迁移到 GPU 与 token 成本管理、rate limit、provider routing。Tier 2 两条：SLO 与 SLI 定义迁移到 agent 质量 SLO（准确率、幻觉率、延迟 P99）；混沌工程迁移到 prompt injection 与模型退化的鲁棒性测试。

最稀缺的定位叫 Agent Reliability Engineer 或 Agent Platform Engineer，描述是能同时理解 LLM 的非确定性和生产系统的确定性要求。（src: `contexts/survey_sessions/agent_dev_vs_agent_ops_infra_survey_20260402.md`）

### Q9.2 有什么外部说法支持「工程基本功比 AI 部分更关键」？

`[业界]` 一句 Google 的观察很好用：我看到开发者在没掌握基础的时候就冲去实现高级功能，每一次他们的 agent 都不可靠，而 AI 那部分，调 API，其实是最容易的部分。

还有一句概括瓶颈转移的：瓶颈已经从「AI 能理解这个吗」变成「我们能把它连接到它需要的一切并且保持可靠吗」。

`[理论]` 这两句支撑的是同一个立场：agent 生产化的困难在系统工程侧，而这正是 SRE 的主场。我用它来解释为什么我这条路径不是转行，而是同一个回路（目标状态对照实际状态，安全地收敛）的下一种形态。（src: `agent_dev_vs_agent_ops_infra_survey_20260402.md`；`v4_ai_agents.md`）

### Q9.3 有多少组织其实还没开始？

`[业界]` 只有 47% 的组织在监控 agent，仅 22% 把 agent 当独立实体监控。加上约 88% 的 agent 从未进入生产。这两组数字说明的是：现在这个市场缺的不是能让 agent 跑起来的人，是能让 agent 可靠地跑在生产里的人。（src: `agent_dev_vs_agent_ops_infra_survey_20260402.md`）
