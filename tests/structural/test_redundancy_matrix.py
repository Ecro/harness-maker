"""P6 / SPEC AC-007 — the matrix COVERS the shipped surface. Not whether it is right.

Two halves, and keeping them apart is the whole design:

  * **Gated** — every rendered command, agent and skill has a row, and every row is
    non-empty in four columns. Coverage is mechanical, so it can be a gate.
  * **NOT gated** — the keep/retire/merge judgment. Gating it would make the executor grade
    the homework it wrote, which is the self-referential defect AC-007's `oracle_evidence`
    exists to avoid. Two cross-model reviewers proposed gating it during plan validation
    and were rejected on exactly this ground; the rejection is recorded in the PLAN.

The subject set is derived from a **render**, and this module never parses the matrix to
decide what should be in it. A subject list read out of the matrix would make the matrix
complete by definition — the same tautology as counting emit lines with emit lines.
"""

from __future__ import annotations

import re
from functools import cache
from pathlib import Path
from tempfile import mkdtemp

import pytest

from harness_maker.interview import interview
from harness_maker.models import Preset, ProjectProfile, Target
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize

_MATRIX = Path(__file__).resolve().parents[2] / "work-docs" / "MATRIX-native-redundancy.md"
_VERDICTS = ("keep", "retire", "merge")


@cache
def _rendered_root() -> Path:
    profile = ProjectProfile(stack=["python"], scale="medium", lifecycle="active")
    answers = interview(profile, autoloop_mode=True)
    answers.targets = [Target.CLAUDE_CODE]
    bp = synthesize(profile, answers, preset=Preset.PRODUCTION)
    root = Path(mkdtemp(prefix="hm-matrix-"))
    render(bp, root / ".claude", freeze_time=DEFAULT_FREEZE_TIME)
    return root / ".claude"


@cache
def inventory() -> dict[str, frozenset[str]]:
    """The INDEPENDENT subject set — from the render, never from the matrix."""
    root = _rendered_root()
    return {
        "command": frozenset(p.stem for p in (root / "commands" / "hm").glob("*.md")),
        "agent": frozenset(p.stem for p in (root / "agents").glob("*.md")),
        "skill": frozenset(p.name for p in (root / "skills").iterdir() if p.is_dir()),
    }


@cache
def matrix_rows() -> dict[str, list[str]]:
    """Subject → its four cells, parsed from the markdown tables."""
    rows: dict[str, list[str]] = {}
    for line in _MATRIX.read_text(encoding="utf-8").splitlines():
        if not line.startswith("| `"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        # subject + the four AC-007 columns.
        if len(cells) != 5:
            continue
        m = re.match(r"^`([^`]+)`$", cells[0])
        if m:
            rows[m.group(1)] = cells
    return rows


def _subject_key(kind: str, name: str) -> str:
    return f"hm:{name}" if kind == "command" else name


# ── the gated half: coverage ──────────────────────────────────────────────────


def test_the_inventory_is_not_empty() -> None:
    """Positive control — subset checks over an empty inventory hold vacuously."""
    inv = inventory()
    assert len(inv["command"]) >= 10
    assert len(inv["agent"]) >= 10
    assert len(inv["skill"]) >= 8


def test_the_matrix_parsed_into_rows() -> None:
    """A parser that silently matched nothing would make every check below vacuous."""
    assert len(matrix_rows()) >= 40


@pytest.mark.parametrize("kind", ["command", "agent", "skill"])
def test_every_rendered_subject_has_a_row(kind: str) -> None:
    """AC-007's coverage half: subject set == union of commands, skills and agents."""
    expected = {_subject_key(kind, n) for n in inventory()[kind]}
    missing = sorted(expected - set(matrix_rows()))
    assert not missing, f"{kind}s with no matrix row: {missing}"


def test_the_matrix_has_no_rows_for_things_that_are_not_shipped() -> None:
    """Equality, not containment.

    A matrix padded with retired or imagined subjects would satisfy a subset check while
    describing a surface that does not exist — and its `retire` rows would be advice about
    nothing.
    """
    shipped = {_subject_key(k, n) for k, names in inventory().items() for n in names}
    assert not sorted(set(matrix_rows()) - shipped), "matrix rows with no rendered subject"


@pytest.mark.parametrize("column", [1, 2, 3, 4])
def test_every_row_is_non_empty_in_every_column(column: int) -> None:
    """`none` is a valid value; blank is not. An empty cell is an unanswered question."""
    blank = sorted(s for s, cells in matrix_rows().items() if not cells[column])
    assert not blank, f"rows with an empty column {column}: {blank}"


def test_every_row_carries_exactly_one_verdict() -> None:
    """Anchored on the BOLD marker, not on the bare word.

    A substring check over the cell counted `test-reviewer`'s rationale — "retirement would
    be an evidence decision" — as a second verdict. Rows carry a rationale after the verdict
    on purpose (a bare `keep` with no reason is the kind of judgment nobody can audit), so
    the marker has to be what distinguishes the verdict from prose about verdicts.
    """
    for subject, cells in matrix_rows().items():
        hits = [v for v in _VERDICTS if f"**{v}**" in cells[4]]
        assert len(hits) == 1, f"{subject}: expected exactly one bolded verdict, found {hits}"


def test_the_native_column_never_asserts_an_unchecked_absence() -> None:
    """`none` is a claim about the host. `unverified` is the honest alternative.

    The matrix's own evidence rule is that recall is inadmissible — the author's knowledge
    cutoff predates this harness version — so a row must either cite an observed capability,
    say `none`, or say `unverified`. This asserts the vocabulary exists to be used.
    """
    text = _MATRIX.read_text(encoding="utf-8")
    assert "unverified" in text, "the matrix has no way to express an unchecked cell"
    assert re.search(r"cutoff", text, re.I), "the evidence rule is not stated"


# ── the NOT-gated half, asserted as a negative ────────────────────────────────


def test_the_judgment_is_declared_out_of_scope_in_the_matrix_itself() -> None:
    """A stage-2 reader opens this file, not the SPEC.

    A table of verdicts with no caveat reads as a decision. The disclaimer has to travel
    with the artifact.
    """
    text = _MATRIX.read_text(encoding="utf-8")
    assert re.search(r"not\s+gated", text, re.I)
    assert "stage 2" in text.lower()


def test_this_module_never_reads_the_matrix_to_build_the_inventory() -> None:
    """AC-007's independence requirement, asserted against this file's own source.

    If `inventory()` ever learned its subjects from the matrix, every coverage test above
    would pass by construction and P6 would gate nothing.
    """
    source = Path(__file__).read_text(encoding="utf-8")
    body = source[source.index("def inventory(") : source.index("def matrix_rows(")]
    assert "_MATRIX" not in body, "inventory() reads the matrix — coverage became a tautology"


# ── AC-007 binding ────────────────────────────────────────────────────────────


def matrix_subjects() -> set[str]:
    return set(matrix_rows())


def rendered_commands() -> set[str]:
    return {f"hm:{n}" for n in inventory()["command"]}


def rendered_skills() -> set[str]:
    return set(inventory()["skill"])


def rendered_agents() -> set[str]:
    return set(inventory()["agent"])


def test_ac_007_redundancy_matrix_covers_surface() -> None:
    """AC-007's executable predicate, verbatim — equality, not containment."""
    assert matrix_subjects() == rendered_commands() | rendered_skills() | rendered_agents()
