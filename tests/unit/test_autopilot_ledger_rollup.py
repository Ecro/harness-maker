"""Phase 1 of PLAN-token-efficiency-autopilot-ux-speed — AC-001 and AC-002.

Both ACs are `type: mechanical` in `specs/SPEC-token-efficiency-autopilot-ux-speed.machine.yaml`,
so the assertions here ARE their `executable_predicate`s, bound to the real subjects.

**Why the AC-001 fixture is shaped the way it is.** Four distinct mis-aggregations each produce a
DIFFERENT number against it, so a wrong implementation cannot pass by accident:

* merging the two models       -> `by_model` loses the per-model split entirely
* dropping `failed` rows       -> codex `calls` reads 4, not 5
* counting disposition rows    -> `total` reads 7, not 6
* skipping the exclusions file -> `total` reads 7, not 6

Three of those four are mistakes CLAUDE.md records as having shipped on this ledger family (a
hand aggregation reported 61.3% where the shipped reader reported 2.15% -- 30x -- and an earlier
`skipped/total` reported 10.3% where the truth was 20.7%, with one model's whole loss in `failed`
rows). The expected numbers below are counted by hand off the fixture, never by a second call to
the aggregator.
"""

from __future__ import annotations

import dataclasses
import json
import re
from pathlib import Path
from typing import Any

import pytest

from harness_maker import autopilot_ledger, verifier_discrimination


def _numbers(body: str) -> list[str]:
    """Every numeric token in the document, as a multiset.

    Used for the per-axis differential below. Comparing multisets rather than substrings is what
    makes a date's digits cancel: they appear identically on both sides of the comparison, so they
    contribute nothing, while a changed aggregate does. `"6" in body` cannot do this — a
    one-character substring is satisfied by any 2026 timestamp regardless of what the render prints.
    """
    return sorted(re.findall(r"\b\d+(?:\.\d+)?\b", body))


# -- AC-001 fixture -----------------------------------------------------------
# Six INVOCATION rows survive the filters. Everything else is a discriminator.
_SECOND_OPINION_ROWS: list[dict[str, Any]] = [
    # codex: 4 invoked + 1 failed = 5 calls. `failed` is IN the loss numerator, never dropped.
    {"model": "codex", "status": "invoked", "stage": "review", "finding_ref": "n/a"},
    {"model": "codex", "status": "invoked", "stage": "review", "finding_ref": "n/a"},
    {"model": "codex", "status": "invoked", "stage": "review", "finding_ref": "n/a"},
    {"model": "codex", "status": "invoked", "stage": "plan", "finding_ref": "n/a"},
    {"model": "codex", "status": "failed", "stage": "plan", "finding_ref": "n/a"},
    # antigravity: 1 skipped. A merged-model aggregate would hide that codex is healthy.
    {"model": "antigravity", "status": "skipped", "stage": "review", "finding_ref": "n/a"},
    # DISPOSITION row -- carries `status: invoked` too, so `finding_ref` is the only
    # discriminator. Counting it as an invocation makes `total` 7.
    {
        "model": "codex",
        "status": "invoked",
        "stage": "review",
        "finding_ref": "f-0001",
        "disposition": "accepted",
    },
    # `stage: "health"` -- the smoke runs in base with a trivial prompt, so it is
    # structurally `invoked`-biased. Including it makes `total` 7.
    {"model": "codex", "status": "invoked", "stage": "health", "finding_ref": "n/a"},
    # Named by `.ledger-exclusions.json` below. Including it makes `total` 7.
    {
        "model": "codex",
        "status": "invoked",
        "stage": "review",
        "finding_ref": "n/a",
        "run_id": "test-pollution-1",
    },
]

# The promoted schema is a JSON **list**. A dict is read as the LEGACY map — which is how the
# first draft of this fixture wrote it, producing precisely the failure `ledger_exclusions.load`
# documents: "a file that looks configured and is inert". Caught by the count arm below, not by
# inspection.
_EXCLUSIONS: list[dict[str, Any]] = [
    {
        "key": "run_id",
        "value": "test-pollution-1",
        "reason": "row written by the test suite into a production ledger",
    }
]

# -- AC-002 fixture -----------------------------------------------------------
# One `advance_authorized` with no matching `advance_entered`, plus a CONFIRMED pair for a
# different stage so a reader that simply counts authorizations reports 2 instead of 1.
_AUTO_ADVANCE_ROWS: list[dict[str, Any]] = [
    {"event": "advance_authorized", "to": "spec", "ts": "2026-09-08T04:00:00+00:00"},
    {"event": "advance_entered", "to": "spec", "ts": "2026-09-08T04:01:00+00:00"},
    {"event": "advance_authorized", "to": "execute", "ts": "2026-09-08T04:02:00+00:00"},
]


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


def _observability(tmp_path: Path) -> Path:
    obs = tmp_path / ".claude" / "observability"
    _write_jsonl(obs / "second-opinion.jsonl", _SECOND_OPINION_ROWS)
    _write_jsonl(obs / "auto-advance.jsonl", _AUTO_ADVANCE_ROWS)
    (obs / ".ledger-exclusions.json").write_text(json.dumps(_EXCLUSIONS), encoding="utf-8")
    return obs


def test_ac_001_rollup_counts_are_hand_checkable(tmp_path: Path) -> None:
    """AC-001 predicate arms 1+2, plus the per-stage axis AC-001's own text names.

    Counted by hand off `_SECOND_OPINION_ROWS`: stage `review` keeps 4 call rows (three codex
    `invoked` + one antigravity `skipped`; the disposition, `health` and excluded rows are all
    `review` too and must NOT appear here), stage `plan` keeps 2 (one `invoked`, one `failed`).
    4 + 2 == the asserted total of 6, so the per-stage split and the total constrain each other.
    """
    obs = _observability(tmp_path)

    result = autopilot_ledger.rollup(tmp_path, observability_dir=obs)

    assert result.by_model["codex"]["invoked"] == 4
    assert result.total == 6
    assert result.by_stage == {"plan": 2, "review": 4}


def test_ac_001_each_misaggregation_changes_the_answer(tmp_path: Path) -> None:
    """The fixture's discriminating power, asserted rather than described.

    Without this, "== 4 and == 6" could hold for an implementation that happens to agree on
    this fixture while getting the semantics wrong. Each arm below is one of the four recorded
    mistakes, and each must move a number.
    """
    obs = _observability(tmp_path)
    result = autopilot_ledger.rollup(tmp_path, observability_dir=obs)

    # dropping `failed` would make codex's denominator 4
    assert result.by_model["codex"]["calls"] == 5
    assert result.by_model["codex"]["failed"] == 1
    # merging models would erase this row entirely
    assert result.by_model["antigravity"]["skipped"] == 1
    # `failed` is inside the loss numerator: (0 skipped + 1 failed) / 5 calls
    assert result.by_model["codex"]["loss_rate"] == 1 / 5
    # the exclusions the report applied are published, so the numbers carry their provenance
    assert [e["value"] for e in result.exclusions["applied"]] == ["test-pollution-1"]
    assert result.exclusions["rows_dropped"] == 1


def test_ac_001_the_rollup_path_is_the_named_deliverable() -> None:
    """The artifact path is fixed by ADR-002 and reuses an existing DELIVERABLE_PREFIXES entry.

    A golden, not a magic value: the literal traces to SPEC Constraints, and the prefix has to be
    one already in `worktree.DELIVERABLE_PREFIXES` or the file is gitignored and never lands.
    """
    assert autopilot_ledger.ROLLUP_RELPATH == "work-docs/BASELINE-ledger-rollup.md"


def test_ac_001_the_document_is_a_function_of_every_aggregate_axis(tmp_path: Path) -> None:
    """Per-axis differential — the render must change when ANY axis it claims to carry changes.

    Substring containment cannot express "this number is the total": `"6" in body` is satisfied by
    any 2026 date, and `"0.2"` by `0.25`. Two prior rounds failed on exactly that, one level apart.
    So the claim is re-bound as a differential instead: perturb one axis at a time and require the
    document's numeric multiset to move.

    **Both perturbations hold the total at 6 on purpose.** A render that prints only the total
    passes neither, and a render that omits an axis entirely fails the perturbation for that axis.
    Nothing here pins layout — not where a number sits, not its formatting, not the table shape.
    Formatting IS still asserted exactly, but on the object (`loss_rate == 1 / 5` below), where a
    float comparison is meaningful.
    """
    obs = _observability(tmp_path)
    result = autopilot_ledger.rollup(tmp_path, observability_dir=obs)
    baseline = _numbers(autopilot_ledger.render_rollup(result))

    # axis 1 — per-model: codex invoked 4 -> 3, total untouched
    per_model = dict(result.by_model)
    per_model["codex"] = {**per_model["codex"], "invoked": 3}
    moved_model = dataclasses.replace(result, by_model=per_model)

    # axis 2 — per-stage: the split moves, total untouched
    moved_stage = dataclasses.replace(result, by_stage={"plan": 3, "review": 3})

    assert _numbers(autopilot_ledger.render_rollup(moved_model)) != baseline, (
        "the rendered document did not change when the per-model counts did — "
        "it is not carrying that axis"
    )
    assert _numbers(autopilot_ledger.render_rollup(moved_stage)) != baseline, (
        "the rendered document did not change when the per-stage split did — "
        "it is not carrying that axis"
    )


def test_ac_002_a_lifetime_window_reports_every_dangling_authorization(tmp_path: Path) -> None:
    """The enumeration is lifetime-wide; the collapse it reused is a SESSION policy (review P1-2).

    `find_unconfirmed_authorization` banks at most one outstanding authorization per stage, which is
    correct inside a session — a retried stage re-authorizes, and banking both would leave a
    confirmable slot for an unrelated later entry. Over the whole ledger it erases evidence: two
    authorizations for the same stage in different sessions are two independent events, so any later
    successful advance pops the earlier dangling one and the section prints `- none`.

    The fixture is that exact shape: authorize `plan` (never entered), authorize `plan` again, enter
    `plan`. One real dangling authorization survives, and the pre-fix code reported zero.
    """
    obs = tmp_path / ".claude" / "observability"
    _write_jsonl(
        obs / "auto-advance.jsonl",
        [
            {"event": "advance_authorized", "to": "plan", "ts": "2026-09-01T00:00:00+00:00"},
            {"event": "advance_authorized", "to": "plan", "ts": "2026-09-02T00:00:00+00:00"},
            {"event": "advance_entered", "to": "plan", "ts": "2026-09-02T00:01:00+00:00"},
        ],
    )

    dangling = autopilot_ledger.dangling_authorizations(tmp_path, observability_dir=obs)

    assert len(dangling) == 1, (
        f"expected the one unconfirmed authorization to survive, got {len(dangling)} — the session "
        "collapse is still being applied to a lifetime window"
    )
    # The entry confirms the OLDEST outstanding authorization (greedy oldest-to-oldest, ADR-005), so
    # the one left dangling is the LATER row. Asserted rather than assumed: I expected the earlier
    # one and was wrong, and pinning the convention is what stops a future pairing change from
    # silently relabelling which event is the defect.
    assert dangling[0]["ts"] == "2026-09-02T00:00:00+00:00", (
        "the entry did not confirm the oldest authorization — the greedy pairing convention moved"
    )


def test_ac_001_the_rendered_wrapup_produces_the_rollup_before_staging_it() -> None:
    """A manifest entry for a file no template writes is AC-014's defect in AC-001's clothes.

    Review finding P1-4: `wrapup.md.j2` staged `work-docs/BASELINE-ledger-rollup.md` as
    `--optional`, and nothing in any rendered command generated it. On every harness where an
    operator does not type the CLI by hand the file never exists, `wrapup_land` records
    `absent-optional`, and ADR-002's "survives a clone" guarantee is unreachable. Ordering matters
    as much as presence: staging before the producer would stage nothing.
    """
    template = (
        Path(__file__).parents[2]
        / "src"
        / "harness_maker"
        / "templates"
        / "stages"
        / "wrapup.md.j2"
    ).read_text(encoding="utf-8")

    producer = template.find("autopilot_ledger rollup")
    stager = template.find(autopilot_ledger.ROLLUP_RELPATH)

    assert producer != -1, (
        "no rendered command produces the roll-up, so the manifest stages a file nothing writes"
    )
    assert stager != -1, "the manifest no longer stages the roll-up"
    assert producer < stager, (
        "the roll-up is staged before it is produced, so the first wrapup stages nothing"
    )


def test_ac_002_a_dangling_authorization_is_reported(tmp_path: Path) -> None:
    """AC-002 predicate: exactly the one authorization no entry confirmed."""
    obs = _observability(tmp_path)

    dangling = autopilot_ledger.dangling_authorizations(tmp_path, observability_dir=obs)

    assert len(dangling) == 1
    assert dangling[0]["to"] == "execute"


def test_ac_002_a_fully_confirmed_ledger_reports_nothing(tmp_path: Path) -> None:
    """The suppression arm, on its OWN fixture — every authorization has a matching entry.

    This is what makes AC-002 bind the *reader* rather than the computation. The shared fixture
    places its one unconfirmed authorization LAST, so a pairing-blind implementation ("return the
    last `advance_authorized` row") satisfies the positive arm while never reading
    `advance_entered` at all. Here there is no last unconfirmed row to return, so that
    implementation reports `execute` and fails.
    """
    obs = tmp_path / ".claude" / "observability"
    _write_jsonl(
        obs / "auto-advance.jsonl",
        [
            {"event": "advance_authorized", "to": "spec", "ts": "2026-09-08T04:00:00+00:00"},
            {"event": "advance_entered", "to": "spec", "ts": "2026-09-08T04:01:00+00:00"},
            {"event": "advance_authorized", "to": "execute", "ts": "2026-09-08T04:02:00+00:00"},
            {"event": "advance_entered", "to": "execute", "ts": "2026-09-08T04:03:00+00:00"},
        ],
    )

    dangling = autopilot_ledger.dangling_authorizations(tmp_path, observability_dir=obs)

    assert dangling == []


def test_ac_001_the_rollup_reads_the_base_repo_not_the_worktree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Rows at base, deliverable where wrapup commits — a differential, because I shipped the bug.

    Found by RUNNING the CLI from inside `.worktrees/<slug>/` during review, not by reading: the
    reader took `Path.cwd()`, found the worktree's gitignored (and empty) `.claude/observability/`,
    and wrote `No rows.` into a document `/hm:wrapup` commits — while the base repo held
    `second-opinion.jsonl`, `auto-advance.jsonl`, `stage-agents.jsonl` and `stage-spans.jsonl`.
    Every test here passed, because every one of them passes `observability_dir` explicitly. That
    is the same absent-case shape as the earlier `Path(DEFAULT_OBSERVABILITY_DIR)` defect this file
    already records, one level up.

    The differential is what makes this a guard: `base` holds rows, `worktree` holds none, and the
    document written under `worktree` must carry `base`'s numbers. Revert the CLI to
    `write_rollup(root)` and the body becomes the absence notice, so the assertion fails.
    """
    base = tmp_path / "base"
    worktree = base / ".worktrees" / "slug"
    (worktree).mkdir(parents=True)
    _observability(base)  # rows + exclusions, at BASE
    (worktree / ".claude" / "observability").mkdir(parents=True)  # present, and empty

    monkeypatch.setattr("harness_maker.second_opinion_invoke.resolve_base_root", lambda _cwd: base)

    assert autopilot_ledger.main(["rollup", "--write", "--root", str(worktree)]) == 0

    written = worktree / autopilot_ledger.ROLLUP_RELPATH
    assert written.is_file(), "the deliverable did not land in the tree wrapup will commit"
    body = written.read_text(encoding="utf-8")

    assert verifier_discrimination.ABSENCE_NOTICE not in body, (
        "the roll-up reported an absence while the base repo held rows — the reader is still "
        "resolving against the caller's cwd"
    )
    assert _numbers(body), "the document carries no numbers, so it aggregated nothing"
    assert not (base / autopilot_ledger.ROLLUP_RELPATH).exists(), (
        "the deliverable landed at BASE, where this worktree's wrapup will not commit it"
    )


def test_the_rollup_path_is_named_in_wrapup_lands_manifest() -> None:
    """The staging half of AC-001, guarded continuously rather than by a one-time shell check.

    Phase 1's exit criterion checks `git ls-tree` once. Without this test the `--optional` entry
    could be dropped from the template later and nothing would notice until measurements silently
    stopped landing on a `worktree.enabled: false` harness — the `worktree-sweep` row records
    `skipped-not-isolated` when the worktree IS the base, so the manifest entry is the only thing
    that stages it there.
    """
    template = (
        Path(__file__).parents[2]
        / "src"
        / "harness_maker"
        / "templates"
        / "stages"
        / "wrapup.md.j2"
    )
    needle = f"--optional {autopilot_ledger.ROLLUP_RELPATH}"
    invocations = [
        line
        for line in template.read_text(encoding="utf-8").splitlines()
        if "hm wrapup_land --worktree" in line
    ]

    # UNIVERSAL, not aggregate. `count(needle) == 2` is satisfied by any distribution summing to
    # two -- including one codex-branch hit plus one prose mention, which leaves the non-codex
    # branch (the one this repo renders) unstaged. That is the repo's signature two-halves-one-
    # checked failure. Quantifying over the invocation lines themselves is immune to a third
    # variant, to a macro extraction, and to prose that merely discusses the manifest.
    assert invocations, "no `hm wrapup_land --worktree` invocation found — the subject moved"
    for line in invocations:
        assert needle in line, f"invocation does not stage the roll-up: {line.strip()[:120]}"


def test_rollup_on_an_empty_observability_dir_is_absence_not_health(tmp_path: Path) -> None:
    """An empty ledger set must not read as a clean bill of health (AC-004's shape, locally).

    Phase 2 owns the property over every reader; this is the arm for the reader Phase 1 adds,
    asserted here because a reader added in this phase would otherwise fall outside whatever
    set Phase 2 derives.
    """
    empty_obs = tmp_path / "empty" / ".claude" / "observability"
    empty_obs.mkdir(parents=True)
    populated_obs = _observability(tmp_path / "populated")

    empty = autopilot_ledger.rollup(tmp_path / "empty", observability_dir=empty_obs)
    populated = autopilot_ledger.rollup(tmp_path / "populated", observability_dir=populated_obs)

    assert empty.total == 0
    assert empty.by_model == {}
    # A DIFFERENTIAL, not a phrase. `"absence of evidence" in body` would be a wording pin: an
    # implementer writing "no evidence recorded" turns it red for no defect. The property AC-004
    # actually names is that absence must be DISTINGUISHABLE from health, and that is what this
    # asserts -- without constraining a single word of how the render says it.
    assert autopilot_ledger.render_rollup(empty) != autopilot_ledger.render_rollup(populated)


def test_the_writer_puts_the_rendered_body_at_the_named_path(tmp_path: Path) -> None:
    """`rollup` + `render_rollup` with no caller is the AC-014 defect, so the writer is bound too.

    AC-001's committed-path conjunct can only ever become true if something writes the file. A
    correct helper wired to nothing is the defect, not the fix.
    """
    obs = _observability(tmp_path)

    written = autopilot_ledger.write_rollup(tmp_path, observability_dir=obs)

    assert written == tmp_path / autopilot_ledger.ROLLUP_RELPATH
    assert written.is_file()
    expected = autopilot_ledger.render_rollup(
        autopilot_ledger.rollup(tmp_path, observability_dir=obs)
    )
    assert written.read_text(encoding="utf-8") == expected


def test_the_default_observability_dir_resolves_against_project_root(tmp_path: Path) -> None:
    """The absent-case arm — every other test passes `observability_dir`, so nothing walked this.

    The first implementation defaulted to a bare relative `Path(".claude/observability")`, which
    reads the CWD rather than `project_root`. Every test above still passed. This is the
    absent-case class CLAUDE.md records at count:8: a fixture that only exercises the present case
    means the code never fires for the data that motivated it.
    """
    _observability(tmp_path)  # writes under tmp_path/.claude/observability

    result = autopilot_ledger.rollup(tmp_path)

    assert result.total == 6
    assert result.by_stage == {"plan": 2, "review": 4}


def test_the_rollup_subcommand_is_registered() -> None:
    """A subparser the registry does not declare is refused, so both sites move together.

    `command_registry` is the producer-consumer parity guard for this module's argv surface;
    adding a subcommand to `main()` alone would be refused at the guard with no test noticing.
    """
    from harness_maker import command_registry

    assert "rollup" in command_registry.MODULES["autopilot_ledger"].subcommands
