"""Tests for 2-pass review engine (Phase 6)."""

from __future__ import annotations

from harness_maker.two_pass_review import (
    build_pass1_prompt,
    build_pass2_prompt,
    is_metadata_redacted,
    merge_passes,
    redact_metadata,
    restore_metadata,
)


def test_redact_metadata_masks_pr_fields() -> None:
    context = {
        "pr_title": "feat: add auth",
        "pr_description": "Implements OAuth2 flow",
        "author": "dev",
        "diff": "--- a/file\n+++ b/file\n",
    }
    redacted = redact_metadata(context)
    assert redacted["pr_title"] == "[REDACTED]"
    assert redacted["pr_description"] == "[REDACTED]"
    assert redacted["author"] == "[REDACTED]"
    assert redacted["diff"] == context["diff"]


def test_redact_metadata_nested() -> None:
    context = {
        "metadata": {
            "title": "some title",
            "description": "some desc",
            "author": "me",
        },
        "diff": "...",
    }
    redacted = redact_metadata(context)
    assert redacted["metadata"]["title"] == "[REDACTED]"
    assert redacted["metadata"]["description"] == "[REDACTED]"


def test_restore_metadata_recovers_original() -> None:
    original = {
        "pr_title": "feat: add auth",
        "pr_description": "Implements OAuth2",
        "author": "dev",
    }
    redacted = redact_metadata(original)
    restored = restore_metadata(redacted, original)
    assert restored["pr_title"] == "feat: add auth"
    assert restored["pr_description"] == "Implements OAuth2"
    assert restored["author"] == "dev"


def test_is_metadata_redacted_true() -> None:
    context = {"pr_title": "[REDACTED]", "diff": "..."}
    assert is_metadata_redacted(context) is True


def test_is_metadata_redacted_false() -> None:
    context = {"pr_title": "feat: something", "diff": "..."}
    assert is_metadata_redacted(context) is False


def test_build_pass1_prompt_contains_rubric_and_no_metadata() -> None:
    prompt = build_pass1_prompt(
        diff="--- a/x.py\n+++ b/x.py\n",
        rubric="Check for correctness, safety, style",
        redacted_context={"pr_title": "[REDACTED]"},
    )
    assert "rubric" in prompt.lower()
    assert "Do NOT consider any metadata" in prompt
    assert "x.py" in prompt


def test_build_pass2_prompt_includes_metadata() -> None:
    findings = [{"severity": "P0", "summary": "Bug", "file": "x.py", "line": 10}]
    context = {"pr_title": "fix: race condition", "pr_description": "Fix race", "author": "dev"}
    prompt = build_pass2_prompt(
        diff="...",
        findings=findings,
        full_context=context,
    )
    assert "fix: race condition" in prompt
    assert "Bug" in prompt


def test_build_pass2_conditional_explanation() -> None:
    findings = [{"severity": "P1", "summary": "Issue", "file": "y.py", "line": 5}]
    context = {"pr_title": "test"}

    without_exp = build_pass2_prompt("", findings, context, explanation_requested=False)
    assert "without explanations" in without_exp

    with_exp = build_pass2_prompt("", findings, context, explanation_requested=True)
    assert "provide a brief explanation" in with_exp


def test_merge_passes_pass2_authoritative() -> None:
    """CP10 fix: Pass 2 is authoritative — Pass 1 findings absent from Pass 2
    are invalidated by context and DROPPED from the merged result.
    Earlier behavior re-surfaced them with status=invalidated_by_context,
    which defeated the design intent when callers forgot to filter."""
    pass1 = [
        {"file": "a.py", "line": 10, "severity": "P0", "summary": "Issue A"},
        {"file": "b.py", "line": 20, "severity": "P1", "summary": "Issue B"},
    ]
    pass2 = [
        {"file": "a.py", "line": 10, "severity": "P1", "summary": "Issue A (adjusted)"},
    ]
    merged = merge_passes(pass1, pass2)
    assert len(merged) == 1
    assert merged[0]["severity"] == "P1"
    assert merged[0]["file"] == "a.py"
    assert merged[0]["pass"] == 2
    assert all(f.get("status") != "invalidated_by_context" for f in merged), (
        "invalidated findings must NOT appear in merged result (CP10)"
    )


def test_merge_passes_empty_pass2_keeps_pass1() -> None:
    pass1 = [{"file": "x.py", "line": 1, "severity": "P0", "summary": "X"}]
    merged = merge_passes(pass1, [])
    assert len(merged) == 1
    assert merged[0]["summary"] == "X"
