---
name: testing-discipline
description: Define, create, review, and maintain risk-based software tests and QA evidence. Use whenever you are asked to add, update, or review tests; fix a bug; validate a feature or refactor; choose test levels; improve coverage, assertions, test data, fixtures, mocks, determinism, or flakiness; define acceptance or release confidence; or plan functional or non-functional testing. Also use during implementation when a behavioral change needs new or changed test evidence even if tests are not explicitly requested. Pair with repo-foundation for test placement, canonical commands, and CI wiring.
---

# Testing Discipline

Build the smallest reliable body of evidence that the software behaves as intended and fails safely. Treat tests as executable contracts and maintained production assets, not as a line-coverage exercise.

## Respect the boundary

- Let repository instructions and `repo-foundation` decide where tests live, how commands are named, and how CI gates are wired.
- Use this skill to decide what evidence is needed, which test level proves it, how to implement it, and how to keep it trustworthy.
- Follow existing framework and repository conventions unless they prevent meaningful verification.
- Do not introduce a new framework, service, or broad harness for one test when the current stack can prove the behavior.

## Use the evidence workflow

1. **Discover local authority.** Read the relevant code, nearby tests, test configuration, fixtures, public contracts, bug report or specification, and local instructions. Identify the narrowest relevant command before editing.
2. **Define the contract and oracle.** State the observable behavior, preconditions, inputs, outputs or state transitions, failure behavior, and important invariants. Identify how the test will recognize correctness: an explicit expected result, invariant, trusted reference, metamorphic relation, safe-failure property, or stakeholder acceptance. Resolve a materially ambiguous oracle before implementation.
3. **Map risk.** Consider impact, likelihood, and how easily a failure would otherwise be detected. Include boundaries such as persistence, filesystem, network, queues, caches, processes, browser, time, randomness, concurrency, permissions, and third-party contracts. For high-assurance or regulated work, trace each material requirement or hazard to evidence or an explicit gap.
4. **Select evidence.** Choose the lowest test level that exercises the real behavior without replacing the decisive logic with mocks. Add higher-level evidence only for wiring, contracts, or critical flows lower levels cannot prove.
5. **Make the test capable of failing.** For a bug, reproduce the defect first when feasible. For new or changed behavior, prefer a test-first check when practical and demonstrate that the test rejects pre-change behavior, a focused mutation, or an equivalent controlled fault before relying on it. Confirm failure is due to the intended assertion, not a broken harness, and leave no temporary mutation behind. Explain when this demonstration is infeasible.
6. **Implement narrowly.** Cover the behavior and credible failure modes without speculative cases. Change production design for testability only when it exposes a legitimate boundary, improves cohesion or dependency control, or removes hidden global state. Do not add production branches or public hooks used only by tests.
7. **Verify progressively.** Run the new or changed test first, then the nearest relevant suite, then broader gates justified by transitive blast radius. Treat changed-file or test-impact selection as an optimization, not proof that unaffected tests cannot regress. Ask before costly, slow, flaky, destructive, or live-networked checks unless already approved.
8. **Report evidence.** Name commands and results, the behavior proved, important gaps, skipped stronger checks, and residual risk. Do not imply that passing tests prove untested properties.

For a refactor, establish a passing behavioral baseline before editing and run the same evidence afterward. Add tests only for uncovered contracts or observed risks; do not encode the old implementation merely to make the refactor feel safer.

## Shape the result to the task

- For implementation, create or update the tests and report the evidence. Do not create a separate strategy document unless the user or repository requires one.
- For a test strategy or plan, give a compact risk-to-evidence matrix: behavior or risk, test level and crossed boundary, scenario and oracle, priority, data or environment needs, and known gap. Add execution order, entry or exit criteria, and repository commands only where relevant.
- For a suite or test-change audit, lead with actionable findings ordered by impact. Include the affected location or example, the failure mode, why current evidence misses or destabilizes it, and the smallest corrective direction. State clearly when there are no findings.
- Omit catalog categories that do not map to a credible risk. A shorter justified strategy is better than a generic exhaustive checklist.

## Choose the test level

Use this decision order:

1. Prefer a **unit test** for deterministic domain logic, transformations, validation, state machines, and error mapping that can run through a stable observable interface.
2. Prefer a **component or module test** when several units collaborate but the full deployed system is unnecessary.
3. Add an **integration test** when correctness depends on a real boundary: database behavior, serialization, filesystem semantics, framework wiring, process execution, queues, caches, or a network adapter.
4. Add a **contract test** when independently changing producers and consumers must agree on requests, responses, messages, schemas, compatibility, or generated clients.
5. Add an **end-to-end or system test** only for critical user journeys, deployment wiring, or behavior that lower levels cannot establish. Keep the flow short and diagnostically useful.
6. Add a **smoke test** to prove that a build or deployment starts and its essential path is reachable; do not confuse this with behavioral depth.
7. Add specialized evidence only when the risk calls for it: property, fuzz, mutation, snapshot, visual regression, accessibility, security, performance, reliability, recovery, compatibility, migration, install, or exploratory testing.

Test-level names vary across ecosystems. Describe the scope, purpose, and real boundaries crossed instead of relying on a label alone.

Read [references/test-catalog.md](references/test-catalog.md) when defining a test strategy, reviewing broad coverage, preparing a release, or selecting specialized functional and non-functional evidence.

### Common selection rules

- Pure rules with broad input spaces: example-based unit tests plus properties, invariants, fuzzing, or metamorphic relations where useful.
- Data store, migration, or query semantics: exercise the real engine and schema version relevant to production.
- HTTP, RPC, event, or file formats: test domain behavior separately, then verify serialization and contracts at the boundary.
- UI behavior: test user-observable interaction and accessibility semantics at the component level; reserve end-to-end tests for critical cross-system flows.
- Visual correctness: use focused visual comparisons with reviewed baselines and stable rendering; pair them with semantic interaction tests.
- Retries, timeouts, idempotency, and concurrency: control time and scheduling where possible, assert bounded behavior, and include an integration test for the real boundary.
- Authorization and security controls: test denial as well as success, ownership and tenant boundaries, least privilege, unsafe inputs, and failure without information leakage.
- Performance-sensitive paths: define workload, environment, metric, threshold, and acceptable variance before measuring. A fast local run is not a performance claim.

## Design high-value cases

Derive cases from the contract and risk, not the code's branches alone. Use the relevant techniques:

- representative happy paths and common real inputs
- equivalence partitions and values just below, at, and above boundaries
- empty, missing, malformed, duplicated, out-of-order, oversized, stale, and unauthorized inputs where credible
- decision tables for interacting rules and state-transition tests for lifecycles
- pairwise or combinatorial selection when configuration combinations matter
- invariants, round trips, reference models, and metamorphic relations for large input spaces
- interruption, partial failure, retry, rollback, recovery, and idempotency for stateful operations
- locale, timezone, encoding, ordering, precision, and version compatibility when they affect the contract

Do not mechanically add every category. Every case should answer: what realistic defect would this catch, and is this the cheapest reliable place to catch it?

## Assert behavior, not construction

- Use an oracle independent enough to catch the defect. Do not calculate the expected result with the production algorithm or a rewritten copy of it.
- Assert returned values, durable state, emitted domain events, visible UI, documented errors, and externally meaningful side effects.
- Assert calls or call order only when the interaction itself is the protocol contract.
- Verify negative space when important: no write, no event, no disclosure, no duplicate effect, or no partial state.
- Prefer one clear behavioral reason for each test. Multiple assertions are fine when they describe one outcome.
- Avoid private methods, incidental queries, internal object shapes, framework call sequences, and exact wording unless they are public contracts.
- Make failure messages and test names explain the scenario and expected behavior.

## Control doubles and boundaries

- Prefer real pure collaborators and lightweight in-memory values.
- Use a test double only to control or observe a costly, nondeterministic, unavailable, or failure-prone boundary, or to simulate an otherwise hard-to-reproduce boundary outcome. Terminology such as fake, stub, spy, and mock varies; follow the local framework rather than enforcing a taxonomy.
- Assert interactions only when the interaction is itself a contract, such as protocol order, idempotency key propagation, or avoiding a forbidden side effect.
- Do not mock the subject under test or reproduce its algorithm in the setup.
- Do not build deep mock chains that mirror implementation structure.
- When compatibility risk justifies it, test adapters with the real dependency or a faithful local substitute in an integration or contract suite. If that is impractical, document that serialization, authentication, or protocol compatibility remains unproved.
- Keep network access out of default tests. Use explicit integration or live-test commands with controlled credentials and cleanup.

## Keep data and fixtures legible

- Use the smallest data set that makes the behavior obvious. Name fixtures by scenario, not by generic size or sequence.
- Keep decisive values visible in the test. Hide only irrelevant construction defaults behind builders or factories.
- Create independent, uniquely identified state and clean it up reliably. Do not rely on test order or hidden developer-machine state.
- Version contract samples, golden files, schemas, and snapshots with the behavior they represent.
- Avoid production personal or secret data. Generate synthetic data or use approved, minimized, anonymized samples.
- Prefer factories over shared mutable fixtures. If a large fixture is unavoidable, document its purpose and provide a narrow way to inspect or regenerate it.

## Enforce determinism

- Control clocks, randomness, locale, timezone, environment, ordering, and external availability when they are not the behavior under test.
- Use fixed or recorded random seeds and preserve a failing generated example.
- Replace sleeps with observable synchronization, fake time, polling with a deadline, or events. Keep eventual assertions bounded.
- Isolate ports, files, databases, accounts, and process state so parallel execution is safe.
- Do not hide failures with broad retries. Retry only a genuinely eventual observation and retain diagnostics from every failed attempt.
- Treat flakes as defects. Reproduce and fix the cause; quarantine only with an owner, issue, expiry condition, and retained visibility.

## Use coverage honestly

- Track coverage of risks, contracts, states, and boundaries first. Use line and branch coverage to find suspicious gaps, not as a quality target by itself.
- Require meaningful assertions. Executing a line without checking its effect is not evidence.
- Focus mutation testing on critical pure logic when ordinary coverage cannot show whether assertions are sensitive.
- Avoid duplicate tests at many levels unless each level protects a distinct failure mode.
- Maintain requirement-to-evidence traceability when the cost of an unproved requirement is high; do not impose traceability paperwork on routine low-risk changes.
- Document intentionally untested risk and why it is acceptable or deferred.

## Maintain the suite

- Change tests when the contract changes, not merely because implementation structure changes.
- During refactors, preserve behavioral tests and remove assertions coupled to internals.
- When fixing a brittle test, retain the defect-detection power; do not simply weaken or delete the assertion.
- Review snapshots and golden files as code. Keep them narrow, deterministic, human-readable, and regenerated through a documented path.
- Delete obsolete or redundant tests only after identifying the remaining test that protects the same behavior.
- Keep the default suite fast enough to run habitually. Separate slower evidence by purpose and make its invocation explicit through repository guidance.
- Investigate sustained runtime growth, nondeterminism, noisy logs, and hard-to-diagnose failures as maintenance problems.
- Revisit supported-version matrices, fixtures, contracts, and baselines when dependencies, platforms, schemas, feature flags, or user promises change.

## Review test changes

Check these questions before accepting a test change:

1. Which contract or risk does each test protect?
2. Would the test fail if that behavior were broken in a plausible way, and is its oracle independent enough to notice?
3. Is this the lowest reliable level, and is any decisive boundary mocked away?
4. Are assertions observable and stable across valid refactors?
5. Are setup, data, cleanup, and failure output understandable in isolation?
6. Can tests run independently, repeatedly, in parallel, and without hidden network or machine state?
7. Do higher-level tests cover only wiring or journeys that lower-level tests cannot prove, and does selected-test scope include transitive impact?
8. Are performance, security, accessibility, compatibility, or recovery risks relevant and either tested or explicitly deferred?
9. Did the change add duplicate evidence, brittle snapshots, sleeps, broad retries, or unnecessary harness complexity?
10. Were the narrow and appropriately broad verification commands actually run?

## Avoid test theater

Reject or repair:

- tests that mirror implementation branches without proving a contract
- mocks that restate the production algorithm
- happy-path-only coverage for important failure behavior
- broad end-to-end flows used to test simple logic
- snapshots approved only because they are large or changed
- tests that pass only in a particular order or on one machine
- arbitrary sleeps, unbounded waits, and retries that conceal flakes
- assertions that only check non-null, status success, or mock invocation when stronger outcomes exist
- coverage increases with no meaningful new defect detection
- giant fixtures whose decisive values cannot be understood
- permanent quarantines and ignored failures without ownership

## Definition of done

Testing work is complete when:

- the intended behavior and credible failure modes have proportionate evidence
- new tests were shown capable of failing for the expected reason when feasible
- targeted tests pass, followed by the broader suite justified by the change
- tests are isolated, deterministic, readable, and coupled to contracts rather than construction
- test data contains no unapproved secrets or personal information
- skipped expensive or environment-dependent checks and residual risks are reported explicitly
- any placement, command, or CI changes are handled by repository-local guidance or `repo-foundation`
