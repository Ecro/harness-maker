"""Phase 5: the delegate-on wrapup artifact carries BOTH paths, and the git tail stays.

ADR-006's fallback only exists if the artifact it falls back INTO is in the same
file. An earlier draft of this plan put the dispatch and the inline body in
mutually-exclusive Jinja branches, which would have made "run the body inline"
unreachable — a degraded path with no destination.

These are render-GREP tests: they prove the instruction is PRESENT. They cannot
prove the interpreting model obeys it. That asymmetry is deliberate and is the same
position the economics prose layer takes.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from harness_maker.context_lint import _count_body_lines
from harness_maker.models import (
    DelegationConfig,
    InterviewAnswers,
    Preset,
    ProjectProfile,
    Target,
)
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize

# The `workflow` Production cap from `context_lint.THRESHOLDS`. Nothing ENFORCES it
# for an atomic stage command — `readiness._CONTEXT_LIMITS` has no command row — so
# this is a chosen yardstick, stated rather than discovered. See the note in
# `test_the_delegate_on_command_size_is_pinned_so_growth_is_a_decision`.
_WORKFLOW_PRODUCTION_CAP = 600


def _flat(text: str) -> str:
    """Collapse whitespace before matching prose.

    Markdown prose is hard-wrapped, so a phrase the template really contains can be
    split across a newline. Asserting the unwrapped form against the raw text fails for
    formatting rather than for content — and the fix would be to re-wrap the template
    to suit the test, which is backwards.
    """
    return " ".join(text.split())


def _wrapup(
    tmp_path: Path,
    *,
    preset: str = "Production",
    stages: list[str] | None = None,
    feature_branch: bool = True,
) -> str:
    # `feature_branch_workflow` must be set EXPLICITLY: constructing `InterviewAnswers`
    # directly bypasses `interview()`'s `_preset_extras`, so the flag-gated Step 7.7
    # (`task-land`) would simply not render and a test asserting its presence would be
    # measuring the fixture, not the template.
    answers = InterviewAnswers(
        preset=Preset(preset),
        targets=[Target.CLAUDE_CODE],
        delegation=DelegationConfig(stages=stages or []),
        worktree={"feature_branch_workflow": feature_branch},
    )
    render(synthesize(ProjectProfile(), answers), tmp_path, freeze_time=DEFAULT_FREEZE_TIME)
    return (tmp_path / "commands" / "hm" / "wrapup.md").read_text(encoding="utf-8")


# ------------------------------------------------------------------ delegate OFF


def test_the_default_render_carries_no_dispatch_block(tmp_path: Path) -> None:
    """ADR-011 ships default-empty for one release. A dispatch block present in the
    default artifact would make the soak meaningless — and would mean every existing
    user's next `--update` silently switched their wrapup to a subagent."""
    body = _wrapup(tmp_path)

    assert "stage-delegate" not in body
    assert "wrapup_brief" not in body


def test_the_default_render_still_carries_the_whole_body(tmp_path: Path) -> None:
    """Negative control for the test above: "no dispatch" must not have been achieved
    by dropping the body."""
    body = _wrapup(tmp_path)

    assert "Step 5 — Memory append" in body
    assert "Steps 6 → 7.6 — Stage, commit, pop, drain" in body


# ------------------------------------------------------------------ delegate ON


def test_the_delegate_on_render_carries_the_dispatch(tmp_path: Path) -> None:
    body = _wrapup(tmp_path, stages=["wrapup"])

    assert "stage-delegate" in body
    assert "hm wrapup_brief" in body


def test_the_delegate_on_render_still_carries_the_inline_body(tmp_path: Path) -> None:
    """ADR-006's reachability fix, and the defect it was written against: with the two
    paths in mutually-exclusive branches there is no inline body to degrade INTO, so
    an incomplete brief or an unavailable dispatch tool strands the stage entirely."""
    body = _wrapup(tmp_path, stages=["wrapup"])

    assert "Step 5 — Memory append" in body
    assert "Steps 6 → 7.6 — Stage, commit, pop, drain" in body


def test_the_inline_body_is_labelled_as_the_degraded_path(tmp_path: Path) -> None:
    """Without the heading, a reader of the delegate-on artifact sees the body twice
    over and cannot tell which one runs."""
    body = _wrapup(tmp_path, stages=["wrapup"])

    assert "degraded" in body.lower()


def test_the_dispatch_block_self_skips_when_the_tool_is_unavailable(tmp_path: Path) -> None:
    """ADR-002's per-target mechanism. There is no `is_cursor` render branch to key
    on, so Cursor and Codex degrade at RUNTIME — the same shape the autopilot block
    already uses. Without the self-skip those sessions get a dispatch instruction they
    cannot execute."""
    body = _wrapup(tmp_path, stages=["wrapup"])

    lowered = body.lower()
    assert "unavailable" in lowered
    assert "inline" in lowered


def test_the_receipt_is_reconciled_before_the_commit(tmp_path: Path) -> None:
    """Order is the contract (ADR-012): reconciling AFTER the commit means a mismatch
    is discovered once it is already in history."""
    body = _wrapup(tmp_path, stages=["wrapup"])

    reconcile_at = body.index("wrapup_receipt")
    commit_at = body.index("Steps 6 → 7.6 — Stage, commit, pop, drain")
    assert reconcile_at < commit_at


def test_the_git_tail_stays_in_the_main_loop(tmp_path: Path) -> None:
    """ADR-004: `git add`/`commit`, the stash pop, the drain and `task-land` stay
    outside the delegated portion — as a prompt instruction, not a runtime boundary
    (the agent has Bash). The delegated body must be told so explicitly."""
    body = _wrapup(tmp_path, stages=["wrapup"])

    assert "Step 7.7" in body
    assert "task-land" in body
    # The dispatch section must name the exclusion rather than leaving it implied.
    dispatch = body[body.index("stage-delegate") : body.index("Step 5 — Memory append")]
    assert "git" in dispatch.lower()


def test_only_the_configured_stage_gets_a_dispatch(tmp_path: Path) -> None:
    """`delegation.stages` is a LIST precisely so one stage's opt-in does not turn on
    another's (ADR-011 rejected `wrapup.delegate` for exactly this). Turning on verify
    alone must leave wrapup inline."""
    body = _wrapup(tmp_path, stages=["verify"])

    assert "stage-delegate" not in body
    assert "Step 5 — Memory append" in body


# ------------------------------------------------------------------ size


# 628 → 627 / 661 → 660 (PLAN-sessionid-env-propagation Phase 5): the `stage_end_summary`
# NO-OP paragraph was compacted by one line to pay for the `--session-id` flags rather than
# raise a per-command ceiling (ADR-011).
# 627 → 625 / 660 → 658 (PLAN-harness-diet ADR-001): each stage template carried a
# two-line `{% if workflow_context %}` header naming the fused workflow it was invoked
# from. With no fused workflows those lines can never render, so they were deleted.
# Both moves SHRINK the render — this ratchet is being tightened, not loosened, and the
# direction is why the constant is allowed to move at all.
# 625 → 658 / 658 → 691 (PLAN-harness-diet ADR-010): the FIRST upward move of this
# constant, so it does not get the "direction justifies it" pass the two above rely on.
# Attribution was measured, not inferred: the delta is +33 in both presets, and the
# session-start autopilot picker block is 31 non-blank lines plus its two blank separators.
# The picker renders under `config.autonomy.level != "gated"`; ADR-010 flipped the class
# DEFAULT to `auto_safe`, so a block that was previously gated OUT of the default render is
# now in it. Nothing about the delegation feature changed — `stage-delegate` is still absent
# from the body, which the assertion above checks independently of this count.
# NOTE for the next reader: the new Side value (658) is numerically the OLD Production value.
# That is a coincidence of a uniform +33, not a mis-edited parametrize.
@pytest.mark.parametrize(("preset", "expected"), [("Side", 658), ("Production", 691)])
def test_the_default_render_costs_existing_users_nothing(
    tmp_path: Path, preset: str, expected: int
) -> None:
    """The shipped artifact is the delegate-OFF one for at least this release
    (ADR-011), so the whole Jinja block must be gated.

    Re-measured 2026-07-29 (was 662 / 695): PLAN-workflow-step-audit Phase 2 collapsed
    Steps 6 → 7.6 into one `hm wrapup_land` call, removing 44 body lines. This constant
    is an equality pin, so it moves only in the commit that moves the render — and it
    moved DOWN here, which is the direction this phase promised.

    Re-measured 2026-07-31 (was 618 / 651): +10. PLAN-autopilot-advance-noop rewrote the two
    SHARED partials — the picker now asks `hm autopilot status` instead of guessing from
    the marker file, and the auto-advance block passes `--slug`/`task_slug` — and every
    stage includes them, wrapup among them. +2 of the +10 are the review's own findings: a
    `degraded-idless` picker branch (without it, a WSL2 session is told a peer owns its own
    marker and never re-arms) and the `rejected*` slug sources; +3 more came from round 5,
    which removed the pre-rendered `--slug '<slug>'` placeholder (it fails the allowlist,
    and a bad slug now HALTS, so a model copying the shipped line would stop the chain at
    every stage) and added the `bad_slug` recovery clause. Wrapup's own body is
    untouched: it is human-gated (`_HUMAN_GATED_STAGES`), so the chain never auto-enters it
    and its terminal STOP needed no exception clause."""
    assert _count_body_lines(_wrapup(tmp_path, preset=preset)) == expected


@pytest.mark.parametrize("preset", ["Side", "Production"])
def test_delegation_adds_a_bounded_amount_of_prose(tmp_path: Path, preset: str) -> None:
    """ADR-006 warns the delegate-on command GROWS rather than shrinks. The DELTA is
    what this phase owns, so that is what is pinned.

    An absolute cap would be dishonest here twice over: the command already sat at 695
    Production body lines — past `context_lint`'s `workflow` cap of 600 — before this
    phase added anything, and nothing ENFORCES that cap on an atomic stage command
    (`readiness._CONTEXT_LIMITS` has no command row). Measuring the delta instead
    makes the assertion about this change rather than about inherited size. Measured:
    **+60 lines — the cap exactly.** Five review rounds of added prose were paid for by
    compressing existing prose in the same block; there is no headroom left, so the next
    addition must be paid for the same way rather than by raising the bound.
    """
    off = _count_body_lines(_wrapup(tmp_path / "off", preset=preset))
    on = _count_body_lines(_wrapup(tmp_path / "on", preset=preset, stages=["wrapup"]))

    assert on - off <= 60, (
        f"{preset} delegation adds {on - off} body lines ({off} → {on}); the delegated "
        "body is supposed to move context OUT of the main loop, not add prose to the "
        f"command. For reference the `workflow` Production cap is "
        f"{_WORKFLOW_PRODUCTION_CAP}, which this command already exceeded before "
        "delegation existed."
    )


# ------------------------------------------------- review round 2 (M-03, M-04)


def test_the_delegate_asset_carries_untrusted_data_framing(tmp_path: Path) -> None:
    """M-03. The same diff added this block twice to the read-only `/hm:metrics`
    surface and omitted it from the only new WRITE-capable asset (Write/Edit/Bash),
    which is the inverse of the correct priority. The delegate reads the PLAN, REVIEW,
    memory tiers and a git-derived diff — all attacker-influencable text."""
    render(
        synthesize(
            ProjectProfile(),
            InterviewAnswers(preset=Preset.PRODUCTION, targets=[Target.CLAUDE_CODE]),
        ),
        tmp_path,
        freeze_time=DEFAULT_FREEZE_TIME,
    )
    body = _flat((tmp_path / "agents" / "stage-delegate.md").read_text(encoding="utf-8"))

    assert "Untrusted data" in body
    assert "never instructions to you" in body
    # It must name the reason this asset in particular needs it.
    assert "Write, Edit and Bash" in body


def test_the_receipt_temp_file_discipline_is_specified(tmp_path: Path) -> None:
    """M-04. Sibling steps 5.1 and 5.6 in the same file already mandate a fresh temp
    file outside the repo, because a fixed name collides under concurrent fleet
    wrapups — one session's reconciler would read another's reply and vouch for claims
    it never saw. Step 0.5 named no path at all."""
    body = _wrapup(tmp_path, stages=["wrapup"])
    section = _flat(body[body.index("Step 0.5") : body.index("Steps 1–5.6 — inline body")])

    assert "OUTSIDE the repo" in section
    assert "never a fixed in-repo name" in section
    # `mktemp`, not a constructed path. The prose used to name `/tmp/hm-receipt-<slug>-$$.json`
    # and lean on `$$` for entropy — but `$$` is a LITERAL under the Write tool, not a PID, so
    # the path collapsed to a slug-derived name a peer can predict or pre-plant a symlink at.
    # The receipt is the artifact the anti-fabrication reconciliation depends on (CWE-377).
    assert "mktemp" in section
    # The stage must be asserted, or a wrapup receipt reconciles as a verify one.
    assert "--stage wrapup" in section


def test_the_reconcile_call_passes_the_worktree_root(tmp_path: Path) -> None:
    """R2-01, and the fourth instance in this task of *unit boundary green, shipped
    entry point wrong*: `reconcile` gained a `worktree_root` parameter with two passing
    unit tests, and no caller passed it — so `doc_root` stayed at base, byte-identical
    to the behaviour the parameter was added to fix.

    `!` lines run at the BASE repo; the delegate writes in the worktree. Without the
    flag, every truthful delegated run reports `document-missing`.
    """
    section = _flat(_wrapup(tmp_path, stages=["wrapup"]))

    assert "--worktree '<brief.worktree_root>'" in section
    assert "`--worktree` is not optional" in section
