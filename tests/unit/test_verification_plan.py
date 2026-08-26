"""Tests for the CI-derived verification plan (SPEC-ci-derived-verification-plan).

The anchor test is a DIFFERENTIAL against this repository's own
`.github/workflows/ci.yml`, not a hand-written fixture. A fixture shaped like what
the author assumed CI looks like is precisely what shipped the divergence this
module closes: the stages prescribed `mypy --strict src/`, CI ran
`mypy --strict src tests`, and no test compared the two. Synthetic workflows still
appear below, but only for the branches the real file does not exercise.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
import yaml

from harness_maker.verification_plan import read_plan

REPO_ROOT = Path(__file__).resolve().parents[2]


def _write_workflow(root: Path, name: str, doc: str) -> Path:
    wf = root / ".github" / "workflows"
    wf.mkdir(parents=True, exist_ok=True)
    path = wf / name
    path.write_text(textwrap.dedent(doc), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# AC-001 — differential against the real CI file
# ---------------------------------------------------------------------------


def test_primary_commands_match_this_repos_actual_quality_gate() -> None:
    """The derived plan must equal what ci.yml's quality-gate job really runs.

    Read from the workflow here, not restated — a literal list would be a second
    source of truth that drifts exactly like the stage examples did. If someone
    changes a CI gate's argv, this test follows it and the stages follow too;
    if someone breaks the derivation, the two sides stop agreeing.
    """
    plan = read_plan(REPO_ROOT)
    assert not plan.degraded, plan.reason

    doc = yaml.safe_load((REPO_ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8"))
    quality_gate_runs = [
        step["run"].strip()
        for step in doc["jobs"]["quality-gate"]["steps"]
        if isinstance(step, dict) and isinstance(step.get("run"), str)
    ]

    for cmd in plan.primary_commands():
        assert cmd in quality_gate_runs, (
            f"derived a command the quality-gate job does not run: {cmd!r}\n"
            f"job runs: {quality_gate_runs}"
        )

    # Every gate kind the job actually exercises must be represented. This is the
    # half that catches NARROWING — the failure mode that shipped two red commits.
    for tool in ("ruff check", "ruff format --check", "mypy --strict", "pytest"):
        assert any(tool in cmd for cmd in plan.primary_commands()), (
            f"CI runs {tool!r} but the derived plan omits it: {plan.primary_commands()}"
        )


def test_derived_type_gate_covers_tests_dir_like_ci_does() -> None:
    """The specific narrowing that caused this work: `src/` alone is not CI's type gate."""
    plan = read_plan(REPO_ROOT)
    type_cmds = [c for c in plan.primary_commands() if "mypy" in c]
    assert type_cmds, "no type gate derived"
    assert all("tests" in c for c in type_cmds), (
        f"derived type gate does not cover tests/, which is the exact divergence "
        f"that shipped two red commits: {type_cmds}"
    )


def test_nightly_is_recorded_as_non_gating_not_ignored() -> None:
    """A schedule-only workflow does not gate a push, but must still be named."""
    plan = read_plan(REPO_ROOT)
    assert "nightly.yml" in plan.non_gating
    assert "nightly.yml" not in plan.sources


# ---------------------------------------------------------------------------
# The YAML 1.1 `on:` trap
# ---------------------------------------------------------------------------


def test_on_key_is_the_yaml_boolean_true_after_safe_load() -> None:
    """Documents the trap the next reader will hit, with the parser as the witness."""
    assert yaml.safe_load("on: [push]") == {True: ["push"]}


def test_on_key_parsed_as_yaml_boolean_still_counts_as_a_trigger(tmp_path: Path) -> None:
    """Left unhandled this is not a partial failure — EVERY workflow becomes non-gating.

    The plan then degrades to empty and every caller silently falls back to the guessed
    commands this module exists to replace. Worth its own test because the symptom (an
    empty plan) looks exactly like "this project has no CI".
    """
    _write_workflow(
        tmp_path,
        "ci.yml",
        """
        name: ci
        on:
          push:
            branches: [main]
        jobs:
          gate:
            runs-on: ubuntu-latest
            steps:
              - name: Type
                run: mypy --strict src tests
        """,
    )
    plan = read_plan(tmp_path)
    assert not plan.degraded, plan.reason
    assert plan.primary_commands() == ["mypy --strict src tests"]


# ---------------------------------------------------------------------------
# AC-002 — advisory steps
# ---------------------------------------------------------------------------


def test_continue_on_error_step_is_non_blocking(tmp_path: Path) -> None:
    """An advisory CI step must not become a blocking local gate.

    The reverse of the narrowing error, and just as wrong: it reports third-party
    drift as a failure of the user's own change.
    """
    _write_workflow(
        tmp_path,
        "ci.yml",
        """
        on: [push]
        jobs:
          gate:
            runs-on: ubuntu-latest
            steps:
              - name: Blocking
                run: pytest -q
              - name: Advisory
                continue-on-error: true
                run: pytest -m advisory
        """,
    )
    plan = read_plan(tmp_path)
    by_step = {g.step: g for g in plan.gates}
    assert by_step["Blocking"].blocking is True
    assert by_step["Advisory"].blocking is False
    assert "pytest -m advisory" not in plan.blocking_commands()
    assert "pytest -m advisory" not in plan.primary_commands()


def test_job_level_continue_on_error_applies_to_its_steps(tmp_path: Path) -> None:
    """`continue-on-error` on the JOB makes every step in it advisory."""
    _write_workflow(
        tmp_path,
        "ci.yml",
        """
        on: [push]
        jobs:
          advisory-job:
            runs-on: ubuntu-latest
            continue-on-error: true
            steps:
              - name: Type
                run: mypy --strict src
        """,
    )
    plan = read_plan(tmp_path)
    assert plan.gates[0].blocking is False
    assert plan.blocking_commands() == []


def test_conditional_gate_carries_its_condition(tmp_path: Path) -> None:
    """A gate that only runs on PRs is reported WITH the condition, not as unconditional."""
    _write_workflow(
        tmp_path,
        "ci.yml",
        """
        on: [push, pull_request]
        jobs:
          gate:
            runs-on: ubuntu-latest
            steps:
              - name: PR only
                if: github.event_name == 'pull_request'
                run: pytest -q
        """,
    )
    plan = read_plan(tmp_path)
    assert plan.gates[0].condition == "github.event_name == 'pull_request'"


# ---------------------------------------------------------------------------
# AC-004 — nothing dropped in silence
# ---------------------------------------------------------------------------


def test_unrecognised_commands_are_reported_with_a_reason(tmp_path: Path) -> None:
    """Setup steps are excluded from gates but must be visible, never silently dropped."""
    _write_workflow(
        tmp_path,
        "ci.yml",
        """
        on: [push]
        jobs:
          gate:
            runs-on: ubuntu-latest
            steps:
              - name: Setup
                run: npm install -g @openai/codex
              - name: Test
                run: pytest -q
        """,
    )
    plan = read_plan(tmp_path)
    assert plan.primary_commands() == ["pytest -q"]
    dropped = {u["cmd"]: u for u in plan.unclassified}
    assert "npm install -g @openai/codex" in dropped
    assert dropped["npm install -g @openai/codex"]["reason"]
    assert dropped["npm install -g @openai/codex"]["step"] == "Setup"


def test_environment_heavy_ci_jobs_are_reported_not_run() -> None:
    """CI's extra blocking jobs stay visible in `additional_commands`, out of `primary`.

    Mirroring CI wholesale would import its environment: one of this repo's blocking
    jobs `npm install -g`s an external CLI first. Dropping those silently would be the
    same class of error as the narrowing — so they must land somewhere a reader sees.
    """
    plan = read_plan(REPO_ROOT)
    primary = set(plan.primary_commands())
    additional = plan.additional_commands()
    assert additional, "this repo has blocking CI commands beyond the four primary gates"
    assert not (primary & set(additional)), "a command must not be in both buckets"
    assert primary | set(additional) == set(plan.blocking_commands())


# ---------------------------------------------------------------------------
# Command parsing
# ---------------------------------------------------------------------------


def test_multiline_run_block_yields_each_command(tmp_path: Path) -> None:
    _write_workflow(
        tmp_path,
        "ci.yml",
        """
        on: [push]
        jobs:
          gate:
            runs-on: ubuntu-latest
            steps:
              - name: All
                run: |
                  # a comment that is not a command
                  ruff check .
                  mypy --strict src tests
                  pytest -q
        """,
    )
    plan = read_plan(tmp_path)
    assert plan.primary_commands() == ["ruff check .", "mypy --strict src tests", "pytest -q"]


def test_line_continuation_is_rejoined(tmp_path: Path) -> None:
    """A backslash-continued command is ONE command; splitting it would run half a gate."""
    _write_workflow(
        tmp_path,
        "ci.yml",
        """
        on: [push]
        jobs:
          gate:
            runs-on: ubuntu-latest
            steps:
              - name: Test
                run: |
                  pytest -x \\
                    --tb=short
        """,
    )
    plan = read_plan(tmp_path)
    assert plan.primary_commands() == ["pytest -x --tb=short"]


@pytest.mark.parametrize(
    ("cmd", "expected"),
    [
        ("ruff check .", "lint"),
        ("ruff format --check .", "format"),
        ("uv run ruff format --check .", "format"),
        ("uv run poetry run pytest -q", "test"),
        ("npx eslint .", "lint"),
        ("cargo test", "test"),
        ("cargo build --release", None),
        ("go vet ./...", "test"),
        ("go build ./...", None),
        ("./node_modules/.bin/eslint .", "lint"),
        ("echo hello", None),
        ("", None),
    ],
)
def test_classification(cmd: str, expected: str | None) -> None:
    from harness_maker.verification_plan import _classify

    assert _classify(cmd) == expected


def test_ruff_check_does_not_shadow_ruff_format(tmp_path: Path) -> None:
    """Both ruff gates survive the one-per-kind selection.

    They share a binary, so keying on the head token alone collapses them and the
    format gate vanishes — a narrowing identical in shape to the one being fixed.
    """
    _write_workflow(
        tmp_path,
        "ci.yml",
        """
        on: [push]
        jobs:
          gate:
            runs-on: ubuntu-latest
            steps:
              - name: Lint
                run: ruff check .
              - name: Format
                run: ruff format --check .
        """,
    )
    plan = read_plan(tmp_path)
    assert plan.primary_commands() == ["ruff check .", "ruff format --check ."]


# ---------------------------------------------------------------------------
# AC-003 — degraded paths, each explicit
# ---------------------------------------------------------------------------


def test_no_workflows_directory_is_degraded_with_a_reason(tmp_path: Path) -> None:
    plan = read_plan(tmp_path)
    assert plan.degraded is True
    assert plan.reason
    assert plan.primary_commands() == []


def test_empty_workflows_directory_is_degraded(tmp_path: Path) -> None:
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    plan = read_plan(tmp_path)
    assert plan.degraded is True
    assert plan.reason


def test_malformed_yaml_names_the_file_and_degrades(tmp_path: Path) -> None:
    """Unreadable CI is not "no gates" — the caller must know its fallback is a guess."""
    _write_workflow(tmp_path, "ci.yml", "on: [push]\njobs: [oops\n  - unbalanced")
    plan = read_plan(tmp_path)
    assert plan.degraded is True
    assert "ci.yml" in (plan.reason or "")
    assert plan.primary_commands() == []


def test_gating_workflow_with_no_recognised_tool_is_degraded(tmp_path: Path) -> None:
    """A CI that only deploys yields no gates, and that must not read as "all clear"."""
    _write_workflow(
        tmp_path,
        "ci.yml",
        """
        on: [push]
        jobs:
          deploy:
            runs-on: ubuntu-latest
            steps:
              - name: Ship
                run: ./deploy.sh
        """,
    )
    plan = read_plan(tmp_path)
    assert plan.degraded is True
    assert plan.reason is not None
    assert "ci.yml" in plan.reason
    assert plan.unclassified, "the unrecognised command must still be visible"


def test_schedule_only_workflow_is_non_gating(tmp_path: Path) -> None:
    _write_workflow(
        tmp_path,
        "nightly.yml",
        """
        on:
          schedule:
            - cron: "0 6 * * *"
        jobs:
          gate:
            runs-on: ubuntu-latest
            steps:
              - run: pytest -q
        """,
    )
    plan = read_plan(tmp_path)
    assert plan.non_gating == ["nightly.yml"]
    assert plan.degraded is True  # no gating workflow at all
    assert plan.gates == []


# ---------------------------------------------------------------------------
# The shipped entry point, in its shipped spelling
# ---------------------------------------------------------------------------


def test_cli_commands_prints_the_primary_gates(capsys: pytest.CaptureFixture[str]) -> None:
    """`hm verification_plan commands` is what the stages actually invoke.

    A unit test over `read_plan` does not exercise it — `[fail:test]
    shipped-entry-point-not-exercised` (count:4) is exactly the gap where the
    module works and the command the template calls does not.
    """
    from harness_maker.verification_plan import main

    rc = main(["commands", "--root", str(REPO_ROOT)])
    out = capsys.readouterr().out.splitlines()
    assert rc == 0
    assert out == read_plan(REPO_ROOT).primary_commands()


def test_cli_commands_exits_one_and_explains_when_degraded(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Degraded must be a non-zero exit AND a stderr reason.

    The stage branches on the exit code to decide whether it is guessing. A silent
    exit 0 with no commands would read as "this project has no gates to run".
    """
    from harness_maker.verification_plan import main

    rc = main(["commands", "--root", str(tmp_path)])
    captured = capsys.readouterr()
    assert rc == 1
    assert captured.out == ""
    assert "degraded" in captured.err


def test_cli_show_emits_parseable_json_with_the_documented_keys(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """`show` is the diagnostic surface the stage points a reader at when a gate looks missing."""
    import json

    from harness_maker.verification_plan import main

    rc = main(["show", "--root", str(REPO_ROOT)])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 0
    for key in (
        "gates",
        "primary_commands",
        "additional_commands",
        "blocking_commands",
        "unclassified",
        "sources",
        "non_gating",
        "degraded",
        "reason",
    ):
        assert key in payload, f"documented key missing from `show` output: {key}"
