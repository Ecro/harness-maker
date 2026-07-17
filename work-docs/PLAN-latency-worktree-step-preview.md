---
type: plan
task_slug: latency-worktree-step-preview
status: planning
created: 2026-05-31
tags: [harness-maker, plan, jinja2, worktree, latency, parallel-execution, step-preview]
research_doc: "[[RESEARCH-latency-worktree-step-preview]]"
interview_rounds: 3
adrs: 6
validator_outcome: NEEDS_REVISION_RESOLVED
summary: "Risk-phased: dedup partials + step-manifest + loop slim (low) ; worktree bug-fixes + L3-removal (isolated, last)"
---

# PLAN — Command/Skill/Agent Latency · Worktree Parallelism · Step-Manifest

## 🎯 Executive Summary

**What:** Three independent improvement tracks bundled into one risk-phased PLAN.
- **Q1 (latency/token):** kill cross-stage duplication — parameterized shared partials for the 5-term gate (×3) and Gate-0 receipt (×4+), extract `loop.md`'s P5-batch path, dedupe agent reviewer prose, add a per-slug memory-retrieve cache.
- **Q2 (worktree parallelism):** fix two confirmed correctness bugs (orphan branch leak, merge-fence boundary) + hot-path latency, then remove the self-defeating Layer-3 UUID apparatus.
- **Q3 (step-manifest):** every command echoes its intended steps before starting; loop-suppressed.

**Why:** The dominant token waste is *duplication re-read every invocation*, not any single expensive step. The worktree subsystem has two confirmed correctness bugs and a defense layer that does not deliver the isolation it claims. No command announces its plan to the user.

**Key decisions:** asymmetric finalize with a thin deferred-pop fallback (ADR-001); remove Layer-3, marker-exists is the boundary (ADR-002); prompt-level step-manifest (ADR-003); parameterized stage-shared partials (ADR-004); sidecar memory cache (ADR-005); P5-batch extraction with per-iter rails retained (ADR-006).

**Estimated impact:** ~175 duplicated template lines removed (Q1); ~150–250 worktree lines removed (Q2, honest estimate after the compensating-control choice — not the 600 a full removal would yield); one new user-visible behavior (step manifest). Two confirmed worktree bugs fixed.

## 📚 Prior Work

- `[[RESEARCH-latency-worktree-step-preview]]` — the five-agent line-by-line audit this PLAN executes against. Two highest-stakes worktree claims (branch leak, fence boundary) were grep-verified.
- `[wiki:gotcha] worktree-finalize-conflicts-with-parallel-main-edits` — squash-merge surfaces conflicts on untouched files; finalize does NOT retry after manual resolution; recovery uses `git branch -D <wt-branch>` (itself proof of the orphan-branch leak).
- `[wiki:architecture] worktree-keep-base-clean-churn-isolation` — `_HARNESS_CHURN_*` single-source-of-truth; the finalize filter must stay a STRICT SUBSET; `.gitignore` itself must be non-dirtying. Constrains ADR-002 + ADR-005.
- `[wiki:fresh-install-health-baseline]` — grep `render.py` for merge semantics already present before designing migration (FileSystemLoader root confirms stage `{% include %}` is feasible).
- `[wiki:model-routing-multi-ide]` — `--update` cwd guard rejects worktree-internal snapshot regen.

## 🎙️ Interview Transcript

| # | Round | Topic | Category | Question | Choice | Note | → ADR |
|---|---|---|---|---|---|---|---|
| 1 | 1 | Packaging | Scope | One PLAN vs split by risk | **One PLAN, risk-phased** | low-risk first, Q2 isolated/revertible last | — |
| 2 | 1 | Q2 aggressiveness | Scope | Bug-fixes-only vs +apparatus simplification | **Fixes + apparatus simplification** | overrode my bug-fixes-only recommendation | ADR-001/002 |
| 3 | 1 | Layer-3 | Architecture | fix / remove / document | **Fix: thread UUID** (later superseded) | reconciled in Round 2 | ADR-002 |
| 4 | 1 | Q3 surfaces | Contract | which IDE surfaces carry the manifest | **Claude + Codex commands**, skills excluded | — | ADR-003 |
| 5 | 2 | Apparatus shape | Architecture | asymmetric / keep+fix / symmetric-abort | **Asymmetric** | supersedes #3: Layer-3 moot under deferred-pop removal | ADR-001/002 |
| 6 | 2 | Memory-cache | Dependencies | include vs defer | **Include with mtime invalidation** | sidecar storage chosen at design (W4) | ADR-005 |
| 7 | 3 | Defense risk-accept | Risk | accept abort / +compensating control / reconsider | **Accept + compensating control** | retain thin deferred-pop for rare stage-only dirt; L3 still removed | ADR-001/002 |

Validator pass (MAJOR_REVISION) resolutions folded in: see `## 🔍 Plan Validation`.

## 📐 Architecture Decision Records

### ADR-001: Asymmetric worktree finalize with thin deferred-pop fallback
**Status:** Accepted (2026-05-31, via /hm:plan interview)
**Context:** The stash/post-commit-pop apparatus exists to handle a base-dirty state that keep-base-clean now actively prevents; it is dormant on a clean base (`_stash_base_dirty` early-returns `None`, worktree.py:480). Bugs (fence boundary) lurk in its rarely-exercised paths.
**Decision:** Success-mode (commits at finalize) keeps the immediate `stash→merge→pop→commit` envelope unchanged. Stage-only mode normally does nothing (clean base); on **genuine** base dirt it falls back to a minimal transparent deferred-pop (the retained `_cli_post_commit_pop` + stash-ref file). The merge fence is widened to wrap `_stash_base_dirty` + the `staged_before` snapshot + `merge()` (currently the stash runs OUTSIDE the fence, worktree.py:1998/2033 vs 2041).
**Consequences:**
- ✅ Graceful handling of the rare stage-only-dirty case retained (compensating control, Interview #7).
- ✅ Merge-fence boundary bug fixed — no parallel-finalize stash race.
- ⚠️ Smaller line reduction than a full removal (~150–250 vs ~600); the deferred-pop plumbing stays.
- ⚠️ The thin deferred-pop path must still be guarded against cross-session contamination — by the marker-exists check (ADR-002), not the removed UUID layer.
**Rejected alternatives:**
- Full abort-on-dirt (symmetric) — Rejected: user chose a compensating control over halting the loop on dirt (Interview #7).
- Keep-deferred-and-thread-UUID — Rejected: threading a working UUID through a path the marker-exists check already gates is redundant work (Interview #5).
**Source:** Interview #2, #5, #7

### ADR-002: Remove the self-defeating Layer-3 UUID apparatus; marker-exists is the boundary
**Status:** Accepted (2026-05-31, via /hm:plan interview)
**Context:** Layer-3 strict mode (`owned-uuids` CLI) builds the "owned" session set from ALL live `.hm-loop-*` markers (shared filesystem, `_owned_session_uuids` worktree.py:167-189), so concurrent sessions admit each other's stash refs at the strict check (2292). The code's own comments admit this (2277-2287). It never delivered isolation.
**Decision:** Remove `_owned_session_uuids`, `_session_owns_marker`, `_cli_owned_uuids`, the `HM_OWNED_SESSION_UUIDS` plumbing, and the `_current_session_uuid` **writer** (the ref-file `session` field is derived from the wt-name dirname UUID instead). The retained (rare) deferred-pop is guarded by the existing marker-exists check (2306) — the honest boundary. **Keep** `.claude/.hm-session-uuid` in `_HARNESS_CHURN_FILES`/`_HARNESS_GITIGNORE_PATTERNS` (worktree.py:88,95) so legacy on-disk files stay ignored and `test_worktree_churn_pollution.py:174`'s sync invariant stays green.
**Consequences:**
- ✅ Removes a layer that contributed nothing (was self-defeating) + its dead side-channels.
- ✅ Honest boundary documented; no false sense of isolation.
- ⚠️ Of the 5-layer defense, the remaining live protections are: queue-guard, dirty-base-guard, widened merge-fence (ADR-001), scope-guard, and marker-exists. These cover the original incident classes (cross-session pop contamination is gated by marker-exists; concurrent finalize by the fence; stash-queue pileup by queue-guard). L3 is the only removed layer and it never functioned.
- ⚠️ The `.hm-session-uuid` gitignore pattern persists for a file the harness no longer writes (cosmetic; covers legacy repos).
**Rejected alternatives:**
- Fix L3 by threading the current session's UUID — Rejected: redundant with marker-exists once deferred-pop is rare (Interview #5).
- Document-only, no code change — Rejected: leaves dead, misleading apparatus in place.
**Source:** Interview #3, #5, #7

### ADR-003: Step-manifest is prompt-level, injected via shared partial, loop-suppressed
**Status:** Accepted (2026-05-31, via /hm:plan interview)
**Context:** No command announces its steps today; users can't see what `/hm:plan` or `/hm:wrapup` will do before it runs. Procedure headings are regular and LLM-extractable.
**Decision:** Add `templates/agents/_partials/step_manifest.md.j2` instructing the LLM to echo its own top-level `Step`/`Phase`/`Check` headings as a numbered manifest of **intended (conditional)** steps before starting. Include it at the head of the 4 command wrappers: `commands/hm/atomic_command.md.j2`, `commands/hm/workflow_command.md.j2`, `codex/stage_skill.md.j2`, `codex/workflow_skill.md.j2`. Suppress when `.hm-loop-active` exists at project root (the loop re-reads workflow files per iter, loop.md.j2:761 — an un-suppressed manifest would flood the transcript ×iterations). Skills excluded.
**Consequences:**
- ✅ One injection mechanism reaches all 3 IDE targets; zero new extraction code; survives template edits.
- ⚠️ "Intended (conditional)" wording is load-bearing — must not collide with Step-0 skip heuristics or verify's early-FAIL stop.
- ⚠️ Shifts all 4 wrapper snapshots (mechanical regen).
**Rejected alternatives:**
- Render-time static heading extraction — Rejected: new Python pass, breaks on template edits, against "LLM judgment over rules" (CLAUDE.md).
- Put it in stage bodies — Rejected: fused workflows would print 2–4 interleaved manifests instead of one upfront.
**Source:** Interview #4

### ADR-004: Parameterized stage-shared partials for the 5-term gate + Gate-0 receipt
**Status:** Accepted (2026-05-31, via /hm:plan interview)
**Context:** The 5-term inequality gate (research/spec/plan) and Gate-0 receipt (all 7 stages) are duplicated. **Verified the copies have DRIFTED** (distinct md5 per stage) — they differ by stage name (`--stage <x>`) and per-stage term wording, so they are NOT byte-identical.
**Decision:** Create `templates/agents/_partials/inequality_gate_block.md.j2` (named to disambiguate from the existing `inequality_gate.py`) and `templates/agents/_partials/gate0_receipt.md.j2`. Both **parameterized**: the receipt takes a `stage` variable for `--stage <name>`; the gate takes per-stage term-impact wording (e.g. "change research direction" vs "change PLAN content") as a parameter. Record the canonical text in this ADR; per-stage deltas become explicit `{% include %}` arguments. These are the first stage-shared partials (partials were agent-only before; `render.py` FileSystemLoader root makes `{% include %}` mechanically feasible).
**Consequences:**
- ✅ ~175 duplicated lines removed; single source of truth for gate + receipt.
- ⚠️ Exit criterion is "snapshot diff limited to the recorded convergence set" — NOT "byte-identical" — because the copies had drifted and the partial forces convergence.
**Rejected alternatives:**
- Keep duplicated — Rejected: the duplication is the dominant cross-stage token waste.
**Source:** RESEARCH Q1; validator Warning 5.

### ADR-005: Per-slug memory-retrieve cache in a gitignored sidecar
**Status:** Accepted (2026-05-31, via /hm:plan interview)
**Context:** `memory_retrieve --k 6 --pre-k 30` reranks the same 30→6 candidates in research, spec, and plan for one slug. RESEARCH already proves the caching pattern (its `sources`/`libs_fetched` are reused by execute).
**Decision:** Cache the retrieval result in a sidecar `.claude/.hm-memory-cache/<slug>.json` (NOT frontmatter — avoids bloating the committed deliverable with volatile data). Invalidation: the JSON stores a stamp of `.claude/memory/{wiki,failures}.md` mtimes at write time; a downstream stage reuses the cache iff those files have not changed since, else re-ranks. Reverse-mapper: the cache reader in `memory_retrieve.py`. Add `.claude/.hm-memory-cache/` to `_HARNESS_CHURN_DIRS` (gitignored + dirt-filter forgiven — shares the `_HARNESS_CHURN_*` surface with ADR-002).
**Consequences:**
- ✅ Eliminates 2 redundant reranks per slug chain; deliverable docs stay clean.
- ⚠️ New `.claude/` sidecar — MUST be in the churn set or it dirties the base (keep-base-clean invariant).
- ⚠️ mtime-comparison logic needs a deterministic test (mocked mtime + frozen clock).
**Rejected alternatives:**
- Store in RESEARCH/PLAN frontmatter — Rejected: bloats committed deliverables; multi-doc-YAML + snapshot-determinism friction (validator Warning 4).
- Defer entirely — Rejected: user chose to include it (Interview #6).
**Source:** Interview #6; validator Warning 4.

### ADR-006: Extract loop.md P5-batch path; per-iter behavioral rails stay in-body
**Status:** Accepted (2026-05-31, via /hm:plan interview)
**Context:** `loop.md.j2` is 1156 lines re-read ≤50× per loop. P5-batch (≈97 lines, loop.md.j2:1044-1141) is a fully separate code path entered only when the goal starts with `p5-batch`.
**Decision:** Extract the P5-batch path to its own command file. **Keep ALL per-iter behavioral rails in `loop.md` body** — the non-stopping discipline (13-40) and forbidden-halt table (556-588) are load-bearing per-iter and MUST always be in context during a loop; they are NOT moved to the autoloop-driver skill (skills load conditionally).
**Consequences:**
- ✅ ~97 lines off the per-iter context for normal loops.
- ⚠️ New command file + dispatch path; loop e2e must still pass.
- ⚠️ Conservative: only the dead-path P5-batch moves; doctrine stays. Larger extractions deferred.
**Rejected alternatives:**
- Move behavioral doctrine to the skill — Rejected: would remove always-in-context rails the loop depends on per-iter.
**Source:** RESEARCH Q1 (loop.md analysis).

## 🏗️ Technical Design

**Current state:** Stage templates carry duplicated gate/receipt blocks; `worktree.py` (2433 lines) has the orphan-branch leak (no `git branch -D` anywhere — grep-confirmed), the merge-fence boundary gap (stash outside fence), the self-defeating L3 apparatus, and a heavy create hot-path (`check-ignore`×12, per-ref `_stash_content_in_head` walk); no command prints a step manifest.

**Affected components:**
- Templates: `stages/*.md.j2`, `commands/hm/{atomic_command,workflow_command,loop}.md.j2`, `codex/{stage_skill,workflow_skill}.md.j2`, `agents/*_body.md.j2` + new `_partials/{inequality_gate_block,gate0_receipt,step_manifest,investigation_steps}.md.j2`.
- Python: `worktree.py`, `memory_retrieve.py`, snapshot/render plumbing.
- Skills/docs: `worktree-isolator`, `autoloop-driver` SKILLs; `CLAUDE.md` §Multi-session worktree + 5-layer table.

**Dependencies / parallelization (answers the user's "perfect parallel execution" interest):** two independent chains that `/hm:execute` can run in parallel worktrees —
- **Chain A (templates):** P1 → P2 → P3 → P4 → P5 (serial; all regen snapshots — `--update` cwd guard forbids worktree-internal regen, so snapshot phases must serialize).
- **Chain B (worktree):** P6 → P7 (serial; P7 builds on P6's bug-fixed module).
- **Cross-link:** P7 edits `execute.md.j2` (Step 5) + `wrapup.md.j2` (Step 7.5), which P1 also edits (Gate-0 receipt) → P7 `depends_on=[6, 1]`.
- **Execution-mode note (post-validation, set at /hm:execute):** the dogfood snapshot infra pins `_HARNESS_MAKER_PKG_ROOT` to the main checkout (`tests/unit/conftest.py:36-40`), so the template chain (P1–P5) cannot be soundly snapshot-verified inside a worktree (`[fail:snapshot-regen-inside-worktree]`). Per user decision, the chains run as **two sequential passes in different modes**: template chain (P1–P5) in the **base checkout**, worktree chain (P6–P7) in **worktree isolation**. Because the chains are now sequential (not parallel), the P5↔P7 churn-constant collision that the parallel-safety fix guarded against is moot, so the `.hm-memory-cache/` churn-dir registration is kept in **P5** (where the feature lives) and P5 `depends_on=[4]`. Pass order: template chain first (satisfies P7's `depends_on=[1]`), worktree chain second (branches from a base already carrying P5's churn-set change).

**Design decisions:** all architectural choices trace to ADR-001…006 above.

## 📝 Implementation Plan

### Phase 1 — Parameterized shared partials (Q1 dedup)  ✅ DONE (2026-05-31, base checkout)
> **Execution note:** Gate-0 receipt extracted to `_partials/gate0_receipt.md.j2` (parameterized by `gate0_heading`/`gate0_stage`/`gate0_pass`/`gate0_fail`/`gate0_standalone`/`gate0_extra_note`) and wired into all 7 stages — golden-master diff confirms **byte-identical** rendered output (pure dedup). **Finding that revises ADR-004 + RESEARCH:** the 5-term inequality gate was NOT "byte-for-byte ×3 duplication" — auditing the three copies showed they have **drifted into genuinely stage-specific prose** (heading, intro, skip-note, term-1/2 suffixes, term-3 frontmatter list, term-4/5 endings, F6 comment length, render-checklist note all differ). Only the canonical **formula block + locale line** (md5 `8120d84e`, identical across all 3) is true duplication; it was single-sourced into `_partials/inequality_gate_block.md.j2`. The drifted prose stays inline (it is not duplication). Verified: ruff clean, snapshot + structural tests pass (no regen needed — output unchanged), codex branch + StrictUndefined-safety checked.
- `depends_on`: `[]`
- `parallel_group`: `serial-templates`
- `merge_hazards`: all 7 stage snapshots; `render-manifest` content_hash; **`execute.md.j2` + `wrapup.md.j2` are also edited by Phase 7** (receipt block) — record so P7 serializes.
- Scope (in): create `_partials/inequality_gate_block.md.j2` + `_partials/gate0_receipt.md.j2` (ADR-004); replace 3 gate copies + 4+ receipt copies with parameterized includes. (out): no behavioral wording change beyond recorded convergence.
- Exit: snapshot regen produces a diff limited to the recorded convergence set (drift between copies resolved to canonical text); `uv run pytest` + `mypy --strict` + snapshot regen green. *(run pytest in background per project policy.)*
- Risk: `low`
- Rollback: revert phase (no prior phase needed).

### Phase 2 — Step-manifest partial (Q3)  ✅ DONE (2026-05-31, base checkout)
> **Execution note:** `_partials/step_manifest.md.j2` created (prompt-level "outline your plan" preamble, `.hm-loop-active`-suppressed, framed "intended, conditional") and `{% include %}`'d into all 4 wrappers (atomic_command, workflow_command, codex stage_skill, codex workflow_skill). Verified: new structural test `tests/structural/test_step_manifest_injection.py` (6 cases, test-reviewer PASS) GREEN; render check confirms manifest present in atomic + workflow commands, **absent from skills and from the loop driver**, references the suppression marker; 8 snapshots regenerated; ruff + format clean.
- `depends_on`: `[1]`
- `parallel_group`: `serial-templates`
- `merge_hazards`: snapshots for `atomic_command`, `workflow_command`, `codex/stage_skill`, `codex/workflow_skill`.
- Scope (in): `_partials/step_manifest.md.j2` (ADR-003) + include at head of the 4 wrappers + `.hm-loop-active` suppression guard + "intended (conditional)" wording. (out): skills; `loop.md` body manifest.
- Exit: rendered commands begin with the manifest instruction; a fast unit/snapshot test asserts loop-dispatch (`.hm-loop-active` present) suppresses it; snapshots regen green.
- Risk: `low`
- Rollback: revert to Phase 1 state.

### Phase 3 — Extract loop.md P5-batch path (Q1 loop slim)  ✅ DONE (2026-05-31, base checkout)
> **Execution note:** three sub-tasks landed. (1) **Formula fold** — `loop.md.j2:323-329` now `{% include %}`s `inequality_gate_block.md.j2` (golden-diff byte-identical; resolves Phase-1 REVIEW P2 — the formula is now truly single-sourced across research/spec/plan/loop). (2) **Driver-ignore backstop** — the per-iter workflow-dispatch step (~756) now tells the loop driver to IGNORE the step-manifest preamble it reads inline (resolves Phase-2 REVIEW P1 #2). (3) **P5-batch extraction (full parity, user-chosen)** — `commands/hm/loop-p5-batch.md.j2` (claude `/hm:loop-p5-batch`) + `codex/loop_p5_batch_skill.md.j2` (codex `hm-loop-p5-batch`), both registered in `synthesize.py` (`_base_files` + `_codex_target_files` with a shared `p5_batch_body` render); `loop.md.j2` reduced to a dispatch pointer. **Per-iter rails (non-stopping discipline, self-pause prohibition) STAY in loop.md** (ADR-006). loop.md: ~1156 → 1029 lines (−127). Verified: new `test_loop_p5_batch_extraction.py` (4 cases) GREEN, codex path renders, mypy + ruff + format clean, snapshots regenerated (file_count 59→60).
- `depends_on`: `[2]`
- `parallel_group`: `serial-templates`
- `merge_hazards`: `loop.md.j2` snapshot; new P5-batch command snapshot.
- Scope (in): move P5-batch (loop.md.j2:1044-1141) to its own command file; keep all per-iter rails in `loop.md` (ADR-006); **fold the 4th inequality-formula copy at `loop.md.j2:323-329` into `{% include "agents/_partials/inequality_gate_block.md.j2" %}`** (Phase-1 REVIEW P2 manual-only finding — `loop.md.j2` holds a byte-identical copy; golden-diff verify the include renders identically); **add a belt-and-suspenders instruction at the loop's per-iter workflow-dispatch step (~761) telling the driver to IGNORE the step-manifest preamble it reads inline — "you are the loop driver; never print the manifest"** (Phase-2 REVIEW P1 #2 — the loop ingests the workflow file inline, so suppression should not rest solely on the marker check; P1 #1's precise marker-resolution fix already landed in the manifest in Phase 2). (out): non-stopping discipline / forbidden-halt doctrine (stays).
- Exit: P5-batch reachable via the new command (named snapshot test for the new file); `loop.md` ~97 lines shorter; a fast unit test asserts main-loop dispatch still resolves the workflow file. Slow loop e2e (`tests/e2e/test_plugin_live.py`) deferred to one gated `INTEGRATION=1` run at end of Chain A.
- Risk: `medium`
- Rollback: revert to Phase 2 state.

### Phase 4 — Agent prose dedup (Q1 agents)  ❌ CANCELLED (2026-05-31, user-approved at execute)
> **Why cancelled:** execute-stage investigation found Phase 4 does not serve the Q1
> latency goal and conflicts with a locked ADR. (1) **~Zero runtime-token saving** — both
> targets are *always-rendered* agent content; a `{% include %}` partial re-expands at render
> time, so the rendered `code-reviewer.md` (and the 3 second-opinion agents) stay the same
> size → the subagent prompt is unchanged. Phase 4 would only shrink *source* lines
> (maintainability), not per-invocation tokens. (2) **ADR-009 conflict** — the 5-reviewer
> "Investigation Steps" substrings are a LOCKED contract (`test_reviewer_prompts_contain_agentic_depth_clauses`
> asserts them in each body *source*; ADR-009 says removing them needs a superseding ADR).
> Deduping to a partial supersedes ADR-009 — a /hm:plan governance decision, not an execute
> phase. (3) `second_opinion_codex` is **untested** (only e2e sandbox configs) and renders
> only when `codex_second_opinion.enabled`. Net: low/no value, real cost. Skipped per user
> decision; the source-maintainability dedup can be revisited as its own ADR-superseding unit
> if ever worth it.
- `depends_on`: `[3]`
- `parallel_group`: `serial-templates`
- `merge_hazards`: 5 reviewer-body snapshots; `code-reviewer`/`consensus-arbiter`/`plan-validator` snapshots (second_opinion includers).
- Scope (in): extract the `second_opinion_codex` bash recipe to a referenced `.claude/lib/` snippet keeping only per-agent output-contract deltas inline; extract the duplicated 5-reviewer "Investigation Steps" block into `_partials/investigation_steps.md.j2`. (out): **`communication_soft` (CLAUDE.md dormant-ship — keep) and `feedback_dispatcher` (live via atomic_command:4 + workflow_command:72 — keep)** are explicitly NOT removed.
- Exit: agent render byte-equivalent minus the recorded dedup; snapshots regen green; `second_opinion_codex` still renders correctly when `codex_second_opinion.enabled`.
- Risk: `medium`
- Rollback: revert to Phase 3 state.

### Phase 5 — Memory-retrieve sidecar cache (Q1)  ❌ CANCELLED (2026-05-31, user-approved at execute)
> **Why cancelled:** the cache has no redundancy to eliminate (broken premise, like P4).
> (1) **Stages query different topics** — research uses the free-form research topic, spec
> "the SPEC topic", plan "the task slug" (verified in the three stage templates). So the
> lexical prefilter yields *different* candidate sets per stage; there is no shared 30→6
> rerank to cache. A slug-keyed cache would miss every stage, or serve research's topic-6 to
> plan's slug-query (wrong results). (2) **memory_retrieve does only the cheap lexical
> prefilter** (no anthropic call by design); the expensive 30→6 rerank happens *inline in the
> consuming LLM turn*, which a Python sidecar cannot capture — so caching memory_retrieve's
> output saves file-read + token-scoring (cheap Python), not LLM tokens (the Q1 goal). The
> only mechanism that would save the rerank is an LLM write-back keyed by (slug+topic), which
> requires stages to share a query — and unifying the query would degrade research's
> rich-topic retrieval. Net: no real saving + new churn-file surface. Skipped per user.
>
> **Q1 track outcome:** P1 (gate0/inequality dedup) + P2 (step-manifest) + P3 (loop slim) are
> the real wins — committed, reviewed A. P4 + P5 cancelled: their RESEARCH-estimated savings
> didn't survive mechanism-level inspection (P4: always-rendered content re-expands via the
> partial → 0 runtime saving; P5: stages query different topics → no rerank redundancy).
> Lesson: token-saving estimates from a fast audit must be mechanism-verified before planning.
- `depends_on`: `[4]` (Chain-A serial order; churn-dir reg is self-contained here under sequential execution — see Execution-mode note).
- `parallel_group`: `serial-templates`
- `merge_hazards`: `research/spec/plan` stage templates; `memory_retrieve.py`; `worktree.py` `_HARNESS_CHURN_DIRS` constant; `test_worktree_churn_pollution.py`. (Safe because the worktree chain runs in a LATER sequential pass branched from this change — no parallel merge.)
- Scope (in): sidecar `.claude/.hm-memory-cache/<slug>.json` + mtime-stamp invalidation (ADR-005); reuse logic in research/spec/plan; the cache reader/writer in `memory_retrieve.py`; add `.claude/.hm-memory-cache/` to `_HARNESS_CHURN_DIRS` + update the sync test. (out): frontmatter storage.
- Exit: spec/plan reuse the cache when `{wiki,failures}.md` not newer than the stamp (test with **mocked mtime + frozen clock**); cache miss re-ranks; `test_worktree_churn_pollution.py` sync invariant green with the new churn dir.
- Risk: `medium`
- Rollback: revert to Phase 4 state.

### Phase 6 — Worktree bug-fixes (Q2, non-envelope)  ⚠️ RE-SCOPED (2026-05-31 at execute): orphan-branch fix → merged into P7
> **Execute-stage finding (orphan-branch fix is NOT separable from P7):** the headline P6
> fix — add `git branch -D` to `cleanup()` — was implemented + RED-tested, then **reverted**
> after verifying a defense-core interaction: `cleanup(on_success=True)` is called by BOTH
> finalize success-mode AND **stage-only** mode (worktree.py:2129), and **execute uses
> stage-only**. In stage-only the work is squash-merged into the base *index* (committed only
> later by wrapup), and the per-worktree branch carries the `wip(execute)` commit that
> CLAUDE.md documents as the **stash-conflict recovery net** (`git reflog --all | grep
> wip(execute)` → cherry-pick). `git branch -D` deletes the branch reflog → breaks that
> recovery for the common autoloop path. Fixing the leak correctly means deleting the branch
> **only after the work is durably committed** (post-wrapup, in the deferred-pop flow) — which
> is exactly the finalize/post-commit-pop machinery **P7 rewrites** (asymmetric finalize). So
> the orphan-branch fix is **folded into P7**, co-designed with the finalize rework, not
> bolted onto cleanup() here. (A success-mode-only delete would leave the common stage-only
> case still leaking — not a real fix.) The RED test (`test_cleanup_on_success_deletes_orphan_branch`)
> is the proof of the leak; re-author it in P7 with the post-commit delete point.
>
> **Remaining P6 items (latency/robustness, independent of the finalize flow) — kept, lower
> priority:** batch `check-ignore` via `--stdin`; move `_stash_content_in_head` off the create
> hot path; collapse triple-duplicated porcelain-path parsing; WSL2 flock positive-exclusion
> probe. These do NOT touch the cleanup/finalize branch flow and can be a small standalone pass
> — but they're polish, not correctness. **Recommendation: do P6-remainder + P7 as one focused,
> fresh pass on worktree.py** (the 3rd-incident defense core deserves un-fatigued attention;
> the orphan-branch + asymmetric-finalize + L3-removal changes are all in the same ~150-line
> region and should be designed coherently).
- `depends_on`: `[]`
- `parallel_group`: `serial-worktree`
- `merge_hazards`: `worktree.py` (NON-finalize-envelope regions only — `cleanup()`, `prune_stale()`, `_ensure_harness_gitignore`, `_cli_create`, `_stash_content_in_head`); worktree tests.
- Scope (in): add `git branch -D <wt-branch>` to `cleanup()` (295-316) + `prune_stale()` (1424-1492) [orphan-branch leak]; batch `check-ignore` via `--stdin` (1821); move `_stash_content_in_head` walk off the create hot path (1378-1421); collapse triple-duplicated porcelain-path parsing (433/686/725) to one helper; add a WSL2 flock positive-exclusion probe (not errno-only, 833). (out): the finalize stash/merge-fence block (deferred to Phase 7 so "revert to Phase 6" is a known-good intermediate); `.hm-memory-cache/` churn-dir registration (done in P5).
- Exit: no orphan branches after finalize (`INTEGRATION=1` test); create-path git-call count measurably reduced; `INTEGRATION=1` worktree suite green.
- Risk: `medium`
- Rollback: revert phase (no prior phase needed).

### Phase 7 — Worktree apparatus simplification (Q2, HIGH-risk, isolated, last)
- `depends_on`: `[6, 1]`
- `parallel_group`: `serial-worktree`
- `merge_hazards`: `worktree.py` finalize-envelope block + L3 functions (disjoint from P6's regions); `execute.md.j2` (Step 5) + `wrapup.md.j2` (Step 7.5) — **both also edited by Phase 1** (hence `depends_on=[1]`); `worktree-isolator` + `autoloop-driver` SKILLs; `CLAUDE.md` §Multi-session worktree + 5-layer table; all worktree tests. (P7 must KEEP `.hm-session-uuid` in `_HARNESS_CHURN_FILES` and *runs* `test_worktree_churn_pollution.py` to confirm sync, but does NOT edit the churn constants — those edits are P6's.)
- Scope (in): implement ADR-001 (asymmetric finalize, thin deferred-pop fallback, widen merge-fence to wrap stash + staged_before + merge) + ADR-002 (remove L3 UUID apparatus: `_owned_session_uuids`, `_session_owns_marker`, `_cli_owned_uuids`, `HM_OWNED_SESSION_UUIDS`, `_current_session_uuid` writer; guard retained deferred-pop with marker-exists; keep `.hm-session-uuid` gitignore pattern); simplify `wrapup.md.j2` Step 7.5 (drop `owned-uuids` call, keep marker-exists pop) + `execute.md.j2` Step 5 (keep deferred fallback, drop UUID plumbing); update both SKILLs + CLAUDE.md. (out): full abort-on-dirt; scope-guard halt-mode promotion (see Non-Goals).
- Exit: `INTEGRATION=1` worktree suite green; success-mode envelope intact; thin stage-only deferred-pop fires only on genuine dirt and is marker-exists-guarded (test); widened fence verified; gated loop e2e green; `test_worktree_churn_pollution.py` sync invariant green; ~150–250 lines removed.
- Risk: `high`
- Rollback: revert to Phase 6 state (Phase 6 deliberately left the envelope block untouched, so this is a known-good intermediate).

## 🧪 Testing Strategy

- **Unit:** snapshot regen for every template phase (P1-P5); loop-suppression assertion (P2); P5-batch dispatch (P3); memory-cache reuse/miss with **mocked mtime + frozen clock** (P5); orphan-branch + porcelain-helper + flock-probe units (P6); marker-exists-guarded deferred-pop + widened-fence + churn-sync units (P7).
- **Integration (`INTEGRATION=1`):** worktree create/finalize/pop lifecycle (P6, P7); cross-session deferred-pop (P7).
- **E2E (gated, one run):** `tests/e2e/test_plugin_live.py` loop dispatch after Chain A completes and after P7.
- Determinism: all mtime/HOME/clock reads isolated (autouse fixture or monkeypatch); snapshot `generated_at` masked.

## ⚠️ Risks & Mitigation

| Risk | Severity | Mitigation |
|---|---|---|
| P7 regresses cross-session contamination defense | high | P7 isolated + last; revert-to-P6 known-good; ADR-002 Consequences enumerate retained layers; INTEGRATION cross-session test |
| P1↔P7 shared-file (execute/wrapup) merge conflict | medium | P7 `depends_on=[1]`; surfaced in both merge_hazards |
| Churn-set drift breaks `test_worktree_churn_pollution.py` | medium | P5 + P7 list the test in merge_hazards; keep `.hm-session-uuid` pattern |
| Gate/receipt copies drifted → non-dedup diff | medium | ADR-004 records canonical text; exit = "convergence diff", not byte-identical |
| Manifest collides with skip-heuristic / early-FAIL | low | "intended (conditional)" wording; loop-suppressed |
| Memory-cache flaky snapshots | low | sidecar (not frontmatter); mocked mtime + frozen clock |

## ✅ Success Criteria

- [ ] Gate + receipt rendered from single parameterized partials; ~175 duplicated lines gone (P1).
- [ ] Every Claude + Codex command echoes its intended steps; suppressed under loop (P2/ADR-003).
- [ ] P5-batch in its own command; per-iter rails retained in loop.md (P3/ADR-006).
- [ ] second_opinion_codex + Investigation-Steps deduped; communication_soft + feedback_dispatcher untouched (P4).
- [ ] Memory cache reused across research/spec/plan with mtime invalidation; in churn set (P5/ADR-005).
- [ ] No orphan branches after finalize; create hot-path lighter (P6).
- [ ] L3 apparatus removed; marker-exists guards the thin deferred-pop; fence widened; churn sync green (P7/ADR-001/002).

## 🔍 Plan Validation

**Validator outcome:** MAJOR_REVISION (pass 1) → all 11 findings resolved → **re-validated once** → NEEDS_REVISION (1 new warning, 0 critical) → resolved (P5↔P7 churn-constant collision serialized by moving the churn-dir edit into P6, P5 `depends_on=[4,6]`). Both original criticals confirmed resolved by the re-run. **Final: NEEDS_REVISION_RESOLVED.**

| Validator finding | Severity | Resolution |
|---|---|---|
| Churn-set sync (`.hm-session-uuid`) unaddressed | critical | ADR-002 keeps the gitignore pattern; P7 merge_hazards add `_HARNESS_CHURN_FILES` + sync test |
| Phase 6/7 share finalize block → "revert to P6" incoherent | critical | Merge-fence fix moved P6→P7; P6 leaves envelope untouched (known-good intermediate) |
| P5↔P1 stage-template collision | warning | Chain A fully serialized (P5 `depends_on=[4]`) under `serial-templates` |
| memory_snapshot determinism / multi-doc YAML | warning | Switched to gitignored sidecar (ADR-005); mocked-mtime + frozen-clock test |
| P1 "byte-identical" not checkable (copies drifted) | warning | Verified drift; ADR-004 parameterizes + records canonical; exit = convergence diff |
| Stale `worktree.py:2047` scope-guard "Phase 7" comment | warning | Non-Goal + P7 fixes the comment (see below) |
| No Non-Goals; communication_soft is dormant-ship | warning | Non-Goals added; communication_soft + feedback_dispatcher kept (verified live/dormant-by-policy) |
| Phase 4 "verify/cut feedback_dispatcher" deferred decision | warning | Pre-resolved: feedback_dispatcher is LIVE (atomic_command:4, workflow_command:72) — kept |
| "loop e2e works" vague | warning | Named fast tests per phase; slow e2e gated to one run |
| ADR-001/002 lack Consequences | warning | Consequences populated; risk explicitly accepted (Interview #7) |
| `inequality_gate.md.j2` vs `inequality_gate.py` collision | suggestion | Renamed `inequality_gate_block.md.j2` |
| (re-run) P5↔P7 churn-constant + sync-test cross-chain collision | warning | Churn-dir registration moved P5→P6; P5 `depends_on=[4,6]`; P7 runs-but-doesn't-edit the sync test |

### Non-Goals
- Full abort-on-dirt worktree behavior (compensating control chosen instead).
- Scope-guard halt-mode promotion (the `worktree.py:2047` comment's "Phase 7" refers to a *prior* plan; P7 only corrects the stale comment, does not promote).
- Memory-cache in frontmatter; 3+-hash heading parsing in `memory_retrieve`.
- Moving loop behavioral doctrine to the autoloop-driver skill.
- Removing communication_soft (dormant-ship per CLAUDE.md) or feedback_dispatcher (live).
- The original ~600-line full apparatus removal (compensating control retains the thin deferred-pop).
