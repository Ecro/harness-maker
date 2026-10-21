"""SPEC-hm-cost-p2 AC-003/004/005/007/008/010: what the rendered stages say, and the land."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from harness_maker import wrapup_land
from harness_maker.models import HarnessConfig
from harness_maker.render import _make_env
from harness_maker.spec_machine import IRREVERSIBLE_CATEGORIES
from harness_maker.synthesize import _HARNESS_MAKER_PKG_ROOT
from tests.hm_cost_p2_fixture import init_project, mech_ac, write_spec


def _render(stage: str, *, is_codex: bool = False, second_brain: bool = True) -> str:
    cfg: dict[str, Any] = HarnessConfig().model_dump(mode="json")
    cfg["second_brain"] = {**(cfg.get("second_brain") or {}), "enabled": second_brain}
    return (
        _make_env()
        .get_template(f"stages/{stage}.md.j2")
        .render(
            stage=stage, workflow_context="", project_name="", feature="", config=cfg,
            harness_maker_src_path=_HARNESS_MAKER_PKG_ROOT, is_codex=is_codex,
        )
    )  # fmt: skip


def test_ac_003_execute_reads_golden_json() -> None:
    text = _render("execute")
    for banned in ("import harness_maker", "from harness_maker", "load_golden_table"):
        assert banned not in text
    assert "golden.json" in text
    assert "export-golden" in text


def test_ac_003_red_without_harness_maker(tmp_path: Path) -> None:
    """A test written as the render says (stdlib JSON) is RED with harness_maker unimportable."""
    proj = tmp_path / "proj"
    (proj / "specs").mkdir(parents=True)
    (proj / "tests").mkdir()
    (proj / "specs" / "SPEC-demo.golden.json").write_text(
        json.dumps({"AC-001": [{"input": {"s": "1h"}, "expected": 3600}]})
    )
    (proj / "conftest.py").write_text("import sys\nsys.modules['harness_maker'] = None\n")
    (proj / "tests" / "test_ac.py").write_text(
        "import json\nfrom pathlib import Path\n\nimport pytest\n\n"
        "ROWS = json.loads((Path(__file__).parents[1] / 'specs' / 'SPEC-demo.golden.json')"
        ".read_text())['AC-001']\n\n\n"
        "@pytest.mark.parametrize('row', ROWS)\n"
        "def test_ac_001_parse(row):\n"
        "    from demo.parse import parse\n\n"
        "    assert parse(**row['input']) == row['expected']\n"
    )
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "tests/test_ac.py"],
        cwd=proj, capture_output=True, text=True, timeout=120, check=False,
    )  # fmt: skip
    assert "1 failed" in proc.stdout, proc.stdout
    assert "error" not in proc.stdout.lower().split("short test summary")[-1].replace(
        "modulenotfounderror", ""
    )


def test_property_ac_needs_no_new_dependency() -> None:
    """PLAN ADR-008: three bench runs stalled after recording Hypothesis as an IRR in execute."""
    for is_codex in (False, True):
        text = _render("execute", is_codex=is_codex)
        assert "no Hypothesis: a seeded stdlib `random` loop; never add it" in text


def _listed(text: str) -> set[str]:
    """Quoted strings on every line that lists the categories."""
    lines = [ln for ln in text.splitlines() if '"data migration"' in ln]
    assert lines, "no line lists the irreversible categories"
    return {q for ln in lines for q in re.findall(r'"([^"]+)"', ln)}


_ANY = set(IRREVERSIBLE_CATEGORIES)


def test_ac_004_categories_verbatim() -> None:
    for stage in ("spec", "execute"):
        text = _render(stage)
        for c in IRREVERSIBLE_CATEGORIES:
            assert f'"{c}"' in text, (stage, c)
        assert _listed(text) == _ANY, stage


def test_ac_005_spec_step5_no_approval_status() -> None:
    text = _render("spec")
    step5 = text.split("## Step 5", 1)[1]
    assert "approval-status" not in step5
    assert "approve" in step5


def _edit_rule(text: str, tool: str) -> bool:
    for line in text.splitlines():
        if all(w in line for w in ("SPEC", "machine.yaml", "PLAN", "REVIEW", tool)) and (
            "whole-file rewrite" in line
        ):
            return True
    return False


def test_ac_007_edit_in_place() -> None:
    for stage in ("spec", "execute"):
        assert _edit_rule(_render(stage), "Edit"), stage
        assert _edit_rule(_render(stage, is_codex=True), "apply_patch"), stage


def test_ac_008_short_plan(tmp_path: Path) -> None:
    text = _render("execute")
    assert "one phase" in text
    assert "short PLAN" in text
    assert "each phase line has all four fields" in text
    assert "`### Do not change` is non-empty" in text
    staged = _land(tmp_path, short_plan=True)
    assert "work-docs/PLAN-demo.md" in staged


def test_ac_010_wrapup_lands_golden_json(tmp_path: Path) -> None:
    assert "specs/SPEC-demo.golden.json" in wrapup_land.derive_deliverable_globs("demo")
    assert "--optional specs/SPEC-<slug>.golden.json" in _render("wrapup")
    # --manifest-only: with the worktree sweep on, any untracked file lands without the glob.
    staged = _land(tmp_path, short_plan=False, manifest_only=True)
    assert "specs/SPEC-demo.golden.json" in staged


SHORT_PLAN = """---
type: plan
task_slug: demo
status: planning
created: 2026-10-21
spec: "[[SPEC-demo]]"
summary: one-phase fix
---

Short PLAN: one phase is enough because the change is one function.

1. **P1** — scope: parse.py · exit: `pytest tests/test_parse.py` · risk: low · rollback: revert.

## 🚧 Contract Boundaries

### Do not change
- none — this task has no contract boundaries
"""


def _land(tmp_path: Path, *, short_plan: bool, manifest_only: bool = False) -> list[str]:
    """Run `wrapup_land` on a non-isolated checkout (worktree == base) and list the commit."""
    root = init_project(tmp_path / "p")
    write_spec(root, [mech_ac("AC-001")])
    (root / "specs" / "SPEC-demo.md").write_text("# SPEC demo\n")
    (root / "specs" / "SPEC-demo.golden.json").write_text("{}\n")
    (root / "work-docs").mkdir()
    (root / "work-docs" / "PLAN-demo.md").write_text(SHORT_PLAN if short_plan else "# PLAN\n")
    message = root / "msg.txt"
    message.write_text("feat: demo\n\nUnderstanding:\n- none\n")
    code = wrapup_land.main(
        [
            "--worktree", str(root), "--base", str(root), "--slug", "demo",
            "--message-file", str(message), "--required", "work-docs/PLAN-demo.md",
            "--optional", "specs/SPEC-demo.md", "--optional", "specs/SPEC-demo.machine.yaml",
            *(["--manifest-only"] if manifest_only else []),
        ]
    )  # fmt: skip
    assert code == 0
    out = subprocess.run(
        ["git", "-C", str(root), "show", "--name-only", "--format=", "HEAD"],
        capture_output=True, text=True, timeout=30, check=True,
    ).stdout  # fmt: skip
    return out.split()
