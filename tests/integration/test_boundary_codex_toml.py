"""Boundary-parse tests for Codex TOML + hooks.json artifacts.

PLAN-test-fidelity-gap Phase 1. Codex CLI is Rust → its ``toml`` crate is
stricter than Python's ``tomllib``. We test what ``tomllib`` accepts AND
additionally pin structural invariants the Codex template enforces:

- ``.codex/config.toml`` — TOML with ``[features]`` (``hooks=true``) and
  optional ``[mcp_servers."<name>"]``. ``[profiles.*]`` MUST NOT appear
  at this layer (Codex CLI v0.130+ rejects them; they live in the
  user-level ``~/.codex/config.toml`` and are installed by
  ``codex_user_config.bootstrap_user_codex_profiles``). The
  ``[fail:render] toml-section-header-variable-injection`` regression
  (2026-05-10): unquoted dotted server names silently nest under hierarchy
  tables. Test pins quoted-key parsing to a single key.
- ``.codex/agents/*.toml`` — TOML with ``name``/``description``/
  ``developer_instructions`` keys.
- ``.codex/hooks.json`` — Claude-like PascalCase + nested ``hooks: [...]``
  shape PLUS ``PermissionRequest`` event AND NO ``PreCompact`` (Codex uses
  ``Stop`` instead, ADR-004 PLAN-codex-target-support).

Negatives inject synthetic bad bytes — template-state-independent.
"""

from __future__ import annotations

import os
import tomllib
from pathlib import Path  # noqa: TC003

import pytest

from tests.integration._boundary_helpers import (
    BoundaryParseError,
    parse_codex_agent_toml,
    parse_codex_config_toml,
    parse_codex_hooks_json,
)

INTEGRATION_GATE = pytest.mark.skipif(
    not os.getenv("INTEGRATION"),
    reason="positive boundary tests require INTEGRATION=1 (LIVE render)",
)


# ──────────────────────────────────────────────────────────────────────────
# Positive — rendered output passes the Codex parsers
# ──────────────────────────────────────────────────────────────────────────


@INTEGRATION_GATE
def test_codex_config_toml_passes_parser(rendered_harness_all_targets: Path) -> None:
    """`.codex/config.toml` has [features] + [profiles] + valid [mcp_servers]."""
    path = rendered_harness_all_targets / ".codex" / "config.toml"
    assert path.is_file(), f"renderer did not produce {path}"
    parsed = parse_codex_config_toml(path.read_text(encoding="utf-8"))
    assert parsed["features"]["hooks"] is True


@INTEGRATION_GATE
def test_codex_agent_toml_files_pass_parser(rendered_harness_all_targets: Path) -> None:
    """Every `.codex/agents/*.toml` parses + has the 3 required keys."""
    agents_dir = rendered_harness_all_targets / ".codex" / "agents"
    assert agents_dir.is_dir(), f"renderer did not produce {agents_dir}"
    toml_files = list(agents_dir.glob("*.toml"))
    assert toml_files, "at least one agent TOML expected from Codex render"
    for path in toml_files:
        parsed = parse_codex_agent_toml(path.read_text(encoding="utf-8"))
        # Sanity: developer_instructions should be non-empty for a real agent.
        assert parsed["developer_instructions"].strip(), (
            f"agent {path.name} has empty developer_instructions"
        )


@INTEGRATION_GATE
def test_codex_hooks_json_passes_parser(rendered_harness_all_targets: Path) -> None:
    """`.codex/hooks.json` has Codex-shape (PascalCase + nested + no PreCompact)."""
    path = rendered_harness_all_targets / ".codex" / "hooks.json"
    assert path.is_file(), f"renderer did not produce {path}"
    parsed = parse_codex_hooks_json(path.read_text(encoding="utf-8"))
    # Codex template wires PermissionRequest — pin its presence.
    assert "PermissionRequest" in parsed["hooks"], (
        "Codex hooks must declare PermissionRequest event (ADR-006). "
        "If template removed it, ADR needs revision."
    )
    # Codex must NOT emit PreCompact (ADR-004).
    assert "PreCompact" not in parsed["hooks"], (
        "Codex hooks template wrote PreCompact — Codex does not support it. "
        "flush_session must be wired to Stop instead (ADR-004)."
    )


# ──────────────────────────────────────────────────────────────────────────
# Negative — synthetic bad bytes; UNGATED
# ──────────────────────────────────────────────────────────────────────────


@pytest.mark.boundary_negative
def test_codex_hooks_rejects_precompact() -> None:
    """A Codex hooks file with PreCompact event must be rejected.

    Regression guard: if the template ever emits PreCompact for Codex,
    this parser catches it. Codex never invokes PreCompact (ADR-004).
    """
    bad = '{"hooks": {"PreCompact": [{"matcher": "*", "hooks": []}]}}'
    with pytest.raises(BoundaryParseError, match="PreCompact"):
        parse_codex_hooks_json(bad)


@pytest.mark.boundary_negative
def test_codex_hooks_rejects_flat_shape() -> None:
    """Codex requires nested ``hooks: [...]`` shape (same as Claude)."""
    bad = '{"hooks": {"PreToolUse": [{"matcher": "Bash", "command": "x"}]}}'
    with pytest.raises(BoundaryParseError, match="nested|hooks"):
        parse_codex_hooks_json(bad)


@pytest.mark.boundary_negative
def test_codex_hooks_accepts_permission_request() -> None:
    """``PermissionRequest`` is Codex-exclusive and must be accepted.

    Inverse-of-negative: this asserts the parser does NOT reject a
    well-formed PermissionRequest entry. If the allow-list were
    accidentally narrowed, this fires red.
    """
    good = '{"hooks": {"PermissionRequest": [{"hooks": [{"type": "command", "command": "x"}]}]}}'
    parsed = parse_codex_hooks_json(good)
    assert "PermissionRequest" in parsed["hooks"]


@pytest.mark.boundary_negative
def test_codex_config_dotted_key_injection_rejected() -> None:
    """Unquoted dotted mcp_server name produces nested tables — must reject.

    Pinned regression: ``[fail:render] toml-section-header-variable-injection``
    (2026-05-10). The template uses ``[mcp_servers."{{ server_name }}"]``
    (quoted) so a server name like ``server.with.dot`` produces a single
    key. If a future refactor drops the quotes, the rendered TOML nests
    the table under ``mcp_servers.server.with.dot`` (a 4-level hierarchy)
    and this parser must reject it.
    """
    # tomllib happily parses unquoted dotted keys as nested. The parser's
    # job is to detect that the result is *not* the expected flat shape.
    bad_unquoted = (
        "[features]\nhooks = true\n"
        # Note: NO quotes around the server name — TOML interprets as hierarchy
        '[mcp_servers.example.com]\ncommand = "x"\n'
    )
    # Sanity: tomllib does parse this without error (silent invariant break).
    raw = tomllib.loads(bad_unquoted)
    assert "example" in raw["mcp_servers"], (
        "tomllib should silently nest unquoted dotted keys — if not, the test "
        "premise is wrong and the dotted-key gotcha may have been resolved upstream."
    )
    # The boundary parser must catch the nesting.
    with pytest.raises(BoundaryParseError, match="dotted-key|table|command"):
        parse_codex_config_toml(bad_unquoted)


@pytest.mark.boundary_negative
def test_codex_config_accepts_quoted_dotted_server_name() -> None:
    """Quoted dotted mcp_server name parses to a single key.

    Inverse-of-negative: the correct (quoted) shape must NOT trigger
    rejection. If the parser's invariant becomes too tight, this fires red.
    """
    good_quoted = (
        "[features]\nhooks = true\n"
        '[mcp_servers."example.com"]\ncommand = "x"\n'
    )
    parsed = parse_codex_config_toml(good_quoted)
    # The dotted name resolves to a single key — NOT nested.
    assert "example.com" in parsed["mcp_servers"]
    assert "example" not in parsed["mcp_servers"]


@pytest.mark.boundary_negative
def test_codex_config_rejects_missing_features() -> None:
    """Codex config without [features] table must be rejected."""
    bad = (
        "[mcp_servers.\"example\"]\ncommand = \"x\"\n"
    )
    with pytest.raises(BoundaryParseError, match="features"):
        parse_codex_config_toml(bad)


@pytest.mark.boundary_negative
def test_codex_config_rejects_project_level_profiles() -> None:
    """[profiles.*] in project-local config must be rejected.

    Codex CLI v0.130+ silently drops [profiles.*] from project-local
    .codex/config.toml with a "Ignored unsupported project-local
    config keys ... profiles" warning. Our parser surfaces this as a
    hard error so a future template regression that re-injects the
    blocks here gets caught at boundary-test time, not by a user
    seeing the Codex warning on every session start.
    """
    bad = (
        "[features]\nhooks = true\n"
        '[profiles.cheap]\nmodel_reasoning_effort = "minimal"\n'
    )
    with pytest.raises(BoundaryParseError, match="profiles"):
        parse_codex_config_toml(bad)


@pytest.mark.boundary_negative
def test_codex_agent_rejects_missing_developer_instructions() -> None:
    """Codex agent TOML missing developer_instructions must be rejected."""
    bad = 'name = "x"\ndescription = "y"\n'
    with pytest.raises(BoundaryParseError, match="developer_instructions"):
        parse_codex_agent_toml(bad)


@pytest.mark.boundary_negative
def test_codex_toml_invalid_bytes_raises_parse_error() -> None:
    """Malformed TOML bytes raise BoundaryParseError, not raw TOMLDecodeError."""
    bad = "[unclosed section"
    with pytest.raises(BoundaryParseError, match="TOML"):
        parse_codex_config_toml(bad)
    with pytest.raises(BoundaryParseError, match="TOML"):
        parse_codex_agent_toml(bad)
