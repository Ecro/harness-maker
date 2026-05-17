"""Phase 1 W-11 (R5): lint — no raw Claude concrete-ID strings in templates.

ADR-003 R5: the alias → concrete-ID mapping lives in CURSOR_MODEL_IDS only.
Templates render concrete IDs via {{ cursor_model }} context variable.

Scope per R5 W-11: assignment-only patterns. Prose mentions like
"this agent uses claude-3-5-sonnet for X" are intentionally NOT matched.
"""

import re
from pathlib import Path

TEMPLATES_DIR = (
    Path(__file__).resolve().parents[2] / "src" / "harness_maker" / "templates"
)

# Each pattern targets a position where a literal concrete ID would actually
# affect rendered output. Comments / prose / examples are not matched.
ASSIGNMENT_PATTERNS: list[tuple[str, str]] = [
    # YAML / Cursor MDC frontmatter: `model: claude-X-Y-family`
    (r"^\s*model:\s+claude-\d+-\d+-\w+\s*$", "YAML/MDC model:"),
    # JSON object: `"model": "claude-X-Y-family"`
    (r'"model"\s*:\s*"claude-\d+-\d+-\w+"', "JSON model field"),
    # TOML key: `model = "claude-X-Y-family"`
    (r'^\s*model\s*=\s*"claude-\d+-\d+-\w+"\s*$', "TOML model ="),
]


def _scan_template(path: Path) -> list[tuple[int, str, str]]:
    """Return [(line_no, pattern_name, matched_line)] for any matches."""
    hits: list[tuple[int, str, str]] = []
    text = path.read_text(encoding="utf-8")
    for line_no, line in enumerate(text.splitlines(), start=1):
        for pattern, name in ASSIGNMENT_PATTERNS:
            if re.search(pattern, line):
                hits.append((line_no, name, line.strip()))
                break  # one match per line is enough
    return hits


def test_no_raw_cursor_model_ids_in_templates() -> None:
    """No raw concrete Claude IDs in assignment positions inside .j2 templates.

    Raw IDs must live in presets.CURSOR_MODEL_IDS and reach templates via
    {{ cursor_model }} render context.
    """
    violations: list[str] = []
    for path in TEMPLATES_DIR.rglob("*.j2"):
        hits = _scan_template(path)
        if hits:
            rel = path.relative_to(TEMPLATES_DIR)
            for line_no, name, line in hits:
                violations.append(f"{rel}:{line_no} [{name}] {line}")
    assert not violations, (
        "Raw Claude concrete-ID strings found in templates "
        "(should reference presets.CURSOR_MODEL_IDS via {{ cursor_model }}):\n"
        + "\n".join(violations)
    )


def test_lint_patterns_match_canonical_examples() -> None:
    """Positive control: the patterns actually match the strings we care about."""
    # YAML/MDC
    assert re.search(ASSIGNMENT_PATTERNS[0][0], "model: claude-4-7-opus")
    # JSON
    assert re.search(ASSIGNMENT_PATTERNS[1][0], '"model": "claude-4-6-sonnet"')
    # TOML
    assert re.search(ASSIGNMENT_PATTERNS[2][0], 'model = "claude-4-5-haiku"')


def test_lint_patterns_do_not_match_prose() -> None:
    """Negative control: prose mentions are NOT flagged."""
    prose_lines = [
        "This agent invokes claude-3-5-sonnet for cheap summarization.",
        "# Comment: claude-4-6-sonnet was deprecated in 2026.",
        '"description": "uses claude-4-7-opus when reasoning is needed",',
    ]
    for line in prose_lines:
        for pattern, _name in ASSIGNMENT_PATTERNS:
            assert not re.search(pattern, line), (
                f"Prose unexpectedly matched {pattern!r}: {line!r}"
            )
