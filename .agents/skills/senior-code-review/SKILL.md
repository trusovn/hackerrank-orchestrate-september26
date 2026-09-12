---
name: senior-code-review
description: Perform a rigorous, read-only code review with the judgment and risk focus expected from a senior engineer or tech lead. Use whenever the user asks to review a pull request, branch, commit, working-tree diff, patch, or named source files; assess merge readiness; audit an implementation for bugs, regressions, security, data integrity, concurrency, performance, architecture, API compatibility, or test adequacy; or asks for a second set of eyes before shipping. Prefer a more specific workflow review skill when the user explicitly invokes one. Do not trigger for merely explaining code or implementing a change without a review request.
compatibility: Requires read access to the repository and its instructions. Git is recommended for diff-based reviews.
---

# Senior Code Review

Review the change as a merge gate, not as a style exercise. Optimize for defects prevented and decision quality. A short report with one proven blocker is more useful than a long checklist of speculation.

## Operating contract

- Stay read-only. Do not edit source, tests, configuration, generated files, or documentation during the review.
- If the user separately asks for fixes, finish and preserve the review first. Treat implementation as a later phase because edits change the review scope.
- Follow repository instructions before this skill. Judge code against the project's requirements and conventions, not personal preference.
- Review the requested change, plus only the surrounding code needed to understand its behavior and blast radius.
- Report a finding only when you can describe a concrete failure mode, regression, security exposure, or material maintenance/operational cost.
- A clean review is valid. Do not manufacture findings to appear thorough.

## 1. Establish the review contract

Identify:

- **Scope:** PR, branch range, commit, staged/unstaged changes, patch, or named files.
- **Intent:** the behavior being added or changed and the reason for it.
- **Sources of truth:** user requirements, issue/PR description, specs, acceptance criteria, API schemas, ADRs, migrations, and repository instructions.
- **Constraints:** compatibility promises, supported platforms, security boundaries, performance budgets, rollout/rollback requirements, and requested review depth.

Use the user's explicit scope. If none is supplied:

1. Inspect repository instructions and Git status.
2. Prefer the one unambiguous non-empty change: working-tree diff, staged diff, or current branch against its clear merge base.
3. State the exact scope used.
4. Ask before continuing only when multiple plausible scopes would materially change the review.

Do not silently treat the last commit, the entire repository, or `main..HEAD` as the scope.

If requirements are incomplete, infer only what established code, tests, contracts, and commit context support. Record material assumptions in the final report.

## 2. Build a change and risk map

Read the complete diff before commenting line by line. Summarize privately:

- behavior added, removed, or altered;
- entry points and affected callers;
- data read, written, migrated, cached, or exposed;
- trust boundaries and authorization decisions;
- external APIs, queues, files, clocks, randomness, and failure-prone dependencies;
- concurrency, retries, idempotency, and transaction boundaries;
- public contracts and backward-compatibility obligations;
- tests changed and important behavior left untested.

Prioritize review effort by blast radius and irreversibility. Authentication, authorization, money, destructive writes, migrations, shared state, public APIs, and silent data corruption deserve deeper tracing than local formatting changes.

Read [references/review-dimensions.md](references/review-dimensions.md) and apply every relevant dimension. Skip dimensions that cannot affect the scoped change.

## 3. Trace behavior through the system

For each high-risk path:

1. Start at the changed entry point.
2. Follow inputs through validation, authorization, domain logic, persistence, side effects, and response/error mapping.
3. Inspect affected callers and consumers, including code outside the diff when necessary.
4. Compare the implementation with requirements and existing invariants.
5. Examine success, failure, boundary, retry, and concurrent execution paths.
6. Confirm tests assert observable behavior rather than mocks or implementation details alone.

Look for omissions as well as bad lines: an absent authorization check, migration/backfill, rollback path, compatibility shim, negative test, error mapping, metric, or cleanup may be the defect.

## 4. Verify candidate findings

Before reporting a candidate:

- Read enough surrounding code to rule out a guard or invariant elsewhere.
- Search call sites, types, schemas, configuration, and tests for contradictory evidence.
- State the inputs and system state that trigger the problem.
- Trace the consequence to a user, system, data, security, or operational impact.
- Use a focused read-only check or targeted test when it materially increases confidence.
- Distinguish a proven defect from a question or residual risk.

Do not report:

- style preferences already settled by the repository;
- theoretical problems with no plausible trigger or impact;
- issues outside the review scope that the change neither introduces nor worsens;
- duplicate findings for one root cause;
- missing tests without naming the important behavior that can regress;
- compatibility concerns when the repository explicitly permits the break.

If evidence remains incomplete, put the item under **Open questions** or **Residual risks**, not **Findings**.

## 5. Use proportionate verification

Start with the cheapest relevant verification:

1. Existing targeted tests for changed behavior.
2. Type checking, linting, or static analysis scoped to affected code.
3. A focused reproduction for a suspected defect.
4. Broader suites only when the blast radius justifies them.

Respect repository guidance. Ask before expensive, slow, flaky, destructive, privileged, or live-networked checks unless already authorized. Never claim a command passed if it was not run. Record commands, results, and important limitations.

A passing test suite is evidence, not proof. Review whether the tests cover the changed contract and whether assertions can fail for the right reason.

## 6. Assign severity from impact

- **P0 — Critical:** credible path to catastrophic loss, broad compromise, unrecoverable corruption, or severe production outage. Immediate stop-ship.
- **P1 — High:** merge-blocking correctness, security, data-integrity, availability, or contract defect with a realistic trigger.
- **P2 — Medium:** material defect or design/test gap likely to cause bounded failures, regressions, or costly operations. Usually fix before merge unless explicitly accepted.
- **P3 — Low:** real but limited issue with low impact. Include only when actionable and worth the author's time.

Severity reflects impact and likelihood, not fix effort. Do not inflate severity to make a finding noticeable.

## 7. Produce the review

Lead with findings, ordered by severity and then by execution flow. Use current file lines rather than patch line numbers.

```markdown
## Findings

### [P1] Imperative, consequence-focused title
- Location: `path/to/file.ext:123`
- Impact: Who or what fails, and how badly.
- Evidence: Concrete triggering inputs/state and the traced failure mechanism.
- Recommendation: Smallest direction that removes the risk; do not write the patch.

## Open questions
- Only questions whose answers could change the verdict or severity.

## Review summary
- Scope: Exact diff/range/files reviewed.
- Intent: One-sentence interpretation of the change.
- Verification: Commands run and results, or "Not run" with reason.
- Residual risks: Important areas not proven or not reviewed.
- Verdict: `CHANGES REQUESTED`, `APPROVE WITH FOLLOW-UPS`, or `APPROVE`.
```

For a clean review, write `No findings.` under **Findings** and still provide the summary, verification, residual risks, and verdict.

Verdicts:

- `CHANGES REQUESTED`: any P0/P1, or a P2 that makes the change unsafe to merge.
- `APPROVE WITH FOLLOW-UPS`: no blocker, but bounded P2/P3 work or an explicit operational follow-up remains.
- `APPROVE`: no actionable finding in scope; residual risk may still be stated.

Keep the report concise enough to act on. Explain why each finding matters; do not narrate the entire review process.

## Completion check

Before returning:

- The scope and merge base are explicit.
- Intent and material assumptions are explicit.
- Relevant high-risk paths were traced end to end.
- Each finding has a location, trigger, consequence, and actionable direction.
- Candidate findings were checked against surrounding code and tests.
- Verification claims are exact.
- Coverage gaps and unreviewed areas are visible.
- The verdict follows from the findings.

