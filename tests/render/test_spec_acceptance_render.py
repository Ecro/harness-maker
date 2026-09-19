"""SPEC-ai-native-sdlc-vs-intent-world AC-007 — the rendered stages carry the acceptance flow.

REQUIRED_MARKERS is written from the AC-007 sentence (a weak text oracle, accepted in the
SPEC's Round 3). Every marker is checked on the Claude Code command AND the Codex stage skill,
because a flow that exists on one runtime only is the multi-target drift the SPEC rules out.
"""

from __future__ import annotations

import pytest

from harness_maker.models import InterviewAnswers, Preset, ProjectProfile, Target
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize

_CATEGORIES = (
    "schema/file format/storage layout",
    "public API/CLI contract",
    "data migration",
    "security/permission boundary",
    "new external dependency",
)

REQUIRED_MARKERS: tuple[tuple[str, str], ...] = (
    ("spec", "Approve this SPEC and end interview"),
    ("spec", "spec_machine approve --yaml"),
    ("spec", "--exempt"),
    ("spec", "schema_version: 3"),
    ("spec", "irreversible_decisions:"),
    ("spec", "🔒 Irreversible Decisions"),
    ("execute", "irreversible_decisions"),
    ("execute", "source: execute"),
    ("execute", "could two units working independently choose incompatibly"),
    ("execute", "is the call non-obvious"),
    ("execute", "is it a real trade-off"),
    ("execute", "cost, scale and compliance"),
    *(("execute", c) for c in _CATEGORIES),
    ("wrapup", "spec_machine approval-status"),
    ("wrapup", "No answer, no question tool, or loop mode is never an approval"),
    ("wrapup", "spec_machine approve --yaml"),
    ("loop", "[finalize] hold:"),
    ("loop", "HALT, not converge"),
)


@pytest.fixture(scope="module")
def rendered(tmp_path_factory: pytest.TempPathFactory) -> dict[str, dict[str, str]]:
    root = tmp_path_factory.mktemp("spec-acceptance")
    bp = synthesize(
        ProjectProfile(),
        InterviewAnswers(preset=Preset.PRODUCTION, targets=[Target.CLAUDE_CODE, Target.CODEX]),
    )
    render(bp, root / ".claude", freeze_time=DEFAULT_FREEZE_TIME)
    out: dict[str, dict[str, str]] = {"claude": {}, "codex": {}}
    for stage in ("spec", "execute", "wrapup", "loop"):
        out["claude"][stage] = (root / ".claude" / "commands" / "hm" / f"{stage}.md").read_text()
        out["codex"][stage] = (root / ".agents" / "skills" / f"hm-{stage}" / "SKILL.md").read_text()
    return out


@pytest.mark.parametrize("target", ["claude", "codex"])
def test_ac_007_stage_renders_carry_the_acceptance_flow(
    rendered: dict[str, dict[str, str]], target: str
) -> None:
    missing = [(s, m) for s, m in REQUIRED_MARKERS if m not in rendered[target][s]]
    assert not missing, f"{target} renders lack: {missing}"


@pytest.mark.parametrize("target", ["claude", "codex"])
def test_ac_007_wrapup_checks_approval_before_it_lands(
    rendered: dict[str, dict[str, str]], target: str
) -> None:
    text = rendered[target]["wrapup"]
    assert text.index("spec_machine approval-status") < text.index("hm wrapup_land")


@pytest.mark.parametrize("target", ["claude", "codex"])
def test_ac_007_spec_no_longer_ends_on_clear_alone(
    rendered: dict[str, dict[str, str]], target: str
) -> None:
    text = rendered[target]["spec"]
    assert "SPEC is sufficiently clear — end interview" not in text
    assert "No mandatory gate — spec may auto-advance" not in text
