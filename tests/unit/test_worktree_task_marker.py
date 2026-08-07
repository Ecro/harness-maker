"""PLAN-multisession-marker-scoping Phase 2 — per-session TASK worktree markers.

ADR-008 `task-create` / `task-preflight` write a session-attributable marker; the
        registry stays OFF the enforcement path (its `pid` is the exited CLI subprocess,
        so its rows are structurally non-live almost immediately). Id-less callers write
        NO marker — an unattributable one could only ever produce false peer-blocks.
ADR-010 the marker lives under a DISTINCT `.hm-task-` prefix, keyed by WORKTREE name with
        the session id in the CONTENT header. Reusing `.hm-loop-` — the obvious
        implementation — would make `loop_gate` refuse to let every `/hm:plan` or
        `/hm:execute` session stop, and would pull task worktrees into
        `_owned_session_uuids` and the queue-guard.
ADR-013 recovery is by TAKEOVER at claim time, not expiry: loop/task marker content
        carries no timestamp, so a crashed session's persistent task worktree would
        otherwise stay marked forever and lock the restarted session out of its own work.

`test_task_marker_does_not_make_the_session_unstoppable` and
`test_two_task_worktrees_in_one_session_are_both_marked` are the two that pin the traps
that killed the earlier designs — the shared prefix and the session-keyed filename.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from harness_maker import loop_marker, worktree

SESS_A = "aaaa1111cafe"
SESS_B = "bbbb2222cafe"


def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "main", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@e.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=repo, check=True)
    (repo / ".gitignore").write_text(".claude/\n.worktrees/\n", encoding="utf-8")
    (repo / "README.md").write_text("base")
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True)
    (repo / ".claude").mkdir(exist_ok=True)
    return repo


def _marker(repo: Path, slug: str) -> Path:
    return repo / ".claude" / f".hm-task-{slug}"


# --- ADR-008: the marker exists at all, and only when attributable ---------------


def test_task_create_writes_a_session_attributable_marker(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    wt = worktree.task_create(repo, "alpha", session_uuid="0123456789ab", claude_session_id=SESS_A)
    text = _marker(repo, "alpha").read_text(encoding="utf-8")
    assert loop_marker.parse_marker_session_id(text) == SESS_A
    assert loop_marker.parse_marker_paths(text) == [str(wt)]


def test_task_create_without_an_id_writes_no_marker(tmp_path: Path) -> None:
    """ADR-008: an unattributable task marker could only produce false peer-blocks."""
    repo = _init_repo(tmp_path)
    worktree.task_create(repo, "alpha", session_uuid="0123456789ab", claude_session_id=None)
    assert not _marker(repo, "alpha").exists()


def test_marker_carries_a_path_line_not_just_a_header(tmp_path: Path) -> None:
    """The gate's peer test needs the path, and a header-only marker can never be pruned."""
    repo = _init_repo(tmp_path)
    worktree.task_create(repo, "alpha", session_uuid="0123456789ab", claude_session_id=SESS_A)
    assert loop_marker.parse_marker_paths(_marker(repo, "alpha").read_text(encoding="utf-8"))


# --- ADR-010: the `.hm-loop-` prefix trap ----------------------------------------


def test_task_marker_does_not_make_the_session_unstoppable(tmp_path: Path) -> None:
    """The `loop-mode-active` CLI half of the ADR-010 trap."""
    repo = _init_repo(tmp_path)
    worktree.task_create(repo, "alpha", session_uuid="0123456789ab", claude_session_id=SESS_A)
    assert worktree.main(["loop-mode-active", str(repo), "--claude-session-id", SESS_A]) == 1


def test_loop_gate_stop_hook_ignores_a_task_marker(tmp_path: Path) -> None:
    """The Stop hook ITSELF — the consumer the exit criterion names.

    The CLI test above shares `marker_dir_has_session` with this path, so a prefix
    inversion fails both; what only this covers is everything `loop_gate` adds on top —
    its own `_project_root` resolution and the `stop_hook_active` guard. Citing a
    mechanism scoped to a different entry point is the same defect class ADR-013's
    `prune_stale` correction records, one module over.
    """
    import json

    from harness_maker.hooks import loop_gate

    repo = _init_repo(tmp_path)
    wt = worktree.task_create(repo, "alpha", session_uuid="0123456789ab", claude_session_id=SESS_A)
    payload = json.dumps({"session_id": SESS_A, "cwd": str(repo)})
    assert loop_gate._stop_hook(payload) == 0

    # Positive control: the SAME session with a real loop marker IS blocked, so the 0
    # above is a decision and not an unreachable branch.
    (repo / ".claude" / ".hm-loop-alpha").write_text(
        loop_marker.format_marker_content(SESS_A, [wt]), encoding="utf-8"
    )
    assert loop_gate._stop_hook(payload) == 2


def test_task_marker_does_not_enter_loop_ownership(tmp_path: Path) -> None:
    """`_owned_session_uuids` parses the UUID out of the worktree NAME, so the slug must
    match `_WT_NAME_RE` or the assertion is true for any prefix — including the inverted
    one it exists to catch."""
    repo = _init_repo(tmp_path)
    named = "plan-0123456789ab-20260807T1200Z"
    wt = worktree.task_create(repo, named, session_uuid="0123456789ab", claude_session_id=SESS_A)
    assert worktree._owned_session_uuids(repo) == set()

    # Positive control: the same name under the LOOP prefix does yield the uuid, so the
    # empty set above is a property of the prefix and not of the name.
    (repo / ".claude" / f".hm-loop-{named}").write_text(
        loop_marker.format_marker_content(SESS_A, [wt]), encoding="utf-8"
    )
    assert worktree._owned_session_uuids(repo) == {"0123456789ab"}


def test_task_marker_is_not_read_as_an_active_loop_worktree(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    worktree.task_create(repo, "alpha", session_uuid="0123456789ab", claude_session_id=SESS_A)
    assert worktree._read_active_worktrees(repo) == []


def test_two_task_worktrees_in_one_session_are_both_marked(tmp_path: Path) -> None:
    """The collision that killed the session-keyed filename: plan on one slug while
    execute runs on another. Keying by WORKTREE makes every lifecycle transition a
    whole-file create or unlink."""
    repo = _init_repo(tmp_path)
    worktree.task_create(repo, "alpha", session_uuid="0123456789ab", claude_session_id=SESS_A)
    worktree.task_create(repo, "beta", session_uuid="0123456789ab", claude_session_id=SESS_A)
    for slug in ("alpha", "beta"):
        text = _marker(repo, slug).read_text(encoding="utf-8")
        assert loop_marker.parse_marker_session_id(text) == SESS_A


# --- ADR-013: takeover-on-claim, and the lifecycle transitions -------------------


def test_preflight_takes_over_the_marker_for_the_claiming_session(tmp_path: Path) -> None:
    """A crashed session's task marker carries no timestamp, so it cannot expire; the
    restarted session must reclaim it in one step or be locked out of its own work."""
    repo = _init_repo(tmp_path)
    worktree.task_create(repo, "alpha", session_uuid="0123456789ab", claude_session_id=SESS_A)
    worktree.task_preflight(
        repo, "alpha", session_uuid="ba9876543210", claude_session_id=SESS_B, allow_shared=True
    )
    text = _marker(repo, "alpha").read_text(encoding="utf-8")
    assert loop_marker.parse_marker_session_id(text) == SESS_B


def test_task_land_unlinks_the_marker(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    wt = worktree.task_create(repo, "alpha", session_uuid="0123456789ab", claude_session_id=SESS_A)
    assert _marker(repo, "alpha").exists()
    assert worktree.task_land(repo, "alpha", session_uuid="0123456789ab") == 0
    assert not wt.is_dir()
    assert not _marker(repo, "alpha").exists()


def test_task_land_rerun_clears_a_leaked_marker(tmp_path: Path) -> None:
    """ADR-008's `already-landed (idempotent)` row: unlink if present, no error. Reached
    only when branch AND worktree are already gone, which the success-path test above
    never enters."""
    repo = _init_repo(tmp_path)
    wt = worktree.task_create(repo, "alpha", session_uuid="0123456789ab", claude_session_id=SESS_A)
    assert worktree.task_land(repo, "alpha", session_uuid="0123456789ab") == 0
    _marker(repo, "alpha").write_text(
        loop_marker.format_marker_content(SESS_A, [wt]), encoding="utf-8"
    )
    assert worktree.task_land(repo, "alpha", session_uuid="0123456789ab") == 0
    assert not _marker(repo, "alpha").exists()


def test_cleanup_all_unlinks_the_marker_of_a_worktree_it_removed(tmp_path: Path) -> None:
    """`cleanup_all` is session-blind by design (a deliberate operator sweep), and is
    therefore the one caller allowed to unlink a peer-owned task marker — possible only
    because ADR-010 keys the filename by worktree, so this is a whole-file unlink and
    never a partial rewrite of someone else's file.

    The slug carries an owned prefix because that is what `_list_worktrees` sweeps; see
    the sibling test for the far more common non-owned-prefix case.
    """
    repo = _init_repo(tmp_path)
    worktree.task_create(repo, "plan-alpha", session_uuid="0123456789ab", claude_session_id=SESS_A)
    assert _marker(repo, "plan-alpha").exists()
    assert worktree.cleanup_all(repo, force=True) == 1
    assert not _marker(repo, "plan-alpha").exists()


def test_cleanup_all_leaves_a_worktree_it_did_not_remove_marked(tmp_path: Path) -> None:
    """ADR-013's hard rule: deleting a task marker while its worktree still EXISTS is
    forbidden to everyone. `cleanup_all` sweeps only `_OWNED_PREFIXES`, so an ordinary
    task slug survives it — and its marker must survive too, or the peer protection for a
    live worktree silently disappears."""
    repo = _init_repo(tmp_path)
    wt = worktree.task_create(repo, "alpha", session_uuid="0123456789ab", claude_session_id=SESS_A)
    worktree.cleanup_all(repo, force=True)
    assert wt.is_dir(), "precondition: cleanup_all does not sweep non-owned-prefix slugs"
    assert _marker(repo, "alpha").exists()


def test_prune_stale_reaps_an_orphan_task_marker(tmp_path: Path) -> None:
    """SIGKILL / a manual `git worktree remove` leaves the marker behind."""
    repo = _init_repo(tmp_path)
    (repo / ".worktrees").mkdir(exist_ok=True)
    _marker(repo, "ghost").write_text(
        loop_marker.format_marker_content(SESS_A, [repo / ".worktrees" / "ghost"]),
        encoding="utf-8",
    )
    worktree.prune_stale(repo)
    assert not _marker(repo, "ghost").exists()


def test_prune_stale_preserves_a_live_task_marker(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    worktree.task_create(repo, "alpha", session_uuid="0123456789ab", claude_session_id=SESS_A)
    worktree.prune_stale(repo)
    assert _marker(repo, "alpha").exists()


# --- ADR-008: argv plumbing (the same substitution class shipped twice here) -----


def test_cli_task_create_does_not_swallow_the_flag_value_as_base_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`rest = [a for a in args if not a.startswith("--")]` leaves the flag's VALUE in
    `rest`, so `task-create <slug> --claude-session-id abc123` silently resolves the base
    repo to `./abc123` — no error, with marker, registry and gitignore all following the
    wrong base."""
    repo = _init_repo(tmp_path)
    monkeypatch.chdir(repo)
    rc = worktree.main(["task-create", "alpha", "--claude-session-id", SESS_A])
    assert rc == 0
    assert not (repo / SESS_A).exists(), "the flag value was taken as base_dir"
    assert _marker(repo, "alpha").exists()


def test_cli_task_create_still_accepts_an_explicit_base_dir(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    rc = worktree.main(["task-create", "alpha", str(repo), "--claude-session-id", SESS_A])
    assert rc == 0
    assert _marker(repo, "alpha").exists()


# --- ADR-011: churn / gitignore for the task family ------------------------------


def test_task_marker_is_not_user_dirt_and_is_gitignored() -> None:
    assert worktree._is_harness_artifact("?? .claude/.hm-task-alpha") is True
    assert ".claude/.hm-task-" in worktree._HARNESS_ARTIFACT_PREFIXES
    assert ".claude/.hm-task-*" in worktree._HARNESS_GITIGNORE_PATTERNS


# --- review round 1 regressions --------------------------------------------------


def test_an_idless_claim_neither_writes_nor_deletes(tmp_path: Path) -> None:
    """Round 2. The first attempt UNLINKED here, to stop a stale marker from blocking a
    degraded session — and handed the least authenticated caller the most destructive
    authority: `claim_task_branch`'s liveness is pid-based (ADR-008: the exited CLI
    subprocess), so a LIVE peer reads dead and the unlink strips its protection while its
    worktree is still there. The lockout is real but belongs to the gate, not to the writer."""
    repo = _init_repo(tmp_path)
    wt = worktree.task_create(repo, "alpha", session_uuid="0123456789ab", claude_session_id=SESS_A)
    worktree._write_task_marker(repo, "alpha", wt, "")
    text = _marker(repo, "alpha").read_text(encoding="utf-8")
    assert loop_marker.parse_marker_session_id(text) == SESS_A, (
        "an id-less caller deleted a peer's marker while its worktree still exists"
    )


def test_a_session_is_never_blocked_from_the_worktree_it_stands_in(tmp_path: Path) -> None:
    """The gate-side fix for CR-1 **and** for the P0 the writer-side attempt introduced.

    Both failure modes reduce to one question asked of the wrong artifact. A stale foreign
    header arises on the ORDINARY path — resuming a task tomorrow is a new session id — and
    whichever way the writer resolved it, someone lost: refuse and the resuming session is
    locked out of its own task with the block message's remedy being the very no-op that
    caused it; rewrite and a live peer is stripped. The cwd cannot be wrong about who is
    standing where.
    """
    import io
    import json
    import sys

    from harness_maker.gates import worktree_gate

    repo = _init_repo(tmp_path)
    (repo / ".claude" / "harness.yaml").write_text("preset: Side\n", encoding="utf-8")
    wt = worktree.task_create(repo, "alpha", session_uuid="0123456789ab", claude_session_id=SESS_A)
    # A DIFFERENT session, working in that same task worktree, with A's header still on disk.
    payload = {
        "tool_name": "Write",
        "cwd": str(wt),
        "session_id": SESS_B,
        "tool_input": {"file_path": str(wt / "src" / "f.py")},
    }
    sys.stdin = io.StringIO(json.dumps(payload))
    assert worktree_gate.main() == 0

    # Peer protection is NOT weakened: from the BASE, the same session is still blocked.
    payload["cwd"] = str(repo)
    sys.stdin = io.StringIO(json.dumps(payload))
    assert worktree_gate.main() == 2


def test_takeover_refuses_a_foreign_marker_without_allow_shared(tmp_path: Path) -> None:
    """CR-2/SR-2 (P1). ADR-013 authorises takeover-on-claim as recovery for a marker that
    cannot expire; it never considered a LIVE peer. The only upstream restraint is
    `claim_task_branch`'s pid liveness, and ADR-008's own Context says that pid is the
    exited CLI subprocess — so a live peer reads dead and the seizure evicts it from its
    own worktree at its very next write."""
    repo = _init_repo(tmp_path)
    wt = worktree.task_create(repo, "alpha", session_uuid="0123456789ab", claude_session_id=SESS_A)
    # `_write_task_marker` directly: the registry's own `claim_task_branch` guard blocks the
    # second claim only while the peer's PID is alive, and the whole premise of this finding
    # is that it usually is not. This exercises the marker-level guard on its own.
    worktree._write_task_marker(repo, "alpha", wt, SESS_B)
    text = _marker(repo, "alpha").read_text(encoding="utf-8")
    assert loop_marker.parse_marker_session_id(text) == SESS_A, "a foreign marker was seized"


def test_takeover_still_works_with_allow_shared(tmp_path: Path) -> None:
    """The positive control — the refusal above must be the guard, not a dead branch.

    Round-2 note: this test was AMENDED to pass `allow_shared=True` when the guard landed,
    and that amendment is what hid the P0 the guard introduced. Amending a test so it keeps
    passing is how a fix's own consequence goes unmeasured; the block it caused is now
    covered by `test_a_session_is_never_blocked_from_the_worktree_it_stands_in`.
    """
    repo = _init_repo(tmp_path)
    wt = worktree.task_create(repo, "alpha", session_uuid="0123456789ab", claude_session_id=SESS_A)
    worktree._write_task_marker(repo, "alpha", wt, SESS_B, allow_shared=True)
    text = _marker(repo, "alpha").read_text(encoding="utf-8")
    assert loop_marker.parse_marker_session_id(text) == SESS_B


def test_refreshing_your_own_marker_is_not_a_takeover(tmp_path: Path) -> None:
    """The guard must not block the SAME session re-claiming — that is the normal path."""
    repo = _init_repo(tmp_path)
    worktree.task_create(repo, "alpha", session_uuid="0123456789ab", claude_session_id=SESS_A)
    _marker(repo, "alpha").unlink()
    worktree.task_create(repo, "alpha", session_uuid="0123456789ab", claude_session_id=SESS_A)
    assert _marker(repo, "alpha").exists()


def test_a_resumed_task_reclaims_its_marker_and_is_not_blocked(tmp_path: Path) -> None:
    """Round 4 — the defect three rounds of fixes did not close.

    A persistent task worktree outlives the session that made it; resuming it tomorrow is a
    NEW `claude_session_id`. The gate's cwd self-membership does not help here because the
    shipped contract (`pf_tail.md.j2`) has stages write to absolute `<WT>/…` paths while the
    session's own cwd stays at the base — so the ONLY thing that can make the resumed session
    an owner is `task_preflight` re-stamping the header. Reaching that line means
    `claim_task_branch` accepted the claim, and that acceptance is the authorisation.
    """
    import io
    import json
    import sys

    from harness_maker.gates import worktree_gate

    repo = _init_repo(tmp_path)
    (repo / ".claude" / "harness.yaml").write_text("preset: Side\n", encoding="utf-8")
    wt = worktree.task_create(repo, "alpha", session_uuid="0123456789ab", claude_session_id=SESS_A)
    # Yesterday's session ENDED — that is what makes this a resume rather than a collision.
    worktree.release_session(repo, session_uuid="0123456789ab")

    # Tomorrow: same task, new session id, cwd at the BASE (the shipped shape).
    worktree.task_preflight(repo, "alpha", session_uuid="ba9876543210", claude_session_id=SESS_B)
    assert (
        loop_marker.parse_marker_session_id(_marker(repo, "alpha").read_text(encoding="utf-8"))
        == SESS_B
    )

    sys.stdin = io.StringIO(
        json.dumps(
            {
                "tool_name": "Write",
                "cwd": str(repo),
                "session_id": SESS_B,
                "tool_input": {"file_path": str(wt / "src" / "f.py")},
            }
        )
    )
    assert worktree_gate.main() == 0, "the resuming session is blocked from its own worktree"


def test_a_bare_task_create_still_refuses_to_seize_a_foreign_marker(tmp_path: Path) -> None:
    """The authority is scoped to PREFLIGHT, not granted to every writer. `task-create`
    without `--allow-shared-slug` still leaves a foreign header alone — otherwise round-1
    CR-2 returns in full."""
    repo = _init_repo(tmp_path)
    worktree.task_create(repo, "alpha", session_uuid="0123456789ab", claude_session_id=SESS_A)
    worktree.release_session(repo, session_uuid="0123456789ab")
    worktree.task_create(repo, "alpha", session_uuid="ba9876543210", claude_session_id=SESS_B)
    assert (
        loop_marker.parse_marker_session_id(_marker(repo, "alpha").read_text(encoding="utf-8"))
        == SESS_A
    ), "a bare task-create seized a foreign marker"


def test_allow_shared_slug_no_longer_silently_grants_marker_seizure_alone(tmp_path: Path) -> None:
    """`--allow-shared-slug` means "two sessions may share this branch". Routing the marker
    authority through the same flag made the flag that means SHARE produce mutual exclusion;
    the two are now separate parameters."""
    import inspect

    params = inspect.signature(worktree.task_create).parameters
    assert "claim_marker" in params
    assert params["claim_marker"].default is False


def test_a_live_peer_still_blocks_the_claim_at_the_registry(tmp_path: Path) -> None:
    """The bound on round 4's widening, asserted rather than argued.

    `task_preflight` re-stamps the header because reaching that line means the branch claim
    was ACCEPTED. This pins the other half: a peer the registry can see is live is refused
    before the marker is ever touched, so a seizure requires a peer believed dead — the same
    window the branch claim already accepts.
    """
    repo = _init_repo(tmp_path)
    worktree.task_create(repo, "alpha", session_uuid="0123456789ab", claude_session_id=SESS_A)
    with pytest.raises(worktree.SharedSlugError):
        worktree.task_preflight(
            repo, "alpha", session_uuid="ba9876543210", claude_session_id=SESS_B
        )
    assert (
        loop_marker.parse_marker_session_id(_marker(repo, "alpha").read_text(encoding="utf-8"))
        == SESS_A
    )
