---
type: review
task_slug: intent-layer-ops
status: APPROVED
created: 2026-09-18
reviewers_invoked: [code-reviewer, security-reviewer, concurrency-reviewer, test-reviewer, codex]
consensus_method: cross-check
run_id: ea5d050fcf59
review_base: 974a554a09abaa90300ba49731c977bc771275b2
drift_verdict:
  result: clean
  scope_violations: []
  scenario_misses: []
  task_slug: intent-layer-ops
  computed_at: 2026-09-18T14:20:00Z
---

# REVIEW — intent-layer-ops (2026-09-18)

Diff under review: this task's uncommitted changes vs `HEAD` (43c7ded0) in
`.worktrees/intent-layer-ops`. `review_base` resolved to 974a554a; the range 974a554a..43c7ded0 is
another task's landed commit (source-plan-steps observability payload) and was excluded from the
reviewed diff.

## 🎯 Round 1 Summary

- **Grade B** — one consensus-passed P1 (`55d83755c1e06011`), zero P0.
- Lens coverage: all 7 exercised (`blocks_approval: false`).
- Cross-model: codex `invoked`, 2 findings, both PIDA `accepted` (one `duplicate` of the P1).
- `human_review_needed`: false (no manual-only / weak-consensus P0/P1).
- Fixes pending: 1 (P1). P2/P3 are dispositioned `accepted` and carried for a human sweep —
  at grade B they are not in the auto-fix queue.

## 🔍 Drift Findings

None — `drift_verdict.result: clean`. Every changed path is inside a PLAN phase's scope; the
three SPEC files are the spec-stage deliverables; `.claude/observability/mutation-receipts.jsonl`
is Phase 4's receipt for the new AC-006 gate.

## ✅ Consensus Findings

### P1
- **`55d83755c1e06011`** — `src/harness_maker/world.py:131` `_git_out` catches only
  `OSError`/`TimeoutExpired`; `subprocess.run(text=True)` raises `UnicodeDecodeError` on a
  non-UTF-8 historical `intent.yaml` blob, so `hm world gap` crashes instead of skipping the blob
  (SPEC S4/AC-004 "exits 0"; ADR-003 "skip that blob"). Lens: robustness. Reproduced.

### P2
- **`b5a2f6f1882fa288`** — `world.py:120` `_INTENT_REL` restates the path `intent_path()` already
  encodes (second source of truth). Lens: consistency.
- **`4be6f597f2fdcf43`** — `world.py:887` `withdrawal_report` reads git history and stage-spans
  after `load_world`, while `gap_report`'s docstring still promises one disk snapshot. Lenses:
  concurrency + consistency (`73987ba56ac54af8` is the same defect, marked `duplicate`).
- **`d8e4765a26eb5e68`** — `tests/unit/test_world_withdrawal.py:154` no span at exactly
  `filled_at`, so `>` vs `>=` is unpinned. Lens: tests.

### P3
- **`fc31721da2c28a3f`** — AC-004 fixtures never combine two failure reasons, so precedence is
  structural only. Lens: tests.
- **`98e96303ebdfe209`** — `_b_spans_dir` stops at `is_file()`; the `except OSError` branch in
  `_count_wrapups` is executed by no test. Lens: tests.

## ⚠️ Weak Consensus

None.

## 📝 Manual-Only Findings

- **`df0fbcab3bdec029`** (P2, codex, PIDA `accepted`) — `world.py:838` `_blob_is_filled` catches
  `yaml.YAMLError`/`IntentInvalidError` only; PyYAML's timestamp constructor raises `ValueError`
  for an invalid date literal in a historical blob, which escapes and crashes `gap`. Reproduced.
- **`d80f153896de0c51`** (P2, codex, PIDA `accepted`) — the non-UTF-8 crash; `duplicate` of the
  P1 `55d83755c1e06011` (same defect, different tier — tiers are not bridged).

## 🤝 Disagreements

- The non-UTF-8 crash: code-reviewer P1 vs codex P2. Kept as independent findings per Step 4c;
  the P2 is dispositioned `duplicate`.

## 🧊 Cross-model findings (frozen @ round 1)

frozen_at_round: 1
models: [codex]

| id | source | severity | file | line | summary | evidence | needs_relaxation | disposition | oracle_result | status | invalidation_reason |
|---|---|---|---|---|---|---|---|---|---|---|---|
| d80f153896de0c51 | codex | P2 | src/harness_maker/world.py | 825 | non-UTF-8 historical blob crashes `hm world gap --json` | null | false | accepted | world.py:825 _git_out text=True catches only OSError/TimeoutExpired; repro raised UnicodeDecodeError | resolved | — |
| df0fbcab3bdec029 | codex | P2 | src/harness_maker/world.py | 838 | invalid date literal in a historical blob raises ValueError past the skip handler | null | false | accepted | world.py:838 catches only YAMLError/IntentInvalidError; repro raised ValueError month must be in 1..12 | resolved | — |

### Iteration 2 (Grade: B → A)
Fixes applied: 1
Batch trigger fired — arm (a): `55d83755c1e06011`, `d80f153896de0c51`, `df0fbcab3bdec029` share the
historical-blob read path. Per-group block: `group_key` = `world.withdrawal-history-read`;
covered ids as listed; dimensions re-derived = git failure / decode failure / YAML constructor
failure — each must skip the blob, never raise; single consolidated edit = `_git_out` pins
`encoding="utf-8"` and catches `UnicodeDecodeError`, `_blob_is_filled` also catches `ValueError`.

| # | Severity | Summary | File | Status |
|---|----------|---------|------|--------|
| 1 | P1 | `_git_out` UnicodeDecodeError (+ codex ValueError, same group) | src/harness_maker/world.py:818 | Applied · caused_by=none |

Verification: reproduction on a tmp repo (non-UTF-8 blob, impossible-date blob, each followed by
a valid fill) now returns the valid fill commit for both; 63 targeted tests green; ruff/mypy clean.
Lifecycle: `55d83755c1e06011`, `d80f153896de0c51`, `df0fbcab3bdec029` pending → resolved.
Re-review: skipped — churn 0.01 < 0.30 (no dispatch).
Remaining: 5 (P2 ×3, P3 ×2 — not auto-fix eligible at grade B/A) | New issues introduced: 0
Churn: 0.0074 (max: src/harness_maker/world.py, measured 1, excluded 0)
Note: no regression test was added in-loop (the loop may not edit a test to resolve a finding
whose target is not that test). The newly reachable window — a historical blob that is not
UTF-8 or carries an impossible YAML date — is covered only by the reproduction above; carried as
a follow-up for a test at wrapup or a later task.

## ✅ Confirmation Pass (confirm-1)

Frozen at `52237373` (`refs/hm-freeze/v1/intent-layer-ops-confirm-1`, reaped after the pass),
diff span `974a554a..52237373`. All 7 lenses exercised (`blocks_approval: false`). New findings: one
P3 (tests — AC-004 forces only `FileNotFoundError` of the three `no_git` exception types;
`TimeoutExpired` / `PermissionError` builders missing). **Zero new consensus-passed P0/P1 →
APPROVED.** Cross-model voters were re-read from the frozen section, not re-invoked.

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | B     | —             | 9         | —   |
| 2         | A     | 1             | 5         | 0   |
| confirm-1 | A     | —             | 6         | 1 (P3) |

Final grade: A
Iterations used: 2 / 3
Exit reason: converged

## 📏 Size & Complexity

| File | LOC | Cyclomatic | Max nesting | Status |
|------|-----|------------|-------------|--------|
| src/harness_maker/world.py | 1743 → 1750 | 334 → 334 | 5 → 5 | measured |

Status: APPROVED
human_review_needed: false
Counters (see §5): unreviewed 1 · prior-fix 0 · unattributed 0

### Carried for a human sweep (accepted, not auto-fix eligible at grade A)

- P2 `b5a2f6f1882fa288` — derive `_INTENT_REL` from `intent_path()`.
- P2 `4be6f597f2fdcf43` — scope `gap_report`'s one-snapshot docstring; name `withdrawal` as the exception.
- P2 `d8e4765a26eb5e68` — add a wrapup `start` span at exactly `filled_at` to AC-002.
- P3 `fc31721da2c28a3f` — one combined-failure fixture pinning reason precedence.
- P3 `98e96303ebdfe209` — exercise `_count_wrapups`' `except OSError` branch.
- P3 (confirm-1) — `TimeoutExpired` / `PermissionError` `no_git` builders.
- Follow-up — a regression test for the round-2 fix (non-UTF-8 / impossible-date historical blob).
