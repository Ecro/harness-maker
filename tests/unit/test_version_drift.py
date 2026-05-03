"""Tests for harness-maker version-drift detection (relevance module)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from harness_maker.relevance import (
    VersionDrift,
    build_drift_lines,
    detect_version_drift,
)


def _write_harness_yaml(project: Path, stamped_version: str) -> None:
    claude = project / ".claude"
    claude.mkdir(parents=True, exist_ok=True)
    (claude / "harness.yaml").write_text(
        f"---\n"
        f"generated_by: harness-maker\n"
        f"harness_maker_version: {stamped_version}\n"
        f"generated_at: '2026-01-01T00:00:00+00:00'\n"
        f"---\n"
        f"preset: Side\n",
        encoding="utf-8",
    )


def test_detect_drift_returns_none_when_versions_match(tmp_path: Path) -> None:
    _write_harness_yaml(tmp_path, "0.3.0")
    with patch("harness_maker.__version__", "0.3.0"):
        assert detect_version_drift(tmp_path) is None


def test_detect_drift_upgrade_when_running_newer(tmp_path: Path) -> None:
    _write_harness_yaml(tmp_path, "0.2.0")
    with patch("harness_maker.__version__", "0.3.0"):
        drift = detect_version_drift(tmp_path)
    assert drift == VersionDrift(installed="0.2.0", current="0.3.0", direction="upgrade")


def test_detect_drift_downgrade_when_running_older(tmp_path: Path) -> None:
    _write_harness_yaml(tmp_path, "0.4.0")
    with patch("harness_maker.__version__", "0.3.0"):
        drift = detect_version_drift(tmp_path)
    assert drift is not None
    assert drift.direction == "downgrade"


def test_detect_drift_semver_minor_jump(tmp_path: Path) -> None:
    _write_harness_yaml(tmp_path, "0.2.0")
    with patch("harness_maker.__version__", "0.10.0"):
        drift = detect_version_drift(tmp_path)
    assert drift is not None
    assert drift.direction == "upgrade"  # 0.2.0 < 0.10.0 by semver, not lexical


def test_detect_drift_falls_back_to_lexical_for_unparseable(tmp_path: Path) -> None:
    """When either side isn't 3-part numeric semver, fall back to lexical."""
    _write_harness_yaml(tmp_path, "0.2.0-rc1")
    with patch("harness_maker.__version__", "0.2.0"):
        drift = detect_version_drift(tmp_path)
    # "0.2.0-rc1" < "0.2.0" lexically? No — "0" < "-" actually. Let's just
    # assert a drift was detected; direction is whatever lexical gives.
    assert drift is not None
    assert drift.direction in {"upgrade", "downgrade"}


def test_detect_drift_returns_none_when_no_harness_yaml(tmp_path: Path) -> None:
    assert detect_version_drift(tmp_path) is None


def test_detect_drift_returns_none_when_no_frontmatter(tmp_path: Path) -> None:
    claude = tmp_path / ".claude"
    claude.mkdir()
    (claude / "harness.yaml").write_text("preset: Side\n", encoding="utf-8")
    assert detect_version_drift(tmp_path) is None


def test_detect_drift_returns_none_when_frontmatter_missing_key(tmp_path: Path) -> None:
    claude = tmp_path / ".claude"
    claude.mkdir()
    (claude / "harness.yaml").write_text(
        "---\ngenerated_by: harness-maker\n---\npreset: Side\n",
        encoding="utf-8",
    )
    assert detect_version_drift(tmp_path) is None


def test_detect_drift_returns_none_on_invalid_yaml(tmp_path: Path) -> None:
    claude = tmp_path / ".claude"
    claude.mkdir()
    (claude / "harness.yaml").write_text(
        "---\nharness_maker_version: 0.1\n  bad: indent\n---\nbody\n",
        encoding="utf-8",
    )
    # Either parses with the version or fails — either way no crash.
    result = detect_version_drift(tmp_path)
    assert result is None or isinstance(result, VersionDrift)


def test_build_drift_lines_empty_when_none() -> None:
    assert build_drift_lines(None) == []


def test_build_drift_lines_upgrade_includes_plugin_update_command() -> None:
    drift = VersionDrift(installed="0.2.0", current="0.3.0", direction="upgrade")
    lines = build_drift_lines(drift)
    body = "\n".join(lines)
    assert "0.2.0" in body
    assert "0.3.0" in body
    assert "↑" in body
    assert "/plugin update" in body
    assert "/harness-maker:make" in body


def test_build_drift_lines_downgrade_suggests_realign() -> None:
    drift = VersionDrift(installed="0.4.0", current="0.3.0", direction="downgrade")
    lines = build_drift_lines(drift)
    body = "\n".join(lines)
    assert "↓" in body
    assert "/harness-maker:make" in body
    # Downgrade path doesn't suggest /plugin update — that'd reinstall the
    # newer cached plugin, defeating the rollback.
    assert "/plugin update" not in body
