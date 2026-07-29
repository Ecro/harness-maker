"""P6 — autopilot auto-advance renders into Claude stage commands, gated cross-IDE.

Behavioral render assertions (more robust than brittle verbatim golden bodies): the
auto-advance terminal block + boundary CLI + per-stage mandatory-gate prose appear in
every rendered Claude stage command; the session-start picker is config-gated (absent
under the default `gated` level); and the Codex exclusion is structural
(`{% if is_codex is defined and not is_codex %}`) so no auto-branch leaks into the Codex
render (ADR-004). NOTE: the Codex stage_skill PRODUCTION render passes `is_codex=True`
(so `not is_codex` already excludes it); the `is defined` clause additionally guards
bare/partial renders (e.g. the codex stage_skill unit render) where `is_codex` is unset.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from harness_maker.interview import interview
from harness_maker.models import ProjectProfile
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize

_STAGES = ("research", "spec", "plan", "execute", "review", "wrapup", "verify")
_GATED_STAGES = ("plan", "review", "wrapup", "verify")  # have a real mandatory gate
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
        "plan": "architectural AskUserQuestion round is pending",
        "review": "CHANGES_REQUESTED",
        "wrapup": "auto-advance never pushes",
        "verify": "verification check FAILED",
    }
    assert needles[stage] in body


def test_picker_absent_under_default_gated_level(rendered_root: Path) -> None:
    # The default harness is `autonomy.level: gated` → the session-start picker is
    # render-time-gated out (no churn / no prompt for users who never opted in).
    body = (rendered_root / "commands" / "hm" / "research.md").read_text(encoding="utf-8")
    assert "<!-- @hm:autopilot-picker -->" not in body


def test_codex_exclusion_is_structural() -> None:
    # ADR-004: the auto-branch is wrapped in `is_codex is defined and not is_codex` (so the
    # Codex render never emits a Skill auto-invoke branch) AND `autopilot_advance_enabled`
    # (REVIEW P1-3: fused renders pass False so the block is not embedded per fragment).
    partial = (_TEMPLATES / "agents" / "_partials" / "stage_end_summary.md.j2").read_text()
    manifest = (_TEMPLATES / "agents" / "_partials" / "step_manifest.md.j2").read_text()
    assert (
        "{% if is_codex is defined and not is_codex "
        "and (autopilot_advance_enabled | default(true)) %}" in partial
    )
    assert "@hm:autopilot-advance" in partial
    assert (
        '{% if is_codex is defined and not is_codex and config.autonomy.level != "gated" %}'
        in manifest
    )


def _render_partial(is_codex: bool, *, advance_enabled: bool | None = None) -> str:
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
    if advance_enabled is not None:
        ctx["autopilot_advance_enabled"] = advance_enabled
    return env.get_template("agents/_partials/stage_end_summary.md.j2").render(**ctx)


def test_autopilot_block_behaviorally_absent_for_codex() -> None:
    # P2-7: behavioral (not just a source grep) — rendering the terminal with is_codex=True
    # emits NO auto-advance branch; the Claude render (is_codex=False) does.
    assert "@hm:autopilot-advance" not in _render_partial(is_codex=True)
    assert "@hm:autopilot-advance" in _render_partial(is_codex=False)


def test_autopilot_block_suppressed_in_fused_render() -> None:
    # P1-3: a fused fragment (autopilot_advance_enabled=False) carries NO live auto-advance
    # block even for Claude — else an armed fused run would escalate past the invoked stages.
    assert "@hm:autopilot-advance" not in _render_partial(is_codex=False, advance_enabled=False)


def test_fuse_emits_no_autopilot_advance_block() -> None:
    # P1-3 end-to-end: workflow_fuse.fuse() threads autopilot_advance_enabled=False, so the
    # fused command body is free of the boundary CLI + Skill auto-invoke branch.
    from harness_maker.models import AtomicStage
    from harness_maker.workflow_fuse import fuse

    body = fuse([AtomicStage.EXECUTE, AtomicStage.REVIEW], "exec-rev")
    assert "@hm:autopilot-advance" not in body
    assert "autopilot_caps boundary" not in body
