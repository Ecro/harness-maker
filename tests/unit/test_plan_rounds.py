"""The plan-stage transfer: progress invariant in, churn gate INVERTED, lens axis not at all.

Each test names the wrong transfer it rejects. The literal copy of the review gate — "low
churn, skip the check" — is the one this file exists to refuse: `plan.md.j2` records 12
validator episodes that never reached a clean verdict and one PLAN whose pass-2 criticals were
created by the pass-1 fixes, so a small edit is precisely NOT evidence that re-validation can
be skipped.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from harness_maker.plan_rounds import (
    DEFAULT_STALE_RATIO,
    PlanRoundsError,
    critique_id,
    follow_up_plan,
    main,
    merge_passes,
    pass_outcome,
    stamp_ids,
)


def _c(title: str, section: str = "Phase 2", severity: str = "critical", **kw: Any) -> dict:
    return {"title": title, "section": section, "severity": severity, **kw}


# ── ids are computed here, never asked of the model ──────────────────────────


def test_the_id_is_stable_across_passes_and_over_reformatting() -> None:
    """An LLM-minted id changes every run, so merge-by-id degrades to "everything is new".

    That is the exact failure the review loop hit twice; there the consequence was a
    corroborating voice vanishing, here it is the progress invariant that can never fire.
    """
    a = critique_id("Phase 2", "Rollback is undefined")
    b = critique_id("  phase 2 ", "Rollback   is\nundefined")
    assert a == b
    assert a != critique_id("Phase 3", "Rollback is undefined")


def test_a_model_supplied_id_is_honoured_but_never_required() -> None:
    rows = stamp_ids([_c("x"), {**_c("y"), "id": "given"}])
    assert rows[0]["id"] == critique_id("Phase 2", "x")
    assert rows[1]["id"] == "given"


def test_a_titleless_critique_is_refused_rather_than_given_an_id() -> None:
    """Hashing an empty title would collide every malformed critique onto one id."""
    with pytest.raises(PlanRoundsError):
        stamp_ids([{"section": "Phase 2", "severity": "critical"}])


# ── the progress invariant ───────────────────────────────────────────────────


def test_a_critique_that_survives_a_revision_is_unresolved_not_pending_again() -> None:
    """The round that produced nothing must not be bought a second time.

    Today the stage runs one follow-up round per critical, so a critique the revision failed
    to answer is answered again with the same answer — the loop `plan.md.j2` measured as
    never converging.
    """
    prev = stamp_ids([_c("Rollback is undefined")])
    now = stamp_ids([_c("Rollback is undefined")])
    merged = merge_passes(prev, now)
    assert [c["status"] for c in merged] == ["unresolved"]


def test_a_critique_the_new_pass_no_longer_raises_is_resolved() -> None:
    prev = stamp_ids([_c("Rollback is undefined"), _c("No exit criterion")])
    now = stamp_ids([_c("Rollback is undefined")])
    merged = {c["title"]: c["status"] for c in merge_passes(prev, now)}
    assert merged == {"Rollback is undefined": "unresolved", "No exit criterion": "resolved"}


def test_a_genuinely_new_critique_is_pending_and_earns_its_round() -> None:
    """Non-vacuity: the invariant must not swallow the findings a revision CREATED.

    Those are the ones the measurement says matter most — one recorded PLAN's pass-2
    criticals were created by the pass-1 fixes.
    """
    prev = stamp_ids([_c("Rollback is undefined")])
    now = stamp_ids([_c("Rollback is undefined"), _c("Phase 3 now contradicts Phase 1")])
    merged = merge_passes(prev, now)
    fresh = [c for c in merged if c["status"] == "pending"]
    assert [c["title"] for c in fresh] == ["Phase 3 now contradicts Phase 1"]
    assert [r["title"] for r in follow_up_plan(merged)["rounds"]] == [
        "Phase 3 now contradicts Phase 1"
    ]


def test_the_lattice_is_monotonic_nothing_returns_to_pending() -> None:
    """A terminal status is terminal. Re-opening it is how the loop stops converging."""
    prev = [{**_c("x"), "status": "stale", "id": critique_id("Phase 2", "x")}]
    now = stamp_ids([_c("x")])
    assert merge_passes(prev, now)[0]["status"] == "stale"


def test_no_progress_is_reported_separately_from_running_out_of_passes() -> None:
    """A bare two-pass cap reports `cap-exhausted` for both, hiding the one that matters."""
    prev = stamp_ids([_c("a"), _c("b")])
    same = stamp_ids([_c("a"), _c("b")])
    assert pass_outcome(prev, same)["outcome"] == "no-progress"

    moved = stamp_ids([_c("a")])
    result = pass_outcome(prev, moved)
    assert result["outcome"] == "progress"
    assert result["resolved_n"] == 1


# ── churn, transferred INVERTED ──────────────────────────────────────────────


def test_high_churn_makes_the_queued_critiques_stale_not_the_low_churn_case() -> None:
    """The direction is the whole point.

    Copying the review gate literally would skip work when churn is LOW — i.e. skip
    re-validation of a small edit, which is the reading `plan.md.j2`'s own measurement
    refutes. Here a LARGE rewrite is what discards the queue: those critiques were raised
    against a document that no longer exists, and the terminal pass re-derives whatever
    still holds.
    """
    rows = stamp_ids([_c("a"), _c("b"), _c("c")])

    big = follow_up_plan(rows, churn_ratio=0.80)
    assert big["rounds"] == []
    assert {s["status"] for s in big["skipped"]} == {"stale"}

    small = follow_up_plan(rows, churn_ratio=0.05)
    assert len(small["rounds"]) == 3
    assert small["skipped"] == []


def test_the_boundary_is_inclusive_at_the_configured_threshold() -> None:
    rows = stamp_ids([_c("a")])
    assert follow_up_plan(rows, churn_ratio=DEFAULT_STALE_RATIO)["rounds"] == []
    assert len(follow_up_plan(rows, churn_ratio=DEFAULT_STALE_RATIO - 0.01)["rounds"]) == 1


def test_an_unmeasured_churn_ratio_runs_every_round() -> None:
    """The absent case, fail-open toward doing the work (count:8 failure class).

    A `None` ratio meaning "stale" would let one missing measurement silently cancel the
    stage's entire revision step — a feature that no-ops for exactly the inputs that predate
    it, which is the shape this repo has shipped eight times.
    """
    rows = stamp_ids([_c("a"), _c("b")])
    assert len(follow_up_plan(rows, churn_ratio=None)["rounds"]) == 2


def test_a_skipped_critique_always_carries_its_reason() -> None:
    """A queue that shrinks silently is indistinguishable from a validator that found less."""
    rows = stamp_ids([_c("a")])
    skipped = follow_up_plan(rows, churn_ratio=0.9)["skipped"]
    assert "0.90 >= 0.50" in skipped[0]["reason"]
    assert "terminal pass re-derives" in skipped[0]["reason"]


def test_criticals_are_ordered_before_warnings_and_ties_are_stable() -> None:
    rows = stamp_ids([_c("w1", severity="warning"), _c("c1"), _c("w2", severity="warning")])
    ordered = [r["title"] for r in follow_up_plan(rows)["rounds"]]
    assert ordered[0] == "c1"
    assert follow_up_plan(rows)["rounds"] == follow_up_plan(list(reversed(rows)))["rounds"]


# ── the CLI the stage actually calls ─────────────────────────────────────────


def test_the_cli_plans_rounds_from_two_passes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    prev = tmp_path / "p1.json"
    now = tmp_path / "p2.json"
    prev.write_text(json.dumps(stamp_ids([_c("a"), _c("b")])), encoding="utf-8")
    now.write_text(json.dumps(stamp_ids([_c("a"), _c("new")])), encoding="utf-8")

    assert main(["plan", "--file", str(now), "--previous", str(prev)]) == 0
    payload = json.loads(capsys.readouterr().out)
    # `a` survived the revision → unresolved, no round. `new` is fresh → one round.
    assert [r["title"] for r in payload["rounds"]] == ["new"]


def test_the_cli_reads_an_envelope_or_a_bare_list(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The validator returns `{overall, critiques: [...]}`; requiring a bare list invites a
    hand-edit that drops the envelope."""
    f = tmp_path / "v.json"
    f.write_text(
        json.dumps({"overall": "MAJOR_REVISION", "critiques": stamp_ids([_c("a")])}),
        encoding="utf-8",
    )
    assert main(["plan", "--file", str(f)]) == 0
    assert len(json.loads(capsys.readouterr().out)["rounds"]) == 1


def test_the_cli_writes_nothing(tmp_path: Path) -> None:
    """Same rule the review verbs converged on: reads only, one payload, no state.

    The write-back is what produced file destruction, envelope loss and a non-idempotent
    retry in `/hm:review`; there is no reason to re-introduce it here.
    """
    f = tmp_path / "v.json"
    body = json.dumps(stamp_ids([_c("a")]))
    f.write_text(body, encoding="utf-8")
    before = sorted(p.name for p in tmp_path.iterdir())
    assert main(["plan", "--file", str(f)]) == 0
    assert f.read_text(encoding="utf-8") == body
    assert sorted(p.name for p in tmp_path.iterdir()) == before


def test_the_cli_diagnoses_a_malformed_input_instead_of_raising(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    f = tmp_path / "bad.json"
    f.write_text('{"overall": "x"}', encoding="utf-8")
    assert main(["plan", "--file", str(f)]) == 2
    assert "critiques" in capsys.readouterr().err


# ── the rendered plan stage actually calls it ────────────────────────────────


def _render_plan() -> dict[str, str]:
    import tempfile

    from harness_maker.interview import interview
    from harness_maker.models import ProjectProfile, Target
    from harness_maker.render import DEFAULT_FREEZE_TIME, render
    from harness_maker.synthesize import synthesize

    profile = ProjectProfile(stack=["python"], scale="small", lifecycle="dormant")
    answers = interview(profile, autoloop_mode=True)
    answers.worktree["enabled"] = True
    answers.targets = [Target.CLAUDE_CODE, Target.CODEX]
    out = Path(tempfile.mkdtemp())
    render(synthesize(profile, answers), out, freeze_time=DEFAULT_FREEZE_TIME)
    return {
        "claude": (out / "commands" / "hm" / "plan.md").read_text(encoding="utf-8"),
        "codex": (out / ".." / ".agents" / "skills" / "hm-plan" / "SKILL.md")
        .resolve()
        .read_text(encoding="utf-8"),
    }


def test_the_rendered_plan_stage_plans_its_follow_up_rounds_by_cli() -> None:
    """Arithmetic nothing calls decides nothing — this PLAN's own round-1 P0, again."""
    for variant, body in _render_plan().items():
        calls = [ln for ln in body.splitlines() if "hm plan_rounds plan " in ln]
        assert len(calls) == 1, f"{variant}: expected one plan_rounds call, got {len(calls)}"
        assert "--file" in calls[0]
        outcome = [ln for ln in body.splitlines() if "hm plan_rounds outcome " in ln]
        assert len(outcome) == 1, f"{variant}: the terminal pass records no outcome"


def test_the_rendered_plan_stage_no_longer_runs_one_round_per_critique() -> None:
    """The instruction being replaced is the unbounded cost; leaving it renders both."""
    for variant, body in _render_plan().items():
        assert "run follow-up rounds for each critical critique" not in body, variant
        assert "one follow-up interview round per warning" not in body, variant
        assert "none for any entry in `skipped`" in body, variant


def test_the_rendered_plan_stage_states_that_an_unmeasured_ratio_runs_every_round() -> None:
    """The absent case, in the render — a skipped measurement must not cancel the step."""
    for variant, body in _render_plan().items():
        assert "an unmeasured ratio runs every round" in body, variant
