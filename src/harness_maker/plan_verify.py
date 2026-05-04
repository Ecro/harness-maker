"""Deep PLAN-fulfillment verification — LLM judges every PLAN item against a diff.

Replaces the trivial ``grep -E "^- \\[ \\]" PLAN-*.md`` check that only ensures
boxes are ticked. The LLM reads the PLAN body + the staged/applied git diff
and rules each PLAN item ``fulfilled`` or not, with cited evidence
(file:line references) drawn from the diff.

Failure policy: hard. The /hm:verify gate blocks completion when any PLAN
item fails OR when the LLM is unreachable — by design, deferring to a
shallower fallback would defeat the gate. The CLI surfaces the LLM error
verbatim so the user can rerun once the API is reachable.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, ValidationError

from harness_maker.llm_judge import JudgeClient

_DIFF_CHAR_CAP = 32_000  # truncate huge diffs; LLM context budget guard


class PlanVerifyError(Exception):
    """Raised when the LLM is unreachable or returns unusable output.

    The /hm:verify gate must propagate this — there is no graceful fallback
    that would keep the gate meaningful.
    """


class PlanItemVerdict(BaseModel):
    """Per-item LLM ruling."""

    model_config = ConfigDict(strict=True, extra="forbid")

    text: str  # the PLAN line under judgment
    fulfilled: bool
    evidence: str  # file:line refs from the diff, or "-" if none
    reason: str  # one-sentence explanation


class PlanVerification(BaseModel):
    """Full verdict for one PLAN file against one diff snapshot."""

    model_config = ConfigDict(strict=True, extra="forbid")

    plan_path: str
    items: list[PlanItemVerdict]
    overall_pass: bool


# ── prompt construction ────────────────────────────────────────────────────


_SYSTEM_PROMPT = """You verify whether each acceptance criterion in a coding \
PLAN was actually fulfilled by a git diff.

For every PLAN item (typically lines starting with `- [ ]` or `- [x]`,
phases, exit criteria, or numbered acceptance lines), judge:
  - fulfilled: true | false
  - evidence: short reference to the specific lines/files in the diff that
    satisfy this item (e.g., `src/foo.py:42-58`). Use "-" if none.
  - reason: one sentence justifying the judgment.

Treat a ticked checkbox alone as INSUFFICIENT — only mark fulfilled when the
diff contains code/test/doc changes that genuinely implement the item.

Output JSON ONLY in this exact schema (no prose, no markdown fences):
{
  "items": [
    {"text": "<PLAN line>", "fulfilled": <bool>, "evidence": "<text>", "reason": "<text>"}
  ],
  "overall_pass": <bool>
}

`overall_pass` is true iff EVERY required PLAN item is fulfilled."""


def _build_user_prompt(plan_text: str, diff_text: str) -> str:
    truncated = diff_text[:_DIFF_CHAR_CAP]
    return f"""--- BEGIN PLAN ---
{plan_text}
--- END PLAN ---

--- BEGIN DIFF ---
{truncated}
--- END DIFF ---

Return JSON only."""


# ── response parsing ───────────────────────────────────────────────────────


def _strip_markdown_fence(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        nl = stripped.find("\n")
        if nl != -1:
            stripped = stripped[nl + 1 :]
        if stripped.endswith("```"):
            stripped = stripped[:-3]
    return stripped.strip()


def _parse_response(raw: str, plan_path: Path) -> PlanVerification:
    body = _strip_markdown_fence(raw)
    try:
        data = json.loads(body)
    except (json.JSONDecodeError, ValueError) as e:
        msg = f"LLM returned non-JSON: {e}"
        raise PlanVerifyError(msg) from e
    if not isinstance(data, dict) or "items" not in data:
        msg = "LLM response missing 'items' key"
        raise PlanVerifyError(msg)
    raw_items = data.get("items")
    if not isinstance(raw_items, list):
        msg = "LLM 'items' is not a list"
        raise PlanVerifyError(msg)

    items: list[PlanItemVerdict] = []
    for entry in raw_items:
        if not isinstance(entry, dict):
            continue
        try:
            items.append(PlanItemVerdict.model_validate(entry))
        except ValidationError as e:
            msg = f"LLM item failed validation: {e}"
            raise PlanVerifyError(msg) from e

    overall_pass = bool(data.get("overall_pass", False))
    if items and overall_pass and any(not item.fulfilled for item in items):
        # Defensive: model said pass but at least one item failed → distrust it.
        overall_pass = False
    return PlanVerification(
        plan_path=str(plan_path),
        items=items,
        overall_pass=overall_pass,
    )


# ── public API ─────────────────────────────────────────────────────────────


def verify_plan(
    plan_path: Path,
    diff_text: str,
    *,
    client: JudgeClient,
    model: str = "claude-sonnet-4-6",
) -> PlanVerification:
    """LLM-judge whether ``diff_text`` actually fulfills every item in ``plan_path``.

    Raises:
        PlanVerifyError: when the PLAN is missing, the LLM call fails, or the
            response cannot be parsed. Callers must propagate the error — no
            graceful fallback is meaningful here.
    """
    if not plan_path.is_file():
        msg = f"PLAN file not found: {plan_path}"
        raise PlanVerifyError(msg)
    try:
        plan_text = plan_path.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        msg = f"Could not read PLAN: {e}"
        raise PlanVerifyError(msg) from e

    user = _build_user_prompt(plan_text, diff_text)
    try:
        raw = client.judge(_SYSTEM_PROMPT, user, model)
    except Exception as e:  # noqa: BLE001 — propagate as PlanVerifyError
        msg = f"LLM call failed: {type(e).__name__}: {e}"
        raise PlanVerifyError(msg) from e

    return _parse_response(raw, plan_path)
