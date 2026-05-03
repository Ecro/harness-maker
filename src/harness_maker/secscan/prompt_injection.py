"""Prompt-injection gate — flag hidden or suspicious instruction patterns in text."""

from __future__ import annotations

import re

from harness_maker.models import Finding

# Zero-width / bidi control characters often used to hide prompt instructions.
_ZERO_WIDTH = re.compile(r"[​-‏‪-‮⁦-⁩﻿]")

_IC = re.IGNORECASE
_ML = re.MULTILINE

# High-confidence injection phrases.
_HIGH_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "ignore_previous",
        re.compile(r"\bignore\s+(?:all\s+)?(?:previous|prior|above)\b", _IC),
    ),
    (
        "system_role_override",
        re.compile(r"^\s*system\s*:\s*", _IC | _ML),
    ),
    (
        "disregard_instructions",
        re.compile(r"\bdisregard\s+(?:the\s+)?(?:above|previous)\b", _IC),
    ),
    (
        "new_instructions",
        re.compile(
            r"\b(?:here are|these are)\s+(?:your\s+)?new\s+instructions\b",
            _IC,
        ),
    ),
    (
        "act_as_jailbreak",
        re.compile(
            r"\b(?:you are now|act as)\s+(?:DAN|an unrestricted|jailbroken)\b",
            _IC,
        ),
    ),
]

# Soft / medium-confidence signals.
_MEDIUM_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("base64_block", re.compile(r"(?:[A-Za-z0-9+/]{40,}={0,2})")),
    ("role_assistant", re.compile(r"^\s*assistant\s*:\s*", _IC | _ML)),
]


def scan(text: str) -> list[Finding]:
    """Return findings for prompt-injection signals in ``text``."""
    findings: list[Finding] = []
    if not text:
        return findings

    # Zero-width characters — high severity (almost always intentional hiding).
    for m in _ZERO_WIDTH.finditer(text):
        line_no = text.count("\n", 0, m.start()) + 1
        findings.append(
            Finding(
                severity="high",
                category="prompt_injection",
                file="",
                line=line_no,
                evidence=f"zero-width char U+{ord(m.group(0)):04X}",
                fix="Strip zero-width / bidi control characters before passing text to LLMs.",
            ),
        )

    for category, pattern in _HIGH_PATTERNS:
        for m in pattern.finditer(text):
            line_no = text.count("\n", 0, m.start()) + 1
            evidence = m.group(0)
            if len(evidence) > 80:
                evidence = evidence[:80] + "..."
            findings.append(
                Finding(
                    severity="high",
                    category="prompt_injection",
                    file="",
                    line=line_no,
                    evidence=f"{category}: {evidence}",
                    fix="Sanitize or sandbox user-supplied text before LLM injection.",
                ),
            )

    for category, pattern in _MEDIUM_PATTERNS:
        for m in pattern.finditer(text):
            line_no = text.count("\n", 0, m.start()) + 1
            evidence = m.group(0)
            if len(evidence) > 80:
                evidence = evidence[:80] + "..."
            findings.append(
                Finding(
                    severity="medium",
                    category="prompt_injection",
                    file="",
                    line=line_no,
                    evidence=f"{category}: {evidence}",
                    fix="Investigate suspicious content; consider stripping or escaping.",
                ),
            )

    return findings
