# Initial Dataset Analysis — Buy or Wait?

> **Supplemental / lower authority.** Counts and derived rules in this note
> are leads, not the canonical profile or behavior contract. Scope/count
> differences and behavior conflicts are catalogued under `IA-006` in
> [`05-todo-and-analysis-runbook.md`](05-todo-and-analysis-runbook.md). Re-run
> the assigned deterministic checks before relying on a disputed value.

Statistical characterization of `dataset/` (participant-facing files only). All
numbers computed directly from the CSVs; derived insight for the solution
design follows each section. Analysis date: 2026-09-12.

## 1. File Inventory

| File | Rows | Notes |
|---|---|---|
| `requests.csv` | 250 | 1 request per user, exactly; 250 distinct users |
| `sample_requests.csv` | 25 | `request_01..25`, users `user_01..25` — calibration set with ground truth |
| `financial_profiles.csv` | 275 | all users incl. the 25 sample users |
| `financial_events.csv` | 25,342 | 56–129 events/user (mean 92) |
| `request_payment_options.csv` | 790 | covers `request_01..request_99` (samples + eval) |
| `messages.csv` | 215 | 116 linked to eval requests, 28 of those also to an event |
| `images.csv` | 16 | all 16 resolve to a blank-amount event; PNGs in `dataset/media/images/` |
| `exchange_rates.csv` | 134 | 5 pairs, monthly, 2023-10-15 → 2026-11-15 |

Key structural fact: **sample users (01–25) are disjoint from eval users
(26–275)**. Sample requests are the only source of labeled outputs.

## 2. Requests (250 eval rows)

- `request_type` (near-uniform): purchase 28, travel 28, education 28,
  family_transfer 28, debt_repayment 28, housing 28, investment 28,
  emergency_expense 27, other 27.
- `allows_partial_payment`: false 170 (68%) / true 80 (32%).
- `request_date` spans 2023-01-20 → 2026-09-04 (synthetic, scattered).
- `desired_completion_date − request_date`: min 6, median 65, p75 72, max 86
  days — always **≤ 90**, consistent with the 90-day safety horizon.
- `requested_amount` in home currency only (verified: text currency mention ==
  profile `home_currency` in 250/250 rows). Range 199.89 → 83.9M (currency
  scale driven, IDR dominates the top).
- `requested_amount / last settled salary`: median 1.15, p75 2.1, mean 380
  (outliers); 25% of requests exceed ~2× monthly salary.
- Headroom `(balance − minimum_balance)`: ≥ requested amount for only 139/250
  (56%); median headroom ≈ 1.14× requested. So roughly half the dataset
  requires a plan/wait/not-affordable outcome.

## 3. Financial Profiles (275 users)

- `home_currency`: INR 67, EUR 62, IDR 55, ZAR 51, USD 40.
- `payment_methods_user_will_consider` (multi-label): full_payment 163,
  installments 156, partial_payment 139. **Users with no full_payment in their
  set can only be served via installments/partial/wait/not_recommended.**
- `max_installment_months`: blank 119 (no installments allowed in practice),
  else 2–12 (median ~6.5). 173/469 installment options exceed their user's
  max — those options are ineligible.
- `financial_priorities`: emergency_savings 171, education 94,
  retirement_investment 61, debt_repayment 56, family_support 49, travel 46,
  healthcare 44, housing 29.
- Protected categories (profile-level): rent 232, groceries 166, transport 109,
  utilities 105, education 60, insurance 46, debt_repayment 56, housing 43,
  healthcare 44, family_support 25.
- Willing to reduce: dining 153, shopping 72, streaming 66, entertainment 44,
  gym 14. Willing to stop: cloud_storage 109, streaming 84,
  music_subscription 58, delivery_membership 41, gym 12.
  → User willingness aligns exactly with which categories carry flexible events.

## 4. Financial Events (25,342 rows)

### Types / status / flexibility

- `event_type`: expense 20,525; subscription 2,488; income 1,696;
  debt_payment 567; investment_purchase 29; refund 22;
  investment_valuation 10 (non_cash); investment_sale 5.
- `direction`: debit 23,609; credit 1,723; non_cash 10.
- `status`: settled 25,148 (99.2%); pending 71; scheduled 70; cancelled 22;
  failed 21; unrealized 10.
- `flexibility`: fixed 21,138; reducible 2,682; stoppable 1,297;
  reducible_or_stoppable 225. **Only settled rows are ever flexible.**
- `minimum_allowed_amount` present for exactly the 2,907 reducible-ish rows;
  ratio to current amount: median 0.50, range 0.357–0.694 → **reduce_to floors
  at ~50% of current spend**.

### Status × flexibility (all non-settled rows are fixed)

| status | settled | pending | scheduled | cancelled | failed | unrealized |
|---|---|---|---|---|---|---|
| rows | 25,148 | 71 | 70 | 22 | 21 | 10 |

- pending/scheduled are: expense 79 (incl. 19 exactly on request_date),
  refund 8, income 47 (next salary), debt_payment 7.
- **All 124 pending/scheduled rows belonging to request users settle AFTER the
  request_date** (event_date may be before, but settlement_date is after) —
  they are future cash movements in the 90-day forecast.
- cancelled/failed always pair with a same-amount successor (see §4 Linked
  events). No orphan duplicates.

### History structure (critical for forecasting)

- Per user, settled history spans **exactly ~175 days** (169–178) ending 0–6
  days before `request_date`. There is **almost no future data**: only 42/250
  request users have a single future event (the next scheduled salary).
- Therefore the 90-day forecast must be **built by extrapolating recurring
  series** from ~6 months of history: cadence detection + conservative amount
  estimate + next-due projection.
- Salary cadence: gaps cluster at 30–31d (monthly, 904 gaps) and 14/15d
  (semi-monthly, 507); a handful of weekly (5–7d) and 2 outliers at 92d.
  Amounts constant per user (only 12/275 users show >1 distinct amount —
  driven by employer-message amendments).
- Recurring expense cadences (user+category median gaps): monthly (25–32d,
  1,643 groups), weekly (3–10d, 446), biweekly (10–14d, 206), ~21–25d (149).
  Group sizes: 5 (monthly), 13/26 (weekly/biweekly), 9/18 (≈21d/10d series).
- Amount behavior in series: e.g. user_27 groceries identical amounts;
  utilities/dining/transport vary ±3–7% (essentials w/ jitter). Conservative
  estimate = max (or high percentile) of recent occurrences.

### Categories

groceries 5,812; transport 5,626; dining 3,479; salary 1,690; utilities 1,452;
rent 1,355; cloud_storage 833; shopping 813; streaming 683; debt_repayment 553;
entertainment 521; insurance 456; music_subscription 451; healthcare 356;
delivery_membership 351; education 306; housing 246; gym 170;
family_support 125; investment 44; work_expense 14; windfall 6.

### Flexibility × category (who can change what)

| category | fixed | reducible | stoppable | reducible_or_stoppable |
|---|---|---|---|---|
| dining | 1,554 | 1,925 | 0 | 0 |
| shopping | 453 | 360 | 0 | 0 |
| entertainment | 301 | 220 | 0 | 0 |
| streaming | 136 | 127 | 215 | 205 |
| gym | 60 | 50 | 40 | 20 |
| cloud_storage | 286 | 0 | 547 | 0 |
| music_subscription | 161 | 0 | 290 | 0 |
| delivery_membership | 146 | 0 | 205 | 0 |
| essentials (rent/utilities/groceries/transport/education/healthcare/insurance/family_support/debt) | all fixed | 0 | 0 | 0 |

- Flexible series occur with period-5 series per user+category (monthly
  cadence), matching the profile willingness lists. A user has on average ~16
  flexible events across ~4–5 category series.
- Per user+category, flexibility label is never mixed (0 mixed groups).
- **No flexible event exists on/after the request date** — changes must be
  applied to *projected* future occurrences of the historical series.

## 5. Linked Events (58 chains, all length 2)

| target → child | count | meaning |
|---|---|---|
| expense → refund (credit, same amount) | 22 | full refund of a purchase |
| expense → expense (settled/scheduled/pending child) | 14 | child is the *resolved* copy: 8 "Settled card purchase" after cancelled parent, 6 "Scheduled bill payment retry" after failed parent |
| investment_purchase → investment_valuation (non_cash, unrealized) | 10 | unrealized value — ignore as cash |
| debt_payment → debt_payment | 7 | retry pattern, same as bills |
| investment_purchase → investment_sale (credit) | 5 | realized sale proceeds (settled, count as cash on settlement date) |

- "Possible duplicate card charge" children (6) are **pending** rows following
  a settled parent — treat as *not yet payable/uncertain* (safer: ignore as
  debit until settled, or reserve per safer-interpretation rule).
- Refund amount == original amount in 22/22 cases; 8 refunds still pending
  (do not count as available cash, per rules).

## 6. Currencies & Exchange Rates

- Events: INR 6,457 / EUR 5,585 / IDR 4,992 / ZAR 4,489 / USD 3,819 rows.
- **140 rows (27 users) are in a non-home currency**: 139 salary credits
  (USD or EUR) + 1 transport debit. Rates exist for every needed
  (rate_date=15th of month, from, to) triple — 0 gaps.
- Rate graph: USD→EUR (0.92), USD→IDR/INR, EUR→ZAR/USD. Monthly dated rows.
- Conversion rule to implement: convert on the event's settlement/rate date
  using the supplied pair; chain USD→EUR→ZAR etc. if needed.

## 7. Payment Options (790 rows)

- Every request (sample + eval) has **exactly one full_payment option**
  (amount == `requested_amount`, first_payment_date == request_date, fee 0)
  plus 1–3 installment options (515 total; 2–24 payments; frequency 28/30/31d;
  first installment 0–14 days after request_date).
- **No partial_payment options exist** — partial payment is purely derived
  (2-payment plan per the output contract).
- `total_payable_amount == number_of_payments × payment_amount` (790/790).
  Installment totals = 1.035–1.22× requested (financing fee 3.5–22%).
- 394/515 installment plans finish after `desired_completion_date` →
  ineligible by the "complete by deadline" ranking rule (long 15/18/21/24-pay
  plans usually out).
- Sample truth shows **rank 3 (minimize total paid) dominates**: even when a
  partial or wait was possible, full_payment or the cheapest installments won
  (e.g. request_02 3-installment plan over cheaper-start options).

## 8. Messages (215 rows)

- Attachment: 100 request-only, 28 request+event, 76 user-only (11 with an
  event link, rest pure user context). All event links resolve; same user.
- 116 messages attach to eval requests (1 per request), sent 0–11 days
  *before* the request_date (never after) — always usable evidence.
- Language: ~148 English, ~67 Indonesian (salary/payroll messages in
  Indonesian are common — need bilingual parsing or per-user salary pattern).
- Themes (approximate counts):
  - Salary/payroll 119: increase (7), reduction (20 — "temporary monthly pay",
    unpaid leave), date change (8), bonus-not-approved (8), payout/other (84).
    These amend the projected salary amount/date for the forecast.
  - Payout pending 18 (gig platforms): "earnings not withdrawable until
    completed" → exclude pending credits.
  - Refund initiated 14: refund pending → don't count as cash.
  - Fraud/dispute 6: "reversal not posted" → don't count as credit; charge
    already reflected.
  - Rent/service changes 31: e.g. "renewed lease increases monthly rent by
    12%" → amend projected rent.
  - Portfolio value up (other 19): "no units sold, no cash proceeds" → ignore
    unrealized value.
- Message→event links point at refunds (10), expenses (9), valuations (7),
  income (6), debt_payments (4), sales (3); 15 settled, 13 pending,
  7 unrealized, 4 failed. Status words in messages confirm/void the row.

## 9. Images (16)

- Each image resolves a **blank-amount event** (16/16 blank amounts covered;
  never treat as zero): 1 income (salary payslip, image_01 → event_253) and
  15 expense debits (rent, groceries, utilities, dining, housing, healthcare,
  transport, shopping).
- Image types seen: Indonesian payroll payslip (gross vs net: **use Net Pay,
  IDR 4,365,000**, not subtotal earnings) and itemized receipts (taxi receipt:
  total = fare + surcharge, cash paid ≠ amount to record).
- Users affected include request users only (each image's user has a request);
  4 of the 16 events are pending/scheduled → amount needed for forecast
  reservation too.

## 10. Sample-Request Calibration (the 25 labeled rows)

Outcome distribution: affordable_now 3, affordable_with_plan 9,
affordable_later 6, not_affordable 7.

Behaviors to replicate:

1. `affordable_now` → asp == requested, earliest == request_date, plan =
   `request_date:full`, method `full_payment`.
2. `installments` chosen even when `earliest_date_for_full_payment` exists
   (request_02/07/12/17/22): user prefers installments and ranking rule 3
   (minimize total paid) picks the cheapest eligible plan; asp is still the
   max safe today; earliest date is capacity-based, independent of method.
3. `wait` (affordable_later, 6 rows): plan is a single full payment exactly at
   `earliest_date_for_full_payment` (== often `desired_completion_date`);
   earliest is NOT ≤ desired_completion (they pay on the last allowed day).
4. `not_affordable` (7 rows): asp > 0 but < requested, plan `none`, earliest
   empty, method `not_recommended`.
5. `partial_payment` (1 row, request_19): exactly 2 payments
   (asp today + remainder at earliest), both sum to requested.
6. Spending changes (3 rows): target settled flexible events; reduce_to uses
   the event's `minimum_allowed_amount` (event_989 → 665,950; event_1816 →
   23.50); stop applies to stoppable subscriptions; one case chains stop +
   reduce on different events. Changes unlock full payment earlier (requests
   06/11/21 are affordable_with_plan via changes, paid as `full_payment`
   method on request_date — note: method full_payment with
   affordable_with_plan is allowed when spending changes enable it).
7. `decision_explanation` pattern: "<Action sentence>. This leaves at least
   <minimum> available." (~1–2 sentences, cites minimum balance).

## 11. Unusual / Edge Cases Summary

- 16 blank-amount events → OCR from PNGs (payslip net pay, receipt totals).
- 6 "possible duplicate card charge" pending events → safer interpretation.
- 22 cancelled → settled / 21 failed → scheduled retry chains via
  `linked_event_id` → count only the resolved child.
- 10 unrealized valuations + "portfolio up" messages → never cash.
- 5 settled investment sales (credits, 1.8–2.8× cost) → cash on settlement.
- 6 windfall credits (settled, one-off) → count as cash on date.
- 47 scheduled next salaries; 42 belong to request users; message amendments
  may change amount (±reduction/increase) or shift date — apply newest
  evidence.
- 140 foreign-currency rows (mostly USD/EUR salaries) → dated conversion.
- 19 pending/scheduled expenses land exactly on request_date → reserve before
  computing asp.
- Semi-monthly and weekly salary cadences exist → cadence detection, not a
  fixed monthly assumption.
- 119 profiles have blank `max_installment_months` (installments not
  considered) and 112 don't consider full_payment → method eligibility filter
  is essential.
- Deadline feasibility: 394/515 installment plans exceed the desired
  completion date; long plans auto-eliminate.

## 12. Implications for the Solution

1. Core engine is deterministic: series detection (~6-month history) →
   90-day projection → safety-constrained asp → candidate plan generation
   (full/partial/installments/wait) → rank per the 6 rules → sample-validate.
2. LLM (if used) only for: message intent classification (EN/ID), image
   amount extraction fallback, explanation phrasing. Keep numeric decisions
   deterministic.
3. The 25 samples provide an exact regression harness: replicate their
   outputs from inputs alone before touching eval rows.
4. Data traps deliberately embedded: pending credits, duplicate charges,
   unrealized gains, cancelled/failed twins, installment plans past deadline,
   ineligible methods, non-home-currency salary, image-only amounts,
   Indonesian text, bonus "not approved", payout "not withdrawable".
