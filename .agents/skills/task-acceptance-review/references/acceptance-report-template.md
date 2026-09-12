# Task Acceptance Report: `<TASK-ID>` — `<brief title>`

| Field | Value |
|---|---|
| Verdict | `ACCEPT | CHANGES_REQUESTED | INCONCLUSIVE | none — SELF_CHECK_ONLY` |
| Non-verdict provenance label | `N/A | SELF_CHECK_ONLY` |
| Producing stage | `task-acceptance-review` |
| Review iteration | `<first review or correction number>` |
| Created at | `<ISO-8601 timestamp with timezone>` |
| Repository root | `<absolute path>` |
| Durable report path | `<authorized runtime path>` |
| Task brief | `<exact path and preflight-recorded SHA-256>` |
| Preflight packet | `<exact path>` |
| Implementer result | `<exact corrected/current path and status>` |
| Run policy | `<identifier and path>` |

This report applies only to the reviewed bytes and artifacts identified below.
Any correction requires a new report and verdict.

## 1. Reviewer provenance

| Question | Evidence |
|---|---|
| Did this session author any reviewed production bytes? | `no — independent | yes — SELF_CHECK_ONLY` plus `<session/diff evidence>` |
| Independent verdict authority | `yes | no — fresh reviewer required` |
| Current byte identity | `<HEAD plus scoped diff identity when available>` |

Independence follows session authorship, not the currently loaded skill. When
the answer is `yes`, label the report `SELF_CHECK_ONLY`, set the summary and
detailed verdict fields to `none — SELF_CHECK_ONLY`, and route to a fresh
reviewer. Do not use `INCONCLUSIVE` to describe missing independence.

## 2. Findings, ordered P0 through P3

Use `No findings.` when no concrete defect exists.

### F-01 [P1] `<consequence-focused title>`

| Field | Evidence |
|---|---|
| Finding ID | `F-01` |
| Current location | `<repository-relative path:line>` |
| Triggering state/input | `<specific reproducible precondition and action>` |
| Consequence | `<user, data, system, contract, or operational impact>` |
| Evidence | `<trace, independent probe, command result, or code fact>` |
| Affected AC | `<AC-ID>` |
| Broken invariant | `<task-authorized property that does not hold>` |
| Credible sibling surface | `<contract-implied cases sharing that invariant>` |
| Smallest corrective direction | `<invariant-level bounded direction; no patch or field-local special case>` |

Keep confirmed findings separate from unproved questions and from unchecked
coverage rows. Continue through independent safe rows after the first finding.

## 3. Completeness ledger

Use stable task-derived row IDs. Consume a supplied prior ledger without
renaming rows, but rerun enough evidence for the current bytes; prior `pass`
guides the review and is not current proof.

| Row ID | AC / invariant | Explicit material cases | Submitted evidence | Independent probe / current evidence | Result / reason |
|---|---|---|---|---|---|---|
| `<stable ID>` | `<observable contract>` | `<finite values/state transitions>` | `<worker claim or N/A>` | `<entry point, boundary, observed result or exact gap>` | `pass | fail | blocked | unchecked — <reason>` |

Passing worker tests are submitted claims until independently corroborated.
Every required/material row must have one of the four results before the review
ends. `CHANGES_REQUESTED` does not imply that unlisted areas passed.

## 4. Adversarial state and evidence checks

Include only rows relevant to this task.

| Ledger row / invariant | Cases exercised | Result and evidence |
|---|---|---|
| Selected versus non-selected state coherence | `<cross-product cases>` | `<result>` |
| Exact cardinality | `<zero, one, and two owners/items>` | `<result>` |
| Latest/current ordering | `<older, latest, missing, duplicated>` | `<result>` |
| Exact ready/eligible set | `<missing, exact, extra>` | `<result>` |
| Parent/child terminal coherence | `<running child under stopped/complete parent>` | `<result>` |
| Persisted type strictness | `<boolean/int, string/collection, other relevant confusions>` | `<result>` |
| Coherent tampering | `<related bytes and internal digests rewritten together>` | `<consistency-only, independently anchored, or defect>` |

## 5. Independent probes and command results

| ID | Exact command / probe | Working directory / environment | Purpose / ACs | Result and observed signal | Side effects / disposition | Independence / gap |
|---|---|---|---|---|---|---|
| `REV-01` | `<exact command or reproducible probe>` | `<cwd and disposable state>` | `<claim>` | `<exit and observation>` | `<none or paths/cleanup>` | `<independent evidence or limitation>` |

Record required-but-unrun checks with the exact capability, permission, or
environment blocker. Never copy a worker's `passed` label as reviewer evidence.

## 6. Broad-gate decision

| Field | Value |
|---|---|
| Gate / exact command | `<command or N/A>` |
| Status | `passed | failed | not run | blocked` |
| Owner and stage | `<discovery reviewer | correction implementer | fresh final reviewer>` |
| Reason | `<why justified, or decisive targeted failure that suppressed it>` |

A discovery review does not run the broad/aggregate gate merely for
completeness after a decisive targeted failure. A fresh final reviewer owns it
once, after reviewer regressions and all required targeted rows are clean.

## 7. Scope and baseline comparison

| Item | Preflight baseline | Current reviewed state | Classification / evidence |
|---|---|---|---|
| `HEAD` | `<SHA or unborn>` | `<SHA or unborn>` | `<expected or unexplained>` |
| Exact `git status --short` | `<verbatim baseline or clean>` | `<verbatim current>` | `<task, user, runtime, unexplained>` |
| Dirty path index/worktree identities | `<separate states/digests>` | `<separate states/digests>` | `<ownership/separability>` |
| Task-owned paths | `<allowed paths>` | `<scoped diff and worker files_changed>` | `<in scope or mismatch>` |
| Runtime artifacts | `<declared paths>` | `<observed paths>` | `<authorized/disposition>` |
| Authority / policy / dependencies | `<recorded identities>` | `<current comparison>` | `<unchanged or invalidation>` |

State the exact diff/range/files reviewed. Do not absorb pre-existing user work.

## 8. Questions, unchecked work, and residual risks

| Type / row ID | Evidence or reason unverified | Blocking? | Owner / follow-up |
|---|---|---|---|
| `question | blocked | unchecked | residual risk` | `<observed limit>` | `yes | no` | `<owner/action>` |

A failed required behavior is a finding, not residual risk. A missing required
oracle is blocking and normally yields `INCONCLUSIVE`.

## 9. Verdict and next route

| Field | Value |
|---|---|
| Verdict | `ACCEPT | CHANGES_REQUESTED | INCONCLUSIVE | none — SELF_CHECK_ONLY` |
| Basis | `<findings, evidence, scope, commands, questions>` |
| Next owner | `<orchestrator, same implementer thread, preflight, brief designer, or user>` |
| Exact next action | `<one smallest action>` |

- `ACCEPT` may route to authorized advancement.
- `CHANGES_REQUESTED` routes to correction followed by a fresh review.
- `INCONCLUSIVE` routes to the owner of the authority, freshness, capability,
  environment, permission, or scope blocker.
- `SELF_CHECK_ONLY` is not a verdict and always routes to a fresh reviewer.
- Only an independent `ACCEPT` may advance work.

## 10. Review continuation

Copy this compact block intact into the next review context:

```markdown
Review continuation:
- Iteration / current byte identity: <iteration; HEAD/scoped diff identity>
- Coverage rows: <every stable row ID = pass/fail/blocked/unchecked + reason>
- Finding IDs: <all IDs or none>
- Reviewer regressions: <paths and exact focused commands, or none>
- Broad gate: <status, exact command/owner, reason>
- Next: <one exact route>
```

A fresh reviewer must also receive the task brief, current scoped diff,
preceding verdict/report, reviewer regressions, and all blocked/unchecked rows.
Prior row results are navigation context, not proof for corrected bytes.

## 11. Post-verdict reproducer (optional)

Include this section only when the fixed independent verdict is
`CHANGES_REQUESTED` and the current invocation explicitly authorized
`tests_only_reproducer` for the exact path or bounded area. Read
`tests-only-reproducer.md` before writing.

| Field | Evidence |
|---|---|
| Authorization source | `<current user/invocation text>` |
| Exact writable test path/area | `<allowlisted path>` |
| Changed tests | `<exact paths only>` |
| Focused command / result | `<command, exit, intended assertion failure>` |
| Intended failure signal | `<contract violation, not harness/import/setup failure>` |
| Pre-write `git status --short` | `<verbatim status>` |
| Post-write `git status --short` | `<verbatim status>` |
| Diff side effects | `<authorized test diff, production unchanged, cleanup>` |
| Next route | `authorized correction, then fresh independent review` |

The verdict remains exactly `CHANGES_REQUESTED`. This session may not repair
production or accept corrected bytes.
