---
type: review
task_slug: failures-consolidate-cli
status: APPROVED
created: 2026-07-05
reviewers_invoked: [code-reviewer, concurrency-reviewer, test-reviewer, codex]
consensus_method: k-of-3 (2 Claude + Codex heterogeneous voter)
drift_verdict:
  result: clean
  scope_violations: []
  scenario_misses: []
  task_slug: failures-consolidate-cli
  computed_at: 2026-07-05
---

# REVIEW — failures-consolidate-cli

## 🎯 Round 1 Summary

**Initial grade: D** (one P0 present) → **auto-fix Round 2 → A**.

Diff reviewed: `git diff 6469b1a5 HEAD` — 3 files (`memory_md.py` +290, `command_registry.py` +4,
`tests/unit/test_memory_md_consolidate.py` +219). All in PLAN scope → **drift: clean**.

Voters: code-reviewer (opus), concurrency-reviewer (opus), test-reviewer (opus), **Codex 0.133.0**
(heterogeneous 3rd voter, Production mandate — invoked, exit 0).

**Headline (cross-model win):** the code-reviewer found a **P0 silent data-loss bug in the wiki
merge path**, and Codex independently converged on the *same* wiki-path asymmetry (from a different
symptom — a malformed heading). The concurrency reviewer and the original execute-time test pass
both missed it. This is exactly the k-of-3 heterogeneous value: two models zeroing in on the one
seam the happy-path tests didn't exercise.

## 🔍 Drift Findings

None. `command_registry.py` is the bidirectional-gate registration required by the new subparser
(caught by `test_command_surface_gate` during execute) — an implied dependency of Phase 1, not scope drift.

## ✅ Consensus / Verified Findings (all RESOLVED in Round 2)

### P0 — Wiki merge silently drops trailing `- [date]` body lines  (code-reviewer; Codex-corroborated)
`_parse_entries` ran `_split_body_bullets` for **every** tier, peeling a trailing `- [YYYY-MM-DD]`
run into `.bullets`. The wiki branch of `_merge_group` only re-emits `.body`, never `.bullets`, so a
wiki dup member whose body ends with a dated line (e.g. `- [2026-06-08] see MEMORY.md`, a style used
throughout this repo's memory) had that line **silently, irreversibly deleted** on
`consolidate --file wiki`. Singletons were unaffected (copied verbatim); only merged wiki dups.
- **Fix:** `_parse_entries` is now tier-aware — wiki takes the whole body (trailing blanks stripped,
  bullets always empty) via `_strip_trailing_blank`; only failures split bullets.
- **Regression test:** `test_wiki_dup_preserves_trailing_dated_body_line` (asserts both members'
  trailing dated lines survive) — fails against the old code, passes now.

### P2/P3 — Dateless wiki dup member → dangling `## [wiki:cat] slug | ` heading  (Codex P2 + code-reviewer P3)
An undated wiki dup member (`date=""`) sorted first, became canonical, and rendered a heading with a
trailing empty pipe.
- **Fix:** (a) undated members now sort **last** (`e.date or "9999-99-99"`) so a real-dated member
  becomes canonical + carries the real first-seen date; (b) `_wiki_heading(..., canonical.date or today)`
  fallback kills the dangling pipe even when *all* members are undated; (c) report `first_seen` ignores
  empty dates.
- **Test:** `test_wiki_dateless_dup_member_no_dangling_pipe`.

## 📝 Manual-Only Findings

### Test coverage gaps (test-reviewer) — all FILLED in Round 2
- **P1** CLI real-merge path untested → `test_cli_real_merge_reports_and_mutates` (rc, stdout report string, mutation).
- **P1** dup-member-unparseable guard (fail-closed rail) untriggered → `test_dup_member_unparseable_meta_raises_byte_identical`.
- **P1** `which="both"` aggregation untested → `test_which_both_aggregates_across_files`.
- **P2** interleaved occurrence-bullet chronological sort unasserted → `test_bullets_merged_in_chronological_order`.
- **P2** tautological `assert "test" in text` → tightened to the exact note string `mixed categories ['render', 'test'], kept 'test'`.
- **P2** legacy-singleton tolerance ('kept' half) untested → `test_legacy_singleton_tolerated_alongside_real_dup`.
- **P3** default-date (`_utcnow`) path → `test_default_date_uses_utcnow`.
- **P3** missing-file / markerless no-op branches → `test_noop_on_missing_and_markerless_files`.

Suite grew 12 → 21 tests, all green.

## ⚠️ Accepted (P3, not fixed)

- **`which="both"` is per-file atomic, not cross-file transactional** (code-reviewer P3). Failures
  writes first; an OSError on the wiki write after would leave failures updated + wiki unchanged. Each
  file stays individually consistent (atomic_write). **Documented in `consolidate()`'s docstring** —
  accepted as low-risk (only an OSError, not a logic path, can trigger it).
- **flock serializes only flock-takers; a direct Claude-Edit write can lose vs consolidate**
  (concurrency-reviewer P3, **out-of-diff**). Pre-existing property of the whole module (identical for
  `upsert_failure`/`upsert_wiki`); consolidate does not widen the blast radius. Not a new-code finding.

## 🤝 Concurrency verdict

**No P0/P1/P2.** Lock-correct: the full read→parse→rebuild→write cycle runs inside
`exclusive_lock` (no TOCTOU); `which="both"` acquires the two file locks **sequentially, never
nested** → no deadlock cycle with any `upsert`; `atomic_write` (tempfile + fsync + os.replace) makes
every write crash-safe; the all-or-nothing raises fire before the single write; base-vs-worktree paths
both resolve through `_base_root` to a byte-identical lock inode.

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | D     | —             | 1 P0, 2 wiki-heading, 8 test-gaps | — |
| 2 (auto)  | A     | P0 + dangling-pipe + 9 tests + docstring | 2×P3 accepted | 0 |

Final grade: **A**
Iterations used: 2 / 3
Status: **APPROVED**
human_review_needed: **false**  (no unverified manual-only/weak-consensus P0/P1 remain — the P0 was fixed + regression-tested)

Post-fix verification: `ruff check` + `ruff format` clean, `mypy --strict` clean, consolidate suite 21/21 green, full unit suite green.
