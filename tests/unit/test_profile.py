"""Tests for the project Profiler."""

from __future__ import annotations

from pathlib import Path

from harness_maker.profile import profile


def test_profile_python_cli_with_git(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n")
    (tmp_path / ".git").mkdir()
    p = profile(tmp_path)
    assert "python" in p.stack
    # No git binary available or empty repo → experiment
    assert p.lifecycle == "experiment"
    assert p.existing_dotclaude is False
    assert p.vault_member is False


def test_profile_no_manifests_returns_unknown(tmp_path: Path) -> None:
    p = profile(tmp_path)
    assert p.stack == ["unknown"]


def test_profile_no_git_lifecycle_experiment(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text("{}")
    p = profile(tmp_path)
    assert p.lifecycle == "experiment"
    assert "node" in p.stack


def test_profile_vault_member(tmp_path: Path) -> None:
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / "obsidian.json").write_text("{}")
    p = profile(tmp_path)
    assert p.vault_member is True
    assert p.existing_dotclaude is True


def test_profile_existing_dotclaude_without_obsidian(tmp_path: Path) -> None:
    (tmp_path / ".claude").mkdir()
    p = profile(tmp_path)
    assert p.existing_dotclaude is True
    assert p.vault_member is False


def test_profile_scale_small_boundary(tmp_path: Path) -> None:
    # 49 files → small (< 50)
    for i in range(49):
        (tmp_path / f"f{i}.txt").touch()
    p = profile(tmp_path)
    assert p.scale == "small"


def test_profile_scale_medium_boundary(tmp_path: Path) -> None:
    # 50 files → medium (>= 50, <= 500)
    for i in range(50):
        (tmp_path / f"f{i}.txt").touch()
    p = profile(tmp_path)
    assert p.scale == "medium"


def test_profile_multi_stack_tauri(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text("{}")
    (tmp_path / "Cargo.toml").write_text("[package]\nname='x'\n")
    p = profile(tmp_path)
    assert "node" in p.stack
    assert "rust" in p.stack


def test_profile_cmake_stack(tmp_path: Path) -> None:
    (tmp_path / "CMakeLists.txt").write_text("project(x)\n")
    p = profile(tmp_path)
    assert "cmake" in p.stack


def test_profile_go_stack(tmp_path: Path) -> None:
    (tmp_path / "go.mod").write_text("module x\n")
    p = profile(tmp_path)
    assert "go" in p.stack


def test_profile_spec_only_true(tmp_path: Path) -> None:
    (tmp_path / "TECH_SPEC.md").write_text("# spec\n")
    p = profile(tmp_path)
    assert p.spec_only is True


def test_profile_spec_only_false_when_many_files(tmp_path: Path) -> None:
    (tmp_path / "TECH_SPEC.md").write_text("# spec\n")
    for i in range(10):
        (tmp_path / f"f{i}.txt").touch()
    p = profile(tmp_path)
    assert p.spec_only is False


def test_profile_ignores_node_modules(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text("{}")
    nm = tmp_path / "node_modules"
    nm.mkdir()
    for i in range(100):
        (nm / f"f{i}.txt").touch()
    p = profile(tmp_path)
    # node_modules should be ignored → only package.json (1 file) → small
    assert p.scale == "small"


# ---------------------------------------------------------------------------
# Phase 3: mechanical_checks detection
# ---------------------------------------------------------------------------


def test_detect_checks_pyproject_ruff(tmp_path: Path) -> None:
    """pyproject.toml with [tool.ruff] → detected_checks includes ruff."""
    (tmp_path / "pyproject.toml").write_text("[tool.ruff]\n")
    p = profile(tmp_path)
    assert any("ruff" in c for c in p.detected_checks)


def test_detect_checks_pyproject_mypy(tmp_path: Path) -> None:
    """pyproject.toml mentioning mypy → detected_checks includes mypy."""
    (tmp_path / "pyproject.toml").write_text("[tool.mypy]\nstrict = true\n")
    p = profile(tmp_path)
    assert any("mypy" in c for c in p.detected_checks)


def test_detect_checks_pyproject_pytest(tmp_path: Path) -> None:
    """pyproject.toml with pytest dependency → detected_checks includes pytest."""
    (tmp_path / "pyproject.toml").write_text('[project]\ndependencies = ["pytest"]\n')
    p = profile(tmp_path)
    assert any("pytest" in c for c in p.detected_checks)


def test_detect_checks_makefile_targets(tmp_path: Path) -> None:
    """Makefile with lint:/test: targets → detected_checks includes make lint/test."""
    (tmp_path / "Makefile").write_text("lint:\n\truff check .\ntest:\n\tpytest\n")
    p = profile(tmp_path)
    assert any("make lint" in c for c in p.detected_checks)
    assert any("make test" in c for c in p.detected_checks)


def test_detect_checks_empty_project(tmp_path: Path) -> None:
    """Project with no pyproject.toml or Makefile → empty detected_checks."""
    (tmp_path / "README.md").write_text("hello")
    p = profile(tmp_path)
    assert p.detected_checks == []


def test_detect_checks_cap_at_4(tmp_path: Path) -> None:
    """detected_checks is capped at 4 to avoid overwhelming."""
    (tmp_path / "pyproject.toml").write_text(
        "[tool.ruff]\n[tool.mypy]\n[project]\ndependencies = ['pytest']\n"
    )
    (tmp_path / "Makefile").write_text(
        "lint:\n\truff .\ntest:\n\tpytest\ntypecheck:\n\tmypy .\ncheck:\n\tall\n"
    )
    p = profile(tmp_path)
    assert len(p.detected_checks) <= 4
