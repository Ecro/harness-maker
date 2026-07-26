"""Phase 5 (ADR-002/004/006): flag-on stage preflight helper.

`task_preflight(base, slug, session_uuid=...)` idempotently ensures the
persistent `.worktrees/<slug>/` task worktree (Phase 2), reclaims dead registry
rows (Phase 1), and returns `(wt_path, warnings)` where warnings surface other
active sessions + a drift notice when the task branch fell behind the base tip.
The `task-preflight` CLI subcommand prints the WT path to stdout (for `<WT>`
capture) and warnings to stderr.
"""

from __future__ import annotations

import subprocess
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from harness_maker import worktree
from harness_maker.stage_spans import (
    UNKNOWN_STAGE,
    SpanEvent,
    attribute_turns,
    ledger_path,
    read_events,
)


def _git(args: list[str], cwd: Path) -> str:
    cp = subprocess.run(  # noqa: S603
        ["git", *args], cwd=str(cwd), check=True, capture_output=True, text=True
    )
    return cp.stdout.strip()


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(["init", "-b", "main"], repo)
    _git(["config", "user.email", "t@e.com"], repo)
    _git(["config", "user.name", "T"], repo)
    (repo / ".gitignore").write_text(".worktrees/\n.claude/\n")
    (repo / "README.md").write_text("x\n")
    _git(["add", "."], repo)
    _git(["commit", "-m", "init"], repo)
    return repo


def _branches(repo: Path) -> list[str]:
    return _git(["branch", "--format=%(refname:short)"], repo).split()


# ── span emission (Phase 2 of PLAN-economics-attribution-and-carry) ──────────
#
# ADR-008: the span START is a SIDE EFFECT of this call, not a separate prose
# instruction. That is the whole argument — a prose line can be skipped silently,
# whereas a stage that skips preflight does not get its `<WT>` and visibly degrades.


def _spans(repo: Path) -> list[SpanEvent]:
    events, _ = read_events(ledger_path(repo))
    return events


class _T:
    """Minimal turn for feeding the consumer — see the dangling-span test."""

    def __init__(self, ts: datetime, session_id: str | None = "S1") -> None:
        self.ts = ts
        self.session_id = session_id


def test_preflight_emits_a_start_span_carrying_the_supplied_stage(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    worktree.task_preflight(repo, "feat-x", session_uuid="u-1", stage="hm:wrapup")
    events = _spans(repo)
    assert [e.event for e in events] == ["start"]
    assert events[0].stage == "hm:wrapup"
    assert events[0].task_slug == "feat-x"


def test_preflight_without_a_stage_emits_an_empty_stage_the_reader_counts(
    tmp_path: Path,
) -> None:
    """An un-re-rendered harness omits `--stage`. Emitting NOTHING would make that
    harness indistinguishable from one whose stage never ran. The round-trip through
    the CONSUMER is what makes the empty string non-magic: normalising to the sentinel
    at write time would leave `unknown_stage_emissions` reading 0 forever.
    """
    repo = _repo(tmp_path)
    worktree.task_preflight(repo, "feat-x", session_uuid="u-1")
    events = _spans(repo)
    assert [e.stage for e in events] == [""]
    res = attribute_turns(
        [_T(events[0].ts + timedelta(seconds=1))], events, max_turns=400, max_min=240.0
    )
    assert res.unknown_stage_emissions == 1
    assert res.stages == (UNKNOWN_STAGE,)


def test_each_fused_stage_appends_its_own_span_to_the_base_ledger(tmp_path: Path) -> None:
    """A fused workflow claims once per fused stage, so the ledger must ACCUMULATE
    rather than be rewritten, and every record must name the base as its root.

    Note on scope: an earlier version of this test passed the WORKTREE as `base_dir`
    to vary "cwd inside a worktree". That call does not exist in production — the
    rendered line is a Claude Code `!` command, which always runs at the project
    root, so `$(pwd)` is the base on every stage including fused ones. (It also
    fails outright, trying to nest `.worktrees/feat-x/.worktrees/feat-x`.) The
    resolver's worktree behaviour is covered where it can actually be exercised:
    `test_stage_spans.py::test_emit_from_inside_a_worktree_appends_to_the_base_ledger`
    drives `emit_event` from a real linked worktree. Here the meaningful assertion is
    on record CONTENT, not on file existence.
    """
    repo = _repo(tmp_path)
    worktree.task_preflight(repo, "feat-x", session_uuid="u-1", stage="hm:execute")
    worktree.task_preflight(repo, "feat-x", session_uuid="u-1", stage="hm:review")

    events = _spans(repo)
    assert [e.stage for e in events] == ["hm:execute", "hm:review"]
    assert {e.base_root for e in events} == {str(repo.resolve())}
    assert {e.event for e in events} == {"start"}


def test_a_failed_preflight_never_attributes_later_turns_to_its_stage(
    tmp_path: Path,
) -> None:
    """A span opened by a stage that never ran would be closed only by next-start,
    session-end, or the 400-turn cap — i.e. it could swallow 400 unrelated turns.

    Asserted through the CONSUMER rather than by counting records: emitting a start
    and an immediate `end` on the failure path is an equally valid implementation,
    and a record-count assertion would wrongly forbid it.
    """
    repo = _repo(tmp_path)
    worktree.task_preflight(repo, "feat-x", session_uuid="u-1", stage="hm:plan")
    with pytest.raises(worktree.SharedSlugError):
        worktree.task_preflight(repo, "feat-x", session_uuid="u-2", stage="hm:review")

    events = _spans(repo)
    later = _T(events[0].ts + timedelta(minutes=5))
    res = attribute_turns([later], events, max_turns=400, max_min=240.0)
    assert res.stages == ("hm:plan",)


# ── creation + idempotency ───────────────────────────────────────────────────


def test_preflight_creates_and_returns_task_worktree(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    wt, warnings = worktree.task_preflight(repo, "feat-x", session_uuid="u-1")
    assert wt == worktree.task_worktree_path(repo, "feat-x")
    assert wt.is_dir()
    assert worktree._current_branch(wt) == "hm/feat-x"
    rows = worktree._read_sessions(repo)
    assert any(r.branch == "hm/feat-x" and r.session_uuid == "u-1" for r in rows)
    # fresh task off the base tip → no drift warning
    assert not any("behind" in w for w in warnings)


def test_preflight_idempotent_reuse(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    wt1, _ = worktree.task_preflight(repo, "feat-x", session_uuid="u-1")
    wt2, _ = worktree.task_preflight(repo, "feat-x", session_uuid="u-1")
    assert wt1 == wt2
    assert _branches(repo).count("hm/feat-x") == 1
    rows = worktree._read_sessions(repo)
    assert len([r for r in rows if r.branch == "hm/feat-x"]) == 1


# ── active-session surface ───────────────────────────────────────────────────


def test_preflight_surfaces_foreign_active_session(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    # a different live session already holds another task
    worktree.task_create(repo, "other-task", session_uuid="u-foreign")
    _, warnings = worktree.task_preflight(repo, "feat-x", session_uuid="u-mine")
    surfaced = " ".join(warnings)
    assert "other-task" in surfaced
    assert "u-mine" not in surfaced  # never lists our own session


def test_preflight_no_foreign_warning_when_alone(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    _, warnings = worktree.task_preflight(repo, "feat-x", session_uuid="u-1")
    assert not any("active session" in w for w in warnings)


def test_preflight_concurrent_same_slug_session_hard_fails(tmp_path: Path) -> None:
    # ADR-001: a SECOND live session entering the SAME task now HARD-FAILS (was a
    # warn-only surface) — this is the silent-share path Fix 1 closes.
    repo = _repo(tmp_path)
    worktree.task_create(repo, "feat-x", session_uuid="u-first")
    with pytest.raises(worktree.SharedSlugError):
        worktree.task_preflight(repo, "feat-x", session_uuid="u-second")
    # The escape hatch keeps the collision warning + lets the sessions coexist.
    _, warnings = worktree.task_preflight(
        repo, "feat-x", session_uuid="u-second", allow_shared=True
    )
    collision = [w for w in warnings if "already hold task" in w]
    assert collision, f"expected a same-slug collision warning, got {warnings!r}"
    assert "feat-x" in collision[0]


def test_preflight_idempotent_reuse_no_self_collision(tmp_path: Path) -> None:
    # Same uuid re-entering its own task must NOT self-report as a collision.
    repo = _repo(tmp_path)
    worktree.task_preflight(repo, "feat-x", session_uuid="u-1")
    _, warnings = worktree.task_preflight(repo, "feat-x", session_uuid="u-1")
    assert not any("already hold task" in w for w in warnings)


# ── drift detection ──────────────────────────────────────────────────────────


def test_branch_drift_counts_behind_and_ahead(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    wt = worktree.task_create(repo, "feat-x", session_uuid="u-1")
    # one commit ahead on the task branch
    (wt / "feature.py").write_text("task\n")
    _git(["add", "-A"], wt)
    _git(["commit", "-m", "wip(execute): feat-x"], wt)
    # advance the base by two commits → branch is 2 behind
    (repo / "a.txt").write_text("a\n")
    _git(["add", "-A"], repo)
    _git(["commit", "-m", "base 1"], repo)
    (repo / "b.txt").write_text("b\n")
    _git(["add", "-A"], repo)
    _git(["commit", "-m", "base 2"], repo)
    behind, ahead = worktree._branch_drift(repo, "hm/feat-x")
    assert behind == 2
    assert ahead == 1


def test_preflight_auto_refreshes_on_clean_drift(tmp_path: Path) -> None:
    # ADR-002: a clean behind branch is auto-refreshed at preflight (was a manual
    # "run task-refresh" warning). Drift is resolved by the time preflight returns.
    repo = _repo(tmp_path)
    worktree.task_create(repo, "feat-x", session_uuid="u-1")
    (repo / "a.txt").write_text("a\n")
    _git(["add", "-A"], repo)
    _git(["commit", "-m", "base advance"], repo)
    _, warnings = worktree.task_preflight(repo, "feat-x", session_uuid="u-1")
    assert any("auto-refreshed" in w for w in warnings), warnings
    assert worktree._branch_drift(repo, "hm/feat-x")[0] == 0


# ── CLI dispatch wiring (Phase-4 dead-entry-point lesson) ─────────────────────


def test_preflight_cli_dispatch_is_wired(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    rc = worktree.main(["task-preflight", "feat-x", str(repo)])
    assert rc == 0
    assert worktree.task_worktree_path(repo, "feat-x").is_dir()


def test_preflight_cli_usage_on_missing_slug(tmp_path: Path) -> None:
    rc = worktree.main(["task-preflight"])
    assert rc == 2
