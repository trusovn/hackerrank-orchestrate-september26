# Open Questions And Working Hypotheses

Status: pre-plan decision register  
Rule: hypotheses are not requirements until evidence resolves them

P0 items can change numeric predictions or plan classification and must be
resolved before the master plan. P1 items affect implementation quality, cost,
or maintainability but do not redefine the product contract. P2 items are
organizer/environment unknowns that may remain unavailable.

## P0 Financial Semantics

### FIN-001 — Opening Balance Cutoff

- **Question:** Does `current_available_balance` already include every settled
  transaction before `request_date`?
- **Impact:** Reapplying historical events would corrupt every forecast.
- **Working hypothesis:** The profile balance is the opening balance at the
  request boundary. Past settled rows are recurrence/evidence history only;
  only future obligations and inferred recurrences change it.
- **Resolution:** Reconstruct several sample timelines both ways. The correct
  interpretation should reproduce their `amount_safe_to_pay` values.
- **Status:** UNRESOLVED, high confidence in hypothesis.

### FIN-002 — Forecast Boundary And Same-Day Ordering

- **Question:** Is the window `[request_date, request_date + 90 days]` or 90
  dates ending on day 89? What happens when income, expense, and a proposed
  payment share a date?
- **Impact:** Changes earliest safe dates and minimum intraday balances.
- **Working hypothesis:** Evaluate the request-day payment first against the
  opening balance; on later dates, settle confirmed credits and reserve debits
  deterministically before testing a proposed end-of-day payment. Use a
  conservative ordering if facts conflict.
- **Evidence:** No supplied settlement date equals its user's request date, so
  the current corpus does not directly resolve request-day ordering. Solved wait
  cases often pay on a confirmed salary date, implying same-day settled salary
  can fund that payment.
- **Status:** UNRESOLVED.

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
- **Resolution:** Implement several policies as experiment configurations and
  score their resulting safe amounts/dates on all 25 examples.
- **Status:** UNRESOLVED and likely the largest accuracy risk.

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
- **Resolution:** Run a deterministic policy sweep and compare numeric residuals
  and earliest-date errors against samples.
- **Status:** UNRESOLVED.

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
- **Resolution:** Run all candidates across the 25 samples, especially cases
  whose plans cross multiple salary dates. Record which outputs discriminate
  rather than relying on qualitative arithmetic.
- **Status:** UNRESOLVED. A concurrent draft argues for explicit-confirmation
  only; that claim has not yet been reproduced.

### FIN-005 — Essential And Protected Expense Definition

- **Question:** Does every fixed future/recurring debit count as essential, or
  only protected categories? What happens to flexible expenses when no change
  is recommended?
- **Impact:** Excluding fixed non-protected spending overstates capacity;
  excluding baseline flexible spending makes optional changes meaningless.
- **Working hypothesis:** All supported recurring debits remain in the baseline.
  Fixed and protected events cannot change. Flexible events remain at baseline
  unless an allowed spending action changes them.
- **Status:** UNRESOLVED, high confidence in hypothesis.

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
- **Resolution:** Create an explicit decision matrix and focused fixture for each
  observed lifecycle pattern.
- **Status:** PARTIALLY RESOLVED.

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
- **Resolution:** Produce expected typed facts and target series for all sample
  messages, then all evaluation messages.
- **Status:** UNRESOLVED.

### FIN-008 — Foreign-Currency Precision

- **Question:** At what precision are event conversions rounded, and when is
  rounding applied?
- **Impact:** Small rounding differences can change exact safe amounts and CSV
  scoring.
- **Working hypothesis:** Use `Decimal`, multiply using the exact supplied
  direction/rate on settlement date, keep internal precision through simulation,
  and round only at currency/output boundaries.
- **Resolution:** Use foreign-currency sample timelines to identify the expected
  rounding point and scale.
- **Status:** UNRESOLVED.

### FIN-009 — General Numeric And Serialization Policy

- **Question:** What decimal scale and formatting are expected per currency and
  output field?
- **Evidence:** Sample outputs mix integer and decimal serialization, including
  currencies commonly displayed without minor units.
- **Working hypothesis:** Use exact decimal arithmetic; normalize negative zero;
  preserve necessary precision without grouping separators or scientific
  notation; format plan amounts consistently with supplied values.
- **Resolution:** Derive golden formatting cases from all 25 samples and option
  rows.
- **Status:** UNRESOLVED.

### FIN-010 — `max_installment_months`

- **Question:** Does the profile field limit the number of installments or the
  elapsed schedule duration in calendar months?
- **Evidence:** Options are expressed as number of payments with 28/30/31-day
  intervals; 193 options exceed the numeric profile maximum if compared to
  payment count.
- **Working hypothesis:** Treat it as maximum number of monthly installments,
  so `number_of_payments <= max_installment_months`, while separately enforcing
  completion date.
- **Resolution:** Confirm every chosen sample installment under both
  interpretations and inspect rejected near-boundary options.
- **Status:** UNRESOLVED, high confidence in hypothesis.

### FIN-011 — Earliest Full-Payment Search

- **Question:** Which dates are tested and may the reported earliest date be
  after the desired completion date?
- **Evidence:** `request_06` and `request_21` report earliest dates one day after
  their desired deadline while recommending immediate payment after changes.
- **Working hypothesis:** Search every balance-changing date, plus request date,
  across the full forecast independently of preferences, spending changes, and
  completion deadline. Report the first date a standalone full payment is safe.
- **Resolution:** Formalize and test against all sample dates.
- **Status:** PARTIALLY RESOLVED from examples.

### FIN-012 — Partial-Payment Feasibility

- **Question:** The second payment date is defined using the date a standalone
  full payment is safe. Must the two-payment plan then be simulated again after
  deducting the first payment?
- **Working hypothesis:** Yes. Construction rules do not waive the global safety
  invariant. A syntactically eligible partial plan can still fail simulation.
- **Resolution:** Add a derived case where standalone full capacity exists later
  but the earlier partial debit makes the remainder unsafe.
- **Status:** INFERRED with high confidence.

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
- **Resolution:** Fully reconstruct `request_06`, `request_11`, and
  `request_21`, then add boundary fixtures.
- **Status:** UNRESOLVED.

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
- **Resolution:** Create a complete truth table before plan-generator design.
- **Status:** PARTIALLY RESOLVED.

### FIN-015 — Image Amount Selection

- **Question:** Which visible financial field supplies each blank event amount?
- **Impact:** Wrong gross/net, bill/balance, or before/after-due selection changes
  recurrence and safety.
- **Resolution:** Complete the independent review in
  [`03-evidence-catalog.md`](03-evidence-catalog.md), especially images 04, 05,
  07, and 14.
- **Status:** PARTIALLY RESOLVED.

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
cost, reproducibility, and offline behavior.

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
