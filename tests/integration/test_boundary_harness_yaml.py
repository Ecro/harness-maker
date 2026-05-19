"""Boundary-parse tests for .claude/harness.yaml (multi-doc YAML).

PLAN-test-fidelity-gap Phase 2. Rendered harness.yaml is a multi-document
YAML stream (provenance frontmatter + body); single-document
``yaml.safe_load`` rejects it (root cause of
``[fail:design] yaml-safe-load-on-multi-doc-harness-yaml``, 2026-05-17).

This module pins the canonical reader contract — every test routes through
``harness_maker.io_utils.load_harness_yaml`` so any future drift between
the renderer and the helper fires red here.

Specific regressions covered:
- ``[fail:design] yaml-empty-list-renders-null`` (2026-05-11): empty lists
  must render as ``[]``, not ``null``.
- ``[fail:design] phantom-key-on-rerender-breaks-idempotency`` (2026-05-19):
  ``permissions.ask`` must not appear when neither side declared it.
- ``[fail:test] unit-fixture-skips-renderer-frontmatter`` (2026-05-17):
  the fixture path here is the LIVE-rendered tree — no hand-built shape.

Negatives inject synthetic bad bytes — template-state-independent.
"""

from __future__ import annotations

import os
import textwrap
from pathlib import Path

import pytest

from tests.integration._boundary_helpers import (
    BoundaryParseError,
    parse_harness_yaml_at,
)

INTEGRATION_GATE = pytest.mark.skipif(
    not os.getenv("INTEGRATION"),
    reason="positive boundary tests require INTEGRATION=1 (LIVE render)",
)


# ──────────────────────────────────────────────────────────────────────────
# Positive — rendered harness.yaml passes the canonical helper
# ──────────────────────────────────────────────────────────────────────────


@INTEGRATION_GATE
def test_rendered_harness_yaml_loads_via_canonical_helper(
    rendered_harness_all_targets: Path,
) -> None:
    """LIVE harness.yaml round-trips through ``load_harness_yaml``."""
    path = rendered_harness_all_targets / ".claude" / "harness.yaml"
    assert path.is_file(), f"renderer did not produce {path}"
    body = parse_harness_yaml_at(path)
    # Sanity: the body is the user-config doc, not provenance frontmatter.
    assert body, "canonical helper returned empty body"
    assert "preset" in body or "targets" in body, (
        "body missing canonical top-level keys (preset/targets) — helper may "
        "be returning the wrong doc."
    )


@INTEGRATION_GATE
def test_rendered_harness_yaml_targets_is_list_not_null(
    rendered_harness_all_targets: Path,
) -> None:
    """``targets`` field renders as a non-null list (regression: yaml-empty-list-renders-null)."""
    path = rendered_harness_all_targets / ".claude" / "harness.yaml"
    body = parse_harness_yaml_at(path)
    targets = body.get("targets")
    assert isinstance(targets, list), (
        f"'targets' must be a list, got {type(targets).__name__}: {targets!r}. "
        f"Regression: [fail:render] yaml-empty-list-renders-null."
    )


@INTEGRATION_GATE
def test_rendered_harness_yaml_permissions_no_phantom_ask(
    rendered_harness_all_targets: Path,
) -> None:
    """``permissions.ask`` must not be phantom-emitted.

    Regression: [fail:design] phantom-key-on-rerender-breaks-idempotency.
    The parser already rejects empty/non-list 'ask' — this test pins that
    the LIVE render does NOT carry a phantom 'ask: []'.
    """
    path = rendered_harness_all_targets / ".claude" / "harness.yaml"
    body = parse_harness_yaml_at(path)
    perms = body.get("permissions")
    # Either 'ask' is absent OR it's a non-empty list. The parser
    # enforces this; reaching here means LIVE render passed.
    if isinstance(perms, dict) and "ask" in perms:
        assert perms["ask"], (
            "permissions.ask is phantom-emitted as empty — "
            "[fail:design] phantom-key-on-rerender-breaks-idempotency."
        )


# ──────────────────────────────────────────────────────────────────────────
# Negative — synthetic bad bytes; UNGATED
# ──────────────────────────────────────────────────────────────────────────


@pytest.mark.boundary_negative
def test_canonical_helper_accepts_single_doc_lacking_provenance(tmp_path: Path) -> None:
    """Inverse-of-negative: a single-doc YAML with no provenance frontmatter
    still loads (becomes the body). This is the legacy path — assert the
    helper does NOT crash on it and returns the doc as body. The
    ``boundary_negative`` marker stays per PLAN convention (the marker
    flags tests that exercise the consumer-parser boundary on synthetic
    bytes, regardless of pass/raise outcome).
    """
    path = tmp_path / "harness.yaml"
    path.write_text("preset: Side\ntargets:\n  - claude-code\n", encoding="utf-8")
    body = parse_harness_yaml_at(path)
    assert body == {"preset": "Side", "targets": ["claude-code"]}


@pytest.mark.boundary_negative
def test_parser_rejects_targets_as_null(tmp_path: Path) -> None:
    """``targets: ~`` (YAML null) must be rejected."""
    path = tmp_path / "harness.yaml"
    path.write_text(
        textwrap.dedent("""\
            preset: Side
            targets: ~
        """),
        encoding="utf-8",
    )
    with pytest.raises(BoundaryParseError, match="targets.*list"):
        parse_harness_yaml_at(path)


@pytest.mark.boundary_negative
def test_parser_rejects_second_brain_folders_as_null(tmp_path: Path) -> None:
    """``second_brain.folders: ~`` must be rejected."""
    path = tmp_path / "harness.yaml"
    path.write_text(
        textwrap.dedent("""\
            preset: Side
            second_brain:
              folders: ~
        """),
        encoding="utf-8",
    )
    with pytest.raises(BoundaryParseError, match="folders.*list"):
        parse_harness_yaml_at(path)


@pytest.mark.boundary_negative
def test_parser_rejects_phantom_empty_ask(tmp_path: Path) -> None:
    """``permissions.ask: []`` (phantom empty) must be rejected."""
    path = tmp_path / "harness.yaml"
    path.write_text(
        textwrap.dedent("""\
            preset: Side
            permissions:
              ask: []
        """),
        encoding="utf-8",
    )
    with pytest.raises(BoundaryParseError, match="ask.*phantom"):
        parse_harness_yaml_at(path)


@pytest.mark.boundary_negative
def test_parser_rejects_missing_file(tmp_path: Path) -> None:
    """Missing file raises BoundaryParseError, not FileNotFoundError."""
    path = tmp_path / "does-not-exist.yaml"
    with pytest.raises(BoundaryParseError, match="not found|found"):
        parse_harness_yaml_at(path)
