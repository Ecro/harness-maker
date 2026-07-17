---
type: review
task_slug: readme-codex-truthification
status: APPROVED
created: 2026-05-22
reviewers_invoked: [code-reviewer]
consensus_method: cross-check
drift_verdict:
  result: clean
  scope_violations: []
  scenario_misses: []
  task_slug: readme-codex-truthification
  computed_at: 2026-05-22T15:30:00Z
---

# REVIEW — README Codex truthification

## 🎯 Round 1 Summary

| Metric | Value |
|---|---|
| Grade | **A** |
| Threshold | A |
| Consensus-passed P0/P1 | 0 / 0 |
| Manual-only findings | 4 (3 P1, 1 P2) |
| Fixes applied this round | 4 (manual orchestrator fixes, NOT auto-fix-loop) |
| Status | **APPROVED** |
| human_review_needed | false |

No consensus-passed findings (only one reviewer ran — single-source = `manual-only` by definition).
However, all 4 single-reviewer findings were correct and trivial to fix; applied them as
orchestrator-judgment manual fixes BEFORE the wrapup commit (same pattern as
`work-docs/REVIEW-codex-compat-fixes-2026-05-22.md`).

## 🔍 Drift Findings

PLAN Phase 5 scope included `.claude-plugin/plugin.json`, `.cursor-plugin/plugin.json`, and
`.claude-plugin/marketplace.json` "for peer consistency". None were modified — verified each
file already accurately describes its own plugin (Claude Code and Cursor have native install
paths via their own marketplaces; only Codex requires indirection). Phase 5 exit criterion
"descriptions consistent with ADR-001" is satisfied because the peer descriptions don't make
the false Codex-install claim that needed correcting. **Drift verdict: clean.**

## ✅ Consensus Findings

None. Single reviewer = no consensus pairs possible.

## ⚠️ Weak Consensus

None.

## 📝 Manual-Only Findings (all 4 applied before wrapup)

### P1-1 — `README.md:272` — Step 3 "After I confirm the reload/restart" contradicts new Codex no-reload branch
- **OBSERVE**: Step 2 Codex branch added by this diff ends with "No Codex reload is needed". Step 3 (unchanged by diff) opens "After I confirm the reload/restart".
- **INFER**: AI agent following the Codex path completes Step 2 without sending any reload message, then stalls at Step 3's precondition that will never fire.
- **CONCLUDE**: Long-form prompt is now self-contradictory for Codex users.
- **Applied fix**: Changed Step 3 opening to "After I confirm the reload (Claude Code / Cursor only — Codex needs no reload; for Codex, proceed immediately after install), invoke harness-maker:make..."

### P1-2 — `README.ko.md:241` — Same Step 3 contradiction in Korean mirror
- **OBSERVE**: Identical structural issue to P1-1, mirrored in `README.ko.md`.
- **Applied fix**: Same edit applied to `README.ko.md`.

### P1-3 — `tests/codex-compat/MANUAL_CHECKLIST.md:78` — `which uv tool install` is invalid shell
- **OBSERVE**: `which` takes a single binary name; passing three tokens (`uv tool install`) makes it look up `uv` only — returns exit 0 on any machine where `uv` is installed even if harness-maker was never installed via uv.
- **INFER**: Tester running this verification sees a false PASS for the PyPI install path — the exact failure case this check was meant to catch.
- **CONCLUDE**: Verification command produces false-positive PASS for "PyPI install succeeded" assertion.
- **Applied fix**: Replaced with `uv tool list | grep harness-maker` (actually lists installed uv tools).

### P2 — `.codex-plugin/plugin.json:4` — description was 238 chars; inline install detail likely truncated in marketplace tooltips
- **OBSERVE**: Codex marketplace UIs typically render plugin descriptions in fixed-width tooltips that truncate at ~100-150 chars.
- **INFER**: The "see README" suffix would be cut off before users see it, leaving them with only the broken-claim warning.
- **CONCLUDE**: Long description defeats the purpose of pointing users to README.
- **Applied fix**: Shortened from 238 → 145 chars: `"Per-project AI coding harness for Claude Code · Cursor · Codex. No native Codex marketplace install today — see README for working install paths."`

## 🤝 Disagreements

None.

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | A     | 4 (manual orchestrator) | 0 | 0 |

Final grade: **A**
Iterations used: 1 / 3
Status: **APPROVED**
human_review_needed: false
