"""Cross-process file lock for index-shape stores (semantic, profile).

POSIX `fcntl.flock(LOCK_EX)` serializes the read-modify-write block so two
concurrent sessions cannot race against each other. On platforms without
`fcntl` (Windows native, not WSL) the helper degrades to a no-op + warning;
the harness primarily targets POSIX-compatible environments (Linux, macOS,
WSL2) so the no-op path is acceptable graceful degradation, not the
default execution path.
"""

from __future__ import annotations

import contextlib
import logging
import os
from collections.abc import Iterator
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    import fcntl

    _HAS_FCNTL = True
except ImportError:
    _HAS_FCNTL = False


@contextlib.contextmanager
def exclusive_lock(lock_path: Path) -> Iterator[None]:
    """Hold an exclusive POSIX file lock on `lock_path` for the body.

    Round-2 Sec F6 hardening: the lock fd is opened with ``O_NOFOLLOW``
    (refuses to follow symlinks — defeats a symlink-redirect attack on
    the lock path) and mode ``0o600`` (owner-only — does not leak lock
    state to other local users). The fd uses ``O_WRONLY`` since this
    helper never reads or writes lock-file bytes; the file is purely a
    flock anchor.
    """
    if not _HAS_FCNTL:
        logger.warning(
            "fcntl unavailable on this platform; concurrent writers to %s "
            "may race. Use a POSIX-compatible environment for safety.",
            lock_path,
        )
        yield
        return
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW
    fd = os.open(str(lock_path), flags, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)
