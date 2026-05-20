"""PLAN-fresh-install-p0-calibration end-to-end test.

Verifies the user-facing CLI behavior at the integration boundary:
  1. ``harness-maker make`` on a minimal fresh project emits NO ``[P0]`` lines
     for any INTENDED_P0_SIGNAL (telemetry / ADR / CI / CONTRIBUTING).
  2. The deferral footer appears in stdout when suppression/demotion happens.
  3. ``adr_present`` (formerly P0) appears as ``[P2]`` (demoted, not hidden).

INTEGRATION-gated to match ``tests/integration/test_fresh_install_readiness.py``
convention. Runs ~3 s. Skipping the gate per PLAN's original ADR-005 would
diverge from the sibling test that exercises the same CLI invocation; that
deviation is recorded in the PLAN's ``## 🔍 Plan Validation`` section as a
self-critique adjustment (the convention wins).
"""

from __future__ import annotations

import os
import re

import pytest
from typer.testing import CliRunner

pytestmark = pytest.mark.skipif(
    not os.getenv("INTEGRATION"),
    reason="integration test requires INTEGRATION=1",
)


_runner = CliRunner()


def _invoke_make(project_dir, preset: str = "Production") -> str:
    """Run ``harness-maker make`` and return combined stdout."""
    from harness_maker.cli import app

    old = os.environ.get("HARNESS_MAKER_FREEZE")
    os.environ["HARNESS_MAKER_FREEZE"] = "1"
    try:
        result = _runner.invoke(
            app,
            ["make", str(project_dir), "--autoloop", "--preset", preset],
            catch_exceptions=False,
        )
    finally:
        if old is None:
            os.environ.pop("HARNESS_MAKER_FREEZE", None)
        else:
            os.environ["HARNESS_MAKER_FREEZE"] = old
    assert result.exit_code == 0, (
        f"harness-maker make failed (exit={result.exit_code}):\n{result.output}"
    )
    return result.output


def _seed_fresh_python_project(project_dir) -> None:
    """Minimal Python project — no observability/, no docs/adr/, no .github/workflows/."""
    (project_dir / "pyproject.toml").write_text(
        '[project]\nname = "fresh-fixture"\nversion = "0.0.0"\n',
        encoding="utf-8",
    )
    (project_dir / "CLAUDE.md").write_text(
        "# fresh\n## Tech Stack\nPython\n",
        encoding="utf-8",
    )


def test_fresh_install_no_p0_for_intended_signals(tmp_path) -> None:
    """No [P0] line in stdout mentions telemetry / ADRs / CONTRIBUTING / CI workflow."""
    _seed_fresh_python_project(tmp_path)
    output = _invoke_make(tmp_path, preset="Production")

    p0_lines = [line for line in output.splitlines() if "[P0]" in line]

    forbidden = re.compile(
        r"telemetry|metrics\.jsonl|No ADRs|CONTRIBUTING|ci_workflow|"
        r".github/workflows/ has no",
        re.IGNORECASE,
    )
    offending = [line for line in p0_lines if forbidden.search(line)]
    assert offending == [], (
        "fresh install must not emit [P0] for INTENDED signals; got:\n"
        + "\n".join(offending)
    )


def test_fresh_install_footer_present(tmp_path) -> None:
    """Deferral footer must appear when telemetry/governance items are deferred/demoted."""
    _seed_fresh_python_project(tmp_path)
    output = _invoke_make(tmp_path, preset="Production")
    assert "deferred" in output.lower(), (
        "expected deferral footer in fresh-install output; stdout:\n" + output
    )
    assert "/hm:health" in output


def test_fresh_install_adr_demoted_not_hidden(tmp_path) -> None:
    """ADRs must appear as P2 (demoted), not hidden entirely (ADR-003 contract)."""
    _seed_fresh_python_project(tmp_path)
    output = _invoke_make(tmp_path, preset="Production")
    p2_lines = [line for line in output.splitlines() if "[P2]" in line]
    has_adr_p2 = any(re.search(r"adr|docs/adr", line, re.IGNORECASE) for line in p2_lines)
    assert has_adr_p2, (
        "expected adr_present to appear as P2 (demoted, not hidden); P2 lines:\n"
        + "\n".join(p2_lines)
    )
