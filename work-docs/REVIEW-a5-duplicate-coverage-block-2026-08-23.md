---
type: review
task_slug: a5-duplicate-coverage-block
status: APPROVED
created: 2026-08-23
reviewers_invoked: [design, functionality, robustness, consistency, security, concurrency, tests, codex]
consensus_method: cross-check
run_id: d861d7b2020b
drift_verdict:
  result: scope_violation
  scope_violations:
    - .claude/harness.yaml
    - tests/structural/test_instruction_preservation.py
    - tests/structural/test_roundtrip_budget.py
    - tests/unit/test_agent_body_partials.py
  scenario_misses: []
  task_slug: a5-duplicate-coverage-block
  computed_at: 2026-08-23T08:56:48Z
---

# REVIEW — a5-duplicate-coverage-block

## 🎯 Round 1 Summary

**Grade C** (P0 0 · P1 4 · P2 8), `human_review_needed: true`. Lens coverage 7/7,
`blocks_approval: false`. Four consensus-passed P1s, one cross-model P1 tagged `manual-only`.

## 🔍 Drift Findings

`result: scope_violation`, severity P1. Four changed paths sit outside every PLAN phase's scope:

- `.claude/harness.yaml` — two configuration changes made on user request in the same session
  (`second_opinion.models` dropped `antigravity`; `interview.comprehension.depth` became `deep`).
  Not a phase of this PLAN. **Seven of the nine failures the Phase 2 full-suite run had to
  reconcile came from this file, not from the SPEC.**
- `tests/structural/test_instruction_preservation.py`, `tests/structural/test_roundtrip_budget.py`,
  `tests/unit/test_agent_body_partials.py` — Phase 2's scope named "the two baseline JSONs"; the
  reconciliation surface was in fact wider. A PLAN under-specification, not a silent expansion.

Scenario misses: none. AC-001..003 are bound by the parity test, AC-004 by the judgment verdict.

Three further paths (`.claude/memory/{failures.md,wiki.md,session/README.md}`) appear in the
diff because `freeze resolve-base` returned `933c961a`, one commit behind the merge-base. They
belong to that commit, not to this task, and were excluded from every lens brief.

## ✅ Consensus Findings

| id | Sev | Finding | Lens | Resolution |
|---|---|---|---|---|
| `r1-spec-md-stale-testnames` | P1 | SPEC Verification-Criteria table named two tests that do not exist | tests | Fixed r2 |
| `r1-machine-stale-testids` | P1 | machine SPEC `test_ids` named nonexistent nodes; `pending_test: true` made `spec_machine` Rule 3 skip them, so an earlier "check passes" was never evidence they resolved | consistency | Fixed r2; flag flipped, Rule 3 now runs `pytest --collect-only` |
| `r1-site4-no-locus` | P1 | The occurrence count stood in for a locus check the fourth site (`execute.md.j2:222`) never got | tests | Fixed r2; verified by the exact padding mutation (aggregate held at 4, only site 4 stripped) |
| `r1-negation-blind` | P1 | Both window predicates are blind to negation; only one blind spot was disclosed | tests | Disclosed r2 |

## ⚠️ Weak Consensus

None.

## 📝 Manual-Only Findings

| id | Sev | Finding | Source | Resolution |
|---|---|---|---|---|
| `1e33584dee639958` | P1 | The clause said such tests "must PASS" unconditionally, targeting the same `per_scenario.quality` field the banned-patterns rule forces to FAIL — two rules with opposite verdicts over a tautological test asserting a different observable | codex | **Fixed r2 on explicit user instruction.** A single cross-model voice is `manual-only` and not auto-fix eligible; the user directed it be fixed. AC-004 was re-judged `pass` on the new subject. |
| `af9f6c69874a303e` | P2 | `interview.comprehension.depth: deep` was applied to the base checkout only; the committed worktree copy read `standard`, so landing would have silently reverted a user request — and a comment added earlier in this task asserted the deep value for the very file the baseline reads | codex | Fixed r2 |

## 🤝 Disagreements

None. No two lenses assigned different severities to one location.

## 🧊 Cross-model findings (frozen @ round 1)

`codex` — `invoked`, 3 findings, 69.6s. PIDA (mode B): **2 accepted, 1 duplicate, 0 rejected, 0 unresolved.**

| id | Sev | Disposition | Oracle |
|---|---|---|---|
| `1e33584dee639958` | P1 | `accepted` | `test-reviewer_body.md.j2:105` "must PASS" targets `per_scenario.quality`, the same field Section 2 (:26) forces to FAIL for banned patterns — unconditional conflict |
| `ce5d76b7ded8fb2c` | P2 | `duplicate` | Same file and substance as this round's tests-lens P1s at :176 (substring containment) and :318 (count backstop misses `execute.md.j2:222`) |
| `af9f6c69874a303e` | P2 | `accepted` | `.claude/harness.yaml:35` reads `depth: standard`; `test_instruction_preservation.py:136` claims `deep` for the same file the baseline reads |

`antigravity` was disabled by the user before this review; it cast no vote and is not a skip.

**Cross-model earned its place twice in this task.** At plan time it was `plan-validator` that
caught a phantom judgment subject; here `codex` caught both the unconditional-PASS collision and
a config change that would have reverted itself on landing. Neither was found by any Claude lens,
and the second is invisible inside the diff — it is a disagreement between two copies of one file.

## Auto-Fix Loop

### Iteration 2 (Grade: C → A)

Fixes applied: 8

| # | Sev | Summary | File | Status |
|---|---|---|---|---|
| 1 | P1 | Fourth locus assertion for the Phase A authoring rule | `test_duplicate_trigger_observable_parity.py` | Applied · falsified in isolation |
| 2 | P1 | Negation blind spot disclosed; "irreducible" softened | same | Applied |
| 3 | P1 | SPEC `.md` table test names | `SPEC-a5-...md` | Applied |
| 4 | P1 | machine SPEC `test_ids` + `pending_test: false` | `SPEC-a5-...machine.yaml` | Applied · Rule 3 now resolves them |
| 5 | P1 | "must PASS" bounded at both sites | `test-reviewer_body.md.j2`, `execute.md.j2` | Applied on user instruction |
| 6 | P2 | `depth: deep` in the committed copy | `.claude/harness.yaml` | Applied · re-baselined |
| 7 | P2 | `_routing_bullet` EOF boundary | `test_duplicate_trigger_observable_parity.py` | Applied |
| 8 | P2 | PLAN Success Criteria checkboxes | `PLAN-a5-...md` | Applied |

Remaining: 5 P2 | New issues introduced: 1 (`test_the_depth_override_lever_actually_moves_the_render`
broke on fix 6 — it hardcoded `"deep"` as its contrast depth, valid only while the repo config was
`standard`. Classified per `targeted-test-selection` §4.5 as a caller-side coupling in the test
rather than a bad fix: reverting would have restored the user-request regression, so the coupling
was removed instead by deriving the contrast from the configured depth. The confirmation pass's
`tests` lens independently judged this a strengthening, not a weakening, tracing `render_surface()`
to confirm `contrast != configured` holds by construction.)

Churn: 1.00 (max: `work-docs/BASELINE-DELTA-a5-duplicate-coverage-block.md`, measured 19, excluded 0)
Re-review: dispatched per `review_consensus plan` — one `functionality` lens over the changed
hunks. **No P0/P1, no P2.**

## 🔁 Oscillation

None. `review_churn oscillation --rounds 2` returned `[]`.

## Confirmation Pass (confirm-1)

Frozen at `133dcffb`, span `933c961a..133dcffb` — the whole review, not the repair round. All
seven lenses dispatched, `blocks_approval: false`, **zero new consensus-passed findings at P0 or
P1**. No fixes applied during the pass.

Five P2s surfaced. Two were corrected after the pass closed, on the user's explicit call, because
both were false statements in artifacts that will be committed:

- `c1-plan-stale-judgment-hash` — the PLAN recorded AC-004's pre-re-judgement hash while the
  machine SPEC carried the current one. Corrected, and the re-judgement is now recorded in the
  PLAN's Phase 3 note. (The finding said "twice"; only one occurrence was the hash value — the
  second mention names the field, not a value.)
- `c1-docstring-self-contradiction` — round 2 answered an overclaim finding by *adding* a
  retraction and leaving the original bolded topic sentence in place, so one paragraph asserted
  and then unsaid the same thing. The topic sentence now agrees with its own retraction.

Three carried to a follow-up: `c1-anchor-uniqueness` (the three anchor-locating helpers use
first-match slicing with no uniqueness assertion, unlike every other site-check in the same
module — latent, no current template renders those anchors twice), `c1-stale-line-cite`
(`:302` should read `:306`; no assertion consumes it), and `r1-overloaded-bullet` (re-derived by
the design lens with a stronger argument: that the sentence needed six A.5 rounds to verify
mechanically is itself evidence about its shape).

`tests` lens, the sharpest result of the pass: *"I could not construct a mutation that both
(a) satisfies every assertion in this file and (b) reproduces the coarse 'count of tests' trigger
the change exists to remove."*

## 📏 Size & Complexity

Not measured — `review_churn complexity` was not run this review. Recorded as absent rather than
reported as zero; a non-Python file and a simple one are different facts and neither was measured.

## Deliberately Deferred

- Define the qualifier once in Jinja instead of five hand copies (design P2, both rounds). The
  strongest structural criticism in this review: it would have made all three A.5 failure classes
  impossible by construction. Out of the PLAN's Phase 1 scope, and applying it now would move all
  four sites, the parity test, the snapshots and the baselines again.
- The uncleaned `mkdtemp` render root — the sibling `test_multi_lens_a5.py` has the same pattern,
  so fixing one alone leaves the other leaking.
- PLAN ADR-002's accepted residual: `per_scenario[].reason` is capped at 80 chars while the repair
  arm treats an ambiguous reason as blanket scope.
- Whether the `.claude/harness.yaml` config changes belong in this commit — **wrapup's call.**

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | C     | —             | 12        | —   |
| 2         | A     | 8             | 5 (P2)    | 1   |
| confirm-1 | A     | 0 (read-only) | 5 (P2)    | 3 (P2) |

Final grade: **A**
Iterations used: 2 / 3
Exit reason: converged
Status: **APPROVED**
human_review_needed: false
Counters: unreviewed 0 · prior-fix 1 · unattributed 0
