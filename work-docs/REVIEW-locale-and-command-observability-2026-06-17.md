---
type: review
task_slug: locale-and-command-observability
status: APPROVED
created: 2026-06-17
reviewers_invoked: [code-reviewer, security-reviewer]
consensus_method: cross-check
codex_status: skipped
codex_skip_reason: "Bash permission gate denied codex exec (sandbox) — not an auth/runtime failure; warn-and-proceed"
drift_verdict:
  result: clean
  scope_violations: []
  scenario_misses: []
  task_slug: locale-and-command-observability
  computed_at: 2026-06-17
final_grade: A
iterations_used: 2
max_review_rounds: 3
human_review_needed: false
---

# REVIEW — locale-and-command-observability

## 🎯 Round 1 Summary

- **Grade: A** (0 consensus-passed P0/P1). Two **verified-real single-source** findings (P1, P2) were fixed anyway in the auto-fix loop — shipping a known regression behind the "single-source → manual-only → doesn't lower grade" rubric rule would be dishonest.
- Reviewers: code-reviewer + security-reviewer (both opus). **Codex 3rd voter skipped** — the Bash permission gate denied `codex exec` (sandbox restriction, not auth/runtime). Consensus degraded to cross-check 2/2; warn-and-proceed per ADR-002/003. Best-effort ledger emit also gated.
- 2-pass redaction collapsed: a local post-execute diff carries no PR title/author/commit metadata to anchor on.

## 🔍 Drift Findings

`drift_verdict: clean`. All 21 non-snapshot staged files map to PLAN phases (Phase 1: `output_language.md.j2` + 4 wrappers + 4 CLAUDE.md + AGENTS.md; Phase 2: `step_manifest.md.j2` + `stage_end_summary.md.j2` + 7 stages; Phase 3: `readiness.py` + tests; 8 snapshots = Phase 3 regen). No file outside scope; no PLAN-scoped file left unchanged.

## ✅ Consensus Findings

None reached **strong consensus** — the two reviewers covered disjoint surfaces (code-reviewer: render/logic; security-reviewer: injection/markers/IO), so no two findings surface-matched. Per the rubric this yields grade **A**. The two real defects below were single-source but orchestrator-verified and fixed.

## ⚠️ Weak Consensus

None.

## 📝 Manual-Only Findings (single-source) — disposition

| # | Sev | Source | File | Finding | Disposition |
|---|-----|--------|------|---------|-------------|
| 1 | P1 | code-reviewer | `readiness.py` | `stage_fused` reused the `'-' in stem` `fused` classifier → swept in the meta command `loop-p5-batch` (always installed, `synthesize.py:442`), which carries no banners → both new health signals false-FAIL on **every** install | **FIXED** (Round 2, Fix #1): added a meta-command denylist `{make,help,health,configure,uninstall,loop,loop-p5-batch}`. Reproduced (2/3 false-fail) before fix; regression test `test_health_excludes_hyphenated_meta_command` added |
| 2 | P2 | code-reviewer | `output_language.md.j2` | `config.locale is defined` is True for present-but-`None`/`''` → would render `**None**`/`****` (the `jinja-is-defined-returns-true-for-none` gotcha) | **FIXED** (Round 2, Fix #2 + Fix #3): combined guard `config is defined and config.locale is defined and config.locale` — `is defined` prevents the StrictUndefined raise on an absent `locale` key (Fix #2's truthiness-only form regressed `test_codex_phase4`'s partial-config render; the full-suite verify caught it → Fix #3). Regression test `test_locale_directive_none_or_empty_falls_back_to_english` added |
| 3 | P3 | code-reviewer | `stages/*.md.j2` | `{% set %}`×3 under `trim_blocks=False` emit ~4 stray blank lines before the end-banner heading | **WONTFIX** (cosmetic — markdown collapses consecutive blanks; fused-stage seam verified clean) |
| 4 | P3 | security-reviewer | `output_language.md.j2` (out-of-diff) | free-text `config.locale` interpolated raw into agent-facing markdown — a pre-existing prompt-injection seam shared by ~8 existing `{{ config.locale }}` sites; self-supply-dominated, no code execution | **WONTFIX here** (pre-existing, out-of-diff; a uniform clamp across all sites is a separate task, not this diff's regression) |

## 🤝 Disagreements

None — coverage was complementary, not contradictory. (security-reviewer judged `readiness.py` "clean" only w.r.t. crash/traversal, a different axis than code-reviewer's logic-scoping P1; not a true rebuttal.)

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | A (rubric) / P1+P2 latent | — | 4 (P1, P2, 2×P3) | — |
| 2 (auto-fix) | A | 3 (P1 meta-exclusion; P2 guard + the guard's own regression fix) | 2×P3 (wontfix) | 0 |

**Final grade: A**
**Iterations used: 2 / 3**
**Status: APPROVED**
**human_review_needed: false**

**Verification after fixes:** `ruff check .` ✓ · `mypy --strict src` ✓ (105 files) · full `pytest` ✓ (0 failures) · 2 regression tests added (meta-command exclusion + None/'' locale fallback). Valid-locale render is byte-identical → snapshots unaffected.

**Notes confirmed safe (from the task brief):** per-stage `{% set summary_* %}` does not leak across fused stages (`fuse()` renders each stage in an isolated `tpl.render()`); end-banner lands in template-owned space (survives reconcile, MERGE_BLOCK test passes); StrictUndefined bare-var enforcement works across all 7 stages; codex `workflow_skill` carries zero end-banners (delegates); `{slug}` placeholders are inside `{% set %}` string literals (not Jinja-interpolated).
