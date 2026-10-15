---
type: plan
task_slug: hm-light-lane-s3c
status: planning
created: 2026-10-15
spec: "[[SPEC-hm-light-lane-s3c]]"
research_doc: "[[RESEARCH-hm-light-lane]]"
intent: HM-LIGHT-LANE
lane: full
tdd: true
adrs: 11
summary: "Three token cuts: one stage preamble per session (A), a quiet spec_machine check (B), a short PLAN and minimal machine.yaml on light (C)"
---

# PLAN — hm-light-lane-s3c (stage 3c, three token cuts)

## 🎯 Goal

This PLAN removes text a small /hm: task carries without using, in three phases: A, then B,
then C (SPEC-hm-light-lane-s3c). A and B apply to both lanes. C applies to the light lane only.
The full lane changes only by the deltas the SPEC lists. Every task, light ones included, still
has a PLAN, so no reader changes.

## 🧭 ADRs

### ADR-001: The preamble moves to a reference file, read once and applied every stage (A)
**Decided by:** user (cut A, 2026-10-15); the mechanism is the agent's.
- The preamble moves to `.claude/hm/stage-preamble.md` behind the s2b `ref_pointer` partial, with
  `ref_missing` set to "no banner, no picker".
- The pointer separates two things. Reading happens unless this session's context already holds
  the file. Applying happens either way, in order: the loop check, this stage's banner, then the
  picker only if it has not been answered this session.
- No marker file is used, because a marker would outlive a compaction that dropped the text.
  After a compaction the stage re-reads the file, which is the safe direction.

### ADR-002: `/hm:health` also checks the preamble file (A)
**Decided by:** agent (coordinator review of 2026-10-15).
- The pointer keeps both markers, so the per-command signals keep their meaning: the wrapper did
  not drop the partial.
- `_dim_workflow_clarity` additionally requires `.claude/hm/stage-preamble.md` to exist and
  carry both markers, so a missing file shows up in `/hm:health` instead of only as a missing
  banner.
- The file is required only when a stage command names `stage-preamble.md`. An older render,
  whose commands still inline the preamble, scores exactly as at `a7403f2f` (spec-validator
  pass 2), so upgrading the plugin never turns a valid project red before it re-renders.

### ADR-003: Codex keeps its inline preamble (A)
**Decided by:** agent. Codex has no reference-file precedent (s2b and s3a inline every moved
body), and AGENTS.md already carries the language directive. This is a follow-up, not a second
mechanism inside this change.

### ADR-004: B changes only `spec_machine check`, and keeps the scores that matter (B)
**Decided by:** agent, after measuring 26 bench hm runs.
- Success is already one line for every light-path CLI. The cost is `check`'s failure payload,
  92% of its ~9.9k chars per run, because each error is printed three times. B prints each
  error once.
- `low_dimensions: {dim: score}` (dims < 60) replaces the `scores` map, on both the weak line
  and the failure payload. It was chosen over the full 8-int map because it names exactly what
  pulls the score down. It is never empty when `overall` < 60, which covers the
  "block, overall 55, no dim < 40" case where `weak_dimensions` is empty.
- When `evaluate_spec` raises, `check` prints the failure-shaped payload with
  `quality: {"error", "strictness"}` and exits as today: 1 if a gate failed, else 0.
- The top-level `strictness` stays on every shape. A non-pydantic load error is one line:
  `yaml load failed: YAMLError: <problem> (line L, column C)` for a syntax error,
  `yaml load failed: FileNotFoundError: <path>` (or `OSError`) for a missing file. These edges
  came from spec-validator pass 2; none changes a verdict, they only fix what a test pins.
- The other light-path CLIs are pinned, not changed.

### ADR-005: Full-lane-only authoring text moves to reference files (C)
**Decided by:** agent; SPEC open question 1 asks the DRI to confirm.
- Execute's Step 0 body after its inline head (ADR-010) and the Step 0.3 body move to
  `.claude/hm/execute-plan.md`. Spec Step 3.5's full-lane fields move to
  `.claude/hm/spec-machine-full.md`. The headings stay in the commands.
- The light lane stops carrying ~3.8k chars of instructions net. The full lane makes two Reads and
  carries the light-branch text (≈ +4.6k).
- Codex inlines both arms through the same partials.

### ADR-006: The light lane writes a short PLAN, not no PLAN (C)
**Decided by:** user (DRI picked "Short PLAN" on the card, 2026-10-15), on the coordinator's
recommendation.
- spec-validator pass 1 found that "no PLAN" touched more than 10 readers, several of which
  failed open.
- A short PLAN from an inline template carries every key and section a gate reads, so no reader
  changes and the decided saving is mostly kept. The template filled from the SPEC's S9 value table (bench t1) measures 925
  chars, against 1.5–2.9k for the full template.
- The template drops what no gate reads: Executive Summary, Prior Work, Technical Design,
  Testing Strategy, Risks, Success Criteria, `tags`, `interview_rounds`, `validator_outcome`,
  and per-phase `depends_on` / `parallel_group` / `merge_hazards`. Step 1.5 therefore does not
  apply to it.

### ADR-007: The oversize rule sits in Step 0 (C)
**Decided by:** agent (coordinator review). If the light phases touch well over five files,
Step 0 writes the full PLAN and logs that the task reads as `full`. Step 2's existing rule and
the 3a light check's five-file skip then agree, and an oversize task never runs with the short
template.

### ADR-008: The validator is unchanged; the minimal yaml is authored, not enforced (C)
**Decided by:** agent (the DRI asked for the simpler option).
- Today's validator, scorer and `approve` accept the minimal key set. The mutation dimension is
  omitted, not zeroed.
- At `verification_tier: 1` the set keeps `mutation_threshold` and `paths_to_mutate`, because
  the T1 gate exits 0 on an empty `paths_to_mutate`.
- Tooling may materialise defaults later. No validator may require an optional key (IRR-003).

### ADR-009: Loop mode and an untrusted light lane write the full PLAN (C)
**Decided by:** agent.
- Loop mode: an iteration's context does not survive, and `/hm:loop` is unchanged.
- An untrusted light lane is treated as `full` by every other gate.

### ADR-010: Step 0's head stays inline; execute-plan.md is two slices with a separator (C)
**Decided by:** agent (spec-validator pass 2 critical finding).
- The two shared rules (the `<WT>`-rooted write path; "if that file already exists, do not
  rewrite it") apply to both arms. Leaving them only in the moved text would let a light
  re-entry overwrite the recorded `spec_need` pair and blocker notes, and let a worktree-on light
  PLAN land in the base tree where no gate reads it.
- The command keeps Step 0's `a7403f2f` head inline: the two intro paragraphs and then the two
  rules (980 chars). Keeping the intro too makes the head a pure prefix, so AC-016 rebuilds the
  body by concatenation instead of a reorder rule. That costs the light lane ~0.56k.
- `execute-plan.md` holds part 1 (the rest of Step 0), a fixed separator line, and part 2 (the
  Step 0.3 body). AC-011 compares each part on its own, so a byte moved across the boundary
  fails. The Step 0.3 heading carries one exact sentence that routes to the light read-back or
  to part 2.

### ADR-011: The light block is one marked span with exact routing strings (C)
**Decided by:** agent (spec-validator pass 2).
- The light text sits between `<!-- @hm:light-plan -->` and `<!-- @hm:/light-plan -->`: one
  span per file, right after the full-lane pointer, at most 2,400 chars (a draft measures 1,417).
- The routing sentence and the Step 0.3 sentence are exact strings in the SPEC. AC-016 deletes
  only those literals and the one span, so no implementation-chosen text is excused.
- The light read-back asserts four things: the template's frontmatter keys; scope/exit/risk/
  rollback on every phase; a non-empty Do not change list in the admitted forms, with `none`
  only alone; and `spec_need_verdict` after Step 0.1.
- The phase line is a fixed literal, so wrapup Step 4 (`- [ ]`) and the verify skill's 1b
  (numbered item) both match it.
- AC-012/013's fixture is derived from the rendered template and the SPEC's value table, so
  the bound follows the template the model actually fills.

## 📝 Implementation Plan

Before any edit, in a detached `a7403f2f` worktree under the scratchpad, capture into
`tests/fixtures/light_lane_s3c/`:
- the preamble spans, Claude and Codex, on every config arm (autonomy gated / auto_safe /
  auto_full / ask, worktree on and off, en and ko);
- the Step 0, Step 0.3, Step 3.5 and Step 4 slices;
- the CLAUDE.md and AGENTS.md language sections;
- `check` outputs on the failure fixtures;
- the light-path CLI outputs;
- the full-lane renders for AC-016;
- `measure_surface()`.

Write each phase's tests RED against those captures, then implement.

1. [ ] **Phase 1 — A, one preamble.** depends_on: none · parallel_group: 1 · merge_hazards:
   every stage command's bytes move (goldens).
   - Scope:
     - `templates/hm/stage-preamble.md.j2` (new; ref markers around the two existing partials);
     - `templates/commands/hm/atomic_command.md.j2` (the pointer replaces the two includes);
     - `synthesize._STAGE_REFERENCE_FILES`;
     - `readiness._dim_workflow_clarity` (the file check, only when a command names the file);
     - `tests/render/test_render_light_lane_s3c.py` (AC-001..003);
     - `tests/unit/test_readiness_stage_preamble.py` (AC-004);
     - the Claude halves of `test_render_autopilot_picker_runtimes.py`,
       `test_autopilot_template_render.py` and `test_locale_observability.py`, which now read the
       reference file;
     - goldens re-captured with a dated note: `test_autopilot_gate_render`,
       `tests/fixtures/strictness_reference/`, the s3a render SHAs;
     - `surface_baseline.json` and §A of `work-docs/BASELINE-DELTA-hm-light-lane-s3c.md`.
   - Exit: AC-001..004 green; every Claude stage command is ≤ −3,712 chars.
   - Risk: medium (golden churn).
   - Rollback: revert the phase.
2. [ ] **Phase 2 — B, quiet check.** depends_on: none · parallel_group: 1 · merge_hazards: the
   spec Step 4 text.
   - Scope:
     - `spec_machine._run_check_all`, the payload builder only (`validate()`, `cross_validate()`
       and the other subcommands keep their output), including the top-level `strictness`, the
       load-error one-liners and the raise-path `quality.strictness`;
     - `templates/stages/spec.md.j2`, the Step 4 description;
     - `tests/unit/test_spec_machine_check_all.py`, updated to the new contract;
     - `tests/unit/test_spec_machine_check_quiet.py` and `tests/unit/test_cli_output_one_line.py`
       (new; AC-005..009);
     - BASELINE-DELTA §B.
   - Exit: AC-005..009 green.
   - Risk: low.
   - Rollback: revert the phase.
3. [ ] **Phase 3 — C, short light PLAN and minimal yaml.** depends_on: 1 (shared pointer partial
   use) · parallel_group: 2 · merge_hazards: the execute and spec goldens.
   - Scope:
     - `templates/hm/execute-plan.md.j2` and `templates/hm/spec-machine-full.md.j2` (new), with
       their partials;
     - `templates/stages/execute.md.j2`: Step 0's inline head, the `approval-status` call and the
       exact routing sentence, the pointer, the one `@hm:light-plan` span (template, four-part
       read-back, Step 1.5 note, oversize rule) and the exact Step 0.3 heading sentence;
     - `templates/stages/spec.md.j2` (Step 3.5 minimal inline);
     - `tests/unit/test_light_plan.py` and the rest of `tests/render/test_render_light_lane_s3c.py`
       (AC-010..017);
     - the light-PLAN fixture, derived in-test from the rendered template and the SPEC's S9
       value table, and the `mark-tested` write-back round-trip (AC-014);
     - goldens re-captured with a dated note;
     - BASELINE-DELTA §C;
     - `CHANGELOG.md`.
   - Exit: AC-001..017 green; ruff, format and mypy --strict clean; `uv run pytest tests -n auto`
     green except the known environment failures.
   - Risk: medium (execute Step 0 is load-bearing; AC-011, AC-012 and AC-016 are the guards).
   - Rollback: revert the phase.

## 🚧 Contract Boundaries

### Do not change
- `src/harness_maker/templates/stages/review.md.j2` — the typed review changes only by A's pointer swap (AC-016)
- `src/harness_maker/templates/stages/verify.md.j2` — the same
- `src/harness_maker/templates/stages/wrapup.md.j2` — the same
- Advisory: every existing file under `src/harness_maker/templates/stages/_partials/` stays byte-identical; Phase 3 may only add new partials there
- `src/harness_maker/templates/hm/execute-light-check.md.j2`
- `src/harness_maker/templates/hm/verify-checks.md.j2`
- `src/harness_maker/templates/hm/wrapup-steps.md.j2`
- `src/harness_maker/templates/skills/verify-before-completion/SKILL.md.j2`
- `src/harness_maker/templates/commands/hm/loop.md.j2`
- `src/harness_maker/templates/codex/AGENTS.md.j2`
- `src/harness_maker/templates/skills/world-model/SKILL.md.j2` — Maker's decision capture is unchanged (confirmed)
- `src/harness_maker/light_lane.py`
- `src/harness_maker/autopilot_caps.py`
- `src/harness_maker/world_model_digest.py`
- `src/harness_maker/wrapup_land.py`
- `src/harness_maker/wrapup_brief.py`
- `src/harness_maker/spec_need.py`
- Advisory: `spec_machine.validate`, `cross_validate`, `approve`, `approval_state`, the content hash and the `validate` / `cross-validate` / `approval-status` output stay as they are; only `_run_check_all` changes

## 🧪 Testing Strategy

Every "moved" or "unchanged" claim is a differential against the `a7403f2f` captures
(AC-002/003/006/007/008/011/015/016). The other ACs are goldens written from the SPEC text.
Moved text is checked by slicing `@hm:ref:start` / `@hm:ref:end`. AC-012 runs real a7403f2f
readers (`_plan_link`, `wrapup_land`, `spec_need frontmatter-upsert`) on a light-PLAN fixture
filled from the rendered template, and AC-014 runs the real `mark-tested` write-back. No live model and no `INTEGRATION=1`.

## ⚠️ Risks & Mitigation

| Risk | Mitigation |
|---|---|
| The model skips the preamble Read, believing it already holds it | the pointer names the file and says "either way, apply it"; a missed picker leaves the session as armed or gated as it was |
| A compaction drops the preamble mid-session | the condition is "context holds it", so the next stage re-reads |
| A missing preamble file goes unnoticed | `/hm:health` now fails on it (ADR-002) |
| An ad-hoc script parses `check`'s old keys (`scores`, `by_rule` lists, paths) | improvised bench pipes read `validate`, which is kept; IRR-001 and CHANGELOG state the change |
| The light template drops a key a reader needs | the reader table comes from grepping the `a7403f2f` render and the Python sources; AC-012 runs the real readers on the fixture |
| The agent writes a long light PLAN anyway | the template is one screen; AC-013 bounds the template-derived fixture; the bench measures real ones |
| A light re-entry rewrites an existing PLAN, or a worktree-on light PLAN lands in the base tree | the two shared rules stay inline above the lane split (ADR-010); AC-010 pins them on worktree on and off |
| A mark-tested write-back invalidates a minimal light stamp | AC-014 round-trips `mark-tested` and re-reads `approval-status` |
| An oversize task runs with the short template | the Step 0 oversize rule writes the full PLAN (ADR-007) |
| C's full-lane cost (+4.6k est.) outweighs the light-lane gain on a mostly-full workload | SPEC open question 1; the stage 4 bench measures both lanes |
| Golden churn hides an unintended byte change | AC-016 deletes only the one light span and three exact SPEC literals, so any other byte that moved fails |

## ✅ Success Criteria

- [ ] AC-001 … AC-017 of SPEC-hm-light-lane-s3c pass.
- [ ] BASELINE-DELTA records the per-stage chars after each phase, against the SPEC's bounds.
- [ ] Re-run the stage 4 bench on light and full tasks and record `hm_cost_ratio_small` (follow-up).

## 🔜 Follow-ups

- The Codex preamble, once a Codex reference-file mechanism exists.
- The `verify-before-completion` skill's `ls PLAN-*.md | head -1` glob can pick another task's
  PLAN on any lane. This is pre-existing, out of scope.
- Whether the inline golden-row shape lowers `check` retries (SPEC open question 3), from the
  stage 4 bench.
