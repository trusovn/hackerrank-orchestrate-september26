# Buy or Wait? — Master Implementation Plan

Status: **READY FOR TASK DECOMPOSITION**  
Plan date: 2026-09-12  
Delivery mode: deadline-aware MVP, then measured extensions  
Runtime shape: offline-capable Python batch CLI

## 1. Purpose And Authority

This is the execution plan for turning the current scaffold and completed
initial-analysis packet into the required submission. It is deliberately more
operational than a product requirements document: future agents should be able
to extract bounded implementation tasks from it without reopening settled
product decisions.

Use sources in this order:

1. [`../AGENTS.md`](../AGENTS.md) for security, logging, challenge, and output
   invariants.
2. [`../problem_statement.md`](../problem_statement.md) for authoritative
   product behavior and evaluation rules.
3. [`project-map.md`](project-map.md) for current paths, commands, and placement.
4. [`initial-analysis/README.md`](initial-analysis/README.md) and its canonical
   numbered documents for observed data facts, selected conservative rules,
   and bounded experiments.
5. This plan for implementation order, subsystem ownership, delivery gates,
   and task boundaries.

If this plan conflicts with a higher source, correct the plan. Lower-authority
supplemental notes under `docs/initial-analysis/` remain experiment leads only.

## 2. Critical Read And Recommendation

**Working interpretation.** Build a deterministic financial decision engine
that may use AI only to turn untrusted messages or images into validated facts,
then generate a contract-valid `output.csv` for all 250 evaluation requests.

**Biggest upside.** The corpus is small, structurally consistent, and backed by
25 solved examples. A traceable deterministic engine can be calibrated quickly,
replayed cheaply, and extended without making model behavior responsible for
money arithmetic or safety.

**Primary failure path.** A polished architecture with the wrong recurrence,
variable-spending, income-continuation, lifecycle, or date policy will score
poorly. The implementation must expose those policies in reproducible sample
traces and bounded experiments before spending time on provider integrations.

**Secondary failure paths.** The solution can also fail by accepting malformed
evidence, double-counting settled or pending events, choosing ineligible offers,
serializing inconsistent fields, producing incomplete output, or leaving too
little time for the final run and package inspection.

**Recommendation.** Proceed with guardrails: build the smallest complete
deterministic vertical path first, make every financial result replayable, run
only the five finite policy experiments already authorized, and retain an
offline conservative fallback at every evidence boundary. Do not build a
general rules engine, web service, database, generic plugin system, or model-led
recommendation agent.

## 3. Definition Of Done

### 3.1 Submission-ready MVP

The MVP is complete only when all of the following are true:

- `python3 code/main.py` reads participant-facing inputs from `dataset/` and
  atomically writes root `output.csv`.
- The output has exactly the eight required ordered columns and one unique row
  for every evaluation `request_id`, with no sample rows or extras.
- Every row passes schema, domain, cross-field, eligibility, deadline, action,
  option-match, and independent 90-day safety validation.
- The 25 solved samples produce a complete metric and mismatch report with zero
  contract and deterministic safety-fixture failures. Every prediction mismatch
  has a named policy/evidence cause; there are no request-ID special cases.
- All accepted plans preserve `minimum_balance_to_keep` after every relevant
  debit and payment checkpoint through the fixed forecast horizon.
- The final full-dataset run completes without unresolved fatal errors. Any
  conservative no-recommendation caused by unbounded evidence is explicit in
  its trace and explanation.
- `code/evaluation/usage_report.md` describes the actual final run, including
  zero model calls if no provider is retained.
- `code.zip`, root `output.csv`, and the required transcript are present and
  inspected; the ZIP contains the runnable code and `evaluation/usage_report.md`
  without credentials or private runtime artifacts.

### 3.2 Quality target, not a false gate

Aim for exact public-sample matches in categorical fields, plans, changes,
amounts, and dates. The organizer's hidden weights and tolerances are unknown,
so do not invent a percentage acceptance threshold. Prefer a conservative,
globally consistent policy over a request-specific patch that raises the public
match count.

## 4. Scope And Priority

### P0 — must ship

- Exact CSV loading, joins, types, and validation.
- Validated message/image fact boundary with conservative failure behavior.
- Event lifecycle normalization and exact directed settlement-date FX.
- Supported recurrence, variable-spending projection, and 90-day ledger.
- Safe-today capacity and earliest-full-payment calculation.
- Eligible plan and spending-change enumeration, safety replay, and ranking.
- Deterministic explanation, final row validation, CSV writing, and CLI wiring.
- Public-sample evaluation, final 250-request run, usage report, ZIP inspection,
  and transcript/submission checks.

### P1 — only after the complete deterministic path works

- A provider-backed message or image extractor when it measurably improves the
  accepted evidence oracle over deterministic parsing.
- Validated extraction caching keyed by carrier hash and extractor/config
  version.
- Performance improvements shown necessary by the full-dataset run.
- More nuanced deterministic explanations if trace consistency already passes.

### Out of scope for this challenge delivery

- Real payment execution, live banking, market, or exchange-rate access.
- Asset-price prediction or security recommendations.
- API server, UI, datastore, migrations, background jobs, or distributed state.
- Generic financial-rule DSL, dependency-injection framework, or speculative
  plugin architecture.
- CI, containers, lint/type tooling, or third-party dependencies unless a
  concrete retained implementation cannot work safely without them.

## 5. Target System Shape

```text
dataset CSVs/images
        |
        v
validated RequestCase + source provenance
        |
        v
validated evidence facts ---- optional ModelProvider ---- usage telemetry
        |
        v
normalized lifecycle events + exact home-currency amounts
        |
        v
supported recurrence / variable-spend projections
        |
        v
baseline 90-day ledger + replayable trace
        |
        +--> safe amount today / baseline earliest full-payment date
        |
        v
eligible plan + spending-change candidates
        |
        v
independent safety replay -> deterministic ranking -> explanation
        |
        v
output-row validator -> atomic root output.csv
        |
        +--> public-sample metrics / mismatch report / usage report
```

The data flowing between boxes is validated and typed. Raw provider text,
message text, and image content cannot reach the ledger, plan selector, or CSV
writer directly.

## 6. Subsystem Boundaries And Placement

Create files only when their owning task begins. Keep a file flat while its
responsibility remains small; do not pre-create empty layers.

| Subsystem | Proposed owner | Responsibility | Must not own |
|---|---|---|---|
| Domain contract | `code/buy_or_wait/domain.py` | Exact decimals, dates, enums, immutable input/fact/forecast/plan/output records | CSV I/O, provider calls, ranking policy |
| Dataset repository | `code/buy_or_wait/repository.py` | Load CSVs, validate rows and joins, build one `RequestCase`, preserve provenance | Financial inference, output decisions |
| Evidence | `code/buy_or_wait/evidence.py` | Typed facts, message/image extraction validation, target resolution, conservative unresolved states | Affordability arithmetic or plan choice |
| Lifecycle and FX | `code/buy_or_wait/events.py` | Status/link resolution, pending reserves, cash/non-cash effects, exact directed conversion | Recurrence discovery or candidate ranking |
| Forecast | `code/buy_or_wait/forecast.py` | Series identity, recurrence policies, variable envelopes, dated baseline ledger and traces | User-method eligibility or output formatting |
| Safety and planning | `code/buy_or_wait/planning.py` | Safe amount, earliest date, candidate creation, changes, safety replay, deterministic ranking | Raw evidence parsing or CSV writing |
| Output | `code/buy_or_wait/output.py` | Explanation from trace, row validator, exact serialization, atomic writer | Forecast policy or provider access |
| Composition | `code/buy_or_wait/pipeline.py`, `code/main.py` | Wire one request and one batch; select explicit policy config; collect diagnostics/usage | Reimplement subsystem logic |
| Evaluation | `code/evaluation/main.py` | Run sample mode, compare fields, group mismatches, summarize optimism risk and usage | Hidden-label fitting or production decisions |
| Tests | mirrored `tests/test_*.py`; concrete fixtures only under `tests/fixtures/` | Behavior, boundary, regression, and public-sample evidence | Live provider calls in ordinary tests |

Keep the existing `buy_or_wait.ai_boundary.ModelProvider` seam. Add a provider
adapter only after the evidence strategy gate in Work Package 03. Shared helper
modules are justified only after two real owners need the same behavior.

## 7. Stable Internal Contracts

These are semantic contracts, not mandates for exact class names.

| Boundary | Input | Output | Failure behavior |
|---|---|---|---|
| Repository | dataset root and request row | fully joined `RequestCase` with source IDs | reject malformed or inconsistent supplied data before forecasting |
| Evidence resolver | one carrier plus minimal linkage context | zero or more validated typed facts plus provenance | unresolved credit adds no cash; unbounded required debit blocks certification |
| Event normalizer | case events plus validated facts and rates | normalized cash effects/reserves in home currency | no inverse/latest-prior FX guess; no amount-as-zero fallback |
| Forecast builder | normalized history, explicit future effects, policy config | dated baseline checkpoints and inference trace | each source belongs to at most one projection family |
| Safety evaluator | baseline, proposed payments, optional changes | safe/unsafe result and minimum-balance checkpoint | replay whole fixed horizon; never trust candidate construction alone |
| Planner | case, baseline measures, candidate inputs | eligible candidates and one ranked recommendation | empty candidate set yields contract-consistent `not_recommended` |
| Output validator | recommendation, source case, independent replay | validated output row | reject writing the entire batch if any row is invalid |

All diagnostic records should carry `run_id`, `request_id`, stage, stable reason
code, and source IDs. Do not log raw sensitive carrier content by default.

## 8. Dependency-Ordered Work Packages

Each package below can become one or more implementation task briefs. Split a
package when one task would touch more than one primary subsystem or cannot be
verified with its focused command.

### WP-00 — Freeze the reproducible baseline

**Goal:** Ensure planning assumptions still describe the input before product
code depends on them.

**Task candidates**

1. Re-run the dataset/repository contract and structural reconciliation tool.
2. Record the current dataset fingerprint in evaluation-run metadata rather
   than duplicating it in product code.

**Acceptance**

- Dataset counts, links, image coverage, and option arithmetic still match the
  canonical analysis packet.
- The recorded fingerprint can identify later input drift without changing or
  copying participant data.

**Focused verification:** `python3 -m unittest tests.test_repository_contract`

**Stop signal:** a fingerprint or contract mismatch makes the analysis stale;
reconcile that exact mismatch before continuing.

### WP-01 — Domain types and strict repository loader

**Depends on:** WP-00

**Goal:** Create the single validated data shape every downstream subsystem
uses.

**Task candidates**

1. Define closed enums and immutable records for requests, profiles, events,
   rates, payment options, evidence facts, payments, changes, and output rows.
2. Parse dates and finite non-negative `Decimal` values; distinguish blank from
   zero and preserve source lexical values where exact rendering needs them.
3. Load each CSV once, validate required headers/domains/foreign keys, and
   expose `load_request_case(request_id)` plus deterministic batch iteration.
4. Validate method/category lists, blank installment-cap semantics, option
   arithmetic, and blank-event/image linkage.
5. Create a tiny sample-case fixture builder that selects records by joins, not
   by hardcoded expected decisions.

**Acceptance**

- All 275 combined requests load into independent cases with one matching
  profile, events, options, and linked evidence.
- A sample case can be assembled without loading unrelated users into a model
  or embedding solved outputs in product inputs.
- Malformed date/decimal/enum, unknown link, duplicate key, wrong-user link,
  missing required value, and invalid option total fixtures fail explicitly.
- No financial prediction is made in this package.

**Focused verification:** `python3 -m unittest tests.test_repository`

### WP-02 — Typed evidence and conservative resolution

**Depends on:** WP-01

**Goal:** Convert only grounded carrier content into validated facts.

**Task candidates**

1. Implement the closed evidence fact vocabulary and carrier/link/schema
   validator from the evidence decision pack.
2. Encode the 17 sample-message expected facts and 16 image adjudications as
   test fixtures or validated extracted-fact data, never as affordability
   answers. Preserve `image_04` as unresolved.
3. Implement exact-target and unique-series targeting with next-only,
   recurring, stop, resume, replacement, one-time, unavailable, and non-cash
   duration semantics.
4. Classify the remaining messages by normalized template in bounded batches;
   emit explicit ignored facts and unresolved diagnostics.
5. Add malformed, missing-field, wrong-currency, unknown-ID, multiple-total,
   empty-output, and provider-error fixtures.

**Acceptance**

- Every current message and image ends in a validated fact set or an explicit
  conservative unresolved state; none silently becomes zero or invented cash.
- The 17 sample messages match the evidence decision pack exactly.
- Fifteen images produce the selected context-appropriate value; `image_04`
  remains unavailable to amount-dependent forecasting.
- Embedded instructions cannot affect policy, output, or side effects.

**Focused verification:** `python3 -m unittest tests.test_evidence`

### WP-03 — Evidence strategy gate

**Depends on:** WP-02

**Goal:** Decide the cheapest reliable extraction path without blocking the
deterministic engine.

**Decision procedure**

1. Measure deterministic template/layout parsing against the accepted evidence
   oracle.
2. If it covers the current corpus with the required conservative outcomes,
   keep the final production path offline and record zero model calls.
3. If material carriers remain unresolved, add one operation-specific adapter
   behind `ModelProvider`, one strict response validator, bounded failure
   handling, telemetry, and content-hash caching.
4. Retain the adapter only when it increases validated coverage without
   introducing an incorrect optimistic fact. Do not ask a model for an
   affordability decision or send a complete ledger.

**Acceptance**

- The selected path and rejected alternative are recorded in evaluation
  metadata.
- Ordinary tests use `FakeModelProvider` only and pass offline.
- Provider absence/failure has a deterministic per-carrier outcome and cannot
  produce a partial or duplicate output batch.

**Focused verification:**
`python3 -m unittest tests.test_ai_boundary tests.test_evidence`

This gate may be deferred until after WP-08 if the offline evidence path lets
the end-to-end MVP proceed.

### WP-04 — Lifecycle normalization and exact FX

**Status:** ACCEPTED (2026-09-12) — `code/buy_or_wait/events.py` and
`tests/test_events.py`; `python3 -m unittest tests.test_events` (54 OK); full
suite 173 OK. See Review Record in the WP-04 plan.

**Depends on:** WP-01 and the typed-fact portion of WP-02

**Goal:** Produce one non-duplicated set of cash effects and reserves in home
currency.

**Task candidates**

1. Implement the FIN-006 lifecycle/status matrix, including retry,
   replacement, refund, possible duplicate, investment, reimbursement, and
   internal-transfer boundaries.
2. Reserve pending debits at opening and convert reserve to settlement without
   a second debit; exclude pending credits, failed/cancelled events, and
   unrealized value.
3. Convert foreign events with exact `Decimal` multiplication using only the
   supplied directed pair on settlement date.
4. Attach source/fact IDs and reason codes to every included, excluded,
   replaced, or unresolved effect.

**Acceptance**

- One fixture per lifecycle row in the FIN-MIN matrix passes.
- USD 1,800 at 15,833.33 produces exactly IDR 28,499,994.
- Wrong-date, missing, reverse-only, and conflicting-rate fixtures fail rather
  than guessing.
- Historical settled rows never replay into opening cash.

**Focused verification:** `python3 -m unittest tests.test_events`

### WP-05 — Recurrence, variable spending, and baseline ledger

**Depends on:** WP-02 and WP-04

**Goal:** Build a reproducible 90-day baseline with explicit policy choices and
no source double counting.

**Task candidates**

1. Implement strict series identity and supported monthly/month-end and exact
   7/14-day cadence detection with at least three settled observations, plus
   explicit recurrence facts.
2. Apply endings, next-only changes, amount/date amendments, explicit future
   occurrence replacement, and unique-series targeting.
3. Implement fixed recurring debit/income projection and the V0 variable
   complete-month category envelope with I0 income continuation.
4. Build dated checkpoints for request date through day +90 inclusive, with
   debit-before-credit fallback and payment after dated settlements.
5. Emit a compact trace: series observations, inclusion/exclusion reason,
   projected occurrence, reserve, checkpoint delta, balance, and minimum
   headroom.
6. Add the finite policy configuration points required by EXP-RV and EXP-DATE;
   do not create a generic rule engine.

**Acceptance**

- Every source event belongs to at most one explicit or inferred forecast
  family.
- A supplied occurrence replaces its matching inferred slot; unrelated pending
  obligations remain additive.
- Ended income, one-time credit, refund, reimbursement, arrears, and unrealized
  value do not recur.
- Missing material debits propagate the documented unresolved state.
- Synthetic month-end, leap/year boundary, day-90, same-day, stop, and
  next-only fixtures pass.

**Focused verification:** `python3 -m unittest tests.test_forecast`

### WP-06 — Capacity and independent safety replay

**Depends on:** WP-05

**Goal:** Make the two preference-independent capacity fields exact and make
every later candidate independently replayable.

**Task candidates**

1. Compute safe-today capacity as the minimum baseline headroom, capped to the
   request and floored only at the output unit.
2. Search every date from request date through day +90 for the first safe
   standalone full payment, independent of methods, changes, and deadline.
3. Implement reusable full-horizon replay for arbitrary payment schedules and
   allowed spending changes.
4. Report the exact first failing checkpoint and reason for unsafe candidates.

**Acceptance**

- `amount_safe_to_pay` remains in `[0, requested_amount]` and is not changed by
  user method preferences or optional-change enumeration.
- `earliest_date_for_full_payment` may be today, after the deadline, or empty
  exactly as the contract permits.
- A later search never ignores an earlier baseline breach.
- Boundary/property fixtures cover full, wait, and the prescribed partial
  trajectory equivalence.

**Focused verification:** `python3 -m unittest tests.test_planning.CapacityTests`

### WP-07 — Candidate plans, spending changes, and ranking

**Status:** ACCEPTED (2026-09-13) — `code/buy_or_wait/planning.py` and
`tests/test_planning.py`; `python3 -m unittest tests.test_planning` (47 OK);
full suite 302 OK. See Review Records in the WP-07 plan.

**Depends on:** WP-06

**Goal:** Enumerate all and only eligible candidates, replay them, and choose
the deterministic winner.

**Task candidates**

1. Generate full-now, wait, two-payment partial, and exact supplied installment
   schedules with all method, request, cap, deadline, and horizon gates.
2. Generate no-change candidates first, then permitted stop/floor-reduction
   sets of one to three distinct recurring series.
3. Validate protected/category/flexibility/floor rules and prevent duplicate
   series or stop/reduce conflicts.
4. Replay every candidate through WP-06 and reject unsafe, late, incomplete, or
   unmatched candidates.
5. Apply the published ranking, then only the documented deterministic residual
   tie-breakers; derive status and method from the winning candidate table.

**Acceptance**

- Installment schedules exactly match a supplied option and valid count/date
  constraints; no offer is resized or invented.
- Partial contains exactly safe-today plus the remainder at baseline earliest
  and is eligible only under every stated gate.
- Baseline capacity fields remain unchanged when a changed candidate wins.
- The three public change cases and synthetic no-method, late-only,
  changed-wait, equal-offer, protected, floor, and pending-debit cases pass.

**Focused verification:** `python3 -m unittest tests.test_planning`

### WP-08 — Output row, explanation, and atomic writer

**Depends on:** WP-06 and WP-07

**Goal:** Prevent any internally invalid recommendation from reaching
`output.csv`.

**Task candidates**

1. Generate concise explanations from validated traces and a small template per
   recommendation class; cite only supplied or derived facts.
2. Implement exact amount/date/plan/action serialization and parse-round-trip
   tests.
3. Implement the complete independent output validator from FIN-MIN, including
   row coverage, cross-field consistency, option/action validity, and safety
   replay.
4. Write to a temporary sibling file, validate the complete batch, then replace
   root `output.csv` atomically.

**Acceptance**

- Every invalid field and cross-field combination has a rejecting fixture.
- Explanations never assert settled income, known totals, met deadlines, or
  insufficient funds unless the trace supports the claim.
- Failed validation leaves no partially replaced final output.
- A CSV parse/write/parse round trip preserves every value and required header.

**Focused verification:** `python3 -m unittest tests.test_output`

### WP-09 — Public-sample oracle and bounded calibration

**Depends on:** WP-02 through WP-08

**Goal:** Measure the whole system and resolve only the finite policy questions
that can materially improve a global, contract-valid rule.

**Task candidates**

1. Implement sample-mode prediction without mixing solved output columns into
   product inputs.
2. Produce one compact trace per sample and compare status, method, amount,
   earliest date, raw/semantic plan, changes, and explanation consistency.
3. Report invariant failures, confusion tables, normalized money residuals,
   date residuals, scenario breakdowns, and optimism signals.
4. Run exactly EXP-RV (maximum 12 configurations), EXP-DATE (maximum 4),
   EXP-NUM (2), EXP-CAP (2), and EXP-CHANGE (6 scoped replays).
5. Select one global policy per experiment using the recorded stop rules. A tie
   keeps the conservative default; do not widen a sweep or add request-specific
   exceptions.

**Acceptance**

- All 25 sample rows are reported and every mismatch maps to a policy,
  evidence, eligibility, arithmetic, or formatting reason.
- Contract and deterministic safety-fixture failure counts are zero.
- Promoted policies improve reproducible evidence without unexplained new
  optimistic failures.
- The chosen configuration is explicit and used identically by sample and
  evaluation runs.

**Focused verification:** `python3 code/evaluation/main.py`

### WP-10 — Batch composition, diagnostics, and full-dataset run

**Depends on:** WP-08 and the selected WP-09 configuration

**Goal:** Run all evaluation requests once through the same validated pipeline.

**Task candidates**

1. Wire `pipeline.py` and keep `code/main.py` to argument/default-path parsing,
   composition, one run ID, and final exit status.
2. Process request cases deterministically and accumulate validated rows before
   the single output write.
3. Record per-stage reason counts and safe provider metadata without raw
   sensitive content.
4. Generate the actual usage totals for the final successful run.

**Acceptance**

- A clean run writes exactly 250 unique rows in request-file order.
- Repeated runs with identical inputs/config produce byte-identical financial
  fields and no duplicate usage/output records.
- A request failure identifies request/stage/reason and prevents a misleading
  partially valid final file.
- Runtime and validation complete within the available local deadline budget.

**Focused verification:** `python3 code/main.py`

### WP-11 — Submission package and release gate

**Depends on:** WP-10

**Goal:** Produce and inspect all three required artifacts while preserving a
submission buffer.

**Task candidates**

1. Finalize `code/evaluation/usage_report.md` from the exact run that produced
   root `output.csv`.
2. Re-run the output validator against the on-disk file and the current
   `dataset/requests.csv`.
3. Build `code.zip` with the runnable solution, prompts/configuration if any,
   README, and `evaluation/`; exclude secrets, caches, bytecode, logs, and
   unrelated development artifacts.
4. Inspect ZIP paths/content, preserve the append-only transcript as the
   required chat artifact, and perform the final submission checklist.

**Acceptance**

- Usage counts/costs reconcile with retained call metadata; a no-model run says
  so explicitly rather than fabricating usage.
- ZIP extraction in a temporary directory can run the documented command with
  the expected dataset placement.
- Full tests and patch hygiene pass; credentials and sensitive carrier content
  are absent from the package.
- `code.zip`, `output.csv`, and the transcript are ready before the submission
  buffer begins.

**Focused verification:** package inspection plus the release commands in
Section 11.

## 9. Delivery Sequence And Deadline Budget

At plan creation, approximately 6 hours 20 minutes remained. Treat the
following as hard timeboxes from the start of implementation, not estimates to
expand automatically:

| Elapsed implementation time | Required outcome | Cut rule |
|---|---|---|
| 0:00–0:35 | WP-00/01: cases load and fail correctly | Skip convenience APIs and extra type abstraction |
| 0:35–1:20 | WP-02/04: evidence, lifecycle, and FX facts are deterministic | Defer real provider; use validated offline facts/fallbacks |
| 1:20–2:40 | WP-05/06: one replayable baseline and capacity path | Keep documented starting policies; no calibration sweep yet |
| 2:40–3:40 | WP-07/08: complete recommendation and valid CSV row | Defer explanation polish and nonessential diagnostics |
| 3:40–4:45 | WP-09: all 25 samples measured; bounded high-value experiments only | Stop any sweep at its declared cap; preserve global fallback |
| 4:45–5:25 | WP-10: final 250-request run and usage report | No new architecture or model integration |
| 5:25 onward | WP-11: package, verify, inspect, and submit | Fix only release-blocking contract/safety/package defects |

The mandatory sequence is WP-00 -> WP-01 -> typed WP-02 -> WP-04 -> WP-05 ->
WP-06 -> WP-07 -> WP-08 -> WP-09 -> WP-10 -> WP-11. WP-03 is an optional gate
that must not delay the first complete deterministic run.

After WP-01 stabilizes the domain contract, separate agents may work on
non-overlapping files for evidence fixtures, lifecycle fixtures, and evaluation
reporting. Do not parallelize changes to shared domain records, forecast policy,
or ranking until their upstream contract is merged and verified.

## 10. Risk Register And Stop Rules

| Risk | Early signal | Response |
|---|---|---|
| Recurrence/variable policy is too optimistic | positive amount residuals, earlier dates, new affordability on public samples | run bounded EXP-RV; retain conservative default on a tradeoff/tie |
| Income projection is invented | credit lacks an explicit occurrence or accepted ongoing series trace | remove the credit; never repair with a buffer or request exception |
| Double counting | one source ID appears in explicit and inferred effects or pending reserve/debit | reject the forecast and fix ownership/replacement logic |
| Evidence is ambiguous | multiple targets/totals survive validation | no new credit; block certification for an unbounded required debit |
| Optional changes distort baseline fields | safe amount/earliest changes when candidate enumeration toggles | separate immutable baseline from changed candidate replay |
| Public-fit overfitting | policy branches on request/user ID or unexplained descriptions | delete the exception; use only global evidenced features |
| Provider threatens delivery | missing credentials, network, validation, cost, or retry uncertainty | ship offline path and zero-call usage report |
| Architecture consumes deadline | empty layers, generic registries, duplicated helpers | collapse to the owning module and current concrete caller |
| Final artifact is invalid | row/header mismatch, partial write, missing usage report, bad ZIP path | freeze feature work and execute WP-11 only |

Stop and ask the owner only if a new higher-authority product choice would
materially change output behavior and neither the problem statement nor the
documented conservative fallback resolves it. Missing organizer scoring detail,
provider availability, or exact public-match certainty does not block the MVP.

## 11. Verification Ladder

Run one focused command after each package. After the first complete row, expand
progressively:

1. Focused owner test named in the work package.
2. `python3 -m compileall -q code tests`
3. `python3 -m unittest discover -s tests -p 'test_*.py'`
4. `python3 code/evaluation/main.py`
5. `python3 code/main.py`
6. Revalidate root `output.csv` with the production validator.
7. `git diff --check`
8. Inspect `code.zip` contents and perform a clean temporary extraction/run.

Do not run live-provider tests, broad policy sweeps, downloads, or expensive
checks without an explicit need and budget. Ordinary unit tests remain offline
and deterministic.

## 12. How To Turn This Plan Into Task Briefs

After completing the WP-00 freshness gate, create task briefs in dependency
order starting with WP-01. Each brief should contain:

- one outcome and one primary owning subsystem;
- authority links and the exact FIN/EV/EXP rules it implements;
- in-scope and explicit out-of-scope behavior;
- concrete source/test files allowed to change;
- observable acceptance criteria, including negative cases;
- one focused verification command and the next broader gate;
- upstream dependencies and the stable input/output contract;
- failure reason/diagnostic expectations;
- whether a model, human action, network, or credentials are required; and
- a stop condition that prevents guessing or scope expansion.

Prefer one brief per numbered task candidate. Combine adjacent candidates only
when they share the same owner, files, and focused verification. Do not assign
two agents overlapping ownership of `domain.py`, `forecast.py`, or
`planning.py` concurrently.

## 13. Immediate Next Steps For The Owner

1. Execute the short WP-00 freshness gate before authoring behavior tasks.
2. Create the WP-01 task brief: domain types, strict loader, and joined
   sample-case fixture builder, with no financial behavior.
3. Queue WP-02 evidence-schema and WP-04 lifecycle/FX briefs behind the stable
   WP-01 contract; identify their non-overlapping files and fixtures.
4. Reserve the final 55 minutes for WP-11 now. Do not spend that buffer on
   provider work or extra sample-policy search.
5. After the first complete sample row passes independent validation, create
   the remaining briefs from WP-05 through WP-11 in order and track each gate
   in a short checklist.
6. If schedule slips, cut P1 work first, then explanation polish and extra
   diagnostics. Do not cut output validation, safety replay, the full-dataset
   run, usage reporting, ZIP inspection, or submission time.

The first implementation brief should therefore be WP-01, not the forecast
engine. WP-00 is a short freshness gate; WP-01 establishes the reproducible
case boundary every later task can use without repeating repository-wide
discovery.
