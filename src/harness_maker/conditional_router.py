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
from typing import TypedDict

from harness_maker.llm_judge import JudgeClient

#: The discovery axis: the source experiment's six textbook categories, MERGED to four.
#:
#: The six were adopted verbatim by ADR-001 and the merge deviates from that deliberately, on
#: measured redundancy rather than on taste. From the 2026-08-16 nine-lens run over the Phases
#: 2-4 diff, counting each lens's findings that ANOTHER lens also raised:
#:
#:     consistency  80% redundant (4 of 5)   design       50% (4 of 8)
#:     complexity   40% (2 of 5)             robustness   40% (2 of 5)
#:     functionality 33% (3 of 9)            naming       14% (1 of 7)
#:     security / concurrency / tests   0% — every finding exclusive
#:
#: Two merges follow from that, and only two:
#:
#: - **`complexity` folded into `design`.** Both of its overlaps were with `design`, and its
#:   exclusive findings were all shape questions — a decision function with no caller, dataclasses
#:   nothing crosses a boundary with, three CLI round trips where one would do. "Is this the right
#:   shape" and "is this more shape than the problem needs" are one question asked twice.
#: - **`naming` folded into `consistency`.** `consistency` was the most redundant lens in the run
#:   and its single exclusive finding was a constant duplicated in two modules — which is what the
#:   merged lens is for. Both read two places and compare: a name against its value, a docstring
#:   against its code, a module against the conventions around it. `naming`'s own yield was almost
#:   entirely exclusive, so the merged brief keeps its question first and in full.
#:
#: Untouched: the three zero-redundancy lenses, plus `robustness` (sole voice on the P0 at P0, and
#: on the codex target rendering every mandated call inert) and `functionality`.
#:
#: The prior five (`correctness`, `failure`, `concurrency`, `security`, `tests`) are NOT carried
#: alongside these: `correctness` and `failure` are RETIRED, replaced by `functionality` and
#: `robustness`. The Phase 0 pilot measured `correctness` at zero exclusive finding-groups across
#: three diffs — every finding it produced, `functionality` produced too.
#:
#: **Caveat, stated because the numbers above look more solid than they are:** one diff, one run
#: per lens. The source experiment measured median Jaccard 0.36 between two runs of ONE reviewer,
#: so a re-run would redraw some of these groups. `consistency` at 80% is 4 findings out of 5.
#: The mandatory set is seven on Production and these four on Side — never nine, never eleven.
CORE_LENSES: tuple[str, ...] = (
    "design",
    "functionality",
    "robustness",
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

#: Every lens name a result file or a telemetry row may legitimately carry, on any preset. This
#: is a VOCABULARY, not a requirement: `mandatory_lenses(preset)` answers "what must be exercised
#: to approve", and the two are different sets on Side.
KNOWN_LENSES: tuple[str, ...] = ALL_LENSES

#: Deprecated alias for `KNOWN_LENSES`. The name asserts preset-scoped mandatoriness that its
#: value never had — it is the full vocabulary — and a reader who "fixed" the constant to be
#: genuinely mandatory-scoped would make `review_telemetry.emit` reject a legitimate Side row
#: carrying a router-selected `security`, losing that append-only row. New code uses
#: `KNOWN_LENSES` or `mandatory_lenses(preset)`; this exists so an out-of-tree import keeps
#: working.
MANDATORY_LENSES: tuple[str, ...] = KNOWN_LENSES


def mandatory_lenses(preset: str = "Production") -> tuple[str, ...]:
    """The lenses a preset must exercise before a review can be approved.

    Unknown presets resolve to Production. Erring toward *more* mandatory coverage is the
    fail-closed direction: the failure mode this set exists to catch is a dispatch that never
    happened, and a typo'd preset silently dropping three lenses would produce exactly the
    clean bill of health the coverage gate is built to prevent.
    """
    return CORE_LENSES if str(preset) == "Side" else ALL_LENSES


#: How each lens is dispatched: the subagent that carries it, and the one-line brief that tells
#: it which axis it owns. The core categories share `code-reviewer` and are distinguished ONLY
#: by this line, which is why the brief is data here rather than prose in the template — several
#: dispatches to one agent name are otherwise indistinguishable in the rendered command.
LENS_DISPATCH: dict[str, tuple[str, str]] = {
    "design": (
        "code-reviewer",
        "design — boundaries, coupling, whether this is the right shape for the problem; and "
        "complexity: could it be simpler? Unnecessary indirection, dead generality, a knob or a "
        "function with no caller on any path a user reaches.",
    ),
    "functionality": (
        "code-reviewer",
        "functionality — does it do what the SPEC and the invariants say, on every path?",
    ),
    "robustness": (
        "code-reviewer",
        "robustness — edge cases, partial writes, restart, resource exhaustion, recovery.",
    ),
    "consistency": (
        "code-reviewer",
        "consistency — do the names, docstrings and declarations say what the code actually "
        "does, and does this match the conventions around it? A name or a docstring that makes a "
        "reader believe something FALSE about behaviour is a defect, not a nit; so is a second "
        "source of truth for something that already had one.",
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


class LensGroup(TypedDict):
    """One subagent dispatch: the lenses it carries, and the result file it produces.

    Separate from `LENS_DISPATCH` because the unit of *dispatch* stopped being the unit of
    *lens* — several lenses now travel in one call, and `lens_coverage` has to map the one
    file that produces back onto the several lenses it is evidence for.
    """

    file: str
    agent: str
    lenses: list[str]
    briefs: list[str]


#: Which lenses travel in ONE dispatch, keyed by the result-file stem the main loop writes.
#:
#: The four core lenses share `code-reviewer` and differ only by their brief sentence, so four
#: dispatches meant four independent re-reads of the same diff for four questions one agent can
#: hold at once. Phase A.5 of `/hm:execute` made the same move for its three test lenses and
#: recorded ≈330k subagent tokens per round — the token claim only: that fan-out was serial
#: retries, while these four already left in one message, so no latency is recovered here.
#:
#: **The yield of the merge is unmeasured, deliberately** (SPEC Intent). `harness-bench` §10's
#: nearest data point scored a single *generic* call at 11.0 distinct findings against 30.0 for
#: a six-category fan-out; the enumerated-categories-in-one-call arm this produces was never run.
#:
#: **This constant IS the reversal.** Restoring the fan-out is `{lens: (lens,) for lens in
#: ALL_LENSES}` and nothing else — both rendered dispatch blocks and `lens_coverage` derive from
#: here, so neither can disagree with the other about what a dispatch is.
#:
#: A singleton group is keyed by its own lens name, so a **domain** lens's per-lens result file
#: resolves through this table. A legacy **core**-lens file (`design.json` and friends) does NOT
#: — `core` is the only key covering those four, and their stems resolve through the separate
#: `stem in ALL_LENSES` fallback in `lenses_for_result_file`. Two mechanisms, not one: deleting
#: that fallback as apparently redundant silently breaks SPEC AC-004's third clause for every
#: core lens an un-re-rendered harness writes.
LENS_GROUPS: dict[str, tuple[str, ...]] = {
    "core": CORE_LENSES,
    **{lens: (lens,) for lens in DOMAIN_LENSES},
}


def lenses_for_result_file(stem: str) -> tuple[str, ...]:
    """The lenses a result file with this stem is evidence for; empty when the stem is unknown.

    Fail-closed by returning the empty tuple rather than raising or guessing: a merged file now
    vouches for four lenses instead of one, so resolving "cannot tell" to "exercised" costs four
    times what it used to. The caller (`lens_coverage.exercised_lenses`) unions what comes back,
    and an empty tuple contributes nothing — which is the same shape as an absent file.
    """
    if stem in LENS_GROUPS:
        return LENS_GROUPS[stem]
    if stem in ALL_LENSES:
        return (stem,)
    return ()


def lens_dispatch_groups(preset: str = "Production") -> list[LensGroup]:
    """The preset's dispatch table grouped into one entry per subagent call.

    Derived from `lens_dispatch` rather than beside it, so a lens cannot be dispatched by one
    and required by the other. Both rendered dispatch sites — round 1 and the confirmation pass
    — loop over this, which makes their parity structural instead of conventional: a pass
    missing a lens the coverage CLI requires makes every review permanently unapprovable
    (SPEC AC-015 of the nine-lens work).
    """
    by_lens = {str(d["lens"]): d for d in lens_dispatch(preset)}
    groups: list[LensGroup] = []
    for file, members in LENS_GROUPS.items():
        present = [lens for lens in members if lens in by_lens]
        if not present:
            continue
        agents = {by_lens[lens]["agent"] for lens in present}
        if len(agents) != 1:
            # A group is one agent and one dispatch. A mixed group would render a call that
            # names one agent while carrying another's brief — silently wrong, and invisible
            # in the rendered command, which is this repository's recurring defect class.
            msg = f"lens group {file!r} spans agents {sorted(agents)}; a group is one agent"
            raise ValueError(msg)
        groups.append(
            LensGroup(
                file=file,
                agent=agents.pop(),
                lenses=present,
                briefs=[by_lens[lens]["brief"] for lens in present],
            )
        )
    return groups


def lens_dispatch(preset: str = "Production") -> list[dict[str, str]]:
    """The preset's dispatch table, in a shape a template can loop over.

    Both dispatch sites — round 1 and the confirmation pass — call this, so the two lists cannot
    drift apart. Parity is not a convention here: a confirmation pass missing a lens the coverage
    CLI requires makes every review permanently unapprovable (SPEC AC-015).
    """
    # mandatory + routable, NOT mandatory alone. The Side split is "the router decides", and a
    # router can only DROP what was dispatched — with the mandatory set alone, `security`,
    # `concurrency` and `tests` were absent from every Side render, so a Side harness could never
    # run them at all while the rendered prose said the router "may drop" them. Opt-out, not
    # opt-in, is what ADR-001 specified. `mandatory_lenses` is unchanged: these three are
    # dispatched on Side but not REQUIRED for approval, which is exactly the preset difference.
    dispatched = list(mandatory_lenses(preset)) + [
        lens for lens in routable_lenses(preset) if lens not in mandatory_lenses(preset)
    ]
    return [
        {"lens": lens, "agent": LENS_DISPATCH[lens][0], "brief": LENS_DISPATCH[lens][1]}
        for lens in dispatched
    ]


def routable_lenses(preset: str = "Production") -> tuple[str, ...]:
    """Lenses the conditional router may drop for a preset — empty on Production.

    Side gets the domain lenses back as routable, which is the whole preset split: a Side project
    touching no auth and no threads still DISPATCHES all seven (a router can only drop what was
    dispatched) but only the four core lenses are REQUIRED for approval.
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
