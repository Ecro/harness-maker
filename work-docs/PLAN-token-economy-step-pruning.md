---
type: plan
task_slug: token-economy-step-pruning
status: phase-1-complete  # Phase 1 (meter correction) shipped + reviewed 2026-07-27. Phases 2-4 NOT started.
created: 2026-07-27
tags: [harness-maker, plan, python, token-economy, prompt-caching, observability, render]
spec: "[[SPEC-token-economy-step-pruning]]"
research_doc: "[[RESEARCH-token-economy-step-pruning]]"
interview_rounds: 4
adrs: 19
validator_outcome: MAJOR_REVISION_RESOLVED_THIRD_PASS
validator_passes: 3
summary: "Fix the billing model end-to-end, compact fused commands under a ratchet, bound reviewer reads visibly"
---

# PLAN — Token economy correction and stage-prompt compaction

## 🎯 Executive Summary

**TL;DR** — 65.6% of this repo's measured 30-day spend ($8,960 of $13,656 across
20,480 turns) is cache-**read** cost: re-reading carried context, not cache
misses. The instrument reporting that is wrong in several verifiable ways, and
the largest untouched prompt-side lever was explicitly deferred by a prior plan.
This plan fixes the meter **through to the production path**, compacts the
prompts, and bounds reviewer reads — without touching any verification mechanism.

**What changes, in four independent commits:**

1. **Meter correction** (`economics.py`, `cache_diagnostics.py`) — per-model
   price keys, per-model threshold resolution, TTL-tier-aware gap
   classification, **and the per-turn entry bridge that makes all three
   reachable from `/hm:health`**.
2. **Unattributed decomposition** (`economics.py`) — split `(unattributed)` on
   an observable adjacency predicate, conserving both turns and USD.
3. **Reviewer read budget** (`review.md.j2`) — bounded default, **visible
   elision**, always-available escalation, asserted at every dispatch site;
   plus the invariance guard proving the verification apparatus did not move.
4. **Fused-command compaction** (`workflow_fuse.py`, `_partials/`) — emit each
   block's **shared prose** once while the **per-stage command line still renders
   per stage**. 4.7% off `exec-rev-wrap-ver` (121,782 → 116,076 characters). The
   documentation-only trim that would have made this 12.0% is **withdrawn**
   ([ADR-017](#adr-017)) — it deleted runtime instructions.

**Why the obvious target was wrong.** The task began from the hypothesis that
`/hm:plan` has too many Steps. Measurement refutes it: `/hm:plan` is 5th at 7.7%
of spend with the **lowest** mean context (165K) and **lowest** carry (0.38) of
any working stage. Prose in a stage template costs O(1) cached tokens; a Step
that spawns a subagent or forces a tool round-trip costs O(context) per turn.
See [ADR-001](#adr-001).

**Key decisions:** [ADR-001](#adr-001) prune by turn-production ·
[ADR-002](#adr-002) per-model price keys · [ADR-003](#adr-003) reproducibility
clause reduced to what the system guarantees · [ADR-004](#adr-004) one function,
two defects · [ADR-005](#adr-005) TTL tier attribution ·
[ADR-006](#adr-006) hoist happens in `workflow_fuse.fuse()`, not the template ·
[ADR-007](#adr-007) budgets are test-local constants ·
[ADR-008](#adr-008) elision must be visible · [ADR-009](#adr-009) four commits ·
[ADR-010](#adr-010) mutation-check every gate · [ADR-011](#adr-011) golden
fixtures for **both** atomic and fused · [ADR-012](#adr-012) the entry bridge
becomes per-turn · [ADR-013](#adr-013) decompose on an observable predicate, and
correct the SPEC's category framing · [ADR-014](#adr-014) the ratchet's value,
unit and command set · [ADR-015](#adr-015) machine-SPEC predicates are the
contract and must carry every strengthening · [ADR-016](#adr-016) classify every
block before hoisting it — the finding that stopped this plan from breaking Gate 0 ·
[ADR-017](#adr-017) the documentation-only trim is withdrawn — it was the same
unclassified removal one level up, and it was 60% of the claimed saving.

**Estimated impact — stated honestly.** Direct token saving is **small**: the
fused command drops 4.7% (121,782 → 116,076 characters, ~30.4K → ~29.0K tokens;
≈0.4% of a turn's context). Three successive estimates went 8.2% → 12.0% → 4.7%,
each correction removing a removal that turned out to carry behaviour
([ADR-016](#adr-016), [ADR-017](#adr-017)). 4.7% is what survives classification.
The meter correction saves **zero** tokens; it decides whether the next
optimization is chosen on an instrument that is currently ~3× wrong for every
Opus turn *and* never applies a per-model cache threshold at all. The reviewer
read budget is the only large-upside item (`code-reviewer` carries 119.4M
context tokens) and the only one touching a verification surface, so it ships
behind this plan's strongest guard.

### Non-Goals

- Weakening any verification apparatus. [ADR-011](#adr-011) makes it
  machine-checkable on **both** the atomic and fused renders.
- Re-doing `CLOSE-workflow-optimization-2026-05` work.
- Changing `delegation.stages`, `default_workflow`, `resolve_model_family`, the
  `estimate_attribution` adjacency algorithm, or making `by_agent` a partition.
- Running an `effort` sweep (method in RESEARCH Appendix A).
- Proving a production token reduction (acceptance is mechanism + budget;
  wrapup delegation landed 2026-07-26 and confounds a near-term soak).

## 📚 Prior Work

| Source | Relevance |
|---|---|
| `CLOSE-workflow-optimization-2026-05` | `cache_control: ephemeral` on `llm_judge` — harness-maker's **only** request-construction surface. Activated Pass 1.5; skip Pass 1 when reviewers == 1. Non-goals here. |
| `PLAN-workflow-overhead-post024` | **Explicitly deferred "full Claude/Cursor fused command compaction to a follow-up."** This plan is that follow-up. Inherits "do not re-open Pass 1.5". |
| `PLAN-economics-attribution-and-carry` (2026-07-26) | Diagnosed `(unattributed)`: Claude Code drops `attributionSkill` when the user speaks mid-stage, so stage costs are **floors**. Shipped wrapup/verify delegation. Its non-goal "any change to pricing" is what leaves [ADR-002](#adr-002) open. |
| `[fail:test] assertion-invariant-over-named-dimension` (count 3, recurred 2026-07-27) | Governing risk. Canonical instance is *about cache-write tiers*. Drives [ADR-010](#adr-010). |
| `[wiki:gotcha] loop-body-skipping-review-stage` | Context-budget pressure once made an LLM silently treat review as optional. Drives the AC-009 guard. |
| `[wiki:gotcha] config-set-in-memory-must-serialize-to-the-consumed-file` | Why budgets are test-local constants ([ADR-007](#adr-007)) — and the exact shape of the C1 defect [ADR-012](#adr-012) fixes. |
| `[wiki:architecture] harness-economics-observability` | No-ratio invariant. Success metrics are `mean_context_tokens` and `carry_ratio`. |

## 🎙️ Interview Transcript

| # | Topic | Category | Question | Choice | Note | → ADR |
|---|---|---|---|---|---|---|
| 1 | Scope | Scope | Which of 5 open items? | **A+B+C+D** | All four workstreams. | ADR-009 |
| 2 | Done definition | Testing depth | Mechanism / +budget / measured | **Mechanism + render-time budget** | Measured reduction is confounded by wrapup delegation landing 2026-07-26. | ADR-007 |
| 3 | Quality floor | Risk tolerance | May verification shrink? | **Untouchable — non-goal** | Author surfaced the tension with item 1's C: a *cap* contradicts this; only an escalation-preserving default satisfies both. | ADR-008, ADR-011 |
| 4 | Pricing shape | Contract shape | Per-model keys / date-effective / single row | **Per-model keys + version bump** | `resolve_model_family` is longest-match already. | ADR-002 |
| 5 | Hoist mechanism | Architecture | Partials / post-render dedup / restructure | **Partials + hoist** | Keeps atomic renders as a clean differential control. | ADR-006 |
| 6 | Phasing | Risk tolerance | Independent / L1-first / single | **Independent, low→high risk** | Independent rollback per workstream. | ADR-009 |
| 7 | AC-003 reproducibility | Contract shape | Reduce / date-effective / leave haiku | **Reduce the clause honestly** | Forced by both second-opinion models. | ADR-003 |
| 8 | Read-budget P0 | Risk tolerance | Visible elision / drop AC-008 / index-only | **Visible elision** | antigravity P0: invisible truncation makes the clause inert. | ADR-008 |
| 9 | Phase 1 scope | Scope | Include the per-turn entry-bridge rework? | **Include** | Without it the corrected table is never exercised by the system it corrects. | ADR-012 |
| 10 | Response to validator-3 | Scope | Withdraw the doc trim + descope / 4th revision keeping it / Phase 1 only / abandon | **Withdraw the trim, descope** | Asked after the third validator returned MAJOR_REVISION with C1/C2 against the trim. The author had misclassified a removal as inert three times; the user chose to remove the class of error rather than attempt a fourth classification of the same material. | ADR-017 |

**Gate exits.** `Q-budget-N` failed **CLARITI** (the user cannot answer a byte
ceiling better than the author) → the value is derived in [ADR-014](#adr-014).
`Q-budget-store` failed **confidence** (0.85) → recorded as [ADR-007](#adr-007).

## 📐 Architecture Decision Records

### ADR-001: Prune by turn-and-context production, not by Step count
**Status:** Accepted (2026-07-27).
**Context:** The task began from "does `/hm:plan` need all these Steps?". Over
20,480 turns, `/hm:plan` is 7.7% of spend at 165K mean context and 0.38 carry —
the lowest of any working stage. Global carry is 0.656.
**Decision:** Optimize context volume per turn and turn/subagent production.
Template prose is a secondary ~12% target.
**Consequences:** ✅ Effort lands where the money is. ⚠️ The deliverable is
smaller than "delete half of `/hm:plan`" sounds.
**Rejected:** Deleting `/hm:plan` Steps — a Step heading is written once and
cache-read after, so 200 lines ≈ 50 tokens/turn amortized.
**Source:** Measurement; Interview #1.

### ADR-002: Per-model price keys; `resolve_model_family` unchanged
**Status:** Accepted (2026-07-27).
**Context:** `resolve_model_family` matches PRICE_TABLE keys as substrings,
longest-match wins, so `"opus"` captures `claude-opus-5` at $15/$75 against a
published $5/$25. Opus 4.6/4.7/4.8 are also $5/$25; Haiku 4.5 is $1/$5.
**Decision:** Add per-model keys (`opus-5`, `opus-4-8`, `opus-4-7`, `opus-4-6`,
**`opus-4-5`**, `sonnet-5`) at published rates; correct `haiku` to 1/5; keep
`opus` = 15/75 reachable for genuinely pre-4.5 ids; bump `PRICE_TABLE_VERSION`
to `"2"`. Leave `resolve_model_family` untouched.

`opus-4-5` is included because this ADR's own boundary is "pre-4.5" — without the
key, `claude-opus-4-5` falls to `opus` = 15/75, i.e. the 3× error this ADR exists
to fix, sitting exactly on the line the ADR draws (validator-3 L1). It is a
**pricing** key only; no `opus-4-5` row is added to AC-001's cache-minimum golden
table, because this plan has no published minimum for that model and inventing one
would be the circular oracle the SPEC forbids. **AC-003 gains an `opus-4-5` arm
and a `haiku` arm** — the haiku 1/5 correction was otherwise asserted by nothing
(validator-3 L2), which is precisely the change [ADR-003](#adr-003) amended the
SPEC Constraints row to permit.
**Consequences:**
- ✅ Zero matcher change, honoring the prior plan's non-goal.
- ⚠️ Correcting `haiku` reprices old Haiku turns on re-run (accepted, ADR-003).
- ⚠️ **The fallback stays at the pre-4.5 rate.** `price_turn`'s
  `fallback_model="opus"` and the `PRICE_TABLE["opus"]` last-resort mean a model
  released *after* this table is written is priced at $15/$75 — re-creating the
  exact 3× error this ADR fixes. `report.unknown_models` and
  `report.fallback_priced_turns` are the only signals. **Accepted as a known
  risk (R8)** rather than silently carried: changing the default fallback is a
  pricing-policy change beyond this task's scope.
**Rejected:** Date-effective tables (declined at #4); editing the single `opus`
row (leaves genuine pre-4.5 turns 3× under).
**Source:** Interview #4; validator warning on the fallback.

### ADR-003: The reproducibility clause is reduced to what the system can guarantee
**Status:** Accepted (2026-07-27, forced by cross-model second opinion).
**Context:** SPEC AC-003 originally required prior-version reports to reproduce.
Both models independently refuted it: `PRICE_TABLE_VERSION` is a **label**
copied into `EconomicsReport.price_table_version`, never a dispatch key, and
every report is recomputed from raw transcripts.
**Decision:** AC-003's third clause becomes "the emitted report's
`price_table_version` differs from the pre-change value". SPEC amended in place
with the rationale inline. **The SPEC Constraints row "must be bumped, never
edited in place" is amended in the same pass** — it asserted the refuted
invariant and would have blocked ADR-002's haiku correction. The stale
assertion in `economics.py:22-23` is corrected in Phase 1.

**There are two provenance signals, not one (validator-3 M5).** This ADR's thesis
is "the version field is the documented signal", but the report emits **both**
`price_table_version` and `price_table_effective_date`
(`economics.py:25` = `"2026-07-25"`, surfaced at `:180`). Bumping the version
while leaving the date ships a report that states the wrong date for when its
rates took effect — a second stale claim inside the fix for the first. Phase 1
updates **both**, and AC-003 asserts both changed.
**Consequences:** ✅ Stops promising what the architecture cannot deliver.
⚠️ Re-running a historical window yields different dollars; the version field is
the documented signal, and the effective-date field says from when.
**Rejected:** Date-effective dispatch (out of scope); calling a label bump
"reproducibility" (the original defect).
**Source:** Interview #7; codex P1 + antigravity P1; validator warning.

### ADR-004: `_threshold_for_model` has two defects, not one
**Status:** Accepted (2026-07-27).
**Context:** `_threshold_for_model` returns on the **first** substring match
(unlike `resolve_model_family`'s longest-match) then falls back to
`_DEFAULT_THRESHOLD = 1024`. Per-model keys alone would let `"opus"` shadow
`"opus-5"`; the 1024 fallback is what makes an unknown model produce a
`miss_min_threshold` verdict, which AC-002 forbids.
**Decision:** `_threshold_for_model` becomes longest-match **and** returns
`None` on no-match. The classifier branches on `None` to an explicit
unknown-model classification.
**Consequences:** ✅ AC-001 and AC-002 satisfied by one contract.
⚠️ The failure-mode set widens; `ai_readiness.py` and `improvement.py` consume
it (`improvement.py` formats `cache.primary_failure` into an ActionItem) and
must land in the same commit.
**Rejected:** Fixing match order only — leaves AC-002 unmet.
**Source:** codex P1 + antigravity P2.

### ADR-005: TTL tier is attributed from the most recent prior cache-writing turn
**Status:** Accepted (2026-07-27).
**Context:** `_TTL_SECONDS = 5*60` is hard-coded. The tier is observable in
`TokenUsage` but the turn being classified carries no creation-tier tokens, so
the attribution rule was undefined.
**Decision:** The applicable TTL for a gap comes from the most recent prior turn
**in the same session** that wrote cache tokens: `cache_write_1h_tokens > 0` →
3600s, else 300s. Both tiers non-zero → 1h wins. No attributable prior write →
300s, with the diagnosis recording that the tier was assumed, not observed.
**Consequences:** ✅ Derived from transcript data, not a config knob.
⚠️ A session whose first write is outside the window falls back to 5m and may
over-report `miss_ttl` — surfaced, not silent.
⚠️ Requires the per-turn entry bridge ([ADR-012](#adr-012)); the current bridge
sums the tiers away and carries no session key.
**Rejected:** A `harness.yaml` TTL setting; reading the tier off the classified
turn (the field is absent there).
**Source:** codex P1 + antigravity P1; validator critical C2.

### ADR-006: The change is emit-once plumbing in `fuse()`, not extraction
**Status:** Accepted (2026-07-27); **mechanism corrected twice** — first by
validator C5, then by validator N-block after re-measurement.
**Context:** Two successive drafts described this wrong. The first said "render
shared blocks once from `workflow_command.md.j2`" — but that file interpolates a
string built in **Python** by `workflow_fuse.fuse()`. The second said "extract
the shared blocks into new files under `templates/agents/_partials/`" — but
`worktree_preflight.md.j2` and `gate0_receipt.md.j2` **already live there** and
are already `{% include %}`d per stage with per-stage variables (`hm_stage`,
`gate0_stage`). There is nothing to extract.
**Decision:** The work is (a) `fuse()` emitting each block's **shared prose**
once ahead of the per-stage loop, (b) a suppression signal threaded into each
per-stage `tpl.render(...)` — reusing `workflow_context` if it already
discriminates fused from atomic, adding no new flag if so, (c) an explicit
decision on the per-stage parameters those partials interpolate, governed by
[ADR-016](#adr-016), and (d) **`fuse()` replicating the
`worktree.feature_branch_workflow` gate**.

**(d) is not optional (validator-3 C5).** `_partials/worktree_preflight.md.j2:2-7`
assigns the gate to its includer: *"The INCLUDING stage owns the
`worktree.feature_branch_workflow` gate (a `{%- if … %}` wrapper) so this partial
is only rendered when the flag is on — its own whitespace therefore never affects
the flag-OFF snapshot fixtures."* Hoisting moves the emit site out of the stage
body and into `fuse()`, which today builds `parts` before the per-stage loop and
reads nothing from the `config_dump` it already holds. A naive preamble therefore
emits preflight prose into **flag-off** harnesses — which CLAUDE.md requires to
stay GREEN through the migration soak, and which the partial says are
snapshot-fixture-protected. AC-006 gains a flag-off arm asserting the block is
**absent**, so the gate's survival is tested rather than assumed.
**Consequences:**
- ✅ Atomic renders remain an unmodified differential control for AC-007.
- ⚠️ Phase 4 touches Python (`workflow_fuse.py`, possibly `synthesize.py`).
- ⚠️ The partials must be split into a shared-prose part and a per-stage part;
  that split is the actual engineering, not the include wiring.
- ⚠️ Phase 4 must render **both** flag states to satisfy AC-006.
**Rejected:** Post-render dedup; restructuring all 7 stage templates; hoisting
without the flag gate (silently changes flag-off output).
**Source:** Interview #5; validator-2 C5 + N-block; validator-3 C5.

### ADR-007: Size budgets are test-local constants, not `harness.yaml` config
**Status:** Accepted (2026-07-27, author assumption).
**Context:** A `harness.yaml` key would reproduce
`config-set-in-memory-must-serialize-to-the-consumed-file`. Codex flagged the
same class independently.
**Decision:** The budget table is a constant in
`tests/structural/test_command_size_budget.py`.
**Consequences:** ✅ No new serialization path. ⚠️ Not user-tunable — correct for
a CI regression ratchet.
**Rejected:** A config block; a generated snapshot file.
**Source:** Author assumption at confidence 0.85.

### ADR-008: A read budget is only admissible if elision is visible
**Status:** Accepted (2026-07-27, antigravity P0).
**Context:** Interview #3 locked "verification untouchable" while #1 put the
read budget in scope. antigravity rated the combination **P0**: truncation that
leaves complete-looking content gives the reviewer no signal, so the escalation
clause never fires and the budget silently lowers recall.
**Decision:** A bounded read must **visibly mark every elision**. Escalation is
unconditional. Plain truncation is prohibited. The clause must state explicitly
that escalation **covers files outside the diff** (imports, tests, template
dependencies) — the dependency-discovery case a marker cannot signal, because a
file never opened leaves no marker anywhere.
**Consequences:** ✅ Restores the observation the escalation decision needs.
⚠️ Markers cost tokens — correct trade. ⚠️ Residual, accepted: no marker can
signal an unopened file; SPEC Open Question 5 (labelled diff set) is the only
oracle and stays out of scope.
**Rejected:** Dropping AC-008; index-only with no budget (kept as R3 fallback).
**Source:** Interview #8; antigravity P0; validator warning on file scope.

### ADR-009: Four independent commits, low risk to high risk
**Status:** Accepted (2026-07-27).
**Decision:** Commit 1 meter correction (pricing + thresholds + TTL + entry
bridge), commit 2 unattributed decomposition, commit 3 reviewer read budget +
invariance guard, commit 4 fused compaction. Each independently revertable;
each phase's rollback is **its own commit**, so the instruction holds regardless
of landing order.
**Consequences:** ✅ The meter is correct before anything is measured against
it. ⚠️ Intermediate commits do not satisfy the full AC set — the SPEC is the task
contract, not a per-commit contract.
**Rejected:** Single commit; ship-then-re-decide (declined at #6).
**Source:** Interview #6; codex P2; validator warning on Phase 3's rollback.

### ADR-010: Every new gate is mutation-checked
**Status:** Accepted (2026-07-27).
**Context:** `[fail:test] assertion-invariant-over-named-dimension` is at count
3 and **recurred today inside the fix for itself**. Its canonical instance is
about cache-write tiers, which this plan touches. Both second-opinion models
found two further instances in the draft ACs.
**Decision:** For every assertion, name the wrong implementation it rejects and
verify it fails against that implementation (delete the code, name the test that
dies), recorded in the commit message. Concretely: AC-005 pairs its ceiling with
a **floor** and AC-007's no-loss check; AC-010 requires **both buckets
non-zero** plus per-turn membership; AC-004 keeps paired 5m/1h arms; AC-006
pairs counts with a **content fingerprint**; AC-001/002 assert against the
**production entry path**, not only the resolver ([ADR-012](#adr-012)).
**Consequences:** ✅ The plan's gates are checked against the failure they are
most likely to reproduce. ⚠️ More test code per AC.
**Rejected:** Prose prevention — it has failed three times.
**Source:** The ledger; codex P1 ×2; antigravity P1 + P2.

### ADR-011: Golden fixtures for both the atomic and the fused render
**Status:** Accepted (2026-07-27); extended by validator-2 C4; **discovery
defined and coverage corrected** by validator-3 C3 + H3.
**Context:** AC-009 compares before and after. Re-rendering both sides, or
grepping pass names, passes even when structure is deleted. An earlier draft
pinned only the atomic fixture and extended only AC-008 to the fused render —
leaving the identical hazard on AC-009, on the **default** workflow.
**Decision:** Pin **three** committed goldens:
`tests/fixtures/review_command_pre_change.md` (atomic),
`tests/fixtures/review_command_fused_pre_change.md` (fused), and
`tests/fixtures/plan_command_fused_pre_change.md` (a **plan-bearing** fused
render). AC-009's structural comparison — reviewer pass count, enabled reviewer
set, consensus threshold, second-opinion invocation points — runs against the two
review goldens; its **validator invocation points** conjunct runs against the
plan-bearing golden.

**Why the third golden (validator-3 H3).** No review render contains a
`plan-validator` dispatch, so comparing `validator_invocation_points` across two
review renders was `∅ == ∅` in every possible world — including one where the
dispatch had been deleted. The dispatch is real (`plan.md` Step 4, with both
`second_opinion_invoke` calls) and **is** in Phase 4's blast radius: Phase 4
regenerates every command under `.claude/commands/hm/`, and the fused set includes
plan-bearing workflows. AC-009 additionally asserts the golden's own dispatch
count is `>= 1`, so the guard fails if the fixture ever stops being a witness.

**Discovery, now defined (validator-3 C3).** AC-008's quadruple (bounded default,
visible elision, escalation, outside-diff scope) is asserted **per reviewer
dispatch site**, not as a whole-document grep. `reviewer_dispatch_sites(render)`
was previously named but never defined, which left it free to be implemented as
"blocks that already contain a bounded-read clause" — vacuously true in every
world. It is now defined against an anchor that exists **before** the edit:
**every `####` heading block inside the reviewer-dispatch step whose body names a
reviewer agent to run.** On the pre-change template that is exactly four sites —
Pass 1 (`:175`), Pass 1.5 (`:194`), Pass 2 (`:216`), and
`#### Direct review (single reviewer — Pass 2 only)` (`:223`). The predicate also
carries an explicit non-emptiness conjunct, because `all()` over an empty set is
`True`.

**The fourth site needs a third render, not just discovery.** The earlier draft
claimed discovery "avoids an unguarded fourth site". **That was false.** Sites
were discovered from `atomic_review_render()` and `fused_review_render()`, both
produced from this harness's multi-reviewer config — and the fourth site lives in
the `{% else %}` of `{% if (config.reviewers.enabled) | length > 1 %}`
(`review.md.j2:170/217/223`), which that config **structurally cannot emit**. The
site was exactly as unguarded as before. AC-008 therefore runs over **three**
renders: atomic, fused, and one rendered with `reviewers.enabled` of length ≤ 1,
named separately in its own non-emptiness conjunct so an empty discovery on that
render alone cannot hide.

**Pass 1.5 is asserted, not exempted.** It dispatches `code-verifier`, which today
reads nothing of its own. Exempting it is what made the earlier
"Pass 1 / 1.5 / 2" enumeration vacuous, and the site gains a read the moment the
verifier does — so Phase 3 edits **four** sites, not three.

Introduced in Phase 3; must stay green through Phase 4, which must not regenerate
any of the three fixtures.
**Consequences:** ✅ A structural deletion in either commit, on any of the three
render paths, fails a test. ⚠️ Fixtures must be regenerated deliberately when the
review or plan stage legitimately changes — that is the point. ⚠️ Phase 3's scope
grows by one fixture and one template site.
**Rejected:** Re-rendering both sides at test time; whole-document greps;
discovery over multi-reviewer renders only (cannot reach the fourth site);
dropping the `validator_invocation_points` conjunct as unguardable (it guards a
real dispatch that Phase 4 re-renders).
**Source:** codex P1 ×2; validator-2 critical C4 + warning; validator-3 C3 + H3.

### ADR-012: The `cache_diagnostics` entry bridge becomes per-turn
**Status:** Accepted (2026-07-27, validator criticals C1 + C2; Interview #9).
**Context:** `diagnose_cache_from_turns(turns, model="sonnet", …)` resolves the
threshold **once per window** from a caller-supplied string, and all three
production callers in `ai_readiness.py` pass a hard-coded
`model="claude-sonnet-4-6"`. `_entry_from_turn` never copies `TurnRecord.model`,
sums the two cache-write tiers into one `cache_creation_tokens` key, and carries
no `session_id`. Consequently a corrected per-model table would **never be
exercised** by `/hm:health`, and ADR-005's rule would be unimplementable — the
exact `config-set-in-memory-must-serialize-to-the-consumed-file` shape this plan
cites as prior work.
**Decision:** `_entry_from_turn` additionally carries `model`,
`cache_write_5m_tokens`, `cache_write_1h_tokens`, and `session_id`.
`cache_creation_tokens` (the tier sum) is **retained** — its docstring records
that dropping it reclassifies every write turn as a sub-threshold miss.
`_classify_turn` resolves the threshold **per turn** from `entry["model"]`;
`_build_evidence` and `_detect_ttl_regression` stop assuming one threshold per
window. `diagnose_cache_from_turns`'s `model` parameter becomes the fallback for
turns whose own model is absent, not the window-wide answer.
**Consequences:**
- ✅ AC-001, AC-002 and AC-004 reach the production path instead of only the
  resolver.
- ⚠️ Phase 1 grows to the entry schema and three classifier helpers. This was an
  explicit user decision (Interview #9), not scope creep.
- ⚠️ `_detect_ttl_regression` re-runs `_classify_turn` over half-window segments
  and must carry the same per-turn state.
- ⚠️ **"Same session" survives only because `session_id` is now on the entry.**
  `diagnose_cache_from_turns` flattens all sessions into one chronological list,
  so the TTL attribution must skip prior entries whose `session_id` differs
  rather than taking the chronologically previous entry.
**Boundary rules (validator warning — otherwise Phase 1 ships a plausible but
wrong `ttl_regression` signal that no AC covers):**
1. **The prior-write lookup crosses `_detect_ttl_regression`'s segment
   boundary.** That helper splits `entries` at `mid` and re-classifies each half
   with `prev = None`; confining the lookup to a segment would strip the second
   half's leading turns of their attributable 1h write, inflate second-half
   `miss_ttl`, and manufacture a false regression along the exact axis the helper
   measures (`rate_recent > rate_early + 0.15`).
2. **The tier lookup is session-scoped; the gap arithmetic is not.** The existing
   gap comparison against `prev_entry` is unchanged — only the TTL *tier*
   resolution skips prior entries whose `session_id` differs.
3. **`_build_evidence` must stop hardcoding the 5-minute framing.** It currently
   formats one `threshold` and one `model` into user text and says "> 5 min gap"
   / "keep sessions tighter (< 5 min…)". With `int | None` thresholds and mixed
   tiers it must emit the tier that actually applied, and render an explicit
   unknown-model line instead of "prefix ≥ None tokens".

**Each boundary rule is bound to a named test (validator-3 H2).** The three rules
were stated as prose obligations with no assertion behind them, which is the same
document split [ADR-015](#adr-015) exists to close. Bindings:

| Rule | Bound by | Rejects |
|---|---|---|
| 1 — lookup crosses the segment boundary | `test_ttl_regression_not_manufactured_by_segment_split` (Phase 1) | a lookup confined to `_detect_ttl_regression`'s half-window, which strips the second half's leading turns of their 1h write and manufactures a regression along the exact `rate_recent > rate_early + 0.15` axis the helper measures |
| 2 — tier lookup is session-scoped, gap arithmetic is not | **AC-004 arm 3** (`prior_write_in_other_session`) | taking the chronologically previous entry regardless of `session_id` — the live failure mode, since `diagnose_cache_from_turns` flattens all sessions into one list |
| 3 — evidence stops hardcoding the 5-minute framing | `test_evidence_names_the_applied_tier_not_a_hardcoded_five_minutes` + `test_evidence_states_the_minimum_is_unknown_for_an_unknown_model` (Phase 1) | a "< 5 min" remedy on a turn whose applied tier was 1h; and the fabricated "prefix < 1024 tokens" HEAD emits for an unknown model, or the literal `prefix ≥ None tokens` an `int \| None` produces through the old f-string |

Only rule 2 rises to an acceptance criterion; rules 1 and 3 are named Phase 1
tests. That is a deliberate asymmetry — rule 2 changes a reported *verdict*,
rules 1 and 3 change a reported *signal* and its *wording* — and it is recorded
here so the asymmetry is a decision rather than an omission.

**Rejected:** Resolver-only correction with the unreached production path
recorded as a limitation (Interview #9 option B — makes the workstream nearly
meaningless); a separate Phase 1b (leaves an intermediate commit that looks
fixed but is not).
**Source:** Validator criticals C1 + C2; Interview #9.

### ADR-013: Decompose on an observable predicate, and correct the SPEC's category framing
**Status:** Accepted (2026-07-27, validator critical C3).
**Context:** SPEC AC-010 named the documented-exempt part as "loop iterations
without per-stage granularity, `feature_branch_workflow: false` harnesses,
Cursor/Codex sessions with no session-end closure hook". Checked against the
data model: **none of the three is a per-turn property.** `TurnRecord` carries
`session_id, ts, model, usage, attribution_skill, attribution_agent,
is_sidechain, task_slug, written_paths, cwd, git_branch, uuid,
preceded_by_user`. Worse, two of the three are not turn classifications at all —
Cursor and Codex write **no Claude Code transcripts**, so those sessions never
enter the report as turns; `feature_branch_workflow: false` is a repository
config, not a turn attribute. With no rule, any invented split satisfies both
the conservation predicate and a self-authored fixture.
**Decision:** Decompose the `(unattributed)` bucket on an **observable**
predicate over fields that exist:
- **recoverable** — the turn has a resolvable neighbour stage within the
  configured adjacency window (`economics.adjacency_max_gap_min` = 10.0,
  `adjacency_max_turns` = 20), or carries `preceded_by_user: true`, which is the
  direct signature of the documented cause (Claude Code drops `attributionSkill`
  when the user speaks mid-stage).
- **unrecoverable-in-window** — no resolvable neighbour and no user-turn
  adjacency.

Population-level exemptions (Cursor/Codex, flag-off harnesses) are reported as
**notes on the report**, not as buckets, because they are absences from the
population rather than members of it. SPEC AC-010's category list is amended
accordingly.
**The decomposed population is the `by_stage["(unattributed)"]` bucket** — turns
whose `source` is `adjacency` or `none` (430 + 5,812 in the current window) —
**not** every turn with `attribution_skill is None`, which `unattributed_usd`
uses and which additionally sweeps in all 5,931 `inferred`-sourced turns. The two
populations differ by thousands of turns; implementing over the wider one would
fail the machine predicate late in Phase 2. Capped turns
(`economics.py:476-484` forces `est = None`) are never `recoverable`.

The population-level exemption notes are emitted as a named field,
`unattributed_breakdown_notes: list[str]`, so the SPEC's re-framing is observable
in the artifact rather than living only in prose.

Grounding: the current report already exposes `turns_by_attribution_source`
= `{direct: 8307, inferred: 5931, adjacency: 430, none: 5812}` and the matching
USD split, so the predicate is built on a signal that already ships.
**Consequences:**
- ✅ The split is reviewable now rather than invented at implementation time.
- ✅ It directly answers SPEC Open Question 1 with a defined meaning.
- ⚠️ "recoverable" means *adjacency-resolvable*, not *will be recovered*. The
  report must say so in its own field documentation.
**Rejected:** Implementing the SPEC's original three categories (two are not
turn properties); leaving the predicate to execute (unreviewed split).
**Source:** Validator critical C3; `turns_by_attribution_source` measurement.

### ADR-014: The ratchet's value, unit, and command set — re-derived from measurement
**Status:** Accepted (2026-07-27); arithmetic corrected by validator-2 N2;
**value revised down** by validator-3 C1/C2 via [ADR-017](#adr-017).
**Context:** The first derivation claimed 3 blocks × 3 redundant copies ≈ 9,963
chars ≈ ">= 10% off 121,782". Two errors: 121,782 − 9,963 = **111,819**, already
above the 110,000 ceiling it set; and the 9,963 assumed the blocks were
duplicates, which [ADR-016](#adr-016) shows they are not. The second derivation
added an 8,738-char "documentation-only" trim to reach 110,000;
[ADR-017](#adr-017) withdraws it. Third and final measurement:

| Source | chars |
|---|---:|
| Hoistable shared prose (preflight 3,729 + Gate 0 shared prose 1,977) | **5,706** |
| ~~Documentation-only sections dropped from the fused render~~ | ~~8,738~~ **withdrawn — ADR-017** |
| **Total removable** | **5,706 (4.69%)** |
| Projected post-change | **116,076** |

Communication Protocol's 120 chars are **not** in the hoistable figure — ADR-016
removed the block from scope but the second derivation kept its contribution in
this table (validator-3 M1). 5,706, not 5,826.
**Decision:**
- **Unit:** characters (`len(read_text())`), stated in the test docstring. The
  earlier "bytes" wording (and the `wc -c` provenance note) is corrected
  everywhere — the file is UTF-8 with substantial multi-byte content, so the two
  counts differ.
- **Set:** every file under `.claude/commands/hm/`, each with its own entry.
- **Ceiling:** `measured_post_change * 1.02` per file; for `exec-rev-wrap-ver`
  **≤ 119,000 characters** (116,076 × 1.02 = 118,397, ~0.5% headroom under the
  ceiling). The hoist is now the only source, so the ceiling is set where the
  hoist alone lands rather than where a target reduction would like it to be.
- **Floor:** `measured_post_change * 0.80` per file.
- **AC-007 compatibility:** with the trim withdrawn, Phase 4 removes no `##`
  section from any render. AC-007's subset rule is trivially satisfied for the
  hoist because the hoisted prose still appears in the fused document, once.
**Consequences:** ✅ AC-005 is falsifiable against a number derived from the
artifact. ✅ The ceiling is now reachable by the work actually in scope, so it
cannot silently pressure the executor into deleting content to meet it —
which is how the withdrawn trim entered the plan. ⚠️ **The headline benefit of
workstream B is 4.7% of one command ≈ 1,400 tokens per fused invocation.** That
is small, and stating it plainly is the point: the plan's real value is in
Phase 1 (the meter) and Phase 3 (the reviewer read budget), not here.
**Rejected:** `< 121,782` (unfalsifiable); a ceiling whose derivation exceeded it;
**a ceiling reachable only by deleting behavioural instructions** ([ADR-017](#adr-017)).
**Source:** SPEC OQ4; codex P2; validator-2 warning + N2; validator-3 C1/C2/M1.

### ADR-017: The documentation-only trim is withdrawn
**Status:** Accepted (2026-07-27, validator-3 criticals C1 + C2 — confirmed by
direct inspection of the committed render before acceptance).
**Context:** [ADR-016](#adr-016) established the discipline that made this plan
safe: **classify every candidate block before removing it**, because a block that
looks like formatting can be the mechanism. That discipline was then applied only
to the three blocks it was derived from. The larger removal —
8,738 chars, 60% of the claimed saving, described as "documentation-only" — was
never classified. Inspecting it:

| Section | What it actually carries in the **fused** render |
|---|---|
| `## When to Run` (review, `:534`) | `> When invoked as part of a fused workflow, the skip conditions above do **NOT** apply — always run.` |
| `## When to Run` (wrapup, `:1228`) | `> When invoked as part of a fused workflow, always run — do not skip based on the conditions above.` |
| `## Purpose` (execute, `:85`) | use `test_dep_map.build_test_hints()` to run only affected tests in Phase D — deleting it makes Phase D run full suites |
| `## Inputs` (verify, `:1969-1974`) | the dashboard and `findings-*.jsonl` paths that **drive Check 3 and Check 4**; the Checks do not restate them |
| `## Usage` (verify, `:1960-1967`) | "without `--reason=<text>`, `--force` requires confirmation via `AskUserQuestion`" — stated nowhere else |
| `## Quality Bar` ×4 | binding exit invariants: "No `git commit` invoked from this stage", "**Exactly one** commit per wrapup invocation", "the gate is **non-negotiable**" |
| `## Outputs` ×2 | the `work_docs/` (underscore) footgun warning that verify carries a dedicated probe for |

The two `When to Run` lines are the decisive case. In the **atomic** render that
section is genuinely documentation — its skip conditions apply. In the **fused**
render it carries the *negation of itself*, and that negation exists only because
the render is fused. The trim was scoped to the fused render only — that is,
precisely the render where the section stops being documentation. RESEARCH cites
`[wiki:gotcha] loop-body-skipping-review-stage` — "context-budget pressure once
made an LLM silently treat review as optional" — as prior work for this very
plan. The trim would have deleted the mitigation for the failure the plan cites.

Each `## Quality Bar` is also immediately followed by
`<!-- @hm:user:extra-quality-checks -->`, a user-owned preservation block anchored
to a section being deleted (CLAUDE.md checkpoint #1, unaddressed).

Compounding, **no acceptance criterion could see any of it.** ADR-014's stated
AC-007 compatibility argument — "not Step/Phase/Check headings, no `!`-prefixed
lines" — is exactly what AC-007's predicate tests, so the argued compatibility
*was* the blindness. AC-005's floor is `measured_post_change * 0.80`, derived
from the artifact the change produces, so it can only catch a *future*
over-trim. AC-009 compares five properties of the review render, and "review is
actually run" is not among them.
**Decision:** The documentation-only trim is **removed from scope entirely**. No
`##` section is dropped from any render in this plan. AC-005's ceiling is
re-derived from the hoist alone ([ADR-014](#adr-014): 119,000).
**Consequences:**
- ✅ The plan stops carrying a 8,738-char removal with zero acceptance coverage
  that `/hm:execute` would have landed green.
- ⚠️ Workstream B's benefit falls from a claimed 12.0% to a measured **4.7%**.
  This is the honest number and the plan states it rather than restoring the
  trim to protect the headline.
- ⚠️ If a future plan wants this trim, it owes a **per-section classification
  table** with ADR-016's discipline, plus its own AC — not an argument that the
  sections look like documentation.
**Rejected:** Trimming a narrowed subset (the same unclassified reasoning at
smaller scale — the exact failure this plan has now committed three times);
keeping the trim with a `## Quality Bar` carve-out (leaves `When to Run`,
`Inputs` and `Usage` unclassified).
**Source:** Validator-3 criticals C1 + C2; independently confirmed against
`.claude/commands/hm/exec-rev-wrap-ver.md:534` and `:1228` before acceptance.

### ADR-015: The machine SPEC is the contract and carries every strengthening
**Status:** Accepted (2026-07-27, validator warning).
**Context:** `/hm:execute` writes tests from the machine SPEC's `test_ids` and
`executable_predicate`. ADR-003's correction was propagated there, but
ADR-004/005/010/012/013/014's strengthenings existed only in PLAN prose. The
predicates still referenced APIs the plan rejects — `classify_gap(ttl="1h")`
passes TTL as a parameter, which ADR-005 explicitly replaces with derivation
from a prior turn; `classify_turn(model=…)` names a function that does not
exist.
**Decision:** Before `/hm:execute`, every strengthened AC's
`executable_predicate` and `note` are updated in
`SPEC-token-economy-step-pruning.machine.yaml` to match its ADR. The PLAN never
carries a strengthening the machine SPEC lacks.
**Consequences:** ✅ Closes the document split that would have reproduced the
count-3 failure inside the plan written to prevent it. ⚠️ Any later ADR change
must patch both files.
**Rejected:** Relying on the executor to read PLAN prose.
**Source:** Validator warning.

### ADR-016: Classify every candidate block before hoisting it
**Status:** Accepted (2026-07-27, validator N1 — the most consequential finding
of this plan).
**Context:** The premise of workstream B was "three shared blocks appear 4× each
= 9,963 wasted chars". Measured line-by-line against the committed render, that
is substantially false. Each block falls into a different class:

| Block | copies | chars/copy | identical prose | per-stage | class |
|---|---:|---:|---:|---:|---|
| worktree preflight | 4 | 1,403 (uniform) | **1,243** | 160 (`--stage hm:<stage>`) | **parameterised — hoistable prose** |
| Gate 0 receipt | 4 | **1,300 / 1,700 / 1,500 / 1,380** | 659 | **the remainder** (heading, pass/fail criteria, `--stage <stage>`) | **parameterised — mostly per-stage** |
| Communication Protocol | 4 | 349 | **40** | **309** | **per-stage semantic — NOT hoistable** |

Gate 0's copies are **not equal** (validator-3 M2): the second derivation wrote
`4 × 1,920`, which both inflated the figure ~30% and implied uniformity the render
does not have — execute ≈1,300, review ≈1,700, wrapup ≈1,500, verify ≈1,380. The
load-bearing number is unaffected: the **659** identical chars are the 151-char
imperative + the 171-char `skipped` bullet + the 347-char guard base, and only
that intersection is hoisted.

**One receipt per stage is the Gate 0 mechanism.** `gate0_receipt.md.j2:33`
renders `--stage {{ gate0_stage }}`; the four copies emit `execute`, `review`,
`wrapup`, `verify`. Collapsing them to one would make the autoloop driver see
three stages as missing on every iteration — the block's own text says "Gate 0
can detect **missing stages**" and "without it Gate 0 would loop forever".
**Decision:**
- **Communication Protocol is removed from AC-006's set.** 40 shared chars of
  349 is not a shared block; hoisting it would destroy per-stage content for a
  120-char gain.
- **AC-006 is restated**: the shared *prose* of the preflight and Gate 0 blocks
  renders **once**; the per-stage command line renders **once per stage**, and
  AC-006 **asserts** all four `--stage` values are present rather than forbidding
  them.
- No block is hoisted before it is classified by this table.
- **Gate 0's hoisted intersection must not become positionally false.** The shared
  prose opens `**You have completed the stage.** Emit a receipt…`, which is untrue
  at a preamble emitted ~2,000 lines before any stage completes, and its guard
  paragraph has three variants (base; base + standalone; base + extra), so a naive
  intersection leaves orphan fragments referring to a `[ -f ]` test defined far
  upstream. Phase 4 rewrites the hoisted sentence to be position-correct and hoists
  only the variant-free remainder; AC-006's `fingerprint == 1` cannot see either
  problem, so this is a stated Phase 4 obligation rather than a gated one
  (validator-3 M3).
**Consequences:**
- ✅ Resolves the AC-006/AC-007 joint unsatisfiability: AC-007 requires the
  atomic `--stage wrapup` line to survive into fused, which the restated AC-006
  now also requires instead of contradicting.
- ✅ Removes a change that would have silently broken the autoloop.
- ⚠️ Workstream B delivers **4.7%** from hoisting. With the documentation-only
  trim withdrawn ([ADR-017](#adr-017)), that is the whole of it.
- ⚠️ **This ADR's own discipline was not applied to the larger removal.** The trim
  was left unclassified in the same revision that authored this table, and
  [ADR-017](#adr-017) had to withdraw it. Classifying "the blocks I am currently
  measuring" is not the rule; classifying **every** removal is.
**Rejected:** "Shared blocks appear exactly once" as originally written — it
described a formatting change and specified a behavioural regression.
**Source:** Validator N1, confirmed by direct measurement of the committed render.

### ADR-018: R8 gets an observability signal, not a policy change
**Status:** Accepted (2026-07-27, review round 3 — supersedes ADR-002's deferral).
**Context:** [ADR-002](#adr-002) recorded R8 — "a model released after this table is
priced at the pre-4.5 fallback" — as an accepted risk, with
`report.unknown_models` / `fallback_priced_turns` named as the surfacing signals and a
policy change deferred to a follow-up. Round-3 review showed **the surfacing claim was
false**. `resolve_model_family` matches substrings, so `claude-opus-9` matches the
`"opus"` family key and returns non-None; `price_turn`'s `used_fallback = family is
None` therefore stays False and the turn increments neither field. It is priced at
15/75 with **no diagnostic trace at all** — bit for bit the recurrence of the defect
this plan exists to fix, guaranteed to happen at the next model release, silently.
Those two fields only ever caught ids matching no key whatsoever (`gpt-*`). Asserting
an untested safety net is precisely how the original defect survived.
**Decision:** Add a **distinct** signal, `TurnCost.priced_with_family_row` →
`report.family_priced_turns` / `family_priced_models`. Detection is
`family is not None and "-" not in family` — every point-release key carries a hyphen
and the family rows do not, so no version heuristic is needed (a newly released model
always brings a version suffix).

**This is observability, not the deferred policy change.** No rate moves; the family
row still serves as the fallback, which remains ADR-002's locked decision. What changes
is that the fallback becomes visible. That distinction is what makes it admissible in
Phase 1 — the scope-out line "the `price_turn` fallback policy (ADR-002 R8)" is
amended to "the fallback **policy**; its observability is in scope".

The two signals are never collapsed: `priced_with_fallback` means the id matched no key
at all, `priced_with_family_row` means it matched a bare family row. A test arm asserts
`gpt-4` sets the first and not the second.
**Consequences:**
- ✅ The next model release surfaces itself instead of quietly repricing 65.6% of the
  bill at 3x.
- ✅ The gate asserts through `report.model_dump(mode="json")`, the form the CLI emits —
  not the in-memory flag. A signal that aggregates correctly and never reaches the
  payload is the `config-set-in-memory-must-serialize-to-the-consumed-file` shape, and
  checking the flag alone would have repeated the exact mistake this ADR corrects.
- ⚠️ `TurnCost` gains a defaulted field. Existing constructors are unaffected.
- ⚠️ It reports a fact, not a fault: `claude-haiku-3` is family-priced and correctly so.
  The signal reads "this turn took a family rate — consider whether a point-release row
  is owed", not "this is wrong".
**Rejected:** Implementing the fallback-policy change (still out of scope); a
version-digit heuristic (a rule that can be wrong, for no gain); deleting the false
claim from the comment and leaving the blind spot (the round-2 response — honest about
the gap, but the gap is the recurrence path of the headline defect).
**Source:** Review round 3, code-reviewer P1 on the false safety-net claim.

### ADR-019: The unknown-minimum case reports a fact and stops there
**Status:** Accepted (2026-07-27, review round 3).
**Context:** Rounds 1-2 grew the `miss_unknown_model` handling into: a per-turn
`unknown_threshold_turns` property tracked independently of classification, an
`_incompleteness_caveat()` appended to both evidence and remediation for every primary,
a dedicated no-primary branch, and a remediation telling the user to upgrade and report
the model id. Round 3 found that structure defective in three independent ways at once,
and the three interacted:
1. The caveat had **no consumer** — `improvement._extract_layer3_actions` returns `[]`
   when `primary_failure is None`, which is exactly the branch the caveat was built for.
   The gate asserted on `diag.remediation`, one layer inside the last reader.
2. The remediation instructed an action the module **refuses to perform**:
   [ADR-002](#adr-002)'s follow-up removed `opus-4-5`/`sonnet-4-5` from the minimum
   table precisely because no release-specific minimum is published, and will not
   re-add them. Users of currently-shipping models were handed an errand with no
   completion.
3. Because the guard read the per-turn property rather than the classification, the
   `hit_rate >= 80` shortcut became **permanently unreachable** for those same users:
   every run reported an incomplete diagnosis with no achievable remedy.
**Decision:** Keep the classification, delete the apparatus. `miss_unknown_model`
remains a counter value and a `_build_evidence` branch; `unknown_threshold_turns`, the
caveat and the no-primary branch are removed; the healthy-shortcut guard reads
`counters["miss_unknown_model"]`; the remediation states plainly that **no action is
available on the user's side**, because whether a minimum exists to record is a
property of the model's published documentation.
**Consequences:**
- ✅ Every surviving output has a reader and every instruction has a completion.
- ⚠️ A turn whose minimum is unknown and whose gap exceeded an *assumed* tier is
  reported as `miss_ttl`. The evidence says the tier was assumed — that accounting
  (`assumed_tier_turns`) predates this ADR and is retained; it is the honest limit of
  what the data supports.
**Rejected:** Patching the three findings separately (they are one over-built
mechanism, and rounds 1-2 had already shown that patching this surface generates new
defects faster than it closes them).
**Source:** Review round 3, code-reviewer P1 x2 + P2.

## 🏗️ Technical Design

**Current state.** `PRICE_TABLE` has 3 family keys with Opus at the pre-4.5
rate; `PRICE_TABLE_VERSION` is a label. `_THRESHOLDS` is a 3-key family map,
first-match, 1024 default; the threshold is resolved **once per window** from a
caller-supplied model string that every production caller hard-codes.
`_entry_from_turn` drops `model` and `session_id` and sums the cache-write
tiers. `_TTL_SECONDS` is 300. Fused bodies are assembled by
`workflow_fuse.fuse()` in Python. `review.md.j2` Step 3 tells Pass 1 reviewers to
read changed files end-to-end.

**Affected components.**

| Component | Change | ADR |
|---|---|---|
| `economics.PRICE_TABLE` / `_VERSION` / `:22-23` docstring | per-model keys, haiku fix, version "2", stale claim corrected | ADR-002, ADR-003 |
| `economics` report | `unattributed_breakdown` (turns **and** USD) | ADR-013 |
| `cache_diagnostics._THRESHOLDS` / `_threshold_for_model` | per-model table, longest-match, `None` on unknown | ADR-004 |
| `cache_diagnostics._entry_from_turn` + entry schema | + `model`, tiers, `session_id`; keep the sum key | ADR-012 |
| `_classify_turn` / `_build_evidence` / `_detect_ttl_regression` | per-turn threshold + TTL tier, session-aware | ADR-005, ADR-012 |
| `ai_readiness`, `improvement` | handle the widened failure-mode set | ADR-004 |
| `_partials/worktree_preflight.md.j2`, `_partials/gate0_receipt.md.j2` | **split** each existing partial into shared prose + per-stage part (no new partial files) | ADR-006, ADR-016 |
| `workflow_fuse.fuse()` | emit shared blocks once; thread suppression; **replicate the `feature_branch_workflow` gate** | ADR-006 |
| `templates/stages/*.md.j2` | suppress shared blocks when fused | ADR-006 |
| `templates/stages/review.md.j2` | bounded read + visible elision + escalation, at **all four** dispatch sites | ADR-008, ADR-011 |
| `cli.py` `--model` help | reword: per-turn fallback, not window-wide answer | ADR-012 |
| `tests/{unit,structural,render,fixtures}` | new gates + **3** goldens | ADR-010, ADR-011 |

**API changes.** `_threshold_for_model` → `int | None`. Entry dict gains four
keys. `CacheDiagnosis.failure_mode` gains one value. Report JSON gains
`unattributed_breakdown`. `diagnose_cache_from_turns(model=…)` changes meaning
from window answer to per-turn fallback. No public CLI signature changes.

## 📝 Implementation Plan

### Phase 1 — Meter correction (pricing, thresholds, TTL, per-turn entry bridge)

- `depends_on`: `[]`
- `parallel_group`: `serial-meter`
- `merge_hazards`: `economics.py` and `cache_diagnostics.py` are read by
  `ai_readiness.py` and `improvement.py`; the widened failure-mode set must land
  in the same commit as its consumers or `/hm:health` breaks. `_entry_from_turn`
  is the single bridge every classifier helper reads — no concurrent edit.
- **Scope (in):** `economics.py` (PRICE_TABLE incl. the `opus-4-5` key,
  PRICE_TABLE_VERSION, **PRICE_TABLE_EFFECTIVE_DATE** — ADR-003, the `:22-23`
  stale-invariant comment); `cache_diagnostics.py` (`_THRESHOLDS`,
  `_threshold_for_model`, `_entry_from_turn`, the entry schema, `_classify_turn`,
  `_build_evidence`, `_detect_ttl_regression`, `diagnose_cache_from_turns`);
  `ai_readiness.py` / `improvement.py` (new failure-mode value); **`cli.py:1518-1522`
  `--model` help text** — it reads "Model hint for cache diagnostics threshold
  calculation", which describes the window-wide answer ADR-012 demotes to a
  per-turn fallback, so leaving it makes the CLI's own documentation false
  (validator-3 M7); `tests/unit/test_cache_diagnostics.py`,
  `tests/unit/test_economics_pricing.py`.
- **Scope (out):** `resolve_model_family`, `estimate_attribution`, the
  `price_turn` fallback **policy** (ADR-002 R8) — its OBSERVABILITY is in scope
  ([ADR-018](#adr-018)); any template other than the ai-readiness rubric, whose
  miss-reason list named the retired classifier.
- **Exit criterion:** the two unit modules green; **AC-001/002/004 assert through
  `diagnose_cache_from_turns`, not only the resolver** — the discriminator is
  `test_mixed_model_window_resolves_two_thresholds` (a window mixing an Opus-5
  turn and an Opus-4-6 turn must produce two different thresholds, which is
  impossible if `_entry_from_turn` still drops `model`); ADR-012's boundary rules
  1 and 3 green under their named tests
  (`test_ttl_regression_not_manufactured_by_segment_split`,
  `test_evidence_renders_applied_tier_and_unknown_model`); the ADR-010 mutation
  check is recorded per AC in the commit message.
- **Risk:** `medium` (raised from `low` — the entry bridge is load-bearing for
  three helpers and its docstring documents two traps).
- **Rollback:** revert this phase's own commit.

### Phase 2 — Unattributed decomposition

- `depends_on`: `[1]`
- `parallel_group`: `serial-meter`
- `merge_hazards`: same file as Phase 1 (`economics.py`) — must follow it.
- **Scope (in):** `economics.py` report assembly + the ADR-013 predicate over
  the `by_stage["(unattributed)"]` population + the
  `unattributed_breakdown_notes` field;
  `tests/unit/test_economics_unattributed_breakdown.py`.
- **Scope (out):** the adjacency **algorithm** (reused, not modified),
  `by_agent`, the forward span ledger.
- **Exit criterion:** `unattributed_breakdown` conserves on **both** turns and
  USD; a `recoverable = 0` implementation and an all-zeros report each fail a
  **named** test; the fixture has both buckets non-zero with per-turn membership
  derived from the ADR-013 predicate, not from the implementation.
- **Risk:** `low`
- **Rollback:** revert this phase's own commit.

### Phase 3 — Reviewer read budget + verification invariance guard

- `depends_on`: `[2]`
- `parallel_group`: `serial-review`
- `merge_hazards`: `templates/stages/review.md.j2` is edited here **and**
  re-rendered differently by Phase 4; the three goldens are the seam and Phase 4
  must not regenerate them.
- **Scope (in):** `templates/stages/review.md.j2` (**all four** dispatch sites —
  Pass 1 `:175`, Pass 1.5 `:194`, Pass 2 `:216`, and the single-reviewer
  `#### Direct review` `:223` inside the `{% else %}` at `:217`);
  `tests/fixtures/review_command_pre_change.md`,
  `tests/fixtures/review_command_fused_pre_change.md` and
  `tests/fixtures/plan_command_fused_pre_change.md` (new goldens);
  `tests/render/test_render_review_read_budget.py`; **the re-rendered
  `.claude/commands/hm/` commands that contain the review stage.**
- **Scope (out):** reviewer agent definitions, `conditional_router`, consensus
  math, `second_opinion` recipes.
- **Rollback independence (validator-3 H4).** The re-render is in scope
  **deliberately**. A template edit whose shipped artifact lands in Phase 4
  instead would leave `.claude/commands/hm/*` stale between the two commits (with
  `/hm:health`'s drift signal firing), and reverting Phase 3 after Phase 4 landed
  would leave the bounded-read prose in the shipped commands while the template no
  longer contains it. ADR-009's "revert this phase's own commit" is only true when
  each phase owns its own artifacts.
- **Exit criterion:** AC-008 asserted at **each of the four** dispatch sites
  across **all three** renders (atomic, fused, single-reviewer), including the
  outside-the-diff escalation scope, with the non-emptiness conjunct green;
  AC-009's structural comparison green against both review goldens **and** its
  `validator_invocation_points` conjunct green against the plan-bearing golden
  with `>= 1` dispatches in it; removing a pass from any render fails the guard.
- **Risk:** `medium` — the only phase touching a verification surface.
- **Rollback:** revert this phase's own commit.

### Phase 4 — Fused-command compaction

- `depends_on`: `[3]`
- `parallel_group`: `serial-render`
- `merge_hazards`: touches `workflow_fuse.py` (**Python**), possibly
  `synthesize.py`, all 7 stage templates, and regenerates every rendered command
  under `.claude/commands/hm/`. Cannot run concurrently with any other template
  or fuse work.
- **Scope (in):** `src/harness_maker/workflow_fuse.py` (emit-once plumbing **plus
  the `worktree.feature_branch_workflow` gate** the hoist moves off the including
  stage — [ADR-006](#adr-006)(d); the partials **already exist**, nothing is
  extracted); the shared-prose / per-stage split inside
  `_partials/worktree_preflight.md.j2` and `_partials/gate0_receipt.md.j2`,
  including the position-correct rewrite of Gate 0's hoisted opening sentence
  ([ADR-016](#adr-016)); `synthesize.py` only if the render context changes; all 7
  `templates/stages/*.md.j2`; `tests/structural/test_command_size_budget.py`;
  re-rendered `.claude/commands/hm/*`.
- **Scope (out):** stage Step content, `atomic_command.md.j2`, all three goldens,
  and — **withdrawn from this plan entirely** — the documentation-only trim of the
  fused render ([ADR-017](#adr-017)). No `##` section is dropped from any render.
- **Command scope of the change (validator-3 H3).** The hoist applies to **every**
  fused command, not only `exec-rev-wrap-ver`. There are five, and the plan-bearing
  ones (`res-spec-plan`, `plan-exec-rev`) are the reason AC-009 needs its third
  golden. Only `exec-rev-wrap-ver` has a hand-set ceiling; the other four ratchet
  from their own `measured_post_change`.
- **Exit criterion:** AC-005/006/007 green under ADR-014's ceiling, floor and
  unit (`exec-rev-wrap-ver` ≤ 119,000 characters); **all four `--stage` values
  survive in the fused render** (`execute`/`review`/`wrapup`/`verify` for Gate 0,
  `hm:*` for preflight) — [ADR-016](#adr-016); **AC-006's flag-off arm green** (no
  preflight block in a `feature_branch_workflow: false` render, all four Gate 0
  stages still present) — [ADR-006](#adr-006)(d); AC-006's content fingerprint
  rejects a heading with an empty body; **Phase 3's AC-008/AC-009 guards still
  green on all three renders**; a deliberately inflated template fails; an empty
  render fails. Phase 4 first classifies every candidate block per
  [ADR-016](#adr-016), and checks whether `workflow_context` already discriminates
  fused from atomic.
- **Risk:** `medium-high` — largest surface, most able to silently drop an
  instruction.
- **Rollback:** revert this phase's own commit.

## 🧪 Testing Strategy

- **Unit** — `test_cache_diagnostics.py` (AC-001/002/004, asserted through
  `diagnose_cache_from_turns`), `test_economics_pricing.py` (AC-003),
  `test_economics_unattributed_breakdown.py` (AC-010, both units).
- **Structural / render** — `test_command_size_budget.py` (AC-005/006/007),
  `test_render_review_read_budget.py` (AC-008/009, per dispatch site, both
  renders).
- **Mutation check (ADR-010)** — per AC, the commit message names the code
  deletion and the test that dies.
- **Determinism** — `freeze_time` + `generated_at` masking per CLAUDE.md.
- **Manual** — after Phase 1 and again after Phase 4, run `/hm:health` and
  confirm Layer 3 produces a diagnosis with no unknown-model crash and that a
  mixed-model window no longer reports a single threshold.

## ⚠️ Risks & Mitigation

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R1 | A new gate passes in the broken world (count-3 pattern) | **high** | high | ADR-010 mutation check per AC; both models already found two instances in the draft, the validator found three more |
| R2 | Phase 4 hoisting gates the escalation clause out of the fused path | medium | high | AC-008 asserted per dispatch site in both renders (ADR-011); Phase 3's guard must stay green through Phase 4 |
| R3 | The read budget lowers recall despite the clause | medium | high | ADR-008 visible elision + outside-diff escalation scope; fallback is index-only (Interview #8) |
| R4 | Widened failure-mode set breaks `/hm:health` | medium | medium | Consumers land in the same commit; manual `/hm:health` after Phase 1 |
| R5 | Historical dollars change and read as a regression | **high** | low | ADR-003; version label changes; documented in SPEC AC-003 inline |
| R6 | AC-007's differential is meaningless because fused deliberately drops repeats | medium | medium | Compare canonical block identity + per-stage applicability, not raw multisets; AC-006 owns counts |
| R7 | Someone measures this with a cost ÷ deliverable ratio | low | high | `harness-economics-observability` ADR-002 no-ratio invariant |
| R8 | **A model released after this table is priced at the pre-4.5 fallback**, re-creating the 3× error | **high** (steady state) | medium | ADR-002 records it explicitly; `report.unknown_models` / `fallback_priced_turns` are the surfacing signals; changing fallback policy is a follow-up |
| R9 | Phase 1's entry-bridge rework breaks a classifier helper subtly | medium | high | The bridge docstring documents two known traps; AC-001/002/004 assert end-to-end through `diagnose_cache_from_turns`, not the resolver |
| R10 | **A literal "exactly once" hoist silently breaks Gate 0** — one receipt per stage is the missing-stage mechanism | was **high** before ADR-016 | **critical** | ADR-016 classifies each block first; AC-006 restated to assert all four `--stage` values are present; Phase 4 exit criterion checks them explicitly |
| R11 | **A removal is classified as inert because it looks like documentation** — the recurring failure of this plan, now at count 3 (CP block, `--stage` values, the `##` trim) | **high** — it survived two validator passes | **critical** | ADR-017 withdraws the trim; ADR-016's discipline is restated as applying to *every* removal, not the blocks currently being measured; ADR-014's ceiling is set where the surviving work lands, so it cannot pressure the executor into deleting content to meet a target |
| R12 | Hoisting emits preflight prose into flag-off harnesses, breaking the migration soak | medium | high | ADR-006(d) makes `fuse()` own the flag gate; AC-006 gains a flag-off arm asserting the block is ABSENT |

## ✅ Success Criteria

> **Execution status (wrapup 2026-07-27).** Only **Phase 1** (meter correction)
> was implemented, reviewed (3 rounds, APPROVED) and landed. **Phases 2, 3 and 4
> are NOT started.** The boxes below are ticked strictly for what is green in the
> suite today; the Phase 2-4 criteria are left `[ ]` deliberately — ticking them
> at wrapup would be exactly the "green gate ≠ correct" claim this plan's own
> review round found eleven times. Their machine-SPEC ACs (AC-005..AC-010) remain
> `pending_test: true`.

- [x] AC-001 — per-model minimums, non-monotonic, **through the production path**
      (driven by `diagnose_cache_from_turns`, plus the mixed-window discriminator)
- [x] AC-002 — unknown model never yields `miss_min_threshold`, end-to-end, with
      **all three prefix lengths pinned** so each arm rejects a named defect
- [x] AC-003 — Opus 5 at 5.0/25.0 with 0.1×/1.25×/2.0× arms; **haiku 1/5 and
      opus-4-5 arms**; version **and effective date** changed
- [x] AC-004 — 30-min gap: not `miss_ttl` at 1h, **is** `miss_ttl` at 5m, with
      tier derived from a prior **same-session** write, **and a cross-session 1h
      write does NOT suppress the miss**
- [ ] AC-005 — ADR-014 ceiling/floor/unit; `exec-rev-wrap-ver` ≤ 119,000 chars
      *(Phase 4 — not started)*
- [ ] AC-006 — shared prose once **with content fingerprint**, all four `--stage`
      values present, **flag-off render carries no preflight block**
      *(Phase 4 — not started)*
- [ ] AC-007 — no instruction lost, by canonical block identity
      *(Phase 4 — not started)*
- [ ] AC-008 — bounded + visible elision + escalation, at **all four dispatch
      sites across three renders** (incl. single-reviewer), non-emptiness
      asserted, outside-diff scope stated *(Phase 3 — not started)*
- [ ] AC-009 — verification structure identical to both review goldens; validator
      invocation points identical to the **plan-bearing** golden, which has `>= 1`
      *(Phase 3 — not started)*
- [ ] AC-010 — decomposes on the ADR-013 predicate; conserves turns **and** USD
      (1e-9 tolerance); `recoverable` strictly exceeds the adjacency count
      *(Phase 2 — not started)*
- [ ] ADR-010 mutation check recorded for every AC *(recorded for the Phase 1 ACs
      only; Phases 2-4 ACs have no tests yet)*
- [x] ADR-012 boundary rules 1 and 3 green under their named Phase 1 tests
- [x] ADR-015 — machine SPEC predicates match their ADRs before execute
- [ ] ADR-017 — no `##` section is removed from any render *(vacuously true so
      far; the obligation binds in Phase 4, which is not started)*

## 🔍 Plan Validation

**Step 4 (pre) — cross-model second opinion.** Both enabled models ran
(`status: invoked`). codex returned 13 findings, antigravity 6.

`second_opinion_results` (per-finding, per the ADR-008 output contract):

```json
[
 {"model":"codex","status":"invoked","reconciliation":[
  {"finding_ref":"P0 plan body not supplied","disposition":"rejected","reason":"Prompt-construction artifact; the validator received the full body and validated against it."},
  {"finding_ref":"P1 ADR-A gives no reproducibility","disposition":"accepted","reason":"ADR-003 reduces the clause; SPEC Constraints row amended in the same pass."},
  {"finding_ref":"P1 ADR-D does not solve AC-002","disposition":"accepted","reason":"ADR-004 returns None on unknown; ADR-012 makes it reachable in production."},
  {"finding_ref":"P1 AC-004 tier attribution undefined","disposition":"accepted","reason":"ADR-005 defines it; ADR-012 supplies the data path."},
  {"finding_ref":"P1 AC-007 not implementable by string comparison","disposition":"accepted","reason":"R6 mandates canonical block identity; AC-006 owns counts."},
  {"finding_ref":"P1 AC-009 needs a pinned fixture","disposition":"accepted","reason":"ADR-011 pins two goldens, atomic and fused."},
  {"finding_ref":"P1 escalation clause could be gated out in Phase 4","disposition":"accepted","reason":"ADR-011 asserts AC-008 per dispatch site in both renders."},
  {"finding_ref":"P1 budget too small to discover deps","disposition":"accepted","reason":"ADR-008 states escalation covers files outside the diff; residual accepted."},
  {"finding_ref":"P1 AC-010 needs classification criteria","disposition":"accepted","reason":"ADR-013 defines an observable predicate and corrects the SPEC's category framing."},
  {"finding_ref":"P2 AC-005 satisfiable at 121781; unit unspecified","disposition":"accepted","reason":"ADR-014 sets a ceiling, floor 0.8x, unit characters, command set. Ceiling later revised 110000 -> 119000 by ADR-017."},
  {"finding_ref":"P2 AC-004 has no commit owner","disposition":"accepted","reason":"ADR-009 assigns it to commit 1."},
  {"finding_ref":"P2 config may never serialize","disposition":"accepted","reason":"ADR-007 removes the config surface entirely."},
  {"finding_ref":"P2 AC-006 count-only passes on empty body","disposition":"accepted","reason":"ADR-010 adds a content fingerprint; ADR-015 propagates it to the machine SPEC."}
 ]},
 {"model":"antigravity","status":"invoked","reconciliation":[
  {"finding_ref":"P0 invisible truncation makes escalation inert","disposition":"accepted","reason":"Drove Interview #8 and ADR-008; SPEC AC-008 amended with the rationale inline."},
  {"finding_ref":"P1 haiku in-place repricing","disposition":"duplicate","reason":"Independent agreement with codex; resolved by ADR-003."},
  {"finding_ref":"P1 AC-010 sum invariant","disposition":"duplicate","reason":"ADR-010 both-non-zero fixture; ADR-013 supplies the missing predicate half."},
  {"finding_ref":"P1 AC-004 unimplementable without dynamic TTL","disposition":"duplicate","reason":"ADR-005 makes it dynamic; ADR-012 supplies the tier on the entry."},
  {"finding_ref":"P2 _DEFAULT_THRESHOLD violates AC-002","disposition":"duplicate","reason":"ADR-004."},
  {"finding_ref":"P2 AC-005 ratchet invariant","disposition":"accepted","reason":"ADR-010 floor + ADR-014 hard ceiling."}
 ]}
]
```

**Step 4 — `plan-validator`: MAJOR_REVISION → resolved.** Five criticals and
eleven warnings, all confirmed against the code before acting:

| Validator finding | Resolution |
|---|---|
| C1 — threshold is window-level; production callers hard-code the model, so the corrected table is never exercised | **ADR-012** (Interview #9 — user chose to include the entry-bridge rework in Phase 1) |
| C2 — ADR-005 unimplementable in Phase 1's scope; tiers summed away, no `session_id` | **ADR-012** + Phase 1 scope extended to the entry schema and three helpers |
| C3 — Phase 2 has no classification rule; the SPEC's exempt categories are not turn properties | **ADR-013** — observable predicate, and two of the three categories re-framed as population absences |
| C4 — AC-009 not extended to the fused render, which is the default workflow | **ADR-011** — two goldens, both asserted |
| C5 — the hoist site is `workflow_fuse.fuse()` (Python), not `workflow_command.md.j2` | **ADR-006** corrected; Phase 4 scope and merge hazards now name the Python file |
| W — AC-005 ratchet value/unit/set unset (SPEC OQ4) | **ADR-014** |
| W — SPEC Constraints row contradicts ADR-002 | **ADR-003** amends it; `economics.py:22-23` corrected in Phase 1 |
| W — machine SPEC still encodes refuted predicates | **ADR-015** |
| W — fallback stays at the pre-4.5 rate | **ADR-002** consequence + risk **R8** |
| W — Phase 3 `depends_on: []` vs its rollback target | `depends_on: [2]`; all rollbacks reworded to "revert this phase's own commit" |
| W — AC-008 under-determines per-dispatch-site coverage | **ADR-011** |
| W — AC-010 unit ambiguous (turns vs USD) | Phase 2 conserves **both** |
| W — `second_opinion_results` was prose, violating the array contract | Rewritten above as a per-finding array |
| S — `_partials/` described as new | Reworded — **and reworded wrongly**; corrected again at pass 3 (L3): the partials already exist and are *split*, not created |
| S — `workflow_context` may already discriminate | Phase 4 exit criterion checks first, adds no flag if so |

**Step 4 (second pass) — `plan-validator`: MAJOR_REVISION → resolved.** C1–C5
above confirmed closed; three **new** criticals, all introduced by the revision
that closed them:

| Validator finding | Resolution |
|---|---|
| N1 — **AC-006's "shared blocks appear exactly once" would break Gate 0.** `_partials/gate0_receipt.md.j2:33` renders `--stage {{ gate0_stage }}`; the four copies emit `execute`/`review`/`wrapup`/`verify`, and one receipt per stage IS the autoloop's missing-stage mechanism. The "4× duplication" was parameterised per-stage rendering, measured as duplication twice by the author. | **ADR-016** — classify each block first; AC-006 restated to assert all four `--stage` values are PRESENT; Communication Protocol removed from scope (40 shared chars of 349) |
| N2 — ADR-014's arithmetic was wrong: 121,782 − 9,963 = 111,819, above the 110,000 ceiling it set | **ADR-014** re-derived from measurement |
| N3 — AC-002's rewritten predicate was satisfiable by a classifier that never emits the verdict — the `assertion-invariant-over-named-dimension` failure, introduced *inside* a fix for a pass-1 finding | Paired positive arm added; strengthened again at pass 3 (H1) by pinning all three prefix lengths |

**Step 4 (third pass) — `plan-validator`: MAJOR_REVISION → resolved.** Requested
by the user after two consecutive MAJOR_REVISIONs, on the grounds that the
second-pass revision — including ADR-016, the AC-006 restatement and the ADR-014
re-derivation — had been reviewed by nobody but the author. Five criticals, four
highs, nine mediums, five lows. **The verdict's framing:** the pass-2 fix
(ADR-016) established a discipline and was then applied only to the blocks it
measured; the same error survived untouched in the larger removal.

| Validator finding | Resolution |
|---|---|
| C1 — the "documentation-only" trim deletes `## When to Run`, which in the **fused** render carries the fused-only override "always run — do not skip", the sole defence against the documented `loop-body-skipping-review-stage` failure this plan cites as prior work. Also in the trim: Phase D's partial-test hint, verify's Check 3/4 input paths, the `--force` confirmation gate, four `## Quality Bar` exit invariants, and four `@hm:user:` preservation-block anchors | **ADR-017** — trim withdrawn entirely. Independently confirmed against `exec-rev-wrap-ver.md:534` and `:1228` before acting |
| C2 — the trim (60% of the claimed saving) is guarded by nothing; ADR-014's AC-007 compatibility argument *was* AC-007's blindness, AC-005's floor derives from the post-change artifact, AC-009 sees only the review render | **ADR-017**; AC-005's ceiling re-derived from the hoist alone (119,000) so no target pressures the executor into deleting content |
| C3 — AC-008 is `all()` over a possibly-empty set; `reviewer_read_sites()` was named but never defined; discovery ran only over multi-reviewer renders, so ADR-011's claim to guard the fourth site (`review.md.j2:223`, inside the `{% else %}` at `:217`) was **false** | **ADR-011** rewritten: discovery defined against a pre-change anchor, non-emptiness conjuncts added, a **single-reviewer render** added as a third input, Pass 1.5 asserted rather than exempted (four sites, not three) |
| C4 — AC-010 is invariant over the entire novel half of ADR-013: `recoverable = {est is not None}` passes all four conjuncts while ignoring `preceded_by_user`. The same shape as N3, without the paired arm | Positive arm added: `recoverable.turns > turns_by_attribution_source["adjacency"]` |
| C5 — hoisting moves the `feature_branch_workflow` gate, which `_partials/worktree_preflight.md.j2:2-7` assigns to the including stage; `fuse()` reads nothing from `config_dump`. A naive preamble emits preflight prose into flag-off harnesses | **ADR-006(d)** — `fuse()` owns the gate; AC-006 gains a flag-off arm asserting the block is ABSENT; risk **R12** |
| H1 — AC-001 is resolver-only (`executable_predicate: null`), violating ADR-010; AC-002's arms were invariant over the defect they targeted | AC-001 bound to `diagnose_cache_from_turns` + a mixed-window discriminator test; AC-002's three prefix lengths pinned to opposite-signed arms |
| H2 — ADR-012's boundary rules 1 and 3 reach no predicate; AC-004 passes a session-blind implementation | AC-004 arm 3 (`prior_write_in_other_session`); rules 1 and 3 bound to named Phase 1 tests, with the asymmetry recorded as a decision |
| H3 — AC-009's `validator_invocation_points` is `∅ == ∅` on two review goldens while Phase 4 re-renders the plan-bearing fused commands that hold the dispatch | Third golden (`plan_command_fused_pre_change.md`) + a `>= 1` non-vacuity conjunct; Phase 4's command scope stated |
| H4 — Phase 3's rollback is not independent: it edits a template but leaves the re-render to Phase 4 | Phase 3's scope now includes its own re-render, with the rationale recorded |
| M1 — ADR-014 still counted Communication Protocol's 120 chars that ADR-016 removed | Hoistable corrected 5,826 → **5,706** |
| M2 — ADR-016's `chars/copy` for Gate 0 was inflated ~30% and implied four equal copies | Table corrected to the measured 1,300 / 1,700 / 1,500 / 1,380; the load-bearing 659 verified unchanged |
| M3 — Gate 0's shared prose is positionally bound ("You have completed the stage") and 3-way variant | Stated as a Phase 4 obligation in ADR-016 — AC-006's fingerprint cannot see it, so it is not claimed as gated |
| M4 — AC-010 compared floats with `==` | 1e-9 tolerance |
| M5 — `PRICE_TABLE_EFFECTIVE_DATE` is a second provenance signal the plan never touched | ADR-003 + Phase 1 scope + an AC-003 arm |
| M6 — AC-008's pinned negative string appears nowhere in the source (wrong verb form, line-wrapped), so the arm always passed | Pin corrected and declared whitespace-normalized |
| M7 — `cli.py --model` help text becomes false under ADR-012 | Added to Phase 1 scope |
| M8 — AC-006's `fingerprint == 1` has no size anchor | Accepted; backstopped by AC-005's ceiling, which no longer depends on the withdrawn trim |
| M9 — Phase 3's exit criterion still enumerated "Pass 1 / 1.5 / 2", the enumeration ADR-011 replaced | Exit criterion rewritten to the four discovered sites across three renders |
| L1 — no `opus-4-5` key, so that model sits on the wrong side of ADR-002's own "pre-4.5" boundary | Key added (pricing only — no cache-minimum golden row, as no published minimum is known) |
| L2 — the haiku 1/5 correction was asserted by nothing | AC-003 arm added |
| L3 — ADR-006, its consequence, and the components table gave three different scopes for the partials | Components table corrected to "split, no new files" |
| L4 — SPEC AC-003's family-fallback clause and ADR-013's `unattributed_breakdown_notes` appear in no predicate | Accepted as documented, ungated; both are report content, not verdicts |
| L5 — verify's `## Output` was not in the trim list but matched a naive selector | Moot — **ADR-017** removes no `##` section at all |

**Clean at pass 3** (verified, not asserted): ADR-016's core finding and AC-006's
restatement bite; Communication Protocol's "not hoistable" classification is
accurate at 40/349; pass-1 C1/C2/C5 are genuinely closed at the code level;
ADR-013's field list matches `TurnRecord` and its population choice is correct;
the phase decomposition's serial chain is right for the shared-file hazards.
