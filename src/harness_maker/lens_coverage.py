"""Compute a round's mandatory-lens coverage verdict from main-loop-written result files."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from harness_maker import command_registry
from harness_maker.conditional_router import ALL_LENSES, mandatory_lenses


def exercised_lenses(round_dir: Path, run_id: str) -> set[str]:
    """Build the exercised set from files that exist AND parse AND self-identify AND are OURS.

    Fail-closed **as to liveness** (SPEC AC-011, which was demoted from the stronger claim):
    a lens is exercised only if its result file is
    present, is valid JSON, and carries a ``lens`` field matching both its filename stem and a
    known lens name. Absent, unreadable, malformed, mislabelled and unknown-lens files all
    fall out of the set rather than into it.

    The distinction matters because the failure this gate exists to catch — a dispatch that
    never happened — produces exactly an absent or empty file. Anything that treats "cannot
    tell" as "exercised" converts a delivery failure into a clean bill of health, which is the
    outcome the whole mechanism is built to prevent.

    ``run_id`` closes the hole the ``<round>`` keying alone does not (F2, demonstrated
    2026-08-15). The directory is keyed by slug and round, so re-running ``/hm:review`` on the
    same slug lands in the SAME directory. Measured: five files from invocation 1, then an
    invocation 2 in which only one lens returns — the verdict was `blocks_approval: false`,
    with four dead lenses vouched for by the previous run. That is precisely the silent false
    approval `round_dir`'s docstring claims the keying prevents; the keying separates a pass
    from a round, not one invocation from the next. A file whose ``run_id`` is absent or
    belongs to another invocation is therefore not evidence about this one.
    """
    # The full vocabulary, NOT the preset's mandatory set. A Side harness whose router pulled
    # `security` in produced a legitimate result file, and scoping this to the mandatory set
    # would discard it — `exercised` would under-report and `review_telemetry.lenses_exercised`
    # would lose a lens that actually ran. What the preset decides is what is REQUIRED, which
    # is `coverage_verdict`'s job; it is not a filter on what counts as a real result.
    known = set(ALL_LENSES)
    found: set[str] = set()
    if not round_dir.is_dir():
        return found
    for path in sorted(round_dir.glob("*.json")):
        stem = path.stem
        if stem not in known:
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(payload, dict):
            continue
        if payload.get("lens") != stem:
            continue
        if payload.get("run_id") != run_id:
            continue
        found.add(stem)
    return found


def coverage_verdict(
    round_dirs: Path | list[Path],
    run_id: str,
    preset: str = "Production",
) -> dict[str, object]:
    """The sole producer of the coverage verdict the rendered gate consumes.

    Takes the UNION across every round directory of one `/hm:review`. Coverage is cumulative
    over a review, not per round: the auto-fix loop re-spawns only the reviewers a fix touched,
    so a later round's directory legitimately holds one or two files.

    Round 2 of this change's own review found why this must be machine-computed. A per-round
    reading made a healthy review permanently unapprovable — round 1 delivers all five, round 2
    re-dispatches one, and the round-2 check reports the other four missing forever. The first
    repair said so in prose and left the CLI single-round, which was worse: the gate branches on
    the CLI's `blocks_approval`, and the template simultaneously forbade the model from
    substituting its own judgement for that field. The instruction and the tool disagreed.
    """
    dirs = [round_dirs] if isinstance(round_dirs, Path) else list(round_dirs)
    required = mandatory_lenses(preset)
    exercised: set[str] = set()
    for d in dirs:
        exercised |= exercised_lenses(d, run_id)
    missing = [lens for lens in required if lens not in exercised]
    return {
        "exercised": [lens for lens in ALL_LENSES if lens in exercised],
        "missing": missing,
        "blocks_approval": bool(missing),
        "preset": str(preset),
    }


def round_dir(results_dir: Path, slug: str, round_id: str, run_id: str) -> Path:
    """Results live under <results-dir>/<slug>/<run-id>/<round-id>/.

    ``round_id`` is a round number for a round and a pass id (``confirm-1`` / ``confirm-2``)
    for a confirmation pass. They share a namespace deliberately so that a pass can never
    inherit a round's files: reusing a round's directory would let a lens that failed during
    the pass be counted as exercised from the stale file, yielding ``blocks_approval: false``
    — a silent false approval produced by the coverage mechanism itself.

    ``run_id`` is in the PATH, not only in the file content, and the difference is the whole
    point. The content check (`exercised_lenses`) closes F2 only while the writer stamps the
    id correctly — and the writer is the model. Keying the directory makes the isolation
    structural: a second `/hm:review` on the same slug cannot see the first invocation's files
    at all, whatever it wrote inside them. Both checks stay; this one does not depend on
    anything a model chose to put in a file.
    """
    candidate = (results_dir / slug / run_id / round_id).resolve()
    root = results_dir.resolve()
    if not candidate.is_relative_to(root):
        # `--slug ../../tmp/fake` pointed the checker at an arbitrary directory. The security
        # reviewer judged this un-exploitable (read-only, and the caller who supplies the
        # argument also writes the result files) and the cross-model reviewer called it P1;
        # the disagreement is recorded in the REVIEW. Containment is two lines and removes the
        # question, which is cheaper than being right about it.
        msg = f"results path escapes {root}: slug={slug!r} run={run_id!r} round={round_id!r}"
        raise ValueError(msg)
    return candidate


def main(argv: list[str] | None = None) -> int:
    """CLI entry: ``hm lens_coverage check --results-dir <d> --slug <s> --round <n>``.

    The misroute guard runs BEFORE parsing: an argparse subparser rejects an unknown verb with
    `SystemExit(2)` of its own, which would pre-empt the did-you-mean redirect entirely.
    """
    guard = command_registry.guard_or_none("lens_coverage", argv)
    if guard is not None:
        return guard
    args = list(sys.argv[1:]) if argv is None else list(argv)
    if not args or args[0] != "check":
        sys.stderr.write(
            "usage: hm lens_coverage check --results-dir <dir> --slug <slug> --round <n> "
            "[--round <n> …] "
            "--run-id <id> [--preset Side|Production]\n"
        )
        return 2

    parser = argparse.ArgumentParser(prog="hm lens_coverage check", add_help=False)
    parser.add_argument("--results-dir", required=True, type=Path)
    parser.add_argument("--slug", required=True)
    parser.add_argument(
        "--round",
        required=True,
        dest="round_ids",
        action="append",
        help=(
            "repeatable: pass EVERY round of this review, so coverage is the union. A single "
            "round is not the review's coverage — the auto-fix loop re-spawns only the "
            "reviewers a fix touched."
        ),
    )
    parser.add_argument(
        "--run-id",
        required=True,
        dest="run_id",
        help="this /hm:review invocation's id; a result file from another invocation is ignored",
    )
    parser.add_argument(
        "--preset",
        default="Production",
        help=(
            "the harness preset. Production requires all seven lenses; Side requires the four "
            "core categories and lets the router decide the three domain lenses. An unknown "
            "value resolves to Production — more mandatory coverage is the fail-closed side. "
            "`--round` also accepts a confirmation-pass id (confirm-1 / confirm-2)."
        ),
    )
    # RETIRED, still accepted (ADR-004). A harness rendered by 0.53.0 keeps passing these
    # until its owner re-renders, and argparse exits 2 on an unknown argument — which would
    # land at /hm:review Step 3 and lose the review. Suppressed from --help so they are not
    # advertised, absorbed so they do not break, and warned about so "absorbed" is not silent.
    # `tests/unit/test_lens_coverage_retired_flags.py` removes them at 0.55.0.
    parser.add_argument("--diff-files", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--rev", help=argparse.SUPPRESS)
    try:
        opts = parser.parse_args(args[1:])
    except SystemExit:
        return 2

    if opts.diff_files or opts.rev:
        sys.stderr.write(
            "lens_coverage: --diff-files/--rev are retired and ignored — the repo-access "
            "probe was removed. Re-render the harness (/harness-maker:make --update) so the "
            "rendered command stops passing them.\n"
        )

    try:
        dirs = [round_dir(opts.results_dir, opts.slug, r, opts.run_id) for r in opts.round_ids]
    except ValueError as exc:
        # The containment check raises. Escaping as a traceback left the caller with no JSON
        # at all, while the template calls this the sole producer of the verdict.
        sys.stderr.write(f"lens_coverage: {exc}\n")
        return 2
    verdict = coverage_verdict(dirs, opts.run_id, opts.preset)
    sys.stdout.write(json.dumps(verdict, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
