"""Tests for _compute_install_ref() — ADR-002 install reference auto-detection."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest


def test_returns_package_name_for_wheel_install(monkeypatch: pytest.MonkeyPatch) -> None:
    """Non-editable wheel install (no direct_url.json) → return 'harness-maker'."""
    monkeypatch.undo()
    dist = SimpleNamespace(read_text=lambda name: None)
    with patch("importlib.metadata.distribution", return_value=dist):
        from harness_maker.synthesize import _compute_install_ref

        assert _compute_install_ref() == "harness-maker"


def test_returns_url_path_for_editable_install(monkeypatch: pytest.MonkeyPatch) -> None:
    """Editable install with file:// direct_url → return the URL path verbatim.

    Before 0.15.1 this returned ``_HARNESS_MAKER_PKG_ROOT`` (the renderer's
    ``__file__``-derived guess), which is wrong when the renderer runs from
    a uv archive cache. The URL path is the original source uv was given
    and is the only value that can be re-used in a downstream
    ``uv run --with <ref>`` call.
    """
    monkeypatch.undo()
    direct_url = json.dumps({"dir_info": {"editable": True}, "url": "file:///tmp/hm"})
    dist = SimpleNamespace(read_text=lambda name: direct_url if name == "direct_url.json" else None)
    with patch("importlib.metadata.distribution", return_value=dist):
        from harness_maker.synthesize import _compute_install_ref

        assert _compute_install_ref() == "/tmp/hm"


def test_returns_local_path_when_not_installed(monkeypatch: pytest.MonkeyPatch) -> None:
    """Package not installed at all → fall back to local abs path."""
    # conftest autouse fixture pins _compute_install_ref, undo it for this test.
    monkeypatch.undo()
    with patch(
        "importlib.metadata.distribution",
        side_effect=Exception("not found"),
    ):
        from harness_maker.synthesize import _HARNESS_MAKER_PKG_ROOT, _compute_install_ref

        assert _compute_install_ref() == _HARNESS_MAKER_PKG_ROOT


def test_returns_package_name_for_non_file_url(monkeypatch: pytest.MonkeyPatch) -> None:
    """Non-editable install with non-file:// direct_url (e.g. git+https) → 'harness-maker'."""
    monkeypatch.undo()
    direct_url = json.dumps({"url": "https://github.com/Ecro/harness-maker.git", "vcs_info": {}})
    dist = SimpleNamespace(read_text=lambda name: direct_url if name == "direct_url.json" else None)
    with patch("importlib.metadata.distribution", return_value=dist):
        from harness_maker.synthesize import _compute_install_ref

        assert _compute_install_ref() == "harness-maker"


def test_returns_local_path_when_direct_url_json_corrupted(monkeypatch: pytest.MonkeyPatch) -> None:
    """Dist found but direct_url.json has invalid JSON → fall back to local path.

    0.11.3: previously returned 'harness-maker' on parse failure. That assumed
    the package is on PyPI, which is unsafe for harness-maker (not published).
    Local path works for both PyPI installs (uv accepts the directory) and
    local installs; PyPI name only works if published. Falling back to local
    on ambiguity removes the SessionStart-drift footgun.
    """
    monkeypatch.undo()

    def _read(name: str) -> str | None:
        return "{bad json" if name == "direct_url.json" else None

    dist = SimpleNamespace(read_text=_read)
    with patch("importlib.metadata.distribution", return_value=dist):
        from harness_maker.synthesize import _HARNESS_MAKER_PKG_ROOT, _compute_install_ref

        assert _compute_install_ref() == _HARNESS_MAKER_PKG_ROOT


def test_returns_url_path_for_non_editable_file_install(monkeypatch: pytest.MonkeyPatch) -> None:
    """Non-editable file:// install (Claude Code plugin cache) → return URL path.

    Regression guard for the 0.15.1 fix: when ``uv run --with /path/to/plugin``
    archives the package into ``~/.cache/uv/archive-v0/<hash>/lib/python3.12/
    site-packages/harness_maker/``, ``_HARNESS_MAKER_PKG_ROOT`` (computed from
    ``__file__.parent.parent.parent``) resolves to the archive's
    ``lib/python3.12`` directory — NOT a Python project. The pre-0.15.1 code
    returned that constant anyway, and every rendered hook then fired
    ``uv run --with <archive>/lib/python3.12 ...`` and failed at uv resolution.

    The fix: read the URL from ``direct_url.json`` directly. uv writes the
    original source path there as a ``file://`` URL, which is exactly the arg
    the downstream rendered ``uv run --with ...`` line needs.
    """
    monkeypatch.undo()
    direct_url = json.dumps(
        {
            "dir_info": {"editable": False},
            "url": "file:///home/user/.claude/plugins/cache/harness-maker-local/harness-maker/0.15.1",
        }
    )
    dist = SimpleNamespace(read_text=lambda name: direct_url if name == "direct_url.json" else None)
    with patch("importlib.metadata.distribution", return_value=dist):
        from harness_maker.synthesize import _compute_install_ref

        assert (
            _compute_install_ref()
            == "/home/user/.claude/plugins/cache/harness-maker-local/harness-maker/0.15.1"
        )


def test_url_path_wins_over_uv_archive_pkg_root(monkeypatch: pytest.MonkeyPatch) -> None:
    """Even when _HARNESS_MAKER_PKG_ROOT points at a uv archive, the URL wins.

    Exact reproduction of the 0.15.0 bug: in production, when the renderer is
    imported from ``~/.cache/uv/archive-v0/<hash>/lib/python3.12/site-packages/
    harness_maker/synthesize.py``, ``_HARNESS_MAKER_PKG_ROOT`` resolves to
    ``<hash>/lib/python3.12`` — not a Python project. The renderer must
    *ignore* this useless value and use the URL from direct_url.json instead.
    """
    monkeypatch.undo()
    # Simulate the broken archive PKG_ROOT.
    from harness_maker import synthesize

    monkeypatch.setattr(
        synthesize,
        "_HARNESS_MAKER_PKG_ROOT",
        "/home/dev/.cache/uv/archive-v0/8LyafCD5C6AzA5QzTykGR/lib/python3.12",
    )
    direct_url = json.dumps(
        {
            "dir_info": {"editable": False},
            "url": "file:///home/dev/.claude/plugins/cache/harness-maker-local/harness-maker/0.15.1",
        }
    )
    dist = SimpleNamespace(read_text=lambda name: direct_url if name == "direct_url.json" else None)
    with patch("importlib.metadata.distribution", return_value=dist):
        result = synthesize._compute_install_ref()

    assert (
        result == "/home/dev/.claude/plugins/cache/harness-maker-local/harness-maker/0.15.1"
    ), f"renderer fell back to broken archive PKG_ROOT instead of URL path: {result}"


def test_console_scripts_entry_point_callable() -> None:
    """Verify the console_scripts entry point resolves to a callable."""
    from harness_maker.cli import main

    assert callable(main)
