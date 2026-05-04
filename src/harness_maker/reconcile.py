"""Reconciler (Task 3.3) — decide per-file action in brownfield projects.

Decision matrix:
- new-only (no existing file)                                → BOTH
- existing has no frontmatter / no hash                      → KEEP (user file)
- existing hash matches our recompute                        → REPLACE (safe overwrite)
- existing hash mismatches AND both OLD/NEW have markers     → MERGE_BLOCK (3-way)
- existing hash mismatches otherwise                         → KEEP (legacy fallback)

Block-marker spec: docs/reference/block-merge-spec.md
"""

from __future__ import annotations

import hashlib
import shutil
from datetime import UTC, datetime
from pathlib import Path

import yaml

from harness_maker.block_merge import ParseError, has_markers, parse_segments
from harness_maker.models import Blueprint, ConflictItem, ReconcileDecision

# Templates ship inside the package; reconcile peeks at the source to know
# whether a fresh render will produce markers without re-rendering.
_TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"


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
    text = body_bytes.decode("utf-8", errors="replace").replace("\r\n", "\n").replace("\r", "\n")
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
        # settings.json is system-managed JSON co-owned with Claude Code (which
        # writes `enabledPlugins`). Render handles shallow merge internally;
        # always REPLACE here so the file isn't filtered out by the KEEP path.
        if fe.path.name == "settings.json":
            conflicts.append(
                ConflictItem(
                    path=fe.path,
                    decision=ReconcileDecision.REPLACE,
                    reason="json-shallow-merge",
                ),
            )
            continue
        # hooks.json is pure JSON (no frontmatter). Always REPLACE so template
        # updates (e.g., new hook commands) propagate on re-render.
        if fe.path == Path("hooks/hooks.json"):
            conflicts.append(
                ConflictItem(
                    path=fe.path,
                    decision=ReconcileDecision.REPLACE,
                    reason="pure-json-no-frontmatter",
                ),
            )
            continue
        # Generated wrappers under `.claude/lib/*.sh` carry no provenance
        # frontmatter (interpreters reject YAML preambles). Always REPLACE so
        # template updates land.
        if str(fe.path).endswith(".sh"):
            conflicts.append(
                ConflictItem(
                    path=fe.path,
                    decision=ReconcileDecision.REPLACE,
                    reason="pure-text-no-frontmatter",
                ),
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
            decision, reason = _decide_user_modified(fe.template, body)
            conflicts.append(
                ConflictItem(path=fe.path, decision=decision, reason=reason),
            )
    return conflicts


def _decide_user_modified(template_name: str, old_body: bytes) -> tuple[ReconcileDecision, str]:
    """User edited the file. Pick MERGE_BLOCK if both sides have markers,
    else fall back to KEEP (preserves legacy behaviour for marker-less files).
    """
    template_path = _TEMPLATE_DIR / template_name
    try:
        template_src = template_path.read_text(encoding="utf-8")
    except OSError:
        return ReconcileDecision.KEEP, "hash-mismatch-template-unreadable"
    try:
        old_text = old_body.decode("utf-8")
    except UnicodeDecodeError:
        return ReconcileDecision.KEEP, "hash-mismatch-binary-old"
    if has_markers(template_src) and has_markers(old_text):
        # Validate OLD parses cleanly. A user who broke marker syntax (typo,
        # deleted close, etc.) should NOT silently lose their edits via
        # REPLACE-on-parse-failure; KEEP the malformed file and surface why.
        try:
            parse_segments(old_text)
        except ParseError:
            return ReconcileDecision.KEEP, "hash-mismatch-malformed-markers"
        return ReconcileDecision.MERGE_BLOCK, "hash-mismatch-mergeable"
    return ReconcileDecision.KEEP, "hash-mismatch-user-modified"


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
