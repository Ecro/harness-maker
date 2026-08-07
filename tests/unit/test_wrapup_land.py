"""Phase 2 — the wrapup composite's exit criteria (a)–(i).

Criterion (j) — one real `/hm:wrapup` on a throwaway task branch — is a MANUAL run and
is deliberately not simulated here; a simulation of it would assert that the simulation
works. It is recorded as outstanding in the PLAN's progress table.

The load-bearing case is (g). `worktree.py:3330` skips a finalize-stash ref only when its
`session_uuid` is truthy AND unowned; a LEGACY ref with an empty uuid falls through to
the session-marker check and IS popped, dirtying the base — and `task-land` self-aborts
on a dirty base. That deadlock is reachable from a state the harness can be carrying, so
the pre-scan must fire BEFORE staging: an abort after a commit would let every retry
accumulate another commit while hitting the same scan.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from harness_maker import worktree as wt
from harness_maker import wrapup_land
from harness_maker.wrapup_land import LandAbortError


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, text=True, check=True
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    base = tmp_path / "base"
    base.mkdir()
    _git(base, "init", "-b", "main")
    _git(base, "config", "user.email", "t@example.com")
    _git(base, "config", "user.name", "T")
    (base / "README.md").write_text("x\n", encoding="utf-8")
    _git(base, "add", "README.md")
    _git(base, "commit", "-m", "init")
    return base


@pytest.fixture
def task_worktree(repo: Path) -> Path:
    target = repo / ".worktrees" / "slug"
    _git(repo, "worktree", "add", "-b", "hm/slug", str(target))
    return target


def _args(wt_path: Path, base_path: Path, msg: Path, **kw: Any) -> argparse.Namespace:
    defaults: dict[str, Any] = {
        "worktree": str(wt_path),
        "base": str(base_path),
        "slug": "slug",
        "message_file": str(msg),
        "required": [],
        "optional": [],
        "allow_legacy_ref": False,
        # Explicit, not `getattr(args, …, False)` in `run()`: a defaulted-absent flag would
        # make "the caller never wired it" and "the caller asked for the old behaviour" the
        # same state, and the old behaviour is the bug ([fail:design] absent-case-is-a-
        # feature-black-hole). A missed call site should be an AttributeError, loudly.
        "manifest_only": False,
    }
    defaults.update(kw)
    return argparse.Namespace(**defaults)


@pytest.fixture
def message(tmp_path: Path) -> Path:
    p = tmp_path / "msg.txt"
    p.write_text("feat(x): subject\n\nbody\n", encoding="utf-8")
    return p


@pytest.fixture(autouse=True)
def _no_real_pop_or_drain(monkeypatch: pytest.MonkeyPatch) -> None:
    """Default to inert pop/drain so each test opts INTO the behaviour it is about."""
    monkeypatch.setattr(wt, "_cli_post_commit_pop", lambda _a: 0)
    monkeypatch.setattr(wt, "_cli_drain", lambda _a: 0)


# ── (f) subject binding: the roots are validated, never defaulted ──────────────


def test_a_relative_worktree_is_refused(repo: Path, task_worktree: Path, message: Path) -> None:
    """No `Path.cwd()` fallback: a relative path cannot silently retarget the commit."""
    with pytest.raises(LandAbortError, match="absolute path"):
        wrapup_land.run(_args(task_worktree, repo, message, worktree="../elsewhere"))


def test_a_nonexistent_root_is_refused(repo: Path, task_worktree: Path, message: Path) -> None:
    with pytest.raises(LandAbortError, match="does not resolve"):
        wrapup_land.run(_args(task_worktree, repo, message, base=str(repo / "nope")))


def test_a_non_git_directory_is_refused(
    repo: Path, task_worktree: Path, message: Path, tmp_path: Path
) -> None:
    plain = tmp_path / "plain"
    plain.mkdir()
    with pytest.raises(LandAbortError, match="not a git working tree"):
        wrapup_land.run(_args(task_worktree, repo, message, base=str(plain)))


def test_a_symlinked_root_resolves_to_the_same_repo(
    repo: Path, task_worktree: Path, message: Path, tmp_path: Path
) -> None:
    """A symlink is not a different repo — resolving first is what makes them compare equal."""
    link = tmp_path / "link-to-base"
    link.symlink_to(repo)
    (task_worktree / "a.md").write_text("a\n", encoding="utf-8")
    rc, receipt = wrapup_land.run(
        _args(task_worktree, repo, message, base=str(link), optional=["a.md"])
    )
    assert receipt["base"] == str(repo.resolve())
    assert rc == wrapup_land.EXIT_OK


def test_an_unrelated_checkout_is_refused(
    repo: Path, task_worktree: Path, message: Path, tmp_path: Path
) -> None:
    other = tmp_path / "other"
    other.mkdir()
    _git(other, "init", "-b", "main")
    with pytest.raises(LandAbortError, match="not a worktree of"):
        wrapup_land.run(_args(task_worktree, other, message))


# ── (a)(b)(c) the typed manifest ──────────────────────────────────────────────


def test_an_absent_optional_path_records_absent_optional_and_staging_continues(
    repo: Path, task_worktree: Path, message: Path
) -> None:
    (task_worktree / "kept.md").write_text("k\n", encoding="utf-8")
    rc, receipt = wrapup_land.run(
        _args(task_worktree, repo, message, optional=["gone.md", "kept.md"])
    )
    # Scoped to the MANIFEST rows on purpose. The worktree-sweep row is a different kind
    # and belongs to its own tests below; folding it in here would turn an exact assertion
    # about the manifest into a loose one about everything.
    by_path = {
        d["path"]: d["disposition"]
        for d in receipt["steps"]["stage"]
        if d["kind"] != "worktree-sweep"
    }
    assert by_path == {"gone.md": "absent-optional", "kept.md": "staged"}
    assert rc == wrapup_land.EXIT_OK


def test_an_absent_required_path_is_a_hard_error_naming_the_path(
    repo: Path, task_worktree: Path, message: Path
) -> None:
    with pytest.raises(LandAbortError, match=r"required path is absent: PLAN-x\.md"):
        wrapup_land.run(_args(task_worktree, repo, message, required=["PLAN-x.md"]))


def test_a_zero_hit_glob_is_absent_optional_not_a_failure(
    repo: Path, task_worktree: Path, message: Path
) -> None:
    """`REVIEW-<slug>-*.md` legitimately matches nothing when review did not run."""
    (task_worktree / "a.md").write_text("a\n", encoding="utf-8")
    rc, receipt = wrapup_land.run(
        _args(task_worktree, repo, message, optional=["REVIEW-slug-*.md", "a.md"])
    )
    by_path = {d["path"]: d["disposition"] for d in receipt["steps"]["stage"]}
    assert by_path["REVIEW-slug-*.md"] == "absent-optional"
    assert rc == wrapup_land.EXIT_OK


def test_a_git_add_failure_surfaces_git_stderr(
    repo: Path, task_worktree: Path, message: Path
) -> None:
    """The `2>/dev/null || true` this replaced made exactly this case invisible."""
    (task_worktree / ".gitignore").write_text("ignored.md\n", encoding="utf-8")
    (task_worktree / "ignored.md").write_text("i\n", encoding="utf-8")
    with pytest.raises(LandAbortError) as ei:
        wrapup_land.run(_args(task_worktree, repo, message, required=["ignored.md"]))
    assert "git add failed for ignored.md" in ei.value.reason
    assert "ignored" in ei.value.detail["git_stderr"].lower()


# ── (d)(i) commit semantics ───────────────────────────────────────────────────


def test_an_empty_index_is_reported_and_never_committed(
    repo: Path, task_worktree: Path, message: Path
) -> None:
    before = _git(task_worktree, "rev-parse", "HEAD").stdout.strip()
    with pytest.raises(LandAbortError, match="refusing to commit an empty index"):
        wrapup_land.run(_args(task_worktree, repo, message))
    assert _git(task_worktree, "rev-parse", "HEAD").stdout.strip() == before


def test_a_second_run_after_a_failed_pop_resumes_instead_of_recommitting(
    repo: Path, task_worktree: Path, message: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """(i) — the commit already happened; a retry must not add an empty duplicate."""
    (task_worktree / "a.md").write_text("a\n", encoding="utf-8")
    monkeypatch.setattr(wt, "_cli_post_commit_pop", lambda _a: 1)
    rc1, r1 = wrapup_land.run(_args(task_worktree, repo, message, optional=["a.md"]))
    assert rc1 == wrapup_land.EXIT_FAILED
    assert r1["steps"]["commit"]["status"] == "created"
    head1 = _git(task_worktree, "rev-parse", "HEAD").stdout.strip()

    monkeypatch.setattr(wt, "_cli_post_commit_pop", lambda _a: 0)
    rc2, r2 = wrapup_land.run(_args(task_worktree, repo, message, optional=["a.md"]))
    assert r2["steps"]["commit"]["status"] == "already-present"
    assert rc2 == wrapup_land.EXIT_OK
    assert _git(task_worktree, "rev-parse", "HEAD").stdout.strip() == head1


# ── (e)(h) delegation + crumb ordering ────────────────────────────────────────


def test_post_commit_pop_receives_the_crumb_derived_ownership_set(
    repo: Path, task_worktree: Path, message: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Delegation is asserted; `post_commit_pop`'s own semantics are NOT re-tested (ADR-003)."""
    wt._owned_crumb_add(repo, "slug", "uuid-aaa")
    wt._owned_crumb_add(repo, "slug", "uuid-bbb")
    seen: dict[str, Any] = {}

    def _spy(args: list[str]) -> int:
        import os

        seen["argv"] = args
        seen["env"] = os.environ.get("HM_OWNED_SESSION_UUIDS")
        return 0

    monkeypatch.setattr(wt, "_cli_post_commit_pop", _spy)
    (task_worktree / "a.md").write_text("a\n", encoding="utf-8")
    wrapup_land.run(_args(task_worktree, repo, message, optional=["a.md"]))
    assert seen["argv"] == [str(repo.resolve())]
    assert set(seen["env"].split(",")) == {"uuid-aaa", "uuid-bbb"}


def test_the_crumb_is_cleared_after_a_successful_pop_and_kept_after_a_failed_one(
    repo: Path, task_worktree: Path, message: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """(h) — clearing after a failure would strand the remaining refs as unownable."""
    wt._owned_crumb_add(repo, "slug", "uuid-aaa")
    (task_worktree / "a.md").write_text("a\n", encoding="utf-8")

    monkeypatch.setattr(wt, "_cli_post_commit_pop", lambda _a: 1)
    _, r_fail = wrapup_land.run(_args(task_worktree, repo, message, optional=["a.md"]))
    assert r_fail["steps"]["owned_crumb_clear"]["status"] == "kept-pop-failed"
    assert wt._owned_crumb_read(repo, "slug") == ["uuid-aaa"]

    (task_worktree / "b.md").write_text("b\n", encoding="utf-8")
    msg2 = message.parent / "msg2.txt"
    msg2.write_text("feat(x): second\n", encoding="utf-8")
    monkeypatch.setattr(wt, "_cli_post_commit_pop", lambda _a: 0)
    _, r_ok = wrapup_land.run(
        _args(task_worktree, repo, msg2, optional=["b.md"], message_file=str(msg2))
    )
    assert r_ok["steps"]["owned_crumb_clear"]["status"] == "cleared"
    assert wt._owned_crumb_read(repo, "slug") == []


def test_drain_does_not_run_when_the_pop_failed(
    repo: Path, task_worktree: Path, message: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    drained: list[Any] = []
    monkeypatch.setattr(wt, "_cli_post_commit_pop", lambda _a: 1)
    monkeypatch.setattr(wt, "_cli_drain", lambda a: drained.append(a) or 0)
    (task_worktree / "a.md").write_text("a\n", encoding="utf-8")
    rc, receipt = wrapup_land.run(_args(task_worktree, repo, message, optional=["a.md"]))
    assert rc == wrapup_land.EXIT_FAILED
    assert drained == []
    assert "drain" not in receipt["steps"]


# ── (g) the legacy-ref pre-scan ───────────────────────────────────────────────


def _plant_legacy_ref(base: Path, *, session_uuid: str, marker_live: bool = True) -> Path:
    """A ref whose schema validates (`key: value`, `ref_sha`, ISO `created_at`).

    Written against `_validate_stash_ref_fields`'s real contract rather than a guess: a
    fixture that fails validation would make every assertion below pass vacuously.
    """
    claude = base / ".claude"
    claude.mkdir(exist_ok=True)
    marker = claude / ".hm-loop-legacy-wt"
    if marker_live:
        marker.write_text("\n", encoding="utf-8")
    ref = claude / f"{wt._STASH_REF_PREFIX}legacy-wt"
    body = [
        f"ref_sha: {'0' * 40}",
        f"base: {base}",
        f"session_marker: {marker}",
        "created_at: 2026-07-29T00:00:00+00:00",
    ]
    if session_uuid:
        body.append(f"session_uuid: {session_uuid}")
    ref.write_text("\n".join(body) + "\n", encoding="utf-8")
    return ref


def test_the_fixture_validates_so_the_scan_assertions_are_not_vacuous(repo: Path) -> None:
    ref = _plant_legacy_ref(repo, session_uuid="")
    fields = wt._validate_stash_ref_fields(wt._read_stash_ref_file(ref))
    assert fields is not None, "the planted ref does not pass the real schema check"


def test_a_live_legacy_ref_is_detected_and_a_uuid_bearing_one_is_not(repo: Path) -> None:
    _plant_legacy_ref(repo, session_uuid="")
    assert wrapup_land.live_legacy_refs(repo) == [f"{wt._STASH_REF_PREFIX}legacy-wt"]
    _plant_legacy_ref(repo, session_uuid="abcdef123456")
    assert wrapup_land.live_legacy_refs(repo) == []


def test_a_legacy_ref_with_a_dead_marker_is_not_flagged(repo: Path) -> None:
    """A stale ref is not popped, so it is not a deadlock source — flagging it is noise."""
    _plant_legacy_ref(repo, session_uuid="", marker_live=False)
    assert wrapup_land.live_legacy_refs(repo) == []


def test_the_prescan_aborts_before_staging_and_before_committing(
    repo: Path, task_worktree: Path, message: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _plant_legacy_ref(repo, session_uuid="")
    (task_worktree / "a.md").write_text("a\n", encoding="utf-8")
    head_before = _git(task_worktree, "rev-parse", "HEAD").stdout.strip()

    rc, receipt = wrapup_land.run(_args(task_worktree, repo, message, optional=["a.md"]))

    assert rc == wrapup_land.EXIT_FAILED
    assert receipt["steps"]["legacy_ref_scan"]["status"] == "abort"
    assert "stage" not in receipt["steps"], "the scan must run BEFORE staging"
    assert "commit" not in receipt["steps"]
    assert _git(task_worktree, "rev-parse", "HEAD").stdout.strip() == head_before
    assert _git(task_worktree, "diff", "--cached", "--name-only").stdout.strip() == ""


def test_the_remediation_carries_the_diff_preview_obligation(repo: Path) -> None:
    """CLAUDE.md's LLM behaviour contract: never point at `drop` without `show -p` first."""
    text = wrapup_land.legacy_ref_remediation(repo, ["ref-a"])
    assert "git stash show -p" in text
    drop_at = text.index("drop")
    assert text.index("git stash show -p") < drop_at, "the preview must precede any mention of drop"


def test_allow_legacy_ref_bypasses_the_scan(repo: Path, task_worktree: Path, message: Path) -> None:
    _plant_legacy_ref(repo, session_uuid="")
    (task_worktree / "a.md").write_text("a\n", encoding="utf-8")
    rc, receipt = wrapup_land.run(
        _args(task_worktree, repo, message, optional=["a.md"], allow_legacy_ref=True)
    )
    assert receipt["steps"]["legacy_ref_scan"]["status"] == "bypassed"
    assert receipt["steps"]["commit"]["status"] == "created"
    assert rc == wrapup_land.EXIT_OK


# ── the receipt is machine-readable ───────────────────────────────────────────


def test_main_prints_a_json_receipt(
    repo: Path, task_worktree: Path, message: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (task_worktree / "a.md").write_text("a\n", encoding="utf-8")
    rc = wrapup_land.main(
        [
            "--worktree",
            str(task_worktree),
            "--base",
            str(repo),
            "--slug",
            "slug",
            "--message-file",
            str(message),
            "--optional",
            "a.md",
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert payload["ok"] is True
    assert payload["steps"]["commit"]["status"] == "created"


def test_the_receipt_is_parseable_json_even_though_drain_prints_to_stdout(
    repo: Path,
    task_worktree: Path,
    message: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The receipt's channel is stdout, and `_cli_drain` writes its summary there too.

    Found by running this composite for real and piping it to `json.load`, which died on
    line 1 — on a document the stage prose instructs the reader to parse. A render-grep
    could not have caught it: the template text is correct, only the bytes on the wire
    are wrong.
    """

    def _noisy_drain(_a: list[str]) -> int:
        print("worktree drain: removed 0 branch(es), 0 marker(s), 0 stash-ref(s)")
        return 0

    monkeypatch.setattr(wt, "_cli_drain", _noisy_drain)
    (task_worktree / "a.md").write_text("a\n", encoding="utf-8")
    rc = wrapup_land.main(
        [
            "--worktree",
            str(task_worktree),
            "--base",
            str(repo),
            "--slug",
            "slug",
            "--message-file",
            str(message),
            "--optional",
            "a.md",
        ]
    )
    out = capsys.readouterr().out
    payload = json.loads(out)  # would raise before the fix
    assert rc == 0
    assert "removed 0 branch(es)" in payload["steps"]["drain"]["summary"]


# ── the implementation must reach its own commit ──────────────────────────────


def _committed_files(root: Path) -> set[str]:
    r = _git(root, "show", "--name-only", "--pretty=format:", "HEAD")
    return {ln.strip() for ln in r.stdout.splitlines() if ln.strip()}


def test_code_in_the_task_worktree_reaches_the_commit(
    repo: Path, task_worktree: Path, message: Path
) -> None:
    """The bug, stated as a test: the manifest names deliverables, never `src/**`.

    Written after it shipped TWICE — a 41-file implementation and then a 6-file one, both
    omitted from their own wrapup commit while the receipt reported `ok: true` and
    `commit.status: created`. Nothing here was hypothetical.
    """
    (task_worktree / "work-docs").mkdir()
    (task_worktree / "work-docs" / "PLAN-slug.md").write_text("plan\n", encoding="utf-8")
    (task_worktree / "src").mkdir()
    (task_worktree / "src" / "impl.py").write_text("x = 1\n", encoding="utf-8")  # NEW file
    (task_worktree / "README.md").write_text("edited\n", encoding="utf-8")  # MODIFIED file

    rc, receipt = wrapup_land.run(
        _args(task_worktree, repo, message, required=["work-docs/PLAN-slug.md"])
    )

    assert rc == 0, receipt
    committed = _committed_files(task_worktree)
    assert "src/impl.py" in committed, "a new source file was left out of its own commit"
    assert "README.md" in committed, "a modified tracked file was left out"
    assert "work-docs/PLAN-slug.md" in committed


def test_manifest_only_is_the_old_behaviour(repo: Path, task_worktree: Path, message: Path) -> None:
    """The escape hatch, and the control that proves the sweep is what carries the test
    above — without it that test would pass on a manifest that happened to match."""
    (task_worktree / "work-docs").mkdir()
    (task_worktree / "work-docs" / "PLAN-slug.md").write_text("plan\n", encoding="utf-8")
    (task_worktree / "src").mkdir()
    (task_worktree / "src" / "impl.py").write_text("x = 1\n", encoding="utf-8")

    rc, _ = wrapup_land.run(
        _args(
            task_worktree,
            repo,
            message,
            required=["work-docs/PLAN-slug.md"],
            manifest_only=True,
        )
    )

    assert rc == 0
    assert "src/impl.py" not in _committed_files(task_worktree)


def test_a_shared_working_tree_is_never_swept(repo: Path, message: Path) -> None:
    """Isolation OFF: `--worktree` IS `--base`, a shared branch that may carry other work.

    Sweeping there would pull a colleague's — or the user's own — unrelated in-flight edits
    into a wrapup commit, which is the contamination class this repo has a five-layer
    defence against. The gate is `worktree != base`, and this is its demonstration.
    """
    (repo / "work-docs").mkdir()
    (repo / "work-docs" / "PLAN-slug.md").write_text("plan\n", encoding="utf-8")
    (repo / "unrelated-wip.py").write_text("not mine\n", encoding="utf-8")

    rc, receipt = wrapup_land.run(_args(repo, repo, message, required=["work-docs/PLAN-slug.md"]))

    assert rc == 0, receipt
    assert "unrelated-wip.py" not in _committed_files(repo)
    sweep = [d for d in receipt["steps"]["stage"] if d["kind"] == "worktree-sweep"]
    assert sweep, "the sweep row is missing — the gate cannot be read from the receipt"
    assert sweep[0]["disposition"] == "skipped-not-isolated"


def test_a_missing_required_path_still_aborts_before_the_sweep(
    repo: Path, task_worktree: Path, message: Path
) -> None:
    """Order matters: `git add -A` cannot notice that a REQUIRED deliverable is absent.

    If the sweep ran first, a wrapup missing its PLAN would commit successfully instead of
    aborting by name — the typed manifest's whole purpose, quietly dissolved by the fix.
    """
    (task_worktree / "src").mkdir()
    (task_worktree / "src" / "impl.py").write_text("x = 1\n", encoding="utf-8")

    with pytest.raises(LandAbortError, match="required path is absent"):
        wrapup_land.run(_args(task_worktree, repo, message, required=["work-docs/PLAN-slug.md"]))
