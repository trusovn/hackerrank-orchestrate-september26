---
name: task-acceptance-review
description: Independently review one bounded implementation against its request or task brief, scoped diff, tests, and material risks, then return ACCEPT, CHANGES_REQUESTED, or INCONCLUSIVE. Use for direct manual implementations as well as orchestrated worker results, especially when task metadata requires immediate review or behavior crosses stateful, public, security, concurrency, recovery, or migration boundaries. Default to a concise guided review; require full packet/digest reconstruction only for explicit high-assurance work.
---

# Task Acceptance Review

Decide whether one bounded implementation is safe to advance. Corroborate the
claims most likely to hide defects instead of recreating the implementer's
entire process. Account for the task's explicit finite risks before spending
the review budget on broad regression.

Repository and user instructions outrank this skill. Preserve pre-existing user
work. Ordinary review is read-only except for an authorized report artifact.

## Establish reviewer provenance first

Independence is a property of session authorship, not of the skill text or role
currently loaded. Before reviewing evidence or issuing a verdict, determine
whether this session authored any production bytes in the reviewed diff.

- An independent session continues to the review profiles below.
- A session that authored reviewed production bytes may perform a clearly
  labeled `SELF_CHECK_ONLY`, but it must not issue `ACCEPT`,
  `CHANGES_REQUESTED`, or `INCONCLUSIVE`. Loading this skill does not reset
  authorship. The route is always a fresh reviewer.
- `SELF_CHECK_ONLY` is a non-verdict conversational/report label, not an
  orchestrator status and never advances work.
- If an independent reviewer later writes an authorized tests-only reproducer,
  its pre-write verdict remains final for that session. Corrected production
  bytes require a new reviewer; the reproducer-writing session cannot accept
  them.

## Choose the profile

Use `guided` by default. Use `high-assurance` when explicitly requested or when
the review is given a preflight packet, machine worker result, run policy, and
durable acceptance path from an orchestrated flow.

### Guided inputs

Require enough to identify:

- the user request, task brief, or acceptance criteria;
- the current task-owned diff or changed paths;
- implementation and verification claims, if available; and
- repository instructions and permissions for independent checks.

Do not return `INCONCLUSIVE` merely because no preflight packet, digest ledger,
worker JSON, or report path exists. Reconstruct the relevant scope from current
Git state and the task conversation/artifact when it is safely separable.

### High-assurance inputs

Require the exact task brief, ready preflight packet, worker result, recorded
baseline, run policy, and authorized report path. Inconsistency, stale authority,
or an inseparable baseline is `INCONCLUSIVE`; do not downgrade silently.

Treat implementer summaries and passing commands as submitted claims, not
independent proof in either profile.

## Review workflow

1. Establish provenance, then read applicable instructions, the task contract,
   scoped diff, implementation evidence, and any prior review continuation.
   Confirm the outcome, allowed scope, profile, and current byte identity when
   available.
2. Reconstruct task ownership before behavioral probes:
   - compare changed paths with stated scope and implementation claims;
   - separate pre-existing user work, task changes, and runtime artifacts;
   - treat unexplained or inseparable overlap as `INCONCLUSIVE`.
   In high-assurance mode, also compare every recorded Git, index/worktree,
   authority, policy, dependency, and environment identity.
3. Build a concise completeness ledger before running a broad suite. Give each
   row a stable task-derived identity and record:
   `AC/invariant → explicit cases → submitted evidence → independent probe →
   pass | fail | blocked | unchecked, with reason`.
   - Start with explicit contract cases and the material dimensions of selected
     high-risk invariants; do not turn review into open-ended repository
     archaeology.
   - Consume a supplied prior ledger as continuation context. Preserve its row
     identities, but corroborate current bytes: a prior `pass` guides probe
     selection and is not current acceptance evidence.
   - Separate required/material rows from optional risks so every required row
     has a visible disposition when review ends.
   - Derive and freeze the required/material rows from the contract, scoped
     diff, and selected risk dimensions before the broad gate. The aggregate
     suite is not a substitute for discovering missing adversarial rows.
4. Batch narrow static traces and targeted adversarial probes across the ledger
   before any aggregate gate. Review public entry points, state transitions,
   side effects, error paths, cleanup, and compatibility where relevant.
   Continue after a finding while remaining probes are independent, safe,
   authorized, and affordable. A first defect does not imply sibling rows are
   clean.
5. Check the lowest-level contract and the real public/decisive boundary when
   both matter. Passing unit tests cannot replace public wiring evidence. For
   repeated, resumed, retried, recovered, paginated, or migrated behavior,
   independently execute the first occurrence, observe or apply its legitimate
   state change, then execute the next real occurrence in authorized disposable
   state. Do not infer the second occurrence from a pure function or worker
   claim.
6. Decide broad-gate ownership explicitly:
   - Immediately before launching a broad gate, reconcile the frozen ledger
     against the task contract and scoped diff. Proceed only when every safely
     runnable required/material row has current targeted evidence, every
     blocked/unchecked row has a concrete non-gate blocker, and no selected
     adversarial probe remains.
   - Discovery review runs targeted adversarial evidence first. After any
     decisive targeted failure in the current review, skip the broad/aggregate
     gate unless it has a distinct authorized diagnostic purpose; do not run it
     merely for completeness.
   - A fresh final review after correction reruns reviewer regressions,
     corroborates every required row against the corrected bytes, completes
     previously blocked/unchecked rows, runs justified owning checks, and owns
     the aggregate gate once after adversarial evidence is clean.
   - Another correction cycle is legitimate when correction introduces a new
     defect, an earlier defect blocked downstream evidence, or authority
     changes.
   - If later evidence reveals an omitted material row, record the earlier
     broad gate as premature rather than final evidence. Run the missing
     targeted probe, then rerun the broad gate only when targeted evidence is
     clean and the gate remains justified.
   Record the exact command or `not run`, owner, stage, and reason.
7. Validate each candidate finding against surrounding code and observed
   behavior. Assign each confirmed finding a stable ID such as `F-01`. Include
   severity, location, demonstrated trigger, consequence, evidence, affected
   AC, broken invariant, an explicit credible contract-implied sibling surface,
   and the smallest invariant-level corrective direction. Never leave the
   sibling surface implicit. Do not give a patch or a demonstrated-field-only
   special case. Keep unproved questions, residual risks, and unchecked ledger
   rows separate from confirmed findings.
8. Finish every ledger row. If work stops early, mark each remaining
   required/material row `blocked` or `unchecked` with the concrete reason.
   `CHANGES_REQUESTED` never means unreported areas are clean.
9. Return one independent verdict, or `SELF_CHECK_ONLY` when provenance
   requires it, plus the broad-gate decision and exact next route. Write a
   durable report only when requested or required by high-assurance mode.
10. Reconcile the final output before returning. Confirm that every finding has
    its stable ID and required fields, the continuation names every finding ID
    and reviewer regression separately, all ledger rows are present, and the
    broad-gate record matches the actual command order. Do not compress away a
    required field in guided output.

## Adversarial checks for stateful work

Apply the relevant checks, not a generic exhaustive matrix:

- Cross product selected/current entities with non-selected entities so a
  valid primary state cannot hide an invalid sibling state.
- When the invariant says exactly one owner/active/current item, test zero, one,
  and two distinct owners.
- Verify current/active attempt ordering against the latest attempt, not merely
  membership or existence.
- Compare the exact ready/eligible set with dependency state; “at least one
  ready” is insufficient when all eligible items must be represented.
- Check terminal states against every subordinate state so stopped/complete
  parents cannot retain running children.
- Reject type confusions such as booleans accepted as integers and strings
  accepted as collections when those values cross persistence or API
  boundaries.
- For tamper claims, modify related evidence coherently, including recomputed
  internal digests. A digest stored with mutable evidence proves consistency,
  not immutability; stronger claims need an independent anchor.

Choose these cases because they catch interacting invariant failures that
ordinary happy-path and one-field corruption tests routinely miss.

## Verdict and routing rules

An independent reviewer uses exactly one verdict:

- `ACCEPT`: all required ACs and justified gates are independently satisfied,
  scope is clean, and no blocking finding or question remains.
- `CHANGES_REQUESTED`: a concrete in-scope production or test defect can be
  corrected without changing authority, scope, dependencies, permissions, or
  required infrastructure.
- `INCONCLUSIVE`: ambiguous authority, inseparable scope, missing decisive
  capability, stale high-assurance inputs, environment/permission failure, or
  an unverified required boundary prevents a truthful decision.

`SELF_CHECK_ONLY` sits outside these verdicts. Use it only when the current
session authored reviewed production bytes; do not mislabel missing
independence as `INCONCLUSIVE` or a clean acceptance.

Route `CHANGES_REQUESTED` to the same implementation thread when possible.
After any correction, run a fresh acceptance review against the corrected bytes;
never reuse or append acceptance to the prior verdict as if it still applied.

Route contract defects to the user or `task-brief-designer`; current-state or
high-assurance freshness failures to `task-preflight`; and wider scope/shared
infrastructure back through brief design. Only an `ACCEPT` verdict may advance
an orchestrated task.

## Output contract

For guided review, default to a concise human-readable response:

```markdown
Verdict: ACCEPT | CHANGES_REQUESTED | INCONCLUSIVE
or
SELF_CHECK_ONLY — not an independent verdict

Findings:
- F-01 [P1] <location, trigger, consequence, evidence, affected AC, broken invariant, explicit sibling surface, direction>

Coverage:
- <stable row ID: cases, submitted evidence, independent probe, pass/fail/blocked/unchecked + reason>

Broad gate: <run/not run, command/owner, reason>
Questions / unchecked work: <separate summary>
Scope / residual risk: <summary>
Next: <one exact route>

Review continuation:
- Iteration / current byte identity: <value when available>
- Coverage rows: <all row IDs and results>
- Finding IDs: <all stable finding IDs or none>
- Reviewer regressions: <paths and exact commands or none>
- Broad gate: <status and reason>
- Next: <exact route>
```

Say `No findings.` when evidence is clean. Do not create a report file unless
the user requested one. A continuation block is required for
`CHANGES_REQUESTED`, `INCONCLUSIVE`, `SELF_CHECK_ONLY`, or any review with
blocked/unchecked rows; keep it compact and copyable.

For high-assurance review, read
`references/acceptance-report-template.md`, write exactly one report, and
include the full baseline/freshness and command records. The report is the only
intentional write during the verdict phase; the separately authorized
post-verdict tests-only protocol is the sole later exception.

Give a fresh reviewer the task brief, current scoped diff, preceding verdict and
continuation block, reviewer regression paths/commands, and every
blocked/unchecked row. Do not invent a new machine schema before an orchestrator
owns it. Only an independent `ACCEPT` advances work.

## Conditional post-verdict tests-only reproducer

`tests_only_reproducer` is an optional mode of this same review session, not a
production-writing role. It is available only after all of these are true:

1. the independent verdict is fixed and already reported as
   `CHANGES_REQUESTED`;
2. the current user or exact review invocation explicitly authorizes
   `tests_only_reproducer`; and
3. that authorization names the exact writable owning test file or bounded test
   area.

Task scope, an allowed test path, or `review: immediate` is not write
permission. If any precondition is absent, remain read-only and do not load the
procedure. When all are satisfied, read
`references/tests-only-reproducer.md` and follow it without loading
`bounded-task-implementer`. The verdict stays `CHANGES_REQUESTED`; production
repair and same-session acceptance remain prohibited.

When this mode runs, keep the authorization source, exact allowed path, exact
pre-write status, exact post-write status, and diff side effects as distinct
reported fields. The final audit must compare those records rather than merely
state that scope was preserved.

## Boundaries

Do not implement fixes, edit reviewed files, update task briefs/plans/trackers,
advance orchestration, commit, launch subagents, or run unauthorized slow,
flaky, destructive, privileged, live, or networked probes. The sole repository
write exception is the explicit post-verdict tests-only protocol above.

## Definition of done

- Reviewer provenance is explicit; an authoring session cannot issue an
  independent verdict.
- Scope is safely separated from user work.
- Every required/material ledger row is `pass`, `fail`, `blocked`, or
  `unchecked` with a reason, using current evidence for the reviewed bytes.
- Relevant lifecycle and interacting-state risks receive adversarial evidence.
- Independent findings are batched where safe; findings name the invariant and
  bounded sibling surface and carry stable IDs; clean work gets no invented
  finding.
- Broad-gate ownership and suppression after decisive failure are visible.
- Exactly one justified verdict or `SELF_CHECK_ONLY`, residual-risk statement,
  continuation when required, and next route are present.
