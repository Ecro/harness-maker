---
type: plan
task_slug: self-induced-regression-gate
status: complete
status_reason: "Landed in 43234d0e and released as 0.52.5; re-render at f4218a64. Review reached grade B against a threshold of A — not for unfinished work (no P0 or P1 open, full suite green, ruff/mypy clean, reviewer called it landable) but because every repair round in a task about self-induced churn produced self-induced churn. Closed 2026-08-19: the only act outstanding was this status flip. The surface growth was already folded into tests/structural/surface_baseline.json in 43234d0e with its BASELINE-DELTA attribution, so completion here RETIRES the 4396-char allowance rather than spending it — left in flight, it was pure unattributed headroom on an already-folded baseline."
created: 2026-08-17
tags: [harness-maker, plan, python, jinja2, review-loop, test-selection, churn]
interview_rounds: 6
adrs: 11
validator_outcome: MAJOR_REVISION_TERMINAL
summary: "Cut self-induced churn: one open review run per slug, per-class test routing, cache reuse, a scoped pre-repair declaration"
surface_allowance:
  chars: 4396
  reason: "MEASURED, replacing the 6000-char ceiling this block opened with. review gains review_run open + close on five branches + the id-source sentence; execute gains the three-line pre-repair declaration, the targeted-test-selection pointer and a corrected Phase D full-mode paragraph. The verification-cache reads both variants were also charged for were withdrawn in review (ADR-008 revised), so they cost nothing. Largest aggregate movement is codex at +4396."
  delta_doc: BASELINE-DELTA-self-induced-regression-gate.md
  commands:
    execute: 2008
    review: 2301
    hm-execute: 2092
    hm-review: 2304
  # No `round_trips` key on purpose. It is HEADROOM ADDED TO the frozen baseline, not the
  # absolute count — `round_trip_headroom` sums it into `surface[variant][cmd].round_trips`.
  # This task re-baselines `surface_baseline.json` in its own commit (attributed in the delta
  # doc's "Why this task may touch the ratchet at all"), so the movement is already folded in
  # and any headroom here would be counted a second time. Declaring `execute: 17` made the gate
  # demand 34.
---

# PLAN — self-induced-regression-gate

## 🎯 Executive Summary

**TL;DR.** Three independent sources of *self-induced churn* — work whose only cause is earlier
work by the same agent — get bounded, and one question gets asked earlier than it is asked
today. **No new quality gate is added, and one existing gate is suspended** — ADR-011 suspends
Phase A.5 for Phase 3 and names the falsifiability probe as its compensating control.

**What.**

1. `/hm:review` gets a **CLI-owned run identity**: at most one open run per slug, so a second
   invocation cannot start a parallel review with a fresh set of caps. *(This bounds run
   creation. It does **not** persist `iteration_count` — see ADR-003's narrowed claim.)*
2. `test_dep_map` stops routing `pyproject.toml` / `uv.lock` / `.github/workflows/*` to the
   loud-FULL default arm and routes `.claude/harness.yaml` to the render suites, so a version
   bump stops making every repair in that phase run the whole suite.
3. ~~`observability.verification_cache` is **read** by `/hm:execute` Phase D and `/hm:review`'s
   auto-fix loop.~~ **Withdrawn during review (ADR-008 revised).** The producer half was cut
   because `is_fresh` never compares check sets; the remaining consumer could then never hit,
   since both stages change files before reaching the read. Neither stage touches the cache now.
   `verify` / `wrapup` / `verify-before-completion` keep it — they hold both halves.
4. `/hm:execute` **declares three things** before Phase C writes a repair: the root-cause
   hypothesis, the repair's scope, and its non-goals — so only the necessary part is changed.

**Why.** The originating proposal asked for a hard "one repair rule" — stop and revert to the
last clean baseline when a fix induces a material regression. That was rejected (ADR-001): the
discarded work costs more than the churn it avoids, and this repository's five-layer worktree
defence makes automated reverts of uncommitted state the exact surface of a contamination class
that has recurred three times. What survives is the diagnosis, not the remedy.

**Key decisions.** ADR-001 (no gate, no revert) · ADR-002 (three declarations, no references) ·
ADR-003 (one open run per slug — narrowed) · ADR-004 (base definition unchanged, idempotence
added) · ADR-006 (per-class config routing) · ADR-008 (**revised in review** — the cache is not
touched by either stage) · ADR-010 (one A.5 dispatch, not three) · ADR-011 (Phase A.5 suspended
for Phase 3, with the falsifiability probe as the compensating control).

**Estimated impact.** Three Python modules changed, one added, two registries touched; two stage
templates edited; no `harness.yaml` schema change; no new user-facing flag.

## 🎯 Scope & Non-Goals

Collected in one place rather than scattered across the ADRs, so a reader — or `/hm:execute` —
can tell in one screen what this change touches and what it deliberately leaves alone. Every
non-goal below is a decision recorded in an ADR above, not an oversight.

### In scope

| File | Change |
|---|---|
| `test_dep_map.py` | `CLASS_CONFIG` + `CONFIG_SUITES` + the `select_tests` accumulation arm |
| `review_run.py` (new) | `open` / `status` / `close` / `open --force` |
| `command_registry.py`, `hm.py` | the two separate registrations |
| `freeze.py` | `resolve-base` idempotence + stamp repair |
| `worktree.py`, `.gitignore` | the run-state file's churn / gitignore membership |
| `execute.md.j2` | the pre-repair declaration, the cache `check`, the full-mode paragraph, the A.5 dispatch collapse (ADR-010), the Phase D pointer to `targeted-test-selection` |
| `review.md.j2` | `run open` / `close`, `<run-id>` sourcing, the cache `check` |
| this PLAN's frontmatter, `.claude/**`, `tests/snapshot/**` | allowance reconciliation + re-render |

### Non-goals

- **No repair gate and no automated revert** (ADR-001).
- **No measurement axis** — self-induced regression rate, corrective depth, rework LOC.
- **`review_base`'s definition is unchanged** (ADR-004); only the overwrite is removed.
- **`any-forces-all` is unchanged** (ADR-007) — a mixed change with an unhinted `.py` is still FULL.
- **`verification_cache.is_fresh` semantics are unchanged** (ADR-008) — which is why the read-only
  cache buys little inside a loop, stated in that ADR and in R7.
- **`iteration_count` is not persisted** (ADR-003) — resume-and-recount stays open, R8.
- **Rounds 2..N of the auto-fix loop are unchanged** — the churn gate already makes them a
  single-reviewer quick review or a skip, with second opinion off (Interview #16).
- **The Confirmation Pass is not narrowed.** It reads the whole review span on purpose: the
  last round's fixes always exit unreviewed, and fixes introduce defects at close to 1:1.
- **No new prohibition prose in Step 3 / Step 4** (ADR-005).
- **No `harness.yaml` schema change and no new knob.**
- **No offsetting deletions in stage prose** — growth is funded by the declared allowance (ADR-009).
- **No slug rename and no second worktree.**

## 📚 Prior Work

- `[wiki:architecture] review-autofix-batch-trigger` (2026-08-01) — the measured precedent. One
  task ran to 6 auto-fix rounds; 9 of 30 findings were defects in a previous round's own fix. It
  shipped `caused_by` attribution and three counters that, in its own words, **"gate nothing"**.
  This PLAN does not make them gate; ADR-001 explains why.
- `[fail:code] fix-introduced-defect-passes-all-gates` (count:4) — produced `/hm:execute` Phase
  D.5, the post-repair written gate. ADR-002 reuses its trigger sentence rather than restating it.
- `PLAN-workflow-step-audit` ADR-008 — introduced the four-way classifier this PLAN extends. Its
  own module comment names `pyproject.toml`, `uv.lock`, `.github/workflows/*.yml` and
  `.claude/harness.yaml` as landing on the default arm, and records that making them select
  *zero* tests was rejected as "strictly weaker". ADR-006 is the third option: a bounded,
  non-empty selection.
- Incident report, 2026-08-17, task `agent-session-attention-ux-unification` — six review runs
  created in one session, each with a fresh `run-id`. Source of ADR-003.
- `[fail:design] absent-case = feature black hole` (count:8) — the repo's most-recurring class.
  It is why ADR-002 was reduced to a referent that always exists.

## 🎙️ Interview Transcript

| # | Round | Topic | Category | Question | Choice | → ADR |
|---|---|---|---|---|---|---|
| 1 | 1 | material judgement | Architecture | What decides a "material self-induced regression"? | LLM judgement + category hints | ADR-002 |
| 2 | 1 | STOP behaviour | Risk tolerance | What happens when the rule fires? | Neither revert nor hard stop | ADR-001 |
| 3 | 1 | gate scope | Scope boundaries | Which stages get the gate? | Deferred, then withdrawn by #4 | ADR-001 |
| 4 | 1 | metrics axis | Scope boundaries | Include regression-rate / corrective-depth / rework-LOC? | Excluded | ADR-001 |
| 5 | 2 | contract location | Implementation phasing | Where does the pre-repair contract live? | `/hm:execute`, before Phase C | ADR-002 |
| 6 | 2 | contract persistence | Contract shape | Persist it to disk? | No — prompt declaration only | ADR-002 |
| 7 | 2 | failure reporting | Failure handling | Include "on failure, stop and report four things"? | Excluded | ADR-001 |
| 8 | 3 | run identity | Architecture | How is cap-bypass-by-new-run prevented? | CLI owns the run lifecycle | ADR-003 |
| 9 | 3 | review base | Contract shape | Redefine `review_base`? | Keep `merge-base`; add idempotence | ADR-004 |
| 10 | 3 | consensus ordering | Testing depth | Add "no fixes before consensus"? | No change — ordering forbids it | ADR-005 |
| 11 | 3 | contract shape | Contract shape | Reduce the 4-tuple after the duplication audit? | Reduced to 1 new + 3 references | ADR-002 |
| 12 | 4 | config classes | Architecture | Where do the config shapes route? | Per-class precise mapping | ADR-006 |
| 13 | 4 | forcing rule | Architecture | Change any-forces-all? | *Unanswered* — default adopted | ADR-007 |
| 14 | 4 | cache extension | Architecture | Extend `verification_cache` to execute / review? | Both | ADR-008 |
| 15 | 4 | review base (re-open) | Contract shape | Anchor at the previous review's terminal point? | No — keep current definition | ADR-004 |
| 16 | 4 | round 2+ scope | Testing depth | Make rounds 2+ quick and second-opinion-free? | **No work needed — already shipped** | — |
| 17 | 5 | workflows routing | Architecture | `.github/workflows/` after the inert claim was refuted | Fold into the new config class | ADR-006 |
| 18 | 5 | run state shape | Architecture | Persist counters, or narrow the claim? | **Narrow the claim** to one open run per slug | ADR-003 |
| 19 | 5 | cache producer | Failure handling | `mark-pass` in execute/review? | **No** — read-only in these stages | ADR-008 |
| 20 | 5 | contract referents | Contract shape | Absent case for the three references? | **Drop them** — hypothesis only | ADR-002 |
| 21 | 6 | scope + non-goal | Contract shape | Restore repair scope and non-goals? | **Yes, as declarations** rather than references — "고쳐야할 부분의 범위를 정하고, non-goal 을 명시해서 필요한 부분만 수정/리뷰 되도록" | ADR-002 |

Rounds 1–4 preceded plan validation. **Round 5 is the validator-driven revision round**: the
`plan-validator` returned `MAJOR_REVISION` with 7 criticals, four of which required an ADR
change rather than a wording fix. Those four are entries 17–20. The remaining ten critiques
were mechanical corrections and are recorded in `## 🔍 Plan Validation` rather than as rounds.

**Round 6 is operator-initiated and post-dates pass 1's resolution of C7.** It supplies the
option neither the validator nor revision 2 considered — that the absent case belongs to the
*reference* and not to the *content*, so declaring scope and non-goals restores the brake
without reintroducing the missing referents. Its effect is confined to ADR-002 and the sites
that quote it.

## 📐 Architecture Decision Records

### ADR-001: No hard repair gate and no automated revert
**Status:** Accepted (2026-08-17, via /hm:plan interview)
**Context:** The originating proposal's central rule was that a fix which induces a material
regression must not be patched again — stop, revert to the last clean baseline, and re-derive
the root cause with the failure as a new constraint. The detection mechanism already exists here
(`caused_by`, stamped once at a finding's first appearance).
**Decision:** Do not build the gate and do not revert.
**Consequences:**
- ✅ Zero interaction with the five-layer worktree/stash defence. An automated revert of
  *uncommitted* state is the same surface as `worktree-finalize-pulls-orphan-wip-into-main`,
  which has recurred three times.
- ✅ No work is discarded, which was the stated objection.
- ⚠️ Patch-on-patch remains possible. The remaining bounds are the round cap, the no-progress
  invariant and the confirmation-pass two-pass cap — all counters, none causal.
- ⚠️ With the metrics axis also excluded, this PLAN ships **no way to measure whether anything
  here reduced self-induced regressions.** The three existing counters keep accruing and remain
  the raw material for a later measurement PLAN.
**Rejected alternatives:**
- Hard STOP + revert to baseline — rejected: cost of discarded work, plus the contamination surface.
- STOP + print the revert command without running it — rejected with the same answer.
- Excluding P0/P1 from auto-fix (from the incident report's remedy list) — rejected: auto-fix
  would then repair only findings that do not matter, and the measured problem was runaway
  re-review, not wrong P0/P1 repairs.
**Source:** Interview #2, #3, #4, #7

### ADR-002: The pre-repair block DECLARES hypothesis, scope and non-goals — it references nothing
**Status:** Accepted (2026-08-17, via /hm:plan interview; **revised in rounds 5 and 6**)
**Context:** The proposal asked for four things to be fixed before editing: root-cause
hypothesis, repair scope, invariants that must not break, non-goals. A duplication audit found
three of the four already exist upstream, so revision 1 kept them as one-line *re-confirmations*
pointing at those artefacts. Validation then found that two of those referents **have no absent
case**: SPEC loading is conditional (`execute.md.j2:114` — "when frontmatter references them"),
so a task-driven PLAN has no `## 🚫 Non-Goals`; and under `--no-tdd` Phase A is skipped, so "the
properties Phase A's tests pin" do not exist. That is this repository's most-recurring failure
class (count:8) reproduced inside the change meant to reduce churn. Revision 2 therefore cut all
three, leaving only the hypothesis.

**Round 6 identifies the option both revisions missed: declare, do not reference.** The absent
case belongs to the *reference*, not to the *content*. "What this repair will change" and "what
it will deliberately not touch" always exist — in every `dev_mode`, with or without a SPEC, with
or without TDD — because they are properties of the repair the agent is about to make, not
lookups into an upstream document that may not be there.
**Decision:** Immediately before Phase C, on the defect-fix path only, **declare** three things
for this repair, in the turn output, persisting none of them:
1. the **root-cause hypothesis** (worded in full, never the bare "Hypothesis");
2. the **repair scope** — the files and call sites this repair will change;
3. the **non-goals** — what it will deliberately not touch, including any refactor, cleanup or
   API improvement noticed while reading. Enlarging the change enlarges the space for a
   self-induced regression, which is the whole premise of this PLAN.

Reuse Phase D.5's existing trigger sentence verbatim as the entry condition. Do **not** phrase
any item as a lookup into PLAN or SPEC.
**Consequences:**
- ✅ No absent case is reachable. Every item is a statement about the repair itself; none is a
  dereference of an artefact that may not exist. This is what makes it survive the count:8 class
  that killed revision 1.
- ✅ The non-goal line is the operative brake on scope creep at the moment it happens. Its
  existing counterparts are all *downstream* — `execute.md.j2:494` and the Quality Bar check for
  out-of-scope diff **after** the work, and SPEC Non-Goals is written before the task rather
  than before the repair.
- ✅ No vocabulary collision. `execute.md.j2:169-180` uses **Hypothesis** for the Python
  property-testing library; `:172` and `:244` use **invariant** for metamorphic relations. The
  fourth item of the source proposal — "invariants that must not break" — stays dropped for
  exactly that reason, and because Phase A's tests and Phase D.5's window question already carry it.
- ✅ One trigger definition, not two. A second, independently-worded trigger would drift from
  D.5's and produce a state where D.5 runs and this does not.
- ⚠️ Nothing is persisted, so nothing verifies the declaration happened or that the repair
  respected it; a render test can only assert the prompt is present. The downstream
  out-of-scope-diff check remains the only enforcement, and it is unchanged by this PLAN.
- ⚠️ It sits before Phase C, but on the TDD path the true "before the repair" moment is before
  Phase A. Placement was chosen explicitly (Interview #5) and the cost stands.
- ⚠️ Three lines rather than one costs more of `execute`'s 871 characters of headroom than
  revision 2 did. The allowance already funds it (ADR-009).
**Rejected alternatives:**
- Re-confirming the three by **reference** to PLAN scope / SPEC Non-Goals / Phase A properties —
  rejected in round 5: two of the three referents are frequently absent and nothing verifies
  which branch fired.
- Dropping scope and non-goals entirely (revision 2) — rejected in round 6: it discarded the
  brake along with the broken reference, and the declaration form has no absent case.
- Restating the source proposal's fourth item, "invariants that must not break" — rejected:
  vocabulary collision, and Phase A plus Phase D.5 already cover it.
- A machine artefact (JSON/YAML) — rejected as too costly for the value (Interview #6).
- Placement before Phase A — rejected: Phase A is skipped under `--no-tdd`, so it needs two sites.
**Source:** Interview #1, #5, #6, #11, #20, #21

### ADR-003: One open `/hm:review` run per slug, owned by the CLI
**Status:** Accepted (2026-08-17, via /hm:plan interview; **claim narrowed in round 5**)
**Context:** `review.md.j2:388` instructs the model to mint `<run-id>` itself. On 2026-08-17 one
session created six runs for one slug, each with its own `iteration_count`, its own
`review_base` resolution and its own confirmation-pass budget.
**Decision:** Add `hm review_run open|status|close`. `open` refuses when a non-terminal run
exists for the slug and prints that run's id and state; the stage resumes it rather than
starting another. `close` releases the slug and **reports** the terminal outcome on stdout — it
does not persist it, and nothing reads it afterwards; the record is unlinked. (The earlier
wording said "records", which described a durability the code has never had.) The stage reads
the id from `open` and
uses it **everywhere `<run-id>` appears** — lens-results paths, `stage_agent_ledger`,
`persist-payload` — never minting one.
**The claim is exactly this and no more: at most one open run per slug.** It does **not**
persist `iteration_count` or the confirmation-pass count. Those live only as prompt prose
(`review.md.j2:704, :708, :858, :953`) and nothing in `src/` records them.
**Consequences:**
- ✅ The observed bypass — six parallel runs — is closed in code. The violating session was
  reading the prompt, so a prompt rule would have been the same defence that already failed.
- ✅ A stable id means `review_base` (via ADR-004's ref), the lens-results directory and the
  ledger all key on one identity instead of six.
- ⚠️ **Resume-and-recount is not closed.** A session that hits the refusal, resumes, and starts
  counting rounds from 1 again is not detected. This is accepted (Interview #18): persisting the
  counters means a `bump` call in the round loop, in the stage with 230 characters of headroom,
  and a missed round silently under-counts — which is a worse failure than the one it fixes,
  because it looks like compliance.
- ⚠️ A crashed or abandoned run leaves a non-terminal record that blocks the next `open`.
  Recovery is **takeover**, not expiry — the conclusion `.hm-task-*` markers reached: a long
  review and an abandoned one are indistinguishable from elapsed time alone.
- ⚠️ Not every review terminates at a STOP line (see ADR-006's sibling problem in Phase 3): the
  autopilot and loop-mode paths leave the Grade Gate without stopping, and a `close` wired only
  to STOPs would leave those runs open forever.
**Rejected alternatives:**
- Prompt rule only — rejected above.
- Persisting the counters in the run record — rejected (Interview #18), reasons in the
  consequence above.
- Reusing the `freeze` ref's existence as the signal — rejected: it cannot distinguish a
  terminal run from an in-flight one, so a normally-finished review would block the next.
- A TTL / Stop-hook auto-close — rejected: hook wiring is a separate design in this repo, and
  the Stop hook's `cwd` is the project root, so it cannot attribute a worktree-scoped run.
**Source:** Interview #8, #18

### ADR-004: `review_base` keeps its definition; `resolve-base` becomes idempotent
**Status:** Accepted (2026-08-17, via /hm:plan interview)
**Context:** `freeze.py` resolves and stores unconditionally, so a second round-1 silently
re-bases a review in flight — the incident report's fourth claim. The definition itself
(`merge-base(HEAD, base-branch)`) means the span is everything since the branch diverged.
**Decision:** Leave the definition alone. Make `resolve-base` idempotent: when the ref exists,
return the stored value and warn on stderr instead of overwriting. **No override flag** — the
overwrite escape hatch is the single control this ADR exists to remove.
**Consequences:**
- ✅ The drift the template already forbids in prose becomes impossible in code, matching
  `read-base`'s existing loud failure.
- ✅ No new user-facing flag, consistent with the API-changes section.
- ⚠️ `store_review_base` writes **two** artefacts: the ref and
  `.claude/observability/.hm-freeze/<slug>.stamp`. The stamp is in the harness churn/gitignore
  set and `freeze reap` unlinks it, so **ref-present / stamp-absent is reachable, not
  hypothetical**, and the stamp exists because the ref points at a months-old merge-base and
  cannot carry the write time. The guard must therefore be keyed on the ref *and* repair a
  missing stamp, not return early on the ref alone.
- ⚠️ Review scope is still branch divergence, not repair scope. Re-opened in Interview #15 and
  re-affirmed: over-scoped review is expensive but not wrong.
**Rejected alternatives:**
- Anchor at the previous review's terminal point — rejected twice (Interview #9, #15).
- A `--base <sha>` override — rejected: in the incident the wrong base was noticed mid-review.
- An `--overwrite` escape hatch on `resolve-base` — rejected in round 5 as undeclared surface
  that reinstates the drift.
**Source:** Interview #9, #15

### ADR-005: No new prohibition on fixing before consensus
**Status:** Accepted (2026-08-17, via /hm:plan interview)
**Context:** The incident report's third claim — a single reviewer's Pass-1 P1 was treated as
final and repaired immediately. The template forbids this structurally (fixes happen only inside
the Auto-Fix Loop, downstream of Step 4's consensus filter) but never says so in a sentence.
**Decision:** Change nothing.
**Consequences:**
- ✅ No growth in the stage with the least headroom.
- ⚠️ The prohibition stays implicit. A reader entering at Step 3 sees no rule forbidding what
  that session did.
- ⚠️ **Interaction with ADR-003, accepted:** the ordering argument is *intra-invocation*, while
  ADR-003 makes a run resumable *across* invocations. A resumed run carries no durable evidence
  that Step 4 ran. Because ADR-003's claim was narrowed to run creation only, this gap is
  unchanged from today rather than newly opened — but it is now named.
**Rejected alternatives:**
- An explicit sentence — rejected (Interview #10).
- A `lens_coverage` completeness gate before the fix step — rejected with it.
**Source:** Interview #10

### ADR-006: One `CLASS_CONFIG` for the config shapes, plus a `select_tests` arm
**Status:** Accepted (2026-08-17, via /hm:plan interview; **revised in round 5**)
**Context:** `classify_path` is total; anything not `.j2`, not render-prefixed, not a doc with
consumers, not inert and not `.py` falls to the loud-FULL default arm — which holds
`pyproject.toml`, `uv.lock`, `.github/workflows/*.yml` and `.claude/harness.yaml`. Because
`select_tests` returns FULL when any changed file is forcing, one of these in a phase's change
set makes every repair in that phase run the whole suite, and this repo's release procedure
edits `pyproject.toml` on a five-file version sync.

The first revision routed `.github/workflows/` to **inert**. That was refuted during validation:
`tests/unit/test_profile.py:665-692` branches its assertion on whether that directory contains
files (`ci_provider == "github-actions"` vs `""`), and `tests/structural/test_no_fused_workflow_axis.py`
records that the directory is read by `profile.py`, `test_dep_map.py` and `readiness.py`. The
fallback the PLAN named — a `doc_consumers` entry — is also not expressible: those keys are
**exact paths** and the module comment forbids prefix entries.
**Decision:**
- `.claude/harness.yaml` → `_RENDER_AFFECTING_PREFIXES`.
- `pyproject.toml`, `uv.lock`, `.github/workflows/` → a new **`CLASS_CONFIG`** with its own
  curated `CONFIG_SUITES` tuple, deliberately broad, covering at minimum the suites that read
  those files (`tests/unit/test_profile.py`, the readiness suite, `tests/structural`).
- **Add the matching arm to `select_tests`'s accumulation loop.** Classification alone
  contributes no node ids: the loop has arms only for `RENDER_AFFECTING`, `DOC_WITH_CONSUMERS`
  and `SOURCE_WITH_HINTS`, so a new class without an arm makes a *mixed* change
  (`pyproject.toml` + one hinted `.py`) return `targeted` with the `.py` hints and **zero**
  config suites — reported as a clean targeted run.
**Consequences:**
- ✅ The forcing set shrinks to what it was meant to hold: source files no test maps to.
- ✅ No inert claim is made, so no false statement and no empty `node_ids` (the inert path
  returns `mode: targeted, node_ids: []`, which the first revision's exit criterion made
  logically impossible to satisfy).
- ⚠️ `CONFIG_SUITES` is a **claim that cannot be proven** — nothing confirms the chosen suites
  would catch a dependency regression. It is the same curated-and-fallible shape as
  `RENDER_AFFECTING_SUITES`, so it errs broad and Phase 1 records what it excludes and why.
- ⚠️ A `.github/workflows/` change now selects tests, which is *more* than the honest minimum
  for a pure CI-config edit. Over-selection is the accepted direction.
**Rejected alternatives:**
- `.github/workflows/` → inert — refuted by source.
- `.github/workflows/*` as a `doc_consumers` entry — not representable (exact-path keys only).
- Exact-path `doc_consumers` entries per workflow file — rejected: a new workflow file silently
  reverts to the default arm.
- All four to `RENDER_AFFECTING` — rejected: a lockfile change would select only render suites.
**Source:** Interview #12, #17

### ADR-010: Phase A.5 dispatches ONE test-reviewer carrying all three lens questions
**Status:** Accepted (2026-08-17, operator decision during implementation — **added after the
terminal validation pass, so no validator has seen it**)
**Context:** `execute.md.j2`'s Phase A.5 dispatches the `test-reviewer` agent three times in one
message, once per lens (`red-correctness`, `discrimination`, `coverage`). The lenses are not a
property of the agent — the agent is one file; the lens is a single line appended to an
otherwise identical brief by the stage's dispatch table. Measured on this task's own Phase 1
round: three dispatches cost ≈330k subagent tokens and ≈2 minutes.
**Decision:** Dispatch **once**, with all three lens questions carried explicitly in the one
brief. Keep the three questions; drop the three separate contexts.
**Consequences:**
- ✅ Roughly one third the dispatch cost, and one merge instead of a three-way merge whose rules
  (dedupe on `file:function:category` carrying the union of `line`s, worst-quality `per_scenario`,
  intersection of `passing_tests`) exist only because there are three payloads.
- ⚠️ **This task's own measurement argues against the change, and it is recorded here rather
  than omitted.** Phase 1's round returned six blocking issues and **all six were solo finds** —
  no defect was reported by more than one lens. The highest-value one (four sibling tests assert
  the exact opposite for the same paths, so the phase's exit criterion `-k dep_map` GREEN was
  unreachable) came from `red-correctness` alone; the second (a factually wrong justification in
  a test's own docstring) from `discrimination` alone. Independent contexts, not the lens text,
  produced that spread.
- ⚠️ The stage's existing rationale for the fan-out — "one reviewer retried serially surfaces one
  category per round, so the two-round budget gets spent on defects that were all present from
  the start" — is about *serial retries*, which this does not reintroduce. One call with three
  questions is a middle ground the stage never had, not a return to the shape it rejected.
- ⚠️ Merge rules in the stage prose become mostly vestigial but are **not deleted**: a future
  reader restoring the fan-out needs them, and they still describe how to fold a round-2
  re-dispatch into round 1's record.
**Rejected alternatives:**
- Reducing to one lens as well as one dispatch — rejected: on this round it would have missed
  four of six blocking issues, including the unreachable-exit-criterion one.
- Keeping three dispatches — rejected by the operator on cost.
**Source:** Operator instruction, 2026-08-17, during Phase 1 implementation

### ADR-011: Phase 3 suspends Phase A.5, because the RED gate's premise does not hold for prose
**Status:** Accepted (2026-08-17, operator decision after the second Phase 3 escalation)
**Context:** Phase A.5 is a RED gate: it assumes that when the implementation is absent, a
correct assertion fails. That holds when absence is **total** — Phase 1's classifier function and
Phase 2's CLI do not exist in the RED corpus in any form, and an assertion cannot accidentally
match. Phase 3's deliverable is ~4000 characters of edit inside two rendered documents of ~60KB
each: **absence is about 6%.** The RED corpus already contains the contract's whole vocabulary,
its placement neighbourhoods, and its exact command literals. So a Phase 3 assertion cannot be
validated against the corpus it runs on; it has to be validated against a post-edit corpus that
does not exist, which in practice means a simulation in the author's head.

Four A.5 rounds across two budgets produced **zero template edits** and findings of 5, 4, 3, 5.
Every finding was real; every repair was sound; two of the last round's findings were created by
the previous round's repair, and one of those made the test **RED under a faithful
implementation of the PLAN** — the test was driving the implementer toward a wrong edit.
**Decision:** For Phase 3 only, apply the template edits first, render, and validate the
assertions against **both** corpora — pre-edit (must be RED, already measured at
`21 failed, 6 passed`) and post-edit (must be GREEN). Keep the falsifiability probe for its
first two mutant classes, now applied to a real rendered artefact rather than to a hand-mutated
template.
**Consequences:**
- ✅ Every finding the last round reasoned about becomes mechanically visible: a raw-literal
  count surfaces as `== 2`, a placement clause as a failed ordering assert, an unprobed clause
  as one whose removal changes no RED/GREEN result.
- ✅ It removes the most expensive device in this session from the place it earned least. Nine
  A.5 dispatches cost ≈1.05M subagent tokens; the four spent here produced no deliverable.
- ⚠️ **RED-first ordering is lost for this phase**, and with it the protection against shaping
  assertions to the implementation just written — the exact bias A.5 exists to catch. The
  compensating control is that the probe's contract mutants must still turn the assertions RED
  against the real post-edit corpus; a confirmation-shaped assertion does not survive that.
- ⚠️ A suspended gate is the shape this repository's failure archive is full of. It is recorded
  here as a decision with a scope (`Phase 3 only`) rather than taken silently.
**Rejected alternatives:**
- A third A.5 budget — rejected: the remainder is a 33-cell matrix (11 assertions × 3 mutant
  classes, 15 filled) and a reviewer is a slow, expensive completeness checker for mechanical work.
- Deleting the placement assertions outright (offered as Path C) — deferred, not rejected; it
  remains available if the post-edit run shows they cannot be stated stably.
**Source:** Operator decision, 2026-08-17, second Phase 3 escalation

### ADR-007: `any-forces-all` is kept (assumption — question unanswered)
**Status:** Accepted (2026-08-17) — **adopted default, not a user decision**
**Context:** Asked in round 4 alongside ADR-006; the answer did not come back.
**Decision:** Keep the rule: one `CLASS_SOURCE_WITHOUT_HINTS` file still forces FULL for the
whole selection.
**Consequences:**
- ✅ "No test maps to this file" keeps meaning "we do not know what this breaks".
- ✅ ADR-006 shrinks the forcing set, which is the effective remedy.
- ⚠️ **A mixed change containing an unhinted `.py` file is still FULL**, config classes included.
  Phase 1's exit criterion and the success criteria must say so rather than claiming that mixing
  a config file with anything no longer forces FULL.
- ⚠️ Recorded as an assumption; never affirmed by the user.
**Rejected alternatives:**
- Union of targeted hints with the forcing file's fallback — rejected: it converts "unknown
  coverage" into "this fallback suffices" with no evidence.
**Source:** Interview #13

### ADR-008: `verification_cache` is READ by execute Phase D and the auto-fix loop, never written
**Status:** Accepted (2026-08-17, via /hm:plan interview; **producer half removed in round 5**)
**Context:** The cache is wired into `verify.md.j2` and `wrapup.md.j2` only. The two stages that
repeat the same checks never consult it. The first revision added `check` **and** `mark-pass` to
both. Validation refuted the producer half: `verification_cache.is_fresh` returns the marker
whenever `passed` is truthy and **never compares the requested checks against the recorded
`checks` list**, which `mark_passed` writes as an unvalidated label. The existing producers mark
`lint,format,mypy,pytest` after a **full** run; execute Phase D runs a **targeted** selection,
and ADR-006 makes targeted strictly more common. A `mark-pass` after a clean targeted run stamps
the same relevant-skip key, and the next `verify` / `wrapup` `check` skips the full suite.
**Decision:** Add `check --mode relevant` only, in both stages. Add **no** `mark-pass`.
**Consequences:**
- ✅ No false green is introduced. The consumer half is safe on its own:
  `compute_relevant_skip_key` hashes every relevant changed file's content, so a repair changes
  the key and misses the cache.
- ⚠️ The benefit is smaller than the first revision claimed. Within one `/hm:execute` or one
  auto-fix loop, nothing produces a marker, so a hit requires a prior `verify` / `wrapup` on the
  same fingerprint. The repeated-round amortisation the axis was chosen for **does not happen**.
- ⚠️ Making it happen means changing `is_fresh` to compare check sets — a change to shipped
  cache semantics that two other stages depend on. Deferred, not solved.
**Rejected alternatives:**
- `check` + `mark-pass` in both stages — refuted by source in round 5.
- Fixing `is_fresh` to compare `checks` — rejected for this PLAN (Interview #19): it changes
  behaviour `verify` and `wrapup` already rely on, and belongs in its own change.
- Dropping the axis entirely — rejected: the read half is free and correct.
**Source:** Interview #14, #19

### ADR-009: Growth is funded by a declared surface allowance, and the template phase is atomic
**Status:** Accepted (2026-08-17, via /hm:plan interview; **phase structure revised in round 5**)
**Context:** Measured 2026-08-17 under the budget test's own render: `review` has 230 characters
of headroom, `execute` 871. ADR-003 and ADR-008 both add mandated calls to `review`.

The first revision split template edits (phases 3, 4) from budget reconciliation (phase 5) and
excluded the round-trip parity test from the template phases' exit criteria **in prose**.
Validation showed the prose cannot hold: a `.j2` change classifies as `CLASS_RENDER_AFFECTING`,
whose suites are `tests/render`, `tests/snapshot`, `tests/structural`; `/hm:execute` Phase D runs
that selection as one `&&` chain and states "All must pass … do NOT advance". So the parity test
the PLAN excluded, and `tests/snapshot` which cannot be green before the re-render, would both
run and block the phase.
**Decision:** Declare `surface_allowance` in this PLAN's frontmatter with an attribution
document, and put **every template edit, the exact `round_trips` measurement, the allowance
tightening, and the re-render into ONE phase** (Phase 3). There is no intermediate state in
which a phase's own exit criterion is unsatisfiable.
**Consequences:**
- ✅ Phase 3's exit criterion is the unmodified suite. No exclusions, no prose override of a
  mechanical gate.
- ✅ Growth stays attributable and folds into `surface_baseline.json` at wrapup.
- ⚠️ Phase 3 is large — both templates, both variants, the allowance, and the re-render. It is
  atomic because the budget couples them, not because the work is small.
- ⚠️ `_sole_active` refuses to sum across two in-flight PLANs (`blocked` ones are exempt from the
  refusal). While this PLAN is `planning`, no other non-blocked PLAN in `work-docs/` may declare
  an allowance.
**Rejected alternatives:**
- Split template edits from reconciliation — refuted in round 5 by Phase D's own selection rule.
- Offsetting deletions — rejected: `review`'s slack is 230 characters *because* it has already
  been cut four times, and every one of those cuts removed a rationale sentence.
**Source:** Derived from Interview #8/#14 plus the measured baseline; revised by validation

## 🏗️ Technical Design

### Current state

| Concern | Where it lives now | Defect |
|---|---|---|
| review run identity | `review.md.j2:388` — the model mints `<run-id>` | no persistence; nothing stops N parallel runs per slug |
| review base | `freeze.py` `resolve_review_base` → `store_review_base` | unconditional overwrite; `read-base` is loud but `resolve-base` is silent |
| test selection | `classify_path` default arm → `CLASS_SOURCE_WITHOUT_HINTS` | four config shapes force FULL; `select_tests` then discards every other file's hints |
| verification cache | `verify.md.j2:67`, `wrapup.md.j2:151` | the two repeating loops never consult it |
| pre-repair reasoning | nothing before Phase C; Phase D.5 after the repair | the hypothesis is never stated, only its consequences audited |
| Phase D full-mode prose | `execute.md.j2:397-399` | names the four config shapes as full-mode triggers — false once ADR-006 lands |

### Affected components

- `src/harness_maker/test_dep_map.py` — `CLASS_CONFIG`, `CONFIG_SUITES`, the `classify_path`
  arms, **and** the `select_tests` accumulation arm.
- `src/harness_maker/freeze.py` — `resolve-base` idempotence including the stamp repair.
- `src/harness_maker/review_run.py` — **new**.
- `src/harness_maker/command_registry.py` — `MODULES` entry for `review_run`.
- `src/harness_maker/hm.py` — **`_DISPATCHABLE` allowlist entry**. This is a *second, separate*
  registration; an unlisted module exits 2 with "unknown module", so registry-only registration
  ships a CLI that every rendered call site cannot invoke.
- `src/harness_maker/worktree.py` — `_HARNESS_CHURN_PREFIXES` for the run-state file.
- `src/harness_maker/templates/stages/execute.md.j2`, `.../review.md.j2`.

### Data flow — review run identity

```
/hm:review <slug>
   │
   ▼
hm review_run open --slug S
   ├── no open run    → mint id, record {id, opened_at, state: open}, print id
   └── open run found → exit non-zero, print {id, state, opened_at}
                         stage RESUMES that run; never mints its own
   │
   ▼   the printed id is used for EVERY <run-id> site:
   │     .hm-lens-results/<slug>/<run-id>/…   stage_agent_ledger --run-id
   │     persist-payload --run-id             confirmation-pass rows
   │
   ▼
hm review_run close --slug S --run-id <id> --outcome APPROVED|CHANGES_REQUESTED
```

`close` must fire on **every** terminal path, and the Grade Gate's terminal paths are not all
`STOP` lines: `review.md.j2:679-714` has five STOPs, plus an autopilot path that carries the gate
onward as `--judgment-gate pending` (`:688-691`) and a loop-mode path that proceeds without
halting (`:692-696`). Confirmation Pass C3 adds four more outcomes. A `close` wired to STOP lines
alone leaves every autopilot and loop-mode review permanently blocking its slug.

### Design decisions

- The run record is a small state file at the **base repo root**, written by the CLI with the
  `atomic_write` pattern. A worktree-relative path is lost at `task-land` — the `codex_ledger`
  `Path.cwd()` mistake.
- It is operational churn: it must be in `_HARNESS_CHURN_PREFIXES` **and** the gitignore set. The
  finalize dirt filter reads the prefix tuple and never the glob (ADR-011 of
  PLAN-multisession-marker-scoping).
- Recovery from an abandoned run is takeover (`--force`, naming the run it displaces), never expiry.
- `classify_path` order is `render-affecting → doc-consumers → inert → .py → default`, so
  `.claude/harness.yaml` in `_RENDER_AFFECTING_PREFIXES` is reached first; no reordering needed.
- Classification stays **path-only, never `Path.exists()`** — the existing rule; a deleted or
  renamed file is the change most likely to break something.

### API changes

New CLI surface only; no `harness.yaml` schema change, no new user-facing flag on existing commands.

```
hm review_run open   --slug <slug> [--root <path>] [--force]
hm review_run status --slug <slug> [--root <path>]
hm review_run close  --slug <slug> --run-id <id> --outcome <APPROVED|CHANGES_REQUESTED>
```

## 📝 Implementation Plan

### Phase 1 — `CLASS_CONFIG` routing in `test_dep_map`

- `depends_on`: `[]`
- `parallel_group`: `serial-selector`
- `merge_hazards`: `src/harness_maker/test_dep_map.py` is `SELECTOR_SOURCE`. `select_tests`
  short-circuits to FULL for any change set containing it, and the module states that a
  selection it derives for its own edit is not evidence about anything. **This phase therefore
  runs alone and first** — a later phase verified against a mid-flight selector has no evidence.
- **Scope in:** `src/harness_maker/test_dep_map.py`, `tests/unit/test_test_dep_map*.py`
- **Scope out:** every template (Phase 3 owns `execute.md.j2:397-399`); `select_tests`'s forcing
  rule (ADR-007 keeps it)
- **Work:**
  1. Add `.claude/harness.yaml` to `_RENDER_AFFECTING_PREFIXES`.
  2. Add `CLASS_CONFIG` + `CONFIG_SUITES`, routed from `pyproject.toml`, `uv.lock` and the
     `.github/workflows/` prefix. Record in a module comment which suites are included and which
     are deliberately excluded (ADR-006's unprovable-claim consequence).
  3. **Add the `CLASS_CONFIG` arm to `select_tests`'s accumulation loop** — without it a mixed
     change silently contributes zero config suites.
  4. Extend the classification-coverage gate so a new suite that a config change should reach
     fails the build when it is unlisted.
- **Exit criterion:** `uv run pytest tests/unit -k dep_map` GREEN, including new tests that
  assert **all four** of these:
  - `select_tests(["pyproject.toml"])`, `(["uv.lock"])`, `([".github/workflows/ci.yml"])` each
    return `mode: targeted` with **non-empty** `node_ids` containing the config suites;
  - `select_tests([".claude/harness.yaml"])` returns `mode: targeted` with the render suites;
  - a **mixed** set `["pyproject.toml", "<a hinted .py>"]` returns `targeted` with **both** the
    `.py` hints **and** the config suites;
  - a **mixed** set `["pyproject.toml", "<an unhinted .py>"]` still returns `mode: full` — ADR-007
    is unchanged and the criterion must assert it rather than assume it away.
- **Risk:** medium — a wrong suite tuple trades always-FULL for sometimes-too-narrow.
- **Rollback:** revert to baseline; no other phase depends on this one.
- **Status: DONE** (2026-08-17). Exit criterion GREEN (`pytest tests/unit -k dep_map`, 104
  tests), and the full Phase D chain — `ruff check` → `ruff format --check` →
  `mypy --strict src tests` → `pytest` — exits 0.

#### Phase 1 — Phase D.5, newly-reachable window (written artifact)

This phase contained repairs, so D.5 applies.

**1. What input window does this repair newly make reachable?** A change set containing
`pyproject.toml`, `uv.lock` or `.github/workflows/*` used to return at `select_tests`'s
`forcing` early-return. It therefore **never reached** the accumulation loop, the
directory-subsumption dedup, or the empty-selection backstop. Those three paths are now
reachable for this input class for the first time. `.claude/harness.yaml` moved the same way,
into the render arm. The concrete combinations inside the window: config alone; config + hinted
source (subsumption between `CONFIG_SUITES`' `tests/structural` directory node and any
`tests/structural/test_*.py` hint); config + render-affecting (two directory-bearing classes
meeting in one accumulation); config + inert only (the arm carries the whole selection);
config + hintless source (must still be FULL); and a **deleted** workflow file, since
classification is path-only.

**2. Which test enters that window, and is it in this same change?** All of them are:

| Window | Test |
|---|---|
| config alone | `test_a_config_file_selects_the_config_suites`, `test_two_config_files_together_stay_targeted` |
| config + hinted source | `test_a_config_file_and_a_hinted_source_union_both_sets` |
| config + render-affecting | `test_a_config_file_and_a_template_union_both_suite_sets` |
| config + inert only | `test_a_config_file_beside_only_inert_paths_still_selects` |
| config + hintless source | `test_a_config_file_with_a_hintless_source_still_forces_full` |
| deleted config path | `test_a_deleted_workflow_file_classifies_by_its_path` |
| `.claude/harness.yaml` | `test_harness_yaml_selects_the_render_suites_not_the_config_suites` |
| breadth ceiling | `test_a_config_selection_leaves_part_of_the_unit_tree_unselected` |

The last three rows of the first column had **no test when Phase D went green**. D.5 is what
surfaced them; they were authored here rather than filed as a gap.

**3. Absent case** (the repo's count:8 class): the routing activates on paths that predate it,
so the window includes a config path whose file is **gone** — a deleted or renamed workflow. The
behaviour is "classify by the pre-change path", inherited from the module's path-only rule, and
it now has its own fixture rather than relying on that rule holding for a class added after it
was written.

> **Blocker (resolved) — A.5 two-round budget exhausted, and round 2's defects were created by
> round 1's repair.** Ledger run `sirg-p1-a5`, both rounds recorded, terminal on round 2.
> Resolved by the operator choosing **Path B** and a reset budget (ledger run
> `sirg-p1-a5-pathb`: round 1 FAIL, round 2 PASS with zero blocking issues). Kept below because
> the episode is the PLAN's own subject matter occurring inside its implementation.
>
> Round 1 (three dispatches) returned six blocking issues, **all six solo finds**. The
> highest-value one was structural: four cases in `tests/unit/test_test_dep_map_select.py`
> asserted the *opposite* classification for the same four config paths, so this phase's exit
> criterion (`-k dep_map` GREEN) was **unreachable** until that suite was amended. It has been.
>
> Round 2 (one dispatch, three questions — ADR-010's first use) returned two blocking issues,
> **both introduced by round 1's own repair.** Round 1 required deleting a `n == "tests/unit"`
> disjunct that let a bare directory satisfy the coverage assertion. The repair deleted it — and
> a *different* repair in the same round, the `_covered` / `_all_covered` helper, re-admitted it
> through the back door. `_covered` is justified by `select_tests` dropping node ids subsumed by
> a directory node it already selected; that justification does not hold where the assertion
> inspects the **constant** rather than a selection result. Consequence: `CONFIG_SUITES =
> ("tests/unit",)` passes the entire file, and the S5 omission gate becomes vacuous — the
> detector matches 29 test modules, 19 of them under `tests/unit/`, and a single directory entry
> swallows them.
>
> **This is the failure class the PLAN exists to bound, occurring inside the PLAN's own
> implementation.** It is recorded rather than smoothed over: ADR-001 declined to build a gate
> for it, and the A.5 round budget — a counter, not a causal rule — is what actually stopped the
> patch-on-patch here.
>
> **How it was actually resolved, and why the reviewer's remedy was not the one used.** The
> escalation's root cause was sharper than "a repair broke a repair": **`CONFIG_SUITES` had a
> floor and no ceiling.** ADR-006 specifies "at minimum the suites that read those files" and
> explicitly declines the other side ("it errs broad"), so every assertion about the constant
> was either unsatisfiable or vacuous, and two rounds were spent oscillating around a boundary
> the PLAN never wrote down. Path B states that ceiling **behaviourally** — a `pyproject.toml`
> change must leave at least one `tests/unit/test_*.py` module unselected. That rejects the
> degenerate `("tests/unit",)` without forbidding `tests/structural`, which ADR-006 names as a
> legitimate member and which a structural ban on bare directories would have outlawed.
>
> The next round then **refuted an explicit claim** that this single bound closed both prior
> defects. It closed one. The other lived in `TESTS_NOT_CONFIG_AFFECTING` — a separate constant
> that never enters a selection, so the bound could not reach it — where `("tests",)` disposed
> of every finding the coverage gate would ever make, and where the sibling precedent
> `TESTS_DIRS_NOT_RENDER_AFFECTING` is eight bare directories. That tuple got its own ceiling by
> a **different** argument: it disposes of file-level detector findings, so a directory entry is
> never needed, and the `CONFIG_SUITES` objection does not transfer.
>
> Two further defects of the same class surfaced in Phase C, both caught by the gate this phase
> built: `tests/integration/test_hm_console_script_resolves.py` asserted `mode: full` for
> `uv.lock` (a fourth file asserting the pre-change behaviour, in a directory no A.5 brief had
> scoped), and then the comment written to fix it re-tripped the detector on its own `uv.lock`
> literal.

### Phase 2 — `review_run` lifecycle CLI + `freeze` idempotence

- `depends_on`: `[1]` (serialized behind the selector edit, not data-dependent)
- `parallel_group`: `serial-python`
- `merge_hazards`: none with Phase 3 (different files); Phase 3 consumes this phase's CLI
- **Scope in:** `src/harness_maker/review_run.py` (new), `command_registry.py`, `hm.py`,
  `freeze.py`, `worktree.py` (churn prefixes), `.gitignore`, new unit tests
- **Scope out:** templates (Phase 3 wires them); persisting `iteration_count` (ADR-003 narrowed)
- **Work:**
  1. `review_run.py` with `open` / `status` / `close` / `open --force`, `atomic_write`, state
     file resolved against the **base repo root**.
  2. Register in `command_registry.MODULES`.
  3. **Register in `hm.py`'s `_DISPATCHABLE` allowlist** — the separate second registration.
  4. Add the state file to `_HARNESS_CHURN_PREFIXES` **and** the gitignore set.
  5. `freeze.resolve-base`: when the ref exists, return the stored commit and warn — **and
     repair a missing stamp file**, because `freeze reap` and the gitignore set make
     ref-present/stamp-absent reachable. No override flag.
- **Exit criterion:** `uv run pytest tests/unit tests/structural -k "review_run or freeze or hm_entrypoint"`
  GREEN, including: `open` twice yields the same id and a non-zero second exit; `close` then
  `open` yields a new id; `open --force` succeeds and names the displaced run; `resolve-base`
  twice returns one commit **and** the second call recreates a deleted stamp; `hm review_run
  status` is dispatchable end-to-end (not merely registry-listed).
- **Risk:** medium — a stuck-open run blocks reviews; `--force` and `status` are the remedy and
  are tested, not merely written.
- **Rollback:** revert to Phase 1's state.

### Phase 3 — Templates, budget reconciliation, and re-render (atomic)

- `depends_on`: `[1, 2]`
- `parallel_group`: `serial-templates`
- `merge_hazards`: `execute.md.j2`, `review.md.j2`, this PLAN's frontmatter, `.claude/**`
  re-render output, `tests/snapshot/**`. Atomic by ADR-009 — the budget couples the edits to the
  reconciliation, so splitting them creates a phase whose exit criterion cannot pass.
- **Scope in:** both stage templates, this PLAN's `surface_allowance` block, the delta document,
  regenerated snapshots, render tests
- **Scope out:** Step 3 / Step 4 ordering prose (ADR-005); `review_base` semantics (ADR-004); the
  churn-gated Step 6 (already correct — Interview #16); any `mark-pass` call (ADR-008)
- **Work:**
  1. `execute.md.j2`: the three-line declaration block before Phase C — root-cause hypothesis,
     repair scope, non-goals — gated on Phase D.5's existing trigger sentence by reference. Each
     item is phrased as a statement about this repair, never as a lookup into PLAN or SPEC
     (ADR-002); the non-goal line names refactors and cleanups noticed while reading as things
     this repair will not do.
  2. `execute.md.j2`: `verification_cache check --mode relevant` in Phase D, both variants.
  3. `execute.md.j2:397-399`: **rewrite the full-mode paragraph.** It currently names
     `pyproject.toml` / `uv.lock` / CI workflows / `harness.yaml` as full-mode triggers; after
     Phase 1 none of them is. Leaving it makes the prompt describe a selector that no longer
     exists, on exactly the class ADR-006 changes.
  4. `review.md.j2`: `review_run open` at the top of Round 1, with the branch prose — a refusal
     names the open run and the correct response is to **resume**, not to start another.
  5. `review.md.j2`: replace the `<run-id>` minting instruction (`:388`) with "read it from
     `open`", and confirm every other `<run-id>` site consumes that value.
  6. `review.md.j2`: `review_run close` on **every** terminal path. Enumerated from source
     during Phase 2, because the two review findings that flagged this (C6, C16) each counted
     it differently and neither matches the template:

     | Site | Branch |
     |---|---|
     | `:701` | `auto_fix` disabled → CHANGES_REQUESTED |
     | `:705` | `iteration_count ≥ max_review_rounds` AND `blocks_approval` |
     | `:709` | `iteration_count ≥ max_review_rounds` |
     | Auto-Fix Loop step 7b | the **no-progress invariant** — outside the Grade Gate block, which is why both findings missed it |
     | Confirmation Pass C3 | its four outcomes |

     **The Grade Gate's four APPROVE-side exits get no `close`.** `:860` gates the Confirmation
     Pass on "only when the gate would APPROVE", so the interactive STOP, the autopilot
     `--judgment-gate pending` path, the loop-mode proceed and the plain `STOP. Proceed to
     wrapup` all flow into C1–C3 first. Closing there releases the slug while the pass's freeze
     refs and ledger rows still use the id, double-closes at C3, and lets the next invocation
     mint a fresh id mid-review — the exact bypass ADR-003 removes. C16 named two of those four
     as terminal; they are not.
  7. `review.md.j2`: `verification_cache check` before the auto-fix loop's Step 5 verification.
  8. `execute.md.j2`: **collapse the Phase A.5 dispatch table to ONE `test-reviewer` call
     carrying all three lens questions** (ADR-010). Keep the merge rules — a round-2 re-dispatch
     still folds into round 1's record, and a future reader restoring the fan-out needs them.
     Added after the terminal validation pass, so no validator has seen this item.
  9. `execute.md.j2`: **point Phase D at the `targeted-test-selection` skill**, the way the
     auto-fix loop already does. No new policy — the skill already owns it and states it better
     than a fresh rule would: run `rerun_failed` first while iterating, then the targeted set,
     then the full suite; take the parallel flag from `hm test_runners plan` (it reports a
     capped `workers`, whether the runner is parallel by default, and what an unusable flag
     needs installed); and keep that flag on the command line, never in `addopts`, because a
     suite only ever run in parallel hides order- and isolation-dependent failures. Phase D
     currently writes its own `<lint> && <type> && <test>` shape and mentions none of it, so the
     stage's two verification paths disagree — that asymmetry is what this closes. No ADR: the
     decision already exists in the skill; this is a missing pointer, not a new choice.
  10. Measure rendered sizes and per-variant round-trip counts; write the exact `round_trips` map;
     tighten `chars` / `commands`; update the delta document.
  11. Re-render this repo's own `.claude/` — **deferred to land time, from the base repo root.**
     The instruction to do it "from the worktree" conflicts with a live guard: `cli.py:300-320`
     rejects `make --update` when cwd is inside `.worktrees/`, because
     `[fail:snapshot-regen-inside-worktree]` (**count:4**) turned that footgun into enforced
     prevention. A bypass env var exists for CI, and using it here would be routing around a
     guard that has fired four times. Nothing in Phase 3's exit criterion depends on it — every
     suite renders into a temp directory — and the repo's rendered harness should be generated
     from **main's** templates rather than a worktree's.

     **Snapshots ARE regenerated here**, and that is a different thing from the re-render above:
     `tests/snapshot/regenerate.py` is worktree-invariant by construction (triple-pinned), so
     running it from the worktree is correct — the "base only" rule was retired 2026-07-26.
     Worth recording how this was nearly missed: `pytest tests/snapshot` passes *unregenerated*,
     because the comparison lives in `tests/unit/test_synthesize_snapshot.py`. Running the
     directory that holds the fixtures and reading green from it is not evidence about the
     fixtures.
- **Exit criterion:** `uv run pytest tests/render tests/structural tests/snapshot tests/unit`
  GREEN **with no exclusions**, plus `uv run ruff check` and `uv run mypy --strict src tests`
  clean. Render tests must assert: the hypothesis line and both cache `check` calls render in
  both variants; **no** `mark-pass` renders in either stage; `review_run open` renders once;
  `review_run close` renders on an enumerated list of terminal paths that includes the two
  non-STOP ones; no "fresh UTC timestamp" minting instruction survives.
- **Risk:** medium — an exact round-trip map is easy to get wrong per variant, and the terminal-path
  enumeration is the phase's primary failure mode.
- **Rollback:** revert to Phase 2's state; phases 1 and 2 stand alone.
- **Status: DONE** (2026-08-17, under ADR-011's A.5 suspension).

  **Evidence, stated as observed rather than as a claim:** `ruff check`, `ruff format --check`
  and `mypy --strict` are green over 657 files. The 27 Phase 3 render assertions are green
  against the edited templates, and the falsifiability probe reports **16 mutants, 0 failing**
  across all three classes. A **complete** full-suite run failed in exactly two files —
  `tests/unit/test_synthesize_snapshot.py` (6) and `tests/unit/test_render_dispatch_macro.py`
  (4) — and both are now green targeted. A single confirming full run is deliberately left to
  `/hm:verify` / `/hm:wrapup` rather than repeated here; re-running everything after each edit is
  the wall-clock cost the `targeted-test-selection` skill names, and this phase spent three full
  runs on it before that was noticed.

  **Two selection facts worth carrying forward.** Both files that failed live in `tests/unit`,
  but both assert on *rendered output* — and `RENDER_AFFECTING_SUITES` is `tests/render`,
  `tests/snapshot`, `tests/structural`. A strict targeted selection on a `.j2` change would have
  missed them. Separately, `pytest tests/snapshot` passes with stale fixtures, because the
  comparison lives in `tests/unit/test_synthesize_snapshot.py`; running the directory that holds
  the fixtures is not evidence about the fixtures. Neither is fixed here — out of scope — but the
  first is a real gap in the constant Phase 1 extended.

#### Phase 3 — Phase D.5, newly-reachable window (written artifact)

This phase repaired tests its own change broke, so D.5 applies.

**1. The window.** Three frozen artefacts pin the *pre-change* shape of the A.5 dispatch, and the
collapse newly reaches all three: `test_multi_lens_a5.py` (count and contiguity of three
dispatch sites), `tests/fixtures/claude_arm_baseline.json` via `_COLLAPSED_MULTILINE` (the exact
Claude-arm dispatch lines), and the round-trip tables (`Task(subagent_type=` counts, which fall
by two). The window also includes the **ledger-off render**: Step 0 sits outside the
instrumentation conditional, so any consumer it names must exist in both configs.

**2. The tests that enter it, in this same change.** `test_multi_lens_a5.py` was rewritten to pin
the new contract (one dispatch, all three lens words in the dispatch LINE) rather than deleted.
`_COLLAPSED_MULTILINE` accounts for the removed lines per the test's own instruction rather than
regenerating the fixture. `test_roundtrip_budget.py`'s table was re-baselined with the −2/+1
arithmetic named. The ledger-off case is covered by `test_instrumentation_axis.py`, which caught
`persist-payload` leaking into Step 0 and is why that sentence no longer names it.

**3. Absent case.** The routing activates on configs that predate it: with
`instrumentation.stage_agent_ledger` **off**, the id-source sentence must still render — it does,
because Step 0 is unconditional, and `test_review_reads_the_run_id_from_open_at_every_consumer`
asserts exactly that config. That is the defect this PLAN found in the *existing* template, where
`<run-id>` had 19 consumers and zero sources with the ledger off.

> **Blocker — the second time this PLAN's own subject matter occurred inside its implementation,
> and the diagnosis is sharper than Phase 1's.**
>
> Round 1 returned five blocking issues, all one defect: a body-wide substring satisfied by prose
> the implementation never touches. Round 2 returned four, and **four of the five repairs moved
> the defect instead of removing it** — a shared `_window` helper was introduced to fix one
> assertion and applied to four, and in three the new window still contains the satisfying prose
> (`execute.md.j2:313-317` names two lens words independently of any dispatch;
> `review.md.j2:867-868` is one pre-existing sentence carrying three of the four terminal-branch
> tokens). A fourth counted `review_run open` only in the ledger-OFF render — the one config in
> which the two-`open` defect cannot appear.
>
> **Binding constraint (from `stuck`, verified at source):** every assertion in the file is a
> *containment* predicate over a corpus that already contains its vocabulary, and no step in the
> loop asks whether the predicate is falsifiable by deleting the implementation. Narrowing the
> window lowers the probability of a false pass without changing its kind, and its correctness
> depends on the author having enumerated every pre-existing sentence inside the window — the
> exact knowledge the author does not have.
>
> **The hypothesis this PLAN's executor offered was partly wrong, and the correction is the
> useful part.** The executor proposed that Phase 2 passed round 1 clean because its tests were
> written after reading the terminal-validation findings that named the traps. `stuck` refuted
> that with the repo's own comparison: Phase 2's assertions are **behavioural** — they shell out
> to a CLI that does not exist yet and assert on exit codes and JSON fields, so their false-pass
> surface is **zero**, not small, and they would have passed round 1 written blind. Phase 1
> converged one round after its assertion was restated as a behavioural bound (Path B, recorded
> above). Trap knowledge is a correlated mitigator; the *kind* of assertion is the variable that
> moved. An approach whose safety depends on having been told about each pre-existing sentence
> has no stopping condition.
>
> **The rule, in one line:** an assertion is finished when you have watched it fail against a
> mutant of the thing it pins, not when you have narrowed its window. For rendered prose, where
> the subject cannot be executed, the mutant is a deletion of the template lines plus a
> re-render — cheap, and it would have caught both `:313-317` and `:867-868` with nobody naming
> them.
>
> Not applied at escalation time: the stage forbids entering Phase C after two failing rounds,
> and `stuck` is advisory — the operator picks the unblock path.
>
> **Resolution — the operator chose Path B (deletion probe before dispatch).**
> `work-docs/probe-phase3-falsifiability.py` applies each named wrong implementation to the real
> template, renders, runs the one test meant to reject it, and requires RED. Baseline: **3 of 11
> assertions were inert** — M1 (lens words), M2 (`close` enumeration), M4 (`open` count) —
> exactly the three the reviewer named, found mechanically rather than by being told. After the
> remedies: **0 inert.**
>
> **The probe needed one refinement, and it was discovered by running it.** A falsifiability
> probe reports "this assertion CAN go red"; it does not report "it goes red because of the
> thing it pins". The first lens remedy anchored a fenced block on the string `test-reviewer`,
> which lands on a **prose mention** nine lines into the document and picks an unrelated block —
> red for the wrong reason, and the probe called it healthy. Two additions close that:
> - a **negative mutant** (`M1b`) that strips the lens words from the retry prose ONLY and
>   requires the assertion to stay **GREEN**. Red there means the anchor is wrong.
> - anchoring on the dispatch LINE (`(?:subagent_type|agent_type)="test-reviewer"` — the two
>   forms the renderer actually emits) rather than on the agent's name.
>
> **The probe also caught its own weak mutants, twice.** M3 was placed away from the preflight
> prose the reviewer cited, and M1 initially renamed descriptions while leaving `Your lens: …`
> inside each dispatch's prompt — both reported a result the mutant had not earned. A probe is
> only as strong as its mutants, and that is now written into the file.
>
> **Path B was not enough either, and the second escalation found why.** Four A.5 rounds across
> two budgets, zero template edits, findings per round 5 → 4 → 3 → 5. **A.5 is a RED gate, and
> its premise does not hold for a prose deliverable.** The gate assumes that when the
> implementation is absent, a correct assertion is RED — true when absence is *total*, as it was
> for Phase 1's `test_dep_map` function and Phase 2's `review_run.py` CLI. Phase 3's deliverable
> is ~4000 characters of edit inside two rendered documents of ~60KB each: **absence is about
> 6%.** The RED corpus already contains the contract's entire vocabulary, its placement
> neighbourhoods, and its exact command literals. An assertion therefore cannot be validated
> against the corpus it runs on — it must be validated against a **post-edit corpus that does
> not exist**, i.e. against a simulation in the author's head. The probe is that simulator, and
> it was extended three times because each round found another axis the simulation got wrong.
>
> That explains what the first diagnosis could not: why Phase 2 passed round 1 clean *written
> blind* (its false-pass surface was zero because absence was total, not because its assertions
> were better); why the correct-implementation mutant class had to be invented and is the one
> still incomplete (it is the only class needing the corpus that does not exist); and both of
> the last round's worst findings — one a mis-simulation of what the GREEN text will *say*
> (a legal id-source sentence must contain the literal `review_run open`, which a raw
> `body.count(...) == 1` cannot distinguish from an invocation), the other of where it will
> *sit* (`review.md.j2:218` is the first consumer; PLAN item 5 directs the edit at `:388`).
>
> **Convergence:** not convergent as run, but the remainder is **countable**. 11 assertions × 3
> mutant classes = 33 obligations; the probe holds 15. Three of the last round's five findings
> are "this cell is empty". The reviewer has been acting as a slow, expensive
> matrix-completeness checker for work that is mechanical. The triad is complete — a fourth leg
> would mean the rule is wrong, not the probe incomplete.
>
> **Third self-induced regression in this PLAN's own implementation, and the sharpest.** The
> ordering clause that failed under a faithful PLAN edit was *this executor's round-1 repair*,
> added in response to that round's own finding. The test was driving the implementer toward a
> wrong edit: the only route to green was to move prose the PLAN requires to stay.
>
> **What to stop doing** (from `stuck`, recorded because a rule with no prohibition is advice):
> stop adding mutant classes in response to findings (fill the 33-cell matrix instead); stop
> repairing an assertion by adding a clause to it (every clause-repair in four rounds created a
> defect; every repair that changed the assertion's *kind* terminated something); stop asserting
> **placement** in prose (three of five findings were placement clauses, and the PLAN's own
> target moved 170 lines); stop counting raw command literals; and stop reviewing tests against
> the unedited templates — that is the constraint itself.
>
> **Where this leaves the executor's hypothesis.** `stuck` was right that the variable is the
> *kind* of assertion, not prior knowledge of traps — but the rule needs both halves:
> **an assertion is finished when you have watched it fail against a mutant of the thing it
> pins, AND stay green against a mutant of everything else.** The second half is what separates
> a real anchor from a lucky one, and it is the half neither the reviewer nor the escalation
> named.

## 🧪 Testing Strategy

**Unit.** Phase 1's four selection assertions including both mixed shapes; Phase 2's
`open`/`close`/`status`/`--force` state machine, `resolve-base` idempotence, and the stamp-repair
absent case.

**Structural.** `hm.py` dispatchability in Phase 2 — not deferred to Phase 3, because an
exit criterion that cannot detect its own phase's primary failure is not an exit criterion. The
command size budget and round-trip parity in Phase 3 only, unexcluded.

**Render.** Phase 3 asserts presence per `is_codex` variant, **and asserts the absence** of
`mark-pass` — ADR-008's decision is a negative one, and only a negative assertion holds it.

**Snapshot.** Regenerated in Phase 3, from the worktree.

**Manual.** One `/hm:review` on a scratch slug: the second invocation refuses and names the open
run; `close` releases it; `--force` names the run it displaces.

> Standing limitation (CLAUDE.md): a render-grep test proves text is on disk, never that the CLI
> behaves. Phase 2's unit tests carry that half deliberately.

## ⚠️ Risks & Mitigation

| # | Risk | Severity | Mitigation |
|---|---|---|---|
| R1 | A config change selects too few tests and a regression ships | high | ADR-006 mandates a deliberately broad `CONFIG_SUITES` with written exclusions; Phase 1's coverage gate fails when a new suite is unlisted; the mixed-shape assertions catch the missing accumulation arm |
| R2 | Phase 3 misses a terminal path, so runs never close and every autopilot/loop review blocks its slug | high | The render test enumerates all five Grade Gate STOPs, the autopilot path, the loop-mode path and C3's four outcomes; `--force` + `status` are the operator remedy |
| R3 | `review_run` is registry-listed but not dispatchable | medium | Phase 2's exit criterion includes `tests/structural` and an end-to-end `status` invocation |
| R4 | The idempotence guard leaves the freeze stamp unrepairable | medium | Phase 2's exit criterion asserts the second call recreates a deleted stamp |
| R5 | Round-trip parity is wrong per variant and Phase 3 churns | medium | Measure both variants separately; the counting rule differs (`^!` vs `Bash(`) |
| R6 | Another non-blocked in-flight PLAN declares an allowance and `_sole_active` raises | low | Check `work-docs/` before starting Phase 3 |
| R7 | ADR-008's read-only cache yields no hits inside a loop, so the axis buys little | accepted | Stated in ADR-008's second consequence; fixing `is_fresh` is deferred to its own change |
| R8 | Resume-and-recount still bypasses the round caps | accepted | ADR-003's narrowed claim; the counters were deliberately not persisted (Interview #18) |
| R9 | ADR-001 leaves patch-on-patch unbounded and nothing measures whether this helped | accepted | Explicit in ADR-001; the three existing counters keep accruing for a later measurement PLAN |

## ✅ Success Criteria

- [ ] A second `/hm:review` for a slug with an open run refuses, names the open run, and the
      stage resumes it rather than minting a new id.
- [ ] `hm review_run status` runs end-to-end via `hm` (not merely registry-listed).
- [ ] `freeze resolve-base` twice returns one commit, warns on the second call, and recreates a
      deleted stamp file.
- [ ] `pyproject.toml`, `uv.lock`, `.github/workflows/*.yml` each return `mode: targeted` with
      non-empty `node_ids`; `.claude/harness.yaml` returns the render suites.
- [ ] A mixed change of a config file plus a **hinted** `.py` returns `targeted` with both sets
      of node ids; a mixed change with an **unhinted** `.py` still returns `mode: full`.
- [ ] `/hm:execute` Phase D and `/hm:review`'s auto-fix loop each render a
      `verification_cache check`, and **neither renders a `mark-pass`**.
- [ ] `execute.md.j2`'s full-mode paragraph no longer names the four config shapes.
- [ ] Phase A.5 renders exactly **one** `test-reviewer` dispatch, and its brief names all three
      lens questions (ADR-010).
- [ ] Phase D names the `targeted-test-selection` skill, so its verification advice matches the
      auto-fix loop's instead of contradicting it by omission.
- [ ] The rendered `execute` command declares root-cause hypothesis, repair scope and non-goals
      before Phase C on the defect-fix path only, without the bare word "Hypothesis", and with
      no item phrased as a reference to PLAN scope or SPEC Non-Goals.
- [ ] `tests/render tests/structural tests/snapshot tests/unit` GREEN with no exclusions.
- [ ] `ruff check` and `mypy --strict` clean.

## 🔍 Plan Validation

**Pass 1** — `plan-validator` (opus), run id `sirg-20260817-1`, duration 368s.
**Verdict: MAJOR_REVISION** — 7 critical, 6 warning, 1 suggestion. Cross-model second opinion
supplied to the validator: `codex` **invoked** (8 findings), `antigravity` **failed**
(`agy` returned `status: SUCCESS` with an empty response and no usable `structured_output` —
intermittent agy-side flakiness on large prompts; that model cast no vote in this validation).

`hm plan_rounds plan` queued all 14 critiques, skipping none (no previous pass to compare
against). Four required an ADR change and became interview rounds 17–20; the other ten were
mechanical corrections applied directly.

| # | Severity | Resolution |
|---|---|---|
| C1 | critical | **Revised** — ADR-009: phases 3–5 merged into one atomic Phase 3. A `.j2` change selects `tests/render` + `tests/snapshot` + `tests/structural`, and Phase D enforces "All must pass", so the prose exclusion could not hold. |
| C2 | critical | **Revised** — the impossible "non-empty `node_ids` for an inert path" criterion is gone; C3's resolution removes the inert routing that made it unreachable. |
| C3 | critical | **Revised (Interview #17)** — `.github/workflows/` folds into `CLASS_CONFIG`. The inert claim was false (`test_profile.py:665-692`) and the `doc_consumers` fallback was not representable (exact-path keys only). |
| C4 | critical | **Revised (Interview #18)** — ADR-003's claim narrowed to "one open run per slug". The Executive Summary's counter claim is corrected and R8 records the residual gap. |
| C5 | critical | **Revised (Interview #19)** — the `mark-pass` half of ADR-008 removed. `is_fresh` does not compare check sets, so a targeted-run marker would let `verify`/`wrapup` skip the full suite. Render tests now assert its **absence**. |
| C6 | critical | **Revised** — the Grade Gate has five STOPs plus two non-STOP terminal exits (autopilot, loop mode); Phase 3 item 6 and R2 enumerate all of them plus C3's four outcomes. |
| C7 | critical | **Revised (Interview #20), then amended (Interview #21)** — the broken *references* are gone, but scope and non-goals returned as **declarations**, which have no absent case. The finding's substance (two referents are frequently absent) holds; its implicit remedy (drop the content) did not survive round 6. |
| C8 | warning | **Revised** — Phase 1 item 3 adds the `select_tests` accumulation arm; both mixed-shape assertions added to the exit criterion. |
| C9 | warning | **Revised** — `hm.py` `_DISPATCHABLE` added to Affected components and Phase 2 item 3; Phase 2's exit criterion now includes `tests/structural` and an end-to-end invocation. |
| C10 | warning | **Revised** — Phase 3 item 3 takes ownership of `execute.md.j2:397-399`. |
| C11 | warning | **Revised** — the undeclared `--overwrite` flag removed from ADR-004 and Phase 2. |
| C12 | warning | **Revised** — ADR-004 and Phase 2 item 5 now cover the stamp-file absent case; asserted in the exit criterion. |
| C13 | warning | **Revised** — Phase 1 is `serial-selector`, runs alone and first, with `SELECTOR_SOURCE` named in its `merge_hazards`. |
| C14 | suggestion | **Moot** — ADR-002's three-reference argument was dropped in C7's resolution, so the misquoted citations no longer appear. |

Codex reconciliation by the validator: 5 accepted, 2 rejected with reasons (`53db19d6` — R6/R7
already carried it and `_sole_active` exempts `blocked` PLANs; `323c19a6` — the stated criterion
already exercises both states, and the genuine absent case is the stamp, raised as C12), 1
marked duplicate and superseded (`8f1d73e8` → C1, which supplied the mechanism codex missed).

**Pass 2 (first attempt)** — dispatched, then **stopped by the operator before it returned a
verdict**. It had begun reading source and produced no findings. Recorded in
`stage-agents.jsonl` as `dispatch-failed`, not as an approval: a terminated pass and a clean
pass must not look alike to a later reader.

**Pass 2 (terminal)** — re-dispatched against the round-6 document. **Verdict: MAJOR_REVISION**,
10 new findings, no second opinion supplied.

`hm plan_rounds outcome` compared the two passes: **`outcome: progress`** — `resolved_n: 14`,
`new_n: 10`, `unresolved_n: 0`. The revision step is working on this document; the two-pass cap
stopped a loop that was still moving, rather than one that had stalled. That distinction is the
reason the outcome is recorded at all: reporting "the cap fired" for both cases hides it.

**Resolution check on pass 1.** 12 of 14 hold. **Two do not:**
- **C6 does not hold.** The five Grade Gate STOPs were counted correctly, but two of them are on
  the APPROVE side and continue into the Confirmation Pass. See C16.
- **C14 does not hold.** It was closed as "moot — the citations no longer appear"; round 6
  reintroduced citations into ADR-002 and one of them is wrong. See C24.

### Terminal findings — carried into implementation as known risks

**These are recorded, not resolved.** `/hm:execute` proceeds and treats them as known risks; it
must not halt on this outcome, which is the normal ending of a loop that does not converge.
Five of them (marked ▲) are **factual corrections to this document**, not judgement calls — the
corrected fact is given inline so the executor applies it rather than rediscovering it.

| # | Sev | Finding | Carried as |
|---|---|---|---|
| C15 ▲ | critical | `_HARNESS_CHURN_PREFIXES` **does not exist** in `worktree.py`. The real constants are `_HARNESS_CHURN_DIRS` / `_FILES` / `_GLOBS` (which feed **gitignore**) and `_HARNESS_ARTIFACT_PREFIXES` (`:597`, which the source comment at `:131` identifies as the tuple the **finalize dirt filter** actually reads). The PLAN merges both roles onto one non-existent name, never names the state file's path, and Phase 2 asserts neither. | **Correction:** register the run-state file in `_HARNESS_ARTIFACT_PREFIXES` **and** the gitignore tuples, name its path, and assert both in Phase 2's exit criterion. Otherwise the live file becomes user dirt and `worktree finalize` stashes every open run — ADR-011 of PLAN-multisession-marker-scoping, repeated. |
| C16 ▲ | critical | Two of the five Grade Gate STOPs (`review.md.j2:687`, `:698`) are on the APPROVE side, and `:860` runs the Confirmation Pass "only when the gate would APPROVE". Closing there closes a run still in use by C1–C3's freeze refs and ledger rows, double-closes at C3 (ADR-003 defines no already-closed behaviour), and lets the next `open` mint a fresh id mid-review. | **Correction:** the terminal set is C3's four outcomes + the three non-approve Grade Gate exits (`:701`, `:705`, `:709`) + the two non-STOP paths. Define `close`'s already-closed case. C6's resolution over-enumerated. |
| C17 ▲ | critical | Both new cache calls are specified bare. `verification_cache.main` returns **1** on a miss (`:451-454`), and ADR-008's own consequence says a hit is nearly impossible in these stages — so **exit 1 is the expected outcome on essentially every call**. Both existing consumers define both arms (`verify.md.j2:75`, `wrapup.md.j2:159`). | **Correction:** specify the 0-arm and the 1-arm at both sites, matching the `verify`/`wrapup` form. An unbranched non-zero exit before the auto-fix loop's verification reads as a verification failure. |
| C18 | warning | The Executive Summary and ADR-006 claim a config file makes **every repair** run the whole suite. `execute.md.j2:400-401` says a repair re-runs targeted on the files it touched, `full` **once, at phase exit** (commit `acbe6a1`). | **Accepted risk.** The work stands on the phase-exit cost; the sizing in those two places is overstated by roughly an order of magnitude and a later reader should not use it. |
| C19 ▲ | warning | ADR-004's cited mechanism is refuted: `freeze reap` (`:267-284`) deletes ref **and** stamp together, so post-reap is both-absent. The real mechanism is that `FREEZE_STAMP_DIR` is gitignored per-worktree state while refs are shared across worktrees. The stamp also has **no reader anywhere in `src/`**. | **Correction:** the absent case is real for the worktree reason, not the reap reason. Record that the stamp currently has no consumer, so the repair's value is known. |
| C20 | warning | `review.md.j2:388` sits **inside** the `stage_agent_ledger` conditional (opened `:359`, closed `:402`), while `<run-id>` is consumed **outside** it (`:218`, `:232`, `:739`, `:904`, `:916`). The PLAN does not require `open` and the id-source sentence to render unconditionally, and "renders once" cannot detect the miss on this repo's config. | **Accepted risk** with a named remedy: assert against a render with `instrumentation.stage_agent_ledger: false`. Same silent-degradation shape as the `is_codex` context bug. |
| C21 | warning | Phase 1 edits `SELECTOR_SOURCE` (short-circuits to FULL) and Phase 2's scope includes `.gitignore` (default arm → FULL), so `/hm:execute` Phase D will enforce the **full** suite in both — strictly larger than the declared criteria. | **Accepted risk.** C1's class inverted: those criteria are not unsatisfiable, they are insufficient. Expect Phase D to run more than the criterion names. |
| C22 | warning | ADR-002 calls the non-goal line "the operative brake" while conceding nothing verifies it, in a PLAN whose ADR-003 rejects prompt-only defences on measured evidence. The declared scope has **no downstream reader**: `execute.md.j2:488` and the Quality Bar at `:614` compare against the **PLAN's** scope. | **Accepted, and the declaration form stands** (the validator agrees the absent case belonged to the reference). What does not stand is the strength of the word "operative": it is an unverified prompt-level statement. |
| C23 | suggestion | The delta doc says the per-command map names only `execute` and `review`; the frontmatter declares four keys. The two `hm-*` keys relax nothing for `command_headroom` (not in `_ATOMIC_RATCHET`) but are the correct keys for `round_trips`. | **Accepted risk.** Reconcile when Phase 3 writes the exact `round_trips` map. |
| C24 ▲ | suggestion | `execute.md.j2:494` is inside the blocked-path-only section. The out-of-scope-diff check is Step 4 item 1 at `:488`; the Quality Bar counterpart is `:614`. Every other round-6 citation verifies clean. | **Correction:** cite `:488` and `:614`. |

**Operator decision (Step 4 resolution).** Asked after the terminal pass: proceed with the
remaining critiques as accepted risk (A), or abort planning (B). **A was chosen.** The PLAN is
final; `/hm:execute` carries the ten findings above, applying the five marked ▲ as corrections.
The frontmatter keeps `MAJOR_REVISION_TERMINAL` rather than `MAJOR_REVISION_RESOLVED` because
that value carries strictly more information — a human accepted the risk *and* a second pass ran
and these survived it. A later reader needs both facts, and only one name records the second.

**Why no pass 3.** The plan stage caps validation at two passes, and this repository's recorded
episodes show every three-pass run also ending `MAJOR_REVISION` — a further pass buys findings,
not release. `MAJOR_REVISION_TERMINAL` is a distinct value from `MAJOR_REVISION` on purpose: it
means a second pass ran and these survived it, not "revise again".
