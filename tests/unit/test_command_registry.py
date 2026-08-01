"""Phase 0 — command-surface registry SSOT + misroute guard.

PLAN-command-surface-registry ADR-002/004: one source of truth for the
`python -m harness_maker[.<module>]` surface, powering the runtime did-you-mean
guard (B) and the CI parse tests (C).
"""

from __future__ import annotations

from harness_maker import command_registry as cr


def test_registry_nonempty_and_unique_verb_owner() -> None:
    assert cr.MODULES
    assert cr.resolve_owners("boundary") == frozenset({"autopilot_caps"})


def test_known_verb_collisions_are_multi_owner() -> None:
    # validator C3: write/read owned by BOTH second_brain and iter_receipts.
    assert cr.resolve_owners("write") == frozenset({"second_brain", "iter_receipts"})
    assert cr.resolve_owners("read") == frozenset({"second_brain", "iter_receipts"})


def test_worktree_is_manual_dispatch_and_guarded() -> None:
    assert cr.MODULES["worktree"].shape == "manual-dispatch"
    assert cr.MODULES["worktree"].guarded is True


def test_flagonly_module_empty_subcommands_and_unguarded() -> None:
    assert cr.MODULES["telemetry"].subcommands == frozenset()
    assert cr.MODULES["telemetry"].guarded is False


def test_typer_host_has_subcommands_but_guard_exempt() -> None:
    assert "health" in cr.MODULES["cli"].subcommands
    assert cr.MODULES["cli"].guarded is False
    assert "health" in cr.TYPER_ALIASES


def test_autopilot_guarded_by_subcommands_not_shape() -> None:
    # validator R2-W2: guard scope is bool(subcommands) (and not typer), so autopilot's
    # subcommands are guarded regardless of parser shape. `status` joined in
    # PLAN-autopilot-advance-noop ADR-002 — it MUST be registered or misroute_guard
    # rejects it before argparse ever sees it.
    assert cr.MODULES["autopilot"].subcommands == frozenset({"on", "off", "status"})
    assert cr.MODULES["autopilot"].guarded is True


def test_guard_redirects_cross_module(capsys) -> None:  # type: ignore[no-untyped-def]
    rc = cr.misroute_guard("autopilot_caps", ["on", "--level", "auto_safe"])
    assert rc == 2
    err = capsys.readouterr().err
    assert "python -m harness_maker.autopilot on --level auto_safe" in err
    assert "invalid choice" not in err


def test_guard_lists_all_owners_on_collision(capsys) -> None:  # type: ignore[no-untyped-def]
    rc = cr.misroute_guard("spec_need", ["write"])
    assert rc == 2
    err = capsys.readouterr().err
    assert "python -m harness_maker.iter_receipts write" in err
    assert "python -m harness_maker.second_brain write" in err


def test_guard_passes_valid_subcommand() -> None:
    assert cr.misroute_guard("autopilot_caps", ["boundary", "--current", "plan"]) is None


def test_guard_ignores_flag_first_and_empty() -> None:
    assert cr.misroute_guard("autopilot_caps", ["--help"]) is None
    assert cr.misroute_guard("autopilot_caps", []) is None


def test_guard_noop_for_unguarded_modules() -> None:
    assert cr.misroute_guard("telemetry", ["anything"]) is None
    assert cr.misroute_guard("cli", ["bogus"]) is None
    assert cr.misroute_guard("nonexistent_module", ["x"]) is None


def test_guard_fails_open_on_registry_unknown_token() -> None:
    # A token owned by NO module returns None (fail-open) — the guard must never
    # false-redirect a valid subcommand this registry happens to under-list.
    assert cr.misroute_guard("worktree", ["totally-unknown-verb"]) is None


def test_guard_or_none_resolves_and_matches_misroute_guard(capsys) -> None:  # type: ignore[no-untyped-def]
    assert cr.guard_or_none("autopilot_caps", ["on"]) == 2
    _ = capsys.readouterr()
    assert cr.guard_or_none("autopilot_caps", ["boundary"]) is None
