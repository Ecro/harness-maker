"""Reconciler (Task 3.3) — decide KEEP/REPLACE/BOTH per file in brownfield projects.

Decision matrix (per amendment §F):
- new-only (no existing file)              → BOTH
- existing has no frontmatter / no hash    → KEEP (user file, do not touch)
- existing hash matches our recompute      → REPLACE (it's our previous output, safe to overwrite)
- existing hash mismatches our recompute   → KEEP (user has modified our file)
"""

from __future__ import annotations

import hashlib
import shutil
from datetime import UTC, datetime
from pathlib import Path

import yaml

from harness_maker.models import Blueprint, ConflictItem, ReconcileDecision


def parse_frontmatter(path: Path) -> tuple[dict[str, object] | None, bytes]:
    """Parse leading YAML frontmatter; return (fm_dict | None, body_bytes)."""
    text = path.read_text(encoding="utf-8", errors="replace")
    if not text.startswith("---\n"):
        return None, text.encode("utf-8")
    end = text.find("\n---\n", 4)
    if end == -1:
        return None, text.encode("utf-8")
    try:
        fm = yaml.safe_load(text[4:end])
    except yaml.YAMLError:
        return None, text[end + 5 :].encode("utf-8")
    if not isinstance(fm, dict):
        return None, text[end + 5 :].encode("utf-8")
    return fm, text[end + 5 :].encode("utf-8")


def compute_body_hash(body_bytes: bytes) -> str:
    """Same normalization as Renderer."""
    text = (
        body_bytes.decode("utf-8", errors="replace")
        .replace("\r\n", "\n")
        .replace("\r", "\n")
    )
    if not text.endswith("\n"):
        text += "\n"
    while text.endswith("\n\n"):
        text = text[:-1]
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def reconcile(existing_dir: Path, blueprint: Blueprint) -> list[ConflictItem]:
    """Apply decision matrix per FileEntry vs existing file."""
    conflicts: list[ConflictItem] = []
    for fe in blueprint.files:
        existing_path = existing_dir / fe.path
        if not existing_path.exists():
            conflicts.append(
                ConflictItem(path=fe.path, decision=ReconcileDecision.BOTH, reason="new-only"),
            )
            continue
        fm, body = parse_frontmatter(existing_path)
        if fm is None or "content_hash" not in fm:
            conflicts.append(
                ConflictItem(
                    path=fe.path,
                    decision=ReconcileDecision.KEEP,
                    reason="no-frontmatter",
                ),
            )
            continue
        existing_hash = fm.get("content_hash")
        recomputed = compute_body_hash(body)
        if existing_hash == recomputed:
            conflicts.append(
                ConflictItem(
                    path=fe.path,
                    decision=ReconcileDecision.REPLACE,
                    reason="hash-match-ours",
                ),
            )
        else:
            conflicts.append(
                ConflictItem(
                    path=fe.path,
                    decision=ReconcileDecision.KEEP,
                    reason="hash-mismatch-user-modified",
                ),
            )
    return conflicts


def backup(existing_dir: Path) -> Path:
    """Snapshot existing .claude/ to .backup-<ISO>/. Microsecond + counter avoids collision."""
    iso = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    candidate = existing_dir.parent / f".backup-{iso}"
    n = 0
    while candidate.exists():
        n += 1
        candidate = existing_dir.parent / f".backup-{iso}-{n}"
    if existing_dir.exists():
        shutil.copytree(existing_dir, candidate)
    return candidate
