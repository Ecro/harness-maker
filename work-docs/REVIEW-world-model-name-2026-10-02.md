---
type: review
task_slug: world-model-name
status: APPROVED
created: 2026-10-02
reviewers_invoked: [code-reviewer, security-reviewer, concurrency-reviewer, test-reviewer]
consensus_method: cross-check
run_id: 7d1123462b67
drift_verdict:
  result: scope_violation
  scope_violations:
    - README.md
    - README.ko.md
    - docs/HOW-IT-WORKS.md
    - docs/HOW-IT-WORKS.ko.md
    - work-docs/MATRIX-native-redundancy.md
    - tests/structural/autopilot_gate_golden.json
    - tests/structural/test_autopilot_gate_render.py
    - tests/structural/test_make_fastpath_contract.py
    - tests/unit/test_interview.py
    - tests/unit/test_interview_codex_second_opinion.py
    - tests/unit/test_interview_strictness_absent.py
    - tests/unit/test_loop_opt_in.py
  scenario_misses: []
  task_slug: world-model-name
  computed_at: 2026-10-02T03:05:00Z
---

# REVIEW — world-model-name

## 🎯 Round 1 Summary

Grade **A** (P0 0 · P1 0 · P2 3 · P3 6, all `consensus-passed`, all `accepted`). Lens coverage
complete (7/7, `blocks_approval: false`). `human_review_needed: false`. Auto-fix loop not entered
(grade met threshold; P2/P3 are not in the fix queue at grade A). Codex second opinion: `skipped`
(usage limit).

## 🔍 Drift Findings

`scope_violation` (P1-class drift record, not a code defect): 12 paths outside the PLAN phases'
listed scope. Every one is a contract-forced consequence of the in-scope change, attributed:
- README/HOW-IT-WORKS (×4): `test_documentation_contract` derives the skill list from
  `templates/skills/` — the new `world-model/` template dir must be listed.
- MATRIX-native-redundancy.md: `test_redundancy_matrix` requires a row per rendered skill.
- autopilot golden + its docstring: `configure` render moved (re-captured, dated entry).
- test_make_fastpath_contract: the new `world_model` axis must be classified.
- test_interview*.py (×3): scripted inputs shifted by the new question after locale;
  prompt-count invariant excludes the new prompt.
- test_loop_opt_in.py: loop-ON CLAUDE.md re-capture (verified loop-independent).
Incomplete-phase check: `tests/unit/test_synthesize.py` and `test_unwired_components.py`
(listed as risks) did not need changes — the counts they assert did not cross a bound.

## ✅ Consensus Findings

| id | Sev | Lens | Finding | File |
|---|---|---|---|---|
| 6d3f14ad | P2 | functionality | Span grep reads a cwd-relative ledger; spans are written at the base root, so from inside a task worktree every task shows "stage unknown" | `templates/skills/world-model/SKILL.md.j2:51` |
| 7c1d7670 | P2 | consistency | Interactive name/handle rejections are hard-coded English; S5 asks for a locale message | `interview.py:289,302` |
| 0248ff45 | P2 | tests | ADR-011 behaviours (7-key filter, `tail -n 1`, 8-line cap, Never-Read, resume mapping) are not pinned | `tests/render/test_render_world_model.py:280` |
| 130d174a | P3 | functionality | Briefing/Resume only see `hm/` task worktrees; flag-OFF harnesses see none and the skill does not say so | `SKILL.md.j2:42` |
| a9402944 | P3 | consistency | `_remove_emptied_skill_dir` docstring says world-model only; it runs for every swept `skills/<x>/` | `reconcile.py:685` |
| 8a53a1be | P3 | robustness | `tojson` emits astral chars (emoji) as surrogate pairs in YAML frontmatter; untested | `SKILL.md.j2:9` |
| 915118c8 | P3 | concurrency | An open `start` span from a live other session is labelled "interrupted" (stage preflight still warns) | `SKILL.md.j2:54` |
| a62626dd | P3 | tests | "Start no stage" / record-first routing rows unpinned | `test_render_world_model.py:261` |
| 3749a9d7 | P3 | tests | make.md dispatch selector uses `--locale` as a proxy | `test_render_world_model.py:318` |

Dropped in Pass 2 (context-invalidated): security ×2 (name metacharacters / injection — same
quoting pattern as existing free-text dispatch vars; S2 requires any-language names; a
harness.yaml committer already controls CLAUDE.md), core-6 (partial `{name: 비비}` → `maker`
is pinned by the SPEC test), concurrency-2 (rmdir race needs two concurrent makes; loud),
tests-3, tests-5 (optional hardening).

## ⚠️ Weak Consensus

None.

## 📝 Manual-Only Findings

None.

## 🤝 Disagreements

None (no same-location severity split).

## 🧊 Cross-model findings (frozen @ round 1)

| model | status | reason | findings |
|---|---|---|---|
| codex | skipped | exit 1 — usage limit (retry after 2026-10-04) | 0 |

## 🔒 Confirmation pass 1 (frozen `575a9642`, span `1ad54d73..575a9642`)

Coverage 7/7. New findings (none of these ids was in round 1's consensus set):

| id | Sev | Lens | Finding | Disposition |
|---|---|---|---|---|
| 86576761 | P1 | security | Handle may equal an existing **user-owned** skill dir. Reviewer claimed overwrite; orchestrator repro shows reconcile KEEPs the user file — the real defect is that the router is then **silently not installed** at `/<handle>` | accepted → fixed in repair round |
| 7c66fff2 | P2 | design | `make --add skill:world-model` renders a second router outside the handle path (`modular_edit`) | accepted (carried) |
| 84a7f33d | P2 | tests | Router skill BODY name / Codex `$handle` token not pinned (only frontmatter) | accepted (carried) |
| a1a2d1c0 | P3 | robustness | `name_error` admits U+FFFE/U+FFFF, which PyYAML rejects | accepted (carried) |
| 289b160a | P3 | consistency | 200-char pointer cap holds only for short names/handles | accepted (carried) |

Grade at confirm-1: **B** (P1 1). → one repair round.

### Repair round (confirmation; does not increment iteration_count)
Grade: B → A (pending confirm-2)
Fixes applied: 1
| # | Severity | Summary | File | Status |
|---|----------|---------|------|--------|
| 1 | P1 | Warn by name when the handle's skill dir is user-owned (router not installed) — the covering test `test_user_owned_skill_dir_is_not_overwritten` pins exit 0 + keep, so the fix warns rather than refuses (§6 outcome 1) | `src/harness_maker/cli.py` `_warn_world_model_handle_taken`, `i18n_messages.py`, new `test_handle_taken_by_user_skill_is_named` | Applied · caused_by=none |

Targeted tests 450 passed / 8 skipped; ruff, format, mypy --strict clean.
Churn: 0.093 (max: `src/harness_maker/i18n_messages.py`, measured 3, excluded 0) → re-review skipped — churn 0.09 < 0.30.

## 🔒 Confirmation pass 2 (frozen `e6163510`, span `1ad54d73..e6163510`)

Coverage 7/7. **Zero new findings** in every lens (the repair-round warning was checked by all
four; concurrency and core noted only sub-P2 residuals: a theoretical is_file/read TOCTOU and
an unreadable-SKILL.md OSError). → **APPROVED**.

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | A     | —             | 9 (P2 3 · P3 6) | — |
| confirm-1 | B     | —             | 5 new (P1 1 · P2 2 · P3 2) | 5 |
| repair    | A     | 1 (P1)        | P2 4 · P3 8 carried | 0 |
| confirm-2 | A     | —             | 0 new      | 0   |

Final grade: A
Iterations used: 1 / 3 (+ 1 confirmation repair round, not counted)
Exit reason: converged

## 📏 Size & Complexity

| File | LOC | Cyclomatic | Max nesting | Status |
|------|-----|------------|-------------|--------|
| src/harness_maker/cli.py | 2819 → 2854 | 382 → 387 | 7 → 7 | measured |
| src/harness_maker/i18n_messages.py | (repair round) | — | — | measured |

(Repair-round deltas only; 5c measures round-scoped endpoints.)

Status: APPROVED
human_review_needed: false
Counters (see §5): unreviewed 1 · prior-fix 0 · unattributed 0

## Carried for a human sweep (accepted, not fixed — P2/P3 are outside the fix queue at grade A)

P2: base-root span path from inside a worktree (6d3f14ad) · interactive locale messages
(7c1d7670) · ADR-011 render pins (0248ff45) · `--add skill:world-model` surface (7c66fff2) ·
router body name / Codex token pins (84a7f33d).
P3: flag-OFF task visibility note (130d174a) · sweep docstring scope (a9402944) · tojson astral
chars (8a53a1be) · live-session "interrupted" label (915118c8) · routing-row pins (a62626dd) ·
dispatch selector (3749a9d7) · U+FFFE/FFFF names (a1a2d1c0) · pointer cap at max lengths (289b160a).

## Post-review fix (DRI request, 2026-10-02)

| id | Sev | Change | Evidence |
|---|---|---|---|
| 6d3f14ad | P2 | Span lookup resolves the ledger from the git base root (`dirname "$(git rev-parse --path-format=absolute --git-common-dir)"`) instead of cwd, so "continue"/briefing find the stage from inside a task worktree or a subdirectory; outside git it degrades to the old cwd path | RED→GREEN `test_span_lookup_reads_the_base_ledger_from_inside_a_worktree` (runs the rendered command in a real base + worktree); feature suite 58/58; snapshots regenerated; ruff, format, `mypy --strict src tests` clean |

Not re-reviewed by the lens fan-out (single-line template change + one behavioural test).
Remaining carried: P2 4 · P3 8 (listed above).
