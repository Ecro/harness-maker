"""P3 structural gate: P5-batch mode is extracted out of the loop body.

ADR-006 of PLAN-latency-worktree-step-preview: keep the per-iter loop body lean.
The niche P5-batch mode (~100 lines) moves to its own command
`commands/hm/loop-p5-batch.md.j2` (claude `/hm:loop-p5-batch`) with a parallel
Codex skill wrapper; `loop.md.j2` keeps only a dispatch pointer. Per-iter
behavioral rails (non-stopping discipline, self-pause prohibition) STAY in
`loop.md.j2` — they are NOT extracted.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TPL = REPO_ROOT / "src/harness_maker/templates"
LOOP = TPL / "commands/hm/loop.md.j2"
P5_CMD = TPL / "commands/hm/loop-p5-batch.md.j2"
P5_CODEX = TPL / "codex/loop_p5_batch_skill.md.j2"

# Distinctive line from the P5 procedure body — must MOVE to the extracted file.
PROCEDURE_MARKER = "Per-batch procedure (replaces the standard iter body)"


def test_p5_batch_command_template_exists_with_procedure() -> None:
    assert P5_CMD.is_file(), f"P5-batch must be extracted to {P5_CMD}"
    assert PROCEDURE_MARKER in P5_CMD.read_text(encoding="utf-8"), (
        "the extracted command must carry the full P5-batch procedure"
    )


def test_p5_batch_codex_skill_wrapper_exists() -> None:
    assert P5_CODEX.is_file(), (
        f"Codex P5-batch skill wrapper must exist at {P5_CODEX} (full-parity "
        "extraction — codex embeds loop_body, so it needs its own asset)"
    )


def test_loop_body_points_to_command_and_drops_procedure() -> None:
    loop = LOOP.read_text(encoding="utf-8")
    assert PROCEDURE_MARKER not in loop, (
        "P5 procedure must be MOVED out of loop.md.j2, not left/duplicated"
    )
    assert "loop-p5-batch" in loop, (
        "loop.md.j2 must keep a dispatch pointer to the extracted command"
    )


def test_per_iter_rails_stay_in_loop() -> None:
    """ADR-006: behavioral rails must NOT be extracted with P5-batch."""
    loop = LOOP.read_text(encoding="utf-8")
    assert "Non-stopping discipline" in loop, "non-stopping rail must stay in loop.md.j2"
    assert "Self-pause prohibition" in loop, "self-pause rail must stay in loop.md.j2"


def test_p5_command_codex_and_standalone_notes() -> None:
    """REVIEW round 2: the extracted command carries a codex-only bash-execution
    note (mitigates the pre-existing !uv-prefix-not-executable-on-codex limit)
    and a standalone worktree-precondition note (it's directly invokable)."""
    body = P5_CMD.read_text(encoding="utf-8")
    assert "{% if is_codex %}" in body, (
        "codex-only execution note must be present (codex can't run !-prefix blocks)"
    )
    assert "Worktree precondition" in body, (
        "standalone worktree-precondition note must be present (command is "
        "directly invokable, not only via /hm:loop)"
    )


def test_loop_detects_p5_batch_early() -> None:
    """REVIEW round 2: mode-detection must branch p5-batch BEFORE the standard
    feature/improve body, so the driver doesn't run steps 3-8 first."""
    loop = LOOP.read_text(encoding="utf-8")
    detect_idx = loop.index("### 2. Detect mode")
    branch_idx = loop.index("P5 BATCH MODE")
    feature_idx = loop.index("feature (default)")
    assert detect_idx < branch_idx < feature_idx, (
        "p5-batch must be detected early in '### 2. Detect mode', before the "
        "feature default falls through"
    )
