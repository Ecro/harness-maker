"""SPEC-review-measurement-fixes AC-001..008: severity measurement, execute rules, retirement."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from harness_maker import check, command_registry, review_effect
from tests._overhaul_p1_ref import HEAD_SRC, REPO_ROOT, init_project, run_make

GOLDEN: dict[str, list[dict[str, Any]]] = json.loads(
    (REPO_ROOT / "specs" / "SPEC-review-measurement-fixes.golden.json").read_text("utf-8")
)
_ARGS = ("--autoloop", "--targets", "claude-code,codex", "--locale", "en")
EXECUTE = (".claude/commands/hm/execute.md", ".agents/skills/hm-execute/SKILL.md")
CODE_REVIEWER = (".claude/agents/code-reviewer.md", ".codex/agents/code-reviewer.toml")
SO_SKILL = ".claude/skills/second-opinion-gate/SKILL.md"


def _ids(ac: str) -> list[str]:
    return [f"{ac}-{i}" for i in range(len(GOLDEN[ac]))]


@pytest.fixture(scope="module")
def renders(tmp_path_factory: pytest.TempPathFactory) -> list[Path]:
    projects = []
    for preset in ("Side", "Production"):
        base = tmp_path_factory.mktemp(f"rmf-{preset}")
        project = init_project(base / "proj")
        proc = run_make(project, (*_ARGS, "--preset", preset), src=HEAD_SRC, home=base / "home")
        assert proc.returncode == 0, proc.stderr[-2000:]
        projects.append(project)
    return projects


@pytest.fixture(scope="module")
def rendered_execute_bodies(renders: list[Path]) -> list[str]:
    return [(p / rel).read_text("utf-8") for p in renders for rel in EXECUTE]


def _step6(body: str) -> str:
    return body.split("## Step 6")[1]


def _bind(body: str) -> str:
    return body.split("**Bind, then gate**")[1].split("## Step 4")[0]


@pytest.mark.parametrize("row", GOLDEN["AC-001"], ids=_ids("AC-001"))
def test_ac_001_word_severities_map_to_p_scale(row: dict[str, Any]) -> None:
    sev = row["input"]["severity"]
    table = (
        "## Findings\n\n| id | severity | disposition |\n|---|---|---|\n"
        f"| F1 | {sev} | accepted |\n"
    )
    parsed = review_effect.parse_review(table)
    exp = row["expected"]
    assert parsed.status == "parsed"
    assert list(parsed.counts) == [exp["sev"]]
    assert parsed.severe_accepted == exp["severe_accepted"]
    assert parsed.unrecognized_n == exp["unrecognized_n"]


def test_ac_002_execute_names_p_scale(rendered_execute_bodies: list[str]) -> None:
    assert all("P0–P3" in _step6(body) for body in rendered_execute_bodies)


def test_ac_003_execute_caps_failing_check(rendered_execute_bodies: list[str]) -> None:
    assert all("third exit 1" in _bind(body) for body in rendered_execute_bodies)


def test_ac_004_execute_keeps_pre_existing_out_of_loop(rendered_execute_bodies: list[str]) -> None:
    for body in rendered_execute_bodies:
        s = _step6(body)
        assert "`pre-existing`" in s
        assert "not fixed" in s


def test_ac_005_execute_states_flaky_rule(rendered_execute_bodies: list[str]) -> None:
    for body in rendered_execute_bodies:
        assert "flaky" in body
        assert "ADR" in body.split("flaky")[1][:300]


@pytest.mark.parametrize("row", GOLDEN["AC-006"], ids=_ids("AC-006"))
def test_ac_006_check_accepts_pre_existing(row: dict[str, Any], tmp_path: Path) -> None:
    disp, auth = row["input"]["disposition"], row["input"]["authority"]
    (tmp_path / "work-docs").mkdir()
    (tmp_path / "work-docs" / "REVIEW-x-2026-11-21.md").write_text(
        "# R\n\n## Findings\n\n| id | severity | file:line | finding | disposition | authority |\n"
        f"|---|---|---|---|---|---|\n| F1 | P1 | a.py:1 | bug | {disp} | {auth} |\n",
        encoding="utf-8",
    )
    section = check.review_section(tmp_path, "x", {})
    assert section.body["ok"] is row["expected"]["ok"]


def test_ac_007_code_reviewer_can_mark_pre_existing(renders: list[Path]) -> None:
    for project in renders:
        for rel in CODE_REVIEWER:
            assert "pre-existing" in (project / rel).read_text("utf-8")


@pytest.fixture(scope="module")
def rendered_second_opinion_skill(tmp_path_factory: pytest.TempPathFactory) -> str:
    """The skill renders only with `second_opinion.models` set, so turn it on and `--update`."""
    base = tmp_path_factory.mktemp("rmf-so")
    project = init_project(base / "proj")
    home = base / "home"
    proc = run_make(project, (*_ARGS, "--preset", "Side"), src=HEAD_SRC, home=home)
    assert proc.returncode == 0, proc.stderr[-2000:]
    cfg = project / ".claude" / "harness.yaml"
    _, front, body = cfg.read_text("utf-8").split("---\n", 2)
    data = yaml.safe_load(body)
    data.setdefault("second_opinion", {})["models"] = ["codex"]
    cfg.write_text(f"---\n{front}---\n{yaml.safe_dump(data, sort_keys=False)}", encoding="utf-8")
    proc = run_make(project, ("--update",), src=HEAD_SRC, home=home)
    assert proc.returncode == 0, proc.stderr[-2000:]
    return (project / SO_SKILL).read_text("utf-8")


def test_ac_008_two_pass_review_is_gone(rendered_second_opinion_skill: str) -> None:
    assert importlib.util.find_spec("harness_maker.two_pass_review") is None
    assert "two_pass_review" not in command_registry.MODULES
    assert "two_pass_review" not in rendered_second_opinion_skill
