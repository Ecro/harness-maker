"""E2E — /hm:verify CLI against engineered dashboard fixtures.

Covers the verify Check 3 (structural delta) contract per
PLAN-health-consolidation ADR-002 / ADR-004 (amended by ADR-007 in 0.22.3
which removed the former Check 4 / external_risks layer):

  * Engineered delta cases (PASS / FAIL for Check 3).
  * Missing baseline → no-baseline PASS.
  * Pre-0.13.0 single-`Health:` scalar schema → no-baseline PASS.
  * Personalization section present → ignored (never gates).

All invocations go through the real CLI via ``subprocess.run`` so the test
exercises the same surface a CI pipeline or autoloop driver would.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXED_TS = "2026-05-17T12:00:00+00:00"


def _run_verify(
    target: Path,
    *,
    prior: Path | None = None,
    force: bool = False,
    reason: str | None = None,
) -> subprocess.CompletedProcess[str]:
    """Invoke ``harness-maker verify`` with a frozen timestamp."""
    cmd = [
        "uv",
        "run",
        "python",
        "-m",
        "harness_maker.cli",
        "verify",
        str(target),
    ]
    if prior is not None:
        cmd.extend(["--prior-dashboard", str(prior)])
    if force:
        cmd.append("--force")
    if reason is not None:
        cmd.extend(["--reason", reason])
    env = {
        "HARNESS_MAKER_VERIFY_TIMESTAMP": FIXED_TS,
    }
    # Inherit PATH + minimal env so `uv` resolves the project venv.
    import os

    inherited = {
        k: os.environ[k]
        for k in ("PATH", "HOME", "USER", "VIRTUAL_ENV", "UV_PROJECT_ENVIRONMENT")
        if k in os.environ
    }
    return subprocess.run(  # noqa: S603
        cmd,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
        env={**inherited, **env},
    )


def _write_dashboard(
    target: Path,
    *,
    structural_score: int,
    personalization_composite: int = 50,
    personalization_tier: str = "silver",
) -> Path:
    """Write a valid 0.22.3 (2-section) dashboard.md."""
    obs = target / ".claude" / "observability"
    obs.mkdir(parents=True, exist_ok=True)
    lines = [
        "---",
        "generated_by: harness-maker",
        f"generated_at: {FIXED_TS}",
        "---",
        "# Health",
        "",
        "## Structural",
        f"score: {structural_score} / 100",
        "signals_failed: []",
        "",
        "## Personalization",
        f"composite: {personalization_composite} / 100",
        f"tier: {personalization_tier}",
        'layers: {"l1_conversion": 0.5, "l2_stability": 0.5, "l3_cadence": 0.5}',
        "action_items: []",
        "",
    ]
    path = obs / "dashboard.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _write_old_schema_dashboard(target: Path, score: int) -> Path:
    """Write a pre-0.13.0 single-scalar dashboard (lacks our frontmatter)."""
    obs = target / ".claude" / "observability"
    obs.mkdir(parents=True, exist_ok=True)
    path = obs / "dashboard.md"
    path.write_text(
        f"# Health\n\n**Composite:** {score} / 100\nHealth: {score}\n",
        encoding="utf-8",
    )
    return path


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


def _expected_jsonl_path(target: Path) -> Path:
    # FIXED_TS is "2026-05-17T..." so the date stamp is 2026-05-17.
    return target / ".claude" / "observability" / "verify-2026-05-17.jsonl"


def _checks_by_id(record: dict[str, object]) -> dict[int, dict[str, object]]:
    checks = record["checks"]
    assert isinstance(checks, list)
    by_id: dict[int, dict[str, object]] = {}
    for c in checks:
        assert isinstance(c, dict)
        cid = c["id"]
        assert isinstance(cid, int)
        by_id[cid] = c
    return by_id


# ──────────────────────────────────────────────────────────────────────────────
# Engineered deltas — Check 3
# ──────────────────────────────────────────────────────────────────────────────


def test_check3_pass_structural_improved(tmp_path: Path) -> None:
    """Structural rose 75 → 80; PASS with delta=+5."""
    project = tmp_path / "proj"
    project.mkdir()
    prior = tmp_path / "prior-dashboard.md"
    prior.parent.mkdir(parents=True, exist_ok=True)
    prior.write_text(
        _dashboard_text(structural_score=75),
        encoding="utf-8",
    )
    _write_dashboard(project, structural_score=80)
    cp = _run_verify(project, prior=prior)
    assert cp.returncode == 0, cp.stderr
    record = _read_jsonl(_expected_jsonl_path(project))[-1]
    assert record["result"] == "PASS"
    c3 = _checks_by_id(record)[3]
    assert c3["result"] == "PASS"
    assert c3["delta"] == 5
    assert c3["prior"] == 75
    assert c3["current"] == 80
    assert c3["reason"] is None


def test_check3_fail_structural_dropped_by_six(tmp_path: Path) -> None:
    """Structural dropped 85 → 79 (delta -6); FAIL because threshold is -5."""
    project = tmp_path / "proj"
    project.mkdir()
    prior = tmp_path / "prior-dashboard.md"
    prior.write_text(_dashboard_text(structural_score=85), encoding="utf-8")
    _write_dashboard(project, structural_score=79)
    cp = _run_verify(project, prior=prior)
    assert cp.returncode == 1, f"expected FAIL exit; stderr={cp.stderr}"
    record = _read_jsonl(_expected_jsonl_path(project))[-1]
    assert record["result"] == "FAIL"
    c3 = _checks_by_id(record)[3]
    assert c3["result"] == "FAIL"
    assert c3["delta"] == -6
    assert c3["prior"] == 85
    assert c3["current"] == 79


# ──────────────────────────────────────────────────────────────────────────────
# Missing baseline — no-baseline PASS
# ──────────────────────────────────────────────────────────────────────────────


def test_check3_no_baseline_pass_when_dashboard_absent(tmp_path: Path) -> None:
    """Brand-new project: no dashboard.md, no prior. Check 3 PASS with reason."""
    project = tmp_path / "proj"
    (project / ".claude" / "observability").mkdir(parents=True)
    cp = _run_verify(project)
    assert cp.returncode == 0, cp.stderr
    record = _read_jsonl(_expected_jsonl_path(project))[-1]
    c3 = _checks_by_id(record)[3]
    assert c3["result"] == "PASS"
    reason = c3["reason"]
    assert isinstance(reason, str)
    assert "no-baseline" in reason or "no baseline" in reason


def test_check3_no_baseline_pass_when_pre_0_13_0_schema(tmp_path: Path) -> None:
    """Old single-scalar dashboard.md is not parseable by 0.13.0 reader → no-baseline."""
    project = tmp_path / "proj"
    project.mkdir()
    _write_old_schema_dashboard(project, score=70)
    cp = _run_verify(project)
    assert cp.returncode == 0, cp.stderr
    record = _read_jsonl(_expected_jsonl_path(project))[-1]
    c3 = _checks_by_id(record)[3]
    assert c3["result"] == "PASS"
    reason = c3["reason"]
    assert isinstance(reason, str)
    assert "no-baseline" in reason


# ──────────────────────────────────────────────────────────────────────────────
# Personalization is NEVER read by verify
# ──────────────────────────────────────────────────────────────────────────────


def test_personalization_section_does_not_gate_verify(tmp_path: Path) -> None:
    """Both sections present with a low personalization composite — verify still PASSes."""
    project = tmp_path / "proj"
    project.mkdir()
    prior = tmp_path / "prior.md"
    prior.write_text(_dashboard_text(structural_score=80), encoding="utf-8")
    _write_dashboard(
        project,
        structural_score=82,
        personalization_composite=30,
        personalization_tier="bronze",
    )
    cp = _run_verify(project, prior=prior)
    assert cp.returncode == 0, cp.stderr
    record = _read_jsonl(_expected_jsonl_path(project))[-1]
    assert record["result"] == "PASS"
    checks_by_id = _checks_by_id(record)
    # ADR-0007: 5-check verify (1..5). Personalization must NOT appear.
    assert set(checks_by_id.keys()) == {1, 2, 3, 4, 5}
    for cid in (1, 2, 3, 4, 5):
        assert checks_by_id[cid]["result"] in {"PASS", "FAIL", "SKIPPED"}
    # No record carries a "personalization" key at any level.
    payload = json.dumps(record)
    assert "personalization" not in payload.lower(), (
        "verify JSONL must not reference personalization"
    )


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────


def _dashboard_text(*, structural_score: int) -> str:
    """Render a minimal valid 0.22.3 (2-section) dashboard body."""
    return "\n".join(
        [
            "---",
            "generated_by: harness-maker",
            f"generated_at: {FIXED_TS}",
            "---",
            "# Health",
            "",
            "## Structural",
            f"score: {structural_score} / 100",
            "signals_failed: []",
            "",
            "## Personalization",
            "composite: 50 / 100",
            "tier: silver",
            'layers: {"l1_conversion": 0.5}',
            "action_items: []",
            "",
        ]
    )


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
