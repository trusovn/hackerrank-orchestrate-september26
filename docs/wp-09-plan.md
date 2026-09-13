# WP-09 — Public-Sample Oracle And Bounded Calibration

Status: **PLANNED — WAITING FOR FRESH WP-08B AND WP-08C ACCEPTANCE**

Authority: [`master-plan.md`](master-plan.md), WP-09; governed by
[`../problem_statement.md`](../problem_statement.md), especially Files
Provided, Required Output, Important Behavior, and Evaluation; and by
[`initial-analysis/08-financial-semantics-decisions.md`](initial-analysis/08-financial-semantics-decisions.md),
especially Bounded Implementation Experiments and Output Validation And
Public-Sample Metrics.

## Why WP-09 Is Split

The unsplit package is approximately **70 tool calls / 210 minutes / large
context**. It combines a product composition seam, an evaluation-only oracle,
multi-field metrics, three forecast/arithmetic experiments, two planning
experiments, and durable policy promotion. That exceeds both user thresholds:
15 calls and 45 minutes.

Split the same total scope into six sequential, independently testable parts:

1. **WP-09A:** one-case product prediction and trace seam — 11 calls / 35
   minutes.
2. **WP-09B:** isolated public oracle, comparison records, and baseline metrics
   — 12 calls / 35 minutes.
3. **WP-09C:** existing forecast-policy experiments EXP-RV and EXP-DATE — 10
   calls / 30 minutes.
4. **WP-09D:** bounded EXP-NUM conversion-rounding policy — 12 calls / 35
   minutes.
5. **WP-09E:** bounded EXP-CAP and EXP-CHANGE planning policies — 13 calls / 40
   minutes.
6. **WP-09F:** conservative selection, frozen global configuration, and final
   25-row evidence artifacts — 10 calls / 35 minutes.

Run the parts in order. They intentionally share `pipeline.py`, evaluation
code, and later policy surfaces, so they must not be implemented concurrently.
Every part stays below the split thresholds and requires at most a strong model
with medium reasoning, not strong plus high reasoning.

## Direction Trace

- Direction contribution: measure the complete deterministic decision path on
  all 25 solved samples and resolve only EXP-RV, EXP-DATE, EXP-NUM, EXP-CAP,
  and EXP-CHANGE within their recorded finite bounds.
- User-observable effect: the final batch uses one explicit, contract-valid
  global policy supported by reproducible public-sample evidence rather than
  request-specific fitting.
- Why now: WP-09 consumes the accepted WP-02 through WP-08 seams and its
  selected configuration is required by WP-10.
- Direction decisions used: `problem_statement.md` Files Provided through
  Evaluation; `master-plan.md` sections 2–8, WP-09, and Risk Register And Stop
  Rules; FIN-002/003/004/004A/008/009/010/013/014 and EXP-RV/DATE/NUM/CAP/CHANGE
  in the financial-semantics decisions.
- New direction decisions required: `None`

## Current-State And Dependency Gate

Planning observed this state on 2026-09-13:

- `code/evaluation/main.py` is empty.
- `DatasetRepository.iter_request_cases(RequestScope.SAMPLE)` already exposes
  25 sample cases in source order and strips all seven solved output columns.
- `ForecastPolicy` already represents every EXP-RV and EXP-DATE candidate.
- Exact conversion is the current arithmetic default; planning currently uses
  payment-count caps and series-wide spending changes.
- `code/buy_or_wait/output.py` and `tests/test_output.py` contain concurrent,
  unaccepted WP-08B work. This plan owns neither working copy.

Before WP-09A edits, require a fresh independent WP-08C `ACCEPT`, a clean
handoff for the final public `output.py` APIs, and no overlapping dirty files.
Do not adapt WP-09 to the in-progress WP-08 implementation. If WP-08's accepted
names differ from this plan's illustrative signatures, preserve the semantics
below and bind to those accepted public names.

## Package Authority And Scope

| Item | Contract |
|---|---|
| Repository root | `/Users/mtrusov/work/repos/hkr-orc-0926` |
| Dependencies | WP-02 through WP-07 accepted; fresh WP-08B then WP-08C acceptance required before A |
| Product owner | `code/buy_or_wait/pipeline.py`; narrow policy parameters in their existing owners only when D/E begin |
| Evaluation owner | `code/evaluation/main.py` |
| Primary tests | `tests/test_pipeline.py`, `tests/test_evaluation.py`, and narrowly affected owner tests |
| Durable evidence | `code/evaluation/sample_report.json`, `code/evaluation/policy_selection.json` created only by F |
| Navigation updates | `code/buy_or_wait/README.md` for the new product seam; `docs/project-map.md` for paths and commands |
| Read-only context | accepted repository/evidence/events/forecast/planning/output APIs and tests; the authorities above |
| Out of scope | evaluation request predictions, root `output.csv`, CLI batch wiring, usage totals, ZIP packaging, live providers, new evidence extraction, new policy candidates, wider sweeps, scoring-weight guesses, and request/user-specific exceptions |

## Proposed Architecture And Data Flow

Keep product composition separate from public labels. Use the existing typed
stage outputs; do not create a generic workflow engine, plugin registry, or
second financial implementation.

```text
DatasetRepository -- RequestScope.SAMPLE --> RequestCase (8 input fields only)
                                              |
                                              v
                           predict_case(case, DecisionPolicy)         (09A)
                             evidence -> events -> forecast
                             -> planning -> output build/validate
                                              |
                                              v
                                      PredictionTrace
                                              |
                    +-------------------------+-------------------------+
                    |                                                   |
                    v                                                   v
       evaluation-only solved-column loader                    compact safe trace
       (request_id + 7 expected fields)                         (no raw carriers)
                    |                                                   |
                    +-------------------- compare -----------------------+
                                              |
                                              v
                      metrics + mismatch reasons + optimism signals      (09B)
                                              |
                  bounded candidate matrices/replays only                (09C/D/E)
                                              |
                                              v
                   conservative dominance + documented defaults          (09F)
                                              |
                                              v
                     one SELECTED_DECISION_POLICY in pipeline.py
                         used by sample evaluation and later WP-10
```

### Product seam

Use one flat `pipeline.py`. Exact names may follow accepted local style, but
preserve these boundaries:

```python
@dataclass(frozen=True)
class DecisionPolicy:
    forecast: ForecastPolicy
    # D adds conversion_rounding only when it is exercised.
    # E adds planning only when it is exercised.

DEFAULT_DECISION_POLICY: DecisionPolicy
SELECTED_DECISION_POLICY: DecisionPolicy  # F freezes the measured winner

@dataclass(frozen=True)
class PredictionTrace:
    request_id: str
    policy_id: str
    evidence: EvidenceResolution
    normalization: EventNormalization
    baseline: BaselineForecast
    decision: PlanningDecision
    output_row: OutputRow

def predict_case(
    case: RequestCase,
    policy: DecisionPolicy = SELECTED_DECISION_POLICY,
) -> PredictionTrace: ...
```

`predict_case` is pure, deterministic, offline, and single-case. It resolves
evidence, normalizes events, builds the baseline, plans, builds the row, and
calls the accepted independent row validator before returning. It does not
read files, inspect request scope, load expected answers, write CSV, catch and
hide stage errors, generate a run ID, or collect usage. WP-10 owns batch/CLI
composition.

`policy_id` is a stable canonical string of enum values, for example
`rv=strict-v0-i0;date=d90-debit-first;num=exact;cap=count;change=series`.
Never use object repr, a randomized hash, a timestamp, request ID, or user ID.

### Evaluation seam

Keep `code/evaluation/main.py` evaluation-only and standard-library-only. Its
publicly testable functions should cover:

```python
def load_sample_oracle(dataset_root: Path) -> tuple[ExpectedSample, ...]: ...
def compare_sample(trace: PredictionTrace, expected: ExpectedSample) -> SampleComparison: ...
def summarize(comparisons: Sequence[SampleComparison]) -> dict[str, object]: ...
def run_samples(dataset_root: Path, policy: DecisionPolicy) -> SampleReport: ...
def run_experiment(dataset_root: Path, experiment_id: str) -> ExperimentReport: ...
def select_policy(experiments: Sequence[ExperimentReport]) -> PolicySelection: ...
```

Do not duplicate product parsers. Build the expected eight-field mapping from
`request_id` plus the seven solved output columns, then use the accepted
`parse_output_row`. Product predictions come only from the repository's sample
`RequestCase`; the oracle is joined after prediction by `request_id`.

The default command must be useful and non-mutating:

```text
python3 code/evaluation/main.py
```

It loads `dataset/`, evaluates all 25 samples with
`SELECTED_DECISION_POLICY`, prints deterministic JSON, exits nonzero for an
incomplete report, an unmapped mismatch, or any contract/safety failure, and
does not fail merely because a public value differs. Add explicit `--output`
and `--experiment` arguments only for the bounded runs in this plan. Tests use
temporary output paths; the implementation never rewrites participant files.

### Required report model

Each of the 25 comparison rows contains at least:

- request ID and policy ID;
- predicted and expected canonical fields;
- status/method exact results;
- signed, absolute, and normalized safe-amount residuals;
- earliest-date exact/empty-state/signed-day results;
- raw and parsed-semantic plan results;
- raw and parsed-semantic spending-change results;
- predicted explanation trace-consistency and informational raw equality;
- contract-validator result;
- compact evidence/forecast/planning reason codes and source IDs; and
- one reason record for every mismatch.

Compact traces may include source IDs, series observation IDs, generated
dates, capacity, selected payments/actions, minimum headroom, and stable reason
codes. They must not include raw message/image/request text, credentials,
environment values, or entire checkpoint ledgers.

Mismatch reason categories are exactly `policy`, `evidence`, `eligibility`,
`arithmetic`, and `formatting`. Apply this deterministic priority:

1. parse/canonical failure or raw-only difference with semantic equality ->
   `formatting`;
2. a relevant blocking/unresolved evidence diagnostic -> `evidence`;
3. exact internal versus cent-rounded numeric divergence -> `arithmetic`;
4. status, method, semantic plan, option, or change eligibility divergence ->
   `eligibility`;
5. remaining amount/date/forecast divergence -> `policy`.

An explanation is consistent only when the accepted production validator
accepts the generated explanation. Expected prose equality is informational;
do not invent a lexical or semantic explanation score.

### Aggregate metrics

Report all of these without combining unlike currencies:

- contract failures by invariant and request; target zero;
- status and method exact counts and confusion tables, separately and jointly;
- money exact count and per-request signed/absolute/normalized error;
- per-currency money summaries and one aggregate of normalized errors only;
- date exact count, empty/nonempty disagreements, and signed/absolute day
  errors only where both dates exist;
- raw and semantic exact counts for plans and changes, with fee and
  missing/extra-payment reasons separated;
- explanation trace-consistency count and informational raw equality;
- scenario breakdowns for preference-only capacity, salary change/stop,
  pending debit, pending credit, FX, image evidence, partial, installments,
  and spending changes, always showing the denominator; and
- optimism warnings: positive safe-amount residual, earlier predicted date,
  and newly affordable prediction, kept separate.

Scenario membership is evaluation metadata derived from supplied public
evidence and stored in evaluation code, never imported by product code. The
implementer must use the request IDs already named in FIN/EXP authority; it may
add an ID to a scenario only with a cited participant-facing source and must
not infer product behavior from the annotation.

## Global Experiment And Selection Contract

Experiments run offline on public samples only. They never read
`dataset/requests.csv` labels, call a provider, or modify the sample file.
Cache identical deterministic stage results within one process, keyed by
sample input fingerprint plus canonical policy ID; a cache is optional when
the full bounded run is already cheap and must not change results.

Run experiments in this order, carrying an earlier promotion into later
experiments and holding not-yet-tested dimensions at their conservative
defaults:

1. EXP-RV;
2. EXP-DATE;
3. EXP-NUM;
4. EXP-CAP;
5. EXP-CHANGE.

For each experiment, the incumbent is the documented conservative default or
the already promoted value for that dimension. A candidate is eligible only
when its targeted deterministic fixtures pass, all 25 generated rows that it
touches remain contract-valid, and it introduces no unexplained optimism
warning.

Promote only conservative Pareto dominance on that experiment's declared
discriminators: no relevant exact-match count decreases, no relevant aggregate
normalized money/date error increases, and at least one declared metric
strictly improves. Any tie, mixed tradeoff, fixture failure, unexplained new
optimism, or non-discriminating public result keeps the incumbent. This
operationalizes the recorded stop rules without inventing organizer weights.

Never widen a matrix, tune buffers/lookbacks, branch on request/user ID, add a
new policy value, or retry a rejected policy with an exception.

---

# WP-09A — Compose And Validate One Prediction

Status: **READY AFTER FRESH WP-08C ACCEPTANCE**

```yaml
agent_tier: standard
reasoning: medium
review: immediate
budget: 11 tool calls / 35 minutes / medium context
```

## Readiness Route

`implementer self-preflight` — confirm fresh WP-08C acceptance, inspect its
final public build/validate APIs, and confirm no overlap with dirty WP-08 files.

## Outcome

Expose one pure product function that runs a supplied `RequestCase` through
the accepted deterministic stages under one explicit forecast policy and
returns a validated row plus trace.

## Required Work

1. Run accepted WP-08 and upstream focused tests before editing.
2. Add fail-first `SingleCasePipelineTests` with one small synthetic case.
3. Create `pipeline.py` with `DecisionPolicy`, default/selected aliases,
   canonical policy ID, `PredictionTrace`, and `predict_case`.
4. Call only accepted public stage functions in order. Pass the same case and
   stage outputs forward; do not reconstruct them.
5. Require the accepted independent row validator before returning.
6. Preserve typed stage exceptions and safe reason/source IDs; do not replace
   them with success or a generic row.
7. Update package navigation after the public seam exists.

## Acceptance Criteria

- **A-AC-01:** a valid synthetic case returns matching IDs through evidence,
  normalization, forecast, decision, and output row, and the row validates.
- **A-AC-02:** explicit non-default `ForecastPolicy` changes only the forecast
  path and appears in the stable policy ID.
- **A-AC-03:** a stage or validator failure propagates and no row/file is
  published.
- **A-AC-04:** `predict_case` has no file, clock, environment, network,
  provider, batch, oracle, or usage behavior.

## WP-09A Verification

| Evidence | Scenario and oracle | Command |
|---|---|---|
| Dependency | accepted final output and upstream stages | `python3 -m unittest tests.test_output tests.test_planning tests.test_forecast` |
| Fail-first/targeted | stage order, policy propagation, validated trace, failure propagation | `python3 -m unittest tests.test_pipeline.SingleCasePipelineTests` |
| Owning suite | complete new composition seam | `python3 -m unittest tests.test_pipeline` |
| Compile | imports and syntax | `python3 -m compileall -q code tests` |
| Broader gate | final A bytes | `python3 -m unittest tests.test_pipeline tests.test_output tests.test_planning tests.test_forecast` then `git diff --check` |

## WP-09A Stops And Handoff

- Stop without fresh WP-08C acceptance or on overlapping dirty files.
- Stop if an accepted stage lacks a public callable needed for composition;
  request the smallest upstream seam rather than copy logic.
- Do not add sample loading or policy variants in A.
- Next: guided A implementation, then immediate fresh independent acceptance.
  Accepted A bytes unblock B.

---

# WP-09B — Isolate The Oracle And Measure The Selected Baseline

Status: **READY AFTER WP-09A ACCEPTANCE**

```yaml
agent_tier: strong
reasoning: medium
review: immediate
budget: 12 tool calls / 35 minutes / medium-high context
```

## Readiness Route

`implementer self-preflight` — confirm accepted A trace fields, the sample
header, and the accepted output parser/validator interfaces.

## Outcome

Produce a complete deterministic comparison report for all 25 samples without
allowing solved columns to affect any prediction.

## Required Work

1. Add fail-first `SampleOracleIsolationTests`, `SampleMetricTests`, and
   `MismatchReasonTests` using temporary synthetic CSVs and fabricated traces.
2. Implement strict solved-column loading in evaluation code. Require the
   exact 15-column sample header, unique IDs, and canonical expected rows.
3. Predict all repository sample cases first; load/join expected values only
   in the evaluation layer.
4. Prove isolation by mutating every solved output column while keeping the
   first eight columns fixed: predictions must be identical and comparisons
   must change.
5. Implement per-row comparisons, finite mismatch taxonomy, aggregate metrics,
   scenario breakdowns, and optimism warnings exactly as specified above.
6. Add the non-mutating default CLI and deterministic JSON rendering.
7. Exit nonzero for missing/extra/duplicate rows, unmapped mismatches,
   non-finite metrics, or any generated-row contract failure.

## Acceptance Criteria

- **B-AC-01:** exactly 25 unique sample IDs are predicted and reported in
  sample-file order; missing, extra, duplicate, or reordered joins reject.
- **B-AC-02:** solved columns are inaccessible to product prediction and a
  poisoned-label test proves it.
- **B-AC-03:** every required metric has exact numerator/denominator or
  per-request residual evidence; raw cross-currency money is never averaged.
- **B-AC-04:** every mismatch has one allowed category and stable reason code;
  raw-only versus semantic plan/change differences remain distinct.
- **B-AC-05:** contract failures, explanation consistency, and three optimism
  signal types are separate from accuracy metrics.
- **B-AC-06:** the default CLI is deterministic, offline, writes nothing, and
  does not fail solely for label mismatches.

## WP-09B Verification

| Evidence | Scenario and oracle | Command |
|---|---|---|
| Dependency | accepted sample isolation and A prediction | `python3 -m unittest tests.test_repository.FullDatasetLoadingTests tests.test_pipeline` |
| Fail-first/targeted | poisoned labels, exact metric arithmetic, cause coverage, malformed joins | `python3 -m unittest tests.test_evaluation.SampleOracleIsolationTests tests.test_evaluation.SampleMetricTests tests.test_evaluation.MismatchReasonTests` |
| Owning suite | all evaluation behavior through B | `python3 -m unittest tests.test_evaluation` |
| Real public boundary | 25-row report; zero missing/unmapped/contract counts | `python3 code/evaluation/main.py` |
| Broader gate | final B bytes | `python3 -m unittest tests.test_evaluation tests.test_pipeline tests.test_repository tests.test_output` then `git diff --check` |

## WP-09B Stops And Handoff

- Stop if product code would need expected outputs, sample annotations, or an
  evaluation import.
- Stop if expected rows cannot be parsed by accepted output codecs; classify
  and escalate the contract discrepancy rather than weakening parsing.
- Do not implement candidate sweeps in B.
- Next: guided B implementation, then immediate fresh independent acceptance.
  Accepted B bytes unblock C.

---

# WP-09C — Run EXP-RV And EXP-DATE Within Existing Forecast Policy

Status: **READY AFTER WP-09B ACCEPTANCE**

```yaml
agent_tier: standard
reasoning: medium
review: immediate
budget: 10 tool calls / 30 minutes / medium context
```

## Readiness Route

`implementer self-preflight` — confirm all five existing `ForecastPolicy`
dimensions and B's experiment/report extension seam.

## Outcome

Run and report the exact 12 EXP-RV and four EXP-DATE forecast configurations,
without adding a policy value or selecting a winner yet.

## Required Work

1. Add fail-first `ForecastExperimentTests` that assert exact candidate sets,
   counts, primary discriminators, deterministic order, and no duplicate IDs.
2. EXP-RV is exactly the Cartesian product:
   - recurrence: strict, tolerant ±2 days;
   - variable: V0 max complete month, V1 max cadenced occurrence, V2 rounded-up
     mean complete month;
   - income: I0 explicit ongoing, I1 strict recent history.
3. Hold date policy at inclusive day +90/debit-first for all 12 EXP-RV runs.
   Run all 25 samples once per configuration; highlight requests 02, 03, 05,
   07, 08, 12, 13, 15, 17, 19, and 25.
4. EXP-DATE is exactly day +89/+90 crossed with debit-first/credit-first. Hold
   the accepted RV incumbent and all later dimensions at defaults. Run all 25;
   highlight requests 03, 08, and 18.
5. Record per-policy metrics, per-request delta from incumbent, recurrence
   observation/exclusion IDs, and optimism warnings.
6. Require the existing explicit-stop, next-only amendment, opening reserve,
   same-day salary/expense, and day-90 owner fixtures before marking a
   candidate eligible.
7. Do not choose or modify defaults in C.

## Acceptance Criteria

- **C-AC-01:** EXP-RV reports exactly 12 unique configurations × 25 rows and
  EXP-DATE exactly four unique configurations × 25 rows.
- **C-AC-02:** only the declared dimensions vary; all other policy values and
  input bytes remain fixed.
- **C-AC-03:** every promoted recurrence candidate would be traceable to source
  observations/exclusions; stopped, final-payroll, and next-only income never
  become unexplained recurring credits.
- **C-AC-04:** candidate fixture eligibility and public metrics are reported
  separately; C performs no policy promotion.

## WP-09C Verification

| Evidence | Scenario and oracle | Command |
|---|---|---|
| Dependency | B metrics and existing forecast dimensions | `python3 -m unittest tests.test_evaluation tests.test_forecast.PolicySurfaceTests` |
| Fail-first/targeted | exact matrices, fixed dimensions, counts, deltas | `python3 -m unittest tests.test_evaluation.ForecastExperimentTests` |
| Owner safety fixtures | recurrence/income/variable/date boundaries | `python3 -m unittest tests.test_forecast` |
| Real bounded runs | complete EXP-RV and EXP-DATE reports | `python3 code/evaluation/main.py --experiment EXP-RV` then `python3 code/evaluation/main.py --experiment EXP-DATE` |
| Broader gate | final C bytes | `python3 -m unittest tests.test_evaluation tests.test_pipeline tests.test_forecast` then `git diff --check` |

## WP-09C Stops And Handoff

- Stop at 12 and four configurations even when results tie.
- Stop if a candidate requires a new lookback, cadence, buffer, horizon, or
  same-day rule.
- Next: guided C implementation, then immediate fresh independent acceptance.
  Accepted C bytes unblock D.

---

# WP-09D — Run EXP-NUM With One Directional Conversion Policy

Status: **READY AFTER WP-09C ACCEPTANCE**

```yaml
agent_tier: strong
reasoning: medium
review: immediate
budget: 12 tool calls / 35 minutes / medium-high context
```

## Readiness Route

`implementer self-preflight` — locate every exact FX conversion used by event
normalization, forecast recurrence, and changed-spending replay on accepted C
bytes; confirm accepted validator policy propagation.

## Outcome

Represent and compare exactly two global arithmetic policies—exact internal
conversion/output-only rounding and directional per-conversion cent rounding—
through the same prediction and validation path.

## Required Work

1. Add fail-first exact/directional conversion tests before changing a
   production signature.
2. Add one two-value enum in the narrow shared conversion owner. Keep the
   existing exact conversion callable and behavior backward-compatible.
3. Directional mode rounds each non-home-currency conversion to 0.01: positive
   debit obligations round upward and positive credits round downward. Home-
   currency amounts do not round; rate date/direction and exact `Decimal`
   multiplication do not change.
4. Route the policy explicitly through normalization, forecast conversions,
   changed-action replay, pipeline, and accepted output validation. No module
   may consult mutable global state or environment flags.
5. Extend `DecisionPolicy` and its ID only after the policy works end-to-end.
6. EXP-NUM runs exactly the two configurations across all 25 samples, holding
   the accepted RV/date incumbent and later planning dimensions fixed.
7. Highlight request 25 arithmetic and requests 02, 06, 12, 17, 21, and 22
   lexical/raw-versus-parsed results. A lexical-only gain is not an arithmetic
   improvement.
8. Require wrong-date, reverse/missing pair, fractional debit/credit, exact IDR
   28,499,994, negative-zero, and no-float fixtures.

## Acceptance Criteria

- **D-AC-01:** exact mode is byte/behavior compatible with the accepted
  pre-D pipeline and remains the default incumbent.
- **D-AC-02:** directional mode rounds only converted debits up and converted
  credits down; home amounts, option values, and canonical rendering are not
  silently rounded.
- **D-AC-03:** planning and output validation use the same arithmetic policy as
  baseline construction, including changed-action replay.
- **D-AC-04:** EXP-NUM reports exactly two configurations × 25 rows with raw,
  parsed, and residual evidence; D performs no promotion.

## WP-09D Verification

| Evidence | Scenario and oracle | Command |
|---|---|---|
| Fail-first/targeted | exact versus directional debit/credit/home conversion and policy propagation | `python3 -m unittest tests.test_events.NumericPolicyTests tests.test_forecast.NumericPolicyTests tests.test_planning.NumericPolicyTests tests.test_output.NumericPolicyValidationTests` |
| Evaluation | exact two-candidate matrix and request-25 residual | `python3 -m unittest tests.test_evaluation.NumericExperimentTests` |
| Owning regressions | lifecycle, forecast, replay, output remain coherent | `python3 -m unittest tests.test_events tests.test_forecast tests.test_planning tests.test_output` |
| Real bounded run | complete EXP-NUM report | `python3 code/evaluation/main.py --experiment EXP-NUM` |
| Broader gate | final D bytes | `python3 -m unittest tests.test_evaluation tests.test_pipeline` then `python3 -m compileall -q code tests` then `git diff --check` |

## WP-09D Stops And Handoff

- Stop if a direction is unknown at a conversion site; do not infer it from
  the numeric sign.
- Stop if changing exact mode alters any accepted upstream fixture.
- Do not add currency-specific rounding, alternate rates, inverse/chained FX,
  or renderer policies.
- Next: guided D implementation, then immediate fresh independent acceptance.
  Accepted D bytes unblock E.

---

# WP-09E — Run EXP-CAP And EXP-CHANGE With Explicit Planning Policy

Status: **READY AFTER WP-09D ACCEPTANCE**

```yaml
agent_tier: strong
reasoning: medium
review: immediate
budget: 13 tool calls / 40 minutes / medium-high context
```

## Readiness Route

`implementer self-preflight` — bind to accepted planning candidate/replay and
output-validation APIs; confirm D's `DecisionPolicy` propagation and no dirty
overlap.

## Outcome

Represent and compare exactly the two authorized installment-cap filters and
the two authorized spending-change scopes without changing action syntax,
candidate ranking, or baseline capacity.

## Required Work

1. Add fail-first `PlanningPolicyTests` and matching output-validator policy
   tests before changing signatures.
2. Add a `PlanningPolicy` with exactly:
   - cap: payment count (default) or elapsed calendar-month endpoint;
   - change scope: every future occurrence in the family (default) or only the
     next eligible future occurrence.
3. For elapsed-cap mode, accept only when
   `last_payment_date <= add_calendar_months(first_payment_date, cap)`, clamping
   the day to month end. This replaces only the count filter; positive cap,
   exact option, frequency, total, deadline, horizon, preference, and replay
   gates remain unchanged.
4. For next-occurrence mode, each action affects only the earliest future
   mutable fixed-recurrence movement in its resolved family. It never changes
   settled history, an opening/pending reserve, an explicit committed debit,
   another family, or later occurrences. Series mode preserves current
   behavior.
5. Route one immutable planning policy through candidate construction,
   `plan_request`, replay, output validation, and pipeline. Recompute unchanged
   baseline capacity without either planning dimension.
6. EXP-CAP runs exactly two full 25-sample configurations; highlight requests
   03, 17, 19, and 22 plus the synthetic three-payments-across-two-months
   boundary.
7. EXP-CHANGE runs exactly six scoped replays: series and next-occurrence for
   requests 06, 11, and 21. Expected public actions remain respectively
   `stop:event_476`, `reduce_to:event_989:665950`, and
   `stop:event_1815|reduce_to:event_1816:23.50`.
8. Require protected, floor, pending, duplicate-family, first-versus-later
   breach, and baseline-capacity-unchanged fixtures. Do not run a continuous
   reduction search.

## Acceptance Criteria

- **E-AC-01:** count and elapsed modes differ only at the cap filter and both
  preserve exact supplied-option/deadline/horizon/safety gates.
- **E-AC-02:** series and next-occurrence modes affect exactly their declared
  movement sets; pending/explicit commitments remain intact.
- **E-AC-03:** planner, replay, and independent output validator receive the
  identical planning policy explicitly.
- **E-AC-04:** optional-change policy never alters baseline safe amount or
  baseline earliest date.
- **E-AC-05:** EXP-CAP reports exactly two configurations × 25 rows and
  EXP-CHANGE exactly six scoped replays; E performs no promotion.

## WP-09E Verification

| Evidence | Scenario and oracle | Command |
|---|---|---|
| Fail-first/targeted | month clamp/count boundary, scope movement sets, pending/protected/floor/duplicate cases | `python3 -m unittest tests.test_planning.PlanningPolicyTests tests.test_output.PlanningPolicyValidationTests` |
| Evaluation | exact candidate/replay counts and fixed discriminator IDs | `python3 -m unittest tests.test_evaluation.PlanningExperimentTests` |
| Owning regressions | all planning/output behavior under defaults | `python3 -m unittest tests.test_planning tests.test_output` |
| Real bounded runs | complete EXP-CAP and EXP-CHANGE reports | `python3 code/evaluation/main.py --experiment EXP-CAP` then `python3 code/evaluation/main.py --experiment EXP-CHANGE` |
| Broader gate | final E bytes | `python3 -m unittest tests.test_evaluation tests.test_pipeline tests.test_forecast tests.test_events` then `git diff --check` |

## WP-09E Stops And Handoff

- Stop if accepted WP-08 validation cannot receive the policy used to produce
  the row; validator/predictor drift is forbidden.
- Stop if next-occurrence identity is ambiguous; do not choose by incidental
  tuple order beyond the accepted date/stable-ID ordering.
- Do not change ranking, action floors, action strings, option amounts, or add
  a third policy value.
- Next: guided E implementation, then immediate fresh independent acceptance.
  Accepted E bytes unblock F.

---

# WP-09F — Select And Freeze One Global Policy

Status: **READY AFTER WP-09C, WP-09D, AND WP-09E ACCEPTANCE**

```yaml
agent_tier: standard
reasoning: medium
review: immediate
budget: 10 tool calls / 35 minutes / medium context
```

## Readiness Route

`implementer self-preflight` — confirm accepted C/D/E reports are reproducible
on current bytes and all candidate/config IDs match their tested semantics.

## Outcome

Apply the recorded stop rules in order, freeze one global product policy, and
write deterministic selection and 25-row sample evidence artifacts that agree
with the runtime constant.

## Required Work

1. Add fail-first `PolicySelectionTests` for dominance, tie, tradeoff, fixture
   failure, unexplained optimism, and ordered carry-forward behavior.
2. Select EXP-RV, DATE, NUM, CAP, then CHANGE using the package selection
   contract. Never select on a metric outside the experiment's declared
   discriminators.
3. Update only `SELECTED_DECISION_POLICY` after selection. Keep
   `DEFAULT_DECISION_POLICY` as the documented conservative baseline for audit
   and regression comparison.
4. Generate deterministic `policy_selection.json` containing schema version,
   participant dataset fingerprint, upstream contract IDs, every candidate
   policy ID and metrics, fixture disposition, optimism disposition, selected
   value, and keep/promote reason. Omit wall-clock time and raw carriers.
5. Generate deterministic `sample_report.json` for the final selected policy,
   with exactly 25 comparison/trace rows and all required aggregate metrics.
6. Add a drift test that parses `policy_selection.json` and requires its
   selected canonical policy to equal `SELECTED_DECISION_POLICY`; product code
   must not read the JSON at runtime.
7. Run the complete deterministic safety/contract suite. Re-run all 25 samples
   after EXP-CHANGE even though that experiment used six scoped replays.
8. Update evaluation and project-map navigation/commands. Do not update
   `master-plan.md` merely to record this design task or implementation status.

## Acceptance Criteria

- **F-AC-01:** each experiment selects exactly one global value by the recorded
  rule; ties/tradeoffs preserve the incumbent and every decision is explained.
- **F-AC-02:** both artifacts are deterministic, complete, source-safe, and
  identify the exact dataset and accepted upstream contracts.
- **F-AC-03:** all 25 sample rows are reported and every mismatch maps to one
  allowed category/reason.
- **F-AC-04:** contract and deterministic safety-fixture failure counts are
  zero; a promotion has reproducible improvement and no unexplained new
  optimism.
- **F-AC-05:** selected JSON, sample report, evaluation default, and product
  runtime constant carry the identical canonical configuration.
- **F-AC-06:** production policy has no request/user-specific exception and is
  ready for WP-10's evaluation batch composition.

## WP-09F Verification

| Evidence | Scenario and oracle | Command |
|---|---|---|
| Fail-first/targeted | selection stop rules, ordered carry-forward, artifact/config drift | `python3 -m unittest tests.test_evaluation.PolicySelectionTests` |
| Owning suite | all evaluator/oracle/experiment behavior | `python3 -m unittest tests.test_evaluation` |
| Generate evidence | final selected 25-row report and selection record | `python3 code/evaluation/main.py --experiment all --output code/evaluation/sample_report.json --selection-output code/evaluation/policy_selection.json` |
| Real public boundary | default uses frozen selection; 25 rows, zero contract/safety/unmapped failures | `python3 code/evaluation/main.py` |
| Aggregate safety owner | final F implementer runs full offline suite after artifacts are generated | `python3 -m unittest discover -s tests -p 'test_*.py'` |
| Compile/navigation/hygiene | imports, links, and patch cleanliness | `python3 -m compileall -q code tests` then `python3 -m unittest tests.test_agent_foundation_contract` then `git diff --check` |

## WP-09F Stops And Handoff

- Stop if an accepted experiment report cannot be reproduced on current bytes
  or the participant dataset fingerprint changed.
- Stop rather than promote when metrics trade off, optimism is unexplained, a
  fixture fails, or a candidate requires new scope.
- A public mismatch is not itself a release blocker when it is mapped and all
  contract/safety gates pass.
- Next: guided F implementation, followed immediately by a fresh independent
  acceptance review. Accepted F bytes and frozen config unblock WP-10.

## Finite-Risk Coverage Contract

Keep these row IDs stable across implementation and correction reviews.

| Invariant | Material dimensions/cases | Decisive oracle/boundary | Implementation evidence | Independent review probe | Gate owner |
|---|---|---|---|---|---|
| FR-09-01 label isolation | eight input columns; seven solved columns; all 25 IDs; poisoned labels | identical `PredictionTrace.output_row` before/after solved-column mutation | B sample isolation tests | alter each solved field independently; prediction bytes remain equal | B implementer/reviewer |
| FR-09-02 complete comparison | status; method; money; date empty/both; plan raw/semantic; change raw/semantic; explanation consistency | 25 ordered comparison rows and exact aggregate denominators | B metric/cause tables | remove/reorder one oracle row or one mismatch reason; run rejects | B implementer/reviewer |
| FR-09-03 forecast matrices | RV 2×3×2=12; DATE 2×2=4; fixed non-tested dimensions | unique canonical policy IDs and 25 rows per configuration | C exact-matrix tests and owner fixtures | duplicate/omit one combination or vary a held dimension; reject | C implementer/reviewer |
| FR-09-04 numeric matrix | exact/output-only; directional-cent debit-up/credit-down; home amount; request 25 exact FX | two policy IDs, owner conversions, full 25-row residuals | D numeric owner/evaluation tests | fractional debit and credit under both policies; exact mode unchanged | D implementer/reviewer |
| FR-09-05 planning matrices | count/elapsed cap; series/next occurrence; six scoped change replays; protected/floor/pending/duplicate | exact option/action eligibility plus fresh policy-aware replay | E planning/output/evaluation tests | month-end clamp and later-occurrence breach distinguish variants | E implementer/reviewer |
| FR-09-06 conservative promotion | improve; tie; tradeoff; fixture fail; explained/unexplained optimism; five-step carry-forward | deterministic selection record and runtime constant equality | F selection/drift tests | worsen one metric while improving another; incumbent must remain | F implementer/final reviewer |
| FR-09-07 final evidence | 25 rows; zero contract/safety failures; every mismatch categorized; deterministic artifacts | real `dataset/` evaluation command plus byte comparison on repeat | F generation/default/full-suite gates | rerun twice and compare artifact bytes and selected policy IDs | F implementer/final reviewer |

## Package Exit Criteria

WP-09 is complete only when A through F receive fresh independent `ACCEPT` in
order; every FR-09 row passes on final bytes; the final default command reports
all 25 samples with zero contract/safety/unmapped failures; every public
mismatch has a stable cause; the two evidence artifacts match the frozen
runtime policy; the complete offline unit suite, compile, navigation, and
`git diff --check` gates pass; and no WP-10 output, usage, or packaging work has
entered scope.
