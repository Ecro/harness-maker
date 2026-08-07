"""No test may pin a STEP NUMBER — an ordinal is prose, never a contract.

`[fail:test] test-pins-retired-implementation-name` (count:4). The class is: *the assertion
names a symbol or string that is one contingent expression of the contract, not the
contract* — a false RED, where a correct rewrite turns the suite red and the TEST is the
thing that is wrong. Instance (c) of 2026-08-01 is exactly this rule's subject: literals
like `"3. **Verify build**"` went red when a round loop was correctly renumbered.

A leading ordinal is the most volatile literal in a numbered procedure and is never the
identity of the instruction it precedes, so this rule has no legitimate exception. Prose has
been tried twice and both recurrences were committed by someone who already knew the rule.

**A second rule was specified in the backlog proposal and is deliberately NOT implemented.**
It read: flag any `assert "<lit>" not in x` whose literal appears nowhere in `src/`, on the
theory that such a pin cannot fail. Implemented and run, it flagged **19 legitimate guards** —
`assert "workflows:" not in rendered` exists precisely to keep a RETIRED axis retired, and
its literal being absent from `src/` is the correct state, not a defect. The proposal's
premise does not survive contact with the tree.

One real instance does match that shape (2026-07-26: a reworded notice left
`assert "will now ask before running" not in err` unable to fail), but the discriminator
between it and a deliberate anti-regression pin is *intent*, which is not mechanically
recoverable from the AST. Rejecting a rule that produces 19 false positives to catch 1 true
one is the right trade; it is left to review, where the docstring is visible.
"""

from __future__ import annotations

import ast
import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

#: A leading ordinal — `3. `, `12. `. Prose numbering, never an identity.
_STEP_NUMBER = re.compile(r"^\d+\. ")

#: Literals short enough to appear incidentally anywhere. A negative pin on `"x"` is not a
#: retired-name pin, and searching for it in src/ would match constantly.
_MIN_PIN_LEN = 8

#: Files whose subject IS the linting of string literals — they hold synthetic examples on
#: purpose. Reason required, never a bare path (ADR-001's "allowlists carry reasons").
_EXEMPT: dict[str, str] = {
    "tests/structural/test_no_dead_string_pins.py": (
        "this file's own synthetic fixtures are deliberately dead pins"
    ),
}


def _tracked_test_modules() -> list[Path]:
    out = subprocess.run(
        # `:(glob)` magic: without it git treats `**` as an ordinary fnmatch without
        # FNM_PATHNAME, so `tests/**/*.py` requires at least one `/` after `tests/` and
        # silently excludes `tests/conftest.py` — a gap the population assertion below
        # could not see, since it only checks a count and a member inside a subdirectory.
        ["git", "ls-files", "-z", ":(glob)tests/**/*.py"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    ).stdout
    return [REPO_ROOT / p for p in out.split("\0") if p]


def _step_numbered_literals(tree: ast.Module) -> list[tuple[int, str]]:
    return [
        (n.lineno, n.value)
        for n in ast.walk(tree)
        if isinstance(n, ast.Constant) and isinstance(n.value, str) and _STEP_NUMBER.match(n.value)
    ]


# --- population -------------------------------------------------------------------------


def test_the_test_module_population_is_not_empty() -> None:
    found = {p.relative_to(REPO_ROOT).as_posix() for p in _tracked_test_modules()}
    assert len(found) > 50, f"only {len(found)} test modules discovered — the glob is wrong"
    assert "tests/structural/test_surface_baseline.py" in found
    assert "tests/conftest.py" in found, "files directly under tests/ fell out of the glob"


# --- rule (b) ---------------------------------------------------------------------------


def test_no_test_pins_a_leading_step_number() -> None:
    offenders: list[str] = []
    for path in _tracked_test_modules():
        rel = path.relative_to(REPO_ROOT).as_posix()
        if rel in _EXEMPT:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:  # pragma: no cover
            continue
        for lineno, literal in _step_numbered_literals(tree):
            offenders.append(f"{rel}:{lineno} {literal[:60]!r}")
    assert not offenders, (
        "string literals pinned to a STEP NUMBER — an ordinal is prose and breaks on a "
        "correct renumber; pin the instruction's identity instead:\n  " + "\n  ".join(offenders)
    )


# --- ADR-002: demonstrated failure, both directions ------------------------------------


def _parse(src: str) -> ast.Module:
    return ast.parse(src)


def test_rule_b_fires_on_a_step_number() -> None:
    assert _step_numbered_literals(_parse('x = "3. **Verify build**"\n'))


def test_rule_b_does_not_fire_on_ordinary_prose() -> None:
    assert not _step_numbered_literals(_parse('x = "Verify build"\n'))
    assert not _step_numbered_literals(_parse('x = "Step 3 verify"\n'))
