---
type: plan
task_slug: economics-attribution-and-carry
status: complete
created: 2026-07-26
tags: [harness-maker, plan, python, economics, observability, attribution, subagent]
interview_rounds: 4
adrs: 12
validator_outcome: MAJOR_REVISION_RESOLVED_SELF_REVIEWED
summary: "Fix stage attribution where it is reachable, and cut inherited context in wrapup/verify"
---

# PLAN — Economics attribution recovery + carry reduction

> **Scope note.** This plan was validated twice. The second pass returned
> MAJOR_REVISION with five new critical findings, all confirmed against the code
> by the author. The validator's re-run budget (one) was spent, so this revision
> narrows scope to what the mechanism can actually reach, names every exemption,
> and was closed by self-review in the validator's place. Every place the first
> two drafts over-claimed coverage is now a stated bound, not a promise.

## 🎯 Executive Summary

**TL;DR** — `/hm:metrics` Step 5 reports 59% of measured spend ($6,917 of
$11,736 list-price equivalent) in an `(unattributed)` bucket at 11.2% estimator
coverage, and 82% / 83% cache-read carry on `hm:wrapup` / `hm:verify`.
Investigation showed **both numbers had the wrong cause attached**. This plan
fixes the measurement where it is reachable, then removes the inherited context.

**What** — Two workstreams:

1. **Attribution recovery.** Claude Code drops `attributionSkill` the moment the
   user speaks mid-stage. Every AskUserQuestion answer, every `진행해`, every
   `<task-notification>` starts a new unattributed run. Stage costs are
   *floors*, and `(unattributed)` is mostly stage work.
2. **Carry reduction.** `hm:wrapup` and `hm:verify` are not expensive *stages*;
   they run *last*. They inherit 94% / 99% of their context before doing any
   work. Their bodies move into a dedicated subagent driven by a compressed
   brief, behind a default-off config key.

**Where the forward ledger does and does not reach** — stated up front because
two drafts got this wrong:

| Population | Forward ledger | Falls back to |
|---|---|---|
| `feature_branch_workflow: true` stages (Production default) | ✅ per-stage spans | — |
| `/hm:loop` iterations | ⚠️ **iteration-level only**, no per-stage granularity | inference + adjacency within the iteration |
| `feature_branch_workflow: false` harnesses (Side default) | ❌ **exempt** | inference + adjacency |
| Cursor / Codex targets | ⚠️ no session-end closure hook | next-start or cap |

**Key decisions** — [ADR-001](#adr-001) hybrid recovery, source-labelled ·
[ADR-008](#adr-008) spans emit from a load-bearing CLI call, with named
exemptions · [ADR-009](#adr-009) sidechain spans nest; **per-source**
conservation only · [ADR-010](#adr-010) ledger at the base root ·
[ADR-003](#adr-003) close rule with measured caps · [ADR-002](#adr-002)
whole-stage delegation with a runtime self-skip · [ADR-011](#adr-011)
config-gated, default-off · [ADR-004](#adr-004) git/land stays in the main loop
**as instruction, not enforcement** · [ADR-007](#adr-007) dedicated agent ·
[ADR-006](#adr-006) brief contract with a reachable degraded path ·
[ADR-012](#adr-012) machine receipt · [ADR-005](#adr-005) LLM-once cached
classification.

---

## 🚫 Non-Goals

1. **Per-stage attribution inside `/hm:loop`.** The loop explicitly instructs
   stages to skip `task-preflight` (`loop.md.j2:990`), so no per-stage emission
   point exists there. [ADR-008](#adr-008) gives loops iteration-level spans
   instead. Finer granularity would mean redesigning the loop's isolation.
2. **Per-stage forward ledger for `feature_branch_workflow: false` harnesses.**
   Six of seven stages have no mandatory CLI call in that configuration.
   > **Corrected during Phase 2 — this was overstated.** `execute` is the exception:
   > its flag-off path renders `worktree create execute`, which *is* a mandatory call
   > and *does* emit (`stage: "hm:execute"`). So flag-off harnesses get **execute-only**
   > coverage, not zero. The earlier "emits nothing" wording was contradicted by the
   > implementation and by the e2e suite at the same time; the code is right and the
   > Non-Goal was wrong. The other six stages remain uncovered there.
3. **Incremental memory capture across the other five stages** (rejected as the
   entry point in [ADR-002](#adr-002)).
4. **Re-classification of already-cached retroactive verdicts.**
5. **Any change to pricing, `resolve_model_family`, or the existing
   `estimate_attribution` adjacency path** — adjacency remains the fallback.
6. **Making `by_agent` a partition.** It is a cross-cut by design
   (`economics.py:418-422` accumulates a turn into both `by_stage` and
   `by_agent`); changing that would break every existing consumer. See
   [ADR-009](#adr-009).
7. **Delegating any stage other than wrapup and verify.**
8. **Automated quality scoring of memory entries.** [ADR-012](#adr-012) receipts
   record *what happened*, never *how good it was*.
9. **Retiring `.claude/hooks/hooks.json`.**

---

## 📚 Prior Work

- **`[wiki:architecture] harness-economics-observability` (2026-07-25)** — ships
  the spend model this plan repairs. Binding:
  - **No cost ÷ deliverable-count metric, ever.** Every field added below is a
    sum or a count, never a quotient of the two; `ratio_field_kinds()` scans the
    real schema incl. `@property`.
  - **Every attribution bound must be able to reject.** [ADR-003](#adr-003)'s
    caps are now calibrated from a measured distribution.
  - **Pricing is per-turn from the turn's own `message.model`.** Untouched.
- **`[fail:test] assertion-invariant-over-named-dimension`** — assertions
  pinning a *relation* where the contract specifies a *value* pass in the broken
  world too. Every assertion below names the wrong implementation it rejects,
  and the cap and brief tests carry positive controls.
- **Learned correction 2026-06-08 — "absent-case = feature black hole"**
  (count:8). Applied to the absent span **start** ([ADR-003](#adr-003)), the
  absent `$HM_SESSION_ID` ([ADR-008](#adr-008)), the absent brief field
  ([ADR-006](#adr-006)), and the absent classifier verdict
  ([ADR-005](#adr-005)).
- **CLAUDE.md §보안** — subagent frontmatter `permissions:` is silently ignored;
  `tools:` is the only enforced boundary. This killed the first draft's
  ADR-004/007 pairing — see [ADR-004](#adr-004).
- **CLAUDE.md checkpoint 6 (bidirectional mapper)** — `InterviewAnswers` is
  `extra='forbid'`, and every comparable config block carries an explicit mirror
  (`feedback`, `second_opinion`, `delivery_metrics`, `economics` in
  `models.py`). A new key without one is silently dropped on re-render.
- **CLAUDE.md ledger precedent** — `codex_ledger.main()`'s `project_root=Path.cwd()`
  wrote into a gitignored worktree path and was lost at `task-land`. The fix
  exists as `second_opinion_invoke.resolve_base_root()` (`:110`), whose docstring
  records that `--show-toplevel` returns the *worktree* in a linked worktree.
  [ADR-010](#adr-010) reuses it.
- **`telemetry.py:199-216`** — the house atomic-append pattern (`O_APPEND` + a
  single `os.write()`, POSIX-atomic below `PIPE_BUF`). Reused verbatim.
- **`memory_md._base_root()` (`:71-90`)** — already strips a trailing
  `.worktrees/<name>`, so `--root .` resolves to BASE from inside a task
  worktree; `wrapup.md.j2` already folds base memory into the squash via
  `commit-base-memory --expect-head`. This **refutes** "a delegated wrapup loses
  memory at `task-land`".
- **`stage_end_summary.md.j2:24-28`** — the runtime self-skip precedent ("If the
  `Skill` tool is unavailable … this section is a NO-OP"). [ADR-002](#adr-002)
  reuses this shape instead of a per-target render branch that has no branch
  point.
- **`[wiki:convention] harness-maker-invocation-launcher`** — every executable
  invocation must use the full
  `uv run --with {{ harness_maker_src_path }} python -m harness_maker.<module>`
  launcher.

### Evidence gathered during this plan (measured, not assumed)

172 local transcript files, 18,135 priced assistant turns.

| Measurement | Value |
|---|---|
| turns carrying `attributionSkill` | 8,005 (44.1%) |
| unattributed runs | 144 (median 45 turns, **max 796**) |
| runs longer than the current `adjacency_max_turns=20` | 99 runs = **95% of unattributed turns** |
| files that never set `attributionSkill` | 45 (2,198 turns) |
| **sidechain (subagent) priced turns** | **3,943** |
| … carrying `attributionAgent` | **3,943 (100.0%)** |
| … also carrying `attributionSkill` | 2,089 (53.0%) |

User text immediately preceding the longest unattributed runs:

| run | preceding stage | user text |
|---:|---|---|
| 796 | `hm:wrapup` | `A로 진행해` |
| 400 | `hm:execute` | `continue` |
| 314 | `hm:wrapup` | `진행해` |
| 303 | `harness-maker:make` | `두 줄 지우고 1번으로 진행해` |
| 240 | `hm:review` | `<task-notification>` |
| 183 | `hm:execute` | `autopilot 켜고 해` |

Entry-vs-exit context per stage (main-loop turns only, median over runs):

| stage | runs | turns | entry ctx | exit ctx | grown in-stage |
|---|---:|---:|---:|---:|---:|
| `hm:wrapup` | 20 | 1,283 | **439k** | 464k | **+26k** |
| `hm:verify` | 7 | 174 | **357k** | 361k | **+4k** |
| `hm:review` | 20 | 1,033 | 366k | 422k | +56k |
| `hm:execute` | 18 | 1,593 | 227k | 334k | +106k |
| `hm:plan` | 17 | 831 | 131k | 182k | +52k |
| `hm:research` | 12 | 445 | 70k | 116k | +46k |

**Cap calibration** — run-length CDF, **144 runs / 10,249 turns** (a first
version of this probe mis-handled the first run of each file; the numbers below
are the corrected full-corpus figures):

| cap | captured | lost | runs over cap |
|---:|---:|---:|---:|
| 200 | 8,612 (84.0%) | 1,637 | 12 |
| 300 | 9,430 (92.0%) | 819 | 7 |
| **400** | **9,853 (96.1%)** | **396** | **1** |
| 800 | 10,249 (100%) | 0 | 0 |

Run **duration**, over the **same complete 144-run set** (an earlier partial
figure over 71 runs is superseded; 0 runs lack usable timestamps):

| p50 | p75 | p90 | p95 | p99 | max |
|---:|---:|---:|---:|---:|---:|
| 7.6 min | 32.7 min | 84.3 min | 179.1 min | 485.2 min | 615.4 min |

Runs over 60 min: 21 (14.6%) · over 120 min: 9 (6.2%) · **over 240 min: 4
(2.8%)** · over 480 min: 2 (1.4%). The 240-minute cap sits between p95 and p99.

### Hypotheses refuted during planning (recorded so they are not re-derived)

- *"The 59% is work done outside `/hm:` commands."* False — the runs begin with
  mid-stage continuations, and 95% exceed the estimator's own cap.
- *"`hm:verify`'s carry comes from being fused into `exec-rev-wrap-ver`."*
  False — no fused-workflow stage name appears in the data; all 174 turns were
  standalone. The carry is inherited session context.
- *"A delegated wrapup writes memory into the worktree and loses it."* False —
  `memory_md._base_root()` already resolves to BASE.
- *"Subagent spend becomes untraceable once delegated."* False — 100% of
  sidechain turns carry `attributionAgent`.
- *"Emission from `task-preflight` covers every invocation path."* **False, and
  this plan asserted it in two drafts.** `loop.md.j2:990` orders stages under
  `/hm:loop` not to run it, and the preflight partial is included only inside
  `{% if …feature_branch_workflow %}` in all seven stages. Both are now stated
  exemptions ([ADR-008](#adr-008), Non-Goals 1–2).

---

## 🎙️ Interview Transcript

| # | Round | Topic | Category | Choice | → ADR |
|---|---|---|---|---|---|
| 1 | 1 | Retroactivity scope | Scope boundaries | **hybrid** — both paths, source-labelled | ADR-001 |
| 2 | 1 | Inherited context | Architecture | **whole-stage subagent + compressed brief** | ADR-002 |
| 3 | 1 | Session autopilot | *(non-decisional — session config, no ADR)* | auto_safe | — |
| 4 | 2 | Span close on missing end marker | Contract shape | **next start / session end / cap, whichever first** | ADR-003 |
| 5 | 2 | Subagent authority boundary | Risk tolerance | **main loop keeps git + land** | ADR-004 |
| 6 | 2 | Retroactive continuation detection | Architecture | **LLM once, cached** | ADR-005 |
| 7 | 3 | Brief-quality regression detection | Testing depth | **validate the brief; missing field fails** | ADR-006 |
| 8 | 3 | Subagent identity | Dependencies | **new dedicated agent asset** | ADR-007 |
| 9 | 4 | Span event producer | Contract shape | **fold into an existing load-bearing CLI call** | ADR-008 |
| 10 | 4 | Enforcement of the subagent boundary | Risk tolerance | **declare: instruction, not enforcement** | ADR-004, ADR-007 |
| 11 | 4 | Recovery-wrapup availability | Failure handling | **machine-derive, then degraded inline execution** | ADR-006 |
| 12 | 4 | Span cap calibration | Contract shape | **400 turns / 240 minutes** | ADR-003 |

Skipped by the 5-term gate, recorded as assumptions:

- **Ledger and cache file names** (failed EIG):
  `.claude/observability/stage-spans.jsonl` and
  `.claude/observability/run-verdicts.jsonl`, both base-root-resolved
  (the name is `run-`, not `continuation-`: the file stores every verdict,
  including `new` and `unknown`, and a name promising only continuations invites
  the reader to assume an absent entry means "not a continuation" — which is
  exactly the miss-vs-verdict conflation [ADR-005](#adr-005) counts separately)
  ([ADR-010](#adr-010)) and both in `_HARNESS_CHURN_PREFIXES`.
- **Where the LLM classifier runs** (failed common-ground — CLAUDE.md §4):
  judgment in the `/hm:metrics` prose layer, persistence in Python.
- **Phase ordering** (confidence above τ): attribution lands before the change
  it evaluates.
- **Whether `hm:verify` gets the same treatment** (failed common-ground):
  yes; later phase because its spend is $123.54 against $1,064.92.

---

## 📐 Architecture Decision Records

<a id="adr-001"></a>
### ADR-001: Hybrid attribution recovery with per-turn source labelling
**Status:** Accepted (2026-07-26)
**Context:** 55.9% of priced turns carry no `attributionSkill`. Forward-only
leaves a 172-file corpus unusable; retroactive-only guesses forever.
**Decision:** Build both. The forward **span ledger** is authoritative where it
reaches ([ADR-008](#adr-008) names where it does not); a retroactive
**transcript inference** path covers older data; the existing adjacency
estimator remains the last fallback. Every **turn** carries an
`attribution_source` (`direct` | `ledger` | `inferred` | `adjacency` | `none`)
and every stage row reports the *breakdown*, never a single label — one row
legitimately mixes sources. **Precedence when sources disagree:** `direct`
(the turn's own `attributionSkill`) > `ledger` > `inferred` > `adjacency`.
A `ledger` vs `direct` disagreement is counted and reported: it is the health
signal for the emitter.
**Consequences:**
- ✅ Usable numbers today, exact numbers where the ledger reaches.
- ✅ The label makes the populations non-comparable by construction, so a trend
  cannot silently mix an inferred number with a measured one.
- ⚠️ Three attribution code paths to maintain and test.
**Rejected alternatives:** forward-only (discards the corpus); retroactive-only
(permanently heuristic); dropping the estimate (leaves the largest line
unexplained).
**Source:** Interview #1

<a id="adr-008"></a>
### ADR-008: Spans emit from a load-bearing CLI call — with named exemptions
**Status:** Accepted (2026-07-26, Interview #9; **coverage bounded after the second validation pass**)
**Context:** The first draft had stage templates emit spans as prose. Both
second-opinion models and the validator rejected it: a Markdown instruction is
best-effort and a render test can only prove the text is *present*. The second
draft moved emission onto `worktree task-preflight` and claimed it covered every
invocation path. **That claim was false**, and verified so:
`loop.md.j2:990` reads "do NOT run `task-preflight`", and the preflight partial
is included only inside `{% if …feature_branch_workflow %}` in all seven stages.
**Decision:**
- The span **start** is emitted as a side effect of a CLI call the stage already
  must make — `worktree task-preflight` under the feature-branch workflow. The
  stage name is passed as an explicit `--stage <name>` argument, positioned
  **after** the base positional (`task-preflight <slug> "$(pwd)" --stage <name>`).
  Position is contractual, not cosmetic: the shipped parser takes positionals as
  "every arg not starting with `--`", so a flag placed *before* the base silently
  consumes its own value as `base_dir` — a stage would then create its worktree
  under a directory literally named `hm:plan` and write the ledger to the wrong
  root. Phase C makes the parser flag-aware, and a **render-gate test** asserts
  every stage template passes `--stage` in that position.
  An emission without it writes an **empty** `stage`, which the reader maps to the
  `(unknown-stage)` sentinel and counts as `unknown_stage_emissions`; it never
  fails the stage (old rendered harnesses must keep working). The empty string is
  the wire value deliberately — normalising to the sentinel at *write* time would
  leave the absent-case counter reading 0 forever, which is precisely the count:8
  "absent case = feature black hole" pattern this rule exists to avoid.
- **`/hm:loop` is exempt from per-stage spans.** The loop owns its own
  isolation and calls `worktree create execute` (`loop.md.j2:431/439`); that
  call emits one **loop-level** span (`stage: "hm:loop"`).
  > **Corrected during Phase 2.** An earlier draft said *iteration*-level. It is
  > not: `loop.md.j2` states "Per-loop (not per-iter)" and calls `create` once at
  > the top, so a single span covers the whole run. A long loop therefore exceeds
  > `span_max_turns` and the remainder lands in `capped_turns` — visible, but not
  > attributed. Per-iteration spans would require redesigning the loop's isolation
  > (Non-Goal 1). Do not read "loop spend is attributed" as "fully attributed".
  Loop spend is
  therefore attributed to the loop, not to `(unattributed)`, but not to the
  individual stage inside it. See Non-Goal 1.
- **`feature_branch_workflow: false` harnesses are ledger-exempt** — six of
  seven stages have no mandatory call there. They fall back to inference and
  adjacency. See Non-Goal 2.
- The **end** stays best-effort, covered by [ADR-003](#adr-003).
**Consequences:**
- ✅ Emission is *coupled* to a call the stage needs for its own correctness, so
  a skipped emission co-occurs with a visibly degraded stage. **This is a
  coupling argument, not a guarantee** — the call is still a model-executed
  `!`-line with a `<slug>` the model substitutes, so a model that ignores
  preflight and edits in cwd produces a degraded stage with no span. The
  ground-truth disagreement rate (Phase 2) is the detector for that residual.
- ✅ Unlocks a free oracle: 8,005 turns carry a ground-truth
  `attributionSkill`, so every ledger span is checkable against it.
- ⚠️ Coverage is bounded by the two exemptions above, and every coverage claim
  in Success Criteria names them.
**Rejected alternatives:**
- *Hooks for stage identity* — a hook does not know which stage is running.
  Hooks are used only for **session-boundary** closure ([ADR-003](#adr-003)).
- *Prose emission* — a render test cannot prove execution.
- *A required `--stage` argument* — would break every already-rendered harness.
**Source:** Interview #9; plan-validator V2, N1, N4, N10.

<a id="adr-009"></a>
### ADR-009: Sidechain spans nest; conservation is per-source only
**Status:** Accepted (2026-07-26; **narrowed after the second validation pass**)
**Context:** [ADR-002](#adr-002) moves wrapup's body into a subagent, whose
turns are `isSidechain`. Without a policy, workstream 2 re-opens the hole
workstream 1 exists to close. Measured: **100% of sidechain turns carry
`attributionAgent`**. The previous draft also asserted a *cross-population*
conservation invariant ("every turn attributed exactly once across the main and
subagent populations") — that is **not expressible**: `economics.py:418`
accumulates every turn into `by_stage` and `:419-422` accumulates the same turn
into `by_agent`, which is a cross-cut, not a partition.
**Decision:**
- A sidechain turn is attributed to the **enclosing main-stage span** and is
  additionally visible on the existing `by_agent` cross-cut. `by_agent`
  semantics are unchanged (Non-Goal 6).
- The conservation invariant is stated **only over the source axis**: every
  priced in-window turn carries exactly one `attribution_source`, and the
  per-source USD totals sum to `total_usd`. This is a unit-test invariant.
- Because sidechain turns nest, `by_stage["hm:wrapup"]` **is** the all-in
  wrapup total. Nothing is added to it — see Success Criteria.
**Consequences:**
- ✅ Delegated spend stays inside the stage that caused it, so the wrapup total
  cannot fall merely because the work moved.
- ✅ The retained invariant is computable against the current schema.
- ⚠️ There is no "main-loop USD" field, so a main-vs-subagent split of a stage's
  cost is not reportable. Not needed by any criterion below.
**Rejected alternatives:** excluding sidechain from spans (delegated cost would
vanish, making the carry number improve for free); giving subagents their own
top-level spans (breaks the stage as the unit of accounting).
**Source:** plan-validator V1, N3; sidechain probe.

<a id="adr-010"></a>
### ADR-010: Ledger and verdict cache live at the base root, written with the house atomic-append pattern
**Status:** Accepted (2026-07-26)
**Context:** Under `feature_branch_workflow` every stage runs inside
`.worktrees/<slug>/`. A cwd-relative write lands in a gitignored path that
`task-land` deletes — the identical bug this project already shipped and fixed
in `codex_ledger`.
**Decision:** Both files resolve through `second_opinion_invoke.resolve_base_root()`;
records are appended with the `telemetry.py:199-216` pattern (`O_APPEND` + a
single `os.write()`), carry a `schema_version`, and a malformed or partial
trailing line is skipped with a counted diagnostic.
**Consequences:**
- ✅ Reuses two proven implementations rather than re-deriving them.
- ✅ Concurrent sessions append safely at these record sizes.
- ⚠️ No rotation policy; the reader must tolerate a partial trailing line.
**Rejected alternatives:** cwd-relative path (the shipped bug); a locked
read-modify-write (unnecessary for append-only records under `PIPE_BUF`).
**Source:** plan-validator V5

<a id="adr-003"></a>
### ADR-003: An open span closes at the next start, session end, or a measured cap
**Status:** Accepted (2026-07-26; caps calibrated Round 4, closure bounded after the second pass)
**Context:** Both markers are optional by construction. The first draft keyed
every closure rule on the next start, so a dropped start degraded into the
"start-only" design the ADR itself rejected. Its caps were also chosen without
consulting the distribution the plan had already measured.
**Decision:**
- An open span closes at the earliest of (a) the next span-start in the same
  session, (b) session end, (c) `span_max_turns` = **400**, (d)
  `span_max_min` = **240**. Turns past a cap stay **unattributed**.
- Reaching a cap moves the span to a **terminal `capped` state**: a late end
  record or a later start can neither reopen nor extend it.
- **Absent start:** a span is only ever opened by an explicit start record.
  Turns before the first start of a session are unattributed — never back-filled
  onto a neighbouring stage.
- **Session-end closure is Claude-Code-only.** It rides the already-wired
  `Stop` / `PreCompact` hooks in `.claude/settings.json`, which only Claude Code
  reads. On Cursor and Codex, closure (c)/(d) — the caps — is the operative
  mechanism, so those targets should expect a higher `capped_turns`. Stated
  rather than discovered.
- **Absent `session_id`:** `$HM_SESSION_ID` is empty on WSL2 (CLAUDE.md
  documents this on the author's own platform). The field is **best-effort**;
  when absent the join degrades to `(base_root, ts-interval)`, whose
  limitation — concurrent sessions in the same repo cannot be separated — is
  reported as a counted `ambiguous_session_join` rather than silently resolved.
- `capped_turns` and `capped_usd` are first-class report fields.
**Consequences:**
- ✅ Both markers' absent cases are defined, as is the absent session id.
- ✅ Caps are calibrated: 400 turns captures 96.1% with exactly one run over;
  240 min sits between p95 (179.1) and p99 (485.2) and cuts 4 of 144 runs.
- ✅ Caps can still reject, preserving the prior work's invariant.
- ⚠️ **Accepted loss, stated:** `cap=400` leaves 396 turns unattributed by
  design on the measured corpus. Success Criteria say "minus the capped
  remainder", never "~100%".
- ⚠️ Boundary inclusivity is contractual: the Nth turn is attributed, N+1 is not.
**Rejected alternatives:** heartbeat refresh (a missed refresh silently
truncates); start-only closure (unbounded over-attribution); caps of 200/120
(reject four of the six continuation runs the plan itself sampled).
**Source:** Interview #4, #12; plan-validator V2, V8, N11.

<a id="adr-002"></a>
### ADR-002: Whole-stage delegation for wrapup and verify, with a runtime self-skip
**Status:** Accepted (2026-07-26; per-target mechanism corrected after the second pass)
**Context:** Measured entry context: `hm:wrapup` 439k (grows +26k in-stage),
`hm:verify` 357k (+4k). Context is a function of *when* a stage runs. The
previous draft said delegation would "render for claude-code only, inline for
cursor" — **there is no such branch point**: `synthesize.py` has no `is_cursor`,
`_cursor_target_files()` renders only `harness.mdc` / `hooks.json` / `mcp.json`,
and commands are single-source `.claude/commands/hm/*.md` that Cursor reads
natively.
**Decision:** The wrapup and verify bodies execute inside a dedicated subagent
driven by a compressed brief. The command is **single-source**; the dispatch
block **self-skips at runtime** when the subagent-dispatch tool is unavailable,
falling through to the inline body — the same shape
`stage_end_summary.md.j2:24-28` already uses for the autopilot block. Codex
keeps its existing `is_codex` render branch.
**Consequences:**
- ✅ Attacks the measured cause rather than a symptom.
- ✅ One command file, no unexpressible render branch; Cursor degrades to inline
  by the same mechanism a Cursor session already uses for autopilot.
- ⚠️ **The 2.31× subagent-vs-main-loop figure ($0.327 against $0.754/turn) is a
  confounded observation, not a projection.** It controls for nothing and
  excludes brief composition, subagent startup, and result ingestion. It is
  motivation; the acceptance test is the all-in total in Success Criteria.
- ⚠️ Stage quality now depends on brief completeness — the plan's largest risk,
  mitigated by [ADR-006](#adr-006) and [ADR-012](#adr-012).
**Rejected alternatives:** heavy-steps-only delegation (most main-loop turns
remain); incremental capture across all seven stages (Non-Goal 3);
measure-only this cycle (rejected by the user); a per-target render branch (no
branch point exists).
**Source:** Interview #2; plan-validator V6, N5.

<a id="adr-011"></a>
### ADR-011: Delegation is config-gated, default-off, with a stated soak exit
**Status:** Accepted (2026-07-26; key renamed and soak bounded after the second pass)
**Context:** Every comparable behavior axis here is config-keyed. Without one,
the only rollback for a user who re-rendered is a patch release. The previous
draft named the key `wrapup.delegate` while Phase 6 also used it to gate
*verify* — a key named for one stage silently controlling another.
**Decision:** `harness.yaml delegation.stages: []` (a list; empty = off),
default **empty** for one release. **Absent key** → inline, with a one-time
advisory (CLAUDE.md #6). A matching `InterviewAnswers` mirror and
`answers_from_harness_yaml` mapping ship with it — without them
`extra='forbid'` drops the user's opt-in on the next `--update`, which would
break the very key designated as the rollback (checkpoint 6).
**Soak exit:** the default flips to `[wrapup, verify]` in the release after
**10 delegated wrapups whose [ADR-012](#adr-012) receipts reconciled clean with
zero manual corrections**, recorded in the release's CHANGELOG entry.
**Consequences:**
- ✅ Rollback is a config edit, not a release.
- ✅ The soak has an owner-checkable end condition rather than "one release".
- ⚠️ Both paths stay green through the soak, doubling the render-test surface.
**Rejected alternatives:** ship default-on (no per-user off switch for a
medium-likelihood / high-impact quality risk); a stage-named key (misleading).
**Source:** plan-validator V11, N7, N12.

<a id="adr-004"></a>
### ADR-004: git and land stay in the main loop — as instruction, not enforcement
**Status:** Accepted (2026-07-26; downgraded from "boundary" in Round 4)
**Context:** The delegated body invokes `memory_md upsert-wiki`,
`memory_md upsert-failure`, and `second_brain promote` — all shell CLIs — so the
agent's `tools:` must include Bash, and CLAUDE.md §보안 states that with Bash
present, per-agent command scoping is not expressible in frontmatter.
**Decision:** `git add`/`commit`, post-commit stash pop, landed-branch drain,
and `task-land` remain in the main loop, documented as a **prompt instruction,
not a runtime boundary** — copying the `executor_body.md.j2` "Scope —
instruction, not enforcement" precedent verbatim.
**Consequences:**
- ✅ Honest; a future reader cannot mistake it for a security property.
- ✅ Base-mutating operations sit in one diagnosable place by prompt
  construction.
- ⚠️ A misbehaving or prompt-injected agent *can* run git. Accepted; an
  agent-identity `PreToolUse` hook (`permission_gate` is already wired on
  matcher `Bash`) is the named upgrade and a Non-Goal here.
**Rejected alternatives:** agent-identity hook now (new logic and tests for a
risk the user judged acceptable this cycle); withholding Bash and building a
Python transaction API (would redesign the locked-CLI contract H1 protects).
**Source:** Interview #5, #10; plan-validator V3.

<a id="adr-007"></a>
### ADR-007: A dedicated agent asset executes the delegated body
**Status:** Accepted (2026-07-26; false enforcement claim removed in Round 4)
**Decision:** Add a dedicated rendered agent with
`tools: Read, Grep, Glob, Write, Edit, Bash` and `communication_variant: full`.
**Consequences:**
- ✅ Prompt written for this body rather than for implementation work.
- ✅ Covered by `agent-quality-rubric` and the render gates.
- ⚠️ **Bash is present, so this tool list does NOT prevent git, `rm`, or writes
  outside the worktree.** It prevents nothing beyond what tool *absence* would;
  it exists for prompt fit, not confinement. See [ADR-004](#adr-004).
- ⚠️ One more asset across three targets, including the `communication_variant`
  whose absence is a render-time `UndefinedError`.
**Rejected alternatives:** reuse `executor`; `general-purpose` (no render-time
verification possible).
**Source:** Interview #8, #10.

<a id="adr-006"></a>
### ADR-006: The brief is a validated contract with a machine-derived core and a *reachable* degraded path
**Status:** Accepted (2026-07-26; reachability fixed after the second pass)
**Context:** Delegation risks shallower memory entries with no failing test. But
hard-failing on an incomplete brief would strand a crashed session's work — the
standalone/recovered wrapup is a first-class supported path. The previous draft
added the degraded path in Python while Phase 5 described a mutually-exclusive
Jinja branch, so **there would have been no inline body to fall back into**.
**Decision:**
- The brief is a typed object validated in Python before dispatch. Every
  derivable field is derived (slug from branch, base and worktree roots from
  cwd resolution, changed files and diff from git).
- If a genuinely non-derivable field is missing, the stage does **not** raise:
  it logs a loud warning, records the reason, and runs the body **inline**.
- **The delegate-on render therefore carries BOTH** the dispatch and the inline
  body, the latter under an explicit "degraded — dispatch unavailable or brief
  incomplete" heading. A render assertion in Phase 5 pins this.
**Consequences:**
- ✅ Blocks the degraded-quality path at its cause without blocking recovery,
  and the fallback target actually exists in the artifact.
- ✅ The same inline body serves [ADR-002](#adr-002)'s runtime self-skip, so one
  block covers both fallbacks.
- ⚠️ **The delegate-on wrapup command grows rather than shrinks.** Context lint
  applies (Production ≤ 500 lines for CLAUDE.md, agent/skill limits separately);
  Phase 5 must check the rendered size.
- ⚠️ A field present but vacuous still passes — structure, not quality.
  [ADR-012](#adr-012) covers the output side.
**Rejected alternatives:** hard fail always (availability regression); A/B as
the primary gate (one-shot, manual — retained as a Phase 6 pre-ship check);
a `/hm:health` signal (post-hoc).
**Source:** Interview #7, #11; plan-validator V4, N6.

<a id="adr-012"></a>
### ADR-012: The delegated body returns a machine receipt, not prose
**Status:** Accepted (2026-07-26)
**Context:** [ADR-006](#adr-006) validates *inputs*; complete inputs do not
imply a complete wrapup. The `promotion evaluated: N candidates, M promoted`
line is CLAUDE.md's sole visibility mechanism for under-promotion, and
delegation puts it behind a summarization boundary.
**Decision:** The delegated agent returns a structured result — memory slugs
written, failure slugs touched, promotion candidate and promoted counts with
per-skip reasons, managed documents updated. The main loop reconciles those
claims against observable state (tier files, the Second Brain namespace) before
committing and surfaces any mismatch loudly.
**Consequences:**
- ✅ Postconditions are checked against reality, so a receipt cannot be
  fabricated by a summarizing main loop.
- ✅ Deterministic, testable without an LLM.
- ⚠️ A result schema to keep in step with the wrapup steps it mirrors.
- ⚠️ Reconciliation proves entries *exist*, never that they are good.
**Rejected alternatives:** trust the prose receipt (the current render test
would pass if the agent never printed the line, or printed `N=0`).
**Source:** plan-validator; codex P1-C8/C9.

<a id="adr-005"></a>
### ADR-005: Retroactive continuation classification is LLM-judged once, cached, and versioned
**Status:** Accepted (2026-07-26)
**Decision:** The `/hm:metrics` prose layer classifies each of the ~144 run
boundaries once. The verdict is keyed by `(boundary turn uuid,
classifier_version)`, so changing the prompt invalidates prior verdicts instead
of silently reusing them. Python owns the cache format and never calls an LLM.
**Absent cases, all explicit:**
- boundary with no user message (session start, tool-result or
  `<task-notification>` boundary, post-compaction): classified from surrounding
  turns, else `unknown`;
- classifier failure, timeout, or unparseable verdict → `unknown`;
- `unknown` and cache-miss both leave the run **unattributed** and increment a
  reported counter. Neither ever defaults to "continuation" — a wrong
  continuation verdict is invisible, an unattributed run is not.
**Consequences:**
- ✅ Follows the LLM-first principle without making the report
  non-deterministic; a cached corpus recomputes identically.
- ✅ Bounded cost: ~144 judgments, not 10,249.
- ⚠️ First run on a fresh clone pays the classification cost; the miss count is
  reported.
- ⚠️ Verdicts are not portable across machines (the cache is gitignored churn).
**Rejected alternatives:** deterministic rules only (a short new task is
textually indistinguishable from a short continuation); rules-then-LLM
(negligible saving, extra branch).
**Source:** Interview #6; plan-validator; codex P1-C12/C13; antigravity P2-A6.

---

## 🏗️ Technical Design

### Current State

- `economics.py` (652) — `TurnRecord.stage` = `attribution_skill or UNATTRIBUTED`;
  `scope` = `"subagent" if is_sidechain`; `aggregate()` at `:412-422` buckets
  each turn into `by_stage` **and** (if agent-tagged) into `by_agent`.
  `EconomicsReport` (`:158-188`) has no USD-by-scope field.
- `economics_source.py` (335) — already surfaces `isSidechain`,
  `attributionAgent`, `cwd`, `gitBranch`.
- `worktree.py:4908` `_cli_task_preflight(<slug> [base_dir])` — mints a fresh
  `uuid.uuid4().hex[:12]` per invocation; knows no stage and no Claude session.
- `templates/agents/_partials/worktree_preflight.md.j2:18` — renders
  `task-preflight <slug> "$(pwd)"`, included by all seven stages only inside
  `{% if …feature_branch_workflow %}`.
- `synthesize.py` — `is_codex` exists; **`is_cursor` does not**.
- `second_opinion_invoke.resolve_base_root()` (`:110`), `memory_md._base_root()`
  (`:71`), `telemetry.py:199-216` — the three precedents reused below.

### Affected Components

| Component | Change |
|---|---|
| new `stage_spans.py` | Ledger writer + reader; close rule; terminal `capped`; base-root resolution |
| `worktree.py` | `--stage` arg + span emission on `task-preflight` **and** on `create execute` (iteration-level) |
| `economics.py` | Span join; per-turn `attribution_source`; sidechain nesting; `capped_*`. **`by_agent` semantics unchanged** |
| `economics_source.py` | Expose turn `uuid` (classifier cache key) |
| new `wrapup_brief.py` | Typed brief, machine derivation, validation, degraded verdict |
| new `wrapup_receipt.py` | Result schema + reconciliation |
| `models.py` | `economics.span_max_turns` / `span_max_min`, `delegation.stages` — **each with an `InterviewAnswers` mirror** |
| `interview.py` | `answers_from_harness_yaml` round-trip for the three new keys |
| `templates/stages/wrapup.md.j2`, `verify.md.j2` | Dispatch + inline body (both present); git tail inline |
| new `templates/agents/<name>.md.j2` | [ADR-007](#adr-007) asset |
| `templates/commands/hm/metrics.md.j2` | Classification step; source breakdown; `capped_*` |
| `worktree._HARNESS_CHURN_PREFIXES` | Ledger + verdict cache |
| `render.py`, snapshot expectations | New asset + template changes |

### Data Flow

`stage-spans.jsonl`, append-only, base-root-resolved, one record per event.
**Fields are limited to what the emitting subprocess can actually observe** —
the previous draft required `turn_uuid`, which a subprocess cannot know:

```
{schema_version, event: "start"|"end", stage, cwd, base_root,
 git_branch, task_slug, ts, session_id?}
```

`session_id` is best-effort from `$HM_SESSION_ID` ([ADR-003](#adr-003)'s absent
case). The join is `(base_root, session_id when present, ts-interval)`.
Closure is computed at **read** time; a capped span is terminal and cannot be
reopened. A malformed trailing line is skipped and counted.

### API Changes

New report fields — all sums or counts, none a quotient of cost by a deliverable
count: `attribution_source_breakdown` (per stage row),
`ledger_attributed_usd`, `inferred_attributed_usd`, `adjacency_attributed_usd`,
`capped_turns`, `capped_usd`, `classification_cache_misses`,
`classification_unknown`, `ledger_ground_truth_disagreements`,
`ambiguous_session_join`, `unknown_stage_emissions`.

---

## 📝 Implementation Plan

### Phase 1 — Span ledger core (Python) — **DONE**

> **Status: done.** 30 tests green; `ruff`, `ruff format`, `mypy --strict` clean;
> full unit+structural suite green. Two defects were caught only by *running* the
> code, not by review: (a) `max_turns` applies per span, so a test expectation
> asserting three attributions on a 2-cap span was wrong — the reviewer had marked
> that test PASSING, but the file was RED at collection so nobody had executed it;
> (b) under `strict=True`, `model_validate` rejects an ISO string for a `datetime`,
> so every well-formed ledger line counted as malformed until the reader moved to
> `model_validate_json`. (b) is the `producer-consumer-schema-drift` class and only
> the round-trip test could have found it.

- `depends_on`: []
- `parallel_group`: `serial-attribution`
- `merge_hazards`: `economics.py`, `models.py`, `economics_source.py` — shared with Phase 3
- **Scope in:** `stage_spans.py` (writer, reader, close rule, terminal `capped`,
  `resolve_base_root`, `telemetry.py`-pattern append); `economics.py` join +
  per-turn `attribution_source` + sidechain nesting + `capped_*`; `uuid`
  passthrough; config keys **with their `InterviewAnswers` mirrors**
- **Scope out:** any template; any LLM path
- **Exit criterion:** `uv run pytest tests/unit/test_stage_spans.py -q` green,
  including: (a) cap boundary pinned both sides — N attributed, N+1 not;
  (b) turn-cap and duration-cap each rejecting independently; (c) a late `end`
  and a later `start` both failing to extend a capped span; (d) **per-source**
  conservation — every turn carries exactly one source, per-source USD sums to
  `total_usd`; (e) a positive control so an implementation attributing nothing,
  or one raising unconditionally, fails; (f) emitting from inside
  `.worktrees/<slug>/` appends to the BASE ledger; (g) an absent `session_id`
  degrades the join and increments `ambiguous_session_join` rather than
  mis-joining; (h) config round-trip — set each key, dump, reload, key survives
- **Risk:** low
- **Rollback:** revert; nothing consumes the module yet

### Phase 2 — Span emission, with exemptions asserted — **DONE**

> **Status: done.** 71 span tests green (incl. a new CLI-driven
> `tests/integration/test_stage_spans_e2e.py`); full suite green after snapshot
> regeneration. Shipped beyond the original scope: a `worktree span-end`
> subcommand — `event: "end"` previously had no producer and no test, so that arm
> of the schema was dead weight.
>
> **Scope items resolved differently than planned:**
> - *"ledger + verdict cache added to `_HARNESS_CHURN_PREFIXES` and gitignore"* —
>   **already satisfied**; `.claude/observability/` is a dir-prefix entry and
>   `_HARNESS_GITIGNORE_PATTERNS` derives from it. Adding a redundant entry would
>   have broken the union sync test. Done-by-inheritance, no code written.
> - *Snapshot regeneration inside a worktree* — the `[fail:test]
>   snapshot-regen-inside-worktree` memory (count:11) says never do this. That
>   memory is now **stale**: `tests/snapshot/regenerate.py:107-125` pins
>   `_HARNESS_MAKER_PKG_ROOT` and `_compute_install_ref` explicitly so snapshots
>   are worktree-invariant. Verified empirically rather than trusted — regenerated
>   from the worktree and grepped: zero occurrences of the worktree path in any
>   fixture. The memory entry should be corrected at wrapup.
>
> **Defects caught by the gate, each of which would have shipped silently:**
> - Argument order: `--stage` before the base positional made
>   `base_dir = Path("hm:plan")`, since the shipped parser treated every non-`--`
>   arg as positional. A text-grep render test cannot observe a parse; the e2e now
>   asserts the worktree LOCATION.
> - The loop discriminator selected on the flag's VALUE, but `loop.md.j2` passes
>   `--claude-session-id "$HM_SESSION_ID"` quoted and that variable is empty on
>   WSL2 — so every loop on the author's own platform would have been labelled
>   `hm:execute`. The signal is flag PRESENCE.
> - `span-end` was session-blind, so an idle peer's Stop hook truncated a live
>   session's span; and its shipped **zero-argument** form was never exercised.
> - `PreCompact` was left unwired although ADR-003 names it, which would have sent
>   every post-compaction tail to the 400-turn cap, absorbed invisibly by
>   `capped_turns`.
> - The `span-end` dispatch token was added without registering it in
>   `command_registry`; the command-surface parity gate caught it.

- `depends_on`: [1]
- `parallel_group`: `serial-attribution`
- `merge_hazards`: `worktree.py`, all `templates/stages/*.md.j2`, snapshot expectations, `render.py`; **must not run concurrently with Phase 4** (both touch `render.py` + snapshots) **or Phases 5–6** (same template files)
- **Scope in:** `--stage` argument + start emission on `task-preflight`;
  iteration-level emission on `worktree create execute` for `/hm:loop`;
  session-end emission via the already-wired `Stop` / `PreCompact` hooks
  (Claude-Code-only, per [ADR-003](#adr-003)); ledger + verdict cache added to
  `_HARNESS_CHURN_PREFIXES` and gitignore; snapshot regeneration
- **Scope out:** economics consumption (Phase 1); any new emission point for
  `feature_branch_workflow: false` stages (Non-Goal 2)
- **Exit criterion:** `uv run pytest tests/integration/test_stage_spans_e2e.py
  tests/unit/test_invocation_render_gate.py tests/snapshot -q` green, where the
  e2e test drives the rendered stage's **CLI lines directly** in a tmp project
  (no model turn) and asserts both records; a **render-gate test** asserts every
  stage template passes `--stage` **after the base positional**; a test asserts the
  flag-off render emits **nothing** (the exemption is pinned, not assumed); and a
  **deterministic unit test of the disagreement computation** — synthetic spans plus
  synthetic turns with known `attributionSkill`, asserting both the count and that it
  is reported.

  > **Corrected after the Phase-2 test gate.** An earlier version of this criterion
  > demanded "over the local corpus, ledger spans disagree with `attributionSkill` on
  > fewer than 1% of turns carrying both". That is **vacuously satisfiable and cannot
  > gate anything**: the 172-file corpus was recorded before any span existed, so the
  > intersection of "turns carrying both" is zero at Phase-2 land time — 0 disagreements
  > out of 0 turns is trivially under 1%. The corpus measurement is therefore moved out
  > of the exit criterion and into a **dated soak item** (below); only the computation is
  > gated here. Presenting the unit test as if it were the corpus measurement would be
  > the same substitution this plan already made once.

  **Soak item (not a Phase-2 gate):** after ≥14 days of real emission, re-run the
  disagreement check over turns that carry both a span and an `attributionSkill`, and
  record the rate. Note that on WSL2 `$HM_SESSION_ID` is empty ([ADR-003](#adr-003)),
  so the join degrades to `(base_root, ts-interval)` there and the rate may be
  structurally unmeasurable — if so, say that rather than reporting a number.
- **Risk:** medium
- **Rollback:** Phase 1

### Phase 3 — Retroactive classification + source-labelled report — **DONE**

> **Status: done.** New `run_classify.py` + 38 unit tests + 14 boundary-field tests
> + 15 render-gate assertions, all green; `ruff`, `ruff format`, `mypy --strict`
> clean over all 122 source files.
>
> **Scope item found missing from every prior phase — the CLI never consumed either
> source.** `_collect()` built `aggregate(...)` without `spans` (Phase 1 wrote the
> join, Phase 2 wrote the emitter, neither wired the reader) and, naturally, without
> `inferred` either. Every unit test in Phases 1–3 passed while
> `economics report` — the only thing a user actually runs — reported a world in
> which neither the ledger nor the classifier existed. Fixed here, and pinned by two
> CLI-level tests (`test_the_report_command_reads_the_verdict_cache_and_labels_the_
> recovered_turns` plus its no-cache negative control). This is the same shape as
> the Phase-2 `--stage` parse defect: the unit boundary was green and the shipped
> entry point was wrong.
>
> **Defects the Phase A.5 gate caught, both of which would have shipped green:**
> - The only test of the `boundaries` command ran against an EMPTY store, so it
>   asserted `boundaries == []` and nothing about the payload. A command emitting
>   rows with no `uuid` / `preceding_stage` / `has_user_message` — i.e. one the prose
>   classifier cannot use at all — passed it. `find_boundaries`' own unit tests stay
>   green in that world.
> - No test recorded a verdict on a `has_user_message: false` boundary. Every
>   remaining assertion was satisfied by `if not boundary.has_user_message: return
>   unknown` *before consulting the cache* — which permanently excludes the
>   post-compaction / tool-result / task-notification population (the longest runs in
>   the measured corpus) from attribution while `classification_unknown` climbs, with
>   nothing able to distinguish "the classifier said unknown" from "the code refused
>   to ask". ADR-005's wording is "classified from surrounding turns, **else**
>   unknown"; the else-branch is the fallback, not the rule.
>
> **A test-helper defect caught by running the tests:** `_turn(uuid=None)` used
> `None` as both "unspecified" and "this transcript line has no uuid", so the
> pre-uuid-line test silently received `"u1"`. Same class as the Phase-1
> `strict=True` datetime defect — only execution finds it.
>
> **Counter mapping, resolved (the exit criterion was ambiguous).** The criterion
> said all three inputs yield "`unknown` + a counter". They yield the same *outcome*
> (unattributed, never a continuation) but land in **two** counters, deliberately:
> a corrupt cache line and an absent one are both "no verdict" →
> `classification_cache_misses`; only a recorded `unknown` verdict →
> `classification_unknown`. The distinction is what tells an operator whether 5a has
> work left or the corpus is genuinely undecidable. Both are reported.
>
> **Naming reconciled:** the cache is `run-verdicts.jsonl`, not the
> `continuation-verdicts.jsonl` this document assumed at line 239 — it stores `new`
> and `unknown` too, and the narrower name invites reading an absent entry as "not a
> continuation".
>
> **Exit criterion evidence** — `python -m harness_maker.economics report --root .`
> on this repo, 2026-07-26:
>
> | field | value |
> |---|---|
> | `turns_by_attribution_source` | `direct 8,323 / adjacency 1,007 / none 9,772` (sum 19,102 = `turns`) |
> | `usd_by_attribution_source` | sums to `total_usd` = **$12,571.397051**, delta 4.4e-11 (float epsilon) |
> | `classification_boundaries` | **385**, all currently `cache_misses` |
> | `capped_turns` / disagreements / `unknown_stage_emissions` / `ambiguous_session_join` | 0 |
> | `ingestion.coverage` | 1.0 |
>
> Two numbers need reading correctly rather than celebrating:
> - **`ledger` is 0 turns, and that is expected, not a failure.** The emitter ships
>   on this branch; the *installed* plugin is 0.43.0, whose
>   `worktree_preflight.md.j2` has no `--stage` (verified: zero matches). No span has
>   ever been written, so `.claude/observability/stage-spans.jsonl` does not exist.
>   The ledger column starts filling only after this work lands **and**
>   `/harness-maker:make --update` re-renders the harness. Do not read a green
>   Phase 2 as "the ledger is measuring".
> - **385 boundaries, not the ~144 this plan quoted.** The earlier probe counted
>   contiguous unattributed stretches without splitting on `session_id`; the shipped
>   detector does split (a peer session's turn must never be inherited from), and the
>   corpus has grown since. 385 is the honest work list. All 385 are misses today
>   because no verdict has been recorded yet — the backlog is now *named* rather than
>   silently absorbed into `(unattributed)`, which is the point of the counter.

- `depends_on`: [1]
- `parallel_group`: `serial-attribution`
- `merge_hazards`: `economics.py` (shared with Phase 1), `metrics.md.j2`
- **Scope in:** run-boundary detection incl. the no-user-message cases;
  `(uuid, classifier_version)`-keyed cache; `/hm:metrics` classification step;
  per-turn source breakdown; `capped_*`, `classification_*`, disagreement and
  `ambiguous_session_join` reporting
- **Scope out:** the forward ledger path
- **Exit criterion:** `python -m harness_maker.economics report` on this repo
  emits a per-source breakdown whose USD totals sum to `total_usd`; unit tests
  pin that a cache miss, an unparseable verdict, and a boundary with no user
  message each yield `unknown` + a counter and **never** a continuation
- **Risk:** medium
- **Rollback:** Phase 2

### Phase 4 — Brief contract, result receipt, agent asset — **DONE**

> **Status: done.** `wrapup_brief.py` + `wrapup_receipt.py` + the `stage-delegate`
> asset; 61 unit tests green, `ruff` / `mypy --strict` clean.
>
> **The A.5 gate's sharpest catch — the round-trip test proved only the READ half.**
> `answers_from_harness_yaml` accepting `delegation` says nothing about whether the
> key is ever WRITTEN. `/harness-maker:make --update` re-renders `harness.yaml` *from
> the template*, so a `delegation:` block missing from `harness-yaml/{Side,Production}
> .yaml.j2` — or a missing `HarnessConfig.delegation` field, or `synthesize` not
> copying `answers.delegation` — silently reverts the user's opt-in on the very next
> update, with every reader-side test green. That is the ADR-011 rollback switch
> disarming itself. All three of those gaps were real and are now fixed and pinned by
> a per-preset render test that closes the loop (write → read back unchanged).
>
> **The same defect already existed in Phase 1 and was found by analogy.**
> `EconomicsConfig` gained `span_max_turns` / `span_max_min`, and
> `answers_from_harness_yaml` reads them, but the `economics:` block in both
> templates listed only the six pre-existing keys. A user who tuned a span cap had it
> reverted to the default on the next `--update`. Fixed here, pinned the same way.
> **Checkpoint 6 needs restating: a bidirectional mapper is write→read AND read→write;
> testing only the reader is half a loop and reads as a full one.**
>
> **Two defects only execution could find:**
> - Under `strict=True`, `model_validate` rejects a JSON **list** for a `tuple` field,
>   so every well-formed agent receipt would have been reported as schema-violating.
>   Identical class to Phase 1's ISO-string datetime — fixed with
>   `model_validate_json`. Two instances now; treat "strict + JSON payload ⇒ use the
>   JSON validator" as settled.
> - `git diff --stat HEAD` reports TRACKED modifications only, and a wrapup's changes
>   are typically new files that were never added. The agent's one view of change size
>   read empty on exactly the tasks that produced the most. `_diff_stat` now
>   summarises untracked paths explicitly.
>
> **The vault reconciliation was tautological as first written.** Positive control:
> vault with one matching note; negative: vault EMPTY. The only varied dimension was
> emptiness, so `vault_root given and any *.md present → ok` passed both — meaning the
> anti-fabrication guarantee for the one number CLAUDE.md relies on (`M promoted`) was
> not tested at all. Replaced with a decoy note (the realistic shape: the agent
> promoted something in an earlier round) plus a substring case.
>
> **Adding an agent touches FIVE sites**, each caught by a different structural test
> rather than by review: `synthesize._ALL_AGENTS`, `_COMMUNICATION_VARIANT`,
> `_CODEX_AGENT_META`, `presets._PRODUCTION_MAP` + `_SIDE_MAP`, and the
> `test_communication_audit` dispatcher-count pin. The gates worked; the surface is
> worth knowing before the next agent.
>
> **Naming debt, accepted:** `wrapup_brief.py` / `wrapup_receipt.py` also serve verify
> (Phase 6). `stage_brief` / `stage_receipt` would be the honest names, but this
> phase's exit criterion names the test files literally, and renaming would make the
> criterion unverifiable against its own PLAN. Left as-is with the docstrings stating
> the scope.

- `depends_on`: []
- `parallel_group`: `serial-carry`
- `merge_hazards`: `render.py`, snapshot expectations, asset models, `synthesize.py` communication-variant table; **must not run concurrently with Phase 2**
- **Scope in:** `wrapup_brief.py`; `wrapup_receipt.py`; new agent template with
  `communication_variant`; `delegation.stages` key **with its `InterviewAnswers`
  mirror and `answers_from_harness_yaml` mapping**; absent-key fallback
- **Scope out:** any change to wrapup/verify stage templates
- **Exit criterion:** `uv run pytest tests/unit/test_wrapup_brief.py
  tests/unit/test_wrapup_receipt.py -q` green, with per-field cases whose
  assertion names *that* field; cases rejecting empty-string, whitespace,
  wrong-root and cross-task-slug values; a positive control so an
  always-raising validator fails; a case proving a non-derivable missing field
  yields the degraded verdict rather than an exception; a config round-trip
  test; `/hm:health` Layer 1 `communication_protocol` reports no silent miss
- **Risk:** low
- **Rollback:** revert; no consumer yet

### Phase 5 — wrapup delegation (config-gated) — **DONE**

> **Status: done.** Step 0.5 dispatch + retained inline body under a degraded heading;
> 12 render tests green; `test_render_worktree_preflight` still green.
>
> **Measured sizes** (body lines, `feature_branch_workflow` on):
>
> | preset | delegate off | delegate on | delta |
> |---|---:|---:|---:|
> | Side | 662 | 712 | +50 |
> | Production | 695 | 745 | +50 |
>
> **The exit criterion's "stays within the context-lint threshold" could not be met
> literally, and pretending otherwise would have been the third substitution in this
> plan.** Two facts:
> - The command was ALREADY past `context_lint.THRESHOLDS[("workflow", Production)]`
>   = 600 before this phase added anything (695).
> - Nothing ENFORCES that threshold on an atomic stage command:
>   `readiness._CONTEXT_LIMITS` has no command row and `context_lint.lint()` is never
>   called by the renderer. It is a yardstick, not a gate.
>
> So the test pins the **delta** (+50, bounded at 60) — the quantity this phase
> actually owns — plus an exact line-count pin on the delegate-OFF render, which is
> the artifact that ships while `delegation.stages` is empty. Existing users pay zero
> lines; only an opt-in pays the growth.
>
> **A fixture defect worth remembering:** constructing `InterviewAnswers` directly
> bypasses `interview()`'s `_preset_extras`, so `worktree.feature_branch_workflow` is
> absent and the flag-gated Step 7.7 (`task-land`) does not render at all. A test
> asserting its presence was measuring the fixture, not the template.

- `depends_on`: [4]
- `parallel_group`: `serial-carry`
- `merge_hazards`: `templates/stages/wrapup.md.j2` — **must not run concurrently with Phase 2**
- **Scope in:** dispatch block with the runtime self-skip
  ([ADR-002](#adr-002)); the inline body retained under the degraded heading
  ([ADR-006](#adr-006)); brief derivation + validation; receipt reconciliation
  before commit; Steps 6–7.7 stay inline ([ADR-004](#adr-004))
- **Scope out:** verify
- **Exit criterion:** `test_render_worktree_preflight.test_wrapup_lands_task_branch_when_flag_on`
  still green; render tests assert the delegate-on artifact contains **both**
  the dispatch and the inline body, and that the rendered command stays within
  the context-lint threshold; a real `/hm:wrapup` with delegation on produces
  wiki + failures entries whose slugs the receipt reconciliation confirms
  against the tier files
- **Risk:** high — where memory quality can silently degrade
- **Rollback:** `delegation.stages: []` (config, not release) — the point of
  [ADR-011](#adr-011); code rollback is Phase 4

### Phase 6 — verify delegation + pre-registered re-measure

> **PRE-REGISTRATION, recorded 2026-07-26 while `delegation.stages` is still empty
> and no wrapup has ever run delegated.** Registering it after the fact would let the
> threshold be chosen to fit the result.
>
> Baseline, `economics report --root .` on this repo, 30-day window:
>
> | stage | turns | USD (list-price equiv.) | carry | mean ctx/turn |
> |---|---:|---:|---:|---:|
> | `hm:wrapup` | 1,354 | $1,120.67 | 0.819 | 454,701 |
> | `hm:verify` | 174 | $123.54 | 0.830 | 394,844 |
>
> **Registered threshold:** for a comparable wrapup, `by_stage["hm:wrapup"].total_usd`
> per turn-matched workload does not increase. Because [ADR-009](#adr-009) nests
> sidechain turns into the enclosing stage span, that figure **is** the all-in total —
> nothing is added to it, so delegation cannot improve it merely by moving turns.
>
> **⚠️ This comparison is NOT evaluable inside this task, and saying otherwise would
> repeat a substitution this plan has already caught itself making twice.** Two
> independent reasons:
> - The criterion is scoped to **ledger-attributed sessions**, and `ledger` currently
>   holds **0 of 19,310** turns — the emitter ships on this branch but the *installed*
>   plugin is 0.43.0, so no span has ever been written. The population is empty.
> - `delegation.stages` is empty by default ([ADR-011](#adr-011)) and stays empty for
>   one release, so there is no delegated wrapup to compare against.
>
> The comparison is therefore a **post-land soak item**, on the same footing as
> Phase 2's disagreement-rate item: re-run it after this work lands, the harness is
> re-rendered, and ≥10 delegated wrapups have accumulated (the [ADR-011](#adr-011)
> soak exit). Phase 6's code can ship; its acceptance number cannot be produced yet,
> and the checkbox in Success Criteria must stay unticked until it is.

> **Status: code DONE, acceptance number DEFERRED (see the pre-registration above).**
> `verify.md.j2` Step 0.5 + retained inline checks; the brief generalised to any
> `DELEGATABLE_STAGES` member (not loosened to a free string — a brief for a stage
> with no dispatch block is still rejected); 17 tests green.
>
> **The verify receipt needed its own observable state.** Reusing the wrapup shape
> verbatim would have given verify a reconciliation containing nothing: every memory
> field is legitimately empty for verify, so any claim reconciles clean. Added
> `record_path` (the JSONL record verify appends — a run that left no trace is now
> catchable) and `checks[]` with a CLOSED `PASS | FAIL | SKIP` enum, plus
> `verify-result-inconsistent`: `result: PASS` while a check said FAIL. That is the
> mirror of the promotion arithmetic and the one mismatch that must never be smoothed
> over, because verify is a **gate** — a relayed "all green" lets the pipeline past
> the thing that was supposed to stop it. The rendered command says so: an
> unreconciled receipt is never a PASS.
>
> **Two render assertions were position-invariant and passed on first run.**
> `"Check 1 —" in body` holds because the check definitions sit near the top of the
> document — it would pass even if the degraded heading pointed at nothing; and
> `"STOP" in body` is satisfied by the pre-existing "STOP on first FAIL" header, so it
> would pass even if the dispatch handed the gate decision to the subagent. Narrowed
> to an ORDER assertion and a dispatch-section-scoped one respectively. Both are the
> repo's `assertion-invariant-over-named-dimension` pattern, caught by suspicion at 17
> instant passes rather than by a gate.

- `depends_on`: [2, 3, 5]
- `parallel_group`: `serial-carry`
- `merge_hazards`: `templates/stages/verify.md.j2`
- **Scope in:** the same pattern for verify; the [ADR-006](#adr-006) secondary
  A/B of one delegated wrapup's output against the last inline one; the
  re-measure against the threshold registered **before** Phase 5 lands
- **Scope out:** the incremental-capture follow-up (Non-Goal 3)
- **Exit criterion:** the pre-registered comparison below is evaluated and
  reported with N and the workload control, on ledger-attributed sessions only
- **Risk:** medium
- **Rollback:** `delegation.stages: []`; code rollback is Phase 5

---

## ⚠️ Handoff note for `/hm:wrapup` — expected land conflict

`main` advanced to `c424dbc9` ("prune retired allow rules from existing harnesses")
while this task branch was open, and the two changes overlap:

| File | `c424dbc9` | This branch |
|---|---|---|
| `templates/settings/{Production,Side}.json.j2` | `permissions.allow` prune | `hooks.Stop` + `hooks.PreCompact` additions |
| `tests/snapshot/*.expected.yaml` (8) | `content_hash` bump | `content_hash` bump |

The `.j2` pair touches different regions and should auto-merge. **The eight snapshot
fixtures will conflict and must NOT be hand-merged** — they are generated artifacts
whose `content_hash` values are only meaningful when produced together. The correct
resolution is:

```bash
# after the rebase/land resolves the .j2 files
uv run python tests/snapshot/regenerate.py
uv run pytest tests/unit/test_synthesize_snapshot.py -q
```

Regenerating from inside the task worktree is safe here — `regenerate.py:107-125`
pins `_HARNESS_MAKER_PKG_ROOT` and `_compute_install_ref`, which was verified during
Phase 2 by grepping every fixture for the worktree path (zero hits). This supersedes
the `[fail:test] snapshot-regen-inside-worktree` memory (count:11); that entry should
be corrected at wrapup rather than followed.

`task-refresh` could not be run from execute: it refuses a dirty worktree, and
execute deliberately leaves its work uncommitted for wrapup to own.

### Memory corrections owed at wrapup

1. **`[fail:test] snapshot-regen-inside-worktree` (count:11) is STALE** — see the
   paragraph above. Correct the entry; do not merely re-file it.
2. **A new failure entry is owed: the reader-only bidirectional mapper.** Checkpoint 6
   is write→read AND read→write, and testing only `answers_from_harness_yaml` reads as
   full coverage while the `.yaml.j2` template silently drops the key on the next
   `--update`. Two live instances found in this task (`delegation.stages`, and
   `economics.span_max_*` which Phase 1 had already shipped that way).
3. **A wiki entry is owed: `strict=True` + a JSON payload ⇒ use `model_validate_json`.**
   Two instances now — the span ledger's ISO datetime and the receipt's list-for-tuple.
   In both, the Python-mode validator rejected every well-formed record, and in both
   only a round trip found it.
4. **A wiki entry is owed: adding an agent touches five registration sites** —
   `synthesize._ALL_AGENTS`, `_COMMUNICATION_VARIANT`, `_CODEX_AGENT_META`,
   `presets._PRODUCTION_MAP` + `_SIDE_MAP`, and the `test_communication_audit`
   dispatcher-count pin.
5. **The Bash-tool cwd hazard** is already saved to the session memory directory
   (`feedback-bash-cwd-persists-across-calls`); no action needed beyond awareness that
   a stray `cd` made a `git status` read like data loss during Phase 3.

---

## 🧪 Testing Strategy

**Unit** (mock-first)
- Span close: one case each for close-by-next-start, close-by-session-end,
  close-by-turn-cap, close-by-duration-cap, each pinning the resulting
  attributed turn count. A "result is non-empty" assertion would pass against an
  implementation ignoring the cap; these do not.
- Cap boundary pinned on **both** sides — a one-sided pin is the
  `fence-position-test-pins-only-upper-boundary` failure.
- Terminal `capped`: a late `end` and a later `start` each fail to extend.
- Per-source conservation + a positive control where an implementation
  attributing nothing fails.
- Absent start: turns before the first start stay unattributed, never
  back-filled.
- Absent `session_id`: join degrades and `ambiguous_session_join` increments.
- Base-root: emitting from `.worktrees/<slug>/` appends to the BASE ledger.
- Brief: one case per required field whose assertion names that field; empty
  string, whitespace, wrong root, cross-task slug all rejected; a positive
  control so an always-raising validator fails; a non-derivable missing field
  yields degraded, not an exception.
- Receipt: reconciliation fails when a claimed slug is absent from the tier
  file, and when the promotion count exceeds observed promotions.
- Classifier: cache miss, unparseable verdict, and no-user-message boundary each
  yield `unknown` + counter, never continuation.
- Config round-trip for all three new keys (`extra='forbid'` regression).
- `ratio_field_kinds()` still rejects every new field.

**Render gates**
- Every stage template passes `--stage` to its preflight call.
- The flag-off render emits nothing (the exemption is pinned).
- The delegate-on wrapup carries both the dispatch and the inline body, within
  the context-lint threshold.

**Integration**
- `tests/integration/test_stage_spans_e2e.py` — render into a tmp project,
  execute the stage's CLI lines directly, assert both records and that
  `economics report` labels those turns `attribution_source: "ledger"`.
- Ledger-vs-`attributionSkill` agreement over the local corpus (< 1%).
- `INTEGRATION=1` guard on anything invoking a real LLM.

**Manual**
- One delegated `/hm:wrapup` compared against the last inline one.
- `/hm:health` after Phases 4 and 5.
- Cursor and Codex render inspection (manual by CLAUDE.md checkpoint 8),
  specifically that the dispatch block self-skips.

---

## ⚠️ Risks & Mitigation

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R1 | Delegated wrapup produces shallower memory with no failing signal | medium | high | [ADR-006](#adr-006) validated brief; [ADR-012](#adr-012) receipt reconciled against tier files; [ADR-011](#adr-011) default-off soak; Phase 6 A/B |
| R2 | Span close over-attributes post-stage conversation | medium | high | Caps are independent rejections calibrated from the CDF; overflow visible as `capped_turns`/`capped_usd`; higher on Cursor/Codex by [ADR-003](#adr-003) |
| R3 | Emission lost when a stage is interrupted, compacted, or the model skips preflight | medium | medium | Emission coupled to a load-bearing call; the ground-truth disagreement rate (< 1%) is the detector; [ADR-003](#adr-003) defines both absent cases |
| R4 | Classifier mislabels a new task as a continuation | medium | medium | `unknown` never defaults to continuation; verdicts cached, versioned, inspectable |
| R5 | Phases sharing `render.py` / templates run concurrently | high | low | Both groups `serial-*`; Phase 2 ↔ 4 and Phase 2 ↔ 5/6 carry reciprocal `merge_hazards` |
| R6 | New report fields reintroduce a cost-per-count ratio | low | high | Every new field is a sum or a count; `ratio_field_kinds()` scan |
| R7 | Baseline and result come from different sources | medium | medium | Per-turn source labelling; Phase 6 compares ledger-attributed sessions only, or states that it cannot |
| R8 | Delegation moves cost into sidechain turns that fall outside every span | medium | high | [ADR-009](#adr-009) nests them into the enclosing span; `by_stage["hm:wrapup"]` is the all-in total |
| R9 | A misbehaving delegated agent runs git despite [ADR-004](#adr-004) | low | medium | Accepted; documented as instruction-not-enforcement; `PreToolUse` agent-identity hook is the named upgrade |
| R10 | Cursor renders a dispatch its runtime does not support | medium | low | Runtime self-skip to the inline body ([ADR-002](#adr-002)), the `stage_end_summary.md.j2` precedent; manual render check |
| R11 | **Loop and flag-off populations stay unmeasured, and that reads as "fixed"** | high | medium | Both are Non-Goals 1–2, named in the Executive Summary table, pinned by a Phase 2 test, and every coverage criterion below names the population it applies to |
| R12 | `delegation.stages` is dropped on re-render, silently reverting the rollback switch | medium | high | `InterviewAnswers` mirror + `answers_from_harness_yaml` mapping in Phase 4 scope, with a round-trip test (checkpoint 6) |

---

## ✅ Success Criteria

> **Legend, added at execute close (2026-07-26).** `[x]` = met and verified in this
> task. `[~]` = **not evaluable yet, deliberately left unticked** — every one of these
> is scoped to *ledger-attributed sessions*, and the ledger holds **0 of 19,310**
> turns because the emitter ships on this branch while the installed plugin is 0.43.0.
> The population is empty, so ticking them would report a measurement nobody made.
> They become checkable after this lands, `/harness-maker:make --update` re-renders,
> and real spans accumulate. Do not convert a `[~]` to `[x]` on the strength of a unit
> test: the unit tests prove the COMPUTATION, the corpus proves the CLAIM, and
> substituting the first for the second is the error this plan has now caught itself
> making three separate times.

Every coverage criterion names its population — the second validation pass found
that unqualified ones were vacuously true for the exempt populations.

- [~] **On ledger-eligible sessions** (`feature_branch_workflow: true`,
      non-loop), every priced in-window turn carries an `attribution_source`,
      and the per-source USD totals sum to `total_usd`
- [~] **On those sessions**, `(unattributed)` contains no mid-stage continuation
      run other than the capped remainder, reported as `capped_turns` /
      `capped_usd`
- [~] Ledger spans disagree with ground-truth `attributionSkill` on **< 1%** of
      turns carrying both, with the count reported
- [x] `/hm:loop` spend is attributed to `hm:loop` at **loop** level rather than
      to `(unattributed)`; per-stage granularity inside a loop is **not**
      claimed (Non-Goal 1)
- [x] `feature_branch_workflow: false` harnesses get **execute-only** ledger
      coverage — a test pins that `worktree create execute` emits there and that
      the other six stages do not (Non-Goal 2, as corrected)
- [x] Every stage row reports its source breakdown, never a single label
- [~] **Pre-registered before Phase 5 lands:** for a comparable wrapup,
      `by_stage["hm:wrapup"].total_usd` — which, because
      [ADR-009](#adr-009) nests sidechain turns, **is** the all-in total, with
      nothing added — does not increase. Stated with N, the comparison window,
      and the workload control. *(This replaces the first draft's "entry context
      below 439k", which [ADR-004](#adr-004) falsifies by construction, and the
      second draft's `by_stage + by_agent` sum, which double-counted the
      delegated turns.)*
- [x] `hm:verify` receives the same treatment (code; the number is deferred with the row above)
- [x] A wrapup missing a non-derivable brief field runs the **rendered** inline
      body with a loud warning rather than failing
- [x] The delegated body's receipt reconciles against the tier files before commit
- [x] `delegation.stages` defaults to empty, an absent key keeps inline
      behavior, and the key survives a `harness.yaml` round-trip
- [x] No cost ÷ deliverable-count field exists anywhere in the report schema
- [x] Full suite green: `uv run pytest`, `ruff check`, `ruff format --check`,
      `mypy --strict`

---

## 🔍 Plan Validation

### Round 1 — cross-model second opinion (Production preset: every enabled model, mandatory)

| model | status | outcome |
|---|---|---|
| `codex` | `invoked` | 19 findings (5×P0, 13×P1, 1×P2) |
| `antigravity` | `invoked` | 7 findings (1×P0, 3×P1, 3×P2) |

### Round 1 — `plan-validator`: `MAJOR_REVISION` (6 critical, 6 warning)

Resolutions proposed via Interview Round 4 and direct revision: V1 → new
[ADR-009](#adr-009) + sidechain probe · V2 → new [ADR-008](#adr-008) ·
V3 → [ADR-004](#adr-004)/[ADR-007](#adr-007) downgraded to
instruction-not-enforcement · V4 → [ADR-006](#adr-006) degraded path ·
V5 → new [ADR-010](#adr-010) · V6 → per-target clause · V7 → all-in criterion ·
V8 → CDF-calibrated caps · V9 → phase graph · V10 → named e2e test ·
V11 → new [ADR-011](#adr-011) · V12 → Non-Goals + frontmatter.

Second-opinion findings **refuted with code evidence** — recorded so they are
not re-raised:

- antigravity **P2-A7** ("subagent writes memory into the worktree and loses it
  at `task-land`") — `memory_md._base_root()` (`:71-90`) already resolves to
  BASE, and `wrapup.md.j2` already folds base memory into the squash via
  `commit-base-memory --expect-head`. The surviving narrow concern (a subagent
  inherits the *main session's* cwd) is handled by [ADR-006](#adr-006)'s derived
  root fields.
- antigravity **P1-A4** ("Phase 4 asserts only that a missing field raises") —
  the draft already required the assertion to name the field. The residual
  (positive control) was adopted.
- codex **P2-C14** — largely duplicate; the residual empty-string / wrong-root
  cases were adopted.

### Round 2 — `plan-validator` re-run: `MAJOR_REVISION` (5 new critical, 6 warning, 3 suggestion)

V3, V5, V8, V12 confirmed resolved. The re-run budget (one) is now spent. The
new findings were **verified against the code by the author** before acting on
them — all five criticals were correct:

| Finding | Verified | Resolution in this revision |
|---|---|---|
| N1 `/hm:loop` never emits — `loop.md.j2:990` says "do NOT run `task-preflight`" | ✅ grep returns only the skip block | [ADR-008](#adr-008) gives loops **iteration-level** spans from `worktree create`; per-stage granularity is **Non-Goal 1**; the false ✅ deleted |
| N2 `task-preflight` cannot produce the record — no stage, no session, fresh `uuid4()` per call | ✅ `worktree.py:4908-4922` | Record cut to observable fields; `turn_uuid` **dropped**; `--stage` added as an explicit arg with a render gate; `session_id` best-effort with a defined absent case |
| N3 conservation + all-in criterion uncomputable and mutually contradictory | ✅ `economics.py:418` / `:419-422` double-accumulate | [ADR-009](#adr-009) narrowed to **per-source** conservation; `by_agent` stays a cross-cut (**Non-Goal 6**); the criterion is now `by_stage["hm:wrapup"]` alone |
| N4 flag-off harnesses have no emission point at all | ✅ all 7 stages gate the partial on `feature_branch_workflow` | Declared **ledger-exempt** (Non-Goal 2), surfaced in the Executive Summary table, pinned by a Phase 2 test |
| N5 no `is_cursor` context; cursor commands are single-source | ✅ grep returns nothing; `_cursor_target_files()` renders 3 files | [ADR-002](#adr-002) replaced the render branch with a **runtime self-skip**, citing `stage_end_summary.md.j2:24-28` |
| N6 degraded path had no inline body to reach | ✅ | [ADR-006](#adr-006): the delegate-on render carries **both**; render assertion added; context-lint cost noted |
| N7 no `InterviewAnswers` mirror (checkpoint 6) | ✅ `extra='forbid'` + four precedent mirrors | Mirror + `answers_from_harness_yaml` mapping in Phase 4 scope; round-trip test; R12 |
| N8 Phase 2 ↔ 4 share `render.py` across groups | ✅ | Reciprocal `merge_hazards` added |
| N9 disagreement threshold never stated | ✅ two sections deferred to each other | **< 1%** stated in Phase 2; Success Criteria cites it |
| N10 ADR-008 overstated its guarantee | ✅ | Softened to a coupling argument with the residual named |
| N11 `Stop`/`PreCompact` are Claude-Code-only | ✅ | [ADR-003](#adr-003) states it; Cursor/Codex rely on cap closure; reflected in R2 |
| N12 key name / no soak exit | ✅ | Renamed `delegation.stages`; soak exit = 10 clean receipts |
| N13 duration denominator 71 vs 143 | ✅ probe defect | **Re-measured over the full 144-run set** (0 missing); length CDF also corrected (144 runs / 10,249 turns); conclusions unchanged |
| N14 frontmatter pre-declared the verdict | ✅ | Corrected, then set to `MAJOR_REVISION_RESOLVED_SELF_REVIEWED` |

### Round 3 — self-review (validator re-run budget exhausted)

Per the stage's no-infinite-loop rule, the user chose to narrow scope and close
by self-review. What that review changed beyond the table above: every coverage
claim in Success Criteria now names its population; three new report counters
(`ambiguous_session_join`, `unknown_stage_emissions`, and the disagreement
count) exist so that each newly-bounded gap is *reported* rather than merely
documented; and R11 records the residual risk that a bounded fix reads as a
complete one.

**Known limitations carried into execute, deliberately and not as oversights:**
per-stage attribution inside `/hm:loop`; the entire `feature_branch_workflow:
false` population; session-end closure on Cursor and Codex; and the fact that
[ADR-008](#adr-008)'s emission is a coupling, not a guarantee — its detector is
the < 1% disagreement rate, not a proof.
