# Development Workflow Router

Start with the operating rules in [`../AGENTS.md`](../AGENTS.md), then use
[`../docs/project-map.md`](../docs/project-map.md) to find the owning component,
closest precedent, and narrowest command. Don't read more documents than is needed 
for the immediate task at hand. Load only the workflow selected below
and only that local skill's complete `SKILL.md`; never preload the skills tree.

This routing is conditional, not a mandatory ceremony. A small, clear task may
need only one workflow.

## Choose The Route

### Plan

- Use `project-direction` only when owner intent, priorities, scope, non-goals,
  trust boundaries, or decision ownership are unresolved.
- When intent is settled, use `task-brief-designer` to create or tighten one
  bounded implementation task.
- Do not use planning to reopen decisions already authoritative in
  [`../problem_statement.md`](../problem_statement.md).

### Implement

- Use `task-preflight` first only when current repository state, ownership,
  commands, permissions, or dependencies are uncertain enough to affect safe
  execution.
- Otherwise use `bounded-task-implementer`: define acceptance evidence, inspect
  the scoped status and precedent, make the smallest change, and verify
  progressively.
- Use `repo-foundation` when the task changes top-level placement, module
  boundaries, canonical commands, repository tools, CI, or agent guidance.
- Use `ai-flow-foundation` before detailed AI behavior only when a new model
  boundary or side-effect path lacks a persisted contract. The current boundary
  is summarized in [`../docs/ai-foundation.md`](../docs/ai-foundation.md).

### Verify Or Review

- Run the focused test for the owning component first, then the nearest relevant
  suite, then a broader gate only when the blast radius justifies it.
- Use `task-acceptance-review` to judge one implementation against a request or
  bounded task contract.
- Use `senior-code-review` for a broader branch, diff, architecture, security,
  data-integrity, performance, concurrency, or merge-readiness audit.
- A session that authored the change may report implementation evidence but
  must not present its own work as an independent acceptance review.

For delegated pre-plan analysis and discovery results, use fast reconciliation
by default: inspect the reported findings for conflicts and planning impact,
but do not run a formal acceptance review or repeat verification locally. If a
material uncertainty needs corroboration, return a separate bounded
verification task that states the exact model, reasoning level, scope, and
whether human action is required. Record minor non-blocking issues for later
work instead of interrupting the planning-critical path. This fast path does
not replace implementation review when task metadata, the user, or material
security, data-integrity, migration, concurrency, or public-API risk requires
it.

### Fix

1. Preserve and reproduce the exact failing signal.
2. Record the command, diagnostic identifier, and relevant artifact described in
   [`../docs/diagnostics.md`](../docs/diagnostics.md).
3. Identify the broken invariant and owning component.
4. Reduce the failure to the smallest fixture or input that still reproduces it.
5. Add or identify regression evidence capable of rejecting the broken state.
6. Fix the invariant narrowly.
7. Rerun the focused regression, owning suite, and only the relevant broader
   gates.

Use `testing-discipline` when adding or changing behavioral evidence. Do not
weaken a failing assertion merely to make the suite green.

### Handoff

Use `session-handoff` before context exhaustion or when work must move to a new
agent or chat. Capture the goal, authority, decisions, changed files, exact
commands and results, blockers, risks, and next actions. Do not rely on the
conversation alone.

## AI Implementation Invariants

- Deterministic financial rules remain deterministic.
- Raw model output is untrusted input.
- Use `ModelProvider`; do not scatter provider SDK calls through domain code.
- Validate model output before deterministic business logic consumes it.
- Unit tests use deterministic fakes and fixtures, never live models.
- Live-model quality and cost checks belong in evaluation, not ordinary unit
  tests.

## Completion

Before declaring a bounded task complete:

1. run its focused verification;
2. run the relevant regression suite;
3. run the repository-wide gate when the change's blast radius warrants it;
4. inspect the final diff and status; and
5. route to an independent acceptance or senior review only when requested,
   required by task metadata, or justified by risk.

The latest recorded foundation readiness and remaining gaps are in
[`../docs/foundation-review.md`](../docs/foundation-review.md).
