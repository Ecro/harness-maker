"""Boundary-parse tests for the Claude Code hooks block.

PLAN-test-fidelity-gap Phase 0. Verifies that the renderer-produced
hooks.json files pass each IDE's expected parser shape:

- `.claude/settings.json` (hooks block) — Claude Code: PascalCase event keys
  (`PreToolUse`/`PostToolUse`/`Stop`/`PreCompact`) + nested
  `{matcher?, hooks: [{type: "command", command, timeout?}]}` shape. (The old
  `.claude/hooks/hooks.json` is retired — Claude Code never read it, ADR-005.)

The Cursor half (`.cursor/hooks.json`, flat camelCase) left with the Cursor
target in 0.63.0. `.codex/hooks.json` is covered by test_boundary_codex_toml.py.

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
    """`.claude/settings.json`'s hooks block matches Claude Code's expected schema.

    `.claude/hooks/hooks.json` is retired (ADR-005) — Claude Code reads project
    hooks ONLY from settings.json. The PascalCase-nested schema now lives there.
    Asserts: parseable JSON; every event key is PascalCase from the allow-list;
    every entry has the nested ``{matcher?, hooks: [...]}`` shape (NOT flat Cursor).
    """
    path = rendered_harness_all_targets / ".claude" / "settings.json"
    assert path.is_file(), f"renderer did not produce {path}"
    assert not (rendered_harness_all_targets / ".claude" / "hooks" / "hooks.json").is_file(), (
        "the retired .claude/hooks/hooks.json must no longer be rendered"
    )

    parsed = parse_claude_hooks_json(path.read_text(encoding="utf-8"))
    # At least one event must be present — settings seeds PostToolUse +
    # PreToolUse + Stop + PreCompact at minimum.
    assert parsed["hooks"], "hooks dict must be non-empty"


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
def test_invalid_json_raises_parse_error() -> None:
    """Malformed JSON bytes raise BoundaryParseError, not raw JSONDecodeError —
    callers handle a single exception type uniformly across all boundary
    parsers in this suite.
    """
    bad = "{not even close to json"
    with pytest.raises(BoundaryParseError, match="JSON"):
        parse_claude_hooks_json(bad)
