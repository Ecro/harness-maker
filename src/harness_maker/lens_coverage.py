"""Compute a round's mandatory-lens coverage verdict from main-loop-written result files."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from harness_maker import command_registry
from harness_maker.conditional_router import ALL_LENSES, mandatory_lenses


@dataclass(frozen=True)
class ProbeCheck:
    """What a `repo_probe` is checked against, and the ONLY way to say "check it".

    `None` in place of this object is how Side says *do not check* — never an empty
    `diff_files`, which would make "not in the diff" true of every path and turn the check
    into a silent no-op. That is the same absent-case class this repo has shipped eight times,
    arriving through a parameter list instead of a config key.

    `read_blob` returns a path's contents **at the reviewed revision**, so the working tree is
    never touched: the path comes from model output, and a tracked symlink is in `git ls-files`
    while resolving anywhere at all.
    """

    diff_files: frozenset[str]
    tracked: frozenset[str]
    read_blob: Callable[[str], str | None]

    def __post_init__(self) -> None:
        # An empty set makes "not in the diff" true of EVERY path, so this object would be a
        # check that silently checks nothing. The matcher cannot catch it downstream — given an
        # empty set a correct matcher has no way to know the quoted path was in the diff either
        # — so the refusal has to live where the object is built.
        if not self.diff_files:
            msg = (
                "ProbeCheck.diff_files is empty, which would accept every path as "
                "out-of-diff. To skip the probe check entirely, pass probe=None."
            )
            raise ValueError(msg)


#: Bound on what a probe may quote. A line number beyond a file and a multi-kilobyte `text`
#: are both nonsense from a reviewer and both cost something to check.
_MAX_PROBE_TEXT = 500


def _probe_ok(probe: object, check: ProbeCheck) -> bool:
    """Fail CLOSED on every shape question. "Cannot tell" must never mean "exercised"."""
    if not isinstance(probe, dict):
        return False

    status = probe.get("status")
    if status is not None:
        # The one escape: a diff touching every tracked file leaves nothing to quote. Verified
        # against the repository, never taken on the reviewer's word — otherwise it is a
        # one-line opt-out of the canary.
        return status == "no-out-of-diff-file" and not (check.tracked - check.diff_files)

    path, line, text = probe.get("path"), probe.get("line"), probe.get("text")
    if not isinstance(path, str) or not path:
        return False
    if not isinstance(line, int) or isinstance(line, bool) or line < 1:
        return False
    if not isinstance(text, str) or len(text) > _MAX_PROBE_TEXT:
        return False

    # The path is model output. Reject anything that is not a plain repo-relative path before
    # it reaches a reader — belt to the braces of reading the object store (R11).
    if path.startswith("/") or ".." in PurePosixPath(path).parts:
        return False
    if path not in check.tracked or path in check.diff_files:
        return False

    body = check.read_blob(path)
    if body is None:
        return False
    lines = body.splitlines()
    if line > len(lines):
        return False
    return lines[line - 1] == text


def exercised_lenses(round_dir: Path, run_id: str, *, probe: ProbeCheck | None) -> set[str]:
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
        if probe is not None and not _probe_ok(payload.get("repo_probe"), probe):
            # A lens that cannot show it read the repository did not deliver a usable result.
            # It becomes `missing`, which already blocks approval and already triggers a
            # re-dispatch — no second blocking reason is introduced.
            continue
        found.add(stem)
    return found


def coverage_verdict(
    round_dirs: Path | list[Path],
    run_id: str,
    preset: str = "Production",
    *,
    probe: ProbeCheck | None,
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
        exercised |= exercised_lenses(d, run_id, probe=probe)
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


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
    ).stdout


def build_probe_check(root: Path, rev: str, diff_files: frozenset[str]) -> ProbeCheck:
    """A `ProbeCheck` whose content comes from the OBJECT STORE, never the working tree.

    `git show <rev>:<path>` is the whole of R11. The probe's `path` is model output and a
    tracked symlink is in `git ls-files` while resolving anywhere at all; the object store
    cannot follow it and an `open()` on the tree can. Reading at `rev` also pins the evidence
    to the code under review rather than to whatever the tree happens to hold now — a probe
    quoting a line someone added after the review point is not evidence about the review.

    The git INDEX is deliberately not a source here either: staged-but-uncommitted content is
    no more the reviewed revision than the tree is. **Membership honours that too** — `tracked`
    comes from `git ls-tree -r <rev>`, not `git ls-files`. The first draft used `ls-files`,
    which reads the current index, while this docstring claimed the opposite; three reviewers
    caught it independently. It was not cosmetic: across auto-fix rounds the index moves while
    `rev` stays pinned, so a probe legitimately quoting a file tracked AT `rev` could be
    rejected — a false access-loss signal out of the access-loss detector.

    `-z` because a tracked filename may contain a newline, which is this repo's convention
    everywhere else it parses git output (`_parse_name_status`, `_parse_numstat`).
    """
    listing = _git(root, "ls-tree", "-r", "-z", "--name-only", rev)
    tracked = frozenset(p for p in listing.split("\0") if p)

    def read_blob(path: str) -> str | None:
        try:
            return _git(root, "show", f"{rev}:{path}")
        except subprocess.SubprocessError:
            # `SubprocessError`, not `CalledProcessError`: a 60s `TimeoutExpired` is not the
            # former, and `coverage_verdict` runs outside `main`'s try — so one probe naming a
            # real-but-slow path crashed the command three sites call to decide
            # `blocks_approval`, turning a fail-closed gate into an unavailable one. An
            # unreadable body already means "this lens did not deliver"; a slow one is that.
            return None

    return ProbeCheck(diff_files=diff_files, tracked=tracked, read_blob=read_blob)


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
    parser.add_argument(
        "--diff-files",
        type=Path,
        help=(
            "path to a file listing the diff's changed paths, one per line. REQUIRED under "
            "Production: an absent list is an error, never an empty set, because empty makes "
            "'not in the diff' true of every path and turns the probe check into a no-op."
        ),
    )
    parser.add_argument(
        "--rev",
        help="the reviewed revision; probe content is read from its blobs, not the work tree",
    )
    parser.add_argument("--root", type=Path, default=Path("."))
    try:
        opts = parser.parse_args(args[1:])
    except SystemExit:
        return 2

    # Side renders no probe requirement (ADR-005), so its result files carry none and the check
    # must not run — otherwise every Side review is permanently unapprovable.
    probe: ProbeCheck | None = None
    if str(opts.preset) != "Side":
        if not opts.diff_files or not opts.rev:
            # ABSENT is not EMPTY, and only one of them is an error. An empty `--diff-files`
            # file makes "not in the diff" true of every path and turns the check into a
            # silent no-op — `ProbeCheck.__post_init__` refuses to be built from one. Absent
            # flags mean a caller that predates the probe: a harness rendered before this
            # change, whose `review.md` has no flags to pass. Failing there would break every
            # un-re-rendered Production harness's review on the first run after a package
            # update, which is a worse outcome than the canary being off — and the warning is
            # what keeps "off" from being silent.
            sys.stderr.write(
                "lens_coverage: --diff-files/--rev absent under Production — the repo-access "
                "probe check is SKIPPED for this run. Re-render the harness "
                "(/harness-maker:make --update) so the rendered command passes them.\n"
            )
        else:
            try:
                listed = frozenset(
                    line.strip()
                    for line in opts.diff_files.read_text(encoding="utf-8").splitlines()
                    if line.strip()
                )
                probe = build_probe_check(opts.root, str(opts.rev), listed)
            except (OSError, ValueError, subprocess.SubprocessError) as exc:
                sys.stderr.write(f"lens_coverage: cannot build the probe check: {exc}\n")
                return 2

    try:
        dirs = [round_dir(opts.results_dir, opts.slug, r, opts.run_id) for r in opts.round_ids]
    except ValueError as exc:
        # The containment check raises. Escaping as a traceback left the caller with no JSON
        # at all, while the template calls this the sole producer of the verdict.
        sys.stderr.write(f"lens_coverage: {exc}\n")
        return 2
    verdict = coverage_verdict(dirs, opts.run_id, opts.preset, probe=probe)
    sys.stdout.write(json.dumps(verdict, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
