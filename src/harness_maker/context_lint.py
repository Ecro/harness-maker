"""Context Lint (Phase 10 Task 8.1) — flag verbose CLAUDE.md / agent / skill / workflow files.

Per spec, context bloat hurts model attention; we enforce per-asset-type line thresholds
that vary by Preset (Side: looser; Production: tightest signal-to-noise).

Scope decision (intentional, per Phase 10 Task 8.2):
This module is a STANDALONE callable. Renderer integration is deferred — the existing
snapshot tests assume byte-stable output; wiring lint warnings into the render path
risks destabilising those baselines. Phase 11 dogfood will exercise this module directly
via the context-linter SKILL or a CLI shim.

Lines are counted EXCLUDING YAML frontmatter (the leading `---\n…\n---\n` block) so
that frontmatter bookkeeping (provenance hash, metadata) does not inflate the count.
"""

from __future__ import annotations

from pathlib import Path

from harness_maker.models import Preset

# (asset_type, preset) → max body line count
THRESHOLDS: dict[tuple[str, str], int] = {
    ("CLAUDE.md", Preset.SIDE.value): 200,
    ("CLAUDE.md", Preset.PRODUCTION.value): 500,
    ("agent", Preset.SIDE.value): 100,
    ("agent", Preset.PRODUCTION.value): 200,
    ("skill", Preset.SIDE.value): 50,
    ("skill", Preset.PRODUCTION.value): 150,
    ("workflow", Preset.SIDE.value): 300,
    ("workflow", Preset.PRODUCTION.value): 600,
}


def _strip_frontmatter(text: str) -> str:
    """Remove leading `---\\n...\\n---\\n` YAML frontmatter block, if present."""
    if not text.startswith("---\n"):
        return text
    end = text.find("\n---\n", 4)
    if end == -1:
        return text
    return text[end + 5 :]


def _count_body_lines(text: str) -> int:
    body = _strip_frontmatter(text)
    if not body:
        return 0
    # Trailing newline shouldn't add a phantom line.
    if body.endswith("\n"):
        body = body[:-1]
    if not body:
        return 0
    return body.count("\n") + 1


def lint(file_path: Path, asset_type: str, preset: Preset) -> list[str]:
    """Return warnings for over-threshold files.

    Args:
        file_path: file to inspect (must exist).
        asset_type: one of "CLAUDE.md", "agent", "skill", "workflow", or "other".
            "other" is treated as no-limit (returns []).
        preset: Side or Production — selects the threshold band.

    Returns:
        List of human-readable warning strings. Empty list = no issues.
    """
    if asset_type == "other":
        return []
    key = (asset_type, preset.value)
    if key not in THRESHOLDS:
        return []
    limit = THRESHOLDS[key]
    text = file_path.read_text(encoding="utf-8", errors="replace")
    actual = _count_body_lines(text)
    if actual <= limit:
        return []
    excess = actual - limit
    return [
        f"{file_path}: {asset_type} body has {actual} lines "
        f"(>{limit} threshold for {preset.value} preset; "
        f"trim ~{excess} lines or split into a referenced doc)"
    ]
