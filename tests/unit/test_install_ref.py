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


def test_returns_package_name_when_direct_url_json_corrupted() -> None:
    """Dist found but direct_url.json has invalid JSON → return 'harness-maker' (not local path)."""

    def _read(name: str) -> str | None:
        return "{bad json" if name == "direct_url.json" else None

    dist = SimpleNamespace(read_text=_read)
    with patch("importlib.metadata.distribution", return_value=dist):
        from harness_maker.synthesize import _compute_install_ref

        assert _compute_install_ref() == "harness-maker"


def test_console_scripts_entry_point_callable() -> None:
    """Verify the console_scripts entry point resolves to a callable."""
    from harness_maker.cli import main

    assert callable(main)
