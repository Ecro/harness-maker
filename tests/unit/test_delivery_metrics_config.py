"""Phase 1 — DeliveryMetricsConfig schema + round-trip (SPEC AC-008, PLAN ADR-003)."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
from pydantic import ValidationError

from harness_maker import interview
from harness_maker.models import DeliveryMetricsConfig, HarnessConfig


def _answers_from_yaml(text: str, tmp_path: Path) -> interview.InterviewAnswers | None:
    p = tmp_path / "harness.yaml"
    p.write_text(textwrap.dedent(text), encoding="utf-8")
    return interview.answers_from_harness_yaml(p)


def test_config_default_off_and_legacy_load(tmp_path: Path) -> None:
    """AC-008: default-constructed config is disabled; legacy harness.yaml
    without the `delivery_metrics:` key loads without error and defaults off."""
    assert DeliveryMetricsConfig().enabled is False
    assert HarnessConfig().delivery_metrics.enabled is False
    yaml_text = """
        preset: Side
        locale: en
        targets: [claude-code]
    """
    answers = _answers_from_yaml(yaml_text, tmp_path)
    assert answers is not None
    assert answers.delivery_metrics.enabled is False


def test_defaults_match_adr_003() -> None:
    """ADR-003 field defaults: windows, cap, tag pattern, branch, paths."""
    cfg = DeliveryMetricsConfig()
    assert cfg.tag_pattern == "v*"
    assert cfg.default_branch is None
    assert cfg.cfr_window_days == 28
    assert cfg.churn_maturation_days == 14
    assert cfg.churn_cohort_days == 14
    assert cfg.blame_file_cap == 500
    assert cfg.paths == []


def test_enabled_round_trip(tmp_path: Path) -> None:
    """Enabled block with custom fields survives answers_from_harness_yaml."""
    yaml_text = """
        preset: Production
        locale: ko
        targets: [claude-code]
        delivery_metrics:
          enabled: true
          tag_pattern: "release-*"
          cfr_window_days: 56
    """
    answers = _answers_from_yaml(yaml_text, tmp_path)
    assert answers is not None
    assert answers.delivery_metrics.enabled is True
    assert answers.delivery_metrics.tag_pattern == "release-*"
    assert answers.delivery_metrics.cfr_window_days == 56
    # Unspecified fields keep defaults, not zeros.
    assert answers.delivery_metrics.churn_maturation_days == 14


def test_malformed_block_falls_back(tmp_path: Path) -> None:
    """Non-dict block / non-bool enabled → tolerant default; other fields parse.

    Three constrained paths (same contract as test_feedback_malformed_value_falls_back):
    (A) tolerant fallback → all asserts pass; (B) silent coerce "yes"→True → last
    assert fails; (C) uncaught ValidationError poisons load → answers is None.
    """
    yaml_text = """
        preset: Side
        locale: en
        targets: [claude-code]
        delivery_metrics:
          enabled: "yes"
    """
    answers = _answers_from_yaml(yaml_text, tmp_path)
    assert answers is not None
    assert answers.locale == "en"
    assert answers.delivery_metrics.enabled is False

    yaml_list = """
        preset: Side
        locale: en
        targets: [claude-code]
        delivery_metrics: [1, 2]
    """
    answers2 = _answers_from_yaml(yaml_list, tmp_path)
    assert answers2 is not None
    assert answers2.delivery_metrics.enabled is False


@pytest.mark.parametrize(
    "bad_pattern",
    [
        "v*;rm -rf",  # shell metachar
        "v`x`*",  # backtick
        "$(evil)",  # command substitution
        "-evil*",  # leading dash (argv option injection)
        "../refs*",  # traversal
        "v *",  # whitespace
        "",  # empty
    ],
)
def test_tag_pattern_validator_rejects(bad_pattern: str) -> None:
    """ADR-003: tag_pattern flows into git argv — reject shell/option/traversal shapes."""
    with pytest.raises(ValidationError):
        DeliveryMetricsConfig(tag_pattern=bad_pattern)


@pytest.mark.parametrize(
    "good_pattern",
    [
        "v*",
        "release-*",
        "v[0-9]*",
        "app/v*",
        "pkg@*",  # monorepo per-package tags — `@` is a literal in fnmatch
        "service:v*",  # `:` likewise — must NOT be rejected as a revspec op
    ],
)
def test_tag_pattern_validator_accepts_globs(good_pattern: str) -> None:
    """fnmatch glob characters (and literals like @ / :) are the point of the
    field — tag_pattern goes to `git tag --list` (fnmatch), NOT a revision, so
    revspec-operator rejection must NOT apply here (REVIEW self-caught regression)."""
    assert DeliveryMetricsConfig(tag_pattern=good_pattern).tag_pattern == good_pattern


def test_default_branch_validator_rejects_option_injection() -> None:
    """default_branch is passed as a git argv value — reject leading dash + metachars."""
    with pytest.raises(ValidationError):
        DeliveryMetricsConfig(default_branch="--upload-pack=evil")
    with pytest.raises(ValidationError):
        DeliveryMetricsConfig(default_branch="main;rm")
    assert DeliveryMetricsConfig(default_branch="trunk").default_branch == "trunk"


@pytest.mark.parametrize(
    "revspec",
    [
        "master^{/regex}",  # commit-message reachability scan (DoS gadget)
        "HEAD~3",  # ancestor walk
        "main@{yesterday}",  # reflog revspec
        "v1.0.0^",  # first parent
        "refs:evil",  # colon operator
    ],
)
def test_revspec_operators_rejected(revspec: str) -> None:
    """REVIEW security P1: default_branch is interpolated into a git revision, so
    revspec operators (^ ~ : @ { }) must be rejected — else `master^{/regex}`
    becomes a full-history scan gadget."""
    with pytest.raises(ValidationError):
        DeliveryMetricsConfig(default_branch=revspec)


def test_paths_validator_rejects_traversal_and_absolute() -> None:
    """paths scope `git log -- <path>` — project-relative only."""
    with pytest.raises(ValidationError):
        DeliveryMetricsConfig(paths=["../outside"])
    with pytest.raises(ValidationError):
        DeliveryMetricsConfig(paths=["/etc"])
    assert DeliveryMetricsConfig(paths=["src/", "lib/"]).paths == ["src/", "lib/"]
