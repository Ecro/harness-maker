---
type: review
task_slug: untested-trio-fix-2026-05-19
status: APPROVED
created: 2026-05-19
reviewers_invoked: [code-reviewer, security-reviewer]
consensus_method: cross-check
drift_verdict:
  result: clean
  scope_violations: []
  scenario_misses: []
  task_slug: untested-trio-fix-2026-05-19
  computed_at: 2026-05-19T13:35:00Z
final_grade: A
iterations_used: 1
max_review_rounds: 3
human_review_needed: false
---

# REVIEW — untested-trio-fix-2026-05-19

## 🎯 Round 1 Summary

- **Grade: A** (0 consensus-passed P0/P1 findings)
- **Status: APPROVED** — ready for wrapup
- **Reviewers invoked:** code-reviewer, security-reviewer (per `harness.yaml.reviewers.enabled`)
- **Findings:** 5 raw → 3 surfaced after Pass 1.5 verifier
  - 0 consensus-passed
  - 0 weak-consensus
  - 3 manual-only (1 introduced by this PLAN, 2 pre-existing flagged as out_of_diff)
- **Fixes pending:** 0 auto-applicable (auto-fix loop not entered — Grade A on entry)
- **Manual items:** 1 (CLAUDE.md line 267 stale prefix list — trivial 1-line follow-up)

## 🔍 Drift Findings

`drift_verdict.result: clean`. All 5 changed files (~331 LOC) are within PLAN Phase 1/2 declared scope:

| File | PLAN Phase | Verdict |
|------|-----------|---------|
| `src/harness_maker/worktree.py` | Phase 1 (P0-2) | ✅ in scope |
| `tests/unit/test_worktree_multi.py` | Phase 1 (P0-2) | ✅ in scope |
| `CLAUDE.md` | Phase 1 (P0-2 docs) | ✅ in scope |
| `src/harness_maker/second_brain.py` | Phase 2 (P1-3) | ✅ in scope |
| `tests/unit/test_second_brain.py` | Phase 2 (P1-3) | ✅ in scope |

No scenario misses (PLAN has no SPEC, so no `## 📋 In-Scope Scenarios` to match). PLAN frontmatter has no `common_ground_marks` — ADR-008 silent-intent-miss hook does not fire for this PLAN.

## ✅ Consensus Findings

**None.** No findings achieved cross-check consensus (surface match + reasoning alignment). Two reviewers ran in parallel; their findings were on different aspects (code-reviewer flagged docs drift, security-reviewer flagged pre-existing helper functions). No overlap.

## ⚠️ Weak Consensus

**None.**

## 📝 Manual-Only Findings

### M1 — `CLAUDE.md:267` retains stale 2-prefix list (`phase-*`, `autoloop-*`) while line 90 was updated to 4 prefixes · `Severity: P2` · `Source: code-reviewer` · `Status: manual-only`

**OBSERVE:** PLAN ADR-004 / Phase 1 scope requires CLAUDE.md to list 4 owned prefixes. The PLAN's Phase 1 exit-criterion `grep` checked only one occurrence (line 90 pattern). Line 267 in `CLAUDE.md`'s "구현 패턴 / Worktree cleanup 정책" section contains a second independent description of the same safety claim, and it still reads:
```
- **Cursor 와 공유 시 주의**: prefix 매치로 자기 것만 cleanup (`phase-*`, `autoloop-*`). Cursor 가 만든 worktree (다른 prefix) 는 건드리지 않음.
```

**INFER:** A future reader of line 267 will form an incorrect mental model — they'll think `execute-*` / `plan-*` worktrees are NOT cleanup-eligible (when in fact they are, per the code change in Phase 1). The two CLAUDE.md locations contradict each other.

**CONCLUDE:** Direct PLAN intent gap — the line 90 edit was incomplete. The fix is a 1-line edit at line 267 to mirror line 90's 4-prefix list. The PLAN's exit-criterion grep should ALSO have been broadened, OR a complete `rg -l '\\(`phase-\\*`, `autoloop-\\*`\\)' CLAUDE.md` would have surfaced the second hit.

**Suggested fix (verbatim):**
```diff
-- **Cursor 와 공유 시 주의**: prefix 매치로 자기 것만 cleanup (`phase-*`, `autoloop-*`). Cursor 가 만든 worktree (다른 prefix) 는 건드리지 않음.
++ **Cursor 와 공유 시 주의**: prefix 매치로 자기 것만 cleanup (`execute-*`, `plan-*`, `phase-*`, `autoloop-*`). Cursor 가 만든 worktree (다른 prefix) 는 건드리지 않음.
```

**Why not auto-applied:** Single-source finding → `manual-only` per Step 4d. User invokes a one-line follow-up Edit or runs `/hm:wrapup` (wrapup may catch this in its quality bar).

### M2 — `src/harness_maker/worktree.py:498` `_ensure_gitignore_entry` non-atomic append · `Severity: P2 out_of_diff` · `Source: security-reviewer` · `Status: manual-only (deferred — pre-existing)`

**OBSERVE:** `_ensure_gitignore_entry` (line 462-490) uses `gitignore.open("a", encoding="utf-8")` to append a line. Plain `open(..., "a")` is non-atomic — process interrupt between the file-handle open and the write leaves a partially-written gitignore.

**INFER:** The function is in a file changed by this PLAN (`worktree.py`), but the function itself is NOT touched by the diff. CLAUDE.md §"Atomic file write" hard-rules atomic_write for all file writes. This is a latent violation, not introduced by this PLAN.

**CONCLUDE:** Out-of-diff finding. Note for a follow-up cleanup PLAN. The risk-impact is low — gitignore is best-effort hygiene (the function's own docstring acknowledges OSError swallow at L488).

**Suggested fix:** Replace the read-check-append sequence with `atomic_write(gitignore, existing + sep + entry + '\n')`.

### M3 — `src/harness_maker/second_brain.py:393` `_iter_markdown` follows symlinks via `rglob` · `Severity: P2 out_of_diff` · `Source: security-reviewer` · `Status: manual-only (deferred — pre-existing)`

**OBSERVE:** `_iter_markdown` uses `root.rglob(f"*{ext}")` which on CPython follows symlinks by default. A symlink inside a configured vault folder pointing outside the vault would be traversed during `search_notes`.

**INFER:** `search_notes` does NOT route through `_resolve_authorized` (that gate is only on `read_note`/`write_note`/`append_note`/`patch_note`). The PLAN-untested-trio-review-2026-05-19 sibling REVIEW also noted this pattern as defense-in-depth-OK for `refdocs_index` (rglob doesn't follow there); same standard would apply here for safety symmetry.

**CONCLUDE:** Pre-existing, untouched by this PLAN. The trio REVIEW REVIEW-second-brain didn't flag this either — would be a fix-stage PLAN follow-up alongside other second_brain hardening.

**Suggested fix:** Post-rglob, filter via `p.resolve().is_relative_to(root.resolve())`.

## 🤝 Disagreements

**None.** Reviewers' findings were on different aspects with no overlap. No severity disagreements arose.

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | A     | —             | 3 (manual-only) | —   |

Final grade: **A**
Iterations used: **1 / 3**
Status: **APPROVED**
human_review_needed: **false**

> Grade A reached on Round 1 — auto-fix loop not entered. All 3 surfaced findings are `manual-only` (1 trivial doc-drift fix, 2 pre-existing out_of_diff notes for future cleanup PLAN).

## 📊 Pass-by-Pass Reviewer Stats

| Reviewer | Pass 1 raw | Pass 1.5 kept | Pass 2 confirmed |
|----------|-----------|---------------|------------------|
| code-reviewer | 3 (1 P1, 2 P2) | 1 (M1 only — F1/F3 dropped as out_of_diff) | 1 |
| security-reviewer | 2 (both P2 out_of_diff) | 2 (both kept as advisory notes) | 2 |
| **Total surfaced** | **5** | **3** | **3** |

Pass 1.5 verifier action log:
- F1 (`patch_note` raw FileNotFoundError) — **DROPPED**: `path.read_text()` at line 217 is unchanged by this diff; pre-existing behavior. Out of scope per PLAN §"No code change outside …".
- F3 (no test for missing-file patch) — **DROPPED**: companion to F1; testing a pre-existing condition.
- F2 (CLAUDE.md L267 stale) — **KEPT** as M1.
- S1/S2 — **KEPT** as M2/M3 with `out_of_diff` advisory tag.
