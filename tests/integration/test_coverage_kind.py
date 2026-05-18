"""Phase 7 coverage-kind classifier fixture (PLAN F7 + ADR-010).

Mock-LLM only — NOT gated by INTEGRATION=1 because the heuristic + mock
paths give deterministic results without real Claude calls. Real-LLM
validation happens at the post-ship telemetry layer (`/hm:health`).
"""

from __future__ import annotations

from harness_maker.observability.coverage_classifier import (
    ALL_KINDS,
    CoverageKind,
    classify_q,
)

# 12 synthetic interview questions chosen so the heuristic taxonomy at
# `coverage_classifier._HEURISTIC_MAP` produces every one of the 5 named
# kinds ≥1 times. If a future heuristic change drops a kind, this fixture
# fails — that's the regression signal ADR-010 mandates.
SYNTHETIC_INTERVIEW_QUESTIONS: list[str] = [
    # WRONG (failure criteria)
    "What would you say is wrong with the current authentication flow?",
    "What are the rejection criteria for this feature?",
    # METHOD (implementation assumption)
    "How will you implement the retry logic?",
    "What assumption are you making about database write throughput?",
    # STAKEHOLDER (review / audience)
    "Who else needs to review the API change before launch?",
    "Which downstream stakeholder consumes this report?",
    # STYLE (format / convention)
    "What format should the audit log file use?",
    "Do you have a naming convention for the new module?",
    # PERF (scale / latency / throughput)
    "What latency target should the gateway meet?",
    "How does this scale to 100k requests/sec?",
    # OTHER fallback — neither heuristic nor classifier matches a named kind
    "Should we keep the configuration in a separate file?",
    "Which database engine do you use?",
]


def test_synthetic_fixture_size_meets_plan_floor() -> None:
    """PLAN F7 AC: fixture has at least 10 synthetic interviews."""
    assert len(SYNTHETIC_INTERVIEW_QUESTIONS) >= 10


def test_all_five_kinds_present_in_synthetic_fixture() -> None:
    """ADR-010 telemetry guard: every named kind (WRONG/METHOD/STAKEHOLDER/
    STYLE/PERF) appears ≥1 time in the synthetic fixture. If this fails,
    the heuristic has regressed and coverage-drift detection is blind."""
    kinds_seen: set[str] = set()
    for q in SYNTHETIC_INTERVIEW_QUESTIONS:
        kinds_seen.add(classify_q(q))

    required = {"WRONG", "METHOD", "STAKEHOLDER", "STYLE", "PERF"}
    missing = required - kinds_seen
    assert not missing, (
        f"coverage-kind regression: synthetic fixture missing {missing}. "
        f"Update either the fixture or coverage_classifier._HEURISTIC_MAP."
    )


def test_classify_q_with_mock_classifier_fn() -> None:
    """classifier_fn override (production LLM path) is respected."""

    def mock_classifier(q: str) -> CoverageKind:
        return "STYLE"

    assert classify_q("anything", classifier_fn=mock_classifier) == "STYLE"


def test_classify_q_invalid_classifier_return_coerced_to_other() -> None:
    """A classifier_fn returning a non-CoverageKind value is coerced to OTHER."""

    def bad_classifier(q: str) -> CoverageKind:
        return "INVALID_KIND"  # type: ignore[return-value]

    assert classify_q("Q?", classifier_fn=bad_classifier) == "OTHER"


def test_classify_q_heuristic_default_path() -> None:
    """The substring-match heuristic returns expected kinds without classifier_fn."""
    assert classify_q("What is wrong with X?") == "WRONG"
    assert classify_q("How will this implement?") == "METHOD"
    assert classify_q("Who reviews this?") == "STAKEHOLDER"
    assert classify_q("Naming convention?") == "STYLE"
    assert classify_q("What latency target?") == "PERF"
    assert classify_q("Random unrelated text") == "OTHER"


def test_all_kinds_constant_is_complete() -> None:
    """ALL_KINDS reflects the 6-kind taxonomy exactly."""
    assert {"WRONG", "METHOD", "STAKEHOLDER", "STYLE", "PERF", "OTHER"} == ALL_KINDS
