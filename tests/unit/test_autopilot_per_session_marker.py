"""PLAN-multisession-marker-scoping Phase 1 — per-session autopilot markers.

ADR-001 the marker filename is keyed by the sanitized `claude_session_id`.
ADR-002 id-less callers share `.hm-autopilot-degraded` — a name DISTINCT from the
        legacy `.hm-autopilot`, which ADR-003 requires to be self-erasing.
ADR-003 the legacy marker is taken over once, then unlinked under a compare-and-swap.
ADR-011 per-session markers are gitignored AND are not dirt for the FINALIZE filter.
ADR-013 a session unlinks only its own key.

The load-bearing assertion here is `test_gc_unlinks_only_the_callers_own_marker`:
ADR-001 turns one file into N, and a glob-scoped GC would make every session an unlink
authority over every peer's marker — reversing ADR-001's isolation through the GC door.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from harness_maker import autopilot, worktree
from harness_maker.io_utils import atomic_write
from harness_maker.models import AtomicStage

PIPE = [AtomicStage.RESEARCH, AtomicStage.SPEC, AtomicStage.PLAN]
SESS_A = "aaaa1111-2222-3333"
SESS_B = "bbbb4444-5555-6666"


@pytest.fixture(autouse=True)
def _no_ambient_session_id(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every id in this module is explicit — an ambient env id would mask a miss."""
    monkeypatch.delenv("HM_SESSION_ID", raising=False)


def _project(tmp_path: Path) -> Path:
    (tmp_path / ".claude").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".claude" / "harness.yaml").write_text("preset: Side\n", encoding="utf-8")
    return tmp_path


def _payload(root: Path, **over: object) -> dict[str, object]:
    base: dict[str, object] = {
        "session_uuid": worktree._current_session_uuid(root),
        "level": "auto_safe",
        "pipeline": [s.value for s in PIPE],
        "created_at": datetime.now(UTC).isoformat(),
        "claude_session_id": None,
    }
    base.update(over)
    return base


def _legacy(root: Path) -> Path:
    return root / ".claude" / ".hm-autopilot"


# --- ADR-001: collisions become impossible ------------------------------------


def test_two_sessions_arm_in_one_project(tmp_path: Path) -> None:
    root = _project(tmp_path)
    autopilot.write(root, level="auto_safe", pipeline=PIPE, claude_session_id=SESS_A)
    autopilot.write(root, level="auto_safe", pipeline=PIPE, claude_session_id=SESS_B)
    assert autopilot.status(root, session_id=SESS_A)["active"] is True
    assert autopilot.status(root, session_id=SESS_B)["active"] is True


def test_two_autoarm_sessionstarts_both_arm(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """ADR-009 — the `autopilot_persistent` path, which arms with no picker in front of it.

    `autopilot.write` called directly (the test above) bypasses `autopilot_autoarm`, whose
    `MarkerOwnedByAnotherSessionError` branch DECLINES to arm. That branch is what actually
    produced this PLAN's opening symptom, so Success Criterion #1 is only satisfied when the
    hook itself arms twice.
    """
    from harness_maker.hooks import autopilot_autoarm

    root = _project(tmp_path)
    (root / ".claude" / "harness.yaml").write_text(
        "autonomy:\n  level: auto_safe\n  autopilot_persistent: true\n", encoding="utf-8"
    )
    assert autopilot_autoarm.arm_if_persistent(root, claude_session_id=SESS_A) is True
    assert autopilot_autoarm.arm_if_persistent(root, claude_session_id=SESS_B) is True
    assert autopilot.status(root, session_id=SESS_A)["active"] is True
    assert autopilot.status(root, session_id=SESS_B)["active"] is True
    assert "not arming" not in caplog.text


def test_marker_filenames_are_distinct_per_session(tmp_path: Path) -> None:
    root = _project(tmp_path)
    a = autopilot.marker_path(root, session_id=SESS_A)
    b = autopilot.marker_path(root, session_id=SESS_B)
    assert a != b
    assert a.parent == root / ".claude"
    assert a.name.startswith(".hm-autopilot-")


def test_clear_removes_only_the_callers_marker(tmp_path: Path) -> None:
    root = _project(tmp_path)
    autopilot.write(root, level="auto_safe", pipeline=PIPE, claude_session_id=SESS_A)
    autopilot.write(root, level="auto_safe", pipeline=PIPE, claude_session_id=SESS_B)
    autopilot.clear(root, session_id=SESS_A)
    assert not autopilot.marker_path(root, session_id=SESS_A).exists()
    assert autopilot.marker_path(root, session_id=SESS_B).exists()


# --- ADR-002: the degraded fallback is NOT the legacy name ---------------------


def test_idless_callers_share_a_named_degraded_marker(tmp_path: Path) -> None:
    root = _project(tmp_path)
    p = autopilot.marker_path(root, session_id=None)
    assert p.name == ".hm-autopilot-degraded"
    assert p != _legacy(root)


def test_a_session_id_cannot_collide_with_the_degraded_name(tmp_path: Path) -> None:
    """`degraded` is not a tame hex id, so it is hashed rather than used verbatim."""
    root = _project(tmp_path)
    assert autopilot.marker_path(root, session_id="degraded") != autopilot.marker_path(
        root, session_id=None
    )


# --- ADR-003: one-shot legacy takeover, compare-and-swap ----------------------


def test_legacy_marker_is_taken_over_then_unlinked(tmp_path: Path) -> None:
    root = _project(tmp_path)
    _legacy(root).write_text(json.dumps(_payload(root, claude_session_id=SESS_A)), encoding="utf-8")
    assert autopilot.status(root, session_id=SESS_A)["active"] is True
    assert not _legacy(root).exists()
    assert autopilot.marker_path(root, session_id=SESS_A).is_file()


def test_legacy_marker_owned_by_a_peer_is_left_alone(tmp_path: Path) -> None:
    root = _project(tmp_path)
    _legacy(root).write_text(json.dumps(_payload(root, claude_session_id=SESS_B)), encoding="utf-8")
    assert autopilot.status(root, session_id=SESS_A)["active"] is False
    assert _legacy(root).exists()


def test_legacy_takeover_does_not_delete_a_marker_that_changed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CAS: a replacement landing between the read and the unlink must survive."""
    root = _project(tmp_path)
    _legacy(root).write_text(json.dumps(_payload(root, claude_session_id=SESS_A)), encoding="utf-8")
    real = atomic_write

    def _mutating(path: Path, content: str) -> None:
        real(path, content)
        _legacy(root).write_text(
            json.dumps(_payload(root, claude_session_id=SESS_B)), encoding="utf-8"
        )

    monkeypatch.setattr(autopilot, "atomic_write", _mutating)
    autopilot._takeover_legacy(root, session_id=SESS_A)
    assert _legacy(root).exists()


def test_legacy_takeover_never_clobbers_an_existing_per_session_marker(tmp_path: Path) -> None:
    root = _project(tmp_path)
    autopilot.write(root, level="full", pipeline=PIPE, claude_session_id=SESS_A)  # type: ignore[arg-type]  # legacy level, normalized on write
    _legacy(root).write_text(
        json.dumps(_payload(root, claude_session_id=SESS_A, level="gated")), encoding="utf-8"
    )
    autopilot._takeover_legacy(root, session_id=SESS_A)
    marker = autopilot.load(root, session_id=SESS_A)
    assert marker is not None
    assert marker.level == "auto_safe"  # B1: `full` demotes to `auto_safe` (ADR-001)


# --- ADR-013: self-only GC ----------------------------------------------------


def test_gc_unlinks_only_the_callers_own_marker(tmp_path: Path) -> None:
    root = _project(tmp_path)
    old = (datetime.now(UTC) - timedelta(hours=48)).isoformat()
    autopilot.write(root, level="auto_safe", pipeline=PIPE, now=old, claude_session_id=SESS_A)
    autopilot.write(root, level="auto_safe", pipeline=PIPE, now=old, claude_session_id=SESS_B)
    assert autopilot.gc_stale_marker(root, session_id=SESS_A) is True
    assert not autopilot.marker_path(root, session_id=SESS_A).exists()
    assert autopilot.marker_path(root, session_id=SESS_B).exists()


# --- ADR-011: churn / gitignore ----------------------------------------------


def test_per_session_marker_is_not_user_dirt_for_finalize(tmp_path: Path) -> None:
    """The FINALIZE filter, not the create guard: create forgives all of `.claude/`."""
    name = autopilot.marker_path(_project(tmp_path), session_id=SESS_A).name
    assert worktree._is_harness_artifact(f"?? .claude/{name}") is True
    assert worktree._is_harness_artifact(f"?? .claude/{autopilot._DEGRADED_BASENAME}") is True
    assert worktree._is_harness_artifact("?? .claude/.hm-autopilot") is True


def test_marker_glob_is_gitignored_and_the_dead_literal_is_gone() -> None:
    assert ".claude/.hm-autopilot*" in worktree._HARNESS_GITIGNORE_PATTERNS
    assert ".claude/.hm-autopilot" not in worktree._HARNESS_CHURN_FILES


def test_shipped_gitignore_glob_covers_both_the_legacy_and_a_per_session_name(
    tmp_path: Path,
) -> None:
    """The SHIPPED pattern must have no hyphen before the `*`.

    `.claude/.hm-autopilot-*` would stop ignoring the bare legacy `.claude/.hm-autopilot`,
    which ADR-003 keeps alive until every project has taken it over. Derived from
    `_HARNESS_GITIGNORE_PATTERNS` rather than restated, so narrowing the shipped glob
    fails here instead of asserting a property of `fnmatch`.
    """
    from fnmatch import fnmatch

    per_session = f".claude/{autopilot.marker_path(_project(tmp_path), session_id=SESS_A).name}"
    patterns = [p for p in worktree._HARNESS_GITIGNORE_PATTERNS if ".hm-autopilot" in p]
    assert patterns, "no .hm-autopilot pattern is shipped to .gitignore at all"
    assert any(fnmatch(".claude/.hm-autopilot", p) for p in patterns)
    assert any(fnmatch(per_session, p) for p in patterns)
    assert any(fnmatch(f".claude/{autopilot._DEGRADED_BASENAME}", p) for p in patterns)


# --- review round 1 regressions --------------------------------------------------


def test_autopilot_off_disarms_the_project_without_a_session_id(tmp_path: Path) -> None:
    """SR-1, round 2. Round 1's `off` printed success over a no-op. The first fix made it
    exit 4 and say so — honest, but the chain still auto-advanced for the full 18h TTL with
    manual file deletion as the only working disarm. A kill switch that cannot kill is the
    defect; telling the truth about it is not the fix. ADR-013 scopes a SESSION's unlink
    authority so no peer can silently disarm another; an operator typing the README's
    command is not a peer."""
    root = _project(tmp_path)
    autopilot.write(root, level="auto_safe", pipeline=PIPE, claude_session_id=SESS_A)
    autopilot.write(root, level="auto_safe", pipeline=PIPE, claude_session_id=SESS_B)
    rc = autopilot._cli_off(root, session_id=None, emit=lambda m, e: None)
    assert rc == 0
    assert autopilot.status(root, session_id=SESS_A)["active"] is False
    assert autopilot.status(root, session_id=SESS_B)["active"] is False


def test_autopilot_off_with_a_session_id_disarms_only_that_session(tmp_path: Path) -> None:
    """The scoped form stays available for a stage that means "disarm ME"."""
    root = _project(tmp_path)
    autopilot.write(root, level="auto_safe", pipeline=PIPE, claude_session_id=SESS_A)
    autopilot.write(root, level="auto_safe", pipeline=PIPE, claude_session_id=SESS_B)
    assert autopilot._cli_off(root, session_id=SESS_A, emit=lambda m, e: None) == 0
    assert autopilot.status(root, session_id=SESS_A)["active"] is False
    assert autopilot.status(root, session_id=SESS_B)["active"] is True


def test_autopilot_off_is_idempotent_when_nothing_is_armed(tmp_path: Path) -> None:
    root = _project(tmp_path)
    assert autopilot._cli_off(root, session_id=None, emit=lambda m, e: None) == 0
    assert autopilot._cli_off(root, session_id=SESS_A, emit=lambda m, e: None) == 0


def test_the_dotform_and_typer_entry_points_both_disarm(tmp_path: Path) -> None:
    """Round 2: exit codes were pinned only on `_cli_off`, so either CLI could stop calling
    it without a test dying — and those two spellings have drifted before."""
    from typer.testing import CliRunner

    from harness_maker.cli import app

    root = _project(tmp_path)
    autopilot.write(root, level="auto_safe", pipeline=PIPE, claude_session_id=SESS_A)
    assert autopilot.main(["off", "--root", str(root)]) == 0
    assert autopilot.status(root, session_id=SESS_A)["active"] is False

    autopilot.write(root, level="auto_safe", pipeline=PIPE, claude_session_id=SESS_B)
    result = CliRunner().invoke(app, ["autopilot", "off", "--root", str(root)])
    assert result.exit_code == 0, result.output
    assert autopilot.status(root, session_id=SESS_B)["active"] is False


def test_expired_markers_are_reaped_and_live_ones_are_not(tmp_path: Path) -> None:
    """SR-3. `gc_stale_marker` only ever collects a marker when its OWN session runs another
    command, and a crashed session never does — so `.claude/` grew one file per session
    forever. The sweep is TTL-only: a live peer's marker is untouchable."""
    root = _project(tmp_path)
    old = (datetime.now(UTC) - timedelta(hours=48)).isoformat()
    autopilot.write(root, level="auto_safe", pipeline=PIPE, now=old, claude_session_id=SESS_A)
    autopilot.write(root, level="auto_safe", pipeline=PIPE, claude_session_id=SESS_B)
    removed = autopilot.gc_expired_markers(root)
    assert removed == [autopilot.marker_path(root, session_id=SESS_A).name]
    assert autopilot.marker_path(root, session_id=SESS_B).exists(), "a LIVE peer was reaped"


def test_the_reaper_never_deletes_a_future_dated_marker(tmp_path: Path) -> None:
    """Clock skew must not let an operator sweep disarm a peer — the property ADR-013's
    restraint actually protects."""
    root = _project(tmp_path)
    ahead = (datetime.now(UTC) + timedelta(hours=5)).isoformat()
    autopilot.write(root, level="auto_safe", pipeline=PIPE, now=ahead, claude_session_id=SESS_A)
    assert autopilot.gc_expired_markers(root) == []
    assert autopilot.marker_path(root, session_id=SESS_A).exists()


def test_prune_stale_reaps_an_expired_autopilot_marker(tmp_path: Path) -> None:
    """SR-3's only delivery path. The reaper had a unit test; its WIRING into `prune_stale`
    — the thing that actually makes it run — did not."""
    import subprocess

    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "main", "."], cwd=repo, check=True, capture_output=True)
    (repo / ".claude").mkdir()
    (repo / ".claude" / "harness.yaml").write_text("preset: Side\n", encoding="utf-8")
    old = (datetime.now(UTC) - timedelta(hours=48)).isoformat()
    autopilot.write(repo, level="auto_safe", pipeline=PIPE, now=old, claude_session_id=SESS_A)
    autopilot.write(repo, level="auto_safe", pipeline=PIPE, claude_session_id=SESS_B)
    report = worktree.prune_stale(repo)
    assert not autopilot.marker_path(repo, session_id=SESS_A).exists()
    assert autopilot.marker_path(repo, session_id=SESS_B).exists()
    assert any(p.name.startswith(".hm-autopilot-") for p in report.removed_markers)
