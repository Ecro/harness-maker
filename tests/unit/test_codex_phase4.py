"""Phase 4 tests: Codex config.toml + AGENTS.md templates + reconcile + synthesize wiring.

RED before Phase 4 implementation:
- templates/codex/config.toml.j2 does not yet exist
- templates/codex/AGENTS.md.j2 does not yet exist
- _codex_target_files() returns [] (stub)
- reconcile() treats AGENTS.md as no-frontmatter → KEEP (wrong)

GREEN after Phase 4:
- config.toml.j2 renders valid TOML
- AGENTS.md.j2 renders non-empty content with block markers but no YAML frontmatter
- _codex_target_files() includes both files
- reconcile() returns MERGE_BLOCK for existing AGENTS.md, BOTH when new
"""

from __future__ import annotations

import tomllib
from pathlib import Path

from harness_maker.models import Blueprint, FileEntry, ReconcileDecision
from harness_maker.reconcile import reconcile
from harness_maker.render import _make_env
from harness_maker.synthesize import _codex_target_files

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

_CONFIG_WITH_MCP = {
    **_BASE_CONFIG,
    "mcp_servers": {
        "my-server": {"command": "npx", "args": ["-y", "@my/server"]},
    },
}


# ── config.toml.j2 ────────────────────────────────────────────────────────────


def test_codex_config_toml_renders_valid_toml() -> None:
    """templates/codex/config.toml.j2 must produce parse-able TOML."""
    env = _make_env()
    tpl = env.get_template("codex/config.toml.j2")
    rendered = tpl.render(config=_BASE_CONFIG, agents={})
    tomllib.loads(rendered)  # raises TOMLDecodeError on invalid TOML


def test_codex_config_toml_has_features_section() -> None:
    """Rendered config.toml must contain [features] with hooks = true."""
    env = _make_env()
    tpl = env.get_template("codex/config.toml.j2")
    rendered = tpl.render(config=_BASE_CONFIG, agents={})
    parsed = tomllib.loads(rendered)
    assert parsed.get("features", {}).get("hooks") is True


def test_codex_config_toml_mcp_servers_included() -> None:
    """MCP servers from config.mcp_servers appear in rendered config.toml."""
    env = _make_env()
    tpl = env.get_template("codex/config.toml.j2")
    rendered = tpl.render(config=_CONFIG_WITH_MCP, agents={})
    parsed = tomllib.loads(rendered)
    assert "my-server" in parsed.get("mcp_servers", {})


def test_codex_config_toml_empty_mcp_servers_no_section() -> None:
    """Empty mcp_servers → no [mcp_servers] table in rendered TOML (no orphan header)."""
    env = _make_env()
    tpl = env.get_template("codex/config.toml.j2")
    rendered = tpl.render(config=_BASE_CONFIG, agents={})
    parsed = tomllib.loads(rendered)
    assert "mcp_servers" not in parsed, (
        "Empty mcp_servers should not render a [mcp_servers] section"
    )


# ── AGENTS.md.j2 ──────────────────────────────────────────────────────────────


def test_codex_agents_md_renders_non_empty() -> None:
    """templates/codex/AGENTS.md.j2 must render non-empty content."""
    env = _make_env()
    tpl = env.get_template("codex/AGENTS.md.j2")
    rendered = tpl.render(config=_BASE_CONFIG, preset="Production")
    assert rendered.strip(), "AGENTS.md.j2 rendered empty"


def test_codex_agents_md_no_yaml_frontmatter() -> None:
    """AGENTS.md must NOT start with ---\\n (would appear as literal text in Codex)."""
    env = _make_env()
    tpl = env.get_template("codex/AGENTS.md.j2")
    rendered = tpl.render(config=_BASE_CONFIG, preset="Production")
    assert not rendered.lstrip().startswith("---\n"), (
        "AGENTS.md starts with YAML frontmatter — Codex shows it as literal text"
    )


def test_codex_agents_md_has_block_markers() -> None:
    """AGENTS.md must contain <!-- @hm:user:* --> block markers for MERGE_BLOCK."""
    env = _make_env()
    tpl = env.get_template("codex/AGENTS.md.j2")
    rendered = tpl.render(config=_BASE_CONFIG, preset="Production")
    assert "<!-- @hm:user:" in rendered, (
        "AGENTS.md missing <!-- @hm:user:* --> block markers — block_merge won't work"
    )


def test_codex_agents_md_mentions_workflow() -> None:
    """AGENTS.md must mention the default workflow for Codex users."""
    env = _make_env()
    tpl = env.get_template("codex/AGENTS.md.j2")
    rendered = tpl.render(config=_BASE_CONFIG, preset="Production")
    assert "exec-rev-wrap" in rendered, (
        "AGENTS.md does not reference the configured default_workflow"
    )


# ── reconcile: AGENTS.md special-casing ───────────────────────────────────────


def test_reconcile_agents_md_both_when_new(tmp_path: Path) -> None:
    """_codex_target_files includes AGENTS.md; reconcile returns BOTH when file absent.

    AGENTS.md resolves to target_dir.parent (project root), so existing_dir must
    be the .claude/ subdir so the path routing mirrors production use.
    """
    specs = _codex_target_files({})
    agents_md_specs = [(t, o, c) for t, o, c in specs if o == "AGENTS.md"]
    assert agents_md_specs, "_codex_target_files must include AGENTS.md (prerequisite S7)"
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    bp = Blueprint(files=[FileEntry(path=Path("AGENTS.md"), template=agents_md_specs[0][0])])
    # AGENTS.md → tmp_path/AGENTS.md (does not exist) → BOTH
    conflicts = reconcile(claude_dir, bp)
    assert len(conflicts) == 1
    assert conflicts[0].decision == ReconcileDecision.BOTH


def test_reconcile_agents_md_merge_block_when_exists(tmp_path: Path) -> None:
    """When AGENTS.md exists at project root → MERGE_BLOCK (MVP always re-merges).

    existing_dir is .claude/; AGENTS.md lives at project root (existing_dir.parent).
    """
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    agents_md = tmp_path / "AGENTS.md"
    agents_md.write_text(
        "# AGENTS.md\n"
        "<!-- @hm:user:project-rules -->\nsome user rule\n<!-- @hm:/user:project-rules -->\n",
        encoding="utf-8",
    )
    bp = Blueprint(files=[FileEntry(path=Path("AGENTS.md"), template="codex/AGENTS.md.j2")])
    conflicts = reconcile(claude_dir, bp)
    assert len(conflicts) == 1
    assert conflicts[0].decision == ReconcileDecision.MERGE_BLOCK


def test_reconcile_agents_md_merge_block_reason(tmp_path: Path) -> None:
    """Reconcile reason for existing AGENTS.md must contain 'codex' to identify the path."""
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    agents_md = tmp_path / "AGENTS.md"
    agents_md.write_text(
        "# AGENTS.md\n<!-- @hm:user:ext -->\ncontent\n<!-- @hm:/user:ext -->\n",
        encoding="utf-8",
    )
    bp = Blueprint(files=[FileEntry(path=Path("AGENTS.md"), template="codex/AGENTS.md.j2")])
    conflicts = reconcile(claude_dir, bp)
    assert conflicts[0].decision == ReconcileDecision.MERGE_BLOCK
    assert conflicts[0].reason is not None
    assert "codex" in conflicts[0].reason


# ── synthesize: _codex_target_files wiring ────────────────────────────────────


def test_codex_target_files_includes_config_toml() -> None:
    """_codex_target_files() must include .codex/config.toml entry."""
    specs = _codex_target_files({})
    out_paths = [out for _, out, _ in specs]
    assert ".codex/config.toml" in out_paths


def test_codex_target_files_includes_agents_md() -> None:
    """_codex_target_files() must include AGENTS.md entry."""
    specs = _codex_target_files({})
    out_paths = [out for _, out, _ in specs]
    assert "AGENTS.md" in out_paths


def test_codex_target_files_template_names_exist() -> None:
    """Templates referenced in _codex_target_files() must be loadable by Jinja2 env."""
    env = _make_env()
    for tpl_path, _, _ in _codex_target_files({}):
        env.get_template(tpl_path)  # raises TemplateNotFound if missing


# ── ADR-001: config.toml agents-section shape contract ────────────────────────


def test_codex_config_toml_agents_section_renders_string_descriptions() -> None:
    """`config.toml.j2` receives `{name: str}` (not `{name: tuple}`) from synthesize.

    Shape-regression guard: pre-ADR-001 `_CODEX_AGENT_META` was
    `dict[str, tuple[str, str]]` and the caller projected `meta[0]` to keep
    the template input a `str`. Post-ADR-001 the value IS the description
    `str` directly. Either shape produces equivalent template output today,
    but a partial revert (only one side) would render `description = ["desc",
    "model"]` (TOML array) instead of a string — and `tojson` would accept
    that, so the bug would NOT raise at parse time. This test locks the
    contract: every agent description routed into the config template is a
    plain `str`.
    """
    from harness_maker.synthesize import _CODEX_AGENT_META

    specs = _codex_target_files({})
    config_spec = next(
        (ctx for tpl, out, ctx in specs if out == ".codex/config.toml"),
        None,
    )
    assert config_spec is not None, (
        "_codex_target_files() did not emit a .codex/config.toml spec — has the "
        "synthesizer entry been removed?"
    )
    agents = config_spec.get("agents")
    assert isinstance(agents, dict), (
        f"config.toml context['agents'] must be a dict, got {type(agents).__name__}"
    )
    assert set(agents.keys()) == set(_CODEX_AGENT_META.keys()), (
        "config.toml agents keys diverge from _CODEX_AGENT_META — synthesizer "
        "wiring drifted from the source-of-truth mapping"
    )
    for name, desc in agents.items():
        assert isinstance(desc, str), (
            f"config.toml context['agents'][{name!r}] = {desc!r}; "
            f"expected str (got {type(desc).__name__}). ADR-001 shape regression."
        )
