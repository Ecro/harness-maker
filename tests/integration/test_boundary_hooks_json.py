"""Boundary-parse tests for hooks.json (Claude Code + Cursor dual-schema).

PLAN-test-fidelity-gap Phase 0. Verifies that the renderer-produced
hooks.json files pass each IDE's expected parser shape:

- `.claude/hooks/hooks.json` — Claude Code: PascalCase event keys
  (`PreToolUse`/`PostToolUse`/`Stop`/`PreCompact`) + nested
  `{matcher?, hooks: [{type: "command", command, timeout?}]}` shape.
- `.cursor/hooks.json` — Cursor: lowercase camelCase event keys
  (`preToolUse`/`postToolUse`/`stop`/`preCompact`) + top-level
  `version: 1` + flat `{matcher?, command, timeout?}` shape.

The dual-schema is deliberate (CLAUDE.md §"Hook schema diverges by design";
kairos 0.5.7 forensic on 2026-05-08). Tests pin this property so future
"unify the schemas" refactors break the suite — exactly what we want.

Negative tests (marker: ``boundary_negative``) inject synthetic bad bytes
at the byte level — they do NOT depend on any production template emitting
the violation. They also do NOT require ``INTEGRATION=1`` because they
exercise only the parser helpers, never the LIVE render. Pattern lesson
from ``[fail:test] boundary-test-no-sentinel`` (2026-05-09): negatives
must plant the failure condition AND remain runnable so PR CI catches
parser regressions before release.
"""

from __future__ import annotations

import os
from pathlib import Path  # noqa: TC003

import pytest

from tests.integration._boundary_helpers import (
    BoundaryParseError,
    parse_claude_hooks_json,
    parse_cursor_hooks_json,
)

# Positives consume the LIVE-rendered tree → require INTEGRATION=1.
# Negatives use only static strings and the parser helpers → no gate.
INTEGRATION_GATE = pytest.mark.skipif(
    not os.getenv("INTEGRATION"),
    reason="positive boundary tests require INTEGRATION=1 (LIVE render)",
)


# ──────────────────────────────────────────────────────────────────────────
# Positive — rendered output passes the consumer parser (INTEGRATION-gated)
# ──────────────────────────────────────────────────────────────────────────


@INTEGRATION_GATE
def test_claude_hooks_json_pascalcase_and_nested(
    rendered_harness_all_targets: Path,
) -> None:
    """`.claude/hooks/hooks.json` matches Claude Code's expected schema.

    Asserts: parseable JSON; every event key is PascalCase from the
    allow-list; every entry has the nested ``{matcher?, hooks: [...]}``
    shape (NOT the flat Cursor shape).
    """
    path = rendered_harness_all_targets / ".claude" / "hooks" / "hooks.json"
    assert path.is_file(), f"renderer did not produce {path}"

    parsed = parse_claude_hooks_json(path.read_text(encoding="utf-8"))
    # At least one event must be present — the template seeds PostToolUse +
    # PreToolUse + PreCompact at minimum (verified in template body).
    assert parsed["hooks"], "hooks dict must be non-empty"


@INTEGRATION_GATE
def test_cursor_hooks_json_lowercase_and_flat(
    rendered_harness_all_targets: Path,
) -> None:
    """`.cursor/hooks.json` matches Cursor's expected schema.

    Asserts: parseable JSON; ``version: 1`` present; every event key is
    lowercase camelCase from the allow-list; every entry has the flat
    ``{matcher?, command, timeout?}`` shape (NOT the nested Claude shape).
    """
    path = rendered_harness_all_targets / ".cursor" / "hooks.json"
    assert path.is_file(), f"renderer did not produce {path}"

    parsed = parse_cursor_hooks_json(path.read_text(encoding="utf-8"))
    assert parsed["version"] == 1, "Cursor hooks file must declare version: 1"
    assert parsed["hooks"], "hooks dict must be non-empty"


@INTEGRATION_GATE
def test_claude_and_cursor_hooks_are_byte_disjoint(
    rendered_harness_all_targets: Path,
) -> None:
    """The two files are distinct on disk (sanity for dual-render contract).

    Catches the silent-collapse failure mode where one render path is
    accidentally pointed at both targets — they'd produce identical bytes,
    which would mean one IDE is reading the wrong schema.
    """
    claude_path = rendered_harness_all_targets / ".claude" / "hooks" / "hooks.json"
    cursor_path = rendered_harness_all_targets / ".cursor" / "hooks.json"
    assert claude_path.read_bytes() != cursor_path.read_bytes(), (
        "Claude + Cursor hooks files have identical bytes — dual-render contract "
        "broken. Each IDE owns its own schema; merging breaks one of them."
    )


# ──────────────────────────────────────────────────────────────────────────
# Negative — synthetic bad bytes; template-state-independent; UNGATED
# (run on every PR so parser regressions are caught immediately, not just
#  at release time when INTEGRATION=1 is exercised.)
# ──────────────────────────────────────────────────────────────────────────


@pytest.mark.boundary_negative
def test_claude_validator_rejects_lowercase_keys() -> None:
    """A hooks file with Cursor-shape keys (lowercase) must be rejected
    by the Claude parser. Synthetic bytes — no template dependency.
    """
    bad = '{"hooks": {"preToolUse": [{"matcher": "Bash", "hooks": []}]}}'
    with pytest.raises(BoundaryParseError, match="PascalCase|event"):
        parse_claude_hooks_json(bad)


@pytest.mark.boundary_negative
def test_claude_validator_rejects_flat_shape() -> None:
    """A hooks file with Cursor-shape entries (flat command, no nested
    hooks[]) must be rejected by the Claude parser even with PascalCase
    event keys. Synthetic bytes — no template dependency.
    """
    bad = '{"hooks": {"PreToolUse": [{"matcher": "Bash", "command": "echo hi"}]}}'
    with pytest.raises(BoundaryParseError, match="nested|hooks"):
        parse_claude_hooks_json(bad)


@pytest.mark.boundary_negative
def test_cursor_validator_rejects_pascalcase_keys() -> None:
    """A hooks file with Claude-shape keys (PascalCase) must be rejected
    by the Cursor parser. Synthetic bytes — no template dependency.
    """
    bad = '{"version": 1, "hooks": {"PreToolUse": [{"matcher": "Bash", "command": "x"}]}}'
    with pytest.raises(BoundaryParseError, match="camelCase|event"):
        parse_cursor_hooks_json(bad)


@pytest.mark.boundary_negative
def test_cursor_validator_rejects_missing_version() -> None:
    """A hooks file without the top-level ``version: 1`` declaration must
    be rejected. Cursor uses the version field to dispatch parser logic.
    """
    bad = '{"hooks": {"preToolUse": [{"matcher": "Bash", "command": "x"}]}}'
    with pytest.raises(BoundaryParseError, match="version"):
        parse_cursor_hooks_json(bad)


@pytest.mark.boundary_negative
def test_cursor_validator_rejects_nested_shape() -> None:
    """A hooks file with Claude-shape nested ``hooks[]`` arrays inside
    each entry must be rejected by the Cursor parser even with lowercase
    keys. Synthetic bytes — no template dependency.
    """
    bad = '{"version": 1, "hooks": {"preToolUse": [{"matcher": "Bash", "hooks": []}]}}'
    with pytest.raises(BoundaryParseError, match="flat|command"):
        parse_cursor_hooks_json(bad)


@pytest.mark.boundary_negative
def test_invalid_json_raises_parse_error() -> None:
    """Malformed JSON bytes raise BoundaryParseError, not raw JSONDecodeError —
    callers handle a single exception type uniformly across all boundary
    parsers in this suite.
    """
    bad = "{not even close to json"
    with pytest.raises(BoundaryParseError, match="JSON"):
        parse_claude_hooks_json(bad)
    with pytest.raises(BoundaryParseError, match="JSON"):
        parse_cursor_hooks_json(bad)
