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

from harness_maker.models import DevMode, HarnessConfig
from harness_maker.render import (
    _HARNESS_RETIRED_HOOK_INVOCATIONS,
    _SETTINGS_KEYS_OWNED_BY_HARNESS,
    _make_env,
    _merge_hooks_json,
)

SETTINGS_TEMPLATES = ("settings/Side.json.j2", "settings/Production.json.j2")

# ADR-006 Stage 1 — non-blocking (Phase 1).
STAGE1_MODULES = frozenset(
    {
        "harness_maker.telemetry",
        "harness_maker.hooks.post_write_reminder",
        "harness_maker.hooks.sessionid_envfile",
        "harness_maker.hooks.autopilot_autoarm",
        "harness_maker.hooks.flush_session",
    }
)

# ADR-006 Stage 2 — control-flow (Phase 2), **Stop event only**. `loop_gate` is what
# lets /hm:loop reach iteration 2. Stop-blocking cannot block a tool call and is
# bounded by each module's stop_hook_active guard — worst case is one extra turn.
# `autopilot_guard` was RETIRED here (PLAN-hook-inventory-efficiency-audit ADR-002):
# it is no longer rendered on any event — see `_HARNESS_RETIRED_HOOK_INVOCATIONS`.
STAGE2_MODULES = frozenset(
    {
        "harness_maker.hooks.loop_gate",
    }
)

# ADR-006 Stage 3 — the PreToolUse BLOCKING gates, now WIRED (Phase 3 redo). Present in
# BOTH dev_modes. (`autopilot_guard`'s former PreToolUse copies were retired per
# PLAN-hook-inventory-efficiency-audit ADR-002 — no longer part of the shipped set.)
STAGE3_MODULES = frozenset(
    {
        "harness_maker.gates.permission_gate",
        "harness_maker.gates.worktree_gate",
    }
)

# spec_gate is Stage 3 too, but spec-driven dev_mode ONLY (task-driven omits it — the
# spec-gate has nothing to enforce without a SPEC). Tested dev_mode-aware, not in SHIPPED.
SPEC_DRIVEN_ONLY_MODULE = "harness_maker.gates.spec_gate"

SHIPPED_MODULES = STAGE1_MODULES | STAGE2_MODULES | STAGE3_MODULES

# The Stage-3 PreToolUse blocking gates must carry an explicit timeout, matching siblings.
_BLOCKING_GATE_MODULES = (
    "harness_maker.gates.permission_gate",
    "harness_maker.gates.worktree_gate",
    "harness_maker.gates.spec_gate",
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
def test_settings_hooks_carry_shipped_modules(template: str) -> None:
    cmds = " ".join(_commands(_render(template)))
    for mod in sorted(SHIPPED_MODULES):
        assert mod in cmds, f"{template}: shipped hook {mod} missing"


@pytest.mark.parametrize("template", SETTINGS_TEMPLATES)
@pytest.mark.parametrize("dev_mode", [DevMode.TASK_DRIVEN, DevMode.SPEC_DRIVEN])
def test_settings_stage3_gates_wired_both_dev_modes(template: str, dev_mode: DevMode) -> None:
    """Phase 3 redo: the Stage-3 PreToolUse blocking gates are wired, both dev_modes.

    The parked attempt's ABSENCE assertion is inverted — permission_gate + worktree_gate
    must now be present on PreToolUse in BOTH task-driven and spec-driven.
    """
    settings = _render(template, dev_mode=dev_mode)
    assert json.dumps(settings)  # valid JSON in this dev_mode (mirrors production shape)
    pre = settings["hooks"].get("PreToolUse")
    assert pre, f"{template} ({dev_mode.value}): no PreToolUse — Stage 3 not wired"
    cmds = " ".join(_commands(settings))
    for mod in sorted(STAGE3_MODULES):
        assert mod in cmds, f"{template} ({dev_mode.value}): Stage-3 gate {mod} missing"


@pytest.mark.parametrize("template", SETTINGS_TEMPLATES)
def test_settings_spec_gate_matcher_is_write_edit_multiedit(template: str) -> None:
    """P2: spec_gate uses `Write|Edit|MultiEdit` (NOT the parked `Write|Edit`).

    The dropped MultiEdit rested on a false premise — `_entry_identity` keys on matcher +
    EVERY command, so spec_gate's group coexists with the worktree_gate group under the
    SAME matcher. spec_gate is spec-driven ONLY; task-driven must omit it entirely.
    """
    spec = _render(template, dev_mode=DevMode.SPEC_DRIVEN)
    matchers = [
        e["matcher"]
        for e in spec["hooks"]["PreToolUse"]
        for h in e["hooks"]
        if SPEC_DRIVEN_ONLY_MODULE in h["command"]
    ]
    assert matchers == ["Write|Edit|MultiEdit"], (
        f"{template}: spec_gate matcher must be Write|Edit|MultiEdit, got {matchers}"
    )

    task = _render(template, dev_mode=DevMode.TASK_DRIVEN)
    task_cmds = " ".join(_commands(task))
    assert SPEC_DRIVEN_ONLY_MODULE not in task_cmds, (
        f"{template}: spec_gate leaked into task-driven mode"
    )


@pytest.mark.parametrize("template", SETTINGS_TEMPLATES)
@pytest.mark.parametrize("dev_mode", [DevMode.TASK_DRIVEN, DevMode.SPEC_DRIVEN])
def test_settings_stage3_blocking_gates_carry_timeout(template: str, dev_mode: DevMode) -> None:
    """P2 (also-open): the newly-wired blocking gates must carry `"timeout": 10`, like
    their loop_gate / autopilot_guard siblings. The parked code shipped them without one.
    """
    pre = _render(template, dev_mode=dev_mode)["hooks"]["PreToolUse"]
    for entry in pre:
        for h in entry["hooks"]:
            if any(mod in h["command"] for mod in _BLOCKING_GATE_MODULES):
                assert h.get("timeout") == 10, (
                    f"{template} ({dev_mode.value}): {h['command']} missing timeout: 10"
                )


@pytest.mark.parametrize("template", SETTINGS_TEMPLATES)
def test_settings_permission_gate_is_subordinate(template: str) -> None:
    """ADR-007: the Claude template's permission_gate takes --subordinate-to-deny-dangerous
    so it defers to settings.json's deny for the deny_dangerous opt-out."""
    cmds = _commands(_render(template))
    gate = [c for c in cmds if "gates.permission_gate" in c]
    assert gate, f"{template}: permission_gate not wired"
    assert all("--subordinate-to-deny-dangerous" in c for c in gate), (
        f"{template}: permission_gate must pass --subordinate-to-deny-dangerous; got {gate}"
    )


@pytest.mark.parametrize("template", SETTINGS_TEMPLATES)
def test_settings_stop_hook_carries_loop_gate_only(template: str) -> None:
    """Stage 2's point: a Stop hook is what lets `/hm:loop` reach iteration 2.

    `autopilot_guard`'s Stop copy was RETIRED (PLAN-hook-inventory-efficiency-audit
    ADR-002 — the Stop-block was the user's friction), so `loop_gate` is now the sole
    Stop hook. It must still pass `--mode stop-hook` (the module dispatches on it).
    """
    stop = _render(template)["hooks"].get("Stop")
    assert stop, f"{template}: no Stop hook — loop_gate cannot block"
    assert len(stop) == 1, f"{template}: Stop must be ONE group, got {len(stop)}"
    cmds = [h["command"] for e in stop for h in e["hooks"]]
    loop = [c for c in cmds if "harness_maker.hooks.loop_gate" in c]
    assert loop, f"{template}: Stop is missing loop_gate"
    assert all("--mode stop-hook" in c for c in loop), (
        f"{template}: loop_gate on Stop must pass --mode stop-hook; got {loop}"
    )
    assert not any("autopilot_guard" in c for c in cmds), (
        f"{template}: autopilot_guard must be RETIRED from Stop; got {cmds}"
    )


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
    # Both must be modules the template genuinely does NOT ship, or the docstring's
    # claim is false: `autopilot_guard` is shipped on Stop as of Phase 2, so it cannot
    # stand in for "an all-harness group the template does not ship" (code-reviewer P2).
    gate = "uv run --with /p python -m harness_maker.gates.spec_gate"
    guard = "uv run --with /p python -m harness_maker.gates.worktree_gate"
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


def test_merge_group_growth_neither_duplicates_nor_loses() -> None:
    """A matcher group that GROWS across a re-render must dedup, not linger/duplicate.

    On-disk PreToolUse/Bash is `[worktree_gate]`; a later template grows that SAME
    matcher group to `[permission_gate, worktree_gate]`. All-commands identity means the
    two groups have DIFFERENT identities, so the on-disk one is not deduped by the
    identity check — and there is no retire rule for these live hooks. `_strip_shipped_commands`
    is the only thing standing between this and either a hook firing twice or the group
    lingering forever. Both fixtures are STILL-SHIPPED hooks (the retired autopilot_guard
    can no longer stand in here — see `test_merge_retires_autopilot_guard_when_template_drops_it`).

    `_normalize_hm_managed_command` keys identity on module **plus trailing args**, so
    `gate` carries `--subordinate-to-deny-dangerous` to model what the template ships.
    """
    grown = "uv run --with /p python -m harness_maker.gates.worktree_gate"
    gate = (
        "uv run --with /p python -m harness_maker.gates.permission_gate "
        "--subordinate-to-deny-dangerous"
    )

    old_on_disk = {"hooks": {"PreToolUse": [_nested("Bash", grown)]}}
    grown_template = {"hooks": {"PreToolUse": [_nested("Bash", gate, grown)]}}

    merged = _merge_hooks_json(old_on_disk, grown_template, schema="nested")
    cmds = [h["command"] for e in merged["hooks"]["PreToolUse"] for h in e["hooks"]]
    assert cmds.count(grown) == 1, f"worktree_gate duplicated across the group growth: {cmds}"
    assert cmds.count(gate) == 1, f"permission_gate missing or duplicated: {cmds}"
    groups = merged["hooks"]["PreToolUse"]
    assert len(groups) == 1, f"superseded smaller group lingered beside the grown one: {groups}"


def test_merge_group_growth_keeps_a_user_command_in_the_grown_group() -> None:
    """The same group growth, with a user command appended into our group.

    Claude Code's `/hooks` UI appends into an existing matcher group, so a user who
    added their own PreToolUse/Bash command must keep it when the template grows the
    group — and must not collect a duplicate of the still-shipped hook either.
    """
    grown = "uv run --with /p python -m harness_maker.gates.worktree_gate"
    gate = "uv run --with /p python -m harness_maker.gates.permission_gate"
    mine = "/usr/local/bin/my-audit.sh"

    on_disk = {"hooks": {"PreToolUse": [_nested("Bash", grown, mine)]}}
    grown_template = {"hooks": {"PreToolUse": [_nested("Bash", gate, grown)]}}

    merged = _merge_hooks_json(on_disk, grown_template, schema="nested")
    cmds = [h["command"] for e in merged["hooks"]["PreToolUse"] for h in e["hooks"]]
    assert mine in cmds, f"user command lost across the group growth: {cmds}"
    assert cmds.count(grown) == 1, f"worktree_gate duplicated: {cmds}"
    assert cmds.count(gate) == 1, f"permission_gate missing or duplicated: {cmds}"


# ──────────────────────────────────────────────────────────────────────────
# Retirement (PLAN-hook-inventory-efficiency-audit ADR-001)
# ──────────────────────────────────────────────────────────────────────────


def test_merge_retires_autopilot_guard_when_template_drops_it() -> None:
    """ADR-001: autopilot_guard is a RETIRED hook. A settings.json still carrying it
    (as pseudo-user content after the template stops shipping it) must lose it on the
    next merge, while its still-shipped sibling in the SAME group survives.

    Without the retired-set strip, the union-merge preserves the guard forever — this
    is the whole point of the mechanism (every existing harness self-cleans on re-render).
    """
    gate = (
        "uv run --with /p python -m harness_maker.gates.permission_gate "
        "--subordinate-to-deny-dangerous"
    )
    guard = "uv run --with /p python -m harness_maker.hooks.autopilot_guard"
    on_disk = {"hooks": {"PreToolUse": [_nested("Bash", gate, guard)]}}
    new = {"hooks": {"PreToolUse": [_nested("Bash", gate)]}}  # template no longer ships guard
    merged = _merge_hooks_json(on_disk, new, schema="nested")
    cmds = [h["command"] for e in merged["hooks"]["PreToolUse"] for h in e["hooks"]]
    assert guard not in cmds, "retired autopilot_guard survived the merge"
    assert cmds.count(gate) == 1, "still-shipped permission_gate must remain exactly once"


def test_merge_retires_autopilot_guard_stop_mode() -> None:
    """The Stop-mode invocation (`--mode stop-hook`) is a DISTINCT retired entry — its
    normalized identity carries the trailing arg, so it needs its own set member."""
    loop = "uv run --with /p python -m harness_maker.hooks.loop_gate --mode stop-hook"
    guard = "uv run --with /p python -m harness_maker.hooks.autopilot_guard --mode stop-hook"
    on_disk = {"hooks": {"Stop": [_nested("", loop, guard)]}}
    new = {"hooks": {"Stop": [_nested("", loop)]}}
    merged = _merge_hooks_json(on_disk, new, schema="nested")
    cmds = [h["command"] for e in merged["hooks"]["Stop"] for h in e["hooks"]]
    assert guard not in cmds, "retired autopilot_guard (stop-hook) survived the merge"
    assert cmds.count(loop) == 1, "still-shipped loop_gate must remain exactly once"


def test_merge_retirement_preserves_a_users_appended_command() -> None:
    """Retiring the guard from a MIXED group must keep the user's own command.

    `[permission_gate, autopilot_guard, user.sh]` → `[permission_gate, user.sh]`.
    """
    gate = "uv run --with /p python -m harness_maker.gates.permission_gate"
    guard = "uv run --with /p python -m harness_maker.hooks.autopilot_guard"
    mine = "/usr/local/bin/my-audit.sh"
    on_disk = {"hooks": {"PreToolUse": [_nested("Bash", gate, guard, mine)]}}
    new = {"hooks": {"PreToolUse": [_nested("Bash", gate)]}}
    merged = _merge_hooks_json(on_disk, new, schema="nested")
    cmds = [h["command"] for e in merged["hooks"]["PreToolUse"] for h in e["hooks"]]
    assert guard not in cmds, "retired guard survived"
    assert mine in cmds, "user's own command dropped alongside the retired guard"
    assert cmds.count(gate) == 1


@pytest.mark.parametrize("template", [*SETTINGS_TEMPLATES, "codex/hooks.json.j2"])
def test_retired_invocations_absent_from_current_templates(template: str) -> None:
    """ADR-001 safety invariant: NEVER retire something a template still ships.

    This is the ONE invariant bounding `_HARNESS_RETIRED_HOOK_INVOCATIONS` membership
    (unlike the deny-literal set, there is no "provably enforces nothing" second
    invariant for a live hook). `_strip_shipped_commands` applies the retired set to
    EVERY nested-schema merge — settings.json AND `.codex/hooks.json` (both routed
    through `_merge_hooks_json(schema="nested")`) — so the invariant must hold for the
    codex hook template too, not just settings (REVIEW P2, 2026-07-21). Cursor's
    `.cursor/hooks.json` is FLAT-schema and the retirement path skips flat entirely, so
    it needs no check here. Every retired invocation must be absent from every current
    nested hook template's rendered output — in BOTH dev_modes.
    """
    for dev_mode in (DevMode.TASK_DRIVEN, DevMode.SPEC_DRIVEN):
        cmds = " ".join(_commands(_render(template, dev_mode=dev_mode)))
        for retired in _HARNESS_RETIRED_HOOK_INVOCATIONS:
            invocation = retired.removeprefix("<HM>:")
            assert f"python -m {invocation}" not in cmds, (
                f"{template} ({dev_mode.value}) still ships a RETIRED invocation: {invocation}"
            )


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
