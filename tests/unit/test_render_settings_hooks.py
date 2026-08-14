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
    _CODEX_HOOKS_ALLOWED_TOP_LEVEL,
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
# Codex strict top-level schema
# ──────────────────────────────────────────────────────────────────────────


def test_merge_prunes_stale_preset_key_for_codex() -> None:
    """Codex rejects the WHOLE file on an unknown top-level key.

    harness-maker shipped `"preset"` into `.codex/hooks.json` through 0.51.1, so
    Codex reported "unknown field preset, expected description or hooks"
    and every hook in it was dead. Dropping the key from the template is NOT
    enough — top-level merge is existing-survives-when-template-is-silent, so the
    stale key on the user's disk would outlive the template fix forever.
    """
    hm = "uv run --with /p python -m harness_maker.telemetry"
    existing = {
        "preset": "Side",
        "hooks": {"PostToolUse": [_nested("*", hm), _nested("*", "/usr/local/bin/mine.sh")]},
    }
    new = {"hooks": {"PostToolUse": [_nested("*", hm)]}}
    merged = _merge_hooks_json(
        existing, new, schema="nested", allowed_top_level=_CODEX_HOOKS_ALLOWED_TOP_LEVEL
    )
    assert set(merged) <= {"description", "hooks"}, f"unknown top-level key survived: {set(merged)}"
    cmds = [h["command"] for e in merged["hooks"]["PostToolUse"] for h in e["hooks"]]
    assert "/usr/local/bin/mine.sh" in cmds, "pruning must not cost the user their hooks"


def test_merge_keeps_top_level_keys_when_no_allowlist_given() -> None:
    """The prune is opt-in per consumer — Cursor's `"version": 1` must still survive."""
    existing = {"version": 1, "hooks": {"postToolUse": [_flat("*", "/usr/local/bin/mine.sh")]}}
    new: dict[str, Any] = {"hooks": {"postToolUse": []}}
    merged = _merge_hooks_json(existing, new, schema="flat")
    assert merged["version"] == 1


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


# ---------------------------------------------------------------------------
# PLAN-render-degrades-live-harness Phase 2 — ADR-003 / ADR-004 / ADR-005.
#
# A user who wraps a harness command in their own matcher (to exempt `projects/`,
# say) had that command STRIPPED out of their entry while the template's bare entry
# was reinstated — Claude Code runs every matching hook, so the exemption stopped
# existing. `_strip_shipped_commands` matched on the command alone and never looked
# at the matcher.
#
# ADR-003: ownership is decided by the MIXED-GROUP evidence, not by a matcher
# difference. There is no provenance at merge time (the manifest stores
# {path, content_hash, timestamp}), so "different matcher" cannot distinguish
# "the user re-scoped it" from "harness-maker's own matcher changed between
# releases" — and under the second reading the gate would silently revert to the
# previous release's matcher.
# ---------------------------------------------------------------------------

_GATE = "uv run --with /p python -m harness_maker.gates.spec_gate"
_PERM = "uv run --with /p python -m harness_maker.gates.permission_gate"
_USER = "/usr/local/bin/my-own-check.sh"


def _cmds(entry: dict[str, Any]) -> list[str]:
    return [h["command"] for h in entry["hooks"]]


def test_a_mixed_group_keeps_its_harness_command() -> None:
    """ADR-003. The user appended their own command beside ours under a narrow
    matcher — that group is theirs, and our command stays inside it."""
    existing = {"hooks": {"PreToolUse": [_nested("Edit", _GATE, _USER)]}}
    new = {"hooks": {"PreToolUse": [_nested("Write|Edit", _GATE)]}}
    merged = _merge_hooks_json(existing, new, schema="nested")
    user_groups = [e for e in merged["hooks"]["PreToolUse"] if e["matcher"] == "Edit"]
    assert user_groups, "the user's scoped group was dropped entirely"
    assert _GATE in _cmds(user_groups[0]), "the harness command was stripped from a MIXED group"
    assert _USER in _cmds(user_groups[0])


def test_the_template_drops_only_the_scoped_command_keeping_siblings() -> None:
    """ADR-004, command-level. Entry-level removal would take `permission_gate` with
    it — a co-located command the user never scoped."""
    existing = {"hooks": {"PreToolUse": [_nested("Edit", _GATE, _USER)]}}
    new = {"hooks": {"PreToolUse": [_nested("Write|Edit", _PERM, _GATE)]}}
    merged = _merge_hooks_json(existing, new, schema="nested")
    template = [e for e in merged["hooks"]["PreToolUse"] if e["matcher"] == "Write|Edit"]
    assert template, "the template group vanished — siblings were dropped with the scoped command"
    assert _cmds(template[0]) == [_PERM], (
        "the template must keep its siblings and drop only the scoped command; "
        f"got {_cmds(template[0])}"
    )


def test_a_template_entry_left_empty_is_not_emitted() -> None:
    """ADR-004's tail: a group whose only command was scoped away registers nothing."""
    existing = {"hooks": {"PreToolUse": [_nested("Edit", _GATE, _USER)]}}
    new = {"hooks": {"PreToolUse": [_nested("Write|Edit", _GATE)]}}
    merged = _merge_hooks_json(existing, new, schema="nested")
    assert all(e["matcher"] != "Write|Edit" for e in merged["hooks"]["PreToolUse"]), (
        "an emptied template group was still emitted"
    )


def test_no_tool_is_gated_twice_by_the_scoped_command() -> None:
    """The whole point, restated for ADR-011: what must not happen is a TOOL being
    gated twice, not a command appearing in two entries.

    The count assertion this replaces (`total == 1`) encoded ADR-008's original
    all-or-nothing suppression. Under ADR-011 the template keeps the residual `Write`
    while the user's entry owns `Edit`: two registrations, disjoint matchers, no tool
    double-gated — and, unlike a plain drop, `Write` is still covered.
    """
    existing = {"hooks": {"PreToolUse": [_nested("Edit", _GATE, _USER)]}}
    new = {"hooks": {"PreToolUse": [_nested("Write|Edit", _GATE)]}}
    merged = _merge_hooks_json(existing, new, schema="nested")
    carrying = [
        set(e["matcher"].split("|")) for e in merged["hooks"]["PreToolUse"] if _GATE in _cmds(e)
    ]
    assert carrying, "the gate disappeared entirely"
    covered: set[str] = set()
    for terms in carrying:
        assert not (terms & covered), f"a tool is gated twice: {terms & covered}"
        covered |= terms
    assert covered == {"Write", "Edit"}, f"coverage changed; got {covered}"


def test_a_pure_harness_entry_under_a_different_matcher_is_still_stripped() -> None:
    """ADR-003's stated COST, pinned so it stays visible.

    A group holding only our commands is indistinguishable from our own older entry
    — which is exactly the case where preserving it would silently revert the gate to
    the previous release's matcher. The user's remedy is to keep a second command in
    the group; the alternative needs manifest provenance.
    """
    existing = {"hooks": {"PreToolUse": [_nested("Edit", _GATE)]}}
    new = {"hooks": {"PreToolUse": [_nested("Write|Edit", _GATE)]}}
    merged = _merge_hooks_json(existing, new, schema="nested")
    assert all(e["matcher"] != "Edit" for e in merged["hooks"]["PreToolUse"]), (
        "a pure-harness group was preserved — that is the unsound branch ADR-003 rejects"
    )
    template = [e for e in merged["hooks"]["PreToolUse"] if e["matcher"] == "Write|Edit"]
    assert template, "the template entry must still ship it"
    assert _GATE in _cmds(template[0]), "the template entry must still ship it"


def test_a_retired_command_is_removed_even_from_a_mixed_group() -> None:
    """ADR-005. A retired command has NO template matcher, so the ownership rule
    cannot apply to it — retirement stays unconditional, and it is the one case where
    provenance is positive by construction (a curated list)."""
    retired = next(iter(_HARNESS_RETIRED_HOOK_INVOCATIONS))
    existing = {"hooks": {"PreToolUse": [_nested("Edit", retired, _USER)]}}
    new = {"hooks": {"PreToolUse": [_nested("Write|Edit", _GATE)]}}
    merged = _merge_hooks_json(existing, new, schema="nested")
    for entry in merged["hooks"]["PreToolUse"]:
        assert retired not in _cmds(entry), "a retired invocation survived inside a mixed group"
    user_groups = [e for e in merged["hooks"]["PreToolUse"] if e["matcher"] == "Edit"]
    assert user_groups, "the user's own command was lost with it"
    assert _USER in _cmds(user_groups[0]), "the user's own command was lost with it"


def test_a_users_own_command_is_never_removed() -> None:
    """The narrow-filter invariant — only `<HM>:`-normalized commands may be stripped."""
    existing = {"hooks": {"PreToolUse": [_nested("Edit", _USER)]}}
    new = {"hooks": {"PreToolUse": [_nested("Write|Edit", _GATE)]}}
    merged = _merge_hooks_json(existing, new, schema="nested")
    user_groups = [e for e in merged["hooks"]["PreToolUse"] if e["matcher"] == "Edit"]
    assert user_groups
    assert _cmds(user_groups[0]) == [_USER]


# ---------------------------------------------------------------------------
# Phase 2b — ADR-006. Flat (Cursor) suppression.
#
# `_strip_shipped_commands` returns flat entries unchanged, and flat identity is
# (matcher, command, ""), so a user's re-scoped flat entry ALREADY survives on
# identity alone — ADR-003 is a structural no-op here. What is missing is ADR-004's
# double-fire suppression: without it Cursor registers the command twice, once under
# the user's narrow matcher and once under ours.
# ---------------------------------------------------------------------------


def test_flat_a_rescoped_user_entry_survives() -> None:
    """Baseline for the schema — identity alone already preserves it."""
    existing = {"hooks": {"beforeShellExecution": [_flat("Edit", _GATE)]}}
    new = {"hooks": {"beforeShellExecution": [_flat("*", _GATE)]}}
    merged = _merge_hooks_json(existing, new, schema="flat")
    assert any(e["matcher"] == "Edit" for e in merged["hooks"]["beforeShellExecution"]), (
        "the user's scoped flat entry was dropped"
    )


def test_flat_the_template_entry_still_ships_and_is_allowed_to_double_fire() -> None:
    """ADR-009 SUPERSEDES ADR-006 — this assertion is INVERTED on purpose.

    It used to assert the template's entry was suppressed. ADR-006 justified that on
    "a re-scoped flat entry already survives on identity, so ADR-003 is a no-op here" —
    true of PRESERVATION, false of SUPPRESSION. A flat entry holds one command, so the
    mixed-group evidence ADR-003 depends on is *structurally unavailable*, leaving only
    the matcher-difference inference ADR-003 was rewritten to reject: if harness-maker
    changes a flat matcher between releases, the on-disk entry suppresses the new one and
    Cursor runs the previous release's matcher forever, silently.

    So Cursor double-fires until manifest provenance lands. That is the accepted cost —
    a duplicate is visible and harmless, a version-lock is neither. Kept as a live
    assertion rather than deleted, because a deleted test is how ADR-006 gets re-derived
    as a missing feature.
    """
    existing = {"hooks": {"beforeShellExecution": [_flat("Edit", _GATE)]}}
    new = {"hooks": {"beforeShellExecution": [_flat("*", _GATE)]}}
    merged = _merge_hooks_json(existing, new, schema="flat")
    matchers = [e["matcher"] for e in merged["hooks"]["beforeShellExecution"]]
    assert "*" in matchers, (
        "the template's entry must still ship — ADR-009 withdrew flat suppression"
    )
    assert "Edit" in matchers, "the user's scoped entry must still survive on identity"


def test_flat_an_unscoped_template_entry_is_untouched() -> None:
    """No user entry for that command → the template ships it exactly as before."""
    existing = {"hooks": {"beforeShellExecution": [_flat("Edit", _USER)]}}
    new = {"hooks": {"beforeShellExecution": [_flat("*", _GATE)]}}
    merged = _merge_hooks_json(existing, new, schema="flat")
    assert any(
        e["matcher"] == "*" and e["command"] == _GATE
        for e in merged["hooks"]["beforeShellExecution"]
    )


# ---------------------------------------------------------------------------
# Phase 4 — REVIEW round 1 remediation. ADR-007 (refresh before suppressing) and
# ADR-008 (suppression is matcher-aware, and abstains when ambiguous).
#
# Round 1 reproduced two defects in what Phase 2 shipped:
#   * a preserved mixed group kept its BAKED `uv run --with <path>` while the
#     template's fresh-path copy was deleted, so a pruned plugin-cache dir froze a
#     dead blocking gate that no re-render could repair;
#   * `user_scoped` was a flat per-event set applied to EVERY template entry, so
#     scoping PreCompact's `auto` emptied the untouched `manual` entry.
# ---------------------------------------------------------------------------

_STALE = 'uv run --with "$HOME/.cache/hm/0.43.3" python -m harness_maker.gates.spec_gate'
_FRESH = 'uv run --with "$HOME/.cache/hm/0.51.3" python -m harness_maker.gates.spec_gate'
_FLUSH = "uv run --with /p python -m harness_maker.hooks.flush_session"
_SPAN = "uv run --with /p python -m harness_maker.worktree span-end"


def test_a_preserved_command_is_refreshed_to_the_templates_text() -> None:
    """ADR-007. The user's matcher survives; the STALE ref does not.

    `_normalize_hm_managed_command` elides the `--with` prefix for identity, so without
    the refresh the user's dead-path copy wins and ADR-004 deletes the only working one.
    """
    existing = {"hooks": {"PreToolUse": [_nested("Edit", _STALE, _USER)]}}
    new = {"hooks": {"PreToolUse": [_nested("Write|Edit", _FRESH)]}}
    merged = _merge_hooks_json(existing, new, schema="nested")
    user = [e for e in merged["hooks"]["PreToolUse"] if e["matcher"] == "Edit"]
    assert user, "the user's scoped group was dropped"
    cmds = _cmds(user[0])
    assert _FRESH in cmds, f"the stale ref was not refreshed to the template's text; got {cmds}"
    assert _STALE not in cmds, "the stale `--with` survived — a pruned cache dir kills the gate"
    assert _USER in cmds, "the user's own command was disturbed"


def test_no_stale_ref_survives_anywhere_in_the_merged_output() -> None:
    """The whole-file invariant behind ADR-007 — a re-render leaves nothing pointing
    at the pruned cache, in the user's entry or the template's."""
    existing = {"hooks": {"PreToolUse": [_nested("Edit", _STALE, _USER)]}}
    new = {"hooks": {"PreToolUse": [_nested("Write|Edit", _FRESH)]}}
    merged = _merge_hooks_json(existing, new, schema="nested")
    every = [c for e in merged["hooks"]["PreToolUse"] for c in _cmds(e)]
    assert _STALE not in every, f"a stale invocation survived the merge: {every}"


def test_scoping_one_matcher_leaves_the_sibling_entry_intact() -> None:
    """ADR-008 branch 1, against the real PreCompact shape.

    `Production.json.j2` ships flush_session + span-end under BOTH `auto` and `manual`.
    Event-global suppression emptied `manual`, which was then not emitted at all.
    """
    existing = {"hooks": {"PreCompact": [_nested("auto", _FLUSH, _USER)]}}
    new = {
        "hooks": {"PreCompact": [_nested("auto", _FLUSH, _SPAN), _nested("manual", _FLUSH, _SPAN)]}
    }
    merged = _merge_hooks_json(existing, new, schema="nested")
    manual = [e for e in merged["hooks"]["PreCompact"] if e["matcher"] == "manual"]
    assert manual, "the untouched `manual` entry was emptied and dropped"
    assert _cmds(manual[0]) == [_FLUSH, _SPAN], (
        f"`manual` lost a command the user never scoped; got {_cmds(manual[0])}"
    )
    auto_tmpl = [
        e for e in merged["hooks"]["PreCompact"] if e["matcher"] == "auto" and _USER not in _cmds(e)
    ]
    assert auto_tmpl, "the template's `auto` entry vanished entirely"
    assert _cmds(auto_tmpl[0]) == [_SPAN], (
        "the entry the user DID scope must still give the command up"
    )


def test_the_template_keeps_the_residual_matcher_when_the_user_narrows() -> None:
    """ADR-011, the load-bearing case. This is the defect round 2 found in round 2's
    own fix: ADR-008's branch 2 dropped the command outright, so a user whose `/hooks`
    group carried a PREVIOUS release's matcher pinned the gate to it forever — widening
    `Write|Edit` to `Write|Edit|MultiEdit` left MultiEdit permanently ungated, silently.
    """
    existing = {"hooks": {"PreToolUse": [_nested("Write|Edit", _FRESH, _USER)]}}
    # `timeout` mirrors the real templates (Production.json.j2 carries it on every
    # blocking gate) — the residual entry must not quietly drop per-hook metadata.
    new = {
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": "Write|Edit|MultiEdit",
                    "hooks": [
                        {"type": "command", "command": _PERM, "timeout": 10},
                        {"type": "command", "command": _FRESH, "timeout": 10},
                    ],
                }
            ]
        }
    }
    merged = _merge_hooks_json(existing, new, schema="nested")
    gated = {
        t
        for e in merged["hooks"]["PreToolUse"]
        if _FRESH in _cmds(e)
        for t in e["matcher"].split("|")
    }
    assert "MultiEdit" in gated, f"MultiEdit lost its gate — ADR-011 regressed; got {gated}"
    assert gated == {"Write", "Edit", "MultiEdit"}, f"coverage changed; got {gated}"
    residual = [e for e in merged["hooks"]["PreToolUse"] if e["matcher"] == "MultiEdit"]
    assert residual, "no residual entry was emitted"
    assert _cmds(residual[0]) == [_FRESH], "the residual entry took a sibling with it"
    assert residual[0]["hooks"][0].get("timeout") == 10, (
        "the residual entry dropped per-hook metadata"
    )
    full = [e for e in merged["hooks"]["PreToolUse"] if e["matcher"] == "Write|Edit|MultiEdit"]
    assert full, "the template's full-matcher entry vanished"
    assert _cmds(full[0]) == [_PERM], "the un-scoped sibling lost its full matcher"


def test_an_ambiguous_multi_matcher_scope_suppresses_nothing_and_warns(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """ADR-008 branch 3. Several template homes → which entry the user meant is not
    derivable, so nothing is suppressed. The bias is one-directional: a duplicate
    announces itself, a deletion is silent.

    The user's `Edit` OVERLAPS the template's `Write|Edit`, so this really is a
    double-fire and the warning must name it. The earlier version of this test used a
    `Custom` matcher against `auto`/`manual` — disjoint sets, so no tool could ever be
    gated twice and the "missing" warning was correct behaviour, not a defect.
    """
    existing = {"hooks": {"PreToolUse": [_nested("Edit", _GATE, _USER)]}}
    new = {"hooks": {"PreToolUse": [_nested("Write|Edit", _GATE), _nested("Bash", _GATE)]}}
    merged = _merge_hooks_json(existing, new, schema="nested")
    for m in ("Write|Edit", "Bash"):
        entry = [e for e in merged["hooks"]["PreToolUse"] if e["matcher"] == m]
        assert entry, f"{m} entry vanished under ambiguity"
        assert _GATE in _cmds(entry[0]), f"{m} lost the command under ambiguity"
    err = capsys.readouterr().err
    assert "registered twice" in err, f"no double-fire warning; got {err!r}"
    assert "'Write|Edit'" in err, f"the warning does not name the template matcher; got {err!r}"
    assert "'Edit'" in err, f"the warning does not name the user matcher; got {err!r}"


def test_disjoint_matchers_are_not_warned_about(capsys: pytest.CaptureFixture[str]) -> None:
    """The corollary that keeps the warning honest. `Custom` and `auto`/`manual` cannot
    match the same tool, so nothing fires twice and there is nothing to say. A warning
    keyed on 'was it suppressed?' rather than 'can both fire?' would cry wolf here — and
    a diagnostic that cries wolf is one the next reader learns to ignore."""
    existing = {"hooks": {"PreCompact": [_nested("Custom", _FLUSH, _USER)]}}
    new = {
        "hooks": {"PreCompact": [_nested("auto", _FLUSH, _SPAN), _nested("manual", _FLUSH, _SPAN)]}
    }
    _merge_hooks_json(existing, new, schema="nested")
    assert capsys.readouterr().err == "", "warned about matchers that cannot both fire"


def test_the_warning_does_not_fire_when_the_command_was_suppressed_somewhere(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The warning must describe what happened. A first cut derived it from the branch-3
    fall-through, so it announced 'not suppressing' for a command branch 1 had already
    suppressed on another entry of the same event — a diagnostic that lies is worse than
    none, because the next reader trusts it."""
    existing = {"hooks": {"PreCompact": [_nested("auto", _FLUSH, _USER)]}}
    new = {
        "hooks": {"PreCompact": [_nested("auto", _FLUSH, _SPAN), _nested("manual", _FLUSH, _SPAN)]}
    }
    _merge_hooks_json(existing, new, schema="nested")
    assert "not suppressing" not in capsys.readouterr().err


def test_the_merge_converges_after_one_render() -> None:
    """Re-render idempotency. Round 1's suppression was byte-stable, which is what made
    the frozen stale ref PERMANENT — stability is only a virtue once the fixed point is
    the right one, so it is asserted here against the repaired output."""
    template = {"hooks": {"PreToolUse": [_nested("Write|Edit", _PERM, _FRESH)]}}
    current: dict[str, Any] = {"hooks": {"PreToolUse": [_nested("Edit", _STALE, _USER)]}}
    seen = []
    for _ in range(3):
        current = _merge_hooks_json(current, template, schema="nested")
        seen.append([(e["matcher"], _cmds(e)) for e in current["hooks"]["PreToolUse"]])
    assert seen[1] == seen[2], f"the merge never reaches a fixed point: {seen[1]} vs {seen[2]}"
    assert all(_STALE not in c for _, cmds in seen[2] for c in cmds), "stale ref reappeared"


# ---------------------------------------------------------------------------
# Cursor / Claude gate-matcher parity.
#
# `.cursor/hooks.json` has NO frozen-baseline and NO snapshot coverage — `grep -c
# cursor/hooks tests/structural/surface_baseline.json` returns 0 — which is how it
# came to ship `spec_gate` under `Write|Edit` while both settings templates used
# `Write|Edit|MultiEdit`. Cursor users' MultiEdit writes were simply not spec-gated,
# and the only record of it was a Production.json.j2 comment describing the divergence
# as intentional. It was not; it was the earlier mistake, uncorrected on one side.
# ---------------------------------------------------------------------------


def _gate_matchers(template: str, module: str, event: str, **cfg: Any) -> list[str]:
    """Matchers a template registers `module` under, for one event, either schema."""
    config = HarnessConfig(**cfg).model_dump(mode="json")
    rendered = json.loads(
        _make_env()
        .get_template(template)
        .render(preset="Side", config=config, harness_maker_src_path="/fake/src/path")
    )
    out: list[str] = []
    for entry in rendered.get("hooks", {}).get(event, []):
        cmds = (
            [entry["command"]]
            if "command" in entry
            else [h["command"] for h in entry.get("hooks", [])]
        )
        if any(module in c for c in cmds):
            out.append(entry.get("matcher", ""))
    return out


@pytest.mark.parametrize("module", sorted({*_BLOCKING_GATE_MODULES}))
def test_cursor_and_claude_agree_on_every_blocking_gate_matcher(module: str) -> None:
    """A gate that guards fewer tools on one IDE than the other is a silent hole.

    Both files are rendered from the same `dev_mode`, so a matcher difference is never a
    deliberate per-IDE policy — it is one side not being updated with the other. Claude's
    `PreToolUse` and Cursor's `preToolUse` are the same stage under each IDE's own schema.
    """
    claude = _gate_matchers(
        "settings/Production.json.j2", module, "PreToolUse", dev_mode=DevMode.SPEC_DRIVEN
    )
    cursor = _gate_matchers(
        "cursor/hooks.json.j2", module, "preToolUse", dev_mode=DevMode.SPEC_DRIVEN
    )
    if not claude or not cursor:
        pytest.skip(f"{module} is not wired on both IDEs — coverage parity is a separate claim")
    assert set(claude) == set(cursor), (
        f"{module}: Claude gates {claude} but Cursor gates {cursor}. A gate guarding fewer "
        "tools on one IDE is a silent hole — align the templates, or state the reason here."
    )


# ---------------------------------------------------------------------------
# Phase 5 — ADR-014 / ADR-015 / ADR-016. REVIEW round 2 remediation.
#
# ADR-016 is the reported incident, identified only at round 2: a Claude Code hook
# `matcher` matches TOOL NAMES, so a `projects/` path exemption cannot be expressed in
# one. The user's "scope wrapper" was an ARGUMENT — `spec_gate --exempt projects/` —
# and trailing args are part of the normalized identity, so the identity-keyed rule
# never saw their variant as ours and the template's bare copy kept firing beside it.
# ---------------------------------------------------------------------------

_PREFIX = 'CLAUDE_PROJECT_DIR="$X" PATH="$HOME/.local/bin:$PATH" '
_SCOPED = (
    _PREFIX + 'uv run --with "/old" python -m harness_maker.gates.spec_gate --exempt projects/'
)
_BARE = 'uv run --with "/new" python -m harness_maker.gates.spec_gate'
_PERM_NEW = 'uv run --with "/new" python -m harness_maker.gates.permission_gate'


def _flat_cmd(ref: str, module: str, args: str = "") -> str:
    return f'{_PREFIX}uv run --with "{ref}" python -m harness_maker.{module}{args}'


def test_an_argument_scoped_wrapper_suppresses_the_templates_bare_copy() -> None:
    """ADR-016 — THE reported incident, pinned.

    "a re-render re-added a bare `spec_gate` beside the scope wrapper and defeated the
    `projects/` exemption." Both fired, so the exemption bought nothing. Identity keying
    could never fix this: the user's variant and the template's differ by the argument
    that IS the scoping.
    """
    existing = {"hooks": {"PreToolUse": [_nested("Write|Edit", _SCOPED, _USER)]}}
    new = {"hooks": {"PreToolUse": [_nested("Write|Edit", _PERM_NEW, _BARE)]}}
    merged = _merge_hooks_json(existing, new, schema="nested")
    every = [c for e in merged["hooks"]["PreToolUse"] for c in _cmds(e)]
    gates = [c for c in every if "spec_gate" in c]
    assert len(gates) == 1, f"spec_gate registered {len(gates)}x — the exemption is defeated"
    assert "--exempt projects/" in gates[0], "the surviving copy is the UNSCOPED one"
    assert any("permission_gate" in c for c in every), "a co-located sibling was dropped with it"
    assert _USER in every, "the user's own command was dropped"


def test_the_refresh_preserves_a_user_prefix_and_trailing_arguments() -> None:
    """ADR-014. Only the ref is stale, so only the ref is replaced.

    Replacing the whole command — ADR-007's first mechanism — discarded the user's env
    prefix and never fired at all for an arg-bearing command, which is exactly the
    population whose ref most needs refreshing.
    """
    existing = {"hooks": {"PreToolUse": [_nested("Write|Edit", _SCOPED, _USER)]}}
    new = {"hooks": {"PreToolUse": [_nested("Write|Edit", _BARE)]}}
    merged = _merge_hooks_json(existing, new, schema="nested")
    gate = next(c for e in merged["hooks"]["PreToolUse"] for c in _cmds(e) if "spec_gate" in c)
    assert '--with "/new"' in gate, f"the stale ref was not refreshed; got {gate}"
    assert '--with "/old"' not in gate, "the stale ref survived"
    assert gate.startswith(_PREFIX), f"the user's env prefix was discarded; got {gate}"
    assert gate.endswith("--exempt projects/"), f"the user's argument was discarded; got {gate}"


def test_flat_a_matcher_change_ships_the_residual_and_refreshes_the_ref() -> None:
    """ADR-015. The realistic Cursor route: harness-maker changes its OWN flat matcher.

    ADR-009 had withdrawn flat suppression because the only action was delete-or-not.
    ADR-011 added subtraction, so the on-disk entry keeps `Write|Edit`, the template
    ships the residual `MultiEdit`, and nothing fires twice — while the preserved entry's
    pruned `--with`, which ADR-009 left in place as "harmless", is repaired.
    """
    old = _flat_cmd("/old", "gates.spec_gate")
    new_cmd = _flat_cmd("/new", "gates.spec_gate")
    existing = {"hooks": {"preToolUse": [{"matcher": "Write|Edit", "command": old}]}}
    new = {"hooks": {"preToolUse": [{"matcher": "Write|Edit|MultiEdit", "command": new_cmd}]}}
    merged = _merge_hooks_json(existing, new, schema="flat")
    entries = merged["hooks"]["preToolUse"]
    covered: set[str] = set()
    for e in entries:
        terms = set(e["matcher"].split("|"))
        assert not (terms & covered), f"a tool is gated twice: {terms & covered}"
        covered |= terms
        assert '--with "/new"' in e["command"], f"a stale flat ref survived: {e['command']}"
    assert covered == {"Write", "Edit", "MultiEdit"}, f"coverage changed; got {covered}"


def test_flat_a_wildcard_template_matcher_emits_both_and_warns(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """ADR-015's stated limit. `*` is not a decidable term set, so it cannot be subtracted
    — the telemetry double-count survives and is warned about. Both refs are refreshed, so
    nothing is dead; only the ledger double-counts."""
    old = _flat_cmd("/old", "telemetry")
    new_cmd = _flat_cmd("/new", "telemetry")
    existing = {"hooks": {"postToolUse": [{"matcher": "Write", "command": old}]}}
    new = {"hooks": {"postToolUse": [{"matcher": "*", "command": new_cmd}]}}
    merged = _merge_hooks_json(existing, new, schema="flat")
    entries = merged["hooks"]["postToolUse"]
    assert {e["matcher"] for e in entries} == {"*", "Write"}, "an entry was suppressed under `*`"
    for e in entries:
        assert '--with "/new"' in e["command"], f"a stale flat ref survived: {e['command']}"
    assert "registered twice" in capsys.readouterr().err, "the surviving duplicate was silent"
