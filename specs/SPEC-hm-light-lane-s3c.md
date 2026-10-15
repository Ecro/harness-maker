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
summary: "Stage 3c of HM-LIGHT-LANE: one stage preamble per session, a quiet spec_machine check, and no PLAN or full machine.yaml on light"
---

# SPEC — hm-light-lane-s3c (stage 3c, three token cuts)

## 🎯 Intent

After stage 3a, a small /hm: task still carries text it does not use. The 2026-10-15 breakdown of
17 completed bench runs (`token-breakdown-2026-10-15.md`) names three sources. The same stage
preamble is loaded once per stage. `hm spec_machine check` prints about 10k chars per run. The
light lane still writes a PLAN and a full machine.yaml. The DRI decided all three ("Cut") on the
2026-10-15 decision cards: **A** load the preamble once, **B** make the hm CLIs quiet on success,
**C** write no PLAN and only a minimal machine.yaml on `lane: light`.

## 🌅 Outcomes

Measured on this repo's committed `.claude/harness.yaml` with
`tests/structural/_surface_baseline.render_surface()` at `a7403f2f` unless a line says otherwise.

- **A — one preamble.** The preamble (start banner, autopilot picker, output-language block) is
  4,362 chars and is byte-identical in all six Claude stage commands (research, spec, execute,
  review, verify, wrapup). It moves, byte for byte, into a new reference file
  `.claude/hm/stage-preamble.md`. Each command keeps a one-line pointer of at most 600 chars in
  its place. The pointer says: unless this session's context already holds that file (read at an
  earlier `/hm:` stage), Read it from the project root, never from `<WT>`, and follow it. The
  pointer carries the `<!-- @hm:banner:start -->` and `<!-- @hm:output_language -->` markers, so
  `/hm:health` (`readiness._dim_workflow_clarity`) keeps passing without a code change. A missing
  file is not a STOP. The stage names the file, says to re-render with `/hm:make`, and runs
  without a banner and without the picker. Autopilot then stays gated. The output language still
  holds because CLAUDE.md carries the same directive. The Codex stage skills, CLAUDE.md and
  AGENTS.md keep their inline text, because Codex has no reference-file precedent (s2b, s3a).
  Cursor reads the Claude render, so it gets the pointer.
- **B — a quiet check.** The bench transcripts (26 hm runs, 77 `check` calls) show that a clean
  `check` already prints one line of about 160 chars. Of the ~9.9k chars `check` prints per run,
  92% are failure payloads: 28 calls averaging 8.1k. In those payloads each pydantic error appears
  three times (`validate.errors`, `cross_validate.errors`, `by_rule.unattributed`), each copy with
  its help URL and input echo, plus a `scores` block. The new contract:
  - **No gate failed** (`ok: true`, a weak score included): one line,
    `{"ok": true, "overall": N, "strictness": S}`. `"weak_dimensions": [...]` is appended only
    when the list is non-empty or `overall < 60`. Exit 0.
  - **A gate failed:** `{"ok": false, "validate": {"ok", "errors"}, "cross_validate": {"ok",
    "errors", "by_rule"}, "quality": {"overall", "weak_dimensions", "blocked", "strictness"}}`.
    Each distinct error appears once. A pydantic load error is one line per location
    (`<loc>: <msg>`), with no help URL and no `input_value` echo. When the yaml failed to load,
    `cross_validate.errors` holds `yaml load failed (see validate.errors)` in place of its copy.
    `by_rule` maps each non-empty bucket to its count. `scores`, `yaml_path` and `md_path` are
    gone. The exit code is unchanged.
  - Estimated on the same 26 runs with a text-level replay: ~9.9k → ~2.8k chars per run.
  - The other hm CLIs the light path calls already print one JSON line on success: `autopilot
    status` (~200 chars), `autopilot_caps boundary` (~410 average), `spec_machine
    approval-status` (~140), `spec_need record` / `frontmatter-upsert` / `op-check` /
    `waiver-check`, and `observability.verification_cache run`. They are not changed. A test pins
    them as one line and byte-equal to `a7403f2f`.
  - `memory_retrieve` is not changed. Its success output is the retrieved data, and its
    empty-result fence is pinned by three test files.
  - The boundary's `judgment_directive` (~480 chars on auto-answered rows) is not changed,
    because it is an instruction the stage must act on.
- **C — the light document set.** On a **trusted light lane**, meaning `approval-status` prints
  `"trusted_lane": "light"`, and with loop mode off for the session:
  - **No PLAN.** Execute Step 0 first runs `hm spec_machine approval-status` (every lane) and
    branches. On the light branch it writes no `work-docs/PLAN-{slug}.md`. It states the phases in
    its reply, one block: per phase the name, the files it touches and its exit test (the SPEC
    scenario it proves). In the rest of execute, "the PLAN" means that block and its frontmatter
    fields come from the SPEC. Step 1's file check and Step 1.5 are skipped, and Step 4's
    phase-status update is the block itself. Step 0.1 upserts `spec_need_verdict` /
    `spec_need_target` into `specs/SPEC-{slug}.md`'s frontmatter
    (`spec_need frontmatter-upsert --plan specs/SPEC-{slug}.md`). If a phase blocks, execute
    writes the PLAN then, from `execute-plan.md`, and records the blocker there, as on the full
    lane.
  - **The full lane keeps its PLAN text.** On the full lane, Step 0's body (4.2k) and Step 0.3's
    body (1.3k) are Read from a new reference file `.claude/hm/execute-plan.md`, whose text equals
    the `a7403f2f` render. The headings stay in the command.
  - **Minimal machine.yaml.** On `lane: light`, Step 3.5 writes only `schema_version: 3`,
    `spec_slug`, `verification_tier`, `irreversible_decisions` (`[]` allowed) and the ACs. Each AC
    has `id`, `title`, `type`, its type's slot, `test_ids` or `pending_test`, `oracle_source` and
    `oracle_evidence`. The type's slot is the predicate, golden rows `{input: {…}, expected: …}`,
    the rubric and subject paths, or the four property fields. At `verification_tier: 1` it also
    writes `mutation_threshold` and `paths_to_mutate`, because the T1 mutation gate passes
    silently when `paths_to_mutate` is empty. Leaving them out would lower a quality floor
    (intent.yaml rules). Today's validator, scorer and `approve` already accept this file (the
    mutation dimension is omitted, not zeroed). No light schema is added, which is the simpler of
    the two options. Step 3.5 shows this minimal schema inline. On the full lane it Reads the
    remaining fields and notes from a new reference file `.claude/hm/spec-machine-full.md`, whose
    text equals the `a7403f2f` render.
  - **Every PLAN reader on the light path gets a defined no-PLAN branch.** The condition is no
    `PLAN-{slug}.md` and the SPEC frontmatter `lane: light`. On the text side:
    - wrapup Step 1.3 (PLAN existence), Step 3.2 (`task_slug` from the SPEC) and Step 4 (no
      PLAN status update);
    - the `wrapup_land` line, where PLAN moves from `--required` to `--optional`;
    - wrapup's Quality Bar and Step 5.7, intent state (`intent:` from the SPEC);
    - verify Check 1 (`task_slug` from the SPEC);
    - the shared Check 6 partial, both arms (spec_need fields from the SPEC frontmatter);
    - the shared drift scan and verdict partials, where scope is the SPEC's In-Scope Scenarios:
      a changed file no scenario needs is scope drift, a scenario with no change is an incomplete
      phase, and `task_slug` comes from the SPEC;
    - review Step 3.3 intent (`intent:` from the SPEC);
    - the `verify-before-completion` skill's Check 1.

    On the Python side, `autopilot_caps._plan_link` reads `intent:` (or legacy `objective:`) from
    the SPEC `.md` on the same condition, so the objective gate keeps firing. This is light-only.
    With no PLAN, a light SPEC's link can now halt at the spec boundary, earlier than at execute
    today. `world_model_digest`, `wrapup_brief`, `wrapup_land`, `drift_monitor` and
    `surface_allowance` already accept a missing PLAN. Tests pin them unchanged.
  - **The full lane fails as today.** Without `lane: light`, a missing PLAN fails exactly as on
    `a7403f2f`: wrapup errors, `wrapup_land` refuses the required path, and verify Check 1 and the
    skill block.
  - **Loop mode** (`/hm:loop`) is excluded, as the 3a light check is: an iteration's context does
    not survive, so its PLAN does.
- **What changes on the full lane, exactly.**
  - (A) Each stage command carries the pointer, and the first `/hm:` stage of a session makes one
    Read of `stage-preamble.md`. The banner, picker and language text are unchanged.
  - (B) The `check` output shape.
  - (C) Execute Step 0 starts with one `approval-status` call. Execute makes one Read of
    `execute-plan.md` and spec one Read of `spec-machine-full.md`; both hold unchanged text.
  - (C) The conditional no-PLAN sentences listed above. They are inert when a PLAN exists, which
    it always does on the full lane.
  - Nothing else: stages, gates, dispatches, the boundary JSON and the light-check record are
    unchanged.
- **Surface (chars, Claude render).** Before `a7403f2f` → bound after all three cuts. The per-cut
  bounds hold at each phase commit.

  | Stage | `a7403f2f` | A | B | C | Bound after |
  |---|---|---|---|---|---|
  | research | 20,461 | ≤ −3,762 | 0 | 0 | ≤ 16,699 |
  | spec | 43,234 | ≤ −3,762 | ≤ +200 | ≤ −1,000 | ≤ 38,672 |
  | execute | 45,572 | ≤ −3,762 | 0 | ≤ −3,000 | ≤ 38,810 |
  | review | 60,617 | ≤ −3,762 | 0 | ≤ +600 | ≤ 57,455 |
  | verify | 16,435 | ≤ −3,762 | 0 | ≤ +600 | ≤ 13,273 |
  | wrapup | 33,099 | ≤ −3,762 | 0 | ≤ +600 | ≤ 29,937 |

  - New reference files: `stage-preamble.md` ≤ 4,900, `execute-plan.md` ≤ 6,300,
    `spec-machine-full.md` ≤ 3,500 chars.
  - Existing reference files: `verify-checks.md` and `wrapup-steps.md` grow by at most 600 each,
    and `execute-light-check.md` by at most 400.
  - Codex skills: the preamble span is unchanged. C grows `hm-execute` by at most 1,500, and
    `hm-spec`, `hm-review`, `hm-verify` and `hm-wrapup` by at most 800 each.
- **Carried per run (estimates; the stage 4 bench measures them).**
  - **Light run (spec → execute → wrapup).**
    - A: ≈ −6.4k (2 × 4,362 saved, minus 3 pointers, minus one Read's overhead).
    - B: ≈ −7.1k.
    - C: ≈ −9k (execute −3.9k, spec −1.5k, PLAN written and read back ≈ −4k, yaml −0.9k, plus
      wrapup sentences +0.4k).
    - Total ≈ −22k.
  - **Full run (5 stage turns).**
    - A: ≈ −14k.
    - B: ≈ −7.1k.
    - C: ≈ +4.6k (two Reads with line-number overhead, the light-branch text carried by every
      lane, and the no-PLAN sentences).
    - Total ≈ −16k.

## 📋 In-Scope Scenarios

### S1: The preamble is loaded once per session
**Given** a rendered Claude stage command for each of the six stages, on gated, auto_safe and ask autonomy and on locales en and ko
**When** its text before `# Stage:` is read
**Then** it is the pointer, at most 600 chars, naming `.claude/hm/stage-preamble.md`, the project root, the read-once condition and the missing-file rule
**And** none of the preamble's sentences appears in the command

### S2: The moved preamble is byte-identical, and health still passes
**Given** the same config arms
**When** `.claude/hm/stage-preamble.md` is rendered and `/hm:health`'s workflow-clarity dimension scores the render
**Then** the text between its `@hm:ref:start` / `@hm:ref:end` markers equals each command's `a7403f2f` preamble span
**And** `output_language_present` and `start_end_summary_present` pass

### S3: Codex, CLAUDE.md and AGENTS.md keep their inline preamble
**Given** a render with the `codex` target
**When** the Codex stage skills, CLAUDE.md and AGENTS.md are read
**Then** each Codex skill's text before `# Stage:` and the output-language sections equal their `a7403f2f` render

### S4: A check with no failed gate prints one line
**Given** a SPEC pair that passes validate and cross-validate, at quality clean, weak (a dimension < 40) and low (overall < 60) under `warn`
**When** `hm spec_machine check --all` runs
**Then** stdout is one JSON line, `weak_dimensions` appears exactly when the score is weak or low, and the exit code is 0

### S5: A failing check prints each error once with the same verdict
**Given** the failure fixtures: string golden-row input, a golden row without `expected`, a missing AC heading, a title mismatch, a v2 AC without `oracle_evidence`, an unparseable yaml, and a `block`-strictness weak score
**When** `check --all` runs on `a7403f2f` and after the change
**Then** `ok`, the exit code, `validate.ok`, `cross_validate.ok`, `quality.blocked` and the set of error locations are equal
**And** no error string appears twice, no help URL or `input_value` appears, and the total output is at most half of `a7403f2f`'s

### S6: The other light-path CLIs keep their one success line
**Given** fixtures where each CLI succeeds
**When** `autopilot status`, `autopilot_caps boundary` (proceed and merge-gate paths), `spec_machine approval-status`, `spec_need record` / `frontmatter-upsert` / `op-check` / `waiver-check` and `observability.verification_cache run` run
**Then** each prints one line, byte-equal to its `a7403f2f` output

### S7: A trusted light execute outside loop mode writes no PLAN
**Given** a rendered execute command (Claude) and execute skill (Codex)
**When** Step 0 is read
**Then** its first action is `approval-status`; on `trusted_lane: light` with loop mode off it writes no PLAN file, states the phase block, defines "the PLAN" for the rest of execute, and upserts the spec_need fields into the SPEC
**And** a blocked phase writes the PLAN first

### S8: Every other execute writes the PLAN as today
**Given** a full lane, an untrusted light lane, or loop mode
**When** execute Step 0 runs
**Then** the Claude command Reads `.claude/hm/execute-plan.md`, whose text between its ref markers equals the `a7403f2f` Step 0 and Step 0.3 bodies, and the Codex skill inlines the same text

### S9: A minimal light machine.yaml validates and approves
**Given** minimal light machine.yamls at tiers 1, 2 and 3 with mechanical, parametric, judgment and property ACs and `irreversible_decisions: []`
**When** `check --all --strictness block`, `approve --exempt` and `approval-status` run
**Then** check is `ok` and not blocked, the stamp is written, and `approval-status` prints `trusted_lane: light`

### S10: Spec Step 3.5 shows the minimal schema and reads the rest on full
**Given** a rendered spec command (Claude) and spec skill (Codex)
**When** Step 3.5 is read
**Then** it shows the minimal schema with the golden-row shape and the T1 mutation keys inline, and on `lane: full` the Claude command Reads `.claude/hm/spec-machine-full.md`, whose ref slice equals the moved `a7403f2f` text

### S11: Every light-path reader accepts a light task without a PLAN
**Given** a light SPEC, a passing light-check record and no PLAN
**When** wrapup Steps 1, 3 and 4, the land line, verify Check 1, Check 6 (verify and light check), the drift partials, review Step 3.3 and the `verify-before-completion` skill are read, and `world_model_digest.next_stage`, `wrapup_brief` and `wrapup_land` run
**Then** each takes its no-PLAN branch: no error, `task_slug`/spec_need/intent from the SPEC, PLAN optional at land, scope from the SPEC's scenarios
**And** the digest routes to `wrapup`

### S12: The objective gate still fires without a PLAN on light
**Given** a light SPEC whose frontmatter links an intent that is missing, not active, or has an invalid approval, and no PLAN
**When** a stage's boundary runs where it would advance
**Then** it halts with the objective-gate message naming the SPEC link and writes the `gate_blocked` row, as with a PLAN link

### S13: Without lane light, a missing PLAN fails as today
**Given** a full or absent-lane SPEC and no PLAN
**When** wrapup, `wrapup_land`, verify Check 1, Check 6, the skill and the boundary read it
**Then** each behaves exactly as on `a7403f2f`

### S14: The full lane changes only by the named deltas
**Given** full-lane configs (Side and Production, worktree on and off, warn and block, loop on and off)
**When** each `a7403f2f` stage command, reference file and Codex skill is compared to the new render with the A pointer restored to the preamble, the C reference pointers restored to their text, and the listed no-PLAN sentences removed
**Then** they are equal, and the boundary JSON with a PLAN present equals `a7403f2f`

### S15: The surface shrinks by the measured bounds
**Given** `_surface_baseline.measure_surface()` and the `a7403f2f` numbers captured before the edit
**When** the Claude commands, reference files and Codex skills are measured
**Then** each meets its bound in the Outcomes table

## 🚫 Non-Goals

- Moving the Codex preamble out of the stage skills (no Codex reference-file mechanism yet).
- Changing any CLI output other than `spec_machine check --all`. `memory_retrieve`, the boundary's
  `judgment_directive` and `verification_cache`'s stderr line are examined and left alone.
- Changing `spec_machine validate`, `cross-validate`, `approve` or the content hash. A declared
  light machine schema is not added.
- A PLAN on light outside the blocked-phase case. The phases do not persist across sessions: an
  interrupted light execute re-states them from the SPEC and the diff.
- Changing the light-check record (IRR-002 of s3a), the boundary skip, or `/hm:loop`.
- Changing the full lane beyond the deltas listed in Outcomes.
- Re-running the bench (stage 4).

## ⚠️ Constraints

| Constraint | Value | Rationale |
|---|---|---|
| Test framework | `pytest` | Project standard (CLAUDE.md) |
| Oracle source | `a7403f2f` renders, CLI outputs and surface numbers captured in a detached worktree before any edit, under `tests/fixtures/light_lane_s3c/` | Byte-identical moves and "unchanged" claims need an independent reference |
| One pointer form | A and C use `stages/_partials/ref_pointer.md.j2`; moved text sits between `@hm:ref:start` / `@hm:ref:end` | Same rule as s2b and s3a; a test slices the markers |
| One source per moved text | The Claude reference file and the Codex inline arm include the same partial | Two copies would drift |
| No-PLAN condition | No `PLAN-{slug}.md` **and** the SPEC frontmatter `lane` is exactly `light` | A full task missing its PLAN must still fail (S13) |
| Fail direction | A missing preamble file runs gated; a missing `execute-plan.md` or `spec-machine-full.md` is a STOP | Losing the picker only removes autonomy; losing PLAN text would break later stages |
| Quality floor | The minimal yaml keeps every key a gate reads (T1 mutation keys, `irreversible_decisions`); Check 6, drift and the objective gate still run on light | intent.yaml rule: no quality floor traded for size |
| Generated-file frontmatter | The three new files carry `generated_by`, `content_hash`, `source_template`, `harness_maker_version` | CLAUDE.md security rule |
| Registry | No new `Step` / `Phase` / `Check` heading; moved bodies leave their headings in the command | `test_step_sensitivity_registry.py` |
| Supersedes | s3a AC-011 (typed review/verify/wrapup/loop byte-identical to `e7dd6648`) holds only up to this SPEC's named deltas (S14) | User decisions 2026-10-15 |
| Goldens | Re-captured with a dated note: `test_autopilot_gate_render` golden, `tests/fixtures/strictness_reference/`, s3a render SHAs, `surface_baseline.json` + `work-docs/BASELINE-DELTA-hm-light-lane-s3c.md` | Their own docstrings require the dated note |
| Compatibility | Python 3.12; re-render through `/hm:make`; an old render keeps writing a PLAN and its stages read the inline preamble | Mixed versions fail toward today's behavior |

## 🔒 Irreversible Decisions

| Id | Decision | Category | Rationale |
|---|---|---|---|
| IRR-001 | `hm spec_machine check --all` prints one line whenever no gate failed, a weak score included, and its failure payload drops `scores`, `yaml_path` and `md_path`, prints each error once (pydantic as `<loc>: <msg>`) and turns `by_rule` into counts | public API/CLI contract | Rendered spec text and any script parsing the payload read these keys; restoring them later breaks readers written against the quiet form |
| IRR-002 | A trusted light task outside loop mode has no `work-docs/PLAN-{slug}.md`; its `spec_need_verdict` / `spec_need_target` live in the SPEC `.md` frontmatter; every PLAN reader accepts "no PLAN + SPEC `lane: light`" | schema/file format/storage layout | Light tasks land in history without a PLAN; no reader may later require one for them |
| IRR-003 | A light machine.yaml carries only the minimal key set (Step 3.5) | schema/file format/storage layout | Committed light SPECs lack the optional keys; a validator may never require them for a light SPEC |
| IRR-004 | Add the generated files `.claude/hm/stage-preamble.md`, `.claude/hm/execute-plan.md` and `.claude/hm/spec-machine-full.md`, the names the commands read | schema/file format/storage layout | Renaming needs a retire step for copies on disk (s2b IRR-001, s3a IRR-003) |

## ✅ Verification Criteria

| Scenario | Verification mode | Test name / manual step |
|---|---|---|
| S1 | unit (render) | `tests/render/test_render_light_lane_s3c.py::test_stage_commands_point_at_the_preamble` |
| S2 | unit (render, differential) | `tests/render/test_render_light_lane_s3c.py::test_preamble_moved_byte_for_byte`, `tests/render/test_render_light_lane_s3c.py::test_health_signals_still_pass` |
| S3 | unit (render, differential) | `tests/render/test_render_light_lane_s3c.py::test_codex_and_claude_md_keep_the_preamble` |
| S4 | unit (CLI) | `tests/unit/test_spec_machine_check_quiet.py::test_no_failed_gate_prints_one_line` |
| S5 | unit (CLI, differential) | `tests/unit/test_spec_machine_check_quiet.py::test_failure_prints_each_error_once`, `tests/unit/test_spec_machine_check_quiet.py::test_failure_output_is_at_most_half` |
| S6 | unit (CLI, differential) | `tests/unit/test_cli_output_one_line.py::test_light_path_clis_unchanged` |
| S7 | unit (render) | `tests/render/test_render_light_lane_s3c.py::test_light_execute_writes_no_plan` |
| S8 | unit (render, differential) | `tests/render/test_render_light_lane_s3c.py::test_full_execute_reads_the_moved_plan_text` |
| S9 | unit (CLI) | `tests/unit/test_light_lane_no_plan.py::test_minimal_machine_yaml_validates_and_approves` |
| S10 | unit (render, differential) | `tests/render/test_render_light_lane_s3c.py::test_spec_step_3_5_minimal_inline` |
| S11 | unit (render, unit) | `tests/render/test_render_light_lane_s3c.py::test_light_readers_accept_no_plan`, `tests/unit/test_light_lane_no_plan.py::test_python_readers_accept_no_plan` |
| S12 | unit (CLI) | `tests/unit/test_light_lane_no_plan.py::test_objective_gate_reads_the_spec_link` |
| S13 | unit (render, CLI) | `tests/unit/test_light_lane_no_plan.py::test_missing_plan_without_light_fails_as_before` |
| S14 | unit (render, differential) | `tests/render/test_render_light_lane_s3c.py::test_full_lane_changes_only_by_named_deltas` |
| S15 | unit (structural) | `tests/render/test_render_light_lane_s3c.py::test_surface_meets_bounds` |
| Outcome (spec text) | unit (render) | `tests/render/test_render_light_lane_s3c.py::test_spec_describes_quiet_check` |
| Outcome (upsert) | unit | `tests/unit/test_light_lane_no_plan.py::test_spec_need_upsert_into_spec_keeps_it_intact` |

### AC-001: Every Claude stage command carries the preamble pointer in place of the preamble
### AC-002: stage-preamble.md holds the a7403f2f preamble byte-for-byte in every config arm
### AC-003: Codex stage skills, CLAUDE.md and AGENTS.md keep the inline preamble
### AC-004: The health audit's locale and banner signals still pass
### AC-005: A check run with no failed gate prints one line
### AC-006: A failing check prints each error once with the same verdict and exit code
### AC-007: Check output on the failure fixtures is at most half of a7403f2f's
### AC-008: The other light-path CLIs print the same single success line as a7403f2f
### AC-009: The spec stage describes the quiet check output
### AC-010: A trusted light execute outside loop mode writes no PLAN
### AC-011: Every other execute writes the PLAN from execute-plan.md, whose text is a7403f2f's
### AC-012: A minimal light machine.yaml passes check, approve and approval-status
### AC-013: Spec Step 3.5 shows the minimal schema inline and the full-lane fields on demand
### AC-014: Every light-path text reader accepts a light task without a PLAN
### AC-015: Python readers accept a light task without a PLAN, and the objective gate reads the SPEC link
### AC-016: spec_need fields upserted into a SPEC keep its frontmatter, body and approval
### AC-017: A missing PLAN without lane light fails exactly as on a7403f2f
### AC-018: Full-lane renders differ from a7403f2f only by the named deltas
### AC-019: The rendered surface meets the per-stage bounds

## ❓ Open Questions

- **C's split costs the full lane about +4.6k carried chars and two Reads per run.** Execute's
  PLAN text and spec's full-lane yaml fields move to reference files, so the light lane stops
  carrying them. Keeping them inline would save the light lane only the written documents
  (≈ −4.9k instead of ≈ −9k) and cost the full lane nothing. Agent default: split (PLAN ADR-005).
- **Scope without a PLAN is LLM-judged.** When a light task has no PLAN, the drift rule uses the
  SPEC's scenarios (light check, a typed `/hm:review`, and the review that runs after a failed
  light check). That is weaker than a declared file scope. It matches the trade-off the DRI
  accepted ("less audit trail for small tasks"), but it also covers the review fallback.
- **Most bench `check` failures are golden-row shape errors** (`input` not a mapping, `expected`
  missing). The minimal inline schema shows the row shape, so both lanes see it. Whether that
  lowers the retry count is unmeasured until the stage 4 bench.
- The carried-chars figures are estimates from 26 bench runs. `hm_cost_ratio_small` is unmeasured
  until the stage 4 bench is re-run on this change.

## 🔍 Refinement Decisions

- Interview not run: the three cuts are the DRI's 2026-10-15 decisions. The defaults below are
  agent decisions recorded as PLAN ADRs with their owner.
- Lane `full`: about 25 files and four irreversible decisions.
- B narrowed to `check` after measuring. "One line on success" already held for every light-path
  CLI, including `check` on a clean pass. The cost is in failure payloads, so B removes their
  repetition and keeps every distinct error. The other CLIs are pinned, not changed.
- C keeps the validator unchanged: the minimal file already validates, so a declared light schema
  would add code for no gain (the simpler option the DRI asked for).
- C excludes loop mode, as the 3a light check does.
- C writes the spec_need fields into the SPEC frontmatter, not into a ledger or a stub PLAN. The
  `.md` is outside the approval hash, and Check 6 already reads frontmatter.
- The objective-gate fallback uses the `.md` lane, not `lane_of`. An unapproved light SPEC with no
  PLAN still has its link checked, and `lane_of` would read it as `full` and skip the gate (fail
  open).
- Evaluated, not irreversible: the objective gate reading the SPEC link (a revert restores it),
  and the execute Step 0 `approval-status` call.
- Work stays on the session's designated branch, as in stages 1–3a.
