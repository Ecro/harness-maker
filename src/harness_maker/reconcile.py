"""Reconciler (Task 3.3) — decide per-file action in brownfield projects.

Decision matrix:
- new-only (no existing file)                                → BOTH
- harness.yaml                                               → REPLACE (always; user
                                                                fields survive via
                                                                answers_from_harness_yaml)
- existing has no frontmatter at all                         → KEEP (user file)
- existing has frontmatter but no content_hash AND
  generated_by == "harness-maker"                            → REPLACE (legacy ours,
                                                                pre-content_hash era)
- existing has frontmatter but no content_hash, not ours     → KEEP (user file w/ fm)
- existing hash matches our recompute                        → REPLACE (safe overwrite)
- existing hash mismatches AND both OLD/NEW have markers     → MERGE_BLOCK (3-way)
- existing hash mismatches otherwise                         → KEEP (legacy fallback)

Block-marker spec: docs/reference/block-merge-spec.md

Orphan-sweep (ADR-005, Phase 0):
``sweep_orphans()`` walks the rendered tree, finds files NOT in the current
blueprint, and decides ours-clean (delete) vs ours-modified / theirs (keep +
warn). Ours-identification uses BOTH a frontmatter check (generated_by +
content_hash) AND a fallback lookup in ``.hm-render-manifest.jsonl`` (covers
.sh, .json, .toml files that legally lack frontmatter). Warnings are appended
to ``.claude/observability/orphans-<YYYY-MM-DD>.jsonl``. Files outside the
five enumerated top-level locations (.claude/, .cursor/, .codex/, .agents/,
AGENTS.md) are NEVER touched — the renderer only writes there.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import yaml

from harness_maker.block_merge import MarkerStyle, ParseError, has_markers, parse_segments
from harness_maker.io_utils import atomic_append
from harness_maker.models import Blueprint, ConflictItem, ReconcileDecision
from harness_maker.render import RENDER_MANIFEST_NAME, resolve_output_path

# Templates ship inside the package; reconcile peeks at the source to know
# whether a fresh render will produce markers without re-rendering.
_TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"

# Top-level locations the renderer ever writes. Used to bound the orphan-sweep
# walk so user-owned dirs (src/, tests/, docs/, ...) are never inspected.
_SWEEP_ROOTS: tuple[str, ...] = (".claude", ".cursor", ".codex", ".agents")
_SWEEP_ROOT_FILES: tuple[str, ...] = ("AGENTS.md",)


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
        existing_path = resolve_output_path(existing_dir, fe.path)
        if not existing_path.exists():
            conflicts.append(
                ConflictItem(path=fe.path, decision=ReconcileDecision.BOTH, reason="new-only"),
            )
            continue
        # harness.yaml is the primary config file. Always REPLACE so template
        # additions (e.g. new second_brain section) propagate on re-render.
        # User-maintained fields (mechanical_checks, etc.) survive because
        # answers_from_harness_yaml reads them back before the render pass.
        if fe.path.name == "harness.yaml":
            conflicts.append(
                ConflictItem(
                    path=fe.path,
                    decision=ReconcileDecision.REPLACE,
                    reason="config-always-replace",
                ),
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
        # AGENTS.md uses HTML-comment metadata (no YAML frontmatter — Codex shows
        # frontmatter as literal text). MVP: always MERGE_BLOCK so user-edited
        # <!-- @hm:user:* --> blocks survive re-renders.
        if fe.path == Path("AGENTS.md"):
            conflicts.append(
                ConflictItem(
                    path=fe.path,
                    decision=ReconcileDecision.MERGE_BLOCK,
                    reason="codex-agents-merge",
                ),
            )
            continue
        # hooks.json is pure JSON (no frontmatter). Phase 1+3 (PLAN-onboarding-
        # backup-friction, ADR-003/006): all three schemas use in-place 3-way
        # merge so user-added entries survive template updates. Schema dispatch
        # happens in render: Claude Code (hooks/hooks.json) and Codex
        # (.codex/hooks.json) use the nested {matcher?, hooks:[{type, command}]}
        # shape; Cursor (.cursor/hooks.json) uses the flat {matcher?, command}
        # shape. `reason="hooks-in-place-merge"` is the dispatch flag the render
        # path reads to invoke _merge_hooks_json instead of overwriting.
        if (
            fe.path == Path("hooks/hooks.json")
            or fe.path == Path(".cursor/hooks.json")
            or fe.path == Path(".codex/hooks.json")
        ):
            conflicts.append(
                ConflictItem(
                    path=fe.path,
                    decision=ReconcileDecision.MERGE_JSON,
                    reason="hooks-in-place-merge",
                ),
            )
            continue
        # Codex TOML files carry no YAML frontmatter (tomllib would reject it).
        # Phase 2 (PLAN-onboarding-backup-friction, ADR-004/007): when both
        # the shipped template and the existing file carry `# @hm:user:*`
        # markers at TOML statement level, return MERGE_BLOCK so user blocks
        # survive re-render. Else REPLACE so template updates land.
        if str(fe.path).endswith(".toml"):
            decision, reason = _decide_hash_comment_branch(fe.template, existing_path)
            conflicts.append(
                ConflictItem(path=fe.path, decision=decision, reason=reason),
            )
            continue
        # Generated wrappers under `.claude/lib/*.sh` carry no provenance
        # frontmatter (interpreters reject YAML preambles). Phase 2 same rule
        # as TOML: marker-aware MERGE_BLOCK when both sides have markers,
        # REPLACE otherwise.
        if str(fe.path).endswith(".sh"):
            decision, reason = _decide_hash_comment_branch(fe.template, existing_path)
            conflicts.append(
                ConflictItem(path=fe.path, decision=decision, reason=reason),
            )
            continue
        fm, body = parse_frontmatter(existing_path)
        if fm is None:
            conflicts.append(
                ConflictItem(
                    path=fe.path,
                    decision=ReconcileDecision.KEEP,
                    reason="no-frontmatter",
                ),
            )
            continue
        if "content_hash" not in fm:
            # Legacy ours: pre-content_hash era (e.g. v0.4.7 memory templates)
            # left a `generated_by` marker but no hash. Without backfill these
            # files KEEP forever despite the user never editing them. Detect
            # via the generated_by stamp; backup() (called by the CLI before
            # render) preserves the legacy file under .backup-<ts>/.
            #
            # Special case: memory/ files intentionally omit content_hash so
            # wrapup can append freely. Use MERGE_BLOCK when BOTH the template
            # and the existing body carry @hm:user:* block markers — that
            # preserves user-accumulated wiki/failure entries across re-renders.
            if fm.get("generated_by") == "harness-maker":
                decision, reason = _decide_user_modified(fe.template, body)
                if decision == ReconcileDecision.MERGE_BLOCK:
                    conflicts.append(
                        ConflictItem(
                            path=fe.path,
                            decision=ReconcileDecision.MERGE_BLOCK,
                            reason="memory-block-merge",
                        ),
                    )
                else:
                    conflicts.append(
                        ConflictItem(
                            path=fe.path,
                            decision=ReconcileDecision.REPLACE,
                            reason="legacy-no-hash-but-ours",
                        ),
                    )
            else:
                conflicts.append(
                    ConflictItem(
                        path=fe.path,
                        decision=ReconcileDecision.KEEP,
                        reason="frontmatter-no-hash-not-ours",
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


def _decide_hash_comment_branch(
    template_name: str,
    existing_path: Path,
) -> tuple[ReconcileDecision, str]:
    """Phase 2 marker-aware dispatch for hash-comment file types (.toml, .sh).

    Returns MERGE_BLOCK when both shipped template and existing file carry
    `# @hm:user:*` HASH_COMMENT markers; KEEP on malformed marker syntax in
    the existing file (preserve user data); REPLACE otherwise (so template
    updates land for marker-less files).
    """
    template_path = _TEMPLATE_DIR / template_name
    try:
        template_src = template_path.read_text(encoding="utf-8")
    except OSError:
        # Template unreadable → conservative REPLACE preserves prior behaviour.
        return ReconcileDecision.REPLACE, "hashcomment-template-unreadable"
    try:
        existing_src = existing_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ReconcileDecision.REPLACE, "hashcomment-existing-unreadable"
    if has_markers(template_src, MarkerStyle.HASH_COMMENT) and has_markers(
        existing_src,
        MarkerStyle.HASH_COMMENT,
    ):
        # Validate existing marker syntax before promising a merge — a typo'd
        # close-marker should KEEP the user's file rather than silently REPLACE.
        try:
            parse_segments(existing_src, MarkerStyle.HASH_COMMENT)
        except ParseError:
            return ReconcileDecision.KEEP, "hashcomment-malformed-markers"
        return ReconcileDecision.MERGE_BLOCK, "hashcomment-marker-merge"
    return ReconcileDecision.REPLACE, "pure-hashcomment-no-markers"


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
    """Snapshot existing harness state (``.claude/`` + ``.cursor/``) to
    ``.backup-<ISO>/``. Microsecond + counter avoids collision.

    Backup layout (Phase 2.4+): backup directory mirrors the project root,
    holding both ``.claude/`` and ``.cursor/`` subtrees so cursor-target
    assets are also restorable. Pre-Phase-2.4 backups have a flat layout
    (``.backup-<ISO>/<files>``); manual restore needed in that case.
    """
    iso = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    candidate = existing_dir.parent / f".backup-{iso}"
    n = 0
    while candidate.exists():
        n += 1
        candidate = existing_dir.parent / f".backup-{iso}-{n}"
    if existing_dir.exists():
        shutil.copytree(existing_dir, candidate / existing_dir.name)
    cursor_dir = existing_dir.parent / ".cursor"
    if cursor_dir.exists():
        shutil.copytree(cursor_dir, candidate / ".cursor")
    codex_dir = existing_dir.parent / ".codex"
    if codex_dir.exists():
        shutil.copytree(codex_dir, candidate / ".codex")
    agents_skills = existing_dir.parent / ".agents"
    if agents_skills.exists():
        shutil.copytree(agents_skills, candidate / ".agents")
    agents_md = existing_dir.parent / "AGENTS.md"
    if agents_md.exists():
        shutil.copy2(agents_md, candidate / "AGENTS.md")
    return candidate


# ──────────────────────────────────────────────────────────────────────────────
# Orphan-sweep (ADR-005, Phase 0)
# ──────────────────────────────────────────────────────────────────────────────


class OrphanSweepReport:
    """Summary of one ``sweep_orphans()`` invocation.

    ``deleted`` paths are relative to project_root; ``kept`` entries include
    a short classifier so the caller (CLI) can format human-readable output.
    """

    __slots__ = ("deleted", "kept")

    def __init__(self) -> None:
        self.deleted: list[Path] = []
        self.kept: list[tuple[Path, str]] = []


def _load_render_manifest(target_dir: Path) -> dict[str, set[str]]:
    """Parse ``<target_dir>/.hm-render-manifest.jsonl`` into ``{path: {hashes}}``.

    Malformed lines are skipped silently — the manifest is append-only audit
    data; a single corrupt entry should not block a sweep. Missing file
    returns an empty dict (sweep falls back to frontmatter-only detection).
    """
    manifest_path = target_dir / RENDER_MANIFEST_NAME
    out: dict[str, set[str]] = {}
    if not manifest_path.is_file():
        return out
    try:
        text = manifest_path.read_text(encoding="utf-8")
    except OSError:
        return out
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            rec = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        if not isinstance(rec, dict):
            continue
        path = rec.get("path")
        content_hash = rec.get("content_hash")
        if not isinstance(path, str) or not isinstance(content_hash, str):
            continue
        out.setdefault(path, set()).add(content_hash)
    return out


def _iter_disk_files(project_root: Path) -> list[Path]:
    """Walk the five enumerated render locations, returning relative paths.

    The manifest itself (``.claude/.hm-render-manifest.jsonl``) is excluded —
    it is internal harness-maker state, not a renderable. Per-session loop
    markers (``.claude/.hm-loop-*``) are excluded for the same reason.
    """
    found: list[Path] = []
    for root_name in _SWEEP_ROOTS:
        root_dir = project_root / root_name
        if not root_dir.is_dir():
            continue
        for f in root_dir.rglob("*"):
            if not f.is_file():
                continue
            rel = f.relative_to(project_root)
            if rel.name == RENDER_MANIFEST_NAME:
                continue
            if rel.name.startswith(".hm-loop-"):
                continue
            found.append(rel)
    for root_file in _SWEEP_ROOT_FILES:
        p = project_root / root_file
        if p.is_file():
            found.append(Path(root_file))
    return found


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _classify_orphan(
    project_root: Path,
    rel_path: Path,
    manifest: dict[str, set[str]],
) -> tuple[str, str | None]:
    """Decide ours-clean / ours-modified / theirs / missing-in-manifest.

    Returns ``(classification, recorded_hash)``. ``recorded_hash`` is set
    when the file claims frontmatter ownership; useful for the warning log.

    Logic:
    - Frontmatter parses + generated_by == harness-maker + content_hash:
        - body recompute disagrees with frontmatter → ours-modified (KEEP)
        - hash in manifest under same path → ours-clean (DELETE)
        - hash NOT in manifest → missing-in-manifest (KEEP)
    - Frontmatter parses + content_hash but generated_by != harness-maker
      → theirs (KEEP)
    - Frontmatter present, no content_hash, generated_by mismatch → theirs
    - No frontmatter (binary, JSON, TOML, .sh):
        - current bytes hash matches any manifest entry for this path
          → ours-clean (DELETE)
        - otherwise → theirs (KEEP)
    """
    abs_path = project_root / rel_path
    rel_key = str(rel_path).replace("\\", "/")
    try:
        raw = abs_path.read_bytes()
    except OSError:
        return ("theirs", None)
    current_hash = _sha256_bytes(raw)

    try:
        fm, body = parse_frontmatter(abs_path)
    except (OSError, UnicodeError):
        fm, body = None, raw

    if fm is not None and fm.get("generated_by") == "harness-maker":
        recorded = fm.get("content_hash")
        if isinstance(recorded, str):
            recomputed = compute_body_hash(body)
            if recorded != recomputed:
                return ("ours-modified", recorded)
            if recorded in manifest.get(rel_key, set()):
                return ("ours-clean", recorded)
            return ("missing-in-manifest", recorded)
        # Pre-content_hash legacy ours — conservative path: keep + warn.
        return ("theirs", None)

    if fm is not None:
        return ("theirs", None)

    # No frontmatter (pure-text / pure-json / pure-toml / binary).
    if current_hash in manifest.get(rel_key, set()):
        return ("ours-clean", current_hash)
    return ("theirs", None)


def _log_orphan_kept(
    project_root: Path,
    rel_path: Path,
    classification: str,
    recorded_hash: str | None,
) -> None:
    """Append a JSON record to ``.claude/observability/orphans-<date>.jsonl``.

    File is created on first write. Each record carries enough context for
    a follow-up audit (date stamped path, classifier, optional recorded hash).
    """
    today = date.today().isoformat()
    obs_dir = project_root / ".claude" / "observability"
    obs_dir.mkdir(parents=True, exist_ok=True)
    log_path = obs_dir / f"orphans-{today}.jsonl"
    record: dict[str, Any] = {
        "path": str(rel_path).replace("\\", "/"),
        "classification": classification,
        "timestamp": datetime.now(UTC).isoformat(),
    }
    if recorded_hash is not None:
        record["recorded_hash"] = recorded_hash
    line = json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n"
    # Single os.write() on O_APPEND fd — interleaving impossible.
    # The buffered ``open("a")`` could split across syscalls. See atomic_append docstring.
    atomic_append(log_path, line)


def _normalize_expected_path(fe_path: Path) -> str:
    """Convert a FileEntry.path to the project-root-relative key used on disk.

    ``synthesize.py`` stores ``.claude/``-bound paths WITHOUT the prefix
    (e.g. ``"commands/hm/refresh.md"``), but stores sibling-tree paths WITH
    their prefix (e.g. ``".cursor/rules/harness.mdc"``, ``"AGENTS.md"``).
    ``_iter_disk_files`` always returns project-root-relative keys, so the
    ``.claude/``-bound case must be prefixed before set comparison —
    otherwise every ``.claude/`` blueprint file misses the ``expected`` set
    and gets classified as an orphan candidate, silently deleting ours-clean
    files (P0 bug).

    The branch list mirrors ``render.resolve_output_path``: any path string
    starting with one of the renderer's sibling locations (``.cursor/``,
    ``.codex/``, ``.agents/``) or equal to ``AGENTS.md`` is already
    project-root-relative and passes through unchanged.
    """
    path_str = str(fe_path).replace("\\", "/")
    if (
        path_str.startswith(".cursor/")
        or path_str.startswith(".codex/")
        or path_str.startswith(".agents/")
        or path_str == "AGENTS.md"
    ):
        return path_str
    return ".claude/" + path_str


def sweep_orphans(project_root: Path, blueprint: Blueprint) -> OrphanSweepReport:
    """Delete blueprint-orphaned files that fingerprint as ours; keep+warn the rest.

    Bounded to the five render locations (``.claude/``, ``.cursor/``,
    ``.codex/``, ``.agents/``, ``AGENTS.md``). Files outside this set are
    never inspected — the renderer never writes there, so they cannot be
    orphans of harness-maker.

    R4 safety property: user-owned files under any of the five locations
    that the renderer never wrote (e.g. ``.claude/observability/adaptive/
    overrides.jsonl``) lack frontmatter AND have no manifest entry, so the
    classifier falls into the "theirs" branch — KEEP + warn.
    """
    expected: set[str] = {_normalize_expected_path(fe.path) for fe in blueprint.files}
    target_dir = project_root / ".claude"
    manifest = _load_render_manifest(target_dir)
    report = OrphanSweepReport()
    for rel_path in _iter_disk_files(project_root):
        rel_key = str(rel_path).replace("\\", "/")
        if rel_key in expected:
            continue
        classification, recorded_hash = _classify_orphan(
            project_root,
            rel_path,
            manifest,
        )
        if classification == "ours-clean":
            try:
                (project_root / rel_path).unlink()
            except OSError as e:
                print(
                    f"WARN: orphan-sweep could not delete {rel_key}: {e}",
                    file=sys.stderr,
                )
                report.kept.append((rel_path, "unlink-failed"))
                continue
            report.deleted.append(rel_path)
        else:
            print(
                f"WARN: orphan-sweep KEPT {rel_key} ({classification}) — manual review needed",
                file=sys.stdout,
            )
            _log_orphan_kept(project_root, rel_path, classification, recorded_hash)
            report.kept.append((rel_path, classification))
    return report
