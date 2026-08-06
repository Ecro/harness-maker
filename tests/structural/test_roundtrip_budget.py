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

from ._surface_baseline import CLAUDE_VARIANT, CODEX_VARIANT, count_round_trips, render_surface

# Measured 2026-07-29 against this repo's `.claude/harness.yaml` through the SAME
# generator the surface baseline uses. Phases 2–5 lowered `execute`, `wrapup` and their
# fused descendants; `research` ROSE because the fan-out's three `Task(` dispatches are
# counted individually by the ADR-011 rule even though they leave in one message — see
# the note in `test_the_fan_out_is_counted_as_three_though_it_costs_one_turn`.
_CLAUDE_ROUND_TRIPS: dict[str, int] = {
    # +1 on every review-bearing command (2026-07-30, PLAN-second-opinion-acceptance-gate):
    # Step 3.4 gained ONE mandated call, `hm codex_adapter stamp-ids`. It exists because the
    # step previously told an LLM to compute `sha256(...)[:16]` itself — which it cannot do, so
    # Claude-side finding ids were invented per round and the merge-by-`id` contract keyed on
    # values that changed every round. The call is the whole point of that fix; no call was
    # removed. `review` 7→8. (The four fused commands that also inherited it were deleted
    # with the fused axis — PLAN-harness-diet ADR-001.)
    # +1 on `execute`, `plan` and `review` (2026-08-05, PLAN-workflow-loop-efficiency P3):
    # each gained exactly ONE mandated call, and each is a ledger write, not a check:
    #   execute Phase A.5 → `hm stage_agent_ledger emit`   (test-reviewer verdict per attempt)
    #   plan    Step 4    → `hm stage_agent_ledger emit`   (validator verdict per pass)
    #   review  Step 3.4  → `hm stage_agent_ledger persist-payload` (ADR-006 part 2 corpus)
    # No call was removed. `execute` 14→15, `plan` 14→15, `review` 8→9, total 127→130.
    # These three calls are the entire reason stage 2 will have a denominator; the round-trip
    # cost is the price of that, and it is charged per stage invocation, not per round.
    #
    # configure 3→4, total 130→131 (PLAN-onboarding-interview-ux, 2026-08-06). ONE call added,
    # none removed: `hm cli detect-tools --json` in the new "Cross-model second opinion"
    # dimension. It is a check, not a ledger write, and it is conditional in spirit but not in
    # render — the dimension only asks after showing which CLIs are on PATH, and detection
    # cannot be cached (installing a CLI invalidates nothing `profile()` watches, ADR-001), so
    # there is no cheaper shape. `health` is unchanged at 7 even though it gained the same call:
    # that one renders under `{% if not config.second_opinion.models %}` and this fixture's
    # harness has models set, so it is absent from the measured body. Do not "fix" that
    # asymmetry by making health's call unconditional — the gate is the point.
    "configure": 4,
    "execute": 15,
    "health": 7,
    "help": 0,
    "loop": 12,
    "loop-p5-batch": 2,
    "make": 1,
    "metrics": 7,
    "plan": 15,
    "research": 8,
    "review": 9,
    "spec": 6,
    "uninstall": 3,
    "verify": 13,
    "wrapup": 29,
}


@pytest.fixture(scope="module")
def surface() -> dict[str, dict[str, str]]:
    return render_surface()


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


def test_the_fan_out_is_counted_as_three_though_it_costs_one_turn(
    surface: dict[str, dict[str, str]],
) -> None:
    """Stated as a test so the discrepancy cannot be quietly forgotten.

    ADR-011's rule adds every `Task(` to the call count. Three `Explore` dispatches sent
    in ONE message are one main-loop turn, so for the fan-out the rule OVER-counts. The
    rule is not being changed mid-flight — moving the goalposts to make a phase pass is
    exactly what ADR-011 forbids — but the Phase 7 receipt reports main-loop turns and
    subagent turns separately (ADR-012) precisely because this proxy conflates them.

    In THIS repo the fan-out does not render at all: `targets` includes `cursor`, and
    Cursor reads the Claude command file (`.cursor/commands/` is dead code), so shipping
    it here would emit a dispatch Cursor cannot resolve.
    """
    body = surface[CLAUDE_VARIANT]["research"]
    assert "Explore" not in body, "this repo includes cursor in targets — see the docstring"


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
    body = surface[CLAUDE_VARIANT]["wrapup"]
    mutated = count_round_trips(_mutate_chain_two_calls(body), CLAUDE_VARIANT)
    assert mutated != _CLAUDE_ROUND_TRIPS["wrapup"]


def test_deleting_one_call_fails_the_floor(surface: dict[str, dict[str, str]]) -> None:
    body = surface[CLAUDE_VARIANT]["verify"]
    mutated = count_round_trips(_mutate_delete_one_call(body), CLAUDE_VARIANT)
    assert mutated != _CLAUDE_ROUND_TRIPS["verify"]


def test_moving_a_call_between_commands_fails_the_total(
    surface: dict[str, dict[str, str]],
) -> None:
    """Per-command equality already catches this; the total is the arm that catches it
    when someone re-baselines one command and forgets the other."""
    bodies = dict(surface[CLAUDE_VARIANT])
    bodies["verify"] = _mutate_delete_one_call(bodies["verify"])
    total = sum(count_round_trips(b, CLAUDE_VARIANT) for b in bodies.values())
    assert total != sum(_CLAUDE_ROUND_TRIPS.values())
