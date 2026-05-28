"""Orphan-sweep test matrix (ADR-005, Phase 0, R4 safety property).

Each test seeds a tmp_path project root with a single orphan file (= present
on disk, absent from blueprint.files) and asserts the classifier's verdict:

- ours-clean       → DELETE
- ours-modified    → KEEP + observability log entry
- theirs-*         → KEEP + observability log entry
- missing-in-manifest → KEEP + observability log entry
- R4 (adaptive)    → KEEP (user telemetry never swept)

Tests run the real ``sweep_orphans`` against a real on-disk manifest — no
mocks. The manifest is hand-assembled to exercise each branch deterministically.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from harness_maker.models import Blueprint, FileEntry
from harness_maker.reconcile import (
    OrphanSweepReport,
    compute_body_hash,
    sweep_orphans,
)
from harness_maker.render import RENDER_MANIFEST_NAME


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _append_manifest(target_dir: Path, path_str: str, content_hash: str) -> None:
    target_dir.mkdir(parents=True, exist_ok=True)
    manifest = target_dir / RENDER_MANIFEST_NAME
    line = json.dumps(
        {
            "path": path_str,
            "content_hash": content_hash,
            "timestamp": "2026-05-16T00:00:00+00:00",
        },
        sort_keys=True,
    )
    with manifest.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def _frontmatter_doc(content_hash: str, generated_by: str = "harness-maker") -> str:
    """Build a minimal frontmatter-wrapped file matching the renderer's contract."""
    return f"---\ngenerated_by: {generated_by}\ncontent_hash: {content_hash}\n---\nhello\n"


def _hash_for(body: str) -> str:
    return compute_body_hash(body.encode("utf-8"))


def _read_orphan_log(project_root: Path) -> list[dict[str, str]]:
    """Read all observability orphan logs (date-stamped) into one flat list."""
    obs = project_root / ".claude" / "observability"
    if not obs.is_dir():
        return []
    out: list[dict[str, str]] = []
    for log in sorted(obs.glob("orphans-*.jsonl")):
        for line in log.read_text(encoding="utf-8").splitlines():
            if line.strip():
                out.append(json.loads(line))
    return out


def _empty_blueprint() -> Blueprint:
    """Blueprint with zero files — every on-disk file becomes an orphan candidate."""
    return Blueprint()


@pytest.fixture
def project_root(tmp_path: Path) -> Path:
    """Initialize the .claude/ subtree so the manifest helper has a parent dir."""
    (tmp_path / ".claude").mkdir()
    return tmp_path


def test_ours_clean_deleted(project_root: Path) -> None:
    """Frontmatter generated_by=harness-maker + content_hash in manifest → DELETE."""
    body = "hello\n"
    h = _hash_for(body)
    target_file = project_root / ".claude" / "commands" / "hm" / "legacy.md"
    _write(target_file, _frontmatter_doc(h))
    _append_manifest(project_root / ".claude", ".claude/commands/hm/legacy.md", h)
    report: OrphanSweepReport = sweep_orphans(project_root, _empty_blueprint())
    assert not target_file.exists(), "ours-clean orphan must be deleted"
    assert report.deleted == [Path(".claude/commands/hm/legacy.md")]
    assert report.kept == []


def test_ours_modified_kept_with_warning(project_root: Path) -> None:
    """Frontmatter present + content_hash, but body bytes drift → KEEP + warn."""
    original_hash = _hash_for("hello\n")
    target_file = project_root / ".claude" / "commands" / "hm" / "edited.md"
    edited = (
        "---\n"
        "generated_by: harness-maker\n"
        f"content_hash: {original_hash}\n"
        "---\n"
        "USER EDITED THIS LINE\n"
    )
    _write(target_file, edited)
    _append_manifest(
        project_root / ".claude",
        ".claude/commands/hm/edited.md",
        original_hash,
    )
    report = sweep_orphans(project_root, _empty_blueprint())
    assert target_file.exists(), "ours-modified must be preserved"
    kept_paths = [p for p, _ in report.kept]
    assert Path(".claude/commands/hm/edited.md") in kept_paths
    log = _read_orphan_log(project_root)
    classifications = {(r["path"], r["classification"]) for r in log}
    assert (".claude/commands/hm/edited.md", "ours-modified") in classifications


def test_theirs_no_frontmatter_kept_with_warning(project_root: Path) -> None:
    """No frontmatter + path NOT in manifest → KEEP + warn."""
    target_file = project_root / ".claude" / "lib" / "user_script.sh"
    _write(target_file, "#!/usr/bin/env bash\nuser code\n")
    report = sweep_orphans(project_root, _empty_blueprint())
    assert target_file.exists()
    kept_paths = [p for p, _ in report.kept]
    assert Path(".claude/lib/user_script.sh") in kept_paths
    log = _read_orphan_log(project_root)
    assert any(
        r["path"] == ".claude/lib/user_script.sh" and r["classification"] == "theirs" for r in log
    )


def test_theirs_with_frontmatter_kept_with_warning(project_root: Path) -> None:
    """Frontmatter present but generated_by != harness-maker → KEEP + warn."""
    target_file = project_root / ".claude" / "agents" / "user_agent.md"
    body = "---\nname: user_agent\ngenerated_by: hand-written\n---\nuser content\n"
    _write(target_file, body)
    report = sweep_orphans(project_root, _empty_blueprint())
    assert target_file.exists()
    kept_paths = [p for p, _ in report.kept]
    assert Path(".claude/agents/user_agent.md") in kept_paths
    log = _read_orphan_log(project_root)
    assert any(
        r["path"] == ".claude/agents/user_agent.md" and r["classification"] == "theirs" for r in log
    )


def test_missing_in_manifest_kept_with_warning(project_root: Path) -> None:
    """Frontmatter says ours + content_hash valid against body, but manifest
    has no entry for this path → KEEP (cannot prove provenance)."""
    body = "hello\n"
    h = _hash_for(body)
    target_file = project_root / ".claude" / "skills" / "copy.md"
    _write(target_file, _frontmatter_doc(h))
    # Manifest is empty — perhaps file was copy-pasted from another harness.
    report = sweep_orphans(project_root, _empty_blueprint())
    assert target_file.exists(), "copy-pasted ours-stamped file must be preserved"
    kept_paths = [p for p, _ in report.kept]
    assert Path(".claude/skills/copy.md") in kept_paths
    log = _read_orphan_log(project_root)
    assert any(
        r["path"] == ".claude/skills/copy.md" and r["classification"] == "missing-in-manifest"
        for r in log
    )


def test_adaptive_telemetry_files_preserved(project_root: Path) -> None:
    """R4 critical: user telemetry under .claude/observability/adaptive/
    has no frontmatter AND no manifest entry → falls into 'theirs' branch → KEEP."""
    overrides = project_root / ".claude" / "observability" / "adaptive" / "overrides.jsonl"
    last_audit = project_root / ".claude" / "observability" / "adaptive" / "last-audit.txt"
    _write(overrides, '{"recommendation":"x","action":"reject"}\n')
    _write(last_audit, "2026-05-15T12:00:00Z\n")
    report = sweep_orphans(project_root, _empty_blueprint())
    assert overrides.exists(), "adaptive telemetry MUST survive orphan-sweep"
    assert last_audit.exists(), "adaptive telemetry MUST survive orphan-sweep"
    kept_paths = {p for p, _ in report.kept}
    assert Path(".claude/observability/adaptive/overrides.jsonl") in kept_paths
    assert Path(".claude/observability/adaptive/last-audit.txt") in kept_paths
    assert report.deleted == []


def test_expected_blueprint_files_not_touched(project_root: Path) -> None:
    """Files listed in blueprint.files are never considered orphans, regardless
    of whether their hash matches the manifest."""
    body = "hello\n"
    h = _hash_for(body)
    target_file = project_root / ".claude" / "commands" / "hm" / "active.md"
    _write(target_file, _frontmatter_doc(h))
    # synthesize.py stores .claude/-bound paths WITHOUT the .claude/ prefix
    # (it gets joined with target_dir by resolve_output_path). The fixture must
    # match production format so _normalize_expected_path's branch is exercised.
    bp = Blueprint(
        files=[
            FileEntry(
                path=Path("commands/hm/active.md"),
                template="dummy.j2",
                context={},
                frontmatter={},
            ),
        ],
    )
    report = sweep_orphans(project_root, bp)
    assert target_file.exists()
    assert report.deleted == []
    assert report.kept == []


def test_files_outside_sweep_roots_never_touched(project_root: Path) -> None:
    """Renderer never writes outside the five enumerated roots, so the sweep
    must not even look at src/, tests/, docs/ etc. — never delete user code."""
    src_file = project_root / "src" / "user_code.py"
    _write(src_file, "print('user owned')\n")
    report = sweep_orphans(project_root, _empty_blueprint())
    assert src_file.exists()
    kept_paths = [p for p, _ in report.kept]
    assert Path("src/user_code.py") not in kept_paths
    assert report.deleted == []


def test_no_frontmatter_file_in_manifest_deleted(project_root: Path) -> None:
    """A non-text orphan (e.g. JSON without frontmatter) whose current bytes
    sha256 matches a manifest entry → DELETE."""
    target_file = project_root / ".cursor" / "mcp.json"
    raw = '{"mcpServers": {}}\n'
    _write(target_file, raw)
    h = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    _append_manifest(project_root / ".claude", ".cursor/mcp.json", h)
    report = sweep_orphans(project_root, _empty_blueprint())
    assert not target_file.exists()
    assert Path(".cursor/mcp.json") in report.deleted


# ──────────────────────────────────────────────────────────────────────────
# RC1: provenance-stripped pure-text renders (.cursor/rules/*.mdc).
# These carry only the external consumer's frontmatter (description/globs/
# alwaysApply) with OUR provenance stripped (render._render_pure_text), so they
# land in the `fm is not None` non-harness-provenance branch of _classify_orphan.
# They must still be sweepable when byte-identical to a manifest entry under
# their OWN path — while R4 safety (never delete what we can't fingerprint as
# ours) is preserved by per-path scoping. (PLAN-cursor-mdc-orphan-sweep)
# ──────────────────────────────────────────────────────────────────────────


def _cursor_mdc(body_line: str = "rule body") -> str:
    """A .cursor/rules/*.mdc exactly as _render_pure_text emits it: Cursor-only
    frontmatter, NO generated_by / content_hash (provenance stripped)."""
    return (
        "---\n"
        "description: harness rules\n"
        "globs: []\n"
        "alwaysApply: true\n"
        "---\n\n"
        f"# Rules\n{body_line}\n"
    )


def _full_file_hash(content: str) -> str:
    """Full-file sha256 — what _render_pure_text records in the manifest, and
    what _classify_orphan recomputes via _sha256_bytes(raw)."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def test_cursor_mdc_ours_clean_deleted(project_root: Path) -> None:
    """RC1 (a): a provenance-stripped .mdc (Cursor frontmatter, no generated_by)
    whose full-file hash is recorded in the manifest under its own path, and which
    is no longer in the blueprint, must classify ours-clean → DELETE."""
    content = _cursor_mdc()
    target_file = project_root / ".cursor" / "rules" / "harness.mdc"
    _write(target_file, content)
    _append_manifest(
        project_root / ".claude", ".cursor/rules/harness.mdc", _full_file_hash(content)
    )
    report = sweep_orphans(project_root, _empty_blueprint())
    assert not target_file.exists(), "unmodified orphaned .mdc must be swept"
    assert Path(".cursor/rules/harness.mdc") in report.deleted


def test_cursor_mdc_no_manifest_entry_kept(project_root: Path) -> None:
    """RC1 (b) R4: a .mdc with Cursor frontmatter but NO manifest entry under its
    path (user-authored rule) → KEEP (theirs)."""
    content = _cursor_mdc("user wrote this")
    target_file = project_root / ".cursor" / "rules" / "user_rule.mdc"
    _write(target_file, content)
    report = sweep_orphans(project_root, _empty_blueprint())
    assert target_file.exists(), "user-authored .mdc must survive"
    assert Path(".cursor/rules/user_rule.mdc") in [p for p, _ in report.kept]
    log = _read_orphan_log(project_root)
    assert any(
        r["path"] == ".cursor/rules/user_rule.mdc" and r["classification"] == "theirs" for r in log
    )


def test_cursor_mdc_edited_hash_mismatch_kept(project_root: Path) -> None:
    """RC1 (c) R4: a harness .mdc the user EDITED — manifest has an entry for the
    path but with a different hash → current bytes miss → KEEP (theirs)."""
    target_file = project_root / ".cursor" / "rules" / "edited.mdc"
    _write(target_file, _cursor_mdc("USER EDITED"))
    _append_manifest(
        project_root / ".claude",
        ".cursor/rules/edited.mdc",
        _full_file_hash(_cursor_mdc("original")),
    )
    report = sweep_orphans(project_root, _empty_blueprint())
    assert target_file.exists(), "edited .mdc must be preserved"
    assert Path(".cursor/rules/edited.mdc") in [p for p, _ in report.kept]
    assert report.deleted == []


def test_cursor_mdc_hash_under_different_path_kept(project_root: Path) -> None:
    """RC1 (d) R4 path-scoping (load-bearing): the .mdc's byte-hash exists in the
    manifest ONLY under a DIFFERENT path key. The lookup is manifest[rel_key], so
    this file has no entry under its own path → KEEP. Locks that the hash check is
    per-path, not a global hash set — a global lookup would delete a user file that
    happens to be byte-identical to a harness file rendered at another path."""
    content = _cursor_mdc("identical bytes")
    target_file = project_root / ".cursor" / "rules" / "mine.mdc"
    _write(target_file, content)
    # the SAME hash is recorded, but under a DIFFERENT path
    _append_manifest(project_root / ".claude", ".cursor/rules/other.mdc", _full_file_hash(content))
    report = sweep_orphans(project_root, _empty_blueprint())
    assert target_file.exists(), "content-colliding file under a different path must survive"
    assert Path(".cursor/rules/mine.mdc") in [p for p, _ in report.kept]
    assert report.deleted == []


def test_cursor_mdc_trailing_newline_perturbation_kept(project_root: Path) -> None:
    """RC1 (e) byte-exact invariant: a trailing-newline perturbation changes the
    full-file hash, so a file whose body matches but whose bytes differ misses the
    manifest → KEEP. Documents that the sweep is byte-exact (not body-normalized)
    and that sweep safety depends on _render_pure_text writing normalized bytes
    verbatim."""
    content = _cursor_mdc()
    target_file = project_root / ".cursor" / "rules" / "perturbed.mdc"
    _write(target_file, content + "\n")  # extra trailing newline on disk
    _append_manifest(
        project_root / ".claude", ".cursor/rules/perturbed.mdc", _full_file_hash(content)
    )
    report = sweep_orphans(project_root, _empty_blueprint())
    assert target_file.exists(), "byte-perturbed file must not match a normalized manifest hash"
    assert Path(".cursor/rules/perturbed.mdc") in [p for p, _ in report.kept]
