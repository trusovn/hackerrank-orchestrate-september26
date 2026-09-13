# WP-08 — Output Row, Explanation, Validation, And Atomic Writer

Status: **COMPLETE — WP-08A, WP-08B, AND WP-08C ACCEPTED (2026-09-13)**

Authority: [`master-plan.md`](master-plan.md), WP-08; governed by
[`../problem_statement.md`](../problem_statement.md), especially Required
Output through Choosing Between Safe Plans, and by
[`initial-analysis/08-financial-semantics-decisions.md`](initial-analysis/08-financial-semantics-decisions.md),
especially FX, Arithmetic, And Serialization; Complete Status And Method
Decision Table; and Output Validation And Public-Sample Metrics.

## Why WP-08 Is Split

The full package is approximately **35 tool calls / 105 minutes / large
context**. It combines three separately falsifiable concerns: building and
rendering a typed row, independently validating its financial and cross-field
meaning, and preserving an existing file across batch/write failures. The
unsplit estimate exceeds the user's 15-call and 45-minute thresholds.

WP-08 is split without changing total scope:

1. **WP-08A:** typed output row, grounded explanation, and canonical field
   codecs — 12 calls / 35 minutes.
2. **WP-08B:** independent single-row financial and contract validator — 13
   calls / 45 minutes.
3. **WP-08C:** complete-batch validation and atomic CSV replacement — 10 calls
   / 25 minutes.

Run the parts sequentially because all three own `output.py` and
`tests/test_output.py`. Do not assign them concurrently.

## Direction Trace

- Direction contribution: implement the P0 output gate that prevents an
  inconsistent or unsafe recommendation from reaching the submission file.
- User-observable effect: every recommendation has the exact required fields,
  a concise trace-grounded explanation, and all-or-nothing publication.
- Why now: WP-08 consumes the accepted WP-06 capacity/replay boundary and the
  final WP-07 planning decision, and it unblocks WP-09 evaluation and WP-10
  batch composition.
- Direction decisions used: `problem_statement.md` Required Output through
  Choosing Between Safe Plans; `master-plan.md` sections 3–8 and WP-08;
  FIN-MIN Output Validation And Public-Sample Metrics.
- New direction decisions required: `None`

## Package Authority And Scope

| Item | Contract |
|---|---|
| Repository root | `/Users/mtrusov/work/repos/hkr-orc-0926` |
| Dependencies | WP-06 accepted; WP-07A/B accepted; **fresh WP-07C acceptance is required before WP-08A edits begin** |
| Primary production owner | `code/buy_or_wait/output.py` |
| Primary tests | `tests/test_output.py` |
| Narrow shared-contract change | `code/buy_or_wait/domain.py` and its closest existing tests only for the output-method type below |
| Navigation updates | `code/buy_or_wait/README.md` and `docs/project-map.md` when public symbols/tests exist |
| Read-only context | accepted `planning.py` decision/capacity/replay records, `forecast.py` baseline records, `RequestCase`, nearby planning tests, and the authorities above |
| Out of scope | WP-07 ranking changes; forecast/evidence/event policy; CLI/pipeline wiring; sample calibration; full-dataset execution; usage reporting; provider calls; explanation polish beyond small deterministic templates |

WP-07C was accepted (2026-09-13) before WP-08A edits began; the WP-08A
implementer inspected the accepted result rather than adapting to or editing a
half-finished seam.

## Proposed Architecture And Data Flow

Keep one flat, standard-library-only output module. Do not create a generic
serialization framework, validator registry, filesystem abstraction, or new
pipeline layer.

```text
RequestCase + BaselineForecast + accepted WP-07 PlanningDecision
                         |
                         v
             build_output_row / explain_decision       (WP-08A)
                         |
                         v
                    typed OutputRow
                         |
                         +--> canonical field encode/decode              (A)
                         |
                         v
       validate_output_row against case + recomputed capacity + replay  (B)
                         |
                         v
          validate complete ordered batch and exact request coverage     (C)
                         |
                         v
       write sibling temp -> read/parse/validate -> os.replace           (C)
```

### Public semantic seam

Exact names may follow the accepted WP-07 style, but preserve these testable
boundaries:

```python
OUTPUT_COLUMNS: tuple[str, ...]

class OutputValidationError(ValueError):
    reason_code: str
    request_id: str | None
    field: str | None

def explain_decision(case, baseline, decision) -> str: ...
def build_output_row(case, baseline, decision) -> OutputRow: ...
def serialize_output_row(row: OutputRow) -> dict[str, str]: ...
def parse_output_row(values: Mapping[str, str]) -> OutputRow: ...
def validate_output_row(row, case, baseline, decision) -> None: ...
def validate_output_batch(rows, contexts_in_request_order) -> None: ...
def write_output_atomic(path, rows, contexts_in_request_order) -> None: ...
```

Use one small context dataclass only if the repeated `(case, baseline,
decision)` triple otherwise makes batch matching ambiguous.

### Output method type correction

The existing `domain.OutputRow.recommended_payment_method` is
`PaymentMethod | None`, which cannot represent authoritative `wait` as a typed
value and uses `None` where CSV requires `not_recommended`. After WP-07C is
accepted, WP-08A should add a domain `RecommendedPaymentMethod` enum with
exactly `full_payment`, `partial_payment`, `installments`, `wait`, and
`not_recommended`, then change only that `OutputRow` annotation. Translate from
WP-07's accepted recommendation enum in `output.py`; do not move or rewrite
WP-07's enum.

### Canonical lexical rules

- All numbers remain finite `Decimal`; never convert through `float`.
- Scalar safe amount is plain decimal with no grouping/exponent/sign on zero
  and trimmed trailing fractional zeros (`620.40` -> `620.4`).
- Plan and `reduce_to` amounts are plain decimal; integers omit `.00`, while a
  noninteger has at least two fractional digits and retains supplied precision
  beyond two (`620.4` -> `620.40`, `1.2340` -> `1.2340`). Never round during
  rendering.
- Dates are strict ISO `YYYY-MM-DD`.
- Plans are chronological `date:amount` tokens joined by `|`, or `none`.
- Changes are ordered by `(event_id, change_type.value, canonical new amount)`
  to match WP-07B, then rendered exactly as `stop:event_id` or
  `reduce_to:event_id:amount`, joined by `|`, or `none`.
- Absent earliest date is empty string. No other required field uses empty,
  `null`, `None`, or a NaN spelling.
- Columns are exactly, in this order:

  ```text
  request_id,amount_safe_to_pay,affordability_status,recommended_payment_method,payment_plan,earliest_date_for_full_payment,spending_changes_needed,decision_explanation
  ```

Parsing rejects padding, exponent/grouping, malformed separators, duplicate
actions, invalid dates, nonpositive payments, and noncanonical text. Enforce
canonical form by parse then serialize and compare to the original fields.

### Explanation contract

`explain_decision` is deterministic, not free-form generation. It may use only
the request amount/date/deadline, profile minimum, horizon end, recomputed
capacity, selected payments/actions, selected replay result, and accepted
WP-07 diagnostic reason. Never copy raw message/image text or infer from an
event description.

Use one short template per outcome class:

- unchanged full now: exact amount/date and replay-protected minimum;
- full with changes: serialized actions, then amount/date and protected minimum;
- partial: both exact amounts/dates and protected minimum;
- installments: count, exact total, first/last dates, protected minimum, and no
  claim of zero financing cost unless the supplied fee is exactly zero;
- unchanged wait: baseline earliest certified date and full amount;
- changed wait: actions and changed candidate date, without calling it the
  baseline earliest date;
- not recommended: the truthful reason class—unbounded required debit, first
  safe date after deadline, no accepted eligible method/option, or no safe
  complete plan—without replacing it with generic insufficient-funds prose.

The validator requires the explanation to equal this renderer. That makes
unsupported custom text rejectable without attempting to fact-check prose.

## Shared Package Invariants

1. Baseline safe amount and earliest date are recomputed from the unchanged
   baseline, never inferred from the winner or optional changes.
2. A row is not trusted because `build_output_row` created it; tests construct
   and reject independently corrupted rows.
3. Safety validation calls WP-06 `replay_schedule` on row-derived payments and
   actions through the fixed horizon; it never trusts cached candidate replay.
4. Output code does not read `dataset/`, call a provider, change policy, rank
   candidates, or expose raw carrier content.
5. The destination is never opened for truncating write. Publication uses a
   fully written, flushed, closed, reparsed, revalidated sibling temp and one
   `os.replace`.

---

# WP-08A — Build And Canonically Render One Output Row

Status: **ACCEPTED (2026-09-13)**

```yaml
agent_tier: standard
reasoning: medium
review: immediate
budget: 12 tool calls / 35 minutes / medium context
```

## Readiness Route

`implementer self-preflight` — confirm WP-07C has a fresh ACCEPT record, bind
to its final immutable fields, and confirm no concurrent edits touch the owned
files.

## Outcome

Convert one accepted planning decision into a typed `OutputRow`, a grounded
deterministic explanation, and a reversible eight-field mapping without file
I/O.

## Required Work

1. Run the final accepted WP-07C targeted/owning commands before editing.
2. Add fail-first `OutputRowBuildAndCodecTests`; prove the current model cannot
   type `wait`/`not_recommended` and lacks canonical codecs.
3. Make the narrow output-method type correction above.
4. Implement `OUTPUT_COLUMNS`, decimal/date/plan/change codecs, and strict row
   parsing. Keep single-use helpers private.
5. Implement pure `explain_decision` and `build_output_row`, copying unchanged
   capacity, selected payments/actions, derived status/method, and explanation.
6. Cover every explanation class, including four fallback reason classes and
   changed-wait versus baseline-earliest wording.
7. Add encode/decode/encode tables for all statuses/methods, money boundaries,
   empty earliest, plan cardinalities, actions, and CSV-sensitive explanation
   content (comma, quote, newline).
8. Update navigation only after public symbols/tests exist.

## Acceptance Criteria

- **A-AC-01:** all eight typed values come only from the matching case,
  unchanged capacity, and accepted decision; wait/fallback are enums.
- **A-AC-02:** codecs preserve typed values without float, exponent, grouping,
  negative zero, or silent rounding.
- **A-AC-03:** plan/action syntax and canonical order are exact; `none` and
  empty earliest have only authorized meanings.
- **A-AC-04:** every outcome class has concise deterministic grounded prose;
  preference, deadline, uncertainty, and safety fallbacks remain distinct.
- **A-AC-05:** A performs no file I/O, independent financial validation,
  ranking, forecasting, provider access, or pipeline wiring.

## WP-08A Verification

| Evidence | Scenario and oracle | Command |
|---|---|---|
| Dependency | Accepted WP-07 decision surface remains green | final WP-07C focused class, then `python3 -m unittest tests.test_planning` |
| Fail-first/targeted | typed wait/fallback, templates, codecs, malformed text | `python3 -m unittest tests.test_output.OutputRowBuildAndCodecTests` |
| Shared contract | domain loading/parsing remains unchanged | `python3 -m unittest tests.test_repository` |
| Compile | source/tests compile | `python3 -m compileall -q code tests` |
| Broader gate | fresh A reviewer on final A bytes | `python3 -m unittest tests.test_planning tests.test_output` then `git diff --check` |

## WP-08A Review Record

- Review date: 2026-09-13
- Profile: guided, fresh independent acceptance review
- Scope: `output.py`, `tests/test_output.py`, the narrow `domain.py`
  output-method type correction (`RecommendedPaymentMethod` enum and the
  `OutputRow` annotation), and the WP-08A navigation rows.
- Dependency evidence: `python3 -m unittest tests.test_planning` — 47 tests OK.
- Targeted evidence: `python3 -m unittest
  tests.test_output.OutputRowBuildAndCodecTests` — 18 tests OK.
- Shared-contract evidence: `python3 -m unittest tests.test_repository` — 39
  tests OK (1 skipped); `python3 -m compileall -q code tests` — OK.
- Independent probes: scalar trimming (`620.40` -> `620.4`, `-0.00` -> `0`,
  `1E+2` -> `100`), plan exponent handling (`1.2E+2` -> `120`, `1E-1` ->
  `0.10`, `0.005` precision preserved), mixed-exponent action ordering
  (`reduce_to:ev1:9.995|reduce_to:ev2:10`), CSV-sensitive round trips, and
  fallback-vocabulary trace against `planning._fallback_diagnostic` — all
  clean.
- Correction cycle: first review found F-01 (integer-valued exponent-2
  Decimals rendered `300.00` in plan/reduce_to, violating the integers-omit-
  `.00` rule, and the parser accepted that noncanonical lexeme) and F-02
  (negative zero rendered `reduce_to:ev1:-0`; only the scalar path normalized
  the sign). Both fixed on the current bytes: `_plain_decimal` normalizes zero
  (any sign/exponent) and strips `.00` from integer-valued amounts on all
  non-scalar paths, and the parse-then-serialize comparison now rejects the
  noncanonical lexemes. Regression tests added:
  `test_integer_valued_plan_and_reduce_to_omit_decimal` and
  `test_negative_zero_normalizes_to_zero_for_plan_and_reduce_to`.
- Post-correction probes: original P1-P4 rerun plus `1E-1`, `0.005`, `1E+2`,
  and mixed-exponent ordering variants — all clean; round-trip stability and
  ordering unaffected.
- Broad gate: owned by the fresh post-correction reviewer and run —
  `python3 -m unittest tests.test_output tests.test_planning
  tests.test_repository` — 106 tests OK (1 skipped); `git diff --check` — OK.
  The first iteration's gate was premature relative to F-01/F-02; the
  corrected-bytes gate is final.
- No open WP-08A findings remain.

Verdict: **ACCEPT** (A-AC-01–A-AC-05 satisfied on the corrected bytes; no open
findings). WP-08B may proceed through its implementer self-preflight.

## WP-08A Stops And Handoff

- Stop if WP-07C is not accepted or lacks status, method, immutable capacity,
  selected candidate, and truthful fallback diagnostics.
- Stop on dirty shared-file overlap; do not adapt to half-written WP-07C code.
- Stop if an explanation needs raw carrier text or a new financial inference.
- Treat 12 calls/35 minutes as soft checkpoints; do not pull B/C forward.
- Next: guided A implementation after self-preflight, followed immediately by
  a fresh independent acceptance review. Accepted A bytes unblock B.

---

# WP-08B — Independently Validate One Output Row

Status: **ACCEPTED (2026-09-13)**

```yaml
agent_tier: strong
reasoning: medium
review: immediate
budget: 13 tool calls / 45 minutes / medium-high context
```

## Readiness Route

`implementer self-preflight` — confirm fresh A acceptance and the accepted
WP-06 replay/capacity and WP-07 decision seams; confirm no overlap.

## Outcome

Reject every row that disagrees with its case, unchanged capacity, accepted
decision, eligibility rules, exact option/action contract, or a fresh
full-horizon replay.

## Required Work

1. Preserve A's suite and add fail-first `OutputRowValidationTests` from
   independently corrupted copies; assert stable reason code and field.
2. Add source-safe `OutputValidationError`; never include raw evidence text.
3. Recompute capacity and require exact safe amount/earliest equality,
   including uncertainty and earliest-after-deadline cases.
4. Validate ID, finite/ranged amount, enums, exact generated explanation, and
   the full status/method table.
5. Validate plan by method:
   - full: one payment of requested amount on D;
   - wait: one full payment strictly after D and by deadline/horizon;
   - partial: exactly `(D, safe)` and `(baseline earliest, A-safe)`, with flag,
     preference, range, total, and deadline gates;
   - installments: exact tuple match to one whole supplied option, including
     count, interval, first date, amount, fee/total, cap, preference, deadline,
     and horizon;
   - not recommended: no payments and no changes.
6. Validate zero-to-three canonical actions. Use WP-07B's public action
   catalogue to resolve series identity, then enforce catalogue membership,
   no repeated family/conflict, category/flexibility/protection/floor rules,
   and allowed-set membership.
7. Freshly call `replay_schedule` with row-derived payments/actions and require
   safety through the final checkpoint. Ignore cached candidate safety.
8. Require exact agreement with the accepted decision, but do the independent
   checks first so jointly corrupt row/decision values cannot bypass capacity,
   option/action, or replay rules.

## Acceptance Criteria

- **B-AC-01:** ID, finite/ranged amount, enum domains, baseline safe amount,
  and baseline earliest date are exact.
- **B-AC-02:** every authorized status/method/plan/change row passes and every
  other cross-field combination rejects with a stable reason.
- **B-AC-03:** full/wait/partial are exact; installments match one complete
  supplied offer and every user/request gate without invention.
- **B-AC-04:** only one-to-three permitted recurring families can change;
  protected/fixed/disallowed/floor/duplicate/conflict cases reject.
- **B-AC-05:** fresh replay catches first-payment, later essential, day-90,
  and changed-plan failures even when cached safety says true.
- **B-AC-06:** empty, edited, or reason-swapped explanation rejects.
- **B-AC-07:** validation is pure, deterministic, offline, and side-effect free.

## WP-08B Verification

| Evidence | Scenario and oracle | Command |
|---|---|---|
| Dependency | A and upstream inputs remain green | `python3 -m unittest tests.test_output.OutputRowBuildAndCodecTests tests.test_planning` |
| Fail-first/targeted | one corruption per domain/table/plan/option/action/explanation/capacity/replay reason | `python3 -m unittest tests.test_output.OutputRowValidationTests` |
| Owning suite | all A/B output behavior | `python3 -m unittest tests.test_output` |
| Upstream regression | forecast/planning stay accepted | `python3 -m unittest tests.test_forecast tests.test_planning` |
| Compile | source/tests compile | `python3 -m compileall -q code tests` |
| Broader gate | fresh B reviewer on final B bytes | `python3 -m unittest discover -s tests -p 'test_*.py'` then `git diff --check` |

## WP-08B Stops And Handoff

- Stop without fresh A acceptance or on shared-file overlap.
- Stop if validation needs a private WP-07 helper; request the smallest public
  seam instead of copying ranking or forecast construction.
- Stop if the row cannot be checked through public WP-06 replay; cached replay
  is not a substitute.
- Treat 13 calls/45 minutes as soft checkpoints; do not add batch I/O.
- Next: guided B implementation after self-preflight, followed immediately by
  a fresh independent acceptance review. Accepted B bytes unblock C.

## WP-08B Review Record

- Review date: 2026-09-13
- Profile: guided, fresh independent acceptance review; two iterations
- Scope: the WP-08B additions in `output.py` (`validate_output_row` and
  private plan/change/replay/table helpers), the `OutputRowValidationTests`
  suite in `tests/test_output.py`, and the WP-08B navigation rows in
  `code/buy_or_wait/README.md` and `docs/project-map.md`. WP-08A bytes were
  not modified.
- Dependency evidence: `python3 -m unittest
  tests.test_output.OutputRowBuildAndCodecTests tests.test_planning` — 67
  tests OK.
- Targeted evidence: `python3 -m unittest
  tests.test_output.OutputRowValidationTests` — 15 tests OK on first
  iteration; 18 tests OK on corrected bytes.
- Owning/upstream evidence: `python3 -m unittest tests.test_output` — 35 OK
  (38 on corrected bytes); `python3 -m unittest tests.test_forecast` — 72 OK;
  `python3 -m compileall -q code tests` — OK; `git diff --check` and
  `git diff --cached --check` — OK.
- Independent probes (iteration 1): jointly corrupt decision/row variants,
  non-anchor sibling occurrence ID (`change_not_eligible`), corrupted cached
  safety verdict ignored in favor of fresh replay, NaN and boolean type
  confusion (`amount_out_of_range`), wait plan date/amount boundaries,
  changed-row replay breach, status-table siblings, partial order/flag
  boundaries, foreign installments option ID, and frozen-input purity —
  13/15 clean; two probe-harness artifacts were re-derived and are not
  defects.
- Correction cycle: first review found F-01/P1 (partial rows accepted when
  `payment_methods_user_will_consider` excludes `PARTIAL_PAYMENT` — missing
  independent preference gate, B-AC-03/FR-08-04), F-02/P1 (same missing gate
  for `INSTALLMENTS`), and F-03/P2 (an incoherent decision escaped
  `validate_output_row` as a raw `IndexError` from `explain_decision` instead
  of a source-safe `OutputValidationError`, violating B-AC-07's rejection
  contract). Fixed on the current bytes: `_validate_plan_by_method` now
  enforces `full_preference_excluded`/`wait_preference_excluded`/
  `partial_preference_excluded`, `_validate_installments` enforces
  `installment_preference_excluded`, and `_validate_decision_coherence`
  raises `invalid_decision` before rendering. Regression tests added:
  `test_full_wait_and_partial_preferences_reject`,
  `test_installment_preference_rejects`,
  `test_incoherent_decision_rejects_before_explanation_rendering`, and
  `test_incoherent_decision_rejects_before_rendering`.
- Post-correction probes: F1-redo and F2-redo (real planner rows with the
  profile flipped to exclude the method) reject with the new reason codes;
  F3/F3b reject as `invalid_decision` with no non-`OutputValidationError`
  escape. False-reject risk checked against planner semantics: full/wait
  gate conditions mirror `_no_change_templates` gating, the changed-WAIT
  derivation sits inside the `accepted_full` block, and
  `NOT_RECOMMENDED` always pairs with `selected_candidate=None`, so genuine
  planner output for full/wait/partial/installments still validates.
- Broad gate: owned by the fresh post-correction reviewer and run —
  `python3 -m unittest discover -s tests -p 'test_*.py'` — 340 tests OK
  (1 skipped); `python3 -m compileall -q code tests` — OK;
  `git diff --check` (staged and unstaged) — OK. The first iteration's gate
  was suppressed after the decisive F-01/F-02/F-03 failures per the
  discovery-review rule; the corrected-bytes gate is final.
- No open WP-08B findings remain.

Verdict: **ACCEPT** (B-AC-01–B-AC-07 satisfied on the corrected bytes; no
open findings). WP-08C may proceed through its implementer self-preflight.

---

# WP-08C — Validate The Batch And Replace The CSV Atomically

Status: **ACCEPTED (2026-09-13)**

```yaml
agent_tier: standard
reasoning: medium
review: immediate
budget: 10 tool calls / 25 minutes / medium context
```

## Readiness Route

`implementer self-preflight` — confirm fresh B acceptance, exact expected
request order from repository iteration, and no concurrent output/test edits.

## Outcome

Publish exactly one validated row per expected evaluation request in input
order by replacing the destination once; any prior failure leaves the old
bytes unchanged and removes the temp sibling.

## Required Work

1. Add fail-first `OutputBatchAndAtomicWriterTests` with `TemporaryDirectory`
   and real files; preserve a sentinel destination for every failure case.
2. Materialize input once and reject missing, duplicate, extra, sample-scope,
   mismatched-context, or out-of-order IDs before publication. Validate each
   row with B.
3. Create a temp file in the existing destination parent. Use
   `csv.DictWriter`, `OUTPUT_COLUMNS`, `newline=""`, and strict extras.
4. Write header/rows, flush, `os.fsync`, and close.
5. Reopen with `newline=""`; require exact header/no extra or missing cells,
   parse every row, rerun batch validation, and require typed equality.
6. Call `os.replace(temp, destination)` exactly once after success. In
   `finally`, unlink only a still-existing temp; never unlink/truncate/create
   the destination as a preparatory step.
7. Test new and existing destinations. Patch only `os.replace` for its failure
   case; use the real sibling temp and assert sentinel preservation/cleanup.
8. Update navigation. Do not wire `code/main.py`; WP-10 owns composition.

Directory fsync for power-loss durability after `os.replace` is out of scope;
the required guarantee is atomic visibility and old-file preservation for
failures before or during replacement.

## Acceptance Criteria

- **C-AC-01:** exactly one row per expected evaluation request, no
  sample/extra/duplicate/missing/out-of-order ID, exact header/order.
- **C-AC-02:** CSV write/read preserves values, canonical fields, and quoted
  comma/quote/newline explanations.
- **C-AC-03:** typed and reparsed rows both pass B before replacement.
- **C-AC-04:** validation, write, flush, reparse, revalidation, and replace
  failures preserve the old destination byte-for-byte and remove temp.
- **C-AC-05:** new and existing destinations publish exact expected bytes
  through one `os.replace`.
- **C-AC-06:** no dataset loading, CLI/pipeline, evaluation, usage, ZIP,
  network, or dependency work enters C.

## WP-08C Verification

| Evidence | Scenario and oracle | Command |
|---|---|---|
| Dependency | accepted A/B behavior | `python3 -m unittest tests.test_output.OutputRowBuildAndCodecTests tests.test_output.OutputRowValidationTests` |
| Fail-first/targeted | coverage, quoting, temp sibling, each failure, creation/replacement | `python3 -m unittest tests.test_output.OutputBatchAndAtomicWriterTests` |
| Owning suite | all WP-08 behavior | `python3 -m unittest tests.test_output` |
| Upstream regression | planner/replay inputs | `python3 -m unittest tests.test_planning tests.test_forecast` |
| Documentation | symbols/commands navigable | `python3 -m unittest tests.test_agent_foundation_contract` |
| Compile | source/tests compile | `python3 -m compileall -q code tests` |
| Broader gate | fresh final C reviewer | `python3 -m unittest discover -s tests -p 'test_*.py'` then `git diff --check` |

## WP-08C Stops And Handoff

- Stop without fresh B acceptance or on shared-file overlap.
- Stop if expected order cannot be supplied without dataset loading in
  `output.py`; WP-10 must pass ordered validated contexts.
- Never use root `output.csv` in tests; use synthetic temp-directory files.
- Treat 10 calls/25 minutes as soft checkpoints.
- Next: guided C implementation after self-preflight, followed immediately by
  a fresh independent acceptance review owning final WP-08 verdict.

## WP-08C Review Record

- Review date: 2026-09-13
- Profile: guided, fresh independent acceptance review; single iteration
- Scope: the WP-08C additions in `output.py` (`OutputContext`,
  `validate_output_batch`, `write_output_atomic`, and private batch/CSV
  helpers), the `OutputBatchAndAtomicWriterTests` suite in
  `tests/test_output.py`, and the WP-08C navigation rows in
  `code/buy_or_wait/README.md` and `docs/project-map.md`. WP-08A/B bytes were
  not modified.
- Dependency evidence: `python3 -m unittest
  tests.test_output.OutputRowBuildAndCodecTests
  tests.test_output.OutputRowValidationTests` — 38 tests OK.
- Targeted evidence: `python3 -m unittest
  tests.test_output.OutputBatchAndAtomicWriterTests` — 13 tests OK on the
  first and only iteration.
- Independent probes: duplicate context IDs (`duplicate_context`), fsync
  failure mid-write, truncated-temp reparse failure (`unexpected_header`),
  tampered reparse equality (`reparse_mismatch`), out-of-order rows rejected
  before any temp or publication, sample context among evaluation contexts
  (`sample_scope` before replace), and a success-path `os.replace` call
  counter confirming exactly one replace with no sibling temp remaining —
  all clean; sentinel destination preserved byte-for-byte and temp removed in
  every failure probe.
- Owning/upstream evidence: `python3 -m unittest tests.test_output
  tests.test_planning tests.test_forecast` — 170 tests OK;
  `python3 -m unittest tests.test_agent_foundation_contract` — 3 tests OK;
  `python3 -m compileall -q code tests` — OK; `git diff --check` and
  `git diff --cached --check` — OK.
- Broad gate: owned and run by this fresh reviewer after targeted/adversarial
  evidence was clean — `python3 -m unittest discover -s tests -p 'test_*.py'`
  — 353 tests OK (1 skipped).
- Residual note (not a defect): a typed row carrying a noncanonical Decimal
  exponent (e.g. `900.00000`) passes numeric validation, but published CSV
  bytes are canonical via `_plain_decimal` and reparse-equality enforces
  canonical rendering. Directory fsync after `os.replace` remains out of
  scope per the plan's durability note.
- No open WP-08C findings remain.

Verdict: **ACCEPT** (C-AC-01–C-AC-06 satisfied; no open findings). WP-08 is
complete; WP-09 and WP-10 may proceed.

## Finite-Risk Coverage Contract

Keep row IDs stable across A/B/C and correction reviews.

| Invariant | Material dimensions/cases | Decisive oracle/boundary | Implementation evidence | Independent review probe | Gate owner |
|---|---|---|---|---|---|
| FR-08-01 exact fields/lexemes | five methods; four statuses; safe 0/A/fraction/negative-zero/NaN/exponent; earliest date/empty; plan/action none/populated | typed encode/decode/encode and exact dict | A codec tables and malformed counterexamples | alter only a numeric lexeme; parser rejects noncanonical form | A implementer/reviewer — **pass on corrected bytes (2026-09-13; F-01/F-02 found and fixed)** |
| FR-08-02 grounded explanations | full unchanged/changed; partial; installments fee zero/nonzero; wait unchanged/changed; four fallbacks | exact renderer from case/baseline/decision | A template fixtures and forbidden-claim assertions | swap fallback reason or wait date; text changes/rejects | A implementer/reviewer — **pass on accepted A bytes (2026-09-13)** |
| FR-08-03 status/method table | full now/changed; partial; installment; wait unchanged/changed; four fallbacks | validator-derived table versus row | B valid rows plus single-field corruption | pair affordable-now with changes or later with changed wait; reject | B implementer/reviewer — **pass on accepted B bytes (2026-09-13; F-01–F-03 found and fixed)** |
| FR-08-04 exact eligible plans | full/wait; partial two; installment 2/3/N; before D/deadline/horizon; bad total/order/count/cap/preference | payments plus source option/request/profile | B boundary tables | mutate installment date preserving count/total; reject | B implementer/reviewer — **pass on accepted B bytes (2026-09-13; preference dimension fixed via F-01/F-02)** |
| FR-08-05 exact eligible actions | 0/1/2/3/4; stop/reduce; fixed/protected/disallowed/floor; duplicate family/conflict | public series catalogue plus case/profile/replay | B allowed/adversarial tables | use another occurrence ID of same family to hide conflict; reject | B implementer/reviewer — **pass on accepted B bytes (2026-09-13)** |
| FR-08-06 fresh safety | equality at minimum; first/later/day-90 breach; changed repair/mismatch; corrupt cached verdict | fresh row-derived WP-06 replay through final checkpoint | B literal ledgers | mark cached replay safe and insert late debit; still reject | B implementer/reviewer — **pass on accepted B bytes (2026-09-13)** |
| FR-08-07 exact batch | missing/extra/duplicate/sample/order/context mismatch; complete evaluation sequence | expected ID sequence versus materialized rows | C exact batch tables | permute two valid rows; reject before replace | C implementer/reviewer — **pass on accepted C bytes (2026-09-13)** |
| FR-08-08 all-or-nothing publication | new/existing destination; fail before/during write, flush, reparse, revalidation, replace; success | real temp-dir bytes and sibling inventory | C sentinel and success tests | fail patched replace after valid temp closes; old bytes/temp cleanup | C implementer/final reviewer — **pass on accepted C bytes (2026-09-13)** |

## Package Exit Criteria

WP-08 is complete only when A, B, and C receive fresh independent `ACCEPT` in
order; every FR-08 row passes on final relevant bytes; `tests.test_output`,
`tests.test_planning`, and `tests.test_forecast` pass; the final reviewer passes
the complete unit suite, compile gate, agent foundation contract, and
`git diff --check`; navigation is current; and WP-08 does not implement WP-09
or WP-10. Accepted C bytes unblock WP-09 and WP-10.

WP-08A, WP-08B, and WP-08C all have fresh independent `ACCEPT` records above.
WP-08 is complete; every FR-08 row passed on final relevant bytes and the
final reviewer owns the completed broad gate. WP-09 and WP-10 may proceed.
