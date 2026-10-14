---
type: plan
task_slug: hm-light-lane
status: planning
created: 2026-10-14
tags: [harness-maker, plan, python, jinja2, cost, context-carry]
spec: "[[SPEC-hm-light-lane]]"
research_doc: "[[RESEARCH-hm-light-lane]]"
interview_rounds: 0
adrs: 5
validator_outcome: NOT_RUN
summary: "HM-LIGHT-LANE in four stages: lane + levers 4/5, body slimming, stage delegation, bench"
intent: HM-LIGHT-LANE
---

# PLAN — hm-light-lane

## 🎯 Executive Summary

Intent HM-LIGHT-LANE moves `hm_cost_ratio_small` from 22 to ≤ 5 without lowering hidden-test pass
rate. About 75% of the cost is main-context carry, so the plan attacks carry, not only steps. It is
delivered in four stages, one PR each; this PLAN stays `planning` until stage 4 measures.

## 📚 Prior Work

- `work-docs/RESEARCH-hm-light-lane.md` — the bench, the ×22, the A.5 self-blocks.
- Research thread token-lever analysis (2026-10-14): stage bodies 60.5% of carry, heredoc tool
  inputs 16.4%, Bash output 10.3%, subagent notifications and results 11.2%.
- `PLAN-economics-attribution-and-carry` ADR-011: `delegation.stages` and `stage-delegate`
  already exist for wrapup and verify, default off pending a soak.

## 📐 Architecture Decision Records

### ADR-001: The lane lives in SPEC frontmatter; missing means full
**Decided by:** agent. One field read by execute and review; no new harness.yaml key; every
existing SPEC keeps the full pipeline.

### ADR-002: The light lane removes A.5 only from execute
**Decided by:** agent (source: intent Constraints). A.4 is one test run and registered INV; the
draft listed it but removing it saves nothing measurable.

### ADR-003: Review keeps every lens on the light lane
**Decided by:** user (source: research thread, "리뷰 렌즈 자체는 싸서 남겨도 됩니다", accepted with
the five-lever scope). The cut is repetition: Pass 1, rounds beyond 2, an unchanged confirmation.

### ADR-004: Lever 1 applies to light execute and verify only
**Decided by:** agent. A subagent cannot dispatch subagents, so review (lens dispatch) and full
execute (A.5, stuck) must stay in the main loop; spec stays for the interview.

### ADR-005: Moved rationale goes to `docs/reference/stage-rationale.md`
**Decided by:** agent. Keeps the aggregate surface ratchet at no growth without a surface
allowance, and starts lever 2 with text that changes nothing at run time.

## 🏗️ Technical Design

Stage templates in `src/harness_maker/templates/stages/`; `spec_machine._run_check_all`;
`synthesize._TYPED_ONLY_SKILLS`, `_TYPED_ONLY_COMMANDS`, `_command_frontmatter`.

## 📝 Implementation Plan

1. **Stage 1 — lane, lever 4, lever 5** (this PR). depends_on: none · parallel_group: 1 ·
   merge_hazards: goldens · scope: spec/execute/review templates, spec_machine.py, synthesize.py,
   five skill templates, tests · exit: `uv run pytest tests -n auto` green except the 7
   pre-existing environment failures · risk: low · rollback: revert the PR.
2. **Stage 2 — lever 2, body slimming.** depends_on: 1 · scope: review.md.j2, execute.md.j2 into
   on-demand reference files for full-lane-only and rare paths. User-approved additions
   (decision cards, 2026-10-14, from `harness-research/ab/2026-10-14-phase-pruning.md`): render
   loop-only branches (Gate 0 receipt, execute Step 0.2 and Step 5, verify Check 5) only when
   `loop.enabled`; state the Auto-advance procedure once and keep each stage's own gate check;
   delete review Step 2.5 and step 5c with its Size table; shrink execute Phase C.0 and D.5 to
   2–3 lines. spec-validator stays on the light lane (user, same date) · exit: size ratchet re-frozen
   lower with BASELINE-DELTA · risk: medium (instruction preservation) · rollback: revert.
3. **Stage 3 — levers 1 and 3.** depends_on: 1 · scope: light execute and verify through
   `stage-delegate`; lens results carried as verdict + path · exit: render tests · risk: medium ·
   rollback: revert.
4. **Stage 4 — bench runner and re-measure.** depends_on: 1–3 · scope: fixtures, hidden tests,
   plain/hm arms under `scripts/` or `tests/bench/` · exit: `hm intent metric record
   hm_cost_ratio_small` · risk: low · rollback: n/a.

## 🚧 Contract Boundaries

### Do not change
- `src/harness_maker/lens_coverage.py` — the coverage verdict stays the sole producer.
- Advisory: the full lane's gates, rounds and dispatches are unchanged.

## 🧪 Testing Strategy

Render tests in `tests/render/test_render_light_lane.py`, unit test for the compact check line,
re-captured goldens (`autopilot_gate_golden.json`, synth snapshots) with their docstring entries.

## ⚠️ Risks & Mitigation

| Risk | Mitigation |
|---|---|
| Step 0 sends a large task down the light lane | logged reason in Refinement Decisions; falsifier in the intent |
| Hidden skill was needed by a path we missed | the visible set is pinned by tests; classification recorded in the PR |
| Steps removed do not move the cost enough | stages 2–3 attack carry; stage 4 measures |

## ✅ Success Criteria

- [ ] AC-001 … AC-008 of SPEC-hm-light-lane pass.
- [ ] Aggregate shipped surface does not grow.
- [ ] `hm_cost_ratio_small` measured after stage 4.
