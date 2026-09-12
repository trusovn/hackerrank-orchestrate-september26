#!/usr/bin/env python3
"""Create deterministic repositories used by project-direction evals."""

from pathlib import Path
import os
import shutil
import subprocess
import sys
import textwrap

WORK = Path(os.environ.get("EVAL_WORK_ROOT", "/work"))
SKILLS = Path(__file__).resolve().parents[3]


def write(root: Path, relative: str, content: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).strip() + "\n", encoding="utf-8")


def initialize(root: Path) -> None:
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(
        ["git", "-C", str(root), "config", "user.email", "eval@example.invalid"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(root), "config", "user.name", "Eval Fixture"],
        check=True,
    )


def commit(root: Path) -> None:
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    subprocess.run(
        ["git", "-C", str(root), "commit", "-qm", "fixture baseline"],
        check=True,
    )


def initial_direction() -> None:
    root = WORK / "reading-helper"
    initialize(root)
    write(
        root,
        "AGENTS.md",
        """
        # Fixture rules

        Write planning artifacts only under `docs/`. Do not add implementation
        files or choose a software architecture.
        """,
    )
    write(
        root,
        "notes/reading-helper.md",
        """
        # Reading helper notes

        I want a private personal tool that turns articles and my highlights
        into a short weekly reading review. It is for me, on my own computer.
        The first useful result is one real review assembled from five saved
        articles, with links back to every source.

        My priority order is: never invent or lose source attribution; give me
        a useful draft quickly; then make the writing polished. If those
        compete, attribution wins and the tool should leave an explicit gap
        rather than guess.

        Normal: I add articles during the week and ask for a review on Friday.
        Recovery: if processing stops, it should preserve completed source work
        and tell me what remains. Stop: if a claim cannot be tied to a source
        or two sources conflict, ask me rather than smoothing it over.

        It may organize, summarize, and draft. It may not publish, contact
        anyone, buy subscriptions, or silently discard sources. I trust my
        local files and myself. Article text and automated summaries can be
        incomplete or wrong. I decide what is published and any change to
        privacy or source-handling rules.
        """,
    )
    commit(root)


def technical_audit() -> None:
    root = WORK / "orchestrator-audit"
    initialize(root)
    write(
        root,
        "AGENTS.md",
        """
        # Fixture rules

        Write only `docs/project-direction.md`. Treat source documents as
        evidence to audit, not as permission to edit implementation or plans.
        """,
    )
    source = SKILLS / "task-orchestrator" / "docs"
    targets = {
        "direction.md": source / "direction.md",
        "stage-3-mvp-rebaseline.md": source / "stage-3-mvp-rebaseline.md",
        "MVP-2-flow-contract.md":
            source / "stage-3-mvp-tasks" / "MVP-2-flow-contract.md",
    }
    for name, source_path in targets.items():
        destination = root / "docs" / "source" / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, destination)
    commit(root)


def direction_delta() -> None:
    root = WORK / "flow-correction"
    initialize(root)
    write(
        root,
        "AGENTS.md",
        """
        # Fixture rules

        Direction artifacts may be written under `docs/`. Do not edit task
        briefs, implementation, tests, or the current baseline.
        """,
    )
    write(
        root,
        "docs/project-direction.md",
        """
        # Project Direction: Local task flow

        Status: owner-confirmed baseline

        ## Direction at a glance

        - Problem: long agent tasks need safe, understandable continuation.
        - Desired experience: the owner can start, inspect, stop, and resume a
          local task flow without reconstructing agent state.
        - First useful proof: one real task completes through a configurable
          local flow and can recover once after interruption.

        ## Priorities and conflict rule

        1. Keep the owner in control.
        2. Preserve useful progress across interruptions.
        3. Automate routine transitions.

        Conflict rule: owner control and an understandable stop beat automatic
        continuation.

        ## Scope

        In scope: one trusted local owner and fallible agent outputs.
        Not in scope: shared hosting, hostile collaborators, or remote control.

        ## Boundaries

        The owner and local run directory are trusted. Agent outputs can be
        mistaken. The system must stop when requested direction is ambiguous.
        """,
    )
    write(
        root,
        "docs/tasks/FLOW-2.md",
        """
        # FLOW-2 — Protect flow records

        Proposed requirement: use signed records and an external trust anchor
        so a malicious local user cannot rewrite flow history or permissions.
        The implementation should reject any history lacking cryptographic
        proof and migrate all current records.
        """,
    )
    commit(root)


SCENARIOS = {
    "direction-delta": direction_delta,
    "initial-direction": initial_direction,
    "technical-audit": technical_audit,
}

if len(sys.argv) != 2 or sys.argv[1] not in SCENARIOS:
    raise SystemExit(f"usage: {sys.argv[0]} <{'|'.join(SCENARIOS)}>")
SCENARIOS[sys.argv[1]]()
