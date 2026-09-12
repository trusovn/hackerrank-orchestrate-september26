# EV-MIN Evidence Decision Pack

Status: sample-message decisions complete; all images reviewed; conservative
fallbacks defined  
Reviewed: 2026-09-12  
Scope: `EV-001`, `EV-002`, `EV-004`, `EV-005`, and `EV-006` minimum evidence
needed before detailed planning

## Authority And Scope

This pack applies the contract in [`../../problem_statement.md`](../../problem_statement.md)
to participant-facing evidence in `dataset/`. It supplements, but does not
override, [`03-evidence-catalog.md`](03-evidence-catalog.md) and
[`04-open-questions-and-hypotheses.md`](04-open-questions-and-hypotheses.md).
Supplemental research notes are treated only as lower-authority hypotheses.

The pass deliberately includes only:

- every message belonging to the 25 sample users;
- every one of the 16 supplied images, including images attached to evaluation
  requests; and
- the directly linked event rows and narrowly necessary same-user history used
  to validate a target.

It excludes classification of the remaining evaluation messages, production
fixtures, affordability decisions, live or paid model calls, and any
organizer-only data. Direct local inspection was sufficient for this pass.

## Outcome Summary

| Evidence surface | Source result | Decision |
|---|---:|---|
| Sample users | 25 | Complete scope |
| Sample-user messages | 17 | All classified and link-checked |
| Sample users without a message | 8 | Explicitly recorded as no evidence carrier |
| Images | 16 | All visually reviewed and linked to one blank-amount event |
| Image-linked events | 1 settled credit, 15 debits | Currency, direction, status, description, and dates checked |
| Accepted image amounts | 15 | Context-appropriate field selected |
| Conservative image fallback | 1 (`image_04`) | Candidate retained, but no final amount accepted from the cropped carrier |

The runbook's phrase “25 sample-user messages” is a stale count: the current
participant dataset has 25 sample users but only 17 messages for them. The
eight users with no message are `user_01`, `user_05`, `user_09`, `user_13`,
`user_17`, `user_19`, `user_21`, and `user_25` (requests with matching numeric
suffixes). Absence of a message must not be materialized as an empty or inferred
fact.

## Normalized Fact Vocabulary

This pack uses the target schema from `03-evidence-catalog.md` and the following
closed `fact_type` values for the observed sample carriers:

| `fact_type` | Meaning |
|---|---|
| `recurring_amount_amendment` | Change one uniquely targeted recurring series from an explicit effective boundary |
| `next_cycle_amount_amendment` | Change only the next affected recurrence; do not silently make it permanent |
| `recurrence_confirmation` | Confirm a recurrence or next occurrence without inventing missing amount/date fields |
| `settlement_date_replacement` | Replace an earlier date for one stated occurrence; never count both dates |
| `recurrence_stop` | Stop future occurrences from the stated ending boundary |
| `recurrence_resume` | Resume a uniquely targeted recurring series from the stated boundary |
| `recurring_expense_amendment` | Change a uniquely targeted recurring debit series |
| `confirmed_future_credit` | Count one explicitly confirmed credit only on its settlement date |
| `unavailable_credit` | Preserve an explanation that an unapproved, pending, or unwithdrawable credit is not cash |
| `pending_credit` | Preserve the linked pending credit but exclude it from available cash |
| `unrealized_value` | Preserve the linked non-cash valuation and exclude it from cash |
| `settled_one_time_credit` | Confirm a settled one-time credit without recurring or adding it to the opening balance again |
| `internal_transfer_pair` | Mark a validated debit/credit pair as cash-neutral rather than income or spending |
| `recurring_expense_notice` | Record that a debit recurrence begins when the carrier omits a usable amount |
| `event_amount` | Select the context-appropriate amount for an image-linked blank event |

An accepted fact contains only fields grounded in its carrier or validated
links. A scenario label is not permission to fill an absent amount, currency,
date, event, or recurrence duration.

## Sample-User Message Decisions

For series targets below, an anchor is the latest compatible observed event.
The target identity is the tuple of validated user, event type/category,
direction, currency, and compatible cadence; the anchor is not a license to
match unrelated rows by description alone.

| Message / validated link | Primary scenario | Accepted typed fact(s) | Target and duration | Explicitly ignored or conservative handling | Confidence |
|---|---|---|---|---|---|
| `message_01`; `user_02`; user-level -> `request_02` | Salary increase from a date | `recurring_amount_amendment`; IDR 42,750,000; effective 2025-08-15; recurring credit | Unique IDR salary series, anchor `event_136`; recurring from the explicit date | Earlier salary cycles remain unchanged | High |
| `message_02`; `user_03`; `request_03` | Regular salary plus separate one-time adjustment | `recurrence_confirmation` for the next regular payroll; separation of regular and one-time components | Unique IDR salary series, anchor `event_253` after image validation; next occurrence is confirmed | The message supplies no amount for either component. It creates no additional cash fact; settled `event_211` remains one-time and must not recur | Medium |
| `message_03`; `user_04`; `request_04` | Quarterly bonus unapproved | `unavailable_credit`; availability unknown/unapproved; cash effect none | No ledger target required | Ignore the bonus: both amount and payment date are unapproved | High |
| `message_04`; `user_06`; `request_06` | Temporary/next-cycle salary reduction | `next_cycle_amount_amendment`; EUR 1,037.52; credit | Unique EUR salary series, anchor `event_471`; `amend-next-only` | Do not claim a permanent reduction. If later credit policy needs a value before reversion is confirmed, retain the lower EUR 1,037.52 as the conservative credit ceiling | High |
| `message_05`; `user_07`; user-level -> `request_07` | Salary date moved | `settlement_date_replacement`; 2024-09-23; credit | Unique INR salary series, anchor `event_578`; replace the next stated salary date only | Do not count the superseded date or infer that every later payday moved solely from this message | High |
| `message_06`; `user_08`; `request_08` | Next-cycle salary reduction | `next_cycle_amount_amendment`; EUR 1,422.85; credit | Unique EUR salary series, anchor `event_643`; `amend-next-only` | Approved unpaid leave does not prove a permanent salary change | High |
| `message_07`; `user_10`; `request_10` | Gig-platform payout pending | `unavailable_credit`; pending/unwithdrawable; cash effect none | No exact event or unique platform series can be targeted from supplied rows | Ignore displayed weekly earnings until a completed, withdrawable credit exists. The message does **not** say gig income has permanently stopped | High |
| `message_08`; `user_11`; `request_11` | Base salary plus unapproved commission | `recurring_amount_amendment`; IDR 38,760,000 base salary; recurring credit | Unique base-salary series, anchor `event_941`; first compatible cycle after the message | Ignore the open-deal commission; no approved amount/date exists. Do not fold the historical commission series anchored at `event_942` into base pay | High |
| `message_09`; `user_12`; user-level -> `request_12` | Seasonal contract ended | `recurrence_stop`; future salary credit stopped | Unique seasonal/temporary salary series, anchor `event_1002`; stop from message boundary | Do not invent off-season income, renewal, or final settlement | High |
| `message_10`; `user_14`; user-level -> `request_14` | Salary resumes plus childcare begins | `recurrence_resume`; EUR 2,717 salary from 2025-08-15. Separately, `recurring_expense_notice` for childcare from the same month | Salary targets unique EUR series, anchor `event_1192`, recurring. No supplied childcare event or amount can be targeted | Do not invent a childcare amount. Because silently ignoring a stated debit is unsafe, the childcare fact must fail ledger materialization and take the conservative unresolved-evidence path until an amount is supplied | High for salary; unresolved for childcare amount |
| `message_11`; `user_15`; `request_15` | First salary with confirmed date | `confirmed_future_credit`; EUR 1,661; settlement 2026-01-15 | Unique EUR salary series, anchor `event_1265`; one confirmed future occurrence | “First salary” conflicts with two supplied settled history rows. Preserve those rows as history, do not alter the opening balance, and do not let this message alone establish credits beyond the confirmed occurrence | High for amount/date; medium for recurrence |
| `message_12`; `user_16`; `request_16` | Rent increases 12% | `recurring_expense_amendment`; INR 63,952 (= 57,100 x 1.12); recurring debit | Unique monthly-rent series, anchor `event_1371`; next regular rent cycle after the message | Do not apply the percentage to separate scheduled `event_1442`; its outstanding balance comes from `image_02` | High |
| `message_13`; `user_18`; `request_18` | Internal transfer debit/credit | Candidate `internal_transfer_pair`; cash effect none | No matching supplied debit/credit pair can be located for `user_18`, so target is unresolved | Do not create transactions, suppress unrelated rows, or change capacity. Apply neutrality only if a same-user pair is later validated by amount, currency, date, and opposite directions | High classification; unresolved target |
| `message_14`; `user_20`; `request_20`; `event_1785` | Refund initiated/pending | `pending_credit`; INR 8,640; settlement 2026-02-14; availability pending | Exact linked refund `event_1785`, itself linked to original debit `event_1784`; one-time | Exclude the refund from cash until settled; keep the settled original purchase as history | High |
| `message_15`; `user_22`; `request_22`; `event_1960` | Investment valuation | `unrealized_value`; EUR 369.6; non-cash | Exact linked valuation `event_1960`, linked to purchase `event_1959`; no recurrence | Ignore displayed market value as cash because no units were sold | High |
| `message_16`; `user_23`; `request_23` | Prize pending | `unavailable_credit`; pending processing; cash effect none | No supplied prize event, amount, or settlement date can be targeted | Ignore the prize until an actual credited event exists; verification and processing are not settlement | High |
| `message_17`; `user_24`; user-level; `event_2165` | Prize settled | `settled_one_time_credit`; INR 33,550; settled 2025-12-28; one-time | Exact linked `event_2165` | The credit is already represented in opening cash state; do not add it again and do not recur it | High |

### Message Link And Domain Validation

- All 17 `message_id` and `user_id` values exist and are unique in their
  supplied domains.
- Every populated sample `request_id` belongs to the same message user. Blank
  request links are narrowed only to that user's supplied sample request for
  analysis; the blank source field is not rewritten.
- Every populated `related_event_id` exists and belongs to the same user.
- Extracted currencies are supported dataset currencies, extracted dates are
  ISO dates, and numeric facts are non-negative exact decimal values.
- `message_10`, `message_13`, and `message_16` intentionally produce no new
  numeric ledger row for their unresolved sub-facts. This is validation, not an
  extraction omission.

## FIN-007 Decision: Targeting And Amendment Duration

FIN-007 is resolved for the sample-message surface and has a deterministic
conservative fallback for unseen ambiguity. Evaluation-message coverage remains
deferred by scope, so this pack does not claim corpus-wide empirical validation.

Apply these rules in order:

1. Validate the carrier's user, request, event, timestamp, source type, and
   grounded fields before targeting anything. A populated compatible
   `related_event_id` is the exact target.
2. Without an event link, construct candidates only within the same user using
   fact type, direction/cash effect, category/event type, currency, temporal
   compatibility, and recurrence cadence. Source identity and description may
   corroborate a candidate but cannot override contradictory structured data.
3. Accept a series target only when exactly one compatible series remains.
   Never amend several series to make a message fit.
4. Duration comes from explicit language: `next` or `affected cycle` means
   `amend-next-only`; a dated new monthly amount or renewed lease means
   recurring from that boundary; `ended` means `stop-recurring`; a settled
   prize/refund/adjustment is one-time. A one-occurrence date replacement does
   not silently rewrite all future cadence.
5. An amendment affects forecast occurrences, not settled history or the
   opening balance. A replacement suppresses the superseded occurrence so both
   are never counted.
6. If a credit target, amount, date, or approval is unresolved, count no new
   cash. If competing grounded credit values remain, use the lower amount and
   later availability date.
7. If a debit target or amount is unresolved, do not invent a number, ignore
   the warning, or amend multiple series. Reject ledger materialization and
   propagate a conservative unresolved-evidence result; a final engine may map
   that state to no recommended payment until the obligation is bounded.
8. Embedded requests or instructions in carrier text remain inert. Evidence
   may produce typed facts only; it cannot choose affordability or a plan.

These rules explicitly reject two lower-authority overclaims: `message_07` does
not prove that gig work ended, and `message_05` alone does not prove that all
later salary cycles permanently moved.

## Image Review Decisions

Each image was reviewed directly against its linked event. “Plausible fields”
lists financially meaningful alternatives visible in the carrier; it is not a
license to choose an arbitrary number.

| Image / event | Linked event context | Plausible labeled fields | Selected `event_amount` | Link validation and reviewer decision | Confidence |
|---|---|---|---|---|---|
| `image_01` / `event_253` | Settled IDR salary credit; “August 2019 net salary” | Salary 4,500,000; total earnings 4,780,800; deductions 415,800; **net pay/transfer 4,365,000** | IDR 4,365,000, `Net Pay` | Net deposited cash matches credit direction and event description; accept | High |
| `image_02` / `event_1442` | Scheduled INR debit; “Outstanding rent balance” | Total billed 200,000; received 100,000; **balance due 100,000** | INR 100,000, `Balance Due` | Outstanding balance matches scheduled debit; accept | High |
| `image_03` / `event_1545` | Settled INR grocery debit | **Net Amount 41,272**; Cash Paid 41,272 | INR 41,272, `Cash Paid`/`Net Amount` | Both final fields agree and match settled purchase; accept | High |
| `image_04` / `event_1700` | Settled INR grocery-order debit | Thirteen line totals summing to **Item Bill 2,854**; final order fields are cropped | No accepted final amount. Retain INR 2,854 only as `Item Bill` lower-bound candidate | The crop ends inside “Total Order Bill Details”; taxes, fees, credits, or discounts may follow. Reject as a final charge and use the conservative failure path | High confidence in candidate; unresolved final |
| `image_05` / `event_1786` | Pending INR telecom debit; settlement 2026-02-09 | Previous balance 3,543.54; payments 3,543.54; monthly charges/**due through 2026-02-06 704.05**; **due after 2026-02-06 822.05** | INR 822.05, `Amount due after 06-Feb-2026` | Settlement occurs after the cutoff and request date. Resolve `REC-08` in favor of 822.05 and reserve that pending debit once; accept | High |
| `image_06` / `event_3051` | Settled INR grocery invoice debit | Item/delivery rows; **invoice Total 1,995.00** | INR 1,995, `Total` | Total is supported by amount-in-words and matches debit context; accept | High |
| `image_07` / `event_3231` | Settled INR restaurant debit | Subtotal 8,122; SGST 203.05; CGST 203.05; **tax Total 8,528.10**; rounded `Grand Total` 8,528 | INR 8,528.10, exact tax `Total` | Arithmetic total is exact and the higher complete debit is safer. It settled before `request_35`, so do not subtract it again; any indirect forecast use requires a supported series policy; accept | Medium-high |
| `image_08` / `event_4535` | Settled INR property-maintenance debit | Charges 13,880 + 1,050 + 409; **Total Amount Received 15,339** | INR 15,339, `Total Amount Received` | Components sum exactly and match settled payment; accept | High |
| `image_09` / `event_5170` | Settled INR water-bill debit | Charged amount 723; line amount 723; **Total Amount Received 723** | INR 723, `Total Amount Received` | All amount fields agree; accept | High |
| `image_10` / `event_6033` | Pending INR large-grocery debit; settlement 2024-06-10 | Subtotal 72,045; taxes 1,513.13 x2 and 2,304 x2; **Total/Balance Due 79,679.26** | INR 79,679.26, `Balance Due` | Complete invoice total matches pending obligation; accept | High |
| `image_11` / `event_6859` | Scheduled INR hospital debit | **Total Bill/Amount Payable/Balance 3,650**; paid 0 | INR 3,650, `Amount Payable` | Payable and balance agree and match scheduled debit; accept | High |
| `image_12` / `event_7307` | Settled USD taxi debit | Ride 28.50; surcharge 5; **subtotal/total 33.50**; cash tendered 40; change 6.50 | USD 33.50, `Total` | Cash tendered is not the expense; fare plus surcharge agrees; accept | High |
| `image_13` / `event_7941` | Settled INR tote-order debit | Items 699 + 1,599; item total 2,298; **Total paid 2,298** | INR 2,298, `Total paid` | Components and final payment agree; accept | High |
| `image_14` / `event_9421` | Settled INR pharmacy debit | Handwritten lines 1,500; 724; 796; 550; 303; 670; explicit **TOTAL 4,543.00** | INR 4,543, handwritten `TOTAL` | The six lines sum exactly to 4,543 and corroborate the labeled total. The debit settled before `request_101`, so it is historical evidence and is not subtracted again; accept | Medium-high |
| `image_15` / `event_9806` | Settled INR airline-ticket debit | Taxable 9,124; airport 388; pre-tax 9,512; taxes 228 + 228; air-travel inclusive 9,580; **Grand Total 9,968** | INR 9,968, `Grand Total` | Final total includes all displayed charges and taxes; accept | High |
| `image_16` / `event_10521` | Settled INR EV-charging wallet debit | Energy 333.24; CGST 29.99; SGST 29.99; **Total 393.22** | INR 393.22, `Total` | Components sum exactly and match final wallet charge; accept | High |

### Image Link And Domain Validation

- `images.csv` contains exactly 16 unique image rows and all 16 PNG files
  exist.
- Each `related_event_id` exists, belongs to the same user, and has a blank
  source `amount`; no blank amount is treated as zero.
- Every selected currency matches the linked event currency. The images cover
  IDR, INR, and USD; no conversion is performed during extraction.
- Selected cash effects follow the linked event direction: `image_01` is the
  sole credit and the other 15 are debits.
- Pending/scheduled debits remain obligations at their supplied settlement
  dates. Settled pre-request image events remain history and are not subtracted
  from the opening balance again.
- Dates printed on a carrier corroborate identity but do not replace supplied
  event/settlement dates unless an explicit accepted amendment requires it.

## FIN-015 Decision: Context-Appropriate Image Amount

FIN-015 is resolved for 15 carriers and has a conservative fallback for the
cropped `image_04`. Use the following deterministic selection order:

1. Validate that the image and blank-amount event agree on user, request/event
   linkage, document kind, currency, direction, and relevant date.
2. For a salary credit, choose deposited `net pay`, not gross earnings,
   allowances, or deductions.
3. For an outstanding or scheduled debit, choose the balance/payable/due amount
   applicable on the supplied settlement date. A date-conditioned later fee is
   included only when settlement crosses that document cutoff.
4. For a settled receipt or payment, choose the final paid/received total. Do
   not use cash tendered, change, a component, subtotal, tax alone, prior
   balance, or amount already paid against an outstanding balance.
5. For a pending invoice debit, choose the complete final total or balance due,
   including displayed taxes and fees.
6. If two complete, context-compatible final fields conflict, apply the
   repository's financially safer rule: higher for a debit, lower for a credit;
   retain both candidates and the reason for selection.
7. A subtotal or partially visible amount is not made “conservative” by calling
   it final. When crop, legibility, currency, or document semantics prevent a
   complete context-appropriate selection, reject the extracted fact. Do not
   invent a surcharge, use zero, or silently omit the obligation.
8. A required unresolved debit amount propagates an evidence-validation
   failure/conservative no-recommendation state until a trusted cached fact or
   complete carrier is available. A settled historical debit already reflected
   in the supplied available balance is not subtracted again and does not make
   the whole request fail merely because its carrier is incomplete. It must
   never enter amount-dependent forecasting as a guessed numeric event.

`image_04` therefore remains explicitly unresolved rather than accepting its
INR 2,854 item subtotal as a final charge. This is safer and more reproducible
than the lower-authority claim that the cropped subtotal is confirmed.
For `request_19`, `event_1700` settled one day before the request, so preserve
the extraction failure without subtracting the debit again or automatically
rejecting the request. The solved sample exposes no ground-truth extracted
image amount; its completed recommendation does not prove that INR 2,854 was
the intended final charge.

## Deferred Work And Handoff

- `EV-003`: classify the remaining evaluation messages in normalized batches.
- `EV-007`: create deterministic extraction and failure fixtures only after
  product schemas exist.
- Decide the production OCR/provider strategy, cached-fact format, and whether
  extraction returns one validated fact or labeled candidates for caller-side
  adjudication under `ENG-002`/`EV-007`; this pack does not make that
  architecture decision or require a paid provider.
- Sample-oracle work may consume the 15 accepted image values. It must preserve
  the `image_04` validation failure and the unresolved debit sub-fact in
  `message_10` rather than converting either into a guessed amount.
- FIN-007 needs corpus-wide empirical validation after `EV-003`; its fallback is
  already defined here. FIN-015 needs no further current-image review unless a
  complete `image_04` carrier or higher-authority fact becomes available.

No conclusion in this pack is an affordability decision, payment-plan choice,
or permission for evidence text to bypass deterministic financial policy.
