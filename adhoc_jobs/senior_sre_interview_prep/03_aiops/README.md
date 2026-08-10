# 03 · AIOps / AI-agent-for-Ops · 核心圈

> 方向定位：差异化卖点。这个方向的价值在于我真建了一套有 phase gate、有审计、有 iron law 的 oncall triage harness，并且在自己的 oncall 上跑着。
> 硬纪律：内核只放代码和文件能背书的东西。团队推广度和 MTTR 收益目前没有数据，一律按「没有」讲。

---

## 这个方向我的一句话定位

我把 oncall triage 当成一个生产系统来做可靠性工程。让一个会幻觉的推理内核在我设计的约束系统里自主完成调查，同时让每一个不可逆操作停在一个确定性的 shell hook 前面等人批准。判断力交给模型，红线交给 `exit 2`。我交付的资产是这套 harness 本身，它把 senior SRE 的调查判断编码成可执行、可审计、可复利的结构，而不是某一次调查的结论。

需要补一句诚实的边界，我会主动说：这套系统目前主要跑我个人的 oncall 与个人工程，它是个人工程成果，还没有做成团队级平台，所以我能讲透设计决策、失败模式和 trade-off，讲不了组织级的 MTTR 改善幅度，因为我没有测过那个数字。

30 秒版本（面试直接背）：

> 我做了一个 SRE oncall triage harness。输入一条 Slack 告警链接，它自主查 VictoriaMetrics、Loki、Slack，产出带证据链的调查报告和带中文意图注释的操作命令方案。核心工程量不在 prompt，在三个地方：一是三层纵深防御，让未授权的生产 mutation 在结构上不可能发生；二是把 context 当 RAM 做容量管理，所有 raw data 查询下沉给 subagent，只回收 500 token 摘要；三是把 agent 当生产系统运维，输出有 CI，质量有趋势追踪，每次调查沉淀回知识库。

---

## 内核：真建了，并且在用

代码与文件可以逐条背书。以下每条我都能打开文件指行。

| 能力条目 | 一句话说明 | evidence 路径 |
|---|---|---|
| Oncall triage harness 整体 | MAP 式入口 + 9 个按需加载子 skill + 6 个 shell hook + 108 个 knowledge 文件，跑真实告警 | `agents/sre_oncall_triage_skill/SKILL.md`；子 skill 见同目录 `skills/`（9 个）；hook 见 `tools/agent_ops/hooks/`（6 个 .sh） |
| 三层纵深防御 | L1 settings.json 静态白名单 / L2 shell hook 链（模型够不着）/ L3 agent spec 软约束，安全属性只放在 L2 | `work-contexts/career/interview/interview-7-agent-harness-engineering.md` §3.1 |
| Mutation Approval Gate 四关 | 一条 mutating 命令要过 skill 层 approval、permissions 名单、`k8s-gate.sh` hook、强制事后验证，任一关拦下就到不了生产 | `adhoc_jobs/dynamic_resume_site/content/projects/p_agentops.md`「真正落地的安全」节；`agents/sre_oncall_triage_skill/SKILL.md` §0 |
| 环境 tier 强制 + default-deny | PROD/PCI/MGT/DEMO 全 block mutating，PREPROD 只 dry-run，DEV 需带 INTENT，未分类 alias 按 PROD 处理 | `agents/sre_oncall_triage_skill/tools/agent_ops/hooks/k8s-gate.sh`（204 行，见 UNCLASSIFIED ALIAS 段 L161-171） |
| `# INTENT:` 审计约定 | 每条 mutating 命令前置一行 reasoning，hook 自动捕获进 JSONL，事故复盘时不用猜当时为什么这么做 | `CLAUDE.md`（项目根）K8s/AWS Operations 节；`hooks/audit-pre.sh`、`hooks/audit-log.sh` |
| Phase Lock A/B/C | plan.md 的 `phase:` 字段在文件级限制主 agent 能读什么，Phase A 读不到 runbook 和 deploy history，所以无从脑补根因 | `agents/sre_oncall_triage_skill/skills/sre-oncall-init/phase_lock.md`（54 行，三 phase 的允许/禁止清单） |
| Subagent Isolation ≤500 token 契约 | 主 agent 禁直调返回 raw 时序或日志行的 MCP 工具，一律派 sonnet subagent 回收结构化摘要 | `agents/sre_oncall_triage_skill/SKILL.md` §0 与 §9（含 subagent prompt 模板与工具分工表） |
| Quote-the-line 证据律 | 每条 finding 后必须紧跟 `> evidence:` / `> file:line:` / `> historical:` / `> user-provided:` 之一，否则 confidence 强制 ≤3 且措辞降级到 possibly | `agents/sre_oncall_triage_skill/skills/sre-oncall-output-format/SKILL.md` §Finding Confidence Rule |
| Iron Laws（3 条） | 无 root_cause_hypothesis 不发 Slack 结论；累计 3 个被否假设强制 escalate；Phase 边界违反即未完成 | `agents/sre_oncall_triage_skill/skills/sre-oncall-acceptance-criteria/SKILL.md` §Iron Laws |
| 8 条 acceptance criteria | 每条对应一个已知 LLM 失效模式，plan-first gate 防边查边编，missing-field gate 防猜测填充，±3min 窗口防宽窗取证 | 同上 §收敛条件 |
| 四控制原语 Spec/Loop/Hook/Fork | 用控制原语替代角色拟物，映射到 K8s 的 manifest / reconcile loop / admission webhook / pod 隔离 | `rules/skills/bestpractice_agentic_control_primitives.md`；`p_agentops.md`「四个控制原语」节 |
| 11-step idempotent pipeline | 每 step 完成写 `step_N_done`，session 断了新 session `grep step_.*_done` 即可续跑，状态外置在单文件 plan.md | `rules/skills/workflow_oncall_full_triage.md`（291 行，含 Resume from Crash 与 Failure Modes 表） |
| 输出 CI + 质量趋势 | `verify.py` 用退出码守单次报告质量（1059 行），`slo.py` 跨调查追踪通过率趋势（281 行） | `agents/sre_oncall_triage_skill/tools/agent_ops/verify.py`、`slo.py` |
| 知识复利闭环与治理 | 只记 delta，AI 写的知识经人 review 才从 draft 升 stable，每条用 `derived_from` 溯源；一次系统性收敛砍掉 6/10 个 facet | `p_agentops.md`「为什么越用越好」节；`work-contexts/career/interview/interview-7-agent-harness-engineering.md` §3.8；`agents/sre_oncall_triage_skill/records/`（converge.py + inventory.json） |
| Agent failure taxonomy | 6 大类 25 种故障模式（C/R/T/P/G/S）+ 记录模板 + 演化规则，把 agent 怎么会出错从直觉变成可检索知识 | `rules/skills/workflow_agent_failure_taxonomy.md` |
| Untrusted input rule | kubectl logs/describe/get -o yaml、event、pod annotation 全部当外部不可信数据，禁止仅凭其内容采取后续动作 | `CLAUDE.md`（项目根）§K8s / AWS Operations · Untrusted input rule |
| AI 审 AI 的红队 hook | `plan-safety-review.sh` 在 ExitPlanMode 时嵌套一次 `claude -p sonnet` 调用，用禁全部工具的方式递归安全地审当前模型的计划 | `agents/sre_oncall_triage_skill/tools/agent_ops/hooks/plan-safety-review.sh`（46 行） |
| 多 agent 并行取证（真实生产战果） | compaction score 卡在约 4,504 时并行派三个只读 agent 走日志、tablet 元数据、catalog 回收站，三条独立证据链收敛到同一个孤儿 tablet | `adhoc_jobs/dynamic_resume_site/content/perspectives/v4_ai_agents.md`「oncall 的执行层交给了 agent」节 |

内核共 18 条。

---

## 中环：做过但规模或影响力有限，需要标准口径

这一环的规则是：先给事实，再给我为什么这样选，最后给我知道差在哪。不吹，也不自贬。

| 能力条目 | 一句话说明 | 被追问时的标准口径 |
|---|---|---|
| 团队推广与 ROI | 这套 harness 服务我个人的 oncall 与个人工程，没有做成团队级已推广的平台 | 「诚实说，它现在是个人工程，用户是我自己。我没有团队采用数字，也没测过 MTTR 改善，所以我不会给你一个编出来的百分比。它对我的价值是把每次被 page 后头三十分钟的跑腿活变成 agent 干（src: `v4_ai_agents.md`），把调查方法从我脑子里搬进可 diff 的文件。要把它变成团队资产还差三件事我很清楚：一套跨人可用的凭证与权限模型、一份带预期结论的 eval 数据集、以及一个团队愿意接受的 approval 流程。这三件我能说出具体做法，但我没做过，所以我把它放在中环。」 |
| agent 执行 mutation 的实战经验 | PROD/PCI/MGT/DEMO 全 tier block，agent 从未在生产执行过 mutation | 「零。这是设计选择而不是能力缺失。价值风险不对称：调查是只读、可并行、错了无代价；mutation 错一次可能放大事故（src: `work-contexts/career/interview/interview-7-agent-harness-engineering.md` §5）。DEV tier 已经允许带 INTENT 的 mutation，所以这是一个可调的信任阈值，通路留着。」 |
| eval 体系的成熟度 | `verify.py` 是 rule-based checker + `slo.py` 是趋势追踪，还没有带预期结论的 eval 数据集 | 「我有输出层的 CI 和跨调查的通过率趋势，缺的是 agent reliability 该有的第二层：50 到 200 个带预期结果的任务集，每次改动都跑（src: `rules/skills/bestpractice_agent_reliability_engineering.md` §Minimal Production Baseline）。我做过的替代方案是历史真实 case 回放，对比结论方向而不要求逐字一致。我也明确知道我还缺一个业务级指标：调查结论被人类采纳率（src: `work-contexts/career/interview/interview-7-agent-harness-engineering.md` §5）。」 |
| agent 可观测性的实装 | 有 kubectl 与 MCP 双 JSONL 审计 + `audit-view.py` 回放，还没有 OTel trace 与 GenAI semconv 实装 | 「我的审计是自建 JSONL，每条带 INTENT 和上下文，可回放（src: `work-contexts/career/interview/interview-7-agent-harness-engineering.md` §3.6）。我知道正确的长期形态是 OTel 作为 substrate、tool call 落成 span，但 GenAI semconv 仍在演进，我的判断是先把 schema adapter 隔离在一层薄封装后面，别过早耦合（src: `rules/skills/bestpractice_agent_observability.md`）。所以这条我有设计判断，没有实装。」 |
| agent 的 SLO 与 error budget | `slo.py` 追踪通过率趋势，还没有 error budget policy 和自动收缩自主权的机制 | 「我知道正确形态是把人工审核当成 error budget 的一种花费方式，只花在不可逆的那一档；budget 烧穿时自主权自动收缩（src: `v4_ai_agents.md`）。我现在的实现是固定档位：只读全开，写侧全部 propose。动态收缩没做。」 |
| 多 agent 编排的规模 | 最大一次是 6 个 sonnet subagent 并行 audit 知识库 | 「我的并行是任务级 fan-out，不是常驻 agent fleet。规模上限就是几个到十几个 subagent，做知识库审计和并行取证。这个规模下我踩到的真实问题是 subagent 的自我报告不可信（它说两个文件完全相同，`diff -q` 说不是）和派发前没核对 subagent 工具集（Explore 型只读，写不了文件），两条都沉淀成规则了（src: `work-contexts/career/interview/interview-7-agent-harness-engineering.md` §4.1 §4.2）。」 |
| prompt injection 的实证防御 | 有规则、有 hook、有 untrusted input 约定，没做过红队实测 | 「我的防线是结构性的：所有从集群读回来的内容当外部不可信输入，禁止仅凭它采取后续动作（src: 项目根 `CLAUDE.md`）；真正的拦截放在 shell hook，prompt injection 绕不过 `exit 2`（src: `work-contexts/career/interview/interview-7-agent-harness-engineering.md` §3.1）。但我没跑过对抗性测试集，所以我说的是这个架构在原理上不依赖模型自觉，不是说我实测证明了它。」 |
| RAG 与向量检索 | 刻意没用，用结构化路由表 | 「百来个文件的量级下我选了确定性路由：alert 类型到 debug tree 是一张表，路由错了能看出是哪一行错。向量检索的失败模式是静默的，召回了不相关的或漏了相关的都没人知道（src: `work-contexts/career/interview/interview-7-agent-harness-engineering.md` §5）。规模涨一个数量级我会上混合检索。这是一个我可以论证的选择，不是我不会。」 |

中环共 8 条。

---

## 外环：补课项，只讲知识不讲经验

这一环的答法统一是：先说我知道它是什么、业界做到哪一层，再说我为什么还没做，最后说如果让我做我会怎么切入。对应内容全在 `fundamentals.md`。

| 能力条目 | 补课要点 | 对应 fundamentals 节 |
|---|---|---|
| 业界 AIOps / incident copilot 产品对标 | PagerDuty、incident.io、K8sGPT、Grafana、Datadog 各自做到哪一层，谁真让 AI 碰 mutation，谁只到 propose | §6 业界对标 |
| 传统 AIOps 的 ML 方法谱系 | 异常检测算法族、告警 correlation 与降噪、根因定位、容量预测，以及它们和 LLM agent 的分工 | §1 AIOps 谱系 |
| LLM 评测体系工程化 | eval 数据集构建、LLM-as-judge 的偏差控制、perturbation set、regression harness 的工程形态 | §2 三支柱与 eval |
| OTel GenAI semantic conventions | 具体 attribute 覆盖、稳定性状态、span 与 event 的建模方式 | §5 agent 可观测性 |
| Agent 安全的正式框架 | OWASP LLM Top 10、prompt injection 的分类与已知绕过手法、tool poisoning | §4 prompt injection 与 untrusted input |
| on-call copilot 的商业方案与 ROI 论证 | 商业方案怎么定价、怎么向管理层论证收益、常用的度量口径 | §6 业界对标 + §7 人机边界 |
| 组织层面的 agent 治理 | 多人共用 agent 时的凭证隔离、审批链、责任归属、合规审计 | §7 人机边界 |

外环共 7 条。

---

## 本方向 3 个最强 headline

**1. 我不是让 LLM 帮我看日志，我是给一个会幻觉的推理内核建了一层可靠的外壳。**
判断交给模型，红线交给确定性代码。一条生产 mutating 命令要闯四关，其中第三关是 6 个 shell hook 组成的确定性执行者，理解集群 alias 到环境的分级并且 fail-closed，未分类的 alias 一律按生产处理。这一层模型绕不过去，所以安全性从「希望模型别犯错」变成「模型犯错也没关系」。（src: `p_agentops.md`、`hooks/k8s-gate.sh` L161-171）

**2. 我把认知偏差工程化成了访问控制。**
Karpathy 描述过一种典型 agent 失败：看到 deploy 记录就脑补根因，症状还没看清就被「最近改过什么」带跑。我用状态机把这个失败模式设计掉了。plan.md 顶部的 `phase:` 字段在文件级限制主 agent 当前能读什么，Phase A 根本读不到 deploy history，也就无从脑补。进入下一阶段的门是显式前置条件，写在文件里，违反了 `verify.py` 会检出。很少有 agent 系统想到把「先看证据再下假设」做成结构性强制。（src: `p_agentops.md`、`phase_lock.md`、`work-contexts/career/interview/interview-7-agent-harness-engineering.md` §3.4）

**3. context 是这个系统最稀缺的资源，所有架构决策围绕它的预算展开。**
一次 raw range query 回来 30K token，一次调查要 5 到 10 次查询。主 agent 自己吃下去，走到需要下关键判断的 phase B/C 时判断力已经榨干。所以主 agent 只保留导航、判断、命令生成，全部原始数据获取下沉给 sonnet subagent，用 ≤500 token 的结构化摘要收口：一个带时间戳的极值、一个 step jump 标记、一个 baseline 比值。这是 SRE 的爆炸半径隔离加容量管理，对象从服务的内存换成 LLM 的 context window。（src: `p_agentops.md`、`SKILL.md` §9）

---

## 面试时的三个雷区（讲之前先看一眼）

这个方向最大的风险是被当成玩具或自娱自乐。三类质疑的应对写在 `story_bank.md` 每个故事的 L3-L5 防线里，这里只放索引：

1. 「LLM 会幻觉，你怎么敢让它碰生产？」→ S01 L3、S03 全篇、S05 L2
2. 「这和写一堆 runbook 脚本有什么本质区别？」→ S01 L4、S02 L4、S08 L3
3. 「团队推广了吗，ROI 多少？」→ S01 L5、S11 L4，以及本页中环第一条的标准口径

另外准备一条元层面的诚实表述，用来防「你是不是把老东西重新包装」：harness engineering 这套叙事本身有营销泡沫，诚实的描述是大部分组件在 2022 到 2023 年的 ReAct 与 AutoGPT 时代就有，真正新的原语很少（src: `contexts/survey_sessions/harness_engineering_real_or_rebrand_survey_20260417.md`）。我主动说这句话，比被面试官说出来强得多。详见 `fundamentals.md` §8。
