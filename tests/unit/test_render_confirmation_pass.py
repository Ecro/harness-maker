"""Phase 5 — the confirmation pass runs over a frozen artifact, once, and can only approve clean.

Criterion ⑤ of the research: N consecutive clean passes on a **frozen diff**. The stage's
existing exit is *issue exhaustion* over a moving target — the auto-fix loop re-reviews only
touched scopes, so the last round's fixes always leave unreviewed, and those fixes introduce
defects at a measured ~1:1.

Anchors follow the same rules this task's Phase 4 file arrived at over five A.5 rounds, and the
reasoning lives there (`tests/unit/test_render_lens_dispatch.py`). In short: slice to a bounded
block with an explicit stop, read decisions out of the gate's pseudocode rather than out of
prose, and pair any ordinary-English token with an unforgeable one.

The branch matrix is the point. S4/S4a/S5/S5a/S6/S9 are six outcomes over three inputs (clean vs
dirty, coverage complete vs not, `auto_fix` on vs off), and the defect class this SPEC records is
a state that matches **no** branch — so each is asserted separately rather than through one
"handles the confirmation pass" check.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from harness_maker.conditional_router import MANDATORY_LENSES
from harness_maker.interview import interview
from harness_maker.models import ProjectProfile
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize


def _render(tmp_path: Path, *, auto_fix: bool = True, instrumented: bool = False) -> str:
    p = ProjectProfile(stack=["python"], scale="small", lifecycle="dormant")
    a = interview(p, autoloop_mode=True)
    a.auto_fix = auto_fix
    # The ledger emit is behind the `instrumentation` axis, which defaults OFF for a fresh
    # install — same gating as `execute.md.j2`'s A.5 row. Tests that assert the row must turn
    # the axis on, or they assert the axis rather than the row.
    a.instrumentation.stage_agent_ledger = instrumented
    render(synthesize(p, a), tmp_path, freeze_time=DEFAULT_FREEZE_TIME)
    return (tmp_path / "commands" / "hm" / "review.md").read_text(encoding="utf-8")


def _section(body: str, start: str, *, stop: str) -> str:
    i = body.find(start)
    assert i != -1, f"rendered command has no section starting {start!r}"
    j = body.find(stop, i + len(start))
    return body[i:] if j == -1 else body[i:j]


@pytest.fixture(scope="module")
def review_body(tmp_path_factory: pytest.TempPathFactory) -> str:
    return _render(tmp_path_factory.mktemp("confirm"))


@pytest.fixture(scope="module")
def confirm_block(review_body: str) -> str:
    return _section(review_body, "## Confirmation Pass", stop="\n## ")


# ── AC-004: the artifact is frozen, and diffed from review_base ──────────────


def test_the_pass_reviews_a_freeze_commit_not_the_working_tree(confirm_block: str) -> None:
    """The whole criterion. A pass over a moving tree re-reviews a different object each time.

    The fixes are uncommitted when the gate would approve (wrapup owns commits), so a ref
    naming HEAD would freeze the artifact WITHOUT the content the pass exists to look at —
    which is why `hm freeze` builds a commit from a temporary index rather than using HEAD.
    """
    assert "hm freeze" in confirm_block, "the pass does not build a frozen commit at all"
    assert "refs/hm-freeze/v1/" in confirm_block


def test_the_diff_spans_the_whole_review_not_the_last_repair(confirm_block: str) -> None:
    """`review_base..<freeze>` is the span; `HEAD..` would be the last round's fixes only.

    Diffing from HEAD reinstates the scope-selective re-review the pass replaces — the pass
    would then examine exactly the changes least likely to have been reviewed, and nothing else.
    """
    assert "review_base" in confirm_block
    assert "review_base.." in confirm_block, (
        "the confirmation pass does not diff FROM review_base; a pass that diffs from HEAD "
        "sees only the repair round it just applied"
    )


def test_the_pass_reads_the_stored_base_rather_than_re_resolving_it(confirm_block: str) -> None:
    """AC-004's store clause. Re-resolving drifts as commits land during the review."""
    assert "-base" in confirm_block
    assert "re-resolve" in confirm_block.lower() or "read" in confirm_block.lower()


# ── AC-006 / S5 / S6: bounded at one repair round, two passes ────────────────


def test_the_pass_id_is_confirm_1_then_confirm_2(confirm_block: str) -> None:
    """Pass ids, not round numbers — a pass is not a round.

    Reusing a round number puts the pass's results in that round's directory, where a lens that
    failed during the pass is counted as exercised from the round's stale file.
    """
    assert "confirm-1" in confirm_block
    assert "confirm-2" in confirm_block


def test_no_third_pass_is_reachable(confirm_block: str) -> None:
    assert "no third" in confirm_block.lower()


def test_the_repair_round_does_not_consume_the_review_budget(confirm_block: str) -> None:
    """S5: budgeted separately, and it must not increment `iteration_count`.

    If it did, a dirty pass would silently eat a review round and could trip the
    `max_review_rounds` exit on a review that had not used them.
    """
    assert "iteration_count" in confirm_block


# ── The branch matrix: every input combination reaches a named outcome ───────


@pytest.mark.parametrize(
    "phrase",
    [
        "zero new",  # S4 clean
        "coverage blocker",  # S4a clean-but-incomplete
        "repair round",  # S5 dirty + auto_fix
        "no repair round",  # S5a dirty + auto_fix off
    ],
)
def test_each_input_combination_names_its_outcome(confirm_block: str, phrase: str) -> None:
    """S4a is the reason this is a matrix and not a single check.

    Zero-new-severe-with-incomplete-coverage matched **no** branch in an earlier draft: S4's
    conjunct fails, S5's dirty trigger does not fire, and S9's not-run path does not apply
    because the pass did run. The pass dispatches five lenses and a dispatch failure is
    medium-likelihood, so the state is reachable.
    """
    assert phrase in confirm_block.lower()


def test_a_clean_pass_with_incomplete_coverage_cannot_approve(confirm_block: str) -> None:
    """S4a's Then, as a conjunction rather than as two facts in the same document.

    "All five exercised" must gate APPROVED in the same breath as "zero new severe"; stated
    apart, a template can approve on the finding count alone.
    """
    # The pseudocode arm, not the first mention: the block's prose opens with "Run it only on
    # the APPROVED path", which precedes the decision and satisfies any first-occurrence slice.
    # Same weakness the Phase 4 file hit twice.
    fences = re.findall(r"^```[^\n]*\n(.*?)^```", confirm_block, flags=re.S | re.M)
    pseudo = "\n".join(f for f in fences if "Status = APPROVED" in f)
    assert pseudo, "no pseudocode arm reaches Status = APPROVED"

    lines = pseudo.splitlines()
    idx = next(i for i, line in enumerate(lines) if "Status = APPROVED" in line)
    guard = "\n".join(lines[:idx])
    assert "blocks_approval" in guard, (
        "nothing on the path to APPROVED reads the coverage verdict, so a pass whose lenses "
        "died returns zero findings and approves"
    )
    assert "zero new" in guard, "the APPROVED arm does not test the finding count either"


def test_auto_fix_off_makes_the_pass_read_only(tmp_path_factory: pytest.TempPathFactory) -> None:
    """S5a, order-independently.

    An earlier draft justified this by asserting the gate tests the grade before the
    auto-fix-disabled branch. Phase 4 edits that gate and nothing pinned the ordering, so the
    rule is asserted as a property of the `auto_fix` input instead.
    """
    body = _render(tmp_path_factory.mktemp("nofix"), auto_fix=False)
    block = _section(body, "## Confirmation Pass", stop="\n## ")
    assert "read-only" in block.lower() or "no repair round" in block.lower()


# ── S9: the pass is skipped on a non-approval exit, and recorded as not-run ──


def test_a_non_approval_exit_dispatches_no_pass(confirm_block: str) -> None:
    """Reaching `max_review_rounds` is not a candidate for confirmation — nothing was approved.

    Running it there would spend five dispatches to confirm a review that already failed.
    """
    assert "max_review_rounds" in confirm_block


def test_a_skipped_pass_is_recorded_as_not_run_not_as_clean(confirm_block: str) -> None:
    """The telemetry distinction. `confirm_pass_ran: false` and "ran and found nothing" are
    opposite facts that a single boolean would merge — the validator in `review_telemetry`
    rejects the merged shape, and this is the emitting half."""
    assert "confirm_pass_ran" in confirm_block


# ── S7 / S8: loop mode, and the vote freeze ──────────────────────────────────


def test_a_dirty_second_pass_fails_the_loop_receipt(confirm_block: str) -> None:
    """S7: under `/hm:loop` the driver owns retry, so the stage reports rather than escalates."""
    assert "verdict: fail" in confirm_block


def test_the_pass_re_reads_the_frozen_cross_model_set(confirm_block: str) -> None:
    """S8: the vote freeze. Re-invoking would give the models a second vote on the same review.

    Asserted as the absence of the invoker's own module name inside the block — a symbol fixed
    by the shipped vote-freeze contract long before this change.
    """
    assert "second_opinion_invoke" not in confirm_block, (
        "the confirmation pass re-invokes the cross-model voters, breaking the round-1 freeze"
    )


@pytest.mark.parametrize("lens", MANDATORY_LENSES)
def test_the_pass_dispatches_every_mandatory_lens(confirm_block: str, lens: str) -> None:
    """A confirmation pass over a subset would confirm a subset."""
    assert f"{lens}.json" in confirm_block


@pytest.fixture(scope="module")
def instrumented_confirm_block(tmp_path_factory: pytest.TempPathFactory) -> str:
    body = _render(tmp_path_factory.mktemp("instrumented"), instrumented=True)
    return _section(body, "## Confirmation Pass", stop="\n## ")


def test_each_pass_is_recorded_as_a_ledger_episode(instrumented_confirm_block: str) -> None:
    """F4 identified this as the one cap in the harness with NO recorded episodes.

    The reviewer and validator caps both have rows, and reading them settled questions no
    argument could — 5-of-9 release for the reviewer gate, 0-of-12 for the validator, calling
    for opposite responses. Without rows, the two-pass bound here can only be defended by
    assertion, which is what this whole task exists to stop.
    """
    assert "stage_agent_ledger emit" in instrumented_confirm_block, (
        "the confirmation pass records no episode, so its two-pass cap stays unmeasurable"
    )
    assert "--agent confirmation-pass" in instrumented_confirm_block, (
        "the row is not attributed to this gate; merged with another agent's rows it cannot "
        "be read as its own release rate"
    )
    assert "--pass" in instrumented_confirm_block


def test_the_ledger_row_uses_the_existing_verdict_vocabulary(
    instrumented_confirm_block: str,
) -> None:
    """No schema change: `PASS`/`FAIL` are what `stage_agent_ledger` already carries.

    A new enum value would need every reader updated, and the missed one is the failure mode
    (`[fail:design] new-marker-content-field-must-update-every-reader`, count:3).
    """
    emit = _section(instrumented_confirm_block, "stage_agent_ledger emit", stop="\n")
    assert "PASS|FAIL" in emit or "<PASS|FAIL>" in emit


def test_the_ledger_row_is_absent_when_instrumentation_is_off(confirm_block: str) -> None:
    """The axis is opt-in, and a fresh install must not pay for a row it never reads."""
    assert "stage_agent_ledger emit" not in confirm_block
