"""PLAN-bench-study-adoption ADR-006 — the disposition vocabulary stays a single object.

`review_consensus.DISPOSITIONS` is `codex_ledger.DISPOSITION_VALUES` by **identity**, not by
coincidence: `review_consensus.py:26,40` imports and assigns it, and the comment at that line
records that the prior state — three independent literals behind a comment claiming a single
source of truth — was the defect the consolidation fixed. `review_telemetry.py:159` validates
`disposition_counts` keys against the same frozenset.

This pin exists because a planning round for this very task proposed un-aliasing them, on the
false premise that they were independently declared. That premise was refuted by reading the
source, and the decision reversed — but the reversal lives in an ADR, and an ADR does not stop
the next reader reaching for the same edit. This does.

**Why it is a pinning test rather than a false RED** (Phase A.4 case 2): it is a negative
invariant, vacuously true while nobody splits the vocabulary. Its RED positive sibling is
`test_oracle_blocked_pairs_only_with_unresolved` in `tests/unit/test_review_consensus.py` —
that test is the pressure. It forces a new recorded reason into existence, and the wrong way
to satisfy it is to add a disposition member, which lands in `DISPOSITION_VALUES` through the
alias and puts a permanently-zero key in `review_telemetry.disposition_counts`. This test is
what makes that wrong fix fail loudly instead of shipping.
"""

from __future__ import annotations

from harness_maker import codex_ledger, review_consensus, review_telemetry


def test_review_consensus_dispositions_is_the_ledger_vocabulary_object() -> None:
    """Identity, not equality — equality would pass a copy that then drifts."""
    assert review_consensus.DISPOSITIONS is codex_ledger.DISPOSITION_VALUES


def test_the_shared_vocabulary_has_exactly_the_four_pida_values() -> None:
    """The task that pinned this adds a recorded reason on the AUTHORITY axis instead.

    Naming the four here rather than only pinning identity: identity alone would still be
    satisfied by adding a fifth member to the one shared object, which is the other half of
    the rejected alternative.
    """
    assert set(codex_ledger.DISPOSITION_VALUES) == {
        "accepted",
        "rejected",
        "duplicate",
        "unresolved",
    }


def test_review_telemetry_validates_against_that_same_object() -> None:
    """The third consumer, and the one a hand-maintained reader list would miss.

    `review_telemetry` imports the frozenset rather than restating it; this asserts the import
    is still the live path, so a future refactor that gives telemetry its own copy fails here
    rather than in a disposition-counts mismatch nobody traces back.

    Read through `vars()` rather than imported directly: `review_telemetry` does not re-export
    the name, so `from … import DISPOSITION_VALUES` fails `mypy --strict`'s implicit-reexport
    check. Inspecting the module namespace is also the more faithful assertion — the property
    under test is what that module's global actually points at, not what a re-export promises.
    """
    assert vars(review_telemetry)["DISPOSITION_VALUES"] is codex_ledger.DISPOSITION_VALUES
