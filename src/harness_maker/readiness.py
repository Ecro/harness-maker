"""Health 6-dimension composite scoring (per amendment §F)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from harness_maker.models import Preset

WEIGHTS_SIDE: dict[str, float] = {
    "docs": 0.20,
    "tests": 0.30,
    "ci": 0.20,
    "observability": 0.15,
    "security": 0.15,
    "governance": 0.0,
}
WEIGHTS_PROD: dict[str, float] = {
    "docs": 0.15,
    "tests": 0.25,
    "ci": 0.15,
    "observability": 0.15,
    "security": 0.20,
    "governance": 0.10,
}


def _score_docs(project_dir: Path) -> int:
    score = 0
    if (project_dir / "CLAUDE.md").is_file():
        score += 40
    if (project_dir / "README.md").is_file():
        score += 30
    adr_dir = project_dir / "docs" / "adr"
    if adr_dir.is_dir() and any(adr_dir.glob("*.md")):
        score += 30
    return min(100, score)


def _score_tests(project_dir: Path) -> int:
    score = 0
    tests_dir = project_dir / "tests"
    if tests_dir.is_dir():
        score += 50
        for py in tests_dir.rglob("*.py"):
            try:
                if "def test_" in py.read_text(encoding="utf-8", errors="ignore"):
                    score += 50
                    break
            except OSError:
                continue
    return min(100, score)


def _score_ci(project_dir: Path) -> int:
    workflows = project_dir / ".github" / "workflows"
    if workflows.is_dir() and any(workflows.glob("*.yml")):
        return 100
    return 0


def _score_observability(project_dir: Path) -> int:
    score = 0
    obs = project_dir / ".claude" / "observability"
    if (obs / "metrics.jsonl").is_file():
        score += 50
    if (obs / "dashboard.md").is_file():
        score += 50
    return score


def _score_security(project_dir: Path) -> int:
    findings_dir = project_dir / ".claude" / "observability" / "security"
    if not findings_dir.is_dir():
        return 70  # unknown
    high = 0
    for f in findings_dir.glob("findings-*.jsonl"):
        try:
            for line in f.read_text(encoding="utf-8", errors="ignore").splitlines():
                if '"severity": "high"' in line or '"severity":"high"' in line:
                    high += 1
        except OSError:
            continue
    return max(0, min(100, 100 - high * 10))


def _score_governance(project_dir: Path, preset: Preset) -> int:
    if preset == Preset.SIDE:
        return 0  # weight 0; value irrelevant
    score = 0
    adr_dir = project_dir / "docs" / "adr"
    if adr_dir.is_dir() and any(adr_dir.glob("*.md")):
        score += 50
    if (project_dir / "CONTRIBUTING.md").is_file() or (
        project_dir / "docs" / "CONTRIBUTING.md"
    ).is_file():
        score += 50
    return score


def _count_files(project_dir: Path) -> int:
    claude_dir = project_dir / ".claude"
    if not claude_dir.is_dir():
        return 0
    return sum(1 for _ in claude_dir.rglob("*") if _.is_file())


def compute_health(project_dir: Path, preset: Preset) -> dict[str, Any]:
    """Compute 6-dimensional Health composite per amendment §F."""
    weights = WEIGHTS_SIDE if preset == Preset.SIDE else WEIGHTS_PROD
    dims: dict[str, int] = {
        "docs": _score_docs(project_dir),
        "tests": _score_tests(project_dir),
        "ci": _score_ci(project_dir),
        "observability": _score_observability(project_dir),
        "security": _score_security(project_dir),
        "governance": _score_governance(project_dir, preset),
    }
    weighted = sum(dims[k] * weights[k] for k in weights)
    file_count = _count_files(project_dir)
    target = 30 if preset == Preset.SIDE else 45
    ceremony_penalty = max(0.0, min(15.0, (file_count - target) * 0.5))
    composite = max(0.0, min(100.0, weighted - ceremony_penalty))
    return {
        "dimensions": dims,
        "weights": weights,
        "ceremony_penalty": ceremony_penalty,
        "composite": int(composite),
    }
