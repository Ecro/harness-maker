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
