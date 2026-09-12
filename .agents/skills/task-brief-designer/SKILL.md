---
name: task-brief-designer
description: Create, tighten, or gap-check one bounded implementation task from a user request, issue, approved plan, specification, or existing brief. Use when asked to make work implementation-ready, define acceptance criteria and verification, split a task, prepare an agent handoff, or repair a task contract. Prefer a lightweight delta over rewriting an adequate brief. Do not implement, certify current repository readiness, or invent unresolved product or architecture decisions.
---

# Task Brief Designer

Turn one bounded task into a clear, testable contract. Preserve useful existing
material and add only what the implementer or reviewer needs.

Repository and user instructions outrank this skill. Preserve existing user
work and never claim ownership of it.

When supplied owner-confirmed direction governs the task, classify direction
authority before selecting a profile, status, or output artifact. If the task
would introduce or change a material practical consequence beyond that
direction, return only the direction-delta-needed response in the conversation
and leave the requested task path absent or unchanged. This route takes
precedence over `blocked_design`; unresolved architecture does not convert a
direction gap into a blocked implementation-task artifact. If the task remains
within the approved consequences, continue normally and do not require
direction to authorize consequence-neutral technical details.

## Choose the profile

Use `guided` by default. Use `high-assurance` only when the user requests it,
an orchestrated artifact chain is already in use, or durable audit/freshness
evidence is proportionate to security, migration, destructive-state,
concurrency, multi-writer, or similar risk.

### Guided

- Accept a user request, issue, plan section, specification, or existing brief
  as authority.
- If an existing task already has a clear outcome, bounded scope, acceptance
  criteria, and useful verification, do not rewrite it. Return a concise gap
  check or make only the requested/local missing additions.
- Produce a compact `ready` brief when a durable artifact is useful. The
  routine readiness route is implementer self-preflight. Recommend standalone
  guided preflight only for a named material readiness uncertainty.

### High assurance

- Require exact authority, dependency, policy, and artifact paths.
- Use the full template and status `ready_for_preflight` or `blocked_design`.
- Design durable evidence, verification-capability disposition, and explicit
  downstream handoffs for separate preflight and acceptance stages.

Do not upgrade a routine task merely because a fuller template exists. If a
guided task discovers a genuine high-assurance need, name the reason and the
smallest additional artifact or decision required.

## Minimum inputs

Require enough information to identify:

- the requested outcome and its authority;
- any supplied governing direction and the part this task is intended to
  advance;
- repository or working context;
- known scope, dependencies, and constraints; and
- any existing task artifact that should be preserved.

Use `UNKNOWN` for non-blocking facts that later repository inspection can
resolve. Stop with `blocked_design` only when a missing product, architecture,
compatibility, permission, or scope decision could materially change the task.
Do not block merely because paths, command syntax, or current Git state still
need focused discovery. Once `blocked_design` applies, use the abbreviated
blocked-design output and stop drafting: do not infer architecture,
implementation scope, acceptance criteria, finite cases, or verification from
an unapproved premise.

## Workflow

1. Read applicable instructions, the task authority, any supplied governing
   direction, and the existing brief if present. Load only cited context needed
   to understand the task.
2. State the smallest testable outcome. When governing direction is supplied,
   prepare the direction trace described in the template. When a technical
   artifact is an intermediate step in an approved end-to-end proof, state both
   its immediate user-observable result and the approved capability it enables;
   do not reduce the trace to a generic artifact property. Allow a task to have
   no direct user-observable effect only when it names the next demonstrable
   outcome it enables. Ground "why now" in approved sequencing or a real
   dependency rather than inventing priority. Separate confirmed requirements
   from implementation choices and unresolved decisions.
3. Run a delta check before drafting:
   - outcome testable;
   - allowed and prohibited scope clear enough to prevent adjacent work;
   - dependencies and meaningful stop conditions known;
   - acceptance criteria observable; and
   - verification can exercise the decisive behavior.
   When governing direction is supplied, also run this direction-authority
   check before claiming the task is ready:
   - Compare the task's material practical consequences, not every
     implementation detail, with the supplied direction.
   - Treat only owner-confirmed direction and specifically confirmed decisions
     as authority. Recommendations, assumptions, unresolved questions, and
     technical notes are not approvals.
   - Check user-observable behavior and operating scenarios, ordered priorities
     and their conflict rule, the first useful proof, scope and non-goals,
     assurance and trust, and intervention and decision ownership.
   - Allow a technical refinement when task authority permits it and it changes
     none of those consequences. Direction need not name every implementation
     detail.
   - Do not make a conflicting request appear authorized by silently dropping
     its stated or recommended behavior and inventing a different task. When
     the supplied request's only proposed approach crosses a direction
     boundary, and the owner has not explicitly rejected or replaced that
     approach with an authorized alternative, the missing choice still needs a
     direction delta. A hypothetical compliant architecture is not authority
     to draft a substitute implementation task.
   - Treat silence as unresolved for a material consequence, not as permission.
     If approval is absent, sources conflict, or the boundary cannot be
     established, return the direction-delta-needed form below in the
     conversation and stop without creating or modifying the requested task
     artifact.
   Preserve adequate sections verbatim or by reference. Do not expand them for
   template completeness. If the task would need to introduce or change product
   behavior, priority, assurance, trust, intervention, or scope beyond supplied
   governing direction, return the plain-language direction-delta-needed form
   below and stop. For other material product or architecture gaps, switch to
   `blocked_design` and stop before the remaining drafting steps.
4. Classify verification-capability uncertainty before choosing preflight or a
   split:
   - Use implementer self-preflight or standalone guided preflight when an
     authorized capability is present or reasonably believed to exist and only
     its current path, interface, command, permission, or availability needs
     confirmation. The implementation contract must remain bounded regardless
     of that current-state result.
   - Create a separate prerequisite evaluation/proof task when no approved or
     believed-existing mechanism can establish the decisive oracle, and
     feasibility would choose the enforcement design, change implementation
     scope, require cross-platform/environment proof, or introduce a shared
     helper or harness. The proof task resolves the mechanism and boundary
     without implementing production behavior. Mark the primary task
     `blocked_design`, record the prerequisite dependency, and do not imply
     preflight or the implementer may discover around it. Give the prerequisite
     task its own proof-only scope, real-boundary success and failure oracles,
     required environments, decision owner, and handoff. Classify the missing
     verification capability as prerequisite/uncertain feasibility; do not
     silently assign a reusable helper to either implementer.
   Split other work only when pieces can be implemented and verified
   independently. Avoid handoffs whose only result is more coordination.
5. Expand finite material risks when authority contains a universal or
   lifecycle claim whose cases are both enumerable and consequential. Name
   every approved artifact family, ordered publication prefix, exact
   cardinality, retry/recovery state, tamper case, or bounded cleanup state
   whose omission could permit false success. Do not expand open-ended quality
   words, speculative abuse cases, or a generic test catalog.
6. Define concise acceptance criteria. Include the positive behavior and the
   most credible negative, unchanged-state, or failure behavior. For lifecycle
   work—retry, resume, recovery, pagination, migration, repeated selection—name
   the first legitimate state change and the next real occurrence.
7. Map each material risk to the lowest reliable evidence. Use a public entry
   point or real boundary when pure/unit evidence cannot prove wiring,
   persistence, processes, filesystem behavior, database behavior,
   concurrency, permissions, or compatibility.
8. Name targeted and broader verification commands when authority or local
   precedent supplies them. In guided mode, focused command discovery may stay
   with the implementer. In high-assurance mode, unresolved required commands
   go to preflight and must not be presented as passing.
9. Add the task metadata block:

   ```yaml
   agent_tier: mechanical | standard | strong
   reasoning: low | medium | high
   review: mechanical | milestone | immediate
   budget: <tool calls> / <time> / <context>
   ```

   Treat `agent_tier`, `reasoning`, and `review` as intended launch guidance
   for future automated or current manual routing, and use the values the task
   authority actually calls for. They are not claims about the eventual
   runtime configuration; do not claim to have observed a runtime reasoning
   setting unless it was supplied. Keep these four scalar keys and treat the
   budget as a soft checkpoint unless higher-priority instructions explicitly
   make it hard. When `review: immediate`, preserve implementation as the next
   action and add the ordered follow-on: immediately after implementation or
   correction, hand the completed bytes to a fresh independent acceptance
   reviewer. Apply this to surgical gap-checks as well as newly drafted briefs;
   a generic implementation next action or a review workflow loaded in the
   authoring or implementation session does not state independent acceptance.
10. Give every durable brief one human-readable readiness route:
    - `implementer self-preflight` for routine guided work;
    - `standalone guided preflight — <material uncertainty>` only when naming
      the concrete uncertainty that makes a separate readiness check useful; or
    - `high-assurance preflight` when the selected profile requires it.
    Do not add a route metadata key. Current repository facts may require the
    implementer or orchestrator to escalate the recommendation at execution
    time. A prerequisite feasibility/proof task from step 4 is a design
    dependency, not a readiness route.
11. Read `references/task-brief-template.md`. Use only the core sections for a
   guided brief; add the high-assurance sections only for that profile.

## Finite-risk coverage contract

Use the optional finite-risk table only when step 5 finds at least one finite,
material dimension. Use exactly these six columns, in this table rather than
scattering their semantics across other sections:

- the invariant;
- the exact material dimensions or state transitions;
- the decisive observable oracle and real boundary;
- fail-first, targeted, or owning evidence the implementer must establish;
- a distinct independent-review probe, or `N/A` with a reason; and
- the gate owner and stage.

Rows may combine cases only when they share one invariant and oracle. The table
is a coverage contract, not a Cartesian-product requirement. Keep
implementation evidence separate from review corroboration; an implementer
self-check is not acceptance. For an immediate-review correction flow, state
whether the correction implementer or final fresh reviewer owns the broader or
aggregate gate. Keep targeted evidence first while it is red instead of
requiring the same broad gate after every failed review. Keep row identity
stable across corrections so later reviews can carry each row forward as
`pass`, `fail`, `blocked`, or `unchecked`; prior status is not proof for
corrected bytes.

## Verification defaults carried by the brief

The user should not need to repeat these instructions for every task:

- For a bug, require a regression that fails for the intended reason before the
  fix when feasible.
- For changed behavior, prefer a focused test capable of rejecting the old or
  faulty behavior.
- Use the lowest reliable test level, adding a real-boundary check only when it
  proves something lower-level evidence cannot.
- Run the targeted check first, then the nearest owning suite, then only the
  broader gate justified by blast radius and authorization.
- Assign each broader or aggregate gate to an owner and stage; do not silently
  duplicate it across correction and review.
- Record skipped stronger checks and residual risk without presenting them as
  passed evidence.

## Output contract

For a gap check, report only:

- whether the existing task is usable;
- concrete missing or contradictory items;
- the smallest proposed edits; and
- whether guided implementation may begin or high-assurance preflight is
  warranted; and
- when `review: immediate`, the ordered handoff from implementation or
  correction to fresh independent acceptance review immediately afterward.

When supplied direction does not authorize a needed product, priority,
assurance, trust, intervention, or scope choice, return only:

```markdown
# Direction delta needed: `<requested task>`

- Governing direction: `<exact source and relevant section>`
- Missing decision: `<plain-language choice the task cannot make>`
- Why it matters: `<practical consequence for the owner or user>`
- Options: `<concise choices and their practical tradeoffs>`
- Recommendation: `<optional and clearly non-authoritative, or none>`
- Downstream impact: `<briefs or plans that may need review>`
- Owner action: `<smallest decision or direction update needed>`
```

This is a routing response, not a task brief. Return it in the conversation and
leave the requested task path absent or unchanged. Write a durable delta only
when the user explicitly requests a separate direction-delta artifact path;
never store it at the requested implementation-task path.

Do not continue into task scope, acceptance criteria, launch metadata,
verification, or implementation handoff until the owner supplies the missing
direction. A technical recommendation is not governing authority.

For a durable brief, use `references/task-brief-template.md`. When governing
direction was supplied, include its `Direction trace` section and require
`New direction decisions required: None`; any other value requires the
direction-delta-needed response instead of a ready brief. Use one status:

- `ready`: guided implementation may begin after its recommended readiness
  route is satisfied;
- `ready_for_preflight`: high-assurance design is complete but current
  executability still requires preflight;
- `blocked_design`: a material decision or authority gap prevents safe work.

For `blocked_design`, return only the requested outcome as stated, the missing
decisions or authority, their owner, and the smallest planning action. Omit
launch metadata, readiness routing, proposed architecture, implementation
scope or paths, work items, implementation ACs, finite-risk coverage,
verification obligations, and implementation handoff language. Those details
would turn an unapproved premise into apparent authority.

Never update an official master plan merely to record completion of this
design task.

## Boundaries and routing

- Route current Git state, command resolution, dirty ownership, and current
  dependency checks to a compact implementer self-preflight or standalone
  `task-preflight`.
- Route unresolved feasibility that determines the implementation mechanism,
  scope, cross-platform enforcement, or shared verification infrastructure to
  a separate prerequisite evaluation/proof task and block the primary task on
  its result.
- Route missing product or architecture authority to its owner or the user.
- Route gaps in supplied product direction through the plain-language
  direction-delta-needed form rather than silently resolving them in a
  technical brief.
- Route wider scope or new shared infrastructure back through brief design.
- Do not implement, accept the result, update trackers, launch subagents, or
  modify orchestration state.

## Definition of done

- The task is independently understandable without this conversation.
- Every changed or added line in an existing brief closes a concrete gap.
- Outcome, scope, ACs, evidence, metadata, stops, and next action are clear.
- When direction is supplied, the contribution, user-observable effect or
  enabled outcome, sequencing reason, and approved decisions are traceable.
- Every ready brief with supplied governing direction says
  `New direction decisions required: None`; otherwise brief design stopped
  with a direction delta.
- Guided briefs avoid high-assurance artifact ceremony unless risk justifies it.
- High-assurance briefs preserve exact stage and evidence contracts.
