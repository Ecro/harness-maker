"""`hm review_run` — at most one open `/hm:review` run per slug (ADR-003).

`review.md.j2` tells the model to mint `<run-id>` itself. `iteration_count`,
`max_review_rounds` and the two-pass confirmation bound are all state inside one run, and
nothing records that a run is still open — so on 2026-08-17 one session created six runs for
one slug, each resetting every cap. This module is the identity those caps were missing.

**The claim is exactly "one open run per slug" and no more** (ADR-003, narrowed). The record
does NOT carry `iteration_count`; a session that resumes and starts counting rounds from 1 is
not detected. Tests here assert the narrow claim, not the wide one — a test written against the
wide claim would fail forever, and one written as if the record carried counters would document
a defence that does not exist.

Two placement facts are load-bearing and each has a test:

* the state file lives at the **base repo root**, not the worktree — a worktree-relative path is
  lost at `task-land` (the `codex_ledger` `Path.cwd()` precedent);
* it is registered in `worktree._HARNESS_ARTIFACT_PREFIXES` — **the tuple the finalize
  dirt-filter actually reads** — as well as in the gitignore set. A gitignore-only registration
  makes every live run-state file user dirt that `worktree finalize` sweeps into the finalize
  stash, which is how `.hm-autopilot` was silently disarmed once already (ADR-011 of
  PLAN-multisession-marker-scoping).
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest

from harness_maker import review_run
from harness_maker.worktree import (
    _HARNESS_ARTIFACT_PREFIXES,
    _HARNESS_CHURN_GLOBS,
)


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True, timeout=30
    ).stdout.strip()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "t")
    (root / "README.md").write_text("x\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "init")
    return root


Runner = Callable[..., tuple[int, str, str]]


@pytest.fixture
def run_cli(capsys: pytest.CaptureFixture[str]) -> Runner:
    """`main(argv)` + `capsys`, the convention the sibling CLI suites already use — rather
    than a `main_captured` shim, which would add production surface for a test's benefit."""

    def run(*args: str) -> tuple[int, str, str]:
        rc = review_run.main(list(args))
        captured = capsys.readouterr()
        return rc, captured.out, captured.err

    return run


# ── the narrow claim: one open run per slug ──────────────────────────────────


def test_open_mints_an_id_and_records_it(run_cli: Runner, repo: Path) -> None:
    rc, out, _ = run_cli("open", "--slug", "demo", "--root", str(repo))
    assert rc == 0, out
    payload = json.loads(out)
    assert payload["state"] == "open"
    assert payload["id"], payload
    assert payload["opened_at"], payload
    assert review_run.run_state_path(repo, "demo").is_file()


def test_a_second_open_refuses_and_returns_the_same_id(run_cli: Runner, repo: Path) -> None:
    """The whole point. A second `/hm:review` must resume rather than start a parallel run
    with a fresh `iteration_count`, a fresh `review_base` resolution and a fresh
    confirmation-pass budget."""
    rc1, out1, _ = run_cli("open", "--slug", "demo", "--root", str(repo))
    assert rc1 == 0
    first = json.loads(out1)["id"]

    rc2, out2, err2 = run_cli("open", "--slug", "demo", "--root", str(repo))
    assert rc2 != 0, (out2, err2)
    second = json.loads(out2)
    assert second["id"] == first, second
    assert second["state"] == "open"


def test_two_slugs_open_independently(run_cli: Runner, repo: Path) -> None:
    """The discriminating case for "one open run PER SLUG". Every other test here uses a single
    slug, so a slug-blind `run_state_path` -- one shared `<prefix>run.json` -- passed the whole
    suite while deleting the per-slug claim entirely. Two slugs is what tells them apart."""
    first = json.loads(run_cli("open", "--slug", "alpha", "--root", str(repo))[1])["id"]

    rc, out, err = run_cli("open", "--slug", "beta", "--root", str(repo))
    assert rc == 0, (out, err)
    second = json.loads(out)["id"]
    assert second != first, "a second slug reused the first slug's run id"

    assert review_run.run_state_path(repo, "alpha").is_file(), "opening `beta` displaced `alpha`"
    assert review_run.run_state_path(repo, "beta").is_file()
    alpha = review_run.load_run(repo, "alpha")
    assert alpha is not None, "alpha's record is gone"
    assert alpha["id"] == first, alpha


def test_close_then_open_yields_a_new_id(run_cli: Runner, repo: Path) -> None:
    first = json.loads(run_cli("open", "--slug", "demo", "--root", str(repo))[1])["id"]
    rc, _, _ = run_cli(
        "close",
        "--slug",
        "demo",
        "--root",
        str(repo),
        "--run-id",
        first,
        "--outcome",
        "APPROVED",
    )
    assert rc == 0
    rc2, out2, _ = run_cli("open", "--slug", "demo", "--root", str(repo))
    assert rc2 == 0, out2
    assert json.loads(out2)["id"] != first


def test_force_takes_over_and_names_the_run_it_displaces(run_cli: Runner, repo: Path) -> None:
    """Recovery is takeover, never expiry: a long review and an abandoned one are
    indistinguishable from elapsed time alone, so the operator names the displacement."""
    first = json.loads(run_cli("open", "--slug", "demo", "--root", str(repo))[1])["id"]
    rc, out, _ = run_cli("open", "--slug", "demo", "--root", str(repo), "--force")
    assert rc == 0, out
    payload = json.loads(out)
    assert payload["id"] != first
    assert payload["displaced"] == first, payload


def test_force_with_no_open_run_still_reports_displaced(run_cli: Runner, repo: Path) -> None:
    """The absent case. `displaced` used to be set only on the takeover path, so a caller that
    read it unconditionally raised `KeyError` on the ORDINARY path rather than the rare one —
    this repo's most-recurring failure class is a feature that only fires when the field is
    present."""
    rc, out, _ = run_cli("open", "--slug", "demo", "--root", str(repo), "--force")
    assert rc == 0, out
    payload = json.loads(out)
    assert "displaced" in payload, payload
    assert payload["displaced"] is None, payload


def test_a_corrupt_state_file_does_not_block_the_slug(run_cli: Runner, repo: Path) -> None:
    """`load_run`'s documented recovery: a half-written record is not an open run. Refusing on it
    would block the slug forever on a file nothing can interpret."""
    path = review_run.run_state_path(repo, "demo")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('{"id": "abc', encoding="utf-8")

    assert review_run.load_run(repo, "demo") is None

    rc, out, _ = run_cli("status", "--slug", "demo", "--root", str(repo))
    assert rc == 0
    assert json.loads(out)["state"] == "none"

    rc, out, _ = run_cli("open", "--slug", "demo", "--root", str(repo))
    assert rc == 0, out
    assert json.loads(out)["state"] == "open"


def test_close_reports_the_outcome_it_was_given(run_cli: Runner, repo: Path) -> None:
    """`--outcome` is validated and then the record is unlinked, so the close PAYLOAD is the only
    place the terminal outcome is observable. Without this, an implementation that ignored
    `--outcome` entirely passed every test in this file."""
    run_id = json.loads(run_cli("open", "--slug", "demo", "--root", str(repo))[1])["id"]
    rc, out, _ = run_cli(
        "close",
        "--slug",
        "demo",
        "--root",
        str(repo),
        "--run-id",
        run_id,
        "--outcome",
        "APPROVED",
    )
    assert rc == 0, out
    payload = json.loads(out)
    assert payload["closed"] is True
    assert payload["outcome"] == "APPROVED", payload


def test_status_reports_open_and_absent_without_failing(run_cli: Runner, repo: Path) -> None:
    rc, out, _ = run_cli("status", "--slug", "demo", "--root", str(repo))
    assert rc == 0
    assert json.loads(out)["state"] == "none"

    opened = json.loads(run_cli("open", "--slug", "demo", "--root", str(repo))[1])["id"]
    rc, out, _ = run_cli("status", "--slug", "demo", "--root", str(repo))
    assert rc == 0
    payload = json.loads(out)
    assert payload["state"] == "open"
    assert payload["id"] == opened


# ── close: the already-closed and wrong-owner cases ──────────────────────────


def test_closing_an_already_closed_run_is_not_an_error(run_cli: Runner, repo: Path) -> None:
    """`review.md.j2` wires `close` onto several terminal branches, and a review can reach two
    of them in one pass (the Grade Gate, then the Confirmation Pass). A second close must be a
    no-op rather than a failure, or the stage reports a blocker for a run that closed correctly."""
    rid = json.loads(run_cli("open", "--slug", "demo", "--root", str(repo))[1])["id"]
    args = (
        "close",
        "--slug",
        "demo",
        "--root",
        str(repo),
        "--run-id",
        rid,
        "--outcome",
        "APPROVED",
    )
    assert run_cli(*args)[0] == 0
    rc, out, _ = run_cli(*args)
    assert rc == 0, out
    assert json.loads(out)["closed"] is False


def test_closing_someone_elses_run_is_refused(run_cli: Runner, repo: Path) -> None:
    """A mismatched id means the caller is closing a run it does not own — releasing the slug
    for a peer that is still using it."""
    run_cli("open", "--slug", "demo", "--root", str(repo))
    rc, _, err = run_cli(
        "close",
        "--slug",
        "demo",
        "--root",
        str(repo),
        "--run-id",
        "not-the-open-one",
        "--outcome",
        "APPROVED",
    )
    assert rc != 0
    assert "not-the-open-one" in err
    assert review_run.run_state_path(repo, "demo").is_file(), "the peer's run was released"


# ── placement: base root, and BOTH churn registrations ───────────────────────


def test_the_state_file_is_written_at_the_base_root_from_a_linked_worktree(
    run_cli: Runner, repo: Path
) -> None:
    """A worktree-relative path is gitignored inside the worktree and vanishes at `task-land`."""
    wt = repo / ".worktrees" / "task"
    _git(repo, "worktree", "add", "-q", "-b", "hm/task", str(wt))

    rc, out, _ = run_cli("open", "--slug", "demo", "--root", str(wt))
    assert rc == 0, out
    assert review_run.run_state_path(repo, "demo").is_file()
    assert not (wt / ".claude").exists() or not list((wt / ".claude").glob(".hm-review-run-*")), (
        "state was written inside the worktree"
    )


def test_the_state_file_prefix_is_registered_in_the_finalize_dirt_filter() -> None:
    """`_HARNESS_ARTIFACT_PREFIXES` is the tuple the finalize dirt-filter reads; the globs are
    gitignore-only. A glob-only registration leaves every live run-state file as user dirt for
    `worktree finalize` to sweep into the stash — the exact way `.hm-autopilot` was disarmed."""
    assert review_run.STATE_PREFIX in _HARNESS_ARTIFACT_PREFIXES, _HARNESS_ARTIFACT_PREFIXES


def test_the_state_file_is_also_gitignored() -> None:
    assert any(g.startswith(review_run.STATE_PREFIX) for g in _HARNESS_CHURN_GLOBS), (
        _HARNESS_CHURN_GLOBS
    )


def test_the_state_path_matches_the_registered_prefix(repo: Path) -> None:
    """The two constants and the writer must agree, or each is separately correct and the
    combination protects nothing."""
    rel = review_run.run_state_path(repo, "demo").relative_to(repo).as_posix()
    assert rel.startswith(review_run.STATE_PREFIX), (rel, review_run.STATE_PREFIX)


@pytest.mark.filterwarnings(
    # `hm` dispatches via `runpy`, and this module already imported `review_run` at module
    # scope, so runpy warns that it is re-executing something already in `sys.modules`.
    # Expected and inherent to exercising the dispatcher in-process; declared rather than
    # left as suite noise.
    "ignore:.*found in sys.modules after import of package.*:RuntimeWarning"
)
def test_the_module_is_reachable_through_the_hm_dispatcher(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`hm <module>` needs a SECOND registration: `command_registry.MODULES` describes the
    subcommands, but `hm._DISPATCHABLE` is the allowlist that decides whether the module can be
    run at all — an unlisted module exits 2 with "unknown module". Registering only the first
    ships a CLI whose every rendered call site is unrunnable, and the rest of this file cannot
    see it because it imports `review_run` directly.

    In-process rather than through the console script: this asserts the allowlist, which is the
    half that gets forgotten. The `hm` packaging boundary is covered generically by
    `tests/integration/test_hm_console_script_resolves.py`; `review_run` is NOT a case there."""
    from harness_maker import hm

    rc = hm.main(["review_run", "status", "--slug", "demo", "--root", str(repo)])
    captured = capsys.readouterr()
    assert "unknown module" not in captured.err, captured.err
    assert rc == 0, (rc, captured.err)
    assert json.loads(captured.out)["state"] == "none"


def test_a_hostile_slug_is_refused_rather_than_sanitised(repo: Path) -> None:
    """The slug becomes a filename. Sanitising would map two slugs onto one namespace."""
    with pytest.raises(ValueError, match="no path separators"):
        review_run.run_state_path(repo, "../escape")
