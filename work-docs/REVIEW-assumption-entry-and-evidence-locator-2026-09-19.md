---
type: review
task_slug: assumption-entry-and-evidence-locator
status: APPROVED
human_review_needed: true
confirm_pass_ran: true
confirm_pass_new_severe_n: 0
created: 2026-09-19
reviewers_invoked: [code-reviewer, security-reviewer, concurrency-reviewer, test-reviewer, codex]
consensus_method: cross-check
run_id: 0718585ae9a6
review_base: b48bcec4131ffc26f8106d667caf45be6a7f2515
drift_verdict:
  result: clean
  scope_violations: []
  scenario_misses: []
  task_slug: assumption-entry-and-evidence-locator
  computed_at: 2026-09-19T00:00:00Z
---

# REVIEW — assumption-entry-and-evidence-locator

> **Base note.** `intent-layer-ops` landed on main (b48bcec4) between `/hm:execute` and this
> review. The branch was rebased onto it before round 1 (conflicts resolved by keeping both
> sides; golden, snapshots and both baselines re-derived). The stored `review_base` had already
> been resolved to the pre-rebase `origin/main` (974a554a), which would have put the other
> task's diff in scope, so the ref was moved to b48bcec4 **before any lens dispatched** — the
> reviewed span is exactly this task's change.

## 🎯 Round 1 Summary

- Lenses: 7/7 exercised (4 dispatches, two passes) — `blocks_approval: false`.
- Cross-model: codex `invoked` (63 s), 4 findings → PIDA: 3 `accepted`, 1 `unresolved`.
- Grade **B** — consensus-passed P0 0 / P1 2 / P2 5 / P3 1. `human_review_needed: true`
  (manual-only P1 from codex present).
- Fixable this round (P1, consensus-passed, concrete suggestion): `8b1d5f50ebad5cb3`, `ff469c7d37b6a535`.

## 🔍 Drift Findings

`clean` — all 32 changed paths are inside a PLAN phase scope; no incomplete phase; no SPEC
scenario without coverage.

## ✅ Consensus Findings

| id | Sev | Lens | Where | Finding |
|---|---|---|---|---|
| 8b1d5f50ebad5cb3 | P1 | consistency | `src/harness_maker/evidence_locator.py:76` | `capture()`/`classify()` reimplement `fingerprint()`'s normalize+hash — three copies of a persisted format; `fingerprint()` has no production caller |
| ff469c7d37b6a535 | P1 | consistency | `src/harness_maker/templates/skills/intent-layer/SKILL.md.j2:20` | the skill's `add` form shows `--locator` independent of `--text`; the CLI refuses that |
| c76cb19de2ac1d7c | P2 | design | `src/harness_maker/world.py:686` | `_locator_problems` bakes the file prefix into `IntentError.field`, unlike sibling validators |
| 95b12f3a820686d4 | P2 | security | `src/harness_maker/evidence_locator.py:108` | unbounded-digit `path:A-B` raises an uncaught `ValueError` (int max-str-digits) |
| 265a1f7c8637f8f9 | P2 | concurrency | `tests/integration/test_world_assume_concurrency.py:129` | fixed 1.0 s sleep before the barrier can under-run import time |
| 34edc703740ed8b0 | P2 | tests | `src/harness_maker/world.py:1144` | `add_assumption`'s own status guard is masked by argparse `choices`; untested |
| 3fd9cf67eb1e25dd | P2 | tests | `tests/unit/test_world_evidence_locator.py:1241` | no regression test for the unbounded-digit boundary |
| c2fec4a48d750199 | P3 | tests | `src/harness_maker/world.py:686` | the non-dict evidence skip in `_locator_problems` is untested |

## ⚠️ Weak Consensus

None.

## 📝 Manual-Only Findings

All four are single cross-model voices (K=2 for cross-model voters), so they neither vote nor
enter the auto-fix queue.

| id | Sev | Disposition | Finding |
|---|---|---|---|
| d6001057f39e2069 | P1 | accepted | a locator-bearing evidence entry with **no** `observed_at` key still invalidates the whole file (the existing required-key rule), unloading every assumption and making unrelated dependents `broken` — contradicts SPEC "Malformed stored data" |
| 082521d2a9fe55ae | P2 | accepted | `add --locator ''` / `--observed-at ''` without `--text` is written instead of refused (truthiness check) — S2 |
| dbc139524f49c9d0 | P1 | unresolved | the 5.7 "new" branch does not say to propose and confirm the new record's exact arguments before `add` |
| 208387053091e577 | P2 | accepted | AC-010's render test checks literal presence only — stale-first order and the Other fallback are unasserted |

## 🤝 Disagreements

None — no two voices put different severities on one location.

## 🧊 Cross-model findings (frozen @ round 1)

frozen_at_round: 1 · models: [codex]

| id | source | severity | file | line | summary | evidence | needs_relaxation | disposition | oracle_result | status | invalidation_reason |
|---|---|---|---|---|---|---|---|---|---|---|---|
| d6001057f39e2069 | codex | P1 | src/harness_maker/world.py | 583 | missing observed_at on a locator entry unloads the ledger | required-key validator rejects it; load_world loads none | false | accepted | main-loop repro: all assumptions unloaded, OBJ broken | pending | — |
| 082521d2a9fe55ae | codex | P2 | src/harness_maker/world.py | 1148 | empty `--locator`/`--observed-at` bypass the refusal | truthiness check | false | accepted | main-loop repro: record written | pending | — |
| dbc139524f49c9d0 | codex | P1 | src/harness_maker/templates/stages/wrapup.md.j2 | 575 | "new" treated as yes without confirming the add arguments | no step collects/confirms id, claim, status | false | unresolved | no oracle for .j2 | pending | — |
| 208387053091e577 | codex | P2 | tests/unit/test_render_intent_layer_assume_add.py | 70 | AC-010 oracle misses stale-first order and the Other fallback | literal-presence asserts only | false | accepted | pytest exit 0 with either broken | pending | — |

### Build-break repair between rounds (not a finding)

The integrated full suite (8 718 passed) had one failure:
`test_intent_layer_ops_invariance.py::test_ac_006_surface_pinned_and_allowance_retired`. That
task's byte pin on `wrapup` is taken at 0.57.1, the same release, so every later wrapup change
fails it with no way out short of editing that task's pin. Its sibling test already hands off
through `_current_delta_doc()` ("a later task moved the baseline; this document is historical").
The same hand-off was added to its render test and to this task's AC-012 test, so exactly one
invariance test (the one whose delta doc quotes the current baseline) owns the pin at a time.
Result: 11 passed, 2 skipped (the superseded pin). The edit is outside the PLAN's phase scope and
is recorded here and in the PLAN.

### Iteration 2 (Grade: B → A)
Fixes applied: 1
| # | Severity | Summary | File | Status |
|---|----------|---------|------|--------|
| 1 | P1 | `capture()`/`classify()` now hash through `fingerprint()`, the single owner of the persisted format (`_normalized` helper; `_digest` has one caller) — 8b1d5f50ebad5cb3 | src/harness_maker/evidence_locator.py | Applied · caused_by=none |
| 2 | P1 | SKILL `add` form: nest `--locator` under `--text` — ff469c7d37b6a535 | src/harness_maker/templates/skills/intent-layer/SKILL.md.j2 | Refused — oracle-blocked · caused_by=none |

Fix #2 refused per `targeted-test-selection` §6: the covering test
(`test_render_intent_layer_assume_add.SKILL_ADD_FORM`) pins the unnested literal, so the fix needs
a test edit that is not this finding's own target. Retagged `manual-only`, disposition
`unresolved` / `oracle-blocked`. The test literal and the CLI disagree, which is now a recorded
decision for a human.

Verification: `tests/unit/test_world_evidence_locator.py` + `test_world_assume_add.py` 62 passed;
mypy/ruff clean.
Remaining: 6 consensus-passed (P2 ×5, P3 ×1 — none grade-lowering) + 5 manual-only | New issues introduced: 0
Churn: 0.142 (max: src/harness_maker/evidence_locator.py, measured 1, excluded 0) — re-review
skipped: `churn 0.14 < 0.30` (unreviewed_fix_count 1). Complexity: evidence_locator.py cyclomatic 44 → 43, LOC 141 → 148.
Progress: 1 transition (8b1d5f50 pending → resolved).

## Confirmation pass (confirm-1)

Frozen `b48bcec4..ef96658c` (the whole review, including the round-2 fix), 7/7 lenses exercised,
`blocks_approval: false`. New findings: one P3 (tests) — `classify()`'s moved scan returns the
first ascending match and no fixture forces a tie-break (`tests/unit/test_world_evidence_locator.py:1382`).
Zero new consensus-passed P0/P1 → **APPROVED**. The core lens independently confirmed that
8b1d5f50 is resolved (`_normalized` is idempotent, so `classify`'s pre-normalized windows and
`capture`'s raw span hash identically). Freeze refs reaped.

## ⚠️ Human review needed

Grade A, but these severe findings were not consensus-verified — human review is required
before wrapup:

| id | Sev | Why it is here | Recommended action |
|---|---|---|---|
| d6001057f39e2069 | P1 | codex, PIDA `accepted`, reproduced: a locator entry with no `observed_at` unloads every assumption and breaks unrelated dependents | fix: exempt locator-bearing entries' `observed_at` from the required-key rule and route it through `_locator_problems` (ADR-008 intent) |
| ff469c7d37b6a535 | P1 | lens finding, refused as `oracle-blocked`: the test literal pins the unnested `[--locator]` form the CLI refuses | fix: nest `[--text --observed-at [--locator <path:A-B>]]` in SKILL and in `SKILL_ADD_FORM` together |
| dbc139524f49c9d0 | P1 | codex, PIDA `unresolved` (no .j2 oracle): 5.7 "new" writes without a step that shows the proposed id/claim/status for confirmation | fix: one sentence — propose the exact `add` arguments and ask once more before running it |

The P2/P3 consensus findings (6) and codex P2s (2) are carried for a human sweep; none moves
the grade.

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | B     | —             | 12        | —   |
| 2         | A     | 1             | 11        | 0   |

Final grade: A
Iterations used: 2 / 3
Exit reason: converged

## 📏 Size & Complexity

| File | LOC | Cyclomatic | Max nesting | Status |
|------|-----|------------|-------------|--------|
| src/harness_maker/evidence_locator.py | 141 → 148 | 44 → 43 | 2 → 2 | measured |

Status: APPROVED
human_review_needed: true
Counters (see §5): unreviewed 1 · prior-fix 0 · unattributed 0

## Post-review fixes (operator-directed, 2026-09-19)

The operator chose to fix the three human-review P1s and two P2s before wrapup. Tests were
written first and observed RED (8 failing for the intended reasons), then the fixes:

| id | Sev | Fix | Test |
|---|---|---|---|
| d6001057f39e2069 | P1 | `_validate_assumption_record` no longer requires `observed_at` on a **locator-bearing** entry; `_locator_problems` reports it (ADR-008). A locator-less entry still requires it. | `test_ac_009_a_locator_entry_without_observed_at_is_reported_not_fatal` (record + unrelated dependent survive; reported; writers now load the file and preserve the entry — the newly reachable window) |
| ff469c7d37b6a535 | P1 | SKILL `add` form → `[--text --observed-at [--locator <path:A-B>]]`, test literal updated with it (operator authorised the test edit the auto-fix refused) | `test_ac_011_skill_lists_add_and_locator` |
| dbc139524f49c9d0 | P1 | 5.7 "new": show the exact `add` arguments and ask once more; run only on "yes", otherwise write nothing (same line, no new call) | `test_ac_010_…` now asserts `new` → confirm literal → ask token → `add` order |
| 082521d2a9fe55ae | P2 | `add_assumption` tests `is not None`, so `--locator ''` / `--observed-at ''` without `--text` are refused | two new `test_ac_002` rows |
| 95b12f3a820686d4 | P2 | `_SPEC_RE` digits bounded to `\d{1,9}` → `LocatorError`, not a bare `ValueError` | `test_ac_003_capture_refuses_bad_citations[digits-past-int-limit]` (also closes 3fd9cf67eb1e25dd) |

Surface: wrapup grew a further +165 / +168 on the existing line; the fold, pin, golden
(`rebases` entry updated) and snapshots were re-derived — BASELINE-DELTA §3/§3.1 carry the final
numbers (+713 / +723 over b48bcec4, round trips +1). Structural + render suites: 755 passed.
Still carried for a human sweep (not fixed): c76cb19de2ac1d7c, 265a1f7c8637f8f9,
34edc703740ed8b0, c2fec4a48d750199, 208387053091e577 (partly — order of `new` vs the confirm step
is now asserted; stale-first ordering still is not), and the confirm-1 P3 on the moved-scan tie-break.

**Post-fix confirmation (one `code-reviewer`, functionality/robustness/consistency over the
162-line fix diff):** all five closed, **zero new findings**. It grepped every `observed_at`
reader in `world.py` (21 sites) — none assumes the key on an evidence entry; `_aware_instant(None)`
degrades to "reported". It traced `--locator ''` with `--text` to a clean `LocatorError` and
`--observed-at ''` with `--text` to a clean `WorldError('observed_at')` (those two with-text
variants are not separately tested).
