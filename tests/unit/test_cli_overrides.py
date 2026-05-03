"""Tests for CLI per-dimension override flags (--preset / --locale / --dev-mode)."""

from __future__ import annotations

import pytest
import typer

from harness_maker.cli import _apply_dimension_overrides
from harness_maker.interview import _build_answers
from harness_maker.models import AtomicStage, DevMode, Preset


def _baseline_side() -> object:
    return _build_answers(
        locale="en",
        preset=Preset.SIDE,
        dev_mode=DevMode.TASK_DRIVEN,
        fused_workflows={
            "exec-rev-wrap": [
                AtomicStage.EXECUTE,
                AtomicStage.REVIEW,
                AtomicStage.WRAPUP,
            ],
        },
        default_workflow="exec-rev-wrap",
    )


def test_no_overrides_returns_input_unchanged() -> None:
    a = _baseline_side()
    out = _apply_dimension_overrides(
        a,
        preset_override=None,
        locale_override=None,
        dev_mode_override=None,
    )
    assert out is a  # short-circuit when nothing to apply


def test_locale_override_sets_locale() -> None:
    a = _baseline_side()
    out = _apply_dimension_overrides(
        a,
        preset_override=None,
        locale_override="ko",
        dev_mode_override=None,
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
    )
    assert out.preset == Preset.PRODUCTION
    assert out.anti_rot.get("enabled") is True
    assert out.worktree.get("enabled") is True
    assert out.context_lint.get("enabled") is True
    # carry-overs
    assert out.locale == "en"
    assert out.dev_mode == DevMode.TASK_DRIVEN
    assert out.fused_workflows == a.fused_workflows


def test_preset_override_invalid_aborts() -> None:
    a = _baseline_side()
    with pytest.raises(typer.Exit):
        _apply_dimension_overrides(
            a,
            preset_override="Experimental",
            locale_override=None,
            dev_mode_override=None,
        )


def test_preset_override_same_preset_is_noop() -> None:
    """Side → Side shouldn't trigger the rebuild path (perf + idempotency)."""
    a = _baseline_side()
    out = _apply_dimension_overrides(
        a,
        preset_override="Side",
        locale_override=None,
        dev_mode_override=None,
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
    )
    assert out.preset == Preset.PRODUCTION
    assert out.locale == "ko"
    assert out.dev_mode == DevMode.SPEC_DRIVEN
