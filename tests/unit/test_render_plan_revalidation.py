"""Phase 6 (AC-010 / S10) — the last revision is re-validated as a whole, once, terminally.

**Why this is the right place to spend a pass, measured.** `stage-agents.jsonl` holds 12
plan-validator episodes and **not one reached a clean verdict**. Reading their recorded critiques
settled why: the blocking findings were verified against source and held, and `opus5` states
outright that pass 2's three criticals were *created by the pass-1 fixes*. So the revisions are
where the new criticals come from, and the revision written last is the one nothing looks at —
the planning-side twin of `[fail:test] fix-introduced-defect-passes-all-gates` (count:7).

That measurement also bounds what this phase may do. The loop does not converge, so a
re-validation cannot be a gate that waits for clean — it would never release. It is terminal by
construction: findings are recorded, named, handed to two readers, and the stage moves on.

Anchors follow the rules the Phase 4/5 files arrived at over five A.5 rounds: bounded slices,
decisions read from pseudocode rather than prose, ordinary-English tokens paired with unforgeable
ones. `MAJOR_REVISION_TERMINAL` is unforgeable — it exists nowhere else in the surface.
"""

from __future__ import annotations

import pytest

from harness_maker.interview import interview
from harness_maker.models import ProjectProfile
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize


def _section(body: str, start: str, *, stop: str) -> str:
    i = body.find(start)
    assert i != -1, f"rendered command has no section starting {start!r}"
    j = body.find(stop, i + len(start))
    return body[i:] if j == -1 else body[i:j]


@pytest.fixture(scope="module")
def plan_body(tmp_path_factory: pytest.TempPathFactory) -> str:
    out = tmp_path_factory.mktemp("plan")
    p = ProjectProfile(stack=["python"], scale="small", lifecycle="dormant")
    render(synthesize(p, interview(p, autoloop_mode=True)), out, freeze_time=DEFAULT_FREEZE_TIME)
    f = out / "commands" / "hm" / "plan.md"
    assert f.is_file(), f"missing rendered command file: {f}"
    return f.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def revalidation_block(plan_body: str) -> str:
    return _section(plan_body, "### Step 4.5 — Terminal re-validation", stop="\n### ")


# ── The outcome name, and the fact that it is terminal ───────────────────────


def test_the_terminal_outcome_has_its_own_name(plan_body: str) -> None:
    """`MAJOR_REVISION_TERMINAL` is distinct from `MAJOR_REVISION` on purpose.

    They mean opposite things to a reader: the first says "a second pass ran and these findings
    survived it, proceed with them as known risks"; the second says "revise". Collapsing them
    would make an unrevised PLAN and a twice-validated one indistinguishable in frontmatter.
    """
    assert "MAJOR_REVISION_TERMINAL" in plan_body


def test_pass_two_is_stated_as_terminal_not_as_another_round(revalidation_block: str) -> None:
    """Measured constraint: 12 of 12 episodes never reached clean, and pass 2's criticals were
    created by pass 1's fixes. A re-validation that waits for clean never releases."""
    assert "terminal" in revalidation_block.lower()
    assert (
        "never revised" in revalidation_block.lower() or "not revised" in revalidation_block.lower()
    )


def test_the_existing_two_pass_cap_is_not_raised(revalidation_block: str) -> None:
    """S10: "the existing two-pass cap ... otherwise unchanged".

    Raising it is the response the measurement rules out — three-pass episodes ended
    `MAJOR_REVISION` too, so a third pass buys findings, not release.
    """
    assert "two-pass" in revalidation_block.lower() or "cap" in revalidation_block.lower()


# ── The scope: the WHOLE document, on BOTH revision paths ────────────────────


def test_the_whole_document_is_re_validated_not_the_revised_sections(plan_body: str) -> None:
    """The defect this closes. Re-reading only what changed is the planning-side twin of the
    review loop's scope-selective re-review, and it misses exactly the cross-section
    contradictions a revision introduces."""
    assert plan_body.count("whole PLAN") >= 2, (
        "the whole-document scope is stated fewer than twice; AC-010 requires it on both the "
        "NEEDS_REVISION and MAJOR_REVISION paths, and one mention cannot cover both"
    )


@pytest.mark.parametrize("path", ["NEEDS_REVISION", "MAJOR_REVISION"])
def test_both_revision_paths_reach_the_re_validation(revalidation_block: str, path: str) -> None:
    """`NEEDS_REVISION` is the easy one to forget — it is the "warnings only" path, so it feels
    minor. But a warning-driven revision edits the document just as much, and the measured
    defect is that revisions introduce criticals regardless of what prompted them."""
    assert path in revalidation_block


# ── Its two readers ──────────────────────────────────────────────────────────


def test_execute_is_named_as_a_reader_that_proceeds(revalidation_block: str) -> None:
    """A terminal outcome with no reader is a field nothing consumes.

    `/hm:execute` must proceed — treating the surviving findings as recorded known risks — or
    the terminal state becomes an unblockable halt on a loop that never converges.
    """
    assert "execute" in revalidation_block.lower()
    assert "known risk" in revalidation_block.lower()


def test_loop_mode_gate0_is_named_as_the_other_reader(revalidation_block: str) -> None:
    """Under `/hm:loop` there is no human to hand the risks to, so the driver is told instead."""
    assert "verdict: fail" in revalidation_block


def test_the_two_readers_are_distinguished_not_merged(revalidation_block: str) -> None:
    """They do opposite things — one proceeds, one fails the receipt.

    A block that names both without separating them reads as a contradiction, and the executing
    model resolves contradictions by picking one.
    """
    assert "loop" in revalidation_block.lower()
    execute_at = revalidation_block.lower().find("known risk")
    loop_at = revalidation_block.find("verdict: fail")
    assert execute_at != -1, "the execute reader's instruction is missing"
    assert loop_at != -1, "the loop reader's instruction is missing"
    assert abs(execute_at - loop_at) > 40, (
        "the two readers' instructions are on top of each other; they must be separate branches"
    )


# ── The frontmatter contract ─────────────────────────────────────────────────


def test_the_frontmatter_field_records_the_terminal_outcome(plan_body: str) -> None:
    """`validator_outcome` is the durable carrier — the ledger row records a verdict per pass,
    but only the PLAN says which outcome the document was written under."""
    frontmatter = _section(plan_body, "validator_outcome:", stop="\n\n")
    assert "MAJOR_REVISION_TERMINAL" in frontmatter


def test_no_ledger_schema_change_is_requested(revalidation_block: str) -> None:
    """AC-010: "No `stage_agent_ledger` schema change."

    The existing rows already carry pass number and verdict; a new field would need every
    reader updated, and `[fail:design] new-marker-content-field-must-update-every-reader`
    (count:3) is what happens when one is missed.
    """
    assert "--verdict" not in revalidation_block or "MAJOR_REVISION_TERMINAL" not in _section(
        revalidation_block, "--verdict", stop="\n"
    ), (
        "the terminal outcome is being pushed into the ledger's verdict enum; it belongs in "
        "the PLAN frontmatter, and the ledger keeps its existing three values"
    )
