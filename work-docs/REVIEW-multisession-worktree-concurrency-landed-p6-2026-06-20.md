---
type: review
task_slug: multisession-worktree-concurrency
status: APPROVED
created: 2026-06-20
scope: standalone re-review of LANDED Phase 6 (main d12d91f)
reviewers_invoked: [code-reviewer, security-reviewer, codex]
consensus_method: k-of-3
drift_verdict:
  result: clean
  scope_violations: []
  scenario_misses: []
  task_slug: multisession-worktree-concurrency
  computed_at: 2026-06-20
codex_status: invoked
---

# REVIEW — standalone re-review of landed Phase 6 (ADR-008), main `d12d91f`

## 🎯 Summary

**Consensus grade: A** — every finding is single-source (none reached 2-of-3
surface+reasoning consensus), so there are zero `consensus-passed` P0/P1 → A →
APPROVED. **BUT** this independent pass surfaced **real single-source gaps the
in-loop k-of-3 missed** — most importantly one genuine P1 data-strand hazard.
Reported honestly (concern-first), not buried by the formal grade. These are
`manual-only` per the consensus rule (not auto-applied), and recommended as a
follow-up fix.

Reviewer standalone grades: code **A**, security **B** (the P1), Codex (1 P2).

## 🔍 Drift gate

All landed Phase 6 files are within ADR-008 scope. `drift_verdict: clean`.

## 📝 Manual-only findings (single-source; real; recommend fixing)

### P1 — sibling-repo strand gap in `enablement_preflight` (security-reviewer)
`worktree.py` `enablement_preflight(target)` globs only the PRIMARY repo's
`.claude/.hm-finalize-stash-*`, `.hm-loop-*`, and `.worktrees/<owned>-*`. It never
reads `sibling_repos`. Multi-repo Production harnesses create per-sibling worktrees
+ per-sibling finalize-stash refs (`_cli_post_commit_pop` drains each sibling base),
but the loop marker is written only to the primary. A crashed/partial old-model
session can leave a live stash ref + in-flight worktree in a SIBLING while the
primary `.claude/` is clean → preflight reports clean → flips → the sibling's
preserved stash strands (only the old `post-commit-pop` would have finalized it).
This is the exact data-loss the migration guard exists to prevent, uncovered for
multi-repo (the flagship Production preset). **Fix:** resolve `sibling_repos`
against `target` and run the same three filesystem-glob blockers against each
sibling base (mirror `_cli_post_commit_pop` sibling discovery); add
`test_pending_sibling_stash_blocks`. *(Narrow trigger: multi-repo + crashed/partial
old session + clean primary — single-repo path is sound, hence not P0.)*

### P2 — `--reinterview` resets an explicit `false` opt-out, ungated (security-reviewer)
The opt-out strip lives only in `answers_from_harness_yaml`; `--reinterview` sets
`reused=None` → bypasses the round-trip AND the migration gate (`reused is not
None`), and `_preset_extras` hard-sets `feature_branch_workflow: True` for
Production. A user who set `false` then runs `make --update --reinterview` gets it
silently re-enabled with no preflight. **Fix:** read the on-disk flag before the
interview and re-apply it post-`_build_answers` on `--reinterview` (or route that
path through `enablement_preflight`).

### P2 — runtime reader mis-reads a string flag as enabled (code-reviewer)
`_feature_branch_workflow_enabled` ends `return bool(wt.get("feature_branch_workflow",
False))`. A hand-edited `feature_branch_workflow: "false"` (string) → `bool("false")`
== True → runtime selects the NEW model on a string opt-out. The interview layer
strips non-bool, but the RUNTIME reader doesn't mirror it → the two readers disagree
on the same bytes. Harness-generated files always emit a real `tojson` bool, so only
hand-edits reach it. **Fix:** in `_feature_branch_workflow_enabled`, treat a non-bool
value as absent (conservative False), mirroring the interview-layer strictness.

### P2 — `git status` failure makes the dirty-probe report clean (security + Codex-in-loop)
`_has_user_dirty_state` returns False on any `RuntimeError` (incl. timeout), so a
git-status timeout/transient error reports the base clean. Lower impact: the three
strand-critical signals are pure filesystem globs (git-independent); only the
user-dirty signal is lost. **Fix:** in `enablement_preflight`, distinguish "clean"
from "could not determine" — treat a status failure as a defer+warn.

### P2 — partial worktree round-trip (`enabled`/`scope`/`branch_prefix`) (Codex)
Only `feature_branch_workflow` is serialized; the templates hard-code `scope`/
`branch_prefix` and never emit `enabled`. A hand-set `worktree.enabled: false` /
custom scope is lost on re-render. **Mostly pre-existing** (the template never
emitted these), but it interacts with the migrate gate's `enabled` read. **Fix
(optional/broader):** render the full `worktree` dict from `config.worktree`.

## 🟢 Acknowledged-not-fixed
- preset-switch bypass (code) — already self-documented in `cli.py`, benign today.
- dirty-base defers on unrelated WIP (code, P3) — intentional ADR-008 conservatism.

## ✅ Cleared (both Claude + Codex agreed)
- No-git-mutation invariant holds (only read-only `git status`).
- `| tojson` emits valid YAML bool; no injection path (non-bool stripped pre-render).
- Round-trip merge/pop correct on all 4 on-disk shapes (true/false/absent/non-bool).
- Flag-OFF / absent render byte-neutral; new-default + serialization end-to-end tested.

## Verdict
**APPROVED (consensus grade A).** The single-repo migration is correct and the
safety invariants hold. The independent pass earned its keep: the **P1 sibling
strand** + the runtime-reader / reinterview opt-out P2s are real and belong in a
follow-up (natural Phase-7 "dual-path coverage" material). None block the landed
single-repo Phase 6.
