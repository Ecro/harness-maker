"""Phase 4 — the four-way test-selection classifier (PLAN-workflow-step-audit ADR-008).

The interview locked "any changed file with no test hint → that phase runs the full
suite". Both second-opinion models then observed that `build_test_hints()` skips every
file whose suffix is not `.py` (`test_dep_map.py:109-110`), so in this repo — where most
changes are `.j2` templates, markdown and config — that rule selects FULL essentially
always: machinery added, cost preserved.

ADR-008 keeps what the locked rule protects (a source file with no known test must never
be silently untested) and sharpens the predicate into four classes. The property that
matters most here is that the classifier is **total**: the validator caught a first
version that defaulted only *out-of-root* paths, leaving in-root non-matches
(`pyproject.toml`, `uv.lock`, `.github/workflows/*.yml`, `.claude/harness.yaml`)
selecting **zero** tests — trading an always-FULL bug for a sometimes-NONE bug, which is
strictly weaker than today. Every test below that names a concrete path is aimed at that
arm.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from harness_maker.test_dep_map import (
    CLASS_INERT,
    CLASS_RENDER_AFFECTING,
    CLASS_SOURCE_WITH_HINTS,
    CLASS_SOURCE_WITHOUT_HINTS,
    RENDER_AFFECTING_SUITES,
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
        "docs/reference/autoloop-pattern.md",
        "README.md",
        "CHANGELOG.md",
    ],
)
def test_inert_paths_are_inert(rel: str) -> None:
    assert _classify(rel) == CLASS_INERT


def test_a_markdown_only_change_selects_neither_tests_nor_full() -> None:
    sel = select_tests(["work-docs/PLAN-x.md", ".claude/memory/wiki.md"], _REPO_ROOT)
    assert sel["mode"] == "targeted", sel
    assert sel["node_ids"] == [], sel


# ── the default arm — the branch whose omission the validator caught ──────────


@pytest.mark.parametrize(
    "rel",
    [
        "pyproject.toml",
        "uv.lock",
        ".github/workflows/ci.yml",
        "tests/fixtures/stop_payload_wsl2.json",
        ".claude/harness.yaml",
        "../outside-the-root/thing.py",
        "Makefile",
        "src/harness_maker/py.typed",
    ],
)
def test_an_unmatched_path_falls_to_full_not_to_zero_tests(rel: str) -> None:
    """`.claude/harness.yaml` is the sharpest of these: it drives every render, so
    classifying it inert because it is not `.py` would skip the render suites on a
    config change. A lockfile bump selecting zero tests would be strictly weaker than
    today's always-run-everything."""
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
    sel = select_tests(
        ["work-docs/PLAN-x.md", "src/harness_maker/templates/stages/verify.md.j2", "uv.lock"],
        _REPO_ROOT,
    )
    assert sel["mode"] == "full", sel
    assert "uv.lock" in sel["reason"]


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

    rc = main(["--root", str(_REPO_ROOT), "--changed-file", "uv.lock"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["mode"] == "full"
    assert "uv.lock" in payload["reason"]


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
