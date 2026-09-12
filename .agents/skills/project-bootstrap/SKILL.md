---
name: project-bootstrap
description: >
  Use at the very beginning of a software project or timed contest challenge, after a high-level
  objective and repository/scaffold are available but BEFORE detailed product specification,
  architecture design, roadmap creation, task decomposition, or implementation. Establish the
  minimum project charter and engineering-foundation plan another agent needs to work effectively.
  Produces docs/project-charter.md and docs/foundation-plan.md. Then hand off repo-level
  materialization to repo-foundation. Do not use this skill to plan features.
---

# Project Bootstrap

Establish the **pre-planning foundation contract** for an unfamiliar project.

The job is not to design the product. The job is to make later planning and implementation
well-founded, fast, and verifiable.

## Core stance

- High-level intent must be clear before infrastructure choices are made.
- Inspect the provided scaffold before proposing new structure.
- Preserve useful local conventions; do not replace the scaffold with a preferred template.
- Create only foundation that enables later work or verification.
- Prefer a few durable, executable signals over extensive prose.
- Do not create feature tasks, feature APIs, detailed domain models, screens, prompts, or workflows here.
- In a timed contest, reversible choices should use good defaults instead of triggering long interviews.

## Inputs

Required:

- the challenge/project high-level objective
- the current repository/scaffold

Optional:

- challenge statement or product brief
- repo-local authority files (`AGENTS.md`, `CLAUDE.md`, `README.md`, architecture docs, ADRs)
- existing build/test/lint/typecheck/run commands
- explicit contest/runtime constraints

## Outputs

Create or update:

- `docs/project-charter.md`
- `docs/foundation-plan.md`

Do not materialize unrelated feature code.

After these artifacts are ready, use `repo-foundation` to make the justified repo-level changes.

## Protocol

### 1. Read authority before inventing anything

Read, when present:

- scoped/root `AGENTS.md`
- `CLAUDE.md`
- `README.md`
- `CONTRIBUTING.md`
- current architecture/project maps
- accepted ADRs
- CI/build/package configuration
- challenge-provided instructions

Classify statements as:

- `REQUIRED` — challenge/runtime/local authority
- `EXISTING` — current scaffold reality
- `DECISION` — explicit user/project choice
- `ASSUMPTION` — reversible default introduced during bootstrap
- `UNKNOWN` — not yet known and not safe to invent

Historical notes are evidence, not authority, unless explicitly marked current.

### 2. Write the project charter

Create `docs/project-charter.md` using `templates/project-charter.md`.

Keep it short. Capture only what is needed to choose an engineering foundation:

- mission / high-level outcome
- target users or external actor, when known
- expected product shape (service, web app, CLI, worker, library, mixed)
- hard constraints
- success signals visible at system level
- quality priorities
- explicit non-goals
- unresolved foundation-bearing questions

Do not decompose features.

If the high-level goal is already clear, restate and record it rather than interviewing again.

### 3. Survey the scaffold for foundation capabilities

Inspect enough of the repo to answer:

- What runtime/build system already exists?
- What starts/runs today?
- What verification commands already exist?
- What test harness exists?
- Is there CI?
- How is config/secrets handled?
- How are logs/errors exposed?
- Is there a datastore/migration mechanism?
- Are there generated files?
- Are agent instructions or architecture maps already present?
- What parts of the scaffold are authoritative or must not be replaced?

Record evidence with file/path anchors where practical.

Do not perform a broad code comprehension exercise unless required to answer these foundation questions.

### 4. Classify foundation gaps

Use these capability groups:

1. **Bootstrap/runtime**
   - reproducible install/start
   - environment prerequisites

2. **Verification**
   - focused test command
   - full verification command
   - lint/typecheck/build where meaningful

3. **Repo navigation**
   - concise agent instructions
   - project/architecture map appropriate to repo size
   - placement rules / closest precedents

4. **Observability for development**
   - usable logs/errors
   - optional traces/diagnostics only when needed

5. **Configuration/state**
   - env/config source of truth
   - datastore/migration mechanics when applicable

6. **Automation**
   - local scripts/Make/Just/package commands
   - CI only if it catches real contest-relevant failures

7. **AI foundation**
   - if AI/LLM is in the process/data flow, mark `ai-flow-foundation: REQUIRED`
   - do not design AI internals here

For each capability mark:

- `REUSE`
- `REPAIR`
- `ADD`
- `DEFER`
- `N/A`

### 5. Write the minimum foundation plan

Create `docs/foundation-plan.md` using `templates/foundation-plan.md`.

For every proposed foundation change include:

- capability/problem
- evidence
- smallest sufficient change
- files likely affected
- verification command or observable DoD
- why it must happen before product planning
- whether it is reversible

Do not write a product roadmap.

### 6. Apply the pre-planning boundary

A change belongs in the foundation plan only if at least one is true:

- without it another agent cannot reliably navigate or modify the repo
- without it the project cannot be run or verified
- without it deterministic tests/evals cannot be written
- without it later architectural decisions would be made on false assumptions
- it encodes a contest/runtime constraint that future agents must not rediscover

Otherwise defer it to product design or implementation.

### 7. Hand off to `repo-foundation`

If `repo-foundation` is available, use it as the governing skill for materialization.

The handoff must name:

- artifacts to read
- exact foundation changes authorized
- non-goals
- verification required
- any `UNKNOWN` values that must remain unknown

Do not silently broaden the materialization scope.

### 8. Stop before detailed product planning

Exit when:

- charter is sufficient to ground architecture decisions
- foundation gaps are explicitly classified
- foundation work is bounded and verifiable
- no feature implementation has begun

Recommended next step after materialization:
`foundation-readiness-review`.

## Definition of Done

- `docs/project-charter.md` states the high-level objective and hard constraints without feature decomposition.
- `docs/foundation-plan.md` distinguishes reuse/repair/add/defer/N/A.
- Every `ADD`/`REPAIR` item has a concrete verification method.
- Existing scaffold capabilities were reused where reasonable.
- Unknowns are explicit rather than guessed.
- Product design, roadmap, and task planning have not started.
- The materialization handoff is narrow enough for `repo-foundation`.

## Anti-patterns

- Writing a detailed master plan before understanding the scaffold.
- Replacing the provided scaffold because another stack/layout is more familiar.
- Creating CI, Docker, observability, or docs merely because "real projects have them".
- Treating architecture diagrams as a substitute for executable run/test commands.
- Putting product behavior into bootstrap tasks.
- Designing prompts, agents, workflows, or business state before the AI/product behavior is specified.
- Producing a 20-page foundation artifact for a small contest repo.
