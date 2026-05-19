"""Boundary-parse tests for `.cursor/rules/*.mdc` (PLAN-test-fidelity-gap Phase 3).

ALLOW-LIST documented in ``_boundary_helpers.parse_cursor_mdc`` (search
the source for "ALLOW-LIST"). The Cursor parser source is unavailable;
the conservative allow-list pins ``description`` / ``globs`` /
``alwaysApply`` as the only frontmatter keys we emit. CLAUDE.md §"외부
소비자의 파서 정합성 확인" already calls out this allow-list as the
contract that Cursor's parser drift would break.

Regressions covered:
- ``[fail:render] yaml-colon-in-unquoted-frontmatter-description``
  (2026-05-10): unquoted ``:`` in description text trips YAML parser →
  renderer prepends provenance → file ends up with TWO ``---`` blocks.
  Parser detects the double-block layout.

Negatives inject synthetic bad bytes — template-state-independent.
"""

from __future__ import annotations

import os
import textwrap
from pathlib import Path  # noqa: TC003

import pytest

from tests.integration._boundary_helpers import (
    BoundaryParseError,
    parse_cursor_mdc,
)

INTEGRATION_GATE = pytest.mark.skipif(
    not os.getenv("INTEGRATION"),
    reason="positive boundary tests require INTEGRATION=1 (LIVE render)",
)


# ──────────────────────────────────────────────────────────────────────────
# Positive — rendered .mdc passes the parser
# ──────────────────────────────────────────────────────────────────────────


@INTEGRATION_GATE
def test_rendered_cursor_mdc_frontmatter_passes_allowlist(
    rendered_harness_all_targets: Path,
) -> None:
    """Every rendered `.cursor/rules/*.mdc` has allow-list-only frontmatter."""
    rules_dir = rendered_harness_all_targets / ".cursor" / "rules"
    assert rules_dir.is_dir(), f"renderer did not produce {rules_dir}"
    mdcs = list(rules_dir.glob("*.mdc"))
    assert mdcs, "at least one .mdc expected when targets includes cursor"
    for path in mdcs:
        text = path.read_text(encoding="utf-8")
        frontmatter = parse_cursor_mdc(text)
        # Sanity: every .mdc must have a non-empty description (it is the
        # field Cursor surfaces in the rules UI).
        assert "description" in frontmatter, (
            f"{path.name} has no 'description' frontmatter key — "
            f"Cursor would render an unnamed rule."
        )


# ──────────────────────────────────────────────────────────────────────────
# Negative — synthetic bad bytes; UNGATED
# ──────────────────────────────────────────────────────────────────────────


@pytest.mark.boundary_negative
def test_mdc_rejects_unknown_frontmatter_key() -> None:
    """An .mdc with a frontmatter key outside the allow-list must be rejected.

    Synthetic bytes — no template dependency. If Cursor's documented
    allow-list expands, update ``_CURSOR_MDC_FRONTMATTER_KEYS`` in
    ``_boundary_helpers`` and bump the retrieval-date comment.
    """
    bad = (
        "---\n"
        "description: hi\n"
        "content_hash: deadbeef\n"  # ← not in allow-list
        "---\n"
        "body\n"
    )
    with pytest.raises(BoundaryParseError, match="unknown.*content_hash|content_hash"):
        parse_cursor_mdc(bad)


@pytest.mark.boundary_negative
def test_mdc_rejects_double_frontmatter_blocks() -> None:
    """An .mdc with TWO `---` frontmatter blocks must be rejected.

    Regression: [fail:render] yaml-colon-in-unquoted-frontmatter-description.
    """
    bad = textwrap.dedent("""\
        ---
        generated_by: harness-maker
        content_hash: abc
        ---
        ---
        description: real description here
        ---
        body
    """)
    with pytest.raises(BoundaryParseError, match="TWO frontmatter|unquoted"):
        parse_cursor_mdc(bad)


@pytest.mark.boundary_negative
def test_mdc_rejects_missing_opening_marker() -> None:
    """An .mdc without a leading `---` is rejected (no frontmatter)."""
    bad = "description: hi\nbody\n"
    with pytest.raises(BoundaryParseError, match="frontmatter"):
        parse_cursor_mdc(bad)


@pytest.mark.boundary_negative
def test_mdc_rejects_description_wrong_type() -> None:
    """`description: 42` (non-string) is rejected."""
    bad = "---\ndescription: 42\n---\nbody\n"
    with pytest.raises(BoundaryParseError, match="description.*str"):
        parse_cursor_mdc(bad)


@pytest.mark.boundary_negative
def test_mdc_rejects_always_apply_wrong_type() -> None:
    """`alwaysApply: maybe` (non-bool) is rejected."""
    bad = "---\ndescription: x\nalwaysApply: maybe\n---\nbody\n"
    with pytest.raises(BoundaryParseError, match="alwaysApply.*bool"):
        parse_cursor_mdc(bad)


@pytest.mark.boundary_negative
def test_mdc_accepts_well_formed_frontmatter() -> None:
    """Inverse-of-negative: minimal well-formed frontmatter parses cleanly."""
    good = "---\ndescription: rule about X\nglobs: []\nalwaysApply: false\n---\nbody\n"
    frontmatter = parse_cursor_mdc(good)
    assert frontmatter["description"] == "rule about X"
    assert frontmatter["alwaysApply"] is False
