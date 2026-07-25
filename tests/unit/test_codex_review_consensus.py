"""Phase 4b — Codex as a cross-model consensus voter in /hm:review
(PLAN-crossmodel-codex-gaps ADR-001, generalized by PLAN-second-opinion-multi-model).

Renders the review stage with codex enabled/disabled and asserts the orchestration,
null-location relaxation, cross-model heterogeneous-voter framing (K=2 fixed, N grows
with each enabled model), grade impact, and skip/status relay are present (and
byte-zero when disabled, so codex-off snapshots are unaffected).
"""

from __future__ import annotations

from harness_maker.models import HarnessConfig
from harness_maker.render import _make_env
from harness_maker.synthesize import _HARNESS_MAKER_PKG_ROOT


def _render_review(*, codex_enabled: bool, is_codex: bool = False) -> str:
    env = _make_env()
    cfg = HarnessConfig().model_dump(mode="json")
    cfg["second_opinion"]["models"] = ["codex"] if codex_enabled else []
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
    assert "second_opinion_invoke --model codex" in out


def test_cross_model_heterogeneous_voter_present_when_enabled() -> None:
    """Generalized wording (rename mapping): "third voter / k-of-3" -> "Cross-model
    heterogeneous voters", N = reviewers + models, K=2 fixed (verified by grep of the
    actual render — see /tmp scratchpad review_enabled.md)."""
    out = _render_review(codex_enabled=True)
    low = out.lower()
    assert "cross-model heterogeneous voters" in low
    assert "k = 2" in low or "k=2" in low


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
    """Old scalar `codex_status` field is superseded by the per-model
    `second_opinion_results` array (rename mapping) — the skip/status relay contract."""
    out = _render_review(codex_enabled=True)
    assert "second_opinion_results" in out
    assert 'status: "skipped"' in out or "status: invoked" in out


def test_codex_blocks_absent_when_disabled() -> None:
    out = _render_review(codex_enabled=False)
    assert "second_opinion_invoke" not in out
    assert "needs_relaxation" not in out
    assert "second_opinion_results" not in out
