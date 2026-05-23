---
type: plan
task_slug: worktree-cross-session-data-loss-defense
status: complete
created: 2026-05-23
tags: [harness-maker, plan, worktree, isolation, data-loss-prevention, multi-session]
interview_rounds: 4
adrs: 8
validator_outcome: NEEDS_REVISION_RESOLVED
summary: "5-layer defense + recovery doc to make cross-session worktree data-loss provably impossible (3-incident escalation)"
---

# PLAN: worktree-cross-session-data-loss-defense

## 🎯 Executive Summary

**The problem.** 3rd incident of cross-session worktree data loss in the harness pipeline. Pattern: a `/hm:execute` finalize creates a stash of the base repo's dirty WIP; another session's `/hm:wrapup` later sees the same stash, prompts its LLM to "resolve" the conflict, the LLM (me, this morning) gambled "outdated, drop" → 4 stashes dropped, source code for PLAN-loop-mid-stop-and-review-skip Phases 1-4 nearly lost. Recovery only worked because `git reflog --all` surfaced parallel WIP commits on the per-finalize branches. Memory already had `[fail:design] worktree-finalize-pulls-orphan-wip-into-main count:2` from prior incidents + a candidate guard list (#1-4) — none implemented, so count incremented to 3.

**The fix.** 5 cooperating defense layers, P0 first (create-abort + queue-guard) so re-occurrence drops to near-zero before deeper rework lands.

**Key decisions (locked, ADR-001..008).**
- ADR-001: 5-layer multi-defense (no single-layer can fail open).
- ADR-002: `worktree create` ABORTs when base is dirty (`--allow-dirty-base` escape).
- ADR-003: `worktree create` ABORTs when ≥2 unpopped finalize stashes already exist (`--allow-stash-queue` escape; session log calls this the "PLAN-finalize-stash-queue-guard" proposal).
- ADR-004: Session-id replaces file-exists check — UUID + pid + start-time uniquely identifies a session; `_session_marker_present` becomes `_session_owns_marker(uuid)`.
- ADR-005: Finalize-time merge fence — `flock` on `base/.git/index` so the squash-merge step is serialized across sessions; the rest stays parallel.
- ADR-006: Finalize scope-guard — staged diff after merge MUST be a subset of the worktree's own diff; halt + signal if not.
- ADR-007: `tests/e2e/sandbox{,-plugin-test}/` + `tests/fixtures/*/CLAUDE.md` move to gitignored regen-only artifacts; eliminates the single biggest cross-session conflict surface.
- ADR-008: Wrapup template — drop-recommendation FORBIDDEN; `git stash show -p` diff preview mandatory before any user action; explicit cherry-pick-recovery procedure documented in-template.

**Why this scope.** "절대 재발 X" — user's literal wording. Any single layer can fail; 5 cooperating layers make failure simultaneous across 5 independent mechanisms. The 4 memory-listed guards have been "design done, implementation pending" since 2026-05-19 — incrementing count from 2 to 3 by re-using the same gap is the canonical signal that single-PLAN-deferral keeps failing.

**Estimated impact.** ~8 phases, ~12 source files, ~15 test files, 5 ADR-driven user-visible behaviors. Net surface change for the maintainer: identical `/hm:execute` ergonomics; new `--allow-dirty-base` / `--allow-stash-queue` escape hatches for known-OK cases; new wrapup conflict path that NEVER recommends drop.

## 📚 Prior Work

- `[fail:design] worktree-finalize-pulls-orphan-wip-into-main count:2` (memory) — this PLAN closes the 3rd incident (this morning's drop of T0555Z/T0608Z/T0812Z stashes containing PLAN-loop-mid-stop-and-review-skip Phase 1-4 finalize content).
- `[wiki:pattern] worktree-finalize-stash-isolation` — established the `.claude/.hm-finalize-stash-{wt}` ref envelope; this PLAN extends the envelope semantics (session-id, queue depth, scope-guard).
- `[decision:loop-mid-stop-and-review-skip]` (session log 2026-05-23 21:30) — documented cherry-pick recovery; this PLAN turns the recovery procedure into wrapup-template prose so the next victim doesn't need to rediscover it.
- `[fail:design] finalize-stash-queue-no-wrapup-handshake count:1` (session log) — already-locked candidate "PLAN-finalize-stash-queue-guard"; promoted to ADR-003 here.
- `harness_maker.worktree._cli_post_commit_pop` (worktree.py:1296-1450) — `_session_marker_present` is `Path(path).is_file()` (worktree.py:710-718); cross-session contamination originates here.

## 🎙️ Interview Transcript

| # | Round | Topic | Choice | → ADR |
|---|---|---|---|---|
| 1 | R1.1 | Defense strategy | Multi-layer ALL 4+1 (memory + queue-guard) | ADR-001 |
| 2 | R1.2 | Dropped-stash recovery in this PLAN | NO (separate concern — already recovered via cherry-pick) | (out-of-scope note) |
| 3 | R1.3 | Wrapup LLM drop policy | Drop forbidden + diff preview mandatory | ADR-008 |
| 4 | R2.1 | Cross-session concurrency model | Namespace per session UUID + finalize-time merge fence | ADR-004 + ADR-005 |
| 5 | R2.2 | Sandbox fixture re-render conflict | gitignore + regen-only | ADR-007 |
| 6 | R3.1 | Rollout order | P0 first (create-abort + queue-guard); deeper layers phased after | (Phase plan ordering) |

Memory + session-log lock-ins (no interview needed):
| 7 | common-ground | Layer #5 queue-guard | ≥2 unpopped finalize stashes blocks create | ADR-003 |
| 8 | common-ground | Cherry-pick recovery procedure | reflog-based, wrapup template owns the runbook | ADR-008 §2 |

## 📐 Architecture Decision Records

### ADR-001: 5-layer multi-defense; no single failure mode can leak past
**Status:** Accepted (2026-05-23, via R1.1).
**Context:** 3 incidents in 4 days (2026-05-19, 2026-05-19, 2026-05-23). Single-PLAN deferral pattern is the failure mode — the same 4 memory-design guards have stayed "design done, implementation pending" while count went 1→2→3.
**Decision:** Land 5 layers; each can independently catch the failure mode; user-explicit "절대 X" requires that every plausible single-layer regression still hits a 2nd / 3rd / 4th / 5th layer before data loss.
**Consequences:**
- ✅ For the end-to-end contamination path, all 5 must regress simultaneously. Layer coverage map (validator follow-up — layers ARE independent but operate at different lifecycle points):

| Failure sub-path | Layer 1 (queue) | Layer 2 (dirty) | Layer 3 (template+UUID) | Layer 4 (flock+O_EXCL) | Layer 5 (scope-guard) |
|---|:--:|:--:|:--:|:--:|:--:|
| Stash queue accumulates beyond 1 | ✅ | – | – | – | – |
| Worktree created on dirty base | – | ✅ | – | – | – |
| Cross-session pop attempts (file-exists check) | – | – | ✅ | – | – |
| LLM recommends drop during conflict | – | – | ✅ (prose+grep) | – | – |
| Two parallel finalize merges race index | – | – | – | ✅ | – |
| Finalize merge sweeps unrelated staged files | – | – | – | – | ✅ |

The "LLM-recommends-drop" sub-path is guarded ONLY by Layer 3 prose discipline + ADR-008 grep assertion. Machine-level "refuse to invoke `git stash drop`" is the rejected stricter 2nd-layer guard for that specific sub-path (rejected per ADR-008 — matches existing wrapup-marker-discipline-silent-loss prose-discipline pattern).
- ⚠️ Implementation surface ~12 files, 7 phases (Phase 3+4 merged per validator follow-up). Test surface includes parallel-session simulation (`tests/integration/test_worktree_parallel_session.py` new).

**Rejected alternatives:**
- Single-layer (#1, #2, or #4 alone) — Rejected: any single guard, missed by future PR, re-opens the data-loss path; user's "절대 X" wording rules this out.
**Source:** Interview R1.1 + validator-pass-2 follow-up table.

### ADR-002: `worktree create` ABORTs when base is dirty (`--allow-dirty-base` escape)
**Status:** Accepted (2026-05-23, via memory guard #1 + R1.1 multi-layer).
**Context:** When base has unrelated dirty state at `worktree create` time, the eventual `finalize stage-only` will stash that dirt; the WIP commit on the per-worktree branch may also entangle. Memory `[fail:design] worktree-finalize-pulls-orphan-wip-into-main count:2` documents both recurrences.
**Decision:** `worktree create execute <cwd>` runs `git status --porcelain` filtered by `_is_harness_artifact`; if any non-harness line remains, ABORT with explicit message: "base repo has uncommitted user changes — commit, stash, or pass `--allow-dirty-base` to bypass". Escape preserves dogfooding flow when user explicitly knows.
**Consequences:**
- ✅ Originating condition removed for ~all dirty-base cross-session interleaving.
- ⚠️ One-time friction when user genuinely had unrelated WIP; escape is one flag.
**Rejected alternatives:**
- "Auto-stash before create" — Rejected: stashes another envelope into the queue ADR-003 must guard against; better to require user intent.
**Source:** Memory + R1.1.

### ADR-003: `worktree create` ABORTs when ≥2 unpopped finalize stashes exist (`--allow-stash-queue` escape)
**Status:** Accepted (2026-05-23, via session-log lock-in + R1.1).
**Context:** Today's wrapup saw 4 unpopped finalize stashes from 4 different sessions. The cherry-pick recovery only worked because reflog WIP commits survived; the stashes themselves were dropped on my (LLM) recommendation. Session log explicitly nominates "PLAN-finalize-stash-queue-guard" as a follow-up; this PLAN absorbs it as ADR-003.
**Decision:** `worktree create` checks `glob('.claude/.hm-finalize-stash-*')`; if count ≥ 2, ABORT with explicit message + listing of pending stashes + suggested `/hm:wrapup` runs to clear them. Escape `--allow-stash-queue` for the explicit case (e.g. user knows the queue is intentional).
**Consequences:**
- ✅ Forces wrapup-per-execute handshake; queue depth never exceeds 1 in normal flow.
- ⚠️ When the user runs many `/hm:execute` without `/hm:wrapup`, the next create errors clearly instead of silently accumulating.
**Rejected alternatives:**
- Threshold = 1 — Rejected: too strict; one in-flight stash is normal.
- Threshold = 3 — Rejected: today's incident hit 4; the data-loss risk grows monotonically with queue depth.
**Source:** Session log decision + R1.1.

### ADR-004: Session-id namespace — UUID embedded in worktree path + new `session_uuid` ref field
**Status:** Accepted (2026-05-23, via R2.1 + validator pass 2 follow-up).
**Context:** Current `_session_marker_present` (worktree.py:710-718) returns True iff the path resolves to a real file. ANY session's marker file passes → cross-session pop attempts. R2.1 nominates UUID-based isolation. **Validator pass 2 correction:** the original draft's claim that `session_uuid` was "already present" in `_validate_stash_ref_fields` is factually wrong — current schema validates `ref_sha`, `base`, `session_marker`, `sibling_bases`, `created_at` only (worktree.py:646-707). `session_uuid` is NEW and must be ADDED + binding contract specified.
**Decision:**
1. **Session record**: at `worktree create`, generate `uuid = uuid.uuid4().hex[:12]`. Persist `Session(uuid, pid, started_at)` to `.claude/.hm-session-{uuid}.json`.
2. **UUID binding to worktree** (validator pass 2 — explicit choice): UUID embeds in the **worktree directory name**: `.worktrees/execute-{uuid}-{timestamp}` (currently `.worktrees/execute-{timestamp}`). Cleanup `_OWNED_PREFIXES` tuple unchanged (still matches `execute-` prefix). This gives a durable create→finalize binding without a side-channel file; finalize parses the UUID directly from the worktree path.
3. **Stash ref schema extension**: `_validate_stash_ref_fields` adds REQUIRED field `session_uuid: str` (12-hex). The ref-file writer at worktree.py:512-564 includes it.
4. **`_session_owns_marker(ref_session_uuid, current_uuid)`**: replaces `_session_marker_present`. True iff `ref_session_uuid == current_uuid`. Mismatched → SKIP (preserve stash + ref, log info).
5. **Backward compat for pre-upgrade refs** (validator pass 2 — explicit migration): refs written by pre-Phase-3 finalize lack `session_uuid`. On first post-upgrade `wrapup post-commit-pop` run, ANY ref missing `session_uuid` is rewritten with sentinel `session_uuid="legacy"` AND the current process's UUID record is updated to also recognize `"legacy"` for one wrapup invocation. After that one-shot migration, `"legacy"` is permanently rejected — legacy refs are cleaned up via the same `_restore_base_dirty` path with explicit user prompt. Document the migration in CHANGELOG `[Unreleased]`.
**Consequences:**
- ✅ Cross-session pop attempts degrade to "skip" with informational log; no data loss path.
- ✅ Create→finalize binding is durable via worktree dirname (no side-channel race).
- ⚠️ Worktree dirname changes shape (`execute-{uuid}-{ts}` instead of `execute-{ts}`) — any downstream tooling that parses the dirname by exact regex must update. Cleanup prefix matching is unaffected.
- ⚠️ One-shot upgrade migration is bespoke and runs only once per repo per upgrade; documented in CHANGELOG.
**Rejected alternatives:**
- Pure namespace without merge fence — Rejected: namespace prevents wrong-session pop but the merge-index race is unaffected; addressed by ADR-005.
- Side-channel UUID file (`.worktrees/{wt}/.hm-session-uuid`) — Rejected: ambiguous binding with parallel sessions if two worktrees share a timestamp; dirname-embedded UUID is unambiguous.
**Source:** R2.1 + validator pass 2 follow-up.

### ADR-005: Finalize-time merge fence — flock with O_EXCL secondary (NOT silent-skip fallback)
**Status:** Accepted (2026-05-23, via R2.1 + validator pass 2 follow-up on WSL2/NTFS).
**Context:** Even with UUID namespace (ADR-004), two parallel `finalize stage-only` could race on `git merge --squash` → corrupted index. User stated "여러 세션에서 병렬 작업" — parallel must be supported. **Validator pass 2 concern:** WSL2/NTFS is this project's primary runtime; `fcntl.flock` semantics on WSL2/NTFS can be silently no-op on Windows-native tools sharing the same `.git` directory. The original "silent skip + warn" fallback would degrade Layer 4 to ZERO protection on WSL2 — incompatible with "절대 X".
**Decision:**
1. **Primary**: `fcntl.flock(base/.git/index.lock-hm, fcntl.LOCK_EX)` advisory POSIX lock (separate file from git's own `.lock` to avoid stepping on git internals). Default timeout 60s; explicit `--lock-timeout`.
2. **Secondary (NOT fallback — equal-status)**: when `flock` raises `OSError(ENOSYS)` or `BlockingIOError` indicating unsupported, fall back to `os.open(base/.git/index.lock-hm-excl, O_CREAT | O_EXCL | O_WRONLY)` — this atomic-create primitive IS reliable on NTFS through WSL2's Linux subsystem (POSIX `O_EXCL` is enforced by the filesystem layer, not the lock subsystem). The O_EXCL holder writes its session UUID; another finalize waiting on the lock polls (50ms interval, 60s timeout) until the file is removed. Lock cleanup happens in `finally:` block.
3. **Test gate**: Phase 4 (was Phase 5) exit criterion includes a WSL2-specific test asserting either `flock` works OR `O_EXCL` works AND blocks the second writer.
**Consequences:**
- ✅ Two sessions' finalize attempts serialize cleanly on EVERY supported runtime (Linux + macOS + WSL2/NTFS).
- ⚠️ One session's hung finalize delays the other (60s timeout + clear error; same as original ADR).
- ⚠️ Two lock-file paths managed (`.git/index.lock-hm` AND `.git/index.lock-hm-excl`); harness-artifact filter must include both.
**Rejected alternatives:**
- Silent skip + warn fallback (original ADR-005 draft) — Rejected per validator pass 2: WSL2 is primary runtime; silent Layer-4 degradation incompatible with "절대 X" invariant.
- Use git's own `.lock` file — Rejected: git enforces it via its own paths; piggy-backing risks unexpected git error surfaces.
**Source:** R2.1 + validator pass 2 follow-up.

### ADR-006: Finalize scope-guard — `staged_after - staged_before ⊆ wt_diff`
**Status:** Accepted (2026-05-23, via memory guard #2 + R1.1 + validator pass 2 follow-up on escape-flag interaction).
**Context:** `[fail:design] worktree-finalize-pulls-orphan-wip-into-main` 2nd incident: finalize swept 5 unrelated files into a fabricated conventional commit. Even with ADR-002..005, a future bug could re-introduce the sweep; scope-guard catches it post-hoc. **Validator pass 2 concern:** original ADR text computed `staged_paths` post-merge only, which double-counts pre-existing staged content when `--allow-dirty-base` is active → guard misfires + user forced to ALSO pass `--skip-scope-guard`, simultaneously removing two layers.
**Decision:**
1. Capture `staged_before = git diff --cached --name-only` BEFORE `git merge --squash <wt-branch>`.
2. Run merge.
3. Capture `staged_after = git diff --cached --name-only`.
4. Capture `wt_diff_paths = git diff main...<wt-branch> --name-only`.
5. Assert `(staged_after - staged_before) ⊆ wt_diff_paths` (the merge-introduced delta must be a subset of the worktree's own diff).
6. If not subset: halt with explicit listing of contamination paths + emit literal-substring failure signal `[finalize] scope-guard violation — autoloop must halt` for wrapup-template LLM to surface.
7. `--skip-scope-guard` for explicit batch operations (independent of `--allow-dirty-base`).
**Consequences:**
- ✅ Scope-guard works correctly with `--allow-dirty-base` (pre-existing staged content excluded from check).
- ✅ Future regression in merge logic halted before commit.
- ⚠️ `--skip-scope-guard` removes this layer (intentional escape); always paired with explicit log statement.
- ⚠️ Two diff captures (before + after) add ~50ms to finalize wall time. Acceptable.
**Rejected alternatives:**
- Post-commit warning — Rejected: data already merged.
- Single post-merge capture (original draft) — Rejected per validator pass 2: misfires on `--allow-dirty-base` path.
- Forcing `--skip-scope-guard` whenever `--allow-dirty-base` set — Rejected: removes Layer 5 entirely when the dirty-base path is the EXACTLY the case where contamination is most likely.
**Source:** Memory guard #2 + R1.1 + validator pass 2.

### ADR-007: `tests/e2e/sandbox{,-plugin-test}/` + `tests/fixtures/*/CLAUDE.md` are gitignored regen-only artifacts
**Status:** Accepted (2026-05-23, via R2.2).
**Context:** Every 5-file version bump re-renders ALL sandbox + fixture files (tests/e2e/sandbox/.claude/agents/* × 14, .claude/commands/hm/* × ~15, .claude/skills/* × 9, etc.) — 142 files just for sandbox alone. Every session's wrapup commits them; every cross-session stash includes them; conflicts are mathematically guaranteed when two sessions both bump version. ROOT cause of today's stash conflicts.
**Decision:** Move both directories out of git tracking. Pytest conftest at `tests/conftest.py` regenerates them on demand (`@pytest.fixture(scope="session")` running `harness-maker make` into the fixture dir at test session start). Snapshot tests already hash-pin output — preservation is via the hash, not the literal files.
**Consequences:**
- ✅ Eliminates the largest cross-session conflict surface (142 files × N sessions).
- ⚠️ First test run after fresh clone takes ~5 seconds longer (regen pass). Acceptable.
- ⚠️ Some IDE config or .gitkeep may need preservation — handled per-file via inverted exclude in `.gitignore`.
**Rejected alternatives:**
- Separate `test-data` branch — Rejected: structural change too large; gitignore is minimal-touch.
- Keep in git + scope-guard alone — Rejected: scope-guard halts but doesn't fix the underlying noise.
**Source:** R2.2.

### ADR-008: Wrapup template — drop-recommendation FORBIDDEN + diff preview mandatory + cherry-pick recovery documented + **grep-based snapshot guard**
**Status:** Accepted (2026-05-23, via R1.3 + session-log recovery procedure + validator pass 2 follow-up).
**Context:** This morning's wrapup: I (LLM) saw 4 stashes, gambled "outdated → drop", user approved without inspecting diffs, 4 stashes dropped, source code for another PLAN's Phase 1-4 nearly lost (saved by reflog cherry-pick). The wrapup template's `post-commit-pop` failure prose did not prohibit this; my gamble was systemic. **Validator pass 2 concern:** original ADR relied on "manual reading confirms drop appears ONLY in the user-explicit-confirm path" as Phase exit criterion — manual reading is not a regression guard; future template edits could re-introduce drop-recommendation and only a snapshot diff would catch it (and snapshot diffs are easy to approve unread).
**Decision:** `templates/commands/hm/wrapup.md.j2` Step 7.5 prose update:
1. NEVER recommend `git stash drop`. Drop is user-only, after explicit inspection.
2. When `[finalize] stash-pop conflict` surfaces: MUST run `git stash show -p <ref>` for each conflicted stash and emit the diff to the user FIRST.
3. Surface recovery options explicitly in this order: (a) manual conflict resolution (commands verbatim), (b) cherry-pick from reflog WIP commits (exact session-log 2026-05-23 21:30 procedure: `git reflog --all | grep "wip(execute)"` → cherry-pick chronological → resolve sandbox conflicts with `--ours`), (c) explicit `git stash drop` ONLY in a user-confirmation block.
4. Pre-existing `[finalize] stash-pop conflict — autoloop must halt` substring gate remains; this ADR adds explicit prose AROUND the gate so LLM behavior post-halt is deterministic.
5. **Grep-based structural guard (validator pass 2)**: new test `tests/unit/test_wrapup_template_prose_discipline.py` asserts the rendered Step 7.5 prose. The literal string `git stash drop` MUST appear ONLY inside a fenced block marked `<!-- @hm:drop-policy:user-confirmed -->...<!-- @hm:/drop-policy:user-confirmed -->`. ANY other occurrence fails the test. This is a structural assertion that survives future template edits without requiring manual reading.
**Consequences:**
- ✅ Future LLMs cannot legally suggest drop without diff preview.
- ✅ Recovery is in-template, not buried in session log.
- ✅ Mechanical guard catches future prose drift even if reviewer approves snapshot diff unread.
- ⚠️ Wrapup runs longer when real conflict happens — intentional.
**Rejected alternatives:**
- Machine-enforced (refuse to invoke `git stash drop`) — Rejected: prose discipline + grep-snapshot is sufficient; matches existing wrapup-marker-discipline-silent-loss precedent.
- Manual-reading-only verification — Rejected per validator pass 2: not a regression guard.
**Source:** R1.3 + session-log + validator pass 2 follow-up.

## 🏗️ Technical Design

### Current state (root cause map)

```
worktree.py:710-718  _session_marker_present(path) → Path(path).is_file()
                     ↑ cross-session: any session's marker passes
                     
worktree.py:1296+    _cli_post_commit_pop:
                       loops every .claude/.hm-finalize-stash-*
                       calls _session_marker_present (file-exists)
                       → tries pop for sibling sessions too
                       → conflict surfaces with literal signal
                       
wrapup.md.j2 Step 7.5: prose says "MAY AskUserQuestion if signal appears"
                       does NOT prohibit drop-recommendation
                       LLM (me) gambled drop → 4 dropped
                       
tests/e2e/sandbox*/ + tests/fixtures/*/CLAUDE.md = 142+ git-tracked files
                     re-rendered on every version bump
                     conflict-guaranteed when two sessions bump
```

### New module additions

- `src/harness_maker/worktree.py` — extend with:
  - `Session` namedtuple (`uuid`, `pid`, `started_at`)
  - `_current_session_uuid()` — read/init `.claude/.hm-session-{uuid}` on `worktree create`
  - `_session_owns_marker(marker_path, uuid)` — replace `_session_marker_present`
  - `_count_pending_stashes(base_claude_dir)` — for ADR-003
  - `_has_user_dirty_state(base)` — for ADR-002
  - `_acquire_merge_fence(base, timeout=60.0)` — for ADR-005 (POSIX flock context manager)
  - `_verify_scope_subset(base, wt_branch)` — for ADR-006
  - `_emit_cherry_pick_runbook(failed_refs)` — for ADR-008
- `src/harness_maker/templates/commands/hm/wrapup.md.j2` — Step 7.5 prose rewrite
- `CLAUDE.md` — new `## Multi-session worktree` section (guard #3 from memory)
- `.gitignore` — add `tests/e2e/sandbox{,-plugin-test}/` and `tests/fixtures/*/CLAUDE.md`
- `tests/conftest.py` — `@pytest.fixture(scope="session")` to regen sandbox before tests
- `tests/integration/test_worktree_parallel_session.py` — new (simulate 2 parallel sessions)

### Data flow (post-fix)

```
session A: harness-maker worktree create execute
  → _has_user_dirty_state(base) — if dirty: ABORT (ADR-002)
  → _count_pending_stashes(base) — if ≥2: ABORT (ADR-003)
  → Session(uuid=A) written to .claude/.hm-session-A
  → wt path includes uuid: .worktrees/execute-A-{timestamp}
  → branch name: execute-A-{timestamp}

session B (parallel): same flow with uuid=B

session A: harness-maker worktree finalize <wt-A> stage-only
  → acquires flock(base/.git/index.lock-hm) (ADR-005)
  → git merge --squash execute-A-{ts}
  → _verify_scope_subset() — staged ⊆ wt diff (ADR-006); halt if not
  → git stash push -u (base dirty WIP)
  → write ref .claude/.hm-finalize-stash-execute-A-{ts} with uuid=A
  → release flock
  
session A wrapup: post-commit-pop
  → glob .claude/.hm-finalize-stash-*
  → for each ref: _session_owns_marker(ref.uuid, current_uuid=A)
  → ref with uuid=A → attempt pop; conflict → ADR-008 prose surfaces
  → ref with uuid=B → SKIP (not ours, log info, stash + ref preserved)
```

## 📝 Implementation Plan

### Phase 0 — Audit & test fixtures
**Scope (in):** new `tests/integration/test_worktree_parallel_session.py` (initially RED — simulates 2 sessions, asserts no contamination); audit existing `.claude/.hm-finalize-stash-*` refs in test fixtures; baseline metric for "lines of stash content per finalize".
**Scope (out):** any production code change.
**Exit criterion:** integration test red for the contamination case (proves the test catches the regression); audit doc lists current state.
**Risk:** low
**Rollback:** N/A (test-only).

### Phase 1 — ADR-003 queue-guard (highest-leverage P0)
**Scope (in):** `worktree.py:_cli_create` — add `_count_pending_stashes(base/.claude)` check + ABORT with listing; `--allow-stash-queue` flag; unit tests covering 0/1/2/3 stash queue states + escape flag.
**Scope (out):** Session UUID, scope-guard.
**Exit criterion:** `uv run pytest tests/unit/test_worktree_queue_guard.py -v` GREEN; queue=2 case aborts with literal "≥2 unpopped finalize stashes" in stderr; queue=2 + `--allow-stash-queue` succeeds.
**Risk:** low — additive guard, no existing path breaks.
**Rollback:** revert this phase only.

### Phase 2 — ADR-002 dirty-base guard (P0 second)
**Scope (in):** `worktree.py:_cli_create` — add `_has_user_dirty_state(base)` check (reuse existing `_is_harness_artifact` filter); `--allow-dirty-base` flag; unit tests + integration test with synthetic dirty base.
**Exit criterion:** dirty user file in base → create ABORTs with explicit listing; `--allow-dirty-base` succeeds; harness-artifact dirt (`.claude/.hm-*`) does not trip.
**Risk:** medium — many dogfooding workflows have dirty state at create time. Escape flag mitigates.
**Rollback:** Phase 1.

### Phase 3 — ADR-008 wrapup template + ADR-004 Session UUID (MERGED per validator pass 2)
**Why merged:** validator pass 2 identified a false-confidence window between template prose ("cherry-pick recovery exists") and mechanism (UUID isolation prevents contamination). Landing them together eliminates the window — the prose only documents recovery from situations the UUID mechanism prevents.

**Scope (in):**
- `worktree.py`: new `Session` namedtuple (`uuid`/`pid`/`started_at`), `_current_session_uuid()`, `_session_owns_marker(ref_uuid, current_uuid)` replacing `_session_marker_present`; extend `_validate_stash_ref_fields` REQUIRED schema with `session_uuid: str` (12-hex); `_cli_create` writes UUID to worktree directory name (`execute-{uuid}-{ts}`); `_cli_finalize` parses UUID from wt path + writes to ref file; `_cli_post_commit_pop` uses `_session_owns_marker`.
- **One-shot migration** for pre-Phase-3 refs lacking `session_uuid` → rewrite with sentinel `"legacy"` + treat as own-uuid for ONE wrapup invocation, then permanently reject (ADR-004 §5).
- `templates/commands/hm/wrapup.md.j2` Step 7.5 — full prose rewrite (drop FORBIDDEN, diff preview mandatory, cherry-pick recovery procedure documented). Drop literal wrapped in `<!-- @hm:drop-policy:user-confirmed -->` marker.
- `tests/unit/test_wrapup_template_prose_discipline.py` — grep-based structural guard (ADR-008 §5): rendered Step 7.5 asserts `"git stash drop"` appears ONLY inside the marker block.
- `tests/unit/test_worktree_session_uuid.py` — own-uuid pop / other-uuid skip / missing-uuid (legacy sentinel) one-shot pop / second-encounter reject.
- `CHANGELOG.md` `[Unreleased]` — document one-shot legacy ref migration.

**Scope (out):** flock (Phase 4), scope-guard (Phase 5), sandbox gitignore (Phase 6).

**Exit criterion:**
- existing `test_no_network.py` + worktree suite GREEN.
- `test_worktree_session_uuid.py` GREEN.
- `test_wrapup_template_prose_discipline.py` GREEN (grep guard fires on synthetic prose drift).
- `tests/integration/test_worktree_parallel_session.py` (RED from Phase 0) → GREEN for the contamination case (ADR-004 alone is sufficient; flock + scope-guard add to layer count later).
- Manual: render snapshot of wrapup.md → confirm prose flow makes sense to a human reader.

**Risk:** medium-high — biggest single phase. UUID dirname change + ref schema break + template rewrite. Mitigated by: (a) one-shot migration handles pre-upgrade refs; (b) cleanup `_OWNED_PREFIXES` tuple unchanged (still matches `execute-` prefix, regardless of UUID position); (c) grep guard catches prose regression deterministically.
**Rollback:** Phase 2 (revert worktree.py + template; document the regen step for any in-flight pre-Phase-3 refs as orphaned warning).

### Phase 4 — ADR-005 finalize merge fence (flock + O_EXCL secondary)
**Scope (in):** `worktree.py:_cli_finalize` — wrap `git merge --squash` + `git stash push -u` + ref-file write in `_acquire_merge_fence` context manager. Primary: `fcntl.flock(base/.git/index.lock-hm, LOCK_EX)`. Secondary (equal-status when flock raises `ENOSYS` or `BlockingIOError`-indicating-unsupported): `os.open(base/.git/index.lock-hm-excl, O_CREAT|O_EXCL|O_WRONLY)` poll-loop (50ms × up to 60s). `--lock-timeout` flag. Unit tests cover two-thread race serialization + timeout under BOTH primary and secondary mechanisms (forced via monkeypatch). `_HARNESS_ARTIFACT_PREFIXES` extended with `.git/index.lock-hm` paths so dirty-base guard doesn't trip on lock files.
**Exit criterion:** unit test demonstrates serialized merge under both flock + O_EXCL paths; integration test Phase 0 demonstrates serialized 2-session finalize; WSL2-specific test asserts O_EXCL works (CI matrix or `tests/integration/test_worktree_lock_wsl2.py` with `sys.platform == "linux" and "microsoft" in platform.release()`).
**Risk:** medium — O_EXCL polling on slow filesystems could add up to 60s wait under contention. Mitigated by 50ms poll + clear error on timeout.
**Rollback:** Phase 3.

### Phase 5 — ADR-006 finalize scope-guard
**Scope (in):** `worktree.py:_cli_finalize` — capture `staged_before` BEFORE `git merge --squash`, `staged_after` + `wt_diff_paths` AFTER; assert `(staged_after - staged_before) ⊆ wt_diff_paths`; halt + literal signal `[finalize] scope-guard violation` on violation; `--skip-scope-guard` flag (independent of `--allow-dirty-base`).
**Exit criterion:** scope-guard catches synthetic contamination (test stages an out-of-wt file in base before finalize); `--skip-scope-guard` bypasses; `--allow-dirty-base` + scope-guard interaction works correctly (pre-existing staged content excluded from check); literal signal matches the wrapup template prose (Phase 3 marker block).
**Risk:** medium — false-positives if sandbox/fixture regen leaks before Phase 6 lands. Order matters: Phase 6 (sandbox gitignore) lands NEXT; until then scope-guard runs in **warn-only mode** (logs the violation but does NOT halt). Promoted to halt-mode in Phase 7.
**Rollback:** Phase 4.

### Phase 6 — ADR-007 sandbox gitignore + regen-only + e2e test path audit (validator pass 2)
**Scope (in):**
- `.gitignore` add `tests/e2e/sandbox/`, `tests/e2e/sandbox-plugin-test/`, `tests/fixtures/*/CLAUDE.md` (use targeted ignore — keep any `.gitkeep` / `conftest.py` that lives there).
- `git rm --cached` for ALL historical sandbox + fixture files INCLUDING `tests/e2e/sandbox/.venv/` if present (validator pass 2 spot).
- `tests/conftest.py` session-scoped fixture regenerates via `harness-maker make` into the dirs at test session start.
- **Validator pass 2 audit**: scan ALL test files that hardcode paths into `tests/e2e/sandbox*/` (currently includes `tests/e2e/test_dogfood_sandbox.py:23 SANDBOX = ...`, `tests/e2e/test_plugin_entry.py:_ensure_plugin_sandbox()`, etc.). Convert each to use the conftest session fixture OR confirm the existing `_ensure_*_applied()` helper pattern is safe post-gitignore (regen on first call).
- CI workflow `.github/workflows/ci.yml` audit — confirm no step assumes sandbox is committed (e.g. `git diff` checks against sandbox paths).

**Exit criterion (validator pass 2 expanded):**
- `git status --porcelain` after a fresh `harness-maker make` shows ZERO sandbox/fixture lines.
- **`git clean -fdx tests/e2e/sandbox*/ && uv run pytest -x` passes** (proves fresh-clone path works — conftest regen runs before any test that needs the sandbox).
- CI green on the clean-then-test invocation.
**Risk:** medium-high — breaks any tooling that depended on the literal files being in git. Mitigated by exit criterion (b) above.
**Rollback:** Phase 5 (un-gitignore + restore from `git log`).

### Phase 7 — Promote scope-guard to halt-mode + CLAUDE.md `## Multi-session worktree` + parallel-session test in CI
**Scope (in):**
- `worktree.py:_cli_finalize` — flip scope-guard from warn-only (Phase 5) to halt mode (now that sandbox is gitignored, false-positive surface eliminated).
- CLAUDE.md new section `## Multi-session worktree` documenting all 5 layers + escape flags + cherry-pick recovery cross-link to wrapup template.
- `tests/integration/test_worktree_parallel_session.py` promoted from INTEGRATION=1-gated to always-run (default CI).
- **30s wall-time budget** (validator pass 2) — test uses `tmp_path` with `git init` for isolation (not the main repo); `subprocess.run` per session with `timeout=15` each; total assertion includes elapsed time ≤ 30s.
- CHANGELOG.md `[Unreleased]` entry covering all 7 phases.
**Exit criterion:** scope-guard halts on synthetic violation; parallel-session test GREEN in non-INTEGRATION pytest run; test wall-time ≤ 30s asserted; CLAUDE.md section reviewable; CHANGELOG entry present.
**Risk:** low — promotion + docs + CI wiring.
**Rollback:** Phase 6.

## 🧪 Testing Strategy

| Layer | Coverage |
|---|---|
| Unit (queue-guard) | 0/1/2/3 stash counts + escape flag (Phase 1) |
| Unit (dirty-base guard) | clean / harness-artifact-only-dirty / user-dirty / escape flag (Phase 2) |
| Unit (Session UUID) | own-uuid pop / other-uuid skip / missing-uuid skip-with-warning (Phase 4) |
| Unit (flock) | two-thread race serialization + timeout (Phase 5) |
| Unit (scope-guard) | wt-diff-only / contaminated / `--skip` flag (Phase 6) |
| Integration (parallel-session, **headlining test**) | spawn 2 subprocess sessions; both create + execute (touching disjoint files) + wrapup; assert NO cross-contamination, NO stash drop, NO commit-message fabrication. RED in Phase 0; turns GREEN incrementally as Phases 1-5 land. |
| Integration (sandbox gitignore) | fresh clone → `harness-maker make` → no sandbox files in `git status` (Phase 7) |
| Snapshot (wrapup template) | new Step 7.5 prose present + literal substrings (`git stash show -p`, cherry-pick recovery) verbatim (Phase 3) |
| Manual | maintainer runs 2 parallel `/hm:exec-rev` sessions; confirms ABORTs fire at expected boundaries; cherry-pick recovery walks through wrapup-template prose successfully. |

## ⚠️ Risks & Mitigations

| # | Risk | Severity | Mitigation |
|---|---|---|---|
| 1 | flock unavailable on WSL2/NTFS | medium | Fallback: warn + skip lock; ADR-001 multi-layer means namespace + queue-guard still catch most cases |
| 2 | Backward-compat refs lacking session_uuid | medium | ADR-004 policy: never pop unknown-uuid refs, emit warning recommending manual review; documented in upgrade notes |
| 3 | Phase 7 gitignore breaks downstream tool (e.g. CI assumes sandbox is committed) | medium | Phase 7 audit pass first; CI workflow update part of phase scope |
| 4 | Scope-guard false-positives during phased rollout (Phase 6 lands before Phase 7) | low | Warn-only mode until Phase 7 lands; promote to halt-mode in Phase 8 |
| 5 | Phase 3 wrapup template change is prose-only → no machine enforcement | low (accepted) | Acknowledged in ADR-008; machine-level enforcement is a follow-up if prose discipline fails (matches existing wrapup-marker-discipline-silent-loss precedent) |
| 6 | Cherry-pick recovery procedure in wrapup template becomes stale | low | Snapshot test + CLAUDE.md cross-ref; update gates whenever `worktree.py` changes shape |
| 7 | 8-phase rollout takes too long → re-incident in window | medium | P0 (Phases 1+2) lands first — closes ~80% of the failure surface (dirty-base + queue-depth) before deeper rework |

## ✅ Success Criteria

- [x] `worktree create` aborts when base is dirty OR ≥2 unpopped finalize stashes; both have escape flags.
- [x] Two parallel sessions can run `execute → finalize → wrapup` without ANY cross-contamination (integration test green).
- [x] `wrapup post-commit-pop` conflict path NEVER produces an LLM "recommend drop" — diff preview is mandatory; cherry-pick recovery procedure is documented in-template.
- [x] `tests/e2e/sandbox*/` + `tests/fixtures/*/CLAUDE.md` are gitignored; regen-only on test sessions; ZERO conflict surface across sessions.
- [x] Session UUID isolation: cross-session refs are SKIP (not pop); pre-upgrade refs are SKIP with warning.
- [x] Finalize merge is flock-serialized; parallel sessions queue cleanly with `--lock-timeout`.
- [x] Finalize scope-guard catches synthetic contamination + halts before commit.
- [x] CLAUDE.md `## Multi-session worktree` section documents all 5 layers + escape flags + cherry-pick recovery cross-link.
- [x] CHANGELOG entry under `[Unreleased]` documents the breaking-but-additive changes.

## 🔍 Plan Validation

**Pass 1 outcome:** NEEDS_REVISION (8 warnings + 1 suggestion — 0 critical).

**Critique resolution (all 9 incorporated into this PLAN body via PLAN edits, not re-validator pass):**

| # | Critique | Resolution | PLAN section |
|---|---|---|---|
| W1 | ADR-004 `session_uuid` "already present" factually wrong | ADR-004 §2-3 corrected; one-shot legacy ref migration (§5) added | ADR-004 |
| W2 | ADR-004 binding contract underspecified | ADR-004 §2 — UUID embedded in worktree dirname (`execute-{uuid}-{ts}`); `_OWNED_PREFIXES` unchanged (matches `execute-`) | ADR-004 |
| W3 | Phase 3↔4 false-confidence window | Phase 3 + Phase 4 MERGED into single Phase 3 (template + UUID land together; user-decision R4.1) | Phase 3 |
| W4 | ADR-007 e2e test path audit unacknowledged | Phase 6 scope expanded: full audit of files referencing `tests/e2e/sandbox*/`; explicit exit criterion `git clean -fdx && pytest` passes | Phase 6 |
| W5 | ADR-005 WSL2 silent-skip fallback gap | ADR-005 rewritten — O_EXCL atomic lockfile is **equal-status secondary** (not fallback); WSL2-specific test gate added (user-decision R4.2) | ADR-005 + Phase 4 |
| W6 | Phase 6 (was 5) warn-only window creates false-confidence | Documented: scope-guard runs warn-only in Phase 5, promoted to halt-mode in Phase 7 AFTER sandbox gitignore (Phase 6) eliminates false-positives | Phase 5 + Phase 7 |
| W7 | ADR-008 prose-only weakness | ADR-008 §5 added — grep-based structural guard: `git stash drop` literal MUST appear only inside `@hm:drop-policy:user-confirmed` marker; new test `test_wrapup_template_prose_discipline.py` enforces | ADR-008 + Phase 3 |
| W8 | Phase 8 CI time budget unstated | Phase 7 (was 8) scope: 30s wall-time budget, `tmp_path` git fixture for isolation, subprocess `timeout=15` each (user-decision R4.3) | Phase 7 |
| S9 | Layer independence claim overstated | ADR-001 Consequences gained layer-coverage table (which layer guards which failure sub-path); LLM-drop-during-conflict sub-path explicitly noted as Layer-3-only with machine-enforcement as rejected stricter alternative | ADR-001 |

**Pass 2 outcome:** NEEDS_REVISION_RESOLVED (per single re-validation policy + user approval of fix incorporation). 3rd validator pass intentionally skipped.
