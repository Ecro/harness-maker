"""Tests for the baseline measurement script (Phase 2)."""

from __future__ import annotations

# Import after ensuring the scripts dir is importable
import importlib
import json
import sys
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType

import pytest


@pytest.fixture
def baseline_module() -> Iterator[ModuleType]:
    """Import the baseline script as a module."""
    scripts_dir = Path(__file__).resolve().parent.parent.parent / "scripts"
    sys.path.insert(0, str(scripts_dir))
    try:
        mod = importlib.import_module("measure_workflow_baseline")
        yield mod
    finally:
        sys.path.pop(0)
        sys.modules.pop("measure_workflow_baseline", None)


def test_baseline_collects_all_axes(
    baseline_module: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """All required axes must be present in the baseline output."""
    commands_dir = tmp_path / ".claude" / "commands" / "hm"
    commands_dir.mkdir(parents=True)

    (commands_dir / "review.md").write_text("# Review\nDrift gate check\n", encoding="utf-8")
    (commands_dir / "exec-rev-wrap-ver.md").write_text(
        "# Fused\nDrift gate\ndrift_verdict\nDrift check\n",
        encoding="utf-8",
    )

    def mock_time_command(cmd: object, cwd: object = None) -> tuple[float, int]:
        return (1.23, 0)

    monkeypatch.setattr(baseline_module, "_time_command", mock_time_command)

    data = baseline_module.measure_baseline(tmp_path)

    for axis in baseline_module.REQUIRED_AXES:
        assert axis in data, f"missing required axis: {axis}"

    assert isinstance(data["pytest_seconds"], float)
    assert isinstance(data["mypy_seconds"], float)
    assert isinstance(data["ruff_seconds"], float)
    assert isinstance(data["machine"], dict)
    assert "os" in data["machine"]
    assert "cpu" in data["machine"]
    assert "python" in data["machine"]


def test_baseline_drift_count(baseline_module: ModuleType, tmp_path: Path) -> None:
    """Drift gate counting must find the correct number of mentions."""
    commands_dir = tmp_path / ".claude" / "commands" / "hm"
    commands_dir.mkdir(parents=True)

    (commands_dir / "review.md").write_text(
        "## Step 2 — Drift gate\nCheck drift_verdict here\n",
        encoding="utf-8",
    )
    (commands_dir / "wrapup.md").write_text(
        "## Step 3 — Drift gate (advisory)\n",
        encoding="utf-8",
    )
    (commands_dir / "execute.md").write_text(
        "# Execute\nNo drift references\n",
        encoding="utf-8",
    )

    counts = baseline_module._count_drift_gates(tmp_path)
    assert counts["review"] == 2
    assert counts["wrapup"] == 1
    assert "execute" not in counts


def test_baseline_save_and_load(baseline_module: ModuleType, tmp_path: Path) -> None:
    """Baseline JSON must round-trip through save/load."""
    data = {"measured_at": "2026-01-01T00:00:00+00:00", "pytest_seconds": 42.0}
    out_path = tmp_path / "baseline.json"

    saved = baseline_module.save_baseline(data, output_path=out_path)
    assert saved == out_path
    assert out_path.is_file()

    loaded = json.loads(out_path.read_text(encoding="utf-8"))
    assert loaded["pytest_seconds"] == 42.0


def test_baseline_cache_dir_env_override(
    baseline_module: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """HARNESS_MAKER_CACHE_DIR must override the default cache path."""
    custom = tmp_path / "custom-cache"
    monkeypatch.setenv("HARNESS_MAKER_CACHE_DIR", str(custom))
    result = baseline_module._cache_dir()
    assert result == custom


def test_baseline_compare(baseline_module: ModuleType, tmp_path: Path) -> None:
    """Compare must produce a markdown delta table."""
    prior = {
        "pytest_seconds": 10.0,
        "mypy_seconds": 5.0,
        "ruff_seconds": 0.5,
        "drift_call_count_fused_exec_rev_wrap_ver": 4,
    }
    prior_path = tmp_path / "prior.json"
    prior_path.write_text(json.dumps(prior), encoding="utf-8")

    current = {
        "pytest_seconds": 8.0,
        "mypy_seconds": 4.0,
        "ruff_seconds": 0.4,
        "drift_call_count_fused_exec_rev_wrap_ver": 1,
    }

    report = baseline_module.compare_baselines(current, prior_path)
    assert "Delta" in report
    assert "pytest_seconds" in report
    assert "-2.00s" in report
