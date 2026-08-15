"""The allowance mechanism itself.

Without these, a silently-ignored block reads as a tighter budget.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from harness_maker.surface_allowance import (
    AllowanceError,
    aggregate_headroom,
    command_headroom,
    load_active_allowances,
)

_DELTA = "BASELINE-DELTA-demo.md"


def _plan(root: Path, slug: str, *, status: str, block: str | None) -> Path:
    docs = root / "work-docs"
    docs.mkdir(parents=True, exist_ok=True)
    (docs / _DELTA).write_text("attribution\n", encoding="utf-8")
    body = f"---\ntype: plan\ntask_slug: {slug}\nstatus: {status}\n"
    if block is not None:
        body += block
    body += "---\n\n# PLAN\n"
    path = docs / f"PLAN-{slug}.md"
    path.write_text(body, encoding="utf-8")
    return path


_VALID = (
    "surface_allowance:\n  chars: 732\n  commands:\n    review: 700\n"
    f'  reason: "two clauses that cannot be cut"\n  delta_doc: {_DELTA}\n'
)


def test_an_in_flight_plan_grants_headroom(tmp_path: Path) -> None:
    _plan(tmp_path, "demo", status="planning", block=_VALID)
    assert aggregate_headroom(tmp_path) == 732
    assert command_headroom(tmp_path, "review") == 700
    assert command_headroom(tmp_path, "wrapup") == 0


def test_a_completed_plan_grants_nothing(tmp_path: Path) -> None:
    """The expiry IS the mechanism.

    Without it every landed PLAN's headroom would persist and the sum would only ever
    grow — which is a re-freeze paid in instalments, the thing this replaces.
    """
    _plan(tmp_path, "demo", status="complete", block=_VALID)
    assert aggregate_headroom(tmp_path) == 0
    assert load_active_allowances(tmp_path) == []


def test_a_plan_without_the_block_grants_nothing(tmp_path: Path) -> None:
    _plan(tmp_path, "demo", status="planning", block=None)
    assert aggregate_headroom(tmp_path) == 0


def test_headroom_sums_across_concurrent_plans(tmp_path: Path) -> None:
    _plan(tmp_path, "alpha", status="planning", block=_VALID)
    _plan(tmp_path, "beta", status="planning", block=_VALID)
    assert aggregate_headroom(tmp_path) == 1464
    assert command_headroom(tmp_path, "review") == 1400


def test_an_absent_work_docs_dir_is_not_an_error(tmp_path: Path) -> None:
    """A consuming project need not use PLAN documents at all."""
    assert aggregate_headroom(tmp_path) == 0


@pytest.mark.parametrize(
    ("block", "fragment"),
    [
        (
            f'surface_allowance:\n  reason: "r"\n  delta_doc: {_DELTA}\n',
            "missing required key 'chars'",
        ),
        (f'surface_allowance:\n  chars: 0\n  reason: "r"\n  delta_doc: {_DELTA}\n', "positive int"),
        (
            f'surface_allowance:\n  chars: -5\n  reason: "r"\n  delta_doc: {_DELTA}\n',
            "positive int",
        ),
        (
            f'surface_allowance:\n  chars: true\n  reason: "r"\n  delta_doc: {_DELTA}\n',
            "positive int",
        ),
        (
            f'surface_allowance:\n  chars: 10\n  reason: ""\n  delta_doc: {_DELTA}\n',
            "non-empty string",
        ),
        (
            'surface_allowance:\n  chars: 10\n  reason: "r"\n  delta_doc: nope.md\n',
            "does not exist",
        ),
        (
            f'surface_allowance:\n  chars: 10\n  reason: "r"\n  delta_doc: {_DELTA}\n'
            "  commands:\n    review: 0\n",
            "positive int",
        ),
        ("surface_allowance: 732\n", "must be a mapping"),
    ],
)
def test_a_malformed_block_is_loud(tmp_path: Path, block: str, fragment: str) -> None:
    """Never a silent zero.

    A malformed allowance that resolved to 0 would surface as the budget refusing a
    change, and the author would go looking at the ratchet instead of their own
    frontmatter — the wrong place, at the worst moment.
    """
    _plan(tmp_path, "demo", status="planning", block=block)
    with pytest.raises(AllowanceError, match=re.escape(fragment)):
        aggregate_headroom(tmp_path)


def test_a_missing_delta_doc_is_rejected(tmp_path: Path) -> None:
    """The attribution is the point; a number with no document is what this replaces."""
    _plan(tmp_path, "demo", status="planning", block=_VALID)
    (tmp_path / "work-docs" / _DELTA).unlink()
    with pytest.raises(AllowanceError, match="does not exist"):
        aggregate_headroom(tmp_path)
