---
type: research
task_slug: intent-world-model-objective-layer
status: complete
created: 2026-09-15
tags: [harness-maker, research, product-direction, intent, world-model, outcome-eval, decision-memory]
mtime_warn_days: 7
libs_fetched: []
sources:
  - https://arxiv.org/abs/2608.02113
  - https://github.com/alexisfox7/PRO-LONG
  - https://arxiv.org/pdf/2606.30306
  - https://arxiv.org/html/2606.08571v1
  - https://arxiv.org/abs/2606.30639
  - https://arxiv.org/pdf/2603.03456
  - https://arxiv.org/pdf/2603.03258
  - https://tianpan.co/blog/2026/05/17/agent-specification-gaming-agentic-loops
  - https://github.com/github/spec-kit
  - https://docs.bmad-method.org/reference/skills-and-agents/
  - https://daniliants.com/insights/understanding-spec-driven-development-kiro-spec-kit-and-tessl/
  - https://www.marktechpost.com/2026/05/08/9-best-ai-tools-for-spec-driven-development-in-2026-kiro-bmad-gsd-and-more-compare/
  - https://sourcegraph.com/blog/context-engineering
  - https://www.morphllm.com/ai-agent-evaluation
  - https://mem0.ai/blog/claude-code-memory
related_docs:
  - "[[RESEARCH-harness-diet]]"
  - "[[RESEARCH-harness-maker-cold-eval]]"
  - "[[PLAN-harness-diet]]"
  - "[[RESEARCH-context-carry-economics-2026-07-28]]"
  - "[[PLAN-workflow-steps-vs-model-capability]]"
summary: "Intent + fact-state + outcome-eval under .claude/; codex data model + this doc's cost discipline; hold objective generation."
---

# RESEARCH — Intent / World Model / Objective / Eval / Autonomy layer

## 🎯 Recommended Direction

**The proposal is directionally right and lands exactly where this repo already decided to
invest — but it is five subsystems where three would do, two of the eight items are already
built, and the highest-risk item does not need to be stored at all.**

Recommended shape (informational; `/hm:plan` decides):

1. **Ship three things, as one small PLAN:** `intent` (mission / vision / outcomes /
   non-negotiables / non-scope / unknowns), **outcome eval** (`baseline` / `target` /
   **`measure_cmd`** + an append-only `outcomes.jsonl` written by `wrapup`), and
   **decision-revisit** (`revisit_when` on existing Second Brain `decision` notes + an
   advisory gate in `/hm:plan`).
2. **Do not store the objective *candidate list*; do store the objective the human *picks*.**
   With intent-outcomes and measured baselines present, candidates are derivable at read time —
   `hm status` / `hm next` computes the gap and has Claude rank it, and nothing is written. But
   the selected objective carries things a metric gap cannot reconstruct: the causal hypothesis,
   the assumptions it rests on, what was rejected and why, and its revisit condition. Persist
   *that* — one record per selected objective, in the same `decision`-note shape as item 3, so
   there is one memory mechanism rather than two. (Corrected after cross-model review; the
   original claim that a derived view has "zero staleness, zero drift" was wrong — its inputs
   stale, and the same inputs can yield a different ranking on a different run.)
3. **Do not build a `.harness/` tree.** It invents a third state root beside `.claude/`
   (harness-owned) and `work-docs/` (deliverables), and every piece of this repo's churn
   machinery — `_HARNESS_CHURN_PREFIXES`, gitignore append, both dirt-filters, the
   create-guard deliverable exemption, Second Brain promotion paths — is keyed to those two.
   One file, `.claude/intent.yaml`, plus one ledger under `.claude/observability/`.
4. **Autonomy is already shipped.** `autonomy.{level,pipeline,step_cap,time_cap_min,extra_deny,autopilot_persistent}`
   + `autopilot_caps` + the 7-stage pipeline exist and run. Solo mode needs **nothing** here.
5. **Do not add a Solo/Cell mode axis.** `preset` × `dev_mode` × `targets` already multiply the
   render matrix that `tests/structural/test_step_sensitivity_registry.py` (`ARMS`) has to
   cover. Gate Cell features on *presence of an `owners:` block*, not on a fourth axis.

**Why this and not the full build:** this repo's own most recent strategic research
([[RESEARCH-harness-diet]], 2026-08-05) measured that five fused workflow commands were
**512,808 of 876,301 rendered command bytes (58.5%) with zero recorded invocations**. That is
a large, expensive, fully-shipped feature with no user. The proposed layer is precisely the
instrument that would have caught it — and it is also precisely the kind of build that
produced it. Ship the measurement half first; let it earn the ideation half.

## 🔍 Refinement Decisions

`--deep` not set; Phase 0 skipped.

**Discovery lens (Phase 0.75):** (1) **User-workflow / product opportunity** — primary; the
question is "would this change what a solo maintainer or a 3-person Cell actually does on a
Monday". (2) **Technical architecture** — what already exists in this 59,248-LOC codebase, so
the proposal is not re-specified on top of shipped code. (3) **Research / benchmark** —
secondary, used for the two novel mechanisms (epistemic tri-state, outcome-driven objective
selection) and for the risk section. (4) **Risk** — goal drift / Goodhart, the failure mode
the proposal does not name.

**Second Brain:** `second_brain.enabled: true` for this repo; `--type reference` and
`--type project` searches for this topic returned `[]`. No prior vault context — noted as a
fact, not a gap.

### Local capability × user artifact matrix

| Artifact the user already maintains | harness-maker capability today | Gap the proposal fills |
|---|---|---|
| README / pitch / the "why" in the founder's head | none — `harness.yaml` stores *how to build*, never *why* | **Intent** |
| GitHub Issues, TODO, 131 `work-docs/PLAN-*.md` | PLAN→SPEC→stage chaining via frontmatter | objective **ranking**, not storage |
| Obsidian vault | `second_brain promote` (wrapup 5.6); `/hm:plan` already searches `--type decision` | `revisit_when` **condition semantics** |
| CI / pytest output | `verify` Check 2, `test_runners`, `test_dep_map` | nothing above test level |
| Analytics, user interviews, support threads | **nothing** | **outcome eval** |
| git history | `delivery_metrics` (CFR + post-merge churn) — *process* metrics | *product* delta |
| `.claude/memory/{wiki,failures}.md` | wrapup fold, `memory_retrieve`, `[fail:design]` oscillation anchor | experiment results **with numbers** |

## 🛠️ Approaches Found

### Item-by-item review of the proposal against repo reality

| # | Proposal item | What already exists | Verdict |
|---|---|---|---|
| 1 | Intent / Intake | Nothing. The `make` interview asks locale, targets, toolchains, reviewers, worktree — never purpose. | **New and cheap.** But *table stakes*: BMAD ships an Analyst Project Brief → PM PRD chain and Spec Kit ships `/constitution`. Not a differentiator. |
| 2 | World Model (`known/assumed/unknown`) | Partial: `wiki.md` (patterns), `failures.md` (652 lines), `pending-drift.md`, `pending-proposals.md` (482 lines). No epistemic status, no current-state snapshot. | **The tri-state is the genuinely novel bit.** The rest of the proposed tree duplicates memory tiers. |
| 3 | Objective generation | Nothing. | **New, and the highest-risk item.** See Pitfalls 2. Recommend *computed*, not stored. |
| 4 | Objective → Spec | `/hm:spec` exists; **cheapest stage in the harness at $15 / 0.5% of spend**. | **~90% exists.** Needs an `objective:` frontmatter field, not a stage. |
| 5 | Eval / Outcome | `delivery_metrics` = CFR + churn (DORA-ish, git-derived). `economics` = $/turn/carry. `readiness` = harness health. **Zero product metrics anywhere.** | **New, and the single highest-value item.** |
| 6 | Ownership + Autonomy | `autonomy.*` block + `autopilot` + `autopilot_caps` + `auto_safe` level **shipped and running in this very session**. Ownership absent. | **~80% built.** Solo: no work. Cell: one `owners:` block. |
| 7 | Decision / Experiment memory | Second Brain `decision`/`failure`/`preference` note types exist; **`/hm:plan` already searches `--type decision` before Step 1**; wrapup Step 5.6 promotes; wrapup already records design *oscillation* as `[fail:design]` anchored to the prior `[wiki:*]` decision. | **~70% built, advisory-only.** Missing: `revisit_when` + evaluation of it. |
| 8 | Cell status view | `/hm:health`, `/hm:metrics`, `.claude/observability/dashboard.md` — all report *harness* health, never *product* progress. | Trivial **if** 1/2/5 exist; meaningless otherwise. |

### Approach A — Build all five subsystems as proposed

| Field | Content |
|---|---|
| Approach | `.harness/world/` tree with intent/state/sources/objectives/decisions/experiments/risks/unknowns + `hm status` + `hm next` |
| Assumption | The maintainer will dogfood all five simultaneously and each earns its surface |
| Evidence | Against: the 58.5%-dead-fused-command measurement; 131 PLANs in 4.5 months of which 49 (37%) are internal plumbing/defect work; `surface_allowance.py` + a frozen `surface_baseline.json` (427,369 claude chars) exist *because* growth already outran value once |
| Trade-off | Maximum coverage, bought with the highest probability that 2–3 of the 5 go unused |
| Compatibility | Poor: a third state root breaks the `.claude/`-keyed churn/gitignore/dirt-filter/create-guard machinery |
| Risk | **high** |

### Approach B — Outcome-first slice ("measure before you steer")

| Field | Content |
|---|---|
| Approach | `intent` (6 fields) + `evaluations` with `baseline`/`target`/**`measure_cmd`** + a wrapup step that runs each `measure_cmd` and appends to `.claude/observability/outcomes.jsonl` + a read-only `hm status` |
| Assumption | The binding problem is *"I cannot tell whether the last month of work moved the product"*, not *"I do not know what to do next"* |
| Evidence | The dead-fused-commands incident was a **measurement** failure, not an ideation failure. 131 PLAN files is not a shortage of ideas. Agent-eval practice converges on the same point: final-answer scoring "tells you almost nothing"; the loop needs production signal fed back (morphllm 2026) |
| Trade-off | Does not by itself answer "며칠 뒤 왜 이걸 하고 있었지" — but the `intent` block does, at ~30 lines of YAML |
| **Open defect** | **Measurement cadence is not the same as wrapup cadence.** Onboarding minutes and success rate do not move at code-complete; the effect appears after deploy, after users arrive, and is confounded by every other change in the window. Reading the latest value at each wrapup and feeding it straight into the next objective choice will mark not-yet-observable work as failed and steer away from it. Each row must record `measured_at`, the deploy/release ref it follows, and the observation window + sample conditions; and the *steering* read should run on its own cadence, not once per wrapup. Raised by the cross-model reviewer; unresolved here, see Open Question 7 |
| Compatibility | Excellent: reuses the JSONL ledger idiom, the `delivery_metrics` CLI shape, the wrapup receipt pattern, and the frozen-baseline + BASELINE-DELTA precedent |
| Risk | **low** |

### Approach C — Memory-first slice ("stop re-litigating")

| Field | Content |
|---|---|
| Approach | `revisit_when` + `revisit_metric` on Second Brain `decision` notes; an advisory gate at `/hm:plan` that evaluates the condition against the current measured value and surfaces "existing decision found / condition unmet / do not revisit"; experiment records with numeric results |
| Assumption | The binding problem is oscillation — the agent re-proposing what was already rejected |
| Evidence | For: this repo's `failures.md` already carries `[fail:design]` entries with `count:3` recurrence markers — **it has measured that this class recurs**. PRO-LONG (arXiv:2607.20064) reports append-only session logs + targeted search as the fix for "after compaction, agents repeat failed work". MemArbiter (2608.02113) frames the same as a decision-time arbitration problem. Against: wrapup's oscillation anchor already covers part of it |
| Trade-off | Cheapest of the three; also the least visible — no new command, no new view |
| Compatibility | Excellent: `/hm:plan` already runs the `decision` search; this adds a condition field and a verdict line |
| Risk | **low** |

### Approach D — Objective layer as a *derived view*, not stored state

| Field | Content |
|---|---|
| Approach | `hm next` reads `intent.outcomes` + the last row per metric in `outcomes.jsonl` + open `unknowns`, computes the gap table, and has Claude rank candidate objectives **in the turn**. Nothing is written. Selecting one writes only a normal `work-docs/SPEC-*.md` |
| Assumption | In Solo mode, the objective list has exactly one consumer (the maintainer, now) and therefore needs no durable representation |
| Evidence | `pending-proposals.md` is 482 lines — this repo already has a persisted proposal list, and its length is the evidence that such lists accumulate rather than resolve. Goal-drift literature (2603.03456, 2603.03258) shows stored agent-authored goals are the surface that drifts under contextual pressure |
| Trade-off | Cell mode eventually needs persistence for shared visibility — accept that as a later, evidence-triggered addition |
| Compatibility | Excellent: pure read path, adds no state, no gitignore entry, no dirt-filter class |
| **Counter (accepted)** | "Derived ⇒ no rot" does **not** follow. The inputs (`intent`, measured rows, `unknowns`) stale on their own, and an LLM ranking is not stable across runs on identical inputs. More importantly a metric gap cannot reconstruct the causal hypothesis, the dependency order, the cost estimate, or *why a candidate was rejected last month* — so a purely derived view re-proposes rejected work, the exact harm item 3 exists to stop. `pending-proposals.md` at 482 lines proves that lists get long, not that persistence is what made them rot |
| Risk | **low for the candidate list, medium if selection rationale is also left underived** |

### Where the differentiation actually is

Intent capture is table stakes by 2026 — BMAD (Analyst→PRD→Architect chain), Spec Kit
(`/constitution`, 90k+ stars), Kiro, OpenSpec and Tessl have each shipped a version of
"capture intent explicitly, upstream of generation". Shipping item 1 alone buys parity, not
advantage, and it must not displace the 2026-05-22 headline lock-in
(*"harness-maker reads YOUR repo and builds YOUR harness"*, [[RESEARCH-harness-maker-cold-eval]]).

Three things in the proposal have **no competitor equivalent found** in this search:

1. **Epistemic tri-state on project facts** (`known` / `assumed` / `unknown`). Closest prior
   art is academic, not product: Structured Ignorance Certificates (arXiv 2606.08571) trains
   models to emit structured metadata distinguishing known / known-unknown / unknown-unknown.
   No SDD tool found does this on *project* facts.
2. **A decision with a machine-checkable revisit condition.** Every tool stores decisions
   (ADRs, memory files, Auto Memory). None found evaluates *"is the condition that would
   justify reopening this actually met?"*
3. **Closing the loop from product metric back into the planning input.** Every SDD tool stops
   at "tests pass". `verify`'s six checks here are drift, regression, structural delta,
   security, worktree cleanliness, SPEC requirement — all code-level.

### Host-substitution check (does Claude Code already do this?)

Claude Code has shipped **Auto Memory on by default since 2.1.59 (Feb 2026)** — the model
maintains its own `MEMORY.md` per project. That is real overlap with unstructured decision
memory and it is free. It does **not** provide: a schema, a revisit condition, cross-IDE
portability (it does not follow you to Cursor or Codex), or any product metric. Per
`step_sensitivity`'s classes, unstructured recall is drifting toward **HOST**; the schema +
condition + external measurement stay **INV**. Build the INV half only.

## ⚠️ Pitfalls

1. **A `.harness/` root is a real, concrete break.** `worktree._HARNESS_CHURN_PREFIXES` drives
   gitignore appends, `_is_harness_artifact` (finalize dirt-filter) and
   `_is_create_guard_harness_artifact` (create-guard) from one shared tuple, all keyed to
   `.claude/` and `work-docs/`. A third root means: new gitignore entries, new dirt-filter
   membership, a new deliverable-exemption decision, and a Second Brain promotion path. CLAUDE.md's
   single-source principle says put it under `.claude/`.

2. **Self-reported outcome numbers are a textbook proxy-gaming setup.** An agent that proposes
   its own objectives from a gap analysis *and* reports the numbers it is judged on is the
   configuration the 2026 literature warns about: Goodhart in agentic loops (tianpan 2026-05),
   asymmetric goal drift in coding agents under value conflict (arXiv 2603.03456), inherited
   goal drift under contextual pressure (2603.03258). Mitigation that fits this repo's idioms:
   **`measure_cmd` is mandatory** — the harness runs a command and records its output, the
   model never types the number. The precedent is already in-tree:
   `step_sensitivity.py`'s TUNE entries carry `measure_cmd` / `remeasure_on` for exactly this
   reason. Second mitigation: **baselines freeze** like `surface_baseline.json`, and moving one
   requires a `BASELINE-DELTA-*` note.

   **This is necessary and not sufficient** (cross-model review, accepted). `measure_cmd` stops
   the model from *typing* the number; it does not make the measurement independent, because the
   same agent can edit the script, change which data it selects, or redefine the metric — and a
   frozen baseline does not close that path, since the baseline is a value and the definition
   is a separate artifact. The real question is *who verifies the number, against what evidence*.
   Minimum viable answer within this repo's existing idioms: the metric **definition** (command +
   data source + version) is pinned next to the baseline and hashed like everything else that
   carries `content_hash`, and any diff to a `measure_cmd` is a reviewed change rather than an
   incidental edit inside the task being measured.

3. **"Human selects, AI proposes" is not secured by making `hm next` read-only.** The proposal
   states the principle; a prompt instruction is not enforcement (CLAUDE.md is explicit that
   frontmatter `permissions:` blocks were cosmetic for exactly this reason). But a read-only
   recommender is *also* not enforcement: the calling agent reads the ranking and walks into the
   ordinary SPEC path by itself. That is not hypothetical here — `autonomy.level: auto_safe` with
   `pipeline: [research, spec, plan, execute, review, verify, wrapup]` and
   `autopilot_persistent: true` is armed in this repo **right now**, and stages auto-advance
   whenever no mandatory gate is pending. The control therefore has to sit on the
   **recommendation → executable SPEC boundary** — that transition needs a named approver and a
   recorded approval, i.e. a mandatory gate in the `autopilot_caps` sense — not on whether the
   recommender writes a file. (Raised by the cross-model reviewer; the original wording of this
   pitfall was wrong.)

4. **A stored objective *candidate* list rots.** `pending-proposals.md` (482 lines) and
   `pending-drift.md` are the local evidence that candidate queues accumulate faster than they
   resolve. Note the scope: this argues against persisting *candidates*, not against persisting
   the *selected* objective with its rationale — see Approach D's accepted counter.

5. **Intent captured once at `make` time goes stale.** BMAD's Project Brief has the same
   failure mode. The repo already has the fix pattern — RESEARCH frontmatter's
   `mtime_warn_days` — so `intent.yaml` should carry a staleness warning that `hm status`
   surfaces, and `/harness-maker:make --update` must **never** silently rewrite hand-authored
   intent (block-merge markers, like `AGENTS.md`).

6. **Adding a Solo/Cell axis multiplies the render matrix.** `ARMS` in
   `tests/structural/test_step_sensitivity_registry.py` already covers preset × dev_mode; every
   rendered heading in every arm must be classified. Gate Cell features on the presence of
   `owners:`, not on a mode.

7. **Building all five before dogfooding repeats the exact incident this layer exists to
   prevent.** 58.5% of rendered command bytes, zero invocations. The user's own rule —
   *"없어서 반복적으로 문제가 되는 것만 추가"* — applies to the user's own proposal.

   **Labeled as inference, with the counter-reading stated** (cross-model review, accepted):
   reading the dead-command incident as a *measurement* failure is my inference, and it is
   over-determined. The same observation supports a wrong demand assumption, a prioritization
   failure, or an absent stopping criterion — and each of those is an argument *for* the World
   Model and Objective layers this document defers. The defer decision therefore rests on
   sequencing economics (measurement is a precondition for evaluating either reading), not on
   having established that ideation is healthy here.

8. **Surface budget is a hard gate here.** The frozen baseline is 427,369 chars (claude) /
   362,326 (codex). A new rendered `/hm:status` slash command spends from it; a plain
   `hm status` CLI verb does not. Prefer the CLI verb, and take a `surface_allowance` in the
   PLAN frontmatter for whatever stage-prose the eval step adds.

## ❓ Open Questions

1. **Scope: dogfood or consumers?** Memory records a prior lock-in for the spec-tetrad work:
   *"대상 = 소비 프로젝트, harness-maker 자체 X."* This proposal explicitly wants Solo
   dogfooding first, which reverses it. Which applies here — and if dogfooding, does
   harness-maker's own `intent.yaml` ship in the repo or stay gitignored?

2. **Where does intent live?** `harness.yaml` is machine-rendered with `content_hash`
   provenance, so hand-edited prose fights the render/reconcile machinery. Separate
   `.claude/intent.yaml` with block-merge markers, or a marked block inside `harness.yaml`?

3. **Who verifies an outcome number, and against what evidence?** (Re-scoped after cross-model
   review — the original question, "is `measure_cmd` mandatory?", presumed that command-vs-manual
   was the axis that matters.) Sub-questions the PLAN must answer: is the metric *definition*
   pinned and hashed alongside the baseline; is a `measure_cmd` diff inside the task being
   measured allowed at all; and for outcomes with no command (onboarding minutes, interview
   findings), does `manual: true` + required `measured_at` + staleness warning suffice, or are
   un-machine-measurable outcomes refused?

4. **Advise or block?** The revisit gate: this repo's precedent is consistently *never-block*
   (plan-validator is PIDA/advisory; cross-model `unresolved` surfaces rather than halts).
   Does the decision-revisit gate follow that, or does it get `blocks_approval` like
   `lens_coverage`?

5. **CLI verb or slash command?** `hm status` / `hm next` as plain CLI verbs cost no rendered
   surface but are invisible to the IDE's command palette. Which trade does the PLAN take?

6. **Backfill or start-from-today?** 131 PLANs exist with no recorded outcome. Does adoption
   require any retro-attribution, or is the first measured row the baseline?

7. **What is the measurement cadence, and is it the same as any stage's cadence?**
   (Re-scoped after cross-model review — the original question only asked `wrapup` vs `verify`,
   which presumed measurement belongs on the per-task loop at all.) Product outcomes lag code
   completion by a deploy plus an observation window, and several tasks land inside one window,
   so a per-wrapup read attributes a flat metric to whichever task happened to finish last. Does
   the eval run on its own cadence (release-triggered, or scheduled) with wrapup merely
   *recording* which release a task entered? If it does sit in a stage: `wrapup` carries the
   highest context carry in the harness (0.84) and is already delegated to `stage-delegate`;
   `verify` is the cheapest stage ($11) and is a retirement candidate per [[PLAN-harness-diet]] —
   putting measurement in a stage that may be cut is a trap.

8. **Cell mode timing.** Is the 3-person Log Agent Cell a real near-term deadline that forces
   `owners:` / shared objectives now, or does Solo dogfooding genuinely come first?

9. **Does the recommendation → SPEC transition become a mandatory autopilot gate?** See
   Pitfall 3. With `auto_safe` + `autopilot_persistent: true` already armed, an ungated
   recommender is an autonomous objective-setter. Adding a gate here is the first time this
   harness would block autopilot on a *product* decision rather than a code one.

## 📚 Sources

- [MemArbiter: Decision-Time Memory Arbitration for Long-Horizon LLM Agents](https://arxiv.org/abs/2608.02113)
- [PRO-LONG — programmatic append-only memory for long-horizon coding agents (arXiv:2607.20064)](https://github.com/alexisfox7/PRO-LONG)
- [Always-On Agents: A Survey of Persistent Memory, State, and Governance in LLM Agents](https://arxiv.org/pdf/2606.30306)
- [Calibration of Structured Ignorance Certificates for Diagnosing Unknown Unknowns](https://arxiv.org/html/2606.08571v1)
- [Self-Evolving World Models for LLM Agent Planning](https://arxiv.org/abs/2606.30639)
- [Asymmetric Goal Drift in Coding Agents Under Value Conflict](https://arxiv.org/pdf/2603.03456)
- [Inherited Goal Drift: Contextual Pressure Can Undermine Agentic Goals](https://arxiv.org/pdf/2603.03258)
- [The Agent Optimized Exactly What You Measured: Goodhart's Law in Agentic Loops](https://tianpan.co/blog/2026/05/17/agent-specification-gaming-agentic-loops)
- [GitHub Spec Kit](https://github.com/github/spec-kit)
- [BMad Method — Skills and Agents](https://docs.bmad-method.org/reference/skills-and-agents/)
- [Understanding Spec-Driven Development: Kiro, spec-kit, and Tessl](https://daniliants.com/insights/understanding-spec-driven-development-kiro-spec-kit-and-tessl/)
- [9 Best AI Tools for Spec-Driven Development in 2026](https://www.marktechpost.com/2026/05/08/9-best-ai-tools-for-spec-driven-development-in-2026-kiro-bmad-gsd-and-more-compare/)
- [Context Engineering: A Practical Guide for AI Agents (Sourcegraph, 2026)](https://sourcegraph.com/blog/context-engineering)
- [AI Agent Evaluation (2026): Metrics, Frameworks, and Production Failures](https://www.morphllm.com/ai-agent-evaluation)
- [Claude Code Auto Memory, default-on since 2.1.59](https://mem0.ai/blog/claude-code-memory)

Internal measurements cited (reproduce with the commands named):

- Per-stage spend, fused-command byte share, VERIFY:PRODUCE ratios — [[RESEARCH-harness-diet]] (2026-08-05), `uv run python -m harness_maker.economics stages --root .`
- Frozen surface baseline 427,369 / 362,326 chars — `tests/structural/surface_baseline.json`
- 59,248 LOC / 511 test files / 131 PLANs (49 internal-plumbing-keyed) / repo age 2026-05-03 → 2026-09-13 — direct counts, this session

## 🧊 Cross-model second opinion (codex)

Two independent codex runs, recorded because they changed this document.

### Run 1 — adversarial review of this document (5 findings, all accepted)

| Finding | Disposition |
|---|---|
| "Derived ⇒ no rot" does not follow; inputs stale, LLM ranking unstable, a metric gap cannot reconstruct rejected-why | **accepted** — Recommended Direction item 2, Approach D counter, Pitfall 4 rewritten |
| Outcome measurement coupled to wrapup ignores observation lag + attribution across a release window | **accepted** — Approach B "Open defect" row, Open Question 7 re-scoped |
| `measure_cmd` stops typed numbers but does not buy independence; the same agent can edit script / data selection / metric definition | **accepted** — Pitfall 2 extended, Open Question 3 re-scoped |
| Read-only `hm next` does not structurally secure human selection — the calling agent walks into the SPEC path itself (and `auto_safe` + `autopilot_persistent` is armed here **now**) | **accepted** — Pitfall 3 rewritten, Open Question 9 added |
| "Measurement failure, not ideation failure" is over-determined; the same evidence supports wrong demand assumptions / prioritization failure, which argue *for* the deferred layers | **accepted** — Pitfall 7 labeled as inference with the counter-reading stated |

### Run 2 — independent design from the original brief only

Codex was given the user's proposal plus bare repo facts, and **no part of this document**.
It produced a full design. Where the two converge independently, confidence is high; where they
diverge, the divergence is the interesting part.

**Converged without contact** (both, independently): store under `.claude/`, never a new
`.harness/` root; `harness.yaml` stays the config/policy source; drop `sources.yaml` /
`risks.yaml` / `unknowns.yaml` as separate files; reuse the shipped `autonomy.*` rather than
build an engine; route objectives into the **existing** `specs/` + `work-docs/` path with no
parallel document system; decisions/experiments extend the existing memory tier with a revisit
condition, and a met condition **surfaces a candidate rather than auto-reversing** the prior
decision; Cell mode is v2 and adds only owners/approvers to the same data model — not a new mode
axis; product metrics lag code completion, so wrapup must be able to report `pending`; and the
count of generated objectives or documents is never the success metric.

**Where codex's design is stronger than this one — adopt:**

1. **It designed the World Model instead of deferring it, and kept it small.** A fact is
   `{id, claim, known|assumed|unknown, scope, evidence_location, observed_at, revalidation_condition}`,
   and a conflicting observation surfaces as a **conflict** rather than overwriting. That
   preserves the one genuinely novel mechanism this document identified (the tri-state) instead
   of postponing it, and `known` is explicitly scoped-and-timestamped rather than "true".
2. **An `evaluating` objective state.** States are `proposed | active | evaluating | closed |
   dropped`, with the evaluation verdict recorded separately as success / partial / failure /
   inconclusive. *Code complete but product effect not yet observable* stays `evaluating` — that
   is the clean structural answer to the observation-lag defect, which this document only raised
   as an open question.
3. **An explicit anti-goalpost rule**: an objective is not edited after the fact to look like it
   succeeded. This document had baseline freezing but not objective immutability.
4. **A sharper autonomy critique than this document made.** The user's `auto / review / dri`
   lists key on *task name* (`research`, `bug_fix`, `refactoring`). Codex rejects that: approve on
   the change's actual external impact, data access, cost, and reversibility, strictest-wins when
   several apply. And it answers the user's real complaint directly — *routine work inside an
   already-approved objective scope must not re-ask*; re-approval is triggered by scope, risk, or
   budget change. This document said "autonomy is already built" and moved on, which is true and
   unhelpful.
5. **Concurrency, which this document ignored entirely.** `state.yaml` writes check the version
   that was read; facts observed inside a worktree carry branch + commit and are **not** promoted
   to the base state immediately. In a repo whose CLAUDE.md is half multi-session worktree
   defense, omitting this was a real miss.
6. **Measure the new layer itself.** Dogfooding tracks objective-proposal adoption rate, human
   course-correction time, evaluable-completion ratio, and maintenance cost — and the automation
   shrinks if those do not beat baseline. This document argued "measure before you steer" and then
   proposed no measurement of its own recommendation.
7. **Decision/experiment originals belong in `.claude/memory/{decisions,experiments}/`, with
   `wiki.md` / `failures.md` as index and Obsidian promotion sharing the same id.** This
   corrects a defect here: this document proposed hanging `revisit_when` off Second Brain
   `decision` notes, but Second Brain is **opt-in, default-off, and its vault is a separate git
   repo** — so the original cannot live there without making the mechanism optional and
   unversioned with the code.
8. **Metric definition enumerated**: numerator/denominator, population, observation period,
   collection method, data source, comparability conditions — and the observation
   ("73% → 84%") is recorded separately from the causal claim ("because of this change").
9. **Its named top risk is more specific than this document's.** Not Goodhart in general, but:
   *an AI-authored assumption becomes treated as fact because it is now in a structured file, and
   then justifies objectives indefinitely.* The defense is provenance + timestamp + refutation +
   pending-evaluation retained on every fact, plus an explicit approval boundary on intent
   changes — not fewer files.

**Where this document is stronger than codex's — keep:**

1. **Competitive and host-substitution analysis.** Codex had no market context and did not ask
   for it. Intent capture is table stakes (BMAD's Analyst→PRD chain, Spec Kit's `/constitution`,
   Kiro, Tessl); Claude Code's default-on Auto Memory partially subsumes *unstructured* decision
   recall. Which parts differentiate is a scoping input codex's design does not have.
2. **Surface cost.** Codex proposes `/hm:objective` + `/hm:eval` as rendered slash commands
   without pricing them against the frozen 427,369-char baseline. Prefer CLI verbs; take an
   explicit `surface_allowance` for whatever stage prose the eval step adds.
3. **This repo's own empirical record.** 58.5% of rendered command bytes shipped with zero
   invocations; `hm:research` $44 vs `hm:execute` $705; 131 PLANs of which 49 are internal
   plumbing. That history is why sequencing discipline, not design quality, is the binding
   constraint here.
4. **The state-vs-behavior scaffolding frame** ([[RESEARCH-harness-diet]]) and the
   COMP/HOST/INV/TUNE classes, which place this whole proposal in the half the repo already
   decided to keep — the argument that makes the build defensible at all.
5. **Deferral discipline.** Codex ships four bundles; this document ships three items and holds
   the rest until the loop has run. Given the 58.5% precedent, the hold is the safer bet — though
   codex's bundle 1 is small enough that the gap is narrower than it first appears.

### Merged direction (supersedes the Recommended Direction above where they conflict)

Take **codex's data model and state machine**, keep **this document's scope and cost discipline**:

- Adopt the `state.yaml` fact schema *and* the `evaluating` objective state now — both fix real
  defects, and both are small.
- Adopt the capability-based autonomy critique (impact / data access / cost / reversibility,
  strictest-wins, no re-asking inside an approved scope). This is what actually answers the
  user's "진행할까요?" complaint.
- Put decision/experiment **originals** under `.claude/memory/`, not in the vault.
- Keep `hm status` / `hm next` as CLI verbs, not rendered slash commands, until they earn the
  surface.
- Hold codex's objective-generation bundle behind its own dogfooding metrics: adopt it when
  proposal-adoption rate and course-correction time show ideation is the bottleneck; drop it if
  they do not.

## 🔗 Related Internal Docs

- [[RESEARCH-harness-diet]] — "cut behavior scaffolding, keep state scaffolding". The proposal is almost entirely *state* scaffolding, which is the half this repo already decided to keep.
- [[RESEARCH-harness-maker-cold-eval]] — 2026-05-22 headline lock-in (personalization) + the explicit instruction to cut surface that exists "for the maintainer's intellectual model".
- [[PLAN-harness-diet]] — the cuts that shipped in 0.47.0 (fused commands) and the `verify` retirement question that Open Question 7 depends on.
- [[RESEARCH-context-carry-economics-2026-07-28]] — carry economics; why a read-only `hm status` is cheap and a rendered slash command is not.
- [[PLAN-workflow-steps-vs-model-capability]] — the COMP/HOST/INV/TUNE classes used in the host-substitution check.
- [[PLAN-command-surface-registry]] — the surface ratchet this work must pass.
