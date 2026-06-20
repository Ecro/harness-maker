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
    assert "harness_maker.autopilot_caps boundary" in body
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
    # ADR-004: the auto-branch + picker are wrapped in `{% if is_codex is defined and not
    # is_codex %}` so the Codex render (is_codex=True) never emits a Skill auto-invoke
    # branch, and a bare/partial render (is_codex unset) omits it too.
    partial = (_TEMPLATES / "agents" / "_partials" / "stage_end_summary.md.j2").read_text()
    manifest = (_TEMPLATES / "agents" / "_partials" / "step_manifest.md.j2").read_text()
    assert "{% if is_codex is defined and not is_codex %}" in partial
    assert "@hm:autopilot-advance" in partial
    assert (
        '{% if is_codex is defined and not is_codex and config.autonomy.level != "gated" %}'
        in manifest
    )
