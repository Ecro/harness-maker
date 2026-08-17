"""`freeze resolve-base` is idempotent, and repairs a missing stamp (ADR-004).

`review.md.j2` forbids re-resolving `review_base` in prose, and `read-base` fails loudly when
the ref is absent — but `resolve-base` itself resolved and stored unconditionally, so a second
round-1 silently re-based a review already in flight. That is the mechanism behind the
2026-08-17 incident's fourth claim.

**The stamp's absent case is real for a reason the first draft got wrong.** `freeze reap`
deletes the ref and the stamp together, so post-reap is both-absent, never ref-present /
stamp-absent. The reachable path is placement: `FREEZE_STAMP_DIR` sits under
`.claude/observability/`, which is per-worktree working-tree state and gitignored, while git
refs are shared across worktrees — so a review running in a worktree sees the ref with no
stamp beside it. An early return keyed on the ref alone would leave that stamp unrepairable,
and the stamp exists precisely because the ref cannot carry the write time (it points at a
merge-base that may be months old).

Recorded so the next reader inherits it: the stamp currently has **no reader in `src/`** — only
the writer, the reap unlink and a boundary test. Repairing it buys correctness of the artefact,
not of a live code path.

**Phase A.4 — two of these four pass against the unmodified subject, on purpose.** Both are
guards against the wrong implementation this change invites, not assertions about behaviour that
is missing today:

* `test_the_first_resolve_computes_and_stores_both_artefacts` pins the absent case, which
  already works. An idempotence guard written as "delegate to `read-base` and return" would
  satisfy no-overwrite while breaking first use; this is the test that goes red for it.
* `test_a_second_resolve_recreates_a_deleted_stamp` passes today only because the current code
  re-stores unconditionally. It goes red the moment the guard is written as an early return
  keyed on the ref alone — which is the shape a reader reaches for first.

`test_resolve_base_has_no_override_escape_hatch` (3 parametrized cases) also passes today, and
is the third shape A.4 recognises: a **negative invariant**, vacuously true while the construct
it forbids does not exist. It goes red the moment someone adds `--force` / `--overwrite` to
`resolve-base`, which a PLAN revision had already slipped into a phase work list once before an
ADR caught it. It is behavioural rather than a source grep, so it also catches a flag that is
accepted and silently ignored.

Their RED positive siblings are the two idempotence tests, which fail against the subject as it
stands. No passing test here is vacuous: each has a named wrong implementation it rejects.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest

from harness_maker import freeze


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True, timeout=30
    ).stdout.strip()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "t")
    (root / "a.txt").write_text("1\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "base")
    _git(root, "checkout", "-qb", "feature")
    (root / "b.txt").write_text("2\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "work")
    return root


def _advance_the_merge_base(repo: Path, tag: str) -> None:
    """Move `merge-base(HEAD, main)` — the only edit that changes what a re-resolution returns.

    Committing on `feature` does NOT: the merge-base stays the branch point however many
    commits pile up on the branch. A first draft of these tests did exactly that and its
    "a re-resolution would produce a different answer" premise was false, so the idempotence
    assertion passed against an implementation that re-resolves every time.
    """
    _git(repo, "checkout", "-q", "main")
    (repo / f"{tag}.txt").write_text(f"{tag}\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", f"main {tag}")
    _git(repo, "checkout", "-q", "feature")
    _git(repo, "merge", "-q", "--no-edit", "main")


Resolver = Callable[[Path], tuple[int, dict[str, object], str]]


@pytest.fixture
def resolve(capsys: pytest.CaptureFixture[str]) -> Resolver:
    """`main(argv)` + `capsys` — the convention the sibling CLI suites use."""

    def _resolve(repo: Path) -> tuple[int, dict[str, object], str]:
        rc = freeze.main(["resolve-base", "--slug", "demo", "--root", str(repo)])
        captured = capsys.readouterr()
        payload: dict[str, object] = json.loads(captured.out) if captured.out.strip() else {}
        return rc, payload, captured.err

    return _resolve


def test_the_first_resolve_computes_and_stores_both_artefacts(
    resolve: Resolver, repo: Path
) -> None:
    """The absent case. An implementation that merely delegated to `read-base` would satisfy
    no-overwrite while breaking first use, so this is asserted separately rather than being
    implied by the second call returning something."""
    rc, payload, _ = resolve(repo)
    assert rc == 0, payload
    assert payload["review_base"], payload
    assert freeze.load_review_base(repo, "demo") == payload["review_base"]
    assert freeze.review_base_stamp(repo, "demo").is_file()


def test_a_second_resolve_returns_the_stored_commit_and_warns(
    resolve: Resolver, repo: Path
) -> None:
    first = resolve(repo)[1]["review_base"]
    _advance_the_merge_base(repo, "c")
    assert freeze.resolve_review_base(repo) != first, (
        "the fixture no longer moves the merge-base, so this test cannot discriminate"
    )

    rc, payload, err = resolve(repo)
    assert rc == 0, payload
    assert payload["review_base"] == first, (payload, first)
    # The identifying substring, not merely "some stderr": a stray git warning satisfies
    # `err.strip()` and the assertion then vouches for a message that never rendered.
    assert "reusing it" in err, (
        f"the reuse is silent, so it is indistinguishable from a silent re-resolution: {err!r}"
    )


def test_a_second_resolve_recreates_a_deleted_stamp(resolve: Resolver, repo: Path) -> None:
    """Ref-present / stamp-absent is reachable: the stamp is gitignored per-worktree state
    while the ref is shared across worktrees. A guard keyed on the ref alone returns early and
    never repairs it."""
    first = resolve(repo)[1]["review_base"]
    stamp = freeze.review_base_stamp(repo, "demo")
    stamp.unlink()
    assert not stamp.exists()

    rc, payload, _ = resolve(repo)
    assert rc == 0, payload
    assert payload["review_base"] == first
    assert stamp.is_file(), "the stamp was not repaired"
    assert stamp.read_text(encoding="utf-8").strip() == first


@pytest.mark.parametrize("flag", ["--force", "--overwrite", "--re-resolve"])
def test_resolve_base_has_no_override_escape_hatch(
    resolve: Resolver, repo: Path, flag: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """ADR-004 decides the guard and **no override flag**: an escape hatch reinstates the exact
    drift the guard exists to remove, one flag away, with no ADR recording when it is legitimate.
    A first revision of the PLAN slipped "overwrite only under an explicit flag" into the phase
    work list without an ADR; this is the assertion that keeps it out.

    Behavioural, not a source grep: the flag must not change the stored base, whether it is
    rejected by the parser or silently ignored."""
    first = resolve(repo)[1]["review_base"]
    # `flag.strip("-").replace("-", "_")`, not `hash(flag)`: `hash` is process-randomised via
    # PYTHONHASHSEED, and this repo pins test determinism as a rule rather than a preference.
    _advance_the_merge_base(repo, f"ov_{flag.strip('-').replace('-', '_')}")

    freeze.main(["resolve-base", "--slug", "demo", "--root", str(repo), flag])
    capsys.readouterr()

    assert freeze.load_review_base(repo, "demo") == first, (
        f"{flag} moved the stored review_base — ADR-004 forbids an override escape hatch"
    )


def test_the_stored_ref_is_never_overwritten_by_a_later_resolve(
    resolve: Resolver, repo: Path
) -> None:
    """The property the prose already required and the code did not enforce."""
    first = resolve(repo)[1]["review_base"]
    for i in range(3):
        _advance_the_merge_base(repo, f"d{i}")
        resolve(repo)
    assert freeze.resolve_review_base(repo) != first, "the fixture stopped moving the base"
    assert freeze.load_review_base(repo, "demo") == first
