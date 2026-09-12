#!/usr/bin/env python3
"""Create staged implementations and review artifacts for acceptance evals."""

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


def policy(authorized_test_path: str | None = None) -> Path:
    path = RUNS / "policies/local-review-v1.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    allow = ["cheap local tests", "disposable probes outside repository", "one acceptance report"]
    deny = ["source/test edits", "network", "dependency installation", "commits", "tracker updates"]
    if authorized_test_path is not None:
        allow.append(f"post-verdict tests_only_reproducer write to {authorized_test_path}")
        deny[0] = "source edits and test edits outside the explicitly authorized path"
    path.write_text(json.dumps({
        "id": "local-review-v1",
        "runtime_root": str(RUNS),
        "allow": allow,
        "deny": deny,
    }, indent=2) + "\n", encoding="utf-8")
    return path


def worker(run_dir: Path, task_id: str, changed: list[str], commands: list[str]) -> None:
    data = {
        "status": "complete",
        "task_id": task_id,
        "summary": f"bounded-task-implementer submitted {task_id} for independent review",
        "files_changed": changed,
        "verification": [{"command": command, "outcome": "passed", "summary": "worker-observed pass"} for command in commands],
        "decisions": [],
        "questions": [],
        "risks": [],
        "next_action": "Run task-acceptance-review.",
    }
    (run_dir / "worker-result.json").write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def queue_defect(*, authorize_reproducer: bool = False) -> None:
    root = WORK / "queue-runner"
    initialize(root)
    test_path = "tests/integration/test_run_next.py" if authorize_reproducer else None
    run_policy = policy(test_path)
    if authorize_reproducer:
        fixture_rule = (
            "# Fixture rules\n\nAcceptance is read-only until a fixed "
            "`CHANGES_REQUESTED` verdict. This invocation may then use "
            "`tests_only_reproducer` only in "
            "`tests/integration/test_run_next.py`. Production remains read-only."
        )
    else:
        fixture_rule = f"# Fixture rules\n\nAcceptance is read-only. Write reports and disposable probe state only under `{RUNS}/`."
    write(root, "AGENTS.md", fixture_rule)
    write(root, "docs/tasks/QR-12.md", "# QR-12\n\nArtifact status: ready_for_preflight\nAC-01: two consecutive public invocations persist state and claim TASK-1 then TASK-2.\nAllowed paths: src/queue/run_next.py; tests/integration/test_run_next.py")
    write(root, "src/__init__.py", "")
    write(root, "src/queue/__init__.py", "")
    write(root, "src/queue/run_next.py", "def run_next(path):\n    raise NotImplementedError")
    write(root, "tests/__init__.py", "")
    write(root, "tests/integration/__init__.py", "")
    write(root, "tests/integration/test_run_next.py", "import unittest\n\nclass Placeholder(unittest.TestCase):\n    def test_placeholder(self):\n        self.assertTrue(True)")
    git(root, "add", ".")
    git(root, "commit", "-qm", "preflight baseline")
    head = git(root, "rev-parse", "HEAD")
    run_dir = RUNS / "QR-12"
    run_dir.mkdir(parents=True, exist_ok=True)
    packet = f"""# Task Preflight Packet: QR-12
Artifact status: ready
Repository root: {root}
Task brief: docs/tasks/QR-12.md
Task brief SHA-256: {file_sha(root / 'docs/tasks/QR-12.md')}
Baseline HEAD: {head}
Baseline exact git status --short: clean
Allowed paths: src/queue/run_next.py; tests/integration/test_run_next.py
Run policy: {run_policy}
Report path: {run_dir / 'acceptance.md'}
AC-01 requires an independent two-invocation public-entry probe in disposable state.
Legacy finding: trace guards that compare against any initially running task.
"""
    (run_dir / "preflight.md").write_text(packet, encoding="utf-8")
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
            def test_first_invocation_and_state(self):
                with TemporaryDirectory() as directory:
                    state = Path(directory) / "state.json"
                    state.write_text(json.dumps({"tasks": [{"id": "TASK-1", "status": "ready"}]}))
                    self.assertEqual(run_next(state), "TASK-1")
                    self.assertEqual(json.loads(state.read_text())["tasks"][0]["status"], "running")
        """,
    )
    worker(run_dir, "QR-12", ["src/queue/run_next.py", "tests/integration/test_run_next.py"], ["python -m unittest tests.integration.test_run_next"])


def queue_defect_reproducer() -> None:
    queue_defect(authorize_reproducer=True)


def exporter_accept() -> None:
    root = WORK / "exporter"
    initialize(root)
    run_policy = policy()
    write(root, "AGENTS.md", "# Fixture rules\n\nAcceptance is read-only. Preserve user notes and use disposable state outside the repository.")
    write(root, "docs/tasks/EXP-08.md", "# EXP-08\n\nArtifact status: ready_for_preflight\nAC-01: `exportctl resume` appends remaining rows after checkpoint.\nAC-02: retry adds no duplicate rows.\nAllowed paths: src/exporter/resume.py; tests/integration/test_resume.py")
    write(root, "notes/local.md", "baseline note")
    write(root, "src/__init__.py", "")
    write(root, "src/exporter/__init__.py", "")
    write(root, "src/exporter/resume.py", "def resume(*args):\n    raise NotImplementedError")
    write(root, "tests/__init__.py", "")
    write(root, "tests/integration/__init__.py", "")
    write(root, "tests/integration/test_resume.py", "import unittest\n\nclass Placeholder(unittest.TestCase):\n    def test_placeholder(self):\n        self.assertTrue(True)")
    git(root, "add", ".")
    git(root, "commit", "-qm", "preflight baseline")
    # Pre-existing MM user work is part of the preflight baseline.
    write(root, "notes/local.md", "staged user note")
    git(root, "add", "notes/local.md")
    write(root, "notes/local.md", "unstaged continuation of user note")
    index_bytes = subprocess.run(["git", "-C", str(root), "show", ":notes/local.md"], check=True, capture_output=True).stdout
    baseline_status = git(root, "status", "--short")
    run_dir = RUNS / "EXP-08"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "preflight.md").write_text(f"""# Task Preflight Packet: EXP-08
Artifact status: ready
Repository root: {root}
Task brief: docs/tasks/EXP-08.md
Task brief SHA-256: {file_sha(root / 'docs/tasks/EXP-08.md')}
Baseline HEAD: {git(root, 'rev-parse', 'HEAD')}
Baseline exact git status --short:\n{baseline_status}
Pre-existing path: notes/local.md
Index SHA-256: {sha(index_bytes)}
Worktree SHA-256: {file_sha(root / 'notes/local.md')}
Ownership: user; task overlap: no
Allowed paths: src/exporter/resume.py; tests/integration/test_resume.py
Run policy: {run_policy}
Report path: {run_dir / 'acceptance.md'}
Targeted: python -m unittest tests.integration.test_resume
Public probe: python -m src.exporter.resume INPUT CHECKPOINT OUTPUT
""", encoding="utf-8")
    write(
        root,
        "src/exporter/resume.py",
        """
        import argparse
        import json
        from pathlib import Path

        def resume(input_path, checkpoint_path, output_path):
            rows = json.loads(Path(input_path).read_text())
            checkpoint = int(Path(checkpoint_path).read_text()) if Path(checkpoint_path).exists() else 0
            existing = Path(output_path).read_text().splitlines() if Path(output_path).exists() else []
            existing.extend(rows[checkpoint:])
            Path(output_path).write_text("\\n".join(existing) + ("\\n" if existing else ""))
            Path(checkpoint_path).write_text(str(len(rows)))

        if __name__ == "__main__":
            parser = argparse.ArgumentParser(prog="exportctl resume")
            parser.add_argument("input")
            parser.add_argument("checkpoint")
            parser.add_argument("output")
            args = parser.parse_args()
            resume(args.input, args.checkpoint, args.output)
        """,
    )
    write(
        root,
        "tests/integration/test_resume.py",
        """
        import json
        from pathlib import Path
        from tempfile import TemporaryDirectory
        import unittest
        from src.exporter.resume import resume

        class ResumeTest(unittest.TestCase):
            def test_resume_and_retry_are_idempotent(self):
                with TemporaryDirectory() as directory:
                    root = Path(directory)
                    source, checkpoint, output = root / "in.json", root / "checkpoint", root / "out.csv"
                    source.write_text(json.dumps(["one", "same", "same"]))
                    resume(source, checkpoint, output)
                    resume(source, checkpoint, output)
                    self.assertEqual(
                        output.read_text().splitlines(), ["one", "same", "same"]
                    )
        """,
    )
    worker(run_dir, "EXP-08", ["src/exporter/resume.py", "tests/integration/test_resume.py"], ["python -m unittest tests.integration.test_resume", "python -m unittest discover -s tests"])


def scheduler_inconclusive() -> None:
    root = WORK / "scheduler"
    initialize(root)
    run_policy = policy()
    write(root, "AGENTS.md", "# Fixture rules\n\nAcceptance may not invent missing concurrency infrastructure or use live services.")
    write(root, "docs/tasks/SCH-09.md", "# SCH-09\n\nArtifact status: ready_for_preflight\nAC-01: two coordinated workers cannot claim the same job.\nRequired helper: tests/helpers/concurrent_claims.py")
    write(root, "src/scheduler/claim.py", "def claim(job):\n    return job['id']")
    write(root, "tests/helpers/concurrent_claims.py", "def coordinated_claims(claim):\n    return claim(), claim()")
    write(root, "tests/test_claim.py", "import unittest\n\nclass ClaimTest(unittest.TestCase):\n    def test_unit(self):\n        self.assertTrue(True)")
    git(root, "add", ".")
    git(root, "commit", "-qm", "preflight baseline")
    helper_digest = file_sha(root / "tests/helpers/concurrent_claims.py")
    run_dir = RUNS / "SCH-09"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "preflight.md").write_text(f"""# Task Preflight Packet: SCH-09
Artifact status: ready
Repository root: {root}
Task brief: docs/tasks/SCH-09.md
Baseline HEAD: {git(root, 'rev-parse', 'HEAD')}
Baseline status: clean
Required helper: tests/helpers/concurrent_claims.py
Helper SHA-256: {helper_digest}
Allowed paths: src/scheduler/claim.py; tests/test_claim.py
Run policy: {run_policy}
Report path: {run_dir / 'acceptance.md'}
""", encoding="utf-8")
    write(root, "src/scheduler/claim.py", "def claim(job):\n    # worker implementation\n    return job['id']")
    (root / "tests/helpers/concurrent_claims.py").unlink()
    worker(run_dir, "SCH-09", ["src/scheduler/claim.py"], ["python -m unittest tests.test_claim"])


def exporter_restaged_stale() -> None:
    exporter_accept()
    root = WORK / "exporter"
    # Preserve short status and worktree bytes while changing only the index
    # blob recorded as pre-existing user work by preflight.
    worktree_bytes = (root / "notes/local.md").read_bytes()
    write(root, "notes/local.md", "different staged user note after preflight")
    git(root, "add", "notes/local.md")
    (root / "notes/local.md").write_bytes(worktree_bytes)


def ledger_defects() -> None:
    root = WORK / "ledger-runner"
    initialize(root)
    write(
        root,
        "AGENTS.md",
        "# Fixture rules\n\nReview is read-only. Use guided acceptance and report findings inline.",
    )
    write(
        root,
        "docs/tasks/LED-04.md",
        """
        # LED-04 — Enforce ledger coherence

        Status: ready
        Allowed paths: src/ledger/state.py; tests/test_state.py.
        AC-01: a ready run has no running task and its ready set equals every
        dependency-ready task.
        AC-02: a running run has exactly one running selected task and its
        active attempt is that task's latest attempt.
        AC-03: a stopped run has no running task; revisions reject booleans;
        completed_task_ids is an array.
        Review: immediate.
        """,
    )
    write(root, "src/__init__.py", "")
    write(root, "src/ledger/__init__.py", "")
    write(root, "src/ledger/state.py", "def validate_ledger(ledger):\n    raise NotImplementedError")
    write(root, "tests/__init__.py", "")
    write(root, "tests/test_state.py", "import unittest\n\nclass Placeholder(unittest.TestCase):\n    def test_placeholder(self):\n        self.assertTrue(True)")
    git(root, "add", ".")
    git(root, "commit", "-qm", "review baseline")
    write(
        root,
        "src/ledger/state.py",
        """
        def validate_ledger(ledger):
            if not isinstance(ledger.get("revision"), int):
                raise ValueError("revision")

            tasks = ledger["tasks"]
            selected_id = ledger.get("selected_task_id")
            selected = next((task for task in tasks if task["id"] == selected_id), None)

            if ledger["status"] == "ready":
                if selected is not None and selected["status"] == "running":
                    raise ValueError("selected task running")
                if not any(task["status"] == "ready" for task in tasks):
                    raise ValueError("no ready task")
            elif ledger["status"] == "running":
                if selected is None or selected["status"] != "running":
                    raise ValueError("selected task not running")
                if ledger.get("active_attempt_id") not in selected["attempt_ids"]:
                    raise ValueError("unknown active attempt")
            elif ledger["status"] == "stopped":
                if selected is not None and selected["status"] == "running":
                    raise ValueError("selected task running")

            return True
        """,
    )
    write(
        root,
        "tests/test_state.py",
        """
        import unittest

        from src.ledger.state import validate_ledger


        class LedgerTest(unittest.TestCase):
            def test_valid_running_ledger(self):
                ledger = {
                    "revision": 2,
                    "status": "running",
                    "selected_task_id": "TASK-1",
                    "active_attempt_id": "A-2",
                    "completed_task_ids": [],
                    "tasks": [
                        {"id": "TASK-1", "status": "running", "attempt_ids": ["A-1", "A-2"]},
                        {"id": "TASK-2", "status": "initialized", "attempt_ids": []},
                    ],
                }
                self.assertTrue(validate_ledger(ledger))
        """,
    )


def authored_production_self_check() -> None:
    root = WORK / "authored-production"
    initialize(root)
    write(
        root,
        "AGENTS.md",
        "# Fixture rules\n\nThe requested implementation edit is authorized. "
        "Any acceptance check in the authoring session is self-check only.",
    )
    write(
        root,
        "docs/tasks/PRICE-02.md",
        """
        # PRICE-02 — Add the approved service fee

        Status: ready
        Allowed paths: src/pricing.py.
        AC-01: `total(100)` returns `110.0`.
        Review: immediate and independent after implementation.
        """,
    )
    write(root, "src/pricing.py", "def total(subtotal):\n    return subtotal")
    write(
        root,
        "tests/test_pricing.py",
        """
        import unittest

        from src.pricing import total


        class PricingTest(unittest.TestCase):
            def test_approved_service_fee(self):
                self.assertEqual(total(100), 110.0)
        """,
    )
    write(root, "src/__init__.py", "")
    write(root, "tests/__init__.py", "")
    git(root, "add", ".")
    git(root, "commit", "-qm", "fixture baseline")


def workflow_matrix_defects() -> None:
    root = WORK / "workflow-runner"
    initialize(root)
    write(root, "AGENTS.md", "# Fixture rules\n\nAcceptance is read-only. Use only disposable copies of case state for probes.")
    write(
        root,
        "docs/tasks/WF-21.md",
        """
        # WF-21 — Validate persisted workflow state before execution

        Status: ready
        Allowed paths: src/workflow/runner.py; tests/test_contract_probes.py.
        Public entry: `python -m src.workflow.runner STATE AUTHORITY`.
        Owning suite: `python -m unittest discover -s tests`.

        Coverage rows:
        - WF-TAMPER: prompt and model must match the independently stored
          authority hashes. Coherent changes to both fields and their mutable
          manifest hashes must be rejected before execution.
        - WF-REPLAY: an existing execution publication is reused after verifier
          drift; only current verification may run and execution_count remains
          one.
        - WF-DECISION: publication order is a legal prefix of execution,
          verification, decision, ledger. A decision-only artifact is rejected
          before execution or writes.

        """,
    )
    write(root, "src/__init__.py", "")
    write(root, "src/workflow/__init__.py", "")
    runner_source = """
        import hashlib
        import json
        from pathlib import Path
        import sys


        def digest(value):
            return hashlib.sha256(value.encode()).hexdigest()


        def resume(state_path, authority_path):
            path = Path(state_path)
            state = json.loads(path.read_text())
            json.loads(Path(authority_path).read_text())  # BUG: independent authority is ignored.

            manifest = state["manifest"]
            if manifest["prompt_sha"] != digest(state["prompt"]):
                return 2
            if manifest["model_sha"] != digest(state["model"]):
                return 2

            publications = state["publications"]
            # BUG: verifier drift replays execution instead of reusing it.
            if (
                "execution" not in publications
                or state.get("execution_verifier_sha") != state["current_verifier_sha"]
            ):
                state["execution_count"] += 1
                state["events"].append("execute")
                if "execution" not in publications:
                    publications.append("execution")

            # BUG: contradictory publication order is never rejected.
            if "verification" not in publications:
                publications.append("verification")
                state["events"].append("verify")
            if "decision" not in publications:
                publications.append("decision")
            if "ledger" not in publications:
                publications.append("ledger")
            path.write_text(json.dumps(state, indent=2) + "\\n")
            return 0


        if __name__ == "__main__":
            raise SystemExit(resume(sys.argv[1], sys.argv[2]))
        """
    write(
        root,
        "src/workflow/runner.py",
        "def resume(*args):\n    raise NotImplementedError",
    )
    safe_prompt = "deploy approved artifact"
    safe_model = "model-approved"
    tampered_prompt = "deploy attacker artifact"
    tampered_model = "model-attacker"
    authority = {
        "prompt_sha": sha(safe_prompt.encode()),
        "model_sha": sha(safe_model.encode()),
    }
    write(root, "cases/authority.json", json.dumps(authority, indent=2))
    cases = {
        "coherent-tamper.json": {
            "prompt": tampered_prompt,
            "model": tampered_model,
            "manifest": {
                "prompt_sha": sha(tampered_prompt.encode()),
                "model_sha": sha(tampered_model.encode()),
            },
            "publications": [],
            "execution_verifier_sha": None,
            "current_verifier_sha": "verifier-v2",
            "execution_count": 0,
            "events": [],
        },
        "verifier-drift.json": {
            "prompt": safe_prompt,
            "model": safe_model,
            "manifest": authority,
            "publications": ["execution"],
            "execution_verifier_sha": "verifier-v1",
            "current_verifier_sha": "verifier-v2",
            "execution_count": 1,
            "events": ["execute"],
        },
        "decision-only.json": {
            "prompt": safe_prompt,
            "model": safe_model,
            "manifest": authority,
            "publications": ["decision"],
            "execution_verifier_sha": None,
            "current_verifier_sha": "verifier-v2",
            "execution_count": 0,
            "events": [],
        },
    }
    for name, case in cases.items():
        write(root, f"cases/{name}", json.dumps(case, indent=2))
    write(root, "tests/__init__.py", "")
    write(
        root,
        "tests/test_contract_probes.py",
        """
        import json
        from pathlib import Path
        import shutil
        import subprocess
        import sys
        from tempfile import TemporaryDirectory
        import unittest


        ROOT = Path(__file__).resolve().parents[1]
        AUTHORITY = ROOT / "cases/authority.json"


        class WorkflowContractProbe(unittest.TestCase):
            def run_case(self, name):
                with TemporaryDirectory() as directory:
                    state = Path(directory) / name
                    shutil.copyfile(ROOT / "cases" / name, state)
                    before = state.read_bytes()
                    completed = subprocess.run(
                        [sys.executable, "-m", "src.workflow.runner", str(state), str(AUTHORITY)],
                        cwd=ROOT,
                        capture_output=True,
                        text=True,
                    )
                    return completed, before, json.loads(state.read_text())

            def test_wf_tamper_rejects_coherent_prompt_and_model_change(self):
                completed, before, state = self.run_case("coherent-tamper.json")
                self.assertNotEqual(completed.returncode, 0)
                self.assertEqual(state["execution_count"], 0)
                self.assertEqual(json.loads(before), state)

            def test_wf_replay_reuses_execution_after_verifier_drift(self):
                completed, before, state = self.run_case("verifier-drift.json")
                self.assertEqual(completed.returncode, 0)
                self.assertEqual(state["execution_count"], 1)
                self.assertEqual(state["events"].count("execute"), 1)

            def test_wf_decision_rejects_decision_only_artifact(self):
                completed, before, state = self.run_case("decision-only.json")
                self.assertNotEqual(completed.returncode, 0)
                self.assertEqual(state["execution_count"], 0)
                self.assertEqual(json.loads(before), state)
        """,
    )
    git(root, "add", ".")
    git(root, "commit", "-qm", "review baseline")
    # The submitted implementation is intentionally defective but scoped.
    write(root, "src/workflow/runner.py", runner_source)
    run_dir = RUNS / "WF-21"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "review-continuation.md").write_text(
        """Review continuation:
- Iteration / current byte identity: prior review; bytes have since changed
- Coverage rows: WF-TAMPER=pass; WF-REPLAY=fail; WF-DECISION=unchecked
- Finding IDs: WF-F1
- Reviewer regressions: tests.test_contract_probes.WorkflowContractProbe.test_wf_replay_reuses_execution_after_verifier_drift
- Broad gate: not run after targeted failure
- Next: continue independent review of the current bytes
""",
        encoding="utf-8",
    )


def process_cleanup_defects() -> None:
    root = WORK / "process-runner"
    initialize(root)
    write(root, "AGENTS.md", "# Fixture rules\n\nUse bounded process probes. Every probe must clean its process group in `finally`.")
    write(
        root,
        "docs/tasks/PROC-17.md",
        """
        # PROC-17 — Clean an entire timed-out process tree

        Status: ready
        Allowed paths: src/process_runner.py; tests/test_cleanup_contract.py.
        Invariant PROC-CLEANUP: after timeout or leader exit, no descendant may
        remain alive or retain inherited output pipes.

        Material cases:
        - PROC-RESIST: a descendant ignores SIGTERM after the leader times out.
        - PROC-PIPE: the leader exits while a descendant holds inherited pipes.
        - PROC-RACE: descendant visibility changes as the leader exits.

        Probes use file events and bounded polling; arbitrary sleeps and
        unbounded waits are prohibited.
        """,
    )
    write(root, "src/__init__.py", "")
    runner_source = """
        import subprocess


        def run_command(command, timeout=0.25):
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                start_new_session=True,
            )
            try:
                return process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                # BUG: only the leader is terminated; descendants and inherited
                # pipes are not handled, and an exited leader skips cleanup.
                if process.poll() is None:
                    process.terminate()
                return process.wait(timeout=0.5)
        """
    write(
        root,
        "src/process_runner.py",
        "def run_command(*args, **kwargs):\n    raise NotImplementedError",
    )
    write(
        root,
        "fixtures/process_tree.py",
        """
        from pathlib import Path
        import os
        import signal
        import subprocess
        import sys
        import threading
        import time


        def wait_path(path, timeout=2.0):
            deadline = time.monotonic() + timeout
            event = threading.Event()
            while time.monotonic() < deadline:
                if path.exists():
                    return
                event.wait(0.01)
            raise TimeoutError(path)


        state = Path(sys.argv[2])
        state.mkdir(parents=True, exist_ok=True)

        if sys.argv[1] == "child":
            signal.signal(signal.SIGTERM, signal.SIG_IGN)
            (state / "child.pid").write_text(str(os.getpid()))
            (state / "child.ready").write_text("ready")
            threading.Event().wait(5.0)
            raise SystemExit(0)

        (state / "parent.pid").write_text(str(os.getpid()))
        scenario = sys.argv[1]
        child_command = [sys.executable, __file__, "child", str(state)]

        if scenario == "resistant":
            subprocess.Popen(child_command)
            wait_path(state / "child.ready")
            (state / "parent.ready").write_text("ready")
            threading.Event().wait(5.0)
        elif scenario == "pipe-holder":
            subprocess.Popen(child_command)
            wait_path(state / "child.ready")
        elif scenario == "visibility-race":
            (state / "parent.ready").write_text("ready")
            wait_path(state / "release")
            subprocess.Popen(child_command)
            wait_path(state / "child.ready")
        else:
            raise SystemExit(f"unknown scenario: {scenario}")
        """,
    )
    write(root, "tests/__init__.py", "")
    write(
        root,
        "tests/test_cleanup_contract.py",
        """
        from pathlib import Path
        import os
        import signal
        import subprocess
        import sys
        from tempfile import TemporaryDirectory
        import threading
        import time
        import unittest

        from src import process_runner


        ROOT = Path(__file__).resolve().parents[1]
        TREE = ROOT / "fixtures/process_tree.py"


        def wait_path(path, timeout=2.0):
            deadline = time.monotonic() + timeout
            event = threading.Event()
            while time.monotonic() < deadline:
                if path.exists():
                    return
                event.wait(0.01)
            raise AssertionError(f"timed out waiting for {path}")


        REAL_POPEN = subprocess.Popen


        def is_alive(pid):
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                return False
            return True


        def group_is_alive(pgid):
            try:
                os.killpg(pgid, 0)
            except ProcessLookupError:
                return False
            return True


        def wait_until(predicate, description, timeout=2.0):
            deadline = time.monotonic() + timeout
            event = threading.Event()
            while time.monotonic() < deadline:
                if predicate():
                    return
                event.wait(0.01)
            raise AssertionError(f"cleanup timed out waiting for {description}")


        def run_tracked(command, processes):
            def tracked_popen(*args, **kwargs):
                process = REAL_POPEN(*args, **kwargs)
                processes.append(process)
                return process

            original = process_runner.subprocess.Popen
            process_runner.subprocess.Popen = tracked_popen
            try:
                return process_runner.run_command(command)
            finally:
                process_runner.subprocess.Popen = original


        def cleanup_group(state, processes):
            parent_path = state / "parent.pid"
            parent_pid = (
                int(parent_path.read_text())
                if parent_path.exists()
                else processes[0].pid if processes else None
            )
            child_path = state / "child.pid"
            child_pid = int(child_path.read_text()) if child_path.exists() else None

            if parent_pid is not None:
                try:
                    os.killpg(parent_pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            if child_pid is not None:
                try:
                    os.kill(child_pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass

            for process in processes:
                try:
                    process.communicate(timeout=2.0)
                except subprocess.TimeoutExpired as error:
                    for stream_name in ("stdout", "stderr"):
                        stream = getattr(process, stream_name)
                        if stream is not None:
                            stream.close()
                    raise AssertionError(
                        "cleanup timed out waiting for inherited output pipes to close"
                    ) from error
                for stream_name in ("stdout", "stderr"):
                    stream = getattr(process, stream_name)
                    if stream is not None and not stream.closed:
                        raise AssertionError(
                            f"cleanup left {stream_name} pipe open for pid {process.pid}"
                        )

            if parent_pid is not None:
                wait_until(
                    lambda: not group_is_alive(parent_pid),
                    f"process group {parent_pid} to disappear",
                )
                wait_until(
                    lambda: not is_alive(parent_pid),
                    f"leader pid {parent_pid} to disappear",
                )
            if child_pid is not None:
                wait_until(
                    lambda: not is_alive(child_pid),
                    f"descendant pid {child_pid} to disappear",
                )


        class CleanupContractProbe(unittest.TestCase):
            def command(self, scenario, state):
                return [sys.executable, str(TREE), scenario, str(state)]

            def assert_child_cleaned(self, state):
                wait_path(state / "child.pid")
                self.assertFalse(is_alive(int((state / "child.pid").read_text())))

            def test_proc_resist_kills_resistant_descendant(self):
                with TemporaryDirectory() as directory:
                    state = Path(directory)
                    processes = []
                    try:
                        run_tracked(self.command("resistant", state), processes)
                        self.assert_child_cleaned(state)
                    finally:
                        cleanup_group(state, processes)

            def test_proc_pipe_cleans_holder_after_leader_exit(self):
                with TemporaryDirectory() as directory:
                    state = Path(directory)
                    processes = []
                    try:
                        run_tracked(self.command("pipe-holder", state), processes)
                        self.assert_child_cleaned(state)
                    finally:
                        cleanup_group(state, processes)

            def test_proc_race_rechecks_descendant_after_leader_exit(self):
                with TemporaryDirectory() as directory:
                    state = Path(directory)
                    result = {}
                    processes = []
                    thread = threading.Thread(
                        target=lambda: result.setdefault(
                            "code",
                            run_tracked(
                                self.command("visibility-race", state), processes
                            ),
                        )
                    )
                    try:
                        thread.start()
                        wait_path(state / "parent.ready")
                        (state / "release").write_text("go")
                        thread.join(timeout=2.0)
                        self.assertFalse(thread.is_alive(), "runner did not finish within bound")
                        self.assertEqual(result.get("code"), 0)
                        self.assert_child_cleaned(state)
                    finally:
                        cleanup_group(state, processes)
                        thread.join(timeout=1.0)
                        self.assertFalse(
                            thread.is_alive(), "runner thread survived fixture cleanup"
                        )
        """,
    )
    git(root, "add", ".")
    git(root, "commit", "-qm", "review baseline")
    write(root, "src/process_runner.py", runner_source)


SCENARIOS = {
    "queue-defect": queue_defect,
    "queue-defect-reproducer": queue_defect_reproducer,
    "exporter-accept": exporter_accept,
    "scheduler-inconclusive": scheduler_inconclusive,
    "exporter-restaged-stale": exporter_restaged_stale,
    "ledger-defects": ledger_defects,
    "authored-production-self-check": authored_production_self_check,
    "workflow-matrix-defects": workflow_matrix_defects,
    "process-cleanup-defects": process_cleanup_defects,
}

if len(sys.argv) != 2 or sys.argv[1] not in SCENARIOS:
    raise SystemExit(f"usage: {sys.argv[0]} <{'|'.join(SCENARIOS)}>")
RUNS.mkdir(parents=True, exist_ok=True)
SCENARIOS[sys.argv[1]]()
