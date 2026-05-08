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
    """Hold an exclusive POSIX file lock on `lock_path` for the body."""
    if not _HAS_FCNTL:
        logger.warning(
            "fcntl unavailable on this platform; concurrent writers to %s "
            "may race. Use a POSIX-compatible environment for safety.",
            lock_path,
        )
        yield
        return
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(lock_path), os.O_RDWR | os.O_CREAT, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)
