"""Unit tests for harness_maker.detection_cache (Phase 2 of personalization-depth)."""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from pathlib import Path

import pytest

from harness_maker.detection_cache import _repo_hash, load_or_run, write
from harness_maker.models import ProjectProfile


def _make_profile(stack: list[str] | None = None) -> ProjectProfile:
    return ProjectProfile(
        stack=stack if stack is not None else ["python"],
        scale="small",
        lifecycle="dormant",
        existing_dotclaude=False,
        spec_only=False,
        vault_member=False,
        detected_checks=["uv run ruff check ."],
    )


def test_load_returns_none_when_no_cache(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    cache_dir = tmp_path / "cache"
    assert load_or_run(repo, cache_dir=cache_dir) is None


def test_write_then_load_round_trip(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    cache_dir = tmp_path / "cache"
    profile = _make_profile(stack=["python", "rust"])

    write(profile, repo, cache_dir=cache_dir)
    loaded = load_or_run(repo, cache_dir=cache_dir)

    assert loaded is not None
    assert loaded.stack == ["python", "rust"]
    assert loaded.scale == "small"
    assert loaded.detected_checks == ["uv run ruff check ."]


def test_load_returns_none_after_manifest_mtime_bump(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    cache_dir = tmp_path / "cache"
    manifest = repo / "pyproject.toml"
    manifest.write_text("[project]\nname='x'\n", encoding="utf-8")

    write(_make_profile(), repo, cache_dir=cache_dir)

    # Move the manifest mtime forward — it must look newer than the cache file.
    cache_file = cache_dir / f"profile-{_repo_hash(repo)}.json"
    cache_mtime = cache_file.stat().st_mtime
    future = cache_mtime + 100.0
    os.utime(manifest, (future, future))

    assert load_or_run(repo, cache_dir=cache_dir) is None


def test_load_returns_none_after_24h_ceiling(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    cache_dir = tmp_path / "cache"

    write(_make_profile(), repo, cache_dir=cache_dir)

    cache_file = cache_dir / f"profile-{_repo_hash(repo)}.json"
    real_mtime = cache_file.stat().st_mtime
    # Pretend "now" is 25h after the cache was written.
    fake_now = real_mtime + 25 * 60 * 60
    monkeypatch.setattr(time, "time", lambda: fake_now)

    assert load_or_run(repo, cache_dir=cache_dir) is None


def test_cache_path_keyed_by_repo_sha256(tmp_path: Path) -> None:
    repo_a = tmp_path / "repo_a"
    repo_b = tmp_path / "repo_b"
    repo_a.mkdir()
    repo_b.mkdir()
    cache_dir = tmp_path / "cache"

    write(_make_profile(stack=["python"]), repo_a, cache_dir=cache_dir)
    write(_make_profile(stack=["rust"]), repo_b, cache_dir=cache_dir)

    file_a = cache_dir / f"profile-{_repo_hash(repo_a)}.json"
    file_b = cache_dir / f"profile-{_repo_hash(repo_b)}.json"
    assert file_a.exists()
    assert file_b.exists()
    assert file_a != file_b

    a_loaded = load_or_run(repo_a, cache_dir=cache_dir)
    b_loaded = load_or_run(repo_b, cache_dir=cache_dir)
    assert a_loaded is not None
    assert a_loaded.stack == ["python"]
    assert b_loaded is not None
    assert b_loaded.stack == ["rust"]


def test_corruption_recovery(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()

    cache_file = cache_dir / f"profile-{_repo_hash(repo)}.json"
    cache_file.write_text("{not valid json", encoding="utf-8")

    caplog.set_level(logging.WARNING, logger="harness_maker.detection_cache")
    result = load_or_run(repo, cache_dir=cache_dir)

    assert result is None
    assert not cache_file.exists(), "corrupt cache file must be deleted"
    assert any("corrupt cache" in rec.message for rec in caplog.records)


def test_concurrent_writes_no_tear(tmp_path: Path) -> None:
    """Validator C2: under repeated concurrent writes, the cache never tears.

    A single race window can pass by luck; loop N=50 iterations to exercise
    diverse thread interleavings and catch any rare torn write.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    cache_dir = tmp_path / "cache"

    profile_one = _make_profile(stack=["python"])
    profile_two = _make_profile(stack=["rust"])

    cache_file = cache_dir / f"profile-{_repo_hash(repo)}.json"

    def _writer(
        p: ProjectProfile,
        barrier: threading.Barrier,
        errors: list[BaseException],
    ) -> None:
        try:
            barrier.wait(timeout=5.0)
            write(p, repo, cache_dir=cache_dir)
        except BaseException as exc:  # noqa: BLE001 - propagated to assert below
            errors.append(exc)

    for iteration in range(50):
        barrier = threading.Barrier(2, timeout=5.0)
        errors: list[BaseException] = []

        threads = [
            threading.Thread(target=_writer, args=(profile_one, barrier, errors)),
            threading.Thread(target=_writer, args=(profile_two, barrier, errors)),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10.0)
            assert not t.is_alive(), f"writer thread hung at iteration {iteration}"

        assert errors == [], f"writer raised at iteration {iteration}: {errors!r}"

        assert cache_file.exists(), f"cache missing after iteration {iteration}"

        # Last-writer-wins is documented (ADR-008). The cache MUST be a valid
        # ProjectProfile — atomic_write guarantees no half-written tears.
        raw = cache_file.read_text(encoding="utf-8")
        parsed = ProjectProfile.model_validate_json(raw)
        assert parsed.stack in (["python"], ["rust"]), (
            f"unexpected stack at iteration {iteration}: {parsed.stack!r}"
        )


def test_cache_invalidated_when_stack_glob_concrete_manifest_changes(
    tmp_path: Path,
) -> None:
    """STACK_GLOB_MANIFESTS literal `stack.yaml` triggers cache invalidation.

    Closes the Phase 3 gap for concrete filenames inside STACK_GLOB_MANIFESTS
    (haskell's `stack.yaml` / `package.yaml`). ``*``-pattern globs (csharp's
    ``*.csproj`` / ``*.sln``) still rely on the 24h ceiling.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    cache_dir = tmp_path / "cache"
    manifest = repo / "stack.yaml"
    manifest.write_text("# minimal stack.yaml\n", encoding="utf-8")

    write(_make_profile(stack=["haskell"]), repo, cache_dir=cache_dir)

    cached = load_or_run(repo, cache_dir=cache_dir)
    assert cached is not None
    assert cached.stack == ["haskell"]

    # Deterministic mtime bump — avoids racy filesystem mtime resolution.
    cache_file = cache_dir / f"profile-{_repo_hash(repo)}.json"
    cache_mtime = cache_file.stat().st_mtime
    future = cache_mtime + 100.0
    os.utime(manifest, (future, future))

    assert load_or_run(repo, cache_dir=cache_dir) is None, (
        "Cache must invalidate when stack.yaml mtime > cache mtime"
    )


def test_cache_invalidated_when_package_yaml_changes(tmp_path: Path) -> None:
    """STACK_GLOB_MANIFESTS `package.yaml` (haskell) triggers cache invalidation."""
    repo = tmp_path / "repo"
    repo.mkdir()
    cache_dir = tmp_path / "cache"
    manifest = repo / "package.yaml"
    manifest.write_text("name: foo\n", encoding="utf-8")

    write(_make_profile(stack=["haskell"]), repo, cache_dir=cache_dir)
    assert load_or_run(repo, cache_dir=cache_dir) is not None

    cache_file = cache_dir / f"profile-{_repo_hash(repo)}.json"
    cache_mtime = cache_file.stat().st_mtime
    future = cache_mtime + 100.0
    os.utime(manifest, (future, future))

    assert load_or_run(repo, cache_dir=cache_dir) is None


def test_backward_compat_old_cache_loads(tmp_path: Path) -> None:
    """Old cache JSON lacking Phase-1 fields must load via ProjectProfile defaults."""
    repo = tmp_path / "repo"
    repo.mkdir()
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()

    legacy_payload = {
        "stack": ["python"],
        "scale": "small",
        "lifecycle": "dormant",
        "existing_dotclaude": False,
        "spec_only": False,
        "vault_member": False,
        "detected_checks": ["uv run ruff check ."],
        # No frameworks / package_manager / ci_provider / foreign_ai_configs /
        # detection_confidence — simulating a pre-Phase-1 cache file.
    }
    cache_file = cache_dir / f"profile-{_repo_hash(repo)}.json"
    cache_file.write_text(json.dumps(legacy_payload), encoding="utf-8")

    loaded = load_or_run(repo, cache_dir=cache_dir)

    assert loaded is not None
    assert loaded.stack == ["python"]
    assert loaded.frameworks == []
    assert loaded.package_manager == ""
    assert loaded.ci_provider == ""
    assert loaded.foreign_ai_configs == []
    assert loaded.detection_confidence == {}
