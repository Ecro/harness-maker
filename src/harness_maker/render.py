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

Render manifest (ADR-005, Phase 0):
- Every blueprint file render appends one JSON line to
  ``<target_dir>/.hm-render-manifest.jsonl`` ({path, content_hash, timestamp}).
  The reconcile orphan-sweep uses this manifest as the authoritative
  ours-vs-theirs registry for files that lack provenance frontmatter (.sh,
  .json, .toml). Duplicates are intentionally not collapsed — re-renders
  accumulate so historical hashes remain matchable.
"""

from __future__ import annotations

import hashlib
import json
import tomllib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined

from harness_maker import __version__
from harness_maker.block_merge import MergeReport
from harness_maker.block_merge import merge as block_merge
from harness_maker.io_utils import atomic_append, atomic_write
from harness_maker.models import Blueprint, FileEntry

# Module constants — templates ship inside the harness_maker package so they're
# present in both editable installs (src/harness_maker/templates/) and wheel
# installs (importable as package data).
TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
DEFAULT_FREEZE_TIME = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)

# Append-only audit log consulted by the reconcile orphan-sweep (ADR-005).
# Lives inside the rendered ``.claude/`` directory so it travels with the
# harness and can be inspected/git-ignored alongside other internal state
# files (e.g. ``.hm-loop-*``).
RENDER_MANIFEST_NAME = ".hm-render-manifest.jsonl"


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
    out = resolve_output_path(target_dir, fe.path)
    merged = _shallow_merge_existing_json(out, new_data)
    body_bytes = _format_settings_json(merged)
    body_hash = hashlib.sha256(body_bytes).hexdigest()
    fe.body_sha256 = body_hash
    if not dry_run:
        atomic_write(out, body_bytes)
    return out


# Keys harness-maker has ever written to settings.json.  When a key is
# removed from the template it must be actively dropped on the next render —
# simple {**existing, **new_data} would leave it behind forever.
# NOTE: "env" is intentionally absent — users may set their own env vars.
_SETTINGS_KEYS_OWNED_BY_HARNESS: frozenset[str] = frozenset(
    {
        "statusLine",  # written by <=0.3.x; template no longer emits it
        "preset",
        "permissions",
    }
)


def _shallow_merge_existing_json(
    out: Path,
    new_data: dict[str, Any],
) -> dict[str, Any]:
    """Merge top-level keys: existing's unique keys + new_data (template wins).

    Previously-owned harness-maker keys absent from new_data are removed so
    stale keys don't linger after a template drops them.
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


def resolve_output_path(target_dir: Path, fe_path: Path) -> Path:
    """Resolve where a FileEntry should be written/read.

    `target_dir` 는 보통 `<project>/.claude` (CLI dispatch). `.cursor/`,
    `.codex/`, `.agents/`, `AGENTS.md` 는 `.claude/` 의 sibling 이라
    `target_dir.parent` 기준으로 resolve.

    그 외 자산은 기존대로 ``target_dir / fe_path``. reconcile.py 도 동일
    helper 사용 — 같은 path 에 read/write/backup 이 일관.
    """
    path_str = str(fe_path)
    if (
        path_str.startswith(".cursor/")
        or path_str.startswith(".codex/")
        or path_str.startswith(".agents/")
        or path_str == "AGENTS.md"
    ):
        return target_dir.parent / fe_path
    return target_dir / fe_path


def _is_cursor_mdc(fe: FileEntry) -> bool:
    """Cursor rules — ``.cursor/rules/*.mdc``. Plain markdown + Cursor frontmatter
    (``description``, ``globs``, ``alwaysApply``). 우리 ``content_hash`` 등 메타는
    Phase 1 A1.frontmatter 검증 결과 따라 추후 sidecar 분리 가능 — 현재는 jinja
    template 이 frontmatter 자체를 만들어내므로 ``_render_pure_text`` 로 처리.
    """
    return str(fe.path).startswith(".cursor/rules/") and fe.path.suffix == ".mdc"


def _is_cursor_command(fe: FileEntry) -> bool:
    """Cursor slash commands — ``.cursor/commands/*.md``.

    **Currently dead code** — no template feeds ``.cursor/commands/`` because
    Cursor 2.4+ reads ``.claude/commands/hm/*.md`` natively (verified
    empirically via kairos 0.5.7 forensic on 2026-05-08; see
    ``tests/cursor-compat/results-2026-05-08.md``). Kept as a reserved
    dispatch in case a future Cursor release regresses the single-source
    contract — adding a ``templates/cursor/commands/`` directory would be
    sufficient to reactivate it. Until that happens, the dispatch evaluates
    to False on every FileEntry produced by synthesize.
    """
    return str(fe.path).startswith(".cursor/commands/") and fe.path.suffix == ".md"


def _is_cursor_mcp_json(fe: FileEntry) -> bool:
    """Cursor MCP config — ``.cursor/mcp.json`` (pure JSON, no frontmatter)."""
    return str(fe.path) == ".cursor/mcp.json"


def _is_codex_hooks_json(fe: FileEntry) -> bool:
    """Codex hooks — ``.codex/hooks.json`` (pure JSON, PascalCase Codex schema)."""
    return str(fe.path) == ".codex/hooks.json"


def _is_codex_config_toml(fe: FileEntry) -> bool:
    """Codex main config — ``.codex/config.toml`` (pure TOML, no frontmatter)."""
    return str(fe.path) == ".codex/config.toml"


def _is_codex_agent_toml(fe: FileEntry) -> bool:
    """Codex agent definition — ``.codex/agents/<name>.toml`` (pure TOML)."""
    return str(fe.path).startswith(".codex/agents/") and fe.path.suffix == ".toml"


def _is_agents_md(fe: FileEntry) -> bool:
    """AGENTS.md at project root — pure text with HTML-comment metadata."""
    return str(fe.path) == "AGENTS.md"


def _render_pure_toml(
    fe: FileEntry,
    env: Environment,
    target_dir: Path,
    *,
    dry_run: bool,
    freeze_time: datetime | None,  # noqa: ARG001 — kept for dispatch signature parity
) -> Path:
    """Render pure TOML (no frontmatter prefix), validated via tomllib.loads().

    Used for ``.codex/config.toml`` and ``.codex/agents/<name>.toml``.
    Raises ``ValueError`` (with template name) if the rendered output is not
    valid TOML — mirrors ``_render_pure_json`` error contract.
    """
    template = env.get_template(fe.template)
    rendered = template.render(**fe.context)
    try:
        tomllib.loads(rendered)
    except tomllib.TOMLDecodeError as e:
        msg = f"Template {fe.template} rendered invalid TOML for {fe.path}: {e}"
        raise ValueError(msg) from e
    body_bytes = _normalize_body(rendered)
    body_hash = hashlib.sha256(body_bytes).hexdigest()
    fe.body_sha256 = body_hash
    out = resolve_output_path(target_dir, fe.path)
    if not dry_run:
        atomic_write(out, body_bytes)
    return out


def _render_agents_md(
    fe: FileEntry,
    env: Environment,
    target_dir: Path,
    *,
    dry_run: bool,
    freeze_time: datetime | None,
    merge_reports: dict[Path, MergeReport] | None = None,
) -> Path:
    """Render AGENTS.md as pure text with a leading HTML-comment metadata line.

    AGENTS.md has no YAML frontmatter (Codex would display it as literal text).
    Provenance is stored in ``<!-- harness-maker: content_hash=... version=... -->``.
    Block-merge markers (``<!-- @hm:user:* -->``) work unchanged because Codex
    ignores HTML comments.

    When ``merge_reports`` is provided the existing file's user blocks are
    preserved into the freshly rendered template — same contract as the YAML
    frontmatter path in ``_render_text_file``.
    """
    template = env.get_template(fe.template)
    rendered = template.render(**fe.context)
    body_text = rendered

    # Block-merge: splice OLD user blocks into fresh template body.
    if merge_reports is not None:
        out_path = resolve_output_path(target_dir, fe.path)
        if out_path.exists():
            try:
                existing = out_path.read_text(encoding="utf-8")
                old_body = _strip_agents_md_metadata(existing)
                merged, report = block_merge(old_body, rendered)
                body_text = merged
                merge_reports[fe.path] = report
            except Exception:  # noqa: BLE001 — fall back to plain replace
                pass

    body_bytes = _normalize_body(body_text)
    body_hash = hashlib.sha256(body_bytes).hexdigest()
    fe.body_sha256 = body_hash
    ts = freeze_time.isoformat() if freeze_time else datetime.now(UTC).isoformat()
    metadata = (
        f"<!-- harness-maker: content_hash={body_hash}"
        f" version={__version__} generated_at={ts} -->\n"
    )
    final_bytes = metadata.encode("utf-8") + body_bytes
    out = resolve_output_path(target_dir, fe.path)
    if not dry_run:
        atomic_write(out, final_bytes)
    return out


def _render_pure_text(
    fe: FileEntry,
    env: Environment,
    target_dir: Path,
    *,
    dry_run: bool,
    freeze_time: datetime | None,  # noqa: ARG001 — kept for dispatch signature parity
) -> Path:
    """Render template body verbatim, no provenance frontmatter.

    Used for files whose external consumer rejects a YAML preamble:

    - ``.sh`` wrappers under ``.claude/lib/`` — bash interprets ``---`` as
      a command
    - ``.cursor/rules/*.mdc`` — Cursor frontmatter parser may strict-reject
      our ``content_hash`` / ``generated_by`` keys (Phase 1 A1.frontmatter
      검증 결과에 따라 sidecar 메타 분리 가능)
    - ``.cursor/commands/*.md`` — Cursor slash commands are plain markdown

    Provenance is sacrificed because these files are small, reproducible
    from the template, and re-rendered every time the user runs
    ``/harness-maker:make``. Reconcile of ``.cursor/`` 자산은 Phase 2.4 에서
    별도 정책 (sidecar 또는 항상 REPLACE).
    """
    template = env.get_template(fe.template)
    rendered = template.render(**fe.context)
    body_bytes = _normalize_body(rendered)
    body_hash = hashlib.sha256(body_bytes).hexdigest()
    fe.body_sha256 = body_hash
    out = resolve_output_path(target_dir, fe.path)
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
    """Render pure JSON (no frontmatter prefix).

    Used for files whose external consumer expects pure JSON:

    - ``.claude/hooks/hooks.json`` — jq-parseable, Claude Code spec
    - ``.cursor/mcp.json`` — Cursor MCP config

    Provenance is intentionally omitted; both are small, reproducible from the
    template, and re-rendered every time. Frontmatter invariant gate explicitly
    excludes them.
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
    out = resolve_output_path(target_dir, fe.path)
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
    out = resolve_output_path(target_dir, fe.path)
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


def _strip_agents_md_metadata(text: str) -> str:
    """Strip the leading ``<!-- harness-maker: ... -->\\n`` line from AGENTS.md.

    AGENTS.md uses an HTML-comment first line instead of YAML frontmatter so
    Codex doesn't display provenance fields as literal text. This function
    removes that line so block_merge receives only the template body.
    """
    if text.startswith("<!-- harness-maker:"):
        newline = text.find("\n")
        if newline != -1:
            return text[newline + 1 :]
    return text


_SIBLING_TREE_PREFIXES = (".cursor/", ".codex/", ".agents/")


def _manifest_key_for(fe_path: Path) -> str:
    """Project-root-relative key for the manifest, derived from ``fe.path``.

    Matches the orphan-sweep's disk walk (``_iter_disk_files`` returns keys
    like ``.claude/commands/hm/x.md`` or ``.cursor/rules/x.mdc``). The
    ``synthesize.py`` convention is to store sibling-tree files (``.cursor/
    ``, ``.codex/``, ``.agents/``) and ``AGENTS.md`` WITH their prefix and
    ``.claude/``-bound files WITHOUT it; this helper restores the missing
    ``.claude/`` so writer and reader agree on a single key shape.

    Deriving from ``fe.path`` (not the resolved ``out_path``) keeps the
    manifest deterministic across runs even when callers pass a transient
    ``target_dir`` (e.g. ``tmp_path`` in unit tests) — the manifest key
    must never leak parent-dir basenames.
    """
    p = str(fe_path).replace("\\", "/")
    if p == "AGENTS.md" or p.startswith(_SIBLING_TREE_PREFIXES):
        return p
    return ".claude/" + p


def _append_render_manifest(
    target_dir: Path,
    fe_path: Path,
    content_hash: str,
    *,
    freeze_time: datetime | None,
) -> None:
    """Append one JSON line to ``<target_dir>/.hm-render-manifest.jsonl``.

    The recorded ``path`` is **project-root-relative** (derived from
    ``fe.path`` via ``_manifest_key_for``). That convention matches the
    orphan-sweep's disk walk so a key written here is queryable as-is on
    the next reconcile — covers both ``.claude/``-bound files
    (``commands/hm/x.md`` → ``.claude/commands/hm/x.md``) and sibling
    locations (``.cursor/``, ``.codex/``, ``.agents/``, ``AGENTS.md``).

    POSIX guarantees that a single ``write()`` <= PIPE_BUF (4096 bytes) is
    atomic. Each record we emit is well below that limit (path + 64-char
    hex hash + iso8601 timestamp), so a plain append is safe. Re-renders of
    the same file produce additional lines — the orphan-sweep does an
    any-match against the historical set, so duplicates are wanted, not
    a bug.

    The manifest file is created on first append. Errors are propagated:
    a render that cannot record its manifest entry would silently break
    ADR-005's orphan detection, so failure should surface.

    Phase 0 deliberately does NOT inject ``.hm-render-manifest.jsonl`` into
    the user's ``.gitignore`` — no gitignore template ships with the harness
    yet (PLAN-health-consolidation Phase 0 calls for the addition, but the
    template surface does not exist). Wiring the entry is deferred to a
    later phase / wrapup stage. Users with the file showing in ``git status``
    can add the line manually until then.
    """
    target_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = target_dir / RENDER_MANIFEST_NAME
    ts = (freeze_time or datetime.now(UTC)).isoformat()
    record = {
        "path": _manifest_key_for(fe_path),
        "content_hash": content_hash,
        "timestamp": ts,
    }
    line = json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n"
    # Single os.write() on O_APPEND fd — concurrent renderers cannot interleave.
    # The buffered ``open("a")`` could split across syscalls. See atomic_append docstring.
    atomic_append(manifest_path, line)


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

    Side-effect: every rendered FileEntry appends one JSON line to
    ``<target_dir>/.hm-render-manifest.jsonl`` (ADR-005). Skipped when
    ``dry_run`` is True so the audit log only reflects on-disk state.

    Returns list of paths written (or would-write paths if dry_run).
    """
    env = _make_env()
    written: list[Path] = []
    paths_to_merge = merge_paths or set()
    for fe in blueprint.files:
        if _is_hooks_json(fe) or _is_cursor_mcp_json(fe) or _is_codex_hooks_json(fe):
            out = _render_pure_json(
                fe,
                env,
                target_dir,
                dry_run=dry_run,
                freeze_time=freeze_time,
            )
        elif _is_codex_config_toml(fe) or _is_codex_agent_toml(fe):
            out = _render_pure_toml(
                fe,
                env,
                target_dir,
                dry_run=dry_run,
                freeze_time=freeze_time,
            )
        elif _is_agents_md(fe):
            agents_merge = (
                merge_reports if merge_reports is not None and fe.path in paths_to_merge else None
            )
            out = _render_agents_md(
                fe,
                env,
                target_dir,
                dry_run=dry_run,
                freeze_time=freeze_time,
                merge_reports=agents_merge,
            )
        elif _is_settings_json(fe):
            out = _render_json_file(
                fe,
                env,
                target_dir,
                dry_run=dry_run,
                freeze_time=freeze_time,
            )
        elif _is_pure_text(fe) or _is_cursor_mdc(fe) or _is_cursor_command(fe):
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
        # ADR-005: record the on-disk render. Skip during dry_run so the
        # audit log only reflects files that actually exist.
        if not dry_run and fe.body_sha256 is not None:
            _append_render_manifest(
                target_dir,
                fe.path,
                fe.body_sha256,
                freeze_time=freeze_time,
            )
    return written
