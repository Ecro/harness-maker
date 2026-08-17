"""Falsifiability probe for Phase 3's render assertions — run against the GREEN corpus.

ADR-011 suspended Phase A.5 for Phase 3, because A.5 is a RED gate and its premise does not hold
for a prose deliverable: absence is ~6% of two 60KB documents, so the RED corpus already contains
the contract's whole vocabulary. This probe is the compensating control the ADR names — with the
templates edited, each mutant DELETES or CORRUPTS a real piece of the contract and requires the
assertion that pins it to go RED.

Three mutant classes, and all three are load-bearing:

* **contract** — remove the thing; the assertion must go **RED**. Catches an inert assertion.
* **everything-else** (`*-MUST-STAY-GREEN` on unrelated prose) — the assertion must stay
  **GREEN**. Catches an assertion that is red for the wrong reason, which the contract class
  alone reports as healthy.
* **correct-implementation** (`M2b`, `M15`, `M16b`) — apply a different but equally valid
  wording, ordering or placement; the assertion must stay **GREEN**. Catches an assertion that
  rejects a faithful implementation and so drives the implementer toward a wrong edit. This class
  is the one that needs the GREEN corpus, and it is why the probe could not be complete before
  ADR-011.

A probe is only as strong as its mutants. Five were caught being weaker than their claim, each
noted where it sits, and the last three came from review rather than from writing the file:

* `M14` was labelled `-moved-after-consumers` while performing a DELETION, so the ordering clause
  it claimed to probe was never reached. Split into `M14` (existence) and `M14b` (ordering).
* `test_the_pre_repair_block_avoids_the_two_collided_words` had **no mutant of any class** —
  a negative invariant, which is the kind that cannot fail by accident and therefore needs one
  most. Now `M16` / `M16b`.
* the correct-implementation class had exactly ONE member, and not on either assertion with a
  recorded history of going RED under a faithful implementation. `M15` covers the declaration;
  the close enumeration's placement sensitivity was removed at the source instead, by scoping
  every declaration assertion through `_declaration_block` rather than a character window.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path

WT = Path(__file__).resolve().parents[1]
EXE = WT / "src/harness_maker/templates/stages/execute.md.j2"
REV = WT / "src/harness_maker/templates/stages/review.md.j2"
TEST = "tests/render/test_render_phase3_surface.py"


def _drop(needle: str, replacement: str = "") -> Callable[[str], str]:
    def mutate(text: str) -> str:
        assert needle in text, f"mutant did not apply: {needle[:60]!r}"
        return text.replace(needle, replacement, 1)

    return mutate


def _drop_all(needle: str, replacement: str = "") -> Callable[[str], str]:
    """Every occurrence, not the first.

    M12/M13 were the fourth weak mutant this probe produced: they removed the PROSE that
    introduces the cache read and left the command block, so the assertion — which looks for the
    command — stayed green and the probe reported the assertion inert. Remove the thing the
    assertion names, not the sentence next to it.
    """

    def mutate(text: str) -> str:
        assert needle in text, f"mutant did not apply: {needle[:60]!r}"
        return text.replace(needle, replacement)

    return mutate


def _collapse_lens_words(text: str) -> str:
    """The single dispatch keeps its shape but loses every lens question."""
    start = text.index('{{ dsp.dispatch(is_codex, "test-reviewer"')
    end = text.index("\n", start)
    return (
        text[:start]
        + '{{ dsp.dispatch(is_codex, "test-reviewer", "A.5: {slug}", "<brief>") }}'
        + text[end:]
    )


def _move_closes_to_approve_side(text: str) -> str:
    """A close on the Grade Gate's APPROVE arm — the bypass ADR-003 removes.

    The planted close carries `--slug`/`--run-id` deliberately. A short-form close would be
    caught by the well-formedness assertion instead, and the mutant would go RED for a reason
    that has nothing to do with the approve-arm property it claims to probe.
    """
    anchor = "     ELSE:\n       STOP. Proceed to wrapup."
    assert anchor in text, "mutant did not apply: approve-arm ELSE"
    return text.replace(
        anchor,
        anchor + "\n       Close the run: `hm review_run close --slug <slug> "
        "--run-id <run-id> --outcome APPROVED`.",
        1,
    )


def _plant_cache_read(text: str) -> str:
    """ADR-008's consumer added back with no producer — the thing review had removed."""
    anchor = (
        "**Verify build**"
        if "**Verify build**" in text
        else "**Follow the `targeted-test-selection` skill"
    )
    assert anchor in text, "mutant did not apply: no anchor for the cache read"
    return text.replace(
        anchor,
        "First run `hm observability.verification_cache check --root . --mode relevant`; "
        "exit `1` is a miss. " + anchor,
        1,
    )


def _move_id_source_after_consumers(text: str) -> str:
    """The sentence survives verbatim but lands BELOW the first `<run-id>` consumer.

    M14 deletes the sentence, so it trips the assertion's existence clause and never reaches the
    ordering clause — and the ordering clause is the point: an existence check over a 60KB body is
    satisfied by a sentence 400 lines away from the value it explains.
    """
    sentence = "**Read it from `open`, never mint one:**"
    assert sentence in text, "mutant did not apply: id-source sentence"
    stripped = text.replace(sentence, "", 1)
    first_consumer = stripped.index("<run-id>")
    line_end = stripped.index("\n", first_consumer)
    return stripped[:line_end] + "\n\n" + sentence + stripped[line_end:]


def _reorder_declaration_items(text: str) -> str:
    """A correct-implementation mutant: the three declared items in a different order. All three
    are still declared, so the assertion must stay GREEN — an assertion that pins ORDER when the
    contract is PRESENCE dictates layout and drives a wrong edit."""
    hypothesis = "1. **The root-cause hypothesis for this repair.**"
    scope = "2. **The scope this repair will touch**"
    assert hypothesis in text, "mutant did not apply: hypothesis item"
    assert scope in text, "mutant did not apply: scope item"
    return (
        text.replace(hypothesis, "1. **TMP-SWAP**", 1)
        .replace(scope, "2. **The root-cause hypothesis for this repair.**", 1)
        .replace("1. **TMP-SWAP**", "1. **The scope this repair will touch**", 1)
    )


def _reorder_id_source(text: str) -> str:
    """A correct-implementation mutant: the id-source sentence reworded but still ahead of every
    consumer. The assertion must stay GREEN — an ordering clause that only accepts one phrasing
    is an assertion that dictates wording rather than the property."""
    return text.replace(
        "**Read it from `open`, never mint one:**",
        "**Take the id from `review_run open` — read it from `open`, never mint one:**",
        1,
    )


#: (label, file, mutate, test node, why)
MUTANTS: list[tuple[str, Path, Callable[[str], str], str, str]] = [
    (
        "M1-lens-words-dropped",
        EXE,
        _collapse_lens_words,
        "test_the_single_a5_dispatch_still_asks_all_three_lens_questions",
        "the single dispatch keeps its shape but carries no lens question",
    ),
    (
        "M1b-prose-only-MUST-STAY-GREEN",
        EXE,
        _drop(
            "| `discrimination` | Would this assertion also pass against a plausibly WRONG"
            " implementation? |\n",
        ),
        "test_the_single_a5_dispatch_still_asks_all_three_lens_questions",
        "inverted — the lens TABLE row goes, the dispatch keeps the question; GREEN is correct",
    ),
    (
        "M2-close-on-approve-side",
        REV,
        _move_closes_to_approve_side,
        "test_review_enumerates_every_terminal_branch_that_must_close",
        "a close on the APPROVE arm, which C1-C3 still hold the id through",
    ),
    (
        "M2b-reworded-id-source-MUST-STAY-GREEN",
        REV,
        _reorder_id_source,
        "test_review_reads_the_run_id_from_open_at_every_consumer",
        "inverted — a different valid phrasing, still ahead of every consumer; GREEN is correct",
    ),
    (
        "M3-no-close-on-no-progress",
        REV,
        _drop(
            " No-progress is stage-terminal, so close the\n"
            "   run: `hm review_run close --slug <slug> --run-id <run-id> "
            "--outcome CHANGES_REQUESTED`,"
        ),
        "test_review_enumerates_every_terminal_branch_that_must_close",
        "the no-progress invariant loses its close — the branch both prior reviews missed",
    ),
    (
        "M4-open-twice",
        REV,
        _drop(
            "### Step 1 — Reviewer set selection",
            "Run `hm review_run open --slug <slug>` again here.\n\n"
            "### Step 1 — Reviewer set selection",
        ),
        "test_review_opens_a_run_once",
        "a second open mints a second id and splits the lens-results tree",
    ),
    (
        "M5-full-mode-names-a-config-shape",
        EXE,
        _drop(
            "Packaging and CI configuration now\n> select bounded suites instead.",
            "`pyproject.toml` and `uv.lock` still force it.",
        ),
        "test_phase_d_no_longer_names_the_config_shapes_as_full_mode_triggers",
        "the full-mode paragraph names a config shape again",
    ),
    (
        "M6-mark-pass-added-execute",
        EXE,
        _drop(
            "**Follow the `targeted-test-selection` skill",
            "Then run `hm observability.verification_cache mark-pass --root . --mode relevant "
            "--checks lint,format,mypy,pytest`.\n\n"
            "**Follow the `targeted-test-selection` skill",
        ),
        "test_the_stage_does_not_touch_the_verification_cache",
        "the producer half added back — it would poison `verify`/`wrapup`",
    ),
    (
        "M6b-mark-pass-added-review",
        REV,
        _drop(
            "**Verify build**",
            "**Verify build** — first `hm observability.verification_cache mark-pass --root . "
            "--mode relevant --checks lint,format,mypy,pytest`.",
        ),
        "test_the_stage_does_not_touch_the_verification_cache",
        "the review-stage parameter M6 does not cover",
    ),
    (
        "M7-declaration-dereferences",
        EXE,
        _drop(
            "3. **The non-goals** — what you will deliberately NOT touch",
            "3. **The non-goals** — re-confirm the SPEC's Non-Goals for what you will NOT touch",
        ),
        "test_the_pre_repair_block_declares_rather_than_dereferences",
        "an item phrased as a lookup into an artefact that may be absent",
    ),
    (
        "M8-declaration-loses-non-goals",
        EXE,
        _drop("3. **The non-goals** — what you will deliberately NOT touch"),
        "test_the_pre_repair_block_declares_all_three_items",
        "the scope brake dropped from the declaration",
    ),
    (
        "M9-phase-d-loses-the-skill-pointer",
        EXE,
        _drop("**Follow the `targeted-test-selection` skill", "**Run the checks"),
        "test_phase_d_points_at_the_targeted_test_selection_skill",
        "Phase D stops naming the skill that owns how to run its checks",
    ),
    (
        "M10-two-dispatches",
        EXE,
        _drop(
            '{{ dsp.dispatch(is_codex, "test-reviewer", "A.5: {slug}"',
            '{{ dsp.dispatch(is_codex, "test-reviewer", "A.5 extra: {slug}", "<brief>") }}\n'
            '{{ dsp.dispatch(is_codex, "test-reviewer", "A.5: {slug}"',
        ),
        "test_phase_a5_dispatches_exactly_one_test_reviewer",
        "the fan-out restored",
    ),
    (
        "M11-minting-instruction-restored",
        REV,
        _drop(
            "**`<run-id>` is the id Step 0's `open` printed**",
            "**`<run-id>` must be a real value you choose.** Use a fresh UTC stamp",
        ),
        "test_review_no_longer_tells_the_model_to_mint_a_run_id",
        "the minting instruction comes back",
    ),
    (
        "M12-cache-read-planted-execute",
        EXE,
        _plant_cache_read,
        "test_the_stage_does_not_touch_the_verification_cache",
        "the producer-less consumer put back — it cannot hit, so it is surface with no behaviour",
    ),
    (
        "M13-cache-read-planted-review",
        REV,
        _plant_cache_read,
        "test_the_stage_does_not_touch_the_verification_cache",
        "the review-stage parameter M12 does not cover",
    ),
    (
        "M14-id-source-deleted",
        REV,
        _drop("**Read it from `open`, never mint one:**", "**Never mint one:**"),
        "test_review_reads_the_run_id_from_open_at_every_consumer",
        "the id-source sentence stops saying where the value comes from",
    ),
    (
        "M14b-id-source-moved-below-its-consumers",
        REV,
        _move_id_source_after_consumers,
        "test_review_reads_the_run_id_from_open_at_every_consumer",
        "the ORDERING clause, which M14 never reached — it failed at the existence clause first",
    ),
    (
        "M15-declaration-reordered-MUST-STAY-GREEN",
        EXE,
        _reorder_declaration_items,
        "test_the_pre_repair_block_declares_all_three_items",
        "inverted — all three still declared, different order; GREEN is correct",
    ),
    (
        "M16-collided-word-planted",
        EXE,
        _drop(
            "2. **The scope this repair will touch**",
            "2. **The scope this repair will touch**, and the invariant it must preserve",
        ),
        "test_the_pre_repair_block_avoids_the_two_collided_words",
        "`invariant` already denotes a metamorphic relation here — this assertion had NO mutant",
    ),
    (
        "M16b-declaration-prose-MUST-STAY-GREEN",
        EXE,
        _drop(
            "Nothing verifies afterwards that you respected what you declared: ",
            "Nothing checks afterwards that you respected what you declared: ",
        ),
        "test_the_pre_repair_block_avoids_the_two_collided_words",
        "inverted — unrelated rewording inside the same block; GREEN is correct",
    ),
]


def run(node: str) -> int:
    return subprocess.run(
        # No `-x`: it hides the later parameters of a parametrized node, which is how the
        # review-stage half of the cache assertion went unprobed for a whole round.
        ["uv", "run", "pytest", f"{TEST}::{node}", "-q", "--no-header"],
        cwd=WT,
        capture_output=True,
        text=True,
        timeout=600,
    ).returncode


def main() -> int:
    # Every node, unmutated, before anything is touched. Without this the probe cannot tell a
    # falsifiable assertion from a test module that does not run: pytest returns 1 for an
    # assertion failure but 2/3/4 for a collection error, an import error or a missing node id,
    # and `rc != 0` reads all of them as "RED (falsifiable)". That is not hypothetical — a
    # `SyntaxError` in the test module once made all 21 mutants report RED and the summary print
    # `failing: 0`, i.e. the probe certified maximum health while testing nothing.
    for node in sorted({node for _, _, _, node, _ in MUTANTS}):
        rc = run(node)
        if rc != 0:
            print(f"ABORT: {node} does not pass unmutated (rc={rc}) — the probe cannot certify")
            return 1

    # The probe mutates the real templates in place and restores them in a `finally`. That covers
    # an exception or a Ctrl-C; it does NOT cover SIGKILL or a machine crash, which would leave a
    # corrupted template in the working tree for the next `git add -A` to commit. Keep a copy
    # outside the tree and say where it is.
    backup = Path(tempfile.mkdtemp(prefix="hm-probe-backup-"))
    for src in (EXE, REV):
        (backup / src.name).write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    print(f"[probe] template backups: {backup}\n")

    bad: list[tuple[str, str]] = []
    for label, path, mutate, node, why in MUTANTS:
        original = path.read_text(encoding="utf-8")
        try:
            path.write_text(mutate(original), encoding="utf-8")
            rc = run(node)
        finally:
            path.write_text(original, encoding="utf-8")
        inverted = "MUST-STAY-GREEN" in label
        if rc not in (0, 1):
            # Anything other than pass/fail is a harness error. Counting it as RED is how a
            # broken probe reports success.
            ok, verdict = False, f"HARNESS ERROR (pytest rc={rc}) — not a falsifiable assertion"
        elif inverted:
            ok, verdict = rc == 0, "GREEN (right reason)" if rc == 0 else "RED — WRONG ANCHOR"
        else:
            ok, verdict = rc == 1, "RED (falsifiable)" if rc == 1 else "GREEN — INERT"
        if not ok:
            bad.append((label, why))
        print(f"{label:42} {verdict}", flush=True)
    print(f"\n--- probed: {len(MUTANTS)} | failing: {len(bad)} ---")
    for label, why in bad:
        print(f"  {label}: {why}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
