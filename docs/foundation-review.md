# Foundation Readiness Review

Reviewed on 2026-09-12 against the materialized repository foundation and the
working tree reported by `git status --short`.

## Verdict

READY_WITH_NOTES

An unfamiliar capable agent can enter through `AGENTS.md`, select only the
needed workflow and component context, find placement and commands in the
project map, and classify failures in the diagnostics guide without relying on
this conversation. Deferred product runtime and evaluation capabilities are
named as unavailable rather than presented as working foundation features.

## Command Verification

| Capability | Command | Result | Notes |
|---|---|---|---|
| Bootstrap/install | `python3 --version` | PASS | Python 3.14.6 is available. No third-party dependencies or install step are declared. |
| Build/typecheck | `python3 -m compileall -q code tests` | PASS | Repository-owned Python compiled with exit 0; this is not a static type checker. |
| Focused foundation contract | `python3 -m unittest tests.test_agent_foundation_contract` | PASS | 3 tests passed: required docs exist, root routing links exist, and authoritative local Markdown links resolve. |
| Full/normal verify | `python3 -m unittest discover -s tests -p 'test_*.py'` | PASS | 11 tests passed across agent foundation, AI boundary, and repository/dataset contracts. |
| Lint/static | N/A | N/A | No lint or static-analysis tool is declared or justified for the dependency-free scaffold. |
| Run/boot | `python3 code/main.py` | PASS | Exited 0 with no output, matching the documented empty product placeholder; this is not product readiness. |
| Migration smoke | N/A | N/A | The batch CLI has no datastore or migration system. |
| AI fake/fixture test | `python3 -m unittest tests.test_ai_boundary` | PASS | 4 tests passed offline for valid output, invalid output, provider failure, and exhausted fake outcomes. |
| Repository/data contract | `python3 -m unittest tests.test_repository_contract` | PASS | 4 tests passed for supplied schemas, request coverage, images, and submission source locations. |
| AI eval smoke | N/A | N/A | The evaluation runner is explicitly deferred until sample-mode predictions exist. |
| Patch hygiene | `git diff --check` | PASS | No whitespace errors in tracked changes. |

Additional checks:

- The foundation contract was demonstrated fail-first: before materialization it
  reported the missing diagnostics document and four missing root routing links;
  the unchanged test then passed after the documents were implemented.
- `git check-ignore -v log.txt` resolves to `.gitignore:1:log.txt`.
- Targeted `rg` inspection confirmed that the documented authority, task routes,
  placement rules, commands, tool-registry fields, diagnostic identifiers, and
  diagnostic planning contract are present in the persisted entry path.

## Agent-Legibility Check

- **What authority applies?** Discoverable. `AGENTS.md` explicitly orders root
  operating rules, the product specification, the live project map, and
  module-local instructions.
- **What should be read for a specific task?** Discoverable. The bounded-context
  protocol routes an agent through the map to one owning component, closest
  precedent, selected workflow, and selected skill rather than a repo-wide read.
- **Where should code, tests, tools, and docs live?** Discoverable. The project
  map assigns each current module and states placement rules for product code,
  mirrored tests, evaluation, generated output, testable utilities, wrappers,
  and cross-project documentation.
- **Which command verifies the change?** Discoverable. Canonical commands and
  closest precedents name focused and broad checks, including the agent
  foundation contract.
- **Where should a failure be diagnosed?** Discoverable. `docs/diagnostics.md`
  gives an ordered triage process and identifiers for environment/import,
  repository contract, deterministic logic, provider, model validation,
  financial policy, output, and evaluation failures.
- **Generated versus editable files clear?** Yes. Dataset inputs are protected;
  root `output.csv` is generated; `log.txt` is append-only and ignored; the
  usage report is a final-run artifact source.
- **Tooling state honest?** Yes. The map records no current repository-owned
  tools or wrappers, defines the registry contract, and prohibits empty
  `tools/` or `scripts/` directories.

## AI Foundation Check

- Provider seam: `ModelProvider` isolates provider SDK concerns.
- Deterministic fake/fixture: `FakeModelProvider` queues responses or failures
  and records calls without network access.
- Output validation: `invoke_validated` exposes only parser-produced values;
  raw content has no side-effect path.
- Retry/idempotency: automatic retries are disabled by default and the persisted
  contract requires bounded retry and per-run/request/operation identity.
- Trace/debug path: required metadata is specified, while real-adapter telemetry
  is honestly marked deferred in the diagnostics guide.
- Eval seam: location and required final metadata are established; the executable
  runner remains explicitly deferred.

Provider failure and model parse/validation failure remain distinguishable in
the AI boundary tests. Ordinary tests require no live provider.

## Blockers

None.

## Notes

- `code/main.py`, `code/evaluation/main.py`, and
  `code/evaluation/usage_report.md` are placeholders. Financial policy, final
  output validation, runtime provider telemetry, and evaluation diagnostics must
  arrive with the product features that own them.
- There is no formatter, linter, static type checker, CI workflow, task runner,
  container, or repository-owned tool. The current direct commands are
  proportionate to the small standard-library scaffold; any future addition
  must update the project map and its tool registry as applicable.
- `docs/foundation-plan.md` is retained as a clearly marked historical bootstrap
  record and is not part of the live operating route.

## Recommended Delivery Route

`PERSONAL_FLOW`

### Reasons

- The governing behavior and output contract are detailed and stable.
- The intended system is a single Python batch CLI without a database, API, UI,
  concurrency, or migration boundary.
- Source, test, tool, documentation, AI-boundary, validation, and diagnostic
  placement are now explicit.
- Remaining risk is concentrated in financial edge cases, evidence
  interpretation, and hidden-test coverage, which fit bounded tasks with
  deterministic tests.
- Contest time pressure favors repeated focused tasks; escalate only if preflight
  finds contradictory requirements or a genuinely cross-cutting contract.

### Next Step

Use `task-brief-designer` for the first bounded product behavior, then apply
`task-preflight` only if repository state or dependencies are uncertain,
followed by `bounded-task-implementer` and an independent
`task-acceptance-review` when warranted.
