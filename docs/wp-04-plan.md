# WP-04 — Lifecycle Normalization And Exact FX

Status: **READY — PREREQUISITE CORRECTION GATED**
Authority: [`master-plan.md`](master-plan.md), WP-04  
Depends on: WP-01 and accepted WP-02; the settlement-date preservation check
below must pass before implementation starts  
Readiness route: standalone guided preflight — confirm the accepted WP-02 fact
contract can represent every dated standalone cash fact

```yaml
agent_tier: standard
reasoning: medium
review: immediate
budget: 16 tool calls / 40 minutes / medium context
```

## Outcome

Implement one deterministic `buy_or_wait.events` boundary that combines a
validated `RequestCase` and its accepted `EvidenceResolution` into exactly one
source-accounted set of historical cash records, opening debit reserves, and
future dated cash effects in the profile's home currency. It must preserve
lifecycle identity, never replay settled history into opening cash, never make
an unsettled credit available, and fail closed when a required amount, pair, or
exact directed settlement-date FX rate is unavailable.

This task has no direct recommendation effect. It supplies the normalized,
non-duplicated financial inputs that WP-05 will use to build the first
replayable 90-day baseline.

## Direction Trace

- Direction contribution: normalize supplied events and accepted evidence into
  conservative home-currency effects without double counting or invented
  financial facts.
- User-observable effect: no direct effect; enables later recommendations whose
  safety calculation respects pending holds, settlement, refunds, investments,
  reimbursements, transfers, and exact FX.
- Why now: [`master-plan.md`](master-plan.md) puts mandatory WP-04 after typed
  WP-02 and before WP-05. WP-03 is optional and must not delay this path.
- Direction decisions used: [`../AGENTS.md`](../AGENTS.md),
  [`../problem_statement.md`](../problem_statement.md),
  [`initial-analysis/07-evidence-decision-pack.md`](initial-analysis/07-evidence-decision-pack.md),
  [`initial-analysis/08-financial-semantics-decisions.md`](initial-analysis/08-financial-semantics-decisions.md)
  (`FIN-001`, `FIN-006`, and `FIN-008`), and
  [`master-plan.md`](master-plan.md), sections 4–8 and WP-04.
- New direction decisions required: None.

## Authority And Scope

| Item | Contract |
|---|---|
| Product authority | [`../problem_statement.md`](../problem_statement.md) and [`../AGENTS.md`](../AGENTS.md) |
| Implementation authority | [`master-plan.md`](master-plan.md), WP-04, plus the decided FIN-MIN lifecycle and FX rules |
| Allowed product changes | New `code/buy_or_wait/events.py` only |
| Allowed evidence changes | New `tests/test_events.py`; [`project-map.md`](project-map.md) only after the module and command exist |
| Read-only upstream context | Accepted `code/buy_or_wait/domain.py`, `repository.py`, `evidence.py`, `tests/test_repository.py`, `tests/test_evidence.py`, and their accepted plan/review records |
| Input boundary | One `RequestCase` and the `EvidenceResolution` produced for that exact case; no CSV reopening and no raw message/image parsing |
| Out of scope | Recurrence discovery or amendments, variable-spend envelopes, the 90-day ledger, safe capacity, payment candidates, ranking, explanations, CSV output, provider/model work, and edits to WP-03 evaluation files |
| External requirements | None; standard library only, offline, deterministic, and no credentials or network |
| Current parallel work | WP-03 owns `code/evaluation/evidence_strategy.py`, `tests/test_evidence_strategy.py`, and its report. WP-04 must not edit or import them. |

## Prerequisite And Timing Gate

WP-02 is accepted, and WP-03 may continue independently. Before creating
`events.py`, the WP-04 implementer must perform this short gate:

1. Run `python3 -m unittest tests.test_repository tests.test_evidence` on the
   accepted WP-01/WP-02 bytes.
2. Confirm `EvidenceFact` has a structured `settlement_date: date | None` (or
   an equivalently explicit field) distinct from recurrence `effective_date`.
3. Confirm `resolve_case_evidence` preserves the date for a standalone
   `CONFIRMED_FUTURE_CREDIT`; the accepted message-11 fact must carry
   `2026-01-15` without reading private candidate tables, notes, or raw carrier
   text.
4. Confirm an event-targeted `EVENT_AMOUNT` fact exposes its exact event ID,
   amount, currency, fact ID, and carrier source IDs.
5. Confirm no active WP-03 work overlaps `events.py` or `test_events.py`.

The currently inspected accepted bytes fail items 2–3: the candidate contains
the settlement date, but the public `EvidenceFact` drops it. Stop and route a
narrow WP-02 correction with a regression for message 11 before implementing
WP-04. That correction may add the field to `domain.py`, preserve it in
`evidence.py`, and update `test_evidence.py`; it is not part of WP-04 and must
receive fresh acceptance. Do not overload `effective_date`, parse `notes`,
reach into `_MESSAGE_FACTS`, reopen `messages.csv`, or omit the credit.

If the accepted upstream shape changes in any other way, update this brief only
for the exact interface delta. Do not redesign lifecycle policy during
preflight. WP-03 completion or its selected strategy is not a prerequisite.

## Architecture

### Public boundary and result records

Add one flat, standard-library-only module:

```python
normalize_case_events(
    case: RequestCase,
    evidence: EvidenceResolution,
) -> EventNormalization
```

`normalize_case_events` is pure: it reads no files, environment, clock, model,
or global cache and performs no output write. Use immutable module-owned
dataclasses and closed enums. Exact names may follow local style, but the
public result must expose these semantic collections without requiring WP-05
to reconstruct lifecycle or FX:

```text
EventNormalization
  historical_cash: tuple[NormalizedCashRecord, ...]
  opening_reserves: tuple[NormalizedReserve, ...]
  dated_cash_effects: tuple[NormalizedCashEffect, ...]
  decisions: tuple[NormalizationDecision, ...]
  blocks_downstream: bool
```

Each normalized monetary record carries:

- one stable record ID;
- non-negative exact `amount_home: Decimal` and `home_currency`;
- `direction` for cash records/effects;
- the supplied settlement date when the source has one;
- `source_event_ids` and `source_fact_ids` as tuples; and
- the category, event type, flexibility, and minimum allowed amount needed by
  WP-05, copied from the authoritative event rather than inferred from text.

`NormalizedReserve` additionally carries the request date as `reserved_on`
and the supplied settlement date as `settlement_date`. It represents one
pending-debit obligation: WP-05 will reduce spendable cash at opening, then
release the reserve while applying the actual debit at settlement, producing
zero additional spendable-cash change. Do not also emit the same obligation as
a normal dated debit.

`NormalizationDecision` is the complete audit index. It contains a disposition
(`included`, `excluded`, `replaced`, or `unresolved`), a stable reason code,
and safe source event/fact/carrier IDs. It contains no raw description,
message text, image data, or extracted excerpt. Every supplied event and every
evidence fact must appear in at least one decision; applicable evidence
diagnostics are propagated by safe IDs/reason codes. This is the oracle for
detecting silent drops and duplicate ownership.

Introduce a feature-owned `EventNormalizationError(ValueError)` with
`reason_code` and safe `source_ids`. Raise it for an internally inconsistent or
unrepresentable input contract (for example, a missing exact FX rate). Do not
return a partial result. Grounded uncertainty such as an amount-less required
future debit is instead represented as an unresolved decision with
`blocks_downstream=True` so later output can fail conservatively.

### Deterministic normalization phases

Implement these phases in order. Preserve `case.events` order within each
result collection and append fact-only effects in `evidence.facts` order.

1. **Validate the boundary.** Require the exact public types. Build unique
   indexes for event IDs, fact IDs, and directed rate keys. Reject duplicate
   IDs, unknown/foreign fact targets, or facts whose carrier sources are not in
   this case. Copy the upstream `blocks_downstream` state; never clear it.
2. **Resolve event amounts.** A populated event amount is authoritative unless
   an accepted fact type explicitly replaces it. A blank event amount may be
   filled only by exactly one targeted `EVENT_AMOUNT` fact with matching
   currency. Multiple facts, a mismatched currency, a fact targeting a
   populated event, or a missing required future-debit amount fails closed.
   A missing amount on settled history is excluded from numeric history with
   an unresolved decision but does not by itself replay a debit or block the
   request; this preserves the accepted `image_04` boundary.
3. **Resolve lifecycle identity.** Process lifecycle links as relationships,
   not automatic netting. A failed/cancelled predecessor has no cash effect;
   its separately supplied retry/replacement is evaluated once on its own
   status. A link alone never proves a duplicate, refund, transfer, or
   replacement. A possible duplicate pending debit remains one reserve until
   explicit accepted evidence proves cancellation or duplicate identity.
4. **Classify lifecycle.** Apply the matrix below and create exactly one audit
   decision per source ownership. Never let recurrence, flexibility, category,
   or descriptive wording override status/direction.
5. **Convert exact money.** Convert every included numeric historical record,
   reserve, or dated effect to home currency. Keep the exact product without
   intermediate rounding or quantization.
6. **Check conservation.** Assert that no event/fact is silently unowned, no
   event owns more than one active cash role, no reserve is duplicated as a
   dated effect, and a neutralized pair contains exactly the two validated
   opposite-direction events. Return immutable tuples only after all checks
   pass.

### Lifecycle matrix

| Source state | Required normalized result | Required reason / guard |
|---|---|---|
| Settled cash with `settlement_date <= request_date` | One home-currency historical record; no opening or future delta | `historical_already_in_opening`; settled one-time credits never recur here |
| Pending debit | One opening reserve, retained even when described as disputed or possibly duplicate | `pending_debit_reserved`; do not emit a second dated debit |
| Pending credit | No cash record, reserve, or dated effect | `pending_credit_unavailable`; passing the predicted date does not settle it |
| Scheduled debit | One dated debit on supplied settlement date | `scheduled_debit` |
| Scheduled confirmed income | One dated credit on supplied settlement date | `scheduled_credit` |
| Failed or cancelled row | No cash effect | `failed_no_cash` or `cancelled_no_cash`; a linked retry is processed independently |
| Proven replacement/retry | Predecessor remains excluded by its status; successor appears once according to its own status | Both event IDs in decisions; link does not clone or erase the successor |
| Duplicate record / possible duplicate | Duplicate event IDs are an invalid upstream contract and fail before normalization. Distinct-ID possible duplicates remain separate obligations unless a future accepted contract supplies explicit duplicate identity. | `duplicate_event_id` or `possible_duplicate_retained`; a link, matching amount, or description alone is insufficient |
| Settled purchase plus refund | Purchase remains historical; refund is a separate credit and unavailable while pending | Never net solely because `linked_event_id` is populated |
| Investment purchase | Historical or future debit according to status and request boundary | `investment_purchase_cash` |
| Investment valuation / unrealized non-cash | No cash effect at any status | `unrealized_non_cash` |
| Settled investment sale | One cash credit, never valuation plus sale | `investment_sale_cash` |
| Work expense and reimbursement | Expense remains its own debit; reimbursement is a separate credit only when scheduled-confirmed or settled | Pending/unapproved reimbursement adds no cash |
| Validated internal transfer pair | No net cash effect for exactly one same-user, same-currency, same-amount, same-settlement-date debit/credit pair identified by an accepted `INTERNAL_TRANSFER_PAIR` fact | `internal_transfer_neutral`; reject or leave unresolved an unmatched/ambiguous pair |
| Fact-only confirmed future credit | One dated credit from its structured amount, currency, settlement date, fact ID, and carrier IDs | No recurrence; do not synthesize an `EventRecord` or reuse an anchor event amount |
| Upstream unresolved required debit | No guessed effect; `blocks_downstream=True` | Preserve upstream reason code and source IDs |

For a settled cash event whose settlement date is after the request date, stop
with an inconsistent-boundary error; do not count future cash as already
settled. Do not invent behavior for overdue scheduled rows during this task: if
one is found in the supplied corpus, stop and route the observed case to the
owner because its placement relative to opening cash is not decided here.

### Exact directed FX

Use this lookup algorithm for every included foreign-currency amount:

1. If `source_currency == home_currency`, return the source `Decimal` unchanged
   and do not require or consult a rate.
2. Otherwise require a non-null supplied settlement date.
3. Select exactly one rate by the full key
   `(settlement_date, source_currency, home_currency)`.
4. Return `source_amount * rate` exactly. Do not round, quantize, convert to
   float, chain through another currency, invert a reverse pair, or choose the
   latest/prior/nearest rate.
5. Zero matches raises `fx_rate_missing`; more than one matching key raises
   `fx_rate_conflict`; a non-positive/non-finite rate raises
   `fx_rate_invalid`. Include the event or fact ID and required key, but no raw
   carrier content.

The decisive precision oracle is:

```text
Decimal("1800") * Decimal("15833.33") == Decimal("28499994.00")
```

Numeric equality must be IDR 28,499,994 exactly; do not replace it with
28,500,000. Lexical rendering belongs to WP-08, not this task.

## Required Work

1. Complete the prerequisite gate and obtain fresh acceptance for the narrow
   WP-02 settlement-date correction if required.
2. Add fail-first `tests/test_events.py` cases using small immutable synthetic
   `RequestCase` and `EvidenceResolution` builders; keep decisive amounts,
   dates, IDs, links, and expected reason codes visible in each test.
3. Add `code/buy_or_wait/events.py` with the public pure function, immutable
   result/audit records, lifecycle matrix, exact FX lookup, and fail-closed
   error type described above.
4. Cover every lifecycle-matrix row, replacement/duplicate negative space,
   source conservation, inherited blocking state, and all FX lookup failures.
5. Add a component-level test that loads accepted participant-facing sample
   cases through `DatasetRepository`, resolves evidence through
   `resolve_case_evidence`, and normalizes them through the public WP-04 API.
   It must include request 25's exact USD-to-IDR salary and request 20's
   pending refund/debit behavior; it must not read solved output fields.
6. Update [`project-map.md`](project-map.md) with the new owner, public entry
   point, and `tests.test_events` command only after they exist and pass.
7. Inspect the final diff for overlap with active WP-03 work, then hand the
   completed bytes to a fresh independent acceptance reviewer.

## Acceptance Criteria

- **AC-01 — Complete source accounting:** every case event and accepted fact is
  traceable through safe source IDs to one included, excluded, replaced, or
  unresolved decision; no event has two active cash roles and no source is
  silently dropped.
- **AC-02 — Exact lifecycle behavior:** every FIN-006 matrix row produces the
  specified history, reserve, dated effect, exclusion, replacement, or
  unresolved result. A failed/cancelled predecessor plus retry never loses or
  duplicates the successor; a pending reserve never becomes a second debit;
  duplicate IDs fail and distinct-ID possible duplicates remain reserved.
- **AC-03 — Conservative cash boundary:** pending credits, failed/cancelled
  rows, unrealized values, and unapproved reimbursements add no cash. Required
  unknown future debits block downstream certification; missing settled-history
  amounts do not replay into opening cash or become zero-valued observations.
- **AC-04 — Exact FX:** every foreign included record uses exactly one supplied
  directed settlement-date pair and exact `Decimal` multiplication. The
  request-25 oracle equals IDR 28,499,994; wrong-date, missing, reverse-only,
  duplicate/conflicting, invalid-rate, and missing-settlement-date cases fail
  without a partial normalization result.
- **AC-05 — Transfer/refund/investment boundaries:** links alone never net cash.
  Only a fully validated transfer pair is neutral; purchase/refund and
  investment purchase/value/sale components retain their distinct authorized
  cash meanings.
- **AC-06 — Boundary preservation:** the module is deterministic,
  standard-library-only, reads no files or raw carriers, calls no provider,
  performs no recurrence/forecast/planning/output work, and does not import or
  modify WP-03 evaluation code.

### Finite-Risk Coverage Contract

| Invariant | Material dimensions/cases | Decisive oracle/boundary | Implementation evidence | Independent review probe | Gate owner |
|---|---|---|---|---|---|
| Each source owns at most one cash role | history, opening reserve, dated debit, dated credit, excluded, replaced, unresolved | Public `EventNormalization` collections plus complete decision index | Table-driven unit test for every lifecycle row and source-conservation assertion | Duplicate a pending debit into the dated list in a controlled mutation; targeted test must reject it | Implementer targeted; fresh reviewer mutation probe |
| Reserve-to-settlement is not a second debit | pending before settlement, at settlement, beyond horizon, possible duplicate | Exactly one reserve record and zero ordinary dated effects for its event | Pending-debit examples including image-05 amount and a possible-duplicate synthetic fixture | Compare spendable amount before/after simulated release-plus-settlement; net additional change is zero | Implementer targeted; fresh reviewer arithmetic probe |
| Links do not imply the wrong lifecycle | failed/cancelled retry, purchase/refund, investment purchase/value/sale, reimbursement, matched/unmatched transfer, duplicate-ID rejection, distinct-ID possible duplicate | Exact included/excluded records and source-ID decisions at public normalizer boundary | Small state-transition and pair-validation fixtures; no description-based oracle | Change only a link while holding statuses/directions fixed and confirm unrelated cash roles do not change | Implementer targeted; fresh reviewer adversarial |
| FX never guesses | home currency, exact direct pair, wrong date, missing pair, reverse-only, duplicate/conflict, invalid rate, missing settlement date | Exact amount or stable `EventNormalizationError.reason_code`; no partial result | Unit decision table plus request-25 component case | Remove the direct rate while leaving reverse/prior rates; confirm `fx_rate_missing` | Implementer targeted; fresh reviewer adversarial |
| Grounded uncertainty stays conservative | upstream blocking diagnostic, amount-less future debit, pending credit, missing historical image amount | `blocks_downstream` is monotonic; no invented amount/effect | Focused unit cases including message 10 and image 04 behavior | Flip upstream block true with otherwise empty events and confirm output remains blocked | Implementer targeted; fresh reviewer boundary probe |

## Verification

Use `unittest`; add no framework or external dependency. Unit fixtures should
construct domain records directly. The component cases may read `dataset/`
through `DatasetRepository`, but expected values must be explicit and must not
come from `sample_requests.csv` solved output columns or from the normalizer's
own implementation.

| Evidence | Scenario and oracle | Command |
|---|---|---|
| Prerequisite | Accepted repository/evidence suites pass; message 11 exposes structured settlement date `2026-01-15` | `python3 -m unittest tests.test_repository tests.test_evidence` |
| Fail-first | New focused tests fail because `buy_or_wait.events` or the required behavior does not yet exist; record the intended failure before production code | `python3 -m unittest tests.test_events` |
| Targeted | Lifecycle table, conservation, blocking propagation, exact FX, error atomicity, and request-20/request-25 component cases pass | `python3 -m unittest tests.test_events` |
| Owning regression | Accepted typed evidence and repository contracts remain green | `python3 -m unittest tests.test_repository tests.test_evidence` |
| Compile | New and owning modules compile without third-party dependencies | `python3 -m compileall -q code tests` |
| Broader gate | Fresh reviewer runs all repository tests on the final bytes, then checks patch hygiene | `python3 -m unittest discover -s tests -p 'test_*.py'` then `git diff --check` |

Execution order is prerequisite, fail-first, targeted, owning regression, and
compile. The implementer records the fail-first reason, then the exact passing
counts. The fresh independent reviewer reruns targeted and owning suites,
performs the finite-risk probes, and owns the full-suite/broader gate on the
final bytes. No live, networked, paid, performance, or cross-platform test is
needed; the relevant risks are pure state transitions, precision, provenance,
and boundary wiring.

Exit criteria: AC-01–AC-06 have passing evidence, every finite-risk row has a
recorded result, no test is skipped, the accepted WP-01/WP-02 suites remain
green, and the final source/test diff contains no WP-03 file. Passing unit
tests do not certify WP-05 forecast safety or final output correctness.

## Stops And Handoff

- Stop before WP-04 implementation until the structured standalone-fact
  settlement date is preserved by accepted WP-02 bytes.
- Stop on a red repository/evidence test, an unknown upstream public shape, or
  dirty overlap with `domain.py`, `evidence.py`, `test_evidence.py`,
  `events.py`, or `test_events.py`; identify the owner rather than combining
  corrections.
- Stop and ask the owner if the supplied corpus contains an overdue scheduled
  cash row or another lifecycle state not covered by the decided matrix.
- Stop rather than parsing descriptions/notes, inverting/chaining rates,
  choosing a nearby rate, fabricating zero, or weakening a conservative block.
- Any requested recurrence, forecast, planning, output, provider, shared
  helper, or new dependency is scope expansion and needs a separate brief.
- Preserve all pre-existing user and WP-03 work. Treat the metadata budget as a
  checkpoint.
- Next action: route the narrow WP-02 settlement-date correction and fresh
  acceptance, then run this task's standalone guided preflight and implement
  WP-04.
- Required follow-on: immediately after implementation or correction, hand the
  completed bytes to a fresh independent acceptance reviewer.
