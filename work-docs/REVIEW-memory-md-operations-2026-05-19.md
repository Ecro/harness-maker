---
type: review
task_slug: memory-md-operations
status: APPROVED
created: 2026-05-19
reviewers_invoked: [code-reviewer, security-reviewer, performance-reviewer]
consensus_method: cross-check
drift_verdict:
  result: clean
  scope_violations: []
  scenario_misses: []
  task_slug: memory-md-operations
  computed_at: 2026-05-19T12:50:00Z
---

# REVIEW — memory-md-operations (Round 1)

## 🎯 Round 1 Summary

- **Grade:** **A** (P0=0, P1=0 consensus-passed)
- **Reviewers:** code-reviewer + security-reviewer + performance-reviewer (parallel, single pass — Pass 1.5 verifier stripped per ADR-008, Pass 2 contextual restoration moot since the diff carries no PR title/author metadata to redact)
- **Routing:** conditional (Python source + templates)
- **Auto-fix loop:** not entered (grade ≥ threshold). Orchestrator manually applied the manual-only P1 fixes — see §Auto-fix manual extensions.

## 🔍 Drift Findings

`drift_verdict.result = clean`. PLAN scope (Phase 1 + Phase 2) covered: new `harness_maker.memory_retrieve` module, 3 test files, 3 stage template edits. No scope drift. No scenario misses (no SPEC file for this task).

## ✅ Consensus Findings

**None.** Every reviewer's finding was single-source; no surface-match cross-reviewer pair.

## ⚠️ Weak Consensus

**None.**

## 📝 Manual-Only Findings

### P1 — applied as orchestrator-judgment fixes

| ID | Source | File:Line | Summary | Fix applied |
|---|---|---|---|---|
| M1 | code-reviewer | memory_retrieve.py:262 | Single-entry truncation reserved fixed 1KB for overhead; long topic + long slug + sentinel could push final output past byte_cap | Compute actual fence + heading + instruction byte overhead from real f-strings; bounded re-shrink loop as defensive backstop. New test `test_render_byte_cap_single_oversized_with_long_topic` regression-guards. |
| M2 | code-reviewer | test_memory_retrieve.py:286 | Single-oversized test only asserted "truncated" in out, not `len ≤ cap` | Added `assert len(out.encode("utf-8")) <= 10240` to the existing test. Pairs with M1. |
| M3 | code-reviewer | memory_retrieve.py:24 | Imported private `_WORD_RE` from sibling module — silent coupling risk on refactor | Promoted `WORD_RE` to public in `relevance.py`; `_WORD_RE` retained as backward-compat alias. memory_retrieve.py imports public name. |
| M4 | security-reviewer | memory_retrieve.py:234, 312 | Topic value interpolated unescaped into `<memory_candidates topic="...">` fence attribute — `"` in topic breaks the attribute, allowing prompt-injection via crafted topic | `html.escape(topic, quote=True)` applied at both interpolation sites. New test `test_render_escapes_double_quote_in_topic` regression-guards. |
| M5 | security-reviewer | memory_retrieve.py:139/252 | Entry body containing literal `</memory_candidates>` would close the fence early; post-fence text consumed by the running Claude turn as instructions. **Stored prompt-injection via committed wiki.md** | `_neutralize_fence()` replaces the literal close substring with `<\/memory_candidates>` in every rendered entry body before fence assembly. New test `test_render_neutralizes_fence_close_in_entry_body` regression-guards. |

### P2 — applied

| ID | Source | File:Line | Summary | Fix applied |
|---|---|---|---|---|
| M6 | code-reviewer | memory_retrieve.py:196 | `byte_cap` parameter accepted by `top_candidates` but never used | Removed the unused parameter. Single CLI caller updated. |

### P2 — deferred (advisory; document for follow-up)

| ID | Source | File:Line | Summary | Rationale to defer |
|---|---|---|---|---|
| M7 | code-reviewer | memory_retrieve.py:160 | `_entry_token_set` doesn't strip stopwords — asymmetry with `topic_tokens` | Intentional: slug/category stopwords ARE legitimate discriminators. Adding the docstring note belongs to Approach A follow-up |
| M8 | code-reviewer | test_memory_retrieve_cli.py:110 | `test_cli_real_repo_memory` not guarded by `INTEGRATION` env | Intentional — this is the load-bearing acceptance for the PLAN's primary value claim ("recent entry at line 258 surfaces"). Guarding behind INTEGRATION would let CI skip the only test that proves the bug was fixed. The test depends on a stable wiki.md anchor (`boundary-parse-test-layer | 2026-05-19`) that won't drift. |
| M9 | code-reviewer | spec.md.j2:62 | `is_codex` branch inside fenced bash block — non-Codex emits `!uv` which is Claude Code shell-shorthand, not POSIX bash | Working as intended (matches the existing `second_brain` invocation pattern in research.md.j2:75-82). Template doc-comment could be added but out of PLAN scope. |
| M10 | security-reviewer | test_memory_retrieve.py:12 | `test_module_does_not_import_anthropic` pops after import — weak guard | Integration-side test `test_cli_invocation_does_not_load_anthropic` runs in subprocess and is the real regression guard. Unit test kept as in-process smoke. |
| M11 | security-reviewer | research.md.j2:72 et al | Shell double-quote around `<topic>` placeholder — agent must shell-escape on substitution | Stage prompts already instruct the agent. Adding an in-line warning is template-doc work, advisory. |
| M12 | performance-reviewer | memory_retrieve.py:272 | O(n²) byte-counting in multi-entry byte-cap loop | Today: 97 entries × ~600 chars at pre_k=30 → ~3ms. Within sub-second budget. Replace before corpus crosses ~500 entries — track as follow-up. |
| M13 | performance-reviewer | memory_retrieve.py:160 | Entry token set recomputed every score_entry call | ~2ms at current scale. Defer; address with M12 in one performance pass. |
| M14 | performance-reviewer | memory_retrieve.py:213 | `_date_desc_key` called O(n log n) without precomputation | Negligible at current scale. Defer with M12/M13. |

## 🤝 Disagreements

None.

## 🛠️ Auto-fix manual extensions

The grade gate (Grade A ≥ Threshold A) means the formal auto-fix loop did not execute. As orchestrator I applied 5 manual-only P1 fixes inline because:

1. **M4 + M5** are real security vulnerabilities (stored prompt-injection vectors via committable wiki.md content) with trivial fixes (`html.escape` + `str.replace`).
2. **M1 + M2** are paired correctness bugs at the byte-cap edge — fixing one without the other leaves the regression-guard gap open.
3. **M3** restores PLAN-locked intent (the PLAN specified promoting `_WORD_RE` to public `WORD_RE` in `relevance.py`; my initial implementation only aliased on the consumer side).

Each fix added a dedicated regression test:
- `test_render_byte_cap_single_oversized_with_long_topic`
- `test_render_neutralizes_fence_close_in_entry_body`
- `test_render_escapes_double_quote_in_topic`

Post-fix verification: 46 in-scope tests green; ruff check + format clean; mypy strict clean.

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | A     | 6 (5 manual P1 + 1 P2)   | 8 (advisory P2)      | 3 regression tests   |

Final grade: **A**
Iterations used: 1 / 3
Status: **APPROVED**
human_review_needed: **false**

P2 items M7–M14 are surfaced for awareness; none block wrapup. Performance items (M12–M14) should be revisited if the memory corpus crosses ~500 entries; until then the implementation is well within the sub-second-per-stage budget.
