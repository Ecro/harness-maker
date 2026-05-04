"""Renderer (Task 3.2) — render Blueprint FileEntries to disk with deterministic output.

Determinism contract (per amendment §C):
- Jinja2 env: StrictUndefined, no autoescape, keep_trailing_newline=True.
- Body: normalize CRLF→LF, exactly one trailing LF, UTF-8 bytes.
- Frontmatter: YAML, sort_keys=False (insertion order), allow_unicode=True.
- settings.json: JSON, sort_keys=True (cross-edit determinism).
- content_hash: sha256 of the normalized body bytes; injected into frontmatter.
- freeze_time: when set, generated_at is fixed (used in tests + CI).

hooks.json (Phase 4 F1 amendment §E):
- Claude Code hooks.json must be pure JSON (jq-parseable) — no YAML frontmatter prefix.
- The cross-phase frontmatter invariant gate explicitly excludes `*/hooks/hooks.json`,
  so we render hooks.json as pure JSON via `_render_pure_json` (no symlink, no sidecar).
- Provenance is sacrificed for hooks.json (acceptable since it's small + reproducible).
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined

from harness_maker import __version__
from harness_maker.block_merge import MergeReport
from harness_maker.block_merge import merge as block_merge
from harness_maker.io_utils import atomic_write
from harness_maker.models import Blueprint, FileEntry

# Module constants — templates ship inside the harness_maker package so they're
# present in both editable installs (src/harness_maker/templates/) and wheel
# installs (importable as package data).
TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
DEFAULT_FREEZE_TIME = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)


def _make_env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        keep_trailing_newline=True,
        trim_blocks=False,
        lstrip_blocks=False,
        undefined=StrictUndefined,
        autoescape=False,
    )


def _normalize_body(text: str) -> bytes:
    """Normalize body to LF + single trailing LF, UTF-8 bytes."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if not text.endswith("\n"):
        text += "\n"
    while text.endswith("\n\n"):
        text = text[:-1]
    return text.encode("utf-8")


def _format_frontmatter(fm: dict[str, Any]) -> str:
    """YAML frontmatter — sort_keys=False for stable insertion order."""
    body = yaml.safe_dump(
        fm,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
    )
    return "---\n" + body + "---\n"


def _format_settings_json(data: dict[str, Any]) -> bytes:
    """settings.json — sort_keys=True for cross-edit determinism."""
    raw = json.dumps(
        data,
        sort_keys=True,
        indent=2,
        ensure_ascii=False,
        separators=(",", ": "),
    )
    return (raw + "\n").encode("utf-8")


def _build_provenance(
    fe: FileEntry,
    freeze_time: datetime | None,
) -> dict[str, Any]:
    ts = (freeze_time or DEFAULT_FREEZE_TIME).isoformat()
    return {
        "generated_by": "harness-maker",
        "harness_maker_version": __version__,
        "generated_at": ts,
        "source_template": fe.template,
        "provenance": "official",
        **fe.frontmatter,
    }


def _render_settings_json(
    fe: FileEntry,
    env: Environment,
    target_dir: Path,
    *,
    dry_run: bool,
    freeze_time: datetime | None,  # noqa: ARG001 — kept for dispatch signature parity
) -> Path:
    """Render settings.json as pure JSON, shallow-merging with any existing on disk.

    Claude Code expects ``settings.json`` to be parseable as plain JSON, so we
    cannot prepend YAML frontmatter (it'd break the file). We also need to
    coexist with Claude Code-managed top-level keys like ``enabledPlugins`` —
    written when the user runs ``/plugin install`` — so we shallow-merge:
      * existing top-level keys NOT in our template are preserved
      * keys present in both — our template's value wins (it's the source of
        truth for permissions/preset)

    v1 limitation — the merge is **shallow**: nested customizations under a
    key our template owns (e.g. user-added entries in ``permissions.allow``)
    are lost on re-render. Workaround: keep custom permissions in
    ``.claude/settings.local.json`` (Claude Code merges that automatically).
    """
    template = env.get_template(fe.template)
    rendered = template.render(**fe.context)
    try:
        new_data: dict[str, Any] = json.loads(rendered)
    except json.JSONDecodeError as e:
        msg = f"Template {fe.template} rendered invalid JSON for {fe.path}: {e}"
        raise ValueError(msg) from e
    if not isinstance(new_data, dict):
        msg = f"Template {fe.template} must render a JSON object (got {type(new_data).__name__})"
        raise ValueError(msg)
    out = target_dir / fe.path
    merged = _shallow_merge_existing_json(out, new_data)
    body_bytes = _format_settings_json(merged)
    body_hash = hashlib.sha256(body_bytes).hexdigest()
    fe.body_sha256 = body_hash
    if not dry_run:
        atomic_write(out, body_bytes)
    return out


# Keys harness-maker has ever written to settings.json.  When a key was
# removed from the template (e.g. statusLine in 0.3.6) it must be actively
# dropped on the next render — simple {**existing, **new_data} would leave it
# behind forever.
_SETTINGS_KEYS_OWNED_BY_HARNESS: frozenset[str] = frozenset(
    {
        "statusLine",   # shipped 0.3.x, removed 0.3.6
        "preset",
        "permissions",
        "env",
    }
)


def _shallow_merge_existing_json(
    out: Path,
    new_data: dict[str, Any],
) -> dict[str, Any]:
    """Merge top-level keys: existing's unique keys + new_data (template wins).

    Previously-owned harness-maker keys absent from new_data are removed so
    stale keys (e.g. statusLine) don't linger after a template drops them.
    """
    existing: dict[str, Any] = {}
    if out.exists():
        try:
            text = out.read_text(encoding="utf-8")
        except OSError:
            text = ""
        if text:
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, dict):
                existing = parsed
    merged = {**existing, **new_data}
    for key in _SETTINGS_KEYS_OWNED_BY_HARNESS:
        if key not in new_data:
            merged.pop(key, None)
    return merged


def _is_settings_json(fe: FileEntry) -> bool:
    return fe.path.name == "settings.json"


def _is_hooks_json(fe: FileEntry) -> bool:
    return str(fe.path).endswith("hooks.json")


def _render_pure_text(
    fe: FileEntry,
    env: Environment,
    target_dir: Path,
    *,
    dry_run: bool,
    freeze_time: datetime | None,  # noqa: ARG001 — kept for dispatch signature parity
) -> Path:
    """Render template body verbatim, no provenance frontmatter.

    Used for files whose interpreter rejects a YAML preamble — currently
    ``.sh`` wrappers under ``.claude/lib/``. Provenance is sacrificed
    because the wrapper is small, reproducible from the template, and
    re-rendered every time the user runs ``/harness-maker:make``.
    """
    template = env.get_template(fe.template)
    rendered = template.render(**fe.context)
    body_bytes = _normalize_body(rendered)
    body_hash = hashlib.sha256(body_bytes).hexdigest()
    fe.body_sha256 = body_hash
    out = target_dir / fe.path
    if not dry_run:
        atomic_write(out, body_bytes)
    return out


def _is_pure_text(fe: FileEntry) -> bool:
    """Files rendered without a YAML provenance prefix (interpreter would
    choke on it). Currently shell wrappers under ``.claude/lib/``.
    """
    return str(fe.path).endswith(".sh")


def _render_pure_json(
    fe: FileEntry,
    env: Environment,
    target_dir: Path,
    *,
    dry_run: bool,
    freeze_time: datetime | None,  # noqa: ARG001 — kept for dispatch signature parity
) -> Path:
    """Render pure JSON (no frontmatter prefix) — used for hooks.json (jq-parseable).

    Provenance is intentionally omitted; hooks.json is small and reproducible from
    the template. The frontmatter invariant gate explicitly excludes hooks.json.
    """
    template = env.get_template(fe.template)
    rendered = template.render(**fe.context)
    try:
        data: dict[str, Any] = json.loads(rendered)
    except json.JSONDecodeError as e:
        msg = f"Template {fe.template} rendered invalid JSON for {fe.path}: {e}"
        raise ValueError(msg) from e
    if not isinstance(data, dict):
        msg = f"Template {fe.template} must render a JSON object (got {type(data).__name__})"
        raise ValueError(msg)
    body_bytes = _format_settings_json(data)
    body_hash = hashlib.sha256(body_bytes).hexdigest()
    fe.body_sha256 = body_hash
    out = target_dir / fe.path
    if not dry_run:
        atomic_write(out, body_bytes)
    return out


def _render_json_file(
    fe: FileEntry,
    env: Environment,
    target_dir: Path,
    *,
    dry_run: bool,
    freeze_time: datetime | None,
) -> Path:
    """settings.json — JSON body wrapped in YAML provenance frontmatter."""
    return _render_settings_json(
        fe,
        env,
        target_dir,
        dry_run=dry_run,
        freeze_time=freeze_time,
    )


def _split_template_frontmatter(rendered: str) -> tuple[dict[str, Any], str]:
    """If rendered text starts with YAML frontmatter (---...---), split and parse it.

    Returns (template_frontmatter_dict, body_without_frontmatter). When no
    frontmatter is present returns ({}, rendered) unchanged.
    """
    if not rendered.startswith("---\n"):
        return {}, rendered
    end = rendered.find("\n---\n", 4)
    if end == -1:
        return {}, rendered
    try:
        parsed = yaml.safe_load(rendered[4:end])
    except yaml.YAMLError:
        return {}, rendered
    if not isinstance(parsed, dict):
        return {}, rendered
    return parsed, rendered[end + 5 :]


def _render_text_file(
    fe: FileEntry,
    env: Environment,
    target_dir: Path,
    *,
    dry_run: bool,
    freeze_time: datetime | None,
    merge_reports: dict[Path, MergeReport] | None = None,
) -> Path:
    template = env.get_template(fe.template)
    rendered = template.render(**fe.context)
    # If template authored its own frontmatter (e.g. SubAgent name/description/tools/model),
    # merge it into the single provenance frontmatter so Claude Code's loaders see one block.
    template_fm, body_text = _split_template_frontmatter(rendered)
    out = target_dir / fe.path
    # Block-merge: caller signals "this file is mergeable" by passing a
    # non-None merge_reports dict. We splice OLD user blocks into NEW before
    # hashing. Parse failures fall through to plain REPLACE.
    if merge_reports is not None and out.exists():
        body_text = _try_block_merge(out, body_text, fe.path, merge_reports)
    body_bytes = _normalize_body(body_text)
    body_hash = hashlib.sha256(body_bytes).hexdigest()
    fe.body_sha256 = body_hash
    fm = _build_provenance(fe, freeze_time)
    # Template-supplied keys take precedence for display fields (name/description/tools/model);
    # provenance fields stay authoritative.
    for k, v in template_fm.items():
        fm.setdefault(k, v)
    # Memory files are user-append targets (wrapup writes to them freely).
    # Injecting content_hash would cause verify to fail after any wrapup write.
    if not str(fe.path).startswith("memory/"):
        fm["content_hash"] = body_hash
    final_bytes = _format_frontmatter(fm).encode("utf-8") + body_bytes
    if not dry_run:
        atomic_write(out, final_bytes)
    return out


def _try_block_merge(
    out: Path,
    new_body: str,
    rel_path: Path,
    merge_reports: dict[Path, MergeReport],
) -> str:
    """Read OLD body (sans frontmatter) at ``out`` and merge with ``new_body``.

    On any parse failure, log nothing and return ``new_body`` unchanged — the
    caller already vetted mergeability via reconcile, so a parse failure here
    is a rare race (file edited mid-make). Falling through to plain REPLACE
    is the safe behaviour.
    """
    try:
        existing = out.read_text(encoding="utf-8")
    except OSError:
        return new_body
    _, old_body = _split_existing_frontmatter(existing)
    try:
        merged, report = block_merge(old_body, new_body)
    except Exception:  # noqa: BLE001 — fall back to REPLACE on any merge failure
        return new_body
    merge_reports[rel_path] = report
    return merged


def _split_existing_frontmatter(text: str) -> tuple[str, str]:
    """Strip a leading ``---\\n…\\n---\\n`` block; return (frontmatter, body)."""
    if not text.startswith("---\n"):
        return "", text
    end = text.find("\n---\n", 4)
    if end == -1:
        return "", text
    return text[: end + 5], text[end + 5 :]


def render(
    blueprint: Blueprint,
    target_dir: Path,
    *,
    dry_run: bool = False,
    freeze_time: datetime | None = None,
    merge_paths: set[Path] | None = None,
    merge_reports: dict[Path, MergeReport] | None = None,
) -> list[Path]:
    """Render blueprint to target_dir.

    ``merge_paths`` — when non-empty, files at those (relative) paths receive
    block-marker-aware merge: NEW template structure with OLD ``user:<id>``
    block contents preserved. Spec: docs/reference/block-merge-spec.md.

    ``merge_reports`` — optional out-dict. When provided, each successfully
    merged path is recorded with its ``MergeReport`` so the CLI can display
    what was preserved/seeded/orphaned.

    Returns list of paths written (or would-write paths if dry_run).
    """
    env = _make_env()
    written: list[Path] = []
    paths_to_merge = merge_paths or set()
    for fe in blueprint.files:
        if _is_hooks_json(fe):
            out = _render_pure_json(
                fe,
                env,
                target_dir,
                dry_run=dry_run,
                freeze_time=freeze_time,
            )
        elif _is_settings_json(fe):
            out = _render_json_file(
                fe,
                env,
                target_dir,
                dry_run=dry_run,
                freeze_time=freeze_time,
            )
        elif _is_pure_text(fe):
            out = _render_pure_text(
                fe,
                env,
                target_dir,
                dry_run=dry_run,
                freeze_time=freeze_time,
            )
        else:
            # Only mergeable text files plumb the merge_reports map; JSON
            # files don't support markers in v1.
            file_merge_reports = (
                merge_reports if merge_reports is not None and fe.path in paths_to_merge else None
            )
            out = _render_text_file(
                fe,
                env,
                target_dir,
                dry_run=dry_run,
                freeze_time=freeze_time,
                merge_reports=file_merge_reports,
            )
        written.append(out)
    return written
