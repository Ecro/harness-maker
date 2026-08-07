"""Record, per new gate, the source line to delete and the test that dies when you do.

`[fail:test] assertion-invariant-over-named-dimension` is at **count:8** — the highest
test-category recurrence in this repo — and its prevention has been recorded as prose five
times: *"for every assertion, name the specific wrong implementation it is meant to reject
and check the assertion actually fails against it — if you cannot name one, the assertion is
decorative."* Five recordings, eight instances. Prose is not the mechanism.

**What this does and does not do (ADR-003 of PLAN-mechanical-guards-from-backlog).** It
mechanises the OBLIGATION, not the PROOF. "Does this assertion reject the wrong
implementation?" is not decidable in general, and a full mutation run over the suite is out
of scope (the repo gates `mutmut` on machine-SPEC paths only, deliberately, for runtime).
**The absent case is now enforced — for new structural gates only.**
`tests/structural/test_new_gates_file_a_mutation_receipt.py` fails when a gate under
`tests/structural/` lands with no row here. Gates that predate that test carry an explicit,
shrink-only debt list; every gate added from now on must answer the question.

For one round this module shipped *registered but inert*, and three reviewers plus a
cross-model voter all called that out in the same round, correctly. An earlier version of
this docstring also claimed it "makes the absent case LOUD" while nothing read the ledger —
refuted in review. Both are recorded here rather than quietly edited away, because
over-claiming in a justification note is itself a failure class in this repo
([fail:design] unverified-number-in-spec-justification).

**What is still NOT enforced (ADR-003).** Nothing re-runs the mutation. The receipt asserts
that the author deleted the line and watched the test die; the consumer checks only that the
answer exists and is shaped like an answer — a *shaped* `file:line` and a *shaped* pytest
node, so "somewhere in that module" is rejected at the door. Validation is SYNTACTIC: it
does not check that the file, the line, or the node exists, so a receipt can name something
that is not there, and a stale line number is not detected. "Does this assertion reject the
wrong implementation?" is not decidable in general, and a full mutation run over the suite is
out of scope for the same runtime reason `mutmut` is gated to machine-SPEC paths.

So: a FALSE receipt is still possible. An ABSENT one is not.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

from harness_maker import command_registry
from harness_maker.io_utils import append_atomic_line

_LEDGER_REL = ".claude/observability/mutation-receipts.jsonl"

#: `path/to/file.py:123` — a locator you can actually open, RELATIVE TO THE REPO. A bare
#: filename is not one ("delete something in worktree.py" is the non-answer this exists to
#: reject), and neither is an absolute path.
#:
#: **Repo-relative is a privacy constraint, not tidiness.** The `.gitignore` change that made
#: this ledger inspectable also made it COMMITTED, and this repo's remote is public. The
#: first version accepted `/home/<user>/…` and `../../…`, so a receipt filed from anywhere
#: would have published the author's home-directory layout — the same leak class as
#: `[fail:test] snapshot-regen-inside-worktree` (count:13), which has its own guard, and
#: which does not scan this file because a ledger is not a golden.
#:
#: `\Z`, not `$`: `$` also matches before a trailing newline, so `"src/x.py:12\n"` passed the
#: shape check and then went into the ledger with the newline inside the JSON string.
#:
#: **No extension allowlist.** The first version required `.py|.j2|.md|.json|.yaml|.toml`,
#: which rejected `.gitignore:74` — a real, load-bearing line that a real gate really does
#: depend on — and also `.yml`, i.e. every CI workflow in this repo. Found by trying to file
#: a legitimate receipt and being refused. The allowlist was never what did the work: `:\d+`
#: is the discriminator that rejects "somewhere in that module", and it rejects it just as
#: well without an opinion about file types. A guard that blocks correct answers to make
#: wrong ones impossible has the trade backwards.
_LOCATOR_RE = re.compile(r"[\w.-]+(?:/[\w.-]+)*:\d+\Z")

#: `tests/path/test_x.py::test_name` — a node id `pytest` can run. Same reasoning.
_NODE_RE = re.compile(r"tests/[\w.-]+(?:/[\w.-]+)*\.py::[\w\[\]:.-]+\Z")

#: A path segment that escapes the repo. `[\w.-]` admits `..` on its own, and one `..` is
#: enough to name a file outside the checkout in a published artifact.
_TRAVERSAL = re.compile(r"(?:^|/)\.\.(?:/|\Z)")


def _is_repo_relative(value: str) -> bool:
    """No leading `/`, no drive letter, no `..` — see `_LOCATOR_RE`'s note on why."""
    return (
        not value.startswith("/")
        and not re.match(r"^[A-Za-z]:", value)
        and not _TRAVERSAL.search(value)
    )


def _base_root(start: Path) -> Path:
    """Resolve to the base repo so a receipt written from a worktree is not stranded there.

    Delegates to the CANONICAL git-authoritative resolver rather than walking parents here.
    The first version was a second, string-based implementation, and a reviewer showed it
    reproduced the very failure this docstring cites: a linked worktree's `.git` is a FILE,
    so `.exists()` is true and the parent walk returned the WORKTREE whenever the
    `.worktrees` fast path missed — rows land in a gitignored path and die at `task-land`,
    which is the `codex_ledger` row-loss verbatim. Walking past a repo boundary could also
    write `.claude/observability/` into an ancestor (a dotfiles repo at `$HOME` is a common
    one). One resolver, already tested, is the fix.
    """
    from harness_maker.second_opinion_invoke import resolve_base_root

    return resolve_base_root(Path(start).resolve())


def record(
    root: Path, *, gate: str, deletes: str, slug: str | None = None, now: str | None = None
) -> Path:
    """Append one receipt. Raises ValueError when either locator is not actionable."""
    if not _NODE_RE.match(gate) or not _is_repo_relative(gate):
        raise ValueError(
            f"--gate {gate!r} is not a runnable pytest node id "
            "(expected tests/…/test_x.py::test_name, repo-relative). "
            "A gate you cannot run is not a gate."
        )
    if not _LOCATOR_RE.match(deletes) or not _is_repo_relative(deletes):
        raise ValueError(
            f"--deletes {deletes!r} is not a repo-relative file:line locator "
            "(expected src/…/x.py:123). 'somewhere in that module' is the non-answer this "
            "receipt exists to reject, and an absolute path publishes your home directory "
            "into a committed ledger on a public remote."
        )
    base = _base_root(root)
    path = base / _LEDGER_REL
    row = {
        "ts": now or datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "gate": gate,
        "deletes": deletes,
        "slug": slug,
    }
    # `append_atomic_line`, NOT read-then-`atomic_write`. The first version read the whole
    # ledger and replaced it, which is last-writer-wins: two sessions filing a receipt
    # concurrently each read N rows and each write their own N+1, so one row is GONE. This
    # repo supports 10-20 parallel sessions against one base-repo ledger and already solved
    # it — `delegation_ledger.append` uses this same helper for this same reason.
    append_atomic_line(path, json.dumps(row, sort_keys=True))
    return path


def main(argv: list[str] | None = None) -> int:
    raw = list(sys.argv[1:] if argv is None else argv)
    # Every dispatchable module wires this BEFORE argparse so a verb owned by another module
    # gets a redirect instead of a bare `invalid choice` — `tests/unit/test_command_surface_
    # gate.py::test_tc2_guard_is_wired_in_every_guarded_module` enforces it, and it caught
    # this module the moment it was registered.
    guard = command_registry.misroute_guard("mutation_receipt", raw)
    if guard is not None:
        return guard
    parser = argparse.ArgumentParser(
        prog="hm mutation_receipt",
        description="record which source line, when deleted, kills which test",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)
    rec = sub.add_parser("record", help="append one receipt at the base repo's ledger")
    rec.add_argument("--root", default=".", help="any path inside the repo; base is resolved")
    rec.add_argument("--gate", required=True, help="tests/…/test_x.py::test_name")
    rec.add_argument("--deletes", required=True, help="src/…/x.py:123 — the line to delete")
    rec.add_argument("--slug", default=None)
    args = parser.parse_args(raw)
    try:
        path = record(Path(args.root), gate=args.gate, deletes=args.deletes, slug=args.slug)
    except ValueError as exc:
        print(f"mutation_receipt: {exc}", file=sys.stderr)
        return 2
    print(str(path))
    return 0


if __name__ == "__main__":  # pragma: no cover — exercised via main(argv) in tests
    sys.exit(main())
