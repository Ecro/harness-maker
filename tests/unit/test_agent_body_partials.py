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
    # Re-pinned 2026-08-20 (review-scope-and-oracle). FIVE entries — exactly the agents that
    # include `_partials/hard_rules.md.j2`, whose `Diff scope` rule was rewritten from location
    # ("outside the changed lines") to causation ("does the change make it reachable"), and lost
    # the `out_of_diff: true` marker. That marker had no consumer anywhere in `src/`, `tests/` or
    # any rendered harness — the reviewers were told to emit it into a void. The rewrite also
    # ends a contradiction inside these same bodies: twelve lines above the rule they are told to
    # "walk the runtime path the changed code triggers … Logic bugs hide where the patch doesn't
    # touch", which the old rule then forbade them to report on. Pre-bump hashes in git history.
    # Re-pinned 2026-07-30 (PLAN-second-opinion-acceptance-gate). SIX entries moved for TWO
    # reasons, both intended: the five reviewers because `_partials/finding_schema.md.j2` gained
    # the note that `id` is harness-assigned and must NOT be emitted by a reviewer (an
    # LLM-generated id differs per run, which defeats the stability the id exists for), and
    # `consensus-arbiter` because its 2-arg `scope_aware_consensus(findings, reviewer_scopes)`
    # call was corrected to the real 1-arg signature. `code-verifier` gained a whole second mode
    # in the same task and does NOT appear here — it carries no sha pin.
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
    # PLAN-probe-envelope-contract Phase 2: these four moved BACK, because the
    # `return_envelope.md.j2` include they gained in PLAN-bench-study-adoption Phase 4 was
    # removed with the partial itself. Still EXACTLY four — the agents
    # `conditional_router.LENS_DISPATCH` names as backing the seven lenses — and that the same
    # four moved, and only those four, is the check worth making: a fifth would mean the
    # deletion reached past the include.
    "code-reviewer": "d09023357e53929d9eee5059ecb624a0f502115da3f1dda7b00c4252de2e5169",
    "concurrency-reviewer": "ffc8b5f6bcc43dd33fc6353e87797216a5c8eb39494e8b762beaab50f31ff359",
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
    "consensus-arbiter": "f7497cebbbde53b777c264a596619c4f436534a0b471227f9baadcff779a67df",
    # executor: re-pinned 2026-06-03 (PLAN-techspec-audit F61). The description
    # + body claimed a runtime-enforced "never writes to repo root" boundary that
    # Claude Code does NOT enforce (subagent-frontmatter permissions are not
    # enforced — see CLAUDE.md §보안/권한). Reworded to "by convention, prompt-
    # level guidance, not runtime-enforced". Pre-bump hash in git history.
    "executor": "0a4a5e34f5b7d985eab1b0b8b2ee79d898d3d95ddd4d68eea051536939e96874",
    "performance-reviewer": "869fa3131ffa6cae4be84232deca0174df7d9cd973cc203499f13f75977771e6",
    "plan-validator": "2116a5ce4fb8053c0a8c921f2a1e2c022ea5099f488e8bc315a6a87b097ec36b",
    "security-auditor": "51a11902b9f56b9ebb0e0103e0d2047a64d1a218898d6cedc229a1a43fed2f53",
    # `return_envelope` include removed — see the code-reviewer note above.
    "security-reviewer": "aadcaf6606ce6b7483f4994f190c919cfba8e9a32d987a4a046e2d9491d19c0e",
    # stuck re-pinned 2026-08-10 (PLAN-multi-lens-review-round, review round 4). `stuck` is the
    # agent A.5 escalates to, and its incoming brief still described the budget as "2 attempts"
    # after the stage renamed the unit to rounds — three lens dispatches now share one round, so
    # the old wording named a unit the stage no longer uses. Its "last 3 reviewer outputs"
    # heuristic also silently changed meaning: three outputs are now ONE round, not three, so the
    # brief says to read across rounds when history is needed. Found by review, out of the diff.
    # Body change outside the codex conditional. Pre-bump hash in git history.
    # stuck re-pinned 2026-08-17 (stuck-dispatch). Step 5 told this agent to WRITE the escalation
    # note to `.claude/memory/escalations/…` and its Hard Rules referenced "the escalation note
    # path" — but its `tools:` grant is `Read, Grep, Glob`, so the write could never execute on
    # Claude Code, and nothing in this repo has ever read that directory. The instruction was
    # inert for as long as no stage dispatched this agent; wiring `/hm:execute`'s blocker path to
    # it made the contradiction load-bearing, because the stage was then told to surface a note
    # PATH that could not exist. Step 5 now returns the note inline. Found by four review lenses
    # independently, none of which was looking at this file. Body change outside the codex
    # conditional. Pre-bump hash in git history.
    "stuck": "2ed15a8cdadeb5b8d6d61b84ba0855b314d786c352618228a4f63984d0c1a4b7",
    # test-reviewer re-pinned 2026-08-10 (PLAN-multi-lens-review-round, review round 2). Two
    # rules changed, both because Phase A.5 now runs three lens-scoped instances of this agent:
    # (a) `passing_tests[]` was declared FROZEN, which conflicted with the caller's merge rule —
    # the intersection of three lenses' bare function names cannot identify a test, so the list
    # is now advisory and the retry's scope is `blocking_issues[]` + `scenarios_missing[]`;
    # (b) the banned-patterns Hard Rule said an out-of-category violation should "downgrade to a
    # `suggestion`", but the mandated JSON has NO suggestions field — so such a finding was
    # DELETED and `overall_assessment` then read PASS over a defect the reviewer had found. It
    # now routes to a field the schema has (scenarios_missing / per_scenario.quality=FAIL /
    # the closest banned pattern). Body change outside the codex conditional. Pre-bump hash in
    # git history.
    # `return_envelope` include removed — see the code-reviewer note above.
    # test-reviewer re-pinned 2026-08-23 (PLAN-a5-duplicate-coverage-block). ONE rule changed:
    # the banned-patterns Hard Rule routed "a scenario covered twice" to a blocking
    # `per_scenario` FAIL, which contradicted this same body's rubric section 1 ("at least one
    # dedicated test function"). The qualifier that reconciles them — duplication is duplication
    # of one OBSERVABLE — lived only in `execute.md.j2`'s Phase A authoring rule, which this agent
    # never reads, so N tests asserting N different observables under one scenario ID blocked
    # Phase A.5. Observed live at 0.54.0 on a consuming project: five tests, five observables, two
    # rounds blocked. The bullet now splits into two predicates — same-observable duplication
    # FAILs, and a test aimed at a different scenario FAILs "regardless of observable" (banned
    # pattern 5 is a naming defect, not a duplication one), so narrowing opens no loophole.
    # Section 1 is unchanged and load-bearing. Body change outside the codex conditional.
    # Pre-bump hash in git history.
    # Re-pinned again in review round 2 of the same task: cross-model review found the new
    # clause said such tests "must PASS" unconditionally, which targets the same
    # `per_scenario.quality` field the banned-patterns rule forces to FAIL — two rules with
    # opposite verdicts over a tautological test that happens to assert a different
    # observable. It now says they may not FAIL *for that reason* and are still judged
    # against the banned patterns, which the clause never overrides.
    "test-reviewer": "0a3978bcd2cb69680a67bdba70d6ce91b07fe86c3ef17e6df6bf6b7cf3f994df",
    "ux-reviewer": "b6e31a5a45013208a80f0c17eca4e720add647f6d9a386027ae1a57b5d347ebc",
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
