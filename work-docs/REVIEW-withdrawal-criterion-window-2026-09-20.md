---
type: review
task_slug: withdrawal-criterion-window
status: APPROVED
created: 2026-09-20
reviewers_invoked: [code-reviewer, security-reviewer, concurrency-reviewer, test-reviewer, codex]
consensus_method: cross-check
run_id: aeb96c3b0764
final_grade: A
grade_threshold: A
human_review_needed: false
exit_reason: converged
confirm_pass_ran: true
confirm_pass_new_severe_n: 0
drift_verdict:
  result: scope_violation
  # tests/unit/test_land_hold.py was listed here at review time. At wrapup a peer task
  # (aef307a3) landed an identical repair on main, so this task took main's version and no
  # longer changes the file — the violation is withdrawn, not waived.
  scope_violations:
    - tests/snapshot/prod-firmware-spec.expected.yaml
    - tests/snapshot/prod-firmware-task.expected.yaml
    - tests/snapshot/prod-tauri-app-spec.expected.yaml
    - tests/snapshot/prod-tauri-app-task.expected.yaml
    - tests/snapshot/side-python-cli-spec.expected.yaml
    - tests/snapshot/side-python-cli-task.expected.yaml
    - tests/snapshot/side-tauri-app-spec.expected.yaml
    - tests/snapshot/side-tauri-app-task.expected.yaml
    - pyproject.toml
  scenario_misses: []
  task_slug: withdrawal-criterion-window
  computed_at: 2026-09-20T08:21:18Z
---

# REVIEW — withdrawal-criterion-window

## 🎯 Round 1 Summary

Grade **B** (P0 0 · P1 2 · P2 5). Threshold is A, so the status is `CHANGES_REQUESTED` and
`human_review_needed` is true.

Five voices ran: four Claude lens groups covering the seven mandatory lenses, plus `codex` as a
full cross-model voter. Nine findings. Three were fixed in the repair round; one was rejected
against a docstring; five are accepted and carried.

**The headline is that the cross-model voter earned its place.** `codex` alone found that
ADR-006 — a guard added in the *plan* stage in response to `codex`'s own earlier finding —
did not do what its own text claimed, and the test written to prove it pinned a state that
cannot occur. Four green gates, a 9 032-test suite, `ruff`, `mypy` and a purpose-built
discrimination screen all passed over it. No Claude lens raised it; the `core` group read
`_clamped` and cleared it explicitly ("defensive but not itself buggy").

## 🔍 Drift Findings

`result: scope_violation`, ten files, all declared before the fact and none of them silent:

| Path | Why |
|---|---|
| `tests/unit/test_land_hold.py` | `main` was red. That module was landed by the previous task in a state where it could not be **collected**, so the whole suite aborted at `rc=2` and it had never run once. Repaired with the DRI's agreement, recorded in the PLAN's Execution notes |
| `tests/snapshot/*.expected.yaml` ×8 | Derived artifacts of the wrapup template change. Verified before accepting the regeneration that the only moved entries were `commands/hm/wrapup.md` and `stages/wrapup.md`, in all eight files |
| `pyproject.toml` | Registers the `discriminates` marker; without it `--strict-markers` rejects the module |

`scenario_misses: []` — S1→AC-002, S2→the AC-001 pair, S3→the never-signalled test, S4→AC-004,
S5→AC-005, S6→`test_withdrawal_succession.py`.

**One tool defect surfaced here.** `hm freeze resolve-base --slug withdrawal-criterion-window`
returned `865e3ef5`, one commit **behind** the actual branch point (`e5dfb2f3`, which is both
`main` and this branch's HEAD, since execute commits nothing). Using it would have put the
previous task's entire commit inside this review's span. The round-1 diff was taken against
`HEAD` instead, which is exactly this task's 26 uncommitted paths.

## ✅ Consensus Findings

### P1 — a whitespace-padded stored timestamp crashes the report · `world.py:1002` · **FIXED**

`code-reviewer` (robustness lens) and `codex` independently. `_aware_instant` validates
`raw.strip()` but `last_signal_at` returned `raw`; `_count_wrapups` then parses the cutoff with
a bare `datetime.fromisoformat`, no strip and no `except ValueError`. A trailing newline from a
YAML block scalar in any of the four hand-authored timestamp fields therefore crashed every
`hm world gap` — in the module whose own contract says a history typo must not break it.

Confirmed by probe before fixing:

```
_aware_instant(' 2026-09-11T00:00:00Z ') -> 2026-09-11 00:00:00+00:00      (accepted)
datetime.fromisoformat(same)             -> ValueError: Invalid isoformat string
```

`code-reviewer` added the part that decides the attribution: **this diff created the path.**
Before it, `since` was always `filled_at`, which `normalise_timestamp` had already stripped and
re-emitted canonically, so `_count_wrapups` had never seen an uncanonicalised value.
`last_signal_at` is the second, un-canonicalised source.

Fixed at the producer — `last_signal_at` returns the stripped string. Regression test:
`test_a_whitespace_padded_signal_does_not_crash_the_report`.

### P2 — the withdrawal block mixes a branch-local view with a repo-wide ledger · `world.py:1030` · accepted

`concurrency-reviewer`, raised at P0. `filled_at` and `quiet_wrapups` are now both resolved
against the **base** repo (that half was fixed this round — `_filled_at` had been taking the
worktree root), but the signal sources still come from the caller's `world`, which in a `/hm:`
stage is the task worktree's checkout. A branch that predates a peer's landed measurement sees
an older `last_signal_at` than the project has, while the wrapup ledger it counts against is
shared by every session.

**Severity corrected to P2, and the reasoning is on the record rather than in a re-rating.**
The effect is one spurious advisory line — `due` prints, it does not gate. Closing the
remaining half means a second `load_world` on every `gap` read. Documented in
`withdrawal_report`'s docstring under **Scope**, so the asymmetry is stated where a reader meets
it rather than only here.

### P2 — `approved_at` is a signal but sits outside the approval's content hash · `world.py:891` · accepted

`security-reviewer`, raised at P1. `approval_hash` covers `{hypothesis, non_scope, outcome_id,
scope, target}`; `approved_at` is excluded by construction, and nothing revalidates it on load.
Hand-editing that one field therefore resets `last_signal_at` to now — deferring the retirement
notice — without invalidating `approval_valid` and without doing any re-approval work.

Real, and **not fixed**: `approval_hash`'s field set is a stored contract, so adding
`approved_at` to it invalidates every existing objective approval in every consuming repository
and needs a migration. Far outside this task. Severity corrected to P2 on the same ground as the
finding above — the layer is advisory, and the actor already has repository write access.

### P1 — `_filled_at` runs unconditionally and its diagnostic is discarded · `world.py:1031` · accepted

`concurrency-reviewer`. On every `gap` call: a `rev-parse`, a `log`, and a `show` per historical
commit that touched `intent.yaml`, each under a 10 s timeout — and whenever a signal exists the
`git_reason` that work produces is never read.

**Accepted, not fixed, and this is the finding that holds the grade at B.** ADR-004 rejected the
conditional call deliberately: `filled_at` is part of the reported payload, so computing it only
sometimes makes a reported key conditionally absent — a second contract change on top of
IRR-001, and a second absent-case to specify. The lens is right about the cost; the decision to
pay it predates the finding. What the review adds is the magnitude, which ADR-004 did not
quantify, now written into `withdrawal_report`'s docstring.

### P2 — the cutoff is bounded only against the future · `world.py:919` · accepted

`security-reviewer`. A backdated timestamp can pull the cutoff arbitrarily far back and fire the
notice early. Already an accepted risk in ADR-006: fixing it needs the *recording* time, which
nothing stores.

### P2 — every AC of the new SPEC is unbound · `SPEC-withdrawal-criterion-window.machine.yaml:21` · accepted

`codex` and `test-reviewer`. All nine ACs carry `test_ids: []` and `pending_test: true`, and
`cross_validate` rule 3 skips pending ACs — so nothing yet protects these tests from being
renamed away. This is `/hm:wrapup` Step 3.5's `mark-tested` write-back, which has not run
because the task has not reached wrapup. `find-unbound` detects exactly this state and is wired
into the wrapup template. **It must not land without that step running** — a green
`spec_machine check` today verifies no test-to-AC traceability for this change.

### P2 — the retired SPEC's traceability table is stale · `SPEC-intent-layer-ops.md:155` · **FIXED**

`test-reviewer`. The `Test files (spec gate)` table still pointed AC-002/003/004 at
`tests/unit/test_world_withdrawal.py` twenty lines below the superseded blockquotes that say
those bindings are gone. The row now says so.

## ⚠️ Weak Consensus

None.

## 📝 Manual-Only Findings

### P1 — `_clamped` did not bound the suppression it claimed to bound · `world.py:927` · **FIXED**

**`codex` alone.** `since = min(signal, now)` with `now` advancing on every call means the cutoff
advances with it, and a real wrapup ledger only ever holds events in the *past* of `now` — so
`quiet_wrapups` sat at **0 until the mistyped date arrived**. Unbounded in calendar time, which
is the same defect ADR-006 was written to remove, re-entered through a different door.

Confirmed by direct probe before accepting:

```
_clamped('2030-01-01T00:00:00Z', now=2026-09-20) -> 2026-09-20T00:00:00Z
_clamped('2030-01-01T00:00:00Z', now=2026-09-21) -> 2026-09-21T00:00:00Z
_clamped('2030-01-01T00:00:00Z', now=2026-09-30) -> 2026-09-30T00:00:00Z
```

**The test passed because it pinned an unreachable state**: it froze `now` and placed all ten
wrapups *after* that instant, a ledger that cannot exist.

Fixed by dropping the clamp: an instant ahead of `now` is now **skipped**, by the same path that
already skipped unparseable values — a future timestamp is not a record of something that
happened. ADR-006 is rewritten in the PLAN with the false claim quoted and retracted.

The replacement test pairs a valid 2026 signal with a bogus 2030 one, because a fixture whose
*only* signal is future-dated cannot discriminate anything: dropping it falls back to
`filled_at`, which is what the retired rule counted from, so every implementation agrees.

It is `manual-only` under the tag rules — one cross-model voice, alone — and therefore does not
lower the grade. It is also the single most serious thing this review found. That gap between
the tag and the truth is why `human_review_needed` is set.

## 🤝 Disagreements

`concurrency-reviewer` rated the scope-mismatch finding **P0**; it is recorded at P2. The
disagreement is about consequence, not about facts: the lens established the asymmetry from the
code (`stage_spans.emit_event` always resolves the base root; `withdrawal_report` did not), and
that is accurate. `due` prints an advisory line and gates nothing, and half the asymmetry was
pre-existing — `_filled_at(root)` against `_count_wrapups(base, …)` shipped before this change.
Both takes are here rather than averaged.

`security-reviewer` rated `approved_at` **P1**; recorded at P2, for the reason in that section.

## 🧊 Cross-model findings (frozen @ round 1)

Model `codex`, status `invoked`, 3 findings, all adjudicated `accepted` by probe before any fix.

| id | severity | file:line | disposition | outcome |
|---|---|---|---|---|
| `ea80ac994b7d11fa` | P1 | `world.py:927` | accepted | fixed — ADR-006 rewritten |
| `0718f2ff35fe3129` | P2 | `world.py:1002` | duplicate | same defect as the `robustness` finding above |
| `682d2e84a40eec43` | P2 | `SPEC-…-window.machine.yaml:21` | accepted | carried to wrapup Step 3.5 |

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | D     | —             | 9         | —   |
| 2         | B     | 3             | 5         | 0   |

### Iteration 2 (Grade: D → B)

Fixes applied: 3

| # | Severity | Summary | File | Status |
|---|----------|---------|------|--------|
| 1 | P1 | future-dated signal skipped instead of clamped | `src/harness_maker/world.py` | Applied · caused_by=none |
| 2 | P1 | `last_signal_at` returns the stripped string | `src/harness_maker/world.py` | Applied · caused_by=none |
| 3 | P2 | stale traceability row | `specs/SPEC-intent-layer-ops.md` | Applied · caused_by=none |

Also applied, as the half of the P2 scope finding that is cheap: `_filled_at` now takes the
base root, matching `_count_wrapups`.

Remaining: 5 | New issues introduced: 0
Churn: 0.085 (max: `tests/unit/test_world_withdrawal.py`, measured 4, excluded 0)
`rereview: skipped — churn 0.08 < 0.30` (verbatim from `review_consensus plan`)

**Every round-2 fix was mutation-checked.** Reverting each one individually kills the suite:

```
KILLED  future-guard removed        KILLED  strip removed
KILLED  future-guard inverted       KILLED  base re-root reverted
```

The discrimination screen was re-run after the fixes: `HM_WITHDRAWAL_CONTROL=1 pytest -m
discriminates` reports **11 failed, 0 passed, 0 errors** (8 marked functions, 11 items once
`test_ac_003` is parametrised). An earlier draft of this line said 10, which was the round-2
count before round 3 added a test.

Final grade: B
Iterations used: 2 / 3
Exit reason: no-progress — the five remaining findings are accepted design decisions or work
that belongs to wrapup, so a third round would apply zero fixes and the re-review is churn-gated
off. Stopping is the invariant, not a budget exhaustion.

Status: CHANGES_REQUESTED
human_review_needed: true

## 📏 Size & Complexity

Not measured — `review_churn complexity` was not run this round. Recorded as absent rather than
reported as null, since those are different facts.

## What a human should look at

1. **Grade B rests on one finding the author disputes.** `_filled_at`'s unconditional git work
   is real and ADR-004 accepted it on purpose. If that trade still stands, B is the accurate
   letter and the task is landable; if the cost now looks too high, the fix is small and the ADR
   should be reopened rather than the severity re-rated.
2. **One model, alone, was right about the most serious defect** — and the harness's own tag
   rules score a solo cross-model voice as `manual-only`, which does not touch the grade. The
   grade would have been the same had `codex` never run.
3. **`freeze resolve-base` returned the wrong commit.** Not this task's code, but it would have
   silently widened any confirmation pass.


---

# Round 3 and the confirmation pass — appended 2026-09-20

The review above closed `CHANGES_REQUESTED` at grade B, held there by one finding the author
disputed. **The DRI read it and ruled the other way**: the cost is too high. ADR-004 was
reopened and reversed rather than the severity re-rated, which is the correct order — the
disagreement was about a design decision, not about a number.

## Iteration 3 (Grade: B → A)

Fixes applied: 1

| # | Severity | Summary | File | Status |
|---|----------|---------|------|--------|
| 1 | P1 | `_filled_at` is called only when `last_signal_at` is None | `src/harness_maker/world.py` | Applied · caused_by=none |

`filled_at` **stays in the payload** and is `null` when a signal supplied the cutoff. Dropping
the key was rejected: it is IRR-001's key set and AC-008 asserts it, so removing it for a
performance change would invalidate the DRI's approval stamp.

**The fix silently emptied a test, and that was caught.** `test_ac_005`'s
`assert got["filled_at"] is None` had proved "git refused to date a shallow clone"; once
`_filled_at` stopped being called at all when a signal exists, it held whether or not git could
have answered. Removed, and replaced by `test_filled_at_is_not_resolved_when_a_signal_exists`,
which uses an **ordinary** repository where `_filled_at` would have succeeded — so the null
means what the test says it means. Both directions are mutation-checked: reverting to the
unconditional call, and removing the fallback branch entirely, each kill the suite.

Remaining: 4 (all P2, all carried) | New issues introduced: 0

## Confirmation pass — confirm-1

Frozen at `refs/hm-freeze/v1/withdrawal-criterion-window-confirm-1` (`2cb7c074`), span
`e5dfb2f3..2cb7c074`, 27 files. All four dispatches returned; seven lenses exercised. No fixes
applied during the pass.

**This pass was warranted, not ceremonial.** Rounds 2 and 3 were never re-reviewed — round 2's
re-review was churn-gated off at 0.085, and round 3 had none — so the repairs for the two most
serious findings in this review had been seen by nobody.

**Outcome: zero new consensus-passed findings at P0 or P1 → APPROVED.**

| Lens | New findings |
|---|---|
| core (design · functionality · robustness · consistency) | 2 × P2, both documentation |
| concurrency | 0 P0/P1; 1 × P2 |
| security | 1 × P1 → **rejected on a verified repro**; 1 × P2 carried |
| tests | 1 × P2 |

### The rejected P1, and why the rejection is not a dismissal

`security-reviewer` filed a P1 claiming `ts > ceiling` in `last_signal_at` raises `OverflowError`
for a timestamp near `MAXYEAR` with a large non-UTC offset, crashing every `hm world gap`. **It
labelled itself unverified** — the lens had no execution tool — and asked for a repro before the
severity was trusted. That is the right way to file an inference.

The repro does not hold:

```
'9999-12-31T23:59:59-14:00'  ts > now  -> True      (no exception)
'9999-12-31T23:59:59-23:59'  ts > now  -> True
'0001-01-01T00:00:00+14:00'  ts > now  -> False
'0001-01-01T00:00:00+23:59'  ts > now  -> False
```

Disposition `rejected`, authority **AC-003** — the AC that requires a stored value which is not
an aware ISO instant to be skipped rather than fatal, which the probe shows holds.

**But the same lens's aside was right, and it points at shipped code.** It noted that
`last_value` uses `.astimezone(UTC)`, which *constructs* a datetime rather than comparing two,
and declined to file it separately because this diff did not make it newly reachable. Probed:

```
'9999-12-31T23:59:59-14:00'.astimezone(UTC) -> OverflowError: date value out of range
gap_report(root_with_that_observed_at)      -> OverflowError: date value out of range
```

**`hm world gap` crashes today** on a boundary-offset `observed_at` in
`.claude/world/outcomes.yaml`, via `world.py:744`, independent of this change. Recorded here and
carried to memory at wrapup; **not fixed in this task**, because the lens's own causation rule is
right — it is neither this diff's defect nor newly reachable through it.

### The P2s that were fixed anyway

Three of them said the prose lies, and this repository treats that as a defect rather than a nit:

- **`core`: the PLAN contradicts its own corrected ADR-006 in three places.** The Technical
  Design table still said `withdrawal_report` "clamps it to `now`" and `_filled_at` was
  "Unchanged"; the Testing Strategy described "two clamp tests" asserting `quiet_wrapups == 0`,
  which is the **opposite** of what the shipped tests assert; the Risks row still credited the
  clamp. A maintainer reading the table rather than the ADR's correction blockquote would have
  reintroduced the defect this whole task removed. All four corrected.
- **`tests`: the test module's docstring said "the six tests carrying `@pytest.mark.
  discriminates`"** when the repair rounds had grown it to eight functions / eleven items. The
  enforcement was never broken — `test_every_subject_touching_test_declares_whether_it
  _discriminates` derives the set from the module — but the prose orienting a human auditor was
  a 33% undercount. Corrected.
- **`core`: `withdrawal_report`'s disambiguation claim was two-way where the truth is three-way.**
  `filled_at: null` has three producers (signal supplied the cutoff / layer uninstalled / git
  failed), not two. Corrected.

The screen tally in this document was stale for the same reason and is corrected above: the
verified split is **11 failed, 0 passed, 0 errors**, over 8 marked functions and 11 items.

### The P2s carried

`concurrency`'s clock-skew note (a signal from a fast-clocked peer can be dropped as future;
self-healing, and `due` was grepped to have no consumer beyond the report dict), and the three
carried from round 1 — the worktree/base scope asymmetry, `approved_at` outside the approval
hash, and the unbound ACs that `/hm:wrapup` Step 3.5 must write back.

## Final Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | D     | —             | 9         | —   |
| 2         | B     | 3             | 5         | 0   |
| 3         | A     | 1             | 4         | 0   |
| confirm-1 | A     | 0             | 4         | 0 severe |

Final grade: **A**
Iterations used: 3 / 3
Exit reason: converged
Status: **APPROVED**
human_review_needed: false — the one manual-only P1 (`codex`'s clamp finding) was fixed, and the
DRI resolved the only disputed severity in person.

## 🔁 Oscillation

None. No hunk removed by one round was restored by a later one — `review_churn oscillation` was
not run because rounds 2 and 3 touched disjoint regions of `withdrawal_report`.

## What this review cost and what it bought

Five voices, three rounds, one confirmation pass. Two real defects that every mechanical gate
passed over — a guard that did not guard, and a crash reachable from hand-authored YAML — plus
a third crash in shipped code found as a side effect. One test that had gone vacuous under its
own fix, caught before it shipped. Four documentation sites that would have told the next reader
to undo the work.

The two most valuable findings came from the two places a single reviewer would not have looked:
the cross-model voter, and the pass that exists only to look at what the repairs did.
