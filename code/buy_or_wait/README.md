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

Select the owning row below, start from its named public symbol, then narrow the
source and test together with:

```text
rg -n '<symbol-or-test-class>' code/buy_or_wait/<module>.py tests/test_<area>.py
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
- Evaluation-only code belongs in `code/evaluation/`, outside this package.

## Maintenance

Keep this file to the routing information that prevents unnecessary discovery:
the owning module, its public entry point, and its nearest test. Update it only
when package ownership, a public starting symbol, a package boundary, or the
nearest focused test changes. Keep the large-file list current when a package
source or owning test becomes costly to read sequentially. Put repository-wide
commands and placement rules in [`docs/project-map.md`](../../docs/project-map.md),
not here.
