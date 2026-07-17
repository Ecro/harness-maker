---
type: review
task_slug: human-bottleneck-auto-advance
status: APPROVED
created: 2026-06-20
phase: 6
reviewers_invoked: [code-reviewer, code-reviewer, codex]
consensus_method: k-of-3 (2 Claude cross-check + Codex heterogeneous voter)
rounds: 2
drift_verdict:
  result: clean
  scope_violations: []
  scenario_misses: []
  task_slug: human-bottleneck-auto-advance
  computed_at: 2026-06-20T00:00:00Z
---

# REVIEW — P6 stage-terminal conditional advance (live auto-advance)

## 🎯 Round 1 Summary

**Round-1 grade: B** (1 consensus-passed P1) → auto-fix loop → **Round-2 grade: A** (APPROVED).

Diff: boundary CLI (`autopilot_caps.main` + `next_stage`) + `autopilot_ledger.count_events`
+ the auto-advance prose block in `stage_end_summary` partial + 7 stage gate vars +
session-start picker in `step_manifest` + cross-IDE `is_codex` gating + 2 test files + 8
regenerated snapshots. This is the phase where live auto-advance turns ON, so it drew
heavy scrutiny (2 Claude reviewers + Codex).

## 🔍 Drift Findings

`drift_verdict: clean`. All files map to PLAN P6 scope (boundary CLI + templates + picker
+ cross-IDE + tests + snapshots). `autopilot_ledger.count_events` is the read-side P6
needs (P7 still owns the `advanced`/`gate_blocked` write call-sites + /hm:health).

## ✅ Consensus Findings (k-of-3) — all FIXED in round 2

| Sev | File | Finding | Voters | Fix |
|-----|------|---------|--------|-----|
| **P1** | autopilot_caps.py / partial | **CLI recorded `advanced` BEFORE the LLM evaluated the mandatory gate** → a gate-pending stage (review CHANGES_REQUESTED, etc.) logs a phantom advance; retry after the gate clears double-counts → step_cap fires early on STOPs, not just advances | Codex + reviewer-B (reviewer-A dissented "benign over-count") | **Reordered the prose**: Step 1 evaluates the mandatory gate FIRST (absent-case=STOP, no CLI call); Step 2 runs the boundary CLI (which records the advance) ONLY when the gate is clear. The advance is now recorded only when the stage truly advances. |
| **P2** | autopilot_caps.py:165 | unknown `--current` (typo / stage outside the pipeline) → `next_stage` None → treated as completion → marker CLEARED + falsely reports `pipeline_complete: true` | Codex + reviewer-A + reviewer-B (all 3) | **Distinguish** unknown-stage from last-stage: `args.current not in marker.pipeline` → `halt_kind: "unknown_stage"`, **marker preserved**, no false completion. (Also fixed a str-enum bug found while implementing: `str(AtomicStage.X)` yields the enum repr, not the value — membership now uses the str-enum directly.) |

## 📝 Manual-Only Findings (single-source) — applied per precedent

| # | Src | Sev | Finding | Disposition |
|---|-----|-----|---------|-------------|
| 1 | reviewer-B | **P1** | `full` autonomy level never bypasses gates — the model docstring promised `full ~= /hm:loop` (no gate stops) but the partial honors gates unconditionally → code/doc divergence | **APPLIED (doc fix)** — corrected the `AutonomyConfig` docstring: the mandatory safety gates are non-negotiable at every level (a `full` session must never auto-push / skip CHANGES_REQUESTED); `full` currently == `auto_safe`, reserved for a future wider-advance policy, NOT a gate-bypass. (Chose doc-fix over letting `full` auto-push — safety.) |
| 2 | reviewer-A | P2 | `count_events` `since`-compare was lexicographic, but marker `created_at` (`isoformat`, microseconds+offset) and ledger ts (`_utc_now_iso`, Z-form) have different shapes → only correct by byte-ordering accident | **APPLIED** — parse BOTH sides to aware UTC datetimes (`_parse_iso`, normalize `Z`) and compare as datetimes. |
| 3 | reviewer-B | P2 | forgotten `summary_stage` → `--current ""` → CLI clears marker (silent session kill), contradicting the partial's "degrades to STOP" claim | **APPLIED** — `summary_stage` is now a REQUIRED bare var (no `default`); a forgotten set fails render loud under StrictUndefined. (The unknown-stage fix above also makes `""` marker-preserving rather than clearing.) |
| 4 | reviewer-B | P2 | Cursor `no-op` for the picker/auto-branch relied on the LLM honoring a prose parenthetical, not a structural gate (Cursor shares the `.claude/commands` file with `is_codex=False`) | **APPLIED** — added an explicit precondition: "If the `Skill` tool is unavailable (any non-Claude-Code IDE such as Cursor) OR no marker is active OR `.hm-loop-active` exists → NO-OP, run nothing." Plus: the default `gated` harness never renders the picker at all. |
| 5 | reviewer-A | P3 | `parse_known_args` silently swallows stray/typo'd flags | **APPLIED** — `parse_args`. |
| 6 | reviewer-B | P2 | test docstring/comment claimed the guard was `{% if not is_codex %}` (stale) + ADR-004 rationale ("Codex render leaves is_codex undefined") factually wrong | **APPLIED** — corrected: Codex prod render passes `is_codex=True` (so `not is_codex` excludes it); the `is defined` clause additionally guards bare/partial renders. |
| 7 | reviewer-A | P2 | no `now` injection seam in `_cmd_boundary` → time-cap path forced onto the live clock | **DEFERRED (accepted)** — the tests arm with the live clock against generous margins (30/60-min vs sub-second jitter); a `--now` seam is a testability nicety, not a correctness defect. Noted for a future refactor. |
| 8 | reviewer-A | P3 | `steps` field semantics differ across outputs (post-advance on proceed vs pre-advance on halt) | **ACCEPTED (documented)** — defensible (proceed reports the new total); cosmetic. |

## 🤝 Disagreements

- **optimistic-advance (the P1 above):** reviewer-A judged it BENIGN (over-count = caps fire
  earlier = fail-safe direction, matching the ADR docstring). Codex + reviewer-B judged it a
  real defect (a *gate-induced* STOP — not a failure — records a phantom advance, and the
  ledger lies "advanced" when it stopped). **Resolved toward the fix**: reviewer-A's analysis
  only covered the *crash-retry* case; the *gate-pending* case (the common review/wrapup path)
  genuinely mis-records. The gate-first reorder eliminates both.

## ⚙️ Verification (round 2, post-fix)

- `uv run pytest tests/unit/test_autopilot_{boundary,caps,template_render}.py` → 41 passed
  (added `test_boundary_unknown_current_preserves_marker`).
- `uv run ruff check` + `ruff format --check` → clean. `uv run mypy --strict src/` → clean (109).
- Full suite → green. 8 manifest snapshots regenerated (prose change).

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | B     | —             | 1 consensus P1 + 1 P2 + manual | — |
| 2         | **A** | 7 (2×P1, 4×P2, 1×P3) | 0 consensus P0/P1 (now-seam P2 + steps P3 deferred) | 0 |

Final grade: **A**
Status: **APPROVED**
human_review_needed: false
