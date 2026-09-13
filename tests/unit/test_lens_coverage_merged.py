"""Merged mode: one group file is evidence for the several lenses it carries.

The gate's stated purpose is to catch a dispatch that never happened, and a group file
vouches for four lenses instead of one — so a fail-open here costs four times what it used
to. `test_merged_mode_is_fail_closed_on_every_bad_file` states that over the whole class of
non-conforming files rather than over an enumeration, which is why it is parametrized on the
corruption rather than on five hand-written cases.

**Phase A.4 — seven tests pass before the implementation exists, for TWO different reasons.**

**Six of them** —
`test_merged_mode_is_fail_closed_on_every_bad_file[absent|unparseable|not-an-object|mislabelled|foreign-run]`
and `test_a_group_file_does_not_vouch_for_a_lens_outside_its_group` — are vacuously true today
because `core.json` is rejected wholesale: `core` is not in `ALL_LENSES`, so the current stem
check drops it and every core lens is `missing` no matter what the file says.

**The seventh is different, and the first draft of this paragraph got it wrong** (corrected from
the A.5 adjudication). `test_four_per_lens_files_still_cover_the_core_set` never writes
`core.json` at all — it writes four per-lens files whose stems are already in `ALL_LENSES`, so it
passes today through the *existing* path and would keep passing under a do-nothing Phase 2. It is
kept because it still discriminates: an implementation that routes only through `LENS_GROUPS`
membership and drops the `stem in ALL_LENSES` fallback fails it, since none of `design.json` …
`consistency.json` is a group key. That is SPEC AC-004's third clause — the un-re-rendered
harness — and it had no named witness before this file.

What makes that legitimate rather than a false-RED is the sibling requirement, and it is
satisfied **in this file**: `test_one_core_file_covers_the_four_core_lenses`,
`test_exercised_names_the_core_lenses_not_the_group`,
`test_a_core_file_alone_leaves_only_the_domain_lenses_missing` and
`test_the_union_across_rounds_still_holds_for_a_group_file` are RED, and they are what force
`core.json` acceptance into existence. The moment Phase C makes a group file acceptable, every
one of the seven stops being vacuous and starts discriminating a fail-closed reader from a
fail-open one — which is the whole risk this phase carries (a group file vouches for four
lenses, so a fail-open costs four times what it did).

Contrast with the Phase 1 test A.5 round 1 rejected: that one guarded `lens_dispatch`, which
**no** implementation in its phase was going to touch, so its construct was never made
reachable. Here the construct is this phase's own deliverable.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from harness_maker.conditional_router import CORE_LENSES, DOMAIN_LENSES
from harness_maker.lens_coverage import coverage_verdict

RUN = "run-merged"


def _write(d: Path, stem: str, payload: object) -> None:
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{stem}.json").write_text(json.dumps(payload), encoding="utf-8")


def _group_file(d: Path, stem: str, lenses: tuple[str, ...], *, run_id: str = RUN) -> None:
    """A merged result file: file-level `lens` is the GROUP, findings carry member lenses."""
    _write(
        d,
        stem,
        {
            "lens": stem,
            "run_id": run_id,
            "findings": [{"id": f"x-{i}", "lens": lens} for i, lens in enumerate(lenses)],
        },
    )


def _domain_files(d: Path) -> None:
    for lens in DOMAIN_LENSES:
        _write(d, lens, {"lens": lens, "run_id": RUN, "findings": []})


def test_one_core_file_covers_the_four_core_lenses(tmp_path: Path) -> None:
    """SPEC AC-004 — the merged case."""
    _group_file(tmp_path, "core", CORE_LENSES)
    _domain_files(tmp_path)
    verdict = coverage_verdict(tmp_path, RUN, "Production")
    assert verdict["missing"] == []
    assert verdict["blocks_approval"] is False


def test_four_per_lens_files_still_cover_the_core_set(tmp_path: Path) -> None:
    """SPEC AC-004's third clause — an un-re-rendered harness writes per-lens files."""
    for lens in CORE_LENSES:
        _write(tmp_path, lens, {"lens": lens, "run_id": RUN, "findings": []})
    _domain_files(tmp_path)
    verdict = coverage_verdict(tmp_path, RUN, "Production")
    assert verdict["missing"] == []
    assert verdict["blocks_approval"] is False


def test_exercised_names_the_core_lenses_not_the_group(tmp_path: Path) -> None:
    """SPEC AC-005 — `lenses_exercised` telemetry stays comparable with pre-merge rows.

    The expected array is the shipped 2026-08-19 row, written by the fan-out this replaces.
    """
    _group_file(tmp_path, "core", CORE_LENSES)
    _domain_files(tmp_path)
    exercised = coverage_verdict(tmp_path, RUN, "Production")["exercised"]
    assert exercised == [
        "design",
        "functionality",
        "robustness",
        "consistency",
        "security",
        "concurrency",
        "tests",
    ]
    assert "core" not in exercised


def test_a_core_file_alone_leaves_only_the_domain_lenses_missing(tmp_path: Path) -> None:
    """Discrimination: a reader that accepted any file would report nothing missing."""
    _group_file(tmp_path, "core", CORE_LENSES)
    verdict = coverage_verdict(tmp_path, RUN, "Production")
    assert verdict["missing"] == list(DOMAIN_LENSES)
    assert verdict["blocks_approval"] is True


_BAD: dict[str, Any] = {
    "absent": None,
    "unparseable": "{not json",
    "not-an-object": [{"lens": "core", "run_id": RUN}],
    "mislabelled": {"lens": "design", "run_id": RUN, "findings": []},
    "foreign-run": {"lens": "core", "run_id": "some-other-invocation", "findings": []},
}


@pytest.mark.parametrize("kind", sorted(_BAD))
def test_merged_mode_is_fail_closed_on_every_bad_file(tmp_path: Path, kind: str) -> None:
    """SPEC AC-006 — "cannot tell" must never resolve to "exercised"."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    body = _BAD[kind]
    if kind == "unparseable":
        (tmp_path / "core.json").write_text(str(body), encoding="utf-8")
    elif body is not None:
        _write(tmp_path, "core", body)
    _domain_files(tmp_path)

    verdict = coverage_verdict(tmp_path, RUN, "Production")
    missing = verdict["missing"]
    assert isinstance(missing, list)
    for lens in CORE_LENSES:
        assert lens in missing, f"{kind}: {lens} was vouched for by a bad group file"
    assert verdict["blocks_approval"] is True


@pytest.mark.parametrize(
    "covered",
    [
        pytest.param(("design",), id="one-of-four"),
        pytest.param(("design", "functionality"), id="two-of-four"),
    ],
)
def test_a_partially_covered_group_file_still_credits_every_member(
    tmp_path: Path, covered: tuple[str, ...]
) -> None:
    """SPEC AC-004's disputed half, pinned as an executable fact rather than left as prose.

    Credit comes from the ROUTER's membership, never from the payload's findings. A merged file
    whose findings name only `design` still clears all four core lenses — the gate answers "was
    this lens asked", not "did this lens deliver" (SPEC Open Question #2, ADR-003).

    **This is the one behaviour this task's review argued about most and settled by citation.**
    Two independent lenses raised it as a defect; it was rejected on AC-004's authority. Without
    this case the suite could not tell the two readings apart: an implementation crediting
    `{f["lens"] for f in findings} & CORE_LENSES` — the exact alternative that was rejected —
    passes every other assertion in this file identically, because every other fixture happens to
    tag all four members. Whichever reading is right, a silent switch between them should not be
    invisible.
    """
    _group_file(tmp_path, "core", covered)
    _domain_files(tmp_path)
    verdict = coverage_verdict(tmp_path, RUN, "Production")
    assert verdict["missing"] == []
    assert verdict["blocks_approval"] is False
    exercised = verdict["exercised"]
    assert isinstance(exercised, list)
    for lens in CORE_LENSES:
        assert lens in exercised, f"{lens} was asked as part of the group and must be credited"


def test_a_group_file_does_not_vouch_for_a_lens_outside_its_group(tmp_path: Path) -> None:
    """The group's membership is the router's, not the file's — a payload cannot widen it."""
    _write(
        tmp_path,
        "core",
        {"lens": "core", "run_id": RUN, "findings": [{"id": "x", "lens": "security"}]},
    )
    verdict = coverage_verdict(tmp_path, RUN, "Production")
    missing = verdict["missing"]
    assert isinstance(missing, list)
    assert "security" in missing


def test_the_union_across_rounds_still_holds_for_a_group_file(tmp_path: Path) -> None:
    """Coverage is cumulative over a review; a later round legitimately holds one file."""
    r1, r2 = tmp_path / "1", tmp_path / "2"
    _group_file(r1, "core", CORE_LENSES)
    for lens in DOMAIN_LENSES:
        _write(r2, lens, {"lens": lens, "run_id": RUN, "findings": []})
    verdict = coverage_verdict([r1, r2], RUN, "Production")
    assert verdict["missing"] == []
