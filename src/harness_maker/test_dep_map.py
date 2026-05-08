"""Test dependency map — map changed source files to affected tests (TDAD).

Given a list of changed source files, resolves which test files are
likely affected using convention-based naming and import analysis.
Used by the execute stage to provide concrete test hints instead of
generic "follow TDD" instructions.
"""

from __future__ import annotations

import ast
from pathlib import Path


def source_to_test_candidates(
    source_path: Path,
    project_root: Path,
) -> list[Path]:
    """Return candidate test file paths for a given source file.

    Applies Python naming conventions:
      src/pkg/module.py → tests/unit/test_module.py
      src/pkg/module.py → tests/test_module.py
      src/pkg/sub/module.py → tests/unit/test_module.py
      pkg/module.py → tests/test_module.py
    """
    stem = source_path.stem
    if stem.startswith("test_") or stem.startswith("conftest"):
        return [source_path]

    test_name = f"test_{stem}.py"
    candidates: list[Path] = []

    for test_dir in ["tests/unit", "tests", "test"]:
        candidate = project_root / test_dir / test_name
        if candidate.exists():
            candidates.append(candidate)

    rel = (
        source_path.relative_to(project_root)
        if source_path.is_relative_to(project_root)
        else source_path
    )
    parts = list(rel.parts)
    if len(parts) > 1 and parts[0] == "src":
        parts = parts[1:]
    if len(parts) > 1:
        sub_dir = "/".join(parts[:-1])
        for test_root in ["tests/unit", "tests"]:
            candidate = project_root / test_root / sub_dir / test_name
            if candidate.exists():
                candidates.append(candidate)

    seen: set[Path] = set()
    deduped: list[Path] = []
    for c in candidates:
        resolved = c.resolve()
        if resolved not in seen:
            seen.add(resolved)
            deduped.append(c)
    return deduped


def find_importers(
    module_name: str,
    test_dir: Path,
) -> list[Path]:
    """Find test files that import the given module name (shallow AST scan)."""
    if not test_dir.is_dir():
        return []

    importers: list[Path] = []
    for py_file in test_dir.rglob("*.py"):
        if not py_file.name.startswith("test_"):
            continue
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if module_name in alias.name:
                        importers.append(py_file)
                        break
                else:
                    continue
                break
            if isinstance(node, ast.ImportFrom) and node.module and module_name in node.module:
                importers.append(py_file)
                break
    return importers


def build_test_hints(
    changed_files: list[Path],
    project_root: Path,
) -> dict[str, list[str]]:
    """Build a mapping of changed source files to affected test file paths.

    Returns a dict mapping source file (relative string) to list of
    affected test file paths (relative strings). Empty list means no
    known tests cover the file.
    """
    hints: dict[str, list[str]] = {}
    for src in changed_files:
        if src.suffix != ".py":
            continue

        rel_src = (
            str(src.relative_to(project_root))
            if src.is_relative_to(project_root)
            else str(src)
        )

        affected: list[Path] = source_to_test_candidates(src, project_root)

        module_stem = src.stem
        if not module_stem.startswith("test_"):
            for test_dir_name in ["tests", "test"]:
                test_dir = project_root / test_dir_name
                if test_dir.is_dir():
                    importers = find_importers(module_stem, test_dir)
                    for imp in importers:
                        if imp.resolve() not in {a.resolve() for a in affected}:
                            affected.append(imp)

        hints[rel_src] = [
            str(t.relative_to(project_root)) if t.is_relative_to(project_root) else str(t)
            for t in affected
        ]
    return hints
