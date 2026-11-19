"""SPEC-stale-install-recovery AC-009/010/011: release procedure and update docs."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _section(text: str, start: str, end: str) -> str:
    return text[text.index(start) : text.index(end)]


def test_ac_009_claude_md_release_section() -> None:
    s = _section((ROOT / "CLAUDE.md").read_text("utf-8"), "## 릴리스 절차", "## 보안")
    assert "autotag" in s
    assert "git tag -a" in s
    assert "gh release create" in s


def _updating() -> str:
    readme = (ROOT / "README.md").read_text("utf-8")
    body = readme[readme.index("## Updating") :]
    return body.split("\n## ", 1)[0]


def test_ac_010_readme_updating_and_no_stale_advice() -> None:
    readme = (ROOT / "README.md").read_text("utf-8")
    assert "## Updating" in readme
    for banned in (
        "rm .claude/harness.yaml",
        "(when published)",
        "Listings are **pending**",
        "The engine must be published at the plugin",
    ):
        assert banned not in readme, banned
    up = _updating()
    assert "/hm:make --update" in up
    assert "self-heal" in up.lower()


def test_ac_011_same_session_record_cited() -> None:
    assert (ROOT / "work-docs/RESEARCH-stale-install-recovery.md").is_file()
    up = _updating()
    assert "RESEARCH-stale-install-recovery" in up
    assert "same session" in up.lower()
