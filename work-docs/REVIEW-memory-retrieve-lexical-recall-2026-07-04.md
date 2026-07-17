---
type: review
task_slug: memory-retrieve-lexical-recall
status: APPROVED
created: 2026-07-04
reviewers_invoked: [code-reviewer, security-reviewer, codex]
consensus_method: cross-check
drift_verdict:
  result: clean
  scope_violations: []
  scenario_misses: []
  task_slug: memory-retrieve-lexical-recall
  computed_at: 2026-07-04
---

# REVIEW — `memory-retrieve-lexical-recall` (conservative stemmer)

## 🎯 Round 1 Summary

- **Grade: A** (0 consensus-passed P0, 0 consensus-passed P1).
- **Status:** APPROVED (letter cleared) — but **one cross-model design finding at P2** is surfaced
  for an owner decision before wrapup (it re-opens a PLAN-pinned assumption, so it is not
  silently auto-fixed).
- `human_review_needed: false` (no unverified P0/P1; the finding is P2).
- Reviewers: `code-reviewer` (CLEAN), `security-reviewer` (CLEAN), `codex` (1× P2). Codex ran as
  the mandatory third voter (Production preset), exit 0.

## 🔍 Drift Findings

`drift_verdict: clean`. Changed files: `src/harness_maker/memory_retrieve.py` (PLAN Phase 1 scope)
+ `tests/unit/test_memory_retrieve_recall.py` (PLAN Phase 2 scope). Both phases complete. No file
outside PLAN scope; no in-scope file left unchanged.

## ✅ Consensus Findings

None at P0/P1. No consensus-passed defect lowers the grade.

## ⚠️ Weak Consensus (cross-model, P2) — `-es`-before-`-s` narrows the recall win

**Both Codex and code-reviewer independently identified the same gap** (strong OBSERVE alignment;
they diverge only on disposition — Codex tags it a P2 recall regression, code-reviewer tags it an
accepted-limitation to document). Tagged **weak-consensus** → NOT auto-applied; surfaced for the owner.

- **Location:** `_stem`, `memory_retrieve.py` (`_STEM_SUFFIXES = ("es", "s", "ing", "ed")`).
- **OBSERVE:** because `-es` is tried before `-s` with first-match-wins + no-cascade + min-stem-len 4,
  ordinary `<stem>e`+`s` plurals fail to bridge to their singular:
  - guard-blocked, stays plural: `files`→`files` (`-es`→`fil` len 3 < 4, no cascade to `-s`→`file`),
    `nodes`→`nodes`, `codes`→`codes`.
  - over-stemmed, wrong stem: `updates`→`updat` (≠`update`), `states`→`stat`, `values`→`valu`.
- **CONCLUDE:** the runtime overlap never matches for these variants, so the recall win is narrower
  than the PLAN's stated scope. The PLAN Exec Summary scopes the win to *"inflectional variants that
  share a ≥4-char stem after a single suffix strip"* — and `files`→(strip `-s`)→`file` is exactly
  that, yet the pinned `-es`-first order forecloses it. This is a **spec↔implementation gap**, not
  merely accepted residue.

**Empirical (`-es`-first vs sibilant-aware `-es`):**

| word | current (`-es` first) | sibilant-aware `-es` |
|------|-----------------------|----------------------|
| files / file | `files` ✗ | `file` ✓ |
| updates / update | `updat` ✗ | `update` ✓ |
| states / state | `stat` ✗ | `state` ✓ |
| nodes / node | `nodes` ✗ | `node` ✓ |
| codes / code | `codes` ✗ | `code` ✓ |
| matches / match | `match` ✓ | `match` ✓ |
| boxes / box | `boxes` (box<4) | `box` blocked (box<4) |
| snapshots / snapshot (flagship) | `snapshot` ✓ | `snapshot` ✓ |

A **sibilant-aware `-es`** (strip `-es` only after s/x/z/ch/sh, else fall to `-s`) closes BOTH the
`<stem>e`+`s` class AND the sibilant `-es` class, is ADR-001/002/003-compatible (still lexical,
single-signal, no `-er`/`-tion`, min-len guard intact — *more* precise, not less), and **passes
every existing test unchanged** (verified: `misses`→`miss`, `uses`→`uses`, `goes`→`goes` all hold
because the sibilant/guard/no-cascade semantics are preserved).

## 📝 Manual-Only Findings

None beyond the above.

## 🤝 Disagreements

Codex (P2, "recall regression, fix it") vs code-reviewer (informational, "accepted limitation,
document it"). Kept as one weak-consensus item — not bridged across dispositions. Security-reviewer
found no security-relevant issue (stem output is data-flow-isolated from every output sink; the
2026-05-19 fence-neutralization is untouched; `_stem` is O(1)/token; frozenset dedup means keyword
stuffing cannot inflate `score_entry`).

## Grade Computation

- consensus-passed P0 = 0, consensus-passed P1 = 0 → **Grade A**.
- unverified_severe = false (the sole cross-model finding is P2).

## Iteration 2 (Grade: A → A) — sibilant-aware `-es` applied

Owner chose **sibilant-aware `-es`** (recommended). Applied to `_stem`:
`-es` strips only when the pre-`es` stem ends in `_ES_SIBILANTS = ("s","x","z","ch","sh")`;
otherwise it falls through to `-s`. Enumerated explicitly (not a bare trailing `h`) so
`-th`/`-ph`/`-gh`+`es` verbs (`breathes`→`breathe`, `clothes`→`clothe`, `bathes`→`bathe`)
fall through to `-s` rather than over-stemming.

| # | Severity | Summary | File | Status |
|---|----------|---------|------|--------|
| 1 | P2 | `-es`-before-`-s` recall gap (Round-1 cross-model finding) | memory_retrieve.py | **Applied** (sibilant-aware `-es`) |
| 2 | P2 | bare-`h` sibilant would over-collapse `breathes`→`breath` (re-review) | memory_retrieve.py | **No change needed** — re-reviewer read the stale `("s","x","z","h")` snippet from the review prompt; the applied code already uses the explicit `("s","x","z","ch","sh")` tuple, so `breathes`→`breathe` (verified empirically) |

New tests (in `test_memory_retrieve_recall.py`): `test_stem_non_sibilant_es_falls_through_to_s`
(files/updates/states/nodes/codes/types/values + `bathes`→`bathe` + singular fixed-points),
`test_stem_sibilant_es_below_guard_stays_unchanged` (`boxes`→`boxes`), and
`test_stem_strips_es_after_sibilant` (misses/dishes/matches). Existing
`test_memory_retrieve.py` still green **unchanged**.

Re-verify: recall + existing memory_retrieve suites GREEN (55 tests); `ruff check` /
`ruff format --check` / `mypy --strict` clean. Precision gate (no `-er`/`-tion`, min-len 4,
no forbidden merge) re-confirmed by the re-reviewer against the current tree.

Remaining: 0 | New issues introduced: 0

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | A     | —             | 1 (P2, owner-decision) | — |
| 2         | A     | 1 (sibilant-aware `-es`) | 0 | 0 |

Final grade: **A**
Iterations used: 2 / 3
Status: **APPROVED**
human_review_needed: false
