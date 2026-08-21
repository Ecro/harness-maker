"""PLAN-bench-study-adoption Phase 2 — the auto-fixer reads the covering test, then refuses.

Render-greps, and honest about it (CLAUDE.md checkpoint 2): they prove the instruction is
PRESENT, never that a fixer obeys it. What keeps them from being decorative is
`test_the_predicates_discriminate`, which asserts the same predicates are FALSE against a
sibling stage render — without it, a predicate true of every document would pass.

Two structural facts drive what is asserted where:

* **The rule body lives in the skill, the pointer in the stage.** Neither ratchet measures a
  skill (`_ATOMIC_RATCHET` is per rendered command; the codex arm globs `hm-*/SKILL.md`, which
  `targeted-test-selection` does not match), so the reasoning can be explicit there while the
  stage carries a reference. That split is asserted, not assumed: a body that migrated into
  `review.md.j2` would pass a naive "the words are somewhere" check while spending budget the
  allowance funds for phases 3 and 4.

* **The refusal retags `manual-only`.** That is the whole mechanism — Step 3's fixable-finding
  filter already requires `Tag = consensus-passed`, so the retag both excludes the finding from
  re-selection and keeps it out of the grade, with no new filter and no new field to preserve
  across the round merge. A render that records the authority but omits the retag ships a
  finding the fixer re-selects every round; that is the assertion below with the sharpest teeth.

**Phase A.4 — three of these nine pass before the implementation, on purpose.** Each is a
negative invariant, vacuously true while the construct it forbids does not exist, and each has a
RED positive sibling in this module that forces that construct into existence:

* `test_the_skill_does_not_restate_section_4_5` — nothing has been added to the skill yet.
  Sibling: `test_the_new_section_does_not_collide_with_the_existing_section_5`, which adds §6.
  The wrong way to write §6 is to paste §4.5's classification into it; this is what catches that.
* `test_the_rendered_skill_is_within_the_context_lint_cap` — the same §6 addition is the pressure.
  A hardcoded cap in this exact assertion drifted for three minor versions, so it reads
  `THRESHOLDS`, never a literal.
* `test_the_predicates_discriminate` — the standing guard. It is *supposed* to pass now and
  after; what it rejects is a predicate true of every rendered document.
* `test_step_3_still_filters_on_the_tag_the_refusal_sets` and
  `test_the_exclusion_is_the_retag_and_not_a_second_authority_filter` — added in round 2 for the
  missing S8. Step 3 already filters on `consensus-passed` and does not yet mention the
  authority, so both are true today; that is the point. They pin the mechanism ADR-004's
  amendment chose over the one it rejected, and the pressure that could break either is the
  refusal block the RED tests above force into existence.

**Round 2 rewrote two assertions that no correct implementation could satisfy.** Both scoped
their terms to the whole rendered command, where `manual-only` already occurs 18 times,
`targeted-test-selection` twice, and `own target` once — the last inside the pre-existing
tests-lens carve-out at `review.md.j2:815` that ADR-004's amendment requires be kept verbatim.
The negative half was therefore satisfiable only by deleting that carve-out, which reintroduces
the pass-1 critical it exists to prevent. Every assertion about the new instruction is now
scoped by the `@hm:oracle-blocked` anchor, and `_refusal_block` fails loudly if the anchor is
absent rather than silently widening back to the whole document.
"""

from __future__ import annotations

from functools import cache
from pathlib import Path
from tempfile import mkdtemp

from harness_maker.context_lint import THRESHOLDS
from harness_maker.interview import interview
from harness_maker.models import Preset, ProjectProfile
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize

_SKILL = "targeted-test-selection"


def _profile(preset: Preset) -> ProjectProfile:
    return (
        ProjectProfile(stack=["python"], scale="small", lifecycle="dormant")
        if preset == Preset.SIDE
        else ProjectProfile(stack=["python"], scale="medium", lifecycle="active")
    )


@cache
def _render_root(preset: Preset) -> Path:
    profile = _profile(preset)
    answers = interview(profile, autoloop_mode=True)
    bp = synthesize(profile, answers, preset=preset)
    out = Path(mkdtemp(prefix="hm-oracle-blocked-"))
    render(bp, out, freeze_time=DEFAULT_FREEZE_TIME)
    return out


def _skill(preset: Preset) -> str:
    return (_render_root(preset) / "skills" / _SKILL / "SKILL.md").read_text(encoding="utf-8")


def _review(preset: Preset) -> str:
    return (_render_root(preset) / "commands" / "hm" / "review.md").read_text(encoding="utf-8")


# ── the rule body, in the skill ─────────────────────────────────────────────


def test_the_skill_carries_the_read_before_fix_rule() -> None:
    """The three operative clauses, each a silent no-op when absent.

    Dropping the READ leaves the existing "never edit a test" ban unchanged and buys nothing;
    dropping the REFUSAL makes the read advisory, and an advisory read is what the study
    measured no effect from; dropping the RECORD means a refused fix leaves no trace, so the
    next round re-derives the same finding and refuses again.
    """
    body = _skill(Preset.PRODUCTION)
    assert "read the test" in body.lower()
    assert "oracle-blocked" in body
    assert "manual-only" in body


def test_the_skill_names_the_tests_lens_carve_out_as_a_non_trigger() -> None:
    """The pass-1 critical: an unqualified refusal breaks the `tests` lens permanently.

    `tests` is a mandatory lens and raises findings repairable only by writing a test, so a
    refusal that fires on "this fix would change a test" with no exception makes every such
    finding unfixable and unapprovable. The rule must say the refusal fires only when the test
    that would change is NOT the finding's own target.
    """
    body = _skill(Preset.PRODUCTION)
    assert "own target" in body


def test_the_skill_does_not_restate_section_4_5() -> None:
    """Contract Boundaries: §4.5 is cited, never restated.

    A second copy of the three-way classification is the duplication that made the previous
    change's stage cost +900 instead of +512, and CLAUDE.md records a rule written in four
    places producing three of eight review findings on its own.
    """
    body = _skill(Preset.PRODUCTION)
    assert body.count("three-way") <= 1


def test_the_new_section_does_not_collide_with_the_existing_section_5() -> None:
    """`## 5. What the selection does and does not promise` already exists.

    Numbering the new rule §5 is ambiguous between append-as-§6 and replace-§5, and the
    replace reading deletes the selector's stated limits, which §4.5 and the Auto-Fix Loop's
    Step 5 both rely on. Found by terminal plan-validation.
    """
    body = _skill(Preset.PRODUCTION)
    assert "## 5. What the selection does and does not promise" in body
    assert body.count("\n## 5.") == 1
    assert "\n## 6." in body


def test_the_rendered_skill_is_within_the_context_lint_cap() -> None:
    cap = THRESHOLDS[("skill", Preset.PRODUCTION.value)]
    lines = _skill(Preset.PRODUCTION).splitlines()
    assert len(lines) <= cap, f"{_SKILL} SKILL.md is {len(lines)} lines (cap {cap})"


# ── the pointer and the record, in the stage ────────────────────────────────


_ANCHOR_OPEN = "<!-- @hm:oracle-blocked -->"
_ANCHOR_CLOSE = "<!-- @hm:/oracle-blocked -->"


def _refusal_block(preset: Preset) -> str:
    """The Step 4 refusal instruction, delimited by its own anchor.

    Every assertion about the new instruction is scoped to this block, because the whole
    rendered command is not a usable scope: `manual-only` has 18 pre-existing occurrences and
    `targeted-test-selection` has 2, so a document-wide `in body` check is satisfied before
    this task starts. Round 1 of Phase A.5 rejected exactly that shape.

    The anchor is the repo's own idiom (`@hm:boundaries` in `execute.md.j2`) and exists so the
    scope is a delimiter the template controls rather than a heading a later edit renames.
    """
    body = _review(preset)
    missing = (
        "the Step 4 refusal instruction must be delimited by "
        f"{_ANCHOR_OPEN} … {_ANCHOR_CLOSE} — without the anchor every assertion below "
        "silently widens to the whole command, where its terms are already present"
    )
    assert _ANCHOR_OPEN in body, missing
    assert _ANCHOR_CLOSE in body, missing
    return body.split(_ANCHOR_OPEN, 1)[1].split(_ANCHOR_CLOSE, 1)[0]


def test_the_stage_points_at_the_rule_rather_than_restating_it() -> None:
    """wiki:747 — stage prose is the most expensive surface; the skill is the escape.

    Both halves are scoped to the refusal block. The negative half used to read
    `"own target" not in body` over the whole command, which **no correct implementation could
    satisfy**: that phrase already occurs at `review.md.j2:815`, inside the pre-existing
    tests-lens carve-out that ADR-004's amendment and Contract Boundaries both require be kept
    verbatim. The only way to go green was to delete the carve-out — reintroducing the pass-1
    critical the amendment exists to prevent. Caught by Phase A.5 round 1.
    """
    block = _refusal_block(Preset.PRODUCTION)
    assert "targeted-test-selection" in block
    assert "own target" not in block


def test_the_refusal_block_sets_the_tag_and_the_authority_together() -> None:
    """The retag and the reason must co-occur in the instruction, not merely in the file.

    Either alone is broken, and a document-wide check cannot tell the difference:
    `manual-only` without the authority is indistinguishable from an ordinary single-voice
    finding, so the free SPEC audit disappears; the authority without the retag leaves the
    finding `consensus-passed`, which Step 3 re-selects every round — the churn ADR-004's
    amendment dissolves. Scoping to the block is what makes this sensitive to the wiring
    rather than to vocabulary that was already in the file.
    """
    block = _refusal_block(Preset.PRODUCTION)
    assert "manual-only" in block
    assert "oracle-blocked" in block
    assert "unresolved" in block


def test_step_4e_publishes_the_authority_in_its_table() -> None:
    """Step 4e's table is where a fixer looks up what to write.

    An authority the validator accepts but the table never names is one nobody uses; the
    disposition falls back to a missing value and the caller's fail-safe records
    `unresolved`/`no-contract`, silently losing the reason.

    **The selector is anchored on the HEADING, and that is a repair, not a convenience.** It
    read `body.split("Step 4e", 1)` — the bare string, whose first occurrence is a *mention* in
    Step 4d's prose, about fifty lines above the section it names. The slice therefore ended at
    the real heading and never contained the table, so the assertion was answering a question
    about the wrong region of the document. It went red at Phase C against an implementation
    that had already added the row. Phase A.5 round 2 checked this specific split and reported
    it landing correctly; it does not. The `count(heading) == 1` guard is what stops the same
    ambiguity returning, and the terminator is `\n#### ` because `### ` matches inside `#### `.
    """
    body = _review(Preset.PRODUCTION)
    heading = "#### Step 4e"
    assert body.count(heading) == 1, "the anchor must identify the section, not a mention of it"
    step_4e = body.split(heading, 1)[1].split("\n#### ", 1)[0]
    assert "oracle-blocked" in step_4e


# ── S8: the retag is the exclusion mechanism, and nothing else was added ─────


def test_step_3_still_filters_on_the_tag_the_refusal_sets() -> None:
    """The load-bearing causal claim of ADR-004's amendment, asserted directly.

    The amendment says the retag to `manual-only` is what excludes a refused finding from
    Step 3's fixable-finding selection — and that this is why R10 (round churn) and R13
    (`authority` surviving the round merge) stopped existing. That claim rests entirely on
    Step 3 continuing to filter on `Tag = consensus-passed`. If a later edit relaxes that
    filter, the refusal silently stops excluding anything and both risks return with no test
    failing. This is the assertion that fails instead.
    """
    body = _review(Preset.PRODUCTION)
    select = body.split("Select fixable findings", 1)[1].split("3b.", 1)[0]
    assert "consensus-passed" in select


def test_the_exclusion_is_the_retag_and_not_a_second_authority_filter() -> None:
    """Rejects the mechanism the amendment deliberately did NOT choose.

    The planning draft added an `authority`-based filter to Step 3 plus a requirement that
    merge-by-`id` preserve `authority` across rounds. The amendment replaced both with the
    retag. An implementer who does not trust the retag would add the filter *as well* — the
    result still passes every other test here while carrying the machinery R13 described, and
    the two mechanisms would then disagree the moment one of them is edited.

    Scoped to Step 3's selection block so this cannot be tripped by Step 4e's table, which is
    where `oracle-blocked` legitimately appears.
    """
    body = _review(Preset.PRODUCTION)
    select = body.split("Select fixable findings", 1)[1].split("3b.", 1)[0]
    assert "oracle-blocked" not in select


# ── discrimination ──────────────────────────────────────────────────────────


def test_the_predicates_discriminate() -> None:
    """The same predicates must be FALSE against a sibling render.

    Without this, a predicate true of every document — or of the pre-change render — would
    pass every arm above and the module would assert nothing.
    """
    execute = (_render_root(Preset.PRODUCTION) / "commands" / "hm" / "execute.md").read_text(
        encoding="utf-8"
    )
    assert "oracle-blocked" not in execute
