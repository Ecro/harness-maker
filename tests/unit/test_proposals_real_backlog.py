"""Phase 1 exit criterion — the parser is checked against the REAL backlog, not only a fixture.

PLAN S1: comparing a parser's output to a count the same parser derived is tautological.
The expected list below was derived independently, by `grep '^## Proposal:'` piped through
`sed`, and is asserted by **containment** (`expected ⊆ actual`) rather than equality —
Phase 5 appends the R7 follow-up to this same file, and an equality assertion would make
Phase 5 unable to satisfy its own full-suite exit criterion.

Re-deriving this list by hand is a Manual item in the PLAN's Testing Strategy, not a phase
exit criterion: it is the one step no autonomous run can discharge honestly.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from harness_maker.proposals import list_proposals

REPO_ROOT = Path(__file__).resolve().parents[2]
REAL_BACKLOG = REPO_ROOT / ".claude" / "memory" / "pending-proposals.md"

#: Hand-derived 2026-08-14 via `grep '^## Proposal:' | sed 's/^## Proposal: //'`, with the
#: trailing ` (YYYY-MM-DD)` dropped. NOT produced by the parser under test.
EXPECTED_OPEN_SUBSET = {
    "orphan-worktree-prune-on-create",
    "health-check-no-concrete-id-in-agent-frontmatter",
    "wrapup-close-marker-integrity-guard",
    "re-review-the-fix-not-just-the-suite",
    "ruff-format-in-execute-not-just-wrapup",
    "a cache key may not fingerprint its own launcher",
    "a success message must be emitted from the same branch as the effect",
    "a gate may not discover its own population from the string it forbids",
    "count distinct voters per manual-only finding and print it",
    "a fix must be tested in the position where it does not obviously apply",
}

#: Sanity floor so a silently-emptied list cannot make containment vacuous.
_MIN_OPEN = 15


@pytest.mark.skipif(not REAL_BACKLOG.exists(), reason="no backlog in this checkout")
def test_real_backlog_contains_every_expected_open_proposal() -> None:
    actual = set(list_proposals(REAL_BACKLOG, "open"))
    missing = EXPECTED_OPEN_SUBSET - actual
    assert not missing, (
        f"{len(missing)} expected open proposal(s) not found: {sorted(missing)}. "
        "Either the parser regressed or a proposal was retired — re-derive the list by hand."
    )
    assert len(actual) >= _MIN_OPEN, (
        f"only {len(actual)} open proposals parsed; expected >= {_MIN_OPEN}"
    )


@pytest.mark.skipif(not REAL_BACKLOG.exists(), reason="no backlog in this checkout")
def test_real_backlog_open_and_triaged_stay_disjoint() -> None:
    """The partition invariant must hold on the real file, not only on generated cases."""
    open_set = set(list_proposals(REAL_BACKLOG, "open"))
    triaged = set(list_proposals(REAL_BACKLOG, "triaged"))
    assert open_set & triaged == set()


@pytest.mark.skipif(not REAL_BACKLOG.exists(), reason="no backlog in this checkout")
def test_real_backlog_triaged_is_non_empty() -> None:
    """One RESOLVED batch exists; an empty result would mean the table parse silently failed."""
    assert list_proposals(REAL_BACKLOG, "triaged")
