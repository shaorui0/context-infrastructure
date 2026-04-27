# Skill: Agent Reliability Engineering (SRE Framing)

## When to Use
Designing or hardening any agent that runs multi-step workflows, touches real systems, or must be operated repeatedly.

## Core Thesis
Agent engineering is an SRE-style problem: build a reliable system out of an unreliable decision component.

## The Three Pillars
1. **Constraints**: limit action space and blast radius (scope, allowlists, budgets, human gates).
2. **Observability**: make decisions and tool effects inspectable (traces, metrics, audit trail).
3. **Convergence**: detect drift and pull the system back (replan, retries, checkpoints, verifiers).

## Why This Matters (Compounding Failure)
Long-horizon workflows amplify small per-step failure. Even a 95% step success rate becomes ~36% over 20 steps (`0.95^20`).

## Minimal Production Baseline
1. **Define success**: task completion rate + convergence time (your first SLI/SLO).
2. **Build an eval dataset**: 50-200 tasks with explicit expected outcomes; run it on every change.
3. **Trace everything**: tool calls as spans; capture intent, inputs, outputs, and evidence links.
4. **Add constraints**: scope declaration + tool allowlist + token/time budget; fail closed.
5. **Add a verifier**: check evidence chain completeness (not just the final answer quality).
6. **Human gate as a primitive**: ask rarely, but ask on uncertainty/high-risk.

## Evaluation Is a Measurement System
Treat eval like SLI/SLO design, not unit tests:
- **Layer 1**: Task completion (regression-like)
- **Layer 2**: Output quality (rubric + human sampling / judge with bias controls)
- **Layer 3**: Process quality (tool efficiency, loops, cost)
- **Layer 4**: Behavioral consistency (perturbation sets)

## Quick Design Prompts
- What is the smallest safe scope that still accomplishes the job?
- What is the evidence chain you require before taking an irreversible action?
- What is your stop condition when the agent is looping or uncertain?
