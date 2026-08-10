# META

id: w-v-agents
kicker_en: PERSPECTIVE
kicker_cn: 视角
title_en: SRE in the Age of AI Agents
title_cn: AI agent 时代的 SRE
sub_en: What changed, and what still needs an engineer
sub_cn: 什么变了，什么还需要工程师
domains: [platform, security, incident]

# EN

Strip SRE down to first principles and it is one job: operating the loop between what a system should be doing and what it is actually doing. Detect the gap, explain it, close it, keep it closed. AI agents have not changed that definition at all. What they have changed is who performs which part of the loop. I say this not as a forecast but as a description of my working week: agents run my production forensics, an agent harness runs my oncall triage, and the evidence behind this resume was itself distilled by an agent pipeline. This page is what the shift looks like from inside it.

## What has changed

**The execution layer of oncall has moved to agents.** When a compaction score on a distributed storage system pinned at ~4,500 and refused to move, I did not investigate serially. I fanned out three read-only agents in parallel: one enumerating logs, one walking the tablet-metadata endpoints, one inspecting the catalog recycle bin. All three converged on the same orphaned tablet from an already-dropped table, structurally excluded from scheduling. One chain of reasoning can be led astray; three independent evidence chains pointing at the same object is a verdict. That fan-out-and-converge pattern is now my default forensics posture, not an experiment.

The same shift is institutionalized in my oncall triage harness. An agent picks up an alert and investigates autonomously, but inside a structure I designed: stage-locked phases it cannot skip, and conclusions that must cite evidence, a query result, a log line, a file and line number. Mutations are never auto-executed; every state change is proposed, and a human approves each one. The agent does the legwork that used to consume the first thirty minutes of every page.

**Knowledge changed shape.** A runbook written for humans is narrative. What compounds for an agent is the discriminator: a cheap check that splits the root-cause candidate set in half. Recording the same dead end ten times as a story yields nothing; recording it once as "if A is normal, prune this entire branch" turns a past investigation into future routing. My triage knowledge base is organized around this unit, decision trees ordered by which checks are cheap and which are expensive, because answers rot as infrastructure changes but probe order barely does.

**The human's position moved, and so did the leverage.** I spend my time designing harnesses and adjudicating their output, not executing steps. The result is reach: the evidence base of this resume was produced by a re-runnable mining pipeline that distilled 82 working sessions into structured highlights with provenance, then into a dossier. One person plus a harness now owns a surface that used to need several.

## What still needs an engineer

Start from one distinction. A Kubernetes controller is deterministic, so it needs no guardrail. An agent is a probabilistic controller, so a policy layer is a production prerequisite, not an option. Most of the engineering that remains human falls out of that fact.

**Intent and constraint definition.** Someone has to write the Spec, the desired end state with machine-checkable acceptance criteria, and place the Hooks: audit hooks that record evidence, deny hooks that hard-block irreversible actions, human-in-the-loop hooks that pause for approval. This is admission control for decisions, and it cannot be delegated to the thing being admitted. Constraints are the source of safety; the model is the source of capability. Confusing the two is how agents end up helpful and dangerous at once.

**Mutation sovereignty.** My harness enforces a strict read/write asymmetry: agents are excellent at reading and diagnosing, and structurally dangerous at writing. All the compounding value lives on the diagnostic side, so that side runs wide open. The write side is proposal-only, because blast radius is a business judgment and because agents fail silently: a hallucinated conclusion returns the equivalent of HTTP 200. You cannot budget what you cannot detect, and automating mutation on top of undetected error is not speed, it is laundering error with speed.

**Eval as the measurement system.** An agent without eval is not operable; you are shipping vibes. Per-step reliability compounds badly, a 95% step success rate is roughly 36% over twenty steps, so the SRE toolkit transfers with modification: task completion rate and convergence time as the first SLIs, an eval dataset with expected outcomes run on every change, and human review treated as a way to spend error budget on the irreversible tier rather than a default everywhere. A reviewer who approves two hundred times a day approves nothing. When the budget burns, autonomy should contract automatically.

**Platform primitives.** Agent systems need exactly what production systems need: a reconcile loop that compares state against Spec, observability over decisions and not just outputs, and explicit convergence criteria. My working summary is three imperatives: constrain it, see it, make it converge.

**Final judgment.** The rule in my harness, agent emits evidence and the human decides policy, is the same principle I argued in database-engine work, where the engine emits estimates and the caller decides routing policy. Mechanism can be shared, delegated, even upstreamed. Policy encodes your risk appetite and your accountability, and it stays with the engineer whose name is on the pager. Two lines of my career, storage engines and agent operations, converge on exactly this sentence.

That is the internal logic of the path from SRE to AI infrastructure. Not a career change: the same loop, desired state against actual state, closed safely, in its next form.

# CN

把 SRE 还原到第一性原理，它就是一件事：运营「系统应该做什么」与「实际在做什么」之间的回路。发现偏差，解释偏差，收敛偏差，并让它保持收敛。AI agent 没有改变这个定义，改变的是回路里谁干什么。这不是预测，是我工作周的实况：agent 在跑我的生产取证，一套 agent harness 在跑我的 oncall triage，这份简历背后的证据本身也是由 agent 流水线蒸馏出来的。这一页写的是从内部看到的这场变化。

## 发展到今天，变了什么

**oncall 的执行层交给了 agent。** 一次分布式存储系统的 compaction score 卡死在约 4,500 不动，我没有串行排查，而是并行派出三个只读 agent：一个枚举日志，一个走 tablet 元数据端点，一个检查 catalog 回收站。三条线索收敛到同一个孤儿 tablet，它属于一张早已 drop 的表，被调度器结构性排除在外。一条推理链会被带偏，三条独立证据链指向同一个对象，那是裁决。这种「扇出再收敛」的取证方式如今是我的默认姿势，不是实验。

同样的变化被固化进我的 oncall triage harness：agent 接到告警后自主调查，但在我设计的结构里运行。阶段锁定，不能跳步；结论必须引用证据，一条查询结果、一行日志、一个文件位置。mutation 零自动执行，每一次状态变更都只能提出，由人逐一批准。过去每次被 page 后头三十分钟的跑腿活，现在归 agent。

**知识资产换了形态。** 写给人读的 runbook 是叙事，对 agent 真正复利的是判别器：一个便宜的检查，把 root cause 候选集劈成两半。同一条死路当故事记十遍没有价值，记成一次「若 A 正常，砍掉这一整支」，过去的调查就变成未来的路由。我的 triage 知识库就按这个单元组织，决策树按检查的便宜与昂贵排序，因为答案会随 infra 变化而腐烂，探查顺序几乎不变。

**人的位置移动了，杠杆也变了。** 我的时间花在设计 harness 和裁决它的产出上，而不是执行步骤。回报是覆盖面：这份简历的证据由一条可重跑的挖掘流水线产出，把 82 个工作 session 蒸馏成带出处的结构化 highlight，再汇成 dossier。一个人加一套 harness，如今能 own 过去需要几个人的面。

## 还有什么需要工程师做

先立一个区分。Kubernetes controller 是确定性的，所以不需要 guardrail；agent 是概率性的 controller，所以 policy 层是生产环境的硬性前提，不是可选项。剩下需要人做的工程，大多从这个事实推出来。

**意图与约束定义。** 得有人写 Spec，也就是带机器可校验验收条件的目标终态；得有人放置 Hook：记录证据的 audit hook，硬性拦截不可逆动作的 deny hook，暂停等人批准的 HITL hook。这是对决策的 admission control，它不能委托给被准入的那个东西自己来做。约束是安全的来源，模型是能力的来源，把两者搞混，agent 就会同时显得热心而危险。

**mutation 主权。** 我的 harness 强制读写不对称：agent 极擅长读和诊断，在写上则是结构性危险。复利全部发生在诊断侧，所以诊断侧放开跑；写侧只允许 propose。写操作的最终批准权留在人手里，一是因为爆炸半径是业务判断，二是因为 agent 的失败是静默的：一个幻觉出来的结论，返回的等价于 HTTP 200。你无法为你检测不到的东西设 budget，在未被检测的错误之上自动化 mutation，不是提速，是用速度给错误洗白。

**eval 与 agent 的 SLO。** 没有 eval 的 agent 是不可运营的，那等于在上线感觉。单步可靠性会复合恶化，95% 的单步成功率跑二十步只剩约 36%，所以 SRE 工具箱可以平移但要改造：把任务完成率和收敛时间定成最初的 SLI；维护一套带预期结果的 eval 数据集，每次改动都跑；把人工审核当成 error budget 的一种花费方式，只花在不可逆的那一档，而不是处处默认。一天批两百次的人等于什么都没批。budget 烧穿时，自主权应该自动收缩。

**平台原语。** agent 系统需要的和生产系统一模一样：一个拿现状对照 Spec 的 reconcile loop，覆盖决策过程而不只是输出的可观测性，以及显式的收敛判据。我的工作总结是三句话：限制它，看见它，让它回正。

**最终判断。** 我的 harness 里那条规则，agent emits evidence, human decides policy，和我在数据库引擎工作里坚持的原则是同一条：engine 输出估计值，调用方决定路由策略。机制可以共享、可以委托、甚至可以贡献给上游；policy 承载的是你的风险偏好和你的问责，它留在名字挂在 pager 上的那个工程师身上。我职业里的两条线，存储引擎和 agent 运营，恰好在这句话上合流。

这就是 SRE 走向 AI infrastructure 这条路径的内在逻辑。不是转行：还是那个回路，目标状态对照实际状态，安全地收敛，只是进入了下一种形态。

# SOURCES

- contexts/thought_review/k8s_sre_agent_controllability_model_20260330.md — SRE and agentic AI as isomorphic control problems; agent as probabilistic controller; "constrain it, see it, make it converge"; engineer's value as defining constraint space and convergence rules
- rules/skills/bestpractice_agent_reliability_engineering.md — three pillars (constraints / observability / convergence); compounding failure math (0.95^20 ≈ 36%); task completion + convergence time as first SLIs; eval as a measurement system
- rules/skills/bestpractice_agentic_control_primitives.md — Spec / Loop / Hook / Fork primitives; hooks as admission control (audit / deny / HITL); K8s mapping
- contexts/survey_sessions/agent_slo_error_budget_survey_20260519.md — HITL as one way to spend error budget, tiered by reversibility × blast radius; oversight fatigue (rubber-stamp approvals); silent failure ("you cannot budget what you cannot detect"); budget burn → autonomy contraction
- contexts/thought_review/agent_ops_competency_model_v1.md — read-only auto / mutating approval permission tiers; audit trail as an answerable "why did the agent do this"; eval as the foundation pillar
- agents/sre_oncall_triage_skill/knowledge/references/agent-ops-lessons.md — discriminator as the minimal compounding unit; cheap-vs-expensive probe ordering; read/write asymmetry; evidence-pointer rule for conclusions
- adhoc_jobs/dynamic_resume_site/content/case_study_ch_to_doris.md — compaction-score forensics (three parallel read-only evidence chains → orphaned tablet); "engine emits data, caller decides policy" upstream decision
- Given facts (verified): triage harness with stage locking, evidence-cited conclusions, zero auto-mutation; resume evidence pipeline distilling 82 working sessions into provenance-tagged highlights and a dossier
