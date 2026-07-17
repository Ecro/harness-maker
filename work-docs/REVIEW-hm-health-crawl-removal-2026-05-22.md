---
type: review
task_slug: hm-health-crawl-removal
status: APPROVED
created: 2026-05-22
reviewers_invoked: [code-reviewer]
consensus_method: cross-check
drift_verdict:
  result: clean
  scope_violations: []
  scenario_misses: []
  task_slug: hm-health-crawl-removal
  computed_at: 2026-05-22T15:30:00Z
---

# REVIEW — hm-health-crawl-removal (2026-05-22)

## 🎯 Round 1 Summary

| Field | Value |
|-------|-------|
| Reviewer | code-reviewer (sonnet, single-pass) |
| Diff size | 62 files, +522/-2439 LOC |
| Initial grade | **B** (2 P1, 8 P2 — single-source, all `manual-only` per consensus filter) |
| Auto-fix mode | operator-driven (single reviewer = no `consensus-passed` structurally possible; findings independently verified by file-read) |
| Round 2 grade | **A** (all P1 + 7 of 8 P2 resolved; 1 P2 deferred to /hm:wrapup per PLAN Phase 6) |
| Status | **APPROVED** |
| human_review_needed | false |

## 🔍 Drift Findings

None. The 62-file diff maps exactly to PLAN-hm-health-crawl-removal Phases 1-5
scope. Phase 6 (rendered output regeneration) is intentionally deferred to
/hm:wrapup post-finalize per `[wiki:pattern] snapshot-regen-on-main-not-worktree-discipline`.

## ✅ Round 1 Findings — Resolved in Round 2

### P1 (2)

| # | File | Line | Summary | Status |
|---|------|------|---------|--------|
| 1 | `src/harness_maker/templates/skills/verify-before-completion/SKILL.md.j2` | 3, 8, 17, 64-69, 95, 99 | "6 checks" + dead Check 4 (anti-rot pending queue) + `/hm:refresh` remediation hint pointing to deleted command | **Fixed**: full rewrite to 5-check protocol; Check 4 (anti-rot) deleted; Check 5/6 renumbered to 4/5; description + remediation hint scrubbed |
| 2 | `.claude-verify.sh` | 505 | `phase_11_commands` requires `tests/e2e/sandbox/.claude/commands/hm/refresh.md` which is no longer generated; running `bash .claude-verify.sh all` would fail | **Fixed**: `refresh` removed from the cmd loop list |

### P2 (8) — 7 fixed + 1 deferred

| # | File | Line | Summary | Status |
|---|------|------|---------|--------|
| 3 | `src/harness_maker/synthesize.py` | 559 | Docstring "Existing 11 skills" — actual count 9 | **Fixed**: "Existing 9 skills (ADR-0007 ...)" |
| 4 | `src/harness_maker/communication_audit.py` | 46 | Docstring "5 LLM-judgment skill" — PINNED_SKILLS has 4 | **Fixed**: "4 LLM-judgment skill (ADR-005; relevance-filter removed in 0.22.3)" |
| 5 | `src/harness_maker/templates/agents/_standards/_template.md.j2` | 9 | User-facing reference to `/hm:refresh` watching `last_reviewed_at` — command deleted | **Fixed**: rephrased to "`last_reviewed_at` field is preserved as provenance metadata" |
| 6 | `.claude-verify.sh` | 623-628 | Skill assertion list labeled "8" — _ALL_SKILLS has 9; `refdocs-search` missing | **Fixed**: label → "9"; `refdocs-search` added to assertion list |
| 7 | `tests/unit/test_codex_phase7.py` | 107 | Section comment "11 + 7 = 18 skill paths" stale | **Fixed**: "9 + 7 + 1 + 1 = 18" |
| 8 | `.claude/skills/research-crawler/`, `.claude/skills/relevance-filter/`, `.agents/skills/...`, `.claude/.harness-manifest.json` | — | Stale rendered output + manifest at v0.22.2 | **Deferred to /hm:wrapup Phase 6**: PLAN Phase 6 explicitly schedules `/hm:make --update` post-finalize per `[wiki:pattern] snapshot-regen-on-main-not-worktree-discipline`. Will be regenerated alongside v0.22.3 commit. |
| 9 | `src/harness_maker/observability/dashboard.py` | 236 | `_parse_int` dead code (only consumer was the deleted external_risks parser) | **Fixed**: function deleted |
| 10 | `CHANGELOG.md` | 27 | Stale line reference "cli.py:1709" — actual line shifted to 1507 after deletions | **Fixed**: line number removed (internal refs rot quickly; no reader value) |

## ⚠️ Weak Consensus

None.

## 📝 Manual-Only Findings

None outstanding.

## 🤝 Disagreements

None.

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | B     | —             | 10        | —   |
| 2 (fix)   | A     | 9             | 1 (deferred to wrapup) | 0 |

**Final grade**: A
**Iterations used**: 2 / 3
**Status**: APPROVED
**human_review_needed**: false
**Deferred to wrapup**: 1 item (rendered output regeneration — PLAN Phase 6 scope; not a regression, intentional sequencing per the worktree-finalize discipline)

## Verification (post-fix)

- `uv run pytest tests/unit/test_codex_phase7.py tests/unit/test_communication_audit.py tests/unit/test_observability_dashboard.py tests/snapshot` → **67 passed in 0.99s**
- `uv run mypy --strict src/` → **Success: no issues found in 96 source files**
- All P1 fixes preserve schema (verify command still emits 5-check protocol; verify-before-completion SKILL.md.j2 frontmatter updated; .claude-verify.sh:505 no longer fails on missing refresh.md)
- Auto-fix did not introduce any new findings (build green; same test count + 0 regressions)
