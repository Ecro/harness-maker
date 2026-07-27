"""AC-011 — `/hm:metrics` Step 5d actually renders the unattributed breakdown.

`economics.py` has shipped `unattributed_breakdown` and `unattributed_breakdown_notes`
since Phase 2, and Step 5b dumps the whole report JSON into the model's context, so the
fields were never *dead* — a reader could see them. But Step 5d's list is **prescriptive,
not illustrative**: the fields it enumerates are the ones that get rendered into the
output the user actually reads. `metrics.md.j2` appeared zero times in the PLAN before
Phase 5 was added, so as written no phase would ever have wired it — the global
CLAUDE.md 2026-06-08 absent-case pattern, a feature activating on a surface nobody owns.

Two properties are gated here, and the second is the one that decays:

1. Step 5d names both bucket keys and the notes field. Losing either fails.
2. The template **references** `unattributed_breakdown_notes` rather than restating the
   note prose. The notes are authored once, in `economics._UNATTRIBUTED_BREAKDOWN_NOTES`;
   a template that paraphrased them would drift the moment that tuple changed, and
   nothing downstream would notice.
"""

from __future__ import annotations

import re
from functools import cache
from pathlib import Path
from tempfile import mkdtemp

import pytest

from harness_maker.economics import _UNATTRIBUTED_BREAKDOWN_NOTES
from harness_maker.interview import interview
from harness_maker.models import Preset, ProjectProfile
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize

from .conftest import pin_install_ref

# Step 5d runs from its heading to the next `###` — the prescriptive list lives inside
# it, and a key that moved out of this slice is not wired even if it survives elsewhere
# in the file.
_STEP_5D = re.compile(r"^### 5d — Render the mix\n(?:(?!^### ).)*", re.M | re.S)

_BUCKET_KEYS = ("recoverable", "unrecoverable_in_window")

# The bullet itself, from its `- ` through to the next top-level bullet. Assertions that
# range over the whole slice are satisfied by neighbouring bullets: `capped_turns` and a
# `$` already live there, so a slice-wide "asks for turns and usd" check passed BEFORE
# this phase wired anything (mutation receipt M7).
_BULLET = re.compile(r"^- `unattributed_breakdown` — .*?(?=^- `|\Z)", re.M | re.S)

# `unattributed_breakdown` is a PREFIX of `unattributed_breakdown_notes`, so a bare
# substring test for the field is satisfied by the notes field alone — the bullet could
# lose the buckets entirely and still pass (M1). Match the field reference exactly.
_FIELD_REF = re.compile(r"`unattributed_breakdown`")


@cache
def _metrics_render() -> str:
    profile = ProjectProfile(stack=["python"], scale="medium", lifecycle="active")
    answers = interview(profile, autoloop_mode=True)
    out = Path(mkdtemp(prefix="hm-metrics-"))
    with pytest.MonkeyPatch.context() as mp:
        pin_install_ref(mp)
        render(
            synthesize(profile, answers, preset=Preset.PRODUCTION),
            out,
            freeze_time=DEFAULT_FREEZE_TIME,
        )
    return (out / "commands" / "hm" / "metrics.md").read_text(encoding="utf-8")


def _step_5d() -> str:
    match = _STEP_5D.search(_metrics_render())
    assert match is not None, "Step 5d heading not found — the slice regex is stale"
    return match.group(0)


def _bullet() -> str:
    match = _BULLET.search(_step_5d())
    assert match is not None, "the unattributed_breakdown bullet is not inside Step 5d"
    return match.group(0)


def test_the_slice_is_not_vacuous() -> None:
    """Positive control: an empty or runaway slice would make every check below pass."""
    body = _step_5d()
    assert 500 < len(body) < 8000, len(body)
    assert "Also surface, in one line each:" in body


def test_the_bullet_is_not_vacuous() -> None:
    """Second positive control — the bullet slice must be a bullet, not the whole list."""
    bullet = _bullet()
    assert 200 < len(bullet) < 1500, len(bullet)
    assert bullet.count("- `") == 1, "the bullet regex swallowed a sibling"


def test_step_5d_names_both_unattributed_buckets() -> None:
    """AC-011 — the prescriptive list carries the field and both of its keys."""
    body = _step_5d()
    assert _FIELD_REF.search(body), "the field itself is not referenced"
    for key in _BUCKET_KEYS:
        assert f"`{key}`" in body, key


def test_step_5d_asks_for_turns_and_usd_per_bucket() -> None:
    """A bucket count with no dollars is half the signal; PLAN Phase 5 names both.

    Scoped to the bullet: over the whole slice this passes on `capped_turns` and a `$`
    that belong to other bullets, which is how it passed before anything was wired.
    """
    bullet = _bullet()
    assert "`turns`" in bullet
    assert "`usd`" in bullet


def test_step_5d_prints_the_notes_verbatim_and_does_not_restate_them() -> None:
    """The notes have exactly one author — `economics._UNATTRIBUTED_BREAKDOWN_NOTES`.

    A template that copied their prose would drift silently the first time that tuple
    is edited, which is the failure this assertion exists to prevent. So: the field name
    must be referenced, and no note's distinctive phrasing may appear inline.
    """
    body = _step_5d()
    assert "unattributed_breakdown_notes" in body
    assert "verbatim" in body.lower()
    for note in _UNATTRIBUTED_BREAKDOWN_NOTES:
        opening = " ".join(note.split()[:8])
        assert opening not in body, f"note prose restated in the template: {opening!r}"


def test_the_breakdown_is_not_presented_as_an_attribution() -> None:
    """PLAN ADR-013: `recoverable` is not a claim that these turns WILL be recovered.

    The bucket partitions `(unattributed)`; it does not attribute it. A Step 5d that
    told the reader to fold it into the per-stage table would undo AC-010's conservation
    property, so the negator check is on the instruction, not the data.
    """
    body = _step_5d().lower()
    for negator in ("fold the breakdown into", "add the breakdown to the per-stage"):
        assert negator not in body, negator
