# WP-02 — Typed Evidence And Conservative Resolution

Status: **READY**  
Authority: [`master-plan.md`](master-plan.md), WP-02  
Depends on: WP-01 (**fresh review returned `CHANGES_REQUESTED`; implementation
must wait for an accepted correction**)  
Readiness route: standalone guided preflight — confirm the final WP-01 carrier
content and `RequestCase` contracts after review

```yaml
agent_tier: strong
reasoning: high
review: immediate
budget: 18 tool calls / 45 minutes / medium context
```

## Outcome

Implement one deterministic evidence boundary that converts every supplied
message and image carrier in a `RequestCase` into validated, provenance-bearing
`EvidenceFact` records or explicit conservative diagnostics. Raw carrier
content, embedded instructions, malformed candidates, unresolved credits, and
unbounded required debits must never reach lifecycle or forecasting logic as
invented financial facts.

This task has no direct user-visible recommendation effect. It enables WP-04 to
normalize grounded facts and is on the mandatory path to the first complete
deterministic recommendation.

## Direction Trace

- Direction contribution: use relevant messages and images to clarify supplied
  financial facts while keeping deterministic challenge rules authoritative.
- User-observable effect: no direct effect; enables a safe 90-day forecast that
  neither invents cash nor silently drops a required obligation.
- Why now: [`master-plan.md`](master-plan.md) orders typed WP-02 after WP-01 and
  before WP-04.
- Direction decisions used: [`../AGENTS.md`](../AGENTS.md),
  [`../problem_statement.md`](../problem_statement.md),
  [`ai-foundation.md`](ai-foundation.md),
  [`initial-analysis/07-evidence-decision-pack.md`](initial-analysis/07-evidence-decision-pack.md)
  (`EV-001`, `EV-002`, `EV-004`–`EV-007`, `FIN-007`, and `FIN-015`), and
  [`master-plan.md`](master-plan.md), sections 6–9 and WP-02.
- New direction decisions required: None.

## Authority And Scope

| Item | Contract |
|---|---|
| Product authority | [`../problem_statement.md`](../problem_statement.md) and [`../AGENTS.md`](../AGENTS.md) |
| Implementation authority | [`master-plan.md`](master-plan.md), WP-02, and the accepted decisions in [`initial-analysis/07-evidence-decision-pack.md`](initial-analysis/07-evidence-decision-pack.md) |
| Allowed product changes | `code/buy_or_wait/evidence.py` |
| Allowed evidence changes | `tests/test_evidence.py` and narrowly scoped fixtures under `tests/fixtures/evidence/` |
| Read-only upstream context | `code/buy_or_wait/domain.py`, `code/buy_or_wait/repository.py`, `code/buy_or_wait/ai_boundary.py`, and their tests |
| Input boundary | Participant-facing messages, image links, linked events, and the 16 supplied image carriers or their accepted reviewed facts |
| Out of scope | Editing WP-01 domain/repository contracts; lifecycle/FX normalization; recurrence forecasting; affordability; candidate plans; output writing; provider selection, prompts, adapters, or live calls; sample-answer fitting |
| External requirements | No network, credentials, third-party dependency, live provider, or new human image review |

## Dependency Gate

WP-02 implementation starts only after the active WP-01 correction passes its
verification ladder and a fresh independent review returns `ACCEPT`. The final
upstream contract must provide:

1. a `RequestCase` containing only the request's joined message/image carriers
   and supporting events;
2. access to the exact supplied `message_text` through `MessageRecord` or an
   approved repository-owned carrier accessor; and
3. preserved source IDs and blank request/event links needed for provenance and
   target resolution.

The reviewed WP-01 draft reads `message_text` but discards it when it
constructs `MessageRecord`. That is an upstream review/correction item. WP-02
must not work around it by reopening `messages.csv`, adding a second repository,
or editing `domain.py` concurrently.

The 16 reviewed image outcomes may be represented as validated extracted-fact
data keyed by `image_id`; this is participant-derived evidence explicitly
allowed by the master plan, not an evaluation label. An unknown or changed
image never inherits a cached amount by position or similarity.

## Public Contracts

### Resolution API

Expose from `buy_or_wait.evidence`:

```python
resolve_case_evidence(case: RequestCase) -> EvidenceResolution
```

`EvidenceResolution` is an immutable feature-owned record containing:

- source-ordered validated `EvidenceFact` values;
- source-ordered safe diagnostics for ignored or unresolved carrier outcomes;
  and
- a derived indication that an unresolved required debit blocks downstream
  certification.

Diagnostics contain a stable reason code and safe source IDs, but no raw
message text, image content, sensitive excerpt, or model response. Downstream
code consumes only validated facts and the conservative blocking state.

### Fact Validation

Every accepted `EvidenceFact` must:

- use the closed `EvidenceFactType` vocabulary from `buy_or_wait.domain`;
- carry at least one supplied `SourceReference` whose carrier exists in the
  current case;
- preserve only supplied and validated request/event targets;
- use finite non-negative `Decimal` amounts, supported currencies, and parsed
  ISO dates when those fields are present;
- include exactly the fields allowed for its fact type; and
- remain grounded in the carrier and compatible linked context.

Field-combination validation rejects missing required fields, unsupported extra
fields, wrong currency, wrong-user or unknown targets, contradictory cash
direction/status, duplicate facts, and multiple surviving targets/totals. A
rejected candidate becomes an explicit conservative diagnostic; it never
becomes a zero-valued or partially trusted fact.

### Conservative Outcomes

Use stable diagnostics to distinguish at least:

- an unavailable or unresolved credit, which adds no cash;
- an unresolved target, which amends no event or series;
- an unbounded required debit, which blocks downstream certification;
- a safely ignored non-cash, settled-history, failed, or cancelled outcome;
- an unsupported or ambiguous carrier/template; and
- malformed, empty, or provider-failed candidate extraction.

An ignored or unresolved carrier is a first-class result, not an empty-success
shortcut. The exact class and reason-code names may follow local style, but the
distinctions and blocking behavior are required.

## Deterministic Evidence Rules

### Messages

1. Normalize only formatting and stable template variation; extract identifiers,
   amounts, currencies, dates, and durations from the actual row. Never reuse
   another user's values when reusing a template classification.
2. Reproduce the 17 sample-message decisions in the evidence decision pack,
   including secondary and explicitly unavailable facts.
3. Classify the remaining 198 messages by the finite normalized scenario
   families catalogued in
   [`initial-analysis/03-evidence-catalog.md`](initial-analysis/03-evidence-catalog.md).
   Bilingual/paraphrased templates share a rule only after their actual fields
   validate.
4. A populated compatible `related_event_id` is the exact target. Otherwise,
   construct same-user candidates using fact type, direction/cash effect,
   category/event type, currency, temporal compatibility, and cadence. Accept
   only one compatible series.
5. Derive duration only from explicit language: next/affected cycle is
   next-only; a dated new monthly amount is recurring from that boundary;
   ended stops recurrence; resume restarts it; a settled prize, refund, or
   adjustment is one-time; and a date replacement suppresses only the stated
   superseded occurrence.
6. Amend forecast occurrences only. Never rewrite settled history or the
   supplied opening balance.
7. For unresolved credits, add no cash; when competing grounded credit values
   survive, retain the lower amount and later availability. For an unresolved
   required debit, invent no amount and block downstream certification.
8. Treat every embedded request or instruction as inert carrier data.

Preserve the pack's explicit edge cases: `message_05` does not move all future
salary dates, `message_07` does not prove gig work ended, `message_10` resolves
salary but leaves childcare as an unbounded debit, and `message_13` does not
create a missing transfer pair.

### Images

1. Validate image, request, event, user, blank source amount, currency,
   direction, status, and date context before accepting a cached reviewed fact.
2. Materialize the 15 accepted `event_amount` facts exactly as selected in the
   evidence decision pack, including their chosen labels and exact decimals.
3. Preserve `image_04` as unresolved. Its INR 2,854 item bill is not a final
   charge and must not enter amount-dependent forecasting.
4. Apply `FIN-015` selection semantics: net deposited pay for salary; applicable
   balance/payable/due for an obligation; final paid/received total for settled
   receipts; and complete total/balance due for pending invoices.
5. Never use subtotal, tax alone, cash tendered, change, prior balance, amount
   already paid, or a cropped lower bound as a final amount.
6. If complete context-compatible totals conflict, retain candidates and choose
   the financially safer amount: higher debit or lower credit. Otherwise fail
   closed.

`image_04` is linked to a settled historical debit before `request_19`; preserve
its extraction failure without subtracting it again or automatically blocking
that request. Any unresolved pending/scheduled debit remains blocking until its
amount is grounded.

### Provider Boundary

The WP-02 production path is offline and deterministic. Do not add a real
provider, prompt, adapter, retry, cache, credential, or network call. Candidate
schema tests may use the existing `FakeModelProvider` only to prove that empty,
malformed, or provider-error output cannot become a fact; these tests do not
authorize a production model path. WP-03 owns the later evidence-strategy
decision and may retain the zero-call path.

## Required Work

1. Add the immutable resolution/diagnostic types and the single case-level
   resolver in `evidence.py`.
2. Implement fact-type field-combination, provenance, link, currency, date,
   direction/status, target, and duplicate validation.
3. Implement normalized deterministic message classification for all current
   templates and exact/unique-series targeting with the `FIN-007` duration
   rules.
4. Encode the 16 reviewed image outcomes as validated extracted-fact data and
   apply the `FIN-015` context rules, preserving `image_04` as unresolved.
5. Emit explicit, redacted diagnostics for ignored, unavailable, ambiguous,
   malformed, empty, unsupported, and blocking-debit cases.
6. Add focused fixtures and tests without copying sample affordability outputs
   or introducing model/network dependencies.
7. Update the project map and the nearest evidence diagnostic only when the new
   module and focused recovery command exist.

## Acceptance Criteria

- **AC-01 — Complete carrier disposition:** all 215 current messages and all 16
  current images resolve in deterministic source order to validated facts or an
  explicit conservative diagnostic; no carrier silently disappears or becomes
  zero.
- **AC-02 — Sample-message oracle:** the 17 sample messages match the accepted
  fact types, grounded fields, targets, durations, ignored components, and
  unresolved states in the evidence decision pack exactly.
- **AC-03 — Image oracle:** 15 images produce the selected context-appropriate
  exact amount and label; `image_04` remains unavailable to amount-dependent
  forecasting and is not treated as a new current debit.
- **AC-04 — Conservative targeting:** exact links win; unlinked amendments
  affect only one uniquely compatible same-user series; ambiguous targets amend
  nothing; replacements never leave both old and new occurrences active.
- **AC-05 — Fail-closed validation:** malformed/empty candidates, missing or
  extra fields, wrong currency/direction/user, unknown IDs, duplicate facts,
  multiple totals, and provider errors cannot yield an accepted fact.
- **AC-06 — Trust boundary:** embedded instructions cannot select policy,
  affordability, payment methods, side effects, files, or provider operations;
  diagnostics and logs expose no raw carrier content.
- **AC-07 — Boundary preservation:** the module performs no FX conversion,
  recurrence projection, affordability arithmetic, plan selection, output
  writing, or live provider access.

### Finite-Risk Coverage Contract

| Invariant | Material dimensions/cases | Decisive oracle/boundary | Implementation evidence | Independent review probe | Gate owner |
|---|---|---|---|---|---|
| Every carrier has one explicit disposition | 215 messages: 17 sample + 198 evaluation; 16 images: 15 accepted + `image_04` unresolved | `resolve_case_evidence` aggregate coverage has no missing/duplicate carrier IDs | Focused full-corpus coverage test plus exact sample/image fixtures | Independently compare carrier-ID sets and the 17/16 accepted decision tables | Implementer targeted; fresh reviewer aggregate |
| Targeting and duration never broaden evidence | exact event, unique series, ambiguous series; next-only, recurring, stop, resume, replacement, one-time, non-cash | Resolved facts name one valid target/duration or return a conservative diagnostic | Parameterized `FIN-007` positive and ambiguity tests | Mutate a second compatible series and confirm resolution fails closed | Implementer targeted; fresh reviewer adversarial |
| Image amounts are context appropriate | salary credit, settled debit, pending/scheduled debit, conflicting totals, cropped total | Exact accepted amount/label or unresolved result at the image/event boundary | Sixteen golden decisions plus multiple-total/wrong-currency fixtures | Recheck `image_04`, `image_05`, `image_07`, and `image_14` dispositions | Implementer targeted; fresh reviewer spot check |
| Untrusted extraction cannot affect policy | valid, malformed, empty, unsupported, unknown ID, wrong user/currency/direction, provider error, embedded instruction | Only validated facts leave the boundary; failures are redacted and conservative | Negative schema/grounding fixtures and fake-provider failures | Inject policy-like text and malformed candidate fields; inspect outputs/logs | Implementer targeted; fresh reviewer security probe |

## Test Plan And Verification

Create `tests.test_evidence` with small explicit fixtures and full-corpus
coverage derived from repository joins. Tests must not copy solved sample output
columns or call a live model.

Required evidence includes:

- exact positive fixtures for the 17 sample-message and 16 image decisions;
- corpus coverage and deterministic ordering for all 231 carriers;
- bilingual/paraphrased template cases populated with row-local values;
- exact-link, unique-series, multi-series ambiguity, wrong-user, unknown-ID,
  replacement, next-only, recurring, stop, resume, one-time, and non-cash cases;
- malformed/empty output, missing/extra fields, invalid decimal/date/enum,
  wrong currency/direction/status, duplicate fact, multiple-total, embedded
  instruction, and provider-error cases; and
- assertions that unresolved credit adds no fact, unbounded debit blocks, and
  safe diagnostics contain IDs/reason codes but no raw carrier text.

Run verification in this order:

1. `python3 -m unittest tests.test_evidence`
2. `python3 -m unittest tests.test_repository tests.test_ai_boundary`
3. `python3 -m compileall -q code tests`
4. `python3 -m unittest discover -s tests -p 'test_*.py'`
5. `git diff --check`

The implementation owner runs steps 1–3. The fresh independent acceptance
reviewer reruns step 1, performs the finite-risk probes, and owns steps 4–5 on
the final bytes.

## Stops And Handoff

- Stop before implementation unless WP-01 review is accepted and message
  carrier content is available through the approved repository boundary.
- Stop on dataset fingerprint/count drift, a missing carrier, or a mismatch
  with the 17-message or 16-image decision tables.
- Stop rather than invent a target, amount, currency, date, duration, approval,
  settlement, or debit value.
- Stop before adding a real provider, dependency, network call, prompt/cache
  architecture, a second dataset loader, or changes to `domain.py` or
  `repository.py`; route those to the owning review/task.
- Preserve all pre-existing WP-01 and review work. Treat the metadata budget as
  a checkpoint; if full-corpus classification cannot fit the timebox, preserve
  the fail-closed resolver and split remaining deterministic template coverage
  without weakening AC-01.
- Next action: after WP-01 receives `ACCEPT`, run a standalone guided preflight
  to confirm carrier content/API availability and ownership, then implement
  this brief.
- Required follow-on: immediately after implementation or correction, hand the
  completed bytes to a fresh independent acceptance reviewer.
