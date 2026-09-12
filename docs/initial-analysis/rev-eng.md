# Reverse-Engineering Financial-State And Forecasting Semantics

Analysis of the 25 solved examples in `dataset/sample_requests.csv`, traced through each
user's profile (`financial_profiles.csv`), event history (`financial_events.csv`), messages
(`messages.csv`), images (`images.csv` + `dataset/media/images/`), and payment options
(`request_payment_options.csv`). Verified numerically with a replay simulator on 2026-09-12.

## 1. Dataset Shape

- 25 samples, one per user `user_01`..`user_25` (exactly one request each; the remaining
  225 users in `requests.csv` share the same data model).
- Each sample user has 80–110 financial events: ~5–6 months of settled history plus a
  handful of non-settled rows (pending / scheduled / cancelled / failed / unrealized).
- Every sample request has 2–4 payment options; 17 of 25 sample users have exactly one
  message; 5 sample users have one blank-amount event resolved by an image.

## 2. Event Status Semantics (confirmed)

| status | cash effect in forecast |
|---|---|
| `settled` | Historical fact; feeds recurrence detection and current balance. |
| `pending` | Debit: **reserves cash immediately** (counted on request date). Credit: **ignored** until settlement date. |
| `scheduled` | Future one-off counted on its `settlement_date` (e.g. next salary, school fee). |
| `cancelled` | Ignored entirely. |
| `failed` | Ignored entirely. |
| `unrealized` | Non-cash (`investment_valuation`, `direction=non_cash`): never counted as cash. |

Evidence:

- `request_01` (user_01): pending fuel debit 567.60 settled 2024-03-05 reduces safe-to-pay;
  cancelled authorization (event_100) and its settled replacement (event_101, linked) show
  the cancellation pair pattern.
- `request_19` (user_19): `event_1784` purchase awaiting refund (settled debit) + `event_1785`
  pending refund **credit** linked to it (user_20 same pattern): pending credits are excluded,
  so the 8,640 refund does not increase capacity before 2026-02-14 (user_20) — see
  `request_20` being `not_affordable` despite the refund.
- `request_21` (user_21): `event_1856` investment valuation `non_cash` / `unrealized` is
  excluded; the prior `investment_purchase` (event_1855) is settled cash.
- `request_25` (user_25): failed subscription debit (event_2287) ignored; salary in USD
  (1,800 on the 15th) converted at the dated rate USD→IDR 15,833.33 on 2024-03-15.

## 3. Currency Semantics

- All output amounts are in `home_currency`.
- Foreign-currency events (e.g. user_25's USD salary) are converted with the
  `exchange_rates.csv` row whose `rate_date` matches the event's settlement date,
  in the stated direction (`from_currency` → `to_currency`).
- The 2024-03-15 USD→IDR rate 15,833.33 ⇒ 1,800 USD = 28,500,000 IDR exactly
  (1,800 × 15,833.33 = 28,499,994 ≈ 28.5M; the minimum-balance math in `request_25`
  explanations is consistent with this conversion).

## 4. Blank Amounts Are Resolved From Images (confirmed)

`problem_statement.md` rule: blank `amount` ⇒ look up `related_event_id` in `images.csv`,
then read the PNG. All five sample-user cases:

| image | event | user | read value | role in decision |
|---|---|---|---|---|
| `image_01` | event_253 | user_03 | Aug-2019 pay slip, Net Pay **IDR 4,365,000** | Confirms routine salary continues at 4,365,000 (message_02 said routine salary confirmed + one-time adjustment shown separately; the one-time 1,964,250 promotion arrears already settled 2019-08-20). |
| `image_02` | event_1442 | user_16 | Rent receipt: total 2,00,000, received 1,00,000, **balance due 1,00,000 INR** | The outstanding rent balance event_1442 (scheduled, settles 2023-08-16) = 100,000 INR debit inside the forecast window. |
| `image_03` | event_1545 | user_17 | Grocery receipt, cash paid **INR 41,272** on 27/02/2026 | Settled grocery expense just before request (2026-03-01); already in the current balance. |
| `image_04` | event_1700 | user_19 | Delivery order, item bill **₹2,854** (delivered 2024-09-03) | Settled grocery order day before request; no forecast impact. |
| `image_05` | event_1786 | user_20 | Airtel bill: amount due till 06-Feb-2026 **704.05 INR** | Pending telecom bill (settles 2026-02-09) = 704.05 debit; request_20 is `not_affordable`, this pending debit contributes. |

## 5. Message Semantics (confirmed)

Every sample message (17 of 25 users) modifies the forecast. Message categories observed:

1. **Salary amount amendment** (message_01 user_02): monthly salary raised to IDR 42,750,000
   effective 2025-08-15 ⇒ forecast salary credits after 2025-08-15 use 42.75M (history shows
   33,345,000). This makes the 3×15,952,906.67 installment plan safe.
2. **Salary amount amendment** (message_06 user_08): next salary reduced to EUR 1,422.85
   (unpaid leave) ⇒ the EUR 996.60 repair cannot be paid now; `wait` until the deadline.
3. **Salary date amendment** (message_05 user_07): confirmed salary date 2024-09-23 replaces
   the earlier payroll date ⇒ `earliest_date_for_full_payment` = 2024-10-23 (the next salary
   day after 09-23), not the historical 15th-of-month cadence.
4. **Salary confirmation** (message_02 user_03, message_11 user_15, message_08 user_11):
   confirms amount/date of next salary; unapproved components (commissions, bonuses) excluded.
   message_11 also confirms first-salary amount 1,661 and date 2026-01-15.
5. **Salary termination** (message_09 user_12): seasonal contract ended, no off-season income
   confirmed ⇒ no projected salary in the 90-day window; full 65,164 payment not safe today,
   so the 3-installment option (which fits before the contract may resume) is chosen.
6. **Salary reduction, temporary** (message_04 user_06): temporary monthly pay 1,037.52
   continues ⇒ forecast salary 1,037.52 (matches settled Nov/Dec events).
7. **Pending / unrealized clarifications**: message_07 user_10 (payout not withdrawable until
   completed ⇒ no income), message_10 user_14 (new recurring childcare payment begins ⇒ extra
   debit), message_14 user_20 (refund initiated but not credited ⇒ pending credit excluded),
   message_15 user_22 + message_16 user_23 (market value not cash; prize not credited ⇒
   unrealized/pending credits excluded), message_17 user_24 (prize credited and closed ⇒
   33,550 windfall already in balance), message_13 user_18 (internal transfer debit+credit
   pair nets to zero; both entries stay visible), message_12 user_16 (rent increased 12% for
   next payment ⇒ event_1442 outstanding balance image + 12% applies forward).
8. message_03 user_04: quarterly bonus still awaiting final approval ⇒ **excluded** from income.

## 6. Spending-Change Semantics (confirmed)

- Only events with `flexibility` of `stoppable`, `reducible`, or `reducible_or_stoppable`
  may be changed; the referenced `event_id` is the **latest occurrence** of that recurring
  stream before the forecast (e.g. event_476 for user_06 = December streaming row; event_989
  for user_11 = latest dining row; event_1815/1816 for user_21 = March rows).
- `reduce_to:<event_id>:<new_amount>` uses the stream's `minimum_allowed_amount` as the
  floor: user_11 event_989 minimum 665,950 ⇒ `reduce_to:event_989:665950` (saves
  1,163,530.49 − 665,950 = 497,580.49). user_21 event_1816 minimum 23.50 ⇒ reduce to 23.50.
- Categories changed always belong to `expense_categories_user_is_willing_to_reduce` (reduce)
  or `expense_categories_user_is_willing_to_stop` (stop). Samples never touch protected or
  unwilling categories: user_06 willing-to-stop=streaming ⇒ stop event_476; user_21
  willing-to-stop includes cloud_storage ⇒ stop event_1815 and reduce streaming.
- Stop vs reduce of the same event never co-occur; two changes reference different streams.

## 7. Decision Outputs By Status (confirmed from all 25 rows)

| status | method | payment_plan | earliest_date_for_full_payment | X = amount_safe_to_pay |
|---|---|---|---|---|
| `affordable_now` (01,09,16) | `full_payment` | `request_date:req` | `request_date` | `requested_amount` |
| `affordable_with_plan` + `installments` (02,07,12,17,22) | `installments` | exact option schedule | later safe single-payment date | < req; max safe today |
| `affordable_with_plan` + `full_payment` (06,11,21) | `full_payment` | `request_date:req` | later safe date | slightly < req (residual gap closed by spending changes) |
| `affordable_with_plan` + `partial_payment` (19) | `partial_payment` | `request_date:X|earliest:req-X` | second-payment date | 28,820 (first partial payment) |
| `affordable_later` / `wait` (03,04,08,13,18,23) | `wait` | `earliest:req` | the wait date | small (bal−minb−reserve) |
| `not_affordable` (05,10,14,15,20,24,25) | `not_recommended` | `none` | empty | small but > 0 |

Key relationships verified numerically:

- `payment_plan` for installments matches a supplied option exactly (amounts, dates from
  `first_payment_date` + `payment_frequency_days`, count = `number_of_payments`).
  request_02: option_05 3×15,952,906.67 from 08-08 every 30 days = target plan.
- For installments, `amount_safe_to_pay` is still reported (>0) even though the chosen plan
  does not start with that amount today — e.g. request_07 X=87,170.56 but plan starts 68,432.
- `earliest_date_for_full_payment` is measured **independently of the chosen method**
  (request_12: installments chosen, earliest = request_date 2026-04-05 because a single full
  payment is already safe, but the user only considers `partial_payment|installments`).
- For `wait` rows the plan is a single payment on `earliest_date_for_full_payment`, which is
  always ≤ `desired_completion_date` and almost always a salary day (the 15th) or the
  message-amended salary date (request_07 → 10-23).

## 8. Forecast Engine Semantics (derived + verified)

Reconstruction of the 90-day safety check:

1. Start from `current_available_balance`.
2. Reserve known non-settled debits: `pending` (immediately) and `scheduled`
   (on `settlement_date`) within the window. Pending credits, failed, cancelled, unrealized
   rows are excluded.
3. Add known future one-off income: `scheduled` income rows count on `settlement_date`.
4. Project recurring streams (per category, from `settled` history): each stream repeats at
   its observed cadence with a conservative amount (mean of recent occurrences; salaries use
   the confirmed amount from messages/images where present).
5. Streams whose history indicates discontinuation (a "final" event, no recent occurrence,
   or an explicit end message) are **not** projected. Examples: user_05 salary ended
   (event_390 "Final employer payroll"), user_10 platform payouts stopped (message_07),
   user_13 second household income discontinued after February, user_12 seasonal contract
   ended (message_09).
6. Walk day by day; the plan is safe only if the projected balance never drops below
   `minimum_balance_to_keep` across the 90-day window.
7. `earliest_date_for_full_payment` = first date D such that paying the full
   `requested_amount` on D keeps the check green through the window. Same-day ordering:
   salary credits land before same-day debits (request_03: pay on the 11-15 salary day is the
   first safe date; verified numerically).
8. `amount_safe_to_pay` = maximum payment on `request_date` under the same check, capped at
   `requested_amount`.

### Verified numeric matches

- request_01: X = 25,256 exactly (all recurring categories projected; min balance 24,264 ≥ 18,000).
- request_03: earliest = 2019-11-15 exactly (first date a full payment survives the window).
- request_09, 12, 16, 17 (≈), 20(no), 14/15/20/24/25 (empty) match; request_17 X matches to
  59.77 of 243,849.58 (0.02%).
- request_19: X = first partial payment; plan chosen over installments because user excludes
  `full_payment` and partial has no financing fee (39,660 vs option_53 total 41,246.40).

### Known gaps (approximations)

- Exact projection details (cadence = median vs mean gap, amount = last-6 mean vs other,
  treatment of secondary incomes, multi-stream categories) could not be pinned to the cent
  for all 25 rows. Several X values (05, 08, 13, 15, 18) sit between "safety-only" and
  "reserve-based" models, indicating the ground truth reserves roughly 30–60 days of
  conservative spending in addition to the minimum balance. Directional behavior, plan
  choices, statuses, and dates match; absolute X values for `wait`/`not_affordable` rows
  vary from our simulation by up to ~2×.
- The generator appears to compute X conservatively (favoring smaller safe amounts) — every
  discrepancy we found is our simulation being *more* optimistic, never less.

## 9. Plan Selection (ranking confirmed on 19/20/11/02/07)

1. Eligibility gate: only methods in `payment_methods_user_will_consider` may be recommended
   (request_19: `partial_payment|installments` ⇒ `partial_payment` beats safe `full_payment`;
   request_07/17/22: methods = `installments` only ⇒ installments despite safe full payment).
2. `wait` requires `full_payment` in the user's methods and full payment becoming safe later.
   All six wait rows have `full_payment` in their methods list.
3. `not_affordable` fallback when no eligible safe plan completes by
   `desired_completion_date` (request_14: user allows only `partial_payment`, X=597.74 > 0
   but completion impossible ⇒ `not_recommended` with explanation "although X is available
   today, the full amount cannot be completed safely within 90 days").
4. Ranking among safe eligible plans: (1) complete by deadline, (2) no spending changes,
   (3) minimize total paid, (4) start earlier, (5) fewer payments, (6) lowest
   `payment_option_id`. request_19 picks partial (no fee) over installments (fee 1,586.40+).
5. Spending changes are used only when they flip a plan to safe AND rank above alternatives
   (request_06/11/21 are the only change cases; request_11 uses `reduce_to` to make
   full_payment safe since user accepts only `full_payment`).

## 10. Explanation Style (all 25 rows)

- `affordable_now`: "Pay X today. This leaves at least <minb> available over the next 90 days."
- `wait`: "Pay <req> in full on <date>. Paying earlier would take the balance below the <minb> minimum."
- `installments`: "Use N installments of <amt>, starting <date>. This leaves at least <minb> available."
- `partial_payment`: "Pay X today and the remaining <rem> on <date>. This completes the full request and keeps the <minb> minimum protected."
- `not_affordable`: "Do not make this payment by <deadline>. None of the available options keeps the <minb> minimum protected." (variant for X>0: "Although X is available today, the full amount cannot be completed safely within 90 days.")
- spending-change rows prepend "Stop the …" / "Reduce the … to …, then pay … today."

## 11. Implications For The Product Implementation

1. Build a deterministic forecast engine with the semantics in §2, §8; use the model layer
   only for text/image extraction (salary amendments, blank amounts) that feeds the same
   deterministic engine.
2. Never let model output set `amount_safe_to_pay` directly; compute it from the forecast.
3. Message parsing must classify: amount amendment, date amendment, income start/stop,
   pending/unrealized clarifications, one-off extras (new recurring debits).
4. Image extraction needed only for blank-amount events (7.4% of events in the full dataset
   are blank-amount candidates: 5 of 25 sample users, 16 images for 250 users).
5. Payment-option selection is fully rule-based given the forecast (§9); installments must
   be validated against `max_installment_months` (option months ≤ profile cap) — request_02
   uses 3 months ≤ 7; request_03's 21/24-month options are ineligible (max_inst=2).
6. Validation gate: two-payment partial rule, option-match rule, chronological plan,
   `0 ≤ X ≤ req`, `earliest == request_date` iff `affordable_now`.