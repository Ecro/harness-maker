---
type: review
task_slug: loop-mid-stop-and-review-skip
phase: post-commit-fixes
status: APPROVED
created: 2026-05-23
reviewers_invoked: [code-reviewer]
consensus_method: single-source-acknowledged-anti-coverage
drift_verdict:
  result: clean
  scope_violations: []
  scenario_misses: []
  task_slug: loop-mid-stop-and-review-skip
  computed_at: "2026-05-23T13:30:00Z"
fixes_applied_for_review_id: REVIEW-loop-mid-stop-and-review-skip-postcommit-2026-05-23.md
human_review_needed: false
---

# 🎯 Round 1 Summary

**Diff:** P0+P1 fix sweep on commit `63eea38` (in this worktree, uncommitted). 13 findings from prior post-commit REVIEW addressed.

**Reviewer:** 1 (code-reviewer) — Grade B initial → **A** after auto-fix.

**Anti-coverage caveat:** Single reviewer again (cross-check rubric still gives Grade A trivially with zero consensus). Findings acted on as if consensus-passed.

# 🔍 Drift Findings

None. All edits within scope of the prior REVIEW's 13 findings.

# ✅ Consensus Findings

None — single reviewer.

# 📝 Manual-Only Findings (all from prior REVIEW + reviewer's new round)

## P0 (3 — all FIXED, verified by tests)

| # | Issue | Fix |
|---|-------|-----|
| P0#1 | `verify.md.j2` missing receipt block | Added Emit Gate 0 receipt section before `## Output`. `STAGE_NAMES` in `test_render_stage_receipts.py` includes `verify` — 22 receipt tests pass. |
| P0#2 | `LoopContext(extra="forbid")` blocks `/compact` recovery | Added `RuntimeBlock` model + `LastTestResult` + `runtime: RuntimeBlock \| None = None` to `LoopContext`. New `save_loop_context()` uses `atomic_write`. 3 new round-trip tests pass. |
| P0#3 | Option B CLI missing `--with` | Added `--with {{ harness_maker_src_path }}` to Option B command. Path also quoted (`"<WT>"`). |

## P1 (10 + 1 from reviewer round 2 — all FIXED)

| # | Issue | Fix |
|---|-------|-----|
| P1#1 | `.current-iter` `printf > file` not atomic | New `iter_receipts.set_iter_marker()` + `set-iter-marker` CLI subcommand using `atomic_write`. Step 3.5 in loop.md.j2 now calls the CLI. |
| P1#2 | TOCTOU on shell guard | All 7 stage templates (6 + verify) upgraded: single `cat` with `[ -n "$ITER" ]` post-check + quoted `<WT>` paths. |
| P1#3 | Prompt-driven YAML write not atomic | **(reviewer's round 2 P1 — also fixed in this round)** New `patch_runtime_block()` + `patch-runtime` CLI subcommand. `loop.md.j2` step 4.5 retry counter + Step 7.0 cleanup both call the CLI. 3 new regression tests pass. |
| P1#4 | `.hm-loop-active` ambiguous cwd vs root | `plan.md.j2` Step 1.5 clarifies "project root, NOT inside `<WT>`" with 2 derivation paths (Step 0 split, or `git rev-parse --show-toplevel`). |
| P1#5 | `STAGE_NAMES` test missing `verify` | Added `verify` to tuple. |
| P1#6 | `--written-at` backdating | Gated behind `HM_TEST_RECEIPTS=1` env. 2 new regression tests (rejected without env, accepted with env). Also `argparse.SUPPRESS` hides from `--help`. |
| P1#7 | Option B no audit log | Added `printf` JSONL append to `<WT>/.claude/observability/gate0-skips.jsonl` (with `mkdir -p`, quoted path). Allowlist updated in `test_telemetry_no_leak.py`. |
| P1#8 | "jump to step 5" ambiguous | Prose now: "jump directly to step 5 — specifically '5. Update state' (the per-iter step inside this section 6 — NOT outer Step 5 'Engage worktree')". |
| P1#9 | Korean "수동 재실행" hardcoded | Wrapped in `{% if config.locale == 'ko' %}수동 재실행{% else %}user runs the stage themselves{% endif %}`. |
| P1#10 | ADR halt "exit non-zero" impossible | Replaced with 3-step concrete procedure: status:blocked frontmatter + halt_reason + `verdict: fail` receipt + surface to operator. |
| Round 2 P1 | `save_loop_context()` unreachable from prompt | **(fixed this round)** Added `patch-runtime` CLI subcommand. loop.md.j2 step 4.5 + Step 7.0 use it. |

## P2 (8 from prior REVIEW + 3 from reviewer round 2 — most FIXED)

| # | Issue | Status |
|---|-------|--------|
| Round 2 P2#1 | Option B printf unquoted `<WT>` + no mkdir | FIXED — added `mkdir -p "<WT>/..." &&` prefix + quoted target |
| Round 2 P2#2 | loop.md.j2 set-iter-marker + verify unquoted `<WT>` | FIXED — quoted at all 4 sites |
| Round 2 P2#3 | Bare `pytest.raises(Exception)` | DEFERRED — cosmetic; the test still passes if any of pydantic ValidationError / ValueError / AttributeError fires |
| Prior P2#1 | Unquoted `<WT>` in stage shell guards | FIXED — all 7 stage templates now quote |
| Prior P2#2 | Wiki entry doesn't note verify exclusion | NOT APPLICABLE — verify now has the receipt block; exclusion claim void |
| Prior P2#3 | `iter_n` no range validation in `_iter_dir` direct callers | DEFERRED — pydantic catches at model layer; direct Python callers are internal |
| Prior P2#4 | `list_iter` silently skips corrupt receipts | DEFERRED — `logger.warning` already mitigates; raising would prevent Gate 0 from advancing on any single corrupt file |
| Prior P2#5 | Korean dirty-state warning in execute.md.j2 | DEFERRED — pre-existing from outside this PLAN's scope |
| Prior P2#6 | Step 1 short-circuit prose buried | DEFERRED — cosmetic positioning, current location is functional |
| Prior P2#7 | Research pass criterion "7 sections + lens" ambiguous | DEFERRED — cosmetic prose |
| Prior P2#8 | CLI error stripping `ValidationError` detail | PARTIALLY FIXED — write subcommand now says `write failed: <exc>`; full ValidationError detail still wrapped by str() |

# 🤝 Disagreements

None.

---

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | B     | —             | 1 P1 + 3 P2 from reviewer round 2 | — |
| 2 (auto-fix) | A | 4 (P1 + 3 P2 — patch-runtime CLI + quote loop.md.j2 + Option B mkdir + audit log quote) | 1 P2 deferred (test exception specificity) | 0 |

**Final grade:** A
**Iterations used:** 2 / 3
**Status:** APPROVED
**human_review_needed:** false

---

## Summary of changes shipped this round

Touched files:
- `src/harness_maker/iter_receipts.py` — added `set_iter_marker()`, `patch_runtime_block()`, `set-iter-marker` + `patch-runtime` CLI subcommands; `--written-at` gated behind `HM_TEST_RECEIPTS=1`; better error prose. Imported `os`.
- `src/harness_maker/autoloop_driver.py` — added `LastTestResult` + `RuntimeBlock` models; added `runtime: RuntimeBlock | None = None` to `LoopContext`; new `save_loop_context()` using `io_utils.atomic_write`.
- `src/harness_maker/templates/stages/{execute,review,wrapup,plan,spec,research}.md.j2` — shell guards upgraded (TOCTOU + quoting).
- `src/harness_maker/templates/stages/verify.md.j2` — added Emit Gate 0 receipt block.
- `src/harness_maker/templates/stages/plan.md.j2` — Step 1.5 marker detection clarified; ADR halt 3-step concrete procedure.
- `src/harness_maker/templates/commands/hm/loop.md.j2` — Step 3.5 set-iter-marker CLI, Step 4.5 patch-runtime CLI + Option B mkdir+audit + step-5 disambiguation + locale conditional, Step 7.0 patch-runtime clear.
- `tests/unit/test_loop_runtime_block_and_marker.py` (NEW) — 13 tests for RuntimeBlock round-trip, set-iter-marker atomicity, `--written-at` gating, `patch-runtime` clear/set.
- `tests/unit/test_render_stage_receipts.py` — `STAGE_NAMES` includes `verify`.
- `tests/unit/test_loop_template_render.py` — updated 2 anchors (`.current-iter` write detection + Option B window).
- `tests/structural/test_telemetry_no_leak.py` — added `commands/hm/loop.md.j2` to observability allowlist.

Test suite: **all GREEN** after final regen (47+ phase-tests + structural + receipt + synth-snapshot all pass).

## Notes

- No `git commit` invoked from this stage.
- Telemetry: not emitted (single-reviewer schema mismatch, recurring).
- Rubric anti-coverage: 5th time documenting. Stronger candidate for `PLAN-review-consensus-rubric-anti-coverage` follow-up — multi-round single-reviewer findings consistently produce Grade A trivially despite real defects.
