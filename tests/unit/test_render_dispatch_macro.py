"""The single dispatch macro renders each runtime's own sub-agent vocabulary.

Phase 1 of PLAN-codex-lens-dispatch (ADR-002/003/006). Codex has no `Task` tool; it exposes
`spawn_agent`. Rendering `Task(` into a Codex skill ships an instruction the runtime cannot
execute — measured 36 occurrences across 9 rendered Codex files, and the observable symptom was
a Codex `/hm:review` that wrote zero lens result files and blocked approval forever.

The load-bearing test here is `test_omitting_is_codex_raises`: a macro that read `is_codex` from
Jinja context instead of taking it as a parameter would pass every other test in this file and
still take the Claude arm in every production render, because `{% import %}` does not pass caller
context unless imported `with context`. That is the exact defect class this work exists to close,
so it is asserted rather than assumed.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path

import pytest
from jinja2 import UndefinedError

from harness_maker.conditional_router import LENS_DISPATCH, lens_dispatch
from harness_maker.models import InterviewAnswers, Preset, ProjectProfile, Target
from harness_maker.render import DEFAULT_FREEZE_TIME, _make_env, render
from harness_maker.synthesize import synthesize

_PARTIAL = "agents/_partials/dispatch.md.j2"
_FIXTURES = Path(__file__).parents[1] / "fixtures"
_INTENT_MARK = "explicitly authorises sub-agent delegation"


def _render(body: str, **ctx: object) -> str:
    """Render through a real `{% import %}` of the shipped partial, not a direct macro call.

    Calling the macro in isolation cannot observe a context-propagation defect; going through
    the loader the way every production template does is the whole point.
    """
    env = _make_env()
    return env.from_string("{% import '" + _PARTIAL + "' as d %}" + body).render(**ctx)


def test_codex_arm_emits_spawn_agent() -> None:
    out = _render(
        '{{ d.dispatch(is_codex, "code-reviewer", "lens design: s", "Your lens: design") }}',
        is_codex=True,
    )
    assert 'spawn_agent(agent_type="code-reviewer", message="Your lens: design")' in out
    assert "Task(" not in out


def test_claude_arm_emits_task() -> None:
    out = _render(
        '{{ d.dispatch(is_codex, "code-reviewer", "lens design: s", "Your lens: design") }}',
        is_codex=False,
    )
    assert 'Task(subagent_type="code-reviewer", description="lens design: s"' in out
    assert 'prompt="Your lens: design")' in out
    assert "spawn_agent" not in out


def test_intent_precedes_literal_on_codex_only() -> None:
    """ADR-002: the two macros' contributions are DISJOINT and the Claude arm carries no intent.

    **Ordering is deliberately NOT asserted here, and a green Phase 1 is not evidence for it.**
    Given two markers each emitted by exactly one macro, any `index(a) < index(b)` comparison
    over a string this test itself concatenates in that order is true for every implementation
    where both markers appear at all — and both are asserted separately below. Round 1's version
    was circular through a shared substring; removing that left the composition circular.
    The real property — intent once above each dispatch block — is a CALL-SITE property, which
    Phase 1's Scope (out) excludes and PLAN Phase 2 exit criterion 4 owns.
    """
    call = 'spawn_agent(agent_type="code-reviewer"'
    intro_only = _render("{{ d.dispatch_intro(is_codex) }}", is_codex=True)
    assert _INTENT_MARK in intro_only
    assert call not in intro_only

    # `dispatch()` alone carries no intent — the two macros' contributions stay distinguishable.
    literal_only = _render('{{ d.dispatch(is_codex, "code-reviewer", "d", "b") }}', is_codex=True)
    assert _INTENT_MARK not in literal_only
    assert call in literal_only
    assert "Task(" not in literal_only

    claude = _render("{{ d.dispatch_intro(is_codex) }}", is_codex=False)
    assert _INTENT_MARK not in claude
    assert "`Task` tool" in claude


def test_omitting_is_codex_raises() -> None:
    """Loud failure, not a silent Claude arm — the whole reason the flag is a parameter.

    Two distinct cases, and the FIRST is the one that occurs at a call site: the argument is
    genuinely absent (arity), not present-but-undefined. A macro declared
    `dispatch(agent, description, brief, is_codex=false)` still raises on the undefined-variable
    case while silently taking the Claude arm for every caller that forgets the flag — which is
    verbatim the `is_codex`-hardcoded-`False` defect ADR-003 exists to make impossible.
    """
    with pytest.raises(UndefinedError):
        _render('{{ d.dispatch("code-reviewer", "d", "b") }}')
    with pytest.raises(UndefinedError):
        _render("{{ d.dispatch_intro() }}")

    # Weaker second case: passed, but unresolved at the call site.
    with pytest.raises(UndefinedError):
        _render('{{ d.dispatch(missing_flag, "code-reviewer", "d", "b") }}')
    with pytest.raises(UndefinedError):
        _render("{{ d.dispatch_intro(missing_flag) }}")


@pytest.mark.parametrize("is_codex", [True, False])
def test_brief_reaches_the_argument_verbatim(is_codex: bool) -> None:
    """Both arms, and with a brief that can actually expose the seam ADR-003 names.

    No string in `LENS_DISPATCH` contains a quote, a backslash or a newline, and `_make_env`
    sets `autoescape=False` — so a real brief passes through `{{ brief|e }}`, `{{ brief|tojson }}`
    and `{{ brief|replace('\\n\\n',' ') }}` unchanged. Those are live authoring mistakes, and the
    hazard ADR-003 states is the `\\n\\n` separator being mangled, which silently collapses four
    lenses into one voice. So the adversarial literal is the test and the real brief is the
    regression guard.

    **The `"` character is deliberately absent from the hostile literal.** The macro interpolates
    raw into a quoted argument, so a brief containing `"` produces `message="… " …"` — and
    asserting that byte-verbatim would pin MALFORMED output as the contract and make the correct
    remedy (escaping) read as a regression. No brief in `LENS_DISPATCH` contains a quote, so the
    case is latent; the policy is an open decision recorded in the PLAN, not something this test
    gets to settle by accident.
    """
    # NO literal newline: the macro emits a one-line call, and `test_multi_lens_a5`
    # (contiguity) plus the live test's line-anchored regex both require that. Asserting a
    # newline-bearing brief round-trips verbatim would pin a MULTI-LINE call as correct —
    # blessing output two other gates reject. The `\\n\\n` ADR-003 names is the two-character
    # ESCAPE the call sites concatenate, which is what this exercises.
    hostile = "has a \\ backslash, an & amp and a \\n\\n escaped separator"
    for brief in (lens_dispatch("Production")[0]["brief"], hostile):
        out = _render(
            '{{ d.dispatch(is_codex, "code-reviewer", "d", brief) }}',
            is_codex=is_codex,
            brief=brief,
        )
        # Argument POSITION, not bare containment: a macro that escapes `message=` while echoing
        # the brief verbatim in a prose fallback satisfies `brief in out` and still hands the
        # runtime a mangled argument.
        arg = f'message="{brief}")' if is_codex else f'prompt="{brief}")'
        assert arg in out, f"brief mangled on the {'codex' if is_codex else 'claude'} arm"


def test_lens_briefs_baseline_covers_every_dispatched_lens() -> None:
    """ADR-006 + T9: all seven, from `conditional_router.LENS_DISPATCH` — not four, not a template.

    The briefs exist only in `conditional_router.py`; `review.md.j2` interpolates `{{ d.brief }}`
    and contains none of the text. And the three domain briefs traverse the same macro quoting
    seam as the four core ones, so a fixture scoped to the core four would let a quoting defect
    on `security` pass Phase 2 unnoticed.
    """
    baseline = json.loads((_FIXTURES / "lens_briefs_baseline.json").read_text(encoding="utf-8"))
    assert set(baseline) == set(LENS_DISPATCH)
    assert len(baseline) == 7
    for lens, (_agent, brief) in LENS_DISPATCH.items():
        assert baseline[lens] == brief


def test_claude_arm_baseline_shape_is_pinned() -> None:
    """A SHRUNKEN capture is self-approving in exactly the way an empty one is.

    Non-emptiness is not the property. The generator has already hit two silent-truncation
    defect — a `target_dir` misread that wrote the Codex half outside the scanned root — which
    yields a partial, perfectly truthy baseline. (The first diagnosis blamed `Path.rglob` for
    skipping dotted paths; it does not, and that wrong explanation reached three files.)
    So the shape is pinned: both presets, all three markers, exact counts.
    A regeneration that dropped a preset, lost a marker, or ran AFTER Phases 2-3 migrated the
    call sites fails here as a visible diff instead of quietly becoming the new baseline.
    """
    baseline = json.loads((_FIXTURES / "claude_arm_baseline.json").read_text(encoding="utf-8"))

    # STRUCTURAL ANCHOR FIRST, counts second. Every integer below is readable off the artifact
    # itself, so had either truncation defect been live at capture time the author would simply
    # have pinned the smaller numbers and this test would be green over exactly the fixture it
    # exists to reject. These two path assertions are not: both are named by the PLAN's own
    # affected-components table, and both would have gone RED under the `target_dir` misread
    # (the Codex half written outside the scan root), which is the defect that actually occurred.
    for preset in ("Side", "Production"):
        assert f"{preset}::.agents/skills/hm-review/SKILL.md" in baseline
        assert f"{preset}::.claude/commands/hm/review.md" in baseline

    assert len(baseline) == 60
    prefixes = {key.split("::", 1)[0] for key in baseline}
    assert prefixes == {"Side", "Production"}
    assert sum(key.startswith("Side::") for key in baseline) == 30

    lines = [line for group in baseline.values() for line in group]
    assert len(lines) == 296
    counts = {
        marker: sum(marker in line for line in lines)
        for marker in ("Task(subagent_type=", "AskUserQuestion", "Skill(")
    }
    assert counts == {"Task(subagent_type=": 118, "AskUserQuestion": 146, "Skill(": 32}


# ---------------------------------------------------------------------------
# The fixtures above are only checked against THEMSELVES. These two check them
# against a render, which is the property PLAN Phase 2 exit criteria 2 and 5 name
# and the only committed mitigation for R2 ("the macro mangles a core-lens brief,
# collapsing four lenses into one voice"). Review round 1 found both fixtures inert:
# four independent voices reported that nothing compared them to anything, so the
# invariant rested on a one-off manual run recorded in prose. These are that run,
# committed.
# ---------------------------------------------------------------------------

_MARKERS = ("Task(subagent_type=", "AskUserQuestion", "Skill(")
_LENS_LINE = re.compile(
    r'(?:spawn_agent\(agent_type|Task\(subagent_type)="[^"]+".*Your lens: (.+?)"\)'
)

#: The ONLY Claude-arm line the migration legitimately removed: `second-opinion-gate`'s
#: dispatch was written across two physical lines, and the macro emits one. Its payload is
#: preserved — the single line carries the same `description=` and `prompt=`. Measured: the
#: whole baseline has exactly these two entries (one per preset) unaccounted for, and a third
#: appearing here means a Claude dispatch was actually lost.
_COLLAPSED_MULTILINE = {'Task(subagent_type="code-verifier", description="Mode B PIDA: <slug>",'}


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _render_all(preset: Preset) -> dict[str, str]:
    blueprint = synthesize(
        ProjectProfile(),
        InterviewAnswers(preset=preset, targets=[Target.CLAUDE_CODE, Target.CODEX]),
    )
    with tempfile.TemporaryDirectory() as td:
        # `target_dir` is the `.claude` dir; Codex output goes to its PARENT.
        root = Path(td)
        render(blueprint, root / ".claude", freeze_time=DEFAULT_FREEZE_TIME)
        out: dict[str, str] = {}
        for walk_root, _dirs, names in os.walk(root):
            for name in names:
                f = Path(walk_root) / name
                out[str(f.relative_to(root))] = f.read_text(encoding="utf-8", errors="replace")
        return out


@pytest.mark.parametrize("preset", [Preset.SIDE, Preset.PRODUCTION])
def test_rendered_lens_briefs_match_the_baseline_on_both_arms(preset: Preset) -> None:
    """R2's actual guard: the brief that REACHES the dispatch argument, not the constant.

    `test_lens_briefs_baseline_covers_every_dispatched_lens` compares the fixture to
    `LENS_DISPATCH` — generator output against generator input, which says nothing about
    rendering. This extracts the briefs back out of the rendered call lines, so a macro or
    call-site change that mangles quoting, escaping or the `\\n\\n` separator fails here.
    """
    baseline = json.loads((_FIXTURES / "lens_briefs_baseline.json").read_text(encoding="utf-8"))
    files = _render_all(preset)
    expected = {d["lens"]: d["brief"] for d in lens_dispatch(preset.value)}

    for path in (".claude/commands/hm/review.md", ".agents/skills/hm-review/SKILL.md"):
        body = files[path]
        found = _LENS_LINE.findall(body)
        assert found, f"{path}: no dispatch line carried a lens brief"
        for brief in found:
            lens = next((k for k, v in expected.items() if v == brief), None)
            assert lens is not None, (
                f"{path}: rendered brief matches no LENS_DISPATCH entry: {brief[:80]!r}"
            )
            assert baseline[lens] == brief, f"{path}: lens {lens!r} brief drifted from the baseline"
        # Every dispatched lens actually reached a rendered line, on both arms.
        assert {next(k for k, v in expected.items() if v == b) for b in found} == set(expected)


@pytest.mark.parametrize("preset", [Preset.SIDE, Preset.PRODUCTION])
def test_rendered_claude_arm_still_matches_the_frozen_baseline(preset: Preset) -> None:
    """PLAN Phase 2 exit 5 — the Claude payload did not regress while the Codex arm changed.

    Compares under the ADR-006 normalizer against the PRE-migration fixture, which is
    deliberately never regenerated: a post-migration capture would approve whatever the macro
    happens to emit, which is the self-approving baseline the PLAN rejected.
    """
    baseline = json.loads((_FIXTURES / "claude_arm_baseline.json").read_text(encoding="utf-8"))
    files = _render_all(preset)
    unaccounted = []
    for key, lines in baseline.items():
        key_preset, _, path = key.partition("::")
        if key_preset != preset.value or not path.startswith(".claude/"):
            continue
        current = {_norm(line) for line in files.get(path, "").splitlines()}
        for line in lines:
            if _norm(line) in current or line.strip() in _COLLAPSED_MULTILINE:
                continue
            unaccounted.append(f"{path}: {line.strip()[:100]}")
    assert not unaccounted, (
        "Claude-arm dispatch/question lines lost since the pre-migration baseline:\n  "
        + "\n  ".join(unaccounted)
        + "\n\nIf a removal is intentional, add the exact line to `_COLLAPSED_MULTILINE` with "
        "the reason — do NOT regenerate the fixture, which would approve the change by fiat."
    )
