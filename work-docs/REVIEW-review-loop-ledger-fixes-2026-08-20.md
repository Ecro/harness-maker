---
type: review
task_slug: review-loop-ledger-fixes
status: CHANGES_REQUESTED
created: 2026-08-20
run_id: 53001da6b35c
review_base: 7da818470aeb2ff8a72a2caac064a22b970746c3
reviewers_invoked: [design, functionality, robustness, consistency, security, concurrency, tests]
consensus_method: solo-lens (ADR-007)
human_review_needed: true
drift_verdict:
  result: scope_violation
  scope_violations:
    - tests/unit/test_review_input_boundaries.py
    - tests/snapshot/*.expected.yaml
  scenario_misses: []
  task_slug: review-loop-ledger-fixes
  computed_at: 2026-08-19T14:25:00Z
second_opinion_results:
  - model: codex
    status: skipped
    reason: "exit 1 — usage limit reached, retry after 2026-08-20 14:35"
    reconciliation: []
  - model: antigravity
    status: skipped
    reason: "agy envelope status 'CANCELED'"
    reconciliation: []
---

# REVIEW — review-loop-ledger-fixes

**Status: CHANGES_REQUESTED.** Confirm-2 returned five new P1s; per the stage's own rule no third
confirmation pass is dispatched in one `/hm:review`. Nothing below is fixed.

## 🎯 Summary

| Round | Grade | Lenses | New severe | Note |
|---|---|---|---|---|
| 1 | D | 7 | P0 1 · P1 1 | cross-model voters both skipped (quota) |
| 2 (repair) | A | 1 (churn-gated) | — | churn 0.348 ≥ 0.30 |
| confirm-1 | — | 7 | P1 2 | both **created by** round 2's repair |
| confirm-1 repair | A | — | — | build green |
| confirm-2 | C | 7 | **P1 5** | all five in the confirm-1 repair |

Exit reason: `confirm-2-dirty`. Iterations used: 2 / 3 (the confirmation repair round is budgeted
separately and did not consume one).

## 🔁 What this review actually established

**The change's stated purpose works.** Producers write the measured numbers and `emit` reads them
with no model transcription — verified end to end with the code under review, from the base cwd
the stage actually runs `emit` in: `round_record.read` returned round 3's
`disposition_counts` written by `finalize` inside the worktree.

**But it did not work as first committed, and it still cannot be exercised through the rendered
stage.** Two independent reasons, both measured rather than argued:

1. **The P0 (fixed).** The store was cwd-relative. Producers run with `cd <WT> &&` and `emit` does
   not, so the record sat in `.worktrees/<slug>/` and the base repo had no such directory.
   Measured live during round 1. Four lenses raised it independently. Fixed by anchoring on the
   base root; a real-git-worktree regression test now gates it. `cd <WT>` on `emit` was rejected
   as the repair — it would move the telemetry ROW into the worktree, which `task-land` deletes.
2. **The rendered command runs the wrong code (NOT fixed, out of this diff's scope).**
   `uv run --with $HOME/harness-maker` resolves to the **base checkout**, so a stage running
   inside `.worktrees/<slug>/` executes `main`'s Python, not the branch under review. Confirmed:
   the terminal `emit` in this very review wrote a row with no `disposition_counts` key at all,
   because the code that produces it is not on `main` yet. Any harness change is therefore
   unverifiable through its own rendered stage until it lands.

## ⚠️ Surviving findings (P1)

None are fixed. All five are in the `flock` + run-identity machinery added by the confirm-1
repair — that is, in the device protecting the feature, not the feature.

| # | File:line | Finding | Lens |
|---|---|---|---|
| 1 | `round_record.py:169` | `run_id` is snapshotted **before** the flock. A writer queued behind the lock can land with a stale id, see a mismatch, and wipe a newer run's already-merged data — strictly worse than the chimera it replaced. | concurrency |
| 2 | `round_record.py:172` | The blocking `flock` has no timeout. It raises neither `OSError` nor `ValueError`, so both call sites' `except` gives no protection — any local process writing the shared store can hang the review forever. | security |
| 3 | `test_round_record_producers.py:140` | **Nothing exercises the lock.** All five new tests are single-threaded and sequential; deleting the `flock` block leaves the entire suite green. | tests |
| 4 | `round_record.py:66` | The `RuntimeError`-on-symlink-loop claim is contradicted by `second_opinion_invoke.py:462` ("OSError (symlink loop…)") on the same call, and the probe backing it is not committed. The claim is correct — re-verified on CPython 3.12 — but the tree contains no evidence, and the test mocks the resolver rather than reproducing the loop. | consistency |
| 5 | `BASELINE-DELTA-…:116` | "+5" contradicts the doc's own figures and the PLAN's "1908+6". ADR-010's whole purpose is that this document account for the ratchet movement. | consistency |

## 📝 Surviving findings (P2/P3)

Not auto-fix eligible — P2/P3 leave the queue except at grade D/F (this change's own new rule).

- `round_record.py:178` — `open --force`, the documented recovery from an abandoned run, mints a
  new id and therefore trips the replace branch, discarding a round's already-measured data. The
  two modules are each correct read alone. *(robustness)*
- `round_record.py:218` — `read()` re-implements `_read_raw()`'s parser, in a module whose stated
  purpose is that a number comes from exactly one place. *(design)*
- `round_record.py:59` — `_base_root` is the only wrapped caller among ~10; `review_run` itself,
  which this module depends on, calls the resolver bare, so the hazard fires there first. Fix
  belongs in the shared resolver. *(design)*
- `round_record.py:169` — `merge()` resolves the base root twice, paying `git` subprocess work
  twice per call. *(consistency)*
- `round_record.py:172` — the lock path skips the containment check `record_path` applies. Not
  exploitable today (nothing is written to the fd) but inconsistent with the file's own
  discipline. *(security)*
- `round_record.py:112` — no janitor removes `.hm-round/*.json` or the `.lock` files. *(design,
  robustness)*
- `test_round_record_producers.py:258` — `_open_run` hand-writes `review_run`'s on-disk format; 2
  of the 3 run-aware tests pass regardless of whether it still matches. *(tests)*
- `test_round_record_producers.py:314` — the fail-open test mocks the resolver, so it cannot
  re-verify the symlink-loop premise on another interpreter or platform. *(tests)*
- `test_round_record_producers.py:294` — the test name claims corrupt-run-state coverage it does
  not have. *(tests, P3)*
- Untested: lock lifetime, a run closed mid-round, churn-coherence reaching `emit`. *(tests, P3)*
- **Out of diff, pre-existing:** `--slug {slug}` interpolates into a model-constructed shell
  command line before Python parses argv; `round_record`'s filesystem containment does not cover
  that channel. *(security)*

## 🤝 Disagreements

`round_record.py`'s `_base_root` except tuple drew four verdicts across three rounds, **two of them
factually wrong**:

| Lens | Claim | Verdict |
|---|---|---|
| functionality (r2) | `RuntimeError` is missing from the tuple | correct |
| security (c1) | the tuple is exactly right, nothing broader is swallowed | **wrong** |
| design (c1) | `resolve_base_root` never raises — dead code | **wrong** |
| consistency (c2) | the claim is unverifiable in-tree and contradicted by a sibling comment | correct |

A three-line probe settled it: CPython 3.12 raises `RuntimeError("Symlink loop from …")` from
`Path.resolve()`. Consensus count was not the discriminator — a direct check was. That is the
second time in this review a confident majority reading was wrong (the first: the reviewer
rejection rate "measured" against `review-payloads/`, a store the gate never writes to).

Severity self-assessment diverged on one defect class three times: a false claim in shipped
documentation was filed **P1** (PRIVACY.md), **P2** (`finalize writes nothing`) and **P3**
(`_base_root`). Only P1 moves the grade.

## 🔬 Cross-model findings

Both voters skipped on quota (`codex`: usage limit; `antigravity`: `CANCELED`). The voter pool was
Claude lenses only. The ledger's `(skipped + failed) / total` cannot distinguish this from model
failure — noted, not fixed.

## Recommended next step

Fix P1 #1 and #2 (both one-line changes: move `_current_run` inside the lock; make the flock
non-blocking with a bounded deadline), then give the lock an oracle (#3) before anything else —
without it the next edit can silently delete the mechanism. #4 and #5 are documentation.

Then reconsider the shape. Three consecutive rounds produced severe findings **only** in the
machinery guarding the feature, never in the feature. CLAUDE.md 제1목표 is explicit that a device
contributing more to complexity than to quality should be reduced or removed.

---

## 🔻 Post-review: the device was reduced, not repaired

Recorded after this review closed. **Nothing below was reviewed** — that is the point of writing
it down here rather than upgrading the status.

Confirm-2's five P1s were all in the `flock` and run-identity machinery, which existed only
because base-root anchoring (the round-1 P0's repair) had made two worktrees share one file. The
pattern across three rounds was that severe findings landed exclusively in the device guarding
the feature, never in the feature. Per 제1목표 the device was removed rather than repaired again.

`round_record.py` (228 lines) is deleted. The producers `tee` their own payload; `review_telemetry
emit --measured <path>` reads `MEASURED_KEYS` out of it. The numbers still never pass through the
model — that property is unchanged and is the entire purpose of the change.

**What happened to this document's findings:**

| Finding | Now |
|---|---|
| P1 #1 run-id TOCTOU | no subject — no lock, no stamp |
| P1 #2 flock has no timeout | no subject |
| P1 #3 flock has no oracle | no subject |
| P1 #4 `_base_root`'s `RuntimeError` claim | no subject — the function is gone |
| P1 #5 BASELINE-DELTA arithmetic | rewritten for the reduced design |
| P2 `--force` discards a round · janitor · duplicated parser · lock containment · double base-root resolution · `_base_root` as the lone wrapper | all no subject |
| P2/P3 test findings about the store, `_open_run`, the fail-open mock | suite replaced (15 tests, new subject) |

**Still standing, unchanged by the reduction:**

- The rendered command runs `uv run --with $HOME/harness-maker`, i.e. the BASE checkout, so a
  stage inside `.worktrees/<slug>/` executes `main`'s Python rather than the branch under review.
  Measured here: this review's terminal `emit` wrote a row with no `disposition_counts` key.
  **A harness change cannot be verified through its own rendered stage.** Pre-existing, separate.
- `--slug {slug}` interpolates into a model-constructed shell command line before Python parses
  argv. Pre-existing, separate.

**The reduction's own cost, stated rather than buried:** the prompt surface grew **+182**
(1 914 → 2 096) while Python shrank 228 lines. Explaining `tee` and `--measured` across four
template arms is longer than describing a store was. The ratchet moved the wrong way.

**The one hazard file paths introduce** — a stale producer payload — is decidable and decided:
the producers stamp `slug`/`round` and `emit` refuses a mismatch; an unstamped payload is
accepted so nothing predating the stamp regresses.

**Verification of the reduced tree:** `ruff check` / `ruff format --check` / `mypy --strict`
(141 source files) / full `pytest` — all green, `rc=0`, zero failures. That is a test result,
not a review.
