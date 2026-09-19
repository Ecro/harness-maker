---
type: review
task_slug: mission-context-loop
status: CHANGES_REQUESTED
human_review_needed: true
created: 2026-09-19
reviewers_invoked: [code-reviewer, security-reviewer, concurrency-reviewer, test-reviewer, codex]
consensus_method: cross-check
run_id: 76038fa71543
review_base: 555ca93378a15caaa98702fd51bedf30bcfbad89
drift_verdict:
  result: scope_violation
  scope_violations:
    - CLAUDE.md
    - src/harness_maker/models.py
    - tests/unit/test_render_wrapup_delegation.py
    - tests/unit/test_synthesize.py
    - tests/structural/test_roundtrip_budget.py
    - tests/structural/test_autopilot_gate_render.py
    - tests/structural/autopilot_gate_golden.json
    - tests/structural/test_command_size_budget.py
    - tests/structural/surface_baseline.json
    - work-docs/MATRIX-native-redundancy.md
  scenario_misses: []
  task_slug: mission-context-loop
  computed_at: 2026-09-19T03:10:00Z
---

# REVIEW — mission-context-loop

## 🎯 Round 1 Summary

- **Grade: B.** consensus-passed P0 0, P1 1, P2 3.
- **Lens coverage:** all 7 lenses exercised; `blocks_approval: false`.
- **Fixes pending:** 1 (P1 `3b1eeac67cfed281`, shell interpolation of DRI text in the skill).
- **Manual items:**
  - 2 × P1 `manual-only`. These are Codex findings `accepted` by PIDA with a single
    cross-model voice, so `human_review_needed` = true.
  - 2 × Codex `unresolved` (Section 7).

## 🔍 Drift Findings

P1, recorded rather than graded.

- **Incomplete phase:** none. Every PLAN phase's scope changed.
- **Scope drift, pre-plan operator request:**
  - `CLAUDE.md` and `src/harness_maker/models.py` hold the Cursor-asset doc corrections the
    operator asked for during research (commit 98e16aa1).
  - `interview.py`'s docstring edit is in the same commit. The file is also in P2's scope.
- **Scope drift, hand-maintained sites the PLAN did not name.** Each is recorded in the PLAN's
  Phase 3/4/5 execution notes and in BASELINE-DELTA §3:
  - `test_render_wrapup_delegation.py`
  - `test_synthesize.py`
  - `test_roundtrip_budget.py`
  - `test_autopilot_gate_render.py` + `autopilot_gate_golden.json`
  - `test_command_size_budget.py`
  - `surface_baseline.json`
  - `MATRIX-native-redundancy.md`
- **SPEC scenarios without coverage:** none. S1–S3 live behaviour stays manual, post-release,
  by design (SPEC Verification table).

## ✅ Consensus Findings

| id | sev | lens | file:line | summary | disposition |
|---|---|---|---|---|---|
| 3b1eeac67cfed281 | P1 | security | `templates/skills/project-knowledge/SKILL.md.j2:31` | DRI-stated free text is interpolated into a shell-quoted `--topic "<subject>"` / `--slug '<subject>'`; backticks / `$()` / quotes break out before `memory_md` validates anything | accepted |
| b6a575683b2bb562 | P2 | consistency | `templates/cursor/rules/harness.mdc.j2:132` | the pointer partial's `ko` arm splices Korean into the single English-only Cursor rule file | accepted |
| 17aedfeace291dfe | P2 | design | `memory_retrieve.py:437` | `resolve_memory_dir` calls `memory_md._memory_dir`, a private helper, across modules | accepted |
| 7fb60872adf38349 | P2 | concurrency | `worktree.py:743` | mid-conversation captures widen the window in which a peer `/hm:loop` finalize stashes an in-flight `[wiki:fact]` (hm/* task worktrees skip finalize) | accepted |

## ⚠️ Weak Consensus

(none)

## 📝 Manual-Only Findings

| id | sev | source | file:line | summary | disposition |
|---|---|---|---|---|---|
| 19b3f7f1f0100b4f | P1 | codex (PIDA accepted) | `templates/stages/wrapup.md.j2:405` | 5.1.0 guards only what `memory_retrieve` returns (top-k, zero-overlap dropped). A new slug that collides with an unsurfaced `[wiki:fact]` still overwrites it; the skill has the symmetric case | accepted |
| 4444994ec2c7ab6f | P1 | codex (PIDA accepted) | `scripts/measure_wiki_fact_window.py:81` | an uncommitted in-window capture that is corrected after the window closes but before any land loses its original date from both inputs | accepted |

## 🤝 Disagreements

- **Security lens P1 `3b1e` vs Codex P1 `f9f5` (same defect).** PIDA left Codex `unresolved`
  ("the DRI is the text source"). The security lens, with the public-plugin consumer context
  restored in Pass 2, kept it as P1. Only the lens voice votes.
- **Concurrency P1 → P2.** Pass 2 narrowed the finding to the `/hm:loop` path.
- **Core P3 dropped in Pass 2.** It had flagged the bundled doc fix as unrelated; the metadata
  showed the operator explicitly requested it.

## 🧊 Cross-model findings (frozen @ round 1)

frozen_at_round: 1 · models: [codex]

| id | source | severity | file | line | summary | evidence | needs_relaxation | disposition | oracle_result | status | invalidation_reason |
|---|---|---|---|---|---|---|---|---|---|---|---|
| f9f5d69d0d365f8a | codex | P1 | src/harness_maker/templates/skills/project-knowledge/SKILL.md.j2 | 31 | DRI-derived subject in `--topic "<subject>"` can run unintended shell commands (Codex + wrapup search lines too) | double quotes still expand `$(...)` and backticks | false | unresolved | no oracle; same pattern as pre-existing 5.2, DRI is the text source | pending | |
| 19b3f7f1f0100b4f | codex | P1 | src/harness_maker/templates/stages/wrapup.md.j2 | 405 | a new slug colliding with a fact missed by the bounded search overwrites it; symmetric in the skill | search limited by pre-k 30 / byte-cap; `_upsert` replaces category + body on slug hit | false | accepted | same-slug write erases a fact (hazard pin test); 5.1.0 guards only top-k results | pending | |
| 09cf56fcd7ad5e2e | codex | P2 | src/harness_maker/templates/skills/project-knowledge/SKILL.md.j2 | 34 | an additive fact on the same subject is treated as a correction and replaces the body | "If a [wiki:fact] entry covers the same subject, reuse its slug: that is a correction." | false | unresolved | model-judgment path the code cannot decide | pending | |
| 4444994ec2c7ab6f | codex | P1 | scripts/measure_wiki_fact_window.py | 81 | uncommitted in-window capture corrected after window, before first land, loses its date | `earliest_fact_dates` reads git history + working tree only; correction re-dates the heading | false | accepted | correction re-dates (memory_md.py:352); no input keeps the original date | pending | |

### Iteration 2 (Grade: B → A)
Fixes applied: 1
| # | Severity | Summary | File | Status |
|---|----------|---------|------|--------|
| 1 | P1 | DRI free text shell-interpolated into `--topic` / `--slug` → agent-composed `[a-z0-9 -]` search words and kebab slug, single-quoted, with an explicit "never paste the DRI's wording into a command" | `src/harness_maker/templates/skills/project-knowledge/SKILL.md.j2:24-41` | Applied · caused_by=none |

Verification: `tests/render/test_render_project_knowledge.py`, `tests/snapshot`, `test_codex_phase7`, `test_synthesize_codex` → 81 passed (snapshots regenerated in the worktree, skill hash only).
rereview: skipped — churn 0.27 < 0.30
Lifecycle: `3b1eeac67cfed281` pending → resolved (fix applied, verification passed) — progress.
Remaining: 5 (3 × P2 consensus-passed, 2 × P1 manual-only) | New issues introduced: 0
Churn: 0.267 (max: src/harness_maker/templates/skills/project-knowledge/SKILL.md.j2, measured 9, excluded 0)

## 🔎 Confirmation pass confirm-1 (freeze bb10edbf, span 555ca933..bb10edbf) — dirty

All 7 lenses exercised (`blocks_approval: false`). New findings, absent from every prior round's `consensus-passed` set:

| id (lens) | sev | file:line | summary | disposition |
|---|---|---|---|---|
| sec-c1 (security) | P1 | `SKILL.md.j2:26` | round-2 fix is prompt-only: the agent-composed `--topic '<search words>'` / `--slug '<slug>'` still reach a shell string; suggested `--topic-file`/`--slug-file` | **unresolved / no-contract.** The operator accepted the residual risk (2026-09-19). The same pattern is harness-wide: wrapup 5.1 has used `--slug '<slug>'` since before this task. The structural fix would cross the `memory_md.py` boundary and extend a CLI, so it is filed as a follow-up. It counts toward the grade. |
| tst-c1 (tests) | P1 | `tests/render/test_render_project_knowledge.py:23` | AC-004 tokens never pin the round-2 fix, so reverting it passes every test | accepted → fixed in the repair round |
| con-c1 (concurrency) | P2 | `SKILL.md.j2:24` | search-then-write across sessions can create duplicate `[wiki:fact]` entries for one subject | accepted, follow-up (P2 does not grade) |

Core lenses: no new finding. They confirmed the round-2 fix is sound as instruction, and that
`world.run_measure` records nothing on the script's exit 2 / 3.

### Repair round (confirm-1 → confirm-2; budgeted separately, `iteration_count` unchanged)
| # | Severity | Summary | File | Status |
|---|----------|---------|------|--------|
| 1 | P1 | pin the round-2 fix with a regression test (search step keeps DRI text out of the shell, restricted alphabet, single quotes, no `<subject>`) | `tests/render/test_render_project_knowledge.py` (`test_skill_search_step_keeps_dri_text_out_of_the_shell`) | Applied · caused_by=3b1eeac67cfed281 |

Discrimination check: against the pre-fix skill (`refs/hm-churn/v1/mission-context-loop-r2-pre`) the new test is RED (2 failed); against the fixed skill the file is green (29 passed).

## 🔎 Confirmation pass confirm-2 (freeze 3642a2ca, span 555ca933..3642a2ca) — clean of new severe

All 7 lenses exercised. The only new finding is a core P2: the PLAN is still `status: planning`.
It is **rejected**, authority `docstring:src/harness_maker/surface_allowance.py:_ACTIVE_STATUSES`
("Only `wrapup` writes the terminal `complete`"); wrapup Step 4 owns that flip. The security,
concurrency and tests lenses reported nothing new. The tests lens confirmed the repair test. The
security lens noted, without filing, that a future hardening of the shell-argument class should
also cover wrapup 5.1.0/5.2's `--topic "…"`, which is pre-existing convention and not introduced
here.

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | B     | —             | 6         | —   |
| 2         | A     | 1             | 5         | 0   |
| repair (confirm-1 → confirm-2) | B | 1 | 7 | 3 (confirm-1) |

Final grade: **B**. Only one consensus-passed P1 remains: `sec-c1-prompt-only-guard`,
dispositioned `unresolved / no-contract` after the operator accepted the residual risk. It has no
AC to cite, so it counts by design.
Iterations used: 2 / 3 (+1 confirmation repair round, budgeted separately)
Exit reason: converged. The loop reached A at round 2; confirm-1 then raised a new P1 that the
operator accepted as residual rather than fixed.

## 📏 Size & Complexity

| File | LOC | Cyclomatic | Max nesting | Status |
|------|-----|------------|-------------|--------|
| src/harness_maker/templates/skills/project-knowledge/SKILL.md.j2 | 56 → 60 | null → null | null → null | not-python |
| tests/snapshot/*.expected.yaml (8) | 187 → 187 | null → null | null → null | not-python |

Status: CHANGES_REQUESTED
human_review_needed: true
Counters (see §5): unreviewed 1 (round 2's fix, whose re-review the churn gate skipped; the
confirmation passes then covered it) · prior-fix 1 (`tst-c1` caused_by `3b1eeac67cfed281`) ·
unattributed 0

### For the human reviewer

1. **Accepted residual, P1 `sec-c1`.** Agent-composed search words and slugs still reach a shell
   string. They are guarded by a restricted alphabet, single quotes, and "never paste the DRI's
   wording", now pinned by a test. **Follow-up task:** `--topic-file` / `--slug-file`, covering
   harness-wide `--topic "…"` / `--slug '…'` sites including wrapup 5.1.0/5.2.
2. **Codex-accepted manual-only P1 `19b3f7f1f0100b4f`.** A new slug that collides with a fact not
   surfaced by the top-k search still overwrites it, and the skill has the symmetric case. A fix
   needs an exact-slug existence check before writing.
3. **Codex-accepted manual-only P1 `4444994ec2c7ab6f`.** A capture made uncommitted inside the
   window, then corrected after the window closes but before the first land, loses its date
   from the measurement. Narrow, but it could flip the pre-registered 0-vs-1 decision.
4. **P2s** for a later sweep:
   - harness.mdc ko arm;
   - the private `memory_md._memory_dir` used cross-module;
   - the `/hm:loop` finalize-stash exposure;
   - the cross-session duplicate-fact race.
