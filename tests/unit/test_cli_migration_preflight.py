"""Phase 6 (ADR-008): make --update enablement-preflight migration.

`make --update` on an existing worktree-enabled harness that has never been
migrated (no `feature_branch_workflow` key) flips the flag to True ONLY on a clean
live-state probe; a pending old-model state (stash ref / loop marker / in-flight
worktree) defers with a loud warning; an explicit `false` opt-out / `true` is
respected. The migrate path mutates config only — never git.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from harness_maker.cli import app
from harness_maker.interview import _build_answers
from harness_maker.models import AtomicStage, DevMode, Preset, Target

runner = CliRunner()

_MUTATING_GIT = {
    "commit",
    "branch",
    "worktree",
    "stash",
    "checkout",
    "reset",
    "merge",
    "rebase",
    "add",
    "push",
    "rm",
    "clean",
}


def _answers(*, preset: Preset, worktree: dict[str, Any]):  # type: ignore[no-untyped-def]
    base = _build_answers(
        locale="en",
        targets=[Target.CLAUDE_CODE],
        preset=preset,
        dev_mode=DevMode.TASK_DRIVEN,
        fused_workflows={
            "exec-rev-wrap": [AtomicStage.EXECUTE, AtomicStage.REVIEW, AtomicStage.WRAPUP]
        },
        default_workflow="exec-rev-wrap",
    )
    # Simulate the answers_from_harness_yaml round-trip result (the on-disk worktree).
    return base.model_copy(update={"worktree": dict(worktree)})


def _harness_dir(tmp_path: Path) -> Path:
    claude = tmp_path / ".claude"
    claude.mkdir(parents=True, exist_ok=True)
    (claude / "harness.yaml").write_text(
        "---\nharness_maker_version: 0.1.0\n---\npreset: Production\n", encoding="utf-8"
    )
    return tmp_path


def _run_make_update(target: Path, answers: Any) -> tuple[Any, list[list[str]], Any]:
    """Run `make --update` with downstream mocked + synthesize capturing `a`; also
    spy git calls. Returns (captured_answers, git_calls, cli_result)."""
    captured: dict[str, Any] = {}
    git_calls: list[list[str]] = []
    real_run = subprocess.run

    def _syn(p: Any, a: Any) -> Any:
        captured["a"] = a
        return MagicMock(files=[])

    def _git_spy(args: Any, *a: Any, **kw: Any) -> Any:
        if isinstance(args, list) and args and args[0] == "git":
            git_calls.append(args)
        return real_run(args, *a, **kw)

    with (
        patch("harness_maker.cli.profile", return_value=MagicMock()),
        patch("harness_maker.cli.synthesize", side_effect=_syn),
        patch("harness_maker.cli.render"),
        patch("harness_maker.cli.verify", return_value=[]),
        patch("harness_maker.cli.backup"),
        patch("harness_maker.cli.reconcile", return_value=[]),
        patch("harness_maker.cli.sweep_orphans", return_value=MagicMock(deleted=[], kept=[])),
        patch("harness_maker.cli._emit_post_make_readiness"),
        patch("harness_maker.cli._emit_refdocs_index_build"),
        patch("harness_maker.cli.answers_from_harness_yaml", return_value=answers),
        patch("harness_maker.worktree.subprocess.run", side_effect=_git_spy),
    ):
        result = runner.invoke(app, ["make", str(target), "--update"])
    return captured.get("a"), git_calls, result


# ── clean key-absent → flip + no mutating git ────────────────────────────────


def test_clean_keyabsent_flips_and_no_mutating_git(tmp_path: Path) -> None:
    target = _harness_dir(tmp_path)
    a, git_calls, result = _run_make_update(
        target, _answers(preset=Preset.PRODUCTION, worktree={"enabled": True})
    )
    assert result.exit_code == 0, result.output
    assert a.worktree.get("feature_branch_workflow") is True
    for call in git_calls:
        verb = call[1] if len(call) > 1 else ""
        assert verb not in _MUTATING_GIT, f"migrate path mutated git: {call}"


# ── each pending old-model state defers + warns ──────────────────────────────


def test_pending_stash_defers(tmp_path: Path) -> None:
    target = _harness_dir(tmp_path)
    (target / ".claude" / ".hm-finalize-stash-execute-x").write_text("r\n")
    a, _g, result = _run_make_update(
        target, _answers(preset=Preset.PRODUCTION, worktree={"enabled": True})
    )
    assert "feature_branch_workflow" not in a.worktree  # NOT flipped
    assert "deferred" in result.output


def test_pending_loop_marker_defers(tmp_path: Path) -> None:
    target = _harness_dir(tmp_path)
    (target / ".claude" / ".hm-loop-execute-y").write_text("x\n")
    a, _g, result = _run_make_update(
        target, _answers(preset=Preset.PRODUCTION, worktree={"enabled": True})
    )
    assert "feature_branch_workflow" not in a.worktree
    assert "deferred" in result.output


def test_pending_inflight_worktree_defers(tmp_path: Path) -> None:
    target = _harness_dir(tmp_path)
    (target / ".worktrees" / "execute-z-20260620T0000Z").mkdir(parents=True)
    a, _g, result = _run_make_update(
        target, _answers(preset=Preset.PRODUCTION, worktree={"enabled": True})
    )
    assert "feature_branch_workflow" not in a.worktree
    assert "deferred" in result.output


# ── explicit user choice respected (round-tripped) ───────────────────────────


def test_explicit_false_opt_out_not_flipped(tmp_path: Path) -> None:
    target = _harness_dir(tmp_path)
    a, _g, result = _run_make_update(
        target,
        _answers(
            preset=Preset.PRODUCTION, worktree={"enabled": True, "feature_branch_workflow": False}
        ),
    )
    assert result.exit_code == 0, result.output
    assert a.worktree.get("feature_branch_workflow") is False  # opt-out preserved


def test_explicit_true_not_reprobed(tmp_path: Path) -> None:
    target = _harness_dir(tmp_path)
    # plant a pending state: if the preflight wrongly re-ran it would warn — it must NOT.
    (target / ".claude" / ".hm-loop-execute-q").write_text("x\n")
    a, _g, result = _run_make_update(
        target,
        _answers(
            preset=Preset.PRODUCTION, worktree={"enabled": True, "feature_branch_workflow": True}
        ),
    )
    assert a.worktree.get("feature_branch_workflow") is True
    assert "deferred" not in result.output  # already migrated → no re-probe


# ── Side (worktree disabled) is never migrated ───────────────────────────────


def test_side_worktree_disabled_not_flipped(tmp_path: Path) -> None:
    target = _harness_dir(tmp_path)
    a, _g, result = _run_make_update(
        target, _answers(preset=Preset.SIDE, worktree={"enabled": False})
    )
    assert result.exit_code == 0, result.output
    assert "feature_branch_workflow" not in a.worktree
