"""Content-fingerprint locators for assumption evidence: capture, classify, shape-check."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

MAX_SPAN = 40
LOCATOR_KEYS: frozenset[str] = frozenset({"path", "lines", "fingerprint", "k"})
#: Bounded digits: an unbounded `\d+` handed `int()` past its digit limit, which raised a bare
#: ValueError that no caller catches — a crash where every other bad citation is a refusal.
_SPEC_RE = re.compile(r"^(?P<path>.+):(?P<a>\d{1,9})-(?P<b>\d{1,9})$")
_FP_RE = re.compile(r"[0-9a-f]{64}")


class LocatorError(ValueError):
    def __init__(self, field: str, message: str) -> None:
        self.field = field
        self.message = message
        super().__init__(f"{field}: {message}")


@dataclass(frozen=True)
class Freshness:
    state: str
    line: int | None = None


def _norm(line: str) -> str:
    return " ".join(line.split())


def _digest(normalized: Sequence[str]) -> str:
    return hashlib.sha256("\n".join(normalized).encode("utf-8")).hexdigest()


def _normalized(lines: Sequence[str]) -> list[str]:
    return [n for n in (_norm(line) for line in lines) if n]


def fingerprint(lines: Sequence[str]) -> str:
    """The one owner of the persisted format: `capture` and `classify` both hash through here.

    Whitespace-only edits (reindent, reflow spacing, blank lines, CRLF) must not move it.
    """
    return _digest(_normalized(lines))


def _path_error(path: Any) -> str | None:
    if not isinstance(path, str) or not path.strip():
        return "path must be a non-empty string"
    pure = PurePosixPath(path)
    if pure.is_absolute() or path.startswith(("/", "\\")):
        return f"path {path!r} must be relative to the checkout root"
    if ".." in pure.parts:
        return f"path {path!r} must not contain '..'"
    return None


def _read_lines(root: Path, path: str) -> list[str]:
    """Every file-state failure becomes a LocatorError — callers decide refuse vs `missing`."""
    try:
        base = root.resolve()
        target = (root / path).resolve()
        target.relative_to(base)
    except ValueError:
        raise LocatorError("locator", f"{path!r} resolves outside the checkout root") from None
    except (OSError, RuntimeError) as exc:
        raise LocatorError("locator", f"{path!r} cannot be resolved: {exc}") from exc
    try:
        if not target.is_file():
            raise LocatorError("locator", f"{path!r} is not an existing file")
        text = target.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        raise LocatorError("locator", f"{path!r} is not UTF-8 text") from None
    except OSError as exc:
        raise LocatorError("locator", f"{path!r} cannot be read: {exc}") from exc
    return text.splitlines()


def capture(root: Path, spec: str) -> dict[str, Any]:
    """Validate `path:A-B` against the file as it is now and build the stored locator."""
    m = _SPEC_RE.match(spec or "")
    if m is None:
        raise LocatorError("locator", f"{spec!r} is not <path>:<A>-<B>")
    path, a, b = m["path"], int(m["a"]), int(m["b"])
    err = _path_error(path)
    if err is not None:
        raise LocatorError("locator", err)
    if a < 1 or a > b:
        raise LocatorError("locator", f"span {a}-{b} must satisfy 1 <= A <= B")
    if b - a + 1 > MAX_SPAN:
        raise LocatorError("locator", f"span {a}-{b} is longer than {MAX_SPAN} lines")
    lines = _read_lines(root, path)
    if b > len(lines):
        raise LocatorError("locator", f"span {a}-{b} is past the last line ({len(lines)})")
    span = lines[a - 1 : b]
    k = len(_normalized(span))
    if not k:
        raise LocatorError("locator", f"span {a}-{b} has no non-blank line")
    return {"path": path, "lines": [a, b], "fingerprint": fingerprint(span), "k": k}


def classify(root: Path, locator: Mapping[str, Any]) -> Freshness:
    """Never raises on file state: anything that stops the read is `missing`."""
    try:
        lines = _read_lines(root, str(locator["path"]))
    except LocatorError:
        return Freshness("missing")
    start, k, fp = int(locator["lines"][0]), int(locator["k"]), str(locator["fingerprint"])
    entries = [(i, n) for i, n in ((i, _norm(line)) for i, line in enumerate(lines, 1)) if n]
    anchor = next((j for j, (lineno, _) in enumerate(entries) if lineno >= start), None)
    window = entries[anchor : anchor + k] if anchor is not None else []
    if len(window) == k and fingerprint([n for _, n in window]) == fp:
        return Freshness("fresh")
    for j in range(len(entries) - k + 1):
        if j != anchor and fingerprint([n for _, n in entries[j : j + k]]) == fp:
            return Freshness("moved", entries[j][0])
    return Freshness("changed")


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def shape_error(raw: Any) -> str | None:
    """The file-independent invariants `capture` guarantees, checked on a stored locator."""
    if not isinstance(raw, dict):
        return "locator must be a mapping"
    if set(raw) != LOCATOR_KEYS:
        return f"locator keys must be exactly {sorted(LOCATOR_KEYS)}"
    err = _path_error(raw["path"])
    if err is not None:
        return err
    lines = raw["lines"]
    if not isinstance(lines, list) or len(lines) != 2 or not all(_is_int(x) for x in lines):
        return "lines must be a list of two integers"
    a, b = lines
    if a < 1 or a > b or b - a + 1 > MAX_SPAN:
        return f"lines {a}-{b} must satisfy 1 <= A <= B and span at most {MAX_SPAN}"
    if not isinstance(raw["fingerprint"], str) or not _FP_RE.fullmatch(raw["fingerprint"]):
        return "fingerprint must be 64 lowercase hex characters"
    k = raw["k"]
    if not _is_int(k) or not 1 <= k <= b - a + 1:
        return f"k must be an integer between 1 and the span length ({b - a + 1})"
    return None
