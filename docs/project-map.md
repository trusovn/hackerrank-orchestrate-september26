# Project Map

Verified on 2026-09-12 against the repository topology and commands recorded
below. Observed verification results are maintained in
[`foundation-review.md`](foundation-review.md).

## Authority And Discovery

Start at [`../AGENTS.md`](../AGENTS.md). It defines operating constraints and
routes product behavior to [`../problem_statement.md`](../problem_statement.md),
current repository facts to this map, task selection to
[`../.agents/workflow.md`](../.agents/workflow.md), and failures to
[`diagnostics.md`](diagnostics.md).

For a bounded task, read only the owning row below, its closest precedent, and
the selected workflow. Use targeted `rg` searches for call sites and tests.

## Canonical Commands

Run from the repository root:

| Purpose | Command | Current scope / failure signal |
|---|---|---|
| Starter entry point | `python3 code/main.py` | Exit 0; still an empty product placeholder. Nonzero exit is a runtime failure. |
| Compile | `python3 -m compileall -q code tests` | Dependency-free syntax/import compilation. Any output with nonzero exit identifies the file. |
| Agent foundation contract | `python3 -m unittest tests.test_agent_foundation_contract` | Required agent docs, root routing links, and all authoritative local Markdown links. |
| AI boundary | `python3 -m unittest tests.test_ai_boundary` | Offline provider fake, provider failure, and validation gate. |
| Dataset/repository contract | `python3 -m unittest tests.test_repository_contract` | Supplied files, headers, IDs, images, and submission source locations. |
| Dataset repository loader | `python3 -m unittest tests.test_repository` | WP-01 domain types, strict loading, case assembly, and fail-fast validation. |
| Patch hygiene | `git diff --check` | Whitespace errors in tracked changes. |

No install, lint, formatter, static type checker, or third-party dependency is
currently declared. Do not imply those gates exist; add and document one only
when a concrete implementation requires it.

## Modules And Ownership

| Path | Owner / responsibility | Public entry point or artifact |
|---|---|---|
| [`../AGENTS.md`](../AGENTS.md) | Mandatory agent operating, logging, security, and challenge invariants. | Every agent session starts here. |
| [`../.agents/workflow.md`](../.agents/workflow.md) | Conditional task-to-workflow router. | Task classification and skill selection. |
| [`../problem_statement.md`](../problem_statement.md) | Authoritative participant-facing product and evaluation behavior. | Required input/output behavior. |
| [`diagnostics.md`](diagnostics.md) | Failure identifiers, triage sequence, and current diagnostic coverage. | Start here after a command or boundary fails. |
| [`../README.md`](../README.md) | Human quick start and submission overview. | `python3 code/main.py`. |
| [`../code/main.py`](../code/main.py) | Thin batch CLI/composition entry point; product behavior is not implemented. | `python3 code/main.py`. |
| [`../code/buy_or_wait/`](../code/buy_or_wait/) | Repository-owned product Python: provider-neutral AI boundary, immutable domain contract, and strict dataset repository. | `buy_or_wait.ai_boundary`, `buy_or_wait.domain`, `buy_or_wait.repository`. |
| [`../code/evaluation/`](../code/evaluation/) | Evaluation runner placeholder and usage-report source packaged under `evaluation/`. | `code/evaluation/main.py`; not runnable as an eval yet. |
| [`../dataset/`](../dataset/) | Supplied participant-facing input and blank output template. Do not modify inputs. | CSV files and `media/images/`. |
| [`../tests/`](../tests/) | Standard-library unit and contract tests mirroring source or repository contracts. | `python3 -m unittest ...`. |
| [`ai-foundation.md`](ai-foundation.md) | Persisted AI boundary, validation, retry, observability, and side-effect constraints. | Guidance for model-owning features. |
| [`initial-analysis/`](initial-analysis/) | Pre-plan product/data findings, evidence catalog, uncertainty register, and ordered analysis runbook. | Start at `initial-analysis/README.md`; hypotheses do not override the product specification. |
| [`master-plan.md`](master-plan.md) | Deadline-aware product implementation sequence, subsystem boundaries, work packages, acceptance gates, and task-brief handoff. | Start here when creating or ordering bounded implementation tasks. |
| [`wp-01-plan.md`](wp-01-plan.md) | Implementation-ready contract for WP-01 domain types, strict dataset loading, joined request cases, and repository validation. | Implement after the WP-00 freshness gate passes. |
| [`wp-02-plan.md`](wp-02-plan.md) | Dependency-gated implementation contract for typed evidence extraction, validation, targeting, and conservative resolution. | Implement only after the corrected WP-01 contract receives fresh independent acceptance. |
| [`foundation-plan.md`](foundation-plan.md) | Historical bootstrap decisions, not live operating guidance. | Context only. |
| [`foundation-review.md`](foundation-review.md) | Latest independent-style readiness record and observed commands. | Readiness verdict and gaps. |
| `output.csv` | Generated final predictions at repository root; absent until a solution run creates it. | Submission artifact. |
| `log.txt` | Append-only, gitignored conversation transcript. | Submission chat transcript. |

## Closest Precedents

| Change | Start with | Verification |
|---|---|---|
| Provider-neutral model call or validation seam | [`../code/buy_or_wait/ai_boundary.py`](../code/buy_or_wait/ai_boundary.py) and [`../tests/test_ai_boundary.py`](../tests/test_ai_boundary.py) | `python3 -m unittest tests.test_ai_boundary` |
| Dataset/header/artifact contract | [`../tests/test_repository_contract.py`](../tests/test_repository_contract.py) | `python3 -m unittest tests.test_repository_contract` |
| Domain types or repository loading | [`../code/buy_or_wait/domain.py`](../code/buy_or_wait/domain.py), [`../code/buy_or_wait/repository.py`](../code/buy_or_wait/repository.py), and [`../tests/test_repository.py`](../tests/test_repository.py) | `python3 -m unittest tests.test_repository` |
| Agent-facing document or navigation rule | [`../tests/test_agent_foundation_contract.py`](../tests/test_agent_foundation_contract.py) | `python3 -m unittest tests.test_agent_foundation_contract` |
| Product/data discovery or master-plan preparation | [`initial-analysis/README.md`](initial-analysis/README.md) and its TODO runbook | Recheck dataset contract, local links, and `git diff --check` |
| New product behavior | Owning module under `code/buy_or_wait/`; no implemented feature precedent exists yet | New focused test, then full unit suite |
| Evaluation behavior or usage accounting | [`../code/evaluation/main.py`](../code/evaluation/main.py) and [`../code/evaluation/usage_report.md`](../code/evaluation/usage_report.md); both remain placeholders | Feature-owned eval command must be added with implementation |

## Placement Rules

- Put product Python in `code/buy_or_wait/`; keep `code/main.py` a thin CLI and
  composition boundary.
- Put provider adapters behind `ModelProvider`. Keep operation-specific parsers
  beside the owning feature and add shared abstractions only after two real
  callers need them.
- Mirror source behavior under `tests/`. Use deterministic model fakes; ordinary
  tests never require network access.
- Add fixtures under `tests/fixtures/` only for a concrete tested behavior.
- Put testable repo-owned utilities, generators, validators, or local CLIs in
  `tools/`. Put thin human-invoked wrappers in `scripts/`.
- `tools/` currently holds only the IA-007 reconciliation query; add entries
  there only for real, working utilities.
- Keep public-example evaluation and final-run usage accounting under
  `code/evaluation/` so they package as `evaluation/` inside `code.zip`.
- Write generated predictions only to root `output.csv`; never overwrite
  participant-facing inputs under `dataset/`.
- Put cross-project operating and diagnostic guidance in `docs/`; keep live
  navigation here and historical bootstrap decisions in `foundation-plan.md`.
- Keep pre-plan observations, hypotheses, evidence annotations, and analysis
  handoff material under `docs/initial-analysis/`. Label authority and
  confidence explicitly; do not restate a hypothesis as product truth.

Any structural, canonical-command, placement, or repository-tool change must
update this map in the same change.

## Tool Registry Contract

There are currently no repository-owned tools or wrapper scripts. When a real
one is added, create the appropriate directory and add one registry row with all
of these fields; do not register placeholders.

| Path | Purpose | Invocation | Inputs | Outputs | Failure signals | Verification command |
|---|---|---|---|---|---|---|
| [`../tools/reconcile_structural_counts.py`](../tools/reconcile_structural_counts.py) | Reproduces IA-007 structural counts (REC-01/02/03/04/13) and the dataset fingerprint | `python3 tools/reconcile_structural_counts.py` | Read-only access to `dataset/` | JSON report on stdout (fingerprint, per-REC counts); writes nothing | Nonzero exit / traceback on schema drift; `ValueError` when users/requests/events no longer map 1:1 | `python3 tools/reconcile_structural_counts.py` |

The registry row and the utility's focused test must land with the tool. A
human-facing wrapper should contain only invocation glue; testable logic belongs
in `tools/` or the owning product module.

## Durable Constraints And Known Gaps

- Root agent rules and the product specification override summaries here.
- The financial engine, evidence resolver, final output validator, model
  adapter, prompts, eval runner, final usage data, and application runtime
  diagnostics are not implemented.
- `RepositoryValidationError` reason codes from `buy_or_wait.repository` are the
  focused redacted failure signal for dataset loading; triage under
  `REPO-CONTRACT` in [`diagnostics.md`](diagnostics.md).
- Raw model output remains untrusted until an operation-specific parser and
  deterministic financial/policy checks accept it.
- Secrets are environment-only and must not enter Git, logs, traces, datasets,
  or submission artifacts.
- No CI, container, datastore, migration, generated-code workflow, or
  `scripts/` directory exists or is currently justified. `tools/` contains the
  registered IA-007 reconciliation query only.
- Use [`diagnostics.md`](diagnostics.md) for honest current failure coverage and
  explicit deferred runtime/evaluation diagnostics.
- Initial corpus findings and P0 behavior questions are preserved in
  [`initial-analysis/README.md`](initial-analysis/README.md); the implementation
  sequence and retained policy experiments are now owned by
  [`master-plan.md`](master-plan.md).
