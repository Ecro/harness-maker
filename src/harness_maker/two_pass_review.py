"""2-pass review engine — metadata redaction + rubric-only verdict (Phase 6).

Based on Phase 0 ablation results (PASS): 2-pass+redaction improves finding
precision from 53% to 100% on anchoring-prone diffs.

Pass 1: metadata (PR title, description, author) redacted. Reviewer evaluates
code quality using rubric only → returns finding list.
Pass 2: metadata restored. Reviewer provides contextual verdict and optional
explanation (only when requested).
"""

from __future__ import annotations

from typing import Any


def redact_metadata(
    diff_context: dict[str, Any],
) -> dict[str, Any]:
    """Remove anchoring metadata from review context for Pass 1.

    Redacts: pr_title, pr_description, author, commit_message.
    Preserves: diff, file paths, line numbers, SPEC/PLAN references.
    """
    redacted = dict(diff_context)
    for key in ("pr_title", "pr_description", "author", "commit_message"):
        if key in redacted:
            redacted[key] = "[REDACTED]"
    if "metadata" in redacted and isinstance(redacted["metadata"], dict):
        for key in ("title", "description", "author", "message"):
            if key in redacted["metadata"]:
                redacted["metadata"][key] = "[REDACTED]"
    return redacted


def restore_metadata(
    redacted_context: dict[str, Any],
    original_context: dict[str, Any],
) -> dict[str, Any]:
    """Restore original metadata for Pass 2."""
    restored = dict(redacted_context)
    for key in ("pr_title", "pr_description", "author", "commit_message"):
        if key in original_context:
            restored[key] = original_context[key]
    if "metadata" in original_context and isinstance(original_context["metadata"], dict):
        if "metadata" not in restored or not isinstance(restored.get("metadata"), dict):
            restored["metadata"] = {}
        for key in ("title", "description", "author", "message"):
            if key in original_context["metadata"]:
                restored["metadata"][key] = original_context["metadata"][key]
    return restored


def is_metadata_redacted(context: dict[str, Any]) -> bool:
    """Check if a context dict has been redacted."""
    for key in ("pr_title", "pr_description", "author", "commit_message"):
        if context.get(key) == "[REDACTED]":
            return True
    return False


def build_pass1_prompt(
    diff: str,
    rubric: str,
    redacted_context: dict[str, Any],
) -> str:
    """Build the Pass 1 prompt — rubric-only, no metadata anchoring."""
    return (
        "Review the following code changes using ONLY the rubric criteria below.\n"
        "Do NOT consider any metadata (PR title, description, author) — "
        "focus exclusively on code quality, correctness, and safety.\n\n"
        f"## Rubric\n{rubric}\n\n"
        f"## Diff\n```\n{diff}\n```\n\n"
        "Return findings as a JSON array of objects with: "
        "severity, file, line, summary, suggestion, reasoning."
    )


def build_pass2_prompt(
    diff: str,
    findings: list[dict[str, Any]],
    full_context: dict[str, Any],
    *,
    explanation_requested: bool = False,
) -> str:
    """Build the Pass 2 prompt — contextual verdict with full metadata."""
    findings_text = "\n".join(
        f"- [{f.get('severity', '?')}] {f.get('summary', '?')} "
        f"({f.get('file', '?')}:{f.get('line', '?')})"
        for f in findings
    )
    parts = [
        "You are reviewing with full context now.",
        f"PR Title: {full_context.get('pr_title', 'N/A')}",
        f"Description: {full_context.get('pr_description', 'N/A')}",
        f"Author: {full_context.get('author', 'N/A')}",
        "",
        f"## Pass 1 Findings\n{findings_text}",
        "",
        "Validate each finding against the full context. "
        "Remove any that are invalidated by the metadata context. "
        "Adjust severity if context changes the risk assessment.",
    ]
    if explanation_requested:
        parts.append(
            "\nFor each retained finding, provide a brief explanation "
            "of why it matters in the context of this PR."
        )
    else:
        parts.append(
            "\nReturn only the validated finding list without explanations."
        )
    return "\n".join(parts)


def merge_passes(
    pass1_findings: list[dict[str, Any]],
    pass2_findings: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Merge Pass 1 and Pass 2 findings.

    Pass 2 can: remove findings (invalidated by context), adjust severity,
    or add explanations. The merge uses Pass 2 as authoritative for retained
    findings.
    """
    if not pass2_findings:
        return pass1_findings

    pass2_keys = {
        f"{f.get('file', '')}:{f.get('line', 0)}" for f in pass2_findings
    }

    merged: list[dict[str, Any]] = []
    for f in pass2_findings:
        entry = dict(f)
        entry["pass"] = 2
        merged.append(entry)

    for f in pass1_findings:
        key = f"{f.get('file', '')}:{f.get('line', 0)}"
        if key not in pass2_keys:
            entry = dict(f)
            entry["pass"] = 1
            entry["status"] = "invalidated_by_context"
            merged.append(entry)

    return merged
