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

**Why the tool-boundary tests below pass the moment they are written** (Phase A.4 of
PLAN-probe-envelope-contract). Five of the six are *characterization* gates: they pin an
invariant that holds today, so no authoring-time RED exists for them. That is legitimate
only with evidence they can go red at all, so each was mutated and observed on
2026-08-22 — not argued:

===================================================  =========================
mutation applied                                     result
===================================================  =========================
`dangerous_grant_violations`: `held != permitted`     RED
  -> `False`
`code-reviewer.md.j2:5` tools += `Bash`               RED
`code-reviewer.md.j2:5` tools -= `Grep`               RED
`_blueprint_agent_names`: comprehension `if False`    RED (empty population)
`_blueprint_agent_names`: += a name render never      RED (blueprint/disk skew)
  writes
`_blueprint_agent_names`: drop a lens agent           RED (lens orphan)
===================================================  =========================

The sixth, `test_the_violation_rule_rejects_a_wrong_population`, is not a
characterization gate — it feeds synthetic violators to the rule and is the arm that
discriminates. `_WRITE_PRIVILEGED` carries the mutation receipt for the set.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from harness_maker.conditional_router import lens_dispatch
from harness_maker.models import Blueprint, InterviewAnswers, Preset, ProjectProfile, Target
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import _ALL_AGENTS, synthesize


@pytest.fixture(scope="module")
def blueprint() -> Blueprint:
    """The synthesizer's OUTPUT. The population tests below read this, not `_ALL_AGENTS`
    — that constant is the synthesizer's input, so asserting on it checks the renderer
    against itself (PLAN-probe-envelope-contract ADR-003)."""
    return synthesize(
        ProjectProfile(),
        InterviewAnswers(preset=Preset.PRODUCTION, targets=[Target.CLAUDE_CODE]),
    )


@pytest.fixture(scope="module")
def render_dir(blueprint: Blueprint, tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("agents-render")
    render(blueprint, out, freeze_time=DEFAULT_FREEZE_TIME)
    return out


@pytest.fixture(scope="module")
def rendered_agents(render_dir: Path) -> dict[str, str]:
    """Keyed by every agent the render actually wrote, so a test iterating a derived
    population can look any of them up."""
    return {p.stem: p.read_text(encoding="utf-8") for p in (render_dir / "agents").glob("*.md")}


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
#
# This used to be enforced through `_READ_ONLY_AGENTS`, a list of the names to CHECK.
# That direction is fail-open: an agent absent from the list — a new one, most likely —
# was checked for nothing beyond a non-empty `tools:`, and so were the four agents that
# legitimately hold write tools. PLAN-probe-envelope-contract ADR-002/003 inverts it.
# The population is now derived from what the blueprint emits, and the only enumerated
# list is the EXCEPTIONS. A new agent is guarded on the day it renders.

#: The dangerous grants. Named once so the allowlist below and the checks agree.
_DANGEROUS = frozenset({"Write", "Edit", "Bash"})

#: The ONLY hand list left, and it holds exceptions rather than subjects, so it fails
#: LOUDLY: an agent missing from it is rejected, not waved through. Values are the
#: dangerous grants each agent may hold — an exact set, so a write-privileged agent
#: silently gaining Bash is caught too.
_WRITE_PRIVILEGED: dict[str, frozenset[str]] = {
    # Writes the implementation during an autoloop iteration.
    "autoloop-coder": frozenset({"Write", "Edit", "Bash"}),
    # The general workflow executor; edits the worktree and runs checks.
    "executor": frozenset({"Write", "Edit", "Bash"}),
    # Runs a whole stage body (wrapup/verify), which writes memory and runs commands.
    "stage-delegate": frozenset({"Write", "Edit", "Bash"}),
    # Read-only in intent, but its 5-gate audit shells out (CVE lookup, secret scan).
    "security-auditor": frozenset({"Bash"}),
}


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


def dangerous_grant_violations(
    grants: dict[str, set[str]], allowlist: dict[str, frozenset[str]]
) -> list[str]:
    """Which agents hold dangerous tools they are not allowed to hold.

    Extracted so the rule can be tested against synthetic input. The render-level tests
    below are characterization gates — they pin an invariant that currently holds, so
    they cannot go red at authoring time. This function can, and
    `test_the_violation_rule_rejects_a_wrong_population` is where it does.
    """
    out: list[str] = []
    for name in sorted(grants):
        held = grants[name] & _DANGEROUS
        permitted = allowlist.get(name, frozenset())
        if held != permitted:
            out.append(
                f"{name}: holds {sorted(held) or 'none'}, permitted {sorted(permitted) or 'none'}"
            )
    return out


def _blueprint_agent_names(blueprint: Blueprint) -> set[str]:
    """The population, taken from what the blueprint emits rather than from a constant.

    ADR-003: `_ALL_AGENTS` is the renderer's own input, so asserting against it would
    check the renderer against itself. This reads its OUTPUT list.
    """
    return {
        entry.path.stem
        for entry in blueprint.files
        if entry.path.suffix == ".md" and entry.path.parent == Path("agents")
    }


def _tools_of(body: str) -> set[str]:
    block, _rest = _frontmatter(body)
    return _granted_tools(yaml.safe_load(block).get("tools"))


# --- the rule, tested against synthetic input (this one CAN go red) ------------------


def test_the_violation_rule_rejects_a_wrong_population() -> None:
    """Discrimination arm for `dangerous_grant_violations`.

    The three render-level gates below all pass against today's tree, so none of them
    demonstrates the rule REJECTS anything. This one does, in all three directions a
    wrong population can be wrong.
    """
    allowlist = {"writer": frozenset({"Write", "Bash"})}

    # An agent outside the allowlist holding a dangerous tool.
    assert dangerous_grant_violations({"reader": {"Read", "Bash"}}, allowlist) == [
        "reader: holds ['Bash'], permitted none"
    ]
    # An allowlisted agent gaining a tool beyond its recorded set.
    assert dangerous_grant_violations({"writer": {"Write", "Edit", "Bash"}}, allowlist) == [
        "writer: holds ['Bash', 'Edit', 'Write'], permitted ['Bash', 'Write']"
    ]
    # An allowlisted agent LOSING one is also a drift the exact-set check reports.
    assert dangerous_grant_violations({"writer": {"Write"}}, allowlist) == [
        "writer: holds ['Write'], permitted ['Bash', 'Write']"
    ]
    # And the clean case stays clean, so the rule is not simply always-report.
    assert dangerous_grant_violations({"reader": {"Read", "Grep"}}, allowlist) == []
    assert dangerous_grant_violations({"writer": {"Write", "Bash", "Read"}}, allowlist) == []


# --- render-level characterization gates ---------------------------------------------


def test_no_agent_grants_write_edit_or_bash_outside_the_allowlist(
    rendered_agents: dict[str, str], blueprint: Blueprint
) -> None:
    """The boundary CLAUDE.md calls the only enforced one, over the whole population.

    Characterization: it holds today. What makes it a gate rather than a fossil is the
    mutation receipt filed against it — deleting the `tools:` line of an agent template
    turns this red.
    """
    population = _blueprint_agent_names(blueprint)
    grants = {name: _tools_of(rendered_agents[name]) for name in population}

    # An agent whose `tools:` is absent inherits every tool the main thread has, and one whose
    # `tools:` is EMPTY declares no boundary at all. The dangerous-grant check below cannot see
    # either: an absent key makes `_tools_of` raise (caught, but with a useless message), and an
    # empty string parses to `set()`, which intersects `_DANGEROUS` to nothing and passes. The
    # gate this file shipped before PLAN-probe-envelope-contract asserted non-emptiness per agent
    # and was deleted with the read-only list; a cross-model reviewer caught the loss.
    empty = sorted(name for name in population if not grants[name])
    assert not empty, (
        f"agents declaring an empty `tools:`: {empty} — an empty tool list is not a boundary, "
        "and an absent one makes the subagent inherit every tool the main thread has"
    )

    # The exception list is only ever consulted BY NAME (`allowlist.get(name, ...)`), so an entry
    # for an agent that no longer renders is never read and never complained about. A stale
    # exception is the one way this fail-closed list can rot silently.
    stale = sorted(set(_WRITE_PRIVILEGED) - population)
    assert not stale, (
        f"`_WRITE_PRIVILEGED` names agents that do not render: {stale} — an exception nothing "
        "consults is an exception nobody can audit"
    )

    violations = dangerous_grant_violations(grants, _WRITE_PRIVILEGED)
    assert not violations, (
        "agent tool grants drifted from the write-privileged allowlist:\n  "
        + "\n  ".join(violations)
        + "\n\nAn agent that legitimately needs write or exec tools belongs in "
        "`_WRITE_PRIVILEGED` with a one-line reason — adding it is the deliberate act "
        "this list exists to record."
    )


def test_review_lens_agents_grant_read_and_grep(rendered_agents: dict[str, str]) -> None:
    """Read+Grep, asserted ONLY where a contract requires them.

    There is no universal minimum: a future agent may legitimately need neither. The
    population is the review stage's own dispatch table, whose agents are told to follow
    a defect to its cause outside the diff — a review is unapprovable without them.
    """
    lens_agents = {d["agent"] for d in lens_dispatch("Production")}
    # Floor: an empty dispatch table would make the difference below empty too, and this test
    # plus `test_every_review_lens_agent_actually_renders` would both pass over nothing.
    assert lens_agents, "lens_dispatch('Production') returned no agents — this check is vacuous"
    missing = {
        name: sorted({"Read", "Grep"} - _tools_of(rendered_agents[name]))
        for name in sorted(lens_agents)
        if {"Read", "Grep"} - _tools_of(rendered_agents[name])
    }
    assert not missing, f"review lens agents missing read tools: {missing}"


# --- non-vacuity, against independent sources ----------------------------------------
#
# The previous revision of this plan compared the derived population against its own
# derivation (`X == X`), which passes on an empty set and is therefore weaker than the
# count floor it replaced. Each arm below compares two DIFFERENT producers.


def test_the_blueprint_agent_set_matches_what_render_wrote(
    blueprint: Blueprint, render_dir: Path
) -> None:
    """Blueprint says what to emit; render writes it. Two producers, compared."""
    planned = _blueprint_agent_names(blueprint)
    written = {p.stem for p in (render_dir / "agents").glob("*.md")}
    assert planned == written, (
        f"blueprint planned {sorted(planned - written)} that render did not write, and "
        f"render wrote {sorted(written - planned)} the blueprint did not plan"
    )


def test_the_agent_population_is_not_empty(blueprint: Blueprint) -> None:
    """The one thing `X == X` could never say — and the shape that makes a derived
    population silently stop guarding anything."""
    assert _blueprint_agent_names(blueprint), (
        "no agents derived from the blueprint — every gate above just became vacuous"
    )


def test_every_review_lens_agent_actually_renders(blueprint: Blueprint) -> None:
    """A lens dispatching to an agent that renders nowhere is a live hazard, not a
    hypothetical: `trajectory-monitor` has a template with `tools:` and is deliberately
    absent from the render, so the two sets are genuinely independent."""
    lens_agents = {d["agent"] for d in lens_dispatch("Production")}
    orphans = sorted(lens_agents - _blueprint_agent_names(blueprint))
    assert not orphans, f"review dispatches to agents that render nowhere: {orphans}"
