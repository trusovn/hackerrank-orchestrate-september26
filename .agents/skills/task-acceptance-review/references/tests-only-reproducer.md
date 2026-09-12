# Post-verdict tests-only reproducer

Use this procedure only after `SKILL.md` has established and reported a fixed
independent `CHANGES_REQUESTED` verdict, explicit current-invocation
`tests_only_reproducer` authorization, and the exact writable owning test path
or area. If any of those facts is absent or ambiguous, stop without writing.

## Preserve the review boundary

- Keep the pre-write verdict final for this session. Do not rename it, append a
  replacement verdict, or accept corrected production bytes.
- Do not load `bounded-task-implementer`, fix production code, or broaden into a
  general implementation role.
- Treat authorization as an allowlist: change only an existing owning test file
  or an explicitly authorized new test file.
- Do not create shared harnesses, fixtures outside the authorized area,
  dependencies, plans, task/result artifacts, trackers, or reports in the
  repository. Do not stage, commit, or normalize unrelated Git state.

## Add the smallest deterministic reproducer

1. Record the exact current-invocation authorization source, exact allowed test
   path or area, exact `git status --short`, and authorized test-path diff
   before writing. Preserve all pre-existing user and task changes.
2. Reuse the demonstrated finding trigger, broken invariant, and existing
   owning-test conventions. Add only the focused regression needed to expose
   that confirmed finding; do not speculate about unproved sibling defects.
3. Run the narrowest focused command. The intended outcome is a deterministic
   failure whose assertion and observed signal demonstrate the reviewed
   contract violation. Import, collection, fixture, timeout, or environment
   failures do not qualify.
4. If the test does not fail for the intended reason, correct only the
   authorized test or stop and report the gap. Never change production to make
   the reproducer pass or fail.
5. Recheck exact status and diff. Confirm production bytes and every
   unauthorized path are unchanged, and report any runtime side effects and
   cleanup.

## Report without changing the verdict

Append an optional human-readable section:

```markdown
Post-verdict reproducer:
- Authorization source: <exact current invocation text or reference>
- Exact allowed test path/area: <allowlisted path>
- Changed tests: <exact paths>
- Focused command/result: <command, exit, intended assertion signal>
- Pre-write git status --short: <verbatim status>
- Post-write git status --short: <verbatim status>
- Diff side effects: <authorized test diff, production unchanged, cleanup>
- Next: correction by the bounded implementer, then a fresh independent review
```

The next route is always production correction by an authorized implementer,
followed by a fresh reviewer that receives the task brief, corrected scoped
diff, fixed verdict and continuation block, this regression path/command, and
all blocked or unchecked coverage rows.
