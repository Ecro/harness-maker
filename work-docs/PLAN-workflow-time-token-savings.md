---
type: plan
task_slug: workflow-time-token-savings
status: complete
created: 2026-08-08
tags: [harness-maker, plan, python, economics, observability, autonomy, autopilot]
research_doc: "[[RESEARCH-workflow-time-token-savings]]"
interview_rounds: 3
adrs: 10
validator_outcome: MAJOR_REVISION_RESOLVED_ROUND3
summary: "Fix the meter, adjudicate the ledger, pre-register the A/B; add auto_full + ask autonomy levels"
---

# PLAN — workflow time/token savings, and the autonomy level axis

## 🎯 Executive Summary

**Two tracks in one PLAN** (ADR-006), landed in one stated global order because they share files.

**Track A — measurement integrity, then a pre-registered experiment.**
`RESEARCH-workflow-time-token-savings` measured $11,022 across four projects: the cost is context
carry (72% of spend) and session length (20–54% of spend past the attribution span cap), not step
count. It also found the instrument broken twice over — `$0` reported for any project whose path
contains `_` (strange_chess: $1,637 invisible), and a stage-agent ledger that disagrees with the
transcript about whether 39 subagent dispatches happened. **Track A fixes the meter and
adjudicates the ledger before changing any workflow.** The session-length lever ships as a
pre-registered A/B protocol only (Interview #3, ADR-004).

**Track B — a real `auto_full` level, plus `ask`.**
`AutonomyConfig.level` is `["gated","auto_safe","full"]` today, and `full` is *deliberately*
identical to `auto_safe` (`models.py:790-796`: "NOT a gate-bypass"; REVIEW P6 corrected the
opposite wording once). Track B makes the top level advance further, by **fixing the gate layer
rather than decorating it** (Interview #5, ADR-009).

**The feature is narrower than the first three drafts claimed, and the narrowing is the most
important thing in this summary.** `auto_full` clears exactly **two** things: the plan stage's
architecture interview, and a review's `human_review_needed` flag on an **APPROVED** review. It
does **not** clear a `CHANGES_REQUESTED` grade (Interview #6, ADR-010) and it does not clear the
wrapup merge/land (Interview #1, ADR-002). Drafts 1–3 asserted "two judgment gates with
recommended answers"; validator round 3 showed the review gate's predicate is
`grade < threshold OR human_review_needed` — a failed quality threshold, not a question — so
auto-answering it would have meant advancing past a failed review, which `models.py:790-796`
forbids and which no interview had asked about. A fourth value `ask` makes the session-start
picker the source of the level.

**Key decisions:** ADR-001 (legacy `full` → `auto_safe`, never escalate) · ADR-002 (`auto_full`
stops at land) · ADR-003 (`ask` is yaml-only) · ADR-004 (measure before changing workflow) ·
ADR-005 (one constant, guarded by an AST discovery test) · ADR-006 (two tracks, one global order,
one declared exception) · ADR-007 (no rendered `--level` carries a meta-level; `/hm:health` skips
its smoke under `ask`) · ADR-008 (A2 emits a verdict token; the net-surface assertion is B5's and
**must be able to fail**) · ADR-009 (judgment gates are source-stage-keyed, and their pending
state is an **explicit fail-closed input** to `boundary`) · ADR-010 (the review gate splits:
grade is never clearable, `human_review_needed` is clearable at `auto_full` only).

**Estimated impact.** Track A recovers $1,637 of already-spent-but-invisible measurement and
either validates or withdraws the "keep both validator passes" verdict. Track B removes **one**
human stop per pipeline run outright (the plan interview) plus one conditional stop (an APPROVED
review's `human_review_needed`), at `auto_full` only; `auto_safe` and `gated` behave exactly as
they do today.

## 📚 Prior Work

- `[[RESEARCH-workflow-time-token-savings]]` — the measurement this PLAN acts on.
- `[[RESEARCH-workflow-loop-efficiency]]` / `[[PLAN-workflow-loop-efficiency]]` — stage 1. Its
  stage-2 scope was "delete the second validator pass and the Phase A.5 gate". The ledger it
  installed reports 22.2% and 37.5% yield for those steps, so **stage 2 is not a deletion
  stage** — conditional on Phase A2's verdict token.
- `[[BASELINE-DELTA-P7]]` §1 — stage 1 grew the shipped surface by +7,113 chars on an explicit
  condition. ADR-008 settles that debt on both of A3's branches; B5 asserts the net.
- **Correction carried forward from the RESEARCH doc.** Its "subagent share" was
  `subagent / (main + subagent)` wall clock; `economics._wall_clock_by_scope`'s docstring states
  the scopes overlap in real time and must never be summed, so that ratio is invalid. Defensible
  form: subagent wall clock is 0–25 h against main-loop 20–103 h per project, so parallelising
  subagents cannot compress main-loop time. Phase A4 forbids re-introducing the invalid quantity.
- **Four of this PLAN's own assertions were refuted by its validator and are recorded as
  corrections, not quietly fixed.** (1) Draft 1 claimed `boundary --current wrapup` returns
  `merge_gate`; it returns `pipeline_complete` (`autopilot_caps.py:316`). (2) Draft 2 claimed the
  level value set lived at five sites and that ADR-005 had "closed the hand-list class"; there
  are ten, and that claim was itself an instance of the class. (3) Draft 3 labelled a B3 criterion
  "the default is unchanged" while it **inverted** the default — it would have made `auto_safe`
  halt at plan→execute and review→verify unconditionally. (4) Drafts 1–3 called the review grade
  gate a "judgment gate with a recommended option"; it is a quality threshold. ADR-005, ADR-009
  and ADR-010 exist because those claims were wrong.
- `failures.md` classes this PLAN is exposed to: `absent-case = feature black hole` (count:8 —
  the autoarm ladder, `ask` + persistent, and non-default pipelines are all this shape),
  `new-marker-content-field-must-update-every-reader` (count:3 — ten level-declaration sites;
  this PLAN committed the error once), `ratchet-rebaselined-by-its-own-subject` (count:2 — four
  phases move `surface_baseline.json`).
- Memory: `feedback_subagent_model_override`, `project_background_exit_code_unreliable`,
  `feedback_pytest_background`.

## 🚫 Non-Goals

- **RESEARCH Approach D** (per-project composition routing) — needs a composition axis in
  `harness.yaml` that does not exist.
- **A `write_after_read` PreToolUse enforcement hook** — Interview #3 chose measure-first.
- **Implementing fresh-session wrapup** — ADR-004 ships the A/B protocol only.
- **Running the retroactive classifier** (RESEARCH Open Question 1, the unattributed 51%).
- **Deleting the second validator pass or the Phase A.5 gate** — actively rejected (RESEARCH
  Approach A, refuted at 22.2% / 37.5%).
- **Making `_HUMAN_GATED_STAGES` level-conditional** — the land gate is never level-dependent.
- **Letting any level advance past a `CHANGES_REQUESTED` grade** — ADR-010. This is a
  non-goal, not a deferral.

## 🎙️ Interview Transcript

| # | Topic | Category | Question | Options | Choice | Note | → ADR |
|---|---|---|---|---|---|---|---|
| 1 | `auto_full` land boundary | Risk tolerance | Should `auto_full` auto-advance through wrapup's merge/land? | A. land included / B. everything up to land / C. advance-only | **B — everything up to land** | The gate that mutates `main` stays human. Narrower than the literal "모두 자동 진행", chosen after the conflict with `models.py:790-796` was surfaced. | ADR-002 |
| 2 | Legacy `level: full` | Contract shape | How should an existing `harness.yaml` with `level: full` be read? | A. downgrade to `auto_safe` / B. promote to `auto_full` / C. reject | **A — downgrade to `auto_safe`** | Preserves ADR-013's "loading never escalates autonomy" and today's behaviour. | ADR-001 |
| 3 | Session-length lever strength | Scope boundaries | How far to take the session-length lever (20–54% of spend past the span cap)? | A. pre-registered A/B first / B. implement now / C. instrument fixes only | **A — pre-registered A/B first** | The fresh-session re-read cost is unmeasured; implementing now could relocate cost rather than remove it. | ADR-004 |
| 4 | Track A/B packaging | Implementation phasing | One PLAN or two? | A. one PLAN, two tracks / B. two PLANs / C. Track B first | **A — one PLAN, two tracks** | Speed was the stated priority. Coherence bounded in ADR-006. | ADR-006 |
| 5 | `auto_full` enforcement point | Architecture | `boundary` sits *below* the mandatory gate (`stage_end_summary.md.j2:33-40`: "gate FIRST … do NOT run the boundary check"), so it cannot govern the judgment gates. Where does enforcement live? | A. fix the gate layer / B. prose-only, grep-asserted / C. ship `ask` only | **A — fix the gate layer** | Accepts a high-risk phase in exchange for an `auto_full` a test can distinguish from `auto_safe`. B rejected: a grep-asserted control can pass while the behaviour is absent. | ADR-009 |
| 6 | The review gate | Risk tolerance | May `auto_full` advance past `CHANGES_REQUESTED` / `human_review_needed`? `models.py:790-796` forbids it and no prior round asked. | A. no, review gate holds at every level / B. `human_review_needed` only, never `grade < threshold` / C. yes, both / D. defer `auto_full`, ship `ask` only | **B — `human_review_needed` only** | Splits one gate into two predicates: a quality threshold that is never clearable, and an unverified-P0/P1 surfacing flag that `auto_full` may clear with a record. Highest implementation complexity of the four options, chosen over the simpler A. | ADR-010 |

**Questions generated and NOT asked** (5-term gate): `encode_project_dir` underscore fix — failed
EIG (verified empirically against five projects). Ledger-validity pre-check — failed
common-ground. `ask`-level persistence — failed confidence (`effective_level`'s marker-over-yaml
precedence answers it). `write_after_read` enforcement hook — out of scope after Interview #3.

## 📐 Architecture Decision Records

### ADR-001: Legacy `level: full` normalizes to `auto_safe`, never to `auto_full`
**Status:** Accepted (2026-08-08, via /hm:plan interview)
**Context:** `level` gains `auto_full`, which unlike today's `full` really does advance further.
Existing harnesses carry `level: full`, and `_parse_autonomy` constructs `AutonomyConfig` from raw
yaml — an unknown value is caught and the **whole block** falls back to `gated`, discarding caps
and pipeline.
**Decision:** `full` is accepted as an input alias and normalized to `auto_safe` at construction.
Neither removing it from the accepted set (→ silent downgrade to `gated`) nor aliasing it to
`auto_full` (→ silent escalation) is permitted. Because normalization rewrites the value on disk
at the next render, `/harness-maker:make --update` emits a one-line advisory when the pre-update
yaml held `level: full`; B1 produces it and a Success Criteria bullet covers it.
**Consequences:**
- ✅ ADR-013's "a config error, a missing block, or a user's no must never escalate autonomy"
  survives, and so does its mirror: loading must not *downgrade* by accident.
- ✅ Behaviour preserved exactly, because `full` already equals `auto_safe`.
- ⚠️ A user who wrote `full` meaning "the most automatic" must re-select `auto_full`, and their
  committed word is rewritten. The advisory is their only notice, so its absence is a B1 failure.
**Rejected alternatives:** promote `full` → `auto_full` (a re-render would delete gates from a
harness whose owner never asked); drop `full` from the Literal (fallback is `gated` *plus* loss of
the sibling fields — the count:8 class).
**Source:** Interview #2

### ADR-002: `auto_full` clears the plan interview, never the wrapup land gate
**Status:** Accepted (2026-08-08; scope narrowed by ADR-010; mechanism by ADR-009)
**Context:** Three things stop an autopilot chain today: the plan stage's architecture interview
(`plan.md.j2:693`), the review stage's gate (`review.md.j2:666`), and the wrapup merge/land
(`autopilot_caps._HUMAN_GATED_STAGES`). Only the first is a *judgment with a recommended answer*.
The third performs an *irreversible mutation* of the shared branch. The second turned out to be
two different things — see ADR-010.
**Decision:** At `auto_full`, the plan architecture interview is cleared by auto-answering with
the recommended option, and the auto-answer is written into the PLAN's own Interview Transcript as
an auto-answered row **before** the stage's terminal block runs (the PLAN file is written and
verified at `plan.md.j2:660-663`, so "record it in the transcript" needs that named write path or
it degrades to the grep-only control this ADR's ⚠️ rejects). The wrapup merge/land gate is
unchanged at every level. `auto_safe` and `gated` are untouched.
**Consequences:**
- ✅ One human stop per pipeline run removed outright at the top level, plus one conditional stop
  via ADR-010.
- ✅ The gate whose failure mode is "a squash commit is on `main`" keeps a human.
- ⚠️ An auto-answered architecture decision is a real decision made without the user. The
  transcript row is a *record*, not an enforcement — which is why Interview #5 chose ADR-009's
  mechanism over prose, and why B3 asserts a behavioural differential rather than a grep alone.
- ⚠️ Drafts 1–3 of this ADR claimed two auto-answerable judgment gates. That was wrong about the
  review gate; ADR-010 replaces it.
**Rejected alternatives:** land included (rejected by the user, Interview #1); advance-only with
no auto-answer (that is the current `full`, so no new level would be needed).
**Source:** Interview #1; corrected by validator round 3

### ADR-003: `ask` is a harness.yaml-only meta-level; the marker holds operational levels
**Status:** Accepted (2026-08-08, via /hm:plan interview)
**Context:** `ask` means "present the three operational levels at session start". A session's
chosen level must apply for that session without being written back to `harness.yaml`.
`autopilot.effective_level` already prefers the marker's `level` over the yaml value.
**Decision:** `ask` is valid in `harness.yaml` and **invalid as a marker/CLI level**. The
operational set (`gated`, `auto_safe`, `auto_full`) governs every runtime and CLI consumer; the
yaml Literal is that set plus `ask`. Both derive from one constant (ADR-005). `effective_level`
with `yaml_level="ask"` and no marker returns `"ask"` — never a silent `gated`. `ask` +
`autopilot_persistent: true` writes **no** marker and logs no error: the picker owns the session,
by design, and B1 asserts it so the absent case is not a black hole.
**Consequences:**
- ✅ No new persistence mechanism; the marker already carries `level`.
- ✅ A session pick cannot leak into the committed config.
- ⚠️ Two value sets for one field name, enforced by a discovery test, not convention.
- ⚠️ `ask` has render-time consequences the runtime resolver cannot reach: **two** templates
  interpolate `config.autonomy.level` into a `--level` flag (`step_manifest.md.j2:52`,
  `commands/hm/health.md.j2:140`). ADR-007 decides both.
**Rejected alternatives:** write the pick back to `harness.yaml` (a per-session answer is not a
project decision); treat `ask` as a fourth operational level (`boundary` would have to answer
"what does `ask` advance past", which has no answer).
**Source:** Interview #1 follow-through; `autopilot.py:762-781`

### ADR-004: Measurement integrity precedes any workflow change; the session-length lever is A/B-only
**Status:** Accepted (2026-08-08, via /hm:plan interview)
**Context:** The largest measured target is session length (20–54% of spend past the span cap).
The obvious intervention — run `wrapup` in a fresh session — trades inherited carry for re-read
cost, and the re-read cost is unmeasured.
**Decision:** This PLAN ships (a) the meter fix, (b) a ledger-validity adjudication, (c) a
**pre-registered** A/B protocol naming corpus, arms, N, metric, decision rule and analysis command
before any run. No workflow prose changes for session length.
**Consequences:**
- ✅ The decision rule cannot be amended post-hoc without disclosure.
- ⚠️ The biggest saving is deferred by one round.
- ⚠️ "No repeat of the stage-1 shape" is only true if something **fails** when it happens. That is
  B5's assertion, which ADR-008 now requires to be mechanically failing rather than a document
  obligation — validator round 3 caught the earlier disjunction that made it unfailable.
**Rejected alternatives:** implement fresh-session wrapup now (rejected by the user); instrument
fixes with no protocol (the next round re-argues from the same absent data).
**Source:** Interview #3

### ADR-005: One constant for the level value sets, guarded by an AST discovery test
**Status:** Accepted (2026-08-08; **rewritten three times** — after validator rounds 1, 2 and 3)
**Context, recorded in full because the correction is the point.** Draft 1 paired a five-site
hand-list with a test asserting the sites *agree*, which ADR-003 requires to be false. Draft 2
replaced the equality with a partition assertion over three sites — and round 2 showed the
enumeration itself was wrong. Verified in source, the level value set is declared at **ten**
places: `models.py:808` (the Literal), `autopilot.py:101`, `:246`, `:759` (`_VALID_LEVELS`),
`:951` (`--level`), `:962` (a `cast("Literal[...]")`), `hooks/autopilot_autoarm.py:62-68` (an
`if/elif/else: return False` ladder), `autopilot_ledger.py:301` (`_ARMED_LEVELS`),
`autopilot_ledger.py:353` (argparse `choices`), and `cli.py:1493` (`valid_levels`). **The claim
that a partition assertion closed the count:3 hand-list class was false, and false because the
hand-list was incomplete — the failure mode of the class, committed inside the fix for it.**
**Decision:** Three mechanisms.
1. **Normalization** (`full` → `auto_safe`) in exactly one `field_validator(mode="before")` on
   `AutonomyConfig.level`, so every construction path inherits it.
2. **One constant**: `models.OPERATIONAL_LEVELS: tuple[str, ...] = ("gated","auto_safe","auto_full")`.
   Every consumer **derives**: `_VALID_LEVELS = frozenset(OPERATIONAL_LEVELS)`,
   `_ARMED_LEVELS = frozenset(OPERATIONAL_LEVELS) - {"gated"}`, both argparse
   `choices=OPERATIONAL_LEVELS`, `cli.valid_levels = OPERATIONAL_LEVELS`. The `autopilot_autoarm`
   if/elif ladder is **deleted** and replaced by a membership test, so there is no ladder to detect.
3. **The guard is an AST discovery test**, modelled on
   `tests/structural/test_autopilot_marker_api_session_key.py`: walk every module under
   `src/harness_maker/`, and fail on any tuple/set/frozenset/`choices=` collection, or any
   `Literal[...]`, containing **two or more** members of the trigger set
   `set(OPERATIONAL_LEVELS) | {"ask", "full"}`, unless the node is one of **exactly two**
   allowlisted AST nodes in `models.py`: the `OPERATIONAL_LEVELS` assignment and the
   `AutonomyConfig.level` annotation. Round 3 caught the earlier "exactly one entry wide" wording —
   `models.py` will legitimately hold both, so a one-node allowlist fails on its own file. Derived
   single-element expressions (`- {"gated"}`) are below the ≥2 threshold and do not trigger.
   **Phase B1 opens with a discovery pass (`rg '"auto_safe"' src/`) and puts every hit in scope**;
   the test, not the list, is what makes a missed hit fail.
**Consequences:**
- ✅ An eleventh site added later fails a test instead of shipping silently.
- ✅ `auto_full` cannot be dead on the autoarm path, because the ladder that would kill it is gone.
- ⚠️ The `Literal` remains a second spelling (the type checker needs it); the two-node allowlist is
  what keeps that honest.
- ⚠️ An AST test can be defeated by dynamic construction. Accepted: nothing here builds these sets
  dynamically, and doing so would be a reviewable change.
**Rejected alternatives:** a better hand-list (three prior fixes of this class were better
hand-lists, all wrong, and this PLAN made it four); an equality test (contradicts ADR-003); a
partition over three sites (draft 2's defect — blind to seven).
**Source:** Interview #2 follow-through; validator rounds 1–3; codex `3845c1ae`

### ADR-006: Two tracks in one PLAN, one global land order, one declared exception
**Status:** Accepted (2026-08-08; revised after rounds 1–3)
**Context:** Track A and Track B are unrelated in subject but not in files. A3 retires prose from
`templates/stages/plan.md.j2` and B3 edits the architecture gate in the same file; four phases
(A3, B3, B4, B5) touch `tests/structural/surface_baseline.json`.
**Decision:** One PLAN, one **explicit global order** in the Implementation Plan preamble, mirrored
in every affected phase's `merge_hazards` in both directions:
`A1 → A2 → A3 → A4 → B1 → B2 → B3 → B4 → B5`, with `A3` strictly before `B3` and `B5` last. No
`depends_on` crosses the track boundary **except B5**, the closing assertion phase, which by
construction depends on both tracks (`depends_on: [A3, B4]`). The tracks are independently
*reasoned about*, not independently *mergeable*.
**Consequences:**
- ✅ Track B is not sent back through research/spec.
- ✅ A scheduler reading any single phase's metadata sees the constraint.
- ⚠️ Serial ordering on shared files removes most of the parallelism a two-track PLAN would buy.
- ⚠️ The "clean separation" claim of draft 1 is retracted; the B5 exception is stated here so a
  future edit does not "fix" B5's metadata and lose the last-landing constraint.
**Rejected alternatives:** two PLANs (rejected by the user); claiming clean separation (refuted by
file ownership); leaving the order implicit (round-2 warning).
**Source:** Interview #4; validator rounds 1–3

### ADR-007: No rendered `--level` carries a meta-level; `/hm:health` skips its smoke under `ask`
**Status:** Accepted (2026-08-08; half (a) superseded by ADR-009; completed after round 3)
**Context:** Verified in source: `step_manifest.md.j2:28` gates the picker on the **render-time**
`config.autonomy.level` and `:52` interpolates it into
`hm autopilot on --level {{ config.autonomy.level }}`; `commands/hm/health.md.j2:131,140` does the
same into `hm autopilot_ledger smoke --level {{ ... }}`. So `level: ask` renders `--level ask` in
two places — the value ADR-003 makes every CLI reject — and `level: auto_full` renders a value
`autopilot_ledger`'s argparse rejects until B1 derives its choices. Round 3 then noted that
"interpolate a resolved operational level" has **no referent at render time** under `ask`, because
the pick happens at runtime, so the decision had to be made here rather than left to the executor.
**Decision:**
- `step_manifest.md.j2:52` takes its level from **the picker's chosen value** (the arm command is
  emitted after the pick), never from `config.autonomy.level`.
- `commands/hm/health.md.j2`: under `level: ask` the autopilot smoke section **is not rendered**;
  in its place one line states that the level is unresolved until the session picker runs.
  Hard-coding `--level auto_safe` there is explicitly forbidden — it would assert a level the
  project never chose, which is the silent-degradation source this ADR exists to remove.
- A render-grep over **every file** under `.claude/` and `.codex/`, rendered **from an `ask`
  fixture**, asserts `--level ask` appears nowhere. The fixture is load-bearing: from the default
  `auto_safe` templates the grep passes vacuously.
**Consequences:**
- ✅ `ask` becomes armable, and `/hm:health` stops being able to report a green smoke for a level
  the harness does not run.
- ⚠️ Under `ask`, `/hm:health` loses its autopilot positive-check until a pick happens. Accepted:
  a check that asserts the wrong level is worse than an absent one, and the line says so.
**Rejected alternatives:** a `boundary` field whose only content is the level it was read from
(round 2 — satisfiable by construction); leaving `/hm:health`'s `ask` behaviour to the executor
(round 3 — "the behaviour is decided" passes on any decision, including the harmful one).
**Source:** validator rounds 1–3; codex `0c3ca089`, `d4e8f96f`

### ADR-008: A2 emits a verdict token; B5's net-surface assertion must be able to fail
**Status:** Accepted (2026-08-08; revised after rounds 2 and 3)
**Context:** Draft 1 gated A3 on "A2 concluded the ledger is trustworthy", a predicate over a value
A2 never produced. Round 2 showed the absolute baseline target sat in A3, which must land *before*
B3/B4 add anything, so it never bound. Round 3 showed the replacement in B5 was written as a
disjunction — "below the literal **or** the shortfall is recorded red" — whose second branch is
always achievable by writing a row, making the criterion unfailable and relocating the laundering
rather than removing it.
**Decision:**
1. A2 writes an explicit token `ledger-trustworthy: yes|no` into its `wiki.md` entry; A3's entry
   condition reads that token and nothing else.
2. On `no`, A3 does not silently skip: it files a BASELINE-DELTA row attributing the retained
   +7,113 chars as an accepted debt and naming the follow-up that owns it.
3. **A1 records the literal pre-A1 `aggregate_chars.claude` integer** into
   `work-docs/BASELINE-DELTA-workflow-time-token-savings.md`. Every later comparison reads that
   literal, not a reconstructed commit.
4. **B5 owns a test that FAILS on net growth.** `tests/structural/` gains an assertion that
   `aggregate_chars.claude <= <the A1 literal>`. If the PLAN legitimately ends net-positive, the
   only permitted escape is an **explicit `xfail` with a documented waiver** referencing the
   BASELINE-DELTA row — so the failure stays visible in CI instead of being absorbed by a
   document obligation.
**Consequences:**
- ✅ Neither A3 branch closes with the debt unrecorded, and the anti-laundering property binds
  where all additions are in, as a red test rather than a paragraph.
- ✅ The comparison target is a written integer, not `git show <A1^>:…` in a squash-landing repo.
- ⚠️ B5 may land red or `xfail`. That is intended: this repo's precedent is to leave such a trip
  visible rather than re-baseline (count:2).
**Rejected alternatives:** directional comparison against the current baseline (launderable); the
absolute assertion in A3 (never binds); a disjunctive criterion (round 3 — unfailable).
**Source:** validator rounds 2 and 3; codex `79d04464`

### ADR-009: Judgment gates are source-stage-keyed, and their pending state is an explicit fail-closed input to `boundary`
**Status:** Accepted (2026-08-08, via Interview #5; **substantially revised after round 3**)
**Context:** `stage_end_summary.md.j2:33-40` evaluates the stage's mandatory gate in **Step 1** and
instructs "if pending/unresolved → **STOP** … Do NOT run the boundary check", so `boundary` is
reached only after the gate has cleared and holds no judgment-gate state. Interview #5 chose to fix
the layer. Round 3 then found three defects in the first attempt, all verified:
(1) with no gate-state input, `boundary` must answer a judgment-gated transition
**unconditionally**, so pinning it to `proceed: false` at `auto_safe` would make `auto_safe` halt
at plan→execute and review→verify **even on clean stages** — a regression enshrined as the desired
result, under a criterion labelled "the default is unchanged";
(2) keying membership on the `(source, next)` pair breaks on any user-customised
`autonomy.pipeline` (`models.py:809-819`, `cli --pipeline`), because the gates belong to the
*source* stage — the count:8 shape;
(3) `stage_end_summary.md.j2` is **one shared include** under StrictUndefined, parameterised only
by `summary_stage` and the `summary_autopilot_gate` prose string, so there is no existing branch to
change and a new caller-set variable would break the five other stage templates that include it
and are in no phase's scope.
**Decision:**
1. Membership is keyed on the **source stage**: `_JUDGMENT_GATED_STAGES = {"plan", "review"}`.
   `_HUMAN_GATED_STAGES` stays next-stage-keyed as it is today.
2. **The gate's pending state is an explicit input, fail-closed.** Step 1 keeps *evaluating* the
   stage's gate and passes the result to Step 2 as `--judgment-gate pending|clear`; **absent ⇒
   `pending`**. `boundary` reads `marker.level` and that flag:
   - `clear`, any level → `proceed: true` (**today's behaviour, preserved and asserted**).
   - `pending`, `gated` or `auto_safe` → `proceed: false, halt_kind: "judgment_gate"`.
   - `pending`, `auto_full` → `proceed: true` with the auto-answer directive, subject to ADR-010.
3. `judgment_gate` **appends a `gate_blocked` ledger event** with the stage, and **preserves the
   marker** — the halt is not terminal, unlike `merge_gate` which clears it (`:329-331`). Without
   this, `autopilot_ledger.smoke_check` loses the rows it consumes and `/hm:health` can report
   `degraded: true` for a harness that is stopping correctly.
4. The Step 1/Step 2 discriminator is **derived inside `stage_end_summary.md.j2` from
   `summary_stage`** (membership in the judgment set), not from a new caller-set variable — so the
   five stage templates outside B3's scope keep rendering under StrictUndefined.
5. The differential test runs at `--current plan` and `--current review` — the stages that own a
   judgment gate — over the full (level × gate-state) matrix, plus one **non-default pipeline**
   (e.g. `[plan, review, verify, wrapup]`) asserting the gate still fires at `auto_safe`.
**Consequences:**
- ✅ `auto_full` is behaviourally distinguishable from `auto_safe` by a test that fails when it is
  not, without changing what `gated`/`auto_safe` do on a clean stage.
- ✅ Fail-closed on an absent flag means a caller that forgets to pass it halts rather than
  advances.
- ⚠️ **This still changes the advance ordering for every stage.** It is the PLAN's largest blast
  radius, and B3 carries it.
- ⚠️ A marker written by an older harness (no level, or legacy `full`) must resolve through the
  same normalization, or the absent case reappears at the marker layer.
- ⚠️ The gate-first invariant existed to stop a stage advancing past an unresolved human decision.
  Moving judgment gates below the boundary is safe only because the flag is fail-closed **and**
  `pending` still stops at `gated`/`auto_safe`; B3 asserts both, at both levels.
**Rejected alternatives:** prose-only + render-grep (Interview #5 option B); an unconditional
answer with no gate-state input (round-3 critical 1 — inverts the default);
`(source, next)`-keyed membership (round-3 critical 3 — breaks on custom pipelines); a caller-set
Jinja variable (round-3 warning — breaks five out-of-scope templates).
**Source:** Interview #5; validator round 3 criticals 1–3 and warnings 1–2

### ADR-010: The review gate splits — grade is never clearable; `human_review_needed` is clearable at `auto_full` only
**Status:** Accepted (2026-08-08, via /hm:plan Interview #6)
**Context:** Drafts 1–3 treated the review stage's gate as a judgment gate with a recommended
answer. Verified in source, its predicate is *two* different things:
`Status == CHANGES_REQUESTED (grade < grade_threshold)` **or** `human_review_needed is true`
(`review.md.j2:666`, with the receipt semantics at `:640` — an APPROVED review with
`human_review_needed=true` records `pass` because the grade cleared, but the flag surfaces
unverified `manual-only` / `weak-consensus` P0/P1 findings). The first is a failed quality
threshold — there is nothing to auto-answer, and clearing it means advancing past a failed review,
which `models.py:790-796` forbids and which no interview had asked about. Interview #6 put the
question to the user.
**Decision:** The gate splits.
- `grade < grade_threshold` (`CHANGES_REQUESTED`) is **mandatory at every level**, including
  `auto_full`, and keeps Step 1's gate-first treatment. It is a Non-Goal of this PLAN, not a
  deferral.
- `human_review_needed == true` on an **APPROVED** review is a judgment-gated condition:
  `gated`/`auto_safe` stop as today; `auto_full` proceeds and records which flagged findings were
  passed over, by `id`, in the REVIEW document.
**Consequences:**
- ✅ `models.py:790-796`'s recorded invariant ("a `full` session must never auto-push or skip a
  CHANGES_REQUESTED review") survives intact, so REVIEW P6's correction is not reversed.
- ✅ The remaining clearance is bounded and auditable: an APPROVED grade plus a named list of
  passed-over finding ids.
- ⚠️ **Accepted risk, explicitly.** `human_review_needed` is the *only* provenance exception in
  this harness — it is how unverified `manual-only` P0/P1 findings reach a human at all
  (CLAUDE.md's `unresolved` note). At `auto_full` that path is consumed automatically. The
  compensating control is the recorded id list, and B3 asserts it.
- ⚠️ Two predicates in one prose gate means `review.md.j2`'s `summary_autopilot_gate` string must be
  split so Step 1 can treat them differently — a template change with no existing seam.
**Rejected alternatives:** hold the whole review gate at every level (Interview #6 option A —
simpler and lower-risk, rejected by the user); clear both predicates (option C — reverses a
recorded invariant); defer `auto_full` entirely (option D).
**Source:** Interview #6; validator round 3 critical 2

### ADR-011: Development instrumentation ships behind an opt-in `instrumentation` axis
**Status:** Accepted (2026-08-08, via /hm:plan Interview #7)
**Context:** harness-maker is a **public** plugin published to PyPI, and it renders
harness-maker's *own* development instrumentation into every consuming project's stage prompts.
Measured: the `stage_agent_ledger` emit block is ≈805 chars of `.claude/commands/hm/plan.md`
(51,987 total) and ≈739 chars of `execute.md` (35,681 total), with a reviewer-payload block in
`review.md`. That prose exists to answer *our* question — the module's own docstring says so:
"stage 2's decision on both … depends entirely on data that did not exist". A third-party user
pays those tokens on every `/hm:plan`, `/hm:execute` and `/hm:review`, and gets a ledger on disk
whose only consumer is us. That is a different category from `/hm:health` (their harness's
health) or `/hm:metrics` (their delivery metrics), which are theirs.
**The counter-evidence is strong and must be recorded, because it nearly went the other way.**
The cross-project denominator is exactly what made this PLAN's verdict correct: harness-maker's
own 6 rows gave **0/3 → "delete the second validator pass"**, while pooling strange_chess (37)
and edgelog (4) gave **2/9 = 22.2% → "keep"**, with one run flipping MAJOR_REVISION → APPROVED
on a third pass. Had the instrumentation not shipped into consuming projects, a load-bearing
step would have been deleted on single-repo evidence.
**Decision:** The axis is not "development vs feature" in the abstract — it is **whose project,
and who consented**. A new `harness.yaml` key gates category-2 instrumentation
(`stage_agent_ledger` emits, reviewer-payload persistence): when it is off, the prose is **not
rendered at all**, not merely inert. The maintainer's own fleet turns it on and keeps the
cross-project denominator; a third-party install defaults to off and pays nothing. There is no
privacy dimension to trade — CLAUDE.md already forbids external transmission and these are local
files; the cost being removed is prompt surface and disk.
**Consequences:**
- ✅ A third-party harness stops carrying ≈1.5–3k chars of prose whose consumer is this repo.
- ✅ The maintainer's four-project fleet keeps producing the pooled denominator that this PLAN
  demonstrated is decisive.
- ⚠️ **The default determines the future denominator.** Defaulting off means the population
  shrinks to whoever opts in — which, on this PLAN's own evidence, is the condition under which
  a wrong deletion becomes likely. The interview question that sets it must say so plainly
  rather than presenting it as a cost-free privacy nicety.
- ⚠️ Two render paths for the same stage templates, which is new conditional surface in the
  place this PLAN is otherwise trying to shrink.
**Rejected alternatives:** split by `preset` (preset is a rigour axis, not a consent axis — a
Production third-party install would still be instrumented); keep shipping to everyone (the
status quo the user challenged); strip it entirely (would have produced the wrong verdict here).
**Source:** Interview #7

### ADR-012: `ask` is the DEFAULT autonomy level for a freshly rendered harness
**Status:** Accepted (2026-08-09, user instruction mid-execute — supersedes the `auto_safe`
class default that PLAN-harness-diet ADR-010 introduced)
**Context:** B4 was scoped to *offer* `ask` as one of four values, with `auto_safe` remaining the
default a fresh harness commits. The user's instruction was direct: the default must be `ask`.
The argument for it is that the right level is not a property of the project — it is a property
of the piece of work in front of you. A committed `auto_safe` answers that question once, months
in advance, for every session; `ask` moves the answer to the only moment it can be given with the
work in view. It also makes the picker — which already exists and is already the documented way
autopilot is armed — the normal path rather than a fallback.
**Decision:** `AutonomyConfig.level` defaults to `ask`; both `harness-yaml` templates fall back to
`ask`; `_ask_autonomy` offers all four with `ask` as the offered default; `commands/make.md`'s
disclosure row states it.
**What does NOT change, and this is the load-bearing part:**
- `interview._parse_autonomy` still pins an **absent or malformed** block to `gated`
  (ADR-013 of PLAN-autopilot-config-surface). A default that asks is still an autonomy change, so
  it reaches an existing project through `/harness-maker:make --update`, never through a load.
- An **explicit decline** in the interview still pins `gated` / `autopilot_persistent: false`.
  Inheriting the class default there would now put the question back to a user who just answered
  it — a sharper version of the same bug ADR-013 wrote that branch for.
**Consequences:**
- ✅ The level is chosen with the work visible, and `auto_full` becomes reachable without editing
  yaml.
- ⚠️ Every session of a fresh harness now sees a picker question it did not see before. That is
  the intended trade, but it is a per-session interruption where there used to be none, and
  `autopilot_persistent` cannot pre-answer it (ADR-003: the picker owns an `ask` session).
- ⚠️ `/hm:health`'s autopilot smoke has no concrete `--level` under `ask` and is skipped with a
  stated one-line note (ADR-007). A project on `ask` therefore loses that silent-degradation
  probe — accepted, because interpolating a meta-level would make the probe fail on an argument
  error and report a healthy harness as degraded.
**Source:** User instruction, 2026-08-09

## 🏗️ Technical Design

### Current state

- `economics_source.encode_project_dir` (`:104`) is `re.sub(r"[/.]", "-", str(path))`. Claude Code
  additionally maps `_` → `-`; verified against five underscore-path projects, all hyphen-encoded
  with no underscore-encoded sibling. `context_composition` imports the function;
  `run_classify.py:338` reaches the encoding **transitively via `load_turns`**.
- `discover_transcript_dirs` (`:114`) prefix-matches the encoded name plus `<name>--worktrees-*`
  siblings and skips symlinked children. Encoding collisions are handled downstream by the per-turn
  `is_own_cwd` check (`:145`, applied at `:488`; `context_composition.py:131` calls the same
  helper), which the code comment names as the real boundary.
- `stage_agent_ledger` holds 47 rows across three projects. strange_chess: 39 subagent dispatches
  recorded, **0** sidechain turns found by `load_turns` across 28 files over an all-time window
  (4,105 for harness-maker), one transcript directory only. spoton: **zero** ledger rows despite 12
  stage-spans rows — the mirror anomaly, and the only Production / spec-driven project.
- `AutonomyConfig.level` is `Literal["gated","auto_safe","full"]`; the value set is re-declared at
  nine further places (ADR-005). `hooks/autopilot_autoarm.py:62-68` narrows it with an
  `if/elif/else: return False` ladder, so an unrecognised level silently declines to arm.
  `autopilot_ledger.py:301`/`:353` and `cli.py:1493` each restate it.
- `autopilot.effective_level` returns the marker's level when a marker exists, else the yaml level,
  else `gated` on an unknown value.
- `autopilot_caps.boundary` (`:228-344`) reads no level and has no gate-state input.
  `_HUMAN_GATED_STAGES` is `frozenset({"wrapup"})`; the check at `:323` is on the **next** stage and
  `merge_gate` clears the marker (`:329-331`); the clean path returns `proceed: true` (`:342-347`).
- `stage_end_summary.md.j2` is **one shared include** under StrictUndefined (`:10-21` requires
  callers to set bare vars), parameterised by `summary_stage` and the prose string
  `summary_autopilot_gate`; it evaluates the gate before the boundary (`:33-40`). Seven stage
  templates include it. The gate predicates are set at `plan.md.j2:693` and `review.md.j2:666`.
- `/hm:health` renders `hm autopilot_ledger smoke --level {{ config.autonomy.level }}`
  (`health.md.j2:140`, guarded at `:131` on `!= "gated"`).
- `autonomy.pipeline` is a user-settable `list[AtomicStage]` (`models.py:809-819`, `cli --pipeline`).

### Affected components

| Component | Track | Phase | Change |
|---|---|---|---|
| `economics_source.encode_project_dir` | A | A1 | widen the character class |
| `economics_source.load_turns` / `discover_transcript_dirs` | A | A2 | only if A2 finds a loader defect |
| `stage_agent_ledger` | A | A2 | new `reconcile` subcommand (diagnostic-only) |
| `templates/stages/plan.md.j2` | A + B | A3, B3 | A3 retires ledger prose; B3 adds the level-conditional gate branch — **shared, A3 first** |
| `templates/stages/execute.md.j2` | A | A3 | retire the conditional ledger prose |
| `templates/stages/review.md.j2` | B | B3 | **split** the gate string into grade vs `human_review_needed` (ADR-010) |
| `models.AutonomyConfig` + `OPERATIONAL_LEVELS` | B | B1 | Literal, constant, one `field_validator` |
| `autopilot` (incl. `:962` cast) | B | B1, B2 | derive `_VALID_LEVELS`, `--level`, `ask` resolution |
| `hooks/autopilot_autoarm.py` | B | B1 | **delete the ladder**; derive from the constant |
| `autopilot_ledger.py` | B | B1 | derive `_ARMED_LEVELS` and argparse `choices` |
| `cli.py` | B | B1 | derive `valid_levels`; emit the `full` → `auto_safe` advisory |
| `autopilot_caps.py` | B | B3 | `_JUDGMENT_GATED_STAGES`; `--judgment-gate` input; `judgment_gate` halt + ledger row |
| `templates/agents/_partials/stage_end_summary.md.j2` | B | B3 | discriminator derived from `summary_stage`; pass the gate flag to Step 2 |
| `templates/agents/_partials/step_manifest.md.j2` | B | B3, B4 | gate prose + picker — **shared, B3 first** |
| `templates/commands/hm/health.md.j2` | B | B4 | skip the smoke under `ask` (ADR-007) |
| `interview._ask_autonomy` / `_parse_autonomy` | B | B1, B4 | 4-value prompt, sibling preservation, round-trip |
| `tests/structural/surface_baseline.json` | A + B | A3, B3, B4, B5 | **shared, serial; B5 asserts the net** |

### Data flow — a judgment-gated stage after ADR-009 / ADR-010

```
stage plan (or review) finishes
   │
   ▼
Step 1: evaluate THIS stage's gate prose
   ├─ land gate (wrapup)          ──▶ gate-first, STOP        (unchanged)
   ├─ review grade < threshold    ──▶ gate-first, STOP        (unchanged at EVERY level, ADR-010)
   └─ judgment gate (plan interview pending | APPROVED + human_review_needed)
            │  pass --judgment-gate pending|clear   (absent ⇒ pending, fail-closed)
            ▼
      Step 2: boundary --current plan|review   (reads marker.level + the flag)
            ├─ clear,   any level      ──▶ proceed:true                        (today's behaviour)
            ├─ pending, gated|auto_safe ──▶ proceed:false, halt_kind:judgment_gate
            │                               + gate_blocked row, marker PRESERVED
            └─ pending, auto_full       ──▶ proceed:true + auto-answer directive
                                            (plan: recommended option written into the PLAN's
                                             Interview Transcript as auto-answered;
                                             review: passed-over finding ids recorded in REVIEW)
```

### Data flow — `ask` resolution

```
harness.yaml level: ask
   │
   ├─ render time: the picker block renders; every --level flag carries the PICKED level, and
   │               /hm:health's smoke section is NOT rendered (one line explains why)   [B4]
   │
   └─ run time:   effective_level(yaml_level="ask", no marker) ──▶ "ask"                 [B2]
                  hm autopilot status ──▶ reason:"ask-pending", active:false             [B2]
                  ask + autopilot_persistent:true ──▶ NO marker, no error (picker owns)  [B1]
                            │
                            ▼
                  user picks gated | auto_safe | auto_full  (picker branches on ask-pending) [B4]
                            │
                            ▼
                  marker written with the picked operational level; harness.yaml untouched
```

### API changes

- `models.OPERATIONAL_LEVELS: tuple[str, ...] = ("gated","auto_safe","auto_full")` (new); with the
  `AutonomyConfig.level` annotation, one of the two allowlisted level declarations (ADR-005).
- `AutonomyConfig.level`: `Literal["gated","auto_safe","auto_full","ask"]`, `"full"` accepted on
  input and normalized to `"auto_safe"`.
- `autopilot._VALID_LEVELS`, `autopilot_ledger._ARMED_LEVELS`, both argparse `choices`,
  `cli.valid_levels`: all **derived** from `OPERATIONAL_LEVELS`.
- `hm autopilot status` JSON: unchanged shape; `reason` gains `"ask-pending"`.
- `autopilot_caps`: `_JUDGMENT_GATED_STAGES = {"plan","review"}`; `boundary` gains
  `--judgment-gate pending|clear` (absent ⇒ `pending`) and `halt_kind: "judgment_gate"`, which
  appends a `gate_blocked` row and **preserves** the marker.
- `hm stage_agent_ledger reconcile --root <path>` (new): per-project ledger-dispatch count vs
  transcript sidechain-turn-group count. **Diagnostic only** — its non-zero exit must not be wired
  into any gate, because an A2 branch-(ii) disagreement is expected forever.

## 📝 Implementation Plan

> **Global land order (ADR-006):** `A1 → A2 → A3 → A4 → B1 → B2 → B3 → B4 → B5`. Hard constraints:
> **A3 strictly before B3** (shared `templates/stages/plan.md.j2`); **B3 before B4** (shared
> `step_manifest.md.j2`); **B5 last** (it asserts the net surface across every other phase).
>
> **Every code-touching phase's exit criterion additionally includes `ruff check`,
> `ruff format --check` and `mypy --strict` on the changed files** — seconds, not the 6-minute
> suite. Load-bearing for Track B: widening the `Literal` makes `autopilot.py:962`'s `cast` and
> `hooks/autopilot_autoarm.py:62`'s annotation type-incoherent, and a phase-local subset would not
> catch it. The full suite is B5's.

### Phase A1 — Widen `encode_project_dir`; record the pre-PLAN baseline literal
- **depends_on:** `[]`
- **parallel_group:** `serial-a1`
- **merge_hazards:** none
- **Scope in:** `src/harness_maker/economics_source.py`, `tests/unit/test_economics_source.py`,
  `work-docs/BASELINE-DELTA-workflow-time-token-savings.md` (new — records the literal)
- **Scope out:** `context_composition.py`, `run_classify.py` (reach the encoding transitively),
  `surface_baseline.json`
- **Exit criterion:** `uv run pytest tests/unit/test_economics_source.py` passes three new cases:
  (1) `encode_project_dir(Path("/a/b/c_d")) == "-a-b-c-d"`; (2) a `discover_transcript_dirs` case
  over a `tmp_path` transcript root containing an **underscore-bearing** project path — the
  existing suite passes only absolute `tmp_path` values with no `_`, which is why this was never
  caught; (3) a collision pin: `/x/a_b` and `/x/a-b` encode identically, and a turn whose `cwd` is
  under `/x/a-b` must be **excluded** from `load_turns(Path("/x/a_b"))`. Plus: the BASELINE-DELTA
  file records the current `aggregate_chars.claude` **integer** verbatim and is committed here.
  Plus `ruff` + `mypy --strict`.
- **Risk:** low
- **Rollback point:** pre-A1 HEAD. No dependents at rollback time.
- **Status: DONE** (2026-08-08). `re.sub(r"[/._]", ...)`; three cases added, all RED first for
  the right reason (`'-x-a_b' != '-x-a-b'`), then GREEN. Phase A.5 test-reviewer: **PASS**, no
  blocking issues; its one suggestion was applied — the collision case now asserts
  `diagnostics.dirs_scanned == 1` and `skipped_by_reason["foreign_cwd"] == 1` instead of
  deducing the mechanism from an empty list, so the pin cannot go green by discovery finding
  nothing. `ruff` + `mypy --strict` + `tests/unit` + `tests/render/test_render_metrics_unattributed.py`
  all pass. Pre-PLAN literal `aggregate_chars.claude = 366439` recorded in the BASELINE-DELTA.
- **Phase D.5 — newly-reachable window (this phase is a repair, so it applies):**
  1. **Window opened.** Before the fix, no project path containing `_` matched any transcript
     directory, so `load_turns`, `is_own_cwd`, pricing, composition and `run_classify boundaries`
     never executed against those corpora at all. The fix makes every underscore-path project's
     entire corpus newly reachable by every economics consumer. A second, narrower window opens
     with it: two distinct project paths (`/x/a_b`, `/x/a-b`) can now encode to the **same**
     directory, so `is_own_cwd` becomes load-bearing on a path where it previously never fired.
  2. **Tests entering it, in this same change.**
     `tests/unit/test_economics_source.py::test_discovery_finds_an_underscore_bearing_project_path`
     enters the first window;
     `::test_cwd_filter_is_the_real_boundary_when_two_paths_encode_alike` enters the collision
     window and names its mechanism via the `foreign_cwd` counter. Neither merely re-asserts the
     reported symptom (`$0` turns) — that would have left both windows untested.
  3. **Absent case.** The repair activates on a path *shape*, not an optional field, so the
     absent case is "underscore-path project with no transcript directory": discovery returns
     `[]` exactly as before, unchanged and already covered by
     `test_discovery_returns_empty_when_no_store_exists`. No migration is owed — the encoder is
     computed per call, nothing persisted was encoded with the old rule.

### Phase A2 — Adjudicate the stage-agent ledger against the transcript
- **depends_on:** `[A1]` — strange_chess's transcripts are undiscoverable until A1 lands
- **parallel_group:** `serial-a2`
- **merge_hazards:** none
- **Scope in:** `src/harness_maker/stage_agent_ledger.py` (new `reconcile`),
  `src/harness_maker/economics_source.py` (**only** if reconcile identifies a loader defect —
  without this in scope the executor is forced into the wiki-entry escape),
  `src/harness_maker/command_registry.py`, `src/harness_maker/hm.py`,
  `tests/unit/test_stage_agent_ledger.py`, `.claude/memory/wiki.md`
- **Scope out:** deleting any workflow step; amending the pre-registered aggregation rules; wiring
  `reconcile` into any gate
- **Exit criterion:** `hm stage_agent_ledger reconcile --root <p>` runs for **all four** projects
  and prints `ledger_dispatches` vs `sidechain_turn_groups` per project. **The live recovery is
  observed, not inferred:** `economics stages --root /home/noel/strange_chess` reports non-zero
  turns, recorded in the phase's notes (A1's cases are synthetic `tmp_path` paths and cannot
  witness the $1,637). For **every** disagreeing project — strange_chess (39 vs 0) **and** spoton
  (0 vs a non-zero sidechain population) — record one of:
  (i) a loader/discovery defect, fixed here, after which the counts agree;
  (ii) a **positive mechanism** ("dispatches went through path X, which emits no sidechain turn";
  "the emit is gated on config Y, absent in this preset") — an assertion of absence is not a
  mechanism;
  (iii) unresolved → the phase **fails**.
  The `wiki.md` entry ends with `ledger-trustworthy: yes|no`, plus, when `no`, which pre-registered
  rate is affected and in which direction. Branch (ii) records the expected disagreement so a later
  reader does not read `reconcile`'s permanent non-zero exit as a regression. Plus `ruff` +
  `mypy --strict`.
- **Risk:** medium — a `no` verdict withdraws the 22.2% / 37.5% figures
- **Rollback point:** post-A1 HEAD.
- **Status: DONE** (2026-08-08). **Verdict `ledger-trustworthy: yes`**, recorded in
  `.claude/memory/wiki.md` with its caveat. Both anomalies resolved with positive mechanisms:
  - **strange_chess's "39 vs 0" was never real** — the `0` came from a hand-built hardlinked
    transcript directory made to work around the A1 encoder bug, not the real corpus. Real
    figures: 37 ledger dispatches (sentinels excluded) against 1704 subagent turns. RESEARCH
    Open Question 2 retracted in place.
  - **spoton's 0 is real, and the mechanism is scheduling, not a black hole** — the emit IS
    rendered (`grep -c` = 1 in its `plan.md` and `execute.md`, 0.50.1); spoton re-rendered on
    2026-08-08 19:27 (`261843e`) while its last `/hm:plan` / `/hm:execute` ran 2026-08-01/02, a
    week before the emit existed there. The `absent-case = feature black hole` hypothesis is
    **refuted** for this instance.
  - **Caveat that qualifies the verdict:** every ledger row comes from a **Side-preset**
    project, so 22.2% / 37.5% are Side-only and must not be described as cross-preset.
  Phase A.5 test-reviewer: **FAIL then PASS** (2 attempts, both on the ledger). The blocking
  issue was correct and was the same error class as the retraction above — the reconciler's
  denominator was hand-passed, so Phase C could have chosen any grouping key and every test
  would have stayed green. Fixed by adding `sidechain_turn_groups` with three tests that
  discriminate the candidate keys. `ruff` + `mypy --strict` + `tests/unit` + `tests/structural`
  pass; `reconcile` run live on all four projects.
- **Phase D.5 — newly-reachable window (A2 repairs a measurement defect, so it applies):**
  1. **Window opened.** `reconcile` makes a comparison reachable that previously had no
     executable form at all — the ledger count and the transcript count had never been set
     against each other by code. The newly-reachable inputs are therefore *every* project's
     ledger/transcript pair, including the two shapes that are not "agreement": a zero ledger
     with a live corpus, and a ledger larger than the corpus.
  2. **Tests entering it, in this same change.**
     `test_reconcile_flags_subagents_that_ran_while_the_ledger_recorded_nothing` (spoton's shape)
     and `test_reconcile_flags_recording_more_dispatches_than_were_observed` enter the two
     disagreement windows; `test_turn_groups_counts_contiguous_sidechain_runs_not_turns` enters
     the derivation window that the A.5 gate showed was otherwise untested.
  3. **Absent case.** The ledger file may not exist at all (a project that never ran a gated
     stage). `reconcile` treats a missing file as zero rows, which combined with a zero corpus
     yields `agrees` — covered by `test_reconcile_agrees_on_an_empty_corpus`. A missing file
     with a live corpus correctly reports spoton's shape.
  4. **Known blindness, recorded rather than fixed.** `ledger <= groups` cannot see *partial*
     loss: 3 recorded of 40 real reads as agreement, and no inequality over two scalars can
     distinguish that from "3 gated dispatches plus 37 other subagents". Making it visible needs
     a denominator restricted to the three recorded agent names, converting `<=` into `==`. Not
     done here; named in the docstring and the wiki entry so `ledger-trustworthy: yes` is not
     read as more than it is.

### Phase A3 — Retire the conditional instrumentation prose
- **depends_on:** `[A2]`
- **parallel_group:** `serial-a3`
- **merge_hazards:** `templates/stages/plan.md.j2` — shared with **B3, across the track boundary**;
  **A3 lands first**. `tests/structural/surface_baseline.json` — shared with B3, B4, B5; **A3
  first, B5 last**.
- **Scope in:** `src/harness_maker/templates/stages/plan.md.j2`,
  `src/harness_maker/templates/stages/execute.md.j2`,
  `work-docs/BASELINE-DELTA-workflow-time-token-savings.md` (append this phase's row),
  `tests/structural/surface_baseline.json`
- **Scope out:** removing the ledger **emit invocations** (the denominator must survive); Track B;
  the net-surface assertion (B5's)
- **Branch on A2's token:** `yes` → retire the prose whose question is answered and record the
  keep-verdict with its denominator. `no` → the prose retirement still happens (instrumentation
  that produced untrustworthy data is not worth its surface), and the row records the withdrawal of
  both rates plus the follow-up that owns re-instrumenting.
- **Exit criterion:** all four hold. (1) `aggregate_chars.claude` decreases **relative to A3's own
  pre-state** — a directional check on this phase's removal; the net assertion is B5's. (2)
  `uv run pytest tests/structural/test_baseline_delta_attribution.py` passes with a row attributing
  the change to this phase. (3) A render-grep asserts the `stage_agent_ledger emit` invocation
  **still appears** in both rendered stage surfaces — without it, deleting the emits alongside the
  prose satisfies (1) and (2) more easily and makes both keep-verdicts permanently unfalsifiable.
  (4) The row quotes A2's token verbatim.
- **Risk:** medium
- **Rollback point:** post-A2 HEAD.
- **Status: DONE** (2026-08-08), on A2's `ledger-trustworthy: yes` branch. Retired the two
  rationale paragraphs in `templates/stages/{plan,execute}.md.j2` — the ones arguing *why* the
  ledger exists ("zero ledger rows, so … has no data behind it"), now that both questions have
  answers. Every operational instruction stayed. **−351 chars on each of `aggregate_chars.claude`
  and `.codex`**, recorded with the keep-verdict in the BASELINE-DELTA. Criterion (3) verified:
  `stage_agent_ledger emit` still appears twice in each template and once in each rendered
  command — deleting the emits alongside the prose would have satisfied "surface decreased" more
  easily and made both verdicts permanently unfalsifiable. The frozen baseline is deliberately
  **not** re-frozen (the ratchet is `now <= was`, so a shrink owes nothing, and re-freezing would
  destroy the pre-PLAN anchor B5 needs). `tests/structural` + `tests/render` pass.
- **Phase D.5:** not applicable — A3 deletes prose, it repairs no defect. Stated rather than
  skipped silently.
- **⚠️ Phase D was run incomplete the first time, and the gap is recorded because it is the
  interesting part.** After the template edit I ran `tests/structural` + `tests/render` and
  called the phase green. Both passed. The full suite then failed with **8 snapshot failures**
  in `tests/unit/test_synthesize_snapshot.py` — a suite I *had* run at A2 time, before the
  template changed, and did not re-run after. The stage template says to select Phase D's tests
  with `hm test_dep_map --changed-file …`; I selected them by hand and chose the two directories
  whose names sounded template-shaped. `tests/snapshot/regenerate.py` fixed it: 32 lines across
  8 files, all four `body_sha256` entries for `plan.md` / `execute.md` per variant, inspected to
  confirm nothing unrelated was swept into the re-freeze.
  **Two compounding traps, both already written down in this repo:** (1) hand-selecting Phase D's
  scope defeats the tool that exists to select it; (2) the background run's completion
  notification reported **exit code 0** while the `rc=$?` written into the output file said
  **1** — `project_background_exit_code_unreliable`, firing exactly as recorded. Trusting the
  notification would have carried a red suite into wrapup.

### Phase A4 — Pre-register the session-length A/B
- **depends_on:** `[A1]`
- **parallel_group:** `serial-a4`
- **merge_hazards:** none
- **Scope in:** `work-docs/EXPERIMENT-session-length-ab.md` (new)
- **Scope out:** every code and template file
- **Exit criterion:** the document names, before any run: corpus; arm definitions
  (inherited-session vs fresh-session wrapup); N per arm; primary metric (`total_usd` per completed
  wrapup) and secondary (`mean_context_tokens`); the decision rule with its threshold; the exact
  analysis command; and how the fresh-session arm's re-read cost is attributed. Two prohibitions
  must appear and be checkable by reading: (a) the protocol must **not** sum
  `wall_clock_seconds_by_scope.main` and `.subagent` (`economics.py:501` — they overlap; this
  PLAN's Prior Work already retracts one such ratio); (b) it must state how turns past the terminal
  attribution span cap (20–54% of spend) are handled. A reviewer must be able to state what result
  would falsify the hypothesis.
- **Risk:** low
- **Rollback point:** post-A1 HEAD
- **Status: DONE** (2026-08-08). `work-docs/EXPERIMENT-session-length-ab.md`, pre-registered
  before any run. Arms assigned by **alternation**, not by choice; medians not means; adopt at
  `median_B <= 0.75 × median_A` with `n >= 8` per arm, evaluated **per project** (per-turn costs
  differ 1.7× across the four, so a pooled mean would mostly measure which project landed in
  which arm). Both prohibitions are stated and checkable by reading: no summing of
  `wall_clock_seconds_by_scope.main` and `.subagent`, and an explicit span-cap correction — arm
  A's wrapups are likelier to be capped, which biases the primary metric **in the hypothesis's
  favour**, so capped sessions are excluded and >30% exclusion in arm A forces "inconclusive
  regardless of the numbers". The falsification condition is stated: if the fresh session's
  re-read consumes the saving, H1 is false and that is a result, not a failed experiment.
- **Phase D.5:** not applicable — A4 writes a protocol and touches no code.
- **⚠️ The deliverable was gitignored and would have been lost at wrapup.** `.gitignore:104` is
  `work-docs/*` with per-prefix negations (`PLAN-`, `RESEARCH-`, `BASELINE-`, `ABLATION-`,
  `MATRIX-`, …); `EXPERIMENT-` was not among them, so `git status` never showed the file and the
  wrapup commit would have carried everything except the one artifact whose entire value is
  being frozen before the run. Caught at Step 4 by noticing the file count was 19 when 20 files
  had been written. Fixed by adding `!work-docs/EXPERIMENT-*.md` with the same durability
  rationale the neighbouring `ABLATION-*` rule carries. This is the
  `a gitignored corpus verifies nothing` class (`4ce41d0c`) in a new location.
  **Correction — the enforcement I claimed did not exist does exist, and it caught me.** This
  entry first said "adding a new deliverable PREFIX requires a matching negation, and nothing
  enforces it". The full suite then failed
  `tests/structural/test_deliverable_single_source.py::test_gitignore_negations_match_the_source`
  with `gitignore-only: ['EXPERIMENT']` and the exact remedy in its message. The single source is
  `worktree.DELIVERABLE_PREFIXES`, from which the `.gitignore` negations **and**
  `worktree._DELIVERABLE_RE` (the `/hm:execute` create-guard exemption) both derive. Registering
  `EXPERIMENT` there fixed the test and, as a side effect, stops an uncommitted EXPERIMENT doc
  from blocking `worktree create` — the same reason PLAN and RESEARCH are exempt. The wrong claim
  flattered my own catch: I found the gitignore gap by eye and then asserted no guard existed,
  when the guard was one full-suite run away.
  Note also that `.gitignore:102`'s own verification instruction ("`git check-ignore -v` … must
  print NOTHING") is wrong for this git version — the working `PLAN-*` rule prints its negation
  and exits 0 exactly as the new one does. `git status` is the operative check.

### Phase A5 — The `instrumentation` axis (ADR-011) — **DONE**
- **depends_on:** `[A3]` — A3 decides which instrumentation prose survives at all; gating prose
  that A3 is about to delete would be wasted work
- **parallel_group:** `serial-a5`
- **merge_hazards:** `templates/stages/{plan,execute,review}.md.j2` (shared with A3 and B3);
  `tests/structural/surface_baseline.json` (shared with A3, B3, B4, B5)
- **Scope in:** `src/harness_maker/models.py` (the new config field),
  `src/harness_maker/templates/stages/{plan,execute,review}.md.j2` (gate the emit blocks),
  `src/harness_maker/templates/harness-yaml/{Production,Side}.yaml.j2`,
  `src/harness_maker/interview.py` (the question that sets it),
  `src/harness_maker/synthesize.py` + `interview.answers_from_harness_yaml` (the round-trip),
  `tests/render/`, `tests/unit/`, `tests/structural/surface_baseline.json`
- **Scope out:** `/hm:health`, `/hm:metrics` and `delivery_metrics` — those are the user's own
  observability and are explicitly NOT gated by this axis
- **Exit criterion:** (1) rendered from a fixture with the axis **off**, no
  `stage_agent_ledger emit` and no `persist-payload` invocation appears in any file under
  `.claude/` or `.codex/` — asserted by render-grep, and the surface baseline **decreases** with
  an attributing BASELINE-DELTA row; (2) rendered with it **on**, both appear exactly as today;
  (3) an absent key in an existing `harness.yaml` resolves to the maintainer-preserving value
  and logs the choice once, so a re-render never silently stops collecting from a project that
  was already contributing rows; (4) the interview question states, in the option text, that
  turning it off removes this project from the cross-project denominator — ADR-011's second ⚠️
  requires the trade to be visible at the point of choice, not only in this document;
  (5) round-trip through `synthesize → harness.yaml → answers_from_harness_yaml`. Plus `ruff` +
  `mypy --strict`.
- **Risk:** medium — two render paths through the stage templates this PLAN is otherwise
  shrinking, and a default that shapes all future measurement
- **Rollback point:** post-A3 HEAD
- **Status: DONE.** `models.InstrumentationConfig` + the `HarnessConfig` / `InterviewAnswers`
  pair, `_parse_instrumentation` (absent → ON, logged), `_ask_instrumentation`, the gate in all
  three stage templates, both `harness-yaml` templates, `commands/make.md`'s disclosure row, and
  eight tests. **The two defaults differ and both criteria are met:** a freshly rendered harness
  gets `false` (ADR-011's "a third-party install defaults to off"), so the surface baseline
  decreases by −7,238 / −7,247 with the BASELINE-DELTA row attributing it; an existing
  harness.yaml with no `instrumentation` key resolves to `true` with a one-time log, so the four
  projects already contributing rows keep contributing. An earlier pass of this phase read
  criterion (3) as governing the class default too and shipped ON everywhere — which would have
  satisfied the round-trip criteria while leaving every third-party install paying for this
  repo's telemetry, i.e. the exact thing the axis exists to stop.

### Phase B1 — One constant, one normalization owner, the AST discovery guard — **DONE**
- **depends_on:** `[]` (lands after A4 per the global order)
- **parallel_group:** `serial-b1`
- **merge_hazards:** none, but **the phase begins with a discovery pass**: `rg '"auto_safe"' src/`,
  with every hit put in scope before code is written. The round-2/3 lesson is that the enumeration
  is not trustworthy on its own — the AST test is.
- **Scope in:** `src/harness_maker/models.py`, `src/harness_maker/autopilot.py` (incl. the `:962`
  `cast`), `src/harness_maker/hooks/autopilot_autoarm.py` (**delete** the ladder),
  `src/harness_maker/autopilot_ledger.py`, `src/harness_maker/cli.py` (`valid_levels` + the
  `--update` advisory), `src/harness_maker/interview.py` (`_parse_autonomy` sibling-preservation
  only), `tests/unit/test_autonomy_defaults.py`, `tests/unit/test_autopilot_marker*.py`,
  **`tests/unit/test_autopilot_autoarm*.py`** (both existing suites pin the truth table that
  deleting the ladder changes), `tests/structural/` (the AST discovery test)
- **Scope out:** `autopilot_caps.py` (B3), templates (B3/B4), `_ask_autonomy` (B4)
- **Exit criterion:** all nine hold.
  1. `AutonomyConfig(level="full").level == "auto_safe"`.
  2. **The whole-block-loss guard uses an UNKNOWN level, not `full`:**
     `_parse_autonomy({"level":"typo","step_cap":7,"time_cap_min":9})` yields `level == "gated"`
     **and** `step_cap == 7` **and** `time_cap_min == 9`. Draft 1's case used `full`, already in
     today's Literal and therefore green pre-B1 — it exercised nothing. Satisfying this requires
     `_parse_autonomy` to fall back on the level alone rather than discarding the block.
  3. `"ask"` is accepted by the yaml Literal and **rejected** by `_VALID_LEVELS`,
     `resolve_toggle_config` / `autopilot on --level`, `autopilot_ledger --level`, and
     `cli --autonomy-level`, each error naming the three operational values.
  4. **`auto_full` arms.** `arm_if_persistent` with `level: auto_full` and
     `autopilot_persistent: true` writes a marker. Today's `else: return False` would make the
     flagship level silently never arm.
  5. **`ask` + `autopilot_persistent: true` writes NO marker and logs no error** — the picker owns
     the session (ADR-003). The absent case is asserted, not assumed.
  6. `_ARMED_LEVELS == set(OPERATIONAL_LEVELS) - {"gated"}`; both argparse `choices` and
     `cli.valid_levels` are `OPERATIONAL_LEVELS`; all **derived**, not restated.
  7. **The AST discovery test** passes with an allowlist of exactly the **two** `models.py` nodes
     (the `OPERATIONAL_LEVELS` assignment and the `AutonomyConfig.level` annotation), trigger set
     `set(OPERATIONAL_LEVELS) | {"ask","full"}`, threshold ≥2. **Prove it bites:** a deliberately
     re-added literal in a scratch module must make it fail.
  8. The `--update` advisory fires for a pre-update `level: full` and not otherwise.
  9. A marker with no level, or a legacy `full`, resolves through the same normalization. Plus
     `ruff` + `mypy --strict` — this is where the `cast` and the hook annotation would break.
- **Risk:** medium
- **Rollback point:** pre-B1 HEAD. **Reverting B1 requires reverting B2, B3, B4 and B5 first.**

### Phase B2 — `ask` resolution — **DONE**
- **depends_on:** `[B1]`
- **parallel_group:** `serial-b2`
- **merge_hazards:** none
- **Scope in:** `src/harness_maker/autopilot.py` (`effective_level`, the `status` JSON),
  `tests/unit/test_autopilot_marker*.py`
- **Scope out:** the picker template and its `ask-pending` branch (**B4** — B2 must not assert a
  property of a file it excludes and a phase that lands later)
- **Exit criterion:** `effective_level(root, yaml_level="ask", session_id=<none>)` returns `"ask"`;
  with a marker present it returns the marker's operational level; `"ask"` is never returned once a
  marker exists; the `ask` path never resolves to `gated` silently; `hm autopilot status` reports
  `reason: "ask-pending"`, `active: false`. Plus `ruff` + `mypy --strict`.
- **Risk:** medium
- **Rollback point:** post-B1 HEAD. Reverting B2 requires reverting B4's picker branch.

### Phase B3 — Judgment gates: source-stage-keyed, fail-closed, and split at review — **DONE**
- **depends_on:** `[B1]`
- **parallel_group:** `serial-b3`
- **merge_hazards:** `templates/stages/plan.md.j2` — shared with **A3, which lands first**.
  `templates/agents/_partials/step_manifest.md.j2` — shared with **B4, which lands after**.
  `tests/structural/surface_baseline.json` — shared with A3 (before), B4 and B5 (after).
- **Scope in:** `src/harness_maker/autopilot_caps.py` (`_JUDGMENT_GATED_STAGES`, the
  `--judgment-gate` input, the `judgment_gate` halt kind + `gate_blocked` row + marker
  preservation), `src/harness_maker/templates/agents/_partials/stage_end_summary.md.j2` (the
  discriminator derived from `summary_stage`; pass the gate flag into Step 2),
  `src/harness_maker/templates/stages/plan.md.j2`,
  `src/harness_maker/templates/stages/review.md.j2` (**split** the gate string per ADR-010),
  `src/harness_maker/templates/agents/_partials/step_manifest.md.j2`,
  `tests/unit/test_autopilot_caps.py`, `tests/render/`, `tests/structural/surface_baseline.json`
- **Scope out:** the picker block and any `--level` interpolation (B4); `_HUMAN_GATED_STAGES`
  membership; introducing a new caller-set Jinja variable (it would break the five stage templates
  outside this scope under StrictUndefined); Track A
- **Exit criterion:** all eight hold.
  1. **Today's clean path is preserved.** `boundary --current plan` and `--current review` with
     `--judgment-gate clear` return `proceed: true` at **every** level, including `auto_safe`. This
     is the assertion draft 3 got backwards: it pinned `proceed: false` at `auto_safe`
     unconditionally and called that "the default is unchanged".
  2. **Pending still stops by default.** The same calls with `--judgment-gate pending` return
     `proceed: false, halt_kind: "judgment_gate"` at **both** `gated` and `auto_safe`.
  3. **Fail-closed.** With the flag **absent**, the result equals the `pending` result at every
     level.
  4. **The differential.** With `--judgment-gate pending` at `auto_full`, both calls return
     `proceed: true` with the auto-answer directive, and a test asserts the `auto_safe` vs
     `auto_full` outputs **differ**. `--current verify` is not used here — that stage owns no
     judgment gate.
  5. **The land gate survives, probed with the call that reaches it.**
     `boundary --current verify` at `auto_full` returns
     `proceed: false, halt_kind: "merge_gate", next_stage: "wrapup"`. `--current wrapup` is the
     wrong probe — it hits the `nxt is None` branch (`:316`) and reports `pipeline_complete`.
  6. **Non-default pipeline.** With `pipeline: [plan, review, verify, wrapup]`, `--current plan`
     with `pending` at `auto_safe` still returns `judgment_gate` — source-stage keying, not
     `(source,next)`.
  7. **ADR-010's split is real.** `review.md.j2`'s rendered Step 1 treats `grade < threshold` as
     gate-first at **every** level (a render-grep asserts the string is not level-conditional),
     while `human_review_needed` on an APPROVED review routes to the boundary. A render-grep per
     file asserts the level-conditional branch exists in the rendered `plan` and `review` surfaces;
     `stage_end_summary.md.j2`'s judgment branch is present and its land branch unchanged, both
     asserted.
  8. `judgment_gate` appends a `gate_blocked` row with the stage and **preserves** the marker
     (asserted, not assumed — `merge_gate` clears it, and copying that would end the autopilot
     session at every plan stage while starving `smoke_check` of rows). The auto-answer recording
     instruction is present for both gates: for `plan`, the recommended option is written into the
     PLAN's Interview Transcript; for `review`, the passed-over finding ids into the REVIEW
     document. Plus a BASELINE-DELTA row, `ruff` and `mypy --strict`.
- **Risk:** **high** — changes the advance ordering for every stage; the PLAN's largest blast radius
- **Rollback point:** post-B1 HEAD. **Reverting B3 requires reverting B4's `auto_full` offer in the
  same operation**, or the interview keeps offering `auto_full` with `auto_safe` semantics —
  reinstating the divergence REVIEW P6 corrected once.

### Phase B4 — Interview, picker, and every rendered `--level` surface — **DONE**
- **depends_on:** `[B1, B2, B3]` — B2 supplies the `ask-pending` reason the picker branches on; B3
  owns the same partial
- **parallel_group:** `serial-b4`
- **merge_hazards:** `templates/agents/_partials/step_manifest.md.j2` — shared with **B3, which
  lands first**. `tests/structural/surface_baseline.json` — shared with A3, B3 (before), B5 (after).
- **Scope in:** `src/harness_maker/interview.py` (`_ask_autonomy`),
  `src/harness_maker/templates/agents/_partials/step_manifest.md.j2` (guard `:28`, arm command
  `:52`, picker block), `src/harness_maker/templates/commands/hm/health.md.j2` (guard `:131`, smoke
  `:140`), `src/harness_maker/templates/harness-yaml/{Production,Side}.yaml.j2`,
  `tests/unit/test_interview*.py`, `tests/render/`, `tests/structural/surface_baseline.json`
- **Scope out:** everything in Track A
- **Exit criterion:** all five hold.
  1. The first interview offers all four values with `auto_safe` as the default; an explicit decline
     still pins `gated` / `autopilot_persistent: false`.
  2. A round-trip test asserts each of the four values survives
     `synthesize → harness.yaml → answers_from_harness_yaml`.
  3. **Rendered from an `ask` fixture** — not the default `auto_safe` templates, which pass it
     vacuously — `--level ask` appears in **no file** under `.claude/` or `.codex/`.
  4. Under `ask`: the picker presents the three operational options (a render-time test on
     `config.autonomy.level == "ask"`, because `effective_level` is unreachable at render time);
     `step_manifest.md.j2:52`'s arm command carries the **picked** level; and
     `health.md.j2`'s autopilot smoke section is **absent**, replaced by the one-line
     level-unresolved note (ADR-007). Hard-coding `--level auto_safe` there fails this criterion.
  5. The picker's runtime branch list handles `reason: "ask-pending"` **explicitly**, not via its
     "anything else" default. Render-grep. Plus `ruff` + `mypy --strict`.
- **Risk:** medium — criteria 3 and 4 are shipped-breakage guards
- **Rollback point:** post-B3 HEAD

### Phase B5 — Close the PLAN: a net-surface test that can fail, and the full suite — **DONE (red, waived)**
- **depends_on:** `[A3, B4]` — the last-landing phase; the one declared cross-track edge (ADR-006)
- **parallel_group:** `serial-b5`
- **merge_hazards:** `tests/structural/surface_baseline.json` — **B5 is last**
- **Scope in:** `tests/structural/` (the new net-surface assertion),
  `work-docs/BASELINE-DELTA-workflow-time-token-savings.md` (the closing row),
  `tests/structural/surface_baseline.json` (only for a legitimate, attributed re-freeze)
- **Scope out:** any source or template change — B5 asserts, it does not fix. A red B5 opens a
  follow-up; it does not authorise edits outside the phases that caused it.
- **Exit criterion:** both hold. (1) A **test** asserts
  `aggregate_chars.claude <= <the integer A1 recorded>` and **fails** when it does not. If the PLAN
  legitimately ends net-positive, the only permitted escape is an explicit `xfail` with a waiver
  referencing the closing BASELINE-DELTA row, so the failure stays visible in CI (ADR-008.4 — the
  earlier "or record it red" disjunction was unfailable). (2) `ruff check`,
  `ruff format --check`, `mypy --strict` and the **full** `pytest` suite pass — run in the
  background (≈6 min), with `rc=$?` written to a file and that file trusted rather than the
  notification's exit code. This is the producing phase for the corresponding Success Criteria
  bullet, which previously had none.
- **Risk:** low mechanically; the phase most likely to legitimately land red or `xfail`
- **Rollback point:** post-B4 HEAD. Reverting B5 reverts an assertion and a record.
- **Status: DONE, and the assertion is RED.** `tests/structural/test_plan_net_surface.py` reads
  §0's pre-PLAN literal out of the BASELINE-DELTA document (so the asserted number and the
  recorded number cannot drift) and compares it to the frozen baseline. `claude` is
  **+1,057** (366,439 → 367,496); `codex` is **−357** and passes. The `xfail` carries the
  ADR-008.4 waiver naming B3 as the cause and stating why compressing further is refused:
  the next candidate was `auto_full`'s auto-answer recording instruction, which ADR-010 lists
  as its only compensating control. `strict=False` because the codex variant genuinely passes.
  `surface_baseline.json` WAS re-frozen (at base SHA `bdaa0ae0`, durable) so day-to-day
  ratcheting resumes — but the PLAN-level assertion is deliberately NOT re-based, which is the
  difference between this and `ratchet-rebaselined-by-its-own-subject`.

## 🧪 Testing Strategy

**Unit.** A1's three cases including the `is_own_cwd` collision pin. A2's reconcile arithmetic on
synthetic fixtures, one per anomaly shape (N-vs-0 and 0-vs-N). B1's matrix — four accepted values,
the `full` alias, an **unknown** level with surviving siblings, marker-layer normalization,
autoarm-arms-`auto_full`, and `ask`-plus-persistent-writes-nothing. B2's four `effective_level`
combinations. B3's boundary matrix: **three levels × three gate-states (`clear` / `pending` /
absent) × {`plan`, `review`}**, plus `--current verify` for the land gate and one non-default
pipeline.

**Structural.** The ADR-005 AST discovery test **plus a meta-assertion that it fails** on a
deliberately re-added literal — a discovery test nobody has seen fail is a hand-list with extra
steps. A3's BASELINE-DELTA attribution test (already present) plus rows from B3, B4, B5. B5's
net-surface test.

**Render.** Per-file greps for B3's two gate owners, for `review.md.j2`'s grade predicate being
**not** level-conditional, and for `stage_end_summary.md.j2`'s two branches; B4's `--level ask`
absence rendered **from an `ask` fixture** over every file under `.claude/` and `.codex/`; B4's
`ask-pending` picker branch and the absent `/hm:health` smoke under `ask`; A3's emit-survival grep.
Every stage template must still render under StrictUndefined after B3 — the five outside its scope
are the reason the discriminator is derived rather than caller-set.

**Integration / manual.** `hm autopilot status` / `on` / `boundary` and `hm autopilot_ledger smoke`
from a real shell in both the base repo and a task worktree — the CLI-in-a-worktree divergence is a
recurring class and unit tests using absolute paths do not reach it. A full interview producing each
of the four levels, then `/harness-maker:make --update` over a `level: full` harness to observe the
advisory. One live `auto_full` run from `plan` to the land gate, plus one where review returns
`CHANGES_REQUESTED`, to confirm ADR-010's split holds in behaviour and not only in text.

## ⚠️ Risks & Mitigation

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| ADR-009's reordering lets a stage advance past an unresolved human decision | medium | **high** | B3 criteria 2 and 3: `pending` stops at `gated`/`auto_safe`, and an **absent** flag equals `pending` (fail-closed) |
| `auto_safe` stops advancing at plan/review even on clean stages | **certain** in draft 3 | high — autopilot stops working for the default level | B3 criterion 1: `clear` returns `proceed: true` at every level. This is the defect round 3 caught |
| `auto_full` consumes the only surfacing path for unverified `manual-only` P0/P1 findings | high by design (ADR-010's ⚠️) | medium | the recorded passed-over finding ids in the REVIEW document, asserted by B3 criterion 8; the grade predicate remains mandatory at every level |
| `auto_full` ships dead on the persistent path (autoarm's `else: return False`) | **certain without a fix** | high | B1 criterion 4; the ladder is deleted, not patched |
| An eleventh level-declaration site is missed, as the fifth-through-tenth already were | medium | high | the ADR-005 AST discovery test with its bite-proof, plus B1's opening `rg` pass |
| Judgment gates vanish on a user-customised `autonomy.pipeline` | medium | high — count:8 class | source-stage keying (ADR-009.1) + B3 criterion 6's non-default-pipeline case |
| `judgment_gate` clears the marker or emits no row → `/hm:health` reports degraded on a healthy harness | medium | medium | ADR-009.3 fixes both; B3 criterion 8 asserts them |
| A new caller-set Jinja var breaks the five out-of-scope stage templates under StrictUndefined | medium | medium | ADR-009.4 derives the discriminator from `summary_stage`; the render suite covers all seven |
| `level: ask` or `auto_full` renders a `--level` flag every CLI rejects | certain without a guard | high | B4 criteria 3–4, rendered from an `ask` fixture, over both interpolation sites |
| `/hm:health` hard-codes a level the project never chose | medium | medium | ADR-007 forbids it explicitly; B4 criterion 4 asserts the section is absent under `ask` |
| Net shipped surface grows while the PLAN reports enforcement | medium | medium | B5's **failing** test against A1's recorded literal; `xfail` + waiver is the only escape |
| `mypy --strict` breaks between B1 and B4 and is found at wrapup | medium | medium | every code phase runs `ruff` + `mypy --strict`; B5 runs the full suite |
| Partial rollback of B3 leaves a selectable `auto_full` with `auto_safe` semantics | medium | medium | revert closure stated per phase; B3's rollback names B4 |
| A2 escapes a real loader defect via a wiki entry | medium | medium | `economics_source.py` in A2's scope; branch (ii) requires a positive mechanism |
| The spoton 0-row anomaly is dismissed, leaving a preset class out of the denominator | medium | high — RESEARCH Pitfall 2 is the precedent | A2 must resolve **every** disagreeing project |
| A3/B3 collide on `plan.md.j2` across the track boundary | medium | low | the global order (A3 first) in the preamble and mirrored in both phases' hazards |

## ✅ Success Criteria

> **Wrapup 2026-08-09 — Track A closed; Track B (A5, B1–B5) never started.** Only the
> criteria below that are ticked have been observed. The unticked ones belong to A5 and
> B1–B5, whose Status lines read NOT STARTED; they are left unticked deliberately rather
> than swept green by the wrapup, because ticking an unrun phase's criterion is the
> `unverified-claim` failure this PLAN's own review recorded twice.

**Track A**

- [x] `economics stages --root <underscore path>` reports non-zero turns — **observed live for
      strange_chess in A2**, not only in synthetic unit cases.
- [x] `hm stage_agent_ledger reconcile` exists, runs on all four projects, and every disagreeing
      project — strange_chess **and** spoton — has a recorded loader fix or a positive mechanism.
- [x] A2's `wiki.md` entry ends with `ledger-trustworthy: yes|no`, and A3's row quotes it.
- [x] The `stage_agent_ledger emit` invocation still appears in both rendered stage surfaces.
- [x] `EXPERIMENT-session-length-ab.md` states a falsifiable decision rule, forbids summing
      wall-clock scopes, and states its post-cap handling.

**Track B — not started, criteria unobserved**

- [ ] `AutonomyConfig(level="full").level == "auto_safe"`; a `level: full` harness keeps its caps
      and pipeline; `--update` emits the advisory for it.
- [ ] `_parse_autonomy({"level":"typo","step_cap":7})` yields `gated` **with `step_cap == 7`**.
- [ ] `level: auto_full` + `autopilot_persistent: true` **arms**; `level: ask` + persistent writes
      **no** marker and no error.
- [ ] `_ARMED_LEVELS`, both argparse `choices`, `cli.valid_levels` and `_VALID_LEVELS` all derive
      from `OPERATIONAL_LEVELS`; the AST discovery test passes **and** is shown to fail on a
      re-added literal.
- [ ] `boundary --current plan|review` with `clear` returns `proceed: true` at every level; with
      `pending` returns `judgment_gate` at `gated` **and** `auto_safe`; with the flag **absent**
      behaves as `pending`; differs at `auto_full`; and still returns `judgment_gate` on a
      non-default pipeline.
- [ ] `boundary --current verify` still returns `merge_gate` at `auto_full`.
- [ ] `judgment_gate` appends a `gate_blocked` row and preserves the marker.
- [ ] `review.md.j2`'s `grade < threshold` predicate is gate-first at **every** level; only
      `human_review_needed` routes to the boundary; passed-over finding ids are recorded at
      `auto_full`.
- [ ] All seven stage templates still render under StrictUndefined after B3.
- [ ] Rendered from an `ask` fixture, `--level ask` appears in no file under `.claude/` or
      `.codex/`; the picker offers three options and handles `reason: "ask-pending"` explicitly;
      `/hm:health`'s smoke section is absent with the one-line note.
- [ ] `effective_level(yaml_level="ask")` returns `"ask"` with no marker; `hm autopilot status`
      reports `reason: "ask-pending"`.
- [ ] The first interview offers `gated` / `auto_safe` / `auto_full` / `ask`, and all four
      round-trip through `harness.yaml`.
- [ ] B5's net-surface test passes, or is an explicit `xfail` with a waiver referencing the closing
      BASELINE-DELTA row.
- [x] `ruff check`, `ruff format --check`, `mypy --strict` and the full `pytest` suite pass —
      verified GREEN at Track A wrapup (2026-08-09, `rc=0` recorded to file), ahead of B5.

## 🔍 Plan Validation

**Round 1 — MAJOR_REVISION** (4 critical, 6 warning, 2 suggestion).
**Round 2 — MAJOR_REVISION** (4 critical, 5 warning, 2 suggestion).
**Round 3 — MAJOR_REVISION** (3 critical, 6 warning, 2 suggestion), operator-requested above the
stage's 2-pass cap.
**Cross-model second opinion:** `codex` **invoked**, 11 findings (2 × P0); `antigravity`
**skipped** — `exit 1: Error: timeout waiting for response`, so this PLAN carries no antigravity
voice. Both on `.claude/observability/second-opinion.jsonl` (`stage: plan`); all three validator
passes on `stage-agents.jsonl` under run `wtts-20260808-1`.

**Ledger integrity defect, recorded rather than hidden.** `--terminal` was stamped on pass 2,
because at that moment the 2-pass cap had ended Step 4; pass 3 was then requested. The ledger is
append-only, so `hm stage_agent_ledger coherence` now reports this run **BAD** (a terminal row that
is not the last). Any aggregation keyed on the run's ending will read pass 2. The lesson for the
template: `--terminal` should be stamped only once no further pass can be requested, which the
current prose does not say.

Every critical from all three rounds was verified against source before being acted on, and every
one was accurate. **Round 3's criticals, and their resolution:**

| # | Defect (verified) | Resolution |
|---|---|---|
| R3-1 | `boundary` had no gate-state input, so a judgment-gated transition had to be answered **unconditionally**; the criterion pinning `proceed: false` at `auto_safe` would have made `auto_safe` halt at plan→execute and review→verify **on clean stages**, labelled "the default is unchanged" — the inverse of today (`autopilot_caps.py:342-347` returns `proceed: true` once Step 1's conditional gate clears) | ADR-009.2 rewritten: `--judgment-gate pending\|clear`, **absent ⇒ pending** (fail-closed). B3's criteria became a 3 × 3 matrix whose first case is "`clear` → `proceed: true` at every level", i.e. today's behaviour asserted rather than asserted-away |
| R3-2 | `("review","verify")` is **not** a judgment gate: its predicate is `grade < threshold OR human_review_needed` (`review.md.j2:666`, receipt semantics at `:640`) — a failed quality threshold, so "auto-answer it" means advancing past a failed review, which `models.py:790-796` forbids and no interview had asked | **Interview #6** put it to the user, who chose "`human_review_needed` only, never `grade < threshold`". New **ADR-010** splits the gate; the grade predicate becomes a stated **Non-Goal**; the Executive Summary now says `auto_full` removes one outright stop plus one conditional one, not two |
| R3-3 | `(source, next)`-keyed membership breaks on any user-customised `autonomy.pipeline` (`models.py:809-819`) — the gates belong to the *source* stage; every criterion was written against the default pipeline (count:8 shape) | `_JUDGMENT_GATED_STAGES = {"plan","review"}`, source-keyed; `_HUMAN_GATED_STAGES` stays next-keyed; B3 criterion 6 asserts the gate still fires on `[plan, review, verify, wrapup]` |

**Round-3 warnings, all resolved:** `stage_end_summary.md.j2` is one shared include under
StrictUndefined with no branch and five out-of-scope callers, so the discriminator is **derived
from `summary_stage`** rather than caller-set (ADR-009.4); `judgment_gate`'s side effects are
specified — `gate_blocked` row appended, marker **preserved**, both asserted (ADR-009.3); the AST
allowlist is **two** `models.py` nodes, not one, with the trigger set and ≥2 threshold defined
(ADR-005.3); `/hm:health`'s `ask` behaviour is **decided in the PLAN** — smoke section absent plus a
one-line note, with hard-coding `auto_safe` explicitly forbidden (ADR-007); B1's scope gains
`tests/unit/test_autopilot_autoarm*.py` and a criterion for `ask` + persistent; B5's disjunction is
replaced by a **failing test** whose only escape is a documented `xfail` (ADR-008.4).
**Suggestions resolved:** ADR-006 now declares B5's cross-track `depends_on` as its one exception;
A2 observes the live strange_chess recovery so Success Criteria bullet 1 has a real producer.

**One codex finding refuted, and it stands refuted across all three rounds.** `dc7b1557` claimed A1
risks cross-project contamination. Verified independently twice: `is_own_cwd` is an anchored
per-turn prefix test applied at `economics_source.py:488` and `context_composition.py:131`, and
`discover_transcript_dirs:127-131` documents the name match as deliberately lossy with the cwd
check as the real boundary. Widening the encoder can admit foreign *directories* whose turns are
then dropped, never foreign turns. A1 exit case 3 pins it.

**No pass 4 was run.** The operator authorised one pass above the cap, and that pass is spent.
Rounds 1–3 each found genuine criticals in the newest and most ambitious part of the PLAN, so the
residual risk is concentrated in **Phase B3** — it carries ADR-009 and ADR-010, changes the advance
ordering for every stage, and is the phase whose criteria have been rewritten three times. The
honest reading is that B3 deserves its own review round at implementation time rather than
confidence from this document. Everything Track A does is small, mechanical and independently
landable; if B3 proves as hard in practice as it has on paper, Track A can land alone.
