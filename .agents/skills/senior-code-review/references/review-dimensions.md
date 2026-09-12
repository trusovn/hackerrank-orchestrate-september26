# Review dimensions

Apply these as risk prompts, not as a requirement to produce one comment per category. Trace only dimensions relevant to the scoped change.

## Requirements and correctness

- Does observable behavior satisfy the stated requirement and acceptance criteria?
- Are boundary values, empty states, partial failures, and invalid transitions handled?
- Does every branch return the intended status, value, error, and side effect?
- Can stale state, retries, reordered events, or duplicate requests violate an invariant?
- Does the implementation fail closed where the domain requires it?

## Security and privacy

- Is identity taken from a trusted session/token rather than user-controlled input?
- Is authorization enforced on the target object and action, not only authentication?
- Can input reach SQL, shell, templates, paths, URLs, logs, or deserializers unsafely?
- Are secrets, tokens, personal data, and internal errors excluded from logs and responses?
- Are tenant, account, and cache boundaries preserved?
- Do defaults, fallback paths, or error paths weaken security?

Report a security issue only with a credible path from attacker-controlled input to impact.

## Data integrity, state, and migrations

- Are transactions aligned with domain invariants and side effects?
- Can concurrent requests cause lost updates, overselling, double processing, or inconsistent reads?
- Are idempotency and retry semantics explicit for mutating operations?
- Do schema changes preserve existing data and support mixed-version rollout?
- Is backfill behavior correct for historical rows rather than only fresh databases?
- Are uniqueness, foreign keys, nullability, precision, time zones, and ordering correct?
- Is rollback safe, or is irreversibility documented and operationally managed?

## APIs and compatibility

- Do request/response schemas, status codes, errors, and events match their contracts?
- Are existing callers broken by changed names, types, defaults, ordering, or semantics?
- Are serialization and deserialization compatible across deployed versions?
- Do pagination, filtering, versioning, rate limits, and partial responses remain coherent?
- Are external failures mapped without hiding retryable versus permanent conditions?

## Architecture and maintainability

- Does the change respect established module boundaries and dependency direction?
- Is domain logic placed where existing code expects it?
- Does it introduce a second pattern, abstraction, or source of truth without need?
- Are lifecycle, ownership, cleanup, and configuration responsibilities clear?
- Is complexity proportional to the requirement?

### SOLID as diagnostic heuristics

Use SOLID when the changed design involves object responsibilities, polymorphism, interfaces, or dependency boundaries. It is not a scorecard, and a principle's name is never sufficient evidence for a finding.

- **Single Responsibility:** Does one unit combine policies with genuinely independent reasons to change, owners, or lifecycles, causing routine changes to affect unrelated behavior?
- **Open/Closed:** Where the code already has demonstrated variants, does each new variant require risky edits to stable central logic? Do not invent an extension point for one known case.
- **Liskov Substitution:** Does a subtype preserve the base contract's valid inputs, outputs, invariants, side effects, and error behavior, or can a caller fail solely because it received that subtype?
- **Interface Segregation:** Are clients forced to depend on methods or data they do not use, making unrelated changes or test doubles spread across consumers?
- **Dependency Inversion:** Does high-level policy depend directly on volatile infrastructure or concrete details in a way that breaks the repository's established dependency direction?

Report a SOLID-related finding only when the scoped change introduces or worsens a concrete failure mode, unsafe substitution, change amplification, testing barrier, or boundary violation. Do not request an interface for every class, split a cohesive unit merely because it is large, or add abstractions for hypothetical future requirements.

Do not flag unfamiliar style as architecture. Show the boundary or maintenance failure it creates.

## Performance and reliability

- Does the changed path add unbounded work, N+1 I/O, large allocations, blocking calls, or lock contention?
- What happens under realistic volume, latency, timeout, and downstream failure?
- Are timeouts, cancellation, retries, backoff, and circuit behavior safe together?
- Can retries amplify load or repeat non-idempotent side effects?
- Are resources closed on every path?
- Does caching have correct keys, invalidation, freshness, and tenant isolation?

Quantify or bound the risk where possible. Avoid speculative micro-optimization comments.

## Tests and verification

- Is each important changed behavior asserted at the lowest useful level?
- Are failure, authorization, migration, concurrency, and compatibility paths covered where relevant?
- Would the test fail if the implementation regressed in the way it claims to prevent?
- Are mocks hiding the integration contract under review?
- Were existing assertions weakened, deleted, skipped, or made less deterministic?
- Do fixtures represent existing production state as well as newly created state?

A missing test is a finding only when it leaves a concrete important behavior unprotected.

## Operations and observability

- Can the change be deployed, monitored, diagnosed, rolled back, or disabled safely?
- Are new failure modes visible through existing logs, metrics, traces, or alerts?
- Do logs contain enough stable context without secrets or personal data?
- Are configuration defaults safe and compatible across environments?
- Do background jobs expose poison messages, retry exhaustion, and partial progress?

Operational concerns should match the repository's maturity and the change's blast radius.

## User and developer experience

- Are errors actionable and consistent with existing behavior?
- Are accessibility, localization, and input-device behavior affected?
- Does a public interface remain understandable and hard to misuse?
- Are documentation or examples required because the contract changed?

Avoid subjective UX critique unless a requirement, established pattern, or concrete usability failure supports it.
