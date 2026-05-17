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
    return (
        "---\n"
        f"generated_by: {generated_by}\n"
        f"content_hash: {content_hash}\n"
        "---\n"
        "hello\n"
    )


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
        r["path"] == ".claude/lib/user_script.sh" and r["classification"] == "theirs"
        for r in log
    )


def test_theirs_with_frontmatter_kept_with_warning(project_root: Path) -> None:
    """Frontmatter present but generated_by != harness-maker → KEEP + warn."""
    target_file = project_root / ".claude" / "agents" / "user_agent.md"
    body = (
        "---\n"
        "name: user_agent\n"
        "generated_by: hand-written\n"
        "---\n"
        "user content\n"
    )
    _write(target_file, body)
    report = sweep_orphans(project_root, _empty_blueprint())
    assert target_file.exists()
    kept_paths = [p for p, _ in report.kept]
    assert Path(".claude/agents/user_agent.md") in kept_paths
    log = _read_orphan_log(project_root)
    assert any(
        r["path"] == ".claude/agents/user_agent.md" and r["classification"] == "theirs"
        for r in log
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
        r["path"] == ".claude/skills/copy.md"
        and r["classification"] == "missing-in-manifest"
        for r in log
    )


def test_adaptive_telemetry_files_preserved(project_root: Path) -> None:
    """R4 critical: user telemetry under .claude/observability/adaptive/
    has no frontmatter AND no manifest entry → falls into 'theirs' branch → KEEP."""
    overrides = (
        project_root / ".claude" / "observability" / "adaptive" / "overrides.jsonl"
    )
    last_audit = (
        project_root / ".claude" / "observability" / "adaptive" / "last-audit.txt"
    )
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
