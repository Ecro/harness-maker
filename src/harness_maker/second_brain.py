"""Filesystem-backed Obsidian Second Brain helper.

The connector treats configured vault folders as trusted read/write zones, but
all operations still pass through resolved-path allowlist checks.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from harness_maker.io_utils import atomic_write, load_harness_yaml
from harness_maker.models import SecondBrainConfig, SecondBrainFolder, SecondBrainNoteType

logger = logging.getLogger(__name__)

_FRONTMATTER_OPEN = "---\n"
_FRONTMATTER_CLOSE = "\n---\n"
_WIKILINK_RE = re.compile(r"\[\[[^\]\n]+?\]\]")
_MARKDOWN_EXTS = {".md", ".markdown"}
_TYPE_TAG_PREFIX = "hm/type/"
_SECOND_BRAIN_TAG = "hm/second-brain"
_EMPTY_FOLDERS_REMEDIATION = (
    "second_brain.folders is empty — run /hm:configure to add at least one folder"
)
_EMPTY_FOLDERS_ACTION = (
    "ACTION: add at least one folder to second_brain.folders in .claude/harness.yaml, "
    "or run /hm:configure"
)

_RECOMMENDED_FIELDS: dict[str, tuple[str, ...]] = {
    "decision": ("status", "related_projects", "supersedes"),
    "preference": ("scope", "applies_to"),
    "failure": ("severity", "recurrence_count", "avoided_by"),
    "project": ("status", "source_repo", "active_plan"),
    "reference": ("source", "authority", "captured_from"),
    "journal": ("date", "session", "work_item"),
}


def _autofill_timestamps(frontmatter: dict[str, Any]) -> dict[str, Any]:
    """Return a NEW dict with `created` (if missing) and `updated` (always now) set.

    Mutation-free per PLAN-untested-trio-fix ADR-010: caller's input dict is
    never modified — slash-command templates that reuse a frontmatter dict
    across multiple notes would otherwise lock `created` to the first call's
    timestamp.

    `created` policy: setdefault — preserve user-supplied or on-disk values.
    `updated` policy: always overwrite to current UTC (ADR-006: last-touch semantic).
    """
    out = dict(frontmatter)
    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    out.setdefault("created", now)
    out["updated"] = now
    return out


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


_DEFAULT_REQUIRED_FRONTMATTER = ["type", "created", "updated", "tags", "links"]


def validate_note(
    frontmatter: dict[str, Any],
    body: str,
    *,
    required_fields: list[str] | None = None,
) -> list[str]:
    """Validate managed-note core schema and return warning strings."""
    required = required_fields if required_fields is not None else _DEFAULT_REQUIRED_FRONTMATTER
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

    recommended_missing = [key for key in _RECOMMENDED_FIELDS[note_type] if key not in frontmatter]
    if recommended_missing:
        warnings.append(
            f"recommended frontmatter missing for {note_type}: {', '.join(recommended_missing)}"
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
    if not cfg.folders:
        raise SecondBrainError(_EMPTY_FOLDERS_REMEDIATION)
    path, folder = _resolve_authorized(harness_root, cfg, relpath, mode="write")
    _require_markdown(path)
    # ADR-008: preserve on-disk `created` across re-writes. Without this, a
    # second write_note with no `created` in fm would silently install a NEW
    # `created` (auto-fill assigns current time), losing the original.
    if path.exists():
        try:
            existing_fm, _ = parse_frontmatter(path.read_text(encoding="utf-8"))
            if "created" in existing_fm and "created" not in frontmatter:
                frontmatter = {**frontmatter, "created": existing_fm["created"]}
        except OSError:
            pass  # treat as fresh write
    fm = _autofill_timestamps(frontmatter)  # ADR-006/010: returns NEW dict
    _ensure_type_allowed(fm, folder)
    warnings = validate_note(fm, body, required_fields=cfg.required_frontmatter)
    warnings.extend(_project_namespace_warnings(fm, cfg))
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(path, _format_note(fm, body))
    return WriteResult(path=path, warnings=warnings)


def append_note(harness_root: Path, relpath: str, text: str) -> WriteResult:
    cfg = _load_config(harness_root)
    if not cfg.folders:
        raise SecondBrainError(_EMPTY_FOLDERS_REMEDIATION)
    path, folder = _resolve_authorized(harness_root, cfg, relpath, mode="write")
    _require_markdown(path)
    # ADR-009: re-serialize via _format_note so the `updated` bump from
    # _autofill_timestamps actually lands on disk. Pre-fix path used raw
    # `existing + text` concat which discarded the fm mutation.
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    fm, body = parse_frontmatter(existing)
    new_body = body + text
    fm = _autofill_timestamps(fm)  # ADR-006: bumps updated
    _ensure_type_allowed(fm, folder)
    warnings = validate_note(fm, new_body, required_fields=cfg.required_frontmatter)
    warnings.extend(_project_namespace_warnings(fm, cfg))
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(path, _format_note(fm, new_body))
    return WriteResult(path=path, warnings=warnings)


def patch_note(harness_root: Path, relpath: str, old_text: str, new_text: str) -> WriteResult:
    cfg = _load_config(harness_root)
    if not cfg.folders:
        raise SecondBrainError(_EMPTY_FOLDERS_REMEDIATION)
    path, folder = _resolve_authorized(harness_root, cfg, relpath, mode="write")
    _require_markdown(path)
    # ADR-009 corrective: match `old_text` against the body only, not the
    # full file. Frontmatter-substring patching was undefined behavior pre-fix.
    existing = path.read_text(encoding="utf-8")
    fm, body = parse_frontmatter(existing)
    if old_text not in body:
        raise SecondBrainError("old text not found")
    new_body = body.replace(old_text, new_text, 1)
    fm = _autofill_timestamps(fm)  # ADR-006: bumps updated
    _ensure_type_allowed(fm, folder)
    warnings = validate_note(fm, new_body, required_fields=cfg.required_frontmatter)
    warnings.extend(_project_namespace_warnings(fm, cfg))
    atomic_write(path, _format_note(fm, new_body))
    return WriteResult(path=path, warnings=warnings)


_SLUG_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")
_SLUG_MAX_LEN = 60


# Frontmatter keys promote_note owns — callers may not override identity,
# timestamp, or namespace fields via extra_frontmatter (REVIEW P2).
_PROMOTE_RESERVED_KEYS = frozenset(
    {
        "type",
        "title",
        "tags",
        "links",
        "hm_source",
        "created",
        "updated",
        "project",
        "project_id",
        "projects",
    }
)


def _slugify(text: str) -> str:
    """Deterministic kebab slug for promotion filenames.

    The slug is the idempotency anchor: re-promoting the same source must
    resolve to the same `<type>-<slug>.md` path so write_note updates in place
    instead of creating a duplicate. Never returns empty (filename safety).

    Caller contract: `source_slug` must be stable AND unique *after*
    kebab-normalization — two inputs that collapse to the same slug (or share a
    60-char prefix) map to the same note. The wrapup Step 5.6 prompt requires a
    stable local identifier (wiki/failure slug or ADR id) precisely for this.
    """
    cleaned = _SLUG_NON_ALNUM_RE.sub("-", text.lower()).strip("-")
    return cleaned[:_SLUG_MAX_LEN].strip("-") or "note"


def promote_note(
    harness_root: Path,
    *,
    note_type: str,
    source_slug: str,
    title: str,
    body: str,
    links: list[str] | None = None,
    extra_frontmatter: dict[str, Any] | None = None,
) -> WriteResult:
    """Promote a local-memory entry into an idempotent, namespaced Obsidian note.

    Python owns the safety rail (deterministic path, link-back + project
    namespace, dedup via write_note); the caller (wrapup Step 5.6) owns the
    judgment of WHAT to promote and the note's prose. Re-promoting the same
    `(note_type, source_slug)` updates the existing note in place — never a dup.
    """
    cfg = _load_config(harness_root)
    if not cfg.folders:
        raise SecondBrainError(_EMPTY_FOLDERS_REMEDIATION)
    # Validate note_type against the enum at the source (REVIEW P1/P2): keeps a
    # raw caller string out of the write path, and lets us pick a folder that
    # actually accepts the type instead of blindly taking the first writable one.
    try:
        nt = SecondBrainNoteType(note_type)
    except ValueError as exc:
        raise SecondBrainError(f"unknown note type: {note_type!r}") from exc
    folder = next((f for f in cfg.folders if f.write and nt in f.note_types), None)
    if folder is None:
        raise SecondBrainError(f"no writable second_brain folder accepts note type {note_type!r}")
    relpath = f"{folder.path}/{nt.value}-{_slugify(source_slug)}.md"

    # promote_note owns identity / timestamp / namespace keys; callers may only
    # contribute recommended per-type fields (status, severity, …) + extra
    # tags/links. Strip reserved keys so the safety rail can't be overridden.
    extra = dict(extra_frontmatter or {})
    caller_tags = extra.get("tags")
    caller_links = [link for link in (extra.get("links") or []) if isinstance(link, str)]
    frontmatter: dict[str, Any] = {
        k: v for k, v in extra.items() if k not in _PROMOTE_RESERVED_KEYS
    }
    tags = [_SECOND_BRAIN_TAG, f"{_TYPE_TAG_PREFIX}{nt.value}"]
    if isinstance(caller_tags, list):
        tags.extend(t for t in caller_tags if isinstance(t, str) and t not in tags)
    merged_links = list(caller_links)
    merged_links.extend(
        link for link in (links or []) if isinstance(link, str) and link not in merged_links
    )
    if not merged_links and cfg.project_id:
        # Default backlink keeps the note connected to the project graph and
        # avoids the spurious "weak graph connectivity" warning (REVIEW P2).
        merged_links = [f"[[{cfg.project_id}]]"]
    frontmatter.update(
        {
            "type": nt.value,
            "title": title,
            "tags": tags,
            "links": merged_links,
            "hm_source": source_slug,
        }
    )
    if cfg.project_id:
        # W1: _project_namespace_warnings recognizes project_id, NOT hm_source.
        frontmatter["project_id"] = cfg.project_id
    result = write_note(harness_root, relpath, frontmatter, body)
    # Surface silently-dropped reserved keys so a caller (or the wrapup LLM)
    # learns its namespace/identity input was ignored, instead of losing it
    # silently (REVIEW: --frontmatter-json contract gap). tags/links are merged
    # rather than dropped, so they are excluded from this warning.
    dropped = sorted((set(extra) & _PROMOTE_RESERVED_KEYS) - {"tags", "links"})
    if dropped:
        result.warnings.append(
            "ignored caller frontmatter keys owned by promote_note: " + ", ".join(dropped)
        )
    return result


_WORD_BOUNDARY_RE = re.compile(r"\b", re.UNICODE)
_TITLE_BOOST = 3.0
_TAG_BOOST = 2.0
_WORD_BOUNDARY_BONUS = 2.0


def _score_result(
    query_tokens: list[str],
    relpath: str,
    title: str | None,
    tags: list[str],
    body: str,
) -> float:
    """Score a search result by relevance. Higher = more relevant."""
    score = 1.0
    lower_title = (title or "").lower()
    lower_tags = " ".join(tags).lower()
    lower_body = body.lower()
    lower_relpath = relpath.lower()

    for token in query_tokens:
        if token in lower_title:
            score += _TITLE_BOOST
            if re.search(rf"\b{re.escape(token)}\b", lower_title):
                score += _WORD_BOUNDARY_BONUS
        if token in lower_tags:
            score += _TAG_BOOST
        if re.search(rf"\b{re.escape(token)}\b", lower_body):
            score += _WORD_BOUNDARY_BONUS
        elif token in lower_body:
            score += 1.0
        if token in lower_relpath:
            score += 1.0
    return score


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
    query_tokens = [t for t in q.split() if t]
    candidates: list[tuple[float, SearchResult]] = []
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
            title = _title_for(fm, body)
            score = _score_result(query_tokens, rel, title, tags, body)
            candidates.append(
                (
                    score,
                    SearchResult(
                        relpath=rel,
                        title=title,
                        note_type=fm_type if isinstance(fm_type, str) else None,
                        tags=tags,
                        links=_merged_links(fm, body),
                        snippet=_snippet(body, q),
                    ),
                )
            )
    candidates.sort(key=lambda x: x[0], reverse=True)
    return [r for _, r in candidates[:limit]]


_DEPRECATED_FIELDS = ("trusted_allowlist",)


def _load_config(harness_root: Path) -> SecondBrainConfig:
    yaml_path = harness_root / ".claude" / "harness.yaml"
    if not yaml_path.exists():
        raise SecondBrainError(f"no harness.yaml at {yaml_path}")
    # Why load_harness_yaml: rendered harness.yaml carries a provenance
    # frontmatter block, so it is a multi-document YAML stream that
    # yaml.safe_load rejects. See io_utils.load_harness_yaml.
    data = load_harness_yaml(yaml_path)
    sb_raw = data.get("second_brain") or {}
    if isinstance(sb_raw, dict):
        for field in _DEPRECATED_FIELDS:
            if field in sb_raw:
                logger.warning(
                    "second_brain.%s is deprecated and ignored — remove from harness.yaml", field
                )
                sb_raw.pop(field)
    cfg = SecondBrainConfig.model_validate(sb_raw)
    if not cfg.enabled:
        raise SecondBrainError("second_brain is disabled")
    if not cfg.vault_path:
        raise SecondBrainError("second_brain.vault_path is required")
    _validate_vault_existence(harness_root, cfg)
    if not cfg.folders:
        logger.warning(_EMPTY_FOLDERS_REMEDIATION)
        print(f"\u26a0\ufe0f  WARNING: {_EMPTY_FOLDERS_REMEDIATION}", file=sys.stderr)
        print(f"   {_EMPTY_FOLDERS_ACTION}", file=sys.stderr)
    return cfg


def _validate_vault_existence(harness_root: Path, cfg: SecondBrainConfig) -> None:
    """Smart vault check (ADR-002): accept missing subdir if parent is an Obsidian vault.

    The user's intent of pointing at a not-yet-created subfolder of a real Obsidian
    vault (the canonical Second Brain pattern) is honoured — the subdir gets created
    at first write. A typo'd path whose parent is not an Obsidian vault fails loudly.

    Resolves relative vault_path values against ``harness_root`` to match
    ``_vault_root`` — otherwise a relative path would resolve against cwd here
    and against harness_root downstream, producing a divergent check.
    """
    vault = _vault_root(harness_root, cfg)
    if vault.exists():
        return
    parent_obsidian = vault.parent / ".obsidian"
    if parent_obsidian.is_dir():
        logger.warning(
            "vault parent has .obsidian/ but the configured subdir %s does not exist "
            "— it will be created on first write",
            vault,
        )
        return
    raise SecondBrainError(
        f"vault parent is not an Obsidian vault (no .obsidian/ at {vault.parent}); "
        f"create {vault} manually or fix second_brain.vault_path"
    )


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
    # Pick the MOST SPECIFIC (longest-root) matching folder, not the first.
    # With nested writable folders, a broad first-listed folder would otherwise
    # shadow a narrow per-type one and make _ensure_type_allowed reject a note
    # the path's real owner would have accepted (silent promotion no-op).
    best: tuple[Path, SecondBrainFolder] | None = None
    best_depth = -1
    for folder in cfg.folders:
        if mode == "read" and not folder.read:
            continue
        if mode == "write" and not folder.write:
            continue
        root = _folder_root(harness_root, cfg, folder.path)
        if target == root or target.is_relative_to(root):
            depth = len(root.parts)
            if depth > best_depth:
                best, best_depth = (target, folder), depth
    if best is not None:
        return best
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

    p_promote = sub.add_parser("promote")
    p_promote.add_argument(
        "--type",
        dest="note_type",
        required=True,
        choices=[t.value for t in SecondBrainNoteType],
    )
    p_promote.add_argument("--source-slug", dest="source_slug", required=True)
    p_promote.add_argument("--title", required=True)
    p_promote.add_argument("--body-file", required=True)
    p_promote.add_argument("--link", dest="links", action="append", default=[])
    p_promote.add_argument("--frontmatter-json", dest="frontmatter_json")

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
        elif args.cmd == "promote":
            extra: dict[str, Any] | None = None
            if args.frontmatter_json:
                parsed = json.loads(args.frontmatter_json)
                if not isinstance(parsed, dict):
                    raise SecondBrainError("--frontmatter-json must decode to an object")
                extra = parsed
            body = Path(args.body_file).read_text(encoding="utf-8")
            result = promote_note(
                root,
                note_type=args.note_type,
                source_slug=args.source_slug,
                title=args.title,
                body=body,
                links=args.links or None,
                extra_frontmatter=extra,
            )
            _print_write_result(result)
        elif args.cmd == "patch":
            result = patch_note(root, args.path, args.old_text, args.new_text)
            _print_write_result(result)
        elif args.cmd == "validate":
            text = read_note(root, args.path)
            fm, body = parse_frontmatter(text)
            cfg = _load_config(root)
            warnings = validate_note(fm, body, required_fields=cfg.required_frontmatter)
            print(json.dumps({"warnings": warnings}, indent=2))
    except (OSError, json.JSONDecodeError, SecondBrainError, yaml.YAMLError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    return 0


def _print_write_result(result: WriteResult) -> None:
    print(json.dumps({"path": str(result.path), "warnings": result.warnings}, indent=2))


if __name__ == "__main__":
    raise SystemExit(_cli(sys.argv[1:]))
