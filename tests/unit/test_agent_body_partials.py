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
    # Phase 5 (REVIEW MV-3 + C-1 fix, 2026-05-19) bumped these 12 hashes.
    # The dispatcher templates now emit cursor_model concrete IDs (when
    # available) with a None-guard fallback chain. Pre-fix hashes are in
    # git history under commit ${PRE_PHASE_5}.
    "autoloop-coder": "328eb72fe2ba3d99d9ceecca4a2f00ca349c266e4a98a75d305f894a7e4662ac",
    "code-reviewer": "4c88418df33c99741e31b4265bf2dbb832c78c51bd87da116925d192eed9568f",
    "concurrency-reviewer": "4d78ffc89957060e675ad6552f5ea082ba068a77e95771d4fee67f3e235688fd",
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
    "consensus-arbiter": "9a5833320294faaeff0819573fabbee349a23aef8c313facdc8214ae06f2dd24",
    "executor": "d2762982da93b4ebba0aec7004a1ca721a6561e9c1c84b53512ce9d48cb391a8",
    "performance-reviewer": "528788051f31414258cabb083a16e578a6d3fc8f112ec071984a31f57edd63c5",
    "plan-validator": "e333c2d3d9ef1f9cb325a3da51da8f240a077e92b6d651c9387c644d3da9504a",
    "security-auditor": "7dfb6da0797f4d3b8b5e47dee0a9625968079aaf6aabd3b98d6383a902cda4fb",
    "security-reviewer": "1d0dd18466dfbc2ca1cb464134babc38a0555914c4767e0f5c80e8621da58626",
    "stuck": "9db1b3f1e94c31a4613868330f3e52aa0796f387f779ae48a1fd030be0f3080c",
    "test-reviewer": "4b36d7169eb7041450c6d705ebe6f550b31f31d9b8c85565ab4fdff7822d2e9d",
    "ux-reviewer": "f0d5e2bbb92271f712fad3e7bc3e6b56fd6276922e0f68218e7f33fab5b82a6f",
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
