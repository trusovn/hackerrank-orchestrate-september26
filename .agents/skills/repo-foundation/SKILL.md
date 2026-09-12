---
name: repo-foundation
description: Use this skill when creating, restructuring, or standardizing repository architecture, top-level project layout, module boundaries, repo-local tools, scripts, lint/test/typecheck commands, CI gates, repo-local agent instructions, architecture/project maps, ADRs, module docs, or "where should this live?" decisions. Use it when an implementation needs new top-level folders, modules, tooling, generated-code flows, or durable placement rules. This skill is especially important when future LLM agents will maintain the repo and token-efficient navigation matters.
---

# Repo Foundation

Use this skill to make repositories easier for humans and LLM agents to maintain. The goal is not more ceremony; it is a small set of current, authoritative signals that prevent repeated rediscovery.

## Core stance

- Local convention wins unless it is absent, stale, or actively causing confusion.
- Prefer the smallest durable structure that gives future work a clear place to land.
- Optimize for low-token maintenance: one short map beats repeated repo-wide searches.
- Do not turn a small repo into a large-process repo. Scale the structure to the project.
- Do not restructure, add tooling, or create docs as a side effect of unrelated feature work.

## Quick protocol

1. Read local authority first: `AGENTS.md`, `CLAUDE.md`, `CONTRIBUTING.md`, `README.md`, `docs/project-map.md`, `docs/architecture-map.md`, `docs/architecture.md`, `docs/adr/`, CI files, and package/build config as available.
2. Classify the task:
   - **Placement:** deciding where new code/docs/tools live.
   - **Foundation:** creating or changing repo-level structure, commands, docs, CI, or module boundaries.
   - **Restructure:** moving existing files or changing public paths.
   - **Feature-only:** ordinary product work. Use this skill only for the placement decision, then keep changes scoped.
3. Classify repo scale:
   - **Ad-hoc/tiny:** one purpose, few files. Keep notes in `README.md` or `AGENTS.md`; add a smoke check only if useful.
   - **Small product/tool:** recurring edits or several modules. Use a concise `docs/project-map.md` or equivalent section in `README.md`.
   - **Large/long-lived:** multiple domains, services, packages, teams, or UI surfaces. Use an architecture map, ADRs for structural decisions, documented gates, and CI.
4. State assumptions and verification before edits. If two layouts are plausible, name the tradeoff.
5. Patch only what the task makes stale. Do not refresh every doc or reformat adjacent sections.
6. Verify with the narrowest meaningful command first; broaden only after that passes.

## Documentation ownership

The person or agent making a structural change owns the docs it makes stale. Update docs in the same change when you alter:

- top-level folders, package layout, module boundaries, or public entry points
- canonical build/test/lint/typecheck/format/migration commands
- CI gates or required local verification
- generated-code source of truth or regeneration commands
- dependency/update policy, env var source, datastore/migration conventions
- durable placement rules or closest precedents for future work

If you notice unrelated stale docs, mention them. Do not fix them unless they block the current task or the user asks.

Patch docs surgically:

- Prefer editing the stale row/section over rewriting the file.
- Keep one source of truth. Other docs may link to it or summarize it briefly.
- Do not update a freshness marker unless you actually verified the content.
- Use `UNKNOWN`, `TBD`, or an empty machine field instead of guessing.
- Delete placeholders before considering a new map complete.

## Documentation roles

Create or update only the documents that match the repo's scale and the change.

| File | Use for | Update when |
|---|---|---|
| `README.md` | human quickstart, purpose, install/run/test workflow | human workflow or basic commands change |
| `AGENTS.md` / `CLAUDE.md` | agent-facing commands, constraints, pitfalls, repo-specific rules | agent workflow, verification, or constraints change |
| `docs/project-map.md` | lightweight navigation for small/medium repos | top-level layout, module list, tools, commands, or placement rules change |
| `docs/architecture-map.md` | stronger map for large repos, SDD flows, or cross-module architecture | boundaries, integrations, datastores, conventions, or major modules change |
| `docs/adr/` | decisions with real blast radius | stack, module style, persistence, deployment, generated-code policy, or public API strategy changes |
| module `README.md` | local module contract and maintenance notes | module public surface, invariants, local commands, dependencies, or generated files change |
| `docs/testing.md` | testing strategy too large for map/README | test layers, fixtures, integration dependencies, or slow/fast gate policy changes |

### Project map contents

A small/medium repo map should usually fit on one screen or close to it:

- canonical commands: build, test, lint, typecheck, format, migrate, verify
- top-level layout with one-line responsibility per folder/module
- "where things live" rules for new source, tests, tools, docs, generated files
- closest precedents for common changes
- known constraints, deprecated patterns, and slow checks
- freshness marker: date, commit, or "verified against current tree"

### Architecture map contents

A large repo map can be longer, but keep it navigational:

- machine-readable command keys when useful
- module/package inventory with boundaries and ownership/responsibility
- wiring/integration points and datastores
- cited conventions with path anchors
- frontend foundation if a frontend exists: component library, tokens, styling approach, shared primitives, closest screen precedent
- ADR links for decisions instead of re-explaining them
- freshness marker such as `updated_at` and `reflects_commit`

## Module structure

Prefer this decision order:

1. Existing local convention.
2. Strong ecosystem/framework convention.
3. Vertical/domain-oriented modules for product code.
4. Horizontal layers only where they reduce duplication or match the framework.

Vertical modules are the default for maintainability because a future agent can inspect one domain without reading the whole repo. A typical product module may look like this, adapted to the language:

```text
modules/<domain>/
  README.md      # optional; only when the module contract is non-obvious
  domain/        # core rules/entities/value objects
  app/           # use cases/orchestration
  ports/         # interfaces/contracts at the boundary
  infra/         # adapters: persistence, HTTP clients, queues, filesystem
  ui/            # only when UI is owned by this module
  tests/         # or ecosystem-equivalent colocated tests
```

Do not create empty layer folders. If a module has only one or two files, keep it flat until structure earns its cost.

Horizontal structure is appropriate when:

- the framework requires it, such as routes/controllers/components directories
- the repo is a library organized around public API layers
- a layer is genuinely shared infrastructure with multiple consumers
- existing code already uses horizontal layers consistently

Avoid mixed architecture without a clear reason. If a repo uses vertical modules, keep new feature code inside the owning module. If it uses horizontal layers, place files in the matching layer and update the map with the feature's cross-layer path.

### Module documentation

Do not add a `README.md` to every folder. Add or update module docs when the module has at least one of:

- public API, CLI, route, event, or package surface used outside the module
- non-obvious invariants or domain rules
- external dependencies, datastore ownership, migrations, or generated code
- special local test/build commands
- ownership boundary in a monorepo or large codebase
- recurring maintenance tasks that agents would otherwise rediscover

Keep module docs short:

- purpose and responsibility
- public entry points and owned data
- internal layout, only if non-obvious
- local commands/tests, only if different from root commands
- generated-code or migration notes
- closest precedent for similar changes

## Where things live

- Put product/source code in the existing source root, not in `tools/` or `scripts/`.
- Put thin human-invoked wrappers in `scripts/`.
- Put testable repo-owned utilities, generators, validators, and local CLIs in `tools/`.
- Put generated output where the ecosystem expects it, and document the editable source plus regeneration command.
- Co-locate tests with code when the repo already does; otherwise mirror source layout under `tests/`.
- Add shared code only after at least two real call sites need it.
- Keep feature/domain code near its domain boundary. Avoid a new top-level folder for a one-off helper.
- For UI, reuse the existing component library, design tokens, styling system, and closest screen precedent.

## Monorepos

Use a root map for repository-wide truths and package-local docs for package-specific truths.

- Root docs own workspace commands, package inventory, dependency policy, CI, shared tooling, and cross-package boundaries.
- Package docs own package-specific commands, public API, local layout, generated files, and tests.
- Do not duplicate every package's README into the root map. Link and summarize.
- If packages have independent release/deploy lifecycles, document that at the root.
- If a change touches one package only, update package docs unless root placement or CI rules changed.

## Restructuring protocol

For requested restructuring:

1. Inventory current layout, public entry points, imports, tests, CI, generated files, and docs that name paths.
2. Write a short old-to-new placement map before moving files.
3. Move in slices that keep the repo buildable.
4. Preserve public import paths, CLI commands, routes, file formats, and env vars unless the user asked for a breaking change.
5. Update affected docs and local instructions in the same slice or immediately after.
6. Run targeted verification after each meaningful slice, then the repo's normal gate at the end.

If the goal can be solved by adding a placement rule or module doc instead of moving files, recommend that lighter path.

## Lint, format, typecheck, and CI

Make verification discoverable and boring:

- Prefer existing commands from package/build config.
- Record canonical commands in `README.md`, `AGENTS.md`, project map, or architecture map.
- Keep one obvious command for each gate where possible: build, test, lint, typecheck, format.
- If no lint exists, do not introduce a heavy linter just for hygiene. Prefer the ecosystem's standard formatter/compiler/typechecker or a small targeted check.
- CI should run the same commands humans and agents run locally.
- For small repos, one `make verify`, `npm run check`, `just verify`, or equivalent is enough if the ecosystem supports it.
- For large repos, split fast default checks from slow/integration checks and document when to run each.

Avoid verification theater. A gate should catch real mistakes or document a meaningful invariant.

## Testing boundary

This skill owns test placement, command discoverability, smoke checks for structural work, and CI gates. It does not own deep test strategy. If a repo or user has a dedicated testing skill or testing guide, use that for deciding what behavior to test, test granularity, mocking strategy, fixtures, and coverage expectations.

When no testing-specific guidance exists, use these minimal defaults:

- For bug fixes, add or identify a failing regression test before the fix when feasible.
- For structural work, use smoke tests: project builds, main entry point boots, command starts, empty migration applies, imports resolve, or generated code round-trips.
- For libraries, test public API behavior and a minimal integration path.
- For CLIs/tools, test argument parsing, one happy path, and one failure path.
- For UI, test durable interaction or render contracts; use visual checks only when visual layout is the task.
- Keep fixtures small and named by behavior.
- Document any intentionally skipped expensive check and the stronger command that would cover it.

Docs-only changes should still run the cheapest relevant check when one exists: markdown lint, link check, doc generator, table-of-contents update, or repository validation script.

## Dependency, migration, and generated-code policy

Only document policies the repo actually needs. When relevant, make these visible:

- where dependencies are declared and how they are updated
- lockfile expectations
- migration tool, migration location, and naming convention
- environment variable source of truth
- generated-code source files and regeneration command
- vendored or external code policy
- version support matrix when the repo has multiple runtimes

## Optional SDD integration

If the target repo has SDD assets, use them as local authority instead of duplicating their role:

- `skills/survey/SKILL.md`
- `skills/survey/templates/architecture-map.md`
- `skills/survey/references/foundation.md`
- `docs/architecture-map.md`
- SDD commands or feature folders under `docs/features/`

If these files are present, follow their map and scaffold conventions. If they are absent, proceed standalone with this skill; do not assume SDD exists or ask the user to install it.

## Definition of done

A repo foundation change is done when:

- new or moved files live in the smallest sensible place according to local or ecosystem convention
- affected docs are updated by role, with no duplicate source of truth introduced
- commands needed for future maintenance are discoverable
- maps/module docs contain nearest precedents for the next similar change when that would save rediscovery
- test placement, documented test commands, and CI gates match the repo's current testing guidance
- tests/lint/typecheck/build/docs checks ran at the narrowest meaningful level, with results reported
- any skipped stronger verification is named explicitly
- unrelated stale docs or structure issues are mentioned, not silently swept into the change
