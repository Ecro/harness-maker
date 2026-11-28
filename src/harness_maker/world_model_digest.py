"""The Maker router's briefing: one read-only, capped JSON digest of the project's task state."""

from __future__ import annotations

import json
import subprocess
import time
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

PIPELINE: tuple[str, ...] = ("research", "spec", "execute", "review", "verify", "wrapup")
MAX_BYTES = 1500
MAX_TASKS = 5
MIN_OPEN_INTENTS = 3
MIN_TASKS = 3
# Dropped per task, group by group, before the task floor gives way (REVIEW dbe5ddc7). Timing
# goes first; `other_session` and `interrupted` are never dropped — Briefing shows the first and
# Resume picks the single cut-off task by the second (SPEC-maker-resume-no-ask).
_OPTIONAL_TASK_FIELDS: tuple[tuple[str, ...], ...] = (
    ("last_seen", "last_stage"),
    ("latest_artifact",),
)
PARK_DAYS = 7
NO_DATA = "—"
_SUBJECT_MAX = 60
_ID_MAX = 40
# Total budget for the artifact checks; past it a task reports `next_stage: null` (REVIEW 6d4374d1).
DEADLINE_S = 5.0


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


def interrupted(rows: list[dict[str, Any]], slug: str) -> bool:
    """The task's newest span row is a `start` that its session never followed with any row.

    Claude Code's Stop hook writes one `end` for the session's open span when a turn finishes,
    so a `start` its session never followed means the stage was cut off (or is running now) —
    the task a resume ask is about. Undecidable cases read False: a start with no session id
    (its `end` may be session-less too, and session-less ends carry no slug), and a ledger with
    no `end` at all (Codex writes none, so every Codex task would read as cut off).
    """
    if not any(r.get("event") == "end" for r in rows):
        return False
    mine = [(i, r) for i, r in enumerate(rows) if r.get("task_slug") == slug]
    if not mine:
        return False

    def key(ir: tuple[int, dict[str, Any]]) -> tuple[str, int]:
        return str(ir[1].get("ts") or ""), ir[0]  # the order last_stage_and_session uses

    at, newest = max(mine, key=key)
    session = newest.get("session_id")
    if newest.get("event") != "start" or not isinstance(session, str) or not session:
        return False
    # One `end` closes a turn that started stages on two tasks; it carries only the last slug.
    after = key((at, newest))
    return not any(
        r.get("session_id") == session and key((i, r)) > after for i, r in enumerate(rows)
    )


def _spec_done(base: Path, slug: str, wt: Path) -> bool:
    from harness_maker import spec_machine

    try:
        state = spec_machine.approval_state(base, slug, checkout=wt).state
    except Exception:  # noqa: BLE001 — a broken SPEC is "not done", never a digest failure
        return False
    return state in ("approved", "exempt")


def _has(directory: Path, pattern: str) -> bool:
    return directory.is_dir() and any(directory.glob(pattern))


def _reviews(docs: Path, slug: str) -> list[Path]:
    # One lister for the digest and the light-lane boundary (SPEC-hm-light-lane-s3a ADR-003).
    from harness_maker import light_lane

    return light_lane.review_records(docs, slug)


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
    # Review and verify were retired in 0.64.0 (SPEC-maker-advance IRR-002).
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
    """Open goals with their metric's last/target/gap, from `hm intent status --json`."""
    if not (base / ".claude/intent.yaml").is_file():
        return None
    from harness_maker import intent_cli

    try:
        status = intent_cli.status_report(base)
    except Exception:  # noqa: BLE001
        return {"unavailable": "intent status failed"}
    if not isinstance(status, dict) or status.get("state") == "invalid":
        return {"unavailable": "intent state invalid"}
    return {"open": _open_rows(status)}


def _open_rows(status: dict[str, Any]) -> list[dict[str, Any]]:
    """Open goals in status order with their metric fields copied verbatim."""
    records = status.get("intents") or {}
    metrics = status.get("metrics") or {}
    rows: list[dict[str, Any]] = []
    for oid in status.get("open") or []:
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
            entries.append((slug, last_stage, last_seen, other, interrupted(rows, slug)))
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
        for slug, last_stage, last_seen, other, cut in entries[:MAX_TASKS]:
            stage = next_stage(base, slug, worktrees[slug]) if time.monotonic() < deadline else None
            task: dict[str, Any] = {
                "slug": slug,
                "next_stage": stage,
                "last_stage": last_stage,
                "last_seen": last_seen,
                "other_session": other,
                "parked": park[slug],
                "latest_artifact": latest_artifact(files[slug]),
            }
            # Only when true: 19 bytes a task, and Maker reads absence as "not cut off".
            if cut:
                task["interrupted"] = True
            tasks.append(task)
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


def _clip_open(row: Any) -> Any:
    if not isinstance(row, dict):
        return row
    return {
        **row,
        **{k: _clip(row[k], _ID_MAX) for k in ("id", "metric_id") if isinstance(row.get(k), str)},
    }


def render(payload: dict[str, Any]) -> str:
    """Compact JSON within MAX_BYTES (ADR-003): clip fields, then drop `recent`, then open
    intents beyond 3, then clip artifact names, then tasks down to 3, then each task's optional
    fields (`last_seen`/`last_stage`, then `latest_artifact`; `other_session` and `interrupted`
    are kept) — past
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
    # Ids are clipped: an unclipped id alone could push past the cap (9df6b033).
    if isinstance(intents, dict) and isinstance(intents.get("open"), list):
        intents = {**intents, "open": [_clip_open(r) for r in intents["open"]]}
        p["intents"] = intents
    if isinstance(p.get("tasks"), list):
        p["tasks"] = list(p["tasks"])
    text = _dumps(p)
    if _over(text) and "recent" in p:
        p.pop("recent")
        text = _dumps(p)
    if _over(text) and isinstance(intents, dict) and isinstance(intents.get("open"), list):
        p["intents"] = {**intents, "open": intents["open"][:MIN_OPEN_INTENTS]}
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
