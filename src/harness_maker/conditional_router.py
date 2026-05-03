"""Conditional Router (M6) — pick reviewers based on changed files.

Per architecture M6, when `harness.yaml.reviewers.routing == 'conditional'`,
the router maps changed-file path patterns to reviewer specialities so a
small change touches only the relevant reviewers (cheaper, faster).

Routing rules (path-substring match, case-insensitive):
- `.env`, `/auth/`, `/secret`            → security-reviewer
- `/perf/`, `benchmark`, `hot`           → performance-reviewer
- `.tsx`, `.jsx`, `/ui/`                 → ux-reviewer
- `thread`, `isr`, `worker`, `async`     → concurrency-reviewer
- (always)                               → code-reviewer

When `routing == 'always-all'` (or anything other than 'conditional'),
the function returns the preset reviewer list unchanged.
"""

from __future__ import annotations

from pathlib import Path

# Routing rule table — order is irrelevant since `selected` is a set.
_RULES: list[tuple[tuple[str, ...], str]] = [
    ((".env", "/auth/", "/secret"), "security-reviewer"),
    (("/perf/", "benchmark", "hot"), "performance-reviewer"),
    ((".tsx", ".jsx", "/ui/"), "ux-reviewer"),
    (("thread", "isr", "worker", "async"), "concurrency-reviewer"),
]


def route_reviewers(
    changed_files: list[Path],
    preset_reviewers: list[str],
    routing: str = "always-all",
) -> list[str]:
    """Return the subset of `preset_reviewers` that should review `changed_files`.

    Args:
        changed_files: paths (relative or absolute) of files in the diff
        preset_reviewers: the full reviewer list configured in harness.yaml
        routing: 'conditional' to apply path → reviewer rules; anything else
                 (incl. 'always-all') returns `preset_reviewers` unchanged.

    Returns:
        A list of reviewer names. Order matches `preset_reviewers` so callers
        get a stable iteration order. Always at least `['code-reviewer']`
        even if no rules match (so we never silently skip review).
    """
    if routing != "conditional":
        return list(preset_reviewers)

    selected: set[str] = {"code-reviewer"}  # always
    for f in changed_files:
        path = str(f).lower()
        for substrings, reviewer in _RULES:
            if any(s in path for s in substrings):
                selected.add(reviewer)

    # Filter through preset_reviewers to preserve preset ordering and to
    # honour the user's choice (don't invoke a reviewer the preset omits).
    filtered = [r for r in preset_reviewers if r in selected]
    return filtered or ["code-reviewer"]
