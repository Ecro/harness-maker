"""Layer-2 LLM judge — evaluate file content against rubric YAMLs.

Each rubric file targets a file pattern (e.g., CLAUDE.md, agent prompts).
For every matching file we ship the rubric as the cached system prompt and
the file body as the per-call user prompt. The LLM returns a JSON verdict
per rubric: passed / failed + evidence + suggested fix.

The Anthropic SDK is wrapped behind ``JudgeClient`` so tests inject a fake
client without monkey-patching the SDK module-level.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, ValidationError

from harness_maker.rubric_loader import RubricFile

# Severity → weight contribution in the per-file score.
_SEVERITY_WEIGHTS: dict[str, int] = {"P0": 3, "P1": 2, "P2": 1}
_DEFAULT_WEIGHT = 1


class RubricVerdict(BaseModel):
    """One LLM judgment for a single rubric on a single file.

    `severity` is enriched from the rubric definition after parsing the LLM
    response — the model returns only the boolean verdict, the severity
    attaches deterministically from the rubric file.
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    rubric_id: str
    severity: str  # P0 | P1 | P2 (from the rubric definition)
    passed: bool
    evidence: str
    suggestion: str | None  # tailored fix when passed=False; None when passed=True


class JudgeResult(BaseModel):
    """LLM judge output for one target file against one rubric file."""

    model_config = ConfigDict(strict=True, extra="forbid")

    file: str
    dimension: str
    score: int  # 0-100, severity-weighted pass rate; 50 when error blocks judgment
    verdicts: list[RubricVerdict]
    error: str | None


class JudgeClient(Protocol):
    """Minimal LLM client interface — accepts cached system + user prompt."""

    def judge(self, system: str, user: str, model: str) -> str: ...


class AnthropicJudgeClient:
    """Production ``JudgeClient`` backed by ``anthropic.Anthropic``.

    The system prompt (rubric) is wrapped with ``cache_control`` so judging
    multiple files against the same rubric pays the prefix cost only once
    every TTL (5 min default). User prompt (file body) is uncached.
    """

    def __init__(self, *, api_key: str | None = None) -> None:
        from anthropic import Anthropic  # local import to keep module light

        self._client = Anthropic(api_key=api_key) if api_key else Anthropic()

    def judge(self, system: str, user: str, model: str) -> str:
        msg = self._client.messages.create(
            model=model,
            max_tokens=4096,
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": user}],
        )
        parts: list[str] = []
        for block in msg.content:
            text = getattr(block, "text", None)
            if isinstance(text, str):
                parts.append(text)
        return "".join(parts)


# ── prompt construction ────────────────────────────────────────────────────


def _build_system_prompt(rubric: RubricFile) -> str:
    rubric_lines = [
        f"- id: {r.id}\n  severity: {r.severity}\n  check: {r.description}" for r in rubric.rubrics
    ]
    return f"""You evaluate files against a structured AI-readiness rubric.

Dimension: {rubric.dimension}
Target file pattern: {rubric.target}

Rubrics to evaluate (one verdict required per rubric):
{chr(10).join(rubric_lines)}

For each rubric:
- Decide whether the file PASSES or FAILS the check.
- Provide concrete evidence — quote or reference specific lines/sections.
- If FAIL, provide a suggestion tailored to THIS file (not generic).
- If PASS, suggestion = null.

Output ONLY a JSON object in this schema (no prose, no markdown fences):
{{
  "verdicts": [
    {{"rubric_id": "<id>", "passed": <bool>, "evidence": "<text>", "suggestion": <string-or-null>}},
    ...
  ]
}}

Include exactly one verdict per rubric in the order listed above."""


def _build_user_prompt(file_path: Path, content: str) -> str:
    return f"""Evaluate this file against the rubrics:

File path: {file_path}

--- BEGIN FILE ---
{content}
--- END FILE ---

Return JSON only."""


# ── response parsing ───────────────────────────────────────────────────────


def _strip_markdown_fence(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        first_nl = stripped.find("\n")
        if first_nl != -1:
            stripped = stripped[first_nl + 1 :]
        if stripped.endswith("```"):
            stripped = stripped[:-3]
    return stripped.strip()


def _parse_response(raw: str, rubric: RubricFile) -> tuple[list[RubricVerdict], str | None]:
    """Parse LLM raw response into validated verdicts.

    Returns (verdicts, error_message_or_none). Best-effort: missing rubrics
    default to passed=False with an explanatory evidence string.
    """
    body = _strip_markdown_fence(raw)
    try:
        parsed: Any = json.loads(body)
    except (json.JSONDecodeError, ValueError) as e:
        return [], f"LLM returned non-JSON: {e}"
    if not isinstance(parsed, dict) or "verdicts" not in parsed:
        return [], "LLM response missing 'verdicts' key"
    raw_verdicts = parsed["verdicts"]
    if not isinstance(raw_verdicts, list):
        return [], "LLM 'verdicts' is not a list"

    severity_by_id = {r.id: r.severity for r in rubric.rubrics}
    by_id: dict[str, RubricVerdict] = {}
    for item in raw_verdicts:
        if not isinstance(item, dict):
            continue
        # The LLM does not return severity — inject it from the rubric def
        # before validating so users always see severity on the verdict.
        rid = item.get("rubric_id")
        if isinstance(rid, str) and rid in severity_by_id:
            enriched = {**item, "severity": severity_by_id[rid]}
        else:
            enriched = item
        try:
            v = RubricVerdict.model_validate(enriched)
        except ValidationError:
            continue
        by_id[v.rubric_id] = v

    # Backfill any missing rubric with a deterministic placeholder so the
    # caller always sees one verdict per rubric.
    out: list[RubricVerdict] = []
    for r in rubric.rubrics:
        if r.id in by_id:
            out.append(by_id[r.id])
        else:
            out.append(
                RubricVerdict(
                    rubric_id=r.id,
                    severity=r.severity,
                    passed=False,
                    evidence="LLM did not return a verdict for this rubric",
                    suggestion=r.action,
                )
            )
    return out, None


# ── score calculation ──────────────────────────────────────────────────────


def _weighted_score(verdicts: list[RubricVerdict]) -> int:
    """Severity-weighted pass rate. Verdicts already carry their severity."""
    total_weight = 0
    earned = 0
    for v in verdicts:
        w = _SEVERITY_WEIGHTS.get(v.severity, _DEFAULT_WEIGHT)
        total_weight += w
        if v.passed:
            earned += w
    if total_weight == 0:
        return 0
    return round(100 * earned / total_weight)


# ── public API ─────────────────────────────────────────────────────────────


def judge_file(
    file_path: Path,
    rubric: RubricFile,
    *,
    client: JudgeClient,
    model: str = "claude-sonnet-4-6",
) -> JudgeResult:
    """Judge one file against a rubric. Returns a result regardless of failure mode."""
    if not file_path.is_file():
        return JudgeResult(
            file=str(file_path),
            dimension=rubric.dimension,
            score=50,
            verdicts=[],
            error=f"File does not exist: {file_path}",
        )
    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return JudgeResult(
            file=str(file_path),
            dimension=rubric.dimension,
            score=50,
            verdicts=[],
            error=f"Could not read file: {e}",
        )

    system = _build_system_prompt(rubric)
    user = _build_user_prompt(file_path, content)
    try:
        raw = client.judge(system, user, model)
    except Exception as e:  # noqa: BLE001 — judge must not crash
        return JudgeResult(
            file=str(file_path),
            dimension=rubric.dimension,
            score=50,
            verdicts=[],
            error=f"LLM call failed: {type(e).__name__}: {e}",
        )

    verdicts, parse_error = _parse_response(raw, rubric)
    if parse_error and not verdicts:
        return JudgeResult(
            file=str(file_path),
            dimension=rubric.dimension,
            score=50,
            verdicts=[],
            error=parse_error,
        )
    score = _weighted_score(verdicts)
    return JudgeResult(
        file=str(file_path),
        dimension=rubric.dimension,
        score=score,
        verdicts=verdicts,
        error=parse_error,
    )


def _expand_target(project_dir: Path, target: str) -> list[Path]:
    """Resolve a rubric target pattern to concrete file paths under project_dir."""
    pattern = target.removeprefix("./")
    if "*" in pattern or "?" in pattern:
        return sorted(project_dir.glob(pattern))
    p = project_dir / pattern
    return [p] if p.is_file() else []


def judge_target(
    project_dir: Path,
    rubric: RubricFile,
    *,
    client: JudgeClient,
    model: str = "claude-sonnet-4-6",
) -> list[JudgeResult]:
    """Judge every file matching rubric.target under project_dir.

    Glob expansion: rubric.target like ``.claude/agents/*.md`` matches all
    agent files. A non-glob target (``CLAUDE.md``) yields zero or one file.
    """
    files = _expand_target(project_dir, rubric.target)
    return [judge_file(f, rubric, client=client, model=model) for f in files]
