---
name: foundation-readiness-review
description: >
  Use after repo-level foundation changes are materialized and BEFORE detailed product planning or
  implementation. Independently verify that an unfamiliar agent can navigate, bootstrap, run, test,
  inspect failures, and follow repo rules from persisted artifacts. Also recommend the cheapest safe
  next delivery route: PERSONAL_FLOW, SDD_QUICK, SDD_STANDARD, or SDD_FULL. Produces
  docs/foundation-review.md. Do not review product functionality here.
---

# Foundation Readiness Review

Perform a clean-context review of the project foundation.

The question is:

> Can another capable coding agent enter this repository now and plan/implement the product without
> rediscovering the environment or relying on this conversation?

This review evaluates the **engineering substrate**, not product completeness.

## Inputs

Read:

- `docs/project-charter.md`
- `docs/foundation-plan.md`
- repo-local `AGENTS.md` / `CLAUDE.md` / `README.md`
- project/architecture map
- relevant ADRs
- build/package/CI configuration
- `docs/ai-foundation.md` when present

Inspect the actual repo state and git diff/status.

## Output

Create:

- `docs/foundation-review.md`

Verdict:

- `READY`
- `READY_WITH_NOTES`
- `BLOCKED`

Also emit one delivery-route recommendation:

- `PERSONAL_FLOW`
- `SDD_QUICK`
- `SDD_STANDARD`
- `SDD_FULL`

## Protocol

### 1. Assume zero conversation memory

Do not rely on prior chat decisions unless they are persisted in the repo.

Try to determine from the repo alone:

1. what the project is
2. what the current scaffold already provides
3. how to install/bootstrap it
4. how to run it
5. how to run the narrowest meaningful check
6. how to run the normal/full verification gate
7. where new product code/tests/tools/docs belong
8. what must not be modified
9. where architecture decisions and constraints live
10. how to diagnose a failed run/test

For an AI-heavy project also determine:

11. where provider/model calls are isolated
12. how tests substitute deterministic model output
13. where output validation occurs
14. how model-dependent quality is evaluated, if required
15. what trace/log data exists for AI failures

### 2. Execute the documented commands

Actually run the commands that foundation claims are canonical, subject to contest safety constraints.

At minimum, where applicable:

- bootstrap/install sanity
- build/typecheck
- focused or smoke test
- normal/full test/verify
- lint/static check
- run/boot smoke
- migration apply/revert smoke
- AI boundary fake/fixture test
- eval smoke if an eval runner is claimed

A documented command that does not work is a blocker until corrected or explicitly marked unavailable with a valid reason.

### 3. Check agent legibility

Fail or note problems when:

- the only way to know a command is to infer it from package files
- two docs disagree on canonical commands
- `AGENTS.md` is a long duplicate of architecture docs instead of a router
- placement rules are absent where the repo has multiple plausible homes
- generated/editable files are not distinguished
- important constraints exist only in ephemeral chat/history
- architecture maps contain guessed or stale claims
- foundation created empty/unused abstractions that increase search space

### 4. Check verification quality

Foundation verification should be:

- executable
- local where practical
- deterministic for deterministic behavior
- narrow enough for fast iteration
- broad enough to catch structural breakage before handoff

Do not require heavyweight infrastructure merely to improve a checklist score.

### 5. Check AI foundation when applicable

Block on material issues such as:

- domain/business code coupled directly to provider SDK with no test seam
- raw model output used for side effects without validation
- ordinary tests requiring a live model/provider
- retries capable of duplicating side effects with no idempotency semantics
- no way to distinguish provider failure from parse/validation failure

Do not block merely because a prompt, model, or final eval dataset has not yet been designed;
those may properly belong to feature design.

### 6. Determine the cheapest safe delivery route

Use `references/delivery-routing.md`.

Default to `PERSONAL_FLOW`.

Escalate only when the cost buys real risk reduction.

### 7. Write the review

Use `templates/foundation-review.md`.

Every blocker must include:

- evidence
- why it blocks downstream work
- smallest repair
- verification after repair

Do not generate speculative improvements.

## Definition of Done

- Canonical commands were actually exercised where feasible.
- Another agent can navigate the repo from persisted artifacts.
- Foundation docs and real repo state agree.
- Any AI boundary is independently testable without a live model for deterministic cases.
- Blockers are concrete and minimal.
- A next delivery route is recommended with explicit reasons.
- No product feature review or detailed task planning was performed.

## Anti-patterns

- Rating the foundation by document count.
- Recommending full SDD simply because the project is important.
- Treating every uncertainty as a blocker.
- Running expensive full integration checks when a documented external dependency makes them impossible.
- Turning the readiness review into a product architecture review.
- Using `SDD_FULL` as a prestige/default choice.
