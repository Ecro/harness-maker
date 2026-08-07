---
type: review
task_slug: validator-pass-cap-telemetry
status: CHANGES_REQUESTED
created: 2026-08-07
reviewers_invoked: [code-reviewer, security-reviewer, codex, antigravity]
consensus_method: cross-check
voter_pool: 4
consensus_threshold: 2
human_review_needed: true
drift_verdict:
  result: scope_violation
  scope_violations:
    - "no PLAN exists for this task — scope could not be computed"
  scenario_misses: []
  task_slug: validator-pass-cap-telemetry
  computed_at: 2026-08-07T02:10:00Z
---

# REVIEW — validator-pass-cap-telemetry

**Post-hoc review of `a7839253`, which was pushed to main without a review stage.** The user
asked for wrapup-and-push; the review was skipped on that instruction. This document is what
that skip cost.

## 🎯 Round Summary

| Round | Grade | Findings | Fixed |
|---|---|---|---|
| 1 (initial) | **C** | 9 | 9 |
| 2 (re-review of fixes) | **A** | 7 | 7 |

**Final grade: A** — zero unresolved `consensus-passed` P0/P1.
**Status: CHANGES_REQUESTED**, `human_review_needed: true` — the reviewed commit is already
on main, so the fixes are a *follow-up* commit, not a gate that held anything back. §6 is
the part to read.

**Voters:** `code-reviewer`, `security-reviewer`, `codex`, `antigravity` (N=4, K=2). All four
returned findings — the first review this session where `antigravity` did not degrade. Its
prompt was 56 KB here versus 68 KB on the two runs that returned `status: failed`, which
suggests a size threshold in the invoker's truncation path rather than an availability
problem. Worth a follow-up; not a defect in this change.

## 🔍 Drift Findings

**No PLAN exists for this task.** It was a direct-request fix — research/spec/plan were all
skipped — so there is no scope to compare the diff against and `drift_verdict` cannot be
computed. Recorded as `scope_violation` rather than `clean`, because "no baseline to check"
is not the same as "checked and clean", and the frontmatter is machine-read downstream.

That absence is the same decision this review exists to examine: the work skipped the front
of the pipeline and the back of it, and 16 real defects followed.

## ✅ Consensus Findings (round 1)

### P1 — `consensus-passed`

**F1 — `check_run_coherence` groups on `(agent, run_id)`, omitting `stage` and `slug`**
`stage_agent_ledger.py:256` · codex + antigravity, independently.

`run_id` is model-chosen and nothing enforces global uniqueness. An id reused across stages
or slugs merged independent runs and produced fabricated "duplicate pass numbers" and
"multiple terminal rows" — **a checker inventing the defects it exists to find.**
Fixed: the key is all four fields.

**F2 — the glob rescope made 4 of 6 assertions corpus-wide, therefore vacuous**
`test_baseline_delta_attribution.py:47` · codex + security-reviewer + code-reviewer (3/4).

Concatenating every `BASELINE-DELTA-*.md` let the stale P7 document satisfy `ADR-010`, the
ratchet name, the direction word and every per-key attribution row **on behalf of a new
document that contained none of them** — verified: 0 occurrences in the new file, 2 each in
P7. The docstring's own defence ("a stale document cannot satisfy it by accident") held only
for the aggregate, which was the single assertion still reading the baseline.

This was a fix for a per-task-pin bug landed one day earlier. It traded one error for a worse
one, and the strengthening pass that touched the same file did not prompt a re-examination of
what the predicate was pointed at.
Fixed: glob for discovery, then pin every per-document assertion to the document whose
figures match the current baseline.

**F4 — the attribution document's own figures were two baseline generations stale**
`BASELINE-DELTA-validator-pass-cap.md:16` · codex + code-reviewer.

Before read `361 396` / `295 916` — copied from the *previous* task's end state. The real
parent values are `362 419` / `295 582`, so the deltas `+1 797` / `+440` were wrong, and the
paragraph explaining that asymmetry via double-rendering **was explaining a copy error**. The
gate could not catch it: it only checked the *After* figure.

Worse, the document asserted "No round-trip count changed" while
`surface.claude.configure.round_trips` went **3 → 4** with `chars` identical — a movement
this task did not cause (an earlier task changed `configure` without regenerating, and this
regeneration swept the correction in). An audit artifact denying a real movement is the
silent rebaseline `ADR-010` exists to prevent.
Fixed: correct figures, and the `configure` movement named and explained rather than denied.

## 📝 Manual-Only Findings (round 1 — single-source, all verified and fixed)

| # | Sev | Finding |
|---|---|---|
| F8 | P1 | **The schema was manufacturing the incoherence the checker reported.** `_a_sentinel_dispatch_is_terminal_and_explained` forced `terminal=True` on every sentinel, but `plan.md.j2:557` mandates a *retry* after a launch failure — so the mandated `[pass 1 failed, pass 2 succeeds]` shape recorded two terminal rows. Compounding it, sentinels were excluded from the pass sequence, which turned the retry into the gap `(2,)`. Both halves were backwards. |
| F6 | P1 | One malformed row aborted the entire scan (`r["pass_or_attempt"]` subscripted, unguarded `int()`, frozenset membership on an unhashable). Rows come from a shared file concurrent sessions append to, so a single torn line converted the checker from "reports problems" to "reports nothing". Also `terminal` was a truthiness test — the string `"false"` counted as terminal. |
| F5 | P1 | `check_run_coherence` had **no caller**: no CLI subcommand, no rendered guidance, only tests — while its docstring said "Run this before any aggregation". `observability-field-with-no-consumer` reproduced one layer up, in the module whose docstring names that failure. |
| F7 | P1 | `--reason` free text interpolated into shell quotes. The double-quoted launch-error variant left `$(...)` and backticks live on text the model did not author; one apostrophe closed the single-quoted variant. |
| F9 | P1 | `--slug {slug}` and `--run-id <run-id>` unquoted in the emit line (pre-existing; the commit touched that line and did not close it). Same sink in `execute.md.j2`. |
| F3 | P2 | The pre-registration amendment's "conservative direction" argument is **mathematically false** — see §5. |
| F7b | P2 | Rendered guidance stated the terminal invariant as global per `<run-id>`; the real identity is `(agent, stage, slug, run-id)`, so another stage's terminal row could make the model wrongly drop its own. |

## 🔁 Round 2 — the fixes were reviewed, and three were half-done

The re-review verified 5 of 7 fix areas as correct with cited evidence, and found 7 new
findings. The three P1s are worth naming because they share one shape:

**The prose half of a fix was left undone.** F8's schema and checker were inverted, but
`plan.md.j2:593` and `execute.md.j2:249` still instructed `--terminal` on the launch-failure
sentinel — so the guidance kept manufacturing the two-terminal run the code no longer
required. `execute.md.j2` contradicted its own rule **one line above**. The model is driven by
the prose, so a code-only fix does not land.

**The new defensive-coercion test asserted only that the result list was non-empty** — true
for any input, including a perfectly coherent row. Deleting the coercion outright would have
kept it green. The same vacuity class as F2, in a test written to cover a fix for it.

Also fixed in round 2: an in-flight run (no terminal row yet) was reported as a *defect*,
which in a repo running many concurrent sessions would make `coherence` exit 1 almost always
— a gate that always fires is a gate that gets ignored. It is now `incomplete`: printed,
never silent, not a failure. And a torn or non-object ledger line printed `BAD` without
affecting the exit code.

## 🧊 Cross-model findings (frozen @ round 1)

| id | model | sev | file:line | disposition | oracle |
|---|---|---|---|---|---|
| — | codex | P1 | `stage_agent_ledger.py:256` | **accepted** | Confirmed by antigravity independently; grouping key read directly |
| `70ed8b11239ec69c` | codex | P2 | `stage_agent_ledger.py:38` | **accepted** | Arithmetic checked against the ledger's 6 rows — see §5 |
| `29461fc1c47c525f` | codex | P1 | `test_baseline_delta_attribution.py:47` | **accepted** | Figures verified against `git show HEAD~1:` |
| — | antigravity | P1 | `stage_agent_ledger.py:256` | **accepted** | Same defect as codex's first |
| `70631e1209a3b885` | antigravity | P2 | `plan.md.j2:574` | **accepted** | Read against the corrected identity tuple |

## ⚠️ The finding that matters most

**F3 — the amendment's audit trail contained a falsehood that flattered the amendment.**

The pre-registered filter was amended from `pass_or_attempt == 2` to `>= 2` after observing a
third validator pass. To keep that auditable rather than result-fitting, a justification was
written beside the rule:

> *"Widening to `>= 2` grows the denominator, so it makes 'the later pass never changes the
> verdict' HARDER to demonstrate."*

**That is false.** The row admitted by the widening was already known to agree with pass 1, so
`0/2` became `0/3`: the rate is unchanged and its upper bound is *tighter*, making the
deletion case **stronger**. Widening only raises the bar when the added rows are
numerator-eligible in expectation — which inspection had already excluded.

Both codex and code-reviewer caught it independently, and code-reviewer named the direction:
false *in the direction that flatters the amendment*. It had been copied into three places —
the module docstring, this task's delta document, and a `failures.md` entry.

Replaced with the honest justification: the equality discarded real observations, so it did
not measure the registered question. That is a correctness defect, and correcting it does not
depend on which way the numbers move. **The protection is the disclosure, not a directional
defence** — and the falsehood is recorded rather than quietly deleted, because a
pre-registration whose audit trail flatters itself is worse than one with no argument at all.

## 📌 What this review says about the process

`a7839253` reached main because the wrapup-and-push request was followed without a review
stage. That commit contained **9 defects**, three of them reproducing failure classes its own
memory entries had just described: an observability field with no consumer (F5), a gate
passing on stale prose (F2), and the lesson to read artifacts rather than trust prose (F4).

The instrument caught the code; the review caught the instrument. Neither would have happened
on the skipped path.

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | C     | 9             | 0         | —   |
| 2         | A     | 7             | 0         | 7   |

Final grade: **A**
Iterations used: 2 / 3
Exit reason: `converged`
Status: **CHANGES_REQUESTED** (the reviewed commit is already on main; the fixes need their own commit)
human_review_needed: **true**
Counters: unreviewed 0 · prior-fix 7 · unattributed 0
