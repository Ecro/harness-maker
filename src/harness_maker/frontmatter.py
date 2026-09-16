"""One byte-level YAML-frontmatter splitter; the body comes back as the ORIGINAL bytes (ADR-009)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Literal

import yaml

Status = Literal["ok", "missing", "unterminated", "invalid_yaml", "non_mapping"]

_BOM = b"\xef\xbb\xbf"
_OPEN = re.compile(rb"\A---[ \t]*\r?\n")
_CLOSE = re.compile(rb"^---[ \t]*\r?\n", re.MULTILINE)


@dataclass(frozen=True)
class Split:
    """`body` is a byte slice of the input after the closing fence — never re-encoded.

    `missing`, `unterminated` and `invalid_yaml` carry the ORIGINAL input (BOM included) as
    `body`, so a caller that treats the file as prose loses nothing; `non_mapping` carries the
    bytes after the closing fence, exactly as `ok` does, because the fence was found and the
    only defect is the frontmatter's shape (review findings b3663bc9 / 7ca445f5). `mapping` is
    None outside `ok` so an empty mapping stays distinguishable from "there was no frontmatter".
    """

    status: Status
    mapping: dict[str, Any] | None
    body: bytes
    error: str | None = None


def split_frontmatter(data: bytes) -> Split:
    """Why bytes: `Path.read_text` translates CRLF and a `str` fence match cannot say which
    bytes the body started at. A BOM is tolerated on the first line only and never reaches YAML."""
    original = data
    if data.startswith(_BOM):
        data = data[len(_BOM) :]
    opened = _OPEN.match(data)
    if opened is None:
        return Split("missing", None, original, "no frontmatter fence on the first line")
    closed = _CLOSE.search(data, opened.end())
    if closed is None:
        return Split("unterminated", None, original, "frontmatter fence never closed")
    raw = data[opened.end() : closed.start()]
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        return Split("invalid_yaml", None, original, f"frontmatter is not UTF-8: {exc}")
    try:
        parsed = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        return Split("invalid_yaml", None, original, f"frontmatter is not valid YAML: {exc}")
    if parsed is None:
        parsed = {}
    body = data[closed.end() :]
    if not isinstance(parsed, dict):
        return Split("non_mapping", None, body, "frontmatter must be a mapping")
    return Split("ok", parsed, body)
