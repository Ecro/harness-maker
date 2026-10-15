---
type: spec
task_slug: hm-light-lane-s3a
status: draft
created: 2026-10-15
tags: [harness-maker, spec, autopilot, cost, light-lane, execute, review, verify]
test_framework: pytest
tier: 2
interview_rounds: 0
lane: full
intent: HM-LIGHT-LANE
research_doc: "[[RESEARCH-hm-light-lane]]"
summary: "Stage 3a of HM-LIGHT-LANE: the light lane runs spec → execute (+ one light check) → wrapup, without review and verify stage turns"
---

# SPEC — hm-light-lane-s3a (stage 3a, fewer light stages)

## 🎯 Intent

On the 2026-10-14 bench (after stage 2b) a completed /hm: run cost about ×17 a plain run on small
tasks. By stage the spend was review 30%, spec 22%, execute 20%, verify 18% and subagents 10%. No
stage dominates, because the carried context is paid again in every stage turn, so removing whole
stage turns is the largest simple lever left. On those tasks review and verify caught nothing the
plain arm missed (plain passed 15/15 hidden tests). The user decided on 2026-10-15 that the light
lane runs spec → execute → **one** combined check, without separate `/hm:review` and `/hm:verify`
stage turns. Stage 3b (light execute and verify in subagents) comes later and is out of scope.

## 🌅 Outcomes

- On `lane: light`, `/hm:execute` ends with a **light check** (new `### Step 4.2`) after all PLAN
  phases are GREEN. It is deterministic and dispatches no reviewer or other subagent. It runs:
  - the `reviewers.mechanical_checks` commands, when configured (review Phase 0);
  - verify **Check 2** (regression smoke, `verification_cache run`), **Check 4** (unresolved high
    security findings) and **Check 6** (SPEC requirement), read from verify's own text (Claude
    Code and Cursor: `.claude/hm/verify-checks.md`; Codex: `.agents/skills/hm-verify/SKILL.md`),
    so the check text has one source;
  - `hm cli security-scan .` first, so Check 4 reads findings for this tree;
  - review **Step 2**'s drift rule, from a partial review also includes, so the rule text has one
    source.
- When every check passes and drift is `clean`, the light check writes a **light-check record**
  `REVIEW-{slug}-{date}.md`, the file name review uses, with this frontmatter:
  `type: review`, `review_kind: light-check`, `task_slug`, `status: PASSED`, `created`,
  `drift_verdict` (review Step 2's block) and `checks` (`mechanical`, `regression`, `security`,
  `spec_requirement`, each `pass` or `n-a`; `structural: not-run`). Wrapup Step 3 and verify
  Check 1 read its `drift_verdict` unchanged, and `wrapup_land` stages it through the existing
  optional `REVIEW-{slug}-*.md` path.
- The light check writes **no** record, and says that review runs next, when it does not run
  (loop mode is active for this session, or more than 10 paths changed: the diff reads as `full`)
  or when drift is not `clean`. A failed check gets one repair round; a second failure takes
  Step 4's blocked path. On every path that writes no record it removes an earlier light-check
  record for this slug, and never touches a real REVIEW.
- Under autopilot, `hm autopilot_caps boundary` skips `review` and `verify` when the SPEC's `lane`
  is exactly `light` **and** the newest `REVIEW-{slug}-{date}.md` is a `PASSED` light-check record
  for this slug. The decision is made in Python. With the default pipeline, execute's boundary
  then reports `next_stage: wrapup`, which is human-gated: `halt_kind: merge_gate` and the marker
  is cleared, as verify's boundary does today. The JSON keys do not change; `reason` names the
  skipped stages. The ledger gets one new `stage_skipped` row
  `{from, skipped, to, reason: "lane light"}`.
- With no passing record (a full lane, no `lane`, any value but exactly `light`, no slug, an
  unreadable SPEC, or a light check that wrote nothing), the boundary is byte-identical to
  `e7dd6648`: same JSON and same ledger rows. The skip fails closed onto today's pipeline.
- A user who types `/hm:review` or `/hm:verify` on a light task runs them as today. Their
  commands and wrapup's are byte-identical to the `e7dd6648` render. A real review written after
  the light check is the newest REVIEW record, so a later boundary no longer skips.
- Maker's `hm world_model digest` agrees with the boundary: on a light SPEC whose newest REVIEW is
  a `PASSED` light-check record, `next_stage` is `wrapup`.
- Execute's auto-advance gate names a failed light check as pending (`gate-blocked`, then STOP).
- `/hm:loop` is unchanged: its `--per-iter-stages` list is explicit and Gate 0 requires a receipt
  from every listed stage. The light check skips itself in loop mode.

## 📋 In-Scope Scenarios

### S1: A light task goes from execute to wrapup under autopilot
**Given** an armed autopilot session with the default pipeline and a SPEC with `lane: light`
**When** execute's light check passes and execute runs its boundary
**Then** the boundary JSON has `proceed: false`, `halt_kind: merge_gate`, `next_stage: wrapup`
**And** the ledger has a `stage_skipped` row naming `review` and `verify`, then `gate_blocked` for `wrapup`
**And** no `advance_authorized` row names `review` or `verify`

### S2: Full-lane pipelines do not change
**Given** a SPEC with `lane: full`, no `lane`, a value other than exactly `light`, or no SPEC
**When** any stage runs its boundary at any level and judgment verdict
**Then** the JSON and the ledger rows equal the `e7dd6648` output for the same inputs

### S3: No passing light-check record, no skip
**Given** a SPEC with `lane: light` whose newest REVIEW record is absent, a real review, or a light-check record that is not `PASSED` or names another slug
**When** execute runs its boundary
**Then** the next stage is `review`, as today, and no `stage_skipped` row is written

### S4: The skip respects narrowed and custom pipelines
**Given** a passing light-check record and a pipeline that ends at `verify`, is narrowed to `review`, or lists `[execute, verify, wrapup]`
**When** execute runs its boundary
**Then** the skip continues to the first stage after execute that is neither `review` nor `verify`; with none left, the boundary returns `pipeline_complete` (or `narrow_end` on a narrowed marker), as at a pipeline's last stage

### S5: The light check runs the gates that must not be lost
**Given** a rendered execute command (Claude Code) and execute stage skill (Codex)
**When** the light check's text is read
**Then** it runs the configured mechanical checks, `security-scan`, verify Checks 2, 4 and 6 from verify's own text, and review Step 2's drift rule
**And** it dispatches no reviewer or other subagent

### S6: The light check fails closed
**Given** a light check that fails, finds drift, does not run in loop mode, or meets more than 10 changed paths
**When** it ends
**Then** it writes no record and removes an earlier light-check record for this slug
**And** on a failure it repairs once, then takes Step 4's blocked path, and the auto-advance gate is pending

### S7: Wrapup accepts the light-check record
**Given** a light-check record written by the light check
**When** wrapup Step 3 and verify Check 1 read it
**Then** `drift_verdict` is present with this slug's `task_slug`, so both pass with their `e7dd6648` text

### S8: Typed stages and the loop are untouched
**Given** a render of these answers before and after the change
**When** the review, verify, wrapup and loop commands and the Codex review, verify and wrapup skills are compared
**Then** each is byte-identical to its `e7dd6648` render

### S9: Maker routes a checked light task to wrapup
**Given** a light SPEC, a PLAN and a `PASSED` light-check record
**When** `hm world_model digest` computes `next_stage`
**Then** it is `wrapup`; the same artifacts on a full SPEC give `review`, as today

## 🚫 Non-Goals

- Stage 3b: running light execute or verify through `stage-delegate`, and lens results as verdict + path.
- Changing the full lane: its stages, gates, rounds and dispatches.
- Changing `/hm:loop`, its default `execute,review` stage list, or Gate 0.
- Auto-entering wrapup. It stays human-gated (`_HUMAN_GATED_STAGES`) on every lane.
- Removing or rewording review or verify. Typed, they run their full text on any lane.
- A new stage, a new harness.yaml key, or a `lane` field in the machine SPEC.
- Running a second-opinion model on light. Configured models run only when `/hm:review` is typed.
- Verify Check 3 (structural delta) and probe A1 on light. The record says `structural: not-run`.
- Reading `work_docs.dir` other than `work-docs/` for the record (the digest's accepted limitation).

## ⚠️ Constraints

| Constraint | Value | Rationale |
|---|---|---|
| Test framework | `pytest` | Project standard (CLAUDE.md) |
| One lane reader | `light_lane.lane_of` and `light_lane.light_check_passed` in Python, used by the boundary and the digest | Two readers would disagree on a malformed SPEC |
| Fail closed | Any read error, unknown value or missing record means no skip | A missing check must never remove two stages |
| Boundary JSON | Same keys and types; the skip shows only in `next_stage`, `reason` and the ledger | Rendered prompts and Codex branch on these keys |
| Placement | The skip is applied where `next_stage` is computed, after the cap, slug and judgment checks | Every existing halt keeps its precedence |
| Single source | Verify's checks are read from verify's text; review Step 2's drift rule moves into a partial both include | A copy would drift |
| Reference file | The Claude Code light-check text renders in `.claude/hm/execute-light-check.md`, read from the project root, never from `<WT>`; missing → STOP naming it | Same rule as SPEC-hm-light-lane-s2b; full-lane runs never read it |
| Generated-file frontmatter | The new file carries `generated_by`, `content_hash`, `source_template`, `harness_maker_version` | CLAUDE.md security rule |
| Supersedes | PLAN-hm-light-lane ADR-003 ("review keeps every lens on light") holds only for a typed `/hm:review`; review Step 2 is no longer the only writer of a `drift_verdict` (the rule text still has one owner) | User decision 2026-10-15 |
| Size | The Claude execute command grows by at most 1,000 characters; the size baseline is re-frozen with a BASELINE-DELTA if the aggregate ratchet requires | Lever 2: full-lane runs carry only a pointer |
| Registry | The new heading is classified in `step_sensitivity.py` | `test_step_sensitivity_registry.py` fails on an unclassified heading |
| Compatibility | Python 3.12; existing harnesses re-render through `/hm:make` with no migration; an old render's execute writes no record, so its boundary never skips | Mixed versions fail closed |

## 🔒 Irreversible Decisions

| Id | Decision | Category | Rationale |
|---|---|---|---|
| IRR-001 | Add `stage_skipped` to the autopilot ledger's closed event vocabulary, with fields `from`, `skipped`, `to`, `reason` | schema/file format/storage layout | Once rows exist the name stays readable forever, as `advanced` and `objective_proposed` do; `/hm:health`'s smoke denominator counts every event |
| IRR-002 | The light-check record is `REVIEW-{slug}-{date}.md` with `review_kind: light-check` and `status: PASSED`, carrying review's `drift_verdict` | schema/file format/storage layout | Wrapup commits it, so it persists in history. The boundary, the digest, wrapup Step 3 and verify Check 1 read it, and a reader may not later drop `review_kind` |
| IRR-003 | Add the generated file `.claude/hm/execute-light-check.md`, the name the execute command reads | schema/file format/storage layout | Renaming it needs a retire step for copies on disk (as SPEC-hm-light-lane-s2b IRR-001) |

## ✅ Verification Criteria

| Scenario | Verification mode | Test name / manual step |
|---|---|---|
| S1 | unit (CLI) | `tests/unit/test_autopilot_caps_light_lane.py::test_light_execute_skips_review_and_verify` |
| S2 | unit (CLI, differential) | `tests/unit/test_autopilot_caps_light_lane.py::test_full_lane_boundary_matches_e7dd6648` |
| S3 | unit (CLI) | `tests/unit/test_autopilot_caps_light_lane.py::test_no_passing_record_no_skip` |
| S4 | unit (CLI) | `tests/unit/test_autopilot_caps_light_lane.py::test_skip_respects_pipeline_shape` |
| S5 | unit (render) | `tests/render/test_render_light_lane_s3a.py::test_light_check_runs_the_kept_gates` |
| S6 | unit (render) | `tests/render/test_render_light_lane_s3a.py::test_light_check_fails_closed` |
| S7 | unit | `tests/unit/test_light_lane.py::test_record_satisfies_wrapup_and_verify` |
| S8 | unit (render, differential) | `tests/render/test_render_light_lane_s3a.py::test_typed_stages_and_loop_unchanged` |
| S9 | unit | `tests/unit/test_light_lane.py::test_digest_routes_checked_light_task_to_wrapup` |
| Outcome (reader) | unit | `tests/unit/test_light_lane.py::test_lane_of`, `tests/unit/test_light_lane.py::test_light_check_passed` |
| Outcome (pointer) | unit (render) | `tests/render/test_render_light_lane_s3a.py::test_execute_points_at_the_light_check` |
| Outcome (ledger) | unit | `tests/unit/test_autopilot_caps_light_lane.py::test_stage_skipped_is_a_ledger_event` |
| Outcome (gate) | unit (render) | `tests/render/test_render_light_lane_s3a.py::test_execute_gate_names_a_failed_light_check` |

### AC-001: The lane reader reads exactly light, everything else as full
### AC-002: A passing light-check record is recognised only for its own slug
### AC-003: A checked light execute skips review and verify at the boundary
### AC-004: Full-lane boundaries are byte-identical to e7dd6648
### AC-005: The skip respects narrowed and custom pipelines
### AC-006: Without a passing record the boundary does not skip
### AC-007: Execute points at the light check, which renders as a reference file
### AC-008: The light check runs the kept gates and dispatches no subagent
### AC-009: The light check fails closed and writes a record only on a clean pass
### AC-010: The light-check record satisfies wrapup Step 3 and verify Check 1
### AC-011: Typed review, verify, wrapup and the loop are byte-identical
### AC-012: The digest routes a checked light task to wrapup
### AC-013: stage_skipped is a ledger event that does not count as an entered stage
### AC-014: Execute's auto-advance gate names a failed light check

## ❓ Open Questions

- `hm cli security-scan .` walks the whole repo, queries OSV.dev and may try an LLM pass for
  prompt injection (it falls back to regex). Its fresh-scan cache limits repeats, but its wall
  time on a large repo is unmeasured. Fallback if it is too slow: Check 4 alone, which reads the
  latest findings file without scanning.
- Whether removing two stage turns moves `hm_cost_ratio_small` toward ≤ 5 is unmeasured until the
  stage 4 bench is re-run on this change.

## 🔍 Refinement Decisions

- Interview not re-run: the scope and the "one combined check, no review/verify turns" shape are
  the user's 2026-10-15 decision; the DRI said on 2026-10-14 to run each stage on the recommended
  option. Defaults below are agent decisions.
- Lane `full`: about 12 files, and three irreversible decisions.
- Q1, where the check lives: a final step of `/hm:execute` (Step 4.2), not a new stage. A new stage
  would add a stage turn, which is the cost being removed. No reviewer dispatch: on the baseline
  tasks review caught nothing plain missed, and the security lens's mechanical part is kept
  through `security-scan` + Check 4.
- Q2, how the pipeline skips: in Python at the boundary, gated on a passing record rather than on
  the lane alone. Then a forgotten, skipped or failed light check falls back to today's review
  path instead of removing two stages unchecked. The skip is recorded as `stage_skipped`.
- Q3, what must not be lost: mechanical checks, regression (Check 2), security (scan + Check 4),
  SPEC requirement (Check 6) and the drift verdict run in the light check. Wrapup's own Step 2
  re-verification, Step 3 drift check, Step 3.5 write-back with the judgment-AC binding, and the
  Step 6/7 land hold for an unapproved SPEC are unchanged. Dropped on light: Check 3 (structural
  score of the harness, not the change), probe A1, Check 5 (loop-only), every review lens, the
  second-opinion models.
- Q4, runtimes: Claude Code and Codex call the same boundary, so they skip alike; Codex inlines the
  light check and reads Checks 2/4/6 from its verify skill. Cursor has no auto-advance (as today):
  it runs the same execute command, and its banner already offers `/hm:wrapup`. `/hm:loop` is
  deliberately unchanged, because its stage list is explicit and Gate 0 exists to catch a skipped
  review (`loop-body-skipping-review-stage`).
- Q5, wrapup: unchanged. It needs a `drift_verdict` (the record supplies it) and a fresh
  verification marker (Check 2 in the light check writes it; Step 2 re-runs the suite otherwise).
  It reads no verify receipt outside loop mode. Its sentence "Review is the single owner (ADR-006)"
  stays, since the light check runs review's own Step 2 partial.
- The record uses `status: PASSED`, not `APPROVED`: nothing graded it, and `APPROVED` would make
  every reader treat it as a review. The digest's one change is to accept it on a light SPEC.
- Evaluated, not irreversible: the boundary's `next_stage` may now skip pipeline entries. Its keys
  are unchanged, an old render's execute writes no record (so no skip), and a revert restores it.
  Dropping review lenses on light is not a permission-boundary change; it is a policy the revert
  undoes.
- The 10-path guard follows review's "a diff well over five files reads as `full`".
- Work stays on the session's designated branch instead of an `hm/<slug>` task worktree, as in
  stages 1, 2a and 2b.
