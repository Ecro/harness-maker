---
type: plan
task_slug: wrapup-intent-hardening
status: complete
created: 2026-10-04
tags: [harness-maker, plan, jinja2, intent-layer, wrapup, shell-safety]
spec: "[[SPEC-wrapup-intent-hardening]]"
interview_rounds: 0
adrs: 3
validator_outcome: NOT_RUN
summary: "Wrapup 5.7: source rows marked in own table; whole-value format check on every non-file shell arg"
spec_need_verdict: add
spec_need_target: wrapup-intent-hardening
---

# PLAN — wrapup-intent-hardening

## 🎯 Executive Summary

This PLAN covers two follow-ups from the intent-surface-diet review. Both are prose changes to
wrapup Step 5.7 and the close block in `src/harness_maker/templates/stages/wrapup.md.j2`.

1. Step 5 now says that a SPEC/RESEARCH source row is marked in its own table as well as in the
   PLAN table, for all three outcomes.
2. Every non-file argument that 5.7 or close puts on a shell line is checked against a
   whole-value format just before the write. A malformed value skips only its item.

The SPEC (approved, interview round 2) fixes the patterns, the malformed state transitions
(first failure → `failed`, re-offer → `declined`) and the argument boundary.

## 📚 Prior Work

- `[fail:design] repeat-p1-same-shell-quoting-seam`: audit the whole seam in one pass. This
  is why every non-file argument is in scope and not only the ids.
- `[wiki] render-golden-path-and-spec-hash`: normalize the install path to `<SRC>` in goldens.
  Never edit authored fields on a landed SPEC.
- `[fail:design] fix-introduced-defect-passes-all-gates` (count 19): the newly-reachable
  window is the malformed branch itself. AC-003 tests it.
- intent-surface-diet's `tests/unit/test_intent_surface_diet.py` pins step 5's old phrase in
  `S57_RULES`. That entry has to be retargeted to the new phrase.

## 📐 Architecture Decision Records

### ADR-001: Goldens are captured from this worktree before the first template edit
The worktree branches from `f57cef3b` and is still pristine, so no detached worktree is
needed. The goldens hold, per arm, the sha256 of the normalized wrapup render with 5.7 stripped
(AC-005), and the placeholder inventory of 5.7 plus close (AC-002).
**Decided by:** agent

### ADR-002: The argument→rule map lives in the test, independent of the prose
The test classifies each `<placeholder>` on an `hm intent` line, using the CLI's own regexes
(`intent.py:45`, `world.py:75`). An unclassified placeholder fails, so a new argument cannot
ship unruled.
**Decided by:** agent

### ADR-003: The check sentence comes before "run only the selected" in step 5
This makes "edit (step 4) < check < run" a textual order the test can pin on both arms.
**Decided by:** agent

## 🏗️ Technical Design

- Current state: step 5 says "Run only the selected writes, once each, and do not retry. Mark
  each in the PLAN's `## Feedback` table, creating the table when it is absent, and a row taken
  from a SPEC or RESEARCH table in that table too: …". Close asks with no id check.
- Change:
  - Step 5 opens with the whole-value check: patterns, malformed line, name-not-value,
    failed→declined on re-offer, continue.
  - Then "run only the selected writes that passed".
  - Then the marking sentence with `in its own table as well as in the PLAN table`, naming
    `recorded`, `failed` and `declined`.
  - Close gains the `[A-Z0-9-]+` whole-value check and the skip line before the question.
- Affected ratchets:
  - `tests/structural/surface_baseline.json`
  - `tests/snapshot/*.expected.yaml`
  - `tests/structural/autopilot_gate_golden.json` (wrapup)
  - the possible line pin in `tests/unit/test_render_wrapup_delegation.py`
  - `S57_RULES` in `tests/unit/test_intent_surface_diet.py`

## 📝 Implementation Plan

### Phase 1: Goldens + RED tests
- depends_on: none · parallel_group: A · merge_hazards: none
- Scope in: `tests/unit/test_wrapup_intent_hardening.py`, `tests/fixtures/wrapup_intent_hardening/goldens.json`. Scope out: templates.
- Exit: `uv run pytest tests/unit/test_wrapup_intent_hardening.py`. The AC-001…AC-004 tests fail. AC-005 passes, justified as a preservation oracle.
- risk: low · rollback: delete the two files

### Phase 2: Template edit to GREEN
- depends_on: Phase 1 · parallel_group: B · merge_hazards: the wrapup ratchets (Phase 3)
- Scope in: `src/harness_maker/templates/stages/wrapup.md.j2`, plus the `S57_RULES` entry in `tests/unit/test_intent_surface_diet.py`.
- Exit: `uv run pytest tests/unit/test_wrapup_intent_hardening.py tests/unit/test_intent_surface_diet.py`
- risk: low · rollback: `git checkout` the template

### Phase 3: Retire — re-freeze ratchets with attribution
- depends_on: Phase 2 · parallel_group: C · merge_hazards: shared baselines (serial)
- Scope in: `tests/structural/surface_baseline.json`, `tests/snapshot/*.expected.yaml`, `tests/structural/autopilot_gate_golden.json` with the docstring entry in `tests/structural/test_autopilot_gate_render.py`, the line pin if it moved, and `work-docs/BASELINE-DELTA-wrapup-intent-hardening.md`.
- Exit: the full suite green (`ruff`, `ruff format --check`, `mypy --strict src tests`, `pytest`).
- risk: low · rollback: revert the regenerated files

## 🚧 Contract Boundaries

### Do not change
- `src/harness_maker/intent.py` — CLI validation is a Non-goal
- `src/harness_maker/world.py`
- `src/harness_maker/templates/stages/review.md.j2` — 3.3 already checks ids
- `specs/SPEC-intent-surface-diet.machine.yaml` — landed, approved
- Advisory: the 5.7 structure (one batch, 16-item cap, close question) and every intent-surface-diet guard phrase stay

## 🧪 Testing Strategy

The tests are unit render tests over four arms (Production/Side × Claude/Codex), and every
predicate has a mutation control. AC-005 compares a sha256 against the pre-change golden.
AC-006 is the existing structural suite. Render tests prove the text, not agent execution
(SPEC Constraints).

## ⚠️ Risks & Mitigation

| Risk | Mitigation |
|---|---|
| The pattern's `.` breaks the sentence split | Split on `. ` followed by an uppercase letter or end |
| intent-surface-diet AC-006 shrink ratio drops below 0.5 | Check after Phase 2; the growth is about 0.7k per arm against about 8k savings |
| The line pin moves | Re-pin in Phase 3 with an attribution row |

## ✅ Success Criteria

- [x] AC-001 source rows marked in their own table
- [x] AC-002 every non-file shell argument has a whole-value format
- [x] AC-003 a malformed argument skips only its item
- [x] AC-004 close refuses a malformed intent id
- [x] AC-005 wrapup text outside 5.7 unchanged
- [x] AC-006 ratchets attributed, suite green

## Phase status

| Phase | Status |
|---|---|
| 1 | done — A.5 exhausted at round 2; controls verified at the Phase 2 exit; test edits in Phase 2 flagged for /hm:review (user chose Path A) |
| 2 | done — target tests green (98 passed) |
| 3 | done — ratchets re-frozen (wrapup +943 / hm-wrapup +942), full suite 9898 passed, 0 failed |

## Blocker — Phase 1 (A.5 retry exhausted)

- **Round 1 FAIL (4 issues):** AC-005 hashed the frontmatter, which carries a body-wide `content_hash`. AC-002 checked presence only. AC-003 used anchors the SPEC does not fix and left the failed reason unasserted. The AC-001 control matched literal wording. All four were rewritten.
- **Round 2 FAIL (2 issues):** the order-control mutation landed outside step 5, so it could not flip the predicate. `close_ok` did not require "whole value". Both were fixed after the round.
- Current A.4 counts: 26 failed, 9 passed. All 9 passes are justified in the module docstring.
- `[boundaries] comparison not performed — blocked exit`
- **Unblock (user, Path A):** proceed to Phase 2. Controls are verified at the Phase 2 exit, and test edits made in Phase 2 are flagged for `/hm:review`. AC-003 now looks for its clause anywhere in step 5, not in a single sentence (user choice). The `failed` and `declined` transitions are tied to their triggers by regex.

## Phase 2 notes — D.5 newly-reachable window

1. **Window.** Before this change every selected item reached the shell. Now a value that fails its whole-value format branches to "run nothing, print the malformed line, mark it `failed`", and a re-offered malformed row branches to `declined`. The new reachable window is that skip branch, on both the edit paths (Claude Other, Codex reply). Close has a parallel window: a malformed `intent:` value skips the question entirely.
2. **Tests that enter it.** `test_ac003_malformed_skips_item[*]`, `test_ac003_control[*]`, `test_ac003_reason_control` and `test_ac003_order_control` cover the skip branch, its state transitions and the edit→check→run order. `test_ac004_close_rejects_malformed_id[*]` and `test_ac004_control` cover the close window. All of them are in this change.
3. **Absent-case.** A PLAN with no `intent:` never reaches the close check. The "Only when" guard comes first and is unchanged. Rows with no locator do not trigger the locator check, because the check applies only to arguments present on the line.
4. **Limit.** These are render tests: they prove the instruction text, not agent execution (SPEC Constraints).

**Test edits made in Phase 2 (flagged for /hm:review, Path A):** none to `test_wrapup_intent_hardening.py` after the A.5 round-2 fixes and the AC-003 loosening. In `tests/unit/test_intent_surface_diet.py`, the `S57_RULES` entry was retargeted from "in that table too" to the new phrase.

## Boundary comparison (Step 4)

15 changed paths: the template, 4 snapshots, the gate golden and its docstring, the surface baseline, `test_intent_surface_diet.py`, and 6 new files (SPEC ×2, test, goldens, BASELINE-DELTA, PLAN). None equals or sits under a `Do not change` entry (`intent.py`, `world.py`, `review.md.j2`, `SPEC-intent-surface-diet.machine.yaml`), so there are **0 crossings**. Advisory honoured: the 5.7 structure and every intent-surface-diet guard phrase stay, and `test_intent_surface_diet.py` is green.

## Phase 3 note

The first full run failed on `test_render_intent_layer.py::test_ac_015…[record-batch-claude]`. That test pins the capitalised token "Run only the selected writes", and step 5 had been reworded to "Then run only…". The template was restored to "Run only the selected writes that passed…" rather than editing that landed test, and the baselines were re-frozen. Ledger note: the A.5 round-2 row was emitted without `--terminal` before the blocked exit, so that run has no terminal row. No round 3 ran (Path A).
