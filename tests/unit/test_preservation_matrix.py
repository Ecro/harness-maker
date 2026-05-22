"""Phase 0 (PLAN-onboarding-backup-friction) preservation matrix tests.

Table-driven cells assert the documented preservation outcome per file class.
Cells corresponding to Phase 1+3 / Phase 2 gaps are RED in Phase 0 and flip
GREEN as those phases land:

- Hooks.json cells (M6a/b/c): RED in Phase 0 (current behavior is REPLACE, but
  desired post-Phase-1+3 decision string is 'merge_json'). NO xfail marker —
  they are intended to flip to GREEN in Phase 1+3, which ships next.
- TOML/sh cells (M7a/b, M8): xfail(strict=True, reason='Phase 2 not yet landed').
  Strict xfail means: if the cell starts passing before Phase 2 (i.e., a code
  change inadvertently fixed it early), the test fails — forcing intentional
  removal of the marker. Phase 2 removes these markers as part of its scope.

See docs/reference/preservation-matrix.md for the human-readable matrix.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from harness_maker.models import Blueprint, FileEntry, ReconcileDecision
from harness_maker.reconcile import compute_body_hash, reconcile


def _bp_one(rel_path: str, template: str = "x.j2") -> Blueprint:
    return Blueprint(files=[FileEntry(path=Path(rel_path), template=template)])


# ─── M1: Markdown without frontmatter ────────────────────────────────────────
def test_m1_markdown_no_frontmatter(tmp_path: Path) -> None:
    """User-authored markdown without our frontmatter survives brownfield render."""
    target = tmp_path / "commands" / "my-custom.md"
    target.parent.mkdir(parents=True)
    target.write_text("# my custom command\n\nfree-form prose\n", encoding="utf-8")
    bp = _bp_one("commands/my-custom.md")
    conflicts = reconcile(tmp_path, bp)
    assert conflicts[0].decision == ReconcileDecision.KEEP
    assert conflicts[0].reason == "no-frontmatter"


# ─── M3: Markdown — hash mismatch, no markers → KEEP ─────────────────────────
def test_m3_markdown_hash_mismatch_no_markers(tmp_path: Path) -> None:
    """User edited a shipped marker-less file → KEEP via legacy fallback."""
    target = tmp_path / "stages" / "research.md"
    target.parent.mkdir(parents=True)
    target.write_text(
        "---\ncontent_hash: " + "0" * 64 + "\n---\n# user has heavily edited this\n",
        encoding="utf-8",
    )
    bp = Blueprint(
        files=[FileEntry(path=Path("stages/research.md"), template="stages/research.md.j2")],
    )
    conflicts = reconcile(tmp_path, bp)
    assert conflicts[0].decision == ReconcileDecision.KEEP
    assert conflicts[0].reason == "hash-mismatch-user-modified"


# ─── M4: harness.yaml — always REPLACE; user keys preserved via render path ──
def test_m4_harness_yaml_replace_decision(tmp_path: Path) -> None:
    """harness.yaml is always REPLACE; user-key preservation happens at render time."""
    target = tmp_path / "harness.yaml"
    target.write_text("preset: Production\nuser_field: kept\n", encoding="utf-8")
    bp = _bp_one("harness.yaml")
    conflicts = reconcile(tmp_path, bp)
    assert conflicts[0].decision == ReconcileDecision.REPLACE
    assert conflicts[0].reason == "config-always-replace"


# ─── M5: settings.json — always REPLACE; permissions union at render time ────
def test_m5_settings_json_replace_decision(tmp_path: Path) -> None:
    target = tmp_path / "settings.json"
    target.write_text('{"permissions": {"allow": ["Bash(git:*)"]}}\n', encoding="utf-8")
    bp = _bp_one("settings.json")
    conflicts = reconcile(tmp_path, bp)
    assert conflicts[0].decision == ReconcileDecision.REPLACE
    assert conflicts[0].reason == "json-shallow-merge"


# ─── M6a: Claude hooks.json — RED in Phase 0, GREEN after Phase 1+3 ──────────
def test_m6a_claude_hooks_json_merges(tmp_path: Path) -> None:
    """Phase 1+3 contract: hooks/hooks.json must use MERGE_JSON, not REPLACE.

    Phase 0: RED (current behavior is REPLACE, asserted value is 'merge_json').
    Phase 1+3: GREEN once ReconcileDecision.MERGE_JSON exists and reconcile maps to it.
    """
    target = tmp_path / "hooks" / "hooks.json"
    target.parent.mkdir(parents=True)
    target.write_text('{"hooks": {"PostToolUse": []}}\n', encoding="utf-8")
    bp = _bp_one("hooks/hooks.json")
    conflicts = reconcile(tmp_path, bp)
    decision = conflicts[0].decision
    assert decision is not None
    assert decision.value == "merge_json", (
        f"Expected MERGE_JSON for hooks/hooks.json (Phase 1+3 contract), got {decision.value}"
    )


# ─── M6b: Cursor hooks.json — RED in Phase 0, GREEN after Phase 1+3 ──────────
def test_m6b_cursor_hooks_json_merges(tmp_path: Path) -> None:
    target = tmp_path.parent / ".cursor"
    target.mkdir(exist_ok=True)
    (target / "hooks.json").write_text('{"version": 1, "hooks": {}}\n', encoding="utf-8")
    # reconcile is called with existing_dir = .claude/; .cursor/ paths render
    # via resolve_output_path to sibling tree. The reconcile loop iterates
    # blueprint files and only checks files at existing_dir; .cursor/hooks.json
    # uses an explicit literal-match in reconcile.py:136 regardless of where
    # the file lives. Setup mirrors the resolve_output_path behavior.
    bp = _bp_one(".cursor/hooks.json")
    # Place the file where resolve_output_path expects it (sibling to .claude/).
    cursor_dir = tmp_path / ".cursor"
    cursor_dir.mkdir(exist_ok=True)
    (cursor_dir / "hooks.json").write_text(
        '{"version": 1, "hooks": {"preToolUse": []}}\n', encoding="utf-8"
    )
    conflicts = reconcile(tmp_path, bp)
    decision = conflicts[0].decision
    assert decision is not None
    assert decision.value == "merge_json", (
        f"Expected MERGE_JSON for .cursor/hooks.json (Phase 1+3 contract), got {decision.value}"
    )


# ─── M6c: Codex hooks.json — RED in Phase 0 (latent KEEP-fallback) ───────────
def test_m6c_codex_hooks_json_merges(tmp_path: Path) -> None:
    """Phase 1 fixes the literal-match bug; Phase 3 makes it MERGE_JSON.

    Phase 0: RED (current decision is KEEP via no-frontmatter fallback —
    the latent bug Phase 1 is documented to fix).
    Phase 1+3 atomic: GREEN with MERGE_JSON.
    """
    # .codex/ resolves to tmp_path.parent via resolve_output_path; place the
    # existing file there so reconcile's existence check passes the new-only
    # short-circuit and hits the literal-match branch.
    codex_dir = tmp_path.parent / ".codex"
    codex_dir.mkdir(exist_ok=True)
    (codex_dir / "hooks.json").write_text('{"hooks": {"PostToolUse": []}}\n', encoding="utf-8")
    bp = _bp_one(".codex/hooks.json")
    conflicts = reconcile(tmp_path, bp)
    decision = conflicts[0].decision
    assert decision is not None
    assert decision.value == "merge_json", (
        f"Expected MERGE_JSON for .codex/hooks.json (Phase 1+3 contract), got "
        f"{decision.value} — pre-PLAN this returns KEEP via the no-frontmatter "
        f"fallback rather than literal-match REPLACE."
    )


# ─── M7a: Codex config.toml with @hm:user:* markers → MERGE_BLOCK (Phase 2) ──
def test_m7a_codex_config_toml_marker_aware(tmp_path: Path) -> None:
    """Phase 2: TOML files with `# @hm:user:NAME` / `# @hm:/user:NAME` markers get MERGE_BLOCK.

    Currently `.toml` is always-REPLACE (reconcile.py:147-155). After Phase 2,
    the dispatch detects HASH_COMMENT markers via detect_marker_style and
    flips to MERGE_BLOCK when both shipped and existing have markers.
    """
    # .codex/ resolves to tmp_path.parent via resolve_output_path; place existing
    # file there so reconcile's existence check hits the literal-match branch.
    codex_dir = tmp_path.parent / ".codex"
    codex_dir.mkdir(exist_ok=True)
    body = (
        "# @hm:user:my-mcp\n"
        '[mcp_servers."my-server"]\n'
        'command = "uv run my-server"\n'
        "# @hm:/user:my-mcp\n"
    )
    (codex_dir / "config.toml").write_text(body, encoding="utf-8")
    bp = Blueprint(
        files=[FileEntry(path=Path(".codex/config.toml"), template="codex/config.toml.j2")],
    )
    conflicts = reconcile(tmp_path, bp)
    assert conflicts[0].decision == ReconcileDecision.MERGE_BLOCK
    assert conflicts[0].reason == "hashcomment-marker-merge"


# ─── M7b: Codex agent toml with TOML-level markers → MERGE_BLOCK (Phase 2) ───
def test_m7b_codex_agent_toml_marker_aware(tmp_path: Path) -> None:
    """Per ADR-007: markers operate at TOML statement level only.

    Inside `developer_instructions = '''…'''` multi-line strings markers are NOT
    recognized. To preserve a custom body the user wraps the entire assignment
    with TOML-level `# @hm:user:body-override` ... `# @hm:/user:body-override`.
    """
    agents_dir = tmp_path.parent / ".codex" / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    body = (
        "# @hm:user:body-override\n"
        'developer_instructions = """custom body content"""\n'
        "# @hm:/user:body-override\n"
    )
    (agents_dir / "code-reviewer.toml").write_text(body, encoding="utf-8")
    bp = Blueprint(
        files=[
            FileEntry(
                path=Path(".codex/agents/code-reviewer.toml"),
                template="codex/agent.toml.j2",
            ),
        ],
    )
    conflicts = reconcile(tmp_path, bp)
    assert conflicts[0].decision == ReconcileDecision.MERGE_BLOCK
    assert conflicts[0].reason == "hashcomment-marker-merge"


# ─── M8: .claude/lib/*.sh with `#` markers → MERGE_BLOCK (Phase 2) ───────────
# Phase 2 dispatch is wired (block_merge.detect_marker_style + reconcile sh
# branch). No `.sh` templates ship in the current blueprint — this cell is
# strict-xfail until a shipped `.sh` template carries `# @hm:user:*` markers.
# Documentation: docs/reference/preservation-matrix.md M8 row.
@pytest.mark.xfail(strict=True, reason="No .sh templates ship yet; dispatch is ready")
def test_m8_claude_lib_sh_marker_aware(tmp_path: Path) -> None:
    lib_dir = tmp_path / "lib"
    lib_dir.mkdir(exist_ok=True)
    body = '#!/bin/sh\n# @hm:user:custom-pre\necho "custom user logic"\n# @hm:/user:custom-pre\n'
    (lib_dir / "wrapper.sh").write_text(body, encoding="utf-8")
    bp = Blueprint(
        files=[FileEntry(path=Path("lib/wrapper.sh"), template="lib/wrapper.sh.j2")],
    )
    conflicts = reconcile(tmp_path, bp)
    assert conflicts[0].decision == ReconcileDecision.MERGE_BLOCK


# ─── M9: AGENTS.md (project root) → MERGE_BLOCK ──────────────────────────────
def test_m9_agents_md_block_merge(tmp_path: Path) -> None:
    """AGENTS.md uses MERGE_BLOCK (codex-agents-merge rule)."""
    (tmp_path.parent / "AGENTS.md").write_text("# agents\n", encoding="utf-8")
    bp = _bp_one("AGENTS.md")  # FileEntry path; reconcile resolves via Path equality
    # Actually reconcile.py:122-129 checks fe.path == Path("AGENTS.md"); ensure
    # an existing file is present at the resolve_output_path location for the
    # check. AGENTS.md lives at project root (sibling to .claude/).
    (tmp_path.parent / "AGENTS.md").write_text("# agents\nuser content\n", encoding="utf-8")
    conflicts = reconcile(tmp_path, bp)
    assert conflicts[0].decision == ReconcileDecision.MERGE_BLOCK
    assert conflicts[0].reason == "codex-agents-merge"


# ─── M2: Hash-match REPLACE (sanity: shipped file untouched by user) ─────────
def test_m2_hash_match_is_replace_safe(tmp_path: Path) -> None:
    """When user's file hash matches our manifest, REPLACE is safe (ours)."""
    target = tmp_path / "a.md"
    body = "# unchanged shipped content\n"
    body_bytes = body.encode("utf-8")
    h = compute_body_hash(body_bytes)
    target.write_text("---\ncontent_hash: " + h + "\n---\n" + body, encoding="utf-8")
    bp = _bp_one("a.md")
    conflicts = reconcile(tmp_path, bp)
    assert conflicts[0].decision == ReconcileDecision.REPLACE
    assert conflicts[0].reason == "hash-match-ours"
