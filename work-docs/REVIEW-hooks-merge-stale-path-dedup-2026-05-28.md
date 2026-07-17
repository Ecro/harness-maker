---
type: review
task_slug: hooks-merge-stale-path-dedup
status: APPROVED
created: 2026-05-28
reviewers_invoked: [code-reviewer, security-reviewer]
consensus_method: cross-check
drift_verdict:
  result: clean
  scope_violations: []
  scenario_misses: []
  task_slug: hooks-merge-stale-path-dedup
  computed_at: 2026-05-28T00:00:00+00:00
---

# REVIEW — hooks-merge-stale-path-dedup (2026-05-28)

## 🎯 Round 1 Summary

- **Grade: A** (consensus-passed P0=0, P1=0). Threshold A met → **APPROVED**.
- Reviewers: `code-reviewer`, `security-reviewer` (both `model: opus`), single round.
- Auto-fix loop: not entered (grade ≥ threshold; both findings are manual-only, not auto-fix-eligible).
- Consensus-passed findings: **0**. 2 single-source `manual-only` findings (1×P2, 1×P3) — non-blocking; dispositions below.

Both reviewers independently confirmed the core safety contract: the broadened regex normalizes
ONLY commands in harness-maker's own `python -m harness_maker.*` namespace, so genuinely
user-authored hooks (other tooling) round-trip unchanged and are preserved by the merge. The
merge only ever KEEPS or DROPS existing entries and emits template entries verbatim — no new
command can be added or executed. No ReDoS (no nested quantifiers; single-line `.*$` is linear).

## 🔍 Drift Findings

`drift_verdict: clean`. Diff-vs-PLAN mapping:

| File(s) | PLAN phase | Verdict |
|---|---|---|
| `src/harness_maker/render.py`, `tests/unit/test_render.py` | Phase 1 (in-scope) | ✅ in scope |
| 5 version files + `CHANGELOG.md` | Phase 3 (in-scope) | ✅ in scope |
| `uv.lock` | — | mechanical: `uv` re-pins the local package version on every bump |

`uv.lock` is a deterministic byproduct of the Phase 3 version bump → `scope_violations: []`. No
snapshot files changed (regen from main produced no diff — version not in body-hashed content
here). No PLAN-scoped code file left unchanged. PLAN has no `common_ground_marks` frontmatter →
Step 2.5 silent-intent-miss hook skipped.

## ✅ Consensus Findings

None. The two findings share file + line (render.py:593) but differ in severity tier (P3 vs P2)
AND in the issue described — surface-match (Step 4a) fails on tier mismatch, so they are
independent, not consensus.

## ⚠️ Weak Consensus

None.

## 📝 Manual-Only Findings

| # | Sev | Reviewer | File:Line | Summary | Disposition |
|---|-----|----------|-----------|---------|-------------|
| 1 | P2 | security-reviewer | render.py:593 | A user hook that re-wraps our `python -m harness_maker.<module>` with byte-identical module+args to a shipped entry (but a different launcher) normalizes to the same identity and is deduped away | **Accepted-risk (ADR-001).** By design: `harness_maker.*` is our namespace — a match is proof of ownership; the docstring states this. Narrow case (must match module+args exactly); backup is the documented recovery path (ADR-001). Narrowing the match to the `uv run --with` launcher shape would reintroduce the W1 brittleness ADR-001 deliberately removed → NOT done. |
| 2 | P3 | code-reviewer | render.py:593 | Greedy `harness_maker\.\S.*$` capture includes trailing whitespace, so a hand-edited on-disk command with a stray trailing space/newline could fail to collapse against the template form | **Deferred (future hardening).** Reviewer: not reachable via template-rendered JSON. Not applied now because the **current regex was validated end-to-end against spoton's real residue in Phase 2** — changing it pre-release would ship a regex differing from the validated one. Candidate follow-up: `harness_maker\.\S.*?)\s*$` + a trailing-ws collapse test. |

## 🤝 Disagreements

None on risk. Findings 1 and 2 reference the same line (render.py:593) but address different concerns
(namespace-ownership config-loss vs trailing-whitespace dedup robustness) at different severity tiers
— recorded as independent manual-only items, not a severity disagreement.

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | A     | —             | 2 manual-only (1×P2, 1×P3) | — |

Final grade: **A**
Iterations used: 1 / 3
Status: **APPROVED**
human_review_needed: false
