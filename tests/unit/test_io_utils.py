"""Unit tests for harness_maker.io_utils."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from harness_maker.io_utils import atomic_write, denormalize_home_to_tilde


def test_atomic_write_str_round_trip(tmp_path: Path) -> None:
    target = tmp_path / "out.txt"
    atomic_write(target, "hello")
    assert target.read_text(encoding="utf-8") == "hello"


def test_atomic_write_bytes_round_trip(tmp_path: Path) -> None:
    target = tmp_path / "out.bin"
    atomic_write(target, b"\x00\x01\x02hello")
    assert target.read_bytes() == b"\x00\x01\x02hello"


def test_atomic_write_creates_parent_dirs(tmp_path: Path) -> None:
    target = tmp_path / "deep" / "nested" / "out.txt"
    atomic_write(target, "ok")
    assert target.read_text(encoding="utf-8") == "ok"


def test_atomic_write_cleans_up_tempfile_on_replace_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression: tempfile must not leak when os.replace raises (WSL2/NTFS EXDEV)."""
    target = tmp_path / "out.txt"

    def boom(*_args: object, **_kwargs: object) -> None:
        raise OSError("simulated EXDEV")

    monkeypatch.setattr(os, "replace", boom)

    with pytest.raises(OSError, match="simulated EXDEV"):
        atomic_write(target, "hello")

    # NamedTemporaryFile defaults yield names starting with "tmp" inside tmp_path.
    # After the failed replace + cleanup, no tempfile entries should remain there,
    # and the target itself must not exist.
    leftovers = [p for p in tmp_path.iterdir() if p.is_file()]
    assert leftovers == [], f"orphaned tempfiles after replace failure: {leftovers}"
    assert not target.exists()


def test_atomic_write_bytes_cleans_up_tempfile_on_replace_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression: bytes path must also clean up tempfile on os.replace failure."""
    target = tmp_path / "out.bin"

    def boom(*_args: object, **_kwargs: object) -> None:
        raise OSError("simulated EXDEV")

    monkeypatch.setattr(os, "replace", boom)

    with pytest.raises(OSError, match="simulated EXDEV"):
        atomic_write(target, b"payload")

    leftovers = [p for p in tmp_path.iterdir() if p.is_file()]
    assert leftovers == [], f"orphaned tempfiles after replace failure: {leftovers}"
    assert not target.exists()


def test_denormalize_home_to_tilde_exact_home(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", "/home/alice")
    monkeypatch.setattr(Path, "home", lambda: Path("/home/alice"))
    assert denormalize_home_to_tilde("/home/alice") == "~"


def test_denormalize_home_to_tilde_under_home(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", "/home/alice")
    monkeypatch.setattr(Path, "home", lambda: Path("/home/alice"))
    assert denormalize_home_to_tilde("/home/alice/projects/x") == "~/projects/x"


def test_denormalize_home_to_tilde_outside_home(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", "/home/alice")
    monkeypatch.setattr(Path, "home", lambda: Path("/home/alice"))
    assert denormalize_home_to_tilde("/etc/passwd") == "/etc/passwd"
