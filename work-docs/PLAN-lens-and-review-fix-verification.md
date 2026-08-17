---
type: plan
task_slug: lens-and-review-fix-verification
status: partial
status_reason: "Phase 1 (ledger isolation + read-time exclusion) implemented and landed; Phases 2-5 were never started and remain deferred, so this PLAN is not complete."
created: 2026-08-17
tags: [harness-maker, plan, python, review-pipeline, observability, config-axis]
spec: "[[SPEC-lens-and-review-fix-verification]]"
research_doc: "[[RESEARCH-lens-and-review-fix-verification]]"
interview_rounds: 2
adrs: 8
validator_outcome: MAJOR_REVISION_TERMINAL
summary: "Close three lens/review defects, add two cost knobs, audit observability"
---

# PLAN — lens and review fix verification

## 🎯 Executive Summary

**What.** Five phases closing the three defects RESEARCH confirmed around the (working) seven-lens
review axis, plus two configuration knobs that stop projects paying for artifacts they do not
consume. Live cross-project verification (SPEC AC-011) is **deferred to a separate task** — see
ADR-008.

**Why.** The axis works; its surroundings do not. The unit suite writes synthetic rows into the
live second-opinion ledger, so the health metric CLAUDE.md prescribes reports a 90.7% codex loss
rate where the truth is ~0%. `review.md.j2`'s routing paragraph still names the agent axis the
lens merge retired, and that prose is what put two never-dispatched agents into a live REVIEW
document's `reviewers_invoked`. The per-finding `lens` stamp the template mandates was missing on
19/19 findings in the only real run, and no gate can see it.

**Key decisions.** ADR-001 (advisory stamp reporting), ADR-002 (read-time exclusion over purge),
ADR-003 (instrumentation absent-key flips to off), ADR-004 (`review_doc` knob, `frontmatter-only`
default on both paths), ADR-005 (`frontmatter-only` retains machine-minimal findings because they
are loop state), ADR-006 (render gates vary the config axes that gate the blocks), ADR-007 (one
per-entry exclusion predicate schema), ADR-008 (live verification deferred).

**Estimated impact.** ~6 Python modules, 2 templates, ~8 new test files, 2 config fields, 1 audit
document. No public CLI removed.

## 📚 Prior Work

- **`[fail:test] gate-matrix-omits-render-gating-axis`** (2026-08-16, count:1) — a render gate whose
  matrix omits an axis that *gates the block* reports "clean" for text it never opened. Three
  `Task`-family leaks survived exactly that way, hidden behind `second_opinion.models`,
  `reviewers.enabled`, and `targets`. This PLAN adds a third such axis (`review_doc`), so ADR-006
  makes the mutation check a phase exit criterion rather than a hope.
- **`[fail:design] per-round-step-runs-only-in-round-1`** (2026-08-10, count:1) — a per-round
  obligation written into the linear first-pass procedure runs once. AC-004's `unstamped` reporting
  is a per-round obligation; Phase 2 places it inside the loop body's checklist, not before it.
- **`[wiki:architecture] lens-axis-pilot-2026-08`** — distinct lenses do **not** corroborate each
  other, which is why one lens votes alone (ADR-007 of the axis work). Nothing here may reintroduce
  a cross-lens K=2 assumption.
- **`[wiki:architecture] review-exit-on-risk-closure`** — `lens_coverage check` verifies **liveness
  only**: that a result file exists, parses, and self-identifies. It never verifies that reviewing
  occurred. AC-004 extends the same liveness family (is the stamp present?) and inherits the same
  limit — Phase 2 must not describe it as a quality check.
- **CLAUDE.md § 렌더 컨텍스트 플래그는 출력 경로에서 파생시킬 것** (`is_codex`, 2026-08-16) — the
  precedent for this PLAN's whole detection problem: template and artifact both read correct, only
  the runtime value is wrong, and render-grep is structurally blind to it.
- **RESEARCH-lens-and-review-fix-verification** — the measurements every phase here is built on.

## 🎙️ Interview Transcript

| # | Topic | Category | Question | Options | Choice | Note | → ADR |
|---|---|---|---|---|---|---|---|
| 1 | `frontmatter-only` findings retention | Contract shape | Findings lists are the round-to-round `id` merge store; dropping them breaks it. What survives? | machine-minimal / sidecar JSON / auto-upgrade on multi-round / drop and accept wholesale replacement | **machine-minimal** (id · severity · file:line · voices · state) | Corrects SPEC AC-006's `findings_lists: false` to `findings_minimal` | ADR-005 |
| 2 | Phase order | Phasing | Which phase runs first? | draft order / live-verify bookends / config first / audit first | **draft order** — ledger → prose+gate → config → agy → audit | Honest measurement (P1) precedes anything that reads the ledger (P4) | ADR-002 (consequence) |
| 3 | Exclusion key schema (validator C1) | Contract shape | The exclusions file is run-id-keyed; second-opinion rows have no `run_id`. What key does the shared helper use? | per-entry predicate / add run_id to rows / separate file per ledger / slug+stage compound key | **per-entry predicate schema** | Adding `run_id` to rows cannot match the 83 existing rows — it fails the actual goal | ADR-007 |
| 4 | Phase 6 vs re-render (validator C2) | Scope boundary | Phase 6's exit needs the Phase 2 fix deployed, but re-rendering the targets is out of scope | pull re-render in / split the exit / only re-render harness-maker / defer Phase 6 | **defer Phase 6 to a separate task** | Removes the contradiction rather than resolving it; AC-011 stays unverified and is recorded as such | ADR-008 |
| 5 | `message` in machine-minimal (validator C3) | Contract shape | `finding_id` hashes `message`; a resumed round 2 has no statement of the defect | add `message` / accept the resume loss / store a hash only | **add `message`** | The saving is prose, not identity — one line per finding is affordable | ADR-005 (amended) |
| 6 | Absent-key announcement (validator C9) | Observability | An INFO line is the whole notice for reversing a fleet-wide ADR | loud advisory / loud + write the resolved value / keep INFO | **loud advisory naming old → new** | Writing to the user's harness.yaml was rejected as a heavier intervention than the notice warrants | ADR-003 (amended) |

**Assumptions taken without asking** (each defensible, each recorded so it is not mistaken for an
oversight):

- The read-time exclusion filter is **extracted to a shared helper** rather than reimplemented, and
  `verifier_discrimination` is migrated onto it. Two ledgers reading one file with two
  implementations is a drift surface, and this repo has that failure class on record.
- "Announce once" for both absent-key resolutions **reuses the existing one-shot advisory logging**
  already used by `interview._parse_instrumentation`, not a new mechanism.
- Phase 5 is split **audit → gate → removal**. Removal scope is unknown until the audit runs; an
  empty orphan set makes AC-010 a vacuous pass, which is a legitimate outcome, not a failure.
- `lean`'s "narrative" is defined concretely in ADR-004's table rather than left to `/hm:execute`.
- Re-rendering `~/neuroTerm` and `~/spoton` onto the new defaults is **out of scope** — a separate
  chore commit per CLAUDE.md, and their operators' call.

## 📐 Architecture Decision Records

### ADR-001: The per-finding lens stamp is reported, never enforced
**Status:** Accepted (2026-08-17, via /hm:spec interview round 1)
**Context:** The template mandates stamping every finding with its lens, because ADR-007's solo-lens
vote is undecidable without it — the four core lenses all dispatch to `code-reviewer`, so without
the stamp Step 4 cannot tell one lens speaking once from one lens speaking several times. The only
live run shipped 19/19 unstamped and the coverage gate passed.
**Decision:** `hm lens_coverage check` gains an `unstamped` array. `blocks_approval` is computed
exactly as today and never consults it.
**Consequences:**
- ✅ The failure becomes visible in the CLI's own output, which is the one artifact the template
  forbids the model from second-guessing.
- ⚠️ A review can still be approved with unstamped findings. The solo-lens vote stays undecidable
  in that case; the operator is told, and decides.
**Rejected alternatives:**
- *Blocking* — rejected because retroactive unapprovability is how a gate gets disabled. (An
  earlier draft also cited the review in flight in `~/neuroTerm`; that is transient and the
  decision is not, so it is struck — validator C10.)
- *Python injects the stamp from the filename stem* — rejected: it makes the field always present
  and therefore never diagnostic, hiding a model that is not following the contract rather than
  surfacing it. **Note (codex finding 1):** "stamp at the trusted dispatch/result-ingest boundary"
  reduces to this same alternative — the result file *is* per-lens and keyed by its filename stem,
  which is what `lens_coverage.exercised_lenses` already checks.
**Revisit trigger:** reconsider blocking once two consecutive live runs report `unstamped: []`.
**Source:** Interview (spec) #1

### ADR-002: Ledger pollution is excluded at read time, never purged
**Status:** Accepted (2026-08-17, via /hm:spec interview round 1)
**Context:** ~140 pytest runs' worth of synthetic `slug: "s"` rows sit in
`.claude/observability/second-opinion.jsonl`, 83 of them since 2026-08-14. They corrupt the
per-model loss rate: raw reading says codex 90.7%, truth ~0%.
**Decision:** Extend the existing `.ledger-exclusions.json` mechanism (today read only by
`verifier_discrimination`) to the second-opinion ledger, via a shared helper both use, **on the
schema ADR-007 fixes**. The jsonl is never rewritten.
**Consequences:**
- ✅ Append-only is preserved, so a concurrent reader in another session is unaffected — and there
  were two live sessions during this task's research.
- ✅ The exclusion carries its own reason string, so a later reader learns why rather than finding
  a gap.
- ⚠️ Every future aggregator must go through the helper. A direct `open(ledger)` bypasses it
  silently. Phase 1's exit criterion is the only thing standing between this and a second
  unfiltered reader.
**Rejected alternatives:**
- *Purge* — rejected: rewrites a file another session may hold open, and destroys the evidence
  that the leak existed.
**Source:** Interview (spec) #1

### ADR-003: An absent `instrumentation` key resolves to off
**Status:** Accepted (2026-08-17, via /hm:spec interview round 2)
**Context:** `InstrumentationConfig` deliberately diverges: a fresh render defaults to `False`,
while an **absent key** in an existing `harness.yaml` resolves to `True` (ADR-011 of the
instrumentation work) so that the fleet already producing rows does not silently stop.
`~/neuroTerm` carries `stage_agent_ledger: true` purely through that rule, having never opted in —
a consuming project producing harness-maker's own development telemetry.
**Decision:** The absent-key branch resolves to `False`. New-render and absent-key now agree. The
resolution is announced with a **loud advisory naming the previous value and the new one** — not
the current `logger.info` — fired only when the key is genuinely absent, once per resolution. The
flip **takes effect at the next `/harness-maker:make --update`**, not on load, so an operator can
predict when their fleet changes (validator C9).
**Consequences:**
- ✅ A project stops producing telemetry whose only consumer is this repo, without editing anything.
- ⚠️ **The cross-project denominator shrinks, and it is load-bearing** — harness-maker's own six
  rows once said "delete the plan-validator second pass" (0/3) while the pooled four-project
  population said keep it (2/9). This PLAN accepts that cost knowingly; it is the precise thing
  ADR-011 was written to avoid.
- ⚠️ Projects that *want* to contribute must now set the key explicitly.
**Rejected alternatives:**
- *Set `false` only in `~/neuroTerm`* — rejected: leaves every other absent-key harness in the same
  position and fixes an instance rather than the rule.
- *Ask at re-render* — rejected: `--update` runs non-interactively in scripts, so the branch would
  still need a default and nothing would be settled.
- *Retire the axis* — rejected: loses cross-project data entirely rather than making it opt-in.
- *Preserve absent-key=True and change only fresh renders* (codex finding 5) — rejected: that is
  the current state, and it re-creates the very new-render/absent-key divergence this ADR removes.
- *Write the resolved value into the user's `harness.yaml`* — rejected: a heavier intervention
  than the notice warrants, and it edits a file the user owns.
**Source:** Interview (spec) #2

### ADR-004: `reviewers.review_doc` gates how much REVIEW prose is written
**Status:** Accepted (2026-08-17, via /hm:spec interview rounds 2-3)
**Context:** The REVIEW document's machine consumers — `verify.md` Check 1a and `wrapup.md` —
read **only** the frontmatter `drift_verdict`. Nothing controls the document's size;
`reviewers.verbosity` governs reviewer *agent prompts*, not the output. Writing it is a real
per-review cost for an operator who never opens it.
**Decision:** Add `reviewers.review_doc: full | lean | frontmatter-only`, defaulting to
`frontmatter-only` on **both** the new-render and absent-key paths.

| section | full | lean | frontmatter-only |
|---|---|---|---|
| frontmatter (incl. `drift_verdict`) | ✅ | ✅ | ✅ |
| §7 cross-model frozen findings (when models enabled) | ✅ | ✅ | ✅ |
| Review Iteration Summary + exit reason + counters | ✅ | ✅ | ✅ |
| findings (id · severity · file:line · **message** · voices · state) | ✅ full prose | ✅ full prose | ✅ machine-minimal |
| per-finding rationale, reproduction, reviewer takes | ✅ | ❌ | ❌ |
| round narrative, drift discussion, oscillation prose | ✅ | ❌ | ❌ |

**Consequences:**
- ✅ The cheapest mode still satisfies every machine reader and the auto-fix loop.
- ⚠️ Existing projects' REVIEW documents shorten at their next re-render. The operator was shown
  this and chose it.
- ⚠️ A human debugging a grade months later has less to read in the default mode.
**Rejected alternatives:**
- *Default `lean`, `frontmatter-only` opt-in* — rejected: the operator's stated premise is that
  most users never read it, and a default that contradicts the premise fixes nothing.
- *Auto-upgrade when `second_opinion.models` is non-empty* — rejected: one setting silently
  overriding another is the "why is my config not taking effect" class.
**Source:** Interview (spec) #2, #3

### ADR-005: `frontmatter-only` retains machine-minimal findings — they are loop state
**Status:** Accepted (2026-08-17, via /hm:plan interview round 1)
**Context:** SPEC AC-006 wrote `findings_lists: false` for `frontmatter-only`. But the auto-fix
loop's per-round voter state is merged **by `id`** — CLAUDE.md forbids wholesale replacement,
because reviewer nondeterminism alone can then drop a corroborating voice and move a grade with no
code change. Those `id`s and voices live in the findings sections. Dropping them leaves round 2
with nothing to merge against.
**Decision:** `frontmatter-only` keeps findings in machine-minimal form —
`id · severity · file:line · message · voices · lifecycle state` — and drops only human prose
(rationale, reproduction, reviewer takes). SPEC AC-006's table is corrected accordingly
(`findings_lists: false` → `findings_minimal`).

**`message` is in the set, and it is not optional** (validator C3, codex finding 3).
`codex_adapter.finding_id` computes identity as `sha256([source, file, line, message])`, so
without `message` the id cannot be re-derived or verified; and a round-2 fix step that reads the
document rather than round-1 context — after a resume, or in a fresh session — would hold an id, a
severity and a location with no statement of what is wrong. One line per finding is the whole
cost; the saving this mode exists for is prose, not identity.
**Consequences:**
- ✅ Every mode supports a multi-round review; no mode is silently single-round-only.
- ✅ The bulk of the saving survives — prose, not identity, is what is long.
- ⚠️ `frontmatter-only` is a misleading name for "frontmatter + machine state". Phase 3 must
  document the name at the config site, or the next reader will assume it means what it says.
**Rejected alternatives:**
- *Sidecar JSON for loop state* — the cleanest separation and rejected twice: it was offered as
  the larger option and not chosen, and it creates a second artifact that can drift from the first.
- *Auto-upgrade multi-round reviews to `lean`* — rejected with ADR-004's variant, same reason.
- *Accept wholesale replacement in this mode* — rejected: CLAUDE.md names it as prohibited and
  gives the mechanism by which it corrupts grades.
**Source:** Interview (plan) #1

### ADR-006: Render gates vary the config axes that gate the block under test
**Status:** Accepted (2026-08-17, from `[fail:test] gate-matrix-omits-render-gating-axis`)
**Context:** This PLAN adds `review_doc`, a third axis that decides whether whole blocks of
`review.md.j2` render at all. The recorded failure is exact: a gate deriving its file set from the
blueprint went green while three leaks survived, each behind a different `{% if config.* %}` the
matrix never varied. "The blueprint gives me every file" is true and insufficient — content is
conditional too.
**Decision:** Every render gate this PLAN adds or touches enumerates the `{% if config.* %}`
conditionals wrapping the text it polices and makes each an explicit matrix row —
`review_doc` (3 values), `second_opinion.models` (empty and non-empty), `reviewers.enabled`, and
**`preset` (Production and Side)**. Each new row must be **proven** by mutating the template to
reintroduce the defect and confirming the row goes RED. Where the gate can derive its rows from
the template's actual conditionals, it does; a hand-maintained list is the failure class CLAUDE.md
records three times.

**`preset` was missing from the first draft of this very ADR** (validator C5) — `review.md.j2:115`,
the exact line Phase 2 rewrites, carries `{% if routable_lenses(config.preset) %}`, and
`routable_lenses` is empty on Production and returns the domain lenses on Side. A gate rendered
only at this repo's Production preset never opens that clause. The ADR written to prevent the
omitted-axis class had committed it.

**Not axes** (codex finding 9, partially refuted): `routing` mode and review round are *runtime*
prose, not render conditionals, so they cannot be matrix rows; instrumentation key state does not
gate the routing block.
**Consequences:**
- ✅ A gate that cannot see its subject fails loudly at authoring time instead of reporting clean.
- ⚠️ Rows are full renders, so the gate is slower. Accepted — a fast blind gate is worth less than
  a slow sighted one.
**Rejected alternatives:**
- *Cross-product of all axes* — rejected: one enabled value per axis reaches the block, so the
  product buys runtime, not coverage.
**Source:** `[fail:test] gate-matrix-omits-render-gating-axis`, Prior Work

### ADR-007: One per-entry exclusion predicate schema, shared by both ledgers
**Status:** Accepted (2026-08-17, via /hm:plan interview round 2 — validator C1, codex finding 7)
**Context:** ADR-002 says a shared helper reads `.ledger-exclusions.json` for both ledgers. It
cannot, as written. The file is documented and used as a map of **run ids** to reasons
(`verifier_discrimination.py:56-61`; all three filters key on `row["run_id"]`), and
`codex_ledger.SecondOpinionRecord` is `strict=True, extra="forbid"` with **no `run_id` field at
all** — its fields are ts / slug / stage / model / finding_ref / disposition / status /
skip_reason / oracle_result / later_regression_link / duration_s. There is no common key.
**Decision:** Promote the file to a **list of per-entry predicates**, each
`{key: "run_id" | "slug" | "stage", value: <str>, reason: <str>}`. A one-shot migration reads the
legacy single map as `run_id` entries, preserving the existing `aiexit-exec-p2b` exclusion's
meaning exactly. The helper is the sole reader for both ledgers and validates on load.
**Consequences:**
- ✅ One schema, one reader, and every exclusion carries its own auditable reason.
- ✅ The 83 historical synthetic rows are reachable — they have a slug and no run id.
- ⚠️ A malformed file must **fail loudly, not fail open**: silently excluding nothing looks
  identical to having nothing to exclude, and that ambiguity is what this whole phase is about.
- ⚠️ Path/root resolution must be pinned to the base repo, matching where the invoker writes.
**Rejected alternatives:**
- *Add `run_id` to the second-opinion row schema* — rejected: it cannot match the 83 rows already
  written, so it fails the actual objective while looking like the tidier fix.
- *A separate exclusions file per ledger* — rejected: recreates the drift surface ADR-002 exists
  to close.
- *Keep one flat map with a compound `slug+stage` key syntax* — rejected: what a key means becomes
  a parsing question, and a mis-keyed entry silently matches nothing.
**Source:** Interview (plan) #3

### ADR-008: Live cross-project verification is deferred to a separate task
**Status:** Accepted (2026-08-17, via /hm:plan interview round 2 — validator C2)
**Context:** The drafted Phase 6 required one `/hm:review` in `~/harness-maker` and `~/spoton`,
with an exit criterion that neither REVIEW frontmatter names an undispatched reviewer — while its
own scope excluded re-rendering either project. The routing prose is baked in at render time, so
an un-re-rendered harness keeps the old paragraph: the phase would have reproduced the defect by
construction and been unable to distinguish "the fix failed" from "the fix was never deployed".
**Decision:** Drop the phase. SPEC AC-011 is **not satisfied by this PLAN** and is recorded as
deferred, not as passed.
**Consequences:**
- ✅ Removes a contradiction rather than papering over it; no unfalsifiable exit criterion ships.
- ⚠️ **The seven-lens axis remains observed in exactly one project** (`~/neuroTerm`). Everything
  here is verified by unit, render and structural gates — the class of gate that, by this repo's
  own record, reports clean for text it never opened.
- ⚠️ The follow-up task must re-render both targets first, and should also assert `unstamped: []`
  — the drafted exit could not observe the very defect with 19/19 incidence (validator C2 /
  codex finding 2).
**Rejected alternatives:**
- *Pull re-rendering into the phase* — the correct fix on the merits, and not chosen: it forces
  new defaults onto two projects as a side effect of a verification step.
- *Split the exit criterion* — rejected: leaves a phase whose strongest claim is unverifiable.
- *Re-render `~/harness-maker` only* — rejected: verifies the axis where it is least in doubt.
**Source:** Interview (plan) #4

## 🏗️ Technical Design

**Current state.**
`lens_coverage.exercised_lenses` opens every result file already (it checks `lens` and `run_id`),
so the stamp check has no new I/O. `ledger_exclusions.EXCLUSIONS_FILE` holds the only
exclusion reader. `InstrumentationConfig.stage_agent_ledger` defaults `False` with the absent-key
branch in `interview._parse_instrumentation` resolving `True`. `ReviewersConfig` has no
`review_doc` field. `review.md.j2` Step 3's routing paragraph names `ux-reviewer` /
`performance-reviewer`, neither of which `conditional_router.lens_dispatch` returns.

**Affected components.**

| Component | Change |
|---|---|
| `lens_coverage.py` | `unstamped` in the verdict; per-file stamp scan |
| `verifier_discrimination.py` | migrate onto the shared exclusion helper |
| new `ledger_exclusions.py` (or equivalent) | shared read-time filter, both ledgers |
| `second_opinion_invoke.py` | distinct `skip_reason` token for the agy empty-response class |
| `models.py` | `ReviewersConfig.review_doc` |
| `interview.py` | absent-key resolution for `instrumentation` and `review_doc` |
| `templates/stages/review.md.j2` | routing prose; `review_doc` section gating; per-round unstamped reporting |
| `tests/unit`, `tests/render`, `tests/structural` | ~8 new files |

**Data flow (unchanged shape, one new field).**
`lens agents → main loop writes <run-id>/<round>/<lens>.json → lens_coverage check → {exercised,
missing, unstamped, blocks_approval} → the gate branches on blocks_approval only`.

**Design decisions.** All eight ADRs above. Two are worth restating as constraints on
implementation: the stamp is **reported not enforced** (ADR-001), so no code path may make
`unstamped` reach `blocks_approval`; and the exclusion helper is the **sole** ledger reader
(ADR-002), so a direct `open()` on either ledger is a defect regardless of test outcome.

**API changes.** `hm lens_coverage check` output gains `unstamped: [...]`. Additive — existing
consumers read `blocks_approval` / `missing` / `exercised` and are unaffected.

## 📝 Implementation Plan

### Phase 1 — Ledger isolation and read-time exclusion
- `depends_on`: `[]`
- `parallel_group`: `serial-foundation`
- `merge_hazards`: `.claude/observability/second-opinion.jsonl` (append-only, concurrent readers);
  `verifier_discrimination.py` (migrated, not duplicated)
- **Scope in**: `tests/conftest.py` (the autouse base-root redirect), `tests/unit/test_second_opinion_invoke.py`,
  `tests/unit/test_second_opinion_budget_advisory.py`,
  new shared exclusion helper (ADR-007 schema + legacy-map migration), `verifier_discrimination.py`, new
  `tests/unit/test_ledger_isolation.py`, `tests/unit/test_ledger_exclusions.py`,
  `.claude/observability/.ledger-exclusions.json`
- **Scope out**: the ledger file's contents; any other test module
- **Exit criterion** (three conjuncts):
  1. **The suite structurally cannot reach the base ledger** — an **autouse** fixture in
     `tests/conftest.py` redirects `second_opinion_invoke`'s base-root resolution to the test's own
     `tmp_path` for every test, with opt-out only by an explicit marker.

     > **The redirect must be CONDITIONAL, not unconditional (constraint B2, added 2026-08-17
     > from Phase A.5 round 2).** `tests/unit/test_second_opinion_invoke.py:133-168` holds five
     > assertions of the form `soi.resolve_base_root(...) == repo.resolve()` — they test the
     > *resolver itself* against a real git repository they construct, and an autouse patch that
     > always redirects breaks every one of them. The fixture must therefore redirect only when
     > the resolved root would contain the tests tree, or be opt-out-able by the resolver's own
     > tests via the `live_env`-style marker `tests/conftest.py` already establishes. Nothing in
     > the SPEC, this PLAN or the authored tests said so; the two-file Phase A.4 measurement could
     > not see it, and a lens found it. **A second constraint arrives with it**: the two canary
     > tests each assert their sandbox ledger holds exactly one slug, which requires the fixture
     > to be **function-scoped with a fresh directory per test** — a session-scoped sandbox makes
     > whichever runs second fail.

     Proven by two assertions:
     (a) a **canary test that deliberately calls `soi.main()` with no `base_root` and no `chdir`**
     — the exact 2026-08-17 leak shape — and asserts the row landed under `tmp_path` and the base
     ledger is untouched; (b) an **AST test over every module importing `second_opinion_invoke`**
     confirming no test module bypasses the fixture.
     **Not byte-identity of the base ledger** (validator C7): it is append-only and shared, so a
     peer session's legitimate row fails that comparison with no test at fault — flakiness on the
     one gate the whole phase rests on, and the standard answer to a flaky gate is to weaken it.
     **And not a "test-owned marker"** (validator C14): `SecondOpinionRecord` is `extra="forbid"`
     so it cannot carry one, leaving a per-test slug convention — a hand list wearing a property
     test's clothes, invisible to every future leak site that happens to use a realistic slug.
     Prevention at the fixture beats detection at the row: nothing has to opt in.
  2. `slug: "s"` rows are absent from both numerator and denominator of the per-model loss rate,
     computed **through the helper**.
  3. **Both** ledgers filter correctly through the one helper — the `aiexit-exec-p2b` run-id
     exclusion still applies to the stage-agents ledger after the ADR-007 migration, and a
     malformed exclusions file fails loudly rather than excluding nothing.
- **Risk**: medium — raised from low: ADR-007 changes a file format an existing reader depends on
- **STATUS: implemented, Phase D pending (2026-08-17).** The A.5 gate ran four rounds (two within
  budget, two operator-authorised) and never returned PASS; the operator elected to apply round
  4's three specified fixes and proceed to Phase C rather than open a fifth. Gate history and the
  unaddressed residue are in `## 🚧 Phase 1 — Phase A.5 gate history` below.

### Phase D.5 — newly-reachable window (this phase is a repair, so this is not optional)

**What input window does this repair newly make reachable?** Two, and they are different in kind.

1. **`load` now accepts a JSON *list*.** Before, any non-dict payload took the "is not an object"
   branch and excluded nothing. The window newly reached is every list-shaped file — including
   entries with an unknown `key`, a non-object element, and a missing `value`/`reason`. Covered:
   `test_predicate_list_is_read_verbatim`, `test_an_unknown_key_is_rejected_loudly_and_the_rest_survive`.
2. **`is_excluded` now compares a NAMED field instead of `run_id` alone.** The window newly
   reached is every row whose `slug` or `stage` matches an entry — and, critically, every row
   whose *other* field happens to equal an excluded value. That is the cross-field case, and it is
   the one where a careless implementation silently drops legitimate rows. Covered at the helper
   (`test_the_key_names_which_field_is_compared`) and at a public seam
   (`test_a_real_row_whose_stage_collides_with_an_excluded_slug_is_still_counted`).

**Absent-case** (the repo's most-recurring class, count:8). The repair activates on an optional
file that most projects do not have, and on an optional `key` field within it. Both absent cases
are defined and covered: no file → `[]` (`test_absent_file_excludes_nothing_but_a_present_one_does_not`);
a row lacking the keyed field → not excluded, and specifically **not** matched by the literal
string `"None"` (`test_a_row_missing_the_keyed_field_is_not_excluded`). The legacy map is read,
never rewritten, so the pre-change reader's input is untouched — which is also the rollback story
finding C16 asked for.

**Third window, from the conftest fixture rather than the helper**: `resolve_base_root` is now
overridden for every test whose real answer would contain the tests tree. The newly-reachable
input is *tests that build their own git repositories* — they must keep the real answer. Covered
by the five pre-existing assertions in `tests/unit/test_second_opinion_invoke.py:133-168`, which
pass, and that is what constraint B2 was recorded to protect.
- **Rollback**: none needed — additive plus test-local fixes

### Phase 2 — Routing prose and the unstamped advisory
> **DEFERRED — never started (2026-08-17 wrapup).** No code, no tests. AC-003/AC-004 remain `pending_test: true`.
- `depends_on`: `[]` — the earlier `[1]` edge was measurement convenience, not correctness, and it
  serialised unrelated work (validator C12). The binding constraint is the `review.md.j2` merge
  hazard with Phase 3, which `parallel_group` already enforces.
- `parallel_group`: `serial-review-surface`
- `merge_hazards`: `templates/stages/review.md.j2` — Phase 3 edits the same file
- **Scope in**: `lens_coverage.py`, `templates/stages/review.md.j2` (routing paragraph + per-round
  unstamped reporting), `tests/unit/test_lens_coverage.py`,
  new `tests/structural/test_routing_prose_matches_dispatch.py`
- **Scope out**: `blocks_approval` logic; `conditional_router.OPTIONAL_REVIEWERS` (Non-Goal)
- **Exit criterion** (four conjuncts):
  1. a fixture directory with one unstamped lens yields `unstamped: ["security"]` with
     `blocks_approval` unchanged from the same directory fully stamped;
  2. the structural gate goes RED when the retired agent names are reintroduced into the prose,
     **at both presets** (ADR-006) — the Side clause `{% if routable_lenses(config.preset) %}` is
     invisible to a Production-only render;
  3. a **multi-round** fixture (round 1 stamped, round 2 unstamped) reports the round-2 lens —
     the cumulative-union reading must not mask a later round's regression;
  4. a structural assertion that the unstamped-reporting instruction appears **inside the round
     loop body and the confirmation-pass body**, not only in the linear first-pass procedure.
- **Risk**: medium — the unstamped report is a **per-round** obligation and
  `[fail:design] per-round-step-runs-only-in-round-1` is exactly this shape. Conjuncts 3 and 4 are
  the mitigation; the first draft claimed this mitigation in the Risks table while its exit
  criterion tested only a single fixture directory (validator C4).
- **Rollback**: revert to Phase 1

### Phase 3 — The two config axes
> **DEFERRED — never started (2026-08-17 wrapup).** No code, no tests. AC-005/AC-006/AC-007 remain `pending_test: true`.
- `depends_on`: `[2]`
- `parallel_group`: `serial-review-surface`
- `merge_hazards`: `templates/stages/review.md.j2` (shared with Phase 2); `models.py` and
  `interview.py` are also touched by any concurrent config work
- **Scope in**: `models.py` (`ReviewersConfig.review_doc`), `interview.py` (both absent-key
  branches), `templates/harness-yaml/{Production,Side}.yaml.j2`, `synthesize.py`,
  `templates/stages/review.md.j2` (section gating), new
  `tests/unit/test_instrumentation_absent_key.py`, `tests/unit/test_review_doc_default.py`,
  `tests/render/test_review_doc_modes.py`
- **Scope out**: re-rendering `~/neuroTerm` / `~/spoton`; `reviewers.verbosity`
- **Exit criterion** (four conjuncts):
  1. three modes render exactly ADR-004's table; `frontmatter-only` retains §7, the iteration
     summary, and machine-minimal findings **including `message`**;
  2. a **serialization/rehydration** test, because a render assertion cannot show that round 2
     merges correctly (validator C4/codex 4): write a `frontmatter-only` round-1 document, drop one
     reviewer in round 2, update another finding by the same `id`, and assert the prior
     corroborating voices, lens, and lifecycle state survive — i.e. that wholesale replacement is
     impossible in **every** mode;
  3. both absent-key resolutions return the new default and emit the ADR-003 loud advisory naming
     old → new, exactly once, only when the key is genuinely absent;
  4. every ADR-006 matrix row — including `preset` — goes RED under a reintroduction mutation.
- **Risk**: **high** — largest change, two intentional default flips, one of which
  (ADR-003) knowingly reverses half of a prior ADR
- **Rollback**: revert to Phase 2; both flips are single-branch changes

### Phase 4 — Antigravity empty-response classification
> **DEFERRED — never started (2026-08-17 wrapup).** No code, no tests. AC-008 remains `pending_test: true`.
- `depends_on`: `[1]`
- `parallel_group`: `parallel-diagnostics`
- `merge_hazards`: none
- **Scope in**: `second_opinion_invoke.py` (skip-reason token), `codex_adapter.py` if the
  classification lives there, `readiness.py` / the `/hm:health` per-model smoke surface,
  `tests/unit/test_second_opinion_agy_envelope.py`
- **Scope out**: any attempt to fix the vendor behaviour (Non-Goal); retry policy
- **Exit criterion**: three fabricated envelopes (SUCCESS+empty, SUCCESS+valid, non-SUCCESS)
  produce three distinguishable rows; **`/hm:health`'s per-model smoke names the class when it
  occurs** — SPEC AC-008's second conjunct, which the first draft silently dropped
  (validator C8), and the surface CLAUDE.md assigns to catching antigravity silent degradation;
  the measured rate for the new class is reported from the **filtered** ledger (hence the Phase 1
  dependency)

> **This phase has a live instance already.** During this PLAN's own Step 4, the mandatory
> antigravity second opinion returned `status: SUCCESS` with an empty `response` and no
> `structured_output` — exactly the class AC-008 defines. The plan-validator's verdict was
> therefore Claude+codex only. That is the warn-and-proceed path working as designed, and it is
> also the evidence that this phase is not hypothetical.
- **Risk**: low
- **Rollback**: revert to Phase 3

### Phase 5 — Observability audit, then orphan removal
> **DEFERRED — never started (2026-08-17 wrapup).** No code, no tests. AC-009/AC-010 remain `pending_test: true`.
- `depends_on`: `[]` — the earlier `[1]` edge was measurement convenience (validator C12)
- `parallel_group`: `parallel-diagnostics`
- `merge_hazards`: any module whose writer is removed
- **Scope in**: new audit document under `work-docs/`, new
  `tests/structural/test_observability_audit_complete.py`, whichever writers the audit marks orphan
- **Scope out**: a standing gate forbidding future reader-less writers (Non-Goal — offered and not
  chosen)
- **Discovery method** (validator C6 — without this the gate is a tautology): the writer set is
  derived by **AST scan over `src/harness_maker/**`** for writes under `.claude/observability/`,
  plus the rendered-command surface for template-generated writes. Both sides of the comparison
  must not be hand-maintained lists, or the test asserts that one list equals itself and an empty
  orphan set is indistinguishable from a blind gate.
- **Exit criterion**: every discovered path appears in the audit table marked `consumed` or
  `orphan`; **a seeded orphan (a writer with no reader, introduced deliberately) is detected** —
  the proof that the gate can detect at all; no module writes an `orphan` path; `/hm:health`,
  `/hm:metrics` and `verifier_discrimination` produce byte-identical output before and after
- **Risk**: medium — removal scope is unknown until the audit runs. **The audit is a gate, not a
  formality**: if it marks nothing orphan *and the seeded-orphan case passes*, AC-010 passes
  vacuously and that is the correct outcome. Without the seeded case the same result is
  meaningless, which is the distinction the first draft missed.
- **Removal caution** (codex finding 11, accepted as guidance): "no in-repo reader" authorises
  removal only for paths this repo owns end to end. Any path a consuming project or an external
  tool could read is marked `orphan-deferred`, not removed.
- **Rollback**: revert to Phase 4; removals are deletions, restorable from git

### ~~Phase 6 — Live verification in two more projects~~ — DEFERRED (ADR-008)

Removed from this PLAN. Its exit criterion required the Phase 2 prose fix to be deployed in
`~/harness-maker` and `~/spoton` while its own scope excluded re-rendering them, so it would have
reproduced the defect by construction and could not distinguish a failed fix from an undeployed
one. **SPEC AC-011 is deferred, not satisfied.**

The follow-up task must: re-render both targets at the Phase 2/3 commit **first**; then run one
`/hm:review` in each; then assert `missing: []` with seven lenses, `unstamped: []`, no undispatched
reviewer in the frontmatter, and a non-empty `lenses_exercised`. The `unstamped: []` conjunct is
new — the drafted exit could not observe the very defect that had 19/19 incidence in the only real
run.

## 🛬 Phase 1 — REQUIRED LAND-TIME STEP (do not skip; the phase is inert without it)

**Promoting `.claude/observability/.ledger-exclusions.json` cannot happen in this branch, and
the phase's measurable outcome does not exist until it does.**

The file currently holds the legacy one-key map. The base repo's code cannot read the promoted
list form — it takes the "is not an object" branch and excludes **nothing**, which silently
disables the pre-existing `aiexit-exec-p2b` exclusion. Promoting it early was tried during
execute and reverted for exactly that reason. So the mechanism ships correct, wired, tested —
and **unconfigured**: 144 `slug: "s"` rows plus 6 `hm-ledger-canary*` rows are still counted in
every aggregate, and the 64.9% → 1.3% correction exists only inside `tmp_path` fixtures.
Two review lenses found this by escalating outside the worktree; it is the absent-case class
(count:8) with the migration step skipped.

**Immediately after this branch lands on main**, replace the file with:

```json
[
  {"key": "run_id", "value": "aiexit-exec-p2b", "reason": "PASS emitted BEFORE the A.5 round it claims to describe was dispatched (2026-08-14, PLAN-ai-review-exit-criteria)."},
  {"key": "slug", "value": "s", "reason": "Synthetic rows from tests/unit/test_second_opinion_invoke.py before the 2026-08-17 conftest redirect; ~140 pytest runs."},
  {"key": "slug", "value": "hm-ledger-canary", "reason": "Canary rows from Phase 1 RED runs of tests/unit/test_ledger_isolation.py."},
  {"key": "slug", "value": "hm-ledger-canary-invoke", "reason": "Same, from the direct-invoke canary."}
]
```

then run `hm verifier_discrimination report` and record the corrected per-model rate. **Verify
the ordering**: promoting before the reader is on main re-breaks the existing exclusion.

## 🚧 Phase 1 — Phase A.5 gate history (rounds 1-2 FAIL; round 3 authorised)

**Round 3 was authorised by the operator after the two-round budget was exhausted**, on the
reading that the loop was converging rather than stalled. Repairs made for round 3: the bypass
predicate was split into three that measure the replacement value rather than the call shape
(closing B1 and B4 together, since they pulled in opposite directions on one predicate); the
direct-invoke test's CLI boundary was stubbed and its vacuous enum assertion narrowed (B3); and
two tests were added for the helper's third consumer (B5). **B2 was NOT handled as a test fix** —
it is a design constraint and is now recorded inline in Phase 1's exit criterion above.

A false positive introduced during those repairs is worth recording, because it is the same
mistake one function away from where a lens had just named it: the first `_passes_cwd_as_base_root`
flagged every `"--root"` constant, and immediately indicted
`test_second_opinion_budget_advisory.py`, which passes `--root str(tmp_path)` — the safest form
there is. It now inspects the value. **Consequence for RESEARCH: that file is not a leak site.**
The one real site is `test_second_opinion_invoke.py:740`.

### Round 3 result: FAIL (3 of 3 lenses). Four blocking findings, one of them self-inflicted.

- **R3-1 (two lenses, one root cause) — the `subprocess.run` stub added in round 3 to fix B3 is
  wired to the wrong channel.** The codex branch of `invoke()` never reads `proc.stdout`: it
  creates an empty `mkstemp` file (`:518-521`), passes it as `--output-last-message` (`:522-526`),
  and reads the payload back from that path (`:580-604`). The stub writes stdout and leaves the
  file empty, so `json.loads("")` raises and the status is `failed` — meaning
  `assert result["status"] == "invoked"` **cannot go green under any correct implementation**. A
  coder chasing it would plausibly delete the stub and reinstate the real paid `codex exec` that a
  lens had removed one round earlier. Fix (specified by the lens): have the stub parse
  `--output-last-message <path>` out of `argv` and write `{"findings": []}` there.
  Two riders: the same stub would also intercept `_git_stdout` if Phase C's redirect relocates
  rather than replaces the resolver; and the two canaries' sole-row assertions require a
  **function-scoped** sandbox (already recorded as constraint B2 above).
- **R3-2 — `_restores_the_real_resolver` is defeated by one hop.** It checks a single node, so
  `_REAL = soi.resolve_base_root` + `setattr(soi, "resolve_base_root", _REAL)`,
  `functools.partial(...)`, and `from … import resolve_base_root` all pass. The lens also
  correctly refuted the round-3 justification: the mutation probe exercised only the two spellings
  the predicate already recognised, so it bounds nothing. Fix: walk the replacement subtree, and
  taint module-level aliases.
- **R3-3 — the `marginal_gain` test's name and failure message claim delegation its assertions
  cannot see.** A private duplicate of the predicate inside `verifier_discrimination` passes it.
  Fix: assert the loader identity, or rename so the test does not claim what it cannot observe.
- **R3-4 (coverage, and the most valuable of the four) — conjunct 3's malformed-file clause never
  reaches a call site.** Every seam test writes well-formed JSON; the only torn-file assertion
  calls the helper directly. So the wrong implementation *that is on disk today* — `verifier_
  discrimination` keeping a private loader alongside the new helper — passes the entire set. One
  seam test with `{not json` next to a real ledger is the only assertion in the suite a private
  per-site loader cannot satisfy.

**Ledger note — the harness cannot express this episode.** `stage_agent_ledger coherence` reports
this run `BAD`: "the terminal row is pass 2 but the run continues to 3". That is not a mistake in
the rows. `execute.md.j2` explicitly anticipates a pass beyond the cap ("still record it, and add
`--reason`") while also requiring exactly one `--terminal` per group and forbidding a retraction
(append-only). Once pass 2 is correctly marked terminal, an operator-authorised pass 3 is
unrecordable coherently: marking it terminal gives the group two endings, omitting it gives the
group an ending it outlived. **An instruction and a tool disagreeing is the same defect class this
whole task is about.**

### Round 1-2 findings (all closed)

Ledger: `stage-agents.jsonl`, run `lensfix-p1-a5`, passes 1 and 2, terminal on 2.

**The loop was converging, and the budget stopped it** — the same reading `plan_rounds outcome`
gave the PLAN's own validation (`progress`, not `no-progress`). Round 1: 6 blocking issues across
three lenses. Round 2: 3 blocking issues, all different, plus one missing scenario. Nothing was
re-raised; every round-1 finding was closed.

### What survives, in the order it should be acted on

**B1 — `test_no_test_module_bypasses_the_ledger_redirect` indicts seven SAFE call sites.**
`tests/unit/test_record_disposition.py` (`:96, :141, :192, :224, :258, :281, :320`) each
`monkeypatch.setattr(second_opinion_invoke, "resolve_base_root", lambda _cwd: base)` where `base`
is under `tmp_path`. That is a *tighter* form of the protection AC-001 asks for, not a bypass —
its own docstring says it exists so 'a regression to cwd fails'. The AST predicate cannot
separate "patched back to the real resolver" from "patched to a test-owned directory", so the
test is RED against correct code. Greening it by editing those seven sites would delete a
regression guard for the documented `task-land` row-loss failure.

**B2 — an unconditional autouse patch breaks `test_second_opinion_invoke.py:133-168`.** Those five
assertions are of the form `soi.resolve_base_root(...) == repo.resolve()` — they test the resolver
*itself*, against a real git repo they construct. A module-attribute patch that always redirects
makes them fail. This is a **design constraint on Phase 1's implementation** that the two-file
Phase A.4 measurement could not see: the fixture must redirect only when the resolved root would
contain the tests tree, or must be opt-out-able by the resolver's own tests. Nothing in the SPEC,
the PLAN or the tests states it. **This is the finding that most changes the phase**, and it
arrived from the lens, not from the plan.

**B3 — `test_the_direct_invoke_entry_point_is_redirected_too` would make a real `codex exec` call.**
Nothing is mocked; `invoke()` reaches `subprocess.run(argv, …, timeout=CODEX_TIMEOUT_S)`. It is
currently RED only because `_assert_redirected` short-circuits before the call — the guard Phase C
removes. Its sole unconditional assertion, `result["status"] in {"invoked","skipped","failed"}`,
is the complete enum and cannot fail. Fix: stub the CLI boundary and assert the specific status.

**B4 — the bypass predicate is too narrow in the other direction** (discrimination): plain
attribute assignment, builtin `setattr(...)`, and `@patch("…")` are all invisible to it, as is the
non-repatch bypass of passing `base_root=Path.cwd()` outright.

**B5 — the helper's third consumer is unexercised** (coverage): `verifier_discrimination`'s
review-rounds path (`marginal_gain`, `:331/:335`) has the same `run_id in exclusions` filter and no
test drives it. Small, and the only gap left in the exit criterion's own terms.

**B1 and B4 pull in opposite directions on the same predicate** — one says it flags too much, the
other too little. That is not a contradiction: the predicate is measuring the wrong property
(AST spelling) instead of the right one (does the replacement restore the real resolver). Both
close together if it is rewritten to inspect the replacement value rather than the call shape.

### State on disk

Tests authored and RED; **no source file modified**. `tests/unit/test_ledger_isolation.py`,
`tests/unit/test_ledger_exclusions.py`, `tests/unit/test_ledger_exclusions_call_sites.py`.

**Six `hm-ledger-canary*` rows leaked into the base repo's real `second-opinion.jsonl`** during a
RED run, before `_assert_redirected` was corrected — the phase's own defect, reproduced by the
phase's own tests. They must be added to `.ledger-exclusions.json` as part of the implementation.

## 🧪 Testing Strategy

- **Unit** — the exclusion filter, both absent-key resolutions, the stamp scan, the agy envelope
  classification. Mock-first per CLAUDE.md; every one must pass `base_root`/`tmp_path` isolation,
  which is itself Phase 1's subject.
- **Render** — the three `review_doc` modes, with ADR-006's matrix rows.
- **Structural** — routing prose ↔ dispatch; observability audit completeness; orphan absence.
- **Property** — AC-001's suite-wide invariant: **no test can reach the enclosing repo's ledger at
  all**, because an autouse fixture redirects base-root resolution to `tmp_path`. This generalizes
  past the three known sites without depending on any per-test opt-in, and it never reads the
  shared base file, so a peer session's legitimate append cannot fail it. The canary test is what
  proves the fixture actually intercepts the leak shape.
- **Manual** — none in this PLAN; the live runs moved to the deferred task (ADR-008).
- **Mutation** — threshold 70 over exactly these paths (validator C11): `lens_coverage.py`,
  `verifier_discrimination.py`, `second_opinion_invoke.py`, `interview.py`, `models.py`. The
  new shared exclusion helper joins the set once its module name is fixed in Phase 1.
- **Baseline rule** — every phase exit is evaluated against a **clean worktree at the phase's own
  commit**, not the shared base tree. Eight structural tests fail in the base tree from another
  session's uncommitted work and pass 61/61 on a clean checkout of the same commit; without this
  rule "RED under mutation" and "the suite is green" are both ambiguous (validator C7 / codex 13).

## ⚠️ Risks & Mitigation

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| A new render gate is blind to its own subject | high — it has happened | high | ADR-006: every gating `{% if config.* %}` becomes a matrix row, each proven RED by mutation |
| The unstamped report runs only in round 1 | medium — recorded failure class | medium | Phase 2 exit conjuncts 3 and 4: a multi-round fixture, and a structural assertion that the instruction sits in the loop body and confirmation-pass body |
| The exclusions schema change breaks the existing stage-agents reader | medium | high — a silent regression re-enters an aggregate | ADR-007's migration is tested in both directions; Phase 1 exit conjunct 3 asserts both ledgers filter |
| The audit gate is a tautology and detects nothing | medium — it was, as first drafted | medium | Phase 5's AST-derived discovery plus a seeded-orphan case that must be detected |
| A peer session's legitimate ledger row fails Phase 1's gate | high — two sessions were live today | medium | The invariant is stated over attribution, not byte-identity |
| A future aggregator bypasses the exclusion helper | medium | high — the metric silently re-corrupts | Helper is the sole reader; Phase 1 migrates the existing one so there is no second precedent |
| Shrinking the instrumentation denominator changes a future cross-project verdict | certain | medium | Accepted in ADR-003 and stated at the config site |
| `frontmatter-only` reads as "frontmatter alone" to the next implementer | high | high — breaks multi-round review | ADR-005 documents the name at the config site; Phase 3's exit criterion asserts §7 and findings survive |
| Phase 2 and 3 both edit `review.md.j2` | certain | low | Declared as a merge hazard; same `parallel_group`, strictly serial |
| **The axis stays observed in exactly one project** | certain — ADR-008 accepts it | medium | Recorded as a deferred AC, not a passed one. Everything else here is verified by the gate class that this repo's own record shows can report clean for text it never opened |

## ✅ Success Criteria

**Status at wrapup (2026-08-17): PARTIAL.** Only **Phase 1** was implemented. Phases 2-5 were
never started, so their ACs are recorded **deferred**, not satisfied — an unticked box here is
the honest state, and ticking it would be the "verified by a gate that never opened the file"
failure this PLAN itself was written to close.

Phase 1 (done, bound in the machine SPEC):

- [x] AC-001 — no test can reach the base ledger: autouse redirect + canary test + AST bypass check
- [x] AC-002 — excluded slugs absent from numerator and denominator; file unchanged

Phases 2-5 (**deferred — not started**; each AC stays `pending_test: true` in the machine SPEC):

- [ ] AC-003 — routing prose names only agents `lens_dispatch` produces — *deferred (Phase 2)*
- [ ] AC-004 — `unstamped` reported; `blocks_approval` provably unchanged — *deferred (Phase 2)*
- [ ] AC-005 — absent `instrumentation` key resolves `False`, announced once — *deferred (Phase 3)*
- [ ] AC-006 — three modes render ADR-004's table exactly — *deferred (Phase 3)*
- [ ] AC-007 — `review_doc` defaults `frontmatter-only` on both paths — *deferred (Phase 3)*
- [ ] AC-008 — agy empty-response is a distinguishable class; `/hm:health` names it; rate reported from the filtered ledger — *deferred (Phase 4)*
- [ ] AC-009 — every **discovered** observability path appears in the audit, marked — *deferred (Phase 5)*
- [ ] AC-010 — no module writes an orphan path, **and** a seeded orphan is detected — *deferred (Phase 5)*
- [ ] ~~AC-011~~ — **deferred (ADR-008)**, not satisfied by this PLAN

## 🔍 Plan Validation

**Pass 1 — `plan-validator`: MAJOR_REVISION.** 12 critiques (2 critical, 7 warning, 3 suggestion).
Cross-model second opinion supplied by the main loop: **codex `invoked`** (13 findings, 1 P0);
**antigravity `failed`** — `status: SUCCESS` with an empty `response` and no `structured_output`,
the documented fail-closed path, warn-and-proceed. The verdict is Claude + codex only, and that is
valid without antigravity.

**Resolution of all 12** — four were put to the operator as A/B/C rounds, eight were revised
directly because the disposition was agreement and the fix mechanical:

| # | Disposition | Where it landed |
|---|---|---|
| C1 critical — exclusions file is run-id-keyed; second-opinion rows have no `run_id` | **A. revise** (operator: per-entry predicate schema) | New ADR-007; Phase 1 exit conjunct 3; Phase 1 risk raised low→medium |
| C2 critical — Phase 6 excludes the re-render its own exit needs | **A. revise** (operator: defer the phase) | New ADR-008; Phase 6 removed; AC-011 recorded deferred |
| C3 — machine-minimal omits `message`, which `finding_id` hashes | **A. revise** (operator: add it) | ADR-004 table; ADR-005 decision + rationale |
| C4 — Risks claimed a round-2 test the exit criterion did not contain | **A. revise** | Phase 2 exit conjuncts 3 and 4; Risks row rewritten |
| C5 — ADR-006's own matrix omitted `preset`, which gates the line Phase 2 rewrites | **A. revise** | ADR-006 axes + the admission that the ADR committed its own failure class |
| C6 — audit gate has no discovery method, so it can be a tautology | **A. revise** | Phase 5 Discovery method; seeded-orphan exit conjunct |
| C7 — byte-identity is nondeterministic with peer sessions live | **A. revise** | Phase 1 exit conjunct 1 restated over attribution; Testing Strategy; Risks |
| C8 — PLAN silently dropped SPEC AC-008's `/hm:health` conjunct | **A. revise** | Phase 4 scope-in + exit criterion |
| C9 — reversing a fleet ADR announced by `logger.info` | **A. revise** (operator: loud advisory) | ADR-003 decision + rejected alternatives |
| C10 — ADR-001 rejected blocking partly on a transient condition | **A. revise** | ADR-001 clause struck; revisit trigger added |
| C11 — mutation scope cited five paths never enumerated | **A. revise** | Testing Strategy enumerates them |
| C12 — two dependency edges were measurement convenience | **A. revise** | Phase 2 and Phase 5 `depends_on` → `[]` |

**Codex findings not adopted**, with grounds (the validator verified each at source):
- *finding 1* (stamp at the trusted ingest boundary) — reduces to the alternative ADR-001 already
  rejected by name: the result file is per-lens and keyed by its filename stem.
- *finding 10* (P4 needs a fuller taxonomy; the P1 edge is not a real dependency) — SPEC AC-008
  already fixes what "correct" means, and the P1 edge is a declared data dependency stated inline.
- *finding 12* (P6 should depend on P1–P4) — moot: P6 is gone. Its P2/P1 half is addressed by C12.
- *finding 11's* "empty orphan set is a vacuous pass" framing — the PLAN pre-empted it explicitly;
  the discovery-method half was accepted as C6.

**Pass 2 — terminal whole-document re-validation: `MAJOR_REVISION_TERMINAL`.**

`hm plan_rounds outcome`: **`progress`** — 12 resolved, 8 new, 0 unresolved. Measured PLAN churn
between the passes: **0.547** (the revision rewrote more than half the document). So the two-pass
cap stopped a loop that was still moving, not a stalled one — a third pass would buy findings, not
release, and every recorded three-pass episode in this repo also ended `MAJOR_REVISION`.

**Two of the eight are critical and both were CREATED by the pass-1 fixes** — which is the
documented reason this whole-document pass exists, and it reproduced exactly.

**Terminal findings are normally recorded and never revised, and `/hm:execute` carries them as
known risks without halting.** Three exceptions were made here, each deliberate and each recorded
as such:

- **C18** — acted on because Step 6's own invariant independently asserts that the frontmatter ADR
  count matches the heading count.
- **C13 and C14** — the operator was shown the terminal verdict and chose "fix the two criticals
  directly, then proceed". So the rule was **knowingly excepted for the two critical findings
  only**; C15-C17, C19 and C20 remain carried, unrevised. A later reader should treat the PLAN
  below as terminal-plus-two-repairs, not as a document that passed pass 2.

| # | Severity | Finding | Disposition |
|---|---|---|---|
| C13 | critical | **AC-001's oracle was stated three ways.** The C7 fix restated it over row attribution in Phase 1 and Testing Strategy, but Success Criteria, SPEC AC-001's `Then` clause, and the SPEC verification row still said byte/row identity — and the verification row is where an implementer copies the test name from. | **FIXED (post-terminal, operator-authorised).** One canonical form now, in all four places: Phase 1 conjunct 1, Testing Strategy, PLAN Success Criteria, and both SPEC sites (amended inline). |
| C14 | critical | **The replacement criterion turned on a "test-owned marker" that was never defined**, and `SecondOpinionRecord` is `extra="forbid"` so it cannot carry one — leaving a per-test slug convention, i.e. the hand list the suite-wide invariant exists to avoid. A leaking test using a realistic slug would be invisible. | **FIXED (post-terminal, operator-authorised).** Replaced detection with **prevention**: an autouse `tests/conftest.py` fixture redirects base-root resolution to `tmp_path`, so no test can reach the base ledger and nothing has to opt in. Proven by a canary test in the exact leak shape plus an AST bypass check. The shared base file is never read, so the peer-session flakiness C7 raised is gone too. |
| C15 | warning | **The unstamped report has no owner across the Phase 2/3 boundary.** Phase 2 adds it to `review.md.j2`; Phase 3 makes that file's sections conditional on `review_doc` with a table asserted exhaustive, and the report has no row in it — so the default mode may drop the advisory ADR-001 exists to surface. | **Carried.** Decide in execute whether it is CLI-only output or a named section present in all three modes. |
| C16 | warning | **Phase 1 still claims "Rollback: none needed"** while ADR-007 rewrites an on-disk format the existing reader depends on. On revert the old reader membership-tests a list, silently excluding nothing — the exact failure ADR-007 declares must be loud. The file is under gitignored `.claude/observability/`, so `git revert` does not restore it. | **Carried.** Execute must state whether the migration rewrites in place, and pick a rollback accordingly. |
| C17 | warning | **"The helper is the sole reader" is enforced by prose only.** ADR-002, Technical Design and a Risks row all name Phase 1's exit as the thing preventing a second unfiltered reader; no conjunct tests for a direct `open()`. Phase 5 was given AST-derived discovery for exactly this reason. | **Carried.** Either add the structural conjunct or downgrade the three claims to "convention, unenforced". |
| C18 | suggestion | Frontmatter counters stale (`adrs: 7` with eight ADRs; `interview_rounds`; "All six ADRs above"). | **Fixed** — Step 6 asserts this invariant independently. |
| C19 | suggestion | Phase 5's exit dropped SPEC AC-009's requirement that each audit row carry writer, readers, and surfacing command — keeping only the `consumed`/`orphan` mark. Same shape as C8. | **Carried.** |
| C20 | suggestion | Phase 4 and Phase 5 share `parallel-diagnostics` while Phase 5's AST scan will discover `second_opinion_invoke.py`, which Phase 4 edits. Friction, not a defect — that path is plainly consumed and will not be marked orphan. | **Carried.** |

**Two claims the validator checked and did NOT file**, worth recording because they close open
questions: ADR-003's "takes effect at the next `--update`" is consistent with AC-005 —
`_parse_instrumentation` has exactly one caller, `answers_from_harness_yaml`, which is the
re-render path. And Phase 2 exit conjunct 4 is structurally testable: `review.md.j2` has three
distinct `lens_coverage check` call sites (round 1, later rounds, confirmation pass), so "inside
the loop body and the confirmation-pass body" is a checkable claim rather than a wish.
