# Structural Reconciliation (IA-007)

Status: **OBSERVED** — deterministic reproduction, no model involvement  
Computed: 2026-09-12  
Scope: disputed counts `REC-01`, `REC-02`, `REC-03`, `REC-04`, and `REC-13`
from the `IA-006` conflict register in
[`05-todo-and-analysis-runbook.md`](05-todo-and-analysis-runbook.md)  
Tool: [`../../tools/reconcile_structural_counts.py`](../../tools/reconcile_structural_counts.py)

Re-run after any change under `dataset/`:

```text
python3 tools/reconcile_structural_counts.py
```

## Dataset Fingerprint (IA-005)

Git revision at computation time: `0683fc1a70b32eae6d2e5ee38abbc0201923f3d7`
(`main`; `git status` clean for `dataset/`). SHA-256 over raw file bytes:

| File | SHA-256 |
|---|---|
| `exchange_rates.csv` | `3de3877e48707fea1c9cd62d1931d8cc6352992ff9549ad41a1580649b1bf3e3` |
| `financial_events.csv` | `f6a7ccf24d9bfd4a019977ea88a9086e5851b3565b1816890fee5023bbd25f1f` |
| `financial_profiles.csv` | `b91b4ccbda3d5af99bf87c313e367f25cde5b2338a2fedafcd8f71550cf86500` |
| `images.csv` | `c5a3f1686b1f98acf9f884aacf512f97f75a7923b066892ca90f7d2d34baa1f9` |
| `messages.csv` | `fd9e3a1acb604f9a855153344539e9eefa71076faabb8c427d107f4724ef52a3` |
| `output.csv` | `ee979aa8cc1b77040b2bf6da2350b313ebe95ce263cab679761293c102ac992d` |
| `request_payment_options.csv` | `aedadf63a13f5dd002934823090f543f17f42eff05f2953a1baae01d8ac91f22` |
| `requests.csv` | `f94255baa9f55857fea57b09c00a7e970c4a80ece4bf1c412fbf5fbe8225f78b` |
| `sample_requests.csv` | `1195bbe962e62a3eafa1118efc5fdef3f5fac0bf70009e6e59dab75b9228c5dc` |

Row counts: `requests` 250, `sample_requests` 25, `financial_profiles` 275,
`financial_events` 25,342, `request_payment_options` 790, `messages` 215,
`images` 16, `exchange_rates` 134. The 16 PNG files under `dataset/media/`
also hash into the checked-in tool's fingerprint output.

If a fingerprint below differs from a fresh run, every count in this document
is stale and must be re-derived before use.

## Scope Definitions

- **Sample scope** = the 25 solved public examples (`request_01..request_25`,
  users `user_01..user_25`). **Evaluation scope** = the 250 rows of
  `requests.csv` (`request_26..request_275`). The two scopes are disjoint and
  together cover all 275 users and all 275 requests.
- **Installment option** = a `request_payment_options.csv` row with
  `payment_method = installments` (515 rows: 46 sample, 469 evaluation).
- **Future event** = `financial_events.csv` row with `status` in
  {`pending`, `scheduled`} and a populated `settlement_date` strictly after
  its user's `request_date`.

### Formulas

- Installment end date (last payment date):
  `end = first_payment_date + (number_of_payments - 1) * payment_frequency_days`.
- Deadline breach: `end > desired_completion_date` of the owning request.
- Maximum-month breach: `number_of_payments > max_installment_months`
  (populated caps only; blank caps exclude the option from this check but
  still gate installment eligibility in the product).
- Rejected alternative for the month cap — elapsed calendar months between
  first and last payment exceeding the cap — yields 186 breaches, matching
  neither recorded figure, so the payment-count interpretation is the one
  consistent with `02-data-profile.md`.

## REC-01 — Installment Deadline And Max-Month Breaches

`dataset-stats.md` reported 394/515 finishing after the deadline and
173/469 over-cap; `02-data-profile.md` reported 434 and 193.

| Metric | Sample | Evaluation | Total |
|---|---:|---:|---:|
| Installment options | 46 | 469 | 515 |
| Finish after deadline | 40 | 394 | **434** |
| Exceed populated max months | 20 | 173 | **193** |

Verdict: **both documents were right at different scopes.** `dataset-stats.md`
quoted evaluation-scope denominators (469 options), `02-data-profile.md`
quoted combined-scope denominators (515 options). `02-data-profile.md`'s
434/515 and 193/515 are the correct corpus-wide figures; the supplemental
counts were not wrong, only unlabeled. No document change is required beyond
adding explicit scope labels.

## REC-02 — Option-File And User Coverage

`dataset-stats.md` claimed the option file covers only `request_01..99`;
`rev-eng.md` described 225 remaining evaluation users.

| Metric | Value |
|---|---:|
| Distinct requests covered by options | 275 (`request_01`..`request_275`) |
| Options per request | 2 (65), 3 (180), 4 (30) = 790 |
| Full-payment options (exactly one per request) | 275 |
| Evaluation requests with ≥1 option | 250 of 250 (0 missing) |
| Sample requests with options | 25 of 25 |

Verdict: **the supplemental claims are rejected.** The `request_99` bound was
a lexicographic-ordering artifact of `request_100+` sorting before
`request_099`; numeric ordering reaches `request_275`. Every evaluation
request has options, so the evaluation user count is 250, not 225.

## REC-03 — Future-Event Coverage By Scope And Type

`dataset-stats.md` claimed only 42/250 request users have any future event;
`02-data-profile.md` records 141 future settlements across 122 users.

| Metric | Sample | Evaluation | Total |
|---|---:|---:|---:|
| Future event rows | 17 | 124 | **141** |
| Users with ≥1 future event | 13 | 109 | **122** |
| Scheduled income rows (next salary) | 5 | 42 | 47 |

Verdict: **the canonical 141/122 figure is confirmed for all pending +
scheduled future settlements.** The supplemental `42/250` was the count of
*evaluation users with a scheduled next-salary income row* — a
salary-only, evaluation-only slice mislabeled as all future data. Both
figures are internally consistent once scope is stated.

## REC-04 — Events Landing On The Request Date

`dataset-stats.md` said 19 pending/scheduled expenses land on the request
date; `02-data-profile.md` said no populated settlement date equals the
request date.

| Metric | Value |
|---|---:|
| Rows with `event_date == request_date` | 21 (19 evaluation, 2 sample) |
| … of which `scheduled`, debit | 21 (14 `expense`, 7 `debt_payment`) |
| Rows with `settlement_date == request_date` | **0** |

Verdict: **both counts are correct for different columns.** The 19 (plus 2
sample rows = 21) are rows whose `event_date` equals the request date; all
are `scheduled` debits that settle strictly later. No row settles on its
request date, so `02-data-profile.md`'s settlement statement stands. Product
ordering for same-date cash movements remains owned by `FP-003`; this check
only resolves which column each document counted.

## REC-13 — Image-Backed Event Share

`rev-eng.md` claimed image extraction applies to 7.4% of full-dataset events.

| Metric | Value |
|---|---:|
| Images / resolvable event links | 16 / 16 |
| Blank-amount events without an image | 0 |
| Image-backed share of all 25,342 events | **0.0631%** |
| Image-backed share of sample-user events (2,288) | 0.70% |
| Sample users with an image-backed event | 5 |

Verdict: **the 7.4% figure is rejected.** 16/25,342 = 0.0631%, nowhere near
7.4%. The likely source is `16 images / 215 messages = 7.44%` — an
image-to-message ratio mislabeled as an event share. The exact usable
statement is: 16 events (0.0631% of the corpus, all blank-amount, all
image-backed) require image extraction, across 5 sample users.

## Disposition Summary

| ID | Losing claim | Action taken |
|---|---|---|
| `REC-01` | Neither; scopes were unlabeled | `02-data-profile.md` figures confirmed as combined scope; supplemental figures confirmed as evaluation scope |
| `REC-02` | `request_01..request_99` coverage; 225 eval users | Rejected; coverage is all 275 requests, 250 eval users |
| `REC-03` | `42/250 request users have a future event` | Rejected as stated; correct slice is 42 eval users with a scheduled next salary |
| `REC-04` | Neither; column mismatch | `event_date` (21 rows) vs `settlement_date` (0 rows) distinguished; `FP-003` keeps ordering ownership |
| `REC-13` | 7.4% of events | Rejected; 16/25,342 = 0.0631% (7.44% is images/messages) |

No canonical packet document required correction: where the supplemental
notes conflicted with `02-data-profile.md`, the profile's combined-scope
counts held, and the supplemental numbers survive only as correctly scoped
slices.