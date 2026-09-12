# Assumptions & Ambiguities — Buy or Wait?

> **Supplemental / lower authority.** This note is research input, not a
> decision record. Its useful discriminators and conflicts were reconciled into
> [`05-todo-and-analysis-runbook.md`](05-todo-and-analysis-runbook.md) under
> `IA-006`. Keep claims here as hypotheses until the numbered packet records a
> reproducible resolution.

Companion to [`dataset-stats.md`](dataset-stats.md). Each entry lists the
ambiguous rule, the interpretations considered, the assumption adopted for the
solution, and — most importantly — **which public samples (`request_01..25`)
discriminate between competing interpretations**. Evidence quotes cite the
exact dataset fields probed on 2026-09-12. Sample users (01–25) are the only
labeled rows; eval users (26–275) are disjoint.

Legend: ✅ = sample confirms assumption; ⚠️ = sample constrains but does not
fully pin the rule; ❌ = no public sample discriminates — treat as pure
assumption and prefer the literal text of `problem_statement.md`.

---

## A. Forecast & balance model

### A1. Does confirmed salary income continue in the 90-day forecast?

- **Ambiguity.** The 90-day safety check says "recurring income and expenses".
  Most users have *no* `scheduled` income row beyond their history (228/275
  users have none), yet salaries settle monthly like clockwork. Interpretations:
  1. Project salary on the historical cadence (monthly on the settlement
     weekday/date) through the horizon.
  2. Count only income that appears as a `scheduled` row or is confirmed by a
     message; no extrapolation.
- **Evidence.** `request_05` (user_05, 2025-11-06, ZAR 15,488; balance
  46,475.10, minimum 13,100): monthly settled spend ≈ 12,800 and salary 14,740
  on the 15th, but ground truth is `not_affordable` with `amount_safe_to_pay`
  = **737**. That number is only reachable if *zero* future salary is credited
  (≈ 12,800/mo burn for 3 months leaves ~32,638 of headroom to distribute —
  far less than the 33,375 + salary continuation would give). Conversely
  `request_02`/`request_07` (installments spanning 3 months) stay safe only
  under continued income. ✅ Interpretation 2 for users without a scheduled
  row: **do not invent future salary**; treat the last settled salary as
  historical unless a `scheduled` row or message confirms the next credit.
- **Corroboration.** `financial_events` contains exactly one `scheduled`
  salary per user for only 47 users ("the next confirmed salary" per the
  problem statement), and messages repeatedly *withhold* confirmation
  ("quarterly bonus … not approved", message_03/message_48; "payout is still
  pending", message_07/message_19). The dataset is deliberately stingy about
  future income.

### A2. Which `status` values enter the forecast?

Vocabulary observed: `settled` (25,148), `pending` (71), `scheduled` (70),
`cancelled` (22), `failed` (21), `unrealized` (10).

- **Adopted (all ✅ or ⚠️):**
  - `settled` debits before `request_date` → already in `current_available_balance`; not re-subtracted. ⚠️ Cannot be proven exactly, but required for any sane arithmetic (`request_16`: balance 362,370 minus rent 57,100 etc. must not double-count).
  - `pending` debits → reserve (subtract at `settlement_date`); `pending` credits (refunds, prizes) → **ignore** ("Ignore pending credits", §90-Day Safety Check; `request_20` has a pending refund of 8,640 that message_14 says has *not* reached the account, yet status is `not_affordable` — counting it would change nothing here, but the rule text is explicit). ✅ rule text; ⚠️ no sample where counting a pending credit flips the verdict.
  - `scheduled` debits → subtract at `settlement_date` (e.g. `event_357`, `event_2166`). ⚠️ constrains but no sample flips on this alone.
  - `scheduled` credits → include (the "next confirmed salary"). ⚠️
  - `cancelled`/`failed` → ignore entirely (`event_557` cancelled shopping 66 EUR on 2025-12-30 for `request_06`; `event_2287` failed utilities for `request_25`; `event_438` failed utilities for `request_05`). ✅ problem statement lists both.
  - `unrealized` (investment_valuation, `direction=non_cash`) → ignore as cash (`event_1960` + message_15: "No units have been sold and no cash proceeds have been generated"). ✅
- **Discriminators.** `request_06` (safe = 603.30 of 620.40): with balance 1,942.40 and minimum 800, headroom is 1,142.40; reaching safe = 603.30 requires reserving the *cancelled* 66 EUR shopping debit to be excluded and the December recurring tail to be counted — i.e., cancelled exclusion materially moves `amount_safe_to_pay`. ✅

### A3. How are recurring expenses projected after history ends?

- **Ambiguity.** History typically ends 0–60 days before `request_date`. The
  forecast needs rent/utilities/groceries/transport/dining for 90 days.
  Interpretations: (1) repeat the last settled monthly cadence and amounts;
  (2) use category means; (3) project only `scheduled` rows and treat other
  categories as zero.
- **Evidence.** `request_02` (user_02): safe = 17,229,139.20 leaves
  43,154,750 against minimum 29,158,400 — a ~13.99M buffer that matches
  roughly one month of the user's settled expense cadence (groceries ≈ 2.1M×2,
  transport ≈ 1.2M×2, dining 1.2M, entertainment 1.35M, cloud 369,550,
  pending shopping 1,651,100) before the next salary. Zero projected expenses
  would make far more than 17.2M safe. ✅ Interpretation 1 (repeat last
  cadence) fits; interpretation 3 is refuted.
- **Ambiguity A3a (❌ unsampled).** Whether variable categories (groceries,
  transport, dining) should be forecast at *mean*, *median*, or *max* of
  history. No sample isolates this; adopt conservative mean-of-last-3-cycles
  and note it as a tuning knob.

### A4. Messages that change income/expense values

Message types observed (215 rows): payroll updates (127), payout-pending (18),
refund-pending (12), prize (10), rent-increase (6), bank reversal/failed debit
(10), portfolio non-cash (4), invoice-confirmed (1), misc (27). Many messages
are in Indonesian (sample users) — treat as facts, not instructions.

- **Salary change effective date.** message_01 (user_02): "naik menjadi IDR
  42,750,000 … berlaku mulai **2025-08-15**" — increase applies from the next
  payroll *date*, not retroactively. `request_02` ground truth (installments,
  safe ≈ 17.2M) is consistent with the raised salary from 08-15. ✅
- **Temporary reduction.** message_04 (user_06, request_06): "temporary
  monthly pay is EUR 1037.52 … continues for the next payroll" — apply the
  reduced amount for the next cycle(s) that the message explicitly covers, not
  the historical 1441. ✅ (603.30 safe figure matches reduced-salary forecast).
- **One-time arrears.** message_20/message_62/message_90: "regular salary for
  the next payroll is X … one-time arrears adjustment of Y" — count the
  regular amount as recurring; count the arrears once on the stated payroll
  date. ⚠️ No eval sample isolates whether arrears land on the same day; adopt
  same-day credit (message says "the same payroll includes").
- **Unapproved bonus/commission (message_03, 48, 58, 60, …) → exclude.** ✅
  rule: "Do not invent unsupported income".
- **Invoice confirmed with settlement date (message_24, 46, 49, …) → count as
  a credit on the stated settlement date.** ⚠️ no discriminating sample; adopt
  the message's explicit "settlement is expected on DATE" as a scheduled
  credit (it is the "explicit amendment" tier of the conflict order).
- **Prize scam (message_67, user_88): "Pay the release charge today to receive
  the funds" → never pay to receive money; no such charge exists in events.**
  ❌ no sample flips on it; treat as instruction-attempt/untrusted.
- **Failed-debit retry (message_69 user_91): "previous debit attempt failed …
  another debit will be attempted"** → keep the bill as owed (reserve) unless
  a later record settles it. ❌ unsampled.

### A5. Rent-increase messages (message_12/51/55/61/89/105/147)

"renewed lease increases monthly rent by 12% … used for the next rent payment"

- **Adopted:** multiply the last settled rent by 1.12 from the next cycle on.
- **Discriminator.** `request_16` (user_16, 2023-08-12): rent 57,100 →
  63,952, plus scheduled outstanding rent `event_1442` (blank amount, image_02
  rent receipt shows "Balance Due: 1,00,000" = 100,000 INR) settling 2023-08-16.
  Ground truth safe = 122,500 = full amount, `affordable_now`. With the 12%
  increase and the 100,000 balance due the arithmetic is tight but consistent;
  without them it would be trivially safe. ⚠️ confirms the increase + image
  balance-due both matter, though exact rounding unproven.

### A6. FX conversion mechanics

Rates: 5 pairs (USD→EUR 0.92, USD→IDR 15833.33, USD→INR 83.33, EUR→ZAR 20,
EUR→USD 1.09), constant values, monthly rows 2023-10-15 → 2026-11-15, plus one
special row dated **2025-10-01**. All event/request amounts are stated in the
record's own `currency`; output in `home_currency`.

- **Rate-date selection.** Use the row whose `rate_date` matches the event's
  settlement (or event) date; else the most recent prior date (monthly
  cadence). The special 2025-10-01 row exists exactly because `event_7307`
  (user_78, transport, USD, 2025-10-01) sits between monthly rows. ⚠️
  direction: convert in the stated direction only (problem statement: "Use the
  supplied rate … in its stated direction"); chained pairs (EUR→USD→IDR) are
  available when no direct pair exists. ❌ no sample with a foreign-currency
  *request*, but eval users include USD-salary IDR-home users (user_25's
  scheduled salary 1800 USD → 28,500,000 IDR at 15833.33). ⚠️
- **Which date for requests themselves?** Requests are always in
  `home_currency` (verified 250/250), so no conversion needed at decision time.
  ✅

---

## B. Status & method semantics

### B1. `affordable_now` ⇔ full payment today is safe **and** `full_payment` ∈ user methods

- **Evidence.** All three `affordable_now` samples (01, 09, 16) have
  `full_payment` in `payment_methods_user_will_consider`, plan =
  single entry on `request_date`, `earliest = request_date`. ✅
- **Corollary.** `request_12`: safe = 65,164 = full, earliest = 2026-04-05 =
  `request_date`, but user considers only `partial_payment|installments` →
  `affordable_with_plan` + `installments`. ✅ Confirms (a) earliest-date is
  capability, not preference ("It may equal request_date even when the
  selected recommendation is installments"), and (b) method eligibility gates
  the *status label*, not just the method column.

### B2. `affordable_later` + `wait` requires `full_payment` ∈ user methods

All wait samples (03, 04, 08, 13, 18, 23) accept `full_payment`. ✅ Rule text
agrees ("`wait` is eligible when full payment becomes safe later and the user
accepts `full_payment`").

### B3. `wait` chosen even when an installment option exists and is safe

`request_03`: user accepts all three methods, installment option_09 (21 pay ×
308,541.90, ~20 months) exceeds `max_installment_months` = 2 → ineligible;
option_10 (24 pay) likewise. So `wait` is forced. ⚠️ constrains ranking; note
it does *not* prove "wait beats installments" when both are eligible — see B4.

### B4. Ranking among safe eligible plans

Rule order: complete by deadline → no spending changes → minimize total paid →
start earlier → fewer payments → lowest `payment_option_id`.

- `request_02` (max months 7): option_05 (3×15,952,906.67, total 47,858,720.01)
  beats option_07 (18 payments, exceeds 7 months → ineligible) and
  full_payment option_06 (not safe). ✅
- `request_17` (max months 3): option_47 (3×95,194.67) selected over option_49
  (18 pay, ineligible). ✅
- `request_22` (max months 6): option_61 (3×253.59) over option_63 (15 pay,
  ineligible). ✅
- **⚠️ Unsampled corner:** when full_payment and a fee-free installment are
  both safe and eligible, "minimize total paid" should pick full_payment; no
  sample shows this head-to-head (all chosen installment plans were forced).
  Adopt rule order literally.
- **`max_installment_months` semantics (⚠️ partially pinned):** samples reject
  options whose payment count exceeds the limit even when the *calendar span*
  is shorter (option_53 = 2 payments 28d apart vs max 2 passes for
  `request_19`… but request_19 chose partial instead). Interpretation adopted:
  **number_of_payments ≤ max_installment_months** (a 3-payment plan over 60
  days ≈ 2 months is still rejected at max 2). `request_22` (option_61, 3
  payments ≈ 56 days, max 6) passes; no sample isolates calendar-span vs
  count at the boundary. ❌ boundary itself unsampled.

### B5. `partial_payment` shape and gates

Rule text: only when `allows_partial_payment` = true, user accepts the method,
`0 < safe < requested`, and `earliest ≤ desired_completion_date`; plan is
exactly two entries (`safe` on request_date + remainder on earliest); need not
match an option.

- `request_19`: safe 28,820; remainder 10,840 on 2024-09-15; earliest ≤
  desired (2024-10-04). ✅ Exactly the two-entry shape.
- **Why not installments instead?** user_19 methods = `partial_payment|
  installments`, max months 2; option_53 = 2×20,623.20 + fee 1,586.40 (total
  42,124.60) vs partial total 39,660 → "minimize total paid" picks partial. ✅
  Ranking criterion 3 in action.
- **⚠️ Unsampled gate:** a case where partial is legal but earliest >
  desired_completion_date. `request_14`/`request_24` look close (partial
  allowed, method accepted) but they are `not_affordable` because earliest is
  *empty* (full never safe in horizon) — which implies the two-payment plan
  cannot be formed. Adopt: partial requires a non-empty earliest within
  desired_completion_date. ⚠️

### B6. `not_affordable` with positive `amount_safe_to_pay`

Five samples (05, 10, 14, 15, 20, 24, 25 — 7 of 25) all have safe > 0, plan
`none`, empty earliest, `not_recommended`. Two distinct causes observed:

1. No eligible method can complete the request in the horizon
   (`request_10`: partial+installments only, installments exceed max months;
   `request_14`/`request_24`: partial-only, full never safe). ✅
2. Full request not completable at all (`request_05`, `request_15`,
   `request_20`, `request_25`). ✅

Explanation template: "Although X is available today, the full amount cannot be
completed safely within 90 days" vs "None of the available options keeps the
… minimum protected". Mirror these two styles. ✅

### B7. `amount_safe_to_pay` when status ≠ affordable_now

Samples show safe > 0 for every status (`affordable_later` rows: 873,000 /
8,401,800 / 284.57 / 433.40 / 462 / 9,152; `not_affordable` rows: 737 / 12,700
/ 597.74 / 83.05 / 5,400 / 13,420 / 1,425,000). Adopt: always report the
today-capacity before optional changes, independent of the recommended method
(and never 0 merely because we recommend wait). ✅ Strong signal.

### B8. `earliest_date_for_full_payment` horizon cap

- It equals `request_date` for `affordable_now` (all ✅).
- It can be the *deadline itself* (`request_03` 2019-11-15, `request_08`
  2025-04-15, `request_18` 2026-09-15 — each = desired_completion_date; all ≤
  request_date + 90). ✅
- Empty when never safe within horizon (`not_affordable` set). ✅
- **❌ Unsampled:** whether earliest may fall beyond request_date + 90 days.
  Every sample value lies within the 90-day window; adopt the 90-day cap.

### B9. Spending changes: gating, shape, and interplay

- Only `flexibility ∈ {stoppable, reducible, reducible_or_stoppable}` events
  in categories the user is willing to stop/reduce may appear; `reduce_to`
  must respect `minimum_allowed_amount` (`event_989` min 665,950 → sample
  `reduce_to:event_989:665950` = exactly the floor; `event_1816` min 23.50 →
  sample `reduce_to:event_1816:23.50`). ✅ (floors are respected; whether the
  solver may reduce *below* the floor is refuted — it never does).
- `stop` only on `stoppable` (or `reducible_or_stoppable`?) events —
  `event_476`/`event_1815` are `stoppable`; `event_1816` is
  `reducible_or_stoppable` and got *reduced*, not stopped, while `event_1815`
  got *stopped* in the same row — consistent with "stopping and reducing the
  same financial event are mutually exclusive" + different events used. ✅
- Category willingness gates: user_21 willing to stop `streaming|cloud_storage`
  → stopped cloud_storage (event_1815), reduced streaming (event_1816). user_06
  willing to stop `streaming` → stopped streaming (event_476). user_11 willing
  to reduce `dining|entertainment` → reduced dining (event_989). ✅ Never a
  change outside the user's lists.
- **Ranking interplay.** Changes are the *last resort*: `request_06` (safe
  603.30 < 620.40) uses `stop` to enable full payment today rather than
  installments/wait; `request_11` (safe 12,510,645 < 13,110,000) uses
  `reduce_to` for full payment today, though the horizon also holds salary
  raises. Both keep `earliest` later than today (01-15 / 07-15) — i.e. the
  spending change buys *today*-capacity, and earliest-without-changes stays
  reported. ✅ Interpretation adopted: `earliest_date_for_full_payment` is
  always computed *without* changes (rule text), while `amount_safe_to_pay`
  is also without changes ("before optional spending changes") — the changed
  world only justifies the method/plan.
- **⚠️ Unsampled:** whether a change may be used to make an *installment*
  plan safe (samples only pair changes with full_payment), and whether
  `reduce_to` mid-horizon applies to every future occurrence of the recurring
  event or just one. Adopt: applies to all occurrences within the horizon
  (the sample explanations phrase it as an ongoing change: "Reduce the
  weekend food delivery to IDR 665,950" — present tense, ongoing).

### B10. Plan-date arithmetic for installments

Sample plans use the option's `first_payment_date` then
`+payment_frequency_days` exactly (option_05: 08-08 → 09-07 → 10-07;
option_19: 09-12 → 10-10 → 11-07; option_33: 04-19 → 05-20 → 06-20; option_61:
12-08 → 01-05 → 02-02). No drift, no month-end snapping. ✅

### B11. Payment-plan formatting

`payment_plan` for full_payment is a single `request_date:amount` entry even
when status is `affordable_with_plan` (request_06, 11, 21) or when the method
is `wait` (a single future-date entry, request_03/04/08/13/18/23). `none`
only for `not_recommended`. ✅

---

## C. Data-reconciliation ambiguities

### C1. Blank amounts ↔ images

All 16 blank-amount events have a matching image (via
`images.related_event_id`); no blank without an image. Images are real-world
receipts (pay slip, rent receipt with "Balance Due 1,00,000", delivery item
bill ₹2,854.00, restaurant tax invoice ₹8,528.10, maintenance receipt
₹15,339.00). Adopt: extract the *total payable/balance-due* figure, respect
the receipt's date as the event's effective amount-date; do not treat blank
as zero. ✅ (mechanism confirmed by problem statement + all 16 cases; per-image
OCR fidelity is an engineering risk, not an ambiguity).

### C2. `linked_event_id` chains

58 rows: refunds → original purchase (settled or pending), investment
valuation/sale → purchase, repeated expenses, scheduled debt payments. Adopt:
a pending refund linked to a settled purchase is *not* cash until settled
(ignore credit, keep original debit); an investment sale that has *settled*
becomes cash (message: "proceeds … have settled in the cash account"). ⚠️
(no sample flips on the settled-sale case; message_207-style texts support it).

### C3. Message-vs-event precedence

Apply the stated order (explicit amendment > newer same-source > settled >
safer). Concrete recurring cases: salary-increase messages override the last
settled salary (A4); rent-increase messages override last rent (A5);
pending-refund messages keep the refund out of cash (A2); prize/payout
messages keep unapproved money out (A4). ✅ by rule text; ⚠️ each individual
flip is not isolated by a sample except salary/rent (request_02, request_16).

### C4. Options coverage & `full_payment` anchor

Every request 01–275 has 2–4 options, always including one `full_payment`
whose amount = `requested_amount` and first date = `request_date`
(spot-checked 275/275 pattern). Adopt: treat the `full_payment` option as the
canonical full-payment plan; installments must match an option exactly (rule
text). ✅

### C5. Requests without any matching supporting records

Some eval requests may have no messages/images/linked events — the pipeline
must degrade to profile + events only. ✅ structural (only 128 of 250 eval
requests have messages; 16 images total).

---

## D. Output-format micro-rules (from samples)

1. Decimal formatting: keep the dataset's natural precision — `25256`,
   `87170.56`, `28820` (trailing `.00` not shown in plan amounts: `25256` not
   `25256.00`, but `620.40` keeps cents). Adopt: output the numeric value as
   computed, trimmed of trailing zeros except two-decimal currency amounts
   that have them. ⚠️ cosmetic; scoring likely numeric-tolerant.
2. `payment_plan` amounts use the *option's* per-payment amount for
   installments (e.g. 15,952,906.67 = total/3 including financing fee? No —
   option_05 per-payment 15,952,906.67 ×3 = 47,858,720.01 = `total_payable_
   amount` including the fee. Adopt exactly the option's `payment_amount`). ✅
3. `decision_explanation` styles: five observed templates (affordable-now /
   installments / wait / not-recommended ×2 / spending-change). Reuse them
   verbatim-structurally. ✅
4. `spending_changes_needed` ordering: `stop:` entries before `reduce_to:`
   entries (request_21). ⚠️ single occurrence.
5. Multiple changes across different events allowed (request_21); never two
   actions on the same event. ✅

---

## E. Open questions with no public discriminator (risk register)

| # | Question | Adopted default | Risk if wrong |
|---|----------|-----------------|---------------|
| 1 | Exact per-day forecast grid (daily vs monthly buckets) affects `safe` pennies | Daily ledger from `request_date`, events at settlement dates | Low — amounts likely graded with tolerance |
| 2 | Variable-expense projection statistic | Mean of last 3 settled cycles per category | Medium — shifts safe amounts on ~half the dataset |
| 3 | Does the 90-day window end at `request_date + 90` inclusive? | Inclusive | Low |
| 4 | Whether `wait` beats a safe fee-free installment when both eligible | Rule order (deadline, no changes, min total) — installments have fees, so wait/full usually wins on cost anyway | Low |
| 5 | Whether `reduce_to` needs to be ≤ current amount (never increase) | Yes, never increase | Low |
| 6 | Whether spending changes count toward `earliest_date_for_full_payment` | No — earliest is without changes | Medium |
| 7 | Partial-payment remainder date strictly `earliest_date_for_full_payment` even if an earlier safe date exists for the *remainder* | Yes (rule text pins it) | Low |
| 8 | Rounding of converted foreign amounts | Round half-even to 2dp at conversion time | Low |
| 9 | Whether `investment` requests may use installment options (they appear in options for some investment requests, e.g. request_120) | Yes — method eligibility follows profile, not request_type | Medium |
| 10 | Whether `emergency_expense` bypasses user method restrictions | No evidence; adopt no bypass | Low |

## F. Discriminator cheat-sheet (sample → ambiguity resolved)

| Sample | What it discriminates |
|---|---|
| request_01, 09, 16 | `affordable_now` ⇔ full_payment eligible + safe; earliest = request_date |
| request_02 | salary-increase message effective date; installment date arithmetic; min-total ranking among installments |
| request_03 | installment months-cap rejection forces wait; earliest can equal deadline |
| request_04 | wait chosen over partial despite `allows_partial_payment=true` (user excludes partial) |
| request_05 | no-salary-extrapolation forecasting (safe = 737); failed events ignored |
| request_06 | cancelled events ignored; `stop` change enables full_payment today; earliest stays without-changes (2026-01-15) |
| request_07 | installments when partial is allowed but user prefers installments-only; 28-day frequency arithmetic |
| request_08, 13 | wait with earliest = deadline; partial allowed but not eligible for user |
| request_10, 24 | method-eligibility-driven `not_affordable` with positive safe amount |
| request_11 | `reduce_to` floor = `minimum_allowed_amount`; change + full_payment same day; earliest unchanged (2025-07-15) |
| request_12 | earliest = request_date while recommending installments (capability vs preference) |
| request_14 | partial gated by non-empty earliest ⇒ not_affordable |
| request_17 | 3-payment option under max-months cap; earliest between installment dates |
| request_19 | partial two-payment shape; partial beats installments on total cost |
| request_21 | two changes (stop + reduce) on different events; floors respected |
| request_22 | small-amount installments vs max-months check |
| request_25 | foreign-currency scheduled salary conversion context (USD salary, IDR home) |
