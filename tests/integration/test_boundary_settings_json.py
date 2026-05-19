"""Boundary-parse tests for `.claude/settings.json` (PLAN-test-fidelity-gap Phase 3).

`settings.json` is NOT template-driven — it is built programmatically in
``render._render_settings_json`` with ``sort_keys=True`` for cross-edit
determinism. The boundary risk is that a frontmatter prefix (which the
renderer applies to most templated files) accidentally leaks onto this
file — which would cause Claude Code to silently ignore the entire
contents (regression-adjacent for
``[fail:render] wrapup-eof-append-outside-marker``, 2026-05-17, where
content past a closing marker was treated as user data and dropped).

Negatives inject synthetic bad bytes — template-state-independent.
"""

from __future__ import annotations

import os
from pathlib import Path  # noqa: TC003

import pytest

from tests.integration._boundary_helpers import (
    BoundaryParseError,
    parse_settings_json,
)

INTEGRATION_GATE = pytest.mark.skipif(
    not os.getenv("INTEGRATION"),
    reason="positive boundary tests require INTEGRATION=1 (LIVE render)",
)


# ──────────────────────────────────────────────────────────────────────────
# Positive — rendered settings.json passes the parser
# ──────────────────────────────────────────────────────────────────────────


@INTEGRATION_GATE
def test_rendered_settings_json_is_pure_json(
    rendered_harness_all_targets: Path,
) -> None:
    """`.claude/settings.json` is pure JSON (no leading frontmatter)."""
    path = rendered_harness_all_targets / ".claude" / "settings.json"
    assert path.is_file(), f"renderer did not produce {path}"
    parsed = parse_settings_json(path.read_text(encoding="utf-8"))
    # Sanity: production settings always carry permissions config — the
    # 4 dangerous-pattern deny entries are part of the baseline.
    assert "permissions" in parsed, (
        "rendered settings.json missing 'permissions' — template invariant broken"
    )


@INTEGRATION_GATE
def test_rendered_settings_json_permissions_lists_well_formed(
    rendered_harness_all_targets: Path,
) -> None:
    """`permissions.allow`, `.deny`, `.ask` (when present) are lists."""
    path = rendered_harness_all_targets / ".claude" / "settings.json"
    parsed = parse_settings_json(path.read_text(encoding="utf-8"))
    perms = parsed["permissions"]
    # `deny` is always seeded with the 4 dangerous patterns; assert
    # explicitly because parse_settings_json only enforces the *type* (list).
    assert isinstance(perms.get("deny"), list), "permissions.deny must be a list"
    assert perms["deny"], (
        "permissions.deny must be non-empty with the 4 dangerous patterns"
    )


# ──────────────────────────────────────────────────────────────────────────
# Negative — synthetic bad bytes; UNGATED
# ──────────────────────────────────────────────────────────────────────────


@pytest.mark.boundary_negative
def test_settings_rejects_leading_frontmatter() -> None:
    """Leading `---` YAML frontmatter must be rejected — Claude Code expects pure JSON."""
    bad = '---\nfoo: bar\n---\n{"permissions": {"allow": []}}'
    with pytest.raises(BoundaryParseError, match="frontmatter|JSON"):
        parse_settings_json(bad)


@pytest.mark.boundary_negative
def test_settings_rejects_invalid_json() -> None:
    """Malformed JSON raises BoundaryParseError, not raw JSONDecodeError."""
    bad = "{not even close to json"
    with pytest.raises(BoundaryParseError, match="JSON"):
        parse_settings_json(bad)


@pytest.mark.boundary_negative
def test_settings_rejects_permissions_wrong_shape() -> None:
    """`permissions` value must be an object, not an array/scalar."""
    bad = '{"permissions": ["allow", "deny"]}'
    with pytest.raises(BoundaryParseError, match="permissions.*object"):
        parse_settings_json(bad)


@pytest.mark.boundary_negative
def test_settings_rejects_permissions_deny_scalar() -> None:
    """`permissions.deny: "rm"` (scalar, not list) must be rejected."""
    bad = '{"permissions": {"deny": "rm"}}'
    with pytest.raises(BoundaryParseError, match="deny.*list"):
        parse_settings_json(bad)


@pytest.mark.boundary_negative
def test_settings_accepts_minimal_well_formed() -> None:
    """Inverse-of-negative: a minimal valid settings.json parses cleanly."""
    good = '{"permissions": {"allow": ["Read(*)"], "deny": ["Bash(rm:*)"]}}'
    parsed = parse_settings_json(good)
    assert parsed["permissions"]["deny"] == ["Bash(rm:*)"]
