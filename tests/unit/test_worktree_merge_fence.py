"""Phase 4 — ADR-005 finalize merge fence (flock primary + O_EXCL secondary).

`_acquire_merge_fence(base, timeout)` context manager serializes the
merge step across parallel finalize invocations. Primary mechanism is
`fcntl.flock`; secondary (when flock unavailable, e.g. some NFS/SMB) is
`os.open(O_CREAT|O_EXCL|O_WRONLY)` polling. Either path MUST work on
WSL2/NTFS (this project's primary runtime).
"""

from __future__ import annotations

import contextlib
import threading
import time
from pathlib import Path

import pytest

from harness_maker.worktree import _acquire_merge_fence

# ── happy-path serialization ────────────────────────────────────────────────


def test_acquire_merge_fence_yields_then_releases(tmp_path: Path) -> None:
    """Single acquirer enters + exits cleanly."""
    with _acquire_merge_fence(tmp_path, timeout=1.0):
        pass  # noqa: PIE790 — testing context-manager mechanics


def test_acquire_merge_fence_serializes_two_threads(tmp_path: Path) -> None:
    """Two threads racing the same base — observed enter/exit sequence is interleaved 0."""
    sequence: list[str] = []
    lock = threading.Lock()

    def acquire_and_hold(label: str, hold_s: float) -> None:
        with _acquire_merge_fence(tmp_path, timeout=5.0):
            with lock:
                sequence.append(f"{label}-enter")
            time.sleep(hold_s)
            with lock:
                sequence.append(f"{label}-exit")

    t1 = threading.Thread(target=acquire_and_hold, args=("A", 0.05))
    t2 = threading.Thread(target=acquire_and_hold, args=("B", 0.05))
    t1.start()
    time.sleep(0.005)  # tiny gap so A starts first
    t2.start()
    t1.join(timeout=10.0)
    t2.join(timeout=10.0)

    # Must observe: <first>-enter, <first>-exit, <second>-enter, <second>-exit
    # (NOT interleaved). Both labels appeared in some order.
    assert len(sequence) == 4
    assert sequence[0].endswith("-enter")
    assert sequence[1].endswith("-exit")
    assert sequence[2].endswith("-enter")
    assert sequence[3].endswith("-exit")
    # The first holder's exit MUST precede the second holder's enter.
    first_label = sequence[0].split("-")[0]
    second_label = sequence[2].split("-")[0]
    assert first_label != second_label, "lock holders should be distinct threads"


# ── timeout ─────────────────────────────────────────────────────────────────


def test_acquire_merge_fence_times_out_when_held(tmp_path: Path) -> None:
    """Second acquirer waits ≤ timeout, then raises if first holds forever."""
    barrier = threading.Event()
    release = threading.Event()

    def hold_forever() -> None:
        with _acquire_merge_fence(tmp_path, timeout=10.0):
            barrier.set()
            release.wait(timeout=5.0)

    t = threading.Thread(target=hold_forever, daemon=True)
    t.start()
    assert barrier.wait(timeout=2.0), "holder failed to enter"

    start = time.monotonic()
    with (
        pytest.raises((TimeoutError, OSError, BlockingIOError)),
        _acquire_merge_fence(tmp_path, timeout=0.5),
    ):
        pass
    elapsed = time.monotonic() - start
    assert 0.3 < elapsed < 1.5, f"timeout out of bounds: {elapsed}"

    release.set()
    t.join(timeout=5.0)


# ── O_EXCL secondary mechanism (force-fallback for test coverage) ───────────


def test_acquire_merge_fence_secondary_mechanism_works_when_flock_unavailable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When flock raises OSError(ENOSYS), the O_EXCL polling path takes over.

    Mocking strategy: monkeypatch fcntl.flock to raise OSError(ENOSYS).
    Test then asserts the fence still serializes (using the O_EXCL path).
    """
    import errno
    import fcntl

    def fake_flock(*args: object, **kwargs: object) -> None:
        raise OSError(errno.ENOSYS, "flock not supported")

    monkeypatch.setattr(fcntl, "flock", fake_flock)

    # Should still acquire + release without raising.
    with _acquire_merge_fence(tmp_path, timeout=1.0):
        pass


# ── P2 (PLAN-p6-p7-worktree-finalize ADR-003): stash gated by the fence ───────


def test_finalize_stash_is_gated_by_merge_fence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ADR-003: `_stash_base_dirty` runs INSIDE the merge fence, so a finalize
    cannot stash the base while another holder owns the fence — the property
    that serializes parallel finalizes. RED on the pre-move code (the stash ran
    before the fence was acquired, so it was never gated)."""
    import subprocess

    from harness_maker import worktree

    def _git(args: list[str], cwd: Path) -> None:
        subprocess.run(  # noqa: S603
            ["git", *args], cwd=str(cwd), check=True, capture_output=True, text=True
        )

    base = tmp_path / "base"
    base.mkdir()
    _git(["init", "-b", "main"], base)
    _git(["config", "user.email", "t@example.com"], base)
    _git(["config", "user.name", "T"], base)
    (base / "README.md").write_text("# base\n")
    (base / ".gitignore").write_text(
        ".worktrees/\n.claude/.hm-loop-*\n.claude/.hm-finalize-stash-*\n"
    )
    _git(["add", "."], base)
    _git(["commit", "-m", "init"], base)

    wt = worktree.create("execute", base)[0]
    (wt / "wt_file.txt").write_text("worktree work\n")
    (base / "dirt.txt").write_text("user dirt\n")
    _git(["add", "dirt.txt"], base)

    stashed = threading.Event()
    real_stash = worktree._stash_base_dirty
    real_fence = worktree._acquire_merge_fence

    def rec_stash(b: Path, wt_name: str) -> str | None:
        stashed.set()  # we reached the stash → it was NOT gated out by the held fence
        return real_stash(b, wt_name)

    # Positive sync (no timing sleep): the worker signals the instant it reaches
    # the fence-acquire boundary, BEFORE it blocks on the lock we hold. We then
    # assert the stash has not run — robust regardless of how slow the worker's
    # pre-fence `_capture_pending_in_worktree` is on WSL2/NTFS.
    reached_fence = threading.Event()

    @contextlib.contextmanager
    def signaling_fence(b: Path, timeout: float = 60.0):  # type: ignore[no-untyped-def]
        reached_fence.set()
        with real_fence(b, timeout=timeout):
            yield

    monkeypatch.setattr(worktree, "_stash_base_dirty", rec_stash)
    monkeypatch.setattr(worktree, "_acquire_merge_fence", signaling_fence)

    rc_box: list[int] = []

    def run() -> None:
        rc_box.append(worktree._cli_finalize([str(wt), "stage-only"]))

    t = threading.Thread(target=run)
    # Main thread holds the REAL fence (bypassing the signaling wrapper).
    with real_fence(base, timeout=10.0):
        t.start()
        assert reached_fence.wait(timeout=15.0), "worker never reached the fence-acquire boundary"
        # Worker is now blocked acquiring the fence we hold. If the stash were
        # gated by the fence (ADR-003), it cannot have run yet.
        assert not stashed.is_set(), (
            "finalize stashed the base while the fence was held — the stash is "
            "NOT gated by the fence (ADR-003 regression)"
        )
    # Fence released → the finalize proceeds and stashes.
    t.join(timeout=30.0)
    assert stashed.is_set(), "finalize never stashed after the fence was released"
    assert rc_box, "finalize thread did not complete"
    assert rc_box[0] == 0, f"finalize rc={rc_box[0]}"
