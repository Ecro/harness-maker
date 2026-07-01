"""Build a minimal yaml index of user-registered ref_folders for skill-driven search.

Lossy by design — the index only stores enough metadata (filename + frontmatter
title + h1/h2 headings) for an LLM to triage candidate files. Actual content is
read fresh from the original file (multimodal Read for PDF, ripgrep for md/txt)
at query time, so the index never causes information loss in answers.

DOCX is unsupported — the index emits a warning per DOCX file found. Users
should convert to PDF or markdown before registering.
"""

from __future__ import annotations

import re
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from harness_maker import command_registry
from harness_maker.io_utils import atomic_write
from harness_maker.models import RefFolder

_FRONTMATTER_OPEN = "---\n"
_FRONTMATTER_CLOSE = "\n---\n"
_HEADING_RE = re.compile(r"^(#{1,2})\s+(.+?)\s*$", re.MULTILINE)

_KIND_BY_EXT: dict[str, str] = {
    ".md": "md",
    ".markdown": "md",
    ".txt": "txt",
    ".pdf": "pdf",
}
_WARN_EXTS: set[str] = {".docx", ".doc"}

# Read cap so a multi-MB markdown doesn't blow up registration.
_MD_READ_BYTES_CAP = 256 * 1024


@dataclass(frozen=True)
class IndexBuildResult:
    """Outcome of a build pass — consumed by tests, CLI, and the post-render hook."""

    index_path: Path
    entry_count: int
    warnings: list[str]


def build(
    harness_root: Path,
    ref_folders: list[RefFolder],
    *,
    now_iso: str | None = None,
) -> IndexBuildResult:
    """Walk ref_folders, build the minimal yaml index, atomic-write it.

    ``harness_root`` is the directory containing ``.claude/`` — used to resolve
    relative ref_folder paths. ``now_iso`` allows tests to freeze the
    ``generated_at`` field for snapshot determinism.
    """
    generated_at = now_iso or datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    out_blocks: list[dict[str, Any]] = []
    warnings: list[str] = []
    entry_count = 0

    for rf in ref_folders:
        block = _build_block(harness_root, rf, warnings)
        out_blocks.append(block)
        entry_count += len(block["entries"])

    payload: dict[str, Any] = {
        "generated_at": generated_at,
        "ref_folders": out_blocks,
        "warnings": warnings,
    }
    yaml_text = yaml.safe_dump(payload, sort_keys=False, allow_unicode=True)

    index_path = harness_root / ".claude" / "observability" / "docs_index.yaml"
    atomic_write(index_path, yaml_text)
    return IndexBuildResult(index_path=index_path, entry_count=entry_count, warnings=warnings)


def _build_block(
    harness_root: Path,
    rf: RefFolder,
    warnings: list[str],
) -> dict[str, Any]:
    # Expand ``~`` FIRST so it actually triggers — ``Path.expanduser()`` only
    # expands when ``~`` is at position 0 of the path. ``harness_root / "~/foo"``
    # joins to ``<root>/~/foo``, where ``~`` is no longer at the start, so a
    # later ``.expanduser()`` is a silent no-op and resolve() produces a bogus
    # path under harness_root. Only join with harness_root when the user-supplied
    # path is genuinely relative (e.g. ``../docs``).
    raw = Path(rf.path).expanduser()
    abs_root = raw.resolve() if raw.is_absolute() else (harness_root / raw).resolve()
    entries: list[dict[str, Any]] = []
    if not abs_root.exists() or not abs_root.is_dir():
        warnings.append(
            f"ref_folder not found or not a directory: {rf.path!r} (resolved {abs_root})",
        )
        return {"path": rf.path, "glob": rf.glob, "entries": entries}

    seen: set[Path] = set()
    for fp in sorted(_walk(abs_root, rf.glob)):
        seen.add(fp)
        if _is_hidden(fp, abs_root):
            continue
        ext = fp.suffix.lower()
        if ext in _WARN_EXTS:
            rel = _safe_rel(fp, abs_root)
            warnings.append(f"Skipped {ext} (unsupported): {rf.path}/{rel}")
            continue
        kind = _KIND_BY_EXT.get(ext)
        if kind is None:
            continue
        rel = _safe_rel(fp, abs_root)
        entries.append(_entry_for(fp, kind, rel))

    # Second pass: warn on unsupported formats that the user's glob excluded.
    # The default glob (``**/*.{md,txt,pdf}``) doesn't match .docx, but users
    # need to know one exists so they can convert it.
    for ext in _WARN_EXTS:
        for fp in sorted(abs_root.rglob(f"*{ext}")):
            if not fp.is_file() or fp in seen or _is_hidden(fp, abs_root):
                continue
            rel = _safe_rel(fp, abs_root)
            warnings.append(f"Skipped {ext} (unsupported): {rf.path}/{rel}")

    return {"path": rf.path, "glob": rf.glob, "entries": entries}


def _is_hidden(p: Path, root: Path) -> bool:
    """Skip dotfiles / dot-dirs like .git, .venv, .pytest_cache so a ref_folder
    pointed at a repo root doesn't index its own VCS guts.
    """
    try:
        rel = p.relative_to(root)
    except ValueError:
        return False
    return any(part.startswith(".") for part in rel.parts)


def _walk(root: Path, glob: str) -> Iterable[Path]:
    """Glob walk with single-level brace expansion for the default ``**/*.{a,b,c}`` shape.

    pathlib.Path.glob lacks brace support. We expand one ``{...}`` group on
    extension-style alternation; anything else is passed through verbatim.
    """
    if "{" in glob and "}" in glob:
        prefix, _, rest = glob.partition("{")
        exts, _, suffix = rest.partition("}")
        for ext in exts.split(","):
            yield from root.glob(f"{prefix}{ext.strip()}{suffix}")
        return
    yield from root.glob(glob)


def _entry_for(fp: Path, kind: str, rel: str) -> dict[str, Any]:
    if kind in {"pdf", "txt"}:
        return {"relpath": rel, "kind": kind, "filename_only": True}
    title, headings = _extract_md_metadata(fp)
    entry: dict[str, Any] = {"relpath": rel, "kind": kind}
    if title:
        entry["title"] = title
    if headings:
        entry["headings"] = headings
    return entry


def _extract_md_metadata(fp: Path) -> tuple[str | None, list[str]]:
    """Title (frontmatter or first H1) + H1/H2 headings, capped to _MD_READ_BYTES_CAP."""
    try:
        text = fp.read_text(encoding="utf-8", errors="replace")[:_MD_READ_BYTES_CAP]
    except OSError:
        return None, []
    body = text
    fm_title: str | None = None
    if text.startswith(_FRONTMATTER_OPEN):
        end = text.find(_FRONTMATTER_CLOSE, len(_FRONTMATTER_OPEN))
        if end != -1:
            fm_block = text[len(_FRONTMATTER_OPEN) : end]
            try:
                fm_data = yaml.safe_load(fm_block)
            except yaml.YAMLError:
                fm_data = None
            if isinstance(fm_data, dict):
                raw_title = fm_data.get("title")
                if isinstance(raw_title, str) and raw_title.strip():
                    fm_title = raw_title.strip()
            body = text[end + len(_FRONTMATTER_CLOSE) :]
    headings: list[str] = []
    first_h1: str | None = None
    for m in _HEADING_RE.finditer(body):
        text_part = m.group(2).strip()
        if not text_part:
            continue
        if m.group(1) == "#" and first_h1 is None:
            first_h1 = text_part
        headings.append(text_part)
    title = fm_title or first_h1
    if title and headings and headings[0] == title:
        headings = headings[1:]
    return title, headings


def _safe_rel(fp: Path, root: Path) -> str:
    try:
        return fp.relative_to(root).as_posix()
    except ValueError:
        return fp.name


def _cli(argv: list[str]) -> int:
    """Entry: ``python -m harness_maker.refdocs_index build [harness_root]``."""
    _guard = command_registry.guard_or_none("refdocs_index", argv)
    if _guard is not None:
        return _guard
    if not argv or argv[0] != "build":
        print("usage: python -m harness_maker.refdocs_index build [harness_root]")
        return 2
    root = Path(argv[1] if len(argv) > 1 else ".").resolve()
    yaml_path = root / ".claude" / "harness.yaml"
    if not yaml_path.exists():
        print(f"no harness.yaml at {yaml_path}")
        return 1
    text = yaml_path.read_text(encoding="utf-8")
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end != -1:
            text = text[end + 5 :]
    data = yaml.safe_load(text) or {}
    raw_list = data.get("ref_folders") or []
    rf_list: list[RefFolder] = []
    if isinstance(raw_list, list):
        for item in raw_list:
            if not isinstance(item, dict):
                continue
            path = item.get("path")
            if not isinstance(path, str) or not path:
                continue
            glob_val = item.get("glob")
            glob = glob_val if isinstance(glob_val, str) and glob_val else "**/*.{md,txt,pdf}"
            rf_list.append(RefFolder(path=path, glob=glob))
    result = build(root, rf_list)
    print(f"docs_index.yaml: {result.entry_count} entries, {len(result.warnings)} warnings")
    for w in result.warnings:
        print(f"  warn: {w}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli(sys.argv[1:]))
