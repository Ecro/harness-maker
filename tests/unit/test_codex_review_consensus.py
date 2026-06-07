"""Phase 4b — Codex as a k-of-3 consensus voter in /hm:review (PLAN-crossmodel-codex-gaps ADR-001).

Renders the review stage with codex enabled/disabled and asserts the orchestration,
null-location relaxation, k-of-3, grade impact, and skip relay are present (and
byte-zero when disabled, so codex-off snapshots are unaffected).
"""

from __future__ import annotations

from harness_maker.models import HarnessConfig
from harness_maker.render import _make_env
from harness_maker.synthesize import _HARNESS_MAKER_PKG_ROOT


def _render_review(*, codex_enabled: bool, is_codex: bool = False) -> str:
    env = _make_env()
    cfg = HarnessConfig().model_dump(mode="json")
    cfg["codex_second_opinion"]["enabled"] = codex_enabled
    return env.get_template("stages/review.md.j2").render(
        stage="review",
        workflow_context="",
        project_name="",
        feature="",
        config=cfg,
        harness_maker_src_path=_HARNESS_MAKER_PKG_ROOT,
        is_codex=is_codex,
    )


def test_codex_orchestration_present_when_enabled() -> None:
    out = _render_review(codex_enabled=True)
    assert "codex_adapter" in out
    assert "codex exec" in out


def test_k_of_3_voter_present_when_enabled() -> None:
    out = _render_review(codex_enabled=True)
    low = out.lower()
    assert "k-of-3" in low or "third voter" in low or "third vote" in low


def test_null_location_relaxation_present() -> None:
    out = _render_review(codex_enabled=True)
    assert "needs_relaxation" in out
    assert "similarity" in out.lower()


def test_grade_impact_documented() -> None:
    """A Codex-raised consensus-passed finding must count toward the grade."""
    out = _render_review(codex_enabled=True)
    low = out.lower()
    assert "consensus-passed" in low
    assert "grade" in low


def test_skip_relay_present() -> None:
    out = _render_review(codex_enabled=True)
    assert "codex_status" in out


def test_codex_blocks_absent_when_disabled() -> None:
    out = _render_review(codex_enabled=False)
    assert "codex_adapter" not in out
    assert "needs_relaxation" not in out
