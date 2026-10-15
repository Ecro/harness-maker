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
adrs: 9
summary: "Three token cuts: one stage preamble per session (A), a quiet spec_machine check (B), no PLAN and a minimal machine.yaml on light (C)"
---

# PLAN — hm-light-lane-s3c (stage 3c, three token cuts)

## 🎯 Goal

This PLAN removes text a small /hm: task carries without using, in three phases: A, then B, then C
(SPEC-hm-light-lane-s3c). A and B apply to both lanes. C applies to the light lane only. The full
lane changes only by the deltas the SPEC lists. Each phase lands with its own surface delta
recorded.

## 🧭 ADRs

### ADR-001: The preamble moves to a reference file read once per session (A)
**Decided by:** user (cut A, 2026-10-15); the mechanism is the agent's. The preamble is the start
banner, the autopilot picker and the output-language block, byte-identical across the six stage
commands. It moves to `.claude/hm/stage-preamble.md` behind the s2b `ref_pointer` partial, with
`ref_missing` set so that a missing file means "no banner, no picker, run gated", not STOP. The
read-once condition is the model's own context ("unless this session's context already holds
it"). No marker file is used, because a marker would outlive a compaction that dropped the text.
After a compaction the stage reads the file again, which is the safe direction.

### ADR-002: The pointer keeps the health markers; readiness is unchanged (A)
**Decided by:** agent. `readiness._dim_workflow_clarity` checks for `@hm:output_language` and
`@hm:banner:start` in every stage command. The pointer carries both comments, so the audit keeps
its meaning ("the wrapper did not drop the partial") without a code change. The alternative, a
readiness change that follows the pointer to the file, adds a reader for no gain.

### ADR-003: Codex keeps its inline preamble (A)
**Decided by:** agent. Codex has no reference-file precedent (s2b and s3a inline every moved
body), and AGENTS.md already carries the language directive. This is left as a follow-up rather
than a second mechanism inside this change.

### ADR-004: B changes only `spec_machine check`; the other CLIs are pinned (B)
**Decided by:** agent, after measuring 26 bench hm runs.
- Success is already one line for every light-path CLI. The remaining cost is `check`'s failure
  payload, 92% of its ~9.9k chars per run, because each error is printed three times.
- B removes the repetition and keeps every distinct error. The agent needs the errors to fix the
  SPEC, so failure details are never cut.
- The weak-but-passing case also becomes one line. It was the only success path that still
  printed the full payload.
- `memory_retrieve`, the boundary's `judgment_directive` and `verification_cache`'s stderr line
  are left as they are: data, an instruction, and ~150 chars. A test pins the light-path CLIs at
  one line, byte-equal to `a7403f2f`.

### ADR-005: C moves full-lane-only authoring text to reference files (C)
**Decided by:** agent; SPEC open question 1 asks the DRI to confirm.
- Moved: execute's Step 0 and Step 0.3 bodies go to `.claude/hm/execute-plan.md`. The full-lane
  fields of spec Step 3.5 go to `.claude/hm/spec-machine-full.md`. The headings stay in the
  commands.
- Light lane: stops carrying ~5.4k chars.
- Full lane: makes two Reads (≈ +1k line-number overhead) and carries the light-branch text
  (≈ +3.6k with the no-PLAN sentences).
- The alternative is inline text plus light-branch sentences. It saves the light lane only the
  written documents (≈ −4.9k instead of ≈ −9k).
- Codex inlines both arms through the same partials.

### ADR-006: No-PLAN branches are conditional on "no PLAN and SPEC `lane: light`" (C)
**Decided by:** agent.
- Every PLAN reader on the light path gets one sentence for this case, and on the full lane the
  sentence is inert.
- The condition reads the `.md` lane, not `lane_of`. The objective gate is the reason: `lane_of`
  reads an unapproved light SPEC as `full`, so that SPEC would skip the link check and fail open.
- A full task missing its PLAN still fails as today (SPEC S13).
- Execute is the only writer that decides "no PLAN", and it does so only on `trusted_lane:
  light` outside loop mode.

### ADR-007: spec_need fields go into the SPEC frontmatter (C)
**Decided by:** agent. Check 6 already reads frontmatter. The SPEC `.md` sits outside the approval
hash, and `spec_need frontmatter-upsert --plan <path>` already works on any fenced `.md` under the
root. Two alternatives were rejected. A stub PLAN is the document C removes, and a ledger read
would be a new reader.

### ADR-008: The validator is unchanged; the minimal yaml is the light schema (C)
**Decided by:** agent (the DRI asked for the simpler option).
- Today's validator, scorer and `approve` accept a file with only the required keys.
- The mutation dimension is omitted, not zeroed, when `mutation_threshold` and `paths_to_mutate`
  are absent.
- At `verification_tier: 1` the minimal set keeps those two keys: the T1 mutation gate exits 0 on
  an empty `paths_to_mutate`, and dropping them would lower a quality floor.

### ADR-009: Loop mode and a blocked phase keep the PLAN (C)
**Decided by:** agent. A loop iteration's context does not survive, so its PLAN does (as with the
3a light check). A blocked light phase writes the PLAN from `execute-plan.md` before escalating,
so the blocker persists across sessions.

## 📝 Implementation Plan

Before any edit, in a detached `a7403f2f` worktree under the scratchpad, capture into
`tests/fixtures/light_lane_s3c/`:
- the preamble spans (Claude and Codex, every config arm);
- the Step 0, Step 0.3 and Step 3.5 slices;
- the CLAUDE.md and AGENTS.md language sections;
- `check` outputs on the failure fixtures;
- the light-path CLI outputs;
- the full-lane renders for S14;
- `measure_surface()`.

Write each phase's tests RED against those captures, then implement.

1. **Phase 1 — A, one preamble.** depends_on: none · parallel_group: 1 · merge_hazards: every
   stage command's bytes move (goldens).
   - Scope:
     - `templates/hm/stage-preamble.md.j2` (new; ref markers around the two existing partials);
     - `templates/commands/hm/atomic_command.md.j2` (pointer in place of the two includes);
     - `synthesize._STAGE_REFERENCE_FILES`;
     - `tests/render/test_render_light_lane_s3c.py` (AC-001..004);
     - the Claude halves of `test_render_autopilot_picker_runtimes.py`,
       `test_autopilot_template_render.py` and `test_locale_observability.py`, which now read the
       reference file for Claude;
     - re-captured goldens with a dated note: `test_autopilot_gate_render` and
       `tests/fixtures/strictness_reference/`;
     - the s3a render SHAs;
     - `surface_baseline.json` and §A of `work-docs/BASELINE-DELTA-hm-light-lane-s3c.md`.
   - Exit: AC-001..004 green; each Claude stage command is ≤ −3,762 chars.
   - Risk: medium (golden churn).
   - Rollback: revert the phase.
2. **Phase 2 — B, quiet check.** depends_on: none · parallel_group: 1 · merge_hazards: the spec
   Step 4 text.
   - Scope:
     - `spec_machine._run_check_all`: payload builder only, since `validate()`, `cross_validate()`
       and the other subcommands keep their output;
     - `templates/stages/spec.md.j2` Step 4 description;
     - `tests/unit/test_spec_machine_check_all.py`, updated to the new contract;
     - `tests/unit/test_spec_machine_check_quiet.py` and
       `tests/unit/test_cli_output_one_line.py` (new; AC-005..009);
     - BASELINE-DELTA §B.
   - Exit: AC-005..009 green.
   - Risk: low.
   - Rollback: revert the phase.
3. **Phase 3 — C, light document set.** depends_on: 1 (the pointer partial use is shared) ·
   parallel_group: 2 · merge_hazards: shared verify and review partials, goldens.
   - Scope:
     - `templates/hm/execute-plan.md.j2` and `templates/hm/spec-machine-full.md.j2` (new), with
       their partials;
     - `templates/stages/execute.md.j2` (Step 0 lane branch, the "the PLAN" definition, pointers);
     - `templates/stages/spec.md.j2` (Step 3.5 minimal inline);
     - `_partials/{verify_check_6,review_drift_scan,review_drift_verdict,verify_checks,wrapup_steps}.md.j2`;
     - `templates/stages/{wrapup,review}.md.j2`;
     - `templates/skills/verify-before-completion/SKILL.md.j2`;
     - `autopilot_caps._plan_link`, with a SPEC fallback on the `.md` lane;
     - `tests/unit/test_light_lane_no_plan.py` and the rest of
       `tests/render/test_render_light_lane_s3c.py` (AC-010..019);
     - goldens re-captured with a dated note;
     - BASELINE-DELTA §C;
     - `CHANGELOG.md`.
   - Exit: AC-001..019 green; ruff, format and mypy --strict clean; `uv run pytest tests -n auto`
     green except the known environment failures.
   - Risk: medium (many readers; S13 and S14 are the guards).
   - Rollback: revert the phase.

## 🚧 Contract Boundaries

### Do not change
- `spec_machine.validate`, `cross_validate`, `approve`, `approval_state`, the content hash and the
  `validate` / `cross-validate` / `approval-status` CLI output.
- `light_lane.py`, the light-check record format, the boundary skip and the boundary JSON key set.
- `wrapup_land.py`, `wrapup_brief.py`, `world_model_digest.py`, `drift_monitor.py` and
  `surface_allowance.py`, beyond tests that pin their no-PLAN behaviour.
- `templates/commands/hm/loop.md.j2` and Gate 0.
- The Codex preamble span, CLAUDE.md and AGENTS.md.
- `_HUMAN_GATED_STAGES` and `_JUDGMENT_GATED_STAGES`.

## 🧪 Testing Strategy

The tests are differential against the `a7403f2f` captures for every "moved" or "unchanged"
claim (AC-002/003/006/007/008/011/013/017/018). The other ACs are goldens written from the SPEC
text. Byte-identity of moved text is checked by slicing `@hm:ref:start` / `@hm:ref:end`. No live
model and no `INTEGRATION=1`.

## ⚠️ Risks & Mitigation

| Risk | Mitigation |
|---|---|
| The model skips the preamble Read, believing it already holds it | the read-once rule names the file; a missed banner is cosmetic and a missed picker leaves the session gated (fails toward less autonomy) |
| A compaction drops the preamble mid-session | the condition is "context holds it", so the next stage re-reads |
| An ad-hoc script parses `check`'s old keys (`scores`, `by_rule` lists, paths) | the bench showed improvised pipes reading `validate`, which is kept; IRR-001 names the change and CHANGELOG states it |
| A PLAN reader is missed and fails closed on light | the reader list comes from grepping the `a7403f2f` render and the Python sources for PLAN reads; AC-014/015 cover each one |
| A no-PLAN branch opens the full lane | the branch is conditional on the `.md` lane; AC-017 is a differential on full or absent-lane SPECs with no PLAN |
| Drift without a PLAN is weaker (LLM-judged scope from the SPEC's scenarios) | accepted trade-off (SPEC open question 2); Check 2/4/6 are deterministic and unchanged |
| An interrupted light execute loses its phase block | the next execute re-states it from the SPEC and the diff; a blocked phase writes the PLAN (ADR-009) |
| C's full-lane cost (+4.6k est.) outweighs the light-lane gain on a mostly-full workload | SPEC open question 1; the stage 4 bench measures both lanes |
| The golden churn hides an unintended byte change | S14 normalises by a fixed whitelist, so any other byte that moved fails |

## ✅ Success Criteria

- [ ] AC-001 … AC-019 of SPEC-hm-light-lane-s3c pass.
- [ ] BASELINE-DELTA records the per-stage chars after each phase, against the SPEC's bounds.
- [ ] Re-run the stage 4 bench on light and full tasks and record `hm_cost_ratio_small` (follow-up).

## 🔜 Follow-ups

- The Codex preamble once a Codex reference-file mechanism exists.
- Whether the inline golden-row shape lowers `check` retries (SPEC open question 3), from the
  stage 4 bench.
