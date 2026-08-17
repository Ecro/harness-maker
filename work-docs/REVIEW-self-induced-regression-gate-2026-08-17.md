# REVIEW — self-induced-regression-gate

```yaml
task_slug: self-induced-regression-gate
reviewed_at: 2026-08-17
review_base: hm/self-induced-regression-gate working tree
rounds_run: 3
grade_round_1: D
grade: B
grade_threshold: A
auto_fix: applied in three rounds — see "Repair record"
scope: round 1 REDUCED (4 of 7 lenses); round 3 full lens set, single reviewer; no cross-model, no confirmation pass in any round
drift_verdict:
  result: clean
  scope_violations: []
  scenario_misses: []
  task_slug: self-induced-regression-gate
  computed_at: 2026-08-17
findings: {P0: 1, P1: 7, P2: 11, P3: 4}
```

## Scope reduction — what did NOT run

This review was deliberately run at reduced scope: **4 lenses** (`design`,
`consistency`, `concurrency`, `tests`), **one pass**, **one round**. The
following are real losses, not omissions of empty work:

| Not run | What it would have covered |
|---|---|
| `security` lens | `review_run.py` writes a state file from a user-supplied slug; `validate_slug` was reviewed only incidentally by `consistency` |
| `robustness` lens | partial writes / restart / recovery on the new state file — `tests` F7 reached the same area from the oracle side, but nobody reviewed the behaviour |
| `functionality` lens | whether the change does what the PLAN's ADRs say on every path — the single largest gap, given that the P0 below is exactly a path that does not work |
| Pass 2 (metadata-restored) | anchoring correction |
| Cross-model second opinion | the one voter class that historically caught what Claude reviewers agreed on and were wrong about |
| Confirmation Pass | the clean sweep over the frozen artifact after fixes |

**The P0 was found anyway, by three of the four lenses independently.** That is
evidence for the reduction being survivable on this diff, not evidence that the
missing lenses had nothing to say.

## Consensus

Under ADR-007 a single lens's finding stands on its own, so lens identity is the
vote. Recorded per finding below. The P0 carries **three** independent lenses at
the same locus, which is the strongest surface match in this review.

Note on tiers: `design` filed the close-recipe defect at P1 while `consistency`
and `tests` filed it at P0. Step 4a does not bridge tiers, so it is recorded at
the higher severity with the disagreement stated rather than averaged.

---

## P0

### P0-1 — Four of five `review_run close` recipes cannot execute

*Lenses: `consistency` (P0), `tests` F1 (P0), `design` (P1) — 3/4*

`src/harness_maker/templates/stages/review.md.j2:728`, `:733`, `:738`, `:879`
render:

```
hm review_run close --outcome CHANGES_REQUESTED
```

`--slug` is `required=True` (`review_run.py:140`) and `--run-id` is checked at
`:166-168`; either absence returns **exit 2** before `run_state_path(...).unlink()`
at `:119` is reached. Only `:968` (Step C3) renders the full form.

Those four sites are the three Grade-Gate `CHANGES_REQUESTED` exits and the
Auto-Fix Loop's no-progress stop — **the ordinary non-approving endings of a
review**. Every one of them leaves `.claude/.hm-review-run-<slug>.json` on disk,
and the next `/hm:review <slug>` hits `_cmd_open`'s refusal at `:71-83` and can
only proceed with `--force`.

This is the exact consequence ADR-003 names as its accepted risk, moved from the
crash path to the **normal** path. The defect is on disk in the rendered
artefact (`tests/e2e/sandbox/.claude/commands/hm/review.md:569, :574, :579` vs
correct `:805`).

**Why the new gate did not catch it.** `tests/render/test_render_phase3_surface.py:326`
collects close sites with `lowered.startswith("review_run close", m)` — a bare
token match that never inspects arguments. The sibling module's own docstring
disowns exactly this (`tests/structural/test_multi_lens_a5.py:7`: "Every
assertion here pins a relation — count, order, or locus — never the presence of
a token").

**Fix.** Write all four as the `:968` form, and assert that every
`review_run close` occurrence carries `--slug` and `--run-id` on the same line.

---

## P1

### P1-1 — The `close` enumeration passes with zero closes on any Grade-Gate branch

*Lens: `tests` F2*

`test_render_phase3_surface.py:331-336` pairs each branch token to any close
within ±400 characters. `review.md.j2:904-906` is a **single pre-existing
sentence** carrying all three tokens in ~185 characters:

> "A review stopping for `max_review_rounds`, for the no-progress invariant, or
> with `auto_fix` disabled has not approved anything…"

Two closes — one anywhere in that paragraph, one at `:968` — satisfy all four
enumerated branches. The approve-arm exclusion (`:343-352`) spans `:705-725` and
contains neither. **The test passes with zero closes on any Grade-Gate branch.**

This is the same class as the Phase 3 blocker note at `:867-868`: the repair
moved the window rather than removing the property, which is precisely what
`stuck` warned about (PLAN:882-886). No mutant models it.

**Fix.** Pair on the close site's *own* branch identifier — the enclosing `IF …:`
clause — not a character neighbourhood.

### P1-2 — The minting instruction ADR-003 removed survives at a second site

*Lens: `consistency`* — verified directly.

`review.md.j2:235` still says "the `\"run_id\"` you minted", contradicting `:123`
("**Read it from `open`, never mint one**") and ADR-003 itself. The render guard
`test_review_no_longer_tells_the_model_to_mint_a_run_id` anchors solely on the
literal `fresh utc` and cannot see it. PLAN Phase 3 item 5 required confirming
"every other `<run-id>` site consumes that value"; that sweep was incomplete.

### P1-3 — A slug-blind state path passes the entire `test_review_run.py` suite

*Lens: `tests` F3*

Every test uses the single slug `"demo"`. Replacing `run_state_path` with
`base / f"{STATE_PREFIX}run.json"` — dropping the slug while keeping
`validate_slug` — leaves all 12 tests GREEN while deleting **ADR-003's entire
thesis** ("one open run per slug"). The discriminating case is missing: open
slug A, open slug B, assert independent ids and both records surviving.

### P1-4 — A.5 merge machinery is dead and the template contradicts the collapse

*Lens: `design`*

`execute.md.j2:298` still says "Round 1 dispatches all three", contradicting
ADR-010's one-dispatch contract, and the merge machinery downstream has no
producer.

### P1-5 — The `verification_cache check` can never hit

*Lens: `design`*

ADR-008 concedes this in its own consequence and ships it anyway. `consistency`
independently confirmed the mechanism is correctly described ("exit 1 is the
expected answer") — the finding is that a read that structurally cannot hit is
surface with no behaviour behind it.

### P1-6 — `M14`'s label claims a mutation it does not make

*Lens: `tests` F4*

`probe-phase3-falsifiability.py:230-235` labels itself
`M14-id-source-moved-after-consumers` but performs a **deletion**. It therefore
fails at the assertion's first clause (`source is not None`) and never exercises
the ordering clause (`source.start() < body.index("<run-id>")`) — the clause the
assertion's own comment calls the whole point. Fifth instance of the probe file's
own recorded failure mode.

### P1-7 — The correct-implementation mutant class has 1 of 16 members

*Lens: `tests` F5*

ADR-011 names the probe as the compensating control for suspending the A.5 RED
gate, and the harm it must compensate for is an assertion that drives the
implementer toward a wrong edit. That harm is covered by **one** mutant, and not
on either of the two assertions with a recorded history of being RED under a
faithful implementation (`test_review_enumerates_every_terminal_branch_that_must_close`,
whose inline comments document two such prior versions; and
`test_the_pre_repair_block_declares_all_three_items:151`, whose `{0,600}` window
was measured at 660–740 characters from the nearest fallback).

---

## P2

1. **`work-docs/PLAN-…md:8` says `adrs: 10`; there are 11.** ADR-011 was added
   without bumping the count. *(consistency)* — verified.
2. **`surface_allowance` was never tightened.** PLAN frontmatter still carries
   `chars: 6000` and **no `round_trips` key**, while Phase 3 item 10 and the
   delta doc `:74-75` both say Phase 3 writes the exact map and tightens the
   ceilings. `surface_baseline.json` was regenerated instead. *(consistency)* — verified.
3. **The delta doc contradicts itself.** §Reconciliation (`:67-82`) is future
   tense about work §Surface baseline movement (`:84-98`) reports as done.
   *(consistency)*
4. **`review.md.j2:972` cites a harm this diff removed** — "double-closes at C3"
   is not a consequence, because `close` was made idempotent in the same change
   (`review_run.py:107-111`). *(consistency)*
5. **`test_dep_map.py:506` "four-way selection"** heads a classifier that now has
   six classes; `:512` ("the other three shapes") is likewise off by one.
   *(consistency)*
6. **Three assertions have no mutant of any class** —
   `test_the_pre_repair_block_avoids_the_two_collided_words`, the exit-code-branch
   clause (M12/M13 fail earlier, at the command rename), and the `review`
   parameter of `test_the_stage_never_writes_the_verification_cache` (M6 mutates
   `EXE` only — verbatim the failure the probe's own comment at `:241-242`
   records). Delivered set fills 16 of 33 cells, clustered away from the negative
   invariants. *(tests F6)*
7. **`review_run` absent cases untested** — `--force` with no open run leaves
   `displaced` unset (`KeyError` for an unconditional reader); the
   `JSONDecodeError → None` recovery branch has no test. Repo's most-recurring
   failure class is `absent-case = feature black hole` (count:8). *(tests F7)*
8. **`--outcome` is validated and then unobservable** — `_cmd_close:119` unlinks
   the record, so no test can read it, and an implementation ignoring `--outcome`
   passes everything. ADR-003's text is "`close` **records** the terminal
   outcome". Spec/test divergence, not just a gap. *(tests F7)*
9. **`_COLLAPSED_MULTILINE`'s tripwire narrative is now false** —
   `test_render_dispatch_macro.py:217-221` says "exactly these two entries … a
   third means a Claude dispatch was lost"; the set holds four. The added entries
   themselves are exact full-line literals with correct attribution — the defect
   is the sentence telling a future reader when to be alarmed. *(tests F8)*
10. **A test docstring asserts an integration test that does not exist** —
    `test_review_run.py:246-247` claims "The packaging boundary has its own
    integration test"; `tests/integration/test_hm_console_script_resolves.py` has
    **zero** `review_run` matches. *(tests F9)* — verified.
11. **`TESTS_NOT_CONFIG_AFFECTING`'s detector polices literal mentions** and its
    remediation edits `SELECTOR_SOURCE`, which forces the full suite; the run-id
    could be derived from `(slug, review_base)` instead of a fourth state file;
    `status` / `state` / `displaced` have no reader. *(design)*

## P3

- `test_render_phase3_surface.py:149` — `"non-goal" in lowered` is body-wide;
  falsifiable only by the accident that the token is globally unique today.
- `probe:73-75` — `_move_closes_to_approve_side` asserts `anchor in text` for an
  anchor it never uses in the `replace`. Dead guard.
- `test_freeze_resolve_base_idempotence.py:135` — `assert err.strip()` passes on
  any stderr; assert the warning's identifying substring.
- `test_render_phase3_surface.py:343` — `lowered.find("if grade")` is a
  first-occurrence anchor on a generic phrase; future prose silently widens the
  excluded span.

---

## Verified negatives

Recorded because a silent omission reads as "not looked at". `consistency`
checked these against source and found them **accurate**:

- `execute.md.j2:450-456` / `review.md.j2:818-824` "exit 1 is the expected
  answer" — true (`verification_cache.py:450-454`).
- "This stage never writes the marker" — true in both stages; the only
  `mark-pass` sites are `verify.md.j2`, `wrapup.md.j2` and the
  `verify-before-completion` skill.
- "The Grade Gate's APPROVE-side exits are NOT terminal" — the Confirmation Pass
  heading is literally "(only when the gate would APPROVE)".
- `STATE_PREFIX`'s "registered in TWO places" — both real (`worktree.py:148`
  and `:617`, the latter being the filter `:679` actually reads).
- `freeze.py:314-329` matches ADR-004 including the stamp repair; the "no
  override flag" claim holds.

`concurrency` additionally resolved four questions clean and filed:

- **P1 (folded into P0-1's file):** `review_run.py:70` `open`'s read-then-write
  is TOCTOU. Load-bearing because `freeze_ref` is keyed on **slug + pass_id with
  no run-id**, so a lost race lets run B clobber the tree run A froze. Fix:
  `os.open(..., O_CREAT|O_EXCL|O_WRONLY, 0o600)` on the non-force path.
- **P2:** `_atomic_write` duplicates `io_utils.atomic_write` (`io_utils.py:56`) —
  though `consistency` notes four other modules roll the same local helper, so
  this follows the house pattern; the real difference is that `io_utils` fsyncs.
- **P2:** `load_run`'s "truncated write" comment describes a state `os.replace`
  makes unreachable — but see P2-7: the *branch* is still untested.

## Second sources of truth — adjudicated

- **Real duplication:** `test_roundtrip_budget.py:93,:172` and
  `surface_baseline.json:19,:55` hold the same two numbers, both hand-maintained,
  neither derived. The delta doc is a third restatement. Pre-existing, but this
  task had to update all three by hand.
- **Not duplication:** `CONFIG_SUITES` vs `TESTS_NOT_CONFIG_AFFECTING` — one
  feeds selection, the other only disposes of detector findings, and
  `test_test_dep_map_config_class.py:327-343` enforces the split.
- **Not duplication:** `review_run._atomic_write` vs `io_utils.atomic_write` —
  house pattern, four precedents.

---

## Repair record (2026-08-18)

Two repair rounds ran after the finding set closed. **Everything above is preserved as written at
round 1** — a review document that is edited to match the fix stops being evidence of what was
found. This section records what happened to each item.

### Round 1 — the P0 block (scoped: P0-1, P1-1, P1-2, P1-4, P1-3)

| Finding | Outcome |
|---|---|
| **P0-1** four unrunnable `close` recipes | **fixed** — all four render the full form |
| **P1-1** ±400 window satisfied by one sentence | **fixed** — each close attributed to the nearest branch identifier ABOVE it, so one close owns at most one branch |
| **P1-2** surviving mint instruction at `:235` | **fixed** |
| **P1-4** `execute.md.j2:298` "dispatches all three" | **fixed** |
| **P1-3** slug-blind path passes the suite | **fixed** — `test_two_slugs_open_independently` |

Both repairs were **measured, not asserted**. Reverting one close to the defect form goes RED on
the new well-formedness assertion; reproducing P1-1's exact construction (no-progress close
removed, a well-formed close planted in the three-token sentence) goes RED on the ownership rule
and **PASSES the old ±400 rule** — confirmed by running both.

### Round 2 — the remainder (user directed: "fix all of P1 and P2")

| Finding | Outcome |
|---|---|
| **P1-5** cache read cannot hit | **withdrawn, not patched** — the read is gone from both stages. `verify`/`wrapup`/`verify-before-completion` keep the cache; they hold both halves. ADR-008 revised; `execute` round-trips land at 17, not 18 |
| **P1-6** `M14` label vs mutation | **fixed** — split into `M14` (existence) / `M14b` (ordering) |
| **P1-7** correct-implementation class 1/16 | **fixed** — now 3 of 21 (`M2b`, `M15`, `M16b`); the close enumeration's placement sensitivity was removed at the source instead, by scoping every declaration assertion through `_declaration_block` |
| **concurrency P1** TOCTOU on `open` | **fixed** — `O_EXCL` makes the create the decision point |
| **P2-1** `adrs: 10` | fixed (11) |
| **P2-2** allowance never tightened | fixed — measured: `chars` 6000 → 4000, per-command to actuals. `round_trips` stays **absent**, which is correct: it is headroom ADDED to the baseline, and this task re-baselines |
| **P2-3** delta doc tense | fixed |
| **P2-4** "double-closes at C3" | fixed — `close` is idempotent, so it is not one of the harms |
| **P2-5** "four-way selection" header | fixed |
| **P2-6** three unfalsified assertions | fixed — `M6b`, `M12`/`M13`, `M16`/`M16b` |
| **P2-7** `displaced` / corrupt-file absent cases | fixed — `displaced` always present (`None`), plus a corrupt-state test |
| **P2-8** `--outcome` unobservable | fixed — asserted on the close payload, which is where it is observable |
| **P2-9** `_COLLAPSED_MULTILINE` tripwire count | fixed |
| **P2-10** false docstring about an integration test | fixed |
| **P2-11** detector remediation cost | fixed — the message now names the self-short-circuit and says to batch |
| **P3** ×4 | fixed — `if grade ≥` anchor, identifying-substring assert, probe dead anchor, `non-goal` scoped to the declaration block |

**Rejected:** deriving the run id from `(slug, review_base)` instead of a state file (P2-11's
second item). The file is what makes "one OPEN run" decidable; a derived id is stable but says
nothing about whether a run is still open.

### Three defects the repair itself introduced, each caught by a check added in the same round

1. A **`SyntaxError`** in the render test. The probe's 21 "RED (falsifiable)" lines were all
   collection failures — the probe reported maximum health while testing nothing. Reading the
   labels rather than the run would have shipped it.
2. `O_EXCL` **broke the corrupt-file recovery** `load_run`'s own comment promises. Caught by the
   absent-case test written minutes earlier for P2-7.
3. `round_trips` declared as an **absolute** count when it is headroom added to the baseline —
   the gate demanded 34.

This is the pattern the whole task is about, and it is the argument for the probe: the round that
fixed the gate also needed the gate.

### Round 3 — full single-reviewer review (2026-08-18)

Run at **full lens weighting**, explicitly prioritising `functionality`, `robustness` and
`security` — the three round 1 never ran. It confirmed round 1's fixes are real and correct, and
returned **three new P1s. All three were introduced by the repair rounds themselves.**

| Finding | What it was | Fix |
|---|---|---|
| **P1-A** | `os.open(O_CREAT\|O_EXCL)` creates the directory entry and writes a moment later. In that window a peer sees a **zero-byte** file, and the corrupt-file recovery added for P2-7 cannot tell "empty because a peer is mid-write" from "corrupt" — so it overwrites a live record and both runs proceed as owner. The race `O_EXCL` closed, reopened by its own recovery path | write to a temp file first, publish with `os.link`. The path never exists empty, which is what makes "unreadable ⇒ corrupt" sound |
| **P1-B** | Step C3 said "**Every** arm below is stage-terminal: close the run on each". The `confirm-1` arm is **not** terminal — it enters a repair round and dispatches confirm-2. Closing there releases the slug mid-pass while `<run-id>` is still the join key for the lens-results tree, the ledger rows and the freeze refs. It is the arm where releasing hurts most, because reaching it means the review is still dirty | reword to four-of-five + an explicit prohibition, plus a render assertion bounding the `confirm-1` arm. **The enumeration assertion could not see this**: requiring ≥1 close per branch is satisfied whether or not an extra close renders |
| **P1-C** | The probe counted **any** non-zero pytest exit as "RED (falsifiable)". pytest returns 1 for an assertion failure but 2/3/4 for a collection error, an import error or a missing node id | RED requires `rc == 1`; anything else is `HARNESS ERROR`. And every node now runs **unmutated first** and must pass, or the probe aborts |

**P1-C is the one that matters.** This exact failure had already happened during round 2 and is
recorded three sections above — 21 mutants all reporting RED because the test module would not
compile. Round 2 fixed the `SyntaxError` and left the blindness, so the next occurrence would
have reported identically. Fixing the symptom and calling the cause handled is the failure mode
this entire task exists to reduce, and it happened inside the task.

P2s also fixed: the freeze stamp is written at the **base repo root** (its only consumer reads it
there, and a stage runs with `cd <WT>`, so the stamp was landing where nothing looks — the repair
ADR-004 added did nothing on the stage's own path) and now uses `atomic_write`; `classify_path`'s
"four classes" docstring; `test_readiness.py`'s unstated exclusion from `CONFIG_SUITES`; ADR-003's
"`close` records the outcome" → "reports" (nothing was ever persisted); the probe now backs the
templates up outside the tree, since it mutates them in place and a SIGKILL would leave a
corrupted template for the next `git add -A`.

**Rejected:** deriving the run id from `(slug, review_base)` instead of a state file. The file is
what makes "one **open** run" decidable; a derived id is stable but says nothing about whether a
run is still open.

### What the size gate caught, after all of that

`review` then failed `test_command_size_budget` by 258 characters — P1-B's paragraph is the fix
itself, so it could not be trimmed, and the allowance was raised to the measured value and
re-attributed. The baseline-attribution gate then failed too, because the delta document still
carried the previous aggregate. Both are the ratchet working as designed: **the change that grew
the surface was made to say so, twice, in the same commit.**

Final measured movement: claude **+4309**, codex **+4396**; `review` +2301, `execute` +2008 with
round-trips **down** 19 → 17.

## Final state

`ruff` clean · `ruff format` clean · `mypy --strict` clean · falsifiability probe **21 mutants,
0 failing** (and the probe now aborts rather than certifying if its own harness is broken) ·
full suite green.

**Grade B.** No P0 or P1 remains open, and the coverage gap that held round 2 at C is closed —
round 3 ran the full lens set with `functionality` / `robustness` / `security` weighted first,
and the reviewer stated the change is landable once its three P1s were fixed, which they are.

Not A, for one reason worth stating plainly: **every repair round in this task introduced a new
defect, and each was caught only because a check added in that same round happened to cover it.**
Three rounds, three self-induced defects (`SyntaxError` in the gate, `O_EXCL` breaking the
corrupt-file recovery, `round_trips` declared as an absolute). The trend is downward in severity
and the final state is verified, but a change about self-induced churn that produced self-induced
churn at every step has not earned an A on its own subject.

**Not re-reviewed:** round 3's own fixes. The P1-A `os.link` publish and the P1-B template
rewording are covered by tests and the probe, not by a reviewer. That is the honest boundary of
what was checked.

## Grade at round 1: D

One P0 on the normal exit path of the stage this change exists to fix. Threshold
is A.

## Why nothing was fixed

This stage forbids repair before consensus, and repairing before the finding set
is closed is item 3 of the incident report that motivated this task. All four
lenses have now returned and the set above **is** the closed set for this scope.

Fixes are the next action, not part of this document.

## Recommended repair order

1. **P0-1** — the four close recipes. One-line edits, plus the well-formedness
   assertion that should have caught them.
2. **P1-1** — re-anchor the enumeration on branch identity. Without this, the
   fix to P0-1 is again unguarded.
3. **P1-2** — delete the surviving mint instruction at `:235`.
4. **P1-3** — the two-slug discriminating test.
5. **P1-4** — the `execute.md.j2:298` contradiction.
6. Everything else, in severity order.

**P1-6 and P1-7 are about the probe, which is ADR-011's compensating control for
the suspended A.5 gate.** They should not be deferred past the P1 block: a
compensating control with 1/16 coverage on the class it compensates for is the
reason P0-1 and P1-1 both shipped.
