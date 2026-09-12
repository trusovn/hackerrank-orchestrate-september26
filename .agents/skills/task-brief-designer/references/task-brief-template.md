# Task Brief: `<TASK-ID>` — `<imperative title>`

Status: `ready | ready_for_preflight | blocked_design`

When the status is `blocked_design`, do not use the implementation template
below. Emit only this abbreviated design-block form and stop:

```markdown
# Design block: `<requested outcome as stated>`

Status: `blocked_design`

## Missing decisions or authority

- `<decision or authority gap; why it materially changes the task>`

## Owner and smallest next action

- Owner: `<user or named decision owner>`
- Next: `<smallest planning/approval action>`
```

Do not add launch metadata, a readiness route, proposed architecture,
implementation scope or paths, work items, implementation acceptance criteria,
finite-risk cases, verification obligations, or an implementation handoff.
The remaining template applies only to `ready` and `ready_for_preflight`.

```yaml
agent_tier: mechanical | standard | strong
reasoning: low | medium | high
review: mechanical | milestone | immediate
budget: <tool calls> / <time> / <context>
```

These four scalar values are intended launch guidance for future automated or
current manual routing. Use the profile approved by the authority; do not
present `reasoning` or another value as observed runtime configuration unless
it was supplied. Treat the budget as a soft checkpoint unless authority makes
it hard.

## Readiness route

`<implementer self-preflight | standalone guided preflight — concrete material uncertainty | high-assurance preflight>`

Use implementer self-preflight for routine guided work. Recommend standalone
guided preflight only with the concrete material readiness uncertainty that it
should resolve. Use high-assurance preflight when that profile is required.
This is human-readable guidance, not a fifth metadata key; current execution
facts may still require escalation.

## Outcome

`<One testable sentence describing the approved result.>`

## Direction trace

Include this section when governing direction was supplied. Omit it otherwise.

- Direction contribution: `<approved outcome, scenario, priority, or boundary
  this task advances>`
- User-observable effect: `<direct effect, or "No direct effect; enables
  <next demonstrable outcome>">`
- Why now: `<approved sequence or real technical dependency leading toward the
  next demonstrable outcome>`
- Direction decisions used: `<exact paths, sections, or decision IDs>`
- New direction decisions required: `None`

If `New direction decisions required` cannot truthfully be `None`, do not use
this template or produce an implementation-ready brief. Return the
plain-language direction-delta-needed response and stop. Do not use "Why now"
to invent priority or ordering that the supplied authority does not establish.

## Authority and scope

| Item | Contract |
|---|---|
| Authority | `<user request, issue, plan/spec path and section, or other source>` |
| Repository root | `<absolute path or working repository>` |
| Dependencies | `<IDs/states or none>` |
| Allowed changes | `<exact paths when known, otherwise bounded area for focused discovery>` |
| Read-only context | `<closest authority, precedent, or owning tests>` |
| Out of scope | `<adjacent work, permissions, or prohibited actions>` |
| Assumptions / unresolved decisions | `<none, UNKNOWN facts for discovery, or blocking decision and owner>` |

For an existing adequate brief, preserve its equivalent sections instead of
rewriting them into this table.

## Work and acceptance criteria

Required work:

1. `<Small implementation outcome.>`
2. `<Small implementation outcome.>`

- **AC-01:** `<Observable positive behavior or invariant.>`
- **AC-02:** `<Most credible negative, failure, or unchanged-state behavior.>`
- **AC-03:** `<Lifecycle, compatibility, or boundary behavior when relevant.>`

Omit AC-03 when it adds no distinct protection. Add more ACs only for distinct
approved outcomes.

### Finite-risk coverage contract (optional)

Include this subsection only when authority contains a universal or lifecycle
claim with finite, material cases whose omission could permit false success.
Omit it for tasks without such dimensions; do not fill it with generic test
categories or speculative cases.

| Invariant | Material dimensions/cases | Decisive oracle/boundary | Implementation evidence | Independent review probe | Gate owner |
|---|---|---|---|---|---|
| `<property that remains true>` | `<exact finite values or state transitions>` | `<observable outcome at the real boundary>` | `<fail-first, targeted, or owning evidence>` | `<distinct corroboration/adversarial probe, or N/A with reason>` | `<owner and stage for owning/broad gate>` |

Combine cases only when they share one invariant and oracle; this table does
not require a Cartesian product. Keep implementation evidence distinct from
independent review. For immediate-review correction, assign the broader or
aggregate gate to either the correction implementer or the final fresh
reviewer, and keep targeted evidence first while it remains red. Keep row
identity stable so later reviews can record `pass`, `fail`, `blocked`, or
`unchecked`; a prior result does not prove corrected bytes. Use exactly these
six semantic columns; do not replace them with a smaller requirements table and
move evidence roles or gate ownership elsewhere.

## Verification

| Evidence | Scenario and oracle | Command |
|---|---|---|
| Fail-first / regression | `<how the test rejects missing or faulty behavior, or why infeasible>` | `<exact command or focused discovery owner>` |
| Targeted | `<lowest reliable behavior and boundary>` | `<exact command or focused discovery owner>` |
| Owning suite | `<nearby regression coverage>` | `<command or N/A with reason>` |
| Broader gate | `<blast radius covered, owner, and execution stage>` | `<command, approval required, or N/A with reason>` |

For repeated, resumed, retried, recovered, paginated, or migrated behavior,
include the first occurrence, its legitimate state change, and the next real
occurrence. Pure state simulation is insufficient when public wiring is the
risk.

## Stops and handoff

- Stop for ambiguous authority, user-work overlap, unsafe permission needs,
  material scope expansion, or a missing decisive verification capability.
- Treat the metadata budget as a checkpoint unless explicitly declared hard.
- Preserve pre-existing user work.
- Next action: `<guided implementation | standalone guided preflight and reason | high-assurance preflight | decision owner>`.
- When `review: immediate`, preserve implementation as the next action and add:
  `Required follow-on: immediately after implementation or correction, hand
  the completed bytes to a fresh independent acceptance reviewer.` Do not use
  same-session self-review as that acceptance step.

---

## High-assurance addendum

Include this addendum only when status is `ready_for_preflight` or when a
specific risk requires durable evidence. Do not add it to routine guided tasks.

### Artifact identity

| Field | Value |
|---|---|
| Task ID | `<stable ID>` |
| Producing stage | `task-brief-designer` |
| Created at | `<ISO-8601 timestamp with timezone>` |
| Primary authority | `<path>#<exact section>` |
| Known policy | `<identifier/path or UNKNOWN for preflight>` |

### Knowledge ledger

| Kind | Path or statement | Relevance / owner |
|---|---|---|
| Confirmed fact | `<fact and source>` | `<effect on task>` |
| Frozen decision | `<authority-entitled decision>` | `<source>` |
| Assumption | `<provisional fact>` | `<how preflight confirms it>` |
| Unresolved item | `<none or blocker>` | `<owner and smallest next action>` |

### AC execution matrix

| AC | Production invariant | Positive evidence | Negative evidence | Real entry point / boundary | Repeated or recovery path | Verification dependency |
|---|---|---|---|---|---|---|
| AC-01 | `<invariant>` | `<scenario/oracle>` | `<scenario/oracle>` | `<public workflow and boundary>` | `<first + state change + next, or N/A with reason>` | `<existing, task-local, prerequisite, or gap>` |

### Legacy-assumption and risk checks

| Area / search | Risk | Required evidence or follow-through |
|---|---|---|
| `<entry point, guard, literal, identifier, path, or baseline assumption>` | `<credible stale assumption>` | `<focused search/test>` |

| Risk | Impact / escalation trigger | Evidence and residual gap |
|---|---|---|
| `<credible failure>` | `<consequence>` | `<test level, real boundary, gap or none>` |

### Verification-capability inventory

| Needed capability | Disposition | Owner / path | Preflight confirmation |
|---|---|---|---|
| `<fixture/helper/runner/oracle>` | `task-local | prerequisite task | believed existing | blocked` | `<path or task>` | `<exact existence/interface question>` |

### High-assurance handoffs

- Preflight must confirm exact paths, dependencies, ownership, permission
  envelope, command syntax, decisive oracles, and required freshness evidence.
- Implementation may change only confirmed scope, must record every required
  command truthfully, and must produce the supplied structured result.
- Independent review must reconstruct the scoped diff, corroborate every AC at
  the required boundary, and issue a fresh verdict after every correction.
