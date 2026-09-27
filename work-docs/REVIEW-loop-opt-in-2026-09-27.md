---
type: review
task_slug: loop-opt-in
status: APPROVED
created: 2026-09-27
run_id: de811b436e83
reviewers_invoked: [code-reviewer, security-reviewer, concurrency-reviewer, test-reviewer, codex]
consensus_method: cross-check
review_base: 67faab2c3efe976fb4c4b9d4896162e94e9ca3a7
drift_verdict:
  result: clean
  scope_violations: []
  scenario_misses: []
  task_slug: loop-opt-in
  computed_at: 2026-09-27T04:40:00Z
---

# REVIEW — loop-opt-in

> The diff under review is the working tree against HEAD `055cce85`. `review_base`
> resolved to `67faab2c` (HEAD~1) by design, because the task branch has no commits
> of its own (`freeze.resolve_base` skips a merge-base equal to HEAD). Commit
> `055cce85` inside that span belongs to a prior task that was already reviewed,
> and it is out of scope here.

## 🎯 Round 1 Summary

- **Grade:** B. Two consensus-passed P1 findings and no P0.
- **Lens coverage:** all 7 lenses exercised; `blocks_approval: false`.
- **Fixes pending:** 2 (both P1).
- **Manual items:** 3 cross-model findings, all PIDA-`accepted` and each backed by a single voice.

## 🔍 Drift Findings

None. Every changed path falls inside a PLAN phase scope:
- Phase 1/2 sources and templates, and `commands/make.md`.
- Phase 3 fixtures and the adjusted tests.
- PLAN Deviations 1–3, which are recorded in the PLAN.

Intent drift (Step 3.3, LOOP-OPT-IN): none. The verify() exemption (Deviation 1) is
what makes the "keep edited files" migration work, so it falls inside
"기존 하네스 보존 마이그레이션".

## ✅ Consensus Findings

| id | Sev | Lens | Location | Summary | Disposition |
|---|---|---|---|---|---|
| f5610f47309c7a63 | P1 | functionality | src/harness_maker/cli.py:1520 | `make --update --preset <X>` rebuilds answers through `_build_answers`' field allowlist, which drops `loop`, so an existing `loop.enabled: true` silently becomes false and the sweep deletes the loop files | accepted, fix |
| cd14c78815a4027d | P1 | tests | tests/unit/test_loop_opt_in.py:389 | The AC-009 body-diff half is vacuous: `body_sha256` is None until `render()`, and the test only calls `synthesize()` | accepted, fix |
| e799cb684b77e61b | P2 | design | src/harness_maker/cli.py:380 | The loop value is read twice and re-applied on the successful-reuse path | accepted, carried |
| 872df6de2b48fdd5 | P2 | concurrency | src/harness_maker/cli.py:353 | TOCTOU: pre-read before a blocking `--reinterview` prompt, applied after. The core Pass 2 disputed it as the same accepted precedent as the autonomy and comprehension re-apply | accepted, carried |
| 5b5155e1309f9a25 | P2 | tests | tests/unit/test_stage_invocation_syntax.py:29 | The dangling-reference scan only sees a loop-ON render | accepted, carried |
| d2d2ed88ce49eaf4 | P3 | tests | work-docs/PLAN-loop-opt-in.md | The loop-off Next: check was done by hand only | duplicate of 5b5155e1309f9a25 |

## ⚠️ Weak Consensus

None.

## 📝 Manual-Only Findings

| id | Sev | Source | Summary | Disposition |
|---|---|---|---|---|
| cc22e4224ce88996 | P2 | codex | An unreadable (invalid UTF-8) harness.yaml fails in `_load_harness_yaml_body` / `answers_from_harness_yaml` before the resolver's UnicodeError branch is reached, so that branch is dead | accepted |
| 87c7da74b7ebaee6 | P2 | codex | AC-009 body check always passes. It also notes that Codex `hm-help` changes body between the loop arms | duplicate of cd14c78815a4027d |
| be85e411cf903480 | P3 | codex | Non-string unknown keys in `loop` raise TypeError in `parse_loop` instead of LoopConfigError | accepted |

## 🤝 Disagreements

- **Dropped in Pass 2.** The concurrency P1 "a concurrent make sweeps another make's
  loop files" was dropped by both the concurrency and core Pass 2 reviewers. Reason:
  `make` has never had a lock, and the same race exists for every conditionally
  rendered file, so the diff does not make it newly reachable.
- **Split verdict (concurrency 872df6de2b48fdd5, P2 TOCTOU).** The concurrency lens
  kept it. The core lens dropped it as the established re-apply precedent. It is kept,
  because a Pass 2 reviewer kept it.

## 🧊 Cross-model findings (frozen @ round 1)

| id | model | severity | file:line | disposition | oracle_result | status |
|---|---|---|---|---|---|---|
| cc22e4224ce88996 | codex | P2 | src/harness_maker/cli.py:350 | accepted | `_load_harness_yaml_body` catches only OSError; UnicodeDecodeError escapes before the resolver | pending |
| 87c7da74b7ebaee6 | codex | P2 | tests/unit/test_loop_opt_in.py:378 | accepted (duplicate of cd14c78815a4027d in consensus) | body_sha256 None until render | pending |
| be85e411cf903480 | codex | P3 | src/harness_maker/interview.py:1466 | accepted | join/sorted on int or mixed keys raises TypeError | pending |

second_opinion_results: `[{model: codex, status: invoked, reason: null}]`

### Iteration 2 (Grade: B → A)
Fixes applied: 2
| # | Severity | Summary | File | Status |
|---|----------|---------|------|--------|
| 1 | P1 | Forward `loop` through the `--preset` switch rebuild (`_build_answers` gains `loop=`; cli passes `loop=answers.loop`). New regression test `test_ac010_preset_switch_keeps_existing_loop` (Side↔Production × true/false); removing the fix makes it fail | src/harness_maker/cli.py:1520, src/harness_maker/interview.py | Applied · caused_by=none |
| 2 | P1 | AC-009 now compares post-render body hashes (`_rendered_body_hashes`, which asserts every hash is stamped). This surfaced the Codex `.agents/skills/hm-help/SKILL.md` as a 6th listing surface, now included in `LISTING_SURFACES` (AC-004) and the AC-009 allowed diffs (SPEC amendment pending DRI) | tests/unit/test_loop_opt_in.py:389 | Applied · caused_by=none |

Verification: `test_loop_opt_in.py` 25/25 passed. Targeted selection 9194 passed; the 6 failures were `test_install_ref` under the `$HOME` basetemp, the known environmental artifact. mypy --strict clean.
Lifecycle: f5610f47309c7a63, cd14c78815a4027d and 87c7da74b7ebaee6 (codex duplicate) went pending → resolved.
Re-review: skipped — churn 0.07 < 0.30. unreviewed_fix_count = 2.
Remaining: 3 consensus-passed P2 (carried) and 2 manual-only (P2 cc22…, P3 be85…) | New issues introduced: 0
Churn: 0.0700 (max: tests/unit/test_loop_opt_in.py, measured 3, excluded 0)

## Confirmation Pass (confirm-1)

Freeze `107f66ed` (span `67faab2c..107f66ed`; the `055cce85` hunks are prior-task and out of scope). All 7 lenses were exercised and `blocks_approval` is false. **No new consensus-passed P0/P1.** No fixes were applied in this pass.

| Lens | Result |
|---|---|
| core | P2 consistency: `models.LoopConfig` docstring names `interview._parse_loop`, but the function is `parse_loop`. P3 design: the loop value is parsed by two readers |
| security | none |
| concurrency | none (reconfirmed the dropped concurrent-make race and the kept TOCTOU P2) |
| tests | none (both round-2 tests confirmed discriminating) |

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | B     | —             | 7         | —   |
| 2         | A     | 2             | 5         | 0   |

Final grade: A
Iterations used: 2 / 3
Exit reason: converged

## 📏 Size & Complexity

| File | LOC | Cyclomatic | Max nesting | Status |
|------|-----|------------|-------------|--------|
| src/harness_maker/cli.py | 2717 → 2721 | 367 → 367 | 7 → 7 | measured |
| src/harness_maker/interview.py | round 2: +2 lines (param + forward) | unchanged | unchanged | measured |
| tests/unit/test_loop_opt_in.py | round 2 rewrite of AC-009 plus one new test | — | — | measured |

Status: APPROVED
human_review_needed: false
Counters (see §5): unreviewed 2 · prior-fix 0 · unattributed 0

### Carried for a human sweep (P2/P3; not grade-moving)

- e799cb684b77e61b (P2 design): double read of the loop value. It was re-raised as a P3 in confirm-1.
- 872df6de2b48fdd5 (P2 concurrency): TOCTOU across the blocking `--reinterview` prompt. It follows the same precedent as the autonomy and comprehension re-apply.
- 5b5155e1309f9a25 (P2 tests): the dangling-reference scan in `test_stage_invocation_syntax` runs only with loop ON.
- cc22e4224ce88996 (P2 codex, manual-only): invalid UTF-8 in harness.yaml fails before the resolver's UnicodeError branch.
- be85e411cf903480 (P3 codex, manual-only): non-string `loop` keys raise TypeError instead of LoopConfigError.
- confirm-1 P2: the `LoopConfig` docstring cites `interview._parse_loop` instead of `parse_loop`.

## Post-review fixes (user-requested at wrapup, 2026-09-27)

The operator asked for the carried P2/P3 items to be fixed before landing. The fixes were checked by one focused code-reviewer pass over the fix delta (`refs/hm-churn/v1/loop-opt-in-r2-post..r3-post`) rather than a full re-review.

| Carried id | Fix |
|---|---|
| e799cb684b77e61b (P2 design) | The existing-file loop override applies only on the interview/fallback path. The reuse path takes `answers_from_harness_yaml`'s value |
| 872df6de2b48fdd5 (P2 concurrency) | On that path the value is re-read after `interview()` via `_resolve_existing_loop_or_exit`, so an edit made during a blocking prompt wins |
| cc22e4224ce88996 (P2 codex) | `UnicodeError` is now treated as an unreadable harness.yaml in `cli._load_harness_yaml_body`, `interview.answers_from_harness_yaml` and `render._preserve_yaml_user_keys` (the third reader crashed the render). AC-010 gained an undecodable-file case |
| be85e411cf903480 (P3 codex) | `parse_loop` sorts and prints unknown keys by repr. AC-011 gained `int_key` and `mixed_keys` cases |
| confirm-1 P2 docstring | `LoopConfig` cites `interview.parse_loop` |
| 5b5155e1309f9a25 / d2d2ed88ce49eaf4 (P2/P3 tests) | `test_recommendations_resolve_to_skills` is parametrized over loop ON/OFF. The loop-off dangling-reference and advertised scans run automatically |

The fix-delta review raised one P1 (tests): the loop-off hint exclusion dropped the whole line, which hid the co-located `$hm-make` reference from the advertised scan. It was fixed in place: only the `hm-loop` token is exempt, and advertised names must resolve against rendered skills ∪ plugin-bundled `skills/` (`hm-make` ships there). The test also asserts that the enable hint exists in the loop-off arm.

Also fixed after /hm:verify's first run: 12 `mypy --strict tests` errors (LoopConfig instead of dicts, unused ignores).

Gates after all fixes: ruff, format, mypy --strict src tests clean; CI pytest (TMPDIR=/var/tmp, due to the stray /tmp/.git) 9351 passed; test_stage_invocation_syntax 26/26 after the last edit.
