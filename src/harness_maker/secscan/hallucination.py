"""AST-based hallucination gate — detect imports of non-existent packages.

Parses Python files with stdlib ``ast``, extracts top-level package names from
import statements, and checks against stdlib + installed packages. Flags imports
that cannot be resolved as potential LLM hallucinations.

Limitations (intentional):
- Dynamic imports (``importlib.import_module``, ``__import__``) are not detected.
- Conditional imports inside ``try/except ImportError`` are flagged but with
  lower severity (P2) since they indicate optional dependencies.
- Only Python files are scanned; other languages are out of scope.
"""

from __future__ import annotations

import ast
import importlib.util
import sys
from pathlib import Path

from harness_maker.models import Finding

_STDLIB_MODULES: frozenset[str] = frozenset(sys.stdlib_module_names)

_KNOWN_NAMESPACE_PACKAGES: frozenset[str] = frozenset(
    {
        "google",
        "azure",
        "aws_cdk",
        "zope",
        "jaraco",
        "backports",
        "sphinxcontrib",
    }
)


def _top_level_package(module_name: str) -> str:
    return module_name.split(".")[0]


def _is_available(package: str) -> bool:
    """Check if a top-level package is stdlib or installed."""
    if package in _STDLIB_MODULES:
        return True
    if package == "__future__":
        return True
    try:
        spec = importlib.util.find_spec(package)
        return spec is not None
    except (ModuleNotFoundError, ValueError):
        return False


def scan_file(file_path: Path) -> list[Finding]:
    """Scan a single Python file for hallucinated imports."""
    try:
        source = file_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    try:
        tree = ast.parse(source, filename=str(file_path))
    except SyntaxError:
        return []

    findings: list[Finding] = []
    guarded_lines: set[int] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Try):
            for try_child in node.body:
                for inner in ast.walk(try_child):
                    if isinstance(inner, (ast.Import, ast.ImportFrom)):
                        guarded_lines.add(inner.lineno)

    for node in ast.walk(tree):
        packages_to_check: list[tuple[str, int]] = []

        if isinstance(node, ast.Import):
            for alias in node.names:
                pkg = _top_level_package(alias.name)
                packages_to_check.append((pkg, node.lineno))
        elif isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                continue
            if node.module is not None:
                pkg = _top_level_package(node.module)
                packages_to_check.append((pkg, node.lineno))

        for pkg, lineno in packages_to_check:
            if not pkg or pkg.startswith("_"):
                continue
            if _is_available(pkg):
                continue
            if pkg in _KNOWN_NAMESPACE_PACKAGES:
                continue

            is_guarded = lineno in guarded_lines
            severity = "P2" if is_guarded else "P0"
            findings.append(
                Finding(
                    severity=severity,
                    category="hallucination",
                    file=str(file_path),
                    line=lineno,
                    evidence=(
                        f"import of '{pkg}' — package not found in stdlib or installed packages"
                    ),
                    fix=(
                        f"Verify '{pkg}' exists. If intentional, add to "
                        f"project dependencies. If hallucinated, remove the import."
                    ),
                )
            )

    return findings


def scan_directory(target_dir: Path) -> list[Finding]:
    """Scan all Python files in a directory tree for hallucinated imports."""
    findings: list[Finding] = []
    skip_dirs = {".git", ".venv", "node_modules", "__pycache__", ".worktrees"}

    for py_file in target_dir.rglob("*.py"):
        if any(part in skip_dirs for part in py_file.parts):
            continue
        findings.extend(scan_file(py_file))

    return findings
