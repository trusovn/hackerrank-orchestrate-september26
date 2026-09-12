# Initial Analysis Packet

Status: ready to create exact product implementation master plan  
Readiness: 8 of 8 complete  
Last verified: 2026-09-12  
Scope: planning inputs for the Buy or Wait? implementation

## Purpose

This folder preserves the first-pass product and dataset analysis so another
agent can continue without rereading the entire participant dataset. It is not
the master implementation plan and does not override repository authority.

Use guidance in this order:

1. [`../../AGENTS.md`](../../AGENTS.md) for operating, security, logging, and
   challenge invariants.
2. [`../../problem_statement.md`](../../problem_statement.md) for authoritative
   product behavior and evaluation requirements.
3. [`../project-map.md`](../project-map.md) for live repository topology,
   placement, and commands.
4. This packet for observed dataset facts, working hypotheses, and follow-up
   analysis.

If this packet conflicts with a higher-authority source, correct this packet;
do not reinterpret the higher-authority source.

## Confidence Labels

- **AUTHORITATIVE**: stated by `AGENTS.md` or `problem_statement.md`.
- **OBSERVED**: measured directly from the supplied participant-facing files.
- **INFERRED**: supported by examples but not explicitly specified.
- **UNRESOLVED**: materially affects behavior and still needs a decision or
  experiment.

## Packet Contents

| Document | Purpose | Start here when |
|---|---|---|
| [`01-contract-and-invariants.md`](01-contract-and-invariants.md) | Compact authoritative product and submission contract | Designing any product behavior or validator |
| [`02-data-profile.md`](02-data-profile.md) | Corpus shape, schemas, distributions, integrity, and scenario coverage | Building loaders, fixtures, or analysis tools |
| [`03-evidence-catalog.md`](03-evidence-catalog.md) | Message taxonomy, image annotations, and extraction risks | Designing evidence extraction or multimodal work |
| [`04-open-questions-and-hypotheses.md`](04-open-questions-and-hypotheses.md) | P0 uncertainties, current hypotheses, and resolution evidence | Defining financial semantics or reviewing assumptions |
| [`05-todo-and-analysis-runbook.md`](05-todo-and-analysis-runbook.md) | Ordered follow-up work, cheap-model routing, outputs, and plan gate | Choosing the next task or preparing the master plan |
| [`06-structural-reconciliation.md`](06-structural-reconciliation.md) | Reproduced disputed counts (`REC-01/02/03/04/13`), scope formulas, and dataset fingerprint | Trusting or quoting a disputed dataset count |
| [`07-evidence-decision-pack.md`](07-evidence-decision-pack.md) | Sample-message typed facts, all-image decisions, and fail-closed evidence rules | Planning evidence extraction and validation |
| [`08-financial-semantics-decisions.md`](08-financial-semantics-decisions.md) | Planning dispositions, conservative defaults, bounded experiments, decision tables, and acceptance signals for remaining P0 financial semantics | Creating the exact product implementation master plan |

### Supplemental Research Notes

Three additional files were created independently of the numbered packet:

- [`dataset-stats.md`](dataset-stats.md)
- [`assumptions-ambiguities.md`](assumptions-ambiguities.md)
- [`rev-eng.md`](rev-eng.md)

They contain useful deeper probes, sample-discriminator ideas, and an
unpublished simulator's partial results. Treat them as lower-authority research
input, not current source of truth: several claims use different scopes, some
conflict with one another, and some label approximate reverse-engineering as
confirmed. The document-level reconciliation is recorded under `IA-006` in
the runbook; unresolved counts and behavior claims remain assigned to explicit
follow-up tasks there. In particular, do not adopt latest-prior/chained FX
fallback, ignore a pending debit, choose an ambiguous image total, continue or
stop recurring salary, or copy a claimed forecast algorithm solely from these
notes.

## Executive Finding

The repository and corpus are structured enough to support a deterministic
financial engine with a narrow evidence-extraction boundary. The dominant risk
is not architecture; it is reproducing the intended recurrence, variable-spend,
event-lifecycle, and date semantics behind the 25 solved examples.

Do not start with a model that directly recommends an answer. The safe target
flow remains:

```text
load and validate participant data
-> normalize events and extract grounded evidence
-> reconstruct a conservative 90-day ledger
-> enumerate eligible plans and optional spending changes
-> deterministically verify and rank candidates
-> render and validate output.csv
```

## Master-Plan Readiness Gate

Create the master implementation plan only after all of these are true. Under
the deadline-aware path, exhaustive corpus classification, all-sample ledger
reconstruction, policy sweeps, and production fixtures belong in early plan
slices rather than blocking creation of the plan.

- [x] Every P0 item in
  [`04-open-questions-and-hypotheses.md`](04-open-questions-and-hypotheses.md)
  is resolved, explicitly accepted as a conservative rule, or assigned to a
  bounded early implementation experiment with a stated safe fallback.
- [x] All 16 images have a selected value or explicit fail-closed disposition,
  evidence field, currency, confidence, and reviewer decision.
- [x] Observed message scenarios map to a typed fact schema and cannot bypass
  deterministic policy; full evaluation-message classification is deferred to
  implementation.
- [x] Public samples that discriminate each known financial rule are indexed;
  full per-request ledger traces are deferred to implementation.
- [x] Competing recurrence and variable-spend policies have named candidates,
  discriminating samples, an experiment boundary, and a conservative fallback.
- [x] Concurrent supplemental drafts have been reconciled, with conflicting
  claims either promoted with evidence or explicitly rejected.
- [x] Numeric precision, date ordering, eligibility, ranking, and output
  validation policies are written as decision tables.
- [x] Provider/model use, if any, is limited to justified extraction operations
  and has an offline test seam and cost-accounting path.

The ordered work and suggested model tier for each item are in the TODO
runbook. Run deterministic profiling and filtering before sending any data to a
model.

## Freshness

The observations in this packet describe the supplied dataset as it existed on
2026-09-12. Re-profile before relying on counts if any file under `dataset/`
changes. Generated predictions and organizer-only data must never be used to
retrofit these findings.
