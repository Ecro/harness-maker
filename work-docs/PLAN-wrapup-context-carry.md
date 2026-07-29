---
type: plan
task_slug: wrapup-context-carry
status: complete
phase_status:
  1_economics_collapse: done       # GREEN — 14 tests; exit criterion 266 passed
  2_delegation_ledger: done        # GREEN — 13 tests; exit criterion 172 passed
  3_brief_seam: done               # GREEN — templates/stages/wrapup.md.j2 (--slug on the
                                   # brief + self-skip `unavailable` ledger line),
                                   # delegation_ledger.main() `record` subcommand,
                                   # metrics.md.j2 coverage prose; 5 integration tests
                                   # (AC-004/005/009 + a base-root guard). Exit criterion
                                   # 187 passed. See the deviation note below.
  4_health_signal: done            # GREEN — readiness._dim_guardrails emits
                                   # `delegation_fires` at weight 0; 13 tests covering all
                                   # 7 ADR-006 arms + the weight/score invariants.
                                   # Arms 2/6/7 and stage scoping came from review
                                   # rounds 3-5, not from the original design.
  5_correct_the_record: done       # RESEARCH correction block, both wiki entries, and
                                   # CLAUDE.md's wrong template path. Exit criterion run;
                                   # see the frozen-corpus reconciliation below.
review: "[[REVIEW-wrapup-context-carry]]"
review_grade: A
review_rounds: 6
accepted_limitations:
  - "delegation_fires detects a stopped dispatch, not an intermittent one (user decision 2026-07-29, option 1 of 3) — see ADR-006 and the SPEC's Accepted Risks"
  - "a peer IDE's single `unavailable` row can satisfy the PASS arm on the shared ledger"
  - "the fix is not live for harness-maker itself until a plugin release ships — the dogfood .claude/ is rendered from the installed 0.43.3, not from this tree"
created: 2026-07-28
tags: [harness-maker, plan, python, observability, context-economy, delegation]
spec: "[[SPEC-wrapup-context-carry]]"
research_doc: "[[RESEARCH-context-carry-economics-2026-07-28]]"
mtime_warn_days: 7
summary: "Collapse split transcript records to API calls, and give the wrapup brief a slug-derived identity"
second_opinion_results:
  - model: codex
    status: invoked
    reconciliation:
      - finding: "AC-006 verifies only degraded ledger rows, so a writer that logs no ok rows passes while destroying the denominator"
        disposition: REFUTE
        note: "Correct. AC-006 gained a success arm; ADR-005 states the ok path explicitly."
      - finding: "the template's unavailable writer is scheduled before the ledger module it calls, and no test executes the rendered self-skip path"
        disposition: REFUTE
        note: "Correct — a real sequencing inversion. Ledger module moved to Phase 2; new AC-009 executes the rendered self-skip line."
      - finding: "lifetime existence of one dispatch row keeps the signal green through any later regression"
        disposition: REFUTE
        note: "Correct, and the sharpest of the three: it rebuilds this defect's blind spot one layer in. ADR-006 now reads a 10-brief recency window (any status — the ok-only form re-opened the same blind spot, see the amendment note)."
  - model: antigravity
    status: failed
    reconciliation: []
---

# PLAN — wrapup context carry

## 🎯 Goal

Make the economics meter count API calls instead of transcript records, and stop
`wrapup_brief` deriving the task identity from a cwd it is never handed. The first makes
this work's own before/after meaningful; the second re-enables the delegation that has
been silently inert since it shipped.

## 🎙️ Interview Transcript

SPEC `status: approved` with empty Open Questions → `/hm:plan` **Case A**: the deep
interview is skipped. The four substantive decisions were taken during `/hm:spec` and are
recorded there; they are restated as ADR context below rather than re-asked.

| # | Topic | Category | Question | Choice | → ADR |
|---|---|---|---|---|---|
| 1 | Scope | Scope boundaries | meter, delegation, boundary, or a combination? | meter + delegation; compaction boundary out | context for ADR-001/002 |
| 2 | Stage | Scope boundaries | include `hm:verify`? | no — 1/12 of wrapup's size | SPEC Non-Goals |
| 3 | Delegate extent | Architecture | does the delegate get git? | no — ADR-004 of the wrapup design holds | SPEC Non-Goals |
| 4 | Recurrence defense | Observability | warn / warn+ledger+health / repair-only | warn + ledger + health signal | ADR-005, ADR-006 |
| 5 | IDE without a dispatch tool | Failure handling | `unavailable` ledger row vs. a detection-rule N-A arm | self-skip writes an `unavailable` row | ADR-005, ADR-006 |

**Validation rounds.** `plan-validator` returned REVISE twice — 7 blocking issues, then 4 —
and every checkable claim in both rounds was verified against the source before being
accepted. Two of them were design defects rather than gaps: the ledger measured brief
derivability instead of dispatch, and the health signal's informational arm carried an
action string that no surface renders. The retry budget was exhausted, so the third round
and question 5 above went to the user, who chose to keep refining. The third round found
one more: Phase 5's oracle ran against a rolling 30-day window, so its pre-registered
figures could never reproduce — the corpus is now frozen and the reference re-derived from
it.

**Cross-model second opinion (Production — mandatory).** Codex returned three P1 findings,
all REFUTE; antigravity `failed` on an unreadable payload and, per the warn-and-proceed
contract, did not block. Codex's third finding is the one to remember: after three
in-house rounds had hardened the ledger into measuring *dispatch* rather than derivability,
the health rule still asked whether a dispatch had **ever** happened — which on an
append-only ledger goes green on the first success and stays green through every later
regression. The blind spot this work exists to close had been rebuilt one layer further in,
and only a reviewer outside the conversation saw it.

At Step 3.0 the user chose **"proceed to phase decomposition"** over opening a round on
the remaining *how* question (where to close the cwd seam). That question is therefore
decided here, by the planner, and is written up as ADR-001 with its rejected alternatives
stated so it can be overturned cheaply if the call is wrong.

## 🏛️ ADRs

### ADR-001: the brief's identity comes from the slug, not from a cwd

**Status:** accepted

**Context:** `derive_brief(cwd)` runs `git rev-parse --show-toplevel` on its cwd and reads
`HEAD` there. The rendered command invokes it from a `!` line as `--root .`, and `!` lines
execute at the **base repo**, whose `HEAD` is `main`. (The template is
`templates/stages/wrapup.md.j2`; `templates/commands/hm/wrapup.md.j2` does not exist, and
the repo's own CLAUDE.md carries the same wrong path — Phase 5 corrects it.) The gate
therefore returns
`degraded` on the normal Production path, 100% of the time — measured at 14 of 16 runs
inline, the other 2 being sessions where the model dispatched anyway.

This is the **fourth** recorded instance of the same shape in this repo: `second_opinion`'s
cwd-relative `--output-schema`, `codex_ledger`'s `project_root=Path.cwd()`, and
`wrapup_receipt`'s `--worktree` (whose own Step 0.5 note warns that "`!` lines run at the
BASE repo" — two tool calls above the line that gets it wrong).

**Decision:** add an optional `--slug` to `wrapup_brief`. When present, the task worktree
is located from the **base repo** by matching `refs/heads/hm/<slug>` in
`git worktree list --porcelain`. When absent, today's cwd-derived path is kept unchanged.
The rendered command passes `--root . --slug <slug>` — the `!` line's natural cwd is now
the correct one, and no `<WT>` placeholder is involved.

**Consequences:** the identity is the thing the stage was invoked with, not a property of
whichever directory a shell happened to start in. `derive_brief` gains a branch, and a
`--slug` naming a task with no worktree degrades — which is correct, and is
distinguishable in the ledger from "HEAD is main" by its reason string.

**Which field goes into `missing` on that path: `slug`.** The local convention pulls the
other way — `validate_brief` reports a worktree that is not `base/.worktrees/<slug>` as
missing `worktree_root` — so an implementer following it by reflex emits `worktree_root`
and fails AC-005. The AC is right and the convention does not apply: this path has no
worktree to be wrong about, it has a **slug that resolved to nothing**, which is the same
underivable field the cwd path reports. The `reason` string is what separates the two.

**`--slug` is a model-substituted placeholder, exactly like `<WT>`.** An earlier draft of
this ADR claimed the decision removed a substitution; it does not. The repo's own
convention (`agents/_partials/worktree_preflight.md.j2`, `wrapup.md.j2`) is a literal
`<slug>` the model replaces, and this line joins it. The argument for the decision is not
placeholder arithmetic — it is **which failure a mistake produces**. A wrong cwd degrades
into a verdict that is byte-identical to the legitimate standalone case, which is why this
went unseen for four months; a wrong or unsubstituted slug degrades with a reason that
names the slug, which the ledger separates. Quote it as `--slug '<slug>'` so an
unsubstituted token becomes a bad argument rather than a shell input redirect.

**How AC-004 executes it.** The test renders the template **hermetically into a tmp tree**
— not the repo's committed `.claude/commands/hm/wrapup.md`, whose contents are whatever
the last dogfood render left. It extracts the `!` line for `wrapup_brief`, asserts the line
still carries a base-relative `--root`, substitutes **only** the `<slug>` token with the
branch the test created, and runs it. Re-typing the whole argv would make the test agree
with itself.

**Alternatives rejected:**
- **`--root '<WT>'`.** Smallest diff and matches the `wrapup_receipt --worktree`
  precedent, but it keeps identity cwd-derived. Given three prior incidents of exactly
  this class, moving *toward* cwd derivation is the wrong direction — and the substitution
  cost is a wash, as stated above.
- **Scan for any `hm/*` worktree from base.** No slug needed, but ambiguous the moment two
  tasks are in flight — which the multi-session worktree model explicitly supports.
- **Make the `!` line `cd` into the worktree first.** Bash cwd persists across a stage's
  calls in this harness, so a stray `cd` silently relocates every later relative command.

### ADR-002: collapse at ingestion, in `load_turns`

**Status:** accepted

**Context:** Claude Code writes one JSONL record per content block (`thinking` / `text` /
`tool_use`) and stamps the **same** `usage` on each. Verified verbatim: one `message.id`,
three records, identical `in=2 out=1663 cr=20352 cw=56171`. Over the frozen corpus, 24,082
assistant records collapse to 10,945 calls (10,942 distinct ids; see the within-file note).

**`load_turns` has four call sites, not three.** Verified: `economics.py:724` (report),
`economics.py:841` (doctor/stages), **`cache_diagnostics.py:615`**, and
**`run_classify.py:342`**. An earlier draft named only the first three, which mattered —
`run_classify` is where the subtle damage is (see ADR-003).

**Decision:** group **within a single transcript file** by `message.id` inside
`load_turns`, and emit one `TurnRecord` per group. Within-file is the key, not a global
`message.id`: main-loop and subagent records live in separate files
(`*/subagents/agent-*.jsonl`), grouping never needs to span files, and a within-file rule
cannot merge two unrelated turns if an id ever repeats. Records with no `message.id` are
never grouped — each gets a unique sentinel — so an unknown or older transcript format
degrades to today's behaviour.

**Within-file is not a precaution — it was measured after implementation.** Running the
shipped collapse against the frozen corpus produced 10,945 calls where the pre-registered
figure said 10,942. The gap is exactly 3, and the cause is that **two `message.id`s recur
across different subagent transcripts** (`agent-a8c94f` / `agent-ad6f81` / `agent-af08a8`,
and a second id across two of those). A global key would have fused *different agents'*
turns into one call. The ADR was written as a defensive "an id might repeat"; it turns out
to happen, and the discrepancy the oracle flagged is what proved it.

**Consequences:** one fix serves all four consumers and no caller changes. `TurnRecord`
gains a `message_id` field. The collapse happens before the `is_own_cwd` and window
filters, so grouping cannot be split across a filter boundary — which is also what forces
ADR-004's counter-unit discipline.

**Alternatives rejected:** deduping in each consumer (three copies, three chances to
diverge); deduping in `price_turn` (too late — turn counts would still be wrong).

### ADR-003: collapse usage once, union the metadata

**Status:** accepted

**Context:** the split records are **not** interchangeable. The `tool_use` block — and
therefore `written_paths` — lives in exactly one record of the group. `written_paths`
feeds the ordered-ladder classifier's `last_write_at`, so a collapse that keeps the wrong
record makes a turn that wrote files look like it wrote none, silently re-labelling
PRODUCE/REWORK turns as OTHER. `uuid` is the retroactive-classification **verdict cache
key**, so a non-deterministic winner invalidates the cache on every run.

**Decision:** one deterministic rule, stated field by field:

| field | source |
|---|---|
| `usage` | the record with max `output_tokens` (ties → last), so a partially-streamed group takes its final counts |
| `written_paths` | **union** across the whole group, order-preserving |
| `uuid`, `ts`, `preceded_by_user`, `session_id` | the **first** record in file order — stable across runs, so cache keys do not move |
| `is_sidechain` | the **first** record's value. It is `bool = False` and never null, so "first non-null" would be vacuous; it is also the sole input to `TurnRecord.scope`, the main-vs-subagent partition this work's headline claim rests on. Records in one file are all one side of that partition, so first-record and any-record agree except in a malformed transcript, where first-record at least keeps the group with the file it came from |
| `model`, `attribution_skill`, `attribution_agent`, `cwd`, `git_branch`, `task_slug` | first non-null in file order |

That is all 13 current `TurnRecord` fields; the 14th, `message_id`, is added by this phase
and is self-evidently the group key.

**Consequences:** the intent is that the classifier and the verdict cache are unaffected by
the change of counting unit. **That is a claim, not a given, and Phase 1 must demonstrate
it rather than assert it.** `run_classify.find_boundaries` derives boundaries from
attribution *changes* between adjacent turns, and this rule sets a collapsed turn's
`attribution_skill` to the group's first non-null value — so a call whose blocks straddled
an attribution change becomes one attributed turn and that boundary disappears. Verdicts
cached under a now-unreachable uuid are silently discarded and counted as a cache miss,
which `run_classify.py` records as having already happened once. Phase 1 therefore carries
an assertion pinning `find_boundaries(collapsed)` to the pre-collapse first-record uuids;
if it cannot hold, the cache-miss cost is recorded here and a migration is planned instead
of the no-migration claim.

**The fixture must exercise the `usage` rule.** In the measured artifact all three records
carry byte-identical usage, so keep-first, keep-last and max-output are indistinguishable
there and the max branch would ship untested — a survivor the tier-2 mutation gate would
find. The fixture therefore includes one group with differing `output_tokens`.

### ADR-003 addendum — measured before implementation (2026-07-28)

The field-source table above was designed against one hand-inspected group. Before writing
a line of it, all **5,757 multi-record groups** in the frozen corpus were checked for
intra-group disagreement:

| field | groups that disagree |
|---|---:|
| `attributionSkill`, `attributionAgent`, `isSidechain`, `sessionId`, `gitBranch`, `cwd` | **0** |
| `usage.input_tokens`, `usage.cache_read_input_tokens`, `usage.cache_creation_input_tokens` | **0** |
| `usage.output_tokens` | **1** (0.017%) |

Three consequences, and they cut in different directions:

1. **The boundary claim is true, and it is true as an invariant rather than by luck.**
   `find_boundaries` can only lose a boundary when a group's records disagree on
   `attribution_skill`; that happens in 0 of 5,757 groups, so every unattributed stretch
   necessarily begins at a group's first record and both the uuid and the boundary set are
   preserved. The round-2 reviewer was right that the assertion is preserved *by
   construction* — but the remedy is to **state and test the precondition**, not to
   fabricate a shape the data does not contain. A fixture built to break an invariant that
   holds would be testing an input the system never receives.
2. **The disagreeing-attribution fixture stays, with a different job.** It no longer claims
   to falsify ADR-003; it pins the behaviour on an unmodelled input so the answer is
   *defined* rather than whatever the loop happens to do. `written_paths` is unaffected by
   this measurement — content blocks differ per record by construction, which is why the
   union rule is the one part of the table that is load-bearing on real data.
3. **The max-`output_tokens` rule fires roughly never**, which is exactly why the fixture
   must synthesise it. One group in 5,757 is not enough for the real corpus to distinguish
   keep-first, keep-last and max — the branch would ship unexercised.

Measured with `tests/manual/oracle_split_record_probe.py`'s corpus walk; re-runnable
against the frozen snapshot.

**Alternatives rejected:** keep-first (drops usage from partially-streamed groups);
keep-last (drops `written_paths` when the tool call precedes the final text block);
sum-the-group (the defect itself, re-expressed).

### ADR-004: `coverage`'s denominator counts calls, not lines

**Status:** accepted

**Context:** `IngestionDiagnostics.coverage` is priced turns ÷ in-window assistant lines,
and ADR-009 of `harness-economics-observability` made it the drift signal that catches a
transcript format change. Collapsing divides the numerator by ~2.2 and leaves the
denominator alone — coverage would fall from 1.00 to ~0.45 and stay there, permanently
red, which retires the drift signal by making it always-on.

**Decision — stated as arithmetic, because prose hid a unit mismatch.** Today:

```
denominator = assistant_lines - skipped_by_reason["outside_window"]
coverage    = turns_with_usage / denominator
```

`assistant_lines` is record-counted; after ADR-002 `turns_with_usage` is group-counted and
`outside_window` is incremented per **group** (the collapse precedes the filters). Mixing
those terms is what produces a value outside [0, 1]. So:

| counter | unit | meaning |
|---|---|---|
| `assistant_lines` | **records** | unchanged — the raw thing we read |
| `duplicate_records_collapsed` | **records** | records **dropped by grouping**: `Σ over groups (len(group) − 1)`. Not a residual — a residual would fold in `no_usage` and `foreign_cwd` skips and corrupt both this field and the denominator |
| `assistant_calls` (new) | **groups** | `assistant_lines − duplicate_records_collapsed` |
| `skipped_by_reason[*]` | **groups** | already post-collapse |
| `turns_with_usage` | **groups** | unchanged name, new unit |

```
denominator = assistant_calls - skipped_by_reason["outside_window"]
```

**Consequences:** coverage keeps meaning "did we price everything we saw" and stays
sensitive to a real format change. The gap between `assistant_lines` and
`turns_with_usage` is now explained by two named fields rather than being a mystery.

**AC-008 owns the verification.** An earlier draft mitigated this risk in the Risk
Register with "assert coverage ≈ 1.0 on the split fixture" and mapped it to no AC and no
exit criterion — a mitigation nobody owned. The second fixture, whose split group straddles
the window boundary, is the one that catches a record-vs-group mismatch; an all-in-window
fixture cannot.

**Alternatives rejected:** leaving coverage alone and documenting the new baseline — a
drift signal whose healthy value is 0.45 gets ignored, and the memory tier already records
what happens to signals nobody reads.

### ADR-005: the ledger writes one row per invocation, at the base root

**Status:** accepted

**Context:** the question the four dead months could not answer was "how often does
delegation fire?" — a rate needs both numerator and denominator. `codex_ledger` shipped
with `project_root=Path.cwd()`, which under the task-worktree model wrote into a gitignored
worktree path that vanished at `task-land`; the correction was to write at the base root
and to log **every** call rather than only the skips.

**A derivable brief is not a dispatch.** An earlier draft logged only
`wrapup_brief.main()` and claimed `ok ÷ total` was the signal AC-007 needs. It is not:
`status: ok` says the brief was derivable, and the dispatch happens *afterwards* and can
still not happen — the template self-skips it when the subagent tool is unavailable
(Cursor, Codex), and the model can simply not dispatch, which is what 14 of the 16
measured runs did for a different reason. Nothing in `wrapup_brief` can observe that. A
ledger built on derivability alone would go green the moment Phase 2 lands and reinstall
this defect's blind spot one level up. The 2-of-16 figure came from transcripts, not from
anything a brief-only ledger could see.

**Decision:** a new `delegation_ledger` module writing
`<base>/.claude/observability/delegation.jsonl`, base resolved through the existing
`resolve_base_root`, append-only, fed by **two** observation points:

| writer | when | row |
|---|---|---|
| `wrapup_brief.main()` | every invocation | `{ts, stage, slug, kind: "brief", status: ok\|degraded, reason}` |
| `wrapup_receipt.main()` | the dispatched path — the rendered stage reaches it only after a subagent reply exists | `{ts, stage, slug, kind: "dispatch", status: dispatched\|mismatch\|unparseable}` |
| `stages/wrapup.md.j2` self-skip branch | the IDE has no subagent-dispatch tool (Cursor, Codex) | `{ts, stage, slug, kind: "dispatch", status: unavailable}` |

The signal is then defined over **dispatch** rows, not `ok ÷ total`.

**Where each writer's `slug` comes from — they differ, and an earlier draft got the second
one wrong.** `wrapup_brief` takes it from **argv** (`--slug`): on the degraded path
`derive_brief` returns `brief=None`, so reading it from the brief would strip the identity
from exactly the rows that matter. `wrapup_receipt` has **no `--slug` flag and the rendered
line does not pass one**; it takes it from the `--worktree` it already resolves and
confines to `base/.worktrees/<slug>`, i.e. the resolved path's `.name` when it differs from
base, else `""`. Machine-derived, so no flag, no template change, and no re-render pulled
into a phase that does not own one.

**`dispatch ÷ brief-ok` is a lower bound, not a rate.** The reconciliation step that writes
the dispatch row is model-executed prose, so a run that dispatches and then skips
reconciliation leaves no row. (An earlier draft justified the writer with
"`--receipt-file` is `required=True`" — that is a non-sequitur: `required=True` only makes
argparse exit before any row is written. The real guarantee is the template's ordering.)

**Consequences:** the question the four dead months could not answer becomes computable.
Three writers means three places to keep in step; they share one module and one row schema,
and `kind` is what keeps them distinguishable. The ledger grows one short line per wrapup
in a directory that is already gitignored churn.

**The brief writer must fire on the `ok` path too, and that is the arm a test forgets.**
AC-006's first draft asserted only the degraded cases, so an implementation that logged
exclusively on failure would have passed while writing no denominator at all — the dispatch
rate then divides by nothing, in the one direction nobody inspects. AC-006 now carries the
success arm.

**Sequencing consequence:** the ledger module must exist before *any* of its three call
sites, including the template's. That reorders the phases — see the Implementation Plan.

**Alternatives rejected:** rows only on degrade (satisfies AC-006 but leaves the
denominator unknown — the exact hole this defect sat in); brief-only rows (the draft
above — measures the wrong event); renaming the signal to admit only derivability is
measurable (honest, but leaves "configured but never firing" invisible, which is the whole
point); reusing `codex_ledger` (different schema and stage vocabulary; coupling two
independent ledgers means a schema change to one perturbs the other).

### ADR-006: `delegation_fires` is a weight-0 display-only signal

**Status:** accepted

**Context:** `_dim_guardrails`' signal weights sum to 100. Adding a weighted signal
re-scores every existing harness's guardrails dimension, so a user who changed nothing
would see their health score move — indistinguishable from a real regression. The
dimension already carries three weight-0 display-only signals
(`autopilot_autoarm_registered`, `judgment_verdict_freshness`, `spec_need_forcing`) for
exactly this reason.

**Decision:** `delegation_fires` ships at `weight=0`, `hard_gate=False`. It reads
`delegation.stages` from `.claude/harness.yaml` (already read in this dimension) and the
ledger from `project_dir/.claude/observability/` — no transcript root, so ADR-009's
`Path.home()` prohibition is not engaged.

**A passing signal cannot carry a message — so both informational arms fail.** `Signal.action`
has exactly one consumer, `improvement._extract_layer1_actions`, and it is gated
`if sig.passed or sig.action is None: continue`. Nothing else in `src/` reads it and
`health.md.j2` never touches signals. An earlier draft resolved the absent-ledger case as
`passed=True` **with** an action — a string no surface renders, certified green by a test
reading the `Signal` object directly. That is a mechanism shipping inert with a test
vouching for it: the shape this whole work exists to end.

`_score_signals` computes `earned = sum(s.weight for s in signals if s.passed)`, so a
**failing weight-0** signal is already score-neutral, and `hard_gate=False` keeps it
non-gating. Failing is therefore the visible *and* harmless choice.

**Dispatch is impossible in some IDEs, and that is a different fact from "never dispatched".**
`stages/wrapup.md.j2` self-skips the subagent when the dispatch tool is unavailable
(Cursor, Codex). Those harnesses would otherwise accumulate brief rows and structurally
zero dispatch rows — arm 1 forever, on an action their user cannot satisfy. Per the user's
decision, the self-skip branch writes a `status: unavailable` dispatch row.

**Lifetime existence is the wrong question — the signal reads a recency window.** An
earlier draft passed on "≥1 non-`unavailable` dispatch row" anywhere in the file. The
ledger is append-only, so that goes green on the first successful dispatch and stays green
through every later regression: delegation could break again tomorrow and health would
report fine forever. That is this defect's blind spot rebuilt one layer further in, and a
cross-model reviewer caught it after three in-house rounds did not.

**Window (amended 2026-07-29):** the most recent **10** `kind: brief` rows **of any
status**, **for this stage**, plus every same-stage `kind: dispatch` row at or after the
oldest of those. Ordering is by **parsed timestamp**, not file position. A **brief** whose
timestamp will not parse is **excluded from the window before the slice**; an undatable
**dispatch** needs no special handling and falls out by comparison.

> **The first version said "brief, status: `ok`" and that was the bug.** Anchoring on `ok`
> briefs means the anchor stops being written by the very regression being detected: when
> the brief degrades, no new `ok` row is appended, the floor stays pinned to the last
> healthy era whose dispatch rows are still inside it, and the verdict reads `ok`
> indefinitely. Two review rounds passed that wording before a re-review traced it.
> Ordering was the second half: file order and timestamp order diverge under late writes,
> interleaved concurrent sessions, and a backward clock — and `Z` vs `+00:00` are the same
> instant that a string comparison ranks hours apart.
>
> **A first attempt at the corrupt-row rule was written here as fail-closed and was the
> exact inverse.** It said "sorting a corrupt row **oldest** is the fail-closed choice in
> both positions it can occupy … a corrupt brief stops widening the window." Sorting oldest
> is fail-closed for a *dispatch* (`_EPOCH >= floor` is false, so it drops out) and
> fail-**open** for a *brief*: an epoch-sorted brief survives the slice whenever the ledger
> holds few enough briefs, lands at index 0, becomes the floor, and admits **every** dispatch
> row in the file — maximally widening the window, not stopping it. One corrupt row was
> enough to restore lifetime-existence semantics. Briefs are therefore excluded, not sorted.
>
> **Stage scoping is the third half, and it was created by the first fix.** Anchoring on all
> brief rows made every brief load-bearing while the ledger was still stage-blind. `verify`
> is delegatable and its rendered line carries no `--slug`, so its briefs degrade
> structurally — a handful of verify runs would push a correctly-dispatching wrapup to
> `brief-degrading`, and a verify dispatch row would vouch for a wrapup that never
> dispatched.

| `delegation.stages` names wrapup | ledger, over that window | verdict |
|---|---|---|
| yes | no brief rows at all | `passed=False` + action "no invocation recorded yet" |
| yes | briefs **all `degraded`**, zero dispatch rows | `passed=False` + action "the brief is not derivable" |
| yes | ≥1 `ok` brief, **zero** dispatch rows | `passed=False` + action "dispatch is not happening" |
| yes | dispatch rows, **all** literally `unavailable` | `passed=True`, N-A |
| yes | ≥1 non-`unavailable` dispatch row | `passed=True` |
| yes | recent dispatch with an **unrecognised** status | `passed=False` (fail-closed) |
| no | any | `passed=True`, no action, no score effect |

Arm 3 covers "never fired" and "fired once, then stopped" together — same observation, same
remedy. The **three** failing arms must emit **different** action strings ("run wrapup
once" / "the brief is not derivable" / "your dispatches are not happening") and AC-007
asserts all three are distinct. They point at three different places, and sending someone
to the wrong half of the seam is how a signal stops being read.

An unrecognised dispatch status is `passed=False` rather than falling through to the
`unavailable-only` **pass** it used to reach. `unavailable-only` is the one arm that turns
this signal green on the strength of a status string, so it must require explicit evidence
that every recent dispatch was a self-skip; anything else is unevaluable, and unevaluable
is not a pass. The CLI's `--status` carries `choices` so a template typo fails loudly at
the writer instead of producing a row the reader has to guess about.

**Detection floor — user decision, 2026-07-29 (option 1 of 3 offered).** `ok` requires only
that *some* dispatch row sits in the window, so intermittent dispatch — including the
2-of-16 regime that motivated this work — reads green. Counting instead of existence was
offered and declined: ADR-005 makes `dispatch ÷ brief-ok` a lower bound (reconciliation is
model-executed and can be skipped), so any threshold strict enough to catch 2-of-16 would
redden healthy harnesses, and no non-arbitrary threshold existed. The signal therefore
catches "broke and stayed broken" and misses "works one time in ten". Re-opening this needs
a measurement that does not exist yet: how often a real dispatch skips reconciliation.

**Consequences:** it surfaces as an action item without docking a score or forcing a
migration. It cannot *fail* a health run, which is the accepted cost — visibility was the
stated requirement, and four months of green while delegation was dead is what needs
fixing, not the arithmetic of the score.

**Alternatives rejected:** a weighted signal (score migration across every harness);
`hard_gate=True` (floors the dimension to 0 for a non-safety condition).

### ADR-007: the record is corrected in this work unit

**Status:** accepted

**Context:** `work-docs/RESEARCH-context-carry-economics-2026-07-28.md` and two wiki
memories state absolute dollars that this change proves ~2.15× too high, and
`[wiki:architecture] carry-is-a-main-loop-phenomenon` states that delegation "reduces what
is ADDED, not what is already in the prefix" — true of ctx/turn, false of carry, which is
ctx/turn × calls.

**Decision:** Phase 5 corrects all three, with the correction dated and its cause named,
in the same style as the RESEARCH document's existing 2026-07-28 correction block. The
ordinal findings are re-affirmed rather than deleted: they survive the change of unit.

**Consequences:** the next reader of either artifact gets the corrected number and the
reason. The alternative — leaving known-false figures in the document the next stage
reads — is how the first mixed-weighting error propagated.

## 📝 Implementation Plan

### Phase 1: collapse split records at ingestion

**Scope:** `src/harness_maker/economics.py` (`TurnRecord.message_id`),
`src/harness_maker/economics_source.py` (grouping in `load_turns`,
`duplicate_records_collapsed` + `assistant_calls`, `coverage` denominator),
**four** fixtures — split group, no-split sibling, split group straddling the window, and
a group whose records disagree on `attributionSkill` (see Test Strategy) —
`tests/unit/test_economics_dedupe.py`
**Depends on:** none
**Parallel group:** A
**Merge hazards:** none — no other phase touches these two modules
**Exit criterion:**
`uv run pytest tests/unit/test_economics*.py tests/unit/test_run_classify*.py tests/unit/test_cache_diagnostics*.py -q`
— the last two are the consumers ADR-002's earlier draft failed to name, and
`run_classify` is where the boundary damage would land
**Implementation note — the one place ADR-004's arithmetic breaks silently:**
`duplicate_records_collapsed` must be summed over **all** groups, including those later
skipped as `no_usage` / `foreign_cwd` / `outside_window`. Sum it only over surviving groups
and `assistant_calls` stops equalling the group count, which puts the coverage denominator
quietly off by the skipped groups' duplicates.
**Also check before writing the new fields:** `duplicate_records_collapsed` and
`assistant_calls` enter the shipped JSON of both `report` and `doctor` via
`diag.model_dump(mode="json")`. If a parity or snapshot test enumerates that payload's
keys, it must be extended — and note the CLAUDE.md precedent where a name-only comparison
was invariant to the value it was supposed to pin
**Risk:** ADR-003's field-source rule is where a subtle wrong answer hides; a collapse that
passes the turn-count assertion can still silently drop `written_paths`, move
`find_boundaries`' boundary set, or invalidate the verdict cache
**Fixture materialization (saves an iteration):** `load_turns` never reads a flat file —
`discover_transcript_dirs` only accepts child directories named `encode_project_dir(root)`
or prefixed `<name>--worktrees-`, so the fixtures must be copied into an encoded directory
under a tmp transcript root. Second trap in the same place: a fixture record carrying a
real `cwd` is dropped as `foreign_cwd` against a tmp project path — rewrite `cwd` at
materialization time, as `tests/unit/test_economics_composition.py` already does
**Rollback:** the change is confined to `load_turns`' inner loop and one model field;
reverting the grouping restores record-counting exactly

### Phase 2: delegation ledger — must precede every call site

> **Reordered.** This was Phase 3 until a cross-model reviewer pointed out that the
> template's `unavailable` writer sat in the seam phase while the module it calls did not
> exist until after it. The module has no dependencies of its own; every call site has one
> on the module. It goes first.

**Scope:** `src/harness_maker/delegation_ledger.py` (new — module, row schema, base-root
resolution, the window reader Phase 4 consumes),
`src/harness_maker/wrapup_receipt.py` (the `kind: "dispatch"` row from `main()`),
`tests/unit/test_delegation_ledger.py`
**Depends on:** none
**Parallel group:** A
**Merge hazards:** none — the brief-row call site lands in Phase 3 with the `--slug` it
needs for the row's identity, so this phase does not touch `wrapup_brief.py`
**Exit criterion:** `uv run pytest tests/unit/test_delegation_ledger.py tests/unit/test_wrapup_receipt*.py tests/structural -q`
— `tests/structural` because this phase adds a new module and `command_registry.py`
enumerates them (`wrapup_brief` / `wrapup_receipt` are registered `flagonly`); check
whether any structural test asserts registry completeness **before** writing the module
**Risk:** writing to the wrong root repeats the `codex_ledger` defect — the test must
assert the file lands at the **base** when called from a cwd inside a worktree
**Ordering trap in `wrapup_receipt.main()`:** it returns early on an unreadable receipt
file and on a parse failure, both **before** `--worktree` is resolved — which is where
ADR-005 gets the slug. Resolve `ns.worktree` at the top of `main()`, or the `unparseable`
rows land slug-less on exactly the paths they exist to record
**Rollback:** delete the module and its one call site — nothing reads it until Phase 4

### Phase 3: give the brief a slug-derived identity

**Scope:** `src/harness_maker/wrapup_brief.py` (`--slug`, base-root worktree resolution),
`src/harness_maker/templates/stages/wrapup.md.j2` — **note the path**: an earlier draft
said `templates/commands/hm/wrapup.md.j2`, which does not exist, though
`templates/commands/hm/` does, so the mistake would have produced a new inert file rather
than an error — the Step 0.5 block is the target; the self-skip branch's `unavailable`
ledger row (ADR-005) lands here too, because this is the phase that owns the re-render;
`src/harness_maker/templates/commands/hm/metrics.md.j2` (its `ingestion.coverage`
description becomes wrong under ADR-004, and correcting it triggers the same re-render);
`src/harness_maker/wrapup_brief.py`'s `kind: "brief"` ledger row, which lands here rather
than in Phase 2 because its `slug` comes from the `--slug` this phase adds;
re-render; `tests/integration/test_wrapup_brief_rendered_argv.py` and the AC-009 test that
**executes the rendered self-skip line** and asserts an `unavailable` row at the base
ledger — a prose branch that claims to record something records nothing, and no
fixture-built ledger can reveal that
**Render preconditions for AC-004 (each costs an iteration to rediscover):** the hermetic
render's config must set `delegation.stages` to include `wrapup`, or the Jinja guard elides
the whole Step 0.5 block and the `!`-line extraction finds nothing; and the extraction must
target the brief line specifically, since the receipt line is adjacent and similar
**Depends on:** Phase 2 (its two ledger call sites need the module)
**Parallel group:** serial
**Merge hazards:** re-rendering touches the whole rendered command surface and its
snapshots. What `[fail:test] snapshot-regen-inside-worktree` (count 13) actually guards is
the **HOME / install-ref pin and the `src`-path frontmatter**, not a cwd — and "regenerate
from base" would be wrong here anyway, since the template edit exists only in this
worktree and a base render would emit the OLD command with no `--slug`, leaving AC-004
testing the wrong artifact. Regenerate here, with the pin, and audit **which** snapshot
entries moved rather than accepting that some did
**Exit criterion:**
`uv run pytest tests/integration/test_wrapup_brief_rendered_argv.py tests/render tests/snapshot tests/structural -q`
— `tests/snapshot` because snapshot churn is this phase's own declared hazard, and
`tests/structural` because a new `!`-line argument is exactly what the rendered-command
gate (`test_no_positional_params_in_commands.py`, CLAUDE.md checkpoint 2) exists to catch
**Risk:** the integration test needs a real temporary git repo with a real linked
worktree; a mocked git would let the base-cwd bug pass, which is the failure this AC exists
to prevent
**Rollback:** revert `wrapup_brief.py` and re-render; the `--slug` flag is additive so an
un-re-rendered harness keeps working

### Phase 4: `delegation_fires` health signal

**Scope:** `src/harness_maker/readiness.py` (`_dim_guardrails`),
`tests/unit/test_readiness_delegation.py` with **five** fixture project trees per
ADR-006's table (no ledger; brief-ok rows with no dispatch; all-`unavailable` dispatch;
a successful dispatch followed by >10 later brief-ok rows and none since; unconfigured)
**Depends on:** Phase 3
**Parallel group:** serial
**Merge hazards:** `_dim_guardrails`' weight sum is an invariant; ADR-006 keeps it at 100
by shipping at weight 0
**Exit criterion:** `uv run pytest tests/unit/test_readiness*.py -q`
**Risk:** two arms decide by reflex if left unstated — the absent-ledger case (every
harness on day one) and the no-dispatch-tool case (every Cursor / Codex harness). ADR-006
decides both. The test asserts the two failing arms' action strings are **different**,
because identical text makes remedies indistinguishable, and asserts the `unavailable`-only
arm passes, because a permanently-red action nobody can clear is the "signal nobody reads"
outcome (`absent-case = feature black hole`, count 8)
**Rollback:** remove the signal; no other signal's weight changes

### Phase 5: correct the record

**Scope:** `work-docs/RESEARCH-context-carry-economics-2026-07-28.md`,
`.claude/memory/wiki.md` (two entries), `CLAUDE.md` (its Step 7.5 reference names the
non-existent `templates/commands/hm/wrapup.md.j2` — the same wrong path that would have
cost Phase 2 an iteration)
**Depends on:** Phase 1
**Parallel group:** serial
**Merge hazards:** `wiki.md` is marker-bearing — edit **inside** `<!-- @hm:user:entries -->`,
never at EOF (`[fail:render] wrapup-eof-append-outside-marker`, count 3)
**Exit criterion:** run the shipped implementation **against the frozen corpus** and
compare with the pre-registered figures:

```bash
uv run python -m harness_maker.economics report --root . \
  --transcript-root ~/.cache/harness-maker/frozen-corpus-2026-07-28 --days 3650
```

Expected: **8,682** main-loop billed calls, **$2,150** total, **79.2%** carry, `hm:wrapup`
**$339 / $294 carry**, and `24,082 - 10,942 = 13,140` collapsed records. Plus
`uv run pytest tests/integration/test_memory_retrieve_cli.py -q` green (the close-marker
regression is invisible to the unit suite).

> **Two earlier drafts of this criterion were unevaluable, in different ways.** The first
> required "the figures quoted in the RESEARCH correction block match the report" — but
> that block is authored in this phase *from that report*, so it passed by construction.
> The second pinned absolute figures against `economics report` over the **live** corpus:
> `window_days: 30` with a lower-bound-only filter (`turn.ts < cutoff`) means every session
> spent on Phases 1–4 enters the window, so the totals grow and the figures cannot
> reproduce — and `--now` does not help, because there is no upper-bound comparison to
> move. The corpus is therefore frozen (done at plan time, since by Phase 5 it is too
> late) and both `--transcript-root` and a `--days` wide enough not to clip are passed.
>
> The reference figures come from `tests/manual/oracle_dedupe_reference.py`, which is not
> the shipped code. A mismatch means the shipped collapse differs from the measured one —
> which is exactly what this phase needs to be able to detect.
**Risk:** editing a large document by full rewrite duplicates it in the context — use
`Edit` on the specific blocks
**Rollback:** `git checkout` the two files

### Execution notes — two things the plan did not anticipate (2026-07-29)

**1. Phase 3 forced a re-base of `_ADR014_CEILING` (scope expansion, stated).** The
rendered `exec-rev-wrap-ver.md` budget constant was 119,000 with **53 characters** of
headroom. AC-004 and AC-009 require two new `!` lines totalling ~190 rendered characters,
so **no implementation of this SPEC fits under it** — trimming prose cannot help, because
the mandatory command surface alone overruns the margin. The constant's own docstring
already flagged it as stale and asked for a re-derivation. Both of ADR-014's anchors
(121,782 pre-pruning size, 5,706 saved) are historical and not re-measurable — pruning was
a one-time prose reduction, not a render flag — so what was re-applied is the rule's shape,
`post-pruning size × 1.02`: measured 119,765 → 122,160 → rounded **down** to **122,000**
(ADR-014 rounded its own figure up). Prose was tightened first (−301 chars) so the new
constant is not padded by verbosity. This is the one edit outside the PLAN's stated scope.

**2. Phase 5's exit criterion did not reproduce, and the reason is not the collapse.** The
pre-registered figures came from `tests/manual/oracle_dedupe_reference.py`; the PLAN said a
mismatch "means the shipped collapse differs from the measured one". That inference is too
strong. Against the frozen corpus the shipped `economics report` gives:

| quantity | pre-registered | shipped | verdict |
|---|---:|---:|---|
| main-loop billed calls | 8,682 | **8,682** | exact |
| main-loop carry $ | 1,704 | **1,704** | exact |
| records collapsed | 13,140 | **13,137** | see below |
| main-loop total $ | 2,150 | 2,278 | explained |
| `hm:wrapup` $ / carry | 339 / 294 | 411 / 348 | different population |

The two quantities the collapse actually determines — the call count and the cache-read
dollars — agree **exactly**. The total differs because the oracle prices every
cache-creation token at the 5-minute rate while the shipped `PRICE_TABLE` splits 5m/1h
(1.6× on opus-5); `hm:wrapup` differs because the shipped `by_stage` includes subagent
turns attributed to the stage while the oracle's per-stage table is main-loop only. The
collapsed count differs by exactly 3 because the PLAN subtracted the count of *globally
distinct* `message.id`s (10,942) while the SPEC's own text records 10,945 — the 3 extra are
the ids that genuinely recur across different `subagents/agent-*.jsonl` files, which is the
observation that motivated ADR-002's within-file rule. **The SPEC figure is correct and the
PLAN's subtraction was stale**; `24,082 − 10,945 = 13,137` is what shipped.

**3. "Re-render" does not mean what the phase scope implied, and the dogfood was NOT
re-rendered.** Checked rather than assumed: `.claude/commands/hm/wrapup.md` is **untracked
by git** and its `!` lines pin
`$HOME/.claude/plugins/cache/harness-maker/harness-maker/0.43.3` — this repo's own harness
is rendered from the **installed plugin release**, not from this source tree. So there is
no re-render this work unit can perform that makes the fix live here; it reaches the
dogfood only after a version bump, a release, `/plugin update`, and
`/harness-maker:make --update`. Until then **harness-maker's own `/hm:wrapup` keeps
degrading, and its `delegation_fires` signal reads `no-rows`** — correctly, since the
ledger has no rows yet. What IS verified is the template, by the AC-004/005/009 tests,
which render hermetically from this tree and execute the result.

**4. The declared snapshot hazard DID materialise, and the exit criterion could not see
it.** `tests/snapshot/` holds goldens, not tests — the test that reads them is
`tests/unit/test_synthesize_snapshot.py`. So Phase 3's exit criterion (which names
`tests/snapshot`) passed green while 8 golden mismatches sat in `tests/unit`, and they
surfaced only in the full suite. The goldens store a `body_sha256` per rendered file, so
the audit the hazard note asked for is possible and was done: **exactly one entry moved in
each of the 8 goldens — `commands/hm/metrics.md`**, the one file this phase edited whose
template renders unconditionally. `stages/wrapup.md.j2` moved nothing because the fixture
configs leave `delegation.stages` empty, so the Jinja guard elides the whole Step 0.5
block. Regenerated via `tests/snapshot/regenerate.py`, which is one of the two places that
pins HOME and the install ref (`[fail:test] snapshot-regen-inside-worktree`, count 13).

**5. A second budget gate, and this one was met by trimming rather than re-basing.**
`test_render_wrapup_delegation.py::test_delegation_adds_a_bounded_amount_of_prose` caps the
Step 0.5 block at **+60 body lines**; it stood at 59. The new fenced `!` line costs ~5 lines
on its own, so this gate was also unsatisfiable as-is — but unlike ADR-014 the shortfall was
small enough to pay for honestly, by compressing 8 lines of genuine redundancy already in
the block (the receipt-collision paragraph, the exit-code bullets, the inline-body preamble).
The gate's own message asks for exactly that. The block now sits **at** its ceiling: the next
addition to Step 0.5 must be paid for the same way.

## 🧪 Test Strategy

| SPEC scenario | AC | test file | mode |
|---|---|---|---|
| S1 one call is one turn | AC-001 | `tests/unit/test_economics_dedupe.py` | unit, fixture transcript |
| S2 collapse count is reported | AC-002 | `tests/unit/test_economics_dedupe.py` | unit, two fixtures |
| S3 collapse preserves ctx, divides carry | AC-003 | `tests/unit/test_economics_dedupe.py` | property (Hypothesis, `ci` profile) |
| S4 rendered argv resolves | AC-004 | `tests/integration/test_wrapup_brief_rendered_argv.py` | integration, real git worktree |
| S5 standalone still degrades | AC-005 | `tests/integration/test_wrapup_brief_rendered_argv.py` | integration, real git repo |
| S6 one ledger row per invocation, ok **and** degraded | AC-006 | `tests/unit/test_delegation_ledger.py` | unit, tmp project root |
| S7 health fails a dead delegation | AC-007 | `tests/unit/test_readiness_delegation.py` | unit, **five** fixture trees |
| S8 drift signal survives | AC-008 | `tests/unit/test_economics_dedupe.py` | unit, window-straddling fixture |
| S9 the rendered self-skip writes its row | AC-009 | `tests/integration/test_wrapup_brief_rendered_argv.py` | integration, extracted-and-executed render line |

**Fixture contract.** The split-record fixture holds one 3-record group and one singleton,
so the expected turn count (2) is distinguishable from the pre-fix answer (4) *and* from a
collapse that merged everything (1). The `tool_use` block sits in the group's **middle**
record and the max-`output_tokens` record is the **last**, so a keep-last collapse drops
`written_paths` and a keep-first collapse drops the final usage — both must fail. Because
the measured artifact's records carry byte-identical usage, the fixture deliberately does
**not**: one group varies `output_tokens`, or ADR-003's max rule ships unexercised.

**Two further fixtures.** A no-split sibling pins AC-002's zero case, and a fixture whose
split group straddles the `--days` window pins AC-008 — the only shape in which ADR-004's
record-vs-group unit mismatch is observable.

**One assertion is a claim-check, not a scenario — and it needs a fixture built to make it
bite.** ADR-003 asserts the verdict cache and the boundary set survive the collapse. Phase 1
pins it: `find_boundaries` over the collapsed turns must yield the same boundary uuids as
the pre-collapse first-record uuids.

Over the three fixtures above that assertion is **vacuous**. `find_boundaries` opens a run
only where `_attributed(i)` is False, reading `turns[i].attribution_skill`, and the boundary
uuid is the stretch's first turn's `uuid`. If every record in a group agrees on
`attributionSkill` — as they do in all three — each stretch necessarily begins at a group's
first record and both the uuid and the boundary set are preserved *by construction*. The
assertion would pass and then be recorded as having demonstrated the claim, which is the
"assert rather than demonstrate" failure ADR-003 itself warns against.

**Fourth fixture, specified to disagree:** one group whose first record carries
`attributionSkill: null` and whose second carries a non-null value, plus a stretch that
pre-collapse begins at a **non-first** record of a group. Then either the boundary set is
unchanged (the claim holds) or the migration branch fires and ADR-003's Consequences are
rewritten. Those are the only two acceptable outcomes; relaxing the assertion is not one.

**No live transcripts.** Every test reads fixtures under `tests/`; the developer's
`~/.claude` is never a test input, and the install-ref pin conftests already in
`tests/{unit,render,structural,snapshot}` keep the render side off this machine.

## ⚠️ Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| collapse drops `written_paths`, silently re-labelling PRODUCE/REWORK as OTHER | high | high — corrupts the classifier the economics model is built on | ADR-003 union rule; fixture places `tool_use` in a record that both naive rules discard |
| `coverage` falls to ~0.45 and the ADR-009 drift signal is retired by always being red | high | medium | ADR-004 moves the denominator; assert coverage ≈ 1.0 on the split fixture |
| `uuid` winner varies between runs, invalidating the verdict cache every time | medium | medium | ADR-003 pins identity fields to the first record in file order |
| collapsing merges an attribution change, so `run_classify.find_boundaries` loses a boundary and the span report degrades to unattributed | medium | **high** — the attributed-stage figures this work is built on | Phase 1's boundary-uuid assertion; `run_classify` tests added to the exit criterion. If the assertion cannot hold, ADR-003's no-migration claim is rewritten rather than the test relaxed |
| the ledger measures brief-derivability, so the health signal goes permanently green while the subagent is still never dispatched | was **certain** in the first draft | high | ADR-005's second writer in `wrapup_receipt.main()`, which runs iff a subagent replied; AC-007's failing arm is unreachable from brief rows alone |
| the absent-ledger arm is resolved by reflex, making the signal either always-red or N-A for the very project it targets | high | medium | ADR-006 decides all five arms; both informational arms fail (score-neutral at weight 0) and the test asserts their action strings differ |
| a `passed=True` arm carries an action no surface renders, so the signal ships inert while its test certifies it green | was **certain** in the second draft | high | verified: `Signal.action`'s only consumer is gated on `sig.passed`. ADR-006 fails both informational arms instead |
| every Cursor / Codex harness sits permanently red on an action its user cannot satisfy | high | medium | the self-skip branch writes a `status: unavailable` dispatch row; ADR-006's arm 3 makes the signal N-A on that evidence |
| the boundary-uuid assertion passes trivially and is recorded as having demonstrated ADR-003 | high | high — it is the only check on the cache/classifier claim | a fourth fixture whose group records **disagree** on `attributionSkill`; without that shape the assertion is preserved by construction |
| delegation works once, then breaks, and the signal stays green forever on an append-only ledger | high | **high** — it is the exact failure this work exists to detect | ADR-006's 10-brief (any-status) recency window; AC-007's `dispatched_long_ago_then_stopped` arm. Found by the cross-model reviewer after three in-house rounds missed it |
| the brief writer logs only failures, so the dispatch rate divides by nothing | medium | high | AC-006's success arm — the degraded-only predicate passed this by construction |
| the `unavailable` row is scheduled before the module it calls, and its rendered branch is never executed by a test | was **certain** in the third draft | medium | ledger module reordered to Phase 2; AC-009 extracts and runs the rendered self-skip line |
| re-render churn moves every command snapshot, hiding the real diff | high | low | regenerate from base only; audit *which* snapshot entries changed, not just that they did |
| `delegation_fires` at weight 0 is too quiet to be noticed | medium | medium | accepted (ADR-006); it lands in dashboard action items, and the ledger makes the rate computable on demand |
| every previously quoted dollar figure becomes wrong mid-flight | certain | low | S2 labelling + Phase 5; the ordinal findings are unaffected and are re-affirmed rather than restated |
| a `--slug` whose worktree is absent degrades and looks like the old bug | medium | low | distinct reason string; the ledger records it, so the two are separable after the fact |

## ❓ Open Questions

None blocking. One deferred item, recorded so it is not lost: the **51 → ~14 main-loop
calls** figure is arithmetic over the rendered command's structure, not an observed delta,
and the delegated sample is n=2. The corrected meter plus the ledger make the real number
answerable after a handful of wrapups; no phase depends on it.
