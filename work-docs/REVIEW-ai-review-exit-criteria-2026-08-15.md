---
type: review
task_slug: ai-review-exit-criteria
status: CHANGES_REQUESTED
created: 2026-08-15
reviewers_invoked: [code-reviewer, security-reviewer, codex, antigravity]
consensus_method: cross-check
human_review_needed: true
drift_verdict:
  result: scope_violation
  scope_violations:
    - src/harness_maker/spec_mutation.py
    - src/harness_maker/spec_machine.py
    - src/harness_maker/verifier_discrimination.py
    - src/harness_maker/command_registry.py
    - src/harness_maker/hm.py
    - src/harness_maker/templates/stages/execute.md.j2
    - PRIVACY.md
    - .gitignore
    - tests/structural/test_comprehension_render_gate.py
    - tests/structural/test_comprehension_zero_cost_golden.py
    - tests/render/test_render_review_read_budget.py
  scenario_misses: []
  task_slug: ai-review-exit-criteria
  computed_at: 2026-08-15T00:00:00Z
---

# REVIEW — ai-review-exit-criteria

## 🎯 Round 1 Summary

**Grade B** (0 consensus-passed P0, 1 consensus-passed P1) against `grade_threshold: A` →
`CHANGES_REQUESTED` → auto-fix loop. Voter pool N = 4 (2 Claude reviewers + 2 models), K = 2.

**`antigravity` returned `failed`** — `status: SUCCESS` with an empty `response`, 8.8 s,
agy-side flakiness on a large prompt. This review is Claude ×2 + codex. Its silence is not
agreement and it cast no vote.

Fifteen findings in round 1, eight more in round 2. **Three of round 1's were reproduced at
source before any repair** (the `-base` ref collision, the freeze-tree omission, the path
escape), and the P0 was confirmed by inspection.

## 🔍 Drift Findings

`result: scope_violation` — real, and authorised outside the PLAN's phase list.

The PLAN's seven phases scope `conditional_router.py`, `lens_coverage.py`,
`review_telemetry.py`, `freeze.py`, `worktree.py`, `review.md.j2`, `plan.md.j2`, the
`harness.yaml` templates, `tests/` and the snapshot baselines. Everything in
`scope_violations` above came from the **follow-ups F1–F5**, which the user authorised in
subsequent instructions and which are recorded with their outcomes in the PLAN's own
`## 📊 F1–F4 outcomes` and F5 sections.

Recorded as a violation rather than laundered to `clean`: the phase list is what the drift gate
reads, and it never contained these files. A reader comparing the diff to the plan should see
the gap and find the authorisation next to it.

`scenario_misses: []` — S1–S10 all carry tests (Phase 4, 5 and 6 files).

## ✅ Consensus Findings

### P1 — `_reap_freeze_refs` deletes a live review's `review_base` [2/4]

`code-reviewer` and `security-reviewer` independently, same file, same line, same tier, same
CONCLUDE. Liveness was proved only by an `hm/<slug>` branch or a `.worktrees/<slug>` directory —
neither of which the review slug owns under `worktree.enabled: false` (the Side default) or
inside `/hm:loop` (worktrees are `execute-<uuid>`). `prune_stale` runs from `worktree create`,
`task-land` **and** `drain`, and `/hm:health` calls `drain` unconditionally, so a peer session
could delete the base mid-review and force a restart from round 1.

**Repaired twice.** Round 1: an empty live set returns early, plus a 6 h grace window. Round 2
found the window inert for the ref that matters — `_ref_age_seconds` read the **commit's**
date, and `<slug>-base` points at a merge-base that is days or months old, so it was born past
the window. `store_review_base` now writes a stamp and the base ref is dated by that.

## ⚠️ Weak Consensus

None. Every other finding was single-source.

## 📝 Manual-Only Findings

All repaired. Round 1, by source:

| Severity | Source | Finding |
|---|---|---|
| **P0** | code-reviewer | Five `hm freeze` / `hm lens_coverage` calls omitted `cd <WT> &&`, so with worktree ON the confirmation pass froze the **base** repo — a tree with none of the fixes — found nothing, and approved |
| P1 | code-reviewer | Per-round coverage made a healthy review permanently unapprovable from round 2 |
| P1 | code-reviewer | `_MUTMUT_ABSENT` was a substring test against arbitrary subprocess output; `--runner` output could force a non-gating skip |
| P1 | code-reviewer | `verifier_discrimination` episode key dropped `stage`, re-introducing a merge defect the sibling module documents |
| P1 | code-reviewer | Dispatch-sentinel rows counted as `bound_by_the_cap` — a launch failure blamed on verifier strictness |
| P1 | codex | `hm freeze commit --pass base` wrote `<slug>-base`, overwriting the review_base store; the next confirmation diff spans nothing |
| P1 | codex | An empty temporary index makes `git add -A` omit a **tracked** file matching `.gitignore` — the frozen tree is not the working tree, and the file reads as deleted |
| P1 | codex | `resolve_review_base` used a local branch name; a clone without it fell through to `HEAD~1` |
| P1 | security-reviewer | `mutation_runner` reaches mutmut's `--runner`, which mutmut runs under `shell=True` on Windows |
| P2 | code-reviewer | Emoji counters overrode worded ones, contradicting the code's own stated precedence |
| P2 | code-reviewer | `EXCLUSIONS_FILE` was honoured by `agents` only, though its contract says "any aggregate" |
| P2 | codex | Duplicate ledger rows silently rewrote a recorded FAIL into a PASS |
| P2 | security-reviewer | The freeze commit sweeps untracked, non-ignored files into a persistent ref |
| P2 | security-reviewer | Model-authored ledger strings are echoed back into a session's context |

Round 2, all repaired except where noted:

| Severity | Source | Finding |
|---|---|---|
| **P1 [2/3]** | both | The grace window dated the **commit**, not the ref write — `-base` was never protected |
| P1 | code-reviewer | Repair #2 closed only the `missing == []` half; the partial case stayed unapprovable, and the prose told the model to compute a union it is forbidden to substitute for the CLI's field |
| P2 | security-reviewer | The round-1 early return meant **nothing** reaps freeze refs under the Side default — a leak the repair created |
| P2 | security-reviewer | The `mutation_runner` docstring claimed the allowlist stops a hostile field. It does not |
| P2 | code-reviewer | `origin/<branch>` first over-scopes when local is ahead — this repo pushes manually and rarely |
| P2 | code-reviewer | Episode classification on `order[-1]` dropped an episode whose **last** pass failed to launch |
| P2 | code-reviewer | `round_dir`'s new `ValueError` escaped `main` as a traceback, leaving the gate no verdict |
| P2 | security-reviewer | A malformed exclusions file silently re-admitted the rows it exists to drop |

**Accepted without repair, with reasons recorded:**

- *The freeze commit sweeps untracked files.* `read-tree HEAD` widens the tree by exactly one
  class — tracked-but-ignored files, which the user already carries in `git status` and which
  wrapup commits anyway. Net secrets delta ≈ zero against a real AC-004 fidelity gain.
- *Ledger strings echoed into a session.* Writer and reader are the same harness; the payload is
  already being read as JSON two lines above. Escalate if any ledger writer ever accepts a field
  from outside the session.

## 🤝 Disagreements

**`lens_coverage` path escape** — `codex` rated it **P1** (a `--slug ../../tmp/fake` points the
checker at an arbitrary directory whose placeholder files satisfy coverage);
`security-reviewer` read the same code and **deliberately did not raise it**, judging it
un-exploitable: the operation is a read whose only output is a set of known lens names, and the
caller supplying the argument also writes the result files.

Not adjudicated. Containment cost two lines, so it was added without deciding who was right,
and both positions are recorded here and in the test's docstring.

## 🧊 Cross-model findings (frozen @ round 1)

| id | model | severity | finding | disposition |
|---|---|---|---|---|
| `co-1` | codex | P1 | `lens_coverage` path escape + coverage satisfiable by placeholders | accepted (contained; see Disagreements) |
| `co-2` | codex | P1 | `--pass base` overwrites the review_base store ref | accepted — reproduced |
| `co-3` | codex | P1 | Freeze tree omits tracked-but-gitignored files | accepted — reproduced on a probe repo |
| `co-4` | codex | P1 | Base resolution uses a local branch, not the remote-tracking ref | accepted — reproduced |
| `co-5` | codex | P2 | Duplicate ledger rows rewrite a recorded verdict | accepted |
| — | antigravity | — | `status: failed`, empty response (agy-side flakiness, 8.8 s) | no vote |

Frozen at round 1; rounds 2 and 3 re-read this section rather than re-invoking either model.

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | B     | —             | 15        | —   |
| 2         | B     | 15            | 8         | 8   |
| 3         | —     | 8             | 0         | not run |

Final grade: **B**
Iterations used: 2 / 3
Exit reason: `operator-stop` — the user directed that round 3 not run and the work be committed.
Status: **CHANGES_REQUESTED**
human_review_needed: **true**
Counters: unreviewed 8 · prior-fix 8 · unattributed 0

**What `unreviewed 8` means, plainly.** Iteration 2's eight repairs were never re-reviewed. Of
round 2's eight findings, **all eight were produced by iteration 1's repairs** — this change's
fix-introduced-defect rate is 8/15 in round 1 → 8, i.e. close to the 1:1 this repository
records at `[fail:test] fix-introduced-defect-passes-all-gates` (count:7). There is no reason
to think iteration 2 is different in kind; it is simply unmeasured.

The suite, `ruff`, `ruff format` and `mypy --strict` are green over those repairs, which is
evidence about the gates and not about the code — every one of the 23 findings above was found
by reading, and every one of them was green.
