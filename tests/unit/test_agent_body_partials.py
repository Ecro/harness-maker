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
    "autoloop-coder": "125bc43d1848570c88d38212b7c9ed69e3cc6b6604ce6b1e7c8989eaa0b446a7",
    "code-reviewer": "d9172c478af1837c186a9bc8d8f3903f6b28aa8887184fe46c1030b7a205c12c",
    "concurrency-reviewer": "b5f1343184940919ae15e5363a3a9f793d3271c036d4b94c1811f586d14c637c",
    "consensus-arbiter": "2bd9ff2373a47ac36bc77e4f1fc5a93c66eaec3241aaabbbbc94042e31c7432e",
    "executor": "226482b939449c7515f6befd6d20b0cc7aa689daebdd110a319d3314627dd5d9",
    "performance-reviewer": "fcb80fdee6cc5a407f06e7ec5f9248d2ffe2818cd6e9611fd7e63ec3ef55e549",
    "plan-validator": "964ff4330221e2dd12f203f58160364d09b76c98fdacc2e5f427e62254cd7489",
    "security-auditor": "0409a3b2dfaed33bc6b4c7a9dbb73bd5582bdcaf7e7f0cc5f66b9dee8a77892b",
    "security-reviewer": "628be7d748daac293341b671d940b22d5db3de8bb6c62549e3f4bf5f8e69d7bb",
    "stuck": "b6ae0cff58351ac80b232fda6984d9f1e6f080e1dbe2b6195e032f7caaf32979",
    "test-reviewer": "a72bcc15d7989d9176d9795befac41a8358ff4ad9b4d5c4d3de2f6c12ba731d2",
    "ux-reviewer": "eaa88cdca9f9b764fcd97f080318738a323da8358971c0a71a131c32f838211b",
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
