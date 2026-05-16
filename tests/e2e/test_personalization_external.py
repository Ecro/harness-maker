"""ADR-010 amendment external e2e test — vendors github/spec-kit fixture.

Per PLAN Phase 12: when this fixture is missing, skip with TODO for follow-up
PLAN to vendor spec-kit into ``tests/e2e/fixtures/external-project-spec-kit/``.
The vendoring is non-trivial (size, licensing) so this phase ships the
contract-asserting test in skip mode — it activates the moment the fixture
lands without further code changes.
"""

from __future__ import annotations

from pathlib import Path

import pytest

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "external-project-spec-kit"


@pytest.mark.skipif(
    not FIXTURE_ROOT.is_dir(),
    reason="TODO: vendor github/spec-kit fixture (ADR-010 amendment)",
)
def test_personalization_audit_on_spec_kit() -> None:
    """Run profile + audit on spec-kit; assert no crash and tier is valid."""
    from harness_maker.personalization_audit import run_audit
    from harness_maker.profile import profile

    p = profile(FIXTURE_ROOT)
    assert p.stack  # at least one stack detected

    plan = run_audit(FIXTURE_ROOT)
    assert plan.tier in {"bronze", "silver", "gold", "platinum"}


@pytest.mark.skipif(
    not FIXTURE_ROOT.is_dir(),
    reason="TODO: vendor github/spec-kit fixture (ADR-010 amendment)",
)
def test_foreign_config_detection_on_spec_kit() -> None:
    """spec-kit likely has CLAUDE.md / AGENTS.md / etc — assert detect() runs."""
    from harness_maker.foreign_config import detect

    configs = detect(FIXTURE_ROOT)
    assert isinstance(configs, list)
