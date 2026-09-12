# Dataset Profile

Status: **OBSERVED** unless explicitly labeled otherwise  
Profiled: 2026-09-12 using Python standard-library CSV parsing  
Dataset source: [`../../dataset/`](../../dataset/)

This profile records facts needed for loader, domain, extraction, and
evaluation planning. Counts should be refreshed if participant-facing files
change.

## Corpus Summary

| File | Data rows | Role |
|---|---:|---|
| `requests.csv` | 250 | Evaluation requests requiring output |
| `sample_requests.csv` | 25 | Solved public examples |
| `financial_profiles.csv` | 275 | One profile per user |
| `financial_events.csv` | 25,342 | Historical, scheduled, pending, and lifecycle events |
| `exchange_rates.csv` | 134 | Dated directed conversion rates |
| `request_payment_options.csv` | 790 | Full-payment and installment offers |
| `messages.csv` | 215 | At most one message per user |
| `images.csv` | 16 | Image-to-event mappings |
| `output.csv` | 250 | Blank template rows |

There are 275 distinct users and 275 total requests when the 25 samples and 250
evaluation requests are combined. Each user owns exactly one request. Every
request has a profile, financial-event history, and at least two payment
options.

## Request Profile

### Request Types

The 250 evaluation requests are nearly balanced:

| Type | Rows |
|---|---:|
| `purchase` | 28 |
| `travel` | 28 |
| `education` | 28 |
| `family_transfer` | 28 |
| `debt_repayment` | 28 |
| `investment` | 28 |
| `housing` | 28 |
| `emergency_expense` | 27 |
| `other` | 27 |

The 25 samples contain three each of the first seven types and two each of
`emergency_expense` and `other`.

### Dates And Amounts

- Evaluation request dates: 2023-01-20 through 2026-09-04.
- Sample request dates: 2019-09-03 through 2026-07-07.
- Desired completion is 6–86 days after the request date; every deadline lies
  within the 90-day forecast.
- 88 requested amounts contain a decimal point; 187 are serialized as integers.
- `allows_partial_payment`: 80 true and 170 false in evaluation requests; 12
  true and 13 false in samples.

No request fields are blank.

## Profile Data

### Home Currency

| Currency | Users |
|---|---:|
| INR | 67 |
| EUR | 62 |
| IDR | 55 |
| ZAR | 51 |
| USD | 40 |

### Payment Preferences

| `payment_methods_user_will_consider` | Users |
|---|---:|
| `full_payment` | 60 |
| `partial_payment\|installments` | 52 |
| `installments` | 41 |
| `full_payment\|partial_payment` | 40 |
| `full_payment\|installments` | 35 |
| `full_payment\|partial_payment\|installments` | 28 |
| `partial_payment` | 19 |

`max_installment_months` is blank for 119 users and ranges from 2 through 12
when populated. Blank corresponds to profiles that do not consider
installments; this relationship should be asserted by the loader rather than
assumed silently.

### Category Domains

Protected categories observed:

```text
rent, education, groceries, debt_repayment, housing, utilities,
transport, healthcare, family_support, insurance
```

Reducible categories observed:

```text
dining, entertainment, streaming, shopping, gym
```

Stoppable categories observed:

```text
delivery_membership, cloud_storage, streaming, music_subscription, gym
```

No profile has a category in both its protected list and either its reducible
or stoppable list.

## Financial Events

There are 56–129 events per user, with a median of 98. Historical settlement
coverage spans 175–179 days before each request, normally about six months.

### Type, Direction, And Status

| Event type | Rows |
|---|---:|
| `expense` | 20,525 |
| `subscription` | 2,488 |
| `income` | 1,696 |
| `debt_payment` | 567 |
| `investment_purchase` | 29 |
| `refund` | 22 |
| `investment_valuation` | 10 |
| `investment_sale` | 5 |

| Direction | Rows |
|---|---:|
| `debit` | 23,609 |
| `credit` | 1,723 |
| `non_cash` | 10 |

| Status | Rows |
|---|---:|
| `settled` | 25,148 |
| `pending` | 71 |
| `scheduled` | 70 |
| `cancelled` | 22 |
| `failed` | 21 |
| `unrealized` | 10 |

### Flexibility

| Flexibility | Rows | `minimum_allowed_amount` present |
|---|---:|---:|
| `fixed` | 21,138 | 0 |
| `reducible` | 2,682 | 2,682 |
| `stoppable` | 1,297 | 0 |
| `reducible_or_stoppable` | 225 | 225 |

All populated minimums are less than or equal to their event amount.

### Missing Values

- `amount`: 16 blanks, exactly matching the 16 `images.csv` event links.
- `settlement_date`: 10 blanks, all non-cash unrealized investment valuations.
- `linked_event_id`: present on 58 lifecycle rows.
- `minimum_allowed_amount`: absent where the flexibility mode does not require
  a lower bound.

No blank amount lacks an image, and no image points to an event with a populated
amount.

### Event Timing Relative To Request

| Position | Rows |
|---|---:|
| Event date before request | 25,274 |
| Event date on request | 21 |
| Event date after request | 47 |
| Settlement before request | 25,191 |
| Settlement in days 1–90 | 141 |
| Settlement after day 90 | 0 |

No populated settlement date equals its request date. This reduces same-day
ambiguity for the supplied run but does not define the general same-day rule.

### Explicit Future Events

The 141 future settlements contain:

| Dimension | Distribution |
|---|---|
| Status | 71 pending; 70 scheduled |
| Direction | 86 debit; 55 credit |
| Type | 79 expense; 47 income; 8 refund; 7 debt payment |
| Users | 122 users; 105 have one, 15 have two, 2 have three |

Future categories are salary, shopping, healthcare, transport, utilities,
education, insurance, rent, and groceries. Most forecast expenses therefore
must be inferred from history rather than read as explicit future rows.

## Recurrence Signals

Historical settled rows were grouped by user, event type, description,
category, direction, and currency:

- 7,808 semantic groups exist.
- 6,109 groups repeat at least twice.
- Repeated groups contain 23,449 historical events.
- 4,848 repeated groups vary in amount.
- 1,261 repeated groups have a fixed amount.
- Common five-observation interval signatures resemble calendar-month
  recurrence: `(31,30,31,30)`, `(30,31,30,31)`, and month-length variants.
- Other interval signatures include 14, 21, 28, 42, 56, 63, 70, 84, 98, 105,
  112, and 126 days, so repetition alone does not imply monthly recurrence.

These observations prove that recurrence and conservative variable-spend
estimation require an explicit algorithm. They do not select that algorithm.

## Lifecycle Links

All 58 `linked_event_id` references resolve. Observed lifecycle patterns
include:

- expense -> settled or pending refund;
- cancelled expense -> settled replacement expense;
- failed debt payment -> scheduled retry;
- settled expense -> pending duplicate/disputed charge;
- investment purchase -> non-cash valuation;
- investment purchase -> settled investment sale; and
- work expense -> settled employer reimbursement.

Create one fixture per pattern. A linked record is not automatically a
duplicate; the event types, directions, statuses, and message evidence determine
its effect.

## Exchange Rates

| Directed pair | Rows | Date coverage | Observed rate values |
|---|---:|---|---|
| EUR -> USD | 24 | 2024-04-15 to 2026-09-15 | 1.09 |
| EUR -> ZAR | 22 | 2023-10-15 to 2026-01-15 | 20 |
| USD -> EUR | 25 | 2023-10-15 to 2026-03-15 | 0.92 |
| USD -> IDR | 30 | 2023-10-15 to 2026-06-15 | 15833.33 |
| USD -> INR | 33 | 2024-01-15 to 2026-11-15 | 83.33 |

There are 140 foreign-currency events. Every observed foreign-event direction
has a supplied pair. The rates are constant in this corpus, but code must not
hardcode that accidental property or calculate an inverse not supplied by the
dataset.

## Payment Options

- 275 full-payment options: exactly one per request, equal to the requested
  amount, with first payment on the request date.
- 515 installment options.
- Options per request: 65 requests have two, 180 have three, and 30 have four.
- Installment counts observed: 2, 3, 4, 6, 15, 18, 21, and 24.
- Frequencies observed: 28, 30, or 31 days.
- All `payment_amount * number_of_payments` values match
  `total_payable_amount` within one cent.
- 434 installment options finish after their request deadline.
- Only 81 requests have any installment that finishes by the deadline before
  applying user preference, safety, or maximum-month filtering.
- 193 installment options have more payments than the populated
  `max_installment_months`; this count depends on the current working
  interpretation that months constrain payment count.

The option file intentionally contains attractive-looking but ineligible
offers. Eligibility must be evaluated before financial safety and ranking.

## Messages And Images

- 215 users have one message; 60 have none.
- 128 messages carry `request_id`.
- 39 messages carry `related_event_id`.
- 76 messages are user-only; linkage counts overlap because some event-linked
  messages also carry a request ID.
- No message timestamp is after its user's request date.
- Sources: 126 employer, 31 service provider, 23 financial service, 18 bank,
  and 17 merchant.
- All 16 image links resolve to PNG files and valid event/request/user IDs.

See [`03-evidence-catalog.md`](03-evidence-catalog.md) for the extraction
taxonomy and image-level notes.

## Solved Output Coverage

| Output dimension | Distribution across 25 samples |
|---|---|
| Status | 3 affordable now; 9 affordable with plan; 6 affordable later; 7 not affordable |
| Method | 6 full payment; 1 partial; 5 installments; 6 wait; 7 not recommended |
| Spending changes | 22 none; 1 stop-only; 1 reduce-only; 1 stop-plus-reduce |
| Earliest full date | Blank for 7 not-affordable examples |

The examples provide broad class coverage but only one partial-payment case and
three spending-change cases. Those sparse branches require derived boundary
fixtures in addition to golden-example regression tests.

## Integrity Findings

Confirmed on the profiled dataset:

- no broken request, profile, event, image, message, payment-option, or lifecycle
  foreign keys;
- no missing required request inputs;
- exactly one blank output row for every evaluation request;
- all image-backed amounts are blank in CSV and all blank amounts are
  image-backed;
- all supplied payment totals are arithmetically consistent; and
- all completion deadlines fall inside the forecast horizon.

## Cautions For Future Analysis

- Do not send all 25,342 events to a language model. Filter per user and reduce
  history to typed recurrence summaries first.
- Do not use historical settled amounts as future cash flows until a recurrence
  rule accepts them.
- Do not add past settled activity to or subtract it from the current balance
  until the opening-balance hypothesis is proven.
- Do not infer reverse FX rates or reuse an event-date rate when settlement date
  differs.
- Do not use evaluation requests as labels or alter participant inputs.
