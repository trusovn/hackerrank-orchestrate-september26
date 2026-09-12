# Diagnostics Guide

Use this guide after a documented command or runtime boundary fails. Canonical
commands and component ownership remain in [`project-map.md`](project-map.md);
product invariants remain in [`../problem_statement.md`](../problem_statement.md).

## Triage Sequence

1. Reproduce the failure without changing code or weakening the check.
2. Capture the exact command, exit status, shortest useful error, and relevant
   artifact path.
3. Classify the failing boundary with one diagnostic identifier from the table
   below.
4. Reduce the failure to the smallest synthetic fixture or participant-facing
   input that still exhibits it.
5. Use the project map to identify the owning component and closest test.
6. State the broken invariant, add or identify regression evidence, and correct
   it narrowly.
7. Rerun the reproducer, the owning focused test, and only the broader gate
   justified by the affected boundary.

Do not paste secrets, credentials, raw model prompts/responses, or raw sensitive
financial evidence into `log.txt`, test output, traces, or committed fixtures.
Record redacted identifiers, aggregate facts, hashes, or minimized synthetic
examples sufficient to reproduce the defect.

## Failure Classes

| Diagnostic ID | Boundary and expected signal | Investigate with | Recovery proof | Availability |
|---|---|---|---|---|
| `ENV-IMPORT` | Python executable, syntax, or imports; nonzero compile/run exit, `SyntaxError`, `ImportError`, or `ModuleNotFoundError`. | `python3 --version`; `python3 -m compileall -q code tests`; the named module and import path. | Compile succeeds, then the owning focused test passes. | Available now. No dependency installer exists. |
| `REPO-CONTRACT` | Required repository/dataset/agent artifact is missing or malformed; assertion names a path, header, ID, image, or unresolved Markdown link. Dataset-loading failures surface as redacted `RepositoryValidationError` reason codes (e.g. `unexpected_header`, `duplicate_event_id`, `option_total_mismatch`) with source file, row/field location, and safe source IDs only. | [`../tests/test_repository_contract.py`](../tests/test_repository_contract.py), [`../tests/test_repository.py`](../tests/test_repository.py), [`../tests/test_agent_foundation_contract.py`](../tests/test_agent_foundation_contract.py), and the exact failing reason code/path. | Rerun the failing contract test, then `python3 -m unittest tests.test_repository`, then the full unit suite. | Available now. |
| `LOGIC-DETERMINISTIC` | A pure rule returns the wrong value or violates an invariant; focused unit assertion shows input and expected behavior. | Owning module under [`../code/buy_or_wait/`](../code/buy_or_wait/) and its mirrored focused test. | Minimal regression passes, then the owning and full suites pass. | Test pattern available; financial logic is deferred. |
| `MODEL-PROVIDER` | Provider transport/authentication/rate/timeout failure; `ProviderError` or future redacted provider status with correlation ID. | [`../code/buy_or_wait/ai_boundary.py`](../code/buy_or_wait/ai_boundary.py), `python3 -m unittest tests.test_ai_boundary`, and future redacted call metadata. | Fake failure path remains classified; real-adapter smoke succeeds only when an explicit live check is authorized. | Fake path available; real adapter/runtime telemetry deferred. |
| `MODEL-VALIDATION` | Model content is empty, malformed, missing required data, or semantically unsupported; parser/validator exception distinct from provider failure. | Operation-owned parser/fixture and `python3 -m unittest tests.test_ai_boundary` for the boundary pattern. Never log raw sensitive content. | Invalid fixture fails safely before deterministic logic; valid fixture passes. | Generic gate available; feature schemas and runtime identifiers deferred. |
| `FIN-POLICY` | A recommendation breaches balance, cash-state, preference, payment-option, schedule, or spending-change policy. | Future deterministic policy validator, minimized request/profile/event fixture, and the cited rule in the product specification. | Regression proves the unsafe plan is rejected and a safe supported outcome is produced. | Deferred until the financial-policy validator exists. |
| `OUTPUT-CONTRACT` | Root output has wrong columns/order, row coverage, enum, bounds, dates, plan arithmetic, or unsupported actions/options. | `dataset/output.csv` for the supplied template, [`../tests/test_repository_contract.py`](../tests/test_repository_contract.py), and the future final-output validator artifact. | Validator accepts a valid minimized output and rejects the failing case; full generated file passes. | Template checks available; generated-output validator deferred. |
| `EVAL` | Public-sample scoring, quality threshold, token/cost accounting, or evaluation runner fails or disagrees with its report. | [`../code/evaluation/main.py`](../code/evaluation/main.py), [`../code/evaluation/usage_report.md`](../code/evaluation/usage_report.md), future versioned eval output, and final run metadata. | Reproduce on a named public sample, rerun the eval command, and reconcile usage totals with the final run. | Deferred; runner and populated report are placeholders. |

## Planning Contract For New Diagnostics

Every future task plan that adds or changes behavior must name:

- the expected failure signal;
- one existing diagnostic identifier above, or a narrowly justified new one;
- the exact command or artifact used to investigate it; and
- the focused recovery command that proves the boundary is healthy again.

When implementation makes a deferred diagnostic available, add its concrete
signal, owning artifact, and command here and update the project map in the same
change. Do not claim runtime or evaluation diagnostics before the owning feature
emits them.
