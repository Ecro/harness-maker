---
type: review
task_slug: intent-file-inputs
status: APPROVED
created: 2026-09-28
reviewers_invoked: [code-reviewer, security-reviewer, concurrency-reviewer, test-reviewer, codex]
consensus_method: cross-check
run_id: f8dec5471aad
review_base: 6ff0d1626234d464becf808814157e760fa8e331
final_grade: A
human_review_needed: false
confirm_pass_ran: true
confirm_pass_new_severe_n: 0
drift_verdict:
  result: clean
  scope_violations: []
  scenario_misses: []
  task_slug: intent-file-inputs
  computed_at: 2026-09-28T00:05:00Z
second_opinion_results:
  - model: codex
    status: invoked
    reason: null
---
# REVIEW — intent-file-inputs

## 🎯 Round 1 Summary

Grade **B** at round 1 (one consensus-passed P1), **A** after the round-1 fix step. Seven
lenses exercised (`lens_coverage`: `blocks_approval: false`); codex invoked once (2 findings,
both `accepted` by PIDA). Confirmation pass `confirm-1` over `review_base..8a18e714` returned
zero new P0/P1 → **APPROVED**.

| Stage | Grade | P0 | P1 | P2 | P3 |
|---|---|---|---|---|---|
| Round 1 | B | 0 | 1 | 2 (+2 manual-only) | 1 |
| After fix step | A | 0 | 0 | 0 | 0 |

## 🔍 Drift Findings

None. Every changed file falls inside a PLAN phase scope (`templates/skills/project-knowledge/SKILL.md.j2`
was added to Phase 2's scope during execute, with its reason). Every SPEC scenario S1–S5 has a
covering test in `tests/unit/test_intent_file_inputs.py`.

## ✅ Consensus Findings (round 1, after Pass 2)

| id | Sev | Lens | Finding | Disposition | Status |
|---|---|---|---|---|---|
| `7c2703017692160c` | P1 | functionality | wrapup Step 5.7 `add` preview prose named `--text`, contradicting the file-only rule on the line above | accepted | resolved |
| `c6f21c44e30931f1` | P2 | design | `FILE_TWINS` and the `_pair()` calls were two hand-synced lists; an unlisted twin would parse and reach its handler as `None` (Pass 1 P1 → Pass 2 P2: no live drift today) | accepted | resolved |
| `77823fe2beba08a1` | P2 | security | no size cap on `-file` reads | **rejected — AC-001** | — |
| `048b0e9fce21286e` | P2 | tests | AC-001 property filter `s == s.strip()` excludes boundary whitespace, so a `data.strip()` reader passes every test | accepted | resolved |
| `8be3b0c571eea42f` | P3 | tests | AC-005 Write-tool/mktemp check scanned the whole intent-layer skill, not its write rule | accepted | resolved |

**Rejection of `77823fe2beba08a1`.** The approved value semantics (IRR-001) have no size bound
and AC-001 requires the stored value to equal the file content for any value in its domain; a cap
would make AC-001 false for large values. The reader is an operator/agent-local CLI, so the
residual is self-inflicted memory use, not a remote DoS. Core Pass 2 dropped it independently.

**Dropped in Pass 2:** core's robustness copy of the size-cap finding (out of the task's threat
model); security's copy of the wrapup preview finding (not an executed line — kept by core as P1).

## ⚠️ Weak Consensus

None.

## 📝 Manual-Only Findings

| id | Sev | Source | Finding | Disposition | Status |
|---|---|---|---|---|---|
| `b5d265eadb6ca004` | P2 | codex | intent-layer proposal path always passed `--declined-file`; with every candidate accepted the file is empty and the CLI refuses it (exit 2) | accepted | resolved |
| `cdd5fb9a23ad13ca` | P2 | codex | AC-005 `present_call_sites` collapsed the two intent-layer `new` lines into one `(surface, verb)` pair and checked no `-file` argument | accepted | resolved |

## 🤝 Disagreements

- Size cap: security kept P2 in Pass 2, core dropped it. Resolved by the AC-001 rejection above.
- Wrapup preview prose: core kept P1, security dropped it (prose, not a shell line). Kept at P1:
  the preview is what the operator confirms, and naming `--text` there invites the inline form
  this task removes.

## 🧊 Cross-model findings (frozen @ round 1)

frozen_at_round: 1
models: [codex]

- id: `b5d265eadb6ca004` · source: codex · severity: P2 · file:
  `src/harness_maker/templates/skills/intent-layer/SKILL.md.j2` · line: 105 · summary: the
  proposal recipe fails when every candidate is accepted; pass `--declined-file` only when a
  candidate was declined · evidence: the recipe always passes `--declined-file <path>`, an empty
  file makes `resolve_file_args` exit 2 · needs_relaxation: false · disposition: accepted ·
  oracle_result: No oracle (.j2). SKILL.md.j2:105 always passes --declined-file; an all-accepted
  proposal writes an empty file, which resolve_file_args refuses. · status: resolved
- id: `cdd5fb9a23ad13ca` · source: codex · severity: P2 · file:
  `tests/unit/test_intent_file_inputs.py` · line: 541 · summary: AC-005 test does not verify
  required call sites or their file arguments · evidence: `present_call_sites` is a set of
  `(surface, verb)`, so synopsis and proposal-path `new` merge; a call with every `-file`
  argument removed still passes · needs_relaxation: false · disposition: accepted ·
  oracle_result: pytest green does not refute: present_call_sites collapses both intent-layer new
  lines into one (surface,verb) pair and checks no -file argument. · status: resolved

## Auto-fix

### Iteration 1 (Grade: B → A)
Fixes applied: 7

| # | Severity | Summary | File | Status |
|---|---|---|---|---|
| 1 | P1 | preview prose says "the why text", no `--text` | `templates/stages/wrapup.md.j2` | Applied · caused_by=none |
| 2 | P2 | proposal path: `[--declined-file <path>]`, omitted when every candidate was accepted | `templates/skills/intent-layer/SKILL.md.j2` | Applied · caused_by=none |
| 3 | P2 | `_pair` raises `ValueError` for a twin missing from `FILE_TWINS` | `src/harness_maker/intent.py` | Applied · caused_by=none |
| 4 | P2 | `test_file_value_keeps_boundary_whitespace` (spaces/tabs survive, only trailing `\n` dropped) + `test_pair_refuses_a_twin_missing_from_the_table` | `tests/unit/test_intent_file_inputs.py` | Applied · caused_by=none |
| 5 | P2 | `CALL_SITES`: ordered, distinct-line matching with the required `-file` flags per site; inline scan covers whole sections, not only call lines | `tests/unit/test_intent_file_inputs.py` | Applied · caused_by=none |
| 6 | P3 | intent-layer mktemp check anchored to `## The rule for every write` | `tests/unit/test_intent_file_inputs.py` | Applied · caused_by=none |
| 7 | — | re-captured autopilot golden (`wrapup` alone, all four arms), re-froze surface baseline (+5 chars wrapup), regenerated snapshots, BASELINE-DELTA updated | structural/snapshot | Applied |

**Deviation, recorded:** Step 3's selection admits only P0/P1 at grade B. Fixes 2–6 are P2/P3 and
were applied anyway: fix 2 is a functional recipe failure on the normal path (all candidates
accepted), and fixes 4–6 are the oracle strength that pins fixes 1–2. The round ran for the P1
regardless, so no extra round trip was spent.

**Mutation check of the new tests** (each mutant, then restored): `rstrip("\n")`→`strip()` →
18 failed; `--declined-file` made mandatory again → 2 failed; proposal `new` line deleted → 2
failed; preview prose back to `` `--text` `` → 2 failed; `close` without `--note-file` → failed.

Verification: `ruff check`, `ruff format`, `mypy --strict src tests` clean; full suite 9367 passed
with 8 snapshot failures → snapshots regenerated → those 31 tests pass; structural suite 807
passed.

Remaining: 0 | New issues introduced: 0
Churn: 0.275 (max: `work-docs/BASELINE-DELTA-intent-file-inputs.md`, measured 12, excluded 0)
Re-review: skipped — churn 0.28 < 0.30 (unreviewed_fix_count 7, covered by confirm-1)

## Confirmation pass

`confirm-1` froze `8a18e714` (working tree incl. uncommitted fixes) and dispatched all 7 lenses
over `6ff0d162..8a18e714`. Three dispatches were interrupted by the operator mid-pass and
re-dispatched against the same frozen artifact; concurrency's original result stood. Coverage:
7/7, `blocks_approval: false`. New findings, none severe:

| Sev | Lens | Finding | Note |
|---|---|---|---|
| P2 | consistency | `test_wrapup_intent_writes_single_quote_inline_values` (tests/unit/test_memory_tier_removed.py) now asserts the opposite of its name | carried — rename in a follow-up |
| P2 | security | `-file` reads any path the process can reach; content lands in committed intent files | carried — same design as `memory_md --body-file`; every write is shown to the operator before it runs |
| P3 | tests | AC-001 generator "excludes spaces" | premise false: the blacklisted characters are U+2028/U+2029, not spaces — no action |

Outcome: zero new consensus-passed P0/P1 → **APPROVED**. No repair round.

## Final Summary

Grade: A (threshold A) · Rounds: 1 + confirm-1 · Exit reason: converged
Status: APPROVED
human_review_needed: false
Counters: unreviewed 0 (confirm-1 covered the 7 round-1 fixes) · prior-fix 0 · unattributed 0
