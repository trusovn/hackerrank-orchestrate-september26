# AI Flow Foundation

## AI boundaries

| Boundary | Purpose | Provider seam | Input contract | Output validation | Status |
|---|---|---|---|---|---|
| | | | | | ESTABLISHED/REUSE/TBD-BY-FEATURE/N/A |

## Deterministic shell

```text
input
-> deterministic preprocessing
-> AI boundary
-> parse/schema validation
-> deterministic policy/business logic
-> side effect/output
```

## Provider/model access
- Adapter/interface:
- Real-provider implementation:
- Test fake/fixture implementation:
- Configuration source:
- Secret handling:

## Validation
- Structured-output mechanism:
- Schema/parser location:
- Invalid-output behavior:

## Test seams
- Fixtures/fakes:
- Injection mechanism:
- Focused test command:
- Required failure fixtures:
  - malformed
  - missing field
  - unexpected value
  - empty
  - provider error/timeout
  - retry/duplicate, if applicable

## Evals
- Needed for acceptance: yes/no
- Eval dataset:
- Eval command:
- Result format:
- Captured version metadata:

## Observability
- Correlation/run ID:
- Operation/boundary:
- Provider/model:
- Latency/status:
- Validation result:
- Retry count:
- Prompt/response capture policy:

## Retry/state/side effects
- Retry policy:
- Idempotency boundary:
- Persisted state owner:
- Side-effect gate:
- Human approval: N/A / <boundary>

## Deferred to feature design
- <prompt contents, detailed routing, workflow graph, feature schemas, etc.>
