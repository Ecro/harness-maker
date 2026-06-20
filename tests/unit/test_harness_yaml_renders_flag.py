"""Phase 6 (ADR-008, REVIEW Codex P0): the feature_branch_workflow flag must be
SERIALIZED into the rendered .claude/harness.yaml — not only set in-memory.

Regression guard for the stage↔runtime mismatch: the stage templates read the flag
from the render context (config.worktree), so they'd render the flag-on preflight;
but `_feature_branch_workflow_enabled` reads the on-disk harness.yaml at runtime. If
the harness.yaml template doesn't emit the flag, the worktree machinery falls back
to the OLD model while the stages instruct the NEW model — a silent strand hazard.
This test renders a real harness and asserts the runtime reader agrees with the
rendered config.
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
    root = _render(
        tmp_path,
        preset=Preset.PRODUCTION,
        worktree_dict={"enabled": True, "feature_branch_workflow": True},
    )
    hy = root / ".claude" / "harness.yaml"
    assert "feature_branch_workflow: true" in hy.read_text(encoding="utf-8")
    # the runtime reader (reads the on-disk harness.yaml) must agree
    assert worktree._feature_branch_workflow_enabled(root) is True
    # the dict round-trips via the canonical loader too
    assert load_harness_yaml(hy)["worktree"]["feature_branch_workflow"] is True


def test_flag_off_opt_out_serialized_and_runtime_reads_false(tmp_path: Path) -> None:
    root = _render(
        tmp_path,
        preset=Preset.PRODUCTION,
        worktree_dict={"enabled": True, "feature_branch_workflow": False},
    )
    hy = root / ".claude" / "harness.yaml"
    assert "feature_branch_workflow: false" in hy.read_text(encoding="utf-8")
    assert worktree._feature_branch_workflow_enabled(root) is False


def test_flag_absent_not_serialized_runtime_old_model(tmp_path: Path) -> None:
    # No flag key → harness.yaml omits it → runtime conservative old-model.
    root = _render(tmp_path, preset=Preset.SIDE, worktree_dict={"enabled": False})
    hy = root / ".claude" / "harness.yaml"
    assert "feature_branch_workflow" not in hy.read_text(encoding="utf-8")
    assert worktree._feature_branch_workflow_enabled(root) is False


def test_runtime_reader_treats_string_flag_as_old_model(tmp_path: Path) -> None:
    # REVIEW code P2: a hand-edited string "false" is truthy to bool() — the runtime
    # reader must NOT read it as enabled (mirror the interview-layer bool-strictness).
    claude = tmp_path / ".claude"
    claude.mkdir(parents=True)
    (claude / "harness.yaml").write_text(
        "---\ngenerated_by: harness-maker\n---\n"
        'preset: Production\nworktree:\n  enabled: true\n  feature_branch_workflow: "false"\n',
        encoding="utf-8",
    )
    assert worktree._feature_branch_workflow_enabled(tmp_path) is False
