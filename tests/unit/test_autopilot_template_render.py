"""Autopilot gates retain Claude dispatch and supply a native Codex continuation."""

from __future__ import annotations

from pathlib import Path

import pytest

from harness_maker.interview import interview
from harness_maker.models import ProjectProfile
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize

_STAGES = ("research", "spec", "execute", "review", "wrapup", "verify")
_GATED_STAGES = ("review", "wrapup", "verify")  # have a real mandatory gate
_TEMPLATES = Path(__file__).resolve().parents[2] / "src" / "harness_maker" / "templates"


@pytest.fixture(scope="module")
def rendered_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("rendered")
    p = ProjectProfile(stack=["python"], scale="small", lifecycle="dormant")
    a = interview(p, autoloop_mode=True)
    render(synthesize(p, a), out, freeze_time=DEFAULT_FREEZE_TIME)
    return out


@pytest.mark.parametrize("stage", _STAGES)
def test_stage_command_has_autopilot_advance_block(rendered_root: Path, stage: str) -> None:
    body = (rendered_root / "commands" / "hm" / f"{stage}.md").read_text(encoding="utf-8")
    assert "<!-- @hm:autopilot-advance -->" in body
    # the deterministic boundary CLI, scoped to THIS stage.
    assert "hm autopilot_caps boundary" in body
    assert f"--current {stage}" in body


@pytest.mark.parametrize("stage", _GATED_STAGES)
def test_gated_stages_carry_their_mandatory_gate(rendered_root: Path, stage: str) -> None:
    body = (rendered_root / "commands" / "hm" / f"{stage}.md").read_text(encoding="utf-8")
    needles = {
        # B3 reworded this gate when it became a judgment gate routed to the boundary. The
        # needle tracks the surviving invariant — an unresolved architecture round is what
        # the gate is about — not the old sentence.
        "plan": "unresolved architectural AskUserQuestion round",
        "review": "CHANGES_REQUESTED",
        "wrapup": "auto-advance never pushes",
        "verify": "verification check FAILED",
    }
    assert needles[stage] in body


def test_picker_present_under_the_promoted_default_level(rendered_root: Path) -> None:
    # ADR-010 promoted the default to `auto_safe`, so a NEW harness renders the
    # session-start picker. The render-time gate itself is unchanged — it is still keyed on
    # the level, and a project pinned back to `gated` still renders no picker
    # (test_picker_absent_when_level_is_pinned_gated below).
    body = (rendered_root / "commands" / "hm" / "research.md").read_text(encoding="utf-8")
    assert "<!-- @hm:autopilot-picker -->" in body


def test_picker_absent_when_level_is_pinned_gated(tmp_path: Path) -> None:
    """Negative control for the test above — without it that assertion is vacuous.

    While the default was `gated`, "picker absent" WAS the control: it failed if the block
    were emitted unconditionally. ADR-010 inverted the default, so the surviving positive
    assertion would now pass even if the render-time gate were deleted outright. This
    renders the other side of the gate.
    """
    from harness_maker.models import AutonomyConfig

    p = ProjectProfile(stack=["python"], scale="small", lifecycle="dormant")
    a = interview(p, autoloop_mode=True).model_copy(
        update={"autonomy": AutonomyConfig(level="gated", autopilot_persistent=False)}
    )
    render(synthesize(p, a), tmp_path, freeze_time=DEFAULT_FREEZE_TIME)
    body = (tmp_path / "commands" / "hm" / "research.md").read_text(encoding="utf-8")
    assert "<!-- @hm:autopilot-picker -->" not in body


def test_runtime_dispatch_is_structural() -> None:
    partial = (_TEMPLATES / "agents/_partials/stage_end_summary.md.j2").read_text()
    assert 'include "agents/_partials/codex_autopilot_advance.md.j2"' in partial
    for is_codex in (True, False):
        assert "hm autopilot on" in _render_manifest(is_codex)
    assert "request_user_input" in _render_manifest(True)
    assert "AskUserQuestion" in _render_manifest(False)


def _render_manifest(is_codex: bool) -> str:
    """Render the picker partial alone, so suppression is measured rather than grepped for."""
    from harness_maker.models import HarnessConfig
    from harness_maker.render import _make_env

    return (
        _make_env()
        .get_template("agents/_partials/step_manifest.md.j2")
        .render(
            config=HarnessConfig().model_dump(mode="json"),
            is_codex=is_codex,
            harness_maker_src_path="/cache/harness-maker/0.0.0",
        )
    )


def _render_partial(is_codex: bool) -> str:
    from harness_maker.models import HarnessConfig
    from harness_maker.render import _make_env

    env = _make_env()
    ctx: dict[str, object] = {
        "summary_stage": "research",
        "summary_autopilot_gate": "no gate",
        "summary_done": "d",
        "summary_artifact": "a",
        "summary_next": "n",
        "config": HarnessConfig().model_dump(mode="json"),
        "is_codex": is_codex,
        # the autopilot-advance block now uses the canonical inline launcher (ADR-001),
        # which the full render injects; supply it here for the isolated partial render.
        "harness_maker_src_path": "/cache/harness-maker/0.0.0",
    }
    return env.get_template("agents/_partials/stage_end_summary.md.j2").render(**ctx)


def test_autopilot_block_has_native_dispatch_for_each_runtime() -> None:
    codex = _render_partial(is_codex=True)
    claude = _render_partial(is_codex=False)
    assert "@hm:autopilot-advance" in codex
    assert ".agents/skills/hm-<next_stage>/SKILL.md" in codex
    assert "Skill(hm:<next_stage" not in codex
    assert "Skill(hm:<next_stage" in claude
