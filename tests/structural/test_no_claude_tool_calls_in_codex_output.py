"""No Codex-rendered file names a tool the Codex runtime does not have.

Claude Code dispatches sub-agents with `Task(subagent_type=…)`, asks structured questions with
`AskUserQuestion` and invokes a stage with `Skill(...)`. Codex has none of those: it dispatches
with `spawn_agent`, asks with `request_user_input`, and has **no** skill-running tool at all
(live probe, Codex CLI 0.147.0 — see `tests/manual/CODEX_SPAWN_AGENT_PROBE.md`).

Rendering those names into a Codex skill ships an instruction the runtime cannot execute, and
it fails **silently**: the model improvises. Measured before PLAN-codex-lens-dispatch, this
repo's own render carried `Task(` **18** times across 9 Codex files per preset (36 across
the two rendered presets), `hm-review` alone **14** — seven lenses x two dispatch blocks. The
observable consequence in a real user harness was a Codex `/hm:review` that wrote zero lens
result files, so `hm lens_coverage check` reported every mandatory lens missing and the review
was permanently unapprovable — while the operator-facing explanation blamed the coverage CLI.

**Two design choices, both load-bearing (ADR-004).**

1. The Codex surface is *derived* from the render blueprint's output paths via
   `synthesize._is_codex_output`, never from a list of templates. A hand-maintained list is the
   thing that went stale before (`tests/structural/test_is_codex_matches_output_path.py` exists
   for the same reason), and it would have missed `commands/hm/loop.md.j2`, whose path says
   `commands/` while its content reaches Codex through `codex/loop_skill.md.j2`.
2. The scan asserts its own surface is **non-empty** before scanning it. A blueprint yielding
   zero Codex entries — a `targets` regression, a refactor of `_is_codex_output` — would
   otherwise make this gate pass vacuously, which is worse than not having it.

The matrix covers the axes that gate whether a conditional producer renders at all. It is a
list of *configurations*, not of files; that residual is smaller than a file list's and is the
cheapest form available without enumerating the whole config space.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from harness_maker.conditional_router import lens_dispatch
from harness_maker.models import (
    DevMode,
    InterviewAnswers,
    Preset,
    ProjectProfile,
    SecondOpinionConfig,
    Target,
)
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import _is_codex_output, synthesize

#: Claude-Code-only tool names. Mostly call forms, not bare words: `Skill(` rather than
#: "Skill", so the prose word "skill" is not a finding.
#:
#: `"Task tool"` is the exception, and it is here because call-forms-only was measurably too
#: narrow: `review.md.j2` told Codex to use "a single message with multiple Task tool uses" —
#: an instruction naming a tool that runtime does not have — and this gate could not see it.
#: A legitimate doc line comparing the two runtimes can name it via the allowlist.
_CLAUDE_ONLY = ("Task(", "Task tool", "AskUserQuestion", "Skill(")

#: Lines allowed to name a Claude-only tool in Codex output, with the reason. Substring match
#: against the stripped line. Keep this SHORT and keep the reason honest — an allowlist that
#: grows without argument is how a gate stops meaning anything.
_ALLOWLIST: dict[str, str] = {
    "`AskUserQuestion` in Claude Code, `request_user_input` in Codex": (
        "Documentation that names BOTH tools on purpose, so a reader knows the mapping. "
        "Rewriting it to name only one would delete the very information it carries."
    ),
}

#: Two enabled reviewers, because `review.md.j2`'s Pass-1 section is gated on
#: `reviewers.enabled | length > 1` and the default answers enable ZERO. That block told Codex
#: to use "a single message with multiple Task tool uses" and this gate could not see it.
#: TWO things were true at once and both fixes were needed: `"Task tool"` was not in
#: `_CLAUDE_ONLY` (so even a row that rendered the block would have reported clean), AND no
#: matrix row rendered the block. Removing either fix restores the blindness. THIS repo's own
#: harness runs with two reviewers enabled, so the unrenderable-by-default block is the one
#: that actually ships here.
_TWO_REVIEWERS = {
    "installed": ["code-reviewer", "security-reviewer"],
    "enabled": ["code-reviewer", "security-reviewer"],
}

_MATRIX = [
    pytest.param(preset, targets, dev_mode, models, reviewers, id=id_)
    for preset, targets, dev_mode, models, reviewers, id_ in [
        *(
            (p, t, d, [], None, f"{p.value}-{len(t)}t-{d.value}")
            for p in (Preset.SIDE, Preset.PRODUCTION)
            for t in ([Target.CODEX], [Target.CLAUDE_CODE, Target.CODEX])
            for d in (DevMode.SPEC_DRIVEN, DevMode.TASK_DRIVEN)
        ),
        # `second_opinion.models` gates a whole block of `plan.md.j2` (and the per-model
        # partials). It defaults to `[]`, so the cross-product above never renders that block —
        # and review round 1 found live `Task()` prose inside it, on the configuration THIS
        # repo runs. A config axis that gates a producer has to be in the matrix or the gate
        # reports clean for text it never opened. Added as explicit rows rather than a fourth
        # cross-product dimension: the axis only needs one enabled value to reach the block,
        # and each row is a full render.
        (
            Preset.PRODUCTION,
            [Target.CLAUDE_CODE, Target.CODEX],
            DevMode.SPEC_DRIVEN,
            ["codex"],
            None,
            "Production-2t-spec-driven-so-codex",
        ),
        (
            Preset.SIDE,
            [Target.CODEX],
            DevMode.TASK_DRIVEN,
            ["codex", "antigravity"],
            None,
            "Side-1t-task-driven-so-both",
        ),
        (
            Preset.PRODUCTION,
            [Target.CLAUDE_CODE, Target.CODEX],
            DevMode.SPEC_DRIVEN,
            ["codex"],
            _TWO_REVIEWERS,
            "Production-2t-spec-driven-two-reviewers",
        ),
    ]
]


def _codex_bodies(
    preset: Preset,
    targets: list[Target],
    dev_mode: DevMode,
    models: list[str] | None = None,
    reviewers: dict[str, list[str]] | None = None,
) -> dict[str, str]:
    """Render one configuration and return only its Codex-destined files."""
    answers = InterviewAnswers(
        preset=preset,
        targets=targets,
        dev_mode=dev_mode,
        second_opinion=SecondOpinionConfig(models=models or []),  # type: ignore[arg-type]
    )
    if reviewers is not None:
        answers.reviewers = reviewers
    blueprint = synthesize(ProjectProfile(), answers)
    with tempfile.TemporaryDirectory() as td:
        # `target_dir` is the `.claude` DIRECTORY, not the project root: Codex outputs
        # (`.codex/`, `.agents/`, `AGENTS.md`) are written to its PARENT. Rooting the render at
        # a bare tmpdir puts the Codex half in the tmpdir's parent — the real `/tmp` — and the
        # scan then finds nothing and reads as "clean" rather than "looked in the wrong place".
        root = Path(td)
        render(blueprint, root / ".claude", freeze_time=DEFAULT_FREEZE_TIME)
        out: dict[str, str] = {}
        # os.walk rather than Path.rglob: not because rglob skips dotted paths — it does NOT,
        # verified — but because the scan must be rooted at `root`, one level ABOVE the render
        # target. The first version of this scan reported "59 of 98 entries, zero Codex files";
        # the cause was the `target_dir.parent` fact above, and blaming rglob was a wrong
        # explanation that got copied into three files before review caught it.
        for walk_root, _dirs, names in os.walk(root):
            for name in names:
                f = Path(walk_root) / name
                rel = str(f.relative_to(root))
                if _is_codex_output(rel):
                    out[rel] = f.read_text(encoding="utf-8", errors="replace")
        return out


def _violations(bodies: dict[str, str]) -> list[str]:
    found = []
    for path, body in sorted(bodies.items()):
        for lineno, line in enumerate(body.splitlines(), 1):
            stripped = line.strip()
            # Exempt the ALLOWED SUBSTRING, not the whole line. Skipping the line would let a
            # real `Task(` ride along on any line that also happens to contain the documented
            # sentence — an allowlist entry that widens itself to everything sharing its row.
            probe = stripped
            for allowed in _ALLOWLIST:
                probe = probe.replace(allowed, "")
            for tool in _CLAUDE_ONLY:
                if tool in probe:
                    found.append(f"{path}:{lineno} [{tool}] {stripped[:100]}")
    return found


@pytest.mark.parametrize(("preset", "targets", "dev_mode", "models", "reviewers"), _MATRIX)
def test_no_claude_only_tool_reaches_codex_output(
    preset: Preset,
    targets: list[Target],
    dev_mode: DevMode,
    models: list[str],
    reviewers: dict[str, list[str]] | None,
) -> None:
    bodies = _codex_bodies(preset, targets, dev_mode, models, reviewers)
    assert bodies, (
        "no Codex output in this blueprint — the gate would pass vacuously. Either `targets` "
        "stopped producing Codex files or `_is_codex_output` stopped recognising them."
    )
    violations = _violations(bodies)
    assert not violations, (
        "Codex output names a tool the Codex runtime does not have:\n  "
        + "\n  ".join(violations)
        + "\n\nDispatch through `agents/_partials/dispatch.md.j2`, ask with "
        "`request_user_input`, and do not name `Skill(` — Codex cannot run a skill "
        "programmatically. If a line legitimately names the Claude tool (documentation "
        "explaining the mapping), add it to `_ALLOWLIST` WITH a reason."
    )


def test_every_allowlist_entry_is_still_reached() -> None:
    """An allowlist entry nobody hits is a permission that outlived its subject.

    Left in place it silently widens the gate for whatever text happens to match it next.
    """
    bodies = _codex_bodies(
        Preset.PRODUCTION, [Target.CLAUDE_CODE, Target.CODEX], DevMode.SPEC_DRIVEN
    )
    corpus = "\n".join(bodies.values())
    for allowed, reason in _ALLOWLIST.items():
        assert allowed in corpus, (
            f"allowlist entry no longer appears in any Codex output: {allowed!r}"
        )
        assert reason.strip(), f"allowlist entry {allowed!r} has no reason"


def test_the_gate_fails_on_an_injected_regression() -> None:
    """A gate never observed failing is not known to be wired.

    Injects each Claude-only form into a real Codex body and asserts the detector reports it —
    exercising `_violations` itself rather than a re-implementation of it.
    """
    # The payloads are DERIVED from `_CLAUDE_ONLY`, not a parallel hardcoded list. A literal
    # list silently stops covering the tuple the moment an entry is added: `"Task tool"` was
    # added to close a measured leak and a hardcoded 3-payload loop exercised it with nothing,
    # so deleting or mis-spelling that entry would have left the whole module green.
    payloads = {
        "Task(": 'Task(subagent_type="code-reviewer", description="d", prompt="p")',
        "Task tool": "run them in a single message with multiple Task tool uses",
        "AskUserQuestion": "offer via `AskUserQuestion`",
        "Skill(": "invoke `Skill(hm:execute)`",
    }
    assert set(payloads) == set(_CLAUDE_ONLY), (
        "every _CLAUDE_ONLY entry needs an injection payload — an undetected entry is a "
        f"detector nothing exercises: {set(_CLAUDE_ONLY) ^ set(payloads)}"
    )

    bodies = _codex_bodies(Preset.SIDE, [Target.CODEX], DevMode.TASK_DRIVEN)
    assert not _violations(bodies)
    target = sorted(bodies)[0]
    for tool, injected in payloads.items():
        mutated = dict(bodies)
        mutated[target] = bodies[target] + "\n" + injected + "\n"
        found = _violations(mutated)
        assert found, f"the gate did not notice an injected {tool}"
        assert any(tool in row for row in found)


def test_the_gate_refuses_an_empty_surface() -> None:
    """The vacuous-pass mode, asserted rather than trusted.

    A Claude-only render produces no Codex files at all; the precondition must fire there, or
    the gate would report "clean" for a configuration it never looked at.
    """
    bodies = _codex_bodies(Preset.SIDE, [Target.CLAUDE_CODE], DevMode.TASK_DRIVEN)
    assert not bodies, "a claude-code-only render produced Codex output — the axis moved"


def test_the_allowlist_does_not_exempt_a_real_call_sharing_its_line() -> None:
    """The allowlist forgives a documented sentence, not everything typed beside it."""
    allowed = next(iter(_ALLOWLIST))
    clean = _violations({"x.md": f"prose {allowed} more prose"})
    assert not clean
    smuggled = _violations({"x.md": f'prose {allowed} and Task(subagent_type="x")'})
    assert smuggled, "a real Task( rode in on an allowlisted line"


@pytest.mark.parametrize("preset", [Preset.SIDE, Preset.PRODUCTION])
def test_the_codex_arm_actually_renders_its_dispatches(preset: Preset) -> None:
    """POSITIVE control. Every other assertion here is negative, so a macro that emitted
    NOTHING on the Codex arm would pass the whole module cleanly — "no Claude tool" is also
    true of an empty file. This pins the count the reported symptom is about: seven lenses
    (`lens_dispatch` returns 7 on both presets) across the two dispatch blocks in
    `review.md.j2` — round 1 and the confirmation re-dispatch.
    """
    bodies = _codex_bodies(preset, [Target.CLAUDE_CODE, Target.CODEX], DevMode.SPEC_DRIVEN)
    review = bodies[".agents/skills/hm-review/SKILL.md"]
    expected = 2 * len(lens_dispatch(preset.value))
    actual = review.count('spawn_agent(agent_type="')
    assert actual == expected, (
        f"hm-review renders {actual} Codex dispatches, expected {expected} "
        f"({len(lens_dispatch(preset.value))} lenses x 2 blocks). A shrinking fan-out is "
        "invisible to every other assertion in this file."
    )
