---
type: review
task_slug: agent-model-version-agnostic
status: APPROVED
created: 2026-05-31
reviewers_invoked: [code-reviewer, code-reviewer, test-reviewer]
consensus_method: cross-check
drift_verdict:
  result: clean
  scope_violations: []
  scenario_misses: []
  task_slug: agent-model-version-agnostic
  computed_at: 2026-05-31T00:00:00Z
  note: >-
    All changed files map to PLAN phases. synthesize reverse-alias derivation
    and foreign_config._FOREIGN_MODEL_IDS are documented in-scope refinements of
    ADR-006 (the literal "reuse CURSOR_MODEL_IDS" was wrong — different
    namespace), not scope violations.
---

# REVIEW — agent-model-version-agnostic (execute diff)

Diff under review: uncommitted working tree (baseline HEAD `3d9b652`).
Source: foreign_config.py, models.py, synthesize.py · 14 agent templates + new
partial · harness.mdc.j2 · plan.md.j2 · 5 test files · 8 regenerated snapshots ·
Cursor checklist.

Reviewers launched with `model:"opus"` (in-repo agents carry the stale pin this
change fixes). Single contextual pass (working-tree diff has no PR metadata to
anchon on → Pass-1 redaction a no-op).

## 🎯 Round 1 Summary

Initial grade: **A** (0 consensus-passed P0/P1). Both code-reviewers: no P0/P1.
test-reviewer: **PASS** — confirmed the new guard *bites on revert* (real
synthesize→render pipeline, not a fixture/tautology) and the phase5 rewrites
*strengthen* coverage rather than echo inputs.

## 🔍 Drift Findings

None. `drift_verdict: clean`. The `synthesize` reverse-alias derivation and the
separate `_FOREIGN_MODEL_IDS` map are in-scope refinements of ADR-006 surfaced
during TDD (the literal "reuse CURSOR_MODEL_IDS" would have fed aider/Continue
an invalid Cursor-format id) — documented in code.

## ✅ Consensus Findings

| Tag | Severity | Finding | Sources | Disposition |
|-----|----------|---------|---------|-------------|
| consensus-passed [2/2] | P2 | `_FOREIGN_MODEL_IDS['opus']=claude-opus-4-8` skews from same-file `_LLM_MAP_MODEL=claude-opus-4-7` | code-reviewer ×2 | **Fixed** — bumped `_LLM_MAP_MODEL` → 4-8 + comment tying them together |
| consensus-passed [2/2] | P3 | partial `{% else %}sonnet` fallback diverges from ADR-002 `opus` floor | code-reviewer #1 + test-reviewer | **Fixed** — fallback → `opus` (dead branch; SHA test confirms zero render change) |

P2/P3 do not affect the grade; fixed anyway (cheap, verified).

## ⚠️ Weak Consensus

None.

## 📝 Manual-Only Findings

| # | Severity | Finding | Source | Disposition |
|---|----------|---------|--------|-------------|
| M1 | P1 | Repo's own dogfood `.claude/agents/*.md` still carry the pinned id (`claude-4-7-opus`/`claude-4-6-sonnet`) | code-reviewer #1 | **Deferred → wrapup/release** (this IS PLAN Phase 5's dogfood re-render; single-source, does not gate grade; must precede the 0.28.2 release) |
| M2 | P3 | All 6 foreign-config templates resolve via the boundary, not just aider/Continue; ADR-006 comment under-described | code-reviewer #2 | **Fixed** — comment broadened (doc-style templates get inert concrete prose) |
| M3 | doc | PLAN ADR-004 lists `memory_retrieve.py` as an SDK call site, but it makes no Anthropic SDK call | code-reviewer #2 | **Noted** — PLAN doc nit; not a code defect. Correct on wrapup PLAN update |

## 🤝 Disagreements

None on severity. Both code-reviewers independently confirmed: no missed
concrete-id surface, no SDK `messages.create` receives `config.default_model`
(ADR-004 holds), `readiness.py` unaffected, `--default-model opus` accepted.

### Iteration 2 (Grade: A → A)
Fixes applied: 2 consensus (P2 + P3) + 1 manual P3 (M2 comment).

| # | Severity | Summary | File | Status |
|---|----------|---------|------|--------|
| 1 | P2 | Align `_LLM_MAP_MODEL` to `claude-opus-4-8` | foreign_config.py | Applied |
| 2 | P3 | Partial fallback `sonnet` → `opus` | _partials/model_frontmatter_line.md.j2 | Applied (no render change) |
| 3 | P3 | Broaden ADR-006 comment to all 6 foreign templates | foreign_config.py | Applied |

Remaining: M1 (deferred Phase 5 dogfood re-render), M3 (PLAN doc nit).
New issues introduced: 0 (ruff + mypy clean; targeted + full suite excl e2e green).

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | A     | —             | 2 consensus + 3 manual | — |
| 2         | A     | 3             | M1 (deferred), M3 (doc) | 0 |

Final grade: **A**
Iterations used: 2 / 3
Status: APPROVED
human_review_needed: false

Verification: ruff ✓, mypy --strict ✓, full suite excl e2e green. 2 e2e
`plugin_live` tests time out spawning the live `claude` binary (environmental;
CI skips them). No `git commit` invoked from this stage (HEAD `3d9b652`).

**Must precede release (M1):** re-render the repo's own `.claude/` so its agents
carry the alias, then bump to 0.28.2 — the published 0.28.1 predates this change.
