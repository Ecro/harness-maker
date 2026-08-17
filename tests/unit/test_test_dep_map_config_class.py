"""`CLASS_CONFIG` — the config shapes stop forcing a full suite (ADR-006).

`classify_path` is total, so anything that is not `.j2`, not render-prefixed, not a doc
with consumers, not inert and not `.py` falls to the loud-FULL default arm. That arm held
`pyproject.toml`, `uv.lock`, `.github/workflows/*.yml` and `.claude/harness.yaml` — and
because `select_tests` returns FULL when ANY changed file is forcing, one of them in a
phase's change set discards every other file's targeted hints. This repository's release
procedure edits `pyproject.toml` on a five-file version sync, so that arm fires often.

Two constraints shape what is asserted here, and both come from findings against the PLAN
that wrote this file:

* **`.github/workflows/` is NOT inert.** The first revision routed it there on the reasoning
  that a CI config cannot change a local pytest outcome. It can:
  `tests/unit/test_profile.py::test_profile_dogfood_on_harness_maker_repo` runs `profile()` on
  the real repository root and branches its `ci_provider` assertion on whether that directory
  holds `.yml`/`.yaml` files — and it does here (`ci.yml`, `nightly.yml`), so the branch is
  live. (The *other* `ci_provider` tests in that file build their own `.github/workflows/`
  under `tmp_path` and are irrelevant to this; a review round cited them and reached the
  opposite conclusion, which is why the specific node id is named here.) It joins the config
  class instead.
* **`any-forces-all` is unchanged** (ADR-007). A config file mixed with a *hintless* `.py`
  must still select FULL. Asserting only the happy mixed case would let the classifier claim
  a guarantee the selector does not make.

`CONFIG_SUITES` is asserted by property — non-empty, test-rooted, naming paths that exist, and
reaching the suites that demonstrably read these files — never by literal equality. A test that
restates the constant passes against any value the constant happens to hold, which is the
tautology the Phase A.5 discrimination lens exists to reject.

**The ceiling is behavioural** (`test_a_config_selection_leaves_part_of_the_unit_tree_unselected`).
ADR-006 gives the constant a floor and no upper bound, so property assertions alone are satisfied
by `CONFIG_SUITES = ("tests/unit",)` — the always-FULL cost restored under a targeted label. Two
A.5 rounds were spent on that unwritten boundary before it was stated as an outcome instead of a
shape.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path

import pytest

from harness_maker.test_dep_map import (
    CLASS_CONFIG,
    CLASS_DOC_WITH_CONSUMERS,
    CLASS_INERT,
    CLASS_RENDER_AFFECTING,
    CLASS_SOURCE_WITH_HINTS,
    CLASS_SOURCE_WITHOUT_HINTS,
    CONFIG_SUITES,
    RENDER_AFFECTING_SUITES,
    TESTS_NOT_CONFIG_AFFECTING,
    classify_path,
    select_tests,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]

#: Proven hinted by `test_a_source_file_with_hints_selects_those_tests` in the sibling suite.
_HINTED_SOURCE = "src/harness_maker/io_utils.py"
#: Proven hintless by `test_a_deleted_or_renamed_path_classifies_by_its_pre_change_path`.
_HINTLESS_SOURCE = "src/harness_maker/deleted_module.py"


def _classify(rel: str) -> str:
    return classify_path(rel, _REPO_ROOT)


def _covered(node: str, selected: list[str]) -> bool:
    """`select_tests` drops a node id that sits under a directory node already selected, so
    literal set-containment is the wrong question: a `CONFIG_SUITES` holding `tests/unit`
    legitimately subsumes `tests/unit/test_x.py` and the file id never appears. Asking for
    membership instead would make two assertions in this file mutually unsatisfiable and push
    Phase C to narrow `CONFIG_SUITES` to satisfy a test rather than to satisfy ADR-006."""
    if node in selected:
        return True
    return any(node.startswith(f"{s.rstrip('/')}/") for s in selected)


def _all_covered(nodes: Iterable[str], selected: list[str]) -> bool:
    return all(_covered(n, selected) for n in nodes)


# ── the config class selects tests instead of forcing FULL ───────────────────


@pytest.mark.parametrize(
    "rel",
    [
        "pyproject.toml",
        "uv.lock",
        ".github/workflows/ci.yml",
        ".github/workflows/release.yml",
    ],
)
def test_a_config_file_selects_the_config_suites(rel: str) -> None:
    assert _classify(rel) == CLASS_CONFIG
    sel = select_tests([rel], _REPO_ROOT)
    assert sel["mode"] == "targeted", sel
    assert _all_covered(CONFIG_SUITES, sel["node_ids"]), sel["node_ids"]


def test_harness_yaml_selects_the_render_suites_not_the_config_suites() -> None:
    """It drives every render, so the render suites are the ones that would catch a
    regression in it — a different answer from the packaging files, which is why ADR-006
    routes it separately rather than folding all four into one class."""
    assert _classify(".claude/harness.yaml") == CLASS_RENDER_AFFECTING
    sel = select_tests([".claude/harness.yaml"], _REPO_ROOT)
    assert sel["mode"] == "targeted", sel
    assert _all_covered(RENDER_AFFECTING_SUITES, sel["node_ids"]), sel["node_ids"]


# ── mixed change sets: the accumulation arm, and ADR-007's unchanged forcing rule ──


def test_a_config_file_and_a_hinted_source_union_both_sets() -> None:
    """Classification alone contributes no node ids — `select_tests` accumulates per class,
    and a class with no arm in that loop silently contributes zero. This is the shape that
    would report a clean targeted run while the config suites were never selected."""
    sel = select_tests(["pyproject.toml", _HINTED_SOURCE], _REPO_ROOT)
    assert sel["mode"] == "targeted", sel
    assert _all_covered(CONFIG_SUITES, sel["node_ids"]), sel["node_ids"]
    hinted_only = select_tests([_HINTED_SOURCE], _REPO_ROOT)["node_ids"]
    assert hinted_only, "the fixture source stopped being hinted — pick another"
    assert _all_covered(hinted_only, sel["node_ids"]), (hinted_only, sel["node_ids"])


def test_a_config_file_with_a_hintless_source_still_forces_full() -> None:
    """ADR-007 is unchanged: "no test maps to this file" still means "we do not know what
    this breaks". Narrowing the forcing SET is the remedy; the forcing RULE stays."""
    assert _classify(_HINTLESS_SOURCE) != CLASS_CONFIG
    sel = select_tests(["pyproject.toml", _HINTLESS_SOURCE], _REPO_ROOT)
    assert sel["mode"] == "full", sel
    assert _HINTLESS_SOURCE in sel["reason"], sel["reason"]


def test_two_config_files_together_stay_targeted() -> None:
    """The five-file version sync touches `pyproject.toml`; a dependency bump touches
    `uv.lock` too. Together they must not degrade to FULL."""
    sel = select_tests(["pyproject.toml", "uv.lock"], _REPO_ROOT)
    assert sel["mode"] == "targeted", sel
    assert _all_covered(CONFIG_SUITES, sel["node_ids"]), sel["node_ids"]


# ── the suite tuple itself ────────────────────────────────────────────────────


def test_config_suites_names_paths_that_exist() -> None:
    """A prefix check alone passes for `("tests/unit/test_deleted.py",)`. `select_tests` would
    then report `mode: targeted` with a node id pytest cannot collect, turning a config
    change's selection into a hard collection error rather than a narrower run. The sibling
    suite guards both of its analogous constants this way."""
    assert CONFIG_SUITES, "an empty tuple would trade always-FULL for sometimes-NONE"
    assert all(n.startswith("tests/") for n in CONFIG_SUITES), CONFIG_SUITES
    for node in CONFIG_SUITES:
        assert (_REPO_ROOT / node).exists(), node


def test_config_suites_reaches_the_suites_that_read_these_files() -> None:
    """Two suites demonstrably read the repository's OWN copies of the files this class routes:

    * `tests/unit/test_version_sync.py` reads the real `pyproject.toml` through `REPO_ROOT`;
    * `tests/unit/test_profile.py::test_profile_dogfood_on_harness_maker_repo` runs `profile()`
      on the real repo root and branches its `ci_provider` assertion on whether
      `.github/workflows/` contains `.yml`/`.yaml` files — which it does here (`ci.yml`,
      `nightly.yml`), so that branch is live rather than skipped.

    Naming both is what makes this test discriminating: a `CONFIG_SUITES` that omits the actual
    consumers satisfies every other test in the file, because they only require the constant to
    be covered by its own selection — true for whatever value it holds.
    """
    for consumer in ("tests/unit/test_version_sync.py", "tests/unit/test_profile.py"):
        assert (_REPO_ROOT / consumer).is_file(), f"fixture moved: {consumer}"
        assert _covered(consumer, list(CONFIG_SUITES)), (consumer, CONFIG_SUITES)


def test_the_config_class_is_a_distinct_class_and_selects_targeted() -> None:
    """`select_tests` populates `classified` before returning on the FULL path too, so the
    classification assertion alone is satisfied even when routing failed — the `mode` assertion
    is what closes that. And the exclusion set must name the DEFAULT arm
    (`CLASS_SOURCE_WITHOUT_HINTS`), which is the alias this guard exists for; omitting it left
    the guard inert against the one wrong implementation it was written to catch."""
    sel = select_tests(["pyproject.toml"], _REPO_ROOT)
    assert sel["mode"] == "targeted", sel
    assert sel["classified"]["pyproject.toml"] == CLASS_CONFIG
    assert CLASS_CONFIG not in {
        CLASS_RENDER_AFFECTING,
        CLASS_SOURCE_WITH_HINTS,
        CLASS_SOURCE_WITHOUT_HINTS,
        CLASS_DOC_WITH_CONSUMERS,
        CLASS_INERT,
    }


# ── Phase D.5: combinations the routing change newly makes reachable ─────────


def test_a_config_file_and_a_template_union_both_suite_sets() -> None:
    """Before this change a config file returned at the forcing early-return, so a change set
    holding one never reached the accumulation loop at all. Two directory-bearing classes
    meeting there is a path that could not previously exist: `CONFIG_SUITES` names
    `tests/structural`, `RENDER_AFFECTING_SUITES` names it too, and the dedup collapses only
    exact duplicates — so the union must contain both sets and run `tests/structural` once."""
    sel = select_tests(
        ["pyproject.toml", "src/harness_maker/templates/stages/verify.md.j2"], _REPO_ROOT
    )
    assert sel["mode"] == "targeted", sel
    assert _all_covered(CONFIG_SUITES, sel["node_ids"]), sel["node_ids"]
    assert _all_covered(RENDER_AFFECTING_SUITES, sel["node_ids"]), sel["node_ids"]
    assert len(sel["node_ids"]) == len(set(sel["node_ids"])), sel["node_ids"]


def test_a_config_file_beside_only_inert_paths_still_selects() -> None:
    """The other newly-reachable combination, and the absent-case half of it: inert paths
    contribute nothing, so before this change `["pyproject.toml", "work-docs/PLAN-x.md"]` hit
    the forcing return, and after it the selection is carried entirely by the config arm. If
    that arm ever contributed nothing the result would fall to the empty-selection backstop and
    read as FULL — correct but silently undoing the change, which is why this asserts the
    outcome rather than trusting `CONFIG_SUITES` to stay non-empty."""
    sel = select_tests(["pyproject.toml", "work-docs/PLAN-x.md"], _REPO_ROOT)
    assert sel["mode"] == "targeted", sel
    assert _all_covered(CONFIG_SUITES, sel["node_ids"]), sel["node_ids"]


def test_a_deleted_workflow_file_classifies_by_its_path() -> None:
    """Classification is path-only by module rule, and a deleted or renamed file is the change
    most likely to break something. The sibling suite pins this for the render and source
    classes; the config class was added without it."""
    assert _classify(".github/workflows/removed.yml") == CLASS_CONFIG
    sel = select_tests([".github/workflows/removed.yml"], _REPO_ROOT)
    assert sel["mode"] == "targeted", sel


# ── the breadth bound (Path B) ───────────────────────────────────────────────


def test_a_config_selection_leaves_part_of_the_unit_tree_unselected() -> None:
    """The ceiling ADR-006 never wrote down, expressed behaviourally.

    ADR-006 specifies a FLOOR for `CONFIG_SUITES` ("at minimum the suites that read those
    files") and explicitly declines the other side ("it errs broad"). With no ceiling,
    `CONFIG_SUITES = ("tests/unit",)` satisfies every other assertion in this file —
    including the prefix-relaxed ones — while restoring exactly the always-run-everything
    behaviour ADR-006 exists to remove. Two Phase A.5 rounds oscillated around that
    unwritten boundary.

    This is the boundary, as an outcome rather than a shape: a `pyproject.toml` change must
    leave *some* unit module unselected. It kills the degenerate value without forbidding
    `tests/structural`, which ADR-006 names as legitimately in the tuple — a structural ban
    on bare directories would have. It is also not hostage to a future maintainer adding a
    config-reading suite: it asks only that the selection be smaller than the directory, not
    that any particular module stay out.

    With this bound in place the prefix relaxation in
    `test_config_suites_reaches_the_suites_that_read_these_files` is no longer a hole — the
    directory value it would admit is rejected here.
    """
    sel = select_tests(["pyproject.toml"], _REPO_ROOT)
    assert sel["mode"] == "targeted", sel
    unit_modules = [
        p.relative_to(_REPO_ROOT).as_posix()
        for p in sorted((_REPO_ROOT / "tests" / "unit").glob("test_*.py"))
    ]
    assert unit_modules, "the unit tree is empty — this bound has stopped bounding anything"
    uncovered = [m for m in unit_modules if not _covered(m, sel["node_ids"])]
    assert uncovered, (
        "a pyproject.toml change selects every tests/unit module — CONFIG_SUITES has widened "
        f"to the whole directory, which is the always-FULL cost ADR-006 removes. node_ids: "
        f"{sel['node_ids']}"
    )


# ── the coverage gate (PLAN Phase 1 work item 4) ─────────────────────────────


def test_a_new_suite_that_reads_repo_level_config_cannot_be_silently_unlisted() -> None:
    """The omission detector, mirroring `test_every_directory_under_tests_is_classified_by_the
    _constant` for the config class.

    Class 3's failure mode is a curated list that silently narrows: a suite is added that a
    `pyproject.toml` change should reach, nobody adds it to `CONFIG_SUITES`, and the selection
    quietly stops covering it. Property assertions about today's tuple cannot see that — they
    keep passing. This scans `tests/` for modules that read one of the routed files through a
    repo-root anchor and requires each to be either covered by `CONFIG_SUITES` or explicitly
    opted out in `TESTS_NOT_CONFIG_AFFECTING`, so an omission fails the build with the file
    named rather than being allowed.
    """
    # `Path(__file__)` is in the anchor set because `tests/unit/test_profile.py` — the canonical
    # `.github/workflows` consumer — finds the root by walking `start.parents`, with no
    # `REPO_ROOT` name and no `parents[N]` subscript anywhere in it. An anchor set that names
    # only the two idioms this file happens to use misses the one consumer it calls canonical.
    anchored = re.compile(r"REPO_ROOT|parents\[\d+\]|Path\(__file__\)")
    routed = ("pyproject.toml", "uv.lock", ".github/workflows")

    # The two selector suites discuss the routed paths in prose; counting them would let the
    # canary below pass on a self-match while the scan found nothing real. Scoping the
    # exclusion to this module alone left the sibling in, which is the same hole one file over.
    discuss_only = {"test_test_dep_map_config_class.py", "test_test_dep_map_select.py"}

    consumers = []
    for path in sorted((_REPO_ROOT / "tests").rglob("test_*.py")):
        if "__pycache__" in path.parts or path.name in discuss_only:
            continue
        text = path.read_text(encoding="utf-8")
        if not anchored.search(text):
            continue
        if not any(name in text for name in routed):
            continue
        consumers.append(path.relative_to(_REPO_ROOT).as_posix())

    assert consumers, "the detector matched nothing — it has stopped detecting"

    # The opt-out tuple needs its own ceiling, for the same reason CONFIG_SUITES did and by a
    # different argument. `TESTS_NOT_CONFIG_AFFECTING = ("tests",)` disposes of every finding
    # this gate will ever make, exists on disk, and is invisible to every other assertion here
    # — the breadth bound above constrains `select_tests`, which never reads this constant. The
    # sibling precedent Phase C will copy, `TESTS_DIRS_NOT_RENDER_AFFECTING`, is eight bare
    # directories, so the degenerate shape is the likely one rather than an exotic one.
    #
    # This is NOT the structural ban that was rightly rejected for CONFIG_SUITES: that argument
    # was about the tuple that SELECTS tests, where ADR-006 names `tests/structural` as a
    # legitimate directory member. This tuple only disposes of detector findings, and the
    # detector yields file paths, so a directory entry is never needed to answer one.
    for opt_out in TESTS_NOT_CONFIG_AFFECTING:
        assert opt_out.endswith(".py"), (
            f"{opt_out!r} is not a file — an opt-out must dispose of one detected suite, and a "
            "directory entry silently disposes of every suite under it, now and in future"
        )
        assert opt_out in consumers, (
            f"{opt_out!r} is opted out of the config class but the detector never flagged it — "
            "either it stopped reading repo-level config (drop the entry) or the detector "
            "stopped seeing it (fix the detector)"
        )

    declared = list(CONFIG_SUITES) + list(TESTS_NOT_CONFIG_AFFECTING)
    unlisted = [c for c in consumers if not _covered(c, declared)]
    assert not unlisted, (
        f"suites read repo-level config but are neither selected nor opted out: {unlisted} — "
        "add each to CONFIG_SUITES or TESTS_NOT_CONFIG_AFFECTING in test_dep_map.py. Note the "
        "cost: `test_dep_map.py` is the selector's own source, so editing it self-short-circuits "
        "to the FULL suite for that change. Batch these edits rather than fixing them one at a "
        "time."
    )
