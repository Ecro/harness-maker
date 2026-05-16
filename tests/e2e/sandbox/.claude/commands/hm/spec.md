---
generated_by: harness-maker
harness_maker_version: 0.12.0
generated_at: '2026-01-01T00:00:00+00:00'
source_template: commands/hm/atomic_command.md.j2
provenance: official
content_hash: ef99352d431a71b6a9ca392c248fbd8080b1a034edbabf7642c02b016b838ffe
---
# Stage: spec

> Atomic stage. Acceptance-criteria specification via 6-category interview. Owns **what / why / verification**. `plan` owns **how / risk / phasing**.


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
- Use the configured locale for every live round preamble, decisions-so-far
  block, ambiguity explanation, question text and option labels, score display
  labels, and validation prompt.
- Use `AskQuestion` (Cursor) or `AskUserQuestion` (Claude Code). **Batch independent questions** per round (independence test: would Q2's options change based on Q1's answer? if yes → separate rounds).
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

#### 2.5 — 3-Layer Deep Interview Gate

Runs after all 6 categories are complete (or skipped), before closing the
interview. This gate surfaces requirements the structured categories miss.
Continue using the configured locale for Layer 1/2 question text and option
labels, ambiguity explanations, score display labels, and validation prompts.

**Skip if early exit**: If the user chose "SPEC is sufficiently clear — end interview"
in any prior §2.1 round, skip §2.5 entirely and proceed to §2.2.

**Layer 1 — GCIC Gap Check**

Map the collected answers to 4 underspecification axes and score each
(0.0 = absent · 0.5 = partial/vague · 1.0 = clear and actionable):

- **Goals**: Intent + Outcomes clearly define the desired end-state?
- **Constraints**: Constraints category covers all inviolable boundaries?
- **Inputs**: Scenarios (Given clauses) + Constraints capture available resources?
- **Context**: Constraints / Non-Goals capture team / tooling / reviewer environment?

For any axis scoring below 0.7, apply the **CLARITI filter** before asking:
1. Task Relevance: "Does knowing this axis change the task outcome?" (0–1)
2. User Answerability: "Can the user realistically answer this now?" (0–1)
→ Ask only if **both ≥ 0.7**. Otherwise log `"LLM-inferred"` and skip.

**Layer 2 — Implicit Probing**

Read all collected answers. Dynamically generate 1–3 reverse questions from
the candidate types most relevant to this specific context (apply CLARITI filter
to each candidate before selecting):

Five candidate types (use short label to track across rounds):
- **WRONG**: "What would make you say the result is **wrong**?" → implicit rejection criteria
- **METHOD**: "What assumptions about **how** this will be built?" → implicit method constraints
- **STAKEHOLDER**: "Who else reviews/uses this output and by what standard?" → implicit stakeholders
- **STYLE**: "What **format or style** constraints apply?" → style (hardest type to elicit)
- **PERF**: "What **performance or scale** expectations exist?" → implicit benchmarks

**MUST NOT reuse a type label** from a prior gate round (track: WRONG/METHOD/STAKEHOLDER/STYLE/PERF used).
Batch Layer 1 and Layer 2 questions into a single `AskQuestion` (Cursor) or `AskUserQuestion` (Claude Code) call (max 4).

**Layer 3 — Ambiguity Score (display every round)**

After receiving answers, compute and display:

```
Ambiguity Score: {X.X}/1.0  (Goal×40% + Constraint×30% + SC×30%)
  Goals:             {g:.1f}/1.0  ✅ or ⚠️  (threshold 0.8)
  Constraints:       {c:.1f}/1.0  ✅ or ⚠️
  Success Criteria:  {sc:.1f}/1.0 ✅ or ⚠️
  Weighted total:    {g*0.4 + c*0.3 + sc*0.3:.2f}
  → PASS or NEEDS  (streak: {N}/2)
```

Inputs/Context gaps resolved in Layer 1 are absorbed into Goals/Constraints
scores respectively. Score monotonicity rule: score must not decrease from the
prior round given the same answer set; a drop ≥ 0.1 requires a one-line
`[score-drop-reason]: ...` note appended to the Layer 3 display, then applied.

**Convergence**: total ≥ 0.8 AND all dims ≥ 0.7, **2 consecutive rounds** → PASS.
On **NEEDS**: return to Layer 1 (focus on failing axis), new Layer 2 probes (no
repeats). Max **3 rounds** total. After 3 NEEDS, offer via `AskQuestion` (Cursor) or `AskUserQuestion` (Claude Code):
- A: "Proceed — accept current ambiguity and move to §2.2"
- B: "Refine further — return to Layer 1 with new focus"

---

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

**Stage terminal**: On success, output the SPEC path and its status (`draft` / `approved`), then **STOP**. Do not proceed to `/hm:plan` or any other stage without an explicit user command. This boundary must survive context compaction — the next stage is user-initiated.

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
