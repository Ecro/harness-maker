---
type: spec
task_slug: token-efficiency-autopilot-ux-speed
status: draft
created: 2026-09-08
tags: [harness-maker, spec, python, observability, parity, autopilot, token-economy]
test_framework: pytest
tier: 2
research_doc: "[[RESEARCH-token-efficiency-autopilot-ux-speed]]"
summary: "Restore the evidence layer, and stop shipping prose that describes behaviour the runtime does not perform"
---

# SPEC — evidence layer + prose/runtime parity

## 🎯 Intent

Two defects discovered together while researching four axes the user named — token
efficiency, autopilot completeness, user comprehension, and workflow wall-clock:

1. **harness-maker's self-measurement layer holds zero rows.** `auto-advance.jsonl`,
   `stage-agents.jsonl`, `second-opinion.jsonl` and `delegation.jsonl` are all absent;
   `stage-spans.jsonl` holds one `start` with no `end`. `.gitignore:73` excludes
   `.claude/observability/*`, so the project commits its narrative and discards its
   measurements. CLAUDE.md forbids hand-calculating these figures and directs the reader
   to the shipped CLI — which answers `no rows … This is not a clean bill of health; it is
   an absence of evidence.` Every optimization on all four axes would therefore be made
   blind, and the single largest un-taken token win (**≈$390 of $697**) has sat
   pre-registered and unrun for a month because it needs n≥8 runs per arm that nothing
   would record.

2. **Fifteen shipped surfaces describe behaviour the runtime does not perform.** A guard
   with zero producers ships 24,884 chars into every non-Codex harness including `gated`
   ones, where it can only emit `kill_switch`. `run_in_background` occurs nowhere, so
   ADR-011's concurrency hoist is unenforceable prose worth up to 300 s per review.
   CLAUDE.md recommends an escape hatch — shrinking `reviewers.enabled` — that
   `lens_dispatch(preset)` cannot honour, because the list is **not an input** to the
   dispatch table at all: narrowing it changes nothing the model is told to invoke.
   (An earlier draft of this SPEC said the rendered review *dispatches reviewers absent
   from that list*. **That was false** and A.5 round 1 refuted it: `interview()` always
   writes `_PROD_ENABLED_REVIEWERS`, which contains every dispatched agent, so on a real
   harness the dispatched set is a strict subset. The `[]` behind the original claim came
   from a bare `InterviewAnswers`, a value no producer emits.) README asserts a worktree
   behaviour that is false on the Side default. The personalization-audit message cites the threshold that did *not* fire.

These are one defect class, and CLAUDE.md's own failure tiers already name it
(`[fail:design] runtime-env-gate-dead-on-arrival` count:2,
`[fail:tooling] silent-no-op-patch-reports-success` count:2,
`[wiki:convention] wrong-transparency-table-worse-than-none`). The second half is cheap and
individually verifiable; the first half is what makes any later claim checkable.

## 🌅 Outcomes

After this unit:

- A maintainer can run one command and get per-model, per-stage and per-arm counts that
  **survive a fresh clone**, because the aggregate is written to an already-committed
  deliverable path rather than to the gitignored ledger directory.
- `/hm:health` distinguishes **"stopped correctly"** from **"never fired"** from **"cannot
  fire in this runtime"** — today all three read as the same "possible silent degradation".
- An `advance_authorized` row with no matching `advance_entered` is **reported**. Today it
  is recorded on disk and read by nothing.
- A harness with `autonomy.level: gated` pays **zero** chars for autopilot auto-advance.
- The cross-model second-opinion call **overlaps** the reviewer fan-out in a real run,
  rather than only claiming to.
- **No document in the repo states a configuration default that the producing object
  contradicts** — and a test proves it by inverting the object and watching the assertion
  fail.
- The `EXPERIMENT-session-length-ab` arms become runnable: the harness records what an arm
  did, so 16 runs would produce a verdict instead of nothing.

Explicitly *not* an outcome: any measured token or wall-clock saving. This unit removes dead
surface and restores the instrument. The savings it enables are the next unit's to claim —
see Non-Goals.

## 📏 The measurement this SPEC is built on

Taken 2026-09-08 on this repo, before any change. These are the numbers the ACs bind to.

| Measurement | Value |
|---|---|
| Rendered `.claude/commands/hm/*.md` total | 447,546 chars |
| Autopilot advance blocks, ×7 commands | **24,884 chars** (2,945–5,230 each) |
| Autopilot picker blocks, ×7 commands | 18,067 chars (2,581 each, correctly gated on `level != "gated"`) |
| Session context share held by the slash-command body | **77.1%** of 140,463 chars |
| Round trips per pipeline | 133 (review 39 · plan 26 · wrapup 25) |
| `uv run … hm --help`, warm | 0.04 s ⇒ all subprocess startup ≈6.7 s/pipeline = 0.3–0.6% |
| Ledgers holding ≥1 row | **0 of 4**; `stage-spans.jsonl` = 1 `start`, 0 `end` |
| `hm autopilot_ledger smoke --level auto_safe` | `{"degraded": true, "entry_count": 0}` |
| `hm verifier_discrimination report` | `no rows … an absence of evidence` |
| `lens_dispatch` parameters | `(preset)` — no `enabled` |
| Rendered `review.md` dispatches | `code-reviewer`×8, `test-reviewer`×2, `security-reviewer`×2, `concurrency-reviewer`×2 |
| `run_in_background` occurrences in templates + rendered commands | **0** |
| `autopilot_advance_enabled` producers | **0** (`workflow_fuse.py` deleted) |
| `Task(subagent_type=` in rendered `research.md` | **0** (gated off by `"cursor" not in config.targets`) |

Two of these constrain what may be proposed. **Subprocess count is not the problem** —
6.7 s per pipeline forecloses any "reduce shell-outs" direction. And **every one of the ten
largest config gates in this repo is ON**, so 447,546 is near the worst case; a default
third-party install is materially cheaper.

## 📋 In-Scope Scenarios

### S1: a gated harness pays nothing for auto-advance
**Given** a harness rendered with `autonomy.level: gated`
**When** the stage commands are rendered
**Then** no command contains an `autopilot_caps boundary` invocation
**And** the dead `autopilot_advance_enabled` name appears nowhere in the sources

### S2: the cross-model call overlaps the reviewer fan-out
**Given** `second_opinion.models` is non-empty and a real `/hm:review` runs
**When** Pass 1's reviewer fan-out is dispatched
**Then** the second-opinion invocation is already in flight, not queued behind it

### S3: a document cannot state a default the producing object contradicts
**Given** a document that discloses a configuration default
**When** the default is inverted in the class that produces it
**Then** the assertion guarding that document fails

### S4: README's worktree claim is true on both arms
**Given** `worktree.enabled` set to `true`, then to `false`
**When** README's worktree sentence is evaluated against `worktree_enabled(base)`
**Then** it holds in both cases, naming the persistent per-task worktree rather than a fresh one

### S5: the audit message names the branch that fired
**Given** an override count below its threshold but a days-since-audit above its own
**When** the personalization-audit advisory is emitted
**Then** the message cites the **days** threshold, not the count threshold

### S6: a rendered config names nothing that does not exist
**Given** a rendered `harness.yaml`
**When** each name in `skills.enabled` and `reviewers.enabled` is resolved against the actual inventory
**Then** every one of them resolves to an existing asset
**And** no shipped doc section survives whose body refutes its own heading

### S7: an enabled feature with an unreachable backend says so
**Given** `second_brain.enabled: true` and a `vault_path` that does not resolve
**When** `/hm:health` runs
**Then** it reports a standing condition naming the unreachable vault

### S8: measurements survive a fresh clone
**Given** ledger rows written on one machine
**When** a roll-up is emitted and the repo is cloned elsewhere
**Then** the per-model and per-stage aggregates are readable in the clone

### S9: an authorized-but-never-entered advance is reported
**Given** an `advance_authorized` row with no matching `advance_entered`
**When** the autopilot report runs
**Then** that dangling authorization is listed

### S10: a runtime that cannot advance is not called degraded
**Given** a harness whose `targets` omit `claude-code`
**When** the autopilot smoke check runs
**Then** it reports not-applicable rather than "configured yet never fired"

### S12: a rendered command does not contradict its own generated table
**Given** the rendered `review.md`, whose lens-dispatch table is generated from `lens_dispatch(preset)`
**When** its prose instruction about which reviewer set to start from is compared against that table
**Then** the two agree, or the instruction is gone

### S11: an unwired component is either wired or recorded as intentional
**Given** a component with no production caller (`context_lint.lint`, `consensus-arbiter`, `verify` delegation)
**When** the structural gates run
**Then** each one either has a production call site or a gate asserting its absence is intentional

## 🚫 Non-Goals

- **Approach C — proportionality / an auto-triaged light path.** Deferred to a follow-up
  PLAN by explicit decision. It is the highest user-noticed wall-clock win and the largest
  design surface, and the data that would justify a triage rule is what this unit
  produces. Designing it now would be routing without evidence, against
  `lens_coverage.blocks_approval`.
- **Running the `EXPERIMENT-session-length-ab` arms.** This unit makes them *recordable*;
  the 16 pipeline runs are a schedule decision and a separate unit.
- **Making `reviewers.enabled` narrow the lens fan-out.** Locked the other way: the prose
  moves. On Production `routable_lenses` is empty, so there is nothing to narrow, and a
  missing mandatory lens makes every review unapprovable.
- **Any further surface-reduction pass.** The one large win is taken (−530,222 chars /
  −45.2%). 67.7% of `review.md` is unconditional-or-target-gated; prior passes netted
  +0.75% and +4,627 chars.
- **Compressing CLAUDE.md, or splitting it via `@import`.** Prior-rejected with a measured
  bound: the ceiling is ~4% of total spend, "the honest size of this win", and the two
  largest blocks are already relocated to `docs/`.
- **Making `second_opinion` opt-in.** Prior-rejected: the largest single saving available,
  refused because a cross-model voter caught a P0 two Claude reviewers missed.
- **Changing the 7-lens mandatory set, `max_review_rounds`, the second `plan-validator`
  pass, execute Phase A.5, the review Confirmation Pass, or the two-pass redaction.** Each
  prior-rejected with a recorded reason (RESEARCH §Pitfalls).
- **Committing the raw ledgers, or un-ignoring `.claude/observability/`.** Locked: the
  roll-up goes to `work-docs/`. `.claude/observability/` is listed in
  `worktree._HARNESS_CHURN_DIRS` (`worktree.py:109-117`), which both the finalize
  dirt-filter and the create-guard read; creating a committed path beneath it would perturb
  the 5-layer defense's dirt classification. (The symbol is `_HARNESS_CHURN_DIRS`, not
  `_HARNESS_CHURN_PREFIXES` — the latter appears in CLAUDE.md and does not exist in the
  source. The sibling names are `_HARNESS_CHURN_FILES`, `_HARNESS_CHURN_GLOBS` and
  `_HARNESS_ARTIFACT_PREFIXES`.) **Accepted limitation, inherited:** neither dirt-filter
  covers a non-default `work_docs.dir` (`worktree.py:122-126`, `:164-166`), so the
  roll-up's staging guarantee is scoped to the default directory.
- **Restoring `research.md`'s three-way `Explore` fan-out.** Real work, not a flag flip —
  it needs a Cursor-specific command render, and `.cursor/commands/` does not exist because
  Cursor reads the shared `.claude/` file. Recorded as a finding; out of scope here.
- **Fixing this machine's `second_brain.vault_path`.** Not a code change. Only the standing
  loud condition (S7) is plannable.
- **Any GitHub/Linear/CI-log integration.** The RESEARCH product lens named these as the
  top missing connections; they are new capability, not parity.

## ⚙️ Constraints

| Constraint | Value | Rationale |
|---|---|---|
| Test framework | `pytest` | CLAUDE.md fixes the toolchain; `uv run pytest -q {path}` is the declared command |
| Language | Python 3.12+, no Bash | CLAUDE.md: Python only, hooks call `python -m harness_maker.<module>` |
| Types / lint | `mypy --strict`, `ruff check` + `ruff format` | project gates; tests are annotated (commit `85b1216c`) |
| Roll-up destination | `work-docs/BASELINE-ledger-rollup.md` | must reuse an existing `DELIVERABLE_PREFIXES` entry (`worktree.py:170-194`), because `.gitignore:104` is `work-docs/*` followed by an explicit negation allowlist, and that twelve-prefix set has three consumers a test asserts equal. A new prefix would mean editing all three; `BASELINE-` is already in the set, so no consumer moves. Note `derive_deliverable_globs` (`wrapup_land.py:257`) yields `work-docs/BASELINE-*{slug}*.md`, which is precisely why a slug-less filename needs the explicit `--optional` entry rather than relying on the derived glob |
| Roll-up staging | named in `wrapup_land`'s typed manifest as `--optional` | the `worktree-sweep` row that would otherwise catch it records `skipped-not-isolated` when `--worktree` IS `--base`, so a `worktree.enabled: false` harness would write the roll-up and never commit it — the exact loss this SPEC exists to end |
| Ledger raw files | stay gitignored | locked decision; durability comes from the roll-up, not from un-ignoring |
| Aggregation semantics | per-model `(skipped + failed) / total` over **invocation rows only** (`finding_ref == "n/a"`), `stage: "health"` excluded, `.ledger-exclusions.json` applied, composed from the shipped reader rather than re-derived | Three recorded mis-measurements, all reachable here. `finding_ref` is the **sole** discriminator between per-invocation and per-finding-disposition rows (both carry `status: "invoked"`), so aggregating without it counts one invocation per finding and silently inflates the denominator. Hand-aggregating without the exclusions file reported 61.3% where the shipped reader reported 2.15% (30×). An earlier `skipped/total` reported 10.3% where the truth was 20.7%, with one model's entire loss in `failed` rows — so `failed` must not be dropped and models must not be merged |
| Surface budget | no ceiling may be raised to pass a phase | `PLAN-workflow-step-audit` ADR-011; removals must be listed in `_ALLOWED_REMOVALS` per cutting phase, keyed `<command>@<dev_mode>` |
| Doc assertions | bound to the object that produces the value | `[wiki:convention] wrong-transparency-table-worse-than-none`; a grep for presence is satisfied by inverted content |
| Behavioural contracts | proven by one real dispatch | `[wiki:architecture] narrative-output-needs-explicit-envelope`: fixture-shaped output proves the validator, never the producer |
| Determinism | render must never shell out | ADR-007 of the second-opinion work; render-time live probes are forbidden |

## ⚠️ Accepted Risks

| # | Risk | Mitigation |
|---|---|---|
| R1 | Deleting the advance block from `gated` renders is a **removal**, and the character floor (`measured × 0.80`) cannot see a single deleted instruction. | Every removal goes in `_ALLOWED_REMOVALS` keyed to this phase and to the exact `<command>@<dev_mode>`, and the allowlist's staleness check must stay green. |
| R2 | AC-006 needs a live `/hm:review`, which costs a real cross-model call and is non-deterministic. | It is the only oracle that counts here (Constraints); the render-grep half is kept as a *cheap precondition*, never as the proof. Treat a green grep with a red dispatch as the expected failure mode. |
| R3 | The roll-up is a new committed artifact, so wrapup must stage it or it silently never lands — and the `worktree-sweep` that would catch an unnamed file records `skipped-not-isolated` when the worktree IS the base. | AC-001 asserts the path is in `git ls-tree` at HEAD and that `git check-ignore --no-index` prints nothing, **not** that a clone contains it (`git clone` transfers commits, never index state). Plus the explicit `--optional` entry in `wrapup_land`'s typed manifest, which is what makes it land at `worktree.enabled: false`. |
| R4 | Target-aware smoke could mask a genuine Claude-Code degradation if the `targets` read is wrong. | The N-A branch fires only when `claude-code` is absent from `targets`; a harness that includes it keeps today's behaviour exactly. |
| R5 | AC-007 is a property over documents; an over-broad predicate would fail on prose that merely mentions a config name. | The property is scoped to *disclosed defaults* — a claim of the form "the default is X" — not to any mention. A false positive here is loud, not silent. |
| R6 | Retracting CLAUDE.md's `reviewers.enabled` recommendation removes the only escape hatch offered for the language-conditional fan-out cost, leaving no user lever. | Stated as a known consequence in the retraction itself, pointing at the deferred Approach C as where a real lever would come from. |

## ✅ Verification Criteria

| Scenario | AC | Mode | Oracle |
|---|---|---|---|
| S1 | AC-005 | unit | differential (two render arms) |
| S2 | AC-006 | integration | differential (live run vs sequential baseline) |
| S3 | AC-007 | unit | property (inversion) |
| S4 | AC-008 | unit | golden (both arms) |
| S5 | AC-009 | unit | golden (three branch states) |
| S6 | AC-010, AC-011 | unit | property / golden |
| S7 | AC-012 | unit | golden |
| S8 | AC-001 | unit | golden (hand-computed fixture) |
| S9 | AC-002 | unit | golden |
| S10 | AC-003 | unit | golden (target-set table) |
| S11 | AC-014 | unit | property |
| S12 | AC-015 | unit | differential (one artifact, two halves) |
| all readers | AC-004 | unit | property |
| S1, S6 | AC-013 | unit | differential (models-off vs models-on render) |

### AC-001: the roll-up carries hand-checkable counts and survives a clone

A fixture ledger is aggregated to **per-model and per-stage** counts, written to
`work-docs/BASELINE-ledger-rollup.md`, committed, and then read back from a **fresh clone**.

**The per-arm axis is deferred, explicitly.** An earlier draft of this AC named
"per-model, per-stage and per-arm"; plan validation caught that no ledger carries an `arm`
field, so the axis was unassertable and would have shipped named-but-untested — the exact
defect this SPEC exists to remove. "Arm" means an `EXPERIMENT-session-length-ab` arm, and
recording it requires the experiment to be running, which interview round 4 put in a
**separate unit**. When that unit lands it adds the axis and its own AC.
The fixture must contain, at minimum: rows for two models where merging them changes the
answer; at least one `failed` row whose omission changes the answer; **at least one
disposition row (`finding_ref != "n/a"`) whose mis-counting as an invocation changes the
answer**; and at least one row named by `.ledger-exclusions.json`. Independence: every
expected number is computed by hand from the fixture file, never by a second call to the
aggregator, and each of the four mis-aggregations produces a *different* number — three are
mistakes CLAUDE.md records as having shipped.

**The clone check proves committing, not staging** — `git clone` transfers commits and never
index state, so the criterion is discharged by `git ls-tree -r HEAD --name-only` containing
the path plus `git check-ignore -v --no-index <path>` printing nothing, not by cloning a
dirty checkout. `check-ignore` needs `--no-index` because it answers "not ignored" for an
already-tracked path.

**The document-content claim is discharged by a per-axis render differential, not by asserting
values in the text.** Recorded here so the deviation is auditable: Phase A.5's round-2 reviewer
named a different accepted form (scope each number to the line carrying its label, match on token
boundaries). That form was not taken, because it pins a layout on a `render_rollup` that did not
exist yet — where codex's counts must share one line, and the total must sit on a line naming it —
which is a design constraint no round reviewed. The differential instead perturbs one aggregate
axis at a time, holding the total fixed, and requires the rendered document's numeric multiset to
move; a date's digits cancel because they appear identically on both sides. It is the pattern the
same reviewer **cleared** in this file for `test_ac_001_each_misaggregation_changes_the_answer`,
and the pattern ADR-005 and `[wiki:convention] wrong-transparency-table-worse-than-none` name as
this project's remedy for "the assertion is weaker than the claim". The A.5 budget was spent, so
this deviation was applied without a third round — see the PLAN's Phase 1 note.

Tests: `tests/unit/test_autopilot_ledger_rollup.py::test_ac_001_rollup_counts_are_hand_checkable`,
`::test_ac_001_each_misaggregation_changes_the_answer`,
`::test_ac_001_the_rollup_path_is_the_named_deliverable`,
`::test_ac_001_the_document_is_a_function_of_every_aggregate_axis`,
`::test_ac_001_the_rollup_reads_the_base_repo_not_the_worktree` (added during review, after the
first real run wrote `No rows.` into the deliverable from inside a task worktree while the base held
`second-opinion.jsonl`, `auto-advance.jsonl`, `stage-agents.jsonl` and `stage-spans.jsonl` — the
reader must resolve the base root the way the writers already do, and this AC's outcome is
"survives a fresh clone", which a worktree-local read cannot deliver),
`::test_the_rollup_path_is_named_in_wrapup_lands_manifest`,
`::test_ac_001_the_rendered_wrapup_produces_the_rollup_before_staging_it` (review finding P1-4: the
manifest named the path and **nothing wrote it**, so the "survives a clone" outcome was unreachable
in the shipped workflow — a manifest entry for a file no template generates is AC-014's defect
wearing AC-001's clothes),
and `tests/unit/test_ledger_exclusions_call_sites.py::test_the_rollup_seam_applies_exclusions` —
the third seam in the call-sites registry. That file's own docstring states why the registry
exists ("a correct helper wired to nothing is the defect, not the fix"), and `rollup` is a second
consumer of the same ledger family, so it could have filtered nothing with every existing test
green. AC-001 claims it here because AC-001 owns the aggregation contract.

### AC-002: a dangling authorization is reported

Given a ledger holding one `advance_authorized` row and no matching `advance_entered`,
the autopilot report lists exactly that one row. Independence: the fixture is
hand-authored to contain the asymmetry; `find_unconfirmed_authorization` already computes
it and today has exactly one caller, so the AC is about the *reader*, and a report that
returns nothing on this fixture is the current behaviour.

Tests: `tests/unit/test_autopilot_ledger_rollup.py::test_ac_002_a_lifetime_window_reports_every_dangling_authorization`
(review finding P1-2: the enumeration reused a session-window collapse that banks at most ONE
outstanding authorization per stage, so any later successful advance to that stage erased an
earlier dangling one and the section printed `- none` for a real defect),
`tests/unit/test_autopilot_ledger_rollup.py::test_ac_002_a_dangling_authorization_is_reported`,
`tests/unit/test_autopilot_ledger_rollup.py::test_ac_002_a_fully_confirmed_ledger_reports_nothing`.

### AC-003: the smoke check is not-applicable when the runtime cannot advance

Parametrized over target sets: `[claude-code]`, `[cursor]`, `[codex]`,
`[claude-code, cursor]`, `[cursor, codex]`. Only sets containing `claude-code` may report
degradation; the others must report not-applicable. Independence: the golden table is
derived from the documented capability rule (auto-advance needs Claude Code's `Skill`
tool), not from the function's own output.

Tests: `tests/unit/test_health_evidence_surface.py::test_ac_003_the_rendered_health_passes_targets_to_the_smoke_verb` (review finding
P1-3: the applicability rule had **no production caller** — the rendered `/hm:health` passed only
`--root`/`--level`, so `targets=None` kept `applicable` True and the permanent false alarm on a
cursor-only harness shipped unchanged while the unit test saw the fix),
`tests/unit/test_health_evidence_surface.py::test_ac_003_smoke_is_not_applicable_when_the_runtime_cannot_advance`,
and `tests/unit/test_autopilot_ledger_health.py::test_smoke_cli_emits_json` — a pre-existing
`set(out) == {...}  # full surface locked` assertion that AC-003 legitimately widens by one key.
The lock is claimed here rather than quietly edited: its whole purpose is to make adding a field a
conscious act, so the AC that adds one owns the change.

### AC-004: absence of evidence is never reported as health

For every ledger reader, the report produced from an empty ledger must be distinguishable
from the report produced from a healthy non-empty ledger, and must not be classifiable as
passing. Independence: a metamorphic relation over any reader — it holds regardless of how
a given reader is implemented, so it cannot be satisfied by reading the implementation.

**The reader set is enumerated, with a positive control** rather than derived from an import
edge. Plan validation flagged that no edge exists: the writers are not the readers, and the one
candidate edge ("imports `ledger_exclusions`") is circular against the very omission ADR-010
warns about — a reader that forgot the import is the one the derivation would not find. The
control instead makes an addition loud, and it needs **two discovery arms** because the family
has two shapes. Phase 2 A.5 caught the first draft with only one: keying on a parameter named
`observability_dir` is blind to `verifier_discrimination`'s `report` verb, which lives inside
`main(argv)` and is keyed on `--ledger` — and that verb is the emitter of the very sentence this
AC's `oracle_evidence` quotes as proof the shape is achievable. So the control scans (a) library
callables by signature, accepting `observability_dir` / `ledger` / `path`, and (b) **CLI verbs
declared in `command_registry.MODULES`**, which is a real mechanical source of the names a
signature scan cannot reach. Every name from either arm must be classified.

**The property's domain includes the CLI report verb**, and its exit code is not part of the
relation — see the corrected `preconditions` in the machine SPEC.

Tests: `tests/unit/test_health_evidence_surface.py::test_ac_004_absence_is_never_reported_as_health`,
`tests/unit/test_health_evidence_surface.py::test_ac_004_the_reader_enumeration_is_complete`.

### AC-005: a gated harness renders no auto-advance surface

Render the same answers twice, changing only `autonomy.level` between `auto_safe` and
`gated`. The gated arm contains zero `autopilot_caps boundary` invocations across all
commands; the difference between the arms accounts for the advance blocks; and the name
`autopilot_advance_enabled` appears in no source file. Independence: differential against
the other render arm, so the expected delta is produced by a second configuration rather
than asserted as a literal — a char pin would break on any unrelated edit.

**The gated arm is guarded by a dedicated byte-level test, not by extending
`_instruction_baseline.AXES`.** Plan validation established that `AXES` is `tuple[DevMode, ...]`
and `entry_key` is `command@dev_mode.value`, so an `autonomy.level` member fails `mypy --strict`,
has no `.value`, and would force a second axis plus a new key grammar — colliding with the
`<command>@<dev_mode>` grammar this PLAN's own Contract Boundary pins, and dragging
`_SCHEMA_VERSION` 2→3 and a doubled baseline behind it. The carried risk named the alternative
("find a different guard for the gated arm") and this is it.

Two consequences worth stating. The pre-change goldens are captured **before** any template edit,
because a snapshot taken afterwards records the over-swallowing instead of flagging it — that is
`ratchet-rebaselined-by-its-own-subject` applied to a byte baseline. And the delta between the
gated and non-gated renders is asserted to be **exactly** the advance blocks, which is this AC's
middle conjunct and the only clause that catches a level gate swallowing more than it should: a
zero-boundary count is satisfied just as well by a gate that also removed a heading or the
sibling `gate-blocked` line.

Tests: `tests/structural/test_autopilot_gate_render.py::test_ac_005_a_gated_harness_renders_no_boundary_invocation`,
`::test_ac_005_the_gated_delta_is_exactly_the_advance_blocks`,
`::test_ac_005_the_dead_guard_name_appears_nowhere`,
`::test_ac_005_the_non_gated_arms_are_byte_identical_to_the_pre_change_golden`,
`::test_ac_005_the_picker_block_is_untouched`.

Also claimed by AC-005, because the dead name lives in them and the third conjunct is not satisfied
until it is gone: `tests/unit/test_autopilot_template_render.py` (the literal-condition assertion,
plus a `_render_partial` `advance_enabled` kwarg and the `ctx[...]` write it feeds — **no caller in
the repo passes that kwarg**, so its survival is silent) and `tests/structural/test_command_size_budget.py`
(a docstring documenting `workflow_fuse.fuse(autopilot_advance_enabled=False)`, for a function that
no longer exists). The `test_command_size_budget.py` hit is a docstring, not an `_ATOMIC_RATCHET`
entry, so fixing it stays inside the Contract Boundary.

**Phase C must edit the condition IN PLACE.** A nested `{% if %}` restructure adds an output newline
to the *armed* arm — `keep_trailing_newline=True, trim_blocks=False, lstrip_blocks=False` — which the
byte golden catches and the delta test does not, because the delta test collapses `\n{3,}` (it must:
removing a whole-line marker pair necessarily leaves a 3-newline run). The two tests are
complementary by construction, and the in-place form is the one both accept.

### AC-006: the cross-model call is in flight before the fan-out completes

In one real `/hm:review` on a non-empty diff with `second_opinion.models` non-empty, the
second-opinion invocation's start precedes the completion of Pass 1's reviewer fan-out.
Independence: differential against the sequential baseline the same run produces without
the wiring. A render-grep for `run_in_background` is a **precondition only** — per
`narrative-output-needs-explicit-envelope`, fixture-shaped output proves the validator and
never the producer, and this is exactly the class where every cheap layer passed while the
behaviour was absent.

> **⚠️ STATUS: MECHANISM LANDED, ORACLE UNVERIFIED — by explicit user decision (2026-09-08).**
>
> Neither `codex` nor `agy` is installed in the environment this unit was implemented in
> (`command -v` for both returns nothing; Phase 1's live `second_opinion_invoke` call returned
> `status: "skipped", reason: "CLI not installed: codex"`). So the one real dispatch this AC's
> oracle requires **cannot be produced here**, and the render-grep is disqualified as proof by this
> AC's own text.
>
> What ships: the backgrounding wiring, stage-guarded, plus a live fixture that is `skipif`'d on CLI
> absence so it runs and proves the AC automatically in any environment that has one. What does NOT
> ship: a claim that AC-006 is green. The user was offered three routes — wire-and-record,
> defer Phases 4+6, or install a CLI first — and chose wire-and-record, on the reasoning that
> leaving the concurrency claim unwired keeps a **false claim** in the harness (ADR-007 rejected
> downgrading it to ordering-only), while calling a render-grep proof would commit the exact defect
> this unit exists to remove.
>
> The honest summary for a later reader: **the 300 s is off the critical path in the render, and
> nobody has watched it happen.**

Tests: `tests/unit/test_second_opinion_backgrounding.py::test_ac_006_the_review_render_backgrounds_the_invoker`,
`::test_ac_006_the_plan_render_refuses_to_background`,
`::test_ac_006_no_model_enabled_renders_neither_instruction`,
`::test_ac_006_a_live_review_overlaps_the_fan_out` (the oracle — `skipif` on CLI absence, so it is
**skipped**, not passed, here).

### AC-007: no disclosed default survives inversion of its producing object

For every document assertion of the form "the default is X", inverting X in the class that
produces it must make the guarding assertion fail. Independence: a metamorphic relation
over the guard itself — it is satisfiable only by binding the claim to the producing
object, which is precisely the remedy `wrong-transparency-table-worse-than-none` records
after a presence-only regex (`re.search(r"autonomy|autopilot", summary)`) passed on
inverted content.

Tests: `tests/unit/test_doc_truth.py::test_ac_007_inverting_a_disclosed_default_fails_the_guard`,
`tests/unit/test_doc_truth.py::test_ac_007_the_guard_is_green_before_the_inversion`,
`tests/unit/test_doc_truth.py::test_ac_007_every_disclosure_is_value_bound`.

### AC-008: README's worktree claim holds on both arms

Golden over `worktree.enabled ∈ {true, false}`: the README sentence must be true in both
cases. Independence: the truth value comes from `worktree_enabled(base)` — the single
documented reader — not from the sentence. Today the sentence asserts a fresh worktree per
`/hm:execute`, which is false at `false` and imprecise at `true` (the worktree is the
persistent per-task `hm/<slug>`).

Tests: `tests/unit/test_doc_truth.py::test_ac_008_the_readme_worktree_claim_holds_on_both_arms`.

### AC-009: the advisory names the threshold that fired

Golden over three states: count-over-only, days-over-only, and both. The emitted message
must cite the threshold belonging to the branch that fired. Independence: the expected
citation is derived from which branch the inputs trip, computed from
`audit_session_threshold` / `audit_days_threshold` directly. The observed production
message — `0 axis overrides … (threshold 30)` — is self-refuting, since 0 < 30 cannot trip
the count branch.

Tests: `tests/unit/test_doc_truth.py::test_ac_009_the_advisory_names_the_threshold_that_fired`,
`tests/unit/test_sessionstart_drift.py::test_ac_009_the_emitted_banner_names_only_the_threshold_that_fired`
(the second is the **observable** arm — it drives the real SessionStart hook and reads the banner a user
sees. A.5 round 1 rejected an `inspect.getsource` wiring grep as a decoration: it is satisfied by a
comment, by a dead branch, and by a call whose return value is discarded, and the justification for
avoiding execution was refuted by `test_sessionstart_drift.py`, which already builds all three fixtures
the justification called unavailable).

### AC-010: every enabled name resolves to a real asset

For any rendered `harness.yaml`, every name in `skills.enabled` resolves to a directory under
`templates/skills/`, and every name in `reviewers.enabled` resolves to a rendered
`.claude/agents/<name>.md`. Independence: the referent is the **actual inventory**, not the
sibling `installed` list. `synthesize.py:3-5` installs the full inventory unconditionally, so
`installed` is descriptive and a containment check against it is satisfiable by *adding* a
phantom name to `installed` — where the phantom still resolves to no template. The
reviewer half — which a containment check would report green with zero work — is exercised
because resolution is against the inventory.

**⚠️ Premise corrected 2026-09-08 (Phase 6).** This AC used to add "Today's two phantoms
(`relevance-filter`, removed in 0.22.3; `research-crawler`) fail this". They do not. Both names
were removed in 0.22.3 (ADR-0007) and survive only in **comments** (`communication_audit.py:25,46`,
`synthesize.py:825`); neither appears in any producer-emitted `skills.enabled`. Measured on both
presets, the resolution invariant is **already green** — my RESEARCH read a comment as a config
value, the third stale premise from that pass. The AC is therefore a **regression guard** rather
than a repair, kept because the mechanism it specifies (resolution against the inventory, not
containment in `installed`) is the one that would have caught the phantoms had they been real.

What the measurement **did** find: `test-reviewer` is in `_PROD_ENABLED_REVIEWERS` but **not** in
`_ALL_REVIEWERS`, so the rendered `installed` list omits a reviewer that is enabled and rendered.
`installed` has no validating consumer (`cli.py` only mutates `enabled`), so nothing breaks — but a
config surface that under-reports what is installed is this unit's own defect class, so it is fixed
and asserted.

Tests: `tests/unit/test_enabled_names_resolve.py::test_ac_010_every_enabled_name_resolves_to_a_real_asset`,
`tests/unit/test_enabled_names_resolve.py::test_ac_010_a_phantom_name_is_caught`,
`tests/unit/test_enabled_names_resolve.py::test_ac_010_enabled_is_contained_in_installed`.

### AC-011: no shipped section survives whose body refutes its heading

`docs/HOW-IT-WORKS.md` contains neither a `Fusion Commands` section nor a
table-of-contents entry for one. Independence: a golden absence check against a
concretely-named stale section whose body already states that no fusion command exists;
the fused-command axis was deleted and `workflow_fuse.py` is gone.

Tests: `tests/unit/test_doc_truth.py::test_ac_011_no_shipped_section_refutes_its_own_heading` (a **deference** test — it asserts
the shared gate owns the invariant), and the normative site
`tests/structural/test_no_fused_workflow_axis.py::test_no_repo_doc_advertises_a_fused_workflow`, whose
`_PROSE_BAN` is widened to be case-insensitive and to cover the plural + hyphenated-anchor spellings.
A.5 round 1 established that the pre-existing gate already owns this invariant repo-wide and missed
these three lines only on case and plurality — so three fresh literals in a new file would have been a
second, strictly narrower source of truth that left the recurrence open.

### AC-012: an unreachable vault is a standing health condition

With `second_brain.enabled: true` and a `vault_path` that does not resolve, `/hm:health`
reports a named condition. Independence: golden against the condition name, with the
precondition constructed rather than observed — today the failure surfaces only when a
`second_brain` subcommand is invoked, so a wrapup that never reaches Step 5.6 shows
nothing.

**The signal carries `weight: 0`.** A `/hm:health` dimension's signal weights sum to 100, so
adding a weighted signal means redistributing every other weight in that dimension — a broad
change next to a Contract-Boundary-adjacent area, for a fact that is a *configuration/environment*
condition rather than a harness-quality defect. AC-012 requires the condition to be **reported**,
not scored, and `weight: 0` is already this module's vocabulary for exactly that (the
`not_applicable` field's own comment says so). Disabled `second_brain` reads as an opt-out
(`passed`, `not_applicable`), reachable vault as `passed`, unreachable-while-enabled as failed
with an action.

Tests: `tests/unit/test_health_evidence_surface.py::test_ac_012_an_unreachable_vault_is_a_standing_condition`,
`tests/unit/test_health_evidence_surface.py::test_ac_012_a_disabled_second_brain_is_an_optout_not_a_failure`.

### AC-013: the per-command ratchet sees second-opinion surface

The render the per-command ratchet measures is constructed with `second_opinion` set, and the
`_ATOMIC_RATCHET` constants for `review` and `plan` are re-derived against that render with
the derivation recorded. Independence: differential between a models-off and a models-on
render of the same answers, so the expected delta is produced by a second configuration
rather than asserted as a literal.

**The "gate measures the shipped file" half is retracted, not deferred.** `.gitignore:26`
excludes `.claude/*`, so there is no shipped render in a fresh worktree and a stale one in
base; `_surface_baseline.py:5-9` records measuring it as a deliberately rejected design
("measuring it would have frozen a baseline against whatever happened to be lying around").
The 435,437-vs-442,446 gap is therefore a **stale untracked local render**, not a gate
defect, and binding the gate to it would make the gate red or erroring in CI and in every
worktree. RESEARCH finding A-10 was mis-framed; this is the correction.

Tests: `tests/structural/test_command_size_budget.py::test_ac_013_the_ratchet_render_carries_second_opinion`,
`tests/structural/test_command_size_budget.py::test_ac_013_the_models_delta_is_produced_by_configuration`.

### AC-015: no rendered command instructs from a list its own dispatch ignores

The rendered `review.md` does not tell the model to start from `harness.yaml reviewers.enabled`
while the same file's generated lens-dispatch table is composed without it. Independence: the
two halves are read from the *same rendered file* — the instruction at `review.md.j2:139` and
the dispatch table generated from `lens_dispatch(preset)` — so the contradiction is decidable
from the artifact alone, with no reference to either producer's intent. This is the other half
of the contract AC-007's family addresses: the fifteenth gap, found by plan validation, in the
largest rendered command (87,438 chars).

Tests: `tests/unit/test_doc_truth.py::test_ac_015_no_rendered_command_instructs_from_an_ignored_list`.

### AC-014: every unwired component is wired or gated as intentional

For each of `context_lint.lint`, `consensus-arbiter` and `verify` delegation, the repo
contains either a production call site or a structural gate asserting the absence is
intentional. Independence: a property over the component set — it holds for a component
added later, and cannot be satisfied by inspecting any one of today's three. The agent arm
**discovers** its members (a rendered agent whose name appears in no rendered command or skill)
rather than reading a hand list, which is how Phase 6 found a **fourth** member the SPEC had not
named: `security-auditor`, present only in `harness.yaml`'s `installed`.

Tests: `tests/structural/test_unwired_components.py::test_ac_014_every_unwired_agent_is_declared`,
`tests/structural/test_unwired_components.py::test_ac_014_context_lint_has_a_production_caller`,
`tests/structural/test_unwired_components.py::test_ac_014_the_linter_sees_every_asset_class`,
`tests/structural/test_unwired_components.py::test_ac_014_the_linter_reaches_the_codex_half_of_the_render` (review finding P1-5: the
caller filtered on `relative_to(target_dir)` and `continue`d, silently dropping the 22 assets that
`resolve_output_path` writes to `target_dir.parent` — `AGENTS.md` and all of `.agents/` — so the
`AGENTS.md` threshold rows were unreachable from the only production caller while a structural
test calling the classifier directly stayed green),
`tests/structural/test_unwired_components.py::test_ac_014_the_linter_emits_on_an_over_threshold_asset`,
`tests/structural/test_unwired_components.py::test_ac_014_verify_delegation_is_config_gated`.

The emission arm is the one A.5 round 1 required and plan validation had pre-named: a call-site
test — even a two-hop reachability one — is still green when the call's return value is discarded,
when `logger.warning` becomes `logger.debug`, or when an early `return` guards it. Only a positive
observation of the emitted record decides Phase 6's exit criterion 3 ("a re-render emits the linter
warning path without failing"), which was otherwise decided by nothing but a hand observation.

## ❓ Open Questions

1. **Which document set does AC-007's property range over?** `CLAUDE.md`, `README.md`,
   `docs/**`, the rendered `make.md` disclosure table, and rendered `harness.yaml`
   comments are all candidates. Ranging over all of them at once risks R5's false
   positives; ranging over too few reproduces the gap. `/hm:plan` should phase this —
   likely starting from the `make.md` table, which already has a truth-regression history.
2. **Does AC-006's live dispatch belong in CI or in a manual `INTEGRATION=1` fixture?**
   CLAUDE.md permits real calls under `INTEGRATION=1`, and `release.yml` already runs a
   `boundary-advisory` suite post-tag. A live cross-model call in the PR gate would be new
   policy.
3. **Roll-up file name and shape.** A `work-docs/` deliverable regenerated on every run
   competes with the wrapup deliverable commit's diff noise. Whether it is one
   append-only file, one per window, or a single overwritten snapshot is a `/hm:plan`
   decision with a git-history cost either way.
4. **Does AC-005 also retire the picker block for `gated`?** The picker is already
   correctly gated on `level != "gated"`, so the answer is presumably no — but the two
   blocks are adjacent in the same partial and a single `{% if %}` restructure could touch
   both. Confirm the picker's 18,067 chars stay exactly as they are.
5. **Ordering: does the evidence half (AC-001–004) have to land before the parity half?**
   AC-013's numbers and AC-005's delta are self-measuring and do not need the ledgers, so
   the halves may be independent — but AC-006's differential does need a recorded run.

## 🔍 Refinement Decisions

- **Round 1 — scope.** Locked `D + A`: restore the evidence layer and close the 14 parity
  gaps. Approach C (proportionality) deferred to a follow-up PLAN, because the data that
  would justify a triage rule is this unit's output and an unjustified rule collides with
  `lens_coverage.blocks_approval`.
- **Round 1 — A-3 direction.** Locked *prose moves*: CLAUDE.md's `reviewers.enabled`
  recommendation is retracted and `enabled` is documented as asset-activation only. Rationale:
  on Production `routable_lenses` is empty so there is nothing to narrow, and dropping a
  mandatory lens makes every review unapprovable. Recorded as R6 that this leaves no user
  lever until Approach C.
- **Round 1 — ledger durability.** Locked *summary roll-up committed to `work-docs/`*, raw
  ledgers stay gitignored. Rationale: `.claude/observability/` is listed in
  `worktree._HARNESS_CHURN_DIRS` (`worktree.py:109-117`), read by both the finalize
  dirt-filter and the create-guard, so a committed path beneath it would perturb the 5-layer
  defense. The `work-docs/` side is narrower than "already staged": the filename must reuse an
  existing `DELIVERABLE_PREFIXES` entry (`BASELINE-` does) and must be named in `wrapup_land`'s
  manifest, which is what gives blast radius zero.
- **Round 1 — the $390 experiment.** Locked *make it runnable, do not run it here*. The 16
  pipeline runs are a schedule decision, and today an arm would execute without being
  recorded.
- **Round 2 — §2.5 inequality gate.** Five further candidates evaluated, none passed: the
  14-gap membership is common ground once scope was chosen; `parent_spec`, `verification_tier`
  and `mutation_threshold` were resolvable from the repository at confidence ≥ τ; the
  autopilot 0-fire cause is an *output* of the evidence half, so it fails answerability; and
  the test framework is fixed by CLAUDE.md.
- **`parent_spec: null`, deliberately.** `SPEC-observability` is the L1 cluster for
  `/hm:health` layers and telemetry and would fit AC-001–004 and AC-012, but not the
  render/doc parity half. Declaring it anyway would be a false structural claim of exactly
  the kind this SPEC exists to remove.
- **Tier 2 / mutation threshold 70.** The changed Python is aggregation arithmetic over
  ledger rows, where a wrong aggregation key survives a shape-only assertion — the failure
  CLAUDE.md records as a 30× mis-measurement (61.3% reported vs 2.15% actual). Not tier 1:
  none of it is on `/hm:execute`'s hot path. 70 rather than 85 because the same modules hold
  path and I/O code these tests cannot reach.
- **Round 3 — plan-validation feedback (2026-09-08).** `/hm:plan`'s validator returned
  `MAJOR_REVISION` with fifteen findings, of which five landed on this SPEC and are corrected
  above. Two required a user decision: the `_ATOMIC_RATCHET` collision (resolved as a recorded
  measurement-subject re-baseline, so AC-013's second half stands) and a newly-found fifteenth
  parity gap (folded in as AC-015 / S12, taking the AC count from 14 to 15). The other three
  had a single sound resolution and were applied directly: AC-001's clone check cannot prove
  staging and the fixture needed a disposition row; AC-010's containment check was bound to the
  wrong referent; **AC-013's "gate measures the shipped file" half is retracted** — `.claude/*`
  is gitignored so there is no shipped render to measure, which makes RESEARCH finding A-10 a
  mis-framing rather than a defect. The roll-up also gained a filename and a staging
  constraint, because `work-docs/` is not blanket-staged.
- **`judgment` avoided.** AC-014 was drafted as a judgment AC, then made mechanical: the
  four available rubrics (`agent_prompt`, `claude_md`, `repair_guard_force`, `skill`) do not
  cover it, and inventing a rubric file to satisfy cross-validate rule 4 would add surface
  for one AC.
