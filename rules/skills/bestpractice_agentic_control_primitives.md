# Skill: Agentic Control Primitives (Spec / Loop / Hook / Fork)

## When to Use
- Designing or reviewing any multi-step agent workflow (single-agent or multi-agent) that must converge, be auditable, and stay safe.
- Refactoring a role-based multi-agent setup (PM/Engineer/QA/Reviewer) into an engineering-first control plane.

## Core Model
Replace role skeuomorphisms with 4 control primitives:

1. **Spec** (declarative intent)
   - A durable artifact (usually a file) that states the desired end state.
   - Must include **machine-checkable acceptance criteria** (not just prose).
   - Properties: diffable, reviewable, resumable after context compression.

2. **Loop** (convergence)
   - A reconcile loop that repeatedly:
     - observes current state,
     - compares against Spec,
     - takes the next action,
     - verifies acceptance criteria.
   - The tighter the acceptance criteria, the more autonomous the loop can be.

3. **Hook** (admission control)
   - Gates at critical points in the loop:
     - audit-only hooks (record evidence),
     - deny hooks (hard blocks),
     - HITL hooks (pause for human approval).
   - Red-team/challenge is a hook: run it at Spec freeze-time and at delivery-time.

4. **Fork** (context isolation)
   - Fork subagents for isolation, not for cosplay roles.
   - Fork when isolation benefit exceeds briefing + merge cost.

## Fork Decision Heuristics
Prioritize isolation reasons (highest first):
1. **Independence-bound**: review/test/red-team must not share producer context.
2. **Attention-bound**: context gets noisy and quality decays; give a clean window.
3. **Capacity-bound**: one window cannot hold required information.
4. **Latency-bound**: truly independent work that can be merged with low coordination.

## Practical Checklist (Convert a Workflow)
1. Write a Spec file that includes acceptance criteria as a checklist (build/test/lint/schema checks, safety constraints).
2. Implement a Loop that can run verification commands and stop only when criteria pass.
3. Add Hooks:
   - deny: irreversible actions (force-push, prod deletes, credential exposure),
   - HITL: high-risk mutations (prod changes, billing/security),
   - audit: persist evidence links for every tool effect.
4. Fork only where isolation is required (review/test/red-team), keep the rest in one working context.

## Mapping (K8s Intuition)
- Spec: desired state (manifest)
- Loop: reconciliation loop (controller)
- Hook: admission control (OPA / validating webhook)
- Fork: isolation (pod/namespace + resource limits; and independent auditors)
