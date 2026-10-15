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
adrs: 9
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

### ADR-002: The skip is decided at execute's boundary, gated on a record Python can check
**Decided by:** agent (spec-validator findings 1 and 10). A helper
`_light_skip(pipeline, root, slug, since) -> (nxt, skipped)` runs only when `--current execute`,
where `nxt = next_stage(...)` is computed today: after the caps, the slug, the `blocked` check and
the judgment gate. Every existing halt keeps its precedence, and every other stage is
byte-identical (AC-004). When `skipped` is non-empty it appends `stage_skipped`, then falls through
to the existing narrow-end, pipeline-complete, merge-gate and objective-gate branches with the new
`nxt`. No new JSON key: `reason` gets ` (lane light: skipped review, verify)`. `since` is
`marker.created_at`.

### ADR-003: One reader module, `light_lane.py`
**Decided by:** agent (findings 1, 2, 4, 5). `lane_of(base, slug, checkout=None)` is `light` only
when the frontmatter says exactly `light` and `approval_state(...)` is `approved` or `exempt` with
no irreversible ids. `light_check_passed(base, slug, checkout=None, *, since=None)` resolves the
checkout as `approval_state` does (`spec_machine._resolve_checkout`) and requires: a trusted light
lane; no real REVIEW for the slug; a newest light-check record `PASSED` for this slug;
`drift_verdict.computed_at >= since` when `since` is given (unparseable → false); and
`verification_cache.is_fresh(compute_relevant_skip_key(checkout))`. Work-docs edits are outside
that key (`work-docs/**` is irrelevant), so writing the record does not stale it. The exact-name
REVIEW lister moves from `world_model_digest._reviews` into `light_lane.review_records`, and the
digest calls it. The digest reads no marker, so it passes no `since`. Imports stay lazy.

### ADR-004: Kept gates are shared partials
**Decided by:** agent (findings 3, 6, 7). Verify's Check 2, Check 4 and Check 6 sections move into
`templates/stages/_partials/verify_check_{2,4,6}.md.j2`, included by `verify_checks.md.j2` in place
(verify renders byte-identical, AC-011) and by the light check. The light check reads Check 2's
"Skip to Check 3" as "go on", and runs `hm cli security-scan {{ WTR }} --force` before Check 4,
telling it to read `{{ WTR }}/.claude/observability/security/` (`_persist` writes under the scan
target). Review Step 2 splits into `review_drift_scan.md.j2` (the two bullets) and
`review_drift_verdict.md.j2` (the `drift_verdict` block and its closing paragraph). The sentence
"Drift findings get severity `P1` … reviewers still run on the actual diff." stays in
`review.md.j2` between the two includes. Mechanical checks render from
`config.reviewers.mechanical_checks` as review Phase 0 does. `cli.security_scan_cmd` gains
`--force` → `scan_all(force=True)` (IRR-004).

### ADR-005: The record is REVIEW-shaped and written only on a clean pass (IRR-002)
**Decided by:** agent (findings 4, 5, 8, 9). Reusing review's file name and `drift_verdict` block
leaves wrapup Step 3, verify Check 1 and `wrapup_land`'s optional `REVIEW-{slug}-*.md` path
unchanged. `status: PASSED` plus `review_kind: light-check` keeps it from passing as a graded
review (status name kept by the coordinator, 2026-10-15). It is written to
`{{ WTR }}/{{ config.work_docs.dir }}`, only when every check passes (Check 6 `WARN` allowed) and
drift is clean, and never over a real review under today's name. Any non-pass writes nothing and
says review runs next: no repair round, no deletion. Stale records are rejected in Python (ADR-003).
The skip condition opens with `hm spec_machine approval-status` so the check never runs where
the boundary will not trust the lane. The diff-size skip is review's own "well over five files"
rule.

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

### ADR-008: Execute's gate is unchanged; the registry gains the new headings
**Decided by:** agent (finding 9). A non-pass writes no record, so the boundary routes to review
by itself. Execute's `summary_autopilot_gate` stays "No mandatory gate". The new headings are
registered in `step_sensitivity.py` as INV, inherited from verify Check 2 (`_u`): Step 4.2 in the
Claude command, and Step 4.2 plus the included Check 2/4/6 headings in the Codex execute skill.

### ADR-009: A light SPEC with no irreversible decisions is stamped exempt
**Decided by:** DRI, 2026-10-15 ("Approve + exempt light" on the decision card; SPEC AC-014). Spec Step 5 stamps a `lane: light` SPEC with
`irreversible_decisions: []` using Step 0's `approve --exempt` command when the DRI did not
approve it, so `lane_of` trusts it on unattended `auto_full` runs. `spec_machine.approve` refuses
`--exempt` on a non-empty list (a stamp `approval_state` would read as `invalid` anyway). It lives
in its own amendment commit plus the Step 5 sentence and its two tests, so it can still revert alone.

## 📝 Implementation Plan

1. **Phase 1 — reader, ledger event, boundary skip.** depends_on: none · parallel_group: 1 ·
   merge_hazards: none · scope: `src/harness_maker/light_lane.py` (new), `autopilot_ledger.py`
   (`stage_skipped` in `LedgerEvent`), `autopilot_caps.py` (`_light_skip`, reason suffix),
   `world_model_digest.py` (use `light_lane.review_records`; `light_check_passed` → `wrapup`),
   `cli.py` (`security-scan --force`), `spec_machine.approve` (refuse `--exempt` on a non-empty
   list, ADR-009), `tests/unit/test_spec_approve_exempt.py`, `tests/unit/test_light_lane.py`,
   `tests/unit/test_autopilot_caps_light_lane.py`, `tests/unit/test_cli_security_scan_force.py`,
   the e7dd6648 boundary and digest goldens under `tests/fixtures/light_lane_s3a/`, captured
   before any edit (AC-004, AC-012) · exit: AC-001..006, 010, 012, 013, AC-014's CLI test and AC-008's CLI test
   green; ruff, mypy --strict clean · risk: medium (boundary is load-bearing; AC-004 is the
   guard) · rollback: revert the phase.
2. **Phase 2 — templates.** depends_on: 1 · parallel_group: 2 · merge_hazards: goldens, size
   baseline · scope: `templates/stages/execute.md.j2` (Step 4.2 pointer / Codex inline),
   `templates/stages/_partials/{execute_light_check,review_drift_scan,review_drift_verdict,verify_check_2,verify_check_4,verify_check_6}.md.j2`
   (new), `templates/stages/review.md.j2` and `templates/stages/_partials/verify_checks.md.j2`
   (include the partials in place, byte-identical render),
   `templates/hm/execute-light-check.md.j2` (new), `templates/stages/spec.md.j2` (Step 5's exempt
   stamp on light, ADR-009), `synthesize.py`, `step_sensitivity.py`,
   `tests/render/test_render_light_lane_s3a.py`, e7dd6648 render SHAs for AC-011 captured before
   the edit, re-captured execute snapshots and goldens with a dated note,
   `tests/structural/surface_baseline.json` + `work-docs/BASELINE-DELTA-hm-light-lane-s3a.md` if
   the aggregate ratchet requires, `CHANGELOG.md` · exit: AC-007..009, 011 and 014 green;
   `uv run pytest tests -n auto` green except the known environment failures · risk: medium
   (golden churn) · rollback: revert the PR.

## 🚧 Contract Boundaries

### Do not change
- `src/harness_maker/templates/stages/wrapup.md.j2`, `templates/stages/_partials/wrapup_steps.md.j2` — wrapup stays byte-identical (AC-011).
- Verify's rendered output: `verify.md.j2` and `_partials/verify_checks.md.j2` may change only to include the Check 2/4/6 partials, and verify must render byte-identical (AC-011).
- Review's rendered output: `review.md.j2` may change only to include the drift partials, and review must render byte-identical (AC-011).
- `src/harness_maker/templates/commands/hm/loop.md.j2` — the loop is unchanged (AC-011).
- `src/harness_maker/wrapup_land.py`, `src/harness_maker/spec_machine.py` approval-state and land-hold logic. The one exception is ADR-009: `approve(exempt=True)` refuses a non-empty irreversible list.
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
| The skip fires on a task nothing checked | gated on a PASSED record for this slug on a trusted lane (ADR-002/003); AC-006 |
| The full-lane boundary drifts | AC-004 differential against e7dd6648 |
| A stale PASSED record outlives a later change | Python requires a fresh verification cache and `computed_at` ≥ marker (ADR-003); AC-006 |
| Partials change review's or verify's bytes | AC-011 SHA of both renders |
| At `auto_full` an interviewed light SPEC is unapproved, so no skip | ADR-009 stamps it exempt when its irreversible list is empty (decided by the DRI 2026-10-15) |
| Forced `security-scan` is slow on a large repo | unmeasured; SPEC open question names the fallback (Check 4 alone) |
| Old render + new CLI | old execute writes no record, so no skip (fails closed) |

## ✅ Success Criteria

- [ ] AC-001 … AC-013 of SPEC-hm-light-lane-s3a pass.
- [ ] Full-lane boundary and typed review/verify/wrapup/loop renders byte-identical to e7dd6648.
- [ ] Re-run the stage 4 bench on light tasks and record `hm_cost_ratio_small` (follow-up).
