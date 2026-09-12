---
name: session-handoff
description: Create context-preserving handoff packets so work can continue after clearing, compacting, or moving an AI session. Use this skill whenever the user asks to hand off a session, summarize current work for another agent, prepare to clear context, make a continuation prompt, preserve decisions/files/results, or resume work in a new chat. It produces a copy/paste-ready packet with goals, decisions, changed files, commands, verification, blockers, risks, and next actions, plus optional filesystem artifact guidance.
compatibility: Works in coding agents and chat agents. Filesystem and shell access are optional but useful for verifying paths, git status, and durable handoff artifacts.
---

# Session Handoff

Use this skill to preserve the useful state of a session before the context window is cleared, compacted, or transferred to another agent. The goal is not to summarize the transcript. The goal is to give the next agent enough concrete state to continue the work without rediscovery.

## Core Judgment

Default to a copy/paste-ready handoff in the final response. That is the only format guaranteed to survive a context clear. Use a filesystem artifact as a companion when it would help preserve long details, generated outputs, or exact file paths, but never make the file the only handoff.

Treat the handoff as an operational brief:

- Preserve facts, decisions, file paths, commands, results, unresolved questions, and next actions.
- Exclude obsolete discussion, false starts unless they prevent repeated mistakes, and private chain-of-thought.
- Separate confirmed facts from assumptions or memory.
- Be explicit about what has not been verified.
- If a repo is dirty, distinguish user changes from agent-made changes when you can.
- Do not include secrets, tokens, private keys, or sensitive personal data. Redact them and state that you did.

## Workflow

1. Identify the newest user intent and the active goal. If the user changed direction, make the latest direction primary and mention older work only if it still matters.
2. Gather current state from available context. In coding sessions, verify with lightweight reads where possible:
   - `pwd`
   - `git status --short`
   - `git diff --name-only`
   - relevant file reads for files that were edited or discussed
   - recent command results and test output already visible in the session
3. Compress the session into reusable facts:
   - decisions made and the reason each matters
   - files created, modified, or intentionally left alone
   - commands run and their outcomes
   - tests, checks, screenshots, or manual verification
   - blockers, risks, missing inputs, and assumptions
   - pending background processes or servers
4. Decide whether to also write a handoff file:
   - If the user asked for copy/paste only, do not write a file.
   - If the handoff is long, has many file paths, or references generated artifacts, write a durable Markdown file when filesystem access is available.
   - Prefer a repo-local path such as `.handoff/session-handoff-YYYYMMDD-HHMM.md` when working inside a project. Use `/tmp` only when there is no suitable project workspace.
   - Include the file path in the copy/paste packet, but make the packet useful even if the file is never opened.
5. Produce the handoff packet using the template below. Keep it dense and factual.

## Handoff Packet Template

Use this structure unless the user asks for a different format:

````markdown
# Session Handoff

Generated: [date/time if available]
Workspace: [cwd or environment]
Primary goal: [one sentence]
Latest user request: [one sentence]

## Resume Prompt
Paste this into the next session:

```text
You are continuing a prior session. Use the handoff below as authoritative context, but verify filesystem state before editing. Do not revert user changes unless explicitly asked.

[compact continuation instruction: goal, current state, next action]
```

## Current State
- [What is true now]
- [What is partially done]
- [What is not done]

## Decisions
- [Decision] - [reason or consequence]

## Files And Artifacts
- `[path]` - [created/modified/read/planned], [important details]

## Commands And Verification
- `[command]` - [result]
- Not run: [checks not run and why]

## Open Threads
- [blocker/risk/question] - [what the next agent should do]

## Next Actions
1. [specific next action]
2. [specific next action]
3. [specific next action]

## Guardrails For The Next Agent
- [Do not repeat known failed approach]
- [Do not touch unrelated files]
- [Preserve user changes]
````

If the nested fenced block would break formatting in the current client, use indented text or a different fence length for the inner block.

## What To Include

Include these when they exist:

- User's actual goal, not just the task label.
- Current date when relative dates appeared in the session.
- Repository path, branch, dirty files, and relevant untracked files.
- Exact file paths with one-line descriptions.
- Commands that changed state.
- Commands that verified behavior.
- Errors encountered and whether they were resolved.
- Important implementation decisions and rejected alternatives.
- External sources or URLs used, with dates if timeliness matters.
- Active dev servers, ports, background jobs, or sessions that must be stopped.
- Environment variables by name only, not secret values.
- The next concrete action the next agent should take first.

## What To Omit

Omit or compress these:

- Long transcript history.
- Repeated attempts that no longer matter.
- Raw logs unless a short excerpt is necessary.
- Hidden reasoning. Summarize conclusions and evidence instead.
- Sensitive values. Use `[REDACTED]` and describe what kind of secret was removed.

## Filesystem Companion

When writing a file, use this short header:

````markdown
# Session Handoff

This file is a durable companion to the copy/paste handoff. The copy/paste packet is still the primary resume context.
````

Then include the same sections as the handoff packet. If the file includes extra details that are too long for the chat response, add an "Extra Detail" section and keep the chat packet focused.

## Quality Checklist

Before finalizing, check:

- Could a new agent identify the first next action within 30 seconds?
- Are all referenced files and commands specific enough to inspect or rerun?
- Are known uncertainties clearly labeled?
- Does the packet avoid depending on unstated session memory?
- Is there enough detail to avoid repeating failed work?
- Are secrets and private data omitted or redacted?

## Example

````markdown
# Session Handoff

Generated: 2026-06-26 09:42 Europe/Lisbon
Workspace: `/Users/example/repo/app`
Primary goal: Finish adding CSV export to the orders page.
Latest user request: Clear context after preserving current implementation state.

## Resume Prompt
Paste this into the next session:

```text
You are continuing a prior session in `/Users/example/repo/app`. Finish the CSV export on the orders page. Start by reading `src/orders/export.ts` and `src/orders/export.test.ts`, then run the focused test listed below. Do not revert unrelated dirty files.
```

## Current State
- CSV export implementation is drafted but not fully tested.
- The UI button already calls `exportOrdersCsv`.
- Filename formatting is still open.

## Decisions
- Use the existing `downloadBlob` helper - keeps behavior consistent with invoice export.
- Do not add a new CSV dependency - current escaping needs are simple.

## Files And Artifacts
- `src/orders/export.ts` - modified; contains CSV serialization.
- `src/orders/OrdersToolbar.tsx` - modified; export button wiring.
- `src/orders/export.test.ts` - created; missing edge case for quotes.

## Commands And Verification
- `npm test -- src/orders/export.test.ts` - failed on quote escaping.
- Not run: full test suite.

## Open Threads
- Quote escaping bug remains.
- Confirm desired filename with user only if existing invoice pattern is unclear.

## Next Actions
1. Fix quote escaping in `src/orders/export.ts`.
2. Add a regression test in `src/orders/export.test.ts`.
3. Run focused test, then consider full suite.

## Guardrails For The Next Agent
- Do not add a dependency unless the CSV scope expands.
- Do not touch unrelated dirty files.
````
