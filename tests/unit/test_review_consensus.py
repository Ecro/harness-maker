"""Phases 3 and 4 — the tag table, the grade, and the disposition column.

After ADR-007 removed cross-lens consensus, these three functions are the entire false-positive
control. That is why they are tested as arithmetic rather than asserted as prose: a render-grep
proves the instruction reached the rendered command, never that the tag it produces is right, and
a wrong tag here is a P0 graded as an A.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from harness_maker.codex_adapter import finding_id
from harness_maker.codex_ledger import disposition_rows, load_ledger, rejection_rate
from harness_maker.review_consensus import (
    DISPOSITIONS,
    ConsensusError,
    build_round_record,
    compute_grade,
    grade_effect,
    grade_from_findings,
    rereview_plan,
    tag_finding,
    validate_disposition,
)


def _lens(name: str) -> dict[str, str]:
    return {"source": name, "kind": "lens"}


def _model(name: str) -> dict[str, str]:
    return {"source": name, "kind": "cross-model"}


# ── AC-004: the golden table, verbatim from the machine SPEC ─────────────────

AC004_ROWS = [
    ([_lens("robustness")], "consensus-passed"),
    ([_lens("consistency"), _lens("design")], "consensus-passed"),
    ([_model("codex")], "manual-only"),
    ([_model("codex"), _model("antigravity")], "consensus-passed"),
    ([_model("codex"), _lens("security")], "consensus-passed"),
]


@pytest.mark.parametrize(("voices", "expected"), AC004_ROWS)
def test_single_lens_votes_crossmodel_keeps_k2(voices: list[dict[str, str]], expected: str) -> None:
    assert tag_finding(voices) == expected


def test_the_same_model_twice_is_one_voice() -> None:
    """Sources are deduped, so a re-invoked model cannot corroborate itself into a pass."""
    assert tag_finding([_model("codex"), _model("codex")]) == "manual-only"


def test_diverging_reasoning_demotes_a_cross_model_pair() -> None:
    """There, divergence does real work: nothing else is holding the finding up."""
    assert (
        tag_finding([_model("codex"), _model("antigravity")], reasoning_diverges=True)
        == "weak-consensus"
    )


def test_divergence_cannot_demote_a_solo_voice() -> None:
    """Divergence is a statement about two chains; there is no second chain to diverge from."""
    assert tag_finding([_lens("robustness")], reasoning_diverges=True) == "consensus-passed"


def test_the_table_is_monotonic_in_voices() -> None:
    """A second voice never produces a worse tag than the first earned alone (T-01).

    The pre-change rule demoted lens A + lens B to `weak-consensus` when their CONCLUDEs
    differed, while lens A alone passed — so two experts noticing one defect and describing it
    differently was punished. On an axis whose premise is that distinct categories see distinct
    things, that is the ordinary case, not the pathological one.
    """
    ranks = {"manual-only": 0, "weak-consensus": 1, "consensus-passed": 2}
    for diverges in (False, True):
        solo = ranks[tag_finding([_lens("robustness")], reasoning_diverges=diverges)]
        pair = ranks[
            tag_finding([_lens("robustness"), _lens("consistency")], reasoning_diverges=diverges)
        ]
        assert pair >= solo, f"a second lens voice made it worse (diverges={diverges})"


@pytest.mark.parametrize(
    "voices",
    [[{"source": "", "kind": "lens"}], [{"source": "x", "kind": "reviewer"}], ["naming"]],
)
def test_a_malformed_voice_is_loud(voices: list[object]) -> None:
    """Never a silent drop: a dropped voice moves a grade with no diagnostic."""
    with pytest.raises(ConsensusError):
        tag_finding(voices)


def test_a_voice_less_finding_is_manual_only_not_an_error() -> None:
    """The stage PRODUCES these, so raising took the whole batch down with them.

    Step 4d tells the model to leave an `unresolved` cross-model finding's voices out of the
    array while Step 4e requires every finding to carry a disposition — so it stays in the file
    with no voices. Raising made one such entry abort `tag` with exit 2 and no output, which then
    fed an untagged file into `grade`. `manual-only` is the tag the skill already specifies for
    that class.
    """
    assert tag_finding([]) == "manual-only"


# ── AC-004 provenance: `lens` is metadata, never part of the merge key ───────


def test_finding_carries_lens_provenance() -> None:
    """The tag rule is undecidable without it — six lenses share one agent name."""
    findings = [
        {
            "lens": "consistency",
            "severity": "P2",
            "tag": "consensus-passed",
            "disposition": "accepted",
        },
        {"lens": "design", "severity": "P2", "tag": "consensus-passed", "disposition": "accepted"},
    ]
    assert {f["lens"] for f in findings} == {"consistency", "design"}
    # Two different lenses, one agent: `source` alone would collapse them.
    assert tag_finding([_lens(f["lens"]) for f in findings]) == "consensus-passed"


def test_finding_id_unchanged_by_lens_field() -> None:
    """Putting `lens` into the id would break the round-2 voter merge (gate skill §1).

    Two arms, because the interesting failure is a future edit rather than today's value. The
    first pins the id for the four inputs the key is built from; the second pins the parameter
    list, which is what an implementer would have to widen to smuggle `lens` in — and widening
    it is exactly the change that silently re-keys every ledger row and frozen-set join.
    """
    import inspect

    a = finding_id("code-reviewer", "src/x.py", 12, "boom")
    assert a == finding_id("code-reviewer", "src/x.py", 12, "boom")
    assert a != finding_id("code-reviewer", "src/x.py", 13, "boom")
    assert list(inspect.signature(finding_id).parameters) == ["source", "file", "line", "message"]


# ── AC-005: P2 never moves the grade ────────────────────────────────────────


def test_p2_only_findings_grade_a() -> None:
    assert compute_grade(p0_count=0, p1_count=0, p2_count=7) == "A"


@pytest.mark.parametrize(
    ("p0", "p1", "expected"),
    [(0, 0, "A"), (0, 1, "B"), (0, 2, "B"), (0, 3, "C"), (1, 9, "D"), (2, 0, "D"), (3, 0, "F")],
)
def test_the_published_grade_table_is_unchanged(p0: int, p1: int, expected: str) -> None:
    """Differential arm: the letters come from the table review.md.j2 already published."""
    assert compute_grade(p0_count=p0, p1_count=p1) == expected


# ── AC-007: a rejection carries an authority ────────────────────────────────

AC007_ROWS = [
    ("rejected", None, False),
    ("rejected", "AC-004", True),
    ("rejected", "docstring:src/x.py:parse", True),
    ("rejected", "no-contract", False),
    ("unresolved", "no-contract", True),
]


@pytest.mark.parametrize(("disposition", "authority", "valid"), AC007_ROWS)
def test_rejection_requires_authority(disposition: str, authority: str | None, valid: bool) -> None:
    assert validate_disposition(disposition, authority) is valid


def test_no_contract_cannot_justify_anything_but_unresolved() -> None:
    """`no-contract` is the recorded ABSENCE of an authority, not a weak one.

    A harness with no SPEC and no docstring has nothing to reject against; the honest record is
    `unresolved`, which still counts toward the grade. Admitting `no-contract` on `rejected`
    would make self-grading sufficient to clear a P0, which is exactly what ADR-002 forbids.
    """
    for disposition in ("accepted", "rejected", "duplicate"):
        assert validate_disposition(disposition, "no-contract") is False


def test_an_unknown_disposition_is_rejected() -> None:
    assert validate_disposition("wontfix", "AC-001") is False
    assert validate_disposition(None) is False


# ── AC-008: only an AC-cited rejection clears the grade ─────────────────────

AC008_ROWS = [
    ("P0", "rejected", "AC-004", {"counted": False, "human_review_needed": False}),
    ("P0", "rejected", "docstring:src/x.py:parse", {"counted": True, "human_review_needed": True}),
    ("P1", "rejected", "docstring:src/y.py:send", {"counted": True, "human_review_needed": True}),
    ("P0", "accepted", None, {"counted": True, "human_review_needed": False}),
]


@pytest.mark.parametrize(("severity", "disposition", "authority", "expected"), AC008_ROWS)
def test_only_ac_cited_rejection_clears_grade(
    severity: str, disposition: str, authority: str | None, expected: dict[str, bool]
) -> None:
    assert grade_effect(severity, disposition, authority) == expected


def test_an_ac_cited_rejection_actually_moves_the_letter() -> None:
    """The escape hatch has to reach the grade, not just the effect dict."""
    p0 = {"severity": "P0", "tag": "consensus-passed", "disposition": "accepted"}
    assert grade_from_findings([p0])["grade"] == "D"
    cleared = {**p0, "disposition": "rejected", "authority": "AC-004"}
    assert grade_from_findings([cleared])["grade"] == "A"
    assert grade_from_findings([cleared])["human_review_needed"] is False


def test_a_docstring_cited_rejection_does_not_clear_the_letter() -> None:
    finding = {
        "severity": "P0",
        "tag": "consensus-passed",
        "disposition": "rejected",
        "authority": "docstring:src/x.py:parse",
    }
    result = grade_from_findings([finding])
    assert result["grade"] == "D"
    assert result["human_review_needed"] is True


def test_a_severe_manual_only_finding_still_needs_a_human() -> None:
    """The unverified-severe scan survives the solo-lens vote."""
    result = grade_from_findings(
        [{"severity": "P1", "tag": "manual-only", "disposition": "accepted"}]
    )
    assert result["grade"] == "A"
    assert result["human_review_needed"] is True


# ── AC-006: every finding carries exactly one disposition ───────────────────


@pytest.mark.parametrize(
    "findings",
    [
        [],
        [{"id": "a", "severity": "P0", "disposition": "accepted"}],
        # A round with no fix step: nothing arrives dispositioned.
        [{"id": "a", "severity": "P2"}, {"id": "b", "severity": "P1"}],
        # auto_fix disabled: the fix-selection step never ran, so a producer living there
        # would have seen none of these.
        [{"id": "a", "severity": "P3", "tag": "manual-only"}],
        # An unrecordable pair must still leave with a disposition.
        [{"id": "a", "severity": "P0", "disposition": "rejected", "authority": None}],
        [{"id": "a", "severity": "P0", "disposition": "wontfix"}],
    ],
)
def test_every_finding_has_disposition(findings: list[dict[str, object]]) -> None:
    record = build_round_record(findings)
    assert len(record.findings) == len(findings)
    assert all(f["disposition"] in DISPOSITIONS for f in record.findings)


def test_a_missing_disposition_becomes_the_weakest_value_and_is_reported() -> None:
    """Fail-safe, not fail-silent: `unresolved` counts and raises the human-review flag."""
    record = build_round_record([{"id": "a", "severity": "P0", "tag": "consensus-passed"}])
    assert record.findings[0]["disposition"] == "unresolved"
    assert record.findings[0]["authority"] == "no-contract"
    assert record.errors
    assert "a" in record.errors[0]
    assert grade_from_findings(record.findings)["human_review_needed"] is True


def test_an_unrecordable_rejection_is_downgraded_not_honoured() -> None:
    """Otherwise an authority-less rejection would be the laundering path."""
    record = build_round_record(
        [{"id": "a", "severity": "P0", "tag": "consensus-passed", "disposition": "rejected"}]
    )
    assert record.findings[0]["disposition"] == "unresolved"
    assert grade_from_findings(record.findings)["grade"] == "D"


# ── AC-009: dispositions are ledgered and aggregable ────────────────────────

_LEDGER_FIXTURE = [
    # Two per-invocation rows — the skip-rate denominator, NOT findings.
    {"finding_ref": "n/a", "status": "invoked", "disposition": "accepted", "model": "codex"},
    {"finding_ref": "n/a", "status": "skipped", "disposition": "unresolved", "model": "codex"},
    # Four per-finding disposition rows: one rejected → 0.25.
    {"finding_ref": "f1", "status": "invoked", "disposition": "accepted", "model": "codex"},
    {"finding_ref": "f2", "status": "invoked", "disposition": "rejected", "model": "codex"},
    {"finding_ref": "f3", "status": "invoked", "disposition": "duplicate", "model": "codex"},
    {"finding_ref": "f4", "status": "invoked", "disposition": "unresolved", "model": "codex"},
]


@pytest.fixture
def ledger(tmp_path: Path) -> Path:
    p = tmp_path / "second-opinion.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in _LEDGER_FIXTURE) + "\n", encoding="utf-8")
    return p


def test_dispositions_ledgered(ledger: Path) -> None:
    assert rejection_rate(load_ledger(ledger)) == 0.25


def test_the_per_invocation_rows_are_excluded_from_the_rate(ledger: Path) -> None:
    """`finding_ref` is the only discriminator — both kinds carry `status: invoked`.

    Counting all six rows gives 1/6 ≈ 0.167. That is the denominator hazard this file has
    already hit once, so it is asserted rather than assumed.
    """
    assert len(disposition_rows(load_ledger(ledger))) == 4
    assert rejection_rate(load_ledger(ledger)) != pytest.approx(1 / 6)


def test_an_absent_ledger_is_an_empty_one(tmp_path: Path) -> None:
    assert load_ledger(tmp_path / "never-written.jsonl") == []
    assert rejection_rate([]) == 0.0


def test_a_torn_line_does_not_make_the_history_unreadable(tmp_path: Path) -> None:
    p = tmp_path / "l.jsonl"
    p.write_text(
        json.dumps(_LEDGER_FIXTURE[2]) + "\n" + '{"finding_ref": "f5", "disp',
        encoding="utf-8",
    )
    assert len(load_ledger(p)) == 1


# ── The re-review plan (created here, wired in Phase 6) ──────────────────────


@pytest.mark.parametrize(
    ("ratio", "threshold", "count"),
    [(0.00, 0.20, 0), (0.05, 0.20, 0), (0.20, 0.20, 1), (0.35, 0.20, 1)],
)
def test_the_threshold_boundary_is_inclusive(ratio: float, threshold: float, count: int) -> None:
    assert len(rereview_plan(ratio, threshold)) == count


def test_at_or_above_threshold_exactly_one_reviewer_is_dispatched() -> None:
    """One, not two: ADR-007 made a single lens sovereign, so K=2 no longer forces a pair."""
    assert len(rereview_plan(churn_ratio=0.35, threshold=0.20)) == 1


# ── The CLI seam the rendered stage actually calls ───────────────────────────


def _hm(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "harness_maker.hm", "review_consensus", *args],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


def test_reachable_through_the_hm_dispatcher(tmp_path: Path) -> None:
    """An in-process test passes whether or not the template's command line runs."""
    f = tmp_path / "findings.json"
    f.write_text(
        json.dumps([{"id": "a", "severity": "P0", "voices": [_lens("robustness")]}]),
        encoding="utf-8",
    )
    proc = _hm("tag", "--file", str(f))
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["findings"][0]["tag"] == "consensus-passed"


def test_the_record_verb_exits_nonzero_on_a_gap(tmp_path: Path) -> None:
    f = tmp_path / "findings.json"
    f.write_text(json.dumps([{"id": "a", "severity": "P0"}]), encoding="utf-8")
    proc = _hm("record", "--file", str(f))
    assert proc.returncode == 1
    assert json.loads(proc.stdout)["errors"]


def test_the_plan_verb_reports_the_comparison(tmp_path: Path) -> None:
    proc = _hm("plan", "--churn-ratio", "0.05", "--threshold", "0.20")
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["dispatches"] == []
    assert "0.05 < 0.20" in payload["reason"]


# ── The seam, end to end: the defect cluster that reached main on 2026-08-16 ──
#
# Every test above this line calls the LIBRARY. The P0 lived in the gap between the library and
# the three-verb chain the rendered stage prescribes — so these drive the CLI over one temp path,
# exactly as the template says to, and assert on what comes out.


@pytest.fixture
def chain(tmp_path: Path):  # type: ignore[no-untyped-def]
    """Write findings, then run tag → record → grade over ONE path, as the stage does."""
    path = tmp_path / "findings.json"

    def run(findings: list[dict[str, object]], *, spec: str | None = None) -> dict[str, object]:
        path.write_text(json.dumps(findings), encoding="utf-8")
        _hm("tag", "--file", str(path))
        _hm("record", "--file", str(path))
        args = ["grade", "--file", str(path)]
        if spec:
            args += ["--spec", spec]
        proc = _hm(*args)
        payload = json.loads(proc.stdout)
        payload["_exit"] = proc.returncode
        return payload

    return run


def test_the_chain_grades_p0s_it_was_given(chain) -> None:  # type: ignore[no-untyped-def]
    """The P0, as a test. Three consensus-passed P0s graded `A` before this.

    `tag` and `record` printed to stdout only while all three verbs were handed the same path, so
    `grade` re-read the untagged array, skipped every finding, and returned zero counts. The
    letter said the review could exit.
    """
    out = chain(
        [
            {"id": fid, "severity": "P0", "voices": [_lens(ln)], "disposition": "accepted"}
            for fid, ln in (("a", "robustness"), ("b", "security"), ("c", "design"))
        ]
    )
    assert out["grade"] == "F"
    assert out["counts"]["P0"] == 3


def test_grade_fails_closed_on_an_untagged_file() -> None:
    """The direction matters more than the letter: unknown input must never read as clean."""
    out = grade_from_findings([{"id": "a", "severity": "P0", "disposition": "accepted"}])
    assert out["grade"] != "A"
    assert out["human_review_needed"] is True
    assert out["errors"]


def test_an_unverifiable_ac_citation_cannot_clear_a_p0(tmp_path: Path) -> None:
    """`AC-999` parses exactly like `AC-004`; only the SPEC can tell them apart.

    Without this, clearing a P0 from the grade needed a well-formed string rather than an
    independent contract — which is the grade laundering ADR-002 exists to forbid.
    """
    spec = tmp_path / "s.machine.yaml"
    spec.write_text("ac:\n  - id: AC-004\n    title: t\n", encoding="utf-8")
    f = tmp_path / "f.json"

    def grade_with(authority: str) -> dict[str, object]:
        f.write_text(
            json.dumps(
                [
                    {
                        "id": "a",
                        "severity": "P0",
                        "tag": "consensus-passed",
                        "disposition": "rejected",
                        "authority": authority,
                    }
                ]
            ),
            encoding="utf-8",
        )
        proc = _hm("grade", "--file", str(f), "--spec", str(spec))
        out = json.loads(proc.stdout)
        out["_exit"] = proc.returncode
        return out

    phantom = grade_with("AC-999")
    assert phantom["grade"] == "D"
    assert phantom["_exit"] == 1

    real = grade_with("AC-004")
    assert real["grade"] == "A"
    assert real["_exit"] == 0


def test_without_a_spec_no_ac_citation_clears_the_grade(tmp_path: Path) -> None:
    """Fail-closed on the absent case: an unverifiable citation is not a verified one."""
    f = tmp_path / "f.json"
    f.write_text(
        json.dumps(
            [
                {
                    "id": "a",
                    "severity": "P0",
                    "tag": "consensus-passed",
                    "disposition": "rejected",
                    "authority": "AC-004",
                }
            ]
        ),
        encoding="utf-8",
    )
    out = json.loads(_hm("grade", "--file", str(f)).stdout)
    assert out["grade"] == "D"


def test_a_voice_less_finding_does_not_abort_the_batch(tmp_path: Path) -> None:
    """One entry used to take the whole round's tag column down with it, via exit 2."""
    f = tmp_path / "f.json"
    f.write_text(
        json.dumps(
            [
                {"id": "a", "severity": "P1", "voices": []},
                {"id": "b", "severity": "P0", "voices": [_lens("consistency")]},
            ]
        ),
        encoding="utf-8",
    )
    proc = _hm("tag", "--file", str(f))
    assert proc.returncode == 0
    assert [x["tag"] for x in json.loads(proc.stdout)["findings"]] == [
        "manual-only",
        "consensus-passed",
    ]


def test_the_tag_verb_honours_reasoning_diverges(tmp_path: Path) -> None:
    """`weak-consensus` was unreachable through the CLI the template calls the sole decider."""
    f = tmp_path / "f.json"
    f.write_text(
        json.dumps(
            [
                {
                    "id": "a",
                    "severity": "P1",
                    "reasoning_diverges": True,
                    "voices": [_model("codex"), _model("antigravity")],
                }
            ]
        ),
        encoding="utf-8",
    )
    assert json.loads(_hm("tag", "--file", str(f)).stdout)["findings"][0]["tag"] == (
        "weak-consensus"
    )


def test_tag_and_record_write_back_in_place(tmp_path: Path) -> None:
    """The in-place write IS the chain; without it each verb re-reads the original array."""
    f = tmp_path / "f.json"
    f.write_text(
        json.dumps([{"id": "a", "severity": "P2", "voices": [_lens("consistency")]}]),
        encoding="utf-8",
    )
    _hm("tag", "--file", str(f))
    assert json.loads(f.read_text())[0]["tag"] == "consensus-passed"
    _hm("record", "--file", str(f))
    assert json.loads(f.read_text())[0]["disposition"] in DISPOSITIONS


def test_a_non_mapping_finding_is_loud_not_dropped(tmp_path: Path) -> None:
    """A dropped finding satisfies AC-006's completeness invariant by not existing."""
    f = tmp_path / "f.json"
    f.write_text(json.dumps([{"id": "a", "severity": "P0"}, "not-a-finding"]), encoding="utf-8")
    assert _hm("record", "--file", str(f)).returncode == 2


def test_build_round_record_preserves_a_valid_disposition() -> None:
    """The one-sided oracle the tests lens caught: only the fail-safe direction was pinned.

    A mutant stamping every finding `unresolved`/`no-contract` passed the whole file, which would
    have killed AC-008's AC-cited escape on the only path the stage uses.
    """
    record = build_round_record(
        [
            {
                "id": "a",
                "severity": "P0",
                "tag": "consensus-passed",
                "disposition": "rejected",
                "authority": "AC-004",
            }
        ]
    )
    assert record.errors == []
    assert record.findings[0]["disposition"] == "rejected"
    assert record.findings[0]["authority"] == "AC-004"
    assert grade_from_findings(record.findings)["grade"] == "A"


# ── Round 2: the three P0s the repair round itself introduced ────────────────


def test_a_json_object_without_findings_is_refused_not_emptied(tmp_path: Path) -> None:
    """The write-back turned a lenient read into destruction of the target file.

    `_load` did `.get("findings", [])`, so `tag --file <any JSON object>` replaced that file's
    contents with `[]` at exit 0, and a following `grade` returned `A` over the wreckage.
    Measured 2026-08-16 against a settings-shaped file. The path is model-substituted out of
    template prose, so leniency here is not tolerance — it is deletion.
    """
    victim = tmp_path / "settings.json"
    original = json.dumps({"permissions": {"allow": ["Bash(uv:*)"]}}, indent=2)
    victim.write_text(original, encoding="utf-8")

    proc = _hm("tag", "--file", str(victim))

    assert proc.returncode == 2
    assert victim.read_text(encoding="utf-8") == original
    assert "no `findings` key" in proc.stderr


def test_the_envelope_survives_the_write_back(tmp_path: Path) -> None:
    """`{"findings": [...], "round": 2}` must not come back as a bare array."""
    f = tmp_path / "f.json"
    f.write_text(
        json.dumps(
            {"findings": [{"id": "a", "severity": "P2", "voices": [_lens("design")]}], "round": 2}
        ),
        encoding="utf-8",
    )
    _hm("tag", "--file", str(f))
    reloaded = json.loads(f.read_text(encoding="utf-8"))
    assert reloaded["round"] == 2
    assert reloaded["findings"][0]["tag"] == "consensus-passed"


@pytest.mark.parametrize("severity", ["critical", "p0", "P0 (blocker)", "", "high"])
def test_an_off_vocabulary_severity_cannot_grade_a(severity: str) -> None:
    """The fail-open moved one field over, onto the field that decides the letter.

    The tag column was closed; `severity` was still matched with `if severity in counts`, so
    `critical` or lowercase `p0` incremented nothing — three `consensus-passed` findings graded
    `A` with zero errors and exit 0. Same shape as the round-1 P0, one field along.
    """
    out = grade_from_findings(
        [
            {"id": i, "severity": severity, "tag": "consensus-passed", "disposition": "accepted"}
            for i in "abc"
        ]
    )
    assert out["grade"] == "F"
    assert out["counts"]["P0"] == 3
    assert out["human_review_needed"] is True
    assert len(out["errors"]) == 3


def test_a_legitimate_low_severity_still_grades_a() -> None:
    """The other half: fail-closed must not swallow the vocabulary it is protecting."""
    out = grade_from_findings(
        [{"id": "a", "severity": "P2", "tag": "consensus-passed", "disposition": "accepted"}] * 5
    )
    assert out["grade"] == "A"
    assert out["errors"] == []


@pytest.mark.parametrize("spec_state", ["missing", "malformed", "no-ac-list"])
def test_an_unusable_spec_degrades_rather_than_aborting_the_grade(
    tmp_path: Path, spec_state: str
) -> None:
    """`grade` used to exit 2 with NO payload for every harness without a machine SPEC.

    That is a first-class `dev_mode`, so the review's sole grade producer was unrunnable there and
    the gate had no letter to branch on — and `_verify_ac_citations`'s `known is None` branch,
    written for exactly this case, was unreachable from the only call site that ships. `None` is
    already the fail-closed value: nothing can be verified, so no AC-cited rejection clears.
    """
    spec = tmp_path / "s.machine.yaml"
    if spec_state == "malformed":
        spec.write_text("ac: [unclosed\n", encoding="utf-8")
    elif spec_state == "no-ac-list":
        spec.write_text("spec_slug: x\n", encoding="utf-8")

    f = tmp_path / "f.json"
    f.write_text(
        json.dumps(
            [
                {
                    "id": "a",
                    "severity": "P0",
                    "tag": "consensus-passed",
                    "disposition": "rejected",
                    "authority": "AC-004",
                }
            ]
        ),
        encoding="utf-8",
    )

    proc = _hm("grade", "--file", str(f), "--spec", str(spec))

    assert proc.stdout, "grade printed no payload at all"
    out = json.loads(proc.stdout)
    assert out["grade"] == "D", "an unverifiable AC citation must not clear the P0"
    assert out["errors"]
    assert proc.returncode == 1
