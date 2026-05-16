"""Tests for harness_maker.recommendation registry + concrete recommenders.

Phase 1 introduced the framework (registry + dispatcher). Phase 4 widens
the recommender signature to ``(profile, project_dir)`` and registers the
first two concrete recommenders: ``wrapup_docs`` and ``mcp_servers``.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from harness_maker.models import (
    Confidence,
    ProjectProfile,
    Recommendation,
    RecommendationEvidence,
)
from harness_maker.recommendation import (
    _REGISTRY,
    recommend,
    recommend_all,
    register,
)

# Snapshot the production-clean registry contents at import time, BEFORE the
# autouse fixture starts clearing per-test. This lets us assert what Phase 4
# ships without re-importing or reloading the module.
_PRODUCTION_AXES: frozenset[str] = frozenset(_REGISTRY)

if TYPE_CHECKING:
    from collections.abc import Iterator


# ──────────────────────────────────────────────────────────────────────────────
# Fixtures — isolate registry mutation per test so order doesn't matter.
# ──────────────────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _clean_registry() -> Iterator[None]:
    """Save/restore registry so each test starts from the production-clean state."""
    saved = dict(_REGISTRY)
    _REGISTRY.clear()
    try:
        yield
    finally:
        _REGISTRY.clear()
        _REGISTRY.update(saved)


def _ev(c: Confidence = Confidence.HIGH) -> RecommendationEvidence:
    return RecommendationEvidence(confidence=c)


# ──────────────────────────────────────────────────────────────────────────────
# Phase 4 invariant — registry ships exactly the two concrete axes.
# Replaces the Phase 1 "registry empty" invariant.
# ──────────────────────────────────────────────────────────────────────────────


def test_registry_contains_phase_4_and_8_axes() -> None:
    """Production-clean registry exposes the Phase 4 + Phase 8 axes.

    Phase 4 shipped ``wrapup_docs`` + ``mcp_servers``; Phase 8 migrated the
    existing 4 transitive recommends (``preset``, ``dev_mode``,
    ``mechanical_checks``, ``second_brain``) into the registry. Updating
    this assertion is the intended forcing function so we notice
    unintentional registrations.
    """
    assert (
        frozenset(
            {
                "wrapup_docs",
                "mcp_servers",
                "preset",
                "dev_mode",
                "mechanical_checks",
                "second_brain",
            },
        )
        == _PRODUCTION_AXES
    )


# ──────────────────────────────────────────────────────────────────────────────
# register decorator
# ──────────────────────────────────────────────────────────────────────────────


def test_register_decorator_adds_entry() -> None:
    @register("preset")
    def _r(_p: ProjectProfile, _d: Path) -> Recommendation:
        return Recommendation(
            axis="preset",
            value="Side",
            confidence=Confidence.HIGH,
            evidence=_ev(),
        )

    assert "preset" in _REGISTRY
    assert _REGISTRY["preset"] is _r


def test_register_decorator_returns_original_callable() -> None:
    """Decorator must be transparent — wrapped fn is identical."""

    def _impl(_p: ProjectProfile, _d: Path) -> Recommendation:
        return Recommendation(
            axis="x",
            value=1,
            confidence=Confidence.LOW,
            evidence=_ev(Confidence.LOW),
        )

    wrapped = register("x")(_impl)
    assert wrapped is _impl


def test_register_rejects_duplicate_axis() -> None:
    @register("preset")
    def _a(_p: ProjectProfile, _d: Path) -> Recommendation:
        return Recommendation(
            axis="preset",
            value="Side",
            confidence=Confidence.HIGH,
            evidence=_ev(),
        )

    with pytest.raises(ValueError, match="already registered"):

        @register("preset")
        def _b(_p: ProjectProfile, _d: Path) -> Recommendation:
            return Recommendation(
                axis="preset",
                value="Production",
                confidence=Confidence.HIGH,
                evidence=_ev(),
            )


def test_register_rejects_empty_axis_name() -> None:
    with pytest.raises(ValueError, match="axis"):

        @register("")
        def _r(_p: ProjectProfile, _d: Path) -> Recommendation:
            return Recommendation(
                axis="",
                value=None,
                confidence=Confidence.LOW,
                evidence=_ev(Confidence.LOW),
            )


# ──────────────────────────────────────────────────────────────────────────────
# recommend (single dispatcher)
# ──────────────────────────────────────────────────────────────────────────────


def test_recommend_unknown_axis_returns_none(tmp_path: Path) -> None:
    assert recommend("does-not-exist", ProjectProfile(), tmp_path) is None


def test_recommend_dispatches_to_registered_callable(tmp_path: Path) -> None:
    @register("preset")
    def _r(profile: ProjectProfile, _d: Path) -> Recommendation:
        return Recommendation(
            axis="preset",
            value="Production" if "rust" in profile.stack else "Side",
            confidence=Confidence.HIGH,
            evidence=_ev(),
        )

    out = recommend("preset", ProjectProfile(stack=["rust"]), tmp_path)
    assert out is not None
    assert out.axis == "preset"
    assert out.value == "Production"
    assert out.confidence == Confidence.HIGH


def test_recommend_propagates_none_from_recommender(tmp_path: Path) -> None:
    """A recommender may return None when it has insufficient signal."""

    @register("preset")
    def _r(_p: ProjectProfile, _d: Path) -> Recommendation | None:
        return None

    assert recommend("preset", ProjectProfile(), tmp_path) is None


def test_recommend_axis_mismatch_raises(tmp_path: Path) -> None:
    """If a recommender returns a Recommendation with the wrong axis, fail loud."""

    @register("preset")
    def _r(_p: ProjectProfile, _d: Path) -> Recommendation:
        return Recommendation(
            axis="WRONG",
            value="x",
            confidence=Confidence.LOW,
            evidence=_ev(Confidence.LOW),
        )

    with pytest.raises(ValueError, match="axis"):
        recommend("preset", ProjectProfile(), tmp_path)


# ──────────────────────────────────────────────────────────────────────────────
# recommend_all (fan-out)
# ──────────────────────────────────────────────────────────────────────────────


def test_recommend_all_empty_registry_returns_empty_list(tmp_path: Path) -> None:
    assert recommend_all(ProjectProfile(), tmp_path) == []


def test_recommend_all_collects_non_none_results(tmp_path: Path) -> None:
    @register("preset")
    def _preset(_p: ProjectProfile, _d: Path) -> Recommendation:
        return Recommendation(
            axis="preset",
            value="Side",
            confidence=Confidence.HIGH,
            evidence=_ev(),
        )

    @register("dev_mode")
    def _dev_mode(_p: ProjectProfile, _d: Path) -> Recommendation | None:
        return None  # insufficient signal — must be skipped

    @register("targets")
    def _targets(_p: ProjectProfile, _d: Path) -> Recommendation:
        return Recommendation(
            axis="targets",
            value=["claude-code"],
            confidence=Confidence.MEDIUM,
            evidence=_ev(Confidence.MEDIUM),
        )

    out = recommend_all(ProjectProfile(), tmp_path)
    axes = {r.axis for r in out}
    assert axes == {"preset", "targets"}


def test_recommend_all_orders_high_before_medium_before_low(tmp_path: Path) -> None:
    """Confidence-bucketed dispatch ordering — HIGH first, LOW last (ADR-004/007)."""

    @register("a")
    def _a(_p: ProjectProfile, _d: Path) -> Recommendation:
        return Recommendation(
            axis="a",
            value=1,
            confidence=Confidence.LOW,
            evidence=_ev(Confidence.LOW),
        )

    @register("b")
    def _b(_p: ProjectProfile, _d: Path) -> Recommendation:
        return Recommendation(
            axis="b",
            value=2,
            confidence=Confidence.HIGH,
            evidence=_ev(Confidence.HIGH),
        )

    @register("c")
    def _c(_p: ProjectProfile, _d: Path) -> Recommendation:
        return Recommendation(
            axis="c",
            value=3,
            confidence=Confidence.MEDIUM,
            evidence=_ev(Confidence.MEDIUM),
        )

    out = recommend_all(ProjectProfile(), tmp_path)
    buckets = [r.confidence for r in out]
    # All HIGH come before any MEDIUM, all MEDIUM before any LOW.
    high_idx = [i for i, c in enumerate(buckets) if c == Confidence.HIGH]
    med_idx = [i for i, c in enumerate(buckets) if c == Confidence.MEDIUM]
    low_idx = [i for i, c in enumerate(buckets) if c == Confidence.LOW]
    assert max(high_idx) < min(med_idx)
    assert max(med_idx) < min(low_idx)


def test_recommend_all_skips_invalid_axis_return_or_raises(tmp_path: Path) -> None:
    """A misbehaving recommender (wrong axis) should not silently corrupt fan-out."""

    @register("preset")
    def _bad(_p: ProjectProfile, _d: Path) -> Recommendation:
        return Recommendation(
            axis="OTHER",
            value=1,
            confidence=Confidence.HIGH,
            evidence=_ev(),
        )

    with pytest.raises(ValueError, match="axis"):
        recommend_all(ProjectProfile(), tmp_path)


# ──────────────────────────────────────────────────────────────────────────────
# Phase 4 — recommend_wrapup_docs (filesystem probe)
# ──────────────────────────────────────────────────────────────────────────────


def _call_wrapup_via_registry(profile: ProjectProfile, project_dir: Path) -> Recommendation | None:
    """Helper: invoke the production recommend_wrapup_docs through the dispatcher.

    The autouse fixture clears _REGISTRY for each test, so we re-register the
    real callable for Phase 4 behavior tests by importing it.
    """
    from harness_maker.recommendation import recommend_wrapup_docs

    return recommend_wrapup_docs(profile, project_dir)


def test_recommend_wrapup_docs_changelog_only(tmp_path: Path) -> None:
    """Single CHANGELOG.md match → recommendation lists exactly that file."""
    (tmp_path / "CHANGELOG.md").write_text("# Changelog\n", encoding="utf-8")

    out = _call_wrapup_via_registry(ProjectProfile(), tmp_path)
    assert out is not None
    assert out.axis == "wrapup_docs"
    assert out.value == ["CHANGELOG.md"]


def test_recommend_wrapup_docs_multiple_signals(tmp_path: Path) -> None:
    """Multiple wrapup signals (CHANGELOG + TODO + ADR glob) all surface."""
    (tmp_path / "CHANGELOG.md").write_text("# Changelog\n", encoding="utf-8")
    (tmp_path / "TODO.md").write_text("- [ ] thing\n", encoding="utf-8")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "ADR-001.md").write_text("# ADR-001\n", encoding="utf-8")

    out = _call_wrapup_via_registry(ProjectProfile(), tmp_path)
    assert out is not None
    assert set(out.value) == {"CHANGELOG.md", "TODO.md", "docs/ADR-001.md"}


def test_recommend_wrapup_docs_none_when_no_signal(tmp_path: Path) -> None:
    """Empty project_dir → no recommendation (None, not an empty list)."""
    out = _call_wrapup_via_registry(ProjectProfile(), tmp_path)
    assert out is None


def test_recommend_wrapup_docs_confidence_high_with_signal(tmp_path: Path) -> None:
    """An explicit filename match is identity-level evidence → HIGH bucket."""
    (tmp_path / "CHANGELOG.md").write_text("x\n", encoding="utf-8")

    out = _call_wrapup_via_registry(ProjectProfile(), tmp_path)
    assert out is not None
    assert out.confidence == Confidence.HIGH
    assert out.evidence.confidence == Confidence.HIGH


# ──────────────────────────────────────────────────────────────────────────────
# Phase 4 — recommend_mcp_servers (framework → MCP mapping)
# ──────────────────────────────────────────────────────────────────────────────


def _call_mcp_via_registry(profile: ProjectProfile, project_dir: Path) -> Recommendation | None:
    """Helper: invoke production recommend_mcp_servers directly."""
    from harness_maker.recommendation import recommend_mcp_servers

    return recommend_mcp_servers(profile, project_dir)


def test_recommend_mcp_react_project_gets_playwright(tmp_path: Path) -> None:
    """React in frameworks → playwright MCP server suggested."""
    profile = ProjectProfile(frameworks=["react"])

    out = _call_mcp_via_registry(profile, tmp_path)
    assert out is not None
    assert out.axis == "mcp_servers"
    assert "playwright" in out.value
    assert out.value["playwright"]["command"] == "npx"


def test_recommend_mcp_vue_project_gets_playwright(tmp_path: Path) -> None:
    """Vue follows the same frontend → playwright mapping."""
    profile = ProjectProfile(frameworks=["vue"])

    out = _call_mcp_via_registry(profile, tmp_path)
    assert out is not None
    assert "playwright" in out.value


def test_recommend_mcp_python_only_no_recommendation(tmp_path: Path) -> None:
    """Python-only stacks have no entry in the conservative MCP table → None."""
    profile = ProjectProfile(frameworks=["fastapi", "django"])

    out = _call_mcp_via_registry(profile, tmp_path)
    assert out is None


def test_recommend_mcp_confidence_medium(tmp_path: Path) -> None:
    """Framework → server mapping IS inference, not identity → MEDIUM bucket."""
    profile = ProjectProfile(frameworks=["next"])

    out = _call_mcp_via_registry(profile, tmp_path)
    assert out is not None
    assert out.confidence == Confidence.MEDIUM
    assert out.evidence.confidence == Confidence.MEDIUM
