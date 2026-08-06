---
type: baseline-delta
task_slug: workflow-loop-efficiency
phase: 7
created: 2026-08-05
owns: [surface_baseline.json, _ATOMIC_RATCHET, _CLAUDE_ROUND_TRIPS]
summary: "Every size/round-trip baseline this PLAN moved, attributed to the phase that moved it"
---

# Baseline delta — PLAN-workflow-loop-efficiency

**P7 is the only phase permitted to touch these baselines (ADR-010).** P2, P3 and P4a each
tripped one or more of them and each left the failure **red on purpose**, recording the trip
in the PLAN instead of resolving it. A phase that re-baselines the guard it tripped is
`ratchet-rebaselined-by-its-own-subject` — count:2 in this repo — and the guard afterwards
measures nothing.

`tests/structural/test_baseline_delta_attribution.py` fails if a changed key in
`surface_baseline.json` has no row below, so a silent rebaseline fails **mechanically**
rather than by anyone noticing.

---

## 1. Read this first — the aggregate went the wrong way

| | Phase 0 | After this PLAN | Δ |
|---|---|---|---|
| `aggregate_chars.claude` | 354 283 | 361 396 | **+7 113** |
| `aggregate_chars.codex` | 288 826 | 295 916 | **+7 090** |
| total mandated round-trips (claude) | 127 | 130 | **+3** |

**This is a workflow-cost-reduction PLAN that made the shipped surface larger.** That is not
a bookkeeping detail and should not be presented as one.

The breakdown:

- **~2 500 chars is P2** — the Phase D.5 newly-reachable-window step. It buys detection
  against `fix-introduced-defect-passes-all-gates` (count:4), a class that four *fully green*
  four-gate runs failed to catch. This one is a straight trade: prompt size for detection.
- **~3 000 chars and all 3 round-trips are P3** — the `stage-agents.jsonl` emits and the
  reviewer-payload persistence. **This portion only pays for itself if stage 2 actually
  reads those ledgers and deletes something.** If stage 2 never runs, P3 is pure cost and
  this PLAN's net effect on prompt size is an increase with no offsetting cut.
- **P1 is the only phase that gave anything back** (~480 chars, one `Task(` dispatch), and
  its saving is already netted into the numbers above.
- **~1 590 chars is the review round itself.** Two of its findings could only be fixed with
  prose in the review template: the payload call was writing N identical copies of the
  merged list under N reviewer labels (F2), and its `<run-id>` placeholder had no defined
  value, so every review would have overwritten the previous one's payload (round-2 P1-1).
  Both blocks exist to stop a silent corpus corruption, which is worth more than their size.

The honest summary: **stage 1 spent surface to buy the ability to decide.** Whether that was
worth it is decided in stage 2, by reading the ledgers — not here.

---

## 2. Attribution — one row per changed key

Every key that moved in `surface_baseline.json`, with the phase that moved it.

### `aggregate_chars`

| Key | From | To | Phase | Cause |
|---|---|---|---|---|
| `claude` | 354 283 | 361 396 | P1+P2+P3+review-round | sum of the per-command rows below |
| `codex` | 288 826 | 295 916 | P1+P2+P3+review-round | same, codex variant |
| `claude` | 361 396 | **361 562** | worktree-side-defaults | +166 — see the appended section |
| `codex` | 295 916 | **295 562** | worktree-side-defaults | −354 — see the appended section |

### `surface.claude`

| Key | chars | round_trips | Phase | Cause |
|---|---|---|---|---|
| `execute` | 29 820 → 33 774 | 14 → 15 | P2, P3 | P2 added Phase D.5; P3 added the Phase A.5 `stage_agent_ledger emit` |
| `plan` | 47 723 → 48 904 | 14 → 15 | P3 | Step 4 `stage_agent_ledger emit` (validator verdict per pass) |
| `review` | 50 379 → 51 808 | 8 → 9 | P1, P3, F2 | P1 removed the Pass 1.5 dispatch (−); P3 added `persist-payload` (+); the review round's F2 fix added the block that stops it being run once per reviewer (+) |

### `surface.codex`

| Key | chars | round_trips | Phase | Cause |
|---|---|---|---|---|
| `hm-execute` | 26 869 → 30 826 | 13 → 14 | P2, P3 | same two changes as `execute` |
| `hm-plan` | 43 244 → 44 428 | 12 → 13 | P3 | same as `plan` |
| `hm-review` | 46 047 → 46 408 | **9 → 9** | P1, P3 | see the note below — this one looks wrong and is not |

### New rendered file (wrapup)

| Path | Phase | Cause |
|---|---|---|
| `rubrics/repair_guard_force.yaml` | wrapup / AC-010 | The judgment rubric the ADR-003 gap was routed to. It is a **new snapshot path**, not a changed key — `aggregate_chars` is unaffected because `surface_baseline` measures commands and skills only, so the shipped-surface figures above still hold. |

### `render_sha`, `payload_digest`

| Key | Phase | Cause |
|---|---|---|
| `render_sha` | P7 | the commit the baseline was regenerated at; mechanical |
| `payload_digest` | P7 | digest of the payload above; mechanical, changes whenever any row does |

---

## 3. The one row that looks like a bug

`surface.codex.hm-review.round_trips` stayed at **9** while its claude twin went **8 → 9**.
An asymmetry there would mean the codex target silently lost the payload persistence — i.e.
ADR-006 part 2 shipping on two targets out of three, which is exactly the
"untested half becomes an assertion" shape that made this repo believe for months that
Claude Code read `.claude/hooks/hooks.json`.

It was checked directly rather than reasoned about. Measured on the rendered codex artifact:

```
.agents/skills/hm-review/SKILL.md   persist-payload: 1   Bash(: 9   Task(: 0
```

The count is unchanged because **two changes cancelled**: P1 removed one `Task(` (the Pass
1.5 `code-verifier` dispatch, which the codex variant also carried) and P3 added one `Bash(`
(`persist-payload`). Codex went 8 `Bash(` + 1 `Task(` → 9 `Bash(` + 0 `Task(`. Same total,
different composition.

The feature is present on all three targets;
`test_stage_agent_ledger_wiring.test_the_review_stage_persists_reviewer_payloads` asserts it
per artifact, including the codex one, so this cannot regress silently.

---

## 4. `_ATOMIC_RATCHET` and `_CLAUDE_ROUND_TRIPS`

These live in test source, not in `surface_baseline.json`, and were updated in the same P7
commit with the attribution written inline as comments:

| Table | Key | From | To | Phase |
|---|---|---|---|---|
| `_ATOMIC_RATCHET` | `execute` | 29 820 | 33 774 | P2, P3 |
| `_ATOMIC_RATCHET` | `plan` | 44 827 | 46 008 | P3 |
| `_ATOMIC_RATCHET` | `review` | 32 502 | 34 760 | P1, P3, review-round F2 |
| `_CLAUDE_ROUND_TRIPS` | `execute` | 14 | 15 | P3 |
| `_CLAUDE_ROUND_TRIPS` | `plan` | 14 | 15 | P3 |
| `_CLAUDE_ROUND_TRIPS` | `review` | 8 | 9 | P3 |

`_ATOMIC_RATCHET`'s ceiling is `measured × 1.02`, so raising a value re-arms the guard at the
new level rather than disabling it. The floor (`× 0.80`) moves up with it — which means a
future phase that *deletes* one of these steps will now trip the floor and have to say so.
That direction is deliberate: this PLAN's own P1 removal was small enough to pass the old
floor unnoticed.

---

## 5. Two acceptance criteria are NOT satisfied, on the record

`hm spec_machine mark-tested` was run for **seven** of nine ACs. Two were deliberately left
`pending_test: true`, because forcing them green is available and would be a lie.

| AC | State | Why |
|---|---|---|
| **AC-005** — ablation artifact records both arms | **not satisfied** | Its predicate is `set(ablation_artifact().keys()) >= {diffs, pass1_only, pass1_plus_pass2, delta, reproduced}` and those keys are **absent**: P5 landed as **pre-registration only**, by explicit user decision, with the 48-dispatch run deferred to stage 2. Writing the keys as empty or zero to turn the predicate green would manufacture the exact "measured zero vs never measured" conflation that §3.2(c) of the ablation artifact documents as a **real, shipped defect in this repo's own ledger**. |
| **AC-006** — wrapup delegate mismatch regression | **waived, per ADR-005** | Its predicate is differential across a fix that **did not land**: P4b is reproduction-gated and the gate did not open. ADR-005 says so in advance — *"if the cause does not reproduce: no code change, and AC-006 is waived on the record."* P4a landed the diagnosis instead, so the **next** occurrence arrives with a `reason` and the reproduction becomes attemptable for the first time. |

AC-006's `test_ids` was repointed from `tests/unit/test_wrapup_receipt_mismatch.py` — a file
that was never created, because P4b never ran — to the P4a diagnosis test that did land.
AC-008's was repointed from `tests/structural/test_shipped_surface_baseline.py`, likewise
never created, to `test_baseline_delta_attribution.py`. Both original paths were planned
names, and a `test_ids` entry pointing at a non-existent file is worse than an empty one: it
reads as coverage.

**Decisions confirmed at wrapup (user, 2026-08-05):**

| Item | Decision | Effect |
|---|---|---|
| ADR-003 operative-force gap | **Convert to a judgment AC** | New `AC-010` (`type: judgment`, rubric `repair_guard_force`), verdict supplied by an independent `judgment-reviewer`, subject-hashed so editing the step invalidates the pass. The mechanical gap is not "closed" — it is routed to the only oracle that can answer a semantic question. |
| AC-005 (ablation not run) | **Record as unsatisfied, proceed** | Stays `pending_test: true`. The 48-dispatch run is stage-2 work. |
| AC-006 (delegate fix) | **Keep the ADR-005 waiver** | P4b did not run; P4a's diagnosis makes the next occurrence the first reproducible one. |

**Nothing here is a surprise.** Both outcomes were decided in advance — AC-005 by the user's
"end P5 at pre-registration" choice, AC-006 by ADR-005's reproduction gate, which exists
precisely because the first PLAN draft proposed a preemptive fix and two independent
cross-model reviewers flagged it as `fix-introduced-defect-passes-all-gates` (count:4).
Recording them as unmet is the design working, not the design failing.


---

## Appendix — `worktree-side-defaults` (landed 2026-08-06, after P7)

This doc's `owns:` covers `surface_baseline.json`, so a later task that moves a key has to
land its rows here rather than start a second attribution file. Two changes now stack on
the same baseline; the rows above are P7's, the rows below are this task's, and the
aggregate row shows both hops.

**Net: claude +166, codex −354.** The only real addition is the `/hm:configure` worktree
dimension. Everything else is the `feature_branch_workflow` → `enabled` gate rename, which
is shorter, plus two lines that stopped rendering.

| Key | chars | Cause |
|---|---|---|
| `configure` | 9 330 → 9 910 (**+580**) | The new "Worktree isolation" dimension + its dispatch note. Compacted twice before landing (raw +534 → +210 on the earlier freeze); the residue is the ONLY discoverable way to change the axis, and "there is no supported way to change this" is the defect the task exists to fix. |
| `execute` | 33 774 → 33 691 (−83) | Gate rename, minus the flag-off Step 0 block and one quality-bar line that no longer render when isolation is off. |
| `plan` / `research` / `review` / `spec` | each −68 | Gate rename only (`config.worktree.get('feature_branch_workflow')` → `…get('enabled')`). |
| `loop-p5-batch` | 4 834 → 4 794 (**net 0 vs P7**) | Moves twice. `f0f8bf45` added a +40 parenthetical ("a no-op when `worktree.enabled` is off"); this change replaces it with a real `{% if wt_on %}` branch, so the ON render returns to its P7 size. The row exists because the key moved against the COMMITTED baseline (−40), even though it is unchanged against P7 — the attribution gate compares to what is on disk, which is the right thing for it to do. |
| `hm-loop-p5-batch` | 5 291 → 5 251 (**net 0 vs P7**) | Codex variant, same two hops. |
| `loop` | 52 269 → 52 242 (−27) | Section 5 branches ON/OFF, command sites take `{{ cdwt }}`/`{{ WTR }}`, prose takes `{{ WTP }}`. The OFF branch replaces the create/verify/finalize machinery with a shorter block, so the ON-side text it removes slightly outweighs what the OFF text adds. |
| `verify` / `wrapup` | each −16 | Gate rename. |
| `hm-execute` | 30 826 → 30 805 (−21) | Codex variant of `execute`. |
| `hm-plan` | 44 428 → 44 360 (−68) | Codex variant of `plan`. |
| `hm-review` | 47 996 → 47 928 (−68) | Codex variant of `review`. |
| `hm-research` | 23 664 → 23 596 (−68) | Codex variant of `research`. |
| `hm-spec` | 27 808 → 27 740 (−68) | Codex variant of `spec`. |
| `hm-loop` | 51 179 → 51 150 (−29) | Codex variant of `loop`. |
| `hm-verify` | 18 740 → 18 724 (−16) | Codex variant of `verify`. |
| `hm-wrapup` | 43 914 → 43 898 (−16) | Codex variant of `wrapup`. |

Codex nets **−354** because it has no `configure` command — it gets the rename shrink
without the one real addition.

**Why the freeze had to happen after the land, not on the task branch.**
`_surface_baseline.py` refuses to freeze at a SHA that is not an ancestor of `main` — a
task branch is squash-landed and deleted, so that SHA would not survive. The rebase onto
P7 therefore left a baseline that accounted for this task but not P7's, and the honest
sequence is land → re-freeze from base → amend. Recorded because the refusal reads like a
tool failure the first time you hit it, and it is not.
