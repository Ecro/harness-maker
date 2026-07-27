"""Regression tests for the REVIEW round-1 fixes.

Every test here pins a defect that shipped GREEN through the Phase 1-3 suites — the
fixes changed behaviour and not one existing test failed, which is exactly the
"changed without a test" class this project keeps hitting.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from harness_maker.economics import (
    PRICE_TABLE,
    TokenUsage,
    TurnRecord,
    classify_turns,
    main,
    price_turn,
    resolve_model_family,
)
from harness_maker.economics_source import is_own_cwd, load_turns

_FIXTURES = Path(__file__).parents[1] / "fixtures" / "transcripts"
_PROJECT = Path("/repo/proj")
_T0 = datetime(2026, 7, 25, 12, 0, 0, tzinfo=UTC)


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


# ------------------------------------------------- classifier state (codex + antigravity P1)


def test_a_write_plus_verify_turn_does_not_open_a_verify_window() -> None:
    """The turn is PRODUCE, so it must NOT stamp last_verify_at.

    Before the fix, `last_verify == last_write == idx` made `idx < idx` False and the
    NEXT unprompted rewrite escaped REWORK.
    """
    labels = classify_turns(
        [
            _turn(0, attribution_skill="hm:review", written_paths=("a.py",)),
            _turn(1, written_paths=("a.py",)),
        ]
    )
    assert labels == ["PRODUCE", "REWORK"]


def test_a_real_verify_turn_still_opens_the_window() -> None:
    labels = classify_turns(
        [
            _turn(0, written_paths=("a.py",)),
            _turn(1, attribution_skill="hm:review"),
            _turn(2, written_paths=("a.py",)),
        ]
    )
    assert labels == ["PRODUCE", "VERIFY", "PRODUCE"]


# ------------------------------------------------- naive timestamps (3-voice consensus P1)


def test_a_timezone_naive_timestamp_does_not_raise(tmp_path: Path) -> None:
    """The module promises never to raise; a tz-less line must not kill the run."""
    store = tmp_path / "-repo-proj"
    store.mkdir(parents=True)
    (store / "s.jsonl").write_text(
        '{"type":"assistant","sessionId":"x","timestamp":"2026-07-25T12:00:00",'
        '"cwd":"/repo/proj","message":{"model":"claude-opus-5","usage":{"output_tokens":5}}}\n',
        encoding="utf-8",
    )
    result = load_turns(
        _PROJECT, transcript_root=tmp_path, days=3650, now=datetime(2026, 7, 26, tzinfo=UTC)
    )
    assert len(result.turns) == 1
    assert result.turns[0].ts.tzinfo is not None


def test_naive_now_flag_does_not_raise(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(
        [
            "report",
            "--root",
            "/repo/proj",
            "--transcript-root",
            str(_FIXTURES),
            "--now",
            "2026-07-25T14:00:00",  # no offset — previously a TypeError
        ]
    )
    assert code == 0
    assert json.loads(capsys.readouterr().out)["status"] == "ok"


# ------------------------------------------------- pricing fallback (code-reviewer P1)


def test_fallback_model_accepts_a_full_model_id_not_just_a_family_key() -> None:
    """`price_model: "claude-sonnet-4-5"` must price at sonnet, not silently at opus."""
    unknown = _turn(0, model="totally-unknown", usage=TokenUsage(output_tokens=1_000_000))
    sonnet = price_turn(unknown, fallback_model="claude-sonnet-4-5").total_usd
    assert sonnet == pytest.approx(PRICE_TABLE["sonnet"].output)
    assert sonnet != pytest.approx(PRICE_TABLE["opus"].output)


def test_unresolvable_fallback_still_degrades_to_opus_rather_than_crashing() -> None:
    cost = price_turn(_turn(0, model="unknown"), fallback_model="nonsense")
    assert cost.total_usd > 0
    assert cost.priced_with_fallback is True


def test_model_family_resolution_is_longest_match_not_dict_order() -> None:
    """Updated by PLAN ADR-002 — the matcher is unchanged, the TABLE gained keys.

    This asserted `claude-opus-5 -> "opus"`, which was only true because no
    point-release key existed. Now that `opus-5` is a key, longest-match must prefer
    it: that preference is the entire fix (`"opus"` capturing Opus 5 priced 30 days of
    spend at 15/75 against a published 5/25). The `opus-4-1` case keeps the original
    intent alive — an id with no point-release key still falls back to the family.
    """
    assert resolve_model_family("claude-opus-5") == "opus-5"
    assert resolve_model_family("claude-opus-4-1") == "opus"
    assert resolve_model_family("CLAUDE-HAIKU-4-5") == "haiku-4-5"  # case-insensitive
    assert resolve_model_family("claude-haiku-3") == "haiku"
    assert resolve_model_family("nothing-here") is None


# ------------------------------------------------- config path (code-reviewer P1: untested)


def test_harness_yaml_tuning_actually_reaches_the_report(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    """The whole per-project tuning surface had zero coverage — swapping two fields
    in the AdjacencyBounds construction would have kept the suite green."""
    claude = tmp_path / ".claude"
    claude.mkdir()
    (claude / "harness.yaml").write_text(
        "preset: Production\neconomics:\n  adjacency_estimate: false\n", encoding="utf-8"
    )
    # The report must be built for THIS project's transcripts, so point the encoded
    # fixture dir at the tmp root by reusing the fixture project path for discovery.
    code = main(
        [
            "report",
            "--root",
            str(tmp_path),
            "--transcript-root",
            str(_FIXTURES),
            "--now",
            "2026-07-25T14:00:00+00:00",
        ]
    )
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    # adjacency_estimate=false must zero the estimator regardless of the turns found.
    assert payload["report"]["estimated_attribution_usd"] == {}
    assert payload["report"]["estimator_coverage"] == 0.0


# ------------------------------------------------- coverage denominator (2-voice P2)


def test_window_excluded_lines_leave_the_coverage_denominator() -> None:
    """Otherwise a narrow --days looks identical to catastrophic format drift."""
    full = load_turns(
        _PROJECT, transcript_root=_FIXTURES, days=3650, now=datetime(2026, 7, 26, tzinfo=UTC)
    )
    narrow = load_turns(
        _PROJECT, transcript_root=_FIXTURES, days=1, now=datetime(2027, 1, 1, tzinfo=UTC)
    )
    assert full.diagnostics.coverage == pytest.approx(7 / 8)
    assert narrow.turns == []
    # every assistant line was window-excluded, so the denominator collapses to 0 → 0.0,
    # NOT a misleading "coverage dropped because the reader broke" figure.
    assert narrow.diagnostics.skipped_by_reason["outside_window"] == 7
    assert narrow.diagnostics.coverage == 0.0


# ------------------------------------------------- foreign-project boundary (2-voice P0/P1)


@pytest.mark.parametrize(
    ("cwd", "expected"),
    [
        ("/repo/proj", True),
        ("/repo/proj/src", True),
        ("/repo/proj/.worktrees/demo", True),
        ("/repo/projector", False),  # prefix of the path, not under it
        ("/repo--worktrees-demo", False),  # the encoding-collision case
        ("/somewhere/else", False),
        (None, True),  # older lines carry no cwd
    ],
)
def test_is_own_cwd_boundary(cwd: str | None, expected: bool) -> None:
    assert is_own_cwd(cwd, _PROJECT) is expected


def test_a_colliding_directory_contributes_no_turns(tmp_path: Path) -> None:
    """`-repo-proj--worktrees-evil` matches the name prefix but its turns are foreign."""
    evil = tmp_path / "-repo-proj--worktrees-evil"
    evil.mkdir(parents=True)
    (evil / "s.jsonl").write_text(
        '{"type":"assistant","sessionId":"e","timestamp":"2026-07-25T12:00:00Z",'
        '"cwd":"/some/other/repo","message":{"model":"claude-opus-5",'
        '"usage":{"output_tokens":9999}}}\n',
        encoding="utf-8",
    )
    result = load_turns(
        _PROJECT, transcript_root=tmp_path, days=3650, now=datetime(2026, 7, 26, tzinfo=UTC)
    )
    assert result.turns == []
    assert result.diagnostics.skipped_by_reason["foreign_cwd"] == 1


# ------------------------------------------------- bounded untrusted values (2-voice P2)


def test_oversized_transcript_derived_keys_are_clipped(tmp_path: Path) -> None:
    store = tmp_path / "-repo-proj"
    store.mkdir(parents=True)
    huge = "m" * 5000
    (store / "s.jsonl").write_text(
        json.dumps(
            {
                "type": "assistant",
                "sessionId": "x",
                "timestamp": "2026-07-25T12:00:00Z",
                "cwd": "/repo/proj",
                "attributionSkill": "s" * 5000,
                "message": {"model": huge, "usage": {"output_tokens": 5}},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    result = load_turns(
        _PROJECT, transcript_root=tmp_path, days=3650, now=datetime(2026, 7, 26, tzinfo=UTC)
    )
    turn = result.turns[0]
    assert turn.model is not None
    assert len(turn.model) <= 64
    assert turn.attribution_skill is not None
    assert len(turn.attribution_skill) <= 64


def test_an_oversized_line_is_skipped_not_buffered(tmp_path: Path) -> None:
    store = tmp_path / "-repo-proj"
    store.mkdir(parents=True)
    (store / "s.jsonl").write_text("x" * (5 * 1024 * 1024) + "\n", encoding="utf-8")
    result = load_turns(_PROJECT, transcript_root=tmp_path)
    assert result.turns == []
    assert result.diagnostics.skipped_by_reason["oversize_line"] == 1


def test_control_characters_are_stripped_from_report_keys(tmp_path: Path) -> None:
    store = tmp_path / "-repo-proj"
    store.mkdir(parents=True)
    (store / "s.jsonl").write_text(
        json.dumps(
            {
                "type": "assistant",
                "sessionId": "x",
                "timestamp": "2026-07-25T12:00:00Z",
                "cwd": "/repo/proj",
                "attributionSkill": "hm:exec\nute",
                "message": {"model": "claude-opus-5", "usage": {"output_tokens": 5}},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    result = load_turns(
        _PROJECT, transcript_root=tmp_path, days=3650, now=datetime(2026, 7, 26, tzinfo=UTC)
    )
    skill = result.turns[0].attribution_skill
    assert skill == "hm:execute"


# ------------------------------------------------- discovery never raises


def test_discovery_survives_an_unreadable_transcript_root(tmp_path: Path) -> None:
    missing = tmp_path / "gone"
    result = load_turns(_PROJECT, transcript_root=missing)
    assert result.turns == []
    assert result.diagnostics.dirs_scanned == 0
