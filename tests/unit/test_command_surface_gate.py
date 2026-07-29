"""Phase 3 — CI hard-fail gates keeping the command surface honest.

PLAN-command-surface-registry ADR-005:
- T-C1 (template↔registry): every rendered `python -m harness_maker[.<mod>] <sub>`
  invocation names a registered module, and (for subcommand-bearing modules) a valid
  subcommand. Catches template↔code drift.
- T-C2 (registry↔code parity + guard wiring): the registry does not lie about a module's
  subcommands, and every guarded module actually calls the misroute guard. Split by parser
  shape so manual-dispatch mutating subcommands are never bare-invoked (validator R2-C1).
"""

from __future__ import annotations

import importlib
import inspect
import re
import sys
from pathlib import Path

import pytest

from harness_maker import command_registry as cr
from harness_maker.models import InterviewAnswers, ProjectProfile, Target
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize

_SRC = Path(__file__).parents[2] / "src" / "harness_maker"

# Matches `python -m harness_maker` optionally followed by `.<dotted.module>` and the next
# whitespace-delimited token (the candidate subcommand).
_INVOKE = re.compile(r"python -m harness_maker(\.[a-zA-Z0-9_.]+)?(?:\s+(\S+))?")
# The `hm <module> <subcommand>` console-script spelling (PLAN-workflow-step-audit
# ADR-018). Extracting only the long form was NOT harmless once the rewrite landed: it
# moved ~230 invocations out of this gate, `finditer` yielded nothing for them, and
# `assert not offenders` passed VACUOUSLY — the precise bug class the registry exists to
# catch, reintroduced by the change that was supposed to be inert. Hooks, the `make`
# bootstrap and the skills templates still emit the long form, so both patterns are live.
_INVOKE_HM = re.compile(r"(?<![\w./-])hm ([a-z][\w.]*)(?:\s+(\S+))?")
# A token we can validate: a plain subcommand word. Anything with shell/Jinja metachars
# (flags, vars, redirects, quotes, backticks) is a runtime value we cannot statically check.
_WORD = re.compile(r"^[a-z][a-z0-9-]*$")


@pytest.fixture(scope="module")
def rendered(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("cmd-surface-gate")
    blueprint = synthesize(
        ProjectProfile(stack=["python"]),
        InterviewAnswers(targets=[Target.CLAUDE_CODE, Target.CURSOR, Target.CODEX]),
    )
    render(blueprint, out, freeze_time=DEFAULT_FREEZE_TIME)
    return out


def _iter_invocations(text: str):  # type: ignore[no-untyped-def]
    for m in _INVOKE.finditer(text):
        dotted, tok = m.group(1), m.group(2)
        module = dotted[1:] if dotted else None  # strip leading '.'
        yield module, tok
    for m in _INVOKE_HM.finditer(text):
        yield m.group(1), m.group(2)


def test_tc1_every_template_invocation_is_registered(rendered: Path) -> None:
    offenders: dict[str, list[str]] = {}
    seen = 0
    for pattern in ("*.md", "*.mdc", "*.toml"):
        for f in rendered.rglob(pattern):
            for module, tok in _iter_invocations(f.read_text(encoding="utf-8")):
                seen += 1
                bad = _classify_invocation(module, tok)
                if bad:
                    offenders.setdefault(str(f.relative_to(rendered)), []).append(bad)
    # Non-empty guard, and it is load-bearing: `assert not offenders` is satisfied by an
    # extraction that finds NOTHING, which is exactly how this gate went quiet when the
    # call sites changed spelling. A green gate must mean "checked and clean", never
    # "looked and saw nothing".
    assert seen > 100, f"extraction looks broken: only {seen} invocations found"
    detail = "\n".join(f"  {k}: {v}" for k, v in sorted(offenders.items()))
    assert not offenders, f"unregistered command-surface invocations in rendered output:\n{detail}"


def _classify_invocation(module: str | None, tok: str | None) -> str | None:
    """Return an error string if the (module, tok) invocation is not registry-valid."""
    if module is None:
        # root form `python -m harness_maker <cmd>` → Typer alias set.
        if tok and _WORD.match(tok) and tok not in cr.TYPER_ALIASES:
            return f"python -m harness_maker {tok} (not a Typer alias)"
        return None
    if module not in cr.MODULES:
        return f"python -m harness_maker.{module} (unknown module)"
    spec = cr.MODULES[module]
    if spec.subcommands and tok and _WORD.match(tok) and tok not in spec.subcommands:
        return f"python -m harness_maker.{module} {tok} (not a subcommand)"
    return None


# ── T-C2 ──────────────────────────────────────────────────────────────────────

_GUARDED = sorted(k for k, s in cr.MODULES.items() if s.guarded)


def _entry(key: str):  # type: ignore[no-untyped-def]
    import_path = (
        "harness_maker.spec_inventory.__main__"
        if key == "spec_inventory"
        else f"harness_maker.{key}"
    )
    mod = importlib.import_module(import_path)
    return getattr(mod, cr.MODULES[key].entry)


def _invoke(key: str, args: list[str], monkeypatch: pytest.MonkeyPatch) -> int:
    fn = _entry(key)
    if "argv" in inspect.signature(fn).parameters:
        return int(fn(list(args)))
    # entry reads sys.argv (spec_quality / two_pass_review)
    monkeypatch.setattr(sys, "argv", ["prog", *args])
    return int(fn())


@pytest.mark.parametrize("key", _GUARDED)
def test_tc2_guard_is_wired_in_every_guarded_module(
    key: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # A verb owned ONLY by another module must trip the guard BEFORE the module's own
    # dispatch — safe for even mutating manual-dispatch modules (the guard returns first).
    foreign = "boundary" if key == "autopilot" else "on"
    rc = _invoke(key, [foreign], monkeypatch)
    err = capsys.readouterr().err
    assert rc == 2, f"{key}: guard not wired — foreign verb {foreign!r} was not redirected"
    assert "is not a subcommand of this module" in err
    assert "invalid choice" not in err


def _add_parser_choices(rel: str) -> set[str]:
    """Every `add_parser("<name>")` literal in a module source (AST, no execution)."""
    import ast

    src = (_SRC / rel).read_text(encoding="utf-8")
    return {
        n.args[0].value
        for n in ast.walk(ast.parse(src))
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute)
        and n.func.attr == "add_parser"
        and n.args
        and isinstance(n.args[0], ast.Constant)
        and isinstance(n.args[0].value, str)
    }


def test_tc2_subparser_registry_matches_source_bidirectionally() -> None:
    # BIDIRECTIONAL parity (review P1/P2): the registry must equal the module's real
    # add_parser set — catching BOTH phantoms (registered, not in code) AND omissions
    # (in code, not registered, e.g. spec_inventory generate-all). AST-based, so it needs
    # no invocation and no fragile dest-name introspection (validator R2-C2).
    mismatches: dict[str, dict[str, list[str]]] = {}
    for key, spec in cr.MODULES.items():
        if spec.shape != "subparser":
            continue
        rel = (
            "spec_inventory/__main__.py"
            if key == "spec_inventory"
            else f"{key.replace('.', '/')}.py"
        )
        actual = _add_parser_choices(rel)
        if actual != set(spec.subcommands):
            mismatches[key] = {
                "registry_only": sorted(set(spec.subcommands) - actual),
                "source_only": sorted(actual - set(spec.subcommands)),
            }
    assert not mismatches, f"registry↔source subparser drift: {mismatches}"


def _rel_for(key: str) -> str:
    return (
        "spec_inventory/__main__.py" if key == "spec_inventory" else f"{key.replace('.', '/')}.py"
    )


def _is_dispatch_operand(node: object) -> bool:
    """True when `node` is the argv-dispatch expression a subcommand string is tested against.

    Covers the shapes used by the manual-dispatch entries: a bare `sub`, an `argv[i]`/
    `args[i]` subscript, and `sys.argv[i]`. Matching the operand (not just "any `== str`")
    keeps unrelated string comparisons in the function body out of the extracted set.
    """
    import ast

    if isinstance(node, ast.Name) and node.id in {"sub", "action"}:
        return True
    if isinstance(node, ast.Subscript):
        base = node.value
        if isinstance(base, ast.Name) and base.id in {"argv", "args"}:
            return True
        if isinstance(base, ast.Attribute) and base.attr == "argv":  # sys.argv[i]
            return True
    return False


def _manual_dispatch_tokens(rel: str, entry: str) -> set[str]:
    """Dispatch subcommand literals inside a manual-dispatch entry function (AST, scoped).

    Extracts `<dispatch> ==/!= "<lit>"` comparison strings and `choices=[...]` list literals
    from the entry function body only — so helper-function string comparisons elsewhere in
    the module are not mistaken for subcommands.
    """
    import ast

    src = (_SRC / rel).read_text(encoding="utf-8")
    fn = next(
        (n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.FunctionDef) and n.name == entry),
        None,
    )
    assert fn is not None, f"entry {entry} not found in {rel}"
    toks: set[str] = set()
    for node in ast.walk(fn):
        if (
            isinstance(node, ast.keyword)
            and node.arg == "choices"
            and isinstance(node.value, ast.List)
        ):
            toks |= {
                e.value
                for e in node.value.elts
                if isinstance(e, ast.Constant) and isinstance(e.value, str)
            }
        if isinstance(node, ast.Compare) and all(
            isinstance(op, ast.Eq | ast.NotEq) for op in node.ops
        ):
            operands = [node.left, *node.comparators]
            strings = {
                o.value
                for o in operands
                if isinstance(o, ast.Constant) and isinstance(o.value, str)
            }
            if strings and any(_is_dispatch_operand(o) for o in operands):
                toks |= strings
    return toks


def test_tc2_manual_dispatch_registry_matches_source_bidirectionally() -> None:
    # BIDIRECTIONAL parity for manual-dispatch modules (review R2 P2), mirroring the
    # subparser gate: a real dispatch token OMITTED from the registry that collides with
    # another module's verb would false-redirect at runtime, and the old one-directional
    # (registry→source) check could not catch it. We do NOT execute these modules (worktree
    # cleanup-all/drain mutate on bare invocation, validator R2-C1) — the tokens come from a
    # scoped AST scan of the entry function's dispatch. A novel dispatch shape not covered by
    # `_is_dispatch_operand` must be added there (same maintenance contract as the registry).
    mismatches: dict[str, dict[str, list[str]]] = {}
    for key, spec in cr.MODULES.items():
        if spec.shape != "manual-dispatch":
            continue
        actual = _manual_dispatch_tokens(_rel_for(key), spec.entry)
        if actual != set(spec.subcommands):
            mismatches[key] = {
                "registry_only": sorted(set(spec.subcommands) - actual),
                "source_only": sorted(actual - set(spec.subcommands)),
            }
    assert not mismatches, f"registry↔source manual-dispatch drift: {mismatches}"


# ── negative fixtures: prove the gates actually trip (non-vacuous) ──────────────


def test_tc1_classifier_trips_on_unknown_module_and_bad_subcommand() -> None:
    assert _classify_invocation("no_such_module", "x") is not None
    assert _classify_invocation("autopilot_caps", "totally-bogus") is not None
    assert _classify_invocation(None, "not-a-typer-alias") is not None
    # valid cases stay None
    assert _classify_invocation("autopilot_caps", "boundary") is None
    assert _classify_invocation("autopilot", "on") is None
    assert _classify_invocation(None, "health") is None
    # unvalidatable runtime tokens (flags / vars) are skipped, not flagged
    assert _classify_invocation("worktree", "--root") is None
    assert _classify_invocation("worktree", "{{ slug }}") is None


def test_tc2_manual_source_scan_would_catch_a_phantom_subcommand() -> None:
    # If the registry gained a phantom manual-dispatch token, the source scan must catch it.
    src = (_SRC / "worktree.py").read_text(encoding="utf-8")
    assert '"totally-phantom-subcommand"' not in src
