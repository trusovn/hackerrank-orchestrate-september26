#!/usr/bin/env python3
"""Create executable repositories, packets, and checkpoints for implementer evals."""

from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess
import sys
import textwrap


WORK = Path(os.environ.get("EVAL_WORK_ROOT", "/work"))
RUNS = WORK / "task-runs"
SCHEMA = WORK / "contracts/worker-result.schema.json"


def write(root: Path, relative: str, content: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).strip() + "\n", encoding="utf-8")


def initialize(root: Path) -> None:
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.email", "eval@example.invalid"], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.name", "Eval Fixture"], check=True)


def git(root: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(root), *args], check=True, text=True, capture_output=True).stdout.rstrip("\n")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_sha(path: Path) -> str:
    return sha(path.read_bytes())


def install_contracts() -> Path:
    SCHEMA.parent.mkdir(parents=True, exist_ok=True)
    SCHEMA.write_text(json.dumps({
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "properties": {
            "status": {"type": "string", "enum": ["complete", "needs_input", "blocked", "failed"]},
            "task_id": {"type": "string"},
            "summary": {"type": "string"},
            "files_changed": {"type": "array", "items": {"type": "string"}},
            "verification": {"type": "array", "items": {"type": "object", "properties": {"command": {"type": "string"}, "outcome": {"type": "string", "enum": ["passed", "failed", "not_run"]}, "summary": {"type": "string"}}, "required": ["command", "outcome", "summary"], "additionalProperties": False}},
            "decisions": {"type": "array", "items": {"type": "object", "properties": {"decision": {"type": "string"}, "reason": {"type": "string"}, "scope": {"type": "string", "enum": ["task", "plan"]}}, "required": ["decision", "reason", "scope"], "additionalProperties": False}},
            "questions": {"type": "array", "items": {"type": "object", "properties": {"question": {"type": "string"}, "recommendation": {"type": "string"}, "blocking": {"type": "boolean"}}, "required": ["question", "recommendation", "blocking"], "additionalProperties": False}},
            "risks": {"type": "array", "items": {"type": "string"}},
            "next_action": {"type": "string"},
        },
        "required": ["status", "task_id", "summary", "files_changed", "verification", "decisions", "questions", "risks", "next_action"],
        "additionalProperties": False,
    }, indent=2) + "\n", encoding="utf-8")
    policy = RUNS / "policies/local-medium-v1.json"
    policy.parent.mkdir(parents=True, exist_ok=True)
    policy.write_text(json.dumps({
        "id": "local-medium-v1",
        "runtime_root": str(RUNS),
        "allow": ["packet allowed repository writes", "cheap local tests", "runtime artifact writes"],
        "deny": ["network", "dependency installation", "commits", "other repository paths"],
    }, indent=2) + "\n", encoding="utf-8")
    return policy


def queue_task() -> None:
    root = WORK / "queue-runner"
    initialize(root)
    policy = install_contracts()
    write(root, "AGENTS.md", "# Fixture rules\n\nEdit only packet-authorized paths. Preserve pre-existing user work. Runtime artifacts live outside the repository.")
    write(
        root,
        "docs/tasks/QR-12.md",
        """
        # QR-12 — Repeated queue selection

        Artifact status: ready_for_preflight
        Allowed paths: src/queue/run_next.py; tests/integration/test_run_next.py
        AC-01: two consecutive public invocations persist state and claim TASK-1 then TASK-2.
        AC-02: an empty queue returns no claim and does not rewrite state.
        Legacy sweep: inspect guards that stop when any task is already running.
        """,
    )
    write(root, ".runner/tracker.json", '{"complete": ["QR-11"]}')
    write(root, "notes/local.md", "baseline notes")
    write(root, "src/__init__.py", "")
    write(root, "src/queue/__init__.py", "")
    write(
        root,
        "src/queue/run_next.py",
        """
        import argparse
        import json
        from pathlib import Path

        def run_next(state_path):
            path = Path(state_path)
            state = json.loads(path.read_text())
            if any(task["status"] == "running" for task in state["tasks"]):
                return None
            task = next((item for item in state["tasks"] if item["status"] == "ready"), None)
            if task is None:
                return None
            task["status"] = "running"
            path.write_text(json.dumps(state))
            return task["id"]

        if __name__ == "__main__":
            parser = argparse.ArgumentParser()
            parser.add_argument("state")
            args = parser.parse_args()
            claimed = run_next(args.state)
            if claimed:
                print(claimed)
        """,
    )
    write(root, "tests/__init__.py", "")
    write(root, "tests/integration/__init__.py", "")
    write(
        root,
        "tests/integration/test_run_next.py",
        """
        import json
        from pathlib import Path
        from tempfile import TemporaryDirectory
        import unittest
        from src.queue.run_next import run_next

        class RunNextTest(unittest.TestCase):
            def test_first_selection(self):
                with TemporaryDirectory() as directory:
                    state = Path(directory) / "state.json"
                    state.write_text(json.dumps({"tasks": [{"id": "TASK-1", "status": "ready"}]}))
                    self.assertEqual(run_next(state), "TASK-1")
        """,
    )
    git(root, "add", ".")
    git(root, "commit", "-qm", "fixture baseline")
    # Preserve an unrelated real MM user change outside task scope.
    write(root, "notes/local.md", "staged user note")
    git(root, "add", "notes/local.md")
    write(root, "notes/local.md", "unstaged continuation of user note")
    run_dir = RUNS / "QR-12"
    run_dir.mkdir(parents=True, exist_ok=True)
    index_bytes = subprocess.run(["git", "-C", str(root), "show", ":notes/local.md"], check=True, capture_output=True).stdout
    packet = f"""# Task Preflight Packet: QR-12

Artifact status: ready
Repository root: {root}
Task brief: docs/tasks/QR-12.md
Task brief SHA-256: {file_sha(root / 'docs/tasks/QR-12.md')}
HEAD: {git(root, 'rev-parse', 'HEAD')}
Exact git status --short:
```
{git(root, 'status', '--short')}
```
Dirty path: notes/local.md
Index SHA-256: {sha(index_bytes)}
Worktree SHA-256: {file_sha(root / 'notes/local.md')}
Ownership: pre-existing user; task overlap: no
Instruction SHA-256: {file_sha(root / 'AGENTS.md')}
Dependency SHA-256: {file_sha(root / '.runner/tracker.json')}
Run policy: {policy}
Run policy SHA-256: {file_sha(policy)}
Packet path: {run_dir / 'preflight.md'} (outside repository)
Allowed paths: src/queue/run_next.py; tests/integration/test_run_next.py
Schema: {SCHEMA}
Result path: {run_dir / 'worker-result.json'}
AC-01 oracle: add and first run `python -m unittest tests.integration.test_run_next.RunNextTest.test_two_consecutive_public_invocations`; it must fail because the second claim is absent, then pass with TASK-1/TASK-2 and persisted state.
AC-02 oracle: empty state remains byte-for-byte unchanged.
CMD-01 targeted: python -m unittest tests.integration.test_run_next.RunNextTest.test_two_consecutive_public_invocations
CMD-02 owning: python -m unittest tests.integration.test_run_next
CMD-03 broader: python -m unittest discover -s tests
Working directory for all commands: {root}
Permissions: only allowed paths and runtime result; no network, install, commit, or other writes.
Next route after complete: task-acceptance-review.
"""
    (run_dir / "preflight.md").write_text(packet, encoding="utf-8")


def scheduler_resume() -> None:
    root = WORK / "scheduler"
    initialize(root)
    policy = install_contracts()
    write(root, "AGENTS.md", "# Fixture rules\n\nPreserve same-thread partial changes and obey the two-strike stop.")
    write(root, "docs/tasks/SCH-09.md", "# SCH-09\n\nArtifact status: ready_for_preflight\nAC-01: two coordinated workers never claim the same job.\nAllowed paths: src/scheduler/claim.py; tests/integration/test_claim.py")
    write(root, "src/scheduler/claim.py", "def claim(job):\n    return job['id']")
    write(root, "tests/integration/test_claim.py", "import unittest\n\nclass ClaimTest(unittest.TestCase):\n    def test_exclusive_claim(self):\n        self.fail('both workers claimed JOB-1')")
    write(root, "tests/__init__.py", "")
    write(root, "tests/integration/__init__.py", "")
    git(root, "add", ".")
    git(root, "commit", "-qm", "fixture baseline")
    baseline_head = git(root, "rev-parse", "HEAD")
    # Same-thread partial diff after two disproved fixes.
    write(root, "src/scheduler/claim.py", "def claim(job):\n    # conditional update attempt remains incomplete\n    return job['id']")
    write(root, "tests/integration/test_claim.py", "import unittest\n\nclass ClaimTest(unittest.TestCase):\n    def test_exclusive_claim(self):\n        self.fail('trace: both workers claimed JOB-1 after conditional update')")
    run_dir = RUNS / "SCH-09"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "preflight.md").write_text(f"""# Task Preflight Packet: SCH-09
Artifact status: ready
Repository root: {root}
Baseline HEAD: {baseline_head}
Baseline status: clean
Allowed paths: src/scheduler/claim.py; tests/integration/test_claim.py
Targeted command: python -m unittest tests.integration.test_claim.ClaimTest.test_exclusive_claim
Run policy: {policy}
Schema: {SCHEMA}
Result path: {run_dir / 'worker-result.json'}
Resume rule: current allowed-path changes are attributed to this implementation thread and recorded in checkpoint.md.
""", encoding="utf-8")
    (run_dir / "checkpoint.md").write_text(f"""# SCH-09 checkpoint
Current status:\n{git(root, 'status', '--short')}
Attempt 1: transaction guard; disproved by trace showing both workers entered before commit.
Attempt 2: conditional update; disproved by trace showing both workers still claimed JOB-1.
Targeted command remains failed. Preserve the partial diff and apply the two-strike stop.
src/scheduler/claim.py SHA-256: {file_sha(root / 'src/scheduler/claim.py')}
tests/integration/test_claim.py SHA-256: {file_sha(root / 'tests/integration/test_claim.py')}
""", encoding="utf-8")


def queue_restaged_stale() -> None:
    queue_task()
    root = WORK / "queue-runner"
    # Replace only the index blob after preflight. Restore identical worktree
    # bytes so `git status --short` remains `MM` and the worktree digest matches.
    worktree_bytes = (root / "notes/local.md").read_bytes()
    write(root, "notes/local.md", "different staged user note after preflight")
    git(root, "add", "notes/local.md")
    (root / "notes/local.md").write_bytes(worktree_bytes)


def api_guided() -> None:
    root = WORK / "api-guided"
    initialize(root)
    write(
        root,
        "AGENTS.md",
        "# Fixture rules\n\nUse guided implementation. Preserve user work, add behavioral tests, and run targeted verification before the broader suite.",
    )
    write(
        root,
        "docs/tasks/API-31.md",
        """
        # API-31 — Reject expired sessions

        Status: ready

        ```yaml
        agent_tier: standard
        reasoning: medium
        review: milestone
        budget: 20 tool calls / 45 minutes / 60k context
        ```

        Outcome: reject expired sessions without changing their token.
        Allowed changes: src/auth/session.py; tests/auth/test_session.py.
        AC-01: an unexpired session remains valid.
        AC-02: an expired session is rejected and its token remains unchanged.
        Targeted: python -m unittest tests.auth.test_session
        Broader: python -m unittest discover -s tests
        No network, dependency installation, commits, or other repository writes.
        """,
    )
    write(root, "src/__init__.py", "")
    write(root, "src/auth/__init__.py", "")
    write(
        root,
        "src/auth/session.py",
        """
        def is_valid(session, now):
            return bool(session.get("token"))
        """,
    )
    write(root, "tests/__init__.py", "")
    write(root, "tests/auth/__init__.py", "")
    write(
        root,
        "tests/auth/test_session.py",
        """
        import unittest

        from src.auth.session import is_valid


        class SessionTest(unittest.TestCase):
            def test_unexpired_session_is_valid(self):
                session = {"token": "abc", "expires_at": 20}
                self.assertTrue(is_valid(session, now=10))
        """,
    )
    git(root, "add", ".")
    git(root, "commit", "-qm", "fixture baseline")


def api_immediate() -> None:
    root = WORK / "api-immediate"
    initialize(root)
    write(
        root,
        "AGENTS.md",
        "# Fixture rules\n\nUse guided implementation. Preserve user work, add behavioral tests, and run the exact targeted command before the owning suite.",
    )
    write(
        root,
        "docs/tasks/API-32.md",
        """
        # API-32 — Reject expired sessions

        Status: ready

        ```yaml
        agent_tier: standard
        reasoning: medium
        review: immediate
        budget: 20 tool calls / 45 minutes / 60k context
        ```

        Outcome: reject expired sessions without changing their token.
        Allowed changes: src/auth/session.py; tests/auth/test_session.py.
        AC-01: an unexpired session remains valid.
        AC-02: an expired session is rejected and its token remains unchanged.
        Targeted: python -m unittest tests.auth.test_session.SessionTest.test_expired_session_is_invalid
        Owning: python -m unittest tests.auth.test_session
        No network, dependency installation, commits, machine result schema, or other repository writes.
        After implementation checks, hand the current bytes to a fresh acceptance reviewer.
        """,
    )
    write(root, "src/__init__.py", "")
    write(root, "src/auth/__init__.py", "")
    write(
        root,
        "src/auth/session.py",
        """
        def is_valid(session, now):
            return bool(session.get("token"))
        """,
    )
    write(root, "tests/__init__.py", "")
    write(root, "tests/auth/__init__.py", "")
    write(
        root,
        "tests/auth/test_session.py",
        """
        import unittest

        from src.auth.session import is_valid


        class SessionTest(unittest.TestCase):
            def test_unexpired_session_is_valid(self):
                session = {"token": "abc", "expires_at": 20}
                self.assertTrue(is_valid(session, now=10))

            def test_expired_session_is_invalid(self):
                session = {"token": "abc", "expires_at": 10}
                self.assertFalse(is_valid(session, now=10))
                self.assertEqual(session["token"], "abc")
        """,
    )
    git(root, "add", ".")
    git(root, "commit", "-qm", "fixture baseline")


def record_correction() -> None:
    root = WORK / "result-record"
    initialize(root)
    write(
        root,
        "AGENTS.md",
        "# Fixture rules\n\nEdit only task-authorized paths. Preserve reviewer regressions and correction handoff state. A fresh reviewer owns final acceptance.",
    )
    original = {
        "task_id": "REC-44",
        "summary": "validated result",
        "files_changed": ["src/result_integrity.py"],
    }
    body = json.dumps(original, sort_keys=True, separators=(",", ":")).encode()
    original["content_digest"] = sha(body)
    exact_bytes = (
        json.dumps(original, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode()
    write(
        root,
        "docs/tasks/REC-44.md",
        """
        # REC-44 — Bind the complete result record

        Status: ready

        ```yaml
        agent_tier: strong
        reasoning: high
        review: immediate
        budget: 18 tool calls / 40 minutes / 50k context
        ```

        This is a correction after `CHANGES_REQUESTED`.
        Outcome: accept a result only when all exact serialized bytes match the independently anchored digest in `authority/result.sha256`.
        Invariant: every result byte is bound; equality of one demonstrated field or internal consistency is insufficient.
        Allowed changes: src/result_integrity.py; tests/test_record_integrity.py.
        Reviewer regression: python -m unittest tests.test_record_integrity.RecordIntegrityTest.test_coherent_mutation_is_rejected
        Owning suite: python -m unittest tests.test_record_integrity
        Aggregate gate: python -m unittest discover -s tests
        Gate ownership: skip the aggregate during correction; the assigned fresh reviewer owns any final aggregate decision.
        Required sibling evidence: add at least one other field mutation or semantically equivalent byte rewrite using the same exact-byte oracle.
        No network, dependency installation, commits, or other repository writes.
        """,
    )
    write(root, "authority/result.json", exact_bytes.decode())
    write(root, "authority/result.sha256", sha(exact_bytes))
    write(root, "src/__init__.py", "")
    write(
        root,
        "src/result_integrity.py",
        """
        import json


        def is_anchored_result(result_bytes, anchor_digest):
            result = json.loads(result_bytes)
            return result.get("task_id") == "REC-44"
        """,
    )
    write(root, "tests/__init__.py", "")
    write(
        root,
        "tests/test_record_integrity.py",
        """
        import hashlib
        import json
        from pathlib import Path
        import unittest

        from src.result_integrity import is_anchored_result


        ROOT = Path(__file__).parents[1]
        ORIGINAL_BYTES = (ROOT / "authority/result.json").read_bytes()
        ANCHOR_DIGEST = (ROOT / "authority/result.sha256").read_text().strip()


        def serialize_coherently(result):
            body = {
                key: value
                for key, value in result.items()
                if key != "content_digest"
            }
            result["content_digest"] = hashlib.sha256(
                json.dumps(
                    body, sort_keys=True, separators=(",", ":")
                ).encode()
            ).hexdigest()
            return (
                json.dumps(result, sort_keys=True, separators=(",", ":"))
                + "\\n"
            ).encode()


        class RecordIntegrityTest(unittest.TestCase):
            def test_original_record_is_accepted(self):
                self.assertTrue(
                    is_anchored_result(ORIGINAL_BYTES, ANCHOR_DIGEST)
                )
        """,
    )
    write(
        root,
        "docs/reviews/REC-44-review.md",
        """
        # REC-44 acceptance review

        Authoritative brief: docs/tasks/REC-44.md
        Preceding verdict: CHANGES_REQUESTED
        Complete finding: the validator checks only `task_id`, so coherent changes to other bytes are accepted.
        Reviewer reproducer: python -m unittest tests.test_record_integrity.RecordIntegrityTest.test_coherent_mutation_is_rejected
        Owning suite: python -m unittest tests.test_record_integrity
        Broad-gate decision: skip aggregate during correction; the assigned fresh reviewer owns the final aggregate decision.

        Coverage ledger:
        - ROW-EXACT-BYTES — failed — coherent summary mutation was accepted.
        - ROW-REPLAY-BOUNDARY — unchecked — fresh reviewer must evaluate; implementer must not claim a verdict.
        """,
    )
    git(root, "add", ".")
    git(root, "commit", "-qm", "fixture baseline")
    test_path = root / "tests/test_record_integrity.py"
    current = test_path.read_text(encoding="utf-8")
    reviewer_regression = (
        "\n\n"
        "    def test_coherent_mutation_is_rejected(self):\n"
        "        mutated = json.loads(ORIGINAL_BYTES)\n"
        '        mutated["summary"] = "coherently changed summary"\n'
        "        mutated_bytes = serialize_coherently(mutated)\n"
        "        self.assertFalse(\n"
        "            is_anchored_result(mutated_bytes, ANCHOR_DIGEST)\n"
        "        )\n"
    )
    test_path.write_text(current.rstrip() + reviewer_regression, encoding="utf-8")


SCENARIOS = {
    "queue-task": queue_task,
    "scheduler-resume": scheduler_resume,
    "queue-restaged-stale": queue_restaged_stale,
    "api-guided": api_guided,
    "api-immediate": api_immediate,
    "record-correction": record_correction,
}

if len(sys.argv) != 2 or sys.argv[1] not in SCENARIOS:
    raise SystemExit(f"usage: {sys.argv[0]} <{'|'.join(SCENARIOS)}>")
RUNS.mkdir(parents=True, exist_ok=True)
SCENARIOS[sys.argv[1]]()
