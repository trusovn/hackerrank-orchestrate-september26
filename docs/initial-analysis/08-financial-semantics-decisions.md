# FIN-MIN Financial Semantics Decisions

Status: **DECIDED FOR PLANNING**, with bounded implementation experiments

Recorded: 2026-09-12

Scope: FIN-001–FIN-006, including FIN-004A, and FIN-008–FIN-014

## Authority And Evidence Boundary

[`../../AGENTS.md`](../../AGENTS.md) and
[`../../problem_statement.md`](../../problem_statement.md) govern. This document
supplies planning dispositions for the remaining questions in
[`04-open-questions-and-hypotheses.md`](04-open-questions-and-hypotheses.md).
It is an input to a future master plan, not that plan or a claim that the
financial engine has been implemented or matches the public oracle.

Evidence comprises direct reading of the public sample rows, their profile and
payment-option rows, selected lifecycle rows, the contract in
[`01-contract-and-invariants.md`](01-contract-and-invariants.md), structural
results in [`06-structural-reconciliation.md`](06-structural-reconciliation.md),
and accepted facts in
[`07-evidence-decision-pack.md`](07-evidence-decision-pack.md). The dataset
fingerprint is recorded in document 06. The supplemental
[`assumptions-ambiguities.md`](assumptions-ambiguities.md) and
[`rev-eng.md`](rev-eng.md) supply experiment leads only. No ledger, policy
sweep, extra message classification, external model call, or hidden-label
inspection was performed here.

**A** below means authoritative; **C** means an explicitly selected conservative
or deterministic interpretation where the authority leaves detail unspecified;
**E** means a bounded implementation experiment with a selected starting rule.
Public request IDs identify relevant discriminators, not proof that one
unimplemented policy reproduces their answers. Where no public row isolates a
boundary, a synthetic fixture is required and is labeled accordingly.

FIN-007 and FIN-015 remain owned by document 07. In particular, `image_04` has
no accepted final amount: INR 2,854 is an item subtotal. Its `event_1700`
settled before `request_19`; it is already represented in opening cash and is
not subtracted again. Its failed extraction alone does not reject that request,
and it cannot supply a guessed amount to a recurring-spend calculation.
Accepted amounts remain INR 822.05 for `image_05`, INR 8,528.10 for `image_07`,
and INR 4,543 for `image_14`.

## P0 Dispositions And Acceptance Signals

| Item | Selected rule / safe starting fallback | Evidence and rejected alternatives | Public discriminator / implementation-time acceptance signal |
|---|---|---|---|
| FIN-001 | **C:** supplied available balance is opening cash at the request boundary. Settled history supplies evidence, not replayed cash deltas. | Profile meaning and pre-request receipts support this; reject replaying all history or reconstructing a new opening balance. Exact oracle arithmetic remains unverified. | `request_16`, `17`, `19`, `24`: changing a historical settled row must not directly change opening cash; only justified forecast inference may change. The historical cropped receipt must not become an extra debit. |
| FIN-002 | **C/E:** fixed inclusive window from request date through day +90; reserve pending debits at opening; unknown intraday ordering uses debit-before-credit, then proposed payment. Explicit settlement timing may override ordering. | The authority requires 90-day safety but does not choose day 89 versus 90 or an intraday order. Salary-day waits support payment after settlement, not necessarily credits before every debit. Reject treating `event_date` as cash date and adding a rolling extra 90 days after each payment. | `request_03`, `08`, `18` test salary-date payment. EXP-DATE tests day 89/90 and same-day ordering; no supplied row settles on its own request date, per document 06. |
| FIN-003 | **E:** explicit ongoing obligations plus strict supported recurrence; uncertain essential debit patterns use the conservative envelope/unresolved path below. | Recurring expenses are required; repeated descriptions alone do not prove cadence. Reject recurring all rows, ignoring all inferred expenses, or adding an unexplained extra 30–60-day reserve. | `request_02`, `05`, `13`, `16`: EXP-RV records accepted/rejected series and candidate deltas; no duplicate occurrence or fabricated series. |
| FIN-004 | **E:** maximum observed comparable complete-cycle spending envelope, reserved at cycle start, for supported variable spending. | Conservative variable forecasting is required; its statistic is unspecified. Reject mean/latest as established oracle policy and reject repeating each purchase plus its category total. | `request_02`, `08`, `13`, `17`, `19`: EXP-RV compares exactly three policies; unknown `image_04` cannot enter a numeric aggregate as zero or 2,854. |
| FIN-004A | **E:** start with confirmed individual future credits and explicitly ongoing grounded income; do not extend a next-only confirmation into later salaries. Compare strict history-supported continuation before widening credit assumptions. | Forecasting recurring income is authoritative, but “next confirmed salary” is not confirmation of every later credit. Conversely, absence of a scheduled row does not prove employment ended. `event_390` explicitly says final payroll; message stops and one-cycle amendments remain effective. | `request_02`, `03`, `05`, `07`, `12`, `13`, `15`, `25`: EXP-RV distinguishes continued income, stopped income, one-time adjustments, and missing FX. This fallback can underpredict; that is reported, not called an exact match. |
| FIN-005 | **A/C:** include all supported baseline recurring debits and confirmed obligations; fixed/protected events cannot be changed, and flexible events stay in baseline until an allowed action changes them. | Otherwise optional changes would have no financial effect and fixed obligations could be ignored. Reject limiting baseline expenses to the profile's protected categories. | `request_06`, `11`, `21`: baseline amount and earliest date are unchanged when optional-change candidates are enabled; changed forecasts alone receive the savings. |
| FIN-006 | **A/C:** use the lifecycle matrix below; reserve a pending debit once, even when described as a possible duplicate, until cancellation/duplicate identity is validated. | Authority explicitly excludes pending credits, failed/cancelled rows, duplicate records, and non-cash values. A link is not proof that both rows represent the same cash effect. | `request_01`, `05`, `06`, `20`, `21`, `22`, `24`, `25`: one fixture per matrix row; no credit from an unsettled refund, no double debit from reserve then settlement. Retry/dispute/sale boundaries without a public discriminator use synthetic fixtures. |
| FIN-008 | **A/C:** exact directed settlement-date FX; exact decimal multiplication, no intermediate money rounding. Missing required rate is a validation failure. | Document 06/FIN-008 reject latest-prior rates and chained/inverted pairs. `event_2288` is USD 1,800: at 15,833.33 the exact IDR value is **28,499,994**, not 28,500,000. | `request_25`: exact conversion fixture plus EXP-NUM. Foreign forecasts without their own supplied dated rates cannot inherit a historical rate. |
| FIN-009 | **C:** exact decimal arithmetic; safe capacity rounded down to 0.01 at output, never up; plain decimal serialization with the table below. | Public samples contain fractional IDR and mixed lexical scales. Reject binary floats, currency-based integer rounding, and treating lexical zero trimming as proven scoring behavior. | `request_02`, `06`, `12`, `17`, `21`, `22`, `25`: parsed numeric values round-trip; option amounts and fees remain exact; EXP-NUM separates formatting from financial residuals. |
| FIN-010 | **C:** positive populated cap and `number_of_payments <= max_installment_months`; exact day intervals; completion also within deadline and forecast. | Payment-count interpretation matches the structural count convention and chosen public options. It is not proved by counts alone. Reject replacing 28/30/31 days with calendar months or granting unlimited installments on a blank cap. | `request_02`, `03`, `12`, `17`, `19`, `22`: supplied selected schedules pass count/date checks. Synthetic three payments across two calendar months at cap two must fail. EXP-CAP may compare elapsed duration, without silently replacing the default. |
| FIN-011 | **A/C:** compute baseline earliest across every date in the fixed forecast independently of methods, changes, and desired deadline. Validate the entire request-window trajectory for each candidate. | `request_06`, `11`, `21` have earliest dates after their deadlines; `request_12` has earliest today despite installments. Reject clipping the reported date to the deadline or computing it from the selected changed plan. | Those four rows plus `request_03`, `08`, `18`: earliest at deadline allowed; later-than-deadline capacity reported but cannot authorize a late recommendation; empty only when no baseline full-payment date is certified. |
| FIN-012 | **A:** construct exactly safe-today plus remainder on baseline earliest, with every eligibility gate; validate the composed schedule. | `request_19` supplies the exact shape. Reject a free choice of remainder date and the proposed mathematically impossible counterexample discussed below. | `request_19`: 28,820 on 2024-09-04 plus 10,840 on 2024-09-15, total 39,660. Property guard checks construction and trajectory equivalence. |
| FIN-013 | **C/E:** a validated recurring-series anchor identifies all changeable future occurrences; actions do not undo history or an already committed pending debit. Start with explicit floor reductions and allowed stops, combinations of at most three distinct series. | Public changes use `event_476`, `989`, `1815`, `1816` and floor amounts. Scope and equal-change tie behavior remain inferred. Reject arbitrary reductions below floors and claiming minimum disruption is an authoritative ranking criterion. | `request_06`, `11`, `21`: EXP-CHANGE compares series versus occurrence scope, with fixed default and boundary fixtures. Recompute cash effects once and retain baseline amount/earliest. |
| FIN-014 | **A/C:** filter complete safe eligible plans, then apply the published ranking; use the status/method table below for unsupported corners. | `request_12` separates capacity from preference; `request_19` separates partial and financed total cost. No category or emergency bypass is authorized. | All 25 samples plus synthetic no-method, late-only, changed-wait, equal-offer and fee-free tie cases: every output has one internally consistent status/method pair. |

## Recurrence, Recurring Income, And Variable Spending

These are finite starting policies, not facts about the hidden generator.
Use settled history before the request and accepted evidence; never use sample
output labels as series features or create user/request-ID rules.

| Concern | Selected starting rule | Experiment alternative / safety boundary |
|---|---|---|
| Identity | Same user, event type, direction, category, currency, compatible normalized description and cadence. Separate clearly distinct income sources and fixed/flexible commitments. | A category envelope may combine residual variable purchases, but not a salary, refund, transfer, or separately modeled fixed obligation. Ambiguous identities cannot receive a multi-series amendment. |
| Fixed cadence | At least three settled observations forming two consecutive intervals: same day-of-month with month-end clamping, or exact 7/14-day cadence. Explicit recurring evidence can establish the series directly. Forecast only after the opening boundary. | Alternative permits at most ±2 days of timing drift around those cadences; use earlier plausible debit date and later plausible credit date. Do not search arbitrary intervals. |
| Recency and stopping | Explicit end/cancellation overrides history. A missed expected credit occurrence without confirmation makes further income uncertain; exclude it in the starting policy. A missed debit is not automatically cancelled. | Stale, unsupported essential debit continuation needs a bounded envelope or an unresolved-materiality result, not invented arrears. Do not debit supposed missed historical occurrences again. |
| Fixed amount | Use the current explicitly amended amount; otherwise latest stable recurring debit amount. Conflicting grounded debit amounts select the higher; credit amounts the lower. | A varying sequence moves to variable policy; it is not falsely declared fixed. No automatic salary increase or temporary-pay reversion. |
| Explicit future occurrence | Prefer a confirmed supplied occurrence over the inferred occurrence for that same validated series/cycle; keep separate arrears or outstanding balances as separate obligations. | Inferred salary plus scheduled next salary must not produce two credits. Rent arrears from `image_02` are not silently merged into ordinary monthly rent. |
| Continuing income | Starting policy I0 counts each confirmed occurrence and recurs an explicitly ongoing series with grounded amount/cadence, subject to endings and amendments. I1 additionally recurs strict, recent historical salary series meeting the cadence rule. | Neither policy recurs windfalls, refunds, reimbursements, one-time arrears, unapproved commission, pending platform payouts, or “first salary” beyond its evidenced duration. History alone never overrides termination. |
| Variable cycle | Use the latest three complete calendar months before the request as comparable cycles, where available. Need at least two complete observed cycles for a category envelope; otherwise use grounded exact obligations or mark unsupported material forecasting. | Calendar months with unavailable required numeric observations are not zero months. Explicit one-time/unusual rows stay excluded. No external category budget is introduced. |
| Variable amount | V0: maximum complete monthly category total. Reserve the envelope at the start of each forecast calendar-month segment; reserve the full current-month envelope at request opening as the conservative initial partial-month treatment. | V1: maximum same-series occurrence amount on supported observed cadence. V2: latest three complete-month mean, rounded upward to 0.01, with the same envelope timing as V0. These alternatives cannot be combined with V0 for the same rows. |
| Envelope ownership | Every source event belongs to at most one forecast family. An explicit occurrence replaces its matching projected slot; an unrelated pending purchase remains an additional obligation. | Reject summing an envelope and all its individual forecast purchases. A known missing historical amount does not alone invalidate the request; if a proposed envelope depends on it, do not certify that envelope as complete. |
| Unbounded debit | If a required future debit amount remains unknown and no supported bound exists, certify no payment under that forecast; preserve the diagnostic. | For example, the amount-less childcare notice in `message_10` remains unresolved. An output fallback may use zero certified capacity, empty earliest, `not_affordable/not_recommended`, `none` plan/changes, and an evidence-gap explanation; this is not a claim that mathematical maximum capacity is known to be zero. |

The conservative envelope can over-reserve the partial first month and I0 can
omit historically supported future income. These are declared starting risks.
The bounded experiment must expose their residuals before a more permissive
policy is promoted. Do not claim to have reproduced public safe amounts using
these unexecuted rules.

## Forecast Dates And Event Lifecycle

Let `D` be request date, `T = D + 90 days`, `A` requested amount, and `M` the
minimum balance. Keep a cash balance and, if needed, reserved amounts; safety
uses spendable cash after reserves. Reserve-to-settlement conversion releases
the hold while applying the actual debit, leaving spendable cash unchanged.

| Boundary | Decision |
|---|---|
| Opening | Start with profile cash; do not replay settled history at or before D. Reserve current pending debits once before any request payment. An explicitly unresolved conflict between snapshot cutoff and a same-day settled row is not a license to add cash twice. |
| Horizon | Check opening and every financial checkpoint on D through T inclusive. Do not extend the horizon from each hypothetical payment date. Reject a schedule extending past T under the starting policy even if its desired deadline is later. |
| Same date | Follow explicit grounded timing when available; otherwise ordinary debits precede credits, and a proposed payment follows all dated settlements. Salary cannot fund a payment before its settlement checkpoint. Check M after each debit/payment; deterministic ID order breaks same-kind ties. |
| Baseline failure | If the baseline already violates M before a candidate payment, the whole forecast is unsafe. Report no positive certified baseline safe amount; do not ignore earlier failures when searching later dates. A permitted changed forecast may independently repair it. |
| Safe today | On a valid additive baseline, use the smallest spendable headroom over all checkpoints, capped to [0, A], then round down for output. Optional changes and method preferences do not enter this calculation. |
| Earliest | Test D and each later date through T, using a single full debit A at its payment checkpoint. A later credit can create capacity; an unresolved future essential debit prevents certification. |

| Lifecycle / status | Forecast cash effect and recurrence treatment | Relevant public evidence |
|---|---|---|
| Settled historical cash | Already in opening balance; history only. A settled one-time credit never recurs merely because it is positive. | `request_17`, `19`; `event_2165` / `request_24` |
| Pending debit | Reserve now and retain until cancellation or settlement; no second charge at settlement. If settlement is beyond T, the known hold still remains unavailable. | `event_102` / `request_01`; `event_1786`, `1787` / `request_20` |
| Pending credit | Zero available cash throughout unless explicit validated settlement supersedes pending status. A predicted date passing does not settle it. | `event_1785` / `request_20` |
| Scheduled debit | Debit on settlement date; future commitment stays in baseline even if its category is not protected. A blank required amount/date must be resolved before a safe recommendation. | `event_1442` / `request_16` |
| Scheduled confirmed income | Credit once at settlement; further recurring credits require the selected recurrence evidence policy. | `event_103` / `request_01`; `event_2288` / `request_25` |
| Failed/cancelled | No cash movement from that row. A separately scheduled retry or settled replacement still has its own valid effect; do not cancel an entire recurring bill solely because one attempt failed. | `event_100`–`101`, `438`, `557`, `2287` |
| Proven duplicate / possible duplicate | Collapse a proven same-cash-effect duplicate. A description saying possible duplicate/dispute alone cannot release a pending debit; retain reserve until evidence resolves it. | Synthetic duplicate and disputed-hold fixtures; no isolated solved discriminator claimed |
| Purchase and refund | Original settled purchase stays historical; refund is a separate cash effect and only settled cash becomes available. `linked_event_id` alone does not net them. | `event_1784`–`1785` / `request_20` |
| Investment purchase / value / sale | Purchase is cash debit if applicable after opening; valuation is never cash; settled sale proceeds are distinct cash, not valuation plus sale. One-off contributions do not automatically recur. | `request_21`, `22` for valuation; synthetic settled-sale fixture |
| Work expense / reimbursement | Expense is a debit; pending/unapproved reimbursement supplies no cash. Only grounded confirmed settlement may supply a future credit. | Synthetic fixture; do not assert corpus-wide message coverage |
| Internal transfer | Neutralize only a validated same-user cash-neutral debit/credit pair. Do not hide a real outflow while the corresponding cash is pending/unavailable. | `message_13` / `request_18` has no matched supplied pair; synthetic matched/unmatched fixtures |

## FX, Arithmetic, And Serialization

| Surface | Decision | Required signal |
|---|---|---|
| Source numbers | Parse finite decimal strings exactly; reject missing required numbers, negative obligations, NaN, infinity, malformed values. Preserve provenance. | No binary-float arithmetic or fabricated zero for a missing amount. |
| FX lookup | Use `(settlement_date, event_currency, home_currency)` and multiply by the supplied directed rate. Home-currency records need no lookup. | Wrong date, reverse pair, missing pair and conflicting duplicate rate fixtures reject conversion. |
| Arithmetic | Keep exact source/rate products and sums without intermediate money rounding; choose decimal precision sufficient to retain those products. For a non-terminating forecast statistic, round debit estimates upward and credit estimates downward to 0.01. | USD 1,800 × 15,833.33 = IDR 28,499,994; no approximation to 28.5 million. |
| Capacity output | All observed currencies permit a 0.01 output unit for this dataset; floor nonnegative safe capacity to that unit, cap at A, normalize negative zero. This is a selected reporting policy, not an assertion about currency standards. | Fractional IDR remains valid; rounding cannot change unsafe headroom into a safe cent. |
| Plans and options | Preserve exact supplied per-payment numbers and total; partial remainder is exactly A minus serialized safe amount. Do not round each installment again, distribute a new last-payment adjustment, or add the financing fee twice. | Sum equals A for full/wait/partial; option payment count × payment amount equals total payable, and total equals A + supplied fee. |
| Text numbers | Plain decimal, no grouping or exponent. Scalar safe amount trims trailing zeros. In plans/actions, integers omit `.00`; nonintegers use two decimal places for current data, retaining further supplied precision if encountered. | `620.4` capacity may coexist with plan `620.40`; compare parsed value separately from lexical form. |
| Dates and CSV | ISO calendar dates; exactly the specified header order. Use a CSV writer for commas/quotes/newlines; `none` for empty plan/actions and empty string for absent earliest. | Parse/write/parse round-trip preserves values and exactly one row per evaluation request. |

## Installments, Partial Payment, Changes, And Ranking

| Plan dimension | Decision |
|---|---|
| Installment dates | Payment i is `first_payment_date + i * payment_frequency_days`, i from zero to count minus one. Positive integer count/interval, positive amounts, no payment before D; final date at or before both deadline and T. |
| Installment cap | Require method acceptance and a populated positive cap; count must not exceed it. A blank cap fails installment eligibility, not the entire request. No invented or resized offer. |
| Fee and matching | Match one complete supplied option, including schedule, count, amounts, fee and total. `payment_option_53` totals 41,246.40, not the supplemental 42,124.60. |
| Partial gates | Request allows partial, user accepts partial, 0 < safe < A, baseline earliest F exists and is at/before deadline; plan is `(D, safe), (F, A-safe)`. Full-payment acceptance is not required for partial. |
| Reduction eligibility | Recurring series, non-protected category, flexibility reducible or reducible_or_stoppable, category in willing-to-reduce list; explicit nonnegative floor exists and is less than baseline amount. Selected starting `reduce_to` is that floor. |
| Stop eligibility | Recurring series, non-protected category, flexibility stoppable or reducible_or_stoppable, category in willing-to-stop list. A stop can remove future recurring debits; it does not erase a committed pending debit. |
| Action identity and duration | Anchor to latest compatible supplied historical occurrence by settlement date then stable ID; validate exactly one series. Apply throughout the forecast from D to future uncommitted occurrences. A future exact series occurrence may anchor when no historical anchor exists and recurrence is explicit. |
| Action enumeration | Try no changes first, then all permitted stop/floor-reduction sets of one to three distinct series; never stop and reduce the same series under different occurrence IDs. A reduction that cannot be mapped from an envelope to an identified recurring expense is ineligible. |
| Ranking | First reject unsafe, ineligible, late or incomplete plans. Then prefer no changes, lowest total paid, earliest first payment, fewest payments, lowest supplied option ID. Compare IDs by stable text order; this tie convention is unproven and must be explicit in fixtures. |
| Residual ties | For the same otherwise equal candidate/offer, prefer fewer actions, then smaller total forecast debit reduction, then sorted action text. These deterministic tie extensions never outrank a published criterion. Candidates without a supplied option ID use a stable method key only after applicable supplied-offer comparisons. |

**FIN-012 correction.** Under a common additive baseline, an unsafe
two-payment counterexample cannot exist if the premises hold. Before F, the
partial schedule has paid only S, which is safe by the definition of safe-today
S across the entire horizon. At and after F, it has paid total A and has the
same balance as the safe standalone full payment at F. Therefore the composed
schedule is safe. Keep independent validation to detect inconsistent ledgers,
rounding, dates, duplicated payments, or violated premises; do not invent a
fixture claiming otherwise. Spending changes only lowering debits preserve
this property when the baseline inputs are identical.

## Complete Status And Method Decision Table

The following rows describe the winning eligible candidate after ranking;
they do not bypass competition from another cheaper/no-change plan.

| Winning candidate / condition | Status | Method and plan | Capacity fields |
|---|---|---|---|
| Baseline full A safe at D; full accepted | affordable_now | full_payment; one payment at D | safe=A; earliest=D |
| Eligible exact supplied installment option, with or without changes | affordable_with_plan | installments; exact option schedule | Baseline safe and earliest, even if earliest=D or empty |
| Eligible two-payment partial schedule | affordable_with_plan | partial_payment; prescribed two entries | Baseline safe and earliest |
| Full at D becomes safe through permitted changes; full accepted | affordable_with_plan | full_payment; one payment at D, actions listed | Preserve baseline safe and earliest |
| Baseline full becomes safe at later F at/before deadline; full accepted | affordable_later | wait; one full payment at F | Baseline safe; earliest=F |
| Full becomes safe later at G through permitted changes; full accepted, G at/before deadline | affordable_with_plan | wait; one full payment at earliest safe changed date G, actions listed | Baseline safe and baseline earliest, which can differ from G; unsampled conservative extension, independently simulated |
| Full safe only after deadline; no other eligible on-time plan | not_affordable | not_recommended; none | Preserve baseline safe and later earliest; explain deadline failure |
| Full capacity exists but no accepted safe method/option; no other candidate | not_affordable | not_recommended; none | Preserve baseline capacity/earliest; explain preference or option constraint, not absence of money |
| No safe complete candidate within horizon | not_affordable | not_recommended; none | Preserve certified safe; earliest empty if none safe |
| Required future-debit evidence unbounded | not_affordable | not_recommended; none | Conservative certification fallback described above; explanation discloses evidence gap |

For the unsampled fallback rows, `not_affordable` describes failure to produce
an eligible complete request under the contract. It must not erase genuine
preference-independent financial capacity or assert a false reason. There is
no extra permission for emergencies, investments, or priority categories to
override accepted methods or the minimum balance.

## Bounded Implementation Experiments

Experiments are deferred, not executed. They run offline on the 25 public
samples with frozen accepted evidence, never on evaluation labels. Each
candidate needs only one sample pass; cache identical subcomputations. Stop at
the stated cap, record residuals, and keep the starting fallback when evidence
does not discriminate. No experiment may authorize invented facts, violate
the contract, or silently change FIN-007/FIN-015 evidence decisions.

| ID / owner | Finite candidate scope | Discriminators and acceptance / stop rule |
|---|---|---|
| EXP-RV / FP-001, FP-002, FIN-004A | At most 12 configurations: two cadence policies (strict; ±2-day tolerant) × three variable policies V0/V1/V2 × two income policies I0/I1 described above. Three complete recent months; fixed 90-day horizon; no buffer tuning, extra lookbacks, request-specific exceptions, or subsequent sweep expansion. Starting configuration strict/V0/I0. | Primary `request_02`, `03`, `05`, `07`, `08`, `12`, `13`, `15`, `17`, `19`, `25`; report all 25. Every promoted recurrence must cite source observations and exclusions; explicit stop/next-only fixtures must pass. Promote only a contract-valid global candidate with reproducible improvement and no unexplained new optimistic safety failures; if candidates trade off materially without a clear safer winner, retain default and record uncertainty. |
| EXP-DATE / FP-003 | At most four configurations: day +89/+90 × unknown same-day debit-first/credit-first. Pending reserves remain at opening in every candidate; scheduled-date movement and a rolling horizon are excluded. | `request_03`, `08`, `18` plus synthetic opening, same-day salary/expense, and day-90 debit fixtures. A tied public result keeps inclusive +90 and debit-first. Never infer intraday ground truth from the existence of a salary-day wait alone. |
| EXP-NUM / FP-004, FIN-009 | At most two numeric configurations: output-only rounding versus per-conversion rounding (debits up, credits down to 0.01). One canonical renderer plus raw/parsed comparisons; no alternative FX date/path. | `request_25` exact FX and fractional-money fixtures; `request_02`, `06`, `12`, `17`, `21`, `22` formatting. Tie keeps exact internal products/output-only rounding. A lexical improvement cannot justify optimistic arithmetic. |
| EXP-CAP / FP-005 | Two filters on supplied sample options: selected payment-count cap versus elapsed-duration endpoint (`last <= first + cap calendar months`, clamp day at month end). All other eligibility and safety rules fixed. | `request_03`, `17`, `19`, `22` and synthetic boundary. Counts in document 06 are observations under definitions, not oracle proof. If both reproduce selected public options, retain count cap. |
| EXP-CHANGE / FP-006 | Two scope interpretations over only `request_06`, `11`, `21`: full series versus next occurrence only; same explicit floor/stop action candidates in each. At most six sample replays, plus synthetic protected/floor/pending/duplicate-series tests. | Expected actions are `stop:event_476`, `reduce_to:event_989:665950`, and `stop:event_1815|reduce_to:event_1816:23.50`. Exact action matches alone do not prove forecast scope. Keep series-wide default if evidence ties; do not introduce a continuous optimization search. |

These bounds replace an open-ended policy hunt. Ledger reconstruction and
tests will supply evidence; this document supplies the decisions needed to
specify that work. A mismatch is recorded with the responsible policy and
source IDs, not patched with an expected-answer lookup.

## Output Validation And Public-Sample Metrics

| Validation surface / EA-001 | Required acceptance signal |
|---|---|
| Coverage and schema | Exactly eight ordered columns and one unique row for each `requests.csv` ID, no sample rows or extras. Public evaluation uses `sample_requests.csv` separately. |
| Domains | Finite home-currency numbers; 0 <= safe <= A; allowed status/method; valid ISO dates; nonempty grounded explanation; no NaN/null spellings replacing required strings. |
| Plan structure | Parse chronological positive payments; `none` only with no recommendation; no payment before D or after deadline/T. Full/wait/partial totals exactly A; installments exactly one option. |
| Eligibility | User method acceptance; request partial flag and prescribed shape; installment cap/date/total; no preference bypass based on request type. |
| Spending actions | Zero to three actions; valid same-user recurring targets; allowed category/flexibility; protected exclusion; reduction floor; no duplicate series or stop/reduce conflict. |
| Cross-field consistency | Status/method table; affordable_now implies safe=A and earliest=D, but the converse does not ignore preferences. Amount and earliest recomputed from unchanged baseline. Changed-wait date need not equal baseline earliest. |
| Safety | Independently replay selected plan and actions from validated facts across the entire forecast, checking every debit/payment checkpoint. An empty plan never certifies the underlying baseline as safe. |
| Explanation | Facts, amounts, dates, constraints and action names come from the trace; do not claim income settled, receipt total known, or deadline met when it is not. No unsupported “cannot afford” rationale for a preference-only failure. |

| Metric / EA-002 | Definition and reporting |
|---|---|
| Contract failures | Count by invariant and request; target **zero**. Evidence-rejection diagnostics are separately counted, never hidden as validator success. |
| Categorical quality | Exact status and method match counts out of 25, separately and jointly; confusion tables when mismatches exist. |
| Money quality | Exact decimal match count, signed error `predicted - expected`, absolute error, and normalized error `abs(error)/requested_amount` per request; summarize within currency and across normalized errors. Do not average raw INR, IDR, EUR, USD and ZAR amounts together. |
| Date quality | Exact date match count; empty/nonempty disagreement separately; signed/absolute day error only for pairs where both dates exist. |
| Plan/change quality | Raw string exact match and parsed semantic exact match separately; parsed plans retain dates/order/amounts, changes compare validated action sets. Fee differences and missing/extra payments get distinct reasons. |
| Scenario quality | Break down preference-only capacity, salary change/stop, pending debit/credit, FX, image evidence, partial, installments and spending changes using public evidence IDs; report small denominators. |
| Explanations | Deterministic trace-consistency checks and bounded mismatch inspection; no guessed hidden lexical/semantic score. |
| Optimism risk | Report positive safe-amount residuals, earlier-than-expected dates and newly affordable predictions separately. These are warning signals, not proof of unsafe behavior without a ledger explanation. |

EA-003 starting acceptance is zero contract/safety-fixture violations and a
complete 25-row metric report with every mismatch assigned a cause or explicit
unresolved policy. Aim for exact public matches but do not invent a percentage
threshold or organizer weighting. Passing these checks establishes a measured
implementation baseline, not hidden-test accuracy. No live-model or full-dataset
run is authorized by these deferred experiment definitions.

## Readiness And Verification Handoff

This document supplies evidence to evaluate the final three readiness rows:

- Every remaining P0 has an authoritative/conservative disposition or a finite
  early experiment with a safe starting fallback, including FIN-004A.
- Recurrence and variable spending have explicit candidates, sample
  discriminators, limits, stop rules and a conservative default.
- Precision, dates, lifecycle, eligibility, ranking and output validation are
  decision tables; public-sample metrics and starting acceptance are defined.

The coordinator should reconcile document 04, update only supported runbook
items, add navigation, and evaluate all eight README rows. FP experiments and
all-sample ledger reconstruction remain unchecked until actually executed;
FP-008 and EA-001–EA-003 can be marked defined for planning based on this
artifact. Nothing here claims EA-004–EA-006 implementation, corpus-wide message
coverage, or production test completion. Do not create the master plan as part
of this reconciliation.

Verification performed for this document: see the FIN-MIN completion report
and append-only root transcript. Only local Markdown-link validation and
`git diff --check` are in scope; the coordinator must not repeat them under the
agreed fast reconciliation procedure.
