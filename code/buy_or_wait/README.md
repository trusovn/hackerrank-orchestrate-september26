# `code/buy_or_wait/` — Navigation Map

Local navigation map for bounded implementation work under this package.
`docs/project-map.md` routes agents here before broad source inspection.

Do not read every module for a bounded task. Start with the owning
module/symbols listed here, inspect the nearest relevant tests, and expand only
if necessary. Use `rg` for call sites; do not open whole modules up front —
`evidence.py` alone is ~2700 lines and most of it is unrelated to any single
change.

## Module Map

| Module | Responsibility | Read when | Start at |
|---|---|---|---|
| `domain.py` | Immutable shared domain contracts: records, enums, `EvidenceFact`, `RequestCase`, `OutputRow`, and CSV parse helpers. | Changing shared record shapes, enums, or parsing. | `RequestCase`, `EvidenceFact`, `EvidenceFactType`, `RequestRecord`, `PaymentOptionRecord`, `parse_date`, `parse_decimal` |
| `repository.py` | Strict dataset loading, validation, and case assembly. Fail-fast `RepositoryValidationError` reason codes. | Source ingestion, joins, header/field validation. | `DatasetRepository.from_directory`, `load_request_case`, `iter_request_cases`, `_validate_options`, `_validate_carriers`, `RepositoryValidationError` |
| `ai_boundary.py` | Provider-neutral model boundary: `ModelProvider` protocol, validation gate, offline fake. | Provider/model-boundary or validation-seam work. | `ModelProvider`, `OutputValidator`, `invoke_validated`, `ValidatedModelResult`, `FakeModelProvider` |
| `evidence.py` | Deterministic carrier-to-fact resolution: validated `EvidenceFact` values or conservative diagnostics. No provider/IO/FX/arithmetic. | Carrier classification, evidence validation, targeting. See map below. | `resolve_case_evidence`, `EvidenceResolution`, `EvidenceDiagnostic`, `EvidenceFactCandidate` |
| `events.py` | Lifecycle normalization: cash records, reserves, dated credits/debits, transfer pairs, settlement-date FX. | Event/lifecycle, cash-conservation, or FX work. See map below. | `normalize_case_events`, `EventNormalization`, `NormalizedCashRecord`, `NormalizedReserve`, `NormalizedCashEffect`, `NormalizationDecision`, `Disposition`, `EventNormalizationError` |
| `forecast.py` | Deterministic WP-05 baseline forecast: recurrence projection, conservative variable-spending envelopes, income continuation, exact settlement-date FX, and replay checkpoints. | Forecast horizon, recurrence, variable spending, forecast diagnostics, or ledger replay. | `build_baseline_forecast`, `BaselineForecast`, `ForecastPolicy`, `ForecastBuildError` |

## `evidence.py` — Internal Symbol Map

Public result types: `EvidenceResolution`, `EvidenceDiagnostic`,
`EvidenceFactCandidate`. Public entry point: `resolve_case_evidence`.

| Area | Symbols |
|---|---|
| Message evidence catalogue | `_MESSAGE_FACTS` |
| Image evidence catalogue | `_IMAGE_FACTS` |
| Field/target contracts | `_FieldContract`, `_FIELD_CONTRACTS`, `_AMOUNT`, `_DATE_EFFECTIVE`, `_DATE_SETTLEMENT` |
| Validation helpers | `_parse_amount`, `_parse_date`, `_parse_currency`, `_validate_candidate_shape`, `_validate_target`, `_validate_request_target` |
| Series/type profiles | `_SERIES_PROFILES`, `_SALARY_FACT_TYPES`, `_RENT_FACT_TYPES` |
| Resolution | `_resolve_message_facts`, `_resolve_image_facts`, `_resolve_cached_candidates`, `_resolve_primary_candidate`, `_resolve_secondary_candidate`, `_resolve_series_target` |
| Diagnostics plumbing | `_carrier_id`, `_reason_for` |

Most of the file is catalogue data or conservative outcome classes. Search for
the relevant symbol before reading sequentially.

Evidence validation bug -> `_validate_candidate_shape`, `_validate_target`,
`_FIELD_CONTRACTS`, then `tests/test_evidence.py::FailClosedValidationTests`,
`TargetingAndDurationTests`, `SettlementDatePreservationTests`

Carrier/message classification issue -> `_MESSAGE_FACTS`,
`_resolve_message_facts`, then `tests/test_evidence.py::CarrierCoverageTests`,
`SampleMessageOracleTests`

Image grounding issue -> `_IMAGE_FACTS`, `_resolve_image_facts`, then
`tests/test_evidence.py::ImageOracleTests`, `CarrierLocalGroundingTests`

Public evidence flow -> `resolve_case_evidence`, then
`tests/test_evidence.py::CarrierCoverageTests`, `BoundaryPreservationTests`

## `events.py` — Internal Symbol Map

Public result types: `EventNormalization`, `NormalizedCashRecord`,
`NormalizedReserve`, `NormalizedCashEffect`, `NormalizationDecision`,
`EventNormalizationError`. Public entry point: `normalize_case_events` (one
`_Normalizer` instance, its `run()` orchestrates all phases below).

| Area | Symbols |
|---|---|
| Decision helpers | `_event_decision`, `_fact_decision` |
| Input validation | `_validate` (contracts, duplicate IDs, unknown carriers/targets, fact routing buckets), `_build_rate_index` (rate conflicts/invalid rates) |
| FX conversion | `convert_exact` (public pure exact-FX converter seam: directed settlement-date rate, no rounding/inversion/chaining), `_convert` (exact directed settlement-date rate; `fx_rate_missing` when absent), `build_directed_rate_index` (directed rate index used by both `_convert` and `convert_exact`) |
| Event classification | `_classify` (status/direction dispatch: settled -> historical, pending debit -> reserve, scheduled -> dated effect, failed/cancelled/unrealized -> excluded), `_settled_boundary_check`, `_reserve`, `_resolve_effect_amount` (event amount or single fill fact; never invents amounts), `_record_fields` |
| Fact-only credits | `_emit_fact_credit` (confirmed future credit -> one dated credit effect) |
| Transfer pairs | `_classify_transfer_pairs`, `_find_counterpart` (exact match incl. `linked_event_id`), `_strip_pair_effects` (removes effects/reserves from neutralized events) |
| Ordering guard | `_remove_event_decision` (used by `_strip_pair_effects`) |
| Conservation | `_check_conservation` (single role per source, every event/fact decided, role/decision match) |
| Main entry | `run` (validate -> classify all -> pair neutralization -> fact-only credits -> fill-fact decisions -> diagnostic propagation -> conservation check) |

Most of the file is one `_Normalizer` class; phases run in the fixed order
documented in `run`. Search for the relevant symbol before reading
sequentially. `events.py` is pure: no I/O, clock, provider, recurrence, or
forecast work (see Boundaries).

Lifecycle/FX issue -> `_classify`, `_convert`, `_build_rate_index`, then
`tests/test_events.py::ExactFXTests`, `LifecycleMatrixTests`

Transfer-pair issue -> `_classify_transfer_pairs`, `_find_counterpart`,
`_strip_pair_effects`, then `tests/test_events.py::TransferPairTests`

Conservation/source-ownership issue -> `_check_conservation`, then
`tests/test_events.py::ConservationTests`

Fail-closed input issue -> `_validate`, `_build_rate_index`, then
`tests/test_events.py::BoundaryValidationTests`, `BlockedCorpusCaseTests`

## `forecast.py` — Internal Symbol Map

Public result types: `BaselineForecast`, `ForecastDiagnostic`,
`SeriesObservation`, `SeriesTrace`, `ProjectedOccurrence`, `PrimitiveMovement`,
`Checkpoint`. `BaselineForecast.primitive_movements` is the ordered immutable
cash/reserve replay ledger; each checkpoint links to its movement by
`movement_id`.
Policy types: `ForecastPolicy`, `RecurrenceTiming`, `IncomeContinuation`,
`VariableSpending`, `HorizonEndpoint`, `UnknownSameDayOrder`.
Public entry point: `build_baseline_forecast`.

| Area | Symbols |
|---|---|
| Boundary and error contract | `ForecastBuildError`, `_Builder._validate_boundary` |
| Recurrence detection | `_detect_monthly`, `_detect_weekly`, `_detect_tolerant_monthly`, `_detect_tolerant_weekly`, `_Builder._detect_cadence`, `_Builder._project_dates` |
| History classification and amounts | `_Builder._classify_histories`, `_Builder._series_key`, `_Builder._select_amount` |
| Evidence-driven lifecycle changes | `_Builder._apply_facts`, `_Builder._resolve_targets`, `_Builder._apply_fact` |
| Variable spending | `_Builder._project_variable`, `_Builder._project_variable_v1`, `_Builder._emit_envelope` |
| Income and FX | `_Builder._project_income_and_fx`, `_Builder._project_income_series`, `_Builder._convert` |
| Fixed debits and traceability | `_Builder._project_fixed_debits`, `_Builder._apply_date_replacement`, `_Builder._trace` |
| Ledger replay | `_Builder._build_ledger`, `_Builder.run` |

Forecast issue -> `build_baseline_forecast`, then the relevant `PolicySurfaceTests`,
`CadenceTests`, `FactLifecycleTests`, `VariableSpendingTests`, `IncomeAndFXTests`,
or `LedgerTests` in `tests/test_forecast.py`.

Boundary validation or conservative blocking issue -> `_Builder._validate_boundary`,
`ForecastBuildError`, and `tests/test_forecast.py::BoundaryValidationTests`

## Verification Commands

Run from the repository root:

| Scope | Command |
|---|---|
| Compile | `python3 -m compileall -q code tests` |
| Domain/repository | `python3 -m unittest tests.test_repository` |
| Evidence resolution | `python3 -m unittest tests.test_evidence` |
| Event/lifecycle | `python3 -m unittest tests.test_events` |
| Baseline forecast | `python3 -m unittest tests.test_forecast` |
| AI boundary | `python3 -m unittest tests.test_ai_boundary` |
| Agent docs contract | `python3 -m unittest tests.test_agent_foundation_contract` |
| All unit tests | `python3 -m unittest` |

Narrow to one test class, e.g.
`python3 -m unittest tests.test_events.ExactFXTests`.

## Task -> Starting Point

| Change | Module -> symbols | Nearest tests |
|---|---|---|
| Domain contract change | `domain.py` -> `RequestCase`, `EvidenceFact`, `EvidenceFactType`, records | `tests/test_repository.py`, `tests/test_evidence.py` |
| Dataset/repository issue | `repository.py` -> `DatasetRepository.from_directory`, `load_request_case`, `_validate_options`, `_validate_carriers`, `RepositoryValidationError` | `tests/test_repository.py::FullDatasetLoadingTests`, `ValidationFailureTests`, `RedactionTests`; `tests/test_repository_contract.py` |
| Evidence validation issue | `evidence.py` -> `_validate_candidate_shape`, `_validate_target`, `_FIELD_CONTRACTS` | `tests/test_evidence.py::FailClosedValidationTests` |
| Carrier classification/grounding | `evidence.py` -> `_MESSAGE_FACTS`, `_IMAGE_FACTS`, `_resolve_message_facts`, `_resolve_image_facts` | `tests/test_evidence.py::CarrierCoverageTests`, `SampleMessageOracleTests`, `ImageOracleTests` |
| Event/lifecycle/FX | `events.py` -> `normalize_case_events`, `_classify`, `_convert`, `_build_rate_index` | `tests/test_events.py::LifecycleMatrixTests`, `ExactFXTests` |
| Transfer-pair neutrality | `events.py` -> `_classify_transfer_pairs`, `_find_counterpart`, `_strip_pair_effects` | `tests/test_events.py::TransferPairTests` |
| Source-accounting conservation | `events.py` -> `_check_conservation` | `tests/test_events.py::ConservationTests` |
| Baseline forecast | `forecast.py` -> `build_baseline_forecast`, `_Builder.run`, `_Builder._build_ledger` | `tests/test_forecast.py` (`PolicySurfaceTests` through `LedgerTests`) |
| Provider/model boundary | `ai_boundary.py` -> `ModelProvider`, `invoke_validated`, `OutputValidator` | `tests/test_ai_boundary.py::AiBoundaryTests` |
| Offline evidence-strategy assessment | `code/evaluation/evidence_strategy.py` (outside this package) | `tests/test_evidence_strategy.py`, oracles under `tests/fixtures/evidence/` |

## Boundaries

- Deterministic product logic (`domain`, `repository`, `evidence`, `events`)
  never imports the provider boundary; `ai_boundary.py` is the only provider
  surface. Raw model output is untrusted until validated.
- `evidence.py` is offline and deterministic: no FX, recurrence projection,
  affordability arithmetic, plan selection, output writing, or provider calls.
- `repository.py` intentionally discards raw `message_text`; message evidence
  resolves from cached validated facts keyed by exact `message_id`, re-validated
  against the case at resolve time. Unknown carriers fail closed to a diagnostic.
- `forecast.py` consumes one validated `RequestCase`, `EvidenceResolution`, and
  `EventNormalization`; it reads no files, clock, environment, provider, or
  global cache, and writes no output. It produces only a baseline forecast for
  downstream payment-capacity and plan-selection work.
- Evaluation-only code lives in `code/evaluation/`, not under this package.

## Maintenance

Update this file in the same change as any module ownership, public symbol, or
closest-test change under this package (required by root `AGENTS.md` §1).
