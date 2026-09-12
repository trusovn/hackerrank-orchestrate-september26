# Open Questions And Working Hypotheses

Status: pre-plan decision register  
Rule: hypotheses are not requirements until evidence resolves them

P0 items can change numeric predictions or plan classification and must be
resolved before the master plan. P1 items affect implementation quality, cost,
or maintainability but do not redefine the product contract. P2 items are
organizer/environment unknowns that may remain unavailable.

Planning dispositions, decision tables, bounded experiments, conservative
fallbacks, discriminating samples, and acceptance signals for the P0 set are
recorded in
[`08-financial-semantics-decisions.md`](08-financial-semantics-decisions.md).

## P0 Financial Semantics

### FIN-001 — Opening Balance Cutoff

- **Question:** Does `current_available_balance` already include every settled
  transaction before `request_date`?
- **Impact:** Reapplying historical events would corrupt every forecast.
- **Working hypothesis:** The profile balance is the opening balance at the
  request boundary. Past settled rows are recurrence/evidence history only;
  only future obligations and inferred recurrences change it.
- **Disposition:** Accept the supplied available balance as opening cash at the
  request boundary. Do not replay settled history; use it only as evidence for
  justified forecast inference.
- **Status:** DECIDED FOR PLANNING — conservative rule; implementation
  validation remains deferred.

### FIN-002 — Forecast Boundary And Same-Day Ordering

- **Question:** Is the window `[request_date, request_date + 90 days]` or 90
  dates ending on day 89? What happens when income, expense, and a proposed
  payment share a date?
- **Impact:** Changes earliest safe dates and minimum intraday balances.
- **Selected rule:** Use the inclusive request-date through day-90 window,
  reserve pending debits at opening, and use debit-before-credit then proposed
  payment when intraday order is unknown. Explicit grounded timing overrides
  the fallback.
- **Evidence:** No supplied settlement date equals its user's request date, so
  the current corpus does not directly resolve request-day ordering. Solved wait
  cases often pay on a confirmed salary date, implying same-day settled salary
  can fund that payment.
- **Supplemental claim:** `rev-eng.md` asserts a daily ledger with later-day
  salary credits before debits, but its simulator is unavailable and its exact
  safe-amount reconstruction has material residuals. Treat this as an
  experiment candidate, not a resolution (`REC-09`).
- **Disposition:** Bounded `EXP-DATE` compares only day 89/90 and the two
  unknown same-day orders; the selected safe fallback is inclusive day 90 and
  debit-first.
- **Status:** DECIDED FOR PLANNING — bounded early experiment.

### FIN-003 — Recurrence Detection

- **Question:** Which historical patterns recur, at what cadence, and after how
  many observations?
- **Impact:** The 141 explicit future events are insufficient; most of the
  90-day forecast must be inferred.
- **Working hypothesis:** Group by user plus semantic event identity, recognize
  supported calendar-month and shorter regular cadences with tolerance, and
  require stronger evidence for variable or unusual groups. Explicit endings
  and amendments override history.
- **Do not assume:** Every repeated description recurs, every five-row series is
  monthly, or every salary continues.
- **Disposition:** Use strict supported recurrence as the safe starting rule;
  run the finite `EXP-RV` matrix of at most 12 global configurations during
  implementation.
- **Status:** DECIDED FOR PLANNING — bounded early experiment; largest retained
  accuracy risk.

### FIN-004 — Conservative Variable-Spend Forecast

- **Question:** How should varying groceries, transport, dining, utilities, and
  other essential series be projected?
- **Impact:** Directly controls the future minimum headroom and safe amount.
- **Candidate policies:** latest observation; mean; maximum observation; upper
  percentile; maximum monthly category total; recent weighted mean plus a
  buffer.
- **Working hypothesis:** Aggregate variable essentials into cadence/category
  envelopes rather than recurring every individual historic purchase. Choose
  the most conservative policy that still matches the solved examples.
- **Disposition:** Start with the maximum comparable complete-cycle category
  envelope and evaluate only the three `EXP-RV` variable policies. Missing
  required numeric observations are never zero.
- **Status:** DECIDED FOR PLANNING — bounded early experiment.

### FIN-004A — Recurring Income Beyond The Next Confirmed Credit

- **Question:** After a supported salary cadence and one confirmed future
  salary, should later salary cycles inside the 90-day window be projected, or
  should income stop after the last explicitly confirmed settlement?
- **Impact:** This can flip installment feasibility and safe amounts across
  multiple months.
- **Authoritative tension:** The statement requires forecasting recurring
  income, while also requiring confirmed salary to be counted only on its
  settlement date and forbidding invented income.
- **Candidate policies:** project all strongly supported salary recurrences;
  project only one explicitly scheduled/confirmed credit; or project recurrence
  only when a message explicitly confirms continued employment/pay.
- **Disposition:** Start with confirmed future credits and explicitly ongoing
  grounded income; do not extend next-only evidence. `EXP-RV` compares that
  rule with strict recent history-supported continuation.
- **Status:** DECIDED FOR PLANNING — bounded early experiment with the more
  conservative income fallback.

### FIN-005 — Essential And Protected Expense Definition

- **Question:** Does every fixed future/recurring debit count as essential, or
  only protected categories? What happens to flexible expenses when no change
  is recommended?
- **Impact:** Excluding fixed non-protected spending overstates capacity;
  excluding baseline flexible spending makes optional changes meaningless.
- **Working hypothesis:** All supported recurring debits remain in the baseline.
  Fixed and protected events cannot change. Flexible events remain at baseline
  unless an allowed spending action changes them.
- **Disposition:** Accept the working hypothesis as the authoritative/
  conservative baseline rule.
- **Status:** DECIDED FOR PLANNING.

### FIN-006 — Event Status And Lifecycle Effects

- **Question:** What exact ledger effect does each status/lifecycle combination
  have?
- **Authoritative core:** settled cash is real; pending debits are reserved;
  unsettled credits and unrealized valuations are excluded; failed and cancelled
  records are ignored unless later evidence establishes another obligation.
- **Working cases to prove:** failed debit plus scheduled retry; settled expense
  plus pending refund; cancelled charge plus settled replacement; settled charge
  plus pending disputed duplicate; investment purchase/valuation/sale; work
  expense/reimbursement; internal transfer pair.
- **Supplemental conflict:** one note suggests ignoring a pending
  possible-duplicate debit while another alternates between reserving it
  immediately and applying it on settlement. Pending-debit reservation remains
  the authoritative baseline; the duplicate lifecycle and timing still need a
  focused decision (`REC-06`).
- **Disposition:** Use the lifecycle/status matrix in document 08. Reserve each
  pending debit once; never count unsettled credits or unrealized values; links
  do not themselves prove cancellation, duplication, or cash neutrality.
- **Status:** DECIDED FOR PLANNING — authoritative core plus conservative
  synthetic-fixture boundaries.

### FIN-007 — Message Targeting And Amendment Duration

- **Question:** How does a user/request-level message target one historical
  recurrence when `related_event_id` is blank, and is the effect one-time or
  recurring?
- **Impact:** Salary, rent, and employment messages can materially alter all
  future dates.
- **Working hypothesis:** Use fact type, source identity, description/category,
  currency, and effective date to select exactly one compatible series. Reject
  or conservatively ignore ambiguous mappings rather than amending multiple
  series.
- **Resolution:** The 17 actual sample-user messages have typed expected facts
  and deterministic target/duration rules in
  [`07-evidence-decision-pack.md`](07-evidence-decision-pack.md). Require one
  compatible same-user series; fail closed for ambiguous debits and add no cash
  for ambiguous credits. Full evaluation-message classification is deferred to
  implementation.
- **Status:** DECIDED FOR PLANNING; corpus-wide empirical coverage deferred.

### FIN-008 — Foreign-Currency Precision

- **Question:** At what precision are event conversions rounded, and when is
  rounding applied?
- **Impact:** Small rounding differences can change exact safe amounts and CSV
  scoring.
- **Working hypothesis:** Use `Decimal`, multiply using the exact supplied
  direction/rate on settlement date, keep internal precision through simulation,
  and round only at currency/output boundaries.
- **Rejected supplemental expansion:** latest-prior fallback and multi-hop
  chaining are not needed for observed foreign events and are not authorized by
  the supplied exact dated-pair rule (`REC-07`). Missing required rates should
  fail validation rather than silently selecting another date or path.
- **Disposition:** Use exact directed settlement-date rates and exact decimal
  products with no intermediate money rounding. Missing required rates fail
  validation; `EXP-NUM` may compare only the documented rounding stages.
- **Status:** DECIDED FOR PLANNING — conservative rule plus bounded experiment.

### FIN-009 — General Numeric And Serialization Policy

- **Question:** What decimal scale and formatting are expected per currency and
  output field?
- **Evidence:** Sample outputs mix integer and decimal serialization, including
  currencies commonly displayed without minor units.
- **Working hypothesis:** Use exact decimal arithmetic; normalize negative zero;
  preserve necessary precision without grouping separators or scientific
  notation; format plan amounts consistently with supplied values.
- **Disposition:** Use exact decimal arithmetic, floor certified capacity to
  0.01 only at output, preserve supplied option amounts, and serialize plain
  decimals under the document 08 table.
- **Status:** DECIDED FOR PLANNING — conservative serialization rule with
  implementation fixtures deferred.

### FIN-010 — `max_installment_months`

- **Question:** Does the profile field limit the number of installments or the
  elapsed schedule duration in calendar months?
- **Evidence:** Options are expressed as number of payments with 28/30/31-day
  intervals; 193 options exceed the numeric profile maximum if compared to
  payment count.
- **Working hypothesis:** Treat it as maximum number of monthly installments,
  so `number_of_payments <= max_installment_months`, while separately enforcing
  completion date.
- **Disposition:** Treat the populated positive value as a payment-count cap;
  blank means installments are ineligible. `EXP-CAP` compares only count versus
  elapsed-duration interpretation and keeps count on a tie.
- **Status:** DECIDED FOR PLANNING — bounded early experiment.

### FIN-011 — Earliest Full-Payment Search

- **Question:** Which dates are tested and may the reported earliest date be
  after the desired completion date?
- **Evidence:** `request_06` and `request_21` report earliest dates one day after
  their desired deadline while recommending immediate payment after changes.
- **Working hypothesis:** Search every balance-changing date, plus request date,
  across the full forecast independently of preferences, spending changes, and
  completion deadline. Report the first date a standalone full payment is safe.
- **Disposition:** Search every date in the fixed baseline window independently
  of methods, changes, and deadline; report a safe later date even when it is
  too late to authorize the recommendation.
- **Status:** DECIDED FOR PLANNING — conservative rule with sample regression
  cases named in document 08.

### FIN-012 — Partial-Payment Feasibility

- **Question:** The second payment date is defined using the date a standalone
  full payment is safe. Must the two-payment plan then be simulated again after
  deducting the first payment?
- **Working hypothesis:** Yes. Construction rules do not waive the global safety
  invariant. A syntactically eligible partial plan can still fail simulation.
- **Disposition:** The proposed counterexample is impossible under a common
  additive baseline: before the later date only the already-certified safe
  amount is paid, and afterward the trajectory equals the safe standalone full
  payment. Keep independent schedule validation as a property/regression guard.
- **Status:** AUTHORITATIVE/DECIDED FOR PLANNING.

### FIN-013 — Spending-Change Scope And Optimization

- **Question:** Does `stop:event_id` or `reduce_to:event_id:amount` change only a
  supplied/future occurrence or the entire inferred recurring series? How is a
  new amount chosen, and how are multiple sufficient change sets ranked?
- **Impact:** Determines feasibility and exact `spending_changes_needed` labels.
- **Working hypothesis:** The event ID identifies a recurring series; the action
  affects its occurrences throughout the forecast. Choose no changes first,
  then the smallest permitted set/magnitude that enables the best-ranked plan,
  never below `minimum_allowed_amount`.
- **Evidence:** Only three solved examples use changes, so this branch is weakly
  supervised.
- **Supplemental claim:** the action ID is the latest historical occurrence and
  the change applies series-wide. This explains the three examples but remains
  underdetermined and must not be treated as confirmed (`REC-15`).
- **Disposition:** Start with validated recurring-series scope, explicit floor
  reductions, allowed stops, and at most three distinct series. `EXP-CHANGE`
  compares series-wide versus next-occurrence scope on only the three change
  samples and retains series-wide on a tie.
- **Status:** DECIDED FOR PLANNING — bounded early experiment.

### FIN-014 — Complete Status/Method Mapping

- **Question:** What output is chosen for every combination of capacity,
  deadline, preference, options, and optional changes?
- **Known examples:** full safe plus full accepted -> affordable now; full safe
  but only installments accepted -> affordable with plan/installments; safe
  later plus full accepted -> affordable later/wait; change-enabled immediate
  full -> affordable with plan/full payment.
- **Remaining cases:** full safe but no accepted safe method; safe only after the
  deadline; wait plus changes; multiple equal change sets; partial allowed by
  request but rejected by user; installment safe but outside maximum months.
- **Disposition:** Use the complete status/method table and published ranking in
  document 08, including preference-only, late-only, changed-wait, and
  no-complete-plan fallbacks.
- **Status:** DECIDED FOR PLANNING — decision table complete; implementation
  fixtures deferred.

### FIN-015 — Image Amount Selection

- **Question:** Which visible financial field supplies each blank event amount?
- **Impact:** Wrong gross/net, bill/balance, or before/after-due selection changes
  recurrence and safety.
- **Resolution:** The review in
  [`07-evidence-decision-pack.md`](07-evidence-decision-pack.md) accepts 15
  context-appropriate values and records fields, currencies, confidence, and
  linkage checks. `image_04` remains cropped and therefore fails closed rather
  than promoting its INR 2,854 item subtotal to a final charge. Its linked
  debit settled before `request_19`, so the unresolved extraction is not
  subtracted again and does not by itself invalidate that solved request; it
  remains unavailable to amount-dependent forecasting.
- **Resolved conflict:** `image_05` is INR 822.05 because its supplied
  settlement date is after the document's 2026-02-06 cutoff; INR 704.05 is the
  earlier due-date amount (`REC-08`).
- **Status:** DECIDED FOR PLANNING; one explicit fail-closed carrier.

## P1 Engineering Decisions

### ENG-001 — AI Operations

Decide whether any operation needs a model after deterministic grouping. The
current recommendation is:

- deterministic CSV loading, normalization, finance, plan generation, policy,
  ranking, validation, and rendering;
- optional model use only for message/image-to-fact extraction; and
- no model-generated final financial decision.

### ENG-002 — OCR/Multimodal Strategy

Compare deterministic OCR, multimodal extraction, and a hybrid against the 16
verified images. Include provider failures, multiple-total ambiguity, latency,
cost, reproducibility, and offline behavior. Defer whether the extractor returns
one validated fact or labeled candidates for deterministic caller-side
adjudication; do not let a model make the affordability decision.

### ENG-003 — Evaluation Design

Define exact-field and numeric comparison against 25 samples, invariant failure
reporting, per-request traces, and scenario-level metrics. Separate contract
failures from prediction-quality errors.

### ENG-004 — Explanation Generation

Prefer deterministic templates driven by validated facts. Determine a concise
style and supported facts per recommendation class before considering a model.

### ENG-005 — Runtime And Packaging

Select dependencies only after actual extraction needs are known. Preserve a
terminal-runnable entry point, root output path, evaluation folder, secret
handling, and final-run usage accounting.

## P2 Organizer/Environment Unknowns

These are not answered by repository artifacts:

- exact scoring weights and numeric tolerances;
- whether explanation scoring is lexical, semantic, or rule-based;
- execution time, memory, dependency, and network limits;
- availability of provider credentials during evaluator execution;
- whether only the submitted static `output.csv` is scored or code is rerun;
  and
- the accepted transcript file format beyond the required chat transcript.

Do not block core implementation on unavailable answers. Build a deterministic,
offline-capable path, document assumptions, and treat any current organizer
clarification as higher confidence only when sourced from official materials.

## Decision Recording Rule

When resolving an item:

1. record the evidence or experiment;
2. replace the hypothesis with the selected rule;
3. name rejected alternatives and why;
4. add the smallest fixture capable of detecting regression; and
5. link the implemented module/test when one exists.

Do not mark an item resolved merely because one sample happens to match.
