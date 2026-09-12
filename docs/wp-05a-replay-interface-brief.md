# WP-05A — Correct The Replayable Baseline Interface

Status: **ACCEPTED** — final verdict ACCEPT (2026-09-12), see Review Record

Authority: [`wp-05-plan.md`](wp-05-plan.md), AC-08; [`wp-06-plan.md`](wp-06-plan.md), Dependency And Interface Gate and WP-06A; and the WP-06A interface-gate finding recorded on 2026-09-12.

```yaml
agent_tier: strong
reasoning: medium
review: immediate
budget: 12 tool calls / 35 minutes / medium context
```

## Readiness route

`standalone guided preflight — bind the corrective surface to the accepted WP-05 ledger without overlapping a WP-06 owner`

## Outcome

Publish an immutable ordered primitive-movement ledger from `BaselineForecast` so a downstream safety replay can independently recompute cash and reserve balances and detect checkpoint corruption without rediscovering events, recurrence, or FX.

## Direction trace

- Direction contribution: restore the accepted WP-05 replayable-boundary promise needed to certify every candidate payment schedule across the fixed horizon.
- User-observable effect: no direct recommendation change; enables WP-06A’s independently verified safety result, which rejects plans that would breach the minimum balance.
- Why now: WP-06A’s mandatory interface gate found that the accepted checkpoint snapshots cannot independently reconstruct reserve settlement movements.
- Direction decisions used: [`../AGENTS.md`](../AGENTS.md), [`../problem_statement.md`](../problem_statement.md) (90-Day Safety Check), [`initial-analysis/08-financial-semantics-decisions.md`](initial-analysis/08-financial-semantics-decisions.md) (`FIN-002`, `FIN-009`, `FIN-011`, `FIN-013`), [`wp-05-plan.md`](wp-05-plan.md) (AC-06–AC-08), and [`wp-06-plan.md`](wp-06-plan.md) (Dependency And Interface Gate and WP-06A).
- New direction decisions required: None.

## Authority and scope

| Item | Contract |
|---|---|
| Product authority | [`../problem_statement.md`](../problem_statement.md) and [`../AGENTS.md`](../AGENTS.md) |
| Correctness authority | [`wp-05-plan.md`](wp-05-plan.md), AC-08 and the accepted-ledger semantics; [`wp-06-plan.md`](wp-06-plan.md), interface gate |
| Dependencies | WP-05 remains accepted; `python3 -m unittest tests.test_forecast` must pass before editing; no active work may overlap `forecast.py` or `test_forecast.py` |
| Allowed product changes | `code/buy_or_wait/forecast.py` only: feature-owned frozen replay records and their construction/publication |
| Allowed evidence changes | `tests/test_forecast.py`; update `code/buy_or_wait/README.md` and `project-map.md` only for the new public forecast surface, ownership, and commands |
| Read-only context | `domain.py`, `events.py` (`convert_exact` remains unchanged), `tests/test_events.py`, accepted WP-05 record, and WP-06A contract |
| Out of scope | Any `planning.py`/`test_planning.py` implementation; payment insertion; capacity; spending-change transformation; recurrence, lifecycle, or FX-policy changes; raw-evidence parsing; output/CLI/provider work |
| Assumptions / unresolved decisions | Existing ordered ledger semantics are authoritative. Preflight must confirm a clean non-overlapping ownership state; otherwise stop. |

## Required work

1. Add a feature-owned frozen `PrimitiveMovement` record in `forecast.py` and add ordered `primitive_movements` to frozen `BaselineForecast`.
2. Materialize the primitive sequence before checkpoints, then derive published checkpoints from that sequence; do not derive primitive deltas from checkpoint balances.
3. Preserve the existing checkpoint behavior while adding a stable movement identity to each checkpoint (or an equally direct immutable one-to-one reference) so an independent consumer can cross-check the public projections.
4. Update navigation only after the public surface and focused tests exist. Do not change the accepted financial policy or forecast result for valid existing cases.

## Contract and acceptance criteria

Each `PrimitiveMovement` must expose: `date`, deterministic `phase`, stable `movement_id`, exact `cash_delta`, exact `reserve_delta`, `origin`, `source_event_ids`, `source_fact_ids`, `family_id`, and `occurrence_date`. For mutable inferred recurring-debit movements it must additionally preserve source amount, source currency, and home currency; fields inapplicable to another movement kind are `None`, never reconstructed from prose.

The ordered sequence starts from `BaselineForecast.opening_cash` and zero reserve. It includes an opening movement, each opening reserve, every dated debit/credit, and each reserve settlement. Its semantic deltas are fixed: an opening reserve is `(cash=0, reserve=+amount)`; a debit is `(-amount, 0)`; a credit is `(+amount, 0)`; a settlement is `(-amount, -amount)`. Checkpoints remain projections of the same ordered sequence, not a second source of truth.

- **AC-01 — Independent reconstruction:** replaying `opening_cash` plus each primitive’s explicit cash/reserve deltas reproduces every published checkpoint’s cash, reserve, spendable balance, and headroom exactly; it also reproduces `minimum_headroom` when the baseline is certified.
- **AC-02 — Stable complete movement identity:** every published movement has a unique deterministic ID and source-safe provenance; ordered movements include opening, reserve, debit, credit, and settlement phases without relying on checkpoint snapshots or text parsing.
- **AC-03 — Reserve conservation:** reserve creation reduces spendable cash once, and its later settlement applies equal cash and reserve deltas so spendable cash does not fall a second time. A reserve beyond the horizon remains represented only by its opening reserve movement.
- **AC-04 — Mutable-recurring boundary:** only inferred recurring debit movements carry the family/source-money fields required by WP-06 change replay. Variable envelopes, explicit committed effects, reserves, credits, and historical records are unambiguously non-mutable.
- **AC-05 — Compatibility and conservatism:** existing valid forecast checkpoints, ordering, diagnostics, `blocks_downstream`, and `minimum_headroom` remain unchanged. Blocking still publishes no numeric certified minimum; invalid trusted ledger construction fails atomically with `ForecastBuildError` and safe IDs.
- **AC-06 — Scope preservation:** the correction is standard-library-only, pure, and does not add payment/capacity/candidate/ranking logic or alter `events.convert_exact`.

### Finite-risk coverage contract

| Invariant | Material dimensions/cases | Decisive oracle/boundary | Implementation evidence | Independent review probe | Gate owner |
|---|---|---|---|---|---|
| Primitive sequence fully reconstructs balances | opening; debit; credit; opening reserve; settlement; reserve beyond horizon; day-90 movement | Independent arithmetic from literal primitive deltas equals literal checkpoint fields and minimum | New `PrimitiveMovementTests` with visible `Decimal` constants | Tamper only a checkpoint balance after primitives are built; independent reconstruction must disagree | Implementer targeted; fresh reviewer tamper probe |
| Reserve is conserved | pending debit before, on, and after settlement; settlement beyond horizon | `(0,+amount)` then `(-amount,-amount)` preserves spendable cash at settlement | Table-driven reserve fixtures | Change settlement reserve delta only; projection/conservation assertion must fail | Implementer targeted; fresh reviewer mutation |
| Changeable family data is neither missing nor overbroad | fixed inferred recurring debit; foreign inferred recurring debit; envelope; explicit effect; credit; reserve | Only qualifying debit movements expose source-money/family metadata | Focused movement-kind fixtures | Give an explicit debit the same category/amount as a series; it remains non-mutable | Implementer targeted; fresh reviewer adversarial |
| Published order is deterministic and complete | same-day debit/credit order; same-kind ID tie; duplicate IDs; blocking baseline | Ordered IDs and one-to-one checkpoint linkage | Deterministic-order and invalid-integrity tests | Reorder equal-date input records; published order remains the accepted stable order | Implementer targeted; fresh reviewer adversarial |

## Verification

| Evidence | Scenario and oracle | Command |
|---|---|---|
| Dependency | Accepted forecast surface is green before correction | `python3 -m unittest tests.test_forecast` |
| Fail-first / regression | New movement tests initially fail because the public primitive ledger is absent; failure must be import/attribute behavior, not fixture setup | `python3 -m unittest tests.test_forecast.PrimitiveMovementTests` |
| Targeted | AC-01–AC-06 and all finite-risk rows through `build_baseline_forecast` | `python3 -m unittest tests.test_forecast.PrimitiveMovementTests tests.test_forecast.LedgerTests` |
| Owning suite | Recurrence, lifecycle facts, variable spending, income/FX, and ledger behavior remain unchanged | `python3 -m unittest tests.test_forecast` |
| Documentation contract | New public symbol and navigation links resolve | `python3 -m unittest tests.test_agent_foundation_contract` |
| Compile | Product and tests compile without dependencies | `python3 -m compileall -q code tests` |
| Broader gate | Fresh reviewer owns full-suite and patch-hygiene checks on final corrected bytes | `python3 -m unittest discover -s tests -p 'test_*.py'` then `git diff --check` |

## Stops and handoff

- Stop if `tests.test_forecast` is red, `forecast.py`/`test_forecast.py` have dirty overlapping work, or a compliant public primitive sequence would require changing recurrence/lifecycle/FX policy.
- Stop and return to task design if the required stable movement identity cannot be added without a shared-domain or WP-04 contract change.
- Preserve pre-existing user work and treat the budget as a soft checkpoint.
- Next action: standalone guided preflight, then implement this correction.
- Required follow-on: after acceptance, run the WP-06A dependency/interface gate and begin its standalone guided preflight.

## Review Record

- Review date: 2026-09-12
- Profile: guided, fresh independent acceptance review
- Scope: `forecast.py`, `test_forecast.py`, and the allowed forecast navigation updates
- Targeted evidence: `python3 -m unittest tests.test_forecast.PrimitiveMovementTests tests.test_forecast.LedgerTests` — 10 tests OK
- Independent regression: equal-date input reordering preserved deterministic movement order and IDs
- Owning and documentation gates: `python3 -m unittest tests.test_forecast` — 72 tests OK; `python3 -m unittest tests.test_agent_foundation_contract` — 3 tests OK; `python3 -m compileall -q code tests` — OK
- Broad gate: `python3 -m unittest discover -s tests -p 'test_*.py'` — 255 tests OK, 1 skipped; `git diff --check` — OK

Verdict: **ACCEPT** — AC-01–AC-06 and all finite-risk rows satisfied; no open findings. WP-06A may proceed through its dependency/interface gate and preflight.
