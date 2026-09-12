---
type: research
task_slug: workflow-steps-vs-model-capability
status: complete
created: 2026-09-12
tags: [harness-maker, research, python, jinja2, workflow-design, model-capability, harness-evolution, review-pipeline]
mtime_warn_days: 7
libs_fetched: []
sources:
  - https://www.anthropic.com/engineering/managed-agents
  - https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents
  - https://openai.com/index/harness-engineering/
  - https://martinfowler.com/articles/harness-engineering.html
  - https://arxiv.org/html/2512.10398v6
  - https://arxiv.org/html/2607.07946
  - https://arxiv.org/abs/2606.22678
  - https://arxiv.org/abs/2609.03141
  - https://code.claude.com/docs/en/worktrees
  - https://code.claude.com/docs/en/code-review
  - https://code.claude.com/docs/en/ultrareview
  - https://code.claude.com/docs/en/memory
  - https://code.claude.com/docs/en/agent-teams
  - https://learn.chatgpt.com/docs/changelog
  - https://cursor.com/changelog
  - https://cursor.com/docs/bugbot
  - https://github.com/buildermethods/agent-os/discussions/310
  - https://www.augmentcode.com/learn/gsd-58k-stars-claude-code
  - https://en.wikipedia.org/wiki/GPT-6_Astra
  - https://openai.com/index/safety-overview-gpt-6-astra/
related_docs:
  - "[[RESEARCH-harness-diet]]"
  - "[[PLAN-harness-diet]]"
  - "[[RESEARCH-workflow-time-token-savings]]"
  - "[[RESEARCH-workflow-step-audit]]"
  - "[[RESEARCH-token-economy-step-pruning]]"
  - "[[MATRIX-native-redundancy]]"
  - "[[ABLATION-pass2-2026-08-05]]"
  - "[[wiki:observability] stage-agent-ledger-reconciled-against-transcripts]"
  - "[[harness-bench docs/review-convergence/ADOPT.md]]"
summary: "Split the question into two axes (model vs host), tag every step by sensitivity class, and settle 'drop it' claims per model by measurement, never by guide"
---

# RESEARCH — Which workflow steps shrink as models/harnesses improve, and which do not

## 🎯 Recommended Direction

**TL;DR — The question has two independent axes, not one, and neither is answered by prediction.
Tag every step with a *sensitivity class* and let a pre-registered per-model measurement decide
which steps shrink; ship the shrink as a preset/knob, not as a deletion.**

Rationale. The user's framing ("model *and* harness get better → some steps vanish, some stay")
bundles two different forces that push on different steps:

1. **Model capability** (GPT-6 Astra, Fable 5.1, Opus 5) erodes *behavior scaffolding* — prose
   that tells the model to plan, verify, double-check, or split its attention. Anthropic says
   this outright ("harnesses encode assumptions about what Claude can't do on its own … those
   assumptions go stale as models improve", managed-agents post). This repo already drew that
   line on 2026-08-05 (`RESEARCH-harness-diet`: cut behavior scaffolding, keep state scaffolding)
   and explicitly labelled the reconciliation an **inference, not a measurement**.
2. **Host harness absorption** (Claude Code, Codex CLI, Cursor 3) erodes *infrastructure
   scaffolding* — worktrees, plan mode, subagent fan-out, multi-lens review with a verification
   pass, auto-memory, scheduling, hooks. These are now native in all three vendors (§Approaches,
   Table 2). This axis is **orthogonal to model capability**: Claude Code enforces worktree
   isolation at runtime today regardless of which model runs inside it.

What survives *both* forces is a short, stable list, and it is the same list three independent
sources converge on (harness-diet's "state scaffolding", harness-bench's "held in both models"
rules, Fowler/Böckeler's "deterministic sensors + human alignment"):

- **State that outlives a context window** — SPEC/PLAN/RESEARCH chaining, memory tiers,
  receipts, harness.yaml.
- **Deterministic oracles** — tests, RED gate, structural/security checks, `spec_machine check`.
  Anthropic's long-running-agents post argues frontier models need *more* of this, not less.
- **Human lock-in points** — plan interview ADRs, spec AC lock, one human triage of findings
  (harness-bench `[**]`: automating past triage grew code 152% in three rounds).
- **Heterogeneity** — two models once each beats one model twice (`[***]`, reproduced across
  vendors); no vendor harness offers cross-vendor voting, and this repo has a live P0 caught
  only by the cross-model voter (CLAUDE.md fleet-parallel-safety entry).
- **The measurement layer itself** — ledgers, pre-registration, baseline ratchet. This is the
  only thing that can tell you *when* a step has become dead weight on the next model.

And the sharpest local fact against the intuition "smarter model ⇒ drop the gate": both gates
that were slated for deletion on capability grounds were **kept by their own denominators** —
plan-validator changes the verdict on a later pass 2/9 (22%), and Phase A.5 test-reviewer now
FAILs **39 of 52 (75%)** on this repo, up from 37.5% at n=24 a month ago. A step that fires
three times out of four on Opus/Fable-class output is not obsolete. (Caveat below: FAIL-rate is
not proof of value either — §Pitfalls 3.)

**Main impact**: internal maintainer value (less prompt carried, fewer redundant surfaces, a
principled answer to every future "the new model doesn't need X" PR) — with one user-facing
effect: a documented thin mode that the ecosystem is visibly converging on (GSD `--minimal`,
Agent OS v3 dropping spec/orchestration, OpenSpec over spec burial).

This is informational. `/hm:plan` makes the binding decision.

## 🔍 Refinement Decisions

`--deep` was not set; no Phase 0 interview ran.

**Discovery lens:** (1) User-workflow / product opportunity — what the three host harnesses
ship natively in 2026 and what plugin users are doing (thin modes, deletions); (2) Technical
architecture — step inventory of the seven rendered stages + the knobs that already turn steps
off; (3) Research / benchmark — scaffold-ablation literature and the local `harness-bench`
cross-model study; (4) Risk — what the local ledgers say breaks when a gate is removed.

**Local capability × user artifact mapping** (what users already have natively vs. what this
harness still adds):

| Artifact the user already has (native, 2026) | harness-maker surface that overlaps | Overlap verdict |
|---|---|---|
| Claude Code `--worktree` + runtime enforcement; Codex `/worktree` (exp.); Cursor worktrees | `worktree.enabled`, task-create/preflight/land, 5-layer defense | **host-redundant in Claude Code**, still needed in Codex/Cursor; multi-session land coordination is not native anywhere |
| Plan mode (all three vendors) | `/hm:plan` Step 1 draft + Step 3 interview + ADRs | draft = redundant; **interview + ADR lock-in = invariant** (no vendor asks the 6-category/ADR questions) |
| `/code-review`, Code Review app with FP-verification, `ultrareview`; Bugbot | `/hm:review` 7-lens fan-out, Pass1/Pass2, code-verifier, consensus | fan-out + FP filter = **host-redundant (single-vendor)**; k-of-N ledger, grade gate, cross-vendor vote = gap |
| Auto-memory (`MEMORY.md`, topic files, shared across worktrees) | `.claude/memory/{wiki,failures}` + `memory_retrieve` + Second Brain promotion | storage = redundant; **recurrence-counted failures + promotion pipeline = gap** |
| Agent teams / subagents (≤6 concurrent in Codex) | reviewer agents, stage-delegate | dispatch mechanism = redundant; **the rubric bodies + model map = the value** |
| Routines / Goals / `/loop` | `/hm:loop`, autopilot | scheduling = redundant; **convergence gates + receipts = gap** |
| Hooks (all three) | `permission_gate`, `loop_gate`, `worktree_gate`, `sessionid_envfile` | mechanism = redundant; the *policies* are ours |
| `claude plugin eval` (2.1.269) | `harness-bench`, `tests/structural/surface_baseline.json` | complementary — could host the per-model ablation |

## 🛠️ Approaches Found

### Table 1 — Sensitivity class per step (the deliverable `/hm:plan` should lock)

Classes: **COMP** = capability-compensation (shrinks with model), **HOST** = host-redundant
(shrinks as the vendor harness absorbs it), **INV** = invariant (keep regardless), **TUNE** =
model-specific tuning (value *flips* per model; must be re-measured, never transferred).
Evidence grade follows harness-bench: `***` reproduced across models/conditions, `**` measured
once, `*` judgement.

| Stage · step | Class | Evidence | Note |
|---|---|---|---|
| research P1–P3 gathering/analysis/write | INV | `**` | cheapest stage ($44); reads a deliverable, writes a deliverable |
| research/spec/plan Phase 0.5 inequality gate | COMP | `*` | question-worthiness is a judgement the model increasingly makes unprompted; keep the *cap*, drop the 5-term ceremony |
| spec Step 2 six-category interview + oracle elicitation | INV | `***` | "if the loop keeps reversing, audit the spec" — the one region the contract left undefined was the only one that moved (bench) |
| spec Step 4 `spec_machine check --all` | INV | `**` | deterministic oracle |
| plan Step 1 internal draft | HOST | `*` | plan mode does this natively in all three vendors |
| plan Step 3 interview loop + ADR promotion | INV | `**` | no vendor asks these; harness-diet kept it, step-audit kept it |
| plan Step 4 plan-validator (single pass) | TUNE | `**` | 22% verdict-change (n=9) → keep; but 37/40 verdicts are MAJOR_REVISION — discrimination unproven (§Pitfalls 3) |
| plan Step 4.5 terminal re-validation | COMP | `**` | user already cut to single pass (memory: plan-validator-single-pass) |
| plan Step 4-pre / review 3.5 cross-model second opinion | INV | `***` | "two models once each > one model twice"; caught a P0 two Claude reviewers missed; **default `models: []` on both presets today** |
| execute Phase A (tests first) + Phase B RED gate | INV | `***` | deterministic oracle; RigorBench: explicit process discipline +17% outcome correctness; Böckeler: AI-written tests are an unreliable oracle → the *gate* is what makes them one |
| execute Phase A.4 false-RED screen | INV | `**` | mechanical |
| execute Phase A.5 test-reviewer | TUNE | `**` | 75% FAIL (n=52) on this repo — high, but no ground truth; re-measure per model |
| execute Phase C.0 declare-the-repair-first, D.5 newly-reachable window | COMP | `*` | prose instructing the model how to fix; frontier models do this (DeepSWE: Opus 4.7/GPT-5.4 write tests unprompted >80%) |
| review Phase 0 mechanical checks | INV | `**` | already off by default (`mechanical_checks: []`) |
| review Step 2 drift gate (PLAN/SPEC vs diff) | INV | `**` | state check, not behavior |
| review Step 3 7-lens same-model fan-out | TUNE | `***`/`**` | +52% unique findings on Python, −7pt recall on C firmware (bench §13) — value depends on *axis separation*, not model; Production forces all 7 |
| review Pass 1 redaction → Pass 2 | COMP | `**` | pre-registered removal arm exists (`ABLATION-pass2`) with a fixed decision rule; never executed |
| review Step 3.4 stable ids, 4a–4e consensus, k-of-N | INV | `***` | "agreement is not truth" (bench) → consensus must be *ledgered*, not trusted; 401 pass1 → 66 consensus-passed (16%) locally |
| review code-verifier mode A (FP filter) | INV | `**` | Opus 5 guide: report everything, filter in a separate pass; Code Review app now ships the same pattern natively |
| review auto-fix loop rounds 2..N | TUNE | `***` | "review many, fix once"; loop_decay −1.25 and code +25.8%/round on opus-5 vs −0.25 / −9.4% on gpt-5.6 → **cap rule is model-specific** |
| review confirmation pass | TUNE | `*` | n=4 (2/2) — unmeasured |
| review grade gate | INV | `**` | deterministic lookup over LLM inputs (review-grade-criteria) |
| verify Checks 2–6 | INV | `**` | harness-diet ADR-003 kept it against the Opus 5 guide: state scaffolding; $11 / 0.4% |
| verify Check 1 PLAN/SPEC satisfaction (LLM) | COMP | `*` | overlaps review Step 2 + wrapup Step 3 |
| wrapup Step 5 memory fold (+recurrence, archive, promotion) | INV | `**` | 67% of failures predate Opus 5 yet encode system invariants (harness-diet) |
| wrapup land / stash / 5-layer defense | HOST (Claude Code) / INV (Codex, Cursor) | `**` | Claude Code enforces isolation natively; multi-session land coordination is still ours |
| stage-delegate for verify/wrapup | INV | `**` | 136–329 → 38–46 main-loop turns; this is about carry, not capability |
| autopilot / auto-advance | HOST | `*` | Routines/Goals/`/goal` exist; convergence *gates* remain ours |

Counts: INV 16 · TUNE 6 · COMP 6 · HOST 4. *(Shipped registry, 2026-09-12: 82 entries, TUNE 7 —
review Step 4e moved to TUNE during `/hm:review`; `src/harness_maker/step_sensitivity.py` is the
source of truth from here on.)* The COMP set is small and mostly prose; the TUNE set
is where the money is (review apparatus = 22.4% of spend) and it is exactly the set harness-bench
says must not be transferred across models without measurement.

### Table 2 — Three ways to act on Table 1

| Field | A. Predict-and-delete | B. Tag + measure per model, ship as knobs | C. Do nothing until next model ships |
|---|---|---|---|
| Approach | Apply the Opus 5 / managed-agents guidance directly: delete COMP steps, collapse HOST steps onto native features | Add a `sensitivity` tag to each step (MATRIX-native-redundancy style), pre-register per-model ablations via `harness-bench` + `stage-agents.jsonl`, expose results as preset/`harness.yaml` knobs (thin mode) | Keep the current surface; re-open when GPT-6 Astra / Fable 5.1 usage data exists |
| Assumption | Vendor guidance transfers to this harness's tasks | The ledgers + bench are trustworthy enough to decide per step (they were, twice) | Accretion cost is tolerable |
| Evidence | For: Anthropic managed-agents, mini-SWE-agent ≈ OpenHands (76.8 vs 77.6), Agent OS v3. Against: plan-validator 22%, A.5 75%, RigorBench +17%, harness-diet ADR-003 reversal | For: two local reversals came from exactly this protocol; bench already separates "held in both models" vs "reversed"; `plugin eval` can host it | Against: BASELINE deltas are all growth (+2,319, +1,865, +732); GSD/BMAD shipped thin modes rather than waiting |
| Trade-off | Fast, but the two measured reversals say it deletes live gates | Slower; needs one bench run per model (≈$16 / 30 calls for review_convergence on opus-5) and ledger rows the Production preset barely produces | Zero risk now; every future "drop X" argument stays a guide-vs-guide debate |
| Compatibility | Conflicts with CLAUDE.md §제1목표's "keep base quality" and the surface ratchet's attribution requirement | Fits: MATRIX-native-redundancy, ABLATION-pass2, BASELINE/RECEIPT protocol, `verifier_discrimination` all exist | Fits trivially |
| Risk | **high** | medium | low now, high later |

**B is the recommendation.** A is the failure mode this repo has already hit twice and reversed
twice; C ignores that the accretion is measurable and the vendors have moved.

### What B concretely means (for `/hm:plan` to lock)

1. **Split the axis in prose and schema.** `MATRIX-native-redundancy.md` already scores HOST
   redundancy per surface (41 rows, `keep/retire/merge/unverified`). Add the COMP/INV/TUNE
   classes as a second column; the per-target difference (Claude Code enforces worktrees, Codex
   and Cursor do not) makes HOST a `targets`-conditional render, not a deletion.
2. **Shrink COMP first, by deleting prose, not by instructing.** harness-diet pitfall 7:
   prose-only rules decay (`write_after_read` 27.8%). Candidates: Phase 0.5 5-term ceremony
   (keep the open-ended cap), C.0/D.5 fix-instruction prose, verify Check 1, Pass 1 redaction
   **only after** the pre-registered `ABLATION-pass2` arm actually runs.
3. **TUNE steps get a per-model measurement, never a transfer.** Auto-fix round cap, churn
   stop rule, findings budget, A.5 threshold, fan-out lens set → `bench run --exp
   review_convergence --model <new>` on each model release; the "reversed between models"
   table is the template. Until measured on Fable 5.1 / GPT-6 Astra, the conservative default
   is bench's: cap by rounds.
4. **INV steps are off the table**, and the doc should say why in one line each (this table).
5. **Ship a thin preset, not a thinner Production.** The ecosystem signal is "keep the kit,
   ship `--minimal`" (GSD ~12K→700 tokens cold start, Agent OS v3, OpenSpec). Side already is
   that mode in spirit (1 reviewer, 4 mandatory lenses, no worktree, 2 rounds); the gap is that
   its choices are not *derived* from Table 1 and its `second_opinion.models` default is `[]`
   even though cross-model is the cheapest INV win.
6. **Fix the denominator before trusting any TUNE number.** Every stage-agent ledger row is
   Side-preset; Production has zero rows (spoton re-rendered after its last gated run). A.5's
   75% is this repo alone. `instrumentation.stage_agent_ledger` is `false` in schema default.

## ⚠️ Pitfalls

1. **"The new model verifies itself" is a claim about the model, not about your gate.**
   Anthropic's Opus 5 guide says to remove self-verification prose; this repo measured the
   verification *agents* firing 22%/75% of the time on that same model class. The guide is
   about prompts the model would follow anyway; the gates are external oracles. Conflating the
   two is how harness-diet nearly cut `/hm:verify` (ADR-003 reversed it).
   ([managed-agents](https://www.anthropic.com/engineering/managed-agents); `RESEARCH-harness-diet:56-58`)

2. **Scaffold ablations are measured on SWE-bench-shaped tasks with a single agent.**
   mini-SWE-agent ≈ OpenHands (76.8 vs 77.6) and DeepSWE's "native vs standardized harness within
   noise" say nothing about spec-lock-in, multi-session land coordination, or memory across
   weeks — the parts of this harness that are state, not behavior.
   ([arxiv 2512.10398](https://arxiv.org/html/2512.10398v6); [arxiv 2607.07946](https://arxiv.org/html/2607.07946))

3. **A high FAIL rate is not proof a gate is valuable.** plan-validator returns
   MAJOR_REVISION 37/40 — a gate that always says "revise" has no discrimination; the metric
   that justified keeping it is *verdict change across passes* (22%), and A.5's 75% has no
   ground-truth arm. `verifier_discrimination` explicitly lists false-acceptance/false-rejection
   as `not_computable` without a labelled corpus. Treat these as "not obviously dead", not as
   "proven alive". (`stage-agents.jsonl`, `hm verifier_discrimination report`)

4. **Model-specific rules reverse.** opus-5 grows code 1.258× per loop and never dries;
   gpt-5.6 shrinks it 0.906× and goes quiet early ("silence is not coverage"). A round cap tuned
   on one is wrong on the other. harness-bench refuses to transfer these and so should the
   harness. ([ADOPT.md](https://github.com/Ecro/harness-bench) "Rules that reversed")

5. **Fan-out is not a general law.** +52% unique findings on Python, 43% vs 50% recall on C
   firmware; the narrow `state-invariant` lens re-introduced a false positive that repository
   access had removed. Production forces 7 lenses regardless (CLAUDE.md records this as a
   *deliberate hold*, not an oversight — `reviewers.enabled` does not change dispatch).

6. **Host absorption is per-target.** Claude Code enforces worktree isolation at runtime;
   Codex's `/worktree` is experimental (Sep 9); Cursor's is Pro+. A HOST-redundant step deleted
   unconditionally re-creates the "Cursor reads the Claude render" failure (harness-diet pitfall 2).

7. **Vendor review products are single-vendor.** Code Review app, ultrareview, Bugbot all add
   an FP-verification pass now — the mode-A filter is host-redundant — but none votes across
   vendors, and "two models once each" is the one `***` rule with the largest measured gain.
   The cheapest INV win is turning `second_opinion.models` on, not off.

8. **Ledger blindness repeats.** The economics meter was blind to `_` paths ($1,637 invisible);
   the second-opinion ledger carried 150 test-written rows (61% vs 2% loss rate). Any per-model
   ablation must run through `ledger_exclusions` and the base-root writer, or it will "prove"
   whatever the contamination says.

9. **Accretion is the default.** Every recent BASELINE-DELTA is growth. Without a class tag,
   each new step is argued on its own merits and the surface only goes up.

## ❓ Open Questions

1. **Which axis first?** HOST cuts are `targets`-conditional renders (low risk, Claude Code
   only); COMP cuts are prose deletions (low risk, all targets); TUNE needs a bench run per
   model (cost). The order changes the phase plan.
2. **Where does the class tag live** — a column in `MATRIX-native-redundancy.md` (doc only), a
   frontmatter field on each `stages/*.md.j2` step, or a `models.py` field the renderer can
   act on (thin preset derivation)? The third is the only one the surface ratchet can enforce.
3. **Is a third preset ("Thin") warranted, or is Side re-derived from Table 1 enough?** Side
   already approximates thin; making it *derived* changes six knobs' defaults.
4. **Should `second_opinion.models` default to non-empty on Production** given it is the
   highest-graded INV item? Cost is 2× review/plan CLI calls; antigravity loss rate is 51% vs
   codex 2%, so "codex only" is the plausible default.
5. **Who runs the per-model bench and when?** On each vendor model release (manual), or wired
   into `claude plugin eval` (2.1.269)? The bench costs ≈$16 per model per experiment.
6. **What is the ground-truth arm for A.5 and plan-validator?** Without one, TUNE numbers stay
   "not obviously dead". A labelled corpus of known-bad RED tests / known-gap PLANs is a
   separate piece of work.
7. **Does the Pass 1/Pass 2 removal arm (`ABLATION-pass2`) run as part of this, or stay
   deferred?** Its decision rule is already fixed; only execution is missing.
8. **Production ledger rows are zero.** Do we accept Side-only evidence for TUNE decisions, or
   gate them on a Production sample first?

## 📚 Sources

External:
- Anthropic, "Managed Agents" — harness assumptions go stale as models improve. https://www.anthropic.com/engineering/managed-agents
- Anthropic, "Effective harnesses for long-running agents" — frontier models still need state/progress structure. https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents
- OpenAI, "Harness engineering" (search snippet; direct fetch blocked). https://openai.com/index/harness-engineering/
- Böckeler/Fowler, "Harness engineering" 2026-04-02 — deterministic sensors survive; AI-written tests not yet an oracle. https://martinfowler.com/articles/harness-engineering.html
- mini-SWE-agent vs OpenHands under Opus 4.5 (76.8 vs 77.6); augmentation gains largest on weaker models. https://arxiv.org/html/2512.10398v6
- DeepSWE 2026 — Opus 4.7 / GPT-5.4 write tests unprompted >80%; native vs standardized harness within noise (10-task pilot). https://arxiv.org/html/2607.07946
- RigorBench 2026 — explicit process discipline +41% process score, +17% outcome correctness. https://arxiv.org/abs/2606.22678
- "Model eats the stack" — compensatory layers subsumed; curated persistent context survives. https://arxiv.org/abs/2609.03141
- Claude Code docs: worktrees (runtime enforcement), code-review, ultrareview, memory, agent-teams. https://code.claude.com/docs/en/worktrees · https://code.claude.com/docs/en/code-review · https://code.claude.com/docs/en/ultrareview · https://code.claude.com/docs/en/memory · https://code.claude.com/docs/en/agent-teams
- Codex changelog (subagents GA, hooks GA, `/worktree` experimental 2026-09-09, Goal mode). https://learn.chatgpt.com/docs/changelog
- Cursor changelog / Bugbot / worktrees. https://cursor.com/changelog · https://cursor.com/docs/bugbot · https://cursor.com/docs/configuration/worktrees
- Agent OS v3 dropped spec/orchestration citing plan mode. https://github.com/buildermethods/agent-os/discussions/310
- GSD `--minimal` mode (~12K → ~700 tokens cold start). https://www.augmentcode.com/learn/gsd-58k-stars-claude-code
- GPT-6 Astra release (2026-09-03/04); no public scaffold ablation found. https://en.wikipedia.org/wiki/GPT-6_Astra · https://openai.com/index/safety-overview-gpt-6-astra/

Internal measurements (this session, 2026-09-12):
- `stage-agents.jsonl`: test-reviewer FAIL 39 / PASS 13 (n=52); plan-validator MAJOR_REVISION 37 / NEEDS_REVISION 1 / dispatch-failed 2.
- `review-*.jsonl` (70 rows, 44 slugs, 17 multi-round): pass1 401 → pass2 390 → consensus 66; regression_attributed 11; auto_fix_reverted 2.
- `hm verifier_discrimination report`: codex loss 2.1% (accepted 15 / judged 22), antigravity loss 51.5% (150 excluded rows applied).
- Rendered 0.55.0 stage sizes (lines / `!` calls / agent dispatches): research 468/8/0, spec 618/6/0, plan 1075/20/1, execute 817/15/2, review 1430/24/19, verify 462/12/0, wrapup 784/24/2.
- `harness-bench` `docs/review-convergence/{STUDY-ko,ADOPT}.md` — held-in-both-models vs reversed-between-models tables; fan-out §13.

## 🔗 Related Internal Docs

- [[RESEARCH-harness-diet]] / [[PLAN-harness-diet]] — the state-vs-behavior line and the ADR-003 reversal on `/hm:verify`.
- [[RESEARCH-workflow-time-token-savings]] — both capability-based deletions refuted by measurement (22%, 37.5%).
- [[RESEARCH-workflow-step-audit]] — "cut round-trips, not rigor"; stage-delegate precedent.
- [[RESEARCH-token-economy-step-pruning]] — prose is O(1), turns are O(context).
- [[MATRIX-native-redundancy]] — 41 surfaces scored against native host capability; the HOST axis already exists here.
- [[ABLATION-pass2-2026-08-05]] — pre-registered Pass 2 removal arm, not yet run.
- [[wiki:observability] stage-agent-ledger-reconciled-against-transcripts] — all ledger rows are Side-preset.
- [[feedback_plan_validator_single_pass]] — Step 4.5 already cut by user decision.
- CLAUDE.md "리뷰어 팬아웃은 언어 조건부다 — 기록만, 라우팅은 안 한다" — the deliberate hold on lens routing.
