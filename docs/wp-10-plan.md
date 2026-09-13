# WP-10 — Batch Composition, Diagnostics, And Full-Dataset Run

Status: **PLANNED — WAITING FOR FRESH WP-09F ACCEPTANCE**

Authority: [`master-plan.md`](master-plan.md), WP-10; governed by
[`../AGENTS.md`](../AGENTS.md), especially Critical Output Invariants and the
Submission Contract; and [`../problem_statement.md`](../problem_statement.md),
especially Required Output, Important Behavior, Evaluation, and Token Usage and
Cost Analysis.

## Why WP-10 Is Split

The unsplit package is approximately **35 tool calls / 115 minutes / large
context**. It crosses three independently testable concerns: deterministic
batch composition, the terminal/atomic-publication boundary, and usage-report
generation plus the real full-dataset run. That exceeds the user's limits of
15 calls and 40 minutes.

Split the same total scope into three sequential parts:

1. **WP-10A:** deterministic batch result, stage failures, and reason counts —
   12 calls / 35 minutes.
2. **WP-10B:** terminal CLI composition and atomic `output.csv` publication —
   12 calls / 40 minutes.
3. **WP-10C:** reconciled usage report and final 250-request run — 11 calls /
   40 minutes.

Run the parts in order. They share `pipeline.py`, `code/main.py`, and batch
result contracts, so they must not be implemented concurrently. Each part uses
a standard agent with medium reasoning; none requires a strong model with high
reasoning.

## Direction Trace

- Direction contribution: run every evaluation request once through the same
  selected, independently validated decision pipeline and leave a complete,
  reproducible output plus truthful usage evidence.
- User-observable effect: `python3 code/main.py` either publishes one valid
  250-row root `output.csv` and the matching usage report, or exits nonzero
  without presenting a failed request batch as successful.
- Why now: WP-08 provides exact batch validation and atomic CSV replacement;
  WP-09 must first freeze the one global policy consumed by this package;
  WP-11 packages the artifacts produced here.
- Direction decisions used: `AGENTS.md` Critical Output Invariants and
  Submission Contract; `problem_statement.md` Required Output and Token Usage
  and Cost Analysis; `master-plan.md` sections 2–7, WP-10, Delivery Sequence,
  Risk Register, and Cut Rules.
- New direction decisions required: `None`

## Current-State And Dependency Gate

Planning observed this state on 2026-09-13:

- WP-08C is accepted. `OutputContext`, `validate_output_batch`, and
  `write_output_atomic` already own exact evaluation coverage, row order,
  independent row revalidation, sibling-temp cleanup, and one `os.replace`.
- `code/buy_or_wait/pipeline.py`, `tests/test_pipeline.py`,
  `code/buy_or_wait/README.md`, and `docs/project-map.md` contain user-owned,
  in-progress WP-09A work. `predict_case` is currently pure, single-case,
  offline, and deliberately owns no batch, run-ID, usage, or file behavior.
- `code/main.py` and `code/evaluation/usage_report.md` are empty placeholders.
- WP-09A is awaiting fresh independent acceptance, and WP-09B through WP-09F
  remain sequential dependencies. WP-09F is expected to expose one accepted
  `SELECTED_DECISION_POLICY` and a final `predict_case` contract.
- The challenge deadline has passed. This plan can prove functional runtime and
  record elapsed duration, but it cannot claim that a pre-deadline delivery
  budget remains.

Do not begin WP-10A until WP-09F has a fresh independent `ACCEPT`, the selected
policy and final trace API are handed off, and no other agent owns
`pipeline.py` or `tests/test_pipeline.py`. Preserve accepted WP-09 semantics
when names differ from the illustrative signatures below. Do not adapt WP-10
to intermediate WP-09 bytes.

At each part's self-preflight, inspect only the named files and scoped Git
status. Stop for overlapping user work. Do not clean, revert, stage, or rewrite
the current WP-09 changes.

## Package Authority And Scope

| Item | Contract |
|---|---|
| Repository root | `/Users/mtrusov/work/repos/hkr-orc-0926` |
| Dependencies | Accepted WP-08C and fresh independent acceptance of WP-09A through WP-09F; A precedes B, B precedes C |
| Product composition owner | `code/buy_or_wait/pipeline.py` |
| Terminal owner | `code/main.py` |
| Usage-report owner | `code/evaluation/usage.py` and `code/evaluation/usage_report.md`; add `code/evaluation/__init__.py` only if normal package import requires it |
| Primary tests | `tests/test_pipeline.py`, `tests/test_main.py`, and `tests/test_usage.py` |
| Navigation/diagnostics | `code/buy_or_wait/README.md`, `docs/project-map.md`, and the existing `EVAL`/`OUTPUT-CONTRACT` rows in `docs/diagnostics.md` when their deferred signals become real |
| Read-only context | Accepted repository, pipeline, output, AI-boundary, and WP-09 evaluation APIs and their nearest tests; the authorities above |
| Out of scope | New financial policy, sample calibration, provider integration, live network calls, pricing lookup, request/user-specific exceptions, duplicated row validation/writer logic, ZIP construction/inspection, transcript preparation, and submission (WP-11) |
| Assumptions / unresolved decisions | The selected WP-09 policy is expected to remain offline. If accepted WP-09 retains model calls, its handoff must expose safe per-call metadata and an approved cost basis; otherwise WP-10C stops rather than reporting false zero usage or inventing prices. |

## Proposed Architecture And Data Flow

Keep the existing single-case seam pure and make the batch and side-effect
boundaries explicit:

```text
code/main.py
  parse --dataset/--output/--usage-report
  create exactly one run_id
  DatasetRepository.from_directory(dataset)
  materialize EVALUATION RequestCases in supplied order
                    |
                    v
  pipeline.predict_batch(cases, SELECTED_DECISION_POLICY, run_id)       (10A)
    one shared staged case executor
      evidence -> normalization -> forecast -> planning -> output build/validate
    collect every PredictionTrace, OutputRow, OutputContext
    aggregate safe (stage, reason_code) counts and retained call metadata
    return only after the whole in-memory batch succeeds
                    |
                    v
  write_output_atomic(output, rows, contexts)                           (10B)
                    |
                    v
  hash the published output bytes
  summarize/render/atomically replace evaluation/usage_report.md        (10C)
                    |
                    v
  emit one safe run summary and exit 0
```

No batch layer may recreate repository joining, financial arithmetic,
candidate selection, row validation, or CSV serialization. It composes the
accepted public seams.

### Batch result and stage failure contract

Exact public names may follow accepted local style, but preserve these
semantics:

```python
@dataclass(frozen=True)
class DiagnosticCount:
    stage: str
    reason_code: str
    count: int

@dataclass(frozen=True)
class BatchPrediction:
    run_id: str
    policy_id: str
    traces: tuple[PredictionTrace, ...]
    rows: tuple[OutputRow, ...]
    contexts: tuple[OutputContext, ...]
    reason_counts: tuple[DiagnosticCount, ...]
    model_calls: tuple[ModelCallMetadata, ...]

class BatchPredictionError(RuntimeError):
    run_id: str
    request_id: str
    stage: str
    reason_code: str
    source_ids: tuple[str, ...]

def predict_batch(
    cases: Iterable[RequestCase],
    *,
    run_id: str,
    policy: DecisionPolicy = SELECTED_DECISION_POLICY,
) -> BatchPrediction: ...
```

`predict_batch` must consume the iterable exactly once, in order. For each
case, invoke the same implementation used by `predict_case`; do not maintain a
second financial path. A small private staged executor may be shared so the
batch caller knows the failing stage while the accepted public `predict_case`
continues to expose its established exception behavior.

The stable stage vocabulary is exactly:

```text
repository,evidence,normalization,forecast,planning,output_build,
output_validate,batch_validate,output_write,usage_report
```

Within the batch, only the six stages from `evidence` through
`output_validate` execute. `code/main.py` assigns the remaining stage labels at
their real boundaries. A known exception's non-empty `reason_code` is retained;
otherwise use `unclassified_<stage>_failure`. Never use `str(exception)` as a
diagnostic because it can contain raw data or paths. Retain `source_ids` only
from established source-safe exception contracts.

Aggregate nonzero reason codes from these accepted trace fields:

- `EvidenceResolution.diagnostics` under `evidence`;
- `EventNormalization.decisions` under `normalization`;
- `BaselineForecast.diagnostics` under `forecast`; and
- `PlanningDecision.diagnostics` under `planning`.

Sort counts by the stable stage order above, then `reason_code`. Count records
contain no raw request/message/image text, descriptions, prompts, model output,
credentials, environment values, or full checkpoint ledgers.

### CLI and publication contract

`code/main.py` remains a thin, standard-library-only adapter. Its defaults are
repository-relative `dataset/`, root `output.csv`, and
`code/evaluation/usage_report.md`; explicit path flags exist so tests use
temporary destinations. Resolve defaults from the repository containing
`code/main.py`, not from the caller's current directory.

Create one non-empty opaque `run_id` per invocation and pass the same value to
all diagnostics, the batch result, the usage report, and the final summary.
Expose a small callable `run(...)` that accepts an injected run ID for tests;
`main(argv)` owns argument parsing, one production run-ID creation, safe
error rendering, and the final exit code.

The CLI must materialize all evaluation cases and complete all predictions
before calling `write_output_atomic` exactly once. Any repository or prediction
failure leaves an existing destination byte-for-byte unchanged. Writer failure
inherits WP-08C's preserved-destination and temp-cleanup behavior.

Emit one deterministic JSON object to stdout on success. On failure, emit one
JSON object to stderr and return nonzero. The failure object contains only
`run_id`, `request_id` when known, stable `stage`, stable `reason_code`, and
safe `source_ids`; no traceback or raw exception text. Ordinary library
functions raise typed exceptions and do not call `sys.exit`.

### Usage and final-run contract

`code/evaluation/usage.py` owns immutable usage totals, validation, deterministic
Markdown rendering, and sibling-temp atomic replacement. It consumes retained
`ModelCallMetadata` from the accepted batch result; it never invokes a model,
reads raw prompts/responses, or fetches live prices.

The report is a single snapshot, not an append-only history. Each successful
run replaces it once so retries do not duplicate request or call records. It
must contain:

- run ID, selected canonical policy ID, request count, output SHA-256, and
  measured elapsed duration;
- provider/model rows with calls, input tokens, output tokens, estimated total
  cost, and their exact sum;
- overall calls/tokens/cost and average tokens/cost per all evaluation requests
  (denominator 250 for the final dataset, including requests with no calls);
- the deterministic per-stage reason-count table; and
- an explicit statement that no model was used when the metadata tuple is
  empty, with provider/model shown as `none` and every usage/cost total `0`.

Use `Decimal` for cost arithmetic and a stable documented decimal rendering.
If model calls exist, group by the exact `(provider, model)` pair and reconcile
every per-model sum to the overall total. Estimated cost must come from the
accepted provider/config handoff or retained call evidence. Missing provider,
model, token count, or approved cost basis is a hard `usage_report` failure;
do not query pricing, guess, or silently substitute zero.

After `write_output_atomic` succeeds, hash the bytes actually present at the
output path, build the report from that hash and the same `BatchPrediction`,
and atomically replace the usage report. There is no portable two-file atomic
commit: if report publication fails after output replacement, return nonzero,
preserve the previous report, and state `stage=usage_report`. Such an invocation
is not the final successful run; rerun WP-10C before WP-11.

The final successful `python3 code/main.py` invocation must be offline unless a
provider path was separately accepted and authorized. It writes root
`output.csv` and the actual `code/evaluation/usage_report.md`; WP-11 may inspect
and package those bytes but must not manufacture their totals.

---

# WP-10A — Add Deterministic Batch Results And Safe Stage Diagnostics

Status: **READY AFTER FRESH WP-09F ACCEPTANCE**

```yaml
agent_tier: standard
reasoning: medium
review: immediate
budget: 12 tool calls / 35 minutes / medium context
```

## Readiness Route

`implementer self-preflight` — confirm fresh WP-09F acceptance, final
`SELECTED_DECISION_POLICY`/`PredictionTrace` APIs, and exclusive ownership of
the in-progress pipeline files.

## Outcome

Produce one immutable, ordered, all-or-nothing batch result with safe stage
failures, deterministic reason counts, and retained provider metadata without
changing single-case financial behavior.

## Required Work

1. Add fail-first batch tests using synthetic evaluation cases and injected
   stage failures; keep all tests offline.
2. Factor only the minimum private staged executor needed for `predict_case`
   and `predict_batch` to share one financial path while batch failures retain
   the exact failing stage.
3. Add the batch result, diagnostic count, typed error, and `predict_batch`
   contract described above. Reject an empty/invalid run ID and invalid case
   records before returning a result.
4. Construct each `OutputContext` from the exact case, baseline, and decision
   that produced its row. Call `validate_output_batch` once after collection;
   return no result if it fails.
5. Aggregate only source-safe reason codes in deterministic order. Carry the
   accepted model-call metadata tuple; for the accepted offline path it is
   exactly empty.
6. Preserve `predict_case` purity, default selected policy, trace content,
   exception compatibility, and all accepted WP-09 evaluation behavior.
7. Update package navigation and repository navigation for the new public batch
   seam. Update `docs/diagnostics.md` only when the implementation makes a
   concrete recovery signal available.

## Acceptance Criteria

- **A-AC-01:** N ordered evaluation cases yield N traces, rows, and contexts in
  identical request order; every row/context pair passes the accepted batch
  validator and uses one policy ID and one run ID.
- **A-AC-02:** the iterable is consumed once and each case is predicted once;
  an empty or malformed batch cannot return a misleading successful result.
- **A-AC-03:** a failure injected at each case stage identifies the exact
  request, stable stage, and safe reason code; later cases are not processed
  and no partial `BatchPrediction` is observable.
- **A-AC-04:** reason counts are exact, sorted, and stable under repeated runs;
  duplicate occurrences increment counts, and absent reasons create no rows.
- **A-AC-05:** `predict_case` and all accepted WP-09 policy/evaluation tests
  remain unchanged in behavior; batch code performs no file, clock, network,
  environment, or exit operation.
- **A-AC-06:** offline execution carries an empty model-call tuple. If WP-09F
  retained a provider, metadata is carried only through its accepted safe
  interface; absence of that interface stops implementation.

## WP-10A Verification

| Evidence | Scenario and oracle | Command |
|---|---|---|
| Fail-first/targeted | ordered success, one-shot iterable, every stage failure, count ordering, no partial result | `python3 -m unittest tests.test_pipeline.BatchPipelineTests` |
| Compatibility | accepted single-case API/default/error behavior | `python3 -m unittest tests.test_pipeline.SingleCasePipelineTests` |
| Owning regressions | all pipeline behavior | `python3 -m unittest tests.test_pipeline` |
| Upstream/downstream seam | accepted row and batch validation remain authoritative | `python3 -m unittest tests.test_output.OutputBatchAndAtomicWriterTests` |
| Broader gate | final A bytes; fresh reviewer owns it | `python3 -m unittest tests.test_pipeline tests.test_output tests.test_evaluation` then `python3 -m unittest tests.test_agent_foundation_contract` then `git diff --check` |

## WP-10A Stops And Handoff

- Stop if WP-09F is not freshly accepted, its selected policy/trace contract is
  still changing, or another agent owns the same files.
- Stop rather than duplicate financial stages or weaken `predict_case` to make
  failure labeling convenient.
- Stop if provider metadata would require a new model integration or unsafe raw
  content. Route that gap to the accepted provider owner.
- Next: guided A implementation.
- Required follow-on: immediately after implementation or correction, hand the
  completed bytes to a fresh independent acceptance reviewer. Accepted A bytes
  unblock B.

---

# WP-10B — Wire The Terminal CLI And Atomic Output Publication

Status: **READY AFTER FRESH WP-10A ACCEPTANCE**

```yaml
agent_tier: standard
reasoning: medium
review: immediate
budget: 12 tool calls / 40 minutes / medium context
```

## Readiness Route

`implementer self-preflight` — confirm accepted A batch contracts, accepted
WP-08C writer signatures, empty or cleanly handed-off `code/main.py`, and
temporary-path test capability.

## Outcome

Make `python3 code/main.py` load evaluation cases, execute one batch, and
publish root `output.csv` exactly once with safe deterministic success/failure
signals.

## Required Work

1. Add fail-first CLI/composition tests in `tests/test_main.py` using temporary
   dataset/output paths and injected run IDs; do not touch root `output.csv` in
   ordinary tests.
2. Implement thin `run(...)` and `main(argv)` entry points with repository-root
   defaults plus explicit `--dataset` and `--output` flags.
3. Generate one run ID in `main`, load `DatasetRepository`, materialize only
   `RequestScope.EVALUATION` in request-file order, and call `predict_batch`
   with `SELECTED_DECISION_POLICY`.
4. Call the accepted `write_output_atomic` once and only after the full batch
   and final batch validation succeed. Do not write rows incrementally or
   reproduce CSV serialization.
5. Map repository, batch-validation, and writer failures to the stable stage
   vocabulary and safe JSON error envelope. Preserve the old output on every
   failure before or within the accepted writer boundary.
6. Emit one safe JSON success summary containing run ID, policy ID, request
   count, nonzero reason counts, output path expressed without user-home
   disclosure, and model-call count. Do not print traces or raw records.
7. Make the same command callable from a working directory outside the repo by
   resolving defaults relative to the script/repository location.
8. Update the root quick-start/project-map command and the concrete
   `OUTPUT-CONTRACT` diagnostic signal only as required by the implemented
   public behavior.

## Acceptance Criteria

- **B-AC-01:** default execution selects all and only evaluation cases in
  supplied order, uses the frozen policy, creates one run ID, and invokes the
  batch and writer once.
- **B-AC-02:** a successful temporary-boundary run produces exact required
  columns and one unique row for every supplied evaluation request in source
  order; no sample row appears.
- **B-AC-03:** repository, each request stage, batch-validation, and output-write
  failures return nonzero with one source-safe JSON diagnostic and no traceback
  or raw carrier data.
- **B-AC-04:** any pre-publication failure preserves an existing output
  byte-for-byte. Writer failure preserves it and removes the sibling temp under
  the accepted WP-08C contract.
- **B-AC-05:** two successful runs with identical data and policy produce
  byte-identical `output.csv` bytes and never append or duplicate rows.
- **B-AC-06:** explicit paths affect only their named destinations; dataset
  inputs and `dataset/output.csv` remain unchanged.

## WP-10B Verification

| Evidence | Scenario and oracle | Command |
|---|---|---|
| Fail-first/targeted | parsing/defaults, one run ID, one batch/write, safe failures, preserved sentinel | `python3 -m unittest tests.test_main.CliCompositionTests` |
| Real temporary boundary | repository load through parsed CSV output; exact IDs/order and repeat-byte equality | `python3 -m unittest tests.test_main.BatchPublicationTests` |
| Owning regressions | CLI plus batch composition | `python3 -m unittest tests.test_main tests.test_pipeline` |
| Writer regressions | one validated atomic replacement remains authoritative | `python3 -m unittest tests.test_output.OutputBatchAndAtomicWriterTests` |
| Broader gate | final B bytes; fresh reviewer owns it | `python3 -m unittest tests.test_repository tests.test_pipeline tests.test_output tests.test_main` then `python3 -m compileall -q code tests` then `git diff --check` |

## WP-10B Stops And Handoff

- Stop for any overlap on `code/main.py`, `pipeline.py`, or their tests.
- Stop rather than add a second CSV writer, bypass `validate_output_batch`, or
  catch and expose raw exception text.
- Do not write the root artifact during unit tests or run the live/default full
  dataset command in B; C owns the final run.
- Next: guided B implementation.
- Required follow-on: immediately after implementation or correction, hand the
  completed bytes to a fresh independent acceptance reviewer. Accepted B bytes
  unblock C.

---

# WP-10C — Reconcile Usage And Execute The Final Full-Dataset Run

Status: **READY AFTER FRESH WP-10B ACCEPTANCE**

```yaml
agent_tier: standard
reasoning: medium
review: immediate
budget: 11 tool calls / 40 minutes / medium context
```

## Readiness Route

`implementer self-preflight` — confirm accepted B CLI behavior, the final
WP-09 provider disposition/cost basis, writable root/evaluation destinations,
and that running `python3 code/main.py` is authorized to replace generated
`output.csv` and `code/evaluation/usage_report.md`.

## Outcome

Generate one validated usage snapshot tied to the published output bytes, then
complete the real evaluation run with exactly 250 ordered rows and truthful
zero-call or reconciled per-model totals.

## Required Work

1. Add fail-first usage tests for zero-call, one-model, multi-model, invalid
   metadata/cost basis, exact totals/averages, stable rendering, atomic replace,
   and preserved old report on failure.
2. Add the smallest evaluation-owned usage module described above. Use no
   third-party package and no live provider/pricing call.
3. Extend the CLI with `--usage-report`; stage the usage summary in memory,
   publish the validated output, hash its actual bytes, then atomically replace
   exactly one report snapshot.
4. Add full-boundary tests that run against the real participant dataset but
   temporary output/report paths. Assert 250 IDs exactly equal
   `requests.csv` order, every row reparses/revalidates, report request count is
   250, and report output hash matches.
5. Run the command twice against separate temporary destinations and require
   byte-identical output CSVs and one non-duplicated usage snapshot per run.
   Runtime is measured and reported, not enforced through a machine-specific
   invented threshold.
6. After targeted and owning gates pass, run `python3 code/main.py` once at the
   real boundary. If it fails, diagnose and rerun only after the owning defect
   is corrected; the last successful invocation is the final-run evidence.
7. Inspect the produced root CSV and report through automated assertions. Do
   not edit generated totals by hand.
8. Update evaluation/project navigation and the `EVAL` diagnostic with the
   real command, artifacts, failure signal, and recovery proof.

## Acceptance Criteria

- **C-AC-01:** zero-call mode explicitly reports provider/model `none`, zero
  calls/tokens/cost, zero averages, 250 requests, the selected policy, and the
  exact output SHA-256; it never implies that an unnamed model ran.
- **C-AC-02:** if accepted retained calls exist, every call belongs to exactly
  one provider/model row; per-model calls/tokens/cost sum exactly to overall
  totals, and averages use all 250 requests as the denominator.
- **C-AC-03:** missing/invalid metadata, missing approved cost basis, aggregate
  mismatch, report-write failure, or output-hash mismatch exits nonzero and
  preserves the previous report. No usage value is guessed.
- **C-AC-04:** the real successful run writes exactly 250 unique output rows in
  `dataset/requests.csv` order, with the exact eight-column header, and all
  rows pass the accepted independent batch validator.
- **C-AC-05:** repeated identical-input/config runs produce byte-identical
  financial output; each destination contains one output batch and one usage
  snapshot, never appended duplicate records.
- **C-AC-06:** the report and success summary share the one invocation run ID,
  policy ID, request count, model-call count, and output hash. Per-stage counts
  equal the accepted batch result and contain no raw sensitive content.
- **C-AC-07:** repository loading, validation, prediction, output publication,
  report generation, and measured runtime complete without unresolved fatal
  errors. A report failure after output replacement remains a non-successful
  run and must be rerun before WP-11.

## WP-10C Verification

| Evidence | Scenario and oracle | Command |
|---|---|---|
| Fail-first/targeted | zero/one/multi-model math, missing cost basis, rendering and atomic failure | `python3 -m unittest tests.test_usage.UsageReportTests` |
| CLI integration | one run ID/output hash across output, report, and summary; report failure is nonzero | `python3 -m unittest tests.test_main.UsagePublicationTests` |
| Real temporary boundary | all 250 participant evaluation requests; exact order/validation/hash and repeat output bytes | `python3 -m unittest tests.test_main.FullDatasetRunTests` |
| Owning suites | all batch, CLI, output, and usage behavior | `python3 -m unittest tests.test_pipeline tests.test_output tests.test_main tests.test_usage` |
| Full offline regression | final C implementer before real artifact generation | `python3 -m unittest discover -s tests -p 'test_*.py'` then `python3 -m compileall -q code tests` then `python3 -m unittest tests.test_agent_foundation_contract` then `git diff --check` |
| Real final boundary | replaces root output and actual usage snapshot only after all prior gates pass | `python3 code/main.py` |
| Final artifact reconciliation | generated files pass the real-boundary test or a dedicated non-mutating artifact-check mode added by C | `python3 -m unittest tests.test_main.GeneratedArtifactTests` |

## WP-10C Stops And Handoff

- Stop before the real run if targeted, owning, full-suite, compile, navigation,
  or hygiene gates fail.
- Stop if a live provider/network/credential action would be required and was
  not separately accepted and authorized. Preserve the accepted offline path.
- Stop if provider use lacks retained token metadata or an approved cost basis;
  do not fetch current prices or report false zero cost.
- Stop on any output/report mismatch. Do not hand-edit `output.csv` or
  `usage_report.md` to make the gate pass.
- Next: guided C implementation and the real run.
- Required follow-on: immediately after implementation or correction, hand the
  completed bytes and generated artifacts to a fresh independent acceptance
  reviewer. Accepted C bytes and artifacts unblock WP-11.

## Finite-Risk Coverage Contract

Keep these row IDs stable across implementation and correction reviews.

| Invariant | Material dimensions/cases | Decisive oracle/boundary | Implementation evidence | Independent review probe | Gate owner |
|---|---|---|---|---|---|
| FR-10-01 exact evaluation coverage | empty/synthetic N; real 250; missing; extra; duplicate; reordered; sample scope | accepted batch validator plus on-disk CSV IDs equal `requests.csv` order | A/B synthetic cases and C full-dataset temporary run | delete, duplicate, swap, and inject one sample row; each run rejects before success | A/B implementers; C final reviewer owns real aggregate gate |
| FR-10-02 stage failure atomicity | repository; evidence; normalization; forecast; planning; output build; output validate; batch validate; output write; usage report | one typed safe failure at the real stage; no partial batch; pre-publication old output preserved; report failure is non-success | injected A/B/C failures with sentinel destinations | fail the second case and each publication replace separately; inspect destination bytes and temp cleanup | owning part implementer/reviewer |
| FR-10-03 safe diagnostic envelope | run ID; known/unknown request; all stable stages; known/generic reason; safe source IDs | parsed JSON/count tables contain only approved fields and no raw carrier/exception/path/env data | redaction fixtures with poisoned raw messages and exception strings | inject secret-like exception text and absolute paths; assert absent from stdout/stderr/report | A/B/C implementers; fresh reviewer adversarial probe |
| FR-10-04 deterministic retries | first successful run; identical next run; failed next run; corrected rerun | output bytes identical for identical inputs/config; each file is replaced, never appended; one run ID per invocation | two-run tests and preserved-sentinel failures | run twice to separate paths and once over existing sentinels; compare bytes/record counts | B/C implementers; C final reviewer owns aggregate retry gate |
| FR-10-05 usage reconciliation | zero calls; one model; multiple models; missing metadata; missing cost basis; invalid/negative totals | per-model sums equal overall; averages divide by all requests; explicit zero-call statement; invalid inputs reject | C exact `Decimal` table tests | duplicate/drop one call and alter one token/cost value; reconciliation or expected totals detect it | C implementer/reviewer |
| FR-10-06 final artifact identity | run ID; policy ID; 250 count; output SHA-256; reason counts; report snapshot | success summary, batch result, on-disk output, and usage report agree | C full-boundary and generated-artifact tests | mutate one output byte or report identity field; artifact check fails | C implementer; fresh reviewer owns final generated-byte probe |

## Package Exit Criteria

WP-10 is complete only when A, B, and C receive fresh independent `ACCEPT` in
order; every FR-10 row passes on final bytes; the last real
`python3 code/main.py` invocation exits zero; root `output.csv` contains exactly
250 ordered, independently validated rows; `code/evaluation/usage_report.md`
reconciles to that output and truthfully reports the accepted provider
disposition; the full offline suite, compile, navigation, and hygiene gates
pass; and no ZIP, transcript, or submission work has been pulled forward from
WP-11.
