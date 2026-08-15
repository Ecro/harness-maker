"""Conditional Router (M6) — pick reviewers based on changed files.

Per architecture M6, when `harness.yaml.reviewers.routing == 'conditional'`,
the router maps changed-file path patterns to reviewer specialities so a
small change touches only the relevant reviewers (cheaper, faster).

Two paths:
- ``route_reviewers`` (path-rule based) — fast, deterministic, no LLM.
- ``route_with_llm`` (diff-aware) — reads the actual diff and picks
  reviewers by semantic intent. Catches cases the path rules miss
  (e.g., a ``.py`` file that introduces concurrency primitives).

The LLM router falls back to the rule-based router on any transport error.
"""

from __future__ import annotations

import json
from pathlib import Path

from harness_maker.llm_judge import JudgeClient

#: The declared failure space (SPEC AC-001). Exactly five, fixed. Every consumer — the
#: coverage CLI, the rendered gate, the report — reads this one constant, so a lens cannot
#: be half-added.
#:
#: These are failure-mode-shaped, not agent-shaped: `REVIEWER_SCOPES` below is the older
#: agent axis and is deliberately NOT the same set. Two of these five have no reviewer agent
#: at all, which is the gap the declaration exists to make visible.
MANDATORY_LENSES: tuple[str, ...] = (
    "correctness",
    "failure",
    "concurrency",
    "security",
    "tests",
)

#: Reviewers outside the declared space. `route_reviewers` may add or drop THESE and nothing
#: else — a mandatory lens is never routed away, because SPEC AC-003 makes incomplete
#: coverage block approval and a routed-away lens would make every conditional review
#: unapprovable. Mirrored in the harness.yaml reviewer-routing comment (AC-002).
OPTIONAL_REVIEWERS: frozenset[str] = frozenset({"ux-reviewer", "performance-reviewer"})

REVIEWER_SCOPES: dict[str, list[str]] = {
    "code-reviewer": ["code", "design", "correctness"],
    "security-reviewer": ["security", "auth", "permissions", "secrets", "injection"],
    "performance-reviewer": ["performance", "latency", "throughput", "allocation"],
    "ux-reviewer": ["ux", "accessibility", "layout", "copy"],
    "concurrency-reviewer": ["concurrency", "race", "deadlock", "async", "threading"],
}


def is_in_reviewer_scope(reviewer: str, finding_category: str) -> bool:
    """Check if a finding's category falls within a reviewer's declared scope."""
    scope = REVIEWER_SCOPES.get(reviewer, [])
    if not scope:
        return False
    cat_lower = finding_category.lower()
    return any(s in cat_lower for s in scope)


def scope_aware_consensus(
    findings: list[dict[str, object]],
) -> list[dict[str, object]]:
    """Apply scope-aware consensus filter (ADR-005).

    Rules:
    - If a finding is tagged by 2+ reviewers (standard cross-check): consensus-passed
    - If a finding is from a single reviewer BUT the finding's category is within
      that reviewer's declared scope AND no other reviewer's scope covers that
      category: the finding is scope-exempted (treated as valid, auto-fix eligible)
    - Otherwise: manual-only
    """
    from collections import defaultdict

    by_location: dict[str, list[dict[str, object]]] = defaultdict(list)
    for f in findings:
        key = f"{f.get('file', '')}:{f.get('line', 0)}:{f.get('severity', '')}"
        by_location[key].append(f)

    result: list[dict[str, object]] = []
    for _key, group in by_location.items():
        reviewers = {str(f.get("reviewer", "")) for f in group}

        if len(reviewers) >= 2:
            merged = dict(group[0])
            merged["consensus_tag"] = "consensus-passed"
            merged["consensus_count"] = len(reviewers)
            result.append(merged)
        elif len(reviewers) == 1:
            reviewer = next(iter(reviewers))
            finding = dict(group[0])
            category = str(finding.get("category", finding.get("summary", "")))

            if is_in_reviewer_scope(reviewer, category):
                other_scopes_cover = any(
                    r != reviewer and is_in_reviewer_scope(r, category) for r in REVIEWER_SCOPES
                )
                if not other_scopes_cover:
                    finding["consensus_tag"] = "scope-exempted"
                    finding["scope_owner"] = reviewer
                else:
                    finding["consensus_tag"] = "manual-only"
            else:
                finding["consensus_tag"] = "manual-only"
            result.append(finding)
        else:
            for f in group:
                merged = dict(f)
                merged["consensus_tag"] = "manual-only"
                result.append(merged)

    return result


# Routing rule table — order is irrelevant since `selected` is a set.
_RULES: list[tuple[tuple[str, ...], str]] = [
    ((".env", "/auth/", "/secret"), "security-reviewer"),
    (("/perf/", "benchmark", "hot"), "performance-reviewer"),
    ((".tsx", ".jsx", "/ui/"), "ux-reviewer"),
    (("thread", "isr", "worker", "async"), "concurrency-reviewer"),
]

_DIFF_CHAR_CAP = 16_000  # cost guard for the LLM router


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

    # SPEC AC-002: conditional routing narrows the OPTIONAL reviewers and nothing else.
    # A reviewer outside OPTIONAL_REVIEWERS is kept whether or not a path rule matched it,
    # because the declared failure space must be exercised every round and a routed-away
    # lens would make every conditional review permanently unapprovable (AC-003).
    selected |= {r for r in preset_reviewers if r not in OPTIONAL_REVIEWERS}

    # Filter through preset_reviewers to preserve preset ordering and to
    # honour the user's choice (don't invoke a reviewer the preset omits).
    filtered = [r for r in preset_reviewers if r in selected]
    return filtered or ["code-reviewer"]


# ── LLM-powered router ─────────────────────────────────────────────────────


_LLM_SYSTEM_PROMPT = """You route reviewer agents based on a git diff.

Given the changed files + diff, pick which reviewers from the available
list should run. Always include `code-reviewer`. Add specialists when the
diff actually warrants them — not by file extension alone, but by what the
code does:

- security-reviewer: auth flows, secrets, permissions, deserialization,
  command injection vectors, crypto, input validation at trust boundaries.
- performance-reviewer: hot loops, N+1 patterns, allocation in inner
  loops, sync I/O on hot paths, caching changes.
- ux-reviewer: user-visible UI changes, copy, accessibility.
- concurrency-reviewer: threads, locks, async/await, ISRs, workers,
  shared mutable state, race conditions.

Output JSON ONLY:
{"reviewers": ["code-reviewer", ...]}

Only include reviewers that appear in the available list. Empty
specialist set is fine if the diff is plain — `code-reviewer` alone is
the floor."""


def _strip_markdown_fence(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        nl = stripped.find("\n")
        if nl != -1:
            stripped = stripped[nl + 1 :]
        if stripped.endswith("```"):
            stripped = stripped[:-3]
    return stripped.strip()


def _parse_router_response(raw: str, allowed: set[str]) -> list[str] | None:
    body = _strip_markdown_fence(raw)
    try:
        data = json.loads(body)
    except (json.JSONDecodeError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    raw_list = data.get("reviewers")
    if not isinstance(raw_list, list):
        return None
    out: list[str] = []
    seen: set[str] = set()
    for item in raw_list:
        if isinstance(item, str) and item in allowed and item not in seen:
            out.append(item)
            seen.add(item)
    if not out:
        return None
    if "code-reviewer" not in seen and "code-reviewer" in allowed:
        out.insert(0, "code-reviewer")
    return out


def route_with_llm(
    changed_files: list[Path],
    preset_reviewers: list[str],
    diff_text: str,
    *,
    client: JudgeClient,
    model: str = "claude-sonnet-4-6",
) -> list[str]:
    """LLM-routed reviewer selection with rule-based fallback.

    On any LLM transport error or unparseable response we delegate to
    ``route_reviewers(..., routing='conditional')`` so /hm:review never
    breaks because the API blinked.
    """
    allowed = set(preset_reviewers)
    user = (
        f"Available reviewers: {', '.join(preset_reviewers)}\n\n"
        f"Changed files:\n  " + "\n  ".join(str(f) for f in changed_files) + "\n\n"
        f"--- BEGIN DIFF ---\n{diff_text[:_DIFF_CHAR_CAP]}\n--- END DIFF ---"
    )
    try:
        raw = client.judge(_LLM_SYSTEM_PROMPT, user, model)
    except Exception:  # noqa: BLE001 — degrade to rules
        return route_reviewers(changed_files, preset_reviewers, routing="conditional")
    parsed = _parse_router_response(raw, allowed)
    if parsed is None:
        return route_reviewers(changed_files, preset_reviewers, routing="conditional")
    # Preserve preset ordering — LLM's order may differ.
    return [r for r in preset_reviewers if r in set(parsed)]
