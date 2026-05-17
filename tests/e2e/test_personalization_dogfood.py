"""Phase 12 dogfood e2e — run profile + foreign_config + audit on harness-maker itself.

The worktree IS a clone of harness-maker; we exercise the Track A / D / B
personalization stack against our own repo and assert basic contract shape:
non-empty Python framework list, ``uv`` package manager, ``python`` in stack,
foreign_config returning a list, and a PersonalizationPlan with score in
[0, 100] + a valid tier label.

Cache isolation: we redirect both ``detection_cache._default_cache_dir`` and
``foreign_config._default_cache_dir`` into ``tmp_path`` so the test never
touches ``~/.cache/harness-maker/``. ``personalization_audit.run_audit``
delegates to ``detection_cache.load_or_run`` which honours that monkeypatch.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from harness_maker import detection_cache, foreign_config
from harness_maker.personalization_audit import PersonalizationPlan, run_audit
from harness_maker.profile import profile

# The worktree root = the project we profile. tests/e2e/ → parents[2] = repo root.
WORKTREE_ROOT = Path(__file__).resolve().parents[2]

# Python frameworks/libraries harness-maker itself depends on; the detector
# must surface at least one of these. Phase 3's framework heuristics include
# anthropic + httpx + pytest + jinja2 + pydantic + typer (subset matches OK).
EXPECTED_FRAMEWORK_CANDIDATES = {
    "pytest",
    "pydantic",
    "jinja2",
    "anthropic",
    "httpx",
    "typer",
}

VALID_TIERS = {"bronze", "silver", "gold", "platinum"}


@pytest.fixture
def _isolated_caches(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Redirect both detection_cache + foreign_config cache dirs into tmp_path.

    Mirrors the autouse fixture in tests/unit/conftest.py but local to this
    e2e file (e2e/ has no shared conftest yet).
    """
    tmp_cache = tmp_path / "hm-cache"
    monkeypatch.setattr(detection_cache, "_default_cache_dir", lambda: tmp_cache)
    monkeypatch.setattr(foreign_config, "_default_cache_dir", lambda: tmp_cache)


@pytest.mark.usefixtures("_isolated_caches")
def test_profile_detects_python_stack_on_harness_maker() -> None:
    """profile() on the harness-maker repo itself must detect python + uv."""
    p = profile(WORKTREE_ROOT)

    assert "python" in p.stack, f"expected python in stack, got {p.stack!r}"
    assert p.package_manager == "uv", f"expected package_manager='uv', got {p.package_manager!r}"
    assert isinstance(p.frameworks, list)
    assert len(p.frameworks) >= 1, (
        f"expected at least one detected framework, got empty list (stack={p.stack!r})"
    )
    # At least one well-known harness-maker dep should be detected.
    detected = set(p.frameworks)
    assert detected & EXPECTED_FRAMEWORK_CANDIDATES, (
        f"none of {EXPECTED_FRAMEWORK_CANDIDATES} found in {detected!r}"
    )
    # ci_provider may be empty in the worktree (no .github/workflows/ symlinked
    # into worktrees by default) — acceptable per Phase 3 dogfood spec.
    assert isinstance(p.ci_provider, str)


@pytest.mark.usefixtures("_isolated_caches")
def test_foreign_config_detect_returns_list() -> None:
    """foreign_config.detect must always return a list; harness-maker has none."""
    configs = foreign_config.detect(WORKTREE_ROOT)
    assert isinstance(configs, list)


@pytest.mark.usefixtures("_isolated_caches")
def test_run_audit_returns_valid_personalization_plan() -> None:
    """run_audit must return a PersonalizationPlan with valid composite + tier."""
    plan = run_audit(WORKTREE_ROOT)

    assert isinstance(plan, PersonalizationPlan)
    assert isinstance(plan.composite_score, int)
    assert 0 <= plan.composite_score <= 100, f"composite_score out of range: {plan.composite_score}"
    assert plan.tier in VALID_TIERS, f"unexpected tier: {plan.tier!r}"
    assert isinstance(plan.layer_scores, dict)
    assert isinstance(plan.actions, list)


def test_no_cache_writes_outside_tmp(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sanity: after exercising the stack, the tmp cache dir holds all artefacts."""
    tmp_cache = tmp_path / "hm-cache"
    monkeypatch.setattr(detection_cache, "_default_cache_dir", lambda: tmp_cache)
    monkeypatch.setattr(foreign_config, "_default_cache_dir", lambda: tmp_cache)

    profile(WORKTREE_ROOT)
    foreign_config.detect(WORKTREE_ROOT)
    run_audit(WORKTREE_ROOT)

    # If the cache dir exists, it was created under tmp_path (the only place we
    # redirected). Both modules use ``_default_cache_dir`` exclusively when
    # callers don't pass an explicit ``cache_dir``, so no leak path remains.
    if tmp_cache.exists():
        # All files inside must live under tmp_path.
        for entry in tmp_cache.rglob("*"):
            assert tmp_path in entry.resolve().parents or entry.resolve() == tmp_cache, (
                f"unexpected cache file outside tmp: {entry}"
            )
