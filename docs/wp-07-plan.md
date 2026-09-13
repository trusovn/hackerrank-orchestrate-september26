# WP-07 — Candidate Plans, Spending Changes, And Ranking

Status: **COMPLETE — WP-07A ACCEPTED, WP-07B ACCEPTED, WP-07C ACCEPTED (2026-09-13)**

Authority: [`master-plan.md`](master-plan.md), WP-07

Depends on: accepted WP-06A and WP-06B

WP-07 is split without changing its total scope. The unsplit work combines
payment-shape eligibility, recurring-series change policy, exhaustive safety
replay, and ranking/status semantics and is estimated at about 36 tool calls.
That exceeds the requested 15-call threshold. WP-07A, WP-07B, and WP-07C each
have a separate proof boundary and a 12–15 call soft checkpoint.

All three parts edit `code/buy_or_wait/planning.py` and
`tests/test_planning.py`. They must run sequentially, and each part must receive
fresh independent acceptance before the next part begins. They must not be
assigned concurrently.

## Direction Trace

- Direction contribution: produce every contract-eligible payment/change
  candidate, independently certify it over the accepted 90-day ledger, and
  select one deterministic recommendation using the published ranking.
- User-observable effect: WP-08 receives one internally consistent planning
  decision whose method, plan, changes, status, and unchanged baseline capacity
  fields can be rendered without recreating financial policy.
- Why now: [`master-plan.md`](master-plan.md) places WP-07 after accepted WP-06
  capacity/replay and before output validation and serialization in WP-08.
- Direction decisions used: [`../AGENTS.md`](../AGENTS.md),
  [`../problem_statement.md`](../problem_statement.md) (Output meaning, Allowed
  values, 90-Day Safety Check, and Choosing Between Safe Plans),
  [`initial-analysis/08-financial-semantics-decisions.md`](initial-analysis/08-financial-semantics-decisions.md)
  (`FIN-005`, `FIN-010`–`FIN-014`, the plan/change/ranking table, and the
  complete status/method table), and [`master-plan.md`](master-plan.md),
  sections 5–10 and WP-07.
- New direction decisions required: None.

## Package Boundary

| Item | Contract |
|---|---|
| Product authority | [`../problem_statement.md`](../problem_statement.md) and [`../AGENTS.md`](../AGENTS.md) |
| Implementation authority | [`master-plan.md`](master-plan.md), WP-07, and the selected `FIN-005`, `FIN-010`–`FIN-014` rules |
| Allowed product changes | `code/buy_or_wait/planning.py` only |
| Allowed evidence changes | `tests/test_planning.py`; `code/buy_or_wait/README.md` and [`project-map.md`](project-map.md) only for exact planning symbols, tests, and commands that exist after each part |
| Read-only upstream context | Accepted `domain.py`, `forecast.py`, and WP-06 implementation/tests; the authority rows named above |
| Inputs | One immutable `RequestCase` and its accepted immutable `BaselineForecast` |
| Final output of WP-07 | One immutable planning decision containing the unchanged `CapacityResult`, the selected candidate or explicit fallback, derived status/method, and source-safe diagnostics |
| Out of scope | Editing domain/repository/evidence/events/forecast behavior; recurrence or lifecycle rediscovery; optional-change calibration; explanations; output-row creation/validation; CSV writing; CLI/pipeline wiring; provider/model work; public-sample metric reporting |
| Runtime constraints | Standard library only; pure, offline, deterministic; no file, environment, provider, network, cache, or clock access |

## Moving-Baseline And In-Progress Work Rule

The user reports that an earlier implementation is in progress. A repository
snapshot observed while this brief was written was clean at accepted WP-06, but
that is not authority to assume the same state at implementation time.

Immediately before each part:

1. Inspect `git status --short` and the scoped diff for `planning.py`,
   `test_planning.py`, `code/buy_or_wait/README.md`, and `project-map.md`.
2. Confirm the previous WP-07 part, if any, is accepted on the exact current
   bytes and run its focused test class.
3. If in-progress work overlaps either shared source/test file, stop and identify
   its owner. Do not overwrite, revert, duplicate, or merge around it.
4. If compatible WP-07 behavior already exists, gap-check it against this brief
   and implement only missing acceptance criteria. Preserve useful names and
   local style when their semantics match the contracts below.
5. Stop if accepted WP-06 public signatures or replay semantics changed. Route a
   narrow correction instead of adding a compatibility layer.

This is the readiness route for all three guided parts: `implementer
self-preflight` with the moving-baseline/overlap check above.

## Shared Architecture Contract

Keep the implementation in the existing flat `buy_or_wait.planning` module.
Do not add a planner class, generic rule engine, policy DSL, compatibility
wrapper, cache, or helper module.

The final public entry point should have this semantic shape (exact compatible
names may follow in-progress precedent):

```python
plan_request(
    case: RequestCase,
    baseline: BaselineForecast,
) -> PlanningDecision
```

Use a planning-owned output-method enum distinct from domain `PaymentMethod`:

```text
RecommendationMethod
  full_payment
  partial_payment
  installments
  wait
  not_recommended
```

Do not add `wait` or `not_recommended` to `PaymentMethod`; that enum validates
the profile's accepted immediate methods, and widening it would also widen the
input domain.

Use small frozen records with these semantics:

```text
PaymentTemplate
  recommendation_method     # full/partial/installments/wait
  payments                   # exact chronological tuple[Payment, ...]
  payment_option_id          # supplied option ID, otherwise None

PlanCandidate
  recommendation_method
  payments
  spending_changes
  payment_option_id
  safety_replay              # accepted WP-06 SafetyReplay
  forecast_debit_reduction   # exact home-currency reduction, zero without changes
  total_paid/start/completion/payment_count derived from payments

CandidatePool
  request_id
  capacity                   # exact CapacityResult computed once from baseline
  eligible_templates         # includes financially unsafe shapes needed by WP-07B
  candidates                 # safe candidates, no-change entries first
  diagnostics                # stable, source-safe rejection reason codes

PlanningDecision
  request_id
  capacity                   # unchanged object/value from CandidatePool
  selected_candidate         # None only for not_recommended
  affordability_status
  recommended_method
  diagnostics                # source-safe fallback/selection reasons
```

Derived properties are preferable to duplicated mutable-looking totals. If a
record stores a derived value, validate it at construction. Neither templates
nor candidates may contain balance values supplied by candidate construction;
the `SafetyReplay` is the sole safety oracle.

The final call flow is:

```text
compute_baseline_capacity
  -> enumerate method/deadline-eligible PaymentTemplate values
  -> replay no-change templates
  -> enumerate eligible recurring-series action sets
  -> replay changed templates and exhaustive changed-wait dates
  -> rank certified candidates
  -> derive status/method or explicit fallback
```

Ordinary ineligibility or an unsafe replay omits a candidate and records a
stable diagnostic. A malformed trusted case/baseline contract, mismatched
request ID, impossible accepted full-option shape, or inconsistent accepted
WP-06 result remains an atomic redacted `PlanningError`; do not silently repair
trusted upstream data.

### Deterministic construction rules

- Capacity is computed once from the unchanged baseline and copied unchanged to
  the pool/decision. Optional changes never recalculate either capacity field.
- Validate exactly one supplied full-payment option matching amount/date/count
  as an upstream contract check. A full-now candidate uses its option ID for
  provenance; a derived wait uses no option ID because its date differs.
- Full-now template: one payment `(D, A)` only when the user accepts
  `full_payment`.
- Partial template: exactly `(D, safe)` and `(F, A-safe)` only when the request
  allows it, the user accepts it, `0 < safe < A`, and baseline `F` exists at or
  before the deadline. Full-payment acceptance is irrelevant.
- Installment template: reproduce each supplied installment option exactly.
  Require user acceptance, populated positive cap, count not exceeding cap,
  positive interval/count/amount, first date at or after D, and last date at or
  before both the deadline and inclusive forecast end. Never resize, round,
  redistribute, synthesize, or add the fee twice.
- Baseline wait template: one payment `(F, A)` only when full payment is
  accepted and `D < F <= deadline` (the accepted horizon already bounds F).
  When `F == D`, full-now is the only corresponding method.
- Replay every eligible template through `replay_schedule`. For
  full/wait/partial, payment sum must be exactly A. For installments, it must be
  the exact supplied `total_payable_amount`. Every schedule must be
  chronological, complete by the deadline, and wholly inside the horizon.
- Preserve eligible but unsafe payment templates in `CandidatePool`; WP-07B
  must be able to combine them with changes. Only `candidates` are certified
  safe.
- Enumerate no-change candidates before changed candidates. Enumeration order
  is stable but must never decide the winner; permutation tests must prove the
  comparator is complete.

### Recurring-series change rules

Build a small family catalogue only from future `PrimitiveMovement` values with
`phase == "debit"`, `origin == "fixed_recurrence"`, a nonblank `family_id`,
occurrence date, exact source amount/currency, and source event IDs. Do not make
explicit commitments, reserves, reserve settlements, variable envelopes,
credits, or history changeable.

For each family:

1. Resolve its supplied same-user event anchors from `RequestCase.events`.
2. Choose the latest compatible historical occurrence by settlement date, then
   stable event ID. A future exact occurrence may anchor only when no historical
   anchor exists and recurrence is explicit in the accepted forecast.
3. Require exactly one family for the chosen anchor. Ambiguous, unknown, or
   cross-family anchors produce no action.
4. Exclude protected categories before checking willingness.
5. A floor reduction requires reducible or reducible-or-stoppable flexibility,
   category membership in the reduce set, a finite nonnegative supplied floor,
   and a floor strictly below every affected forecast source amount. The only
   generated amount is that floor.
6. A stop requires stoppable or reducible-or-stoppable flexibility and category
   membership in the stop set.

Generate every set of one, two, or three distinct families, choosing at most one
eligible action per family. Canonical storage order is stable family ID, then
anchor event ID/action type/amount. Never combine stop and reduce for one family,
even through different occurrence IDs. Do not generate reductions for variable
envelopes or a continuous range of amounts.

For each nonempty action set:

- replay every non-wait eligible payment template, including templates that
  were unsafe without changes;
- when full payment is accepted, exhaustively test one full payment on every
  date from D through `min(deadline, horizon_end)` and keep only the first safe
  changed date; represent D as `full_payment` and a later date as `wait`;
- accept a candidate only when the replay is safe, complete, on time, and its
  applied change IDs equal the requested canonical anchors;
- suppress exact duplicate `(method, option ID, payments, actions)` values; and
- calculate exact forecast debit reduction from the zero-payment changed replay
  versus the zero-payment baseline replay. It must be nonnegative. Do not infer
  it from source lexemes or round it.

A stop/reduction never removes an explicit or pending debit. A same-category or
same-amount pending debit is an explicit adversarial test.

### Ranking and status rules

Only safe, eligible, complete, on-time candidates reach ranking. Compare in
this exact order:

1. no spending changes;
2. lower exact total paid;
3. earlier first payment date;
4. fewer payments;
5. when both candidates are supplied offers, lower `payment_option_id` by
   stable text order;
6. fewer actions;
7. smaller exact total forecast debit reduction;
8. lexically sorted rendered action text; and
9. a documented stable method key only when the preceding fields cannot compare
   a supplied offer with a derived method.

Do not add an emergency/category/priority preference, maximize safe amount,
prefer installments, or use enumeration order. The published criteria outrank
all residual tie-breakers.

Derive output semantics from the winner, never from a separate decision tree:

| Winner | Status | Method |
|---|---|---|
| Full at D, no changes | `affordable_now` | `full_payment` |
| Full at D, with changes | `affordable_with_plan` | `full_payment` |
| Partial, with or without changes | `affordable_with_plan` | `partial_payment` |
| Installments, with or without changes | `affordable_with_plan` | `installments` |
| Wait after D, no changes | `affordable_later` | `wait` |
| Wait after D, with changes | `affordable_with_plan` | `wait` |
| No candidate | `not_affordable` | `not_recommended` |

For fallback, keep the baseline capacity unchanged and choose one truthful
stable reason category in this precedence: upstream baseline uncertified;
otherwise financially possible only after the deadline; otherwise no accepted
method/eligible option; otherwise no safe complete candidate. This diagnostic
supports WP-08 explanation but is not itself user-facing prose.

---

# WP-07A — Enumerate And Certify No-Change Candidates

Status: **ACCEPTED** — final verdict ACCEPT (2026-09-13), see Review Record
below

```yaml
agent_tier: standard
reasoning: medium
review: immediate
budget: 12 tool calls / 45 minutes / medium context
```

## Readiness Route

`implementer self-preflight` — apply the moving-baseline/overlap rule and run
the accepted WP-06 test classes before editing.

## Outcome

Produce an immutable candidate pool containing exact method/deadline-eligible
payment templates and every independently safe no-change candidate, while
preserving the accepted baseline capacity result unchanged.

## Required Work

1. Run the scoped overlap check and `python3 -m unittest
   tests.test_planning.SafetyReplayTests tests.test_planning.CapacityTests`.
2. Add fail-first `NoChangeCandidateTests`; make the first failure demonstrate
   missing eligibility/construction behavior, not fixture setup.
3. Add the minimal frozen method/template/candidate/pool records and one
   no-change enumeration entry point in `planning.py`.
4. Compute capacity once, validate the full-option upstream contract, and build
   full, partial, installment, and baseline-wait templates exactly as specified
   in the shared rules.
5. Replay each template with no changes; retain unsafe eligible templates for
   WP-07B but expose only safe results as candidates.
6. Record stable source-safe rejection codes; do not produce explanations or an
   output row.
7. Update only the exact new symbols/test class in the package README and
   project map after the implementation exists.

## Acceptance Criteria

- **A-AC-01 — Exact shapes:** full/wait/partial totals and dates are exact;
  installments reproduce a single supplied option's count, interval, amounts,
  fee-derived total, and ID without invention or rounding.
- **A-AC-02 — Complete eligibility:** method acceptance, request partial flag,
  positive partial bounds, baseline earliest, cap, first/last date, deadline,
  and horizon gates are all enforced independently.
- **A-AC-03 — Independent safety:** every returned no-change candidate has a
  safe WP-06 replay through the entire horizon; an unsafe but otherwise eligible
  template remains available for changed evaluation and is not called safe.
- **A-AC-04 — Capacity immutability:** candidate eligibility/preferences and
  unsafe/safe results do not change `amount_safe_to_pay` or baseline earliest.
- **A-AC-05 — Conservative empty pool:** no accepted method or no safe template
  yields an empty candidate tuple with truthful diagnostics, not an invented
  method or plan.

## WP-07A Verification

| Evidence | Scenario and oracle | Command |
|---|---|---|
| Dependency | Accepted replay/capacity contracts pass on current bytes | `python3 -m unittest tests.test_planning.SafetyReplayTests tests.test_planning.CapacityTests` |
| Fail-first/targeted | Exact full, wait, prescribed partial, exact installment, no-method, cap, deadline, horizon, and unsafe-template cases | `python3 -m unittest tests.test_planning.NoChangeCandidateTests` |
| Owning suite | Existing WP-06 and new WP-07A behavior pass together | `python3 -m unittest tests.test_planning` |
| Documentation | New names and focused command are navigable | `python3 -m unittest tests.test_agent_foundation_contract` |
| Compile | Standard-library source/tests compile | `python3 -m compileall -q code tests` |
| Broader gate | Deferred to the fresh final WP-07C reviewer; A reviewer reruns dependency and targeted tests | N/A — avoids duplicating the aggregate gate before later shared-file edits |

## WP-07A Stops And Handoff

- Stop on overlapping in-progress shared files or red accepted WP-06 tests.
- Stop if exact templates require changing repository/domain parsing or WP-06
  replay behavior.
- Treat 12 calls as a soft checkpoint. Spending-change enumeration, changed
  dates, ranking, statuses, explanations, and output are later scope.
- Next action: guided WP-07A implementation after self-preflight.
- Required follow-on: immediately after implementation or correction, hand the
  completed bytes to a fresh independent acceptance reviewer. Only accepted
  WP-07A bytes unblock WP-07B.

## Review Record

- Review date: 2026-09-13
- Profile: guided, fresh independent acceptance review
- Scope: `planning.py`, `test_planning.py`, and the WP-07A navigation rows in
  `code/buy_or_wait/README.md` and `docs/project-map.md`.
- Dependency evidence: `python3 -m unittest
  tests.test_planning.SafetyReplayTests tests.test_planning.CapacityTests` — OK.
- Targeted evidence: `python3 -m unittest
  tests.test_planning.NoChangeCandidateTests` — 11 tests OK (25 OK with
  dependencies).
- Independent regressions: interval mutation (freq 20 -> 15) keeps count and
  amount exact and recomputes dates without resizing; stripping every method
  leaves `CapacityResult` byte-identical with an empty pool; wait eligibility
  produces `(F, A)` with no option ID when full payment is accepted and no full
  option is supplied; installment fee is a separate disclosure, never added to
  `total_payable_amount` (repository `option_total_mismatch` and dataset rows
  agree: principal x count = total).
- Correction cycle: first review found F-01 (wait template gated on the
  supplied full option, contradicting the shared baseline-wait rule) and F-02
  (dead `_earliest_full`). Both fixed on the current bytes: wait eligibility
  depends only on full-payment acceptance and `D < F <= deadline`, and
  `_earliest_full` was removed, with regression tests
  `test_wait_eligibility_does_not_require_supplied_full_option`,
  `test_wait_absent_when_full_payment_not_accepted`, and
  `test_fee_bearing_installment_matches_real_dataset_total_contract`.
- Owning and repository gates: `python3 -m unittest tests.test_planning` — 25
  tests OK; `python3 -m unittest tests.test_forecast` — 72 tests OK;
  `python3 -m unittest tests.test_agent_foundation_contract` — 3 tests OK;
  `python3 -m compileall -q code tests` — OK; `git diff --check` — OK.
- Broad gate: deferred to the fresh final WP-07C reviewer per the split
  verification contract.
- No open WP-07A findings remain.

Verdict: **ACCEPT** (A-AC-01–A-AC-05 satisfied; no open findings). WP-07B may
proceed through its implementer self-preflight.

---

# WP-07B — Enumerate Changes And Certify Changed Candidates

Status: **ACCEPTED** — final verdict ACCEPT (2026-09-13), see Review Record
below

```yaml
agent_tier: standard
reasoning: medium
review: immediate
budget: 15 tool calls / 60 minutes / medium context
```

## Readiness Route

`implementer self-preflight` — confirm fresh WP-07A acceptance, no shared-file
overlap, and the exact accepted candidate-pool/template seam.

## Outcome

Extend the accepted pool with every permitted one-to-three-family action set and
every resulting independently safe changed candidate, including the earliest
safe changed wait/full date, without changing baseline capacity.

## Required Work

1. Run `NoChangeCandidateTests` and the WP-06 replay tests before editing.
2. Add fail-first `SpendingChangeCandidateTests` with visible event/family/
   movement fixtures; no expected balance may be generated by the code under
   test.
3. Build the fixed-recurrence family catalogue and canonical anchor selection
   exactly as specified in the shared rules.
4. Generate only allowed floor-reduction/stop actions and all canonical sets of
   up to three distinct families.
5. Replay eligible non-wait templates with each set. Separately search every
   allowed day for the earliest changed full/wait payment.
6. Reject no-effect, ambiguous, duplicate-family, protected, disallowed,
   below-floor, unsafe, late, incomplete, and applied-ID-mismatch results.
7. Calculate exact change reduction, suppress exact duplicates, and append
   changed candidates only after all no-change candidates.
8. Add dataset-backed boundary tests showing that the candidate pool contains
   the expected action-enabled candidates for `request_06`, `request_11`, and
   `request_21`. These are planner integration evidence, not permission to add
   request-ID branches.
9. Update the two navigation documents only for exact implemented symbols and
   tests.

## Acceptance Criteria

- **B-AC-01 — Only mutable series:** actions target uniquely anchored future
  fixed recurring debit families; history, explicit commitments, reserves,
  variable envelopes, credits, and unrelated families remain unchanged.
- **B-AC-02 — Permission and floor:** protected/category/flexibility checks all
  pass before action creation; reductions use exactly the supplied floor and
  stops require explicit stop willingness.
- **B-AC-03 — Complete finite enumeration:** every one-, two-, and three-family
  combination is considered deterministically, with at most one action per
  family and no stop/reduce conflict through alternate event IDs.
- **B-AC-04 — Changed safety:** every returned changed candidate is independently
  replay-safe, complete, on time, in horizon, and applies exactly its requested
  anchors. Pending debits survive same-category changes.
- **B-AC-05 — Changed date search:** for each action set, D through the bounded
  deadline/horizon is tested in order; the first safe date becomes full-at-D or
  changed-wait and no earlier unsafe date is skipped.
- **B-AC-06 — Capacity and ordering:** capacity values equal WP-07A's unchanged
  baseline result byte-for-value, and all no-change candidates precede changed
  candidates without making order a ranking input.
- **B-AC-07 — Public change boundaries:** candidate pools for requests 06, 11,
  and 21 contain exactly the expected anchors/floors for their selected changed
  path, with no request-ID-specific product logic.

## WP-07B Verification

| Evidence | Scenario and oracle | Command |
|---|---|---|
| Dependency | Accepted no-change pool and replay kernel pass | `python3 -m unittest tests.test_planning.NoChangeCandidateTests tests.test_planning.SafetyReplayTests` |
| Fail-first/targeted | Stop/reduce permission, protected/floor, family identity, 1–3 combinations, changed date, duplicate, FX/no-effect, and pending-debit cases | `python3 -m unittest tests.test_planning.SpendingChangeCandidateTests` |
| Public boundaries | Requests 06/11/21 expose expected safe changed candidates from the real dataset pipeline | Included in `SpendingChangeCandidateTests`; use `DatasetRepository -> resolve_case_evidence -> normalize_case_events -> build_baseline_forecast -> planner` |
| Owning suite | WP-06, WP-07A, and WP-07B pass together | `python3 -m unittest tests.test_planning` |
| Upstream regression | Accepted forecast production remains unchanged | `python3 -m unittest tests.test_forecast` |
| Documentation/compile | Navigation and syntax remain valid | `python3 -m unittest tests.test_agent_foundation_contract` then `python3 -m compileall -q code tests` |
| Broader gate | Deferred to the fresh final WP-07C reviewer | N/A — final shared bytes do not exist yet |

## WP-07B Stops And Handoff

- Stop without fresh WP-07A acceptance or on any dirty shared-file overlap.
- Stop if unique family/action eligibility cannot be proven from accepted
  primitives plus `RequestCase.events`; do not re-run recurrence discovery.
- Stop if public cases require request-ID rules, continuous reductions, or a
  changed capacity value.
- Treat 15 calls as a soft checkpoint. Ranking/status/output are not part B.
- Next action: guided WP-07B implementation after self-preflight.
- Required follow-on: immediately after implementation or correction, hand the
  completed bytes to a fresh independent acceptance reviewer. Only accepted
  WP-07B bytes unblock WP-07C.

## Review Record

- Review date: 2026-09-13
- Profile: guided, fresh independent acceptance review (two rounds: initial
  CHANGES_REQUESTED, then correction-round ACCEPT on the fixed bytes)
- Scope: `planning.py`, `test_planning.py`, and the WP-07B navigation rows in
  `code/buy_or_wait/README.md` and `docs/project-map.md`.
- Initial round: F-01 (P1) order-sensitive anchor comparison dropped safe
  multi-family candidates (`anchor_ids` sorted vs chronological
  `applied_change_event_ids` at the template and earliest-changed-date gates);
  F-02 (P2) `_action_sets` generated four-family sets; F-03 (P2) one source
  event anchoring two families produced actions for both instead of none.
- Correction round on the fixed bytes: F-01 fixed by comparing applied IDs as
  an ordered set; F-02 fixed by stopping extension at three families; F-03
  fixed by dropping anchors shared across families in `_family_catalogue`.
  Independent regression probes (order-sensitive two-family fixture, four-
  family enumeration, cross-family anchor) all pass on the corrected bytes.
- Regression tests added: `test_changed_replay_applied_ids_do_not_depend_on_application_order`,
  `test_four_family_sets_never_exceed_three_families`,
  `test_cross_family_anchor_produces_no_actions`.
- Dependency evidence: `python3 -m unittest
  tests.test_planning.NoChangeCandidateTests tests.test_planning.SafetyReplayTests` — OK.
- Targeted evidence: `python3 -m unittest
  tests.test_planning.SpendingChangeCandidateTests` — 17 tests OK.
- Owning and repository gates: `python3 -m unittest tests.test_planning` — 42
  tests OK; `python3 -m unittest tests.test_forecast` — 72 tests OK;
  `python3 -m unittest tests.test_agent_foundation_contract` — 3 tests OK;
  `python3 -m unittest discover -s tests -p 'test_*.py'` — 297 tests OK
  (1 skipped); `python3 -m compileall -q code tests` — OK; `git diff --check`
  — OK. Full 250-request dataset pipeline processed in ~1.1s.
- Broad gate: deferred to the fresh final WP-07C reviewer per the split
  verification contract.
- No open WP-07B findings remain.

Verdict: **ACCEPT** (B-AC-01–B-AC-07 satisfied on the corrected bytes; no open
findings). WP-07C may proceed through its implementer self-preflight.

---

# WP-07C — Rank Candidates And Return One Decision

Status: **ACCEPTED** — final verdict ACCEPT (2026-09-13), see Review Record
below

```yaml
agent_tier: standard
reasoning: medium
review: immediate
budget: 12 tool calls / 45 minutes / medium context
```

## Readiness Route

`implementer self-preflight` — confirm fresh WP-07B acceptance, no shared-file
overlap, and the final candidate fields needed by every ranking key.

## Outcome

Select one winner with a total deterministic comparator and return a complete
planning decision whose status/method follow the authoritative table and whose
capacity remains the accepted baseline result; return an explicit conservative
fallback when the pool is empty.

## Required Work

1. Run both WP-07A/B focused classes before editing.
2. Add fail-first `RankingAndDecisionTests` covering every published criterion,
   each residual tie-breaker, permutation independence, every status row, and
   each fallback reason class.
3. Implement one explicit rank-key/comparator in the published order. Do not
   rely on dataclass ordering, enumeration order, enum ordinal, set iteration,
   or Python object identity.
4. Implement `plan_request` (or the compatible final public name) to obtain the
   pool, select the minimum ranked candidate, and derive status/method from the
   winner table.
5. For an empty pool, return `not_affordable/not_recommended`, no selected
   candidate, unchanged capacity, and the truthful precedence-ordered fallback
   diagnostic.
6. Add exact selection assertions for public requests 06, 11, and 21 and
   synthetic no-method, late-only, changed-wait, equal-offer, fee-free tie, and
   candidate-permutation cases.
7. Update `code/buy_or_wait/README.md` and `project-map.md` with the final
   planner entry point, result records, test classes, and focused command. Do
   not mark WP-07 complete; acceptance records own that state.

## Acceptance Criteria

- **C-AC-01 — Published order:** no-change, exact total cost, start date,
  payment count, and stable text option ID decide in that order and always
  outrank residual ties.
- **C-AC-02 — Total deterministic tie:** action count, exact forecast reduction,
  action text, and final method key resolve remaining ties; permuting otherwise
  identical input candidate order never changes the winner.
- **C-AC-03 — Status/method table:** all six winner classes and the empty-pool
  fallback produce exactly the authorized status/method combination; capacity
  is never inferred from the winner.
- **C-AC-04 — Truthful fallback:** late-only capacity, preference/option
  exclusion, upstream uncertainty, and genuine no-safe-candidate conditions
  remain distinguishable without invented financial claims.
- **C-AC-05 — Public and synthetic cases:** requests 06/11/21 select their exact
  action-enabled full-payment paths; no-method, late-only, changed-wait,
  equal-offer, fee-free tie, protected, floor, and pending-debit regressions
  remain green across the complete planning suite.
- **C-AC-06 — Scope preservation:** no explanation, `OutputRow`, CSV, pipeline,
  provider, calibration, or upstream financial policy enters `planning.py`.

## WP-07C Verification

| Evidence | Scenario and oracle | Command |
|---|---|---|
| Dependency | Accepted candidate construction/change enumeration pass | `python3 -m unittest tests.test_planning.NoChangeCandidateTests tests.test_planning.SpendingChangeCandidateTests` |
| Fail-first/targeted | Every ranking/status/fallback row and input permutation | `python3 -m unittest tests.test_planning.RankingAndDecisionTests` |
| Owning suite | All WP-06/WP-07 planner behavior passes together | `python3 -m unittest tests.test_planning` |
| Upstream regression | Forecast and replay inputs remain accepted | `python3 -m unittest tests.test_forecast` |
| Documentation | Final symbols, owner, links, and commands are navigable | `python3 -m unittest tests.test_agent_foundation_contract` |
| Compile | Product/tests compile with the standard library | `python3 -m compileall -q code tests` |
| Broader gate | Fresh WP-07C reviewer owns aggregate verification on final bytes | `python3 -m unittest discover -s tests -p 'test_*.py'` then `git diff --check` |

## Review Record

- Review date: 2026-09-13
- Profile: guided, fresh independent acceptance review (three rounds: initial
  CHANGES_REQUESTED, then correction rounds on the fixed bytes)
- Scope: `planning.py`, `test_planning.py`, and the WP-07C navigation rows in
  `code/buy_or_wait/README.md` and `docs/project-map.md`.
- Initial round: F-01 (P2) `rank_key` compared the option-ID key before the
  residual action/reduction/text keys, so a mixed supplied/derived pair could
  be decided by the option-ID state instead of the published residuals;
  F-02 (P2) `_fallback_diagnostic` checked the no-accepted-method template
  proxy before the financially-possible-after-deadline scan, misclassifying
  "safe within deadline but unaccepted" as `fallback_no_safe_candidate`.
- Correction round on the fixed bytes: F-01 fixed by moving the option key
  after the residual keys; F-02 fixed by scanning after-deadline full-payment
  possibility before the no-eligible-option template check. Independent
  pairwise probes (derived-1-action beats supplied-2-actions; supplied-1-action
  beats derived-2-actions; supplied-only stable text order
  `payment_option_10` < `payment_option_2`) and fallback probes ((a) `methods=()`
  with safe-only-after-deadline → `fallback_possible_after_deadline`;
  (b) installments accepted with no option → `fallback_no_accepted_method`;
  (b-real) eligible-but-unsafe option → `fallback_no_safe_candidate`;
  (d) blocked baseline → `fallback_baseline_uncertified`) all pass.
- Second correction round: F-03 (P2) `_OptionTieKey` made the comparator
  non-total for mixed supplied/derived twins (`A == C` while `A < B` and
  `B < C`), so `min()` winner identity was input-order-dependent, violating
  C-AC-02/FR-08. Fixed by making the option key a total three-state order
  (supplied before derived, supplied IDs by stable text) placed after the
  residual keys; the mixed twin set now has the strict total order
  `C < A < B` and every one of the six candidate permutations returns the same
  winner. Regression tests added: `test_residual_ties_are_total_and_permutation_independent`
  (F-01/F-03 rows), `test_fallback_classes_are_truthful_and_ordered`
  (F-02 rows).
- Dependency evidence: `python3 -m unittest
  tests.test_planning.NoChangeCandidateTests tests.test_planning.SpendingChangeCandidateTests` — 28 tests OK.
- Targeted evidence: `python3 -m unittest
  tests.test_planning.RankingAndDecisionTests` — 5 tests OK.
- Owning and repository gates: `python3 -m unittest tests.test_planning` — 47
  tests OK; `python3 -m unittest tests.test_forecast` — 72 tests OK;
  `python3 -m unittest tests.test_agent_foundation_contract` — 3 tests OK;
  `python3 -m unittest discover -s tests -p 'test_*.py'` — 302 tests OK
  (1 skipped); `python3 -m compileall -q code tests` — OK; `git diff --check`
  — OK. Full 250-request dataset pipeline processed with status distribution
  unchanged (affordable_now 9, affordable_with_plan 9, affordable_later 1,
  not_affordable 231) and no rank_key-vs-brief_key winner diffs.
- Broad gate: owned by this fresh final WP-07C reviewer on the corrected
  bytes; run and passed.
- No open WP-07C findings remain.

Verdict: **ACCEPT** (C-AC-01–C-AC-06 satisfied on the corrected bytes; no open
findings). WP-07 package exit criteria are met; WP-08 may proceed.

## WP-07C Stops And Handoff

- Stop without fresh WP-07B acceptance or on shared-file overlap.
- Stop if a candidate lacks a field needed to implement the exact comparator;
  correct the WP-07B seam narrowly rather than reading upstream data in the
  comparator.
- Stop if an observed public mismatch would require changing an authoritative
  ranking rule or adding request/category-specific priority.
- Treat 12 calls as a soft checkpoint. WP-08 owns explanations, output-row
  validation, serialization, and writing.
- Next action: guided WP-07C implementation after self-preflight.
- Required follow-on: immediately after implementation or correction, hand the
  completed bytes to a fresh independent acceptance reviewer. That reviewer
  owns the broader gate and the final WP-07 verdict.

## Finite-Risk Coverage Contract

Row IDs remain stable across all three parts and correction reviews.

| Invariant | Material dimensions/cases | Decisive oracle/boundary | Implementation evidence | Independent review probe | Gate owner |
|---|---|---|---|---|---|
| FR-01 payment templates are exact | full D; wait F; partial two payments; installments with 2/3/N payments; 28/30/31-day interval; before D; on/after deadline and day 90 | `PaymentTemplate` values plus matching source option/cap/request | WP-07A literal date/Decimal tables and malformed boundary cases | Mutate one option interval or last date while keeping total fixed; no candidate may resize it | A implementer targeted; A fresh reviewer mutation |
| FR-02 method gates never alter capacity | full/partial/installments accepted or absent; partial flag; blank/populated cap; no methods | Equal `CapacityResult` with differing candidate pools | WP-07A metamorphic profile/request tests | Strip every method after fixing baseline; capacity must remain identical and pool empty | A implementer; A fresh reviewer metamorphic |
| FR-03 every candidate is fully replayed | safe; payment breach; later essential breach; baseline breach repaired/not repaired by change; equality at minimum | Candidate's `SafetyReplay` through final horizon checkpoint | A/B fixtures with visible independent balances | Add a late day-90 debit after the final payment; candidate must disappear if unsafe | A/B implementers; respective fresh reviewers |
| FR-04 only approved recurring families change | reducible; stoppable; both; fixed; protected; category disallowed; variable envelope; explicit/pending debit; credit; ambiguous/duplicate anchor | Generated actions and unchanged replay checkpoints | WP-07B two-family plus unrelated-obligation fixtures | Give pending/fixed debit same category, amount, and source-near ID; it must survive | B implementer; B fresh reviewer adversarial |
| FR-05 action sets are complete and conflict-free | one/two/three families; fourth excluded; two action choices; duplicate occurrence IDs; stop/reduce same family | Canonical action-set list, no duplicate family, max length three | WP-07B exact finite set for three small families | Reverse event/movement order; canonical sets must remain identical | B implementer; B fresh reviewer permutation |
| FR-06 changed dates are earliest and bounded | D; D+1; deadline; after deadline; day 90; earlier failed date; no safe date | Consecutive replay attempts and returned candidate date | WP-07B small dated ledger fixtures | Insert a one-day dip immediately before apparent safe day; result advances or disappears | B implementer; B fresh reviewer adversarial |
| FR-07 ranking follows published priority | change/no-change; lower/equal cost; earlier/equal start; fewer/equal payments; two option IDs | Selected candidate under one-variable-at-a-time pairs | WP-07C pairwise decision table | Make a changed plan cheaper than no-change; no-change must still win | C implementer; C fresh reviewer pairwise |
| FR-08 residual ties are total and stable | action count; reduction; action text; derived versus supplied; permuted candidate order | Same winner identity for every permutation | WP-07C exhaustive permutations of a small equal-primary set | Use `payment_option_10` and `payment_option_2`; stable text ordering, not numeric parsing, must decide | C implementer; C fresh reviewer permutation |
| FR-09 decision table preserves semantics | full now unchanged/changed; partial; installment; wait unchanged/changed; empty pool; baseline earliest today/later/empty | `PlanningDecision` status/method/capacity/candidate tuple | WP-07C row-by-row table plus public 06/11/21 | Remove full acceptance while leaving money unchanged; no wait/full result may appear | C implementer; final fresh reviewer |

## Package Exit Criteria

WP-07 is complete only when A, B, and C receive fresh independent `ACCEPT` in
order; every FR row is recorded pass on the final relevant bytes;
`tests.test_planning` and `tests.test_forecast` pass; the final planner symbols
and focused classes are present in both navigation maps; the final fresh
reviewer owns and passes the complete unit suite and `git diff --check`; and no
WP-07 change touches upstream financial behavior or WP-08 output concerns.
All criteria are met on the accepted WP-07C bytes; WP-08 may proceed.

