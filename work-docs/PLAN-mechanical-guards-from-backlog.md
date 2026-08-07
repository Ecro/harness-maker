---
type: plan
task_slug: mechanical-guards-from-backlog
status: complete
created: 2026-08-07
tags: [harness-maker, plan, python, testing, guards, backlog]
summary: "Convert the four highest-yield pending proposals into mechanical guards — the escalation pipeline's missing last step"
---

# PLAN — mechanical guards from the proposal backlog

## 🎯 Executive Summary

**TL;DR.** `.claude/memory/pending-proposals.md` holds **17 proposals, the oldest from
2026-05-10**. Every `count >= 3` failure already carries one. The escalation machinery
detects recurrence correctly and writes the recommendation — and **nothing consumes it**.
This PLAN closes that last step for the four proposals with the highest incident count and
the lowest implementation cost.

**Why these four.** Each is a single test/lint file, adds **no runtime behaviour**, and
targets a failure class that prose has already failed to prevent — repeatedly, and in the
last two cases *by an author who knew the rule*.

| Guard | Failure it closes | count | Prose attempts that failed |
|---|---|---|---|
| G1 machine-specific path in a committed golden | `snapshot-regen-inside-worktree` | **13** | 3 proposals (count 3, 5, 11), none shipped |
| G2 mutation receipt per new gate | `assertion-invariant-over-named-dimension` | **8** | 5 |
| G3 dead string pin lint | `test-pins-retired-implementation-name` | **4** | 2 (both recurrences by someone who knew) |
| G4 shipped CLI surface driven as shipped | `shipped-entry-point-not-exercised` | **4** | — |

**Non-goal.** Not clearing the backlog. Thirteen proposals stay; three of them are stale
and Phase 5 retires those explicitly rather than leaving the list untrustworthy at a glance,
which is itself part of why it goes unconsumed.

## 📚 Prior Work

- **`[fail:test] snapshot-regen-inside-worktree` (count:13)** — the entry itself names the
  gate it has never had: *"asserting no `/home|/Users|/root` path survives … It checks the
  PROPERTY (no machine-specific absolute path) rather than the SYMPTOM (no `.worktrees`)."*
  G1 is that sentence, implemented. The original mechanism is already closed by the
  `regenerate.py` / `tests/render/conftest.py` pins — the count kept climbing because **new**
  artifacts did not inherit them, which is precisely why the guard must derive its population.
- **`[fail:test] assertion-invariant-over-named-dimension` (count:8)** — prevention recorded
  five times as prose: *"name the specific wrong implementation it is meant to reject and
  check the assertion actually fails against it."* Never mechanised.
- **`[fail:test] gate-scoped-to-the-artifact-being-fixed` (count:3)** and *"a new gate must
  state its population, and a test must prove the population is complete"* — binding on this
  PLAN's own guards: each must derive its subject set, and carry a non-vacuity assertion.
- **`[fail:test] fix-introduced-defect-passes-all-gates` (count:5)** — three of four rounds in
  the immediately preceding task each shipped a defect worse than the one fixed, every time
  on a green suite. Every phase below therefore ends by **injecting the violation and watching
  the guard fail**, not by observing a green suite.

## 📐 Architecture Decision Records

### ADR-001: Every guard derives its population; none enumerates it
**Status:** Accepted (2026-08-07)
**Context:** `gate-scoped-to-the-artifact-being-fixed` is at count:3 — a guard written while
fixing one artifact gets scoped to that artifact and the same defect survives elsewhere. The
snapshot family is the proof: the pins existed, a NEW test directory did not inherit them,
and the count went 11 → 13.
**Decision:** Each guard globs its subjects from the repo (committed fixture-shaped files,
all `tests/**` modules, all registered CLI subcommands) and asserts the discovered set is
non-empty. No hand-written list of files.
**Consequences:** ✅ a new artifact is covered the moment it exists. ⚠️ a glob can drift into
over-matching; each phase pins the expected population size loosely (non-empty + a named
member) rather than exactly, so adding an artifact does not fail the guard spuriously.

### ADR-002: A guard ships only with a demonstrated failure
**Status:** Accepted (2026-08-07)
**Context:** `assertion-invariant-over-named-dimension` (count:8) and
`fix-introduced-defect-passes-all-gates` (count:5) are both "green for the wrong reason".
A guard that has never been observed to fail is indistinguishable from one that cannot.
**Decision:** Each phase's exit criterion includes injecting a real violation into a temp
copy and asserting the guard reports it. Where the guard is a pytest meta-test, this is a
test case in the same file (a synthetic-source negative + a positive control), not a manual
step — the manual version is what has failed five times.
**Consequences:** ✅ every guard is falsifiable at the moment it lands. ⚠️ each guard file
grows a small fixture surface; accepted, it is the whole point.

### ADR-003: G2 is a receipt, not an automated prover
**Status:** Accepted (2026-08-07)
**Context:** "does this assertion reject the wrong implementation?" is not mechanically
decidable in general — a real mutation run over every test is far beyond this PLAN.
**Decision:** G2 mechanises the *obligation*, not the *proof*: a `hm mutation_receipt` CLI
that records, per new/changed gate, the source locator to delete and the test node that dies.
The review stage requires the receipt; a missing one is visible rather than assumed.
**Consequences:** ✅ cheap, deterministic, and it makes the absent case loud — which is the
failure mode (five silent misses). ⚠️ a dishonest receipt is still possible; this raises the
cost of skipping, it does not make skipping impossible. Recorded as an accepted limit, not
sold as a proof.
**Rejected:** wiring `mutmut` over the whole suite — the repo already gates T1 mutation on
machine-SPEC paths only, deliberately, for runtime reasons.

## 🚫 Non-Goals

- Clearing the remaining 13 proposals.
- Any runtime behaviour change. Every phase is test/lint/CLI-receipt only.
- Re-opening the multisession-marker-scoping P1 (a separate PLAN owns that).

## 📝 Implementation Plan

### Phase 1 — G1: no machine-specific absolute path in a committed golden
- `depends_on`: []
- **Scope (in):** `tests/structural/test_no_golden_bakes_a_machine_path.py`. Population
  DERIVED: every committed file under `tests/**` matching a fixture shape
  (`*.expected.yaml`, `*baseline*.json`, `tests/render/**` goldens if any return). Assert
  no `/home/`, `/Users/`, `/root/` survives, and that the portable `$HOME` form is what
  appears instead where a path is expected.
- **Exit criterion:** full `uv run pytest tests/ -q` green **plus** an in-file negative
  control that injects `/home/someone/x` into a temp copy and asserts the checker reports it,
  and a non-vacuity assertion that the discovered population is non-empty and contains
  `tests/snapshot/prod-firmware-spec.expected.yaml`.
- **Risk:** low. **Rollback:** delete the file.

### Phase 2 — G3: dead string pin lint
- `depends_on`: []
- **Scope (in):** `tests/structural/test_no_dead_string_pins.py`. Two rules over all
  `tests/**/*.py` (AST, not regex): (a) `assert "<lit>" not in <x>` where `<lit>` occurs
  nowhere in `src/` — a pin that cannot fail; (b) any string literal matching `^\d+\. ` —
  a step number, which is prose, never a contract.
- **Scope (out):** positive pins generally — rule (b) is the narrow, evidenced subset.
- **Exit criterion:** full suite green **plus** synthetic-source cases proving each rule
  fires, plus a negative control (a live negative pin, and a non-step-numbered literal) that
  must NOT fire. Existing offenders: fix them, or record each with a one-line justification —
  do not weaken the rule to accommodate them.
- **Risk:** medium — rule (b) may over-match. **Rollback:** delete the file.

### Phase 3 — G4: every shipped CLI surface is driven in its shipped form
- `depends_on`: []
- **Scope (in):** `tests/structural/test_cli_surfaces_are_driven.py`. Enumerate subcommands
  from the registry/Typer app (DERIVED — 30 today), and assert each has ≥1 test invoking it
  as a **subprocess** in its shipped spelling. Allowlist entries need an inline reason.
- **Exit criterion:** full suite green; the enumeration is non-empty and ≥25; every
  allowlisted subcommand carries a reason string.
- **Risk:** medium — likely surfaces real uncovered subcommands. Those are findings, not
  blockers: record them in the allowlist with reasons in this phase, close them in a
  follow-up PLAN.
- **Rollback:** delete the file.

### Phase 4 — G2: mutation receipt per new gate
- `depends_on`: [1, 2, 3]  *(the three guards above are its first real subjects — writing it
  last means it is exercised by them rather than asserted in the abstract)*
- **Scope (in):** `hm mutation_receipt record --gate <test-node> --deletes <src-locator>`
  appending to `.claude/observability/mutation-receipts.jsonl`; a review-stage prose line
  requiring one per new gate; a receipt for each of G1/G3/G4.
- **Exit criterion:** full suite green; three receipts on disk, one per guard, each naming a
  real source locator and a real test node.
- **Risk:** low. **Rollback:** revert; the three guards stand alone.

### Phase 5 — Retire the stale proposals
- `depends_on`: [1]
- **Scope (in):** remove the three superseded `snapshot-regen-*` proposals and the RETIRE
  entry from `pending-proposals.md`, replacing them with one line pointing at G1; mark
  `health-check-no-concrete-id` and `orphan-worktree-prune-on-create` as shipped.
- **Exit criterion:** `pending-proposals.md` contains no proposal whose mechanism is already
  in the tree.
- **Risk:** low. **Rollback:** revert.

## 🧪 Testing Strategy

- **Every guard is its own subject.** Each guard file contains its synthetic-source negatives
  AND a positive control, so "the rule fires" and "the rule does not fire on clean input" are
  both pinned. A guard with only negatives passes on a matcher that flags everything.
- **Population non-vacuity.** Each guard asserts its discovered subject set is non-empty and
  names one known member. A discovery test that discovers nothing is a green light over a
  blind spot.
- **No manual mutation step.** ADR-002's demonstration is in-file, because the manual version
  is the thing that failed five times.

## ⚠️ Risks & Mitigation

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| A guard over-matches and blocks honest work | Medium | Medium | Negative controls in every guard; allowlists carry reasons, not bare entries |
| G3 rule (b) fires on legitimate prose assertions | Medium | Low | Narrow to leading step numbers only; existing offenders get a justification line each |
| G4 surfaces many uncovered subcommands at once | High | Low | Allowlist-with-reason in this phase; closing them is a follow-up, not a blocker |
| These guards become the next "green for the wrong reason" | Medium | High | ADR-002 — no guard lands without a demonstrated failure |

## ✅ Success Criteria

- [x] A committed golden containing `/home/<user>/…` fails the suite. **Also** the
      post-portablize `$HOME/…/.worktrees/<slug>` form, which the first cut was blind to —
      `synthesize._portablize_ref` normalises away every discriminator except `.worktrees`,
      so the guard was largely vacuous over the very failure it quotes as its spec.
- [x] **NOT MET — the rule was refuted, deliberately.** "A negative string pin on a literal
      absent from `src/` fails the suite" was implemented, run against the tree, and
      **rejected**: 19 legitimate anti-regression guards flagged against 1 true instance.
      `assert "workflows:" not in rendered` exists precisely to keep a retired axis retired,
      and its literal being absent from `src/` is the correct state. The reasoning is
      recorded in `test_no_dead_string_pins.py` rather than deleted, so it is not proposed a
      fourth time. Checked off as *resolved*, not as *delivered* — the criterion was wrong.
- [x] A new `hm` subcommand with no subprocess test fails the suite (or is allowlisted with
      a reason **that a machine re-checks** — three rounds of hand-written reasons produced
      three rounds of false ones).
- [x] Each of G1/G3/G4 has a mutation receipt naming the line to delete and the test that
      dies — earned by deleting the line and observing an **assertion** failure; a collection
      error was rejected as proof. Plus the consumer that makes the receipt mandatory, and
      two gates that landed concurrently on main.
- [x] `pending-proposals.md` holds no proposal already implemented in the tree (17 → 10).
- [x] Every guard has both a firing case and a non-firing case in its own file.
