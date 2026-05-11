"""Phase A1 structural gate: verifier agent permissions + reduce-only invariant.

PLAN-llm-code-review-2026 ADR-002 requires the verifier role to be read-only
and strictly reduce-only (no new findings introduced). These assertions run
on the source template so the gate doesn't depend on rendering.
"""

from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
VERIFIER_FM = REPO_ROOT / "src/harness_maker/templates/agents/code-verifier.md.j2"
VERIFIER_BODY = REPO_ROOT / "src/harness_maker/templates/agents/code-verifier_body.md.j2"

# Mirror code-reviewer deny set — interpreter denies close the
# `Bash(python -c "...")` escape per REVIEW M7 (CLAUDE.md §보안).
REQUIRED_DENIES = {
    "Write(*)",
    "Edit(*)",
    "Bash(rm:*)",
    "Bash(curl:*)",
    "Bash(npm:*)",
    "Bash(eval *)",
    "Bash(python:*)",
    "Bash(node:*)",
    "Bash(sh:*)",
    "Bash(bash:*)",
}

REQUIRED_ALLOWS = {
    "Read(*)",
    "Grep(*)",
    "Glob(*)",
}


def _parse_frontmatter(path: Path) -> dict[str, object]:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), f"missing frontmatter: {path}"
    end = text.find("\n---\n", 4)
    assert end != -1, f"unterminated frontmatter: {path}"
    return yaml.safe_load(text[4:end]) or {}


def test_verifier_template_exists() -> None:
    assert VERIFIER_FM.is_file(), f"missing verifier template: {VERIFIER_FM}"
    assert VERIFIER_BODY.is_file(), f"missing verifier body partial: {VERIFIER_BODY}"


def test_verifier_frontmatter_is_read_only() -> None:
    fm = _parse_frontmatter(VERIFIER_FM)
    perms = fm.get("permissions")
    assert isinstance(perms, dict), "permissions block missing"
    allow = set(perms.get("allow") or [])
    deny = set(perms.get("deny") or [])
    missing_denies = REQUIRED_DENIES - deny
    assert not missing_denies, f"verifier missing required denies: {sorted(missing_denies)}"
    missing_allows = REQUIRED_ALLOWS - allow
    assert not missing_allows, f"verifier missing required allows: {sorted(missing_allows)}"
    # No Write/Edit anywhere in allow — reduce-only is structural.
    assert not any(p.startswith(("Write(", "Edit(")) for p in allow), (
        "verifier allow set must not include any Write/Edit grant"
    )


def test_verifier_body_contains_no_introduction_invariant() -> None:
    """Reduce-only invariant must be literal in the prompt body (ADR-002)."""
    body = VERIFIER_BODY.read_text(encoding="utf-8")
    assert "MUST NOT introduce" in body, (
        "verifier body missing reduce-only invariant 'MUST NOT introduce findings'"
    )
    # Reject paraphrasing that loses the strict-subset guarantee — explicit
    # mention of the input set keeps the verifier role unambiguous.
    assert "pass1_findings" in body or "Pass 1 findings" in body, (
        "verifier body must reference its input set (pass1_findings / Pass 1 findings)"
    )


def test_verifier_registered_in_synthesize() -> None:
    """Agent must be wired into the synthesizer's catalog or rendered output skips it."""
    src = (REPO_ROOT / "src/harness_maker/synthesize.py").read_text(encoding="utf-8")
    assert '"code-verifier"' in src, (
        "code-verifier missing from synthesize._ALL_AGENTS catalog"
    )
