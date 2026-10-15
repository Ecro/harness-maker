---
type: spec
task_slug: hm-light-lane-s3c
status: draft
created: 2026-10-15
tags: [harness-maker, spec, cost, light-lane, preamble, cli-output, plan, machine-spec]
test_framework: pytest
tier: 2
interview_rounds: 0
lane: full
intent: HM-LIGHT-LANE
research_doc: "[[RESEARCH-hm-light-lane]]"
summary: "Stage 3c of HM-LIGHT-LANE: one stage preamble per session, a quiet spec_machine check, a short PLAN and minimal machine.yaml on light"
---

# SPEC — hm-light-lane-s3c (stage 3c, three token cuts)

## 🎯 Intent

After stage 3a, a small /hm: task still carries text it does not use. The 2026-10-15 breakdown of
17 completed bench runs (`token-breakdown-2026-10-15.md`) names three sources. The same stage
preamble is loaded once per stage. `hm spec_machine check` prints about 10k chars per run. The
light lane still writes a full-template PLAN and a full machine.yaml. The DRI decided all three
("Cut") on the 2026-10-15 decision cards: **A** load the preamble once, **B** make the hm CLIs
quiet on success, **C** write less paperwork on `lane: light`. After spec-validator pass 1, C is a
**short light PLAN**, not "no PLAN" (Refinement Decisions).

## 🌅 Outcomes

Measured on this repo's committed `.claude/harness.yaml` with
`tests/structural/_surface_baseline.render_surface()` at `a7403f2f` unless a line says otherwise.

### A — One preamble

- The preamble (start banner, autopilot picker, output-language block) is 4,362 chars and is
  byte-identical in all six Claude stage commands (research, spec, execute, review, verify,
  wrapup). It moves, byte for byte, into a new reference file `.claude/hm/stage-preamble.md`.
- Each command keeps a pointer of at most 650 chars in its place. The pointer separates **read
  once** from **apply every stage**:
  - Read the file from the project root, never from `<WT>`, unless this session's context
    already holds it from an earlier `/hm:` stage.
  - **Either way**, apply it to this stage, in order: the loop-mode check, then this stage's
    start banner, then the autopilot picker, only if the picker has not been answered this
    session.
- The pointer keeps the `<!-- @hm:banner:start -->` and `<!-- @hm:output_language -->` markers.
- `/hm:health` changes slightly. When a stage command names `stage-preamble.md`,
  `readiness._dim_workflow_clarity`'s two signals (`output_language_present`,
  `start_end_summary_present`) also require `.claude/hm/stage-preamble.md` to exist and carry
  both markers. Without it, they fail and name the file. An older render whose commands carry
  the inline preamble and name no such file is scored as today, so it stays valid.
- A missing file is not a STOP. The stage names the file, says to re-render with `/hm:make`, and
  runs with no banner and no picker. An auto-armed session (`autopilot_persistent`) stays armed.
  The output language still holds, because CLAUDE.md carries the same directive.
- The Codex stage skills, CLAUDE.md and AGENTS.md keep their inline text. Codex has no
  reference-file precedent (s2b, s3a). Cursor reads the Claude render, so it gets the pointer.

### B — A quiet check

- **What the bench shows** (26 hm runs, 77 `check` calls):
  - A clean `check` already prints one line of about 160 chars.
  - Of the ~9.9k chars `check` prints per run, 92% are failure payloads: 28 calls averaging
    8.1k chars.
  - In those payloads each pydantic error appears three times (`validate.errors`,
    `cross_validate.errors`, `by_rule.unattributed`), each copy with its help URL and input echo.
- **No gate failed** (`ok: true`): one line, `{"ok": true, "overall": N, "strictness": S}`, and
  exit 0.
  - When the score is weak (any dimension < 40) or low (`overall` < 60), the line also carries
    `"weak_dimensions": [...]` (dimensions < 40, the list Step 4.5's warn row reads) and
    `"low_dimensions": {dim: score}` (every dimension < 60, with its score).
  - `low_dimensions` is never empty when `overall` < 60, because the integer mean of scores that
    are all ≥ 60 is ≥ 60.
- **A gate failed:**
  `{"ok": false, "strictness": S, "validate": {"ok", "errors"}, "cross_validate": {"ok",
  "errors", "by_rule"}, "quality": {"overall", "weak_dimensions", "low_dimensions", "blocked",
  "strictness"}}`. The top-level `strictness` stays.
  - Each distinct error appears once.
  - A pydantic load error is one line per location (`<loc>: <msg>`), with no help URL and no
    `input_value` echo.
  - A non-pydantic load error is one line, `yaml load failed: <Type>: <message>`:
    - a yaml syntax error: `yaml load failed: YAMLError: <problem> (line L, column C)`, the
      problem being the parser's first line;
    - a missing or unreadable file: `yaml load failed: FileNotFoundError: <path>` (or
      `OSError`);
    - a missing `.md`: cross-validate's existing message, once.
  - When the yaml failed to load, `cross_validate.errors` holds
    `yaml load failed (see validate.errors)` instead of a second copy.
  - `by_rule` maps each non-empty bucket to its count.
  - `scores`, `yaml_path` and `md_path` are gone; `low_dimensions` carries the scores that
    matter. The exit code is unchanged.
- **Scoring exception.** When `evaluate_spec` raises, `check` prints the failure-shaped payload
  with the top-level `strictness` and `quality: {"error": "<Type>: <msg>", "strictness": S}`,
  and exits as today: 1 when validate or cross-validate also failed (`ok: false`), else 0
  (`ok: true`).
- **Saving.** Estimated on the same 26 runs with a text-level replay: ~9.9k → ~2.9k chars per
  run.
- **Other light-path CLIs, unchanged.** These already print one JSON line on success: `autopilot
  status` (~200 chars), `autopilot_caps boundary` (~410 average), `spec_machine approval-status`
  (~140), `spec_need record` / `frontmatter-upsert` / `op-check` / `waiver-check`, and
  `observability.verification_cache run`. A test pins them as one line, byte-equal to
  `a7403f2f`.
- **Not changed, by design:**
  - `memory_retrieve`: its success output is the retrieved data, and its empty-result fence is
    pinned by three test files.
  - The boundary's `judgment_directive`: it is an instruction the stage must act on.

### C — Less paperwork on light

**Execute Step 0, in order** (Claude command; the Codex skill has the same order with its full
text inline):

1. **Step 0's `a7403f2f` head, inline, above the lane split**, so both arms get it: the two intro
   paragraphs and then the two shared rules (`execute.md.j2:126-132`), unchanged, ending at the
   do-not-rewrite paragraph. The head is a pure prefix of the `a7403f2f` body, so S13 rebuilds
   that body by concatenation (980 chars on the default render). The shared rules are:
   - the rooted write path: `` Write to `<WT>/work-docs/PLAN-{slug}.md` ``, or
     `` `./work-docs/PLAN-{slug}.md` `` with worktree off;
   - "**If that file already exists, do not rewrite it** — skip to the SPEC-need write below".
2. **The `approval-status` call**, then the routing sentence, exactly:
   `` If that prints `"trusted_lane": "light"` and loop mode is not active for this session, write the light PLAN from the light block below. Otherwise (full lane, untrusted light, or loop mode) follow the full PLAN text instead. ``
3. **The full-lane pointer** (`ref_pointer` partial, STOP on a missing file):
   `.claude/hm/execute-plan.md`, its Step 0 part now and its Step 0.3 part at the Step 0.3
   heading.
4. **The light block.** One span per file, between `<!-- @hm:light-plan -->` and
   `<!-- @hm:/light-plan -->`, anchored right after the full-lane pointer, at most 2,400 chars.
   It holds:
   - **The fenced one-screen template.** Its placeholders are `{slug}`, `{YYYY-MM-DD}`,
     `{summary}`, `{M}`, `<id>`, and per row `{name}`, `{files}`, `{command}`, `{risk}`,
     `{rollback}`, `{path}`, `{why}`, `{NNN}`, `{decision}`, `{provenance}`. Its content:
     - frontmatter: `type: plan`, `task_slug`, `status: planning`, `created`, `spec`, `intent`
       when the SPEC names one (`research_doc` only when RESEARCH ran), `adrs`, `summary`;
     - `## 📝 Implementation Plan`: one line per phase, with the fixed literal
       `` - [ ] {N}. **Phase {N} — {name}** — scope: {files} · exit: `{command}` · risk: {risk} · rollback: {rollback} ``.
       Wrapup Step 4 and the Quality Bar match `- [ ]`; the `verify-before-completion` skill's
       1b matches the numbered item;
     - `## 🚧 Contract Boundaries` / `### Do not change`, in the three admitted forms;
     - `## 📐 Architecture Decision Records`: one bullet per decision, `- ADR-{NNN}: {decision}.
       **Decided by:** {provenance}`, where provenance is `user (source: …)` or `agent`.
   - **The light read-back**, run at the Step 0.3 heading after Step 0.1. It asserts:
     - (a) the frontmatter carries every key of the template;
     - (b) every phase line carries `scope:`, `exit:`, `risk:` and `rollback:`;
     - (c) `### Do not change` is present and non-empty, every bullet is one of the three
       admitted forms, and a `none` bullet appears only as the sole bullet;
     - (d) the frontmatter carries `spec_need_verdict` after Step 0.1.

     A failure is self-repaired inline, as in Step 0.3.
   - **The Step 1.5 note:** Step 1.5 (parallel split) does not apply to a light PLAN, because
     its phases run in order.
   - **The oversize rule:** if the light phases touch well over five files, the task is not
     light. Follow the full PLAN text instead and log that it reads as `full`, so Step 2's rule
     and the 3a light check's five-file skip agree.
5. **Step 0.1** (the spec_need upsert) and **Step 0.2** (loop mode only) stay as they are.
   **Step 0.3**'s heading carries, exactly:
   `` Light PLAN: run the light read-back from Step 0's light block. Any other PLAN: apply the Step 0.3 part of `.claude/hm/execute-plan.md`. ``

**Size.** A light PLAN filled from the template for the bench t1 task (the value table under S9)
is ≤ 1,200 chars after Step 0.1. A draft of the template filled from that table measures 925
chars, and the draft light block 1,417 chars. The light PLANs the bench wrote
from the full template were 1.5–2.9k chars.

**`execute-plan.md`** holds two ref slices, compared separately:
- **Part 1:** the rest of Step 0's `a7403f2f` body after the inline head, from
  `**Required frontmatter**` to the end.
- **The separator**, one fixed line:
  `<!-- @hm:ref:step-0.3 --> Apply the rest of this file at the command's Step 0.3 heading, after Step 0.1 has run.`
- **Part 2:** Step 0.3's `a7403f2f` body.

The headings stay in the command. The Codex skill inlines both parts at their `a7403f2f`
positions through the same partials.

**No reader changes.** Every light task still has a PLAN, so no stage gets a no-PLAN branch.
The light PLAN carries every key and section a gate reads:

| Reader | Reads |
|---|---|
| wrapup Step 1.3 | the PLAN exists |
| wrapup Step 3.2, verify Check 1, the drift verdict, Check 6's foreign-slug test | `task_slug` |
| wrapup Step 4 and the Quality Bar | `status`, `- [ ]` |
| wrapup Step 5.7, review Step 3.3, the boundary's objective gate (`_plan_link`) | `intent:` |
| wrapup's `agent-decided:` bullet | ADR ids with `**Decided by:**` |
| verify Check 6, both arms | `spec_need_verdict` / `spec_need_target` |
| the `verify-before-completion` skill, Check 1 / 1b | the PLAN glob, numbered items |
| review Step 2 and the light check's drift | phase `scope` |
| execute Steps 1, 2 and 4 | `spec:`, phases, the Do-not-change list |
| Maker's decision capture | the PLAN, else the SPEC, else the RESEARCH |
| `wrapup_land --required` | the PLAN path |

Wrapup creates the `## Feedback` table when it is absent, as it does today.

**Minimal machine.yaml.** On `lane: light`, Step 3.5 **authors** only:
- top level: `schema_version: 3`, `spec_slug`, `verification_tier`, `irreversible_decisions`
  (`[]` allowed) and the ACs;
- per AC: `id`, `title`, `type`, its type's slot, `test_ids` or `pending_test`, `oracle_source`
  and `oracle_evidence`. The type's slot is the predicate; golden rows `{input: {…}, expected: …}`;
  the rubric and subject paths; or the four property fields;
- at `verification_tier: 1`, also `mutation_threshold` and `paths_to_mutate`. The T1 mutation
  gate passes silently when `paths_to_mutate` is empty, and a quality floor may not be traded
  for size (intent.yaml rules).

Today's validator, scorer and `approve` already accept this file. The mutation dimension is
omitted, not zeroed. No light schema is added, which is the simpler of the two options. Tooling
may later materialise defaults in the file (e.g. `test_ids`, `pending_test`). Step 3.5 shows this
minimal schema inline. On the full lane it Reads the remaining fields and notes from a new
reference file `.claude/hm/spec-machine-full.md`, byte-identical to the moved `a7403f2f` text.

**Loop mode** (`/hm:loop`) is excluded, as the 3a light check is.

### What changes on the full lane, exactly

- **(A)** Each stage command carries the pointer. The first `/hm:` stage of a session makes one
  Read of `stage-preamble.md`. `/hm:health` also checks that file. The banner, picker and
  language text are unchanged.
- **(B)** The `check` output shape.
- **(C)** Execute Step 0 starts with one `approval-status` call on every lane. On the full lane,
  execute makes one Read of `execute-plan.md` and spec makes one Read of
  `spec-machine-full.md`. Both files hold unchanged text, and the command also carries the light
  branch's text.
- **Nothing else.** review, verify, wrapup, the loop, their reference files, the
  `verify-before-completion` skill, `light_lane.py`, `autopilot_caps.py`, the boundary JSON and
  the light-check record are byte-identical to `a7403f2f`, except A's pointer swap in the stage
  commands.

### Surface (chars, Claude render)

Before is `a7403f2f`; the last column is the bound after all three cuts. The per-cut bounds hold
at each phase commit.

| Stage | `a7403f2f` | A | B | C | Bound after |
|---|---|---|---|---|---|
| research | 20,461 | ≤ −3,712 | 0 | 0 | ≤ 16,749 |
| spec | 43,234 | ≤ −3,712 | ≤ +300 | ≤ −1,000 | ≤ 38,822 |
| execute | 45,572 | ≤ −3,712 | 0 | ≤ −2,500 | ≤ 39,360 |
| review | 60,617 | ≤ −3,712 | 0 | 0 | ≤ 56,905 |
| verify | 16,435 | ≤ −3,712 | 0 | 0 | ≤ 12,723 |
| wrapup | 33,099 | ≤ −3,712 | 0 | 0 | ≤ 29,387 |

- New reference files: `stage-preamble.md` ≤ 4,900, `execute-plan.md` ≤ 6,300,
  `spec-machine-full.md` ≤ 3,500 chars. The existing reference files do not change.
- Codex skills: the preamble span is unchanged. C grows `hm-execute` by at most 2,500 and
  `hm-spec` by at most 800. The other Codex skills do not change.

### Carried per run (estimates; the stage 4 bench measures them)

| Cut | Light run (spec → execute → wrapup) | Full run (5 stage turns) |
|---|---|---|
| A | ≈ −6.3k: 2 × 4,362 saved, minus 3 pointers, minus one Read's overhead | ≈ −13.9k |
| B | ≈ −7.0k | ≈ −7.0k |
| C | ≈ −7.4k (breakdown below) | ≈ +4.6k (breakdown below) |
| **Total** | **≈ −20.7k** | **≈ −16.3k** |

- **C on a light run:** execute instructions −2.3k (the Step 0 and 0.3 bodies, 5,526 chars,
  minus the 980-char inline head, the routing, pointer and Step 0.3 sentences, and the ~1.4k
  light block), spec instructions −1.5k, the PLAN written −0.9k (≈ 2.0k → ≤ 1.2k) and read back twice (Step 0.3 and Step 1) −1.8k, yaml −0.9k
  (19 light SPECs: 3,530 → 2,591 average).
- **C on a full run:** the two Reads with line-number overhead, and the light-branch text every
  lane carries.

## 📋 In-Scope Scenarios

### S1: The preamble is read once and applied every stage
**Given** a rendered Claude stage command for each of the six stages, on every config arm (autonomy gated, auto_safe, auto_full and ask; worktree on and off; locales en and ko)
**When** its text before `# Stage:` is read
**Then** it is the pointer, at most 650 chars, naming `.claude/hm/stage-preamble.md`, the project root, the read-unless-in-context condition, "either way" applying it to this stage (loop check, banner, picker only if not yet answered), and the missing-file rule
**And** none of the preamble's sentences appears in the command
**And** (runtime, bench-measured; the render test pins only the wording) a later stage whose context already holds the file prints its own banner without reading the file again

### S2: The moved preamble is byte-identical, and health checks it
**Given** the same config arms
**When** `.claude/hm/stage-preamble.md` is rendered and `/hm:health`'s workflow-clarity dimension scores the render, then scores it again with the file deleted, again with a marker removed from it, and once on the `a7403f2f` render (inline preamble, no file)
**Then** the text between its `@hm:ref:start` / `@hm:ref:end` markers equals each command's `a7403f2f` preamble span
**And** both signals pass on the full render and on the `a7403f2f` render, and fail, naming the file, when the file is deleted or a marker is removed

### S3: Codex, CLAUDE.md and AGENTS.md keep their inline preamble
**Given** a render with the `codex` target
**When** the Codex stage skills, CLAUDE.md and AGENTS.md are read
**Then** each Codex skill's text before `# Stage:` and the output-language sections equal their `a7403f2f` render

### S4: A check with no failed gate prints one line
**Given** a SPEC pair that passes validate and cross-validate, with quality clean, weak (a dimension < 40), low (overall < 60) under `warn`, or `evaluate_spec` raising
**When** `hm spec_machine check --all` runs
**Then** the first three print one JSON line, carrying `weak_dimensions` and `low_dimensions` exactly when the score is weak or low, and exit 0
**And** the raising case prints the failure-shaped payload with the top-level `strictness` and `quality: {error, strictness}`, `ok: true`, and exits 0

### S5: A failing check prints each error once and names the low dimensions
**Given** the failure fixtures: string golden-row input, a golden row without `expected`, a missing AC heading, a title mismatch, a v2 AC without `oracle_evidence`, an unparseable yaml, a missing yaml file, `block` strictness with overall 55 and no dimension < 40, and `evaluate_spec` raising while validate fails
**When** `check --all` runs on `a7403f2f` and after the change
**Then** `ok`, the exit code, `validate.ok`, `cross_validate.ok`, `quality.blocked` and the set of error locations are equal
**And** no error string appears twice, no help URL or `input_value` appears, the overall-55 payload names at least one dimension with its score in `low_dimensions`, and the total output is at most half of `a7403f2f`'s

### S6: The other light-path CLIs keep their one success line
**Given** fixtures where each CLI succeeds
**When** `autopilot status`, `autopilot_caps boundary` (proceed and merge-gate paths), `spec_machine approval-status`, `spec_need record` / `frontmatter-upsert` / `op-check` / `waiver-check` and `observability.verification_cache run` run
**Then** each prints one line, byte-equal to its `a7403f2f` output

### S7: A trusted light execute writes the short light PLAN
**Given** a rendered execute command (Claude) and execute skill (Codex)
**When** Step 0 and the Step 0.3 heading are read, with worktree on and off
**Then** Step 0 opens with its `a7403f2f` head, the intro and then the two shared rules (the rooted write path, `<WT>/` or `./`, and "if that file already exists, do not rewrite it"), then the `approval-status` call and the exact routing sentence, then the full-lane pointer, then exactly one light block between the `@hm:light-plan` markers
**And** the light block holds the template with the phase-line literal, the four read-back assertions (a)–(d), the Step 1.5 note and the oversize rule, and the Step 0.3 heading carries its exact sentence
**And** the two shared rules sit above the lane split, so they apply to the light arm and the full arm alike

### S8: Every other execute writes the full PLAN from the reference file
**Given** a full lane, an untrusted light lane, loop mode, or an oversize light block
**When** execute Step 0 runs
**Then** the Claude command Reads `.claude/hm/execute-plan.md`; its part 1 equals the `a7403f2f` Step 0 body after the inline head, then the fixed separator line, then part 2 equals the `a7403f2f` Step 0.3 body
**And** the Codex skill inlines both parts at their `a7403f2f` positions

### S9: The light PLAN feeds every gate that reads a PLAN
**Given** the fenced light template extracted from `render(cfg)['execute']`, filled mechanically from this value table (bench t1, plus a fixture intent), then given Step 0.1's real `spec_need frontmatter-upsert`:

| Placeholder | Value |
|---|---|
| `{slug}` | `format-max-units` |
| `{YYYY-MM-DD}` | `2026-10-14` |
| `<id>` (intent) | `TIMEPARSE-UNITS` |
| `{M}` | `2` |
| `{summary}` | `format_duration gains max_units to cap the number of emitted units` |
| phase 1 | `max_units parameter`; `` `timeparse/format.py`, `tests/test_format.py` ``; `pytest tests/test_format.py -q`; `low`; `revert` |
| phase 2 | `CLI flag`; `` `timeparse/cli.py`, `tests/test_cli.py` ``; `pytest tests/test_cli.py -q`; `low`; `revert` |
| boundary | `timeparse/parse.py`; `parsing grammar is out of scope` |
| ADR-001 | `truncate, never round, the dropped units`; `user (source: SPEC S2)` |
| ADR-002 | `max_units=None keeps today's output`; `agent` |
| spec_need | `--verdict add --target SPEC-format-max-units` |

The phase, boundary and ADR lines repeat once per row; `research_doc` is dropped (no RESEARCH).
**When** each reader in the Outcomes table reads it, and `autopilot_caps._plan_link` and `wrapup_land` (PLAN `--required`) run on it
**Then** every key and section that reader needs is present and parseable: `_plan_link` returns the intent link, `wrapup_land` stages the PLAN, the Do-not-change list parses in an admitted form, the phase lines match `- [ ]` and the numbered-item form, and the ADR ids carry `**Decided by:**`

### S10: The light PLAN is short
**Given** the template-derived fixture of S9, after the upsert
**When** its size is measured
**Then** it is at most 1,200 chars

### S11: A minimal light machine.yaml validates, approves and survives write-back
**Given** minimal light machine.yamls at tiers 1, 2 and 3 with mechanical, parametric, judgment and property ACs and `irreversible_decisions: []`
**When** `check --all --strictness block`, `approve --exempt` and `approval-status` run, then `spec_machine mark-tested` writes test ids back, then `approval-status` runs again
**Then** check is `ok` and not blocked, the stamp is written, and both `approval-status` calls print state `exempt` and `trusted_lane: light`
**And** a human-approved copy reads `approved` and `trusted_lane: light` after the same write-back

### S12: Spec Step 3.5 shows the minimal schema and reads the rest on full
**Given** a rendered spec command (Claude) and spec skill (Codex)
**When** Step 3.5 is read
**Then** it shows the minimal schema with the golden-row shape and the T1 mutation keys inline, and on `lane: full` the Claude command Reads `.claude/hm/spec-machine-full.md`, whose ref slice equals the moved `a7403f2f` text

### S13: The full lane and the typed stages change only by the named deltas
**Given** full-lane configs (Side and Production, worktree on and off, warn and block, loop on and off)
**When** each `a7403f2f` stage command, reference file, Codex skill and the `verify-before-completion` skill is compared to the new render after a fixed normalisation:
- the A pointer is restored to the preamble;
- in execute, exactly one `@hm:light-plan` span (≤ 2,400 chars, right after the full-lane pointer) is deleted;
- the exact routing sentence, the `approval-status` call and the exact Step 0.3 heading sentence are deleted;
- the full-lane pointer and the separator are replaced by `execute-plan.md`'s two parts;
- in spec, the Step 3.5 and Step 4 + 4.5 sections are left out (AC-015 and AC-009 compare them)

**Then** they are equal, and the boundary JSON for the same inputs equals `a7403f2f`

### S14: The surface shrinks by the measured bounds
**Given** `_surface_baseline.measure_surface()` and the `a7403f2f` numbers captured before the edit
**When** the Claude commands, reference files and Codex skills are measured
**Then** each meets its bound in the Outcomes table

## 🚫 Non-Goals

- Moving the Codex preamble out of the stage skills (no Codex reference-file mechanism yet).
- Changing any CLI output other than `spec_machine check --all`. `memory_retrieve`, the boundary's
  `judgment_directive` and `verification_cache`'s stderr line are examined and left alone.
- Changing `spec_machine validate`, `cross-validate`, `approve` or the content hash. A declared
  light machine schema is not added.
- Removing the PLAN on light, or adding a no-PLAN branch to any reader.
- Changing review, verify, wrapup, the loop, the light-check record or the boundary skip.
- Fixing the `verify-before-completion` skill's `ls PLAN-*.md | head -1` glob, which can pick
  another task's PLAN on every lane. This is pre-existing and listed as a follow-up.
- Re-running the bench (stage 4).

## ⚠️ Constraints

| Constraint | Value | Rationale |
|---|---|---|
| Test framework | `pytest` | Project standard (CLAUDE.md) |
| Oracle source | `a7403f2f` renders, CLI outputs and surface numbers captured in a detached worktree before any edit, under `tests/fixtures/light_lane_s3c/` | Byte-identical moves and "unchanged" claims need an independent reference |
| One pointer form | A and C use `stages/_partials/ref_pointer.md.j2`; moved text sits between `@hm:ref:start` / `@hm:ref:end` | Same rule as s2b and s3a; a test slices the markers |
| One source per moved text | The Claude reference file and the Codex inline arm include the same partial | Two copies would drift |
| Fail direction | A missing `stage-preamble.md` means no banner and no picker, and an auto-armed session stays armed; `/hm:health` flags it. A missing `execute-plan.md` or `spec-machine-full.md` is a STOP | Losing the picker only removes the offer; losing PLAN text would break later stages |
| Quality floor | The light PLAN keeps every key and section a gate reads; the minimal yaml keeps every key a gate reads (T1 mutation keys, `irreversible_decisions`) | intent.yaml rule: no quality floor traded for size |
| Generated-file frontmatter | The three new files carry `generated_by`, `content_hash`, `source_template`, `harness_maker_version` | CLAUDE.md security rule |
| Registry | No new `Step` / `Phase` / `Check` heading; moved bodies leave their headings in the command; the light template's headings sit inside a fenced block | `test_step_sensitivity_registry.py` |
| Supersedes | s3a AC-011 (typed review/verify/wrapup/loop byte-identical to `e7dd6648`) holds up to A's pointer swap (S13) | User decisions 2026-10-15 |
| Goldens | Re-captured with a dated note: `test_autopilot_gate_render` golden, `tests/fixtures/strictness_reference/`, s3a render SHAs, `surface_baseline.json` + `work-docs/BASELINE-DELTA-hm-light-lane-s3c.md` | Their own docstrings require the dated note |
| Compatibility | Python 3.12; re-render through `/hm:make`; an old render keeps the inline preamble and writes the full PLAN | Mixed versions fail toward today's behavior |

## 🔒 Irreversible Decisions

| Id | Decision | Category | Rationale |
|---|---|---|---|
| IRR-001 | `hm spec_machine check --all` prints one line whenever no gate failed (with `weak_dimensions` and `low_dimensions` on a weak or low score); its failure payload drops `scores`, `yaml_path` and `md_path`, adds `low_dimensions`, prints each error once (pydantic as `<loc>: <msg>`) and turns `by_rule` into counts | public API/CLI contract | Rendered spec text and any script parsing the payload read these keys; restoring them later breaks readers written against the quiet form |
| IRR-002 | A trusted light task outside loop mode carries the short light PLAN (the inline template's frontmatter keys and three sections) instead of the full nine-section template | schema/file format/storage layout | Light PLANs land in history; no reader may later require a full-template section or a phase field the light template omits (Executive Summary, Prior Work, Technical Design, Testing Strategy, Risks, Success Criteria, `depends_on` / `parallel_group` / `merge_hazards`) |
| IRR-003 | A light machine.yaml is authored minimal (the Step 3.5 key set); tooling may materialise defaults; no validator may require an optional key | schema/file format/storage layout | Committed light SPECs lack the optional keys; requiring one later invalidates them |
| IRR-004 | Add the generated files `.claude/hm/stage-preamble.md`, `.claude/hm/execute-plan.md` and `.claude/hm/spec-machine-full.md`, the names the commands and `/hm:health` read | schema/file format/storage layout | Renaming needs a retire step for copies on disk (s2b IRR-001, s3a IRR-003) |

## ✅ Verification Criteria

| Scenario | Verification mode | Test name / manual step |
|---|---|---|
| S1 | unit (render) | `tests/render/test_render_light_lane_s3c.py::test_stage_commands_point_at_the_preamble` |
| S2 | unit (render, differential) | `tests/render/test_render_light_lane_s3c.py::test_preamble_moved_byte_for_byte`, `tests/unit/test_readiness_stage_preamble.py::test_health_checks_the_preamble_file`, `tests/unit/test_readiness_stage_preamble.py::test_health_scores_an_old_render_as_today` |
| S3 | unit (render, differential) | `tests/render/test_render_light_lane_s3c.py::test_codex_and_claude_md_keep_the_preamble` |
| S4 | unit (CLI) | `tests/unit/test_spec_machine_check_quiet.py::test_no_failed_gate_prints_one_line` |
| S5 | unit (CLI, differential) | `tests/unit/test_spec_machine_check_quiet.py::test_failure_prints_each_error_once`, `tests/unit/test_spec_machine_check_quiet.py::test_failure_output_is_at_most_half` |
| S6 | unit (CLI, differential) | `tests/unit/test_cli_output_one_line.py::test_light_path_clis_unchanged` |
| S7 | unit (render) | `tests/render/test_render_light_lane_s3c.py::test_light_execute_writes_the_short_plan` |
| S8 | unit (render, differential) | `tests/render/test_render_light_lane_s3c.py::test_full_execute_reads_the_moved_plan_text` |
| S9 | unit | `tests/unit/test_light_plan.py::test_light_plan_feeds_every_reader` |
| S10 | unit | `tests/unit/test_light_plan.py::test_light_plan_is_short` |
| S11 | unit (CLI) | `tests/unit/test_light_plan.py::test_minimal_machine_yaml_validates_and_approves`, `tests/unit/test_light_plan.py::test_mark_tested_write_back_keeps_the_stamp` |
| S12 | unit (render, differential) | `tests/render/test_render_light_lane_s3c.py::test_spec_step_3_5_minimal_inline` |
| S13 | unit (render, differential) | `tests/render/test_render_light_lane_s3c.py::test_full_lane_changes_only_by_named_deltas` |
| S14 | unit (structural) | `tests/render/test_render_light_lane_s3c.py::test_surface_meets_bounds` |
| Outcome (spec text) | unit (render) | `tests/render/test_render_light_lane_s3c.py::test_spec_describes_quiet_check` |

### AC-001: Every Claude stage command carries the read-once, apply-every-stage preamble pointer
### AC-002: stage-preamble.md holds the a7403f2f preamble byte-for-byte in every config arm
### AC-003: Codex stage skills, CLAUDE.md and AGENTS.md keep the inline preamble
### AC-004: The health audit requires the preamble file and its markers when a stage command names it
### AC-005: A check run with no failed gate prints one line, and a scoring exception keeps the verdict
### AC-006: A failing check prints each error once and names its low dimensions with scores
### AC-007: Check output on the failure fixtures is at most half of a7403f2f's
### AC-008: The other light-path CLIs print the same single success line as a7403f2f
### AC-009: The spec stage describes the quiet check output
### AC-010: A trusted light execute outside loop mode writes the short light PLAN
### AC-011: Every other execute writes the full PLAN from execute-plan.md, whose text is a7403f2f's
### AC-012: The light PLAN carries every key and section a gate reads
### AC-013: The template-derived light PLAN fixture is at most 1,200 chars
### AC-014: A minimal light machine.yaml passes check, approve and approval-status, and survives write-back
### AC-015: Spec Step 3.5 shows the minimal schema inline and the full-lane fields on demand
### AC-016: The full lane and the typed stages differ from a7403f2f only by the named deltas
### AC-017: The rendered surface meets the per-stage bounds

## ❓ Open Questions

- **C's split costs the full lane about +4.6k carried chars and two Reads per run.** Execute's
  full PLAN text and spec's full-lane yaml fields move to reference files, so the light lane stops
  carrying them. Keeping them inline would cut the light lane's C saving from ≈ −7.4k to
  ≈ −3.6k (only the shorter PLAN and yaml) and cost the full lane nothing. Agent default: split
  (PLAN ADR-005).
- **Most bench `check` failures are golden-row shape errors** (`input` not a mapping, `expected`
  missing). The minimal inline schema shows the row shape, so both lanes see it. Whether that
  lowers the retry count is unmeasured until the stage 4 bench.
- The carried-chars figures are estimates from 26 bench runs. `hm_cost_ratio_small` is unmeasured
  until the stage 4 bench is re-run on this change.

## 🔍 Refinement Decisions

- Interview not run: the three cuts are the DRI's 2026-10-15 decisions. The defaults below are
  agent decisions recorded as PLAN ADRs with their owner.
- Lane `full`: about 20 files and four irreversible decisions.
- **spec-validator pass 1: MAJOR_REVISION.** Most critical and warning findings came from
  "no PLAN on light" touching more than 10 PLAN readers, several of which failed open:
  - untrusted-light and loop tasks with a missing PLAN;
  - the Feedback-table write creating a stub PLAN;
  - the agent-decided accounting;
  - the contract do-not-change list;
  - the verify skill's PLAN glob;
  - the oversize downgrade after Step 0;
  - the drift scope.

  On the coordinator's recommendation, which the DRI later confirmed, C became a short light PLAN that
  carries every key and section a gate reads. Every no-PLAN branch, the `_plan_link` SPEC
  fallback and the SPEC-frontmatter spec_need fields were removed.
- Pass 1 also changed B and A:
  - B keeps per-dimension scores: `low_dimensions` maps dims < 60 to their score. It was chosen
    over the full 8-int map because it names exactly what pulls the score down, and it is never
    empty when `overall` < 60. B also defines the scoring-exception path.
  - A separates "read once" from "apply every stage". `/hm:health` also checks the file, and the
    config arms gain worktree on/off and `auto_full`.
- B was narrowed to `check` after measuring. "One line on success" already held for every
  light-path CLI, including `check` on a clean pass; the cost is in failure payloads.
- C keeps the validator unchanged: the minimal file already validates (the simpler option the DRI
  asked for).
- C excludes loop mode, as the 3a light check does.
- Confirmed unchanged: Maker's decision-capture rule ("write it into that task's most downstream
  artifact (PLAN, else SPEC, else RESEARCH)") and AGENTS.md (`$hm-execute` "Writes the PLAN
  (phases, ADRs)") stay true with a light PLAN.
- **DRI decision 2026-10-15, "Short PLAN" on the card.** spec-validator pass 2 found no missing
  IRR and confirmed that every key a reader parses is in the light template. Its findings were
  folded in:
  - Step 0's two shared rules (the rooted write path; do not rewrite an existing PLAN) stay
    inline above the lane split. The two intro paragraphs before them stay too, so the inline
    head is a pure prefix of the `a7403f2f` body and S13 compares by concatenation. That costs
    the light lane ~0.56k; the alternative, a reorder rule in the normalisation, is the kind of
    hand-written whitelist entry AC-016 exists to avoid;
  - the light read-back's four assertions are listed;
  - `execute-plan.md` is two ref slices with a fixed separator, and the Step 0.3 heading
    sentence is exact;
  - the AC-012 fixture is derived from the rendered template and the S9 value table, and
    `next_stage` was dropped from S9 (the digest reads only a PLAN's existence);
  - the light span has fixed markers and a size bound, and the routing sentence is exact;
  - `/hm:health` checks the file only when a command names it;
  - the phase-line literal is pinned;
  - B keeps the top-level `strictness`, states the non-pydantic load-error format, and adds the
    raise-plus-failed-gate row;
  - AC-014 adds the `mark-tested` round-trip;
  - S1's runtime clause is labelled bench-measured.
- Evaluated, not irreversible: execute Step 0's `approval-status` call, and Step 1.5 not applying
  to a light PLAN.
- Work stays on the session's designated branch, as in stages 1–3a.
