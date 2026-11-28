"""SPEC-test-shape-rules: golden rows are call -> return value; lists grow; diff rules are reviewed.

After SPEC-behaviour-named-tests the evidence judge still ruled hm's tests less maintainable 9-15.
Three test-side causes were confirmed by counterfactual (hm code kept, only test text edited):
golden tables over CLI output / call scripts / one case, a parallel table beside an existing
parametrize, and a test that polices the change itself. These tests pin the row print used to grow
an existing list and the stage and reviewer sentences that steer the model away from the three.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

from harness_maker.models import HarnessConfig
from harness_maker.render import _make_env
from tests.hm_cost_p2_fixture import init_project, mech_ac, param_ac, write_spec
from tests.unit.test_behaviour_named_tests import EXECUTE_PHRASES
from tests.unit.test_hm_cost_p2_templates import _render

ROWS: list[dict[str, Any]] = [
    {"input": {"seconds": 5430, "max_units": 1}, "expected": "2h"},
    {"input": {"seconds": 3601, "max_units": 2}, "expected": "1h"},
]
OTHER_ROWS: list[dict[str, Any]] = [{"input": {"seconds": 0}, "expected": "0s"}]
PRINTED = '    (5430, 1, "2h"),\n    (3601, 2, "1h"),\n'
EXTEND_PHRASES = (
    "already parametrizes with the same columns",
    "prints into that list",
    "never type the rows",
)
SPEC_PHRASES = (
    "A golden table maps one function's arguments to its return value",
    "printed output, exit code, call sequence or lone case is a mechanical AC too",
    "A rule about the change itself (files touched, no secret committed) is a Constraint for"
    " the review, not an AC.",
    "computed at spec time by running the unchanged code",
)
REVIEWER_PHRASE = "the SPEC's intent or its Constraints"


def _cli(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "harness_maker.spec_machine", *args],
        cwd=root, capture_output=True, text=True, check=False, timeout=60,
    )  # fmt: skip


def test_export_golden_prints_one_acs_rows_for_an_existing_list(tmp_path: Path) -> None:
    root = init_project(tmp_path / "p")
    write_spec(root, [param_ac("AC-001", ROWS), param_ac("AC-002", OTHER_ROWS), mech_ac("AC-003")])
    tree = sorted(p.relative_to(root) for p in root.rglob("*") if ".git" not in p.parts)
    base = ("export-golden", "--inline", "--slug", "demo")
    r = _cli(root, *base, "--ac", "AC-001")
    assert (r.returncode, r.stdout) == (0, PRINTED), r.stderr
    for ac in ("AC-003", "AC-009"):  # mechanical, unknown
        r = _cli(root, *base, "--ac", ac)
        assert (r.returncode, r.stdout) == (1, ""), (ac, r.stderr)
    r = _cli(root, *base, "--ac", "AC-001", "--name", "X")  # a name needs --write
    assert r.returncode == 2, r.stdout + r.stderr
    assert sorted(p.relative_to(root) for p in root.rglob("*") if ".git" not in p.parts) == tree


def test_export_golden_print_refuses_a_spec_with_no_parametric_ac(tmp_path: Path) -> None:
    root = init_project(tmp_path / "p")
    write_spec(root, [mech_ac("AC-001")])
    r = _cli(root, "export-golden", "--inline", "--slug", "demo", "--ac", "AC-001")
    assert (r.returncode, r.stdout) == (1, ""), r.stderr


def test_execute_grows_an_existing_parametrize_before_writing_a_block() -> None:
    for is_codex in (False, True):
        text = _render("execute", is_codex=is_codex)
        for phrase in (*EXTEND_PHRASES, *EXECUTE_PHRASES):
            assert phrase in text, (is_codex, phrase)
        assert text.index("already parametrizes") < text.index("--ac AC-NNN --name")


def test_spec_keeps_golden_rows_to_return_values_and_diff_rules_out_of_acs() -> None:
    for is_codex in (False, True):
        text = _render("spec", is_codex=is_codex)
        for phrase in SPEC_PHRASES:
            assert phrase in text, (is_codex, phrase)
        assert "it is parametric" not in text


def test_reviewer_checks_spec_constraints() -> None:
    cfg = HarnessConfig().model_dump(mode="json")
    body = (
        _make_env()
        .get_template("agents/code-reviewer_body.md.j2")
        .render(config=cfg, communication_variant="full", is_codex=False)
    )
    assert REVIEWER_PHRASE in body
