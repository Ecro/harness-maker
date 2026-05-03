"""Tests for harness_maker.relevance stale-asset detection + accept handler."""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from harness_maker.relevance import (
    DEFAULT_STALE_DAYS,
    StaleAsset,
    StaleAssetUpdateError,
    build_proposal_lines,
    detect_stale_assets,
    parse_last_reviewed_at,
    resolve_template_dir,
    update_last_reviewed_at,
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


def test_parse_jinja_comment_form() -> None:
    """Reviewer partials use Jinja {# #} so HTML doesn't leak; regex still matches."""
    body = "{# harness-maker partial: rubric (last_reviewed_at: 2026-05-03) #}\n"
    assert parse_last_reviewed_at(body) == date(2026, 5, 3)


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


def test_user_pack_tagged_user_source(
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
    assert asset.source == "user"
    assert asset.last_reviewed_at == date(2025, 1, 1)
    assert asset.days_since_review > 90
    assert asset.path.name == "tauri.md"


def test_shipped_pack_tagged_shipped_source(
    tmp_path: Path,
    isolated_template_dir: Path,
) -> None:
    _write(
        isolated_template_dir / "agents" / "_standards" / "tauri.md.j2",
        _domain_pack(date(2025, 1, 1)),
    )
    stale = detect_stale_assets(
        tmp_path,
        now=date(2026, 5, 1),
        threshold_days=90,
        template_dir=isolated_template_dir,
    )
    assert len(stale) == 1
    assert stale[0].source == "shipped"
    assert stale[0].asset_kind == "domain-pack"


def test_partial_tagged_partial_kind_shipped_source(
    tmp_path: Path,
    isolated_template_dir: Path,
) -> None:
    _write(
        isolated_template_dir / "agents" / "_partials" / "rubric.md.j2",
        "{# last_reviewed_at: 2024-01-01 #}\n",
    )
    stale = detect_stale_assets(
        tmp_path,
        now=date(2026, 5, 1),
        template_dir=isolated_template_dir,
    )
    assert len(stale) == 1
    assert stale[0].asset_kind == "partial"
    assert stale[0].source == "shipped"
    assert stale[0].path.name == "rubric.md.j2"


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


# ──────────────────────────────────────────────────────────────────────────────
# resolve_template_dir + real-templates integration
# ──────────────────────────────────────────────────────────────────────────────


def test_resolve_template_dir_returns_existing_dir() -> None:
    tdir = resolve_template_dir()
    assert tdir.is_dir()
    assert (tdir / "agents" / "_partials").is_dir()
    assert (tdir / "agents" / "_standards").is_dir()


def test_real_partials_have_parseable_dates(tmp_path: Path) -> None:
    """Every shipped partial must carry a last_reviewed_at the parser can read."""
    tdir = resolve_template_dir()
    partials = sorted((tdir / "agents" / "_partials").glob("*.md.j2"))
    assert partials, "expected at least one partial"
    for p in partials:
        assert parse_last_reviewed_at(p.read_text(encoding="utf-8")) is not None, p


def test_real_partials_flagged_when_now_advanced_past_threshold(tmp_path: Path) -> None:
    """Set now far in the future and verify the shipped partials surface as stale.

    Closes the prior tautology where the test froze ``now`` 1 day after the
    partial's last_reviewed_at; that asserted only "no stale" which passed
    trivially. Here we assert the *positive* case — pushing now beyond the
    threshold actually flags the shipped partials.
    """
    far_future = date(2099, 1, 1)
    stale = detect_stale_assets(tmp_path, now=far_future, threshold_days=DEFAULT_STALE_DAYS)
    partial_paths = [s for s in stale if s.asset_kind == "partial"]
    assert len(partial_paths) >= 4, (
        f"expected ≥4 shipped partials flagged, got {len(partial_paths)}"
    )
    assert all(s.source == "shipped" for s in partial_paths)


# ──────────────────────────────────────────────────────────────────────────────
# update_last_reviewed_at — accept handler
# ──────────────────────────────────────────────────────────────────────────────


def test_update_last_reviewed_at_rewrites_html_comment(tmp_path: Path) -> None:
    f = tmp_path / "tauri.md"
    f.write_text(
        "<!-- harness-maker domain pack: tauri (last_reviewed_at: 2024-01-01) -->\n"
        "body unchanged\n",
    )
    new = update_last_reviewed_at(f, date(2026, 5, 3))
    assert new == date(2026, 5, 3)
    text = f.read_text()
    assert "last_reviewed_at: 2026-05-03" in text
    assert "2024-01-01" not in text
    assert "body unchanged" in text


def test_update_last_reviewed_at_rewrites_jinja_comment(tmp_path: Path) -> None:
    f = tmp_path / "rubric.md.j2"
    f.write_text("{# last_reviewed_at: 2024-01-01 #}\n## body\n")
    update_last_reviewed_at(f, date(2026, 5, 3))
    text = f.read_text()
    assert "last_reviewed_at: 2026-05-03" in text
    assert "## body" in text


def test_update_last_reviewed_at_default_to_today(tmp_path: Path) -> None:
    f = tmp_path / "x.md"
    f.write_text("<!-- last_reviewed_at: 2024-01-01 -->\n")
    new = update_last_reviewed_at(f)
    expected_today = datetime.now(tz=UTC).date()
    assert new == expected_today


def test_update_last_reviewed_at_raises_when_annotation_missing(tmp_path: Path) -> None:
    f = tmp_path / "no-annotation.md"
    f.write_text("# just a heading\n")
    with pytest.raises(StaleAssetUpdateError, match="no last_reviewed_at"):
        update_last_reviewed_at(f, date(2026, 5, 3))


def test_update_last_reviewed_at_only_replaces_first_occurrence(tmp_path: Path) -> None:
    """Files with multiple annotations (rare) update only the first; rest stay user-managed."""
    f = tmp_path / "x.md"
    f.write_text(
        "<!-- last_reviewed_at: 2024-01-01 -->\n"
        "intermediate text\n"
        "<!-- last_reviewed_at: 2024-06-01 -->\n",
    )
    update_last_reviewed_at(f, date(2026, 5, 3))
    text = f.read_text()
    assert text.count("last_reviewed_at: 2026-05-03") == 1
    assert "last_reviewed_at: 2024-06-01" in text


# ──────────────────────────────────────────────────────────────────────────────
# build_proposal_lines
# ──────────────────────────────────────────────────────────────────────────────


def test_build_proposal_lines_renders_relative_paths(tmp_path: Path) -> None:
    asset_path = tmp_path / ".claude" / "agents" / "_standards" / "tauri.md"
    asset_path.parent.mkdir(parents=True)
    asset_path.write_text("<!-- last_reviewed_at: 2024-01-01 -->\n")
    asset = StaleAsset(
        path=asset_path,
        asset_kind="domain-pack",
        source="user",
        last_reviewed_at=date(2024, 1, 1),
        days_since_review=486,
        threshold_days=90,
    )
    lines = build_proposal_lines([asset], tmp_path)
    assert len(lines) == 1
    assert ".claude/agents/_standards/tauri.md" in lines[0]
    assert "user/domain-pack" in lines[0]
    assert "486 days" in lines[0]
    assert "2024-01-01" in lines[0]


def test_build_proposal_lines_handles_missing_date(tmp_path: Path) -> None:
    asset = StaleAsset(
        path=tmp_path / "x.md",
        asset_kind="partial",
        source="shipped",
        last_reviewed_at=None,
        days_since_review=91,
        threshold_days=90,
    )
    lines = build_proposal_lines([asset], tmp_path)
    assert "(never)" in lines[0]
