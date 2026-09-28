"""Repository-local, session-independent collection for activated intent trials.

The trial PLAN is the only authoritative record. Source inventories are bounded to
Git-registered worktrees; human decisions enter only through record_decision.
"""

from __future__ import annotations

import contextlib
import copy
import hashlib
import json
import os
import re
import subprocess
import tempfile
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from harness_maker.worktree import _flock_lock

_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
_START = re.compile(r"^Activation:\s*(\S+)", re.M)
_OWNER = re.compile(r"^Collector:\s*(.+)$", re.M)
_HISTORY_START = "<!-- intent-trial:history:start -->\n"
_HISTORY_END = "<!-- intent-trial:history:end -->"
_ROW = re.compile(
    r"^\|\s*(\d+)\s*\|\s*([^|]+)\|\s*([^|]+)\|\s*([^|]+)\|\s*([^|]+)\|\s*([^|]+)\|", re.M
)
_ACTION = {
    "no_trial": "none",
    "no_candidates": "none",
    "source_incomplete": "collect_missing_evidence",
    "source_conflict": "resolve_source_conflict",
    "order_conflict": "resolve_order_conflict",
    "policy_revision_required": "request_policy_decision",
    "authority_required": "request_policy_decision",
    "source_review_required": "request_bounded_source_review",
    "awaiting_reconciliation": "reconcile",
    "awaiting_user_assessment": "request_user_assessment",
    "observation_window_open": "wait_until_window_closes",
    "lock_busy": "retry_next_invocation",
    "unsupported_lock": "retry_on_supported_storage",
    "lifecycle_pending": "resolve_pending_lifecycle",
}


def _git(root: Path, *args: str) -> str:
    try:
        process = subprocess.run(
            ["git", *args], cwd=root, text=True, capture_output=True, check=True, timeout=5
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise OSError("git operation failed") from exc
    return process.stdout.strip()


def _head_bytes(root: Path, relative: str) -> bytes | None:
    try:
        process = subprocess.run(
            ["git", "show", f"HEAD:{relative}"],
            cwd=root,
            capture_output=True,
            check=True,
            timeout=5,
        )
    except subprocess.CalledProcessError as exc:
        # A path absent from HEAD, or no commit yet: either way there is no committed version.
        if exc.returncode == 128 and (
            b"does not exist" in exc.stderr
            or b"not in 'HEAD'" in exc.stderr
            or b"invalid object name 'HEAD'" in exc.stderr
        ):
            return None
        raise OSError("git show failed") from exc
    except subprocess.TimeoutExpired as exc:
        raise OSError("git show timed out") from exc
    return process.stdout


def _roots(root: Path) -> tuple[Path, list[Path]]:
    try:
        output = _git(root, "worktree", "list", "--porcelain")
    except OSError as exc:
        raise RuntimeError("source discovery failed") from exc
    paths = [
        Path(line.removeprefix("worktree ")).resolve()
        for line in output.splitlines()
        if line.startswith("worktree ")
    ]
    return (paths[0], paths) if paths else (root.resolve(), [root.resolve()])


def _path(root: Path, trial_id: str) -> Path:
    if not _ID.fullmatch(trial_id) or ".." in trial_id:
        raise ValueError("invalid trial id")
    return root / "work-docs" / f"PLAN-{trial_id}.md"


def _split(content: bytes) -> tuple[dict[str, Any], str]:
    text = content.decode("utf-8")
    pieces = text.split("---", 2)
    if len(pieces) < 3 or pieces[0] != "":
        raise ValueError("invalid trial frontmatter")
    try:
        meta = yaml.safe_load(pieces[1])
    except yaml.YAMLError as exc:
        raise ValueError("invalid trial frontmatter") from exc
    if not isinstance(meta, dict):
        raise ValueError("invalid trial frontmatter")
    return meta, pieces[2].lstrip("\n")


def _dump(meta: dict[str, Any], body: str) -> bytes:
    return (
        "---\n" + yaml.safe_dump(meta, sort_keys=False, allow_unicode=True) + "---\n" + body
    ).encode()


def _hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _canon(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _iso(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp lacks timezone")
    return parsed


def _valid_slug(slug: str) -> bool:
    return bool(_ID.fullmatch(slug)) and ".." not in slug


def _source_file_ok(repo: Path, path: Path) -> bool:
    return not path.is_symlink() and path.resolve().is_relative_to(repo.resolve())


def _trial_file_ok(base: Path, path: Path) -> bool:
    return (
        not path.is_symlink()
        and not path.parent.is_symlink()
        and path.resolve().is_relative_to(base.resolve())
    )


def _window_end(value: str) -> datetime:
    # A date-only closing day remains open through that UTC calendar day.
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        value += "T23:59:59.999999Z"
    return _iso(value)


def _history_body(body: str) -> str:
    if _HISTORY_START not in body and _HISTORY_END not in body:
        return body
    if body.count(_HISTORY_START) != 1 or body.count(_HISTORY_END) != 1:
        raise ValueError("invalid preserved trial history")
    return body.split(_HISTORY_START, 1)[1].split(_HISTORY_END, 1)[0]


def _legacy(body: str) -> dict[str, Any] | None:
    body = _history_body(body)
    activation = _START.search(body)
    if not activation:
        return None
    owner = _OWNER.search(body)
    members: list[dict[str, Any]] = []
    decisions: list[dict[str, Any]] = []
    for row in _ROW.finditer(body):
        ordinal, task_cell, times, trace, conversation, judgment = (x.strip() for x in row.groups())
        if not ordinal.isdigit():
            continue
        task = task_cell.split("/")[0].strip()
        if not task or task.lower() in {"task slug", "no qualifying task"}:
            continue
        members.append(
            {
                "task": task,
                "start": times.split("/")[0].strip(),
                "legacy_trace": trace,
                "legacy_conversation": conversation,
                "legacy_times": times,
            }
        )
        verdict = judgment.lower()
        if verdict in {"pass", "fail"}:
            refs = re.findall(r"conversation:[A-Za-z0-9._-]+", conversation)
            decisions.append(
                {
                    "id": f"legacy-assessment-{task}",
                    "kind": "assessment",
                    "actor": "user",
                    "decided_at": None,
                    "evidence_refs": refs,
                    "authority": "legacy_user_assessment",
                    "payload": {"task": task, "verdict": verdict},
                }
            )
    return {
        "schema_version": 1,
        "activation": activation.group(1),
        "policy": {
            "enabled": False,
            "revision": "legacy_collector",
            "authority": "legacy_named_collector",
        },
        "collector_provenance": owner.group(1).strip() if owner else None,
        "decisions": decisions,
        "members": members,
        "recovery": {"state": "pending", "next_trigger": "next_eligible_invocation"},
        "legacy_snapshot": {
            "activation": activation.group(1),
            "members": [m["task"] for m in members],
            "assessments": {d["payload"]["task"]: d["payload"]["verdict"] for d in decisions},
            "body_hash": _hash(body.encode()),
        },
    }


def _render_body(body: str, report: dict[str, Any], trial: dict[str, Any]) -> str:
    """Show typed current state while retaining the exact pre-migration record."""
    history = _history_body(body)
    lines = [
        "## Trial",
        "",
        f"Activated at: {report['activation']}",
        f"Collection: {report['collection']}",
        f"Outcome: {report['outcome']}",
        f"Enrolled: {len(report['cohort'])}/3",
        "",
        "| Order | Task | Start | Terminal | User assessment |",
        "|---|---|---|---|---|",
    ]
    for index, task in enumerate(report["cohort"], 1):
        start = next((m.get("start", "") for m in trial["members"] if m.get("task") == task), "")
        lines.append(
            f"| {index} | {task} | "
            f"{start} | "
            f"{report['tasks'].get(task, {}).get('terminal', False)} | "
            f"{report['assessments'].get(task, 'pending')} |"
        )
    lines.extend(
        [
            "",
            "<details><summary>Preserved trial history</summary>",
            "",
            _HISTORY_START.rstrip("\n"),
        ]
    )
    return "\n".join(lines) + "\n" + history + _HISTORY_END + "\n</details>\n"


def _doc(path: Path) -> tuple[dict[str, Any], str, bytes, dict[str, Any] | None]:
    if not _trial_file_ok(path.parent.parent, path):
        raise ValueError("trial PLAN path escapes repository")
    content = path.read_bytes()
    meta, body = _split(content)
    if meta.get("type") != "plan" or meta.get("task_slug") != path.stem.removeprefix("PLAN-"):
        raise ValueError("invalid trial PLAN identity")
    legacy = _legacy(body)
    trial = meta.get("trial")
    if trial is not None and (not isinstance(trial, dict) or trial.get("schema_version") != 1):
        raise ValueError("unsupported trial metadata")
    if trial is not None and (
        not isinstance(trial.get("activation"), str)
        or not _valid_timestamp(trial["activation"])
        or not isinstance(trial.get("policy"), dict)
        or not isinstance(trial.get("decisions"), list)
        or not isinstance(trial.get("members"), list)
        or not isinstance(trial.get("recovery", {}), dict)
        or not isinstance(trial.get("legacy_snapshot", {}), dict)
        or not isinstance(trial.get("publication", {}), dict)
        or not all(
            isinstance(item, dict) and isinstance(item.get("payload", {}), dict)
            for item in trial["decisions"]
        )
        or not all(isinstance(item, dict) for item in trial["members"])
        or not all(
            _valid_source_review_payload(item.get("payload", {}))
            for item in trial["decisions"]
            if item.get("kind") == "source_review"
        )
        or not all(
            _valid_assessment_payload(item.get("payload", {}))
            for item in trial["decisions"]
            if item.get("kind") == "assessment"
        )
    ):
        raise ValueError("invalid trial metadata")
    if trial is not None:
        snapshot = trial.get("legacy_snapshot", {})
        if snapshot and (
            not isinstance(snapshot.get("body_hash"), str)
            or not isinstance(snapshot.get("members"), list)
            or not all(isinstance(task, str) for task in snapshot["members"])
            or not isinstance(snapshot.get("assessments"), dict)
            or not all(
                isinstance(task, str) and verdict in ("pass", "fail")
                for task, verdict in snapshot["assessments"].items()
            )
        ):
            raise ValueError("invalid trial legacy_snapshot")
    return meta, body, content, legacy


def _trial(meta: dict[str, Any], legacy: dict[str, Any] | None) -> dict[str, Any] | None:
    return copy.deepcopy(meta.get("trial") if meta.get("trial") is not None else legacy)


def _trial_conflict(trial: dict[str, Any], legacy: dict[str, Any] | None) -> bool:
    snap = trial.get("legacy_snapshot")
    if not snap:
        return False
    if legacy is None or snap.get("body_hash") != legacy["legacy_snapshot"]["body_hash"]:
        return True
    if [
        m.get("task") for m in trial.get("members", [])[: len(snap.get("members", []))]
    ] != snap.get("members", []):
        return True
    decisions = {
        d.get("payload", {}).get("task"): d.get("payload", {}).get("verdict")
        for d in trial.get("decisions", [])
        if d.get("kind") == "assessment"
    }
    return any(
        decisions.get(task) != verdict for task, verdict in snap.get("assessments", {}).items()
    )


def _source_snapshot(
    base: Path, roots: list[Path], trial_id: str, activation: str
) -> dict[str, Any]:
    inventory: dict[str, str] = {}
    ledger_contents: dict[str, bytes] = {}
    starts: dict[str, list[str]] = {}
    events: dict[str, dict[str, Any]] = {}
    sources: dict[str, str] = {}
    bad: list[str] = []
    conflicts: list[str] = []
    registered_artifact_tasks: set[str] = set()
    _iso(activation)
    for repo in roots:
        label = "base" if repo == base else f"worktree:{repo}"
        if not repo.is_dir():
            bad.append(str(repo))
            continue
        ledger = repo / ".claude/observability/stage-spans.jsonl"
        if ledger.exists():
            try:
                if not _source_file_ok(repo, ledger):
                    raise ValueError("source path escapes registered repository")
                content = ledger.read_bytes()
                ledger_key = f"{label}:ledger"
                inventory[ledger_key] = _hash(content)
                ledger_contents[ledger_key] = content
                for line in content.decode().splitlines():
                    if not line.strip():
                        continue
                    item = json.loads(line)
                    if not isinstance(item, dict):
                        raise ValueError("ledger record is not a JSON object")
                    if item.get("event") == "start":
                        slug = item.get("task_slug")
                        # Stage spans may begin before a task has a slug. Such a
                        # span is not an attributable trial task start.
                        if slug is None:
                            continue
                        timestamp = item.get("ts")
                        if (
                            not isinstance(slug, str)
                            or not _valid_slug(slug)
                            or not isinstance(timestamp, str)
                            or not _valid_timestamp(timestamp)
                        ):
                            bad.append(f"{ledger}: invalid start for {slug!r}")
                            continue
                        starts.setdefault(slug, []).append(timestamp)
            except (OSError, ValueError, KeyError) as exc:
                bad.append(f"{ledger}: {exc}")
        for kind, folder in (
            ("RESEARCH", "work-docs"),
            ("SPEC", "specs"),
            ("SPEC", "work-docs"),
            ("PLAN", "work-docs"),
        ):
            for path in sorted((repo / folder).glob(f"{kind}-*.md")):
                if path.name == f"PLAN-{trial_id}.md":
                    continue
                try:
                    if not _source_file_ok(repo, path):
                        raise ValueError("source path escapes registered repository")
                    content = path.read_bytes()
                    # A task's own registered worktree artifact is evidence that
                    # the task exists even when its first start was never logged.
                    # Other files in the checkout may merely be inherited from
                    # base, so only its matching task slug is a candidate here.
                    own_task_artifact = (
                        repo != base
                        and repo.parent.name == ".worktrees"
                        and path.stem == f"{kind}-{repo.name}"
                    )
                    if own_task_artifact:
                        registered_artifact_tasks.add(repo.name)
                        inventory[f"{label}:{path.relative_to(repo)}"] = _hash(content)
                    # Old deliverables need not be valid YAML and are not trial
                    # evidence unless they explicitly carry structured events.
                    if b"trial_feedback:" not in content:
                        continue
                    meta, _ = _split(content)
                except (OSError, ValueError) as exc:
                    bad.append(f"{path}: {exc}")
                    continue
                raw_events = meta.get("trial_feedback", [])
                if not raw_events:
                    continue
                if not isinstance(raw_events, list):
                    bad.append(str(path))
                    continue
                inventory[f"{label}:{path.relative_to(repo)}"] = _hash(content)
                for event in raw_events:
                    if not isinstance(event, dict) or event.get("trial_id") != trial_id:
                        continue
                    if event.get("task_slug") != meta.get("task_slug"):
                        bad.append(f"{path}: event task does not match artifact")
                        continue
                    slug = event.get("task_slug")
                    eid = event.get("id")
                    if (
                        not isinstance(slug, str)
                        or not _valid_slug(slug)
                        or not isinstance(eid, str)
                        or not eid.strip()
                    ):
                        bad.append(str(path))
                        continue
                    prior = events.get(eid)
                    if prior is not None and prior != event:
                        conflicts.append(f"{path}: event {eid}")
                    else:
                        events[eid] = event
                        sources[eid] = str(path)
                    if event.get("kind") == "start":
                        at = event.get("at")
                        if not isinstance(at, str) or not _valid_timestamp(at):
                            bad.append(f"{path}: invalid start for {slug}")
                        else:
                            starts.setdefault(slug, []).append(at)
                    if (
                        event.get("kind") == "deferred"
                        and event.get("until")
                        and not _valid_window_end(str(event["until"]))
                    ):
                        bad.append(str(path))
    for event in events.values():
        slug = event.get("task_slug")
        if event.get("kind") != "start" and isinstance(slug, str) and slug not in starts:
            bad.append(f"{sources.get(str(event.get('id')), slug)}: missing start for {slug}")
    for slug in sorted(registered_artifact_tasks - starts.keys()):
        bad.append(f"registered task {slug}: missing first start")
    ordered: list[tuple[str, str]] = []
    for slug, times in starts.items():
        # The stage ledger records a new start on every resumed stage. A task
        # keeps one slot, anchored to its earliest attributable start.
        first = min(times, key=_iso)
        if _iso(first) >= _iso(activation):
            ordered.append((slug, first))
    ordered.sort(key=lambda x: (_iso(x[1]), x[0]))
    cutoff = ordered[-1][1] if ordered else activation
    # Legacy task artifacts often predate trial_feedback frontmatter. Bind their
    # bytes to a reviewed population without treating unrelated old documents
    # as evidence or requiring every historical frontmatter to parse.
    for slug, _ in ordered:
        for repo in roots:
            label = "base" if repo == base else f"worktree:{repo}"
            for kind, folder in (
                ("RESEARCH", "work-docs"),
                ("SPEC", "specs"),
                ("SPEC", "work-docs"),
                ("PLAN", "work-docs"),
            ):
                path = repo / folder / f"{kind}-{slug}.md"
                key = f"{label}:{path.relative_to(repo)}"
                if path.is_file() and key not in inventory:
                    try:
                        if not _source_file_ok(repo, path):
                            raise ValueError("source path escapes registered repository")
                        inventory[key] = _hash(path.read_bytes())
                    except (OSError, ValueError) as exc:
                        bad.append(f"{path}: {exc}")
    return {
        "inventory": inventory,
        "ledger_contents": ledger_contents,
        "registered_labels": ["base" if repo == base else f"worktree:{repo}" for repo in roots],
        "starts": ordered,
        "events": events,
        "sources": sources,
        "bad": bad,
        "conflicts": conflicts,
        "cutoff": cutoff,
    }


def _missing_reviewed_source(trial: dict[str, Any], source: dict[str, Any]) -> str | None:
    """Name a previously reviewed source that vanished from the bounded inventory."""
    reviews = [d for d in trial.get("decisions", []) if d.get("kind") == "source_review"]
    if not reviews or reviews[-1].get("payload", {}).get("disposition") != "accepted":
        return None
    accepted = reviews[-1]["payload"].get("inventory", {})
    current = source["inventory"]
    for key, digest in accepted.items():
        if key in current:
            continue
        if key.endswith(":ledger"):
            if key.rsplit(":", 1)[0] in source["registered_labels"]:
                return str(key)
            continue
        # A task artifact can move from its worktree to base unchanged.
        relative = key.split(":", 2)[-1]
        if not any(
            present_key.endswith(f":{relative}") and present_hash == digest
            for present_key, present_hash in current.items()
        ):
            return str(key)
    return None


def _changed_reviewed_source(trial: dict[str, Any], source: dict[str, Any]) -> str | None:
    """A changed reviewed identity cannot be reapproved by a later task start."""
    reviews = [d for d in trial.get("decisions", []) if d.get("kind") == "source_review"]
    if not reviews or reviews[-1].get("payload", {}).get("disposition") != "accepted":
        return None
    accepted = reviews[-1]["payload"].get("inventory", {})
    current = source["inventory"]
    for key, digest in accepted.items():
        if key.endswith(":ledger"):
            content = source.get("ledger_contents", {}).get(key)
            if (
                key in current
                and current[key] != digest
                and (not isinstance(content, bytes) or not _has_ledger_prefix(content, digest))
            ):
                return str(key)
            continue
        if key in current and current[key] != digest:
            return str(key)
    return None


def _has_ledger_prefix(content: bytes, digest: str) -> bool:
    """A later start may append records, but cannot rewrite the reviewed bytes."""
    hashed = hashlib.sha256()
    if hashed.hexdigest() == digest:
        return True
    for line in content.splitlines(keepends=True):
        hashed.update(line)
        if hashed.hexdigest() == digest:
            return True
    return False


def _reviewed_order(
    trial: dict[str, Any], source: dict[str, Any], candidates: list[str]
) -> list[str] | None:
    """Keep an accepted tie resolution while a later acknowledged interval grows."""
    reviews = [d for d in trial.get("decisions", []) if d.get("kind") == "source_review"]
    if not reviews:
        return None
    payload = reviews[-1].get("payload", {})
    ordered = payload.get("ordered_tasks")
    if (
        payload.get("disposition") != "accepted"
        or not isinstance(ordered, list)
        or not all(isinstance(item, str) for item in ordered)
    ):
        return None
    starts = {slug: _iso(at) for slug, at in source["starts"]}
    if payload.get("inventory") == source["inventory"]:
        if len(ordered) != len(candidates) or set(ordered) != set(candidates):
            return None
        resolved = ordered
    else:
        if _missing_reviewed_source(trial, source) or _changed_reviewed_source(trial, source):
            return None
        reviewed = set(ordered)
        if len(reviewed) != len(ordered) or not reviewed.issubset(candidates):
            return None
        later = [slug for slug in candidates if slug not in reviewed]
        if any(starts[slug] <= _iso(payload["through"]) for slug in later):
            return None
        # A same-slug resume adds no task; later tasks that tie were never ordered by the user.
        if any(starts[x] >= starts[y] for x, y in zip(later, later[1:], strict=False)):
            return None
        resolved = ordered + later
    if any(
        starts[left] > starts[right] for left, right in zip(resolved, resolved[1:], strict=False)
    ):
        return None
    return resolved


def _coverage(trial: dict[str, Any], source: dict[str, Any]) -> tuple[bool, str]:
    reviews = [d for d in trial.get("decisions", []) if d.get("kind") == "source_review"]
    first_starts = dict(source["starts"])

    def acknowledged(slug: str) -> bool:
        first = first_starts.get(slug)
        if first is None:
            return False
        return any(
            e.get("kind") == "start"
            and e.get("task_slug") == slug
            and isinstance(e.get("at"), str)
            and _valid_timestamp(e["at"])
            and _iso(e["at"]) == _iso(first)
            for e in source["events"].values()
        )

    if not reviews:
        # Typed start acknowledgments can cover future sessions without legacy review.
        if source["starts"] and all(acknowledged(slug) for slug, _ in source["starts"]):
            return True, "acknowledged"
        return False, "source_review_required"
    latest = reviews[-1].get("payload", {})
    if latest.get("disposition") != "accepted":
        return False, "source_incomplete"
    if _missing_reviewed_source(trial, source):
        return False, "source_incomplete"
    excluded = set(latest.get("excluded_tasks", []))
    observed = [slug for slug, _ in source["starts"] if slug not in excluded]
    observed = _reviewed_order(trial, source, observed) or observed
    if latest.get("inventory") != source["inventory"]:
        if _changed_reviewed_source(trial, source):
            return False, "source_conflict"
        # The reviewed historical prefix is already committed. A later task
        # can extend it from an explicit start acknowledgment even after its
        # artifact moves from a task worktree to the landed base document.
        members = trial.get("members", [])
        frozen = [m.get("task") for m in members]
        starts = dict(source["starts"])
        reviewed = latest.get("ordered_tasks")
        later = observed[len(reviewed) :] if isinstance(reviewed, list) else []
        if (
            isinstance(reviewed, list)
            and observed[: len(reviewed)] == reviewed
            and observed[: len(frozen)] == frozen
            and all(
                isinstance(m.get("start"), str)
                and m.get("task") in starts
                and _iso(m["start"]) == _iso(starts[m["task"]])
                for m in members
            )
            and all(
                _iso(starts[slug]) > _iso(latest["through"]) and acknowledged(slug)
                for slug in later
            )
            and later
        ):
            return True, "acknowledged_extension"
        return False, "source_conflict"
    if latest.get("ordered_tasks") != observed:
        return False, "order_conflict"
    try:
        if _iso(latest["through"]) < _iso(source["cutoff"]):
            return False, "source_review_required"
    except (KeyError, ValueError):
        return False, "source_review_required"
    return True, "accepted"


def _member_start_conflict(trial: dict[str, Any], source: dict[str, Any]) -> bool:
    starts = dict(source["starts"])
    for member in trial.get("members", []):
        task = member.get("task")
        committed = member.get("start")
        if not isinstance(task, str) or not isinstance(committed, str):
            return True
        current = starts.get(task)
        if current is None or not _valid_timestamp(committed):
            return True
        if _iso(committed) != _iso(current):
            return True
    return False


def _task_source_refs(inventory: dict[str, str], slug: str) -> list[str]:
    """Attribute artifact paths, never worktree directory names, to a task."""
    names = {f"work-docs/{kind}-{slug}.md" for kind in ("RESEARCH", "SPEC", "PLAN")}
    names.add(f"specs/SPEC-{slug}.md")
    return [key for key in inventory if key.rsplit(":", 1)[-1] in names]


def _status(
    base: Path,
    trial_id: str,
    trial: dict[str, Any] | None,
    source: dict[str, Any] | None,
    revision: str,
    *,
    legacy: bool = False,
    conflict: bool = False,
) -> dict[str, Any]:
    cohort = [str(m.get("task")) for m in trial.get("members", [])] if trial else []
    candidates = [slug for slug, _ in source["starts"]] if source else []
    reviews = (
        [d for d in trial.get("decisions", []) if d.get("kind") == "source_review"] if trial else []
    )
    if reviews and reviews[-1].get("payload", {}).get("disposition") == "accepted":
        excluded = set(reviews[-1]["payload"].get("excluded_tasks", []))
        candidates = [slug for slug in candidates if slug not in excluded]
    reviewed_order = _reviewed_order(trial, source, candidates) if trial and source else None
    if reviewed_order:
        candidates = reviewed_order
    tasks: dict[str, dict[str, Any]] = {}
    terminal_refs: dict[str, bool] = {}
    if source:
        for slug in candidates:
            records = [e for e in source["events"].values() if e.get("task_slug") == slug]
            terminal = any(e.get("kind") == "terminal" for e in records)
            terminal_evidence = any(
                e.get("kind") == "terminal" and e.get("evidence_refs") for e in records
            )
            terminal_refs[slug] = terminal_evidence
            evidence = any(
                e.get("kind") == "observation" and e.get("evidence_refs") for e in records
            )
            deferred = next(
                (e for e in records if e.get("kind") == "deferred" and e.get("until")), None
            )
            tasks[slug] = {
                "terminal": terminal,
                "evidence": evidence,
                "deferred_until": deferred.get("until") if deferred else None,
                "events": [e["id"] for e in records],
            }
    assessments: dict[str, str] = {}
    if trial:
        for decision in trial.get("decisions", []):
            if decision.get("kind") != "assessment":
                continue
            task = decision.get("payload", {}).get("task")
            verdict = decision.get("payload", {}).get("verdict")
            # A later decision ID cannot erase a confirmed failure.
            if (
                isinstance(task, str)
                and verdict in {"pass", "fail"}
                and assessments.get(task) != "fail"
            ):
                assessments[task] = verdict
    policy = trial.get("policy", {}) if trial else {}
    missing_reviewed = _missing_reviewed_source(trial, source) if trial and source else None
    collection = (
        "complete"
        if len(cohort) == 3 and all(tasks.get(x, {}).get("terminal") for x in cohort)
        else "collecting"
        if trial
        else "not_started"
    )
    outcome = "pending"
    if any(assessments.get(task) == "fail" for task in cohort):
        outcome = "failed"
    elif any(
        tasks.get(x, {}).get("terminal")
        and (not tasks.get(x, {}).get("evidence") or not terminal_refs.get(x))
        for x in cohort
    ):
        outcome = "insufficient_evidence"
    elif collection == "complete" and all(assessments.get(x) == "pass" for x in cohort):
        outcome = "passed"
    if trial is None:
        reason = "no_trial"
    elif (source and source["bad"]) or missing_reviewed:
        reason = "source_incomplete"
    elif conflict or (source and source["conflicts"]):
        reason = "source_conflict"
    elif (
        len(candidates) != len(set(candidates))
        or (
            source
            and reviewed_order is None
            and len({_iso(dict(source["starts"])[task]) for task in candidates}) != len(candidates)
        )
        or cohort
        and candidates
        and candidates[: len(cohort)] != cohort
    ):
        reason = "order_conflict"
    elif trial and source and not legacy and _member_start_conflict(trial, source):
        reason = "source_conflict"
    elif legacy or policy.get("revision") == "legacy_collector":
        reason = "policy_revision_required"
    elif policy.get("enabled") is not True:
        reason = "authority_required"
    elif any(
        _window_end(str(tasks[x]["deferred_until"])) > datetime.now(UTC)
        for x in candidates
        if tasks.get(x, {}).get("deferred_until")
    ):
        reason = "observation_window_open"
    elif candidates and (not cohort or any(x not in cohort for x in candidates[:3])):
        covered, why = _coverage(trial, source or {})
        reason = "awaiting_reconciliation" if covered else why
    elif outcome == "pending" and any(
        tasks.get(x, {}).get("terminal")
        and tasks.get(x, {}).get("evidence")
        and x not in assessments
        for x in cohort
    ):
        reason = "awaiting_user_assessment"
    elif not candidates:
        covered, why = _coverage(trial, source or {})
        reason = "no_candidates" if covered else why
    else:
        reason = "pending"
    if outcome == "passed" and reason in {
        "source_incomplete",
        "source_conflict",
        "order_conflict",
        "source_review_required",
    }:
        outcome = "pending"
    recovery = (
        copy.deepcopy(trial.get("recovery", {"state": "pending"})) if trial else {"state": "none"}
    )
    action = _ACTION.get(reason, "none")
    if recovery.get("state") == "blocked" and reason not in {
        "source_incomplete",
        "source_conflict",
        "order_conflict",
        "policy_revision_required",
        "authority_required",
        "source_review_required",
    }:
        action = "resume_recovery_and_readback"
    return {
        "schema_version": 1,
        "trial_id": trial_id,
        "activation": trial.get("activation") if trial else None,
        "policy_revision": policy.get("revision"),
        "revision": revision,
        "inventory": source["inventory"] if source else {},
        "cutoff": source["cutoff"] if source else None,
        "candidates": candidates,
        "cohort": cohort,
        "collection": collection,
        "outcome": outcome,
        "assessments": assessments,
        "tasks": tasks,
        "reason": reason,
        "action": action,
        "questions": [],
        "recovery": recovery,
        "source": (
            source["bad"][0]
            if source and source["bad"]
            else source["conflicts"][0]
            if source and source["conflicts"]
            else missing_reviewed
            if missing_reviewed
            else None
        ),
        "changed": False,
    }


def _read(
    base: Path, roots: list[Path], trial_id: str
) -> tuple[
    dict[str, Any], dict[str, Any] | None, dict[str, Any] | None, bytes, str, dict[str, Any]
]:
    path = _path(base, trial_id)
    if _pending_trial_stash(base, trial_id):
        pending = _status(base, trial_id, None, None, "")
        pending.update(reason="lifecycle_pending", action=_ACTION["lifecycle_pending"])
        return pending, None, None, b"", "", {}
    if not path.exists():
        empty = _status(base, trial_id, None, None, "", legacy=False)
        committed = _head_bytes(base, f"work-docs/{path.name}")
        if committed is not None and _marks_trial_content(committed):
            empty.update(
                reason="source_conflict",
                action=_ACTION["source_conflict"],
                source=f"work-docs/{path.name}: committed active trial is missing",
            )
        return empty, None, None, b"", "", {}
    meta, body, content, legacy = _doc(path)
    trial = _trial(meta, legacy)
    if trial is None:
        empty = _status(base, trial_id, None, None, _hash(content))
        committed = _head_bytes(base, f"work-docs/{path.name}")
        if committed is not None and _marks_trial_content(committed):
            # Like a deleted file: dropping the marker does not end a committed trial.
            empty.update(
                reason="source_conflict",
                action=_ACTION["source_conflict"],
                source=f"work-docs/{path.name}: committed active trial marker is missing",
            )
        return empty, meta, None, content, body, {}
    source = _source_snapshot(base, roots, trial_id, str(trial["activation"]))
    report = _status(
        base,
        trial_id,
        trial,
        source,
        _hash(content),
        legacy=meta.get("trial") is None,
        conflict=_trial_conflict(trial, legacy),
    )
    return report, meta, trial, content, body, source


def status(root: Path, trial_id: str) -> dict[str, Any]:
    _path(Path(root), trial_id)
    try:
        base, roots = _roots(Path(root))
    except RuntimeError:
        result = _status(Path(root), trial_id, None, None, "")
        result.update(reason="source_incomplete", action=_ACTION["source_incomplete"])
        return result
    _path(base, trial_id)
    try:
        # ADR-003: reads share the trial fence, so a status never mixes pre- and post-write files.
        with _writer(base):
            return _read(base, roots, trial_id)[0]
    except OSError as exc:
        if str(exc) in {"lock_busy", "unsupported_lock"}:
            # The fence is the read's precondition; answer without touching the sources.
            busy = _status(base, trial_id, None, None, "")
            busy.update(reason=str(exc), action=_ACTION[str(exc)])
            return busy
        result = _status(base, trial_id, None, None, "")
        result.update(
            reason="source_incomplete",
            action=_ACTION["source_incomplete"],
            source=f"{_path(base, trial_id)}: {exc}",
        )
        return result
    except ValueError as exc:
        result = _status(base, trial_id, None, None, "")
        result.update(
            reason="source_incomplete",
            action=_ACTION["source_incomplete"],
            source=f"{_path(base, trial_id)}: {exc}",
        )
        return result


def _marks_trial_content(content: bytes) -> bool:
    try:
        meta, body = _split(content)
    except ValueError:
        # Preserve an unparseable trial candidate. A previously committed
        # active PLAN is checked separately even when this heuristic finds none.
        return bool(re.search(rb"(?m)^\s*(?:trial|Activation)\s*:", content))
    return "trial" in meta or _legacy(body) is not None


def active_trials(root: Path) -> list[str]:
    base, _ = _roots(Path(root))
    results: list[str] = []
    folder = base / "work-docs"
    if folder.is_symlink():
        raise ValueError("trial PLAN directory escapes repository")
    changed_paths: set[str] | None = None

    for path in sorted(folder.glob("PLAN-*.md")):
        if path.is_symlink():
            results.append(path.stem.removeprefix("PLAN-"))
            continue
        try:
            raw = path.read_bytes()
        except OSError:
            results.append(path.stem.removeprefix("PLAN-"))
            continue
        if _marks_trial_content(raw):
            results.append(path.stem.removeprefix("PLAN-"))
            continue
        # A valid marker-free working copy can still be an edit of an active
        # committed trial. Probe HEAD only for changed PLANs: checking every
        # historical PLAN separately would turn each landing into hundreds of
        # Git subprocesses.
        if changed_paths is None:
            try:
                changed_paths = set(
                    _git(base, "diff", "--name-only", "HEAD", "--", "work-docs").splitlines()
                )
            except OSError:
                changed_paths = {
                    f"work-docs/{candidate.name}" for candidate in folder.glob("PLAN-*.md")
                }
        relative = f"work-docs/{path.name}"
        if relative not in changed_paths:
            continue
        try:
            committed = _head_bytes(base, relative)
        except OSError:
            # Uncertainty about committed identity must not strip protection.
            results.append(path.stem.removeprefix("PLAN-"))
            continue
        if committed is not None and _marks_trial_content(committed):
            results.append(path.stem.removeprefix("PLAN-"))
    deleted = _git(
        base, "diff", "--no-renames", "--name-only", "--diff-filter=D", "HEAD", "--", "work-docs"
    ).splitlines()
    for relative in deleted:
        name = Path(relative).name
        if not relative.startswith("work-docs/PLAN-") or not name.endswith(".md"):
            continue
        trial_id = name.removeprefix("PLAN-").removesuffix(".md")
        if trial_id in results:
            continue
        committed = _head_bytes(base, relative)
        if committed is not None and _marks_trial_content(committed):
            results.append(trial_id)
    return results


def protected_trial_paths(root: Path) -> set[str]:
    """Tracked base documents that a supported Git writer must preserve."""
    base, _ = _roots(Path(root))
    return {f"work-docs/PLAN-{trial_id}.md" for trial_id in active_trials(base)}


def stash_contains_protected_trial(root: Path, stash_ref: str) -> bool:
    base, _ = _roots(Path(root))
    protected = protected_trial_paths(base)
    if not protected:
        return False
    try:
        shown = set(_git(base, "stash", "show", "--name-only", stash_ref).splitlines())
    except OSError:
        return True
    return bool(shown & protected)


def _pending_trial_stash(base: Path, trial_id: str) -> bool:
    relative = f"work-docs/PLAN-{trial_id}.md"
    try:
        refs = _git(base, "stash", "list", "--format=%gd").splitlines()
    except OSError:
        return True
    for ref in refs:
        try:
            if relative in _git(base, "stash", "show", "--name-only", ref).splitlines():
                return True
        except OSError:
            return True
    return False


def pending_trial_stashes(root: Path) -> list[str]:
    base, _ = _roots(Path(root))
    return [trial_id for trial_id in active_trials(base) if _pending_trial_stash(base, trial_id)]


def verified_trial_landing_paths(root: Path) -> set[str]:
    """Return only runtime-owned trial deltas with exact publication provenance.

    A manual prose or metadata edit after publication invalidates the receipt;
    callers must refuse to land rather than silently sweep that edit into Git.
    """
    base, _ = _roots(Path(root))
    eligible: set[str] = set()
    for relative in protected_trial_paths(base):
        path = base / relative
        if not _trial_file_ok(base, path):
            raise ValueError(f"trial PLAN path escapes repository: {relative}")
        content = path.read_bytes()
        head = _head_bytes(base, relative)
        if head == content:
            continue
        meta, body = _split(content)
        receipt = (meta.get("trial") or {}).get("publication")
        if not receipt or receipt.get("owner") != "intent_trial":
            raise ValueError(f"unverified trial change: {relative}")
        if not _prior_publication_valid(meta, body):
            raise ValueError(f"trial publication changed: {relative}")
        expected_blob = _hash(head) if head is not None else "untracked"
        if receipt.get("base_blob") != expected_blob:
            raise ValueError(f"trial HEAD changed since publication: {relative}")
        eligible.add(relative)
    return eligible


@contextlib.contextmanager
def _writer(base: Path) -> Iterator[None]:
    try:
        common = Path(_git(base, "rev-parse", "--git-common-dir"))
        common = common if common.is_absolute() else (base / common).resolve()
        fd, mechanism = _flock_lock(common / "index.lock-hm", 5.0)
        if mechanism != "flock" or fd is None:
            raise OSError("unsupported_lock")
    except TimeoutError as exc:
        raise OSError("lock_busy") from exc
    try:
        yield
    finally:
        os.close(fd)


def _publication_hash(meta: dict[str, Any], body: str) -> str:
    clean = copy.deepcopy(meta)
    if isinstance(clean.get("trial"), dict):
        clean["trial"].pop("publication", None)
    return _hash(_dump(clean, body))


def _prior_publication_valid(meta: dict[str, Any], body: str) -> bool:
    trial = meta.get("trial") or {}
    receipt = trial.get("publication")
    return receipt is None or receipt.get("content_hash") == _publication_hash(meta, body)


def _publish(base: Path, trial_id: str, meta: dict[str, Any], body: str, read: bytes) -> str:
    """`read` is the destination as the caller's `_read` saw it; any other bytes now mean an
    edit landed after that read, and publishing would silently discard it."""
    path = _path(base, trial_id)
    if not _trial_file_ok(base, path):
        raise ValueError("trial PLAN path escapes repository")
    trial = meta["trial"]
    previous = trial.get("publication", {})
    head = _head_bytes(base, f"work-docs/PLAN-{trial_id}.md")
    current = path.read_bytes()
    if current != read:
        raise ValueError("trial PLAN changed after it was read")
    if not previous:
        # A first write may migrate an already dirty legacy record, but cannot
        # certify unrelated preexisting dirt as a runtime-owned landing delta.
        base_blob = (
            _hash(head) if head is not None and current == head else "unverified_preexisting"
        )
    elif current == head:
        # The previous publication has landed. Start a fresh Git delta.
        base_blob = _hash(head)
    elif previous.get("base_blob") == "unverified_preexisting":
        base_blob = "unverified_preexisting"
    else:
        base_blob = previous.get("base_blob")
        if base_blob != (_hash(head) if head is not None else "untracked"):
            raise ValueError("trial HEAD changed since publication")
    trial["publication"] = {
        "base_blob": base_blob,
        "content_hash": _publication_hash(meta, body),
        "owner": "intent_trial",
    }
    content = _dump(meta, body)
    fd, tmp = tempfile.mkstemp(prefix=f".PLAN-{trial_id}-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return _hash(content)


def _rejected(report: dict[str, Any], why: str) -> dict[str, Any]:
    """A rejection names its own next step, never the one status computed before the check."""
    return dict(report, reason=why, action=_ACTION.get(why, "none"), changed=False)


def _blocked(base: Path, roots: list[Path], trial_id: str, why: str) -> dict[str, Any]:
    try:
        result = _read(base, roots, trial_id)[0]
    except (OSError, ValueError) as exc:
        result = _status(base, trial_id, None, None, "")
        result.update(source=f"{_path(base, trial_id)}: {exc}")
        why = "source_incomplete"
    result.update(reason=why, action=_ACTION.get(why, "none"), changed=False)
    return result


def _valid_assessment_payload(payload: dict[str, Any]) -> bool:
    task = payload.get("task")
    verdict = payload.get("verdict")
    return (
        isinstance(task, str)
        and _valid_slug(task)
        and isinstance(verdict, str)
        and verdict in ("pass", "fail")
    )


def _valid_source_review_payload(payload: dict[str, Any]) -> bool:
    ordered = payload.get("ordered_tasks")
    excluded = payload.get("excluded_tasks")
    inventory = payload.get("inventory")
    return (
        isinstance(inventory, dict)
        and all(
            isinstance(key, str) and isinstance(digest, str) for key, digest in inventory.items()
        )
        and isinstance(ordered, list)
        and isinstance(excluded, list)
        and all(isinstance(x, str) and _valid_slug(x) for x in ordered + excluded)
        and len(set(ordered + excluded)) == len(ordered + excluded)
        and payload.get("disposition") in ("accepted", "unresolved")
        and isinstance(payload.get("through"), str)
        and _valid_timestamp(payload["through"])
    )


def _validate_decision(decision: dict[str, Any]) -> bool:
    if (
        not isinstance(decision, dict)
        or not isinstance(decision.get("kind"), str)
        or decision.get("kind")
        not in {
            "policy",
            "source_review",
            "assessment",
        }
    ):
        return False
    if not all(
        decision.get(key) for key in ("id", "actor", "decided_at", "evidence_refs", "authority")
    ):
        return False
    if decision.get("actor") != "user" or not isinstance(decision.get("payload"), dict):
        return False
    try:
        _iso(str(decision["decided_at"]))
    except ValueError:
        return False
    payload = decision["payload"]
    if decision["kind"] == "policy":
        return (
            type(payload.get("enabled")) is bool
            and isinstance(payload.get("revision"), str)
            and bool(payload["revision"])
        )
    if decision["kind"] == "assessment":
        return _valid_assessment_payload(payload)
    if decision["kind"] == "source_review":
        return _valid_source_review_payload(payload)
    return True


def _valid_timestamp(value: str) -> bool:
    try:
        _iso(value)
    except ValueError:
        return False
    return True


def _valid_window_end(value: str) -> bool:
    try:
        _window_end(value)
    except ValueError:
        return False
    return True


def record_decision(
    root: Path, trial_id: str, decision: dict[str, Any], *, expected_revision: str
) -> dict[str, Any]:
    _path(Path(root), trial_id)
    try:
        base, roots = _roots(Path(root))
    except RuntimeError:
        return status(root, trial_id)
    _path(base, trial_id)
    if not _validate_decision(decision):
        return _blocked(base, roots, trial_id, "authority_required")
    try:
        with _writer(base):
            locked_base, locked_roots = _roots(base)
            if locked_base != base or set(locked_roots) != set(roots):
                return _blocked(base, locked_roots, trial_id, "source_conflict")
            report, meta, trial, content, body, source = _read(base, roots, trial_id)
            if trial is None or meta is None:
                # `_read` already told an absent trial from a missing or stashed one.
                return _rejected(report, str(report.get("reason") or "no_trial"))
            for old in trial.get("decisions", []):
                if old.get("id") == decision["id"]:
                    return _rejected(report, "replay" if old == decision else "decision_conflict")
            if report["revision"] != expected_revision:
                return _rejected(report, "revision_conflict")
            if (
                decision["kind"] == "assessment"
                and decision["payload"]["task"] not in report["cohort"]
            ):
                return _rejected(report, "authority_required")
            if not _prior_publication_valid(meta, body):
                return _rejected(report, "source_conflict")
            new_meta = copy.deepcopy(meta)
            new_trial = _trial(meta, _legacy(body))
            assert new_trial is not None
            new_trial.setdefault("decisions", []).append(copy.deepcopy(decision))
            if decision["kind"] == "policy":
                new_trial["policy"] = {
                    "enabled": decision["payload"].get("enabled"),
                    "revision": decision["payload"].get("revision"),
                    "authority": decision["id"],
                }
            new_meta["trial"] = new_trial
            rendered = _render_body(body, _status(base, trial_id, new_trial, source, ""), new_trial)
            _publish(base, trial_id, new_meta, rendered, content)
            fresh = _read(base, roots, trial_id)[0]
            fresh["changed"] = True
            return fresh
    except OSError as exc:
        why = str(exc) if str(exc) in {"lock_busy", "unsupported_lock"} else "unsupported_lock"
        return _blocked(base, roots, trial_id, why)
    except RuntimeError:
        return _blocked(base, roots, trial_id, "source_incomplete")
    except ValueError:
        return _blocked(base, roots, trial_id, "source_conflict")


def reconcile(root: Path, trial_id: str, *, dry_run: bool = False) -> dict[str, Any]:
    _path(Path(root), trial_id)
    try:
        base, roots = _roots(Path(root))
    except RuntimeError:
        return status(root, trial_id)
    _path(base, trial_id)
    if dry_run:
        return status(base, trial_id)
    try:
        with _writer(base):
            locked_base, locked_roots = _roots(base)
            if locked_base != base or set(locked_roots) != set(roots):
                return _blocked(base, locked_roots, trial_id, "source_conflict")
            report, meta, trial, content, body, source = _read(base, roots, trial_id)
            if trial is None or meta is None:
                return report
            if report["reason"] in {
                "source_incomplete",
                "source_conflict",
                "order_conflict",
                "policy_revision_required",
                "authority_required",
            }:
                return report
            if not _prior_publication_valid(meta, body):
                return dict(report, reason="source_conflict", changed=False)
            covered, why = _coverage(trial, source)
            uncommitted = [s for s in report["candidates"][:3] if s not in report["cohort"]]
            proposed = uncommitted[: max(0, 3 - len(report["cohort"]))] if covered else []
            new_meta = copy.deepcopy(meta)
            new_trial = copy.deepcopy(trial)
            refs_changed = False
            if covered:
                for member in new_trial.get("members", []):
                    exact_refs = _task_source_refs(source["inventory"], str(member["task"]))
                    if member.get("source_refs") != exact_refs:
                        member["source_refs"] = exact_refs
                        refs_changed = True
            if not covered and uncommitted:
                new_trial["recovery"] = {
                    "state": "blocked",
                    "reason": why,
                    "authority": new_trial.get("policy", {}).get("authority"),
                    "next_trigger": "next_eligible_invocation",
                }
            elif covered and (
                proposed or refs_changed or new_trial.get("recovery", {}).get("state") != "complete"
            ):
                by_slug = dict(source["starts"])
                for slug in proposed:
                    new_trial.setdefault("members", []).append(
                        {
                            "task": slug,
                            "start": by_slug[slug],
                            "source_refs": _task_source_refs(source["inventory"], slug),
                        }
                    )
                new_trial["recovery"] = {
                    "state": "complete",
                    "next_trigger": "next_eligible_invocation",
                    "authority": new_trial.get("policy", {}).get("authority"),
                }
            else:
                return report
            if new_trial == trial:
                return report
            # A source can change while this process parses it. Re-read relevant
            # source identities before publishing to avoid stale cohort writes.
            check_base, check_roots = _roots(base)
            if check_base != base or set(check_roots) != set(roots):
                return dict(
                    report,
                    reason="source_conflict",
                    action=_ACTION["source_conflict"],
                    changed=False,
                )
            check = _source_snapshot(base, check_roots, trial_id, str(trial["activation"]))
            if (
                check["inventory"] != source["inventory"]
                or check["starts"] != source["starts"]
                or check["conflicts"] != source["conflicts"]
                or check["bad"] != source["bad"]
            ):
                return dict(
                    report,
                    reason="source_conflict",
                    action=_ACTION["source_conflict"],
                    changed=False,
                )
            new_meta["trial"] = new_trial
            rendered = _render_body(body, _status(base, trial_id, new_trial, source, ""), new_trial)
            _publish(base, trial_id, new_meta, rendered, content)
            fresh = _read(base, roots, trial_id)[0]
            fresh["changed"] = True
            return fresh
    except OSError as exc:
        why = str(exc) if str(exc) in {"lock_busy", "unsupported_lock"} else "unsupported_lock"
        return _blocked(base, roots, trial_id, why)
    except RuntimeError:
        return _blocked(base, roots, trial_id, "source_incomplete")
    except ValueError:
        return _blocked(base, roots, trial_id, "source_conflict")
