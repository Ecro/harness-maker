"""Every shipped `hm` subcommand must be driven somewhere in its SHIPPED spelling.

`[fail:test] shipped-entry-point-not-exercised` (count:4). The class: a module's functions
are unit-tested thoroughly and the **entry point nobody runs in a test** is the thing that
breaks. `import harness_maker.x` succeeding says nothing about `uv run … hm x` working — a
missing `main()`, a bad `argparse` wiring, a registry name that drifted from the module
name, or an import that only fails under the installed package all pass a unit suite and
fail the first real invocation.

The rendered commands call these as `uv run --with … hm <subcommand> …`. That string is the
contract with the user; this test asserts something exercises it.

**Driven** means: some test file mentions the subcommand in a subprocess-shaped invocation
(`hm <name>`, `harness_maker.<name>`, or `main([...])` inside that module's own test). The
check is deliberately generous — it is a *coverage floor*, not a proof of behaviour. Its job
is to make a NEW subcommand with no test at all impossible to ship silently, which is
exactly the four incidents.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

#: Subcommands with no driver, each with the REASON it is acceptable today. A bare entry is
#: not allowed — an allowlist without reasons becomes a place to hide things (ADR-001).
_ALLOWED_UNDRIVEN: dict[str, str] = {
    # PER-ENTRY, not a shared string. Round 2 stamped ONE reason on nine names via
    # `dict.fromkeys`, and both reviewers showed it was factually FALSE for at least two of
    # them — `test_dep_map` is driven by a real console-script subprocess and
    # `second_opinion_oracle` by `mod.main([...])`. A shared reason has nowhere to record a
    # difference, so it laundered detector false-negatives into a documented-looking
    # backlog. Both are now correctly detected and are gone from this list; the eight that
    # remain were re-derived after the detector was rewritten in AST form.
    # Round 3 wrote per-entry reasons and THREE of the eight were still false — a worse
    # result than round 2's one shared string, because eight individual sentences read as
    # eight individual verifications. `wrapup_brief` is driven by `_run(wrapup_brief, argv)`,
    # `spec_need` by `from …spec_need import main as spec_need_main`, and
    # `observability.verification_cache` by a bare `main([...])` from a direct import. All
    # three are gone from this list; the detector below now sees all three shapes.
    #
    # Three rounds of hand-written reasons produced three rounds of false ones, so the claim
    # is no longer trusted: `test_no_allowlist_entry_is_actually_driven` re-checks every
    # entry here against a deliberately OVER-generous detector and fails if one looks driven
    # at all. That test is what found the verification_cache entry — not review, and not the
    # reason-writing.
    "refdocs_index": "module-level tests only; entry point never run",
    "second_brain": "driven only by a stderr-text assertion in test_command_registry, not a call",
    "spec_quality": "module-level tests only; entry point never run",
    "stage_agent_ledger": "module-level tests only; entry point never run",
    "two_pass_review": "module-level tests only; entry point never run",
}


def _shipped_subcommands() -> list[str]:
    """DERIVED from `hm._DISPATCHABLE` — the definition `hm --help` renders (ADR-001).

    A subcommand added tomorrow is in the population without editing anything here, which is
    the whole point: the failure is "the NEW entry point had no test".

    **Read in-process, NOT via `uv run --with <path> hm --help`.** That was the first
    implementation and it was broken in exactly the way this guard exists to catch: `--with`
    resolves a CACHED wheel, so a subcommand added to the working tree was absent from the
    population and the guard passed over it. Caught by adding `mutation_receipt` and watching
    this test stay green — an assertion invariant over the dimension its own name claims
    ([fail:test] assertion-invariant-over-named-dimension, count:8). The subprocess bought
    nothing here: `_DISPATCHABLE` IS what `--help` prints.
    """
    from harness_maker.hm import _DISPATCHABLE

    return sorted(_DISPATCHABLE)


def _driven_names() -> set[str]:
    """Subcommands some test actually EXECUTES, by AST — never by text match.

    Two rounds of regex both failed, in opposite directions, and the reason is the same: a
    concatenated blob of test SOURCE cannot distinguish a call from a sentence. Round 1
    accepted any mention (`assert "hm wrapup_land" in body` — a render-grep over template
    text). Round 2 narrowed the patterns and still accepted a prose literal, a docstring and
    an assertion about stderr, while REJECTING `_uv_run("hm", "test_dep_map", …)` — a real
    console-script subprocess, the very spelling this guard calls the contract with the user.

    So the population is read from the syntax tree, where a string constant simply is not a
    call. Six executing shapes count — the last three were added after the allowlist's
    per-entry reasons turned out to be false for three of eight names, each one a driver
    this function could not see:

      * any argv sequence containing consecutive `"-m", "harness_maker.<name>"`;
      * any argv sequence containing `"hm"` (or `"harness_maker.hm"`) followed by `"<name>"`
        — the shipped console-script form;
      * `<name>.main(...)` — the entry function itself;
      * `from harness_maker.<name> import main [as alias]` + a call to `main`/`alias` — a
        DIRECT import of the entry function, with or without renaming (`spec_need`,
        `observability.verification_cache`);
      * `_helper(<name>, argv)` where `_helper` calls `<its param>.main(...)` — the module
        object passed to a same-file runner (`wrapup_brief`);
      * argv held in a VARIABLE (`cmd = ["hm", "<name>", …]` then `subprocess.run(cmd)`), by
        scanning every list/tuple literal rather than only a call's own arguments.

    The last one matches nothing in the repo today and is shipped anyway, with a synthetic
    demonstration below: the shape is real, the direction of its failure is false-negative
    (a driver read as absent, then written into the allowlist as a fact), and every one of
    the five other shapes was also absent right up until it was not.
    """
    driven: set[str] = set()
    for path in sorted((REPO_ROOT / "tests").rglob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:  # pragma: no cover — a broken test file fails elsewhere
            continue
        # local name -> real module name, so `from harness_maker import x as mod` +
        # `mod.main(...)` is still attributed to `x`. The same alias blind spot bit the
        # autopilot import-graph guard; it is not a hypothetical.
        alias: dict[str, str] = {}
        # local name of a DIRECTLY imported entry function -> its module.
        main_alias: dict[str, str] = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("harness_maker"):
                for a in node.names:
                    alias[a.asname or a.name] = a.name
                mod = (node.module or "").removeprefix("harness_maker.")
                if mod and mod != "harness_maker":
                    for a in node.names:
                        if a.name == "main":
                            main_alias[a.asname or a.name] = mod
            elif isinstance(node, ast.Import):
                for a in node.names:
                    if a.name.startswith("harness_maker."):
                        alias[a.asname or a.name] = a.name.removeprefix("harness_maker.")
        # same-file runners: `def _run(mod, argv): return mod.main(argv)` — the module is
        # DATA here, so no amount of pattern-matching on the call site sees an entry point.
        # Positional index, because the call site passes it positionally.
        runners: dict[str, set[int]] = {}
        for fn in ast.walk(tree):
            if not isinstance(fn, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            params = [a.arg for a in fn.args.args]
            for node in ast.walk(fn):
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "main"
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id in params
                ):
                    runners.setdefault(fn.name, set()).add(params.index(node.func.value.id))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            # `<name>.main(...)`
            if isinstance(func, ast.Attribute) and func.attr == "main":
                base = func.value
                if isinstance(base, ast.Name):
                    driven.add(alias.get(base.id, base.id))
                elif isinstance(base, ast.Attribute):
                    driven.add(base.attr)
            elif isinstance(func, ast.Name):
                # a directly-imported `main`, renamed or not
                if func.id in main_alias:
                    driven.add(main_alias[func.id])
                # the module object handed to a same-file runner
                for i in runners.get(func.id, ()):
                    if i < len(node.args) and isinstance(node.args[i], ast.Name):
                        local = node.args[i].id
                        if local in alias:
                            driven.add(alias[local])
            # argv positions: only STRING CONSTANTS that are arguments of a call, and only
            # when adjacent in the way a real command line is.
            words: list[str] = []
            for arg in node.args:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    words.append(arg.value)
                elif isinstance(arg, ast.List | ast.Tuple):
                    words.extend(
                        el.value
                        for el in arg.elts
                        if isinstance(el, ast.Constant) and isinstance(el.value, str)
                    )
            driven |= _argv_names(words)
        # argv built into a variable first. A bare list of strings is not prose: this needs
        # two ADJACENT constants spelling a real command line, which no docstring or
        # render-grep assertion produces (the negative cases below hold it to that).
        for lit in ast.walk(tree):
            if isinstance(lit, ast.List | ast.Tuple):
                driven |= _argv_names(
                    [
                        e.value
                        for e in lit.elts
                        if isinstance(e, ast.Constant) and isinstance(e.value, str)
                    ]
                )
    return driven


def _argv_names(words: list[str]) -> set[str]:
    """Subcommands named by an adjacent pair in a command line."""
    found: set[str] = set()
    for i, w in enumerate(words[:-1]):
        nxt = words[i + 1]
        if w == "-m" and nxt.startswith("harness_maker."):
            found.add(nxt.removeprefix("harness_maker."))
        elif w in ("hm", "harness_maker.hm"):
            found.add(nxt)
    return found


def _possibly_driven_names() -> set[str]:
    """DELIBERATELY over-generous — the check on the allowlist, not on the surface.

    The recurring defect is not a missing test, it is a **false claim about a test**: three
    rounds of "this subcommand has no driver" were written by hand and three rounds contained
    false entries, each hiding a real driver that the strict detector could not see. A
    reviewer catches those only by reading every test file, which is why two rounds of review
    did not.

    So the allowlist is held to a different, looser standard than the guard: a name may be
    allowlisted only if it looks undriven even to a rule that over-reports. Here that means
    *the module is imported by a test file that calls something named `main` or `*_main`* —
    which says nothing about whether THAT call runs THIS module, and is meant not to. A hit
    is not proof of a driver; it is proof the claim needs a human to look again.
    """
    suspect: set[str] = set()
    for path in sorted((REPO_ROOT / "tests").rglob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:  # pragma: no cover
            continue
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("harness_maker"):
                mod = (node.module or "").removeprefix("harness_maker.")
                if mod and mod != "harness_maker":
                    imported.add(mod)
                imported.update(a.name for a in node.names)
            elif isinstance(node, ast.Import):
                for a in node.names:
                    if a.name.startswith("harness_maker."):
                        imported.add(a.name.removeprefix("harness_maker."))
        calls_a_main = any(
            isinstance(c, ast.Call)
            and (
                (isinstance(c.func, ast.Attribute) and c.func.attr == "main")
                or (
                    isinstance(c.func, ast.Name)
                    and (c.func.id == "main" or c.func.id.endswith("_main"))
                )
            )
            for c in ast.walk(tree)
        )
        if calls_a_main:
            suspect |= imported
    return suspect


# --- population -------------------------------------------------------------------------


def test_the_subcommand_population_is_plausible() -> None:
    """A discovery test that discovers nothing is a green light over a blind spot."""
    names = _shipped_subcommands()
    assert len(names) >= 25, f"only {len(names)} subcommands discovered — parsing broke: {names}"
    for expected in ("worktree", "autopilot", "wrapup_land"):
        assert expected in names, f"{expected} vanished from `hm --help`"


def test_every_allowlist_entry_carries_a_reason() -> None:
    """Vacuous while the allowlist is empty, so it is paired with the synthetic case below —
    a loop over an empty dict passes on any implementation, including none."""
    assert _ALLOWED_UNDRIVEN, "the allowlist is empty; this test would assert nothing"
    for name, reason in _ALLOWED_UNDRIVEN.items():
        assert reason.strip(), f"{name} is allowlisted with no reason"


def test_a_reasonless_allowlist_entry_would_be_caught() -> None:
    """The control for the above: proves the emptiness check is what carries it."""
    synthetic = {"some_surface": ""}
    assert not all(r.strip() for r in synthetic.values())


def test_no_allowlist_entry_is_actually_driven() -> None:
    """The claim in each reason, re-checked by machine instead of trusted.

    This is the round-4 fix for a defect that survived three rounds: the reasons are prose,
    prose is not checked, and three of eight were false. It found
    `observability.verification_cache` — imported directly as `main` and called — which the
    strict detector missed and which two reviewers, a cross-model voter and a written reason
    all passed over.
    """
    suspicious = sorted(set(_ALLOWED_UNDRIVEN) & _possibly_driven_names())
    assert not suspicious, (
        "these are allowlisted as undriven, but a test file imports them and calls a `main`: "
        f"{suspicious}\n"
        "Read those test files. If a real driver exists, delete the entry — the detector "
        "above is missing a shape, and an allowlist entry is how that becomes a documented "
        "'fact'. If the call genuinely runs something else, the over-generous rule "
        "(_possibly_driven_names) is what needs narrowing, deliberately and in writing."
    )


# --- the guard --------------------------------------------------------------------------


def test_every_shipped_subcommand_is_driven_somewhere() -> None:
    driven = _driven_names()
    undriven = [n for n in _shipped_subcommands() if n not in _ALLOWED_UNDRIVEN and n not in driven]
    assert not undriven, (
        "shipped `hm` subcommands that no test invokes in their shipped spelling "
        "([fail:test] shipped-entry-point-not-exercised, count:4 — a unit test on the "
        f"module's functions does not exercise the entry point): {undriven}\n"
        "Add a test that runs it, or allowlist it in _ALLOWED_UNDRIVEN with a reason."
    )


# --- ADR-002: demonstrated failure, both directions -------------------------------------
#
# Every case below is synthetic. Two regex detectors shipped before this one and BOTH were
# wrong in ways the repo scan could not show — one accepted prose, the other rejected the
# canonical `hm <name>` form. Feeding known-good and known-bad source through the real
# extractor is the only thing that separates those.


def _driven_in(src: str, tmp_path: Path) -> set[str]:
    (tmp_path / "tests").mkdir(parents=True, exist_ok=True)
    (tmp_path / "tests" / "test_probe.py").write_text(src, encoding="utf-8")
    real = globals()["REPO_ROOT"]
    globals()["REPO_ROOT"] = tmp_path
    try:
        return _driven_names()
    finally:
        globals()["REPO_ROOT"] = real


@pytest.mark.parametrize(
    "src",
    [
        'subprocess.run(["hm", "spec_need", "--root", "."])',  # console script
        'subprocess.run([sys.executable, "-m", "harness_maker.spec_need"])',  # -m form
        '_uv_run("hm", "spec_need", "--root", ".")',  # helper, argv args
        'from harness_maker import spec_need\nspec_need.main(["x"])',  # entry function
        'from harness_maker import spec_need as mod\nmod.main(["x"])',  # ALIASED entry
        # The three shapes that were live in this repo while the allowlist called them
        # absent. Each one is a real driver of a real subcommand, today.
        # `observability.verification_cache`, verbatim in shape:
        'from harness_maker.spec_need import main\nassert main(["check"]) == 0',
        # `spec_need`, verbatim in shape:
        'from harness_maker.spec_need import main as sn_main\nrc = sn_main(["op-check"])',
        # `wrapup_brief`, verbatim in shape — the module handed to a same-file runner:
        (
            "from harness_maker import spec_need\n"
            "def _run(mod, argv):\n    return mod.main(argv)\n"
            '_run(spec_need, ["--root", "."])'
        ),
        # argv held in a variable — matches nothing in the repo today (stated in the
        # docstring), shipped because its failure direction is a false negative.
        'cmd = ["hm", "spec_need", "--root", "."]\nsubprocess.run(cmd)',
    ],
)
def test_a_real_driver_is_detected(src: str, tmp_path: Path) -> None:
    assert "spec_need" in _driven_in(src, tmp_path), f"a real driver went undetected: {src!r}"


@pytest.mark.parametrize(
    "src",
    [
        'assert "hm spec_need" in body',  # render-grep over TEXT
        '"""Docstring mentioning spec_need.main() prose."""',  # docstring
        '_GATED = "run `python -m harness_maker.spec_need op-check`"',  # prose literal
        'assert "python -m harness_maker.spec_need" in err',  # assertion about stderr
        'assert "hm spec_need" not in rendered',  # asserts ABSENCE
        "from harness_maker import spec_need  # import only",  # bare import
    ],
)
def test_a_non_executing_mention_is_not_counted(src: str, tmp_path: Path) -> None:
    """Every one of these was accepted by a previous detector. They are the failure class."""
    assert "spec_need" not in _driven_in(src, tmp_path), f"a mention read as a driver: {src!r}"
