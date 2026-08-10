"""AC-005/006/007 — the fused-command size ratchet, the hoist, and the no-loss check.

**Unit: characters** (`len(read_text())`), not bytes. PLAN ADR-014 corrects an earlier
"bytes" wording: these files are UTF-8 with substantial multi-byte content (—, ≥, ✅),
so `wc -c` and `len()` disagree and only one of them is what a model's context sees.

Three criteria, three different jobs:

* **AC-005** is a ratchet. Every rendered command carries a committed ceiling and a
  floor. The ceiling stops the file growing back; the **floor** stops it being met by
  gutting the render — the failure mode PLAN ADR-017 caught, where an 8,738-char
  "documentation-only" trim turned out to delete runtime-behavioural instructions.
  `exec-rev-wrap-ver` additionally carries the hand-set 119,000 ceiling from ADR-014.
  Each entry also records the **pre-change** size, an observation taken before any of
  this phase's edits, so the table cannot be satisfied by whatever the change happened
  to produce.

* **AC-006** is the hoist. The shared prose of the preflight and Gate-0 blocks renders
  ONCE; the per-stage command line renders once PER STAGE. The stage arms assert the
  four `--stage` values are **present**, not absent: one receipt per stage IS the Gate-0
  missing-stage mechanism (PLAN ADR-016 / risk R10), so collapsing them would make the
  autoloop driver see three stages missing on every iteration.

* **AC-007** is the no-loss check, and it is an **equality**, not a subset. The
  differential between an atomic render and the fused render is measured to be exactly
  one heading and two executable lines — the autopilot auto-advance block, which
  `workflow_fuse.fuse()` deliberately omits (`autopilot_advance_enabled=False`, see the
  REVIEW P1-3 rationale there). Asserting equality against that named exemption means
  any *other* instruction the fused render drops fails immediately; a subset-with-
  exemptions would have silently absorbed it.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from harness_maker.models import InterviewAnswers, Preset, ProjectProfile, Target
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize

from .conftest import pin_install_ref

# ── the ratchet table ──────────────────────────────────────────────────────────
# `pre_change` is an observation of the committed render at 8addbee0, taken before
# this phase edited anything. `measured` is the post-change size. Ceiling =
# measured * 1.02, floor = measured * 0.80 (ADR-014), except exec-rev-wrap-ver whose
# ceiling is the hand-set 119,000.

# ADR-014's hand-set ceiling is measured against a DIFFERENT render: this repo's own
# `.claude/harness.yaml` (second opinion + full reviewer set enabled). The fixture render
# above is ~16% smaller, so applying this figure to it would assert nothing. Keeping the
# two apart is what makes each bind — see `test_the_repo_render_is_under_the_adr014_ceiling`.
#
# Re-based 2026-07-29 from 119,000 (PLAN-wrapup-context-carry Phase 3). Derivation below.

# ── the atomic arm (PLAN-workflow-step-audit Phase 0.5, ADR-011 assertion 2) ────
# The table above holds five FUSED entries and no atomic ones, so until now nothing
# measured the size of a single stage command — and every cutting phase of that PLAN
# edits exactly those. Frozen against the PRE-change render, before any phase cuts.
#
# One int, not the `(pre_change, measured)` pair the fused entries carry: that pair's
# `size < pre` arm encodes "this phase already shrank it", which is true of the fused
# compaction that produced those numbers and false here — pre and post are the same
# observation at freeze time, so the arm would fail by construction.
#
# Ceiling and floor follow ADR-014's ratio (`* 1.02` / `* 0.80`). Note what the floor
# can and cannot do: at 20% slack it catches the render being GUTTED, never a single
# instruction being deleted (~0.5% of any of these). That gap is why
# `test_instruction_preservation.py` exists; do not read a green floor as evidence that
# nothing was removed.
#
# WHICH RENDER: these numbers come from the `flag_on` fixture below, which is
# `dev_mode: spec-driven` — `InterviewAnswers.dev_mode` defaults to `DevMode.SPEC_DRIVEN`
# (`models.py:948`) and `_render()` never overrides it. The instruction baseline in
# `_instruction_baseline.py` freezes BOTH dev_mode arms, and the aggregate arm below
# measures this repo's `.claude/harness.yaml` (task-driven). Three arms, two configs —
# stated here because the mismatch was once a live blind spot: spec-driven-only
# instructions were absent from the instruction snapshot and invisible to this floor.
# Re-baselined 2026-07-29 after Phases 2–5. Each entry moved for a named reason:
#   execute  +20    Phase D's select-then-one-call prose costs slightly more than the
#                   three lines it replaced — and removes one call (ADR-002's trade).
#   research +449   the Claude-only `Explore` fan-out block. This one is TIGHT: it was
#                   compressed twice to stay under the OLD ceiling (23,509) rather than
#                   raise it, because ADR-011 forbids raising a ceiling to pass a phase.
#   wrapup   −1976  Steps 6→7.6 collapsed into `wrapup_land`.
#   spec     −211   Steps 4/4.5 collapsed into `spec_machine check --all`.
#   plan/review/verify — untouched by this PLAN; they drifted down under the `hm`
#                   rewrite (d98355d6) and stayed inside the 20% floor, so the table was
#                   never re-baselined for them. Doing it here removes that slack.
#
# review 27590 → 29235, PLAN-second-opinion-acceptance-gate ADR-012 (2026-07-30). This raise
# EXPLICITLY OVERRIDES the ADR-011 prohibition quoted 12 lines above — read that ADR before
# treating this entry as licence. In short: the compaction was done first (the gate procedure
# moved to the `second-opinion-gate` skill, the agent's half to `code-verifier` mode B, four
# compression passes: +12333 → +3547, −71%), and the +1645 that remains is UNGUARDED
# correctness — Step 3.4's id stamping, the round-state pointer, Step 4b's 4-step reasoning fix
# (it was comparing a chain shape reviewers never emit), and the exit reason. Compressing those
# away deletes fixes rather than prose. Anyone raising this again is expected to show a
# comparable compaction ratio first and to quote ADR-011 as ADR-012 does.
# configure raised +210 aggregate, PLAN-worktree-side-defaults (2026-08-06). Same bar as
# ADR-012/Phase-4 above: compaction FIRST. Raw addition was +534 (the `/hm:configure`
# worktree dimension + its dispatch note + the rewritten `worktree-isolator` skill). Two
# passes cut it to +210 (−61%): the dimension went from seven lines to four, the dispatch
# note from five to three, and the skill's config section lost its restated rationale.
# The residue is not prose — it is the ONLY discoverable way to change the axis, and
# "there is no supported way to change this" is the defect this PLAN exists to fix. The
# offsetting deletions (execute's flag-off Step 0 block, `branch_prefix` from the skill)
# do not show up here because the baseline renders this repo's own harness, which is
# isolation-ON.
# execute/research/spec/verify raised, PLAN-autopilot-advance-noop Phase 4 (2026-07-31).
# Same bar as ADR-012 above: compaction FIRST, then the residue.
#   Raw additions were +524/+726/+822/+822 across six stages. Two compaction passes
#   (picker rewritten from a paragraph to a branch list, slug + precedence prose halved,
#   terminal clause 137→81 chars) absorbed plan and review ENTIRELY — both are back under
#   their unchanged ceilings — and cut the rest to +15/+162/+84/+218.
#   What remains is unguarded correctness, not prose. Each item is a distinct way the
#   feature was silently dead: the picker asking `autopilot status` instead of guessing
#   from the marker FILE (a stale file read as "already armed", so autopilot never turned
#   on); its `foreign` branch (without it, arming clobbers a live peer's marker and their
#   chain dies at the next boundary with a bare kill_switch); `--slug` on the boundary
#   call plus the literal-slug warning (an argument-less `Skill()` stalls every
#   argument-parsing stage); and the two-sided precedence clause (the terminal STOP reads
#   earlier and stronger than the auto-advance block, so a model resolving the conflict
#   conservatively stops — the reported bug). Compressing any of these deletes the fix.
# review raised 29235 → 29848, PLAN-review-round-inflation Phase 3 (2026-08-01).
# Same bar as ADR-012 and the Phase-4 entry above: compaction FIRST, then the residue.
#   Raw additions were +774. Three passes cut them to +613: the §5 load imperative and the
#   step-2 pointer tightened (−88), and the `caused_by` grammar moved into §5 — where a rule
#   belongs under this PLAN's ADR-005 — leaving exemplar rows in the stage (−73).
#   30009 → 29921 → 29848 against the old 29819 ceiling. Trimming stopped there: closing the
#   last 29 chars means cutting meaning, and shaving wording after the logic is settled is the
#   unreviewed-compaction failure this very PLAN names as a defect source (the reference case
#   inverted a negation that way, and no gate caught it).
#   What remains is unguarded correctness. The two DELETED blocks were restatements of
#   `second-opinion-gate` §5 (ADR-005 — the duplicate contract that drifted); the additions are
#   the §5 load imperative that replaces them and must be UNCONDITIONAL, the two-arm trigger's
#   firing condition at its point of use, `caused_by` in the iteration record (without it
#   ADR-001 arm (b) has nothing to read and measure A misses exactly the lone regressions it
#   targets), the Final Summary counters, and the four measure-C fields on the emit roster
#   (absent there, the schema accepts them and nothing ever sends them — this project's
#   recorded absent-case failure).
#   Why this ceiling moves while the AGGREGATE ratchet passes at claude −615 / codex −123:
#   the larger of the two deletions is inside `{% if config.second_opinion.models %}`, so it
#   frees nothing in the models-off render this fixture builds, while every addition is
#   unconditional. That asymmetry is recorded in the PLAN's ADR-008 and R10 as an accepted
#   consequence for `models: []` harnesses; this line is that consequence reaching a gate.
# Re-frozen 2026-08-05 (PLAN-harness-diet Phases 3+4). +2,497..+3,171 chars per command,
# +19,041 total. Attribution was measured, not assumed:
#   ~+2,400 of each  ADR-010 flipped the `AutonomyConfig.level` DEFAULT from `gated` to
#                    `auto_safe`, and the session-start autopilot picker renders under
#                    `config.autonomy.level != "gated"`. This fixture builds a DEFAULT
#                    config, so the block that was previously gated OUT is now in every
#                    stage command. The picker IS what auto-arming means — this is the
#                    feature arriving at a gate, not prompt bloat.
#     ~+136 of each  ADR-016's frontmatter `description:` line.
# This is the ONE place in this PLAN where a size constant moves UP. It does not touch this
# repo's own surface: `.claude/harness.yaml` was already `auto_safe`, so the aggregate
# ratchet moved +1,616 claude / +41 codex — the descriptions plus the new `| autopilot |`
# row in `help.*.md.j2`, which also reaches the Codex skill render (an earlier note here
# said "+1,571 (the descriptions)" and "codex +0"; both were wrong, and the codex figure
# was wrong in KIND — it claimed the change did not touch that target at all). The shipped
# surface is still ~45% below
# the pre-diet 1,173,667. A NEW harness pays the picker; that trade is ADR-010's, recorded
# rather than absorbed. `autopilot_persistent: true` (also now default) arguably makes the
# picker redundant, but no ADR decided that and the render gate is unchanged.
# Re-baselined 2026-08-05 by PLAN-workflow-loop-efficiency **P7**, which is the phase that
# OWNS this table (ADR-010). No earlier phase touched it, deliberately: a phase that
# re-baselines the ratchet it tripped is `ratchet-rebaselined-by-its-own-subject` (count:2),
# and the whole guard then measures nothing. Every delta below is attributed to the phase
# that caused it in `work-docs/BASELINE-DELTA-P7.md`, and a structural test fails if a
# changed key has no attribution row there.
#
#   execute 29820 → 33774  (+3954: P2 Phase D.5 step, P3 A.5 ledger emit)
#   plan    44827 → 46008  (+1181: P3 validator ledger emit)
#   review  32502 → 34760  (+2258: P3 payload persistence net of P1's Pass 1.5 removal,
#                           plus the review-round F2 correction — the persistence call was
#                           writing N identical copies of the merged list under N reviewer
#                           labels, and the block that stops that recurring is prose)
#
# Read the aggregate row in the delta document before treating this as routine: this is a
# cost-REDUCTION plan that raised the shipped surface, and the raise only pays for itself if
# stage 2 reads the ledgers these calls fill and deletes something.
#
# aggregate claude raised 361582 → 362186 (+604), PLAN-onboarding-interview-ux Phase 6
# (2026-08-06). Same bar as ADR-012 and the `configure +210` entry above: compaction FIRST.
# NOTE the artifact — this raise lives in `tests/structural/surface_baseline.json`, not in
# this file. `configure` and `health` have NO per-command ceiling at all (they are excluded
# by `test_the_atomic_table_covers_every_atomic_command`), so the JSON is the only binding
# number, and it moves as four coupled fields: the two `chars` entries, the aggregate (which
# `test_the_committed_numbers_are_not_zeros` asserts equals the per-command sum), and a
# recomputed `payload_digest`. `build_baseline()` was not used — `assert_sha_is_durable`
# refuses to run from a task branch.
#   Raw addition +1162; three passes cut it to +604 (−48%). What was cut: a dangling
#   `Default model` fragment, `Delivery metrics tuning` 7→5 lines, four repeated
#   "omit `--x` … pass `\"\"` to clear" sentences collapsed to one rule, and two numbered
#   single-question sub-blocks turned back into prose. Full per-pass accounting in
#   `work-docs/BASELINE-onboarding-offset-ledger.md`.
#   codex delta is 0, structurally: `configure.md.j2` / `health.md.j2` render into
#   `_base_files` only and have no counterpart in `_codex_target_files`.
#   The residue is unguarded correctness: `/hm:configure` previously named NEITHER
#   `second_opinion` nor `autonomy` nor `locale`, so a harness installed with any of them
#   off could only be changed by hand-editing `harness.yaml` — "there is no supported way to
#   change this" is the same defect the `configure +210` raise cited, arriving again. The
#   dispatch appendix states omit-preserves vs `""`-clears, which is a data-loss boundary,
#   not prose.
#   The `/hm:health` advisory is INVISIBLE here (+1 char, a newline): it renders under
#   `{% if not config.second_opinion.models %}` and this repo's harness has models set. Its
#   correctness is gated by `tests/unit/test_render_configure_health_second_opinion.py`
#   instead — do not read a green aggregate as evidence that block works.
_ATOMIC_RATCHET: dict[str, int] = {
    # 33774 → 34533 (execute-step5-model-mismatch, 2026-08-08). Same bar as ADR-012 and the
    # entries above: compaction FIRST, then the residue. Raw addition was +954; two passes cut
    # it to +424 (−55%) — the new gate lost its dual codex/non-codex code fence for an inline
    # command, the dirty-base paragraph and the crumb note were tightened now that both are
    # provably loop-only, and the "sequences without wrapup" prose was halved.
    # The residue is not prose. Step 5 instructed `worktree finalize <WT> stage-only` while the
    # stage's own Step 0 is the per-task `task-preflight` — both render under the same `wt_on`,
    # so on every isolated `/hm:execute` the document told the operator to merge into base a
    # worktree that `task-land` owns, citing a "Step 0 `worktree create`" the rendered file no
    # longer contains. The finalize is CORRECT under `/hm:loop`, whose `<WT>` is an
    # `execute-<uuid>`, so a render-time gate cannot separate them: the residue is a runtime
    # read of `rev-parse --abbrev-ref HEAD` that skips Step 5 on `hm/*` — the discriminator
    # wrapup Step 7.7 already uses. Compressing it away restores a destructive instruction.
    # Attributed in work-docs/BASELINE-DELTA-execute-step5-model-mismatch.md.
    # 34533 → 35322 (multi-lens-review-round, 2026-08-10). +789. Phase A.5 went from one
    # `test-reviewer` dispatch to three lens-scoped ones in a single message, and gained the
    # merge algebra those three outputs need — PASS iff all three, union of `blocking_issues`
    # deduped on `test_file:test_function:category`, worst-quality `per_scenario`, and
    # `passing_tests` demoted to advisory because it carries bare function names with no
    # `test_file` and so cannot identify the test a rewrite would freeze.
    #
    # The compaction-first bar is met by SUBSTITUTION, not by prose trimming: the shared
    # reviewer brief is stated once and the three dispatch lines reference it, and the old
    # per-dispatch ledger bullets collapsed to per-round ones (ADR-007). Raw addition was
    # ~1.5k; what landed is +789.
    #
    # The residue is not compressible without deleting instruction. Three lenses need three
    # dispatch lines — a single parameterised `Task(` template with a `<lens>` placeholder was
    # tried first, cost ~500 fewer chars AND zero round-trips, and was REVERTED: the repo's own
    # fan-out precedent (`research.md.j2`) uses three literal lines, and choosing the cheaper
    # form because it was cheaper is the exact move that produced two of the four P0s in
    # `opus5-selfreview-vs-harness-gates`. Attributed in
    # work-docs/BASELINE-DELTA-multi-lens-review-round.md.
    #
    # 35322 → 37048 (+1726, same task, review round 2). Not new feature surface — every
    # character is a defect fix a 3-voice review found in the round-1 text, and each one closes
    # a hole that a render test could not see:
    #   • the round-2 PASS rule was UNSATISFIABLE ("all three PASS" + "re-dispatch only failing
    #     lenses" + "no verdict carries" — three verdicts cannot exist in round 2), so A.5 either
    #     never cleared a retry or silently carried a stale verdict;
    #   • a dead dispatch had no repair path, leaving a FAIL round with nothing to act on;
    #   • the brief told lenses to report out-of-lens defects into a `suggestions` field the
    #     schema does not have, so they were discarded and the lens returned PASS — which
    #     defeated the measured justification for the fan-out itself;
    #   • the dedupe key lacked `line`, collapsing two distinct bad assertions in one function.
    # Attributed in the same BASELINE-DELTA document.
    #
    # 37048 → 38197 (+1149, same task, review round 3). Again defect repair only, zero new
    # round-trips. The round-2 FIXES created three of these: the merge trusted a lens's
    # self-reported PASS while the new brief openly allows a lens to report a defect (so an
    # inconsistent-but-parseable reply passed the gate) — it now RECOMPUTES from the merged
    # fields; routing duplicates to `per_scenario.quality=FAIL` made a blocking state with no
    # repair action, burning the budget on identical rounds — a third repair arm now retargets
    # or deletes the offending test; and a test AUTHORED for `scenarios_missing[]` was reviewed
    # only by the coverage lens that asked for it, never by red-correctness or discrimination —
    # authoring now re-dispatches all three.
    #
    # 38197 → 39343 (+1146, same task, review round 4 — the last). Defect repair, zero new
    # round-trips. Round 3's own fixes produced the biggest one: the re-dispatch rule had grown
    # to four clauses and clause (c) — "supplied a blocking_issues entry even if it returned
    # PASS" — was UNREACHABLE, because the agent's PASS requires zero blocking_issues, so such a
    # lens had already returned FAIL. Meanwhile the hole it was written for (a REWRITE means the
    # other two lenses never see the changed file) stayed open, since the authoring clause only
    # fired on authored tests. All four clauses collapsed to one: **repair anything → re-dispatch
    # all three**, which also removes the standing contradiction with "no verdict carries".
    # Also: the dedupe key stopped being line-keyed (two lenses anchor one defect on different
    # lines, so it almost never merged) and now carries a line LIST; `per_scenario` FAIL with an
    # empty `covered_by` routes to the authoring arm instead of naming a test that does not
    # exist; and a truncated sentence — "Ask what those newly made reachable." — was completed.
    "execute": 39343,
    # 46008 → 47503 (validator-pass-cap-telemetry + its review round): the pass cap, the
    # corrected per-(agent,stage,slug,run-id) terminal invariant, the `coherence` pointer,
    # and the shell-quoting rules for the free-text `--reason`. Attributed in
    # work-docs/BASELINE-DELTA-validator-pass-cap.md.
    "plan": 47503,
    "research": 26673,
    # 34760 → 35828 (review round 4): the `CHANGES_REQUESTED` resolution bullet gained an
    # autopilot carve-out, and the APPROVED+human_review_needed bullet was split so the
    # interactive and autopilot paths stop saying the same thing. Both were live
    # contradictions with the enforceable gate — nothing in code can tell a failed grade
    # from a passing one, so this prose IS ADR-010's guarantee on the review side and
    # cannot be compressed away. Attributed in
    # work-docs/BASELINE-DELTA-workflow-time-token-savings.md.
    "review": 35828,
    "spec": 30537,
    "verify": 23796,
    # 41345 → 42452 (PLAN-workflow-time-token-savings B3/B4): the shared
    # `stage_end_summary` partial gained the judgment-gate discriminator and
    # `step_manifest` gained the `ask-pending` picker branch, both of which every stage
    # command inlines. wrapup is the largest command, so it is the one that crossed its
    # ceiling first. Attributed in work-docs/BASELINE-DELTA-workflow-time-token-savings.md.
    "wrapup": 42452,
}


# ── AC-007's named exemption ───────────────────────────────────────────────────
# The ONLY content `fuse()` intentionally drops. Kept as an equality target so a
# second omission cannot hide behind it.
# Matches BOTH spellings of the same call: the long `hm <mod>` form
# and the `hm <mod>` console-script shorthand that replaced it. They dispatch through the
# identical `runpy.run_module` path, so an exemption that recognised only one would have
# reported the autopilot block as a NEW loss the moment the shorthand landed.

# ── fingerprints (AC-006) ──────────────────────────────────────────────────────
# Each names a sentence from the block's BODY, never its heading, so a heading left
# behind with an empty body fingerprints as 0 and the `== 1` arm fails.
_FINGERPRINT = {
    "worktree_preflight": "Claim/refresh it and surface concurrent work + drift",
    "gate0_receipt": "Gate 0 only reads receipts written under `iter-N` for N≥1.",
    # ADR-020's third hoisted block. The preamble and the atomic block word the rule
    # differently ("a stage's summary banner" vs "this banner"), so the fingerprint is
    # the clause they share verbatim — a wording-only fingerprint would have matched
    # neither. Without this entry the mutation receipt's M8 survived: nothing asserted
    # the rule still existed anywhere after the stages stopped carrying it.
    "stage_end_banner": "the autoloop uses machine receipts, not prose",
}

# Content of the preflight tail, which the fused render keeps ONLY in the preamble.
# Fingerprinting the intro alone let M10 survive: an atomic render could lose its whole
# tail — the `<WT>` rule and the drift remedy — with every assertion still green.
_PREFLIGHT_TAIL_MARKERS = (
    "worktree task-refresh <slug>",
    "**Treat that exact string as `<WT>`**",
    "`task-refresh` rebases `hm/<slug>` onto the base tip",
)

_HEADING = re.compile(r"^#{2,6} .*$", re.M)
_EXEC_LINE = re.compile(r"^\s*!.*$", re.M)


def _render(*, feature_branch_workflow: bool, tmp: Path) -> dict[str, str]:
    """`fused_workflows` is passed explicitly: its model default is a single 3-stage
    workflow, so an implicit render would not contain the commands this gate measures
    and every assertion below would KeyError rather than assert.

    The install-ref pin is applied HERE rather than left to the conftest autouse fixture:
    these render fixtures are module-scoped and are therefore set up before any
    function-scoped autouse fixture runs.
    """
    with pytest.MonkeyPatch.context() as mp:
        pin_install_ref(mp)
        render(
            synthesize(
                ProjectProfile(),
                InterviewAnswers(
                    preset=Preset.PRODUCTION,
                    targets=[Target.CLAUDE_CODE],
                    worktree={"feature_branch_workflow": feature_branch_workflow},
                ),
            ),
            tmp,
            freeze_time=DEFAULT_FREEZE_TIME,
        )
    root = tmp / "commands" / "hm"
    return {p.stem: p.read_text(encoding="utf-8") for p in sorted(root.glob("*.md"))}


@pytest.fixture(scope="module")
def flag_on(tmp_path_factory: pytest.TempPathFactory) -> dict[str, str]:
    return _render(feature_branch_workflow=True, tmp=tmp_path_factory.mktemp("on"))


@pytest.fixture(scope="module")
def flag_off(tmp_path_factory: pytest.TempPathFactory) -> dict[str, str]:
    return _render(feature_branch_workflow=False, tmp=tmp_path_factory.mktemp("off"))


def headings(text: str) -> set[str]:
    return {h.strip() for h in _HEADING.findall(text)}


def executable_lines(text: str) -> set[str]:
    return {ln.strip() for ln in _EXEC_LINE.findall(text)}


def shared_prose_fingerprints(text: str, block: str) -> int:
    return text.count(_FINGERPRINT[block])


def stage_arg_values(text: str, marker: str) -> set[str]:
    if marker == "iter_receipts write":
        return set(re.findall(r"--stage (\w+) --verdict", text))
    if marker == "task-preflight":
        return set(re.findall(r"task-preflight <slug> \"\$\(pwd\)\" --stage (hm:\w+)", text))
    raise AssertionError(f"unknown marker {marker!r}")


# ── positive controls ──────────────────────────────────────────────────────────


def test_the_fixtures_actually_rendered_commands(
    flag_on: dict[str, str], flag_off: dict[str, str]
) -> None:
    """Every assertion below is vacuous against an empty render."""
    # The fused arm's guard went with the fused table (PLAN-harness-diet ADR-001); the
    # atomic guard below is now the whole control. Without it every `_ATOMIC_RATCHET`
    # assertion would KeyError-or-pass against a render that produced no stage commands.
    assert set(_ATOMIC_RATCHET) <= set(flag_off), sorted(set(_ATOMIC_RATCHET) - set(flag_off))
    assert set(_ATOMIC_RATCHET) <= set(flag_on), sorted(set(_ATOMIC_RATCHET) - set(flag_on))
    assert all(len(flag_on[k]) > 10_000 for k in _ATOMIC_RATCHET)


def test_no_rendered_command_bakes_a_machine_specific_absolute_path(
    flag_on: dict[str, str],
) -> None:
    """The ratchet's constants are only portable if the render is.

    `harness_maker_src_path` appears dozens of times per fused command; unpinned it is
    the checkout's absolute path, which would make every number in `_RATCHET` a
    measurement of this machine. Property, not symptom: any `/home|/Users|/root` path
    fails, so a capture from any checkout location is caught, not only a worktree.
    """
    machine_path = re.compile(r"(?:/home/|/Users/|/root/)[\w.\-/]+")
    for name, text in flag_on.items():
        found = machine_path.findall(text)
        assert not found, f"{name}: {sorted(set(found))[:3]}"
    # Positive control for the pin itself: the portable form must actually appear.
    assert "$HOME/harness-maker" in flag_on["wrapup"]


# ── AC-005 ─────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("name", sorted(_ATOMIC_RATCHET))
def test_atomic_commands_within_budget(flag_on: dict[str, str], name: str) -> None:
    """AC-005 extended to the seven atomic commands (PLAN-workflow-step-audit Phase 0.5).

    Landing this BEFORE the cutting phases is the whole point: a floor introduced after
    the cuts is measured from the already-reduced render, so the phases that actually
    delete would have run unguarded — the withdrawn ADR-017 failure, repeated.
    """
    measured = _ATOMIC_RATCHET[name]
    ceiling = int(measured * 1.02)
    floor = int(measured * 0.80)
    size = len(flag_on[name])
    assert floor <= size <= ceiling, f"{name}: {size} outside [{floor}, {ceiling}]"


def test_the_atomic_table_covers_every_atomic_command(flag_on: dict[str, str]) -> None:
    """A command missing from the table is a command with no budget at all — the silent
    way this arm narrows. Meta commands are excluded by name, not by omission — and
    since the fused axis went (ADR-001) there is nothing else left to exclude."""
    rendered_atomic = set(flag_on) - {
        "configure",
        "health",
        "help",
        "loop",
        "loop-p5-batch",
        "make",
        "metrics",
        "uninstall",
    }
    assert rendered_atomic == set(_ATOMIC_RATCHET), sorted(rendered_atomic ^ set(_ATOMIC_RATCHET))


# ── ADR-011 assertion 3 — the aggregate shipped surface ────────────────────────


def test_aggregate_shipped_surface_does_not_grow() -> None:
    """The failure mode the per-command arms structurally cannot see.

    The prior compaction effort removed 4,437 characters from one command while adding
    3,765 to a heavily-invoked one: every per-command ceiling held and the shipped
    surface still grew 0.75%. Only a total catches that, and it is measured against
    Phase 0's frozen baseline through the SAME generator Phase 6 re-invokes.

    Summed over the **frozen** command set, so a legitimate future addition — an eighth
    command, a new target — adds an entry rather than forcing this constant to be
    relaxed. Non-increase is the ratchet; the strict decrease this PLAN promises is
    Phase 6's final re-verification, not this arm.

    A reader of this test alone would conclude that a newly added command escapes the
    total, and would be half right: it escapes *this* sum by design, and is caught by
    `test_surface_baseline.py::test_baseline_shape_matches_the_generator`, which asserts
    frozen-vs-measured command-set and variant-set equality. Adding a command means
    regenerating the baseline, which is the explicit act that arm forces.
    """
    from ._surface_baseline import load_baseline, measure_surface

    frozen = load_baseline()
    current = measure_surface()
    for variant, commands in frozen["surface"].items():
        missing = set(commands) - set(current[variant])
        assert not missing, f"{variant}: commands vanished from the render: {sorted(missing)}"
        now = sum(current[variant][name]["chars"] for name in commands)
        was = frozen["aggregate_chars"][variant]
        assert now <= was, (
            f"{variant}: shipped surface grew {now - was} chars over the Phase 0 baseline "
            f"({was} → {now}). A per-command ceiling cannot see this."
        )


# ADR-014's per-command ceiling was measured on `exec-rev-wrap-ver`, the largest FUSED
# command. That command no longer renders (PLAN-harness-diet ADR-001), so the test that
# measured it was deleted rather than re-pointed: its successor is
# `test_aggregate_shipped_surface_does_not_grow` above, which budgets the WHOLE shipped
# surface instead of one command. Per-command ceilings survive in `_ATOMIC_RATCHET`.


def test_an_inflated_render_fails_the_ceiling(flag_on: dict[str, str]) -> None:
    """Negative control — the budget rejects growth rather than merely observing it.

    Re-pointed from `exec-rev-wrap-ver` to the largest ATOMIC command when the fused
    axis was deleted (PLAN-harness-diet ADR-001). The mechanism under test — AC-005's
    ceiling — is unchanged; only the subject moved. Deleting these two controls instead
    would have removed the proof that the ratchet rejects rather than merely observes.
    """
    measured = _ATOMIC_RATCHET["wrapup"]
    inflated = flag_on["wrapup"] + "x" * 10_000
    assert len(inflated) > int(measured * 1.02)


def test_a_gutted_render_fails_the_floor(flag_on: dict[str, str]) -> None:
    """Negative control — ADR-017's failure mode: meeting the ceiling by deleting content."""
    measured = _ATOMIC_RATCHET["wrapup"]
    gutted = flag_on["wrapup"][: int(measured * 0.5)]
    assert len(gutted) < int(measured * 0.80)


# ── AC-006 ─────────────────────────────────────────────────────────────────────


def test_the_fingerprint_rejects_a_heading_with_an_empty_body(flag_on: dict[str, str]) -> None:
    """A block that keeps its heading and drops the prose must not fingerprint as 1."""
    text = flag_on["wrapup"]
    for block, sentence in _FINGERPRINT.items():
        assert shared_prose_fingerprints(text.replace(sentence, ""), block) == 0, block


def test_atomic_renders_keep_their_own_copy(flag_on: dict[str, str]) -> None:
    """The hoist is fused-only — an atomic command still carries the WHOLE block.

    "Whole" is checked through the tail markers, not just the intro fingerprint. An
    atomic render that kept the opening sentence and lost the `<WT>` rule and the
    drift remedy fingerprinted as intact; the mutation receipt's M10 survived on
    exactly that, and nothing else in this file measures atomic size.
    """
    for stage in ("execute", "review", "wrapup", "verify", "plan", "spec", "research"):
        text = flag_on[stage]
        assert shared_prose_fingerprints(text, "worktree_preflight") == 1, stage
        assert shared_prose_fingerprints(text, "gate0_receipt") == 1, stage
        assert shared_prose_fingerprints(text, "stage_end_banner") == 1, stage
        for marker in _PREFLIGHT_TAIL_MARKERS:
            assert text.count(marker) == 1, f"{stage}: {marker}"
        assert "- **`skipped`** —" in text, stage


# ── AC-007 ─────────────────────────────────────────────────────────────────────
