"""Tests for harness_maker.relevance.detect_stale_assets."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from harness_maker.relevance import (
    DEFAULT_STALE_DAYS,
    StaleAsset,
    detect_stale_assets,
    parse_last_reviewed_at,
)

# ──────────────────────────────────────────────────────────────────────────────
# parse_last_reviewed_at
# ──────────────────────────────────────────────────────────────────────────────


def test_parse_html_comment_form() -> None:
    body = "<!-- harness-maker partial: rubric (last_reviewed_at: 2026-01-15) -->\n"
    assert parse_last_reviewed_at(body) == date(2026, 1, 15)


def test_parse_yaml_frontmatter_form() -> None:
    body = '---\nname: python\nlast_reviewed_at: "2025-08-01"\n---\n'
    assert parse_last_reviewed_at(body) == date(2025, 8, 1)


def test_parse_returns_none_when_absent() -> None:
    assert parse_last_reviewed_at("# just a heading\n") is None


def test_parse_returns_none_for_invalid_date() -> None:
    body = "<!-- last_reviewed_at: 2026-13-99 -->\n"
    assert parse_last_reviewed_at(body) is None


# ──────────────────────────────────────────────────────────────────────────────
# detect_stale_assets — uses isolated template_dir + project_dir
# ──────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def isolated_template_dir(tmp_path: Path) -> Path:
    """Builds a minimal templates/ skeleton so production templates aren't read."""
    tdir = tmp_path / "templates"
    (tdir / "agents" / "_partials").mkdir(parents=True)
    (tdir / "agents" / "_standards").mkdir(parents=True)
    return tdir


def _write(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body)


def _domain_pack(d: date | None) -> str:
    if d is None:
        return "<!-- harness-maker domain pack: x -->\n## x standards\n"
    return f"<!-- harness-maker domain pack: x (last_reviewed_at: {d.isoformat()}) -->\n"


def test_no_stale_when_recent(tmp_path: Path, isolated_template_dir: Path) -> None:
    _write(
        tmp_path / ".claude" / "agents" / "_standards" / "tauri.md",
        _domain_pack(date(2026, 4, 1)),
    )
    stale = detect_stale_assets(
        tmp_path,
        now=date(2026, 5, 1),
        threshold_days=90,
        template_dir=isolated_template_dir,
    )
    assert stale == []


def test_stale_when_threshold_exceeded(
    tmp_path: Path,
    isolated_template_dir: Path,
) -> None:
    _write(
        tmp_path / ".claude" / "agents" / "_standards" / "tauri.md",
        _domain_pack(date(2025, 1, 1)),
    )
    stale = detect_stale_assets(
        tmp_path,
        now=date(2026, 5, 1),
        threshold_days=90,
        template_dir=isolated_template_dir,
    )
    assert len(stale) == 1
    asset = stale[0]
    assert asset.asset_kind == "domain-pack"
    assert asset.last_reviewed_at == date(2025, 1, 1)
    assert asset.days_since_review > 90
    assert asset.path.name == "tauri.md"


def test_missing_date_counts_as_stale(
    tmp_path: Path,
    isolated_template_dir: Path,
) -> None:
    _write(
        tmp_path / ".claude" / "agents" / "_standards" / "rust.md",
        _domain_pack(None),
    )
    stale = detect_stale_assets(
        tmp_path,
        now=date(2026, 5, 1),
        template_dir=isolated_template_dir,
    )
    assert len(stale) == 1
    assert stale[0].last_reviewed_at is None
    assert stale[0].days_since_review > stale[0].threshold_days


def test_skips_underscore_template(
    tmp_path: Path,
    isolated_template_dir: Path,
) -> None:
    """The skeleton _template.md.j2 is a TEMPLATE, not real content."""
    _write(
        isolated_template_dir / "agents" / "_standards" / "_template.md.j2",
        "<!-- last_reviewed_at: 2024-01-01 -->\n",
    )
    stale = detect_stale_assets(
        tmp_path,
        now=date(2026, 5, 1),
        template_dir=isolated_template_dir,
    )
    assert stale == []


def test_partials_scanned_from_template_dir(
    tmp_path: Path,
    isolated_template_dir: Path,
) -> None:
    _write(
        isolated_template_dir / "agents" / "_partials" / "rubric.md.j2",
        "<!-- last_reviewed_at: 2024-01-01 -->\n",
    )
    stale = detect_stale_assets(
        tmp_path,
        now=date(2026, 5, 1),
        template_dir=isolated_template_dir,
    )
    assert len(stale) == 1
    assert stale[0].asset_kind == "partial"
    assert stale[0].path.name == "rubric.md.j2"


def test_default_template_dir_resolves_to_real_templates(tmp_path: Path) -> None:
    """When template_dir is None, the real harness-maker templates/ is read."""
    # Use the real shipped partials: today they all have 2026-05-03.
    stale = detect_stale_assets(
        tmp_path,
        now=date(2026, 5, 4),  # 1 day after — well below threshold
        threshold_days=DEFAULT_STALE_DAYS,
    )
    # No stale assets expected because all shipped templates were just curated.
    assert all(s.days_since_review <= DEFAULT_STALE_DAYS for s in stale), stale


def test_returns_typed_stale_asset(
    tmp_path: Path,
    isolated_template_dir: Path,
) -> None:
    _write(
        tmp_path / ".claude" / "agents" / "_standards" / "x.md",
        _domain_pack(date(2024, 1, 1)),
    )
    stale = detect_stale_assets(
        tmp_path,
        now=date(2026, 5, 1),
        template_dir=isolated_template_dir,
    )
    assert isinstance(stale[0], StaleAsset)
    assert stale[0].threshold_days == DEFAULT_STALE_DAYS
