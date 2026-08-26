---
type: review
task_slug: render-observability-audit
status: APPROVED
created: 2026-08-26
reviewers_invoked: [code-reviewer, security-reviewer, concurrency-reviewer, test-reviewer, codex]
consensus_method: cross-check
run_id: 5982e7298a87
review_base: d0fcd6d76831dee6e73aac976dc529bed8793e1e
human_review_needed: false
drift_verdict:
  result: scope_violation
  scope_violations:
    - tests/snapshot/prod-firmware-spec.expected.yaml
    - tests/snapshot/prod-firmware-task.expected.yaml
    - tests/snapshot/prod-tauri-app-spec.expected.yaml
    - tests/snapshot/prod-tauri-app-task.expected.yaml
    - tests/snapshot/side-python-cli-spec.expected.yaml
    - tests/snapshot/side-python-cli-task.expected.yaml
    - tests/snapshot/side-tauri-app-spec.expected.yaml
    - tests/snapshot/side-tauri-app-task.expected.yaml
    - tests/fixtures/claude_md_relocated_blocks/implementation-patterns.md
    - tests/fixtures/claude_md_relocated_blocks/pre-change-checklist.md
  scenario_misses: []
  task_slug: render-observability-audit
  computed_at: 2026-08-26T02:40:00Z
---

# REVIEW — render + observability audit remediation

## 🎯 Round 1 Summary

**Grade: B → A** after one repair round. Final: **APPROVED**, `human_review_needed: false`.

7 lenses exercised every round (`blocks_approval: false` in round 1 and in the confirmation
pass). `codex` joined as a full heterogeneous voter, `status: invoked`, 51.9 s, 1 finding.

Round 1 raised **3 P1 + 6 P2 + 1 P3**. All three P1s were repaired in round 2; the confirmation
pass returned **zero new consensus-passed P0/P1** across all 7 lenses.

## 🔍 Drift Findings

**`scope_violation` — 10 of 25 changed paths sit outside any PLAN phase's declared scope.**

- **8 regenerated snapshots** (`tests/snapshot/*.expected.yaml`). Phase 2's `merge_hazards`
  named the three render trees the template edit regenerates but not the snapshot fixtures that
  pin them. Each snapshot's diff is exactly one line — the same `body_sha256` — so the blast
  radius is fully accounted for, but the PLAN did not predict the files.
- **2 relocation reference fixtures** (`tests/fixtures/claude_md_relocated_blocks/`). Authored
  in Phase A as the independent pre-move capture AC-002's byte-for-byte test compares against;
  they did not exist when the PLAN was written.

Both are defensible and neither hides unrelated logic. Recorded rather than waived: a PLAN that
did not foresee a file is a PLAN that was wrong about its own scope, which is the fact this
section exists to preserve.

`scenario_misses: []` — S1–S4 each retain a test that exercises them, re-verified in the
confirmation pass rather than assumed from round 1.

## ✅ Consensus Findings

### P1 — all three repaired in round 2

**P1-a · the producer contract contradicted itself** — `templates/agents/stage-delegate_body.md.j2:81`
*Voices: `consistency` (P1) + `codex` (P2) + `robustness` (P2, via the "never" wording).*
"Emit these keys and no others" sat immediately before two sentences saying `steps_skipped` and
`drift_verdict` are accepted — fields the worked example omitted. A delegate following the rule
literally must drop them; one emitting the new schema fields violates the rule. The same block
also said paths must "never" be absolute, the exact case ADR-003 exists to accept.
**Repair:** both optional fields named with worked examples; the path rule restated as
"accepted when it resolves INSIDE the repository".
**Note on the disagreement:** the `design` lens read the same file and reported it "matches the
schema exactly, no scope creep". Two independent voices refuted that. A single-lens review would
have shipped this.

**P1-b · the id-less path copied a peer's identity** — `worktree.py:5780`
*Voices: `concurrency` (P1) + `robustness` (P2).*
Round 1 copied `git_branch`/`task_slug` from `ours[-1]` unconditionally. When the caller has no
session id, `ours` is the **shared session-less bucket**, so `ours[-1]` can be a concurrent
peer's still-open `start` — and the `ours[-1].event == "end"` guard does not catch it, because a
peer's open span *is* a start. The escalation the finding named is the operative part: a null is
excluded by the slug-keyed join AC-003 exists to enable, while a well-formed **wrong** slug is
silently accepted by that same join and attributed to the wrong task. Null is inert; wrong is not.
**Repair:** gated on `attributable = bool(mine)`; both fields stay `None` on the degraded path.
`stage` is deliberately left unchanged (pre-existing behaviour; narrowing it is a separate change
with its own consumers). New regression test `test_id_less_end_does_not_copy_a_peers_pair`,
verified by mutation — reverting the gate kills it.
**Confirmation-pass verdict:** `concurrency` re-examined its own fix adversarially and confirmed
`ours` is filtered by exact `session_id` equality, so `ours[-1].session_id == mine` is a
structural invariant of the comprehension rather than an assumption. It also established that
`_build_spans` never reads `stage` off an `end` event — the local is computed and discarded — so
the remaining asymmetry is inert against the only reader that exists today.

**P1-c · the SPEC write-back never ran** — `specs/SPEC-render-observability-audit.machine.yaml`
*Voice: `robustness` (P1).*
All four ACs carried populated `test_ids` pointing at real tests while still `pending_test: true`.
Production's wrapup renders a hard STOP when `hm spec_machine find-unbound` exits non-zero.
**Repair:** `hm spec_machine mark-tested` for all four.

### P2 — repaired

| Finding | Voice | Repair |
|---|---|---|
| PLAN Phase-0 clause 4 said "add the template to `paths_to_mutate`"; the shipped rationale argues for excluding it | `functionality`, `robustness` | PLAN text moved to record the deliberate exclusion — mutmut is Python-only |
| The ADR-003 widening made a docstring in `test_wrapup_receipt.py` factually wrong | `consistency` | Corrected; `/etc/hostname` now reaches the containment check |
| `test_guidance_names_the_exclusions_file` was a whole-file substring check | `tests` | Bound to a ±12-line window around the extracted command |
| The `promotion-missing` fixture's vault note was inert against the regression it appeared to guard | `tests` | Note removed; the comment now claims only what the row proves |
| `Any` used without the justification CLAUDE.md's python standards require | `functionality` (confirm) | Comment added, recording the `drift_verdict` name collision in the same place |
| `test_an_absolute_claimed_path_is_rejected_rather_than_probed` reads as if all absolute paths are rejected | `functionality` (confirm) | Renamed to `..._escaping_absolute_...` |
| Phase 2 `merge_hazards` asserted an edit to `templates/stages/wrapup.md.j2` | `consistency` (confirm) | Clause deleted — `git status` confirms the file is untouched |
| A test docstring said "four MORE justified passes" and itemized five | `consistency` (confirm) | Corrected to five, with the arithmetic shown |

### P2 — carried, not repaired

- **`SpanEvent`'s docstring does not record the `stage` vs `task_slug`/`git_branch` trust
  asymmetry** (`stage_spans.py:39`, raised by the round-2 re-review). The note belongs where a
  ledger consumer would read it, but `src/harness_maker/stage_spans.py` is a declared **Contract
  Boundary** for this PLAN. Left to the human rather than crossed: the boundary exists to stop
  exactly this kind of reasonable-sounding expansion.
- **`drift_verdict: dict[str, Any]` shares its name with the load-bearing REVIEW-frontmatter
  `drift_verdict`** that wrapup and verify actually read (`security`, confirm). Inert today —
  nothing consumes the receipt's copy. Recorded at the field so a future consumer cannot wire it
  into a gate by name-similarity and inherit an unvalidated `"result"` key.
- **`rel="."` has no dedicated test**; the generic `is_file()` gate covers the failure mode
  (`security`, round 1).
- **`record_path`'s TOCTOU window is inert** because the verdict comes from `receipt.result`, not
  from file content (`security`, round 1).
- **The differential does not exercise the literal `hm` console-script wiring** (`tests`, P3) —
  an accepted scope cut; AC-001's oracle is the arithmetic recipe, not packaging.

## ⚠️ Weak Consensus

None.

## 📝 Manual-Only Findings

None. Every cross-model finding reached a lens voice.

## 🤝 Disagreements

1. **`design` vs `consistency` + `codex` on the producer template.** `design` cleared it as
   matching the schema exactly; the other two found it self-contradictory. Resolved in favour of
   the two: the text was read directly and the contradiction is literal.
2. **`security` claimed the newly-accepted absolute-inside-base branch has no positive test.**
   `disposition: rejected`, authority **AC-004** — `test_confined_accepts_a_contained_absolute_path`
   and the `[document-escapes-root]` golden row both exercise it. The reviewer read only the
   pre-existing `test_wrapup_receipt.py` and missed the new file.
3. **Line-count disagreement on `CLAUDE.md`** — reported as 308, 392 and 393 by different lenses.
   Measured directly: **392**, identical in the working tree, the freeze tree, and under
   `splitlines()`. Under the 500 ceiling on every reading, so AC-002's verdict is unaffected.

## 🧊 Cross-model findings (frozen @ round 1)

Invoked once, at round 1, per the one-call-per-review contract. Rounds 2 and the confirmation
pass re-read this section rather than re-invoking.

| id | model | severity | file | status | disposition |
|---|---|---|---|---|---|
| `9feb5ec62f06f7b8` | codex | P2 | `templates/agents/stage-delegate_body.md.j2:81` | invoked | **accepted** |

**Summary.** "The producer contract contradicts the widened consumer schema… Current tests only
check the consumer and snapshot hash, so this inconsistent producer instruction passes all gates."

**Why it earned its vote.** The second half was the sharp part and it was correct: none of the
three new test files reads the producer text, so no gate in this change could have caught it.
The `consistency` lens found the same defect independently and rated it P1; the cluster is
recorded at P1 on the lens voice, with codex as the corroborating voice.

## 🔬 Confirmation Pass (confirm-1)

Freeze `eb76136a3c06ac53a07214ce1a8da2f45722e80a`, span `d0fcd6d7..eb76136a` — the **whole
review**, not the repair round. All 7 lenses re-dispatched; `blocks_approval: false`. No fixes
applied during the pass.

**Zero new consensus-passed findings at P0 or P1 → APPROVED.** Four P2s surfaced, all repaired
except the two carried above.

The pass earned its cost. The gate's exit is issue exhaustion over a moving target — the last
round's fixes always leave unreviewed, and this repo's `[fail:test]
fix-introduced-defect-passes-all-gates` is at count:4 with every instance on a fully green
four-gate run. Four of the eight P2s repaired in this review were found only here, after the
suite was green.

## 🔁 Oscillation

None. No hunk removed in one round was restored in a later one.

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | B     | —             | 10        | —   |
| 2         | A     | 7             | 3         | 0   |
| confirm-1 | A     | 4             | 3         | 4 (all P2) |

Final grade: **A**
Iterations used: 2 / 3
Exit reason: **converged**

## 📏 Size & Complexity

Measured at round 2 (`review_churn complexity`), after reverts. Report only — no threshold, no gate.

| File | LOC | Cyclomatic | Max nesting | Status |
|------|-----|------------|-------------|--------|
| `src/harness_maker/worktree.py` | 5987 → 5997 | 743 → 745 | 6 → 6 | measured |
| `tests/unit/test_stage_span_end_fields.py` | 214 → 247 | 14 → 18 | 1 → 1 | measured |
| `tests/unit/test_claude_md_second_opinion_guidance.py` | 226 → 244 | 31 → 32 | 2 → 2 | measured |
| `tests/unit/test_wrapup_receipt.py` | 912 → 918 | 100 → 100 | 1 → 1 | measured |
| `tests/unit/test_wrapup_receipt_deterministic_kinds.py` | 300 → 298 | 26 → 26 | 1 → 1 | measured |
| `specs/SPEC-render-observability-audit.machine.yaml` | 145 → 180 | null | null | not-python |
| `src/harness_maker/templates/agents/stage-delegate_body.md.j2` | 109 → 115 | null | null | not-python |
| `tests/snapshot/*.expected.yaml` (×8) | 181 → 181 | null | null | not-python |
| `work-docs/PLAN-render-observability-audit.md` | 604 → 607 | null | null | not-python |

`worktree.py` +2 cyclomatic is the two conditionals of P1-b's gate; the test files' growth is the
new regression test. `test_wrapup_receipt_deterministic_kinds.py` **shrank** — the misleading
fixture dressing came out.

Churn round 2: **1.00** (max path `specs/SPEC-render-observability-audit.machine.yaml`, 16
measured, 0 excluded) — above the 0.30 gate, so the re-review ran rather than being skipped.

Status: **APPROVED**
human_review_needed: **false**
Counters: unreviewed 0 · prior-fix 0 · unattributed 0

## 🚩 Out of scope, reported not fixed

**`spec_machine._pytest_collect_nodeids` returns zero node ids in this repo, so the Production
`find-unbound` gate cannot fail.** Found while verifying P1-c: the gate reported `OK` while all
four ACs were genuinely `pending_test: true`.

```
_pytest_collect_nodeids(cwd) → ran=True, nodeids=0
```

`pytest --collect-only -q` prints per-file summary lines here (`tests/e2e/foo.py: 2`), not node
ids; the helper filters on `"::" in ln` and therefore always yields the empty list. With
`collectable` empty, `pending & collectable` is empty and `find_unbound_closed_type_acs` returns
`[]` unconditionally. Its docstring promises the Production caller "fails closed (never a false
PASS by missing inputs)" — the `ran=True, nodeids=0` path is exactly that false PASS.

Not repaired: `spec_machine.py` is outside this PLAN's scope, and a gate mechanism is its own
task. Raised here because the consequence is broad — every SPEC binding this gate was believed to
enforce has been unenforced for as long as this behaviour has held.

**`tests/unit/test_run_classify.py` fails 7 tests at base.** Reproduced on `fbdc67d6` with a
clean tree (`git status` empty), before any of this work. Unrelated to this change and left alone,
but `main` is currently red.
