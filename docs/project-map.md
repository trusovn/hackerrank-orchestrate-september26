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
| Lifecycle normalization and exact FX | `python3 -m unittest tests.test_events` | WP-04 lifecycle matrix, source accounting, pending reserves, and exact directed settlement-date FX; fail-closed error atomicity. |
| Baseline forecast | `python3 -m unittest tests.test_forecast` | WP-05 recurrence, recurrence facts, variable-spending envelopes, income continuation, settlement-date FX, and ledger replay. |
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
  | [`../code/buy_or_wait/`](../code/buy_or_wait/) | Repository-owned product Python: provider-neutral AI boundary, immutable domain contract, strict dataset repository, deterministic typed-evidence resolver, lifecycle/forecasting, WP-06A independent safety replay, and WP-06B baseline capacity. Before broad source inspection, read [`../code/buy_or_wait/README.md`](../code/buy_or_wait/README.md) and start from the listed owning symbols/tests. | `buy_or_wait.ai_boundary`, `buy_or_wait.domain`, `buy_or_wait.repository`, `buy_or_wait.evidence`, `buy_or_wait.events` (`normalize_case_events`), `buy_or_wait.forecast` (`build_baseline_forecast`), `buy_or_wait.planning` (`replay_schedule`, `compute_baseline_capacity`, `build_no_change_candidate_pool`). |
| [`../code/evaluation/`](../code/evaluation/) | Evaluation runner and usage-report source packaged under `evaluation/`; `evidence_strategy.py` implements the WP-03 offline evidence-strategy gate. | `python3 code/evaluation/evidence_strategy.py --dataset dataset --output code/evaluation/evidence_strategy.json` (offline, deterministic; regenerates `evidence_strategy.json`). |
| [`../dataset/`](../dataset/) | Supplied participant-facing input and blank output template. Do not modify inputs. | CSV files and `media/images/`. |
| [`../tests/`](../tests/) | Standard-library unit and contract tests mirroring source or repository contracts. | `python3 -m unittest ...`. |
| [`ai-foundation.md`](ai-foundation.md) | Persisted AI boundary, validation, retry, observability, and side-effect constraints. | Guidance for model-owning features. |
| [`initial-analysis/`](initial-analysis/) | Pre-plan product/data findings, evidence catalog, uncertainty register, and ordered analysis runbook. | Start at `initial-analysis/README.md`; hypotheses do not override the product specification. |
| [`master-plan.md`](master-plan.md) | Deadline-aware product implementation sequence, subsystem boundaries, work packages, acceptance gates, and task-brief handoff. | Start here when creating or ordering bounded implementation tasks. |
| [`wp-01-plan.md`](wp-01-plan.md) | Implementation-ready contract for WP-01 domain types, strict dataset loading, joined request cases, and repository validation. | Implement after the WP-00 freshness gate passes. |
| [`wp-02-plan.md`](wp-02-plan.md) | Dependency-gated implementation contract for typed evidence extraction, validation, targeting, and conservative resolution. | Implement only after the corrected WP-01 contract receives fresh independent acceptance. |
| [`wp-03-plan.md`](wp-03-plan.md) | Dependency-gated contract for measuring the accepted offline evidence path and deciding whether a separately authorized provider trial is justified. | Implement only after WP-02 receives fresh independent acceptance; may defer until after WP-08. |
| [`wp-04-plan.md`](wp-04-plan.md) | Accepted-gate implementation contract for lifecycle normalization, pending reserves, source accounting, and exact directed settlement-date FX. | Implemented and accepted (2026-09-12): `code/buy_or_wait/events.py` and `tests/test_events.py` exist; run `python3 -m unittest tests.test_events` for the owning suite. WP-05 may now consume `normalize_case_events`. |
| [`wp-05-plan.md`](wp-05-plan.md) | Accepted WP-05 implementation contract for strict recurrence, finite variable/income/date policies, exclusive source ownership, and a replayable baseline ledger. | Implemented and accepted (2026-09-12); run `python3 -m unittest tests.test_forecast` for the owning suite. |
| [`wp-05a-replay-interface-brief.md`](wp-05a-replay-interface-brief.md) | Accepted narrow correction brief for WP-05’s independent `PrimitiveMovement` replay surface (2026-09-12). | WP-06A may proceed through its dependency/interface gate and preflight; run `python3 -m unittest tests.test_forecast.PrimitiveMovementTests tests.test_forecast.LedgerTests`. |
| [`wp-06-plan.md`](wp-06-plan.md) | WP-05-acceptance-gated, sequential WP-06A/WP-06B contracts for independent schedule/change replay, exact failure checkpoints, safe-today capacity, and exhaustive baseline earliest-date search. | WP-06A implemented and accepted (2026-09-13): `planning.py`/`test_planning.py` exist; run `python3 -m unittest tests.test_planning.SafetyReplayTests`. WP-06B implemented and accepted (2026-09-13): `compute_baseline_capacity`/`CapacityResult` live in the same `planning.py`; run `python3 -m unittest tests.test_planning.CapacityTests`. WP-06 complete; WP-07 may proceed. |
| [`wp-07-plan.md`](wp-07-plan.md) | Sequential implementation contracts for exact no-change candidates, recurring-series spending changes, changed-candidate replay, deterministic ranking, and status/method derivation. | WP-07A accepted (2026-09-13). WP-07B accepted (2026-09-13): `enumerate_spending_change_actions` and `build_candidate_pool` in `planning.py`, covered by `python3 -m unittest tests.test_planning.SpendingChangeCandidateTests`; run `python3 -m unittest tests.test_planning` for the owning suite. WP-07C accepted (2026-09-13): `PlanningDecision`, `rank_key`, and `plan_request` in `planning.py`, covered by `python3 -m unittest tests.test_planning.RankingAndDecisionTests`. WP-07 complete; WP-08 may proceed. |
| [`wp-08-plan.md`](wp-08-plan.md) | WP-07C-acceptance-gated, sequential WP-08A/B/C contracts for typed rows and grounded explanations, canonical codecs, independent row validation, exact batch coverage, and atomic CSV replacement. | WP-08A accepted (2026-09-13): `RecommendedPaymentMethod`, `OutputRow`, and canonical output codecs; run `python3 -m unittest tests.test_output.OutputRowBuildAndCodecTests`. WP-08B accepted (2026-09-13, after one correction cycle): `validate_output_row` recomputes capacity, enforces preference/coherence gates, validates exact plans/actions, and runs a fresh replay; run `python3 -m unittest tests.test_output.OutputRowValidationTests`. WP-08C implemented (2026-09-13, pending review): `OutputContext`, `validate_output_batch`, and `write_output_atomic` publish one validated row per evaluation request in order through a flushed/reparsed/revalidated sibling temp and one `os.replace`; run `python3 -m unittest tests.test_output.OutputBatchAndAtomicWriterTests`. WP-08C accepted (2026-09-13): batch validation and atomic publication reviewed clean; WP-08 complete; WP-09/WP-10 may proceed. |
| [`wp-09-plan.md`](wp-09-plan.md) | WP-08C-acceptance-gated, sequential WP-09A–F contracts for one-case composition, isolated public oracle/metrics, the five bounded experiments, conservative selection, and one frozen global policy. | WP-09A implemented (2026-09-13): `DecisionPolicy`, `PredictionTrace`, and `predict_case` in `pipeline.py`; run `python3 -m unittest tests.test_pipeline.SingleCasePipelineTests`. Next: immediate fresh independent WP-09A acceptance, then WP-09B. |
| [`wp-10-plan.md`](wp-10-plan.md) | WP-09F-acceptance-gated, sequential WP-10A/B/C contracts for deterministic batch results, safe diagnostics, CLI/atomic output publication, reconciled usage reporting, and the real 250-request run. | Planned while WP-09 is in progress. Do not begin WP-10A until WP-09F receives fresh independent acceptance and the shared pipeline files are handed off. |
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
 | Carrier-to-fact evidence resolution | [`../code/buy_or_wait/evidence.py`](../code/buy_or_wait/evidence.py) and [`../tests/test_evidence.py`](../tests/test_evidence.py) | `python3 -m unittest tests.test_evidence` |
| Lifecycle normalization or exact FX | [`../code/buy_or_wait/events.py`](../code/buy_or_wait/events.py) and [`../tests/test_events.py`](../tests/test_events.py) | `python3 -m unittest tests.test_events` |
| Baseline forecast | [`../code/buy_or_wait/forecast.py`](../code/buy_or_wait/forecast.py) and [`../tests/test_forecast.py`](../tests/test_forecast.py) | `python3 -m unittest tests.test_forecast` |
| Independent schedule safety replay | [`../code/buy_or_wait/planning.py`](../code/buy_or_wait/planning.py) and [`../tests/test_planning.py`](../tests/test_planning.py) | `python3 -m unittest tests.test_planning.SafetyReplayTests` |
| Baseline capacity | [`../code/buy_or_wait/planning.py`](../code/buy_or_wait/planning.py) and [`../tests/test_planning.py`](../tests/test_planning.py) | `python3 -m unittest tests.test_planning.CapacityTests` |
| WP-07A no-change candidates | [`../code/buy_or_wait/planning.py`](../code/buy_or_wait/planning.py) and [`../tests/test_planning.py`](../tests/test_planning.py) | `python3 -m unittest tests.test_planning.NoChangeCandidateTests` |
| WP-07B spending-change candidates | [`../code/buy_or_wait/planning.py`](../code/buy_or_wait/planning.py) and [`../tests/test_planning.py`](../tests/test_planning.py) | `python3 -m unittest tests.test_planning.SpendingChangeCandidateTests` |
| WP-07C ranking and decision | [`../code/buy_or_wait/planning.py`](../code/buy_or_wait/planning.py) and [`../tests/test_planning.py`](../tests/test_planning.py) | `python3 -m unittest tests.test_planning.RankingAndDecisionTests` |
| Output row validation | [`../code/buy_or_wait/output.py`](../code/buy_or_wait/output.py) and [`../tests/test_output.py`](../tests/test_output.py) | `python3 -m unittest tests.test_output.OutputRowValidationTests` |
| One-case product composition (WP-09A) | [`../code/buy_or_wait/pipeline.py`](../code/buy_or_wait/pipeline.py) and [`../tests/test_pipeline.py`](../tests/test_pipeline.py) | `python3 -m unittest tests.test_pipeline.SingleCasePipelineTests` |
| Agent-facing document or navigation rule | [`../tests/test_agent_foundation_contract.py`](../tests/test_agent_foundation_contract.py) | `python3 -m unittest tests.test_agent_foundation_contract` |
| Product/data discovery or master-plan preparation | [`initial-analysis/README.md`](initial-analysis/README.md) and its TODO runbook | Recheck dataset contract, local links, and `git diff --check` |
| New product behavior | Owning module under `code/buy_or_wait/`; no implemented feature precedent exists yet | New focused test, then full unit suite |
| Evaluation behavior or usage accounting | [`../code/evaluation/main.py`](../code/evaluation/main.py) and [`../code/evaluation/usage_report.md`](../code/evaluation/usage_report.md); usage report remains a placeholder | Feature-owned eval command must be added with implementation |
| Evidence-strategy assessment | [`../code/evaluation/evidence_strategy.py`](../code/evaluation/evidence_strategy.py) and [`../tests/test_evidence_strategy.py`](../tests/test_evidence_strategy.py) with data-only oracles under [`../tests/fixtures/evidence/`](../tests/fixtures/evidence/) | `python3 -m unittest tests.test_evidence_strategy` |

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
- The financial engine, final output validator, model
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
