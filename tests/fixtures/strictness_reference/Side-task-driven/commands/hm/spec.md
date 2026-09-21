---
generated_by: harness-maker
harness_maker_version: 0.58.0
generated_at: '2026-01-01T00:00:00+00:00'
source_template: commands/hm/atomic_command.md.j2
provenance: official
description: Lock what and why — acceptance criteria via a 6-category interview into
  a SPEC doc.
content_hash: a764b11fd599fe2fc9ee0b4a3ada011f81c256774f998778ba4bb93d6f498016
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
> **Autopilot session start.** This harness is configured for autonomy (`autonomy.level: ask`).
> **Arming works in any runtime**; only end-of-stage auto-advance needs Claude Code's `Skill`
> tool. If loop-mode is active for this session (see above), SKIP this. Otherwise, at the first eligible stage, ask the CLI
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
> - `reason: "degraded-idless"` → no id of your own: **NORMAL state, not a failure** in Cursor/Codex (`$CLAUDE_ENV_FILE` is Claude-Code-only), a hook failure in Claude Code.
>   Arm either way — unset expands to `""` and arms the shared degraded marker.
> - `reason: "ask-pending"` → the normal path here (`level: ask`). Offer three options via
>   `AskUserQuestion` for the `research → spec → execute → review → verify → wrapup` pipeline:
>   **`auto_safe`** (stops at the plan interview), **`auto_full`** (answers it, and an
>   APPROVED review's `human_review_needed`), or **gated**. A CHANGES_REQUESTED review and
>   the wrapup land stop at every level. Arm with the PICKED level:
> - anything else → offer ONCE via `AskUserQuestion`: "Run the
>   `research → spec → execute → review → verify → wrapup` pipeline on autopilot this session
>   (stages auto-advance when no mandatory gate is pending), or stay gated?" On **yes**:
>   `uv run --with $HOME/harness-maker hm autopilot on --level <the level the user picked> --pipeline research,spec,execute,review,verify,wrapup --session-id "$HM_SESSION_ID"`
>   On **no**, proceed gated — do not re-prompt unless the user asks.
>
> **Persistence:** the marker lives at the **project root** (a stage inside
> `.worktrees/<slug>/` sees it), is **one file per session** (`.hm-autopilot-<id>`, so two
> can be armed), and expires after 18h. `session_scoped: false` = no id (Cursor, Codex,
> hook failure) → you share `.hm-autopilot-degraded`. Commit
> `autonomy.autopilot_persistent: true` to auto-arm every session; the default is `true`.
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
- `/hm:execute` Step 0 can decompose into phases that each map back to a SPEC scenario.
- `/hm:execute` Phase A can author tests **directly from the SPEC**, not from planner intent.
- `/hm:wrapup` Drift gate can compare actual diff against SPEC scope.

This is the **only** interview in the pipeline. It owns **what**, **why** and **how to verify**, plus the decisions that cannot be cheaply undone. *How to build* — phases, ordering, risk — is authored by `/hm:execute` Step 0 with no human gate.

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

When skipped: write a minimal SPEC (Intent + 1 happy-path scenario in G-W-T form + Verification = "manual smoke") and continue. Do NOT ask permission to skip — proceed and log rationale in the SPEC's `## Refinement Decisions` section. Its machine.yaml is `schema_version: 3` with `irreversible_decisions: []` (the four criteria above rule out every irreversible category), and it is stamped **exempt** — no identity, no prompt; the stamp stays valid only while the list stays empty:


```bash
!uv run --with $HOME/harness-maker hm spec_machine approve --yaml specs/SPEC-{slug}.machine.yaml --exempt
```


### Step 0.5 — Objective context (intent layer — one line and continue when unused)

> Relocated from `/hm:plan` by SPEC-plan-stage-absorption: the objective link is DRI lock-in,
> which is what the SPEC owns. It runs before the interview so the answer is available to it.

Read the intent state — LLM-free. (`/hm:loop` iterations inherit `objective:` from the master PLAN, so this is the one place a task acquires it.)


```bash
!uv run --with $HOME/harness-maker hm world status --json   # loads .claude/intent.yaml + .claude/world/assumptions.yaml
```


- `state: not_filled_in` / `invalid` → print `[intent] no objectives — skipping` and continue. That line is the whole cost for a project that does not use the layer.
- Filled in but **no `active` and no `proposed` objective** (the first objective has not been written yet) → skip the pick and go straight to the consent question below: **"Draft an objective for this task?"**
- Otherwise ask ONE closed question with `AskUserQuestion`: **"Which objective does this task serve?"** — one option per `active` / `proposed` objective (id + title) plus **"none"**. Step 3 writes the answer into the SPEC frontmatter as `objective: <id>` (omitted on "none").
- On **"none"**, ask once, closed: **"Draft an objective for this task?"** Yes records consent only — Step 4.9 writes after the interview closes. No: write nothing and continue.
- Then compare the work this SPEC scopes against each objective's `rejected[]` list (your judgment — read the records). For each matching objective:

  ```bash
  !uv run --with $HOME/harness-maker hm world objective revisit <objective-id> --json
  ```

  Show its title, condition and last value. `candidate` = the revisit condition holds — surface it as a revisit *candidate* in the design brief; `not_met` / `unevaluable` = show and continue. This check never blocks.

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

### Step 2 — Interview (default ON; up to 5 rounds)

> `interview.main_loop.max_rounds` used to bound `/hm:plan`'s loop and had no other
> consumer. SPEC-plan-stage-absorption left this as the only interview in the pipeline, so
> the knob applies here — a user who set it would otherwise find it silently inert.

Interview UX rules:
- **Live UI** in `en` (en→English, ko→Korean, others→English fallback).
- **SPEC document on disk** always English. Translate user's free-form answers when archiving.
- Use the configured locale for every live round preamble, decisions-so-far
  block, ambiguity explanation, question text and option labels, score display
  labels, and validation prompt.
- Use `AskQuestion` (Cursor) or `AskUserQuestion` (Claude Code). **Batch independent questions** per round (independence test: would Q2's options change based on Q1's answer? if yes → separate rounds).
- Always include **"Other — let me describe"**.
- From Round 2 onward, include **"Approve this SPEC and end interview"** on one foundational question per round. Choosing it is the DRI's acceptance of the SPEC — remember it and stamp it in Step 5, after the files pass Step 4. It is the only approval: no answer, no question tool, or loop mode never counts as one.
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
4. **Non-Goals** — explicit out-of-scope list. Prevents scope creep when `/hm:execute` authors the PLAN.
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

**Irreversible decisions (every SPEC — `irreversible_decisions`).** Before closing, list the
decisions this change makes that cannot be cheaply undone, judged against five categories:
schema/file format/storage layout · public API/CLI contract · data migration ·
security/permission boundary · new external dependency. Use the narrowing questions only to
**drop** candidates — could two units working independently choose incompatibly? is the call
non-obvious? is it a real trade-off? — never to exclude an obviously destructive change; cost,
scale and compliance are judgment examples inside a category, not categories. Each entry is
`{id: IRR-NNN, decision, category, rationale, source: spec}` with sequential ids that are never
renumbered. Show the list to the DRI in the interview (they add or remove entries); an empty
list is valid and is written as `irreversible_decisions: []`.

**Open-ended cap** (follow-ups after the six categories): at most `2` open-ended question(s) per turn for locale `en`; closed-form (multi-select / yes-no) questions are unrestricted. Ask a follow-up only when its answer would change SPEC content and the user can answer it now; stop when every SPEC slot is settled or the user ends the interview.

---

#### 2.2 Promotion rule

SPEC's substantive decisions (e.g., "what counts as done for Scenario 2?", "fail-closed vs fail-open?") live in the SPEC's `## ❓ Open Questions` section with the resolution, and the ones that cannot be cheaply undone go in `irreversible_decisions`. **SPEC has no ADR section.** `/hm:execute` Step 0 records the design ADRs it locks while authoring the PLAN.

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
interview_rounds: {N}   # rounds this interview took; 0 when Step 0 skipped it
objective: <id>   # ONLY when Step 0.5 picked one or Step 4.9 drafted one; omit on "none"
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
6. **🔒 Irreversible Decisions** — table `| Id | Decision | Category | Rationale |`, one row per `irreversible_decisions` entry (write "none" when the list is empty).
7. **✅ Verification Criteria** — per-scenario:
   | Scenario | Verification mode | Test name / manual step |
   |---|---|---|
   | S1 | unit | `test_s1_happy_path` |
   | S2 | integration | `test_s2_with_db` |
   | S3 | manual | "open settings, click X, confirm Y" |
8. **❓ Open Questions** — items the user could not resolve in interview. These reach `/hm:execute` Step 0, which resolves them as design ADRs while authoring the PLAN. Empty list = SPEC ready to implement.
9. **🔍 Refinement Decisions** — 1-line per round summarizing what was locked in (or "skipped — task is trivial: {reason}").

### Step 3.5 — Write SPEC.machine.yaml (ADR-006 dual-file)

Alongside SPEC.md write the machine-readable companion at
`specs/SPEC-{slug}.machine.yaml`. This carries the
fields that AI verifiers consume directly (test_ids[], executable_predicate,
golden_table, rubric_id, mutation_threshold, verification_tier) — values
the human SPEC.md describes but doesn't structure.

**Required machine.yaml schema (schema_version=3):**

> **Version note (ADR-006 of spec-tetrad):** new specs declare `schema_version: 2`.
> An **omitted** version pins to v1 (oracle_source NOT required) so legacy specs
> keep working; do NOT hand-edit a v2 oracle field into a v1 file — declare the
> version. v2 requires `oracle_source` + `oracle_evidence` on **every** AC.
> **v3 (SPEC approval)** additionally requires `irreversible_decisions` (a list, possibly empty).
> Never hand-write `approval:` — `hm spec_machine approve` writes it, bound to a hash of every
> authored field (tooling fields such as `test_ids` / `pending_test` are excluded).

```yaml
schema_version: 3
spec_slug: {slug}
irreversible_decisions:               # [] when none — the key is required at v3
  - id: IRR-001
    decision: "<what is decided>"
    category: public API/CLI contract   # one of the five categories
    rationale: "<why it cannot be cheaply undone>"
    source: spec                        # execute when appended during /hm:execute
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

### Step 4.6 — `spec-validator` (single pass, advisory)

**Trigger.** Dispatch ONLY when this SPEC declares a non-empty `irreversible_decisions`, or the
ACs **imply** a decision in one of the five categories, or Step 0's skip heuristic did not fire.
A Step-0 skip-path SPEC with `irreversible_decisions: []` is **not** dispatched — a critic on a
trivial SPEC re-imposes the ceremony a light SPEC exists to avoid. Say in one line which branch
you took; a silent skip and a silent run are indistinguishable afterwards.

**One pass. There is no re-validation.** The agent it relocates (`plan-validator`) returned
`APPROVED` 0 times in 54 runs, so a second pass buys findings, not release.



Dispatch each item below with the `Task` tool.

```
Task(subagent_type="spec-validator", description="Spec validator: {slug}", prompt="<the full SPEC body + its .machine.yaml + the RESEARCH document when one exists>

Critique the four categories you are accountable for: missing or contradictory ACs, circular oracles, irreversible decisions the ACs imply but `irreversible_decisions` does not list, and scope boundary.

Return ONLY the JSON output as specified in your instructions.")
```

**The verdict does not gate anything.** Record `overall_assessment` and the `critiques` under
the SPEC's `## ❓ Open Questions` (or a `## 🔎 Spec Validation` section when the list is long),
surface the `critical` findings in your turn output, and **continue to Step 5 regardless**. The
DRI decides what to do with them; `MAJOR_REVISION` is a description of the findings, never an
instruction to halt. Its discrimination is unmeasured, and an unproven gate must not hold a
release while it is being measured.



### Step 4.9 — Objective draft (consented at Step 0.5)

Only when Step 0.5 recorded consent. Derive from the interview + RESEARCH: `<ID>` = `OBJ-` +
the task slug upper-cased, `--title`, `--hypothesis`, one `--scope` per in-scope item,
`--outcome` = the outcome the interview named (none fits → say so and skip). Show the
arguments, run once:


```bash
!uv run --with $HOME/harness-maker hm world objective new <ID> --title "<title>" --hypothesis "<hypothesis>" --scope "<item>" --outcome <outcome-id> --from-proposal --candidates 1
```


Carry `<ID>` into the SPEC frontmatter's `objective:`. If the verb refuses (id exists, unknown outcome):
print the refusal and continue with no link — never retry with a mutated id. The record is
`proposed`: the gate halts with `not_active` until a human runs `approve` + `activate`; an
orphan is retired with `objective drop`.

### Step 5 — Status update

If `## ❓ Open Questions` is empty: update frontmatter `status: approved`. Otherwise `status: draft`.

The user can resume by editing the SPEC directly or re-running `/hm:spec {slug}` (interview will read the existing SPEC and re-engage on draft items).

**Stamp the DRI's acceptance.** Only when the DRI chose "Approve this SPEC and end interview"
(and Step 4 passed), record it — content hash, base-root identity, time:


```bash
!uv run --with $HOME/harness-maker hm spec_machine approve --yaml specs/SPEC-{slug}.machine.yaml
```


Otherwise leave the SPEC unstamped: autopilot stops at this stage, and `/hm:wrapup` asks again
before landing. `status:` above is the document lifecycle; acceptance lives only in `approval`.

**Stage terminal**: On success, output the SPEC path and its status (`draft` / `approved`), then **STOP**. Do not proceed to `/hm:execute` or any other stage without an explicit user command. This boundary must survive context compaction — the next stage is user-initiated. Exception: an auto-advance check below returning `proceed: true` supersedes this.

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

- `specs/SPEC-{slug}.md` — frontmatter + 9 sections above.
- Status: `draft` (open questions remain) or `approved` (ready for `/hm:execute`).

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
*before* anything else: Read the SPEC's acceptance with `hm spec_machine approval-status --root . --slug <slug>`: pass --judgment-gate clear when state is approved or exempt, blocked when malformed, pending otherwise. The boundary re-derives the same verdict from the SPEC, so a clear the SPEC does not support never advances. At auto_full a pending is answered WITHOUT writing an approval — the land hold covers the SPEC's irreversible decisions.
Do NOT stop here and do NOT run `gate-blocked`. Classify the gate and carry the verdict into
Step 2, which records the stop for you. Exactly one of:
- **`clear`** — nothing pending.
- **`pending`** — a genuine judgment is unresolved: a question with a defensible answer.
  Stops at `gated`/`auto_safe`; `auto_full` answers it.
- **`blocked`** — the failing half is a **quality threshold**, not a question (a failed grade,
  a failed check). **No level clears it, `auto_full` included.**

**Unsure at any boundary → pick the more restrictive value.** The ladder is
`clear` < `pending` < `blocked`. That direction is deliberate: `pending` is the one value
`auto_full` clears, so resolving uncertainty downward routes a possible failure past the gate.

Omitting the flag entirely is **not** `pending` — it halts at every level, including
`auto_full`, and reports a stale render. Say nothing only when you mean "I did not classify".

**Step 2 — boundary check.** Run the deterministic check
(it enforces the Phase-5 runaway caps + kill switch, and on proceed records the advance it
authorizes — so it must run only after Step 1 clears):

If this stage has a slug, **append** it to the command below in single quotes — e.g.
` --slug 'my-task'`. Never a shell expression or a bracketed placeholder. Omit it
otherwise; the marker keeps the earlier stage's slug.

**Also append your Step 1 verdict** — exactly one of ` --judgment-gate clear`,
` --judgment-gate pending`, or ` --judgment-gate blocked`. A literal word, never a
placeholder. **Omitting it is not a way to say `pending`**: an absent verdict halts at every
level, `auto_full` included, and reports a stale render.


!uv run --with $HOME/harness-maker hm autopilot_caps boundary --root . --current spec --session-id "$HM_SESSION_ID" --step-cap 20 --time-cap-min 300

Read the JSON:
- `proceed: false` → **STOP** (print the banner) — **except `bad_slug`**. `step_cap`/
  `time_cap` = a runaway cap fired (`halted_cap` logged, marker cleared); `kill_switch` =
  autopilot off/expired; `merge_gate` = the next stage is human-gated (e.g. wrapup's
  merge/land — the marker was cleared, so invoke `/hm:wrapup` manually); `unknown_stage` =
  `--current` not in the pipeline; `pipeline_complete: true` = the pipeline finished and
  the marker was cleared.
  `judgment_gate` = the gate was `pending` at a level that does not
  clear it, or `blocked` (which no level clears). The marker was **preserved** and the stop
  was recorded; resolve the gate and re-run.
  **`bad_slug` is yours to undo**: the `--slug` you passed is invalid; nothing was
  authorized. Do NOT print the banner — re-run with a corrected slug, or no flag.
- `proceed: true` → **auto-advance**: invoke `Skill(hm:<next_stage from the JSON>)` with
  the JSON's `task_slug` as its argument (omit when `null`), instead of the STOP banner.
  **This supersedes this stage's earlier "Stage terminal … STOP"** — that governs the
  gated path, and `proceed: true` IS the authorization it asks for. `task_slug_source:
  "persisted"` means the slug came from an earlier stage — name it before invoking, so
  another task's slug cannot advance silently.
- `judgment_auto_answered: true` → the level cleared a judgment gate for you. **Do what
  `judgment_directive` says before advancing.** An auto-answer that is not written down is
  an unauditable skip of a human decision — the record is the only thing that makes this
  level reviewable after the fact.

<!-- @hm:/autopilot-advance -->

## Stage summary — print before you STOP

Skip this banner entirely if loop-mode is active for THIS session (a
`.claude/.hm-loop-*` marker matches `$HM_SESSION_ID`, or a legacy
`.hm-loop-active` exists — the autoloop uses machine receipts, not prose).
Otherwise emit it as your final output, in the configured output language:
<!-- @hm:banner:end -->
> ✅ **Done:** SPEC authored with observable acceptance criteria
> 📁 **Artifacts:** specs/SPEC-{slug}.md
> ➡️ **Next:** `/hm:execute {slug}` (STOP — user-initiated)


<!-- @hm:user:extra-quality-checks -->
<!-- Project-specific quality bar items. Preserved across harness-maker upgrades. -->
<!-- @hm:/user:extra-quality-checks -->



<!-- @hm:user:extensions -->
<!-- Free-form project-specific additions to the spec stage. Preserved across harness-maker upgrades. -->
<!-- @hm:/user:extensions -->
