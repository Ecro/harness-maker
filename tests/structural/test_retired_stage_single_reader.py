"""Every reader that turns a raw pipeline into `AtomicStage` must filter retired names first.

**The bug this exists because of.** SPEC-plan-stage-absorption retired `plan`, and the
migration was written into `interview._parse_autonomy` — one reader. Two others construct
`AtomicStage` from raw strings, and one of them is `hooks/autopilot_autoarm.py`, whose module
docstring says an invalid pipeline "is a silent no-op (never raises)" **by design**: a hook
that blocks a session is worse than a hook that does nothing. So a legacy `harness.yaml` —
and every one rendered before the removal names `plan` in `autonomy.pipeline` — made
`arm_if_persistent` throw, get swallowed, and return False. Autopilot would have silently
stopped arming for every existing user until they re-rendered, with no diagnostic anywhere.

That is `new-marker-content-field-must-update-every-reader` (count:3): a format changed and
only one of its readers was updated. The three previous fixes for that class were all "a
better hand-written list", and all three lists were wrong.

**So this gate DISCOVERS the call sites instead of listing them.** It walks the AST of every
shipped module for a call to `AtomicStage(...)` whose argument is not a literal, and requires
`drop_retired_stages` to be named in the same function. A new reader added anywhere under
`src/harness_maker/` fails here until it filters.
"""

from __future__ import annotations

import ast
from pathlib import Path

import harness_maker
from harness_maker.models import RETIRED_STAGES, AtomicStage, drop_retired_stages

_SRC = Path(harness_maker.__file__).parent
#: The module that DEFINES the enum and the filter — it constructs members by definition.
_EXEMPT = {"models.py"}


def _scopes(tree: ast.AST) -> list[ast.AST]:
    """Every function/method, plus the module itself for top-level constructions."""
    out: list[ast.AST] = [tree]
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            out.append(node)
    return out


def _models_carrying_stages() -> frozenset[str]:
    """Pydantic models with an `AtomicStage`-typed field, read off `models.py` rather than listed.

    These are the SECOND way a raw pipeline becomes `AtomicStage` members: pydantic coerces
    inside `model_validate`, so the module doing it contains no `AtomicStage(...)` call at all.
    """
    tree = ast.parse((_SRC / "models.py").read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        for stmt in node.body:
            if isinstance(stmt, ast.AnnAssign) and "AtomicStage" in ast.unparse(stmt.annotation):
                found.add(node.name)
                break
    return frozenset(found)


_STAGE_MODELS = _models_carrying_stages()


def _constructs_from_a_variable(scope: ast.AST) -> bool:
    """A raw name off a config becomes an `AtomicStage`, by either of the two routes.

    Route 1 is the explicit `AtomicStage(x)` call with a non-literal argument. Route 2 is
    `<Model>.model_validate(x)` for a model carrying an `AtomicStage` field — pydantic performs
    the same coercion with no call for a walker keyed on the enum name to find. `interview.py`
    is route 2, and while this predicate only knew route 1 that reader could hand-write its own
    filter and still leave the gate green.
    """
    for node in ast.walk(scope):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if (
            isinstance(func, ast.Attribute)
            and func.attr in {"model_validate", "model_validate_json"}
            and isinstance(func.value, ast.Name)
            and func.value.id in _STAGE_MODELS
            and node.args
            and not isinstance(node.args[0], ast.Constant)
        ):
            return True
        name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", None)
        if name != "AtomicStage" or not node.args:
            continue
        if not isinstance(node.args[0], ast.Constant):
            return True
    return False


def _names_the_filter(scope: ast.AST) -> bool:
    return any(
        (isinstance(n, ast.Name) and n.id == "drop_retired_stages")
        or (isinstance(n, ast.Attribute) and n.attr == "drop_retired_stages")
        for n in ast.walk(scope)
    )


def _dynamic_readers() -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    for path in sorted(_SRC.rglob("*.py")):
        if path.name in _EXEMPT:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for scope in _scopes(tree):
            if _constructs_from_a_variable(scope):
                found.append((path.name, getattr(scope, "name", "<module>")))
    return found


def test_every_dynamic_atomicstage_construction_filters_retired_names() -> None:
    offenders: list[str] = []
    for path in sorted(_SRC.rglob("*.py")):
        if path.name in _EXEMPT:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for scope in _scopes(tree):
            if _constructs_from_a_variable(scope) and not _names_the_filter(scope):
                offenders.append(f"{path.relative_to(_SRC)}::{getattr(scope, 'name', '<module>')}")
    assert not offenders, (
        "these build AtomicStage from a non-literal without calling drop_retired_stages, so a "
        f"legacy pipeline naming a retired stage reaches the enum: {offenders}"
    )


def test_the_discovery_actually_finds_the_known_readers() -> None:
    """A walker that finds nothing would pass the gate above while asserting nothing."""
    names = {mod for mod, _ in _dynamic_readers()}
    assert "autopilot_autoarm.py" in names, (
        "the walker no longer sees the silent-no-op hook — the one reader whose failure mode "
        "has no diagnostic at all"
    )
    assert "autopilot.py" in names
    assert "interview.py" in names, (
        "the walker no longer sees the pydantic-coercion reader — the one that has no "
        "`AtomicStage(...)` call to find, and so was silently exempt while it hand-wrote its "
        'own `!= "plan"` filter'
    )


def test_the_stage_carrying_models_are_discovered_not_listed() -> None:
    """A walker with an empty model set would pass the gate above while asserting nothing."""
    assert "AutonomyConfig" in _STAGE_MODELS, (
        f"no model with an AtomicStage field was found in models.py; got {sorted(_STAGE_MODELS)}"
    )


def test_the_filter_splits_kept_from_dropped() -> None:
    kept, dropped = drop_retired_stages(["research", "plan", "spec"])
    assert kept == ["research", "spec"]
    assert dropped == ["plan"]


def test_the_filter_is_idempotent() -> None:
    once, _ = drop_retired_stages(["research", "plan", "spec"])
    twice, dropped_again = drop_retired_stages(list(once))
    assert twice == once
    assert dropped_again == [], "a migrated pipeline must report nothing left to drop"


def test_no_retired_name_is_still_a_live_enum_member() -> None:
    """The two halves must not drift: a name cannot be both retired and constructible."""
    live = {m.value for m in AtomicStage}
    assert not (live & RETIRED_STAGES), (
        f"{sorted(live & RETIRED_STAGES)} is in RETIRED_STAGES and still a live stage — the "
        "filter would strip a stage the render still produces"
    )
