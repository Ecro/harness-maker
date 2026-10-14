---
type: review
task_slug: hm-light-lane
status: APPROVED
created: 2026-10-14
reviewers_invoked: [code-reviewer, security-reviewer, concurrency-reviewer, test-reviewer]
consensus_method: cross-check
run_id: e63c8d843621
review_base: bd3bd67b6efa97624339db85d1643bdf724f022e
drift_verdict:
  result: clean
  scope_violations: []   # round 1 found verify.md.j2 and step_sensitivity.py; round 2 added both to the PLAN scope
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

### Iteration 2 (Grade: B → A)
Fixes applied: 19 (the P1 drift fix, plus the accepted P2/P3 findings, applied in the same round
as an operator sweep so the re-review and the confirmation pass would cover them; P2s are not in
the auto-fix queue by rule)

| # | Severity | Summary | File | Status |
|---|---|---|---|---|
| 1 | P1 | PLAN stage 1 scope lists verify.md.j2, step_sensitivity.py | PLAN | Applied · caused_by=none |
| 2–19 | P2/P3 | every round-1 finding except the two below | see round-1 table | Applied · caused_by=none |

Carried (accepted, not fixed here): `a32cfd97` derive skills' typed-only flag from
`_TYPED_ONLY_SKILLS` (PLAN stage 2); `51ca5d8b` the intent's cost ratio (stage 4).

Re-review: one `code-reviewer` (functionality) over the round-2 hunks, churn 0.675 ≥ 0.3. It
confirmed 19 resolved, 0 new defects; it flagged the missing template pointers to
`stage-rationale.md`, added as Jinja comments (render nothing).
Remaining: 2 (carried) | New issues introduced: 0
Churn: 0.675 (max: docs/reference/stage-rationale.md, measured 17, excluded 0)

## Confirmation Pass (confirm-1)

Frozen `bd3bd67..51eeb88`, all 7 lenses in 4 dispatches, coverage complete. **Zero new P0/P1** →
APPROVED. Ref reaped, run closed `APPROVED`, ledger row written.

New P2/P3 from the pass (applied after it as a post-review sweep, **not re-reviewed**; tests and
goldens re-run):

| Sev | Lens | Finding | Done |
|---|---|---|---|
| P2 | concurrency | C3 closed the run before reaping, contrary to the new reap-first rule | C3 now reaps, then closes |
| P2 | consistency | AC-006/AC-007 predicates drifted from the rendered text and the test | predicates updated |
| P2 | robustness | an unrecognised `lane` value had no reading | any value but exactly `light` is `full` (execute, review) |
| P2 | design | the approver never sees the lane | the light closing question shows the lane |
| P2 | consistency | registry silent on the light overrides of TUNE review knobs | notes on Step 4e and Step C1 |
| P2 | tests | no failed-gate + clean-score case | `test_a_failed_gate_never_collapses_even_with_a_clean_score` |
| P2 | tests | lane re-check clauses unasserted | asserted in execute and review tests |
| P3 | tests | AC-007 predicate vs test | covered by the predicate fix |
| P3 | tests | Codex policy test checks paths, not "exactly" | not done; low risk |

## 🔁 Oscillation

None.

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|---|---|---|---|---|
| 1 (init) | B | — | 21 | — |
| 2 | A | 19 | 2 | 0 |

Final grade: A
Iterations used: 2 / 3
Exit reason: converged
Status: APPROVED
human_review_needed: false
Counters (see §5): unreviewed 0 · prior-fix 0 · unattributed 0

Not part of the verdict: the SPEC's DRI approval is still `missing`
(`hm spec_machine approval-status`), so `/hm:wrapup` would ask for it. Locally,
`test_real_on_disk_rows_still_validate` globs `review-*.jsonl` and trips on the
`review-complexity.jsonl` that step 5c writes; this only shows once 5c has run in this repo, and
stage 2 removes 5c.
