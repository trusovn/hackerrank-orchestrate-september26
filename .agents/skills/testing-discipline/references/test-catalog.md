# Test Catalog and QA Coverage

Use this catalog to choose relevant evidence for a feature, system, release, or test-suite review. It is a menu, not a mandate. Select areas from concrete product risk, architecture, users, data, operating environment, and change impact.

Verification asks whether the implementation satisfies its specified contract. Validation asks whether the resulting product satisfies user and stakeholder needs. Use both perspectives where product suitability matters. Testing terms vary between organizations, so define scope and crossed boundaries rather than assuming a label has a universal meaning.

## Contents

- Static and early feedback
- Functional scope and purpose
- Functional test design
- Specialized correctness tests
- Non-functional quality areas
- Change, release, and production confidence
- Strategy checklist

## Static and early feedback

Static checks prevent defects without executing the full system:

- compiler and type checking for invalid states, API misuse, and incompatible changes
- linting and formatting for enforceable correctness or consistency rules
- schema, configuration, migration, generated-code, and documentation validation
- dependency, secret, license, and static security analysis
- architecture or boundary checks when the repository has explicit layering rules

Do not count a static check as behavioral proof it cannot provide. Use it to shorten feedback and reserve runtime tests for runtime contracts.

## Functional scope and purpose

The core skill defines unit, component, integration, contract, system, end-to-end, and smoke selection. For a strategy, record what each selected level isolates, what real boundaries it crosses, and which distinct failure mode it protects.

### Acceptance and user acceptance

Translate business rules and examples into evidence stakeholders can evaluate. Acceptance tests may live at unit, API, component, or end-to-end level; acceptance describes purpose, not necessarily technical level. User acceptance testing validates suitability with authorized stakeholders and is not automatically replaced by an automated acceptance suite.

### Smoke and sanity

Smoke tests quickly prove essential startup and reachability after a build or deployment. Sanity tests give narrow confidence after a small change. Neither replaces regression depth.

### Exploratory

Use time-boxed human investigation for novel interactions, usability, unexpected states, and risks that scripted tests miss. Record charters, environment, observations, and reproducible defects. Automate durable regression cases afterward when valuable.

## Functional test design

### Specification-based techniques

- **Equivalence partitioning:** choose representatives from inputs expected to behave alike.
- **Boundary-value analysis:** test just below, at, and just above limits and transitions.
- **Decision tables:** cover meaningful combinations of conditions and outcomes.
- **State transitions:** cover valid and invalid events from each important state.
- **Use-case and journey testing:** cover actor goals, alternate paths, and failure paths.
- **Pairwise or combinatorial selection:** reduce large configuration matrices while covering interactions.

### Structure-based techniques

Use statement, branch, condition, path, and data-flow information to find gaps after contract-derived tests exist. Avoid writing tests solely to satisfy a number.

### Experience-based techniques

Use defect history, error guessing, production incidents, support cases, and exploratory testing to target likely failures. Convert recurring discoveries into stable automated checks at the lowest suitable level.

## Specialized correctness tests

### Regression and confirmation

A confirmation test proves a specific fix. Regression testing checks that established behavior remains intact. Put the smallest durable reproducer near the responsible behavior and add boundary-level evidence only when the defect arose from integration or wiring.

### Property-based and generative

Generate many inputs and assert invariants such as round trips, monotonicity, idempotency, conservation, or equivalence to a reference model. Constrain generators to meaningful domains, retain seeds and minimized failures, and supplement properties with readable examples.

### Fuzz

Feed malformed, unexpected, or adversarial inputs to parsers, protocol handlers, and trust boundaries. Define useful oracles such as no crash, no hang, bounded resource use, valid error response, or agreement with a reference implementation.

### Metamorphic

When an exact expected result is hard to compute, transform the input in a way that implies a relation between outputs. Examples include permutation invariance, reversible encoding, scale relations, and adding irrelevant data without changing the result.

### Mutation

Introduce controlled faults to see whether tests detect meaningful behavioral changes. Use selectively for critical logic and weak assertions; do not optimize blindly for a mutation score.

### Snapshot, golden, and approval

Use for stable, reviewable structured output where a full expected artifact is clearer than many assertions. Keep the artifact small, normalize nondeterministic fields, review diffs semantically, and avoid treating baseline regeneration as approval.

### Model-based

Represent allowed states and transitions, generate action sequences, and compare the system with the model. This is valuable for protocols, workflows, permission systems, and stateful APIs.

### Differential

Compare implementations, versions, platforms, or a new algorithm against a trusted reference on the same inputs. Explain tolerated differences and avoid assuming both implementations cannot share the same defect.

### Instrumented runtime analysis

Use memory, address, undefined-behavior, thread, race, or leak detectors and runtime assertions when the language and risk warrant them. Exercise representative concurrent and failure paths; a clean run covers only the schedules and inputs executed.

### Statistical and nondeterministic systems

For search, recommendation, simulation, probabilistic, or ML behavior, define distributions, tolerances, confidence, evaluation data, and repeated or seeded runs before testing. Combine invariant checks with task-specific quality and safety metrics, monitor drift, and do not turn a noisy single run into a deterministic gate.

## Non-functional quality areas

### Performance and efficiency

Choose the relevant mode:

- benchmark for a focused operation
- load for expected concurrent demand
- stress for behavior beyond capacity
- spike for sudden demand changes
- endurance or soak for leaks and degradation over time
- volume for large data sets
- scalability for resource and throughput relationships

Define representative workload, environment, warm-up, data shape, concurrency, metric, percentile, budget, variance, and pass threshold. Track regressions against comparable runs rather than mixing unlike machines or environments.

### Security

Combine static analysis, dependency and secret scanning, configuration review, threat-informed tests, and dynamic checks. Cover authentication, authorization, tenant isolation, input handling, injection, unsafe deserialization, path traversal, request forgery, session and token handling, rate limits, auditability, secure failure, and sensitive-data exposure as relevant. Use authorized environments only.

### Accessibility

Use semantic and automated checks for roles, names, keyboard access, focus order, contrast, form errors, reduced motion, and assistive-technology compatibility. Add manual keyboard and screen-reader checks for critical flows because automation cannot establish full usability.

### Usability

Evaluate whether representative users can complete important tasks accurately and efficiently. Use moderated or unmoderated studies, heuristic review, task observation, and analytics as appropriate. Do not substitute implementation assertions for user evidence.

### Compatibility and portability

Define a supported matrix for browsers, devices, operating systems, runtimes, databases, architectures, network conditions, and dependency versions. Select combinations by usage and risk, use pairwise reduction where suitable, and test upgrade and backward compatibility explicitly.

### Reliability, resilience, and recovery

Test timeouts, retries, backoff, circuit breaking, failover, duplicate delivery, out-of-order events, partial dependencies, process restarts, network partitions, and resource exhaustion where relevant. Verify data integrity, bounded degradation, recovery time, recovery point, observability, and operator action. Use fault injection or chaos experiments only with controlled blast radius and approval.

### Installation, configuration, and deployment

Test clean install, upgrade, rollback, startup, shutdown, configuration precedence, missing and invalid configuration, secrets injection, migrations, health checks, and deployment topology. Smoke-test the produced artifact, not only the source checkout.

### Data integrity and migration

Cover constraints, transactions, concurrency, precision, encoding, schema evolution, forward and backward compatibility, backfill idempotency, partial failure, rollback or roll-forward, and reconciliation. Test representative production-scale shapes without importing unapproved production data.

### Localization and internationalization

Cover locale formats, pluralization, text expansion, right-to-left layout, Unicode, collation, timezone and daylight-saving transitions, calendars, currencies, and translated error or accessibility content where supported.

### Privacy and compliance

Verify consent, minimization, purpose limitation, retention, deletion, export, access control, audit trails, redaction, and logging behavior against the system's actual obligations. Do not infer legal compliance from technical tests alone; identify required specialist review.

### Observability and operability

Verify that critical failures produce actionable logs, metrics, traces, alerts, correlation identifiers, and health signals without leaking sensitive data. Test runbooks, alert routing, maintenance operations, backup restoration, and degraded modes for important services.

### Maintainability and testability

Use architecture checks, complexity or duplication signals, dependency rules, and change-focused reviews to identify maintenance risk. Verify supported extension and configuration points where they are contractual. Treat metrics as investigation signals, not proof of maintainability.

### Safety and high-assurance systems

Derive evidence from hazard analysis, fail-safe states, safety requirements, independence needs, and required assurance levels. Preserve requirement-to-test traceability and qualified environments where mandated. Testing supports but does not replace required safety analysis, formal methods, independent review, or certification.

## Change, release, and production confidence

- **Build verification:** prove the artifact compiles, packages, and starts.
- **Changed-area regression:** exercise affected contracts and dependency boundaries.
- **Full regression:** use for broad or high-risk releases when its cost is justified.
- **Release acceptance:** verify business-critical flows in the release candidate environment.
- **Canary or staged rollout:** limit exposure and compare health signals before expansion.
- **Feature-flag transition:** test important enabled and disabled behavior, migration between states, rollback, and eventual flag removal.
- **Synthetic monitoring:** continuously exercise a small critical path in production-safe ways.
- **Post-deployment smoke:** verify the deployed version, routing, configuration, and essential dependencies.
- **Rollback or recovery rehearsal:** demonstrate that operational recovery works before relying on it.

Production checks complement pre-release testing. They require approved scope, safe test identities and data, bounded load, cleanup, and observability.

## Strategy checklist

For a broad test strategy or release assessment, define:

1. Scope, quality goals, users, architecture, and excluded areas.
2. Risk list ranked by impact, likelihood, and detectability.
3. Behavior, failure, security, data, operational, compatibility, and safety contracts, with trustworthy oracles.
4. Selected test levels and why each catches a distinct failure mode.
5. Test-design techniques and representative cases.
6. Environments, versions, dependencies, tools, identities, synthetic data, and material differences from production.
7. Entry criteria, exit criteria, pass thresholds, and stop conditions.
8. Ownership, execution frequency, diagnostics, triage, and defect workflow.
9. Flake policy, quarantine limits, fixture and baseline maintenance, and suite runtime budgets.
10. Requirement and risk traceability where justified, plus known gaps, residual risks, manual checks, and evidence required after deployment.

Keep the strategy proportional. A small change may need only a regression test and targeted command; a system release may need the full checklist.
