"""Unit tests for harness_maker.io_utils."""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

import pytest
import yaml

from harness_maker.io_utils import (
    LockTimeoutError,
    atomic_append,
    atomic_write,
    denormalize_home_to_tilde,
    load_harness_yaml,
    rmw_lock,
)


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


# ---------------------------------------------------------------------------
# load_harness_yaml — provenance-frontmatter-aware loader
# ---------------------------------------------------------------------------


def _provenance_frontmatter() -> str:
    """Frontmatter shape injected by render.py for harness.yaml."""
    return (
        "---\n"
        "generated_by: harness-maker\n"
        "harness_maker_version: 0.13.0\n"
        "generated_at: '2026-01-01T00:00:00+00:00'\n"
        "source_template: harness-yaml/Production.yaml.j2\n"
        "provenance: official\n"
        "content_hash: 384fc6d5a53752ffef038282975540251278615efdf76059ac7a75f668eee136\n"
        "---\n"
    )


def test_load_harness_yaml_returns_body_when_frontmatter_present(tmp_path: Path) -> None:
    """The renderer injects a provenance frontmatter block; loader returns the body doc.

    Why: production harness.yaml always has frontmatter (render._format_frontmatter).
    Single-document yaml.safe_load rejects multi-doc streams — this is the exact bug
    being fixed for the Second Brain loader.
    """
    yaml_path = tmp_path / "harness.yaml"
    body = "preset: Production\nlocale: ko\nsecond_brain:\n  enabled: true\n"
    yaml_path.write_text(_provenance_frontmatter() + body, encoding="utf-8")

    data = load_harness_yaml(yaml_path)

    assert data["preset"] == "Production"
    assert data["locale"] == "ko"
    assert data["second_brain"]["enabled"] is True
    # Must NOT return the frontmatter doc — that contains generated_by/content_hash.
    assert "generated_by" not in data
    assert "content_hash" not in data


def test_load_harness_yaml_handles_bare_file_without_frontmatter(tmp_path: Path) -> None:
    """Hand-written or pre-render harness.yaml has no frontmatter; loader still works."""
    yaml_path = tmp_path / "harness.yaml"
    yaml_path.write_text("preset: Side\nlocale: en\n", encoding="utf-8")

    data = load_harness_yaml(yaml_path)

    assert data == {"preset": "Side", "locale": "en"}


def test_load_harness_yaml_returns_empty_dict_for_empty_file(tmp_path: Path) -> None:
    """An empty harness.yaml returns {} rather than None — callers expect dict.get()."""
    yaml_path = tmp_path / "harness.yaml"
    yaml_path.write_text("", encoding="utf-8")

    data = load_harness_yaml(yaml_path)

    assert data == {}


def test_load_harness_yaml_returns_last_nonempty_document(tmp_path: Path) -> None:
    """Multi-doc YAML: last non-empty doc is the canonical user-data block.

    Why: render.py prepends provenance frontmatter as the FIRST doc; the user
    body is the LAST doc. The loader must pick the last so user data wins.
    """
    yaml_path = tmp_path / "harness.yaml"
    yaml_path.write_text(
        "---\nfirst: 1\n---\nsecond: 2\n---\nthird: 3\n",
        encoding="utf-8",
    )

    data = load_harness_yaml(yaml_path)

    assert data == {"third": 3}


def test_load_harness_yaml_raises_for_missing_file(tmp_path: Path) -> None:
    """Missing file → FileNotFoundError (caller decides how to surface)."""
    with pytest.raises(FileNotFoundError):
        load_harness_yaml(tmp_path / "does-not-exist.yaml")


def test_load_harness_yaml_raises_for_malformed_yaml(tmp_path: Path) -> None:
    """Genuinely malformed YAML surfaces yaml.YAMLError to the caller."""
    yaml_path = tmp_path / "harness.yaml"
    yaml_path.write_text("preset: [unclosed\n  bracket\n", encoding="utf-8")

    with pytest.raises(yaml.YAMLError):
        load_harness_yaml(yaml_path)


def test_load_harness_yaml_returns_empty_dict_for_top_level_sequence(
    tmp_path: Path,
) -> None:
    """Top-level sequence is invalid for harness.yaml → empty dict fallback.

    Why: harness.yaml is by contract a mapping; surfacing a list would crash
    callers deeper than necessary. Empty-dict gives a clean validation point.
    """
    yaml_path = tmp_path / "harness.yaml"
    yaml_path.write_text("- one\n- two\n", encoding="utf-8")

    data = load_harness_yaml(yaml_path)

    assert data == {}


def test_load_harness_yaml_skips_provenance_only_truncated_write(
    tmp_path: Path,
) -> None:
    """A file containing ONLY provenance (truncated write) returns {} not provenance.

    Regression: REVIEW-2026-05-17 P1 — earlier loader returned the provenance
    block as user data when the body had not yet been flushed (WSL2/NTFS
    partial-write scenario named in CLAUDE.md §실행 주의).
    """
    yaml_path = tmp_path / "harness.yaml"
    yaml_path.write_text(_provenance_frontmatter(), encoding="utf-8")

    data = load_harness_yaml(yaml_path)

    assert data == {}
    assert "generated_by" not in data
    assert "content_hash" not in data


def test_atomic_append_refuses_a_line_over_pipe_buf(tmp_path: Path) -> None:
    """Over PIPE_BUF the O_APPEND write is no longer atomic between concurrent writers;
    the helper must refuse loudly rather than silently interleave (same guard as the
    telemetry / stage-agent ledger writers)."""
    target = tmp_path / "ledger.jsonl"
    with pytest.raises(ValueError, match="PIPE_BUF"):
        atomic_append(target, "x" * 4097 + "\n")
    assert not target.exists() or target.read_text() == ""


def test_atomic_append_writes_the_whole_line(tmp_path: Path) -> None:
    target = tmp_path / "ledger.jsonl"
    atomic_append(target, "a\n")
    atomic_append(target, "b\n")
    assert target.read_text() == "a\nb\n"


def test_atomic_append_never_retries_a_short_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A retry would let a peer's append land between the two syscalls and splice the
    rows; the helper raises instead (the contract `append_atomic_line` documents)."""
    calls: list[int] = []
    real_write = os.write

    def short_write(fd: int, data: bytes) -> int:
        calls.append(len(data))
        return real_write(fd, data[: len(data) // 2])

    monkeypatch.setattr(os, "write", short_write)
    with pytest.raises(OSError, match="short append"):
        atomic_append(tmp_path / "ledger.jsonl", "abcdef\n")
    assert calls == [7], "exactly one write() attempt — no retry loop"


# ── rmw_lock (SPEC-mutation-survivors-and-approval-p2s, AC-004/AC-005) ──────────


def _hold_the_lock(lock_path: str, ready: Any, release: Any) -> None:  # pragma: no cover - child
    from harness_maker.io_utils import rmw_lock as _rmw_lock

    with _rmw_lock(Path(lock_path), timeout=5.0):
        ready.set()
        release.wait(timeout=30)


def test_a_held_lock_times_out_instead_of_blocking(tmp_path: Path) -> None:
    """Real `flock`, no monkeypatch — this is the only test that binds the actual flags.

    The 2026-09-20 mutation run left `fcntl.flock(fd, LOCK_EX | LOCK_NB)` alive: every other
    lock test patches `fcntl`, so nothing noticed what the flags were. Dropping `LOCK_NB`
    makes the second writer BLOCK instead of polling, and a blocked writer never reaches the
    deadline — the timeout contract silently becomes "wait forever". The wall-clock bound
    below is what makes that visible: a blocking mutant fails by exhausting the 30 s join,
    not by raising something else.
    """
    import multiprocessing

    ctx = multiprocessing.get_context("fork")
    ready, release = ctx.Event(), ctx.Event()
    lock_path = tmp_path / "obs" / ".hm-spec-demo.lock"
    holder = ctx.Process(target=_hold_the_lock, args=(str(lock_path), ready, release))
    holder.start()
    try:
        assert ready.wait(timeout=30), "the holder never acquired the lock"
        started = time.monotonic()
        with pytest.raises(LockTimeoutError), rmw_lock(lock_path, timeout=0.3):
            pass  # pragma: no cover - the lock is held, so this never runs
        waited = time.monotonic() - started
        assert 0.3 <= waited < 10, f"waited {waited:.2f}s — not the declared budget"
    finally:
        release.set()
        holder.join(timeout=30)
    assert holder.exitcode == 0


def test_an_uncontended_lock_is_released_on_exit(tmp_path: Path) -> None:
    """The `finally: os.close(fd)` arm — a leaked descriptor holds the lock for the process."""
    lock_path = tmp_path / "obs" / ".hm-spec-demo.lock"
    for _ in range(3):
        with rmw_lock(lock_path, timeout=0.5):
            pass
    assert lock_path.exists()
    # The creation mode, which the 2026-09-20 run left alive: the lock names a path inside the
    # project, and a world-writable one lets any local account stall this repo's writers.
    assert lock_path.stat().st_mode & 0o777 == 0o600
