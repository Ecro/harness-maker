"""SPEC scenario tests exercise durable records, not collection self-report.

Golden source tables are loaded from the approved SPEC. Parametric fixtures select
actual repository arrangements; expected outputs never seed the subject state.

"""

from __future__ import annotations

import copy
import importlib
import json
import os
from pathlib import Path
from typing import Any

import pytest
import yaml
from hypothesis import HealthCheck, given, seed, settings
from hypothesis import strategies as st
from hypothesis.database import DirectoryBasedExampleDatabase

from harness_maker.spec_machine import GoldenRow, load_golden_table
from tests.unit import trial_fixture as fx

SPEC = Path(__file__).parents[2] / "specs/SPEC-intent-feedback-continuity.machine.yaml"
settings.register_profile(
    "trial-ci", derandomize=True, max_examples=6, deadline=None, database=None
)
settings.register_profile(
    "trial-dev",
    max_examples=12,
    deadline=None,
    database=DirectoryBasedExampleDatabase(".hypothesis/trial"),
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
settings.load_profile(
    "trial-ci"
    if os.environ.get("HYPOTHESIS_PROFILE", "ci" if os.environ.get("CI") else "dev") == "ci"
    else "trial-dev"
)


def api() -> Any:
    return importlib.import_module("harness_maker.intent_trial")


def rows(ac: str) -> list[GoldenRow]:
    return load_golden_table(SPEC, ac)


def snapshot(root: Path) -> dict[str, bytes]:
    return {
        str(p.relative_to(root)): p.read_bytes()
        for p in root.rglob("*")
        if p.is_file() and ".git" not in p.relative_to(root).parts
    }


def ready(
    root: Path, tasks: tuple[str, ...] = ("a",), *, terminal: bool = False, evidence: bool = True
) -> Path:
    fx.build(root)
    for n, slug in enumerate(tasks, 1):
        fx.task(root, slug, f"2026-09-22T0{n}:00:00Z", terminal=terminal, evidence=evidence)
    assert fx.cover(root)["changed"] is True
    return root


def assess(root: Path, task: str, verdict: str) -> dict[str, Any]:
    s = api().status(root, fx.TRIAL)
    result: dict[str, Any] = api().record_decision(
        root,
        fx.TRIAL,
        fx.decision("assessment", {"task": task, "verdict": verdict}, decision_id=f"assess-{task}"),
        expected_revision=s["revision"],
    )
    return result


@pytest.mark.parametrize("artifact", ["RESEARCH", "SPEC", "PLAN"])
def test_s1_next_session_enrolls_without_plan_or_collector(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, artifact: str
) -> None:
    subject = api()
    root = fx.build(tmp_path / "repo")
    wt = root / ".worktrees/task-a"
    wt.parent.mkdir()
    fx.git(root, "worktree", "add", "-qb", "hm/task-a", str(wt))
    fx.task(wt, artifact=artifact)
    # An arbitrary sibling directory is not a registered evidence source.
    fx.task(root / ".worktrees/unregistered", "noise", fx.T0, artifact=artifact)
    fx.cover(root)
    monkeypatch.setenv("HM_SESSION_ID", "B")
    result = subject.reconcile(wt, fx.TRIAL)
    assert result["cohort"] == ["a"]
    assert result["collection"] == "collecting"
    assert result["outcome"] == "pending"
    assert fx.read(root)["trial"]["members"][0]["task"] == "a"
    before = snapshot(root)
    subject.status(root, fx.TRIAL)
    subject.reconcile(root, fx.TRIAL, dry_run=True)
    assert snapshot(root) == before


def test_s1_member_source_refs_match_artifact_slug_not_worktree_name(tmp_path: Path) -> None:
    subject = api()
    root = fx.build(tmp_path / "repo")
    wt = root / ".worktrees/intent-feedback-continuity"
    wt.parent.mkdir()
    fx.git(root, "worktree", "add", "-qb", "hm/intent-feedback-continuity", str(wt))
    fx.task(wt, "docs-release-sync", fx.T1)
    fx.task(wt, "intent-feedback-continuity", fx.T2)
    fx.cover(root)
    assert subject.reconcile(root, fx.TRIAL)["cohort"] == [
        "docs-release-sync",
        "intent-feedback-continuity",
    ]
    members = fx.read(root)["trial"]["members"]
    assert members[0]["source_refs"] == [f"worktree:{wt}:work-docs/PLAN-docs-release-sync.md"]
    assert members[1]["source_refs"] == [
        f"worktree:{wt}:work-docs/PLAN-intent-feedback-continuity.md"
    ]


def test_s1_existing_member_source_refs_are_repaired_from_exact_artifacts(tmp_path: Path) -> None:
    subject = api()
    root = fx.build(tmp_path / "repo")
    fx.task(root, "a", fx.T1)
    path = fx.path(root)
    meta = fx.read(root)
    meta["trial"]["members"] = [
        {"task": "a", "start": fx.T1, "source_refs": ["worktree:a:work-docs/PLAN-wrong.md"]}
    ]
    fx.write_doc(path, meta, path.read_text().split("---", 2)[2])
    fx.cover(root)
    result = subject.reconcile(root, fx.TRIAL)
    assert result["changed"] is True
    assert fx.read(root)["trial"]["members"][0]["source_refs"] == ["base:work-docs/PLAN-a.md"]


def test_s3_user_decision_is_persisted_and_replay_is_safe(tmp_path: Path) -> None:
    subject = api()
    root = ready(tmp_path / "repo", terminal=True)
    subject.reconcile(root, fx.TRIAL)
    before = subject.status(root, fx.TRIAL)
    d = fx.decision("assessment", {"task": "a", "verdict": "fail"})
    result = subject.record_decision(root, fx.TRIAL, d, expected_revision=before["revision"])
    assert result["outcome"] == "failed"
    stored = fx.read(root)["trial"]["decisions"]
    assert d in stored
    bytes_before = snapshot(root)
    assert (
        subject.record_decision(root, fx.TRIAL, d, expected_revision=before["revision"])["changed"]
        is False
    )
    assert snapshot(root) == bytes_before
    assert subject.reconcile(root, fx.TRIAL)["outcome"] == "failed"
    changed = copy.deepcopy(d)
    changed["payload"]["verdict"] = "pass"
    assert (
        subject.record_decision(root, fx.TRIAL, changed, expected_revision=result["revision"])[
            "reason"
        ]
        == "decision_conflict"
    )
    assert fx.read(root)["trial"]["decisions"] == stored


@seed(20260923)
@given(order=st.permutations(("a", "b", "c")), repeats=st.integers(1, 4))
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_ac_003_snapshot_permutation_and_replay(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, order: tuple[str, ...], repeats: int
) -> None:
    import tempfile

    subject = api()
    with tempfile.TemporaryDirectory(dir=tmp_path) as folder:
        root = fx.build(Path(folder))
        for slug in order:
            fx.task(root, slug, {"a": fx.T1, "b": fx.T2, "c": fx.T3}[slug])
        # The fixed snapshot contains identical stable events in two stage artifacts.
        for slug in order:
            source = root / f"work-docs/PLAN-{slug}.md"
            (root / f"work-docs/RESEARCH-{slug}.md").write_bytes(source.read_bytes())
        fx.cover(root)
        assert subject.reconcile(root, fx.TRIAL)["cohort"] == ["a", "b", "c"]
        assess(root, "a", "fail")
        before = snapshot(root)
        for n in range(repeats):
            monkeypatch.setenv("HM_SESSION_ID", f"replacement-{n}")
            result = subject.reconcile(root, fx.TRIAL)
            assert result["cohort"] == ["a", "b", "c"]
            assert result["assessments"]["a"] == "fail"
        assert snapshot(root) == before
        # Same identity with different payload is a conflict, never last-writer-wins.
        source = root / "work-docs/RESEARCH-a.md"
        data = yaml.safe_load(source.read_text().split("---", 2)[1])
        data["trial_feedback"][0]["decision"] = "Contradictory decision"
        fx.write_doc(source, data)
        canonical = fx.path(root).read_bytes()
        result = subject.reconcile(root, fx.TRIAL)
        assert result["reason"] == "source_conflict"
        assert fx.path(root).read_bytes() == canonical


@seed(20260924)
@given(replays=st.integers(1, 4), prose=st.text(alphabet="ABC xyz012", min_size=1, max_size=25))
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_ac_007_migration_preserves_history(tmp_path: Path, replays: int, prose: str) -> None:
    import tempfile

    subject = api()
    with tempfile.TemporaryDirectory(dir=tmp_path) as folder:
        root = fx.build(Path(folder), legacy=True)
        p = fx.path(root)
        history = (
            "\n| Order | Task slug / PLAN | Start / terminal times | "
            "Observation → update → decision evidence | Conversation evidence | User assessment |\n"
            "|---|---|---|---|---|---|\n"
            f"| 1 | a / PLAN-a.md | {fx.T1} / {fx.T3} (aborted) | "
            "evidence-a | conversation:failure-a | fail |\n"
            "\nUser intervention: reminder-a at conversation:failure-a.\n"
        )
        p.write_text(
            p.read_text()
            .replace("Enrolled: 0/3", "Enrolled: 1/3")
            .replace("Outcome: pending", "Outcome: failed")
            + history
            + "\nLegacy evidence: "
            + prose
            + "\n"
        )
        old = p.read_text()
        preview = subject.reconcile(root, fx.TRIAL, dry_run=True)
        assert p.read_text() == old
        assert preview["reason"] == "policy_revision_required"
        assert preview["cohort"] == ["a"]
        assert preview["assessments"]["a"] == "fail"
        assert preview["outcome"] == "failed"
        denied = subject.reconcile(root, fx.TRIAL)
        assert denied["reason"] == "policy_revision_required"
        assert p.read_text() == old
        d = fx.decision("policy", {"enabled": True, "revision": "v1"})
        result = subject.record_decision(
            root, fx.TRIAL, d, expected_revision=subject.status(root, fx.TRIAL)["revision"]
        )
        assert result["changed"] is True
        migrated = p.read_bytes()
        assert "Legacy evidence: " + prose in p.read_text()
        assert fx.read(root)["trial"]["activation"] == fx.T0
        assert "old-session" in p.read_text()
        assert history in p.read_text()
        assert result["cohort"] == ["a"]
        assert result["assessments"]["a"] == "fail"
        assert result["outcome"] == "failed"
        assert fx.read(root)["trial"]["members"][0]["task"] == "a"
        migrated_decisions = fx.read(root)["trial"]["decisions"]
        historical_assessment = [
            item
            for item in migrated_decisions
            if item.get("kind") == "assessment" and item.get("payload", {}).get("task") == "a"
        ]
        assert len(historical_assessment) == 1
        assert historical_assessment[0]["payload"]["verdict"] == "fail"
        assert "conversation:failure-a" in historical_assessment[0]["evidence_refs"]
        assert "legacy" in historical_assessment[0]["authority"]
        assert subject.status(root, fx.TRIAL)["assessments"]["a"] == "fail"
        for _ in range(replays):
            subject.record_decision(root, fx.TRIAL, d, expected_revision=result["revision"])
        assert p.read_bytes() == migrated
        # Divergent typed and legacy judgments must not erase the original failure.
        data = fx.read(root)
        data["trial"]["members"] = [{"task": "b"}]
        body = p.read_text().split("---", 2)[2]
        fx.write_doc(p, data, body)
        divergent = p.read_bytes()
        assert subject.reconcile(root, fx.TRIAL)["reason"] == "source_conflict"
        assert p.read_bytes() == divergent


def test_s3_missing_changed_and_equal_time_sources_are_not_success(tmp_path: Path) -> None:
    subject = api()
    root = ready(tmp_path / "repo")
    fx.task(root, "b", fx.T1)
    s = subject.reconcile(root, fx.TRIAL)
    assert s["reason"] in {"source_conflict", "order_conflict"}
    assert s["cohort"] == []
    assert s["outcome"] != "passed"
    ledger = root / ".claude/observability/stage-spans.jsonl"
    ledger.write_text(ledger.read_text() + "{broken\n")
    assert subject.status(root, fx.TRIAL)["reason"] == "source_incomplete"


def test_s3_late_preceding_start_preserves_committed_member(tmp_path: Path) -> None:
    subject = api()
    root = ready(tmp_path / "repo", ("b",))
    subject.reconcile(root, fx.TRIAL)
    fx.task(root, "a", "2026-09-22T00:30:00Z")
    before = fx.read(root)["trial"]["members"]
    s = subject.reconcile(root, fx.TRIAL)
    assert s["reason"] == "order_conflict"
    assert fx.read(root)["trial"]["members"] == before


def test_s1_reviewed_legacy_prefix_extends_from_typed_ack_after_handoff(
    tmp_path: Path,
) -> None:
    subject = api()
    root = ready(tmp_path / "repo", ("a", "b"))
    assert subject.reconcile(root, fx.TRIAL)["cohort"] == ["a", "b"]
    fx.task(root, "c", fx.T3, ack=True)
    result = subject.reconcile(root, fx.TRIAL)
    assert result["cohort"] == ["a", "b", "c"]
    assert [m["task"] for m in fx.read(root)["trial"]["members"]] == ["a", "b", "c"]


def test_s1_approved_equal_time_order_survives_later_acknowledged_start(
    tmp_path: Path,
) -> None:
    subject = api()
    root = fx.build(tmp_path / "repo")
    fx.task(root, "a", fx.T1)
    fx.task(root, "b", fx.T1)
    observed = subject.status(root, fx.TRIAL)
    review = fx.decision(
        "source_review",
        {
            "inventory": observed["inventory"],
            "through": observed["cutoff"],
            "disposition": "accepted",
            "ordered_tasks": ["b", "a"],
            "excluded_tasks": [],
        },
    )
    subject.record_decision(root, fx.TRIAL, review, expected_revision=observed["revision"])
    assert subject.reconcile(root, fx.TRIAL)["cohort"] == ["b", "a"]

    fx.task(root, "c", fx.T3, ack=True)
    assert subject.status(root, fx.TRIAL)["reason"] == "awaiting_reconciliation"
    assert subject.reconcile(root, fx.TRIAL)["cohort"] == ["b", "a", "c"]
    assert [m["task"] for m in fx.read(root)["trial"]["members"]] == ["b", "a", "c"]

    # Repeat the approved tie with an open third slot: a capacity-only guard
    # cannot satisfy the earlier-start invariant.
    earlier = fx.build(tmp_path / "earlier")
    fx.task(earlier, "a", fx.T1)
    fx.task(earlier, "b", fx.T1)
    earlier_status = subject.status(earlier, fx.TRIAL)
    earlier_review = fx.decision(
        "source_review",
        {
            "inventory": earlier_status["inventory"],
            "through": earlier_status["cutoff"],
            "disposition": "accepted",
            "ordered_tasks": ["b", "a"],
            "excluded_tasks": [],
        },
    )
    subject.record_decision(
        earlier, fx.TRIAL, earlier_review, expected_revision=earlier_status["revision"]
    )
    assert subject.reconcile(earlier, fx.TRIAL)["cohort"] == ["b", "a"]
    before = fx.read(earlier)["trial"]["members"]
    fx.task(earlier, "c", "2026-09-22T00:30:00Z", ack=True)
    rejected = subject.reconcile(earlier, fx.TRIAL)
    assert rejected["reason"] == "order_conflict"
    assert rejected["cohort"] == ["b", "a"]
    assert fx.read(earlier)["trial"]["members"] == before

    # Same approved tie and a later start, but no typed start acknowledgment:
    # chronology alone must not extend the cohort.
    unacked = fx.build(tmp_path / "unacked")
    fx.task(unacked, "a", fx.T1)
    fx.task(unacked, "b", fx.T1)
    unacked_status = subject.status(unacked, fx.TRIAL)
    unacked_review = fx.decision(
        "source_review",
        {
            "inventory": unacked_status["inventory"],
            "through": unacked_status["cutoff"],
            "disposition": "accepted",
            "ordered_tasks": ["b", "a"],
            "excluded_tasks": [],
        },
    )
    subject.record_decision(
        unacked, fx.TRIAL, unacked_review, expected_revision=unacked_status["revision"]
    )
    assert subject.reconcile(unacked, fx.TRIAL)["cohort"] == ["b", "a"]
    before = fx.read(unacked)["trial"]["members"]
    fx.task(unacked, "c", fx.T3)
    assert subject.status(unacked, fx.TRIAL)["reason"] == "source_conflict"
    blocked = subject.reconcile(unacked, fx.TRIAL)
    assert blocked["reason"] == "source_conflict"
    assert blocked["cohort"] == ["b", "a"]
    assert fx.read(unacked)["trial"]["members"] == before


def approved_tie(root: Path) -> list[dict[str, Any]]:
    """a and b start together; the user orders them [b, a] and reconcile commits it."""
    subject = api()
    fx.task(root, "a", fx.T1)
    fx.task(root, "b", fx.T1)
    s = subject.status(root, fx.TRIAL)
    review = fx.decision(
        "source_review",
        {
            "inventory": s["inventory"],
            "through": s["cutoff"],
            "disposition": "accepted",
            "ordered_tasks": ["b", "a"],
            "excluded_tasks": [],
        },
    )
    subject.record_decision(root, fx.TRIAL, review, expected_revision=s["revision"])
    assert subject.reconcile(root, fx.TRIAL)["cohort"] == ["b", "a"]
    members: list[dict[str, Any]] = fx.read(root)["trial"]["members"]
    return members


def test_s1_approved_tie_survives_a_same_slug_stage_resume(tmp_path: Path) -> None:
    """Every later stage entry appends a start row for its slug; that is not a new task and
    must not undo the user's order (the untied case already stays `pending`)."""
    subject = api()
    root = fx.build(tmp_path / "repo")
    members = approved_tie(root)
    ledger = root / ".claude/observability/stage-spans.jsonl"
    row = json.loads(ledger.read_text().splitlines()[-1])
    row.update(task_slug="b", ts=fx.T3, stage="hm:execute")
    with ledger.open("a") as f:
        f.write(json.dumps(row) + "\n")
    assert subject.status(root, fx.TRIAL)["reason"] == "pending"
    assert subject.reconcile(root, fx.TRIAL)["cohort"] == ["b", "a"]
    assert fx.read(root)["trial"]["members"] == members


def test_s3_append_that_moves_a_tied_member_earlier_is_not_laundered(tmp_path: Path) -> None:
    """Keeping the approved order across an append-only ledger must not keep it when the
    append gives a member an earlier first start than the user reviewed."""
    subject = api()
    root = fx.build(tmp_path / "repo")
    members = approved_tie(root)
    ledger = root / ".claude/observability/stage-spans.jsonl"
    row = json.loads(ledger.read_text().splitlines()[-1])
    row.update(task_slug="a", ts=fx.T0, stage="hm:execute")
    with ledger.open("a") as f:
        f.write(json.dumps(row) + "\n")
    assert subject.status(root, fx.TRIAL)["reason"] == "order_conflict"
    assert subject.reconcile(root, fx.TRIAL)["cohort"] == ["b", "a"]
    assert fx.read(root)["trial"]["members"] == members


def test_s1_later_tasks_that_tie_do_not_extend_an_approved_order(tmp_path: Path) -> None:
    """The approval covered a and b only; which of c and d takes the last slot is a new tie
    the user has not ordered."""
    subject = api()
    root = fx.build(tmp_path / "repo")
    members = approved_tie(root)
    fx.task(root, "d", fx.T3, ack=True)
    fx.task(root, "c", fx.T3, ack=True)
    assert subject.status(root, fx.TRIAL)["reason"] == "order_conflict"
    blocked = subject.reconcile(root, fx.TRIAL)
    assert (blocked["reason"], blocked["cohort"]) == ("order_conflict", ["b", "a"])
    assert fx.read(root)["trial"]["members"] == members


def test_s2_rejected_decision_reports_the_action_for_its_own_reason(tmp_path: Path) -> None:
    """A rejection must not carry the next action status computed before the check ran.

    Drives every early rejection that has a trial to read; the trial-less ones are
    `test_s2_trial_less_rejection_keeps_the_readers_classification`."""
    subject = api()
    legacy = fx.build(tmp_path / "legacy", legacy=True)
    assert subject.status(legacy, fx.TRIAL)["action"] == "request_policy_decision"
    stale = subject.record_decision(
        legacy,
        fx.TRIAL,
        fx.decision("policy", {"enabled": True, "revision": "v1"}),
        expected_revision="0" * 64,
    )
    assert (stale["reason"], stale["action"]) == ("revision_conflict", "none")

    root = ready(tmp_path / "repo", ("a",))
    assert subject.status(root, fx.TRIAL)["action"] == "reconcile"
    outside = assess(root, "a", "pass")
    assert (outside["reason"], outside["action"]) == (
        "authority_required",
        "request_policy_decision",
    )

    policy = fx.decision("policy", {"enabled": True, "revision": "v1"}, decision_id="p-extra")
    s = subject.status(root, fx.TRIAL)
    assert subject.record_decision(root, fx.TRIAL, policy, expected_revision=s["revision"])[
        "changed"
    ]
    s = subject.status(root, fx.TRIAL)
    assert s["action"] == "reconcile"
    replay = subject.record_decision(root, fx.TRIAL, policy, expected_revision=s["revision"])
    assert (replay["reason"], replay["action"]) == ("replay", "none")
    changed = dict(policy, payload={"enabled": True, "revision": "v2"})
    clash = subject.record_decision(root, fx.TRIAL, changed, expected_revision=s["revision"])
    assert (clash["reason"], clash["action"]) == ("decision_conflict", "none")

    # Prose added to the published trial document after its receipt was written.
    doc = fx.path(root)
    doc.write_text(doc.read_text() + "\nstray prose\n")
    s = subject.status(root, fx.TRIAL)
    assert s["action"] == "reconcile"
    later = fx.decision("policy", {"enabled": True, "revision": "v1"}, decision_id="p-3")
    tampered = subject.record_decision(root, fx.TRIAL, later, expected_revision=s["revision"])
    assert (tampered["reason"], tampered["action"]) == (
        "source_conflict",
        "resolve_source_conflict",
    )


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        ("absent", ("no_trial", "none")),
        ("deleted_after_commit", ("source_conflict", "resolve_source_conflict")),
        ("pending_stash", ("lifecycle_pending", "resolve_pending_lifecycle")),
    ],
)
def test_s2_trial_less_rejection_keeps_the_readers_classification(
    tmp_path: Path, state: str, expected: tuple[str, str]
) -> None:
    """Only a trial that is really absent is `no_trial`; a missing committed trial or a
    pending trial stash is a problem to resolve, not "nothing to do" (ADR-005).

    `absent` already passes before the fix; it is the control that fails an over-correction
    reporting every trial-less state as a conflict. Its RED siblings are the other two cases."""
    subject = api()
    root = fx.build(tmp_path / "repo")
    trial_id = fx.TRIAL
    if state == "absent":
        trial_id = "never-activated"
    elif state == "deleted_after_commit":
        fx.path(root).unlink()
    else:
        fx.path(root).write_text(fx.path(root).read_text() + "\nHistorical trial WIP\n")
        fx.git(root, "stash", "push", "-m", "harness pending trial", "--", str(fx.path(root)))
    s = subject.status(root, trial_id)
    assert (s["reason"], s["action"]) == expected
    policy = fx.decision("policy", {"enabled": True, "revision": "v1"})
    rejected = subject.record_decision(root, trial_id, policy, expected_revision=s["revision"])
    assert (rejected["reason"], rejected["action"], rejected["changed"]) == (*expected, False)


def test_s1_two_acknowledged_extensions_arrive_in_separate_reconcile_calls(
    tmp_path: Path,
) -> None:
    subject = api()
    root = ready(tmp_path / "repo", ("a",))
    assert subject.reconcile(root, fx.TRIAL)["cohort"] == ["a"]
    fx.task(root, "b", fx.T2, ack=True)
    assert subject.reconcile(root, fx.TRIAL)["cohort"] == ["a", "b"]
    fx.task(root, "c", fx.T3, ack=True)
    assert subject.reconcile(root, fx.TRIAL)["cohort"] == ["a", "b", "c"]


def test_s3_registered_task_artifact_without_start_blocks_enrollment(tmp_path: Path) -> None:
    subject = api()
    root = fx.build(tmp_path / "repo")
    wt = root / ".worktrees" / "b"
    wt.parent.mkdir()
    fx.git(root, "worktree", "add", "-qb", "hm/b", str(wt))
    fx.write_doc(wt / "work-docs" / "RESEARCH-b.md", {"type": "research", "task_slug": "b"})
    fx.task(root, "a", fx.T1, ack=True)
    assert subject.status(root, fx.TRIAL)["reason"] == "source_incomplete"
    assert subject.reconcile(root, fx.TRIAL)["cohort"] == []


def test_s3_later_typed_ack_cannot_cover_earlier_ledger_start(tmp_path: Path) -> None:
    subject = api()
    root = fx.build(tmp_path / "repo")
    fx.task(root, "a", fx.T2, ack=True)
    ledger = root / ".claude/observability/stage-spans.jsonl"
    event = json.loads(ledger.read_text().splitlines()[0])
    event["ts"] = fx.T1
    ledger.write_text(json.dumps(event) + "\n")
    assert subject.status(root, fx.TRIAL)["reason"] == "source_review_required"
    assert subject.reconcile(root, fx.TRIAL)["cohort"] == []


def test_s1_reviewed_members_survive_later_artifact_edit_until_new_ack(tmp_path: Path) -> None:
    subject = api()
    root = ready(tmp_path / "repo", ("a", "b"))
    assert subject.reconcile(root, fx.TRIAL)["cohort"] == ["a", "b"]
    artifact = root / "work-docs/PLAN-b.md"
    artifact.write_text(artifact.read_text() + "\n## Later stage note\n")
    before = fx.path(root).read_bytes()
    report = subject.reconcile(root, fx.TRIAL)
    assert report["reason"] == "pending"
    assert report["recovery"]["state"] == "complete"
    assert report["changed"] is False
    assert fx.path(root).read_bytes() == before
    fx.task(root, "c", fx.T3, ack=True)
    assert subject.reconcile(root, fx.TRIAL)["reason"] == "source_conflict"
    assert subject.status(root, fx.TRIAL)["cohort"] == ["a", "b"]


def test_s1_slugless_stage_start_does_not_block_attributed_task(tmp_path: Path) -> None:
    subject = api()
    root = fx.build(tmp_path / "repo")
    fx.task(root)
    ledger = root / ".claude/observability/stage-spans.jsonl"
    with ledger.open("a") as handle:
        handle.write(json.dumps({"event": "start", "task_slug": None, "ts": fx.T2}) + "\n")
    assert fx.cover(root)["changed"] is True
    result = subject.reconcile(root, fx.TRIAL)
    assert result["cohort"] == ["a"]
    assert result["reason"] != "source_incomplete"


@pytest.mark.parametrize("field", ["decisions", "members"])
def test_s3_malformed_trial_entries_fail_closed_without_traceback(
    tmp_path: Path, field: str
) -> None:
    subject = api()
    root = fx.build(tmp_path / "repo")
    meta = fx.read(root)
    meta["trial"][field] = [None]
    fx.write_doc(fx.path(root), meta)
    assert f"work-docs/PLAN-{fx.TRIAL}.md" in subject.protected_trial_paths(root)
    assert subject.status(root, fx.TRIAL)["reason"] == "source_incomplete"
    result = subject.record_decision(root, fx.TRIAL, {"kind": "invalid"}, expected_revision="stale")
    assert result["reason"] == "source_incomplete"
    assert result["changed"] is False


def test_s3_source_review_without_payload_is_incomplete_not_exception(tmp_path: Path) -> None:
    subject = api()
    root = fx.build(tmp_path / "repo")
    meta = fx.read(root)
    meta["trial"]["decisions"] = [{"kind": "source_review"}]
    fx.write_doc(fx.path(root), meta)
    before = fx.path(root).read_bytes()
    assert f"work-docs/PLAN-{fx.TRIAL}.md" in subject.protected_trial_paths(root)
    assert subject.status(root, fx.TRIAL)["reason"] == "source_incomplete"
    assert subject.reconcile(root, fx.TRIAL)["reason"] == "source_incomplete"
    assert fx.path(root).read_bytes() == before


def test_s3_malformed_legacy_snapshot_is_incomplete_not_exception(tmp_path: Path) -> None:
    subject = api()
    root = fx.build(tmp_path / "repo", legacy=True)
    observed = subject.status(root, fx.TRIAL)
    subject.record_decision(
        root,
        fx.TRIAL,
        fx.decision("policy", {"enabled": True, "revision": "v1"}),
        expected_revision=observed["revision"],
    )
    meta = fx.read(root)
    meta["trial"]["legacy_snapshot"]["members"] = 7
    path = fx.path(root)
    fx.write_doc(path, meta, path.read_text().split("---", 2)[2])
    before = path.read_bytes()
    status = subject.status(root, fx.TRIAL)
    assert status["reason"] == "source_incomplete"
    assert f"PLAN-{fx.TRIAL}.md" in status["source"]
    assert "legacy_snapshot" in status["source"]
    assert subject.reconcile(root, fx.TRIAL)["reason"] == "source_incomplete"
    assert path.read_bytes() == before


def test_s3_malformed_trial_policy_stays_protected(tmp_path: Path) -> None:
    subject = api()
    root = fx.build(tmp_path / "repo")
    meta = fx.read(root)
    meta["trial"]["policy"] = "broken"
    fx.write_doc(fx.path(root), meta)
    assert f"work-docs/PLAN-{fx.TRIAL}.md" in subject.protected_trial_paths(root)
    assert subject.status(root, fx.TRIAL)["reason"] == "source_incomplete"
    assert subject.reconcile(root, fx.TRIAL)["reason"] == "source_incomplete"


def test_s3_committed_active_trial_stays_protected_after_parseable_marker_removal(
    tmp_path: Path,
) -> None:
    subject = api()
    root = fx.build(tmp_path / "repo")
    # HEAD is an active typed trial; the working copy remains valid YAML but
    # omits both the typed marker and the legacy activation line.
    fx.write_doc(
        fx.path(root),
        {"type": "plan", "task_slug": fx.TRIAL},
        "## Evidence\nA later working-copy edit.\n",
    )
    assert f"work-docs/PLAN-{fx.TRIAL}.md" in subject.protected_trial_paths(root)


def test_s3_malformed_trial_key_with_space_stays_protected(tmp_path: Path) -> None:
    subject = api()
    root = fx.build(tmp_path / "repo")
    fx.write_doc(fx.path(root), {"type": "plan", "task_slug": fx.TRIAL})
    fx.git(root, "add", f"work-docs/PLAN-{fx.TRIAL}.md")
    fx.git(root, "commit", "-qm", "ordinary PLAN baseline")
    fx.path(root).write_text(
        "---\ntype: plan\ntask_slug: field-trial\ntrial :\n  schema_version: [\n---\n## Evidence\n"
    )
    assert f"work-docs/PLAN-{fx.TRIAL}.md" in subject.protected_trial_paths(root)


def test_s3_failure_assessment_remains_failed_after_later_pass(tmp_path: Path) -> None:
    subject = api()
    root = ready(tmp_path / "repo", ("a", "b", "c"), terminal=True)
    subject.reconcile(root, fx.TRIAL)
    assess(root, "a", "fail")
    before = subject.status(root, fx.TRIAL)
    later = fx.decision("assessment", {"task": "a", "verdict": "pass"}, decision_id="later-pass")
    result = subject.record_decision(root, fx.TRIAL, later, expected_revision=before["revision"])
    assert result["outcome"] == "failed"
    assert subject.status(root, fx.TRIAL)["outcome"] == "failed"


def test_s4_migrated_trial_displays_current_state_and_preserves_history(tmp_path: Path) -> None:
    subject = api()
    root = fx.build(tmp_path / "repo", legacy=True)
    original = fx.path(root).read_text().split("---", 2)[2]
    current = subject.status(root, fx.TRIAL)
    policy = fx.decision("policy", {"enabled": True, "revision": "v1"})
    subject.record_decision(root, fx.TRIAL, policy, expected_revision=current["revision"])
    fx.task(root, "a")
    fx.cover(root)
    assert subject.reconcile(root, fx.TRIAL)["cohort"] == ["a"]
    body = fx.path(root).read_text().split("---", 2)[2]
    assert "Enrolled: 1/3" in body.split("Preserved trial history", 1)[0]
    assert original in body
    assert subject.status(root, fx.TRIAL)["reason"] != "source_conflict"


def test_s1_canonical_spec_artifact_is_discovered(tmp_path: Path) -> None:
    subject = api()
    root = fx.build(tmp_path / "repo")
    fx.task(root, artifact="SPEC")
    canonical = root / "specs/SPEC-a.md"
    canonical.parent.mkdir()
    (root / "work-docs/SPEC-a.md").rename(canonical)
    fx.cover(root)
    assert subject.reconcile(root, fx.TRIAL)["cohort"] == ["a"]
    assert fx.read(root)["trial"]["members"][0]["source_refs"] == ["base:specs/SPEC-a.md"]


def test_s3_observation_without_attributable_start_is_incomplete(tmp_path: Path) -> None:
    subject = api()
    root = fx.build(tmp_path / "repo")
    fx.write_doc(
        root / "work-docs/PLAN-a.md",
        {
            "type": "plan",
            "task_slug": "a",
            "trial_feedback": [
                {
                    "id": "a-observation",
                    "trial_id": fx.TRIAL,
                    "task_slug": "a",
                    "kind": "observation",
                    "at": fx.T1,
                    "evidence_refs": ["conversation:observed"],
                }
            ],
        },
    )
    report = subject.status(root, fx.TRIAL)
    assert report["reason"] == "source_incomplete"
    assert "PLAN-a.md" in str(report["source"])
    assert subject.reconcile(root, fx.TRIAL)["cohort"] == []


def test_s3_start_ack_without_timestamp_is_incomplete(tmp_path: Path) -> None:
    subject = api()
    root = fx.build(tmp_path / "repo")
    fx.write_doc(
        root / "work-docs/PLAN-a.md",
        {
            "type": "plan",
            "task_slug": "a",
            "trial_feedback": [
                {
                    "id": "a-start",
                    "trial_id": fx.TRIAL,
                    "task_slug": "a",
                    "kind": "start",
                }
            ],
        },
    )
    report = subject.status(root, fx.TRIAL)
    assert report["reason"] == "source_incomplete"
    assert "invalid start" in str(report["source"])
    assert "PLAN-a.md" in str(report["source"])
    assert " for a" in str(report["source"])


def test_s3_symlinked_trial_plan_is_not_read_or_published(tmp_path: Path) -> None:
    subject = api()
    root = fx.build(tmp_path / "repo")
    external = tmp_path / "external-trial.md"
    fx.path(root).rename(external)
    fx.path(root).symlink_to(external)
    original = external.read_bytes()
    assert subject.status(root, fx.TRIAL)["reason"] == "source_incomplete"
    assert f"work-docs/PLAN-{fx.TRIAL}.md" in subject.protected_trial_paths(root)
    assert subject.reconcile(root, fx.TRIAL)["reason"] == "source_incomplete"
    with pytest.raises(ValueError, match="escapes repository"):
        subject.verified_trial_landing_paths(root)
    assert external.read_bytes() == original


def test_s2_first_publication_does_not_certify_preexisting_manual_dirt(tmp_path: Path) -> None:
    subject = api()
    root = fx.build(tmp_path / "repo")
    fx.path(root).write_text(fx.path(root).read_text() + "\nManual unrelated note.\n")
    fx.task(root)
    assert fx.cover(root)["changed"] is True
    assert subject.reconcile(root, fx.TRIAL)["cohort"] == ["a"]
    with pytest.raises(ValueError, match="trial HEAD changed"):
        subject.verified_trial_landing_paths(root)
    assert "Manual unrelated note." in fx.path(root).read_text()


def test_s3_equal_starts_require_matching_explicit_review_order(tmp_path: Path) -> None:
    subject = api()
    root = fx.build(tmp_path / "repo")
    fx.task(root, "a", fx.T1)
    fx.task(root, "b", fx.T1)
    assert subject.status(root, fx.TRIAL)["reason"] == "order_conflict"
    pending = subject.status(root, fx.TRIAL)
    review = fx.decision(
        "source_review",
        {
            "inventory": pending["inventory"],
            "through": pending["cutoff"],
            "disposition": "accepted",
            "ordered_tasks": ["b", "a"],
            "excluded_tasks": [],
        },
    )
    subject.record_decision(root, fx.TRIAL, review, expected_revision=pending["revision"])
    assert subject.status(root, fx.TRIAL)["candidates"] == ["b", "a"]
    assert subject.reconcile(root, fx.TRIAL)["cohort"] == ["b", "a"]


def test_s3_no_authority_stale_revision_and_revocation(tmp_path: Path) -> None:
    subject = api()
    root = ready(tmp_path / "repo")
    s = subject.status(root, fx.TRIAL)
    d = fx.decision("policy", {"enabled": False, "revision": "v2"})
    before = snapshot(root)
    no_answer = dict(d, authority="")
    assert (
        subject.record_decision(root, fx.TRIAL, no_answer, expected_revision=s["revision"])[
            "reason"
        ]
        == "authority_required"
    )
    assert (
        subject.record_decision(root, fx.TRIAL, d, expected_revision="stale")["reason"]
        == "revision_conflict"
    )
    assert snapshot(root) == before
    assert subject.record_decision(root, fx.TRIAL, d, expected_revision=s["revision"])["changed"]
    before = snapshot(root)
    assert subject.reconcile(root, fx.TRIAL)["reason"] == "authority_required"
    assert snapshot(root) == before


def test_s3_outcome_precedence_and_metrics_preserved(tmp_path: Path) -> None:
    subject = api()
    root = ready(tmp_path / "repo", ("a", "b", "c"), terminal=True)
    metric = root / ".claude/intent/metrics.yaml"
    metric.parent.mkdir(parents=True, exist_ok=True)
    metric.write_text("values: []\n")
    subject.reconcile(root, fx.TRIAL)
    assert subject.status(root, fx.TRIAL)["outcome"] == "pending"
    for slug in ("a", "b", "c"):
        assess(root, slug, "pass")
    assert subject.status(root, fx.TRIAL)["outcome"] == "passed"
    assert subject.status(root, fx.TRIAL)["collection"] == "complete"
    assert metric.read_text() == "values: []\n"


def test_s3_missing_terminal_trace_cannot_be_passed(tmp_path: Path) -> None:
    subject = api()
    root = ready(tmp_path / "repo", terminal=True, evidence=False)
    subject.reconcile(root, fx.TRIAL)
    assess(root, "a", "pass")
    assert subject.status(root, fx.TRIAL)["outcome"] == "insufficient_evidence"


def test_s4_recovery_remains_discoverable_until_apply_readback(tmp_path: Path) -> None:
    subject = api()
    root = fx.build(tmp_path / "repo", legacy=True)
    fx.task(root)
    initial = subject.status(root, fx.TRIAL)
    d = fx.decision("policy", {"enabled": True, "revision": "v1"})
    subject.record_decision(root, fx.TRIAL, d, expected_revision=initial["revision"])
    result = subject.reconcile(root, fx.TRIAL)
    assert result["recovery"]["state"] == "blocked"
    assert fx.read(root)["trial"]["recovery"]["next_trigger"] == "next_eligible_invocation"
    fx.cover(root)
    assert subject.reconcile(root, fx.TRIAL)["cohort"] == ["a"]
    readback = subject.status(root, fx.TRIAL)
    assert readback["recovery"]["state"] == "complete"
    assert readback["outcome"] == "pending"


def test_s1_no_active_trial_is_noop(tmp_path: Path) -> None:
    subject = api()
    root = fx.build(tmp_path / "repo")
    fx.path(root).unlink()
    fx.git(root, "add", "-u", f"work-docs/PLAN-{fx.TRIAL}.md")
    fx.git(root, "commit", "-qm", "remove trial before this observation")
    before = snapshot(root)
    assert subject.active_trials(root) == []
    assert subject.status(root, "absent")["reason"] == "no_trial"
    assert snapshot(root) == before


@pytest.mark.parametrize(
    ("committed_trial", "expected"),
    [
        (True, ("source_conflict", "resolve_source_conflict")),
        (False, ("no_trial", "none")),
    ],
)
def test_s3_de_marked_committed_trial_is_not_absent(
    tmp_path: Path, committed_trial: bool, expected: tuple[str, str]
) -> None:
    """Removing the trial block from a committed active trial is not the end of the trial:
    like a deleted file it is a conflict to resolve. A PLAN that never carried a trial is the
    control that stays `no_trial`."""
    subject = api()
    root = fx.build(tmp_path / "repo")
    doc = fx.path(root)
    if not committed_trial:
        fx.write_doc(doc, {"type": "plan", "task_slug": fx.TRIAL}, "# Plain plan\n")
        fx.git(root, "commit", "-qam", "no trial in this PLAN")
    fx.write_doc(doc, {"type": "plan", "task_slug": fx.TRIAL}, "# Plain plan\n\nNo trial prose.\n")
    before = doc.read_bytes()
    s = subject.status(root, fx.TRIAL)
    assert (s["reason"], s["action"]) == expected
    policy = fx.decision("policy", {"enabled": True, "revision": "v1"})
    refused = subject.record_decision(root, fx.TRIAL, policy, expected_revision=s["revision"])
    assert (refused["reason"], refused["action"], refused["changed"]) == (*expected, False)
    assert doc.read_bytes() == before


def test_s3_trial_less_plan_before_the_first_commit_is_absent(tmp_path: Path) -> None:
    """The committed-marker check must treat "no commit yet" as no committed trial, not as a
    git failure that turns an ordinary PLAN into `source_incomplete`."""
    subject = api()
    root = tmp_path / "repo"
    root.mkdir()
    fx.git(root, "init", "-q")
    fx.write_doc(fx.path(root), {"type": "plan", "task_slug": fx.TRIAL}, "# Plain plan\n")
    s = subject.status(root, fx.TRIAL)
    assert (s["reason"], s["action"]) == ("no_trial", "none")


@pytest.mark.parametrize(
    ("why", "action"),
    [("lock_busy", "retry_next_invocation"), ("unsupported_lock", "retry_on_supported_storage")],
)
def test_s2_status_lock_failure_reports_without_an_unfenced_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, why: str, action: str
) -> None:
    """ADR-006: status reads only under the trial fence, so a status that cannot take it
    must not fall back to reading the sources anyway."""
    from contextlib import contextmanager

    subject = api()
    root = fx.build(tmp_path / "repo")
    fx.task(root, "a", fx.T1, ack=True)
    reads: list[str] = []
    real_read = subject._read

    def counted(*args: Any, **kwargs: Any) -> Any:
        reads.append("read")
        return real_read(*args, **kwargs)

    @contextmanager
    def refused(_base: Path) -> Any:
        raise OSError(why)
        yield

    monkeypatch.setattr(subject, "_read", counted)
    monkeypatch.setattr(subject, "_writer", refused)
    s = subject.status(root, fx.TRIAL)
    assert (s["reason"], s["action"]) == (why, action)
    assert reads == []


@pytest.mark.parametrize("operation", ["record_decision", "reconcile"])
def test_s2_edit_between_read_and_publish_is_not_overwritten(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, operation: str
) -> None:
    """SPEC: never an update based on stale contents. The fence serializes supported writers
    only, so an editor that saves between the read and the publish must win a conflict, not
    be silently replaced."""
    subject = api()
    root = ready(tmp_path / "repo", ("a",))
    doc = fx.path(root)
    real_render = subject._render_body

    def edit_then_render(*args: Any, **kwargs: Any) -> Any:
        doc.write_text(doc.read_text() + "\nSaved by an editor mid-write.\n")
        return real_render(*args, **kwargs)

    monkeypatch.setattr(subject, "_render_body", edit_then_render)
    if operation == "reconcile":
        result = subject.reconcile(root, fx.TRIAL)
    else:
        s = subject.status(root, fx.TRIAL)
        policy = fx.decision("policy", {"enabled": True, "revision": "v2"}, decision_id="p-2")
        result = subject.record_decision(root, fx.TRIAL, policy, expected_revision=s["revision"])
    assert (result["reason"], result["changed"]) == ("source_conflict", False)
    assert "Saved by an editor mid-write." in doc.read_text()


def test_s3_deleted_committed_active_trial_remains_protected(tmp_path: Path) -> None:
    subject = api()
    root = fx.build(tmp_path / "repo")
    committed = fx.git(root, "show", f"HEAD:work-docs/PLAN-{fx.TRIAL}.md")
    fx.path(root).unlink()
    assert f"work-docs/PLAN-{fx.TRIAL}.md" in subject.protected_trial_paths(root)
    assert subject.status(root, fx.TRIAL)["reason"] == "source_conflict"
    assert subject.reconcile(root, fx.TRIAL)["reason"] == "source_conflict"
    assert not fx.path(root).exists()
    assert fx.git(root, "show", f"HEAD:work-docs/PLAN-{fx.TRIAL}.md") == committed


@pytest.mark.parametrize("bad", ["../outside", "/tmp/outside", "a/b", "..", ""])
def test_s3_trial_id_cannot_escape_repository(tmp_path: Path, bad: str) -> None:
    subject = api()
    with pytest.raises(ValueError, match="trial"):
        subject.status(tmp_path, bad)


def test_s1_cli_status_and_decision_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    api()
    from harness_maker.intent_cli import main

    root = fx.build(tmp_path / "repo", legacy=True)
    assert main(["--root", str(root), "trial", "status", fx.TRIAL, "--json"]) == 0
    s = json.loads(capsys.readouterr().out)
    dpath = tmp_path / "decision.json"
    dpath.write_text(json.dumps(fx.decision("policy", {"enabled": True, "revision": "v1"})))
    assert (
        main(
            [
                "--root",
                str(root),
                "trial",
                "record-decision",
                fx.TRIAL,
                "--file",
                str(dpath),
                "--expected-revision",
                s["revision"],
                "--json",
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["changed"] is True


def test_s1_cli_reconcile_dry_run_writes_nothing_and_apply_commits(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    api()
    from harness_maker.intent_cli import main

    root = ready(tmp_path / "repo", ("a",))
    before = fx.path(root).read_bytes()
    argv = ["--root", str(root), "trial", "reconcile", fx.TRIAL, "--json"]
    assert main([*argv, "--dry-run"]) == 0
    assert json.loads(capsys.readouterr().out)["reason"] == "awaiting_reconciliation"
    assert fx.path(root).read_bytes() == before
    assert main(argv) == 0
    assert json.loads(capsys.readouterr().out)["cohort"] == ["a"]
    assert [m["task"] for m in fx.read(root)["trial"]["members"]] == ["a"]


def test_s2_cli_rejected_decision_exits_nonzero_without_writing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    api()
    from harness_maker.intent_cli import main

    root = fx.build(tmp_path / "repo", legacy=True)
    before = fx.path(root).read_bytes()
    dpath = tmp_path / "decision.json"
    dpath.write_text(json.dumps(fx.decision("policy", {"enabled": True, "revision": "v1"})))
    argv = ["--root", str(root), "trial", "record-decision", fx.TRIAL, "--file", str(dpath)]
    assert main([*argv, "--expected-revision", "0" * 64, "--json"]) == 1
    out = json.loads(capsys.readouterr().out)
    assert (out["reason"], out["changed"]) == ("revision_conflict", False)
    assert fx.path(root).read_bytes() == before


def golden_observation(
    root: Path, inp: dict[str, Any], monkeypatch: pytest.MonkeyPatch, ac: str
) -> dict[str, Any]:
    """Materialize SPEC inputs in files, invoke public operations, project observables.

    Only input facts drive fixture construction. No expected field is used here.
    Boolean observables describe persisted files/actions rather than writer claims.
    """
    subject = api()
    legacy = (
        inp.get("policy") == "legacy"
        or inp.get("current_policy") == "legacy_collector"
        or inp.get("reason") == "policy_revision_required"
    )
    fx.build(root, legacy=legacy)
    from tests.unit import world_fixture as wf
    from tests.unit.test_intent_vocabulary import _canonical

    wf.build_root(root, git=False, intent=_canonical())
    intent_record = wf.approved(wf.objective("OBJ-1", outcome_id="latency", state="active"), 10)
    intent_record["metric_id"] = intent_record.pop("outcome_id")
    intent_path = root / "intent/OBJ-1.md"
    intent_path.parent.mkdir(exist_ok=True)
    wf.dump_intent(intent_path, intent_record)
    metric_path = root / ".claude/intent/metrics.yaml"
    wf.dump(
        metric_path,
        {
            "schema_version": 1,
            "values": [{"metric_id": "latency", "value": 9, "observed_at": fx.T1}],
        },
    )
    protected = {
        p: p.read_bytes() for p in [intent_path, root / ".claude/intent.yaml", metric_path]
    }
    if inp.get("active") is False:
        fx.path(root).unlink()
        fx.git(root, "add", "-u", f"work-docs/PLAN-{fx.TRIAL}.md")
        fx.git(root, "commit", "-qm", "absent trial fixture")
        before = snapshot(root)
        s = subject.reconcile(root, fx.TRIAL)
        return dict(s, writes=int(snapshot(root) != before), questions=len(s["questions"]))
    raw = inp.get("raw_sources")
    if raw:
        names = [x["task"] for x in raw["starts"]]
        data = fx.read(root)
        data["trial"]["activation"] = raw["interval"]["from"]
        fx.write_doc(fx.path(root), data)
    elif "member_count" in inp or inp.get("terminal_count") == 3:
        names = ["a", "b", "c"]
    else:
        names = inp.get("starts", inp.get("start_order", ["a"]))
    terminal = bool(
        inp.get("terminal_count")
        or inp.get("terminal_member_missing_evidence")
        or inp.get("reason") == "awaiting_user_assessment"
    )
    for n, slug in enumerate(names, 1):
        ts = raw["starts"][n - 1]["at"] if raw else f"2026-09-22T0{n}:00:00Z"
        fx.task(
            root,
            slug,
            ts,
            terminal=terminal,
            evidence=not (
                inp.get("terminal_member_missing_evidence") or (inp.get("earlier") and slug == "a")
            ),
            artifact=inp.get("artifact", "PLAN"),
        )
    incomplete = (
        inp.get("sources") == "missing"
        or inp.get("registered_source") == "unreadable"
        or inp.get("reason") == "source_incomplete"
    )
    review_required = (raw is not None and not inp.get("source_review")) or inp.get(
        "reason"
    ) == "source_review_required"
    # Registered Git sources are real directories; unreadable means the registered
    # path has disappeared, independent of filesystem mode/root privileges.
    source_wt = None
    if incomplete or inp.get("base_and_worktree") == "divergent":
        source_wt = root / ".worktrees/evidence"
        source_wt.parent.mkdir(exist_ok=True)
        fx.git(root, "worktree", "add", "-qb", "hm/evidence", str(source_wt))
        if incomplete:
            source_wt.rename(root / ".worktrees/unavailable")
        else:
            fx.task(source_wt, "a", fx.T1)
            doc = source_wt / "work-docs/PLAN-a.md"
            data = yaml.safe_load(doc.read_text().split("---", 2)[1])
            data["trial_feedback"][0]["decision"] = "Conflicting observation from copied artifact"
            fx.write_doc(doc, data)
    if not legacy and not incomplete and not review_required and source_wt is None:
        state = subject.status(root, fx.TRIAL)
        # Inventory is an opaque captured input. Population, order and boundary
        # come from the independent fixture, never from subject candidates/cutoff.
        review = inp.get("source_review") or {}
        d = fx.decision(
            "source_review",
            {
                "inventory": state["inventory"],
                "through": review.get("through", fx.T3),
                "disposition": review.get("disposition", "accepted"),
                "ordered_tasks": review.get("ordered_tasks", list(names)),
                "excluded_tasks": review.get("excluded_tasks", []),
            },
        )
        subject.record_decision(root, fx.TRIAL, d, expected_revision=state["revision"])
        if raw and raw["inventory"] != review.get("inventory"):
            # L1 -> L2 changes a source payload without changing task chronology.
            ledger = root / ".claude/observability/stage-spans.jsonl"
            with ledger.open("a") as handle:
                handle.write(
                    json.dumps(
                        {
                            "event": "end",
                            "task_slug": "a",
                            "ts": raw["interval"]["through"],
                            "stage": "hm:research",
                            "result": "aborted",
                        }
                    )
                    + "\n"
                )
    late = inp.get("late_start") or inp.get("reason") == "order_conflict"
    if late:
        # Establish the b-only committed snapshot before exposing earlier a.
        ledger = root / ".claude/observability/stage-spans.jsonl"
        ledger.write_text("")
        for p in (root / "work-docs").glob("PLAN-?.md"):
            p.unlink()
        fx.task(root, "b", fx.T2)
        data = fx.read(root)
        data["trial"]["decisions"] = []
        # This is a newly seeded snapshot, not a runtime mutation of the
        # earlier published document. Discard its old publication receipt.
        data["trial"].pop("publication", None)
        fx.write_doc(fx.path(root), data)
        fx.cover(root)
        subject.reconcile(root, fx.TRIAL)
        fx.task(root, "a", fx.T1)
    if "start_times" in inp:
        fx.task(root, "b", fx.T1)
    if inp.get("earlier"):
        fx.task(root, "b", fx.T2, terminal=True)
    if inp.get("task_result"):
        doc = root / "work-docs/PLAN-a.md"
        data = yaml.safe_load(doc.read_text().split("---", 2)[1])
        data["trial_feedback"].append(
            {
                "id": "a-abort",
                "trial_id": fx.TRIAL,
                "task_slug": "a",
                "kind": "terminal",
                "at": fx.T3,
                "result": "aborted",
                "evidence_refs": ["conversation:abort-a"],
            }
        )
        fx.write_doc(doc, data)
        state = subject.status(root, fx.TRIAL)
        subject.record_decision(
            root,
            fx.TRIAL,
            fx.decision(
                "source_review",
                {
                    "inventory": state["inventory"],
                    "through": fx.T3,
                    "disposition": "accepted",
                    "ordered_tasks": names,
                    "excluded_tasks": [],
                },
                decision_id="review-abort",
            ),
            expected_revision=state["revision"],
        )
    if inp.get("authority") == "revoked":
        s = subject.status(root, fx.TRIAL)
        subject.record_decision(
            root,
            fx.TRIAL,
            fx.decision("policy", {"enabled": False, "revision": "v2"}),
            expected_revision=s["revision"],
        )
    if terminal and not legacy and not incomplete:
        subject.reconcile(root, fx.TRIAL)
    if inp.get("user_failure") or inp.get("user_assessments"):
        subject.reconcile(root, fx.TRIAL)
        for slug, verdict in zip(names, inp.get("user_assessments", ["fail"]), strict=False):
            assess(root, slug, verdict)
    if inp.get("reason") == "awaiting_user_assessment":
        subject.reconcile(root, fx.TRIAL)
    if inp.get("reason") == "observation_window_open":
        p = root / "work-docs/PLAN-a.md"
        data = yaml.safe_load(p.read_text().split("---", 2)[1])
        data["trial_feedback"].append(
            {
                "id": "window",
                "trial_id": fx.TRIAL,
                "task_slug": "a",
                "kind": "deferred",
                "at": fx.T1,
                "until": inp["closing_date"],
            }
        )
        fx.write_doc(p, data)
    if inp.get("stage_handoff"):
        ledger = root / ".claude/observability/stage-spans.jsonl"
        with ledger.open("a") as handle:
            handle.write(
                json.dumps(
                    {
                        "event": "end",
                        "stage": "hm:research",
                        "task_slug": "a",
                        "ts": fx.T2,
                        "result": "success",
                    }
                )
                + "\n"
            )
    if inp.get("recovery") == "blocked":
        # Durable blocked obligation survives into B after a source review clears it.
        data = fx.read(root)
        data["trial"]["recovery"] = {
            "state": "blocked",
            "reason": "source_review_required",
            "authority": "conversation:approved",
            "next_trigger": "next_eligible_invocation",
        }
        fx.write_doc(fx.path(root), data)
        monkeypatch.setenv("HM_SESSION_ID", inp["next_session"])
    before = snapshot(root)
    before_trial = copy.deepcopy(fx.read(root))
    operation = inp.get("operation", "status")
    if (
        (source_wt is not None and ac == "AC-005")
        or inp.get("earlier")
        or inp.get("start_times")
        or inp.get("source_changed_before_commit")
    ):
        operation = "reconcile"
    raced: list[bool] = []
    if inp.get("source_changed_before_commit"):
        source = root / "work-docs/PLAN-a.md"
        original = Path.read_bytes

        def change_after_capture(path: Path) -> bytes:
            content = original(path)
            if path == source and not raced:
                raced.append(True)
                data = yaml.safe_load(content.split(b"---", 2)[1])
                data["trial_feedback"][0]["decision"] = "Changed after captured source read"
                fx.write_doc(path, data)
            return content

        monkeypatch.setattr(Path, "read_bytes", change_after_capture)
    if operation == "record-decision":
        current = subject.status(root, fx.TRIAL)
        payload = (
            {"enabled": True, "revision": "v1"}
            if inp.get("kind") == "policy_replacement"
            else {"task": "a", "verdict": "fail"}
        )
        kind = "policy" if inp.get("kind") == "policy_replacement" else "assessment"
        if kind == "assessment" and not legacy:
            subject.reconcile(root, fx.TRIAL)
            current = subject.status(root, fx.TRIAL)
        did = inp.get("decision", {}).get("id", "decision-1")
        d = fx.decision(kind, payload, decision_id=did)
        if inp.get("same_id"):
            subject.record_decision(root, fx.TRIAL, d, expected_revision=current["revision"])
            current = subject.status(root, fx.TRIAL)
            if inp["same_id"] == "different_payload":
                d["payload"]["verdict"] = "pass"
        if inp.get("explicit_user_answer") is False:
            d["authority"] = ""
        before = snapshot(root)
        s = subject.record_decision(
            root,
            fx.TRIAL,
            d,
            expected_revision="stale"
            if inp.get("expected_revision_matches") is False
            else current["revision"],
        )
    elif (
        operation in {"reconcile", "mechanical_reconcile", "apply"}
        or inp.get("old_session")
        or inp.get("task_result")
    ):
        s = subject.reconcile(root, fx.TRIAL)
    elif inp.get("recovery") == "blocked" and inp.get("blocker_cleared"):
        s = subject.status(root, fx.TRIAL)
    else:
        s = subject.status(root, fx.TRIAL)
    if inp.get("source_changed_before_commit"):
        assert raced, "The source must be captured through the byte-preserving reader"
        assert s["reason"] == "source_conflict"
        assert fx.read(root)["trial"]["members"] == before_trial["trial"]["members"]
    if source_wt is not None:
        assert str(source_wt) in json.dumps(s), (
            "Identify the unavailable/conflicting registered source"
        )
        assert fx.read(root)["trial"]["members"] == before_trial["trial"]["members"]
    after_trial = fx.read(root)
    result = dict(s)
    result.update(
        writes=int(snapshot(root) != before),
        candidate=s.get("candidates", []),
        questions=len(s.get("questions", [])),
        old_session_ack_required=s.get("reason") == "collector_required",
        additional_user_confirmation=s.get("reason") == "confirmation_required",
        additional_confirmation=s.get("reason") == "confirmation_required",
        terminal=bool(s.get("tasks", {}).get("a", {}).get("terminal")),
        invented_assessments=len(after_trial.get("trial", {}).get("decisions", []))
        - len(before_trial.get("trial", {}).get("decisions", []))
        if operation != "record-decision"
        else 0,
        assessment_mutation=after_trial.get("trial", {}).get("decisions")
        != before_trial.get("trial", {}).get("decisions"),
        intent_mutation=any(
            p.read_bytes() != content for p, content in protected.items() if p != metric_path
        ),
        metric_mutation=metric_path.read_bytes() != protected[metric_path],
        activation_mutation=after_trial.get("trial", {}).get("activation")
        != before_trial.get("trial", {}).get("activation"),
        commit=after_trial.get("trial", {}).get("members")
        != before_trial.get("trial", {}).get("members"),
        stale_commit=after_trial.get("trial", {}).get("members")
        != before_trial.get("trial", {}).get("members"),
        prefer_later=bool(s.get("cohort") and s["cohort"][0] == "b"),
        silent_replacement=s.get("cohort") != ["b"] if late else False,
        invented_verdict=s.get("outcome") == "passed",
        invented_coverage=bool(s.get("coverage_accepted")) and review_required,
        independent_work_may_continue=not s.get("halt_independent_work", False),
        immediate_remeasurement=metric_path.read_bytes() != protected[metric_path],
    )
    if operation == "record-decision":
        ds = after_trial.get("trial", {}).get("decisions", [])
        result["persisted_decision"] = next((x["id"] for x in ds if x["id"] == d["id"]), None)
        result["next_session_assessment"] = (
            subject.status(root, fx.TRIAL).get("assessments", {}).get("a")
        )
        result["policy_decision_persisted"] = any(x["kind"] == "policy" for x in ds)
        result["replay"] = not s.get("changed") and s.get("reason") != "decision_conflict"
    return result


_GOLDEN_CASES = [
    (ac, i, row)
    for ac in ("AC-001", "AC-002", "AC-005", "AC-006", "AC-008")
    for i, row in enumerate(rows(ac))
]


@pytest.mark.parametrize(
    ("ac", "index", "row"), _GOLDEN_CASES, ids=[f"{ac}-{i}" for ac, i, _ in _GOLDEN_CASES]
)
def test_machine_golden_tables_are_exercised(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, ac: str, index: int, row: GoldenRow
) -> None:
    result = golden_observation(tmp_path / "repo", row.input, monkeypatch, ac)
    for key, value in row.expected.items():
        assert result.get(key) == value, (ac, index, key, result, value)
