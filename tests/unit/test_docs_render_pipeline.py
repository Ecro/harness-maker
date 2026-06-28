"""Phase 4: render-pipeline + git-decision docs present in README + HOW-IT-WORKS (both locales)."""

from __future__ import annotations

import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (_ROOT / rel).read_text(encoding="utf-8")


def _anchor(heading: str) -> str:
    """GitHub-style anchor: lowercase, drop punctuation, spaces->hyphens."""
    a = heading.strip().lower()
    a = re.sub(r"[^\w\s가-힣-]", "", a)  # keep word chars, spaces, hyphens, hangul
    return re.sub(r"\s+", "-", a)


def test_readme_en_has_render_flow_and_resolving_link() -> None:
    body = _read("README.md")
    assert "no git worktree" in body.lower()
    assert "commit" in body
    assert "gitignore" in body
    assert "docs/HOW-IT-WORKS.md#render-pipeline" in body
    # the linked anchor must exist as a heading in the target doc
    how = _read("docs/HOW-IT-WORKS.md")
    headings = {_anchor(m) for m in re.findall(r"^#{1,4}\s+(.*)$", how, re.M)}
    assert "render-pipeline" in headings


def test_readme_ko_has_render_flow_and_resolving_link() -> None:
    body = _read("README.ko.md")
    assert "worktree" in body.lower()
    assert "commit" in body
    assert "gitignore" in body
    assert "docs/HOW-IT-WORKS.ko.md#렌더-파이프라인" in body
    how = _read("docs/HOW-IT-WORKS.ko.md")
    headings = {_anchor(m) for m in re.findall(r"^#{1,4}\s+(.*)$", how, re.M)}
    assert "렌더-파이프라인" in headings


def test_how_it_works_both_locales_have_git_disposition() -> None:
    for rel in ("docs/HOW-IT-WORKS.md", "docs/HOW-IT-WORKS.ko.md"):
        body = _read(rel)
        assert "git-status" in body, rel
        assert "git-ignore-roots" in body, rel
        assert "--dry-run" in body, rel
        assert "re-nag" in body or "다시 묻지 않" in body, rel
