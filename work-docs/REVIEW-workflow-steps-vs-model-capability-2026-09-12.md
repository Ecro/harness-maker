---
type: review
task_slug: workflow-steps-vs-model-capability
status: APPROVED
created: 2026-09-12
reviewers_invoked: [code-reviewer(design,functionality,robustness,consistency), security-reviewer, concurrency-reviewer, test-reviewer, codex(skipped)]
consensus_method: cross-check
run_id: a018216f139a
review_base: b778e52415edf3a47d45c6166e4656b4dcba2260
drift_verdict:
  result: scope_violation
  scope_violations: [tests/unit/test_schema_migration.py, tests/snapshot/*.expected.yaml, tests/structural/autopilot_gate_golden.json, .claude/observability/mutation-receipts.jsonl (base)]
  scenario_misses: []
  task_slug: workflow-steps-vs-model-capability
  computed_at: 2026-09-12T06:46:05+00:00
---

# REVIEW — workflow-steps-vs-model-capability

## 🎯 Round 1 Summary

**Grade C** (P0 0 · P1 4 · P2 6 · P3 1, all `consensus-passed`; 2 duplicates). Lens coverage 7/7
(`blocks_approval: false`). Cross-model: codex **skipped** (CLI usage limit until 2026-09-15 16:51).
Threshold A not met → auto-fix loop round 2 on the four P1s. `human_review_needed: false` (no
manual-only / weak-consensus severe findings).

## 🔍 Drift Findings (P1, informational)

- **Scope drift** — `tests/unit/test_schema_migration.py` (consumer test pinning the deleted
  ceremony, rewritten to pin the surviving cap sentence — pre-change checklist item 2),
  `tests/snapshot/*.expected.yaml` ×8 (regenerated in-worktree, consequence of the template edits),
  `tests/structural/autopilot_gate_golden.json` (re-based with an attributed `rebases` row),
  `.claude/observability/mutation-receipts.jsonl` on **base** (receipt files at base by design —
  wrapup must commit it before `task-land`). All four are recorded in the PLAN's execution notes.
- **Incomplete phase** — Phase 7 (post-land re-freeze) is pending by design (ADR-006), not drift.

## ✅ Consensus Findings

| id | sev | lens | location | summary | disposition | voices |
|---|---|---|---|---|---|---|
| `c83ee64c4498cee8` | P1 | consistency | `src/harness_maker/step_sensitivity.py:300` | review Step 4e classed INV while CLAUDE.md and its own note call the auto-fix cap TUNE; grep TUNE workflow never surfaces it | accepted | consistency, functionality |
| `24606b32ae0a9d7d` | P2 | consistency | `src/harness_maker/step_sensitivity.py:12` | Census docstring per-stage totals exclude renders_when entries while the total adds them back; review has 19 entries not 16 | accepted | consistency |
| `f621e6bb9b33e36f` | P1 | design | `src/harness_maker/step_sensitivity.py:226` | review Step 1 entry attributes reviewer-set selection to knob reviewers.enabled, which CLAUDE.md states has zero effect on dispatch (lens_dispatch(preset) never reads it) | accepted | design, functionality |
| `a22d612ca4f76fb7` | P2 | design | `src/harness_maker/step_sensitivity.py:1276` | 4-variant Ordering DSL + importlib knob resolution built for 7 comparisons, two orderings used once each — speculative generality vs CLAUDE.md 제1목표 | accepted | design |
| `861c3214519d196f` | P1 | functionality | `src/harness_maker/step_sensitivity.py:226` | review Step 1 entry attributes routing to reviewers.enabled, which per CLAUDE.md does not gate dispatch (routable_lenses(preset)/conditional_router do) | duplicate | design, functionality |
| `9436b77ddd328a0a` | P1 | functionality | `src/harness_maker/step_sensitivity.py:300` | review Step 4e classified INV while its own note says the governed value (auto-fix round cap) is TUNE and reverses per model — the grep-TUNE re-measurement workflow never surfaces it | duplicate | consistency, functionality |
| `4b4d9393c7c3e81c` | P1 | robustness | `src/harness_maker/step_sensitivity.py:286` | S3 knob reviewers.consensus is documented dead config (interview.py: neither value is read by any code path or stage template), not a real ordering guard | accepted | robustness |
| `610e4804e98cae36` | P2 | robustness | `work-docs/PLAN-workflow-steps-vs-model-capability.md:384` | Phase 7 post-land baseline re-freeze is unenforced prose; the same post-land step from a prior PLAN already silently failed (frozen baseline is behind main) | accepted | robustness |
| `3f102cec00dd6030` | P2 | robustness | `src/harness_maker/step_sensitivity.py:330` | _rank() raises a bare KeyError if a le-ordered string value is not in _CONSENSUS_RANK | accepted | robustness |
| `3ddaf706cdd08c2a` | P1 | security | `src/harness_maker/templates/stages/verify.md.j2:48` | Verify Check 1 drops the only per-scenario SPEC coverage gate; the replacement prose claims duplication by review Step 2 / wrapup Step 3, neither of which checks scenario coverage | accepted | security |
| `d2bdf88a2cf23eba` | P2 | tests | `tests/unit/test_render_inequality_gate_removed.py:24` | CAP_SENTENCE golden checks only a phrase fragment; the rendered cap value/locale is unverified for spec/plan/loop | accepted | tests |
| `cc6229e5ec067a25` | P2 | tests | `tests/structural/test_step_sensitivity_registry.py:104` | test_extractor_matches_headings_helper compares counts, not extracted ordinal values | accepted | tests |
| `f602732f489dc713` | P3 | tests | `tests/structural/test_step_sensitivity_registry.py:60` | test_arms_is_preset_times_dev_mode recomputes the production expression — tautological | accepted | tests |

## ⚠️ Weak Consensus

(none)

## 📝 Manual-Only Findings

(none)

## 🤝 Disagreements

(none — the two clusters (`f621e6bb…`/`861c3214…` Step 1 knob; `c83ee64c…`/`9436b77d…` Step 4e
class) agree on tier and CONCLUDE.)

## 🧊 Cross-model findings (frozen @ round 1)

| model | status | reason | findings |
|---|---|---|---|
| codex | skipped | exit 1 — CLI usage limit (retry after 2026-09-15 16:51) | 0 |

No cross-model findings; nothing to adjudicate at Step 3.6/3.7. Rounds 2..N re-read this section.

## Round records

### Iteration 1 (initial)
Findings: 13 (P1 4 · P2 6 · P3 1); dispositions accepted 11 · duplicate 2.

### Iteration 2 (Grade: C → A)
Fixes applied: 4 (P1) + 1 incidental (P2)
| # | Severity | Summary | File | Status |
|---|----------|---------|------|--------|
| 1 | P1 | review Step 4e INV→TUNE (+remeasure_on, measure_cmd=harness-bench) — `c83ee64c` (+dup `9436b77d`) | src/harness_maker/step_sensitivity.py | Applied · caused_by=none |
| 2 | P1 | review Step 1 knob `reviewers.enabled` dropped (routing is preset-derived) — `f621e6bb` (+dup `861c3214`) | src/harness_maker/step_sensitivity.py | Applied · caused_by=none |
| 3 | P1 | review Step 4 knob `reviewers.consensus` dropped (display-only field); `_CONSENSUS_RANK` removed, `_rank` str → ValueError — `4b4d9393` (also resolves P2 `3f102cec`) | src/harness_maker/step_sensitivity.py | Applied · caused_by=none |
| 4 | P1 | verify Check 1 note rewritten: names execute Phase A.5 / wrapup Step 3.5 as the coverage enforcement points, documents the `--no-tdd` limit — `3ddaf706` | src/harness_maker/templates/stages/verify.md.j2 | Applied · caused_by=none |

Verify build: targeted set GREEN (registry, verify render ×3, instruction preservation, snapshot regen, schema migration, ratchet ×3, mutation-receipt gate); autopilot golden re-based (verify bytes moved again; `rebases` row re-measured: −8 674 / −8 730 / −8 686 / −8 686); DELTA doc re-measured (−8 674 both variants).
Remaining: 6 (P2 5 · P3 1, all `accepted`, pending — outside the fix queue at grade A) | New issues introduced: 0
Churn: 0.048 (max: src/harness_maker/step_sensitivity.py, measured 3, excluded 0) — rereview: skipped — churn 0.05 < 0.30
Lifecycle transitions this round: 7 × pending→resolved (progress: yes).

## Confirmation pass confirm-1 (frozen @ 07d60579, span b778e524..07d60579)
Lens coverage 7/7. New consensus-passed severe findings: **6 P1** (each a solo lens vote) → one
repair round (separately budgeted; `iteration_count` unchanged), then confirm-2.

| lens | sev | location | finding | disposition |
|---|---|---|---|---|
| security | P1 | verify.md.j2:54 | `--no-tdd` coverage gap disclosed but not mechanically closed | accepted → fixed: note now names wrapup Step 3.5 `find-unbound` (fail-closed) as the spec-driven backstop; task-driven has no machine SPEC (stated) |
| design | P1 | verify.md.j2:343 | Procedure steps 2/4 still "emit … JSON record" for the retired ledger (51b5bbfb leftover) | accepted → fixed |
| functionality | P1 | verify.md.j2:230 | stale `PLAN/SPEC satisfaction` label in both worked-example outputs | accepted → fixed; REMOVED golden broadened to the bare phrase |
| functionality | P1 | verify.md.j2:297 / wrapup_receipt.py:402 | Step 0.5 delegate contract still requires `record_path` for the retired JSONL (51b5bbfb leftover) | accepted → fixed: template + `verify-record-missing`-on-absent check dropped (claimed-but-missing still checked) |
| consistency | P1 | step_sensitivity.py:55 | `_LEDGER` measure_cmd uses `--root .`, not a flag of `verifier_discrimination report` | accepted → fixed (`--ledger …`) |
| concurrency | P1 | io_utils.py:88 | `atomic_append` lacks PIPE_BUF guard + short-write loop (51b5bbfb routed multi-session writes through it) | accepted → fixed + 2 unit tests |
| robustness | P1 | readiness.py:540 | ls-files failure inside a checkout reported as "not a git checkout" | accepted → fixed (`GitProbeError`, truthful N/A evidence) |
| tests | P2 | verify.md.j2:230 | REMOVED golden too narrow | accepted → fixed with the functionality P1 |
| design | P2 | CLAUDE.md:271 | ordering check covers any knob-bearing entry, not only COMP/TUNE | accepted → fixed |
| consistency | P2 | RESEARCH:152 | TUNE tally 6 vs shipped 7 | accepted → fixed (pointer note) |
| robustness | P2 | readiness.py:542 | two 30 s git calls per health run | accepted, pending (not in fix queue) |

Repair verification: ruff/mypy clean; delegation prose bound (+60) restored by trimming Step 0.5;
snapshots regenerated; golden re-based (−8 561/−8 661/−8 573/−8 573); DELTA re-measured (−8 561).
Three of the P1s sit in code landed by base commit 51b5bbfb (inside the review span, not this
task's PLAN scope) — recorded as scope drift in the drift verdict and in the PLAN execution notes.

## Confirmation pass confirm-2 (frozen @ 5b8dbe25, span b778e524..5b8dbe25)
Lens coverage 7/7 (`blocks_approval: false`). **Dirty: 3 new consensus-passed P1** — no third pass
is dispatched; per C3 the review ends **CHANGES_REQUESTED**, `human_review_needed: true`.

| lens | sev | location | finding | remedy for the next round |
|---|---|---|---|---|
| design | P1 | step_sensitivity.py:55 | `_LEDGER` measure_cmd names `verifier_discrimination report`, which measures second-opinion loss — not plan-validator verdict change / A.5 FAIL / confirmation-pass rates (5 of 8 TUNE entries) | point those entries at a stage-agent aggregation (`verifier_discrimination.agent_rounds` exists as a function but has no CLI verb — either add `hm verifier_discrimination agent-rounds --root .` or record the measurement as a documented one-liner) |
| concurrency | P1 | io_utils.py:118 | the repair-round short-write retry loop reopens the interleave race that `append_atomic_line` (same file) documents as "Do NOT loop" — a fix-introduced defect, `caused_by` = confirm-1 repair Fix #6 | drop the loop: raise `OSError` on a short write, mirroring `append_atomic_line`; keep the PIPE_BUF guard |
| security | P1 | verify.md.j2:55 | the Check 1 `--no-tdd` note says wrapup's `find-unbound` gate is fail-closed, but that is Production-only; Side is advisory (`wrapup.md.j2:286-289`) — `caused_by` = confirm-1 repair Fix #1 | gate the sentence on `config.preset == 'Production'` and state the Side advisory-only behaviour |
| tests | P2 | wrapup_receipt.py:420 / readiness.py:429 / io_utils.py:118 | the record_path relaxation, the `GitProbeError` branch and the retry loop have no direct tests | add the three tests (the loop test becomes moot once the loop is removed) |
| security | P2 | intent_miss.py:91 | `atomic_append`'s new `ValueError` breaks `record_intent_miss`'s no-raise contract | catch `(OSError, ValueError)` as `delegation_ledger` does |
| robustness | P2 | render.py:1996 · readiness.py:1364 | the new `ValueError` can abort a whole render on an oversized manifest line; remediation command does not quote paths | guard the manifest append; `shlex.quote` the paths |
| design | P2 | readiness.py:1325 | try/except/else + trailing `if` is harder to follow than one linear branch | collapse |
| security/robustness | P3 | reconcile.py:649 · cli.py:2404 | unguarded `atomic_append` callers | catch `(OSError, ValueError)` |

**Root cause of the dirty pass (for the next reader):** the confirm-1 repair round ported
`review_telemetry`'s retry loop into `io_utils.atomic_append` without noticing the same file
already held a contrary, better-reasoned sibling (`append_atomic_line`); and the `--no-tdd`
disclosure was written from `wrapup.md.j2`'s Production branch alone. Both are one-line fixes,
but this `/hm:review` has no repair budget left (one repair round per confirmation, ADR).

## 🔁 Oscillation
(none — `review_churn oscillation --rounds 2` returned no rows)

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | C     | —             | 13 (P1 4 · P2 6 · P3 1; dup 2) | — |
| 2         | A     | 4 (+1 incidental P2) | 6 (P2 5 · P3 1) | 0 |
| confirm-1 | — (observation) | — | — | 6 P1 · 4 P2 → repair round (7 fixes) |
| confirm-2 | — (observation) | — | — | **3 P1** · 6 P2 · 2 P3 |

Final grade: A on the voting set at round 2; **confirmation pass dirty** → Status CHANGES_REQUESTED
Iterations used: 2 / 3 (plus one separately-budgeted repair round)
Exit reason: converged (grade), then confirm-2 dirty (risk-closure not reached)

## 📏 Size & Complexity

| File | LOC | Cyclomatic | Max nesting | Status |
|------|-----|------------|-------------|--------|
| src/harness_maker/step_sensitivity.py | 517 → 521 | null → null | null → null | measured (round 2: `complexity_status` from 5c — Python file; see CHURN-r2 payload) |
| src/harness_maker/templates/stages/verify.md.j2 | 378 → 383 | null | null | not-python |
| work-docs/MATRIX-native-redundancy.md | 261 → 261 | null | null | not-python |

(Round-2 5c payload; the repair round was not separately measured — its churn is in the confirm
diff. Report only; no threshold.)

Status: CHANGES_REQUESTED
human_review_needed: true
Counters (see §5): unreviewed 0 · prior-fix 2 · unattributed 0
Full unit+structural suite after the repair round: **rc=0** (`tests/integration`, `tests/e2e` ignored; the two failures that also fail on base — `test_the_wrapup_git_tail_is_three_calls`, `test_ac_006_a_live_review_overlaps_the_fan_out` — deselected).


---

# Run 2 — `e06a3b304e71` (after the three P1 fixes; review_base b778e524)

## 🎯 Round 1 Summary
**Grade C** (P0 0 · P1 5 · P2 7; 3 duplicates; 1 cross-model `manual-only`). Lens coverage 7/7.
Cross-model: codex **invoked**, 1 finding, PIDA **accepted** (no oracle — toolchains declare no
per-path command; the diff settled it). Threshold A not met → auto-fix round 2.

## 🔍 Drift Findings (P1, informational)
Unchanged from run 1, plus the post-review fixes touched `io_utils.py`, `readiness.py`,
`wrapup_receipt.py`, `render.py`, `reconcile.py`, `cli.py`, `observability/intent_miss.py`
(all consequences of the confirm-pass repairs; recorded in the PLAN execution notes).

## ✅ Consensus Findings
| id | sev | lens | location | summary | tag · disposition | voices |
|---|---|---|---|---|---|---|
| `ae4333902f7ff8af` | P1 | concurrency | `src/harness_maker/spec_need.py:257` | write_waiver's atomic_append call is unguarded and its only caller catches ValueError only, so the new short-write OSError escapes as a traceback | consensus-passed · accepted | concurrency, functionality, robustness |
| `0e80ec34acc91655` | P2 | consistency | `src/harness_maker/step_sensitivity.py:40` | Comment claims 7 knob entries / two orderings used once; the registry has 5 knob entries (le ×2, subset/bool_off/equal_by_design ×1) | consensus-passed · accepted | consistency, design |
| `bb34051459cef388` | P1 | consistency | `src/harness_maker/cli.py:2289` | Docs assert the verify JSONL ledger 'was retired' (verify.md.j2:306,356; wrapup_receipt.py:402) but the hm verify CI wrapper still writes verify-<date>.jsonl | consensus-passed · accepted | consistency |
| `a2418ed43a616349` | P2 | design | `src/harness_maker/step_sensitivity.py:469` | Reflection-based knob resolution for a single call site adds indirection with no type safety | consensus-passed · accepted | design |
| `f3dc1d317e51ec21` | P2 | design | `src/harness_maker/step_sensitivity.py:40` | Comment claims 7 knob entries / 2 orderings used once; registry has 5 knob entries and 3 single-use orderings | consensus-passed · duplicate | consistency, design |
| `39fa9a64b96c053a` | P2 | design | `src/harness_maker/step_sensitivity.py:449` | Correlated optional fields (knob/ordering/source_kind) enforced only by a runtime XOR check in validate() | consensus-passed · accepted | design |
| `99e7107882fd4bc5` | P2 | design | `src/harness_maker/templates/stages/verify.md.j2:539` | Check 1 --no-tdd prose nests preset/dev_mode conditionals inline; four behaviours in one paragraph | consensus-passed · accepted | design |
| `bad17e9cafc41ab6` | P1 | functionality | `src/harness_maker/render.py:1997` | _append_render_manifest catches only ValueError, not OSError, from atomic_append — a short write still aborts the whole render, contradicting the inline comment | consensus-passed · accepted | functionality |
| `fb6468310d07dcc9` | P1 | functionality | `src/harness_maker/spec_need.py:257` | write_waiver's atomic_append call is unguarded against the new ValueError/OSError contract; an oversized rationale that used to write now raises, colliding with the blank-rationale ValueError | consensus-passed · duplicate | concurrency, functionality, robustness |
| `dda4ae5e984878a5` | P1 | robustness | `src/harness_maker/spec_need.py:257` | write_waiver's atomic_append call is unguarded; its only CLI caller catches ValueError but not the new OSError | consensus-passed · duplicate | concurrency, functionality, robustness |
| `711381687fd116a7` | P2 | robustness | `src/harness_maker/spec_machine.py:1223` | _run_waiver_check suppresses OSError from the receipt write but not the new ValueError | consensus-passed · accepted | robustness |
| `ce10c1d790096c04` | P1 | security | `src/harness_maker/templates/stages/verify.md.j2:52` | Check 1 note claims each PLAN phase exit criterion is re-run by Check 2; Check 2 only runs the CI-derived commands, so script/manual-checklist criteria are not re-verified | consensus-passed · accepted | security |
| `ccc84e1a6878e370` | P2 | security | `src/harness_maker/templates/stages/verify.md.j2:50` | Verify cites execute Phase A.5 as the coverage backstop without disclosing its own registry grade (TUNE, discrimination unproven, Side-only n=52) | consensus-passed · accepted | security |
| `47fc3b888c6923a6` | P1 | tests | `tests/unit/test_observability_rows_at_base.py:152` | New GitProbeError test never exercises _dim_guardrails, the only place the exception is caught and turned into a signal | consensus-passed · accepted | tests |
| `ab6f7bcb2acd7dc9` | P2 | tests | `src/harness_maker/cli.py:2404` | Four new try/except-around-atomic_append call sites (cli, intent_miss, reconcile, render) have no direct test of the degrade behaviour | consensus-passed · accepted | tests |

## 📝 Manual-Only Findings
| id | sev | lens | location | summary | tag · disposition | voices |
|---|---|---|---|---|---|---|
| `8f4f5fd20ccef168` | P2 | codex | `tests/structural/test_step_sensitivity_registry.py:77` | Major: Duplicate rendered ordinals bypass the classification gate; the per-stage collision check required by ADR-001 is missing. | manual-only · accepted | codex |

## 🧊 Cross-model findings (frozen @ round 1)
frozen_at_round: 1 · models: [codex]

| id | source | severity | file | line | summary | evidence | needs_relaxation | disposition | oracle_result | status | invalidation_reason |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `8f4f5fd20ccef168` | codex | P2 | tests/structural/test_step_sensitivity_registry.py | 77 | Duplicate rendered ordinals bypass the classification gate; the per-stage collision check required by ADR-001 is missing | `union[stage].update(...)` discards duplicates; uniqueness asserted on registry keys only | false | accepted | No oracle; diff settles it: :76 set-collapses ordinals, :103 asserts registry keys only — ADR-001 per-stage uniqueness unimplemented | pending | — |

## Round records
### Iteration 1 (initial, run 2)
Findings: 16 (P1 5 · P2 7 · dup 3 · cross-model 1); dispositions accepted 13 · duplicate 3.

### Iteration 2 (run 2; Grade: C → A)
Fixes applied: 5 (P1) + 4 (P2, cheap)
| # | Severity | Summary | File | Status |
|---|----------|---------|------|--------|
| 1 | P1 | `waiver-set` CLI catches `(OSError, ValueError)` — `ae433390` (+dups `fb646831`, `dda4ae5e`) | src/harness_maker/spec_need.py | Applied · caused_by=none |
| 2 | P1 | render manifest append catches `(OSError, ValueError)` — `bad17e9c` | src/harness_maker/render.py | Applied · caused_by=none |
| 3 | P1 | "verify JSONL ledger retired" claim scoped to the slash-command stage (`hm verify` CI wrapper still writes) — `bb340514` | verify.md.j2 ×2, wrapup_receipt.py ×2 | Applied · caused_by=none |
| 4 | P1 | Check 1 note: Check 2 re-runs test-expressed exit criteria only; script/manual criteria have no re-check — `ce10c1d7`; A.5 grade caveat — `ccc84e1a` (P2) | src/harness_maker/templates/stages/verify.md.j2 | Applied · caused_by=none |
| 5 | P1 | GitProbeError test asserts the `_dim_guardrails` signal — `47fc3b88` | tests/unit/test_observability_rows_at_base.py | Applied · caused_by=none |
| 6 | P2 | `Ordering` comment: 5 knob entries — `0e80ec34` (+dup `f3dc1d31`) | src/harness_maker/step_sensitivity.py | Applied · caused_by=none |
| 7 | P2 | `_run_waiver_check` suppresses `(OSError, ValueError)` — `71138168` | src/harness_maker/spec_machine.py | Applied · caused_by=none |
| 8 | P2 | per-stage duplicate-ordinal assertion (ADR-001) — codex `8f4f5fd2` | tests/structural/test_step_sensitivity_registry.py | Applied · caused_by=none |

Verify build: ruff/mypy clean; delegation prose bound (+60) restored by compressing the Step 0.5 receipt sentence; snapshots regenerated; targeted set GREEN; golden re-based; DELTA re-measured.
Remaining: 4 (P2 — reflection knob resolution, KnobRef bundling, verify paragraph restructure, four-caller degrade test) — accepted, pending, outside the fix queue at grade A.
Churn: 0.051 (max: tests/unit/test_observability_rows_at_base.py, measured 16, excluded 0) — rereview: skipped — churn 0.05 < 0.30
Lifecycle transitions this round: 12 × pending→resolved (progress: yes).

## Confirmation pass confirm-1 (run 2; frozen @ 67fa3f25, span b778e524..67fa3f25)
Lens coverage 7/7 (consistency re-dispatched on `opus` after the `sonnet` dispatch died on a
session rate limit). **No new P0/P1.** P2/P3 raised: concurrency (readiness rev-parse asymmetry),
robustness (render docstring stale; spec_machine slug cap), design (spec_need docstring rationale;
readiness imports a private `_git_stdout`), tests (two P3: four-caller ValueError test;
duplicate-ordinal negative control), consistency (DELTA sentence truncated; golden `reason`
spliced; wrapup_receipt comment `hm verify`; bare `print` in cli.py; "TUNE-graded" wording).

**Repair round (separately budgeted):** two structural gates went red on the *frozen* text
(`test_every_module_the_rendered_surface_calls_is_dispatchable`,
`test_tc1_every_template_invocation_is_registered`) because the scoped "retired ledger" wording
named the literal `hm verify`, which is not a dispatchable `hm` module. Fixed the two template
sites ("the CI `verify` command in `cli.py`"), plus the five consistency P2/P3s above. Snapshots
regenerated; golden re-based (−8 222 / −8 360 / −8 234 / −8 234); DELTA re-measured (−8 222).
Because the artifact moved after the confirm-1 freeze, a **confirm-2** pass runs on `07549f1c`.
Remaining accepted-pending: design P2 ×4 (reflection knob resolution, KnobRef bundling, verify
paragraph restructure, spec_need docstring), robustness P2 ×2, concurrency P2 ×1, tests P2/P3 ×3.


## Confirmation pass confirm-2 (run 2; frozen @ 07549f1c, span b778e524..07549f1c)
Lens coverage 7/7 (`blocks_approval: false`). **Zero new consensus-passed P0/P1** → **APPROVED**.
P2/P3 raised (recorded, accepted-pending — no fixes are applied in a confirmation pass):
consistency P2 ×3 (PLAN §Phase 5/§notes still carry the pre-repair delta figures −9 168 / −9 137…−9 190 —
corrected in the PLAN below; TUNE entries review C2/C3 lack the `Side-preset only, n=` tag; the
HOW-IT-WORKS guides still list `verify-{date}.jsonl` as a `/hm:verify` output), consistency P3 ×2
(PLAN ADR-008/Phase 2 knob list says 7, shipped 5 — corrected below; the `record_path` negative
golden over-matches the delegation-on render), functionality P2 ×1 (render manifest docstring —
duplicate of the confirm-1 robustness P2).

## 🔁 Oscillation
(none — `review_churn oscillation --rounds 2` returned no rows)

## Review Iteration Summary (run 2)

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | C     | —             | 16 (P1 5 · P2 7 · dup 3 · cross-model 1) | — |
| 2         | A     | 5 P1 + 4 P2   | 4 (P2)    | 0   |
| confirm-1 | — (observation) | — | — | 0 P1 · 5 P2 · 2 P3 → gate-driven repair round (wording) + 5 fixes |
| confirm-2 | — (observation) | — | — | **0 P1** · 4 P2 · 2 P3 |

Final grade: **A** — confirmation pass clean → Status **APPROVED**
Iterations used: 2 / 3 (plus one separately-budgeted repair round)
Exit reason: converged

## 📏 Size & Complexity (round 2, from 5c)

| File | LOC | Cyclomatic | Max nesting | Status |
|------|-----|------------|-------------|--------|
| src/harness_maker/render.py | 2280 → 2280 | {'cyclomatic': 306, 'max_function_lines': 221, 'max_nesting': 8} → {'cyclomatic': 306, 'max_function_lines': 221, 'max_nesting': 8} | null → null | measured |
| src/harness_maker/spec_machine.py | 1518 → 1518 | {'cyclomatic': 219, 'max_function_lines': 109, 'max_nesting': 4} → {'cyclomatic': 219, 'max_function_lines': 109, 'max_nesting': 4} | null → null | measured |
| src/harness_maker/spec_need.py | 608 → 610 | {'cyclomatic': 66, 'max_function_lines': 106, 'max_nesting': 3} → {'cyclomatic': 66, 'max_function_lines': 108, 'max_nesting': 3} | null → null | measured |
| src/harness_maker/step_sensitivity.py | 554 → 554 | {'cyclomatic': 41, 'max_function_lines': 17, 'max_nesting': 2} → {'cyclomatic': 41, 'max_function_lines': 17, 'max_nesting': 2} | null → null | measured |
| src/harness_maker/templates/stages/verify.md.j2 | 388 → 391 | None → None | null → null | not-python |
| src/harness_maker/wrapup_receipt.py | 675 → 676 | {'cyclomatic': 87, 'max_function_lines': 189, 'max_nesting': 3} → {'cyclomatic': 87, 'max_function_lines': 190, 'max_nesting': 3} | null → null | measured |
| tests/snapshot/prod-firmware-spec.expected.yaml | 181 → 181 | None → None | null → null | not-python |
| tests/snapshot/prod-firmware-task.expected.yaml | 181 → 181 | None → None | null → null | not-python |
| tests/snapshot/prod-tauri-app-spec.expected.yaml | 181 → 181 | None → None | null → null | not-python |
| tests/snapshot/prod-tauri-app-task.expected.yaml | 181 → 181 | None → None | null → null | not-python |
| tests/snapshot/side-python-cli-spec.expected.yaml | 181 → 181 | None → None | null → null | not-python |
| tests/snapshot/side-python-cli-task.expected.yaml | 181 → 181 | None → None | null → null | not-python |
| tests/snapshot/side-tauri-app-spec.expected.yaml | 181 → 181 | None → None | null → null | not-python |
| tests/snapshot/side-tauri-app-task.expected.yaml | 181 → 181 | None → None | null → null | not-python |
| tests/structural/test_step_sensitivity_registry.py | 247 → 252 | {'cyclomatic': 36, 'max_function_lines': 26, 'max_nesting': 2} → {'cyclomatic': 38, 'max_function_lines': 26, 'max_nesting': 2} | null → null | measured |
| tests/unit/test_observability_rows_at_base.py | 166 → 175 | {'cyclomatic': 21, 'max_function_lines': 15, 'max_nesting': 1} → {'cyclomatic': 25, 'max_function_lines': 24, 'max_nesting': 1} | null → null | measured |

Report only; no threshold.

Status: APPROVED
human_review_needed: false
Counters (see §5): unreviewed 0 · prior-fix 0 · unattributed 0
Cross-model: codex invoked once (round 1), 1 finding PIDA-accepted and fixed in round 2; disposition ledgered.
Full unit+structural suite: fullsuite8 (post-wording-fix state) **rc=0**; fullsuite9 (confirm-2 artifact) rc recorded in the wrapup notes (the two base-failing tests deselected).
