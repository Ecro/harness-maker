---
type: review
task_slug: multisession-marker-scoping
status: CHANGES_REQUESTED
created: 2026-08-07
reviewers_invoked: [code-reviewer, security-reviewer, codex]
consensus_method: cross-check
drift_verdict:
  result: clean
  scope_violations: []
  scenario_misses: []
  task_slug: multisession-marker-scoping
  computed_at: 2026-08-07T22:35:00Z
---

# REVIEW — multisession-marker-scoping

## 🎯 Round 1 Summary

**Grade: B** (threshold A). `P0_count = 0`, `P1_count = 2` consensus-passed.

Voter pool **N = 3**, K = 2: `code-reviewer`, `security-reviewer`, and `codex`.
`antigravity` was invoked and **skipped** — `exit 1: Error: timeout waiting for response`
on a ~190 KB prompt, the native 240 s `--print-timeout` firing. Warn-and-proceed per
`second_opinion.failure_policy`. **Its silence is not agreement** and it cast no vote; the
pool is 3, not 4.

Seven findings survived Pass 2. Three of the four severe ones were **reproduced by
executable probe** before any fix was written, so they are not review opinion:

| Probe | Result |
|---|---|
| id-less claim then Write inside own worktree | `rc=2` — **blocked from its own worktree** |
| `autopilot off` with no `--session-id` | prints success; `status.active` still `True` |
| relative `../peer/src/f.py` from a worktree cwd | `rc=0` allow, while the tool writes into `.worktrees/peer/` |

## 🔍 Drift Findings

`drift_verdict: clean`. All nine changed source files map to a PLAN phase scope. Two
divergences, neither a defect, recorded so they are not rediscovered:

- **`tests/snapshot/*` (8 files) — outside stated scope.** Mechanical regeneration
  downstream of the template + gitignore changes. No PLAN phase lists them; the alternative
  is a permanently red suite. Informational, not a violation.
- **`gates/permission_gate.py` — in ADR-009's consumer list, unchanged.** It calls only
  `resolve_marker_root`, which is key-free by design and now pinned as such by
  `test_resolve_marker_root_stays_key_free`. The ADR's enumeration over-listed it. A PLAN
  inaccuracy, not an incomplete phase.

Step 2.5's silent-intent-miss hook is **N-A** — the PLAN carries no `common_ground_marks`.

## ✅ Consensus Findings

### P1 — `consensus-passed [2/3]`

**CR-1 · `src/harness_maker/worktree.py:2797` — an id-less claim leaves the prior owner's
task marker standing, and the gate then blocks the claiming session from its own worktree.**

The marker WRITER takes its id from `$HM_SESSION_ID` (a shell variable); `worktree_gate`
takes its id from the PreToolUse payload. Those two sources fail **independently**: in the
documented `sessionid_envfile` failure the writer sees `""` while the gate still sees a real
`session_id`. ADR-008's transition table says "without an id → no marker"; the implementation
did "leave the previous owner's marker", which is a different thing. The claiming session is
then fully identified to the gate, finds its own worktree in the peer set, and is denied
every `Write`/`Edit` inside it — with no in-band recovery, because the block message's remedy
needs the id it structurally cannot obtain. Reproduced.

*security-reviewer set P1 rather than code-reviewer's P0 on the grounds that an ungated Bash
`rm` of the marker does recover it; both kept the finding and the mechanism verbatim.*

**CR-2 · `src/harness_maker/worktree.py:4541` — task-marker takeover has no liveness check,
so a peer's preflight locks the live owner out of its own worktree.**

`task_create` rewrote the worktree-keyed marker unconditionally. The only upstream restraint
is `claim_task_branch`'s pid liveness — and **ADR-008's own Context says that pid is the
exited CLI subprocess**, so a live peer's row reads dead and `SharedSlugError` never fires.
Session B's preflight on a slug A holds flips the header to B; A's next write inside its own
worktree exits 2, and the block message tells A to re-run preflight — the same seizure in
reverse, a flip-flop rather than a resolution. ADR-013 authorises takeover-on-claim as
recovery for a marker that cannot expire; it never considered a LIVE peer.

### P2 — `consensus-passed [2/3]`

- **CX-1 · `gates/worktree_gate.py`** — a relative `file_path` was resolved against the
  *stripped* base root rather than the tool's own cwd, so `../their-task/f.py` from a
  worktree cwd resolved outside the repo and was allowed. Raised by **codex** at P1; both
  reviewers kept it at P2 because the captured live payload carries an absolute path, making
  the branch close to unreachable in Claude Code. Latent, not shipped. Reproduced.
- **CR-3 · `tests/structural/test_autopilot_marker_api_session_key.py`** — the import-graph
  guard compared LOCAL names, so `from harness_maker.autopilot import load as _load` evaded
  it; and a key hardcoded to `None` read as compliant.
- **SR-3 · `src/harness_maker/autopilot.py`** — per-session markers had no reaper.
  `gc_stale_marker` collects a marker only when its OWN session next runs a command, and a
  crashed session never does, so `.claude/` grew one file per session forever. The docstring
  claiming a peer's marker "survives to its TTL" described a sweep that did not exist.

## ⚠️ Weak Consensus

**SR-1 · `src/harness_maker/cli.py:2475` — `autopilot off` silently no-ops and reports
success.** *Severities diverge: security-reviewer **P0**, code-reviewer **P1**.*

Step 4a admits only same-tier pairs and forbids bridging, so this cannot be
`consensus-passed` — but both reviewers kept the finding and reached the **same CONCLUDE**.
`clear(root, session_id=None)` resolves to `.hm-autopilot-degraded`; the README documents the
disarm as `harness-maker autopilot off` with no `--session-id`, and `HM_SESSION_ID` is a
shell variable `os.environ` never sees, so the env fallback cannot rescue a user-typed
invocation. The live `.hm-autopilot-<id>` is untouched while the CLI prints
`autopilot: off (marker cleared)`. Before this change the same command worked. This is a
regression in the documented kill switch for an agent that auto-advances stages. Reproduced.

## 📝 Manual-Only Findings

- **NEW-1 (P2, code-reviewer) · `gates/worktree_gate.py`** — ADR-004's own-membership-wins
  precedence can never fire for task markers: ADR-010 keys the filename by worktree with a
  single owner header, so `mine ∩ peers` is always empty for that family. The two windows
  ADR-004 cited as its justification (restart-before-takeover, `--allow-shared-slug`) are
  therefore **not** mitigated by it — which is precisely why CR-1 and CR-2 were classified
  as covered when they were not. A documented invariant enforced nowhere.
- **NEW-SR-4 (P2, security-reviewer) · `gates/worktree_gate.py`** — marker path lines are
  unconstrained, so any process that can write in the repo can deny a peer writes to an
  arbitrary directory by naming it in a marker. Suggested bound: keep only paths under
  `<root>/.worktrees`.

## 🤝 Disagreements

| Finding | code-reviewer | security-reviewer | Resolution |
|---|---|---|---|
| SR-1 `autopilot off` | P1 — "the mandatory wrapup/review gates still bound the pipeline" | P0 — "a documented safety control, disabled on its only documented invocation path" | **Not bridged** (Step 4c). Kept as weak-consensus at both tiers; sets `unverified_severe`. |
| CR-1 id-less claim | P0 — "no in-band recovery" | P1 — "an ungated Bash `rm` does recover it" | Both tiers are severe and the mechanism is agreed; the P1 pair carries the consensus. |
| CX-1 relative path | P2 (from codex's P1) | P2 (from codex's P1) | Both reviewers independently demoted the cross-model severity; recorded as P2. |

**SR-2 was dropped by BOTH Pass-2 reviewers** as a duplicate of CR-2 — one root cause at one
line, reached through two call paths. Merging it prevented double-weighting a single defect
in the consensus count.

## 🧊 Cross-model findings (frozen @ round 1)

Rounds 2..N re-read this section instead of re-invoking a model. Each model is invoked
**exactly once per `/hm:review`**.

### `codex` — status: `invoked`

| field | value |
|---|---|
| `id` | `a38d7b103929f5bd` |
| severity (as filed) | P1 |
| file / line | `src/harness_maker/gates/worktree_gate.py:214` |
| summary | Relative tool paths are resolved against the wrong directory, allowing writes into a peer worktree |
| PIDA disposition | **`accepted`** |
| oracle | probe: relative `../peer/src/f.py` from `cwd=.worktrees/mine` resolved outside the repo (`rc=0` ALLOW) while the tool writes `.worktrees/peer/`. Reproduced. |
| Step 4 outcome | folded in; both reviewers kept it at P2 → `consensus-passed P2` |

### `antigravity` — status: `skipped`

| field | value |
|---|---|
| reason | `exit 1: Error: timeout waiting for response` |
| findings | none — **cast no vote** |

The 240 s native `--print-timeout` fired on a ~190 KB prompt. Warn-and-proceed. Recorded so
a later reader does not mistake an absent voice for an agreeing one.

## Review Iteration Summary

*(completed after round 2)*

---

## Auto-Fix Loop

### Iteration 2 (Grade: B → B)

Fixes applied: 6 · re-reviewed by both reviewers.

| # | Sev | Summary | File | Status |
|---|-----|---------|------|--------|
| 1 | P1 | CR-1 — id-less claim unlinks the stale marker | `worktree.py` | Applied |
| 2 | P1 | CR-2 — foreign header not taken over without `allow_shared` | `worktree.py` | Applied |
| 3 | wk | SR-1 — `off` exits 4 and names what is armed | `autopilot.py`/`cli.py` | Applied **out-of-band** (weak-consensus is not auto-fix eligible; oracle-verified, recorded rather than retagged) |
| 4 | P2 | CX-1 — relative target resolves against the raw cwd | `worktree_gate.py` | Applied |
| 5 | P2 | CR-3 — import-graph guard tracks aliases + literal `None` | structural test | Applied |
| 6 | P2 | SR-3 — TTL reaper wired into `prune_stale` | `autopilot.py`/`worktree.py` | Applied |

Remaining: 2 · **New issues introduced: 2** — and this is the round's real result.

- **NEW P0 (security-reviewer)** — fix #2's guard locks a *resuming* session out of its own
  task worktree, permanently. A new session id every day makes that the ordinary path, and
  the block message's remedy is the very no-op that caused it.
- **NEW P1 (both reviewers)** — fix #1's unlink is an ungated delete of live peer state,
  handing the least-authenticated caller the most destructive authority. It contradicts
  `_clear_task_marker`'s own docstring in the same commit.
- **SR-1 held open** — exit-4-and-explain was honest, but the chain still auto-advanced for
  the full 18h TTL. A kill switch that cannot kill is the defect; reporting it accurately
  is not the fix.

The suite was **fully green** across all of this. `[fail:test]
fix-introduced-defect-passes-all-gates`, count:4 → **count:5**.

### Iteration 3 (Grade: B → B)

Fixes applied: 5 · re-reviewed by both reviewers.

| # | Sev | Summary | File | Status |
|---|-----|---------|------|--------|
| 7 | P1 | **Reverted** fix #1's unlink | `worktree.py` | Applied · caused_by=#1 |
| 8 | P0 | Gate grants membership from the caller's **cwd** | `worktree_gate.py` | Applied · caused_by=#2 |
| 9 | P2 | Guard compares **sanitized** ids on both sides | `worktree.py` | Applied · caused_by=#2 |
| 10 | P1 | `off` actually disarms (project-wide with no `--session-id`) | `autopilot.py` | Applied · caused_by=#3 |
| 11 | P2 | README + docstrings; guard tests made falsifiable | several | Applied |

Remaining: 4 · **New issues introduced: 3.**

## 🚨 Round 3 findings — the headline defect is NOT closed

**cwd self-membership is inert on the flow this harness renders.** Both reviewers, with
source evidence I did not have: `templates/agents/_partials/pf_tail.md.j2` is the shipped
contract for every task stage — *"stdout = the task worktree absolute path. Treat that exact
string as `<WT>` for every Read/Write/Edit"*, with `!cd <WT> && …` for **Bash only**. The
session's own cwd stays at the base (`task-preflight <slug> "$(pwd)"`). So `here` is never
inside the worktree, membership never fires, and a session resuming an existing task with a
rotated id is blocked from every write into its own worktree. Fix #8 does not fix the thing
it was written to fix.

*security-reviewer P1, code-reviewer P0 — tiers diverge, so `weak-consensus`, not
consensus-passed. Both agree on the mechanism.*

**The reviewer-supplied fix, NOT applied:** in `task_preflight`, call
`_write_task_marker(..., allow_shared=True)` — the registry claim IS the authorisation —
and keep the refusal only for a bare `task_create` with no preflight. This is left for a
human because applying a fourth unreviewed change at the round cap is the exact pattern
that produced iteration 2.

### `consensus-passed P1`

- **`gates/worktree_gate.py:211` — membership compares an `.absolute()` cwd against
  `.resolve()`d marker paths.** `is_relative_to` is lexical: a symlinked home, a `..`
  segment, or a case-insensitive mount silently denies self-membership and blocks a session
  from its own worktree. Both reviewers, same line, same tier. The one mechanism round 3
  relies on to prevent a lockout is defeated by an unresolved comparison.

### `manual-only P1`

- **`tests/unit/test_worktree_gate.py:126` — `test_own_membership_wins_over_a_peer_claim`
  builds a state no writer can produce.** It fabricates a `.hm-loop-*` and a `.hm-task-*`
  marker for one path with different owners; `task_create` writes only `.hm-task-*`. The one
  test positioned to catch this regression asserts a shape that cannot occur — so the
  regression ships green.
- **`gates/worktree_gate.py:299` — the block message's remedy is the command that just
  refused.** Following it re-enters the same refusal: an infinite loop with no in-band
  escape. Same defect shape round 2 found in the writer, left in the reader.

### `manual-only P2`

- `gc_stale_marker`'s docstring and the module partition table still describe
  header-only membership.
- `prune_stale --dry-run` omits expired autopilot markers from the report (the block sits
  under `if not dry_run`).
- The sanitized-header comparison is unfalsifiable — every fixture id is tame and sanitizes
  to itself.
- The alias/dotted guard tests lack negative controls; `_cli_off`'s mid-sweep `OSError`
  branch loses the already-removed names, so a half-disarmed project reports only failure.

## ⚠️ An unverified premise this all rests on

ADR-005's probe recorded the payload's **key set** and I then reasoned about the `cwd`
**value** — the fixture's `cwd` is a placeholder I wrote, not an observation. Round 3's whole
mechanism depends on what `cwd` actually is at PreToolUse time, and the reviewers' reading of
`pf_tail.md.j2` says it is the base. This is `[fail:design] runtime-env-gate-dead-on-arrival`
(count:2) — *a runtime input must be probed in the target execution context* — recurring
inside the PLAN that cites it. **The gate is not wired into this project's `settings.json`,
so it cannot be probed here.** Settling it needs a live probe in a harness where the hook
fires, and that should precede any further fix.

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | B     | —             | 7         | —   |
| 2         | B     | 6             | 2         | 2   |
| 3         | B     | 5             | 4         | 3   |

Final grade: **B** (`P0_count = 0`, `P1_count = 1` consensus-passed)
Iterations used: 4 / 3 — **round 4 was authorised by the user past the cap**
Exit reason: **cap-exhausted** (round 3), then user-authorised round 4
Status: **CHANGES_REQUESTED**
human_review_needed: **true**
Counters: unreviewed 0 · prior-fix 5 · unattributed 0

`cap-exhausted`, not `no-progress`: every round produced lifecycle transitions, and round 3
closed four round-1 findings outright. A higher cap would plausibly have helped — but the
recurring shape here is that each round's fix introduced the next round's defect, so the
honest recommendation is a human decision on the mechanism, not a fourth automated attempt.


---

## Iteration 4 (user-authorised past the cap) — Grade: B → B

The user directed: apply the round-3 reviewer's suggested fix and re-review.

| # | Sev | Summary | File | Status |
|---|-----|---------|------|--------|
| 12 | P0 | `task_preflight` claims the marker (`claim_marker=True`) | `worktree.py` | Applied · caused_by=#2 |
| 13 | — | Authorities **split**: `allow_shared` (branch) vs `claim_marker` (marker) | `worktree.py` | Applied — passing `allow_shared` through would also have disabled the branch guard (round-2 P2) |
| 14 | P1 | `here = Path(cwd).resolve()` | `worktree_gate.py` | Applied · caused_by=#8 |
| 15 | P1 | Block message named `--allow-shared-slug` | `worktree_gate.py` | Applied, then **retracted** — see below |
| 16 | P1 | `test_own_membership_wins_over_a_peer_claim` rebuilt on a producible shape | test | Applied |

**Closed (both reviewers):** the round-3 P0 resume lockout · the `.absolute()`/`.resolve()`
consensus P1 · the fabricated-state test · the no-op remedy loop.

### Still open after round 4

- **`consensus-passed P1` — the bound I claimed for the re-admitted takeover is vacuous in
  production.** `task_preflight` runs `reclaim_stale` first, and a registry row's pid is the
  one-shot `!uv run … task-preflight` subprocess, already exited. The row is dropped,
  `_foreign_live_rows` is empty, and **every** second session that preflights an existing
  slug seizes the header silently. `test_a_live_peer_still_blocks_the_claim_at_the_registry`
  passes only because pytest is the registering process — it asserts a precondition the
  shipped path never satisfies. Both reviewers, independently, at the same line. The source
  comment asserting the bound has been **retracted and replaced with the refutation**.
- **`weak-consensus` (security P1 / code P2) — the remedy I added in fix #15 was worse than
  the no-op it replaced.** `--allow-shared-slug` skips `_foreign_live_rows` *entirely*, so
  two live sessions following the printed instruction evict each other in turn. **Retracted**:
  the message now names plain `task-preflight` and explicitly warns against forcing with the
  flag.
- **`manual-only P1` — the degraded (empty `$HM_SESSION_ID`) resume is still locked out.**
  `_write_task_marker` returns early on a falsy id, so yesterday's header survives while the
  gate still sees a real payload id. No test in the suite passes an empty id.
- **`manual-only P2`** — `_cli_task_create` re-couples the two authorities
  (`claim_marker=allow_shared`); `prune_stale --dry-run` omits expired autopilot markers;
  `_cli_off`'s mid-sweep `OSError` discards the names already removed.

### What the four rounds actually establish

The P0 is closed, but **the underlying defect changed shape rather than disappearing**: for
two *concurrent* sessions on one slug it is now lockout-on-seizure instead of
lockout-on-refusal. Every attempt to resolve it inside `_write_task_marker` failed, because
the system has no liveness signal that survives its own CLI — the registry's pid is dead by
construction, and the gate's cwd is the base by the shipped `pf_tail.md.j2` contract.

**The two candidate real fixes, neither attempted here:**
1. Give a task claim a liveness signal that outlives the CLI process — a heartbeat file, or
   marker mtime — so `_foreign_live_rows` can actually discriminate.
2. Change `pf_tail.md.j2` so a stage `cd`s into `<WT>` for the whole stage rather than for
   Bash only, which would make the gate's cwd self-membership real instead of inert.

Both are design decisions about the concurrency model, not patches, and each would need its
own PLAN. **Recommendation: do not attempt a fifth in-place fix.**
