---
type: review
task_slug: sdlc-three-loops-gap
status: CHANGES_REQUESTED
human_review_needed: true
created: 2026-09-27
reviewers_invoked: [code-reviewer, security-reviewer, concurrency-reviewer, test-reviewer, codex]
consensus_method: cross-check
run_id: 6cb74c0a3f9f
review_base: 9417f3685a150ade9e3cf34039039b877497ca60
drift_verdict:
  result: clean
  scope_violations: []
  scenario_misses: []
  task_slug: sdlc-three-loops-gap
  computed_at: 2026-09-27T09:05:00Z
---
# REVIEW — sdlc-three-loops-gap

## 🎯 Round 1 Summary

Grade **B** (P0 0 · P1 2 consensus-passed). Lens coverage: all 7 exercised, `blocks_approval: false`.
Fixes pending: 2 (both P1, auto-fix eligible). Manual items: 2 cross-model (P2, P3) + 1 P3 lens.

Pass 1 → Pass 2: 6 Pass-1 findings, 3 survived. Dropped by Pass 2 with restored context:
the tests-lens "snapshots not regenerated" (the Pass-1 diff omitted `tests/snapshot/`; they were
regenerated and `test_loop_opt_in.py` is 27/27 green) and the design-lens "explicit allowlist for
`moved`" (an explicit list re-breaks on every template change — ADR-004). Concurrency: 0 findings.

## 🔍 Drift Findings

None. Every changed path is inside PLAN Phases 1–4 (Phase 4 added in execute with the user's
approval). No SPEC scenario lacks coverage.

## ✅ Consensus Findings

### P1
- `29da43db0a9589dc` · consistency · `src/harness_maker/memory/_locking.py:1` — module docstring
  names the deleted index/profile lock tier (`index.lock`, `profile.lock`) as current; the only
  importer, `memory_md`, uses `.session.lock` / `.wiki.lock` / `.failures.lock`.
- `7bc6db87acc5e933` · security · `src/harness_maker/templates/skills/project-knowledge/SKILL.md.j2`
  — the new Route-first hand-off sends DRI claim text toward `hm intent question add --claim …`,
  a shell-interpolated command with no file input, without the never-paste-raw-wording rule the
  same skill applies to its search step.

### P3
- `44c6b42228a6b31f` · tests · SPEC S1's docstring clause has no test (AC-001 deliberately
  excludes prose; manual-only by SPEC design).

## ⚠️ Weak Consensus

None.

## 📝 Manual-Only Findings

- `59db47012df403d0` · codex · P2 · project-knowledge routing is not limited to new claims, while
  the SPEC Non-Goal says the rule applies to new claims only — a correction of an existing
  intent-bearing `[wiki:fact]` would be routed away and leave the old entry stale.
- `141ed2767a9b2485` · codex · P3 · CHANGELOG says "read the 10-17 count against this landing
  date" without the date; fill it at wrapup.

## 🤝 Disagreements

None across tiers.

## 🧊 Cross-model findings (frozen @ round 1)

| id | model | severity | file | disposition | status |
|---|---|---|---|---|---|
| 59db47012df403d0 | codex | P2 | src/harness_maker/templates/skills/project-knowledge/SKILL.md.j2 | accepted | pending |
| 141ed2767a9b2485 | codex | P3 | CHANGELOG.md | accepted | pending |

second_opinion_results: [{model: codex, status: invoked}]

### Iteration 2 (Grade: B → A)
Fixes applied: 2
| # | Severity | Summary | File | Status |
|---|----------|---------|------|--------|
| 1 | P1 | `_locking` docstring names deleted tier (`29da43db0a9589dc`) | src/harness_maker/memory/_locking.py | Applied · resolved · caused_by=none |
| 2 | P1 | Routed claim text reaches shell sink without guidance (`7bc6db87acc5e933`) | project-knowledge + intent-layer SKILL.md.j2 | Applied · resolved · caused_by=none |

Remaining: 1 P3 (lens) + 2 manual-only (codex) | New issues introduced: 0
Churn: 0.078 (max: src/harness_maker/memory/_locking.py, measured 7, excluded 0)
Re-review: skipped — churn 0.08 < 0.30

## Confirmation passes

### confirm-1 (frozen fa2900ce) — dirty
New consensus-passed P1 ×2 (security): `wrapup.md.j2` Step 5.7 Claude-branch `hm intent question
add/observe` and `hm intent close` double-quoted operator text (`9942668943ed8914`,
`7bfb3e32e7ddf4e2`) — pre-existing, outside this task's diff, made more reachable by the new
routing. P2 (tests): routing test lacks the question-id link-direction assertion (`23ddadb30c4c7665`).

Repair round (user chose to fix in this task): switched those five values to single quotes
(net 0 chars — a longer guidance sentence was reverted because the shipped-surface budget
allows no growth), regenerated snapshots, re-captured `autopilot_gate_golden.json`
(`wrapup`-only in all four arms, dated entry in `test_autopilot_gate_render.py`). 1168
structural/render/snapshot tests green. Churn 0.038.

Harness defect observed: `review_consensus finalize` recomputes the tag from voices and ignores a
pre-set `manual-only` retag, so the review template's oracle-blocked refusal path cannot be
expressed to the CLI that computes the grade.

### confirm-2 (frozen 5faf479e) — dirty → stop
New consensus-passed P1 (security) `4621494f2640860a`: single quotes stop `$(...)`/backtick
expansion, but Step 5.7 carries no "no `'` inside" instruction, and the intent-layer write rule
the repair note relied on is NOT loaded by Step 5.7 (it loads only `references/workflow-feedback.md`).
A literal apostrophe in operator text ends the quoted argument. The repair's stated mitigation
was wrong. P2 (tests) `93ce5f865106b124`: nothing pins the single-quoted form except the opaque
golden hash.

No third confirmation pass is dispatched in one `/hm:review`.

## 🔁 Oscillation

None.

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | B     | —             | 5         | —   |
| 2         | A     | 2             | 3         | 0   |
| confirm-1 repair | B | 1 (5 values) | 6       | 3   |
| confirm-2 | B     | —             | 5         | 2   |

Final grade: B
Iterations used: 2 / 3 (+ confirm-1 repair round, budgeted separately)
Exit reason: confirm-2 dirty

## 📏 Size & Complexity

| File | LOC | Cyclomatic | Max nesting | Status |
|------|-----|------------|-------------|--------|
| src/harness_maker/memory/_locking.py | 102 → 102 | 4 → 4 | 3 → 3 | measured |
| src/harness_maker/templates/skills/intent-layer/SKILL.md.j2 | 112 → 112 | null | null | not-python |
| src/harness_maker/templates/skills/project-knowledge/SKILL.md.j2 | null | null | null | not-python |

Status: CHANGES_REQUESTED
human_review_needed: true
Counters (see §5): unreviewed 3 · prior-fix 1 · unattributed 0

### Open for the human
1. **P1 `4621494f2640860a`** — add an apostrophe-avoidance clause where Step 5.7 actually reads it.
   Options: (a) one short clause in `wrapup.md.j2` Step 5.7 with a declared `surface_allowance`
   and a retire phase; (b) put it in `references/workflow-feedback.md.j2` (the file 5.7 loads;
   not a command, so outside the command-surface budget); (c) a `--claim-file/--text-file/--note-file`
   CLI option (removes the class; larger change).
2. P2 `59db47012df403d0` (codex) — scope the routing rule to new claims in the skill text.
3. P2 `23ddadb30c4c7665`, `93ce5f865106b124` — two missing test assertions.
4. P3 `141ed2767a9b2485` — CHANGELOG landing date (fill at wrapup).

---

# Re-review — run d5a96ec922f4 (after option b)

## 🎯 Round 1 Summary
Grade **B** (P1 ×2 consensus-passed). Coverage: all 7 lenses exercised. drift_verdict: clean
(Phase 5 covers wrapup/workflow-feedback/golden; the `workflow-feedback.md.j2` boundary crossing
is logged in the PLAN as the user's decision). Pass 1 → Pass 2: 6 → 4 (tests lens dropped its
`moved` P2; core kept it at P1).

## ✅ Consensus Findings
- `b843818b8a0ddf64` P1 design · `tests/unit/test_loop_opt_in.py:234` — moved paths lost all
  loop-on parity coverage, and the set only grows.
- `990807e0474b5a26` P1 security · intent-layer `SKILL.md.j2:49` — write rule named
  `--claim`/`--text` but not `--note` (the free-text flag of `close`).
- `ab259dc6c37b80d9` P2 consistency · project-knowledge restates the quote rule with drifted wording.
- `41f0bce0a0b1a9da` P3 tests · `--text` lacks a positive single-quote assertion.

## 📝 Manual-Only Findings
- `3638189a8cc0d42a` codex P2 — same defect as `b843818b8a0ddf64` (different tier, kept independent).
- `d99756e01de01bba` codex P3 — CHANGELOG landing date (wrapup item).

## 🧊 Cross-model findings (frozen @ round 1)
| id | model | severity | file | disposition | status |
|---|---|---|---|---|---|
| 3638189a8cc0d42a | codex | P2 | tests/unit/test_loop_opt_in.py | accepted | resolved (by Fix #1) |
| d99756e01de01bba | codex | P3 | CHANGELOG.md | accepted | pending |

second_opinion_results: [{model: codex, status: invoked}]

### Iteration 2 (Grade: B → A)
Fixes applied: 2
| # | Severity | Summary | File | Status |
|---|----------|---------|------|--------|
| 1 | P1 | moved loop-insensitive paths now compared against the current snapshot; a moved loop-sensitive path fails the test (none today) | tests/unit/test_loop_opt_in.py | Applied · resolved · caused_by=none |
| 2 | P1 | `--note` added to the intent-layer write rule (same line, 120-line cap kept) | intent-layer/SKILL.md.j2 | Applied · resolved · caused_by=none |

Remaining: P2 ×1, P3 ×1 (lens) + P3 ×1 (codex) | New issues introduced: 0
Churn: 0.052 (max: tests/unit/test_loop_opt_in.py) · Re-review: skipped — churn 0.05 < 0.30

## Confirmation passes (run d5a96ec922f4)

### confirm-1 (frozen 48ba965a) — dirty
New P1 (security): Step 5.7 run lines carried no local quote cue; the rule was only reachable via
the workflow-feedback pointer. P2 (security, same as `ab259dc6c37b80d9`): project-knowledge guard
omits "single-quoted". P3 (tests): lock test counts calls, not distinct lock paths.
Repair round: the two Step 5.7 run lines now read `(no `'` inside)` — reworded from existing text,
net −8 characters (single quotes already make `$`/backtick inert, so only an embedded quote
matters); pinned by `test_wrapup_intent_writes_single_quote_inline_values`; golden re-captured
(`wrapup` only). 1172 tests green. Churn 0.038.

### confirm-2 (frozen 0c2b46b7) — dirty → stop
New P1 (security) `93479083cb71beba`: the `add` (new question) intro sentence at Step 5.7 lacks
the `(no `'` inside)` cue that the observe and close run lines now carry. Core, concurrency and
tests lenses: 0 findings. No third confirmation pass in one `/hm:review`.

## Review Iteration Summary (run d5a96ec922f4)

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | B     | —             | 6         | —   |
| 2         | A     | 2             | 3         | 0   |
| confirm-1 repair | B | 1 (2 lines) | 5         | 3   |
| confirm-2 | B     | —             | 3         | 1   |

Final grade: B · Exit reason: confirm-2 dirty · Status: CHANGES_REQUESTED · human_review_needed: true

### Open for the human
1. **P1 `93479083cb71beba`** — add `(no `'` inside)` to the Step 5.7 `add` intro sentence
   (+16 chars; current net is −8, so ~8 chars must be trimmed from that sentence to stay in budget).
2. P2 `ab259dc6c37b80d9` — align project-knowledge's guard wording with the intent-layer rule.
3. P3 ×3 — `--text` positive assertion, lock-path distinctness in the lock test, CHANGELOG date.

---

# Re-review — run a8bcd353b3b0 (after the add-branch cue)

Round 1: grade **B** — P1 `7c363ecf92facf84` (robustness, project-knowledge restated the quote
rule without "single-quoted") and P1 `58ef46c950a7b459` (security: the quote-breakout defence for
`hm intent` inline text is prompt-only; argparse validation cannot help because the shell parses
first; structural fixes are file-based `--*-file` inputs or a PreToolUse check). Codex: P3
`76d15a10ef71d385` (CHANGELOG landing date, accepted → wrapup). Tests lens Pass 2 dropped both of
its Pass-1 items; concurrency 0. All 7 lenses exercised.

### Iteration 2 (Grade: B → B)
| # | Severity | Summary | File | Status |
|---|----------|---------|------|--------|
| 1 | P1 | project-knowledge now uses intent-layer's exact wording and names it | project-knowledge/SKILL.md.j2 | Applied · resolved |
| — | P1 | `58ef46c950a7b459` prompt-only injection defence | wrapup.md.j2 Step 5.7 | **Carried — user decision C (accepted residual, separate task)** |

Churn 0.063 · re-review skipped (< 0.30). 853 targeted tests green.

Final grade: B · Exit reason: accepted-residual (user decision) · Status: CHANGES_REQUESTED ·
human_review_needed: true · confirm_pass_ran: false

**Accepted residual (user, 2026-09-27):** the `hm intent question add/observe` / `hm intent close`
sink pre-dates this task; this change reduced its exposure (double → single quotes, `(no ' inside)`
cues at all three run lines, rule in both intent-layer files). The structural fix — file-based
`--claim-file/--text-file/--note-file` like `memory_md upsert-wiki --body-file` — is a separate task.
