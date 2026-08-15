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

#: The discovery axis, adopted verbatim from the source experiment's structured arm
#: (PLAN-review-loop-empirics ADR-001). Textbook code-review order; the measured fan-out gain
#: concentrated in `robustness` and `naming`, which the old axis had no owner for.
#:
#: The prior five (`correctness`, `failure`, `concurrency`, `security`, `tests`) are NOT carried
#: alongside these: `correctness` and `failure` are RETIRED, replaced by `functionality` and
#: `robustness`. The Phase 0 pilot measured `correctness` at zero exclusive finding-groups across
#: three diffs — every finding it produced, `functionality` produced too — so the substitution is
#: evidenced rather than assumed. The mandatory set is nine, never eleven.
CORE_LENSES: tuple[str, ...] = (
    "design",
    "functionality",
    "complexity",
    "robustness",
    "naming",
    "consistency",
)

#: The domain lenses that ride alongside the axis. The source experiment's target had no auth and
#: no threads so it needed none of these; harness-maker renders for firmware and BLE repositories
#: that do. Mandatory on Production, conditionally routed on Side — the cost adjustment lands on
#: the preset axis rather than on coverage.
DOMAIN_LENSES: tuple[str, ...] = ("security", "concurrency", "tests")

#: Every lens name any preset can dispatch. Availability is preset-independent (SPEC AC-002):
#: presets differ in which lenses are *mandatory*, never in which exist.
ALL_LENSES: tuple[str, ...] = CORE_LENSES + DOMAIN_LENSES

#: Production's mandatory set, and the name every existing consumer imports. Kept as an alias so
#: `review_telemetry`'s known-lens validation accepts the full vocabulary regardless of preset —
#: a Side harness that routes in `security` still emits a legitimate `security` result.
MANDATORY_LENSES: tuple[str, ...] = ALL_LENSES


def mandatory_lenses(preset: str = "Production") -> tuple[str, ...]:
    """The lenses a preset must exercise before a review can be approved.

    Unknown presets resolve to Production. Erring toward *more* mandatory coverage is the
    fail-closed direction: the failure mode this set exists to catch is a dispatch that never
    happened, and a typo'd preset silently dropping three lenses would produce exactly the
    clean bill of health the coverage gate is built to prevent.
    """
    return CORE_LENSES if str(preset) == "Side" else ALL_LENSES


#: How each lens is dispatched: the subagent that carries it, and the one-line brief that tells
#: it which axis it owns. The six core categories share `code-reviewer` and are distinguished ONLY
#: by this line, which is why the brief is data here rather than prose in the template — six
#: dispatches to one agent name are otherwise indistinguishable in the rendered command.
LENS_DISPATCH: dict[str, tuple[str, str]] = {
    "design": (
        "code-reviewer",
        "design — boundaries, coupling, whether this is the right shape for the problem.",
    ),
    "functionality": (
        "code-reviewer",
        "functionality — does it do what the SPEC and the invariants say, on every path?",
    ),
    "complexity": (
        "code-reviewer",
        "complexity — could this be simpler? Unnecessary indirection, dead generality.",
    ),
    "robustness": (
        "code-reviewer",
        "robustness — edge cases, partial writes, restart, resource exhaustion, recovery.",
    ),
    "naming": (
        "code-reviewer",
        "naming — do the names say what the things are? Misleading names are defects.",
    ),
    "consistency": (
        "code-reviewer",
        "consistency — does this match the conventions of the code around it?",
    ),
    "security": (
        "security-reviewer",
        "security — external input, authz, secrets, injection.",
    ),
    "concurrency": (
        "concurrency-reviewer",
        "concurrency — races, deadlock, resource lifetime, cancellation.",
    ),
    "tests": (
        "test-reviewer",
        "tests — oracle strength, discrimination, would these tests pass a wrong implementation?",
    ),
}


def lens_dispatch(preset: str = "Production") -> list[dict[str, str]]:
    """The preset's dispatch table, in a shape a template can loop over.

    Both dispatch sites — round 1 and the confirmation pass — call this, so the two lists cannot
    drift apart. Parity is not a convention here: a confirmation pass missing a lens the coverage
    CLI requires makes every review permanently unapprovable (SPEC AC-015).
    """
    return [
        {"lens": lens, "agent": LENS_DISPATCH[lens][0], "brief": LENS_DISPATCH[lens][1]}
        for lens in mandatory_lenses(preset)
    ]


def routable_lenses(preset: str = "Production") -> tuple[str, ...]:
    """Lenses the conditional router may drop for a preset — empty on Production.

    Side gets the domain lenses back as routable, which is the whole preset split: a Side
    project touching no auth and no threads pays six dispatches, not nine.
    """
    return DOMAIN_LENSES if str(preset) == "Side" else ()


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
