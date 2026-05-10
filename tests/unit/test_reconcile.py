"""Tests for the Reconciler (Task 3.3)."""

from __future__ import annotations

from pathlib import Path

from harness_maker.models import Blueprint, FileEntry, ReconcileDecision
from harness_maker.reconcile import backup, compute_body_hash, parse_frontmatter, reconcile


def _bp(rel_paths: list[str]) -> Blueprint:
    return Blueprint(
        files=[FileEntry(path=Path(rp), template="x.j2") for rp in rel_paths],
    )


def test_reconcile_new_only_returns_both(tmp_path: Path) -> None:
    bp = _bp(["a.md"])
    conflicts = reconcile(tmp_path, bp)
    assert len(conflicts) == 1
    assert conflicts[0].decision == ReconcileDecision.BOTH
    assert conflicts[0].reason == "new-only"


def test_reconcile_no_frontmatter_returns_keep(tmp_path: Path) -> None:
    target = tmp_path / "a.md"
    target.write_text("plain content with no frontmatter\n", encoding="utf-8")
    bp = _bp(["a.md"])
    conflicts = reconcile(tmp_path, bp)
    assert conflicts[0].decision == ReconcileDecision.KEEP
    assert conflicts[0].reason == "no-frontmatter"


def test_reconcile_hash_match_returns_replace(tmp_path: Path) -> None:
    target = tmp_path / "a.md"
    body = "# hello\n"
    body_bytes = body.encode("utf-8")
    h = compute_body_hash(body_bytes)
    fm = "---\ncontent_hash: " + h + "\n---\n"
    target.write_text(fm + body, encoding="utf-8")
    bp = _bp(["a.md"])
    conflicts = reconcile(tmp_path, bp)
    assert conflicts[0].decision == ReconcileDecision.REPLACE
    assert conflicts[0].reason == "hash-match-ours"


def test_reconcile_hash_mismatch_no_markers_returns_keep(tmp_path: Path) -> None:
    """User edited a marker-less file → KEEP (legacy fallback)."""
    target = tmp_path / "a.md"
    body = "# user has edited this\n"
    fm = (
        "---\ncontent_hash: 0000000000000000000000000000000000000000000000000000000000000000\n---\n"
    )
    target.write_text(fm + body, encoding="utf-8")
    # Use a real marker-less template so reconcile can read it; the hash
    # mismatch is what we exercise here, not template-unreadable.
    bp = Blueprint(files=[FileEntry(path=Path("a.md"), template="stages/research.md.j2")])
    conflicts = reconcile(tmp_path, bp)
    assert conflicts[0].decision == ReconcileDecision.KEEP
    assert conflicts[0].reason == "hash-mismatch-user-modified"


def test_reconcile_hash_mismatch_template_unreadable_returns_keep(tmp_path: Path) -> None:
    """Missing template → graceful KEEP with diagnostic reason."""
    target = tmp_path / "a.md"
    body = "# edited\n"
    fm = (
        "---\ncontent_hash: 0000000000000000000000000000000000000000000000000000000000000000\n---\n"
    )
    target.write_text(fm + body, encoding="utf-8")
    bp = _bp(["a.md"])  # template="x.j2" doesn't exist
    conflicts = reconcile(tmp_path, bp)
    assert conflicts[0].decision == ReconcileDecision.KEEP
    assert conflicts[0].reason == "hash-mismatch-template-unreadable"


def test_reconcile_hash_mismatch_both_have_markers_returns_merge_block(tmp_path: Path) -> None:
    """User edited a marker-bearing file whose template still has markers
    → MERGE_BLOCK so user blocks survive the upgrade.
    """
    target = tmp_path / "review.md"
    # OLD body has a user block — simulates a previously-rendered review.md.
    body = "# Stage: review\n<!-- @hm:user:notes -->\nmy custom step\n<!-- @hm:/user:notes -->\n"
    fm = (
        "---\ncontent_hash: 0000000000000000000000000000000000000000000000000000000000000000\n---\n"
    )
    target.write_text(fm + body, encoding="utf-8")
    bp = Blueprint(files=[FileEntry(path=Path("review.md"), template="stages/review.md.j2")])
    conflicts = reconcile(tmp_path, bp)
    assert conflicts[0].decision == ReconcileDecision.MERGE_BLOCK
    assert conflicts[0].reason == "hash-mismatch-mergeable"


def test_reconcile_malformed_markers_falls_back_to_keep(tmp_path: Path) -> None:
    """User broke marker syntax (e.g., deleted the close tag) → KEEP not
    MERGE_BLOCK. Reason: silent loss of user edits is unacceptable; surface
    the diagnostic so the user can fix their markup.
    """
    target = tmp_path / "review.md"
    body = "# Stage: review\n<!-- @hm:user:notes -->\nuser content but close tag is missing\n"
    fm = (
        "---\ncontent_hash: 0000000000000000000000000000000000000000000000000000000000000000\n---\n"
    )
    target.write_text(fm + body, encoding="utf-8")
    bp = Blueprint(files=[FileEntry(path=Path("review.md"), template="stages/review.md.j2")])
    conflicts = reconcile(tmp_path, bp)
    assert conflicts[0].decision == ReconcileDecision.KEEP
    assert conflicts[0].reason == "hash-mismatch-malformed-markers"


def test_parse_frontmatter_no_marker(tmp_path: Path) -> None:
    p = tmp_path / "x.md"
    p.write_text("plain text\n")
    fm, body = parse_frontmatter(p)
    assert fm is None
    assert body == b"plain text\n"


def test_parse_frontmatter_valid(tmp_path: Path) -> None:
    p = tmp_path / "x.md"
    p.write_text("---\nfoo: bar\n---\nbody\n")
    fm, body = parse_frontmatter(p)
    assert fm == {"foo": "bar"}
    assert body == b"body\n"


def test_backup_creates_dir(tmp_path: Path) -> None:
    """Phase 2.4 backup layout: backup mirrors project root, holding
    ``.claude/`` + ``.cursor/`` subtrees. Pre-2.4 callers did `bdir / 'f.txt'`;
    new layout is `bdir / '.claude' / 'f.txt'`.
    """
    src = tmp_path / ".claude"
    src.mkdir()
    (src / "f.txt").write_text("hi\n")
    bdir = backup(src)
    assert bdir.exists()
    assert (bdir / ".claude" / "f.txt").read_text() == "hi\n"
    assert bdir.name.startswith(".backup-")


def test_backup_includes_cursor_directory(tmp_path: Path) -> None:
    """Cursor target 자산 (`.cursor/`) 도 backup 안에 포함되어 restore 가능."""
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    (claude_dir / "f.txt").write_text("claude\n")
    cursor_dir = tmp_path / ".cursor"
    (cursor_dir / "rules").mkdir(parents=True)
    (cursor_dir / "rules" / "harness.mdc").write_text("---\nalwaysApply: true\n---\n# x\n")

    bdir = backup(claude_dir)

    assert (bdir / ".claude" / "f.txt").read_text() == "claude\n"
    assert (bdir / ".cursor" / "rules" / "harness.mdc").read_text().startswith("---\n")


def test_backup_missing_dir_returns_path(tmp_path: Path) -> None:
    src = tmp_path / "nonexistent"
    bdir = backup(src)
    # backup_dir is computed but not created when src is missing
    assert bdir.name.startswith(".backup-")


# ──────────────────────────────────────────────────────────────────────────────
# Cursor target reconcile — Phase 2.4
# ──────────────────────────────────────────────────────────────────────────────


def test_reconcile_cursor_first_render_returns_both(tmp_path: Path) -> None:
    """첫 render — existing 없음 → BOTH (render + symlink). cursor 자산도 동일."""
    from harness_maker.interview import interview
    from harness_maker.models import ProjectProfile, Target
    from harness_maker.synthesize import synthesize

    p = ProjectProfile(stack=["python"], scale="small", lifecycle="experiment")
    a = interview(p, autoloop_mode=True).model_copy(update={"targets": [Target.CURSOR]})
    bp = synthesize(p, a)

    project_root = tmp_path
    target_dir = project_root / ".claude"
    target_dir.mkdir()

    conflicts = reconcile(target_dir, bp)
    cursor_decisions = {
        str(c.path): c.decision for c in conflicts if str(c.path).startswith(".cursor/")
    }
    assert cursor_decisions == {
        ".cursor/rules/harness.mdc": ReconcileDecision.BOTH,
        ".cursor/hooks.json": ReconcileDecision.BOTH,
        ".cursor/mcp.json": ReconcileDecision.BOTH,
    }


def test_reconcile_cursor_mdc_keeps_after_render(tmp_path: Path) -> None:
    """첫 render 후 두 번째 reconcile: existing mdc 가 Cursor frontmatter
    (description/globs/alwaysApply) 만 있고 우리 generated_by/content_hash
    없음 (Cursor strict-reject 회피) → KEEP.

    Trade-off: 사용자 수정 자동 보존 ✅, 우리 template 업데이트는 사용자가
    수동 delete + re-render 필요. sidecar 메타 도입 시 변경 가능.
    """
    from harness_maker.interview import interview
    from harness_maker.models import ProjectProfile, Target
    from harness_maker.render import DEFAULT_FREEZE_TIME, render
    from harness_maker.synthesize import synthesize

    p = ProjectProfile(stack=["python"], scale="small", lifecycle="experiment")
    a = interview(p, autoloop_mode=True).model_copy(update={"targets": [Target.CURSOR]})

    project_root = tmp_path
    target_dir = project_root / ".claude"
    target_dir.mkdir()

    # 첫 render
    bp = synthesize(p, a)
    render(bp, target_dir, freeze_time=DEFAULT_FREEZE_TIME)

    # 두 번째 reconcile
    bp2 = synthesize(p, a)
    conflicts = reconcile(target_dir, bp2)
    mdc_conflicts = [c for c in conflicts if str(c.path) == ".cursor/rules/harness.mdc"]
    assert len(mdc_conflicts) == 1
    assert mdc_conflicts[0].decision == ReconcileDecision.KEEP
    # Cursor frontmatter (description/globs/alwaysApply) is present; absence
    # of generated_by routes through the new "frontmatter-no-hash-not-ours"
    # branch so user mdc edits are preserved.
    assert mdc_conflicts[0].reason == "frontmatter-no-hash-not-ours"


def test_reconcile_legacy_ours_no_hash_returns_replace(tmp_path: Path) -> None:
    """Legacy ours: pre-content_hash version (e.g. v0.4.7 memory templates)
    has generated_by but no content_hash → REPLACE so version bumps land.

    Real-world reproducer: ~/kairos memory/wiki.md stuck on v0.4.7 with
    'Side preset' header even after upgrading the harness to Production.
    """
    from harness_maker.models import Blueprint, FileEntry

    target = tmp_path / ".claude"
    target.mkdir()
    (target / "memory").mkdir()
    (target / "memory" / "wiki.md").write_text(
        "---\n"
        "generated_by: harness-maker\n"
        "harness_maker_version: 0.4.7\n"
        "source_template: memory/wiki.ko.md.j2\n"
        "---\n"
        "# Wiki — Side preset\n"
        "(아직 기록된 항목 없음)\n",
        encoding="utf-8",
    )
    bp = Blueprint(
        files=[
            FileEntry(
                path=Path("memory/wiki.md"),
                template="memory/wiki.ko.md.j2",
                context={},
                frontmatter={},
            ),
        ],
    )
    conflicts = reconcile(target, bp)
    assert len(conflicts) == 1
    assert conflicts[0].decision == ReconcileDecision.REPLACE
    assert conflicts[0].reason == "legacy-no-hash-but-ours"


def test_reconcile_legacy_ours_with_markers_returns_merge_block(tmp_path: Path) -> None:
    """Memory files have no content_hash by design (wrapup appends freely).
    When BOTH the template and existing body have @hm:user:* markers, use
    MERGE_BLOCK so accumulated wiki/failure entries survive re-renders.
    """
    from harness_maker.models import Blueprint, FileEntry

    target = tmp_path / ".claude"
    target.mkdir()
    (target / "memory").mkdir()
    (target / "memory" / "wiki.md").write_text(
        "---\n"
        "generated_by: harness-maker\n"
        "harness_maker_version: 0.7.2\n"
        "source_template: memory/wiki.ko.md.j2\n"
        "provenance: official\n"
        "---\n"
        "# Wiki Index — Production preset\n"
        "\n"
        "---\n"
        "\n"
        "<!-- @hm:user:entries -->\n"
        "## [wiki:gotcha] some-gotcha | 2026-05-09\n"
        "User-accumulated entry that must survive re-render.\n"
        "<!-- @hm:/user:entries -->\n",
        encoding="utf-8",
    )
    bp = Blueprint(
        files=[
            FileEntry(
                path=Path("memory/wiki.md"),
                template="memory/wiki.ko.md.j2",
                context={},
                frontmatter={},
            ),
        ],
    )
    conflicts = reconcile(target, bp)
    assert len(conflicts) == 1
    assert conflicts[0].decision == ReconcileDecision.MERGE_BLOCK
    assert conflicts[0].reason == "memory-block-merge"


def test_reconcile_cursor_hooks_json_always_replaces(tmp_path: Path) -> None:
    """`.cursor/hooks.json` is pure JSON (no frontmatter possible — Cursor's
    parser is strict). Always REPLACE so template updates land, mirroring
    `.claude/hooks/hooks.json` policy. User edits are overwritten by design.
    """
    from harness_maker.models import Blueprint, FileEntry

    target = tmp_path / ".claude"
    target.mkdir()
    cursor_dir = tmp_path / ".cursor"
    cursor_dir.mkdir()
    (cursor_dir / "hooks.json").write_text(
        '{"version": 1, "hooks": {"preToolUse": [{"command": "user-edit"}]}}\n',
        encoding="utf-8",
    )
    bp = Blueprint(
        files=[
            FileEntry(
                path=Path(".cursor/hooks.json"),
                template="cursor/hooks.json.j2",
                context={},
                frontmatter={},
            ),
        ],
    )
    conflicts = reconcile(target, bp)
    assert len(conflicts) == 1
    assert conflicts[0].decision == ReconcileDecision.REPLACE
    assert conflicts[0].reason == "pure-json-no-frontmatter"


def test_reconcile_user_frontmatter_no_hash_returns_keep(tmp_path: Path) -> None:
    """User-authored file with arbitrary frontmatter (no generated_by) →
    KEEP. Mirror of the .cursor/rules/*.mdc case but for an arbitrary
    user file: never silently overwrite something we didn't generate.
    """
    from harness_maker.models import Blueprint, FileEntry

    target = tmp_path / ".claude"
    target.mkdir()
    (target / "agents").mkdir()
    (target / "agents" / "user-agent.md").write_text(
        "---\nname: user-agent\nfoo: bar\n---\n# my agent\n",
        encoding="utf-8",
    )
    bp = Blueprint(
        files=[
            FileEntry(
                path=Path("agents/user-agent.md"),
                template="agents/code-reviewer.md.j2",  # any template
                context={},
                frontmatter={},
            ),
        ],
    )
    conflicts = reconcile(target, bp)
    assert len(conflicts) == 1
    assert conflicts[0].decision == ReconcileDecision.KEEP
    assert conflicts[0].reason == "frontmatter-no-hash-not-ours"


def test_reconcile_codex_toml_always_replaces(tmp_path: Path) -> None:
    """`.codex/*.toml` files have no YAML frontmatter (tomllib rejects preambles).
    Always REPLACE so template updates (model defaults, MCP fields) propagate.
    """
    from harness_maker.models import Blueprint, FileEntry

    target = tmp_path / ".claude"
    target.mkdir()
    codex_dir = tmp_path / ".codex"
    codex_dir.mkdir()
    (codex_dir / "config.toml").write_text(
        "[features]\ncodex_hooks = true\n",
        encoding="utf-8",
    )
    bp = Blueprint(
        files=[
            FileEntry(
                path=Path(".codex/config.toml"),
                template="codex/config.toml.j2",
                context={},
                frontmatter={},
            ),
        ],
    )
    conflicts = reconcile(target, bp)
    assert len(conflicts) == 1
    assert conflicts[0].decision == ReconcileDecision.REPLACE
    assert conflicts[0].reason == "pure-toml-no-frontmatter"


def test_backup_after_full_render_preserves_cursor_user_modifications(tmp_path: Path) -> None:
    """B13 — backup() 가 .cursor/ 의 사용자 수정도 보존."""
    from harness_maker.interview import interview
    from harness_maker.models import ProjectProfile, Target
    from harness_maker.render import DEFAULT_FREEZE_TIME, render
    from harness_maker.synthesize import synthesize

    p = ProjectProfile(stack=["python"], scale="small", lifecycle="experiment")
    a = interview(p, autoloop_mode=True).model_copy(update={"targets": [Target.CURSOR]})

    project_root = tmp_path
    target_dir = project_root / ".claude"
    target_dir.mkdir()

    bp = synthesize(p, a)
    render(bp, target_dir, freeze_time=DEFAULT_FREEZE_TIME)

    # 사용자 수정 시뮬레이션 (cursor mdc)
    mdc = project_root / ".cursor" / "rules" / "harness.mdc"
    mdc.write_text("# user override\n", encoding="utf-8")

    bdir = backup(target_dir)
    backup_mdc = bdir / ".cursor" / "rules" / "harness.mdc"
    assert backup_mdc.read_text(encoding="utf-8") == "# user override\n"
