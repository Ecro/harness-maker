---
type: review
task_slug: failure-memory-recurrence-dedup
status: APPROVED
created: 2026-07-04
reviewers_invoked: [code-reviewer x2, test-reviewer, codex (gpt-5.5, k-of-3 third voter)]
consensus_method: cross-check
drift_verdict:
  result: clean
  scope_violations: []
  scenario_misses: []
  task_slug: failure-memory-recurrence-dedup
  computed_at: 2026-07-04T00:00:00Z
---

# REVIEW — failure-memory-recurrence-dedup

## 🎯 Round 1 Summary

- **Initial grade: B** (1 consensus-passed P1). Below threshold A → auto-fix loop.
- **Final grade: A** after 1 auto-fix round + a Codex re-verification pass.
- **Status: APPROVED**, `human_review_needed: false` (no unresolved P0/P1).
- Reviewers: 2× `code-reviewer` (cross-check) + `test-reviewer` + **Codex gpt-5.5** as the
  k-of-3 third voter (`codex_status: invoked`, Production mandatory gate).

All findings clustered in ONE place: the `_upsert` **new-entry `--occurrence-note`
safety-net path** in `memory_md.py`. The core occurrence-log append + count++ mechanic,
the match path, and the wrapup template were confirmed correct by all reviewers.

## 🔍 Drift Findings

`drift_verdict: clean`. All 14 changed files map to a PLAN phase (Phase 1 memory_md +
tests, Phase 2 templates + render tests, Phase 3 snapshot regen). No scope violation, no
incomplete phase.

## ✅ Consensus Findings (consensus-passed)

### P1 — Heading-injection via the new-entry occurrence-note seed  ✅ FIXED
- **Sources:** Codex (high), code-reviewer #1 (P2), test-reviewer (blocking) — 3 independent
  voices, same symbol + same failure mode (Codex null-location relaxation → symbol match).
- **Defect:** on a NON-matching slug, `--occurrence-note` was collapsed and written as an
  **unprefixed** body line (`new_body = [collapsed]`). A heading-shaped note
  (`## [fail:x] …`) became a phantom heading on the next `_entry_headings` scan → silent
  truncation / tier DoS — the exact class the body heading-guard exists to prevent, bypassed.
- **Fix:** the new-entry seed is now a **dated bullet** `- [today] {collapsed}` (heading-
  immune, `- ` prefix defeats the anchored `^##`), via the shared `_new_entry_body` helper.
- **Binding test:** `test_new_failure_from_heading_shaped_occurrence_note_is_not_a_phantom_heading`
  (line-anchored heading count == 1; RED on the old unprefixed code).

### P3 — `--body-file` silently dropped when `--occurrence-note` also passed  ✅ FIXED
- **Sources:** code-reviewer #1 (P3) + code-reviewer #2 (P3) — 2 voices.
- **Defect:** `main()` forced `body=""` whenever `--occurrence-note` was set, silently
  discarding a supplied `--body-file` paragraph with exit 0.
- **Fix:** loud mutual-exclusion error (`MemoryBlockError` → non-zero exit).
- **Binding test:** `test_cli_occurrence_note_mutually_exclusive_with_body`.

## ⚠️ Weak Consensus

None.

## 📝 Manual-Only Findings

### P2 — Empty occurrence-note not fail-closed on the new-entry path  ✅ FIXED
- **Source:** code-reviewer #2. The match path raised on an empty note, but the new-entry
  path fell through to an evidence-less `count:1` entry (trigger: a slug typo on an intended
  recurrence — the exact fragmentation the feature warns about).
- **Fix:** `_new_entry_body` raises on an empty collapsed note (parity with the match path).
- **Binding tests:** `test_new_failure_from_empty_occurrence_note_is_fail_closed`,
  `test_new_failure_from_occurrence_note_on_markerless_file_seeds_bullet` (empty half).

### P3 — Marker guard bypassable via newline-split  ✅ FIXED
- **Source:** code-reviewer #2. `<!-- @hm:user:entries\n-->` passed the raw substring guard,
  then whitespace-collapse reformed the marker. Harmless today (exact-equality `_locate_block`
  + bullet prefix) but defeats the guard's intent.
- **Fix:** `_collapse_note` re-checks OPEN/CLOSE markers **after** collapse, on both the
  match (`source`) and new-entry paths.
- **Binding test:** `test_occurrence_note_with_newline_split_marker_is_rejected`.

### P2 — Marker-absent (fresh/legacy file) creation path dropped the occurrence-note  ✅ FIXED
- **Source:** Codex re-verification (Round 2). The `_locate_block is None` creation branch
  used `body_lines` directly, bypassing the new occurrence-note seed handling — same
  evidence-less-entry invariant violation in an untouched branch.
- **Fix:** extracted `_new_entry_body`; **all three** creation paths (marker-absent, no-match,
  and by symmetry the match append) now share one seed contract.
- **Binding test:** `test_new_failure_from_occurrence_note_on_markerless_file_seeds_bullet`.

### Test quality (test-reviewer FAIL → resolved)
- Untested new-entry branch + untested `occurrence_note` marker guard + stale
  `test_upsert_failure_same_slug_increments_count_and_preserves_first_date` (survived a
  replace regression). Resolved: **8 new tests** + strengthened the stale test (now asserts
  body preservation + bullet form) + strengthened the render test (exact `--slug <existing-slug>`
  wiring).

## 🤝 Disagreements

- **Heading-injection severity:** Codex P1 vs code-reviewer #1 P2 (same defect, different
  tier — kept independent per the no-bridge-tiers rule). Recorded at P1 (the memory-corruption
  class + 2-of-3 weighting). Moot post-fix.
- **Codex Hunt-1 (match path):** code-reviewer #2 declared the *match* append heading-safe and
  missed the *new-entry* unprefixed case; Codex + cr#1 + test-reviewer caught it. The
  heterogeneous panel is what surfaced the full picture — no single reviewer had all of it.

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | B     | —             | 5 (1×P1, 2×P2, 2×P3) | — |
| 2 (auto-fix) | A  | 4 code fixes + 8 tests | 0 | 1 (P2 markerless, from Codex re-verify — fixed same round) |

- **Final grade: A**
- **Iterations used: 2 / 3**
- **Status: APPROVED**
- **human_review_needed: false**

**Verification (final state):** affected unit tests + render tests GREEN (58 in
`test_memory_md.py` + `test_wrapup_memory_fold.py`), `mypy --strict` 117 files clean,
`ruff check`/`format` clean, full `pytest` GREEN. Fixes are on
`hm/failure-memory-recurrence-dedup` (uncommitted working tree in the task worktree);
wrapup owns the squash-land. No commit made in this stage.
