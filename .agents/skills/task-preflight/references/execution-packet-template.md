# Task Preflight: `<TASK-ID>` — `<brief title>`

Status: `ready | blocked`

## Readiness summary

| Item | Result and evidence |
|---|---|
| Task / authority | `<brief or request and status>` |
| Repository | `<absolute root>` |
| Dependencies / entry criteria | `<confirmed state or blocker>` |
| Allowed scope | `<paths or bounded area>` |
| User-work ownership | `<clean, separable paths, or overlap>` |
| Permission limits | `<network/dependency/commit/destructive/slow-check policy>` |
| Profile | `guided | high-assurance` |

## Acceptance evidence and commands

| AC / risk | Observable oracle and boundary | Exact command | Baseline result / gap |
|---|---|---|---|
| `<AC-ID>` | `<positive plus important negative/lifecycle behavior>` | `<copy-pasteable command and cwd>` | `<passed, intended fail-first, not run, or blocker>` |

## Warnings, blockers, and next action

| Condition | Effect | Owner | Smallest next action |
|---|---|---|---|
| `<none, warning, or blocker>` | `<non-blocking limit or why implementation cannot begin>` | `<person/stage>` | `<action>` |

For `ready`, state the implementation stops and the next exact action. For
`blocked`, state that implementation must not begin.

---

## High-assurance packet addendum

Include every section below only for a high-assurance packet.

### Artifact identity and inputs

| Field | Value |
|---|---|
| Task ID | `<stable ID>` |
| Producing stage | `task-preflight` |
| Created at | `<ISO-8601 timestamp with timezone>` |
| Durable packet path | `<external or proved ignored/status-neutral path>` |
| Task brief | `<exact path and lowercase SHA-256>` |
| Primary authority | `<path>#<section> and digest>` |
| Dependency source | `<path, digest, and state>` |
| Instructions | `<applicable paths and digests>` |
| Run policy | `<identifier, paths, and digests>` |
| Environment fingerprints | `<values/digests or N/A>` |

### Repository baseline and dirty ownership

| Field | Value |
|---|---|
| `HEAD` | `<commit SHA or unborn>` |
| Exact `git status --short` | `<verbatim snapshot or clean>` |
| Packet-path neutrality | `<outside repository or ignored/status-neutral before and after>` |
| Final baseline recapture | `<unchanged or exact blocker>` |
| Incidental artifacts | `<paths/disposition or none>` |

| Status entry / path | Index SHA-256 or state | Worktree SHA-256 or state | Ownership | Task overlap | Evidence / disposition |
|---|---|---|---|---|---|
| `<verbatim status and path>` | `<sha256, absent, deleted, or not_applicable>` | `<sha256, absent, deleted, or not_applicable>` | `<user/task/tool/UNKNOWN>` | `yes | no` | `<source/route>` |

Preserve separate index and worktree identities for staged/unstaged
combinations, renames, and deletions even when short-status text is unchanged.

### Exact command records

| ID | Class / cost | Exact command | Working directory / environment | Purpose / ACs | Expected signal | Run? / result | Authorization |
|---|---|---|---|---|---|---|---|
| `CMD-01` | `<targeted; cheap/local>` | `<no placeholders>` | `<cwd and variables>` | `<behavior>` | `<observable oracle>` | `<yes/no; exit and signal>` | `<allowed or approval need>` |

### Helper and capability inventory

| Capability | Exact path / interface | Existence evidence | Authorized and usable? | Disposition |
|---|---|---|---|---|
| `<fixture/helper/runner/oracle>` | `<path/interface>` | `<inspection evidence>` | `yes | no` | `<use or blocker/owner>` |

### Implementer contract

Before the first edit, the implementer must recalculate the recorded brief,
Git, dirty-path, dependency, instruction, policy, and environment identities.
It may change only allowed paths, must preserve pre-existing work, run exact
commands progressively, and produce the supplied structured result. Any
unexplained freshness mismatch routes to fresh preflight.
