---
type: research
task_slug: fleet-10-20-parallel-safety
status: complete
created: 2026-06-21
tags: [harness-maker, research, git-worktree, concurrency, multisession, fleet-safety]
mtime_warn_days: 7
libs_fetched: []
sources: []
related_docs:
  - "[[RESEARCH-multisession-worktree-concurrency]]"
  - "[[RESEARCH-worktree-base-artifact-pollution]]"
summary: "Safe-by-correctness for primary single-repo Claude path; real friction + 4 residual gaps bite at N=10-20; never tested above N=4."
---

# RESEARCH — Is 10–20-session parallel worktree work actually problem-free?

> Scope: can 10–20 concurrent Claude/Cursor/Codex sessions each run
> `plan/execute/loop/wrapup/research/spec` independently with **no problems**?
> This is a code-level audit of `src/harness_maker/worktree.py` (4688 LOC) +
> `loop_marker.py`, sourced from a 5-agent fan-out (registry locking, finalize/land
> fence, prune/create races, loop-marker scoping, test coverage), anchored to the
> two latest hardening commits `1905f184` ("4 concurrency hardenings for
> ~10-session fleet safety") and `ee43de1b` ("close create-time prune-vs-create
> work-loss race (lock-free)").

## 🎯 Recommended Direction

**No — not "아무런 문제 없이".** Honest verdict: **data-integrity correctness is strong
and well-defended** for the *primary single-repo, valid-id Claude-Code path* — at
N=20 you will **not** get main corruption, cross-session contamination, or commit
loss. But "no problems" is false. There are **real liveness/friction problems** that
surface specifically at fleet scale, and **four residual gaps** (two correctness-class,
two friction-class) that the codebase itself documents as deferred or only partially
covered. Critically, **nothing in the suite is tested above N=4**, and the worktree
races cap at **N=2 threads** — so the "~10-session fleet" label is *aspirational by
inspection*, not *proven by test*. 10–20 is at and beyond the design boundary.

The binding trade-off is deliberate: the design chose **best-effort lock-free prune +
strictly-serial fenced land** — correctness over throughput. At 20 sessions the serial
land becomes the bottleneck, and the *fleet-global* guards (queue-guard, degraded loop
marker) misfire because they count fleet-wide state instead of per-session state.

**Stage risk map** (which of the 6 stages actually touch the hazardous machinery):

| Stage | Worktree create? | Land/finalize? | Loop marker? | Fleet risk |
|---|---|---|---|---|
| `research`, `spec` | No (read-mostly; write `work-docs/` deliverables) | No | No | **Low** — deliverable writes only |
| `plan` | Yes (`scope: [execute, plan]`) | No | No | Medium (create-guard false-blocks) |
| `execute` | Yes | Yes (finalize, flag-off) | No | Medium-high |
| `wrapup` | — | **Yes (task-land, flag-on)** | No | **High — serial land wall** |
| `loop` | Yes (`execute-<uuid>`) | Yes (loop-close finalize) | **Yes** | **High — degraded-global collision** |

## 🔍 Refinement Decisions

- Discovery lens: **Technical architecture / implementation** (primary) + **Risk /
  concurrency** (secondary). `--deep` not set; topic was already sharp.
- Two parallel memory models analyzed (CLAUDE.md): per-task feature-branch (flag
  **ON**, Production default) and old-model 5-layer defense (flag **OFF**, Side default).
  This repo's local `harness.yaml` omits `feature_branch_workflow` → old-harness
  fallback. Findings cover both because the question is general.

## 🛠️ Approaches / Findings Found

### Finding A — Correctness on the primary path: GUARANTEED (the system's strength)

| Field | Content |
|---|---|
| Approach | Single shared fence on git-common-dir + biased-to-preserve heuristics |
| Assumption | One repo, valid-id Claude-Code sessions, flag-on feature-branch model |
| Evidence | Registry RMW serialized under dedicated `index.lock-hm-registry` (flock primary / O_EXCL secondary), `worktree.py:3554,3579-3584`. Atomic claim closes check-then-act TOCTOU `3675-3686`. Merge fence wraps the entire base-mutating section `4288`, common-dir-resolved `1304-1313`. task-land: scoped unstage of non-`touched` paths `4421-4424`, scoped conflict cleanup excluding sibling pre-staged `4152-4188`, idempotent recovery `4205-4232`. Drift-block runs *inside* the fence so B reads post-A HEAD → cannot land stale-over-A `4399-4420`. Landed-marker tip-SHA gate is name-collision-safe (12-hex uuid names) `2106-2120,312-314`. Live stash ref never drained (dir-or-marker preserve gate) `2150-2188`. prune-vs-create closed by written-once `.hm-creating-*` reservation `323-352,1824-1831`. |
| Trade-off | Strictly serial land; best-effort lock-free prune |
| Compatibility | Native to the model |
| Risk | **low** (correctness) |

This is real and well-engineered. The 3×-recurring contamination class is structurally
closed for the primary path. Do not regress it.

### Finding B — Liveness: serial land wall + non-FIFO starvation (the soft spot)

| Field | Content |
|---|---|
| Approach | All lands serialize on the shared base HEAD under one 360s fence |
| Assumption | 20 sessions reach `wrapup`/loop-close near-simultaneously |
| Evidence | Docstring `4201-4204`: "the fence covers even distinct slugs because all lands serialize on the SHARED base HEAD/index." Timeout `_FENCE_TIMEOUT = 360s` `:57` is a **per-waiter acquire budget, NOT cumulative-fair**. flock/O_EXCL acquisition is a 50ms poll loop, **not FIFO** `1034-1047` → no fairness ordering. |
| Trade-off | Safety (serial) bought at wall-clock latency + starvation exposure |
| Compatibility | Inherent to the fence design |
| Risk | **medium** — deferral, not data loss |

At N=20 the *normal* task-land hold is short (no base stash on the flag-on path; it
aborts on user dirt instead), so 19 predecessors × few-seconds ≪ 360s — unlikely to
exhaust the budget. **But** if any single holder runs long (giant capture commit, slow
NTFS git op, the 300s stash budget on the legacy path), non-FIFO polling means an
unlucky waiter can be **repeatedly out-raced and time out** even while others succeed.
Timeout fails safe: `rc=1`, branch+worktree preserved, user re-runs (idempotent). So
the symptom is *"my wrapup randomly failed, re-run it"* at scale, plus a visible
serial-land latency tax — not corruption.

### Finding C — Four residual gaps that bite at N≥3

| # | Gap | Class | Evidence |
|---|---|---|---|
| C1 | **Degraded-global loop collision.** Any id-less loop (Cursor, Codex, WSL2 env-file failure, SessionStart-hook failure) falls back to the single `.hm-loop-active`. The Stop-hook honors it existence-only, no owner key. 3+ id-less loops → **all mutually entangled**: loop A's close runs `rm -f .hm-loop-active` and deletes the guard for B/C/D → premature termination; idle id-less sessions held open by any running id-less loop. Exactly the pre-`80b80bcd` bug, re-entered for the degraded population. | **correctness/behavior** | `loop_gate.py:128-139`, `loop.md.j2:518,972-976`; provisioning failure modes `sessionid_envfile.py:55-73`, `readiness.py:550-587` |
| C2 | **Sibling-base prune-vs-add race.** `.hm-creating-*` reservation is written for the **primary base only** `worktree.py:323`. Multi-repo sibling worktrees (`{name}-{slug}`) get **no reservation** → a concurrent prune in a sibling repo can race a sibling `git worktree add`. Commit `ee43de1b` flags this as a deferred follow-up. **Real work-loss vector** for multi-repo configs. | **correctness (multi-repo only)** | `worktree.py:323,332-337`; commit `ee43de1b` residuals |
| C3 | **Queue-guard false-positive block.** `_count_pending_stashes ≥ 2` is **fleet-global, not per-session** `worktree.py:768-787,2350-2374`. Sessions A+B each with 1 legit live stash → session C's `worktree create` blocks on "≥2 unpopped finalize stashes" though neither is C's. (Old-model / flag-off path.) Escape: `--allow-stash-queue`. | **friction** | `worktree.py:785,2350-2374` |
| C4 | **uuid identity model designed but not wired at the CLI.** ADR-004's mismatched-UUID protections are **effectively inert**: every `task-*` subprocess mints a throwaway `uuid.uuid4().hex[:12]` and the pid dies between stages, so live-row protection reduces to the **pid-liveness + worktree-dir-existence heuristic** `worktree.py:3473-3484,4494,4543,4502-4526`. Biased to over-preserve (safe direction), but the *formal* guarantee is not operative; a row whose worktree dir is *also* transiently absent at reclaim time could be dropped. | **latent correctness** | `worktree.py:3739-3752,4260-4262` |

### Approach comparison — best vs worst fleet composition

| Composition | Correctness | Liveness | Net |
|---|---|---|---|
| All valid-id Claude-Code, single repo, flag-on | Strong | Serial-land latency + occasional false create-block (C3) | **Annoying, not destructive** |
| Mixed Cursor/Codex/WSL2-flaky-env | Strong *except* **C1** | Loops kill each other | **Sharpest edge — real behavior bug** |
| Multi-repo sibling bases | **C2 unguarded** | same | **Actual work-loss window** |

## ⚠️ Pitfalls

1. **"It passed CI" ≠ "it's race-free at N=20".** Max N tested anywhere is **4**
   (memory/telemetry `multiprocessing`, JSONL locks — *not* the worktree registry or
   fence). Worktree races cap at **N=2 threads** (GIL-sharing — structurally weaker than
   the cross-process reality). `test_concurrent_mutate_does_not_clobber_live_claim`
   (`test_worktree_session_registry.py:217`) is **sequential-simulation masquerading as
   a concurrency test** — its own docstring says "Two sequential registers." The two
   flagship multi-session integration files are **opt-in** (`HM_RUN_PARALLEL_SESSION=1`)
   and **not in default CI** (`test_worktree_parallel_session.py:42`,
   `test_loop_parallel_session.py:26`).
2. **Non-strict registry fallback re-opens a lost-update window.** On a wedged lock,
   every mutate *except* `claim_task_branch` silently proceeds **unfenced**
   (`worktree.py:3589-3594`). Low-probability (lock only wedges on SIGKILL'd O_EXCL
   holder or genuine 30s starvation), nonzero at N=20.
3. **Double-land prevention is prompt-routed, not runtime-enforced.** The `hm/*` vs
   `execute-*` branch-namespace partition lives in `wrapup.md.j2:410-424` (LLM-followed),
   not a code-level mutual-exclusion lock between the two land paths.
4. **`_branch_drift` fails *open* `(0,0)` on any git error** (`worktree.py:3962-3963`).
   A transient probe failure could skip the drift-block and let a behind branch land.
5. **gitignore concurrent append: no corruption, but transient lost-updates.**
   read→modify→`atomic_write` is not atomic as a unit; last-writer-wins avoids dupes and
   self-heals on the next create, so not work-loss — but don't assume the append is
   serialized.
6. **`research`/`spec` are NOT free of all risk** — they write `work-docs/` deliverables
   that are deliberately NOT gitignored; two sessions editing the shared base
   simultaneously can cross-trip the dirty-base guard (`worktree.py:2385`).

## ❓ Open Questions (for `/hm:plan` to lock down)

1. **Scope:** is the target fleet realistically all-Claude-Code single-repo (then the
   work is C3 + serial-land ergonomics), or genuinely mixed Cursor/Codex/multi-repo
   (then C1 + C2 are the priority, and they are *correctness*, not friction)?
2. **C1 fix shape:** give the degraded global a per-session key (count/owner) so id-less
   loops stop entangling? Or hard-fail loop launch when `HM_SESSION_ID` is unset
   (refuse-to-degrade) vs the current warn-and-proceed?
3. **C3 fix shape:** make the queue-guard count only the *caller's own* session's pending
   stashes instead of fleet-wide? Does that weaken the original single-session footgun it
   was built for?
4. **C2:** extend the `.hm-creating-*` reservation to sibling bases, or declare multi-repo
   out-of-scope for the fleet guarantee?
5. **Test fidelity:** is a real **N≥10 multi-process** torture test (not N=2 threads)
   worth adding to back the "fleet" claim, and should the opt-in
   `HM_RUN_PARALLEL_SESSION` suite be promoted into CI?
6. **Land throughput:** is the strictly-serial land acceptable at N=20 wall-clock, or is a
   fairness/queue mechanism (FIFO ticket) needed to bound tail-waiter starvation?

## 📚 Sources

- Internal code: `src/harness_maker/worktree.py`, `src/harness_maker/loop_marker.py`,
  `src/harness_maker/loop_gate.py`, `src/harness_maker/sessionid_envfile.py`,
  `src/harness_maker/readiness.py`, `src/harness_maker/io_utils.py`.
- Templates: `templates/stages/wrapup.md.j2`, `templates/commands/hm/loop.md.j2`.
- Commits: `1905f184` (4 concurrency hardenings, ~10-session fleet),
  `ee43de1b` (prune-vs-create lock-free), `80b80bcd` (session-scope `/hm:loop`).
- Tests audited: `test_worktree_parallel_session.py`, `test_loop_parallel_session.py`,
  `test_worktree_merge_fence.py`, `test_worktree_prune_race.py`,
  `test_worktree_session_registry.py`, `test_worktree_shared_slug_guard.py`,
  `test_worktree_task_land.py`, `test_worktree_excl_lock_reaper.py`.
- CLAUDE.md §Multi-session worktree, §Loop-marker session-scoping.
- Memory: `[fail:design] worktree-finalize-pulls-orphan-wip-into-main` (count:3).

## 🔗 Related Internal Docs

- [[RESEARCH-multisession-worktree-concurrency]] — prior (2026-06-20) general worktree
  concurrency survey with external prior-art; this doc is the deeper N=10–20 code audit.
- [[RESEARCH-worktree-base-artifact-pollution]] — keep-base-clean churn-filter work that
  stops the 5-layer defense from firing on the harness's own churn.
