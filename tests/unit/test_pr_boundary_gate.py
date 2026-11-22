"""SPEC-pr-boundary-gate: boundary suite in CI before merge, DRI block on the PR template."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
CI_YML = ROOT / ".github" / "workflows" / "ci.yml"
TEMPLATE = ROOT / ".github" / "PULL_REQUEST_TEMPLATE.md"
CLAUDE_MD = ROOT / "CLAUDE.md"

FIVE_LABELS = [
    "Behaviour change:",
    "Host check:",
    "Your decision:",
    "Ships a release on merge:",
    "Understanding delta:",
]


def _workflow() -> dict[Any, Any]:
    data = yaml.safe_load(CI_YML.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def test_ac_001_ci_runs_boundary_blocking() -> None:
    wf = _workflow()
    # PyYAML reads the bare key `on` as the boolean True.
    triggers = wf["on"] if "on" in wf else wf[True]
    assert "pull_request" in triggers
    assert "main" in triggers["push"]["branches"]

    job = wf["jobs"]["boundary"]
    assert "continue-on-error" not in job
    steps = job["steps"]
    checkout = next(s for s in steps if str(s.get("uses", "")).startswith("actions/checkout@"))
    assert checkout["with"]["fetch-depth"] == 0
    run = [s for s in steps if "tests/integration/test_boundary_*.py" in str(s.get("run", ""))]
    assert len(run) == 1
    step = run[0]
    assert "uv run pytest" in step["run"]
    assert step["env"]["INTEGRATION"] == "1"
    assert "continue-on-error" not in step


def test_ac_002_pr_template_dri_block() -> None:
    text = TEMPLATE.read_text(encoding="utf-8")
    body = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    headings = re.findall(r"^## (.+)$", body, flags=re.M)
    assert headings[0].strip() == "For the DRI"
    assert headings.index("Summary") > 0

    block = body.split("## For the DRI", 1)[1].split("\n## ", 1)[0]
    items = [ln.strip()[2:] for ln in block.splitlines() if ln.strip().startswith("- ")]
    assert len(items) == 5
    for item, label in zip(items, FIVE_LABELS, strict=True):
        assert item.startswith(label), (item, label)


def test_ac_003_claude_md_describes_gate() -> None:
    text = CLAUDE_MD.read_text(encoding="utf-8")
    assert "advisory 로 실행 권장" not in text
    # The Maker test file is also named in the World model section, so look only inside
    # the release section for the gate's description.
    release = text.split("## 릴리스 절차", 1)[1].split("\n## ", 1)[0]
    assert "`boundary`" in release
    assert "test_boundary_maker_default_permissions.py" in release
    assert "Host check:" in release
