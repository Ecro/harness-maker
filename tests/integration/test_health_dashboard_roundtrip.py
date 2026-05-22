"""Round-trip contract test: run_structural() -> write_dashboard() -> parse_dashboard().

Bug 2 (PLAN-health-plugin-bugs-2026-05) shipped because the producer and the
renderer were tested in isolation against fixture dicts that each matched
their own assumption. No test exercised the real producer output flowing into
the real renderer. The first time the contract drifted (producer returned
``{"structural": <int>}`` but renderer expected ``{"score": <int>}``), every
user's dashboard rendered ``score: 0 / 100`` and the test suite stayed green.

This module closes that gap with two tests:

  - ``test_dashboard_roundtrip_preserves_structural_score`` — the safety net.
    Floor + equality assertions catch fixture rot and contract drift.

  - ``test_dashboard_roundtrip_catches_producer_key_drift`` — meta-test that
    proves the safety net actually fires when fed the OLD shape. Without this
    proof, the "non-zero" clause in the first test could be vacuous.

ADR-002 in ``work-docs/PLAN-health-plugin-bugs-2026-05.md`` pins the fixture
floor at 30 points and the assertion structure.
"""

from __future__ import annotations

from pathlib import Path

from harness_maker.ai_readiness import run_structural
from harness_maker.models import Preset
from harness_maker.observability.dashboard import parse_dashboard, write_dashboard
from tests.integration.conftest import build_min_fixture

# ADR-002 pinned floor: fixture must clear this on Side preset so the
# floor assertion is meaningful (not vacuously true with score=0).
MIN_FIXTURE_SCORE = 30

# Minimal valid personalization section — orthogonal to Bug 2 (which is
# about the structural section's schema). Kept constant so the test
# isolates the producer↔renderer contract for the structural layer alone.
# ADR-0007 removed the external_risks section in 0.22.3.
_MIN_PERSONALIZATION: dict[str, object] = {
    "composite": 0,
    "tier": "bronze",
    "layers": {},
    "action_items": [],
}


def test_dashboard_roundtrip_preserves_structural_score(tmp_path: Path) -> None:
    """Real producer → real renderer → real parser; score survives the trip.

    Two assertions, two failure modes:
      - ``producer_score >= MIN_FIXTURE_SCORE`` — catches fixture drift that
        would silently zero the score and make the equality check vacuous.
      - ``parsed_score == producer_score`` — catches producer/consumer schema
        drift like Bug 2 (renamed key, missing key, type mismatch).
    """
    fixture = build_min_fixture(tmp_path)

    result = run_structural(fixture, preset=Preset.SIDE)
    # Producer is expected to expose the score under the contract key the
    # renderer reads from (``dashboard.py`` reads ``structural.get("score")``).
    # If the producer changes its return shape, accessing this key fails
    # loudly here — that is the intent of this assertion.
    producer_score = result["score"]
    assert producer_score >= MIN_FIXTURE_SCORE, (
        f"Fixture floor not cleared: producer_score={producer_score} "
        f"(expected >= {MIN_FIXTURE_SCORE}). Either the fixture has rotted "
        "or a signal weight changed. Seed one more signal in "
        "build_min_fixture, do NOT lower the floor."
    )

    dashboard_path = write_dashboard(
        fixture,
        result,
        _MIN_PERSONALIZATION,
        generated_at="2026-05-17T00:00:00+00:00",
    )
    parsed = parse_dashboard(dashboard_path)
    assert parsed is not None, "parse_dashboard returned None — schema unparseable"
    parsed_score = parsed["structural"]["score"]

    assert parsed_score == producer_score, (
        f"Contract drift: producer reported {producer_score} but dashboard "
        f"rendered {parsed_score}. Check the key name agreement between "
        "ai_readiness.run_structural() return shape and "
        "observability/dashboard.py render_dashboard_markdown()."
    )


def test_dashboard_roundtrip_catches_producer_key_drift(tmp_path: Path) -> None:
    """Meta-test: prove the round-trip would fire if the OLD shape returned.

    Constructs the pre-Phase-2 producer return shape (``{"structural": <int>}``)
    by hand, sends it through the real ``write_dashboard()``, parses back, and
    asserts the renderer extracted 0 — meaning the equality assertion in the
    main test would have caught the drift. Without this proof, the floor +
    equality assertions could pass for the wrong reasons (e.g. if both sides
    drifted to use the same wrong key).
    """
    fixture = build_min_fixture(tmp_path)

    # OLD shape: pre-Phase-2 producer return — key is "structural", not "score".
    # The renderer reads ``.get("score")`` which is None → coerced to 0.
    old_shape_claimed_score = 81
    old_shape_result: dict[str, object] = {
        "structural": old_shape_claimed_score,
        "signals_failed": [],
    }

    dashboard_path = write_dashboard(
        fixture,
        old_shape_result,
        _MIN_PERSONALIZATION,
        generated_at="2026-05-17T00:00:00+00:00",
    )
    parsed = parse_dashboard(dashboard_path)
    assert parsed is not None
    parsed_score = parsed["structural"]["score"]

    # Drift proof part 1: renderer can't extract score from OLD shape → 0.
    assert parsed_score == 0, (
        f"Expected parsed_score=0 from OLD shape (renderer reads 'score' "
        f"key, not 'structural'); got {parsed_score}. If this assertion "
        "fires, the contract drift safety net may have been silently "
        "weakened — investigate render_dashboard_markdown()."
    )

    # Drift proof part 2: the main test's equality assertion would fail
    # on this OLD shape because claimed score (81) != parsed (0).
    assert old_shape_claimed_score != parsed_score, (
        "The main test's equality assertion would NOT fire on this drift "
        "— the round-trip safety net is broken."
    )
