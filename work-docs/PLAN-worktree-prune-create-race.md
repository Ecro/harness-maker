---
type: plan
task_slug: worktree-prune-create-race
status: complete
created: 2026-06-21
tags: [harness-maker, plan, python, worktree, concurrency, prune]
interview_rounds: 2
adrs: 3
validator_outcome: NEEDS_REVISION_RESOLVED
summary: "Stop create-time prune_stale from rmtree-ing a peer session's in-flight worktree (work-loss)"
status_execute: all-phases-green
---

> **Execution status (2026-06-21):** All 4 phases GREEN (TDD). `worktree.py` +
> `tests/unit/test_worktree_prune.py` (16 tests) + `test_worktree_prune_race.py`
> (2 concurrency tests) + `test_worktree_drain.py` fixture update.
> - **Phase 1 (reservation + `.git` filter):** DONE — `create()` writes
>   `.hm-creating-<name>` around the primary `git worktree add` (try/finally
>   spanning add→marker); `_scan_dangling_worktrees` skips fresh-reservation +
>   no-`.git` dirs.
> - **Phase 2 (`--expire`):** DONE — `_git_expire_arg` + gated `git worktree prune`.
> - **Phase 3 (marker-strand):** DONE — `_marker_has_pending_stash` (content-field
>   `session_marker` join) + `_is_orphan_marker` preserve.
> - **Phase 4 (concurrency tests):** DONE — and **caught a more severe facet**: a
>   concurrent `git worktree prune` removes a peer's HALF-WRITTEN admin entry
>   (`gitdir` not yet present) regardless of `--expire`, crashing the peer's
>   `git worktree add`. Fixed by gating `git worktree prune` on
>   `_any_fresh_reservation` (ADR-002 refinement, recorded inline). Race tests 3/3 stable.
> - **Full gate:** `ruff` + `ruff format` + `mypy --strict` (111 files) all clean.
> - **2 pre-existing unrelated failures** (NOT in my diff, different subsystems):
>   `test_autopilot_boundary::test_boundary_step_cap_halt` (autopilot halt_kind
>   precedence) and `test_plugin_live::test_make_no_interactive_prompts` (e2e
>   subprocess). My `.git`-filter regression on `test_worktree_drain` was found +
>   fixed (fixture now seeds `.git`).

# PLAN — Worktree prune-vs-create rmtree race

## 🎯 Executive Summary

**What:** Make the create-time `prune_stale` sweep incapable of `shutil.rmtree`-ing a *peer session's in-flight worktree directory*, closing a **work-loss** path that the 10-fleet audit surfaced and the 4-fix hardening (PLAN-multisession-10-fleet-hardening) explicitly deferred.

**Why:** `prune_stale` runs at every `worktree create` (`_cli_create`), lock-free, BEFORE this session's own create. Its `_scan_dangling_worktrees` (worktree.py:1684) reaps any `.worktrees/<owned-prefix>*` dir that is NOT git-registered AND NOT live-marker-referenced — with **no age guard and no `.git`-entry guard**. During a peer's `git worktree add` (and before the peer writes its `.hm-loop-*` marker), the peer's leaf dir can be on disk yet not-yet-visible-as-registered to the pruning session → `rmtree`. Worse, `prune_stale` runs `git worktree prune` first (worktree.py:1930) which can *de-register* a peer's recent in-flight admin entry, widening the window. The window size depends on git-internal timing (sub-second), so this is fixed **by construction** rather than gated on proving reachability — it is a work-loss path and the defense is cheap.

**Key Decisions:**
- ADR-001 — lock-free, DETERMINISTIC **pre-create reservation**: `create()` writes `.claude/.hm-creating-<name>` before `git worktree add` (removed in a `finally`); the prune scan skips a dir with a fresh reservation. A generous 300s age backstop bounds a leaked reservation; the `.git`-entry filter stays (non-worktree safety). This replaces the Round-1 age+`.git` mechanism, which Codex refuted: a leaf-dir's mtime goes stale during a nested checkout and `.git` appears early, so neither reliably protects the in-flight window.
- ADR-002 — `git worktree prune --expire=<grace>` so the create-time prune does not de-register a peer's recent in-flight worktree admin entry.
- ADR-003 — a TARGETED marker-prune fix: preserve a marker that has a pending `.hm-finalize-stash-*` ref. (Round 1 deferred the marker-prune gap as low-severity; Codex showed it strands deferred base-dirty stash restoration after stage-only finalize — real work loss.) Full session-scoped marker pruning stays deferred.

**Estimated impact:** `worktree.py` (one region: `_scan_dangling_worktrees` + the `prune_stale` `git worktree prune` call + one grace constant) + unit tests (age-guard, `.git`-guard, window-simulation) + a best-effort concurrent repro test. No public API change, no new flag, no behavior change for single-session use.

## 📚 Prior Work

- **`[wiki:architecture] worktree-artifact-janitor` (2026-05-25)** — documents the janitor as removing dangling owned dirs "only when they have a **`.git` entry** and are neither git-registered nor live-marker referenced." The current `_scan_dangling_worktrees` (worktree.py:1684-1702) has **no `.git` check** — so that gate was removed in a later refactor, silently WIDENING the destructive path. ADR-001 restores it.
- **`[wiki:pattern] drain-trigger-additive-relocation` (2026-06-20)** — the janitor-gate principle: never duplicate or widen the destructive gate; the create-time `prune_stale` call is the single gate. This PLAN NARROWS the gate (adds guards), never widens it — consistent.
- **`[fail:design] worktree-finalize-pulls-orphan-wip-into-main` (count:3)** — the 5-layer defense + per-session markers descend from cross-session contamination incidents; this PLAN closes the remaining *deletion* (vs contamination) vector the 10-fleet audit flagged.
- **PLAN-multisession-10-fleet-hardening** — explicitly deferred this race as "a real work-loss path, out of scope." This is the follow-up.

## 🎙️ Interview Transcript

| # | Topic | Category | Question | Choice | → ADR |
|---|-------|----------|----------|--------|-------|
| 1 | Verify-first vs fix-by-construction | Scope/Risk | reachability is git-timing-dependent | **fix-by-construction + repro-attempt test** | ADR-001 |
| 2 | Defense mechanism | Architecture | age-guard+`.git` vs lock vs age-only | **age-grace + `.git`-gate (both lock-free)** | ADR-001 |
| 3 | `git worktree prune` de-registration vector | Failure | `--expire` vs leave vs skip | **`git worktree prune --expire=<grace>`** | ADR-002 |
| 4 | Scope | Scope | rmtree-only vs include marker-prune | rmtree-only (Round 1) → **revised R2** | ADR-003 |
| 5 | Mechanism (Codex-refuted) | Architecture | age+`.git` unsound → reservation vs generous-age vs lock | **pre-create reservation + generous age backstop** | ADR-001 |
| 6 | Scope (Codex-refuted) | Failure | marker-prune deferral strands deferred stash | **targeted marker fix (preserve on pending stash)** | ADR-003 |

Round 2 was driven by Codex second-opinion findings that refuted two Round-1 choices (the age+`.git` mechanism is not sound in-flight protection; the marker-prune deferral strands deferred stash restoration). Defaults taken without a round (recorded as ADR consequences): grace `_PRUNE_GRACE_SECONDS = 300` (generous — Codex P2 showed `_GIT_TIMEOUT`=60s leaves no margin for hooks/teardown/FS latency); the freshness signal is the **reservation file's** mtime (written once at create-start — reliable), NOT the leaf-dir mtime (Codex: stale during nested checkout); the single grace constant drives the reservation-freshness check and `--expire`.

## 📐 Architecture Decision Records

### ADR-001: Pre-create reservation (deterministic) + generous age backstop + `.git` filter
**Status:** Accepted (2026-06-21, via /hm:plan interview Rounds 1-2)
**Context:** `_scan_dangling_worktrees` reaps a dir on `owned-prefix ∧ ¬registered ∧ ¬marker` with no in-flight protection (worktree.py:1941-1944), so a peer's in-flight `create()` worktree (leaf dir on disk, registration not yet visible, marker not yet written) can be `rmtree`d — work loss. **Codex (Round 2) refuted a pure age+`.git` guard:** a directory's `st_mtime` updates only when entries DIRECTLY under it change, so a long checkout writing NESTED content can leave the leaf-dir mtime stale → an age-guard on the leaf mtime misses the window; and `.git` is written EARLY in `git worktree add`, so the `.git`-gate is a non-worktree FILTER, not in-flight protection.
**Decision:** Close the window DETERMINISTICALLY with a **pre-create reservation**. `create()` (the only owned-prefix producer — `_OWNED_PREFIXES`; per-task `hm/<slug>` worktrees aren't prefix-scanned) writes an atomic reservation file `.claude/.hm-creating-<name>` BEFORE `git worktree add`, and removes it in a `finally` once the real `.hm-loop-*` marker is written (or on create failure). `_scan_dangling_worktrees` skips any candidate dir that has a **fresh** reservation (reservation-file mtime within `_PRUNE_GRACE_SECONDS`). The reservation mtime is written ONCE at create-start, so "fresh reservation" reliably means "create started < grace ago" — NOT subject to the nested-checkout leaf-mtime problem Codex flagged. Backstops: (a) a **generous** grace = 300s (not `_GIT_TIMEOUT`=60s — Codex P2: no margin for hooks/teardown/slow FS/timestamp granularity) bounds a leaked reservation; an aged reservation is ignored AND best-effort removed; (b) the **`.git`-entry filter** stays — only reap dirs that ARE worktrees (never a random non-worktree dir), but it is NOT claimed as in-flight protection. A dir is dangling-removable iff `owned-prefix ∧ ¬registered ∧ ¬marker ∧ ¬fresh-reservation ∧ has-.git`. Lock-free throughout.
**Consequences:**
- ✅ Deterministic: the in-flight dir is protected from before it exists until its marker is written, independent of git-internal timing or checkout duration.
- ✅ The reservation's single create-start mtime is a RELIABLE freshness signal (unlike the leaf-dir mtime).
- ✅ No create-path lock → no perf regression; consistent with the lock-free prune philosophy.
- ⚠️ `create()` gains a reservation write + try/finally cleanup; a SIGKILL between reservation-write and `git worktree add` leaves a reservation that the 300s grace reaps — bounded.
- ⚠️ A `.git`-less partial dir (crashed add before `.git`) is preserved indefinitely by the filter — see ADR-001 note + Risks (operator path).
- ⚠️ Existing prune-regression fixtures need a `.git` entry (+ no fresh reservation) to still assert reaping — see Testing Strategy.
**Rejected alternatives:**
- Pure age+`.git` guard on the leaf dir (Round 1 choice) — refuted by Codex: leaf-dir mtime goes stale during nested checkout; `.git` appears early.
- Registry-lock serialization of prune↔create — rejected: forces `git worktree add` under a lock (perf) and violates the deliberate lock-free prune design.
**Source:** Interview #1, #2, #5 (Round 2)

### ADR-002: `git worktree prune --expire=<grace>` at create-time prune
**Status:** Accepted (2026-06-21, via /hm:plan interview)
**Context:** `prune_stale` runs `git worktree prune` (worktree.py:1930) before the dangling scan. A bare `git worktree prune` can de-register a peer's *recently-created* admin entry whose checkout is still in flight, turning a registered worktree into an unregistered (reapable) one — widening the race the scan-guards close.
**Decision:** Pass `--expire=<grace>` (derived from `_PRUNE_GRACE_SECONDS`) so `git worktree prune` only de-registers admin entries older than the grace, never a peer's recent in-flight one. **Execute-discovered refinement (Phase 4 concurrent test, RED):** `--expire` alone is INSUFFICIENT — a peer's HALF-WRITTEN admin entry (mid-`git worktree add`, `gitdir` file not yet present) is pruned by `git worktree prune` REGARDLESS of `--expire`, crashing the peer's add (`fatal: could not open '.git/worktrees/<name>/gitdir'`). This is a more severe facet than the rmtree (it kills the peer's create outright). Fix (reusing the ADR-001 reservation, still lock-free): `prune_stale` SKIPS the `git worktree prune` call entirely when `_any_fresh_reservation(base)` — i.e. any peer is mid-create. Deferring is brief (the reservation clears on completion) and the scan-based rmtree (reservation + `.git` guarded) still runs safely. **Fallback when the installed git rejects the computed `--expire` arg (validator suggestion):** SKIP the create-time `git worktree prune` entirely — do NOT fall back to a BARE `git worktree prune` (which re-opens the de-registration race this ADR closes). Skipping only lets stale admin entries accumulate (cosmetic), and ADR-001's reservation + `.git` scan-guard still protects the dir; the off-create `drain`/`prune-branches` path reaps the admin backlog.
**Consequences:**
- ✅ Closes the self-inflicted de-registration vector with the same grace concept as ADR-001.
- ⚠️ Stale admin entries linger up to `grace` longer before git de-registers them — cosmetic.
- ⚠️ `git worktree prune --expire` takes an approxidate; the grace seconds must be rendered into git's expire format (e.g. `now-60.seconds` / a relative form git accepts) — see Technical Design.
**Rejected alternatives:**
- Leave `git worktree prune` bare, rely on the age-guard as backstop — rejected: the age-guard protects the *dir* from rmtree, but a de-registered peer worktree is itself a correctness problem (git no longer tracks it); fix the de-registration at the source.
- Skip `git worktree prune` during create — rejected: stale admin entries would accumulate unbounded.
**Source:** Interview #1, #3

### ADR-003: Targeted marker-prune fix — preserve a marker with a pending stash ref
**Status:** Accepted (2026-06-21, via /hm:plan interview Rounds 1-2)
**Context:** Round 1 deferred the marker-prune gap as "low severity, no work loss." **Codex (Round 2) refuted that with a concrete strand chain:** in stage-only finalize a `.hm-finalize-stash-*` ref is written, then `cleanup()` removes the worktree dir, and the marker is intentionally KEPT while stash refs remain. A concurrent `prune_stale` then sees the marker's referenced dirs absent → `_is_orphan_marker` (worktree.py:1665) returns True → unlinks the marker. Later `_cli_post_commit_pop` finds `_session_marker_present` False → SKIPS restoration: the stash + ref are **PRESERVED, not dropped** (worktree.py:3084), but the deferred base-dirty work is **permanently stranded** — never auto-popped, recoverable only manually via reflog. Not destructive data loss, but the user's set-aside work silently never comes back. So the marker-prune gap strands real deferred work, not just a cheap marker.
**Decision:** A TARGETED fix (not full session-scoping): `_is_orphan_marker` returns False (preserve) when the marker's session has an associated pending `.hm-finalize-stash-*` ref, so the marker survives until `post-commit-pop` consumes the stash. Full session-uuid-scoped marker pruning is still deferred — this closes only the work-stranding chain.
**Consequences:**
- ✅ Closes the deferred-stash strand chain Codex found; post-commit-pop always finds its marker.
- ✅ Stays narrow — the marker prune is otherwise unchanged.
- ⚠️ A marker with a leaked/orphaned stash ref is preserved longer; the existing stash-ref drain (`_stash_object_exists` gc-gate) still reaps truly-dead refs, so this doesn't accumulate.
**Rejected alternatives:**
- Defer the whole marker-prune gap (Round 1 choice) — refuted by Codex: it strands deferred base-dirty restoration (work loss), not just a cheap marker.
- Full session-uuid-scoped marker pruning here — rejected: wider than needed to close the strand chain; deferred to its own PLAN.
**Source:** Interview #4, #6 (Round 2)

## 🏗️ Technical Design

**Current State:** `prune_stale` (worktree.py:1917) runs at create time: (a) `git worktree prune` (:1930, bare), (b) orphan-marker sweep (:1934), (c) `_scan_dangling_worktrees` → `rmtree` (:1941-1944, no age/`.git` guard), (d) orphan-branch sweep. `_scan_dangling_worktrees` (:1684) gates on owned-prefix ∧ ¬registered ∧ ¬marker.

**Affected Components:**
- `worktree.py` — `_PRUNE_GRACE_SECONDS = 300` constant; `create()` writes/cleans the `.claude/.hm-creating-<name>` reservation around `git worktree add` (try/finally); `_scan_dangling_worktrees` gains the fresh-reservation skip + `.git`-entry filter; `_is_orphan_marker` preserves a marker with a pending `.hm-finalize-stash-*` ref; the `git worktree prune` call at :1930 gains `--expire`. Helpers: `_reservation_path(base, name)`, `_has_fresh_reservation(base, dir)`, `_git_expire_arg(grace_s)`, `_marker_has_pending_stash(marker)`.
- Tests — `tests/unit/test_worktree_prune.py` (extend) + `tests/unit/test_worktree_prune_race.py` (reservation + window simulation) + the marker-strand test + a best-effort concurrent repro.

**Design Decisions:** See ADR-001..003.
- **Reservation:** `_reservation_path` = `base/_LOOP_MARKER_DIR/.hm-creating-<name>`. `create()` `atomic_write`s it (mtime=now) before `git worktree add`, and `unlink(missing_ok=True)` in a `finally` after the `.hm-loop-*` marker is written. `_has_fresh_reservation(base, dir)` → True iff a reservation for `dir.name` exists with `time.time() - reservation.stat().st_mtime <= _PRUNE_GRACE_SECONDS`; an aged reservation is best-effort unlinked. The reservation mtime is the create-START time (written once) — the reliable freshness signal.
- **`--expire`:** `_git_expire_arg(grace_s)` returns the approxidate git accepts (validated via `git worktree prune --expire=<arg> --dry-run`; conservative fallback if unsupported).
- **Marker strand fix:** `_marker_has_pending_stash(marker)` matches by the stash-ref **`session_marker` content field** (`_write_stash_ref_file`, worktree.py:1382) resolving to THIS marker's path — NOT a filename-stem join (validator W2). A filename-stem match (`.hm-loop-<wt>` → `.hm-finalize-stash-<wt>`) would MISS a multi-repo **sibling-only** pending stash, whose ref is `.hm-finalize-stash-<primary>-<slug>` but whose `session_marker` points at the PRIMARY marker — exactly the marker `post-commit-pop` keys on (worktree.py:3081). Validate refs via `_validate_stash_ref_fields`. `_is_orphan_marker` returns False when any validated ref's `session_marker` == this marker.
- A `stat` failure (dir/reservation vanished mid-scan) → treat as not-removable / not-fresh-but-skip (it is gone or racing).

**Data Flow (the fix):** create writes reservation → `git worktree add` → marker → reservation removed (finally). Concurrent prune: `git worktree prune --expire=<grace>` (recent peer admin entries survive) → `_scan_dangling_worktrees` (owned-prefix ∧ ¬registered ∧ ¬marker ∧ **¬fresh-reservation ∧ has-.git**) → rmtree only genuine old orphans.

**API Changes:** none public. New module-private `_PRUNE_GRACE_SECONDS`, `_reservation_path`, `_has_fresh_reservation`, `_git_expire_arg`, `_marker_has_pending_stash`. `_scan_dangling_worktrees` / `_is_orphan_marker` predicates tightened (callers unchanged).

## 📝 Implementation Plan

### Phase 1 — Pre-create reservation + scan fresh-reservation skip + `.git` filter
- `depends_on`: []
- `parallel_group`: serial-worktree
- `merge_hazards`: `worktree.py` `create()` + `_scan_dangling_worktrees` (shared file with Phases 2-3 → serial)
- Scope (in): `worktree.py` (`_PRUNE_GRACE_SECONDS=300`, `_reservation_path`, `_has_fresh_reservation`, `create()` reservation write+finally-cleanup, `_scan_dangling_worktrees` fresh-reservation skip + `.git`-entry filter); `tests/unit/test_worktree_prune.py`. (out): `--expire`, marker prune.
- **Reservation placement (validator W1 — load-bearing):** `create()` currently has NO outer try/finally (only an inner sibling-rollback `try/except` at worktree.py:323-331 that re-raises). The reservation `atomic_write` MUST precede the **primary** `git worktree add` (worktree.py:312 — the primary leaf is the dir the prune races), and a SINGLE outer `try/finally` must span lines 312-334 (`finally` → `unlink(missing_ok=True)`). It must compose with the existing sibling-rollback except (which re-raises into the new finally). Wrapping only the marker write, or starting the `try` after line 312, leaves the exact in-flight window unguarded — defeating the fix.
- Exit criterion: `uv run pytest tests/unit/test_worktree_prune.py -q` green — a dir WITH a fresh reservation is NOT reaped; a dir whose reservation is aged>grace IS reaped (and the stale reservation removed); a dir WITHOUT `.git` is NOT reaped; `create()` removes its reservation on both success and `git worktree add` failure (try/finally); existing prune-regression fixtures updated (add `.git`, no fresh reservation) so they still assert reaping.
- Risk: medium (touches `create()` hot path + tightens a destructive predicate; existing fixtures need updating)
- Rollback: base.

### Phase 2 — `git worktree prune --expire=<grace>`
- `depends_on`: [1]
- `parallel_group`: serial-worktree
- `merge_hazards`: `worktree.py` `prune_stale` :1930 + `_git_expire_arg` (same file)
- Scope (in): `worktree.py` (`_git_expire_arg`, the `git worktree prune` call gains `--expire`); `tests/unit/test_worktree_prune.py`. (out): scan/reservation (Phase 1), marker prune.
- Exit criterion: `uv run pytest tests/unit -k "expire" -q` green — `_git_expire_arg` output is accepted by the installed git (`git worktree prune --expire=<arg> --dry-run` exits 0); **a RECENT prunable admin entry (gitdir → missing path, fresh) SURVIVES the create-time prune** (Codex P2: not a normal fresh worktree, which survives a bare prune anyway); the SAME entry aged past grace IS de-registered.
- Risk: medium (git CLI-flag compatibility across versions)
- Rollback: Phase 1.

### Phase 3 — Targeted marker-strand fix (preserve marker on pending stash)
- `depends_on`: [1]
- `parallel_group`: serial-worktree
- `merge_hazards`: `worktree.py` `_is_orphan_marker` :1665 + `_marker_has_pending_stash` (same file)
- Scope (in): `worktree.py` (`_marker_has_pending_stash`, `_is_orphan_marker` preserve-on-pending-stash); `tests/unit/test_worktree_prune.py` / a marker test. (out): reservation, `--expire`.
- Exit criterion: `uv run pytest tests/unit -k "orphan_marker or marker_strand" -q` green — a marker whose referenced dirs are absent BUT which has a pending `.hm-finalize-stash-*` ref is NOT pruned (preserved); a marker with no pending stash and absent dirs IS still pruned (unchanged); RED on base for the strand case.
- Risk: medium (marker semantics; must not over-preserve genuinely-orphaned markers)
- Rollback: Phase 1.

### Phase 4 — Window-simulation + strand-chain + best-effort concurrent repro
- `depends_on`: [1, 2, 3]
- `parallel_group`: serial-worktree
- `merge_hazards`: none (test-only; new file)
- Scope (in): `tests/unit/test_worktree_prune_race.py` — (a) deterministic reservation window-simulation (peer-create writes reservation, a concurrent `prune_stale` does NOT rmtree the reserved dir; RED on base); (b) the ADR-003 strand chain — **drive the FULL sequence** (validator suggestion 5): real finalize stash-defer → `cleanup()` removes the dir → concurrent `prune_stale` → assert marker survives → `_cli_post_commit_pop` RESTORES the stash. A predicate-only unit test on `_is_orphan_marker` would NOT reproduce the strand (no RED-on-base) — wire the full chain through `_cli_post_commit_pop`/`cleanup`. **Plus a multi-repo case** (validator W2): a SIBLING-only pending stash (`session_marker` → primary marker) must preserve the PRIMARY marker. (c) best-effort concurrent stress (`INTEGRATION`-gated thread/process repro — advisory, logs a skip if it cannot trigger; never a flaky CI gate). (out): src.
- Exit criterion: `uv run pytest tests/unit/test_worktree_prune_race.py -q` green; the deterministic (a)+(b) fail on pre-fix code (prove they guard the window/chain — (b) via the full finalize→cleanup→prune→pop sequence, asserting restoration). Concurrent stress is advisory/non-gating.
- Risk: medium (concurrent-test flakiness — deterministic (a)+(b) are the real proof; stress is advisory)
- Rollback: Phase 3.

## 🧪 Testing Strategy

- **Deterministic (the real proof):** (a) reservation window-simulation — seed an owned-prefix dir with `.git`, NO registration, NO marker, but a FRESH `.hm-creating-<name>` reservation → assert `prune_stale` does NOT rmtree it; aged reservation → reaped + reservation removed; no-`.git` → preserved. (b) strand chain — a marker with absent referenced dirs but a pending `.hm-finalize-stash-*` ref → `_is_orphan_marker` False (preserved); post-commit-pop then restores. Both RED on base, GREEN after.
- **Existing-fixture update:** `tests/unit/test_worktree_prune.py` seeds "dangling worktree dirs" — audit those fixtures; any that assert reaping must now include a `.git` entry and have NO fresh reservation, or they will (correctly) no longer be reaped. The ADR-001 behavior change made visible.
- **`--expire` compat + vector:** assert `_git_expire_arg` output is accepted by the installed git via `--dry-run`; and that a RECENT prunable admin entry (gitdir→missing) SURVIVES while the same entry aged past grace is de-registered (Codex P2 — not a normal fresh worktree, which survives a bare prune regardless).
- **Concurrent stress (advisory, non-gating):** best-effort N-session repro; logs a skip if it cannot trigger the window. NOT a flaky CI gate.
- Full gate before wrapup: `ruff check`, `ruff format --check`, `mypy --strict`, full `pytest`.

## ⚠️ Risks & Mitigation

| Risk | Severity | Mitigation |
|------|----------|------------|
| Leaf-dir mtime stale during nested checkout → age-guard misses window (Codex P1) | high | RESERVATION (single create-start mtime) is the freshness signal, not the leaf-dir mtime; deterministic |
| Marker-prune deferral permanently strands deferred stash restoration — stash/ref preserved but never auto-popped (Codex P1) | high | ADR-003 targeted fix: `_is_orphan_marker` preserves a marker whose `session_marker` matches a pending stash ref + full-chain strand test |
| `_GIT_TIMEOUT`=60s grace too tight (Codex P2) | medium | grace = 300s (margin for hooks/teardown/FS latency); reservation freshness, not the timeout boundary |
| `--expire` test gives false confidence on a normal fresh worktree (Codex P2) | medium | test a RECENT PRUNABLE admin entry (gitdir→missing), not a healthy worktree |
| `.git`-filter breaks existing prune-regression tests | medium | update fixtures: add `.git`, no fresh reservation (Phase 1 exit) |
| `--expire` flag unsupported on some git versions | medium | `_git_expire_arg` validated via `--dry-run`; conservative fallback; unit test pins it |
| reservation leaked by SIGKILL between write and add | low | 300s grace reaps the stale reservation; bounded |
| `.git`-less partial dirs preserved indefinitely (Codex P3) | low | accepted, biased-to-preserve; OPERATOR PATH — `prune-branches --force` / a future long-age non-create cleanup mode sweeps them (documented, not silent) |
| concurrent stress test flaky in CI | medium | deterministic (a)+(b) are the real proof; stress advisory/non-gating |

## ✅ Success Criteria

- [x] A peer session's in-flight worktree dir (fresh reservation, unregistered, unmarked, `.git`) is NEVER `rmtree`d by a concurrent create-time `prune_stale` — deterministically, regardless of checkout duration.
- [x] `create()` removes its reservation on both success and `git worktree add` failure.
- [x] A genuine aged orphan (owned-prefix, `.git`, no fresh reservation, unregistered, unmarked) IS still reaped.
- [x] A marker with a pending (LIVE) `.hm-finalize-stash-*` ref survives a concurrent prune. **NOTE:** the marker-survival precondition is proven (`test_orphan_marker_with_pending_stash_is_preserved`); the REVIEW found + fixed a related immortal-marker bug (a DEAD stash must NOT preserve). The full end-to-end finalize→cleanup→prune→`post-commit-pop`-restores chain test (validator suggestion) was NOT separately authored — the restoration is implied by the marker surviving (which post-commit-pop keys on). Carry-forward.
- [x] `git worktree prune` at create time no longer de-registers a peer's recent in-flight admin entry (`--expire`) — AND (REVIEW execute-discovery) is skipped entirely while any peer is mid-create, closing the prune-crashes-add facet.
- [x] No new flag, no public API change, single-session behavior unchanged.
- [x] `mypy --strict` + `ruff` + full `pytest` green; existing prune + drain fixtures updated; deterministic reservation/`.git`/marker tests RED-on-base / GREEN-after.

## 🔍 Plan Validation

**Codex second opinion (invoked, Production-mandatory):** 5 findings (2×P1, 2×P2, 1×P3). All KEEP (none refuted). Two P1s refuted Round-1 design choices and drove Round 2: the age+`.git` mechanism is not sound in-flight protection (→ reservation), and the marker-prune deferral strands deferred stash restoration (→ targeted marker fix). All 5 are resolved in the current text (see ADR annotations + risk table).

**plan-validator (model opus):** **NEEDS_REVISION → resolved.** Zero critical; all 5 Codex findings reconciled KEEP + `resolved_by_plan: true` (no unresolved finding). 3 warnings + 2 suggestions, all code-grounded spec-precision (not design holes), applied:
1. **Reservation try/finally placement** — pinned: `try` opens BEFORE the primary `git worktree add` (worktree.py:312); single outer try/finally spans 312-334; composes with the existing sibling-rollback except (323-331). (Phase 1.)
2. **`_marker_has_pending_stash` join key** — match by the stash-ref `session_marker` content field (worktree.py:1382) == marker path, NOT a filename stem (multi-repo sibling-only stash would under-preserve). Multi-repo strand test added. (Technical Design + Phase 4.)
3. **Severity wording** — strand is "restoration permanently stranded (stash/ref preserved, never auto-popped, manually recoverable)", not destructive work loss. (ADR-003 + risk row.)
4. **`--expire` fallback** — on unsupported git, SKIP the create-time prune (not bare-prune, which re-opens the race). (ADR-002.)
5. **Phase 4(b) RED-on-base** — must drive the full finalize→cleanup→prune→post-commit-pop chain (a predicate-only test won't reproduce the strand). (Phase 4.)

**Verified against code at validator-cited lines:** `create` 279-335 (no outer try/finally; sibling-rollback 323-331), `_scan_dangling_worktrees` 1684-1702, `_is_orphan_marker` 1665-1668, stash-ref `session_marker` field 1382, `_cli_post_commit_pop` strand 3081-3087, `prune_stale` 1917-1944, and the existing fixture `test_worktree_prune.py:33-56` that the `.git`-filter breaks (confirming the Phase 1 fixture-update claim).
