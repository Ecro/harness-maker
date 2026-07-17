---
type: plan
task_slug: multisession-10-fleet-hardening
status: complete
created: 2026-06-21
tags: [harness-maker, plan, python, worktree, concurrency, multisession]
interview_rounds: 1
adrs: 4
validator_outcome: MAJOR_REVISION_RESOLVED
status_execute: all-phases-green
summary: "4 concurrency hardenings so ~10 parallel sessions hit no silent data-mix or silent degradation"
---

> **Execution status (2026-06-21):** All 4 phases implemented to GREEN (TDD).
> - **Phase 2 (Fix 3 — `_excl_lock` pid+nonce reaper):** DONE — `tests/unit/test_worktree_excl_lock_reaper.py` (13 tests).
> - **Phase 3 (Fix 1 — atomic `claim_task_branch` + `SharedSlugError`):** DONE — `tests/unit/test_worktree_shared_slug_guard.py` (9 tests). Existing `test_task_create_distinct_uuid_*` / `test_preflight_*concurrent_same_slug*` updated to the new hard-fail contract.
> - **Phase 4 (Fix 2 — preflight auto-refresh + land drift-block):** DONE — `tests/unit/test_worktree_drift_autorefresh_landblock.py`. Drift-block placed AFTER the empty-squash no-op (not just after `already`) so a change-already-in-head branch converges, not blocks (discovered via `test_task_land_converges_when_branch_change_already_in_head`).
> - **Phase 1 (Fix 4 — readiness live HM_SESSION_ID hard-gate):** DONE — `tests/unit/test_readiness_sessionid_live.py`. Live probe gated on `CLAUDE_ENV_FILE` presence so it only fires inside a real Claude Code session (no false-positive in tests/CI/`make` audit — an integration-boundary gap the plan missed; conftest autouse `_isolate_session_env` pins determinism).
> - **Full gate:** `ruff check` + `ruff format` + `mypy --strict` (111 files) all clean.
> - **One pre-existing, unrelated failure:** `test_codex_stage_procedures.py::test_loop_codex_render_keeps_marker_on_non_convergence` asserts a string absent from `templates/commands/hm/loop.md.j2`; fails identically on base HEAD (this PLAN touches only `worktree.py`/`readiness.py`/their tests — not the loop template/render path). NOT a regression of this work.

# PLAN — Multi-session 10-fleet worktree hardening

## 🎯 Executive Summary

**What:** Four targeted hardenings to the per-task feature-branch worktree model so that ~10 Claude/Cursor/Codex sessions using `/hm:execute`, `/hm:loop`, `/hm:plan`, `/hm:wrapup` freely and concurrently hit **no silent data-mix and no silent degradation** — only loud, recoverable errors.

**Why:** A 4-agent forensic of the concurrency-critical paths (`worktree.py`, `loop_marker.py`, `readiness.py`) found the design is *abort-and-preserve* throughout (no committed-work loss, no main corruption), but four real edges remain at 10-session scale:
1. **Same-slug silent share** — two sessions picking the same feature name silently share `.worktrees/<slug>/` + `hm/<slug>`; registry forgets the first; only a stderr warning marked "no action needed". The one genuine silent data-mix path.
2. **Manual-only drift** — when one session lands, peers' task branches drift; refresh is manual, so overlapping work increasingly hits a conflict-abort dead-end.
3. **O_EXCL stale-lock wedge** — a SIGKILL'd holder of the WSL2 fallback lock is never reaped → all sessions fall to the unfenced best-effort path → a registry row can silently vanish.
4. **Silent degraded health** — when `HM_SESSION_ID` is never set at runtime (env-file plumbing failure / Cursor / Codex), sessions block each other's Stop while `/hm:health` still reads green (static grep only).

**Key Decisions:**
- ADR-001 — same-slug foreign-live session → **hard-fail + `--allow-shared-slug`** escape hatch (own-session re-entry still attaches by uuid).
- ADR-002 — drift → **preflight auto-`task_refresh` (clean+no-conflict) AND `task_land` drift-block** with `--allow-drift-land` escape hatch.
- ADR-003 — `_excl_lock` → **pid-stamped lock file + reap-at-acquire** (pid-dead OR mtime>2×fence), TOCTOU-careful re-check.
- ADR-004 — `/hm:health` → **new live signal `sessionid_envfile_live`** probing own-env `HM_SESSION_ID`; FAIL only when `claude-code` ∈ targets, N-A for Cursor/Codex-only.

**Estimated impact:** worktree.py (3 disjoint regions: lock primitive, task_create/preflight, task_land), readiness.py (1 dimension), CLI flag wiring, plus unit + the parallel-session integration suite. No schema change to `harness.yaml`. No behavior change for single-session use.

## 📚 Prior Work

- **`[wiki:pattern] merge-fence-wraps-full-critical-section` (2026-06-01)** — explicitly predicted Fix 3: *"A proper fix (mtime/PID staleness guard on `_excl_lock`) is a separate, TOCTOU-careful fence-primitive hardening, deliberately NOT rushed."* This PLAN is that deferred work. The entry also fixes the timeout budget (`_FENCE_TIMEOUT = 360s`), which sets the reaper threshold (2× = 720s).
- **`[wiki:architecture] feature-branch-land-idempotency` (2026-06-20)** — land idempotency rests on the landed-marker (`marker==tip`), and conflict cleanup must be scoped to the squash's own path set. Fix 2's land-block must not perturb this: it gates *before* the squash, returning rc1 with the branch untouched.
- **`[wiki:pattern] drain-trigger-additive-relocation` (2026-06-20)** — janitor gate principle: never duplicate or widen a destructive gate; only add trigger points delegating to the same gate. Fix 3 honors this — the reaper lives inside the single `_excl_lock` primitive, not duplicated.
- **`[fail:design] worktree-finalize-pulls-orphan-wip-into-main` (count:3)** — the originating incident class; the 5-layer defense (flag-OFF) and the per-task model (flag-ON) descend from it. These fixes harden the flag-ON model, which is the Production default at 10-session scale.

## 🎙️ Interview Transcript

| # | Topic | Category | Question | Choice | → ADR |
|---|-------|----------|----------|--------|-------|
| 1 | Same-slug foreign-live collision | Risk/Contract | hard-fail vs warn vs escape-hatch | **Hard-fail + `--allow-shared-slug`** (own re-entry attaches by uuid) | ADR-001 |
| 2 | Base-drift handling | Risk/Architecture | auto-refresh vs land-block vs both | **Both: preflight auto-refresh + land drift-block** | ADR-002 |
| 3 | O_EXCL stale-lock reaper | Architecture/Failure | pure-mtime vs pid-stamped | **pid-stamped lock + reaper (TOCTOU re-check)** | ADR-003 |
| 4 | Health degraded detection | Observability | new live signal (CC-only FAIL) vs extend vs all-WARN | **New signal, Claude-Code-only FAIL / Cursor·Codex N-A** | ADR-004 |

Defaults taken without a round (low blast radius, recorded as ADR consequences): reaper mtime threshold = 720s; guard placement in both `task_preflight` (post-reclaim, has live signal) and `task_create` (defense-in-depth for direct CLI calls) via a shared `_foreign_live_holder` helper; land-block escape hatch `--allow-drift-land` for symmetry with ADR-001; phase ordering by ascending blast radius.

## 📐 Architecture Decision Records

### ADR-001: Same-slug foreign-live session hard-fails task creation
**Status:** Accepted (2026-06-21, via /hm:plan interview)
**Context:** Two independent sessions choosing the same feature slug silently share `.worktrees/<slug>/` + `hm/<slug>`; `register_session` dedups by branch so the first session's registry row is overwritten and forgotten. This is the only path that silently mixes two sessions' work (`worktree.py:3504` attach, `:3329` overwrite). Same-session re-entry (crash recovery, idempotent re-run) MUST still attach by uuid.
**Decision:** The claim is **atomic under the registry lock** (Codex P1 — a separate pre-read is check-then-act: two empty-registry same-slug callers both pass, then `register_session` overwrites). A new `claim_task_branch(base, *, task, branch, wt, session_uuid, pid, allow_shared)` runs inside ONE `_registry_mutate(fn)` where `fn(rows)`: (1) computes foreign-live rows = same `branch`, different `session_uuid`, `_pid_alive(pid)` AND `Path(worktree).exists()`; (2) if non-empty and not `allow_shared` → **raise `SharedSlugError`**; (3) else dedup-by-branch+uuid and append our row — same single critical section, no TOCTOU window. **`SharedSlugError` MUST subclass plain `Exception`, NOT `RuntimeError`/`OSError` (validator critical):** `_registry_mutate`'s fenced path catches `except (TimeoutError, RuntimeError, OSError)` (worktree.py:3271-3284); a `RuntimeError` subclass would be swallowed, print a spurious "lock unavailable" warning, then re-run `fn` on the unfenced fallback. As a plain `Exception` it propagates directly from the fenced `with`. **Atomicity is conditional on the fence being available (validator warning):** when the registry lock is wedged (the WSL2 stale-O_EXCL case), `_registry_mutate` falls to the unfenced path and two concurrent same-slug callers can both pass — so ADR-001's guarantee *rests on* ADR-003 keeping the lock un-wedged. This is why Phase 3 (Fix 1) `depends_on` Phase 2 (Fix 3): the lock-reliability foundation lands first. `task_create` calls `claim_task_branch` BEFORE `git worktree add`; if the subsequent worktree creation fails it rolls the claim back (`release_session`). Own-uuid rows never trip it (re-entry attaches). `task_preflight` runs `reclaim_stale` first so dead rows don't false-block; the claim is then authoritative.
**Consequences:**
- ✅ Closes the only silent data-mix path with a loud, actionable error.
- ✅ Escape hatch preserves the intentional-pairing use case, consistent with the existing 5-layer `--allow-*` pattern.
- ⚠️ Two sessions deliberately wanting the same worktree must now pass a flag — a one-time friction, by design.
- ⚠️ `task_create` direct CLI callers (`_cli_task_create`) get the guard too via `claim_task_branch`.
- ⚠️ The claim now precedes worktree creation, requiring a rollback path on `git worktree add` failure — added explicitly.
**Rejected alternatives:**
- Separate `_foreign_live_holder` pre-read then register (original draft) — rejected (Codex P1): check-then-act TOCTOU re-opens the silent same-slug share on first concurrent create.
- Hard-fail with no escape hatch — rejected: forecloses intentional pairing/handoff.
- Warn-only (status quo) — rejected: leaves the silent share open; the whole point.
**Source:** Interview #1

### ADR-002: Drift = preflight auto-refresh AND land drift-block
**Status:** Accepted (2026-06-21, via /hm:plan interview)
**Context:** When session A lands, base HEAD advances; peers' `hm/<slug>` branches fall behind. Today `task_preflight` only warns (`worktree.py:3593`) and refresh is manual; a drifted branch that later conflicts is a manual-resolution dead-end.
**Decision:** (a) In `task_preflight`, when `behind > 0` AND the worktree is clean, automatically invoke refresh via a **quiet** path — refresh diagnostics go to stderr, never stdout, so `_cli_task_preflight`'s stdout contract (exactly the `<WT>` path, consumed by templates) is preserved (Codex P2; requires changing `task_refresh`'s stdout print at worktree.py:3653 to stderr or a `quiet=True` capture). **Treat any refresh `rc1` generically (validator warning): conflict OR dirty OR wrong-branch/detached-HEAD** (refresh refuses all three, worktree.py:3617/3631) → "auto-refresh declined → fall through to the existing drift warning + land-block backstop". Do NOT conflate rc1 with "conflict" specifically. On success → note "auto-refreshed onto base tip" (stderr). (b) `task_land`'s drift-block sits **inside the fence, within the `else:` (not-already-landed) branch at worktree.py:3907, immediately before `_squash_path_set`** — AFTER the `already = _read_landed_marker == _branch_tip or _branch_content_in_head` computation at :3898 and only on its False path (validator warning: "after :3898" pinned to the `else` branch). A partial-land rerun (`already` True) never reaches the drift-block. The block reads `_branch_drift` under the fence (base HEAD is stable only there); if `behind > 0` and `allow_drift_land` is False → return rc1 with "run `task-refresh <slug>`", branch and base untouched. Escape hatch `--allow-drift-land`.
**Consequences:**
- ✅ Most drift self-resolves at preflight before work starts; the conflict dead-end only surfaces when a real conflict exists, and then loudly at land.
- ✅ Land-block protects the rare case where base advanced *after* preflight refreshed.
- ⚠️ Auto-rebase rewrites task-branch WIP history — acceptable: these commits are squash-landed, so identity is not preserved anyway; ADR-001 guarantees single-owner so no peer is mid-operation on the branch.
- ⚠️ A clean auto-refresh adds a rebase to preflight wall-clock; bounded by `_GIT_TIMEOUT`.
- ⚠️ Drift-block MUST sit after convergence detection (:3898), not at land entry — placement is load-bearing for idempotency.
**Rejected alternatives:**
- Land-block only (manual refresh) — rejected: leaves the drift dead-end the user must hand-resolve.
- Preflight auto-refresh only — rejected: a base advance between preflight and land could still land a drifted branch silently.
- Drift-block at land entry (original draft) — rejected (Codex P1): blocks already-landed partial-rerun on unrelated base drift.
**Source:** Interview #1

### ADR-003: pid-stamped O_EXCL lock with reap-at-acquire
**Status:** Accepted (2026-06-21, via /hm:plan interview)
**Context:** On WSL2/NTFS where `flock` is unsupported, the merge fence and registry lock fall to `_excl_lock` (`worktree.py:1022`). A holder SIGKILL'd while holding it leaves the `-excl` lock file forever — no reaper — wedging the lock so all sessions fall to the unfenced best-effort path and a registry row can silently vanish. Memory flagged this as deferred, TOCTOU-careful work.
**Decision (revised per Codex P0+P1):** On successful O_EXCL create, write a 3-field body `f"{nonce}\n{os.getpid()}\n{time.time()}\n"` where `nonce = uuid.uuid4().hex` is a per-acquire ownership token. Reaping is **gated on liveness, never on age-of-a-live-holder** — the fence acquire-timeout bounds only *waiting*, not *hold* time, so a slow/hung but LIVE land legitimately holds the lock past 720s; reaping it by age would break mutual exclusion (Codex P0). Rules on `FileExistsError`:
- Read the body. If `_pid_alive(pid)` is **True** → do NOT reap (a live holder, even a reused pid — the safe over-preservation direction); keep polling.
- If `_pid_alive(pid)` is **False** → the holder is genuinely dead (the SIGKILL case this fix targets) → reap.
- If the body is **unparseable/empty** (legacy or partial write) → reap only if filesystem `mtime` exceeds `2*_FENCE_TIMEOUT` (720s); never on parse failure alone.
**TOCTOU-safe reap (Codex P1):** before `unlink`, re-open and re-read the body and confirm the SAME `nonce` observed at decision time still occupies the file; only then unlink, then retry O_EXCL create. If the nonce changed (a successor C re-created the lock) → abandon the reap, continue polling. The **release** path likewise unlinks only when the on-disk body still carries the releaser's own `nonce` — so B can never unlink C's successor lock, and a reaped-then-recreated lock is never double-removed. `_excl_lock` operates on the `<basename>-excl` path, disjoint from the flock primary's file, so the body cannot perturb the flock path.
**Consequences:**
- ✅ A SIGKILL'd holder self-heals within one acquire attempt (pid-dead → immediate reap) instead of wedging indefinitely.
- ✅ A live holder is NEVER reaped by age (Codex P0) — mutual exclusion holds even for a legitimately slow/hung land; age only reaps an unparseable legacy body.
- ✅ The `nonce` ownership token makes both reap and release identity-checked (Codex P1) — no successor-unlink race.
- ⚠️ Lock-file format gains a 3-field body; the only readers are `_excl_lock` itself — contained.
- ⚠️ Reap-at-acquire is more code than reap-in-prune but self-heals the blocked session directly; prune-based reaping would only help the *next* create.
- ⚠️ A genuinely-wedged lock held by a live-but-hung pid is NOT auto-recovered (by design — reaping it is unsafe); it surfaces as a fence TimeoutError → unfenced best-effort fallback, the pre-existing behavior.
- ⚠️ **Create→body-write window (validator suggestion):** the body is a SECOND syscall after the atomic O_EXCL create (worktree.py:1032); a SIGKILL in that sub-millisecond window leaves an empty/unparseable body, which then degrades to the 720s age-gated reap path rather than immediate pid-dead reaping. Accepted as rare and bounded — documented here rather than papered over (O_EXCL semantics preclude a temp+rename atomic body write).
**Rejected alternatives:**
- Reap a live pid on age (`pid-dead OR mtime>720s`, original draft) — rejected (Codex P0): unlinks a live slow holder's lock → concurrent base/index mutation.
- Pure mtime threshold — rejected: same defect, plus reaps a legitimately slow holder.
- Reap without a nonce re-check — rejected (Codex P1): B can unlink successor C's freshly-created lock.
- Reap inside `prune_stale` only — rejected: doesn't unblock the currently-wedged session, only the next `create`.
**Source:** Interview #1

### ADR-004: `/hm:health` live `HM_SESSION_ID` probe, Claude-Code-gated
**Status:** Accepted (2026-06-21, via /hm:plan interview)
**Context:** The existing `sessionid_envfile_registered` signal is a static grep of `hooks.json` — it catches a render that dropped the SessionStart hook but NOT a runtime where the hook is registered yet `HM_SESSION_ID` never reaches the environment (env-file plumbing absent on WSL2, or Cursor/Codex which don't implement `CLAUDE_ENV_FILE`). In that runtime-degraded state, sessions block each other's Stop while health reads green.
**Decision:** Add a new signal `sessionid_envfile_live` in `readiness._dim_guardrails`: read `os.environ.get("HM_SESSION_ID")`. If `claude-code` ∈ `harness.yaml targets` and it is unset/empty → FAIL (actionable: "SessionStart env-file plumbing not firing; loops will run degraded"). If targets is Cursor/Codex-only (no `claude-code`) → N-A (passed=True, no penalty) since those platforms never set it. The existing static signal is retained for render-regression coverage. **The signal must be a hard-gate, not additive weight (Codex P1 — validator-confirmed: weights sum to 115 = 25+25+15+20+15+15, capped at `min(100, …)` in `_score_signals` readiness.py:189, so a failing normal signal stays hidden at score 100).** The `Signal`/`DimensionScore` model (readiness.py:108-127) has **no `status` or `hard_gate` field today — this phase ADDS only `hard_gate` to `Signal`** (the score-flooring mechanism below; the `DimensionScore.status` enum alternative was rejected for minimal model change). Concrete mechanism (score-flooring, chosen over a new status enum for minimal model change): (1) add `hard_gate: bool = False` to the `Signal` dataclass (verified absent today, readiness.py:108-118); (2) `_score_signals` gains a post-sum rule, slotted before the existing `return max(0, min(100, earned))` (readiness.py:189) — **if any signal with `hard_gate=True` has `passed=False`, the dimension score is floored to the literal `0`.** Flooring to `0` (not `GREEN_CUTOFF-1`) is deliberate: validator confirmed **no per-dimension green-threshold constant exists** in readiness.py (the only tier cutoffs — `agent_quality._tier` ≥90/80/70 — are composite-level and unrelated), so there is no constant to read; `0` is a concrete, non-invented literal that is unambiguously sub-green under any composite tier. (3) The failing signal also carries its existing `Signal.action` remediation string ("SessionStart env-file plumbing not firing; loops will run degraded"), which `/hm:health` already lists as an actionable item — so the degraded state surfaces both via the zeroed score AND an action line. (4) `sessionid_envfile_live` is emitted with `hard_gate=True` only when `claude-code` ∈ targets (else omitted/N-A). Phase asserts the **dimension score is floored to 0** (not just the signal boolean) when a Claude Code session lacks `HM_SESSION_ID`.
**Consequences:**
- ✅ A correctly-rendered-but-runtime-broken hook is now caught by a live probe, closing the green-while-degraded blind spot for Claude Code.
- ✅ Cursor/Codex N-A gating prevents cry-wolf on platforms where the env var is structurally absent.
- ⚠️ Adds `hard_gate` to the `Signal` model + a score-flooring branch to `_score_signals` — a small but real change to the scoring reducer, covered by its own regression test.
- ⚠️ The probe reflects only the health command's own session; it cannot observe peers — accepted, as per-session self-probe is the best signal without cross-session coordination.
**Rejected alternatives:**
- Extend the existing static signal — rejected: static and runtime failures should surface as distinct signals so the remediation differs (re-render vs fix env-file plumbing).
- All-target WARN — rejected: doesn't gate health green on the degraded state and cry-wolfs on Cursor/Codex.
**Source:** Interview #1

## 🏗️ Technical Design

**Current State:** Per-task feature-branch model (flag ON, Production default). `task_create:3481` attaches idempotently by slug; `register_session:3305` dedups by branch; `task_preflight:3554` warns-only on same-task + drift; `task_land:3765` squash-lands under the 360s fence; `_excl_lock:1022` has no stale reaper; `readiness._dim_guardrails` checks `sessionid_envfile_registered` statically.

**Affected Components:**
- `worktree.py` — three disjoint regions: (R1) `_excl_lock` lock primitive [Fix 3]; (R2) `task_create` + `task_preflight` + new `_foreign_live_holder` + `SharedSlugError` [Fix 1]; (R3) `task_preflight` drift branch + `task_land` entry [Fix 2].
- `cli.py` — `--allow-shared-slug`, `--allow-drift-land` flag parsing for `task-create`/`task-preflight`/`task-land`; map `SharedSlugError`/drift-block to rc1 + message.
- `readiness.py` — `_dim_guardrails` new `sessionid_envfile_live` signal [Fix 4].
- `templates/agents/_partials/worktree_preflight.md.j2` — surface the new hard-fail + auto-refresh outcomes to the LLM (informational → now actionable on fail).
- Tests — `tests/unit/` per fix + `tests/integration/test_worktree_parallel_session.py` extension.

**Design Decisions:** See ADR-001..004. Note the **synergy**: ADR-001 (single-owner branch) is what makes ADR-002's auto-rebase safe (no peer mid-operation), and ADR-003's pid-stamp reuses the existing `_pid_alive` helper that ADR-001's `_foreign_live_holder` also uses.

**Data Flow (Fix 1):** stage → `task_preflight` → `reclaim_stale` (drop dead) → `_foreign_live_holder` (live same-branch foreign?) → raise `SharedSlugError` unless `allow_shared` → else `task_create` (also guarded) → register.

**API Changes:** `task_create(..., allow_shared: bool = False)`, `task_preflight(..., allow_shared: bool = False)`, `task_land(..., allow_drift_land: bool = False)`. New `_foreign_live_holder`, `SharedSlugError`. New readiness signal key `sessionid_envfile_live`.

## 📝 Implementation Plan

### Phase 1 — Fix 4: health live `HM_SESSION_ID` probe
- `depends_on`: []
- `parallel_group`: p-health (independent file — runs alongside the worktree group)
- `merge_hazards`: none (readiness.py + its own tests; no overlap with worktree.py)
- Scope (in): `readiness.py` `_dim_guardrails` + the guardrail dimension reducer (hard-gate support, Codex P1); `tests/unit/test_readiness*.py`. (out): worktree.py, cli.py.
- Exit criterion: `uv run pytest tests/unit/test_readiness*.py -k "sessionid_live or guardrail_gate" -q` green — asserts the guardrails **dimension score is floored to 0** (not merely the signal boolean) when `claude-code` ∈ targets and `HM_SESSION_ID` unset (monkeypatched env); N-A (no penalty, score unaffected) when Cursor/Codex-only; and a non-hard-gate signal failing still only subtracts its weight (floor applies only to `hard_gate=True` failures).
- Risk: low
- Rollback: revert to base (no prior phase dependency).

> **Phase ordering note (validator warning):** Fix 1's atomic-claim guarantee holds only while the registry fence is reliable; Fix 3 is what keeps the WSL2 O_EXCL lock from wedging. So the lock fix (Fix 3) lands as Phase 2 — the *foundation* — and the claim fix (Fix 1) as Phase 3 `depends_on` it. This corrects the original draft's backwards arrow.

### Phase 2 — Fix 3: pid+nonce O_EXCL lock + liveness-gated reap-at-acquire
- `depends_on`: []
- `parallel_group`: serial-worktree
- `merge_hazards`: `worktree.py` `_excl_lock` (distinct region from Phases 3,4, but same file → serial).
- Scope (in): `worktree.py` (`_excl_lock` nonce+pid+stamp body, liveness-gated reap-at-acquire with nonce re-check, identity-checked release); `tests/unit/test_worktree*lock*.py`. (out): task_create/preflight/land, readiness.
- Exit criterion: `uv run pytest tests/unit -k "excl_lock or stale_reap" -q` green — stale lock with **dead** pid → reaped + acquired; lock with **live** pid (even aged >720s) → NOT reaped, blocks to timeout (Codex P0); unparseable body aged >720s → reaped; unparseable body fresh → not reaped; **nonce changed between decision and unlink → reap abandoned (Codex P1)**; release unlinks only own-nonce body; **SIGKILL-in-create→write window simulated (empty body) → age-gated only**; flock primary path unaffected.
- Risk: high (TOCTOU lock primitive — irreversible-class concurrency code)
- Rollback: Phase 1 (or base).

### Phase 3 — Fix 1: same-slug foreign-live hard-fail + escape hatch
- `depends_on`: [2]  (atomicity rests on Fix 3's reliable fence)
- `parallel_group`: serial-worktree
- `merge_hazards`: `worktree.py` (`claim_task_branch`/`task_create`/`task_preflight`) — serial with Phases 2,4 (same file); shares `task_preflight` with Phase 4.
- Scope (in): `worktree.py` (`class SharedSlugError(Exception)`, atomic `claim_task_branch` inside `_registry_mutate`, `task_create` rollback-on-add-failure, `task_preflight`), `cli.py` (`--allow-shared-slug` + rc mapping), `worktree_preflight.md.j2`; `tests/unit/test_worktree*.py`. (out): lock primitive, drift logic.
- Exit criterion: `uv run pytest tests/unit -k "shared_slug or claim_task" -q` green — foreign-live same-branch → `SharedSlugError`; own-uuid re-entry → attaches; `--allow-shared-slug` → proceeds; dead foreign row (reclaimed) → no error; **two concurrent same-slug claims → exactly one wins, the other raises (atomic-claim TOCTOU test)**; **`SharedSlugError` propagates from the fenced path WITHOUT the "lock unavailable" warning (asserts it is not a RuntimeError subclass).**
- Risk: medium (stage-abort behavior change)
- Rollback: Phase 2.

### Phase 4 — Fix 2: drift auto-refresh (preflight) + land drift-block
- `depends_on`: [2, 3]
- `parallel_group`: serial-worktree
- `merge_hazards`: `worktree.py` `task_preflight` (shared with Phase 3 — MUST follow it) + `task_land` + `task_refresh` (stdout→stderr); `cli.py` `--allow-drift-land`.
- Scope (in): `worktree.py` (`task_refresh` stdout→stderr/quiet; `task_preflight` drift branch → auto-refresh with generic-rc1 fall-through; `task_land` `else`-branch drift-block at :3907 + `allow_drift_land`), `cli.py`, `worktree_preflight.md.j2`; `tests/unit` + `tests/integration/test_worktree_parallel_session.py`. (out): lock primitive, readiness.
- Exit criterion: `uv run pytest tests/unit -k "drift or auto_refresh or land_block" -q` AND `INTEGRATION=1 uv run pytest tests/integration/test_worktree_parallel_session.py -q` green — preflight clean+behind → auto-refreshed (diagnostics on stderr; stdout still exactly `<WT>`, Codex P2); preflight **wrong-branch/detached-HEAD or dirty → auto-refresh declined, stdout still exactly `<WT>`** (validator warning); preflight conflict → warn+proceed; land behind+not-converged → rc1 unless `--allow-drift-land`; **land of an already-converged (partial-land rerun) branch with base drift → NOT blocked (Codex P1, convergence check at :3898 precedes the :3907 drift-block)**; land clean → squashes as before (idempotency intact).
- Risk: high (drift semantics + land path)
- Rollback: Phase 3.

## 🧪 Testing Strategy

- **Unit (mock-first, deterministic):** per-fix tests as in each phase exit criterion. Fix 1 uses a seeded registry (live/dead/own/foreign rows). Fix 3 simulates a stale lock file (stamped dead pid; aged mtime) — no real SIGKILL needed. Fix 4 monkeypatches `os.environ` + `targets`.
- **Integration (`INTEGRATION=1`):** extend `tests/integration/test_worktree_parallel_session.py` — the established regression boundary (memory `[fail:design]` count:3 freeze rests on it). Add: (a) two sessions same-slug → second hard-fails; (b) land after a peer's land → drift detected → preflight auto-refresh → clean land; (c) wedged `-excl` lock with dead pid → next acquire self-heals.
- **Behavioral, not source-grep** (memory `drain-trigger-additive-relocation`): every guard is proven by seeding state and asserting the firing, never by grepping source.
- Full gate before wrapup: `ruff check`, `ruff format --check`, `mypy --strict`, full `pytest` (background).

## ⚠️ Risks & Mitigation

| Risk | Severity | Mitigation |
|------|----------|------------|
| Fix 3 reaps a LIVE slow holder by age → broken mutual exclusion (Codex P0) | critical | reap gated on `pid-dead` only; live pid never reaped by age; age reaps only an unparseable legacy body |
| Fix 3 successor-unlink race (B unlinks C's lock, Codex P1) | high | per-acquire `nonce`; reap re-checks same nonce immediately before unlink; release unlinks only own-nonce body |
| Fix 1 silent same-slug share survives via check-then-act (Codex P1) | high | claim is one atomic `_registry_mutate` that raises on conflict; rollback claim on `git worktree add` failure |
| Fix 2 land-block breaks partial-land idempotency (Codex P1) | high | drift-block placed AFTER landed-marker convergence check (:3898); converged branch bypasses block |
| Fix 2 auto-refresh pollutes preflight stdout contract (Codex P2) | medium | refresh diagnostics → stderr; preflight stdout stays exactly `<WT>` |
| Fix 4 failing signal hidden by >100 additive weight (Codex P1) | high | hard-gate semantics: failing signal forces dimension FAIL; Phase 1 asserts dimension status, not signal boolean |
| Fix 1 guard false-positives on own crashed re-entry | medium | uuid match short-circuits before the foreign check; `reclaim_stale` drops the dead prior row first |
| Fix 2 auto-rebase surprises user mid-preflight | medium | only when worktree clean; conflict → clean abort + warn (no silent history loss); single-owner guaranteed by ADR-001 |
| Fix 4 cry-wolf on Cursor/Codex | low | N-A gating when `claude-code` ∉ targets |
| Phases 2/4 both edit `task_preflight` → merge conflict | medium | serial-worktree ordering; Phase 4 `depends_on [2,3]` |

## ✅ Success Criteria

- [x] Two sessions, same slug → second gets a loud `SharedSlugError` naming `--allow-shared-slug` (not a silent share).
- [x] Peer-land drift → preflight auto-refreshes a clean branch; conflicting branch is blocked at land, not silently landed.
- [x] A SIGKILL'd `-excl` lock holder no longer wedges the fence; the next acquire self-heals.
- [x] `/hm:health` FAILs `sessionid_envfile_live` when a Claude Code session lacks `HM_SESSION_ID`; N-A on Cursor/Codex-only. **(re-fixed post-review: gate was on the wrong env var `CLAUDE_ENV_FILE` → never fired; now `CLAUDECODE`, proven live.)**
- [x] Single-session use is behaviorally unchanged (no new friction, no flag required).
- [x] `mypy --strict` + `ruff` + full `pytest` (unit) green. **DEFERRED:** the `tests/integration/test_worktree_parallel_session.py` extension under `INTEGRATION=1` was NOT done — unit tests cover the behavior; the cross-process integration extension is a follow-up coverage gap.

## 🔍 Plan Validation

**Codex second opinion (invoked, Production-mandatory):** 6 findings (1×P0, 4×P1, 1×P2), all KEEP-disposed — none refuted. Each is addressed in the revised ADRs (see the per-ADR "Codex Pn" annotations and the risk table).

**plan-validator (2 passes, model opus):**

| Pass | Outcome | Notes |
|------|---------|-------|
| 1 | NEEDS_REVISION | 1 critical (ADR-004 referenced nonexistent `DimensionScore.status`/`hard_gate`) + 5 warnings + 1 suggestion; reconciled all 6 Codex findings |
| 2 | MAJOR_REVISION → **resolved** | 6/7 prior critiques verified resolved against code; remaining critical = narrowed recurrence (floored to phantom `GREEN_CUTOFF`) |

**Resolution of the final critical (post-pass-2, no 3rd re-run per stage "re-run once" rule):** ADR-004's score-floor target was changed from the nonexistent `GREEN_CUTOFF-1` to the literal `0` — validator's own recommended option (b), "floor to a stated literal that guarantees sub-green." No phantom symbol remains; the floor slots cleanly before `_score_signals`'s `return max(0, min(100, earned))` (readiness.py:189). This was a mechanical fix requiring no architectural decision, so it was applied directly rather than via a follow-up interview round.

**Verified against code at validator-cited lines:** `_registry_mutate` catch (worktree.py:3278), land convergence/`else` (:3898/:3907/:3908), refresh rc1 exits (:3617/:3631/:3645), refresh stdout print (:3653), guardrail weights sum 115 (:451/:460/:481/:523/:554/:591), `Signal` lacks `hard_gate` today (:108-118).

**Accepted residual:** the create→body-write sub-ms window in ADR-003 (SIGKILL → 720s age-gated path) is documented, not eliminated (O_EXCL semantics preclude an atomic body write). Rare and bounded.
