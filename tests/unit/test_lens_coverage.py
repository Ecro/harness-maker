"""Phase 1 — the coverage verdict is computed by the entrypoint the template calls."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from harness_maker.conditional_router import MANDATORY_LENSES
from harness_maker.lens_coverage import coverage_verdict, exercised_lenses, main, round_dir

#: The run id every helper below stamps. A second value appears only in the F2 tests, where
#: "written by another invocation" is the property under test.
RUN = "run-a"


def _write_result(d: Path, lens: str, *, body: object | None = None, run_id: str = RUN) -> None:
    d.mkdir(parents=True, exist_ok=True)
    payload = {"lens": lens, "run_id": run_id, "findings": []} if body is None else body
    (d / f"{lens}.json").write_text(json.dumps(payload), encoding="utf-8")


def test_the_known_lens_vocabulary_is_seven_and_holds_no_retired_name() -> None:
    """Seven, not nine and never eleven.

    `correctness`/`failure` were retired by the axis change; `complexity`/`naming` were then
    merged into `design`/`consistency` on measured redundancy (2026-08-16 run). A retired name
    reappearing means two axes are live at once, which is how the set drifts to eleven.
    """
    assert len(MANDATORY_LENSES) == 7
    assert len(set(MANDATORY_LENSES)) == 7
    for retired in ("correctness", "failure", "complexity", "naming"):
        assert retired not in MANDATORY_LENSES


def test_every_mandatory_lens_present_does_not_block(tmp_path: Path) -> None:
    for lens in MANDATORY_LENSES:
        _write_result(tmp_path, lens)
    verdict = coverage_verdict(tmp_path, RUN)
    assert verdict["blocks_approval"] is False
    assert verdict["missing"] == []


@pytest.mark.parametrize("dropped", MANDATORY_LENSES)
def test_any_absent_lens_blocks(tmp_path: Path, dropped: str) -> None:
    for lens in MANDATORY_LENSES:
        if lens != dropped:
            _write_result(tmp_path, lens)
    verdict = coverage_verdict(tmp_path, RUN)
    assert verdict["blocks_approval"] is True
    assert verdict["missing"] == [dropped]


def test_unparseable_file_is_not_exercised(tmp_path: Path) -> None:
    for lens in MANDATORY_LENSES:
        _write_result(tmp_path, lens)
    (tmp_path / "security.json").write_text("{not json", encoding="utf-8")
    assert coverage_verdict(tmp_path, RUN)["missing"] == ["security"]


def test_mislabelled_file_is_not_exercised(tmp_path: Path) -> None:
    """A file whose `lens` field disagrees with its name cannot vouch for either lens."""
    for lens in MANDATORY_LENSES:
        _write_result(tmp_path, lens)
    _write_result(tmp_path, "tests", body={"lens": "robustness", "findings": []})
    assert coverage_verdict(tmp_path, RUN)["missing"] == ["tests"]


def test_unknown_lens_file_cannot_pad_coverage(tmp_path: Path) -> None:
    for lens in MANDATORY_LENSES:
        if lens != "robustness":
            _write_result(tmp_path, lens)
    _write_result(tmp_path, "performance")
    assert coverage_verdict(tmp_path, RUN)["missing"] == ["robustness"]


def test_empty_directory_blocks(tmp_path: Path) -> None:
    verdict = coverage_verdict(tmp_path, RUN)
    assert verdict["blocks_approval"] is True
    assert verdict["exercised"] == []


def test_absent_directory_blocks(tmp_path: Path) -> None:
    assert coverage_verdict(tmp_path / "never-created", RUN)["blocks_approval"] is True


def test_a_confirmation_pass_never_inherits_a_round_directory(tmp_path: Path) -> None:
    """The defect this keying exists to prevent: a silent false approval.

    Round 3 exercised every mandatory lens. The first confirmation pass then loses one lens to
    a dispatch failure. If the pass shared round 3's directory the stale file would vouch for
    the lens that never ran, and `blocks_approval` would come back False — the coverage mechanism
    itself certifying coverage it does not have.
    """
    results = tmp_path / "results"
    for lens in MANDATORY_LENSES:
        _write_result(round_dir(results, "slug", "3"), lens)

    for lens in MANDATORY_LENSES:
        if lens != "robustness":
            _write_result(round_dir(results, "slug", "confirm-1"), lens)

    assert coverage_verdict(round_dir(results, "slug", "3"), RUN)["blocks_approval"] is False
    assert coverage_verdict(round_dir(results, "slug", "confirm-1"), RUN)["blocks_approval"] is True


def test_cli_prints_the_verdict(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    for lens in MANDATORY_LENSES:
        if lens != "security":
            _write_result(round_dir(tmp_path, "slug", "confirm-2"), lens)
    rc = main(
        [
            "check",
            "--results-dir",
            str(tmp_path),
            "--slug",
            "slug",
            "--round",
            "confirm-2",
            "--run-id",
            RUN,
        ]
    )
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["blocks_approval"] is True
    assert payload["missing"] == ["security"]


def test_reachable_through_the_hm_dispatcher(tmp_path: Path) -> None:
    """AC-011's seam only exists if the template's actual command line runs.

    An in-process test of `coverage_verdict` passes whether or not `hm lens_coverage` is
    reachable — which is the whole failure mode this phase's exit criterion names.
    """
    for lens in MANDATORY_LENSES:
        _write_result(round_dir(tmp_path, "slug", "1"), lens)
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "harness_maker.hm",
            "lens_coverage",
            "check",
            "--results-dir",
            str(tmp_path),
            "--slug",
            "slug",
            "--round",
            "1",
            "--run-id",
            RUN,
        ],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["blocks_approval"] is False


# ── F2: a previous invocation's files are not evidence about this one ─────────


def test_f2_a_prior_invocation_cannot_vouch_for_a_dead_lens(tmp_path: Path) -> None:
    """The demonstrated hole: `<round>` keying does not separate invocation from invocation.

    Measured 2026-08-15 before the fix. `/hm:review` runs on a slug and every lens returns,
    writing one file each under `<slug>/1/`. The operator re-runs `/hm:review` on the same slug;
    round 1 lands in the SAME directory, and this time only `robustness` returns. Nothing
    clears the directory, so the verdict was `blocks_approval: false` with four dead lenses
    reported as exercised — the exact silent false approval `round_dir`'s own docstring claims
    the keying prevents.
    """
    for lens in MANDATORY_LENSES:
        _write_result(tmp_path, lens, run_id="invocation-1")

    # Invocation 2: one lens returns; the other four files are last time's.
    _write_result(tmp_path, "robustness", run_id="invocation-2")

    verdict = coverage_verdict(tmp_path, "invocation-2")
    assert verdict["exercised"] == ["robustness"]
    assert verdict["missing"] == [lens for lens in MANDATORY_LENSES if lens != "robustness"]
    assert verdict["blocks_approval"] is True


def test_f2_a_result_without_a_run_id_is_not_counted(tmp_path: Path) -> None:
    """Fail-closed on the absent case, which is how this field will most often be wrong.

    A legacy file, a hand-written one, or a main loop that forgot the key all produce a file
    with no `run_id`. Treating "cannot attribute" as "ours" restores the hole for exactly the
    inputs that predate the fix — the absent-case black hole this repo records at count:8.
    """
    _write_result(tmp_path, "security", body={"lens": "security", "findings": []})
    assert exercised_lenses(tmp_path, RUN) == set()


def test_f2_the_run_id_does_not_weaken_the_existing_checks(tmp_path: Path) -> None:
    """A matching run_id must not rescue a file that fails the lens-identity check."""
    _write_result(tmp_path, "security", body={"lens": "correctness", "run_id": RUN, "findings": []})
    assert exercised_lenses(tmp_path, RUN) == set(), (
        "a mislabelled file was accepted because its run_id matched"
    )


def test_the_results_path_cannot_escape_its_root(tmp_path: Path) -> None:
    """`--slug ../../tmp/fake` pointed the checker at an arbitrary directory.

    Recorded as a DISAGREEMENT in the round-1 review: the cross-model reviewer called it P1;
    the security reviewer read the same code and judged it un-exploitable (read-only, and the
    caller supplying the argument also writes the result files). Containment costs two lines,
    which is cheaper than continuing to be right about it.
    """
    with pytest.raises(ValueError, match="escapes"):
        round_dir(tmp_path, "../../etc", "1")
    with pytest.raises(ValueError, match="escapes"):
        round_dir(tmp_path, "/etc", "1")
    assert round_dir(tmp_path, "ok-slug", "1") == (tmp_path / "ok-slug" / "1").resolve()


def test_coverage_is_the_union_across_the_review_s_rounds(tmp_path: Path) -> None:
    """Round-2 P1. A per-round reading made a healthy review permanently unapprovable.

    The auto-fix loop re-spawns only the reviewers a fix touched, so a later round's directory
    holds one or two files. Round 1 delivers four, round 2 re-dispatches the fifth — a
    single-round check then reports the first four missing, `blocks_approval: true`, forever.

    The first repair said "take the union" in prose while leaving the CLI single-round, which
    was worse than the defect: the gate branches on the CLI's `blocks_approval`, and the same
    template forbids substituting the model's judgement for it. The union is computed here.
    """
    r1 = round_dir(tmp_path, "s", "1")
    r2 = round_dir(tmp_path, "s", "2")
    for lens in MANDATORY_LENSES:
        if lens != "security":
            _write_result(r1, lens)
    _write_result(r2, "security")

    assert coverage_verdict(r1, RUN)["blocks_approval"] is True
    assert coverage_verdict(r2, RUN)["blocks_approval"] is True

    union = coverage_verdict([r1, r2], RUN)
    assert union["missing"] == []
    assert union["blocks_approval"] is False


def test_the_cli_takes_round_repeatably(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    for lens in MANDATORY_LENSES:
        target = "1" if lens != "tests" else "2"
        _write_result(round_dir(tmp_path, "s", target), lens)
    rc = main(
        [
            "check",
            "--results-dir",
            str(tmp_path),
            "--slug",
            "s",
            "--round",
            "1",
            "--round",
            "2",
            "--run-id",
            RUN,
        ]
    )
    assert rc == 0
    assert json.loads(capsys.readouterr().out)["blocks_approval"] is False


def test_a_traversal_slug_exits_2_with_a_message_not_a_traceback(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The containment check raises; escaping `main` left the caller no JSON at all.

    The template calls this the sole producer of the coverage verdict, so a bare traceback
    leaves the gate with nothing to read and no documented handling.
    """
    rc = main(
        [
            "check",
            "--results-dir",
            str(tmp_path),
            "--slug",
            "../../etc",
            "--round",
            "1",
            "--run-id",
            RUN,
        ]
    )
    assert rc == 2
    assert "escapes" in capsys.readouterr().err
