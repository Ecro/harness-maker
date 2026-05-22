---
generated_by: harness-maker
harness_maker_version: 0.23.1
generated_at: '2026-01-01T00:00:00+00:00'
source_template: stages/spec.md.j2
provenance: official
content_hash: 0b38f11919eed82f20dd49baf3becef28931a2b924b7cd1612f6b8ad80693d83
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
# Repo memory — replace `<topic>` with the actual SPEC topic before running.

!uv run python -m harness_maker.memory_retrieve --topic "<topic>" --k 6 --pre-k 30

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

#### 2.5 — 5-Term Inequality Gate

Runs after the 6 structured categories are complete, before §2.2 promotion.
This gate surfaces requirements the structured categories miss by filtering
candidate follow-up questions through the 5-term inequality
(0.16.0, PLAN-deep-interview-question-criteria):

```
ask(Q) iff EIG(Q) ≥ ε  ∧  TaskRel·UserAns ≥ 0.7
        ∧ slot ∉ common_ground  ∧  confidence < τ
        ∧ open_ended_count < cap_locale
```

Continue using the configured locale for all live gate text.

**Skip if early exit**: If the user chose "SPEC is sufficiently clear — end
interview" in any prior §2.1 round, skip §2.5 entirely and proceed to §2.2.

**Term meanings (this stage's settings, rendered from harness.yaml):**

1. **EIG** — Expected information gain ≥ `ε = 0.5`. Skip Qs whose answer won't change SPEC content.
2. **CLARITI** — Task-relevance × user-answerability ≥ 0.7. Skip Qs the user cannot meaningfully answer right now.
3. **Common-ground** — Skip slots already determined by CLAUDE.md / harness.yaml / prior answers / RESEARCH frontmatter / same-slug PLAN|REVIEW history, **OR** by LLM self-inference at confidence ≥ 0.95 (kill-switch: `interview.deep_gate.common_ground.llm_inference_enabled: false` in harness.yaml).
4. **Confidence** — Slot's current resolution confidence must be `< τ = 0.7`.
5. **Open-ended cap** — At most `2` open-ended question(s) per turn for locale `en`. Closed-form (multi-select / yes-no) unrestricted.

<!-- F6-deferred: see inequality_gate.py; F6 wires the real mechanism.
     Locale cap above is render-time baked — re-render to refresh after locale change. -->

**Per-round display (ADR-005):**

```
✅ EIG ✅ CLARITI ❌ common-ground ✅ confidence ✅ open-ended → 4/5 met (NEEDS)
```

Render the checklist for EVERY candidate question. A candidate is asked iff
all 5 terms are ✅. The "common-ground" term is the primary defense against
asking obvious questions (silent-intent-miss telemetry per ADR-008 monitors
its post-hoc accuracy).

**Question generation:** LLM generates 1-3 follow-up candidates targeting the
SPEC slots Layer-0 categories did not lock down (WRONG / METHOD / STAKEHOLDER
/ STYLE / PERF style cues are inputs to the generator, not gating labels).
Ranking among passing candidates is by EIG descending.

**Exit:** Continue until either:
- All SPEC slots reach confidence ≥ τ (the inequality naturally stops the loop), OR
- User chooses "end interview" / "Proceed to §2.2 with current ambiguity accepted".

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

### Step 3.5 — Write SPEC.machine.yaml (ADR-006 dual-file)

Alongside SPEC.md write the machine-readable companion at
`specs/SPEC-{slug}.machine.yaml`. This carries the
fields that AI verifiers consume directly (test_ids[], executable_predicate,
golden_table, rubric_id, mutation_threshold, verification_tier) — values
the human SPEC.md describes but doesn't structure.

**Required machine.yaml schema (schema_version=1):**

```yaml
schema_version: 1
spec_slug: {slug}
parent_spec: SPEC-{l1-cluster-slug}   # null OR L1 file in same specs/ dir
verification_tier: 1 | 2 | 3          # T1/T2/T3 per ADR-008
mutation_threshold: 85 | 70 | null    # Python only; null = ADR-009 3-layer
mutation_threshold_rationale: "..."
last_mutation_run: null | "YYYY-MM-DD"
paths_to_mutate:                       # Python source files; reject `..` or absolute
  - src/<module>.py
spec_quality_score: null               # filled by Step 4.5
spec_quality_score_at: null
ac:
  - id: AC-001
    title: "<matches the ### AC-001 heading in .md within fuzzy ≥ 0.85>"
    type: mechanical | parametric | judgment    # ADR-003
    test_ids:
      - tests/<path>::<fn_name>         # must resolve via `pytest --collect-only`
    executable_predicate: "<Python expr>"        # mechanical only (else null)
    golden_table: []                              # parametric only
    rubric_id: null                               # judgment only
    pending_test: true                            # false ONLY when test_ids verified
```

Each AC's heading in SPEC.md must be `### AC-NNN: <title>` (NNN ≥ 3 digits)
to satisfy `spec_machine.cross_validate` rule 1. The title in `.md` and the
`title:` field in `.machine.yaml` must be similar within fuzzy ratio 0.85
(rule 2). At least one of `(test_ids != [])` OR `pending_test=true` per AC.

### Step 4 — Verify write + cross-validate dual-file contract

After writing both files, run:

```bash
python -m harness_maker.spec_machine validate specs/SPEC-{slug}.machine.yaml
```

Then the 6-rule cross-validation:

```bash
python -c "
from pathlib import Path
from harness_maker.spec_machine import cross_validate
errors = cross_validate(Path('specs/SPEC-{slug}.md'),
                        Path('specs/SPEC-{slug}.machine.yaml'))
for e in errors: print(e)
exit(1 if errors else 0)
"
```

Cross-validate enforces (ADR-007):
1. Every `ac.id` in .yaml has a matching `### AC-NNN` heading in .md.
2. `ac.title` in .yaml ≈ heading title (fuzzy ratio ≥ 0.85).
3. Every `test_ids[]` entry resolves via `pytest --collect-only` (skipped when `pending_test=true`).
4. Every `rubric_id` resolves under `.claude/rubrics/` or `templates/rubrics/`.
5. `verification_tier` matches `tier:` in .md frontmatter.
6. `parent_spec` resolves to an existing L1 SPEC file.

Plus the legacy .md checks:
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
      --arg machine "$(cat specs/SPEC-{slug}.machine.yaml)" \
      --arg mode "spec-driven" \
      '{spec_text: $spec, machine_yaml: $machine, dev_mode: $mode}' \
  | python -m harness_maker.spec_quality eval
```

The `machine_yaml` field (ADR-006) enables the 3 machine dims —
`machine_verifiability`, `mutation_coverage_set` (Python only),
`non_python_intent_alignment` — to be scored. Without it only the 5 narrative
dims are evaluated and the gate is less informative.

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
