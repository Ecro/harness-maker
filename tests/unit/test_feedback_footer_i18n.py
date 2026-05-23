"""Phase 4 — footer i18n.

PLAN-auto-feedback-2026-05 Phase 4 exit criterion (en + ko strings).
"""

from __future__ import annotations

from pathlib import Path

from harness_maker.feedback.footer import render


def test_footer_silent_when_no_draft() -> None:
    """Silent-when-empty contract — empty string when nothing to report."""
    assert render(None) == ""
    assert render(None, locale="en") == ""
    assert render(None, locale="ko") == ""


def test_footer_en_contains_required_substrings() -> None:
    p = Path(".claude/observability/feedback/2026-05-23-x-aabb.md")
    line = render(p, locale="en")
    assert "📝" in line
    assert "feedback draft saved" in line
    assert "gh issue create --web --body-file" in line
    assert str(p) in line


def test_footer_ko_contains_required_substrings() -> None:
    p = Path(".claude/observability/feedback/2026-05-23-x-aabb.md")
    line = render(p, locale="ko")
    assert "📝" in line
    assert "feedback draft 저장됨" in line
    assert "gh issue create --web --body-file" in line
    assert str(p) in line


def test_footer_unknown_locale_falls_back_to_en() -> None:
    """Mirror project-wide locale policy — unknown → en fallback (no exception)."""
    p = Path("x.md")
    line = render(p, locale="ja")
    assert line == render(p, locale="en")
