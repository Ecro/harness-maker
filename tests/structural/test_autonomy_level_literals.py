"""ADR-005 — the autonomy level strings live in exactly two places, found by walking the AST.

Before this, `("gated", "auto_safe", "full")` was restated in nine spots across six modules:
two Literal annotations and a `cast` in `autopilot.py`, an argparse `choices`, a Typer help
string, `cli.valid_levels`, `_ARMED_LEVELS`, the autoarm hook's if/elif ladder, and
`_ask_autonomy`. Adding `auto_full` meant finding all nine. The ladder alone would have made
the flagship level silently never arm.

The point is that the guard **discovers** rather than remembering. Every previous fix of this
class shipped a better hand-list, and every hand-list was wrong by the next change — see
`[fail:design] new-marker-content-field-must-update-every-reader` (count:3), whose real fix was
also an import-graph test rather than a longer docstring.

Threshold ≥2, not ≥1, because a single level string is ordinary code: `if level == "gated"`,
`{"gated": ...}` defaults, a log line naming one value. Two or more in one node is an
enumeration, and an enumeration is what goes stale.
"""

from __future__ import annotations

import ast
import textwrap
from pathlib import Path

from harness_maker.models import OPERATIONAL_LEVELS

_SRC = Path(__file__).resolve().parents[2] / "src" / "harness_maker"

# `full` and `ask` are in the trigger set on purpose. `full` is the retired spelling — a
# module still enumerating it has not been migrated; `ask` is yaml-only, and a runtime
# surface that lists it alongside operational levels is offering something it cannot honour.
_TRIGGERS = frozenset(OPERATIONAL_LEVELS) | {"ask", "full"}
_THRESHOLD = 2

# The two nodes that are ALLOWED to enumerate. Both are in models.py and both are the
# definition itself; everything else must derive from them.
_ALLOWED = {
    ("models.py", "OperationalLevel"),
    ("models.py", "AutonomyLevel"),
    # The alias map: `full` → `auto_safe`. Definitional by the same argument — it is
    # the one place the retired spelling is allowed to be named.
    ("models.py", "LEGACY_LEVEL_ALIASES"),
}


def _enumerating_nodes(tree: ast.AST, rel: str) -> list[tuple[str, int, str]]:
    """Statements whose source text spells out ≥2 trigger strings."""
    found: list[tuple[str, int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.stmt):
            continue
        # Only leaf-ish statements: walking a whole function body would count the module.
        if _count(node) < _THRESHOLD:
            continue
        # A compound statement (if/def/class) reports its own line but contains its children's
        # literals; attribute the hit to the innermost statement instead.
        inner = [
            c
            for c in ast.walk(node)
            if isinstance(c, ast.stmt) and c is not node and _count(c) >= _THRESHOLD
        ]
        if inner:
            continue
        found.append((rel, node.lineno, _name_of(node)))
    return found


def _count(node: ast.AST) -> int:
    """DISTINCT trigger values, not occurrences.

    `{"full": "full"}` and a `try/except` that pins `gated` on both arms are one value used
    twice, not an enumeration — and counting occurrences flagged both, plus
    `synthesize._COMMUNICATION_VARIANT`, whose `"full"` is a communication variant that merely
    shares a spelling with the retired level. A guard whose first run is mostly false
    positives gets its allowlist padded until it means nothing.
    """
    return len(
        {
            n.value
            for n in ast.walk(node)
            if isinstance(n, ast.Constant) and isinstance(n.value, str) and n.value in _TRIGGERS
        }
    )


def _name_of(node: ast.stmt) -> str:
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        return node.target.id
    if isinstance(node, ast.Assign) and node.targets and isinstance(node.targets[0], ast.Name):
        return node.targets[0].id
    return type(node).__name__


def _scan(root: Path) -> list[tuple[str, int, str]]:
    hits: list[tuple[str, int, str]] = []
    for py in sorted(root.rglob("*.py")):
        rel = str(py.relative_to(root))
        hits.extend(_enumerating_nodes(ast.parse(py.read_text(encoding="utf-8")), rel))
    return hits


def test_only_the_two_definitions_enumerate_the_levels() -> None:
    offenders = [h for h in _scan(_SRC) if (h[0], h[2]) not in _ALLOWED]
    assert not offenders, (
        "these restate the autonomy levels instead of deriving them from "
        "models.OPERATIONAL_LEVELS / OperationalLevel / AutonomyLevel:\n"
        + "\n".join(f"  {f}:{line} ({name})" for f, line, name in offenders)
    )


def test_both_allowlisted_definitions_are_actually_there() -> None:
    """Otherwise a rename empties the scan and the test above passes by finding nothing."""
    found = {(h[0], h[2]) for h in _scan(_SRC)}
    assert found >= _ALLOWED, f"allowlisted definitions missing from the scan: {_ALLOWED - found}"


def test_the_guard_bites(tmp_path: Path) -> None:
    """A discovery test nobody has seen fail is a hand-list with extra steps.

    This re-adds the exact shape that was deleted — the autoarm hook's ladder — and asserts
    the scan reports it.
    """
    (tmp_path / "regression.py").write_text(
        textwrap.dedent(
            """
            def pick(level: str) -> str:
                if level == "auto_safe":
                    return "auto_safe"
                elif level == "full":
                    return "full"
                return "gated"
            """
        ),
        encoding="utf-8",
    )
    assert _scan(tmp_path), "the guard did not report a re-added level ladder"


def test_two_derived_constants_agree_with_the_definitions() -> None:
    from typing import get_args

    from harness_maker.models import ARMED_LEVELS, AutonomyLevel

    assert set(get_args(AutonomyLevel)) == set(OPERATIONAL_LEVELS) | {"ask"}
    assert set(OPERATIONAL_LEVELS) - {"gated"} == ARMED_LEVELS
