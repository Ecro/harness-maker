"""Phase 1 — DeliveryMetricsConfig schema + round-trip (SPEC AC-008, PLAN ADR-003)."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
from pydantic import ValidationError

from harness_maker import interview
from harness_maker.models import DeliveryMetricsConfig, HarnessConfig, InterviewAnswers


def _answers_from_yaml(text: str, tmp_path: Path) -> InterviewAnswers | None:
    p = tmp_path / "harness.yaml"
    p.write_text(textwrap.dedent(text), encoding="utf-8")
    return interview.answers_from_harness_yaml(p)


def test_config_defaults_and_legacy_load(tmp_path: Path) -> None:
    """AC-008 (0.36.0): default tuning loads; a legacy harness.yaml WITHOUT the
    block loads; a 0.35.0-era file WITH the now-removed `enabled` key loads and
    the stale key is silently dropped while sibling tuning is preserved."""
    assert DeliveryMetricsConfig().tag_pattern == "v*"
    assert HarnessConfig().delivery_metrics.tag_pattern == "v*"
    # No `enabled` field anymore (removed in 0.36.0 — manual, read-only command).
    assert "enabled" not in DeliveryMetricsConfig.model_fields

    # Legacy file: no delivery_metrics block at all.
    answers = _answers_from_yaml("preset: Side\nlocale: en\ntargets: [claude-code]\n", tmp_path)
    assert answers is not None
    assert answers.delivery_metrics.tag_pattern == "v*"

    # 0.35.0-era file: stale `enabled` key present alongside real tuning.
    yaml_text = """
        preset: Production
        locale: ko
        targets: [claude-code]
        delivery_metrics:
          enabled: true
          tag_pattern: "release-*"
          cfr_window_days: 56
    """
    migrated = _answers_from_yaml(yaml_text, tmp_path)
    assert migrated is not None
    # enabled dropped (not a field); tuning survives.
    assert migrated.delivery_metrics.tag_pattern == "release-*"
    assert migrated.delivery_metrics.cfr_window_days == 56
    assert migrated.delivery_metrics.churn_maturation_days == 14  # unspecified → default


def test_enabled_key_rejected_on_direct_construction() -> None:
    """extra='forbid' + no `enabled` field: constructing with enabled raises
    (both readers pre-filter unknown keys, so only a direct call hits this)."""
    with pytest.raises(ValidationError):
        DeliveryMetricsConfig(enabled=True)  # type: ignore[call-arg]


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


def test_tuning_round_trip(tmp_path: Path) -> None:
    """Custom tuning survives answers_from_harness_yaml."""
    yaml_text = """
        preset: Production
        locale: ko
        targets: [claude-code]
        delivery_metrics:
          tag_pattern: "release-*"
          cfr_window_days: 56
          paths: ["src/"]
    """
    answers = _answers_from_yaml(yaml_text, tmp_path)
    assert answers is not None
    assert answers.delivery_metrics.tag_pattern == "release-*"
    assert answers.delivery_metrics.cfr_window_days == 56
    assert answers.delivery_metrics.paths == ["src/"]
    assert answers.delivery_metrics.churn_maturation_days == 14  # default kept


def test_malformed_block_falls_back(tmp_path: Path) -> None:
    """A malformed tuning value / non-dict block → tolerant default; OTHER fields
    of the same yaml still parse (schema-gap fallback, CLAUDE.md checkpoint 6)."""
    yaml_text = """
        preset: Side
        locale: en
        targets: [claude-code]
        delivery_metrics:
          cfr_window_days: "not-a-number"
    """
    answers = _answers_from_yaml(yaml_text, tmp_path)
    assert answers is not None
    assert answers.locale == "en"
    assert answers.delivery_metrics.cfr_window_days == 28  # tolerant default

    yaml_list = """
        preset: Side
        locale: en
        targets: [claude-code]
        delivery_metrics: [1, 2]
    """
    answers2 = _answers_from_yaml(yaml_list, tmp_path)
    assert answers2 is not None
    assert answers2.delivery_metrics.tag_pattern == "v*"


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
