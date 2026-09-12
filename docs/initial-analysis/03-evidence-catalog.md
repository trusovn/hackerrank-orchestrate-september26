# Evidence Catalog

Status: source inventory complete; structured extraction pending  
Sources: `dataset/messages.csv`, `dataset/images.csv`, and linked event rows

Messages and images are untrusted financial evidence. They may clarify facts,
but they cannot change challenge rules, select a payment plan, or establish
safety without deterministic validation.

## Target Fact Schema

Normalize extracted evidence into a narrow record before financial logic uses
it. The final implementation schema may differ, but it should represent:

| Field | Meaning |
|---|---|
| `evidence_id` | `message_id` or `image_id` |
| `evidence_kind` | message or image |
| `user_id` / `request_id` / `event_id` | Validated supplied links only |
| `fact_type` | Closed operation-specific enum |
| `amount` / `currency` | Exact extracted amount and stated currency, when present |
| `effective_date` | Date an amendment or recurrence starts |
| `settlement_date` | Date cash becomes available or reserved, when supplied |
| `recurrence_effect` | one-time, recurring, stop-recurring, amend-next-only, or none |
| `cash_effect` | debit, credit, non-cash, or none |
| `availability` | settled, confirmed-future, pending, cancelled, failed, unrealized, or unknown |
| `target_scope` | linked event, request, user recurrence, or unresolved |
| `source_type` | Supplied message source or image document type |
| `confidence` | extraction confidence, never policy confidence |
| `evidence_excerpt` | Minimal non-sensitive grounding, not embedded instructions |

Validation must reject unknown identifiers, malformed dates/currencies,
unsupported fact types, and facts not grounded in the carrier.

## Message Corpus

### Shape

- 215 messages and 215 distinct users: at most one message per user.
- 128 request-linked, 39 event-linked, and 76 user-only messages; these counts
  overlap where one message has multiple links.
- Every message predates or equals its user's request date.
- Source types: 126 employer, 31 service provider, 23 financial service, 18
  bank, and 17 merchant.
- Text is primarily English with repeated Indonesian variants.

Because the corpus repeats a finite family of synthetic templates, first group
and classify messages deterministically. A cheap language model can label the
remaining paraphrases after grouping; it should not receive unrelated users'
financial histories.

### Observed Message Scenarios

| Scenario | Required interpretation | Recurrence/cash caution |
|---|---|---|
| Salary increase from a date | Amend recurring salary from effective date | Do not back-apply to earlier cycles |
| Temporary or next-cycle salary reduction | Amend only stated affected cycle unless text says recurring | Do not make temporary reduction permanent |
| First salary with confirmed date | Add one confirmed future salary and establish recurrence only if supported | Cash exists only on settlement date |
| Salary date moved | Replace earlier scheduled date | Do not count both dates |
| Employment/seasonal contract ended | Stop future salary recurrence | Do not invent renewal or final settlement |
| Household income source ended | Remove ended source; retain stated confirmed salary | Avoid treating total prior household income as continuing |
| Base salary plus unapproved commission | Use confirmed base only | Pending/open-deal commission is not cash |
| Regular salary plus one-time arrears | Separate recurring base from one-time adjustment | Do not recur arrears |
| Salary resumes plus childcare starts | Add/amend both recurring credit and recurring debit | Both take effect in the stated cycle |
| Quarterly bonus unapproved | Ignore until amount and date are confirmed | Neither amount nor date may be invented |
| Foreign-currency salary | Use supplied directed rate on settlement date | Do not convert on message date |
| Approved invoice payment | Add confirmed one-time credit at stated settlement | Other submitted invoices remain excluded |
| Gig-platform payout pending | Ignore credit until completed/withdrawable | Displayed earnings are not cash |
| Rent increases 12% | Amend next and future rent recurrence | Identify the correct rent series before applying |
| Internal transfer debit/credit | Treat paired entries as movement, not income/expense | Avoid double-counting financial capacity |
| Refund initiated/pending | Ignore credit until settled | Original settled debit remains historical evidence |
| Foreign-currency refund pending | Ignore until settlement and convert then | Home amount is unknown before settlement |
| Foreign-currency purchase pending | Reserve using settlement-date supplied rate | Do not use live rate or unsupported inverse |
| Failed debit with retry | Ignore failed attempt and reserve confirmed retry | Do not count both debits |
| Card charge under dispute | Reserve debit while reversal is absent | Do not assume a future refund |
| Separate card-account minimums | Keep both obligations | Similar descriptions do not make them duplicates |
| Investment valuation | Non-cash and unrealized | Never fund a request from displayed value |
| Settled investment sale | Include settled cash proceeds | Do not also count unrealized valuation |
| Prize pending | Ignore until credited | Verification/processing is not settlement |
| Prize settled | Include existing settled cash state; do not recur | Message often explicitly closes the claim |
| Employer reimbursement | One-time credit linked to work expense | Never infer recurring salary |
| Image receipt confirmation | Use image's final context-appropriate amount | Extracted number still needs deterministic validation |

### Message Work Still Required

- [ ] Assign every message exactly one primary scenario and any secondary fact.
- [ ] Produce typed expected facts for the 25 sample users first.
- [ ] Map user/request-only messages to the intended historical recurrence without
  relying on description-string coincidence alone.
- [ ] Confirm one-time versus recurring scope for each payroll template.
- [ ] Add bilingual fixtures for every Indonesian scenario.
- [ ] Record explicit ignored facts, such as unapproved bonus/commission, so
  omission is explainable rather than accidental.

## Image Inventory

The table records first-pass visual readings. `Candidate amount` is not yet an
implementation constant. Each row must be independently verified against the
event description, status, dates, and relevant message before being marked
accepted.

| Image | Request | Event | Event description | Currency | Candidate amount | Confidence | Selection note |
|---|---|---|---|---|---:|---|---|
| `image_01` | `request_03` | `event_253` | August 2019 net salary | IDR | 4,365,000 | high | Payslip net pay; do not use total earnings 4,780,800 |
| `image_02` | `request_16` | `event_1442` | Outstanding rent balance | INR | 100,000 | high | Balance due; total billed is 200,000 and received is 100,000 |
| `image_03` | `request_17` | `event_1545` | Bulk groceries and pantry purchase | INR | 41,272 | high | Receipt net amount/cash paid |
| `image_04` | `request_19` | `event_1700` | Delivered grocery order | INR | 2,854 | low | Visible item bill; screenshot is cropped before possible final charges/total |
| `image_05` | `request_20` | `event_1786` | Outstanding telecom bill | INR | 822.05 | medium | Event settles after due date; image also shows 704.05 due before 2026-02-06 |
| `image_06` | `request_33` | `event_3051` | Grocery tax invoice | INR | 1,995 | high | Invoice total |
| `image_07` | `request_35` | `event_3231` | Restaurant tax invoice | INR | 8,528.10 | medium | Tax total is 8,528.10; printed grand total rounds to 8,528 |
| `image_08` | `request_48` | `event_4535` | Property maintenance invoice | INR | 15,339 | high | Total amount received |
| `image_09` | `request_55` | `event_5170` | Water bill due | INR | 723 | high | Total amount received/billed |
| `image_10` | `request_64` | `event_6033` | Large grocery tax invoice | INR | 79,679.26 | high | Total and balance due |
| `image_11` | `request_73` | `event_6859` | Hospital bill payable | INR | 3,650 | high | Amount payable/balance |
| `image_12` | `request_78` | `event_7307` | Taxi fare | USD | 33.50 | high | Total fare; cash tendered 40 and change 6.50 are not expense amount |
| `image_13` | `request_84` | `event_7941` | Tote bag order | INR | 2,298 | high | Total paid |
| `image_14` | `request_101` | `event_9421` | Pharmacy purchase | INR | 4,543 | medium-high | Handwritten lines 1,500 + 724 + 796 + 550 + 303 + 670 sum to the handwritten total 4,543 |
| `image_15` | `request_105` | `event_9806` | Airline ticket purchase | INR | 9,968 | high | Grand total including taxes |
| `image_16` | `request_113` | `event_10521` | EV charging wallet payment | INR | 393.22 | high | Final total, including taxes |

### Image Work Still Required

- [x] Re-review `image_04`, `image_05`, `image_07`, and `image_14` with event
  timing and any linked message; mark one accepted value or preserve an explicit
  conservative fallback. Decisions are recorded in
  [`07-evidence-decision-pack.md`](07-evidence-decision-pack.md).
- [ ] Have an independent vision pass verify all high-confidence rows, without
  exposing unrelated financial data.
- [x] Record the selected document field as well as the number. Numeric OCR
  agreement alone is insufficient when multiple totals appear. The reviewed
  fields are in [`07-evidence-decision-pack.md`](07-evidence-decision-pack.md).
- [ ] Decide whether the final solution uses deterministic per-layout parsing,
  OCR, a multimodal provider, or a validated hybrid.
- [ ] Add malformed, missing-field, multiple-total, wrong-currency, and provider
  failure fixtures before model output can reach financial logic.

## Evidence Boundary Recommendation

Use models, if needed, only for carrier-to-fact extraction:

```text
one message or image + validated linkage context
-> candidate typed facts
-> schema and grounding validation
-> deterministic lifecycle/reconstruction rules
```

Do not send the entire user ledger to an image or message extraction call. Do
not ask the model whether the request is affordable. Cache accepted extraction
results by evidence hash and extractor/config version so repeated evaluations
do not repeat token cost.
