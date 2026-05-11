"""Filesystem-backed Obsidian Second Brain helper.

The connector treats configured vault folders as trusted read/write zones, but
all operations still pass through resolved-path allowlist checks.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from harness_maker.io_utils import atomic_write
from harness_maker.models import SecondBrainConfig, SecondBrainFolder, SecondBrainNoteType

_FRONTMATTER_OPEN = "---\n"
_FRONTMATTER_CLOSE = "\n---\n"
_WIKILINK_RE = re.compile(r"\[\[[^\]\n]+?\]\]")
_MARKDOWN_EXTS = {".md", ".markdown"}
_TYPE_TAG_PREFIX = "hm/type/"
_SECOND_BRAIN_TAG = "hm/second-brain"

_RECOMMENDED_FIELDS: dict[str, tuple[str, ...]] = {
    "decision": ("status", "related_projects", "supersedes"),
    "preference": ("scope", "applies_to"),
    "failure": ("severity", "recurrence_count", "avoided_by"),
    "project": ("status", "source_repo", "active_plan"),
    "reference": ("source", "authority", "captured_from"),
    "journal": ("date", "session", "work_item"),
}


class SecondBrainError(RuntimeError):
    """Raised when a Second Brain operation violates config or schema."""


@dataclass(frozen=True)
class WriteResult:
    path: Path
    warnings: list[str]


@dataclass(frozen=True)
class SearchResult:
    relpath: str
    title: str | None
    note_type: str | None
    tags: list[str]
    links: list[str]
    snippet: str


def parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Return YAML frontmatter dict and body.

    Missing or malformed frontmatter returns an empty dict and the original body.
    Validation is handled separately by ``validate_note``.
    """
    if not text.startswith(_FRONTMATTER_OPEN):
        return {}, text
    end = text.find(_FRONTMATTER_CLOSE, len(_FRONTMATTER_OPEN))
    if end == -1:
        return {}, text
    raw = text[len(_FRONTMATTER_OPEN) : end]
    try:
        parsed = yaml.safe_load(raw)
    except yaml.YAMLError:
        return {}, text
    body = text[end + len(_FRONTMATTER_CLOSE) :]
    return (parsed if isinstance(parsed, dict) else {}), body


def validate_note(frontmatter: dict[str, Any], body: str) -> list[str]:
    """Validate managed-note core schema and return warning strings."""
    required = ["type", "created", "updated", "tags", "links"]
    missing = [k for k in required if k not in frontmatter]
    if missing:
        raise SecondBrainError(f"missing required frontmatter: {', '.join(missing)}")

    note_type = frontmatter.get("type")
    allowed = {t.value for t in SecondBrainNoteType}
    if not isinstance(note_type, str) or note_type not in allowed:
        raise SecondBrainError(f"unknown note type: {note_type!r}")

    tags = frontmatter.get("tags")
    if not isinstance(tags, list) or not all(isinstance(t, str) for t in tags):
        raise SecondBrainError("frontmatter tags must be a list of strings")
    links = frontmatter.get("links")
    if not isinstance(links, list) or not all(isinstance(link, str) for link in links):
        raise SecondBrainError("frontmatter links must be a list of strings")

    warnings: list[str] = []
    required_tags = {_SECOND_BRAIN_TAG, f"{_TYPE_TAG_PREFIX}{note_type}"}
    missing_tags = sorted(required_tags - set(tags))
    if missing_tags:
        warnings.append(f"recommended tags missing: {', '.join(missing_tags)}")

    recommended_missing = [
        key for key in _RECOMMENDED_FIELDS[note_type] if key not in frontmatter
    ]
    if recommended_missing:
        warnings.append(
            "recommended frontmatter missing for "
            f"{note_type}: {', '.join(recommended_missing)}"
        )

    wikilinks = extract_links(body)
    if not links and not wikilinks:
        warnings.append("note has no links; graph connectivity may be weak")
    return warnings


def extract_links(text: str) -> list[str]:
    """Extract unique Obsidian wiki links from text in first-seen order."""
    out: list[str] = []
    seen: set[str] = set()
    for match in _WIKILINK_RE.findall(text):
        if match not in seen:
            seen.add(match)
            out.append(match)
    return out


def read_note(harness_root: Path, relpath: str) -> str:
    cfg = _load_config(harness_root)
    path, _folder = _resolve_authorized(harness_root, cfg, relpath, mode="read")
    return path.read_text(encoding="utf-8")


def write_note(
    harness_root: Path,
    relpath: str,
    frontmatter: dict[str, Any],
    body: str,
) -> WriteResult:
    cfg = _load_config(harness_root)
    path, folder = _resolve_authorized(harness_root, cfg, relpath, mode="write")
    _require_markdown(path)
    _ensure_type_allowed(frontmatter, folder)
    warnings = validate_note(frontmatter, body)
    warnings.extend(_project_namespace_warnings(frontmatter, cfg))
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(path, _format_note(frontmatter, body))
    return WriteResult(path=path, warnings=warnings)


def append_note(harness_root: Path, relpath: str, text: str) -> WriteResult:
    cfg = _load_config(harness_root)
    path, folder = _resolve_authorized(harness_root, cfg, relpath, mode="write")
    _require_markdown(path)
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    fm, body = parse_frontmatter(existing)
    _ensure_type_allowed(fm, folder)
    warnings = validate_note(fm, body + text)
    warnings.extend(_project_namespace_warnings(fm, cfg))
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(path, existing + text)
    return WriteResult(path=path, warnings=warnings)


def patch_note(harness_root: Path, relpath: str, old_text: str, new_text: str) -> WriteResult:
    cfg = _load_config(harness_root)
    path, folder = _resolve_authorized(harness_root, cfg, relpath, mode="write")
    _require_markdown(path)
    existing = path.read_text(encoding="utf-8")
    if old_text not in existing:
        raise SecondBrainError("old text not found")
    updated = existing.replace(old_text, new_text, 1)
    fm, body = parse_frontmatter(updated)
    _ensure_type_allowed(fm, folder)
    warnings = validate_note(fm, body)
    warnings.extend(_project_namespace_warnings(fm, cfg))
    atomic_write(path, updated)
    return WriteResult(path=path, warnings=warnings)


def search_notes(
    harness_root: Path,
    query: str,
    *,
    note_type: str | None = None,
    tag: str | None = None,
    limit: int = 20,
) -> list[SearchResult]:
    cfg = _load_config(harness_root)
    if not query.strip():
        raise SecondBrainError("search query cannot be empty")
    q = query.lower()
    results: list[SearchResult] = []
    for folder in cfg.folders:
        if not folder.read:
            continue
        root = _folder_root(harness_root, cfg, folder.path)
        if not root.exists():
            continue
        for path in sorted(_iter_markdown(root)):
            rel = _rel_to_vault(harness_root, cfg, path)
            text = path.read_text(encoding="utf-8", errors="replace")
            fm, body = parse_frontmatter(text)
            fm_type = fm.get("type")
            tags = _string_list(fm.get("tags"))
            if isinstance(fm_type, str) and fm_type not in {t.value for t in folder.note_types}:
                continue
            if note_type and fm_type != note_type:
                continue
            if tag and tag not in tags:
                continue
            if q not in rel.lower() and q not in text.lower():
                continue
            results.append(
                SearchResult(
                    relpath=rel,
                    title=_title_for(fm, body),
                    note_type=fm_type if isinstance(fm_type, str) else None,
                    tags=tags,
                    links=_merged_links(fm, body),
                    snippet=_snippet(body, q),
                )
            )
            if len(results) >= limit:
                return results
    return results


def _load_config(harness_root: Path) -> SecondBrainConfig:
    yaml_path = harness_root / ".claude" / "harness.yaml"
    if not yaml_path.exists():
        raise SecondBrainError(f"no harness.yaml at {yaml_path}")
    data = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise SecondBrainError("harness.yaml is not a mapping")
    cfg = SecondBrainConfig.model_validate(data.get("second_brain") or {})
    if not cfg.enabled:
        raise SecondBrainError("second_brain is disabled")
    if not cfg.vault_path:
        raise SecondBrainError("second_brain.vault_path is required")
    return cfg


def _vault_root(harness_root: Path, cfg: SecondBrainConfig) -> Path:
    raw = Path(cfg.vault_path).expanduser()
    return (raw if raw.is_absolute() else harness_root / raw).resolve()


def _folder_root(harness_root: Path, cfg: SecondBrainConfig, folder_path: str) -> Path:
    return (_vault_root(harness_root, cfg) / folder_path).resolve()


def _resolve_authorized(
    harness_root: Path,
    cfg: SecondBrainConfig,
    relpath: str,
    *,
    mode: str,
) -> tuple[Path, SecondBrainFolder]:
    if mode not in {"read", "write"}:
        raise ValueError(f"unknown mode: {mode}")
    vault = _vault_root(harness_root, cfg)
    target = (vault / relpath).resolve()
    for folder in cfg.folders:
        if mode == "read" and not folder.read:
            continue
        if mode == "write" and not folder.write:
            continue
        root = _folder_root(harness_root, cfg, folder.path)
        if target == root or target.is_relative_to(root):
            return target, folder
    raise SecondBrainError(f"{relpath!r} is not under a configured {mode} folder")


def _require_markdown(path: Path) -> None:
    if path.suffix.lower() not in _MARKDOWN_EXTS:
        raise SecondBrainError("second_brain writes are limited to Markdown files")


def _ensure_type_allowed(frontmatter: dict[str, Any], folder: SecondBrainFolder) -> None:
    note_type = frontmatter.get("type")
    allowed = {t.value for t in folder.note_types}
    if isinstance(note_type, str) and note_type not in allowed:
        raise SecondBrainError(f"note type {note_type!r} is not allowed in folder {folder.path!r}")


def _project_namespace_warnings(
    frontmatter: dict[str, Any],
    cfg: SecondBrainConfig,
) -> list[str]:
    if not cfg.project_id:
        return []
    project = frontmatter.get("project")
    project_id = frontmatter.get("project_id")
    projects = frontmatter.get("projects")
    if project == cfg.project_id or project_id == cfg.project_id:
        return []
    if isinstance(projects, list) and cfg.project_id in projects:
        return []
    return [
        "recommended project namespace missing: "
        f"set project_id/project/projects to {cfg.project_id!r}"
    ]


def _format_note(frontmatter: dict[str, Any], body: str) -> str:
    yaml_text = yaml.safe_dump(frontmatter, sort_keys=False, allow_unicode=True).strip()
    normalized_body = body if body.endswith("\n") else f"{body}\n"
    return f"---\n{yaml_text}\n---\n{normalized_body}"


def _iter_markdown(root: Path) -> list[Path]:
    out: list[Path] = []
    for ext in _MARKDOWN_EXTS:
        out.extend(p for p in root.rglob(f"*{ext}") if p.is_file())
    return out


def _rel_to_vault(harness_root: Path, cfg: SecondBrainConfig, path: Path) -> str:
    try:
        return path.relative_to(_vault_root(harness_root, cfg)).as_posix()
    except ValueError:
        return path.name


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [v for v in value if isinstance(v, str)]


def _merged_links(frontmatter: dict[str, Any], body: str) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for link in [*_string_list(frontmatter.get("links")), *extract_links(body)]:
        if link not in seen:
            seen.add(link)
            out.append(link)
    return out


def _title_for(frontmatter: dict[str, Any], body: str) -> str | None:
    title = frontmatter.get("title")
    if isinstance(title, str) and title.strip():
        return title.strip()
    for line in body.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return None


def _snippet(body: str, query_lower: str) -> str:
    lower = body.lower()
    idx = lower.find(query_lower)
    if idx == -1:
        return body.strip().splitlines()[0][:160] if body.strip() else ""
    start = max(0, idx - 60)
    end = min(len(body), idx + len(query_lower) + 100)
    return body[start:end].replace("\n", " ").strip()


def _cli(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="python -m harness_maker.second_brain")
    parser.add_argument("--root", default=".", help="Harness root containing .claude/harness.yaml")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_search = sub.add_parser("search")
    p_search.add_argument("query")
    p_search.add_argument("--type", dest="note_type")
    p_search.add_argument("--tag")

    p_read = sub.add_parser("read")
    p_read.add_argument("path")

    p_write = sub.add_parser("write")
    p_write.add_argument("path")
    p_write.add_argument("--frontmatter-json", required=True)
    p_write.add_argument("--body-file", required=True)

    p_append = sub.add_parser("append")
    p_append.add_argument("path")
    p_append.add_argument("--text-file", required=True)

    p_patch = sub.add_parser("patch")
    p_patch.add_argument("path")
    p_patch.add_argument("--old-text", required=True)
    p_patch.add_argument("--new-text", required=True)

    p_validate = sub.add_parser("validate")
    p_validate.add_argument("path")

    args = parser.parse_args(argv)
    root = Path(args.root).resolve()
    try:
        if args.cmd == "search":
            results = search_notes(root, args.query, note_type=args.note_type, tag=args.tag)
            print(json.dumps([r.__dict__ for r in results], indent=2, ensure_ascii=False))
        elif args.cmd == "read":
            print(read_note(root, args.path), end="")
        elif args.cmd == "write":
            fm = json.loads(args.frontmatter_json)
            if not isinstance(fm, dict):
                raise SecondBrainError("--frontmatter-json must decode to an object")
            body = Path(args.body_file).read_text(encoding="utf-8")
            result = write_note(root, args.path, fm, body)
            _print_write_result(result)
        elif args.cmd == "append":
            text = Path(args.text_file).read_text(encoding="utf-8")
            result = append_note(root, args.path, text)
            _print_write_result(result)
        elif args.cmd == "patch":
            result = patch_note(root, args.path, args.old_text, args.new_text)
            _print_write_result(result)
        elif args.cmd == "validate":
            text = read_note(root, args.path)
            fm, body = parse_frontmatter(text)
            warnings = validate_note(fm, body)
            print(json.dumps({"warnings": warnings}, indent=2))
    except (OSError, json.JSONDecodeError, SecondBrainError, yaml.YAMLError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    return 0


def _print_write_result(result: WriteResult) -> None:
    print(json.dumps({"path": str(result.path), "warnings": result.warnings}, indent=2))


if __name__ == "__main__":
    raise SystemExit(_cli(sys.argv[1:]))
