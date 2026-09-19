"""AC-010/AC-011 — a rendered template must not state a field contract the CLI rejects.

Two instances of one class were found in a single audit:

- `review.md.j2` claimed round-level numerics default to 0 while `wall_time_ms` was required
  with no default — and the *same paragraph* forbade interpolating it. The first emit of
  every round was rejected.
- `plan.md.j2` rendered `--barrier-index '<segment>'` with no statement that the value is an
  integer, while the CLI parses it with `type=int`. `execute.md.j2` already explained it.

A third instance makes this a `count:3` escalation. These tests are the floor.

A.4 (justified pass): `test_execute_barrier_index_guidance_is_unchanged` passes on the
unmodified template by design — a preservation guard for the stage that already explained the
type. Its RED positive sibling is `test_plan_barrier_index_documented_as_int`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from harness_maker.models import (
    InstrumentationConfig,
    InterviewAnswers,
    Preset,
    ProjectProfile,
    Target,
)
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize


def _rendered(tmp_path: Path, depth: str | None = None) -> dict[str, str]:
    # `stage_agent_ledger` defaults to False, and the `--barrier-index` guidance lives inside
    # that gate — rendering without it would make every assertion below vacuous by absence.
    answers = InterviewAnswers(
        preset=Preset.PRODUCTION,
        targets=[Target.CLAUDE_CODE],
        instrumentation=InstrumentationConfig(stage_agent_ledger=True),
    )
    if depth is not None:
        interview = dict(answers.interview)
        interview["comprehension"] = {**dict(interview.get("comprehension", {})), "depth": depth}
        answers = answers.model_copy(update={"interview": interview})
    blueprint = synthesize(ProjectProfile(), answers)
    render(blueprint, tmp_path, freeze_time=DEFAULT_FREEZE_TIME)
    base = tmp_path / "commands" / "hm"
    return {p.stem: p.read_text(encoding="utf-8") for p in base.glob("*.md")}


def _telemetry_paragraph(review_body: str) -> str:
    """Scope the assertion — an unrelated occurrence elsewhere must not decide this."""
    start = review_body.index("Round-level numeric fields")
    return review_body[start : start + 1400]


# --------------------------------------------------------------------------------------
# AC-010 — the review doc matches wall_time_ms optionality
# --------------------------------------------------------------------------------------


def test_review_doc_matches_wall_time_optionality(tmp_path: Path) -> None:
    para = _telemetry_paragraph(_rendered(tmp_path)["review"])
    assert "wall_time_ms" in para
    assert "optional" in para
    assert "null" in para


def test_review_doc_does_not_claim_wall_time_defaults_to_zero(tmp_path: Path) -> None:
    """The unscoped 'numerics default to 0' claim is what rejected the first emit."""
    para = _telemetry_paragraph(_rendered(tmp_path)["review"])
    idx = para.index("default to 0")
    # The exception must be stated in the same breath, not paragraphs later.
    assert "except" in para[idx : idx + 120].lower()
    assert "wall_time_ms" in para[idx : idx + 200]


def test_review_doc_keeps_the_never_send_zero_rule(tmp_path: Path) -> None:
    """Optional must not be read as 'send 0 instead' — 0 means measured-instantly."""
    para = _telemetry_paragraph(_rendered(tmp_path)["review"])
    assert "never `0`" in para or "never 0" in para


# --------------------------------------------------------------------------------------
# AC-011 — plan documents --barrier-index as an integer
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize("depth", [None, "minimal"], ids=["default", "minimal"])
def test_plan_barrier_index_documented_as_int(tmp_path: Path, depth: str | None) -> None:
    """Every depth: a CLI type fact is not explanatory prose (validator W3, salvage).

    The source gated this note on `depth != minimal` to keep a golden byte-identical; that
    golden's byte-identity was narrowed on 2026-08-15, and the gate left `minimal` users
    without the type — reopening AC-011 at that depth.
    """
    body = _rendered(tmp_path, depth)["plan"]
    idx = body.index("--barrier-index")
    window = body[idx : idx + 2500]
    assert "integer" in window, "the plan stage must say the segment is an integer"
    assert "type=int" in window, "name the enforcement, so the reason survives a rewrite"


def test_execute_barrier_index_guidance_is_unchanged(tmp_path: Path) -> None:
    """Regression guard: execute already explained this and must keep doing so."""
    body = _rendered(tmp_path)["execute"]
    assert "A.5 is its own barrier" in body
