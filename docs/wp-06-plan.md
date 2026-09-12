# WP-06 — Capacity And Independent Safety Replay

Status: **READY FOR SEQUENTIAL IMPLEMENTATION — WP-05 ACCEPTANCE GATED**

Authority: [`master-plan.md`](master-plan.md), WP-06

Depends on: a fresh independent `ACCEPT` for WP-05, built on the final accepted
WP-04 bytes

This work package is split without changing scope. WP-06A establishes the
single replay oracle and exact failure evidence. WP-06B uses the accepted
oracle to compute the two preference-independent capacity fields. The tasks
share `planning.py` and `test_planning.py`, so they must run sequentially and
must not be assigned concurrently.

The split is deliberate: the unsplit work is estimated at 23 tool calls and
combines two different proof obligations. Each part below is small enough for
the stated routing profile and has its own focused acceptance boundary.

## Direction Trace

- Direction contribution: certify candidate schedules over the complete fixed
  horizon, then derive exact baseline safe-today capacity and the first safe
  standalone full-payment date.
- User-observable effect: no recommendation is selected yet; this package
  produces the two baseline capacity values later written to every output row
  and the independent safety verdict used to reject unsafe WP-07 candidates.
- Why now: [`master-plan.md`](master-plan.md) places WP-06 after a replayable
  WP-05 baseline and before candidate enumeration, ranking, and output
  validation.
- Direction decisions used: [`../AGENTS.md`](../AGENTS.md),
  [`../problem_statement.md`](../problem_statement.md),
  [`initial-analysis/08-financial-semantics-decisions.md`](initial-analysis/08-financial-semantics-decisions.md)
  (`FIN-002`, `FIN-009`, `FIN-011`, `FIN-012`, and `FIN-013`), and
  [`master-plan.md`](master-plan.md), sections 5–12 and WP-06.
- New direction decisions required: None.

## Package Boundary

| Item | Contract |
|---|---|
| Product authority | [`../problem_statement.md`](../problem_statement.md) and [`../AGENTS.md`](../AGENTS.md) |
| Implementation authority | [`master-plan.md`](master-plan.md), WP-06, and the selected safety/capacity rules in `initial-analysis/08-financial-semantics-decisions.md` |
| Allowed product changes | New `code/buy_or_wait/planning.py` only |
| Allowed evidence changes | New `tests/test_planning.py`; `code/buy_or_wait/README.md` and [`project-map.md`](project-map.md) only for the exact new owner, symbols, links, and commands after implementation exists |
| Read-only upstream context | Accepted `domain.py`, accepted `forecast.py`, their navigation entries and owning tests, plus the final WP-05 acceptance record |
| Shared input boundary | One `RequestCase`, its accepted immutable `BaselineForecast`, domain `Payment` values, and zero or more domain `SpendingChange` values |
| Out of scope | Editing WP-05 files; recurrence or ledger rediscovery; raw evidence parsing; lifecycle/FX policy changes; candidate generation, method eligibility, deadline filtering, installment matching, spending-change enumeration/ranking, status/method selection, explanation, CSV output, provider/model work, or public-sample calibration |
| External requirements | Standard library only; offline, deterministic, no credentials, no network, no filesystem writes, and no clock reads |
| Parallel work | Earlier implementation is in progress. Planning may land now, but WP-06 implementation must wait for accepted WP-05 and may not overlap another owner of `planning.py` or `test_planning.py`. |

## Dependency And Interface Gate

Run this gate immediately before WP-06A implementation, against accepted—not
in-progress—upstream bytes:

1. Run `python3 -m unittest tests.test_forecast` and record the exact result.
2. Confirm `BaselineForecast` is immutable and exposes `request_id`,
   `request_date`, `horizon_end`, `opening_cash`, `minimum_balance`,
   `blocks_downstream`, `minimum_headroom`, diagnostics, and a deterministic
   ordered sequence from which cash and reserve balances can be recomputed.
3. Confirm each replayable movement exposes, without parsing trace prose:
   date, phase/order, stable ID, exact cash delta, exact reserve delta, origin,
   source event/fact IDs, and—when it is a mutable inferred recurring debit—
   its family anchor, source amount/currency, home amount/currency, and
   occurrence date.
4. Confirm baseline checkpoints expose their expected cash, reserve,
   spendable, and headroom values so empty replay can cross-check the producer
   rather than trusting only `minimum_headroom`.
5. Confirm the accepted forecast states exactly which inferred recurring
   debit movements are changeable. Opening reserves, reserve settlements,
   explicit committed effects, variable envelopes, history, and credits must
   not become changeable merely because their category or amount resembles a
   series.
6. Confirm `events.convert_exact` remains the accepted pure converter for a
   changed foreign source amount on its occurrence date.
7. Confirm no active work overlaps `planning.py` or `test_planning.py`.

The ordered primitive-movement seam is decisive. If accepted WP-05 exposes
only final balances, cached minimum headroom, prose traces, or data that cannot
identify mutable recurring debits, stop and route a narrow WP-05 interface
correction with a focused regression and fresh independent acceptance. Do not
rebuild recurrence from events, scrape trace text, mutate forecast records, or
trust candidate-supplied balance trajectories.

Exact accepted upstream type/member names may replace the semantic names in
this plan during preflight. That binding must not change behavior. WP-03 is not
a dependency.

## Shared Architecture Contract

Keep one flat pure module, `buy_or_wait.planning`. Do not add a planner class,
generic rules engine, compatibility layer, cache, or shared helper module. Use
the accepted WP-05 public records directly and the existing domain `Payment`
and `SpendingChange` records.

The public API after both parts is:

```python
replay_schedule(
    case: RequestCase,
    baseline: BaselineForecast,
    payments: tuple[Payment, ...] = (),
    spending_changes: tuple[SpendingChange, ...] = (),
) -> SafetyReplay

compute_baseline_capacity(
    case: RequestCase,
    baseline: BaselineForecast,
) -> CapacityResult
```

Use the final accepted WP-05 type names exactly. Do not accept dictionaries,
raw events, raw evidence, callbacks, or candidate-computed checkpoints.

Feature-owned frozen result records must expose these semantics:

```text
SafetyReplay
  request_id
  safe: bool
  checkpoints
  minimum_headroom: Decimal | None
  first_failure: ReplayFailure | None
  applied_change_event_ids

ReplayCheckpoint
  checkpoint_index
  date
  phase
  stable_id
  cash_balance
  reserved_balance
  spendable_balance
  minimum_balance
  headroom
  source_ids

ReplayFailure
  reason_code
  date: date | None
  checkpoint_index: int | None
  source_ids

CapacityResult
  request_id
  amount_safe_to_pay
  earliest_date_for_full_payment: date | None
  diagnostics
```

Names may follow local style, but the meanings and immutability may not. A
feature-owned `PlanningError(ValueError)` is for an inconsistent trusted
boundary: mismatched case/forecast, impossible baseline arithmetic, duplicate
primitive IDs, or another state that accepted WP-05 must never produce. It
carries only a stable reason code and safe source IDs and never returns a
partial result.

An ordinary unsafe or ineligible candidate is data, not an exception.
`replay_schedule` returns `safe=False` and one stable `ReplayFailure` for an
uncertified baseline, malformed payment schedule, intrinsically unapplicable
change, out-of-horizon payment, or minimum-balance breach. WP-07 can therefore
reject candidates deterministically without catching programming errors.

The first failure is deterministic:

1. first malformed payment/change in supplied order;
2. first upstream blocking diagnostic in accepted order;
3. first chronological replay checkpoint below the minimum, using accepted
   phase order and stable ID order.

Never include raw descriptions, message/image content, evidence notes, or
payment preferences in a replay or diagnostic.

---

# WP-06A — Implement The Independent Safety Replay Kernel

Status: `ready` — WP-05A dependency/interface gate may now run against the
accepted replay surface

```yaml
agent_tier: strong
reasoning: medium
review: immediate
budget: 13 tool calls / 35 minutes / medium context
```

## Readiness Route

`standalone guided preflight — bind replay to the accepted WP-05 primitive-movement and changeable-series interface`

## Outcome

Implement a pure full-horizon replay that independently recomputes every
balance from accepted baseline movements plus a proposed payment schedule and
prevalidated spending changes, then returns exact checkpoints and the first
safe failure without trusting candidate construction or cached balances.

## Required Work

1. Complete the package dependency/interface gate and record the exact
   accepted WP-05 symbols used.
2. Add fail-first `SafetyReplayTests` in `tests/test_planning.py`; the initial
   failure must be the missing replay boundary or missing behavior, not a
   broken fixture/import.
3. Add frozen `SafetyReplay`, `ReplayCheckpoint`, `ReplayFailure`, and
   `PlanningError` records plus `replay_schedule` in `planning.py`.
4. Validate case/baseline identity and primitive integrity once, before any
   candidate transformation. Recompute the empty baseline from opening cash,
   zero opening reserve, and every ordered primitive. Compare every published
   baseline checkpoint and `minimum_headroom`; disagreement raises
   `PlanningError("baseline_replay_mismatch", safe_ids)` atomically.
5. Validate supplied payment order without sorting it. Dates must be
   nondecreasing and within `[request_date, horizon_end]`; amounts must be
   finite and strictly positive. Multiple same-date payments retain tuple
   order. Candidate-shape failure returns the first stable failure and no
   misleading safety certification.
6. Apply each payment after all accepted baseline settlement/checkpoint phases
   on that date. A payment reduces cash, never reserve. Check the minimum after
   each payment and keep replaying through `horizon_end`, including after the
   last payment.
7. Resolve each `SpendingChange.event_id` to exactly one accepted recurring
   debit family anchor. Reject unknown/ambiguous targets, duplicate family
   actions, stop/reduce on the same family, more than three actions, a missing
   reduction amount, or a non-finite/negative/non-reducing amount.
8. Apply changes only to WP-05 movements explicitly marked as mutable inferred
   recurring debits on or after the request boundary. `stop` removes those
   future debits. `reduce_to` replaces each affected source amount with the
   exact new source amount and recomputes its home amount for that occurrence
   date through `events.convert_exact`; do not ratio-scale, round, reuse a
   historical rate, or rewrite the baseline.
9. Never change opening reserves, pending/reserve settlement, explicitly
   committed future effects, variable envelopes, credits, or historical
   records. An action with no affected mutable occurrence is rejected as
   `change_has_no_effect` rather than reported as savings.
10. Materialize a new immutable replay trace. Compute headroom after opening,
    every reserve/cash movement, every applied change replacement, and every
    payment. Equality with the minimum is safe; the first value below it is the
    checkpoint failure. Continue arithmetic after a breach so the trace still
    covers the complete horizon, but preserve the first failure unchanged.
11. On `blocks_downstream=True` or `minimum_headroom=None`, return uncertified
    and no numeric minimum. Later credits or changes must not silently clear an
    upstream unknown required debit. A missing exact FX rate for a proposed
    reduced debit is likewise an unsafe, source-identified candidate result;
    converter conflict/invalid-input errors remain atomic contract errors.
12. After tests pass, update the exact `planning.py` owner and replay symbols in
    `code/buy_or_wait/README.md` and `project-map.md`. Do not yet advertise the
    capacity API from WP-06B.

WP-06A accepts spending changes only as proposed transformations to replay.
It checks intrinsic applicability and arithmetic. WP-07 still owns user
permission, protected-category, flexibility/floor eligibility, candidate
enumeration, deadlines, payment-option matching, and ranking. Do not duplicate
those policies here.

## Acceptance Criteria

- **A-AC-01 — Independent arithmetic:** empty replay reproduces every accepted
  baseline checkpoint and minimum from primitive deltas; cached balance or
  minimum corruption is detected rather than trusted.
- **A-AC-02 — Exact payment phase:** every payment occurs after dated
  settlements on its date, reduces cash once, and is checked together with all
  later checkpoints through the fixed horizon.
- **A-AC-03 — Earlier breaches survive:** an opening or pre-payment baseline
  breach makes a later payment unsafe even if later credit would otherwise
  fund it. The returned failure identifies that first checkpoint.
- **A-AC-04 — Reserve conservation:** opening reservation reduces spendable
  cash once; settlement applies the debit and releases the same reserve without
  a second spendable reduction. Payments never release reserves.
- **A-AC-05 — Change isolation:** stop/reduce affects only the uniquely targeted
  mutable recurring debit family. Committed effects, reserves, envelopes,
  credits, other families, and the original baseline remain unchanged.
- **A-AC-06 — Exact changed FX:** a foreign reduction uses the supplied direct
  rate for each changed occurrence date with exact `Decimal` multiplication;
  missing debit FX rejects certification and reverse/prior rates are not used.
- **A-AC-07 — Fail-closed boundary:** upstream uncertainty remains monotonic;
  malformed candidates return a stable unsafe result, while impossible trusted
  baseline contracts raise a redacted atomic `PlanningError`.
- **A-AC-08 — Scope preservation:** no method preference, deadline,
  installment, partial-construction, candidate ranking, output formatting,
  provider, I/O, or clock behavior enters the replay kernel.

### WP-06A Finite-Risk Coverage Contract

| Invariant | Material dimensions/cases | Decisive oracle/boundary | Implementation evidence | Independent review probe | Gate owner |
|---|---|---|---|---|---|
| Every balance is independently reconstructed | opening; ordinary debit/credit; variable reserve; pending reserve before/at/after settlement; reserve beyond horizon; cached checkpoint/minimum tamper | Public `SafetyReplay` checkpoints compared with accepted primitive deltas and baseline publication | Arithmetic table with visible `Decimal` constants; one fail-first tamper case | Change one cached baseline balance while keeping primitive deltas fixed; replay must raise mismatch | Implementer targeted; fresh reviewer tamper probe |
| Payment ordering and horizon are exact | payment on D, after same-day debit/credit, multiple same-day payments, later payment, day 90, after-horizon, breach after last payment | Ordered replay checkpoints and first failure | Boundary-value tests around date/phase/minimum equality | Move only a late essential debit to day 90 and confirm an earlier apparently safe payment fails | Implementer targeted; fresh reviewer boundary probe |
| First failure is stable and truthful | malformed candidate; upstream block; opening breach; pre-payment breach; payment breach; later baseline breach; equality at minimum | `ReplayFailure` reason/date/index/source IDs | Decision-table tests with two possible later failures | Add a large later credit after the first breach; first failure must not move or clear | Implementer targeted; fresh reviewer mutation |
| Changes cannot erase unrelated obligations | stop/reduce; duplicate/conflicting action; unknown/ambiguous anchor; other family; committed debit; reserve; envelope; credit; no-effect action | Exact changed movement set, applied IDs, and unchanged original baseline | Small two-family fixtures plus one committed obligation and one reserve | Give an unrelated obligation the same amount/category as target; it must remain | Implementer targeted; fresh reviewer adversarial |
| Changed money remains exact | home amount; foreign direct rate by occurrence date; missing direct rate; reverse-only/prior-only; non-finite/negative/non-reducing new amount | Exact changed debit or stable rejected candidate/error | Direct Decimal products with distinct rates on two dates | Retain historical rate but remove second occurrence-date rate; second change must not reuse history | Implementer targeted; fresh reviewer adversarial |

## WP-06A Verification

Tests use small frozen synthetic `BaselineForecast` builders with decisive
deltas visible in each test. Expected balances and failures are independent
constants; no helper may call production replay to create the oracle.

| Evidence | Scenario and oracle | Command |
|---|---|---|
| Dependency | Accepted baseline producer and its exact replay surface pass | `python3 -m unittest tests.test_forecast` |
| Fail-first | Replay tests reject the absent implementation for the intended reason | `python3 -m unittest tests.test_planning.SafetyReplayTests` |
| Targeted | A-AC-01–A-AC-08 and every WP-06A finite-risk row pass through `replay_schedule` | `python3 -m unittest tests.test_planning.SafetyReplayTests` |
| Owning regression | Accepted forecast behavior remains unchanged | `python3 -m unittest tests.test_forecast` |
| Documentation contract | New owner/symbol/test links are navigable after the implementation map update | `python3 -m unittest tests.test_agent_foundation_contract` |
| Compile | New and upstream modules compile with the standard library | `python3 -m compileall -q code tests` |
| Broader gate | Fresh reviewer runs the complete suite and patch hygiene on final WP-06A bytes | `python3 -m unittest discover -s tests -p 'test_*.py'` then `git diff --check` |

Execution order is dependency, fail-first, targeted, owning regression,
documentation contract, and compile. The fresh independent reviewer reruns
targeted/upstream tests, performs distinct probes, and owns the broader gate.

## WP-06A Stops And Handoff

- Stop until WP-05 receives fresh independent `ACCEPT` and the interface gate
  passes on those exact bytes.
- Stop on dirty overlap in `planning.py` or `test_planning.py`; identify its
  owner rather than merging around it.
- Stop and route a narrow WP-05 correction when primitive movements,
  independent checkpoint fields, or mutable-family identity are unavailable.
- Stop rather than reconstructing upstream events, recurrence, or FX policy.
- Treat 13 calls as a soft checkpoint. If the task needs shared domain changes,
  new infrastructure, or more than this bounded replay surface, return to task
  design instead of consuming WP-06B scope.
- Next action: after dependency acceptance, run the standalone guided
  preflight and implement WP-06A.
- Required follow-on: immediately after implementation or correction, hand
  the completed bytes to a fresh independent acceptance reviewer.

---

# WP-06B — Compute Preference-Independent Baseline Capacity

Status: `ready` — blocked from execution until WP-06A receives fresh
independent `ACCEPT`

```yaml
agent_tier: standard
reasoning: medium
review: immediate
budget: 10 tool calls / 30 minutes / small context
```

## Readiness Route

`implementer self-preflight`

## Outcome

Implement `compute_baseline_capacity` on the accepted replay kernel so it
returns the exact safe amount on the request date and the first date through
the fixed horizon on which one standalone full payment is certified, without
consulting payment preferences, optional changes, or the desired deadline.

## Required Work

1. Confirm the exact accepted WP-06A API and rerun
   `tests.test_planning.SafetyReplayTests` before editing.
2. Add fail-first `CapacityTests` beside the replay tests. The first failure
   must demonstrate missing/incorrect capacity behavior, not a fixture error.
3. Add frozen `CapacityResult` and `compute_baseline_capacity(case, baseline)`
   to `planning.py`. Validate request ID/date, opening cash, home currency, and
   minimum consistency with the accepted baseline; do not read methods,
   partial permission, installment cap/options, desired completion date, or
   spending preferences.
4. First call empty `replay_schedule` to validate and independently certify
   the unchanged baseline. If upstream is blocked/uncertified or the baseline
   ever falls below minimum, return numeric safe amount zero and no earliest
   date, with the conservative diagnostic. Do not let a later credit erase the
   earlier breach.
5. On a certified additive baseline, compute raw safe-today capacity from the
   verified minimum headroom. Clamp it to `[0, requested_amount]`, then round
   downward once to the dataset output unit `Decimal("0.01")`; normalize
   negative zero to `Decimal("0")`. Do not round intermediate balances or
   requested amount, and do not change the result for preferences or optional
   changes.
6. When the rounded safe amount is positive, replay exactly one payment of
   that amount on `request_date`; an unsafe result is an internal
   `PlanningError("capacity_replay_mismatch", ...)`, not a smaller silent
   fallback.
7. Search dates in exact calendar order from `request_date` through
   `horizon_end`, inclusive. For each date, call the accepted replay with one
   payment equal to the full requested amount and no spending changes. Return
   the first safe date. Do not skip dates, infer from net daily balance, clip
   to `desired_completion_date`, or consult accepted methods.
8. If no date is certified, return `None`. A date after the desired deadline is
   still the correct baseline capacity result; WP-07 owns whether it can form
   an on-time recommendation.
9. Add the capacity API and `CapacityTests` command to the existing planning
   rows in `code/buy_or_wait/README.md` and `project-map.md`; do not add another
   module or command family.

The exhaustive search is at most 91 pure replays per case and is the required
simple implementation. Do not add indexes, binary search, caching, or a
different mathematical shortcut without measured need in a later task.

## Acceptance Criteria

- **B-AC-01 — Exact safe amount:** the result is the verified baseline minimum
  headroom clamped to the request and nonnegative range, rounded down once to
  `0.01`, with no negative zero and with a confirming payment replay.
- **B-AC-02 — Preference independence:** changing accepted payment methods,
  partial permission, installment cap/options, desired completion date, or
  optional-change willingness does not change either capacity field when the
  financial baseline and request amount are unchanged.
- **B-AC-03 — Exhaustive earliest search:** every date from D through the
  inclusive accepted horizon is tested in order with one full payment after
  that date's settlements; the first safe date is returned.
- **B-AC-04 — Contract dates:** earliest may equal D, fall after the desired
  deadline, land on day 90, or be `None`. It is never taken from a changed or
  installment/partial candidate.
- **B-AC-05 — Breach monotonicity:** upstream uncertainty or any earlier
  baseline breach yields zero certified safe amount and no earliest date even
  when later credits make the ending balance large.
- **B-AC-06 — Partial trajectory equivalence:** for `0 < safe < requested` and
  a certified earliest date F, replaying `(D, safe)` then
  `(F, requested-safe)` is safe; before F it matches the certified safe-today
  displacement and from F onward it matches the standalone full payment at F.
  This is a property guard, not authority to construct or select partial plans.
- **B-AC-07 — Scope preservation:** no eligibility, deadline filtering,
  spending changes, candidate enumeration/ranking, status/method derivation,
  serialization, provider, I/O, or clock behavior is added.

### WP-06B Finite-Risk Coverage Contract

| Invariant | Material dimensions/cases | Decisive oracle/boundary | Implementation evidence | Independent review probe | Gate owner |
|---|---|---|---|---|---|
| Safe amount is clamped and floored once | negative/zero/positive headroom; below/equal/above requested; fractional cent; exact cent; negative zero; blocked baseline | Public `CapacityResult` plus confirming `SafetyReplay` | Boundary table with literal Decimal inputs and outputs | Add `0.009` to headroom below the next cent; output must not round upward | Implementer targeted; fresh reviewer boundary probe |
| Earliest means first baseline full-payment date | today; later after credit; date before/on/after deadline; day 90; no safe date; earlier breach before later surplus | Exhaustive replay call outcomes and returned date | Small dated-ledger fixtures with independently calculated first safe dates | Insert a one-day unsafe dip before the apparent safe date; result must advance or become empty, never ignore it | Implementer targeted; fresh reviewer adversarial |
| Capacity ignores preferences and optional changes | full accepted/rejected; partial allowed/disallowed; installment cap/options; different deadline; stop/reduce willingness | Equal `CapacityResult` for financially identical case/baseline pairs | Metamorphic test changing only preference/deadline fields | Remove every accepted method while retaining the baseline; both capacity values must remain identical | Implementer targeted; fresh reviewer metamorphic |
| Prescribed partial path is arithmetically consistent | safe on D; remainder on F; before F; at/after F; exact sum; rounded safe remainder | Two-payment replay compared with the two certified single-payment trajectories | Property-style loop over small exact additive ledgers; preserve failing example if found | Perturb the remainder by `0.01`; equality/sum relation and trajectory comparison must detect it | Implementer targeted; fresh reviewer mutation |

## WP-06B Verification

Tests construct accepted synthetic forecast records directly. Dates, amounts,
checkpoint sequences, and expected outputs remain visible constants. The
partial equivalence oracle compares independently calculated balance
displacements; it must not call `compute_baseline_capacity` to calculate its
expected answer.

| Evidence | Scenario and oracle | Command |
|---|---|---|
| Dependency | Accepted replay kernel remains green on exact bytes | `python3 -m unittest tests.test_planning.SafetyReplayTests` |
| Fail-first | Capacity tests reject missing/incorrect capacity behavior for the intended reason | `python3 -m unittest tests.test_planning.CapacityTests` |
| Targeted | B-AC-01–B-AC-07 and every WP-06B finite-risk row pass through `compute_baseline_capacity` | `python3 -m unittest tests.test_planning.CapacityTests` |
| Owning suite | Replay and capacity behavior pass together | `python3 -m unittest tests.test_planning` |
| Upstream regression | Forecast production contract remains green | `python3 -m unittest tests.test_forecast` |
| Documentation contract | Planning owner, symbols, commands, and links remain navigable | `python3 -m unittest tests.test_agent_foundation_contract` |
| Compile | Planning and upstream code compile without dependencies | `python3 -m compileall -q code tests` |
| Broader gate | Fresh reviewer runs the full suite and patch hygiene on final WP-06 bytes | `python3 -m unittest discover -s tests -p 'test_*.py'` then `git diff --check` |

Execution order is dependency, fail-first, targeted, owning suite, upstream
regression, documentation contract, and compile. Record exact counts and the
fail-first reason. The fresh reviewer reruns the targeted/owning evidence,
performs the distinct probes, and owns the broader gate.

No live, paid, networked, performance, filesystem, provider, or public-sample
evaluation is required. Passing WP-06 proves capacity arithmetic and replay,
not candidate eligibility, ranking, output-row consistency, or sample accuracy.

## WP-06B Stops And Handoff

- Stop until WP-06A receives fresh independent `ACCEPT`; do not implement both
  parts concurrently in the shared files.
- Stop on red WP-06A or WP-05 tests, accepted API drift, or dirty overlap in
  `planning.py`/`test_planning.py`.
- Stop if correct capacity would require reading raw evidence, recomputing
  recurrence/lifecycle, or changing the accepted forecast ordering.
- Treat 10 calls as a soft checkpoint. Candidate generation, eligibility,
  ranking, output fields, performance optimization, or a shared abstraction is
  WP-07+ scope and must not be pulled forward.
- Next action: after WP-06A acceptance, self-preflight and implement WP-06B.
- Required follow-on: immediately after implementation or correction, hand
  the completed bytes to a fresh independent acceptance reviewer. Only an
  accepted WP-06B result may unblock WP-07.

## Package Exit Criteria

WP-06 is complete only after both parts receive fresh independent `ACCEPT` in
order. `tests.test_planning` and `tests.test_forecast` pass on the final shared
bytes; every finite-risk row has a recorded result; the public package and
project maps name the final symbols/commands; the diff contains no edit to
forecast/event/evidence/repository/domain behavior; and no capacity result
depends on preferences, optional changes, deadline, or a selected candidate.
