# Skill: Agent Harness Architecture (Policy Runtime + Stateful Workflow + Orchestrator)

## When to Use
Designing an agent framework ("harness") that must run long-horizon workflows repeatedly, safely, and operably.

## Core Model
Treat the harness as three separable layers. Each layer must be durable even when models, prompts, or tasks change.

1. **Policy Runtime**
   - Purpose: constrain action space and enforce invariants.
   - Owns: scope/allowlist, budgets (time/token/cost), approval gates, secrets boundaries, irreversible-action rules.
   - Rule of thumb: treat all external tool/system outputs as untrusted input; require an evidence chain before mutating actions.
   - Principle: fail-closed by default.

2. **Stateful Workflow**
   - Purpose: make multi-step work resumable and debuggable.
   - Owns: checkpoints, state machine, retries/backoff, idempotency keys, stop conditions, evidence requirements.
   - Principle: correctness comes from explicit state, not "it usually works".

3. **Orchestrator**
   - Purpose: route work to the right components and coordinate parallelism.
   - Owns: tool routing, sub-agent fanout, model selection, context loading strategy, scheduling.
   - Principle: orchestration is a product surface, not glue code.

## Design Note: Orchestration Redistributes
Orchestration does not disappear; it redistributes into model weights (RL internalization), protocol standards (e.g. MCP), and a thinner harness.
Optimize for essential complexity (context management, tool integration, safety/oversight, and system boundary management) over brittle role-play patterns.

## Agent-Harness-Lite (Minimal Baseline)
Build a thin but complete slice before adding features.

1. **Checkpointing**: write state after every meaningful tool effect; support resume.
2. **Policy**: explicit scope + tool allowlist + budget; block irreversible actions without a gate.
3. **Routing**: choose tool/model based on task type; keep routing rules inspectable.
4. **Observability**: traces for tool calls, state transitions, and policy decisions.
5. **Eval Loop**: a small, stable task set; run on every change to catch regressions.

## Dogfooding Proof Plan
Evidence the harness works by operating it on real, recurring tasks:
1. Pick 3-5 weekly workflows with clear success criteria.
2. Run them end-to-end with traces + checkpoints; record failure modes.
3. Tighten policy/workflow until failures converge (retries, verifiers, gates).
4. Only then scale scope, parallelism, and automation.
