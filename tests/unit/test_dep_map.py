"""Tests for test dependency map (TDAD — Phase 11)."""

from __future__ import annotations

from pathlib import Path

from harness_maker.test_dep_map import (
    build_test_hints,
    find_importers,
    source_to_test_candidates,
)


def _setup_project(tmp_path: Path) -> Path:
    """Create a minimal project structure for testing."""
    (tmp_path / "src" / "pkg").mkdir(parents=True)
    (tmp_path / "tests" / "unit").mkdir(parents=True)
    (tmp_path / "src" / "pkg" / "auth.py").write_text("def login(): pass\n")
    (tmp_path / "src" / "pkg" / "utils.py").write_text("def helper(): pass\n")
    (tmp_path / "tests" / "unit" / "test_auth.py").write_text(
        "from harness_maker.auth import login\ndef test_login(): pass\n"
    )
    (tmp_path / "tests" / "unit" / "test_utils.py").write_text(
        "from harness_maker.utils import helper\ndef test_helper(): pass\n"
    )
    return tmp_path


def test_source_to_test_candidates_finds_unit_test(tmp_path: Path) -> None:
    root = _setup_project(tmp_path)
    src = root / "src" / "pkg" / "auth.py"
    candidates = source_to_test_candidates(src, root)
    names = [c.name for c in candidates]
    assert "test_auth.py" in names


def test_source_to_test_candidates_no_match(tmp_path: Path) -> None:
    root = _setup_project(tmp_path)
    (root / "src" / "pkg" / "unknown.py").write_text("pass\n")
    src = root / "src" / "pkg" / "unknown.py"
    candidates = source_to_test_candidates(src, root)
    assert candidates == []


def test_source_to_test_returns_self_for_test_file(tmp_path: Path) -> None:
    root = _setup_project(tmp_path)
    test_file = root / "tests" / "unit" / "test_auth.py"
    candidates = source_to_test_candidates(test_file, root)
    assert test_file in candidates


def test_find_importers_detects_import(tmp_path: Path) -> None:
    root = _setup_project(tmp_path)
    importers = find_importers("auth", root / "tests")
    names = [p.name for p in importers]
    assert "test_auth.py" in names


def test_find_importers_no_match(tmp_path: Path) -> None:
    root = _setup_project(tmp_path)
    importers = find_importers("nonexistent_module", root / "tests")
    assert importers == []


def test_find_importers_handles_missing_dir(tmp_path: Path) -> None:
    importers = find_importers("auth", tmp_path / "no_such_dir")
    assert importers == []


def test_build_test_hints_maps_source_to_tests(tmp_path: Path) -> None:
    root = _setup_project(tmp_path)
    changed = [root / "src" / "pkg" / "auth.py"]
    hints = build_test_hints(changed, root)
    assert "src/pkg/auth.py" in hints
    assert any("test_auth" in t for t in hints["src/pkg/auth.py"])


def test_build_test_hints_skips_non_python(tmp_path: Path) -> None:
    root = _setup_project(tmp_path)
    readme = root / "README.md"
    readme.write_text("# Hello\n")
    hints = build_test_hints([readme], root)
    assert hints == {}


def test_build_test_hints_empty_input(tmp_path: Path) -> None:
    root = _setup_project(tmp_path)
    hints = build_test_hints([], root)
    assert hints == {}


def test_build_test_hints_no_tests_for_file(tmp_path: Path) -> None:
    root = _setup_project(tmp_path)
    orphan = root / "src" / "pkg" / "orphan.py"
    orphan.write_text("pass\n")
    hints = build_test_hints([orphan], root)
    assert "src/pkg/orphan.py" in hints
    assert hints["src/pkg/orphan.py"] == []


def test_build_test_hints_deduplicates(tmp_path: Path) -> None:
    root = _setup_project(tmp_path)
    changed = [root / "src" / "pkg" / "auth.py"]
    hints = build_test_hints(changed, root)
    paths = hints.get("src/pkg/auth.py", [])
    assert len(paths) == len(set(paths))
