---
generated_by: harness-maker
harness_maker_version: 0.52.1
generated_at: '2026-01-01T00:00:00+00:00'
source_template: commands/hm/atomic_command.md.j2
provenance: official
description: Lock what and why — acceptance criteria via a 6-category interview into
  a SPEC doc.
content_hash: bdb339fd194007dd7f63b6c1ac4a77c10a91ea4e5ba5def11f78be524abe25a8
---
> **Before you begin — outline your plan.** First check whether an autoloop is
> active **for THIS session** (session-scoped — a loop in another session must
> not suppress your banner). Loop-mode is active iff `$HM_SESSION_ID` matches a
> `.claude/.hm-loop-*` marker's `claude_session_id:` content header, OR a legacy
> `<project-root>/.hm-loop-active` exists (degraded fallback). The project root is
> above `.worktrees/` if your cwd is inside a `.worktrees/<name>/` worktree (strip
> the `/.worktrees/<wt-name>/` suffix, or `git rev-parse --show-toplevel` then walk
> up out of `.worktrees/`).
> **If loop-mode is active for this session, skip this banner entirely and operate
> without it** — the autoloop runs silently and a per-iteration banner would flood
> the transcript. Otherwise, print the start banner below (in the configured output
> language), then begin.

<!-- @hm:banner:start -->
> 🎯 **Goal:** one line — what this command will accomplish for the user.
> 📋 **Plan:** a short numbered list of the top-level steps you intend to take —
> for a single stage, its `Step` / `Phase` / `Check` headings; for a fused
> workflow, **one line per stage** (the `## Stage:` entries), not every sub-step.
> Present them as **intended, conditional** steps — skip heuristics, early-exit /
> early-FAIL rules, and any stage's own `STOP — do not proceed` boundary override
> this plan; never treat the banner as a commitment to run past a STOP.


<!-- @hm:autopilot-picker -->
> **Autopilot session start.** This harness is configured for
> autonomy (`autonomy.level: ask`). If loop-mode is active for
> this session (see above), SKIP this.
>
> **Arming works in every runtime; auto-advance does not.** Two different things used to sit
> under one "Claude Code only" label, which is why a Codex session reads this block and stands
> down. Arming writes a marker file — nothing runtime-specific. What IS Claude-Code-only is the
> *auto-advance* section at the end of a stage: it needs the `Skill` tool to invoke the next
> stage, and Cursor/Codex have none. So outside Claude Code, autopilot means **the gate answers
> are pre-approved** — you still start each stage yourself. Otherwise, at the first eligible stage, ask the CLI
> whether autopilot is already active — **never decide this from whether the marker file
> exists.** Nothing collects a stale one, so file-existence reads as "already armed" and
> autopilot silently never turns on — the usual reason it looks dead.
>
> `uv run --with $HOME/harness-maker hm autopilot status --root . --session-id "$HM_SESSION_ID"`
>
> Branch on **both** fields of the JSON (it always exits 0):
> - `active: true` → armed already. Skip the picker; do not re-arm.
> - `reason: "foreign"` → **rare** (one file per session): the file at YOUR key holds someone
>   else's id. **You cannot tell an active peer from one abandoned mid-pipeline**, so do not
>   guess and never `--force` on your own initiative. State it — `idle_minutes` is the owner's
>   silence, `null` = unknown — then ask: *is another Claude session open in this project?*
>   Only on **no**, re-run the arm command with `--force`. On yes, stay gated.
> - `reason: "degraded-idless"` → you have no session id and some peer does. **In Cursor and
>   Codex this is the NORMAL state, not a failure**: `HM_SESSION_ID` is published through
>   `$CLAUDE_ENV_FILE`, which only Claude Code provides. (In Claude Code it does mean a
>   SessionStart-hook failure.) Either way **arming is safe — say so and arm.** The command
>   below already handles it: an unset `$HM_SESSION_ID` expands to an empty string, which arms
>   the shared degraded marker. Accept `session_scoped: false` — every id-less session in this
>   project shares that one marker, so two Codex windows share an autopilot state.
> - `reason: "ask-pending"` → the normal path here (`level: ask`). Offer three options via
>   `AskUserQuestion` for the `research → spec → plan → execute → review → verify → wrapup` pipeline:
>   **`auto_safe`** (stops at the plan interview), **`auto_full`** (answers it, and an
>   APPROVED review's `human_review_needed`), or **gated**. A CHANGES_REQUESTED review and
>   the wrapup land stop at every level. Arm with the PICKED level:
> - anything else → offer ONCE via `AskUserQuestion`: "Run the
>   `research → spec → plan → execute → review → verify → wrapup` pipeline on autopilot this session
>   (stages auto-advance when no mandatory gate is pending), or stay gated?" On **yes**:
>   `uv run --with $HOME/harness-maker hm autopilot on --level <the level the user picked> --pipeline research,spec,plan,execute,review,verify,wrapup --session-id "$HM_SESSION_ID"`
>   On **no**, proceed gated — do not re-prompt unless the user asks.
>
> **Persistence:** the marker lives at the **project root** (a stage inside
> `.worktrees/<slug>/` sees it), is **one file per session** (`.hm-autopilot-<id>`, so two
> can be armed), and expires after 18h. `session_scoped: false` = no id (Cursor, Codex,
> hook failure) → you share `.hm-autopilot-degraded`. Commit
> `autonomy.autopilot_persistent: true` to auto-arm every session; the default is `false`.
<!-- @hm:/autopilot-picker -->



> **Output language.** Respond to the user in **en**
> (en→English, ko→Korean, ja→Japanese, others→English fallback) on **every turn** —
> the live chat output and the start/end summary banners, not only the onboarding
> interview. Code, identifiers, file paths, and the persisted deliverable documents
> (PLAN / RESEARCH / REVIEW / SPEC) stay in **English**.
<!-- @hm:output_language -->


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

!uv run --with $HOME/harness-maker hm memory_retrieve --topic "<topic>" --k 6 --pre-k 30

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

<!-- @hm:comprehension:brief -->
### Design brief — show this BEFORE the first interview round

`/hm:spec` has no architecture draft — its Step 1 is knowledge retrieval — so disclose what this
stage holds, in `en`, before the first category:

1. **Inherited scope** — what RESEARCH and any prior SPEC settled, so the user sees what is not
   being re-litigated.
2. **AC skeleton** — the criteria you can already draft, marked provisional.
3. **Category status** — of the six, which are answered, which are open, and which you will
   default rather than ask, with the default and its reason.

One screen. This is the overview layer; detail arrives per question, on demand.

#### 2.1 Six interview categories (in this order)

Skip a category when sufficiently answered by prior research, prior SPEC, or earlier rounds. Batch multiple independent questions per round when possible.

1. **Intent (Why)** — motivation, business / technical trigger. Often answered by `/hm:research`; confirm if so.
2. **Outcomes (What success looks like)** — observable end-state. Force the user to state "done" in observable terms, not implementation details.
3. **In-Scope Scenarios** — generate 2-4 scenarios in **Given-When-Then** form covering normal / edge / failure paths. This is mandatory format; reject prose like "the system handles errors" — restate as G-W-T.
4. **Non-Goals** — explicit out-of-scope list. Prevents scope creep in `plan`.
5. **Constraints** — HW, SW, security, performance, compatibility, **and test framework** (mandatory — pick `pytest` / `gtest` / `vitest` / `bats` / etc; `/hm:execute` Phase A uses this to write tests).
6. **Verification Criteria** — per-scenario, how we'll prove it: unit / integration / manual. Each scenario MUST map to at least one verification mode.

#### 2.1.5 — Oracle elicitation (MANDATORY — ADR-001/007 of spec-tetrad)

Verification *mode* (unit/integration/manual) is not the oracle. The **oracle**
is what decides *correct vs plausible-but-wrong* for a scenario — and in the LLM
era it is the scarce resource: `/hm:execute` must not invent an assertion derived
from the very code it checks (the **circular oracle**). For **every** acceptance
criterion / scenario, force two answers (closed-form — does not count against the
open-ended cap):

**(A) Oracle source** — pick one of:
- `golden` — a hardcoded expected value / fixture (where did it come from?).
- `differential` — a reference or second implementation the result is compared to.
- `property` — a metamorphic relation or invariant that holds for *all* inputs
  (e.g. `decode(encode(x)) == x`, idempotence, ordering) — independent of the impl,
  so the LLM cannot satisfy it by reading the code. Promotes the AC to `type: property`.
- `rubric` — human / LLM judgment against a named rubric.
- `consensus` — agreement of independent reviewers (k-of-3 / Codex second opinion).

**(B) Oracle evidence** — a one-line *independence* justification the
`spec_quality` gate will score (NOT the label): the golden's provenance, the
reference-impl identity, the metamorphic rationale ("why this relation holds
regardless of implementation"), the rubric_id, or the attestation reference.
**Reject "the test will check it"** the same way vague acceptance is rejected —
that is the circular oracle. A declared high-trust source with no evidence
**fails the gate** (spec-driven) or **requires a durable
`oracle_independence_waiver`** (task-driven).

For a `property` oracle, also collect the structured triple `input_domain` /
`transformation` / `expected_relation` (+ optional `preconditions` /
`observable_output`) — free-text alone is not gateable.

> **x-contract correspondence (documented, not a guaranteed isomorphism — ADR-005):**
> `oracle_source` ↔ sw-improve x-contract `conformance.kind`; `differential` ↔ a
> cross-language golden pin; `consensus` ↔ the adversarial 3-skeptic verify;
> mutation adequacy ↔ shared. `property` has no x-contract equivalent (new).

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


<!-- @hm:comprehension:round_state -->
**Round state — required when anything changed.** Open every round after the first with:

```
## Interview Round {N}

**Decisions locked in so far:**
- ✅ {decision} (→ ADR-XXX)

**Changed since last round:**
{the delta only — not a re-dump}

**Ambiguity to resolve this round:** {one specific thing}
**Why it matters:** {one-sentence impact of getting it wrong}
```

- **"Changed"** = a component, boundary, phase, or locked decision moved. Wording edits do not.
- **Round 1 has no base** — emit the full state, not a delta.
- **The final round emits a delta if one exists**, so the last thing seen is what the last
  answer moved.
- Nothing changed? Omit the block, but say "no change since last round" — an absence should be a
  statement, not an oversight.

### Step 3 — Write SPEC document

Write to `./specs/SPEC-{slug}.md`.

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

**Required machine.yaml schema (schema_version=2):**

> **Version note (ADR-006 of spec-tetrad):** new specs declare `schema_version: 2`.
> An **omitted** version pins to v1 (oracle_source NOT required) so legacy specs
> keep working; do NOT hand-edit a v2 oracle field into a v1 file — declare the
> version. v2 requires `oracle_source` + `oracle_evidence` on **every** AC.

```yaml
schema_version: 2
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
    type: mechanical | parametric | judgment | property   # ADR-003 + spec-tetrad
    test_ids:
      - tests/<path>::<fn_name>         # must resolve via `pytest --collect-only`
    executable_predicate: "<runnable Python expr>" # mechanical only (else null) — see note
    golden_table: []                              # parametric only
    rubric_id: null                               # judgment only
    pending_test: true                            # false ONLY when test_ids verified
    # --- oracle axis (v2, ADR-001/007) — REQUIRED on every AC ---
    oracle_source: golden | differential | property | rubric | consensus
    oracle_evidence: "<one-line independence justification the gate scores>"
    oracle_independence_waiver: null  # task-driven only: durable override reason
    # --- structured property fields (type: property only) ---
    input_domain: null        # e.g. "arbitrary UTF-8 strings"
    transformation: null      # e.g. "encode then decode"
    expected_relation: null   # e.g. "decode(encode(x)) == x"  (metamorphic/invariant)
    preconditions: []         # optional list
    observable_output: null   # e.g. "bytes"
    generator_hint: null      # advisory only — NOT a generator
```

**`executable_predicate` must be a *runnable* expression, not prose**
(PLAN-spec-test-accumulation ADR-007). `spec_machine.validate` now rejects a
mechanical AC unless its predicate `ast.parse`s as a Python expression whose
top-level node is a comparison / call / bool-op / unary-op and references at
least one symbol — `/hm:execute` turns it directly into a test assertion. Write
`result.retry_count <= 3` or `is_idempotent(send(msg))`, never `"retries are
bounded"` or the tautology `True`. Bind the free symbols to the system under
test; if you cannot yet name them, leave the AC `parametric`/`judgment` instead
of forcing a fake mechanical predicate.

Each AC's heading in SPEC.md must be `### AC-NNN: <title>` (NNN ≥ 3 digits)
to satisfy `spec_machine.cross_validate` rule 1. The title in `.md` and the
`title:` field in `.machine.yaml` must be similar within fuzzy ratio 0.85
(rule 2). At least one of `(test_ids != [])` OR `pending_test=true` per AC.

### Step 4 + 4.5 — Verify write, cross-validate, and score, in ONE call

After writing both files, run **one** command. It performs the schema validate, the
6-rule cross-validation, and the quality scoring of Step 4.5, and returns a single JSON
object — the three separate calls this replaced cost three round-trips for verdicts that
are always read together:

```bash
uv run --with $HOME/harness-maker hm spec_machine check --all \
  --yaml specs/SPEC-{slug}.machine.yaml \
  --md specs/SPEC-{slug}.md \
  --dev-mode task-driven
```

Returns `{ok, validate: {ok, errors}, cross_validate: {ok, errors, by_rule}, quality:
{overall, scores, weak_dimensions, blocked, dev_mode}}`. Exit 1 when validate or
cross-validate has errors, or when `quality.blocked`. `by_rule` buckets the
cross-validate errors under `rule-1`…`rule-6` plus `unattributed`.

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

### Step 4.5 — Spec quality gate (ADR-006) — read from the Step 4 payload

The `quality` block of the call above already carries this — do **not** issue a second
call. It scores the 5 narrative dimensions (completeness, testability, unambiguity,
consistency, scope_boundary) plus, because `--yaml` was passed, the 3 machine dims
`machine_verifiability`, `mutation_coverage_set` (Python only) and
`non_python_intent_alignment` (ADR-006).

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

**Stage terminal**: On success, output the SPEC path and its status (`draft` / `approved`), then **STOP**. Do not proceed to `/hm:plan` or any other stage without an explicit user command. This boundary must survive context compaction — the next stage is user-initiated. Exception: an auto-advance check below returning `proceed: true` supersedes this.

## Emit Gate 0 receipt (ADR-001, ADR-005)

You have completed the stage. Emit a receipt so the autoloop driver's Gate 0 can detect missing stages at the next convergence check. Pick `<verdict>`:

- **`pass`** — SPEC written with valid frontmatter; status is `draft` or `approved`.
- **`fail`** — SPEC write failed validation or the dual-file cross-validate step returned errors.
- **`skipped`** — **DO NOT emit this value from a stage prompt.** Reserved for the autoloop driver's auto-retry escape hatch (ADR-005 of PLAN-loop-mid-stop-and-review-skip).

The shell guard below makes the receipt a no-op when `.current-iter` is absent — that file is written only by the autoloop driver at iter start. Standalone runs (no autoloop), no-isolation runs, and post-`/compact` restoration before iter 1 all skip the write naturally. This is by design — Gate 0 only reads receipts written under `iter-N` for N≥1. In a standalone `/hm:spec` the driver has not written `.current-iter`, so the guard's `[ -f ]` test is false and no write fires.


```bash
!if [ -f "./.claude/.hm-iter-receipts/.current-iter" ]; then \
   ITER=$(cat "./.claude/.hm-iter-receipts/.current-iter" 2>/dev/null); \
   if [ -n "$ITER" ]; then \
     uv run --with $HOME/harness-maker hm iter_receipts write \
       --iter "$ITER" --stage spec --verdict <verdict> --root "."; \
   fi; \
 fi
```


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


<!-- @hm:autopilot-advance -->
## Auto-advance check (autopilot — Claude Code only)

Before the STOP banner below, check whether this session runs under **autopilot** (live
auto-advance, ADR-005) — **Claude-Code-only**: it needs the `.hm-autopilot` marker (armed
by the picker) and the `Skill` tool. **This section is a NO-OP** — fall straight through
to the STOP banner, running nothing below — **if any of: no `Skill` tool (Cursor/Codex),
no active marker, or loop-mode is on for THIS session (a `.claude/.hm-loop-*` marker
matches `$HM_SESSION_ID`, or a legacy `.hm-loop-active` exists).**

**Step 1 — mandatory gate FIRST (absent-case = STOP).** Evaluate THIS stage's gate
*before* anything else: No mandatory gate — spec may auto-advance.
If the gate is pending/unresolved → record it on the ledger, then **STOP** (print the
banner). Do NOT run the boundary check — a stage that stops at its gate must not record an
advance:

!uv run --with $HOME/harness-maker hm autopilot_caps gate-blocked --root . --stage spec --session-id "$HM_SESSION_ID"

**Step 2 — boundary check (ONLY when the gate is clear).** Run the deterministic check
(it enforces the Phase-5 runaway caps + kill switch, and on proceed records the advance it
authorizes — so it must run only after Step 1 clears):

If this stage has a slug, **append** it to the command below in single quotes — e.g.
` --slug 'my-task'`. Never a shell expression or a bracketed placeholder. Omit it
otherwise; the marker keeps the earlier stage's slug.


!uv run --with $HOME/harness-maker hm autopilot_caps boundary --root . --current spec --session-id "$HM_SESSION_ID" --step-cap 20 --time-cap-min 300

Read the JSON:
- `proceed: false` → **STOP** (print the banner) — **except `bad_slug`**. `step_cap`/
  `time_cap` = a runaway cap fired (`halted_cap` logged, marker cleared); `kill_switch` =
  autopilot off/expired; `merge_gate` = the next stage is human-gated (e.g. wrapup's
  merge/land — the marker was cleared, so invoke `/hm:wrapup` manually); `unknown_stage` =
  `--current` not in the pipeline; `pipeline_complete: true` = the pipeline finished and
  the marker was cleared.
  **`bad_slug` is yours to undo**: the `--slug` you passed is invalid; nothing was
  authorized. Do NOT print the banner — re-run with a corrected slug, or no flag.
- `proceed: true` → **auto-advance**: invoke `Skill(hm:<next_stage from the JSON>)` with
  the JSON's `task_slug` as its argument (omit when `null`), instead of the STOP banner.
  **This supersedes this stage's earlier "Stage terminal … STOP"** — that governs the
  gated path, and `proceed: true` IS the authorization it asks for. `task_slug_source:
  "persisted"` means the slug came from an earlier stage — name it before invoking, so
  another task's slug cannot advance silently.

<!-- @hm:/autopilot-advance -->

## Stage summary — print before you STOP

Skip this banner entirely if loop-mode is active for THIS session (a
`.claude/.hm-loop-*` marker matches `$HM_SESSION_ID`, or a legacy
`.hm-loop-active` exists — the autoloop uses machine receipts, not prose).
Otherwise emit it as your final output, in the configured output language:
<!-- @hm:banner:end -->
> ✅ **Done:** SPEC authored with observable acceptance criteria
> 📁 **Artifacts:** specs/SPEC-{slug}.md
> ➡️ **Next:** `/hm:plan {slug}` (STOP — user-initiated)


<!-- @hm:user:extra-quality-checks -->
<!-- Project-specific quality bar items. Preserved across harness-maker upgrades. -->
<!-- @hm:/user:extra-quality-checks -->



<!-- @hm:user:extensions -->
<!-- Free-form project-specific additions to the spec stage. Preserved across harness-maker upgrades. -->
<!-- @hm:/user:extensions -->
