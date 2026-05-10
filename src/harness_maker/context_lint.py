"""Context Lint — flag verbose files and context window overuse.

Per spec, context bloat hurts model attention; we enforce per-asset-type line thresholds
that vary by Preset (Side: looser; Production: tightest signal-to-noise).

Phase 1 addition: window % hard-cap warning when context usage exceeds 40%.

Lines are counted EXCLUDING YAML frontmatter (the leading `---\\n…\\n---\\n` block) so
that frontmatter bookkeeping (provenance hash, metadata) does not inflate the count.
"""

from __future__ import annotations

from pathlib import Path

from harness_maker.models import Preset

MODEL_CONTEXT_WINDOWS: dict[str, int] = {
    "opus": 200_000,
    "sonnet": 200_000,
    "haiku": 200_000,
}
_DEFAULT_WINDOW = 200_000
_WINDOW_WARN_THRESHOLD = 0.40

# (asset_type, preset) → max body line count
THRESHOLDS: dict[tuple[str, str], int] = {
    ("CLAUDE.md", Preset.SIDE.value): 200,
    ("CLAUDE.md", Preset.PRODUCTION.value): 500,
    # AGENTS.md is the Codex equivalent of CLAUDE.md — same parity thresholds.
    ("AGENTS.md", Preset.SIDE.value): 200,
    ("AGENTS.md", Preset.PRODUCTION.value): 500,
    ("agent", Preset.SIDE.value): 100,
    ("agent", Preset.PRODUCTION.value): 200,
    ("skill", Preset.SIDE.value): 50,
    ("skill", Preset.PRODUCTION.value): 150,
    ("workflow", Preset.SIDE.value): 300,
    ("workflow", Preset.PRODUCTION.value): 600,
}


def _strip_frontmatter(text: str) -> str:
    """Remove provenance header before counting body lines.

    Handles two formats:
    - YAML frontmatter ``---\\n...\\n---\\n`` (agents, skills, commands, …)
    - HTML metadata comment ``<!-- harness-maker: ... -->\\n`` (AGENTS.md)
    """
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end != -1:
            return text[end + 5 :]
    if text.startswith("<!-- harness-maker:"):
        newline = text.find("\n")
        if newline != -1:
            return text[newline + 1 :]
    return text


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


_MCP_SERVER_WARN_THRESHOLD = 6


def lint_mcp_server_count(
    server_count: int,
    threshold: int = _MCP_SERVER_WARN_THRESHOLD,
) -> list[str]:
    """Warn when the number of MCP servers exceeds the threshold.

    High MCP server counts inflate context with tool descriptors,
    reducing useful context budget.
    """
    if server_count <= threshold:
        return []
    return [
        f"MCP server count ({server_count}) exceeds recommended "
        f"maximum ({threshold}). Each server adds tool descriptors "
        f"to the context window. Consider disabling unused servers."
    ]


def lint_window_usage(
    total_tokens: int,
    model: str = "sonnet",
    threshold: float = _WINDOW_WARN_THRESHOLD,
) -> list[str]:
    """Warn when context window usage exceeds the threshold (default 40%)."""
    m = model.lower()
    window = _DEFAULT_WINDOW
    for key, val in MODEL_CONTEXT_WINDOWS.items():
        if key in m:
            window = val
            break
    usage_pct = total_tokens / window if window > 0 else 0.0
    if usage_pct <= threshold:
        return []
    return [
        f"Context window {usage_pct:.0%} used ({total_tokens:,}/{window:,} tokens) "
        f"— exceeds {threshold:.0%} threshold. Consider compacting context or "
        f"splitting into a new session."
    ]
