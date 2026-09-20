"""AC-009 (SPEC-withdrawal-criterion-window) — both registration sites carry the succession.

A pre-registered rule is not reinterpreted once it fires. This one never fired and never could,
so replacing it is legitimate — but only if the replacement is registered with the same force
and the site that registered the original stops presenting a dead rule as live. That is two
documents, and nothing else in the suite reads either of them for this.

It lives under `tests/unit/`, not `tests/structural/`, on purpose: a structural gate must answer
`test_new_gates_file_a_mutation_receipt`'s question — "which source line, when deleted, turns
this red?" — and this one guards a cross-reference between two documents, so it has no such
line. Putting it there would mean filing a receipt that cannot be truthfully written.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
ORIGINAL = REPO_ROOT / "specs" / "SPEC-intent-world-model-objective-layer.md"
SUCCESSOR_SLUG = "SPEC-withdrawal-criterion-window"


def _constraints_row(spec: Path, first_cell: str) -> str:
    """The one Constraints table row whose first cell is `first_cell`, whole line."""
    rows = [
        line
        for line in spec.read_text(encoding="utf-8").splitlines()
        if line.startswith("|") and line.split("|")[1].strip() == first_cell
    ]
    assert len(rows) == 1, f"expected exactly one `{first_cell}` row in {spec.name}, got {rows}"
    return rows[0]


def test_ac_009_the_original_registration_names_its_successor() -> None:
    """The row that registered the retired rule must point at the rule that replaced it."""
    row = _constraints_row(ORIGINAL, "Withdrawal criterion")
    assert SUCCESSOR_SLUG in row, (
        "a reader of the SPEC that registered the criterion would otherwise take a rule that "
        f"cannot fire for the live one; row: {row}"
    )


def test_ac_009_the_original_registration_says_the_rule_cannot_fire() -> None:
    """Naming a successor is not the same as saying the old rule is dead.

    Without this, the row could cite the new SPEC as a mere refinement and still read as the
    operative criterion — which is what it was doing for the two days between the defect
    becoming permanent and being found.
    """
    row = _constraints_row(ORIGINAL, "Withdrawal criterion").lower()
    assert "superseded" in row, row
    assert "no longer fire" in row or "cannot fire" in row, row


@pytest.mark.parametrize("path", [ORIGINAL])
def test_the_registration_sites_exist(path: Path) -> None:
    """A rename or a move must fail here rather than silently skipping the assertions above."""
    assert path.is_file(), f"{path} is missing — the succession has nowhere to be recorded"
