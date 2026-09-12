# WP-01 — Domain Types And Strict Repository Loader

Status: **ACCEPTED** — final verdict ACCEPT (2026-09-12), see Review Record
Authority: [`master-plan.md`](master-plan.md), WP-01  
Depends on: WP-00 (**passed; baseline is fresh**)  
Readiness route: implementer self-preflight

```yaml
agent_tier: strong
reasoning: medium
review: immediate
budget: 12 tool calls / 35 minutes / medium context
```

## Outcome

Implement the immutable domain contract and eager, fail-fast dataset repository
used by every downstream subsystem. The repository must parse each CSV once,
validate the complete dataset before exposing cases, and assemble deterministic
per-request `RequestCase` objects without financial prediction or sample-answer
leakage.

WP-00 established the current baseline: the repository contract passes and
structural reconciliation reports 275 combined requests with valid links and
payment-option coverage. The implementer must rerun the WP-00 checks during
self-preflight and stop if the dataset fingerprint has drifted.

## Authority And Scope

| Item | Contract |
|---|---|
| Product authority | [`../problem_statement.md`](../problem_statement.md) and [`../AGENTS.md`](../AGENTS.md) |
| Implementation authority | [`master-plan.md`](master-plan.md), sections 6–8 and WP-01 |
| Allowed product changes | `code/buy_or_wait/domain.py`, `code/buy_or_wait/repository.py` |
| Allowed evidence and navigation changes | `tests/test_repository.py`, narrowly scoped test fixtures/helpers, [`project-map.md`](project-map.md), and [`diagnostics.md`](diagnostics.md) |
| Input boundary | Participant-facing files under `dataset/` only |
| Out of scope | Evidence extraction/resolution, lifecycle normalization, FX conversion, recurrence, forecasting, affordability, plan ranking, explanations, output writing, provider calls, and sample calibration |
| External requirements | No model, network, credentials, third-party dependency, or human adjudication |

## Public Contracts

### Domain records

Add immutable standard-library dataclasses in `buy_or_wait.domain` for:

- requests, profiles, events, exchange rates, and payment options;
- message and image carriers plus source references;
- the stable evidence-fact envelope;
- payments, spending changes, and output rows; and
- `RequestCase`, containing one request and its joined supporting records.

Add closed enums for every fixed domain used by those records: request scope,
request type, currency, event type, direction, status, flexibility, carrier
source type, payment method, affordability status, spending-change type, and
the evidence fact types approved in the evidence decision pack.

Use these scalar representations:

- `datetime.date` for dates;
- finite non-negative `Decimal` for money and rates;
- `None` for permitted source blanks, never zero or an empty sentinel;
- tuples for source-ordered pipe-delimited values;
- frozen sets for membership-only values; and
- original amount lexemes beside parsed payment-option values needed for exact
  later option rendering.

The evidence-fact type in WP-01 is only the immutable carrier-neutral envelope
and closed vocabulary. WP-02 owns extraction, field-combination validation,
targeting, duration, and conservative evidence resolution.

### Repository API

Expose from `buy_or_wait.repository`:

```python
DatasetRepository.from_directory(dataset_root: Path) -> DatasetRepository
DatasetRepository.load_request_case(request_id: str) -> RequestCase
DatasetRepository.iter_request_cases(
    scope: RequestScope = RequestScope.EVALUATION,
) -> Iterator[RequestCase]
```

Also expose `RepositoryValidationError`, a `ValueError` subtype containing a
stable reason code, source filename, row/field location, and safe source IDs.
Its message must not include raw message text, request text, or other sensitive
carrier content.

Repository construction validates the full dataset eagerly. Case iteration
preserves source CSV order, and repeated case access performs no additional CSV
reads. Each `RequestCase` contains only its request's profile, events, options,
messages, images, and relevant directed rates.

Sample request rows use only their eight input columns when constructing a
case. Their solved output columns must never be attached to `RequestCase` or
otherwise exposed as product input.

## Required Work

1. Define the closed enums, immutable records, source provenance, and basic
   construction invariants in `domain.py`.
2. Read all required CSVs once using `utf-8-sig` and `newline=""`; require exact
   headers and build unique indexes before returning a repository.
3. Parse and validate values, optional-field semantics, list fields, uniqueness,
   ownership, foreign keys, and cross-row structural invariants.
4. Assemble evaluation, sample, and combined request cases deterministically
   from indexes rather than rescanning files.
5. Add a small join-derived sample fixture builder for tests. It may select and
   copy relevant source rows into a temporary dataset, but must not copy solved
   output fields or hardcode expected financial decisions.
6. Update the project map and the existing `REPO-CONTRACT` diagnostic when the
   new module and focused recovery command become available.

## Validation Contract

### Scalar and row validation

- Require exact headers and every schema-required value.
- Accept only ISO `YYYY-MM-DD` dates and strict `true`/`false` booleans.
- Reject malformed, negative, `NaN`, or infinite decimals.
- Require positive counts and frequencies where the payment-option shape uses
  them, and reject values outside a closed enum.
- Require `desired_completion_date >= request_date`.
- Preserve an allowed blank as `None`; never coerce it to zero.

### Keys, links, and ownership

- Request IDs are unique across sample and evaluation inputs; every request has
  exactly one profile and the current one-request-per-user invariant holds.
- Event, option, message, image, and exchange-rate primary or compound keys are
  unique.
- Options belong to their referenced request.
- Populated message/image request and event links resolve and belong to the
  same user as the carrier.
- Lifecycle `linked_event_id` values resolve within the same user and cannot
  self-link.
- A blank message request link remains blank in provenance but joins to the
  carrier user's unique request for case assembly.
- Directed exchange-rate keys are unique by date, source currency, and target
  currency. Rate selection and missing-rate policy remain WP-04 behavior.

### Profiles, events, and images

- Parse pipe-delimited profile fields without empty or duplicate tokens.
- Validate payment methods and observed category domains. A protected category
  cannot also be reducible or stoppable.
- A blank `max_installment_months` is valid only when the profile does not
  consider installments; a profile considering installments must have a
  positive populated cap.
- Every blank event amount has exactly one image link, every image links to a
  blank-amount event, and no blank amount is treated as zero.
- A blank settlement date is permitted only for an unrealized non-cash
  valuation.
- `reducible` and `reducible_or_stoppable` events require a non-negative
  `minimum_allowed_amount` no greater than the event amount; the other
  flexibility modes require that field to be blank.

### Payment options

- Every request has exactly one full-payment option.
- A full-payment option has one payment, no frequency, zero financing fee, the
  request amount as both payment and total, and the request date as its first
  payment date.
- An installment option has more than one payment and a positive frequency.
- For every option,
  `payment_amount * number_of_payments == total_payable_amount` using exact
  decimal arithmetic.
- `financing_fee` is supplied metadata already reflected in the option total;
  do not add it again during arithmetic validation.
- Deadline, preference, installment-cap eligibility, safety, and ranking are
  intentionally deferred to the planning subsystem.

## Acceptance Criteria

- **AC-01 — Complete deterministic loading:** all 275 combined requests load in
  source order into independent cases, each with one profile and only correctly
  owned supporting records. Multiple case reads do not reopen any CSV.
- **AC-02 — Sample isolation:** a sample case is assembled through source joins
  without unrelated-user records or any solved output field in product inputs.
- **AC-03 — Exact parsing:** dates, booleans, enums, optional blanks, and exact
  decimals reach the documented domain representations without float use or
  blank-to-zero coercion.
- **AC-04 — Fail-fast integrity:** malformed values, missing required fields,
  duplicate keys, unknown links, wrong-user links, invalid blank/image
  relationships, and invalid option arithmetic fail before any case is exposed.
- **AC-05 — Boundary preservation:** the package performs no financial
  inference, evidence resolution, FX conversion, forecast, recommendation, or
  output write.

## Test Plan

Add `tests.test_repository` using a join-derived sample fixture and minimized
temporary-dataset mutations. The tests must prove the positive full-dataset
path and explicitly reject:

- malformed, missing, negative, `NaN`, infinite, boolean, date, integer, and
  enum values;
- duplicate IDs or rate keys, unknown links, self/dangling lifecycle links,
  and wrong-user request/event links;
- invalid pipe lists, category conflicts, and installment-cap inconsistencies;
- invalid option totals or full-payment shapes; and
- unmatched or multiply matched blank-event/image links.

Assert deterministic, redacted `RepositoryValidationError` reason codes for
each failure family.

Run verification in this order:

1. `python3 -m unittest tests.test_repository`
2. `python3 -m unittest tests.test_repository_contract`
3. `python3 -m compileall -q code tests`
4. `python3 -m unittest discover -s tests -p 'test_*.py'`
5. `git diff --check`

## Review Record

Independent acceptance review of the corrected bytes (2026-09-12): reviewer
regressions F-01/F-02/F-03 pass; AC-01–AC-05 verified; 50-test suite and all
gates green. Non-blocking P3 findings recorded for the next implementation
thread:

- **F-04** — Blank required date/boolean fields (`request_date`, `event_date`,
  `rate_date`, `allows_partial_payment`) surface as `invalid_date` /
  `invalid_boolean` instead of `missing_required_value` because `_require`
  runs inside the parse `try` in `_parse_date_field` / `_parse_bool_field`
  (repository.py). Raise the missing-value reason code before parsing.
- **F-05** — Dead code `_dedupe` in `code/buy_or_wait/repository.py`; remove.
- **F-06** — Eight carrier/image/message failure tests in
  `tests/test_repository.py` skip on the default fixture (user_01 has no
  messages or images); independently probed but untested in the suite.
  Consider fixture coverage.

Resolved 2026-09-12 in the maintainability pass: F-05 (dead `_dedupe`
removed, duplicated `@staticmethod` fixed) and F-06 (fixture now selects a
sample user with messages, images, and a blank image-linked event, so the
carrier failure tests run instead of skipping). F-04 remains open.

### Final Verdict — ACCEPT (2026-09-12)

Fresh independent acceptance review of the corrected bytes: F-07 (fixture still
selected user_01, 8 carrier tests skipping despite the F-06 resolution claim)
was raised and resolved — the fixture now join-derives a carrier-bearing target
(request_03/user_03) plus a foreign-user secondary sample for cross-user link
tests. Follow-up test regressions (stale completion-date mutation; unknown
foreign request link) were corrected with derived dates and a known foreign
request. Re-review evidence: full discover 50 tests OK (skipped=1, legitimate —
user_03 has one blank event), `test_repository_contract` 4 OK, `compileall`
clean, `git diff --check` clean, adversarial probes (two-user fixture load,
carrier case assembly, duplicate keys, link ownership, option shape, sample
isolation) all pass. AC-01–AC-05 satisfied; F-04 remains the sole open P3,
tracked for the next implementation thread and non-blocking. WP-01 is accepted
and may advance.

## Stops And Handoff

- Stop on dataset fingerprint drift and reconcile WP-00 before continuing.
- Stop for ambiguous authority, user-work overlap, unsafe permission needs, a
  required new dependency, or validation behavior that would invent financial
  semantics.
- Do not expand this task to fix malformed participant data or implement later
  work packages.
- Preserve existing user work and treat the metadata budget as a soft
  checkpoint.
- Next action: none — WP-01 accepted. Proceed to the next work package.
- Required follow-on: carry open F-04 into the next work package's brief.
- Required follow-on: immediately after implementation or correction, hand the
  completed bytes to a fresh independent acceptance reviewer.
