"""Guard: agent-launch surfaces render the Claude ALIAS, never a concrete ID.

PLAN-agent-model-version-agnostic Phase 3. Claude Code now respects the agent
`model:` frontmatter (#43869 fixed), so a pinned concrete ID (e.g. the stale
Cursor `claude-4-7-opus`) fails to launch in a newer-model session. The
templates must render `opus`/`sonnet`/`haiku`, which Claude Code resolves to the
current tier model.

ADR-004 boundary: this guard scans ONLY agent-launch surfaces (rendered
`.claude/agents/*.md` + `default_model`). Anthropic-API surfaces (Python SDK
constants, aider/Continue foreign configs) require concrete IDs and are checked
*inversely* in test_foreign_config_renders_concrete_model.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from harness_maker.interview import interview
from harness_maker.models import HarnessConfig, Preset, ProjectProfile, Target
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize

_ALIASES = {"opus", "sonnet", "haiku"}
_CONCRETE_RE = re.compile(r"claude-")


@pytest.fixture(autouse=True)
def _isolate_home(
    tmp_path_factory: pytest.TempPathFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_home = tmp_path_factory.mktemp("hm-home")
    monkeypatch.setattr(Path, "home", lambda: fake_home)


def _render_agent_files(tmp_path: Path, preset: Preset) -> list[Path]:
    """Render a full harness with cursor in targets (so cursor_model — the
    concrete CURSOR_MODEL_IDS value — is populated, which is exactly the
    precedence the bug exploited) and return the rendered agent files.
    """
    p = ProjectProfile(stack=["python"], scale="small", lifecycle="dormant")
    a = interview(p, autoloop_mode=True).model_copy(
        update={"preset": preset, "targets": [Target.CLAUDE_CODE, Target.CURSOR]}
    )
    bp = synthesize(p, a)
    render(bp, tmp_path, dry_run=False, freeze_time=DEFAULT_FREEZE_TIME)
    return sorted((tmp_path / "agents").glob("*.md"))


def _model_line(text: str) -> str:
    m = re.search(r"^model:\s*(\S+)\s*$", text, re.MULTILINE)
    assert m is not None, "rendered agent has no `model:` frontmatter line"
    return m.group(1)


@pytest.mark.parametrize("preset", [Preset.PRODUCTION, Preset.SIDE])
def test_agent_frontmatter_renders_alias_not_concrete(tmp_path: Path, preset: Preset) -> None:
    agent_files = _render_agent_files(tmp_path, preset)
    assert agent_files, "no agent files rendered"
    for f in agent_files:
        model = _model_line(f.read_text(encoding="utf-8"))
        assert model in _ALIASES, (
            f"{f.name} ({preset.value}): model={model!r} is not an alias {_ALIASES} "
            "— a concrete/pinned ID leaked into a Claude-launch surface"
        )
        assert not _CONCRETE_RE.match(model), f"{f.name}: concrete ID {model!r} leaked"


def test_default_model_floor_is_alias() -> None:
    """Floor fallback is version-agnostic (ADR-002)."""
    assert HarnessConfig().default_model == "opus"


@pytest.mark.parametrize("ftype", ["aider", "continue"])
def test_foreign_config_renders_concrete_model(ftype: str) -> None:
    """ADR-006: aider/Continue hit the Anthropic API and require a CONCRETE id.

    With the floor now an alias (`opus`), the foreign-config render boundary
    must resolve it to a concrete Anthropic model id — `opus` would be an
    unusable model string for those external tools.
    """
    from harness_maker.foreign_config import (
        AxisMapping,
        ForeignConfig,
        _build_render_context,
    )
    from harness_maker.models import Confidence

    fc = ForeignConfig(path=".aider.conf.yml", type=ftype, size=10, confidence=Confidence.HIGH)
    cfg = HarnessConfig(default_model="opus")
    ctx = _build_render_context(fc, cfg, AxisMapping())
    rendered_model = ctx["default_model"]
    assert rendered_model not in _ALIASES, (
        f"{ftype}: foreign config received bare alias {rendered_model!r} — "
        "Anthropic API needs a concrete id"
    )
    assert _CONCRETE_RE.match(rendered_model), (
        f"{ftype}: expected a concrete claude-* id, got {rendered_model!r}"
    )
