---
type: plan
task_slug: hm-light-lane-s3a
status: planning
created: 2026-10-15
spec: "[[SPEC-hm-light-lane-s3a]]"
research_doc: "[[RESEARCH-hm-light-lane]]"
intent: HM-LIGHT-LANE
lane: full
tdd: true
adrs: 8
summary: "Light lane runs spec → execute (+ light check) → wrapup; boundary skips review and verify on a passing light-check record"
---

# PLAN — hm-light-lane-s3a (stage 3a, fewer light stages)

## 🎯 Goal

On `lane: light`, drop the `/hm:review` and `/hm:verify` stage turns from the autopilot pipeline
and run one deterministic light check at the end of `/hm:execute`. Full-lane behaviour stays
byte-identical (SPEC-hm-light-lane-s3a). This splits PLAN-hm-light-lane stage 3: 3a is this
change; 3b (light execute and verify in `stage-delegate`) follows.

## 🧭 ADRs

### ADR-001: The combined check is execute Step 4.2, not a new stage
**Decided by:** agent (user decision 2026-10-15 set the shape: one combined check). A new stage
would add the stage turn whose carried context is the cost. The check runs after Step 4's
items 1–3 on the GREEN path, before the auto-advance check, and dispatches nothing.

### ADR-002: The skip is decided in `_cmd_boundary`, gated on a passing record
**Decided by:** agent. A helper `_light_skip(pipeline, current, root, slug, cwd) -> (nxt, skipped)`
runs where `nxt = next_stage(...)` is computed today: after the caps, the slug, the `blocked`
check and the judgment gate. Every existing halt keeps its precedence. When `skipped` is
non-empty it appends `stage_skipped`, then falls through to the existing narrow-end, pipeline-
complete, merge-gate and objective-gate branches with the new `nxt`. No new JSON key: `reason`
gets ` (lane light: skipped review, verify)`. Gating on the record, not on the lane alone, means a
forgotten, failed or skipped light check falls back to today's review path.

### ADR-003: One reader module, `light_lane.py`
**Decided by:** agent. `lane_of(base, slug, checkout=None)` reads `SPEC-<slug>.md` frontmatter
through `spec_machine`'s checkout and spec-dir resolution; `light_check_passed(...)` reads the
newest exact-name REVIEW record. The exact-name REVIEW lister moves from
`world_model_digest._reviews` into `light_lane.review_records`, and the digest calls it, so the
boundary and Maker list the same files. Imports stay lazy, so neither the boundary's nor the
digest's import graph grows at module load.

### ADR-004: Kept gates are read from their owners' text
**Decided by:** agent. The light check tells the model to run verify Checks 2, 4 and 6 from
`.claude/hm/verify-checks.md` (Codex: `.agents/skills/hm-verify/SKILL.md`), with "skip to Check 3"
read as "go to Check 4", and Check 4 preceded by `hm cli security-scan .`. Review Step 2's body
moves into `templates/stages/_partials/review_drift_gate.md.j2`, which review includes in place
(AC-011 pins the review render byte-identical) and the light check includes too. Mechanical
checks render from `config.reviewers.mechanical_checks` as review Phase 0 does.

### ADR-005: The record is REVIEW-shaped and written only on a clean pass (IRR-002)
**Decided by:** agent. Reusing review's file name and `drift_verdict` block leaves wrapup Step 3,
verify Check 1 and `wrapup_land`'s optional `REVIEW-{slug}-*.md` path unchanged. `status: PASSED`
plus `review_kind: light-check` keeps it from passing as a graded review. On every path that
writes no record, the check removes an earlier light-check record for this slug. A real review
is never removed.

### ADR-006: Text lives in `.claude/hm/execute-light-check.md` (IRR-003)
**Decided by:** agent. Same pattern as SPEC-hm-light-lane-s2b. Partial
`stages/_partials/execute_light_check.md.j2`; the Claude arm renders a skip line plus the shared
`ref_pointer` partial; the Codex arm includes the partial inline; `templates/hm/execute-light-check.md.j2`
renders it for `.claude/hm/`. Add `execute-light-check` to `synthesize._STAGE_REFERENCE_FILES`.
Full-lane runs carry about 600 characters (heading, skip line, pointer).

### ADR-007: `/hm:loop` and Cursor unchanged; Codex shares the boundary
**Decided by:** agent. The loop's stage list is explicit and Gate 0 catches a skipped review, so
the light check skips itself in loop mode and the loop keeps its listed stages. Cursor has no
auto-advance; it runs the same execute command and its banner already offers `/hm:wrapup`. Codex
calls the same boundary CLI, so it skips alike.

### ADR-008: Execute's gate and the registry
**Decided by:** agent. Execute's `summary_autopilot_gate` becomes: pending only when the Step 4.2
light check ran on `lane: light` and failed. Pending runs `gate-blocked`, so no boundary call and
no skip follow. The new heading is registered in `step_sensitivity.py` as INV, inherited from
verify Check 2 (`_u`).

## 📝 Implementation Plan

1. **Phase 1 — reader, ledger event, boundary skip.** depends_on: none · parallel_group: 1 ·
   merge_hazards: none · scope: `src/harness_maker/light_lane.py` (new), `autopilot_ledger.py`
   (`stage_skipped` in `LedgerEvent`), `autopilot_caps.py` (`_light_skip`, reason suffix),
   `world_model_digest.py` (use `light_lane.review_records`; light-check record → `wrapup`),
   `tests/unit/test_light_lane.py`, `tests/unit/test_autopilot_caps_light_lane.py`, the
   e7dd6648 boundary goldens under `tests/fixtures/light_lane_s3a/`, captured before any edit
   (AC-004) · exit: AC-001..006, 010, 012, 013 green; ruff, mypy --strict clean · risk: medium
   (boundary is load-bearing; AC-004 is the guard) · rollback: revert the phase.
2. **Phase 2 — templates.** depends_on: 1 · parallel_group: 2 · merge_hazards: goldens, size
   baseline · scope: `templates/stages/execute.md.j2` (Step 4.2, gate prose),
   `templates/stages/_partials/{execute_light_check,review_drift_gate}.md.j2` (new),
   `templates/stages/review.md.j2` (include the drift partial in place),
   `templates/hm/execute-light-check.md.j2` (new), `synthesize.py`, `step_sensitivity.py`,
   `tests/render/test_render_light_lane_s3a.py`, e7dd6648 render SHAs for AC-011 captured before
   the edit, re-captured execute snapshots and goldens with a dated note,
   `tests/structural/surface_baseline.json` + `work-docs/BASELINE-DELTA-hm-light-lane-s3a.md` if
   the aggregate ratchet requires, `CHANGELOG.md` · exit: AC-007..009, 011, 014 green;
   `uv run pytest tests -n auto` green except the known environment failures · risk: medium
   (golden churn) · rollback: revert the PR.

## 🚧 Contract Boundaries

### Do not change
- `src/harness_maker/templates/stages/wrapup.md.j2`, `templates/stages/_partials/wrapup_steps.md.j2` — wrapup stays byte-identical (AC-011).
- `src/harness_maker/templates/stages/verify.md.j2`, `templates/stages/_partials/verify_checks.md.j2` — verify stays byte-identical (AC-011).
- `src/harness_maker/templates/commands/hm/loop.md.j2` — the loop is unchanged (AC-011).
- `src/harness_maker/wrapup_land.py`, `src/harness_maker/spec_machine.py` approval and land-hold logic.
- `_HUMAN_GATED_STAGES` and `_JUDGMENT_GATED_STAGES` in `autopilot_caps.py`.
- The boundary JSON key set (AC-003 asserts it).

## 🧪 Testing Strategy

Before any edit, in a detached e7dd6648 worktree under the scratchpad: capture the boundary
JSON, ledger rows and marker for AC-004's input domain, and the render SHAs for AC-011. Write
the Phase 1 and Phase 2 tests against those goldens and this SPEC's tables (RED), then
implement (GREEN). No live model: the security scan's LLM pass is not exercised in tests.

## ⚠️ Risks & Mitigation

| Risk | Mitigation |
|---|---|
| The skip fires on a task nothing checked | gated on a PASSED record for this slug (ADR-002); AC-006 |
| The full-lane boundary drifts | AC-004 differential against e7dd6648 |
| A stale PASSED record outlives a later failed check | removed on every non-pass path (ADR-005); wrapup Step 2 re-runs the suite on a changed tree |
| Drift partial changes review's bytes | AC-011 SHA of the review render |
| `security-scan` is slow on a large repo | its fresh-scan cache; SPEC open question names the fallback (Check 4 alone) |
| Old render + new CLI | old execute writes no record, so no skip (fails closed) |

## ✅ Success Criteria

- [ ] AC-001 … AC-014 of SPEC-hm-light-lane-s3a pass.
- [ ] Full-lane boundary and typed review/verify/wrapup/loop renders byte-identical to e7dd6648.
- [ ] Re-run the stage 4 bench on light tasks and record `hm_cost_ratio_small` (follow-up).
