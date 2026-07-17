"""settings.json `hooks` wiring (PLAN-permission-deny-and-hooks-wiring Phase 1).

Claude Code reads project hooks ONLY from settings files — a plain project's
`.claude/hooks/hooks.json` is never loaded (hooks.md's location table; confirmed
by controlled experiment 2026-07-17: hand-adding telemetry + sessionid_envfile to
settings.json flipped both `metrics-*.jsonl` and `HM_SESSION_ID`, while the same
commands in `.claude/hooks/hooks.json` fired nothing).

These tests pin the Phase 1 contract:
  - the settings template emits the ADR-006 Stage-1 hooks,
  - `sessionstart_drift` is NOT among them (ADR-010 — the plugin bundle owns it),
  - `hooks` is harness-owned but DEEP-merged (ADR-008): user hooks survive,
    retired harness hooks are dropped via the `<HM>:` command fingerprint,
  - `permissions` merging is unregressed.

Fixtures mirror the renderer's real output shape per
`[wiki:pattern] test-fixture-must-mirror-renderer` — settings.json is pure JSON
with no frontmatter, so a plain `json.dump` IS the production shape here.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from harness_maker.models import HarnessConfig
from harness_maker.render import (
    _SETTINGS_KEYS_OWNED_BY_HARNESS,
    _make_env,
    _merge_hooks_json,
)

SETTINGS_TEMPLATES = ("settings/Side.json.j2", "settings/Production.json.j2")

# ADR-006 Stage 1 — non-blocking only. Stage 2 (loop_gate, autopilot_guard) and
# Stage 3 (permission_gate, worktree_gate, spec_gate) land in later phases.
STAGE1_MODULES = frozenset(
    {
        "harness_maker.telemetry",
        "harness_maker.hooks.post_write_reminder",
        "harness_maker.hooks.sessionid_envfile",
        "harness_maker.hooks.autopilot_autoarm",
        "harness_maker.hooks.flush_session",
    }
)

# Not yet wired (ADR-006 staging) — a later phase adds these. Pinning their
# ABSENCE is what makes the staged rollout real rather than aspirational.
LATER_STAGE_MODULES = frozenset(
    {
        "harness_maker.hooks.loop_gate",
        "harness_maker.hooks.autopilot_guard",
        "harness_maker.gates.permission_gate",
        "harness_maker.gates.worktree_gate",
        "harness_maker.gates.spec_gate",
    }
)


def _render(template: str, **cfg: Any) -> dict[str, Any]:
    config = HarnessConfig(**cfg).model_dump(mode="json")
    out = (
        _make_env()
        .get_template(template)
        .render(
            preset="Side",
            config=config,
            harness_maker_src_path="/fake/src/path",
        )
    )
    parsed = json.loads(out)
    assert isinstance(parsed, dict)
    return parsed


def _commands(settings: dict[str, Any]) -> list[str]:
    """Every command string under settings["hooks"], any event."""
    out: list[str] = []
    for entries in settings.get("hooks", {}).values():
        for entry in entries:
            for h in entry.get("hooks", []):
                out.append(h["command"])
    return out


# ──────────────────────────────────────────────────────────────────────────
# Template contract
# ──────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("template", SETTINGS_TEMPLATES)
def test_settings_template_emits_hooks_key(template: str) -> None:
    """The premise fix: hooks must live in settings.json, not hooks/hooks.json."""
    assert "hooks" in _render(template), (
        f"{template}: no 'hooks' key — Claude reads hooks only from settings files"
    )


@pytest.mark.parametrize("template", SETTINGS_TEMPLATES)
def test_settings_hooks_carry_stage1_modules(template: str) -> None:
    cmds = " ".join(_commands(_render(template)))
    for mod in STAGE1_MODULES:
        assert mod in cmds, f"{template}: Stage-1 hook {mod} missing"


@pytest.mark.parametrize("template", SETTINGS_TEMPLATES)
def test_settings_hooks_exclude_later_stages(template: str) -> None:
    """ADR-006: staging is only real if the later stages are provably absent."""
    cmds = " ".join(_commands(_render(template)))
    for mod in LATER_STAGE_MODULES:
        assert mod not in cmds, f"{template}: {mod} is Stage 2/3 — must not ship in Phase 1"


@pytest.mark.parametrize("template", SETTINGS_TEMPLATES)
def test_settings_hooks_exclude_sessionstart_drift(template: str) -> None:
    """ADR-010: the plugin bundle already fires it; rendering it here double-registers."""
    cmds = " ".join(_commands(_render(template)))
    assert "sessionstart_drift" not in cmds


@pytest.mark.parametrize("template", SETTINGS_TEMPLATES)
def test_settings_hooks_use_claude_nested_schema(template: str) -> None:
    """PascalCase events + nested {matcher?, hooks:[{type,command}]} — Claude's shape."""
    hooks = _render(template)["hooks"]
    assert all(e[0].isupper() for e in hooks), f"{template}: event keys must be PascalCase"
    for event, entries in hooks.items():
        assert isinstance(entries, list), f"{template}: {event} must be a list"
        for entry in entries:
            assert "command" not in entry, f"{template}: {event} uses Cursor's flat shape"
            inner = entry.get("hooks")
            assert isinstance(inner, list), f"{template}: {event} needs a nested hooks[] list"
            assert inner, f"{template}: {event} has an empty nested hooks[]"
            for h in entry["hooks"]:
                assert h.get("type") == "command"
                assert isinstance(h.get("command"), str)


# ──────────────────────────────────────────────────────────────────────────
# Ownership + merge contract (ADR-008)
# ──────────────────────────────────────────────────────────────────────────


def test_hooks_is_harness_owned_key() -> None:
    """Owned ⇒ a template that drops the key actively removes it from disk."""
    assert "hooks" in _SETTINGS_KEYS_OWNED_BY_HARNESS


def _nested(matcher: str, *commands: str) -> dict[str, Any]:
    """A nested (Claude/Codex) entry. Variadic: a matcher group may hold N commands."""
    return {"matcher": matcher, "hooks": [{"type": "command", "command": c} for c in commands]}


def test_merge_preserves_user_authored_hook() -> None:
    """CLAUDE.md checklist §1 — a user hook in settings.json survives re-render."""
    existing = {"hooks": {"PostToolUse": [_nested("*", "/usr/local/bin/my-own-hook.sh")]}}
    new = {
        "hooks": {
            "PostToolUse": [_nested("*", "uv run --with /p python -m harness_maker.telemetry")]
        }
    }
    merged = _merge_hooks_json(existing, new, schema="nested")
    cmds = [h["command"] for e in merged["hooks"]["PostToolUse"] for h in e["hooks"]]
    assert "/usr/local/bin/my-own-hook.sh" in cmds


def test_merge_never_deletes_a_hook_in_our_namespace_that_we_do_not_ship() -> None:
    """REVIEW round 1 (security-reviewer P1 + codex): `<HM>:` is namespace, not authorship.

    A draft dropped any all-`<HM>:` entry absent from the template as "retired-ours".
    But the staged rollout deliberately does not ship `spec_gate` / `permission_gate` /
    `loop_gate` yet, so a user who hand-wires one would have it silently deleted — and
    the staging is exactly what creates that population. Deletion is not free and
    Phase 1 gains nothing from it (no template retires anything yet).

    Preservation is the invariant. Re-pin this ONLY alongside positive provenance
    (a prior-render manifest), never a command-prefix inference.
    """
    hand_wired = "uv run --with /p python -m harness_maker.gates.spec_gate"
    existing = {"hooks": {"PreToolUse": [_nested("Write|Edit", hand_wired)]}}
    new: dict[str, Any] = {"hooks": {"PreToolUse": []}}
    merged = _merge_hooks_json(existing, new, schema="nested")
    cmds = [h["command"] for e in merged["hooks"]["PreToolUse"] for h in e["hooks"]]
    assert hand_wired in cmds, "a user's hand-wired harness-module hook was silently deleted"


def test_merge_dedups_harness_hook_across_plugin_path_change() -> None:
    """The 2026-05-28 spoton-triplication invariant — path-agnostic identity."""
    existing = {
        "hooks": {
            "PostToolUse": [
                _nested("*", "uv run --with /old/0.38.0 python -m harness_maker.telemetry")
            ]
        }
    }
    new = {
        "hooks": {
            "PostToolUse": [
                _nested("*", "uv run --with /new/0.39.0 python -m harness_maker.telemetry")
            ]
        }
    }
    merged = _merge_hooks_json(existing, new, schema="nested")
    assert len(merged["hooks"]["PostToolUse"]) == 1, "same hook at a new cache path duplicated"


def test_merge_preserves_user_added_event() -> None:
    existing = {"hooks": {"Notification": [_nested("*", "/usr/local/bin/notify.sh")]}}
    new = {
        "hooks": {
            "PostToolUse": [_nested("*", "uv run --with /p python -m harness_maker.telemetry")]
        }
    }
    merged = _merge_hooks_json(existing, new, schema="nested")
    assert "Notification" in merged["hooks"]


def test_merge_no_duplication_when_target_template_ships_the_same_command() -> None:
    """`permission_gate` is wired to PreToolUse/Bash in BOTH the Claude and Codex
    templates under the same nested schema and event name. Feeding an identical
    on-disk entry to a template that ships it must dedup to exactly one, and to a
    template that does not must preserve it (never delete — see
    `test_merge_never_deletes_a_hook_in_our_namespace_that_we_do_not_ship`).
    """
    cmd = "uv run --with /p python -m harness_maker.gates.permission_gate"
    on_disk = {"hooks": {"PreToolUse": [_nested("Bash", cmd)]}}

    ships = _merge_hooks_json(
        on_disk, {"hooks": {"PreToolUse": [_nested("Bash", cmd)]}}, schema="nested"
    )
    ships_cmds = [h["command"] for e in ships["hooks"]["PreToolUse"] for h in e["hooks"]]
    assert ships_cmds.count(cmd) == 1, "template ships it → dedup to one, not two"

    silent: dict[str, Any] = {"hooks": {"PreToolUse": []}}
    kept = _merge_hooks_json(on_disk, silent, schema="nested")
    kept_cmds = [h["command"] for e in kept["hooks"]["PreToolUse"] for h in e["hooks"]]
    assert kept_cmds == [cmd], "template silent → preserve, never delete"


def test_merge_entry_identity_covers_all_commands_in_group() -> None:
    """ADR-008(b): identity must key on EVERY command in a matcher group.

    Live on the entry Phase 1 ships: with `sessionstart_drift` excluded (ADR-010),
    the Stage-1 SessionStart group carries TWO commands. Under the current
    `hooks_list[0]`-only key (render.py:652) a group is identified by its first
    command alone, so an on-disk group whose LATER commands differ is misread as
    identical to the shipped one and replaced wholesale.

    The case that makes this a data-loss bug rather than a cosmetic one: a user
    appends their own hook to a harness matcher group. First-command-only sees
    `<HM>:telemetry` on both sides, classifies the on-disk group as "already
    shipped", and drops it — taking the user's command with it (CLAUDE.md §1).
    """
    hm_cmd = "uv run --with /p python -m harness_maker.telemetry"
    existing = {"hooks": {"PostToolUse": [_nested("*", hm_cmd, "/usr/local/bin/user-extra.sh")]}}
    new = {"hooks": {"PostToolUse": [_nested("*", hm_cmd)]}}

    merged = _merge_hooks_json(existing, new, schema="nested")
    cmds = [h["command"] for e in merged["hooks"]["PostToolUse"] for h in e["hooks"]]
    assert "/usr/local/bin/user-extra.sh" in cmds, (
        "user command inside a harness matcher group was dropped — the group's identity "
        "must cover all commands, and a group is only retired when EVERY command is ours"
    )
    # REVIEW round 1, consensus-passed P1 (codex + code-reviewer): preserving the
    # mixed group VERBATIM beside the shipped group registers our command twice, so
    # it fires twice — the duplication `_normalize_hm_managed_command` exists to
    # prevent. The user's command is kept; ours is not duplicated.
    assert cmds.count(hm_cmd) == 1, f"harness command duplicated → fires twice: {cmds}"


def test_merge_preserves_both_all_harness_and_mixed_groups_when_template_is_silent() -> None:
    """Nothing is deleted when the template ships nothing for the event.

    Covers both shapes an on-disk group can take — wholly ours, and mixed with a
    user command. Neither is the template's to remove.
    """
    gate = "uv run --with /p python -m harness_maker.gates.spec_gate"
    guard = "uv run --with /p python -m harness_maker.hooks.autopilot_guard"
    existing = {
        "hooks": {
            "PreToolUse": [
                _nested("Write|Edit", gate, guard),  # wholly ours
                _nested("Bash", gate, "/usr/local/bin/mine.sh"),  # mixed
            ]
        }
    }
    new: dict[str, Any] = {"hooks": {"PreToolUse": []}}
    merged = _merge_hooks_json(existing, new, schema="nested")
    cmds = [h["command"] for e in merged["hooks"]["PreToolUse"] for h in e["hooks"]]
    assert "/usr/local/bin/mine.sh" in cmds, "mixed group holds user content — must survive"
    assert guard in cmds, "an all-harness group the template does not ship is not ours to delete"
    assert gate in cmds


def _flat(matcher: str, command: str) -> dict[str, Any]:
    """A flat (Cursor) entry — one command, no nested hooks[] list."""
    return {"matcher": matcher, "command": command}


def test_merge_flat_cursor_schema_preserves_and_dedups() -> None:
    """`_entry_identity` + `_strip_shipped_commands` are shared with `.cursor/hooks.json`.

    That file uses the FLAT schema (one command per entry, no nested `hooks[]`), so it
    must survive the nested-schema-driven changes untouched.
    """
    hm = "uv run --with /p python -m harness_maker.telemetry"
    existing = {"hooks": {"postToolUse": [_flat("*", hm), _flat("*", "/usr/local/bin/mine.sh")]}}
    new = {
        "hooks": {
            "postToolUse": [_flat("*", "uv run --with /NEW python -m harness_maker.telemetry")]
        }
    }
    merged = _merge_hooks_json(existing, new, schema="flat")
    cmds = [e["command"] for e in merged["hooks"]["postToolUse"]]
    assert sum("harness_maker.telemetry" in c for c in cmds) == 1, "flat: path change must dedup"
    assert "/usr/local/bin/mine.sh" in cmds, "flat: user entry must survive"


def test_merge_flat_empty_command_is_preserved() -> None:
    """A degenerate entry is still the user's — never silently dropped."""
    existing = {"hooks": {"preToolUse": [_flat("*", "")]}}
    new: dict[str, Any] = {"hooks": {"preToolUse": []}}
    merged = _merge_hooks_json(existing, new, schema="flat")
    assert len(merged["hooks"]["preToolUse"]) == 1


# ──────────────────────────────────────────────────────────────────────────
# Whole-file render behavior (no regression on permissions)
# ──────────────────────────────────────────────────────────────────────────


def _write_settings(tmp: Path, data: dict[str, Any]) -> Path:
    claude = tmp / ".claude"
    claude.mkdir(parents=True, exist_ok=True)
    p = claude / "settings.json"
    p.write_text(json.dumps(data, indent=2) + "\n")
    return p


def test_render_settings_merges_hooks_and_preserves_foreign_keys(tmp_path: Path) -> None:
    """End-to-end through the real render path: enabledPlugins + a user hook survive."""
    from harness_maker.render import _render_settings_json

    _write_settings(
        tmp_path,
        {
            "enabledPlugins": {"harness-maker@local": True},
            "hooks": {"PostToolUse": [_nested("*", "/usr/local/bin/mine.sh")]},
        },
    )

    class _FE:
        template = "settings/Side.json.j2"
        path = Path("settings.json")
        context = {
            "preset": "Side",
            "config": HarnessConfig().model_dump(mode="json"),
            "harness_maker_src_path": "/fake/src/path",
        }
        body_sha256 = ""

    out = _render_settings_json(
        _FE(),  # type: ignore[arg-type]
        _make_env(),
        tmp_path / ".claude",
        dry_run=False,
        freeze_time=None,
    )
    data = json.loads(out.read_text())
    assert data["enabledPlugins"] == {"harness-maker@local": True}, "Claude-owned key clobbered"
    cmds = _commands(data)
    assert "/usr/local/bin/mine.sh" in cmds, "user hook wiped by re-render"
    assert any("harness_maker.telemetry" in c for c in cmds), "template hook not merged in"
    assert isinstance(data["permissions"]["deny"], list), "permissions regressed"
