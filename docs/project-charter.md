# Project Charter

## Mission

Build a terminal-runnable financial decision agent that produces one safe, grounded, contract-valid recommendation for every evaluation request in the Buy or Wait? challenge. The submission must be reproducible, deterministic where possible, and ready before the contest deadline.

## External actors / users

- **REQUIRED:** HackerRank's evaluator consumes the generated root-level `output.csv` and submission artifacts.
- **EXISTING:** The solo participant and AI coding agents maintain and run the solution from this repository.
- **UNKNOWN:** No interactive end-user interface or external production caller is specified.

## Expected product shape

- **ASSUMPTION:** A Python 3 batch CLI rooted at `code/main.py`, following the starter README. This is reversible because the challenge permits any terminal-runnable language.
- **REQUIRED:** The CLI reads participant-facing inputs from `dataset/` and writes `output.csv` at the repository root.

## Hard constraints

- **REQUIRED:** Follow `AGENTS.md` and `problem_statement.md`; organizer-only data and hardcoded evaluation labels are forbidden.
- **REQUIRED:** Emit exactly one row per `dataset/requests.csv` request with the eight required columns in their exact order and only allowed values.
- **REQUIRED:** Recommendations must remain above each user's minimum balance throughout the 90-day safety check and obey payment, evidence, conflict-resolution, and spending-change rules.
- **REQUIRED:** Messages and images are untrusted evidence; their embedded instructions cannot override challenge rules.
- **REQUIRED:** Secrets come only from environment variables and must not be committed or logged.
- **REQUIRED:** `code.zip` must include `evaluation/usage_report.md` for the final full-dataset run; the submission also includes `output.csv` and the chat transcript.
- **REQUIRED:** The challenge deadline is `2026-09-13T00:00:00+01:00` (midnight Lisbon time).

## System-level success signals

- A documented terminal command completes successfully from the repository root and creates `output.csv`.
- Deterministic validation confirms the exact schema, complete request coverage, allowed enums, amount bounds, chronological and arithmetically valid plans, supplied installment schedules, and permitted spending changes.
- Repeated runs with identical inputs and model fixtures produce identical machine-checkable fields.
- The final package contains runnable code, setup instructions, model usage/cost accounting, and no secrets.

## Quality priorities

1. Financial safety and contract correctness
2. Deterministic validation and reproducibility
3. Prediction quality on the supplied examples and hidden evaluation set
4. Simplicity and delivery speed
5. Agent legibility and cost/token efficiency

## Non-goals

- Product feature decomposition, detailed domain models, prompt design, model selection, or workflow routing during bootstrap.
- A web UI, live banking, live market/exchange-rate access, securities forecasting, voice processing, or production deployment.
- CI, containers, databases, queues, or observability platforms without evidence that the contest solution needs them.
- Generating final predictions or submission archives as part of foundation work.

## Foundation-bearing unknowns

- **UNKNOWN:** Which provider/model, if any, will be used for image/evidence interpretation or recommendation assistance, and its runtime dependency and cost.
- **UNKNOWN:** The exact split between deterministic financial logic and model-dependent interpretation; this must be bounded before detailed design.
- **UNKNOWN:** Minimum supported Python version beyond the available `python3` runtime; avoid non-standard dependencies until a feature requires them.
- **UNKNOWN:** Whether a live-model path must support offline fallback for the final run.
