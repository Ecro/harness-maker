"""Phase 4: the delegated wrapup's INPUT contract (ADR-006) and its config gate.

Delegation moves the wrapup body behind a summarisation boundary, so the brief is
the only thing standing between "the agent had what it needed" and a silently
shallower wrapup. Two failure directions matter and they pull opposite ways:

- accept a vacuous brief  → the agent runs on nothing and nobody notices;
- raise on an incomplete brief → a crashed session's recovery wrapup is stranded,
  and ADR-006 makes that path first-class.

So validation must REJECT precisely, and the stage must DEGRADE rather than throw.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import yaml

from harness_maker import wrapup_brief as wb
from harness_maker.interview import answers_from_harness_yaml
from harness_maker.models import DelegationConfig, InterviewAnswers


def _git(args: list[str], cwd: Path) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True, timeout=60
    ).stdout


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(["init", "-b", "main"], repo)
    _git(["config", "user.email", "t@e.com"], repo)
    _git(["config", "user.name", "T"], repo)
    (repo / ".gitignore").write_text(".worktrees/\n", encoding="utf-8")
    (repo / "README.md").write_text("x\n", encoding="utf-8")
    _git(["add", "."], repo)
    _git(["commit", "-m", "init"], repo)
    return repo


def _task_worktree(repo: Path, slug: str) -> Path:
    wt = repo / ".worktrees" / slug
    _git(["worktree", "add", "-b", f"hm/{slug}", str(wt)], repo)
    return wt


def _valid(**overrides: object) -> wb.WrapupBrief:
    fields: dict[str, object] = {
        "schema_version": wb.SCHEMA_VERSION,
        "stage": "wrapup",
        "slug": "my-task",
        "task_branch": "hm/my-task",
        "base_root": "/repo",
        "worktree_root": "/repo/.worktrees/my-task",
        "locale": "en",
        "changed_files": ("src/a.py",),
        "diff_stat": " src/a.py | 2 +-",
        "plan_path": "work-docs/PLAN-my-task.md",
        "review_path": None,
    }
    fields.update(overrides)
    return wb.WrapupBrief.model_validate(fields)


# ------------------------------------------------------------------ positive control


def test_a_fully_derived_brief_validates() -> None:
    """Positive control. Without it every rejection test below is satisfied by a
    validator that returns `ok=False` unconditionally."""
    verdict = wb.validate_brief(_valid())

    assert verdict.ok is True
    assert verdict.missing == ()
    assert verdict.reason == ""


# ------------------------------------------------------------------ per-field rejection


@pytest.mark.parametrize("field", ["slug", "task_branch", "base_root", "worktree_root", "locale"])
def test_an_empty_required_field_is_rejected_and_named(field: str) -> None:
    """The field is named in `missing`, not merely counted: the degraded-path warning
    has to tell the operator WHICH field was underivable or it is unactionable."""
    verdict = wb.validate_brief(_valid(**{field: ""}))

    assert verdict.ok is False
    # EXACTLY this field, not merely containing it: a validator that dumps every
    # field name whenever anything is wrong satisfies a containment check while
    # defeating the stated purpose of telling the operator which one failed.
    assert verdict.missing == (field,)


@pytest.mark.parametrize("field", ["slug", "task_branch", "base_root", "worktree_root", "locale"])
def test_a_whitespace_only_field_is_rejected_and_named(field: str) -> None:
    """`"   "` is truthy in Python. A presence check that only tests truthiness
    accepts it, and the agent receives a brief whose slug is three spaces."""
    verdict = wb.validate_brief(_valid(**{field: "   "}))

    assert verdict.ok is False
    assert field in verdict.missing


def test_a_brief_whose_worktree_is_not_under_the_base_is_rejected() -> None:
    """Wrong-root. `.worktrees/<slug>/` under the base is what makes the two roots
    consistent; a brief pairing an unrelated checkout with this base would send the
    agent's writes into another repo."""
    verdict = wb.validate_brief(_valid(worktree_root="/elsewhere/.worktrees/my-task"))

    assert verdict.ok is False
    assert verdict.missing == ("worktree_root",)
    assert verdict.reason


def test_a_brief_whose_branch_names_a_different_task_is_rejected() -> None:
    """Cross-task-slug. The slug selects PLAN / REVIEW documents and the land target;
    a mismatch means the agent writes one task's memory while landing another's."""
    verdict = wb.validate_brief(_valid(slug="my-task", task_branch="hm/other-task"))

    assert verdict.ok is False
    assert "task_branch" in verdict.missing


def test_a_brief_whose_worktree_directory_names_a_different_task_is_rejected() -> None:
    """The same mismatch through the other spelling: branch and slug agree, but the
    checkout is a different task's worktree."""
    verdict = wb.validate_brief(_valid(worktree_root="/repo/.worktrees/other-task"))

    assert verdict.ok is False
    assert "worktree_root" in verdict.missing


def test_a_brief_for_the_wrong_stage_is_rejected() -> None:
    verdict = wb.validate_brief(_valid(stage="execute"))

    assert verdict.ok is False
    assert "stage" in verdict.missing


def test_every_missing_field_is_reported_at_once() -> None:
    """One round trip: reporting only the first failure makes the operator re-run the
    stage once per defect."""
    verdict = wb.validate_brief(_valid(slug="", locale="  "))

    assert set(verdict.missing) >= {"slug", "locale"}


# ------------------------------------------------------------------ derivation


def test_derivation_inside_a_task_worktree_fills_every_machine_field(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    wt = _task_worktree(repo, "my-task")
    (wt / "src").mkdir()
    (wt / "src" / "a.py").write_text("x = 1\n", encoding="utf-8")

    brief, verdict = wb.derive_brief(wt)

    assert verdict.ok is True, verdict
    assert brief is not None
    assert brief.slug == "my-task"
    assert brief.task_branch == "hm/my-task"
    assert brief.base_root == str(repo.resolve())
    assert brief.worktree_root == str(wt.resolve())
    assert brief.stage == "wrapup"
    assert "src/a.py" in brief.changed_files
    # The diff summary is the agent's only view of change SIZE. An implementation
    # emitting a constant empty string passes every other assertion here.
    assert brief.diff_stat.strip()


def test_derivation_finds_the_plan_and_review_documents_for_the_slug(tmp_path: Path) -> None:
    """These are the two documents the wrapup body reads. Deriving the slug but not
    resolving them hands the agent a brief that looks complete and is not."""
    repo = _repo(tmp_path)
    wt = _task_worktree(repo, "my-task")
    docs = wt / "work-docs"
    docs.mkdir()
    (docs / "PLAN-my-task.md").write_text("plan\n", encoding="utf-8")
    (docs / "REVIEW-my-task.md").write_text("review\n", encoding="utf-8")

    brief, _ = wb.derive_brief(wt)

    assert brief is not None
    assert brief.plan_path == "work-docs/PLAN-my-task.md"
    assert brief.review_path == "work-docs/REVIEW-my-task.md"


def test_an_absent_review_document_is_none_rather_than_a_failure(tmp_path: Path) -> None:
    """A wrapup after a review-less task is normal. Treating the absence as a missing
    field would degrade every such wrapup to inline for no reason."""
    repo = _repo(tmp_path)
    wt = _task_worktree(repo, "my-task")

    brief, verdict = wb.derive_brief(wt)

    assert verdict.ok is True
    assert brief is not None
    assert brief.review_path is None


def test_derivation_outside_a_task_branch_degrades_instead_of_raising(tmp_path: Path) -> None:
    """The standalone / recovered wrapup — ADR-006 calls it first-class. Raising here
    would strand a crashed session's work, which is the exact opposite of what a
    recovery path is for."""
    repo = _repo(tmp_path)

    brief, verdict = wb.derive_brief(repo)

    assert brief is None
    assert verdict.ok is False
    assert "slug" in verdict.missing
    assert verdict.reason


def test_derivation_outside_a_git_repository_degrades_instead_of_raising(
    tmp_path: Path,
) -> None:
    """Cursor and Codex users, CI checkouts, and a `git`-less container all land here."""
    plain = tmp_path / "not-a-repo"
    plain.mkdir()

    brief, verdict = wb.derive_brief(plain)

    assert brief is None
    assert verdict.ok is False
    assert verdict.reason


def test_derivation_reads_the_locale_from_the_base_harness_yaml(tmp_path: Path) -> None:
    """The brief carries locale because the agent's user-facing output must match the
    session's. Defaulting silently to `en` would flip a ko user's wrapup to English
    with no signal."""
    repo = _repo(tmp_path)
    (repo / ".claude").mkdir()
    (repo / ".claude" / "harness.yaml").write_text("locale: ko\n", encoding="utf-8")
    wt = _task_worktree(repo, "my-task")

    brief, _ = wb.derive_brief(wt)

    assert brief is not None
    assert brief.locale == "ko"


def test_an_absent_harness_yaml_falls_back_to_en_without_degrading(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    wt = _task_worktree(repo, "my-task")

    brief, verdict = wb.derive_brief(wt)

    assert verdict.ok is True
    assert brief is not None
    assert brief.locale == "en"


# ------------------------------------------------------------------ config gate


def test_delegation_is_off_by_default() -> None:
    """ADR-011 ships default-empty for one release. A default that delegated would
    make the soak period meaningless."""
    assert DelegationConfig().stages == []
    assert wb.is_delegated("wrapup", DelegationConfig()) is False


def test_a_configured_stage_is_delegated() -> None:
    cfg = DelegationConfig(stages=["wrapup"])

    assert wb.is_delegated("wrapup", cfg) is True
    assert wb.is_delegated("verify", cfg) is False


def test_stage_names_are_normalised_so_casing_and_spacing_do_not_silently_disable() -> None:
    """A hand-edited `- Wrapup ` reads as "on" to the user and as "off" to a naive
    membership test — an opt-in that silently does nothing."""
    cfg = DelegationConfig(stages=[" Wrapup ", "VERIFY"])

    assert wb.is_delegated("wrapup", cfg) is True
    assert wb.is_delegated("verify", cfg) is True


def test_an_unknown_stage_name_is_surfaced_rather_than_silently_ignored() -> None:
    """A typo is the whole risk of a free-string list: `wrapp` is not an error, it is
    an opt-in that never fires. It must be reportable."""
    cfg = DelegationConfig(stages=["wrapp"])

    assert cfg.unknown_stages == ("wrapp",)
    assert wb.is_delegated("wrapup", cfg) is False


def test_a_known_stage_name_is_not_reported_as_unknown() -> None:
    assert DelegationConfig(stages=["wrapup", "verify"]).unknown_stages == ()


def test_the_delegation_key_is_read_back_from_harness_yaml(tmp_path: Path) -> None:
    """Checkpoint 6, READ half. Without the `InterviewAnswers` mirror, `extra='forbid'`
    drops the user's opt-in — but see the WRITE-half test below: this alone is only
    half the loop."""
    path = tmp_path / "harness.yaml"
    path.write_text(
        yaml.safe_dump({"locale": "en", "delegation": {"stages": ["wrapup"]}}),
        encoding="utf-8",
    )

    answers = answers_from_harness_yaml(path)

    assert answers is not None
    assert answers.delegation.stages == ["wrapup"]


def test_the_harness_config_carries_the_delegation_block() -> None:
    """WRITE half, step 1: `synthesize` builds a `HarnessConfig`, and a key absent
    there can never reach the rendered file no matter what the reader accepts."""
    from harness_maker.models import HarnessConfig

    assert HarnessConfig().delegation.stages == []
    assert HarnessConfig(delegation=DelegationConfig(stages=["wrapup"])).delegation.stages == [
        "wrapup"
    ]


@pytest.mark.parametrize("preset", ["Side", "Production"])
def test_a_rendered_harness_yaml_emits_the_delegation_block_for_both_presets(
    tmp_path: Path, preset: str
) -> None:
    """WRITE half, step 2 — and the actual R12 hazard.

    `/harness-maker:make --update` re-renders `harness.yaml` FROM the template. A
    `delegation:` block missing from `harness-yaml/{Side,Production}.yaml.j2` silently
    reverts the user's opt-in on the very next update, while every reader-side test
    above stays green. That is the ADR-011 rollback switch quietly disarming itself.
    """
    from harness_maker.io_utils import load_harness_yaml
    from harness_maker.models import Preset, ProjectProfile, Target
    from harness_maker.render import DEFAULT_FREEZE_TIME, render
    from harness_maker.synthesize import synthesize

    answers = InterviewAnswers(
        preset=Preset(preset),
        targets=[Target.CLAUDE_CODE],
        delegation=DelegationConfig(stages=["wrapup"]),
    )
    render(synthesize(ProjectProfile(), answers), tmp_path, freeze_time=DEFAULT_FREEZE_TIME)

    rendered = tmp_path / "harness.yaml"
    data = load_harness_yaml(rendered)
    assert data["delegation"]["stages"] == ["wrapup"]

    # And the loop closes: what was written reads back unchanged.
    reloaded = answers_from_harness_yaml(rendered)
    assert reloaded is not None
    assert reloaded.delegation.stages == ["wrapup"]


@pytest.mark.parametrize("preset", ["Side", "Production"])
def test_a_rendered_harness_yaml_emits_the_span_cap_keys(tmp_path: Path, preset: str) -> None:
    """The same WRITE-half gap, on the keys Phase 1 added.

    `EconomicsConfig` gained `span_max_turns` / `span_max_min` and
    `answers_from_harness_yaml` reads them, but the `economics:` block in both
    templates listed only the six pre-existing keys — so a user who tuned a cap had
    it reverted to the default on the next `--update`, with the reader-side
    round-trip test green throughout. Found while fixing the identical defect for
    `delegation`.
    """
    from harness_maker.io_utils import load_harness_yaml
    from harness_maker.models import EconomicsConfig, Preset, ProjectProfile, Target
    from harness_maker.render import DEFAULT_FREEZE_TIME, render
    from harness_maker.synthesize import synthesize

    answers = InterviewAnswers(
        preset=Preset(preset),
        targets=[Target.CLAUDE_CODE],
        economics=EconomicsConfig(span_max_turns=123, span_max_min=45.0),
    )
    render(synthesize(ProjectProfile(), answers), tmp_path, freeze_time=DEFAULT_FREEZE_TIME)

    data = load_harness_yaml(tmp_path / "harness.yaml")
    assert data["economics"]["span_max_turns"] == 123
    assert data["economics"]["span_max_min"] == 45.0

    reloaded = answers_from_harness_yaml(tmp_path / "harness.yaml")
    assert reloaded is not None
    assert reloaded.economics.span_max_turns == 123
    assert reloaded.economics.span_max_min == 45.0


def test_an_absent_delegation_key_round_trips_to_the_off_default(tmp_path: Path) -> None:
    """The absent case: every harness rendered before this feature existed. It must
    load, and it must load as OFF."""
    path = tmp_path / "harness.yaml"
    path.write_text(yaml.safe_dump({"locale": "en"}), encoding="utf-8")

    answers = answers_from_harness_yaml(path)

    assert answers is not None
    assert answers.delegation.stages == []


def test_a_malformed_delegation_block_falls_back_to_off_rather_than_poisoning_the_load(
    tmp_path: Path,
) -> None:
    """Tolerant-fallback, matching `delivery_metrics` / `economics`: one bad block must
    not cost the user every other answer in the file."""
    path = tmp_path / "harness.yaml"
    path.write_text(
        yaml.safe_dump({"locale": "ko", "delegation": {"stages": "wrapup"}}),
        encoding="utf-8",
    )

    answers = answers_from_harness_yaml(path)

    assert answers is not None
    assert answers.delegation.stages == []
    assert answers.locale == "ko"  # the rest of the file survived


def test_interview_answers_accepts_the_key_directly() -> None:
    """`extra='forbid'` makes this a real constraint, not a formality."""
    answers = InterviewAnswers(delegation=DelegationConfig(stages=["verify"]))

    assert answers.delegation.stages == ["verify"]
