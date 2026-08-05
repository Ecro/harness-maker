"""End-to-end regression: rendered harness.yaml is loadable by Second Brain.

PLAN-second-brain-write-failure Phase 4 (ADR-005). The defect class this test
guards is **fixture-vs-production drift** — unit tests built harness.yaml via
``yaml.safe_dump(...)`` without the renderer's provenance frontmatter, so the
production crash in ``second_brain._load_config`` was not caught by unit
tests. This test invokes ``harness_maker.render.render`` live (no snapshot
pinning) so any future change that breaks the renderer→loader contract fails
here, regardless of where in the templates it lands.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from harness_maker.interview import _build_answers
from harness_maker.models import (
    DevMode,
    Preset,
    SecondBrainConfig,
    SecondBrainFolder,
    Target,
)
from harness_maker.profile import profile
from harness_maker.render import render
from harness_maker.second_brain import (
    SecondBrainError,
    _load_config,
    promote_note,
    search_notes,
    write_note,
)
from harness_maker.synthesize import synthesize


def _baseline_answers(vault_path: Path, project_id: str = "harness-maker"):  # noqa: ANN202
    """Minimal answers with Second Brain enabled + one writable folder."""
    return _build_answers(
        locale="en",
        targets=[Target.CLAUDE_CODE],
        preset=Preset.SIDE,
        dev_mode=DevMode.TASK_DRIVEN,
        second_brain=SecondBrainConfig(
            enabled=True,
            project_id=project_id,
            vault_path=str(vault_path),
            folders=[
                SecondBrainFolder(
                    path=f"99_HM/{project_id}",
                    read=True,
                    write=True,
                )
            ],
        ),
    )


def _render_harness(target_root: Path, answers) -> Path:  # noqa: ANN001
    """Run profile → synthesize → render against ``target_root/.claude``; return .claude dir."""
    project_profile = profile(target_root)
    blueprint = synthesize(project_profile, answers)
    dotclaude = target_root / ".claude"
    dotclaude.mkdir(parents=True, exist_ok=True)
    render(blueprint, dotclaude)
    return dotclaude


def test_rendered_harness_yaml_loads_via_second_brain(tmp_path: Path) -> None:
    """End-to-end: render harness.yaml live → _load_config succeeds.

    This is the core regression guard for the original bug (yaml.safe_load
    crashing on provenance-frontmatter-wrapped harness.yaml).
    """
    project_root = tmp_path / "project"
    project_root.mkdir()
    vault = tmp_path / "obsidian-vault"
    (vault / ".obsidian").mkdir(parents=True)  # mark as real Obsidian vault

    answers = _baseline_answers(vault)
    dotclaude = _render_harness(project_root, answers)

    yaml_path = dotclaude / "harness.yaml"
    assert yaml_path.is_file(), "render must emit harness.yaml"

    # Production frontmatter shape is required for the regression to bite.
    head_lines = yaml_path.read_text(encoding="utf-8").splitlines()[:3]
    assert head_lines[0] == "---", "rendered harness.yaml must start with ---"
    assert "generated_by" in "\n".join(head_lines), (
        "rendered harness.yaml must carry provenance frontmatter "
        "(this is what made the original yaml.safe_load crash)"
    )

    cfg = _load_config(project_root)
    assert cfg.enabled is True
    assert cfg.vault_path == str(vault)
    assert cfg.project_id == "harness-maker"
    assert len(cfg.folders) == 1
    assert cfg.folders[0].path == "99_HM/harness-maker"


def test_rendered_harness_yaml_supports_write_roundtrip(tmp_path: Path) -> None:
    """Full pipeline: render → load → write_note → file lands inside vault folder."""
    project_root = tmp_path / "project"
    project_root.mkdir()
    vault = tmp_path / "obsidian-vault"
    (vault / ".obsidian").mkdir(parents=True)

    answers = _baseline_answers(vault)
    _render_harness(project_root, answers)

    frontmatter = {
        "type": "decision",
        "created": "2026-05-17",
        "updated": "2026-05-17",
        "tags": ["hm/second-brain", "hm/type/decision"],
        "links": ["[[PLAN second-brain-write-failure]]"],
        "project_id": "harness-maker",
        "status": "accepted",
    }
    result = write_note(
        project_root,
        "99_HM/harness-maker/test-note.md",
        frontmatter,
        "# Test\n\nNote body.\n",
    )

    assert result.path.is_file()
    assert (vault / "99_HM" / "harness-maker" / "test-note.md").is_file()


def test_render_loader_drift_is_detected(tmp_path: Path) -> None:
    """If a renderer change ever drops provenance frontmatter, this test fails.

    Mirrors the regression class — confirms the test is a real drift signal,
    not a tautology. We render normally, then strip the frontmatter manually
    and re-write the file; ``_load_config`` must still succeed (the loader is
    frontmatter-tolerant). What it must NOT do is start crashing because the
    file shape changed. If you ever rewrite the renderer to drop frontmatter
    AND the loader still works, this test stays green — that is desirable.
    If you rewrite the loader to require frontmatter AND the renderer stops
    emitting it, the first test in this file fails immediately.
    """
    project_root = tmp_path / "project"
    project_root.mkdir()
    vault = tmp_path / "obsidian-vault"
    (vault / ".obsidian").mkdir(parents=True)

    answers = _baseline_answers(vault)
    _render_harness(project_root, answers)
    yaml_path = project_root / ".claude" / "harness.yaml"

    # Strip the frontmatter manually — simulate a bare harness.yaml.
    raw = yaml_path.read_text(encoding="utf-8")
    if raw.startswith("---\n"):
        end = raw.find("\n---\n", 4)
        if end != -1:
            yaml_path.write_text(raw[end + 5 :], encoding="utf-8")

    cfg = _load_config(project_root)
    assert cfg.enabled is True
    assert len(cfg.folders) == 1


def test_rendered_yaml_with_empty_folders_degrades_gracefully(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Render with empty folders → load returns degraded cfg + warns (ADR-008)."""
    import logging

    project_root = tmp_path / "project"
    project_root.mkdir()
    vault = tmp_path / "obsidian-vault"
    (vault / ".obsidian").mkdir(parents=True)

    answers = _baseline_answers(vault)
    # Wipe folders to simulate the existing-user upgrade gap.
    answers.second_brain = SecondBrainConfig(
        enabled=True,
        project_id="harness-maker",
        vault_path=str(vault),
        folders=[],
    )
    _render_harness(project_root, answers)

    with caplog.at_level(logging.WARNING, logger="harness_maker.second_brain"):
        cfg = _load_config(project_root)

    assert cfg.enabled is True
    assert cfg.folders == []
    assert any(
        "second_brain.folders is empty" in rec.message or "/hm:configure" in rec.message
        for rec in caplog.records
    )

    with pytest.raises(SecondBrainError, match="/hm:configure"):
        write_note(
            project_root,
            "anywhere/n.md",
            {
                "type": "decision",
                "created": "2026-05-17",
                "updated": "2026-05-17",
                "tags": ["hm/second-brain", "hm/type/decision"],
                "links": [],
            },
            "Body",
        )


def test_rendered_yaml_rejects_typoed_vault_path(tmp_path: Path) -> None:
    """vault_path pointing into a non-Obsidian parent → SecondBrainError (ADR-002)."""
    project_root = tmp_path / "project"
    project_root.mkdir()
    typo_root = tmp_path / "not-an-obsidian-vault"
    typo_root.mkdir()  # exists, but no .obsidian/
    vault_typo = typo_root / "second-brain"  # missing

    answers = _baseline_answers(vault_typo)
    _render_harness(project_root, answers)

    with pytest.raises(SecondBrainError, match="not an Obsidian vault"):
        _load_config(project_root)


# ---------------------------------------------------------------------------
# PLAN-second-brain-promotion — wrapup promotion Step regression guards
# ---------------------------------------------------------------------------


def _wrapup_procedure_files(dotclaude: Path) -> list[Path]:
    """Rendered files carrying the wrapup PROCEDURE body.

    Discovered by content (the stable "Memory append" step header) rather than
    a fixed path, so the guard covers the atomic stage file AND any fused
    workflow command embedding it (W3 — the body is NOT in the thin
    commands/hm/wrapup.md dispatcher).
    """
    return [p for p in dotclaude.rglob("*.md") if "Memory append" in p.read_text(encoding="utf-8")]


def test_wrapup_renders_promote_step(tmp_path: Path) -> None:
    """The rendered wrapup procedure MUST call `second_brain promote` + emit the receipt.

    Regression guard against silently relapsing to the old advisory-only
    preamble (the root-cause bug). Live-render + substring grep — NOT a
    snapshot/hash pin — so it stays valid inside a worktree.
    """
    project_root = tmp_path / "project"
    project_root.mkdir()
    vault = tmp_path / "obsidian-vault"
    (vault / ".obsidian").mkdir(parents=True)

    answers = _baseline_answers(vault)
    dotclaude = _render_harness(project_root, answers)

    procedure_files = _wrapup_procedure_files(dotclaude)
    assert procedure_files, "no rendered file carries the wrapup procedure body"

    for path in procedure_files:
        text = path.read_text(encoding="utf-8")
        assert "second_brain promote" in text, (
            f"{path} lost the promote Step — relapsed to advisory-only?"
        )
        assert "promotion evaluated:" in text, f"{path} lost the promotion receipt line (ADR-006)"
        assert "wrapup also writes" not in text, f"{path} still carries the old advisory preamble"
        # `--root` is a TOP-LEVEL flag — it must precede the subcommand. A
        # rendered `promote --root` is an invalid invocation (argparse rejects
        # it); dogfooding 0.27.0's first real wrapup caught exactly this.
        assert "promote --root" not in text, (
            f"{path} renders an invalid `promote --root` (--root must precede the subcommand)"
        )


def test_wrapup_promotion_drops_session_source(tmp_path: Path) -> None:
    """session-tier-slim ADR-001: wrapup no longer lists session `[decision:...]`
    as a Second-Brain promotion source or in the receipt N-count."""
    project_root = tmp_path / "project"
    project_root.mkdir()
    vault = tmp_path / "obsidian-vault"
    (vault / ".obsidian").mkdir(parents=True)

    dotclaude = _render_harness(project_root, _baseline_answers(vault))
    procedure_files = _wrapup_procedure_files(dotclaude)
    assert procedure_files, "no rendered file carries the wrapup procedure body"

    for path in procedure_files:
        text = path.read_text(encoding="utf-8")
        assert "second_brain promote" in text  # 5.6 promotion still present
        assert "[decision:...]" not in text, (
            f"{path} still references the removed session decision journal (ADR-001)"
        )


def test_render_promote_search_roundtrip(tmp_path: Path) -> None:
    """Full pipeline: render harness → promote_note → search finds the note."""
    project_root = tmp_path / "project"
    project_root.mkdir()
    vault = tmp_path / "obsidian-vault"
    (vault / ".obsidian").mkdir(parents=True)

    answers = _baseline_answers(vault)
    _render_harness(project_root, answers)

    result = promote_note(
        project_root,
        note_type="decision",
        source_slug="promotion-pipeline",
        title="Promotion pipeline",
        body="Local memory promotes to Obsidian at wrapup.\n",
    )
    assert result.path.is_file()
    assert (vault / "99_HM" / "harness-maker" / "decision-promotion-pipeline.md").is_file()

    hits = search_notes(project_root, "promotion", note_type="decision")
    assert any("decision-promotion-pipeline" in h.relpath for h in hits)


# Cleanup helper for tests that may leave a .claude tree in tmp_path —
# pytest's tmp_path cleanup handles this automatically but be explicit when
# debugging by running with --basetemp=/tmp/xxx.
def _cleanup(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path, ignore_errors=True)
