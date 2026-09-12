# Delivery Routing After Foundation

Choose the **cheapest route that adequately controls risk**.

## PERSONAL_FLOW — default

Use the personal task flow when most are true:

- the high-level goal is stable enough to derive bounded tasks
- one or two modules own most changes
- existing interfaces/architecture constrain the solution
- no major schema/API/UI contract must be jointly designed
- a task can be expressed with explicit scope, acceptance, and verification
- hidden-test risk is primarily implementation/edge-case risk
- time/token pressure is high

Recommended flow:

`task-brief-designer -> task-preflight -> bounded-task-implementer -> task-acceptance-review`

Use repeated bounded tasks rather than one giant implementation task.

## SDD_QUICK — targeted spec/design protection

Use when at least one is true:

- externally observable behavior has several acceptance conditions that are easy to misread
- a new architectural boundary/interface is required
- AI behavior introduces a nontrivial contract between model output and deterministic code
- feature touches multiple layers and a short design artifact will prevent rework
- you need durable AC-to-implementation traceability for a critical feature

Prefer easy interview depth and quick route. Skip N/A stages.

This is usually the maximum SDD depth justified for a timed contest feature.

## SDD_STANDARD — cross-cutting system change

Use when several are true:

- multiple modules/services/surfaces change
- schema + API + workflow behavior must evolve together
- there are competing architectural approaches with meaningful blast radius
- state ownership or persistence semantics are non-obvious
- concurrency/idempotency/recovery semantics matter
- several dependent features/tasks require a shared design
- the challenge is large enough that rework would cost more than planning

Still skip irrelevant stages.

## SDD_FULL — rare contest escalation

Use only when the project behaves more like a mini-product than a bounded challenge:

- many user stories / surfaces
- new persistent domain model plus API plus UI/process flows
- multiple irreversible architecture choices
- safety/security/compliance constraints with traceability requirements
- substantial parallel implementation lanes depend on a shared formal design
- there is enough remaining contest time/token budget for the planning overhead

Do not select `SDD_FULL` merely because:
- the task is hard
- AI is involved
- the repo is unfamiliar
- you want more confidence

Hard implementation can still be a bounded task after a good foundation.

## Route escalation during execution

Start lighter.

Escalate from PERSONAL_FLOW to SDD when preflight discovers:

- unresolved architecture ownership
- contradictory requirements
- a task brief expanding across multiple system boundaries
- repeated implementation rework caused by missing design
- acceptance criteria that cannot be localized to a bounded change

Escalation is allowed mid-contest; starting with full ceremony is not required.
