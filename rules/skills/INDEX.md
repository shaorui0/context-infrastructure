# Skills Index

本索引指向可复用的 Skills（技能）—— AI 可以调用的工具、流程和最佳实践。

- **想使用某个能力** → 浏览下方分类，找到对应的 skill 文件
- **想添加新 skill** → 参考现有文件格式，添加到对应分类

---

## 组件状态

### Tier 1: 核心（clone 后即可开始）
- ✅ Rules 框架（SOUL/USER/COMMUNICATION/WORKSPACE）— 填写即用
- ✅ Skills 框架（本目录）— 填写即用
- ✅ 三层记忆系统 — 需配置 OpenCode + cron

### Tier 2: 扩展（需要额外配置）
- ⚙️ Semantic Search — 需要 LLM Studio 或 OpenAI API
- ⚙️ Share Report — 需要 SSH 服务器或 GitHub Pages
- ⚙️ Google Docs — 需要 Google OAuth
- ⚙️ Send Email — 需要 Gmail App Password
- ⚙️ Delayed Execution — 适配你自己的工具路径

### 说明
✅ = 最多 15 分钟即可使用
⚙️ = 需要额外配置，不配不影响核心功能

---

## 分类索引

### API Guide（API 指南）

调用外部系统或工具的操作手册。

- [AI CLI Agent 实用指南](./ai_agent_cli_guide.md) — CLI Agent 设计原则、工具对比（Claude Code / Codex / OpenCode）、文件响应模式、AI 调用 AI
- [给自己发邮件技能](./send_email.md) ⚙️ — 通过 Gmail 发送邮件通知，需配置 App Password
- [分享报告到 Web](./share_report.md) ⚙️ — 将 MD 报告转 HTML 发布到你自己的服务器，返回 URL
- [Google Docs 操作](./google_docs.md) ⚙️ — CLI 工具：发布 Markdown、创建/搜索/修改/分享文档
- [Gemini 图片生成与放大](./gemini_image_generation.md) — CLI 工具：文生图、图片编辑、分辨率放大
- [增长数据分析](./growth_analytics.md) ⚙️ — 三个 CLI 查询网站流量（GA4）、邮件订阅（Kit）、Twitter 互动（Typefully）
- [Typefully Metrics CLI](./typefully_metrics.md) ⚙️ — 通过浏览器 session 凭据查询 Twitter impression、engagement、followers 数据

### Workflow（工作流）

特定任务的完整工作流程。

- [Session Context 保存](./save_session_context.md) ✅ — Session 结束前把想法/insight/决策/讨论留档到 `contexts/daily_records/`，宁原始勿提炼
- [Session Recap 断点续接](./session_recap/SKILL.md) ✅ — 停了很久的 session 回来，用 `tools/session_recap.py` 从 transcript 重建骨架（时间线/任务板/改过的文件），产出「已落地 / 停在哪 / 下一步 / 续跑指令」briefing，不用重读对话（truth 是 `rules/skills/session_recap/SKILL.md`，`~/.claude/skills/session_recap` 对该目录做真软链，不再靠 sync 脚本复制；没放 `archives/skills/` 是因为那整棵目录被 `.gitignore` 排除，会脱离版本控制）
- [本地 Markdown 分析](./workflow_local_md_analysis.md) ✅ — 对一批本地 md 文件全量阅读 + 跨文件主题/洞察/时间线，>20 文件并行 sub-agent
- [批处理 Agent 执行](./workflow_batch_agent_orchestration.md) ✅ — Orchestrator-Worker-Verifier-StateMachine，状态外置到 `queue.jsonl`/`results.jsonl`/`failures.jsonl`
- [自主执行工作流](./workflow_autonomous_execution.md) ✅ — Plan agent + scope 预授权 + 持续自主执行
  - 三阶段：Plan（派 sub-agent 规划）→ Execute（scope 内自主执行）→ Report
  - 核心：scope declaration 持久化到 plan 文件，context 压缩后仍可恢复
  - 配合 parallel subagents 使用，可并行步骤自动派 background agent
- [并行 Subagent 工作流](./workflow_parallel_subagents.md) ✅ — 调用后台 agent、并行执行多个 subagent
  - **必读**：初次使用并行 subagent 前，必须先读此 skill
  - **禁止轮询**：agent 运行期间不要反复调用 `background_output`，系统会自动通知
  - 判断标准：任务可拆分为 ≥2 个子任务，每个 ≥5 tool calls
  - 核心参数：并行度 ≤5，调研 overlap 30-50%，代码 overlap 0-20%
- [Agent 故障分类学](./workflow_agent_failure_taxonomy.md) ✅ — 系统性记录、分类、命名 agent 故障模式，积累 failure taxonomy
  - 6 大类 25 种故障模式：Context / Retrieval / Tool / Planning / Generation / System
  - 记录存放：`contexts/agent_failure_cases/`
  - 触发：agent 产出明显不对时，对照分类记录一条
- [深度调研工作流](./workflow_deep_research_survey.md) ✅ — 多 Agent 并行 + 交叉验证
- [认知画像提取工作流](./workflow_cognitive_profile_extraction.md) — 从非结构化对话数据提取可预测的认知公理
  - 适用：群聊/Slack/Discord/邮件/播客转录等任意对话数据
  - 流程：广泛扫描 → 深度验证 → 压力测试 → 定稿（≥3 轮动态滚动）
  - **要求 Opus 模型**：写作由 Opus 亲自完成，调研全部 delegate + 并行
- [AI 生成 Slide Deck 工作流 v1](./workflow_presentation_slides.md) — Gemini 渲染、Clean Ink 风格、8 进程并行、4K 放大前验证
- [AI 生成 Slide Deck 工作流 v2（image-free）](./workflow_presentation_slides_v2.md) — 不依赖任何 image-gen API；LLM 直写 HTML/SVG + Reveal.js + 并行 subagent 起草 + Playwright 导出 PNG。Clean Ink / 信息图风格首选
- [语义搜索技能](./semantic_search.md) ⚙️ — 利用向量相似度检索深层背景与观点演变
- [知识飞轮设计模式](./workflow_knowledge_flywheel.md) — 笨数据+笨方法+笨模型=精知识
- [视频下载与语音识别工作流](./workflow_bilibili_whisper_transcription.md) — Bilibili/YouTube 视频处理
- [延时执行技能](./delayed_execution.md) ⚙️ — 定时任务：sleep + 后台执行，或 OpenCode API 智能任务
- [N2 日本語トレーニング](./skill_n2_japanese_training.md) ✅ — 6 模式 N2 训练：会話/文法パターン/読解/語彙/模試/素材マイニング（单题/短会话）
- [N2 完整备考流水线 `/n2prep`](../../archives/skills/n2_exam_prep/SKILL.md) ✅ — 长周期备考编排：官方 scope → 4 并行 subagent 出卷 → 扎实度门禁(3 轮) → TTS 听力 → Python runner → 每日 30 条 Anki → 弱点台帳 + shadowing
  - 区别于 `/n2`：n2 是单题即兴练习，n2prep 是完整模考 + 每日备考包
  - 反偷懒设计：出卷与验卷 sub-agent 分离；门禁失败回流最多 3 轮
  - 脚本：`doctor.sh` / `run_written.py` / `run_listening.py` / `run_shadowing.py`
- [日语 Anki 闪卡生成](../../archives/skills/anki_japanese_flashcard/README.md) ✅ — 语料→闪卡 CSV→.apkg（含 TTS 语音）→自动导入 Anki（被 `/n2prep` Phase 6 调用）
- [给已有 Anki Deck 批量补语音 `/anki_add_audio`](../../archives/skills/anki_add_audio_existing_deck/SKILL.md) ✅ — 已有 deck 内容齐全但没语音时，用 Anki 自带 python 直接改 live collection（不用 AnkiConnect）：侦察→edge-tts 生成→关 Anki 写回→验证。读音放认读卡正面/回忆卡背面
- [学习对齐引擎判断层 `/anki_harness`](./anki_harness.md) ✅ — 读 engine 产出的 state.json，做质性诊断（缺口/记住没内化/领先/盲区）并写明日处方 plan.json；三模式 status/plan/replan
  - 薄封装：实现在 `work-contexts/toy-proj/anki-learning-harness/`（engine=state.json 唯一写者，本 skill=plan.json 唯一写者）
  - 不重算事实：mastery/latency/forecast 由 engine 算好，agent 只在事实之上做判断；确定性归 `analyst.py`，判断归 agent
  - Headless：`claude -p "/anki_harness status"`；触发词「学习复盘」「anki harness」「今天该学啥」
- [Kindle Syncer](../../archives/skills/kindle_syncer/README.md) ⚙️ — Markdown→PDF→邮件发送到 Kindle，支持 Mermaid 图表
- [注册 Skill 到全局](./workflow_register_global_skill.md) ✅ — 将 context-infrastructure 的 skill symlink 到 ~/.claude/skills 全局可用
- [dcluster StarRocks CN 部署与验证](./workflow_dcluster_starrocks_cn_deployment.md) ✅ — 构建→部署→E2E 验证完整流程，含 API 测试清单、Spot 冷启动等待、踩坑记录
- [DV 监控导览 & Oncall 入口](./workflow_dv_monitoring_oncall.md) ✅ — 监控栈架构 + 6 大核心 dashboard + alert→playbook 路由表 + 5 步 oncall 流程；导航到 `contexts/survey_sessions/monitoring_overview_20260521/` 的详细 parts
- [SRE Oncall Triage `/sre-oncall-triage`](../../agents/sre_oncall_triage_skill/SKILL.md) ✅ — Slack 告警 → 自主调查 → 中文注释的操作命令方案
  - MAP 风格入口：mode select（quick/full）+ 诊断路由（alert→Layer 1 sub-skill）+ 操作路由（→`historial_operations/` 外部 runbook）
  - **Mutation Approval Gate**：所有 `kubectl/helm/aws` mutating 命令零自动执行，必须 user approve
  - **Subagent Isolation**：主 agent 禁止直调 raw data MCP（VM query/series, Loki query），必须派 sonnet subagent 返回 ≤500 token 摘要
  - **Phase Lock (A/B/C)**：调查者 / 决策者 / 操作员三 phase 文件级 gate，phase=A 禁读 runbooks，phase=B 才解锁 cases，phase=C 才生成命令（见 `/sre-oncall-init` Step 2.5）
  - **Iron Laws**：(1) 无 root_cause_hypothesis 不能发 Slack conclusion；(2) 3 个 ✗ hypothesis 强制 escalate；(3) Phase 边界（见 `/sre-oncall-acceptance-criteria`）
  - **Quote-the-line**：每条 finding 必须有 `> evidence:` / `> file:line:` / `> historical:` / `> user-provided:` 之一，否则 confidence ≤ 3（见 `/sre-oncall-output-format` Finding Confidence Rule）
  - 9 个嵌套子 skill：`/sre-oncall-init`, `/sre-oncall-quick-check`, `/workflow-oncall-spike`, `/sre-vm-query` …
  - 旧 agent 形态保留在 `agents/sre_oncall_triage_agent/`（冻结，legacy subagent 仍可用）
- [Oncall Full Triage Pipeline `/workflow_oncall_full_triage`](./workflow_oncall_full_triage.md) ✅ — 11-step idempotent re-runnable pipeline 串联 Phase Lock + Iron Laws + Subagent Isolation + Quote-the-line；session 断了读 plan.md 的 `step_N_done` 字段续跑（≈ gstack `/ship` 风格）；设计来源 [survey](../../contexts/survey_sessions/gstack_design_philosophy_survey_20260527.md)

### BestPractice（最佳实践）

通用的最佳实践和经验教训。

- [AI 编程核心方法论](./bestpractice_ai_programming_mindset.md) ✅ — 70%问题、成功标准、可验证性
- [AI-native 知识系统 (Day-N 蒸馏优先)](./bestpractice_ai_native_knowledge_system.md) ✅ — 知识系统首要消费者是 AI；零组织捕获 + reflector 蒸馏；六维评估框架
- [SRE 第一性原理模型](./bestpractice_sre_reliability_models.md) ✅ — Availability 概率分解 / Overload λ vs μ / Latency SLI-Histogram-Quantile-SLO 四层分离
  - 配套 [Traditional SRE 7 层工具箱](./bestpractice_traditional_sre_methodology.md)：本 skill 是认知骨架（短），traditional 是参考手册（长）
- [数据系统监控归因模型](./bestpractice_data_system_monitoring.md) ✅ — OLAP/数据库监控按 oncall 提问顺序组织：契约(三组 SLI，含静默正确性故障) → 归因(需求侧 vs 供给侧判定表，依赖 audit log + SQL fingerprint) → 能力(ρ/(1-ρ) 三角 + 隔离降级) → 变更与恢复
  - 验收判据：出事时能否 5 分钟内判定该找写 SQL 的人还是管集群的人
  - 含实测陷阱表（资源全绿仍 1.12s、加机器对 LIMIT 点查无效、剪枝治不了列读放大）
- [去 AI 味写作规范](./bestpractice_de_ai_writing.md) ✅ — 翻译腔/模板句/AI 套话检测规则，博客质检流程，中英双语适用
- [Automation Path Hygiene](./bestpractice_automation_path_hygiene.md) ✅ — 自动化脚本的 workspace root 推导 + 预检 + fail-closed
- [Agentic Control Primitives (Spec/Loop/Hook/Fork)](./bestpractice_agentic_control_primitives.md) ✅ — 用控制原语替代角色拟物，围绕 Spec/Loop/Hook/Fork 设计可收敛、可审计的 agent workflow
- [Agent Reliability Engineering (SRE Framing)](./bestpractice_agent_reliability_engineering.md) ✅ — 约束/可观测/收敛三支柱 + eval 作为度量系统
- [Traditional SRE Methodology 7 层工具箱](./bestpractice_traditional_sre_methodology.md) ✅ — SLO / 过载 / 观测 / 发布 / Chaos / 事件 / 弹性模式，及映射到 AI 系统的翻译
  - 配套 Axiom：T12（第一性 SRE 是 AI 系统的外壳）
  - 用法：AI 系统设计时做 7 层 checklist；补 SRE 心智的参考手册
- [Agent Harness Architecture](./bestpractice_agent_harness_architecture.md) ✅ — Policy Runtime + Stateful Workflow + Orchestrator；先做 agent-harness-lite 再扩展
- [Agent Observability](./bestpractice_agent_observability.md) ✅ — OTel substrate reality + experimental GenAI semconv + provenance/"200-but-garbage" gaps
- [OSS Contribution Strategy](./bestpractice_oss_contribution_strategy.md) ✅ — Middle-layer collapse framing + license/supply-chain filters + infra/standards leverage
- [API Key 管理与调用](./bestpractice_api_key_management_1password_cli.md) ✅ — 使用 1Password CLI 安全管理密钥
- [面试评估框架](./bestpractice_interview_evaluation.md) ✅ — Trait > Skill、AI 作弊识别、技术深度探测
- [Markdown 转 HTML 最佳实践](./bestpractice_markdown_html_conversion.md) ✅
- [时间敏感信息验证](./bestpractice_temporal_info_verification.md) ✅ — 验证可能超出 knowledge cutoff 的信息
- [分阶段工作法](./bestpractice_staged_approach.md) ✅ — 隔离-处理-验证闭环，破坏性操作前 Dry Run
- [多 Agent 并行 analysis](./bestpractice_multi_agent_analysis.md) ✅ — Topic 分割 50% 重叠、交叉验证
- [AI 辅助调试诊断](./bestpractice_ai_debugging_diagnosis.md) ✅ — "代码改不好"的根因诊断决策树
- [AI 产品设计原则](./bestpractice_ai_product_design.md) ✅ — 线性聊天 vs 知识工作、感知规则解耦
- [Solid Skill Creator](./bestpractice_solid_skill_creator.md) ✅ — 工程化写 skill：失败模式优先、产物代替形容词、冗余设计、陷阱表、自检三问

---

## 如何添加你自己的 Skill

1. 参考现有 skill 文件的格式（元数据、核心说明、使用步骤、示例）
2. 以 `<category>_<name>.md` 命名（例如 `workflow_my_process.md`、`bestpractice_my_insight.md`）
3. 在 INDEX.md 对应分类下添加一行

Skill 格式参考（最简版）：
```markdown
# Skill: 名称

## When to Use
什么情况下触发这个 skill

## Prerequisites
需要什么工具/配置

## 步骤
1. 步骤一
2. 步骤二
```

## Progressive Disclosure

Skills 采用渐进式披露原则：
- **INDEX.md** 提供概览，快速定位
- **具体 skill 文件** 包含完整的操作步骤和示例
