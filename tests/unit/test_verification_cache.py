"""Phase 8 — A1 check-suite verification cache tests."""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from harness_maker.observability.verification_cache import (
    _env_hash,
    _should_ignore_env,
    compute_skip_key,
    is_fresh,
    mark_passed,
)


@pytest.fixture()
def fake_project(tmp_path: Path) -> Path:
    """Create a minimal git repo for skip-key computation."""
    (tmp_path / "pyproject.toml").write_text("[project]\nname='test'\n")
    (tmp_path / "uv.lock").write_text("# lock\n")

    import subprocess

    subprocess.run(
        ["git", "init"], cwd=tmp_path, capture_output=True, check=True
    )
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=tmp_path,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=tmp_path,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "add", "."], cwd=tmp_path, capture_output=True, check=True
    )
    subprocess.run(
        ["git", "commit", "-m", "init"],
        cwd=tmp_path,
        capture_output=True,
        check=True,
    )
    return tmp_path


def test_verification_key_includes_sha(fake_project: Path) -> None:
    """Key must change when HEAD sha changes."""
    key1 = compute_skip_key(fake_project)
    (fake_project / "new.txt").write_text("data")
    import subprocess

    subprocess.run(
        ["git", "add", "."], cwd=fake_project, capture_output=True, check=True
    )
    subprocess.run(
        ["git", "commit", "-m", "second"],
        cwd=fake_project,
        capture_output=True,
        check=True,
    )
    key2 = compute_skip_key(fake_project)
    assert key1 != key2


def test_verification_key_includes_uv_lock(fake_project: Path) -> None:
    """Key must change when uv.lock changes."""
    key1 = compute_skip_key(fake_project)
    (fake_project / "uv.lock").write_text("# changed lock\n")
    key2 = compute_skip_key(fake_project)
    assert key1 != key2


def test_verification_key_includes_tool_versions(fake_project: Path) -> None:
    """Key must change when tool versions change (mocked)."""
    key1 = compute_skip_key(fake_project)
    with patch(
        "harness_maker.observability.verification_cache._tool_versions",
        return_value={"python": "3.99.0", "ruff": "99.0", "mypy": "99.0", "pytest": "99.0"},
    ):
        key2 = compute_skip_key(fake_project)
    assert key1 != key2


def test_verification_key_includes_project_root(tmp_path: Path) -> None:
    """Two projects with same content but different roots must have different keys."""
    import subprocess

    for name in ("repo_a", "repo_b"):
        d = tmp_path / name
        d.mkdir()
        (d / "pyproject.toml").write_text("[project]\nname='test'\n")
        (d / "uv.lock").write_text("# lock\n")
        subprocess.run(
            ["git", "init"], cwd=d, capture_output=True, check=True
        )
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=d, capture_output=True, check=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=d, capture_output=True, check=True,
        )
        subprocess.run(
            ["git", "add", "."], cwd=d, capture_output=True, check=True
        )
        subprocess.run(
            ["git", "commit", "-m", "init"],
            cwd=d, capture_output=True, check=True,
        )

    key_a = compute_skip_key(tmp_path / "repo_a")
    key_b = compute_skip_key(tmp_path / "repo_b")
    assert key_a != key_b, "Different project roots must produce different keys"


def test_verification_key_invalidates_on_lang_change(fake_project: Path) -> None:
    """Changing LANG env var must invalidate the key (C1 validator concern)."""
    old_lang = os.environ.get("LANG")
    try:
        os.environ["LANG"] = "en_US.UTF-8"
        key1 = compute_skip_key(fake_project)
        os.environ["LANG"] = "C"
        key2 = compute_skip_key(fake_project)
        assert key1 != key2
    finally:
        if old_lang is None:
            os.environ.pop("LANG", None)
        else:
            os.environ["LANG"] = old_lang


def test_verification_key_invalidates_on_tz_change(fake_project: Path) -> None:
    """Changing TZ env var must invalidate the key."""
    old_tz = os.environ.get("TZ")
    try:
        os.environ["TZ"] = "UTC"
        key1 = compute_skip_key(fake_project)
        os.environ["TZ"] = "America/New_York"
        key2 = compute_skip_key(fake_project)
        assert key1 != key2
    finally:
        if old_tz is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = old_tz


def test_verification_key_ignores_pwd(fake_project: Path) -> None:
    """PWD is in the ignore set and must not affect the key."""
    old_pwd = os.environ.get("PWD")
    try:
        os.environ["PWD"] = "/tmp/foo"
        key1 = compute_skip_key(fake_project)
        os.environ["PWD"] = "/tmp/bar"
        key2 = compute_skip_key(fake_project)
        assert key1 == key2
    finally:
        if old_pwd is None:
            os.environ.pop("PWD", None)
        else:
            os.environ["PWD"] = old_pwd


def test_verification_skip_hit_only_when_all_match(
    fake_project: Path, tmp_path: Path
) -> None:
    """is_fresh returns marker only after mark_passed; different key returns None."""
    cache_dir = tmp_path / "cache"
    with patch.dict(os.environ, {"HARNESS_MAKER_CACHE_DIR": str(cache_dir)}):
        key = compute_skip_key(fake_project)

        assert is_fresh(key) is None

        mark_passed(key, project_root=str(fake_project))

        result = is_fresh(key)
        assert result is not None
        assert result["passed"] is True
        assert result["key"] == key

        assert is_fresh("totally-different-key") is None


def test_env_ignore_patterns() -> None:
    """SSH_*, WSL_*, WT_*, CLAUDE_CODE_* should be ignored."""
    assert _should_ignore_env("SSH_AUTH_SOCK")
    assert _should_ignore_env("WSL_DISTRO_NAME")
    assert _should_ignore_env("WT_SESSION")
    assert _should_ignore_env("CLAUDE_CODE_SESSION_ID")
    assert not _should_ignore_env("LANG")
    assert not _should_ignore_env("PATH")
    assert not _should_ignore_env("TZ")
