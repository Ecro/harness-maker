"""SPEC-intent-layer-improvements AC-005 — a trial is inactive only on a recorded user disable.

The relation is stated on recorded authority, not on the working-copy `enabled` field: the
latest `policy` decision must be a user decision with `enabled: false`, and the trial's `policy`
must name it, in BOTH the working copy and HEAD. Every other arrangement is enumerated from the
pre-change fail-closed branches of `active_trials` and must stay active and protected.

Phase A.4: every `stays-active` case passes before the change (today every trial is active);
they are preservation guards whose RED sibling is `disabled-in-both`, the only case that needs
the new behaviour.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest

from harness_maker import intent_trial
from tests.unit import trial_fixture as fx

REL = f"work-docs/PLAN-{fx.TRIAL}.md"


def _policy(
    enabled: bool, decision_id: str, *, authority: str = "explicit_user_decision"
) -> dict[str, Any]:
    d = fx.decision("policy", {"enabled": enabled, "revision": "v2"}, decision_id=decision_id)
    d["authority"] = authority
    return d


def _with_decisions(root: Path, decisions: list[dict[str, Any]], *, commit: bool) -> None:
    meta = fx.read(root)
    meta["trial"]["decisions"] = decisions
    latest = decisions[-1]
    meta["trial"]["policy"] = {
        "enabled": latest["payload"]["enabled"],
        "revision": "v2",
        "authority": latest["id"],
    }
    fx.write_doc(fx.path(root), meta, "## Trial\n\nFrozen.\n")
    if commit:
        fx.git(root, "add", REL)
        fx.git(root, "commit", "-qm", "policy decision")


def _disabled(root: Path, *, commit: bool = True) -> None:
    _with_decisions(root, [_policy(False, "freeze")], commit=commit)


def _case_disabled_in_both(root: Path) -> None:
    _disabled(root)


def _case_enabled(root: Path) -> None:
    return None


def _case_hand_edit_without_decision(root: Path) -> None:
    meta = fx.read(root)
    meta["trial"]["policy"]["enabled"] = False
    fx.write_doc(fx.path(root), meta, "## Trial\n\nHand edit.\n")
    fx.git(root, "add", REL)
    fx.git(root, "commit", "-qm", "hand edit")


def _case_decision_only_in_working_copy(root: Path) -> None:
    _disabled(root, commit=False)


def _case_reenabled_after_disable(root: Path) -> None:
    _with_decisions(root, [_policy(False, "freeze"), _policy(True, "thaw")], commit=True)


def _case_disable_without_user_authority(root: Path) -> None:
    _with_decisions(root, [_policy(False, "freeze", authority="agent_inference")], commit=True)


def _case_policy_names_other_decision(root: Path) -> None:
    _disabled(root)
    meta = fx.read(root)
    meta["trial"]["policy"]["authority"] = "someone-else"
    fx.write_doc(fx.path(root), meta, "## Trial\n\nFrozen.\n")
    fx.git(root, "commit", "-qam", "authority drift")


def _case_non_user_actor(root: Path) -> None:
    d = _policy(False, "freeze")
    d["actor"] = "agent"
    _with_decisions(root, [d], commit=True)


def _case_policy_still_enabled(root: Path) -> None:
    _disabled(root)
    meta = fx.read(root)
    meta["trial"]["policy"]["enabled"] = True
    fx.write_doc(fx.path(root), meta, "## Trial\n\nFrozen.\n")
    fx.git(root, "commit", "-qam", "policy drift")


def _case_untracked_plan(root: Path) -> None:
    _disabled(root)
    fx.git(root, "rm", "-q", "--cached", REL)
    fx.git(root, "commit", "-qm", "untrack the trial PLAN")


def _case_disable_without_ids(root: Path) -> None:
    d = _policy(False, "freeze")
    del d["id"]
    meta = fx.read(root)
    meta["trial"]["decisions"] = [d]
    meta["trial"]["policy"] = {"enabled": False, "revision": "v2"}
    fx.write_doc(fx.path(root), meta, "## Trial\n\nNo ids.\n")
    fx.git(root, "add", REL)
    fx.git(root, "commit", "-qm", "disable without ids")


def _case_head_disabled_working_copy_reenabled(root: Path) -> None:
    _disabled(root)
    _with_decisions(root, [_policy(False, "freeze"), _policy(True, "thaw")], commit=False)


def _case_refrozen_after_thaw(root: Path) -> None:
    _with_decisions(
        root,
        [_policy(False, "freeze"), _policy(True, "thaw"), _policy(False, "refreeze")],
        commit=True,
    )


def _case_head_not_utf8(root: Path) -> None:
    _disabled(root, commit=False)
    frozen = fx.path(root).read_bytes()
    fx.path(root).write_bytes(b"---\ntrial: \xff\xfe\n---\n")
    fx.git(root, "add", REL)
    fx.git(root, "commit", "-qm", "undecodable HEAD")
    fx.path(root).write_bytes(frozen)


def _case_legacy(root: Path) -> None:
    return None


def _case_unparseable(root: Path) -> None:
    _disabled(root)
    fx.path(root).write_text("---\ntrial:\n  policy: [\n---\n## Trial\n")


def _case_symlink(root: Path) -> None:
    _disabled(root)
    target = root / "elsewhere.md"
    target.write_bytes(fx.path(root).read_bytes())
    fx.path(root).unlink()
    fx.path(root).symlink_to(target)


def _case_deleted_tracked(root: Path) -> None:
    _disabled(root)
    fx.path(root).unlink()


def _case_marker_free_over_disabled_head(root: Path) -> None:
    _disabled(root)
    fx.write_doc(fx.path(root), {"type": "plan", "task_slug": fx.TRIAL}, "## Evidence\n")


def _case_unreadable(root: Path) -> None:
    _disabled(root)
    fx.path(root).chmod(0)


CASES = {
    "disabled-in-both": (_case_disabled_in_both, False, False),
    "refrozen-after-thaw": (_case_refrozen_after_thaw, False, False),
    "head-not-utf8": (_case_head_not_utf8, True, False),
    "enabled": (_case_enabled, True, False),
    "hand-edit-without-decision": (_case_hand_edit_without_decision, True, False),
    "decision-only-in-working-copy": (_case_decision_only_in_working_copy, True, False),
    "reenabled-after-disable": (_case_reenabled_after_disable, True, False),
    "disable-without-user-authority": (_case_disable_without_user_authority, True, False),
    "policy-names-other-decision": (_case_policy_names_other_decision, True, False),
    "non-user-actor": (_case_non_user_actor, True, False),
    "policy-still-enabled": (_case_policy_still_enabled, True, False),
    "untracked-plan": (_case_untracked_plan, True, False),
    "disable-without-ids": (_case_disable_without_ids, True, False),
    "head-disabled-working-copy-reenabled": (
        _case_head_disabled_working_copy_reenabled,
        True,
        False,
    ),
    "legacy": (_case_legacy, True, True),
    "unparseable": (_case_unparseable, True, False),
    "symlink": (_case_symlink, True, False),
    "deleted-tracked": (_case_deleted_tracked, True, False),
    "marker-free-over-disabled-head": (_case_marker_free_over_disabled_head, True, False),
    "unreadable": (_case_unreadable, True, False),
}


@pytest.mark.parametrize("name", sorted(CASES))
def test_frozen_trial_is_inactive(name: str, tmp_path: Path) -> None:
    arrange, active, legacy = CASES[name]
    if name == "unreadable" and os.geteuid() == 0:
        pytest.skip("root reads mode-0 files")
    root = fx.build(tmp_path / "repo", legacy=legacy)
    arrange(root)
    try:
        listed = fx.TRIAL in intent_trial.active_trials(root)
        protected = intent_trial.protected_trial_paths(root)
    finally:
        if fx.path(root).exists() and not fx.path(root).is_symlink():
            fx.path(root).chmod(0o644)
    assert listed is active
    assert (REL in protected) is active


def test_head_read_failure_keeps_disabled_trial_active(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = fx.build(tmp_path / "repo")
    _disabled(root)

    def _boom(base: Path, relative: str) -> bytes | None:
        raise OSError("git unavailable")

    monkeypatch.setattr(intent_trial, "_head_bytes", _boom)
    assert fx.TRIAL in intent_trial.active_trials(root)
