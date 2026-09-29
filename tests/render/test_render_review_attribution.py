"""SPEC-top-issues-2026-09 S6 (review half): the persisted payload carries the stamped `caused_by`.

Render-greps prove presence, not behaviour (CLAUDE.md checkpoint 2). What keeps these from being
decorative is that each one binds the two ends of a data path to the SAME token: a test that
only checked `review_churn attribute` appears before `persist-payload` would pass a template that
stamps one temp file and persists another — the green-module-dead-prose-wiring shape (count:7).

Phase A.4 justified pass: `test_single_owner_predicates_discriminate` is a positive control for the
negative predicate, and by construction it has no implementation to wait for.
"""

from __future__ import annotations

import re

import pytest

from ._top_issues_render import rendered, section, stage_bodies

_FIRES_ON_FIX = re.compile(r"\(b\)[^.]*`caused_by`[^.]*`fix-r")
_NONE_UNKNOWN_NEVER = re.compile(r"`none`[^.]*`unknown`[^.]*never fire")
_A_OR_B = re.compile(r"\(a\).*\*\*or\*\*.*\(b\)", re.S)
_B_SENTENCE = re.compile(r"\(b\)[^.]*\.")


def _arm_b_fires_only_on_fix(arm_b: str) -> bool:
    """Arm (b) fires on a `fix-r` stamp, `none`/`unknown` are named as never firing it, and it
    stays one arm of an (a)-or-(b) disjunction — a relation, not three words being present."""
    b_sentence = _B_SENTENCE.search(arm_b)
    return bool(
        b_sentence
        and "`none`" not in b_sentence.group(0)
        and "`unknown`" not in b_sentence.group(0)
        and _FIRES_ON_FIX.search(arm_b)
        and _NONE_UNKNOWN_NEVER.search(arm_b)
        and _A_OR_B.search(arm_b)
    )


def _file_arg(step34: str, command: str, flag: str) -> str:
    """The temp-file argument, normalised: both commands say `<the literal temp path>`."""
    line = next(ln for ln in step34.splitlines() if command in ln)
    m = re.search(rf"{re.escape(flag)} (<[^>]+>|\S+)", line)
    assert m, f"{flag} missing on {line!r}"
    return m.group(1)


@pytest.mark.parametrize(
    ("variant", "body"), stage_bodies("review", ledger=True), ids=["claude", "codex"]
)
def test_attribute_and_persist_share_file(variant: str, body: str) -> None:
    step34 = section(body, "### Step 3.4")
    assert "review_churn attribute" in step34, variant
    assert _file_arg(step34, "review_churn attribute", "--findings-file") == _file_arg(
        step34, "persist-payload", "--file"
    )
    assert step34.index("review_churn attribute") < step34.index("persist-payload")
    attr_line = next(ln for ln in step34.splitlines() if "review_churn attribute" in ln)
    for flag in ("--slug", "--run-id", "--round"):
        assert flag in attr_line, (variant, flag)


@pytest.mark.parametrize(("variant", "body"), stage_bodies("review"), ids=["claude", "codex"])
def test_caused_by_single_owner(variant: str, body: str) -> None:
    autofix_step1 = section(body, "1. **Merge and attribute.**", "\n2. **Group.**")
    assert "determine each one" not in autofix_step1, variant
    assert "caused_by" in autofix_step1
    assert "review_churn attribute" in autofix_step1

    # The REVIEW iteration record is emitted by the stage body — its grammar must match the stamp.
    assert "caused_by=#" not in body, variant
    assert "caused_by=fix-r" in body, variant

    skill = rendered(True)["skill:second-opinion-gate"]
    assert "caused_by=#" not in skill
    arm_b = section(skill, "**Two-arm batch trigger.**", "\n\n")
    # Every finding now carries a string, so "non-null" would fire arm (b) on `none`/`unknown`
    # too and remove the fast path. The firing condition must be the `fix-r` value itself.
    assert "non-null" not in arm_b
    assert _arm_b_fires_only_on_fix(arm_b), arm_b
    grammar = section(skill, "**`caused_by` grammar.**", "\n\n")
    assert "caused_by=fix-r" in grammar
    assert "caused_by=none" in grammar


def test_single_owner_predicates_discriminate() -> None:
    """The negative predicates must be false against text that still has the old owner.

    Without this, `'determine each one' not in step1` would pass a template whose step 1 was
    simply renamed — the assertion-invariant-over-named-dimension shape (count:22).
    """
    old = (
        "1. **Merge and attribute.** ... then determine each one's `caused_by` "
        "from the fix log.\n2. **Group.**"
    )
    assert "determine each one" in section(old, "1. **Merge and attribute.**", "\n2. **Group.**")

    fires_on_everything = (
        "Re-derive when **either** (a) two findings share a subsystem, **or** (b) any finding "
        "new this round has `caused_by` `fix-r1`, `none` or `unknown`."
    )
    assert not _arm_b_fires_only_on_fix(fires_on_everything)
    right = (
        "Re-derive when **either** (a) two findings share a subsystem, **or** (b) any finding "
        "new this round whose stamped `caused_by` is a `fix-r<N>` value. `none` and `unknown` "
        "never fire it."
    )
    assert _arm_b_fires_only_on_fix(right)
