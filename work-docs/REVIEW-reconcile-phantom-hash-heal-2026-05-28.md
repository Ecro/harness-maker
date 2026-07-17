---
type: review
task_slug: reconcile-phantom-hash-heal
status: APPROVED
created: 2026-05-28
reviewers_invoked: [code-reviewer, security-reviewer]
consensus_method: cross-check
drift_verdict:
  result: clean
  scope_violations: []
  scenario_misses: []
  task_slug: reconcile-phantom-hash-heal
  computed_at: 2026-05-28T00:00:00Z
---

# REVIEW — reconcile phantom-hash heal

Diff under review: `src/harness_maker/reconcile.py` + `tests/unit/test_reconcile.py`.
Ad-hoc fix (no PLAN/SPEC) — drift gate N/A (`result: clean`).

## 🎯 Round 1 Summary

- Grade (consensus-passed only): **A** (P0=0, P1=0).
- One reviewer **disagreement** on the central risk (see §Disagreements) — surfaced, not averaged.
- 5 manual findings (no strong consensus) acted on by orchestrator judgment in Round 2.

## 🔍 Drift Findings

None. No PLAN scope to violate.

## ✅ Consensus Findings (strong)

None reached strong consensus (only 2 reviewers; the one overlapping issue diverged on severity → weak — see below).

## ⚠️ Weak Consensus

- **Heal vs malformed-markers protection** — code-reviewer P2 / security-reviewer P3. Both observe: a pre-floor ours file with user-broken markers hits the same `hash-mismatch-malformed-markers` reason as a renderer-emitted duplicate-id phantom, so the heal can REPLACE a real (broken) user edit. Both note `.backup-<ts>/` mitigates. Tier diverged (P2 vs P3) → recorded weak, not auto-applied. **Resolved in Round 2** by template-gating (heal now only touches Codex skill bodies, where duplicate-id markers are render artifacts).

## 📝 Manual-Only Findings

1. **(code-reviewer P1) Heal scope broader than the phantom population.** `hash-mismatch-user-modified` is produced for both a phantom hash and a genuine hand-edit of any marker-less pre-floor ours file → those edits get REPLACEd (backup-recoverable). Docstring overclaimed "never clobbered."
2. **(code-reviewer P2) Version-floor keying contradicts the repo's "key on the stable invariant" rule** — a future phantom-class regression at ≥ floor would not auto-heal.
3. **(code-reviewer P2) Test gaps** — no coverage of floor boundary semantics, not-healed KEEP reasons, or malformed version.
4. **(security-reviewer P3) Precondition implicit** — heal correctness depends on staying nested under the hash-mismatch `else`; a refactor could silently break it.
5. **(security-reviewer, scrutiny 1–4) Confirmed SAFE**: backup-first ordering is fail-safe (`cli.py:356` before render, no try/except); version-string handling has no unhandled path; the heal is strictly tighter than the already-shipped `legacy-no-hash-but-ours` REPLACE branch.

## 🤝 Disagreements

**Central risk — code-reviewer P1 (data loss) vs security-reviewer SAFE.**
- code-reviewer: the discriminator over-includes genuine user edits → P1, and the docstring's "never clobbered" is false below the floor.
- security-reviewer: backup-first is fail-safe and the heal is strictly more conservative than existing shipped behavior → no finding ≥ P2.
- **Resolution:** Both are correct on the facts. The orchestrator sided with code-reviewer on *scope* and applied their suggested fix (gate on `source_template`), which removes the broad data-loss surface (only Codex skill bodies are touched; CLAUDE.md / agents / commands are never healed) while keeping security-reviewer's verified safety properties (backup-first, version floor, fail-safe version parsing).

## Round 2 — fixes applied (orchestrator)

| # | Addresses | Change |
|---|-----------|--------|
| 1 | P1, weak-consensus | Template-gate: `_PHANTOM_AFFECTED_TEMPLATES = {codex/stage_skill.md.j2, codex/loop_skill.md.j2}`; renamed `_is_pre_phantom_fix_ours` → `_is_healable_phantom_ours` with `source_template` check. Heal now scoped to the exact file class the bug touched. |
| 2 | P1 | Docstring rewritten — accurate boundary (≥ floor never clobbered; pre-floor *skill* bodies healed + backup-recoverable; the residual is explicitly an accepted, documented trade-off). |
| 3 | P2 (version-floor) | Comment cross-references the "key on the stable invariant" rule (`source_template` is the stable key; version floor protects current edits), and documents that a ≥-floor phantom regression fails safe (re-freeze, never auto-overwrite). |
| 4 | P3 (precondition) | Inline comment at the guard noting it's reachable only when `existing_hash != recomputed`. |
| 5 | P2 (test gaps) | +3 tests: `_non_affected_template_not_healed`, `_template_unreadable_not_healed`, `_malformed_version_not_healed`. |

Verification: reconcile suite (30 tests) green; ruff + format clean; `mypy --strict` clean; all 4 real backup phantom files (`hm-execute/verify/wrapup/loop`) still heal → `legacy-phantom-hash-heal`; a non-skill pre-floor ours file now correctly stays KEEP.

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | A     | —             | 5 manual  | —   |
| 2         | A     | 5             | 0         | 0   |

Final grade: **A**
Iterations used: 2 / 3
Status: **APPROVED**
human_review_needed: false
