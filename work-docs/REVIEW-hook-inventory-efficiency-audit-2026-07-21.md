---
type: review
task_slug: hook-inventory-efficiency-audit
status: APPROVED
created: 2026-07-21
reviewers_invoked: [code-reviewer, codex, antigravity]
consensus_method: cross-check
drift_verdict:
  result: clean
  scope_violations: []
  scenario_misses: []
  task_slug: hook-inventory-efficiency-audit
  computed_at: 2026-07-21T00:00:00Z
second_opinion_results:
  - model: codex
    status: invoked
    reconciliation: []   # 0 findings — explicit APPROVE (confidence 0.96)
  - model: antigravity
    status: failed
    reconciliation: []   # agy --print returned a generic sandbox greeting, no JSON payload (fail-closed)
human_review_needed: false
---

# REVIEW — hook-inventory-efficiency-audit (2026-07-21)

## 🎯 Round 1 Summary

- **Final grade: A** (P0=0, P1=0 consensus-passed). **Status: APPROVED.** `human_review_needed: false`.
- **Reviewed diff:** branch `hm/hook-inventory-efficiency-audit` vs `main` — 13 files, +170/−76
  (render.py retirement mechanism, 2 settings templates, test file, 8 snapshot hashes, harness.yaml flip).
- **Voter pool (K=2 consensus):** code-reviewer (Claude, opus) + codex (invoked) + antigravity (failed → no vote).
- **1 P2 finding raised (code-reviewer, single-source → manual-only) and AUTO-FIXED this round.**
  No P0/P1. Cross-model: codex independently returned **0 findings** (explicit APPROVE, confidence 0.96).

## 🔍 Drift Findings

**Clean.** All 13 changed files are within PLAN Phase 1–3 scope (render.py=Phase 1; settings
templates=Phase 1; test file=Phase 1/2; 8 snapshots=Phase 2; harness.yaml=Phase 2). No scope
violation, no incomplete phase. Phase 3 (delete this repo's dead `.claude/hooks/hooks.json`) is
correctly NOT in this branch diff — it is a base-level artifact deferred to wrapup (ADR-003 revised).

## ✅ Consensus Findings

None at P0/P1. codex (independent voter) returned an empty findings array with an explicit APPROVE.
code-reviewer confirmed the mechanism correct across all 5 probes (under-retire, over-retire,
guard-survives / user-command-dropped, flat-schema skip, idempotency) with concrete traces.

## ⚠️ Weak Consensus

None.

## 📝 Manual-Only Findings

### P2 — retired-set invariant scope narrower than application scope (AUTO-FIXED)
- **Source:** code-reviewer (single-source; codex did not flag → manual-only, does not affect grade).
- **File:** `src/harness_maker/render.py:730` + `tests/unit/test_render_settings_hooks.py`.
- **Issue:** `_strip_shipped_commands` applies `_HARNESS_RETIRED_HOOK_INVOCATIONS` to EVERY
  nested-schema merge (settings.json AND `.codex/hooks.json`, both via `_merge_hooks_json(schema="nested")`),
  but the safety-invariant test `test_retired_invocations_absent_from_current_templates` only iterated
  the settings templates. Latent (not a live bug — codex/cursor templates don't ship `autopilot_guard`,
  and a still-shipped hook is always re-added by `new_entries`), but a future retired hook added to a
  codex template could be silently mis-scoped.
- **Resolution (applied Round 1):** extended the invariant test to also render `codex/hooks.json.j2`
  (`[*SETTINGS_TEMPLATES, "codex/hooks.json.j2"]`), and aligned the `render.py` frozenset comment to
  state the set applies to all nested merges (settings + codex; Cursor flat-exempt). Re-verified:
  `test_render_settings_hooks.py` 41 tests green, ruff clean. Committed as `wip(review)` e8261509.

## 🤝 Disagreements

None — codex (0 findings) and code-reviewer (1 P2, no P0/P1) agree the change is correct; they differ
only on whether the doc/test-scope alignment was worth surfacing. antigravity produced no usable output.

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | A     | 1 (P2 scope-alignment) | 0 | 0 |

Final grade: **A**
Iterations used: 1 / 3
Status: **APPROVED**
human_review_needed: **false**

## Cross-model notes

- **codex** — invoked, 0 findings, confidence 0.96. Independently confirmed: both retired invocation
  forms cover all 3 historical sites; mixed-group user commands preserved; Cursor flat exclusion matches
  scope; re-render stable; swapped stage-bump fixtures preserve coverage.
- **antigravity** — `status: failed`. `agy --print --sandbox` returned a generic startup greeting
  instead of consuming the piped review prompt → fail-closed adapter found 0 JSON payloads. Graceful
  degrade (warn-and-proceed); ledger row written to `.claude/observability/second-opinion.jsonl`.
  Known agy flakiness (no CLI-level schema enforcement). The Claude + codex voters are sufficient for
  an APPROVED verdict without it.
