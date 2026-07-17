"""Phase 3 regression tests: agent _body.md.j2 partials exist + full md.j2 is unchanged.

These tests are RED before the refactor (TemplateNotFound on _body.md.j2 imports).
After the refactor they verify zero behavioral change — full agent md.j2 output
must be identical to what it was before splitting the body into a partial.
"""

from __future__ import annotations

import hashlib

import pytest

from harness_maker.render import _extract_source_communication_variant, _make_env

_ALL_AGENTS: list[str] = [
    "autoloop-coder",
    "code-reviewer",
    "concurrency-reviewer",
    "consensus-arbiter",
    "executor",
    "performance-reviewer",
    "plan-validator",
    "security-auditor",
    "security-reviewer",
    "stuck",
    "test-reviewer",
    "ux-reviewer",
]

_REVIEWER_KINDS: dict[str, str] = {
    "code-reviewer": "code",
    "security-reviewer": "security",
    "performance-reviewer": "performance",
    "concurrency-reviewer": "concurrency",
    "ux-reviewer": "ux",
}

_FULL_CONFIG = {
    "reviewers": {"verbosity": "standard"},
    "project": {"domains": []},
    "work_docs": {"dir": "work-docs/"},
    "spec": {"dir": "specs/"},
    "dev_mode": "task-driven",
}


def _render_agent(name: str) -> str:
    from harness_maker.models import HarnessConfig, Preset
    from harness_maker.presets import resolve_agent_spec

    env = _make_env()
    variant = _extract_source_communication_variant(f"agents/{name}.md.j2", env)
    tpl = env.get_template(f"agents/{name}.md.j2")
    # Phase 3 (PLAN-model-routing-multi-ide) added claude_model/cursor_model/
    # codex_reasoning_effort context vars. Pass the Production preset's resolved
    # values so the sha256 pin reflects what synthesize() emits in real renders
    # (autoloop-coder/plan-validator/stuck → opus; others → sonnet).
    spec = resolve_agent_spec(name, HarnessConfig(preset=Preset.PRODUCTION))
    return tpl.render(
        name=name,
        reviewer_kind=_REVIEWER_KINDS.get(name, ""),
        config=_FULL_CONFIG,
        communication_variant=variant,
        claude_model=spec.claude,
        cursor_model=spec.cursor,
        codex_reasoning_effort=(spec.codex.reasoning_effort if spec.codex else None),
    )


def _render_body(name: str) -> str:
    env = _make_env()
    variant = _extract_source_communication_variant(f"agents/{name}.md.j2", env)
    tpl = env.get_template(f"agents/{name}_body.md.j2")
    return tpl.render(
        name=name,
        reviewer_kind=_REVIEWER_KINDS.get(name, ""),
        config=_FULL_CONFIG,
        communication_variant=variant,
    )


# Baseline sha256 of each full agent md.j2 render.
# Originally captured before the Phase 3 body-split refactor as a zero-diff
# guard. Phase C of PLAN-llm-code-review-2026 (2026-05-11) intentionally
# rewrites the 5 reviewer bodies (code/security/performance/concurrency/ux)
# to add the agentic-depth Investigation Steps section + untrusted-data
# caveat (ADR-009 substring contract + Round-2 prompt-injection fix). The
# 5 reviewer entries below are the post-Phase-C hashes; the remaining 7
# agents keep their pre-refactor hashes.
_EXPECTED_SHA256: dict[str, str] = {
    # ALL hashes re-pinned 2026-07-17 (PLAN-permission-deny-and-hooks-wiring
    # Phase 7, ADR-002): the `permissions:` frontmatter block was deleted from
    # every agent template. Claude Code has no such subagent-frontmatter field —
    # it was silently ignored, so the blocks enforced nothing while reading as a
    # security boundary (they misled the incoming brief's author with the docs
    # open). executor + autoloop-coder additionally lost their "Permissions
    # policy" prose section, reworded to "Scope — instruction, not enforcement"
    # so the agent is told the truth: only `tools:` binds it.
    # Pre-bump hashes in git history.
    # Bumped 2026-05-31 (PLAN-agent-model-version-agnostic ADR-001): the
    # dispatcher `model:` line is now a shared partial rendering the Claude
    # ALIAS (`{{ claude_model }}`), SUPERSEDING the Phase-5 (2026-05-19 C-1)
    # cursor-concrete-id behavior — Claude Code now respects the field (#43869),
    # so a pinned id fails to launch in a newer-model session. Pre-bump hashes
    # are in git history.
    # code-reviewer + consensus-arbiter + plan-validator: 0.28.5 added an
    # UNCONDITIONAL `Bash` to `tools:`; 0.28.6 (PLAN-spoton-codex-rm-stash-
    # rootcause follow-up) made it CONDITIONAL on codex_second_opinion.enabled
    # — subagent-frontmatter `permissions.deny` is NOT enforced by Claude Code,
    # so a bare Bash tool = unrestricted shell; confine it to opted-in users.
    # `_render_agent` uses a no-codex config, so these 3 revert to their
    # pre-0.28.5 hashes. The codex-ENABLED tools:Bash path is asserted in
    # test_render_codex_permission_injection.py. Pre-bump hashes in git history.
    "autoloop-coder": "093210f0b4da3e0d0431c7fa4a0833f19f320d04ee349989fd8b5b5882483932",
    "code-reviewer": "cd980f015d0774eca7a97ec721a3a317f53f781ddc6b8902d88704617e3ac2ef",
    "concurrency-reviewer": "6e115a2b7798a0eca6047b4e4cdbc3bb78884ac16acf7e91e4be090cdb8563d0",
    # consensus-arbiter + plan-validator: hashes bumped 2026-05-24 per
    # PLAN-codex-second-llm-integration ADR-007 + review security fix.
    # Both agents previously had NO frontmatter permissions block; Phase 2
    # added a minimal one with allow: [Read(*), Grep(*), Glob(*)] + conditional
    # Bash(codex exec:*), and the security review added the full deny:
    # baseline (Write/Edit + Bash interpreter denies) matching code-reviewer.
    # The conditional codex line is BYTE-ZERO when enabled=false (test config),
    # so the rendered hash reflects the new allow-list + deny baseline.
    # PLAN R8 risk: any future drift in the baseline changes these hashes —
    # re-pin and document the reason here.
    # consensus-arbiter re-pinned 2026-07-01 (PLAN-review-grade-criteria ADR-002):
    # Step 4c hard-sealed (dead cross-tier "Middle of the scale" rows removed;
    # "single-tier by construction" replacement), Hard Rule + Out-of-Scope
    # reconciled to forbid cross-tier severity resolution, and the user-extension
    # comment reworded to forbid tier bridging. Body change outside the codex
    # conditional, so the disabled-config hash moves. Pre-bump hash in git history.
    "consensus-arbiter": "c340a9c4fb8f043d8d33b785c1ee4e54f35f8b735e46baa87951c54b097051ba",
    # executor: re-pinned 2026-06-03 (PLAN-techspec-audit F61). The description
    # + body claimed a runtime-enforced "never writes to repo root" boundary that
    # Claude Code does NOT enforce (subagent-frontmatter permissions are not
    # enforced — see CLAUDE.md §보안/권한). Reworded to "by convention, prompt-
    # level guidance, not runtime-enforced". Pre-bump hash in git history.
    "executor": "0a4a5e34f5b7d985eab1b0b8b2ee79d898d3d95ddd4d68eea051536939e96874",
    "performance-reviewer": "8735a961e59fd3475de4ff6e45b8f4e89fd4e1e0c808f4acaaf65504a3a62b9a",
    "plan-validator": "2116a5ce4fb8053c0a8c921f2a1e2c022ea5099f488e8bc315a6a87b097ec36b",
    "security-auditor": "51a11902b9f56b9ebb0e0103e0d2047a64d1a218898d6cedc229a1a43fed2f53",
    "security-reviewer": "33a672397c087866e001b875e99998f46920a0b15b024ce277f2a5b319f73d48",
    "stuck": "a62459d1205ed4fd67769ebb2f729a4de9b1d7b9ff5d770cc6ed767e63746fd0",
    "test-reviewer": "d102698d962884761172fa6a241c8a578cb7c038596905c141fd9f596b37cabb",
    "ux-reviewer": "b65045b2f2fafb1d3fb8fd2f16469a2c2977a28ef7ee9a1eb4f6529aa0ad0d96",
}


@pytest.mark.parametrize("name", _ALL_AGENTS)
def test_body_partial_renders_non_empty(name: str) -> None:
    """Each _body.md.j2 partial must exist and render non-empty content."""
    body = _render_body(name)
    assert body.strip(), f"Body partial for {name!r} rendered empty"


@pytest.mark.parametrize("name", _ALL_AGENTS)
def test_body_partial_does_not_contain_yaml_frontmatter(name: str) -> None:
    """Body partial MUST NOT start with ---\\n (frontmatter would bleed into Codex TOML)."""
    body = _render_body(name)
    assert not body.lstrip().startswith("---\n"), (
        f"Body partial for {name!r} starts with YAML frontmatter — "
        "this would bleed into Codex TOML developer_instructions"
    )


@pytest.mark.parametrize("name", _ALL_AGENTS)
def test_full_agent_md_starts_with_frontmatter(name: str) -> None:
    """Full agent md.j2 (with frontmatter + include) must still start with ---."""
    full = _render_agent(name)
    assert full.startswith("---\n"), (
        f"Full agent template for {name!r} no longer starts with YAML frontmatter"
    )


@pytest.mark.parametrize("name", _ALL_AGENTS)
def test_full_agent_md_contains_name_heading(name: str) -> None:
    """Full agent md.j2 body must contain the agent name as a markdown heading."""
    full = _render_agent(name)
    assert f"# {name}" in full, (
        f"Agent {name!r} full template missing '# {name}' heading — body partial likely missing"
    )


@pytest.mark.parametrize(
    "name",
    [n for n in _ALL_AGENTS if _EXPECTED_SHA256.get(n)],
)
def test_full_agent_md_sha256_unchanged(name: str) -> None:
    """Full agent md.j2 output sha256 must be identical to pre-refactor baseline."""
    full = _render_agent(name)
    actual = hashlib.sha256(full.encode()).hexdigest()
    expected = _EXPECTED_SHA256[name]
    assert actual == expected, (
        f"Agent {name!r} output changed after body partial refactor!\n"
        f"  expected sha256: {expected}\n"
        f"  actual   sha256: {actual}\n"
        "The refactor must produce zero diff in rendered output."
    )
