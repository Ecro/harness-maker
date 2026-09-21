"""AC-006 (SPEC-dev-mode-removal): warn renders the SPEC machinery and blocks nothing; block
renders the hook.

The oracle is DIFFERENTIAL (ADR-008). `tests/fixtures/strictness_reference/` holds this
repository's render at the pre-change commit for all four `preset x dev_mode` arms, captured
before any source edit so it cannot be tuned to agree with the new code:

* the new `warn` render may stop on nothing the old `task-driven` render did not stop on;
* the new `block` render must stop on everything the old `spec-driven` render stopped on.

A "stop line" is a line carrying STOP / HALT / BLOCK(ED|S) / FAIL / "do not proceed", with
digits normalised — the verify header says "6 checks" where it used to say "5", and a count is
not a stop condition. Measured on the fixture, the normalised spec-only stop lines are exactly
the five Check-6 lines in verify and the one SPEC-need line in execute, so this oracle binds
to the SPEC gates and nothing else.

The reference is written in the retired vocabulary, so it is TRANSLATED before comparison —
`spec-driven`→`block`, `task-driven`→`warn`, `dev_mode`/`dev-mode`→`strictness` — for the same
reason digits are normalised: without it a stop line whose only change is the renamed axis reads
as one condition lost at `block` and one gained at `warn`, and the oracle cannot tell a rename
from a deletion. Only those tokens move; every other character of the line must still match.

Presence is asserted separately (the checks must render at `warn`), because a subset check alone
is satisfied by deleting the checks outright.

Phase A.4 — justified passes (3 of 9 items in this file), all in
`test_ac_006_hook_guard_reads_strictness`:
  * `[prod-warn]` and `[side-absent]` stand aside today because no `dev_mode` key is present.
    They go RED if the new guard activates on the preset alone and ignores an explicit `warn`
    (prod-warn), or derives `block` for Side (side-absent). RED positive siblings forcing the
    strictness-reading guard into existence: `[side-block]` and `[prod-absent]`.
  * `[legacy-spec-driven]` is active today through `dev_mode`. It goes RED if the hook stops
    reading through the migrating loader and sees only the raw `spec.strictness`. RED positive
    sibling: `[side-block]`, which forces the guard to read the new key.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from harness_maker.models import Preset, ProjectProfile, Target
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.strictness import Strictness
from harness_maker.synthesize import synthesize

from ..structural.conftest import pin_install_ref

REF = Path(__file__).resolve().parents[1] / "fixtures" / "strictness_reference"
STAGES = ("verify", "execute", "review", "spec", "wrapup")
STOP = re.compile(r"\bSTOP\b|\bHALT\b|\bBLOCK(?:ED|S)?\b|\b[Dd]o (?:NOT|not) proceed\b|\bFAIL\b")


_LEGACY_VOCABULARY = (
    ("spec-driven", "block"),
    ("task-driven", "warn"),
    ("dev_mode", "strictness"),
    ("dev-mode", "strictness"),
)


def _stops(text: str) -> set[str]:
    return {re.sub(r"\d+", "#", ln.strip()) for ln in text.splitlines() if STOP.search(ln)}


def _render(preset: Preset, strictness: Strictness, tmp: Path) -> dict[str, str]:
    from harness_maker.interview import _build_answers

    answers = _build_answers(
        locale="en", targets=[Target.CLAUDE_CODE], preset=preset, strictness=strictness
    )
    with pytest.MonkeyPatch.context() as mp:
        pin_install_ref(mp)
        render(
            synthesize(ProjectProfile(), answers, preset=preset),
            tmp,
            freeze_time=DEFAULT_FREEZE_TIME,
        )
    out = {s: (tmp / "commands" / "hm" / f"{s}.md").read_text(encoding="utf-8") for s in STAGES}
    out["settings"] = (tmp / "settings.json").read_text(encoding="utf-8")
    return out


def _ref(preset: Preset, arm: str, stage: str) -> str:
    text = (REF / f"{preset.value}-{arm}" / "commands" / "hm" / f"{stage}.md").read_text(
        encoding="utf-8"
    )
    for old, new in _LEGACY_VOCABULARY:
        text = text.replace(old, new)
    return text


def _hook_commands(settings_text: str) -> list[str]:
    hooks = json.loads(settings_text).get("hooks", {})
    return [
        h.get("command", "")
        for entries in hooks.values()
        for entry in entries
        for h in entry.get("hooks", [])
    ]


@pytest.mark.parametrize("preset", list(Preset), ids=lambda p: p.value)
def test_ac_006_warn_renders_the_checks_and_blocks_nothing(preset: Preset, tmp_path: Path) -> None:
    new = _render(preset, "warn", tmp_path)

    assert "### Check 6" in new["verify"]
    assert "SPEC-need fields" in new["execute"]
    assert "--spec specs/SPEC-{slug}.machine.yaml" in new["review"]

    for stage in STAGES:
        extra = _stops(new[stage]) - _stops(_ref(preset, "task-driven", stage))
        assert not extra, (
            f"{stage} at warn stops on what the relaxed harness never did: {sorted(extra)}"
        )

    assert not any("spec_gate" in c for c in _hook_commands(new["settings"]))


@pytest.mark.parametrize("preset", list(Preset), ids=lambda p: p.value)
def test_ac_006_block_renders_the_spec_gate_hook(preset: Preset, tmp_path: Path) -> None:
    new = _render(preset, "block", tmp_path)

    for stage in STAGES:
        lost = _stops(_ref(preset, "spec-driven", stage)) - _stops(new[stage])
        assert not lost, (
            f"{stage} at block lost stop conditions the strict harness had: {sorted(lost)}"
        )

    assert any("spec_gate" in c for c in _hook_commands(new["settings"]))


def _gate_active(tmp_path: Path, body: str) -> bool:
    """True when the hook reaches its SPEC lookup instead of standing aside.

    With no SPEC on disk and default (warn) severity the lookup ALLOWS with a message; the
    stand-aside path allows silently. The message is the only difference, and it is the one
    that says whether the guard evaluated the right key.
    """
    from harness_maker.gates.spec_gate import evaluate

    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / "harness.yaml").write_text(body, encoding="utf-8")
    decision = evaluate("Write", {"file_path": "tests/test_x.py"}, tmp_path)
    return decision.message != ""


def test_ac_006_an_explicit_block_actually_blocks(tmp_path: Path) -> None:
    """Round-1 consensus P1 (core lens + cross-model, seconded by security): the gate used to
    take its severity from the preset-written `security.gates.spec_gate` literal, so a Side
    project that asked for `block` got the hook registered and the write allowed anyway. The
    knob's name is the contract — `block` refuses."""
    from harness_maker.gates.spec_gate import Severity, evaluate

    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / "harness.yaml").write_text(
        # The preset literal that used to win, set to the value that used to defang the gate.
        "preset: Side\nspec:\n  strictness: block\nsecurity:\n  gates:\n    spec_gate: warn\n",
        encoding="utf-8",
    )
    decision = evaluate("Write", {"file_path": "tests/test_x.py"}, tmp_path)
    assert decision.severity is Severity.BLOCK
    assert decision.allow is False


def test_ac_006_warn_never_blocks_even_when_the_legacy_key_says_block(tmp_path: Path) -> None:
    """The symmetric direction: the legacy key cannot re-arm a gate the strictness stood down."""
    from harness_maker.gates.spec_gate import evaluate

    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / "harness.yaml").write_text(
        "preset: Production\nspec:\n  strictness: warn\n"
        "security:\n  gates:\n    spec_gate: block\n",
        encoding="utf-8",
    )
    decision = evaluate("Write", {"file_path": "tests/test_x.py"}, tmp_path)
    assert decision.allow is True
    assert decision.message == ""


@pytest.mark.parametrize(
    ("body", "active"),
    [
        ("preset: Side\nspec:\n  strictness: block\n", True),
        ("preset: Production\nspec:\n  strictness: warn\n", False),
        ("preset: Production\n", True),
        ("preset: Side\n", False),
        ("preset: Side\ndev_mode: spec-driven\n", True),
        # Advisory-first: an unreadable config must not make every test write fail.
        ("preset: Production\nspec: [unclosed\n", False),
    ],
    ids=[
        "side-block",
        "prod-warn",
        "prod-absent",
        "side-absent",
        "legacy-spec-driven",
        "unreadable",
    ],
)
def test_ac_006_hook_guard_reads_strictness(tmp_path: Path, body: str, active: bool) -> None:
    assert _gate_active(tmp_path, body) is active
