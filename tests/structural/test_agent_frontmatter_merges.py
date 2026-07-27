"""Every rendered agent must expose ONE parseable frontmatter block carrying `name`.

The renderer merges an agent template's own frontmatter into the provenance block it
prepends. That merge parses the source frontmatter as YAML — so an unquoted value
containing `: ` silently defeats it, and the renderer emits the agent's fields as a
SECOND `---` block after the provenance one. Claude Code reads only the first block, so
the agent ships with no `name` and no `description`: broken as an agent, not merely
untidy.

That is exactly what happened to `stage-delegate`, whose description read
`Runs a whole /hm: stage body …`. It was caught by `readiness`'s
`agent_frontmatter_valid` signal — but only in CI, because the integration test that
computes readiness is `INTEGRATION=1`-gated and skips in the default suite. This test
runs unconditionally so the next one fails locally, in seconds, at the point of change.

CLAUDE.md checkpoint 2: the file is read by a tool that is not us, and its parser
decides what is valid.
"""

from __future__ import annotations

import pytest
import yaml

from harness_maker.models import InterviewAnswers, Preset, ProjectProfile, Target
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import _ALL_AGENTS, synthesize


@pytest.fixture(scope="module")
def rendered_agents(tmp_path_factory: pytest.TempPathFactory) -> dict[str, str]:
    out = tmp_path_factory.mktemp("agents-render")
    render(
        synthesize(
            ProjectProfile(),
            InterviewAnswers(preset=Preset.PRODUCTION, targets=[Target.CLAUDE_CODE]),
        ),
        out,
        freeze_time=DEFAULT_FREEZE_TIME,
    )
    return {
        name: (out / "agents" / f"{name}.md").read_text(encoding="utf-8") for name in _ALL_AGENTS
    }


def _frontmatter(body: str) -> tuple[str, str]:
    """(first block, remainder). Splitting on the literal fence, not on a YAML parse."""
    assert body.startswith("---\n"), "rendered agent does not open with a frontmatter fence"
    end = body.index("\n---\n", 4)
    return body[4:end], body[end + len("\n---\n") :]


@pytest.mark.parametrize("name", _ALL_AGENTS)
def test_agent_frontmatter_is_a_single_parseable_block(
    name: str, rendered_agents: dict[str, str]
) -> None:
    block, _rest = _frontmatter(rendered_agents[name])

    data = yaml.safe_load(block)
    assert isinstance(data, dict), f"{name}: frontmatter is not a YAML mapping"
    # `name` and `description` are what Claude Code dispatches on; provenance keys
    # alone mean the merge failed and the real fields are stranded in a second block.
    assert data.get("name") == name, (
        f"{name}: frontmatter `name` missing or wrong: {data.get('name')!r}"
    )
    description = data.get("description")
    assert isinstance(description, str), (
        f"{name}: frontmatter `description` missing — the source frontmatter did not "
        "merge (an unquoted `: ` in a value is the usual cause)"
    )
    assert description.strip(), f"{name}: frontmatter `description` is empty"


@pytest.mark.parametrize("name", _ALL_AGENTS)
def test_agent_body_has_no_second_frontmatter_block(
    name: str, rendered_agents: dict[str, str]
) -> None:
    """The failure mode is a stranded second block, so assert on it directly.

    Checking only that the first block parses would pass on the broken artifact: the
    provenance block is valid YAML on its own, which is precisely why the defect looked
    fine to every other test.
    """
    _block, rest = _frontmatter(rendered_agents[name])

    assert not rest.lstrip().startswith("---"), (
        f"{name}: a second frontmatter block follows the provenance block — the source "
        "frontmatter failed to merge and Claude Code will never read those fields"
    )


# `tools:` is the ONLY enforced agent boundary (CLAUDE.md §보안): frontmatter
# `permissions:` is silently ignored by Claude Code, and an ABSENT `tools:` makes a
# subagent inherit every tool the main thread has. So its loss is a security
# regression, not a cosmetic one — and the two tests above pass a partial merge that
# keeps `name`/`description` and drops it.
_READ_ONLY_AGENTS = frozenset(
    {
        "code-reviewer",
        "code-verifier",
        "concurrency-reviewer",
        "consensus-arbiter",
        "judgment-reviewer",
        "performance-reviewer",
        "plan-validator",
        "security-reviewer",
        "stuck",
        "test-reviewer",
        "ux-reviewer",
    }
)


@pytest.mark.parametrize("name", _ALL_AGENTS)
def test_every_agent_declares_a_non_empty_tools_list(
    name: str, rendered_agents: dict[str, str]
) -> None:
    block, _rest = _frontmatter(rendered_agents[name])
    data = yaml.safe_load(block)

    tools = data.get("tools")
    assert isinstance(tools, str), (
        f"{name}: no `tools:` in the merged frontmatter — an absent tools list makes the "
        "subagent inherit every tool the main thread has"
    )
    assert tools.strip(), f"{name}: `tools:` is empty"


def _granted_tools(value: object) -> set[str]:
    """Parse `tools:` in BOTH shapes YAML can produce, because the assertion below is
    an intersection and an unparsed shape silently makes it empty.

    `str(["Read", "Write"]).split(",")` yields `{"['Read'", " 'Write']"}` — no element
    of which equals `"Write"` — so a `tools:` written as a YAML list made the read-only
    check pass while Write and Bash were granted. Verified against the real parser
    before this helper existed: the intersection was empty and the test was green.
    """
    if isinstance(value, str):
        return {t.strip() for t in value.split(",") if t.strip()}
    if isinstance(value, list):
        return {str(t).strip() for t in value if str(t).strip()}
    raise AssertionError(f"unhandled `tools:` shape {type(value).__name__}: {value!r}")


@pytest.mark.parametrize("name", sorted(_READ_ONLY_AGENTS))
def test_read_only_agents_are_not_granted_write_edit_or_bash(
    name: str, rendered_agents: dict[str, str]
) -> None:
    """The boundary that is actually enforced, asserted per agent.

    CLAUDE.md is explicit that a reviewer's real limit is the ABSENCE of Bash/Write/Edit
    from `tools:` — the frontmatter `permissions:` block was deleted in 0.40.0 precisely
    because it was never enforced. A silent widening here is invisible to every other
    test in the suite.
    """
    block, _rest = _frontmatter(rendered_agents[name])
    granted = _granted_tools(yaml.safe_load(block).get("tools"))

    assert not (granted & {"Write", "Edit", "Bash"}), (
        f"{name} is a read-only agent but its rendered tools grant "
        f"{sorted(granted & {'Write', 'Edit', 'Bash'})}"
    )
