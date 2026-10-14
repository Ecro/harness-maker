"""Save and load named durations as a JSON file, atomically."""

from __future__ import annotations

import contextlib
import json
import os
import tempfile
from pathlib import Path

from timeparse.parse import parse_duration


def save_durations(path: str | os.PathLike[str], mapping: dict[str, str]) -> None:
    """Validate every value first, then replace the file in one step."""
    if not isinstance(mapping, dict):
        raise TypeError("mapping must be a dict")
    seconds: dict[str, int] = {}
    for name, text in mapping.items():
        try:
            seconds[name] = parse_duration(text)
        except (ValueError, AttributeError) as exc:
            raise ValueError(f"invalid duration for {name!r}: {text!r}") from exc
    target = Path(path)
    fd, tmp = tempfile.mkstemp(dir=target.parent, prefix=f".{target.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(seconds, handle)
        os.replace(tmp, target)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise


def load_durations(path: str | os.PathLike[str]) -> dict[str, int]:
    """Return the stored mapping, or {} when the file does not exist."""
    target = Path(path)
    if not target.exists():
        return {}
    data = json.loads(target.read_text(encoding="utf-8"))
    return {str(k): int(v) for k, v in data.items()}
