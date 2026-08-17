"""W7 (PLAN-second-opinion-multi-model ADR-006): K=2 stays fixed as the voter pool N grows.

Proves empirically — not by example alone — that `scope_aware_consensus` promotes a finding to
`consensus-passed` on exactly 2 agreeing distinct voices regardless of whether the total pool is
3 (2 claude + codex), 4 (+antigravity), or 5, and that a lone voice stays manual-only at every N.
This is the regression guard for ADR-006's "no Python change needed" claim: the fixed absolute
`len(reviewers) >= 2` rule is genuinely source-agnostic.
"""

from __future__ import annotations

from typing import Any

from harness_maker.conditional_router import scope_aware_consensus


def _finding(
    reviewer: str, *, file: str = "a.py", line: int = 10, sev: str = "P0"
) -> dict[str, Any]:
    return {
        "reviewer": reviewer,
        "file": file,
        "line": line,
        "severity": sev,
        "category": "correctness",
        "summary": "same issue",
    }


def _tag_for(findings: list[dict[str, Any]], *, file: str = "a.py", line: int = 10) -> str:
    out = scope_aware_consensus(findings)
    for f in out:
        if f.get("file") == file and f.get("line") == line:
            return str(f.get("consensus_tag"))
    raise AssertionError("finding not found in consensus output")


def test_two_voices_pass_at_n3() -> None:
    # pool of 3 voices (2 claude reviewers + codex), 2 agree on the same location
    findings: list[dict[str, Any]] = [
        _finding("code-reviewer"),
        _finding("codex"),
        _finding("security-reviewer", file="b.py", line=99, sev="P1"),
    ]
    assert _tag_for(findings) == "consensus-passed"


def test_two_voices_pass_at_n4() -> None:
    # pool of 4 (2 claude + codex + antigravity); still exactly 2 agree on a.py:10
    findings = [
        _finding("code-reviewer"),
        _finding("codex"),
        _finding("antigravity", file="c.py", line=5, sev="P2"),
        _finding("security-reviewer", file="b.py", line=99, sev="P1"),
    ]
    assert _tag_for(findings) == "consensus-passed"


def test_three_voices_still_pass_at_n5() -> None:
    # 3 agree at a.py:10 within a pool of 5 — K=2 threshold is met (and exceeded)
    findings = [
        _finding("code-reviewer"),
        _finding("codex"),
        _finding("antigravity"),
        _finding("performance-reviewer", file="d.py", line=1, sev="P3"),
        _finding("ux-reviewer", file="e.py", line=2, sev="P3"),
    ]
    out = scope_aware_consensus(findings)
    passed = next(f for f in out if f.get("file") == "a.py")
    assert passed["consensus_tag"] == "consensus-passed"
    assert passed["consensus_count"] == 3


def test_lone_second_opinion_voice_not_auto_passed() -> None:
    # a single antigravity finding with no agreeing peer must NOT reach consensus-passed
    # (category 'correctness' is code-reviewer scope, so a lone non-owner voice is manual-only)
    findings = [
        _finding("antigravity"),
        _finding("code-reviewer", file="z.py", line=1, sev="P3"),
    ]
    assert _tag_for(findings) != "consensus-passed"


def test_null_location_relaxation_is_a_render_concern_not_math() -> None:
    # scope_aware_consensus keys on file:line:severity; a null-location finding lands in its
    # own bucket. The symbol/message-similarity relaxation is applied by the LLM per the
    # rendered prose BEFORE this function — so two null-location voices with the SAME
    # (None,None,sev) bucket still count as 2 distinct reviewers here.
    findings: list[dict[str, Any]] = [
        {
            "reviewer": "codex",
            "file": None,
            "line": None,
            "severity": "P1",
            "category": "correctness",
            "summary": "x",
        },
        {
            "reviewer": "code-reviewer",
            "file": None,
            "line": None,
            "severity": "P1",
            "category": "correctness",
            "summary": "x",
        },
    ]
    out = scope_aware_consensus(findings)
    assert out[0]["consensus_tag"] == "consensus-passed"
