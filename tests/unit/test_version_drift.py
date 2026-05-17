"""Tests for harness-maker version-drift detection.

Moved from relevance to sessionstart_drift in 0.13.0 (PLAN
health-consolidation Phase 1). The hook is the sole consumer; ``/hm:health``
does not surface version drift.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from harness_maker.hooks.sessionstart_drift import (
    VersionDrift,
    detect_version_drift,
    latest_installed_version,
)


@pytest.fixture(autouse=True)
def _clear_drift_cache() -> None:
    """Reset @lru_cache between tests — REVIEW M3 added memoization to
    latest_installed_version, which would otherwise leak state across cases
    that mock _scan_plugin_cache_versions with different return values."""
    latest_installed_version.cache_clear()


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
    with patch(
        "harness_maker.hooks.sessionstart_drift.latest_installed_version",
        return_value="0.3.0",
    ):
        assert detect_version_drift(tmp_path) is None


def test_detect_drift_upgrade_when_running_newer(tmp_path: Path) -> None:
    _write_harness_yaml(tmp_path, "0.2.0")
    with patch(
        "harness_maker.hooks.sessionstart_drift.latest_installed_version",
        return_value="0.3.0",
    ):
        drift = detect_version_drift(tmp_path)
    assert drift == VersionDrift(stamped="0.2.0", current="0.3.0", direction="upgrade")


def test_detect_drift_downgrade_when_running_older(tmp_path: Path) -> None:
    _write_harness_yaml(tmp_path, "0.4.0")
    with patch(
        "harness_maker.hooks.sessionstart_drift.latest_installed_version",
        return_value="0.3.0",
    ):
        drift = detect_version_drift(tmp_path)
    assert drift is not None
    assert drift.direction == "downgrade"


def test_detect_drift_semver_minor_jump(tmp_path: Path) -> None:
    _write_harness_yaml(tmp_path, "0.2.0")
    with patch(
        "harness_maker.hooks.sessionstart_drift.latest_installed_version",
        return_value="0.10.0",
    ):
        drift = detect_version_drift(tmp_path)
    assert drift is not None
    assert drift.direction == "upgrade"  # 0.2.0 < 0.10.0 by semver, not lexical


def test_detect_drift_falls_back_to_lexical_for_unparseable(tmp_path: Path) -> None:
    """When either side isn't 3-part numeric semver, fall back to lexical."""
    _write_harness_yaml(tmp_path, "0.2.0-rc1")
    with patch(
        "harness_maker.hooks.sessionstart_drift.latest_installed_version",
        return_value="0.2.0",
    ):
        drift = detect_version_drift(tmp_path)
    assert drift is not None
    assert drift.direction == "downgrade"


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
    result = detect_version_drift(tmp_path)
    assert result is None or isinstance(result, VersionDrift)


def test_drift_detector_uses_latest_installed_not_imported_version(tmp_path: Path) -> None:
    """detect_version_drift consults the plugin cache, not the imported __version__."""
    _write_harness_yaml(tmp_path, "0.5.7")
    with patch(
        "harness_maker.hooks.sessionstart_drift.latest_installed_version",
        return_value="0.6.1",
    ):
        drift = detect_version_drift(tmp_path)
    assert drift is not None
    assert drift.stamped == "0.5.7"
    assert drift.current == "0.6.1"
    assert drift.direction == "upgrade"


def test_latest_installed_version_falls_back_to_imported_when_cache_empty(
    tmp_path: Path,
) -> None:
    with (
        patch(
            "harness_maker.hooks.sessionstart_drift._scan_plugin_cache_versions",
            return_value=[],
        ),
        patch("harness_maker.__version__", "0.7.7"),
    ):
        assert latest_installed_version() == "0.7.7"


def test_latest_installed_version_picks_highest_semver(tmp_path: Path) -> None:
    with patch(
        "harness_maker.hooks.sessionstart_drift._scan_plugin_cache_versions",
        return_value=["0.3.2", "0.6.1", "0.5.7", "0.10.0", "0.6.0"],
    ):
        assert latest_installed_version() == "0.10.0"


def test_latest_installed_version_skips_unparseable(tmp_path: Path) -> None:
    with patch(
        "harness_maker.hooks.sessionstart_drift._scan_plugin_cache_versions",
        return_value=["random-text", "0.6.1", "not.a.version", ".tmp"],
    ):
        assert latest_installed_version() == "0.6.1"


def test_latest_installed_version_all_unparseable_falls_back(tmp_path: Path) -> None:
    with (
        patch(
            "harness_maker.hooks.sessionstart_drift._scan_plugin_cache_versions",
            return_value=["random-text", "not.a.version", ".tmp", "garbage"],
        ),
        patch("harness_maker.__version__", "0.6.2"),
    ):
        assert latest_installed_version() == "0.6.2"


def test_drift_helper_lives_with_its_caller() -> None:
    """0.13.0 contract: version drift moved out of relevance into the hook
    so the public ``relevance`` surface no longer drags the cache scanner in.
    Asserting the rename keeps a regression visible if a future refactor
    accidentally reintroduces the export.
    """
    import inspect

    from harness_maker.hooks import sessionstart_drift
    from harness_maker.hooks.sessionstart_drift import detect_version_drift as hook_fn

    hook_src = inspect.getsource(sessionstart_drift)
    assert "detect_version_drift" in hook_src
    drift_src = inspect.getsource(hook_fn)
    assert "latest_installed_version()" in drift_src, (
        "detect_version_drift must call latest_installed_version() so a "
        "future cache-bypass regression is caught at source-shape level."
    )
