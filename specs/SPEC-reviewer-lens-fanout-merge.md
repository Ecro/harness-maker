---
type: spec
task_slug: reviewer-lens-fanout-merge
status: approved
created: 2026-09-13
tier: 2
tags: [harness-maker, spec, python, jinja2, review-pipeline, token-efficiency]
test_framework: pytest
research_doc: "[[RESEARCH-reviewer-lens-fanout-merge]]"
summary: "Collapse /hm:review's four core lenses into one code-reviewer dispatch, with lens_coverage gaining a merged mode"
---

# SPEC — merging the `/hm:review` core-lens fan-out

## 🎯 Intent

`/hm:review` dispatches seven lenses per round, and four of them — `design`, `functionality`,
`robustness`, `consistency` — go to the **same** `code-reviewer` agent, differing only by one
brief sentence. Each one independently ingests the diff and up to 400 lines of context per
changed file, so three of those four ingestions buy nothing but a separate context. Phase A.5
of `/hm:execute` already made this exact move for its three test lenses and recorded ≈330k
subagent tokens saved per round.

This SPEC collapses the four into one dispatch carrying all four lens questions verbatim, and
teaches `lens_coverage` that one merged result file satisfies the four core lenses it stands
for. The three domain lenses (`security`, `concurrency`, `tests`) dispatch to three different
agents and are untouched — the end state is seven dispatches becoming four.

The yield risk is accepted rather than measured, and is stated in Non-Goals: the nearest
measured point (`harness-bench` §10) scored a single generic call at 11.0 distinct findings
against 30.0 for a six-category fan-out, and the enumerated-categories-in-one-call arm the
merge actually produces was never run. This is the same trade A.5 took.

## 🌅 Outcomes

A reviewer running `/hm:review` after this change:

- sees **four** subagent dispatches per round on Production (one merged `code-reviewer` plus
  `security-reviewer`, `concurrency-reviewer`, `test-reviewer`) where seven ran before, and
  four on Side for the same reason;
- gets the same grade-gate behaviour: every finding still carries its `lens` stamp, one lens
  still votes alone (ADR-007), and `hm lens_coverage check` still reports
  `blocks_approval: false` on a complete round;
- can restore the fan-out by editing **one function** — the grouping function in
  `conditional_router` — with no template surgery and no config migration.

Nothing a consuming project configures changes: `harness.yaml` gains no key.

## 📋 In-Scope Scenarios

### AC-001: Round 1 sends the four core lenses as exactly one `code-reviewer` dispatch

**Given** a Production harness rendered from `review.md.j2`
**When** the rendered `/hm:review` Step 3 dispatch block is read
**Then** it contains exactly **one** dispatch naming the `code-reviewer` agent
**And** the total dispatch count in that block is four — the merged core plus
`security-reviewer`, `concurrency-reviewer` and `test-reviewer`
**And** the same holds for the Side render and for the `is_codex` variant, which differ in
call form but not in grouping.

### AC-002: The confirmation pass renders the identical grouping to round 1

**Given** the same render
**When** Step C2's dispatch block and Step 3's dispatch block are both extracted
**Then** the two lists of (agent, lens-set) groups are equal, element for element and in order
**And** this holds for every preset × target arm, because both blocks are generated from the
same grouping function rather than restated.

> This is SPEC AC-015 of the nine-lens work, carried forward. A confirmation pass missing a
> lens the coverage CLI requires makes every review permanently unapprovable, so the parity is
> a structural property, not a convention.

### AC-003: All four core lens questions survive the merge verbatim

**Given** `conditional_router.LENS_DISPATCH`
**When** the merged dispatch's brief is read out of the render
**Then** each of the four core lens brief strings appears in it **byte-identically**
**And** the merged dispatch also carries an explicit accountability line naming all four lenses,
so the agent is told it owns every one of them rather than choosing among them.

> `LENS_DISPATCH` is the independent source of truth here: the render is compared against the
> Python constant, not against a copy of itself.

### AC-004: One merged result file marks the four core lenses exercised

**Given** a round directory holding a single `core.json` whose `lens` field is `core` and whose
`run_id` matches the invocation
**When** `lens_coverage.coverage_verdict` runs for that round with `--preset Production`
**Then** `missing` contains none of `design`, `functionality`, `robustness`, `consistency`
**And** `blocks_approval` is `false` once the three domain lens files are also present
**And** a round directory holding the four individual `<lens>.json` files instead still
resolves the same way, so an un-re-rendered harness keeps working.

### AC-005: `exercised` still names the four core lenses individually

**Given** the merged-mode verdict of AC-004
**When** its `exercised` array is read
**Then** it contains `design`, `functionality`, `robustness` and `consistency` as separate
entries
**And** it does **not** contain `core`
**And** `review_telemetry`'s `lenses_exercised` field therefore stays comparable with rows
written before this change.

> Provenance for the expected value: the shipped row in
> `.claude/observability/review-2026-08-19.jsonl` carries
> `["design","functionality","robustness","consistency","security","concurrency","tests"]`.
> A merged run of the same shape must produce the same array.

### AC-006: Merged mode stays fail-closed on every non-conforming file

**Given** a round directory whose `core.json` is absent, unparseable, not a JSON object,
carries a `lens` value other than `core`, or carries a `run_id` from another invocation
**When** `coverage_verdict` runs
**Then** all four core lenses appear in `missing`, for every one of those five cases
**And** `blocks_approval` is `true`.

> The property, not the five cases: "cannot tell" must never resolve to "exercised". This is
> the invariant `exercised_lenses` already holds for per-lens files, and merged mode must not
> be the hole in it — a merged file is now vouching for four lenses instead of one, so a
> fail-open here is four times as expensive as before.

### AC-007: The round-trip budget and the surface baseline agree on the new value

**Given** the merged render
**When** `tests/structural/test_roundtrip_budget.py` and
`tests/structural/surface_baseline.json` are both evaluated against it
**Then** the `review` round-trip count is **33** in the budget table and the live render
produces the same count
**And** `surface_baseline.json`'s `review` and `hm-review` entries match the live render's
`chars` and `round_trips`
**And** `work-docs/BASELINE-DELTA-reviewer-lens-fanout-merge.md` carries an attribution row for
every changed key, each naming its parent segment backticked.

> Round trips are compared **exactly** and have no ratchet, so the budget table and the frozen
> baseline must move in the same commit or the suite is red either way.

### AC-008: The grouping function is the sole producer of the dispatch groups

**Given** `review.md.j2`
**When** its two dispatch blocks are read
**Then** neither block contains a literal lens name or a literal lens brief string — every
lens name, agent name and brief reaching the render comes from the grouping function exported
as a Jinja global
**And** `conditional_router.lens_dispatch()` is unchanged and still returns one entry per lens,
so `lens_coverage`'s notion of the mandatory set is untouched.

> This is the reversibility decision made executable. Restoring the fan-out means changing the
> grouping function to return one group per lens; if the template held literals, it would mean
> editing two blocks that can drift from each other.

## 🚫 Non-Goals

- **Measuring the merge's yield.** No paired run, no before/after finding comparison. The
  trade is recorded in Intent and in the PLAN, the way A.5 recorded its own.
- **Per-lens `stage_agent_ledger` instrumentation.** Declined this round; review lens cost
  stays unmeasurable.
- **Content-based or language-based lens routing** (the deferred option B).
  `conditional_router.route_reviewers` and `route_with_llm` are not touched.
- **Stage-level proportionality triage** — deferred by ADR-008 of
  PLAN-token-efficiency-autopilot-ux-speed and still deferred.
- **The three domain lenses.** `security`, `concurrency` and `tests` keep their own agents and
  their own dispatches. `mandatory_lenses` / `routable_lenses` / the preset split are unchanged.
- **ADR-007's solo-lens vote and `review_consensus`.** One lens still votes alone; the per-finding
  `lens` stamp stays metadata and is still never an input to `codex_adapter.finding_id`.
- **`reviewers.enabled` semantics** — it is not an input to the dispatch and does not become one.
- **Any `harness.yaml` key.** No schema change, no migration, no interview round.
- **The 2-pass redaction protocol**, which gates on `reviewers.enabled | length` and is
  unaffected by the lens count.

## ⚠️ Constraints

| Constraint | Value | Rationale |
|---|---|---|
| Test framework | `pytest` | CLAUDE.md fixes the toolchain; `uv run pytest` is the gate. |
| Type checking | `mypy --strict` clean | Repository-wide gate; the new grouping function is typed. |
| Round trips | `review` **exactly 33** | Exact-match with no ratchet — 39 today, −3 in round 1 and −3 in Step C2. |
| Render determinism | No shell-out, no I/O at render time | `implementation-patterns.md`; the grouping function is pure. |
| Target coverage | all three targets, ungated | PLAN-multi-lens-review-round ADR-005 — the fan-out renders ungated, so its replacement does too. |
| Dispatch form | one literal dispatch with four literal questions | A templated `<lens>` placeholder was tried and reverted; a literal example is what an executing model imitates. |
| Backward compatibility | per-lens result files keep resolving | An un-re-rendered harness writes four files and must stay approvable. |

## ✅ Verification Criteria

| Scenario | Verification mode | Test name / manual step |
|---|---|---|
| AC-001 | unit (render) | `tests/render/test_render_review_lens_groups.py::test_round_one_sends_one_code_reviewer_dispatch` |
| AC-002 | unit (render, property) | `tests/render/test_render_review_lens_groups.py::test_the_confirmation_pass_groups_match_round_one` |
| AC-003 | unit (render, differential) | `tests/render/test_render_review_lens_groups.py::test_every_core_lens_brief_survives_verbatim` |
| AC-004 | unit | `tests/unit/test_lens_coverage_merged.py::test_one_core_file_covers_the_four_core_lenses` |
| AC-005 | unit | `tests/unit/test_lens_coverage_merged.py::test_exercised_names_the_core_lenses_not_the_group` |
| AC-006 | unit (property) | `tests/unit/test_lens_coverage_merged.py::test_merged_mode_is_fail_closed_on_every_bad_file` |
| AC-007 | structural | `tests/structural/test_roundtrip_budget.py` + `tests/structural/test_surface_allowance.py` + `tests/structural/test_baseline_delta_attribution.py` |
| AC-008 | unit (render, source-level) | `tests/render/test_render_review_lens_groups.py::test_no_lens_text_is_a_literal_in_the_template` |

## ❓ Open Questions

None blocking. Two items are decided here rather than deferred, and are flagged so `/hm:plan`
can promote them to ADRs with their rationale attached:

1. **`exercised` expands the group into its member lenses** (AC-005) rather than reporting
   `core`. Decided to keep `review_telemetry.lenses_exercised` comparable with historical rows
   and to leave `ALL_LENSES` as the output vocabulary. The group name lives in a separate
   group-file vocabulary consumed only by `exercised_lenses`.
2. **The coverage gate's meaning weakens, deliberately.** With four files written by the main
   loop from one return, `exercised` answers "was this lens asked" rather than "did this lens
   deliver". The gate still catches the merged dispatch dying wholesale. Recorded here so the
   next reader does not discover it from behaviour.

## 🔍 Refinement Decisions

- **Round 1** — Direction locked: **immediate merge**, following the A.5 precedent, with no
  measurement arm (the yield comparison AC was dropped). Per-lens `stage_agent_ledger`
  instrumentation declined, which fixes the round-trip target at 33 rather than 37.
- **Round 2** — Coverage locked: **`lens_coverage` gains a merged mode** (a `core.json` group
  file satisfies the four core lenses) rather than the main loop fabricating four empty files;
  this makes the gate say what it actually measures, at the cost of a Python change and a
  group-file vocabulary. Reversibility locked at **code level**: a grouping function in
  `conditional_router` is the sole producer of dispatch groups, with no `harness.yaml` knob —
  an unevidenced choice is not put to consuming projects.
- **Defaulted without asking** — the four lens briefs are carried **verbatim** (A.5 precedent,
  confidence above threshold); the render stays ungated across all three targets
  (PLAN-multi-lens-review-round ADR-005); `pytest` as the framework (CLAUDE.md).
