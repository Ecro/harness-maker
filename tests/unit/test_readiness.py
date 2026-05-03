"""Health 6-dim scoring tests (per amendment §F)."""

from __future__ import annotations

from pathlib import Path

from harness_maker.models import Preset
from harness_maker.readiness import compute_health


def test_empty_project_low_score(tmp_path: Path) -> None:
    res = compute_health(tmp_path, Preset.SIDE)
    assert res["composite"] < 30
    assert "dimensions" in res
    assert set(res["dimensions"].keys()) == {
        "docs",
        "tests",
        "ci",
        "observability",
        "security",
        "governance",
    }


def test_rich_project_high_score(tmp_path: Path) -> None:
    (tmp_path / "CLAUDE.md").write_text("# claude md\n")
    (tmp_path / "README.md").write_text("# readme\n")
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'x'\n")  # stack marker
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_x.py").write_text("def test_one():\n    assert True\n")
    workflows = tmp_path / ".github" / "workflows"
    workflows.mkdir(parents=True)
    (workflows / "ci.yml").write_text("name: ci\n")
    res = compute_health(tmp_path, Preset.SIDE)
    assert res["composite"] > 50
    assert res["dimensions"]["docs"] >= 70
    assert res["dimensions"]["tests"] == 100
    assert res["dimensions"]["ci"] == 100


def test_side_vs_production_weights(tmp_path: Path) -> None:
    # Production weighs governance (which Side ignores); add ADR + CONTRIBUTING
    (tmp_path / "CLAUDE.md").write_text("# x\n")
    (tmp_path / "README.md").write_text("# y\n")
    (tmp_path / "CONTRIBUTING.md").write_text("# c\n")
    adr = tmp_path / "docs" / "adr"
    adr.mkdir(parents=True)
    (adr / "001.md").write_text("# adr\n")
    res_side = compute_health(tmp_path, Preset.SIDE)
    res_prod = compute_health(tmp_path, Preset.PRODUCTION)
    # Side: governance weight 0; Production: weight 0.10 with full 100 governance
    assert res_side["weights"] != res_prod["weights"]
    assert res_prod["dimensions"]["governance"] == 100
    assert res_side["dimensions"]["governance"] == 0


def test_observability_dimension(tmp_path: Path) -> None:
    obs = tmp_path / ".claude" / "observability"
    obs.mkdir(parents=True)
    (obs / "metrics.jsonl").write_text("")
    (obs / "dashboard.md").write_text("# dash\n")
    res = compute_health(tmp_path, Preset.SIDE)
    assert res["dimensions"]["observability"] == 100


def test_security_unknown_default(tmp_path: Path) -> None:
    res = compute_health(tmp_path, Preset.SIDE)
    assert res["dimensions"]["security"] == 50


def test_ceremony_penalty_applied(tmp_path: Path) -> None:
    # Create user-added .md files (no content_hash) to trigger ceremony penalty.
    # Side threshold is 10; 20 files should produce a non-zero penalty.
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    for i in range(20):
        (claude_dir / f"user-agent-{i}.md").write_text(f"# Agent {i}\nsome content\n")
    res = compute_health(tmp_path, Preset.SIDE)
    assert res["ceremony_penalty"] > 0
    assert res["user_md_files"] == 20
