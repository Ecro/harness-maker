"""Tests for harness-maker version-drift detection (relevance module)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from harness_maker.relevance import (
    VersionDrift,
    build_drift_lines,
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
    with patch("harness_maker.relevance.latest_installed_version", return_value="0.3.0"):
        assert detect_version_drift(tmp_path) is None


def test_detect_drift_upgrade_when_running_newer(tmp_path: Path) -> None:
    _write_harness_yaml(tmp_path, "0.2.0")
    with patch("harness_maker.relevance.latest_installed_version", return_value="0.3.0"):
        drift = detect_version_drift(tmp_path)
    assert drift == VersionDrift(stamped="0.2.0", current="0.3.0", direction="upgrade")


def test_detect_drift_downgrade_when_running_older(tmp_path: Path) -> None:
    _write_harness_yaml(tmp_path, "0.4.0")
    with patch("harness_maker.relevance.latest_installed_version", return_value="0.3.0"):
        drift = detect_version_drift(tmp_path)
    assert drift is not None
    assert drift.direction == "downgrade"


def test_detect_drift_semver_minor_jump(tmp_path: Path) -> None:
    _write_harness_yaml(tmp_path, "0.2.0")
    with patch("harness_maker.relevance.latest_installed_version", return_value="0.10.0"):
        drift = detect_version_drift(tmp_path)
    assert drift is not None
    assert drift.direction == "upgrade"  # 0.2.0 < 0.10.0 by semver, not lexical


def test_detect_drift_falls_back_to_lexical_for_unparseable(tmp_path: Path) -> None:
    """When either side isn't 3-part numeric semver, fall back to lexical."""
    _write_harness_yaml(tmp_path, "0.2.0-rc1")
    with patch("harness_maker.relevance.latest_installed_version", return_value="0.2.0"):
        drift = detect_version_drift(tmp_path)
    # Lexical: "0.2.0-rc1" vs "0.2.0" — first 5 chars equal, then "-" (0x2D)
    # vs "" (string ends). Python string comparison: shorter string is "less"
    # when prefix-equal, so "0.2.0" < "0.2.0-rc1" → stamped > current →
    # downgrade direction. Pin this exact result so a sign-flip in the
    # fallback branch is caught (REVIEW M2 surfaced the loose prior assertion).
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
    # Either parses with the version or fails — either way no crash.
    result = detect_version_drift(tmp_path)
    assert result is None or isinstance(result, VersionDrift)


def test_build_drift_lines_empty_when_none() -> None:
    assert build_drift_lines(None) == []


def test_build_drift_lines_upgrade_includes_plugin_update_command() -> None:
    drift = VersionDrift(stamped="0.2.0", current="0.3.0", direction="upgrade")
    lines = build_drift_lines(drift)
    body = "\n".join(lines)
    assert "0.2.0" in body
    assert "0.3.0" in body
    assert "↑" in body
    assert "/plugin update" in body
    assert "/harness-maker:make" in body


def test_build_drift_lines_downgrade_suggests_realign() -> None:
    drift = VersionDrift(stamped="0.4.0", current="0.3.0", direction="downgrade")
    lines = build_drift_lines(drift)
    body = "\n".join(lines)
    assert "↓" in body
    assert "/harness-maker:make" in body
    # Downgrade path doesn't suggest /plugin update — that'd reinstall the
    # newer cached plugin, defeating the rollback.
    assert "/plugin update" not in body


def test_drift_detector_uses_latest_installed_not_imported_version(tmp_path: Path) -> None:
    """0.6.2 P6 alignment: detect_version_drift consults the plugin cache, not
    the imported __version__.

    Why: ``/hm:refresh`` is rendered with a pinned ``--with <render-time-path>``
    clause, so its in-process ``__version__`` matches harness.yaml exactly and
    the old code returned no drift even after a real plugin upgrade. SessionStart
    hook saw the running plugin's newer ``__version__`` and reported drift.
    The two paths disagreed. After this fix both call
    ``latest_installed_version()`` which reads from the plugin cache — single
    source of truth, both paths see the same verdict.
    """
    _write_harness_yaml(tmp_path, "0.5.7")

    # If detect_version_drift ignored the cache and used __version__ directly,
    # this test would behave differently when run via the pinned-import path
    # vs the system-import path. By patching latest_installed_version we
    # demonstrate that's the only knob the function consults — refactoring
    # callers to inject __version__ directly would break this test.
    with patch("harness_maker.relevance.latest_installed_version", return_value="0.6.1"):
        drift = detect_version_drift(tmp_path)
    assert drift is not None
    assert drift.stamped == "0.5.7"
    assert drift.current == "0.6.1"
    assert drift.direction == "upgrade"


def test_latest_installed_version_falls_back_to_imported_when_cache_empty(
    tmp_path: Path,
) -> None:
    """When ~/.claude/plugins/cache is empty/unreadable, fall back to __version__.

    Required for environments without Claude Code installed (CI, dev sandboxes).
    """
    from harness_maker.relevance import latest_installed_version

    with (
        patch("harness_maker.relevance._scan_plugin_cache_versions", return_value=[]),
        patch("harness_maker.__version__", "0.7.7"),
    ):
        assert latest_installed_version() == "0.7.7"


def test_latest_installed_version_picks_highest_semver(tmp_path: Path) -> None:
    """Among multiple cached versions, return the highest by semver tuple."""
    from harness_maker.relevance import latest_installed_version

    with patch(
        "harness_maker.relevance._scan_plugin_cache_versions",
        return_value=["0.3.2", "0.6.1", "0.5.7", "0.10.0", "0.6.0"],
    ):
        # 0.10.0 > 0.6.1 by semver (not lexical — lexical would say "0.5.7" wins)
        assert latest_installed_version() == "0.10.0"


def test_latest_installed_version_skips_unparseable(tmp_path: Path) -> None:
    """Garbage entries in the cache directory are ignored, not parsed."""
    with patch(
        "harness_maker.relevance._scan_plugin_cache_versions",
        return_value=["random-text", "0.6.1", "not.a.version", ".tmp"],
    ):
        assert latest_installed_version() == "0.6.1"


def test_latest_installed_version_all_unparseable_falls_back(tmp_path: Path) -> None:
    """When EVERY cache entry fails semver parsing, fall back to __version__.

    REVIEW M6 (2026-05-08): coverage gap — prior tests always included at least
    one valid entry, leaving the `if not valid: return __version__` branch at
    relevance.py untested. This test exercises that branch directly.
    """
    with (
        patch(
            "harness_maker.relevance._scan_plugin_cache_versions",
            return_value=["random-text", "not.a.version", ".tmp", "garbage"],
        ),
        patch("harness_maker.__version__", "0.6.2"),
    ):
        assert latest_installed_version() == "0.6.2"


def test_session_start_hook_and_refresh_command_agree(tmp_path: Path) -> None:
    """Q-D resolved: both code paths now call detect_version_drift which uses
    latest_installed_version → identical verdict.

    The fix is structural (single helper) so this test asserts the code shape:
    both paths must funnel through detect_version_drift, and detect_version_drift
    must NOT directly import __version__ for comparison.
    """
    import inspect

    from harness_maker.hooks import sessionstart_drift
    from harness_maker.relevance import detect_version_drift

    # Both should use the same drift fn
    hook_src = inspect.getsource(sessionstart_drift)
    assert "detect_version_drift" in hook_src

    # detect_version_drift body must consult latest_installed_version, not __version__
    drift_src = inspect.getsource(detect_version_drift)
    assert "latest_installed_version()" in drift_src, (
        "detect_version_drift must call latest_installed_version() so the "
        "pinned /hm:refresh path and the system SessionStart path agree."
    )
    # And NOT directly import __version__ for the comparison side
    assert "from harness_maker import __version__" not in drift_src, (
        "detect_version_drift should not bypass latest_installed_version() — "
        "doing so reintroduces the divergence between /hm:refresh (pinned) and "
        "SessionStart (system) reported drift."
    )
