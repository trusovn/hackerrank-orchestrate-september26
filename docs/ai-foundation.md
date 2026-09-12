# AI Flow Foundation

## AI boundaries

| Boundary | Purpose | Provider seam | Input contract | Output validation | Status |
|---|---|---|---|---|---|
| Model inference | Support only the portions of evidence interpretation or candidate generation later proven to need a model. Exact operations remain feature decisions. | `buy_or_wait.ai_boundary.ModelProvider` | Provider-neutral request with operation, correlation ID, and opaque payload | Operation-specific validator must convert raw text to a validated type before deterministic logic can consume it | ESTABLISHED |
| Image/evidence interpretation | Extract grounded facts only if deterministic parsing is insufficient. | Reuse the model-inference seam | Exact carrier and supported fact schema | Reject malformed, missing, unsupported, or ungrounded values; exact schema is feature-owned | TBD-BY-FEATURE |
| Recommendation assistance | May propose structured candidates, but cannot own financial safety or final output validity. | Reuse the model-inference seam | Exact financial-context projection | Deterministic rules re-check every recommendation and output field | TBD-BY-FEATURE |

## Deterministic shell

```text
participant-facing CSV/image input
-> deterministic loading, normalization, and financial preprocessing
-> optional AI boundary
-> operation-specific parse/schema validation
-> deterministic financial safety, policy, and output validation
-> root-level output.csv
```

Raw model text is untrusted data. It must never write `output.csv`, change files, call external services, or bypass deterministic challenge rules directly.

## Provider/model access

- Adapter/interface: **ESTABLISHED** in `code/buy_or_wait/ai_boundary.py`; domain code depends on `ModelProvider`, not a provider SDK.
- Real-provider implementation: **TBD-BY-FEATURE** after provider/model selection.
- Test fake/fixture implementation: **ESTABLISHED** as a deterministic queued fake in the same foundation module; feature-specific fixtures belong under `tests/fixtures/ai/` when schemas exist.
- Configuration source: **TBD-BY-FEATURE** environment variables named only when a provider is selected.
- Secret handling: **ESTABLISHED** as environment-only; never commit, trace, or include secrets in request payloads or metadata.

## Validation

- Structured-output mechanism: **TBD-BY-FEATURE**; prefer a constrained structured response when downstream fields are required.
- Schema/parser location: **ESTABLISHED placement rule**: feature-owned parsers/validators live under `code/buy_or_wait/`; shared abstractions require at least two real call sites.
- Invalid-output behavior: **ESTABLISHED**: reject before deterministic business logic or output; classify as non-retryable unless failure is truncation/transient-provider related and a bounded retry is safe.

## Test seams

- Fixtures/fakes: **ESTABLISHED** deterministic `FakeModelProvider`; add small feature fixtures under `tests/fixtures/ai/` only when a concrete schema exists.
- Injection mechanism: **ESTABLISHED** constructor/argument injection through the `ModelProvider` protocol.
- Focused test command: `python3 -m unittest tests.test_ai_boundary`
- Required feature-owned failure fixtures:
  - malformed
  - missing field
  - unexpected value
  - empty
  - provider error/timeout
  - retry/duplicate, if applicable

## Evals

- Needed for acceptance: **yes**; hidden scoring evaluates recommendation quality and contract correctness.
- Eval dataset: **REUSE** `dataset/sample_requests.csv` for public examples; evaluation requests are never labels.
- Eval command: **TBD-BY-FEATURE** in the existing `code/evaluation/main.py` once sample-mode predictions exist.
- Result format: **TBD-BY-FEATURE**; must separate deterministic contract failures from prediction-quality metrics.
- Captured version metadata: **ESTABLISHED requirement**: provider, model, prompt/config version, code revision when available, calls, tokens, cost, and run timestamp. Final aggregate usage belongs in `code/evaluation/usage_report.md` so it packages as `evaluation/usage_report.md`.

## Observability

- Correlation/run ID: **ESTABLISHED requirement** per full run and request/model call.
- Operation/boundary: **ESTABLISHED requirement**.
- Provider/model: **ESTABLISHED requirement** without credentials.
- Latency/status: **ESTABLISHED requirement**.
- Validation result: **ESTABLISHED requirement**.
- Retry count: **ESTABLISHED requirement**.
- Prompt/response capture policy: **ESTABLISHED** default-off for raw content; if enabled for development, redact secrets and sensitive PII, keep it out of Git/submission artifacts, and record only what is needed to reproduce failures.

## Retry/state/side effects

- Retry policy: **ESTABLISHED** as no automatic retry by default. A feature may add bounded retries only for transient provider failures; malformed/semantically invalid output is non-retryable unless a distinct repair request is explicitly designed and measured.
- Idempotency boundary: **ESTABLISHED** per `(run_id, request_id, operation, input/config version)`; retries may replace an in-memory candidate but cannot append duplicate output rows or usage records.
- Persisted state owner: **N/A for foundation**; the intended batch run uses in-memory processing and final files. If resumability is later required, feature design must name a single owner and atomic-write semantics.
- Side-effect gate: **ESTABLISHED**: only deterministic, fully validated results may reach the output writer; write the final CSV once, preferably via a temporary file plus atomic replacement.
- Human approval: **N/A**; the challenge produces recommendations and does not execute real payments.

## Deferred to feature design

- Provider/model selection, prompts, routing, batching, caching, and multimodal strategy.
- Exact request/response schemas and operation-specific parsers.
- Financial algorithms, evidence conflict resolution, plan construction/ranking, and final explanation generation.
- Live integration tests, quality thresholds, eval metrics, and offline fallback behavior.
