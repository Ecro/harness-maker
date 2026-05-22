"""Phase 6 tests — communication-protocol Layer 1 sub-check.

Two acceptance fixtures (PLAN-antisycophancy-2026-05 ADR-006):
- Fixture A: existing template with frontmatter declared but rendered output
  has the variant block removed (marker absent) → audit surfaces 1 item.
- Fixture B: synthetic dispatcher template lacking `communication_variant`
  frontmatter → audit surfaces 1 item (silent-miss proof).

Plus repo full-scan must return 0 items (clean baseline).
"""

from __future__ import annotations

from pathlib import Path

from harness_maker.communication_audit import (
    PINNED_SKILLS,
    audit_communication,
    discover_dispatchers,
    discover_pinned_skills,
    require_variant_frontmatter,
    scan_output_marker,
)

_REPO_TEMPLATES = Path(__file__).resolve().parents[2] / "src/harness_maker/templates"


def test_discover_dispatchers_returns_14_agents() -> None:
    found = discover_dispatchers(_REPO_TEMPLATES)
    # 14 dispatcher templates (excludes _body / _partials)
    assert len(found) == 14
    names = {f.stem.removesuffix(".md") for f in found}
    assert "code-reviewer" in names
    assert "autoloop-coder" in names
    assert "trajectory-monitor" in names
    # _body files excluded
    assert not any(f.name.endswith("_body.md.j2") for f in found)


def test_discover_pinned_skills_returns_four_llm_judgment() -> None:
    found = discover_pinned_skills(_REPO_TEMPLATES)
    # 4 pinned skills (relevance-filter removed in 0.22.3 per ADR-0007)
    assert len(found) == 4
    parents = {f.parent.name for f in found}
    assert parents == set(PINNED_SKILLS)


def test_repo_full_scan_returns_zero_items_when_clean() -> None:
    """Baseline: with all 14 dispatchers + 4 skills correctly declared, audit is empty."""
    items = audit_communication(_REPO_TEMPLATES)
    assert items == [], f"Expected clean baseline, got items: {items}"


def test_fixture_b_silent_miss_dispatcher_surfaces_item(tmp_path: Path) -> None:
    """Synthetic new dispatcher template WITHOUT `communication_variant` → fail.

    ADR-006 silent-miss canonical failure mode.
    """
    tdir = tmp_path / "templates"
    (tdir / "agents").mkdir(parents=True)
    # Synthetic dispatcher missing the variant frontmatter.
    (tdir / "agents" / "new-reviewer.md.j2").write_text(
        "---\nname: new-reviewer\ndescription: synthetic\n---\n",
        encoding="utf-8",
    )
    items = audit_communication(tdir)
    assert len(items) == 1
    assert items[0].dimension == "communication_protocol"
    assert "missing `communication_variant` frontmatter" in items[0].summary


def test_fixture_a_block_removed_in_output_surfaces_item(tmp_path: Path) -> None:
    """Source declared variant, rendered output marker removed → drift detected."""
    tdir = tmp_path / "templates"
    odir = tmp_path / "rendered"
    (tdir / "agents").mkdir(parents=True)
    (odir / "agents").mkdir(parents=True)
    # Source: declares reframe variant
    (tdir / "agents" / "demo.md.j2").write_text(
        "---\nname: demo\ncommunication_variant: reframe\n---\n# demo\n",
        encoding="utf-8",
    )
    # Rendered output: marker deleted (block removed by hand)
    (odir / "agents" / "demo.md").write_text(
        "---\nname: demo\n---\n# demo\n\n## Communication Protocol\n\n- bullet\n",
        encoding="utf-8",
    )
    items = audit_communication(tdir, output_dir=odir)
    assert len(items) == 1
    assert "missing communication-protocol marker" in items[0].summary


def test_require_variant_frontmatter_rejects_invalid_value(tmp_path: Path) -> None:
    f = tmp_path / "broken.md.j2"
    f.write_text(
        "---\nname: broken\ncommunication_variant: hard\n---\n",
        encoding="utf-8",
    )
    item = require_variant_frontmatter(f)
    assert item is not None
    assert "invalid" in item.summary


def test_scan_output_marker_returns_variant_string(tmp_path: Path) -> None:
    f = tmp_path / "out.md"
    f.write_text(
        "header\n\n## body\n\n<!-- @hm:communication_variant: reframe -->\n",
        encoding="utf-8",
    )
    assert scan_output_marker(f) == "reframe"


def test_scan_output_marker_returns_none_when_absent(tmp_path: Path) -> None:
    f = tmp_path / "out.md"
    f.write_text("header — no marker here\n", encoding="utf-8")
    assert scan_output_marker(f) is None
