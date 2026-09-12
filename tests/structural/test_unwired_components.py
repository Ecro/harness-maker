"""Phase 6 of PLAN-token-efficiency-autopilot-ux-speed — AC-014.

A component that ships into every harness and is invoked by nothing costs tokens and reads as a
capability. Three were measured: `context_lint.lint` (a Python function with no production caller),
`consensus-arbiter` (an agent rendered into every harness and dispatched nowhere), and the `verify`
stage's `stage-delegate` handoff (present in the template, absent from every default render).

**Each must be WIRED or DECLARED**, and the three arms below are three different kinds of evidence
because the three components are three different kinds of thing — a function, an asset, a template
branch. A single arm covering all three would have to be so loose that none of them is really
checked.

**The agent arm DISCOVERS its members.** It renders a harness and asks which rendered agent names
appear nowhere in any rendered command or skill; whatever it finds must be declared with a reason.
That is what the AC means by "it holds for a component added later", and it is not decoration: run
against today's tree it found a **fourth** member the SPEC never named (`security-auditor`), which a
hand list transcribed from the SPEC would have missed by construction.

Why "appears nowhere" rather than "no `subagent_type=` literal": the lens fan-out dispatches through
a loop over `d.agent`, so no reviewer's name appears literally anywhere. Using the literal as the
criterion reports seven false members including `code-reviewer`'s peers. A name that appears in some
rendered prose is at least reachable by an instruction; a name that appears in none is not.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from harness_maker import interview as iv
from harness_maker.models import (
    DelegationConfig,
    InterviewAnswers,
    Preset,
    ProjectProfile,
    Target,
)
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize

_ROOT = Path(__file__).parents[2]
_SRC = _ROOT / "src" / "harness_maker"

#: Rendered agents that no rendered command or skill names, each with the reason its absence is a
#: decision. A new entry here is a claim a human typed; a new *undeclared* one fails the test.
_UNWIRED_DECLARED: dict[str, str] = {
    "consensus-arbiter": (
        "Rendered but never dispatched. `/hm:review` Step 4 reconciles findings inline — the "
        "surface-match + reasoning-alignment filter is prose over the merged finding list, and "
        "`conditional_router.scope_aware_consensus` supplies the k-of-N threshold. The agent is a "
        "heavier alternative that pays off only on `--with-reviewers` fan-outs beyond the four "
        "lenses a preset dispatches, and wiring it would change the review flow. Declared as a "
        "deliberate hold, not a gap: docs/HOW-IT-WORKS.md §11.8 describes the METHOD, which is "
        "implemented, rather than the agent, which is not."
    ),
    "security-auditor": (
        "Rendered but never dispatched — found by this test's discovery arm, unnamed by the SPEC. "
        "The 5-gate audit it performs is `/hm:review`'s `security` lens plus the `security-"
        "reviewer` agent on the normal path; the auditor is the deep, Bash-carrying variant kept "
        "for an explicit opt-in that no rendered command currently offers. Declared so the next "
        "reader sees a decision instead of an oversight."
    ),
    "stage-delegate": (
        "Absent from a DEFAULT render only. `verify.md.j2` gates Step 0.5 on "
        "`'verify' in config.delegation.stages`, so this is opt-in configuration rather than dead "
        "surface — proved by `test_ac_014_verify_delegation_is_config_gated`, which renders both "
        "arms and watches the handoff appear."
    ),
}


@pytest.fixture(scope="module")
def rendered(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("prod")
    render(
        synthesize(
            ProjectProfile(),
            InterviewAnswers(
                preset=Preset.PRODUCTION,
                targets=[Target.CLAUDE_CODE],
                skills={
                    "installed": list(iv._ALL_SKILLS),
                    "enabled": list(iv._PROD_ENABLED_SKILLS),
                },
                reviewers={
                    "installed": list(iv._ALL_REVIEWERS),
                    "enabled": list(iv._PROD_ENABLED_REVIEWERS),
                },
            ),
        ),
        out,
        freeze_time=DEFAULT_FREEZE_TIME,
    )
    return out


def _prose_corpus(out: Path) -> str:
    return "\n".join(
        p.read_text(encoding="utf-8")
        for p in [*(out / "commands").rglob("*.md"), *(out / "skills").rglob("*.md")]
    )


def test_ac_014_every_unwired_agent_is_declared(rendered: Path) -> None:
    """Discovery, then declaration. Both directions, so the table cannot rot in either.

    A stale entry matters as much as a missing one: an agent that later gets wired should drop out
    of the table, otherwise the table becomes a list of things that used to be true — which is the
    defect class this whole unit is about.
    """
    agents = {p.stem for p in (rendered / "agents").glob("*.md")}
    assert agents, "the render produced no agents, so this test would pass vacuously"

    corpus = _prose_corpus(rendered)
    unwired = {name for name in agents if name not in corpus}

    undeclared = sorted(unwired - set(_UNWIRED_DECLARED))
    assert undeclared == [], (
        f"rendered agents that no command or skill names, and that nothing declares: {undeclared}. "
        "Wire them, or add an entry to _UNWIRED_DECLARED saying why the absence is intended."
    )

    stale = sorted(set(_UNWIRED_DECLARED) - unwired)
    assert stale == [], (
        f"_UNWIRED_DECLARED still claims these are unwired, but the render names them: {stale}"
    )

    # A word-count floor on the reasons was tried and dropped: today's entries were authored in the
    # same commit as the assertion so it could not fail on arrival, and a future 20-word rubber
    # stamp satisfies it exactly. It decided nothing (A.5 round 1, ADVISORY-4).


def _module_calls(tree: ast.Module) -> set[str]:
    """Every simple name invoked anywhere in a module — the crude reachability oracle below."""
    out: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Attribute):
            out.add(func.attr)
        elif isinstance(func, ast.Name):
            out.add(func.id)
    return out


def _enclosing_function(tree: ast.Module, lineno: int) -> str | None:
    best: tuple[int, str] | None = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            end = node.end_lineno or node.lineno
            if node.lineno <= lineno <= end and (best is None or node.lineno > best[0]):
                best = (node.lineno, node.name)
    return best[1] if best else None


def test_ac_014_context_lint_has_a_production_caller() -> None:
    """A call site that is itself REACHED — two hops, because one hop was not enough.

    First attempt walked for any `Call` named `lint` outside `context_lint.py`. I mutated the
    implementation to check it, and **it did not go red**: the only such call lives inside
    `_warn_context_lint`, so deleting the line that *invokes that helper* left the gate green. A
    `lint` call inside a function nobody calls is precisely the defect AC-014 names, reproduced
    inside AC-014's own gate. Recorded rather than quietly repaired.

    So: (1) the callee must be `context_lint.lint` specifically, not any `lint`; (2) the function
    enclosing it must itself be invoked somewhere in shipped code. Two hops is still not full
    reachability — a chain of three uncalled helpers would pass — but it kills the mutation that
    killed the first version, which is the bar a gate has to clear to be one.
    """
    hits: list[tuple[Path, ast.Module, int]] = []
    for path in sorted(_SRC.rglob("*.py")):
        if path.name == "context_lint.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            is_context_lint_lint = (
                isinstance(func, ast.Attribute)
                and func.attr == "lint"
                and isinstance(func.value, ast.Name)
                and func.value.id == "context_lint"
            )
            if is_context_lint_lint:
                hits.append((path, tree, node.lineno))

    assert hits, (
        "context_lint.lint has no call site in src/harness_maker/ — the linter's thresholds are "
        "configured, documented and never applied to anything"
    )

    all_calls: set[str] = set()
    for path in sorted(_SRC.rglob("*.py")):
        all_calls |= _module_calls(ast.parse(path.read_text(encoding="utf-8"), filename=str(path)))

    reached = [
        f"{p.relative_to(_ROOT)}:{lineno}"
        for p, tree, lineno in hits
        if (fn := _enclosing_function(tree, lineno)) is not None and fn in all_calls
    ]
    assert reached, (
        "every context_lint.lint call sits inside a function that nothing in src/ invokes — "
        f"the linter is wired to a dead branch (call sites: "
        f"{[f'{p.relative_to(_ROOT)}:{ln}' for p, _t, ln in hits]})"
    )


def test_ac_014_the_linter_sees_every_asset_class(rendered: Path) -> None:
    """Wired is not enough — the caller must reach something. Measured: 1 + 15 + 11 of 59 written.

    `_warn_context_lint` classifies by output path and skips `"other"`. A future move of `agents/`
    or a rename of `SKILL.md` would silently classify every file as `"other"`, and the linter would
    keep being *called* while checking nothing — `runtime-env-gate-dead-on-arrival` with a green
    call-site test above it. Zero warnings on this repo is a real all-within-band result (0.45.0
    raised the agent and skill bands to 300); this arm is what makes that reading legitimate rather
    than indistinguishable from a dead loop.
    """
    from harness_maker.render import _context_lint_asset_type

    agent_paths = sorted((rendered / "agents").glob("*.md"))
    skill_paths = sorted((rendered / "skills").rglob("SKILL.md"))
    assert agent_paths, "the render produced no agents to classify"
    assert skill_paths, "the render produced no skills to classify"

    classes: dict[str, int] = {}
    for path in [*agent_paths, *skill_paths]:
        kind = _context_lint_asset_type(path.relative_to(rendered))
        classes[kind] = classes.get(kind, 0) + 1

    # Counted against the globbed set rather than against a floor: `>= 10` agents passed a 15 -> 10
    # render regression silently, and neither number traced to the SPEC (A.5 round 1, ADVISORY-3).
    assert classes.get("agent", 0) == len(agent_paths), (
        f"{len(agent_paths) - classes.get('agent', 0)} agent(s) did not classify as lintable: "
        f"{classes}"
    )
    assert classes.get("skill", 0) == len(skill_paths), (
        f"{len(skill_paths) - classes.get('skill', 0)} skill(s) did not classify as lintable: "
        f"{classes}"
    )
    assert "other" not in classes, (
        f"an agent or skill fell through to the no-limit class: {classes}"
    )
    assert _context_lint_asset_type(Path("CLAUDE.md")) == "CLAUDE.md"
    assert _context_lint_asset_type(Path("AGENTS.md")) == "AGENTS.md"


def test_ac_014_the_linter_reaches_the_codex_half_of_the_render(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """`AGENTS.md` must be lintable from the CALLER, not just from the classifier.

    Review finding P1-5: `_warn_context_lint` filtered `written` with `relative_to(target_dir)`
    and `continue`d on `ValueError`, so every asset `resolve_output_path` writes to
    `target_dir.parent` — `AGENTS.md`, `.agents/`, `.codex/`, `.cursor/` — was dropped before
    classification. 22 assets on a codex render, and the `AGENTS.md` rows in `THRESHOLDS` were
    unreachable in production while `test_ac_014_the_linter_sees_every_asset_class` asserted the
    classifier's `AGENTS.md` arm directly and stayed green. A pure-function assertion cannot see a
    caller that never hands it that input.

    Also pins the deliberate silence on `.agents/skills/**`: it mirrors assets already linted
    under `.claude/`, and the `hm-<stage>` entries are stage-command bodies whose size
    `_ATOMIC_RATCHET` governs (measured: `hm-review` 1120 lines). Classifying them would emit
    eight duplicate warnings per render that nobody can act on from there.
    """
    from harness_maker import context_lint

    monkeypatch.setattr(
        context_lint, "THRESHOLDS", dict.fromkeys(context_lint.THRESHOLDS, 5), raising=True
    )

    with caplog.at_level("WARNING", logger="harness_maker.render"):
        render(
            synthesize(
                ProjectProfile(),
                InterviewAnswers(
                    preset=Preset.PRODUCTION, targets=[Target.CLAUDE_CODE, Target.CODEX]
                ),
            ),
            tmp_path / ".claude",
            freeze_time=DEFAULT_FREEZE_TIME,
        )

    emitted = [r.getMessage() for r in caplog.records if "[context-lint]" in r.getMessage()]
    assert any("AGENTS.md" in m for m in emitted), (
        "AGENTS.md was never linted, so its threshold rows are unreachable from the only "
        f"production caller (records: {len(emitted)})"
    )
    assert not [m for m in emitted if ".agents/skills" in m], (
        "the Codex skill mirror is being linted, which duplicates every warning its "
        "`.claude/` twin already carries"
    )


def test_ac_014_the_linter_emits_on_an_over_threshold_asset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """The POSITIVE observation. A call-site test cannot decide this, and A.5 round 1 proved it.

    Four mutations keep every other AC-014 arm green while the warning never reaches a user:
    discard `context_lint.lint`'s return value, demote `logger.warning` to `logger.debug`, return
    early from `_warn_context_lint`, or delete its single invocation (the last one is caught by the
    two-hop arm above; the first three are not). This drives the whole wired path — `render()` with
    `dry_run=False` — against thresholds low enough that a real asset must trip one, and asserts the
    record.

    Thresholds are monkeypatched rather than an oversized asset being constructed, because the
    subject is the WIRING, and a synthetic 600-line agent would test `context_lint.lint`, which
    `tests/unit/test_context_lint.py` already owns. `THRESHOLDS`' unit stays lines (ADR-004) — this
    lowers values, never the unit.
    """
    from harness_maker import context_lint

    monkeypatch.setattr(
        context_lint, "THRESHOLDS", dict.fromkeys(context_lint.THRESHOLDS, 5), raising=True
    )

    with caplog.at_level("WARNING", logger="harness_maker.render"):
        render(
            synthesize(
                ProjectProfile(),
                InterviewAnswers(preset=Preset.PRODUCTION, targets=[Target.CLAUDE_CODE]),
            ),
            tmp_path,
            freeze_time=DEFAULT_FREEZE_TIME,
        )

    emitted = [r.getMessage() for r in caplog.records if "[context-lint]" in r.getMessage()]
    assert emitted, (
        "render() emitted no [context-lint] record with every threshold at 5 lines — the linter is "
        "called but its output reaches nobody"
    )
    assert any("SKILL.md" in m or "agents/" in m or "CLAUDE.md" in m for m in emitted), (
        "the records name no lintable asset, so the classifier fed the linter nothing: "
        f"{emitted[:3]}"
    )


def test_ac_014_verify_delegation_is_config_gated(tmp_path: Path) -> None:
    """Wired-or-gated for a template branch: render BOTH arms and watch the handoff move.

    Asserting only that the template contains an `{% if %}` would pass on a condition that can
    never be true. The differential is the evidence: with `delegation.stages` carrying `verify` the
    rendered command names `stage-delegate`; without it, it does not.
    """
    # Three arms, not two. The third is a SHIPPED defect class, not a hypothetical: `models.py`
    # records that ADR-011 rejected `wrapup.delegate` because an earlier phase used one key to gate
    # a different stage — "a key named for one stage silently controlling another". With only
    # `["verify"]` and `[]`, a regression from `'verify' in config.delegation.stages` to a bare
    # `{% if config.delegation.stages %}` passes every assertion (A.5 round 1, ADVISORY-1).
    renders: dict[str, str] = {}
    for label, stages in (("verify", ["verify"]), ("off", []), ("wrapup", ["wrapup"])):
        out = tmp_path / label
        render(
            synthesize(
                ProjectProfile(),
                InterviewAnswers(
                    preset=Preset.PRODUCTION,
                    targets=[Target.CLAUDE_CODE],
                    delegation=DelegationConfig(stages=stages),
                ),
            ),
            out,
            freeze_time=DEFAULT_FREEZE_TIME,
        )
        renders[label] = (out / "commands" / "hm" / "verify.md").read_text(encoding="utf-8")

    assert "stage-delegate" not in renders["wrapup"], (
        "`delegation.stages: [wrapup]` renders verify's handoff — the gate keys on the presence of "
        "the list rather than on this stage's name, which is the cross-stage collision ADR-011 "
        "rejected once already"
    )

    assert "stage-delegate" in renders["verify"], (
        "delegation.stages includes `verify` and the rendered command still does not name "
        "`stage-delegate` — the gate's true branch is unreachable, so the absence is not a "
        "configuration choice"
    )
    assert "stage-delegate" not in renders["off"], (
        "the handoff renders with delegation off, so it is not gated at all"
    )
    assert re.search(
        r"\{%\s*if\s+config\.delegation\b",
        (_SRC / "templates" / "stages" / "verify.md.j2").read_text(encoding="utf-8"),
    ), "the gate moved out of verify.md.j2 — update this test's anchor"
