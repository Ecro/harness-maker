"""Atomic file I/O helpers."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path


def denormalize_home_to_tilde(path_str: str) -> str:
    """Convert a literal $HOME-prefixed absolute path back to ``~/...``.

    Bash expands unquoted ``~/foo`` at variable assignment time
    (``VAR=~/foo`` → ``VAR=/home/alice/foo``), so the CLI receives the
    machine-specific absolute path even though the user typed ``~/foo``.
    Storing that in ``harness.yaml`` breaks team sharing — teammate Bob has
    ``/home/bob``, not ``/home/alice``. Re-prefixing with ``~`` makes the path
    portable while still resolving correctly on every machine via
    ``Path(...).expanduser()`` downstream.
    """
    home = str(Path.home())
    if path_str == home:
        return "~"
    if path_str.startswith(home + "/"):
        return "~/" + path_str[len(home) + 1 :]
    return path_str


def atomic_write(path: Path, content: str | bytes, *, encoding: str = "utf-8") -> None:
    """Write content to path atomically: tempfile + os.replace."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, bytes):
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=path.parent,
            delete=False,
        ) as tmp_b:
            tmp_b.write(content)
            tmp_b.flush()
            os.fsync(tmp_b.fileno())
            tmp_path = Path(tmp_b.name)
    else:
        with tempfile.NamedTemporaryFile(
            mode="w",
            dir=path.parent,
            delete=False,
            encoding=encoding,
            newline="",
        ) as tmp_t:
            tmp_t.write(content)
            tmp_t.flush()
            os.fsync(tmp_t.fileno())
            tmp_path = Path(tmp_t.name)
    try:
        os.replace(tmp_path, path)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise
