---
type: plan
task_slug: bench-study-adoption
status: complete
created: 2026-08-21
tags: [harness-maker, plan, python, review-stage, telemetry, reviewer-contract]
research_doc: "[[STUDY-ko]]"
interview_rounds: 6
adrs: 7
validator_outcome: MAJOR_REVISION_TERMINAL
surface_allowance:
  chars: 3817
  reason: "DECLARED, not measured — terminal plan-validation found this PLAN would block phases 2-4 mid-flight on the review ratchet with no escape its own Contract Boundaries permit. _ATOMIC_RATCHET review is 67008 with about 1340 characters of built-in 2 percent slack; this PLAN's estimate is about 1.2k of prose plus about 240 from appending --diff-files and --rev to six literal command lines across three logical sites. Phase 2 funds the Auto-Fix Step 4 pointer, the Step 4e authority row and the oracle-blocked exclusion in the fixable-finding filter; phase 3 funds the complexity invocation and the Size and Complexity report section, both Production-gated; phase 4 funds repo_probe transcription and the two new flags on both branches of the is_codex fence. The rule body for phase 2 lives in the targeted-test-selection skill, which neither ratchet measures. ONE round trip is declared per variant: Phase 3's Step 5c is its own call rather than a chain onto 5b, so that a record-only telemetry failure cannot take the churn measurement down with it. The delta doc named this case in advance as the one thing that would require the declaration. Every other phase adds arguments to invocations that already exist, never a new call site. RE-MEASURED 2026-08-22, replacing a declared 2600. The estimate was 2.6x low: measured growth is 3817 on the codex variant and 3810 on claude, not the 1.44k predicted. Two reasons, both recorded rather than smoothed over. First, the estimate predated the round-1 live review, whose repairs added prose the declaration could not have known about - chiefly the confirmation-pass re-derivation note. Second, and larger, the per-block estimates were simply short; each landed block is longer than guessed. The number here is now the measured one rather than a guess with margin, which is what the delta doc said would happen either way. execute is not expected to move; if it does that is a finding."
  delta_doc: BASELINE-DELTA-bench-study-adoption.md
  commands:
    review: 3817
  round_trips:
    review: 1
    hm-review: 1
summary: "Adopt four harness-bench STUDY prescriptions: fixer test-read, complexity telemetry, repo-access canary, fan-out note"
---

# PLAN — bench-study-adoption

## 🎯 Executive Summary

**TL;DR** — Four prescriptions from `Ecro/harness-bench` `docs/STUDY-ko.md` are real gaps in
this harness. Adopt them as four independent phases: a **doc-only** note about fan-out's
language-conditional payoff (D), a **prose-only** rule making the auto-fixer read the covering
test before it edits (A), **new telemetry** recording size and complexity change beside the
compliance verdict (B), and a **reviewer-contract change** that mechanically proves each lens
actually had repository access (C).

**Why** — the study prescribes across its own benchmark arms; the table below is **our audit
of this repository against those prescriptions**, not a finding of the study:

| Prescription | Our state before this PLAN |
|---|---|
| ⑤ fixer may read tests, not edit | We say "Run the tests, never edit one". **Running is not reading.** The self-refusal the study measured (build failures 4 rounds → 0) requires the read. |
| ⑥ record size/complexity beside compliance | **Zero.** No complexity metric anywhere in `src/`. `review_churn` measures churn only. Study: compliance identical 19/19 across 10 arms while complexity split −17% vs +58%. |
| ① reviewers get repo read access | Reviewers **have** Read/Grep/Glob, and 2026-08-20 landed the causation rule that depends on it. **Nothing verifies the access is live.** The study's canary caught three misdiagnoses. |
| fan-out caution | Our 7 lenses are Production-mandatory regardless of language. Study: +52% recall on Python, **no gain on C firmware** (43% vs 50%). |

**Two prescriptions were examined and deliberately rejected** — see ADR-000.

**Key decisions**: ADR-001 (Python-AST-only complexity), ADR-002 (dual sink), ADR-003
(`repo_probe` on all 7 Production lenses, failure ⇒ `missing`), ADR-004 (mandatory read +
mandatory self-refusal), ADR-005 (Production-only), ADR-006 (record the refusal on the
**authority** axis; the disposition vocabulary is not touched).

**Estimated impact** — one new module surface in `review_churn`, one contract field in the
reviewer output schema, one new `authority` value, ~1.2k characters of new `review.md.j2`
prose, and a doc note.

**This DOES change review's behaviour**, and the earlier draft of this line claiming otherwise
was wrong: a failed probe turns an exercised lens into `missing`, which blocks approval and
triggers a re-dispatch, and ADR-004 adds a branch in which a fix is refused rather than applied.
Both are new outcomes reachable on a normal run. They travel through existing mechanisms; that
is not the same as changing nothing.

## 📚 Prior Work

- **`work-docs/BASELINE-DELTA-review-scope-and-oracle.md` (2026-08-20)** — the immediately prior
  change. It landed the causation rule in `hard_rules.md.j2` and `targeted-test-selection` §4.5.
  **Phase A is the pre-emptive half of §4.5**: §4.5 classifies a targeted run that already went
  RED; A stops the class of fix that makes it go RED. They must not restate each other.
- **CLAUDE.md 제1목표** — prefer the simple, fast device. Every phase below is bounded by it;
  Phase D exists *because* the honest answer to fan-out routing is a note, not a mechanism.
- **wiki:747** — stage prose is the most expensive surface; skills are the sanctioned zero-cost
  escape. Phase A's rule body therefore goes where it is not measured, with a pointer in stage.
- **`[fail:design] absent-case = feature black hole` (count:8)** — the most recurring failure
  class in this repo. It is why ADR-002 chose two sinks and why ADR-005 rejected an opt-in flag.
- **`[fail:design] new-marker-content-field-must-update-every-reader` (count:3)** — three
  hand-maintained reader lists, all wrong. ADR-006's consequence section is written against it.
- Memory retrieval for this topic returned one candidate
  (`[wiki:architecture] per-session-marker-scoping`), unrelated. Recorded so the absence is a
  statement rather than an omission.

## 🎙️ Interview Transcript

| # | Topic | Category | Question | Options | Choice | Note | → ADR |
|---|---|---|---|---|---|---|---|
| 1 | Complexity metric scope | Dependencies | How wide should B's complexity calculation reach? | Python AST only / language-agnostic proxy / AST + plugin interface | Python AST only, LOC-only elsewhere | Rejected the plugin interface as generalisation with zero consumers | ADR-001 |
| 2 | Canary shape | Contract shape | Always-on `repo_probe` field, periodic health probe, or only on out-of-diff findings? | 3 options | Always-on `repo_probe` in lens JSON | The out-of-diff-only variant self-defeats: a reviewer that lost access produces zero out-of-diff findings | ADR-003 |
| 3 | Fixer test-read strength | Risk tolerance | Mandatory read + mandatory self-refusal, advisory, or delegate judgement to §4.5? | 3 options | Mandatory both | Advisory is unmeasurable; the study's effect came from the enforced refusal | ADR-004 |
| 4 | Preset gating for B and C | Scope boundaries | Production-only, both presets, or opt-in flag? | 3 options | Production mandatory, Side unrendered | Opt-in default-off is the absent-case black hole this repo has hit 8 times | ADR-005 |
| 5 | `repo_probe` failure semantics | Failure handling | Treat the lens as `missing`, warn only, or add an independent gate? | 3 options | Treat as `missing` | Reuses `lens_coverage`'s existing block/re-dispatch path; adds no second blocking reason | ADR-003 |
| 6 | Probe breadth | Scope boundaries | All 7 lenses, one per agent (4), or one? | 3 options | All 7 | Tool grants are per-agent and 4 agents back the 7 lenses; a per-agent sample also needs a representative-selection rule that breaks `lens_coverage`'s set comparison | ADR-003 |
| 7 | Complexity output sink | Observability | REVIEW section, jsonl, or both? | 3 options | Both | The study's conclusion came only from reading across 47 rounds; a report-only sink cannot produce that view | ADR-002 |
| 8 | Self-refusal disposition | Contract shape | New `blocked-by-oracle`, reuse `manual-only`, or extend `unresolved`? | 4 (incl. end-interview) | New `blocked-by-oracle` | Reusing `manual-only` conflates "no consensus" with "consensus but oracle-blocked" — opposite causes, opposite remedies | ADR-006 |
| 9 | Self-refusal disposition — **reopened** | Contract shape | The round-3 premise was refuted at source: the two enums are a deliberate alias, not independent declarations. Re-decide. | new `oracle-blocked` authority / add to the shared vocabulary / split the alias | `unresolved` + new `oracle-blocked` **authority** | Supersedes #8. Reversed because a cross-model second opinion refuted the premise, not because of pushback | ADR-006 (rewritten) |
| 10 | ADR-004 vs the existing tests-lens carve-out | Failure handling | `review.md.j2:813-817` already permits fixing a finding whose own target is the test. How do the rules coexist? | restate as non-trigger / apply only to non-test targets / defer Phase 2 | Restate the exception as an explicit non-trigger | Found by plan-validator; without it every `tests`-lens P0/P1 becomes permanently unfixable | ADR-004 (amended) |
| 11 | Phase 1 scope vs the CLAUDE.md line cap | Scope boundaries | This repo's CLAUDE.md is 612 lines against a 500 Production cap, and `context_lint` has no CLI entrypoint at all. | record the overage + use `wc -l` / Phase 1 owns 612→500 / build the CLI | Record the overage; `wc -l` as the criterion | Both alternatives are real work and out of scope. **The stated reason was wrong** — see the Phase 1 note: the cap is live via `readiness`, not inapplicable. The choice is unaffected; the accounting is | Phase 1 |

## 📐 Architecture Decision Records

### ADR-000: Two of the study's prescriptions are rejected, on the record
**Status:** Accepted (2026-08-21, via /hm:plan audit)
**Context:** The study ships eight prescriptions. Adopting the headline of each without checking
its stated preconditions would import two changes whose evidence does not apply here.
**Decision:** Explicitly reject ③ (*turn off the consensus filter*) and ⑧ (*do not trust a
churn-0 stopping criterion*), and record why, so a later reader does not re-derive them as gaps.
**Consequences:**
- ✅ ③'s evidence (false-positive discovery rate 6.8 vs real 3.4) is measured under a
  **file-scope** condition, and the study says on the same line that opening the repository
  inverts the correlation. Our reviewers have Read/Grep/Glob. Adopting ③ would remove the
  consensus filter on the strength of a number taken under the opposite condition.
- ✅ ⑧ does not apply because `rereview_churn_ratio` is **not our stopping criterion**. It is a
  skip-optimisation; `max_review_rounds` is the bound. On a contract-less task where churn grows
  (194→262→395 in the study) our gate simply never fires and the round cap stops the loop —
  which is the fallback the study recommends. No change needed.
- ⚠️ If reviewer repo access is ever removed, ③ becomes live again. Phase C's canary is what
  would make that condition visible.
**Rejected alternatives:** Adopting all eight — rejected because two would be changes made
against inapplicable evidence.
**Source:** Pre-interview audit.

### ADR-001: Complexity is computed from the Python AST only; other languages get LOC only
**Status:** Accepted (2026-08-21, via /hm:plan interview)
**Context:** The study measured complexity on Python and C. We must write the calculator.
**Decision:** Use the stdlib `ast` module for `.py` files (cyclomatic count, max nesting depth,
max function length). For every other extension record the LOC delta `review_churn` already
collects and emit `complexity: null` — an explicit null, never a zero.
**Consequences:**
- ✅ Zero new dependencies, fully deterministic, immediately valid on this repository.
- ⚠️ **The size half needs new git plumbing.** An earlier draft claimed `collect`/`_post_loc`
  already produce pre/post LOC; they do not. `FileChurn` carries `post_loc` **only** — the pre
  side exists as numstat added/deleted, which is not a line count. Phase 3 must read the pre-tree
  blob (a `_pre_loc` mirroring `_post_loc`) or state an explicitly-justified derivation. Scoped
  into Phase 3 rather than assumed away.
- ⚠️ A C or Rust consumer project sees LOC only. Accepted: an indentation-based proxy is wrong
  on brace languages, and it is not the metric that produced the study's −17% vs +58% split.
- ⚠️ `null` must be distinguishable from `0` in both sinks, or an unsupported language reads as
  a perfectly simple one.
**Rejected alternatives:**
- Language-agnostic indentation proxy — rejected: inaccurate exactly where it would be the only
  signal available.
- Pluggable per-language analyzer interface — rejected: an abstraction with one implementation
  and no second consumer, which CLAUDE.md 제1목표 names directly.
**Source:** Interview #1.

### ADR-002: Complexity/size deltas are written to BOTH the REVIEW report and an observability jsonl
**Status:** Accepted (2026-08-21, via /hm:plan interview)
**Context:** The study's conclusion — compliance flat while complexity diverged — is only
visible when reading across many rounds and tasks.
**Decision:** Each measured round appends one row to
`.claude/observability/review-complexity.jsonl` and renders a `## 📏 Size & Complexity` section
in `work-docs/REVIEW-{slug}.md`.
**Consequences:**
- ✅ The report answers "what did this round cost"; the jsonl answers "what is the trend", which
  is the question the study actually answered.
- ✅ Mirrors the existing `review_churn` oscillation two-sink pattern — no new concept.
- ⚠️ Two sinks means two writers to keep consistent. Bounded by making the jsonl row the single
  produced object and the report section a rendering of it.
- ⚠️ The jsonl is harness churn and MUST be added to `worktree._HARNESS_CHURN_PREFIXES` — it is
  under `.claude/observability/`, which is already covered by that prefix, so this is a
  verification item, not an edit.
**Rejected alternatives:** Report-only (no trend view — the point of the prescription);
jsonl-only (nobody reads it in the round where the cost was paid).
**Source:** Interview #7.

### ADR-003: Every lens returns a `repo_probe`; a failed probe makes that lens `missing`
**Status:** Accepted (2026-08-21, via /hm:plan interview)
**Context:** Reviewers were given repository access, and 2026-08-20's causation rule now depends
on it, but nothing verifies the access is live. The study reports that a one-minute canary
caught three misdiagnoses where "the setting did not apply" was indistinguishable from "the
model just behaves that way".
**Decision:** Under the Production preset (ADR-005 — Side renders no probe requirement at all,
and ADR-003's "every lens" is scoped by that), add a top-level `repo_probe: {path, line, text}`
to every lens's returned object —
one verbatim line from a file the diff does not touch. `lens_coverage.exercised_lenses` is
extended from an existence check to an existence-and-validity check: a result file whose
`repo_probe` is absent, quotes a file inside the diff, names a path not in `git ls-files`, or
whose `text` does not match that file's line on disk, does not count its lens as exercised.
**Consequences:**
- ✅ No new blocking gate. `missing` already blocks approval and the Auto-Fix Loop already
  re-dispatches missing lenses, so a transient formatting error costs one re-dispatch and a
  genuine access loss escalates to an unapprovable review at the round cap — the correct
  outcome, and the one the operator sees.
- ✅ All 7 lenses probe. Tool grants are per-agent and four agents back the seven lenses, so a
  sample would not observe the other agents' grants; a representative-selection rule would also
  break `lens_coverage`'s plain set comparison.
- ⚠️ `exercised_lenses` changes contract from "the file exists" to "the file is valid". Its
  docstring and every caller's expectation must be updated in the same change.
- ⚠️ **A diff that touches every tracked file has no out-of-diff file to quote.** The escape is
  `repo_probe: {status: "no-out-of-diff-file"}`, and the CLI **verifies** the claim against
  `git ls-files` minus the diff's file list — it is never taken on the reviewer's word.
- ⚠️ Reviewer agent bodies change ⇒ `content_hash` frontmatter moves ⇒ the `full_agent_md_sha256`
  pins move for every affected reviewer. Known, attributable cost (5 pins moved on 2026-08-20).
- ⚠️ **A tracked path is not a safe path.** A tracked symlink satisfies `git ls-files` while
  resolving outside the repository, so a naive "read that path on disk" makes the validator an
  arbitrary-file reader driven by model output. The validator therefore reads the **blob at the
  reviewed revision** (`git show <rev>:<path>`), never the working tree, and additionally
  rejects a resolved path outside the repository root. `line` and `text` are length-bounded.
**Rejected alternatives:**
- Periodic `/hm:health` probe — rejected: `/hm:health` is deterministic Python with no LLM
  dispatch path, so this needs a new axis, and a single sampled reviewer cannot detect a
  per-lens regression.
- Probe only when an out-of-diff finding exists — rejected as self-defeating: a reviewer that
  lost repository access produces exactly zero out-of-diff findings, so the check never runs in
  the case it exists to detect.
- An independent blocking gate — rejected: a second blocking reason beside `missing` creates a
  state needing both satisfied, for no additional detection.
**Source:** Interview #2, #5, #6.

### ADR-004: The auto-fixer must READ the covering test before editing, and must refuse rather than widen the fix
**Status:** Accepted (2026-08-21, via /hm:plan interview)
**Context:** Review's Auto-Fix Loop Step 4 says *"Run the tests, never edit one to make a finding
go away."* Running a test is not reading it. The study reports build failures falling from four
rounds to zero once the fixer could read the covering test and refuse on its own.
**Decision:** Before this round's first `Edit` on a file, the fixer reads the test(s) covering
it. If applying the suggested fix would require changing a test to pass, it does not apply the
fix. It **retags the finding `manual-only`** and records `disposition: unresolved` /
`authority: oracle-blocked` (ADR-006), then states the caller-side fact.

**AMENDMENT (execute, remedy #2 of the terminal validation).** The record above was decided
here, not in planning, because terminal validation found `review.md.j2:843-848` assigning the
opposite grade effect to an overlapping fact. Read at source, the two rules fire at different
times on the *same* fact: `:843-848` is Step 5, **after** a fix was applied, came back RED,
was classified unreachable by §4.5 and was **reverted** — and its record is one `manual-only`
P1 `spec_gap`, *"never grade-lowering, never authority to edit the test"*. ADR-004's refusal is
Step 4, **before** any edit, on the same discovery.

**The earlier discovery must not carry the harsher record.** If refusing early lowered the grade
while applying-failing-reverting did not, the fixer's rational move would be to skip the read —
which defeats the entire prescription this ADR exists to adopt. So the refusal takes `:843-848`'s
record verbatim: `manual-only`, not grade-lowering. Verified at source that this is sufficient —
`grade_from_findings` grades only `consensus-passed` findings (`review_consensus.py:285`), and
`review.md.j2:666` states plainly that `manual-only` does not lower the grade.

**The existing carve-out is an explicit NON-trigger, restated here verbatim in scope.**
`review.md.j2:813-817` already qualifies the ban it appears to make: *"You must not edit a test
file to resolve a finding whose target is not that test … But **a finding whose own target is
the test may be fixed**: `tests` is a mandatory lens and raises findings repairable only by
writing a test, so an unqualified ban leaves them `pending` → one non-progressing round → an
unapprovable review."* The refusal therefore fires **only when the test that would have to
change is not the finding's own target**. An earlier draft of this ADR quoted the rule as
unqualified and would have made every `tests`-lens P0/P1 permanently unfixable and permanently
grade-counting — the exact outcome that prose was written to prevent.
The **rule body lives in the `targeted-test-selection` skill**, with a pointer from
`review.md.j2` — wiki:747, and the same structure that cut the previous change's stage cost from
+900 to +512 characters.
**Consequences:**
- ✅ The `tests` lens keeps working: its findings target tests, so they never trip the refusal.
- ✅ Prevents the class of failure that `targeted-test-selection` §4.5 currently only classifies
  after it happens. §4.5 stays untouched and is cited, not restated.
- ✅ Cheaper than the alternative the study compares it against (widening the oracle target).
- ⚠️ Adds a few Read calls per round. Accepted.
- ⚠️ A fixer that cannot locate a covering test must not treat "no test found" as permission.
  The absent case is `unresolved` / `oracle-blocked` with the reason `no covering test located`, so it
  surfaces rather than silently proceeding — `[fail:design] absent-case` (count:8).
**Rejected alternatives:**
- Advisory wording — rejected: unmeasurable, and the study's effect came from the enforced
  refusal, not from the reading.
- Delegating the judgement to §4.5 — rejected: §4.5 is post-hoc classification of a RED run;
  reusing it as a pre-hoc predicate would require rewriting it and would couple two rules that
  are currently independent.
**Source:** Interview #3.

### ADR-005: Phases B and C render in Production only; Side does not render them
**Status:** Accepted (2026-08-21, via /hm:plan interview)
**Context:** `lens_coverage` and `second_opinion` are already Production-gated. Side exists to be
fast.
**Decision:** Both the complexity measurement and the `repo_probe` requirement render only when
`config.preset == Production`. Phase A's rule renders in both — it is prose with no runtime cost
and it prevents a defect rather than measuring one.
**Consequences:**
- ✅ Consistent with every existing measurement gate in this stage.
- ⚠️ Side users get no complexity trend and no access canary. Accepted: Side's reviewers have the
  same tool grants, so the risk is unobserved rather than higher.
- ⚠️ **The Python validator needs its own Side branch — the render gate is not enough.** All
  three rendered `hm lens_coverage check` sites pass `--preset {{ config.preset }}`
  unconditionally, and `lens_coverage.main`'s `--preset` resolves an unknown value to
  Production because "more mandatory coverage is the fail-closed side". So a Side review, whose
  reviewers correctly emit no `repo_probe`, would hit invalidity mode #1 (absent field) on every
  lens: `missing` = the full mandatory set, `blocks_approval: true`, CHANGES_REQUESTED at the
  round cap, **every Side review, permanently.** Under `--preset Side` the probe check is
  therefore **skipped entirely** — an absent `repo_probe` is not an invalidity mode there. A
  render-absence assertion cannot detect this; Phase 4 carries a Side integration test instead.
- ⚠️ Render tests must assert the **absence** in Side, not only the presence in Production — a
  presence-only test passes on a template that renders it unconditionally.
**Rejected alternatives:**
- Both presets — rejected: contradicts Side's stated purpose for a signal Side users have little
  reason to read.
- `harness.yaml` flag defaulting off — rejected outright: a default-off instrument is never
  turned on. This repo's most-recurring failure class.
**Source:** Interview #4.

### ADR-006: The oracle-blocked refusal is recorded on the `authority` axis; the disposition vocabulary is untouched
**Status:** Accepted (2026-08-21, via /hm:plan interview round 4, after a cross-model second
opinion refuted the premise of the round-3 decision)
**Context:** Round 3 locked "add `blocked-by-oracle` to `review_consensus.DISPOSITIONS` only,
letting the two disposition enums diverge". **That premise was false**, and reading the source
proved it: `review_consensus.py:26,40` does `from harness_maker.codex_ledger import
DISPOSITION_VALUES` / `DISPOSITIONS = DISPOSITION_VALUES`. It is a deliberate alias, and the
comment at that line records that the *previous* state — three independent literals behind a
comment claiming a single source — was the defect the consolidation fixed.
`review_telemetry.py:159` validates against the same frozenset. The round-3 option would have
undone that consolidation with no new evidence for doing so.
**Decision:** Add no disposition value. A fix refused because passing would require editing a
test is recorded as `disposition: unresolved` with a **new authority value `oracle-blocked`**,
which — like the existing `no-contract` — is legal only in combination with `unresolved`.
**Consequences:**
- ✅ Zero readers break. `DISPOSITIONS`, `LedgerRow.disposition` and
  `review_telemetry.disposition_counts` are all unchanged, so this repo's count:3
  "new enum value must reach every reader" failure class is not entered at all.
- ✅ `grade_effect("unresolved")` already returns `counted: True` and `human_review_needed` for
  severe findings — exactly the intended treatment, with no new branch.
- ✅ `_authority_kind` already distinguishes `no-contract` from `ac`/`docstring`/`none`, so
  adding a fourth kind is in-grain rather than a new axis. `validate_disposition`'s existing
  rule ("this authority kind pairs only with `unresolved`") extends verbatim.
- ✅ The set of `oracle-blocked` findings remains a free SPEC audit, in the same family as the
  oscillation signal — the property that motivated a distinct value survives.
- ⚠️ "Consensus reached but the oracle blocks the fix" now requires reading two columns rather
  than one. Accepted: the authority column exists precisely to carry the reason a finding could
  not be adjudicated, and `no-contract` already sets that precedent.
- ✅ **AMENDED at execute (remedy #2).** The planning draft said an oracle-blocked severe
  finding *should* hold the review at CHANGES_REQUESTED permanently, and called that intended.
  ADR-004's amendment refutes it: the same fact discovered one step later is explicitly
  never-grade-lowering, so making the earlier discovery grade-lowering rewards not reading the
  test. The refusal now **retags to `manual-only`**, which settles both harms at once and
  needs no new machinery:
  - *Wasted rounds* — Step 3's fixable-finding filter already requires `Tag = consensus-passed`
    (`review.md.j2:791-794`), so a retagged finding is excluded **by the existing filter**. No
    new disposition-based filter, and no requirement that `authority` survive the round merge:
    the carrier is `tag`, which the merge already preserves. **R10 and R13 are both dissolved.**
  - *Grade* — `manual-only` is excluded from `P0_count`/`P1_count` by the rule stated at
    `review.md.j2:666` and enforced at `review_consensus.py:285`. `grade_effect` is untouched,
    exactly as Contract Boundaries requires.
  - The `oracle-blocked` authority still carries **why** this finding is `manual-only`,
    distinguishing it from an ordinary single-voice one. That is the whole reason the authority
    axis was chosen over a disposition value.
**Rejected alternatives:**
- `blocked-by-oracle` in the shared vocabulary — rejected: it puts a value in the PIDA ledger's
  enum that the ledger can never emit, leaving a permanently-zero key in `disposition_counts`.
- Splitting the two vocabularies (the round-3 decision) — rejected on the corrected facts: it
  reverses a deliberate consolidation whose stated purpose was to stop the rejection rate
  splitting silently between two producers, and nothing in this task supplies a reason to.
- `manual-only` — rejected as malformed: that is a value on `review_consensus.Tag`, the
  **consensus** axis, not the disposition axis.
**Source:** Interview #8 (superseded) and Interview #9; source verification of
`review_consensus.py:20-45`, `codex_ledger.py:243-245`, `review_telemetry.py:154-159`.

## 🏗️ Technical Design

### Current state

- `src/harness_maker/lens_coverage.py` (189 lines) — `exercised_lenses(round_dir, run_id)`
  returns the set of lenses whose result file exists, **parses as JSON, is a dict, and
  self-identifies** — `payload["lens"] == stem` and `payload["run_id"] == run_id`, fail-closed on
  each (`:50-59`). So the shift ADR-003 makes is narrower than existence→validity: it is
  self-identification → self-identification **plus an out-of-diff evidence claim**, inserted into
  the existing continue-on-mismatch loop. It is called by `coverage_verdict()` (`:84`), by `main()`, and directly by tests;
  the rendered stage invokes `hm lens_coverage check` at **three** sites in `review.md.j2`
  (Step 3, the Auto-Fix Loop re-check, and the confirmation pass).
- `src/harness_maker/review_churn.py` (606 lines) — `FileChurn` / `ChurnMeasurement`,
  `collect(root, pre_ref, post_ref)`, `_post_loc`, `measure_refs`, plus the oscillation
  detector and its `record_oscillations` jsonl sink. **`FileChurn` carries `post_loc` only** —
  there is no pre-tree line count, only numstat added/deleted. Pre/post refs are already pinned per round
  by review's Step 3b (`r{N}-pre` / `r{N}-post`).
- `src/harness_maker/review_consensus.py` — `Tag` (consensus axis) is local; `DISPOSITIONS` is
  an **alias of `codex_ledger.DISPOSITION_VALUES`**, deliberately consolidated and also imported
  by `review_telemetry`. `_authority_kind` returns `ac | docstring | no-contract | none |
  unknown`; `validate_disposition` pairs `no-contract` with `unresolved` only.
- `src/harness_maker/templates/agents/_partials/finding_schema.md.j2` — the shared per-finding
  envelope. `repo_probe` is **top-level, not per-finding**, so it does not belong here.
- `src/harness_maker/templates/stages/review.md.j2` — Step 3 (dispatch + result-file write),
  Step 4e (disposition table), Auto-Fix Loop Step 4 (apply).
- `src/harness_maker/templates/skills/targeted-test-selection/SKILL.md.j2` — 163 source lines,
  cap 300 (`context_lint.THRESHOLDS[("skill", "Production")]`). Headroom exists.

### Affected components

| Component | Phase | Change |
|---|---|---|
| `CLAUDE.md`, `.claude/memory/wiki.md` | D | Fan-out language-conditionality note |
| `templates/skills/targeted-test-selection/SKILL.md.j2` | A | New §5 — read-before-fix + refusal |
| `templates/stages/review.md.j2` Auto-Fix Step 4 | A | Pointer to §5 |
| `review_consensus.py` | A | `oracle-blocked` authority in `_authority_kind` + `validate_disposition`; **no** change to `DISPOSITIONS` or `grade_effect` |
| `templates/stages/review.md.j2` Step 4e | A | New authority row; fixable-selection exclusion for `oracle-blocked` |
| `review_churn.py` | B | `complexity.py` sibling or new section; per-file AST metrics |
| `cli` / `hm review_churn complexity` | B | New subcommand over pinned refs |
| `command_registry.py` | B | `complexity` added to the `review_churn` verb allowlist |
| `templates/stages/review.md.j2` Step 3b/5 | B | Measure call + `## 📏 Size & Complexity` |
| `lens_coverage.py` | C | Validity check + diff-file list input |
| reviewer agent bodies (7 lenses / 4 agents) | C | `repo_probe` in the return contract |
| `templates/stages/review.md.j2` Step 3 | C | Transcribe `repo_probe`; pass diff list to CLI |

### Dependencies

None added. `ast` is stdlib.

### Data flow — Phase C

```
lens agent  ──returns──►  {findings: [...], repo_probe: {path,line,text}}
                                   │
main loop writes result file, adding lens + run_id
                                   │
                                   ▼
hm lens_coverage check --diff-files <list>
   ├─ file exists + run_id matches      (existing)
   └─ repo_probe valid                   (NEW)
        ├─ path ∈ git ls-files
        ├─ path ∉ diff files
        └─ text == that file's line N on disk
              └─ OR status == "no-out-of-diff-file", verified against ls-files − diff
                                   │
                      exercised / missing  ──►  blocks_approval  (unchanged)
```

### Data flow — Phase B

```
r{N}-pre ref ──┐
               ├─► review_churn.collect (existing: name-status + numstat + post LOC)
r{N}-post ref ─┘             │
                             ▼
                  per-file: LOC delta        (existing)
                          + AST metrics      (NEW, .py only; null otherwise)
                             │
              ┌──────────────┴──────────────┐
              ▼                             ▼
   .claude/observability/           REVIEW-{slug}.md
   review-complexity.jsonl          ## 📏 Size & Complexity
   (one row per round)              (renders that row)
```

### API changes

- `lens_coverage.exercised_lenses` gains a required keyword argument carrying the diff's file
  list and the reviewed revision, and its contract becomes existence-and-validity.
  **Required, not defaulted** — a default would let a missed caller silently skip the probe
  check, which is the exact shape of
  `[fail:design] new-marker-content-field-must-update-every-reader`.
- **Every consumer, enumerated** (the second opinion caught this list being one entry long):
  `coverage_verdict()` at `lens_coverage.py:84` must thread the argument through and therefore
  changes signature too; `lens_coverage.main()`; the direct unit-test callers; and **all three**
  `hm lens_coverage check` invocations in `review.md.j2` — Step 3, the Auto-Fix Loop re-check,
  and the confirmation pass — which are **six literal command lines**, because each site is
  rendered twice behind an `{% if is_codex %}` / `{% else %}` fence (`review.md.j2:258/260`,
  `:767/769`, `:971/973`). An executor counting to three edits the Claude branch of each and
  leaves all three Codex renders unflagged. A missed stage call site is the failure mode, because
  a re-check without the flag would readmit a lens the first check rejected — and the Codex-only
  variant of that is CLAUDE.md's documented `is_codex` incident, which no Claude-branch render
  test can see. Phase 4's render assertion must check **both** branches.
- `hm lens_coverage check` gains `--diff-files <path>` and `--rev <sha>`, both **required under
  Production**. An absent `--diff-files` must be an error, never an empty set: an empty diff list
  makes `path ∉ diff_files` true for every path, which silently turns the whole check into a
  no-op — the absent-case black hole, arriving through the CLI instead of the config.
- `hm review_churn complexity --pre <ref> --post <ref>` — new subcommand.
- `review_consensus` gains an `oracle-blocked` **authority** kind. `DISPOSITIONS`,
  `codex_ledger.DISPOSITION_VALUES` and `LedgerRow.disposition` are **unchanged** (ADR-006).

## 📝 Implementation Plan

### Phase 1 — D: record fan-out's language conditionality — **DONE**

- `depends_on`: []
- `parallel_group`: `serial-docs`
- `merge_hazards`: none
- **Scope in**: `CLAUDE.md`, `.claude/memory/wiki.md`
- **Scope out**: every template, every module. **No runtime change.**
- **Content**: our 7 lenses are Production-mandatory regardless of language; the study measured
  +52% recall on a Python codebase and **no gain** on C firmware (43% fan-out vs 50% single) at
  equal budget. We have no data to route on, so this is recorded, not acted on. State that
  explicitly, so a later reader does not read the silence as an unexamined gap.
- **Exit criterion**: `rg -n "fan-out|팬아웃" CLAUDE.md .claude/memory/wiki.md` shows the note in
  both, and `wc -l CLAUDE.md` grows by no more than 12 lines.
  > **`context_lint` is deliberately NOT the criterion.** An earlier draft invoked
  > `python -m harness_maker.context_lint`; that module has **no `main()` and no
  > `__main__` block**, so the command exits 0 having printed nothing — a green light wired to
  > nothing. That half is verified and stands.
  >
  > **CORRECTED at the Phase 4 re-render — the cap DOES apply.** This note used to say it did
  > not, on the reasoning that `context_lint` lints rendered assets while this repo's
  > `CLAUDE.md` is source. Wrong: `readiness._dim_context_quality:413-414` lints
  > `project_dir / "CLAUDE.md"` against `_CONTEXT_LIMITS[("CLAUDE.md", preset)]`, and
  > `make . --update` reported `[P1] context_quality :: 612 lines vs 500 limit (Production)` out
  > loud. Enforcement runs through the readiness scan, not through a `context_lint` CLI — a
  > different fact from the one asserted, and the assertion was never checked against a run.
  >
  > **The decision stands; the reasoning does not.** Interview #11 chose to record the overage
  > rather than have this phase own a 612→500 trim, and that choice is unaffected. What changes
  > is the honest accounting: Phase 1 added 12 lines to a file already 100 over, and this repo's
  > readiness scan reports it P1 on every run. The 112-line overage is not this phase's
  > creation; 12 of it now are.
- **Risk**: low
- **Rollback**: revert the two files; nothing depends on them.

### Phase 2 — A: fixer reads the covering test; the `oracle-blocked` authority — **DONE**

- `depends_on`: []
- `parallel_group`: `serial-review-md` *(every phase from 2 on edits `review.md.j2`)*
- `merge_hazards`: `src/harness_maker/templates/stages/review.md.j2`;
  `tests/structural/test_command_size_budget.py` (`_ATOMIC_RATCHET["review"]`, currently 67008)
- **Scope in**: `templates/skills/targeted-test-selection/SKILL.md.j2` (new §5),
  `templates/stages/review.md.j2` (Auto-Fix Step 4 pointer; Step 4e authority row; exclusion of
  the refusal **retags the finding `manual-only`**, which Step 3's existing
  `Tag = consensus-passed` filter at `review.md.j2:791-794` already excludes — no new filter and
  no merge-preservation requirement, see ADR-004's amendment), `review_consensus.py`
  (`_authority_kind` + `validate_disposition` only), tests
- **Scope out**: `DISPOSITIONS`, `codex_ledger.DISPOSITION_VALUES`, `LedgerRow.disposition`,
  `grade_effect` (ADR-006 — all deliberately unchanged); `targeted-test-selection` §4.5 (cited,
  not edited)
- **Exit criterion**: `uv run pytest tests/unit/test_review_consensus.py tests/render tests/structural -q` green — **`tests/render` in full, not only the skill's own render test**, because this phase edits `review.md.j2` and a skill-scoped selection would not compile it. Includes: a unit test that `oracle-blocked` validates on `unresolved` and is **rejected** on `accepted`/`rejected`/`duplicate`; a structural test asserting `DISPOSITIONS is codex_ledger.DISPOSITION_VALUES` still holds (the alias is now load-bearing and undocumented drift would re-split it); a render assertion that the exclusion instruction is present; and the rendered skill within `THRESHOLDS[("skill","Production")]`.
- **Risk**: medium — the fixable-selection exclusion is the part that, if missed, burns the round cap.
- **Rollback**: Phase 1.

### Phase 3 — B: size and complexity telemetry — **DONE (verification in flight)**

- `depends_on`: [2]  *(ordering only — same file, avoid a self-inflicted conflict)*
- `parallel_group`: `serial-review-md`
- `merge_hazards`: `review.md.j2`; `_ATOMIC_RATCHET["review"]`
- **Scope in**: `review_churn.py` (or a `complexity.py` sibling if `review_churn` would exceed a
  reasonable module size), **a `_pre_loc` reader mirroring `_post_loc`** (ADR-001 — the pre-tree
  line count does not exist today), the CLI subcommand **and its jsonl writer**, `review.md.j2`
  measure call + `## 📏 Size & Complexity` section, **`command_registry.py`** (add `complexity`
  to the `review_churn` verb tuple — without it the verb is unreachable), tests
- **Scope out**: any gate or threshold on the new numbers — ADR: **record only**. The study
  supplies no threshold, and inventing one would be the "device that costs more than it
  protects" 제1목표 warns about.
- **Exit criterion**: three assertions, not one — (a) `hm review_churn complexity --pre <ref>
  --post <ref>` emits a row carrying a **pre and post** LOC, an AST metric set for `.py`, and an
  explicit `null` for other extensions, with a unit test proving `null ≠ 0` survives both sinks.
  **(a) must invoke the CLI, not the library** — `command_registry.py:146` declares
  `"review_churn": ModuleSpec("manual-dispatch", _s("measure", "pin", "oscillation"))` and
  `guard_or_none` runs before argparse, so an unregistered `complexity` verb is intercepted and
  the subcommand is unreachable. A library-level test would pass over a dead verb;
  (b) an **integration** test that running the command appends exactly one row to
  `.claude/observability/review-complexity.jsonl` carrying slug and round identity; (c) a
  **render** assertion that the Production `review.md.j2` actually contains the invocation and
  the `## 📏 Size & Complexity` section, and that the Side render contains neither. Without (b)
  and (c) the phase can pass with both sinks disconnected — a working calculator nothing calls.
- **Risk**: medium — new module surface; the AST metrics must be deterministic across runs.
- **Rollback**: Phase 2.

### Phase 4 — C: repo-access canary — **BLOCKED at the Phase A.5 gate**

> **Blocker (2026-08-21, execute).** The A.5 two-round budget is spent; round 2 returned FAIL
> with one blocking issue and no other defect. Nothing of Phase 4 is implemented — A.5 gates
> the implementation, so `lens_coverage` holds only a `ProbeCheck` skeleton that ignores its
> argument. Phases 1-3 are unaffected and green.
>
> **The finding, and it is correct.** No test distinguishes an implementation that reads
> `git show <rev>:<path>` from one that reads the working tree: every fixture commits once and
> never mutates, so the two byte-identical sources make the two implementations produce
> identical verdicts. "Reads the blob at `--rev`, never the working tree" is a gating clause of
> this phase's own exit criterion and the entire basis of R11 — and it is untested. The R11
> tests in `test_lens_repo_probe.py` inject `read_blob`, so they say nothing about the real
> read path.
>
> **This is the third instance of one confound class in this phase**: an assertion passing for
> a reason unrelated to the property it claims. Round 1 caught the other two (the R11 fixture
> rejected via untracked-path, and the empty-diff test failed via unreadable blob). That the
> same shape recurred after being named twice is the reason the two-round budget exists, and
> the reason this escalates rather than being repaired on a third pass.
>
> **The remaining fix looks small** — one CLI test that mutates the working tree without
> committing, so a good-at-`rev` probe would be wrong-on-disk. That is precisely the claim the
> budget exists to distrust, so it is the operator's call, not this stage's.
>
> `[boundaries] comparison not performed — blocked exit`
>
> **UNBLOCKED by operator, 2026-08-21 — Path A, closed scope.** One A.5 round beyond the
> two-round budget is authorized, and its input is a **closed list: S12 only**. The round admits
> **no new findings**; it verifies that one scenario and returns. The exception is recorded here
> rather than left implicit because breaking a budget rule silently is how the rule stops
> existing — and because `stuck` named the thing that makes this exception different from every
> round-3 request, which is the closed scope, "and that distinction is only real if you enforce
> it."
>
> **What Path A knowingly does not buy:** the confound *class* stays alive. `_repo()`'s
> single-commit-clean-tree shape is what made three instances possible in this phase, and
> closing S12 closes one instance. Path C — making the CLI structurally incapable of reading the
> working tree, with an import-graph gate instead of a behavioural fixture — is the durable fix
> and is opened as a follow-up below, not smuggled into this round.

### Follow-up (not this task): kill the read-path confound class structurally

`stuck` judged this the better engineering answer and declined to recommend it only on scope
timing. It needs `/hm:plan` to amend Phase 4's **Scope in**, so it is named here and left there.

The shape: the probe validator's only read path becomes a single git-backed `read_blob` factory
injected at one seam, plus a structural test asserting no other file-open path exists in
`lens_coverage`'s probe validation. The behavioural fixture then becomes redundant rather than
load-bearing. This matches what this repo has learned three times over — `[fail:design]
new-marker-content-field-must-update-every-reader` was fixed twice with better hand lists before
`test_autopilot_marker_api_session_key.py` and `test_is_codex_matches_output_path.py` replaced
enumeration with an import-graph gate.

- `depends_on`: [3]  *(ordering only — same file)*
- `parallel_group`: `serial-review-md`
- `merge_hazards`: `review.md.j2`; `_ATOMIC_RATCHET["review"]`; the reviewer agents'
  `full_agent_md_sha256` pins; `tests/snapshot` `body_sha256` values
- **Scope in**: the reviewer return contract (top-level, **not** `finding_schema.md.j2` — that
  partial is the per-finding envelope), `lens_coverage.py`, `hm lens_coverage check
  --diff-files`, `review.md.j2` Step 3, tests, re-pinned SHAs
- **Scope out**: `finding_schema.md.j2`; any second blocking gate
- **Exit criterion**, and the last item is **gating, not advisory**: a unit test proves each of
  the five invalidity modes (absent field, in-diff path, untracked path, text mismatch,
  symlink/out-of-root resolution) yields `missing` for that lens; the `no-out-of-diff-file`
  escape is accepted **only** when `git ls-files` minus the diff list is empty; the validator
  reads the blob at `--rev`, never the working tree; Side renders no probe requirement; every
  moved SHA pin carries an attribution comment; **and one real `/hm:review` on this repository
  shows all seven live lenses producing passing probes.**

  > **OPERATOR OVERRIDE (2026-08-21, execute): a failing live run does NOT revert the phase.**
  > The clause this replaces said it did. The user directed otherwise when the gate was still
  > ahead of us — before its result was known, which is what makes this a policy decision rather
  > than a reaction to a red light.
  >
  > **What does not change: the run still happens, and its result is still recorded.** The
  > override governs the disposition of a failure, not whether the evidence is gathered. A
  > failing run therefore ships Phase 4 with R1 **live and named** — the probe contract would be
  > in force while unproven against real reviewers, and `/hm:review` on a Production harness
  > could be unapprovable until the contract is loosened. That is the risk being accepted, said
  > plainly here so the next reader inherits it rather than rediscovering it.
  >
  > Reverting is still the remedy if the run fails; it is now a **follow-up decision** the
  > operator makes with the result in hand, not an automatic consequence.
- **Risk**: high — changes a contract seven dispatches depend on, and a wrong validator makes
  every review unapprovable.
- **Rollback**: Phase 3.

## 🚧 Contract Boundaries

### Do not change

- `src/harness_maker/codex_ledger.py` — ADR-006: `DISPOSITION_VALUES` and
  `LedgerRow.disposition` are the shared disposition vocabulary. `review_consensus.DISPOSITIONS`
  aliases the former **on purpose**; this task adds no member and does not un-alias it.
- `src/harness_maker/templates/agents/_partials/finding_schema.md.j2` — `repo_probe` is a
  top-level return field, not a per-finding one; editing this partial would put it on every
  finding.
- `src/harness_maker/templates/skills/targeted-test-selection/SKILL.md.j2` — its §4.5 is cited by
  Phase 2, never restated. It classifies a RED run after the fact; Phase 2 prevents one.
- `src/harness_maker/templates/agents/_partials/hard_rules.md.j2` — the 2026-08-20 causation
  rule is settled; this task does not reopen it.
- `src/harness_maker/review_consensus.py` — `Tag` and `DISPOSITIONS` are both untouched. Only
  `_authority_kind` / `validate_disposition` gain the `oracle-blocked` authority.
- `src/harness_maker/review_consensus.py` — `grade_effect` is untouched; `unresolved` already
  yields the intended `counted` / `human_review_needed` result.
- `surface_baseline.json` — a ratchet is never rebaselined by its own subject; growth is folded
  with a BASELINE-DELTA attribution document. (The rule is
  `PLAN-surface-ratchet`'s ADR-010, not one of this PLAN's — stated self-containedly here
  because an unresolvable citation on the highest-likelihood risk invites exactly the
  improvisation it forbids.)
- Advisory: no phase adds a threshold, gate, or automatic action on the complexity numbers.
- Advisory: `blocks_approval` keeps exactly one meaning — a lens did not deliver a usable
  result. Phase 4 widens what "usable" means; it does not add a second reason.

### Execution notes — what the phases actually cost

Recorded here because three of them contradict what the PLAN predicted, and a PLAN whose
predictions are silently overwritten teaches nothing.

- **Phase 0** (the terminal validation's remedy #1) landed first and unblocked the rest:
  `surface_allowance` + this delta doc. `command_headroom(review)` returns 2600.
- **Remedy #2 reversed an ADR consequence.** ADR-006 had said an oracle-blocked severe finding
  *should* hold the review at CHANGES_REQUESTED permanently. Reading `review.md.j2:843-848` at
  execute time refuted it: the same fact discovered one step later is explicitly
  never-grade-lowering, so the harsher early record would reward not reading the test. The
  refusal now retags `manual-only`, which dissolved **R10 and R13** with no new machinery.
- **Round trips DID increase**, against ADR-002's declaration of none. Phase 3's Step 5c is its
  own call, deliberately — see the delta doc. `review` 38 → 39 in the hand table,
  `round_trips: {review: 1, hm-review: 1}` in the allowance.
- **`guard_or_none` does not gate an unregistered verb.** Terminal validation said it does;
  `misroute_guard` is fail-open and redirects only for another module's verb. The registry entry
  is still required, enforced by `test_every_documented_subcommand_is_registered` instead.
- **`INTEGRATION=1` was mis-scoped** on the CLI test — CLAUDE.md:136 reserves it for external
  APIs. Phase A.5 blocked; the ungated in-process test is now the primary verifier.

## 🧪 Testing Strategy

**Unit**
- `review_consensus`: `oracle-blocked` is a legal **authority** on `unresolved` and is
  **rejected** on `accepted` / `rejected` / `duplicate`; `DISPOSITIONS` is untouched and
  `grade_effect("unresolved")` already returns `counted: True` with `human_review_needed` for
  P0/P1, so no `grade_effect` change is asserted.
- `lens_coverage`: **five** invalidity modes — absent field, in-diff path, untracked path, text
  mismatch, and **symlink / out-of-root resolution** (the R11 case; naming it explicitly because
  a bullet saying "four" would leave the security-relevant mitigation untested while three other
  sections report it covered). Plus the verified `no-out-of-diff-file` escape and its rejection
  when out-of-diff files do exist. Plus a **`--preset Side` case**: probe-less result files still
  count as exercised.
- complexity: AST metrics on a fixture; `null` for `.c`/`.md`; determinism across two runs;
  `null` distinguishable from `0` in both sinks.

**Structural**
- An **alias-invariant** test asserting `review_consensus.DISPOSITIONS is
  codex_ledger.DISPOSITION_VALUES` (ADR-006). The alias is now load-bearing: this task chose the
  authority axis precisely because the vocabulary is shared, and a later un-aliasing would
  silently reopen the split this decision avoided.
- Side-preset **absence** assertions for the Phase 3 and Phase 4 renders (ADR-005).

**Render**
- `targeted-test-selection` stays within `THRESHOLDS[("skill", Preset.PRODUCTION.value)]` — read
  from the table, never a literal. A hardcoded `150` in this exact test drifted for three
  minor versions and was corrected on 2026-08-20.
- `_ATOMIC_RATCHET["review"]` updated **once, at the end**, with the per-phase attribution split
  out. `execute` is not expected to move; if it does, that is a finding.

**Integration**
- One end-to-end `lens_coverage check` over a fixture results directory containing one valid and
  one probe-invalid lens, asserting `blocks_approval: true` and the invalid lens in `missing`.

**Manual**
- One real `/hm:review` on this repository after Phase 4, confirming the seven live reviewers
  actually produce passing probes. **This is the only evidence that the contract change is
  answerable by the agents** — every automated test above uses fixtures the reviewers did not
  write. Skipping it ships a contract nobody has demonstrated a reviewer can satisfy.

## ⚠️ Risks & Mitigation

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R1 | `repo_probe` makes every review unapprovable because reviewers cannot reliably satisfy the format | medium | high | The Phase 4 manual run still runs and its result is still recorded. **It no longer auto-reverts** (operator override, 2026-08-21) — so on a failing run this risk ships LIVE, and the remedy becomes a follow-up decision rather than an automatic one. Stated as accepted, not mitigated. |
| R2 | The new disposition value misses a reader | medium | high | ADR-006's discovering structural test. This exact class has recurred three times and each hand list was wrong. |
| R3 | Surface ratchet blocks the change | high | low | Expected. Fold once, at the end, with a BASELINE-DELTA attribution document. Never rebaseline to go green. See Contract Boundaries for the rule, stated without a cross-PLAN ADR number. |
| R4 | `exercised_lenses`'s new argument is defaulted by a later caller, silently skipping the probe check | low | high | Required keyword-only; a defaulted variant is explicitly forbidden in the design. |
| R5 | Phase 3 complexity metrics are non-deterministic (dict ordering, path ordering) | low | medium | Determinism test comparing two runs byte-for-byte; sorted output. |
| R6 | Phases 2–4 all edit `review.md.j2` and conflict | medium | low | Single `serial-review-md` group; strictly sequential; `depends_on` encodes the ordering even where there is no logical dependency. |
| R7 | The study's evidence is thinner than its headlines (author-as-judge, 17 reversals, n=1.25 for the full-prescription arm) | certain | medium | Phases are ordered cheapest-first. If the evidence is discounted further, Phases 1–2 are still cheap and Phases 3–4 can be dropped without touching them. |
| R8 | Phase 2's rule and §4.5 drift into contradiction | low | medium | §4.5 is in Contract Boundaries. Phase 2 cites it and must not restate it. |
| R9 | Reviewer SHA pins and snapshots move, hiding an unintended change | medium | medium | Verify exactly the expected agent set moved, and attribute each; the 2026-08-20 precedent (5 pins, `code-verifier` correctly absent) is the template. |
| R10 | ~~An `oracle-blocked` finding is re-selected every round~~ | — | — | **DISSOLVED at execute.** The refusal retags to `manual-only`, and Step 3's existing `consensus-passed` filter excludes it. Kept in the register rather than deleted: the risk was real against the planning draft, and a reader comparing PLAN to REVIEW needs to see why it stopped existing. |
| R13 | ~~The exclusion never fires because `authority` does not survive the round merge~~ | — | — | **DISSOLVED at execute**, by the same amendment: the carrier is `tag`, which the round merge already preserves, so there is no new field to keep alive. |
| R11 | The canary validator is driven by model-supplied paths and becomes an arbitrary-file reader via a tracked symlink | low | high | ADR-003: read the blob at the reviewed revision, reject paths resolving outside the repo root, bound `line`/`text` length. Found by the cross-model second opinion, not by our own review. |
| R12 | Phase A's rule is prose a fixer can satisfy by reading an irrelevant test, or by claiming none was located | medium | medium | **Accepted risk, not mitigated.** The machine-observable part is the disposition/authority pair the refusal produces; the read itself is not traced. A read-before-edit receipt was considered and deferred — it is a new observability axis, and the study's own measured effect came from prose-level instruction. Revisit if `oracle-blocked` counts look implausibly low. |

## ✅ Success Criteria

- [x] Fan-out's language conditionality is stated in `CLAUDE.md` and `wiki.md`, with the explicit
      note that we are recording rather than routing.
- [x] The auto-fixer reads the covering test before its first edit on a file, and refuses rather
      than widening the fix; the rule body is in the skill, not the stage.
- [x] An oracle-blocked refusal records `unresolved` / `oracle-blocked`; `DISPOSITIONS`,
      `DISPOSITION_VALUES` and `LedgerRow.disposition` are byte-identical to before.
- [x] An oracle-blocked refusal is retagged `manual-only`, which both excludes it from Step 3's
      fixable-finding selection and keeps it out of the grade — the same record
      `review.md.j2:843-848` gives the identical fact discovered one step later.
- [x] `hm review_churn complexity` emits per-file LOC and AST deltas, `null` (not `0`) for
      non-Python, into both sinks.
- [x] A lens whose `repo_probe` is absent or unverifiable is reported `missing`, on all five
      invalidity modes, with content read from the blob at the reviewed revision.
- [x] `hm lens_coverage check` errors rather than defaulting when `--diff-files` is absent under
      Production, and all three `review.md.j2` call sites pass it.
- [x] Phases 3 and 4 render in Production and are asserted **absent** in Side, **and** a Side
      integration test shows probe-less result files still counting as exercised under
      `--preset Side`.
- [x] `hm review_churn complexity` is reachable through `command_registry`'s verb allowlist,
      proven by a CLI-level invocation rather than a library call.
- [x] A `tests`-lens finding whose own target is the test is still fixable — the refusal does
      not fire on it.
- [x] One real `/hm:review` on this repository shows all seven live lenses producing passing
      probes.
- [x] Surface growth is folded once with a BASELINE-DELTA attribution document; the baseline is
      never regenerated to go green.
- [x] `ruff check`, `ruff format --check`, `mypy --strict src tests`, `pytest` all green.

## 🔍 Plan Validation

### Cross-model second opinion (Step 4 pre — main loop)

Both enabled models ran on the pre-validation draft. `second_opinion_results`:

```yaml
- model: codex
  status: invoked        # 9 findings, 148.6s
- model: antigravity
  status: invoked        # 8 findings, 46.7s
```

**Accepted and folded into this document:**

| Model | Finding | Resolution |
|---|---|---|
| codex | ADR-006's premise is false — `DISPOSITIONS` **aliases** `codex_ledger.DISPOSITION_VALUES` | **Verified at source and upheld.** Reopened the decision with the user (Interview #9); ADR-006 fully rewritten to use the authority axis instead. This reversed a locked decision. |
| codex | `FileChurn` has no pre-LOC; ADR-001's "already produces pre/post LOC" is false | **Verified and upheld.** ADR-001 corrected; `_pre_loc` added to Phase 3 scope. |
| codex + antigravity | `exercised_lenses` consumers under-enumerated | Full enumeration added: `coverage_verdict`, `main`, tests, and **three** `review.md.j2` call sites. |
| antigravity | `--diff-files` absent ⇒ empty set ⇒ check silently no-ops | Required-under-Production; absent is an error. |
| codex | Phase 4 can exit without the live run that R1 calls gating | Live 7-lens run moved into Phase 4's exit criterion with an explicit revert outcome. |
| codex | Phase 3 can pass with both sinks disconnected | Exit criterion split into calculator / jsonl-append integration / render assertions. |
| codex | Canary can be steered to read outside the repo via a tracked symlink | ADR-003 now reads the blob at `--rev` and rejects out-of-root resolution; R11 added. |
| codex | "No change to any stage's control flow" contradicts ADR-003/ADR-004 | Corrected; the summary now states what changes. |
| antigravity | "the study's own audit against this repository" overstates provenance | Corrected — the audit is ours, against the study's prescriptions. |
| antigravity | ADR-003 "all 7 lenses" reads unconditional against ADR-005's Production gate | ADR-003 now scopes itself to Production explicitly. |
| antigravity | Round-churn risk of a permanently-unfixable finding | R10 added; the fixable-selection exclusion became a Phase 2 exit criterion. |
| antigravity | Phase 2's exit never renders `review.md.j2` | Exit widened to `tests/render` in full. |
| codex | Phase A's rule is unverifiable prose | **Accepted as risk, not fixed** — R12 records the reasoning and the revisit trigger. |

**Rejected:**

| Model | Finding | Why |
|---|---|---|
| antigravity (P0) | ADR-004 and ADR-006 contradict because "the fixer writes to `codex_ledger`" | Factually wrong. `review.md.j2` states that reviewer-lens dispositions do **not** go to the codex ledger — its `model` field is a closed enum of second-opinion vendors. The second half ("pre-fix consensus cannot assign a disposition discovered later") is also wrong: Step 4e is the round-record writer and runs on every path, including after the fix step. Moot in any case now that ADR-006 adds no disposition value. |
| antigravity (P2) | ADR-006 delegates reader enumeration to an unwritten test | Moot — the rewritten ADR-006 adds no enum value, so there is no reader set to enumerate. |

### Plan validator — pass 1 (MAJOR_REVISION, resolved)

11 critiques: 5 critical, 5 warning, 1 suggestion. `hm plan_rounds plan` queued all 11 and
skipped none (churn 0.186, below the 0.5 stale threshold). All 11 were verified against source
before being acted on — the count matters because two of pass 1's criticals were **not** defects
introduced by this PLAN but existing contracts its author had not read.

| Severity | Critique | Resolution |
|---|---|---|
| critical | Phase 1's exit criterion invoked `python -m harness_maker.context_lint`, which has **no `main()`** — exit 0, no output, a green light wired to nothing; and this repo's `CLAUDE.md` is 612 lines against a 500 Production cap | Interview #11. Criterion replaced with `wc -l`. **The "cap does not apply" half of this resolution was itself wrong** and was corrected at the Phase 4 re-render — `readiness` lints this file and reports it P1. Recorded in the Phase 1 note rather than edited away |
| critical | `hm review_churn complexity` unreachable — `command_registry.py:146` allowlists only `measure`/`pin`/`oscillation`, and `guard_or_none` runs before argparse | `command_registry.py` added to Phase 3 scope and the components table; exit criterion (a) must invoke the CLI, not the library |
| critical | ADR-004 erased the carve-out at `review.md.j2:813-817`, which already permits fixing a finding whose own target IS the test — every `tests`-lens P0/P1 would have become permanently unfixable | Interview #10. The carve-out is restated verbatim in ADR-004 as an explicit **non-trigger** |
| critical | The Side branch of the new validity check was undefined while `lens_coverage.main`'s `--preset` fail-closes toward Production — **every Side review would be permanently unapprovable** | ADR-005 now states the probe check is skipped entirely under `--preset Side`; a Side integration test added to Phase 4 |
| critical | `blocked-by-oracle` survived ADR-006's rewrite in three instructive places, one of which (Testing Strategy) demanded a test that can only pass by editing a Contract-Boundaries-protected file | Purged from ADR-004, the Phase 2 heading and Testing Strategy |
| warning ×5 | four→five invalidity modes; R10's two harms conflated; the exclusion's carrier field unnamed; a dangling `ADR-010` citation; "three invocations" that are six literal lines behind the `is_codex` fence | All folded; R13 added for the carrier |
| suggestion | `exercised_lenses` described as having no content validation | Corrected — it already validates JSON, `lens` and `run_id` |

### Plan validator — pass 2 (TERMINAL, MAJOR_REVISION)

`hm plan_rounds outcome`: **`progress`** — `resolved_n: 11`, `new_n: 7`, `unresolved_n: 0`. The
two-pass cap stopped a loop that was still moving; it did not stop a stalled one. Reporting the
cap alone would hide that distinction, which is why it is recorded here.

**These findings are terminal: recorded, NOT revised.** This document was not edited after
pass 2, so there is no unvalidated last revision. `/hm:execute` carries them as **known risks
and proceeds** — it must not halt on them.

| Severity | Finding (each verified at source before recording) | Execute must |
|---|---|---|
| critical | **`review.md.j2:843-848` assigns the opposite record to an overlapping fact.** It says: on §4.5's unreachable case carry one `manual-only` P1 `spec_gap`, *"never grade-lowering, never authority to edit the test"*. ADR-006 consequence (ii) deliberately WANTS `unresolved` to hold the review at CHANGES_REQUESTED. Two legal records for one event, opposite grade effects — eleven lines below the rule pass 1 said to preserve | Decide the boundary (pre-fix refusal vs post-verify unreachable state) **before** touching Step 4, and add `:843-848` to Contract Boundaries or to Phase 2's scope |
| critical | **Phase 4's gating live `/hm:review` would exercise the un-re-rendered harness.** Every Phase 4 edit is to `src/harness_maker/templates/`; `/hm:review` runs `.claude/commands/hm/review.md`, a prior render. The run would pass green having tested nothing about the change | Re-render (`/harness-maker:make --update`) as a scoped Phase 4 step, assert the rendered command carries `--diff-files`/`--rev`, **then** run it |
| critical | **The surface ratchet blocks phases 2–4 mid-flight.** `_ATOMIC_RATCHET["review"] = 67008` with `measured * 1.02` ≈ 1340 chars of slack; this PLAN's own estimate is ~1.2k plus ~240 from the six flag additions. `surface_allowance` exists for exactly this and requires `chars` plus a `delta_doc` **that already exists on disk** — this PLAN declares neither | **Phase 0, before any template edit**: create `work-docs/BASELINE-DELTA-bench-study-adoption.md` and add the `surface_allowance` block to this PLAN's frontmatter. Never bump the ratchet per phase |
| warning | The Side branch has no expressible representation — a required non-defaultable kwarg, `[]` declared illegal, and "skipped entirely" leaves no third state. `exercised_lenses` takes no `preset` today; `preset` stops at `coverage_verdict` | Choose: thread `preset` into `exercised_lenses`, or make the parameter `list[str] | None` where `None` means skip and `[]` stays an error |
| warning | Phase 2's "new §5" collides with `SKILL.md.j2:152`'s existing `## 5. What the selection does and does not promise` | Call it §6, name it by heading, and preserve the existing §5 |
| warning | **There is no top-level reviewer return contract to add `repo_probe` to.** `finding_schema.md.j2` is the only output-shape section and is entirely per-finding; the envelope is built by the main loop at `review.md.j2:233-235` | Name the destination file and section explicitly, and state the expected pin set so R9's verification has a target |
| warning | ADR-004's premise is not reconciled with this harness's own measurement at `review.md.j2:845-848` — the neighbouring failure class went to **0 in 10 rounds** once the reviewer could read the repository, a condition already met here. ADR-000's own standard demands the discount be recorded | Record the local measurement beside the study's; give R12's revisit trigger a number derived from it |

**Clean categories across both passes:** rollback-strategy, scope-drift-hazards,
missing-interview-rounds, test-strategy-depth.

### Operator resolution (Interview #12)

The Step 4 A/B question was put to the user with all three live criticals named. **The user chose
A — record them as accepted risk and proceed.** `/hm:execute` therefore runs with these seven
findings carried, and the three criticals have named remedies it must perform in this order:

1. **Phase 0, before any template edit** — create `work-docs/BASELINE-DELTA-bench-study-adoption.md`
   and declare the `surface_allowance` block in this PLAN's frontmatter. Without it phases 2–4
   block on a red `test_atomic_commands_within_budget` with no authorized escape.
2. **Before touching Auto-Fix Step 4** — decide the boundary between `review.md.j2:843-848`'s
   `manual-only` / never-grade-lowering record and ADR-006's `unresolved` / grade-counting one,
   and write the decision into ADR-004 as an amendment.
3. **In Phase 4** — re-render before the live `/hm:review`, and assert the rendered command
   carries `--diff-files`/`--rev` first.

`validator_outcome` stays `MAJOR_REVISION_TERMINAL`, which is the accurate name: a second pass
ran and these survived it. The operator acceptance is recorded here rather than by renaming the
outcome, because "the findings were answered" and "a human accepted them unanswered" are
different facts and a shared name would make them indistinguishable to every later reader.

**The cost of the two-pass cap, stated plainly:** three criticals are live at hand-off. One
(the ratchet allowance) is mechanically blocking and has a named remedy. Two require a decision
a third validator pass would not make for us — and every recorded three-pass episode on this
repository's `stage-agents.jsonl` also ended `MAJOR_REVISION`, so a third pass buys findings,
not release.
