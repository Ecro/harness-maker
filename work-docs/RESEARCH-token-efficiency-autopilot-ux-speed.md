---
type: research
task_slug: token-efficiency-autopilot-ux-speed
status: complete
created: 2026-09-08
tags: [harness-maker, research, python, token-efficiency, autopilot, onboarding-ux, wall-clock, observability]
mtime_warn_days: 7
libs_fetched: []
sources:
  - https://github.com/anthropics/claude-code/issues/29971
  - https://www.faros.ai/blog/claude-code-token-usage
  - https://ccusage.com/guide/
  - https://blog.prototypr.io/stop-wasting-tokens-a-developers-guide-to-claude-code-cleanup-de842f6403e5
  - https://wec.wiline.com/docs/news/spec-driven-development-solution-to-vibe-coding/
  - https://medium.com/@reenbit/bmad-vs-spec-kit-vs-openspec-choosing-your-spec-driven-ai-framework-in-2026-a6996b3ebb8d
  - https://resources.anthropic.com/2026-agentic-coding-trends-report
  - https://sirishacherala.substack.com/p/code-review-assistance-system-design
  - https://github.com/charlieyou/cerberus
  - https://github.com/szarkans/multi-code-review
  - https://github.com/DantesPeak85/the-council
  - https://www.baseten.co/blog/harnesses-are-everything-heres-how-to-optimize-yours/
  - https://zander.wtf/blog/claude-md-agents-md/
  - https://atlassianblog.wpengine.com/development/scale-agent-impact-with-jira-automation
related_docs:
  - [[PLAN-harness-diet]]
  - [[PLAN-token-economy-step-pruning]]
  - [[RESEARCH-context-carry-economics-2026-07-28]]
  - [[PLAN-render-observability-audit]]
  - [[PLAN-economics-attribution-and-carry]]
  - [[PLAN-workflow-time-token-savings]]
  - [[EXPERIMENT-session-length-ab]]
  - [[PLAN-onboarding-interview-ux]]
  - [[RESEARCH-first-interview-ux-2026-08-06]]
  - [[PLAN-autopilot-advance-noop]]
  - [[PLAN-multi-lens-review-round]]
  - [[RESEARCH-review-round-inflation]]
summary: "Measurement is the binding constraint; the parity-gap class is the cheap win on all four axes"
---

# RESEARCH — token efficiency · autopilot completeness · user comprehension · wall-clock

## 🎯 Recommended Direction

**Do not start with an optimization pass. Start with (a) restoring the evidence layer and
(b) closing the prose–runtime parity gaps.** Every large optimization on all four axes is
already in one of three states — *taken*, *prior-rejected with a recorded reason*, or
**pre-registered and unrun**. The third state is the live one, and it is blocked on
measurement, not on design.

Two findings, reached independently, converge on the same constraint:

1. **All five observability ledgers hold zero rows.** `auto-advance.jsonl`,
   `stage-agents.jsonl`, `second-opinion.jsonl`, `delegation.jsonl` are all ABSENT;
   `stage-spans.jsonl` holds one `start` row (written by this stage) and no `end`.
   `.gitignore:73` excludes `.claude/observability/*`, so **the project commits its
   narrative (`work-docs/`, `.claude/memory/`) and discards its measurements.** For a
   project whose method is BASELINE-DELTA measurement, that is inverted. CLAUDE.md
   forbids hand-calculating these figures ("출하된 리더를 쓴다") — and the shipped reader
   answers `no rows … This is not a clean bill of health; it is an absence of evidence.`
2. **The single largest un-taken token win is unrun, not unplanned.** Resetting context
   before `verify`/`wrapup` is worth **≈$390 of the $697** those two stages spend
   (`RESEARCH-context-carry-economics-2026-07-28.md:161-164`). It was pre-registered as
   `EXPERIMENT-session-length-ab.md` on 2026-08-08; **§8's run log is empty** — zero runs
   in a month against a rule needing n≥8 per arm. *Unblocking it is 16 runs, not new design.*

Alongside that, one defect class accounts for damage on **all four axes at once**:
**shipped prose that describes behaviour the runtime does not perform.** 14 instances are
confirmed below (§3, Approach A). They are individually cheap, individually verifiable,
and CLAUDE.md's own failure tiers already name the class
(`[fail:design] runtime-env-gate-dead-on-arrival` count:2,
`[fail:tooling] silent-no-op-patch-reports-success` count:2,
`[wiki:convention] wrong-transparency-table-worse-than-none`).

The four axes look like they conflict (more explanation ⇄ fewer tokens; more autonomy ⇄
more gates; faster ⇄ same quality). **They stop conflicting once prose is routed by
load-time**: unconditional command-body prose is the expensive channel (loaded in full,
then carried every turn); skills, `/hm:help`, README and YAML comments are the cheap
channel (loaded on demand, or never by the model). Almost every explanatory improvement
the user asked for belongs in the cheap channel, and almost every token saving available
is *deletion of dead prose*, not compression of live prose.

### 📊 Measured baseline (this repo, 2026-09-08)

| Measurement | Value | Source |
|---|---|---|
| Rendered `.claude/commands/hm/*.md` total | 447,546 chars | direct `wc` |
| `review.md` / `plan.md` / `loop.md` / `execute.md` | 87,438 / 67,667 / 53,711 / 51,100 | direct `wc` |
| Session context share held by slash-command body | **77.1%** of 140,463 chars | `economics composition` |
| Autopilot prose in commands: advance ×7 + picker ×7 | 24,884 + 18,067 = **42,951** (9.6% of surface) | direct measurement |
| Round trips per pipeline (research→wrapup) | **133** (review 39 · plan 26 · wrapup 25) | `surface_baseline.json` `round_trips` |
| `uv run … hm --help` startup, warm | **0.04 s** (cold 0.60 s once) | 10-run timing |
| ⇒ all subprocess startup per pipeline | ≈6.7 s = **0.3–0.6%** of a round trip | derived |
| Wall clock spent in the main loop, not subagents | **~85%** | `RESEARCH-workflow-time-token-savings.md:33` |
| Stage medians (min) | plan 23.4 (n=6) · execute 20.2 (n=8) · research 11.1 (n=2) · review 7.3 (n=8) · wrapup 3.6 (n=9) · verify 1.7 (n=1) · **spec: no row** | ibid. `:89-99` |
| CLAUDE.md always-carried cost | 392 lines / **60,921 chars** (~155 chars/line) | direct `wc` |
| Largest single config-gated block | `plan.md.j2:152-309`, `dev_mode=='spec-driven'`, 9,243 B = 15.5% of plan.md | static attribution |
| `review.md` empirically droppable by config | **25.8%** (21,352 B); 67.7% unconditional-or-target-gated | static attribution |

Two facts constrain how these numbers should be read. **Subprocess cost is not the
problem** — 6.7 s per pipeline kills the tempting "reduce shell-outs" direction outright;
the mechanism is that each `!` line is *one main-loop turn at 200–430K context*.
And **every one of the ten largest config gates in this repo is ON**, so 447,546 is near
the worst case: a default third-party install is materially cheaper than these figures.

## 🔍 Refinement Decisions

`--deep` was not set and the session runs under armed autopilot, so the Phase 0/0.5
refinement interview was skipped by the stage's own default.

**Discovery lens:** (1) **User-workflow / product opportunity** — the user's third axis is
squarely a product question, and the wall-clock axis turned out to be one too;
(2) **Technical architecture / implementation** — the token, autopilot and serialization
axes; (3) **Research / benchmark** — used as a secondary lens to check measurement
methodology and to source external evidence on autonomy trust and review-loop fatigue.

Gathering was fanned out across five parallel read-only agents (one per axis plus the
product lens), because the prior-art surface is 407 documents in `work-docs/` and the
research's whole value is separating *landed* from *still open*. Note the
self-evidencing detail: the rendered `research.md` ships **zero** `Task(subagent_type=`
sites, so that fan-out had to be hand-rolled — see gap A-4.

## 🛠️ Approaches Found

### Approach A — Prose–runtime parity pass  ⟵ recommended, together with D

| Field | Content |
|---|---|
| **Approach** | Delete or re-wire shipped prose that describes behaviour the runtime does not perform; bind each surviving claim to the object that produces the value. |
| **Assumption** | That dead prose is pure cost with negative explanatory value — a *wrong* disclosure is worse than none (`[wiki:convention] wrong-transparency-table-worse-than-none`). |
| **Evidence** | 14 confirmed instances, below. 10 of 14 were verified against code by this research, not read from a doc. |
| **Trade-off** | Broad but shallow: many small diffs across templates, docs and one Python signature. No single dramatic number. |
| **Compatibility** | Very high. The repo already ships the remedy pattern three times: AST-walk discovery (`tests/structural/test_autonomy_level_literals.py`), value-bound assertion (the `AutonomyConfig()` fix), removal allowlist with staleness check (`_ALLOWED_REMOVALS`). This extends them from *values* to *claims*. |
| **Risk** | **low** per item; medium in aggregate only because 14 diffs across 4 surfaces need per-item ACs. |

**Confirmed parity gaps** (✅ = code-verified during this research):

| # | Gap | Evidence | Axis hit |
|---|---|---|---|
| A-1 | ✅ `autopilot_advance_enabled` has **zero producers** (`workflow_fuse.py` deleted); its only reference is the consumer `stage_end_summary.md.j2:24` with `\| default(true)`. The advance block is **not** gated on `autonomy.level`, so a `gated` harness ships **24,884 chars** that can only ever emit `kill_switch`. `ask` is the fresh-render default and absent/malformed pins to `gated`. | measured per-file 2,945–5,230 | token + autopilot |
| A-2 | ✅ `run_in_background` occurs **0×** in templates and rendered commands. ADR-011 hoisted the second-opinion call to run "concurrently with Pass 1"; with no mechanism the foreground Bash blocks up to `CODEX_TIMEOUT_S=300`. | grep | wall-clock |
| A-3 | ✅ CLAUDE.md recommends shrinking `reviewers.enabled` as the escape hatch for language-conditional fan-out cost. `lens_dispatch(preset)` (`conditional_router.py:141`) takes **no such argument** and never reads the list, so narrowing it changes nothing that is dispatched. **⚠️ CORRECTED 2026-09-08** (Phase 5 A.5 round 1): this row also claimed the rendered review dispatches `test-reviewer` and `concurrency-reviewer` "**both absent from `enabled`**". That was **false** — `interview.py:127-137`'s `_PROD_ENABLED_REVIEWERS` contains both, and `interview.py:978` preserves a non-empty user list, so the dispatched set is a strict *subset* of `enabled` on any harness a producer emits. I measured the empty `enabled` from a bare `InterviewAnswers`, which no producer emits. The finding stands on the signature alone; the dispatch half of the evidence was an artifact of my own fixture. | signature (dispatch half retracted) | comprehension + wall-clock |
| A-4 | ✅ `research.md.j2:181` gates the 3-way `Explore` fan-out on `"cursor" not in config.targets`; with cursor among targets the rendered `research.md` has **0** `Task(` sites. Sole site using that gate form — every other discriminator derives from the output path. | grep, count 0 | wall-clock |
| A-5 | ✅ `README.md:106` — "Every `/hm:execute` runs in a fresh worktree." False for Side (`worktree.enabled: false`), and imprecise when ON (persistent `hm/<slug>`, not fresh). | read | comprehension |
| A-6 | ✅ `second_brain.enabled: true` with an unreachable `vault_path` → wrapup Step 5.6 promotion cannot ever have run on this machine. Error text is good; nothing surfaces the standing condition. | live CLI error | comprehension |
| A-7 | ✅ Personalization-audit message reads `0 axis overrides … (threshold 30)`; 0 < 30 means the **count** branch cannot have fired, so the **days** branch (`audit_days_threshold=14`, `models.py:395`) did — while the message cites the other threshold. | observed message + `models.py:394-395` | comprehension |
| A-8 | `context-linter` is advisory with **no production caller** — `context_lint.lint()` is invoked only by the skill's own snippet and by tests. | agent, cited | token |
| A-9 | ✅ `harness.yaml` `skills.enabled` lists `relevance-filter` (removed in 0.22.3, `docs/adr/0007:34`) and `research-crawler`; neither appears in `skills.installed`. | read | comprehension |
| A-10 | ~~The size gate measures a **re-render, not the shipped file**~~ — **RETRACTED 2026-09-08** (PLAN ADR-012). The re-render *is* the correct subject: `.claude/` is gitignored, so there is no shipped render to measure and the on-disk 442,446 was this repo's own working copy, not a shipped artifact. The measured gap was real but meant the opposite of what I concluded from it. The headroom-0 half stands and is what the `surface_allowance` mechanism addresses. | agent, cited — conclusion inverted | token |
| A-11 | Per-command ceilings are **blind to second-opinion surface** — `_render()` passes no `second_opinion` (`test_command_size_budget.py:53-55`), so review's ~10.6 kB never touches `_ATOMIC_RATCHET`. | agent, cited | token |
| A-12 | `consensus-arbiter` is **never invoked** ("the unwired arbiter path", `review.md:672`) though installed and named in `second_opinion.agents`. | agent, cited | wall-clock |
| A-13 | `docs/HOW-IT-WORKS.md:22,938` ships a `## 4. Fusion Commands` TOC entry and section whose body states there is no fusion command. | agent, cited | comprehension |
| A-14 | `verify` delegation is shipped-but-off — `templates/stages/verify.md.j2:314` exists, rendered `verify.md` has 0 `stage-delegate`. | agent, cited | wall-clock |

### Approach D — Restore the evidence layer  ⟵ recommended as Phase 0 of A

| Field | Content |
|---|---|
| **Approach** | Make the five ledgers durable and readable; give `/hm:health` a report for the two silent detectors that already exist on disk. |
| **Assumption** | That the optimization backlog is evidence-blocked rather than design-blocked. |
| **Evidence** | Five empty ledgers (§1). `EXPERIMENT-session-length-ab.md` §8 empty after a month. Phase 6's pre-registered re-measure "code DONE, acceptance number DEFERRED" (`PLAN-economics-attribution-and-carry.md:1030`). Wall-clock medians at n=1–9 with **spec absent entirely**. `find_unconfirmed_authorization` (`autopilot_ledger.py:235-272`) has exactly one caller and `elapsed_s` has **no consumer anywhere** — the "announced the next stage, never ran it" defect is recorded and never reported. |
| **Trade-off** | Delivers no saving itself. Its whole value is unblocking A/B/C claims and the $390 experiment. |
| **Compatibility** | High — all five writers exist; what is missing is durability, one reader, and target-awareness. |
| **Risk** | **low**. Sub-risk: `smoke_check` reads only `yaml_level` with zero `targets` references, so a Cursor-only harness reports "never fired" **forever** — a false alarm that trains users to ignore the one real degradation signal. |

### Approach B — Another surface-reduction pass

| Field | Content |
|---|---|
| **Approach** | Cut/compress rendered command prose against the existing ratchet. |
| **Assumption** | That meaningful surface remains after the fused-command deletion. |
| **Evidence** | **Against.** The one large win is already taken: −530,222 chars / **−45.2%** (`PLAN-harness-diet.md:18-22`). 67.7% of `review.md` is unconditional-or-target-gated; only 25.8% is config-droppable. ADR-011 forbids raising a ceiling to pass a phase. Prior estimates collapsed 8.2% → 12.0% → 4.7%, and the surviving 4.7% was measured on `exec-rev-wrap-ver`, **deleted 9 days later** — net value today zero. |
| **Trade-off** | Historically negative: one pass cut 4,437 chars from one command while adding 3,765 to review — **surface grew 0.75%**; `PLAN-workflow-time-token-savings` closed at **+4,627** on claude behind a `strict=False` xfail. |
| **Compatibility** | High mechanically, poor on value. |
| **Risk** | **medium** — ADR-017's withdrawn 8,738-char "documentation-only" trim removed runtime-behavioural instructions. |

The two genuinely remaining items here are narrow and worth folding into A rather than
run as a pass: **(i)** the `second-opinion-gate` skill body is unconditional — §2/2b/3/4/6
(≈52% of 18,695 chars) is PIDA machinery unreachable when `models: []`, so ≈9.8k chars
for models-off installs (**0 here**, models on); **(ii)** ≈4.4 kB of near-identical
generated lens-dispatch tables in `review.md` (`:216-217` and `:994-995`, 11.6× loop
expansion) — but collapsing dispatch sites shrinks `count_round_trips` without reducing
real dispatches, so it distorts the meter.

**Round trips, not chars, is the lever this repo already identified and then failed to
pull.** `surface_baseline.json` records review 39 / plan 26 / wrapup 25 but does **not**
ratchet them; `PLAN-token-economy-step-pruning.md` ADR-001 declared exactly this correct
("a Step that spawns a subagent or forces a tool round-trip costs O(context) per turn")
and then compacted prose instead, delivering ~0.

### Approach C — Proportionality: an auto-triaged light path

| Field | Content |
|---|---|
| **Approach** | Triage by diff size / blast radius into a reduced stage subset, instead of running all 7 stages for every change. |
| **Assumption** | That a large share of real tasks do not warrant the full pipeline. |
| **Evidence** | This is the **strongest external signal found**, and the one criticism of spec-driven flows nobody has shipped a fix for: Böckeler got 4 user stories + 16 acceptance criteria for one small bug fix ("a sledgehammer to crack a nut"); a 2026 review names "the proportionality problem, where a four-line bug fix triggers a full specification pipeline" as unfixed; measured spread on one CRM task is **12 min / 90 min / 5.5 h** across OpenSpec / Spec Kit / BMAD. Converges with an internal finding: `make.md:672-686` already names only `/hm:health`, `/hm:execute` and `/hm:configure`, so users are **accidentally** trained onto a light path with no design behind it. |
| **Trade-off** | The highest user-noticed win on the wall-clock axis, and the largest new design surface. |
| **Compatibility** | Contested. Mandatory-lens coverage **blocks approval** (`lens_coverage.blocks_approval`), and CLAUDE.md records the language-conditional lens reduction as a *deliberate hold* for want of data — which Approach D would supply. |
| **Risk** | **high** — a triage rule that under-scopes silently converts a quality gate into a skipped gate. |

## ⚠️ Pitfalls

- **Estimates in this area have a documented history of collapsing under scrutiny**
  (8.2% → 12.0% → 4.7% → net zero). Each correction removed a block described as
  documentation-only that carried behaviour. Any saving claim in the PLAN needs a
  pre-change measurement and a per-section classification table, per ADR-017's
  reopening conditions.
- **The line-vs-character measurement split is already known and accepted, and its
  upside is capped.** `PLAN-render-observability-audit.md:234-236` rejects an `@import`
  split on exactly this ground ("an import loads into the same context, so the
  line-count signal would pass while the token cost stayed"); `:500` R6 records "line
  count passes but token cost does not move" as known and accepted; and
  `SPEC-workflow-loop-efficiency` puts the CLAUDE.md ceiling at **~4% of total spend —
  "the honest size of this win."** The two largest blocks are already relocated to
  `docs/` (624 → 392 lines). *Do not re-propose compressing CLAUDE.md.* The residual is
  a **meter** defect: no doc gives a reason for `context_lint.THRESHOLDS` staying
  line-based while the command ratchet is explicitly character-based (its ADR-014
  corrected "bytes"→"characters" because "only one of them is what a model's context
  sees").
- **Delegation is a token lever, not a wall-clock lever.** Measured: "Delegation
  reduces what is added; it cannot reduce what is already there"
  (`RESEARCH-context-carry-economics-2026-07-28.md:102-108`); `CHANGELOG.md:2611` — "ships
  the instrument, not a saving." Do not budget wall-clock savings to it.
- **Prior rejections that must not be re-proposed** (each with a recorded reason):
  deleting the 2nd `plan-validator` pass (22.2% verdict flip); deleting execute Phase A.5
  (P(FAIL)=37.5%); raising `max_review_rounds` ("hides the rate problem behind a bigger
  number"); shrinking the lens set or gating the multi-lens fan-out; re-dispatching all
  lenses every round; agent-prose dedup and memory-retrieve caching (mechanism refuted at
  execute); deleting `/hm:plan` Step headings (~50 tok/turn, cache-read); making
  `second_opinion` opt-in (**largest single saving available**, rejected because a
  cross-model voter caught a P0 two Claude reviewers missed); delegation default-on;
  skipping the review Confirmation Pass; collapsing the two-pass redaction (+47 pp
  precision).
- **Wall-clock scopes must never be summed** (`economics.py:501`) — the PLAN already
  retracted one such ratio. And medians here are n=1–9 with **spec entirely absent**;
  any time claim built on them is an inference, not a measurement.
- **A green `/hm:health` is not evidence for the Production path** — the second-opinion
  smoke runs in base only, with no worktree preflight. CLAUDE.md records that this
  inference "hid H1 for its entire lifetime."
- **External: review-loop fatigue has a published budget.** Above **20–30% false
  positives developers ignore all findings**; recommended cap is **3–5 findings per PR**.
  A 7-lens × 2-pass fan-out producing 14 dispatches sits directly against that, and the
  harness has no false-positive rate because the ledgers are empty.
- **External: the autonomy ceiling is verification, not capability.** ~60% of work runs
  through AI but only 0–20% is fully delegated; adoption 84% while trust in accuracy fell
  40% → 29%. METR: of **296 test-passing** AI PRs, ~half would not have been merged by
  maintainers. Autopilot completeness work should target *legibility and resumability*,
  not wider advance.
- **External, and directly relevant to our own antigravity path**: the-council's advisory
  records `agy --dangerously-skip-permissions` **ghost-writing 8 files** into a project
  (2026-05-24). Our `agy --sandbox --print` probe was itself once wrong about whether
  sandbox applied (flag consumed as prompt text; corrected 2026-07-25). Treat as a
  standing reason to keep the corrected probe green, not as an action.
- **Command sprawl is self-reported as embarrassing, not powerful**: an audit of 58 slash
  commands — "I genuinely did not recognize half of them"; a Vercel eval found skills
  **never invoked in 56%** of cases. We ship 15 `/hm:` commands.
- **`/usage` now attributes cost per plugin, skill and subagent.** harness-maker is
  *named* in the user's own cost screen, and a "deep review, use multiple subagents"
  prompt can burn 50% of a Max 5× weekly limit in under a minute. This is the first time
  token efficiency is user-visible rather than maintainer-visible.

## ❓ Open Questions

These block `/hm:plan` from locking a phase order.

1. **Scope split.** Is this one PLAN (parity + evidence) with proportionality deferred,
   or does the user want C's light path in scope now? C is the highest user-noticed win
   and the largest design surface, and it depends on D for the lens data.
2. **A-1 — fix or delete?** Gate the advance block on `level != "gated"` (recovers
   24,884 chars for gated installs) *and* delete the dead `autopilot_advance_enabled`, or
   only the latter?
3. **A-3 — which side moves?** Either `lens_dispatch` grows an `enabled` argument (making
   CLAUDE.md's recommendation true), or CLAUDE.md's recommendation is retracted. Making
   `enabled` real interacts with `blocks_approval`, so this is not purely editorial.
4. **A-2 — is real concurrency wanted?** Wire `run_in_background` for the second-opinion
   call (up to 300 s/review), or downgrade ADR-011's claim to ordering-only? Note the
   harness has no measured second-opinion latency, because the ledger is empty.
5. **D scope — durability.** Do the ledgers stay gitignored (accepting per-machine,
   per-clone loss) or does a summarized, committed roll-up ship? A committed roll-up
   changes the dirt/preserve classification the 5-layer worktree defense depends on.
6. **D — is autopilot's 0-fire a defect or an unexercised path?** `entry_count: 0` with
   two live markers and `last_seen: null` cannot distinguish "never armed correctly" from
   "armed but this repo never ran a multi-stage pipeline." The dangling-authorization
   reader (Approach D) is what would answer it — so this question is *output* of D, not
   input.
7. **Is the $390 experiment in scope?** Running `EXPERIMENT-session-length-ab.md` to n≥8
   per arm is the single largest available token win and needs no new design — but it is
   16 pipeline runs, which is a schedule decision, not an architecture one.
8. **A-6 — machine config or loud failure?** Fix this machine's `vault_path`, or make
   `second_brain.enabled: true` with an unreachable vault a standing loud condition in
   `/hm:health`? (The former is not a code change; only the latter is plannable.)
9. **Explanation placement.** The comprehension fixes are cheap only if routed to the
   cheap channel — `make.md` quick-start (slash-command body, not rendered into the
   harness), `/hm:help`, rendered `harness.yaml` comments, README. Confirm nothing lands
   in a stage command body, which pays on every invocation.
10. **The 5 undisclosed axes** — `delegation`, `memory`, `security.gates`,
    `skills.enabled`, `max_review_rounds`, `default_model` are asked nowhere and disclosed
    nowhere. Disclose in the `make.md` table, or accept them as preset-only?

## 📚 Sources

- Claude Code context bloat tracker — https://github.com/anthropics/claude-code/issues/29971
- `/usage` per-plugin/skill/subagent attribution — https://www.faros.ai/blog/claude-code-token-usage · https://ccusage.com/guide/
- Command/plugin sprawl audit (58 commands; Vercel eval 56% skills never invoked) — https://blog.prototypr.io/stop-wasting-tokens-a-developers-guide-to-claude-code-cleanup-de842f6403e5
- Proportionality problem in spec-driven development — https://wec.wiline.com/docs/news/spec-driven-development-solution-to-vibe-coding/ · https://2muchcoffee.com/blog/spec-driven-development-tools/ · https://medium.com/@reenbit/bmad-vs-spec-kit-vs-openspec-choosing-your-spec-driven-ai-framework-in-2026-a6996b3ebb8d
- Delegation gap / trust decline — https://resources.anthropic.com/2026-agentic-coding-trends-report · https://rits.shanghai.nyu.edu/ai/anthropics-2026-agentic-coding-trends-report-from-assistants-to-agent-teams
- METR merge-worthiness of test-passing AI PRs — https://hackernoon.com/the-safe-way-to-ship-production-code-written-by-ai-agents
- Review-loop fatigue budget (20–30% FP ceiling; 3–5 findings/PR) — https://sirishacherala.substack.com/p/code-review-assistance-system-design
- Cross-model consensus prior art + the `--dangerously-skip-permissions` ghost-write advisory — https://github.com/charlieyou/cerberus · https://github.com/szarkans/multi-code-review · https://github.com/akholod/consensus-review · https://github.com/DantesPeak85/the-council
- Harness optimization / progressive disclosure — https://www.baseten.co/blog/harnesses-are-everything-heres-how-to-optimize-yours/
- CLAUDE.md vs AGENTS.md, and the ETH Zurich context-file result (LLM-generated −3% success/+20% cost; human-written +4%) — https://zander.wtf/blog/claude-md-agents-md/
- Trackers as agent control plane — https://atlassianblog.wpengine.com/development/scale-agent-impact-with-jira-automation · https://www.openhands.dev/blog/codex-vs-cursor

**Honest gaps.** The ETH Zurich arXiv ID could not be verified and the Anthropic report
PDF was not read directly (both delegation-gap figures come from three agreeing secondary
summaries). No source was found measuring how users *receive* k-of-N consensus
quantitatively — the evidence is presentation convention from shipped tools, not user
study. Internally, every wall-clock figure rests on `RESEARCH-workflow-time-token-savings`
medians at n=1–9, because the live ledgers are empty.

## 🔗 Related Internal Docs

- [[PLAN-harness-diet]] — the −45.2% fused-command deletion (ADR-001/002); ADR-004 defers the review cost centre to a PLAN that does not exist
- [[PLAN-token-economy-step-pruning]] — ADR-001 names round-trips as the correct lever; ADR-016/017 record the estimate collapse and the withdrawn trim
- [[RESEARCH-context-carry-economics-2026-07-28]] — the $697 / $390 figures; delegation measured as not fixing carry
- [[EXPERIMENT-session-length-ab]] — pre-registered 2026-08-08, §8 run log empty
- [[PLAN-render-observability-audit]] — ADR-004 CLAUDE.md→`docs/` relocation; `:234-236`/`:500` accept the line-vs-token divergence
- [[PLAN-economics-attribution-and-carry]] — delegation soak exit never taken; Phase 6 re-measure deferred
- [[PLAN-workflow-time-token-savings]] + [[BASELINE-DELTA-workflow-time-token-savings]] — the judgment gate, `auto_full`, and the +4,627 close
- [[RESEARCH-workflow-time-token-savings]] — stage medians; ~85% of wall clock is the main loop
- [[PLAN-multi-lens-review-round]] / [[RESEARCH-review-round-inflation]] — lens-set and round-count rejections
- [[PLAN-onboarding-interview-ux]] / [[RESEARCH-first-interview-ux-2026-08-06]] / [[BASELINE-onboarding-offset-ledger]] — the silent-axis disclosure table and its deferred remainder
- [[PLAN-plan-interview-comprehension]] — `interview.comprehension.depth`; comprehension never measured for comprehension
- [[PLAN-autopilot-advance-noop]] / [[RESEARCH-autopilot-invocation-and-marker-fix]] — autopilot marker and advance history
- [[PLAN-user-workflow-opportunities-2026-05]] — Second Brain has no install question at all
- `[wiki:convention] wrong-transparency-table-worse-than-none` — a false disclosure is worse than none; bind claims to the producing object
- `[wiki:architecture] one-rule-one-normative-site-others-defer` — the deletion test for duplicated normative prose
- `[wiki:architecture] autonomy-levels-live-in-two-places-and-a-test-finds-the-third` — `ask` is the fresh-render default; absent pins to `gated`
- `[wiki:architecture] narrative-output-needs-explicit-envelope` — one real dispatch is the only evidence for an output-shape contract
