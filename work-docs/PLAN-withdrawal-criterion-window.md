---
type: plan
task_slug: withdrawal-criterion-window
status: complete
created: 2026-09-20
tags: [harness-maker, plan, python, intent-layer, withdrawal, observability]
spec: "[[SPEC-withdrawal-criterion-window]]"
research_doc: "[[RESEARCH-ai-native-sdlc-vs-intent-world]]"
interview_rounds: 3
adrs: 6
validator_outcome: MAJOR_REVISION_RESOLVED
summary: "Replace the cumulative withdrawal rule with a quiet-window counter, and register the succession"
spec_need_verdict: add
spec_need_target: withdrawal-criterion-window
---

# PLAN: A withdrawal criterion that can still fire

## 🎯 Executive Summary

**What.** `withdrawal_due` stops reading a cumulative count and starts reading one number:
how many `hm:wrapup` start events have landed since the intent layer last did anything. The
`gap --json` `withdrawal` block swaps `objectives_observed` / `wrapups_since_fill` for
`last_signal_at` / `quiet_wrapups`, the `/hm:wrapup` notice is rewritten to quote them, and
the succession is registered in both the new SPEC and the SPEC that registered the retired
rule.

**Why.** The shipped rule requires `objectives_observed == 0`. This repository closed
`SOURCE-PLAN-STEPS` with `observed: missed` on 2026-09-18, so that count is permanently 1 and
`due` can never be true again. Meanwhile every one of the 16 measurement rows in
`.claude/world/outcomes.yaml` carries an `observed_at` of 2026-09-18, four wrapups have
landed since with no signal of any kind, and `LOOP-OPT-IN` has sat at `proposed` throughout.
The instrument reports green while describing the exact state it exists to detect.

**Key decisions.** One counter rather than a window set (ADR-001). The retired ACs are marked,
not rewritten or deleted (ADR-002). The payload replaces keys instead of keeping dead ones
(ADR-003, = IRR-001). `filled_at` is the fallback cutoff and is resolved only on the branch
that consumes it, while `reason` derives from what blocked the count (ADR-004, reversed at
review round 3). The byte-lock golden is regenerated rather than merged (ADR-005). A
future-dated datum is skipped rather than clamped, so it cannot re-create the permanent
suppression this task exists to remove (ADR-006, corrected at review round 2).

**Impact.** ~60 lines of `src/harness_maker/world.py`, one rewritten unit-test module and two
extended ones, five prose sites, three SPEC ACs marked superseded. No stored data changes, so
no migration.

### Non-Goals (PLAN level; the SPEC's list also applies)

- The objective **link rate** signal — three readers of that link are mid-move to SPEC on
  `hm/plan-stage-absorption`.
- Any change to `hm world status --json`.
- Re-tuning `WITHDRAWAL_WRAPUPS`.

## 📚 Prior Work

- `[wiki:architecture] intent-layer-withdrawal-instrument` — the block's shipped contract,
  including the invariant this PLAN must preserve: **a count that cannot be taken is `None`
  with a `reason`, never a disguised `0`.**
- `[wiki:architecture] objective-gap-and-proposal` — `status --json` is byte-frozen; the
  withdrawal block lives in `gap` only, and both entry points share one `_status_payload`.
- `[wiki:architecture] outcome-measure-verb` — how a measurement row, and therefore a signal,
  comes to exist.
- `[fail:test] assertion-invariant-over-named-dimension` (count:16) — the dominant local
  defect. Every test here must bind the **window** dimension specifically; a test that passes
  against the cumulative implementation has not tested this change.
- `[fail:test] fix-introduced-defect-passes-all-gates` (count:13) — the revision rounds are
  where new defects come from.
- `[fail:design] wrapup-memory-base-seam` (count:5) — base-rooted writers and a worktree
  `git add` diverge; relevant to Phase 4's receipt if one is needed.
- `work-docs/RESEARCH-ai-native-sdlc-vs-intent-world.md` — ranked item 3, "register a fireable
  withdrawal criterion", named as the prerequisite for expanding the layer.
- [[feedback_honor_preregistered_rules]] — a pre-registered rule is not reinterpreted once it
  fires. This one has not fired and cannot; replacing it now is legitimate only because the
  replacement is registered with the same force.

## 🎙️ Interview Transcript

| # | Topic | Category | Question | Options | Choice | Note | → ADR |
|---|---|---|---|---|---|---|---|
| 1 | Strictness | Scope | Activity window or influence window? | activity / influence / both-reported | activity | Locked pre-interview; influence fires during legitimately quiet stretches where objectives are being worked | ADR-001 |
| 2 | Window shape | Contract | One "since last signal" counter, or a trailing-10-wrapup set? | counter / set | counter | The set needs its own rule for repositories with fewer than 10 wrapups; the counter's `filled_at` fallback covers it for free | ADR-001 |
| 3 | Payload | Contract | Replace the deciding keys, or keep the old ones as informational? | replace / keep both | replace | A key that is read but decides nothing is the next reader's trap | ADR-003 |
| 4 | Registration | Risk | Register the successor here only, or also at the original site? | both / here only | both | A reader of the original SPEC would otherwise see a dead rule presented as live | ADR-001 |
| 5 | Threshold | Scope | Keep `WITHDRAWAL_WRAPUPS = 10`? | 10 / 15-20 / 5-7 | 10 | Changing the number while changing the rule makes the successor untraceable to what it replaced | — |
| 6 | Irreversible list | Contract | IRR-001 alone, or also the rule replacement? | IRR-001 only / add the rule | IRR-001 only | The rule replacement fits none of the five categories; widening the filter to admit it would set a worse precedent than recording it as prose | — |
| 7 | AC succession | Contract | New SPEC owns the tables / update the old tables in place / delete the old ACs | three options | new SPEC owns, old marked | A landed SPEC must keep answering "what did that task deliver" | ADR-002 |
| 8 | Objective link | Scope | LOOP-OPT-IN / none / none + draft | three options | none, no draft | No current outcome moves under this hypothesis; linking to an absent one is how the layer becomes decoration | — |
| 9 | Retirement marker | Contract | `superseded_by` extension key / `pending_test: false` variant / prose only | three options | `superseded_by` key | First AC retirement in this repo; the marker chosen becomes the precedent | ADR-002 |
| 10 | Clock skew | Failure handling | Clamp the cutoff to `now`, trust producer timestamps, or clamp both ends? | three options | clamp to `now` | Raised by the validator and by codex; trusting the timestamps re-creates permanent suppression through the data instead of the logic | ADR-006 |

## 📐 Architecture Decision Records

### ADR-001: One counter — wrapups since the last signal, with `filled_at` as the floor
**Status:** Accepted (2026-09-20, via /hm:plan interview)
**Context:** The shipped rule's `objectives_observed` is cumulative, so a single measurement
anywhere in history pins `due` to false forever. A replacement must be window-scoped, and the
window has to be defined for repositories whose entire history is shorter than the threshold.
**Decision:** `last_signal_at` = the maximum over measurement `observed_at` and each
objective's `created_at`, `approval.approved_at` and `closed_at`. `quiet_wrapups` = the count
of `hm:wrapup` start events after the cutoff, where the cutoff is `last_signal_at`, or
`filled_at` when no signal has ever been recorded; a stored instant ahead of `now` is skipped
rather than used, per ADR-006 as corrected. `due` =
`quiet_wrapups >= WITHDRAWAL_WRAPUPS and revisit_candidates_now == 0`. The threshold stays 10.
The `not_filled_in` guard keeps precedence over all of it — see Technical Design.
**Consequences:**
- ✅ Ratchet-free: an event older than `last_signal_at` cannot move the verdict, and `due` is
  reachable from every **filled-in** state whose revisit set is empty. The qualifier is
  load-bearing: `world.objectives` loads independently of `intent.outcomes`, so an unfilled
  intent carrying objective records is reachable, and it must keep returning `not_filled_in`.
- ✅ The never-signalled case needs no special rule — `filled_at` is the natural floor, and it
  reproduces the retired rule's behaviour for a layer that was filled in and then ignored.
- ⚠️ "Activity" is counted, not "influence": an operator who runs `outcome measure` every
  wrapup keeps the layer alive without it ever changing a decision. Accepted — the influence
  variant fires during legitimately quiet stretches where objectives are active and being
  worked.
**Rejected alternatives:**
- A trailing-10-wrapup set — needs its own absent-case rule for repositories with fewer than
  10 wrapups, which is the class of bug this repo has shipped eight times
  (`absent-case = feature black hole`).
- An influence-weighted window — see the trade-off above.
**Source:** Interview #1, #2, #5

### ADR-002: The retired ACs are marked with a `superseded_by` key, not rewritten or deleted
**Status:** Accepted (2026-09-20, via /hm:plan interview)
**Context:** `tests/unit/test_world_withdrawal.py` loads its golden tables from
`SPEC-intent-layer-ops.machine.yaml` AC-003 and AC-004, and calls
`withdrawal_due(wrapups_since_fill, objectives_observed, revisit_candidates_now)`. Changing
the signature invalidates both tables and both tests. That SPEC is `schema_version: 2` and
carries no approval stamp, so every option is hash-safe; the question is what the SPEC corpus
should say afterwards. This is the first AC retirement in this repository.
**Decision:** `SPEC-withdrawal-criterion-window` AC-006 owns the new golden table and the
rewritten tests bind to it. `SPEC-intent-layer-ops` **AC-002, AC-003 and AC-004** each gain an
authored `superseded_by: SPEC-withdrawal-criterion-window` key (round-tripped and hashed by
`ConfigDict(extra="allow")`), `test_ids: []` and `pending_test: true`, and their existing
golden tables and predicates are left in place as the historical record of what that task
accepted. The `.md` headings gain a matching superseded line. **The retired test function
names are not reused** — `test_ac_002_gap_reports_the_withdrawal_block`,
`test_ac_003_due_is_the_criterion_exactly`, `test_ac_004_unmeasurable_counts_are_null_with_reason`
and `test_ac_004_every_table_row_has_a_fixture` are deleted, not repurposed.

**AC-002 is in this list because Phase 1 breaks it.** It is `pending_test: false`, bound to
`tests/unit/test_world_withdrawal.py::test_ac_002_gap_reports_the_withdrawal_block`, and its
`executable_predicate` asserts `set(w) == {'filled_at', 'wrapups_since_fill',
'objectives_observed', ...}` — the key set IRR-001 removes. `cross_validate` rule 3
(`spec_machine.py:528-540`) resolves every non-pending AC's `test_ids` through
`pytest --collect-only`, so the moment Phase 1 rewrites that module, rule 3 fails on an AC the
first draft of this PLAN never mentioned. Keeping the old function name to keep the gate green
would leave a live AC whose predicate asserts a key set that no longer exists — a green gate
asserting a false contract, which is worse than the failure.
**Consequences:**
- ✅ A reader can still ask what `intent-layer-ops` delivered and get the answer it shipped.
- ✅ `superseded_by` is the only machine-readable signal distinguishing a retired AC from an
  unwritten one, and it is available to every future retirement.
- ⚠️ `pending_test: true` reads as "the test has not been written yet", which is not what is
  true here. The schema requires `test_ids != []` **or** `pending_test: true`, so with the
  bindings removed this is the only admissible value. `superseded_by` carries the real meaning;
  anything reading `pending_test` alone will misread these two ACs.
- ⚠️ `find-unbound` will treat them as genuine future work and safe-skip them, because no
  convention-named test will collect once the old tests are gone.
**Rejected alternatives:**
- Update the old tables in place — makes a completed task's SPEC describe behaviour that task
  never delivered.
- Delete the ACs — erases the acceptance record of a landed task.
- Keep the retired function names so rule 3 stays green — ships a live AC asserting a removed
  key set.
**Source:** Interview #7, #9; plan-validator critical #3

### ADR-003: The payload replaces its deciding keys rather than keeping dead ones
**Status:** Accepted (2026-09-20, via /hm:plan interview)
**Context:** `objectives_observed` is the key that created the ratchet and `wrapups_since_fill`
names a window that no longer exists. Both could be kept as informational fields.
**Decision:** The `withdrawal` block becomes exactly
`{filled_at, last_signal_at, quiet_wrapups, revisit_candidates_now, due, reason}`.
`objectives_observed` and `wrapups_since_fill` are removed. This is IRR-001.
**Consequences:**
- ✅ Every key in the block decides something or is explicitly labelled informational, and the
  names match the semantics.
- ⚠️ A consumer outside this repository that parses the removed keys breaks with no shim
  available. The in-repo readers — the wrapup template, `test_world_withdrawal.py`,
  `docs/HOW-IT-WORKS.md` — are all updated in this change.
**Rejected alternatives:**
- Keep both key sets — leaves a key that is read and decides nothing, which is the trap the
  next reader falls into.
- Keep the old names with new meanings — a name that makes a reader believe something false
  about behaviour is the defect, not the fix.
**Source:** Interview #3

### ADR-004: `filled_at` is resolved only on the branch that consumes it
**Status:** Accepted (2026-09-20, via /hm:plan default) · **REVERSED at review round 3** (DRI
decision, on `concurrency-reviewer`'s evidence)
**Context:** Once `last_signal_at` exists, `filled_at` is no longer needed to produce a
verdict, and computing it costs `git` subprocess calls on every `gap`. It is nevertheless part
of the reported payload.

> **The original decision was to keep computing it unconditionally**, on the ground that making
> a reported field conditionally absent is "a second contract change and a second absent-case to
> specify". Review round 1 supplied the magnitude that reasoning lacked: not two or three calls
> but a `rev-parse`, a `log`, and **a `show` per historical commit that touched the file**, each
> under a 10 s timeout, against an object store shared with every concurrent worktree — and the
> `git_reason` that work produces is discarded whenever a signal exists, which is the common
> case once the layer has been used at all. The DRI judged the cost too high. Reversed.

**Decision:** `_filled_at` is called **only when `last_signal_at` is None**, because that is the
only branch that consumes it. `filled_at` stays in the payload and is `null` otherwise. `reason`
is still derived from whatever blocked `quiet_wrapups`.
**Consequences:**
- ✅ The git chain leaves the hot read path in the common case. A repository that has ever
  signalled pays nothing for it.
- ✅ The key set is untouched, so IRR-001 and AC-008 hold and the SPEC needs no re-approval.
  Dropping the key outright was rejected for exactly that reason.
- ⚠️ `filled_at: null` now has two producers — "not asked for" and "git could not answer". They
  are distinguishable **from the payload itself**: a non-null `last_signal_at` means the first,
  a null one means the second and `reason` names it. Written into `withdrawal_report`'s
  docstring, since a reader meets the field there rather than here.
- ⚠️ `test_ac_005`'s `filled_at is None` assertion became vacuous under this change — it had
  proved "git refused", and would now pass whether or not git could answer. Removed from that
  test and replaced by `test_filled_at_is_not_resolved_when_a_signal_exists`, which uses an
  ordinary repository where git WOULD succeed, so the null means what it says.
**Rejected alternatives:**
- Keep computing it unconditionally — what this supersedes.
- Drop `filled_at` from the payload — changes the key set IRR-001 fixed and the set AC-008
  asserts, so it would invalidate the DRI's approval stamp for a performance change.
**Source:** Pre-interview default, disclosed in the design brief; reversed on
`concurrency-reviewer`'s round-1 finding after the DRI judged the cost too high

### ADR-005: The byte-lock golden is regenerated, never merged
**Status:** Accepted (2026-09-20, via /hm:plan default)
**Context:** Rewriting the `/hm:wrapup` withdrawal notice moves the hashes in
`tests/structural/autopilot_gate_golden.json` across all four arms. A concurrent task on
`hm/plan-stage-absorption` is modifying many templates and will move the same hashes.
**Decision:** Treat the golden as a derived artifact. Whichever task lands second re-captures
it from its own tree rather than resolving a textual conflict, and records the re-capture with
its reason in `tests/structural/test_autopilot_gate_render.py`'s docstring, as every previous
re-capture has been.
**Consequences:**
- ✅ No hand-merge of a hash file, which cannot be reviewed for correctness by reading it.
- ⚠️ The second task pays a re-capture and a re-run of the structural suite.
**Rejected alternatives:**
- Sequencing the two tasks so only one touches the golden — the other task is already in
  flight across 64 files; blocking on it would stall this one for no safety gain.
**Source:** Design brief, ambiguity 4

### ADR-006: A stored instant ahead of `now` is skipped, not clamped
**Status:** Accepted (2026-09-20, via /hm:plan follow-up round)
**Context:** `_aware_instant` rejects a naive or malformed timestamp but accepts an aware one
dated years in the future, and `_count_wrapups` compares event timestamps directly against the
cutoff with no plausibility bound. An objective's `created_at`, `approval.approved_at` and
`closed_at` are hand-authored YAML, not machine-stamped like a measurement's `observed_at`. A
single mistyped future-dated `closed_at` would become `last_signal_at` permanently, pin
`quiet_wrapups` at 0, and make `due` unreachable — the exact permanent-suppression defect this
task exists to remove, re-entered through the data rather than the logic.
**Decision — CORRECTED at review round 2.** A stored instant ahead of `now` is **skipped**, on
the same grounds and by the same code path as an unparseable one: a timestamp in the future is
not a record of something that happened, it is bad data. `last_signal_at` drops it and the next
real signal wins; if there is none, the count falls back to `filled_at`.

> **The original decision was `since = min(last_signal_at or filled_at, now)`, and the claim
> attached to it — "the suppression it causes is bounded at 10 wrapups instead of unbounded" —
> was false.** `now` advances on every call, so the clamped cutoff advanced with it, while a real
> wrapup ledger only ever holds events in the *past* of `now`. `quiet_wrapups` therefore sat at
> **0 until the mistyped date actually arrived** — unbounded in calendar time, which is the exact
> defect ADR-006 exists to remove, re-entered through a different door. Found by the codex
> second opinion at review round 1 (`ea80ac994b7d11fa`) and confirmed here by direct probe:
> `_clamped('2030-01-01T00:00:00Z', now)` returns `now` for every `now`.
>
> **The test passed because it pinned an unreachable state.** It froze `now` at 2026-09-20 and
> placed all ten wrapups *after* that instant — a ledger that cannot exist. Four green gates,
> a 9032-test suite and a discrimination screen all passed over it. The replacement fixture
> pairs a valid 2026 signal with a bogus 2030 one, which is reachable and which no
> future-accepting reader can satisfy.

**Consequences:**
- ✅ No single datum can make the switch unfireable, and the fix needs no new concept — it
  reuses the skip path that already existed for unparseable values.
- ⚠️ A clock skewed a few seconds fast drops that one signal until the next report, which then
  picks it up. Self-healing and bounded, unlike the behaviour it replaces.
- ⚠️ The mirror case is still accepted, not fixed: a signal backdated before existing wrapups
  makes those wrapups count as quiet and can fire the notice early. Fixing it needs the
  *recording* time, which nothing stores. `due` prints an advisory line rather than gating.
**Rejected alternatives:**
- Clamping the cutoff to `now` — what this supersedes; see above.
- Producer timestamps authoritative — leaves the original defect open.
**Source:** plan-validator warning; codex `db64b48cd8136286` (plan) and `ea80ac994b7d11fa`
(review round 1); corrected at review round 2

## 🏗️ Technical Design

**Current state.** `world.withdrawal_report(world, root, fired)` computes `objectives_observed`
by scanning every objective for a non-null `observed`, resolves `filled_at` through `_filled_at`
(git), counts wrapups since that date through `_count_wrapups`, and calls
`withdrawal_due(wrapups, observed, candidates)`. `gap_report` attaches the result under
`withdrawal`. `status_report` does not.

**Affected components.**

| Component | Change |
|---|---|
| `world.withdrawal_due` | Signature drops `observed`; takes `(quiet_wrapups, candidates)` |
| `world` (new helper) | `last_signal_at(world)` — max over the four timestamp sources, skipping unparseable values |
| `world.withdrawal_report` | Computes `last_signal_at`, chooses `since`, emits the six-key payload; the `not_filled_in` short-circuit stays exactly where it is. No clamp — a future instant is dropped inside `last_signal_at` (ADR-006 as corrected) |
| `world._count_wrapups` | Unchanged — already takes a `since` string and returns `(count, reason)` |
| `world._filled_at` | Body unchanged, but it is now called **only when `last_signal_at` is None** and against `resolve_base_root(root)` rather than the checkout (ADR-004 as reversed) |
| `tests/unit/test_render_intent_layer.py` | Gains AC-007's rendered-notice assertion |
| `tests/unit/test_withdrawal_succession.py` | New — AC-009 |
| `intent.SKELETON` | The comment describing the criterion |
| `templates/stages/wrapup.md.j2` | The notice line |
| `docs/HOW-IT-WORKS.md:1539-1549` | The block's documented shape |
| `specs/SPEC-intent-world-model-objective-layer.md` | Constraints row gains the successor pointer |
| `specs/SPEC-intent-layer-ops.{md,machine.yaml}` | AC-003/AC-004 marked superseded |
| `tests/unit/test_world_withdrawal.py` | Rewritten against the new SPEC's tables |
| `tests/structural/autopilot_gate_golden.json` | Re-captured |

**Dependencies.** None added.

**Data flow.** `load_world` already supplies both the measurement rows (`world.values`) and the
objective records (`world.objectives`) that `last_signal_at` reads, in one disk snapshot — the
same call `gap_report` already makes. No new read of disk, and no possibility of the two halves
coming from different snapshots.

**Design decisions.** `last_signal_at` skips a timestamp that is not an aware ISO instant
rather than failing, matching the existing evidence readers (`_aware_instant` returns `None`
and the row is passed over). This is deliberate and specified as part of AC-003: a history
typo must not break every `gap` call. ADR-004 governs the `reason` derivation, ADR-006 the
clamp.

**Reason precedence — fixed order, first match wins.** The existing `not_filled_in`
short-circuit (`world.py:970-975`) keeps precedence over everything below it and is **not**
moved. Reading ADR-001's reachability claim as permission to hoist the signal computation
above that guard would let a never-installed layer carrying one stray objective record report
`reason: ok` and, after ten wrapups, `due: true` — a retirement notice for a layer that was
never filled in.

| # | Condition | `reason` |
|---|---|---|
| 1 | `is_not_filled_in(world.intent)` | `not_filled_in` |
| 2 | no signal, and git cannot resolve the fill date | `no_git` |
| 3 | no signal, and no commit carries a filled `intent.yaml` | `fill_uncommitted` |
| 4 | a cutoff exists, `stage-spans.jsonl` absent | `no_stage_spans` |
| 5 | a cutoff exists, ledger carries no `hm:wrapup` event | `no_wrapup_spans` |
| 6 | otherwise | `ok` |

Rows 2 and 3 are unreachable once a signal exists — that is exactly AC-005. The enum gains and
loses no value.

**AC-005's fixture preconditions**, which the SPEC's one-line summary does not carry: a
**filled-in** intent, a `stage-spans.jsonl` carrying at least one `hm:wrapup` **start** event,
a shallow clone (so `_filled_at` returns `no_git`), and at least one recorded signal. A signal
alone does not produce `reason: ok`; rows 4 and 5 above still apply.

**API changes.** `hm world gap --json` → `withdrawal` block key set (IRR-001). No other CLI
surface changes.

## 📝 Implementation Plan

### Phase 1 — The windowed criterion in `world.py`
- **depends_on:** `[]`
- **parallel_group:** `serial-core`
- **merge_hazards:** none — the concurrent task's 64-file set does not include `world.py`
  (verified 2026-09-20)
- **Scope (in):** `src/harness_maker/world.py`, `tests/unit/test_world_withdrawal.py`
- **Scope (out):** every template, every other SPEC, `docs/`
- **Exit criterion:** all four must hold —
  1. `uv run pytest tests/unit/test_world_withdrawal.py tests/unit/test_world_gap.py tests/unit/test_world_status_and_revisit.py` passes;
  2. `HM_WITHDRAWAL_CONTROL=1 uv run pytest tests/unit/test_world_withdrawal.py -m discriminates` reports **every selected test failing** — a red sweep against HEAD proves nothing here;
  3. `test_every_subject_touching_test_declares_whether_it_discriminates` passes, which is what makes criterion 2 exhaustive rather than a claim about whichever tests happen to carry the marker;
  4. `uv run ruff check src/harness_maker/world.py` and `uv run mypy --strict src/harness_maker/world.py` clean
- **Risk:** medium — this is the behaviour change; the tests must bind the window dimension, not merely the new key names
- **Rollback point:** base HEAD
- **Status: DONE.** All four exit criteria met: the three modules pass (43); `HM_WITHDRAWAL_CONTROL=1 … -m discriminates` reports **6 failed, 0 passed**; the marker-bookkeeping test passes (6 of 25 selected, 9 exemptions each carrying a reason); `ruff check` and `mypy --strict` clean on `world.py`. Phase D's targeted set (28 nodes → 1309 tests) passed.

### Phase 2 — Golden tables and AC supersession
- **depends_on:** `[1]`
- **parallel_group:** `serial-core`
- **merge_hazards:** `specs/SPEC-intent-layer-ops.machine.yaml` — not in the concurrent task's set
- **Scope (in):** `specs/SPEC-intent-layer-ops.md`, `specs/SPEC-intent-layer-ops.machine.yaml` — AC-002, AC-003 and AC-004
- **Scope (out):** the **authored** fields of `specs/SPEC-withdrawal-criterion-window.machine.yaml` (see Contract Boundaries — its tooling fields are a different matter)
- **Exit criterion:** all three —
  1. `uv run hm spec_machine check --all --yaml specs/SPEC-intent-layer-ops.machine.yaml --md specs/SPEC-intent-layer-ops.md --dev-mode spec-driven` exits 0;
  2. the same command against **`specs/SPEC-withdrawal-criterion-window.{machine.yaml,md}`** exits 0 — the first draft of this PLAN never cross-validated the SPEC the task delivers;
  3. `hm spec_machine approval-status --root . --slug withdrawal-criterion-window` still reports `state: approved`
- **Risk:** low
- **Rollback point:** Phase 1
- **Status: DONE.** All three exit criteria met: `spec_machine check --all` exits 0 on `SPEC-intent-layer-ops` (quality 84) and on `SPEC-withdrawal-criterion-window` (quality 80), and `approval-status --slug withdrawal-criterion-window` still reports `state: approved`, `gate: clear`. AC-002, AC-003 and AC-004 of the old SPEC carry `superseded_by`, `test_ids: []`, `pending_test: true`, with a matching superseded blockquote in the `.md` and their golden tables kept verbatim.

### Phase 3 — Prose, the two registration sites, and the golden
- **depends_on:** `[1]`
- **parallel_group:** `serial-core`
- **merge_hazards:** `tests/structural/autopilot_gate_golden.json` — the concurrent task moves the same hashes; per ADR-005 the second lander regenerates rather than merging
- **Scope (in):** `src/harness_maker/intent.py` (the `SKELETON` comment only), `src/harness_maker/templates/stages/wrapup.md.j2`, `docs/HOW-IT-WORKS.md:1539-1549`, `.claude/memory/wiki.md` (the `intent-layer-withdrawal-instrument` entry, which states the retired key set verbatim — edited through the memory CLI, not by hand), `specs/SPEC-intent-world-model-objective-layer.md`, `tests/unit/test_render_intent_layer.py` (AC-007), `tests/unit/test_withdrawal_succession.py` (new — AC-009), `tests/structural/autopilot_gate_golden.json`, `tests/structural/test_autopilot_gate_render.py` (docstring re-capture entry)
- **Scope (out):** any other template; any new `Step`/`Phase`/`Check` heading; `tests/structural/` — AC-009 guards a document cross-reference, which has no source line whose deletion turns it red, so it cannot answer the `test_new_gates_file_a_mutation_receipt` obligation and does not belong there
- **Exit criterion:** both —
  1. `uv run pytest tests/structural/test_autopilot_gate_render.py tests/unit/test_render_intent_layer.py tests/unit/test_render_wrapup_delegation.py tests/unit/test_withdrawal_succession.py tests/structural/test_command_size_budget.py` passes, **including the new AC-007 assertion in `test_render_intent_layer.py` and every test in `test_withdrawal_succession.py`** — the four pre-existing modules pass today on the unchanged notice and prove nothing about this phase;
  2. the re-capture entry added to `test_autopilot_gate_render.py`'s docstring states, as every prior entry does, that wrapup is the only moved command in every arm — verified before re-capturing, not asserted after
- **Risk:** medium — the golden re-capture is the step that can silently absorb an unintended template change
- **Rollback point:** Phase 2
- **Status: DONE.** 68 tests pass across the five named modules. AC-007 and AC-009 were each verified to FAIL against the pre-change state mechanically, not by assertion: `git show HEAD:…wrapup.md.j2` carries `wrapups_since_fill` and `no observed objective` with zero occurrences of the new keys, and the old Constraints row carries no successor pointer. The golden was re-captured after verifying across **all four arms** that `wrapup` is the only moved command; the notice came out a net 10 characters shorter, so no `surface_allowance` was needed.
- **Constraint honoured:** the old SPEC's AC-005 was NOT retired, and its predicate requires four literals to survive — `[intent] withdrawal criterion met` exactly once in Step 5.7, `withdrawal.due`, and `hm world gap` + `withdrawal.due` in `intent.SKELETON`. All four are still present.

### Phase 4 — Mutation measurement and the full suite
- **depends_on:** `[1, 2, 3]`
- **parallel_group:** `serial-tail`
- **merge_hazards:** `.claude/observability/mutation-receipts.jsonl` is base-rooted and the concurrent task has an uncommitted row in it; write only if a new gate requires a receipt, and mirror per `[fail:design] wrapup-memory-base-seam`
- **Scope (in):** `work-docs/MUTATION-withdrawal-criterion-window-2026-09-20.md`
- **Scope (out):** source and tests — a measurement that changes the subject is not a measurement
- **Exit criterion:** the full suite is green and the MUTATION document records a real score for `src/harness_maker/world.py` with the survivors named
- **Risk:** low
- **Rollback point:** Phase 3
- **Status: DONE.** 19 targeted mutants, 17 killed, **89%** — `work-docs/MUTATION-withdrawal-criterion-window-2026-09-20.md`. Both survivors are classified equivalent. The measurement is targeted rather than mutmut-whole-file for two reasons recorded in that document, one of which is a tool defect (`--sampled` silently measures nothing).

### Execution notes

**Phase D.5 — the window this repair newly made reachable.** `withdrawal_report` previously
read no signal timestamp at all and always counted from `filled_at`. Four input windows open:

| Newly reachable | Test that enters it |
|---|---|
| Any of the four signal timestamps participating, including unparseable ones | `test_ac_003_last_signal_at_is_the_max_over_the_four_sources` — parametrised over all four winners, with two unparseable values riding along |
| A cutoff LATER than `filled_at` | `test_ac_001_moving_the_newest_signal_across_the_wrapups_changes_the_count` |
| A cutoff dated in the future | `test_a_future_dated_signal_is_clamped_to_now`, with `test_a_normally_dated_signal_is_not_clamped` as its control |
| `_filled_at` failing while a signal exists — previously a hard stop at `no_git` | `test_ac_005_a_shallow_clone_with_a_signal_still_counts` |

**Absent case**, the repository's most recurrent class (count 8): the repair activates on
optional fields that predate it — `approval`, `closed_at`, `observed_at` are all nullable, and
most objectives carry `approval: null`. The absent-case behaviour is *skip the source*, and if
every source is absent, *fall back to `filled_at`*. Covered by
`test_a_layer_that_never_signalled_counts_from_filled_at` (no source at all) and by every
fixture in the reason table (each carries some sources and not others).

**Declared scope drift — `tests/unit/test_land_hold.py`.** Not in any phase's scope, changed
anyway, with the DRI's agreement recorded in-session. `main` was red: that module could not be
COLLECTED, so the whole suite aborted at `rc=2`. It was landed broken by the previous task
(`e5dfb2f3`) and had never run once. Three independent mismatches: an AC inserted mid-list in
`SPEC-mutation-survivors-and-approval-p2s` shifted every later id by one; the spec.dir rows key
their input `value`, not `dir`; and the caps AC (AC-011) is `mechanical` with no golden table at
all and `pending_test: true`, so its consumer had nothing to load. Repaired by moving the
consumer, never the record — that SPEC carries an approval stamp bound to its authored fields,
and its own rule is that ids are never reused. The test names were corrected to the ids they
actually load.

**Why no gate caught it:** the previous task's wrapup Step 2 reused a fresh verification-cache
marker instead of running the suite. That cache claims to invalidate on source and test changes,
and that commit changed both. Worth a REVIEW finding of its own.

## 🚧 Contract Boundaries

### Do not change
- `src/harness_maker/autopilot_caps.py` — in flight on `hm/plan-stage-absorption`
- `src/harness_maker/models.py` — in flight on `hm/plan-stage-absorption`
- `src/harness_maker/presets.py` — in flight on `hm/plan-stage-absorption`
- `src/harness_maker/synthesize.py` — in flight on `hm/plan-stage-absorption`
- `src/harness_maker/step_sensitivity.py` — in flight; it must classify every rendered heading
- `src/harness_maker/command_registry.py` — in flight on `hm/plan-stage-absorption`
- `src/harness_maker/templates/stages/spec.md.j2` — in flight on `hm/plan-stage-absorption`
- `src/harness_maker/templates/stages/plan.md.j2` — deleted by the concurrent task
- `specs/SPEC-withdrawal-criterion-window.machine.yaml` — the **authored** fields (AC titles, predicates, oracles, golden rows, `irreversible_decisions`, tier, `spec_slug`) are DRI-approved and frozen; editing any of them invalidates `approval.content_hash`. **The tooling fields are not frozen and must be written**: `HASH_DENYLIST_AC` (`spec_machine.py:1516-1523`) excludes `test_ids`, `pending_test`, `judgment_verdict`, `judged_at`, `judgment_evidence` and `judgment_subject_hash` from the hash, and `_hash_payload` pops them before hashing. `/hm:wrapup` Step 3.5's `mark-tested` write-back is the owner of that write, and it is stamp-safe by design. An earlier draft of this PLAN said "any edit invalidates the stamp", which would have left all nine ACs of the delivered SPEC permanently unbound
- Advisory: add no new rendered `Step`/`Phase`/`Check` heading — the registry that must classify it is owned by the concurrent task
- Advisory: `hm world status --json` stays byte-identical
- Advisory: the `reason` enum gains and loses no value

## 🧪 Testing Strategy

**Unit** — `tests/unit/test_world_withdrawal.py`, rewritten:

- **AC-001, two halves in one place.** The *invariance* half (append a signal older than
  `last_signal_at`; nothing moves) and a named *sensitivity* half (move the newest signal
  forward across counted wrapups; `quiet_wrapups` and `due` must both change). The invariance
  half alone is satisfied by a constant — and by the retired rule, which reads no timestamp
  source at all. Only the pair binds the dimension.
- **AC-002 reachability**, with the generator pinned to include at least one objective carrying
  `observed: missed` — the exact state that pinned this repository's `due` to false.
- **The never-signalled fallback**, named explicitly: no signal at all → the count runs from
  `filled_at` → `due` after 10 wrapups. ADR-001 rejects the alternative design *because* this
  case needs no special rule, and nothing else in the suite would notice it regressing to
  `None`/`no_git`.
- **Two future-signal tests** (ADR-006 as corrected): a fixture pairing a valid 2026 signal with
  a bogus 2030 one must pick the 2026 value and count the wrapups after it — the future value is
  dropped, not clamped, so `quiet_wrapups` reaches the threshold immediately rather than sitting
  at 0. A past-dated signal is the control. `now` is injected, never read from the wall clock.
  The superseded wording here described the clamp and asserted the opposite outcome.
- **Parametrised reason-table tests** from the new SPEC's AC-006 golden table, plus the
  precedence table in Technical Design.
- **AC-004** absent-case and **AC-005** shallow-clone-with-signal, the latter built with all
  four preconditions listed in Technical Design.

**The discrimination requirement, and why the obvious check does not work.** Per
`assertion-invariant-over-named-dimension` (count:16) every test here must fail against a
*behaviourally* retired implementation. **Phase A.4's false-RED screen against HEAD cannot
establish that**: IRR-001 renames the payload keys, so any test touching `quiet_wrapups` or
`last_signal_at` raises `KeyError` against HEAD whether it binds the window dimension or
merely reads a renamed field. An all-red sweep against HEAD carries zero bits.

The screen therefore runs against a **renamed-only control** — the retired cumulative logic
emitting the new six key names — which lives in the test module and is selected by
`HM_WITHDRAWAL_CONTROL=1`.

**Only some tests can discriminate, and that is the SPEC's doing, not an omission.** AC-004's
own `oracle_evidence` calls it a continuity check ("the new key inherits the assertion its
predecessor already had to pass"); AC-006's says the replacement "introduces no new failure
mode and retires none"; S3 says the never-signalled case behaves "as it did under the retired
rule". Requiring those to fail against the control would be requiring the SPEC to be violated —
an earlier draft of this PLAN did exactly that, naming the never-signalled test as one that
must fail, which is unsatisfiable. The six tests that read a value the window change moves
carry `@pytest.mark.discriminates`; every other test names its reason in `_NOT_IN_THE_SCREEN`,
in one of two kinds — **preserved** (the SPEC keeps this identical, so no correct
implementation diverges from the control) or **control-blind** (this control ignores the
dimension, though other wrong implementations would fail it). `test_every_subject_touching_test
_declares_whether_it_discriminates` derives the module's test set and asserts the two lists are
exhaustive, so a new window test cannot silently escape the screen.

**Render** — AC-007's assertion lives in `tests/unit/test_render_intent_layer.py`, grepping the
rendered command (not the template source) for `quiet_wrapups` and `last_signal_at` and for
the *absence* of "no observed objective". The module's existing withdrawal assertions
(`:370-377`) check only `[intent] withdrawal criterion met` and `withdrawal.due`, both of which
survive any rewrite of the notice — they are not a substitute.

**Succession** — AC-009's assertion lives in a new `tests/unit/test_withdrawal_succession.py`,
reading the Constraints row of `specs/SPEC-intent-world-model-objective-layer.md` for the
pointer to this SPEC.

**Integration** — none added; `gap --json` is exercised through the unit tests.

**Manual** — after landing, `uv run hm world gap --json` on this repository should report
`quiet_wrapups` around 4 and `due: false`, with `reason: ok`.

## ⚠️ Risks & Mitigation

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| A test passes against both implementations, so the change is untested | medium | high | The screen runs against a **renamed-only control**, not HEAD — a red sweep against HEAD is informationless once IRR-001 renames the keys. AC-001 carries a sensitivity half; AC-002's generator is pinned to include an `observed: missed` objective. Phase 1 exit criterion 2 |
| A hand-authored future-dated `closed_at` makes `due` permanently unreachable | low | high | ADR-006 **as corrected** skips the instant rather than clamping the cutoff; two named tests. The clamp this replaced did not bound it |
| A backdated signal fires the notice early on an active layer | low | medium | **Accepted.** Fixing it needs the signal's *recording* time, which nothing stores. `due` is a notice, so the cost is one spurious line, not a retirement |
| Phase 1 breaks `SPEC-intent-layer-ops` AC-002's rule-3 binding unnoticed | medium | medium | ADR-002 covers AC-002 explicitly; Phase 2 exit criterion 1 runs `spec_machine check` on that SPEC |
| The delivered SPEC's nine ACs land permanently unbound | medium | high | Contract Boundaries now states that `test_ids`/`pending_test` are hash-denied tooling fields; wrapup Step 3.5 owns the write; Phase 2 exit criterion 2 cross-validates the new SPEC |
| The golden re-capture absorbs an unintended template edit | medium | medium | Re-capture in Phase 3 only, with the diff of `wrapup.md.j2` reviewed first; the re-capture entry names the expected line count |
| The concurrent task lands first and this branch drifts | high | low | `task-refresh` rebases onto the base tip; the file sets are disjoint except the golden, which ADR-005 regenerates |
| `pending_test: true` on a superseded AC is misread by a future reader | medium | low | ADR-002 records the limitation; `superseded_by` is the authoritative signal |
| Removing `objectives_observed` breaks an out-of-repo consumer | low | medium | IRR-001 records it as irreversible and DRI-approved; all in-repo readers are updated in this change |
| The new rule fires sooner than expected and the layer is retired prematurely | low | high | `due` remains a notice; nothing is removed automatically, and the threshold is unchanged at 10 |

## ✅ Success Criteria

- [x] AC-001 — an event older than `last_signal_at` leaves `last_signal_at`, `quiet_wrapups` and `due` unchanged
- [x] AC-002 — appending 10 signal-free wrapups to any revisit-free state makes `due` true
- [x] AC-003 — `last_signal_at` is the maximum over the four sources; an unparseable timestamp is skipped
- [x] AC-004 — `quiet_wrapups is None` implies `reason != "ok"` and `due is False`
- [x] AC-005 — a shallow clone with a signal reports an integer count and `reason: ok`
- [x] AC-006 — the six reason values each have exactly one producing condition
- [x] AC-007 — the rendered wrapup notice quotes the new keys and drops "no observed objective"
- [x] AC-008 — the withdrawal block's key set is exactly the six declared keys
- [x] AC-009 — both registration sites carry the succession
- [x] `hm world status --json` byte-identical
- [x] Full suite, `ruff check`, `ruff format --check`, `mypy --strict` green

## 🔍 Plan Validation

**Pass 1 — `plan-validator`: MAJOR_REVISION** (4 critical, 5 warning, 1 suggestion).
Clean categories: `rollback-strategy`, `missing-interview-rounds`, `scope-drift-hazards`.

**Single pass by standing instruction.** The validator is not re-run after this revision.
Measured on this repository's own `stage-agents.jsonl`, 40 of 40 episodes ended
`MAJOR_REVISION` and no recorded episode ever reached a clean verdict, so a second pass buys
findings rather than release. The cost is explicit: any defect introduced *by* this revision
reaches `/hm:execute` Phase A.5 and `/hm:review` rather than being caught here, and
`fix-introduced-defect-passes-all-gates` (count:13) says that is where revision defects live.

| # | Severity | Finding | Disposition |
|---|---|---|---|
| 1 | critical | A.4's false-RED screen is informationless because IRR-001's rename makes every test red against HEAD | **revised** — renamed-only control; Phase 1 exit criterion 2 |
| 2 | critical | AC-001 is satisfied by the retired implementation, so "both violated by construction" is false | **revised** — sensitivity half added; AC-002 generator pinned to an `observed: missed` objective |
| 3 | critical | `SPEC-intent-layer-ops` AC-002 is invalidated by Phase 1 and was in no ADR or phase | **revised** — ADR-002 and Phase 2 extended; retired test names forbidden |
| 4 | critical | No phase binds the new SPEC's ACs, and the stated reason is refuted by `HASH_DENYLIST_AC` | **revised** — Contract Boundaries corrected; wrapup Step 3.5 named as owner; Phase 2 exit criterion 2 |
| 5 | warning | AC-007 and AC-009 have no owning phase or test file | **revised** — assigned to `test_render_intent_layer.py` and a new `test_withdrawal_succession.py`, both in Phase 3 scope and exit |
| 6 | warning | The `not_filled_in` guard's precedence is unstated; AC-005's preconditions are missing | **revised** — precedence table and fixture preconditions added to Technical Design |
| 7 | warning | The never-signalled `filled_at` fallback has no AC and no named test | **revised** — named test in Testing Strategy and Phase 1 exit criterion 3 |
| 8 | warning | Phase 3 scope names a nonexistent path and omits the wiki entry holding the retired contract | **revised** — `tests/e2e/sandbox*/` removed (verified absent); `.claude/memory/wiki.md` added; "four prose sites" corrected to five |
| 9 | warning | No clock-skew policy on the new cutoff | **revised** — ADR-006, after a follow-up round; the backdated mirror case is an accepted risk |
| 10 | suggestion | Phase 3's golden exit does not prove the re-capture absorbed only the intended change | **revised** — the only-moved-command verification is now exit criterion 2 |

Nine of the ten were corrections of demonstrable errors in the draft rather than choices, so
they were applied directly; only #9 had two defensible answers and went to a follow-up round.
The revision rewrote **47.3%** of the document (`review_churn measure`, refs
`…-plan-p1-pre` → `…-plan-p1-post`) — just under the 0.5 staleness threshold, so none of the
findings were queued against a document that no longer existed.

Ledger: `wcw-e5dfb2f3-202609200506`, `plan-validator`, pass 1, terminal, barrier 1,
`MAJOR_REVISION`, 419.9 s. `stage_agent_ledger coherence` reports this run `OK`.

**Three of the validator's claims were independently re-verified before acceptance**, because
a reviewer that is right nine times is not thereby right the tenth: `tests/e2e/sandbox*/` does
not exist in this worktree (`git ls-files tests/e2e/` lists only `.py` modules — the earlier
sighting was untracked run output in the base checkout); `HASH_DENYLIST_AC` does contain
`test_ids` and `pending_test` (`spec_machine.py:1516-1523`); and `SPEC-intent-layer-ops`
AC-002 is `pending_test: false` with a predicate asserting the removed key set
(`machine.yaml:50-61`).

**Cross-model second opinion — `codex`, status `invoked`** (5 findings, reconciled by the
validator): `883675f8` accepted (guard precedence, folded into #6); `db64b48c` accepted (clock
skew, folded into #9); `30ed0b83` accepted and **promoted** P2 → critical (#2); `ab99f0b2`
**rejected** — the new SPEC's AC-006 golden table is already authored and stamped, so Phase 1's
dependency is satisfied at Phase 1 start, though the ordering hazard it gestured at is real in
a different AC and became #3; `d90327d8` accepted in substance with its premise corrected
(Phase 2 already `depends_on: [1]`, so behavioural completeness is gated — the real hole was
that nothing cross-validated the delivered SPEC at all) (#4).

Codex's distinctive contribution was #2: two of this repository's own reviewers would have had
to notice that the retired implementation reads no timestamp at all, which is what makes the
invariance property vacuous against it.
