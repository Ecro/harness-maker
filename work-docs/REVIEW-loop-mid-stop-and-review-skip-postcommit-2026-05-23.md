---
type: review
task_slug: loop-mid-stop-and-review-skip
phase: post-commit
status: CHANGES_REQUESTED
created: 2026-05-23
commit_under_review: 63eea38
reviewers_invoked: [code-reviewer, security-reviewer, concurrency-reviewer, ux-reviewer]
consensus_method: cross-check
drift_verdict:
  result: clean
  scope_violations: []
  scenario_misses: []
  task_slug: loop-mid-stop-and-review-skip
  computed_at: "2026-05-23T22:00:00Z"
human_review_needed: true
---

# 🎯 Round 1 Summary

**Diff under review:** commit `63eea38` (pushed to `origin/main`), 29 files, +1597/-168.

**Reviewers:** 4 in parallel — `code-reviewer`, `security-reviewer`, `concurrency-reviewer`, `ux-reviewer`. Per-reviewer grades: C / B / C / B.

**Strict rubric grade: A (trivial)** — zero `consensus-passed` findings because each reviewer surfaced different categories (architecture / security / concurrency / UX) that almost never cluster on the same `(file, line, severity-tier)`. The two surface-matches that did occur (`execute.md.j2:238`) span different severity tiers (P1 concurrency vs P2 code), and Step 4a forbids tier-bridging.

**Actual grade: D-equivalent** based on findings impact. 3 P0s + 10 P1s + 8 P2s, all tagged `manual-only` per strict rubric. **This is the same anti-coverage failure the just-shipped Gate 0 mechanism cannot mitigate by itself** — the rubric needs improvement (separate follow-up).

# 🔍 Drift Findings

None. All 29 changed files match PLAN Phase 1-4 scope.

# ✅ Consensus Findings (`consensus-passed`)

**None.** No surface-match + reasoning-alignment pairs survived Step 4 filter.

# ⚠️ Weak Consensus

None at the strict level. Notable near-miss: 4 reviewers independently flagged different problems clustered around `loop.md.j2:722-733` (Option B escape hatch) — code-reviewer didn't see Option B specifically, but security-reviewer + ux-reviewer + concurrency-reviewer all surfaced separate issues with that block. Rubric records them as 3 independent manual-only findings; in practice they form a "weak architectural consensus" that **Option B as currently written is the weakest part of this commit**.

# 📝 Manual-Only Findings

## P0 (3 findings — verified)

### P0 #1 — `verify.md.j2` missing Gate 0 receipt-emit block; Production default loops will infinitely retry

**File:** `src/harness_maker/templates/stages/verify.md.j2` (entire file).
**Source:** code-reviewer.
**Verification:** `grep -c "Emit Gate 0 receipt" src/harness_maker/templates/stages/verify.md.j2` = `0`. `interview.py:94` declares `_PRODUCTION_DEFAULT = "exec-rev-wrap-ver"`. `loop.md.j2:679` declares `exec-rev-wrap-ver → execute,review,wrapup,verify` in EXPECTED_STAGES.

**Reasoning:**
- OBSERVE: Phase 2 added receipt-emit blocks to 6 stage templates (execute, review, wrapup, plan, spec, research). `verify.md.j2` was not in that set. Phase 3 EXPECTED_STAGES table requires `verify` for the production default workflow.
- INFER: Any production-preset user running default `exec-rev-wrap-ver` (or explicitly passing it via `--per-iter-workflow`) writes execute+review+wrapup receipts but NO verify receipt. Gate 0 verify CLI exits 1 every iter ("missing: verify"). Auto-retry cap=2 → escalation → user picks one of A/B/C → next iter same situation → infinite loop on the escalation prompt.
- CONCLUDE: **P0**. The commit ships Gate 0 mechanism but makes the PRODUCTION default workflow unusable. Test suite has the same gap: `test_render_stage_receipts.py:45 STAGE_NAMES` excludes `verify`, so CI never caught it.

**Fix:** Add the same shell-guarded receipt-emit block to `verify.md.j2` (before its `## Output` section — note singular, vs other stages' `## Outputs`). Add `"verify"` to `STAGE_NAMES` in `test_render_stage_receipts.py`.

---

### P0 #2 — `LoopContext(extra="forbid")` blocks `/compact` recovery once runtime block lands on disk

**File:** `src/harness_maker/autoloop_driver.py:103-117` (`LoopContext` class).
**Source:** concurrency-reviewer.
**Verification:** Confirmed at line 110: `model_config = ConfigDict(strict=True, extra="forbid")`. No `runtime` field declared. `loop.md.j2:390-397` instructs LLM driver to persist `runtime:` block to the same YAML file.

**Reasoning:**
- OBSERVE: `LoopContext` has `extra="forbid"` strict pydantic config. `loop.md.j2` Step 4-F documents the YAML schema as having both `context:` (a declared field) AND `runtime:` (an undeclared top-level key).
- INFER: After any Gate 0 retry where the driver persists `stage_retry_counts`, the YAML file contains `runtime:`. The next `parse_loop_context` call (post-`/compact` recovery in `loop.md.j2:502-508`) does `LoopContext.model_validate(data)` → raises `ValidationError: Extra inputs are not permitted [runtime]`.
- CONCLUDE: **P0**. /compact recovery — a core invariant of the Gate 0 mechanism (and of the entire autoloop) — is permanently broken once a single Gate 0 retry persists. The longer the loop, the more guaranteed the break.

**Fix:** Add `runtime: RuntimeBlock | None = None` to `LoopContext` with a new `RuntimeBlock` model (or change to `extra="ignore"` for LoopContext only). Add a regression test that round-trips a YAML with runtime block.

---

### P0 #3 — Option B (`verdict: skipped` escape hatch) CLI command will fail with `ModuleNotFoundError` in every user project

**File:** `src/harness_maker/templates/commands/hm/loop.md.j2:729`.
**Source:** ux-reviewer.
**Verification:** Line 729 reads `uv run python -m harness_maker.iter_receipts write --iter <N> --stage <stage> --verdict skipped --root <WT>`. Every OTHER invocation of the same CLI in the file (lines 691, 695) uses `uv run --with {{ harness_maker_src_path }} python -m harness_maker.iter_receipts ...`.

**Reasoning:**
- OBSERVE: User harnesses inject `harness_maker` via `uv run --with <path>` because `harness_maker` is not on the project's default `uv` environment PATH.
- INFER: When Gate 0 auto-retry cap is exhausted (the exact moment an operator needs the escape hatch most), the operator copies the Option B command verbatim and runs it. `uv run python -m harness_maker.iter_receipts` fails with `ModuleNotFoundError: No module named 'harness_maker'`. Operator has no working escape; loop is stuck at Option C (abort) only.
- CONCLUDE: **P0** by operational impact — Gate 0's documented user-recovery path is broken at the point of greatest need.

**Fix:** Change line 729 to `uv run --with {{ harness_maker_src_path }} python -m harness_maker.iter_receipts write --iter <N> --stage <stage> --verdict skipped --root <WT>`.

## P1 (10 findings)

| # | Source | File:Line | Summary |
|---|--------|-----------|---------|
| 1 | concurrency | `loop.md.j2:648` | `.current-iter` write via `printf > file` not atomic — crash mid-write → empty file → empty `$ITER` → silently dropped receipt on every stage |
| 2 | concurrency | `execute.md.j2:238` (+5 stages) | TOCTOU between `[ -f .current-iter ]` and `$(cat .current-iter)` — concurrent removal yields empty `$ITER` |
| 3 | concurrency | `loop.md.j2:714` | `stage_retry_counts` persistence is prompt-driven plain YAML write — no `atomic_write`, no Python helper, vulnerable to corruption + extra='forbid' clash (P0 #2) |
| 4 | code | `plan.md.j2:101` | `.hm-loop-active` detection prose doesn't specify project-root vs cwd; inside worktree, relative lookup misses → loop-mode never engages → `AskUserQuestion` fires in autoloop body |
| 5 | code | `test_render_stage_receipts.py:45` | `STAGE_NAMES` excludes `verify` (companion to P0 #1) — Phase 2 gap untested |
| 6 | security | `iter_receipts.py:202` | `--written-at` CLI flag exposed publicly; allows backdating receipts → undermines audit-log integrity Gate 0 promises |
| 7 | security | `loop.md.j2:729` | Option B `verdict: skipped` write leaves no durable audit log; `/hm:health` cannot detect systematic skip patterns |
| 8 | ux | `loop.md.j2:733` | "jump to step 5" ambiguous — inner Step 5 (Update state) vs outer Step 5 (Engage worktree). Under context pressure LLM may misroute |
| 9 | ux | `loop.md.j2:726` | Option A label "수동 재실행" hardcoded Korean in English-default template; locale guard missing |
| 10 | ux | `plan.md.j2:126` | ADR-pivot halt mechanism "exit non-zero" impossible for LLM driver; missing receipt-emit step → halt doesn't propagate to Gate 0 → infinite retry |

## P2 (8 findings)

| # | Source | File:Line | Summary |
|---|--------|-----------|---------|
| 1 | code | (multiple stages):receipt block | Shell guard uses unquoted `<WT>` path — spaces in path break the guard (low likelihood — WSL2 user-config paths rarely contain spaces) |
| 2 | code | `.claude/memory/wiki.md:357` | New wiki entry omits that `verify.md.j2` was excluded — should be amended once P0 #1 is fixed or annotated otherwise |
| 3 | security | `iter_receipts.py:96` | `iter_n` interpolated to dir name without range validation; pydantic catches model-construction but direct Python callers bypass |
| 4 | security | `iter_receipts.py:136` | `list_iter` silently skips corrupt receipts (logger.warning only) — masks tampered files as absent rather than raising |
| 5 | ux | `execute.md.j2:251` | Korean dirty-state warning in English-default template — locale guard missing (pre-existing, not from this commit) |
| 6 | ux | `plan.md.j2:90` | Step 1 short-circuit prose buried mid-paragraph; first-time readers miss it. Recommendation: promote to callout |
| 7 | ux | `research.md.j2:285` | Pass criterion "7 sections + discovery lens" reads as 8 conditions; recommendation: separate "all sections" from "lens entry present when --deep set" |
| 8 | ux | `iter_receipts.py:239,273` | CLI error messages strip pydantic detail; FAIL stdout uses `-` as missing-list sentinel — clashes with list comma syntax in operator copy-paste |

# 🤝 Disagreements

Tier-disagreement at `execute.md.j2:238`:
- code-reviewer: **P2** (unquoted `<WT>` path)
- concurrency-reviewer: **P1** (TOCTOU between `[ -f ]` and `$(cat)`)

Both findings are about the same shell guard at the same line. They identify different failure modes (quoting on space path vs TOCTOU on concurrent delete). Strict rubric Step 4c says tier-disagreement uses majority — only 2 reviewers, no majority, so the P2 + P1 stand independently. Documenting here for visibility.

---

## Review Iteration Summary

| Iteration | Grade (strict) | Fixes Applied | Remaining | New |
|-----------|----------------|---------------|-----------|-----|
| 1 (init)  | A (rubric) / D (actual) | — | 3 P0 + 10 P1 + 8 P2 | — |

**Final grade:** A per strict rubric (no consensus-passed findings); **D-equivalent per impact assessment**.
**Iterations used:** 1 / 3 — auto-fix loop did NOT run because `grade_threshold = A` is "met" trivially. **This is the rubric anti-coverage failure mode.**
**Status:** **CHANGES_REQUESTED** (overriding the rubric's APPROVED because 3 verified P0s exist).
**human_review_needed:** true.

---

## Rubric Anti-Coverage Caveat (recurring — 3rd time)

This is the third REVIEW in this PLAN's lifecycle where the strict `cross-check (2/3)` consensus mode returned Grade A trivially despite real defects. Phase 1, Phase 2, Phase 3 reviews each had a single reviewer (manual-only by definition). This post-commit review with 4 reviewers in parallel STILL fell into the same trap because the consensus filter requires `(file, line ± 5, same severity tier)` agreement — but well-orchestrated reviewers naturally specialize in different aspects of the same code and find different defects.

**Pattern:** the rubric's design assumption (multiple reviewers find the SAME defects) is empirically false at this codebase's diff size + reviewer specialization. The PLAN's wiki gotcha already documented this for Phase 1 (single-reviewer manual-only). The 4-reviewer cross-check this round merely scales the gap.

**Follow-up PLAN candidate:** `PLAN-review-consensus-rubric-anti-coverage` — add a "broad-area" consensus mode where any 2 P0/P1 findings within the same FILE (regardless of line/severity tier) escalate to weak-consensus. OR: detect "reviewer specialization mode" and switch from surface-match to category-coverage scoring.

---

## Recommended Action

**Immediate (P0 follow-up commit before any further loop usage on Production preset):**
1. Add receipt-emit block to `verify.md.j2`.
2. Add `runtime: RuntimeBlock | None = None` to `LoopContext` schema (+ regression test).
3. Fix Option B CLI command in `loop.md.j2:729`: add `--with {{ harness_maker_src_path }}`.

**Soon (P1):**
4-7. Address P1 #1-#4 (atomic `.current-iter` write, plan.md loop-mode marker detection, TOCTOU on shell guard, prompt-driven YAML write atomicity).
8-13. Other P1s (audit log, written-at backdating, step-numbering ambiguity, Korean locale leak, ADR halt mechanism).

**Eventually (P2):**
P2 findings + rubric anti-coverage PLAN.

## Notes

- No `git commit` invoked from this review stage. (Verified: `git log` HEAD = `63eea38` unchanged.)
- Telemetry: 4-reviewer round does not fit the 14-field `review_telemetry.py` schema (which is pass1/pass2/verifier specific). Skipped — same recurring caveat.
- All findings have OBSERVE → INFER → CONCLUDE reasoning chains and are file-line addressable.
- 3 P0s verified via direct grep against the committed code, not just reviewer claim.
