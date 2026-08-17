"""AC-001 — the suite structurally cannot append to the base repo's second-opinion ledger.

The leak is measured, not hypothetical: on 2026-08-17 the live ledger held 150 rows written
by this suite, and a naive per-model read reported codex at 64.9% loss where the truth was
1.3%. The shape is `second_opinion_invoke.main()`/`.invoke()` called with no `base_root` and
no `chdir`, so base-root resolution walks up to the enclosing checkout.

Three things this module deliberately does NOT do, each rejected for a recorded reason:

* It does not compare the base ledger before and after. That file is append-only and shared;
  a concurrent session's legitimate row fails a byte or row-count comparison with no test at
  fault, and a flaky gate on the suite's foundational invariant gets weakened rather than
  fixed.
* It does not look for a "test-owned marker" on rows. `codex_ledger.SecondOpinionRecord` is
  `strict=True, extra="forbid"`, so there is no field to carry one; what remains is a
  per-test slug convention — a hand list of the sites that remembered to opt in, which is the
  failure mode a suite-wide invariant exists to avoid.
* **No test requests the redirect fixture by name.** A test that names its sandbox is
  satisfied by an ordinary non-autouse fixture, i.e. by the per-test opt-in AC-001 forbids.

**The subject is `codex_ledger.emit`, not `resolve_base_root`.** An earlier version of this
module policed the resolver, and Phase D — not any of four review rounds — found two
regressions: `mutation_receipt._base_root` calls that resolver at call time to locate a
COMMITTED ledger, and a root-conftest import of `second_opinion_invoke` collapsed
`test_dep_map`'s targeted selection to the whole tests tree. A general-purpose resolver has
consumers beyond the thing being isolated; the append does not.
"""

from __future__ import annotations

import ast
import json
import subprocess
from pathlib import Path

import pytest

import harness_maker.second_opinion_invoke as soi

_TESTS_ROOT = Path(__file__).resolve().parents[1]
_CONFTEST = _TESTS_ROOT / "conftest.py"
_REPO_ROOT = _TESTS_ROOT.parent


def _rows_under(root: Path) -> list[dict[str, object]]:
    """Every second-opinion row anywhere beneath `root`."""
    rows: list[dict[str, object]] = []
    for path in sorted(root.rglob("second-opinion.jsonl")):
        rows += [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    return rows


# ── behaviour: the write lands in pytest's tmp area, never in this checkout ────


def test_leaking_invoker_call_lands_in_tmp_path(tmp_path: Path) -> None:
    """The canary reproduces the leak shape verbatim: no base_root, no chdir.

    `tmp_path` is requested to READ the outcome, not to obtain the redirect — the redirect is
    autouse and applies whether or not a test asks. `--prompt-file` points at a path that does
    not exist, which is the real leak site's shape (`test_unreadable_prompt_file_*`): the
    invoker degrades to a `skipped` row and emits it, which is exactly the write being proven
    unable to escape.
    """
    rc = soi.main(
        [
            "--model",
            "codex",
            "--prompt-file",
            str(tmp_path / "does-not-exist.txt"),
            "--slug",
            "hm-ledger-canary",
            "--stage",
            "review",
        ]
    )
    assert rc == 0, "the invoker degrades gracefully; a non-zero exit means bad arguments"

    assert [r["slug"] for r in _rows_under(tmp_path)] == ["hm-ledger-canary"], (
        "the row did not land under this test's tmp_path — the append escaped the redirect, "
        "which means it reached the enclosing repository instead"
    )


def test_the_direct_invoke_entry_point_is_redirected_too(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`invoke()` emits its own row; a redirect wrapping only `main()` would miss it.

    `invoke()` is the entry point the rendered stage recipes call, so a redirect narrower
    than the emit boundary leaks here while the canary above stays green.

    **The CLI boundary is stubbed, and that is not incidental.** Unstubbed, `invoke()` reaches
    `subprocess.run(argv, …, timeout=CODEX_TIMEOUT_S)` — a real, paid `codex exec` on every
    suite run, whose outcome depends on whether the operator has the CLI installed and is
    logged in. CLAUDE.md's policy is mock-first for unit tests. The stub writes the
    `--output-last-message` FILE rather than stdout, because that is the channel the codex
    branch actually reads; an earlier stub returned the payload on stdout and made the status
    assertion unreachable by any correct implementation.
    """

    def _fake_run(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        if "--output-last-message" in argv:
            Path(argv[argv.index("--output-last-message") + 1]).write_text(
                json.dumps({"findings": []}), encoding="utf-8"
            )
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", _fake_run)
    # Pin the config too. `invoke()` reads `<root>/.claude/harness.yaml` and can raise
    # SecondOpinionSkipError on a non-default `output_schema_path` that does not exist — so
    # `status == "invoked"` was contingent on a checked-in file OUTSIDE this worktree, and an
    # unrelated edit to it would turn this test red with no defect in the code under test.
    # Base-root resolution stays live; only the ambient input is fixed (CLAUDE.md ckpt 7).
    monkeypatch.setattr(
        soi,
        "load_config",
        lambda _root: {"codex": {"hermetic": True, "output_schema_path": soi.DEFAULT_SCHEMA_REL}},
    )

    result = soi.invoke(
        model="codex", prompt="probe", slug="hm-ledger-canary-invoke", stage="review"
    )
    assert result["status"] == "invoked", (
        "the stub returns a well-formed empty payload, so the only correct status is "
        f"'invoked' — got {result['status']!r} ({result.get('reason')!r})"
    )
    assert [r["slug"] for r in _rows_under(tmp_path)] == ["hm-ledger-canary-invoke"]


def test_a_deliberate_project_root_is_left_alone(tmp_path: Path) -> None:
    """The counterexample: a test that names its own root must keep it.

    Without this, "redirect everything" satisfies both canaries, and the fixture would break
    every test that builds its own repository — which is what happened when the redirect sat
    on the resolver.
    """
    own = tmp_path / "own-repo"
    (own / ".claude" / "observability").mkdir(parents=True)

    rc = soi.main(
        [
            "--model",
            "codex",
            "--prompt-file",
            str(tmp_path / "missing.txt"),
            "--slug",
            "hm-ledger-explicit-root",
            "--stage",
            "review",
            "--root",
            str(own),
        ]
    )
    assert rc == 0
    assert [r["slug"] for r in _rows_under(own)] == ["hm-ledger-explicit-root"], (
        "an explicit --root was overridden — the redirect cannot tell a deliberate fixture "
        "from the accidental leak"
    )


# ── structure: the redirect exists, is autouse, and nothing undoes it ──────────


def _names_ledger_emit(node: ast.AST) -> bool:
    """`codex_ledger.emit` as an attribute chain or a patch-target string.

    Deliberately NOT a bare `emit`: that name is common enough that a bare match would indict
    unrelated code, which is the over-broad-predicate mistake this gate already made once.
    """
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value.endswith("codex_ledger.emit")
    if isinstance(node, ast.Attribute) and node.attr == "emit":
        return _is_codex_ledger_ref(node.value)
    return False


def _is_codex_ledger_ref(node: ast.AST) -> bool:
    """`codex_ledger` reached as a bare name OR through a dotted module path.

    `soi.codex_ledger` is an `ast.Attribute`, not an `ast.Name`. Requiring a Name closed
    three bypass spellings and left the fourth — which is the one that already exists in the
    tree, at `tests/unit/test_second_opinion_invoke.py:826`
    (`monkeypatch.setattr(soi.codex_ledger, "emit", boom)`) — so the gate was blind to the
    nearest precedent a future author would copy.
    """
    if isinstance(node, ast.Name):
        return node.id.endswith("codex_ledger")
    return isinstance(node, ast.Attribute) and node.attr.endswith("codex_ledger")


def _autouse_fixtures(tree: ast.Module) -> dict[str, ast.FunctionDef]:
    """Fixtures declared `autouse=True`, by name — read from source, not from pytest."""
    found: dict[str, ast.FunctionDef] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        for dec in node.decorator_list:
            if isinstance(dec, ast.Call) and any(
                kw.arg == "autouse"
                and isinstance(kw.value, ast.Constant)
                and kw.value.value is True
                for kw in dec.keywords
            ):
                found[node.name] = node
    return found


def _patch_calls(fn: ast.FunctionDef) -> list[ast.Call]:
    """Every call that rebinds the emit boundary, in any spelling that actually rebinds it.

    Method form (`monkeypatch.setattr`, `mocker.patch`) and bare form (`setattr`, `patch`,
    including as a decorator) both count — an earlier version recognised only the method
    form, so three of four bypass spellings were invisible to it.
    """
    out: list[ast.Call] = []
    for node in ast.walk(fn):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute | ast.Name)):
            continue
        name = node.func.attr if isinstance(node.func, ast.Attribute) else node.func.id
        if name not in {"setattr", "object", "patch"}:
            continue
        # Dotted form: `patch("harness_maker.codex_ledger.emit", …)` or
        # `setattr(x, codex_ledger.emit)`.
        if any(_names_ledger_emit(a) for a in node.args):
            out.append(node)
            continue
        # Split form: `setattr(codex_ledger, "emit", …)` — module and attribute arrive as
        # two separate arguments, so neither one alone spells the target. This is the form
        # the conftest itself uses, and the first draft of this predicate could not see it.
        if len(node.args) >= 2:
            target, attr = node.args[0], node.args[1]
            if (
                _is_codex_ledger_ref(target)
                and isinstance(attr, ast.Constant)
                and attr.value == "emit"
            ):
                out.append(node)
    return out


def _installs_redirect(fn: ast.FunctionDef) -> bool:
    """Does this fixture PATCH the boundary — as opposed to mentioning it?

    An earlier draft searched `ast.dump(fn)` for the symbol, which a docstring reading "we do
    NOT patch it" satisfies. Only a rebinding shows a patch was installed.
    """
    if _patch_calls(fn):
        return True
    return any(
        isinstance(node, ast.Assign) and any(_names_ledger_emit(t) for t in node.targets)
        for node in ast.walk(fn)
    )


def _tainted_aliases(tree: ast.Module) -> set[str]:
    """Module-level names bound to the real `emit`.

    `_REAL = codex_ledger.emit` at module scope, then `setattr(codex_ledger, "emit", _REAL)`
    inside a test, restores the leak while presenting a bare `ast.Name` no target-spelling
    check can see. One hop, not N — a chain of aliases still escapes, and that is a stated
    limit rather than a claim of closure.
    """
    tainted: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            _names_ledger_emit(n) for n in ast.walk(node.value)
        ):
            tainted |= {t.id for t in node.targets if isinstance(t, ast.Name)}
        if isinstance(node, ast.ImportFrom) and node.module and "codex_ledger" in node.module:
            tainted |= {(a.asname or a.name) for a in node.names if a.name == "emit"}
    return tainted


def _mentions_real_emit(node: ast.AST, tainted: set[str]) -> bool:
    """Does this expression evaluate to the real `emit`, anywhere inside it?

    A subtree walk, not a single-node check: `functools.partial(codex_ledger.emit)` hides the
    attribute one level down, and the single-node version passed it.
    """
    for sub in ast.walk(node):
        if _names_ledger_emit(sub):
            return True
        if isinstance(sub, ast.Name) and sub.id in tainted:
            return True
    return False


def _restores_the_real_emit(fn: ast.FunctionDef, tainted: set[str]) -> bool:
    """Is the REPLACEMENT the real `emit` — i.e. does this undo the redirect?

    This is the property the scan must measure. Asking what the call LOOKS like indicted
    seven safe sites that patch to a `tmp_path` lambda — a tighter form of the same
    protection — while missing spellings that genuinely undo it.
    """
    for call in _patch_calls(fn):
        replacement = call.args[-1] if len(call.args) > 1 else None
        for kw in call.keywords:
            if kw.arg in {"new", "side_effect"}:
                replacement = kw.value
        if replacement is None:
            # `patch("…codex_ledger.emit")` with no replacement installs a MagicMock, which
            # writes nothing at all — a different breakage, but equally a module opting out.
            return True
        if _mentions_real_emit(replacement, tainted):
            return True
    for node in ast.walk(fn):
        if (
            isinstance(node, ast.Assign)
            and any(_names_ledger_emit(t) for t in node.targets)
            and _mentions_real_emit(node.value, tainted)
        ):
            return True
    return False


def test_the_ledger_redirect_fixture_is_autouse_and_actually_patches() -> None:
    """Structural, because behaviour alone cannot see this failure.

    If the fixture stops being autouse, every existing test keeps passing — they were never
    writing rows — and the next test that leaks does so silently. The behavioural tests above
    cannot catch that either: pytest applies an autouse fixture to them regardless, so only
    the declaration tells us the protection covers tests that never ask.
    """
    tree = ast.parse(_CONFTEST.read_text(encoding="utf-8"))

    redirecting = {
        name: fn for name, fn in _autouse_fixtures(tree).items() if _installs_redirect(fn)
    }

    assert redirecting, (
        "tests/conftest.py declares no autouse fixture that PATCHES `codex_ledger.emit`; "
        "without it a test that forgets `base_root=` appends to the real ledger"
    )


def _imports_ledger_surface(tree: ast.Module) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            if any(m in node.module for m in ("codex_ledger", "second_opinion_invoke")):
                return True
            if any(a.name in {"codex_ledger", "second_opinion_invoke"} for a in node.names):
                return True
        if isinstance(node, ast.Import) and any(
            m in a.name for a in node.names for m in ("codex_ledger", "second_opinion_invoke")
        ):
            return True
    return False


def _carries_marker(tree: ast.Module, marker: str) -> bool:
    """`@pytest.mark.<marker>` on any function, or a module-level `pytestmark`."""
    return any(isinstance(n, ast.Attribute) and n.attr == marker for n in ast.walk(tree))


def _calls_a_tainted_name(tree: ast.Module, tainted: set[str]) -> bool:
    """Does this module CALL a from-imported `emit`, rather than merely import it?"""
    return any(
        isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in tainted
        for node in ast.walk(tree)
    )


_BYPASS_SPELLINGS = (
    'def f(monkeypatch):\n    monkeypatch.setattr(codex_ledger, "emit", _REAL)\n',
    'def f():\n    setattr(codex_ledger, "emit", _REAL)\n',
    'def f():\n    patch("harness_maker.codex_ledger.emit")\n',
    "def f(monkeypatch):\n"
    "    monkeypatch.setattr(codex_ledger, 'emit', partial(codex_ledger.emit))\n",
    # The dotted-module spelling. It is last because it is the one that already exists in
    # this repository (`tests/unit/test_second_opinion_invoke.py:826`) and the one the
    # round-2 hardening missed while closing the other three.
    'def f(monkeypatch):\n    monkeypatch.setattr(soi.codex_ledger, "emit", _REAL)\n',
)


def test_the_offender_predicate_detects_every_spelling_it_claims_to() -> None:
    """A positive control, because `assert not offenders` is true for two different reasons.

    Nothing in the tree currently restores the real `emit`, so the offender scan's central
    predicate is evaluated against zero true positives — and a refactor that made it return
    `False` unconditionally would leave that scan green forever. That is the regression class
    the earlier resolver version actually hit ("defeated by one hop"), caught then by a
    throwaway probe module. This pins the same evidence in the suite instead.
    """
    for source in _BYPASS_SPELLINGS:
        tree = ast.parse("_REAL = codex_ledger.emit\n" + source)
        fn = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
        # `_tainted_aliases(tree)` ALONE — an earlier version seeded `{"_REAL"}` by hand,
        # which meant the two alias spellings passed whether or not the alias computation
        # worked. A control that supplies the answer it is checking is not a control.
        assert _restores_the_real_emit(fn, _tainted_aliases(tree)), source


def test_no_test_module_bypasses_the_ledger_redirect() -> None:
    """AC-001's third clause: the fixture is only worth what it cannot be undone by.

    An autouse fixture is overridable — a module that re-patches `emit` back to the real one,
    or a child `conftest.py` shadowing the fixture's name with a no-op body, silently restores
    the leak while every other test stays green. `conftest.py` is IN the denominator for
    exactly that reason.

    **What counts as an offender is the REPLACEMENT, not the call shape.** Patching `emit` to
    a `tmp_path`-bound stub is a redirect of its own and is fine.
    """
    installer = ast.parse(_CONFTEST.read_text(encoding="utf-8"))
    redirect_fixtures = {
        name for name, fn in _autouse_fixtures(installer).items() if _installs_redirect(fn)
    }

    offenders: list[str] = []
    candidates = sorted(_TESTS_ROOT.rglob("test_*.py")) + sorted(_TESTS_ROOT.rglob("conftest.py"))
    for path in candidates:
        if path in {Path(__file__).resolve(), _CONFTEST}:
            continue  # this module names the symbol to police it; _CONFTEST installs it
        tree = ast.parse(path.read_text(encoding="utf-8"))
        rel = path.relative_to(_TESTS_ROOT)

        for node in ast.walk(tree):
            if (
                isinstance(node, ast.FunctionDef)
                and node.name in redirect_fixtures
                and not _installs_redirect(node)
            ):
                offenders.append(f"{rel}::{node.name} (shadows the redirect fixture)")

        # A `live_ledger` decorator or module-level `pytestmark` disables the redirect for
        # that scope. No patch call is involved, so the predicates below are blind to it —
        # which is exactly how the old `live_env` reuse could have re-opened the leak with
        # this gate green.
        if _carries_marker(tree, "live_ledger"):
            offenders.append(f"{rel} (live_ledger marker — opts out of the redirect)")

        if not _imports_ledger_surface(tree):
            continue
        tainted = _tainted_aliases(tree)

        # `from harness_maker.codex_ledger import emit` binds the real function into this
        # module's globals at import time; the redirect rebinds the module ATTRIBUTE, so a
        # call through that binding is structurally immune to it. `_tainted_aliases` already
        # computes the import — nothing consumed it for this until two lenses pointed out
        # that one shipped module used the idiom as precedent.
        if tainted and _calls_a_tainted_name(tree, tainted):
            offenders.append(f"{rel} (calls a from-imported `emit`, bypassing the redirect)")

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and _restores_the_real_emit(node, tainted):
                offenders.append(f"{rel}::{node.name} (restores)")

    assert not offenders, (
        "these test functions undo the autouse redirect for their own module, restoring the "
        f"leak AC-001 exists to prevent: {offenders}"
    )


def test_the_repository_is_not_where_this_suite_writes() -> None:
    """A guard on the guard: `_REPO_ROOT` must actually be this checkout.

    If it drifted, every assertion above would still pass while measuring nothing — the
    `parents[2]` mistake this module already made once, where a worktree made a comparison
    true for the wrong reason.
    """
    assert (_REPO_ROOT / "pyproject.toml").is_file(), _REPO_ROOT
    assert Path(__file__).resolve().is_relative_to(_REPO_ROOT)
