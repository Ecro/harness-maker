"""Phase 3 of PLAN-token-efficiency-autopilot-ux-speed — AC-005.

`autopilot_advance_enabled` has zero producers (its only producer, `workflow_fuse.py`, is gone) and
the advance block is not gated on `autonomy.level`, so a `gated` harness ships ~24.9 kB of prose
whose only possible output is `kill_switch`. This guards removing the dead name and adding the gate.

**Why the guard lives here and not in `_instruction_baseline.AXES`.** `AXES` holds the arms of
ONE config axis (spec strictness — it was the retired methodology axis until
SPEC-dev-mode-removal re-spelled the arms 1:1) and `entry_key` is `command@<arm>`, so adding
`autonomy.level` there forces a second axis plus a new key grammar — which collides with the
`<command>@<arm>` grammar the PLAN's Contract Boundary pins and drags `_SCHEMA_VERSION` 2→3
behind it. The PLAN's carried risk named this alternative explicitly.

**The goldens in `autopilot_gate_golden.json` were captured BEFORE the template edit.** A snapshot
taken afterwards records whatever the edited template produces, so it would freeze an
over-swallowing gate rather than flag it — `ratchet-rebaselined-by-its-own-subject` applied to a
byte baseline. Regenerating this file to make a red test green is therefore never the fix **for a
change that is this guard's own subject**.

**What the rule does NOT cover, learned 2026-09-13.** The golden byte-locks 15 commands across 4
arms, and the property it proved — that the autopilot gate edit left the non-gated arms alone —
was established when that PLAN landed and cannot be re-established afterwards. Any LATER change by
any other task that legitimately edits a covered template lands here as a permanent red with no
producer script and no documented way out. That is a third party moving the bytes, not the subject
rebaselining itself, and the two need opposite treatment: **re-capture, and record in the list
below which task moved what and why.** Refusing to re-capture in that case does not preserve the
original proof — it only stops every future edit to any rendered command.

Re-captures (append; never silently overwrite):

- **2026-09-22, `codex-stage-invocation`** — help corrects Codex examples and the six-stage
  count. The SPEC hash drift also reproduces using unmodified HEAD source extracted to an
  isolated baseline directory; refresh that inherited stale hash alongside the snapshots.
  Only help/spec moved in all four arms; command sets and autonomy gates are unchanged.

- **2026-09-21, release 0.59.0** — same per-release case: 56 lines (14 commands × 4 arms), all the
  frontmatter `harness_maker_version:` key, and substituting `0.59.0` back to `0.58.0` reproduces
  every previous hash — checked across every arm, so no content moved.

- **2026-09-21, `intent-vocabulary-and-owners`** — execute, review, spec, wrapup and
  help adopt canonical intent vocabulary and preserve legacy PLAN link reads. All four
  arms have identical moved command sets; no commands added or removed. Autonomy
  conditions and answer gates are unchanged.

- **2026-09-21, `dev-mode-removal`** — the methodology axis folded into `spec.strictness`, and the
  two `auto_safe` arms re-spelled 1:1 (`@task-driven`→`@warn`, `@spec-driven`→`@block`, content
  unchanged) before comparing. `configure`, `execute`, `make`, `review`, `spec` and `verify`
  moved in all four arms; `wrapup` moved in `auto_safe@warn` only, because Step 3.6 renders at
  `warn` alone. Causes, one per command: `/hm:configure` gains the `spec.strictness` entry;
  execute's SPEC-need Step 0.1 renders at every strictness; `make.md` drops a `dev_mode` word;
  review's `finalize --spec` is unconditional; spec passes `--strictness` and its gate table is
  re-spelled; verify renders six checks everywhere. Autonomy gating untouched. Verified each
  arm's moved set and that no command was added or removed before re-capturing.

- **2026-09-21, `codex-plan-integration-repair`** — only `execute` moved in all four
  arms; command sets are unchanged. Inputs now reuse a PLAN or let Step 0 create it,
  fixing the contradictory missing-PLAN error after plan-stage retirement. Autonomy
  gating is unchanged. Verified each arm's moved set before re-capturing.

- **2026-09-20, rebase of `plan-stage-absorption` onto `main` (fifth re-capture)** — `wrapup`
  moved in all four arms, identically in `auto_safe` and `ask`. Command set unchanged. **Not this
  task's movement**: `697036be fix(intent): the withdrawal criterion counts a quiet window` edits
  `wrapup.md.j2`, and it landed on `main` while this branch was in flight. The re-capture happens
  here only because the rebase is where the two met — the third-party case the rule above names.
  Verified before re-capturing that `wrapup` is the ONLY moved command in every arm and that
  nothing was added or removed.

- **2026-09-20, `plan-stage-absorption` (fourth re-capture, review round 2)** — `execute` and
  `spec` moved in all four arms, identically in `auto_safe` and `ask`. Command set unchanged.
  The review's consensus-passed fixes: `execute.md.j2` moved `Step 0.3` after `Step 0.2` (it
  verified `spec_need_verdict` before `Step 0.1` judged it), dropped the SPEC-need pair from
  Step 0's authored frontmatter (declaring it forced an unjudged guess the preserving writer
  then kept forever), and single-quoted every model-filled placeholder in the Step 0.1 recipes;
  `spec.md.j2` lost a stale backticked `plan` reference. Both arms move because the Step 0.3
  relocation and the `spec.md.j2` line sit outside every `dev_mode` gate. Verified before
  re-capturing that no command was added or removed in any arm.

- **2026-09-20, `plan-stage-absorption` (third re-capture)** — `spec` alone moved, in all four
  arms, identically in `auto_safe` and `ask`. Command set unchanged from the second re-capture.
  The cross-model second-opinion main loop moved into `/hm:spec` Step 4.6 from the removed plan
  stage, which CLAUDE.md's mandatory matrix requires over the judgment-gated stages. Verified
  before re-capturing that nothing was added or removed in any arm.

- **2026-09-20, `plan-stage-absorption` (second re-capture, supersedes the Phase-1 entry below
  in scope)** — `plan` was REMOVED from every arm, and eight to nine other commands moved in each
  (`execute`, `spec`, `help`, `loop`, `research`, `review`, `verify`, `wrapup`, plus `health` in
  the `auto_safe` arms). Verified before re-capturing that the only command-set change is the
  removal of `plan` and that nothing was ADDED in any arm. The breadth is explained, not
  alarming: `step_manifest.md.j2` interpolates `config.autonomy.pipeline` into every stage's
  autopilot picker, so dropping `plan` from the pipeline moves that one line everywhere;
  `execute` and `spec` moved for their own reasons (Steps 0–0.3 and Step 4.6). The autopilot
  advance block itself is untouched — the same bytes move identically in `auto_safe` and `ask`,
  which is the signal that this is not an arm-differential defect. Attributed in
  `work-docs/BASELINE-DELTA-plan-stage-absorption.md`.

- **2026-09-20, `plan-stage-absorption` Phase 1** — `execute` moved in all four arms, identically
  in `auto_safe` and `ask`. `/hm:execute` gained `Step 0` / `0.1` / `0.2`: the removed `/hm:plan`
  stage's Step 5, 1.7 and 1.5 relocated, so execute now authors the PLAN document, writes the
  SPEC-need pair through `hm spec_need frontmatter-upsert`, and scopes the loop per-iter PLAN.
  Verified BEFORE re-capturing that `execute` is the ONLY moved command in every arm and that no
  command was added or removed in any arm. The autopilot advance block is untouched — this task
  is a third party to this guard's subject, which is the case the rule above says to re-capture
  and record. Attributed in `work-docs/BASELINE-DELTA-plan-stage-absorption.md`; the character
  and round-trip ratchets are handled there and in that PLAN's `surface_allowance`.

- **2026-09-13, release 0.56.0** — ALL FIFTEEN commands moved in all four arms, which looks
  alarming and is not: the only differing line per command is the frontmatter
  `harness_maker_version:` key. Verified before re-capturing — 15 lines across 15/15 commands,
  **zero** non-frontmatter occurrences of the new version string. A version bump moves every
  rendered artifact by construction, so this fixture will need a re-capture at every release
  until something keys it on content rather than bytes.
- **2026-09-13, `reviewer-lens-fanout-merge`** — `review` moved in all four arms. The four core
  reviewer lenses merged into one `code-reviewer` dispatch, so `review.md` renders four dispatches
  where it rendered seven. Unrelated to autonomy gating: the same bytes move identically in
  `auto_safe` and `ask`, which is the signal that this is not an arm-differential defect. Verified
  before re-capture that `review` is the ONLY moved command in every arm.
- **2026-09-16, `intent-world-model-objective-layer`** — `plan`, `review`, `wrapup` and `help`
  moved in all four arms, identically in `auto_safe` and `ask`: plan gained Step 0.5 (objective
  context), review gained Step 3.3 (objective drift, P2), wrapup gained 5.7 (two answer-gated
  questions), help gained the `intent-layer` skill row. Verified before re-capture that these
  four are the ONLY moved commands in every arm and that the command set did not drift; the
  autopilot advance block itself is untouched. Re-captured a second time the same day after the
  AC-017 judgment asked Step 3.3 to open each finding with the objective id — `review` alone moved.
  Re-captured a third time after `/hm:review`'s round-2 fix added the `[A-Z0-9-]+` id check to
  Step 3.3 (P1 security: frontmatter text reached the shell unchecked) — again `review` alone moved.
- **2026-09-16, `playbook-alignment`** — `wrapup` moved in all four arms, identically in
  `auto_safe` and `ask`: the 5.7 observe line names `--claim` for the `supersedes` relation
  (AC-007). Verified before re-capture that `wrapup` is the ONLY moved command in every arm.
- **2026-09-16, `objective-gap-proposal`** — `plan` moved in all four arms, identically in
  `auto_safe` and `ask`: Step 0.5 gained the "Draft an objective for this task?" consent
  question and a new Step 4.9 (the `objective new … --from-proposal --candidates 1` call after
  the interview). Verified before re-capture that `plan` is the ONLY moved command in every arm.
  Attributed in `work-docs/BASELINE-DELTA-objective-gap-proposal.md` §3.
- **2026-09-17, `outcome-measure`** — `wrapup` moved in all four arms, identically in
  `auto_safe` and `ask`: 5.7 gained the third answer-gated block (`outcome-measure` — "Measure
  outcomes now?", one `hm world outcome measure --all` call) and its heading now says three
  questions. Verified before re-capture that `wrapup` is the ONLY moved command in every arm.
  Attributed in `work-docs/BASELINE-DELTA-outcome-measure.md` §3.
- **2026-09-17, release 0.57.0** — ALL FIFTEEN commands moved in all four arms, the per-release
  case recorded at 0.56.0. Verified before re-capturing — 60 lines (15 commands × 4 arms), every
  one the frontmatter `harness_maker_version:` key, and each render with `0.57.0` substituted
  back to `0.56.0` hashes identically to the previous golden, so no content moved.
- **2026-09-17, release 0.57.1** — same per-release case: 60 lines, all the frontmatter
  `harness_maker_version:` key, and substituting `0.57.1` back to `0.57.0` reproduces every
  previous hash.
- **2026-09-18, `intent-layer-ops`** — `wrapup` moved in all four arms, identically in
  `auto_safe` and `ask`: 5.7 gained one sentence after the `outcome-measure` block that prints
  `[intent] withdrawal criterion met …` when the `gap` output reports `withdrawal.due` (zero new
  calls). Verified before re-capture that `wrapup` is the ONLY moved command in every arm.
  Attributed in `work-docs/BASELINE-DELTA-intent-layer-ops.md` §3.
- **2026-09-18, `assumption-entry-and-evidence-locator`** — `wrapup` moved in all four arms,
  identically in `auto_safe` and `ask`: 5.7's assumption block gained the "new — record an
  assumption" option (one `hm world assume add` call), the four-option cap with stale-first ids
  from `hm world gap --json`, and `[--locator <path:A-B>]` on the observe line. Verified before
  re-capture that `wrapup` is the ONLY moved command in every arm. Attributed in
  `work-docs/BASELINE-DELTA-assumption-entry-and-evidence-locator.md` §3.
- **2026-09-19, `mission-context-loop`** — `wrapup` and `help` moved in all four arms,
  identically in `auto_safe` and `ask`: wrapup 5.1 gained the 5.1.0 fact-safe
  search-before-write blockquote (one `hm memory_retrieve` call; never reuse a `[wiki:fact]`
  slug) and its slug bullet now names the reused non-fact slug; help gained the
  `project-knowledge` skill row. Verified before re-capture that these two are the ONLY moved
  commands in every arm and the command set did not drift. Attributed in
  `work-docs/BASELINE-DELTA-mission-context-loop.md` §3. Re-captured again after `/hm:review`'s
  Codex P1 fix added the exact-slug Grep check to 5.1.0, and twice more for its base-path note
  (re-review P1; then `/hm:verify` removed a `<WT>` token that leaked into the worktree-OFF
  render) — `wrapup` the ONLY moved command each time.
- **2026-09-19, `ai-native-sdlc-vs-intent-world`** — `spec`, `execute` and `wrapup` moved in all
  four arms and `loop` in the three worktree-on arms (its finalize block does not render with
  isolation off), identically in `auto_safe` and `ask`: spec became judgment-gated (the shared
  partial renders its classify-then-boundary branch) and gained the approve/exempt stamps and the
  irreversible-decision list; execute gained the escalation rule; wrapup gained the
  `approval-status` check before the land call; loop gained the `[finalize] hold:` HALT note.
  Verified before re-capture that these four are the ONLY moved commands in every arm and the
  command set did not drift. Attributed in
  `work-docs/BASELINE-DELTA-ai-native-sdlc-vs-intent-world.md` §3.
- **2026-09-20, release 0.58.0** — same per-release case: 60 lines, all the frontmatter
  `harness_maker_version:` key, and substituting `0.58.0` back to `0.57.1` reproduces every
  previous hash.
- **2026-09-20, withdrawal-criterion-window Phase 3** — the withdrawal notice in wrapup Step 5.7
  now quotes `quiet_wrapups` and `last_signal_at`, and no longer asserts "no observed objective":
  the replacement criterion never evaluates how many objectives carry `observed:`, so the old
  sentence told the operator the criterion checked something it did not. Verified before
  re-capture that `wrapup` is the ONLY moved command in EVERY one of the four arms, and that no
  command was added or removed — not only in the arm this test stops at. The replacement notice
  is a net 10 characters SHORTER, so no `surface_allowance` was declared; the absent-signal case
  rides in the placeholder (`<last_signal_at or filled_at>`) rather than a second sentence.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pytest

from harness_maker.models import (
    AutonomyConfig,
    InterviewAnswers,
    Preset,
    ProjectProfile,
    Target,
)
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize

from ._instruction_baseline import AXES, _render_atomic
from .conftest import pin_install_ref
from .test_command_size_budget import _render

_REPO_ROOT = Path(__file__).resolve().parents[2]
_GOLDEN = Path(__file__).resolve().parent / "autopilot_gate_golden.json"

#: Built by concatenation so the widened scan below does not flag this file for holding the needle.
_DEAD_GUARD = "autopilot" + "_advance_enabled"

#: Trees the dead-name scan walks. `work-docs/`, `specs/` and `.claude/` are excluded by NOT being
#: listed — a mention there is a record of the removal, not a live reference. An earlier draft also
#: carried a `_DEAD_GUARD_EXEMPT` tuple naming those three, which could never match because the
#: loop only ever walked these two trees: an inert filter, inside the very test that exists to
#: remove an inert flag. Widening this tuple means re-deciding the exclusions here, deliberately.
_DEAD_GUARD_TREES = ("src", "tests")
_BOUNDARY_CALL = "autopilot_caps boundary"
_ADVANCE_BLOCK = re.compile(
    r"<!-- @hm:autopilot-advance -->.*?<!-- @hm:/autopilot-advance -->",
    re.S,
)
_PICKER_BLOCK = re.compile(
    r"<!-- @hm:autopilot-picker -->.*?<!-- @hm:/autopilot-picker -->",
    re.S,
)


_CONTENT_HASH = re.compile(r"^content_hash: .*$", re.M)


def _normalise(text: str) -> str:
    """Blank the body-derived frontmatter hash, then collapse runs of blank lines.

    `content_hash` is computed FROM the body, so it necessarily differs between two arms whose
    bodies differ — comparing it adds nothing once the bodies are compared, and leaving it in made
    this assertion unsatisfiable by construction. Collapsing `\\n{3,}` is required for a different
    reason: removing a marker pair that occupies whole lines necessarily leaves a 3-newline run.
    Neither normalisation weakens the byte-identity golden, which pins the non-gated arms by
    un-normalised sha256 over the whole file, hash included.
    """
    return re.sub(r"\n{3,}", "\n\n", _CONTENT_HASH.sub("content_hash: <normalised>", text))


def _render_at_level(level: str, tmp: Path) -> dict[str, str]:
    """Render the commands with only `autonomy.level` varied — the AC's differential."""
    with pytest.MonkeyPatch.context() as mp:
        pin_install_ref(mp)
        render(
            synthesize(
                ProjectProfile(),
                InterviewAnswers(
                    preset=Preset.PRODUCTION,
                    targets=[Target.CLAUDE_CODE],
                    autonomy=AutonomyConfig(level=level),  # type: ignore[arg-type]
                ),
            ),
            tmp,
            freeze_time=DEFAULT_FREEZE_TIME,
        )
    root = tmp / "commands" / "hm"
    return {p.stem: p.read_text(encoding="utf-8") for p in sorted(root.glob("*.md"))}


@pytest.fixture(scope="module")
def gated(tmp_path_factory: pytest.TempPathFactory) -> dict[str, str]:
    return _render_at_level("gated", tmp_path_factory.mktemp("gated"))


@pytest.fixture(scope="module")
def armed(tmp_path_factory: pytest.TempPathFactory) -> dict[str, str]:
    return _render_at_level("auto_safe", tmp_path_factory.mktemp("armed"))


def test_ac_005_a_gated_harness_renders_no_boundary_invocation(gated: dict[str, str]) -> None:
    """The whole point: a gated harness must not carry a call whose only output is `kill_switch`."""
    carriers = {name: text.count(_BOUNDARY_CALL) for name, text in gated.items()}

    assert sum(carriers.values()) == 0, {k: v for k, v in carriers.items() if v}


def test_ac_005_the_gated_delta_is_exactly_the_advance_blocks(
    gated: dict[str, str], armed: dict[str, str]
) -> None:
    """AC-005's MIDDLE conjunct — a zero-boundary count alone does not catch over-swallowing.

    A level gate that also removed a heading, the sibling `gate-blocked` line, or adjacent banner
    prose would satisfy the count assertion just as well. So the armed render with its advance
    blocks stripped must equal the gated render, byte for byte, per command.
    """
    assert set(gated) == set(armed), "the command set itself moved"

    # Scoped to the commands that CARRY an advance block, derived rather than hand-listed. This
    # conjunct asks what the ADVANCE gate removed, and a command with no advance block has nothing
    # for it to remove. The scoping is not a convenience: `autonomy.level` gates a THIRD region
    # that predates this change and carries no `@hm:` marker — `health.md`'s "Autopilot
    # auto-advance smoke check" section — so a whole-command comparison would charge this phase for
    # correct, pre-existing behaviour. Non-carriers are covered by the byte golden on the non-gated
    # arms, which is where a regression in them would show up.
    carriers = sorted(name for name, text in armed.items() if _ADVANCE_BLOCK.search(text))
    assert carriers, "no armed command carries an advance block — this assertion would be vacuous"

    for name in carriers:
        armed_text = armed[name]
        # BOTH marked blocks. `autonomy.level` gates two, not one: `step_manifest.md.j2:33` already
        # gates the PICKER on `level != "gated"`, and `atomic_command.md.j2` includes that partial
        # into every command. Stripping only the advance block made this test fail a CORRECT
        # implementation, and the only way to green it would have been deleting the picker's gate —
        # which ADR-006 and SPEC Open Question 4 forbid. The sibling test below asserts that same
        # asymmetry, so the file contradicted itself.
        stripped = _PICKER_BLOCK.sub("", _ADVANCE_BLOCK.sub("", armed_text))
        # Collapsing 3+ newlines is required, not a loosening: removing a marker pair that occupies
        # whole lines necessarily leaves a 3-newline run. It does not weaken what the golden
        # catches — that pins the non-gated arms by un-normalised sha256. The accepted residual is
        # that blank-line drift in the GATED arm is unpinned, which no AC binds.
        expected = _normalise(stripped)
        actual = _normalise(gated[name])
        assert actual == expected, (
            f"{name}: the gated render is not the armed render minus its two level-gated blocks — "
            "the level gate removed or added something else"
        )


def test_ac_005_the_advance_block_is_present_in_the_armed_arm(armed: dict[str, str]) -> None:
    """Control for the test above: strip-and-compare is vacuous if nothing was there to strip.

    Without this, a render that emitted no advance block in EITHER arm would pass the delta
    assertion trivially, and the 24.9 kB this AC exists to reclaim would be reported as reclaimed
    in a harness that never had it.
    """
    carriers = [name for name, text in armed.items() if _ADVANCE_BLOCK.search(text)]

    assert carriers, "no armed command carries an advance block — the delta test proves nothing"
    assert all(_BOUNDARY_CALL in armed[name] for name in carriers)


def test_ac_005_the_dead_guard_name_appears_nowhere() -> None:
    """Zero producers, so the name is not a flag — it is a comment that looks like one.

    **`src/` AND `tests/`.** An earlier draft scanned `src/` only, justified as "where a producer
    would have to live" — refuted by a counterexample already in the repo:
    `tests/unit/test_autopilot_template_render.py` declares an `advance_enabled` kwarg and writes
    `ctx["autopilot_advance_enabled"]` from it, and nothing in the repo passes that kwarg. So a
    Phase C that edits the template and leaves the injector would have reported AC-005's third
    conjunct green with the dead name still live, which is the very "a knob that looks live but
    cannot act" defect the AC removes. Nothing else catches it either: the literal-condition
    assertion self-reports on the template edit, but an uncalled kwarg's survival is silent.

    `work-docs/`, `specs/` and `.claude/` are exempt — a mention there is a record of the removal.
    """
    hits: list[str] = []
    for tree in _DEAD_GUARD_TREES:
        for path in (_REPO_ROOT / tree).rglob("*"):
            if not path.is_file() or path == Path(__file__).resolve():
                continue
            rel = path.relative_to(_REPO_ROOT)
            # `__pycache__` holds the compiled form of the very files being scanned, so a `.pyc`
            # hit is an echo of a source hit rather than an independent reference — and it lingers
            # after the source is fixed, which would leave this test red for a stale artifact.
            if "__pycache__" in rel.parts:
                continue
            if _DEAD_GUARD in path.read_text(encoding="utf-8", errors="replace"):
                hits.append(str(rel))

    assert hits == [], f"{_DEAD_GUARD} still referenced in: {sorted(hits)}"


def test_ac_005_the_non_gated_arms_are_byte_identical_to_the_pre_change_golden(
    tmp_path: Path,
) -> None:
    """The non-gated arms must not move by one byte — including whitespace.

    The render env is `trim_blocks=False, lstrip_blocks=False`, so restructuring the condition into
    nested `{% if %}` tags ADDS output newlines, and nothing else in the repo would catch that: the
    character ratchet's 2% band absorbs a few chars, `instruction_baseline` compares stripped
    heading and `!`-line SETS, and the aggregate baseline has headroom.
    `[wiki:convention] jinja-comment-whitespace-moves-renders` is the recorded hazard.
    """
    golden = json.loads(_GOLDEN.read_text(encoding="utf-8"))["arms"]
    live: dict[str, dict[str, str]] = {}
    for strictness in AXES:
        live[f"auto_safe@{strictness}"] = {
            k: hashlib.sha256(v.encode()).hexdigest()
            for k, v in sorted(_render_atomic(strictness).items())
        }
    live["ask@flag_on"] = {
        k: hashlib.sha256(v.encode()).hexdigest()
        for k, v in sorted(_render(feature_branch_workflow=True, tmp=tmp_path / "on").items())
    }
    live["ask@flag_off"] = {
        k: hashlib.sha256(v.encode()).hexdigest()
        for k, v in sorted(_render(feature_branch_workflow=False, tmp=tmp_path / "off").items())
    }

    assert set(live) == set(golden), "the captured arm set drifted"
    for arm in sorted(golden):
        # Per-arm COMMAND sets too, not just the arm names: iterating golden's keys alone would
        # not see a newly ADDED command file. Impossible from a single-condition edit, which is
        # why it was recorded as a note rather than a gate — and cheap enough to close anyway.
        assert set(live[arm]) == set(golden[arm]), (
            f"{arm}: command set moved — "
            f"added {sorted(set(live[arm]) - set(golden[arm]))}, "
            f"removed {sorted(set(golden[arm]) - set(live[arm]))}"
        )
        moved = {k for k, sha in golden[arm].items() if live[arm].get(k) != sha}
        assert not moved, (
            f"{arm}: rendered bytes moved for {sorted(moved)}. If THIS guard's subject (the "
            "autopilot gate) moved them, regenerating would freeze whatever the edit produced, "
            "which is the failure it exists to catch. If a LATER, unrelated task moved them, "
            "re-capture and append a dated entry to the module docstring naming the task and the "
            "commands — see the re-capture list there."
        )


def test_ac_005_the_picker_block_is_untouched(gated: dict[str, str], armed: dict[str, str]) -> None:
    """ADR-006 leaves the picker alone: it is already correctly gated on `level != "gated"`.

    So the gated arm renders no picker and the armed arm does — and the armed picker's bytes are
    covered by the golden above. Asserting it here is what stops a `{% if %}` restructure of the
    adjacent block from taking the picker with it.
    """
    assert not any(_PICKER_BLOCK.search(text) for text in gated.values())

    armed_pickers = [text for text in armed.values() if _PICKER_BLOCK.search(text)]
    assert armed_pickers, "the armed arm lost its picker — the restructure reached too far"


def test_strictness_is_still_the_only_instruction_baseline_axis() -> None:
    """Records WHY the gated guard lives in this file, and fails if that reason stops holding.

    If `AXES` ever grows a second axis (an `autonomy.level` arm, say), the migration this phase
    deliberately avoided has happened anyway — and then this file's dedicated guard is redundant
    rather than necessary. A comment would rot; this notices. Pinned to the exact arms so a
    third member cannot slip in as "still strings".
    """
    assert AXES == ("warn", "block"), AXES
