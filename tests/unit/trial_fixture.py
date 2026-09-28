"""Independent on-disk trial fixtures; never imported by production code."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import yaml

TRIAL = "field-trial"
T0 = "2026-09-22T00:00:00Z"
T1 = "2026-09-22T01:00:00Z"
T2 = "2026-09-22T02:00:00Z"
T3 = "2026-09-22T03:00:00Z"


def git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()


def path(root: Path) -> Path:
    return root / "work-docs" / f"PLAN-{TRIAL}.md"


def write_doc(
    p: Path, meta: dict[str, Any], body: str = "## Evidence\nOriginal user prose.\n"
) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("---\n" + yaml.safe_dump(meta, sort_keys=False) + "---\n" + body)


def read(root: Path) -> dict[str, Any]:
    value: dict[str, Any] = yaml.safe_load(path(root).read_text().split("---", 2)[1])
    return value


def build(root: Path, *, legacy: bool = False) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    git(root, "init", "-q")
    git(root, "config", "user.name", "Test User")
    git(root, "config", "user.email", "test@example.invalid")
    (root / ".gitignore").write_text(".claude/\n.worktrees/\n")
    meta: dict[str, Any] = {"type": "plan", "task_slug": TRIAL}
    body = (
        f"## Trial\n\nActivation: {T0}\nCollector: old-session\n"
        "Collection: collecting\nOutcome: pending\nEnrolled: 0/3\n\nOriginal user prose.\n"
    )
    if not legacy:
        meta["trial"] = {
            "schema_version": 1,
            "activation": T0,
            "policy": {"enabled": True, "revision": "v1", "authority": "conversation:approved"},
            "decisions": [],
            "members": [],
            "recovery": {"state": "pending"},
        }
    write_doc(path(root), meta, body)
    git(root, "add", ".")
    git(root, "commit", "-qm", "fixture baseline")
    return root


def task(
    root: Path,
    slug: str = "a",
    ts: str = T1,
    *,
    terminal: bool = False,
    evidence: bool = True,
    artifact: str = "PLAN",
    ack: bool = False,
) -> None:
    event: dict[str, Any] = {
        "id": f"{slug}-start",
        "trial_id": TRIAL,
        "task_slug": slug,
        "kind": "start",
        "at": ts,
    }
    events = [event] if ack else []
    if evidence:
        events.append(
            {
                "id": f"{slug}-observation",
                "trial_id": TRIAL,
                "task_slug": slug,
                "kind": "observation",
                "at": ts,
                "evidence_refs": [f"conversation:{slug}", f"work-docs/{artifact}-{slug}.md"],
                "decision": "Continue authorized work",
            }
        )
    if terminal:
        events.append(
            {
                "id": f"{slug}-terminal",
                "trial_id": TRIAL,
                "task_slug": slug,
                "kind": "terminal",
                "at": T3,
                "evidence_refs": [f"conversation:{slug}:terminal"],
            }
        )
    write_doc(
        root / "work-docs" / f"{artifact}-{slug}.md",
        {"type": artifact.lower(), "task_slug": slug, "trial_feedback": events},
    )
    ledger = root / ".claude/observability/stage-spans.jsonl"
    ledger.parent.mkdir(parents=True, exist_ok=True)
    with ledger.open("a") as f:
        f.write(
            json.dumps(
                {
                    "schema_version": 1,
                    "event": "start",
                    "stage": "hm:research",
                    "cwd": str(root),
                    "base_root": str(root),
                    "git_branch": None,
                    "task_slug": slug,
                    "ts": ts,
                    "session_id": "A",
                }
            )
            + "\n"
        )


def decision(
    kind: str, payload: dict[str, Any], *, decision_id: str | None = None
) -> dict[str, Any]:
    return {
        "id": decision_id or f"{kind}-1",
        "kind": kind,
        "actor": "user",
        "decided_at": T3,
        "evidence_refs": ["conversation:explicit-answer"],
        "authority": "explicit_user_decision",
        "payload": payload,
    }


def cover(root: Path) -> dict[str, Any]:
    from harness_maker import intent_trial as subject

    s = subject.status(root, TRIAL)
    d = decision(
        "source_review",
        {
            "inventory": s["inventory"],
            "through": s["cutoff"],
            "disposition": "accepted",
            "ordered_tasks": s["candidates"],
            "excluded_tasks": [],
        },
    )
    return subject.record_decision(root, TRIAL, d, expected_revision=s["revision"])
