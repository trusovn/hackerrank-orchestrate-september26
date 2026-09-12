---
name: project-direction
description: >-
  Create, extract, audit, or rebaseline a plain-language governing direction
  for a project, product, feature, system, or workflow before or during
  technical planning. Use when the user wants to decide or clarify the desired
  experience, ordered priorities, first useful proof, scope, non-goals, trust
  boundaries, intervention boundaries, or decision ownership; when existing
  plans are too technical for the owner to govern; or when a mid-project change
  needs a direction delta. Produce an owner-editable direction, not research,
  architecture, a PRD, or an implementation plan.
---

# Project Direction

Create the plain-language authority that technical plans must serve. It must use 
simple language so that a non-technical person can easily understand it. Get technical
only when can't explain the concept without it.

## Boundary

Use this skill to record what the project should achieve and the practical
boundaries within which it may do so.

Route adjacent work elsewhere:

- Use `idea-investigator` when the user is asking whether an idea is worth
  pursuing, needs commercial validation or current market or competitor
  research, or has not decided to proceed.
- Use idea challenge for a compact pressure test of a proposed direction.
- Use technical specification, architecture, or task-brief workflows only
  after the governing direction is clear enough for those documents to remain
  subordinate to it.

Apply this boundary before choosing a mode, resolving an output, or beginning
an interview. Routing is a handoff boundary, not permission to start the
adjacent workflow in the same response. When the requested outcome belongs
elsewhere, return a concise handoff that names the workflow and why, then stop;
do not ask that workflow's questions or perform any of its work.

For commercial-worth, demand, market, or competitor-validation requests, say
that commercial validation belongs to `idea-investigator` and should happen
before project direction is established. Do not begin its discovery interview,
perform research, or create a direction artifact.

Do not turn the direction artifact into an architecture document, product
requirements document, implementation plan, task list, exhaustive risk
register, or acceptance-criteria catalog. Technical source documents may
contain evidence about past decisions, but technical detail is not owner
authority merely because it was written down.

## Choose the mode

### Initial direction

Use a raw idea, notes, or an owner conversation to establish the first
governing direction. Preserve the user's confirmed choices and keep missing
choices visibly unresolved.

### Extraction or audit

Use existing plans, specifications, task briefs, or architecture documents as
source material.

- Extract the user-facing purpose, experience, priorities, scenarios, and
  boundaries in plain language.
- Separate current authority from proposals, implementation choices, history,
  and superseded statements.
- Surface contradictions and direction decisions that technical work appears
  to have made without owner approval.
- Do not copy the structure or technical density of the source documents into
  the direction artifact.

### Direction delta or rebaseline

Use when feedback, evidence, or a mid-project correction changes governing
direction.

- State what changed, why, what remains unchanged, and which downstream plans
  need review.
- Treat a user-confirmed correction as a confirmed decision. Label an
  agent-originated change as a recommendation until the owner approves it.
- Return a concise direction delta first. Rebaseline the full direction only
  when the user asks for it or the supplied correction already authorizes it.
- Do not rewrite technical plans as part of the delta.

## Workflow

1. Resolve the source, mode, output location, and whether the result is a draft
   or an owner-confirmed baseline. Create resulting direction-<name>.md file
   next to the provided source file(s), or the current project docs/ folder 
   if no source is provided.
2. Read supplied source material before asking questions. Load only the
   documents needed to understand the intended direction and its conflicts.
3. Identify what the user has actually confirmed. Keep recommendations,
   assumptions, and unresolved questions separate; polished prose must not turn
   them into decisions.
4. Ask only questions whose answers could change the experience, priority
   order, first proof, scope, assurance, trust, intervention, or decision
   boundary. Ask in batches of no more than three. Translate technical choices
   into practical consequences before asking the owner to choose.
5. Build concrete operating stories:
   - the normal value-producing situation;
   - a recovery situation after interruption, error, or partial progress; and
   - a must-stop situation where the tool or team needs owner intervention.
6. Order the priorities. Give a specific conflict rule that tells downstream
   planners which priority wins when two desirable outcomes cannot both be
   maximized.
7. Define the first useful end-to-end proof. It should demonstrate real owner
   value, not merely technical completeness or internal correctness.
8. Define scope, non-goals, trust boundaries, and intervention boundaries in
   language that describes practical consequences.
9. Read `references/direction-template.md` and use the full-direction or delta
   form that matches the selected mode. Keep source/audit notes brief and
   separate from the governing core.
10. Verify the result against the checks below. If a material direction choice
    remains open, leave it open and state what it prevents downstream planners
    from deciding.
11. Do not advance to the next section of the interview until you're sure you 
    have collected enough evidence for the current one.

## Planning contract

Downstream technical work may choose implementation details only inside the
approved direction. It must:

- cite the governing direction and state which outcome, scenario, priority, or
  boundary the work advances;
- preserve the priority conflict rule and all scope, trust, assurance, and
  intervention boundaries;
- distinguish technical recommendations from owner-approved direction; and
- return a plain-language direction delta when useful technical work would
  require a new product behavior, priority, assurance level, trust assumption,
  intervention rule, or scope decision.

A direction delta states the missing decision and its practical consequences.
It does not disguise a recommendation as authority or continue drafting an
implementation-ready plan on top of an unresolved choice.

## Writing rules

- Write for the owner, not for an architect.
- Prefer concrete situations and consequences over abstractions.
- Explain unavoidable technical terms on first use.
- Use ordered lists only where order governs a tradeoff or sequence.
- Keep the governing core concise. Put provenance or audit observations in a
  short source-notes section rather than expanding every section.
- Do not invent architecture, stages, schemas, state machines, file layouts,
  model/provider choices, APIs, or implementation tasks.
- Do not claim that a draft, recommendation, assumption, or extracted
  technical statement is approved.

## Definition of done

- The problem, desired experience, and first useful proof are concrete.
- Priorities are ordered and include a conflict rule.
- Normal, recovery, and must-stop situations show how the direction operates.
- Scope, non-goals, trust, and intervention boundaries are explicit.
- Confirmed decisions, recommendations, assumptions, and unresolved questions
  are visibly distinct.
- The planning contract prevents downstream technical authority drift.
- A nontechnical owner can edit the artifact without reconstructing the source
  documents or learning the proposed architecture.
