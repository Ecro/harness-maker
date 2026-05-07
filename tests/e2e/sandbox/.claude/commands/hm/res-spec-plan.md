---
generated_by: harness-maker
harness_maker_version: 0.5.7
generated_at: '2026-01-01T00:00:00+00:00'
source_template: commands/hm/workflow_command.md.j2
provenance: official
content_hash: cf7e750ca0ad9c197c79b6affc59b2c2ce0d4eb061c214870f4748b742ec4427
---
# /hm:res-spec-plan


## Stage: research

# Stage: research

> Atomic stage. Information gathering and best-practice exploration.

> Invoked as part of the **res-spec-plan** workflow.


## Purpose

Gather sufficient context before committing to a plan. Surface unknowns, prior
art, library docs, and architectural constraints so that downstream stages
(`spec`, `plan`, `execute`) can proceed without rework.

## When to Run

- Starting a new feature or change in an unfamiliar area of the codebase
- Selecting between competing approaches (libraries, patterns, algorithms)
- Investigating a bug whose root cause is unclear
- Before writing a SPEC for a non-trivial change

## Inputs

- User question, task description, or feature request (`$ARGUMENTS`)
- Codebase context (relevant files, prior PLANs, prior REVIEWs)
- Memory tiers: session log (hot), failures + wiki (warm) — see loading order below

## Session Context Loading

Before starting, load memory in tier order (stops at first miss per tier):

1. **Hot tier** — Read `.claude/memory/session/<today's date>.md` in full if it
   exists. Compaction checkpoint entries reveal where the prior session ended.
2. **Warm tier** — Skim `.claude/memory/failures.md` (first 60 lines).
   Search for relevant entries: `rg -F "[fail:" .claude/memory/failures.md`
3. **Warm tier** — Skim `.claude/memory/wiki.md` (first 60 lines).
   Search for relevant entries: `rg -F "[wiki:" .claude/memory/wiki.md`

## Procedure

1. Identify the scope. State explicitly what is in/out of scope.
2. Search prior art (using loaded memory above as starting point):
   - Targeted grep: `rg -F "[wiki:<keyword>]" .claude/memory/wiki.md`
   - Targeted grep: `rg -F "[fail:<keyword>]" .claude/memory/failures.md`
   - Codebase patterns via Grep/Glob
3. Fetch external documentation when a library/framework/API is involved.
   Prefer official docs over training data — versions drift.
4. Enumerate alternatives. For each, capture: assumption, evidence, trade-off.
5. Surface open questions for the user before SPEC. Use AskUserQuestion when
   the answer would change the chosen approach.

## Outputs

- Research notes summarising:
  - Scope
  - Alternatives considered
  - Recommended direction with rationale
  - Open questions (if any)
- Updated reading list / external references for the plan stage

## Quality Bar

- No "I don't know" surprises in later stages on points covered here
- Recommendation is grounded in evidence, not authority
- Open questions are explicit, not hidden as assumptions

<!-- @hm:user:extra-quality-checks -->
<!-- Project-specific quality bar items. Preserved across harness-maker upgrades. -->
<!-- @hm:/user:extra-quality-checks -->



<!-- @hm:user:extensions -->
<!-- Free-form project-specific additions to the research stage. Preserved across harness-maker upgrades. -->
<!-- @hm:/user:extensions -->


## Stage: spec

# Stage: spec

> Atomic stage. Acceptance-criteria specification.

> Invoked as part of the **res-spec-plan** workflow.


## Purpose

Convert a task description into testable acceptance criteria so that
implementation has an objective definition of "done" and the test stage
has something concrete to write tests against.

## When to Run

- After `research` for non-trivial features
- Before `plan` whenever the change is observable to a user, an API consumer,
  or another module
- Skipped for: docs-only changes, single-file refactors, trivial bug fixes

## Inputs

- Research notes (if `research` was run)
- User requirements / acceptance constraints
- Existing SPEC if this is an evolution of prior behaviour

## Procedure

1. Write the user-facing summary in 2-3 sentences. If it doesn't fit, the
   spec is still too broad.
2. Enumerate behaviours as numbered acceptance criteria. Each MUST be:
   - Observable (you can write a test that fails before, passes after)
   - Independent (one criterion per concern)
   - Bounded (no "etc.", no "and other related cases")
3. List explicit non-goals. What this SPEC does NOT cover.
4. Capture edge cases and error modes. Each becomes a criterion.
5. Note open questions and resolve them via AskUserQuestion before
   marking the SPEC ready.

## Outputs

- `specs/SPEC-{slug}.md` with frontmatter:
  - `type: spec`
  - `status: draft | approved`
  - `task_slug:`, `created:`, `tags:`
- Acceptance criteria numbered AC-1, AC-2, ...
- Non-goals section
- Open questions section (empty when status=approved)

## Quality Bar

- A test author can write tests directly from the criteria without guessing
- Criteria are not implementation details — they describe behaviour
- Non-goals prevent scope creep in `plan` and `execute`

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
1. Read it fully.
2. For each SPEC category already filled (Intent, Outcomes, In-Scope Scenarios, Non-Goals, Constraints, Verification): **do NOT re-ask** in the interview. Reference it as `✅ {category}: {summary} (from SPEC)` in the round preamble's "지금까지 확정된 것" / "decisions locked in" block.
3. Phase 0 remaining scope becomes the **how** questions (architecture / phasing / risk / trade-offs), not the **what** questions.

### Step 3 — Interview loop (unlimited rounds, user-controlled exit)

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
