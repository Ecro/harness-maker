---
type: research
task_slug: multisession-fleet-reverify
status: complete
created: 2026-06-21
tags: [harness-maker, research, concurrency, worktree, multisession, memory]
mtime_warn_days: 7
libs_fetched: []
sources: []
related_docs: ["[[RESEARCH-fleet-10-20-parallel-safety]]", "[[PLAN-layer3-per-session-ownership]]", "[[REVIEW-layer3-per-session-ownership-2026-06-21]]", "[[PLAN-fleet-10-20-parallel-safety]]"]
summary: "Safe-with-conditions, not unconditionally; new P0 = concurrent memory-tier RMW data loss"
---

# RESEARCH — 10-20 multi-session fleet re-verification (all stages)

## 🎯 Recommended Direction

**"마구마구 (free-for-all) is NOT problem-free — but the failures are now well-characterized, and most are friction, not data loss."** After today's three landings (C1 floor 08:30, Layer-3 per-session crumb 11:30, prune-create reservation), the **worktree machinery is code-verified solid**: a fleet of **distinct-slug, single-repo, flag-ON `execute`/`loop` operations is structurally isolated** — there is no path for one session to contaminate another's commit. The strong guarantee the prior RESEARCH gave still holds for that core case.

What the user's literal question ("아무런 문제가 없을지") trips on is **everything OUTSIDE the worktree machinery**, plus a small set of bounded in-machinery residuals. The single most important new finding — not covered by the prior fleet research, which focused only on worktree internals — is a **HIGH-severity lost-update on the shared-base memory tiers**: every stage that appends `.claude/memory/session/<date>.md` / `wiki.md` / `failures.md` does so via unlocked whole-file read-modify-write (Claude's Edit tool). Ten sessions finishing `wrapup` around the same time silently clobber each other's memory writes. This is the real "마구마구" hazard because it does not require same-slug, multi-repo, or WSL2 degradation to fire — it fires on the **normal** path whenever two stages touch memory concurrently.

Bottom line: **safe for the isolated core (distinct-slug execute/loop on one repo), with five conditions that break it — ranked below.** No new architectural commitment is made here; `/hm:plan` decides what (if anything) to fix.

## 🔍 Refinement Decisions

- **Discovery lens:** Technical architecture / implementation + Risk / compliance / data-loss. (No `--deep`; topic is concrete and has deep prior art.)
- **Scope:** re-verification of the *current* shipped state (post-2026-06-21 landings), spanning ALL six stage types the user named, not just the worktree-isolated ones.
- **User environment note:** the user runs **WSL2** (`microsoft-standard-WSL2`), which makes the C1 degraded-loop path (below) directly relevant rather than theoretical.

## 🛠️ Approaches Found

This is an audit, so "approaches" = (a) the current posture per stage, and (b) candidate remediation directions for the open hazards.

### Posture map — which stages isolate, which share the base

| Stage | Worktree isolation (default) | Shared-base writes | Concurrency verdict |
|-------|------------------------------|--------------------|---------------------|
| `execute` | YES (both presets, `scope:[execute,...]`) | deliverables (slug), iter-receipts | **Isolated** — structurally safe distinct-slug |
| `loop` (execute body) | YES | markers, finalize stash, crumb | **Isolated** + WSL2 degradation risk (C1) |
| `plan` | YES on **Production** only (`scope:[execute,plan]`); NO on Side | PLAN/RESEARCH deliverables (slug) | Isolated on Prod; slug-safe on Side |
| `research` | **NO** (not in default scope) | RESEARCH-{slug}.md (slug-keyed) | Slug-safe; no memory write |
| `spec` | **NO** | SPEC-{slug}.md (slug-keyed) | Slug-safe |
| `wrapup` | **NO** (runs on base) | **memory tiers (session/wiki/failures)**, squash-land, gitignore | **Highest risk** — memory lost-update + serial-land |

Source: code-verified — default scope literals at `templates/harness-yaml/Production.yaml.j2:83` (`[execute, plan]`) and `Side.yaml.j2:83` (`[execute]`); `_scope_includes` `worktree.py:2290`.

### Hazard register (code-verified, ranked)

| # | Hazard | Sev | Trigger condition | Loss vs friction | Mitigation present | Status |
|---|--------|-----|-------------------|------------------|--------------------|--------|
| **H1** | **Memory-tier RMW lost-update** — concurrent `wrapup` (or any memory write) on `session/<date>.md`, `wiki.md`, `failures.md` via unlocked whole-file Edit | **HIGH** | ≥2 stages writing memory near-simultaneously; **normal path**, repo-wide | **Data-loss** (silent) | None — plain `.md` tiers lack the flock that `memory/profile.py:51` / `semantic.py` already have | **OPEN (new)** |
| **H2** | **WSL2 degraded loop** — empty `HM_SESSION_ID` → loop self-stops after iter 1; two id-less sessions share global `.hm-loop-active` | MED | `loop` on WSL2 when SessionStart env-file fails (**user's env**) | Friction (loop halts) | C1 loud floor at loop-start + `/hm:health`; manual remedy | Closed (floor only; self-heal N/A) |
| **H3** | **Same-slug collision** — two sessions, identical slug → (a) work-docs whole-file clobber, (b) flag-OFF Layer-3 crumb UNION peer-pops a deferred stash | MED→HIGH | Two sessions choose the **same slug** | (a) deliverable loss (b) stash contamination | flag-ON `SharedSlugError`; distinct-slug fully isolated; empty-slug rejected | OPEN accepted-risk (SharedSlug-on-crumb follow-up) |
| **H4** | **Queue-guard fleet false-block** + serial-land wall — ≥2 pending finalize stashes from ANY session block `create`; merge-fence serializes all lands | MED | flag-OFF fleet at N=10-20 | Friction (blocked create / land latency, FIFO starvation) | `--allow-stash-queue`; foreign-count is **load-bearing safety** (C3 WONTFIX till Layer-3 trusted) | OPEN (by design) |
| **H5** | **Multi-repo C2** — sibling-base `git worktree add` vs concurrent sibling prune; no `.hm-creating-*` reservation across sibling repos | HIGH | working across **sibling repos** only | **Data-loss** | None — documented out-of-scope | OPEN |
| **H6** | **Stale-rendered harness** — install not re-rendered still sources all-markers `owned-uuids` → restores peer stash | HIGH if hit | un-re-rendered harness in the fleet | Data-loss | render-grep gate (shipped templates) + `/hm:health` stale-render flag | OPEN (inherent) |
| **H7** | **post-commit-pop empty-set ≠ unconditional skip** — legacy/empty-UUID ref still falls to vulnerable marker-exists pop (`worktree.py:3283-3297`) | LOW | legacy refs only (writer now always stamps uuid) | Data-loss (narrow) | uuid-stamping writer; bounded marker accept | OPEN (legacy-only) |
| H8 | gitignore append lost-update; cg-marks/security-findings jsonl byte-interleave | LOW | concurrent create/scan | Friction (idempotent re-add) / low corruption | idempotent; lines < PIPE_BUF | OPEN (benign) |

**SAFE under the fleet workload (code-verified):** session registry (`.hm-sessions.json`, flock+O_EXCL, dedicated `index.lock-hm-registry`), structured memory stores (profile/semantic under flock), observability JSONL via `atomic_append` O_APPEND, iter-receipts (per-iter/stage distinct paths), `harness.yaml` (make-time only, not per-stage). All 5 defense layers + prune-race reservation + registry lock confirmed PRESENT in `worktree.py`.

### Candidate remediation directions (informational — `plan` decides)

- **H1 (highest leverage):** give the plain `.md` memory tiers the same flock `memory/_locking.py` already wraps the structured stores in, OR convert the session log to `atomic_append` (line-oriented). Either kills the only normal-path data-loss hazard.
- **H3:** extend the SharedSlug guard onto the flag-OFF crumb path; add a slug-uniqueness preflight (warn when two live sessions claim one slug).
- **H4:** the C3 re-enablement is blocked until Layer-3 is fully per-session (the foreign-count is load-bearing today). Sequence matters: Layer-3 hardening first, then C3.
- **H5:** extend `.hm-creating-*` reservation to sibling bases (multi-repo only).

## ⚠️ Pitfalls

1. **"The worktree defense covers everything" — false.** `research`/`spec`/`wrapup` run on the shared base by default; only `execute` (+`plan` on Production) isolate. The most dangerous stage for memory — `wrapup` — is NOT isolated. (Prior RESEARCH-fleet-10-20 audited only worktree internals and missed H1.)
2. **"Fixing" the C3 queue-guard false-block re-opens the 3×-recurring contamination.** The foreign-stash count is load-bearing because Layer-3 `post-commit-pop` still globs all markers (`worktree.py:836-843`). Codex P0 caught this in the fleet REVIEW after two Claude reviewers cleared it. Do not naively exclude foreign stashes.
3. **A "per-session" key that partitions by a non-session key isn't per-session.** The Layer-3 crumb is slug-keyed and UNIONs uuids → same-slug sessions pop each other (Layer-3 REVIEW Finding A, grade B). Lesson already recorded.
4. **Empty owned-set does not fail-safe to "skip all."** `worktree.py:3268-3297` preserves the prior vulnerable marker-exists pop for legacy/empty-UUID refs — the empty-set skip only applies to uuid-bearing refs.
5. **WSL2 env-file failure is silent except for the loud floor.** If `HM_SESSION_ID` never lands, loops degrade; the only signal is the loop-start warning + `/hm:health` smoke. No Stop-hook self-heal is possible (Stop cwd = project root, no worktree field).

## ❓ Open Questions (for `/hm:plan`)

1. **Is H1 in scope to fix now?** It is the only normal-path, no-precondition data-loss hazard and directly answers "wrapup running concurrently." Flock vs atomic_append is the design choice.
2. **Does the user actually run same-slug concurrently?** If discipline guarantees distinct slugs, H3 drops to low. Worth a slug-uniqueness preflight regardless.
3. **Single-repo or multi-repo fleet?** H5 (C2) only bites multi-repo. The user's `multi-repo-mgmt-2026-05` work suggests this may be live.
4. **flag-ON or flag-OFF for the fleet?** flag-ON (Production default) eliminates H3's stash path and the H4 stash-queue friction structurally; flag-OFF keeps the legacy stash model where H4 friction is constant at N=10-20.
5. **Is every harness in the fleet freshly rendered?** H6 only bites stale renders; a `/hm:health` sweep across the fleet answers it.

## 📚 Sources

- (Internal-only; no external fetches.) Code-verified against `src/harness_maker/worktree.py`, `loop_marker.py`, `io_utils.py`, `memory/_locking.py`, `iter_receipts.py`, `templates/harness-yaml/{Production,Side}.yaml.j2`, `templates/stages/wrapup.md.j2`.

## 🔗 Related Internal Docs

- [[RESEARCH-fleet-10-20-parallel-safety]] — prior audit (worktree internals only; missed H1)
- [[PLAN-fleet-10-20-parallel-safety]] — C1 floor shipped, C3 reverted
- [[REVIEW-fleet-10-20-parallel-safety-2026-06-21]] — Codex P0 on C3 load-bearing foreign-count
- [[PLAN-layer3-per-session-ownership]] / [[REVIEW-layer3-per-session-ownership-2026-06-21]] — per-session crumb, same-slug residual (grade B)
- [[PLAN-worktree-prune-create-race]] — reservation; C2 sibling-base deferred
- [[PLAN-multisession-10-fleet-hardening]] — registry hardening; CLAUDECODE live-probe lesson
- `[fail:design] worktree-finalize-pulls-orphan-wip-into-main` (count:3, closed by 5-layer)
