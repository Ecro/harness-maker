"""Prune harness-shipped deny literals on re-render (Phase 6, ADR-004 rev2).

`_merge_permissions` unions the on-disk deny list to preserve rules a user
added, which means every literal harness-maker itself ever rendered survives
forever and is indistinguishable from a user's own. That is how a project ends
up carrying `Write(/etc/**)` (dead, warns) years after the template stopped
being the reason it is there — the warning the incoming brief reported.

The fix drops harness-shipped literals by exact full-string match before the
union, so the deny list is rebuilt from `deny_dangerous` policy each render
instead of accreting history. User-authored rules must survive untouched.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from harness_maker.permission_syntax import is_matchable_rule
from harness_maker.render import _HARNESS_SHIPPED_DENY_LITERALS, _merge_permissions

# Merge-input fixture: every literal a settings template rendered through 0.39.0.
# This is test INPUT, not the oracle — the oracle is git history, see
# `test_every_pruned_literal_was_really_shipped_by_a_settings_template`.
ALL_HISTORICAL = [
    "Bash(rm:*)",
    "Bash(curl * | sh)",
    "Write(/etc/**)",
    "Write(~/.ssh/**)",
    "Bash(curl:*)",
    "Write(~/.aws/**)",
    "Edit(/etc/**)",
    "Edit(~/.ssh/**)",
    "Edit(~/.aws/**)",
]


def _shipped_in_settings_history(literal: str) -> bool:
    """Did a settings template ever contain `literal`? Oracle = git history."""
    proc = subprocess.run(
        [
            "git",
            "log",
            "--oneline",
            f"-S{literal}",
            "--",
            "src/harness_maker/templates/settings/",
        ],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    )
    return bool(proc.stdout.strip())


def _is_a_git_checkout() -> bool:
    return (Path(__file__).resolve().parents[2] / ".git").exists()


def test_every_pruned_literal_provably_enforces_nothing() -> None:
    """THE safety invariant. Runs everywhere, no git needed.

    Deleting a rule that never fired removes zero protection and clears the
    warning it caused. Deleting a LIVE rule is silent data loss — and no oracle
    can tell "harness-maker shipped this string" from "the user also typed it",
    so liveness is the only line that holds without knowing the user's config.

    If this fails, do not relax it: the entry is about to delete real protection.
    """
    for literal in sorted(_HARNESS_SHIPPED_DENY_LITERALS):
        assert not is_matchable_rule(literal), (
            f"{literal!r} is ENFORCEABLE — pruning it removes protection the user "
            f"may rely on. Only provably-dead rules may be pruned."
        )


def test_live_rules_we_shipped_are_not_pruned() -> None:
    """`deny_dangerous` defaults to False, so the template does not re-add these."""
    for live in ("Bash(rm:*)", "Bash(curl:*)"):
        assert is_matchable_rule(live)
        assert live not in _HARNESS_SHIPPED_DENY_LITERALS


@pytest.mark.skipif(not _is_a_git_checkout(), reason="no .git (sdist/wheel test)")
def test_every_pruned_literal_was_really_shipped_by_a_settings_template() -> None:
    """Second oracle: we only delete strings we can prove we emitted.

    A shallow clone FAILS rather than skips — CI checks out with `fetch-depth: 0`
    precisely so this runs. A skip here would suppress the exact failure that
    matters, in the only place that gates a release.
    """
    root = Path(__file__).resolve().parents[2]
    shallow = subprocess.run(
        ["git", "rev-parse", "--is-shallow-repository"],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    assert shallow.stdout.strip() == "false", (
        "shallow clone: `git log -S` cannot see history, so this guard would "
        "pass vacuously. Set `fetch-depth: 0` on the checkout step."
    )

    hits = {
        lit: _shipped_in_settings_history(lit) for lit in sorted(_HARNESS_SHIPPED_DENY_LITERALS)
    }
    # Anti-vacuity: a renamed template dir would make every `git log -S` return
    # empty, and a "no literal was ever shipped" result must not read as a pass.
    assert any(hits.values()), (
        "git log -S found NOTHING for any literal — the search path is wrong "
        "(renamed templates/settings/?), not the frozenset"
    )
    for literal, shipped in hits.items():
        assert shipped, (
            f"{literal!r} never appears in any settings template in git history — "
            f"pruning it would delete a USER-authored deny rule"
        )


def test_literals_never_shipped_by_a_settings_template_are_not_pruned() -> None:
    """ADR-004 rev4 — these are the USER's rules, not our history.

    The git-history oracle proved ADR-004's inventory wrong: these four reach a
    project's disk via /hm:health Layer 1 acceptance or by hand, never from a
    settings template. Pruning them would be silent deletion of user content.
    `Edit(...)` becomes harness-shipped in 0.40 — but a copy already on disk
    predates that, so it stays the user's.
    """
    for not_ours in ("Write(~/.aws/**)", "Edit(/etc/**)", "Edit(~/.ssh/**)", "Edit(~/.aws/**)"):
        assert not_ours not in _HARNESS_SHIPPED_DENY_LITERALS


def test_a_user_authored_edit_rule_survives_an_opt_out_render() -> None:
    """The concrete data-loss case ADR-004 would have caused."""
    merged = _merge_permissions({"deny": ["Edit(/etc/**)", "Write(~/.aws/**)"]}, {"deny": []})
    assert merged["deny"] == ["Edit(/etc/**)", "Write(~/.aws/**)"]


def test_bash_curl_star_is_held_back_until_the_gate_lands() -> None:
    """ADR-004 rev3: never remove live protection before its replacement ships.

    `Bash(curl:*)` is live and the template does NOT re-add it, so pruning it
    while `permission_gate`'s PreToolUse hook is unwired (Phase 3, parked) is a
    strict reduction with nothing behind it.

    Revisit in the same commit that wires the gate — and even then, prune it only
    if `test_every_pruned_literal_provably_enforces_nothing` can be satisfied or
    consciously superseded.
    """
    assert "Bash(curl:*)" not in _HARNESS_SHIPPED_DENY_LITERALS


def test_dead_literals_we_shipped_are_pruned() -> None:
    """These three are the startup warning the incoming brief reported."""
    for dead in ("Bash(curl * | sh)", "Write(/etc/**)", "Write(~/.ssh/**)"):
        assert dead in _HARNESS_SHIPPED_DENY_LITERALS


def test_accreted_literals_are_dropped_and_user_rules_survive() -> None:
    existing = {"deny": [*ALL_HISTORICAL, "Bash(foo:*)", "Edit(/srv/secret/**)"]}
    new = {"deny": ["Bash(rm:*)", "Edit(/etc/**)", "Edit(~/.ssh/**)", "Edit(~/.aws/**)"]}

    merged = _merge_permissions(existing, new)["deny"]

    # The policy-derived list is rebuilt, in template order, at the front.
    assert merged[:4] == new["deny"]
    # Nothing harness-maker shipped accreted past it.
    for literal in _HARNESS_SHIPPED_DENY_LITERALS:
        if literal not in new["deny"]:
            assert literal not in merged, f"{literal} should have been pruned"
    # User-authored rules are untouched — this is what the union exists for.
    assert "Bash(foo:*)" in merged
    assert "Edit(/srv/secret/**)" in merged


def test_opt_out_drops_our_history_and_keeps_everything_else() -> None:
    """The proof case: this repo, which carries all nine literals on disk."""
    merged = _merge_permissions({"deny": list(ALL_HISTORICAL)}, {"deny": []})["deny"]
    assert merged == [
        # Live + not re-added at the default opt-out ⇒ held back (rev3/rev5).
        # `Bash(rm:*)` is exactly what /hm:health Layer 1 has users accept.
        "Bash(rm:*)",
        "Bash(curl:*)",
        # Never shipped by a settings template ⇒ the user's (rev4).
        "Write(~/.aws/**)",
        "Edit(/etc/**)",
        "Edit(~/.ssh/**)",
        "Edit(~/.aws/**)",
    ]


def test_prune_does_not_touch_allow_or_ask() -> None:
    """The literals are deny-history. An identical string in `allow` is a user's."""
    existing = {"allow": ["Write(/etc/**)"], "ask": ["Write(~/.ssh/**)"]}
    merged = _merge_permissions(existing, {"allow": [], "ask": []})
    assert merged["allow"] == ["Write(/etc/**)"]
    assert merged["ask"] == ["Write(~/.ssh/**)"]


def test_prune_is_exact_match_not_substring() -> None:
    existing = {"deny": ["Bash(rm:*) # my note", "XWrite(/etc/**)", "Edit(/etc/**)/sub"]}
    merged = _merge_permissions(existing, {"deny": []})["deny"]
    assert merged == existing["deny"], "near-misses are user content, not our history"


@pytest.mark.parametrize("_run", [1, 2])
def test_render_is_idempotent_over_the_prune(tmp_path: Path, _run: int) -> None:
    """Re-rendering must converge, not oscillate between pruned and re-added."""
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps({"permissions": {"deny": list(ALL_HISTORICAL)}}))
    new = {"deny": ["Bash(rm:*)", "Edit(/etc/**)"]}
    first = _merge_permissions(json.loads(settings.read_text())["permissions"], new)
    second = _merge_permissions(first, new)
    assert first == second
