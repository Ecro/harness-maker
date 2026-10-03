"""The Maker router's briefing: one read-only, capped JSON digest of the project's task state."""

from __future__ import annotations

import json
import re
import subprocess
import time
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

PIPELINE: tuple[str, ...] = ("research", "spec", "execute", "review", "verify", "wrapup")
MAX_BYTES = 1500
MAX_TASKS = 5
MAX_INTENT_ITEMS = 3
MIN_ACTIVE_INTENTS = 3
MIN_TASKS = 3
# Dropped per task, group by group, before the task floor gives way (REVIEW dbe5ddc7). Timing
# goes first; `other_session` is never dropped — Maker reads its absence as "unknown, ask once",
# so dropping it would cost a question on every resume (REVIEW confirm-1).
_OPTIONAL_TASK_FIELDS: tuple[tuple[str, ...], ...] = (
    ("last_seen", "last_stage"),
    ("latest_artifact",),
)
PARK_DAYS = 7
NO_DATA = "—"
_SUBJECT_MAX = 60
_ID_MAX = 40
_REVIEW_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
# Total budget for the artifact checks; past it a task reports `next_stage: null` (REVIEW 6d4374d1).
DEADLINE_S = 5.0
_INTENT_KEYS: tuple[str, ...] = (
    "conflicts",
    "fired_revisits",
    "needs_revalidation",
    "stale_evidence",
)


def _git(cwd: Path, *args: str) -> str | None:
    try:
        proc = subprocess.run(
            ["git", *args], cwd=cwd, capture_output=True, text=True, timeout=15, check=False
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return proc.stdout if proc.returncode == 0 else None


def base_root(root: Path) -> Path | None:
    """The git base root for any cwd inside the project (base, subdirectory or task worktree)."""
    common = _git(root, "rev-parse", "--path-format=absolute", "--git-common-dir")
    if common is None:
        return None
    return Path(common.strip()).parent


def task_worktrees(base: Path) -> dict[str, Path]:
    """`hm/<slug>` worktrees under `.worktrees/`, found from their `.git` files (no subprocess)."""
    found: dict[str, Path] = {}
    parent = base / ".worktrees"
    if not parent.is_dir():
        return found
    for wt in sorted(parent.iterdir()):
        try:
            pointer = (wt / ".git").read_text(encoding="utf-8").strip()
            if not pointer.startswith("gitdir:"):
                continue
            gitdir = Path(pointer.split(":", 1)[1].strip())
            if not gitdir.is_absolute():
                gitdir = (wt / gitdir).resolve()
            head = (gitdir / "HEAD").read_text(encoding="utf-8").strip()
        except OSError:
            continue
        prefix = "ref: refs/heads/hm/"
        if head.startswith(prefix):
            found[head[len(prefix) :]] = wt
    return found


def _stage_name(stage: str) -> str | None:
    name = stage.removeprefix("hm:")
    return name if name in PIPELINE else None


def span_rows(base: Path) -> list[dict[str, Any]]:
    """Well-formed span rows in file order; torn or malformed lines are skipped, never raised."""
    path = base / ".claude/observability/stage-spans.jsonl"
    rows: list[dict[str, Any]] = []
    try:
        raw = path.read_bytes()
    except OSError:
        return rows
    for line in raw.decode("utf-8", errors="replace").splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict) and isinstance(row.get("task_slug"), str):
            rows.append(row)
    return rows


def last_stage_and_session(
    rows: list[dict[str, Any]], session_id: str | None
) -> tuple[str | None, str | None, bool | None]:
    """(last_stage, last_seen, other_session) from a task's rows, newest last.

    `other_session` is only decidable when both ids are present — a missing id on either side
    is `None`, never a guess.
    """
    if not rows:
        return None, None, None
    # Newest by timestamp; file order breaks ties (two sessions can append out of order).
    newest = max(enumerate(rows), key=lambda ir: (str(ir[1].get("ts") or ""), ir[0]))[1]
    stage = newest.get("stage")
    last_stage = _stage_name(stage) if isinstance(stage, str) else None
    ts = newest.get("ts")
    row_session = newest.get("session_id")
    if not session_id or not isinstance(row_session, str) or not row_session:
        other: bool | None = None
    else:
        other = row_session != session_id
    return last_stage, ts if isinstance(ts, str) else None, other


def _review_status(path: Path) -> str | None:
    from harness_maker.frontmatter import split_frontmatter

    try:
        split = split_frontmatter(path.read_bytes())
    except OSError:
        return None
    mapping = getattr(split, "mapping", None) or {}
    status = mapping.get("status") if isinstance(mapping, dict) else None
    return status if isinstance(status, str) else None


def _spec_done(base: Path, slug: str, wt: Path) -> bool:
    from harness_maker import spec_machine

    try:
        state = spec_machine.approval_state(base, slug, checkout=wt).state
    except Exception:  # noqa: BLE001 — a broken SPEC is "not done", never a digest failure
        return False
    return state in ("approved", "exempt")


def _verify_done(wt: Path) -> bool:
    from harness_maker.observability import verification_cache

    try:
        key = verification_cache.compute_relevant_skip_key(wt)
        return bool(verification_cache.is_fresh(key))
    except Exception:  # noqa: BLE001
        return False


def _has(directory: Path, pattern: str) -> bool:
    return directory.is_dir() and any(directory.glob(pattern))


def _reviews(docs: Path, slug: str) -> list[Path]:
    # Exact names only: a hyphen-prefix slug (`world-model` vs `world-model-name`) must not
    # pick up a sibling task's committed REVIEW/SPEC (REVIEW a003ff68).
    prefix = f"REVIEW-{slug}-"
    return sorted(
        p
        for p in (docs.glob(f"{prefix}*.md") if docs.is_dir() else [])
        if _REVIEW_DATE.fullmatch(p.name[len(prefix) : -len(".md")])
    )


def artifact_files(slug: str, wt: Path) -> list[Path]:
    """The same artifact set `next_stage` reads, so `parked`/`latest_artifact` agree with it."""
    docs, specs = wt / "work-docs", wt / "specs"
    named = [
        docs / f"RESEARCH-{slug}.md",
        docs / f"PLAN-{slug}.md",
        specs / f"SPEC-{slug}.md",
        specs / f"SPEC-{slug}.machine.yaml",
    ]
    return [p for p in named if p.is_file()] + _reviews(docs, slug)


def latest_artifact(files: list[Path]) -> dict[str, str] | None:
    newest: tuple[float, str] | None = None
    for p in files:
        try:
            mtime = p.stat().st_mtime
        except OSError:
            continue
        if newest is None or mtime > newest[0]:
            newest = (mtime, p.name)
    if newest is None:
        return None
    at = datetime.fromtimestamp(int(newest[0]), UTC).isoformat(timespec="seconds")
    return {"name": newest[1], "at": at}


def _created(path: Path) -> date | None:
    from harness_maker.frontmatter import split_frontmatter

    try:
        mapping = split_frontmatter(path.read_bytes()).mapping or {}
    except OSError:
        return None
    value = mapping.get("created")
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value.strip()[:10])
        except ValueError:
            return None
    return None


def parked(base: Path, slug: str, wt: Path, files: list[Path], deadline: float) -> bool:
    """A research-only task left alone past PARK_DAYS (SPEC S8); unknown is never parked."""
    research = wt / "work-docs" / f"RESEARCH-{slug}.md"
    if files != [research]:
        return False
    created = _created(research)
    if created is None or (date.today() - created).days <= PARK_DAYS:
        return False
    if time.monotonic() >= deadline:
        return False
    # Base HEAD, not a hardcoded `main`: the tip `task_land` squashes onto (_branch_drift).
    ahead = _git(base, "rev-list", "--count", f"HEAD..hm/{slug}")
    return ahead is not None and ahead.strip() == "0"


def next_stage(base: Path, slug: str, wt: Path) -> str:
    """The first pipeline stage whose artifact signal is absent (SPEC S2). Spans never count."""
    docs = wt / "work-docs"
    research = _has(docs, f"RESEARCH-{slug}.md")
    plan = _has(docs, f"PLAN-{slug}.md")
    reviews = _reviews(docs, slug)
    specs = wt / "specs"
    spec_files = (specs / f"SPEC-{slug}.md").is_file() or (
        specs / f"SPEC-{slug}.machine.yaml"
    ).is_file()
    if not (research or spec_files or plan or reviews):
        return "research"
    if not _spec_done(base, slug, wt):
        return "spec"
    if not reviews:
        return "execute"
    if _review_status(reviews[-1]) != "APPROVED":
        return "review"
    if not _verify_done(wt):
        return "verify"
    return "wrapup"


def autopilot_state(base: Path, session_id: str | None) -> dict[str, Any]:
    """Read the marker without `autopilot.status` — that call migrates and GCs markers (ADR-002)."""
    from harness_maker import autopilot

    try:
        path = autopilot.marker_path(base, session_id=session_id or None)
        if not path.is_file():
            return {"active": False}
        marker = autopilot.AutopilotMarker.model_validate(
            json.loads(path.read_text(encoding="utf-8")), strict=False
        )
        fresh = autopilot._freshness(marker.created_at) == "fresh"
        return {
            "active": fresh,
            "level": str(marker.level),
            "pipeline": [getattr(s, "value", str(s)) for s in marker.pipeline],
        }
    except Exception:  # noqa: BLE001
        return {"unavailable": "autopilot marker unreadable"}


def intent_items(base: Path) -> dict[str, Any] | None:
    """Only what needs a decision, mirrored from `hm intent status --json` (SPEC S7)."""
    if not (base / ".claude/intent.yaml").is_file():
        return None
    from harness_maker import intent_cli

    try:
        status = intent_cli.status_report(base)
    except Exception:  # noqa: BLE001
        return {"unavailable": "intent status failed"}
    if not isinstance(status, dict) or status.get("state") == "invalid":
        return {"unavailable": "intent state invalid"}
    counts: dict[str, int] = {}
    items: list[str] = []
    for key in _INTENT_KEYS:
        value = status.get(key) or []
        ids = list(value) if isinstance(value, (list, dict)) else []
        counts[key] = len(ids)
        for i in ids:
            if isinstance(i, str) and i not in items:
                items.append(i)
    return {"counts": counts, "items": items[:MAX_INTENT_ITEMS], "active": _active_rows(status)}


def _active_rows(status: dict[str, Any]) -> list[dict[str, Any]]:
    """Active intents in status order with their metric fields copied verbatim (SPEC S3)."""
    records = status.get("intents") or {}
    metrics = status.get("metrics") or {}
    rows: list[dict[str, Any]] = []
    for oid in status.get("active") or []:
        record = records.get(oid) if isinstance(records, dict) else None
        metric_id = record.get("metric_id") if isinstance(record, dict) else None
        metric = metrics.get(metric_id) if isinstance(metrics, dict) and metric_id else None
        row: dict[str, Any] = {"id": oid, "metric_id": metric_id}
        for field in ("last", "target", "gap"):
            value = metric.get(field) if isinstance(metric, dict) else None
            row[field] = NO_DATA if value is None else value
        rows.append(row)
    return rows


def recent_commits(base: Path) -> list[str]:
    out = _git(base, "log", "-3", "--format=%h %s")
    return [line for line in (out or "").splitlines() if line]


def digest(root: Path, session_id: str | None = None) -> dict[str, Any]:
    """Never raises: any failure becomes an `unavailable` field (SPEC S1)."""
    try:
        base = base_root(root)
        if base is None:
            return {"unavailable": "not a git repository"}
        rows = span_rows(base)
        worktrees = task_worktrees(base)
        entries = []
        for slug in worktrees:
            mine = [r for r in rows if r.get("task_slug") == slug]
            last_stage, last_seen, other = last_stage_and_session(mine, session_id)
            entries.append((slug, last_stage, last_seen, other))
        entries.sort(key=lambda e: e[2] or "", reverse=True)
        deadline = time.monotonic() + DEADLINE_S
        # `parked` decides the order, so it is computed for every task before the cut; its git
        # call runs only for stale research-only candidates and shares the deadline.
        files = {slug: artifact_files(slug, wt) for slug, wt in worktrees.items()}
        park = {
            slug: parked(base, slug, worktrees[slug], files[slug], deadline) for slug in worktrees
        }
        entries.sort(key=lambda e: park[e[0]])
        # The stage checks (git + tool-version subprocesses) run only for the tasks shown, and
        # stop at DEADLINE_S — a slow host yields `null`, never a stalled briefing.
        tasks = []
        for slug, last_stage, last_seen, other in entries[:MAX_TASKS]:
            stage = next_stage(base, slug, worktrees[slug]) if time.monotonic() < deadline else None
            tasks.append(
                {
                    "slug": slug,
                    "next_stage": stage,
                    "last_stage": last_stage,
                    "last_seen": last_seen,
                    "other_session": other,
                    "parked": park[slug],
                    "latest_artifact": latest_artifact(files[slug]),
                }
            )
        payload: dict[str, Any] = {
            "tasks": tasks,
            "more": max(0, len(entries) - MAX_TASKS),
            "autopilot": autopilot_state(base, session_id),
            "recent": recent_commits(base),
        }
        intents = intent_items(base)
        if intents is not None:
            payload["intents"] = intents
        return payload
    except Exception as e:  # noqa: BLE001
        return {"unavailable": f"digest failed: {type(e).__name__}"}


def _clip(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _dumps(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def _over(text: str) -> bool:
    return len(text.encode("utf-8")) > MAX_BYTES


def _clip_artifact(task: Any) -> Any:
    art = task.get("latest_artifact") if isinstance(task, dict) else None
    if not isinstance(art, dict) or not isinstance(art.get("name"), str):
        return task
    return {**task, "latest_artifact": {**art, "name": _clip(art["name"], _ID_MAX)}}


def _clip_active(row: Any) -> Any:
    if not isinstance(row, dict):
        return row
    return {
        **row,
        **{k: _clip(row[k], _ID_MAX) for k in ("id", "metric_id") if isinstance(row.get(k), str)},
    }


def render(payload: dict[str, Any]) -> str:
    """Compact JSON within MAX_BYTES (ADR-003): clip fields, then drop `recent`, then active
    intents beyond 3, then clip artifact names, then tasks down to 3, then each task's optional
    fields (`last_seen`/`last_stage`, then `latest_artifact`; `other_session` is kept) — past
    that, the old last resort (fewer tasks, then `unavailable`). Never raises."""
    try:
        return _render(payload)
    except Exception as e:  # noqa: BLE001
        return _dumps({"unavailable": f"render failed: {type(e).__name__}"})


def _render(payload: dict[str, Any]) -> str:
    p = dict(payload)
    if isinstance(p.get("recent"), list):
        p["recent"] = [_clip(str(s), _SUBJECT_MAX) for s in p["recent"]]
    intents = p.get("intents")
    if isinstance(intents, dict) and isinstance(intents.get("items"), list):
        intents = {
            **intents,
            "items": [_clip(str(i), _ID_MAX) for i in intents["items"][:MAX_INTENT_ITEMS]],
        }
        p["intents"] = intents
    # Active ids are sized like `items`: an unclipped id alone could push past the cap (9df6b033).
    if isinstance(intents, dict) and isinstance(intents.get("active"), list):
        intents = {**intents, "active": [_clip_active(r) for r in intents["active"]]}
        p["intents"] = intents
    if isinstance(p.get("tasks"), list):
        p["tasks"] = list(p["tasks"])
    text = _dumps(p)
    if _over(text) and "recent" in p:
        p.pop("recent")
        text = _dumps(p)
    if _over(text) and isinstance(intents, dict) and isinstance(intents.get("active"), list):
        p["intents"] = {**intents, "active": intents["active"][:MIN_ACTIVE_INTENTS]}
        text = _dumps(p)
    if _over(text) and isinstance(p.get("tasks"), list):
        p["tasks"] = [_clip_artifact(t) for t in p["tasks"]]
        text = _dumps(p)
    while _over(text) and isinstance(p.get("tasks"), list) and len(p["tasks"]) > MIN_TASKS:
        p["tasks"].pop()
        p["more"] = int(p.get("more") or 0) + 1
        text = _dumps(p)
    for group in _OPTIONAL_TASK_FIELDS:
        if not (_over(text) and isinstance(p.get("tasks"), list)):
            break
        p["tasks"] = [
            {k: v for k, v in t.items() if k not in group} if isinstance(t, dict) else t
            for t in p["tasks"]
        ]
        text = _dumps(p)
    # Trimming below MIN_TASKS breaks S3's floor, but a short briefing still beats `unavailable`.
    while _over(text) and isinstance(p.get("tasks"), list) and p["tasks"]:
        p["tasks"].pop()
        p["more"] = int(p.get("more") or 0) + 1
        text = _dumps(p)
    if _over(text):
        return _dumps({"unavailable": "digest too large"})
    return text
