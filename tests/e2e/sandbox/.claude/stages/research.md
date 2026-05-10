---
generated_by: harness-maker
harness_maker_version: 0.9.3
generated_at: '2026-01-01T00:00:00+00:00'
source_template: stages/research.md.j2
provenance: official
content_hash: 284511ed15a63b37c2f17fd0309f24517f0becfefd23ebe2fb28d6fc9322aacd
---
# Stage: research

> Atomic stage. **Exploratory** — gather facts, surface alternatives. Decisions get locked in `plan`, not here.


## Communication Protocol

- Be direct and matter-of-fact. No flattery, no preamble.
- When alternatives differ in trade-offs, say which trade-off is binding.
- Distinguish facts (cite source) from inferences (label as such).
- Surface unknowns explicitly — never paper over with confident-sounding speculation.

## Purpose

Gather sufficient context before committing to a plan. Surface unknowns, prior art, library docs, and architectural alternatives so that downstream stages (`spec`, `plan`, `execute`) can proceed without rework.

**Role separation vs `/hm:plan`:**
- `research` = exploratory. Multiple approaches surface; user decides direction informally.
- `plan` = decisive. Architecture locked via formal interview + ADRs.

Research deliberately avoids heavy interaction — it is silent multi-source gathering. The deep interview belongs to `plan`. Use `--deep` here only when the topic itself is so vague that searching would produce noise.

## When to Run

- Starting a new feature in an unfamiliar area of the codebase.
- Selecting between competing approaches (libraries, patterns, algorithms).
- Investigating a bug whose root cause is unclear.
- Before writing a SPEC for a non-trivial change.

## Usage

```
/hm:research <topic> [--deep] [--slug=<name>]
```

- `<topic>` — free-form description of what to research.
- `--deep` — opt into Phase 0 refinement interview (3-5 questions to narrow scope before searching). Use when the topic is vague or over-broad. Default is OFF — research dives in directly.
- `--slug=<name>` — explicit kebab-case slug for the output file. When omitted, derive from topic (lowercase, non-alphanumeric → `-`, ≤40 chars).

## Inputs

- User topic (`$ARGUMENTS`).
- Codebase context (relevant files, prior PLANs, prior REVIEWs in `work-docs/`).
- Memory tiers — see loading order below.

## Session Context Loading

Before starting, load memory in tier order (stops at first miss per tier):

1. **Hot tier** — Read `.claude/memory/session/<today's date>.md` if it exists.
2. **Warm tier** — Skim `.claude/memory/failures.md` (first 60 lines); search relevant: `rg -F "[fail:" .claude/memory/failures.md`.
3. **Warm tier** — Skim `.claude/memory/wiki.md` (first 60 lines); search relevant: `rg -F "[wiki:" .claude/memory/wiki.md`.

## Procedure

### Phase 0 — Refinement interview (only when `--deep` is set)

Vague or over-broad topics produce shallow research. Narrowing the question first is the single highest-leverage step. Skip this phase by default; engage when the topic itself is the unknown.

When `--deep` is set, conduct one `AskUserQuestion` call in `en` with 3-5 questions drawn from this rubric:

1. **Scope narrowing** — "Is this about {sub-area A} specifically, or the broader {domain}?"
2. **Constraint surfacing** — "Which constraint actually binds: {HW budget / API compat / team skill / timeline / other}?"
3. **Pre-seed check** — "Do you have a preferred approach in mind to validate, or is this open exploration?"
4. **Success definition** — "What makes this research successful — concrete recommendation, trade-off matrix, or copyable code patterns?"
5. **Prior-art** — "Have you tried an approach that didn't work, so we can avoid it?"

Always include "Skip — proceed with topic as given" as an option. Record interview outcomes under `## Refinement Decisions` in the output document.

### Phase 0.5 — 3-Layer Deep Interview Gate (only when `--deep` is set)

Runs immediately after Phase 0's rubric questions, before Phase 1 gathering.
Bridges from the rubric's broad-scope answers to research-ready precision.

**Skip if user chose Skip**: If the user chose "Skip — proceed with topic as given"
in Phase 0, skip Phase 0.5 entirely and proceed directly to Phase 1.

**Layer 1 — GCIC Gap Check**

Map Phase 0 answers to 4 research-scoping axes
(0.0 = absent · 0.5 = partial · 1.0 = clear):

- **Goals**: Research objective — what decision or output does this research inform?
- **Constraints**: Binding constraints on the recommended approach (budget, compat, risk tolerance)?
- **Inputs**: Prior knowledge, rejected approaches, existing code to build on?
- **Context**: Team skill level, timeline, and who evaluates the research output?

Note: axes already clearly answered by Phase 0 rubric questions are scored 1.0 and
skipped — do NOT re-ask. Only probe uncovered axes.

For any axis < 0.7 that wasn't covered by the rubric, apply the **CLARITI filter**:
1. Task Relevance: "Does knowing this axis change which sources to search?" (0–1)
2. User Answerability: "Can the user answer this now?" (0–1)
→ Ask only if both ≥ 0.7. Otherwise log `"LLM-inferred"`.

**Layer 2 — Implicit Probing**

Five candidate types (use short label to track; also exclude types semantically covered by Phase 0 rubric questions):
- **NOT-USEFUL**: "What would make this research **not useful** to you?" → implicit failure criteria
- **AVOID**: "What direction are you hoping I **won't** recommend?" → implicit bias/constraints
- **DEPTH**: "What **depth** is needed — proof of concept vs production-grade?" → scope expectations
- **AUDIENCE**: "Who else will read this research output?" → implicit audience / quality bar
- **TIME-SCOPE**: "What **time or depth** constraints apply — quick scan vs exhaustive survey?" → scope bounds

**MUST NOT reuse a type label** from Phase 0 rubric or a prior gate round (track: NOT-USEFUL/AVOID/DEPTH/AUDIENCE/TIME-SCOPE used).
Batch into one `AskUserQuestion` call (max 4).

**Layer 3 — Ambiguity Score (display)**

```
Research Scope Score: {X.X}/1.0  (Goal×40% + Constraint×30% + OC×30%)
  Goals (research objective):  {g:.1f}/1.0  ✅ or ⚠️
  Constraints (approach):      {c:.1f}/1.0  ✅ or ⚠️
  Output Criteria (usefulness):{oc:.1f}/1.0 ✅ or ⚠️
  Weighted total: {g*0.4 + c*0.3 + oc*0.3:.2f}
  → PASS or NEEDS  (streak: {N}/2)
```

Score monotonicity rule: score must not decrease round-over-round for the same answers;
a drop ≥ 0.1 requires a one-line `[score-drop-reason]: ...` note appended to the
Layer 3 display block, then applied.

**Convergence**: total ≥ 0.8 AND all dims ≥ 0.7, **2 consecutive rounds** → PASS.
On **NEEDS**: new probes only (no repeats). Max **3 rounds**. After 3 NEEDS,
offer "Proceed with current scope?" and continue to Phase 1 regardless.

### Phase 1 — Multi-source gathering

Run these in parallel where the answers are independent. Total token budget ≤8k.

1. **Codebase patterns** — `Grep` / `Glob` for related identifiers, prior implementations, similar features.
2. **Prior-art search in memory** — already loaded above; pull relevant `[wiki:*]` and `[fail:*]` entries.
3. **Prior PLANs / REVIEWs** — `Grep` over `work-docs/` for related task slugs.
4. **Library / framework docs** — when the topic involves a named library (React, FastAPI, Tokio, etc.), use Context7 (or equivalent doc-fetch MCP if available) for **current** docs. Training data drifts; check official docs.
5. **Web search** — for "best practices YEAR" / "common pitfalls" / "implementation patterns" queries. Skip when an internal answer is already authoritative.
6. **Refdocs folders** — when project has `ref_folders` configured in `harness.yaml`, the `refdocs-search` skill provides lossless full-text search across registered folders.

Cite every external source. Track:
- `libs_fetched` — list of library IDs / doc URLs queried.
- `sources` — list of web URLs cited.
- `related_docs` — list of internal `[[doc-link]]` references found.

### Phase 2 — Analysis

For each surfaced approach, capture:

| Field | Content |
|-------|---------|
| Approach | Short name |
| Assumption | What it presumes about the project |
| Evidence | What sources support / contradict it |
| Trade-off | Cost paid for the benefit |
| Compatibility | Fit with existing architecture |
| Risk | low / medium / high |

Then synthesize:
1. **Problem understanding** — restate the topic with sharper boundaries (in/out of scope).
2. **Recommended direction** — pick one approach with one-sentence rationale. This is *informational* — `plan` makes the binding decision.
3. **Open questions** — items that block `plan` from starting. Surface these as the validation prompt at Phase 4.
4. **Pitfalls** — what others got wrong on this topic.

### Phase 3 — Write RESEARCH document

Write to `work-docs/RESEARCH-{slug}.md`. `/hm:plan` Step 2 reads this file via PLAN frontmatter `research_doc:` and skips its own retrieval — this is the single biggest token saver in the workflow.

**Required frontmatter:**

```yaml
---
type: research
task_slug: {slug}
status: complete
created: {YYYY-MM-DD}
tags: [{project}, research, {tech-stack}, {2-5 domain tags}]
mtime_warn_days: 7  # downstream commands warn when this file is older than N days
libs_fetched: [{lib-ids}]
sources: [{urls}]
related_docs: [{wiki-links}]
summary: "{≤100 char one-line: recommended direction}"
---
```

**Required sections (in this order):**

1. **🎯 Recommended Direction** — TL;DR sentence + one-paragraph rationale.
2. **🔍 Refinement Decisions** — when `--deep` ran, summarize Phase 0 answers; otherwise omit.
3. **🛠️ Approaches Found** — 2-3 alternatives, each with the analysis table fields above.
4. **⚠️ Pitfalls** — concrete failure modes others hit on this topic, with citations.
5. **❓ Open Questions** — items `/hm:plan` will need to lock down via interview.
6. **📚 Sources** — bullet list of every external citation (web URLs, doc URLs, library IDs).
7. **🔗 Related Internal Docs** — `[[wiki-links]]` to prior PLANs / SESSIONS / REVIEWs found in Phase 1.

### Phase 4 — Validation

Stop and validate with the user. Surface this prompt:

```markdown
## Research saved → RESEARCH-{slug}.md

**Topic:** {topic}
**Recommended:** {Option X — one-line rationale}
**Sources fetched:** {N web} + {N library docs} + {N internal refs}
**Open questions for plan:** {N}

**Ready to proceed?** {Y/N}
- Y → run `/hm:plan {slug}` (will read RESEARCH-{slug}.md via frontmatter)
- N → tell me which approach to dig deeper into, or which open question to answer first
```

If the user opts for "dig deeper" — re-enter Phase 1 with narrowed scope (one approach in focus). Re-write the RESEARCH document; do NOT create a second file.

## Outputs

- `work-docs/RESEARCH-{slug}.md` — frontmatter + 7 sections above.
- Validation summary surfaced to the user.

## Quality Bar

- No "I don't know" surprises in later stages on points covered here.
- Every claim is grounded in a cited source (internal or external) or labeled as inference.
- Open questions are explicit, not hidden as assumptions.
- The Recommended Direction is informational — never written as an architectural commitment (that's `plan`'s job).
- File is reusable: `/hm:plan` can read it without contacting the user for re-clarification on settled facts.

<!-- @hm:user:extra-quality-checks -->
<!-- Project-specific quality bar items. Preserved across harness-maker upgrades. -->
<!-- @hm:/user:extra-quality-checks -->



<!-- @hm:user:extensions -->
<!-- Free-form project-specific additions to the research stage. Preserved across harness-maker upgrades. -->
<!-- @hm:/user:extensions -->
