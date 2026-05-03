"""Tests for the modular installer (--add / --remove)."""

from __future__ import annotations

from pathlib import Path

import pytest

from harness_maker.interview import interview
from harness_maker.modular_edit import ModularEditError, add, remove
from harness_maker.profile import profile
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize


def _build_side_fixture(tmp_path: Path) -> Path:
    """Render a fresh Side preset .claude/ tree under tmp_path."""
    target = tmp_path / "side-fixture"
    target.mkdir()
    (target / "pyproject.toml").write_text("[project]\nname='x'\nversion='0'\n")
    p = profile(target)
    a = interview(p, autoloop_mode=True)
    bp = synthesize(p, a)
    target_dotclaude = target / ".claude"
    render(bp, target_dotclaude, freeze_time=DEFAULT_FREEZE_TIME)
    return target_dotclaude


def test_add_reviewer_security_creates_file(tmp_path: Path) -> None:
    target_dotclaude = _build_side_fixture(tmp_path)
    rendered = add("reviewer:security", target_dotclaude)
    assert rendered.exists()
    assert rendered.name == "security-reviewer.md"
    assert (target_dotclaude / "agents" / "security-reviewer.md").exists()


def test_add_reviewer_idempotent(tmp_path: Path) -> None:
    target_dotclaude = _build_side_fixture(tmp_path)
    add("reviewer:security", target_dotclaude)
    # Second call should not raise (file exists, list contains entry)
    add("reviewer:security", target_dotclaude)
    import yaml

    text = (target_dotclaude / "harness.yaml").read_text()
    # Strip frontmatter
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        text = text[end + 5 :]
    config = yaml.safe_load(text)
    enabled = config["reviewers"]["enabled"]
    assert enabled.count("security-reviewer") == 1


def test_add_invalid_component_raises(tmp_path: Path) -> None:
    target_dotclaude = _build_side_fixture(tmp_path)
    with pytest.raises(ModularEditError):
        add("nonsense", target_dotclaude)


def test_add_unsupported_kind_raises(tmp_path: Path) -> None:
    target_dotclaude = _build_side_fixture(tmp_path)
    with pytest.raises(ModularEditError):
        add("hook:pre-push-smoke", target_dotclaude)


def test_add_skill_creates_file(tmp_path: Path) -> None:
    target_dotclaude = _build_side_fixture(tmp_path)
    rendered = add("skill:conditional-router", target_dotclaude)
    assert rendered.exists()
    assert rendered.name == "SKILL.md"


def test_remove_reviewer_deletes_file(tmp_path: Path) -> None:
    target_dotclaude = _build_side_fixture(tmp_path)
    add("reviewer:security", target_dotclaude)
    out = remove("reviewer:security", target_dotclaude)
    assert not out.exists()


def test_add_updates_harness_yaml(tmp_path: Path) -> None:
    target_dotclaude = _build_side_fixture(tmp_path)
    add("reviewer:security", target_dotclaude)
    import yaml

    text = (target_dotclaude / "harness.yaml").read_text()
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        text = text[end + 5 :]
    config = yaml.safe_load(text)
    assert "security-reviewer" in config["reviewers"]["enabled"]
