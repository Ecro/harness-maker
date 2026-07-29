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

from harness_maker.interview import answers_from_harness_yaml
from harness_maker.models import AtomicStage, InterviewAnswers, Preset, ProjectProfile, Target
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize

from .conftest import pin_install_ref

# ── the ratchet table ──────────────────────────────────────────────────────────
# `pre_change` is an observation of the committed render at 8addbee0, taken before
# this phase edited anything. `measured` is the post-change size. Ceiling =
# measured * 1.02, floor = measured * 0.80 (ADR-014), except exec-rev-wrap-ver whose
# ceiling is the hand-set 119,000.
_RATCHET: dict[str, tuple[int, int]] = {
    # name: (pre_change_chars, measured_post_change_chars)
    "exec-rev-wrap-ver": (103057, 98620),
    "exec-rev-wrap": (86367, 83689),
    "plan-exec-rev": (88353, 85676),
    "res-spec-plan": (84639, 81963),
    "exec-rev": (50596, 49678),
}

# ADR-014's hand-set ceiling is measured against a DIFFERENT render: this repo's own
# `.claude/harness.yaml` (second opinion + full reviewer set enabled). The fixture render
# above is ~16% smaller, so applying this figure to it would assert nothing. Keeping the
# two apart is what makes each bind — see `test_the_repo_render_is_under_the_adr014_ceiling`.
#
# Re-based 2026-07-29 from 119,000 (PLAN-wrapup-context-carry Phase 3). Derivation below.
_ADR014_CEILING = 122_000

_WORKFLOWS: dict[str, tuple[str, ...]] = {
    "exec-rev-wrap-ver": ("execute", "review", "wrapup", "verify"),
    "exec-rev-wrap": ("execute", "review", "wrapup"),
    "plan-exec-rev": ("plan", "execute", "review"),
    "res-spec-plan": ("research", "spec", "plan"),
    "exec-rev": ("execute", "review"),
}

# ── AC-007's named exemption ───────────────────────────────────────────────────
# The ONLY content `fuse()` intentionally drops. Kept as an equality target so a
# second omission cannot hide behind it.
_EXEMPT_HEADING = "## Auto-advance check (autopilot — Claude Code only)"
_EXEMPT_EXEC = re.compile(r"harness_maker\.autopilot_caps ")

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
                    fused_workflows={
                        name: [AtomicStage(s) for s in stages]
                        for name, stages in _WORKFLOWS.items()
                    },
                    default_workflow="exec-rev-wrap-ver",
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
    assert set(_RATCHET) <= set(flag_on), sorted(set(_RATCHET) - set(flag_on))
    assert set(_RATCHET) <= set(flag_off), sorted(set(_RATCHET) - set(flag_off))
    assert all(len(v) > 10_000 for k, v in flag_on.items() if k in _RATCHET)


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
    assert "$HOME/harness-maker" in flag_on["exec-rev-wrap-ver"]


# ── AC-005 ─────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("name", sorted(_RATCHET))
def test_rendered_commands_within_budget(flag_on: dict[str, str], name: str) -> None:
    """AC-005 — ceiling stops regrowth, floor stops the render being gutted to meet it."""
    pre, measured = _RATCHET[name]
    ceiling = int(measured * 1.02)
    floor = int(measured * 0.80)
    size = len(flag_on[name])
    assert floor <= size <= ceiling, f"{name}: {size} outside [{floor}, {ceiling}]"
    assert size < pre, f"{name}: {size} did not shrink from the pre-change {pre}"


def test_the_repo_render_is_under_the_adr014_ceiling(tmp_path: Path) -> None:
    """AC-005's second conjunct, against the artifact ADR-014 actually measured.

    Rendered from this repo's committed `.claude/harness.yaml` — the config behind the
    121,782 baseline. Fail-closed if that file is missing: an absent config means the
    measurement cannot be made, which is not the same as passing.

    **Re-based 2026-07-29, and the reason matters more than the number.** The previous
    constant was 119,000, derived by ADR-014 as `(121,782 − 5,706) × 1.02` — a
    pre-pruning render size minus what `PLAN-token-economy-step-pruning` removed, plus 2%
    headroom. By 2026-07-28 that left **53 characters** of margin, and the prior version
    of this docstring already flagged the constant as stale and asked for a re-derivation.

    What forced it: `PLAN-wrapup-context-carry` AC-004 and AC-009 require two new `!`
    lines in the wrapup stage (`--slug` on the brief, and the self-skip ledger row) that
    total ~190 rendered characters. **No implementation of that SPEC fits under 119,000** —
    not by trimming prose, because the mandatory command surface alone overruns the margin.
    A ceiling that no correct implementation can satisfy stops being a budget and becomes
    a prompt to weaken the test, so it was re-based rather than worked around.

    Both of ADR-014's anchors (121,782 pre-pruning, 5,706 saved) are HISTORICAL — pruning
    was a one-time prose reduction, not a render flag, so neither is re-measurable today.
    What survives is the rule's shape: `post-pruning size × 1.02`. Measured here on
    2026-07-29 the render is 119,765, giving 122,160; the constant is rounded DOWN to
    122,000, which is the conservative direction (ADR-014 rounded its 118,398 *up*).

    The margin is now ~2,200 characters. Treat that as the budget it is: growth beyond it
    should be paid for by pruning, not by moving this number again.
    """
    cfg = Path(__file__).resolve().parents[2] / ".claude" / "harness.yaml"
    assert cfg.exists(), f"cannot measure the ADR-014 ceiling: {cfg} is missing"
    with pytest.MonkeyPatch.context() as mp:
        pin_install_ref(mp)
        render(
            synthesize(ProjectProfile(), answers_from_harness_yaml(cfg)),
            tmp_path,
            freeze_time=DEFAULT_FREEZE_TIME,
        )
    size = len((tmp_path / "commands" / "hm" / "exec-rev-wrap-ver.md").read_text("utf-8"))
    assert size <= _ADR014_CEILING, f"{size} exceeds ADR-014's {_ADR014_CEILING}"


def test_an_inflated_render_fails_the_ceiling(flag_on: dict[str, str]) -> None:
    """Negative control — the budget rejects growth rather than merely observing it."""
    _, measured = _RATCHET["exec-rev-wrap-ver"]
    inflated = flag_on["exec-rev-wrap-ver"] + "x" * 10_000
    assert len(inflated) > int(measured * 1.02)


def test_a_gutted_render_fails_the_floor(flag_on: dict[str, str]) -> None:
    """Negative control — ADR-017's failure mode: meeting the ceiling by deleting content."""
    _, measured = _RATCHET["exec-rev-wrap-ver"]
    gutted = flag_on["exec-rev-wrap-ver"][: int(measured * 0.5)]
    assert len(gutted) < int(measured * 0.80)


# ── AC-006 ─────────────────────────────────────────────────────────────────────


def test_shared_blocks_appear_once(flag_on: dict[str, str]) -> None:
    """AC-006 flag-on arm — shared prose once, all four `--stage` values present."""
    text = flag_on["exec-rev-wrap-ver"]
    assert shared_prose_fingerprints(text, "worktree_preflight") == 1
    assert shared_prose_fingerprints(text, "gate0_receipt") == 1
    assert shared_prose_fingerprints(text, "stage_end_banner") == 1
    for marker in _PREFLIGHT_TAIL_MARKERS:
        assert text.count(marker) == 1, marker
    assert stage_arg_values(text, "iter_receipts write") == {
        "execute",
        "review",
        "wrapup",
        "verify",
    }
    assert stage_arg_values(text, "task-preflight") == {
        "hm:execute",
        "hm:review",
        "hm:wrapup",
        "hm:verify",
    }


def test_shared_blocks_appear_once_in_every_fused_command(flag_on: dict[str, str]) -> None:
    """The hoist applies to all five fused commands, not only the largest (PLAN H3)."""
    for name, stages in _WORKFLOWS.items():
        text = flag_on[name]
        assert shared_prose_fingerprints(text, "worktree_preflight") == 1, name
        assert shared_prose_fingerprints(text, "gate0_receipt") == 1, name
        assert shared_prose_fingerprints(text, "stage_end_banner") == 1, name
        assert stage_arg_values(text, "task-preflight") == {f"hm:{s}" for s in stages}, name


def test_the_flag_off_render_has_no_preflight_but_keeps_every_gate0_stage(
    flag_off: dict[str, str],
) -> None:
    """AC-006 flag-off arm (ADR-006(d)) — the hoist carries the flag gate into fuse()."""
    text = flag_off["exec-rev-wrap-ver"]
    assert shared_prose_fingerprints(text, "worktree_preflight") == 0
    assert stage_arg_values(text, "task-preflight") == set()
    assert stage_arg_values(text, "iter_receipts write") == {
        "execute",
        "review",
        "wrapup",
        "verify",
    }
    assert shared_prose_fingerprints(text, "gate0_receipt") == 1


def test_the_fingerprint_rejects_a_heading_with_an_empty_body(flag_on: dict[str, str]) -> None:
    """A hoist that leaves the heading and drops the prose must not fingerprint as 1."""
    text = flag_on["exec-rev-wrap-ver"]
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


@pytest.mark.parametrize("workflow", sorted(_WORKFLOWS))
def test_fused_loses_no_instruction(flag_on: dict[str, str], workflow: str) -> None:
    """AC-007 — the atomic-minus-fused differential is EXACTLY the autopilot block."""
    fused = flag_on[workflow]
    fh, fe = headings(fused), executable_lines(fused)
    for stage in _WORKFLOWS[workflow]:
        atomic = flag_on[stage]
        missing_h = headings(atomic) - fh
        missing_e = executable_lines(atomic) - fe
        assert missing_h == {_EXEMPT_HEADING}, f"{workflow}/{stage}: {sorted(missing_h)}"
        assert all(_EXEMPT_EXEC.search(x) for x in missing_e), (
            f"{workflow}/{stage}: {sorted(missing_e)}"
        )
        assert missing_e, f"{workflow}/{stage}: exemption set went empty — control broke"


def test_the_no_loss_check_would_notice_a_dropped_instruction(flag_on: dict[str, str]) -> None:
    """Negative control — remove one heading from the fused text and the equality breaks."""
    atomic = flag_on["execute"]
    victim = next(h for h in sorted(headings(atomic)) if h != _EXEMPT_HEADING)
    mutilated = flag_on["exec-rev-wrap-ver"].replace(victim + "\n", "")
    assert headings(atomic) - headings(mutilated) != {_EXEMPT_HEADING}
