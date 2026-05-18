"""Phase 4 — Codex per-agent reasoning_effort + .codex/config.toml profiles.

ADR-008: render model_reasoning_effort per-agent (the dominant cost lever on
reasoning models). Keep `model =` omission (RESEARCH-codex-plan-validator
precedent). Render [profiles.cheap] + [profiles.deep] in .codex/config.toml.
"""

from __future__ import annotations

from harness_maker.models import (
    AgentModelSpec,
    CodexAgentSpec,
    Preset,
)
from harness_maker.synthesize import _codex_agent_files


def _ctx_for(name: str, file_specs: list[tuple[str, str, dict]]) -> dict:
    for _tmpl, dst, ctx in file_specs:
        if dst == f".codex/agents/{name}.toml":
            return ctx
    raise AssertionError(f"codex agent {name!r} not in file_specs")


def test_production_preset_reviewer_gets_medium_effort() -> None:
    """Production preset → code-reviewer Codex context has reasoning_effort=medium."""
    specs = _codex_agent_files(preset=Preset.PRODUCTION)
    ctx = _ctx_for("code-reviewer", specs)
    assert ctx["codex_reasoning_effort"] == "medium"
    # Per RESEARCH-codex: model field stays None (Codex CLI ChatGPT-tier rejects most IDs).
    assert ctx["model_codex"] is None


def test_production_preset_reasoning_agent_gets_high_effort() -> None:
    """Production preset → autoloop-coder (reasoning-heavy) gets high effort."""
    specs = _codex_agent_files(preset=Preset.PRODUCTION)
    ctx = _ctx_for("autoloop-coder", specs)
    assert ctx["codex_reasoning_effort"] == "high"


def test_side_preset_downshifts_reviewer_to_low() -> None:
    """Side preset → code-reviewer drops to low effort (cost optimization)."""
    specs = _codex_agent_files(preset=Preset.SIDE)
    ctx = _ctx_for("code-reviewer", specs)
    assert ctx["codex_reasoning_effort"] == "low"


def test_explicit_override_beats_preset_for_codex() -> None:
    """User-supplied agent_models override wins on Codex side too."""
    custom = AgentModelSpec(codex=CodexAgentSpec(reasoning_effort="xhigh"))
    specs = _codex_agent_files(
        preset=Preset.SIDE,
        agent_models={"code-reviewer": custom},
    )
    ctx = _ctx_for("code-reviewer", specs)
    assert ctx["codex_reasoning_effort"] == "xhigh"


def test_codex_template_renders_reasoning_effort_line() -> None:
    """End-to-end render check: the .codex/agents/<n>.toml file actually
    contains the `model_reasoning_effort = "..."` line when the spec provides
    one. Catches template-context wiring issues.

    The agent _body templates pull from many config fields (project.domains,
    reviewers.verbosity, etc.), so use a real HarnessConfig().model_dump()
    rather than a minimal stub.
    """
    from pathlib import Path

    from jinja2 import Environment, FileSystemLoader, StrictUndefined

    from harness_maker.models import HarnessConfig

    templates_dir = Path(__file__).resolve().parents[2] / "src" / "harness_maker" / "templates"
    env = Environment(
        loader=FileSystemLoader(str(templates_dir)),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
    )
    config_dump = HarnessConfig().model_dump(mode="json")
    rendered = env.get_template("codex/agent.toml.j2").render(
        name="code-reviewer",
        description="Reviews code",
        model_codex=None,
        codex_reasoning_effort="medium",
        reviewer_kind="code",
        communication_variant="reframe",
        config=config_dump,
        preset="Production",
    )
    assert 'model_reasoning_effort = "medium"' in rendered
    # `model =` line stays omitted (ADR-008 + RESEARCH-codex precedent).
    assert "\nmodel = " not in rendered


def test_codex_config_toml_renders_profile_blocks() -> None:
    """.codex/config.toml has [profiles.cheap] + [profiles.deep] blocks."""
    from pathlib import Path

    from jinja2 import Environment, FileSystemLoader, StrictUndefined

    templates_dir = Path(__file__).resolve().parents[2] / "src" / "harness_maker" / "templates"
    env = Environment(
        loader=FileSystemLoader(str(templates_dir)),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
    )
    rendered = env.get_template("codex/config.toml.j2").render(
        agents={"code-reviewer": "Reviews code"},
        config={"mcp_servers": {}},
    )
    assert "[profiles.cheap]" in rendered
    assert 'model_reasoning_effort = "minimal"' in rendered
    assert "[profiles.deep]" in rendered
    assert 'model_reasoning_effort = "high"' in rendered
