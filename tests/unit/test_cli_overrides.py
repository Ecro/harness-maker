"""Tests for CLI per-dimension override flags (--preset / --locale / --dev-mode / --targets)."""

from __future__ import annotations

import pytest
import typer

from harness_maker.cli import _apply_dimension_overrides
from harness_maker.interview import _build_answers
from harness_maker.models import DevMode, InterviewAnswers, Preset, Target


def _baseline_side() -> InterviewAnswers:
    return _build_answers(
        locale="en",
        targets=[Target.CLAUDE_CODE],
        preset=Preset.SIDE,
        dev_mode=DevMode.TASK_DRIVEN,
    )


def test_no_overrides_returns_input_unchanged() -> None:
    a = _baseline_side()
    out = _apply_dimension_overrides(
        a,
        preset_override=None,
        locale_override=None,
        dev_mode_override=None,
        targets_override=None,
    )
    assert out is a  # short-circuit when nothing to apply


def test_locale_override_sets_locale() -> None:
    a = _baseline_side()
    out = _apply_dimension_overrides(
        a,
        preset_override=None,
        locale_override="ko",
        dev_mode_override=None,
        targets_override=None,
    )
    assert out.locale == "ko"
    assert out.preset == Preset.SIDE  # untouched


def test_dev_mode_override_sets_dev_mode() -> None:
    a = _baseline_side()
    out = _apply_dimension_overrides(
        a,
        preset_override=None,
        locale_override=None,
        dev_mode_override="spec-driven",
        targets_override=None,
    )
    assert out.dev_mode == DevMode.SPEC_DRIVEN


def test_dev_mode_override_invalid_aborts() -> None:
    a = _baseline_side()
    with pytest.raises(typer.Exit):
        _apply_dimension_overrides(
            a,
            preset_override=None,
            locale_override=None,
            dev_mode_override="bogus",
            targets_override=None,
        )


def test_preset_override_rederives_extras() -> None:
    """Side → Production must unlock Production-only extras (anti_rot, worktree, etc.)."""
    a = _baseline_side()
    assert a.anti_rot.get("enabled") is False  # Side default
    out = _apply_dimension_overrides(
        a,
        preset_override="Production",
        locale_override=None,
        dev_mode_override=None,
        targets_override=None,
    )
    assert out.preset == Preset.PRODUCTION
    assert out.anti_rot.get("enabled") is True
    assert out.worktree.get("enabled") is True
    assert out.context_lint.get("enabled") is True
    # carry-overs
    assert out.locale == "en"
    assert out.dev_mode == DevMode.TASK_DRIVEN
    assert out.consensus == a.consensus


def test_preset_override_invalid_aborts() -> None:
    a = _baseline_side()
    with pytest.raises(typer.Exit):
        _apply_dimension_overrides(
            a,
            preset_override="Experimental",
            locale_override=None,
            dev_mode_override=None,
            targets_override=None,
        )


def test_preset_override_same_preset_is_noop() -> None:
    """Side → Side shouldn't trigger the rebuild path (perf + idempotency)."""
    a = _baseline_side()
    out = _apply_dimension_overrides(
        a,
        preset_override="Side",
        locale_override=None,
        dev_mode_override=None,
        targets_override=None,
    )
    assert out.preset == Preset.SIDE
    # Internals (anti_rot etc.) carry through untouched
    assert out.anti_rot == a.anti_rot


def test_combined_overrides_apply_all() -> None:
    a = _baseline_side()
    out = _apply_dimension_overrides(
        a,
        preset_override="Production",
        locale_override="ko",
        dev_mode_override="spec-driven",
        targets_override="claude-code,cursor",
    )
    assert out.preset == Preset.PRODUCTION
    assert out.locale == "ko"
    assert out.dev_mode == DevMode.SPEC_DRIVEN
    assert out.targets == [Target.CLAUDE_CODE, Target.CURSOR]


def test_targets_override_single_cursor() -> None:
    a = _baseline_side()
    assert a.targets == [Target.CLAUDE_CODE]
    out = _apply_dimension_overrides(
        a,
        preset_override=None,
        locale_override=None,
        dev_mode_override=None,
        targets_override="cursor",
    )
    assert out.targets == [Target.CURSOR]


def test_targets_override_both_preserves_order() -> None:
    a = _baseline_side()
    out = _apply_dimension_overrides(
        a,
        preset_override=None,
        locale_override=None,
        dev_mode_override=None,
        targets_override="cursor,claude-code",
    )
    # input order preserved
    assert out.targets == [Target.CURSOR, Target.CLAUDE_CODE]


def test_targets_override_dedupes() -> None:
    a = _baseline_side()
    out = _apply_dimension_overrides(
        a,
        preset_override=None,
        locale_override=None,
        dev_mode_override=None,
        targets_override="cursor,cursor,claude-code",
    )
    assert out.targets == [Target.CURSOR, Target.CLAUDE_CODE]


def test_targets_override_whitespace_tolerant() -> None:
    a = _baseline_side()
    out = _apply_dimension_overrides(
        a,
        preset_override=None,
        locale_override=None,
        dev_mode_override=None,
        targets_override=" claude-code , cursor ",
    )
    assert out.targets == [Target.CLAUDE_CODE, Target.CURSOR]


def test_targets_override_invalid_aborts() -> None:
    a = _baseline_side()
    with pytest.raises(typer.Exit):
        _apply_dimension_overrides(
            a,
            preset_override=None,
            locale_override=None,
            dev_mode_override=None,
            targets_override="vscode",
        )


def test_targets_override_empty_aborts() -> None:
    """`--targets ,,` (only commas/whitespace) must reject — min_length=1."""
    a = _baseline_side()
    with pytest.raises(typer.Exit):
        _apply_dimension_overrides(
            a,
            preset_override=None,
            locale_override=None,
            dev_mode_override=None,
            targets_override=" , , ",
        )


def test_targets_override_with_preset_switch() -> None:
    """Targets carry through a preset rebuild (override applied on top of rebuild)."""
    a = _baseline_side()
    out = _apply_dimension_overrides(
        a,
        preset_override="Production",
        locale_override=None,
        dev_mode_override=None,
        targets_override="claude-code,cursor",
    )
    assert out.preset == Preset.PRODUCTION
    assert out.targets == [Target.CLAUDE_CODE, Target.CURSOR]


def test_empty_list_overrides_clear_configurable_lists() -> None:
    """Configure's clear action passes an empty string; it must clear lists."""
    a = _baseline_side().model_copy(
        update={
            "domains": ["python", "react"],
            "mechanical_checks": ["ruff check ."],
            "wrapup_docs": ["CHANGELOG.md"],
            "sibling_repos": ["../backend"],
        }
    )
    out = _apply_dimension_overrides(
        a,
        preset_override=None,
        locale_override=None,
        dev_mode_override=None,
        targets_override=None,
        domains_override="",
        mechanical_checks_override="",
        wrapup_docs_override="",
        sibling_repos_override="",
    )
    assert out.domains == []
    assert out.mechanical_checks == []
    assert out.wrapup_docs == []
    assert out.sibling_repos == []


def test_empty_ref_folders_override_clears_ref_folders() -> None:
    from harness_maker.models import RefFolder

    a = _baseline_side().model_copy(update={"ref_folders": [RefFolder(path="./docs")]})
    out = _apply_dimension_overrides(
        a,
        preset_override=None,
        locale_override=None,
        dev_mode_override=None,
        targets_override=None,
        ref_folders_override="",
    )
    assert out.ref_folders == []


def test_ref_folders_override_denormalizes_home_to_tilde(monkeypatch: pytest.MonkeyPatch) -> None:
    """Bash expands ``~/foo`` to ``/home/user/foo`` at variable assignment;
    the CLI must store ``~/foo`` so harness.yaml stays portable across machines.
    """
    monkeypatch.setenv("HOME", "/home/alice")
    a = _baseline_side()
    out = _apply_dimension_overrides(
        a,
        preset_override=None,
        locale_override=None,
        dev_mode_override=None,
        targets_override=None,
        ref_folders_override="/home/alice/edge_bsp_foundation",
    )
    assert len(out.ref_folders) == 1
    assert out.ref_folders[0].path == "~/edge_bsp_foundation"


def test_ref_folders_override_leaves_non_home_paths_alone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Absolute paths outside $HOME and relative paths must pass through."""
    monkeypatch.setenv("HOME", "/home/alice")
    a = _baseline_side()
    out = _apply_dimension_overrides(
        a,
        preset_override=None,
        locale_override=None,
        dev_mode_override=None,
        targets_override=None,
        ref_folders_override="/opt/docs::../shared",
    )
    paths = [rf.path for rf in out.ref_folders]
    assert paths == ["/opt/docs", "../shared"]


def test_second_brain_vault_path_denormalizes_home_to_tilde(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Same shell-expansion problem hits --second-brain-vault-path."""
    monkeypatch.setenv("HOME", "/home/alice")
    a = _baseline_side()
    out = _apply_dimension_overrides(
        a,
        preset_override=None,
        locale_override=None,
        dev_mode_override=None,
        targets_override=None,
        second_brain_vault_path="/home/alice/Obsidian/Main",
    )
    assert out.second_brain.vault_path == "~/Obsidian/Main"
