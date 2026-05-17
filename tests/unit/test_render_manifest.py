"""Tests for ``.hm-render-manifest.jsonl`` append behaviour (ADR-005, Phase 0).

The manifest is an append-only audit log consulted by reconcile's orphan-sweep.
Properties under test:
- Every render appends exactly one line per FileEntry.
- Re-renders of the same path append additional lines (no de-dup).
- Hash collisions across distinct paths preserve both records.
- Multi-pass rendering accumulates entries deterministically.
- Recorded ``path`` is **project-root-relative** so the orphan-sweep can
  query the manifest with its own ``rglob`` output unchanged.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from harness_maker import render as render_mod
from harness_maker.models import Blueprint, FileEntry
from harness_maker.render import (
    DEFAULT_FREEZE_TIME,
    RENDER_MANIFEST_NAME,
    render,
)


@pytest.fixture
def synthetic_templates(
    tmp_path_factory: pytest.TempPathFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> Path:
    """Point the renderer at a tiny synthetic template dir for fast, isolated tests.

    ``TEMPLATE_DIR`` is read by ``_make_env`` at call time, so monkeypatching
    the module attribute is sufficient — no global Jinja env to invalidate.
    """
    tdir: Path = tmp_path_factory.mktemp("templates")
    (tdir / "skills").mkdir()
    (tdir / "skills" / "alpha.md.j2").write_text(
        "# alpha skill\nbody-A\n",
        encoding="utf-8",
    )
    (tdir / "skills" / "beta.md.j2").write_text(
        "# beta skill\nbody-B\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(render_mod, "TEMPLATE_DIR", tdir)
    return tdir


@pytest.fixture
def target_dir(tmp_path: Path) -> Path:
    """``<project_root>/.claude`` — matches production CLI dispatch."""
    td: Path = tmp_path / ".claude"
    td.mkdir()
    return td


def _read_manifest(target_dir: Path) -> list[dict[str, str]]:
    manifest = target_dir / RENDER_MANIFEST_NAME
    assert manifest.is_file(), "manifest should be created on first render"
    out: list[dict[str, str]] = []
    for line in manifest.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        assert isinstance(rec, dict)
        out.append(rec)
    return out


def _is_iso8601(ts: str) -> bool:
    try:
        datetime.fromisoformat(ts)
    except ValueError:
        return False
    return True


def _bp_one(template: str, out_path: str) -> Blueprint:
    return Blueprint(
        files=[
            FileEntry(
                path=Path(out_path),
                template=template,
                context={},
                frontmatter={},
            ),
        ],
    )


def test_manifest_append_writes_one_line(
    target_dir: Path,
    synthetic_templates: Path,
) -> None:
    """Single render → exactly one manifest line with valid schema."""
    bp = _bp_one("skills/alpha.md.j2", "skills/alpha.md")
    render(bp, target_dir, freeze_time=DEFAULT_FREEZE_TIME)
    entries = _read_manifest(target_dir)
    assert len(entries) == 1
    rec = entries[0]
    assert rec["path"] == ".claude/skills/alpha.md"
    assert len(rec["content_hash"]) == 64
    assert all(c in "0123456789abcdef" for c in rec["content_hash"])
    assert _is_iso8601(rec["timestamp"])


def test_manifest_append_idempotent_across_runs(
    target_dir: Path,
    synthetic_templates: Path,
) -> None:
    """Re-render same blueprint → two lines (NOT collapsed). Timestamps non-decreasing."""
    bp = _bp_one("skills/alpha.md.j2", "skills/alpha.md")
    early = datetime.fromisoformat("2026-01-01T00:00:00+00:00")
    later = datetime.fromisoformat("2026-05-16T14:06:00+00:00")
    render(bp, target_dir, freeze_time=early)
    render(bp, target_dir, freeze_time=later)
    entries = _read_manifest(target_dir)
    assert len(entries) == 2
    assert entries[0]["path"] == entries[1]["path"] == ".claude/skills/alpha.md"
    assert entries[0]["content_hash"] == entries[1]["content_hash"]
    assert entries[0]["timestamp"] <= entries[1]["timestamp"]


def test_manifest_hash_collision_logged_separately(
    target_dir: Path,
    synthetic_templates: Path,
) -> None:
    """Two FileEntries that render to identical bytes (same template, no context)
    still produce two distinct manifest lines — manifest must not de-dup by hash."""
    bp = Blueprint(
        files=[
            FileEntry(
                path=Path("skills/alpha.md"),
                template="skills/alpha.md.j2",
                context={},
                frontmatter={},
            ),
            FileEntry(
                path=Path("skills/alpha_copy.md"),
                template="skills/alpha.md.j2",
                context={},
                frontmatter={},
            ),
        ],
    )
    render(bp, target_dir, freeze_time=DEFAULT_FREEZE_TIME)
    entries = _read_manifest(target_dir)
    assert len(entries) == 2
    paths = {e["path"] for e in entries}
    assert paths == {".claude/skills/alpha.md", ".claude/skills/alpha_copy.md"}
    hashes = {e["content_hash"] for e in entries}
    assert len(hashes) == 1, "identical body should yield identical hash"


def test_manifest_survives_multiple_render_passes(
    target_dir: Path,
    synthetic_templates: Path,
) -> None:
    """Three render passes accumulate three lines for the same path."""
    bp = _bp_one("skills/beta.md.j2", "skills/beta.md")
    for _ in range(3):
        render(bp, target_dir, freeze_time=DEFAULT_FREEZE_TIME)
    entries = _read_manifest(target_dir)
    assert len(entries) == 3
    assert {e["path"] for e in entries} == {".claude/skills/beta.md"}
    assert len({e["content_hash"] for e in entries}) == 1


def test_manifest_skipped_on_dry_run(
    target_dir: Path,
    synthetic_templates: Path,
) -> None:
    """dry_run=True must not produce a manifest; audit log mirrors on-disk state."""
    bp = _bp_one("skills/alpha.md.j2", "skills/alpha.md")
    render(bp, target_dir, dry_run=True, freeze_time=DEFAULT_FREEZE_TIME)
    manifest = target_dir / RENDER_MANIFEST_NAME
    assert not manifest.exists()
