"""Single source of truth for the `python -m harness_maker[.<module>]` command surface.

WHY: the plugin renders ~230 `python -m harness_maker.<module> <subcommand>` invocations
into slash-command templates. An LLM reconstructing those strings from prose mis-transcribes
the module path (observed 2026-07-01: `python -m harness_maker.autopilot_caps on`, which does
not exist). This registry lets the tool describe its own command surface so a runtime guard
can redirect misroutes (B) and a CI test can prove every template invocation parses (C).
"""

from __future__ import annotations

import sys
from collections.abc import Sequence
from dataclasses import dataclass

# Parser shapes — a dispatch hint, NOT the guard-scope predicate (validator R2-W2):
#   subparser       argparse add_subparsers          (guarded, introspectable)
#   manual-dispatch `if sub == "..."` on argv[0]     (guarded, executes on invocation)
#   typer           Typer app (owns its own dispatch) (guard-exempt; T-C1 still validates)
#   flagonly        flags / stdin only, no subcommand (guard-exempt, empty subcommands)


@dataclass(frozen=True)
class ModuleSpec:
    """One `python -m` entry point. `entry` is its callable name (`main` / `_cli`)."""

    shape: str
    subcommands: frozenset[str] = frozenset()
    entry: str = "main"

    @property
    def guarded(self) -> bool:
        """Guard scope = has subcommands AND is not the Typer host (validator R2-W2).

        WHY not shape membership: autopilot's on/off must be guarded whatever its parser
        shape; the Typer host dispatches its own unknown-command errors and must not be
        second-guessed by argv[0]."""
        return self.shape != "typer" and bool(self.subcommands)


def _s(*names: str) -> frozenset[str]:
    return frozenset(names)


# Verified against source 2026-07-01 (extracted add_parser / manual `sub ==` tokens).
MODULES: dict[str, ModuleSpec] = {
    # ── argparse-subparser (guarded) ──
    "autopilot_caps": ModuleSpec("subparser", _s("boundary", "gate-blocked")),
    "autopilot_ledger": ModuleSpec("subparser", _s("smoke")),
    "codex_ledger": ModuleSpec("subparser", _s("emit")),
    "delegation_ledger": ModuleSpec("subparser", _s("record")),
    "delivery_metrics": ModuleSpec("subparser", _s("candidates", "adjudicate", "compute", "trend")),
    "economics": ModuleSpec("subparser", _s("report", "stages", "doctor", "composition")),
    "high_diff": ModuleSpec("subparser", _s("classify")),
    "iter_receipts": ModuleSpec(
        "subparser",
        _s("write", "set-iter-marker", "patch-runtime", "read", "list", "verify"),
    ),
    "memory_md": ModuleSpec(
        "subparser", _s("append-session", "upsert-wiki", "upsert-failure", "consolidate")
    ),
    "run_classify": ModuleSpec("subparser", _s("boundaries", "record")),
    "observability.verification_cache": ModuleSpec(
        "subparser", _s("key", "check", "mark-pass", "explain")
    ),
    "second_brain": ModuleSpec(
        "subparser",
        _s("search", "read", "write", "append", "promote", "patch", "validate"),
        entry="_cli",
    ),
    # flagonly: no subcommand, so guard-exempt — the argparse layer owns its own errors.
    "second_opinion_invoke": ModuleSpec("flagonly"),
    "test_dep_map": ModuleSpec("flagonly"),
    "wrapup_brief": ModuleSpec("flagonly"),
    "wrapup_land": ModuleSpec("flagonly"),
    "wrapup_receipt": ModuleSpec("flagonly"),
    "spec_inventory": ModuleSpec(
        "subparser", _s("reverse-map", "verify-inventory", "sample-for-review", "generate-all")
    ),
    "spec_machine": ModuleSpec(
        "subparser",
        _s(
            "validate",
            "cross-validate",
            "mark-tested",
            "waiver-check",
            "find-unbound",
            "mark-judged",
            "find-unjudged",
            "check",
        ),
    ),
    "spec_mutation": ModuleSpec("subparser", _s("gate", "classify")),
    "spec_need": ModuleSpec(
        "subparser",
        _s(
            "prefilter",
            "record",
            "op-check",
            "waiver-set",
            "waiver-check",
            "marker-write",
            "marker-read",
            "marker-clear",
            "marker-fresh",
        ),
    ),
    # ── manual-dispatch (guarded; SOME subcommands mutate on bare invocation) ──
    "worktree": ModuleSpec(
        "manual-dispatch",
        _s(
            "cleanup-all",
            "commit-base-memory",
            "create",
            "drain",
            "finalize",
            "loop-mode-active",
            "owned-crumb-add",
            "owned-crumb-clear",
            "owned-crumb-read",
            "owned-uuids",
            "post-commit-pop",
            "prune-branches",
            "span-end",
            "task-create",
            "task-land",
            "task-preflight",
            "task-refresh",
            "verify",
            "wt-uuid",
        ),
    ),
    "codex_adapter": ModuleSpec("manual-dispatch", _s("adapt", "stamp-ids")),
    # Flag-only (no subcommand): it owns the path filtering that keeps external-model output
    # off a pre-approved argv, so it must be reachable but has nothing to dispatch on.
    "second_opinion_oracle": ModuleSpec("flagonly"),
    "review_telemetry": ModuleSpec("manual-dispatch", _s("emit")),
    "spec_quality": ModuleSpec("manual-dispatch", _s("eval")),
    "two_pass_review": ModuleSpec("manual-dispatch", _s("redact", "merge")),
    "refdocs_index": ModuleSpec("manual-dispatch", _s("build"), entry="_cli"),
    # NEW (Phase 1): down-unified from the Typer `autopilot` toggle. It uses argparse with
    # a choices-positional, not `if sub ==`, but is deliberately classed manual-dispatch so
    # T-C2 source-scans it (its `on` mutates a marker) instead of bare-invoking it.
    # `status` (PLAN-autopilot-advance-noop ADR-002) is dot-form / `hm`-form only — the
    # Typer alias at :161 stays a backward-compat on/off shim and does NOT gain it.
    "autopilot": ModuleSpec("manual-dispatch", _s("on", "off", "status")),
    # ── Typer host (guard-exempt; T-C1 validates these as `python -m harness_maker.cli X`
    #    and the root `python -m harness_maker X` form via TYPER_ALIASES) ──
    "cli": ModuleSpec(
        "typer",
        _s(
            "make",
            "locate",
            "git-status",
            "git-ignore-roots",
            "prune-backups",
            "health",
            "security-scan",
            "remove",
            "profile",
            "verify",
            "configure-second-brain",
            "autopilot",
        ),
    ),
    # ── flagonly / stdin / hook / gate (guard-exempt, empty subcommands) ──
    "drift_monitor": ModuleSpec("flagonly"),
    "telemetry": ModuleSpec("flagonly"),
    "memory_retrieve": ModuleSpec("flagonly"),
    "feedback.draft_writer": ModuleSpec("flagonly"),
    "feedback.footer": ModuleSpec("flagonly"),
    "feedback.telemetry_grep": ModuleSpec("flagonly"),
    "gates.permission_gate": ModuleSpec("flagonly"),
    "gates.spec_gate": ModuleSpec("flagonly"),
    "gates.worktree_gate": ModuleSpec("flagonly"),
    "hooks.autopilot_autoarm": ModuleSpec("flagonly"),
    "hooks.flush_session": ModuleSpec("flagonly"),
    "hooks.loop_gate": ModuleSpec("flagonly"),
    "hooks.post_write_reminder": ModuleSpec("flagonly"),
    "hooks.sessionid_envfile": ModuleSpec("flagonly"),
    "hooks.sessionstart_drift": ModuleSpec("flagonly"),
}

# The root `python -m harness_maker <cmd>` form (via __main__ → Typer) accepts these.
TYPER_ALIASES: frozenset[str] = MODULES["cli"].subcommands


def resolve_owners(verb: str) -> frozenset[str]:
    """Modules whose subcommand set includes `verb`.

    Multi-owner by design — `write`/`read`/`validate`/`verify`/`emit` collide across
    modules (validator C3); the guard lists every owner rather than guessing one.
    """
    return frozenset(name for name, spec in MODULES.items() if verb in spec.subcommands)


def guard_or_none(module: str, argv: Sequence[str] | None = None) -> int | None:
    """`misroute_guard` with argv-None resolution — the uniform per-module entry hook.

    Every guarded module calls this at the top of its entry (`main`/`_cli`); `argv=None`
    resolves to `sys.argv[1:]` so the same one-liner works whether the entry took an
    explicit list or not.
    """
    return misroute_guard(module, list(sys.argv[1:] if argv is None else argv))


def misroute_guard(module: str, argv: list[str]) -> int | None:
    """Return None to proceed; else print a did-you-mean redirect and return exit code 2.

    FAIL-OPEN by design: a redirect fires ONLY when `argv[0]` is a valid subcommand of a
    DIFFERENT module (the actual bug class — `autopilot_caps on` → `autopilot on`). A token
    that is this module's own subcommand, or is unknown to the whole registry, returns None
    and lets the module's own parser handle it. WHY fail-open: a token UNKNOWN to the whole
    registry never false-redirects (it degrades to pre-guard behavior). The one residual risk
    is a valid subcommand under-listed for THIS module that ALSO happens to be another
    module's verb — that WOULD be wrongly redirected; the T-C2 subparser parity gate exists to
    make such under-listing fail CI so it can never ship.
    """
    spec = MODULES.get(module)
    if spec is None or not spec.guarded:
        return None
    if not argv:
        return None  # missing subcommand — the module's own parser reports it
    tok = argv[0]
    if tok.startswith("-"):
        return None  # flag-first — not a subcommand misroute
    if tok in spec.subcommands:
        return None  # valid subcommand of THIS module
    owners = sorted(resolve_owners(tok) - {module})
    if not owners:
        return None  # unknown to the whole registry — fail open, let the module report it
    suffix = (" " + " ".join(argv[1:])) if argv[1:] else ""

    def _fmt(owner: str) -> str:
        # The Typer host is reached via the root form `python -m harness_maker <cmd>`
        # (the documented, canonical invocation), not `python -m harness_maker.cli <cmd>`.
        base = (
            f"python -m harness_maker {tok}"
            if owner == "cli"
            else f"python -m harness_maker.{owner} {tok}"
        )
        return f"    {base}{suffix}"

    lines = [
        f"{module}: {tok!r} is not a subcommand of this module.",
        "Did you mean:",
        *[_fmt(o) for o in owners],
    ]
    # Multi-owner: the same verb exists in several modules whose flag surfaces differ, so the
    # trailing args are only valid for the module they were typed against (review R2 P3).
    if len(owners) > 1:
        lines.append("(the same verb exists in several modules — flags may differ per target)")
    print("\n".join(lines), file=sys.stderr)
    return 2
