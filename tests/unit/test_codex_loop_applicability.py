"""Phase 6 — loop applicability invariant (PLAN-crossmodel-codex-gaps ADR-006).

Second opinion mandatory-ness is stage-level (gated only on
config.second_opinion.models), NOT on loop/standalone context — so /hm:loop inherits
the matrix automatically: loop-mode plan still reaches plan-validator (Step 4) and
review runs at the iteration boundary. Generalized by PLAN-second-opinion-multi-model
ADR-011 from the single-vendor codex_second_opinion.enabled gate.
"""

from __future__ import annotations

from pathlib import Path

from harness_maker.models import HarnessConfig
from harness_maker.render import _make_env
from harness_maker.synthesize import _HARNESS_MAKER_PKG_ROOT

_TEMPLATES = Path(__file__).resolve().parents[2] / "src" / "harness_maker" / "templates"


def _render_review(*, is_codex: bool) -> str:
    env = _make_env()
    cfg = HarnessConfig().model_dump(mode="json")
    cfg["second_opinion"]["models"] = ["codex"]
    return env.get_template("stages/review.md.j2").render(
        stage="review",
        workflow_context="loop",
        project_name="",
        feature="",
        config=cfg,
        harness_maker_src_path=_HARNESS_MAKER_PKG_ROOT,
        is_codex=is_codex,
    )


def test_review_codex_present_regardless_of_runner() -> None:
    """Same stage, same second-opinion wiring whether run standalone or via loop
    (both IDE flavors)."""
    for is_codex in (False, True):
        out = _render_review(is_codex=is_codex)
        assert "codex_adapter" in out, f"second-opinion wiring missing for is_codex={is_codex}"


def test_codex_blocks_not_gated_on_loop_or_standalone() -> None:
    """The second-opinion blocks must gate ONLY on config.second_opinion.models — never
    on a loop/standalone flag."""
    src = (_TEMPLATES / "stages" / "review.md.j2").read_text(encoding="utf-8")
    # every second-opinion block opens with the models guard, none with a loop/standalone guard
    assert "config.second_opinion.models" in src
    assert "if loop_mode" not in src
    assert "if standalone" not in src


def test_loop_command_does_not_suppress_second_opinion() -> None:
    loop_src = (_TEMPLATES / "commands" / "hm" / "loop.md.j2").read_text(encoding="utf-8")
    low = loop_src.lower()
    # the loop must not disable / skip the second opinion
    assert "second_opinion: false" not in low
    assert "second_opinion.models = []" not in low
    assert "skip second opinion" not in low
    assert "disable second opinion" not in low
