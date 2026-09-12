# Project Map

Verified on 2026-09-12 against commit `0637eb1` plus the bootstrap foundation changes in the working tree.

## Canonical commands

Run these from the repository root:

| Purpose | Command | Current scope |
|---|---|---|
| Starter entry point | `python3 code/main.py` | Exits successfully but is still an empty product placeholder. |
| Compile check | `python3 -m compileall -q code tests` | Syntax/import compilation for repository-owned Python. |
| Focused AI boundary tests | `python3 -m unittest tests.test_ai_boundary` | Offline provider fake and validation gate. |
| Full foundation verification | `python3 -m unittest discover -s tests -p 'test_*.py'` | AI boundary plus supplied scaffold/data contract. |

No install step or third-party dependency exists yet. Add and document one only when an implemented feature requires it.

## Layout and ownership

| Path | Responsibility |
|---|---|
| `AGENTS.md` | Highest repository-local agent rules, challenge contract, and required transcript logging. |
| `problem_statement.md` | Participant-facing product and output specification. |
| `README.md` | Human quick start, submission shape, and high-level dataset guide. |
| `code/main.py` | Canonical batch CLI entry point; product implementation is not present yet. |
| `code/buy_or_wait/` | Repository-owned Python source; currently only the provider-neutral AI boundary. |
| `code/evaluation/` | Evaluation runner placeholder and final-run `usage_report.md` source for `code.zip`. |
| `dataset/` | Supplied participant-facing inputs and blank output template; do not modify inputs. |
| `tests/` | Standard-library unit and repository-contract tests. |
| `docs/` | Bootstrap decisions, AI foundation boundaries, and this navigation map. |
| `output.csv` | Generated final predictions at the repository root; absent until a solution run creates it. |
| `log.txt` | Append-only, gitignored conversation transcript required for submission. |

## Placement rules

- Put product Python in `code/buy_or_wait/` and keep `code/main.py` a thin CLI/composition entry point.
- Put provider SDK adapters behind `ModelProvider`; do not import provider SDKs throughout financial logic.
- Put operation-specific model parsers beside the owning feature under `code/buy_or_wait/`. Add shared abstractions only after two real callers need them.
- Mirror source behavior under `tests/`; model unit tests use deterministic fakes and never require network access.
- Put small model fixtures under `tests/fixtures/ai/` only when a concrete feature schema exists.
- Keep public-example evaluation code and final-run usage accounting under `code/evaluation/` so they package as `evaluation/` inside `code.zip`.
- Write generated predictions only to root `output.csv`; never overwrite participant-facing dataset inputs.
- Update this map in the same change when canonical commands, top-level layout, or placement rules change.

## Durable constraints and known gaps

- `AGENTS.md` and `problem_statement.md` override summaries here.
- The financial engine, final output validator, model adapter, prompts, eval runner, usage report contents, and application diagnostics are not implemented.
- Model output is untrusted until an operation-specific parser and deterministic financial/policy checks accept it.
- Secrets are environment-only and must not enter Git, logs, traces, datasets, or submission artifacts.
- No CI, container, datastore, migration system, or generated-code workflow exists; none is justified at bootstrap scale.

