---
type: review
task_slug: mission-context-loop
status: APPROVED
human_review_needed: false
created: 2026-09-19
reviewers_invoked: [code-reviewer, security-reviewer, concurrency-reviewer, test-reviewer, codex]
consensus_method: cross-check
run_id: ae126b7682ec
review_base: 555ca93378a15caaa98702fd51bedf30bcfbad89
previous_review: "[[REVIEW-mission-context-loop-2026-09-19]]"
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
  computed_at: 2026-09-19T04:05:00Z
---

# REVIEW (re-review) — mission-context-loop

Re-review after the operator asked to fix the two Codex P1s from
[[REVIEW-mission-context-loop-2026-09-19]]:
- `19b3f7f1f0100b4f`: exact-slug check before a new slug.
- `4444994ec2c7ab6f`: first-recorded date carried forward and read by the measure.

Full suite before this run: 8777 passed (RC=0).

## 🎯 Round 1 Summary

- **Grade: B.** consensus-passed P1 2, P2 2; manual-only P2 2 (Codex, PIDA accepted).
- **Lens coverage:** all 7 lenses exercised; `blocks_approval: false`.
- **`human_review_needed`:** false.
- **Fixes pending:** 2 (P1 `92cde7ba0790a79f`, `df86b130c1c70c27`).

## 🔍 Drift Findings

Unchanged from the previous review: the operator-requested doc fix, plus the hand-maintained
sites the PLAN did not name. No incomplete phase, no scenario miss.

## ✅ Consensus Findings

| id | sev | lens | file:line | summary | disposition |
|---|---|---|---|---|---|
| 92cde7ba0790a79f | P1 | functionality | `templates/stages/wrapup.md.j2:406` | 5.1.0's exact-slug Grep names "the base wiki.md" with no path. From `<WT>` (the Production default) an agent reads the stale worktree copy, misses the fact, and the base-rooted `upsert-wiki` overwrites it | accepted |
| df86b130c1c70c27 | P1 | functionality | `templates/skills/project-knowledge/SKILL.md.j2:43` | the skill's exact-slug Grep says "the base checkout" with no rule for finding it from a worktree cwd | accepted |
| c8fec696784f18b1 | P2 | concurrency | `SKILL.md.j2:44` | Grep-then-write is TOCTOU: two sessions converging on one new slug means the last writer silently wins. This is distinct from the known duplicate race | accepted |
| 316a8185e32b954b | P2 | tests | `tests/render/test_render_project_knowledge.py:220` | the exact-slug test's token oracle cannot see whether base-path resolution is stated | accepted |

## ⚠️ Weak Consensus

(none)

## 📝 Manual-Only Findings

| id | sev | source | file:line | summary | disposition |
|---|---|---|---|---|---|
| 9392ab8d2827dba1 | P2 | codex (PIDA accepted) | `SKILL.md.j2:44` | when the exact-slug Grep finds a same-subject `[wiki:fact]` the search missed, "pick another slug" leaves the wrong old claim beside the correction (SPEC S2) | accepted |
| b61fe493da38eabc | P2 | codex (PIDA accepted) | `scripts/measure_wiki_fact_window.py:89` | `(first recorded <date>)` is matched on any body line, so prose can move a capture date. It should be restricted to the `Supersedes:` line | accepted |

## 🤝 Disagreements

- **Security P2 on 5.1.0's double-quoted `--topic`.** Dropped in Pass 2. It is the same
  pre-existing convention as the plan/spec/research/5.2 call sites, and it is covered by the
  operator-accepted harness-wide follow-up.

## 🧊 Cross-model findings (frozen @ round 1)

frozen_at_round: 1 · models: [codex]

| id | source | severity | file | line | summary | evidence | needs_relaxation | disposition | oracle_result | status | invalidation_reason |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 9392ab8d2827dba1 | codex | P2 | src/harness_maker/templates/skills/project-knowledge/SKILL.md.j2 | 44 | exact-slug hit on a same-subject fact → "pick another slug" leaves the old claim beside the correction | lines 44–45 say pick another slug whatever its category | false | accepted | SPEC S2 requires one heading; the skill routes a missed same-subject correction to a new slug | resolved | |
| b61fe493da38eabc | codex | P2 | scripts/measure_wiki_fact_window.py | 89 | `(first recorded …)` in ordinary prose is read as capture metadata | repro: "The vendor incident (first recorded 2026-09-25) remains unresolved." → capture date 2026-09-25 | false | accepted | `_FIRST_RECORDED.search` runs on every fact body line; `_note` keeps the minimum | pending | |

### Iteration 2 (Grade: B → A)

§5 batch trigger (a) fired: two findings share the exact-slug check.

Per-group block:
- `group_key`: `exact-slug-check`, covering skill step 2 and wrapup 5.1.0.
- `covered_finding_ids`: `92cde7ba0790a79f` and `df86b130c1c70c27` were selected. In-model
  dimensions: `9392ab8d2827dba1`, `c8fec696784f18b1`, `316a8185e32b954b`.
- Dimensions:
  - (a) which file: the base checkout, from any cwd, is two levels above `.worktrees/<name>/`;
  - (b) what a hit means per writer: the skill reuses a same-subject fact the DRI is
    correcting, and otherwise picks another slug; wrapup always picks another;
  - (c) check and write are not atomic, so the last write wins, and the text now says so;
  - (d) the test pins the resolution phrase.
- One consolidated edit.

Fixes applied: 1 (consolidated)
| # | Severity | Summary | File | Status |
|---|----------|---------|------|--------|
| 1 | P1 | exact-slug Grep now states the base path ("two levels above" `.worktrees/<name>/` / `<WT>`; worktree copy is stale), reuses a same-subject fact on correction (skill), states check/write are not atomic; test pins "two levels above" + "stale" | `SKILL.md.j2:42-48`, `wrapup.md.j2:406-408`, `tests/render/test_render_project_knowledge.py` | Applied · caused_by=none |

Verification (targeted `targeted-test-selection`):
- `tests/render/test_render_project_knowledge.py` + `tests/snapshot`: 46 passed.
- `tests/structural` + `test_render_wrapup_delegation.py`: 719 passed.

Surface consequences, all attributed in `BASELINE-DELTA-mission-context-loop.md` §3/§3.1:
- baseline re-frozen at claude 435 484 / codex 370 564 (+73 per variant);
- `autopilot_gate_golden.json` re-captured (wrapup only);
- wrapup body-line pins 729/762;
- §1 re-pinned.

rereview: skipped — churn 0.27 < 0.30

Lifecycle:
- `92cde7ba0790a79f`, `df86b130c1c70c27`, `9392ab8d2827dba1`, `c8fec696784f18b1`,
  `316a8185e32b954b`: pending → resolved. That counts as progress.

Remaining: 1 (`b61fe493da38eabc`, manual-only P2). New issues introduced: 0.
Churn: 0.267 (max: work-docs/BASELINE-DELTA-mission-context-loop.md, measured 15, excluded 0)

## 🔎 Confirmation pass confirm-1 (freeze 8916f885, span 555ca933..8916f885) — clean

All 7 lenses exercised (`blocks_approval: false`), and none of the four dispatches reported a
new finding. The core lens checked the round-2 fix directly:
- "two levels above" matches the only cwds an agent's tool calls produce (`<base>` or
  `.worktrees/<name>/`);
- the skill/wrapup divergence (the skill reuses a same-subject fact; wrapup never does) is
  deliberate;
- the non-atomic note is accurate.

→ **APPROVED.** No second confirmation pass was needed.

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | B     | —             | 6         | —   |
| 2         | A     | 1 (consolidated; 5 findings resolved) | 1 | 0 |

Final grade: **A**
Iterations used: 2 / 3
Exit reason: converged

## 📏 Size & Complexity

| File | LOC | Cyclomatic | Max nesting | Status |
|------|-----|------------|-------------|--------|
| src/harness_maker/templates/skills/project-knowledge/SKILL.md.j2 | 66 → 69 | null → null | null → null | not-python |
| src/harness_maker/templates/stages/wrapup.md.j2 | 826 → 827 | null → null | null → null | not-python |
| tests/render/test_render_project_knowledge.py | 243 → 247 | measured (see 5c payload) | — | measured |
| tests/unit/test_render_wrapup_delegation.py | 356 → 357 | measured (see 5c payload) | — | measured |

Status: APPROVED
human_review_needed: false
Counters (see §5): unreviewed 1 (round 2's consolidated fix skipped re-review under the churn
gate; confirm-1 then covered the whole span) · prior-fix 0 · unattributed 0

### Carried to a later sweep (non-grading)

- **P2 `b61fe493da38eabc` (Codex, manual-only).** `(first recorded …)` in prose is read as
  capture metadata. Restrict it to the `Supersedes:` line.
- **Operator-accepted residual from the previous review.** Agent-composed `--topic` / `--slug`
  are guarded by instruction. Harness-wide follow-up: `--topic-file` / `--slug-file`, together
  with the plan/spec/research/wrapup `--topic "…"` sites.
- **Earlier P2s:**
  - the harness.mdc ko arm;
  - the private `memory_md._memory_dir`;
  - the `/hm:loop` finalize-stash exposure;
  - the cross-session duplicate.
