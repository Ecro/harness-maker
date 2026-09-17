---
type: review
task_slug: outcome-measure
status: APPROVED
created: 2026-09-17
reviewers_invoked: [code-reviewer (design+functionality+robustness+consistency), security-reviewer, concurrency-reviewer, test-reviewer, codex]
consensus_method: cross-check
run_id: decaaceffd9e
review_base: 2fd69df7d203bd41b5d02dd91e032649273780a6
drift_verdict:
  result: scope_violation
  scope_violations: [tests/unit/test_render_wrapup_delegation.py, tests/structural/test_instruction_preservation.py, tests/structural/test_objective_gap_proposal_invariance.py]
  scenario_misses: []
  task_slug: outcome-measure
  computed_at: 2026-09-17T00:00:00Z
second_opinion_results:
  - model: codex
    status: invoked
    reason: null
human_review_needed: false
final_grade: A
---

# REVIEW — outcome-measure (2026-09-17)

## 🎯 Round 1 Summary

Grade **C** — 0 P0 · 5 P1 · 2 P2 · 2 P3, all `consensus-passed` (one lens votes alone, ADR-007;
codex joined three of the P1s as a cross-model voice after PIDA accepted all 3 of its findings).
Lens coverage 7/7, `blocks_approval: false`. `human_review_needed: false`. Auto-fix enters
round 2 on the five P1s; the P2/P3 stay in the report for the human sweep (grade is C, not D/F).

## 🔍 Drift Findings (Step 2)

`result: scope_violation` (P1, informational — not a reviewer finding, never a grade input):
three test files changed that no PLAN phase names explicitly. All three are ratchet
consequences of the Phase 3 wrapup edit, not new behaviour: the wrapup body-line pin
(`test_render_wrapup_delegation.py` 702/735 → 709/742), the instruction-preservation allowlist
for the 5.7 heading rename (`test_instruction_preservation.py`), and the prior task's retirement
test learning to skip once a later task owns the baseline aggregate
(`test_objective_gap_proposal_invariance.py`). No incomplete phase: every Phase 0–5 scope file
changed. No SPEC scenario without coverage (S1–S8 → AC-001…008 tests exist).

## ✅ Consensus Findings (round 1)

| id | Sev | Lens voices | Summary | Disposition |
|---|---|---|---|---|
| 40a36af2 | P1 | concurrency, consistency | `_append_value` read-modify-writes outcomes.yaml with no lock — pre-existing in `record_value`, exposure widened by `measure --all` at wrapup | accepted → fix r2 |
| 1b9bdc41 | P1 | concurrency, robustness | `TimeoutExpired` kills the direct child only; grandchildren of `measure.cmd` outlive `timeout_s` | accepted → fix r2 |
| c55b8855 | P1 | security, consistency, **codex** | select-failure `WorldError` messages embed raw stdout (`value!r`, `m.group(1)!r`, path segment) — bypasses the stderr redaction (ADR-004) | accepted → fix r2 |
| 58012515 | P1 | robustness, security, tests, **codex** | regex optional group → `float(None)` `TypeError` escapes `measure_all` (crashes the batch) | accepted → fix r2 |
| 3836a55b | P1 | robustness, tests, **codex** | huge JSON int → `OverflowError` in `math.isfinite`, escapes `measure_all` | accepted → fix r2 |
| efaf6ef2 | P2 | tests, design | json list-index bounds (valid negative / out-of-range) untested | accepted (carried) |
| 9c349bfb | P2 | design | `measure_all` reloads intent.yaml per outcome via `measure_outcome` | accepted (carried) |
| 09f5a4d4 | P3 | consistency, security | evidence `cwd=` records the declared label, not the resolved path (git-absent fallback) | accepted (carried) |
| 87a7f5d8 | P3 | tests | `_short_sha` `nogit` fallback unasserted | accepted (carried) |
| 982afe3d | P1 | security | skill "measure first" runs `--dry-run` without a per-run human gate | **rejected — AC-007**: the SPEC mandates the dry-run call inside the "Proposing objectives" step, which itself runs only when the operator asks for proposals; the wrapup 5.7 block is answer-gated. `cmd` is a versioned, human-authored string (trust class = `harness.yaml toolchains`, RESEARCH pitfall 2). |

## ⚠️ Weak Consensus

None.

## 📝 Manual-Only Findings

None.

## 🤝 Disagreements

- efaf6ef2 (json index bounds untested): core lens argued P1 ("newly-added Tier-1 code"), the
  owning tests lens kept P2. Recorded at P2; both takes kept.
- 09f5a4d4 (evidence cwd label): consistency P2, security downgraded to P3 (narrow trigger,
  no decision reads it). Recorded at P3.
- Pass 1 concurrency P1 "cwd:base measure commands race at the shared base" was DROPPED in
  Pass 2 by both concurrency and core: ADR-006 assigns the measured command's side effects to
  the command; a blanket base-root mutex around arbitrary argv would serialize unrelated
  commands and hold a harness lock across an operator-set timeout.

## 🧊 Cross-model findings (frozen @ round 1)

Model `codex`, status `invoked` (28.7 s), 3 findings; PIDA (code-verifier mode B, oracle =
toolchain checks + four verbatim reproductions against `world.select_number`): 3 `accepted`,
0 rejected, 0 duplicate, 0 unresolved. Ledger rows recorded via `--record-disposition`.

| id | sev | file:line | summary | disposition | lifecycle | oracle_result |
|---|---|---|---|---|---|---|
| 56197cdd156b02ba | P2 | world.py:1006 | regex optional capture → `TypeError`, aborts `--all` | accepted (voter on 58012515) | pending | repro: `select_number('none','regex:(1)?none')` → TypeError |
| 841b252a077dfffb | P1 | world.py:974 | selector failures expose unredacted, unbounded stdout | accepted (voter on c55b8855) | pending | repro: `json:v` on `{"v":"token=super-secret"}` → message carries the value |
| fe5fe84c32f2fa45 | P2 | world.py:973 | 400-digit JSON int → `OverflowError` at `math.isfinite` | accepted (voter on 3836a55b) | pending | repro: OverflowError, not WorldError |

### Iteration 2 (Grade: C → A)
Fixes applied: 5 (+3 regression tests). caused_by=none for all (round-1 originals). Verify: ruff / format / mypy strict / 1 215 targeted tests green.
| # | Severity | Summary | File | Status |
|---|----------|---------|------|--------|
| 1 | P1 | 40a36af2 `_append_value` read-modify-write unlocked | src/harness_maker/world.py | Applied — `_rmw_lock` (flock on `outcomes.yaml.lock`, 30 s, unlockable FS → proceed) · caused_by=none |
| 2 | P1 | 1b9bdc41 timeout kills the direct child only | src/harness_maker/world.py | Applied — `Popen(start_new_session=True)` + `communicate(timeout)` + `os.killpg(SIGKILL)`; test `test_ac_003_timeout_kills_the_whole_process_group` · caused_by=none |
| 3 | P1 | c55b8855 select-failure messages carry raw stdout | src/harness_maker/world.py | Applied — messages carry `_shape()` (type + length) only; test `test_ac_002_select_failure_message_is_redacted_and_bounded` · caused_by=none |
| 4 | P1 | 58012515 regex optional group → TypeError | src/harness_maker/world.py | Applied — `captured is None` → `WorldError("select")`; refusal row `("abc","regex:(\d+)?abc")` · caused_by=none |
| 5 | P1 | 3836a55b huge JSON int → OverflowError | src/harness_maker/world.py | Applied — ints skip `isfinite`; beyond float range → `WorldError("select")`; refusal row (400-digit int) · caused_by=none |

Remaining: 4 (P2 ×2, P3 ×2, carried for the human sweep) | New issues introduced: 0
Churn: 0.154 (max: tests/unit/test_world_outcome_measure.py, measured 2, excluded 0) — re-review: skipped — `churn 0.15 < 0.30` (review_consensus plan)
Progress: 5 lifecycle transitions pending → resolved.

## Confirmation pass 1 (confirm-1, frozen @ 31ead265) — dirty

Span: this task's base `6ef0bcf9..31ead265` (the stored `review_base` 2fd69df7 is `origin/main`;
6ef0bcf9 is the already-reviewed, unpushed `objective-gap-proposal` land, so the pass diffed
this task's own whole review rather than re-reviewing a landed commit — recorded as a deviation).
Coverage 7/7, `blocks_approval: false`. New consensus-passed findings (not among the round-1
ids), all raised against the round-2 fixes:

| Sev | Lens | Summary | Repair |
|---|---|---|---|
| P1 | tests | `_rmw_lock` has zero test coverage — no two-writer test | `test_concurrent_writers_never_lose_a_row` (8 parallel `outcome record` CLIs → 8 rows) |
| P1 | concurrency | unguarded `proc.kill()` fallback can raise `ProcessLookupError` past `measure_all` | both kills under `contextlib.suppress(OSError)` |
| P1 | robustness (core) | lock file created in the tracked `.claude/world/` dir — untracked dirt, not harness churn | lock moved to `.claude/observability/.hm-world-outcomes.lock` (already gitignored + churn-classified); test asserts no `*.lock` under `.claude/world` and clean `git status` there |
| P2 | concurrency + core | Popen pipes never closed on the timeout path | `with subprocess.Popen(...) as proc:` (deterministic close) — folded into the P1 repair since it is the same block |
| P2 | design | `SELECT_PREFIXES` declared, never read | carried |
| P2 | design | `_MEASURE_STATUSES` has no caller | deleted (one line, same file as the repair) |
| P3 | tests | grandchild test `timeout_s=1` is tight on loaded runners | `timeout_s=3` |

One repair round (separately budgeted, `iteration_count` unchanged) → confirm-2.

## Confirmation pass 2 (confirm-2, frozen @ 349cc9ee) — clean

Span `6ef0bcf9..349cc9ee` (same deviation as confirm-1). Coverage 7/7, `blocks_approval: false`.
New consensus-passed P0/P1: **0**. Cross-model set re-read, not re-invoked. Non-severe residue
(carried for the human sweep, never a grade input):

| Sev | Lens | Summary |
|---|---|---|
| P2 | security | `os.open` of the lock file is unguarded: a foreign-owned 0o600 lock (shared multi-user checkout) raises an uncaught `PermissionError` instead of a `WorldError("lock")` |
| P2 | security | `suppress(OSError)` around `killpg`/`kill` also hides `PermissionError` before an untimed `proc.wait()` — concurrency lens disagrees: our child runs in its own session under our uid, so EPERM is unreachable for this code path |
| P2 | tests | `test_concurrent_writers_never_lose_a_row` is a probabilistic oracle (8 interpreters must overlap in the RMW window); a barrier-driven in-process variant would be deterministic |
| P3 | tests | its `git status` assertion is pathspec-restricted to `.claude/world`; the "already gitignored" wording in the `_rmw_lock` comment is not what the test checks |

Freeze refs reaped. Run `decaaceffd9e` closed `APPROVED`.

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | C     | —             | 10        | —   |
| 2         | A     | 5             | 5 (P2 ×2, P3 ×2, rejected ×1) | 0 |
| confirm-1 | (A)   | — (repair round: 4 + 1 P3)  | 3 new P1 → repaired | 3 |
| confirm-2 | A     | —             | P2 ×3, P3 ×1 residue | 0 severe |

Final grade: **A**
Iterations used: 2 / 3 (+ one separately budgeted repair round between the confirmation passes)
Exit reason: converged

## 📏 Size & Complexity

| File | LOC | Cyclomatic | Max nesting | Status |
|------|-----|------------|-------------|--------|
| src/harness_maker/world.py | 1561 → 1631 (round 2) | 301 → 311 | 5 → 5 | measured |
| tests/unit/test_world_outcome_measure.py | 308 → 364 (round 2) | 55 → 67 | 3 → 3 | measured |

(5c rows are from round 2; the confirmation repair round was not churn-measured — it is budgeted
outside the iteration loop.)

Status: **APPROVED**
human_review_needed: **false**
Counters (see §5): unreviewed 5 (round-2 re-review skipped at churn 0.15; all five were then swept by both confirmation passes) · prior-fix 0 · unattributed 0

## 🔁 Oscillation

None (`review_churn oscillation --rounds 2` → `[]`).

## Carried for the human sweep (never grade inputs)

- efaf6ef2 P2 — json list-index bounds (valid negative / out-of-range) untested.
- 9c349bfb P2 — `measure_all` reloads `intent.yaml` per outcome via `measure_outcome`.
- `SELECT_PREFIXES` (intent.py) declared, never read — P2 design.
- 09f5a4d4 P3 — evidence `cwd=` label vs resolved path on the git-absent fallback.
- 87a7f5d8 P3 — `_short_sha` `nogit` fallback unasserted.
- confirm-2 residue above (lock `os.open` guard, kill `PermissionError` split, deterministic
  two-writer oracle, test docstring wording).
- Deviation to record: the confirmation passes diffed `6ef0bcf9..<freeze>` rather than the stored
  `review_base` (`2fd69df7`, `origin/main`), because `6ef0bcf9` is the already-reviewed, unpushed
  `objective-gap-proposal` land; `freeze resolve-base` picks `origin/main` whenever the base
  commit is unpushed — worth a follow-up so `review_base` is the task branch's fork point.
