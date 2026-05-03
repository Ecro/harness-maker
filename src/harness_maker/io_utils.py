"""Atomic file I/O helpers."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path


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
    os.replace(tmp_path, path)
