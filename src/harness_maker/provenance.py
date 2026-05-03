"""Provenance verification (Phase 10 Task 8.6).

Every harness-maker generated file carries YAML frontmatter with `content_hash`
(sha256 of the normalized body bytes) and `source_template` (the .j2 origin).
This module verifies that a file on disk still matches the recorded hash —
mismatch = the user has hand-edited it and `/hm:refresh` must NOT silently
overwrite.

Re-exports `parse_frontmatter` and `compute_body_hash` from reconcile so callers
can stay on a single import surface; the underlying implementations are shared
with the Reconciler to keep normalization rules in one place.
"""

from __future__ import annotations

from pathlib import Path

from harness_maker.reconcile import compute_body_hash
from harness_maker.reconcile import parse_frontmatter as _parse_fm

__all__ = [
    "compute_hash",
    "parse_frontmatter",
    "verify_file",
]


def parse_frontmatter(file_path: Path) -> dict[str, object]:
    """Return frontmatter as a plain dict (empty if absent / malformed).

    Thin wrapper around `reconcile.parse_frontmatter` that drops the body
    half of the tuple and normalizes the missing case to `{}`.
    """
    fm, _body = _parse_fm(file_path)
    if fm is None:
        return {}
    return fm


def compute_hash(file_path: Path) -> str:
    """sha256 of the body bytes (frontmatter stripped + normalized).

    Matches Renderer's normalization exactly (CRLF → LF, single trailing LF)
    so a freshly rendered file always equals its recorded `content_hash`.
    """
    _fm, body = _parse_fm(file_path)
    return compute_body_hash(body)


def verify_file(file_path: Path) -> tuple[bool, str]:
    """Verify a file's recorded `content_hash` matches its current body.

    Returns:
        (matches, source_template) where:
        - matches: True iff frontmatter has `content_hash` and it equals the
          recomputed hash. False on missing frontmatter, missing hash field,
          or hash mismatch.
        - source_template: value of `source_template` frontmatter field if
          present, else "" (empty string).

    A False return with empty source_template indicates the file is not a
    harness-maker artifact (no provenance metadata present).
    """
    fm, body = _parse_fm(file_path)
    if fm is None:
        return (False, "")
    source_template = str(fm.get("source_template", "") or "")
    recorded = fm.get("content_hash")
    if not recorded:
        return (False, source_template)
    actual = compute_body_hash(body)
    return (recorded == actual, source_template)
