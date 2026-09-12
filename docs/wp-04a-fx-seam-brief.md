# WP-04A — Public Exact-FX Converter Seam (Narrow WP-04 Interface Correction)

Status: **READY — BLOCKS WP-05**

Authority: [`wp-05-plan.md`](wp-05-plan.md) (Dependency Gate item 4 and
Stops And Handoff), [`master-plan.md`](master-plan.md) WP-04/WP-05, and the
accepted WP-04 exact-FX rules in [`wp-04-plan.md`](wp-04-plan.md)
("Exact directed FX").

Depends on: accepted WP-04 (`code/buy_or_wait/events.py`, commit `78d9a7b`).
WP-05 implementation is stopped on this seam.

Metadata:

```yaml
agent_tier: strong
reasoning: high
review: immediate
budget: 12 tool calls / 45 minutes / small context
```

## Problem

WP-05's dependency gate (docs/wp-05-plan.md:69-98) requires accepted WP-04 to
expose **one public pure exact-FX operation (or an equivalent immutable
converter owned by `events.py`)** that converts a synthesized future source
amount using exactly `(settlement_date, source_currency, home_currency)`,
retaining WP-04's no-inversion, no-nearest-date, no-chaining, and no-rounding
behavior.

Accepted WP-04 has only the private `_Normalizer._convert`
(`code/buy_or_wait/events.py:338`) and the private rate index built by
`_Normalizer._build_rate_index`. There is no public converter seam
(`events.py.__all__` has none). The accepted WP-04 plan never promised one;
the WP-05 gate introduced it. Per wp-05-plan.md:92-98 the fix is a narrow
WP-04 interface correction plus focused regression and fresh independent
acceptance — not a workaround in `forecast.py`.

## Outcome

`buy_or_wait.events` exports one public pure converter that WP-05 can call for
every synthesized foreign-currency occurrence, with WP-04's exact accepted
semantics. Accepted lifecycle behavior is unchanged and all existing suites
stay green.

## Scope

| Item | Contract |
|---|---|
| Allowed code changes | `code/buy_or_wait/events.py` (new public seam + minimal delegation refactor), `tests/test_events.py` (new focused regression class) |
| Allowed doc changes | `code/buy_or_wait/README.md` symbol-map rows for the new public symbol; `docs/project-map.md` only if a command row changes (none should) |
| Out of scope | Any WP-05 file (`forecast.py`, `test_forecast.py`), evidence/repository/domain changes, FX semantic changes, recurrence or forecast logic, new dependencies, provider/network/IO |
| Read-only context | Accepted `events.py`, `tests/test_events.py`, `docs/wp-04-plan.md` (Exact directed FX section), `docs/wp-05-plan.md` (Dependency Gate item 4, phase 7) |

## Required Interface

Exact names may follow local style, but the seam must be a pure, immutable,
standard-library-only module-level function in `events.py`, roughly:

```python
def convert_exact(
    rates: tuple[ExchangeRateRecord, ...],
    source_amount: Decimal,
    settlement_date: date,
    source_currency: CurrencyCode,
    home_currency: CurrencyCode,
    source_ids: tuple[str, ...] = (),
) -> Decimal
```

Semantics (must match `_convert`/`_build_rate_index` exactly):

1. `source_currency is home_currency` → return `source_amount` unchanged; no
   rate consulted.
2. Build the directed rate index from `rates` exactly as
   `_build_rate_index` does: a non-`ExchangeRateRecord` element →
   `EventNormalizationError("invalid_rate_record", ...)`, duplicate
   conflicting key → `("fx_rate_conflict", ...)`, non-finite or
   non-positive rate → `("fx_rate_invalid", ...)`. Conflict and invalid
   errors carry the safe key ID only; never raw carrier content.
3. Look up exactly `(settlement_date, source_currency, home_currency)`.
   Missing → `("fx_rate_missing", ...)`. Only this branch prefixes the
   caller's `source_ids` onto the error's safe IDs (key ID like
   `"2024-03-15:USD:IDR"` last), matching the accepted shaping in
   `_convert`; conflict/invalid do not add `source_ids`.
4. Return `source_amount * rate` exactly: no rounding, quantization, float
   conversion, inversion of reverse pairs, chaining, or nearest/prior-date
   selection.

Recommended implementation: extract module-level pure helpers
(rate-index builder + converter) and have `_Normalizer._build_rate_index` and
`_Normalizer._convert` delegate to them, preserving the accepted error-ID
shaping (existing `ExactFXTests` are the regression oracle). Do not duplicate
a second divergent algorithm.

WP-05 will consume the seam like this (context for the correction, not work
for it): missing-rate errors are caught by WP-05 per direction (debit →
blocking diagnostic, credit → conservative omit); any other converter error
(conflict/invalid) is re-raised atomically as WP-05's
`ForecastBuildError`. WP-05 passes `case.relevant_rates` and attaches its own
occurrence source IDs via the `source_ids` prefix.

## Acceptance Criteria

- **AC-1** — Public converter exists, is pure (no files, env, clock, provider,
  cache; writes nothing), and is importable from `buy_or_wait.events`.
- **AC-2** — Exact products: home-currency passthrough unchanged;
  `Decimal("1800")` at rate `Decimal("15833.33")` returns exactly
  `Decimal("28499994.00")`.
- **AC-3** — Missing, reverse-only, prior-date-only, conflicting, and invalid
  rate fixtures each fail closed with the accepted reason codes and safe IDs;
  no partial result, no nearest-date or inversion fallback.
- **AC-4** — Accepted WP-04 behavior is byte-for-byte preserved:
  `python3 -m unittest tests.test_repository tests.test_evidence
  tests.test_events` stays green without modifying any existing test.
- **AC-5** — New focused regressions live in `tests/test_events.py`, use
  hand-built `ExchangeRateRecord` tuples (repository duplicate-key rejection
  does not apply to hand-built tuples), and independently written expected
  constants.
- **AC-6** — Final diff touches only the allowed paths above: `events.py`,
  `tests/test_events.py`, and the permitted `README.md` symbol-map row; no
  WP-05, project-map, dataset, or solved-output edits.

## Verification

| Evidence | Command |
|---|---|
| Fail-first | New regression class fails before the converter exists (record output) |
| Targeted | `python3 -m unittest tests.test_events` (existing + new, all green) |
| Owning regression | `python3 -m unittest tests.test_repository tests.test_evidence tests.test_events` |
| Compile | `python3 -m compileall -q code tests` |
| Patch hygiene | `git diff --check` |

## Stops And Handoff

- Stop if any existing WP-04 test would need modification to pass; that
  indicates a semantic change, which is out of scope.
- Do not edit `docs/wp-04-plan.md` status or add a Review Record; the fresh
  reviewer owns the acceptance record.
- Required follow-on: immediately after implementation, hand the completed
  bytes to a fresh independent `task-acceptance-review`.
- WP-05 resumes only after this correction receives fresh independent
  `ACCEPT`; then the WP-05 dependency gate is re-run on the corrected bytes.

## Pre-existing documentation gap (do not fix here, report to owner)

`docs/wp-04-plan.md:3` says "see Review Record", but the file contains no
`## Review Record` section (the status edit landed without it). The WP-04A
reviewer may append the WP-04A record; restoring the missing WP-04 record
needs its owner and is outside this correction.