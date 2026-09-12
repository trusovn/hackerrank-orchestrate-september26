# WP-05 — Recurrence, Variable Spending, And Baseline Ledger

Status: **ACCEPTED** — final verdict ACCEPT (2026-09-12), see Review Record

Authority: [`master-plan.md`](master-plan.md), WP-05

Depends on: accepted WP-02 and accepted WP-04

Readiness route: standalone guided preflight — bind this task to the accepted
WP-04 normalization and future-date FX interface

```yaml
agent_tier: strong
reasoning: high
review: immediate
budget: 24 tool calls / 70 minutes / medium context
```

## Outcome

Implement one deterministic `buy_or_wait.forecast` boundary that consumes a
validated request case, its accepted evidence resolution, and the accepted
WP-04 normalization, then produces a reproducible baseline ledger from the
request date through the selected day-89/day-90 endpoint. The default policy
must use strict supported recurrence, I0 income continuation, V0 variable
spending, an inclusive day-90 horizon, debit-before-credit ordering, exact
source ownership, and a compact replayable trace.

This task does not compute `amount_safe_to_pay`, search for a full-payment
date, insert a proposed payment, enumerate spending changes, or choose a plan.
It enables WP-06 to calculate those results by independently replaying one
auditable baseline.

## Direction Trace

- Direction contribution: forecast recurring income, recurring expenses,
  confirmed future effects, pending debit reserves, and essential variable
  spending conservatively for the fixed safety horizon.
- User-observable effect: no final recommendation yet; enables the first
  balance trajectory that can prove whether a later payment plan protects the
  user's `minimum_balance_to_keep` at every checkpoint.
- Why now: [`master-plan.md`](master-plan.md) places mandatory WP-05 after
  lifecycle/FX normalization and before WP-06 capacity and safety replay.
- Direction decisions used: [`../AGENTS.md`](../AGENTS.md),
  [`../problem_statement.md`](../problem_statement.md),
  [`initial-analysis/07-evidence-decision-pack.md`](initial-analysis/07-evidence-decision-pack.md),
  [`initial-analysis/08-financial-semantics-decisions.md`](initial-analysis/08-financial-semantics-decisions.md)
  (`FIN-002`–`FIN-005` and `FIN-008`), and
  [`master-plan.md`](master-plan.md), sections 5–9 and WP-05.
- New direction decisions required: None.

## Authority And Scope

| Item | Contract |
|---|---|
| Product authority | [`../problem_statement.md`](../problem_statement.md) and [`../AGENTS.md`](../AGENTS.md) |
| Implementation authority | [`master-plan.md`](master-plan.md), WP-05, and the selected recurrence/date policies in [`initial-analysis/08-financial-semantics-decisions.md`](initial-analysis/08-financial-semantics-decisions.md) |
| Allowed product changes | New `code/buy_or_wait/forecast.py` only |
| Allowed evidence changes | New `tests/test_forecast.py`; [`project-map.md`](project-map.md) only after the module and command exist |
| Read-only upstream context | Accepted `domain.py`, `repository.py`, `evidence.py`, `events.py`, their owning tests, and the final WP-04 review record |
| Input boundary | One `RequestCase`, its exact `EvidenceResolution`, and the `EventNormalization` produced from those same inputs |
| Out of scope | Editing WP-04 files; parsing raw messages/images; lifecycle or FX reimplementation; payment insertion; safe amount or earliest-date search; spending-change application; candidate construction/ranking; explanations; CSV output; provider/model work; policy calibration against solved outputs |
| External requirements | Standard library only; offline, deterministic, no credentials, no network, and no clock reads |
| Parallel work | WP-04 is accepted. WP-05 implementation is complete; no further WP-05 implementation may overlap `events.py`/`test_events.py` or another owner of `forecast.py`/`test_forecast.py`. |

## Dependency And Timing Gate

Run this gate immediately before WP-05 implementation, against the accepted
WP-04 bytes rather than the in-progress draft:

1. Run `python3 -m unittest tests.test_repository tests.test_evidence
   tests.test_events`.
2. Confirm the public normalizer still accepts the exact `RequestCase` and
   `EvidenceResolution` for one case and returns immutable historical cash,
   opening reserves, future dated cash effects, source decisions, and a
   monotonic downstream-blocking flag.
3. Confirm every recurrence-eligible historical record preserves its resolved
   source amount and source currency as well as its exact home amount. Source
   IDs alone are insufficient because an image fact may have supplied an
   originally blank event amount.
4. Confirm WP-04 exposes one public pure exact-FX operation (or an equivalent
   immutable converter owned by `events.py`) that can convert a synthesized
   future source amount using exactly
   `(settlement_date, source_currency, home_currency)`. It must retain WP-04's
   no-inversion, no-nearest-date, no-chaining, and no-rounding behavior.
5. Confirm the normalized records expose the category, event type, direction,
   flexibility, minimum allowed amount, settlement date, source event IDs, and
   source fact IDs needed for series identity and trace ownership.
6. Confirm no active work overlaps `forecast.py` or `test_forecast.py`.

The source-money and future-date converter checks are decisive. A foreign
recurrence must not reuse its historical home-currency amount because the
future settlement date may require a different supplied rate. If accepted
WP-04 lacks either capability, stop and route a narrow WP-04 interface
correction plus focused regression and fresh independent acceptance. Do not
join back to raw events to redo amount resolution, copy a private FX helper,
reuse a historical rate, or implement FX in `forecast.py`.

If accepted WP-04 changes only exact type or member names, bind this brief to
those names during preflight without changing the semantics below. WP-03 is
optional and is not a dependency.

## Architecture

### Public Boundary

Add one flat pure module with this public operation:

```python
build_baseline_forecast(
    case: RequestCase,
    evidence: EvidenceResolution,
    normalization: EventNormalization,
    policy: ForecastPolicy = DEFAULT_FORECAST_POLICY,
) -> BaselineForecast
```

Use the final accepted WP-04 type names exactly. Do not use loose dictionaries,
duck typing, reflection, or compatibility shims. Validate that all three
inputs have the same request and source ownership before doing arithmetic.
The function reads no files, environment, clock, provider, or global cache and
writes nothing.

Keep immutable, feature-owned records in `forecast.py`. Exact class names may
follow local style, but the public result must expose these semantics:

```text
BaselineForecast
  request_id
  request_date
  horizon_end
  opening_cash
  minimum_balance
  opening_reserved
  series_traces
  projected_occurrences
  checkpoints
  diagnostics
  blocks_downstream
  minimum_headroom: Decimal | None
```

`minimum_headroom` is the minimum `spendable_balance - minimum_balance` over
the materialized opening and dated checkpoints. It is `None`, not zero, when a
material unknown debit or required FX conversion prevents certification.
Computing payment capacity from this value belongs to WP-06.

Each projected occurrence carries a stable family ID, date, direction,
source amount/currency when applicable, exact home amount, origin
(`explicit`, `fixed_recurrence`, or `variable_envelope`), and safe source
event/fact IDs. Each series trace lists its ordered observations, selected or
rejected cadence, selected amount rule, applied evidence fact IDs, generated
dates, replacement decisions, and one stable reason code. Do not include raw
descriptions, message text, image content, or evidence notes in the result.

Use the latest compatible historical occurrence, ordered by settlement date
then event ID, as the series anchor. Its public family ID is
`series:<anchor_event_id>`; later spending-change work can therefore target the
same validated series without inventing another identity system.

### Finite Policy Surface

`ForecastPolicy` is a frozen record containing only the following closed
choices. Do not build a generic rule engine or accept arbitrary thresholds.

| Dimension | Closed values | Default |
|---|---|---|
| Recurrence timing | `STRICT`; `TOLERANT_2_DAY` | `STRICT` |
| Income continuation | `I0_EXPLICIT_ONGOING`; `I1_STRICT_RECENT_HISTORY` | `I0_EXPLICIT_ONGOING` |
| Variable spending | `V0_MAX_COMPLETE_MONTH`; `V1_MAX_CADENCED_OCCURRENCE`; `V2_MEAN_COMPLETE_MONTH` | `V0_MAX_COMPLETE_MONTH` |
| Horizon endpoint | `DAY_89_INCLUSIVE`; `DAY_90_INCLUSIVE` | `DAY_90_INCLUSIVE` |
| Unknown same-day order | `DEBIT_CREDIT_PAYMENT`; `CREDIT_DEBIT_PAYMENT` | `DEBIT_CREDIT_PAYMENT` |

The first three dimensions form exactly the maximum 12 `EXP-RV`
configurations. The last two form exactly the four `EXP-DATE`
configurations. WP-05 implements and tests these finite switches; WP-09 owns
the full sample sweep and any promotion away from the defaults.

### Deterministic Build Phases

Implement the phases below in order. A later phase consumes the immutable
result of the previous phase; it must not mutate upstream records.

#### 1. Validate The Boundary

- Require matching request/user IDs and accepted public input types.
- Reject duplicate event IDs, fact IDs, normalized record IDs, or family IDs.
- Copy any upstream `blocks_downstream=True`; this flag is monotonic and can
  never be cleared.
- Build read-only indexes by source event ID and fact ID. Every referenced ID
  must belong to this case.
- Reject impossible monetary inputs or an upstream active cash role with no
  source owner. Use a feature-owned `ForecastBuildError(ValueError)` with a
  stable reason code and safe source IDs; never return a partial result for an
  internally inconsistent contract.

#### 2. Assign Every Historical Cash Source Once

Each normalized historical cash record must receive exactly one forecast
disposition:

1. fixed recurrence observation;
2. variable-policy observation;
3. explicit non-recurring history; or
4. unusable/unresolved history.

Never infer recurrence from refunds, reimbursements, transfers, one-time
arrears or adjustments, investment purchases/valuations/sales, failed or
cancelled rows, or non-cash values. Historical rows remain observations only;
none is replayed into opening cash.

Fixed-series candidate identity is the exact tuple of user, event type,
direction, category, source currency, flexibility, minimum allowed amount,
and a strictly canonicalized description. Canonicalization is limited to
Unicode `casefold`, replacing non-alphanumeric runs with one space, collapsing
whitespace, and trimming. It must not stem words, drop tokens, use fuzzy
matching, translate, or merge descriptions by category alone. Structured
field disagreement always separates a series.

#### 3. Detect Supported Cadence And Amount

Sort observations by settlement date then event ID. A history-inferred series
needs at least three settled observations in a matching suffix, which proves
two consecutive intervals.

- **Monthly:** consecutive calendar months. Prefer an all-month-end family
  when every observation is that month's final day. Otherwise find one nominal
  day `n` for which each observed day is
  `min(n, last_day_of_observed_month)`. Future dates use the same rule.
- **Weekly/fortnightly:** every consecutive interval is exactly 7 or exactly
  14 days.
- **Strict rejection:** 21/28-day, arbitrary, mixed, duplicate-date, skipped-
  month, or fewer-than-three sequences do not establish cadence.
- **Tolerant alternative:** each observed date may be at most two days from
  the canonical monthly/7-day/14-day date. Project a debit on the earliest
  plausible date and a credit on the latest plausible date. Never search a
  wider or arbitrary interval.

Use the latest stable source amount: an accepted recurring amendment wins from
its effective boundary; otherwise require an equal-amount suffix of at least
two observations. A varying debit without such a suffix is eligible for the
selected variable policy, not a fixed series. A varying credit is not promoted
without the selected income policy and one grounded conservative amount.
When compatible grounded amounts still conflict, use the higher debit or lower
credit and record the conservative reason.

Generate inferred occurrences strictly after the opening boundary and no
later than `horizon_end`. A missed expected credit date on or before the
request date, without explicit confirmation, makes subsequent history-only
income stale. Do not replay the missed credit. A missed debit does not prove
cancellation; begin with the first supported occurrence after the request
date, without charging historical missed occurrences as arrears.

#### 4. Apply Accepted Recurrence Facts

Consume only validated `EvidenceFact` fields and IDs; never parse `notes` or
carrier content. Map a fact's accepted target anchor to exactly one series.
Zero or multiple matches produce a safe diagnostic; a required debit fact
also blocks downstream certification.

Apply facts before projecting final occurrences:

- `RECURRING_AMOUNT_AMENDMENT` and `RECURRING_EXPENSE_AMENDMENT` change the
  uniquely targeted series from the explicit effective date, or from the next
  future occurrence when the accepted fact has no date. Do not change history.
- `NEXT_CYCLE_AMOUNT_AMENDMENT` changes the first future occurrence. Do not
  assume a favorable reversion afterward: until a grounded reversion exists,
  later debits use the higher grounded value and later credits the lower.
- `SETTLEMENT_DATE_REPLACEMENT` moves only the first compatible future
  occurrence to the supplied replacement date and suppresses its old date.
- `RECURRENCE_STOP` removes future occurrences from the carrier/effective
  boundary. Because current carriers are no later than the request, a stop
  with no explicit date removes all occurrences after opening.
- `RECURRENCE_RESUME` restarts the unique supported series at its effective
  boundary with its grounded amount. It cannot invent a cadence.
- `RECURRENCE_CONFIRMATION` confirms only the next compatible occurrence
  unless the accepted fact contract explicitly carries a longer duration.
- `RECURRING_EXPENSE_NOTICE` with no bounded amount creates a blocking
  diagnostic and no zero-valued occurrence.
- One-time, unavailable, pending, unrealized, transfer, image-amount, and
  already-normalized future-cash facts do not independently establish a
  recurring series.

Fact order is accepted evidence order. Two incompatible surviving facts for
the same family/cycle are an upstream contract error; do not choose from raw
text or silently let the last one win.

#### 5. Merge Explicit Future Effects Without Double Counting

Start from WP-04's future dated effects and opening reserves. They are
authoritative occurrences, not recurrence evidence by themselves.

- A supplied future occurrence replaces one inferred fixed-series slot only
  when its accepted source target maps to that unique series and the occurrence
  belongs to the same predicted cycle. Retain the supplied date and amount;
  remove the inferred slot; record both source ownership decisions.
- A date-replacement fact suppresses the superseded slot before this merge.
- Arrears, outstanding balances, refunds, reimbursements, and separately
  supplied one-time effects remain additive.
- A pending reserve is additive unless accepted evidence identifies it as the
  exact occurrence of that unique series. Similar category, description, or
  amount is not enough to absorb it.
- No source event or fact may own two active projected effects.

#### 6. Project Variable Spending

Variable-policy input is residual settled debit history not already owned by a
fixed series and not classified as one-time/unusual/non-cash. Group it by the
same user, category, and home currency. Do not combine income with spending or
combine an explicit fixed obligation with its category envelope.

For V0 and V2, a comparable category-month is a calendar month strictly before
the request month that contains at least one eligible numeric observation and
no known unresolved amount for that category. Absence of a category row is not
invented as a zero month. Use the latest three comparable months, with at least
two required.

- **V0:** the maximum exact monthly category total.
- **V2:** the arithmetic mean of those monthly totals, rounded upward to
  `Decimal("0.01")`.
- **V1:** for each residual variable series with a supported cadence, use its
  maximum observed source amount and project that cadence. It is used instead
  of, never in addition to, a V0/V2 envelope for the same sources.

For V0/V2, reserve the full current-month envelope at opening even when the
request is late in the month. Reserve another full envelope at the first day
of every later calendar-month segment that intersects the horizon. Model each
as one projected debit/reserve checkpoint with its category sources and policy
reason; do not also project its owned historical series. A known explicit
future obligation remains additive unless it uniquely replaces a supported
fixed-series slot.

If positive residual variable history has fewer than two usable category
months under V0/V2, or a required numeric observation makes a candidate month
incomplete, emit `variable_history_unbounded`, set `blocks_downstream=True`,
and do not fabricate a category total. Exact future obligations still remain
in the trace.

#### 7. Apply Income Policy And Future FX

I0 includes every confirmed explicit future credit once and continues only a
series explicitly established as ongoing by accepted recurring evidence, with
grounded amount and cadence. It does not extend a next-only confirmation.
I1 additionally continues a strict, recent historical salary series that
passes the cadence, amount, staleness, stop, and amendment rules. Neither
policy recurs windfalls, refunds, reimbursements, arrears, commission,
pending/unwithdrawable income, investment proceeds, or a first salary beyond
its accepted duration.

For each synthesized foreign-currency fixed occurrence, call the accepted
WP-04 exact converter with that occurrence's source amount, source currency,
and synthesized settlement date. Never reuse a historical home amount or rate.

- Missing exact rate for a debit: omit the unknown numeric occurrence, emit a
  blocking diagnostic, and leave `minimum_headroom=None`.
- Missing exact rate for a credit: omit the credit and emit a non-blocking
  conservative diagnostic.
- Conflicting/invalid rates or another converter contract violation: raise
  `ForecastBuildError` atomically; do not return partial output.

Variable envelopes are already home-currency aggregates of exact historical
WP-04 amounts; do not convert them a second time.

#### 8. Build The Baseline Ledger And Trace

Let `D = request_date` and let `T` be D+90 by default or D+89 for the alternate
policy. Start `cash_balance` at the supplied current available balance and
`reserved_balance` at zero. `spendable_balance = cash_balance -
reserved_balance`; `headroom = spendable_balance - minimum_balance`.

1. Emit an opening checkpoint at D.
2. Apply every opening debit reserve once in stable record-ID order. Increase
   `reserved_balance`; do not reduce `cash_balance` yet. Check headroom after
   each reserve.
3. Materialize dated effects and projected occurrences on D through T
   inclusive. Under the default, process debits before credits, sort same-kind
   items by stable ID, and reserve the payment phase after all settlements.
   The alternate EXP-DATE order reverses credit/debit only; payment remains
   last.
4. When a pending reserve settles inside the horizon, reduce `cash_balance` by
   its amount and release the same amount from `reserved_balance` in one
   checkpoint. The spendable balance therefore does not fall a second time.
   A reserve settling after T remains unavailable through T.
5. Apply ordinary debits and credits as exact signed cash deltas. Check and
   record balance, reserved amount, spendable balance, and headroom after every
   debit, reserve, reserve settlement, credit, and future variable reserve.

The result may contain a negative baseline headroom; WP-05 reports it exactly
and does not repair it. WP-06 must not ignore an early breach when testing a
later payment. Ordering and checkpoints must be reconstructible from the
public result without rerunning recurrence discovery.

## Required Work

1. Complete the dependency gate after WP-04 is accepted. Route any missing
   source-money or future-date FX seam back to WP-04 before editing WP-05.
2. Add fail-first `tests/test_forecast.py` fixtures with small immutable
   builders. Record the initial missing-module/behavior failure.
3. Add the frozen finite policy enums/record, trace records, diagnostics,
   `ForecastBuildError`, and `build_baseline_forecast` in
   `code/buy_or_wait/forecast.py`.
4. Implement strict/tolerant cadence detection, stable amount selection,
   evidence amendments/stops/resumes, income I0/I1, and exact supplied-slot
   replacement in the phase order above.
5. Implement V0/V1/V2 with exclusive source ownership and conservative
   incomplete-history behavior.
6. Implement exact future-date FX through WP-04 and the opening/day-89/day-90
   ledger with deterministic same-day ordering and reserve settlement.
7. Add component tests that load, resolve, normalize, and forecast selected
   participant-facing sample cases through public boundaries. Include facts
   exercising salary amendment, next-only pay, date replacement, ended income,
   amount-less childcare, rent amendment, and foreign salary. Assert trace
   facts and invariants from source data only; never import solved output
   fields or encode request-specific product branches.
8. Update [`project-map.md`](project-map.md) with the new owner, public entry
   point, and `tests.test_forecast` command only after implementation passes.
9. Inspect the final diff for edits outside `forecast.py`, `test_forecast.py`,
   and the exact project-map rows, then hand the completed bytes to a fresh
   independent acceptance reviewer.

## Acceptance Criteria

- **AC-01 — Exclusive source ownership:** every normalized historical cash
  source has exactly one fixed, variable, non-recurring, or unresolved
  forecast disposition. Every explicit future effect and reserve appears once;
  an explicit occurrence replaces only its matching inferred slot.
- **AC-02 — Supported recurrence only:** the exact strict monthly/month-end,
  7-day, and 14-day rules require at least three settled observations. Fewer
  observations, unsupported intervals, stale credits, ambiguous identities,
  one-time credits, refunds, reimbursements, arrears, investments, and
  unrealized values do not recur.
- **AC-03 — Evidence lifecycle:** recurring amendments, next-only conservative
  continuation, one-occurrence date replacement, stop, resume, confirmation,
  and unbounded recurring-debit notice produce the specified occurrences,
  suppressions, or blocking diagnostics without altering history.
- **AC-04 — Conservative variable spending:** V0 uses the maximum of the latest
  three usable complete category-months with at least two, reserves the full
  current-month envelope at opening and later envelopes at month boundaries,
  and never combines an envelope with its owned series. V1/V2 are mutually
  exclusive alternatives with the specified exact calculations.
- **AC-05 — Income and FX safety:** I0 and I1 differ only at the documented
  continuation boundary. No unsupported credit appears. Every foreign
  inferred occurrence uses WP-04's exact directed rate for its own date;
  missing debit FX blocks, while missing credit FX excludes that credit.
- **AC-06 — Exact ledger boundary:** opening and every checkpoint from D
  through selected D+89/D+90 inclusive are materialized in deterministic
  order. The default is debit, credit, then later payment; day 90 is included.
  A pending reserve reduces spendable cash once and settlement does not create
  a second reduction.
- **AC-07 — Conservative failure:** upstream blocking state, an unbounded
  required debit, incomplete material variable history, or missing required
  debit FX remains visible and makes `minimum_headroom=None`. Internal contract
  errors fail atomically with safe IDs and a stable reason code.
- **AC-08 — Replayable boundary:** the public immutable result carries enough
  dated deltas, reserve changes, balances, source IDs, reasons, family anchors,
  and ordering information for WP-06 to replay safety without parsing raw
  evidence or rediscovering recurrence.
- **AC-09 — Scope preservation:** the module is standard-library-only and
  deterministic, reads no files or raw carriers, calls no provider, writes no
  output, makes no payment/candidate/ranking decision, and does not edit or
  duplicate WP-04 behavior.

### Finite-Risk Coverage Contract

| Invariant | Material dimensions/cases | Decisive oracle/boundary | Implementation evidence | Independent review probe | Gate owner |
|---|---|---|---|---|---|
| Only supported series recur | exact monthly, month-end with leap year, year boundary, exact 7/14 day, tolerant ±2-day alternative, fewer than 3, skipped month, 21/28-day, duplicate date, structured-identity mismatch | Public series trace and exact projected dates | Table-driven cadence tests that reject unsupported cases and show the fail-first behavior | Perturb one date/structured identity while preserving descriptions and confirm strict projection disappears | Implementer targeted; fresh reviewer adversarial |
| Evidence changes only the intended future series/cycle | recurring amount, expense amendment, next-only, date replacement, stop, resume, next confirmation, unknown debit notice, zero/multiple target | Occurrence list plus fact/source decisions; history unchanged | One small fixture per fact transition, including first affected and next real occurrence | Retarget the same fact to an ambiguous anchor and confirm no multi-series amendment occurs | Implementer targeted; fresh reviewer adversarial |
| One source has at most one forecast role | fixed, V0/V2 envelope, V1 series, explicit future replacement, additive arrears/refund/reserve, excluded one-time/non-cash | Source ownership index covers every normalized source once and active occurrence owners are unique | Conservation assertion plus mixed fixed/variable/explicit fixture | Add an explicit pending obligation with matching category but no exact target; confirm it remains additive without duplicating an inferred slot | Implementer targeted; fresh reviewer mutation |
| Variable spending is conservative and finite | 2/3 usable months, maximum, mean-up, current partial month, next month, insufficient history, missing amount, V1 alternative | Exact envelope amounts/dates and blocking diagnostic | Decimal fixtures spanning month/year boundaries; no zero-filled missing month | Remove one required numeric observation from the maximum month and confirm the baseline blocks rather than shrinking | Implementer targeted; fresh reviewer adversarial |
| Income never appears optimistically | I0 explicit ongoing, I1 recent history, next-only confirmation, missed expected credit, stop, one-time/refund/reimbursement/arrears/commission | Exact credit occurrence dates/amounts and exclusion reasons | Focused income-policy matrix | Remove ongoing evidence while leaving salary-like history; I0 must lose future credits while I1 changes only if strict recency still passes | Implementer targeted; fresh reviewer differential |
| Synthesized FX never reuses history | home currency, exact future direct pair, missing debit pair, missing credit pair, reverse-only/prior-only, conflict/invalid | WP-04 converter call outcome, exact occurrence home amount, block/omit/error reason | Stub accepted converter or use synthetic rates; assert date-specific exact products | Change only the future rate date while retaining historical rate and confirm no historical conversion is reused | Implementer targeted; fresh reviewer adversarial |
| Ledger checks the complete boundary exactly once | opening, D event, day 89, day 90, debit/credit same day, stable tie, reserve before/at/after settlement, reserve beyond T, negative baseline | Public ordered checkpoints, balances, reserved amounts, spendable amounts, and minimum headroom | Arithmetic table tests for both endpoint and both same-day policies | Place the minimum on day 90 and flip only endpoint policy; then settle a reserve and verify spendable cash is unchanged at settlement | Implementer targeted; fresh reviewer arithmetic |
| Blocking is monotonic and atomic | upstream block, unbounded debit, incomplete variable month, missing debit FX, missing credit FX, invalid input | `blocks_downstream`, `minimum_headroom`, diagnostics, or raised error with no partial return | Focused failure table | Start with upstream block true on an otherwise valid empty forecast; confirm later positive credits cannot clear it | Implementer targeted; fresh reviewer boundary |

## Verification

Use `unittest` and exact `Decimal`/`date` fixtures. Unit tests construct public
records directly; component tests may read `dataset/` only through
`DatasetRepository`. Expected recurrence dates, deltas, balances, and reason
codes must be independently written constants, not values generated by the
implementation under test or copied from solved sample output columns.

| Evidence | Scenario and oracle | Command |
|---|---|---|
| Dependency | Accepted repository/evidence/events interfaces pass, including exact normalization source accounting and FX | `python3 -m unittest tests.test_repository tests.test_evidence tests.test_events` |
| Fail-first | New tests fail because `buy_or_wait.forecast` or the required behavior is absent; record the intended failure before production code | `python3 -m unittest tests.test_forecast` |
| Targeted | AC-01–AC-09 and every finite-risk row pass through the public forecast boundary | `python3 -m unittest tests.test_forecast` |
| Owning regression | Accepted repository, evidence, and lifecycle/FX behavior remains green | `python3 -m unittest tests.test_repository tests.test_evidence tests.test_events` |
| Documentation contract | The new module/test command and plan link are navigable after project-map update | `python3 -m unittest tests.test_agent_foundation_contract` |
| Compile | New and owning modules compile without external dependencies | `python3 -m compileall -q code tests` |
| Broader gate | Fresh reviewer runs the full suite on final bytes, then checks patch hygiene | `python3 -m unittest discover -s tests -p 'test_*.py'` then `git diff --check` |

Execution order is dependency gate, fail-first, targeted, owning regression,
documentation contract, and compile. The implementer records the fail-first
reason and exact passing counts. The fresh independent reviewer reruns the
targeted and owning suites, performs distinct finite-risk probes, and owns the
full-suite and patch-hygiene gate on the final bytes.

No live, paid, networked, performance, or cross-platform check is needed.
Do not run the full EXP-RV/EXP-DATE sample calibration in this task; WP-09 owns
that broader evaluation. Passing WP-05 tests proves a deterministic baseline,
not safe payment capacity or final output correctness.

Exit criteria: AC-01–AC-09 pass; every finite-risk row has a recorded result;
no focused test is skipped; accepted upstream suites remain green; the default
policy values are explicit; and the final diff contains no edit to WP-04,
planning, output, evaluation, dataset, or solved-sample files.

## Stops And Handoff

- WP-04 received fresh independent `ACCEPT` and the dependency gate passed on
  those exact bytes before implementation.
- Stop and route a narrow WP-04 correction if canonical resolved source money
  or an exact synthesized-date FX operation is absent. Do not work around that
  seam in WP-05.
- Stop on red upstream tests, unknown public shapes, or dirty overlap in
  `forecast.py`/`test_forecast.py`; identify the current owner before editing.
- Stop on a recurrence fact that maps to zero/multiple series, incompatible
  facts for the same cycle, or a material variable debit with no supported
  bound. Preserve the conservative diagnostic rather than guessing.
- Any payment replay, capacity, spending-change, candidate, ranking, output,
  provider, generic rules engine, shared helper, or new dependency is scope
  expansion and needs its owning task.
- Preserve all pre-existing user and WP-04 work. Treat the metadata budget as
  a checkpoint, not permission to cut verification.
- Next action: run the WP-06 standalone guided preflight against the accepted
  WP-05 boundary.
- Required follow-on: immediately after implementation or correction, hand
  the completed bytes to a fresh independent acceptance reviewer.

## Review Record

- Review date: 2026-09-12
- Profile: guided, fresh independent acceptance review
- Scope: `forecast.py`, `test_forecast.py`, the WP-05 navigation rows in
  `code/buy_or_wait/README.md` and `docs/project-map.md`; the separately owned
  `.gitignore` change was excluded from this review.
- Dependency evidence: `python3 -m unittest tests.test_repository
  tests.test_evidence tests.test_events` — 151 tests OK, 1 skipped.
- Targeted evidence: `python3 -m unittest tests.test_forecast` — 70 tests OK.
- Independent regressions: duplicate source ownership fails closed;
  malformed monetary input raises `ForecastBuildError`; debit traces expose
  generated dates.
- Owning and repository gates: `python3 -m unittest
  tests.test_agent_foundation_contract` — 3 tests OK; `python3 -m compileall
  -q code tests` — OK.
- Broad gate: `python3 -m unittest discover -s tests -p 'test_*.py'` — 253
  tests OK, 1 skipped; `git diff --check HEAD` — OK.
- Prior findings F-01 through F-04 were resolved or, for F-04, explicitly
  excluded as unrelated user-owned work. No open WP-05 findings remain.

Verdict: **ACCEPT** (AC-01–AC-09 satisfied; no open findings). WP-06 may
proceed through its dependency-gated preflight.
