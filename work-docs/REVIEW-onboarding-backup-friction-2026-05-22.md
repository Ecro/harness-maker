---
type: review
task_slug: onboarding-backup-friction
status: APPROVED
created: 2026-05-22
reviewers_invoked: [code-reviewer, security-reviewer, ux-reviewer]
consensus_method: cross-check
drift_verdict:
  result: clean
  scope_violations: []
  scenario_misses: []
  task_slug: onboarding-backup-friction
  computed_at: 2026-05-22T16:30:00Z
auto_fixes_applied: 6
manual_findings: 7
final_grade: A
human_review_needed: false
---

# REVIEW — onboarding-backup-friction (Round 1)

## 🎯 Round 1 Summary

Cumulative review across 6 phases shipped in one `/hm:loop` session (Phase 7 e2e
deferred per `phase_status` frontmatter). Three reviewers invoked (Production
preset; conditional routing skipped performance + concurrency per change
profile — no hot paths, no async/threading).

**Findings: 0 P0, 5 P1 (orchestrator-applied), 9 P2 (4 applied, 5 surfaced
manual-only).**

**Strict consensus filter grade: A**
- `consensus-passed` P0 = 0; `consensus-passed` P1 = 0; weak-consensus + manual-only do NOT lower grade per project rubric.
- Threshold (A) met → Grade Gate STOPs.

**Orchestrator's honest grade: B**
- The strict rubric returns A but 5 single-reviewer P1 findings sit as `manual-only`. With 3 reviewers covering different domains, requiring ≥2/3 to flag the SAME line for consensus-passed status is anti-coverage. Each reviewer surfaces their domain's issues by design; cross-reviewer surface match is rare.
- Orchestrator (this stage's driver) applied the high-impact P1 fixes inline outside the consensus-passed auto-fix loop. After fixes: 5 manual-only P2 remain.

## 🔍 Drift Findings

`drift_verdict: clean`. All 14 modified + 4 new files lie within PLAN phase scope. Phase 7 (`tests/e2e/test_preservation_e2e.py` + manual IDE checklist) explicitly deferred via `phase_status.phase_7_e2e_on_disk: deferred` in PLAN frontmatter — recognized scope deferral, not silent miss.

## ✅ Consensus Findings

No `consensus-passed` findings — zero cross-reviewer surface matches with matching CONCLUDE reasoning.

## ⚠️ Weak Consensus

| Severity | File:line | Finding | Resolution |
|---|---|---|---|
| P1 (majority 2/3 → P1) | `src/harness_maker/render.py:669` | Bare `print(..., file=sys.stderr)` in `_render_hooks_json_merged`. Three reviewers flagged same line with different CONCLUDE angles: code (logging-standard violation + untestable), security (consistency with `typer.echo(err=True)` pattern), ux (silent overwrite invisible to user in slash-command context). Surface match: ✅. Reasoning alignment: ⚠️ different execution risks → weak. | **APPLIED**: replaced both prints with `typer.echo(..., err=True)` — addresses all three angles simultaneously. |

## 📝 Manual-Only Findings (single-reviewer)

### Security-reviewer P1s — APPLIED

| # | File:line | Finding | Status |
|---|---|---|---|
| S1 | `cli.py:544` | `child.is_dir()` follows symlinks → `.backup-evil` symlink to `/home/user/.ssh` passes enumeration filter. | **APPLIED**: added `child.is_symlink() or` to the early-skip condition. |
| S2 | `cli.py:594` | TOCTOU between scan and `shutil.rmtree`: symlink injected after listing, before deletion, follows to arbitrary target. | **APPLIED**: added re-validation immediately before `rmtree` — checks symlink status + that `path.resolve()` stays under `root.resolve()`. WARN+skip on violation. |

### Code-reviewer P1 — APPLIED

| # | File | Finding | Status |
|---|---|---|---|
| C1 | `tests/unit/test_render.py` | Missing end-to-end test for the Phase 1+3 exit criterion "manifest records merged hash → sweep_orphans sees ours-clean". `_merge_hooks_json` unit tests cover the helper in isolation; integration boundary uncovered. | **APPLIED**: added `test_render_hooks_json_merged_manifest_records_merged_hash` exercising the full render → manifest → sweep_orphans path. |

### Ux-reviewer P1s — APPLIED

| # | File:line | Finding | Status |
|---|---|---|---|
| U1 | `cli.py:526` | `--help` text leaks `[wiki:gotcha] worktree-finalize-untracked-loss` internal tag to users running `harness-maker prune-backups --help`. | **APPLIED**: rewrote the docstring with plain-English rationale ("Backup snapshots may contain state not yet committed to git, so silent auto-deletion has caused unrecoverable loss in practice"). |
| U2 | `cli.py:584` | "Read-only audit (no files removed)" footer gated inside `if candidates:` — suppressed when zero candidates, leaving users unable to distinguish "scan found nothing" from "silent error". | **APPLIED**: moved footer outside the `if candidates:` guard — always printed when `--apply` is absent. |

### Code/Ux/Security P2s — partial fix

| # | File:line | Finding | Status |
|---|---|---|---|
| C2 | `cli.py:648` | `_human_bytes` trailing `return` is dead code (unreachable; the `"GB"` branch unconditionally returns). | **APPLIED**: replaced with `raise AssertionError(...)` so a future loop-guard regression is caught loudly. |
| U3 | `cli.py:622` | `--apply` success line doesn't report total bytes freed. | **APPLIED**: track `freed_bytes` during loop; final echo includes `freed {_human_bytes(...)}`. |
| U4 | `commands/make.md:203` | `(read-only by default; user-gated per ADR-005)` exposes internal ADR jargon to users. | **APPLIED**: replaced with `(read-only by default; pass --apply to actually delete)`. |
| U5 | `docs/reference/preservation-matrix.md:63` | ADR-003 + ADR-005 cited in matrix body but missing from link reference block at bottom — renders as unlinked literal text. | **APPLIED**: added both link defs. |

### Remaining manual-only (deferred / debate)

| # | Severity | File:line | Finding | Disposition |
|---|---|---|---|---|
| C3 | P2 | `render.py:1030` | `_is_codex_hooks_json` predicate redundant in dispatch (`_is_hooks_json` already matches via `endswith('hooks.json')`). | **DEFERRED**: tightening to allowlist (`fe.path in {"hooks/hooks.json", ".cursor/hooks.json"}`) would change behavior for any future hypothetical path ending in `hooks.json`. Cosmetic, debatable. |
| C4 | P2 | `reconcile.py:244` | `_decide_hash_comment_branch` docstring omits "existing-unreadable → REPLACE" path. | **DEFERRED**: cosmetic; behavior is correct. |
| S3 | P2 | `render.py:267` | `_is_hooks_json` suffix-match too broad. | **DEFERRED**: same as C3. |
| S4 | P2 | `cli.py:362` | `target` (project_root) vs `target_dotclaude` variable-name ambiguity. | **DEFERRED**: cosmetic; comment in `_ensure_gitignore_entry` call site already documents intent. |
| U6 | P2 | `cli.py:583` | Total prune savings in dry-run summary buried in same line as kept/candidates count. | **PARTIAL**: already shown inline; standalone "total" line not added (low impact). |

## 🤝 Disagreements

The `render.py:669` print() case: three reviewers, three different angles. Severity divergence (P1/P2/P1) → majority P1 per Step 4c rubric. All three angles addressed by single `typer.echo(err=True)` fix.

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|---|---|---|---|---|
| 1 (init)  | A (strict) / B (honest) | 9 (1 weak-consensus + 5 manual P1 + 3 manual P2) | 5 manual-only P2 (deferred — cosmetic / debatable) | 0 |

**Final grade:** A (strict) — gate met.
**Iterations used:** 1 / 3
**Status:** APPROVED
**human_review_needed:** false

**Pragmatic note:** Strict consensus rubric returned A on Round 1 because cross-domain reviewers don't surface-match by design. Orchestrator (this stage's driver) applied 9 of 14 findings inline rather than declaring APPROVED with critical security TOCTOU and silent-overwrite WARN paths unaddressed. The 5 deferred items are all cosmetic P2s with clear trade-offs documented above.
