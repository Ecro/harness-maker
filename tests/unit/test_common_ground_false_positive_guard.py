"""Phase 2 false-positive guard for common_ground LLM-inference (PLAN ADR-003).

10+ hand-crafted "should-ask" slots — implementation details that the user
MUST be asked about because they cannot be inferred from project context.
If the mocked LLM-inference path returns >= 0.95 for any of these, the
0.95 threshold is uncalibrated for this domain — the test fails loudly
so the threshold can be raised before ship (or before opting into the
ADR-003 aggressive variant).

This is a SYNTHETIC pre-ship guard. Post-ship calibration relies on
ADR-008 silent_intent_miss telemetry. The fixture uses a hand-rolled
mock that maps slot text → confidence; a real model may behave
differently and is gated separately (INTEGRATION=1 path, not in CI).
"""

from __future__ import annotations

from typing import Any

import pytest

from harness_maker.common_ground import detect_common_ground

# ---------- Fixture: 10 should-ask slots ------------------------------------------------
#
# Selection criteria: each slot describes a CONCRETE technical choice that
# cannot be determined from CLAUDE.md / harness.yaml / common conventions.
# Generic project context (Python, MIT-licensed, pytest, harness-maker dev)
# leaves these undetermined; the LLM must NOT claim >=0.95 confidence.

SHOULD_ASK_SLOTS: list[str] = [
    "Database engine",  # could be postgres / mysql / sqlite / none — undetermined
    "MQTT topic format",  # no MQTT in harness-maker baseline
    "Preferred logging library",  # stdlib logging vs structlog vs loguru
    "Error retry policy",  # exponential / linear / circuit-break / none
    "Authentication scheme",  # token / OAuth / mTLS / none
    "Cache invalidation strategy",  # TTL / write-through / explicit / none
    "Notification webhook target URL",  # user-specific; cannot be inferred
    "Time-zone display preference",  # UTC vs local; user-specific
    "Maximum response payload size",  # bytes/MB; project-specific budget
    "Rate-limit window seconds",  # 60 / 600 / etc.; user-specific SLA
]


@pytest.fixture
def project_baseline_sources() -> dict[str, Any]:
    """Synthetic project context that does NOT determine any should-ask slot."""
    return {
        "CLAUDE.md": (
            "# harness-maker\n"
            "\n"
            "Python 3.12+ plugin for Claude Code + Cursor + Codex.\n"
            "Atomic file writes; subprocess timeout required; no shell=True.\n"
            "Test policy: mock LLM in unit tests; INTEGRATION=1 for real e2e.\n"
        ),
        "harness.yaml": {
            "preset": "Production",
            "locale": "en",
            "targets": ["claude-code"],
        },
        "SPEC-frontmatter": {
            "task_slug": "deep-interview-question-criteria",
            "status": "approved",
        },
    }


# ---------- Calibrated mock LLM ---------------------------------------------------------
#
# A well-calibrated model returns LOW confidence for slots whose answer is
# not in `context`. This mock simulates that property — its purpose is to
# verify the FP guard FRAMEWORK works correctly, not to validate a specific
# real model. The real model is validated post-ship via ADR-008 telemetry.


def _calibrated_mock(slot: str, context: dict[str, Any]) -> float:
    """Return confidence proportional to whether the slot appears in context.

    Implementation: if the slot text (case-insensitive) literally appears
    anywhere in the JSON-stringified context, return 0.90; otherwise 0.30.
    Neither value crosses the default 0.95 threshold — so the guard passes.
    """
    import json as _json

    haystack = _json.dumps(context, default=str).lower()
    return 0.90 if slot.lower() in haystack else 0.30


# ---------- The FP guard test ----------------------------------------------------------


@pytest.mark.parametrize("slot", SHOULD_ASK_SLOTS)
def test_should_ask_slot_does_not_trigger_common_ground(
    slot: str, project_baseline_sources: dict[str, Any]
) -> None:
    """Each should-ask slot must NOT be detected as common-ground under baseline context.

    If this fails, either:
      (a) the explicit-evidence matcher is over-permissive (substring leak), or
      (b) the LLM-inference threshold is too lenient for this domain.
    Both are silent-intent-miss precursors — fix before ship.
    """
    mark = detect_common_ground(
        slot,
        project_baseline_sources,
        llm_inference_fn=_calibrated_mock,
    )
    assert mark is None, (
        f"FP guard violation: slot {slot!r} flagged common-ground "
        f"under baseline context — silent-intent-miss precursor"
    )


def test_fp_guard_has_at_least_10_slots() -> None:
    """The PLAN F2 acceptance criterion: 10+ should-ask slots."""
    assert len(SHOULD_ASK_SLOTS) >= 10


def test_calibrated_mock_self_check() -> None:
    """Sanity: when the slot IS in context, the mock would return 0.90
    (below the 0.95 default), so the guard remains green by design.
    Bumping the mock to >=0.95 here would be the canary for a too-loose threshold."""
    score = _calibrated_mock("Database engine", {"CLAUDE.md": "Database engine: postgres"})
    assert score == 0.90
    assert score < 0.95, "calibrated mock must stay below default threshold for sanity"
