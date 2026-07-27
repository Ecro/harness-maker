"""Regression tests for REVIEW round-2 fixes (the three open P1 findings).

1. classifier state leaked across concurrent sessions (codex P1)
2. a worktree `--root` silently truncated the report (codex P1 + code-reviewer P2)
3. the harness.yaml tuning surface reached the report untested (code-reviewer P1)
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from harness_maker.economics import TokenUsage, TurnRecord, classify_turns, main
from harness_maker.economics_source import (
    discover_transcript_dirs,
    encode_project_dir,
    load_turns,
    resolve_project_root,
)

_T0 = datetime(2026, 7, 25, 12, 0, 0, tzinfo=UTC)
_NOW = "2026-07-25T23:00:00+00:00"


def _turn(idx: int, **kw: object) -> TurnRecord:
    base: dict[str, object] = {
        "session_id": "s1",
        "ts": _T0 + timedelta(minutes=idx),
        "model": "claude-opus-5",
        "usage": TokenUsage(output_tokens=100),
        "task_slug": "demo",
        "cwd": "/repo/proj",
        "git_branch": "hm/demo",
    }
    base.update(kw)
    return TurnRecord(**base)  # type: ignore[arg-type]


# ------------------------------------------------- 1. session-scoped verify window


def test_a_peer_sessions_review_does_not_absolve_my_rewrite() -> None:
    """Concurrent sessions on one task are a supported workflow; turns interleave."""
    labels = classify_turns(
        [
            _turn(0, session_id="A", written_paths=("a.py",)),
            _turn(1, session_id="B", attribution_skill="hm:review"),
            _turn(2, session_id="A", written_paths=("a.py",)),
        ]
    )
    assert labels == ["PRODUCE", "VERIFY", "REWORK"]


def test_my_own_review_still_absolves_my_rewrite() -> None:
    labels = classify_turns(
        [
            _turn(0, session_id="A", written_paths=("a.py",)),
            _turn(1, session_id="A", attribution_skill="hm:review"),
            _turn(2, session_id="A", written_paths=("a.py",)),
        ]
    )
    assert labels == ["PRODUCE", "VERIFY", "PRODUCE"]


def test_write_history_stays_task_scoped_across_sessions() -> None:
    """A task worktree spans sessions — a later session's rewrite IS still rework."""
    labels = classify_turns(
        [
            _turn(0, session_id="A", written_paths=("a.py",)),
            _turn(1, session_id="B", written_paths=("a.py",)),
        ]
    )
    assert labels == ["PRODUCE", "REWORK"]


# ------------------------------------------------- 2. worktree root resolution


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("/repo/proj", "/repo/proj"),
        ("/repo/proj/.worktrees/demo", "/repo/proj"),
        ("/repo/proj/.worktrees/demo/src", "/repo/proj"),
        ("/repo/proj/worktrees/demo", "/repo/proj/worktrees/demo"),  # not the marker dir
    ],
)
def test_resolve_project_root(raw: str, expected: str) -> None:
    assert resolve_project_root(Path(raw)) == Path(expected)


def test_discovery_from_inside_a_worktree_still_finds_the_base_and_siblings() -> None:
    fixtures = Path(__file__).parents[1] / "fixtures" / "transcripts"
    from_worktree = discover_transcript_dirs(
        Path("/repo/proj/.worktrees/demo"), transcript_root=fixtures
    )
    from_base = discover_transcript_dirs(Path("/repo/proj"), transcript_root=fixtures)
    assert {p.name for p in from_worktree} == {"-repo-proj", "-repo-proj--worktrees-demo"}
    assert from_worktree == from_base


def test_loading_from_inside_a_worktree_returns_the_same_turns_as_from_base() -> None:
    fixtures = Path(__file__).parents[1] / "fixtures" / "transcripts"
    kw = {"transcript_root": fixtures, "days": 3650, "now": datetime(2026, 7, 26, tzinfo=UTC)}
    from_base = load_turns(Path("/repo/proj"), **kw)  # type: ignore[arg-type]
    from_wt = load_turns(Path("/repo/proj/.worktrees/demo"), **kw)  # type: ignore[arg-type]
    assert len(from_base.turns) == 7
    assert [t.ts for t in from_wt.turns] == [t.ts for t in from_base.turns]
    assert [t.written_paths for t in from_wt.turns] == [t.written_paths for t in from_base.turns]


# ------------------------------------------------- 3. every config knob, end to end


def _project_with_transcripts(tmp_path: Path, *, harness_yaml: str) -> tuple[Path, Path]:
    """Build a project root whose ENCODED name matches a transcript dir we control."""
    root = tmp_path / "proj"
    (root / ".claude").mkdir(parents=True)
    (root / ".claude" / "harness.yaml").write_text(harness_yaml, encoding="utf-8")

    store = tmp_path / "projects"
    (store / encode_project_dir(root)).mkdir(parents=True)
    lines = [
        # attributed anchor, then two unattributed turns 1 and 30 minutes later
        {"skill": "hm:execute", "minute": 0},
        {"skill": None, "minute": 1},
        {"skill": None, "minute": 30},
    ]
    payload = ""
    for row in lines:
        rec: dict[str, object] = {
            "type": "assistant",
            "sessionId": "s1",
            "timestamp": (_T0 + timedelta(minutes=int(row["minute"] or 0))).isoformat(),
            "cwd": str(root),
            "gitBranch": "hm/demo",
            "message": {"model": "claude-opus-5", "usage": {"output_tokens": 1000}},
        }
        if row["skill"]:
            rec["attributionSkill"] = row["skill"]
        payload += json.dumps(rec) + "\n"
    (store / encode_project_dir(root) / "s1.jsonl").write_text(payload, encoding="utf-8")
    return root, store


def _report(capsys: pytest.CaptureFixture[str], root: Path, store: Path) -> dict[str, object]:
    code = main(["report", "--root", str(root), "--transcript-root", str(store), "--now", _NOW])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert isinstance(payload["report"], dict)
    return payload["report"]  # type: ignore[return-value]


def test_adjacency_estimate_knob_reaches_the_report(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    root, store = _project_with_transcripts(
        tmp_path, harness_yaml="economics:\n  adjacency_estimate: false\n"
    )
    assert _report(capsys, root, store)["estimated_attribution_usd"] == {}


def test_adjacency_max_gap_min_knob_reaches_the_report(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    """Turn at +30min is inside a 60-min bound and outside a 5-min one."""
    wide_root, wide_store = _project_with_transcripts(
        tmp_path / "wide", harness_yaml="economics:\n  adjacency_max_gap_min: 60.0\n"
    )
    wide = _report(capsys, wide_root, wide_store)
    narrow_root, narrow_store = _project_with_transcripts(
        tmp_path / "narrow", harness_yaml="economics:\n  adjacency_max_gap_min: 5.0\n"
    )
    narrow = _report(capsys, narrow_root, narrow_store)
    assert wide["estimator_coverage"] == pytest.approx(1.0)
    assert narrow["estimator_coverage"] == pytest.approx(0.5)


def test_adjacency_max_turns_knob_reaches_the_report(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    root, store = _project_with_transcripts(
        tmp_path,
        harness_yaml="economics:\n  adjacency_max_turns: 1\n  adjacency_max_gap_min: 600.0\n",
    )
    # only the turn 1 step away from the anchor may be claimed
    assert _report(capsys, root, store)["estimator_coverage"] == pytest.approx(0.5)


def test_idle_gap_cap_min_knob_reaches_the_report(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    small_root, small_store = _project_with_transcripts(
        tmp_path / "small", harness_yaml="economics:\n  idle_gap_cap_min: 1.0\n"
    )
    big_root, big_store = _project_with_transcripts(
        tmp_path / "big", harness_yaml="economics:\n  idle_gap_cap_min: 10.0\n"
    )
    small = _report(capsys, small_root, small_store)["wall_clock_seconds_by_scope"]
    big = _report(capsys, big_root, big_store)["wall_clock_seconds_by_scope"]
    assert isinstance(small, dict)
    assert isinstance(big, dict)
    assert big["main"] > small["main"]


def test_price_model_knob_reaches_the_report(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    """Only reachable for turns whose own model is unrecognised (ADR-010 fallback)."""
    root, store = _project_with_transcripts(
        tmp_path, harness_yaml="economics:\n  price_model: haiku\n"
    )
    path = store / encode_project_dir(root) / "s1.jsonl"
    path.write_text(
        json.dumps(
            {
                "type": "assistant",
                "sessionId": "s1",
                "timestamp": _T0.isoformat(),
                "cwd": str(root),
                "message": {"model": "mystery-model", "usage": {"output_tokens": 1_000_000}},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    report = _report(capsys, root, store)
    assert report["fallback_priced_turns"] == 1
    # Still 1.25. An intermediate revision briefly changed this to 5.0, which was the
    # SYMPTOM of a defect review caught: the haiku FAMILY row had been overwritten with
    # Haiku 4.5's rate instead of a `haiku-4-5` key being added. `price_model: haiku`
    # names the family fallback — the row that prices ids the table does not recognise —
    # and that row is the legacy 0.25/1.25. A user wanting the 4.5 rate sets
    # `price_model: haiku-4-5`, which resolves through the same longest-match matcher.
    assert report["total_usd"] == pytest.approx(1.25)  # haiku family rate, not opus 75.0


def test_window_days_knob_reaches_the_report(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    root, store = _project_with_transcripts(tmp_path, harness_yaml="economics:\n  window_days: 1\n")
    code = main(
        [
            "report",
            "--root",
            str(root),
            "--transcript-root",
            str(store),
            "--now",
            "2027-01-01T00:00:00+00:00",
        ]
    )
    assert code == 0
    report = json.loads(capsys.readouterr().out)["report"]
    assert report["turns"] == 0
