"""ADR-011 assertion 1 — the round-trip floor, and the proof it can fail.

The character floor is `measured * 0.80`. One deleted `!` line is ~0.5% of an atomic
command, so a character floor is structurally blind to the very thing this PLAN spends:
round-trips. This arm is therefore **exact equality, zero slack** — deliberately unlike
the character floor. A phase that changes a command's call count re-baselines the table
below **in its own commit**, naming the calls it removed.

A ratchet that cannot fail is worse than none, so the three mutations at the bottom are
not decoration: they are the evidence. The first draft of this phase aimed a single
mutation at the *ceiling*, which that mutation passes — and the shipped render already
`&&`-chains two commands onto one line, so chaining is not even an anomaly to detect by
shape. It has to be detected by count.
"""

from __future__ import annotations

import re

import pytest

from ._instruction_baseline import stage_text
from ._surface_baseline import (
    CLAUDE_VARIANT,
    CODEX_VARIANT,
    REFS_VARIANT,
    count_round_trips,
    render_surface,
)

# Measured against this repo's `.claude/harness.yaml` through the SAME generator the surface
# baseline uses (re-measured for 0.64.0; earlier movements are in git history).
_CLAUDE_ROUND_TRIPS: dict[str, int] = {
    # 144 → 14 (0.64.0, SPEC-hm-overhaul-p1). The four stages no longer carry `!` lines: each
    # `hm …` call is an instruction the model runs (`_hm.md.j2`'s `cli()` prefix), so the
    # ADR-011 rule counts only their `Task(subagent_type=` dispatches — execute's code-reviewer
    # and second opinion, spec's validator, wrapup's stage-delegate and judgment reviewer.
    # configure, review and verify no longer render; research's fan-out is prose ("fan out in
    # one message") with no named dispatch. health, make and uninstall are unchanged.
    "execute": 2,
    "health": 5,
    "help": 0,
    "make": 1,
    "metrics": 0,
    "research": 0,
    "spec": 1,
    "uninstall": 3,
    "wrapup": 2,
}


@pytest.fixture(scope="module")
def surface() -> dict[str, dict[str, str]]:
    """Each Claude command as the model meets it: the command plus the `.claude/hm/` files it
    points at (`_instruction_baseline.stage_text`). Calls that moved into a reference file are
    still calls the stage makes, so they stay under this budget (stage 2b confirmation pass)."""
    rendered = render_surface(with_refs=True)
    commands, refs = rendered[CLAUDE_VARIANT], rendered[REFS_VARIANT]
    return {
        CLAUDE_VARIANT: {name: stage_text(name, commands, refs) for name in commands},
        CODEX_VARIANT: rendered[CODEX_VARIANT],
    }


def test_the_table_covers_every_rendered_claude_command(surface: dict[str, dict[str, str]]) -> None:
    """A command absent from the table has no round-trip budget at all — the silent way
    this arm narrows. Asserted as set equality so neither direction can drift."""
    assert set(surface[CLAUDE_VARIANT]) == set(_CLAUDE_ROUND_TRIPS)


@pytest.mark.parametrize("name", sorted(_CLAUDE_ROUND_TRIPS))
def test_round_trips_match_exactly(surface: dict[str, dict[str, str]], name: str) -> None:
    actual = count_round_trips(surface[CLAUDE_VARIANT][name], CLAUDE_VARIANT)
    assert actual == _CLAUDE_ROUND_TRIPS[name], (
        f"{name}: {actual} mandated calls, table says {_CLAUDE_ROUND_TRIPS[name]}. "
        "If a phase changed this deliberately, re-baseline HERE in that phase's commit "
        "and name the calls it added or removed."
    )


def test_the_shipped_total_is_not_higher_than_the_table(
    surface: dict[str, dict[str, str]],
) -> None:
    """The aggregate the per-command arms cannot see: calls moved between commands."""
    total = sum(
        count_round_trips(body, CLAUDE_VARIANT) for body in surface[CLAUDE_VARIANT].values()
    )
    assert total == sum(_CLAUDE_ROUND_TRIPS.values())


def test_the_codex_variant_is_counted_by_its_own_call_form(
    surface: dict[str, dict[str, str]],
) -> None:
    """`Bash(` not `^!` — a counter applying the Claude rule to Codex returns 0 and
    asserts nothing, which is how this arm would silently stop binding on that target."""
    execute = surface[CODEX_VARIANT]["hm-execute"]
    assert count_round_trips(execute, CODEX_VARIANT) > 0
    assert len(re.findall(r"^!", execute, re.M)) == 0




# ── the three mutations ADR-011 requires this arm to fail under ────────────────


def _mutate_chain_two_calls(text: str) -> str:
    """`&&`-chain two real calls onto one line — the shape a ceiling cannot see."""
    lines = text.splitlines()
    idx = [i for i, ln in enumerate(lines) if ln.startswith("!")]
    assert len(idx) >= 2, "fixture has too few calls to chain"
    a, b = idx[0], idx[1]
    lines[a] = lines[a] + " && " + lines[b].lstrip("!")
    del lines[b]
    return "\n".join(lines)


def _mutate_delete_one_call(text: str) -> str:
    lines = text.splitlines()
    idx = next(i for i, ln in enumerate(lines) if ln.startswith("!"))
    del lines[idx]
    return "\n".join(lines)


def test_chaining_two_calls_onto_one_line_fails_the_floor(
    surface: dict[str, dict[str, str]],
) -> None:
    body = surface[CLAUDE_VARIANT]["health"]
    mutated = count_round_trips(_mutate_chain_two_calls(body), CLAUDE_VARIANT)
    assert mutated != _CLAUDE_ROUND_TRIPS["health"]


def test_deleting_one_call_fails_the_floor(surface: dict[str, dict[str, str]]) -> None:
    body = surface[CLAUDE_VARIANT]["health"]
    mutated = count_round_trips(_mutate_delete_one_call(body), CLAUDE_VARIANT)
    assert mutated != _CLAUDE_ROUND_TRIPS["health"]


def test_moving_a_call_between_commands_fails_the_total(
    surface: dict[str, dict[str, str]],
) -> None:
    """Per-command equality already catches this; the total is the arm that catches it
    when someone re-baselines one command and forgets the other."""
    bodies = dict(surface[CLAUDE_VARIANT])
    bodies["health"] = _mutate_delete_one_call(bodies["health"])
    total = sum(count_round_trips(b, CLAUDE_VARIANT) for b in bodies.values())
    assert total != sum(_CLAUDE_ROUND_TRIPS.values())
