"""Phase 5 — CLI --recommended-model deprecation alias to --default-model.

ADR-012: deprecate in 0.15.0 with DeprecationWarning, remove no earlier than 0.17.0.
"""

from __future__ import annotations

import os
import warnings
from pathlib import Path

from typer.testing import CliRunner

from harness_maker.cli import app


def test_recommended_model_emits_deprecation_warning(tmp_path: Path) -> None:
    """--recommended-model still works but emits DeprecationWarning."""
    runner = CliRunner()

    with warnings.catch_warnings(record=True) as recorded:
        warnings.simplefilter("always")
        result = runner.invoke(
            app,
            [
                "make",
                str(tmp_path),
                "--autoloop",
                "--recommended-model",
                "claude-sonnet-4-6",
            ],
        )

    assert result.exit_code == 0, result.output
    dep_warnings = [
        w
        for w in recorded
        if issubclass(w.category, DeprecationWarning) and "recommended-model" in str(w.message)
    ]
    assert dep_warnings, (
        f"expected DeprecationWarning mentioning --recommended-model, got: "
        f"{[(w.category.__name__, str(w.message)) for w in recorded]}"
    )


def test_default_model_works_without_deprecation(tmp_path: Path) -> None:
    """--default-model is the canonical flag and does NOT emit deprecation."""
    runner = CliRunner()

    with warnings.catch_warnings(record=True) as recorded:
        warnings.simplefilter("always")
        result = runner.invoke(
            app,
            [
                "make",
                str(tmp_path),
                "--autoloop",
                "--default-model",
                "claude-opus-4-7",
            ],
        )

    assert result.exit_code == 0, result.output
    dep_warnings = [
        w
        for w in recorded
        if issubclass(w.category, DeprecationWarning) and "recommended-model" in str(w.message)
    ]
    assert not dep_warnings, (
        f"--default-model should NOT trigger deprecation warning: "
        f"{[str(w.message) for w in dep_warnings]}"
    )


def test_recommended_model_value_applied(tmp_path: Path) -> None:
    """The deprecated alias still applies the value to default_model.

    Two-step: bootstrap first, then re-render with the deprecated flag.
    Must `os.chdir(tmp_path)` so the Phase 7 cwd guard (ADR-013) doesn't
    fire when pytest itself runs inside the harness-maker .worktrees/ tree.
    """
    runner = CliRunner()
    cwd_before = os.getcwd()
    try:
        os.chdir(tmp_path)
        result1 = runner.invoke(app, ["make", str(tmp_path), "--autoloop"])
        assert result1.exit_code == 0, result1.output
        result2 = runner.invoke(
            app,
            [
                "make",
                str(tmp_path),
                "--autoloop",
                "--recommended-model",
                "claude-sonnet-4-6",
                "--update",
            ],
        )
        assert result2.exit_code == 0, result2.output
        rendered = (tmp_path / ".claude" / "harness.yaml").read_text(encoding="utf-8")
        assert "claude-sonnet-4-6" in rendered, rendered[:500]
    finally:
        os.chdir(cwd_before)
