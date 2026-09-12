# Foundation Plan

> Historical bootstrap record (2026-09-12). This document preserves the
> foundation decisions that were authorized before materialization; it is not
> live operating guidance. Use `AGENTS.md`, `.agents/workflow.md`,
> `docs/project-map.md`, and `docs/diagnostics.md` for current work.

## Baseline

- Runtime/build: **EXISTING** Python 3 (`Python 3.14.4` observed locally); no dependency or build manifest.
- Existing run command: **EXISTING** `python3 code/main.py`; the file is empty and currently performs no product work.
- Existing focused verification: **EXISTING** `python3 -m compileall -q code` passes.
- Existing full verification: **UNKNOWN/ABSENT**; `python3 -m unittest discover -s tests -p 'test_*.py'` fails because `tests/` does not exist.
- Existing repo instructions/maps: **REUSE** `AGENTS.md`, `README.md`, `problem_statement.md`, and `CLAUDE.md`; no concise project map exists.
- Existing CI: **N/A for bootstrap**; no CI configuration exists and a local gate is sufficient for this timed contest.
- Config/state: **EXISTING** CSV files under `dataset/`; no datastore, migrations, runtime config, or committed secrets.
- Development diagnostics: **ABSENT** for the empty solution; `log.txt` is the required append-only conversation log, not an application log.
- AI in data/process flow: **yes**; `ai-flow-foundation` is **REQUIRED** before detailed prompt or workflow design.

## Capability decisions

| Capability | Status | Evidence | Minimum change | Verification |
|---|---|---|---|---|
| Bootstrap/runtime | REUSE | `README.md` names `python3 code/main.py`; it exits 0 and `code/` compiles. | Keep Python 3 and the existing entry point; defer product behavior and dependencies. | `python3 -m compileall -q code` |
| Verification | ADD | No `tests/`; unittest discovery currently errors. | Add standard-library contract/smoke tests and one documented full local command. | `python3 -m unittest discover -s tests -p 'test_*.py'` |
| Repo navigation | ADD | Authority docs exist, but there is no concise current map or placement guidance. | Add `docs/project-map.md` and link it from `README.md`. | Inspect links and run the full local verification command. |
| Development diagnostics | DEFER | No runtime behavior or provider is implemented. | Record required AI-call metadata in `docs/ai-foundation.md`; add runtime logging only with the owning feature. | AI foundation document names correlation, provider/model, latency/status, validation, and retry fields. |
| Configuration/state | REUSE / DEFER | Dataset paths and env-only secret rule are authoritative; no datastore is needed. | Reuse `dataset/`; defer `.env.example` until a concrete provider variable exists. | Contract test checks required participant-facing files and CSV headers. |
| Automation/CI | DEFER | No CI exists; fewer than 24 hours remain and local commands are sufficient. | Do not add CI, Docker, Make, or a task runner during bootstrap. | Canonical commands remain directly runnable from the root. |
| AI foundation | ADD | The challenge explicitly requires an AI-powered agent and model-quality/cost reporting. | Add a provider-neutral, fakeable call/validation seam plus `docs/ai-foundation.md`; do not choose a model or prompts. | Focused AI-boundary unit tests run without network access. |

## Authorized foundation changes

1. Keep the required conversation log out of Git.
   - Why before product planning: repository instructions require this on every turn and forbid committing the transcript log.
   - Files: `.gitignore`
   - DoD: `git check-ignore -v log.txt` identifies the root ignore rule.
   - Reversible: yes

2. Make the small repository navigable and its commands discoverable.
   - Why before product planning: future agents otherwise have to repeat the same scaffold survey and may place code or outputs incorrectly.
   - Files: `docs/project-map.md`, `README.md`
   - DoD: the map records current top-level ownership, placement rules, canonical commands, constraints, and a freshness marker; README links to it and names verification.
   - Reversible: yes

3. Add a deterministic scaffold contract test using only Python's standard library.
   - Why before product planning: it protects authoritative dataset/header and artifact-location assumptions before implementation relies on them.
   - Files: `tests/test_repository_contract.py`
   - DoD: `python3 -m unittest discover -s tests -p 'test_*.py'` passes.
   - Reversible: yes

4. Establish the minimum AI/provider boundary.
   - Why before product planning: model output is untrusted and ordinary tests must not require a live provider.
   - Files: `docs/ai-foundation.md`, `code/buy_or_wait/__init__.py`, `code/buy_or_wait/ai_boundary.py`, `tests/test_ai_boundary.py`
   - DoD: the provider is replaceable, validation gates downstream values, a deterministic fake covers success/provider failure/validation failure, and focused tests pass offline.
   - Reversible: yes

5. Preserve honest scaffold status.
   - Why before product planning: an empty entry point and evaluation placeholder must not be mistaken for an implemented solution.
   - Files: documentation only
   - DoD: project docs explicitly mark final run, eval runner, usage report contents, application diagnostics, and product tests as not yet implemented.
   - Reversible: yes

## Explicitly deferred

- Financial-state reconstruction, recurrence detection, forecasting, plan ranking, output generation, and deterministic product validators.
- Image extraction behavior, prompts, structured feature schemas, provider/model selection, caching, batching, and fallback policy.
- Sample scoring implementation and final full-dataset evaluation/usage accounting.
- CI, containers, datastore/migrations, web UI, and production deployment.

## Materialization handoff

Read:

- `docs/project-charter.md`
- `docs/foundation-plan.md`
- `docs/ai-foundation.md`

Use:

- `repo-foundation` for the exact files in authorized changes 1-5.

Do not:

- implement product features or generate predictions
- broaden architecture beyond a small Python batch CLI
- select a provider/model or write prompts
- add third-party dependencies, CI, containers, or runtime configuration
- guess unresolved Python, provider, offline-fallback, or workflow values

Required verification:

- `git check-ignore -v log.txt`
- `python3 -m compileall -q code tests`
- `python3 -m unittest discover -s tests -p 'test_*.py'`
