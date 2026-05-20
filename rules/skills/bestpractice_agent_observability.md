# Skill: Agent Observability (Constraints-First, Evidence-Based)

## When to Use
- You are designing or evaluating an agent observability stack (tracing/metrics/logs/evals) for multi-step or multi-agent workflows.
- You need to choose frameworks/vendors with clear tradeoffs (depth vs control/cost vs eval velocity vs infra integration).

## Core Thesis
"Best" in agent observability is constraint-driven. Start from requirements and constraints, then select the minimum stack that satisfies them.

## Current Substrate Reality
- OTel is the de-facto substrate for traces/metrics/logs integration across infra.
- OTel GenAI is still experimental. Treat it as a moving target: pin versions, avoid over-coupling schemas, and keep an escape hatch.

## What Remains Hard (Don’t Underestimate)
- Multi-agent + long-session provenance: attributing outcomes to specific decisions/tools/agents over long horizons.
- Semantic tool failures: cases where tools return HTTP 200 but the content is wrong or misleading ("200-but-garbage").
- Evaluation as a measurement system: converting natural-language outputs into stable signals without judge bias/overfitting.

## Design Constraints Checklist
1. Data control: what must stay local (PII, secrets, proprietary logs)?
2. Cost envelope: trace volume + prompt tokens + storage/retention.
3. Eval velocity: how quickly you need regression signals (PR-level vs weekly).
4. Infra integration: do you require native OTel pipelines, Prometheus, Grafana, ClickHouse, etc.?
5. Auditability: do you need replayable evidence chains for high-risk actions?

## Minimal Baseline (Works Before It’s Perfect)
- Trace every tool call with: intent, inputs, outputs, evidence links, and error classification.
- Persist workflow checkpoints (state transitions) so failures are debuggable and resumable.
- Add an explicit channel for "tool output untrusted" and require verifiers for mutating/irreversible actions.

## Guidance
- Prefer portable primitives (OTel-compatible traces + explicit state + eval dataset) over vendor-only features.
- Treat schema churn as normal: isolate telemetry schema adapters behind a thin layer.
