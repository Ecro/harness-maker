"""Regression guard for permission-rule syntax that can never match (Phase 8).

Three of the four deny rules harness-maker shipped through 0.39.0 used syntax
Claude Code accepts but never matches, so they silently enforced nothing:

  - `Write(<path>)` — only `Edit`/`Read` are consulted by the file-permission
    check; `Write`/`NotebookEdit`/`Glob` with a path arg warn at startup.
  - `Bash(curl * | sh)` — Bash rules are matched per-subcommand after splitting
    on separators, so a rule spanning `|` can never match. This one fails
    *silently* (no startup warning), which is why it survived 39 releases.

The suite asserts the property (no unmatchable rule is rendered) rather than
pinning literals, so a future template edit that reintroduces the shape fails
here instead of on a user's terminal.
"""

from __future__ import annotations

import json

from harness_maker.models import HarnessConfig
from harness_maker.permission_syntax import (
    BASH_SEPARATORS,
    UNMATCHED_PATH_TOOLS,
    is_matchable_rule,
    unmatchable_reason,
)
from harness_maker.render import _make_env

SETTINGS_TEMPLATES = ("settings/Side.json.j2", "settings/Production.json.j2")


def _render_permissions(template: str, deny_dangerous: bool) -> dict[str, list[str]]:
    cfg = HarnessConfig(permissions={"deny_dangerous": deny_dangerous}).model_dump(mode="json")
    out = (
        _make_env()
        .get_template(template)
        .render(preset="Side", config=cfg, harness_maker_src_path="/fake/src/path")
    )
    return dict(json.loads(out)["permissions"])


# --- the validator itself -------------------------------------------------


def test_write_path_rules_are_unmatchable() -> None:
    for tool in UNMATCHED_PATH_TOOLS:
        rule = f"{tool}(/etc/**)"
        assert not is_matchable_rule(rule), f"{rule} must be reported unmatchable"
        assert tool in (unmatchable_reason(rule) or "")


def test_edit_and_read_path_rules_are_matchable() -> None:
    for rule in ("Edit(/etc/**)", "Edit(~/.ssh/**)", "Read(//**)"):
        assert is_matchable_rule(rule), f"{rule} is a real, enforced rule shape"


def test_bash_rule_spanning_a_separator_is_unmatchable() -> None:
    for sep in BASH_SEPARATORS:
        rule = f"Bash(curl * {sep} sh)"
        assert not is_matchable_rule(rule), f"{rule} spans {sep!r} — can never match"


def test_bare_and_scoped_bash_rules_are_matchable() -> None:
    for rule in ("Bash(rm:*)", "Bash(curl:*)", "Bash(git diff:*)", "Bash", "Read"):
        assert is_matchable_rule(rule), f"{rule} must be accepted"


def test_the_exact_rules_this_plan_removed_are_all_unmatchable() -> None:
    """The premise of the whole change, pinned so it cannot be re-litigated."""
    for rule in ("Bash(curl * | sh)", "Write(/etc/**)", "Write(~/.ssh/**)", "Write(~/.aws/**)"):
        assert not is_matchable_rule(rule), f"{rule} was shipped dead through 0.39.0"


def test_the_replacements_are_all_matchable() -> None:
    for rule in ("Bash(rm:*)", "Edit(/etc/**)", "Edit(~/.ssh/**)", "Edit(~/.aws/**)"):
        assert is_matchable_rule(rule), f"{rule} is the Phase 5 replacement — must match"


# --- the property, over every rendered rule -------------------------------


def test_no_rendered_rule_is_unmatchable() -> None:
    """FAILS against d895800b's templates — that is the point (Phase 8 exit)."""
    for tpl in SETTINGS_TEMPLATES:
        for opted_in in (False, True):
            perms = _render_permissions(tpl, opted_in)
            for key, rules in perms.items():
                if not isinstance(rules, list):
                    continue
                for rule in rules:
                    assert is_matchable_rule(rule), (
                        f"{tpl} (deny_dangerous={opted_in}) renders an unmatchable "
                        f"{key} rule {rule!r}: {unmatchable_reason(rule)}"
                    )
