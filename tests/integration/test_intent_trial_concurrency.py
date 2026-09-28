"""Real-process crash/exclusion and Git landing conservation for AC-004."""

from __future__ import annotations

import importlib
import json
import subprocess
import sys
import threading
import time
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest
from hypothesis import HealthCheck, given, seed, settings
from hypothesis import strategies as st

from tests.unit import trial_fixture as fx


def api() -> Any:
    return importlib.import_module("harness_maker.intent_trial")


def run_python(root: Path, code: str, *args: str) -> subprocess.Popen[str]:
    return subprocess.Popen(
        [sys.executable, "-c", code, str(root), *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


@seed(20260925)
@given(count=st.integers(min_value=2, max_value=4))
@settings(
    max_examples=3, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)
def test_ac_004_parallel_decisions_conserve_committed_records(tmp_path: Path, count: int) -> None:
    import tempfile

    subject = api()
    with tempfile.TemporaryDirectory(dir=tmp_path) as folder:
        root = fx.build(Path(folder))
        fx.task(root)
        fx.cover(root)
        subject.reconcile(root, fx.TRIAL)
        code = """import sys,json
from pathlib import Path
from harness_maker import intent_trial as t
from tests.unit import trial_fixture as f
r=Path(sys.argv[1]); i=sys.argv[2]
import time
initial=t.status(r,f.TRIAL)
(r/('ready-'+i)).touch()
while not (r/'release').exists(): time.sleep(0.01)
d=f.decision('assessment',{'task':'a','verdict':'pass'},decision_id='judge-'+i)
for attempt in range(10):
 s=initial if attempt==0 else t.status(r,f.TRIAL)
 result=t.record_decision(r,f.TRIAL,d,expected_revision=s['revision'])
 if result.get('reason')!='revision_conflict': break
print(json.dumps(result))
"""
        procs = [run_python(root, code, str(i)) for i in range(count)]
        deadline = time.monotonic() + 15
        while len(list(root.glob("ready-*"))) < count:
            assert time.monotonic() < deadline
            assert all(p.poll() is None for p in procs)
            time.sleep(0.01)
        (root / "release").touch()
        for p in procs:
            out, err = p.communicate(timeout=30)
            assert p.returncode == 0, err
            assert json.loads(out)["changed"] is True, out
        ds = fx.read(root)["trial"]["decisions"]
        assert {x["id"] for x in ds if x["kind"] == "assessment"} == {
            f"judge-{i}" for i in range(count)
        }


@pytest.mark.parametrize("point", ["before", "after"])
def test_s2_writer_kill_releases_lock_and_preserves_atomic_document(
    tmp_path: Path, point: str
) -> None:
    subject = api()
    root = fx.build(tmp_path / "repo", legacy=True)
    before = fx.path(root).read_bytes()
    code = """import sys,os,signal
from pathlib import Path
from harness_maker import intent_trial as t
from tests.unit import trial_fixture as f
r=Path(sys.argv[1]); point=sys.argv[2]; original=os.replace
def cut(src,dst):
 if Path(dst)==f.path(r):
  if point=='after': original(src,dst)
  os.kill(os.getpid(),signal.SIGKILL)
 return original(src,dst)
os.replace=cut
s=t.status(r,f.TRIAL)
t.record_decision(r,f.TRIAL,f.decision('policy',{'enabled':True,'revision':'v1'}),expected_revision=s['revision'])
"""
    p = run_python(root, code, point)
    p.communicate(timeout=20)
    assert p.returncode is not None
    assert p.returncode < 0
    state = subject.status(root, fx.TRIAL)
    if point == "before":
        assert fx.path(root).read_bytes() == before
    else:
        assert fx.read(root)["trial"]["policy"]["enabled"] is True
    d = fx.decision("policy", {"enabled": True, "revision": "v1"})
    assert (
        subject.record_decision(root, fx.TRIAL, d, expected_revision=state["revision"])["reason"]
        != "lock_busy"
    )


def test_s2_shared_merge_fence_bounds_wait(tmp_path: Path) -> None:
    subject = api()
    root = fx.build(tmp_path / "repo")
    code = """import sys,time
from pathlib import Path
from harness_maker.worktree import _acquire_merge_fence
with _acquire_merge_fence(Path(sys.argv[1])):
 print('locked',flush=True);time.sleep(30)
"""
    p = run_python(root, code)
    try:
        assert p.stdout is not None
        assert p.stdout.readline().strip() == "locked"
        import time

        started = time.monotonic()
        result = subject.reconcile(root, fx.TRIAL)
        assert result["reason"] == "lock_busy"
        assert time.monotonic() - started < 7
    finally:
        p.terminate()
        p.communicate(timeout=10)


def test_s2_actual_task_land_persists_trial_only(tmp_path: Path) -> None:
    subject = api()
    from harness_maker import worktree

    root = fx.build(tmp_path / "repo")
    wt = root / ".worktrees/change"
    wt.parent.mkdir()
    fx.git(root, "worktree", "add", "-qb", "hm/change", str(wt))
    (wt / "feature.txt").write_text("feature")
    fx.git(wt, "add", "feature.txt")
    fx.git(wt, "commit", "-qm", "feature")
    fx.task(root)
    fx.cover(root)
    subject.reconcile(root, fx.TRIAL)
    other = root / "work-docs/PLAN-unrelated.md"
    other.write_text("unrelated WIP")
    fx.git(root, "add", str(other.relative_to(root)))
    current = fx.path(root).read_bytes()
    assert worktree.task_land(root, "change") == 0
    assert fx.path(root).read_bytes() == current
    assert fx.git(root, "show", "HEAD:work-docs/PLAN-field-trial.md") == current.decode().strip()
    assert (root / "feature.txt").read_text() == "feature"
    assert other.read_text() == "unrelated WIP"
    assert "work-docs/PLAN-unrelated.md" not in fx.git(root, "ls-tree", "-r", "--name-only", "HEAD")


def test_s2_supported_worktree_registration_waits_for_trial_fence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from harness_maker import worktree

    root = fx.build(tmp_path / "repo")
    claimed = threading.Event()
    original_claim = worktree.claim_task_branch

    def claim_then_signal(*args: Any, **kwargs: Any) -> Any:
        result = original_claim(*args, **kwargs)
        claimed.set()
        return result

    monkeypatch.setattr(worktree, "claim_task_branch", claim_then_signal)
    with ThreadPoolExecutor(max_workers=1) as pool:
        with worktree._acquire_merge_fence(root):
            future = pool.submit(worktree.task_create, root, "late", session_uuid="late-session")
            assert claimed.wait(5)
            assert not future.done()
            assert "hm/late" not in fx.git(root, "worktree", "list", "--porcelain")
        created = future.result(timeout=10)
    assert created == root / ".worktrees/late"
    assert "hm/late" in fx.git(root, "worktree", "list", "--porcelain")


def test_s2_task_refresh_waits_for_trial_fence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from harness_maker import worktree

    root = fx.build(tmp_path / "repo")
    wt = worktree.task_create(root, "refresh", session_uuid="refresh-session")
    assert wt.is_dir()
    (wt / "feature.txt").write_text("task feature\n")
    fx.git(wt, "add", "feature.txt")
    fx.git(wt, "commit", "-qm", "task feature")
    (root / "base.txt").write_text("base change\n")
    fx.git(root, "add", "base.txt")
    fx.git(root, "commit", "-qm", "base change")
    before_head = fx.git(wt, "rev-parse", "HEAD")
    base_head = fx.git(root, "rev-parse", "HEAD")
    entered = threading.Event()
    original_fence = worktree._acquire_merge_fence

    def instrumented_fence(*args: Any, **kwargs: Any) -> Any:
        entered.set()
        return original_fence(*args, **kwargs)

    monkeypatch.setattr(worktree, "_acquire_merge_fence", instrumented_fence)
    with ThreadPoolExecutor(max_workers=1) as pool:
        with original_fence(root):
            future = pool.submit(worktree.task_refresh, root, "refresh")
            assert entered.wait(5)
            assert not future.done()
            assert fx.git(wt, "rev-parse", "HEAD") == before_head
            assert not (wt / "base.txt").exists()
        assert future.result(timeout=10) == 0
    assert fx.git(wt, "rev-parse", "HEAD") != before_head
    assert fx.git(wt, "merge-base", "HEAD", base_head) == base_head
    assert (wt / "base.txt").read_text() == "base change\n"
    assert (wt / "feature.txt").read_text() == "task feature\n"


def test_s2_stale_branch_cannot_overwrite_canonical_trial(tmp_path: Path) -> None:
    subject = api()
    from harness_maker import worktree

    root = fx.build(tmp_path / "repo")
    wt = root / ".worktrees/stale"
    wt.parent.mkdir()
    fx.git(root, "worktree", "add", "-qb", "hm/stale", str(wt))
    fx.path(wt).write_text(fx.path(wt).read_text() + "\nStale branch edit\n")
    fx.git(wt, "add", ".")
    fx.git(wt, "commit", "-qm", "stale")
    fx.task(root)
    fx.cover(root)
    subject.reconcile(root, fx.TRIAL)
    before = fx.path(root).read_bytes()
    assert worktree.task_land(root, "stale") != 0
    assert fx.path(root).read_bytes() == before


def test_s2_legacy_finalize_refuses_before_hiding_trial(tmp_path: Path) -> None:
    subject = api()
    from harness_maker import worktree

    root = fx.build(tmp_path / "repo")
    wt = worktree.create("execute", root)[0]
    (wt / "feature.txt").write_text("feature")
    fx.task(root)
    fx.cover(root)
    subject.reconcile(root, fx.TRIAL)
    before = fx.path(root).read_bytes()
    stashes = fx.git(root, "stash", "list")
    assert worktree._cli_finalize([str(wt), "stage-only"]) != 0
    assert fx.path(root).read_bytes() == before
    assert fx.git(root, "stash", "list") == stashes
    assert wt.exists()


def test_s2_pending_legacy_trial_stash_is_discoverable_and_not_restored_unfenced(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from harness_maker import worktree

    subject = api()
    root = fx.build(tmp_path / "repo")
    fx.path(root).write_text(fx.path(root).read_text() + "\nHistorical trial WIP\n")
    fx.git(root, "stash", "push", "-m", "harness pending trial", "--", str(fx.path(root)))
    ref = fx.git(root, "rev-parse", "stash@{0}")
    assert subject.status(root, fx.TRIAL)["reason"] == "lifecycle_pending"

    def denied_fence(*_args: Any, **_kwargs: Any) -> Any:
        raise TimeoutError("held by another writer")

    monkeypatch.setattr(worktree, "_acquire_merge_fence", denied_fence)
    ok, kind, _ = worktree._fenced_restore_base_dirty(root, ref)
    assert not ok
    assert kind == "protected_trial_pending"
    assert fx.git(root, "stash", "list")
    assert "Historical trial WIP" not in fx.path(root).read_text()


def test_s2_trial_activated_during_the_fence_wait_blocks_the_unfenced_restore(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The fence wait can last `_FENCE_TIMEOUT`; a trial activated meanwhile must still stop
    the restore that would run outside every fence."""
    from harness_maker import intent_trial, worktree

    root = fx.build(tmp_path / "repo")
    fx.path(root).write_text(fx.path(root).read_text() + "\nStashed trial edit\n")
    fx.git(root, "stash", "push", "-m", "harness pending trial", "--", str(fx.path(root)))
    ref = fx.git(root, "rev-parse", "stash@{0}")
    answers = iter([False, True])
    monkeypatch.setattr(intent_trial, "stash_contains_protected_trial", lambda *_a: next(answers))

    def denied_fence(*_args: Any, **_kwargs: Any) -> Any:
        raise TimeoutError("held by another writer")

    monkeypatch.setattr(worktree, "_acquire_merge_fence", denied_fence)
    ok, kind, _ = worktree._fenced_restore_base_dirty(root, ref)
    assert (ok, kind) == (False, "protected_trial_pending")
    assert fx.git(root, "stash", "list")
    assert "Stashed trial edit" not in fx.path(root).read_text()


def test_s2_finalize_rejects_parseable_rewrite_of_committed_active_trial(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from harness_maker import worktree

    root = fx.build(tmp_path / "repo")
    wt = worktree.create("execute", root)[0]
    (wt / "feature.txt").write_text("feature")
    fx.write_doc(
        fx.path(root),
        {"type": "plan", "task_slug": fx.TRIAL},
        "## Evidence\nMarker-free working copy.\n",
    )
    before = fx.path(root).read_bytes()
    stashes = fx.git(root, "stash", "list")
    assert worktree._cli_finalize([str(wt), "stage-only"]) != 0
    assert "protected trial would be hidden or overwritten by finalize" in capsys.readouterr().err
    assert fx.path(root).read_bytes() == before
    assert fx.git(root, "stash", "list") == stashes
    assert wt.exists()


def test_s2_finalize_rechecks_trial_protection_after_fence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from harness_maker import intent_trial, worktree

    root = fx.build(tmp_path / "repo")
    active = fx.read(root)["trial"]
    fx.write_doc(fx.path(root), {"type": "plan", "task_slug": fx.TRIAL})
    fx.git(root, "add", ".")
    fx.git(root, "commit", "-qm", "marker-free baseline")
    assert not intent_trial.protected_trial_paths(root)
    wt = worktree.create("execute", root)[0]
    (wt / "feature.txt").write_text("feature\n")
    original_fence = worktree._acquire_merge_fence
    activated = False
    activated_bytes = b""

    @contextmanager
    def activate_inside_fence(
        base: Path, timeout: float = 60.0, lock_basename: str = "index.lock-hm"
    ) -> Iterator[None]:
        nonlocal activated, activated_bytes
        with original_fence(base, timeout=timeout, lock_basename=lock_basename):
            if not activated:
                activated = True
                fx.write_doc(
                    fx.path(root),
                    {"type": "plan", "task_slug": fx.TRIAL, "trial": active},
                )
                fx.git(root, "add", ".")
                fx.git(root, "commit", "-qm", "activate trial during fence wait")
                fx.path(root).write_text(fx.path(root).read_text() + "\nPending trial note\n")
                activated_bytes = fx.path(root).read_bytes()
            yield

    monkeypatch.setattr(worktree, "_acquire_merge_fence", activate_inside_fence)
    stashes = fx.git(root, "stash", "list")
    assert worktree._cli_finalize([str(wt), "stage-only"]) != 0
    assert activated
    assert "protected trial would be hidden or overwritten" in capsys.readouterr().err
    assert fx.path(root).read_bytes() == activated_bytes
    assert fx.git(root, "stash", "list") == stashes
    assert wt.exists()


def test_s2_land_failure_preserves_trial_and_rejects_unrelated_prose(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    subject = api()
    from harness_maker import worktree

    root = fx.build(tmp_path / "repo")
    wt = root / ".worktrees/change"
    wt.parent.mkdir()
    fx.git(root, "worktree", "add", "-qb", "hm/change", str(wt))
    (wt / "feature.txt").write_text("feature")
    fx.git(wt, "add", "feature.txt")
    fx.git(wt, "commit", "-qm", "feature")
    fx.task(root)
    fx.cover(root)
    subject.reconcile(root, fx.TRIAL)
    before = fx.path(root).read_bytes()
    real = worktree._run

    def failing(args: list[str], **kw: Any) -> Any:
        if args[:2] == ["git", "commit"] and kw.get("cwd") == root:
            raise RuntimeError("injected commit failure")
        return real(args, **kw)

    monkeypatch.setattr(worktree, "_run", failing)
    assert worktree.task_land(root, "change") != 0
    assert fx.path(root).read_bytes() == before
    monkeypatch.setattr(worktree, "_run", real)
    fx.path(root).write_bytes(before + b"\nUnrelated unapproved prose\n")
    assert worktree.task_land(root, "change") != 0
    assert "Unrelated unapproved prose" not in fx.git(
        root, "show", "HEAD:work-docs/PLAN-field-trial.md"
    )


def test_s2_unsupported_lock_never_writes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    subject = api()
    import fcntl

    root = fx.build(tmp_path / "repo", legacy=True)
    s = subject.status(root, fx.TRIAL)
    before = fx.path(root).read_bytes()

    def unavailable(*args: Any, **kw: Any) -> None:
        raise OSError(95, "unsupported locking")

    monkeypatch.setattr(fcntl, "flock", unavailable)
    result = subject.record_decision(
        root,
        fx.TRIAL,
        fx.decision("policy", {"enabled": True, "revision": "v1"}),
        expected_revision=s["revision"],
    )
    assert result["reason"] == "unsupported_lock"
    assert result.get("changed") is False
    assert fx.path(root).read_bytes() == before
    # ADR-003: status shares the fence, so it reports the storage limit instead of an
    # unfenced read.
    assert subject.status(root, fx.TRIAL)["reason"] == "unsupported_lock"


@pytest.mark.parametrize("competitor", ["collector", "revoke", "land", "finalize"])
def test_ac_004_collector_overlaps_supported_writers(tmp_path: Path, competitor: str) -> None:
    """Pause a real collector immediately before publication while it holds exclusion.

    A second process is observed entering its supported write operation, and must
    remain blocked until release or report a safe bounded conflict. No lock-only
    surrogate stands in for task_land or legacy finalize.
    """
    subject = api()
    from harness_maker import worktree

    root = fx.build(tmp_path / "repo")
    if competitor == "finalize":
        wt = worktree.create("execute", root)[0]
    else:
        wt = root / ".worktrees/feature"
        wt.parent.mkdir()
        fx.git(root, "worktree", "add", "-qb", "hm/feature", str(wt))
    (wt / "feature.txt").write_text("feature")
    if competitor == "land":
        fx.git(wt, "add", "feature.txt")
        fx.git(wt, "commit", "-qm", "feature")
    fx.task(root)
    fx.cover(root)
    revision = subject.status(root, fx.TRIAL)["revision"]
    before = fx.path(root).read_bytes()
    paused = run_python(
        root,
        r"""import os,sys,time,json
from pathlib import Path
from harness_maker import intent_trial as t
from tests.unit import trial_fixture as f
r=Path(sys.argv[1]); replace=os.replace
 def_placeholder
""".replace(
            " def_placeholder",
            """def publish(src,dst):
 if Path(dst)==f.path(r):
  (r/'at-publication').touch()
  while not (r/'continue-publication').exists(): time.sleep(.01)
 return replace(src,dst)
os.replace=publish
print(json.dumps(t.reconcile(r,f.TRIAL)),flush=True)""",
        ),
    )
    other = None
    try:
        deadline = time.monotonic() + 15
        while not (root / "at-publication").exists():
            assert time.monotonic() < deadline
            assert paused.poll() is None
            time.sleep(0.01)
        assert fx.path(root).read_bytes() == before
        other = run_python(
            root,
            """import sys,json
from pathlib import Path
from harness_maker import intent_trial as t,worktree
from tests.unit import trial_fixture as f
r=Path(sys.argv[1]); mode=sys.argv[2]; wt=sys.argv[3]
(r/'competitor-entered').touch()
if mode=='collector': result=t.reconcile(r,f.TRIAL)
elif mode=='revoke':
 result=t.record_decision(r,f.TRIAL,f.decision('policy',{'enabled':False,'revision':'v2'}),expected_revision=sys.argv[4])
elif mode=='land': result={'exit':worktree.task_land(r,'feature')}
else: result={'exit':worktree._cli_finalize([wt,'stage-only'])}
print('RESULT='+json.dumps(result),flush=True)
""",
            competitor,
            str(wt),
            revision,
        )
        deadline = time.monotonic() + 15
        while not (root / "competitor-entered").exists():
            assert time.monotonic() < deadline
            assert other.poll() is None
            time.sleep(0.01)
        # Keep the holder paused for the whole bounded wait. The competitor
        # cannot succeed with unlocked publication while the holder has old bytes.
        out, err = other.communicate(timeout=8)
        assert other.returncode == 0, err
        result = json.loads(out.rsplit("RESULT=", 1)[1])
        if competitor in {"land", "finalize"}:
            assert result["exit"] != 0
        else:
            assert result["reason"] == "lock_busy"
        assert fx.path(root).read_bytes() == before
        (root / "continue-publication").touch()
        out, err = paused.communicate(timeout=15)
        assert paused.returncode == 0, err
        assert json.loads(out)["cohort"] == ["a"]
        if competitor == "revoke":
            state = subject.status(root, fx.TRIAL)
            d = fx.decision("policy", {"enabled": False, "revision": "v2"})
            assert subject.record_decision(root, fx.TRIAL, d, expected_revision=state["revision"])[
                "changed"
            ]
            revoked = fx.path(root).read_bytes()
            assert subject.reconcile(root, fx.TRIAL)["reason"] == "authority_required"
            assert fx.path(root).read_bytes() == revoked
        assert fx.read(root)["trial"]["members"][0]["task"] == "a"
    finally:
        for process in (paused, other):
            if process is not None and process.poll() is None:
                process.kill()
                process.communicate(timeout=10)


def test_s2_task_start_waits_out_a_fence_held_past_the_telemetry_budget(tmp_path: Path) -> None:
    """A peer's land holds the merge fence up to `_FENCE_TIMEOUT`; a task start is required
    trial evidence, so it must outlast the 5 s telemetry budget instead of failing preflight.
    Held for 6.5 s: a 5 s wait raises here."""
    from harness_maker import stage_spans, worktree

    root = fx.build(tmp_path / "repo").resolve()
    held = threading.Event()

    def hold() -> None:
        with worktree._acquire_merge_fence(root, timeout=10.0):
            held.set()
            time.sleep(6.5)

    peer = threading.Thread(target=hold)
    peer.start()
    try:
        assert held.wait(10.0)
        worktree._emit_stage_span(root, stage="hm:execute", task_slug="feat-x")
    finally:
        peer.join()
    events, _ = stage_spans.read_events(stage_spans.ledger_path(root))
    assert [(e.stage, e.task_slug) for e in events][-1] == ("hm:execute", "feat-x")


def test_s2_task_start_span_failure_is_fatal_only_while_a_trial_is_active(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """ADR-006: a missing task start costs trial evidence only when a trial is active, so a
    project that never activated one keeps warn-and-proceed telemetry."""
    from harness_maker import stage_spans, worktree

    active = fx.build(tmp_path / "active").resolve()
    plain = tmp_path / "plain"
    plain.mkdir()
    fx.git(plain, "init", "-q")
    fx.git(plain, "config", "user.name", "Test User")
    fx.git(plain, "config", "user.email", "test@example.invalid")
    (plain / "README.md").write_text("no trial here\n")
    fx.git(plain, "add", ".")
    fx.git(plain, "commit", "-qm", "plain baseline")
    budgets: list[float] = []

    def refuse(*_a: object, fence_timeout: float = 5.0, **_k: object) -> Path:
        budgets.append(fence_timeout)
        raise TimeoutError("merge fence busy")

    monkeypatch.setattr(stage_spans, "emit_event", refuse)
    with pytest.raises(RuntimeError, match="task start was not recorded for feat-x"):
        worktree._emit_stage_span(active, stage="hm:execute", task_slug="feat-x")
    worktree._emit_stage_span(plain.resolve(), stage="hm:execute", task_slug="feat-x")
    worktree._emit_stage_span(active, stage="hm:execute", task_slug=None)
    assert capsys.readouterr().err.count("[span] emission failed (non-fatal)") == 2
    assert budgets == [worktree._FENCE_TIMEOUT, 5.0, 5.0]

    # An unreadable trial directory counts as active: evidence is never skipped on doubt.
    from harness_maker import intent_trial

    def unreadable(_root: Path) -> list[str]:
        raise ValueError("trial PLAN directory escapes repository")

    monkeypatch.setattr(intent_trial, "active_trials", unreadable)
    with pytest.raises(RuntimeError, match="task start was not recorded for feat-x"):
        worktree._emit_stage_span(plain.resolve(), stage="hm:execute", task_slug="feat-x")
    assert budgets[-1] == worktree._FENCE_TIMEOUT


def test_s2_status_reads_under_the_trial_fence(tmp_path: Path) -> None:
    """ADR-003: a status read while another writer holds the trial fence past the budget
    reports `lock_busy` instead of reading sources mid-write."""
    from harness_maker import worktree

    subject = api()
    root = fx.build(tmp_path / "repo").resolve()
    fx.task(root, "a", fx.T1, ack=True)
    held = threading.Event()

    def hold() -> None:
        with worktree._acquire_merge_fence(root, timeout=10.0):
            held.set()
            time.sleep(6.5)

    peer = threading.Thread(target=hold)
    peer.start()
    try:
        assert held.wait(10.0)
        busy = subject.status(root, fx.TRIAL)
    finally:
        peer.join()
    assert (busy["reason"], busy["action"]) == ("lock_busy", "retry_next_invocation")
    assert subject.status(root, fx.TRIAL)["reason"] == "awaiting_reconciliation"


def _stash_repo(root: Path) -> Path:
    root.mkdir()
    fx.git(root, "init", "-q", "-b", "main")
    fx.git(root, "config", "user.name", "Test User")
    fx.git(root, "config", "user.email", "test@example.invalid")
    (root / "README.md").write_text("# repo\n")
    (root / ".gitignore").write_text(
        ".worktrees/\n.claude/.hm-loop-*\n.claude/.hm-finalize-stash-*\n"
    )
    fx.git(root, "add", "README.md", ".gitignore")
    fx.git(root, "commit", "-qm", "init")
    return root


def test_s2_post_commit_pop_never_restores_over_a_trial_activated_since_the_stash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A deferred finalize stash is popped by a later wrapup, possibly in another session;
    a trial activated in between must stop that pop exactly as the fenced restore does."""
    from harness_maker import intent_trial, worktree

    repo = _stash_repo(tmp_path / "repo")
    (wt,) = worktree.create("execute", repo)
    monkeypatch.setenv("HM_OWNED_SESSION_UUIDS", worktree._extract_uuid_from_wt_name(wt.name))
    (wt / "feature.py").write_text("def feature() -> None:\n    pass\n")
    fx.git(wt, "add", "feature.py")
    fx.git(wt, "commit", "-qm", "add feature")
    (repo / "README.md").write_text("# repo\n\nUSER WIP\n")
    fx.git(repo, "add", "README.md")
    assert worktree._cli_finalize([str(wt), "stage-only"]) == 0
    fx.git(repo, "commit", "-qm", "wrapup: stage-only result")
    ref_file = repo / ".claude" / f".hm-finalize-stash-{wt.name}"
    assert ref_file.exists()

    monkeypatch.setattr(intent_trial, "stash_contains_protected_trial", lambda *_a: True)
    assert worktree._cli_post_commit_pop([str(repo)]) == 1
    assert ref_file.exists()
    assert f"hm-finalize-{wt.name}" in fx.git(repo, "stash", "list")
    assert (repo / "README.md").read_text() == "# repo\n"
    assert "Stash:" in capsys.readouterr().err


def test_s2_fenced_restore_rechecks_trial_protection_after_a_successful_wait(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The success path of the fenced restore must re-check too: a trial can be activated
    while the fence is being waited for and then granted."""
    from harness_maker import intent_trial, worktree

    root = fx.build(tmp_path / "repo")
    fx.path(root).write_text(fx.path(root).read_text() + "\nStashed trial edit\n")
    fx.git(root, "stash", "push", "-m", "harness pending trial", "--", str(fx.path(root)))
    ref = fx.git(root, "rev-parse", "stash@{0}")
    answers = iter([False, True])
    monkeypatch.setattr(intent_trial, "stash_contains_protected_trial", lambda *_a: next(answers))
    ok, kind, _ = worktree._fenced_restore_base_dirty(root, ref)
    assert (ok, kind) == (False, "protected_trial_pending")
    assert fx.git(root, "stash", "list")
    assert "Stashed trial edit" not in fx.path(root).read_text()


def test_s2_unignored_secret_copy_is_removed_before_the_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Whichever task-create path retries it, a copied secret that git would not ignore
    must not stay on disk after the failure."""
    from harness_maker import worktree

    repo = _stash_repo(tmp_path / "repo")
    (repo / ".gitignore").write_text((repo / ".gitignore").read_text() + ".env\n")
    (repo / ".env").write_text("TOKEN=secret\n")
    wt = tmp_path / "wt"
    wt.mkdir()
    fx.git(wt, "init", "-q")
    real_run = worktree._run

    def refuse_check_ignore(args: list[str], *a: Any, **kw: Any) -> Any:
        if args[:2] == ["git", "check-ignore"] and kw.get("cwd") == wt:
            raise RuntimeError("not ignored")
        return real_run(args, *a, **kw)

    monkeypatch.setattr(worktree, "_run", refuse_check_ignore)
    with pytest.raises(RuntimeError, match="copied include is not ignored"):
        worktree._copy_and_exclude_secrets(repo, wt, [".env"])
    assert not (wt / ".env").exists()
