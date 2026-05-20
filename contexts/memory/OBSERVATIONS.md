# Memory Observations

这是三层记忆系统的 L1/L2 层。每日观察由 `periodic_jobs/ai_heartbeat/src/v0/observer.py` 自动写入，每周由 `reflector.py` 整理和蒸馏。

## 格式说明

每个日期条目格式如下：

```
Date: YYYY-MM-DD

🔴 High: [方法论/约束] 描述
🟡 Medium: [项目状态/决策] 描述
🟢 Low: [任务流水] 描述
```

### 优先级定义

- **🔴 High**：跨项目通用的经验教训、硬性约束、影响系统架构的重大决策。永久保留，候选晋升为 axiom 或 skill。
- **🟡 Medium**：活跃项目的关键进展、技术决策背景、未来几周仍需参考的信息。
- **🟢 Low**：日常任务流水、瞬时 debug 记录、临时上下文。定期垃圾回收。

## 如何加载记忆

不要全文加载这个文件（可能很大）。按需检索：

```bash
# 搜索特定主题
grep -n "关键词" contexts/memory/OBSERVATIONS.md

# 搜索最近 N 天
grep -A 20 "Date: $(date -v-7d +%Y-%m-%d)" contexts/memory/OBSERVATIONS.md
```

或使用语义搜索（`rules/skills/semantic_search.md`）做跨日期语义检索。

---

<!-- 以下是记录区域，由 observer.py 自动追加 -->

<!-- L2 Reflect note (2026-04-05): GC'd 8 empty backfill entries (2025-09-30, 2025-12-31, 2026-01-01, 2026-03-22~24, 2026-03-28~29).
     Consolidated methodology: "When backfilling L1 for a date with no evidence (empty mtime slice + empty VCS history), record the null result explicitly rather than inferring activity."
     This rule is now covered by KNOWLEDGE_BASE.md SOP §2.1. -->

<!-- L2 Reflect note (2026-04-14): Promoted "path drift handling" into L3 via rules/skills/bestpractice_automation_path_hygiene.md; GC'd related L1 entries and low-signal scan-noise. -->

<!-- L2 Reflect note (2026-04-21): Promoted (1) agentic control primitives (Spec/Loop/Hook/Fork) into rules/skills, (2) the round-number tail-latency timeout heuristic into SRE methodology, and (3) the "orchestration redistributes" + "untrusted outputs" policy note into harness architecture; GC'd the corresponding L1 red entries and repeated scan-noise. -->

<!-- L2 Reflect note (2026-04-28): Promoted (1) constraint-driven agent observability guidance into rules/skills/bestpractice_agent_observability.md, and (2) OSS contribution strategy filters into rules/skills/bestpractice_oss_contribution_strategy.md; GC'd the corresponding L1 red entries and scan-noise lows. -->

<!-- L2 Reflect note (2026-05-18): GC'd redundant empty scan entries (2026-05-12~14) and removed low-signal scan-noise; kept the latest explicit null-scan (2026-05-18). -->

Date: 2026-03-31

🟡 Medium: [Operational + market intel] Capture ClickHouse CPU triage case that avoids merge-only confirmation bias by requiring `system.processes` + `top -H` (`contexts/agent_failure_cases/2026-03-31_0000_clickhouse-cpu-oncall-investigation.md`); document Japan market signal that "AI Agent Ops" is mostly embedded into LLM/Agent/MLOps roles (`contexts/survey_sessions/ai_agent_ops_japan_jobs_survey_20260331.md`).

Date: 2026-04-03

🟡 Medium: [VictoriaMetrics ops/playbook] Capture current VM Single-mode scale (~0.8M active series) and top mitigations: disk headroom is the P0 risk; add `--storage.minFreeDiskSpaceBytes`, cap `--maxInsertRequestSize`, size vmagent WAL to cover an oncall window; include concrete PromQL alerts and safe-ops guardrails (`contexts/thought_review/victoriametrics_ops_review_20260402.md`, `contexts/thought_review/victoriametrics_sre_playbook_20260402.md`).

Date: 2026-04-09

🟡 Medium: [Nginx ingress rate limiting risk] `global_throttle` plugin can synchronously block nginx workers on memcached connect/read timeouts; single-replica memcached and lack of exporter metrics make it a latent SPOF (`contexts/thought_review/nginx_waiting_latency_memcached_root_cause_20260408.md`).

Date: 2026-04-17

🟡 Medium: Add 5 new survey outputs covering orchestration durability, harness engineering term/technology split, AI essential problems (effective context vs advertised, trust floors, hybrid architectures), China AI startup ecosystem signals, and learning-layer obsolescence (`contexts/survey_sessions/llm_orchestration_transitional_crutch_survey_20260417.md`, `contexts/survey_sessions/harness_engineering_real_or_rebrand_survey_20260417.md`, `contexts/survey_sessions/ai_essential_problems_survey_20260417.md`, `contexts/survey_sessions/china_ai_startup_ecosystem_survey_20260417.md`, `contexts/survey_sessions/ai_learning_obsolescence_survey_20260417.md`).

Date: 2026-04-22

🟡 Medium: [Contribution targets] A prioritized first-PR list emerges (Langfuse Prometheus exporter discussion, smolagents retry/backoff, DSPy streaming retries, LangGraph backoff math) plus a 3-6 month roadmap toward SIG-level contributions (`contexts/survey_sessions/agentic_ai_opensource_contribution_survey_20260422.md`).
🟡 Medium: [N2 prep scaffolding] Added a stub JLPT N2 exam spec with explicit TODO to validate via deep research and upgrade to VERIFIED (`rules/knowledge/n2_exam_spec.md`).

Date: 2026-05-18

🔴 High: (none observed in last 24h scan; no new high-signal artifacts)
🟡 Medium: (none observed in last 24h scan; `find <dir> -type f -mtime -1` empty across `contexts/thought_review/`, `contexts/survey_sessions/`, `contexts/memory/`, `rules/`, `periodic_jobs/`, `adhoc_jobs/`, `tools/`)

Date: 2026-05-19

🔴 High: Production-grade agent systems converge on the same physics as distributed systems: locality + staleness are fundamental tradeoffs, so correctness comes from constraining agency, wrapping non-determinism with durable execution, and gating irreversible actions with HITL (evidence and synthesis in `contexts/survey_sessions/agent_ops_locality_staleness_survey_20260519.md`).
🟡 Medium: New deep-research survey artifact added on Agent Ops / locality / staleness, framing durable execution (Temporal/Inngest/Restate etc.) and trace→eval→replay as the emerging operational stack (`contexts/survey_sessions/agent_ops_locality_staleness_survey_20260519.md`).
🟢 Low: Routine memory file churn only; no other new artifacts detected via `find <dir> -type f -mtime -1` across the scanned workspace directories in the last 24h (`contexts/thought_review/`, `contexts/daily_records/`, `rules/`, `periodic_jobs/`, `adhoc_jobs/`, `tools/`).

Date: 2026-05-20

🔴 High: [Locality as first-principles constraint] Locality is a structural constraint (not an engineer-chosen tradeoff) across CPU/DB/agent-memory layers; changing architectures (attention/SSM/RAG/external memory) only changes the manifestation, so durable value comes from policy/eviction/observability strategies (`rules/axioms/x07_locality_is_constraint_not_tradeoff.md`, `contexts/daily_records/2026-05-19_2109_locality-as-cs-unifying-principle.md`).
🟡 Medium: [Agent reliability framing] Treat SLO/error-budget as a viable ops framing for probabilistic agent systems, but only with explicit countermeasures for compound error, silent failure, Goodhart, and evaluation-awareness; HITL is a budget spending mechanism gated by reversibility and blast radius tiers (`contexts/survey_sessions/agent_slo_error_budget_survey_20260519.md`).
🟢 Low: [Daily record + scan results] New daily record file detected (`contexts/daily_records/2026-05-19_2109_locality-as-cs-unifying-principle.md`); `find <dir> -type f -mtime -1` showed no other changes under `contexts/thought_review/`, `contexts/memory/`, `periodic_jobs/`, `adhoc_jobs/`, `tools/`; requested directories `contexts/agent_failure_cases/`, `contexts/life_record/`, `contexts/blog/` were not present in this workspace.
