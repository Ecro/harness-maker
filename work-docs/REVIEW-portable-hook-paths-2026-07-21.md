---
type: review
task_slug: portable-hook-paths
status: APPROVED
created: 2026-07-21
reviewers_invoked: [code-reviewer, security-reviewer, codex, antigravity]
consensus_method: cross-check
drift_verdict:
  result: clean
  scope_violations: []
  scenario_misses: []
  task_slug: portable-hook-paths
  computed_at: 2026-07-21
final_grade: A
human_review_needed: false
---

# REVIEW — portable-hook-paths

## 🎯 Round 1 Summary

- **Grade: A** (0 consensus-passed P0, 0 consensus-passed P1).
- **Status: APPROVED**, `human_review_needed: false` (no unverified P0/P1).
- Reviewers: `code-reviewer` (1 P2 + 3 P3), `security-reviewer` (0 findings). Cross-model
  second opinions both graceful-degraded this round: **codex — skipped** (`codex exec` exit 1,
  empty output), **antigravity — failed** (exit 0 but no parseable JSON payload). Both ledgered
  to `.claude/observability/second-opinion.jsonl`; verdict is Claude-reviewer-derived and valid.
- One real coverage gap (P2) was fixed in this round even though single-source (`manual-only`) —
  it strengthens the ADR-005 guard on my own deliverable and is test-locked.

## 🔍 Drift Findings

`drift_verdict: clean`. Every changed file maps to a PLAN phase scope:
Phase 1 (`synthesize.py`, `test_install_ref.py`), Phase 2 (4 hook templates, `render.py`,
`conftest.py`, `test_portable_hooks.py`), Phase 3 (`regenerate.py`, 8 snapshots), Phase 4
(`docs/migration/`, `CHANGELOG.md`), Phase 5 (5 version files) + `uv.lock` (version reflection)
+ the PLAN doc. No scope drift; no incomplete phase.

## ✅ Consensus Findings

None. The two Claude reviewers had no overlapping findings (security-reviewer returned empty),
and both cross-model voters degraded — so no finding reached surface+reasoning consensus. All
findings below are `manual-only` (single-source).

## ⚠️ Weak Consensus

None.

## 📝 Manual-Only Findings

### P2 — leak-check assert did not cover the fresh cursor/codex `_render_pure_json` path (code-reviewer) — **FIXED**
- **OBSERVE**: `_assert_portable_install_ref` was wired only into `_render_settings_json` and
  `_render_hooks_json_merged`. On a FRESH render (no existing hooks.json → not in
  `json_merge_paths`), `.cursor/hooks.json` and `.codex/hooks.json` dispatch to
  `_render_pure_json` (render.py:1400-1411), which had no assert.
- **CONCLUDE**: 2 of 3 IDE hook surfaces bypassed the ADR-005 guard on the common path — they
  rendered portably only because `_portablize_ref` centralized the substitution, not because the
  guard verified it. A future `_portablize_ref` regression would leak into cursor/codex silently
  while only Claude `settings.json` raised.
- **Fix applied**: added `_assert_portable_install_ref(fe.context.get("harness_maker_src_path"))`
  at the top of `_render_pure_json` (no-op for `.cursor/mcp.json` / schemas — no install ref in
  context). Regression lock: `test_leaked_ref_raises_on_fresh_cursor_codex_render` renders a
  home-prefixed leak through the fresh cursor/codex path and asserts it now RAISES.

### P3 — home-boundary predicate duplicated between `render._assert_portable_install_ref` and `synthesize._portablize_ref` (code-reviewer) — accepted
- Two 2-line copies of `x == home or x.startswith(home + os.sep)` in different modules. DRY nit;
  left as-is (extracting a shared helper adds cross-module coupling for 2 lines). Noted so a
  future change to the boundary rule updates both copies.

### P3 — command/skill `.md` bodies render unquoted `--with $HOME/...` (code-reviewer) — accepted (ADR-003)
- This is the ADR-003 / Risk R2 accepted decision: command bodies stay unquoted (POSIX-only,
  space-free homes). Pre-existing severity (literal paths were also unquoted). Not a defect.

### P3 — stale-hooks retirement now compares against a `$HOME`-form pristine render (code-reviewer) — accepted (Risk R3)
- `render_stale_hooks_json_bytes` pristine bytes now contain `$HOME`, so an old-version on-disk
  `.claude/hooks/hooks.json` (literal-path pristine) won't byte-match → WARN/preserve branch
  instead of RETIRED. Matches PLAN Risk R3 (documented in `docs/migration/`); the direction is
  safe (preserve, never wrongful delete). No action required.

## 🤝 Disagreements

None — security-reviewer found nothing that contradicts code-reviewer; no severity conflicts.

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | A     | 1 (P2 guard-coverage, + regression test) | 3× P3 (accepted) | 0 |

Final grade: **A**
Iterations used: 1 / 3
Status: **APPROVED**
human_review_needed: **false**

Post-fix verification: `ruff` + `ruff format` + `mypy --strict` clean on `render.py`; targeted
render/snapshot/invocation tests green; full suite re-run green (see stage output).
