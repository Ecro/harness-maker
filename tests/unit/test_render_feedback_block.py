"""Phase 4 — render wiring for the feedback dispatcher block.

PLAN-auto-feedback-2026-05 Phase 4 exit criteria — exercised via the real
synthesize() pipeline (not Jinja in isolation) so the test catches both the
template change AND the synthesize.py context-propagation change.
"""

from __future__ import annotations

import jinja2
import pytest

import harness_maker.render as render_mod
from harness_maker.models import (
    FeedbackConfig,
    InterviewAnswers,
    Preset,
    ProjectProfile,
    Target,
)
from harness_maker.synthesize import synthesize

_env = render_mod._make_env()


def _render_blueprint(*, feedback_enabled: bool) -> dict[str, str]:
    """Render the full Blueprint and return {relative_path: rendered_text}.

    Uses the real synthesize() pipeline so we test both the synthesize.py
    context-propagation change AND the template change together.
    """
    profile = ProjectProfile()
    answers = InterviewAnswers(
        preset=Preset.SIDE,
        targets=[Target.CLAUDE_CODE],
        feedback=FeedbackConfig(enabled=feedback_enabled),
    )
    blueprint = synthesize(profile, answers)
    out: dict[str, str] = {}
    for fe in blueprint.files:
        if "commands/hm/" not in str(fe.path) or not str(fe.path).endswith(".md"):
            continue
        tpl = _env.get_template(fe.template)
        out[str(fe.path)] = tpl.render(**fe.context)
    return out


# ── (a) byte-identical-when-off semantics: marker is absent everywhere ───────


def test_when_feedback_disabled_no_command_file_contains_dispatcher_marker() -> None:
    rendered = _render_blueprint(feedback_enabled=False)
    assert rendered, "blueprint produced no /hm:* command files"
    for path, body in rendered.items():
        assert "@hm:feedback:dispatcher-block" not in body, (
            f"feedback dispatcher block leaked into {path} when feedback.enabled=false"
        )


# ── (b)(c) marker present + grep-count == 1 when on, in BOTH atomic + workflow ─


def test_when_feedback_enabled_marker_appears_exactly_once_in_atomic_commands() -> None:
    rendered = _render_blueprint(feedback_enabled=True)
    atomic_files = {
        p: b
        for p, b in rendered.items()
        if "commands/hm/" in p
        # atomic_command.md.j2 produces files like 'research.md', 'execute.md', etc.
        and not any(
            p.endswith(f"/{w}.md")
            for w in ("configure", "make", "loop", "health", "uninstall", "help")
        )
        and not p.endswith("/exec-rev-wrap.md")  # workflow-fused (default in Side preset)
    }
    assert atomic_files, "no atomic /hm:* commands in blueprint"
    for path, body in atomic_files.items():
        assert body.count("@hm:feedback:dispatcher-block") == 1, (
            f"{path}: expected 1 marker, got {body.count('@hm:feedback:dispatcher-block')}"
        )
        assert "@hm:/feedback:dispatcher-block" in body


def test_when_feedback_enabled_marker_appears_in_workflow_commands() -> None:
    """Phase 4 validator-W2 fix: fused_workflow MUST be in the rendered set.
    Side preset's default `exec-rev-wrap` workflow guarantees at least one."""
    rendered = _render_blueprint(feedback_enabled=True)
    workflow_files = {p: b for p, b in rendered.items() if p.endswith("/exec-rev-wrap.md")}
    assert workflow_files, "Side preset must render at least one fused workflow command"
    for path, body in workflow_files.items():
        assert body.count("@hm:feedback:dispatcher-block") == 1, (
            f"{path}: expected 1 marker, got {body.count('@hm:feedback:dispatcher-block')}"
        )


# ── StrictUndefined regression — feedback_enabled MUST be in context ─────────


def test_atomic_command_raises_when_feedback_enabled_missing() -> None:
    """If synthesize.py drops the feedback_enabled injection, StrictUndefined trips."""
    tpl = _env.get_template("commands/hm/atomic_command.md.j2")
    with pytest.raises(jinja2.UndefinedError):
        tpl.render(stage="research", stage_body="x", config={"locale": "en"})


# ── synthesize.py propagation contract (validator C1 verification) ───────────


def test_synthesize_propagates_feedback_enabled_to_command_render_contexts() -> None:
    profile = ProjectProfile()
    answers = InterviewAnswers(
        preset=Preset.SIDE,
        targets=[Target.CLAUDE_CODE],
        feedback=FeedbackConfig(enabled=True),
    )
    blueprint = synthesize(profile, answers)
    hm_commands = [
        f for f in blueprint.files if str(f.path).endswith(".md") and "commands/hm/" in str(f.path)
    ]
    assert hm_commands
    for fe in hm_commands:
        assert fe.context.get("feedback_enabled") is True, (
            f"feedback_enabled missing from {fe.path} context — ADR-005 regression"
        )


def test_synthesize_default_off_propagates_feedback_enabled_false() -> None:
    profile = ProjectProfile()
    answers = InterviewAnswers(preset=Preset.SIDE, targets=[Target.CLAUDE_CODE])
    blueprint = synthesize(profile, answers)
    hm_commands = [
        f for f in blueprint.files if str(f.path).endswith(".md") and "commands/hm/" in str(f.path)
    ]
    assert hm_commands
    for fe in hm_commands:
        assert fe.context.get("feedback_enabled") is False
