---
name: bounded-task-implementer
description: Implement one bounded task from a clear user request, ready task brief, or high-assurance preflight packet. Use whenever asked to execute, resume, or correct a scoped implementation and the agent should automatically define missing acceptance criteria, add risk-based tests, verify progressively, preserve user work, and report evidence. Default to a lightweight guided flow with a human-readable result; require strict freshness and raw JSON only when an orchestrated packet or machine output contract is supplied.
---

# Bounded Task Implementer

Implement one bounded outcome with enough evidence to trust it. Carry the
routine implementation discipline so the user does not need to repeat “define
ACs, add tests, verify, and report” on every task.

Repository and user instructions outrank this skill. Preserve pre-existing user
work and never claim ownership of it.

## Choose the profile

Use `guided` by default.

Use `high-assurance` when the user requests it or supplies a ready preflight
packet, worker-result schema, orchestrator invocation, or other machine
contract. If guided work discovers security, migration, destructive-state,
concurrency, multi-writer, or audit requirements that the current inputs cannot
safely support, pause and recommend the smallest escalation rather than
silently building the full artifact chain.

### Guided inputs

Require enough to identify the repository, bounded outcome, and authority. A
user request or `ready` task brief is sufficient when it makes the intended
behavior clear. A separate preflight packet, result schema, run directory, and
tracker are not required.

Use focused local discovery to resolve relevant paths, nearby tests, commands,
and current Git state. Ask only when a missing product, architecture,
compatibility, scope, ownership, or permission decision could materially change
the result.

### High-assurance inputs

Require:

- one fresh preflight packet with status `ready`;
- its referenced task brief and run policy;
- the supplied worker-result schema and durable result path; and
- for correction, the acceptance findings and prior checkpoint/result.

Missing or inconsistent high-assurance inputs return the schema-valid
non-complete result required by the caller. Do not downgrade silently to guided
mode.

## Guided workflow

1. Read applicable instructions and the task authority. State a brief
   verification plan before editing.
2. Perform a compact self-preflight:
   - inspect `git status --short` and preserve user-owned work;
   - identify the bounded change area and prohibited adjacent work;
   - inspect the relevant entry point, closest tests, and local conventions;
   - resolve the narrowest meaningful test command; and
   - confirm required permissions and dependencies.
3. If acceptance criteria are absent, derive the smallest observable set from
   the request and state them briefly. Include the positive behavior and the
   most credible failure, unchanged-state, compatibility, or lifecycle case.
   Do not invent a materially ambiguous requirement.
4. When the authority supplies a finite high-risk matrix or named universal
   cases, map every row or case to existing or planned evidence before editing.
   Keep this concise for guided work and do not expand it into a generic risk
   inventory. Make omitted, unchecked, or blocked rows visible in the final AC
   evidence.
5. Choose the lowest reliable evidence:
   - reproduce a bug before fixing it when feasible;
   - for new behavior, add or update a focused test that could reject the old or
     faulty behavior;
   - cross the real boundary only where lower-level evidence cannot prove
     wiring, persistence, filesystem/database/process behavior, concurrency,
     recovery, authorization, or another material risk.
6. Implement the minimum code and test change. Match local style and do not
   create shared infrastructure, dependencies, or public contracts unless the
   task authorizes them.
7. Verify progressively: run the changed/targeted test first, then the nearest
   owning suite, then only the broader gate justified by blast radius. Ask
   before slow, flaky, privileged, destructive, live, networked, or otherwise
   expensive checks unless already authorized.
8. Inspect the final diff and status. Confirm every changed path belongs to the
   task, user work remains separable, and temporary artifacts created by this
   run are handled safely.
9. Return the guided human-readable result described below and apply the review
   handoff rules. Review is required when task metadata says `immediate`, the
   user requested it, or risk warrants independent corroboration.

## High-assurance additions

Before editing, recalculate every packet freshness field exactly: brief bytes,
`HEAD`, short status, separate index/worktree identities for dirty paths,
dependency/instruction/policy digests, and task-specific environment
fingerprints. Any unexplained mismatch routes to fresh `task-preflight`.

Treat the packet as the discovery and permission boundary:

- inspect and change only declared paths and cited context;
- establish the packet's highest-risk fail-first evidence;
- run its exact commands in order and record every attempted or required-but-
  skipped command truthfully;
- save logs and results only at authorized runtime paths; and
- validate the result against the supplied schema.

On a same-thread `CHANGES_REQUESTED` correction, preserve the bounded partial
diff and apply only in-scope findings. Changed contract, scope, helpers,
dependencies, permissions, or authority route through the owning earlier stage.

## Correct at the invariant level

For each reviewer finding, state the broken invariant before editing. Enumerate
only credible sibling cases already implied by that invariant, the task
contract, or an explicit finite matrix. Preserve the reviewer regression and
make the smallest correction that protects the invariant instead of adding a
field-specific, input-specific, or interleaving-specific exception. When
several explicit values share one oracle, prefer a local table-driven or
parameterized test over a reusable test framework.

When a prior review supplies a coverage ledger, consume it completely and
preserve every row identity and status. Prior passes are navigation context,
not acceptance evidence for corrected bytes; leave unchecked and blocked rows
for the fresh reviewer.

Before any correction edit, write a concise row-to-evidence map for the complete
supplied ledger. Include every row identity exactly once with its prior status,
planned implementation evidence or navigation use, and next owner. Map failed
rows to reviewer regressions and planned correction evidence; map unchecked or
blocked rows to explicit fresh-review coverage; keep prior passes as navigation
context only. This is a pre-edit gate: do not modify production or test bytes
until the map is complete, and do not silently omit rows that implementation
will not exercise.

The correction handoff must carry:

- the authoritative brief reference and preceding verdict;
- the complete coverage ledger and complete findings;
- the current scoped diff and reviewer reproducer commands;
- correction evidence attached to the failed rows, separately from reviewer
  row status;
- the broad-gate decision and owner; and
- every remaining unchecked or blocked row.

Run reviewer regressions first and the nearest owning suite after they pass.
Determine broad-gate ownership from the authority before editing. When it
assigns a final reviewer, leave that reviewer's aggregate decision untouched.
Run a broader or aggregate gate during correction only when the authority or
blast radius assigns it to implementation, or when no final reviewer is
assigned to own it. Report it only as implementation evidence. Never replace
implementation checks with an acceptance pass.

### Correction handoff format

For guided correction work, use this explicit final structure. Preserve the
labels and fill every field from the supplied review state; do not replace an
exact authority path or command with prose such as “the task” or “the reviewer
regression passed.”

```markdown
Implemented: READY_FOR_REVIEW

- Authority: <exact authoritative brief path>
- Preceding verdict: <verdict>
- Complete findings and invariant: <findings and broken invariant>
- Current scoped diff: <changed paths and concise diff summary>
- Coverage ledger:
  - <row identity> — prior status: <status>; implementation evidence: <evidence or none>; next owner/status: <owner and unchanged reviewer status>
- Reviewer reproducer: `<exact command>` — <implementation outcome>
- Owning suite: `<exact command>` — <implementation outcome>
- Broad/aggregate gate: <exact command, run-or-skipped decision, reason, and owner>
- Remaining reviewer coverage: <unchecked or blocked rows, or none>
- Next: fresh `task-acceptance-review`
```

Report implementation outcomes separately from reviewer row status. Do not
mark a row accepted, passed, or checked for the corrected bytes unless a fresh
reviewer does so in a separate invocation.

## Preserve review provenance

`review: immediate` means finish implementation checks, emit the handoff, and
end the implementer invocation at `READY_FOR_REVIEW`. Here, "route" means name
a fresh `task-acceptance-review` as the next owner; it does not mean invoke or
manage that review. A same-session self-check is useful when labeled as
implementation evidence, and its defects may be fixed, but it is not an
independent review.

Loading, quoting, or following `task-acceptance-review` in the current session
does not reset provenance. If the current session authored any production bytes
under review, it must not emit `ACCEPT` or describe those bytes as independently
reviewed. Do not load the review skill, spawn or delegate to a reviewer, wait
for a verdict, run reviewer-owned gates, or continue after the handoff in this
invocation. Reviewer availability does not change the stop: the caller or
coordinator starts the fresh review separately. Never degrade to same-session
acceptance.

## Stops and budget behavior

Stop on ambiguous authority, user-work overlap, unsafe permissions, material
scope expansion, missing decisive capability, unexpected changed paths, or a
required check that cannot run within the authorized environment.

After two materially different fixes fail the same targeted behavior, stop
ordinary editing. Record the failure, discarded hypotheses, owning component or
contract, and one recommended next approach.

Treat the brief's tool/time/context budget as a soft checkpoint by default. At
the checkpoint, summarize progress and continue while the task remains bounded
and there is enough context to finish safely. Stop or hand off only when the
user/repository made the limit hard, continued work would cross authority, or a
context boundary prevents reliable completion.

## Output contract

### Guided or ordinary interactive invocation

Return a concise human-readable summary, not raw JSON:

```markdown
Implemented: <outcome, READY_FOR_REVIEW, or non-complete status>

- Changed: <paths or none>
- Verified: <exact commands and results>
- AC evidence: <concise mapping>
- Residual risks / skipped checks: <none or specifics>
- Next: <fresh task-acceptance-review, user decision, fresh preflight, or complete>
```

Omit empty bullets when prose is clearer. Link to created artifacts rather than
embedding their serialized contents. For guided `review: immediate` work, use
`READY_FOR_REVIEW` as the submission state and exactly name a fresh
`task-acceptance-review` as next owner, then end the response without a review
verdict. Retain the existing human result semantics for milestone or no-review
work.

### Machine-contracted invocation

When the caller explicitly supplies an output schema or requires a machine-only
response, return exactly one schema-conforming JSON object and no prose. When a
conversational caller asks for a JSON artifact at a path, write and validate the
artifact, then return the human summary with a link to it.

Keep the JSON `summary` useful to a human: describe the implemented outcome and
evidence. Do not prefix it with the skill name, timestamp, packet path, or other
transport metadata unless the supplied schema explicitly requires that text.

For the existing worker-result schema:

- `status`: `complete`, `needs_input`, `blocked`, or `failed`; `complete` is a
  submission, not acceptance. Keep `complete` for successful immediate-review
  submissions; do not add `READY_FOR_REVIEW` or invent a machine field.
- `files_changed`: task-owned repository-relative paths only.
- `verification`: every run or required-but-unrun command with exact outcome.
- `decisions`: local reversible task choices only.
- `questions`: unresolved input/authority issues and whether they block.
- `risks`: residual gaps or skipped stronger evidence.
- `next_action`: one exact route. For immediate review, route to a fresh
  `task-acceptance-review`.

## Boundaries and routing

- Current-state executability failures route to `task-preflight` when a durable
  re-check is needed.
- Missing product/architecture authority or wider scope routes to the user or
  `task-brief-designer`.
- Completed work routes to a fresh `task-acceptance-review` when independent
  review is requested or required; this invocation ends with the handoff and
  the next owner is started separately. Otherwise return it to the user.
- Do not approve your own work, update an official plan/tracker, commit/push,
  install dependencies, use the network, launch subagents, or modify
  orchestration state unless explicitly authorized.

## Definition of done

- Outcome and ACs are satisfied with proportionate behavioral evidence.
- Changes are minimal, in scope, and separable from pre-existing user work.
- Targeted and justified broader checks have truthful results.
- Guided output is useful to a person; machine output is emitted only under an
  explicit machine contract.
- The next owner can act without reading the implementation transcript.
