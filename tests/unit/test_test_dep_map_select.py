"""Phase 4 — the four-way test-selection classifier (PLAN-workflow-step-audit ADR-008).

The interview locked "any changed file with no test hint → that phase runs the full
suite". Both second-opinion models then observed that `build_test_hints()` skips every
file whose suffix is not `.py` (`test_dep_map.py:109-110`), so in this repo — where most
changes are `.j2` templates, markdown and config — that rule selects FULL essentially
always: machinery added, cost preserved.

ADR-008 keeps what the locked rule protects (a source file with no known test must never
be silently untested) and sharpens the predicate into four classes. The property that
matters most here is that the classifier is **total**: the validator caught a first
version that defaulted only *out-of-root* paths, leaving in-root non-matches selecting
**zero** tests — trading an always-FULL bug for a sometimes-NONE bug, which is strictly
weaker than today. Every test below that names a concrete path is aimed at that arm.

**The four config shapes moved out of that arm** (PLAN-self-induced-regression-gate
ADR-006): `pyproject.toml`, `uv.lock` and `.github/workflows/` are now `CLASS_CONFIG`, and
`.claude/harness.yaml` is render-affecting. They are asserted in
`test_test_dep_map_config_class.py`; what remains here guards the default arm with paths
that genuinely have no mapped tests. The forcing RULE is unchanged — one hintless source
file still takes the whole selection to FULL.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from harness_maker.test_dep_map import (
    CLASS_CONFIG,
    CLASS_DOC_WITH_CONSUMERS,
    CLASS_INERT,
    CLASS_RENDER_AFFECTING,
    CLASS_SOURCE_WITH_HINTS,
    CLASS_SOURCE_WITHOUT_HINTS,
    DOC_CONSUMING_SUITES,
    RENDER_AFFECTING_SUITES,
    SELECTOR_SOURCE,
    TESTS_DIRS_NOT_RENDER_AFFECTING,
    classify_path,
    select_tests,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _classify(rel: str) -> str:
    return classify_path(rel, _REPO_ROOT)


# ── class 1: a source file some test maps to ───────────────────────────────────


def test_a_source_file_with_hints_selects_those_tests() -> None:
    sel = select_tests(["src/harness_maker/io_utils.py"], _REPO_ROOT)
    assert sel["mode"] == "targeted", sel
    assert sel["node_ids"], "a module with importing tests selected nothing"
    assert all(n.startswith("tests/") for n in sel["node_ids"]), sel["node_ids"]
    assert sel["classified"]["src/harness_maker/io_utils.py"] == CLASS_SOURCE_WITH_HINTS


# ── class 2: a source file nothing maps to → FULL, loudly ─────────────────────


def test_a_python_file_with_no_hint_forces_full_and_names_itself(tmp_path: Path) -> None:
    """The locked decision's protected case. `tmp_path` has no `tests/`, so no hint
    can exist for anything — the classification cannot be an accident of this repo."""
    orphan = tmp_path / "src" / "pkg" / "lonely.py"
    orphan.parent.mkdir(parents=True)
    orphan.write_text("x = 1\n", encoding="utf-8")
    sel = select_tests(["src/pkg/lonely.py"], tmp_path)
    assert sel["mode"] == "full", sel
    assert "src/pkg/lonely.py" in sel["reason"], sel["reason"]
    assert sel["classified"]["src/pkg/lonely.py"] == CLASS_SOURCE_WITHOUT_HINTS


# ── class 3: render-affecting → a bounded, named set, never FULL ───────────────


def test_a_template_change_selects_the_render_suites_and_not_full() -> None:
    sel = select_tests(["src/harness_maker/templates/stages/verify.md.j2"], _REPO_ROOT)
    assert sel["mode"] == "targeted", sel
    assert set(sel["node_ids"]) == set(RENDER_AFFECTING_SUITES), sel["node_ids"]
    assert (
        sel["classified"]["src/harness_maker/templates/stages/verify.md.j2"]
        == CLASS_RENDER_AFFECTING
    )


@pytest.mark.parametrize(
    "rel",
    [
        "src/harness_maker/templates/agents/code-reviewer.md.j2",
        "tests/snapshot/fixtures/whatever.md",
        "tests/e2e/sandbox-plugin-test/.claude/commands/hm/verify.md",
    ],
)
def test_render_affecting_covers_templates_and_snapshot_fixtures(rel: str) -> None:
    assert _classify(rel) == CLASS_RENDER_AFFECTING


# ── class 4: inert → contributes nothing, and never forces FULL alone ─────────


@pytest.mark.parametrize(
    "rel",
    [
        "work-docs/PLAN-workflow-step-audit.md",
        "work-docs/RESEARCH-x.md",
        ".claude/memory/wiki.md",
        "CHANGELOG.md",
    ],
)
def test_inert_paths_are_inert(rel: str) -> None:
    """`docs/…` and `README.md` USED to be listed here. The review found their real
    consumers, so their presence in this list was the defect, not the coverage."""
    assert _classify(rel) == CLASS_INERT


def test_a_markdown_only_change_selects_neither_tests_nor_full() -> None:
    sel = select_tests(["work-docs/PLAN-x.md", ".claude/memory/wiki.md"], _REPO_ROOT)
    assert sel["mode"] == "targeted", sel
    assert sel["node_ids"] == [], sel


# ── the default arm — the branch whose omission the validator caught ──────────


@pytest.mark.parametrize(
    "rel",
    [
        "tests/fixtures/stop_payload_wsl2.json",
        "../outside-the-root/thing.py",
        "Makefile",
        "src/harness_maker/py.typed",
    ],
)
def test_an_unmatched_path_falls_to_full_not_to_zero_tests(rel: str) -> None:
    """The default arm's whole job: a path nothing maps to selects everything rather than
    nothing. Selecting zero would be indistinguishable from "checked and clean", which is
    strictly weaker than today's always-run-everything.

    The four config shapes that used to sit in this list are now routed by ADR-006 and are
    asserted in `test_test_dep_map_config_class.py`. What is left has no mapped tests by any
    rule: a fixture payload, an out-of-root path, a Makefile, and a marker file."""
    assert _classify(rel) == CLASS_SOURCE_WITHOUT_HINTS
    sel = select_tests([rel], _REPO_ROOT)
    assert sel["mode"] == "full", sel
    assert rel in sel["reason"], sel["reason"]


def test_the_classifier_is_total_over_a_hostile_sample() -> None:
    """Every path lands in exactly one of the four classes — no `None`, no exception."""
    hostile = [
        "",
        ".",
        "..",
        "/absolute/path.py",
        "a/b/c/d/e/f.unknownsuffix",
        "src/harness_maker/",
        ".gitignore",
        "tests/",
    ]
    classes = {
        CLASS_SOURCE_WITH_HINTS,
        CLASS_SOURCE_WITHOUT_HINTS,
        CLASS_RENDER_AFFECTING,
        CLASS_INERT,
        CLASS_CONFIG,
    }
    for rel in hostile:
        assert _classify(rel) in classes, rel


# ── deletions and renames resolve against the PRE-change path ────────────────


def test_a_deleted_or_renamed_path_classifies_by_its_pre_change_path() -> None:
    """The file is gone from disk, so a classifier that stats the path would misroute
    it — a deleted template must still select the render suites."""
    assert _classify("src/harness_maker/templates/stages/deleted-stage.md.j2") == (
        CLASS_RENDER_AFFECTING
    )
    assert _classify("src/harness_maker/deleted_module.py") == CLASS_SOURCE_WITHOUT_HINTS
    sel = select_tests(["src/harness_maker/templates/stages/gone.md.j2"], _REPO_ROOT)
    assert sel["mode"] == "targeted", sel


# ── mixed inputs: one FULL-forcing path dominates ────────────────────────────


def test_one_hintless_source_file_forces_full_for_the_whole_phase() -> None:
    """ADR-007 of PLAN-self-induced-regression-gate keeps this rule. The forcing path used to
    be `uv.lock`; ADR-006 moved that to `CLASS_CONFIG`, so the case is now carried by a source
    module no test maps to — which is what the rule was always about."""
    sel = select_tests(
        [
            "work-docs/PLAN-x.md",
            "src/harness_maker/templates/stages/verify.md.j2",
            "src/harness_maker/deleted_module.py",
        ],
        _REPO_ROOT,
    )
    assert sel["mode"] == "full", sel
    assert "src/harness_maker/deleted_module.py" in sel["reason"]


def test_render_and_hinted_sources_union_without_forcing_full() -> None:
    sel = select_tests(
        ["src/harness_maker/io_utils.py", "src/harness_maker/templates/stages/spec.md.j2"],
        _REPO_ROOT,
    )
    assert sel["mode"] == "targeted", sel
    assert set(RENDER_AFFECTING_SUITES) <= set(sel["node_ids"]), sel["node_ids"]


# ── the class-3 constant cannot silently narrow ──────────────────────────────


def test_every_directory_under_tests_is_classified_by_the_constant() -> None:
    """ADR-008's named residual, given a detector.

    Class 3's suite list is curated, so a newly added render-sensitive suite would
    silently stop running per-phase. This fails when a directory appears under `tests/`
    that is neither render-affecting nor explicitly declared not to be — forcing an
    edit rather than allowing an omission.
    """
    present = {
        f"tests/{p.name}"
        for p in (_REPO_ROOT / "tests").iterdir()
        if p.is_dir() and p.name != "__pycache__"
    }
    declared = set(RENDER_AFFECTING_SUITES) | set(TESTS_DIRS_NOT_RENDER_AFFECTING)
    undeclared = present - declared
    assert not undeclared, (
        f"new test directories are unclassified: {sorted(undeclared)} — add each to "
        f"RENDER_AFFECTING_SUITES or TESTS_DIRS_NOT_RENDER_AFFECTING in test_dep_map.py"
    )
    stale = declared - present
    assert not stale, f"declared test directories that no longer exist: {sorted(stale)}"


def test_the_render_suite_constant_names_real_directories() -> None:
    for suite in RENDER_AFFECTING_SUITES:
        assert (_REPO_ROOT / suite).is_dir(), suite


# ── the CLI surface ──────────────────────────────────────────────────────────


def test_the_cli_emits_json_and_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    import json

    from harness_maker.test_dep_map import main

    rc = main(["--root", str(_REPO_ROOT), "--changed-file", "src/harness_maker/deleted_module.py"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["mode"] == "full"
    assert "src/harness_maker/deleted_module.py" in payload["reason"]


def test_the_cli_with_no_changed_files_is_explicit_not_silent(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The absent case. An empty change set must not read as "targeted, zero tests" —
    that is indistinguishable from "everything is inert" and would silently skip a
    phase's verification."""
    import json

    from harness_maker.test_dep_map import main

    rc = main(["--root", str(_REPO_ROOT)])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["mode"] == "full"
    assert "no changed files" in payload["reason"]


# ── REVIEW P1-1 / P1-2 — the two ways a selection reported "targeted" over nothing ──


def test_the_selector_source_forces_full() -> None:
    """P1-1. `build_test_hints` returns this file as its own hint (its stem reads as a
    test module), that hint is filtered out for not living under `tests/`, and the
    result was `targeted` with an EMPTY node list — a false green on the one file that
    decides every other file's fate."""
    out = select_tests([SELECTOR_SOURCE], _REPO_ROOT)
    assert out["mode"] == "full"
    assert SELECTOR_SOURCE in out["reason"]
    assert "cannot produce evidence about its own change" in out["reason"]


def test_selector_source_forces_full_even_beside_a_targetable_file() -> None:
    """The rule is not "if nothing else matched" — a circular selection stays circular
    when a second file happens to contribute node ids."""
    out = select_tests(
        [SELECTOR_SOURCE, "src/harness_maker/templates/stages/spec.md.j2"], _REPO_ROOT
    )
    assert out["mode"] == "full"
    assert out["node_ids"] == []


def test_a_source_whose_hints_are_all_filtered_out_forces_full(tmp_path: Path) -> None:
    """The GENERAL form of P1-1, guarded so the specific rule above is not the only
    thing standing between an all-filtered hint set and an empty targeted run."""
    root = tmp_path
    (root / "src").mkdir()
    # Stem reads as a test module → `build_test_hints` hints at itself → filtered out.
    (root / "src" / "test_thing.py").write_text("x = 1\n", encoding="utf-8")
    out = select_tests(["src/test_thing.py"], root)
    assert out["mode"] == "full"
    assert "src/test_thing.py" in out["reason"]


@pytest.mark.parametrize(
    ("path", "expected_suite"),
    [
        ("README.md", "tests/integration/test_readme_one_prompt.py"),
        ("docs/HOW-IT-WORKS.md", "tests/unit/test_docs_render_pipeline.py"),
        ("docs/assets/showcase-diff.md", "tests/integration/test_profile_reality_check.py"),
    ],
)
def test_docs_and_readme_select_their_real_consumers(path: str, expected_suite: str) -> None:
    """P1-2. Both were classified `inert` while suites read and assert on them, so a
    `docs/HOW-IT-WORKS.md` edit selected zero tests and reported `targeted`."""
    assert classify_path(path, _REPO_ROOT) == CLASS_DOC_WITH_CONSUMERS
    out = select_tests([path], _REPO_ROOT)
    assert out["mode"] == "targeted"
    assert expected_suite in out["node_ids"]


def test_work_docs_and_changelog_stay_inert() -> None:
    """The narrowing must not become 'all markdown runs tests' — the inert class still
    has to hold the paths nothing reads, or the selector degrades to always-full."""
    for path in ("work-docs/PLAN-x.md", "CHANGELOG.md", ".claude/memory/wiki.md"):
        assert classify_path(path, _REPO_ROOT) == CLASS_INERT
    # An ALL-inert change is the one honest empty selection — the backstop above must
    # not swallow it, or every PLAN edit costs a full suite run.
    sel = select_tests(["work-docs/PLAN-x.md"], _REPO_ROOT)
    assert sel["mode"] == "targeted"
    assert sel["node_ids"] == []


def test_an_undeclared_doc_path_forces_full_rather_than_selecting_nothing() -> None:
    """The map is an OPTIMISATION, never a safety boundary.

    A source-scanning detector was tried here first and thrown away: it flagged 24
    suites, nearly all of which merely WRITE a fixture `README.md` into a tmp repo.
    A heuristic that noisy gets weakened until it is vacuous, which is worse than
    absent. So the failure mode is inverted instead — a doc path nobody declared falls
    through to the default arm and forces FULL. Being incomplete costs a full run; it
    can never cost a missed test.
    """
    out = select_tests(["docs/some-doc-nobody-mapped.md"], _REPO_ROOT)
    assert out["mode"] == "full"
    assert out["node_ids"] == []


def test_the_declared_consumers_exist() -> None:
    """A map entry naming a deleted suite hands pytest a node id that cannot collect."""
    declared = {s for suites in DOC_CONSUMING_SUITES.values() for s in suites}
    assert declared, "the map is empty"
    for rel in declared:
        assert (_REPO_ROOT / rel).exists(), f"declared consumer does not exist: {rel}"
