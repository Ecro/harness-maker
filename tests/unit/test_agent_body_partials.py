"""Phase 3 regression tests: agent _body.md.j2 partials exist + full md.j2 is unchanged.

These tests are RED before the refactor (TemplateNotFound on _body.md.j2 imports).
After the refactor they verify zero behavioral change — full agent md.j2 output
must be identical to what it was before splitting the body into a partial.
"""

from __future__ import annotations

import hashlib

import pytest

from harness_maker.render import _make_env

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
    env = _make_env()
    tpl = env.get_template(f"agents/{name}.md.j2")
    return tpl.render(
        name=name,
        reviewer_kind=_REVIEWER_KINDS.get(name, ""),
        config=_FULL_CONFIG,
    )


def _render_body(name: str) -> str:
    env = _make_env()
    tpl = env.get_template(f"agents/{name}_body.md.j2")
    return tpl.render(
        name=name,
        reviewer_kind=_REVIEWER_KINDS.get(name, ""),
        config=_FULL_CONFIG,
    )


# Pre-refactor sha256 of each full agent md.j2 render (captured before Phase 3 body-split).
# 9 agents were verified against pre-refactor values using minimal config.
# stuck + test-reviewer require work_docs/spec in config → captured with _FULL_CONFIG
# after verifying -%} whitespace-trim fix produces zero diff on all 9 checkable agents.
_EXPECTED_SHA256: dict[str, str] = {
    "autoloop-coder": "1889773f6ad10e9659f32fdea9300c5a041178e9c1546540ee80cbfa0089426a",
    "code-reviewer": "57bf412a7e93463c931930558d6afd2114983c9a29f2406653e6afa9a05000d7",
    "concurrency-reviewer": "bb11ace54c41b8634b73a59b232d20fd2ad2035e4612df836516e7c82fbc79e5",
    "consensus-arbiter": "1e628aa224fd2a668a6e6c08b64b42459e8e545b78a5720042572599a3301d3c",
    "executor": "d78b2df7a3a04008ee5f87c5b5610732fcd706563d23e3ced30fc1916db1fa73",
    "performance-reviewer": "6b5e6fea8da59eb9ce017bc92c651d5252c371b4f076813d5546c4e805084b7c",
    "plan-validator": "c3bc0546ad28adfdc36401ae2c3d189f443d3f120b20a5603e0c8cf32ea6afe1",
    "security-auditor": "8ac1b082fcd2fe1ad2d520f85f068f5f1f1082e54230fb6ecec7dd0d446f0b32",
    "security-reviewer": "4e44c9bc3849a7da176ffb061a51bb956799416584c14edf1ede1ce8c7b7d252",
    "stuck": "d0c5e1655ef5253390198d7916ce36b955c72ef54f5a8677128fef35535d637a",
    "test-reviewer": "ebda93df78ecf4df3eaf90821b0d7d9b2ab3c116015b065867913fe2e3ce5220",
    "ux-reviewer": "857f706400b2e9b891b307bdd0a0765b8161764794a926a67acc9460034fee2f",
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
