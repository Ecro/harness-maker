"""3-section health dashboard writer/reader (0.13.0).

PLAN health-consolidation Phase 1 / ADR-002 (amended by ADR-006). The
verify stage (Phase 3) reads the schema produced here; this test pins
the public contract so a future tweak can't silently break Check 3.
"""

from __future__ import annotations

import json
from pathlib import Path

from harness_maker.observability.dashboard import (
    parse_dashboard,
    render_dashboard_markdown,
    write_dashboard,
)

# ─── render_dashboard_markdown ──────────────────────────────────────────────


def _sample_inputs() -> tuple[dict, dict, dict]:
    structural = {
        "score": 72,
        "signals_failed": ["context_quality:has_stack", "agent_quality:has_charter"],
    }
    external_risks = {
        "pending": 2,
        "items": [
            {
                "source": "osv.dev",
                "id": "CVE-2026-0001",
                "severity": "high",
                "relevance": 0.82,
            },
            {
                "source": "anthropic_blog",
                "id": "post-2026-05-01",
                "severity": "info",
                "relevance": 0.81,
            },
        ],
    }
    personalization = {
        "composite": 67,
        "tier": "gold",
        "layers": {"l1_conversion": 60, "l2_stability": 75, "l3_cadence": 50},
        "action_items": [
            {
                "priority": "P1",
                "dimension": "override_stability",
                "summary": "preset overridden 5 times",
            }
        ],
    }
    return structural, external_risks, personalization


def test_render_has_three_sections() -> None:
    s, e, p = _sample_inputs()
    body = render_dashboard_markdown(s, e, p, generated_at="2026-05-16T00:00:00+00:00")
    assert "## Structural" in body
    assert "## External risks" in body
    assert "## Personalization" in body


def test_render_includes_frontmatter() -> None:
    s, e, p = _sample_inputs()
    body = render_dashboard_markdown(s, e, p, generated_at="2026-05-16T00:00:00+00:00")
    assert body.startswith("---\n")
    assert "generated_by: harness-maker" in body.split("\n---\n", 1)[0]
    assert "generated_at: 2026-05-16T00:00:00+00:00" in body


def test_render_structural_fields() -> None:
    s, e, p = _sample_inputs()
    body = render_dashboard_markdown(s, e, p, generated_at="2026-05-16T00:00:00+00:00")
    assert "score: 72 / 100" in body
    # signals_failed is JSON-encoded so a verify reader can parse it
    assert '"context_quality:has_stack"' in body


def test_render_external_risks_fields() -> None:
    s, e, p = _sample_inputs()
    body = render_dashboard_markdown(s, e, p, generated_at="2026-05-16T00:00:00+00:00")
    assert "pending: 2" in body
    assert '"CVE-2026-0001"' in body


def test_render_personalization_fields() -> None:
    s, e, p = _sample_inputs()
    body = render_dashboard_markdown(s, e, p, generated_at="2026-05-16T00:00:00+00:00")
    assert "composite: 67 / 100" in body
    assert "tier: gold" in body
    assert '"l1_conversion": 60' in body
    assert '"override_stability"' in body


def test_render_clamps_out_of_range_scores() -> None:
    s = {"score": 250, "signals_failed": []}
    e = {"pending": 0, "items": []}
    p = {"composite": -10, "tier": "bronze", "layers": {}, "action_items": []}
    body = render_dashboard_markdown(s, e, p, generated_at="2026-05-16T00:00:00+00:00")
    assert "score: 100 / 100" in body
    assert "composite: 0 / 100" in body


def test_render_handles_missing_optional_fields() -> None:
    """A degenerate section dict must still produce a valid markdown body."""
    body = render_dashboard_markdown({}, {}, {}, generated_at="2026-05-16T00:00:00+00:00")
    assert "## Structural" in body
    assert "score: 0 / 100" in body
    assert "signals_failed: []" in body
    assert "pending: 0" in body
    assert "tier: bronze" in body
    assert "layers: {}" in body
    assert "action_items: []" in body


# ─── write_dashboard ────────────────────────────────────────────────────────


def test_write_dashboard_creates_file_at_canonical_path(tmp_path: Path) -> None:
    s, e, p = _sample_inputs()
    out = write_dashboard(tmp_path, s, e, p, generated_at="2026-05-16T00:00:00+00:00")
    expected = tmp_path / ".claude" / "observability" / "dashboard.md"
    assert out == expected
    assert expected.is_file()


def test_write_dashboard_overwrites_existing(tmp_path: Path) -> None:
    s, e, p = _sample_inputs()
    write_dashboard(tmp_path, s, e, p, generated_at="2026-05-16T00:00:00+00:00")
    # Bump structural and re-write — first body must be gone.
    s2 = {**s, "score": 99}
    write_dashboard(tmp_path, s2, e, p, generated_at="2026-05-17T00:00:00+00:00")
    body = (tmp_path / ".claude" / "observability" / "dashboard.md").read_text(encoding="utf-8")
    assert "score: 99 / 100" in body
    assert "score: 72 / 100" not in body


# ─── parse_dashboard (reader contract) ──────────────────────────────────────


def test_parse_round_trips_known_inputs(tmp_path: Path) -> None:
    s, e, p = _sample_inputs()
    out = write_dashboard(tmp_path, s, e, p, generated_at="2026-05-16T00:00:00+00:00")
    parsed = parse_dashboard(out)
    assert parsed is not None
    assert parsed["structural"]["score"] == 72
    assert parsed["structural"]["signals_failed"][0] == "context_quality:has_stack"
    assert parsed["external_risks"]["pending"] == 2
    assert parsed["external_risks"]["items"][0]["id"] == "CVE-2026-0001"
    assert parsed["personalization"]["composite"] == 67
    assert parsed["personalization"]["tier"] == "gold"
    assert parsed["personalization"]["layers"]["l1_conversion"] == 60
    assert parsed["personalization"]["action_items"][0]["priority"] == "P1"


def test_parse_returns_none_for_old_single_scalar_schema(tmp_path: Path) -> None:
    """The legacy 0.12.x dashboard rendered a single ``**Composite:** NN``
    scalar with no harness-maker frontmatter. ADR-004: that schema MUST
    be unparseable by the 0.13.0 reader so the verify stage treats it
    as "no baseline → PASS" rather than mistaking it for a fresh run.
    """
    legacy = tmp_path / "dashboard.md"
    legacy.write_text(
        "# AI Readiness — example\n\n"
        "**Composite:** 75 / 100\n\n"
        "## Layer scores\n\n"
        "| Layer | Score |\n"
        "|-------|------:|\n"
        "| readiness | 80 |\n",
        encoding="utf-8",
    )
    assert parse_dashboard(legacy) is None


def test_parse_returns_none_when_missing_file(tmp_path: Path) -> None:
    assert parse_dashboard(tmp_path / "missing.md") is None


def test_parse_rejects_frontmatter_without_harness_maker_tag(tmp_path: Path) -> None:
    """Other tools could write a markdown file with frontmatter; only ours
    carries ``generated_by: harness-maker``. Treat foreign frontmatter as
    no-baseline so verify cannot read stale data from a different source."""
    foreign = tmp_path / "dash.md"
    foreign.write_text(
        "---\ngenerated_by: someone-else\n---\n# Health\n## Structural\nscore: 50 / 100\n",
        encoding="utf-8",
    )
    assert parse_dashboard(foreign) is None


def test_signals_failed_round_trips_via_json() -> None:
    """The list block uses JSON so non-trivial values survive — proves a
    verify-stage shell reader can ``jq`` the field rather than parse markdown.
    """
    s = {
        "score": 50,
        "signals_failed": [
            "dim1:sig with spaces",
            "dim2:sig|with|pipes",
            'dim3:sig"with"quotes',
        ],
    }
    body = render_dashboard_markdown(
        s, {"pending": 0, "items": []}, {}, generated_at="2026-05-16T00:00:00+00:00"
    )
    # Recover the line and JSON-parse it.
    [line] = [ln for ln in body.splitlines() if ln.startswith("signals_failed: ")]
    payload = line.removeprefix("signals_failed: ")
    decoded = json.loads(payload)
    assert decoded == s["signals_failed"]
