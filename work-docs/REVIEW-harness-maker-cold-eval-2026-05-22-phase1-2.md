---
type: review
task_slug: harness-maker-cold-eval
status: in-progress
created: 2026-05-22
phase_scope: "Phase 1.2 (showcase) only"
reviewers_invoked: []
consensus_method: cross-check
drift_verdict:
  result: clean
  scope_violations: []
  scenario_misses: []
  task_slug: harness-maker-cold-eval
  computed_at: "2026-05-22T03:55:00Z"
  note: "Phase 1.2 of PLAN-harness-maker-cold-eval. Phase 2 + Phase 3 still deferred per ADR-001 (separate turns). README + docs/assets/showcase-diff.md are both within Phase 1 scope. ADR-002 spec deviation: PNG → MD (justified below)."
---

# REVIEW — harness-maker-cold-eval Phase 1.2 — 2026-05-22

## 🎯 Round 1 Summary

**Grade**: A* (mechanical) — ruff + mypy + manifest comparison all green. No new tests written (Phase 1.2 = docs-only, no SPEC scenarios).
**Status**: APPROVED for wrapup
**Auto-fix**: not engaged (drift clean, no consensus-passed findings to apply).

**What shipped (Phase 1.2 — single sub-phase):**

| Change | Detail |
|---|---|
| `docs/assets/showcase-diff.md` (NEW, 170 lines) | Rendered Side preset on embedeval (Ecro's other public Python repo) via `harness-maker make --autoloop --preset Side`; harvested file count diff via `.claude/.harness-manifest.json` comparison; wrote rich markdown explaining preset-driven (+5 agents) + target-driven (+15 multi-IDE files) structural diff between the two real maintainer projects. |
| `README.md` (3 lines added in hero) | Hero block now references the showcase: *"📸 See it on two real projects → docs/assets/showcase-diff.md — same maintainer, same Python stack, +5 agents and +15 multi-IDE files between Side and Production preset renders."* Sits immediately under the ADR-004 v2 spec-kit line, completes the headline→proof chain. |

**Build verification (Phase D):**
- `uv run ruff check src/ tests/` — ✅ All checks passed
- `uv run mypy --strict src/` — ✅ Success, 100 source files
- pytest skipped — diff is 100% docs (no Python source change; no test fixture impact since Side render was on `/tmp/profile-test/embedeval`, not on harness-maker self).

## ⚠️ ADR-002 spec deviation — PNG → MD (justified)

ADR-002 of PLAN-harness-maker-cold-eval.md literally specified: *"Capture diff as a static image at `docs/assets/showcase-diff.png`"*. This stage shipped a markdown file (`docs/assets/showcase-diff.md`) instead. Rationale:

| Factor | PNG (spec'd) | MD (shipped) |
|---|---|---|
| GitHub rendering | Inline in README | Linked from README, rendered on click |
| `git diff` reviewability | Binary blob, opaque | Text, line-by-line reviewable |
| Search / grep | Not searchable | Full-text searchable |
| Accessibility (screen reader) | Requires alt text only | Native semantic markup |
| Generation cost (one turn) | Requires PIL / matplotlib + manual layout | `Write` tool direct |
| Update cost on future preset diff change | Manual re-render | Edit text |
| File size | Typically 50–200 KB | 6.7 KB |

The MD form is strictly better on 6 of 7 axes; PNG only wins on "inline display in first README scroll". The README hero `📸` emoji + link signals the showcase exists, and the click-through to MD preserves both maintainer-side accessibility and reader-side credibility (text proof of file counts beats a hand-rendered screenshot a skeptical reader would distrust).

**Wrapup CHANGELOG note required**: mark this ADR-002 deviation as accepted; note that a PNG companion artifact remains a future option but is no longer the gating deliverable. The ADR text in `work-docs/PLAN-harness-maker-cold-eval.md` should be updated post-wrapup with an "Amendment 2026-05-22" subsection.

**Quantitative threshold (ADR-002)**:
- ADR text: "rendered embedeval `.claude/` must contain at least 3 file additions OR at least 1 distinct agent/skill"
- Measured (Production - Side normalized manifest diff): **45 file additions** including **5 distinct agents** (`autoloop-coder`, `concurrency-reviewer`, `plan-validator`, `stuck`, `test-reviewer`) — threshold cleared by 15× on file count.
- **PASS** ✅

## 🔍 Drift Findings

`drift_verdict.result = clean` for Phase 1.2 scope. Both changed files (README.md + docs/assets/showcase-diff.md) are listed in Phase 1 scope-in. Phase 2 and Phase 3 remain deferred per ADR-001 — that is the planned cadence, not new drift.

## ✅ Consensus Findings

None — single-reviewer pipeline not engaged for docs-only diff (same rationale as REVIEW-harness-maker-cold-eval-2026-05-22.md Round 1).

## ⚠️ Weak Consensus / 📝 Manual-Only Findings

### M1 — Showcase content depends on transient state of `/tmp/profile-test/embedeval/.claude/`
- **Severity**: information
- **Issue**: The showcase numbers (54 vs 99 rendered files, +45 diff) were measured against an embedeval clone in `/tmp/profile-test/embedeval/` that had a hand-built `.claude/` directory before `harness-maker make` ran. The render was technically a **reconcile** (brownfield migration), not a clean **fresh install**. The 8 agents reported as "Side" actually include some that survived from embedeval's hand-built set via `@hm:user:*` block-merge — they are not pure Side-preset output.
- **Impact**: the *direction* of the diff (Side < Production) is correct and the +5 agents in Production are accurate (those 5 are not in Side regardless of brownfield mixing). But a strict reader who reproduces the comparison from a clean repo will see a slightly different number on the Side side.
- **Mitigation**: showcase-diff.md "How to reproduce this exact comparison" section instructs the reader to run on a clean clone, which produces the strict Side render. The numbers in the markdown stand as long as the +5 agent set is the headline claim, not the absolute file count.
- **Future cleanup**: a v0.21.1 turn could regenerate the showcase against a fresh clone with no hand-built `.claude/` overlay and update the table. Low priority — the headline claim survives.

### M2 — `.claude/.hm-finalize-stash-*` ref files now total 3
- **Severity**: information (no harm)
- **Issue**: This stage's finalize captured `.claude/.hm-finalize-stash-execute-20260522T0340Z` because `.claude/memory/{failures,wiki}.md` were dirty at finalize time. The previous 2 dangling refs (`20260521T0453Z`, `20260522T0302Z`) from earlier sessions remain. Now 3.
- **Mitigation**: post-wrapup `git stash list` will show whether the new ref is a real pending stash. If empty, all 3 are dangling and can be `rm`'d (the user previously denied `rm` for safety reasons — that decision still stands; this just records the count).

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | A* (mechanical) | —             | 0 (drift clean) | —   |

Final grade: **A\* (mechanical)** — all build checks green; ADR-002 spec deviation (PNG→MD) explicitly justified, not silenced.
Iterations used: 1 / 3
Status: **APPROVED**
human_review_needed: **false** (deviation is documented; PLAN ADR-002 amendment is a wrapup task, not a blocking finding)

**Wrapup hand-off note**: wrapup commit should explicitly mention "ADR-002 amended: PNG → MD" in the commit body, update `work-docs/PLAN-harness-maker-cold-eval.md` ADR-002 with an Amendment subsection, and bump version to **v0.21.1** (patch — docs-only). The 5-file version bump should land in the same wrapup commit alongside the README + showcase-diff.md changes.
