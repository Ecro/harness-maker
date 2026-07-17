---
type: review
task_slug: loop-marker-session-scoping
status: APPROVED
created: 2026-06-21
reviewers_invoked: [code-reviewer x2, concurrency-reviewer, security-reviewer, codex]
consensus_method: k-of-3 (+ codex heterogeneous voter)
drift_verdict:
  result: clean
  scope_violations: []
  scenario_misses: []
  task_slug: loop-marker-session-scoping
  computed_at: 2026-06-21
final_grade: A
human_review_needed: false
---

# REVIEW — loop-marker-session-scoping (P1+P2+P3 increment)

## 🎯 Round 1 Summary

- **Diff reviewed:** the P1+P2+P3 Python layer (10 files, 660+/39-): `loop_marker.py`
  (new), `hooks/sessionid_envfile.py` (new), `hooks/loop_gate.py`,
  `gates/worktree_gate.py`, `worktree.py`, + 5 test files.
- **Grade: D** (consensus P0/P1 = feature non-functional end-to-end).
  Threshold A not met → **CHANGES_REQUESTED**, `human_review_needed: true`.
- **Unanimous verdict (4 voters):** the P1-P3 Python code is *internally correct*
  — but the feature **does not fire** because the producer wiring (planned P4)
  is absent. This is the deferred-scope gap, surfaced precisely.

## ✅ What all reviewers confirmed CORRECT (no findings)

- All **four** marker-content readers drop the `claude_session_id:` header by the
  explicit `startswith("/")` rule (worktree `_read_active_worktrees`,
  `worktree_gate._read_active_worktrees`, `_marker_referenced_paths`,
  `_session_worktrees`) — incl. the 4th reader that broke finalize mid-execute,
  now fixed.
- Claude `session_id` (content) never contaminates the registry UUID
  (`_owned_session_uuids` reads the filename only).
- `sanitize_session_id` symmetric on all 3 boundaries; idempotent even for
  non-tame ids (hash16 re-matches the tame regex). **Security review: 0 findings**
  — no path traversal, no env-file injection (value is hex/dash only, no
  newline/`$`/`;`/`=`/space).
- `atomic_write` used for marker + env-file; resume-idempotent; prune/`_clear`
  never delete another live session's marker.
- `--claude-session-id` CLI value-flag parsing correct (no off-by-one, back-compat).

## ✅ Consensus Findings (consensus-passed)

| # | Sev | Finding | Voters | Status |
|---|-----|---------|--------|--------|
| C1 | P0 | `hooks.json.j2` (+ `codex/hooks.json.j2`) never registers the `sessionid_envfile` SessionStart hook → `HM_SESSION_ID` never set | cr#1, concurrency, codex(summary) | **deferred-P4** |
| C2 | P0 | `loop.md.j2` `worktree create` never passes `--claude-session-id` → marker header always empty → Stop-hook content match never fires | cr#1, cr#2, concurrency, codex | **deferred-P4** |
| C3 | P1 | `loop.md.j2` touches global `.hm-loop-active` **unconditionally** → original cross-session block reachable on the DEFAULT path via the Stop-hook fallback | cr#1, cr#2, concurrency | **deferred-P4** |

> These P0/P1 are about **files NOT in the reviewed diff** (`loop.md.j2`,
> `hooks.json.j2`) — i.e. the **deferred P4 wiring**, not a defect in the shipped
> P1-P3 code. The reviewers correctly assessed end-to-end function: the new
> mechanism is exercised only by unit tests, never by the shipped loop driver.
> Coupling note: making the global touch conditional (C3) **requires** the
> loop-mode detection templates (`plan.md.j2` + 2 partials) to switch to the
> session-scoped signal in the same change, or session A's own loop stages lose
> loop-mode detection — so the fix is the whole P4 phase, not a localized patch.

## 📝 Manual-Only Findings (applied / accepted)

| # | Sev | Finding | Disposition |
|---|-----|---------|-------------|
| M1 | P2 | `_marker_referenced_paths` reimplemented the path rule inline | **APPLIED** — now reuses `parse_marker_paths` (one rule for all 4 readers) |
| M2 | P2 | `test_other_session_marker_allows` omits the global, so it tests the post-P4 normal-path state, not the current driver | Accept — forward-correct (post-P4 normal path writes no global); render-boundary test to be added in P4 |
| M3 | P2 | `sessionid_envfile._rewrite_env_file` strips blank lines from the env file | Accept — inert for `KEY=value` sourcing |
| M4 | P1 | No render/boundary test binds the hook to `hooks.json` or the flag to `loop.md.j2` (CLAUDE.md §8) | **Adopt in P4** — render-assert `sessionid_envfile` registered + `--claude-session-id` present |

## Iteration 2 — P4 wiring landed (resolves C1/C2/C3)

The consensus blockers were the missing P4 wiring. P4 was implemented in the same
session and resolves all three, each locked by a render-boundary test (the
units-pass/wiring-dead gap the review caught — CLAUDE.md §8):

| # | Finding | Resolution | Test |
|---|---------|------------|------|
| C1 | hook not registered | `hooks.json.j2` (+codex) register `sessionid_envfile` on SessionStart | `test_loop_marker_wiring_render::test_sessionstart_hook_registered` |
| C2 | `--claude-session-id` not passed | `loop.md.j2` `worktree create` passes it from `$HM_SESSION_ID` | `test_loop_create_passes_claude_session_id` |
| C3 | unconditional global touch | global touch now guarded by `[ -z "$HM_SESSION_ID" ]` (degraded only) | `test_loop_global_marker_is_conditional` |
| bug-2 | loop-mode false-positive | `plan.md.j2` + 2 partials detect via `worktree loop-mode-active --claude-session-id` | `test_plan_loop_mode_detection_is_session_scoped` |

**Design lock:** ONLY `loop.md.j2` passes `--claude-session-id`, so a standalone
`/hm:execute` worktree (empty content header) never trips the Stop-hook — only
loops do. Shared `loop_marker.marker_dir_has_session` backs both the Stop-hook and
the `loop-mode-active` CLI (one content-match rule). SPEC-loop-gate AC-001 updated.

**Verification:** full unit + snapshot suite exit 0; ruff clean; mypy --strict 111
files clean; 8 snapshots regenerated (from main root — no path contamination).

## Iteration 3 — fresh k-of-3 re-review of full P1-P4 (code×2 + concurrency + Codex)

**No P0/P1 from any of the 4 voters.** All reviewers confirmed the feature is
correctly wired and functional end-to-end on the normal path; bug-2 fixed;
loop-vs-standalone-execute distinction sound; 4 marker readers header-safe;
sanitize symmetric; CLI/template/detection-enforcement consistent. Findings were
all P2/P3 edge/ergonomics/test-quality — applied below.

| # | Sev | Finding (voters) | Resolution |
|---|-----|------------------|------------|
| R1 | P2 | `loop-mode-active`/Stop-hook honored the session-blind global *unconditionally* → a valid-id session B false-positived on session A's degraded global (cr#1, concurrency, Codex) | **Fixed**: global honored ONLY when caller has no id (`not sid`). Valid-id sessions use content-match exclusively → never blocked/loop-detected by a foreign global. **Supersedes first-review H2** (a degraded loop whose Stop payload carries an id loses its own global guard — accepted: parallel-safety > degraded self-guard). Tests updated. |
| R2 | P2 | codex loop `create execute $(pwd)` unquoted → breaks on space paths (cr#1, Codex) | **Fixed**: quoted `"$(pwd)"` to match siblings. |
| R3 | P2 | trailing `--claude-session-id` no-value silently drops (cr#2, Codex) | **Fixed**: usage error (exit 2) in both `_cli_create` + `_cli_loop_mode_active`; test added. |
| R4 | P2 | wiring test near-tautological (cr#1, cr#2) | **Fixed**: asserts the exact guard literal + no-unguarded-touch scan. |
| R5 | P2 | no e2e "standalone execute stays unscoped" test (cr#2) | **Added** `test_standalone_create_stays_unscoped` + `test_loop_create_is_session_scoped`. |
| R6 | P3 | machine.yaml AC-001 `test_ids` empty / `pending_test:true` (cr#1) | **Fixed**: populated test_ids, `pending_test:false`. |
| R7 | P2 | degraded two-BOTH-id-less loops share the global (concurrency, Codex) | **Accepted** (ADR-003) — structurally unavoidable without a per-session key; strictly better than pre-feature (bug-2 gone on the normal path); degraded warning is loud. |
| R8 | P3 | `<WT>` literal-substitution fidelity in the degraded guard (concurrency, cr#1) | **Accepted** — same prompt-fidelity risk `<WT>` carries everywhere; guard logic verified correct for all 4 cases. |

**Verification:** affected tests + full unit + snapshot suite green; ruff clean;
mypy --strict clean; snapshots regenerated from main root.

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | D     | M1 (DRY)      | C1,C2,C3 (P4 wiring) | — |
| 2 (P4)    | A*    | C1,C2,C3,bug-2 + 9 tests | P5(health)+P6(integration test) | — |
| 3 (re-review) | **A** | R1–R6 + 4 tests | P5(health)+P6(integration), R7/R8 accepted | 0 |

Final grade: **A** (iteration 3 fresh k-of-3 re-review: no P0/P1 from any voter;
all P2/P3 findings fixed or accepted-with-rationale). Status: **APPROVED** for the
implemented scope (P1-P4). P5 (CLAUDE.md + `/hm:health` loud smoke) + P6
(parallel-session integration test) remain as non-blocking hardening.
Codex second opinion: **invoked** both review rounds (exit 0).
human_review_needed: **false**.
