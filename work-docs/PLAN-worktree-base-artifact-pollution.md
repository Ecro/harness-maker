---
type: plan
task_slug: worktree-base-artifact-pollution
status: complete
created: 2026-05-28
tags: [harness-maker, plan, python, worktree, git, gitignore, parallel-sessions]
research_doc: "[[RESEARCH-worktree-base-artifact-pollution]]"
interview_rounds: 1
adrs: 5
validator_outcome: NEEDS_REVISION_RESOLVED
summary: "Keep base clean (gitignore churn + filter alignment + deliverable commit + orphan-ref drain) so the 5-layer defense goes quiet."
---

# PLAN — Worktree base-repo artifact pollution

## 🎯 Executive Summary

**TL;DR.** Parallel `/hm:execute` across sessions is blocked not by a race but by the harness polluting its own base repo. Every session writes churn files (telemetry on *every* tool call, observability, iter-receipts, loop-context) that git can see; that dirt makes finalize stash on every run (→ queue-guard blocks next `create`) and trips the dirty-base guard directly for files outside `.claude/`. The fix is to **keep the base clean** so the existing 5-layer defense stops firing in normal operation — not to add a 6th layer.

**What.** Five levers, all locked via interview:
1. **gitignore the churn** (Lever 1, ADR-002) — surgically ignore harness-generated churn dirs, leave deliverables trackable.
2. **align the finalize filter** (Lever 2, ADR-003) — broaden `_is_harness_artifact` to the churn subdirs so users who *commit* `.claude/` also stop getting spurious stashes (gitignore can't hide tracked-file edits).
3. **commit the deliverables** (Lever 3, ADR-004) — wrapup also `git add`s RESEARCH + SPEC, so they stop lingering uncommitted and dirtying the base.
4. **drain orphan stash-refs** (Lever 4, ADR-005) — `prune_stale` removes ref files whose underlying stash object is gone (nothing to restore = safe).
5. **auto-migrate + correct docs** (Lever 5) — `_ensure_gitignore_entry` appends the new patterns on next `create` (zero user action); fix stale CLAUDE.md claims.

**Why.** User pain: "마음놓고 병렬로 /hm:execute 를 못하겠어 — 자꾸 stash warning." Root cause confirmed in RESEARCH: `telemetry.py:216` writes `.claude/observability/metrics-{date}.jsonl` on every `PostToolUse` (hooks.json.j2:18), and the two dirt-filters disagree (finalize filter forgives only 3 prefixes; create filter forgives all of `.claude/`; neither forgives `work-docs/`). The dogfood repo is already clean *only* because of a hand-rolled `.gitignore` (`.gitignore:13,24`) — downstream user repos get only 4 appended patterns and are unprotected.

**Key Decisions:** ADR-001 (keep-base-clean strategy, retain 5 layers), ADR-002 (surgical gitignore boundary), ADR-003 (filter-alignment scope), ADR-004 (deliverable commit), ADR-005 (orphan-ref drain).

**Estimated impact.** `src/harness_maker/worktree.py` (filters + gitignore helper + prune), `templates/stages/wrapup.md.j2` (git add line 265), CLAUDE.md, CHANGELOG. ~150 LOC + ~10 test cases. No public CLI signature change. The dogfood repo sees no behavior change (its blunt gitignore already subsumes the new patterns — `_ensure_gitignore_entry` no-ops via `git check-ignore` subsumption).

## 📚 Prior Work

- [[RESEARCH-worktree-base-artifact-pollution]] — 4-agent audit of every base writer; the per-writer tables and 3 approaches (keep-clean / relocate-writes / merge-tree-plumbing). This PLAN implements Approach A (keep-clean).
- [[PLAN-worktree-cross-session-data-loss-defense]] — the 5-layer defense (queue-guard, dirty-base-guard, session-UUID, merge-fence, scope-guard). This PLAN makes those layers near-dormant by removing the self-inflicted dirt that triggers them; layers stay as a net.
- [[PLAN-worktree-finalize-stash-isolation]] — why the base-side stash exists (`merge --squash` runs in base index). The narrow `_is_harness_artifact` filter (worktree.py:375-399) and its intentional design comment (worktree.py:609-617, "finalize-stash must preserve genuine user `.claude/` edits") constrain ADR-003.
- memory `[wiki:architecture] worktree-artifact-janitor` (2026-05-25) — `prune_stale` already runs at `_cli_create` (worktree.py:1530); this PLAN extends its ref-drain (ADR-005), not introduces it.
- memory `[wiki:gotcha] worktree-finalize-untracked-loss` — gitignored files written *inside* a worktree are lost at finalize (squash is tracked-only + cleanup --force). Confirms deliverables must be written to the **base** `work-docs/` (research/plan/review already do this), so gitignoring churn is compatible with the base-write discipline.

## 🎙️ Interview Transcript

| # | Topic | Category | Question | Choice | → ADR |
|---|-------|----------|----------|--------|-------|
| 1 | Churn mechanism | Architecture | gitignore / filter-align / both | **Both** (gitignore + filter alignment) | ADR-002, ADR-003 |
| 2 | Deliverable handling | Contract | wrapup-commit / gitignore / leave | **wrapup git-adds RESEARCH+SPEC** | ADR-004 |
| 3 | Orphan stash-ref drain | Failure/Risk | prune_stale ext / +health / manual | **prune_stale extension** | ADR-005 |
| 4 | Migration for installed harnesses | Phasing | ensure-append / make / health | **`_ensure_gitignore_entry` auto-append on create** | ADR-002 §migration |

**Defensible defaults (not separately interviewed — determined by the principle "ignore churn, commit deliverables" + the preserve-user-`.claude` constraint):**
- Exact gitignore pattern set (ADR-002) — enumerated from the RESEARCH audit.
- Filter-alignment boundary (ADR-003) — churn subdirs only, NOT all of `.claude/`, because worktree.py:609-617 must keep preserving genuine user `.claude/` edits during finalize stash.
- `.claude/memory/` split — machine tiers (`semantic/`, `episodic/`, `profile/`, `*.lock`) are regenerable churn → ignored; human tiers (`wiki.md`, `failures.md`, `session/*.md`) stay committed (wrapup already adds them).
- Telemetry stays project-scoped under `.claude/observability/` (just gitignored), NOT relocated to `~/.cache/` — keeps per-project `/hm:health` inspection contract intact (rejected alternative in ADR-001).
- 5-layer defense retained as a safety net (RESEARCH Q6 — common-ground; removing layers would re-open the data-loss path the user called "절대 X").

## 📐 Architecture Decision Records

### ADR-001: Keep-base-clean strategy; retain the 5-layer defense as a dormant net
**Status:** Accepted (2026-05-28, via /hm:plan interview #1)
**Context:** The 5-layer cross-session defense treats symptoms (stash queue, dirty base, merge race). The disease is the harness dirtying its own base on every session, which makes those layers fire constantly. Adding a 6th layer compounds the noise; removing the trigger silences it.
**Decision:** Eliminate the self-inflicted base dirt (Levers 1-4) so that in normal operation `git status --porcelain` is clean → `_stash_base_dirty` returns `None` (worktree.py:419-422) → no stash → no queue pressure → no guard warnings. Keep all 5 layers unchanged as a safety net for genuine user dirt and real races.
**Consequences:**
- ✅ Parallel `/hm:execute` "just works" when the user has no genuine uncommitted work.
- ✅ The defense layers stop producing false-positive warnings but still protect real incidents.
- ⚠️ A user with genuine uncommitted base work still hits the dirty-base guard — correct behavior, not a regression.
**Rejected alternatives:**
- Add a 6th guard layer — Rejected: compounds noise; doesn't remove the trigger.
- Relocate telemetry/observability to `~/.cache/harness-maker/` — Rejected: breaks per-project `/hm:health` inspection; bigger surgery (Approach B in RESEARCH); gitignore achieves the clean-base goal with far less risk.
- Switch finalize to `git merge-tree`/`commit-tree` plumbing (no base index touch) — Rejected: base is checked out on the target branch, so advancing the ref still needs the working tree updated (RESEARCH Approach C blocker).
**Source:** Interview #1.

### ADR-002: Surgical gitignore of harness churn; deliverables stay trackable; auto-migrate on create
**Status:** Accepted (2026-05-28, via interview #1 Q1+Q4)
**Context:** No `.gitignore` template ships (render.py:1081-1086); only 4 patterns are ever appended. Downstream repos therefore see all churn in `git status`. The dogfood repo avoids this with a blunt hand-rolled gitignore (ignores all `.claude/` + `work-docs/`), but that is incompatible with downstream users who want PLAN/REVIEW/RESEARCH/SPEC + human memory committed (wrapup.md.j2:265 `git add`s them).
**Decision:** Append a **surgical** churn set via the existing idempotent `_ensure_gitignore_entry` (worktree.py:1677, which already subsumption-skips when a broader pattern like `.claude/` is ignored). Add a consolidated `_ensure_harness_gitignore(base)` that appends every churn pattern; call it once at the top of `_cli_create` (auto-migration for existing installs, zero user action) and from the render pass for new installs.

**IGNORE (churn — regenerable, per-session):**
- `.claude/observability/` (metrics, security, adaptive, dashboard, docs_index, review/verify logs, cg-marks, orphans)
- `.claude/.hm-iter-receipts/`
- `.claude/loop-specs/`
- `.claude/.hm-render-manifest.jsonl` (validator W1 — render.py:1061/1089 writes it to `.claude/`; render.py:1081-1086 explicitly flags it as not-yet-gitignored. This PLAN closes that deferral.)
- `.claude/memory/semantic/`, `.claude/memory/episodic/`, `.claude/memory/profile/`, `.claude/memory/**/*.lock`
- `work-docs/loop-context/`
- `work-docs/p5-batch-state.yaml`
- (already present: `.claude/.hm-loop-*`, `.claude/.hm-finalize-stash-*`, `.claude/.hm-session-uuid`, `.backup-*/`, `.worktrees/`)

**DO NOT ignore (deliverables — trackable, committed by wrapup):**
- `work-docs/PLAN-*.md`, `work-docs/REVIEW-*.md`, `work-docs/RESEARCH-*.md`
- `specs/SPEC-*.md`, `specs/SPEC-*.machine.yaml`
- `.claude/memory/wiki.md`, `.claude/memory/failures.md`, `.claude/memory/session/*.md`, `.claude/memory/pending-*.md`

**Consequences:**
- ✅ Downstream `git status` is clean of churn → no spurious stash, no dirty-base block.
- ✅ Deliverables + human memory remain in git.
- ✅ Dogfood repo unaffected (`.claude/`+`work-docs/` already ignored at dir level → `_ensure_gitignore_entry` subsumption no-ops; `git check-ignore` guard at worktree.py:1690-1697).
- ⚠️ Existing installs only get the patterns on their *next* `worktree create`; until then the finalize-filter alignment (ADR-003) covers them.
- ⚠️ Patterns must be paths git can ignore even when already tracked is NOT possible — a user who already committed `.claude/observability/` keeps it tracked (gitignore won't untrack); ADR-003 covers that case.
**Rejected alternatives:**
- Blunt `work-docs/` + `.claude/` ignore (dogfood style) — Rejected: un-commits deliverables; conflicts with wrapup git add.
- Ship a full `.gitignore` template at make — Rejected as the *primary* mechanism (only helps re-rendered repos); folded in as the new-install path on top of the create-time auto-migration.
**Source:** Interview #1 Q1, Q4.

### ADR-003: Filter alignment — both filters recognize churn subdirs only, never all of `.claude/`
**Status:** Accepted (2026-05-28, via interview #1 Q1; scope expanded to both filters per validator W2)
**Context:** gitignore cannot hide modifications to *tracked* files. A user/team that commits churn to git will keep seeing it dirty. Two distinct symptoms for committed churn:
1. **committed `.claude/` churn** (e.g. `M .claude/observability/...`) → the **create** filter `_is_create_guard_harness_artifact` (worktree.py:618-633) already forgives ALL of `.claude/`, so it does NOT block `create`; but the **finalize** filter `_is_harness_artifact` (worktree.py:375-399, intentionally narrow per worktree.py:609-617) DOES stash it.
2. **committed `work-docs/loop-context/` or `work-docs/p5-batch-state.yaml` churn** → NEITHER filter forgives `work-docs/`, so it both **blocks** `create` (create guard) AND gets stashed (finalize). This is the only sub-case that actually blocks parallel execute (validator W2).

The finalize filter must NOT be broadened to all of `.claude/` — worktree.py:609-617 deliberately keeps it narrow so genuine user `.claude/` edits (custom agents/skills/commands) are preserved by the stash, not silently merged.
**Decision:** Introduce a shared `_HARNESS_CHURN_PREFIXES` tuple and have BOTH filters recognize it:
- `_is_harness_artifact` (finalize) recognizes `_HARNESS_CHURN_PREFIXES` IN ADDITION to its current 3 prefixes (`.claude/.hm-loop-`, `.claude/.hm-finalize-stash-`, `.worktrees/`) — union, not equality.
- `_is_create_guard_harness_artifact` (create) already forgives all `.claude/`; it additionally recognizes the **`work-docs/` churn members** of `_HARNESS_CHURN_PREFIXES` so committed `work-docs/loop-context/` + `p5-batch-state.yaml` stop blocking `create`.

`_HARNESS_CHURN_PREFIXES` (the shared tuple):
- `.claude/observability/`, `.claude/.hm-iter-receipts/`, `.claude/loop-specs/`, `.claude/.hm-session-uuid`, `.claude/.hm-render-manifest.jsonl`
- `.claude/memory/semantic/`, `.claude/memory/episodic/`, `.claude/memory/profile/`, any `*.lock` under `.claude/memory/`
- `work-docs/loop-context/`, `work-docs/p5-batch-state.yaml`

This is strictly a subset of `.claude/` + the two `work-docs/` churn paths — it does NOT forgive `.claude/agents/`, `.claude/skills/`, `.claude/commands/`, `.claude/hooks/`, `.claude/harness.yaml`, or `work-docs/{PLAN,REVIEW,RESEARCH,SPEC}`.
**Consequences:**
- ✅ Committed-churn users: `work-docs/` churn no longer blocks `create`; `.claude/` + `work-docs/` churn no longer stashed at finalize.
- ✅ Genuine user `.claude/agents` edits are still stashed/preserved (worktree.py:609-617 invariant intact).
- ✅ Defense-in-depth: protects even when gitignore is absent or subsumed; NON-DESTRUCTIVE (no `git rm --cached`, honoring CLAUDE.md git policy).
- ⚠️ Residual (accepted limitation): a user who committed `.claude/` churn still sees cosmetic `M .claude/observability/...` in `git status` (gitignore can't untrack; we deliberately do NOT auto-`git rm --cached`). It neither blocks nor stashes, so it does not impair parallel execute. Documented in CLAUDE.md with an OPTIONAL manual `git rm --cached -r .claude/observability/ …` one-liner the user may run if they want a clean status.
- ⚠️ The churn-prefix tuple is a manual-maintenance list; a new churn dir must be appended to `_HARNESS_CHURN_PREFIXES` once (both filters + the gitignore set derive from it). Phase 2 sync test asserts the gitignore pattern set ⇔ `_HARNESS_CHURN_PREFIXES` (NOT ⇔ the legacy 3-prefix `_HARNESS_ARTIFACT_PREFIXES`, which is recognized as a union).
**Rejected alternatives:**
- Broaden `_is_harness_artifact` to all of `.claude/` (mirror the create filter) — Rejected: would stop preserving genuine user `.claude/` edits during finalize stash (worktree.py:609-617).
- Auto `git rm --cached` migration for tracked churn (validator W2 alt; sandbox-fixture precedent PLAN-…-data-loss-defense ADR-007) — Rejected: destructive-adjacent (mutates index, records deletions in the user's next commit); violates CLAUDE.md "never run destructive git unless explicitly requested". Filter alignment solves the *blocking* case non-destructively; the cosmetic residual is an accepted, documented limitation with an opt-in manual command.
- gitignore only, no filter change — Rejected: leaves committed-churn users exposed (interview Q1 chose "both").
**Source:** Interview #1 Q1; worktree.py:609-617 design constraint; validator W2.

### ADR-004: wrapup commits RESEARCH + SPEC deliverables
**Status:** Accepted (2026-05-28, via interview #1 Q2)
**Context:** wrapup.md.j2:265 stages only `.claude/memory/ + PLAN + REVIEW`. RESEARCH (`work-docs/RESEARCH-{slug}.md`) and SPEC (`specs/SPEC-{slug}.md` + `.machine.yaml`) are written to the base by their stages and never committed → they linger as untracked dirt outside `.claude/`, blocking the next `worktree create` (the create filter forgives `.claude/` but not `work-docs/` or `specs/`).
**Decision:** Extend the wrapup `git add` (line 265) to also stage, with the same `2>/dev/null` tolerance:
`{{ config.work_docs.dir }}RESEARCH-{slug}.md {{ config.spec.dir }}SPEC-{slug}.md {{ config.spec.dir }}SPEC-{slug}.machine.yaml`
**Consequences:**
- ✅ RESEARCH/SPEC land in git as deliverables (symmetric with PLAN/REVIEW); base stops being dirtied by them after wrapup.
- ✅ In the dogfood repo (work-docs/ + specs trackability varies) the `2>/dev/null` swallows a gitignored-add no-op — no behavior change.
- ⚠️ A RESEARCH/SPEC with no matching file (slug ran plan-only) → glob misses → harmless no-op.
**Rejected alternatives:**
- gitignore RESEARCH/SPEC as scratch — Rejected: they are deliverables the user wants in history.
- Leave as-is — Rejected: they keep blocking parallel create.
**Source:** Interview #1 Q2.

### ADR-005: `prune_stale` drains orphan stash-refs whose stash object is gone
**Status:** Accepted (2026-05-28, via interview #1 Q3)
**Context:** A finalize-stash ref file can outlive its git stash (stash dropped/gc'd). Found live: `.claude/.hm-finalize-stash-execute-85d4064c848f-20260525T0223Z` (May 25) with `git stash list` empty. `prune_stale`'s `_stash_content_in_head` (worktree.py:1298-1341) returns `False` when the stash commit object is missing (`git cat-file -e {ref_sha}^{commit}` fails) and the caller biases toward retention → such refs are preserved forever. This matches memory `[wiki:gotcha] orphan-stash-registration-drain-manual` ("indrainable by automation").
**Decision:** Distinguish two cases in the prune ref-drain, keyed STRICTLY on object presence (validator W4 — do not reason about drop-vs-gc):
1. **Stash commit object truly ABSENT** (`git cat-file -e {ref_sha}^{commit}` fails) → the object is gone from the object DB and is, by definition of that check, unrecoverable (a merely-dropped-but-reflog-present stash still RESOLVES, so `cat-file -e` SUCCEEDS and this branch does NOT fire). Nothing to restore can exist → **safe to delete the ref file** (record in `PruneReport.removed_stash_refs`). This is NOT a `git stash drop` (no object to drop), so the ADR-008 "never drop without diff preview" contract is not engaged.
2. **Stash object resolvable** (present, OR dropped-but-reflog-recoverable) but content not provably in HEAD → **preserve + warn** (unchanged current behavior — biases to retention).
Add a helper `_stash_object_exists(base, ref_sha) -> bool` wrapping `git cat-file -e {ref_sha}^{commit}`; the drain removes the ref when the object is absent OR (object present AND `_stash_content_in_head`).
**Consequences:**
- ✅ Dead ref files stop accumulating; queue-pressure forensics stay accurate.
- ✅ ADR-008 user-consent-before-drop contract untouched (only applies to resolvable stashes).
- ✅ A dropped-but-still-reflog-recoverable stash is PRESERVED, not drained (the `cat-file -e` succeeds in that window) — no recoverable work is ever lost.
- ⚠️ A ref whose object is truly absent is pure cruft (git itself can no longer produce the content); deleting the ref file loses nothing.
**Rejected alternatives:**
- Reason about "dropped vs gc'd / 90-day grace" to drain more aggressively — Rejected (validator W4): the only sound predicate is object-presence; a dropped stash is still reflog-recoverable and must be preserved.
- Also add a periodic `/hm:health` drain — Rejected for now (interview Q3 chose prune_stale extension only; create-time janitor already runs `prune_stale`); can be a follow-up.
- Manual-only (status quo) — Rejected: leaves cruft the user must hand-clean.
**Source:** Interview #1 Q3; validator W4.

## 🏗️ Technical Design

### Current State
- `worktree.py:375-399` `_is_harness_artifact` — narrow finalize filter (3 prefixes).
- `worktree.py:618-633` `_is_create_guard_harness_artifact` — create filter (+ all `.claude/`).
- `worktree.py:402-451` `_stash_base_dirty` — stashes when `git status --porcelain` (filtered by the narrow filter) is non-empty.
- `worktree.py:1677-1739` `_ensure_gitignore_entry` — idempotent single-pattern append with `git check-ignore` subsumption guard.
- `worktree.py:1298-1341` `_stash_content_in_head` + `worktree.py:1344+` `prune_stale` — create-time janitor; biases to retention when stash object missing.
- `templates/stages/wrapup.md.j2:265` — `git add .claude/memory/ <wd>PLAN-{slug}.md <wd>REVIEW-{slug}-*.md 2>/dev/null`.
- `render.py:1081-1086` — comment: no gitignore template ships.

### Affected Components
| Component | Change |
|-----------|--------|
| `src/harness_maker/worktree.py` | New `_HARNESS_CHURN_PREFIXES` shared tuple; `_is_harness_artifact` recognizes it (ADR-003); new `_ensure_harness_gitignore(base)` consolidating all churn patterns (ADR-002) wired into `_cli_create` top; `_stash_object_exists` + prune drain change (ADR-005). |
| `src/harness_maker/render.py` | Call `_ensure_harness_gitignore` at render pass for new installs (ADR-002); update the render.py:1081-1086 comment (the `.hm-render-manifest.jsonl` gitignore deferral it describes is now closed). |
| `src/harness_maker/templates/stages/wrapup.md.j2` | Extend git add line 265 with RESEARCH + SPEC + machine.yaml (ADR-004). (Template root is `src/harness_maker/templates/`, not repo-root `templates/`.) |
| `CLAUDE.md` | Correct phantom "/hm:health 24h cleanup" + "3 patterns" → 4; document the churn gitignore set + filter alignment in `## Multi-session worktree`. |
| `CHANGELOG.md` | `[Unreleased]` entry. |
| tests | unit: filter recognizes churn / preserves user `.claude/agents`; gitignore-set ↔ filter-set sync; prune drains missing-stash ref, preserves present-stash-not-in-HEAD; snapshot: wrapup git add line. |

### Dependencies
None added.

### Data Flow (post-fix, normal session)
```
session writes telemetry/observability/iter-receipts/loop-context
  → all covered by gitignore (ADR-002) → git status --porcelain CLEAN
worktree create (parallel session)
  → _ensure_harness_gitignore(base)   # auto-migrate (ADR-002)
  → prune_stale(base)                 # drains dead refs (ADR-005)
  → _has_user_dirty_state → False     # nothing user-dirty → no block
finalize
  → _stash_base_dirty: status clean (or churn recognized by ADR-003) → None → NO stash
wrapup
  → git add memory + PLAN + REVIEW + RESEARCH + SPEC (ADR-004) → base clean after commit
```

### API Changes
None (internal helpers only; no CLI signature change).

## 📝 Implementation Plan

### Phase 1 — gitignore consolidation + auto-migration (Lever 1 + Lever 5)
- **depends_on:** []
- **parallel_group:** serial-worktree-py
- **merge_hazards:** `src/harness_maker/worktree.py` (shared with Phases 2, 4)
- **Scope (in):** `worktree.py` — define `_HARNESS_CHURN_PREFIXES` (shared tuple) and `_HARNESS_GITIGNORE_PATTERNS` (derived from it); add `_ensure_harness_gitignore(base)` looping `_ensure_gitignore_entry` over the churn patterns; call it in `_cli_create` **immediately after the `_detect_existing_worktree` early-return (~worktree.py:1522) and before `prune_stale`/the queue+dirty guards (~1533)** — NOT literally at function top, so the nested-reuse no-op path is excluded. `render.py` — call `_ensure_harness_gitignore` at render pass + update the 1081-1086 comment. Unit test: patterns appended once, idempotent, subsumption no-op when `.claude/` already ignored.
- **Known window (accepted):** auto-migration fires at `create`, but telemetry dirties the base on the FIRST `PostToolUse` of the FIRST session — so a brand-new install's very first session can see one dirty-base/stash event before the gitignore lands. Acceptable because ADR-003 filter-alignment is UNCONDITIONAL (covers untracked churn at finalize/create regardless of gitignore state), so the window is benign. Noted, not mitigated further.
- **Scope (out):** filter change, wrapup, prune.
- **Exit criterion:** `uv run pytest tests/unit/test_worktree*.py -k gitignore -v` GREEN; in a tmp repo, `create` appends the churn patterns; second `create` is a no-op; with `.claude/` dir-ignored, no `.claude/...` lines appended (subsumption).
- **Risk:** low (additive, idempotent, subsumption-guarded).
- **Rollback point:** revert Phase 1 commit.

### Phase 2 — filter alignment, both filters (Lever 2)
- **depends_on:** [1]  (true symbol dependency — reuses `_HARNESS_CHURN_PREFIXES` from Phase 1)
- **parallel_group:** serial-worktree-py
- **merge_hazards:** `src/harness_maker/worktree.py`
- **Scope (in):** `worktree.py` — (i) `_is_harness_artifact` (finalize) additionally returns True for `_HARNESS_CHURN_PREFIXES` (union with the legacy 3 prefixes); (ii) `_is_create_guard_harness_artifact` (create) additionally returns True for the **`work-docs/` members** of `_HARNESS_CHURN_PREFIXES` (it already forgives all `.claude/`). Unit tests: (a) only churn dirty → `_stash_base_dirty` returns None (no stash); (b) genuine `.claude/agents/foo.md` edit → still treated as dirt (stashed) AND still blocks `create` — the preserve-user-`.claude` guard; (c) `work-docs/PLAN-*.md` → still dirt (both filters); (d) committed `work-docs/loop-context/x.yaml` modified → does NOT block `create` (create filter) AND not stashed (finalize filter); (e) **sync guard** — assert the gitignore pattern set ⇔ `_HARNESS_CHURN_PREFIXES` (NOT ⇔ the legacy `_HARNESS_ARTIFACT_PREFIXES`, which is a union member).
- **Scope (out):** wrapup, prune.
- **Exit criterion:** `uv run pytest tests/unit/test_worktree*.py -k "filter or artifact or churn or sync" -v` GREEN; the (b) preserve-user-`.claude/agents` test passes; the (d) committed-work-docs-churn test passes.
- **Risk:** medium — must not over-broaden and swallow genuine user `.claude/` edits (worktree.py:609-617). The (b) test is the guard.
- **Rollback point:** Phase 1.

### Phase 3 — wrapup commits RESEARCH + SPEC (Lever 3)
- **depends_on:** []
- **parallel_group:** parallel-templates  (different file from Phases 1/2/4 — can land concurrently)
- **merge_hazards:** snapshot fixtures for wrapup render (none vs worktree.py)
- **Scope (in):** `templates/stages/wrapup.md.j2:265` — extend git add with `{{ config.work_docs.dir }}RESEARCH-{slug}.md {{ config.spec.dir }}SPEC-{slug}.md {{ config.spec.dir }}SPEC-{slug}.machine.yaml` (keep `2>/dev/null`). Re-render `.claude/commands/hm/wrapup.md`. Update wrapup snapshot test (assert both Codex and non-Codex render forms).
- **Scope (out):** worktree.py.
- **Exit criterion:** `uv run pytest -k "wrapup and (render or snapshot)" -v` GREEN; rendered wrapup contains the RESEARCH + SPEC paths in the add line.
- **Risk:** low (template + snapshot).
- **Rollback point:** revert Phase 3 commit.

### Phase 4 — orphan stash-ref drain (Lever 4)
- **depends_on:** [1]  (file-serialization only — `_stash_object_exists`/prune does NOT use `_HARNESS_CHURN_PREFIXES`; logically orderable before Phase 1, sequenced here purely to avoid worktree.py merge conflicts)
- **parallel_group:** serial-worktree-py
- **merge_hazards:** `src/harness_maker/worktree.py`
- **Scope (in):** `worktree.py` — `_stash_object_exists(base, ref_sha)`; prune ref-drain removes the ref when the stash object is absent OR (present AND `_stash_content_in_head`); record in `PruneReport.removed_stash_refs`; keep preserve+warn for present-but-not-in-HEAD. Unit tests: (a) ref with missing/gc'd stash → drained; (b) ref with present stash + content NOT in HEAD → preserved + warned; (c) ref with present stash + content in HEAD → drained (existing behavior).
- **Scope (out):** /hm:health drain (follow-up).
- **Exit criterion:** `uv run pytest tests/unit/test_worktree*.py -k "prune or drain or orphan" -v` GREEN; the live May-25 ref scenario (missing stash) drains.
- **Risk:** low-medium — must not drain a ref whose stash still exists with un-landed content (case (b) test guards).
- **Rollback point:** Phase 1.

### Phase 5 — CLAUDE.md correction + CHANGELOG (Lever 5 docs)
- **depends_on:** [1, 2, 3, 4]
- **parallel_group:** serial-docs
- **merge_hazards:** CLAUDE.md, CHANGELOG.md
- **Scope (in):** CLAUDE.md `## Multi-session worktree` — remove the false "weekly cleanup hook (`/hm:health` Step 2) cleans 24h stale worktrees" claim (no such code; `prune_stale` runs only at `_cli_create`); correct "3 GITIGNORE_PATTERN constants" → 4; document the churn gitignore set + filter alignment + orphan-ref drain. CHANGELOG `[Unreleased]`.
- **Scope (out):** code.
- **Exit criterion:** CLAUDE.md no longer references a 24h health cleanup; CHANGELOG entry present; `grep -c "weekly cleanup" CLAUDE.md` reflects the correction.
- **Risk:** low.
- **Rollback point:** Phase 4.

## 🧪 Testing Strategy
- **Unit (worktree.py):** churn-only-dirty → no stash; genuine `.claude/agents` edit → stashed; gitignore-set ↔ filter-set sync; gitignore idempotent + subsumption; prune drains missing-stash ref + preserves present-not-in-HEAD.
- **Snapshot:** wrapup render contains RESEARCH+SPEC in git add (Codex + non-Codex).
- **Integration (`INTEGRATION=1`, optional):** two tmp-repo sessions both `create → finalize` with only churn present → neither stashes, neither blocks; assert `git stash list` empty and no queue-guard abort. Reuse `tests/integration/test_worktree_parallel_session.py` pattern.
- **Manual:** in a fresh non-dogfood repo (no blunt gitignore), run `/hm:execute` twice in parallel → confirm no stash warning, no dirty-base block.

## ⚠️ Risks & Mitigation
| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Filter over-broadens, swallows genuine user `.claude/` edits | low | high | Phase 2 test (b) asserts `.claude/agents/` edit still stashed; churn prefixes are a strict subset. |
| gitignore-set and filter-set drift over time | medium | medium | Single shared `_HARNESS_CHURN_PREFIXES`; sync unit test (Phase 2). |
| Existing install not re-rendered → no gitignore until next create | medium | low | ADR-003 filter alignment is unconditional and covers the gap; auto-append fires on next `create`. |
| Draining a ref whose stash holds un-landed work | low | high | ADR-005 only drains when the stash object is **truly absent** (`cat-file -e` fails → unrecoverable by definition; a dropped-but-reflog-present stash still resolves → preserved). |
| Already-committed `.claude/` churn stays tracked (gitignore no-op) → cosmetic `M` in status | medium | low | ACCEPTED LIMITATION (ADR-003): create filter forgives all `.claude/` (no block); finalize filter forgives churn (no stash); only cosmetic noise remains. NON-destructive by choice — CLAUDE.md offers an opt-in manual `git rm --cached`. |
| Committed `work-docs/` churn (loop-context/p5-batch-state) blocks create | low | medium | ADR-003 adds `work-docs/` churn members to the create filter — non-destructive fix. |
| wrapup git add of gitignored RESEARCH/SPEC errors | low | low | `2>/dev/null` swallows; glob miss is harmless. |

## ✅ Success Criteria
- [x] Churn dirs (incl. `.claude/.hm-render-manifest.jsonl`) gitignored via consolidated `_ensure_harness_gitignore`, auto-appended at `create` after the existing-worktree early-return, subsumption-safe (Phase 1).
- [x] BOTH filters recognize churn: `_is_harness_artifact` (finalize) + `work-docs/` churn in `_is_create_guard_harness_artifact` (create); NEITHER swallows genuine user `.claude/` assets (Phase 2).
- [x] gitignore-set ⇔ `_HARNESS_CHURN_PREFIXES` sync test GREEN (Phase 2).
- [x] wrapup commits RESEARCH + SPEC (Phase 3).
- [x] `prune_stale` drains refs whose stash object is truly absent; preserves dropped-but-reflog-recoverable (Phase 4).
- [x] CLAUDE.md corrected (phantom 24h health cleanup removed; 3→4 patterns) + opt-in `git rm --cached` note; CHANGELOG entry (Phase 5).
- [x] In a non-dogfood repo, parallel `/hm:execute` produces no stash warning and no dirty-base block (manual).
- [x] Full suite GREEN (`uv run pytest tests/ -q`, ruff, mypy).

## 🔍 Plan Validation

**Pass 1 outcome:** NEEDS_REVISION (4 warnings + 2 suggestions, 0 critical — core strategy sound; worktree.py:609-617 design constraint respected). All resolved by revision (no re-validation required for warnings-only per stage protocol).

| # | Sev | Finding | Resolution |
|---|-----|---------|------------|
| W1 | warning | Churn set omits `.claude/.hm-render-manifest.jsonl` (render.py:1061/1089 writes it; 1081-1086 flags it un-ignored) | Added to gitignore set (ADR-002) + `_HARNESS_CHURN_PREFIXES` (ADR-003); Phase 1 updates the render.py comment. |
| W2 | warning | Tracked-churn migration gap — gitignore can't untrack committed churn; `work-docs/` churn actually BLOCKS create | ADR-003 expanded to BOTH filters (create filter now forgives `work-docs/` churn) → blocking case fixed non-destructively. Auto `git rm --cached` REJECTED (violates CLAUDE.md git policy); cosmetic `.claude/` residual documented as accepted limitation + opt-in manual command. |
| W3 | warning | "_ensure at top of _cli_create" imprecise; first-session-before-migration window | Phase 1 specifies exact insertion point (after `_detect_existing_worktree` early-return ~1522, before prune/guards ~1533); first-session window documented as benign (filter-alignment unconditional). |
| W4 | warning | ADR-005 reasoning muddled ("90-day gc/drop") — a dropped stash is still reflog-recoverable | ADR-005 reasoning tightened: drain ONLY when `cat-file -e` fails (object truly absent); dropped-but-reflog-present is PRESERVED. Added that as a Phase 4 unit test. |
| S1 | suggestion | Sync-test ambiguity (churn-set vs legacy 3-prefix) | Phase 2 (e) test asserts gitignore-set ⇔ `_HARNESS_CHURN_PREFIXES`; legacy `_HARNESS_ARTIFACT_PREFIXES` is a union member, not asserted equal. |
| S2 | suggestion | Phase 4 `depends_on [1]` conflates file-serialization with symbol dependency | Phase 4 note clarifies it is a merge_hazard (same-file) constraint, not a symbol dependency. |

Also fixed: component-table template path (`templates/` → `src/harness_maker/templates/`).
