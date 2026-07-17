---
type: plan
task_slug: worktree-deliverable-blocks-create
status: complete
created: 2026-06-12
tags: [harness-maker, plan, python, worktree, dirty-base-guard, branch-cruft]
interview_rounds: 2
adrs: 4
validator_outcome: NEEDS_REVISION_RESOLVED
summary: "Exempt harness deliverables from the create dirty-base guard; SHA-validated landed-marker branch sweep"
---

# PLAN — worktree-deliverable-blocks-create

## 🎯 Executive Summary

**TL;DR:** `/hm:execute` aborts on every run because the `/hm:plan` deliverable
it depends on is uncommitted at `worktree create` time. Fix the create-guard to
forgive harness deliverables per-line (finalize still preserves them), and
replace the fragile branch-cruft sweep with an SHA-validated landed-marker so
74+ leaked `execute-*` branches stop regrowing the warning wall.

**What / Why:**
- The Layer-2 dirty-base-guard (`_has_user_dirty_state` → `_is_create_guard_harness_artifact`, `worktree.py:735/760`) blocks `worktree create` when the base has uncommitted user dirt. Deliverables (`work-docs/PLAN-*.md` etc.) are **deliberately** excluded from the harness-churn set so `/hm:wrapup` can commit them — but execute runs *between* plan and wrapup, so the deliverable is **always** uncommitted at create time. Structural, not incidental: every plan→execute pair trips it.
- Secondary: `_branch_content_in_head` (`worktree.py:1490`) compares *current* blob SHAs; once a landed branch's files are re-edited by later work the comparison never re-matches → the branch is preserved forever → the `[WARN] preserved branch …` wall regrows on every create (74 branches and counting).

**Key Decisions:**
- Forgive deliverables in the **create-guard only**, per-line, anchored full-match pattern; finalize filter untouched (→ ADR-001).
- Branch-cruft fixed in the same PLAN (→ ADR-002).
- Landed-marker = git ref `refs/hm-landed/v1/<branch>` carrying the branch tip SHA; sweep deletes iff `tip == marker_SHA` (→ ADR-003).
- Legacy backlog drained via content-gate fallback + a new `prune-branches [--force]` CLI; orphan refs reaped on every delete path (→ ADR-004).

**Estimated impact:** ~1 module (`worktree.py`) + tests + docs. Unblocks the
core plan→execute workflow; eliminates an unbounded warning wall.

## 📚 Prior Work

- `[fail:design] worktree-finalize-pulls-orphan-wip-into-main` (count:3) — the incident the dirty-base-guard exists to prevent (orphan **code** WIP swept into main). Bounds how far ADR-001 may safely broaden the guard.
- `[wiki:architecture] worktree-keep-base-clean-churn-isolation` — prior fix philosophy "keep the base clean so the defense goes quiet, NOT a 6th layer"; the two-filter asymmetry (create-guard forgives all `.claude/`; finalize is a strict subset). ADR-001 extends the asymmetry, never the finalize subset.
- `[wiki:pattern] fail-safe-direction-when-unifying-divergent-parsers` — for the create-guard, forgiving more = firing less = the **unsafe** direction; ADR-001 carries an explicit safety-direction justification.
- `PLAN-worktree-cross-session-data-loss-defense.md`, `PLAN-worktree-base-artifact-pollution.md`, `PLAN-p6-p7-worktree-finalize.md` — the 5-layer defense + churn-isolation + branch-sweep origins.
- CLAUDE.md global learned-correction 2026-06-08 (absent-case = feature black hole) — drives the non-default `work_docs.dir` Non-Goal in ADR-001 and the `main()` dispatch exit-criterion in Phase 2.

## 🎙️ Interview Transcript

| # | Topic | Category | Question | Choice | Note | → ADR |
|---|-------|----------|----------|--------|------|-------|
| 1 | deliverable blocks create | Architecture | create-guard exemption vs auto-commit vs isolator auto-bypass | create-guard only, per-line deliverable exemption | finalize filter untouched; narrow pattern to bound unsafe direction | ADR-001 |
| 2 | branch-cruft scope | Scope | include in this PLAN? | Yes — landed-detection + cumulative cleanup | | ADR-002 |
| 3 | landed-detection mechanism | Architecture | patch-id (squash-blind) vs landed-marker vs recorded-squash-commit | finalize writes durable landed-marker | patch-id rejected: git cherry sees squash as unmerged | ADR-003 |
| 4 | legacy 74-branch backlog | Risk | auto vs explicit cleanup | content-gated auto fallback + explicit `prune-branches --force` | | ADR-004 |
| 5 (validator follow-up) | marker safety | Risk | CRIT-1 stale-marker → live-branch deletion | revise: record tip SHA, sweep iff tip==marker_SHA | merges the rejected recorded-SHA alt | ADR-003 |
| 6 (validator follow-up) | ref lifecycle | Risk | CRIT-2 orphan refs accumulate | revise: same-op marker delete on all paths + reap orphans | mirrors stash-ref reaping loop | ADR-004 |
| 7 (validator follow-up) | CLI reachability | Failure handling | W1 prune-branches unreachable via main() | revise: add Phase 2 exit (i) dispatch + subprocess test | concurs w/ Codex | ADR-004 |
| 8 (validator follow-up) | marker write-site | Failure handling | W2 SHA source / clean-tree path | revise: tip-after-capture, co-locate in handed_off block | clean-tree finalize creates no wip commit | ADR-003 |

## 📐 Architecture Decision Records

### ADR-001: Create-guard deliverable exemption (per-line, anchored)
**Status:** Accepted (2026-06-12, via /hm:plan interview)
**Context:** `/hm:plan` writes a deliverable to `work-docs/` that `/hm:execute` depends on; deliverables are excluded from the churn set so wrapup can commit them, so they are always uncommitted at `worktree create` time and the dirty-base-guard always blocks.
**Decision:** Add `_is_deliverable_path(path)` — a FULL-MATCH regex `^work-docs/(PLAN|RESEARCH|SPEC|REVIEW)-.+\.md$` OR `^specs/SPEC-.+\.md$`, anchored to mirror the EXACT-match discipline at `worktree.py:84-86`. Wire it into `_is_create_guard_harness_artifact` (`worktree.py:735`) so deliverable porcelain lines are removed **per-line** from `user_lines`. The finalize filter `_is_harness_artifact` (`worktree.py:450`) is **unchanged** — deliverables remain user-dirt there and are stash-PRESERVED at finalize.
**Consequences:**
- ✅ plan→execute no longer self-blocks; no workflow change for the user.
- ✅ Per-line: any non-deliverable dirt (code WIP) still makes `_has_user_dirty_state` return True and `_list_user_dirty_files` lists *only* the code WIP.
- ⚠️ Broadening the create-guard fires it LESS (documented unsafe direction). Bounded by: (a) per-line so code WIP still blocks; (b) anchored full-match pattern (`.bak`/`random.md` siblings NOT forgiven); (c) finalize still preserves the file → no data-loss path opens even for a user hand-authored same-named file.
**Non-Goal (explicit absent-case decision):** A non-default `harness.yaml` `work_docs.dir` is **NOT** covered — the predicate is a pure porcelain-line check with no harness.yaml access, the same accepted limitation as the churn-filter at `worktree.py:88-92`. Documented + a test asserts the skip behavior.
**Rejected alternatives:**
- Auto-commit deliverable at stage end — rejected: breaks the wrapup-commits-deliverables model; orphan commits on abandoned execute; history churn on plan re-run.
- Execute isolator auto-passes `--allow-dirty-base` — rejected: LLM soft-contract; bypasses the *whole* guard, so coexisting code WIP would also be bypassed.
**Source:** Interview #1, #5 hardening.

### ADR-002: Branch-cruft included in this PLAN's scope
**Status:** Accepted (2026-06-12, via /hm:plan interview)
**Context:** The same error output carries a growing `[WARN] preserved branch …` wall (74 leaked `execute-*` branches) alongside the blocking `[ERROR]`.
**Decision:** Address both in this PLAN rather than splitting the cruft into a separate one — they share `worktree.py` and the same user-visible failure surface.
**Consequences:** ✅ One coherent fix. ⚠️ Larger diff; mitigated by serial phases on the shared file.
**Source:** Interview #2.

### ADR-003: SHA-validated landed-marker for branch sweep
**Status:** Accepted (2026-06-12, via /hm:plan interview)
**Context:** `_branch_content_in_head` (`worktree.py:1490`) re-compares current blob SHAs; after a landed branch's files are re-edited it never re-matches → permanent preserve → warning wall. `git branch --merged` / patch-id / git-cherry all fail because finalize **squash-merges** (individual commits become non-ancestors).
**Decision:** On finalize success, write a git ref `refs/hm-landed/v1/<wt_name>` targeting the worktree **branch tip read AFTER `_capture_pending_in_worktree` (`worktree.py:2217`)** — i.e. the `wip(execute)` commit *iff* capture occurred, else the last execute commit. The write co-locates inside the `handed_off` handshake block (`worktree.py:2289-2313`) so a cleanup failure after handoff cannot leave a branch with no marker. `git update-ref` is atomic by default (no `atomic_write` needed — refs are not work-tree files, so zero new gitignore churn). In `prune_stale`, for an owned-prefix branch whose worktree dir is gone: if a `v1` marker exists **AND** `current_branch_tip == marker_SHA` → delete branch + marker unconditionally (provably the same branch we finalized; trust the finalize record, no content re-compare). Else (no marker, or `tip != marker_SHA`) → existing `_branch_content_in_head` content-gate (preserve+warn on mismatch).
**Consequences:**
- ✅ Landed branches sweep cleanly regardless of later HEAD edits.
- ✅ Name-collision safe: a re-created same-named branch has a different tip → marker mismatch → falls to the preserve-biased content-gate (this resolves CRIT-1).
- ✅ Race-safe by construction: the dir-gone-but-marker-not-yet-written window degrades to the content-gate (preserve), and `prune_stale` skips any branch whose worktree dir exists/is registered (`worktree.py:1585`).
- ⚠️ New durable ref state in the user repo — lifecycle owned by ADR-004.
**Rejected alternatives:**
- patch-id / git-cherry — squash-merge makes individual commits non-ancestors → false-preserve.
- bare-marker-presence (first draft) — would authorize deleting a live re-created same-named branch (CRIT-1 unsafe path).
- compare-against-recorded-squash-commit — folded INTO this decision: recording + validating the SHA is exactly the safety this needs.
**Source:** Interview #3, #5, #8 hardening.

### ADR-004: Legacy backlog drain + marker-ref lifecycle + warning summarization
**Status:** Accepted (2026-06-12, via /hm:plan interview)
**Context:** The 74 pre-existing branches predate the marker and cannot be auto-classified safely once their squash-merged files were re-edited. Marker refs must not themselves become a new accumulation wall.
**Decision:**
- Legacy markerless branches route through the `_branch_content_in_head` fallback (un-re-edited → auto-sweep; re-edited squash-merged → preserve+warn — honestly un-auto-classifiable without a marker).
- New CLI subcommand `worktree prune-branches [--force]`, wired into `main()` dispatch (`worktree.py:2645`) + usage string: lists each preserved legacy branch with a `git log -p <branch>` recovery hint; `--force` deletes markerless gone-worktree branches but **prints** the per-branch recovery hint (reflog `wip(execute)` commits survive the gc window per the existing recovery-net). `--force` is parsed explicitly, not via the substring-`in args` idiom.
- Marker-ref lifecycle: every branch-delete path (marker-sweep, content-gate sweep, `--force`) deletes the branch's `refs/hm-landed/v1/<name>` in the same op; `prune_stale` additionally reaps any `refs/hm-landed/v1/*` with no matching branch — mirroring the existing stash-ref reaping loop (`worktree.py:1610-1648`). (Resolves CRIT-2.)
- Multi-branch preserved warnings collapse to ONE summary line + hint (kills the wall).
**Consequences:** ✅ Backlog drainable; refs cannot accumulate; wall removed. ⚠️ `--force` is the only escape for genuinely-diverged legacy branches — made safe via mandatory recovery-hint print, not blind delete.
**Rejected alternatives:** marker backfill for ancestor-of-HEAD legacy tips — rejected: squash-merged branches are not ancestors, so it would not catch the cruft it targets.
**Source:** Interview #4, #6, #7 hardening.

## 🏗️ Technical Design

**Current State:** `worktree.py` create path runs queue-guard → dirty-base-guard
(`_has_user_dirty_state`) → branch-name allocation → `git worktree add`.
`prune_stale` sweeps markers, dangling worktrees, owned branches (content-gated),
and stash refs. `main()` dispatches a fixed subcommand set.

**Affected Components:**
- `src/harness_maker/worktree.py` — `_is_create_guard_harness_artifact`, new `_is_deliverable_path`; finalize (`_cli_finalize`/handoff block ~2289-2313) marker write; `prune_stale` sweep + reaping; `main()` dispatch + new `_cli_prune_branches`.
- `src/harness_maker/templates/stages/execute.md.j2`, `templates/skills/worktree-isolator/SKILL.md.j2` — dirty-base wording (docs only).
- `CLAUDE.md` — Multi-session worktree + Worktree-cleanup sections.
- Tests: `tests/unit/test_worktree*.py`, an integration/e2e subprocess test for `prune-branches`.

**Dependencies:** none added (pure git + stdlib).

**Design Decisions:** every decision above links to ADR-001…ADR-004.

**Data Flow:** plan writes deliverable → execute `worktree create` (deliverable
forgiven per-line) → execute in worktree → finalize squash-merge + write
`refs/hm-landed/v1/<branch>=tip` in the handed_off block → wrapup commits → next
create's `prune_stale` sweeps marked landed branches (tip==marker) + reaps orphan
refs.

**API Changes:** new CLI subcommand `worktree prune-branches [--force]`. No
Python public-API removals.

## 📝 Implementation Plan

### Phase 1 — Create-guard deliverable exemption (ADR-001)
- **depends_on:** `[]`
- **parallel_group:** `serial-guard`
- **merge_hazards:** `worktree.py` (shared with Phase 2 → serial)
- **Scope (in):** `_is_deliverable_path` + wiring into `_is_create_guard_harness_artifact`; unit tests.
- **Scope (out):** branch sweep, finalize, CLI.
- **Exit criterion** (`uv run pytest tests/unit/test_worktree*.py -k deliverable`): (1) lone `work-docs/PLAN-x.md` forgiven → create proceeds; (2) code WIP `src/foo.py` still blocks; (3) mixed → blocks and `_list_user_dirty_files` lists ONLY `src/foo.py`; (4) anti-over-match `work-docs/PLAN-x.md.bak` NOT forgiven; (5) anti-over-match `work-docs/random.md` NOT forgiven; (6) finalize `_is_harness_artifact` still treats the deliverable as user-dirt (preserve invariant unchanged); (7) non-default `work_docs.dir` documented-skip behavior asserted.
- **Risk:** medium (safety gate, unsafe direction — bounded per ADR-001).
- **Rollback point:** revert Phase 1 commit.

### Phase 2 — Landed-marker sweep + legacy drain + CLI (ADR-003, ADR-004)
- **depends_on:** `[1]`
- **parallel_group:** `serial-guard`
- **merge_hazards:** `worktree.py` (same file) + rendered-snapshot baseline (new CLI surface)
- **Scope (in):** finalize marker write (handed_off block); SHA-validated marker sweep; legacy content-gate fallback; `_cli_prune_branches` + `main()` dispatch + usage string; orphan-ref reaping; warning summarization.
- **Scope (out):** docs/template wording (Phase 3).
- **Exit criterion** (enumerated, runnable): (a) finalize writes `refs/hm-landed/v1/<name>` = tip-after-capture, co-located in handed_off; (b) marker sweep deletes iff `tip==marker_SHA` & dir gone, deletes marker same-op; (c) name-collision: re-created branch `tip != marker_SHA` → NOT marker-deleted → content-gate path; (d) orphan reaping: branch deleted → marker gone; `refs/hm-landed/v1/*` with no branch → reaped; (e) legacy markerless → content-gate preserve+warn; (f) `prune-branches --force` deletes + prints per-branch recovery hint; (g) warning wall collapses to 1 summary line; (h) snapshot suite GREEN incl. new CLI surface (Phase 2 self-green); **(i)** `python -m harness_maker.worktree prune-branches` and `… prune-branches --force` route through `main()` and exit 0 via an end-to-end **subprocess** test; usage string updated; `--force` parsed explicitly.
- **Risk:** medium (recovery-net + durable ref state).
- **Rollback point:** revert to Phase 1 **and** clean durable refs: `git for-each-ref refs/hm-landed/ --format='%(refname)' | xargs -rn1 git update-ref -d`. The `v1/` namespace lets a future re-land migrate stale markers.

### Phase 3 — Docs, templates, memory (ADR-001…004)
- **depends_on:** `[1, 2]`
- **parallel_group:** `serial-docs`
- **merge_hazards:** shares the rendered-snapshot baseline with Phase 2, but Phase 2 already left it green, so Phase 3 adds only doc/wording deltas.
- **Scope (in):** CLAUDE.md Multi-session-worktree + Worktree-cleanup sections (deliverable exemption, landed-marker, `prune-branches`, ref lifecycle); `worktree-isolator/SKILL.md.j2` + `execute.md.j2` dirty-base wording; wiki memory entry.
- **Exit criterion:** full `uv run pytest` + `ruff check` + `mypy --strict` green + snapshot regen clean.
- **Risk:** low.
- **Rollback point:** revert Phase 3.

## 🧪 Testing Strategy

- **Unit:** Phase 1 (1)-(7) and Phase 2 (a)-(g) cases against a temp git repo fixture (`tmp_path` + `git init`). Deterministic: no clock/HOME dependence; marker SHAs read back from `git rev-parse`.
- **Integration / e2e:** Phase 2 (i) — `subprocess.run([... "prune-branches"])` and `--force` end-to-end, asserting exit 0 and ref/branch state (catches the dead-dispatch black hole that unit tests on `_cli_prune_branches` would miss).
- **Manual:** in a downstream rendered harness, run plan→execute and confirm no `[ERROR]`; run `prune-branches` and confirm the 74-branch backlog drains / summarizes.

## ⚠️ Risks & Mitigation

| Risk | Severity | Mitigation |
|------|----------|------------|
| Create-guard broadened in the unsafe direction | medium | Per-line filter + anchored full-match pattern + finalize preserves file (ADR-001); anti-over-match tests (4)(5) |
| Stale marker deletes a live re-created branch | high (resolved) | SHA validation `tip==marker_SHA`; mismatch → preserve-biased content-gate (ADR-003); test (c) |
| Orphan `refs/hm-landed/*` become a new wall | medium (resolved) | Same-op delete on all paths + `prune_stale` reaping (ADR-004); test (d) |
| `prune-branches` ships unreachable | medium (resolved) | Phase 2 exit (i): `main()` dispatch + subprocess test |
| `--force` becomes a routine blind wall-silencer | medium | Mandatory per-branch `git log -p` recovery-hint print; reflog wip commits survive |
| Non-default `work_docs.dir` user still blocked | low | Explicit Non-Goal + documented-skip test (ADR-001) |
| Clean-tree finalize records wrong/None SHA | low (resolved) | Record tip-after-capture, not "the wip commit" (ADR-003); not message-dependent |

## ✅ Success Criteria

- [x] plan→execute no longer aborts on an uncommitted deliverable (Phase 1 (1)).
- [x] Coexisting code WIP still blocks create and is listed alone (Phase 1 (2)(3)).
- [x] `.bak`/non-deliverable siblings not forgiven (Phase 1 (4)(5)).
- [x] finalize still stash-preserves deliverables (Phase 1 (6)).
- [x] Landed branches sweep regardless of later HEAD edits; name-collision safe (Phase 2 (b)(c)).
- [x] No orphan `refs/hm-landed/*` accumulation (Phase 2 (d)).
- [x] `prune-branches [--force]` reachable and drains the backlog (Phase 2 (f)(i)).
- [x] Warning wall collapsed to one summary line (Phase 2 (g)).
- [x] `uv run pytest` + `ruff check` + `mypy --strict` green (Phase 3).

## 📊 Execution Status (2026-06-12)

- **Phase 1 — create-guard deliverable exemption: DONE.** `_is_deliverable_path` + per-line wiring in `_is_create_guard_harness_artifact`; guard helpers switched to `git status --porcelain -uall` (a fresh project's first PLAN collapses to one untracked `work-docs/` line otherwise — found during execute, fixed). `tests/unit/test_worktree_deliverable_guard.py` (9 tests) GREEN.
- **Phase 2 — landed-marker sweep + legacy drain + CLI: DONE.** `refs/hm-landed/v1/<branch>` written pre-cleanup on both clean/dirty base; SHA-validated sweep; orphan reaping; `prune-branches [--force]` wired into `main()` dispatch + usage; warning wall collapsed via `_print_prune_warnings`. `tests/unit/test_worktree_landed_marker.py` (11 tests) GREEN.
- **Phase 3 — docs: DONE.** CLAUDE.md keep-base-clean + cleanup sections updated.
- **Contract change:** `test_worktree_churn_pollution.py` updated — the old `work-docs/PLAN-foo.md`-is-dirt assertion now reflects ADR-001 (deliverable forgiven at create, still preserved at finalize); added a non-deliverable-still-blocks case.
- **Phase D gate:** full unit suite, full `tests/` tree, `ruff check .`, `mypy --strict src/` (105 files) — all GREEN. No commit (wrapup owns it).
- **Note:** the dogfood repo gitignores all of `work-docs/`, so it does not itself reproduce the create-block; the unit tests reproduce it via a fixture that tracks `work-docs/` like a real downstream harness.

## 🔍 Plan Validation

**Validator outcome:** NEEDS_REVISION_RESOLVED (2 passes).

- **Pass 1 → MAJOR_REVISION** (2 critical). codex_status: skipped (env permission gate; warn-and-proceed).
  - CRIT-1 stale-marker → live-branch deletion: **resolved** in ADR-003 (SHA-validated sweep).
  - CRIT-2 orphan-ref accumulation + unverifiable Phase 2 exit: **resolved** in ADR-004 + enumerated Phase 2 exit.
- **Pass 2 → NEEDS_REVISION** (0 critical, 2 warning). codex_status: invoked (concurred on W1).
  - W1 `prune-branches` unreachable via `main()`: **resolved** → Phase 2 exit (i) (dispatch + usage + subprocess test + explicit `--force` parse).
  - W2 ADR-003 SHA-source wording / clean-tree path: **resolved** → record tip-after-capture, co-locate in handed_off block.
  - Probed-and-cleared: marker-vs-prune race (preserve-biased by construction); ADR-001 anti-over-match + absent-case coverage; phase decomposition metadata.

Both prior criticals were verified by the validator against the actual source
(`worktree.py:2217`, `:1572-1573`, `:1490`, `:1610-1648`), not merely asserted.
