---
type: spec
task_slug: lens-and-review-fix-verification
status: approved
created: 2026-08-17
tier: 2
tags: [harness-maker, spec, python, review-pipeline, observability, config-axis]
test_framework: pytest
research_doc: "[[RESEARCH-lens-and-review-fix-verification]]"
summary: "Close three lens/review defects, stop paying for artifacts nobody reads, and prove the axis runs"
---

# SPEC — lens and review fix verification

## 🎯 Intent

RESEARCH established that the seven-lens review axis works — one live run in `~/neuroTerm`
delivered all seven lens files and passed `lens_coverage check` with `missing: []`. What does
not work is everything around it: the unit suite writes synthetic rows into the live
second-opinion ledger and corrupts the one health metric CLAUDE.md prescribes; `review.md.j2`'s
routing paragraph still describes the agent axis the lens merge retired; and the per-finding
`lens` stamp the template mandates was absent on 19/19 findings in the one real run.

Alongside those, the operator raised a cost question the audit half-confirmed: `~/neuroTerm`
carries `instrumentation.stage_agent_ledger: true` without ever having opted in, and the REVIEW
document — whose only machine consumers read its frontmatter — has no size control at all.

## 🌅 Outcomes

- A reader of `.claude/observability/second-opinion.jsonl` gets the real per-model loss rate
  without knowing which rows are test artifacts.
- A reviewer running `/hm:review` is told, in the coverage CLI's own output, which lenses
  delivered unstamped findings — without the review becoming unapprovable.
- A project that never consumes harness-maker's development telemetry stops producing it.
- A project can choose how much REVIEW prose it pays for, and the cheapest choice still leaves
  the auto-fix loop able to run round 2.
- Every `.claude/observability/` artifact has a named consumer, or it is gone.

## 📋 In-Scope Scenarios

Each scenario is stated as the acceptance criterion it belongs to, below. The index:

| # | AC | Area |
|---|---|---|
| S1 | AC-001 | Test suite stops writing to the live ledger |
| S2 | AC-002 | Aggregation excludes already-recorded synthetic rows |
| S3 | AC-003 | Routing prose matches the actual dispatch |
| S4 | AC-004 | Missing per-finding lens stamp is reported, advisory |
| S5 | AC-005 | Instrumentation absent-key resolves to off |
| S6 | AC-006 | `review_doc` knob with three modes |
| S7 | AC-007 | `review_doc` default is `frontmatter-only`, both paths |
| S8 | AC-008 | Antigravity empty-response failures are classified |
| S9 | AC-009 | Observability consumer audit is complete |
| S10 | AC-010 | Orphan writers are removed |
| S11 | AC-011 | The lens axis is exercised live in two more projects |

---

### AC-001: The unit suite writes no rows into the base repo's second-opinion ledger

**Given** a repository whose `.claude/observability/second-opinion.jsonl` may be appended to at any
time by a concurrent session
**When** the full unit suite runs from the repo root
**Then** every `second_opinion_invoke` entry point reached by a test resolves its base root to a
test-owned directory, never to the enclosing git repository — enforced by an **autouse** fixture,
not by per-test opt-in
**And** a canary test that calls `soi.main()` with no `base_root` and no `chdir` writes its row
under `tmp_path`
**And** no test module bypasses the fixture.

> **Amended 2026-08-17 (PLAN validator C7/C13/C14).** The original `Then` was "the file still has N
> rows". That is unusable as an oracle: the ledger is append-only and shared, so a peer session's
> legitimate row fails it with no test at fault — and this SPEC's own Constraints record that two
> sessions were live during research. Its first replacement, a "test-owned marker" on rows, was
> also rejected: `codex_ledger.SecondOpinionRecord` is `extra="forbid"` and cannot carry one,
> which leaves a per-test slug convention — a hand list, i.e. the exact thing this criterion is
> stated suite-wide to avoid. The criterion is now **prevention at the fixture**, which nothing
> has to opt into, plus two checks that the prevention is real.

> The leak is `soi.main()` / `soi.invoke()` called without `base_root` and without `chdir`:
> `resolve_base_root()` then walks up from the real cwd. `tests/unit/test_second_opinion_invoke.py`
> (`:359`, `:740`) are the known
>
> ⚠️ **Corrected 2026-08-17 during execute:** this sentence also listed
> `tests/unit/test_second_opinion_budget_advisory.py` (`:160`). It is **not** a leak site — it
> passes `--root str(tmp_path)`, an explicit test-owned root. The claim came from matching the
> polluted rows' `skip_reason` text against test names rather than from reading the call, and an
> AST scan authored in Phase 1 surfaced it as a false positive. Which is the reason this criterion
> is a suite-wide invariant and not a list of sites. Original text follows:
>
> ~~and `tests/unit/test_second_opinion_budget_advisory.py` (`:160`) are the known~~
> sites; the criterion is stated over the whole suite because a hand list of sites is the failure
> mode CLAUDE.md records three times.

### AC-002: Recorded synthetic rows are excluded at read time

**Given** a ledger containing rows with a slug listed in `.claude/observability/.ledger-exclusions.json`
**When** any aggregate over the second-opinion ledger is computed
**Then** those rows are absent from both numerator and denominator
**And** the ledger file itself is byte-identical before and after (append-only is preserved).

> The mechanism already exists for the stage-agents ledger (`ledger_exclusions.EXCLUSIONS_FILE`)
> and is generalized here rather than reinvented. The 83 `slug: "s"` rows since 2026-08-14 are the
> first entry.
>
> **Amended 2026-08-17 (PLAN ADR-007).** "Generalized" required a schema decision this SPEC had not
> made: the existing file is keyed by **run id**, and `codex_ledger.SecondOpinionRecord` is
> `extra="forbid"` with no `run_id` field, so the two ledgers had no common key. The file becomes a
> list of per-entry predicates `{key: "run_id"|"slug"|"stage", value, reason}`, with a one-shot
> migration of the legacy map. A malformed file **fails loudly** — excluding nothing must not look
> like having nothing to exclude.

### AC-003: The routing paragraph names only agents the dispatch can produce

**Given** `review.md.j2` Step 3's routing prose for a given preset
**When** its named reviewer agents are compared against `lens_dispatch(preset)`
**Then** every agent the prose names appears in the dispatch list
**And** no dispatched lens is described as routable when `mandatory_lenses(preset)` contains it.

> Today the prose says the conditional router "may drop only `ux-reviewer` / `performance-reviewer`",
> neither of which `lens_dispatch` ever returns. That prose is what made the live neuroTerm run
> stamp both into `reviewers_invoked:`.

### AC-004: Unstamped findings are reported without blocking approval

**Given** a per-round lens results directory in which some result files contain findings lacking
a `lens` key matching the file's lens
**When** `hm lens_coverage check` runs over it
**Then** the JSON carries an `unstamped` array naming each such lens
**And** `blocks_approval` is computed exactly as it is today — the stamp never changes it
**And** a directory in which every finding is stamped yields `unstamped: []`.

### AC-005: An absent instrumentation key resolves to off

**Given** a `harness.yaml` with no `instrumentation` block
**When** it is loaded by `interview._parse_instrumentation`
**Then** `stage_agent_ledger` is `False`
**And** the resolution is announced once, naming the change from the previous behaviour.

> This deliberately reverses half of `InstrumentationConfig`'s ADR-011 (absent → `True`). The cost
> is accepted and stated in Non-Goals: projects that were producing rows only because they predate
> the key will stop, and the cross-project denominator shrinks.

### AC-006: `reviewers.review_doc` selects how much REVIEW prose is written

**Given** `reviewers.review_doc` set to `full`, `lean`, or `frontmatter-only`
**When** `/hm:review` renders and writes its report
**Then** the document contains exactly the sections that mode defines:

| mode | frontmatter | loop-state sections | findings | narrative / rationale |
|---|---|---|---|---|
| `full` | ✅ | ✅ | ✅ full prose | ✅ |
| `lean` | ✅ | ✅ | ✅ full prose | ❌ |
| `frontmatter-only` | ✅ | ✅ | ✅ **machine-minimal** | ❌ |

> **Amended 2026-08-17 (PLAN ADR-005).** This row read `findings_lists: false` for
> `frontmatter-only`, which contradicted the constraint below it: the findings ARE the loop state,
> because the round-to-round voter merge is keyed by finding `id`. Machine-minimal means
> `id · severity · file:line · message · voices · lifecycle state`. **`message` is not optional** —
> `codex_adapter.finding_id` hashes it as an identity input, and a round-2 fix step that reads the
> document rather than round-1 context would otherwise hold an id and a location with no statement
> of the defect.

**And** in every mode `drift_verdict` is present in the frontmatter
**And** in every mode Section 7 `🧊 Cross-model findings (frozen @ round 1)` is written whenever
`second_opinion.models` is non-empty.

> `frontmatter-only` means *"only what a machine reads"*, not *"only the frontmatter"*. The REVIEW
> body is the auto-fix loop's own working state: rounds 2..N re-read Section 7 instead of
> re-invoking a model, and finding lifecycle (`pending` → `resolved`/`stale`) lives in the
> per-iteration records. Dropping those would break multi-round review in every harness with
> cross-model voters — spoton and harness-maker both qualify.

### AC-007: frontmatter-only is the default on both the new-render and absent-key paths

**Given** either a freshly rendered harness or an existing `harness.yaml` with no `review_doc` key
**When** the value is resolved
**Then** it is `frontmatter-only`
**And** the resolution for the absent-key case is announced once.

> Unlike `instrumentation`, the new-render and absent-key defaults deliberately agree. The operator
> chose this knowing existing projects' REVIEW documents shorten at the next re-render.

### AC-008: Antigravity's empty-response failure is a distinguishable class

**Given** an `agy` invocation returning `status: SUCCESS` with an empty `response` and no
`structured_output`
**When** the invoker records the outcome
**Then** the ledger row's `skip_reason` carries a stable token identifying this class specifically,
distinct from parse failure and from a non-SUCCESS status
**And** `/hm:health`'s per-model smoke reports the class when it occurs
**And** the measured rate for this class over real invocations is reported, not inferred.

> Excluding synthetic rows, antigravity failed 4 of 7 real invocations since 2026-08-16, all with
> this signature. This AC makes the class countable; it does not promise a fix, because the cause
> is on the vendor side of the CLI boundary.

### AC-009: Every observability artifact has a named consumer or is listed as orphaned

**Given** the set of paths any module writes under `.claude/observability/`
**When** the audit document is produced
**Then** every path in that set appears in the audit table with its writer, its readers, and the
user-facing command (if any) that surfaces it
**And** the table marks each row `consumed` or `orphan`.

### AC-010: Orphan writers are removed

**Given** the audit's `orphan` rows
**When** the change is complete
**Then** no module writes those paths
**And** removing them changes no `/hm:health`, `/hm:metrics`, or `verifier_discrimination` output.

### AC-011: The lens axis is exercised live in harness-maker and spoton

> ⏸️ **DEFERRED — not satisfied by PLAN-lens-and-review-fix-verification (its ADR-008).** The
> drafted Phase 6 excluded re-rendering the two target projects while requiring that neither
> REVIEW frontmatter name an undispatched reviewer — but the routing prose is baked in at render
> time, so the phase would have reproduced the defect by construction and could not distinguish a
> failed fix from an undeployed one. The follow-up task must re-render both targets first, and
> must additionally assert `unstamped: []` — the criterion below cannot observe the very defect
> that had 19/19 incidence in the only real run. **The axis therefore remains observed in exactly
> one project.**

**Given** each of `~/harness-maker` and `~/spoton`, neither of which has run `/hm:review` since the
seven-lens axis landed on 2026-08-16
**When** one `/hm:review` completes in each
**Then** `hm lens_coverage check` reports `missing: []` with all seven lenses exercised
**And** the resulting REVIEW frontmatter names no reviewer the dispatch did not produce
**And** the run's telemetry row carries a non-empty `lenses_exercised`.

---

## 🚫 Non-Goals

- **Fixing antigravity's empty responses.** AC-008 classifies and counts; the cause is behind the
  vendor CLI. Not in scope.
- **Retiring `ux-reviewer` / `performance-reviewer`.** RESEARCH Approach C. They are unreachable
  through `/hm:review` but still installed and referenced by `conditional_router.OPTIONAL_REVIEWERS`;
  removing them is a behaviour change across three rendered harnesses. Deferred.
- **Purging the ledger file.** AC-002 excludes at read time; the file stays append-only.
- **Restoring the cross-project instrumentation denominator.** AC-005 knowingly shrinks it.
- **A structural gate forbidding new reader-less writers.** AC-009/010 audit and remove once; the
  standing gate was offered and not chosen.
- **The eight structural failures in the base working tree.** Attributed to another session's
  uncommitted `execute.md.j2` work; 61 passed on a clean checkout of the same commit.

## ⚠️ Constraints

| Constraint | Value | Rationale |
|---|---|---|
| Test framework | `pytest` | CLAUDE.md 기술 결정 — not re-litigated |
| Language | Python 3.12+, no Bash | CLAUDE.md 기술 결정 |
| Ledger mutability | append-only; no rewrite | AC-002; another session may be reading concurrently |
| REVIEW loop state | must survive every `review_doc` mode | AC-006; rounds 2..N depend on it |
| Config compatibility | absent keys must resolve deterministically and announce once | CLAUDE.md checkpoint 6 (bidirectional mapper) + the absent-case failure class (count:8) |
| Concurrency | two other sessions were live during research; base `git status` is not stable | Work in the task worktree only |
| Detection | render-grep cannot see any of AC-001/003/004 | CLAUDE.md checkpoint 2 — the value differs from the artifact; gates must compare real outputs |

## ✅ Verification Criteria

| AC | Mode | Test / step |
|---|---|---|
| AC-001 | unit (property) + structural | `test_leaking_invoker_call_lands_in_tmp_path` (canary, no `base_root`, no `chdir`) and `test_no_test_module_bypasses_the_ledger_redirect` (AST). **Not** a before/after row count on the shared base ledger — see the amendment under AC-001 |
| AC-002 | unit | `test_excluded_slug_absent_from_second_opinion_aggregate` |
| AC-003 | structural | `test_routing_prose_names_only_dispatched_agents` — prose ∩ agents vs `lens_dispatch` |
| AC-004 | unit | `test_lens_coverage_reports_unstamped_without_blocking` |
| AC-005 | unit | `test_absent_instrumentation_key_resolves_false` |
| AC-006 | render | `test_review_doc_modes_render_expected_sections` (3 modes × section set) |
| AC-007 | unit | `test_review_doc_default_is_frontmatter_only_on_both_paths` |
| AC-008 | unit + integration | `test_agy_empty_response_has_distinct_skip_reason`; live rate from the ledger |
| AC-009 | structural | `test_every_observability_path_appears_in_the_audit` |
| AC-010 | structural | `test_no_module_writes_an_orphan_observability_path` |
| AC-011 | manual | run `/hm:review` once in each project; record the CLI JSON and the telemetry row |

## ❓ Open Questions

None blocking. Two handoffs to `/hm:plan`:

1. **Phasing order.** AC-001/002 are independent of everything else and unblock honest measurement
   for AC-008 — they likely come first. AC-006/007 are the largest single change.
2. **AC-011 sequencing.** It verifies the axis *and* exercises the AC-003/004/006 changes. Running it
   before the changes land gives a baseline; after, it gives acceptance. `/hm:plan` decides whether
   it is one manual step or two.

## 🔍 Refinement Decisions

- **Round 1** — lens stamp = advisory (not blocking, not Python-injected); ledger pollution = read-time
  exclusion via the existing `.ledger-exclusions.json` mechanism, no purge; scope = the three confirmed
  defects + antigravity + live verification, plus a new axis the operator raised: are the REVIEW document
  and the observability artifacts actually consumed, and can their cost be made optional.
- **Round 2** — audit answered the new axis: REVIEW is consumed (by frontmatter only) but has no size
  knob at all, while `instrumentation` exists and is on in `~/neuroTerm` without an opt-in. Decisions:
  instrumentation absent-key flips to `False`; a new `reviewers.review_doc` knob with three modes.
- **Round 3** — `review_doc` defaults to `frontmatter-only` on both the new-render and absent-key paths;
  the observability audit removes orphan writers rather than only reporting them.
- **Round 4** — concern raised and accepted: the REVIEW body is the auto-fix loop's state store, so
  `frontmatter-only` is defined as *frontmatter + loop-state sections*, never frontmatter alone.
