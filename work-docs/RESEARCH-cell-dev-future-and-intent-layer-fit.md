---
type: research
task_slug: intent-world-model-objective-layer
status: complete
created: 2026-09-16
tags: [harness-maker, research, product-direction, intent, outcome-eval, cell, future-of-dev, token-economics]
mtime_warn_days: 14
libs_fetched: []
sources:
  - https://s29.q4cdn.com/628966176/files/doc_financials/2025/q4/Q4-2025-Shareholder-Letter_Block.pdf
  - https://s29.q4cdn.com/628966176/files/doc_financials/2026/q1/Block_Q1-2026-Shareholder-Letter.pdf
  - https://s29.q4cdn.com/628966176/files/doc_financials/2026/q2/Q2-2026-Shareholder-Letter.pdf
  - https://sequoiacap.com/article/from-hierarchy-to-intelligence
  - https://fortune.com/2026/03/06/exclusive-block-cfo-ai-leaps-18-months-led-decision-slash-nearly-half-its-workforce/
  - https://m.investing.com/news/stock-market-news/block-launches-ai-tool-to-speed-code-development-93CH-4748091
  - https://siliconangle.com/2026/07/21/block-launches-buzz-open-source-workspace-humans-ai-agents/
  - https://www.anthropic.com/institute/recursive-self-improvement
  - https://www.anthropic.com/engineering/harness-design-long-running-apps
  - https://www.anthropic.com/research/how-ai-is-transforming-work-at-anthropic
  - https://openai.com/index/harness-engineering/
  - https://openai.com/index/how-agents-are-transforming-work/
  - https://newsletter.pragmaticengineer.com/p/how-codex-is-built
  - https://developers.openai.com/blog/codex-as-a-platform
  - https://cursor.com/blog/building-bugbot
  - https://github.blog/ai-and-ml/github-copilot/improving-token-efficiency-in-github-agentic-workflows/
  - https://metr.org/blog/2026-1-29-time-horizon-1-1/
  - https://metr.org/blog/2026-02-24-uplift-update/
  - https://www.faros.ai/blog/ai-software-engineering
  - https://linearb.io/resources/software-engineering-benchmarks-report
  - https://www.gitclear.com/the_ai_code_quality_maintainability_gap
  - https://www.infoq.com/news/2026/05/dora-roi-ai-assisted-dev-report/
  - https://arxiv.org/abs/2605.18461
  - https://arxiv.org/pdf/2602.11988
  - https://arxiv.org/abs/2606.26300
  - https://arxiv.org/abs/2605.12925
  - https://arxiv.org/abs/2605.01160
  - https://arxiv.org/abs/2609.06383
  - https://arxiv.org/abs/2603.03456
  - https://arxiv.org/abs/2606.08571
  - https://arxiv.org/abs/2604.00073
  - https://www.martinfowler.com/articles/exploring-gen-ai/sdd-3-tools.html
  - https://addyosmani.com/blog/agent-harness-engineering/
  - https://charliehills.substack.com/p/delete-your-claudemd
  - https://mightybot.ai/tools/agent-evaluation-cost-study/
  - https://code.claude.com/docs/en/memory
  - https://www.oreilly.com/radar/when-ai-writes-the-code-specifications-need-an-exit-strategy/
related_docs:
  - "[[RESEARCH-intent-world-model-objective-layer]]"
  - "[[RESEARCH-harness-diet]]"
  - "[[RESEARCH-harness-maker-cold-eval]]"
  - "[[RESEARCH-harness-trends-2026-05]]"
  - "[[RESEARCH-context-carry-economics-2026-07-28]]"
  - "[[SPEC-intent-world-model-objective-layer]]"
summary: "Re-research from first principles: keep intent + assumptions + human-picked objective (state), drop the automated measurement/verdict machinery (behaviour nobody has closed), and spend the saved budget on the two things evidence says matter — verification and per-turn context cost."
---

# RESEARCH — Cell-era development, the next 6–36 months, and whether the intent layer fits harness-maker

> Supersedes the direction in [[RESEARCH-intent-world-model-objective-layer]] where they
> conflict. That document reviewed the *proposal*. This one re-derives the question from
> outside evidence (Block after its 2026 layoffs, frontier-lab practice, 2026 measurement
> studies, 6–36 month projections) and from this repo's own spend ledger, then judges the
> revision-2 SPEC against it.

## 🎯 Recommended Direction

**Keep the state, drop the machine.** Of the four bundles in the revision-2 SPEC, evidence
supports shipping two as durable *state* and withdrawing two as *behaviour* built on
infrastructure no team has yet made work:

| Bundle | Verdict | Evidence |
|---|---|---|
| Intent (`intent.yaml`: mission, outcomes with targets, non-negotiables, non-scope, unknowns) | **Ship** | every lab converges on a written intent layer; human-written context measured +4%, generated −3% (ETH 2602.11988); "specification quality … not model capability" is the binding constraint (2605.18461, 2605.01160) |
| Assumptions ledger (`known / assumed / unknown` + `revisit_when`), surfaced at gates | **Ship, minimal** | no vendor ships epistemic state (Claude/Codex/Cursor memory is preference memory); goal drift correlates with accumulated context (2603.03456); ignorance certificates exist only for QA tasks (2606.08571). Differentiator, but **no practitioner evidence teams maintain it** — so the schema must be tiny |
| Human-picked objective as a decision note + approval bound to scope, read by the autopilot boundary | **Ship, as a record** | Block's rule: human makes the merge/deploy decision even at "15% fully autonomous"; approval-to-scope is a drift defence. Candidate *generation* (`/hm:objective` as a rendered command) stays held — labs pulled heavy pre-planning (Ultraplan removed) |
| Automated outcome measurement (`measure_cmd` scheduler, cadence, budget round-robin, horizons, `released_at`, verdict state machine) | **Withdraw from v1** | nobody credible reports closing the product-metric → agent loop (Arize: "early form"; projection [low] even at 3 years); Block's only reported metrics are *delivery* metrics this repo already has (`delivery_metrics` CFR + churn); this bundle carries ~15 of the 28 unclosed codex findings, all of them contracts still to be designed |

Then redirect the saved budget to where every evidence stream points:

1. **Verification is the bottleneck, not generation.** Review is already this repo's most
   expensive stage ($239 of $596 stage-attributed spend). Faros: +98% PRs, +91% review time,
   flat delivery; LinearB: AI PRs wait 4.6× longer and are accepted 32.7% vs 84.4%;
   AgentLens: 10.7% of *passing* trajectories are lucky passes. Invest in oracles that
   co-evolve with the diff (property/differential, already started in spec-tetrad), lucky-pass
   detection, and review-queue-age as a first-class metric.
2. **Per-turn context is the cost centre.** 77% of this repo's spend ($1,990 of $2,586) is
   *outside* any `/hm:` stage — free conversation. `CLAUDE.md` is 425 lines / 64 KB and is
   re-read every turn; the cell evidence says < 200 lines, human-written, pruned every ~6
   months, and OpenAI's pattern is `AGENTS.md` as a table of contents into `docs/`. A new
   layer that only fires inside stages misses three quarters of the work; a layer that adds
   bytes to the always-loaded surface taxes all of it.
3. **Let the host absorb behaviour.** `/goal`, Routines, Auto Memory, Agent Teams and
   background sessions now cover "loop until done", per-repo memory and parallelism. What
   survives in a third-party harness is what [[RESEARCH-harness-diet]] already named — state
   across context windows, deterministic oracles, human lock-ins, cross-model checks — and
   the evidence from six independent sources says the same thing.

## 🔍 Refinement Decisions

- **Cell mode is presence of `owners:` + a shared intent file in git, not an axis.** Block
  discloses no pod sizes; Gartner's "tiny team" is PM + designer + ≥1 AI-native engineer. The
  only cell-specific artifacts with evidence are: one human-written spec per unit of work,
  ADR/decision notes because agents "refactor the reason away", review-queue age and
  change-failure rate as the weekly numbers. harness-maker has the last three; it lacks the
  intent file and the owner field. Nothing else is needed for five people.
- **Objective ≈ ticket, not a generated candidate list.** Block's unit of agent work is a
  Linear/Jira ticket tagged by a human; OpenAI's is a doc-anchored task. The objective record
  should look like a ticket with a hypothesis and a revisit condition, written by the human
  (optionally drafted by Claude inside `/hm:plan`, which already runs an LLM and already
  searches decision notes).
- **Verdicts are human-recorded observations, not computed.** `observed: met | missed |
  no_data` plus a note, written when the human closes the objective. No `released_at`, no
  horizon clock, no causal claim — this is the "option 2" split from the revision-2 review,
  reduced to its human-entered half.
- **Measurement stays manual and on-demand in v1.** `outcomes[].how_measured` is prose or an
  argv the human runs; `hm status` shows the last *recorded* observation. `measure_cmd`
  automation is reconsidered only when one real project has a metric worth polling — this
  repo's own first candidate is "rendered bytes with zero invocations", which is a one-line
  reader, not a scheduler.
- **The surface budget goes to reading, not writing.** No new rendered slash command in v1.
  `hm status` (CLI, LLM-free) plus a ≤ 40-line intent block loaded into the always-on context
  is the whole user surface.

### What existing evidence in this repo says about each SPEC scenario

| SPEC scenario | Keep / cut | Why |
|---|---|---|
| S1 intent skeleton, never overwritten | keep | table stakes; `_preserve_yaml_user_keys` pattern exists |
| S2 conflict without losing either side | keep, shrink | keep the status field and both observations; drop supersession / validity-interval design (R1-4) — it is the part with no practice evidence |
| S3–S4 argv measurement on cadence, failure rows | **cut** | scheduler, budget, crash recovery, cursor location (R1-5/10/11/25/26) all unresolved; no team runs this loop |
| S5 provenance on manual outcome | keep | cheap, and it is exactly what "observation, not causation" needs |
| S6 definition change starts a new series | defer | only matters once series exist |
| S7 approved objective cannot silently grow | keep | drift defence; hash must include the outcome id (codex NEW-6) |
| S8 approval; approved scope does not re-ask | keep | Block/labs: human gate at the decision, not at every step |
| S9 judged only after horizon | **cut** | replaced by human-recorded `observed:`; removes NEW-2/NEW-3 and AC-013/016 |
| S10 prior decision advises, never blocks | keep | already half-built in `/hm:plan` decision search |
| S11 commit shared knowledge, not local measurement | keep, simpler | with no ledger in v1 only deliverable paths remain — the gitignore negation trap disappears |
| S12 `hm status` / `hm eval` contracts | keep `status`, fold `eval` into `objective close` | `eval` had no user; user said so |

## 🛠️ Approaches Found

### Approach A — Ship the revision-2 SPEC as written (four bundles)
- **Assumption**: an automated outcome loop is what makes the layer worth having.
- **Evidence against**: 28 unclosed findings, ~15 of them undesigned contracts; no external
  precedent for the loop; the break-even needs 2–11% of execute+review spend removed and
  nothing in v1 can show it.
- **Cost**: 4 new modules, `autopilot_caps` mutation, a rendered command (~19 K chars across
  two variants), plus the plan ADRs for every open contract.

### Approach B — State-only slice (recommended)
- Intent file + assumptions ledger + objective record + approval gate + `hm status`.
- Removes `outcome_eval.py`, the scheduler, the verdict machine, and `/hm:objective`.
- Roughly halves the AC count (≈ 12), removes every "designed later" contract, and keeps every
  item the evidence classes as durable state.
- Cost: 2 modules (`intent.py`, `objectives.py`), one boundary check, one CLI verb, zero
  rendered surface.

### Approach C — Do nothing new; spend the effort on verification + context cost
- Evidence supports the *targets* but not skipping intent: intent capture is the one thing
  every lab and every cell report converges on, and this repo demonstrably lacks it.
- Rejected as a whole; adopted as the **second half** of the recommendation.

### Where harness-maker sits against the labs (convergence check)

| Practice (labs + startups converge) | harness-maker today | Gap |
|---|---|---|
| Written intent file | `CLAUDE.md` (how), `harness.yaml` (config) | **no "why" / outcomes** — this layer |
| Spec/plan before build | `/hm:spec`, `/hm:plan`, dual-file SPEC | none |
| Independent verification, never self-grading | 7-lens review, code-verifier, cross-model PIDA | oracle co-evolution, lucky-pass detection |
| Cross-session memory | `.claude/memory/`, Second Brain | host Auto Memory now overlaps the unstructured part |
| Parallel isolated agents | per-task worktrees, registry, markers | none |
| Human gate at merge / deploy | wrapup gate, judgment gates | objective approval is a fourth gate |
| Cost discipline | economics reader, context discipline section | **CLAUDE.md 64 KB per turn; 77% spend unattributed** |

### How the 6–12 month and 3-year projections bear on the design

- 6–12 months [high]: native long-running primitives absorb loop drivers; native memory covers
  preference/correction memory; verification cost becomes the visible budget line. → Do not
  add loop or memory behaviour; add state that hosts do not have (intent, assumptions,
  objective approval).
- 3 years [med]: procedural stage prose and reviewer lenses largely gone; specs survive as
  agent-maintained *anchored* artifacts (PROOF 2609.06383), not human-maintained documents.
  → Anything that requires a human to keep a second document current will rot; the intent
  file must be short enough to be re-read at every gate and cheap enough to be corrected in
  one line. Outcome loops are [low] confidence even at three years.

## ⚠️ Pitfalls

1. **Generated context is measured negative.** If `/harness-maker:make` fills the intent
   skeleton with LLM prose, expect the ETH result (−3% success, +20% cost). The skeleton must
   stay empty until a human writes it; `hm status` reporting "intent not filled in" is the
   correct nag.
2. **Adding to the always-loaded surface.** Every line added to `CLAUDE.md` or a SessionStart
   hook output is paid on every turn of the 77% unattributed spend. Load the intent block only
   at gates (`/hm:plan` Step 0, `/hm:review`, autopilot boundary) and in `hm status`.
3. **Mandate morale.** Block's "use AI daily, it is in your review" produced the worst morale
   reports in years. For a cell, the objective/approval layer must be advisory outside the
   autopilot path; a blocking gate on `/hm:plan` for missing intent would be the same mistake.
4. **Output metrics.** "Changes per engineer" rose 150% at Block while nothing independent
   verifies quality. If `hm status` shows anything, it shows review-queue age and CFR, not
   task counts.
5. **Second-document rot.** The only spec-maintenance evidence is that humans do not maintain
   specs beyond one change. An assumptions ledger that is not touched by `/hm:plan` and
   `/hm:wrapup` automatically will be stale within a month.

## ❓ Open Questions

1. Does the objective record live as a Second Brain `decision` note (one memory mechanism)
   or as `.claude/world/objectives/<id>.yaml` (machine-readable for the boundary check)? The
   previous research said "same shape as a decision note"; the boundary check needs a stable
   path. Likely: yaml is the source, promotion writes the note.
2. What is the smallest assumptions schema that `/hm:plan` will actually update? Candidate:
   `{id, claim, status, evidence, revisit_when}` and nothing else.
3. Which always-on bytes to remove from `CLAUDE.md` to pay for the intent block — a
   table-of-contents rewrite (OpenAI pattern) is a separate task with its own measurement.
4. Withdrawal criterion for the state-only slice: if after N wrapups no objective has an
   `observed:` value and no `revisit_when` has fired, the layer is unused and should go.

## 📚 Sources

Grouped by the question they answer. Confidence tags: [F] primary/confirmed, [C] company
claim, [M] measured, [S] secondary.

**Block after the layoffs.** Q4-2025 letter (4,000+ cut, "intelligence tools") [F]; Q1-2026
letter (Builderbot reviews >90% of PRs, 15% nearly fully autonomous, humans decide push) [C];
Q2-2026 letter (agentic AI in nearly all changes; incident rate −70% claimed) [C]; Sequoia
"From Hierarchy to Intelligence" (ICs / DRIs / player-coaches, no permanent middle layer) [C];
Buzz (agents as channel members, Jul 2026) [F]; Fortune CFO interview (bottom-up sizing) [C].
No pod sizes or manager ratios disclosed anywhere.

**Frontier labs.** Anthropic Institute "When AI builds itself" (>80% merged code by Claude,
review is the bottleneck, LOC overstates) [M]; Anthropic harness design (generator
self-evaluation unreliable; $9 solo vs $125–200 full harness) [M]; OpenAI harness engineering
(3–7 engineers, 1M LOC, AGENTS.md as ToC, GC agents) [C]; OpenAI "agents transforming work"
(Codex reviews 100% of internal PRs) [M]; Pragmatic Engineer on Codex (4–8 agents per
engineer, non-critical merges on AI review) [S]; Cursor Bugbot (52→70% resolution, human
corrections become rules) [M]; Google 75% AI-generated (no methodology) [C].

**Measurement.** METR uplift update (−18% / −4%, design abandoned) [M]; Faros telemetry [M];
LinearB 8.1M PRs [M]; GitClear duplication +81% [M]; DORA 2026 ROI "verification tax" [M];
Stack Overflow 2025 trust 29% [M]; ETH AGENTS.md study [M]; one-developer squad case (spec
quality is the constraint) [M-ish].

**Projection.** METR time-horizon 1.1 [M]; Verification Horizon 2606.26300; AgentLens
2605.12925; goal drift 2603.03456; ignorance certificates 2606.08571; PROOF 2609.06383;
terminal agents suffice 2604.00073; MightyBot context-carry 3.6× [M]; Osmani harness
engineering; Hills "delete your CLAUDE.md"; Claude Code memory docs.

## 🔗 Related Internal Docs

- [[RESEARCH-intent-world-model-objective-layer]] — the proposal review this supersedes in part
- [[SPEC-intent-world-model-objective-layer]] — revision 2, judged above scenario by scenario
- [[RESEARCH-harness-diet]] — "cut behaviour, keep state"; this document is that rule applied to the new layer
- [[RESEARCH-context-carry-economics-2026-07-28]] — the carry measurement the cost argument rests on
- [[RESEARCH-harness-trends-2026-05]] — verification-with-typed-boundaries direction, still valid
