---
type: review
task_slug: spoton-codex-rm-stash-rootcause
status: APPROVED
created: 2026-06-02
reviewers_invoked: [security-reviewer, code-reviewer]
consensus_method: cross-check
drift_verdict:
  result: clean
  scope_violations: []
  scenario_misses: []
  task_slug: spoton-codex-rm-stash-rootcause
  computed_at: 2026-06-02T00:00:00Z
final_grade: A
iterations_used: 1
human_review_needed: false
---

# REVIEW — spoton-codex-rm-stash-rootcause (2026-06-02)

## 🎯 Round 1 Summary

- **Grade: A** (consensus-passed P0=0, P1=0).
- Diff under review: the 12 staged files in harness-maker (3 agent templates +Bash on `tools:`, 2 test files, 5 version files + uv.lock, CHANGELOG). The spoton remediation lives in a separate repo (commit `4cfae0b`) and is out of this repo's review scope.
- Redaction (2-pass) was moot — uncommitted working-tree diff has no PR title/author/commit metadata to anchor on; a single contextual reviewer pass was run.
- 1 consensus-passed P2 (test-hardening) applied in-round; no grade-affecting findings. Status: **APPROVED**.

## 🔍 Drift Findings

`drift_verdict: clean`. All 12 staged files map to PLAN scope:
- Phase 1: 3 agent templates + `test_render_codex_permission_injection.py` ✅.
- Phase 1 consequence: `test_agent_body_partials.py` SHA pins (expected — the template change shifts the rendered agent hash; not scope drift).
- Phase 2: 5 version files + CHANGELOG ✅; `uv.lock` is the expected consequence of the `pyproject.toml` bump.
- No file outside PLAN scope; no in-scope file left unchanged. PLAN has no `common_ground_marks` → Step 2.5 (silent-intent-miss hook) not applicable.

## ✅ Consensus Findings

### P2 (does not affect grade) — APPLIED
- **`consensus-passed [2/2]` · `tests/unit/test_render_codex_permission_injection.py:114` · loose `"Bash" in line` substring.**
  - OBSERVE (both reviewers): the tools-Bash assertion used `"Bash" in line`, a substring check.
  - INFER: a malformed token like `BashFoo` would satisfy it (false-pass).
  - CONCLUDE: weaken regression guard. Same execution risk identified by both → strong consensus.
  - **Fix applied this round:** parse the line into tokens and assert membership — `tools = [t.strip() for t in line.removeprefix("tools:").split(",")]; assert "Bash" in tools`. Targeted test re-run GREEN, ruff clean, re-staged.

## ⚠️ Weak Consensus

None.

## 📝 Manual-Only Findings

- **P2 · `tests/unit/test_render_codex_permission_injection.py:131` (deny-quartet whole-document substring)** — *code-reviewer only*. The quartet check scans the whole rendered body, not just the deny block. Safe today (the quartet tokens appear nowhere else), so left as-is; recorded for future hardening (scope to the `deny:` block).
- **P2 · `templates/agents/{code-reviewer,consensus-arbiter,plan-validator}.md.j2:5` (unconditional Bash)** — *security-reviewer only*. Granting `Bash` even when `codex_second_opinion` is disabled is a hair looser than gating it on `_csoo.enabled`. Explicitly chosen in ADR-001 (the deny floor is unconditional, `tools:` can't argument-scope anyway, and unconditional avoids a render-time lockstep bug). Defensible-as-is; not applied.
- **P3 · disabled-state Bash exposure** — *security-reviewer only*. When codex is disabled the agent carries the Bash tool with no allow entry; every command falls through to an ask-prompt and the deny quartet still hard-blocks dangerous verbs. No auto-exec exposure. Informational.

## 🤝 Disagreements

None — both reviewers independently returned no P0/P1 and converged on the single P2 test-hardening. Confirmations cross-checked:
- **Deny-quartet completeness:** both confirmed all 3 templates carry `python/node/sh/bash` + rm/curl/npm/eval → the REVIEW-M7 `sh -c "…"` escape stays closed. No security regression from making the deny list the sole barrier.
- **SHA-pin version-independence:** code-reviewer verified `_render_agent` renders the raw template (no provenance/version block), so the 0.28.5 bump does not invalidate the 3 pins; only the 3 changed agents got new hashes. (Literal hex correctness is the quality-gate's job — full suite already GREEN.)
- **Version sync:** all 5 canonical files + uv.lock consistently at 0.28.5.
- **CHANGELOG:** accurate, including the "incidentally restores `code-reviewer`'s `Bash(git diff:*)`" claim (those git allow-entries were inert without the Bash tool).

## ⚑ Pre-release advisory (out-of-diff, not grade-affecting)

`tests/manual/CODEX_PERMISSION_PROBE.md` (`Last run: TBD`) is the only check that the fix works at *runtime* — i.e. that Claude Code's permission evaluator honors `Bash(codex exec:*)` (allow) given a bare `Bash` tool + the interpreter denies, and doesn't let the denies shadow the allow. This is statically undeterminable. **Run the manual probe before the 0.28.5 user-facing release**, since this diff is what activates the previously-inert path. (Pre-existing manual gate; surfaced by security-reviewer.)

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | A     | 1 (consensus P2 test-hardening) | 0 consensus / 3 manual-only | 0 |

Final grade: **A**
Iterations used: 1 / 3
Status: **APPROVED**
human_review_needed: false
