"""Tests for _compute_install_ref() — ADR-002 install reference auto-detection."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import patch


def test_returns_package_name_for_wheel_install() -> None:
    """Non-editable wheel install → return 'harness-maker'."""
    dist = SimpleNamespace(read_text=lambda name: None)
    with patch("importlib.metadata.distribution", return_value=dist):
        from harness_maker.synthesize import _compute_install_ref

        assert _compute_install_ref() == "harness-maker"


def test_returns_local_path_for_editable_install() -> None:
    """Editable install with direct_url.json → return local abs path."""
    direct_url = json.dumps({"dir_info": {"editable": True}, "url": "file:///tmp/hm"})
    dist = SimpleNamespace(read_text=lambda name: direct_url if name == "direct_url.json" else None)
    with patch("importlib.metadata.distribution", return_value=dist):
        from harness_maker.synthesize import _HARNESS_MAKER_PKG_ROOT, _compute_install_ref

        assert _compute_install_ref() == _HARNESS_MAKER_PKG_ROOT


def test_returns_local_path_when_not_installed() -> None:
    """Package not installed at all → fall back to local abs path."""
    with patch(
        "importlib.metadata.distribution",
        side_effect=Exception("not found"),
    ):
        from harness_maker.synthesize import _HARNESS_MAKER_PKG_ROOT, _compute_install_ref

        assert _compute_install_ref() == _HARNESS_MAKER_PKG_ROOT


def test_returns_package_name_for_non_editable_with_direct_url() -> None:
    """Non-editable install with direct_url.json (e.g. git+https) → return 'harness-maker'."""
    direct_url = json.dumps({"url": "https://github.com/Ecro/harness-maker.git", "vcs_info": {}})
    dist = SimpleNamespace(read_text=lambda name: direct_url if name == "direct_url.json" else None)
    with patch("importlib.metadata.distribution", return_value=dist):
        from harness_maker.synthesize import _compute_install_ref

        assert _compute_install_ref() == "harness-maker"


def test_returns_local_path_when_direct_url_json_corrupted() -> None:
    """Dist found but direct_url.json has invalid JSON → return local path (safer).

    0.11.3: previously returned 'harness-maker' on parse failure. That assumed
    the package is on PyPI, which is unsafe for harness-maker (not published).
    Local path works for both PyPI installs (uv accepts the directory) and
    local installs; PyPI name only works if published. Falling back to local
    on ambiguity removes the SessionStart-drift footgun.
    """

    def _read(name: str) -> str | None:
        return "{bad json" if name == "direct_url.json" else None

    dist = SimpleNamespace(read_text=_read)
    with patch("importlib.metadata.distribution", return_value=dist):
        from harness_maker.synthesize import _HARNESS_MAKER_PKG_ROOT, _compute_install_ref

        assert _compute_install_ref() == _HARNESS_MAKER_PKG_ROOT


def test_returns_local_path_for_non_editable_file_install() -> None:
    """Non-editable file:// install (Claude Code plugin cache) → return local path.

    Regression guard for the 0.11.3 SessionStart-drift fix: Claude Code's plugin
    cache records direct_url.json with editable=false but a file:// URL. The
    previous logic (editable-only check) returned 'harness-maker', which uv
    cannot resolve since harness-maker is not on PyPI. Result: every drift hook
    silently failed with 'No solution found'. Any file:// URL must resolve to
    the local path.
    """
    direct_url = json.dumps(
        {
            "dir_info": {"editable": False},
            "url": "file:///home/user/.claude/plugins/cache/harness-maker-local/harness-maker/0.11.2",
        }
    )
    dist = SimpleNamespace(read_text=lambda name: direct_url if name == "direct_url.json" else None)
    with patch("importlib.metadata.distribution", return_value=dist):
        from harness_maker.synthesize import _HARNESS_MAKER_PKG_ROOT, _compute_install_ref

        assert _compute_install_ref() == _HARNESS_MAKER_PKG_ROOT


def test_console_scripts_entry_point_callable() -> None:
    """Verify the console_scripts entry point resolves to a callable."""
    from harness_maker.cli import main

    assert callable(main)
