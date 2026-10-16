"""Version sync — 4 files must agree on harness-maker version (0.63.0 removed the Cursor manifest).

CLAUDE.md "버전업 정책": four files must be bumped together; if any one is
out of date Claude Code's ``/plugin update`` or the Codex Marketplace
reports "already at latest" with a stale version. The four sources of truth:

- ``.claude-plugin/plugin.json``  — Claude Code marketplace
- ``.codex-plugin/plugin.json``   — Codex CLI manifest
- ``pyproject.toml``              — Python package distribution
- ``src/harness_maker/__init__.py`` — runtime ``__version__``
"""

from __future__ import annotations

import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _read_text(rel: str) -> str:
    return (REPO_ROOT / rel).read_text(encoding="utf-8")


def _claude_plugin_version() -> str:
    raw: str = json.loads(_read_text(".claude-plugin/plugin.json"))["version"]
    return raw


def _codex_plugin_version() -> str:
    raw: str = json.loads(_read_text(".codex-plugin/plugin.json"))["version"]
    return raw


def _pyproject_version() -> str:
    text = _read_text("pyproject.toml")
    match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    assert match is not None, "pyproject.toml has no `version` key"
    return match.group(1)


def _runtime_version() -> str:
    text = _read_text("src/harness_maker/__init__.py")
    match = re.search(r'__version__\s*=\s*"([^"]+)"', text)
    assert match is not None, "__init__.py has no `__version__`"
    return match.group(1)


def test_claude_plugin_and_pyproject_versions_match() -> None:
    assert _claude_plugin_version() == _pyproject_version()


def test_runtime_init_and_pyproject_versions_match() -> None:
    assert _runtime_version() == _pyproject_version()


def test_codex_plugin_and_pyproject_versions_match() -> None:
    """0.16.0: codex-plugin manifest joined the version sync (four files since 0.63.0)."""
    assert _codex_plugin_version() == _pyproject_version()


def test_four_manifests_share_one_version() -> None:
    """SPEC-hm-overhaul-p1 AC-001: version sync spans four files and no fifth manifest exists."""
    manifests = sorted(
        p.relative_to(REPO_ROOT).as_posix() for p in REPO_ROOT.glob(".*-plugin/plugin.json")
    )
    assert manifests == [".claude-plugin/plugin.json", ".codex-plugin/plugin.json"], manifests
    versions = {
        ".claude-plugin/plugin.json": _claude_plugin_version(),
        ".codex-plugin/plugin.json": _codex_plugin_version(),
        "pyproject.toml": _pyproject_version(),
        "src/harness_maker/__init__.py": _runtime_version(),
    }
    unique = set(versions.values())
    assert len(unique) == 1, f"version drift detected: {versions}"


def test_claude_and_codex_manifests_share_required_metadata() -> None:
    """The two marketplace manifests describe one plugin: same identity, version and links.

    Replaces the claude-vs-cursor check that left with `.cursor-plugin/plugin.json` (0.63.0).
    Description and keywords may differ per marketplace.
    """
    claude: dict[str, object] = json.loads(_read_text(".claude-plugin/plugin.json"))
    codex: dict[str, object] = json.loads(_read_text(".codex-plugin/plugin.json"))
    for key in ("name", "version", "author", "license", "repository", "homepage"):
        assert claude.get(key) is not None, f".claude-plugin/plugin.json has no {key!r}"
        assert claude.get(key) == codex.get(key), f"manifest drift on key={key!r}"
