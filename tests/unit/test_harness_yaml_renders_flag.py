"""The isolation flag must be SERIALIZED into the rendered .claude/harness.yaml —
not only set in-memory (originally Phase 6 / ADR-008; renamed to `worktree.enabled`
by PLAN-worktree-side-defaults ADR-007).

Regression guard for the stage↔runtime mismatch: the stage templates read the flag
from the render context (`config.worktree`), so they render the flag-on preflight;
but the runtime reader reads the on-disk harness.yaml. If the harness.yaml template
doesn't emit the flag, the worktree machinery falls back to isolation-off while the
stages instruct the isolated model — a silent strand hazard. This test renders a
real harness and asserts the runtime reader agrees with the rendered config.
"""

from __future__ import annotations

from pathlib import Path

from harness_maker import worktree
from harness_maker.io_utils import load_harness_yaml
from harness_maker.models import InterviewAnswers, Preset, ProjectProfile, Target
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize


def _render(tmp_path: Path, *, preset: Preset, worktree_dict: dict) -> Path:  # type: ignore[type-arg]
    """Render into <tmp>/.claude (mirrors real `make` layout) and return the
    project root (parent of .claude) so the runtime reader resolves correctly."""
    bp = synthesize(
        ProjectProfile(),
        InterviewAnswers(preset=preset, targets=[Target.CLAUDE_CODE], worktree=worktree_dict),
    )
    render(bp, tmp_path / ".claude", freeze_time=DEFAULT_FREEZE_TIME)
    return tmp_path


def test_flag_on_serialized_and_runtime_reads_true(tmp_path: Path) -> None:
    root = _render(tmp_path, preset=Preset.PRODUCTION, worktree_dict={"enabled": True})
    hy = root / ".claude" / "harness.yaml"
    assert "enabled: true" in hy.read_text(encoding="utf-8")
    assert worktree.worktree_enabled(root) is True
    assert load_harness_yaml(hy)["worktree"]["enabled"] is True


def test_flag_off_opt_out_serialized_and_runtime_reads_false(tmp_path: Path) -> None:
    root = _render(tmp_path, preset=Preset.PRODUCTION, worktree_dict={"enabled": False})
    hy = root / ".claude" / "harness.yaml"
    assert "enabled: false" in hy.read_text(encoding="utf-8")
    assert worktree.worktree_enabled(root) is False


def test_legacy_answers_dict_still_renders(tmp_path: Path) -> None:
    """`synthesize` is the single normalization point, so an answers dict from
    before the collapse resolves rather than rendering StrictUndefined."""
    root = _render(
        tmp_path, preset=Preset.PRODUCTION, worktree_dict={"feature_branch_workflow": True}
    )
    assert worktree.worktree_enabled(root) is True


def test_runtime_reader_treats_string_flag_as_fail_closed(tmp_path: Path) -> None:
    """A hand-edited non-bool is truthy to `bool(...)`; it must resolve OFF and must
    NOT fall through to a stale legacy key."""
    (tmp_path / ".claude").mkdir(parents=True)
    (tmp_path / ".claude" / "harness.yaml").write_text(
        'preset: Production\nworktree:\n  enabled: "false"\n  feature_branch_workflow: true\n',
        encoding="utf-8",
    )
    assert worktree.worktree_enabled(tmp_path) is False


def test_deprecated_alias_still_resolves(tmp_path: Path) -> None:
    root = _render(tmp_path, preset=Preset.PRODUCTION, worktree_dict={"enabled": True})
    assert worktree._feature_branch_workflow_enabled(root) is True
