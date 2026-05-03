"""Health 6-dimension composite scoring (per amendment §F)."""

from __future__ import annotations

import json
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

# Dirs to skip when scanning source files
_SCAN_IGNORE = {"build", "_build", ".git", "node_modules", "__pycache__", ".venv", "target", "dist"}


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


# ── test detection ───────────────────────────────────────────────────���─────


def _detect_stacks(project_dir: Path) -> set[str]:
    stacks: set[str] = set()
    if any((project_dir / m).exists() for m in ["pyproject.toml", "requirements.txt", "setup.py"]):
        stacks.add("python")
    if (project_dir / "pubspec.yaml").exists():
        stacks.add("dart")
    if (project_dir / "CMakeLists.txt").exists():
        stacks.add("c")
    if (project_dir / "Cargo.toml").exists():
        stacks.add("rust")
    if (project_dir / "go.mod").exists():
        stacks.add("go")
    if (project_dir / "package.json").exists():
        stacks.add("node")
    return stacks


def _has_tests_python(project_dir: Path) -> bool:
    tests_dir = project_dir / "tests"
    if not tests_dir.is_dir():
        return False
    for py in tests_dir.rglob("*.py"):
        try:
            if "def test_" in py.read_text(encoding="utf-8", errors="ignore"):
                return True
        except OSError:
            continue
    return False


def _has_tests_dart(project_dir: Path) -> bool:
    test_dir = project_dir / "test"
    return test_dir.is_dir() and any(test_dir.rglob("*_test.dart"))


def _has_tests_c(project_dir: Path) -> bool:
    # Zephyr: tests/ subdir is the standard location
    if (project_dir / "tests").is_dir():
        return True
    # Fallback: scan .c files for ZTEST / Unity TEST macros (capped at 100 files)
    scanned = 0
    for c_file in project_dir.rglob("*.c"):
        if any(part in _SCAN_IGNORE for part in c_file.parts):
            continue
        if scanned >= 100:
            break
        scanned += 1
        try:
            content = c_file.read_text(encoding="utf-8", errors="ignore")
            if "ZTEST(" in content or "TEST(" in content or "test_" in c_file.name:
                return True
        except OSError:
            continue
    return False


def _has_tests_rust(project_dir: Path) -> bool:
    tests_dir = project_dir / "tests"
    if tests_dir.is_dir() and any(tests_dir.glob("*.rs")):
        return True
    scanned = 0
    for rs_file in project_dir.rglob("*.rs"):
        if any(part in _SCAN_IGNORE for part in rs_file.parts):
            continue
        if scanned >= 100:
            break
        scanned += 1
        try:
            if "#[test]" in rs_file.read_text(encoding="utf-8", errors="ignore"):
                return True
        except OSError:
            continue
    return False


def _has_tests_go(project_dir: Path) -> bool:
    return any(
        f
        for f in project_dir.rglob("*_test.go")
        if not any(part in _SCAN_IGNORE for part in f.parts)
    )


def _has_tests_node(project_dir: Path) -> bool:
    pkg = project_dir / "package.json"
    try:
        data = json.loads(pkg.read_text(encoding="utf-8"))
        if "test" in data.get("scripts", {}):
            return True
    except (OSError, json.JSONDecodeError, ValueError):
        pass
    patterns = ("*.test.js", "*.test.ts", "*.spec.js", "*.spec.ts")
    return any(
        f
        for pat in patterns
        for f in project_dir.rglob(pat)
        if not any(part in _SCAN_IGNORE for part in f.parts)
    )


_STACK_TESTERS = {
    "python": _has_tests_python,
    "dart": _has_tests_dart,
    "c": _has_tests_c,
    "rust": _has_tests_rust,
    "go": _has_tests_go,
    "node": _has_tests_node,
}


def _score_tests(project_dir: Path) -> int:
    stacks = _detect_stacks(project_dir)
    if not stacks:
        return 50  # unknown stack — cannot assess
    has_tests = any(_STACK_TESTERS[s](project_dir) for s in stacks if s in _STACK_TESTERS)
    return 100 if has_tests else 0


# ── other dimensions ────────────────────────────────────────────────────────


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
        return 50  # not scanned yet — neutral, not assumed safe
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


# ── ceremony penalty (C+A) ──────────────────────────────────────────────────


def _count_user_md_files(claude_dir: Path) -> int:
    """Count .md files in .claude/ without harness-maker provenance frontmatter.

    Harness-generated files always have `content_hash:` in the first 500 chars
    of their YAML frontmatter. Files without it are user-added.
    """
    if not claude_dir.is_dir():
        return 0
    count = 0
    for f in claude_dir.rglob("*.md"):
        if not f.is_file():
            continue
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            count += 1  # unreadable → treat as user-owned
            continue
        if not (text.startswith("---\n") and "content_hash:" in text[:500]):
            count += 1
    return count


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

    # Ceremony penalty: user-added .md files beyond threshold signal over-customisation.
    # Counts only files lacking harness provenance (content_hash) so harness-generated
    # files never count against the project.
    claude_dir = project_dir / ".claude"
    user_md = _count_user_md_files(claude_dir)
    target = 10 if preset == Preset.SIDE else 15
    ceremony_penalty = max(0.0, min(15.0, max(0, user_md - target) * 1.5))

    composite = max(0.0, min(100.0, weighted - ceremony_penalty))
    return {
        "dimensions": dims,
        "weights": weights,
        "user_md_files": user_md,
        "ceremony_penalty": ceremony_penalty,
        "composite": int(composite),
    }
