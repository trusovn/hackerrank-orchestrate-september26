# `code/buy_or_wait/` — Navigation Map

This is the package's **small, default-load navigation map**. For a bounded
change, select the row below, read only that module and its nearest test, then
use `rg` for the named symbol and its call sites. Do not load every module or
maintain a second catalogue of private implementation details here.

[`docs/project-map.md`](../../docs/project-map.md) owns repository-wide
commands, cross-package routing, and the full component map.

## Start Here

### Large-file routing

Do not read these files sequentially; each currently exceeds roughly 900
lines:

- `evidence.py` and `tests/test_evidence.py`
- `events.py` and `tests/test_events.py`
- `forecast.py` and `tests/test_forecast.py`
- `repository.py`
- `tests/test_planning.py`

Select the owning row below, start from its named public symbol, then narrow the
source and test together with:

```text
rg -n '<symbol-or-test-class>' code/buy_or_wait/<module>.py tests/test_<area>.py
rg -n '^class .*Tests' tests/test_<area>.py
python3 -m unittest tests.test_<area> -k '<TestClass-or-name-fragment>'
```

Read only the matching function and the nearest relevant test class.

| Change area | Module and public starting point | Nearest test / focused command |
|---|---|---|
| Shared records, enums, or parse helpers | `domain.py`: `RequestCase`, `EvidenceFact`, `EvidenceFactType`, `parse_date`, `parse_decimal` | `tests/test_repository.py` — `python3 -m unittest tests.test_repository` |
| Dataset validation or case assembly | `repository.py`: `DatasetRepository.from_directory`, `load_request_case`, `iter_request_cases`, `RepositoryValidationError` | `tests/test_repository.py` — `python3 -m unittest tests.test_repository` |
| Provider boundary or output validation | `ai_boundary.py`: `ModelProvider`, `OutputValidator`, `invoke_validated`, `FakeModelProvider` | `tests/test_ai_boundary.py` — `python3 -m unittest tests.test_ai_boundary` |
| Carrier facts, evidence validation, or targeting | `evidence.py`: `resolve_case_evidence`, `EvidenceResolution`, `EvidenceDiagnostic` | `tests/test_evidence.py` — `python3 -m unittest tests.test_evidence` |
| Event lifecycle, reserves, transfer pairing, or FX | `events.py`: `normalize_case_events`, `convert_exact`, `EventNormalization`, `EventNormalizationError` | `tests/test_events.py` — `python3 -m unittest tests.test_events` |
| Recurrence, variable-spending envelope, income, or baseline ledger | `forecast.py`: `build_baseline_forecast`, `BaselineForecast`, `ForecastPolicy`, `ForecastBuildError` | `tests/test_forecast.py` — `python3 -m unittest tests.test_forecast` |
| Payment replay or baseline capacity | `planning.py`: `replay_schedule`, `compute_baseline_capacity`, `SafetyReplay`, `CapacityResult`, `PlanningError` | `tests/test_planning.py` — `python3 -m unittest tests.test_planning.SafetyReplayTests` or `python3 -m unittest tests.test_planning.CapacityTests` |
| No-change candidate enumeration (WP-07A) | `planning.py`: `RecommendationMethod`, `PaymentTemplate`, `PlanCandidate`, `CandidatePool`, `build_no_change_candidate_pool` | `tests/test_planning.py` — `python3 -m unittest tests.test_planning.NoChangeCandidateTests` |
| Spending-change candidate enumeration (WP-07B) | `planning.py`: `SpendingChangeAction`, `FamilyAction`, `enumerate_spending_change_actions`, `build_candidate_pool` | `tests/test_planning.py` — `python3 -m unittest tests.test_planning.SpendingChangeCandidateTests` |
| Ranking and planning decision (WP-07C) | `planning.py`: `PlanningDecision`, `rank_key`, `plan_request` | `tests/test_planning.py` — `python3 -m unittest tests.test_planning.RankingAndDecisionTests` |
| Typed output row, codecs, and independent row validation (WP-08A/B) | `output.py`: `OUTPUT_COLUMNS`, `build_output_row`, `explain_decision`, `serialize_output_row`, `parse_output_row`, `validate_output_row`, `OutputValidationError` | `tests/test_output.py` — `python3 -m unittest tests.test_output.OutputRowValidationTests` |
| Batch coverage and atomic CSV publication (WP-08C) | `output.py`: `OutputContext`, `validate_output_batch`, `write_output_atomic` | `tests/test_output.py` — `python3 -m unittest tests.test_output.OutputBatchAndAtomicWriterTests` |
| One-case product composition and trace seam (WP-09A) | `pipeline.py`: `DecisionPolicy`, `PredictionTrace`, `predict_case` | `tests/test_pipeline.py` — `python3 -m unittest tests.test_pipeline.SingleCasePipelineTests` |

## Dependency Fan-Out

This is contract/data flow, not merely Python import direction:

```text
dataset -> repository -> RequestCase -> evidence -> events -> forecast -> planning
                    domain contracts support every deterministic stage above
               pipeline composes evidence->events->forecast->planning->output
ai_boundary remains isolated until an explicit composition layer consumes it
```

For a public contract change, inspect and test the owning stage and every
affected stage to its right. For a private implementation-only change, start
with the owning test and broaden only when behavior or a shared contract can
propagate.

## Package Boundaries

- Deterministic product logic (`domain`, `repository`, `evidence`, `events`)
  never imports the provider boundary. `ai_boundary.py` is the only provider
  surface, and raw model output remains untrusted until validated.
- `evidence.py` is offline and deterministic: it does no FX, recurrence,
  affordability arithmetic, plan selection, output writing, or provider calls.
- `repository.py` keeps cached validated message facts keyed by exact
  `message_id`; unknown carriers resolve conservatively to diagnostics.
- `forecast.py` consumes validated in-memory inputs and produces a baseline
  forecast only. It performs no file, clock, environment, provider, cache, or
  output access.
- `pipeline.py` composes the accepted deterministic stages behind one pure,
  single-case `predict_case`; it reads no files, loads no expected answers,
  writes no CSV, and catches no stage errors.
- Evaluation-only code belongs in `code/evaluation/`, outside this package.

## Maintenance

Keep this file to the routing information that prevents unnecessary discovery:
the owning module, its public entry point, and its nearest test. Update it only
when package ownership, a public starting symbol, a package boundary, or the
nearest focused test changes. Keep the large-file list current when a package
source or owning test becomes costly to read sequentially, and update the
fan-out only when a public dependency or data-flow boundary changes. Put
repository-wide commands and placement rules in
[`docs/project-map.md`](../../docs/project-map.md), not here.
