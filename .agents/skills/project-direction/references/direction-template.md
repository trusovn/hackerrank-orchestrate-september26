# Project Direction: `<working name>`

Status: `<draft | owner-confirmed baseline>`

Source: `<prompt, notes, or document paths>`

## Direction at a glance

- Problem: `<the practical problem worth solving>`
- Desired experience: `<what should feel or work differently for the user>`
- First useful proof: `<the smallest end-to-end result that proves real value>`

## How this should work in practice

| Situation | What should happen | When the owner must step in |
|---|---|---|
| Normal | `<ordinary value-producing story>` | `<none, or the explicit decision point>` |
| Recovery | `<interrupted, failed, or partial work and its recovery>` | `<when automatic recovery is no longer safe or useful>` |
| Must stop | `<ambiguous, unsafe, or out-of-bounds situation>` | `<decision or action only the owner may take>` |

## Priorities and conflict rule

1. `<highest priority>`
2. `<next priority>`
3. `<next priority>`

Conflict rule: `<when priorities compete, state which wins and what may be
sacrificed or deferred>`

## Scope

### In scope

- `<owner-visible capability or responsibility>`

### Not in scope

- `<explicit non-goal>`

## Boundaries

### Trust

- Trusted: `<people, sources, or local conditions the direction relies on>`
- Fallible or untrusted: `<inputs or actors that must be checked or contained>`
- Not a design target: `<threat or assurance level deliberately excluded>`

### Intervention and decision ownership

- May proceed without asking: `<bounded decisions or actions>`
- Must ask or stop: `<choice, consequence, ambiguity, or risk requiring owner action>`
- Owner-controlled changes: `<direction that downstream planners may not alter>`

## Direction ledger

### Confirmed decisions

- `<decision the owner explicitly confirmed>`

### Recommendations awaiting approval

- `<recommendation and its practical reason, or none>`

### Assumptions

- `<assumption, why it matters, and how it can be confirmed>`

### Unresolved direction questions

- `<plain-language question; practical consequence; downstream work it blocks>`

## Contract for technical planning

- Technical work must cite the direction outcome, scenario, priority, or
  boundary it advances.
- Technical work may choose implementation details inside this direction.
- Technical work may not silently add product behavior, reorder priorities,
  raise or lower assurance, change trust or intervention boundaries, or widen
  scope.
- If such a choice is needed, return a plain-language direction delta for
  owner approval before making the technical task implementation-ready.

## Source notes

`<For extraction/audit only: concise provenance, contradictions, superseded
statements, and technical choices that were not treated as owner decisions.>`

---

# Direction Delta: `<working name>`

Status: `<proposed | owner-confirmed>`

Source: `<feedback, evidence, correction, or document paths>`

## What changed

- Previous direction: `<plain-language summary>`
- New direction: `<plain-language summary>`
- Why: `<reason for the change>`

## What remains unchanged

- `<priority, scope, trust, or experience that still governs>`

## Practical impact

- Priority or conflict-rule impact: `<change or none>`
- Scenario impact: `<normal, recovery, or must-stop behavior that changes>`
- Boundary impact: `<scope, assurance, trust, intervention, or ownership change>`
- First useful proof impact: `<change or none>`

## Downstream plans to review

- `<document or task; why it may conflict; do not rewrite it here>`

## Decision status

- Confirmed decisions: `<owner-confirmed changes>`
- Recommendations awaiting approval: `<agent recommendations or none>`
- Assumptions: `<provisional beliefs or none>`
- Unresolved direction questions: `<question and consequence or none>`
