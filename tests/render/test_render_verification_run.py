"""SPEC-top-issues-2026-09 S6 (verify/wrapup half): one verb owns the gate run and the marker.

`mark-pass` survives only for a project with no readable CI. These tests pin that it appears
nowhere else in the two stages that used to call it unconditionally.

Phase A.4 justified pass: `test_degraded_predicate_discriminates` is a positive control for the
block-membership predicate, and by construction it has no implementation to wait for.
"""

from __future__ import annotations

import pytest

from ._top_issues_render import stage_bodies

_OPEN = "<!-- @hm:verify-degraded -->"
_CLOSE = "<!-- @hm:/verify-degraded -->"


def _degraded_spans(body: str) -> list[tuple[int, int]]:
    spans, i = [], 0
    while (s := body.find(_OPEN, i)) != -1:
        e = body.index(_CLOSE, s)
        spans.append((s, e))
        i = e
    return spans


def _mark_pass_positions(body: str) -> list[int]:
    out, i = [], 0
    while (p := body.find("mark-pass", i)) != -1:
        out.append(p)
        i = p + 1
    return out


def in_degraded_block(body: str, pos: int) -> bool:
    return any(s < pos < e for s, e in _degraded_spans(body))


_CASES = [(stage, v, b) for stage in ("verify", "wrapup") for v, b in stage_bodies(stage)]


@pytest.mark.parametrize(
    ("stage", "variant", "body"), _CASES, ids=[f"{s}-{v}" for s, v, _ in _CASES]
)
def test_stages_call_run(stage: str, variant: str, body: str) -> None:
    assert "verification_cache run" in body, (stage, variant)
    assert "verification_cache check" not in body, (stage, variant)
    assert _degraded_spans(body), (stage, variant)
    assert all(in_degraded_block(body, i) for i in _mark_pass_positions(body)), (stage, variant)
    run_at = body.index("verification_cache run")
    tail = body[run_at : run_at + 4000]
    for code in ("`3`", "`4`", "`1`"):
        assert code in tail, (stage, variant, code)
    assert "killed" in tail.lower()  # the host-kill path is named, not left to improvisation
    run_line = next(ln for ln in body.splitlines() if "verification_cache run" in ln)
    # A backgrounded call's host-reported status is not trustworthy; the verdict is the JSON line.
    assert '`"exit"` field' in tail, (stage, variant)
    if variant == "claude":
        # A real suite outlives the 10-minute foreground cap (this repo: 425-702 s for pytest
        # alone), so the Claude Code call lifts both budgets and runs in the background.
        assert "--deadline-s" in run_line, (stage, variant)
        assert "--timeout-s" in run_line, (stage, variant)
        assert "run_in_background" in tail, (stage, variant)
    else:
        # Codex has no background call: lifted budgets there would outrun its own shell timeout.
        assert "--deadline-s" not in run_line, (stage, variant)
        assert "Foreground call" in tail, (stage, variant)


def test_degraded_predicate_discriminates() -> None:
    body = f"a mark-pass b {_OPEN} mark-pass {_CLOSE}"
    positions = _mark_pass_positions(body)
    assert [in_degraded_block(body, p) for p in positions] == [False, True]
