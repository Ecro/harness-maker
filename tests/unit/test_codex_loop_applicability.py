"""Phase 6 — loop applicability invariant (PLAN-crossmodel-codex-gaps ADR-006).

Codex mandatory is stage-level (gated only on codex_second_opinion.enabled), NOT on
loop/standalone context — so /hm:loop inherits the matrix automatically: loop-mode
plan still reaches plan-validator (Step 4) and review runs at the iteration boundary.
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
    cfg["codex_second_opinion"]["enabled"] = True
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
    """Same stage, same codex wiring whether run standalone or via loop (both IDE flavors)."""
    for is_codex in (False, True):
        out = _render_review(is_codex=is_codex)
        assert "codex_adapter" in out, f"codex wiring missing for is_codex={is_codex}"


def test_codex_blocks_not_gated_on_loop_or_standalone() -> None:
    """The codex blocks must gate ONLY on enabled — never on a loop/standalone flag."""
    src = (_TEMPLATES / "stages" / "review.md.j2").read_text(encoding="utf-8")
    # every codex block opens with the enabled guard, none with a loop/standalone guard
    assert "codex_second_opinion.enabled" in src
    assert "if loop_mode" not in src
    assert "if standalone" not in src


def test_loop_command_does_not_suppress_codex() -> None:
    loop_src = (_TEMPLATES / "commands" / "hm" / "loop.md.j2").read_text(encoding="utf-8")
    low = loop_src.lower()
    # the loop must not disable / skip the codex second opinion
    assert "codex_second_opinion: false" not in low
    assert "skip codex" not in low
    assert "disable codex" not in low
