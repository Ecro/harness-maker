---
type: review
task_slug: autopilot-advance-noop
status: CHANGES_REQUESTED
created: 2026-07-31
reviewers_invoked: [code-reviewer, security-reviewer, codex, antigravity]
consensus_method: cross-check
consensus_k: 2
voter_pool_n: 4
rounds_used: 7
max_review_rounds: 3
rounds_note: "rounds 4-7 were user-requested extra passes past the configured budget"
final_grade: A
human_review_needed: true
drift_verdict:
  result: clean
  scope_violations: []
  scenario_misses: []
  task_slug: autopilot-advance-noop
  computed_at: 2026-07-31T00:00:00Z
---

# REVIEW — autopilot-advance-noop

## 🎯 Summary

Seven rounds, four voices (2 Claude reviewers + codex + antigravity as full k-of-N voters,
K=2). **Round 1 graded D** — two consensus P0s, one of which was a process failure of mine.
Every consensus finding was fixed; each fix round surfaced a new defect *in the fix*, which
is the honest signal here: this change touches a concurrency-sensitive on-disk marker and
the first two attempts at the ownership rule were both wrong in opposite directions.

**Final grade A** (0 consensus-passed P0/P1 remaining), but `human_review_needed: true` —
the last round's fixes landed after the final re-review, so the newest code has been
verified by the test suite and by my own reading, not by an independent reviewer round.
The budget (`max_review_rounds: 3`) was exhausted at round 3; rounds 4-7 were
user-requested. Rounds 4-7 ran without the cross-model voters (frozen at round 1 per the
vote-freeze contract), so they are single-voice reads, not k-of-N consensus.

**Landed with three findings open** (F31 P2, F33 P3, F34 P3 — see Round 7). That was a
deliberate call, not an oversight: F31's correct home is the ADR-007/010 reduction the
user is handling in a separate session, and holding ~1000 uncommitted lines across
sessions is the larger risk.

## 🔍 Drift Findings

`result: clean`. No file changed outside PLAN scope. Two informational notes:

- `readiness.py` appears in Phase 2's scope but was **not** changed. Verified unnecessary:
  it contains zero references to the ledger event names (`rg` returns nothing), so the
  scope entry was a speculative over-declaration, not an incomplete phase.
- `tests/structural/test_{command_size_budget,instruction_preservation}.py` and
  `tests/unit/test_render_wrapup_delegation.py` were modified without being named in a
  phase scope list. All three are ratchet/pin files that Phase 4 necessarily moves; each
  carries a written justification at the changed constant.

## ✅ Consensus Findings (all fixed)

### Round 1 — grade D (P0 ×2, P1 ×1)

| # | Sev | Voices | Finding | Fix |
|---|-----|--------|---------|-----|
| 1 | **P0** | 2/2 Claude | `test_autopilot_advance_render_gate.py` asserted three literals that no longer matched the templates — 6 tests red on every run. The change shipped its own gate permanently failing. | Corrected the three literals. |
| 2 | **P0** | 2/2 Claude | `autopilot_autoarm` called `write()` with no session id. `HM_SESSION_ID` is published by the sibling `sessionid_envfile` hook into `$CLAUDE_ENV_FILE` — later Bash only — so the marker was stamped `claude_session_id: null` and the arming session then read it as **foreign**. With ADR-010's picker branch refusing to arm over a foreign marker, `autopilot_persistent: true` harnesses were wedged for the full 18h TTL with no in-band recovery: strictly worse than the bug under repair. | `write()` gained `claude_session_id`; autoarm reads `session_id` off its own stdin payload. |
| 3 | P1 | 2/2 Claude | `cli.py`'s Typer `autopilot on` shim did not catch the new `MarkerOwnedByAnotherSessionError` → raw traceback, no `--force` escape on the documented CLI surface. | Added the except → exit 3, plus `--force`. |
| 4 | P2 | code-reviewer + codex | `count_entries` dropped **all** legacy `advanced` rows once any new-vocabulary row existed, handing a partially-consumed session a fresh step budget. | See "reversed decision" below. |
| 5 | P2 | antigravity + security | `gc_stale_marker` never collected a marker whose `created_at` was garbage-but-schema-valid → permanent wedge. | `deletable` now includes `"unparseable"`. |
| 6 | P2 | antigravity + code-reviewer | GC docstring claimed the re-read closed the TOCTOU window. | Reworded to "narrows, does not close", with the reason. |

### Round 2 — the fix for #2 was itself a P0

| # | Sev | Voices | Finding | Fix |
|---|-----|--------|---------|-----|
| 7 | **P0** | 2/2 Claude | Round 1's fix passed `force=True`, disabling the ADR-010 guard for **genuinely foreign** markers too: any second session's SessionStart stole a live peer's marker and killed its chain at the next boundary with a bare `kill_switch`. **Root cause both reviewers identified: `_is_own` never consulted the `claude_session_id` that had just been threaded in**, so `force` was not an optimisation — it was the only way `write` could succeed at all. | `_is_own(session_id=…)`; `write` computes `effective_session_id` once and uses it for both the guard and the stamp; autoarm dropped `force` and now catches the ownership error as an explicit no-arm. |
| 8 | P1 | 2/2 Claude | `_resolve_task_slug` discarded `set_task_slug`'s bool and echoed a **rejected** slug into the boundary JSON — i.e. the allowlist covered the marker sink but not the sink the prompt actually reads. | Gates on the bool. |
| 9 | P1 | 2/2 Claude | Every round-1 fix shipped with zero regression tests: deleting the `claude_session_id=` kwarg left the suite fully green. | New `tests/unit/test_autopilot_autoarm_identity.py` (18 tests). |

### Round 3 — the fix for #7 relocated the wedge

| # | Sev | Voices | Finding | Fix |
|---|-----|--------|---------|-----|
| 10 | **P1** | 2/2 Claude | On WSL2 the SessionStart hook receives the id on stdin while `$CLAUDE_ENV_FILE` publication fails, so the marker is id-stamped and the session's own Bash is id-less → `status` reported the user's **own** marker as `foreign`, and the picker (per ADR-010) refused to arm. Round 1's healthy-case wedge had been traded for a wedge on a documented platform. | `status` now reports `degraded-idless`; the picker gained a branch that states the ambiguity honestly and offers `--force`. |
| 11 | P1 | security-reviewer | The ownership guard fired only on `_freshness == "fresh"`. A `future`-dated marker — one `gc_stale_marker` deliberately refuses to delete *because it may be a peer's live marker* — was still overwritable by `write`. The same peer-disarm through the other door. | Guard widened to `!= "stale"`. |
| 12 | P2 | code-reviewer | The `MarkerOwnedByAnotherSessionError` branch logged at `INFO`. Nothing configures logging, so the root logger sits at WARNING and `logging.lastResort` also fires at WARNING+ — the record was discarded, making the "logged distinctly" branch *less* visible than the generic fail-safe. | `logger.warning`. |
| 13 | P2 | code-reviewer | The rejected-slug fall-through reported `task_slug_source: "persisted"`, byte-identical to the benign "no flag passed" case, so the prompt could not tell a refused slug from a normal inherit while a **different task's** slug advanced. | New sources `rejected` / `rejected-fallback`, and the template branches on "anything other than `flag`". |
| 14 | P2 | security-reviewer | `_TASK_SLUG_RE.match` + `$` accepts a trailing newline — for a value interpolated into a shell command line. | `fullmatch`, with the divergence from `worktree`'s looser `match` stated rather than glossed. |

### Round 4 (user-requested, past the budget) — the fix for #10 recreated the ORIGINAL bug

| # | Sev | Voices | Finding | Fix |
|---|-----|--------|---------|-----|
| 15 | **P0/P1** | code-reviewer P0 + security P1 | **Ownership conflates "a different session id" with "a LIVE session".** Nothing clears the marker at session end — `clear` fires only on explicit `off` and the three terminal boundary paths, and there is no SessionEnd hook. So a session that armed and closed mid-pipeline (the ordinary case) left a `fresh` id-stamped marker that no one could take for 18h: autoarm raised, and the picker was under my own instruction not to arm on `foreign`. **ADR-007 + ADR-010 together turned "silently inherited" into "silently never arms" — the exact defect this PLAN exists to remove.** | Marker `last_seen` heartbeat, refreshed by the owner at every boundary/gate-blocked; `status` reports `idle_minutes`. |
| 16 | P1 | security + codex + antigravity (3) | The `degraded-idless` prose ("probably yours … offer `--force`") is indistinguishable from a degraded session meeting a HEALTHY peer's marker, so it instructs the agent to disarm a peer on a plausible-sounding prompt. | The picker no longer guesses: it states `idle_minutes` as a fact and asks the user *is another Claude session open in this project?* — `--force` only on an explicit "no". |
| 17 | P1 | code-reviewer + codex (antigravity P2) | A `rejected*` slug still emitted `proceed: true` + `advance_authorized` while the template told the model not to run — self-contradictory, and a later retry's entry would be greedily paired against the stranded authorization. | `halt_kind: "bad_slug"`, no authorization recorded. |
| 18 | P2 | code-reviewer + security | A `future`-dated **foreign** marker was neither GC-able (GC preserves `future`) nor overwritable (guard protects non-`stale`) → unbounded wedge. | Skew beyond one TTL is no longer credible jitter; it classifies as `stale`. |
| 19 | P2 | codex | `find_unconfirmed_authorization` split the events apart and reconstructed order from timestamps, making the pairing hostage to a clock rollback and skipping the ordering check entirely on a missing `ts`. | Single pass in **append order** — the ledger is O_APPEND, so file order IS write order. Timestamps now serve only the window filter and `elapsed_s`. |

**The design decision behind #15/#16 (user's call).** Liveness is not provable locally: nothing
cheaply distinguishes "the peer is working" from "the peer is between stages". So the fix does
not try to prove it. The heartbeat produces a *fact* (last active N minutes ago) and the
picker puts the question to the party who actually knows the answer. That closes the 18h
wedge and removes the peer-disarm push in one move, without inventing a liveness window whose
wrong guess would kill a live chain.

### Round 5 (user-requested) — the R4 slug halt fail-closed the whole feature

| # | Sev | Voices | Finding | Fix |
|---|-----|--------|---------|-----|
| 20 | **P1** | code-reviewer + security | **The shipped `--slug '<slug>'` placeholder always fails the allowlist, and R4 promoted that failure to a terminal halt.** Before R4 it fell through to the persisted slug and the chain continued; after R4 it returns `halt_kind: "bad_slug"` — and `bad_slug` was absent from the prose's `proceed: false` halt list, so a model reading an unlisted halt under a bullet that says "**STOP** (print the banner)" stops. A model that copies the rendered line verbatim therefore halts at **every** boundary: the reported symptom, manufactured by the fix for it. | The flag is no longer pre-rendered — the prose says to *append* it when a real slug exists. `bad_slug` joins the halt list with its recovery ("re-run with a corrected slug, or no flag; nothing was authorized"), and the render gate now asserts the placeholder is absent. |
| 21 | **P1** | security + codex | `touch()` is a read-modify-write with no re-check, unlike `set_task_slug`, whose comment calls that same window "the only remaining marker-clobber window". A deliberate `--force` takeover landing mid-touch is silently reverted, and the taker halts at `kill_switch`. R4 reopened it on a hotter path (every boundary). | `touch` re-reads and compares `created_at` immediately before the write. |
| 22 | P1 / P2 | security P1 + code-reviewer P2 | `idle_minutes` clamped a future stamp to `0.0` — reporting "active right now" for a clock-skewed marker that is also GC-protected and overwrite-protected. The picker puts that number to the user as the fact that decides a takeover. | Returns `None` (unknown); the picker prose says `null` proves nothing. |
| 23 | P2 | code-reviewer | Duplicate `advance_authorized` rows for one stage (a re-run boundary) banked a second confirmable slot, so a later entry could be consumed against work that never happened. | Consecutive authorizations with no intervening entry collapse to one. |
| 24 | P2 | code-reviewer | A cap-halt comment still cited the Stop-hook backstop that this PLAN's predecessor deleted. | Removed. |

**Two process notes from this round, both mine.** (a) Compressing prose to fit the size
ratchet, I shortened "not evidence either way" to "evidence either way" — inverting the
instruction. Caught on re-read, but it is direct evidence that prose compaction can flip
meaning, and no gate would have caught it. (b) The stale-allowlist arm in
`test_instruction_preservation` fired correctly: removing the placeholder restored the
boundary line to its original text, so the Phase-4 "this line was removed" entry became a
lie. Dropped.

**Unresolved, single voice, deliberately not fixed.** antigravity: for an *unattended* run
(`autopilot_persistent: true`, previous session crashed) the picker's question has nobody to
answer, so the wedge is relabelled rather than closed for that population. This is real. The
only fix is a liveness threshold — the guess R4 deliberately refused to invent, because a
wrong one kills a live chain. Recorded as an accepted limitation rather than papered over.

### Round 6 (user-requested) — and a converged cross-model claim that was WRONG

| # | Sev | Voices | Finding | Fix |
|---|-----|--------|---------|-----|
| 25 | **P1** | security + antigravity | `created_at` is not a change detector for the writes `touch`/`set_task_slug` actually make — **neither mutates `created_at`**, so every same-owner collision passed the guard and the later writer reverted the other's field. Co-ownership is a real population: `_is_own` falls back to the project-scoped `session_uuid` whenever neither side has an id (Cursor, Codex, WSL2 env-file failure). | Shared `_write_if_unchanged` using **byte identity** — the primitive `gc_stale_marker` already used ten lines away. |
| 26 | P2 | code-reviewer | The round-5 render gates passed on **prose alone**: `assert "--slug" in partial` is satisfied by any mention, so they stayed green both when the flag was pre-rendered with a placeholder AND when the append instruction was inert. | The gate now isolates the single `autopilot_caps boundary` line and asserts the flag is absent from it, plus no `--slug <…>` placeholder anywhere. |
| 27 | P1 | antigravity + code-reviewer | `bad_slug`'s "do NOT print the banner" sat four lines under a bullet opening "**STOP** (print the banner)" — the same earlier-and-stronger shape ADR-006 exists to prevent, and only one side named the other. | The exception is named at the head of the bullet. |
| 28 | P1 | security | The model composes the `--slug` value into a shell line; the allowlist is downstream (argparse → pydantic), so the shell sees it first. | Instruction now requires single quotes (`--slug 'my-task'`), matching sibling templates. |
| 29 | P2 | code-reviewer | The slug was persisted **before** the unknown-stage check, so `--current bogus --slug s` stamped `task_slug_stage: "bogus"` and then reported "marker preserved". | Slug resolution moved below the guard. |
| 30 | P2 | code-reviewer | `HaltKind` Literal lacked `"bad_slug"`; `out` is `dict[str, object]` so mypy could not see the JSON contract diverge from the declared vocabulary. | Added. |

**A converged cross-model claim that was refuted.** codex (P1) and antigravity (P0)
independently concluded that the round-5 fix was inert: "a `!`-prefixed line in a rendered
slash command is executed as written, so the model cannot append `--slug`; the flag is
never passed and ADR-003 is dead." Two models agreeing is persuasive, and it is wrong for
this harness. Direct evidence from the session that produced this change: the `/hm:research`
prompt carried
`!uv run … hm worktree task-preflight <slug> "$(pwd)" --stage hm:research`, it was **not**
auto-executed, and the model substituted `<slug>` and ran it via Bash — as it did for every
`!` line in every stage of this task. Had the harness executed them verbatim, `<slug>` would
have gone through literally and failed immediately. The `!` lines in these stage bodies are
model-composed instructions. security-reviewer's framing (the append works, and the composed
value reaches the shell ahead of the allowlist) is the correct one, and #28 is its fix.

## 📝 Manual-Only Findings (unverified, no second voice)

None outstanding — every manual-only finding raised across the three rounds was fixed
rather than accepted as risk (#11, #12, #13, #14 above each had a single voice).

## 🤝 Disagreements

- **`count_entries` (#4).** codex called it P2, antigravity P1, code-reviewer P2 —
  same defect, different tiers, so the P1 did not bridge (Step 4c). Fixed regardless.
- **GC TOCTOU.** codex P1 vs antigravity/code-reviewer P2. The P1 framing (a pathname-based
  unlink can never be made safe) is correct in principle; the P2 framing (narrow the window,
  document the residue) is what shipped, because closing it needs an inode-level swap
  primitive `Path.unlink` does not offer. Recorded in the docstring, not papered over.

## 🔄 A reversed decision (ADR-004 sub-rule)

Three voices independently attacked `count_entries`'s original rule, and they were right in
a way that inverted my own test:

- **Drafted:** a legacy `advanced` row counts only when the window has **no** new-vocabulary
  row — chosen to stop a pre-upgrade phantom double-counting one advance.
- **Consequence they found:** a partially-consumed session that upgrades mid-window gets its
  step budget **reset**, because two completed legacy steps plus one stalled new
  authorization counted as zero. Under-counting lets the chain run *longer* than
  configured.
- **Reversed to:** `entered + legacy rows before the upgrade point`. `count_events`'s own
  comment already states the governing bias — "the cap must be block-biased toward firing,
  not toward running longer" — and the drafted rule violated it. The accepted cost (a
  phantom over-counts by one, so the cap fires one step early) is pinned by
  `test_a_pre_upgrade_phantom_over_counts_rather_than_under_counts`.

## ⚠️ Remaining — why `human_review_needed: true`

1. **Round 3's fixes are unreviewed by an independent voice.** `max_review_rounds: 3` is
   exhausted. Findings #10–#14 were fixed after the last reviewer round, verified by the
   suite and by reading, not by a fourth review. Given that *each* of the previous two fix
   rounds introduced a new P0/P1 in the fix itself, that is a real risk, not a formality.
2. **Two suite failures remain**, both the documented Phase-5 blocker:
   `test_aggregate_shipped_surface_does_not_grow` and
   `test_the_standalone_generator_agrees_with_the_baseline_in_shape_and_direction`.
   The surface baseline can only be frozen at a commit that is an ancestor of `main`
   (`_surface_baseline.assert_sha_is_durable`), and this work sits on an unlanded task
   branch. Resolution is a post-land `uv run python -m tests.structural._surface_baseline`,
   per the existing precedent commit `dfb3caeb`.
3. **The headline behaviour is still unverified end-to-end.** Interview #11 chose to keep
   the manual observation as a Success Criterion rather than a phase gate, so no automated
   check confirms that a real session now advances. R2 in the PLAN carries this.

## 🧪 Verification state

- Full suite: 21 failures at round 1 → **2** (both the Phase-5 baseline blocker above).
- `ruff check` clean; `ruff format` clean; `mypy --strict` clean on all touched modules.
- Snapshots regenerated after every source change that moved a template.

> **Correction (same session).** The "2" above was first written from the round-4 suite run
> — i.e. *before* round 3's own fixes landed. Those fixes added prose to the two shared
> partials and pushed `plan` (+7 chars) and `review` (+62) back over their ceilings and the
> wrapup equality pin from 626/659 to 628/661, so the real count at that moment was **6**.
> Resolved by compressing the round-3 prose (plan and review returned under their
> *unchanged* ceilings — no third ratchet raise) and moving the wrapup pin with a written
> reason. The final figure is confirmed by the last full run recorded below, not by this
> paragraph.
>
> This is the second time in this task that a size ratchet caught a change I had already
> called finished, and the first time I reported a suite figure from a stale run. Both are
> the same mistake: quoting a number without re-deriving it after the last edit.

**Confirmed final run** (after the last edit in this session, snapshots regenerated):

```
2 failed
  tests/structural/test_command_size_budget.py::test_aggregate_shipped_surface_does_not_grow
  tests/structural/test_surface_baseline.py::test_the_standalone_generator_agrees_with_the_baseline_in_shape_and_direction
```

`ruff check` — all checks passed. `ruff format --check` — 527 files already formatted.
`mypy --strict` — clean across `autopilot.py`, `autopilot_caps.py`, `autopilot_ledger.py`,
`hooks/autopilot_autoarm.py`, `cli.py`.

**After round 4** (full run, then targeted re-verification of the delta): 4 failures →
the 2 baseline blockers, plus

- `test_picker_has_the_foreign_no_arm_branch` — the round-4 picker rewrite merged the
  `foreign` and `degraded-idless` branches, so the gate's old literals were gone. The gate
  was rewritten to pin the *new*, stronger contract (name both reasons, state
  `idle_minutes`, refuse to guess, ask the user) and is green.
- `test_plugin_live.py::test_make_fresh_install_creates_harness_yaml` — failed once in the
  full run; passes standalone and with the whole `tests/e2e/` directory. **Not reproduced,
  cause unknown.** Recorded as an open observation rather than declared a flake.

**After round 5** (full run, snapshots regenerated): **2 failures — the two Phase-5
baseline blockers only.** `ruff check` clean, `mypy --strict` clean. The e2e above did not
recur.

**After round 6** (full run, snapshots regenerated — the final state of this session):

```
2 failed
  tests/structural/test_command_size_budget.py::test_aggregate_shipped_surface_does_not_grow
  tests/structural/test_surface_baseline.py::test_the_standalone_generator_agrees_with_the_baseline_in_shape_and_direction
```

Both are the documented Phase-5 blocker: the surface baseline can only be frozen at a commit
that is an ancestor of `main` (`_surface_baseline.assert_sha_is_durable`), and this work sits
on an unlanded task branch. Resolution is a post-land
`uv run python -m tests.structural._surface_baseline`, per precedent commit `dfb3caeb`.
`ruff check` clean, `ruff format --check` clean, `mypy --strict` clean. Per-command size
budgets pass without a further ratchet raise (the round-6 prose was compressed to fit).

## 📊 Review Iteration Summary

| Iteration | Grade | Fixes applied | Remaining | New defects found IN that round's fix |
|-----------|-------|---------------|-----------|---------------------------------------|
| 1 (init)  | **D** | —             | 6         | —                                      |
| 2         | **D** | 8             | 3         | 1 × P0 (`force=True`)                  |
| 3         | **A** | 5             | 0 consensus | 2 × P1 (degraded-idless, `future` guard) |
| 4 (extra) | **A** | 5             | 0 consensus | 1 × P0/P1 (**the original bug, recreated**) + 4 |
| 5 (extra) | **A** | 5             | 0 consensus | 1 × P1 (**the original bug, recreated again**) + 4 |
| 6 (extra) | **A** | 6             | 0 consensus | 3 × P1/P2 in rounds 4–5's fixes + 3 |

Final grade: **A**
Iterations used: 6 (3 budgeted + 3 user-requested)
Status: **CHANGES_REQUESTED**
human_review_needed: **true**

**The number that matters is not the grade — it is the last column.** Five consecutive
rounds each found a defect inside the previous round's fix. Three were on the ownership
rule; rounds 4 and 5 each reconstructed the ORIGINAL reported symptom ("announces the next
stage, never advances") out of the fix for it — once through the ownership guard, once
through the slug halt. Round 5's fixes are themselves unreviewed.

An A here means "no consensus P0/P1 that anyone has looked for yet", not "this is settled".

### Why every round finds more — a diagnosis, not an excuse

Roughly **half of all 30 findings are defects in a PREVIOUS round's fix**, not in the
original code: `#2 → #7 → #15 → #21 → #25` is one unbroken chain through the ownership
rule, and `#17 → #20 → #26/#27` is another through the slug path. The defect-per-fix rate is
about 1:1. Detection is not the problem; fix quality is. Four named causes, each with
evidence above:

1. **No state table.** Ownership spans `{own, foreign, both-idless, one-idless} × {fresh,
   stale, future, unparseable} × {live, abandoned} × {arm, read, GC, field-write}`. Each
   round patched the reported cell without re-deriving the table, so "foreign+fresh must not
   be overwritten" broke "abandoned+fresh must be takeable". This one subsystem produced 9
   of the 30.
2. **Two layers with no consistency check.** The Python contract and the prompt prose drift,
   and the render gates were whole-file substring matches — green for a working instruction
   and an inert one alike (#26).
3. **Fixing at the reported layer, not the causal one.** `force=True` (#7) is the clearest:
   the cause was `_is_own` ignoring its new parameter; `force` was symptom relief that
   opened a hole.
4. **Prose compaction after the logic settled.** A size-ratchet compression inverted a
   negation ("not evidence either way" → "evidence either way") and buried #27's exception.
   Compaction is an unreviewed edit pass over carefully-worded text.

**What would actually reduce it**, in expected-effect order: batch a round's findings and
re-derive the model once instead of patching each immediately; write the ownership truth
table into the PLAN and make it the parametrized test matrix; make render gates assert the
*executed* surface (the `!` line, the JSON keys) rather than prose that mentions it;
compress before finalising wording, not after.

**And the strategic read:** six rounds is a signal that the design is wrong, not that the
reviews are good. The minimal change (`status` + GC + the ledger split) never generated a
follow-on defect. ADR-007 (session-scoping) and ADR-010 (the ownership guard) generated
almost all of them. Reverting those two and re-doing them as their own PLAN — with the truth
table up front — is a live option and was raised with the user, who is handling it
separately.

---

## Round 7 (2026-08-01)

Four findings. All four were green under the 259 autopilot-scoped tests, which pass.

### F31 (P2) — the stage-end block reinstates marker guessing as a precondition
`templates/agents/_partials/stage_end_summary.md.j2:32-36` makes "no `.hm-autopilot`
marker is active" a NO-OP precondition and then says "do not run any command below". No
command for that predicate is offered at that point, so the only remaining means is
checking whether the file exists — the ADR-002 failure the picker removed, relocated. The
failure direction is the reported symptom (armed marker, model decides otherwise, STOP).
`hm autopilot status` is in the same rendered document (the picker is included by
`atomic_command.md.j2`), which is why this is P2 and not P1 — but nothing in the block
points at it.

The precondition is pure downside: running `boundary` unconditionally is safe and
authoritative. `_cmd_boundary` returns `kill_switch` and returns *before* `touch`,
`_confirm_entry` and any ledger append when `active_marker` is None — the P2-5 invariant
it documents. Both paths end at the STOP banner; one reads a fact, the other guesses.

**Not fixed.** A prose edit, and rounds 3-6 sourced almost every follow-on defect from the
prompt layer. Its correct home is the ADR-007/010 reduction the user is handling
separately, where the block gets rewritten whole rather than having a paragraph excised.

### F32 (P2) — the two `autopilot` CLI surfaces diverged on `status` — FIXED
Confirmed by execution, both halves:

    hm autopilot status --root .            → {"active": false, ...}   rc=0
    harness-maker autopilot status --root . → unknown action 'status'  rc=2

`cli.py`'s typer shim gained `--force` in the same change that added `status` to
`autopilot.main` and to `command_registry.MODULES["autopilot"].subcommands`; the action
table was the half that was missed. `resolve_toggle_config`'s own comment states the
shared helper exists so "the Typer alias and the dot-form entry can never drift" — the
validation path could not drift, the dispatch table could. No test invoked the shim with
anything but `on`/`off`/garbage.

Fixed: `status` branch added to the shim (delegating to `autopilot.status`, no
reimplementation), unknown-action message corrected to name all three. Gate:
`test_cli_shim_accepts_every_registered_action` derives the action set from the registry
and asserts the shim's payload equals `autopilot.status(...)`, so a future action cannot
land on one surface only. `ruff`, `ruff format`, `mypy --strict` clean.

### F33 (P3) — `status()` reports a failed GC as `"stale (gc'd)"`
The tail `if fresh != "fresh"` branch in `autopilot.status` is reachable only when the
top-of-function `gc_stale_marker` returned False (bytes changed underneath it) — i.e.
nothing was collected, while the label claims it was. The picker then takes the "anything
else" branch and attempts to arm, which can hit the ownership raise (exit 3); the picker
has no branch for that exit. Narrow race. Not fixed.

### F34 (P3) — a post-upgrade legacy marker reads as `foreign`
`_is_own` is one-directional, so an id-bearing session versus a marker with
`claude_session_id: null` is foreign. A user who upgrades mid-session with a fresh
pre-upgrade marker is asked by the picker whether another Claude session is open — a false
premise about their own marker. Self-heals within the 18h TTL, or with one "no" plus
`--force`. It is the CLAUDE.md absent-case rule landing on the wrong side: the missing
field means "written before this shipped", not "written by someone else". Not fixed.

### Side effect of this review
Verifying F32 ran `hm autopilot status` against the real tree, which GC'd a TTL-stale
marker at the base. Intended behaviour, but `status` is not a pure read on either surface —
now noted in the shim's comment.

### Round 7 verification
`tests/unit/test_autopilot.py`, `test_command_registry.py`, `test_autonomy_config.py`: 50
passed. Full autopilot scope before the fix: 259 passed. `ruff check`, `ruff format
--check`, `mypy --strict` clean on the touched files. The two known Phase-5 surface-baseline
failures are unaffected (no rendered surface changed in this round).
