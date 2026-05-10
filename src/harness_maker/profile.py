"""Project profiler — derives stack/scale/lifecycle/dotclaude/spec_only/vault signals."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from harness_maker.models import ProjectProfile

SCALE_SMALL_MAX = 50
SCALE_MEDIUM_MAX = 500

IGNORE_DIRS = {
    ".git",
    "node_modules",
    "__pycache__",
    ".venv",
    ".worktrees",
    "dist",
    "build",
    "target",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
}

STACK_MANIFESTS: dict[str, list[str]] = {
    "python": ["pyproject.toml", "requirements.txt", "setup.py"],
    "node": ["package.json"],
    "rust": ["Cargo.toml"],
    "cmake": ["CMakeLists.txt"],
    "go": ["go.mod"],
}


def profile(project_dir: Path) -> ProjectProfile:
    """Inspect ``project_dir`` and return a ProjectProfile of detected signals."""
    # (a) stack
    stack: list[str] = []
    for stack_name, manifests in STACK_MANIFESTS.items():
        if any((project_dir / m).exists() for m in manifests):
            stack.append(stack_name)
    if not stack:
        stack = ["unknown"]

    # (b) scale — count files excluding ignore dirs
    file_count = _count_tracked_files(project_dir)
    if file_count < SCALE_SMALL_MAX:
        scale = "small"
    elif file_count <= SCALE_MEDIUM_MAX:
        scale = "medium"
    else:
        scale = "large"

    # (c) lifecycle — git commit count last 30 days
    lifecycle = _detect_lifecycle(project_dir)

    # (d) existing_dotclaude
    existing_dotclaude = (project_dir / ".claude").is_dir()

    # (e) spec_only — TECH_SPEC.md exists + ≤5 files (assumed scaffolding only)
    spec_only = (project_dir / "TECH_SPEC.md").exists() and file_count <= 5

    # (f) vault_member
    vault_member = (project_dir / ".claude" / "obsidian.json").exists()

    detected_checks = _detect_mechanical_checks(project_dir)

    return ProjectProfile(
        stack=stack,
        scale=scale,
        lifecycle=lifecycle,
        existing_dotclaude=existing_dotclaude,
        spec_only=spec_only,
        vault_member=vault_member,
        detected_checks=detected_checks,
    )


def _detect_mechanical_checks(project_dir: Path) -> list[str]:
    """Scan pyproject.toml and Makefile for common check commands."""
    checks: list[str] = []
    pyproject = project_dir / "pyproject.toml"
    if pyproject.exists():
        try:
            content = pyproject.read_text(encoding="utf-8")
        except OSError:
            content = ""
        if "[tool.ruff]" in content:
            checks.append("uv run ruff check .")
        if "[tool.mypy]" in content or "mypy" in content:
            checks.append("uv run mypy .")
        if "pytest" in content:
            checks.append("uv run pytest --tb=short -q")
    makefile = project_dir / "Makefile"
    if makefile.exists():
        try:
            content = makefile.read_text(encoding="utf-8")
        except OSError:
            content = ""
        for line in content.splitlines():
            if line.strip().startswith(("lint:", "check:", "typecheck:", "test:")):
                target = line.split(":")[0].strip()
                checks.append(f"make {target}")
    return checks[:4]


def _count_tracked_files(project_dir: Path) -> int:
    """Count tracked files via git ls-files if non-zero; otherwise os.walk excluding IGNORE_DIRS."""
    if (project_dir / ".git").exists():
        try:
            result = subprocess.run(
                ["git", "ls-files"],
                cwd=project_dir,
                capture_output=True,
                text=True,
                timeout=10,
                check=True,
            )
        except (subprocess.SubprocessError, FileNotFoundError):
            pass
        else:
            tracked = len(result.stdout.splitlines())
            if tracked > 0:
                return tracked
            # git ls-files returned 0 → either fixture inside a parent repo with no
            # tracked files in this subtree, or empty repo. Fall through to os.walk.
    count = 0
    for root, dirs, files in os.walk(project_dir):  # noqa: B007
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        count += len(files)
    return count


def _detect_lifecycle(project_dir: Path) -> str:
    """Map last-30-days commit count to a lifecycle bucket."""
    if not (project_dir / ".git").exists():
        return "experiment"
    try:
        result = subprocess.run(
            ["git", "log", "--since=30.days.ago", "--oneline"],
            cwd=project_dir,
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        )
    except (subprocess.SubprocessError, FileNotFoundError):
        return "experiment"
    commit_count = len(result.stdout.splitlines())
    if commit_count == 0:
        return "experiment"
    if commit_count < 10:
        return "maintenance"
    return "active"
