---
type: review
task_slug: hm-light-lane
status: in-progress
created: 2026-10-14
reviewers_invoked: [code-reviewer, security-reviewer, concurrency-reviewer, test-reviewer]
consensus_method: cross-check
run_id: e63c8d843621
review_base: bd3bd67b6efa97624339db85d1643bdf724f022e
drift_verdict:
  result: scope_violation
  scope_violations: [src/harness_maker/templates/stages/verify.md.j2, src/harness_maker/step_sensitivity.py]
  scenario_misses: []
  task_slug: hm-light-lane
  computed_at: 2026-10-14T12:40:00Z
---

# REVIEW — hm-light-lane (stage 1 of HM-LIGHT-LANE)

Run on the PR branch itself (no per-task worktree, so task-preflight was skipped; `<WT>` = repo root).
Lane: `full` (SPEC frontmatter). Preset: Production, two-pass. Diff: `review_base..HEAD`, snapshot
YAMLs and the autopilot golden excluded from the reviewer diff (regenerated outputs).

## 🎯 Round 1 Summary

Grade **B** (P0 0, P1 1 consensus-passed). 24 Pass 1 findings → 19 after Pass 2 → 21 with the two
main-loop findings (drift, intent). Coverage: all 7 lenses exercised, `blocks_approval: false`.
`human_review_needed: false`. The one P1 is the drift finding.

## 🔍 Drift Findings

- P1 `scope_violation`: `verify.md.j2` (light-lane coverage caveat) and `step_sensitivity.py`
  (A.5 source note) changed outside PLAN stage 1's scope line. Both follow from this stage; fix is
  to the PLAN.
- Intent (Step 3.3): P2 — HM-LIGHT-LANE's statement (`hm_cost_ratio_small` ≤ 5) is unmeasured
  here; stage 4 measures it.

## ✅ Consensus Findings (round 1)

Solo lens votes are `consensus-passed` (ADR-007).

| id | Sev | Lens | Tag | Disposition | Location | Summary |
|---|---|---|---|---|---|---|
| d40401e8 | P2 | functionality | consensus-passed | accepted | `src/harness_maker/templates/stages/review.md.j2:280` | Light-lane 'skip Pass 1' does not say which dispatch writes lens results |
| b7ac1169 | P2 | consistency | consensus-passed | accepted | `src/harness_maker/templates/stages/review.md.j2:739` | Round cap of 2 lives in a comment inside the gate; other readers uncapped |
| eb478518 | P2 | functionality | consensus-passed | accepted | `src/harness_maker/templates/stages/execute.md.j2:527` | A.5 skip ledger row lacks --terminal and reuses the failure sentinel |
| c1cfafc2 | P2 | design | consensus-passed | accepted | `src/harness_maker/templates/stages/spec.md.j2:65` | Lane is a one-time guess at spec time; execute/review never re-check it |
| 818940cd | P2 | functionality | consensus-passed | accepted | `src/harness_maker/templates/stages/spec.md.j2:124` | Light Round 1 offers Approve beside the questions it must collect |
| 2a6dc385 | P2 | consistency | consensus-passed | accepted | `src/harness_maker/spec_machine.py:1618` | weak re-derives SpecQualityResult.is_weak with a hardcoded 60 |
| 87ef88c1 | P3 | consistency | consensus-passed | accepted | `src/harness_maker/spec_machine.py:1623` | Failure payload lost indent=2, undeclared |
| a32cfd97 | P2 | design | consensus-passed | accepted | `src/harness_maker/synthesize.py:961` | Typed-only skills declared in the tuple AND hand-copied into each template |
| d7f44473 | P2 | consistency | consensus-passed | accepted | `src/harness_maker/step_sensitivity.py:123` | spec Step 0 still 'INV / mechanical skip heuristic' but holds an LLM lane call |
| 3fc4a318 | P2 | consistency | consensus-passed | accepted | `docs/reference/stage-rationale.md:5` | Moved rationale: non-specific headings, collapsed quotes, no pointer from template |
| 9eb661d5 | P2 | consistency | consensus-passed | accepted | `tests/render/test_render_light_lane.py:145` | AC-008/S6 claim seven typed-only commands; tests cover five |
| 64af0251 | P3 | consistency | consensus-passed | accepted | `src/harness_maker/templates/skills/context-linter/SKILL.md.j2:3` | Typed-only skills' descriptions still advertise automatic use |
| cb1fcf69 | P2 | security | consensus-passed | duplicate | `src/harness_maker/templates/stages/spec.md.j2:65` | Light lane is set once, from the ask, and nothing downstream rechecks it against the real diff or security surface |
| 8747a6ba | P2 | concurrency | consensus-passed | accepted | `src/harness_maker/templates/stages/review.md.j2:739` | Light cap of 2 makes the no-reap CHANGES_REQUESTED exits common; base ref leaks |
| d3646ef3 | P2 | tests | consensus-passed | accepted | `tests/unit/test_spec_machine_check_all.py:136` | Compact-output test never exercises the weak_dimensions branch or the 60 boundary; assertions conditional |
| 9d18c71c | P2 | tests | consensus-passed | accepted | `tests/render/test_render_light_lane.py:59` | Step 0 assertions 'irreversible'/'Refinement Decisions' pre-exist in the skip paragraph; lane thresholds unpinned |
| e9a15dcd | P2 | tests | consensus-passed | duplicate | `tests/render/test_render_light_lane.py:145` | Seven typed-only commands claimed, five tested; plan missing from visible list |
| b7d52941 | P2 | tests | consensus-passed | accepted | `tests/render/test_render_light_lane.py:186` | Codex test checks only the constant, not the rendered openai.yaml policy |
| 0233b4aa | P2 | tests | consensus-passed | accepted | `tests/render/test_render_light_lane.py:81` | S2's dispatch-skipped ledger row is not asserted |
| 79fe8403 | P1 | functionality | consensus-passed | accepted | `work-docs/PLAN-hm-light-lane.md:61` | Drift: verify.md.j2 and step_sensitivity.py changed outside stage 1's PLAN scope |
| 51ca5d8b | P2 | functionality | consensus-passed | accepted | `work-docs/PLAN-hm-light-lane.md:96` | HM-LIGHT-LANE: statement (hm_cost_ratio_small ≤ 5) is not met or measured by this stage |

Pass 2 dropped: design P2 "anti-anchoring trade undocumented" (absorbed); concurrency P2
"close-then-reap race" (narrow window, inference only); security P2 "Pass 1 drop on security
diffs" (same root cause as the kept lane-recheck finding); security P3 description drift (no
security impact, covered by consistency); tests P3 "substring frontmatter check". Pass 2
downgraded core P1 "which dispatch writes lens results" → P2 (Round 1 files already exist, so it
cannot block approval; the risk is cost).

## ⚠️ Weak Consensus

None.

## 📝 Manual-Only Findings

None.

## 🤝 Disagreements

Security lens rated the one-time lane call P1 in Pass 1 and P2 in Pass 2; core rated it P2. Same
tier after Pass 2; recorded as one finding plus a duplicate.

## 🧊 Cross-model findings (frozen @ round 1)

- codex: `status: skipped`, reason `CLI not installed: codex`. No findings. No re-invocation in
  later rounds.
