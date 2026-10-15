"""SPEC-hm-autopilot-spec-advance — Step 5 must not tell an auto_full run to stop.

A 2026-10-14 bench saw 6 of 15 headless `/hm:spec` runs at `auto_full` stop after the boundary
returned `proceed: true`, quoting Step 5's "autopilot stops at this stage" back as the reason.
The boundary advances a pending spec gate at `auto_full` without an approval; the land hold in
`/hm:wrapup` is what covers the unapproved SPEC.
"""

from __future__ import annotations

from pathlib import Path

from harness_maker import models
from harness_maker.interview import _build_answers
from harness_maker.models import Preset, ProjectProfile, Target
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize


def _step5(root: Path, level: str) -> dict[str, str]:
    answers = _build_answers(
        locale="en",
        targets=[Target.CLAUDE_CODE, Target.CODEX],
        preset=Preset.PRODUCTION,
        autonomy=models.AutonomyConfig(level=level),  # type: ignore[arg-type]
    )
    render(
        synthesize(ProjectProfile(), answers, preset=Preset.PRODUCTION),
        root / ".claude",
        freeze_time=DEFAULT_FREEZE_TIME,
    )
    paths = {
        "claude": root / ".claude" / "commands" / "hm" / "spec.md",
        "codex": root / ".agents" / "skills" / "hm-spec" / "SKILL.md",
    }
    out: dict[str, str] = {}
    for target, path in paths.items():
        text = path.read_text(encoding="utf-8")
        start = text.index("### Step 5 — Status update")
        end = text.index("**Stage terminal**", start)
        # Codex has no slash command; its skills name the next stage as `$hm-<stage>`.
        out[target] = " ".join(text[start:end].split()).replace("$hm-", "/hm:")
    return out


def test_auto_full_step5_says_the_stage_advances(tmp_path: Path) -> None:
    step5 = _step5(tmp_path, "auto_full")
    for target, text in step5.items():
        assert "autopilot stops at this stage" not in text, target
        assert "does not end this stage by itself" in text, target
        assert "`proceed: true` advances WITHOUT an approval" in text, target
        assert "`/hm:wrapup` asks again before landing" in text, target
    # 2026-10-15, SPEC-hm-light-lane-s3a AC-014: a light SPEC with an empty irreversible list is
    # now stamped exempt first, so the unstamped sentence opens "On `full`, leave".
    claude_tail, codex_tail = (step5[t].split("On `full`, leave")[1] for t in ("claude", "codex"))
    assert claude_tail == codex_tail


def test_step5_is_the_same_at_every_level(tmp_path: Path) -> None:
    # A gated harness renders no auto-advance check, and the autopilot-gate contract
    # (test_autopilot_gate_render AC-005) allows gated and armed renders to differ only inside
    # the marked advance and picker blocks. So the sentence holds at every level unchanged.
    armed = _step5(tmp_path / "auto_full", "auto_full")
    for level in ("gated", "ask", "auto_safe"):
        assert _step5(tmp_path / level, level) == armed, level
