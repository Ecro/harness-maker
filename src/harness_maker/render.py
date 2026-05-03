"""Renderer (Task 3.2) — render Blueprint FileEntries to disk with deterministic output.

Determinism contract (per amendment §C):
- Jinja2 env: StrictUndefined, no autoescape, keep_trailing_newline=True.
- Body: normalize CRLF→LF, exactly one trailing LF, UTF-8 bytes.
- Frontmatter: YAML, sort_keys=False (insertion order), allow_unicode=True.
- settings.json: JSON, sort_keys=True (cross-edit determinism).
- content_hash: sha256 of the normalized body bytes; injected into frontmatter.
- freeze_time: when set, generated_at is fixed (used in tests + CI).
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
from harness_maker.io_utils import atomic_write
from harness_maker.models import Blueprint, FileEntry

# Module constants
TEMPLATE_DIR = Path(__file__).resolve().parent.parent.parent / "templates"
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
    freeze_time: datetime | None,
) -> Path:
    """Render JSON template, embed _provenance with content_hash, prepend YAML frontmatter.

    Output layout:
      ---
      <YAML frontmatter>
      ---
      <JSON body>

    The leading `---` satisfies the cross-phase frontmatter invariant.
    The verifier strips the frontmatter before json.loads.
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
    prov = _build_provenance(fe, freeze_time)
    # Provenance lives in YAML frontmatter only — keeping it out of the JSON body
    # makes reconciler hash recomputation stable across re-renders.
    body_bytes = _format_settings_json(data)
    body_hash = hashlib.sha256(body_bytes).hexdigest()
    fe.body_sha256 = body_hash
    prov["content_hash"] = body_hash
    fm_str = _format_frontmatter(prov)
    final_bytes = fm_str.encode("utf-8") + body_bytes
    out = target_dir / fe.path
    if not dry_run:
        atomic_write(out, final_bytes)
    return out


def _is_settings_json(fe: FileEntry) -> bool:
    return fe.path.name == "settings.json" or str(fe.path).endswith("hooks.json")


def _render_json_file(
    fe: FileEntry,
    env: Environment,
    target_dir: Path,
    *,
    dry_run: bool,
    freeze_time: datetime | None,
) -> Path:
    """settings.json / hooks.json — JSON output with _provenance key."""
    return _render_settings_json(
        fe, env, target_dir, dry_run=dry_run, freeze_time=freeze_time,
    )


def _render_text_file(
    fe: FileEntry,
    env: Environment,
    target_dir: Path,
    *,
    dry_run: bool,
    freeze_time: datetime | None,
) -> Path:
    template = env.get_template(fe.template)
    rendered_body = template.render(**fe.context)
    body_bytes = _normalize_body(rendered_body)
    body_hash = hashlib.sha256(body_bytes).hexdigest()
    fe.body_sha256 = body_hash
    fm = _build_provenance(fe, freeze_time)
    fm["content_hash"] = body_hash
    final_bytes = _format_frontmatter(fm).encode("utf-8") + body_bytes
    out = target_dir / fe.path
    if not dry_run:
        atomic_write(out, final_bytes)
    return out


def render(
    blueprint: Blueprint,
    target_dir: Path,
    *,
    dry_run: bool = False,
    freeze_time: datetime | None = None,
) -> list[Path]:
    """Render blueprint to target_dir.

    Returns list of paths written (or would-write paths if dry_run).
    """
    env = _make_env()
    written: list[Path] = []
    for fe in blueprint.files:
        if _is_settings_json(fe):
            out = _render_json_file(
                fe, env, target_dir, dry_run=dry_run, freeze_time=freeze_time,
            )
        else:
            out = _render_text_file(
                fe, env, target_dir, dry_run=dry_run, freeze_time=freeze_time,
            )
        written.append(out)
    return written
