"""SPEC-execute-report-short: execute closes short; the land card carries the rest."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests._overhaul_p1_ref import HEAD_SRC, init_project, run_make

_PATHS = {
    "claude": ".claude/commands/hm/execute.md",
    "codex": ".agents/skills/hm-execute/SKILL.md",
}

# Typed from the SPEC's Outcomes and S2/S3: what the DRI must still see before wrapup.
REQUIRED = (
    "at most three lines",
    "`hm check` result",
    "REVIEW path",
    "`unresolved`",
    "P0/P1 `pre-existing`",
    "no other summary",
    "change card",
)


@pytest.fixture(scope="module")
def project(tmp_path_factory: pytest.TempPathFactory) -> Path:
    base = tmp_path_factory.mktemp("exec-report")
    proj = init_project(base / "proj")
    args = ("--autoloop", "--targets", "claude-code,codex", "--preset", "Production")
    proc = run_make(proj, args, src=HEAD_SRC, home=base / "home")
    assert proc.returncode == 0, proc.stderr[-2000:]
    return proj


@pytest.mark.parametrize("runtime", ["claude", "codex"])
def test_ac_001_execute_closes_short(project: Path, runtime: str) -> None:
    text = (project / _PATHS[runtime]).read_text(encoding="utf-8")
    step6 = text[text.index("## Step 6") :]
    close = step6[step6.rindex("`hm check` result") :]  # the closing sentence, not Step 6's rules
    close = close[: close.index("STOP")]
    missing = [p for p in REQUIRED if p not in close]
    assert "Print the phases done" not in text, "the long closing summary is still asked for"
    assert missing == [], missing
