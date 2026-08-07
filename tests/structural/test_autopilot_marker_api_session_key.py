"""Import-graph gate — every autopilot marker-API call must pass a session key.

PLAN-multisession-marker-scoping ADR-009. `[fail:design]
new-marker-content-field-must-update-every-reader` is at count:3, and all three
mitigations tried so far were hand-written enumerations that were themselves wrong —
the third instance (`hooks/autopilot_autoarm.py`) was missed by a list written inside
the PLAN that cites the class, because that list omitted `write`, the only API the
missed module calls.

So this test DISCOVERS its own subjects: it walks `src/harness_maker/`, finds every
module that imports `harness_maker.autopilot` (by AST, not grep), and asserts that
every call into the session-keyed marker API passes a session key. A consumer added
later is in the subject set the moment it imports the module — no edit here, and no
edit to the PLAN.

`resolve_marker_root` is deliberately NOT in the keyed set: it resolves a project
ROOT, takes no marker key, and gaining one would be meaningless. The second test below
pins that so the exclusion is an assertion rather than an omission.
"""

from __future__ import annotations

import ast
from pathlib import Path

import harness_maker

SRC = Path(harness_maker.__file__).parent

#: Marker APIs whose result depends on WHICH session is asking.
KEYED_APIS: frozenset[str] = frozenset(
    {
        "active_marker",
        "clear",
        "effective_level",
        "gc_stale_marker",
        "load",
        "marker_path",
        "other_keyed_markers",
        "set_task_slug",
        "status",
        "touch",
        "write",
    }
)

#: Either spelling counts — `write` names its parameter `claude_session_id`.
KEY_KWARGS: frozenset[str] = frozenset({"session_id", "claude_session_id"})

#: No session key, by design. `resolve_marker_root` resolves a project ROOT.
#: `gc_expired_markers` is the OPERATOR sweep `prune_stale` owns — ADR-013 scopes a
#: SESSION's unlink authority, not the operator's, and it deletes only TTL-expired
#: markers, so keying it to a caller would defeat its whole purpose (a crashed session
#: never returns to collect its own file).
KEYLESS_APIS: frozenset[str] = frozenset({"resolve_marker_root", "gc_expired_markers"})


def _modules() -> list[Path]:
    return sorted(p for p in SRC.rglob("*.py") if p.name != "autopilot.py")


def _imports_autopilot(tree: ast.Module) -> dict[str, str]:
    """`{local_name: original_name}` for every binding to autopilot or one of its members.

    The mapping, not a bare set, is what makes an ALIASED import visible (review round 1,
    CR-3): `from harness_maker.autopilot import load as _load` binds `_load`, and a guard
    that compares the LOCAL name against `KEYED_APIS` never matches it — so the one shape
    that hides a call from this test would have sailed through the test.
    """
    names: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module in (
            "harness_maker",
            "harness_maker.autopilot",
        ):
            for alias in node.names:
                if node.module == "harness_maker" and alias.name != "autopilot":
                    continue
                names[alias.asname or alias.name] = alias.name
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "harness_maker.autopilot":
                    names[alias.asname or "harness_maker.autopilot"] = "autopilot"
                elif alias.name == "harness_maker" and alias.asname is None:
                    # `import harness_maker` then `harness_maker.autopilot.load(...)` —
                    # a dotted chain the Name-only matcher below cannot see (round 2).
                    names["harness_maker.autopilot"] = "autopilot"
    return names


def _module_ref(func: ast.expr) -> str | None:
    """Dotted spelling of an attribute's base: `autopilot` or `harness_maker.autopilot`."""
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        inner = _module_ref(func.value)
        return f"{inner}.{func.attr}" if inner else None
    return None


def _is_literal_none_or_empty(node: ast.expr) -> bool:
    """A key argument hardcoded to `None` / `""` is a session key in name only."""
    return isinstance(node, ast.Constant) and node.value in (None, "")


def _offenders(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    bound = _imports_autopilot(tree)
    if not bound:
        return []
    module_aliases = {
        local for local, orig in bound.items() if orig in ("autopilot", "harness_maker.autopilot")
    }
    # local -> ORIGINAL name, so an alias is checked against the API it actually calls.
    direct = {local: orig for local, orig in bound.items() if local not in module_aliases}
    bad: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Attribute):
            base = _module_ref(func.value)
            if base not in module_aliases or func.attr not in KEYED_APIS:
                continue
            name = func.attr
        elif isinstance(func, ast.Name) and direct.get(func.id) in KEYED_APIS:
            name = direct[func.id]
        else:
            continue
        keys = [kw for kw in node.keywords if kw.arg in KEY_KWARGS]
        if not keys:
            bad.append(f"{path.relative_to(SRC)}:{node.lineno} {name}() — no session key")
        elif all(_is_literal_none_or_empty(kw.value) for kw in keys):
            # `clear(root, session_id=None)` type-checks and reads as compliant while
            # resolving to the degraded file — the exact shape of the `autopilot off`
            # regression (SR-1). Passing the key is not the same as passing an id.
            bad.append(f"{path.relative_to(SRC)}:{node.lineno} {name}() — key hardcoded None/''")
    return bad


def test_every_autopilot_consumer_passes_a_session_key() -> None:
    offenders = [item for path in _modules() for item in _offenders(path)]
    assert not offenders, (
        "autopilot marker-API calls without a session key (the marker is per-session "
        "since PLAN-multisession-marker-scoping ADR-001; an unkeyed call silently reads "
        "the degraded fallback file):\n  " + "\n  ".join(offenders)
    )


def test_the_gate_actually_sees_the_known_consumers() -> None:
    """A discovery test that discovers nothing is a green light over a blind spot."""
    seen = {
        p.relative_to(SRC).as_posix()
        for p in _modules()
        if _imports_autopilot(ast.parse(p.read_text(encoding="utf-8")))
    }
    for expected in (
        "autopilot_caps.py",
        "cli.py",
        "gates/permission_gate.py",
        "hooks/autopilot_autoarm.py",
    ):
        assert expected in seen, f"{expected} dropped out of the autopilot import graph"


def test_keyed_api_set_covers_every_public_marker_function() -> None:
    """A NEW public function that touches the marker path must join KEYED_APIS."""
    tree = ast.parse((SRC / "autopilot.py").read_text(encoding="utf-8"))
    missing: list[str] = []
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef) or node.name.startswith("_"):
            continue
        if node.name in KEYED_APIS or node.name in KEYLESS_APIS:
            continue
        body = ast.dump(node)
        if "'marker_path'" in body or "_MARKER_" in body:
            missing.append(node.name)
    assert not missing, (
        "public autopilot functions touching the marker path but absent from "
        f"KEYED_APIS/KEYLESS_APIS: {missing}"
    )


def test_resolve_marker_root_stays_key_free() -> None:
    import inspect

    from harness_maker import autopilot

    params = inspect.signature(autopilot.resolve_marker_root).parameters
    assert not (set(params) & KEY_KWARGS)


# --- the guard's own guards (round 2) ------------------------------------------------
#
# Every shape below is ABSENT from `src/` today, so the handling for it is unfalsifiable by
# the repo scan alone: it would pass identically if the handling were deleted. Feeding
# synthetic sources through the same `_offenders` logic is what gives it teeth.


def _offenders_from_source(src: str, tmp_path: Path) -> list[str]:
    module = tmp_path / "probe.py"
    module.write_text(src, encoding="utf-8")
    real = globals()["SRC"]
    globals()["SRC"] = tmp_path
    try:
        return _offenders(module)
    finally:
        globals()["SRC"] = real


def test_an_aliased_import_is_still_caught(tmp_path: Path) -> None:
    src = "from harness_maker.autopilot import load as _load\n_load(root)\n"
    assert _offenders_from_source(src, tmp_path), "an aliased keyed call slipped through"


def test_a_dotted_module_call_is_still_caught(tmp_path: Path) -> None:
    src = "import harness_maker\nharness_maker.autopilot.load(root)\n"
    assert _offenders_from_source(src, tmp_path), "a dotted keyed call slipped through"


def test_a_hardcoded_none_key_is_caught(tmp_path: Path) -> None:
    src = "from harness_maker import autopilot\nautopilot.clear(root, session_id=None)\n"
    assert _offenders_from_source(src, tmp_path), "a literal-None key read as compliant"


def test_a_real_key_is_not_flagged(tmp_path: Path) -> None:
    """The negative control — without it the three tests above pass on a matcher that flags
    everything."""
    src = "from harness_maker import autopilot\nautopilot.clear(root, session_id=sid)\n"
    assert not _offenders_from_source(src, tmp_path)
