---
type: plan
task_slug: harness-diet
status: phase-1-complete  # NOT `complete` — see "Why this is not `status: complete`" below
created: 2026-08-05
tags: [harness-maker, plan, python, context-economics, prompt-surface, memory-tiers, autonomy]
research_doc: "[[RESEARCH-harness-diet]]"
interview_rounds: 6
adrs: 16
validator_outcome: MAJOR_REVISION_RESOLVED
summary: "Delete the fused-workflow axis, archive stale failures at write time, make autopilot the default"
---

# PLAN — harness-maker diet

## 🎯 Executive Summary

**TL;DR** — Delete the fused workflow commands and the entire `workflows` config axis
(−530,222 chars, **−45.2%** of shipped prompt surface), rewire `/hm:loop` so it survives
that deletion, make autopilot the shipped default so the removed capability has a live
replacement, and add a write-time archive pass so `failures.md` stops growing
monotonically.

**What.** Four independent cuts plus one enabling change:

1. Remove the fused commands on every target, and the `workflows` / `default_workflow`
   schema axis and `workflow_fuse` engine behind them. The schema **defines seven**
   names (`exec-rev`, `exec-rev-wrap`, `exec-rev-ver-wrap`, `exec-rev-wrap-ver`,
   `plan-exec-rev`, `plan-exec-rev-wrap`, `res-spec-plan` — `interview.py:71-136`); this
   repo currently renders **five** of them. Five is the measured byte figure; seven is
   the deletion scope.
2. Rewire `/hm:loop` to call `/hm:execute` then `/hm:review` directly, since its
   per-iteration unit is today a fused command (ADR-014).
3. Promote `autonomy.level` to `auto_safe` and `autopilot_persistent` to `true` as
   shipped defaults — the replacement for what §1 deletes.
4. Give every rendered `/hm:` command a real frontmatter `description:`.
5. Archive `failures.md` entries that are `count:1` **and** older than 90 days, at
   write time inside `upsert-failure`.

**Why.** Measured, not inferred: the fused commands are 58.6% of the Claude command
surface and have **zero** invocations across the full economics history, while
autopilot has already performed 40 stage advances. `failures.md` is 156 entries /
266KB with **no eviction mechanism in code**, 87% never-recurred, and its retrieval
returned 1/6 relevant hits on this task's own topic. Full evidence:
[[RESEARCH-harness-diet]].

**Key decisions.** Delete the axis outright, not just its defaults (ADR-002);
archive at write time so the feature cannot be forgotten (ADR-006); **keep
`/hm:verify`** — reading the template reversed the research's own classification
(ADR-003); leave the review apparatus alone (ADR-004).

**Estimated impact.** Shipped surface 1,173,667 → ~643,000 chars. `failures.md`
156 → ~95 entries. On Claude Code, `/hm:loop` keeps working through ADR-014's rewiring —
**without that rewiring it would be silently decommissioned**, so it is a scope item, not
an out-of-scope neighbour. Cursor and Codex lose pre-fused multi-stage chaining
(accepted, ADR-001).

## 📚 Prior Work

- [[RESEARCH-harness-diet]] — the measurement this plan acts on. **Unit correction:**
  research reported `wc -c` bytes; the committed baseline and this plan use
  **characters** (`len(read_text())`). Multi-byte content makes them disagree, and
  chars is what a model's context sees.
- [[PLAN-workflow-step-audit]] / [[BASELINE-workflow-step-audit]] — produced the
  fused-preamble hoist (2026-07-27) and `test_command_size_budget.py`'s AC-005/006/007.
  **This plan deletes what AC-006 and AC-007 exist to protect.** Those criteria must be
  removed with the feature, not "fixed".
- [[PLAN-token-economy-step-pruning]] / [[PLAN-workflow-overhead-post024]] — prior
  overhead passes; check for already-removed steps before re-proposing.
- [[PLAN-second-brain-promotion]] ADR-005 — the precedent this plan's ADR-006 avoids:
  a feature wired only into `/hm:wrapup` fires only as often as wrapup runs.
- Global CLAUDE.md, 2026-06-08 learned correction — "absent-case = feature black hole";
  any feature gated on an optional field must define the absent case. Applies to the
  archive threshold and to the autonomy default flip.
- `[wiki:architecture] cursor-reads-the-claude-command-render` — Cursor reads
  `.claude/commands/hm/*.md`; a target gate must be written `"cursor" not in targets`.

## 🎙️ Interview Transcript

| # | Round | Topic | Category | Question | Choice | Note | → ADR |
|---|---|---|---|---|---|---|---|
| 1 | 1 | Fused workflow disposition | Scope | Delete all / keep 1 / conditional-render / port autopilot | **Delete all 5, every target** | Cursor+Codex lose multi-stage chaining; accepted | ADR-001 |
| 2 | 1 | Memory eviction shape | Architecture | Recurrence-archive / age-archive / retrieval-only / both | **Recurrence-based archive** | `count>=2` permanently exempt | ADR-005 |
| 3 | 1 | Review apparatus in scope? | Scope | Out / second_opinion only / verify only / all | **verify only** (superseded in R2) | Reversed by new evidence | ADR-004 |
| 4 | 1 | Success metric | Risk | Shipped chars / carry share / usd-per-task / chars+no-regression | **Shipped prompt chars** | Existing `surface_baseline.json` reused | ADR-008 |
| 5 | 2 | verify re-adjudication | Architecture | Keep / drop skill only / drop all / dedupe only | **Keep — out of scope** | 5 of 6 checks are machine gates; reverses #3 | ADR-003 |
| 6 | 2 | `workflows` axis fate | Contract | Remove axis / keep key w/ 0 defaults / deprecate | **Remove the axis entirely** | Engine + schema + presets all go | ADR-002 |
| 7 | 2 | Archive threshold | Risk | 90d / 60d / 180d / age-agnostic | **90 days** | ~60 entries archived; last 3 months fully retained | ADR-005 |
| 8 | 2 | `wiki.md` treatment | Scope | Add `count` / age-only / out of scope / end | **Out of scope** | No `count` field; different loss profile | ADR-007 |
| 9 | 3 | Archive firing point | Architecture | write-time / wrapup step / prune_stale / manual CLI | **Write time, inside `upsert-failure`** | Growth point == eviction point | ADR-006 |
| 10 | 3 | Removal comms | Risk | CHANGELOG+help / stub commands / silent | **CHANGELOG BREAKING + `/hm:help`** | No stubs | ADR-009 |
| 11 | 4 | Autonomy promotion scope | Contract | Code default + both presets / Production only / presets only / this repo only | **Code default + both presets** | New harnesses auto-arm | ADR-010 |
| 12 | 4 | Runaway caps under auto-arm | Risk | Restore 20/300 / 50/600 / keep null / defer | **Restore 20/300 in this repo** | Backstop for auto-arm | ADR-011 |
| 13 | 5 | `_parse_autonomy` fallback under a flipped default | Failure handling | Explicit gated fallback / absent gets new default / revert to presets-only | **Pin the fallback to explicit `gated`** | Raised by the codex second opinion; keeps Interview #11 intact | ADR-013 |
| 14 | 6 | `/hm:loop`'s per-iteration unit after fusion is deleted | Architecture | loop calls execute→review directly / delegate to autopilot / retire loop / keep `exec-rev` | **loop calls `/hm:execute` then `/hm:review` directly** | Raised by plan-validator; neither second-opinion model caught it | ADR-014 |

Assumptions taken without asking (gate-filtered as low-EIG or common-ground):
archive directory is `.claude/memory/archive/`; `memory_md.py` owns the archive pass; the
`harness.yaml` schema_version bump follows the documented `answers_from_harness_yaml`
silent-migration pattern.

Two earlier assumptions were **withdrawn** after `plan-validator` challenged them:
"adding `description:` frontmatter is an unambiguous improvement" became ADR-016 (it is a
contract change on three parsers), and "the aggregate ratchet extends AC-005" was simply
wrong — `test_aggregate_shipped_surface_does_not_grow` already exists at
`test_command_size_budget.py:367`, so Phase 6 retunes it rather than adding it.

## 📐 Architecture Decision Records

### ADR-001: Delete every fused workflow command on every target
**Status:** Accepted (2026-08-05, via /hm:plan interview)
**Context:** The 5 fused commands are 499,797 chars of the Claude surface (58.6%) plus
30,425 chars of Codex stage skills, and have zero recorded invocations across the full
`harness_maker.economics` history, while `.claude/observability/auto-advance.jsonl`
records 40 autopilot advances.
**Decision:** Delete every fused name from every target — no conditional render, no
survivor. The schema defines **seven** (`interview.py:71-136`); this repo renders five,
which is where the byte figure comes from.
**Consequences:**
- ✅ −530,222 chars (−45.2%) of shipped prompt surface in one change.
- ✅ Removes 5 re-concatenated copies from the per-stage-edit maintenance path.
- ⚠️ **`/hm:loop` breaks without ADR-014.** `loop.md.j2` states "Each iter invokes one
  fused workflow command", defaults to `exec-rev`, halts when
  `.claude/commands/hm/<WORKFLOW>.md` is missing ("Do NOT silently fall back"), and
  interpolates `{{ config.default_workflow }}` and `{{ config.workflows.keys() }}`. An
  earlier draft of this ADR claimed no Claude Code capability was lost; that was false.
- ⚠️ Cursor and Codex lose their only multi-stage mechanism: autopilot's auto-advance
  block needs the `Skill` tool (absent in Cursor) and is not rendered into
  `.agents/skills/hm-*/SKILL.md` at all (verified: 0 occurrences).
- ⚠️ Evidence is n=1 — this repo's maintainer works in Claude Code. Absence of Cursor
  telemetry is not evidence of absence of Cursor users.
**Rejected alternatives:**
- Keep `exec-rev-wrap` only — leaves the fuse engine and its tests alive to serve one
  never-invoked command.
- Conditional render on `targets` — this repo lists all three targets, so it would
  reduce nothing here while keeping the full engine.
- Port autopilot to Cursor/Codex first — inverts the diet's direction; new hook and
  marker paths across two IDEs.
**Source:** Interview #1

### ADR-002: Remove the `workflows` configuration axis entirely
**Status:** Accepted (2026-08-05, via /hm:plan interview)
**Context:** With no fused commands shipped, `harness.yaml.workflows`,
`default_workflow`, `workflow_fuse.py`, `RESERVED_WORKFLOW_NAMES`, `STAGE_ABBREV`, the
per-preset workflow tables in `interview.py`, and the `{% if workflow_context %}`
conditionals in all seven stage templates become a code path nobody exercises.
**Decision:** Delete the axis — schema fields, fuse engine, validators, preset tables,
rubric, and template conditionals.
**Consequences:**
- ✅ Maintenance surface shrinks in code, not only in rendered output; dead code with
  passing tests is exactly what this task removes elsewhere.
- ⚠️ User-defined fused workflows cease to be a feature.
- ⚠️ Existing `harness.yaml` files carry `workflows:` and `default_workflow:`;
  `extra="forbid"` on the config models means they must be dropped by migration, not
  ignored.
**Rejected alternatives:**
- Keep key with zero shipped defaults — preserves an unexercised engine plus its tests.
- Keep + deprecation warning — a grace period for a feature with no observed users.
**Source:** Interview #6

### ADR-003: `/hm:verify` stays — it is state scaffolding, not behavior scaffolding
**Status:** Accepted (2026-08-05, via /hm:plan interview) — **reverses Interview #3**
**Context:** RESEARCH-harness-diet nominated `/hm:verify` for removal on its cost
($11, 0.4%) and on Anthropic's Opus 5 guidance to remove "legacy harness scaffolding
that adds separate verification steps". Reading `verify.md.j2` shows 5 of its 6 checks
are deterministic machine gates — regression smoke, structural delta from
`dashboard.md`, security findings from `findings-*.jsonl`, worktree merge cleanliness,
SPEC requirement — not a request that the model re-check its own reasoning. It is also
in `DELEGATABLE_STAGES` (already carry-optimised via `stage-delegate`) and shows 19
events in the autopilot ledger.
**Decision:** Keep `/hm:verify` and `verify-before-completion`. Out of scope.
**Consequences:**
- ✅ The plan's own state/behavior criterion is applied consistently rather than by
  cost ranking.
- ✅ Avoids touching `AtomicStage.VERIFY`, wired into 12 consumers.
- ⚠️ The task's total reduction is smaller by ~21,257 chars.
**Rejected alternatives:**
- Retire the whole stage — the original Interview #3 answer, withdrawn on this evidence.
- Drop the skill only — deferred; the skill/command overlap is real but small.
- Dedupe Check 2 against review's targeted tests — analysis likely costs more than it saves.
**Source:** Interview #5

### ADR-004: The review apparatus is out of scope
**Status:** Accepted (2026-08-05, via /hm:plan interview)
**Context:** `hm:review` is the largest reducible cost ($658, 22.4%, VERIFY:PRODUCE
4.4:1), but its k-of-2 consensus, PIDA acceptance gate, and auto-fix monotonic lattice
are interlocked; CLAUDE.md records a P0 that fired when one piece was changed alone.
**Decision:** Reviewers, consensus mode, and `second_opinion` are untouched here.
**Consequences:**
- ✅ A regression after this task is attributable to surface deletion, not to review
  semantics.
- ⚠️ The single largest cost centre is deferred to a separate PLAN.
**Rejected alternatives:**
- Include `second_opinion` mandatory→opt-in — the largest single saving, but a
  cross-model voter caught a P0 two Claude reviewers missed (fleet C3).
**Source:** Inference from RESEARCH-harness-diet's risk analysis, not an interview round.
Interview #3's recorded choice ("verify only") is what ADR-003 reverses; no round
produced this scope exclusion directly.

### ADR-005: Archive `failures.md` entries by recurrence, 90-day threshold
**Status:** Accepted (2026-08-05, via /hm:plan interview)
**Context:** 156 entries / 266KB, 87% at `count:1`, 8 entries carrying all recurrence
signal, no eviction mechanism in code. Age alone is the wrong predicate — the entries
encode system invariants, not model-capability workarounds.
**Decision:** Move an entry to `.claude/memory/archive/failures-<YYYY>.md` when it is
`count:1` **and** its date is older than 90 days. `count>=2` is permanently exempt at
any age. Archive, never delete.
**Consequences:**
- ✅ ~60 entries archived; retrieval corpus 368 → ~307; the last three months stay whole.
- ✅ Reversible — the archive file is committed alongside.
- ⚠️ A `count:1` entry archived today can become a repeat tomorrow; recall degrades for
  the tail.
- ⚠️ `wiki.md` is untouched (ADR-007), so retrieval noise is only partly addressed.
**Rejected alternatives:**
- 60 days — reaches entries that have not yet had a chance to recur.
- 180 days — archives ~0 entries today; installs a mechanism that does nothing now.
- Age-agnostic `count:1` — would archive last week's failure before the next session
  can benefit from it.
**Source:** Interview #2, #7

### ADR-006: The archive pass fires at write time inside `upsert-failure`
**Status:** Accepted (2026-08-05, via /hm:plan interview)
**Context:** `memory_md` is called from exactly one place — `wrapup.md.j2`. A wrapup-step
archive would inherit PLAN-second-brain-promotion ADR-005's documented limitation: the
feature fires only as often as wrapup runs.
**Decision:** `upsert-failure` runs a bounded archive pass immediately after its write,
in the same atomic-write path.
**Consequences:**
- ✅ Growth point and eviction point are the same call — the pass cannot be forgotten
  or skipped by a manual-commit workflow.
- ✅ No new template step, no new user-visible command in the hot path.
- ⚠️ `upsert-failure` gains a side effect beyond its name; it must stay atomic and must
  never fail the write when archiving fails.
- ⚠️ A project that stops recording failures also stops archiving — acceptable, since
  it is also not growing.
**Rejected alternatives:**
- New wrapup step — inherits the known under-firing limitation.
- `worktree create` / `prune_stale` — reliable but low cohesion with memory.
- Manual CLI + `/hm:health` warning — accumulates until someone acts.
**Source:** Interview #9

### ADR-007: `wiki.md` is out of scope
**Status:** Accepted (2026-08-05, via /hm:plan interview)
**Context:** `wiki.md` (212 entries, 297KB, 81% pre-July) has no `count:` field, so the
recurrence predicate of ADR-005 cannot be evaluated against it without a schema change
plus a backfill.
**Decision:** Leave `wiki.md` untouched. Archive `failures.md` only.
**Consequences:**
- ✅ No schema migration on the tier holding architecture decisions.
- ⚠️ Retrieval corpus drops only 368 → ~307; the observed 1/6 relevance is only partly
  improved.
**Rejected alternatives:**
- Add `count:` + backfill — a schema change on the higher-loss-cost tier, in the same
  task as a 45% surface deletion.
- Age-only archive for wiki — the predicate this plan rejects for failures.
**Source:** Interview #8

### ADR-008: Success is measured in shipped-surface characters via the existing baseline
**Status:** Accepted (2026-08-05, via /hm:plan interview)
**Context:** `tests/structural/surface_baseline.json` already records
`aggregate_chars: {claude: 853424, codex: 320243}`, and `test_command_size_budget.py`
AC-005 already ratchets each command with both a ceiling and a floor.
**Decision:** The metric is `aggregate_chars`. Extend the existing ratchet to the
aggregate; do not build new measurement.
**Consequences:**
- ✅ Deterministic, CI-gateable, already committed.
- ✅ AC-005's **floor** protects against meeting the target by gutting surviving renders.
- ⚠️ Characters are a proxy for context cost, not a measure of it — token counts differ.
**Rejected alternatives:**
- `slash-command-body` share (15.1%) — post-hoc; requires running sessions to evaluate.
- `total_usd` per task — dominated by task difficulty.
**Source:** Interview #4

### ADR-009: Removal is communicated by CHANGELOG BREAKING plus `/hm:help`; no stubs
**Status:** Accepted (2026-08-05, via /hm:plan interview)
**Context:** `reconcile.sweep_orphans()` already deletes blueprint-orphaned files that
fingerprint as ours and keeps + warns the rest, logging to
`.claude/observability/orphans-<date>.jsonl`. Propagation needs no new mechanism.
**Decision:** Mark BREAKING in CHANGELOG, update `/hm:help` to point at autopilot. Ship
no stub commands.
**Consequences:**
- ✅ Zero new rendered artifacts.
- ⚠️ A user who modified a fused command keeps a stale, still-functional file (it is
  self-contained prose) with only a warn — documented as an accepted limitation.
**Rejected alternatives:**
- One-release stubs — recreates five artifacts to announce their own deletion.
- Silent removal — a public plugin losing commands with no note.
**Source:** Interview #10

### ADR-010: Promote autonomy defaults to `auto_safe` + `autopilot_persistent: true`
**Status:** Accepted (2026-08-05, via /hm:plan interview)
**Context:** ADR-001's justification for deleting the fused commands is that autopilot
replaces them — but `AutonomyConfig.level` defaults to `"gated"` and
`autopilot_persistent` to `false` in code and in both preset templates, so a new
harness ships with the replacement off. `full` behaves identically to `auto_safe`, so
`auto_safe` is the maximum meaningful level.
**Decision:** `AutonomyConfig.level` default → `"auto_safe"`, `autopilot_persistent`
default → `true`, and the same values in the Production and Side preset fallbacks.
**Consequences:**
- ✅ The capability ADR-001 removes has a live default replacement.
- ✅ Mandatory gates are unaffected — the plan architecture interview, a review
  CHANGES_REQUESTED grade gate, and the wrapup merge/push stop at every level.
- ⚠️ Every new session in every downstream harness auto-arms without being asked. This
  is a behavioral change in a public plugin and belongs in the CHANGELOG BREAKING entry
  alongside ADR-009's.
- ⚠️ An old `harness.yaml` **with** an `autonomy` key keeps its stored `gated`; only new
  renders and key-absent harnesses pick up the new default.
**Rejected alternatives:**
- Production only — Side's solo/fast profile benefits at least as much.
- Presets only, code default stays `gated` — leaves the absent-key case on the old
  behavior, the exact absent-case black hole CLAUDE.md warns about.
- This repo only — leaves ADR-001 without a shipped replacement downstream.
**Source:** Interview #11

### ADR-011: Restore this repo's runaway caps to 20 / 300
**Status:** Accepted (2026-08-05, via /hm:plan interview)
**Context:** This repo's `harness.yaml` has `step_cap: null` and `time_cap_min: null`
while both presets default to 20 / 300. Auto-arming by default (ADR-010) with caps off
removes the only bound on a chained session.
**Decision:** Set `step_cap: 20`, `time_cap_min: 300` in `.claude/harness.yaml`.
**Consequences:**
- ✅ `autopilot_caps boundary` already enforces both — zero new code.
- ⚠️ A long legitimate chain will now halt at the cap and need re-arming.
**Rejected alternatives:**
- 50 / 600 — looser, but the preset value is the tested default.
- Keep `null` — pairs auto-arm with no backstop.
**Source:** Interview #12

### ADR-012: The retired-key drop ships atomically with the schema removal
**Status:** Accepted (2026-08-05, via cross-model second opinion — codex + antigravity, both P0)
**Context:** The original plan sequenced migration (P2) *after* schema removal (P1). Both
second-opinion models independently found this unshippable. `HarnessConfig` is
`extra="forbid"`, and `render._preserve_yaml_user_keys` treats a top-level key absent
from the new template as a user addition and re-appends it. So after P1 alone, an
existing `harness.yaml` carrying `workflows:` is re-injected on the next render and
raises `ValidationError` on the load after that — with the migration that would have
fixed it sitting in a later phase.
**Decision:** The retired-key handling ships in the same phase and the same commit as the
schema removal: an explicit `_RETIRED_TOP_LEVEL_KEYS = {"workflows", "default_workflow"}`
drop-list consulted by `_preserve_yaml_user_keys` (so preservation never resurrects them)
**and** a raw-YAML pre-strip ahead of Pydantic instantiation (so validation never sees
them). There is no intermediate commit at which the schema and the key handling disagree.
**Consequences:**
- ✅ Every phase boundary is independently shippable.
- ✅ The drop-list is a named, testable constant rather than an implicit absence.
- ✅ **Precedent exists in-repo**: `interview.py:1451-1456` already drops the retired
  `guard_when` key before `model_validate`, with a comment giving this exact rationale.
  ADR-012 lifts that pattern to the top level rather than inventing one — the executor
  should read those lines first.
- ⚠️ `_preserve_yaml_user_keys` gains the retired-key concept at the top level; it must
  be documented as the mechanism for every future key removal, not a one-off.
**Rejected alternatives:**
- Run migration before schema removal — leaves a commit where the model still accepts a
  key the migration has already dropped.
- Rely on `answers_from_harness_yaml` alone — it is the `make --update` reverse-map path
  and does not run when an already-installed project loads its config (codex P1).
**Source:** Cross-model second opinion, plan stage

### ADR-013: The malformed/absent autonomy fallback is pinned to explicit `gated`
**Status:** Accepted (2026-08-05, via /hm:plan interview + codex second opinion)
**Context:** `interview._parse_autonomy` returns a bare `AutonomyConfig()` for a missing
**or malformed** block — its docstring states this is deliberate ("absent-case = gated"),
so a hand-edited or old `harness.yaml` never breaks the load. ADR-010 flips that class
default to `auto_safe` / `True`, which silently converts the safety fallback into an
auto-arm path: a single typo or bad enum in the autonomy block would enable persistent
autopilot the user never requested.
**Decision:** Keep ADR-010's class-default flip, and make `_parse_autonomy`'s
missing/malformed branch construct `AutonomyConfig(level="gated",
autopilot_persistent=False)` explicitly rather than relying on the class default. New
harnesses auto-arm through the preset templates; error paths stay gated.
**Consequences:**
- ✅ Interview #11 is preserved — new harnesses still auto-arm by default.
- ✅ A config error can never escalate autonomy.
- ⚠️ An old `harness.yaml` with no `autonomy` block stays `gated` until re-rendered, so
  ADR-010 reaches existing users only through `/harness-maker:make --update`. The
  success criteria and the CHANGELOG must say this rather than implying a silent upgrade.
- ⚠️ The class default and the fallback now differ; both need a test asserting the
  divergence is intentional, or a future refactor will "simplify" it back.
- ⚠️ **The pin extends to the interview's decline branch** (`interview.py:718-720`), not
  only to `_parse_autonomy`. A user who answers "no" to "Enable autopilot auto-advance?"
  must get `gated` / `False`; leaving that `return AutonomyConfig()` bare would invert an
  explicit refusal, which is worse than the malformed-config case this ADR started from.
- ⚠️ An **empty but present** `autonomy: {}` block is *not* covered: `{}` is a dict, so it
  validates cleanly and receives the new class defaults. That is accepted rather than
  special-cased — inventing a predicate for "empty or partial block" would silently extend
  to blocks like `{step_cap: 20}`, a semantic no round decided.
**Rejected alternatives:**
- Let the absent case inherit the new default — more consistent with the absent-case
  black-hole rule, but it auto-arms existing users on a package upgrade alone.
- Revert to presets-only promotion — rejected in Interview #11 and would leave the
  key-absent case on the old behavior.
**Source:** Interview #13

### ADR-014: `/hm:loop` calls `/hm:execute` then `/hm:review` directly
**Status:** Accepted (2026-08-05, via /hm:plan interview — raised by `plan-validator`)
**Context:** `/hm:loop` (53,519 chars, the harness's only long-horizon driver) is
structurally coupled to the feature ADR-001 deletes. `loop.md.j2` says "Each iter invokes
one fused workflow command", defaults `WORKFLOW` to `exec-rev`, validates
`.claude/commands/hm/<WORKFLOW>.md` exists and **halts** when it does not ("Do NOT
silently fall back to a different workflow"), and interpolates both
`{{ config.default_workflow }}` and `{{ config.workflows.keys() }}`. After ADR-001/002 the
template would fail to render, and if it rendered, every loop would halt before iteration 1.
Neither second-opinion model reported this; `plan-validator` did.
**Decision:** Rewrite the per-iter section so the loop prompt itself sequences
`/hm:execute` → `/hm:review` for each iteration. Redefine `--per-iter-workflow` as an
explicit **stage list** (e.g. `plan,execute,review`) rather than a fused command name.
Remove the workflow-file existence check and its halt path — there is no file to find.
**Consequences:**
- ✅ `/hm:loop` survives the diet with unchanged iteration semantics.
- ✅ The iteration unit becomes data (a stage list) instead of a rendered artifact, which
  is why no fused command needs to survive for it.
- ⚠️ `loop.md.j2` and `autoloop_driver.py:480`'s `workflow` parameter move into Phase 1
  scope; Phase 1 grows.
- ⚠️ Loop-close's deferred-wrapup contract assumes an iter never runs wrapup. The new
  stage-list flag must reject `wrapup` explicitly, or the loop will commit per iteration.
**Rejected alternatives:**
- Delegate per-iter advance to autopilot — two autonomous drivers (loop convergence vs
  autopilot caps) would interact in ways neither was designed for.
- Retire `/hm:loop` too — a larger cut (−49.6%) that orphans `autoloop_driver`,
  `iter_receipts`, the loop-marker session scoping, and part of the 5-layer defense.
- Keep `exec-rev` as a loop-only survivor — partially reverses ADR-001 and blocks ADR-002
  entirely, since the fuse engine would still be needed.
**Source:** Interview #14

### ADR-015: The archive directory is classified as a deliverable, like `failures.md`
**Status:** Accepted (2026-08-05, via `plan-validator` — warning)
**Context:** `worktree.py`'s `_HARNESS_CHURN_DIRS` covers only
`.claude/memory/{semantic,episodic,profile}/`, and its `_classify` deliverable branch
names exactly `.claude/memory/wiki.md`, `.claude/memory/failures.md`, and
`.claude/memory/session/`. A new `.claude/memory/archive/failures-<YYYY>.md` is therefore
neither churn (not gitignored, not forgiven by `_is_create_guard_harness_artifact`) nor
deliverable (not forgiven by the create-guard deliverable exemption) — it lands as user
dirt that trips the Layer 2 dirty-base guard and blocks `worktree create`. That is the
PLAN-worktree-deliverable-blocks-create failure this repo already paid to fix.
**Decision:** Extend `_classify`'s deliverable branch and
`_is_create_guard_harness_artifact` to `.claude/memory/archive/`, matching how
`failures.md` itself is treated.
**Consequences:**
- ✅ An uncommitted archive file never blocks `worktree create`.
- ✅ Consistent with ADR-005's "archive, never delete, committed alongside".
- ⚠️ One more path in a classifier whose narrowness is a documented safety invariant; the
  addition must be a full-match on the directory prefix, not a substring test.
**Rejected alternatives:**
- Add it to the churn set — churn is gitignored, which would silently stop the archive
  from ever being committed, contradicting ADR-005.
- Leave it undecided — the window between the wrapup that writes and the wrapup that
  commits is intermittent, which makes the resulting block hard to reproduce, not rare.
**Source:** plan-validator, plan stage

### ADR-016: Rendered commands carry a frontmatter `description:`
**Status:** Accepted (2026-08-05, via `plan-validator` — warning)
**Context:** No rendered `/hm:` command has a frontmatter `description:`, so each falls
back to its first body line; 14 commands present the identical string in the tool
listing. This was originally taken as a gate-filtered assumption, but it is a shipped
contract change on a triple-marketplace plugin, and CLAUDE.md §2 warns that each
consumer's parser accepts a different field set.
**Decision:** Emit a `description:` in the command frontmatter. **The per-target parser
question is answered before the field ships**, not assumed: confirm the Codex TOML path
in `synthesize` and `_render_cursor_mdc` either carry the field through or are correctly
excluded. The requirement is **non-empty**; uniqueness is checked as an advisory warning,
not a hard gate — no interview round justified a uniqueness constraint.
**Consequences:**
- ✅ Commands become distinguishable in the tool listing at ~2KB total cost.
- ⚠️ If a target's parser strict-rejects unknown frontmatter keys, this must become
  target-conditional — resolved by the pre-ship check, not by assumption.
**Rejected alternatives:**
- Ship it as an unrecorded assumption — the original plan's approach; it skipped the
  per-target parser analysis every other rendered-file decision in this repo receives.
- Hard-gate uniqueness — unjustified by any decision, and it would fail the build for a
  cosmetic collision.
**Source:** plan-validator, plan stage

## 🏗️ Technical Design

### Current state

| Concern | Where it lives |
|---|---|
| Fused render | `workflow_fuse.py`, `synthesize.py:710`, `render.py` blueprint |
| Workflow axis schema | `models.py` (`workflows`, `default_workflow`, `STAGE_ABBREV`), `validators.py:20` (`RESERVED_WORKFLOW_NAMES`) |
| Preset workflow tables | `interview.py:71-136` (`_SIDE_DEFAULT`, `_PRODUCTION_DEFAULT`) |
| Template conditionals | `{% if workflow_context %}` in all 7 `templates/stages/*.j2` |
| Other consumers | `readiness.py:1272`, `personalization_audit.py:319`, `autoloop_driver.py:480`, `profile.py`, `rubric_loader.py`, `test_dep_map.py`, `cli.py` |
| Preset YAML | `templates/harness-yaml/{Production,Side}.yaml.j2` |
| Other targets | `templates/codex/AGENTS.md.j2`, `templates/cursor/rules/harness.mdc.j2`, `templates/rubrics/workflow.yaml.j2` |
| Autonomy defaults | `models.py:802-834` (`AutonomyConfig`), both preset YAML templates |
| Memory writes | `memory_md.py` (`upsert-failure`, `upsert-wiki`, `consolidate`), called only from `wrapup.md.j2` |
| Surface metric | `tests/structural/{surface_baseline.json,_surface_baseline.py,test_command_size_budget.py}` |
| Orphan deletion | `reconcile.sweep_orphans()` |

### Affected components

**Real reference set (measured, not estimated):**
`rg 'workflows|workflow_fuse|RESERVED_WORKFLOW_NAMES|STAGE_ABBREV|default_workflow|workflow_context' src/`
→ **151 hits across 37 files**, 24 of them templates. An earlier draft said "11 modules,
12 templates" — a ~2× undercount. Phase 1's scope list is generated from that `rg`, not
from the Current-state table.

Notably absent from the earlier list and now in scope: `templates/commands/hm/loop.md.j2`
(ADR-014); all four `templates/claude-md/{Production,Side}.{en,ko}.md.j2`, each carrying a
hard `{{ config.default_workflow }}` at line 7 — these fail at **render** time, which
`mypy --strict` cannot catch; `templates/agents/_partials/fused_preamble.md.j2` (delete —
rendered only by `workflow_fuse.fuse()`); the shared partials
`_partials/worktree_preflight.md.j2` (`{% if workflow_context %}` :19, `{% if not
workflow_context %}` :30), `_partials/gate0_receipt.md.j2:29`,
`_partials/stage_end_summary.md.j2:74` — every stage includes these, so the conditionals
are not confined to `templates/stages/*.j2` as the Current-state table implied;
`templates/commands/hm/help.{en,ko}.md.j2`; `templates/commands/hm/configure.md.j2`.

Removed: `workflow_fuse.py`, `tests/unit/test_workflow_fuse.py`,
`tests/unit/test_workflow_preamble.py`, `templates/rubrics/workflow.yaml.j2`,
`templates/agents/_partials/fused_preamble.md.j2`, AC-007 and AC-006's **fused arms only**
in `test_command_size_budget.py`.
Modified: 37 files across `src/` (13 Python modules + 24 templates), ~25 test files,
`.claude/harness.yaml`, CHANGELOG, README, `/hm:help`.
Added: archive logic in `memory_md.py`, `.claude/memory/archive/`, a `description:`
field in the command frontmatter emitter, an aggregate-chars assertion.

### Design decisions

- The `workflows` axis is removed at the schema layer first (ADR-002); every downstream
  consumer then fails loudly at import or type-check rather than silently defaulting.
  `extra="forbid"` guarantees an old `harness.yaml` raises rather than ignores.
- Migration drops `workflows` / `default_workflow` in `answers_from_harness_yaml`,
  matching the documented `second_opinion` precedent (schema_version bump + one-shot
  silent migration + a single advisory line).
- The archive pass lives in `memory_md.py` behind the existing atomic-write helper
  (ADR-006); it must be exception-isolated so an archive failure never loses a write.
- The autonomy default flip (ADR-010) changes only `AutonomyConfig` field defaults and
  the two preset fallback expressions — the marker, hook, and `autopilot_caps` paths are
  untouched.

### Data flow (archive)

```
wrapup → hm memory_md upsert-failure --slug S
          │
          ├─ 1. upsert/increment entry S            (existing, atomic)
          ├─ 2. archive pass                         (NEW, exception-isolated)
          │     for each entry E in failures.md:
          │        if E.count == 1 and age(E) > 90d → move to archive/failures-<YYYY>.md
          └─ 3. atomic_write both files
```

### API / contract changes

- `harness.yaml`: `workflows` and `default_workflow` removed; `schema_version` bumped.
- `AutonomyConfig.level` default `gated` → `auto_safe`; `autopilot_persistent`
  `false` → `true`.
- Rendered `/hm:` commands gain a frontmatter `description:`.
- New file: `.claude/memory/archive/failures-<YYYY>.md`.

## 🚦 Phase Status (updated by /hm:wrapup, 2026-08-05)

> **Why this is not `status: complete`.** `/hm:wrapup`'s Step 4 says to set
> `status: complete` and tick every checkbox. That instruction assumes a wrapup closes the
> whole PLAN; this one closes **Phase 1 of 6**. Setting `complete` and ticking 17 boxes
> would make this document assert that the autonomy flip, the migration loader, the command
> descriptions and the memory archive had shipped. They have not. Six boxes are ticked
> because they are demonstrably met; the other eleven carry a `↳` note naming the phase that
> owns them, so an unchecked box reads as *scheduled*, not *missed*.

| Phase | Status | Notes |
|---|---|---|
| 1 — fused render + `workflows` axis | **done** | Source, templates, and all test repair complete. `ruff` + `mypy --strict` green; full suite green. Measured surface **1,173,667 → 641,241 chars (−45.3%)**, against the PLAN's predicted 643,445 (−45.2%). |
| 2 — loader tolerance | not started | |
| 3 — autonomy defaults + ADR-013 pins | not started | |
| 4 — command `description:` | not started | |
| 5 — write-time failures archive | not started | |
| 6 — baseline re-freeze + docs | not started | |

**Nothing is blocked.** No commit was made (wrapup owns commits); the work sits in the
task worktree `.worktrees/harness-diet` on `hm/harness-diet`.

### Phase 1 — what is done

- Deleted: `workflow_fuse.py`, `validators.py` (whole module — it existed only to police
  workflow names; sole consumer was `interview.py`), `commands/hm/workflow_command.md.j2`,
  `codex/workflow_skill.md.j2`, `rubrics/workflow.yaml.j2`,
  `agents/_partials/fused_preamble.md.j2`, `tests/unit/test_workflow_fuse.py`,
  `tests/unit/test_workflow_preamble.py`.
- Schema: `STAGE_ABBREV`, `auto_workflow_name`, `WorkflowDef`,
  `HarnessConfig.{workflows,default_workflow}`,
  `InterviewAnswers.{fused_workflows,default_workflow}` + its `model_validator`.
- `interview.py`: both starter tables, `_SIDE_DEFAULT`/`_PRODUCTION_DEFAULT`,
  `_starter_for`/`_default_for`, `_ask_fused_workflows`/`_ask_custom_workflows`,
  `_parse_workflows`, and the reverse-map fields.
- `synthesize.py`: `_workflow_command_files`, `_codex_workflow_skills`, the `fuse`
  import, and `"workflow"` in `_ALL_RUBRICS`.
- **ADR-012 landed**: `render._RETIRED_TOP_LEVEL_KEYS` + wired into
  `_preserve_yaml_user_keys`, so an existing `harness.yaml` carrying `workflows:` is
  dropped rather than re-appended.
- **ADR-014 landed**: `loop.md.j2` per-iter section rewritten —
  `--per-iter-workflow <fused>` → `--per-iter-stages <a,b,...>`, `wrapup` rejected,
  workflow-file existence check + halt path removed, `EXPECTED_STAGES` **is** `STAGES`.
  `autoloop_driver.py`'s opaque `workflow` parameter removed.
- `readiness.py`: `fused_workflow_present` (weight 30) → `atomic_stages_complete`, and
  `harness_workflows_defined` (weight 20) removed. Deleting them outright would have left
  two permanently-unpassable signals as phantom penalties.
- Templates: `workflow_context` stripped from all 7 stage templates and the three shared
  partials (`worktree_preflight`, `gate0_receipt`, `stage_end_summary`); both preset
  `harness-yaml`; all four `claude-md`; both `help`; `codex/AGENTS.md.j2`.

### Phase 1 — test repair (done)

All ~160 failures across 33 files cleared. Where a test's *subject* disappeared but its
*mechanism* still mattered, it was **re-pointed rather than deleted** — deleting would
have silently removed the guard:

- AC-005's two negative controls (`test_an_inflated_render_fails_the_ceiling`,
  `test_a_gutted_render_fails_the_floor`) → from `exec-rev-wrap-ver` to `wrapup`. The
  floor control is ADR-017's guard against meeting a ceiling by gutting the render.
- The install-ref pin positive control, the fingerprint negative control, and the dep-map
  out-of-scope control → likewise re-pointed to atomic subjects.
- `readiness`'s `fused_workflow_present` (weight 30) → `atomic_stages_complete`, and
  `harness_workflows_defined` (weight 20) deleted. Left in place both would be
  permanently-unpassable phantom penalties.
- `loop.md`'s `plan-exec-rev` EXPECTED_STAGES assertion → two tests that check ADR-014
  actually reached the render (`EXPECTED_STAGES` **is** `STAGES`; `wrapup` rejected).
- `test_discovery_covers_all_four_artifact_families` → `..._three_...`. The
  "≥1 fused workflow" arm was **removed, not relaxed** — a `len(...) >= 0` arm would
  still be present while asserting nothing.
- `test_the_repo_render_is_under_the_adr014_ceiling` deleted: ADR-014's ceiling measured
  the largest *fused* command, which no longer renders. Its successor is the pre-existing
  `test_aggregate_shipped_surface_does_not_grow`, and the file records that.

**Fixture-position bug worth remembering:** `_ask_fused_workflows` consumed **two**
interview prompts. Removing it shifted every later positional answer two places earlier,
which surfaced as unrelated-looking failures in
`test_interview_codex_second_opinion.py` (`[""] * 11` → `[""] * 9`) and
`test_interview.py`'s ref-folders test. The assertions were fine; the inputs were not.

**Template whitespace:** the `{% if workflow_context %}` tag line contributed a newline to
the output. Deleting the conditional silently removed it from the preflight block of
every stage command; the render-equality test caught it and the blank line was restored.

### Deviation from this PLAN's phase boundaries

`surface_baseline.json` and `tests/snapshot/*.expected.yaml` were regenerated **here**,
not in Phase 6 as scoped. Without them `test_aggregate_shipped_surface_does_not_grow` and
the eight snapshot tests stay red, so "test repair complete" would have been false.
**Phase 6 must regenerate both again** after Phases 2–5 change the render. Both generators
were checked for the `HM_MAIN_CHECKOUT_PATH` pin before running — regenerating inside a
worktree is `[fail:test] snapshot-regen-inside-worktree`, this repo's most-recurring
failure at `count:13` — and the outputs were verified to contain no worktree path.

### Corrections to this PLAN found during execution

1. **Two deletion targets the PLAN never named**: `commands/hm/workflow_command.md.j2`
   (the fused command template itself) and `codex/workflow_skill.md.j2`.
2. **Phases 2 and 3 are not siblings.** Both edit `interview.py` (Phase 2 the migration
   loader, Phase 3 `_parse_autonomy` + `:718-720` + `:839`), so Step 1.5's same-file rule
   forces them serial. The `siblings-after-1` label is wrong for that pair.
3. **`validators.py` goes entirely**, which the PLAN listed only as an edit.
4. False-positive guard held: `profile.py`, `test_dep_map.py`, `readiness.py:1188-1197`
   (`.github/workflows`) and `worktree.py` (`<workflow>-<uuid>-<ts>` naming) were left
   untouched — a naive sweep of the word "workflow" would have broken the worktree
   lifecycle.

## 📝 Implementation Plan

> **`parallel_group` convention.** A shared label means the phases in it are **siblings
> that may run concurrently**; `depends_on` alone expresses ordering. The real schedule is
> **1 → (2 ∥ 3 ∥ 4) → 6**, with **5** parallel to all of them except its end-to-end
> assertion, which waits for 1. Phases 2/3/4 are siblings of each other but all depend on
> 1, which is why they share `siblings-after-1` rather than a "serial" label — an earlier
> draft labelled 1-4 `serial-render-surface`, which was redundant with `depends_on` and
> said nothing true about 2/3/4 relative to each other.

### Phase 1 — Remove the fused render and the `workflows` axis, **with** its retired-key handling
- `depends_on`: `[]`
- `parallel_group`: `foundation` — its own group. Sharing `siblings-after-1` with its own
  dependents would, under the convention above, assert Phase 1 may run concurrently with
  Phases 2/3/4.
- `merge_hazards`: `templates/harness-yaml/{Production,Side}.yaml.j2` (also touched by
  Phase 3); every rendered command output and `surface_baseline.json` (Phases 3, 4, 6)
- **Scope in**: `workflow_fuse.py` (delete), `models.py`, `validators.py`,
  `interview.py`, `synthesize.py`, `readiness.py`, `personalization_audit.py`,
  `autoloop_driver.py`, `profile.py`, `rubric_loader.py`, `test_dep_map.py`, `cli.py`,
  all 7 `templates/stages/*.j2` (`workflow_context` conditionals), both preset YAML
  templates, `templates/codex/AGENTS.md.j2`,
  `templates/cursor/rules/harness.mdc.j2`, `templates/rubrics/workflow.yaml.j2`
  (delete), `test_workflow_fuse.py` and `test_workflow_preamble.py` (delete), all
  fused-referencing tests.
  **Plus, in the same commit (ADR-012):** `_RETIRED_TOP_LEVEL_KEYS = {"workflows",
  "default_workflow"}` honored by `render._preserve_yaml_user_keys`, and a raw-YAML
  pre-strip ahead of Pydantic instantiation on every config entry point.
  **AC-006 is split, not deleted (codex P1, verified):** delete only the fused arms —
  `test_shared_blocks_appear_once_in_every_fused_command` (:482),
  `test_fused_loses_no_instruction` (:537),
  `test_the_no_loss_check_would_notice_a_dropped_instruction` (:552), and the fused rows
  of `test_rendered_commands_within_budget` (:308). **Keep**
  `test_atomic_renders_keep_their_own_copy` (:515),
  `test_the_flag_off_render_has_no_preflight_but_keeps_every_gate0_stage` (:492),
  `test_the_fingerprint_rejects_a_heading_with_an_empty_body` (:508) — they cover the
  seven surviving atomic commands.
  **Plus ADR-014**: `templates/commands/hm/loop.md.j2` per-iter rewrite (execute→review
  sequence, `--per-iter-workflow` becomes a stage list that rejects `wrapup`, workflow-file
  existence check and halt path removed) and `autoloop_driver.py:480`'s `workflow`
  parameter.
  **Plus the files the earlier draft missed** (see Technical Design): four
  `templates/claude-md/*.md.j2`, `_partials/fused_preamble.md.j2` (delete), three shared
  `_partials`, `help.{en,ko}.md.j2`, `configure.md.j2`.
- **Scope out**: `AtomicStage` enum (unchanged — all 7 stages stay), `/hm:verify`, any
  reviewer or `second_opinion` code
- **Exit criterion** — the `if` form matters because a bare `rg …; test $? -eq 1` aborts
  early under `set -e`. Note `templates/` is **inside** `src/`, so the original `src/`
  scan already covered it; both models were wrong on that half. The real gap was the
  rendered-output and fresh-render paths. Fixture directories are **excluded** — they hold
  intentional retired-format inputs that Phase 2's own exit criterion requires, and
  grepping them would make the two phases mutually unsatisfiable:
  ```
  if rg -q 'exec-rev|res-spec-plan|workflow_fuse|default_workflow|RESERVED_WORKFLOW_NAMES|workflow_context' \
        src/harness_maker/ .claude/commands/ .agents/ .cursor/ \
        tests/ -g '!tests/fixtures/**' -g '!tests/cursor-compat/fixture/**' -g '!tests/e2e/sandbox*/**' ; \
     then echo FAIL; exit 1; fi
  # fresh render of BOTH presets x all target combinations into a tmp dir, then the same rg
  # (this render is what catches the four claude-md templates — mypy cannot)
  uv run ruff check . && uv run mypy --strict src/
  uv run pytest tests/ -q
  ```
  The committed render snapshots under `tests/e2e/sandbox*/` are regenerated in **Phase 6**
  with the baseline, not here — recorded so the exclusion above is a decision, not a hole.
  `/hm:loop` render + halt-path tests are part of this phase's suite run.
- **Risk**: `high`
- **Rollback**: revert to the pre-phase commit; this is the first phase, so the branch
  base is the rollback point

### Phase 2 — Loader tolerance for already-installed projects
- `depends_on`: `[1]`
- `parallel_group`: `siblings-after-1`
- `merge_hazards`: `interview.py` (Phase 1)
- **Context**: ADR-012 moved the drop-list into Phase 1. What remains here is the case
  codex raised separately (P1): `answers_from_harness_yaml` is the `make --update`
  reverse-map path and does **not** run when an already-installed project merely loads
  its config after a package upgrade.
- **Scope in**: route every config entry point through one shared migration loader that
  strips retired keys before validation; `schema_version` bump; a single advisory line
  per project, not per load; migration unit + integration tests
- **Scope out**: autonomy keys (Phase 3)
- **Exit criterion**: a test upgrades the package **without** re-rendering, loads a
  fixture `harness.yaml` containing `workflows:` + `default_workflow:`, and asserts it
  loads cleanly, drops both keys, and emits exactly one advisory;
  `uv run pytest tests/unit/ tests/integration/ -k migration -q`.
  The retired-format inputs this phase needs already exist and are deliberately preserved:
  `tests/fixtures/harness_yaml_v1_with_provenance.yaml`,
  `tests/cursor-compat/fixture/.claude/harness.yaml`. They are the paths Phase 1's grep
  excludes — the exclusion exists for this phase.
- **Risk**: `medium`
- **Rollback**: Phase 1 tip

### Phase 3 — Promote autonomy defaults and restore this repo's caps
- `depends_on`: `[1]`
- `parallel_group`: `siblings-after-1`
- `merge_hazards`: both preset YAML templates (Phase 1)
- **Scope in**: `AutonomyConfig.level` default → `auto_safe`, `autopilot_persistent`
  default → `true`, both preset fallback expressions, `.claude/harness.yaml`
  (`step_cap: 20`, `time_cap_min: 300`, `autopilot_persistent: true`), **and ADR-013's
  explicit fallback**: `interview._parse_autonomy`'s missing/malformed branch constructs
  `AutonomyConfig(level="gated", autopilot_persistent=False)` rather than a bare
  `AutonomyConfig()` — **both** returns, the absent branch (`:1441`) and the malformed
  branch (`:1461`).
  **Also in scope — but the two bare `AutonomyConfig()` sites on the interview path are
  opposites and must not be treated alike:**
  - `interview.py:839` (synthesis fallback, `autonomy if autonomy is not None else
    AutonomyConfig()`) **is** the site that delivers the new default to a new harness.
    Leave it bare so the flipped class default reaches it. The preset templates' `else`
    literals are the *unreachable* arm for a normal render (`config.autonomy` is truthy),
    so changing only those would ship nothing.
  - `interview.py:718-720` is the branch taken when the interviewee answers anything other
    than `y`/`yes` to "Enable autopilot auto-advance? [y/N]". It is an **explicit decline**.
    Pin it the ADR-013 way — `AutonomyConfig(level="gated", autopilot_persistent=False)` —
    or the flipped class default converts a user's "no" into persistent auto-arm. That is
    strictly worse than the malformed-config case, because here the user was asked.
- **Scope out**: `autopilot.py` marker logic, `autopilot_caps` boundary logic, hooks
- **Exit criterion**:
  ```
  uv run python -c "from harness_maker.models import AutonomyConfig as A; a=A(); assert a.level=='auto_safe' and a.autopilot_persistent is True"
  # ADR-013 divergence — BOTH bare-AutonomyConfig() returns in _parse_autonomy must stay
  # gated: the absent branch (:1441, `not isinstance(value, dict)`) and the malformed
  # branch (:1461). Testing only 'bogus' reaches :1461 alone.
  # `p({})` is deliberately NOT asserted: {} is a dict, so it skips :1441 and validates
  # cleanly at :1458, returning the class defaults by design. Asserting it gated would
  # contradict the AutonomyConfig() assertion above.
  uv run python -c "from harness_maker.interview import _parse_autonomy as p; \
    assert p({'level':'bogus'}).level=='gated'; assert p(None).level=='gated'; \
    assert not p({'level':'bogus'}).autopilot_persistent and not p(None).autopilot_persistent"
  # ADR-013 extension — an explicit interview decline must stay gated (interview.py:718-720)
  uv run pytest tests/unit/ -k "autonomy or autopilot" -q
  ```
- **Risk**: `medium`
- **Rollback**: Phase 2 tip

### Phase 4 — Command frontmatter descriptions
- `depends_on`: `[1]`
- `parallel_group`: `siblings-after-1`
- `merge_hazards`: rendered command outputs and `surface_baseline.json` (Phases 1, 6)
- **Implements**: ADR-016
- **Scope in**: the per-target parser check **first** (does `synthesize`'s Codex TOML path
  and `_render_cursor_mdc` carry `description` through, or must it be target-conditional?),
  then the command frontmatter emitter in `render.py` / `synthesize.py`, a one-line
  description per surviving command, and a structural test asserting **non-empty**
  `description:` on every rendered `/hm:` command (uniqueness is an advisory warning, not
  a gate — ADR-016)
- **Scope out**: command bodies
- **Exit criterion**: `uv run pytest tests/structural/ -k description -q` passes;
  `rg -L '^description:' .claude/commands/hm/*.md` lists nothing; a render with
  `targets: [claude-code, cursor, codex]` produces valid output for all three
- **Risk**: `low`
- **Rollback**: Phase 3 tip

### Phase 5 — Write-time failures archive
- `depends_on`: `[]`
- `parallel_group`: `parallel-memory`
- `merge_hazards`: `templates/stages/wrapup.md.j2` — the failure writer is invoked
  **only** from the wrapup stage, and Phase 1 edits that template. The unit work is
  independent; the end-to-end assertion is not (codex P2). Land the code in parallel,
  but run the e2e check after Phase 1.
- **Scope in**: `memory_md.py` archive pass inside `upsert-failure`
  (`count==1 and age>90d`, `count>=2` exempt, exception-isolated, atomic),
  **per-entry date handling (both models):** the heading regex matches the *shape*
  `YYYY-MM-DD`, so `2026-99-99` passes it and fails calendar parsing. Wrap parsing per
  entry — a malformed or missing date means *preserve + warn*, never archive, and never
  abort the pass for the remaining entries. Compute the archive set inside the same
  lock and the same read-modify-write transaction as the upsert.
  `.claude/memory/archive/failures-<YYYY>.md`, unit tests for boundary ages, exempt
  entries, and an archive-failure-does-not-lose-the-write case.
  **gitignore verification (not assumption):** `.gitignore` re-includes
  `!.claude/memory/` and then re-ignores only `semantic/`, `episodic/`, `profile/`, and
  `*.lock`, so `archive/` is tracked — which ADR-005 requires. The file's own header
  records a past regression where new memory files were silently dropped from `git add`,
  so assert it rather than assume it: `git check-ignore -v .claude/memory/archive/failures-2026.md`
  must print nothing.
  **Plus ADR-015**: extend `worktree._classify`'s deliverable branch and
  `_is_create_guard_harness_artifact` to `.claude/memory/archive/` (anchored directory
  prefix, not a substring test), so an uncommitted archive file cannot trip the Layer 2
  dirty-base guard and block `worktree create`.
- **Scope out**: `wiki.md` (ADR-007), `memory_retrieve.py`, `consolidate`
- **Exit criterion**:
  ```
  uv run pytest tests/unit/ -k "memory_md" -q
  uv run python -m harness_maker.memory_md upsert-failure --root . --slug probe-archive --category design --body-file <tmp>
  # then assert: failures.md entry count dropped, archive file exists, no count>=2 entry moved,
  #              a fixture entry dated 2026-99-99 is still present and warned about
  # ADR-015: `worktree create` succeeds with an uncommitted archive file present
  # e2e (after Phase 1): the surviving wrapup render invokes the writer and the pass fires
  ```
- **Risk**: `medium`
- **Rollback**: branch base for the code; the e2e assertion rolls back with Phase 1

### Phase 6 — Re-freeze baseline, aggregate ratchet, docs
- `depends_on`: `[1, 2, 3, 4, 5]`
- `parallel_group`: `serial-close`
- `merge_hazards`: `surface_baseline.json` — must be regenerated last, after every
  render-affecting phase
- **Scope in**: regenerate `surface_baseline.json` via `_surface_baseline.py`; retune the
  existing `test_aggregate_shipped_surface_does_not_grow` (:367) — **it already exists;
  the earlier "add an aggregate assertion" wording was wrong** — keeping its **per-target**
  `{claude, codex}` form so a rise in one target cannot hide behind a cut in the other
  (codex P2); CHANGELOG BREAKING entries — **three** user-visible breaks, not two: fused
  removal, the autonomy default flip, and **ADR-014's redefinition of
  `--per-iter-workflow`** from a fused command name to a stage list that rejects `wrapup`
  (a user with `--per-iter-workflow exec-rev` in a script otherwise gets a rejected value
  and no entry pointing at the new form) — stating
  that existing harnesses adopt the new autonomy default only on
  `/harness-maker:make --update`, per ADR-013); `/hm:help` update; README/docs references
  to fused workflows; 5-file version sync
- **Scope out**: new features
- **Exit criterion**:
  ```
  uv run python tests/structural/_surface_baseline.py   # regenerate
  uv run pytest tests/ -q                                # full suite green (~6 min; run
                                                         # backgrounded, trust rc written
                                                         # to the output file, not the
                                                         # notification's exit code)
  uv run --with . hm health --root .                     # zero P0
  # Per-target ceilings, with the expected post-change values stated so the margin is
  # visible rather than implied:
  #   claude: 853,424 - 499,797 = 353,627 expected   → ceiling 375,000 (margin 21,373)
  #   codex:  320,243 -  30,425 = 289,818 expected   → ceiling 300,000 (margin 10,182)
  # Phase 4's `description:` lines (~2KB total) and Phase 1's `{% if not workflow_context %}`
  # arms both land inside these margins; an earlier draft quoted a 700,000 combined
  # ceiling and 56,555 slack, which contradicted its own per-target numbers.
  # Regenerate the tests/e2e/sandbox*/ render snapshots here (deferred from Phase 1).
  ```
- **Risk**: `low`
- **Rollback**: Phase 5 tip

## 🧪 Testing Strategy

**Unit** — migration drop of `workflows`/`default_workflow` with a single advisory;
`AutonomyConfig` defaults **and** the ADR-013 divergences (`_parse_autonomy`'s absent and
malformed branches, and the interview decline branch, all `gated`); archive predicate at
the 89/90/91-day boundary; `count>=2` exemption at any age; archive exception does not
lose the write; every rendered command has a **non-empty** `description:` (uniqueness
warns, does not fail — ADR-016).

**Structural** — `surface_baseline.json` regenerated and the aggregate under budget;
no `exec-rev` / `res-spec-plan` / `workflow_fuse` reference survives in `src/` or
rendered output; AC-005 ceilings and **floors** still hold for surviving commands (the
floor is what proves the reduction came from deleting whole commands, not from gutting
the survivors).

**Integration** — render a fixture harness with `targets: [claude-code, cursor, codex]`
and assert no fused artifact appears in `.claude/`, `.agents/`, or `.cursor/`; render an
old fixture `harness.yaml` carrying the removed keys and assert clean migration.

**Manual** — after `/harness-maker:make --update` on this repo, confirm `sweep_orphans`
deleted the five fused command files and logged to `orphans-<date>.jsonl`; confirm a new
session auto-arms autopilot and that `autopilot_caps boundary` halts at `step_cap: 20`.

**Suite runtime** — the full suite is ~6 minutes; run it in the background and read the
`rc=$?` written to the output file rather than trusting the notification's exit code.

## ⚠️ Risks & Mitigation

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R1 | Removing `{% if workflow_context %}` from 7 stage templates shifts atomic-render chars, so surviving AC-005 floors fail | high | medium | Expected and desired; regenerate the baseline in Phase 6 and confirm the delta is confined to the conditional's own bytes |
| R2 | A user modified a fused command → `sweep_orphans` keeps it; the stale file still "works" | medium | low | ADR-009 accepted limitation; name it in the CHANGELOG and check `orphans-<date>.jsonl` |
| R3 | `_preserve_yaml_user_keys` preserves `workflows` through the migration, re-introducing a forbidden key | **confirmed** | high | **Resolved by ADR-012** — the drop-list ships inside Phase 1. Phase 1 test asserts the key is absent from the *re-rendered* `harness.yaml`, not just from the parsed model |
| R11 | An already-installed project loads its config after a package upgrade without ever re-rendering, so `answers_from_harness_yaml` never runs and validation sees the retired key | medium | high | Phase 2's shared migration loader on every config entry point; the phase's exit criterion tests the no-re-render path explicitly |
| R12 | The class-default flip converts `_parse_autonomy`'s malformed-block safety fallback into an auto-arm path | **confirmed** | high | **Resolved by ADR-013** — explicit `gated` construction on the missing/malformed branch, with a test asserting the class default and the fallback intentionally differ |
| R13 | A single entry with a shape-valid but calendar-invalid date (`2026-99-99`) aborts the archive pass, permanently blocking archival of every healthy entry | medium | medium | Per-entry try/except in Phase 5; malformed date → preserve + warn, never abort |
| R14 | Splitting AC-006 removes an atomic arm by accident along with the fused arms | medium | medium | Phase 1 names the four fused arms to delete and the three atomic arms to keep by line number; the suite fails if an atomic arm disappears |
| R4 | `autoloop_driver.py` takes `workflow: str = "exec-rev-wrap"` (opaque, `noqa: ARG001`) and `/hm:loop` passes it | medium | high | Phase 1 must remove the parameter and its call site together; `/hm:loop` render test must stay green |
| R5 | `personalization_audit.py:319` uses `default_workflow=exec-rev-wrap` in convergence logic (F22) | medium | medium | Re-derive the convergence baseline in Phase 1; `test_personalization_audit_convergence.py` is the gate |
| R6 | Auto-arm by default surprises a downstream user mid-session | medium | medium | ADR-010 accepted; CHANGELOG BREAKING; mandatory gates and the restored caps bound the blast radius |
| R7 | Write-time archive makes `upsert-failure` non-atomic or slow | low | high | Archive inside the existing atomic-write path, exception-isolated; a failed archive logs and returns success for the write |
| R8 | Archiving removes an entry that recurs the following week | medium | low | Archive, never delete; the file is committed and greppable |
| R9 | Deleting AC-006/AC-007 removes real protection for the surviving atomic renders | **confirmed for AC-006** | medium | AC-006 is **not** fused-specific: `:492`, `:508`, `:515` cover the seven surviving atomic commands. Phase 1 splits it. AC-007 is genuinely fused-only, and the atomic autopilot block is independently covered by `tests/structural/test_autopilot_advance_render_gate.py` — so the antigravity finding claiming otherwise is refuted |
| R10 | Codex `AGENTS.md.j2` / Cursor `harness.mdc.j2` reference workflows → render error on a non-Claude target | medium | high | Phase 1 exit criterion renders all three targets, not just Claude |
| R15 | `/hm:loop` silently decommissioned — template fails to render, or renders and halts before iter 1 | **confirmed** | critical | **Resolved by ADR-014**; `loop.md.j2` and `autoloop_driver.py:480` move into Phase 1 scope with render + halt-path tests |
| R16 | ADR-014's stage-list flag admits `wrapup`, so an iteration commits and merges, defeating the per-loop worktree | medium | high | The flag rejects `wrapup` explicitly; loop-close retains sole ownership of wrapup |
| R17 | Four `templates/claude-md/*.md.j2` reference a deleted field and fail at **render** time, which `mypy --strict` cannot catch | **confirmed** | high | Phase 1's exit criterion includes a fresh render of both presets × all target combinations, which is the only check that reaches them |
| R18 | Phase 1's grep and Phase 2's fixture requirement are mutually unsatisfiable | **confirmed** | medium | Phase 1 excludes `tests/fixtures/`, `tests/cursor-compat/fixture/`, `tests/e2e/sandbox*/`; Phase 2 names them as intentional retired-format inputs |
| R19 | `.claude/memory/archive/` is neither churn nor deliverable → uncommitted archive file blocks `worktree create` (Layer 2) | **confirmed** | high | **Resolved by ADR-015**; Phase 5 exit asserts `worktree create` succeeds with an uncommitted archive present |
| R20 | Phase 6's per-target margins (21,373 / 10,182) are consumed by Phase 4's `description:` lines and Phase 1's `not workflow_context` arms | medium | medium | Margins are stated with the expected post-change values so the budget is visible; if breached, the ceiling is raised deliberately rather than the render gutted (AC-005 floors enforce this) |

## ✅ Success Criteria

- [x] No `exec-rev*`, `plan-exec-rev`, or `res-spec-plan` artifact in `.claude/`,
      `.agents/`, or `.cursor/` for any `targets` combination.
- [x] `workflow_fuse.py`, `RESERVED_WORKFLOW_NAMES`, `default_workflow`, and
      `STAGE_ABBREV` are absent from `src/`.
- [ ] `/hm:loop` renders and completes an iteration with no fused command present
      ↳ renders + rejects `wrapup` are asserted; a full live iteration is unverified.
      (ADR-014), and its stage-list flag rejects `wrapup`.
- [x] A fresh render of both presets × all target combinations succeeds — this is the
      only check that reaches the four `claude-md` templates.
- [x] `surface_baseline.json` per-target: `aggregate_chars.claude ≤ 375,000` **and**
      `aggregate_chars.codex ≤ 300,000` (expected 353,627 / 289,818, from 853,424 / 320,243).
- [ ] `worktree create` succeeds with an uncommitted `.claude/memory/archive/` file
      ↳ **Phase 5** — the archive directory does not exist yet.
      present (ADR-015).
- [x] AC-005 ceilings **and floors** hold for every surviving command.
- [x] AC-006's three atomic arms (`:492`, `:508`, `:515`) still run and pass.
- [ ] An old `harness.yaml` with `workflows:` loads cleanly **without re-rendering**, and
      ↳ the re-render half is covered by `test_a_retired_key_is_not_re_injected_on_re_render`;
        the load-without-re-rendering half + the single advisory are **Phase 2**.
      re-renders without the key reappearing, emitting exactly one advisory.
- [ ] `AutonomyConfig()` yields `level == "auto_safe"` and `autopilot_persistent is True`,
      ↳ **Phase 3**.
      **while** `_parse_autonomy` on a malformed block yields `gated` / `False`.
- [ ] `.claude/harness.yaml` has `step_cap: 20`, `time_cap_min: 300`.
      ↳ **Phase 3**.
- [ ] Every rendered `/hm:` command has a **non-empty** frontmatter `description:`
      ↳ **Phase 4**.
      (uniqueness is an advisory warning, not a gate — ADR-016).
- [ ] `interview.py:718-720` returns `gated` / `False` on an explicit decline (ADR-013).
      ↳ **Phase 3** (ADR-013).
- [ ] `failures.md` ≤ ~95 entries; `.claude/memory/archive/failures-2026.md` holds the
      ↳ **Phase 5**.
      rest; no `count>=2` entry archived.
- [ ] `upsert-failure` remains atomic and succeeds when the archive pass raises.
      ↳ **Phase 5**.
- [ ] Full suite green; `hm health` reports zero P0.
      ↳ full suite is green; `hm health` not run this unit.
- [ ] CHANGELOG carries BREAKING entries for all three user-visible breaks: the fused
      ↳ CHANGELOG done this unit; the 5-file version sync is **Phase 6 / release**.
      removal, the autonomy default flip, and `--per-iter-workflow`'s new stage-list form;
      5-file version sync done.

## 🔍 Plan Validation

### Cross-model second opinion

```yaml
second_opinion_results:
  - model: codex
    status: invoked
    findings: 10   # 3 P0, 4 P1, 3 P2
  - model: antigravity
    status: invoked
    findings: 7    # 2 P0, 1 P1, 2 P2, 2 P3
```

Both models ran successfully. Independent convergence on two P0s.

| Finding | Models | Disposition | Resolution |
|---|---|---|---|
| P1→P2 ordering unshippable (`extra="forbid"` + `_preserve_yaml_user_keys` resurrect the key) | codex + antigravity | **accepted** | ADR-012; Phase 1 absorbs the retired-key drop-list |
| `_parse_autonomy` fallback becomes an auto-arm path | codex | **accepted** | ADR-013 (Interview #13); explicit `gated` construction |
| AC-006 deletion loses atomic-render coverage (`:515` et al.) | codex | **accepted** — verified in the file | Phase 1 splits AC-006 by named arm |
| Archive predicate: shape-valid but calendar-invalid dates; needs per-entry isolation | codex + antigravity | **accepted** | Phase 5 scope + R13 |
| P1 exit criterion under-scoped (`templates/`, `.agents/`, `.cursor/`, fresh renders) and fragile under `set -e` | codex + antigravity | **accepted** | Phase 1 exit rewritten as `if/elif` over the wider path set |
| P5's `merge_hazards: none` is wrong — the writer is wrapup-only and Phase 1 edits wrapup | codex | **accepted** | Phase 5 hazards + split unit/e2e timing |
| Pydantic default flip does not reach users with explicit values | codex + antigravity | **accepted** | Already in ADR-010 consequences; now also in the CHANGELOG requirement and success criteria |
| Combined-only char assertion hides a per-target rise; target is arithmetically reachable (643,445, 56,555 slack) | codex | **accepted** | Per-target ceilings in Phase 6 and the success criteria |
| Migration never fires for an installed project that only upgrades the package | codex | **accepted** | Phase 2 rescoped to a shared migration loader; R11 |
| Cursor/Codex stranded with no multi-stage mechanism | codex + antigravity (both P0) | **acknowledged, not actioned** | Presented as the explicit trade-off of Interview #1 option A and chosen with that information; recorded in ADR-001 consequences |
| Deleting AC-007 leaves the atomic autopilot block untested | antigravity | **rejected** | Refuted: `tests/structural/test_autopilot_advance_render_gate.py` covers it via `test_terminal_stop_names_the_auto_advance_exception` (stage-parameterized), `test_auto_advance_block_claims_precedence`, `test_auto_advance_passes_the_task_slug` |

### Plan validator

**Outcome: `MAJOR_REVISION` → resolved.** Four critical findings, seven warnings /
suggestions. All eleven were verified against the codebase before being folded in; none
were accepted on assertion alone.

| # | Severity | Finding | Resolution |
|---|---|---|---|
| 1 | critical | `/hm:loop` is structurally dependent on the deleted fused commands, yet Phase 1 declared it out of scope — the template would fail to render, and if it rendered every loop would halt before iteration 1. ADR-001's "no Claude Code capability lost" was false. | **ADR-014** + Interview #14. `loop.md.j2` and `autoloop_driver.py:480` moved into Phase 1; ADR-001 consequences corrected; R15/R16 added. Verified in `loop.md.j2`. |
| 2 | critical | Blast radius undercounted ~2× — the real set is 151 hits across 37 files, including four `claude-md` templates that fail at *render* time (invisible to `mypy`), `fused_preamble.md.j2`, and three shared `_partials` the Current-state table implied did not exist. | Technical Design now states the measured set; Phase 1 scope regenerated from `rg`; R17 added. Verified: 37 files, and the four `claude-md` hits at line 7. |
| 3 | critical | The fused set is seven names, not five — `exec-rev-ver-wrap` and `plan-exec-rev-wrap` were omitted. Five is what this repo renders, not what the schema defines. | Executive Summary and ADR-001 corrected. Verified at `interview.py:71-136`. |
| 4 | critical | Phase 1's widened grep and Phase 2's fixture requirement are mutually unsatisfiable; and the widening was partly wrong, since `templates/` is inside `src/`. | Phase 1 excludes the three fixture/snapshot paths and says why; Phase 2 names them as intentional inputs; sandbox snapshot regeneration explicitly deferred to Phase 6. R18 added. |
| 5 | warning | `.claude/memory/archive/` is neither churn nor deliverable → an uncommitted archive file trips the Layer 2 dirty-base guard. Phase 5 had deferred this as a checklist item. | **ADR-015** + R19 + a Phase 5 exit assertion. |
| 6 | warning | Phase 6's budget was self-contradictory (a 700,000 combined ceiling quoted against per-target ceilings summing to 655,000); real margins were 6,373 / 5,182, not 56,555. | Ceilings raised to 375,000 / 300,000 with expected values stated inline; the contradictory sentence removed. R20 added. |
| 7 | warning | `parallel_group` was meaningless as assigned — the label said nothing true about phases 2/3/4 relative to each other. | Convention stated once; label renamed `siblings-after-1`; the real schedule written out. |
| 8 | warning | The `description:` work had no ADR despite being a shipped contract change on three parsers, and imposed a uniqueness constraint no decision justified. | **ADR-016**; the per-target parser check moves ahead of the emitter; uniqueness demoted to advisory. |
| 9 | warning | Phase 3's ADR-013 check exercised only `_parse_autonomy`'s malformed branch (`:1461`), not the absent branch (`:1441`) — and named the preset `else` literals, which are the unreachable arm for a normal render. | Exit criterion now asserts all three inputs; `interview.py:720`/`:839` added to scope as the constructions that actually deliver the default. |
| 10 | suggestion | ADR-012 claimed to introduce a retired-key concept that already exists at `interview.py:1451-1456` (`guard_when`). | Cited as precedent in ADR-012. |
| 11 | suggestion | ADR-004's `Source: Interview #3` did not match the transcript. | Re-sourced as an inference, consistent with how other gate-filtered assumptions are labelled. |

The validator also confirmed every one of the second-opinion dispositions above, including
the antigravity rejection (it independently located the three tests in
`test_autopilot_advance_render_gate.py`) and every AC-006 line number.

### Plan validator — pass 2

**Outcome: `MAJOR_REVISION` again.** Of the 11 pass-1 findings: **8 resolved**, **3
partially resolved**. It then found **two new critical defects introduced by the pass-1
revisions themselves**, plus three carry-overs from the partial resolutions. Both new
criticals were verified against `interview.py` before being accepted.

| Severity | Defect | Fix applied |
|---|---|---|
| critical | The new Phase 3 assertion `p({}).level=='gated'` is **unsatisfiable**: `{}` is a dict, so it skips the `:1441` absent branch and validates cleanly at `:1458`, returning the class defaults — which ADR-010 flips to `auto_safe`. The plan asserted that *and* `AutonomyConfig()` yields `auto_safe` simultaneously. | `p({})` dropped from the criterion with the reason stated inline; the empty-but-present block is recorded as an accepted, non-special-cased case in ADR-013, because a predicate for "empty or partial" would silently extend to `{step_cap: 20}`. |
| critical | Pass 1 added `interview.py:720` to Phase 3 as a "default-delivery site". It is the **opposite** — the branch taken when the interviewee answers anything but `y`/`yes` to "Enable autopilot auto-advance? [y/N]". Left bare under the flipped default it converts an **explicit refusal** into persistent auto-arm, which is worse than the malformed-config case ADR-013 exists for. | Phase 3 scope now splits the two sites explicitly: `:839` stays bare (it *is* the delivery site), `:718-720` is pinned to `gated`/`False` the ADR-013 way. Recorded as an ADR-013 consequence and a success criterion. |
| warning | Phase 1 still carried `siblings-after-1`, which under the newly-stated convention asserts it may run concurrently with its own dependents. | Phase 1 moved to its own `foundation` group. |
| warning | ADR-016 demoted uniqueness to advisory, but Testing Strategy and Success Criteria still hard-gated it — and Success Criteria is what `/hm:verify` checks. | Both changed to non-empty, uniqueness advisory. |
| suggestion | ADR-014's `--per-iter-workflow` redefinition is a user-visible flag break, but Phase 6's CHANGELOG scope listed only two BREAKING items. | Third BREAKING item added to Phase 6 scope and to the success criterion. |

**Re-validation budget is exhausted** (the stage allows one re-run). All five pass-2
critiques were fixed rather than accepted as risk, but those fixes have not themselves been
validator-checked. Invariants were re-verified mechanically after the edits: 16 ADRs
matching frontmatter, 10 required sections in order, all six phases carrying every required
field, no banned deferral phrasing, and the two specific pass-2 defects confirmed absent.
