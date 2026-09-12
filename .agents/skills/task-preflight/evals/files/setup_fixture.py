#!/usr/bin/env python3
"""Create deterministic Git repositories and policy inputs for preflight evals."""

from pathlib import Path
import json
import os
import shutil
import subprocess
import sys
import textwrap


WORK = Path(os.environ.get("EVAL_WORK_ROOT", "/work"))
RUNS = WORK / "task-runs"


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


def commit(root: Path) -> None:
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    subprocess.run(["git", "-C", str(root), "commit", "-qm", "fixture baseline"], check=True)


def common(root: Path, task_id: str) -> None:
    write(root, "AGENTS.md", "# Fixture rules\n\nPreflight is repository-read-only. Runtime artifacts must be written under `/work/task-runs/`, outside this repository.")
    write(root, ".runner/tracker.json", json.dumps({"complete": [task_id]}, indent=2))
    write(root, "pyproject.toml", "[project]\nname = \"eval-fixture\"\nversion = \"0.0.0\"\nrequires-python = \">=3.11\"")
    policy = RUNS / "policies/local-medium-v1.json"
    policy.parent.mkdir(parents=True, exist_ok=True)
    policy.write_text(json.dumps({
        "id": "local-medium-v1",
        "runtime_root": str(RUNS),
        "allow": ["cheap local tests", "runtime artifact writes"],
        "deny": ["network", "dependency installation", "commits", "repository writes during preflight"],
    }, indent=2) + "\n", encoding="utf-8")


def queue_ready() -> None:
    root = WORK / "queue-runner"
    initialize(root)
    common(root, "QR-11")
    write(
        root,
        "docs/tasks/QR-12.md",
        """
        # QR-12 — Repeated queue selection

        Artifact status: ready_for_preflight
        Authority: docs/plan.md#repeated-selection
        Dependency: QR-11 complete in .runner/tracker.json
        Allowed paths: src/queue/run_next.py; tests/integration/test_run_next.py
        AC-01: two public `runner run-next` invocations persist state and claim
        TASK-1 then TASK-2. Empty queues remain unchanged.
        Required helper: tests/helpers/queue_state.py::seed_queue
        Candidate targeted test: test_second_selection[queue with spaces [persisted]]
        Canonical command family: uv run pytest
        """,
    )
    write(root, "docs/plan.md", "# Plan\n\n## repeated-selection\nApprove persisted repeated queue selection through the public CLI.")
    write(
        root,
        "tests/helpers/queue_state.py",
        """
        import json

        def seed_queue(path):
            path.write_text(json.dumps({"tasks": [
                {"id": "TASK-1", "status": "ready"},
                {"id": "TASK-2", "status": "ready"},
            ]}))
        """,
    )
    write(
        root,
        "tests/integration/test_run_next.py",
        """
        import pytest
        from tests.helpers.queue_state import seed_queue

        @pytest.mark.parametrize("case", ["queue with spaces [persisted]"])
        def test_second_selection(tmp_path, case):
            state = tmp_path / "state.json"
            seed_queue(state)
            assert state.exists() and case.endswith("[persisted]")
        """,
    )
    write(root, "tests/__init__.py", "")
    write(root, "tests/helpers/__init__.py", "")
    write(root, "tests/integration/__init__.py", "")
    write(root, "src/queue/run_next.py", "def run_next(state_path):\n    raise NotImplementedError")
    commit(root)
    (RUNS / "QR-12").mkdir(parents=True, exist_ok=True)


def scheduler_missing() -> None:
    root = WORK / "scheduler"
    initialize(root)
    common(root, "SCH-08")
    write(
        root,
        "docs/tasks/SCH-09.md",
        """
        # SCH-09 — Exclusive claim

        Artifact status: ready_for_preflight
        Dependency: SCH-08 complete in .runner/tracker.json
        Allowed paths: src/scheduler/claim.py; tests/integration/test_claim.py
        AC-01: two simultaneous workers cannot claim the same ready job.
        Believed-existing required helper: tests/helpers/concurrent_claims.py
        The oracle must coordinate two real workers at a barrier.
        """,
    )
    write(root, "src/scheduler/claim.py", "def claim(job):\n    return job")
    write(root, "tests/test_claim_unit.py", "def test_placeholder():\n    assert True")
    commit(root)
    (RUNS / "SCH-09").mkdir(parents=True, exist_ok=True)


def api_overlap() -> None:
    root = WORK / "api"
    initialize(root)
    common(root, "API-30")
    write(
        root,
        "docs/tasks/API-31.md",
        """
        # API-31 — Session expiry

        Artifact status: ready_for_preflight
        Dependency: API-30 complete in .runner/tracker.json
        Allowed paths: src/auth/session.py; tests/auth/test_session.py
        AC-01: expired sessions are rejected without refreshing their token.
        Command: python -m unittest tests.auth.test_session
        """,
    )
    write(root, "src/auth/session.py", "def is_valid(session):\n    return True")
    write(root, "tests/auth/test_session.py", "import unittest\n\nclass SessionTest(unittest.TestCase):\n    def test_valid(self):\n        self.assertTrue(True)")
    write(root, "tests/__init__.py", "")
    write(root, "tests/auth/__init__.py", "")
    commit(root)
    # Real MM state: staged user change, followed by different unstaged bytes.
    write(root, "src/auth/session.py", "def is_valid(session):\n    # staged user token-refresh work\n    return bool(session)")
    subprocess.run(["git", "-C", str(root), "add", "src/auth/session.py"], check=True)
    write(root, "src/auth/session.py", "def is_valid(session):\n    # unstaged continuation of user token-refresh work\n    return bool(session.get('token'))")
    (RUNS / "API-31").mkdir(parents=True, exist_ok=True)


def queue_guided() -> None:
    queue_ready()
    root = WORK / "queue-runner"
    brief = root / "docs/tasks/QR-12.md"
    brief.write_text(
        brief.read_text(encoding="utf-8").replace(
            "Artifact status: ready_for_preflight", "Artifact status: ready"
        ),
        encoding="utf-8",
    )
    subprocess.run(["git", "-C", str(root), "add", "docs/tasks/QR-12.md"], check=True)
    subprocess.run(["git", "-C", str(root), "commit", "--amend", "-qm", "fixture baseline"], check=True)


def api_routine() -> None:
    root = WORK / "api-routine"
    initialize(root)
    write(
        root,
        "AGENTS.md",
        "# Fixture rules\n\nPreflight is repository-read-only. Use the exact targeted unittest command in the task brief.",
    )
    write(
        root,
        "docs/tasks/API-07.md",
        """
        # API-07 — Reject expired sessions

        Artifact status: ready
        Standalone readiness route: guided preflight to confirm the local test command.
        Allowed paths: src/auth/session.py; tests/auth/test_session.py
        Dependencies: complete; Python standard library only.
        AC-01: an unexpired session is valid when its expiry is later than the current time.
        Targeted command: PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.auth.test_session.SessionTest.test_unexpired_session_is_valid
        Oracle: the public `is_valid` result is true for expires_at=200 and now=100.
        """,
    )
    write(
        root,
        "src/auth/session.py",
        """
        def is_valid(session, now):
            return session["expires_at"] > now
        """,
    )
    write(
        root,
        "tests/auth/test_session.py",
        """
        import unittest

        from src.auth.session import is_valid


        class SessionTest(unittest.TestCase):
            def test_unexpired_session_is_valid(self):
                session = {"expires_at": 200}

                self.assertTrue(is_valid(session, now=100))
        """,
    )
    write(root, "tests/__init__.py", "")
    write(root, "tests/auth/__init__.py", "")
    commit(root)


SCENARIOS = {
    "api-routine": api_routine,
    "queue-ready": queue_ready,
    "queue-guided": queue_guided,
    "scheduler-missing": scheduler_missing,
    "api-overlap": api_overlap,
}

if len(sys.argv) != 2 or sys.argv[1] not in SCENARIOS:
    raise SystemExit(f"usage: {sys.argv[0]} <{'|'.join(SCENARIOS)}>")
RUNS.mkdir(parents=True, exist_ok=True)
SCENARIOS[sys.argv[1]]()
