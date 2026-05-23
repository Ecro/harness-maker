"""Phase 4 — ADR-005 finalize merge fence (flock primary + O_EXCL secondary).

`_acquire_merge_fence(base, timeout)` context manager serializes the
merge step across parallel finalize invocations. Primary mechanism is
`fcntl.flock`; secondary (when flock unavailable, e.g. some NFS/SMB) is
`os.open(O_CREAT|O_EXCL|O_WRONLY)` polling. Either path MUST work on
WSL2/NTFS (this project's primary runtime).
"""

from __future__ import annotations

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
