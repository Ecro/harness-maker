---
generated_by: harness-maker
harness_maker_version: 0.7.1
generated_at: '2026-01-01T00:00:00+00:00'
source_template: commands/hm/workflow_command.md.j2
provenance: official
content_hash: 753963cc9fe113f6c63cff52f312d1d07a5aa76a0523f6302284c55b3e7423b1
---
# /hm:res-spec-plan


## Stage: research

# Stage: research

> Atomic stage. **Exploratory** — gather facts, surface alternatives. Decisions get locked in `plan`, not here.

> Invoked as part of the **res-spec-plan** workflow.


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


## Stage: spec

# Stage: spec

> Atomic stage. Acceptance-criteria specification via 6-category interview. Owns **what / why / verification**. `plan` owns **how / risk / phasing**.

> Invoked as part of the **res-spec-plan** workflow.


## Communication Protocol

- Be direct. No flattery, no preamble.
- Force observable acceptance — vague criteria ("works correctly") are rejected.
- Force the test framework choice in Constraints — `/hm:execute` Phase A writes tests against it; deferring this just kicks the can.
- Lead with concerns: if a SPEC criterion is implementation detail in disguise, say so.

## Purpose

Convert a task description into testable acceptance criteria so that:
- `/hm:plan` can decompose into phases that each map back to a SPEC scenario.
- `/hm:execute` Phase A can author tests **directly from the SPEC**, not from planner intent.
- `/hm:wrapup` Drift gate can compare actual diff against SPEC scope.

The deep interview here is shorter than `/hm:plan`'s — SPEC concerns are **what** and **how to verify**, not **how to build**. Architecture decisions belong to `plan`.

## When to Run

- After `research` for non-trivial features.
- Before `plan` whenever the change is observable to a user, an API consumer, or another module.
- Skip via Step 0 heuristic for trivial changes.

## Inputs

- Research notes at `work-docs/RESEARCH-{slug}.md` (when `/hm:research` ran).
- User requirements / acceptance constraints.
- Existing SPEC at `specs/SPEC-{slug}.md` if this is an evolution.
- Project memory (`.claude/memory/wiki.md`, `failures.md`).

## Procedure

### Step 0 — Skip heuristic (ALL 4 criteria + title-obvious)

Skip the SPEC interview ONLY when:

| Criterion | Skip condition |
|-----------|----------------|
| **Scope** | Single file OR config-only (typo, env var, README copy) |
| **Acceptance** | Obvious from the title — no scenarios beyond happy path |
| **Contracts** | No API / IPC / DB schema / file format change |
| **Risk** | Reversible in <1h with no user-facing impact |

When skipped: write a minimal SPEC (Intent + 1 happy-path scenario in G-W-T form + Verification = "manual smoke") and continue. Do NOT ask permission to skip — proceed and log rationale in the SPEC's `## Refinement Decisions` section.

### Step 1 — Knowledge retrieval

Search prior work to ground the interview (token budget ≤3k):

```bash
# Prior SPECs on related topics
Grep "<key terms>" --glob "specs/SPEC-*.md"
# Prior PLANs (for scope reference)
Grep "<key terms>" --glob "work-docs/PLAN-*.md"
# Repo memory
[ -f .claude/memory/failures.md ] && rg "<key terms>" .claude/memory/failures.md
[ -f .claude/memory/wiki.md ] && rg "<key terms>" .claude/memory/wiki.md
# When research ran, read its cache
[ -f work-docs/RESEARCH-{slug}.md ] && Read work-docs/RESEARCH-{slug}.md
```

Surface relevant prior-SPEC snippets at the top of the interview so the user can see what's been specified before.

### Step 2 — Interview (default ON)

Same UX rules as `/hm:plan`:
- **Live UI** in `en` (en→English, ko→Korean, others→English fallback).
- **SPEC document on disk** always English. Translate user's free-form answers when archiving.
- Use `AskUserQuestion`. **Batch independent questions** per round (independence test: would Q2's options change based on Q1's answer? if yes → separate rounds).
- Always include **"Other — let me describe"**.
- From Round 2 onward, include **"SPEC is sufficiently clear — end interview"** on one foundational question per round.
- Visualization OPTIONAL — prose / bullets preferred, ASCII for topology, Mermaid only in the final document (never in live terminal).

#### 2.1 Six interview categories (in this order)

Skip a category when sufficiently answered by prior research, prior SPEC, or earlier rounds. Batch multiple independent questions per round when possible.

1. **Intent (Why)** — motivation, business / technical trigger. Often answered by `/hm:research`; confirm if so.
2. **Outcomes (What success looks like)** — observable end-state. Force the user to state "done" in observable terms, not implementation details.
3. **In-Scope Scenarios** — generate 2-4 scenarios in **Given-When-Then** form covering normal / edge / failure paths. This is mandatory format; reject prose like "the system handles errors" — restate as G-W-T.
4. **Non-Goals** — explicit out-of-scope list. Prevents scope creep in `plan`.
5. **Constraints** — HW, SW, security, performance, compatibility, **and test framework** (mandatory — pick `pytest` / `gtest` / `vitest` / `bats` / etc; `/hm:execute` Phase A uses this to write tests).
6. **Verification Criteria** — per-scenario, how we'll prove it: unit / integration / manual. Each scenario MUST map to at least one verification mode.

#### 2.2 Promotion rule

SPEC's substantive decisions (e.g., "what counts as done for Scenario 2?", "fail-closed vs fail-open?") feed `/hm:plan`'s ADRs downstream — they live in the SPEC's `## ❓ Open Questions` section with the resolution. **SPEC does NOT have its own ADR section.** Promotion to ADR happens in `plan`.

#### 2.3 Round preamble

```
## SPEC Interview Round {N}

**Decisions locked in so far:**
- ✅ Intent: {summary}
- ✅ Outcomes: {summary}
- ✅ Scenario S1, S2 confirmed

**This round's category:** {Non-Goals / Constraints / Verification}
**Why it matters:** {one-sentence cost of getting this wrong}
```

### Step 3 — Write SPEC document

Write to `specs/SPEC-{slug}.md`.

**Required frontmatter:**

```yaml
---
type: spec
task_slug: {slug}
status: draft   # → approved when interview ends with no open questions
created: {YYYY-MM-DD}
tags: [{project}, spec, {tech-stack}, {2-5 domain tags}]
test_framework: {pytest | gtest | vitest | bats | …}   # MANDATORY
research_doc: "[[RESEARCH-{slug}]]"   # OR omit when no research artifact
summary: "{≤100 char one-line: what this SPEC is for}"
---
```

**Required sections (in this order):**

1. **🎯 Intent** — 2-3 sentences: trigger + business/technical motivation.
2. **🌅 Outcomes** — observable end-state. What the user / API consumer can do that they cannot do today.
3. **📋 In-Scope Scenarios** — numbered S1, S2, … each in **Given-When-Then** form:
   ```markdown
   ### S1: {short title}
   **Given** {initial state}
   **When** {triggering action}
   **Then** {observable result}
   **And** {additional observable}   ← optional
   ```
4. **🚫 Non-Goals** — bullet list of explicit out-of-scope items.
5. **⚠️ Constraints** — table:
   | Constraint | Value | Rationale |
   |---|---|---|
   | Test framework | `{name}` | {why this one} |
   | Performance | `{budget}` | {source of bound} |
   | Security | `{requirement}` | {threat model} |
   | Compatibility | `{version range}` | {ecosystem} |
6. **✅ Verification Criteria** — per-scenario:
   | Scenario | Verification mode | Test name / manual step |
   |---|---|---|
   | S1 | unit | `test_s1_happy_path` |
   | S2 | integration | `test_s2_with_db` |
   | S3 | manual | "open settings, click X, confirm Y" |
7. **❓ Open Questions** — items the user could not resolve in interview. These feed `/hm:plan`'s ADRs. Empty list = SPEC ready for plan.
8. **🔍 Refinement Decisions** — 1-line per round summarizing what was locked in (or "skipped — task is trivial: {reason}").

### Step 4 — Verify write

After writing, Read the file back and assert:
- Starts with `---` frontmatter.
- `test_framework:` field is non-empty.
- ≥1 scenario in G-W-T form.
- Verification table covers every scenario.

If verification fails, retry write **once**. If still failing, surface error + path and stop.

### Step 4.5 — Spec quality gate (ADR-006)

Score the freshly-written SPEC against the rubric (5 dimensions, each 0-100):
completeness, testability, unambiguity, consistency, scope_boundary.

```bash
jq -n --arg spec "$(cat specs/SPEC-{slug}.md)" \
      --arg mode "spec-driven" \
      '{spec_text: $spec, dev_mode: $mode}' \
  | python -m harness_maker.spec_quality eval
```

Read the returned JSON `{overall, scores, weak_dimensions, blocked, dev_mode}`.

| `dev_mode` | `blocked == true` (overall < 60 OR any dim < 40) | Action |
|------------|--------------------------------------------------|--------|
| `spec-driven` | yes | **HALT.** Surface failing dims + concrete improvement bullets ("strengthen acceptance criteria for Scenario 2", "delete vague qualifier 'fast'", "add an out-of-scope section"). Do NOT mark `status: approved`. |
| `spec-driven` | no | continue to Step 5 |
| `task-driven` | yes | **WARN only.** Print `⚠️ spec quality below threshold ({overall}/100): {weak_dimensions}` and continue — task-driven mode does not block. |
| `task-driven` | no | continue silently |

Failure rationale always cites the exact `weak_dimensions` from the CLI
output. Do not paraphrase — the user will rewrite those specific
dimensions.

### Step 5 — Status update

If `## ❓ Open Questions` is empty: update frontmatter `status: approved`. Otherwise `status: draft`.

The user can resume by editing the SPEC directly or re-running `/hm:spec {slug}` (interview will read the existing SPEC and re-engage on draft items).

## Outputs

- `specs/SPEC-{slug}.md` — frontmatter + 8 sections above.
- Status: `draft` (open questions remain) or `approved` (ready for `/hm:plan`).

## Quality Bar

- A test author can write tests directly from `## ✅ Verification Criteria` without guessing.
- No criterion is implementation detail in disguise — descriptions are about behavior.
- Non-goals prevent scope creep in `plan` and `execute`.
- Test framework is named — `pytest` not "Python testing".
- Every scenario in `## 📋 In-Scope Scenarios` is in G-W-T form (no prose-form scenarios).
- Open Questions are explicit handoffs to `plan`, not silent assumptions.

<!-- @hm:user:extra-quality-checks -->
<!-- Project-specific quality bar items. Preserved across harness-maker upgrades. -->
<!-- @hm:/user:extra-quality-checks -->



<!-- @hm:user:extensions -->
<!-- Free-form project-specific additions to the spec stage. Preserved across harness-maker upgrades. -->
<!-- @hm:/user:extensions -->


## Stage: plan

# Stage: plan

> Atomic stage. Implementation planning via deep interactive interview, ADR promotion, and validator-checked phase decomposition.

> Invoked as part of the **res-spec-plan** workflow.


## Communication Protocol

- Be direct and matter-of-fact. No flattery, no preamble, no "Great question!"
- If the user's reasoning is flawed, say so immediately with specific evidence.
- Don't fold on pushback — maintain position unless new evidence is presented.
- Lead with concerns before agreement. When agreeing, explain WHY.
- Never write a plan you cannot defend at code-review time.

## Purpose

Convert acceptance criteria into a concrete sequence of implementation phases. **The deep interview is the centerpiece** — architectural decisions locked in here define how `/hm:execute` will behave. Surface ambiguity here, not in code review. A thorough interview is worth 10× the time it saves in execute.

## When to Run

- After `spec` (or after `research` when `spec` is skipped).
- Before `execute` for any change touching more than 2-3 files or introducing new architectural elements.

## Inputs

- SPEC at `specs/SPEC-{slug}.md` (when present) — drives interview skip logic.
- Research notes at `work-docs/RESEARCH-{slug}.md` (when present).
- Existing TECH_SPEC.md, ADRs, prior PLANs in `work-docs/`.
- Codebase structure (modules, conventions, test layout).

## Procedure

### Step 0 — Skip heuristic (ALL 4 criteria must hold to skip the interview)

| Criterion | Skip condition |
|-----------|----------------|
| **Scope** | Single file OR config-only (typo, env var, doc copy) |
| **Architecture** | No component boundary changes, no new modules |
| **Contracts** | No API / IPC / DB schema / file format changes |
| **Risk** | Reversible in <1h with no user-facing impact |

If any criterion fails → **run the interview by default** (do not ask permission). When skipped, write a one-line justification under `## 🎙️ Interview Transcript` and proceed to Step 5.

### Step 1 — Pre-interview internal draft (NOT shown to user)

Synthesize a working plan from inputs:
- Tentative architecture (components, boundaries, data flow).
- Candidate phase decomposition.
- **Explicit list of ambiguities** ranked by blast radius (affects contracts > affects internal logic > affects naming).

This seed is what the interview refines. Investigate code unknowns with Read/Grep before treating them as ambiguities — don't outsource research to the user.

### Step 2 — SPEC inheritance check (when SPEC exists)

If `specs/SPEC-{slug}.md` exists:

1. **Read it fully**, including frontmatter `status:` and the `## ❓ Open Questions` section.
2. Branch on SPEC completeness:

   **Case A — `status: approved` AND `## ❓ Open Questions` is empty:**
   The user has already gone through `/hm:spec`'s 6-category interview, and every question was locked. Plan **SKIPS the deep interview**. Run only Step 3.0 (the brief lock-in confirmation below), then proceed to Step 4.

   **Case B — `status: draft` (open questions remain):**
   Plan inherits the resolved categories but **MUST** engage interview on the remaining ambiguities:
   - For each SPEC category already filled (Intent, Outcomes, In-Scope Scenarios, Non-Goals, Constraints, Verification): **do NOT re-ask**. Reference as `✅ {category}: {summary} (from SPEC)` in the round preamble's "decisions locked in" block.
   - For each entry in `## ❓ Open Questions`: open as a Phase 0 round.
   - Phase 0 remaining scope = (a) SPEC open questions, then (b) the **how** questions (architecture / phasing / risk / trade-offs).

   **Case C — no SPEC file:**
   Run the full Step 3 interview from scratch.

#### Step 3.0 — Brief lock-in confirmation (Case A only)

When SPEC is fully approved, the only remaining `/hm:plan` question is: **"Given this SPEC, are you ready for phase decomposition, or is there a how-question (architecture / phasing / library choice) you want to lock down first?"** Surface this as ONE `AskUserQuestion` with options:

- **"Proceed to phase decomposition"** — skip Step 3 entirely, jump to Step 4.
- **"One architectural decision first: {topic}"** — engage Step 3 for that single round only.
- **"Several architecture questions"** — engage full Step 3.
- **"Other"** — user free-form.

This single confirmation prevents the "I just answered every SPEC question — why is plan asking again?" foot-shooting.

### Step 3 — Interview loop (skipped in Case A; unlimited rounds otherwise)

> **If Step 2 set Case A and Step 3.0 returned "Proceed to phase decomposition": SKIP this entire step.** Jump to Step 4.

**Language rule (important):**
- **Live interview UI** → conduct in `en` (en→English, ko→Korean, ja→Japanese, others→English fallback). Round preamble, "decisions so far", open ambiguity explanations, AskUserQuestion prompts and option labels — all in `en`.
- **PLAN document on disk** → always English. Translate user's free-form answers when archiving in Step 5.

Each round runs Steps A–E.

#### Step A — Render current plan state (visualization OPTIONAL)

Visualization is NOT mandatory. Use only when it genuinely speeds comprehension. Format priority (most readable first):

1. **Prose / bullet summary** — default.
2. **Compact table** — when comparing alternatives across dimensions.
3. **ASCII boxes / arrows / trees** — when topology helps.
4. **Mermaid** — AVOID in live interview (renders as raw fenced code in terminal). OK in the final PLAN document.

Round preamble structure:

```
## Interview Round {N}

**Decisions locked in so far:**
- ✅ {Round 1 decision} (→ ADR-001)
- ✅ {Round 2 decision}

**Current plan state:**
{ASCII / bullets / table — whatever makes THIS decision easiest to see}

**Ambiguity to resolve this round:** {one specific thing}
**Why it matters:** {one-sentence impact of getting it wrong}
```

If nothing topologically changed since last round, skip the "current plan state" block.

#### Step B — AskUserQuestion (in `en`)

Constraints:
- **2-5 options per question**, each with trade-off in the label.
- **Every question includes "Other — let me describe"** as an explicit option.
- **From Round 2 onward**, include **"Plan is sufficiently clear — end interview"** on ONE foundational question per round. Not on Round 1 — require at least one substantive decision first.
- **Batch independent questions** (up to 4 per `AskUserQuestion` call). Independence test: "Would my choice of options or recommended default change based on the user's answer to another question in this batch?" If yes → separate rounds.
- **Never re-ask answered questions** — re-read prior Interview Entries before each round.
- **Never ask trivial questions** (naming conventions, file paths) — pick a defensible default and note it as an assumption.

**Question category priority** (ask in this order if multiple ambiguities remain):

1. Scope boundaries — in/out, breaking vs backward-compat
2. Architecture — component ownership, pattern choice
3. Contract shape — API signature, MQTT topic, DB schema, file format
4. Risk tolerance — staged/safe vs big-bang/fast, rollback strategy
5. Testing depth — unit / integration / manual
6. Implementation phasing — feature flag, sequence, dependencies
7. Dependencies — add library vs write own, upgrade vs pin
8. Failure handling — retry policy, circuit-break, fallback behavior
9. Observability — log level, metric names, alert thresholds

#### Step C — Record answer as Interview Entry

Append to internal transcript (written to PLAN in Step 5). Compact format (default):

```
| # | Topic | Category | Question (1 line) | Options | Choice | Note | → ADR |
```

Verbose format (when user asks for full audit trail):

```markdown
### Interview #{N} — {short topic}
**Round:** {N} | **Category:** {category} | **Promoted to ADR:** {ADR-XXX or "no"}

**Working assumptions at this point:**
- {assumption 1}

**Question asked:** {full prompt}

**Options presented:**
- A: {label} — {trade-off summary}
- B: {label} — {trade-off summary}
- Other — user-described

**User's choice:** {letter + label}
**Free-form note:** {verbatim or "—"}
**Impact on plan:** {which downstream sections this updates}
```

#### Step D — ADR promotion check

Promote the decision to a formal **Architecture Decision Record** if ANY of:
- Component boundary or ownership change.
- New or modified contract (API, IPC, schema, file format, wire protocol).
- Rejects a reasonably viable alternative.
- Long-term consequences beyond this task (sets precedent).
- Constrains future flexibility (locks in framework, library, protocol).

ADR template:

```markdown
### ADR-{NNN}: {Title}
**Status:** Accepted ({YYYY-MM-DD}, via /hm:plan interview)
**Context:** {1-2 sentences — why this decision was needed}
**Decision:** {1-2 sentences — what was chosen}
**Consequences:**
- ✅ {Positive outcome}
- ⚠️ {Trade-off accepted}
**Rejected alternatives:**
- {Option B} — Rejected because {specific reason}
**Source:** Interview #{N}
```

#### Step E — Exit check

Continue to next round UNLESS:
- User chose "Plan is sufficiently clear — end interview", OR
- Zero high/medium-impact ambiguities remain in the internal draft.

**No deferred decisions via checklist.** Before ending, scan the draft for "Accept?", "OK?", "Verify?", "Should we?", "Is this correct?" phrasings — each one is a missed round. The PLAN has no `## REVIEW CHECKLIST` section; all judgments live in the Interview Transcript or ADRs.

### Step 4 — Plan validation (`plan-validator` agent)

After the internal plan is complete (interview done, draft synthesized), invoke the `plan-validator` agent to critique it before writing to disk:

```
Task(
  subagent_type="plan-validator",
  description="Plan validator: {slug}",
  prompt="<full draft PLAN body + Interview Transcript + ADRs>\n\nReturn JSON: {overall: APPROVED|NEEDS_REVISION|MAJOR_REVISION, critiques: [...]}"
)
```

Resolution:
- **APPROVED** → write PLAN, proceed to Step 5.
- **NEEDS_REVISION** (warnings only) → run one follow-up interview round per warning. Options: A. revise plan / B. accept as risk (record in ADR) / C. reject / Other. Then write PLAN.
- **MAJOR_REVISION** (critical issues) → run follow-up rounds for each critical critique. After resolution, **re-run validator once only** (no infinite loop). If second pass still MAJOR_REVISION, ask user: A. proceed with remaining critiques as accepted-risk / B. abort planning.

Each follow-up interview answer is appended to `## 🎙️ Interview Transcript` and promoted to ADR when Step D criteria apply.

### Step 5 — Write PLAN document

Write to `work-docs/PLAN-{slug}.md` with the structure below.

**Required frontmatter:**

```yaml
---
type: plan
task_slug: {slug}
status: planning
created: {YYYY-MM-DD}
tags: [{project}, plan, {tech-stack}, {2-5 domain tags}]
spec: "[[SPEC-{slug}]]"  # OR omit when no SPEC exists
research_doc: "[[RESEARCH-{slug}]]"  # OR omit when /hm:research did not run
interview_rounds: {N}
adrs: {M}
validator_outcome: APPROVED | NEEDS_REVISION_RESOLVED | MAJOR_REVISION_RESOLVED
summary: "{≤100 char one-line TL;DR}"
---
```

**Required sections (in this order):**

1. **🎯 Executive Summary** — TL;DR, What/Why, Key Decisions (linking ADRs), estimated impact
2. **📚 Prior Work** — when relevant: similar PLANs, lessons from `failures.md` / `wiki.md`, RESEARCH.md findings
3. **🎙️ Interview Transcript** — compact table (verbose only on user request) listing every round
4. **📐 Architecture Decision Records** — every promoted ADR with full template
5. **🏗️ Technical Design** — Current State / Affected Components / Dependencies / Architecture / Design Decisions (referencing ADRs) / Data Flow / API Changes
6. **📝 Implementation Plan** — numbered phases. **Each phase MUST have**:
   - Scope (files in / out)
   - Exit criterion (a runnable command or check that proves the phase is done)
   - Risk: `low` | `medium` | `high`
   - Rollback point reference (which prior phase to revert to on failure)
7. **🧪 Testing Strategy** — unit / integration / manual steps
8. **⚠️ Risks & Mitigation** — risk register table
9. **✅ Success Criteria** — checklist mirroring SPEC verification criteria when SPEC exists
10. **🔍 Plan Validation** — append validator outcome (APPROVED / consensus critiques table / resolution links to interview rounds)

### Step 6 — Verify write

After writing, Read the file back and assert:
- Starts with `---` frontmatter.
- Contains `## 🎙️ Interview Transcript` with ≥1 entry (or skip-justification line).
- ADR count in frontmatter matches `## 📐 Architecture Decision Records` heading count.
- Every phase has all 4 required fields (scope / exit / risk / rollback).

If verification fails, retry write **once**. If still failing, surface the path + error and stop — do NOT proceed to a downstream stage.

## Outputs

- `work-docs/PLAN-{slug}.md` (frontmatter + 10 sections above)
- Interview Transcript as the single source of truth for user decisions
- ADR set bound to this PLAN (numbered ADR-001…)
- `validator_outcome` recorded in frontmatter

## Quality Bar

- An independent reader can predict the file diff per phase.
- Each exit criterion is checkable (script, test, or manual checklist).
- Risks are concrete, not platitudes ("might break things").
- Every architectural decision in `## 🏗️ Technical Design` links back to an ADR or Interview Entry.
- No `Accept? / Verify? / OK?` phrasing anywhere in the PLAN — those are missed interview rounds.
- Plan validator returned APPROVED, or the resolution path is fully recorded.

<!-- @hm:user:extra-quality-checks -->
<!-- Project-specific quality bar items. Preserved across harness-maker upgrades. -->
<!-- @hm:/user:extra-quality-checks -->



<!-- @hm:user:extensions -->
<!-- Free-form project-specific additions to the plan stage. Preserved across harness-maker upgrades. -->
<!-- @hm:/user:extensions -->


---

## Harness Configuration [MUST FOLLOW — overrides built-in defaults]

These values come from `.claude/harness.yaml` and **must not be replaced by
model defaults**. If a value conflicts with your training-data intuition, the
harness value wins.

| Key | Value |
|-----|-------|
| `reviewers.grade_threshold` | `A` |
| `reviewers.auto_fix` | `true` |
| `reviewers.max_review_rounds` | `3` |
| `reviewers.consensus` | `cross-check` |
| `dev_mode` | `task-driven` |
| `caching` | `agent-aware` |

Re-read `.claude/harness.yaml` whenever you are unsure of the current value.

---

## Inline overrides

Extra reviewers/skills can be activated for one invocation by passing flags:

    /hm:res-spec-plan <task description> --with-reviewers=security-reviewer,performance-reviewer
    /hm:res-spec-plan <task description> --with-skills=context-linter

Recognised flags parsed from `$ARGUMENTS`:

- `--with-reviewers=<csv>` — additionally activate these reviewers (must be in
  `harness.yaml`'s `reviewers.installed` list).
- `--with-skills=<csv>` — additionally activate these skills (must be in
  `harness.yaml`'s `skills.installed` list).
- `--no-auto-fix` — disable the review stage's auto-fix loop for this run
  (config default in `harness.yaml`'s `reviewers.auto_fix` is unchanged).
  Findings are still reported; no edits are applied.

Flags are additive to the harness defaults (`reviewers.enabled` /
`skills.enabled`) and apply only to this run. Unknown identifiers are warned
and ignored. The flags themselves are stripped from `$ARGUMENTS` before the
fused stages read the user's task description.
