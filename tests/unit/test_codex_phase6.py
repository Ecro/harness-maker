"""Phase 6 tests: Codex agent TOML templates (12 agents via codex/agent.toml.j2).

RED before Phase 6 implementation:
- templates/codex/agent.toml.j2 does not yet exist
- _codex_agent_files() is a stub returning []
- _codex_target_files() does not include agent TOML entries

GREEN after Phase 6:
- Each agent renders valid TOML
- developer_instructions does NOT contain YAML frontmatter (ADR-007 regression guard)
- All 12 agent paths present in _codex_target_files()
"""

from __future__ import annotations

import tomllib

import pytest

from harness_maker.render import _make_env
from harness_maker.synthesize import (
    _ALL_AGENTS,
    _codex_agent_files,
    _codex_target_files,
)

_BASE_CONFIG = {
    "preset": "Production",
    "dev_mode": "task-driven",
    "default_workflow": "exec-rev-wrap",
    "caching": "agent-aware",
    "reviewers": {"verbosity": "standard"},
    "project": {"domains": []},
    "work_docs": {"dir": "work-docs/"},
    "spec": {"dir": "specs/"},
    "mcp_servers": {},
}


def _render_agent_toml(name: str) -> dict:
    """Render a Codex agent TOML using production context from _codex_agent_files()."""
    specs = _codex_agent_files()
    agent_ctx = next((ctx for _, out, ctx in specs if out == f".codex/agents/{name}.toml"), {})
    assert agent_ctx, f"_codex_agent_files() returned no entry for {name!r}"
    env = _make_env()
    tpl = env.get_template("codex/agent.toml.j2")
    rendered = tpl.render(**agent_ctx, config=_BASE_CONFIG)
    return tomllib.loads(rendered)


# ── template existence and valid TOML ─────────────────────────────────────────


@pytest.mark.parametrize("name", _ALL_AGENTS)
def test_codex_agent_toml_renders_valid_toml(name: str) -> None:
    """codex/agent.toml.j2 must produce parse-able TOML for each agent."""
    _render_agent_toml(name)  # raises TOMLDecodeError on invalid TOML


@pytest.mark.parametrize("name", _ALL_AGENTS)
def test_codex_agent_toml_has_name_field(name: str) -> None:
    """Rendered TOML must have a 'name' field matching the agent name."""
    parsed = _render_agent_toml(name)
    assert parsed.get("name") == name, f"Agent {name!r} TOML missing correct 'name' field"


@pytest.mark.parametrize("name", _ALL_AGENTS)
def test_codex_agent_toml_has_description_field(name: str) -> None:
    """Rendered TOML must have a non-empty 'description' field."""
    parsed = _render_agent_toml(name)
    assert parsed.get("description"), f"Agent {name!r} TOML missing 'description' field"


@pytest.mark.parametrize("name", _ALL_AGENTS)
def test_codex_agent_toml_has_developer_instructions(name: str) -> None:
    """Rendered TOML must have a non-empty 'developer_instructions' field."""
    parsed = _render_agent_toml(name)
    assert parsed.get("developer_instructions"), (
        f"Agent {name!r} TOML missing 'developer_instructions' field"
    )


@pytest.mark.parametrize("name", _ALL_AGENTS)
def test_codex_agent_toml_developer_instructions_no_yaml_frontmatter(name: str) -> None:
    """developer_instructions must NOT start with YAML frontmatter (ADR-007 regression guard)."""
    parsed = _render_agent_toml(name)
    instructions = parsed.get("developer_instructions", "")
    # The body partial must not contain the ---\nname: frontmatter block
    assert "---\nname:" not in instructions, (
        f"Agent {name!r} developer_instructions contains YAML frontmatter — "
        "body partial refactor (ADR-007) is broken"
    )


@pytest.mark.parametrize("name", _ALL_AGENTS)
def test_codex_agent_toml_developer_instructions_has_heading(name: str) -> None:
    """developer_instructions must contain the agent name as a Markdown heading."""
    parsed = _render_agent_toml(name)
    instructions = parsed.get("developer_instructions", "")
    assert f"# {name}" in instructions, (
        f"Agent {name!r} developer_instructions missing '# {name}' heading"
    )


# ── synthesize: _codex_agent_files and _codex_target_files ───────────────────


def test_codex_agent_files_returns_12_entries() -> None:
    """_codex_agent_files() must return 12 FileSpec entries (one per agent)."""
    specs = _codex_agent_files()
    assert len(specs) == 12, f"Expected 12 agent specs, got {len(specs)}"


def test_codex_agent_files_correct_output_paths() -> None:
    """Each agent FileSpec must have output path .codex/agents/<name>.toml."""
    specs = _codex_agent_files()
    out_paths = {out for _, out, _ in specs}
    for name in _ALL_AGENTS:
        assert f".codex/agents/{name}.toml" in out_paths, (
            f"Missing output path for agent {name!r}"
        )


def test_codex_target_files_includes_all_agent_tomls() -> None:
    """_codex_target_files() must include all 12 .codex/agents/*.toml paths."""
    out_paths = {out for _, out, _ in _codex_target_files()}
    for name in _ALL_AGENTS:
        assert f".codex/agents/{name}.toml" in out_paths, (
            f"_codex_target_files missing agent {name!r}"
        )
