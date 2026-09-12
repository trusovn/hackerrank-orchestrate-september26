# WP-03 — Evidence Strategy Gate

Status: **READY — DEPENDENCY GATED; WP-02 is still in implementation/review**
Authority: [`master-plan.md`](master-plan.md), WP-03
Depends on: WP-02 (**do not implement against its in-progress interface**)
Readiness route: standalone guided preflight — confirm the final WP-02 evidence
API, diagnostics, oracle fixtures, and independent `ACCEPT` verdict

```yaml
agent_tier: standard
reasoning: medium
review: immediate
budget: 14 tool calls / 35 minutes / medium context
```

## Outcome

After WP-02 is accepted, implement a deterministic, offline evidence-strategy
assessment that measures the accepted resolver against its independent evidence
oracle and records one reproducible decision: retain the zero-call offline path,
or identify the exact carrier IDs that justify a separately authorized provider
trial. The assessment itself never calls a live model and never changes a
financial fact.

This task has no direct recommendation effect. It prevents optional model work
from delaying or weakening the deterministic path and supplies strategy and
zero-call usage metadata to later evaluation and release work.

## Direction Trace

- Direction contribution: choose the cheapest reliable carrier-to-fact path
  while keeping raw model output outside financial logic.
- User-observable effect: no direct effect; enables the same validated evidence
  facts to feed later lifecycle and forecast work with a measured offline or
  provider-trial decision.
- Why now: [`master-plan.md`](master-plan.md) places this gate after WP-02 and
  permits deferral until after WP-08 when offline evidence is sufficient.
- Direction decisions used: [`../AGENTS.md`](../AGENTS.md),
  [`../problem_statement.md`](../problem_statement.md),
  [`ai-foundation.md`](ai-foundation.md),
  [`initial-analysis/03-evidence-catalog.md`](initial-analysis/03-evidence-catalog.md),
  [`initial-analysis/05-todo-and-analysis-runbook.md`](initial-analysis/05-todo-and-analysis-runbook.md),
  [`initial-analysis/07-evidence-decision-pack.md`](initial-analysis/07-evidence-decision-pack.md),
  and [`master-plan.md`](master-plan.md), sections 2–8 and WP-03.
- New direction decisions required: None

A concrete provider trial is outside this ready task and requires the owner
decisions listed under Stops And Handoff.

## Authority And Scope

| Item | Contract |
|---|---|
| Product authority | [`../problem_statement.md`](../problem_statement.md) and [`../AGENTS.md`](../AGENTS.md) |
| Implementation authority | [`master-plan.md`](master-plan.md), WP-03, and the accepted final WP-02 brief/bytes/review |
| Allowed implementation changes | `code/evaluation/evidence_strategy.py` |
| Allowed evidence changes | `tests/test_evidence_strategy.py`, generated `code/evaluation/evidence_strategy.json`, [`project-map.md`](project-map.md), and the nearest existing diagnostic only if a real recovery command is added |
| Read-only upstream context | accepted `code/buy_or_wait/evidence.py`, `code/buy_or_wait/ai_boundary.py`, `code/buy_or_wait/domain.py`, `code/buy_or_wait/repository.py`, their focused tests, and accepted WP-02 review evidence |
| Input boundary | Participant-facing cases from `dataset/` and independent expected evidence fixtures accepted with WP-02 |
| Out of scope | Editing WP-02 behavior or oracle expectations; lifecycle/FX, forecast, planning, output, or explanation behavior; provider/model selection; live calls; credentials; prompt tuning; sample-answer fitting; sending a full ledger to a model |
| External requirements | None. The implemented gate is standard-library-only, offline, and deterministic. |

## Dependency And Timing Gate

Do not begin implementation until all of the following are true:

1. WP-02's final independent review says `ACCEPT`.
2. `python3 -m unittest tests.test_evidence tests.test_ai_boundary` passes on
   those accepted bytes.
3. The accepted resolver exposes stable carrier source IDs, validated facts,
   diagnostic reason codes, and the conservative blocking indication promised
   by [`wp-02-plan.md`](wp-02-plan.md).
4. A data-only independent WP-02 oracle fixture identifies the expected 17
   sample-message and 16 image decisions without deriving expectations from
   production resolver output. If WP-02 instead embeds the only copy inside
   test code, route a WP-02 correction to expose the same accepted fixture as
   data; do not import a test module or duplicate the oracle in WP-03.
5. No in-progress WP-02 owner is editing `evidence.py`, `test_evidence.py`, or
   the evidence fixtures this task must read.

If any item fails, stop and route the mismatch back to WP-02. Do not add a
second evidence resolver, reopen CSVs outside `DatasetRepository`, copy
in-progress types, or relax an oracle to make this gate executable.

WP-03 is optional on the critical path. If WP-04 through WP-08 can proceed from
the accepted offline WP-02 boundary, they take priority over this gate. Starting
WP-03 must not delay the first complete deterministic output row.

## Architecture

### Evaluation-only boundary

Add `code/evaluation/evidence_strategy.py`. It may import the accepted
repository and evidence APIs but must not be imported by product modules. Keep
the module flat and standard-library-only.

Expose these semantic entry points; exact private helper names may follow local
style:

```python
assess_evidence_strategy(cases, oracle) -> EvidenceStrategyReport
write_strategy_report(report, output_path: Path) -> None
main(argv: Sequence[str] | None = None) -> int
```

`assess_evidence_strategy` is pure with respect to files, network, environment,
and providers. `write_strategy_report` writes UTF-8 JSON through a sibling
temporary file and atomic replacement. `main` loads both evaluation and sample
cases through `DatasetRepository`, invokes the accepted case resolver once per
case, assesses the results, and writes the report.

The CLI contract is:

```text
python3 code/evaluation/evidence_strategy.py \
  --dataset dataset \
  --output code/evaluation/evidence_strategy.json
```

Defaults may be those exact repository-relative paths. Explicit arguments are
required in tests so fixtures never read or overwrite the real dataset/report.

### Report contract

`EvidenceStrategyReport` is an immutable evaluation-owned value. The JSON form
uses sorted keys, two-space indentation, and one trailing newline. It contains
only these categories of data:

- schema version and dataset fingerprint;
- selected strategy: `offline` or `provider_trial_required`;
- one-sentence decision reason and the rejected alternative;
- total, message, and image carrier counts;
- exact-oracle match/mismatch counts;
- accepted-fact, intentional-conservative, model-eligible-unresolved,
  blocking-unbounded-debit, and incorrect-optimistic counts;
- source IDs and stable reason codes for mismatches or unresolved outcomes;
- model usage totals: calls, input tokens, output tokens, and estimated cost,
  all numeric zero for this offline assessment; and
- the fixed assessment schema/config identifier `wp-03-v1` and the accepted
  WP-02 resolver contract identifier needed to reproduce the assessment.

Do not include raw message text, request text, image bytes, extracted excerpts,
model responses, credentials, absolute paths, or solved affordability outputs.
The report is evidence-strategy metadata, not the final-run usage report owned
by WP-10.

### One disposition per carrier

Build an index by `(source_type, source_id)` while traversing evaluation cases
in source order followed by sample cases in source order. Reject duplicate or
missing carrier IDs. Each of the current 215 messages and 16 images must map to
exactly one assessment row. That row preserves all accepted WP-02 facts and
diagnostics for the carrier, then assigns one strategy classification:

- one or more validated facts;
- an intentional conservative diagnostic; or
- a model-eligible unresolved diagnostic.

Never infer strategy from fact count alone. A carrier may correctly yield no
numeric fact, may yield more than one validated fact, or may yield a grounded
fact plus an unresolved secondary diagnostic.

### Decision rules

Apply these rules in order:

1. **Invalid gate:** raise an assessment error and write no replacement report
   for a carrier-set mismatch, duplicate/missing disposition, accepted-oracle
   mismatch, incorrect optimistic fact, malformed accepted fact, or red WP-02
   test. These are WP-02 defects, not reasons to add a model.
2. **Intentional conservative:** do not request a provider for information the
   carrier does not contain, a target that cannot be uniquely grounded, or a
   fact that policy intentionally excludes. This includes the unresolved
   unapproved commission in `message_08`, the unresolved childcare amount in
   `message_10`, the missing transfer pair in `message_13`, the unsettled prize
   in `message_16`, and cropped non-final subtotal in `image_04`.
3. **Offline:** select `offline` only when the full carrier set has explicit
   accepted dispositions, the 17-message/16-image oracle matches exactly,
   incorrect-optimistic count is zero, and model-eligible-unresolved count is
   zero. Reject the provider alternative because it has no measured validated
   coverage to add. Record zero calls/tokens/cost.
4. **Provider trial required:** select `provider_trial_required` only when all
   WP-02 correctness checks pass and at least one carrier contains a grounded,
   policy-permitted fact that the deterministic resolver cannot extract or
   validate. Record only its source ID and reason code. Do not implement or call
   a provider in this task.

An unresolved required debit may still block downstream certification without
being model-eligible. “Conservative” is not synonymous with “needs AI.”

### Conditional provider follow-on

If and only if the report selects `provider_trial_required`, stop this task and
create a separate WP-03B brief after the owner supplies provider authority. That
brief must preserve these already-approved constraints:

- one carrier plus minimal validated linkage context per call, never a full
  ledger or affordability question;
- one carrier-family-specific operation behind `ModelProvider` and one strict
  feature-owned response validator;
- deterministic fallback to the same WP-02 conservative disposition on
  provider absence, timeout, error, empty output, malformed output, or failed
  grounding;
- no automatic retry by default; any later transient retry is bounded and
  replaces rather than appends a candidate;
- accepted-result caching keyed by a SHA-256 digest of carrier content plus
  operation, schema, extractor, model, and config versions; cache neither raw
  carrier content nor raw provider output;
- call/token/latency/retry/validation/cost telemetry without secrets or raw
  content; and
- retention only after a bounded trial increases independently validated fact
  coverage and produces zero incorrect optimistic facts. A tie or tradeoff
  keeps the offline path.

These constraints do not authorize a specific provider, model, endpoint,
dependency, credential, price, live call, or cache location.

## Required Work

1. Perform the dependency gate against accepted WP-02 bytes and record the
   exact review verdict and commands used.
2. Add fail-first strategy tests using small fake `RequestCase`/resolution
   fixtures and the independent accepted WP-02 oracle.
3. Implement the evaluation-only assessor, strict carrier accounting, ordered
   decision rules, redacted report type, and atomic JSON writer.
4. Add the CLI that loads sample plus evaluation cases through the existing
   repository and resolves each case through the accepted WP-02 public API.
5. Generate `code/evaluation/evidence_strategy.json` from the current dataset
   and inspect it for raw/sensitive content.
6. Update [`project-map.md`](project-map.md) with the real evaluator command and
   output only after both exist and pass.
7. If the result is `provider_trial_required`, stop at the metadata and hand
   the exact source IDs/reason codes to the owner; do not begin WP-03B.

## Acceptance Criteria

- **AC-01 — Dependency integrity:** assessment runs only against independently
  accepted WP-02 bytes and does not modify or duplicate the evidence resolver,
  evidence oracle, repository, or domain contract.
- **AC-02 — Exact carrier accounting:** all current 215 messages and 16 images
  receive exactly one source-ID-addressable assessment row preserving their
  facts and diagnostics; a missing, extra, or duplicate carrier fails without
  replacing the prior report.
- **AC-03 — Independent oracle:** the accepted 17 sample-message and 16 image
  expected decisions match exactly; expected values are never generated from
  the production resolver under test.
- **AC-04 — Correct strategy:** known intentional/unrecoverable conservative
  outcomes do not trigger AI; only grounded extractable-but-unresolved carrier
  facts yield `provider_trial_required`; any incorrect optimistic fact fails
  the gate instead of being averaged into a coverage score.
- **AC-05 — Offline safety:** the assessment has no provider parameter or
  provider import, performs zero model/network calls, and reports zero
  calls/tokens/cost. Existing provider-boundary evidence uses
  `FakeModelProvider` only.
- **AC-06 — Deterministic failure:** the accepted WP-02 provider
  absence/failure fixtures preserve the per-carrier conservative outcome and
  cannot create a fact or duplicate carrier disposition; an assessment failure
  cannot partially replace metadata or create `output.csv`.
- **AC-07 — Reproducible metadata:** two assessments over identical accepted
  inputs produce byte-identical JSON; it records the selected path, rejected
  alternative, versions, counts, safe IDs/reasons, and dataset fingerprint,
  with no raw carrier content, solved output, credentials, or absolute paths.

### Finite-Risk Coverage Contract

| Invariant | Material dimensions/cases | Decisive oracle/boundary | Implementation evidence | Independent review probe | Gate owner |
|---|---|---|---|---|---|
| Strategy never hides a WP-02 defect | missing, extra, duplicate, oracle mismatch, malformed fact, incorrect optimistic fact | Assessor raises and existing report bytes remain unchanged | Fail-first unit cases plus temp-directory atomic-write assertions | Corrupt one disposition and one oracle fact independently; verify no report replacement | Implementer targeted; fresh reviewer adversarial |
| Conservative outcomes are classified by resolvability | validated fact, intentional conservative, model-eligible unresolved, unbounded but source-incomplete debit | Exact selected strategy and safe source-ID/reason list | Table-driven decision-rule tests including `message_08`, `message_10`, `message_13`, `message_16`, and `image_04` | Reclassify a source-incomplete amount as model-eligible and confirm the test rejects it | Implementer targeted; fresh reviewer spot check |
| Offline path has no hidden AI side effect | provider absent plus inherited fake-provider success/failure fixtures | Assessor has no provider dependency; zero usage totals; accepted WP-02 conservative fallback remains green | Static import check, report assertions, and accepted fake-provider failure fixture | Patch `FakeModelProvider.complete` to fail if reached, run the assessor, and confirm it is unreachable | Implementer targeted; fresh reviewer security probe |
| Metadata is complete, deterministic, and redacted | offline selection, provider-trial selection, assessment failure | Byte equality for repeated success; prior bytes preserved on failure; forbidden-content scan | Temp-file round trip and two-run byte comparison | Scan generated current-dataset report for known raw-text fragments and absolute repo path | Implementer targeted; fresh reviewer aggregate |

## Verification

Add `tests.test_evidence_strategy`; tests use temporary output paths and never
overwrite the checked-in current-dataset report.

| Evidence | Scenario and oracle | Command |
|---|---|---|
| Fail-first | New focused test fails because the evaluation assessor/CLI does not exist; preserve that failure before implementation | `python3 -m unittest tests.test_evidence_strategy` |
| Targeted | Decision table, carrier accounting, zero-call proof, atomic write, deterministic bytes, and redaction pass | `python3 -m unittest tests.test_evidence_strategy` |
| Owning suites | Accepted evidence and provider-neutral boundary remain unchanged | `python3 -m unittest tests.test_evidence tests.test_ai_boundary` |
| Current-dataset run | Generates the reproducible strategy decision from participant-facing data only | `python3 code/evaluation/evidence_strategy.py --dataset dataset --output code/evaluation/evidence_strategy.json` |
| Compile | New and owning Python modules compile | `python3 -m compileall -q code tests` |
| Broader gate | Fresh reviewer checks repository regressions and final patch hygiene | `python3 -m unittest discover -s tests -p 'test_*.py'` then `git diff --check` |

Run fail-first once, then targeted tests, owning suites, the current-dataset
command, and compile. The fresh independent reviewer reruns targeted and owning
suites, performs the finite-risk probes, and owns the broader gate on the final
bytes. No live, networked, credentialed, or paid verification is authorized.

## Stops And Handoff

- Stop until WP-02 has an independent `ACCEPT`; its current in-process design
  or partial bytes are not an implementation dependency.
- Stop on dirty overlap with WP-02-owned source, tests, or fixtures.
- Stop and route back to WP-02 for a red evidence test, unstable/missing public
  result field, carrier-set drift, oracle mismatch, duplicate/silent carrier,
  malformed fact, or incorrect optimistic fact.
- Stop rather than treating unavailable source information or ambiguous
  targeting as something a model may guess.
- If `provider_trial_required` is selected, ask the owner to choose the exact
  provider/model, approve network and credential use, set a cost/call ceiling,
  confirm the carrier family, and approve a local cache location. Then create a
  separate bounded WP-03B brief; do not expand this task in place.
- Preserve all pre-existing user and WP-02 work. Treat the metadata budget as a
  checkpoint.
- Next action: after WP-02 is accepted, run the standalone guided preflight,
  then implement this offline assessment. If the deterministic WP-02 path
  already unblocks WP-04 through WP-08, those mandatory packages may proceed
  first.
- Required follow-on: immediately after implementation or correction, hand the
  completed bytes to a fresh independent acceptance reviewer.
