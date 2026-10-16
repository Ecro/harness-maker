"""Every test a SPEC binds must exist, so deleting a test cannot silently unbind an AC.

PR-C of SPEC-hm-overhaul-p1 deleted Cursor tests that three other SPECs still listed as
`test_ids`; nothing noticed, because `mark-tested` only checks the ids it is adding. This
resolves every bound id statically (file, then class, then function, by AST) — the same nodes
`pytest --collect-only` would find, without paying for a full collection inside the suite.
"""

from __future__ import annotations

import ast
import re
from functools import cache
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
SPECS = REPO / "specs"

#: Ids already dead when this guard landed (2026-10-16), grouped by why. Shrink-only.
KNOWN_DEAD_FILE = Path(__file__).with_name("spec_test_ids_known_dead.txt")


def _known_dead() -> dict[str, frozenset[str]]:
    groups: dict[str, set[str]] = {}
    current = ""
    for raw in KNOWN_DEAD_FILE.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            current = line[1:-1]
            groups[current] = set()
        else:
            groups[current].add(line)
    return {k: frozenset(v) for k, v in groups.items()}


def _bound_ids() -> dict[str, list[str]]:
    """Live, already-tested bindings: superseded and still-pending ACs owe nothing yet."""
    found: dict[str, list[str]] = {}
    for path in sorted(SPECS.glob("SPEC-*.machine.yaml")):
        doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for ac in doc.get("ac") or []:
            if ac.get("superseded_by") or ac.get("pending_test"):
                continue
            for test_id in ac.get("test_ids") or []:
                found.setdefault(str(test_id), []).append(f"{path.name}:{ac.get('id')}")
    return found


@cache
def _names(path: Path) -> frozenset[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            names.add(node.name)
        elif isinstance(node, ast.ClassDef):
            names.add(node.name)
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    names.add(f"{node.name}::{item.name}")
    return frozenset(names)


def _resolves(test_id: str) -> bool:
    file, _, rest = test_id.partition("::")
    path = REPO / file
    if not path.is_file():
        return False
    if not rest:
        return True
    return re.sub(r"\[.*\]$", "", rest) in _names(path)


def _dead() -> dict[str, list[str]]:
    return {t: owners for t, owners in _bound_ids().items() if not _resolves(t)}


def _known() -> frozenset[str]:
    return frozenset().union(*_known_dead().values())


def test_the_guard_sees_real_bindings() -> None:
    bound = _bound_ids()
    assert len(bound) > 500, len(bound)
    rebound = "tests/unit/test_render.py::test_render_settings_hooks_gate_spec_gate_on_strictness"
    assert rebound in bound
    assert _resolves(rebound)
    # Negative control: a deleted test, a renamed one, and a method named without its class.
    assert not _resolves("tests/unit/test_render.py::test_no_such_test")
    assert not _resolves("tests/unit/no_such_file.py::test_x")
    assert not _resolves("tests/unit/hooks/test_loop_gate.py::test_found_in_cwd")
    assert _resolves("tests/unit/hooks/test_loop_gate.py::TestFindMarker::test_found_in_cwd")
    assert set(_known_dead()) == {"pr-c-cursor", "pre-existing"}


def test_every_bound_test_id_resolves() -> None:
    new = {t: o for t, o in _dead().items() if t not in _known()}
    assert not new, (
        "SPEC test_ids name tests that do not exist (bind the replacement with `hm spec_machine "
        "mark-tested`, or `retire` the AC):\n"
        + "\n".join(f"  {t}  <- {', '.join(o)}" for t, o in sorted(new.items()))
    )


def test_known_dead_ids_are_still_dead() -> None:
    revived = sorted(_known() - set(_dead()))
    assert not revived, (
        f"these resolve (or are unbound) now; drop them from {KNOWN_DEAD_FILE.name}: {revived}"
    )
