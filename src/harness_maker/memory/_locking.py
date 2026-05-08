"""Cross-process file lock for index-shape stores (semantic, profile).

POSIX `fcntl.flock(LOCK_EX)` serializes the read-modify-write block so two
concurrent sessions cannot race against each other. On platforms without
`fcntl` (Windows native, not WSL) the helper degrades to a no-op + warning;
the harness primarily targets POSIX-compatible environments (Linux, macOS,
WSL2) so the no-op path is acceptable graceful degradation, not the
default execution path.

**Lock files are permanent sentinels by design.** They accumulate one per
protected store directory (``index.lock``, ``profile.lock``), never grow
individually, and are never auto-deleted. Cleanup is the operator's
responsibility — `find .claude/memory -name '*.lock' -mtime +30 -delete`
is safe at any time since the file holds no data, only the flock anchor.
"""

from __future__ import annotations

import contextlib
import logging
import os
import threading
from collections.abc import Iterator
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    import fcntl

    _HAS_FCNTL = True
except ImportError:
    _HAS_FCNTL = False

# ADR-106 (0.7.1): per-thread depth counter keyed by full lock path string
# so the same thread can re-acquire the lock without deadlocking on its
# own flock fd. Cross-thread / cross-process serialisation is unaffected —
# flock is process-scoped, and the counter only suppresses a redundant
# in-process flock call from a re-entrant caller.
_LOCK_DEPTH = threading.local()


def _depth_get(key: str) -> int:
    return int(getattr(_LOCK_DEPTH, key, 0))


def _depth_set(key: str, value: int) -> None:
    setattr(_LOCK_DEPTH, key, value)


@contextlib.contextmanager
def exclusive_lock(lock_path: Path) -> Iterator[None]:
    """Hold an exclusive POSIX file lock on `lock_path` for the body.

    Round-2 Sec F6 hardening: the lock fd is opened with ``O_NOFOLLOW``
    (refuses to follow symlinks — defeats a symlink-redirect attack on
    the lock path) and mode ``0o600`` (owner-only — does not leak lock
    state to other local users). The fd uses ``O_WRONLY`` since this
    helper never reads or writes lock-file bytes; the file is purely a
    flock anchor.

    0.7.1 (ADR-106): re-entrant within a single thread — the same thread
    acquiring the same ``lock_path`` twice does not deadlock; the inner
    ``with`` block yields immediately. Tracked via ``threading.local``
    keyed by the absolute path string.
    """
    if not _HAS_FCNTL:
        logger.warning(
            "fcntl unavailable on this platform; concurrent writers to %s "
            "may race. Use a POSIX-compatible environment for safety.",
            lock_path,
        )
        yield
        return
    key = str(lock_path)
    if _depth_get(key) > 0:
        # Same thread already holds this lock — nested ``with`` is a no-op.
        _depth_set(key, _depth_get(key) + 1)
        try:
            yield
        finally:
            _depth_set(key, _depth_get(key) - 1)
        return
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW
    fd = os.open(str(lock_path), flags, 0o600)
    try:
        # Acquire flock BEFORE bumping depth — otherwise a sibling thread
        # / signal handler observing `_depth_get(key) > 0` would fast-path
        # past flock acquisition while we are still blocked. Equally, if
        # flock raises (EINTR, EBADF, etc.), the depth counter must remain
        # 0 so a retry can re-enter cleanly.
        fcntl.flock(fd, fcntl.LOCK_EX)
        _depth_set(key, 1)
        try:
            yield
        finally:
            _depth_set(key, 0)
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
            except OSError:
                # Best-effort: closing the fd will release the lock anyway.
                pass
    finally:
        os.close(fd)
