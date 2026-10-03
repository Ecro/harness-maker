---
type: review
task_slug: maker-front-door-improvements
status: APPROVED
created: 2026-10-03
reviewers_invoked: [code-reviewer, security-reviewer, concurrency-reviewer, test-reviewer, codex]
consensus_method: cross-check
run_id: 48ea175fa60f
drift_verdict:
  result: scope_violation
  scope_violations:
    - src/harness_maker/cli.py
    - src/harness_maker/templates/stages/execute.md.j2
    - tests/unit/test_loop_opt_in.py
    - tests/unit/test_render_intent_layer_assume_add.py
    - tests/structural/test_autopilot_gate_render.py
  scenario_misses: []
  task_slug: maker-front-door-improvements
  computed_at: 2026-10-03T04:10:00Z
---

# REVIEW — maker-front-door-improvements

## 🎯 Round 1 Summary

Grade **B** (P0 0, P1 1, P2 11, P3 3 consensus-passed; 3 cross-model P2 manual-only).
Lenses exercised: all 7 (`blocks_approval: false`). Cross-model: codex invoked, 6 findings —
PIDA 4 accepted, 2 unresolved.

Review span: working tree vs `HEAD` (c70f300a). `hm freeze resolve-base` returned `ddd70a07`
(HEAD~1), which would have pulled the unrelated commit c70f300a into the span; the brief named
the span explicitly instead. Recorded as a process defect (the same wrong-base symptom
REVIEW-world-model-followups noted for `read-base`).

DRI decisions after round 1 (2026-10-03): fix the P1 by narrowing `allowed-tools` and updating
the AC-010 literal (an oracle change the DRI approved, not a fixer edit); also fix the functional
and test P2s this round. Comment/diagnostic-only P2/P3 stay in the report.

## 🔍 Drift Findings

All five out-of-scope paths are follow-ons of in-scope contract changes, not unrelated edits:
`cli.py` (Typer shim parity for the new `narrow` action), `stages/execute.md.j2` (declared
boundary crossing: its retrieval note became false in Phase 3), `test_loop_opt_in.py` (loop-ON
recaptures), `test_render_intent_layer_assume_add.py` (+1 frontmatter line),
`test_autopilot_gate_render.py` (golden rebase note). No incomplete phase.

## ✅ Consensus Findings

| id | Sev | Lens | Location | Summary |
|---|---|---|---|---|
| 24451777c57f24d6 | P1 | security | world-model/SKILL.md.j2:21 | `allowed-tools: Bash(uv run:*)` pre-approves any `uv run`; scope to `uv run --with <src> hm *` |
| aea107e8b49b7c93 | P2 | functionality | world-model/SKILL.md.j2:90 | narrowed marker has no undo path when the run stops before its boundary |
| 17052bb44a074efb | P2 | robustness | world-model/SKILL.md.j2:21 | same grant, robustness framing |
| f336c238172fcb50 | P2 | robustness | autopilot.py:803 | single-shot restore; lost race leaves the marker narrowed |
| 9df6b033df04fe24 | P2 | robustness | world_model_digest.py:297 | active intent ids unclipped → digest `unavailable` |
| be4f288a685d0778 | P2 | consistency | synthesize.py:343 | dead `stage_description` ctx; description built in several places |
| 46a3fe23f7cffd47 | P2 | concurrency | autopilot.py:802 | restore authorized from a fresh snapshot can erase a concurrent re-narrow |
| 7a51c2b150b26794 | P2 | concurrency | autopilot_caps.py:583 | every restore failure reported as "changed concurrently" |
| f084ce96ef7255c0 | P2 | tests (+codex ed3f3031) | test_render_maker_front_door.py:384 | AC-007 never reads the Ends-at cell |
| c5c46e752007225f | P2 | tests | test_autopilot_narrow.py:141 | no double-narrow test |
| e84ee34f6adbea3e | P2 | tests | test_maker_digest.py:266 | AC-006 worst-case cap interaction untested |
| f27254a5598bbd14 | P2 | tests | test_memory_retrieve_cli.py:185 | CLI floor wiring no longer exercised |
| 091d480f58f10b19 | P3 | consistency | autopilot_caps.py:1094 | restore-failure reason misattributes cause |
| 1d10228fcc972527 | P3 | consistency | synthesize.py:372 | comment claims a 120-char cap a long name exceeds |
| 1159f620b5cf4562 | P3 | tests | test_maker_digest.py:315 | AC-011 absent-case inputs untested |

## ⚠️ Weak Consensus

None.

## 📝 Manual-Only Findings

| id | Sev | Source | Location | Summary |
|---|---|---|---|---|
| dbe5ddc7d2b897ab | P2 | codex (accepted) | world_model_digest.py:424 | render trims tasks below the S3 floor of 3 |
| a1231bf63fedfd24 | P2 | codex (accepted) | world-model/SKILL.md.j2:87 | a concrete research-only ask enters spec |
| 406f3bc12ab25792 | P2 | codex (accepted) | memory_retrieve.py:445 | long escaped topic exceeds the 8,192-byte cap |

## 🤝 Disagreements

security rates the `allowed-tools` grant P1; the core robustness lens rates the same defect P2.
Kept as independent findings (tiers are not bridged); the P1 drives the grade.

## 🧊 Cross-model findings (frozen @ round 1)

frozen_at_round: 1 · models: [codex]

| id | source | severity | file | line | summary | evidence | needs_relaxation | disposition | oracle_result | status | invalidation_reason |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 558e706d12033840 | codex | P1 | src/harness_maker/autopilot_caps.py | 578 | restoration can erase a concurrent narrowing decision | compare protects only restore's own snapshot | false | unresolved | TOCTOU real; needs two concurrent same-session writes; no oracle | pending | — |
| dbe5ddc7d2b897ab | codex | P2 | src/harness_maker/world_model_digest.py | 424 | size loop drops tasks below 3 | comment at :423 concedes it | false | accepted | AC-006 requires min(3, tasks) | pending | — |
| cbd661e472556113 | codex | P2 | src/harness_maker/autopilot.py | 768 | narrow does not detect an end stage already passed | no progress field on the marker | false | unresolved | S5 "already passed" reading ambiguous | pending | — |
| a1231bf63fedfd24 | codex | P2 | src/harness_maker/templates/skills/world-model/SKILL.md.j2 | 87 | research-only ask can enter spec | entry ignores the chosen end point | false | accepted | SKILL.md.j2:87 enters spec for any concrete ask | pending | — |
| 406f3bc12ab25792 | codex | P2 | src/harness_maker/memory_retrieve.py | 445 | byte cap does not cover oversized escaped topics | fence_open unbounded | false | accepted | empty-result path skips both cap branches | pending | — |
| ed3f30316a871e26 | codex | P2 | tests/render/test_render_maker_front_door.py | 383 | AC-007 never asserts the mapped end stage | cue match over whole row | false | accepted | green run consistent with weak test | pending | — |

### Iteration 2 (Grade: B → A)
Fixes applied: 9 (§5 batch trigger fired: groups A autopilot narrow lifecycle, B Maker routing/grant, C digest cap, D retrieval topic bound, E tests)
| # | Severity | Summary | File | Status |
|---|---|---|---|---|
| 1 | P2 | narrow --until <armed end> un-narrows a leftover (aea107e8) | src/harness_maker/autopilot.py | Applied · caused_by=none |
| 2 | P2 | restore_narrowed takes expected_pipeline; superseded restore skipped (46a3fe23, codex 558e706d) | src/harness_maker/autopilot.py | Applied · caused_by=none |
| 3 | P2 | restore retries once after a byte miss; second miss = raced (f336c238) | src/harness_maker/autopilot.py | Applied · caused_by=none |
| 4 | P2 | typed restore causes in the boundary reason (7a51c2b1, 091d480f) | src/harness_maker/autopilot_caps.py | Applied · caused_by=none |
| 5 | P1 | allowed-tools scoped to `uv run --with <src> hm *`; AC-010 literal updated (DRI-approved) (24451777, 17052bb4) | world-model/SKILL.md.j2 | Applied · caused_by=none |
| 6 | P2 | research-only ask enters research; narrow on every ask, `wrapup` for full (codex a1231bf6) | world-model/SKILL.md.j2 | Applied · caused_by=none |
| 7 | P2 | active intent ids clipped; trim stops at 3 tasks, optional fields dropped first (9df6b033, codex dbe5ddc7) | src/harness_maker/world_model_digest.py | Applied · caused_by=none |
| 8 | P2 | fence topic clipped to 200 codepoints on every path (codex 406f3bc1) | src/harness_maker/memory_retrieve.py | Applied · caused_by=none |
| 9 | P2 | tests: AC-007 Ends-at cell, double/undo/superseded narrow, digest worst case, AC-011 absent cases, 20 KB topic, CLI floor below k (f084ce96, ed3f3031, c5c46e75, e84ee34f, 1159f620, f27254a5) | tests/… | Applied · caused_by=none |

Remaining: 2 (be4f288a P2 consistency, 1d10228f P3 comment — DRI scoped comment/diagnostic-only items to the report) | New issues introduced: 0 (re-review skipped)
Churn: 0.274 (max: tests/unit/test_autopilot_narrow.py, measured 15, excluded 0)
rereview: skipped — churn 0.27 < 0.30
Verification: selected suite 1537 passed, 8 skipped; snapshot + loop-opt-in 31 passed; ruff/format/mypy clean.
Open notes from the fixer: (1) whether Claude Code matches `Bash(uv run --with <src> hm *)` against a sub-command inside the `{ …; } | tail` group is unverified (same unknown as the old grant); (2) the worst-case digest test feeds 8 tasks to `render`, but `digest()` caps at 5 first; (3) the full-pipeline undo assumes the armed pipeline ends at `wrapup`.

## Confirmation passes

**confirm-1** (span c70f300a..3a310378, all 7 lenses exercised) — dirty: 1 new consensus-passed P1
(security: `allowed-tools: Bash(uv run --with <src> hm *)` still pre-approved every `hm` verb) plus
P2s: a spec-end narrow left stale because Resume never undid it; the over-cap trim dropped
`other_session`; the worst-case digest test never ran `digest()`; P3s: `ts` unchecked, fence
attribute unchecked, undated entries cut to the first paragraph (design; reported, not changed).
**Repair round** (separate budget, churn 0.67): grant scoped to `Bash(<hm> world_model:*)`
(`world_model` has only the read-only `digest`) + `Bash(<hm> autopilot narrow:*)` + printf/tail; AC-010
literal updated under the same DRI authorisation as round 2; Resume runs `narrow --until wrapup`
first and defines absent `latest_artifact` / `other_session`; trim order drops `last_seen`/`last_stage`
then `latest_artifact`, never `other_session`; end-to-end worst case, ISO `ts`, fence-attribute
checks added. Focused suite 466 passed, 8 skipped; ruff/format clean.
**confirm-2** (span c70f300a..6a1a39d4, all 7 lenses exercised) — clean of new P0/P1 → **APPROVED**.
Remaining for a human sweep: P2 functionality — whether Claude Code's permission matcher accepts the
brace-grouped `{ …; } | tail` injected command against the scoped rules is unverified (same unknown
as the original grant; a mismatch would prompt or abort Maker's load outside auto mode); P2 tests —
the new trim order has no test that reaches the field-drop step; P3 — the `wrapup` undo does not
restore a custom armed pipeline that lacks `wrapup`.

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | B     | —             | 18        | —   |
| 2         | A     | 9             | 2         | 0 (re-review skipped, churn 0.27) |
| confirm-1 repair | A | 4          | 2         | 1 P1 found by confirm-1, repaired |

Final grade: A
Iterations used: 2 / 3
Exit reason: converged

## 📏 Size & Complexity

Round-2 complexity rows were recorded by `hm review_churn complexity` (observability ledger); no
threshold, report only.

Status: APPROVED
human_review_needed: false
Counters (see §5): unreviewed 13 (9 round-2 fixes skipped by the churn gate + 4 confirm-1 repair fixes, both covered afterwards by a whole-review confirmation pass) · prior-fix 1 (the confirm-1 P1 was caused by the round-2 grant fix) · unattributed 0

## 🔁 Oscillation

None (`hm review_churn oscillation --rounds 2` returned no rows).

## Post-approval fixes (DRI request, 2026-10-03)

The DRI asked for the three items confirm-2 left for a human sweep to be fixed before wrapup.
1. P2 (brace group vs permission matcher): the injected briefing is now
   `<hm> world_model digest … 2>/dev/null | tail -n 1 | grep '^{.*}$' || printf '{"unavailable":"digest"}\n'`
   — no `{ …; }` group, every split piece starts with a command; `allowed-tools` adds `Bash(grep:*)`.
   Whether Claude Code accepts the chain against the scoped rules is still to be confirmed in a live
   session after release.
2. P2 (trim order untested): `test_ac006_trim_drops_optional_fields_in_order_and_keeps_other_session`
   reaches the field-drop step with exactly 3 tasks (MAX_BYTES patched) and pins the order.
3. P3 (custom pipeline undo): on a narrowed marker, `--until wrapup` restores an armed pipeline
   that lacks `wrapup`; other unknown stages leave the narrowing in place
   (`test_narrow_to_a_stage_the_custom_pipeline_lacks_restores_it`,
   `test_narrow_to_an_unknown_stage_keeps_a_deliberate_narrowing`).
A focused code-reviewer pass over this delta (memory: fix-introduced-defect-passes-all-gates)
returned P2 "any unknown stage restores" and P3 "`grep '}$'` accepts a truncated line ending in
`}`" — both applied (literal-`wrapup` restriction; anchored `'^{.*}$'`); P3 "`Bash(grep:*)` is
broader than its one use" accepted (read-only, needed by the chain). Render/structural/snapshot +
narrow/digest suites: 1278 passed; ruff, format, `mypy --strict src tests` clean.
