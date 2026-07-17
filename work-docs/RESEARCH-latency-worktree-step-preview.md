---
type: research
task_slug: latency-worktree-step-preview
status: complete
created: 2026-05-31
tags: [harness-maker, research, latency, token-cost, worktree, parallel-execution, step-preview]
mtime_warn_days: 7
libs_fetched: []
sources: []
related_docs: [[PLAN-worktree-cross-session-data-loss-defense]], [[PLAN-worktree-base-artifact-pollution]], [[PLAN-worktree-finalize-stash-isolation]], [[REVIEW-worktree-phantom-path-2026-05-31]]
summary: "Three tracks: dedupe gate/receipt blocks + cache memory; fix branch leak + Layer-3 + fence; add step-manifest partial"
---

# RESEARCH — Command/Skill/Agent Latency · Worktree Parallelism · Step-Preview

Internal audit of harness-maker's own rendered prompts and worktree subsystem.
Five parallel deep-readers covered the 7 stage templates (~2880 lines),
`loop.md.j2` (1156), 10 skills, all agent bodies/partials (~1862), and
`worktree.py` (2433) + `autoloop_driver.py` + `iter_receipts.py`. Every claim
below carries a `file:line` citation. Highest-stakes worktree findings
(branch leak, merge-fence boundary) were independently re-verified by grep.

## 🎯 Recommended Direction

Treat the three asks as three independent tracks, sequenced by ROI:

1. **Q1 — Latency/token (highest leverage, lowest risk):** The dominant waste is
   **duplication of two blocks across stages**, not any single expensive step.
   The **5-term inequality gate (~25 lines × 3 stages)** and the **Gate-0 receipt
   block (~25 lines × 4 stages)** are byte-for-byte copies re-read on every
   invocation, and a fused workflow renders the receipt block 3–4× in one turn.
   Extract both into shared render fragments, and **cache `memory_retrieve`
   per-slug** the way `RESEARCH.md` already caches `sources`/`libs_fetched`
   (research Phase 3 explicitly calls that the single biggest token saver). This
   removes ~175 duplicated lines and 2 redundant 30→6 reranks per slug chain.
   Secondary: move loop-only/doctrine prose out of `loop.md.j2`'s 1156-line body
   into the **already-existing `autoloop-driver` skill** (loaded once vs re-read
   ≤50× per loop).

2. **Q2 — Worktree parallelism (highest correctness risk):** Two real
   correctness bugs, not just inefficiency. **(a) Orphan branch leak** —
   `cleanup()` never runs `git branch -D`; confirmed no such call exists anywhere
   in the module, so every finalized worktree leaks a branch + its WIP commit
   forever. **(b) Layer-3 session-UUID strict mode is self-defeating** —
   `owned-uuids` builds the owned set from *all* live `.hm-loop-*` markers
   (shared filesystem), so concurrent sessions admit each other's stash refs; the
   code's own comments admit this. Plus a narrower **merge-fence boundary gap**
   (stash happens outside the flock). Fixing (a) and (b) is the priority; the
   stash-envelope/post-commit-pop apparatus (~600 of 2433 lines) is also a
   complexity-reduction candidate now that the base is kept clean by design.

3. **Q3 — Step preview (cheap UX win, one design tension):** No command or skill
   announces its steps today (confirmed). The Procedure headings are clean and
   LLM-extractable. Cleanest mechanism: one shared `_partials/step_manifest.md.j2`
   included at the head of the **two Claude wrappers** (`atomic_command.md.j2`,
   `workflow_command.md.j2`) **plus the two Codex skill wrappers**. The one hard
   constraint: it **must be suppressed under `/hm:loop` dispatch**, or it floods
   the autoloop transcript ×iterations.

Each track is independently shippable. None requires the others. `/hm:plan`
makes the binding decisions; the below is informational.

## 🔍 Refinement Decisions

`--deep` not set. Discovery lens: **Technical architecture / implementation**
(this is an internal codebase audit, not a user-facing trend question — the
user-workflow/product lens does not apply). No refinement interview run.

## 🛠️ Approaches Found

### Track Q1 — Latency & token cost

**Cross-stage redundancy (the main finding, not per-step bloat):**

| Field | Content |
|---|---|
| Approach | Extract duplicated blocks to shared fragments + cache memory per-slug |
| Assumption | The per-invocation token cost is dominated by re-read duplication, not by genuinely expensive single steps |
| Evidence | 5-term gate duplicated: research `Phase 0.5` (115–161), spec `§2.5` (97–145), plan `Step E` (292–340). Gate-0 receipt duplicated: research (283–307), spec (339–363), plan (426–450), execute (305–329), and again in review/wrapup/verify — identical 15-line guarded `iter_receipts write`. `memory_retrieve --k 6 --pre-k 30` runs in research (72), spec (65), plan (42) on the same slug; RESEARCH-doc caching of `sources`/`libs_fetched` (research:233) proves the pattern works but is not applied to memory/second-brain results. |
| Trade-off | Shared fragments add one indirection layer in the render pipeline; per-slug memory cache needs an invalidation story |
| Compatibility | Aligns with existing `RESEARCH.md`-reuse pattern (execute Step 2 reads it, 175–176); render.py already composes fragments |
| Risk | low |

**Per-stage expensive steps (ranked, ESSENTIAL/REDUCIBLE/CUTTABLE):**

- **research Phase 1** — 7 parallel sources @ ≤8k budget (185–211) + "discovery
  coverage guard" (201–205). **REDUCIBLE**: gate sources 4–6 behind the Phase
  0.75 lens so a "technical" lens skips the user-workflow matrix + arXiv prose.
  **Phase 0.75 lens (163–183) CUTTABLE as a separate phase** — fold into Phase 1
  opening; it restates source categories that reappear at 192.
- **spec Step 4.5 quality gate** (300–330) — full SPEC body shelled through `jq`
  into `spec_quality eval`. **REDUCIBLE**: skip entirely when
  `dev_mode == task-driven` (it only WARNs there, 324). **Step 4 `pytest
  --collect-only`** (287) should never fire at spec-time (tests not yet written)
  — set `pending_test: true` and defer collection to execute.
- **plan Step 3 interview** (177–347, 170 lines — largest single block):
  ESSENTIAL, but **Step E gate (292–340) REDUCIBLE** (3rd verbatim gate copy).
  **Step 1.5 loop-mode detection (99–145, 47 lines) REDUCIBLE** — standalone
  `/hm:plan` pays 47 dead lines; gate behind conditional render or move detail to
  the autoloop-driver skill.
- **execute per-phase A→D loop** (179–291) — ESSENTIAL TDD core, but **wire
  `build_test_hints()` (mentioned at 17) into Phase D's `<test command>` (259)**
  so the full suite doesn't run per phase. **Step 5 finalize (331–391, 61 lines
  of branchy prose) REDUCIBLE in context** — move the "workflows without wrapup"
  fallback (373–391) behind conditional render.
- **review auto-fix loop** (344–386) — ESSENTIAL, but re-running the **full
  Step-4 consensus filter** (370) each round on a small fix-set is overkill;
  REDUCIBLE to merging touched-file findings into prior consensus. **`code-verifier`
  middle dispatch (191–211) CUTTABLE for quick/standard runs**. **Step 2.5
  silent-intent-miss hook (122–150) CUTTABLE from body** — pure telemetry, "does
  NOT change the verdict" (148).
- **wrapup Step 5.6 second-brain promotion** (266–305, "MUST evaluate every
  wrapup") — REDUCIBLE: collapse ADR/idempotency prose (296–303) into the CLI
  `--help`; keep trigger + one-line receipt.
- **verify** — **Procedure recap (247–254) CUTTABLE** (restates checks already at
  41–152). Check-2 suite is cache-gated and runs again in wrapup Step 2 (cheap
  hit) — acceptable.
- **loop.md.j2 (1156 lines, re-read ≤50×):** ~250 lines are doctrine/dead-path:
  non-stopping discipline (13–40), forbidden-halt table (556–588), Gate-0
  retry/escalation procedure (813–865), **P5 batch mode (1044–1141, a fully
  separate code path) — strongest extraction candidate**. Genuine per-iter logic
  is only ~150 lines (4-gate 670–735, marker 737–760, dispatch 761–767, Gate-0
  verify call 792–812, update-state 867–878).

**Skills:** Two routinely-fired expensive steps that **duplicate the same
readiness computation**: **ai-readiness Layer 2** (per-rubric LLM scoring on every
`/hm:health`, `ai-readiness-rubric/SKILL.md.j2:33,39`) and
**verify-before-completion Check 3** (`compute_readiness` recompute every
wrapup/iteration close, `verify-before-completion/SKILL.md.j2:52-66`). Both
REDUCIBLE via caching — both skills already advertise the hook (layer-only mode
`:22`; "previous PASS still valid" `:18-20`). `trajectory-monitor`'s cosine
pre-filter gating the LLM (`:15-18`) is the exemplary pattern to copy.

**Agents:** Small partials (communication_*, rubric, reasoning, hard_rules) are
verbosity-gated and fine. Real multiplication: **second_opinion_codex.md.j2 (112
lines × up to 3 agents)** — REDUCIBLE by externalizing the bash recipe; and the
**un-partialed ~20-line "Investigation Steps" block copied across 5 reviewer
bodies (~100 lines)** — REDUCIBLE to a `_partials/investigation_steps.md.j2`.
**communication_soft.md.j2 (dormant, 0 consumers, self-documented `:1`)** and
**feedback_dispatcher.md.j2 (53 lines, no `_body` includes it — grep-confirmed)**
are dead/near-dead weight to verify or cut.

### Track Q2 — Worktree parallel execution

| Field | Content |
|---|---|
| Approach | Fix branch leak + correct/remove Layer-3 + tighten merge fence; then simplify the now-rarely-needed stash apparatus |
| Assumption | The 5-layer defense should fire on real contamination, not leak refs or claim isolation it doesn't deliver |
| Evidence | **P1 branch leak**: `cleanup()` (295–316) and `prune_stale()` (1424–1492) never call `git branch -D`; grep confirms zero occurrences in the module. **P1 Layer-3 self-defeat**: `owned-uuids` derives owned set from `_owned_session_uuids` (167–189) which reads ALL `.hm-loop-*` markers; concurrent sessions admit each other's refs at the strict check (2292); code comments admit it (2277–2287). **P2 fence boundary**: `_stash_base_dirty` (1998) + `staged_before` snapshot (2033–2036) run OUTSIDE `_acquire_merge_fence` which wraps only `merge()` (2041–2042) — verified by grep ordering. **P2 squash conflict no-retry**: `merge()` raises on conflict → worktree preserved (2043–2045), conflicted index not reset on success path; scope-guard warn-only (2056). **P2 WSL2 flock**: O_EXCL secondary only triggers on errno (833), not on a real-exclusion probe — silent-success failure mode uncaught. |
| Trade-off | Removing the UUID apparatus loses a claimed (but non-functional) isolation layer; must document marker-exists as the real boundary |
| Compatibility | Branch-cleanup is additive; fence widening matches ADR-005's own data-flow diagram (`PLAN-...-defense.md:248-252`) |
| Risk | medium (touches the contamination-defense core; needs careful test coverage) |

**Over-engineering / unnecessary steps:**
- `.hm-session-uuid` file (`worktree.py:752-795`) — **vestigial**, superseded by
  dirname-embedded UUIDs per ADR-004's own text; only a legacy fallback, never
  cleaned up. Removable.
- Triple-duplicated porcelain-path parsing (433–438, 686–695, 725–729) — collapse
  to one `_porcelain_path(line)` helper (the comments themselves worry about drift).
- **`prune_stale` on the create hot path does too much**: `_stash_content_in_head`
  (1378–1421) does `1 + N_tracked + 1 + N_untracked` git calls *per stale ref*,
  synchronously, before the worktree even exists.

**Hot-path latency on `create`:** happy path (clean base, migrated gitignore, no
stale refs) ≈ **5 git subprocess calls** (`worktree prune`, `worktree list`,
`status`, `branch --list`, `worktree add`). First-ever/unmigrated create balloons
to **17+** (the `git check-ignore` ×12 subsumption loop at 1821) + 3·per-stale-ref.
The `check-ignore`×12 (batchable via `--stdin`) and the per-ref
`_stash_content_in_head` walk are the two avoidable spikes.

### Track Q3 — Step manifest display

| Field | Content |
|---|---|
| Approach | One shared `_partials/step_manifest.md.j2` included at head of 4 wrapper templates, loop-suppressed |
| Assumption | Users want to see the plan before a multi-step command runs; LLM can echo its own Procedure headings |
| Evidence | No command/skill announces steps today (every stage jumps straight to Phase/Step 0 — research:101, spec:39, plan:77, execute:65, review:78, wrapup:51, verify:43). Headings are regular and extractable (`^#{2,4} (Phase|Step|Check)` with em-dash titles). Composition forks in synthesize.py into 3 wrappers: atomic (`atomic_command.md.j2`, synthesize.py:174), fused (`workflow_command.md.j2`, synthesize.py:477 + workflow_fuse.py:68), codex (`stage_skill.md.j2`/`workflow_skill.md.j2`, synthesize.py:614+). |
| Trade-off | No single injection point covers all surfaces (architecture forks Claude-atomic / Claude-fused / Codex); needs the partial in 4 wrappers + a loop guard |
| Compatibility | Prompt-level "echo your headings" needs zero new extraction code, survives template edits (matches "LLM judgment over rules" principle); shifts all snapshots (mechanical regen needed) |
| Risk | low (UX), but the loop-suppression guard is load-bearing |

Alternative considered: put the instruction in the **stage body** — rejected
because a fused workflow would then print 2–4 separate manifests interleaved with
execution instead of one upfront manifest. Putting it in the **wrappers** yields
one combined manifest per command.

## ⚠️ Pitfalls

- **The 5-term gate / Gate-0 receipt are `{% if is_codex %}`-doubled in source.**
  Only one branch renders, so de-duplication does NOT reduce *runtime* tokens for
  those `{% if %}` halves — it reduces source/maintenance burden and the
  *rendered* duplication across stages. Don't conflate the two when estimating
  savings.
- **Gate-0 receipt is almost always a runtime no-op** (only fires under autoloop
  with `.current-iter`). Its cost is context tokens (the explanatory paragraph),
  not execution — frame the cut accordingly.
- **Step-manifest under autoloop is the trap.** `/hm:loop` re-reads and runs the
  workflow file every iter (loop.md.j2:761); a wrapper-level manifest would
  re-emit ×iterations and violate the non-stopping/low-chatter rail (loop.md.j2:
  21–22). Must gate off under loop dispatch.
- **Step-manifest vs early-exit semantics.** verify stops at first FAIL; spec/plan
  /execute have Step-0 skip heuristics. Word the manifest as "steps you *intend*
  (conditional)", not "steps you *will* perform", or it contradicts skip/early-exit.
- **Removing Layer-3 UUID apparatus must not silently weaken the contamination
  defense narrative.** The marker-exists check (2306) is what actually gates the
  pop today; document that explicitly so a future reader doesn't "restore" the
  broken strict mode (recurrence precedent: this defense is already on its 3rd
  incident per CLAUDE.md).
- **Finalize squash-merge surfaces conflicts on files the worktree never touched**
  (`[wiki:gotcha] worktree-finalize-conflicts-with-parallel-main-edits`, 118-file
  case observed) and **does not retry after manual resolution** — any "improve
  parallel finalize" work must account for this manual-recovery reality.
- **`build_test_hints` may be advertised but not wired.** execute Purpose mentions
  it (17) but Phase D (259) just says `<test command>` — verify it actually
  narrows scope before claiming it as a latency mitigation.

## ❓ Open Questions (for /hm:plan to lock)

1. **Q1 scope:** ship all three sub-items (fragment extraction + memory cache +
   loop.md slimming) as one PLAN, or three? Fragment extraction touches every
   stage snapshot; memory-cache needs an invalidation design; loop.md slimming
   touches the autoloop-driver skill contract.
2. **Memory-cache invalidation:** where does the per-slug `memory_retrieve` result
   live (RESEARCH frontmatter? a sidecar?) and when is it stale (mtime? slug
   change? new memory writes since)?
3. **Q2 priority/sequencing:** branch-leak fix is isolated and safe — ship alone
   first? Or bundle with the Layer-3 correction (riskier, touches defense core)?
4. **Layer-3 decision:** *fix* (thread the current session's single UUID through
   `owned-uuids`) or *remove* (delete the apparatus, document marker-exists as the
   boundary)? Both are defensible; the PLAN must pick one.
5. **Stash-apparatus simplification:** is the ~600-line stash/post-commit-pop
   machinery worth keeping as a safety net now that the base is kept clean by
   design, or can stage-only mode commit at finalize to drop the deferred-pop
   handshake entirely?
6. **Q3 surfaces:** include the manifest in Codex skill wrappers too (3rd surface)
   or Claude-only for v1? And: skills excluded entirely, or limited to the
   multi-gate ones (security-scanner 5 gates, verify-before-completion 5 checks)?
7. **Snapshot churn:** all three tracks shift rendered output + `content_hash`;
   confirm the snapshot-regen + boundary-advisory release flow can absorb it.

## 📚 Sources

All internal (codebase audit; no external libraries involved). Primary evidence
files:
- `src/harness_maker/templates/stages/{research,spec,plan,execute,review,wrapup,verify}.md.j2`
- `src/harness_maker/templates/commands/hm/{atomic_command,workflow_command,loop}.md.j2`
- `src/harness_maker/templates/skills/*/SKILL.md.j2`
- `src/harness_maker/templates/agents/*_body.md.j2` + `_partials/*.j2`
- `src/harness_maker/worktree.py` (2433), `autoloop_driver.py`, `iter_receipts.py`
- `src/harness_maker/{render,synthesize,workflow_fuse}.py`

## 🔗 Related Internal Docs

- [[PLAN-worktree-cross-session-data-loss-defense]] — the 5-layer defense (Layer-3 origin)
- [[PLAN-worktree-base-artifact-pollution]] — keep-base-clean (ADR-005 ref-drain)
- [[PLAN-worktree-finalize-stash-isolation]] — stash envelope + handed_off ordering
- [[REVIEW-worktree-phantom-path-2026-05-31]] — most recent worktree review
- `[wiki:gotcha] worktree-finalize-conflicts-with-parallel-main-edits` — no-retry-after-resolution
- `[wiki:pattern] worktree-finalize-stash-isolation` — handed_off-before-cleanup invariant
