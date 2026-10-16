"""Shared infrastructure for boundary-parse tests (PLAN-test-fidelity-gap).

Each `test_boundary_<filetype>.py` module imports:

* ``BoundaryParseError`` — single uniform exception type raised by every
  parser helper in this module. Tests catch this; raw stdlib parser
  errors (``json.JSONDecodeError`` / ``tomllib.TOMLDecodeError`` /
  ``yaml.YAMLError``) are wrapped so callers handle one type.

* Parser helpers per file type (``parse_claude_hooks_json``,
  ``parse_settings_json``, …). Each enforces the consumer's schema:
  not just "is it valid JSON?" but "does it have the keys and shape the
  REAL consumer expects?". This is the boundary the PLAN targets — the
  gap between Python's lenient JSON loader and the strict shape the
  consumer (Claude Code / Codex / jq) actually requires.

The session-scoped ``rendered_harness_all_targets`` fixture lives in
``conftest.py`` (pytest only discovers fixtures from conftest or
explicitly registered plugins). It calls ``_invoke_make_all_targets``
from this module.

Why ``cli.make`` rather than ``synthesize() + render()`` directly: the
CLI path is what real users exercise (interview defaults → synthesize →
reconcile → render → verify → orphan_sweep) and is already pinned as
byte-identical-idempotent by ``test_render_idempotent_byte_identical``.
Going one layer deeper would diverge from the actual user-facing path
ADR-002 wants exercised — the ADR's "LIVE render" invariant is upheld
here since ``cli.make`` internally calls ``synthesize`` + ``render``
on every invocation.

CIRCULAR-ORACLE LIMITATION (Phase 9, ADR-009): every parser here validates
that a rendered file has the SHAPE its consumer expects — it does NOT
validate that the consumer actually READS that file at that location. This
is exactly how ``.claude/hooks/hooks.json`` stayed dead for 39 releases: the
boundary tests parsed the same location the emitter wrote, so a hooks block
in a location Claude Code never loads still "passed". Schema-fidelity ≠
consumption. The one test that closes this gap is the live consumption canary
``tests/e2e/test_hook_consumption_canary.py`` — it runs the real ``claude``
binary and asserts a PostToolUse hook FIRES (a ``post_tool_use`` telemetry
entry appears), which no static parser in this module can prove.

Negative tests inject synthetic bad bytes directly and assert the parser
raises — they do NOT depend on any production template carrying the
violation. Lesson from ``[fail:test] boundary-test-no-sentinel`` (2026-05-09).
"""

from __future__ import annotations

import json
import os
import tomllib
from pathlib import Path
from typing import Any

# ──────────────────────────────────────────────────────────────────────────
# Exception
# ──────────────────────────────────────────────────────────────────────────


class BoundaryParseError(ValueError):
    """Raised when a boundary parser rejects bytes for any reason.

    Wraps stdlib decoder errors so callers handle a single exception type
    across all file types in this suite.
    """


# ──────────────────────────────────────────────────────────────────────────
# Schema constants
# ──────────────────────────────────────────────────────────────────────────

# Claude Code's documented PascalCase event keys. Extending this set is a
# deliberate change — bump it when Claude Code adds an event we render.
_CLAUDE_EVENTS: frozenset[str] = frozenset(
    {
        "PreToolUse",
        "PostToolUse",
        "Stop",
        "PreCompact",
        "SessionStart",
        "SessionEnd",
        "Notification",
        "SubagentStop",
        "UserPromptSubmit",
        "PermissionRequest",
    }
)

# Codex's documented PascalCase event keys (ADR-004/006 in
# PLAN-codex-target-support). Shares Claude's PascalCase + nested-hooks
# shape but: adds ``PermissionRequest`` (Codex-exclusive), and Codex does
# NOT support ``PreCompact`` (Stop is used instead — flush_session is
# wired to Stop in the template).
_CODEX_EVENTS: frozenset[str] = frozenset(
    {
        "PreToolUse",
        "PostToolUse",
        "Stop",
        "SessionStart",
        "SessionEnd",
        "Notification",
        "SubagentStop",
        "UserPromptSubmit",
        "PermissionRequest",
    }
)


# ──────────────────────────────────────────────────────────────────────────
# Parser helpers
# ──────────────────────────────────────────────────────────────────────────


def _load_json(text: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise BoundaryParseError(f"invalid JSON: {exc.msg} at line {exc.lineno}") from exc


def parse_claude_hooks_json(text: str) -> dict[str, Any]:
    """Validate Claude Code's hooks.json schema and return the parsed mapping.

    Required invariants:
    1. Parseable JSON object at top level.
    2. Top-level key ``hooks`` mapping event name → list of entries.
    3. Every event key is in ``_CLAUDE_EVENTS`` (PascalCase allow-list).
    4. Every entry is an object with a nested ``hooks: [...]`` list
       (Claude's documented shape). The presence of a top-level ``command``
       field on the entry — the flat shape — is a hard reject.
    5. Every inner-hooks entry has ``type`` and ``command`` keys.
    """
    parsed = _load_json(text)
    if not isinstance(parsed, dict):
        raise BoundaryParseError("top level must be a JSON object")

    hooks = parsed.get("hooks")
    if not isinstance(hooks, dict):
        raise BoundaryParseError("top-level 'hooks' must be an object")

    for event_name, entries in hooks.items():
        if event_name not in _CLAUDE_EVENTS:
            raise BoundaryParseError(
                f"event {event_name!r} is not a Claude PascalCase event "
                f"(allow-list: {sorted(_CLAUDE_EVENTS)})"
            )
        if not isinstance(entries, list):
            raise BoundaryParseError(f"event {event_name!r} value must be a list")
        for entry in entries:
            if not isinstance(entry, dict):
                raise BoundaryParseError(f"event {event_name!r} entry must be an object")
            if "command" in entry and "hooks" not in entry:
                raise BoundaryParseError(
                    f"event {event_name!r} entry uses flat command shape "
                    f"(flat schema). Claude requires nested 'hooks: [...]'."
                )
            if "hooks" not in entry:
                raise BoundaryParseError(f"event {event_name!r} entry missing nested 'hooks' list")
            inner = entry["hooks"]
            if not isinstance(inner, list):
                raise BoundaryParseError(f"event {event_name!r} entry's 'hooks' must be a list")
            for h in inner:
                if not isinstance(h, dict):
                    raise BoundaryParseError("inner hook entry must be an object")
                if "type" not in h or "command" not in h:
                    raise BoundaryParseError("inner hook entry requires 'type' and 'command' keys")
    return parsed


def parse_codex_hooks_json(text: str) -> dict[str, Any]:
    """Validate Codex's hooks.json schema and return the parsed mapping.

    Shares Claude's PascalCase + nested-hooks shape but with two
    differences (ADR-004/006 in PLAN-codex-target-support):
    1. ``PermissionRequest`` event is allowed (Codex-exclusive).
    2. ``PreCompact`` event is NOT allowed (Codex uses ``Stop``).
    """
    parsed = _load_json(text)
    if not isinstance(parsed, dict):
        raise BoundaryParseError("top level must be a JSON object")

    hooks = parsed.get("hooks")
    if not isinstance(hooks, dict):
        raise BoundaryParseError("top-level 'hooks' must be an object")

    for event_name, entries in hooks.items():
        if event_name == "PreCompact":
            raise BoundaryParseError(
                "event 'PreCompact' is not supported by Codex "
                "(use 'Stop' instead — flush_session wires to Stop, ADR-004)"
            )
        if event_name not in _CODEX_EVENTS:
            raise BoundaryParseError(
                f"event {event_name!r} is not a Codex PascalCase event "
                f"(allow-list: {sorted(_CODEX_EVENTS)})"
            )
        if not isinstance(entries, list):
            raise BoundaryParseError(f"event {event_name!r} value must be a list")
        for entry in entries:
            if not isinstance(entry, dict):
                raise BoundaryParseError(f"event {event_name!r} entry must be an object")
            if "command" in entry and "hooks" not in entry:
                raise BoundaryParseError(
                    f"event {event_name!r} entry uses flat command shape. "
                    f"Codex requires nested 'hooks: [...]'."
                )
            if "hooks" not in entry:
                raise BoundaryParseError(f"event {event_name!r} entry missing nested 'hooks' list")
    return parsed


def parse_harness_yaml_at(path: Path) -> dict[str, Any]:
    """Validate a rendered harness.yaml via the canonical reader.

    Uses ``harness_maker.io_utils.load_harness_yaml`` — the single source
    of truth for multi-doc YAML parsing of provenance-wrapped harness
    config (CLAUDE.md §"외부 소비자의 파서 정합성 확인").

    Invariants beyond "loads cleanly":
    1. The returned mapping is NOT a provenance frontmatter doc (helper
       already filters those — sanity assert in case the helper changes).
    2. ``targets`` and ``second_brain.folders`` when present must be
       lists, not ``None`` (regression for
       ``[fail:render] yaml-empty-list-renders-null`` — 2026-05-11).
    3. ``permissions`` (when present) must not carry phantom-emitted
       ``ask: []`` key absent from both sides on idempotent rerender
       (regression for
       ``[fail:design] phantom-key-on-rerender-breaks-idempotency`` —
       2026-05-19). This boundary parser cannot directly observe the
       idempotency property; it asserts the weaker "if ask is present, it
       is a non-empty list" precondition — a phantom ``ask: []`` would
       fire this.
    """
    # Use the canonical helper — this is the contract the production code
    # uses. If the helper raises, that IS the boundary failure.
    try:
        from harness_maker.io_utils import load_harness_yaml
    except ImportError as exc:  # pragma: no cover — defensive
        raise BoundaryParseError(f"cannot import canonical helper: {exc}") from exc

    try:
        body = load_harness_yaml(path)
    except FileNotFoundError as exc:
        raise BoundaryParseError(f"harness.yaml not found at {path}") from exc
    except Exception as exc:
        raise BoundaryParseError(f"canonical load_harness_yaml failed: {exc}") from exc

    if not isinstance(body, dict):
        raise BoundaryParseError(f"canonical helper returned {type(body).__name__}, expected dict")

    if body.get("generated_by") == "harness-maker":
        raise BoundaryParseError(
            "canonical helper returned the provenance doc — helper contract "
            "broken (should filter provenance docs)"
        )

    if "targets" in body and not isinstance(body["targets"], list):
        raise BoundaryParseError(
            f"'targets' must be a list (got {type(body['targets']).__name__}). "
            f"Empty must render as [] not null — see "
            f"[fail:render] yaml-empty-list-renders-null."
        )

    sb = body.get("second_brain")
    if isinstance(sb, dict) and "folders" in sb and not isinstance(sb["folders"], list):
        raise BoundaryParseError(
            f"'second_brain.folders' must be a list (got "
            f"{type(sb['folders']).__name__}). Empty must render as [] not null."
        )

    perms = body.get("permissions")
    if isinstance(perms, dict) and "ask" in perms:
        ask = perms["ask"]
        if not isinstance(ask, list) or not ask:
            raise BoundaryParseError(
                "'permissions.ask' is present but empty/non-list — phantom "
                "key emission. See [fail:design] phantom-key-on-rerender-"
                "breaks-idempotency."
            )

    return body


def parse_settings_json(text: str) -> dict[str, Any]:
    """Validate `.claude/settings.json` shape and return the parsed mapping.

    Required invariants:
    1. File begins with JSON object opening (``{`` ignoring whitespace) —
       NOT a leading YAML frontmatter block (regression-adjacent for
       ``[fail:render] wrapup-eof-append-outside-marker``).
    2. Parses as a JSON object.
    3. If ``permissions`` is present, it must be an object with
       ``allow`` / ``deny`` / ``ask`` keys as lists when present.
    """
    stripped = text.lstrip()
    if stripped.startswith("---"):
        raise BoundaryParseError(
            "settings.json has leading YAML frontmatter — Claude Code "
            "parses it as JSON-only and will ignore the file. "
            "(Adjacent failure class: [fail:render] wrapup-eof-append-"
            "outside-marker.)"
        )

    parsed = _load_json(text)
    if not isinstance(parsed, dict):
        raise BoundaryParseError("settings.json top level must be a JSON object")

    perms = parsed.get("permissions")
    if perms is not None:
        if not isinstance(perms, dict):
            raise BoundaryParseError(f"'permissions' must be an object, got {type(perms).__name__}")
        for key in ("allow", "deny", "ask"):
            if key in perms and not isinstance(perms[key], list):
                raise BoundaryParseError(
                    f"'permissions.{key}' must be a list, got {type(perms[key]).__name__}"
                )
    return parsed


def _load_toml(text: str) -> dict[str, Any]:
    try:
        return tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise BoundaryParseError(f"invalid TOML: {exc}") from exc


def parse_codex_agent_toml(text: str) -> dict[str, Any]:
    """Validate a Codex agent TOML and return the parsed mapping.

    Required invariants (templates/codex/agent.toml.j2):
    1. Parseable TOML.
    2. Top-level keys: ``name`` (str), ``description`` (str),
       ``developer_instructions`` (str). Other keys allowed.
    """
    parsed = _load_toml(text)
    for required, kind in (
        ("name", str),
        ("description", str),
        ("developer_instructions", str),
    ):
        if required not in parsed:
            raise BoundaryParseError(f"agent TOML missing required key {required!r}")
        if not isinstance(parsed[required], kind):
            raise BoundaryParseError(
                f"agent TOML key {required!r} must be {kind.__name__}, "
                f"got {type(parsed[required]).__name__}"
            )
    return parsed


def parse_codex_config_toml(text: str) -> dict[str, Any]:
    """Validate Codex's top-level config.toml and return the parsed mapping.

    Required invariants (templates/codex/config.toml.j2):
    1. Parseable TOML.
    2. ``[features]`` table with ``hooks: bool`` present.
    3. If ``[mcp_servers]`` table exists, every key must be quoted in the
       source — but we can't see the source from a parsed dict. The proxy
       invariant: every mcp_server value must be a flat mapping with a
       ``command`` field, NOT nested deeper than one level (which would
       indicate dotted-key injection per
       ``[fail:render] toml-section-header-variable-injection``).
    4. ``[profiles.*]`` MUST NOT appear here. Codex CLI v0.130+ rejects
       project-local profiles with a "Ignored unsupported project-local
       config keys ... profiles" warning. The cheap/deep profiles live
       at the USER level (~/.codex/config.toml); harness-maker installs
       them there via ``codex_user_config.bootstrap_user_codex_profiles``.
    """
    parsed = _load_toml(text)

    features = parsed.get("features")
    if not isinstance(features, dict):
        raise BoundaryParseError("config.toml missing [features] table")
    if not isinstance(features.get("hooks"), bool):
        raise BoundaryParseError("config.toml [features].hooks must be a bool")

    if "profiles" in parsed:
        raise BoundaryParseError(
            "project-local config.toml MUST NOT contain [profiles.*] — Codex "
            "CLI v0.130+ rejects them at this layer. Move to ~/.codex/config.toml."
        )

    mcp_servers = parsed.get("mcp_servers")
    if mcp_servers is not None:
        if not isinstance(mcp_servers, dict):
            raise BoundaryParseError("[mcp_servers] must be a table when present")
        for server_name, server_cfg in mcp_servers.items():
            if not isinstance(server_cfg, dict):
                raise BoundaryParseError(
                    f"mcp_server {server_name!r} value must be a table, got "
                    f"{type(server_cfg).__name__} — likely unquoted dotted-key "
                    f"injection (see [fail:render] toml-section-header-"
                    f"variable-injection)."
                )
            if "command" not in server_cfg:
                raise BoundaryParseError(
                    f"mcp_server {server_name!r} missing required 'command' field"
                )

    return parsed


# ──────────────────────────────────────────────────────────────────────────
# LIVE render fixture
# ──────────────────────────────────────────────────────────────────────────


def invoke_make_all_targets(project_dir: Path) -> None:
    """Run ``harness-maker make`` with every IDE target via Typer's CliRunner.

    Pattern mirrors ``test_fresh_install_readiness._invoke_make`` but
    overrides ``--targets`` to the full set so boundary tests can inspect
    .claude/ and .codex/ artifacts from a single rendered tree.
    """
    from typer.testing import CliRunner

    from harness_maker.cli import app

    old_freeze = os.environ.get("HARNESS_MAKER_FREEZE")
    os.environ["HARNESS_MAKER_FREEZE"] = "1"
    try:
        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "make",
                str(project_dir),
                "--autoloop",
                "--preset",
                "Side",
                "--locale",
                "en",
                "--targets",
                "claude-code,codex",
            ],
            catch_exceptions=False,
        )
    finally:
        if old_freeze is None:
            os.environ.pop("HARNESS_MAKER_FREEZE", None)
        else:
            os.environ["HARNESS_MAKER_FREEZE"] = old_freeze

    if result.exit_code != 0:
        raise RuntimeError(f"harness-maker make failed (exit={result.exit_code}):\n{result.output}")
