"""Phase 1 — the proposal backlog gets a reader (SPEC-observed-harness-gaps-salvage S1/S8, AC-001/002/012).

`pending-proposals.md` had one writer (`wrapup.md.j2`) and no reader; 20 proposals
accumulated over 89 days. These tests pin the parse rule ADR-004 states against the file's
REAL shape, which is NOT what the SPEC's §2.5 common-ground inference assumed:

- open      = `## Proposal:` headings
- triaged   = backticked names in the FIRST cell of the RESOLVED batch section's tables
- neither   = any other `##` heading (e.g. `## Backlog note`)

The third bucket is load-bearing: without it AC-002's partition is unsatisfiable, because
resolved proposals carry no heading of their own.
"""

# ruff: noqa: E501 — the _HEADING_KIND templates mirror rendered markdown table rows verbatim.

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from harness_maker.proposals import (
    count_proposals,
    list_proposals,
    parse_proposals,
    summarize_open,
)
from harness_maker.spec_machine import GoldenRow, load_golden_table

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "pending_proposals_sample.md"

#: Hand-authored from the fixture file itself (AC-001's oracle: the expected split is fixed
#: in the fixture, not produced by running the parser under test).
EXPECTED_OPEN = {"alpha-guard", "beta-guard", "gamma-guard"}
EXPECTED_TRIAGED = {"retired-one", "retired-two", "retired-three"}


# --------------------------------------------------------------------------------------
# AC-001 — `proposals list --open` lists every unresolved proposal
# --------------------------------------------------------------------------------------


def test_proposals_list_open_lists_unresolved() -> None:
    """AC-001 predicate: set(list_proposals(FIXTURE_BACKLOG, OPEN)) == EXPECTED_OPEN_SLUGS."""
    assert set(list_proposals(FIXTURE, "open")) == EXPECTED_OPEN


def test_proposals_list_triaged_reads_backticked_table_cells() -> None:
    """Retired names live in table CELLS, not headings — the SPEC's inference was wrong."""
    assert set(list_proposals(FIXTURE, "triaged")) == EXPECTED_TRIAGED


def test_triaged_ignores_backticks_in_the_shipped_as_column() -> None:
    """Only the FIRST cell names proposals; column two holds test paths, also backticked."""
    triaged = set(list_proposals(FIXTURE, "triaged"))
    assert not any("tests/structural" in name or name.endswith(".py") for name in triaged)
    assert "src/pkg/mod.py" not in triaged


def test_backlog_note_heading_is_in_neither_set() -> None:
    """`## Backlog note` is not a proposal; counting it would break AC-002's partition."""
    sets = parse_proposals(FIXTURE.read_text(encoding="utf-8"))
    assert not any("Backlog note" in n for n in sets.open)
    assert not any("Backlog note" in n for n in sets.triaged)
    assert any("Backlog note" in h for h in sets.other_headings)


def test_open_name_strips_the_trailing_date_parenthetical() -> None:
    """`## Proposal: alpha-guard (2026-01-03)` names the proposal `alpha-guard`."""
    assert "alpha-guard" in list_proposals(FIXTURE, "open")


def test_prose_mention_of_a_retired_name_does_not_make_it_triaged_twice() -> None:
    """beta-guard's body mentions `retired-one`; only the RESOLVED table decides triage."""
    assert sorted(list_proposals(FIXTURE, "triaged")) == sorted(EXPECTED_TRIAGED)


def test_count_matches_the_hand_authored_fixture_split() -> None:
    """The oracle is the fixture constant, never the parser's own second output (A.5 r1)."""
    assert count_proposals(FIXTURE, "open") == len(EXPECTED_OPEN)
    assert count_proposals(FIXTURE, "triaged") == len(EXPECTED_TRIAGED)


def test_missing_file_returns_empty_sets_not_an_exception(tmp_path: Path) -> None:
    """Absent-case: a project with no backlog yet is not an error (CLAUDE.md count:8)."""
    assert list_proposals(tmp_path / "nope.md", "open") == []
    assert count_proposals(tmp_path / "nope.md", "open") == 0


# --------------------------------------------------------------------------------------
# AC-002 (property) — `--open` and `--triaged` partition the backlog exactly
# --------------------------------------------------------------------------------------

_HEADING_KIND = st.sampled_from(
    [
        "## Proposal: {name} (2026-01-0{n})",
        "## RESOLVED 2026-01-0{n} — shipped\n\n| Retired proposal(s) | Shipped as |\n|---|---|\n| `{name}` | `tests/t.py` |",
        "## Backlog note (2026-01-0{n}) — count >= 3",
        "## Some other heading {name}",
    ]
)


@st.composite
def _backlog(draw: st.DrawFn) -> tuple[str, set[str], set[str]]:
    """Build a backlog plus the independently-tracked expected sets."""
    blocks = draw(st.lists(_HEADING_KIND, min_size=0, max_size=8))
    text, expected_open, expected_triaged = ["# Backlog"], set(), set()
    for i, tpl in enumerate(blocks):
        name = f"name-{i}"
        text.append(tpl.format(name=name, n=i % 10))
        text.append(f"\nbody for block {i}\n")
        if tpl.startswith("## Proposal:"):
            expected_open.add(name)
        elif tpl.startswith("## RESOLVED"):
            expected_triaged.add(name)
    return "\n".join(text), expected_open, expected_triaged


@settings(max_examples=100)
@given(_backlog())
def test_proposals_open_triaged_partition(case: tuple[str, set[str], set[str]]) -> None:
    """AC-002: the two sets are disjoint, and together they are exactly the proposals.

    Holds for any correct implementation and is violated by one that, say, drops a
    malformed heading from both buckets or counts a `## Backlog note` as open.
    """
    text, expected_open, expected_triaged = case
    sets = parse_proposals(text)
    assert set(sets.open) & set(sets.triaged) == set()
    assert set(sets.open) == expected_open
    assert set(sets.triaged) == expected_triaged


# --------------------------------------------------------------------------------------
# Shipped-surface driver (`tests/structural/test_cli_surfaces_are_driven.py` floor)
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize("status_flag", ["--open", "--triaged"])
def test_hm_proposals_list_runs_in_its_shipped_spelling(status_flag: str) -> None:
    """`hm proposals list` must work as invoked, not merely import."""
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "harness_maker.proposals",
            "list",
            status_flag,
            "--file",
            str(FIXTURE),
        ],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    names = {line.strip() for line in result.stdout.splitlines() if line.strip()}
    assert names == (EXPECTED_OPEN if status_flag == "--open" else EXPECTED_TRIAGED)


def test_hm_proposals_count_prints_a_bare_integer() -> None:
    """The wrapup template consumes this value; anything but a bare int breaks it."""
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "harness_maker.proposals",
            "count",
            "--open",
            "--file",
            str(FIXTURE),
        ],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == str(len(EXPECTED_OPEN))


# --------------------------------------------------------------------------------------
# AC-012 — `summary` reports the oldest open proposal's date (ADR-007, open-only)
# --------------------------------------------------------------------------------------

_MACHINE_SPEC = REPO_ROOT / "specs" / "SPEC-observed-harness-gaps-salvage.machine.yaml"
_AC_012_ROWS = load_golden_table(_MACHINE_SPEC, "AC-012")


def _backlog_from_row(row_input: dict[str, object]) -> str:
    """Build a backlog in the file's REAL shape from a golden row — the row is the oracle."""
    parts: list[str] = []
    open_rows = row_input["open"]
    assert isinstance(open_rows, list)
    for name, date in open_rows:
        suffix = f" ({date})" if date else ""
        parts.append(f"## Proposal: {name}{suffix}\n\n**Proposed mechanism:** x\n")
    resolved = row_input["resolved"]
    assert isinstance(resolved, list)
    if resolved:
        # A resolved batch carries an OLDER date in its heading on purpose: the oldest-open rule
        # must never read a RESOLVED heading's date.
        rows = "".join(f"| `{n}` | `tests/x.py` |\n" for n in resolved)
        parts.append(
            "## RESOLVED 2026-01-03 — shipped as mechanical guards\n\n"
            f"| Retired | Shipped as |\n|---|---|\n{rows}"
        )
    return "\n".join(parts)


@pytest.mark.parametrize(
    "row", _AC_012_ROWS, ids=[r.note or str(i) for i, r in enumerate(_AC_012_ROWS)]
)
def test_ac_012_oldest_open_date(tmp_path: Path, row: GoldenRow) -> None:
    row_input = row.input
    expected = row.expected
    assert isinstance(expected, dict)
    path = tmp_path / "pending-proposals.md"
    if not row_input["absent"]:
        path.write_text(_backlog_from_row(row_input), encoding="utf-8")
    summary = summarize_open(path)
    assert summary == {"open": expected["open"], "oldest": expected["oldest"]}


def _summary_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "harness_maker.proposals", "summary", *args],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


def test_hm_proposals_summary_prints_one_json_object() -> None:
    """ADR-007: one JSON line — the wrapup main loop parses exactly this shape."""
    result = _summary_cli("--file", str(FIXTURE))
    assert result.returncode == 0, result.stderr
    lines = [ln for ln in result.stdout.splitlines() if ln.strip()]
    assert len(lines) == 1, result.stdout
    payload = json.loads(lines[0])
    assert set(payload) == {"open", "oldest"}
    assert payload["open"] == len(EXPECTED_OPEN)
    assert payload["open"] == count_proposals(FIXTURE, "open")
    # Hand-read from the fixture: alpha-guard (2026-01-03) is the oldest OPEN heading. The
    # RESOLVED batch (2026-01-02) and the Backlog note are older/other and must not count.
    assert payload["oldest"] == "2026-01-03"


@pytest.mark.parametrize("flag", ["--open", "--triaged"])
def test_summary_takes_no_status_flag(flag: str) -> None:
    """ADR-007: `summary` is open-only — a `--triaged` count under key `open` is the bug."""
    result = _summary_cli(flag, "--file", str(FIXTURE))
    assert result.returncode != 0
