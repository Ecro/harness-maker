"""SPEC-cli-bookkeeping: the CLI does the SPEC bookkeeping the model used to run by hand.

The 2026-11-27 turn-level cost split found that about 80% of hm's output went to running hm's
own procedure. These tests pin the four CLI pieces that take it over (golden rows written into
the test, mark-tested without per-AC flags, finalize, the land manifest) and the stage text
that now calls them.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from harness_maker import check, spec_machine, wrapup_land
from tests.hm_cost_p2_fixture import init_project, mech_ac, param_ac, write_spec

ROWS: list[dict[str, Any]] = [
    {"input": {"s": "1h"}, "expected": 3600},
    {"input": {"s": "bad"}, "expected": "ValueError"},
]
REPO = Path(__file__).resolve().parents[2]
OWN_SPEC = REPO / "specs" / "SPEC-cli-bookkeeping.md"
OWN_YAML = REPO / "specs" / "SPEC-cli-bookkeeping.machine.yaml"


def _hm(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "harness_maker.spec_machine", *args],
        cwd=root, capture_output=True, text=True, check=False, timeout=120,
    )  # fmt: skip


def _rows_text(root: Path) -> str:
    yaml_path = root / "specs" / "SPEC-demo.machine.yaml"
    payload = spec_machine.golden_export(spec_machine.load(yaml_path))
    return spec_machine.golden_inline_text(payload)


# ── AC-001 ──────────────────────────────────────────────────────────────────────────────────


def _golden_project(tmp_path: Path) -> Path:
    root = init_project(tmp_path / "p")
    write_spec(
        root,
        [param_ac("AC-001", ROWS, test_ids=["tests/test_parse.py::test_ac_001_parse"],
                  pending_test=False)],
    )  # fmt: skip
    (root / "tests").mkdir()
    venv_bin = root / ".venv" / "bin"
    venv_bin.mkdir(parents=True)
    wrapper = venv_bin / "python"
    wrapper.write_text(f'#!/bin/sh\nexec "{sys.executable}" "$@"\n')
    wrapper.chmod(0o755)
    return root


def test_ac_001_export_golden_write_puts_rows_in_the_test_file(tmp_path: Path) -> None:
    root = _golden_project(tmp_path)
    target = root / "tests" / "test_parse.py"
    want = _rows_text(root)

    r = _hm(root, "export-golden", "--slug", "demo", "--inline", "--write", "tests/test_parse.py")
    assert r.returncode == 0, r.stderr
    assert target.read_text(encoding="utf-8") == want

    # An old block is replaced in place; every other byte stays.
    prefix = "import pytest\n\n"
    suffix = "\n\ndef test_ac_001_parse():\n    assert True\n"
    stale = want.replace("3600", "3601")
    target.write_text(prefix + stale + suffix, encoding="utf-8")
    r = _hm(root, "export-golden", "--slug", "demo", "--inline", "--write", "tests/test_parse.py")
    assert r.returncode == 0, r.stderr
    assert target.read_text(encoding="utf-8") == prefix + want + suffix

    before = target.read_bytes()
    r = _hm(root, "export-golden", "--slug", "demo", "--inline", "--write", "tests/test_parse.py")
    assert r.returncode == 0, r.stderr
    assert target.read_bytes() == before

    ac = check.run(check.Options(slug="demo", root=root, offline=True))["sections"]["ac"]
    assert ac.get("golden") == "inline", ac
    assert ac.get("golden_drift", {}).get("acs", []) == [], ac


def test_ac_001_write_puts_a_missing_block_above_the_tests(tmp_path: Path) -> None:
    """A parametrize decorator reads the rows at import, so they must sit above the first test."""
    root = _golden_project(tmp_path)
    target = root / "tests" / "test_parse.py"
    head = "import pytest\n\n\n"
    body = "@pytest.mark.parametrize('row', AC_001_ROWS)\ndef test_ac_001_parse(row):\n    pass\n"
    target.write_text(head + body, encoding="utf-8")
    r = _hm(root, "export-golden", "--slug", "demo", "--inline", "--write", "tests/test_parse.py")
    assert r.returncode == 0, r.stderr
    text = target.read_text(encoding="utf-8")
    assert text == head + _rows_text(root) + "\n\n" + body
    assert text.count("AC_001_ROWS = [") == 1


def test_ac_001_write_creates_the_same_text_as_inline_for_several_acs(tmp_path: Path) -> None:
    root = init_project(tmp_path / "p")
    write_spec(root, [param_ac("AC-001", ROWS), param_ac("AC-002", ROWS[:1])])
    target = root / "tests" / "test_x.py"
    r = _hm(root, "export-golden", "--slug", "demo", "--inline", "--write", "tests/test_x.py")
    assert r.returncode == 0, r.stderr
    assert target.read_text(encoding="utf-8") == _rows_text(root)


# ── AC-002 ──────────────────────────────────────────────────────────────────────────────────


def test_ac_002_mark_tested_binds_every_testable_ac_by_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = init_project(tmp_path / "p")
    judgment = mech_ac("AC-003")
    judgment.update(type="judgment", executable_predicate=None, rubric_id="r",
                    judgment_subject_paths=["README.md"])  # fmt: skip
    write_spec(root, [mech_ac("AC-001"), param_ac("AC-002", ROWS), judgment])
    (root / "specs" / "SPEC-demo.md").write_text("# demo\n", encoding="utf-8")
    seen: list[dict[str, list[str]]] = []

    def fake(_y: Path, _m: Path, ids: dict[str, list[str]], **_kw: Any) -> list[str]:
        seen.append(ids)
        return []

    monkeypatch.setattr(spec_machine, "mark_tested", fake)
    monkeypatch.chdir(root)
    assert spec_machine.main(["mark-tested", "--slug", "demo"]) == 0
    assert spec_machine.main(["mark-tested", "--slug", "demo", "--ac", "AC-001"]) == 0
    marked_default, marked_with_ac = set(seen[0]), set(seen[1])
    assert marked_default == {"AC-001", "AC-002"}
    assert "AC-003" not in marked_default
    assert marked_with_ac == {"AC-001"}


def test_ac_002_default_leaves_an_ac_with_no_test_pending(tmp_path: Path) -> None:
    """One AC whose test comes in a later phase must not block binding the others."""
    root = init_project(tmp_path / "p")
    write_spec(root, [mech_ac("AC-001"), mech_ac("AC-002")])
    yaml_path = root / "specs" / "SPEC-demo.machine.yaml"
    md_path = root / "specs" / "SPEC-demo.md"
    found = {"AC-001": ["tests/test_x.py::test_ac_001_x"]}
    skipped: list[str] = []
    errors = spec_machine._mark_tested_locked(
        yaml_path, md_path, {"AC-001": [], "AC-002": []}, validate_after=False,
        discovered=found, skipped=skipped,
    )  # fmt: skip
    assert errors == []
    assert skipped == ["AC-002"]
    by_id = {ac.id: ac for ac in spec_machine.load(yaml_path).ac}
    assert by_id["AC-001"].test_ids == found["AC-001"]
    assert not by_id["AC-001"].pending_test
    assert by_id["AC-002"].pending_test
    # With nothing to bind at all it still refuses, and an explicit --ac never skips.
    variants: tuple[dict[str, Any], ...] = ({"skipped": []}, {})
    for kwargs in variants:
        before = yaml_path.read_bytes()
        errs = spec_machine._mark_tested_locked(
            yaml_path, md_path, {"AC-002": []}, validate_after=False, discovered=found, **kwargs
        )
        assert errs
        assert yaml_path.read_bytes() == before


# ── AC-003 / AC-004 ─────────────────────────────────────────────────────────────────────────


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, timeout=60)


def _spec_project(tmp_path: Path, *, irr: bool = True, break_md: bool = False) -> Path:
    """This task's own SPEC, unstamped, in a fresh repo: real content that passes check."""
    root = tmp_path / "p"
    (root / "specs").mkdir(parents=True)
    _git(root, "init", "-q")
    _git(root, "config", "user.name", "Tester")
    _git(root, "config", "user.email", "t@example.invalid")
    md = OWN_SPEC.read_text(encoding="utf-8").replace("status: approved", "status: draft")
    md = md.replace("task_slug: cli-bookkeeping", "task_slug: demo")
    if break_md:
        md = md.replace("### AC-007:", "### Removed:")
    (root / "specs" / "SPEC-demo.md").write_text(md, encoding="utf-8")
    model = spec_machine.load(OWN_YAML)
    model.approval = None
    model.spec_slug = "demo"
    for ac in model.ac:  # the SPEC as the spec stage leaves it: no test bound yet
        ac.test_ids, ac.pending_test = [], True
    if not irr:
        model.irreversible_decisions = []
    spec_machine._dump_machine_yaml(root / "specs" / "SPEC-demo.machine.yaml", model)
    return root


def _status(root: Path) -> str:
    text = (root / "specs" / "SPEC-demo.md").read_text(encoding="utf-8")
    m = re.search(r"^status: (\S+)$", text, re.M)
    assert m, text[:200]
    return m.group(1)


def _snapshot(root: Path) -> dict[str, bytes]:
    return {p.name: p.read_bytes() for p in sorted((root / "specs").iterdir())}


def test_ac_003_finalize_without_a_flag_is_the_check(tmp_path: Path) -> None:
    root = _spec_project(tmp_path)
    paths = ["--yaml", "specs/SPEC-demo.machine.yaml", "--md", "specs/SPEC-demo.md"]
    before = _snapshot(root)
    chk = _hm(root, "check", "--all", *paths, "--strictness", "warn")
    fin = _hm(root, "finalize", "--slug", "demo", "--strictness", "warn")
    check_keys = json.loads(chk.stdout)
    finalize_out = json.loads(fin.stdout)
    assert set(check_keys) <= set(finalize_out), (chk.stdout, fin.stdout)
    assert {"approval", "status"} <= set(finalize_out)
    assert fin.returncode == chk.returncode == 0, fin.stderr
    assert _snapshot(root) == before


def test_ac_003_finalize_reports_a_failing_check_with_its_exit(tmp_path: Path) -> None:
    root = _spec_project(tmp_path, break_md=True)
    paths = ["--yaml", "specs/SPEC-demo.machine.yaml", "--md", "specs/SPEC-demo.md"]
    chk = _hm(root, "check", "--all", *paths, "--strictness", "warn")
    fin = _hm(root, "finalize", "--slug", "demo", "--strictness", "warn")
    assert chk.returncode == fin.returncode == 1
    assert set(json.loads(chk.stdout)) <= set(json.loads(fin.stdout))


def test_ac_004_finalize_approve_stamps_and_sets_status(tmp_path: Path) -> None:
    ok = _spec_project(tmp_path / "ok")
    r = _hm(ok, "finalize", "--slug", "demo", "--approve")
    assert r.returncode == 0, r.stderr
    assert spec_machine.approval_state(ok, "demo").state == "approved"
    assert _status(ok) == "approved"
    assert json.loads(r.stdout)["approval"]["state"] == "approved"
    assert json.loads(r.stdout)["status"] == "approved"


def test_ac_004_finalize_exempt_and_its_refusal(tmp_path: Path) -> None:
    ok2 = _spec_project(tmp_path / "ok2", irr=False)
    r = _hm(ok2, "finalize", "--slug", "demo", "--exempt")
    assert r.returncode == 0, r.stderr
    assert spec_machine.approval_state(ok2, "demo").state == "exempt"
    assert _status(ok2) == "approved"

    with_irr = _spec_project(tmp_path / "irr")
    before = _snapshot(with_irr)
    r = _hm(with_irr, "finalize", "--slug", "demo", "--exempt")
    assert r.returncode != 0
    assert _snapshot(with_irr) == before


def test_ac_004_finalize_on_a_failing_check_stamps_nothing(tmp_path: Path) -> None:
    bad = _spec_project(tmp_path, break_md=True)
    before = _snapshot(bad)
    r = _hm(bad, "finalize", "--slug", "demo", "--approve")
    assert r.returncode == 1
    assert _snapshot(bad) == before
    assert spec_machine.approval_state(bad, "demo").state == "missing"
    assert _status(bad) == "draft"


def test_ac_004_finalize_never_stamps_a_spec_whose_status_it_cannot_set(tmp_path: Path) -> None:
    root = _spec_project(tmp_path)
    md = root / "specs" / "SPEC-demo.md"
    md.write_text(md.read_text(encoding="utf-8").replace("status: draft\n", ""), encoding="utf-8")
    r = _hm(root, "finalize", "--slug", "demo", "--approve")
    assert r.returncode == 1
    assert "status" in r.stderr
    assert spec_machine.approval_state(root, "demo").state == "missing"


# ── AC-005 ──────────────────────────────────────────────────────────────────────────────────


def test_ac_005_wrapup_land_has_a_default_manifest(monkeypatch: pytest.MonkeyPatch) -> None:
    assert wrapup_land.default_manifest("s") == (
        ["work-docs/PLAN-s.md"],
        [
            ".claude/memory/",
            "work-docs/REVIEW-s-*.md",
            "work-docs/RESEARCH-s.md",
            "specs/SPEC-s.md",
            "specs/SPEC-s.golden.json",
            "specs/SPEC-s.machine.yaml",
        ],
    )
    seen: list[tuple[list[str], list[str]]] = []

    def fake_run(args: Any) -> tuple[int, dict[str, Any]]:
        seen.append((list(args.required), list(args.optional)))
        return 0, {}

    monkeypatch.setattr(wrapup_land, "run", fake_run)
    base = ["--worktree", "/w", "--base", "/b", "--slug", "s", "--message-file", "/m"]
    assert wrapup_land.main(base) == 0
    assert wrapup_land.main([*base, "--required", "x.md"]) == 0
    assert seen[0] == wrapup_land.default_manifest("s")
    assert seen[1] == (["x.md"], [])


# ── AC-006 ──────────────────────────────────────────────────────────────────────────────────

# execute keys re-pinned by SPEC-execute-report-short's measured growth (+93: the three-line closing
# report that names what the DRI must still see); the other stages are untouched.
# spec and execute keys re-pinned by SPEC-test-shape-rules' measured growth (spec +97: the
# golden-row and Constraint rules; execute +43: paste rows into an existing same-column list).
MAIN_CHARS_PATH = REPO / "tests" / "fixtures" / "cli_bookkeeping" / "main_chars.json"


def render_stages(tmp: Path) -> dict[str, str]:
    """Both presets at their defaults, both targets: `<preset>:<stage>:<claude|codex>` -> text."""
    from harness_maker.interview import _build_answers
    from harness_maker.models import Preset, ProjectProfile, Target
    from harness_maker.render import DEFAULT_FREEZE_TIME, render
    from harness_maker.synthesize import synthesize
    from tests.structural.conftest import pin_install_ref

    out: dict[str, str] = {}
    for preset in (Preset.SIDE, Preset.PRODUCTION):
        claude = tmp / preset.value / ".claude"
        answers = _build_answers(
            locale="en", targets=[Target.CLAUDE_CODE, Target.CODEX], preset=preset
        )
        with pytest.MonkeyPatch.context() as mp:
            pin_install_ref(mp)
            render(synthesize(ProjectProfile(), answers, preset=preset), claude,
                   freeze_time=DEFAULT_FREEZE_TIME)  # fmt: skip
        for stage in ("spec", "execute", "wrapup"):
            out[f"{preset.value}:{stage}:claude"] = (
                claude / "commands" / "hm" / f"{stage}.md"
            ).read_text(encoding="utf-8")
            out[f"{preset.value}:{stage}:codex"] = (
                claude.parent / ".agents" / "skills" / f"hm-{stage}" / "SKILL.md"
            ).read_text(encoding="utf-8")
    return out


def _steps_6_7(wrapup: str) -> str:
    m = re.search(r"^## Steps 6 → 7\.6.*?(?=^## )", wrapup, re.M | re.S)
    assert m, "wrapup has no Steps 6 → 7.6 section"
    return m.group(0)


@pytest.fixture(scope="module")
def rendered(tmp_path_factory: pytest.TempPathFactory) -> dict[str, str]:
    return render_stages(tmp_path_factory.mktemp("stages"))


@pytest.mark.parametrize("preset", ["Side", "Production"])
@pytest.mark.parametrize("target", ["claude", "codex"])
def test_ac_006_the_stages_call_the_cli(rendered: dict[str, str], preset: str, target: str) -> None:
    main_chars: dict[str, int] = json.loads(MAIN_CHARS_PATH.read_text(encoding="utf-8"))
    spec, execute, wrapup = (
        rendered[f"{preset}:{s}:{target}"] for s in ("spec", "execute", "wrapup")
    )
    assert "spec_machine finalize" in spec
    assert "spec_machine check" not in spec
    assert "spec_machine approve" not in spec
    assert "--write" in execute
    # mark-tested binds every AC itself; `--ac AC-NNN` now appears only in export-golden's
    # one-AC write (SPEC-behaviour-named-tests), so the pin names mark-tested.
    assert not re.search(r"mark-tested[^`\n]*--ac", execute)
    assert "--required" not in wrapup
    assert "approval-status" not in _steps_6_7(wrapup)
    for stage, text in (("spec", spec), ("execute", execute), ("wrapup", wrapup)):
        key = f"{preset}:{stage}:{target}"
        assert len(text) <= main_chars[key], (key, len(text), main_chars[key])
