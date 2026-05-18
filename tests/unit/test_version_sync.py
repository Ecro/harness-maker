"""Version sync — 5 files must agree on harness-maker version (Phase 2.5, expanded 0.16.0).

CLAUDE.md "버전업 정책": five files must be bumped together; if any one is
out of date Claude Code's ``/plugin update`` 또는 Cursor / Codex Marketplace
reports "already at latest" with a stale version. The five sources of truth:

- ``.claude-plugin/plugin.json``  — Claude Code marketplace
- ``.cursor-plugin/plugin.json``  — Cursor Marketplace
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


def _cursor_plugin_version() -> str:
    raw: str = json.loads(_read_text(".cursor-plugin/plugin.json"))["version"]
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


def test_cursor_plugin_and_pyproject_versions_match() -> None:
    """Phase 2.5: dual plugin manifest must follow the 4-file sync policy."""
    assert _cursor_plugin_version() == _pyproject_version()


def test_runtime_init_and_pyproject_versions_match() -> None:
    assert _runtime_version() == _pyproject_version()


def test_codex_plugin_and_pyproject_versions_match() -> None:
    """0.16.0: codex-plugin manifest joins the 5-file sync policy."""
    assert _codex_plugin_version() == _pyproject_version()


def test_all_five_version_sources_agree() -> None:
    """5-way agreement gate (CLAUDE.md "버전업 정책", expanded 0.16.0)."""
    versions = {
        ".claude-plugin/plugin.json": _claude_plugin_version(),
        ".cursor-plugin/plugin.json": _cursor_plugin_version(),
        ".codex-plugin/plugin.json": _codex_plugin_version(),
        "pyproject.toml": _pyproject_version(),
        "src/harness_maker/__init__.py": _runtime_version(),
    }
    unique = set(versions.values())
    assert len(unique) == 1, f"version drift detected: {versions}"


def test_cursor_plugin_manifest_has_cursor_keyword() -> None:
    """Phase 2.5: cursor-plugin manifest 의 keywords 에 ``cursor`` 포함 — Cursor
    Marketplace 에서 검색 가능하도록.
    """
    manifest: dict[str, object] = json.loads(_read_text(".cursor-plugin/plugin.json"))
    keywords = manifest.get("keywords", [])
    assert isinstance(keywords, list)
    assert "cursor" in keywords


def test_cursor_plugin_explicit_commands_path() -> None:
    """Phase 2.5 Round 2: Cursor docs 권고 (explicit > implicit) 따라
    ``commands`` 컴포넌트 path 명시. auto-discovery 결과는 동일하지만 spec
    변경 시 break 회피 + manifest 가 self-documenting.

    https://cursor.com/docs/plugins/building "If a manifest field is
    specified...it replaces folder discovery for that component."
    """
    manifest: dict[str, object] = json.loads(_read_text(".cursor-plugin/plugin.json"))
    assert manifest.get("commands") == "./commands"


def test_cursor_plugin_commands_path_resolves_to_existing_directory() -> None:
    """``commands`` path 가 실제 디렉토리를 가리키는지 — 향후 commands path
    refactor 시 plugin 깨지지 않도록.
    """
    manifest: dict[str, object] = json.loads(_read_text(".cursor-plugin/plugin.json"))
    commands_rel = manifest.get("commands")
    assert isinstance(commands_rel, str)
    commands_dir = REPO_ROOT / commands_rel.lstrip("./")
    assert commands_dir.is_dir(), f"manifest commands path missing: {commands_rel}"
    assert any(commands_dir.glob("*.md")), f"no .md files under {commands_rel}"


def test_two_manifests_share_required_metadata() -> None:
    """Two manifests share name / author / license / repository / homepage.
    Description and keywords may differ (cursor-plugin 의 description 은 양쪽
    IDE 명시 + keywords 에 cursor 추가).
    """
    claude: dict[str, object] = json.loads(_read_text(".claude-plugin/plugin.json"))
    cursor: dict[str, object] = json.loads(_read_text(".cursor-plugin/plugin.json"))
    for key in ("name", "author", "license", "repository", "homepage"):
        assert claude.get(key) == cursor.get(key), f"manifest drift on key={key!r}"
