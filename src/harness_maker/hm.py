"""`hm <module> [args…]` — the short console-script form of `python -m harness_maker.<module>`.

**Why this exists.** Every mandated call in every rendered stage command carries the
prefix `python -m harness_maker.` — 24 characters, 390 times across the shipped surface.
That prefix is the reason PLAN-workflow-step-audit's central mechanism could not land:
[ADR-002](../../work-docs/PLAN-workflow-step-audit.md#adr-002) replaces short inline
command sequences with composite CLI calls, and a CLI invocation line is *longer* than
the inline command it replaces, so every phase that removed round-trips added characters
and failed [ADR-011](../../work-docs/PLAN-workflow-step-audit.md#adr-011)'s aggregate
arm. Shortening the invocation attacks the cause rather than the symptom, and it pays
out on every stage at once instead of only the ones this PLAN edits.

**It dispatches; it does not reimplement.** `runpy.run_module(..., run_name="__main__")`
is *literally* the code path `python -m` takes, so argument parsing, exit codes and
`SystemExit` semantics are the module's own — there is no second implementation to drift
([ADR-003](../../work-docs/PLAN-workflow-step-audit.md#adr-003)). A module reached
through `hm` and the same module reached through `python -m` cannot behave differently,
because they are the same call.

**The module name is not free-form.** `_DISPATCHABLE` is an explicit allowlist, so `hm`
cannot be talked into executing an arbitrary importable module, and a typo in a rendered
template fails loudly at the dispatcher rather than as a confusing import error deep
inside somebody else's package. `tests/structural/test_hm_entrypoint.py` asserts the
allowlist covers every module the rendered surface actually calls — the failure mode
otherwise is a template that ships a call nothing can run.
"""

from __future__ import annotations

import runpy
import sys

#: Every module the rendered stage commands may invoke. Derived from the shipped surface
#: and gated by a structural test, so adding a call site to a template without adding it
#: here fails in CI rather than at a user's gate.
_DISPATCHABLE: frozenset[str] = frozenset(
    {
        "autopilot",
        "autopilot_caps",
        "autopilot_ledger",
        "cli",
        "delegation_ledger",
        "delivery_metrics",
        "economics",
        "high_diff",
        "iter_receipts",
        "memory_md",
        "memory_retrieve",
        "observability.verification_cache",
        "review_telemetry",
        "run_classify",
        "second_brain",
        "second_opinion_invoke",
        "spec_machine",
        "spec_mutation",
        "spec_need",
        "spec_quality",
        "test_dep_map",
        "two_pass_review",
        "worktree",
        "wrapup_brief",
        "wrapup_receipt",
    }
)

_USAGE = "usage: hm <module> [args…]\n\nequivalent to: python -m harness_maker.<module> [args…]\n"


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in {"-h", "--help"}:
        sys.stdout.write(_USAGE + "\nmodules:\n")
        for name in sorted(_DISPATCHABLE):
            sys.stdout.write(f"  {name}\n")
        return 0 if args else 2
    module, rest = args[0], args[1:]
    if module not in _DISPATCHABLE:
        sys.stderr.write(
            f"hm: unknown module {module!r}. `hm --help` lists the dispatchable set; if a "
            f"rendered template calls this, the template and _DISPATCHABLE have drifted.\n"
        )
        return 2
    target = f"harness_maker.{module}"
    saved = sys.argv
    # `python -m pkg.mod` sets argv[0] to the module's __file__; nothing downstream reads
    # it for anything but usage text, and a stable, honest string beats a fabricated path.
    sys.argv = [f"hm {module}", *rest]
    try:
        runpy.run_module(target, run_name="__main__", alter_sys=True)
    except SystemExit as exc:  # the module's own exit code is the contract
        code = exc.code
        if code is None:
            return 0
        if isinstance(code, int):
            return code
        sys.stderr.write(f"{code}\n")
        return 1
    finally:
        sys.argv = saved
    return 0


if __name__ == "__main__":  # pragma: no cover — exercised through the console script
    raise SystemExit(main())
