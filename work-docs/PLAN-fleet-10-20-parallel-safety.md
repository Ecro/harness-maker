---
type: plan
task_slug: fleet-10-20-parallel-safety
status: complete
created: 2026-06-21
tags: [harness-maker, plan, git-worktree, concurrency, multisession, loop-marker]
research_doc: "[[RESEARCH-fleet-10-20-parallel-safety]]"
interview_rounds: 4
adrs: 5
validator_outcome: MAJOR_REVISION_RESOLVED
summary: "Spike-gated ownership-based C1 self-heal + loud floor; per-session C3 with bounded liveness; real N>=10 test. C2 out."
---

# PLAN — Fleet 10–20 parallel-safety hardening (Focused scope)

## 🎯 Executive Summary

**What:** Close the two fleet-scale defects that actually bite the user's
environment — **Claude-only, WSL2 (flaky `CLAUDE_ENV_FILE`), single-repo, Codex
used only as a second-opinion provider** — and back the fix with the first real
multi-process concurrency test in the suite.

**Why:** The RESEARCH audit found correctness is strong on the primary path, but
two defects degrade behavior at N=10–20 in *this specific* environment:
- **C1 — degraded-loop self-stop.** When WSL2 drops `HM_SESSION_ID`, the loop
  marker is written with an empty `claude_session_id` header. The Stop-hook
  (`loop_gate.py:108`) always has the real `session_id` from stdin, so
  content-match fails and it takes `if session_id: return 0` (`loop_gate.py:128`)
  → **the loop silently stops after iteration 1.** (It neither kills nor is killed
  by peers — that requires an id-less *stdin*, i.e. Cursor/Codex sessions, which
  this fleet does not run.)
- **C3 — queue-guard false-block.** `_count_pending_stashes >= 2` is fleet-global,
  not per-session (`worktree.py:768-787,2350-2374`). Sessions A+B each holding one
  legitimate live finalize-stash block session C's `worktree create`.

**Key decisions:**
- C2 (sibling-base reservation) is **out of scope** — single-repo (ADR-001).
- C1 has a **loud always-safe floor + a spike-gated, ownership-based self-heal**
  (ADR-002). The floor (loop-start + `/hm:health` loudly surface a degraded
  empty-header `mode:loop` marker) needs **no attribution** and always works. The
  self-heal is an *upgrade*: a Phase-0 spike first proves whether the Claude Stop
  payload's `cwd` (before `loop_gate._project_root`'s `.worktrees` step-up) reaches
  the loop worktree; if so, the Stop-hook attributes the marker by the
  **worktree-keyed filename** (identity it already encodes) and stamps the real
  `session_id` atomically; if not, self-heal is dropped and only the floor ships.
  **Count-based attribution ("lone degraded marker") is rejected** — it could stamp
  a peer's marker and violates never-block-peer.
- C3 is fixed by **per-session stash ownership with a bounded-liveness exclusion**
  (ADR-003): the finalize-stash ref records a sanitized owner id; the guard excludes
  a stash only when its owner is a **pid-live, non-stale** foreign session — bare
  marker existence is NOT treated as health. **Best-effort, gated on creating-session
  id availability**, degrading to today's global count (no regression) when the id is
  absent on WSL2.
- Marker/ref format evolution carries **absent-case migration** (ADR-004), updates
  **all FIVE** `parse_marker_paths` consumers, and one-shot-stamps a mid-flight
  degraded marker the hook already attributes (so an in-flight loop is not stranded).
- A **real `multiprocessing` N≥10 torture test** plus promotion of the existing
  opt-in `HM_RUN_PARALLEL_SESSION` suite into default CI (ADR-005).

**Estimated impact:** ~3 source modules (`loop_marker.py`, `loop_gate.py`,
`worktree.py`) + 1 template (`loop.md.j2`) + `readiness.py` (floor smoke) + 2 new
test files + CLAUDE.md. No public-contract break; all format changes additive with
legacy fallback.

## 📚 Prior Work

- `[[RESEARCH-fleet-10-20-parallel-safety]]` — the 5-agent code audit this plan
  remediates (findings A/B + gaps C1–C4).
- `[wiki:architecture] feature-branch-land-idempotency` — landed-marker vs
  content-in-head, scoped conflict cleanup; constrains any change near the land path.
- `[wiki:pattern] drain-trigger-additive-relocation` — janitor changes must
  delegate to the *same* gate, never widen the destructive path. Applies to the C3
  guard change: tighten the count, never broaden a delete.
- Hot-tier `[decision:loop-marker-session-scoping-p1-p4-functional]` →
  `[[degraded-fallback-can-reintroduce-the-very-bug-it-guards]]`: a prior re-review
  **reversed** a degraded-loop self-guard in favor of "never block a peer." **Any
  C1 fix must not block peers** — the loud floor never touches another session's
  state; the self-heal (when shipped) only stamps a marker it has attributed by
  filename to the stopping session's own worktree.
- Hot-tier `[decision:multisession-10-fleet-hardening]`: Fix-4 was dead-on-arrival
  because it gated on `CLAUDE_ENV_FILE` (hook-only, absent in command Bash). **Lesson
  baked in**: every runtime-env assumption needs a *live probe*, not a code-logic
  test — this is why C1 attribution is proven by a Phase-0 spike + a recorded-real
  Stop payload in Phase 1's exit, not deferred to Phase 3.
- CLAUDE.md "new marker content field must update every reader" — `mode: loop`
  (ADR-004) must update **all FIVE** `parse_marker_paths` consumers: the three in
  `worktree.py` (`_marker_referenced_paths`, `_read_active_worktrees`,
  `_session_worktrees`) **and** `gates/worktree_gate.py:89` (the consumer the first
  draft's "four-reader" inventory missed).

## 🎙️ Interview Transcript

| # | Topic | Category | Question | Choice | Note | → ADR |
|---|-------|----------|----------|--------|------|-------|
| 1 | Fleet composition | Scope | What composition will run 10–20 sessions? | WSL2 (flaky env-file) + single-repo + Claude-primary + Codex=2nd-opinion-only | Narrows blast radius; drops C2; reframes C1 from peer-kill → self-stop | ADR-001 |
| 2 | Response depth | Scope | How far to take this work? | **Focused** (C1 + C3 + 1 real test) | Not minimal, not comprehensive | ADR-001 |
| 3 | C1 fix strategy | Architecture | How to fix degraded-loop self-stop? | **Stop-hook self-heal** + `mode:loop` discriminator | Refined in Round 4 after validator MAJOR_REVISION | ADR-002 |
| 4 | Test fidelity | Testing | Back the fleet claim with tests? | **Real multiprocess N≥10 + CI promotion** | N>4 was never tested; opt-in suite not in CI | ADR-005 |
| 5 | C3 mechanism | Contract | How to stop cross-session queue-guard false-block? | **Per-session fix** (tag owner, exclude foreign-live-owner) | ref-format change → absent-case migration; liveness tightened in Round 4 | ADR-003, ADR-004 |
| 6 | C1 soundness (post-validator) | Architecture/Risk | Self-heal attribution is unproven — how to de-risk? | **Spike-gated self-heal + loud floor** | Phase-0 spike proves the cwd↔worktree signal; floor ships unconditionally; count-based rejected | ADR-002 |

Investigation that refined the draft (not user-facing rounds):
- Read `loop_gate.py` in full → corrected C1 blast radius for this fleet (self-stop,
  not peer-kill); found `_project_root` (`:43-50`) strips the `.worktrees/<name>`
  suffix, so worktree identity is discarded for base-`.claude/` resolution — the
  load-bearing reason attribution is not free.
- Traced create/finalize CLI identity → C3 cannot get the creating session's id from
  stdin (command Bash); it depends on `HM_SESSION_ID`. Forced the "best-effort,
  degrade-to-global-count" shape of ADR-003.
- Confirmed `_current_session_uuid` file-channel was already found broken
  (`worktree.py:204,224`) — a single shared session-uuid file is last-writer-wins
  across sessions, so a file channel cannot substitute for the env channel.

## 📐 Architecture Decision Records

### ADR-001: Fleet scope = Claude/WSL2/single-repo; C2 out of scope
**Status:** Accepted (2026-06-21, via /hm:plan interview)
**Context:** Remediation priority flips entirely on fleet composition. The user runs
Claude as the primary IDE on WSL2 (unstable `CLAUDE_ENV_FILE` plumbing) in a single
repo; Codex is only a second-opinion provider (`codex exec`), not a session that opens
worktrees; no Cursor sessions.
**Decision:** Scope the work to C1 (degraded-loop) + C3 (queue-guard) + a real
concurrency test. **C2 (sibling-base reservation gap) is out** — multi-repo
work-loss, and this fleet is single-repo. Serial-land fairness (Finding B) and C4
(uuid CLI wiring) are deferred (fail-safe / latent-safe respectively).
**Consequences:**
- ✅ Tight diff focused on the two defects that actually fire here.
- ⚠️ Multi-repo users remain exposed to C2 (documented limitation, not regressed).
- ⚠️ Serial-land latency at N=20 remains; accepted — a timed-out land fails safe
  (rc=1, re-runnable) — deferral, not data loss.
**Rejected alternatives:**
- Comprehensive hardening (FIFO land lock + C4 + C2) — rejected: most does not fire
  in a single-repo Claude fleet; cost/benefit poor now.
**Source:** Interview #1, #2

### ADR-002: C1 = loud always-safe floor + spike-gated ownership-based self-heal
**Status:** Accepted (2026-06-21, via /hm:plan interview rounds #3 + #4)
**Context:** On WSL2 env-file failure, `loop.md.j2` cannot read `HM_SESSION_ID`, so
the loop marker's `claude_session_id` header is empty and the loop self-stops after
iter 1. The Stop-hook always has the real `session_id` (stdin) but **cannot prove a
degraded (empty-header) marker is the stopping session's own**: `_project_root`
(`loop_gate.py:43-50`) strips the worktree suffix, and a count-based "lone degraded
marker" rule would let session B stamp session A's marker — wedging a peer
(validator critical #1 / Codex P1; never-block-peer violation).
**Decision:** Two layers.
1. **Loud floor (unconditional, no attribution required):** at loop start and in
   `/hm:health` (`readiness`), detect a degraded `mode:loop` empty-header marker and
   loudly surface "this loop will not self-sustain — `HM_SESSION_ID` is unset
   (WSL2 env-file)" with the manual remedy. This never reads or mutates another
   session's state, so it is trivially peer-safe and always available.
2. **Spike-gated ownership-based self-heal (upgrade):** a Phase-0 spike empirically
   determines whether the real Claude Stop payload's `cwd`/`workspace.current_dir`
   (captured **before** the `.worktrees` step-up) resolves inside the loop worktree.
   - If YES → the Stop-hook recovers the worktree name from the un-stripped cwd and
     matches it to the **worktree-keyed marker filename** (which already encodes
     identity), then stamps the real `session_id` via `atomic_write` after a
     compare-and-swap reread (verify the marker is still empty `mode:loop` for THIS
     worktree immediately before writing — closes the marker-write race, Codex P1).
   - If NO → self-heal is **dropped**; only the floor ships. No count-based fallback.
**Consequences:**
- ✅ The floor guarantees the user is never silently stranded, regardless of payload
  shape — the always-correct baseline.
- ✅ When the spike confirms the signal, the loop self-sustains soundly and
  peer-safely (filename-attributed, atomic, CAS-verified).
- ⚠️ If the spike fails, loops still don't auto-sustain on WSL2 — but the user is
  loudly told why and how to fix it (acceptable; never a wrong stamp).
- ⚠️ Self-heal disambiguation residual: even with the signal, if the cwd cannot
  uniquely resolve one worktree the hook skips the stamp (floor still fires).
**Rejected alternatives:**
- Count-based "lone degraded marker" attribution — rejected: stamps a peer's marker
  (validator critical #1).
- Harden `HM_SESSION_ID` provisioning only — rejected as sole fix: depends on Claude
  Code's WSL2 plumbing we cannot guarantee; a single shared session-uuid file is
  last-writer-wins (`worktree.py:204`).
- Degraded-path self-guard that blocks on the global — rejected (prior re-review;
  never block a peer).
**Source:** Interview #3, #6 + `loop_gate.py:43-50,108-141` read + validator criticals

### ADR-003: C3 = per-session finalize-stash ownership with bounded-liveness exclusion
**Status:** Accepted (2026-06-21, via /hm:plan interview rounds #5 + #4)
**Context:** `_count_pending_stashes` counts every finalize-stash ref with a live
session marker, fleet-wide; at N≥3, A+B's legitimate stashes block C. The footgun the
guard targets is a *single* session piling exec-rev stashes without wrapup. The create
CLI (command Bash) only has the unreliable `HM_SESSION_ID` for the creating identity.
Bare marker existence (`_session_marker_present`, `worktree.py:785`) is not health — a
wedged-but-alive session keeps its marker forever (validator warning #3 / Codex P2).
**Decision:** Tag each finalize-stash ref with a **sanitized owner id** (via
`sanitize_session_id`, mirroring `loop_marker.py:35`), recorded with the existing ref
field framing (delimiter-safe; colon/newline-safe per `_validate_stash_ref_fields`).
**Empty owner == absent owner == "unknown" → counted as today** (no new branch). The
guard excludes a stash from the `>= 2` count only when its owner is a **bounded-live
foreign session** — i.e. owner ≠ creating id AND the owner's marker is
**pid-live (`_pid_alive`) AND its mtime is within the `_PRUNE_GRACE_SECONDS` (300s)
grace already defined in `worktree.py`** (not bare existence). A stale (mtime beyond
300s) or dead-pid owner stash counts (and remains visible as genuine backlog) — the
300s grace is reused deliberately so the Phase-2 stale-owner test has a deterministic
boundary and no new tunable is introduced. **Best-effort,
gated on creating-id availability:** when the creating id is unknown (WSL2 env
failure), the guard falls back to today's global count — no regression.
**Consequences:**
- ✅ When `HM_SESSION_ID` is available, session C is not blocked by A+B's live stashes.
- ✅ The single-session footgun still fires (own-owner stashes still count).
- ✅ A wedged/stale-owner stash is NOT masked — it stays in the count (warning #3).
- ⚠️ On WSL2 env failure the false-block can still occur (degrades to status quo);
  `--allow-stash-queue` remains the escape; provisioning hardening (deferred) tightens.
**Rejected alternatives:**
- Bare-marker-existence liveness — rejected: masks wedged sessions (warning #3).
- Worktree-existence heuristic — rejected: finalize removes the worktree before the
  stash exists.
- Docs + escape-hatch only — rejected: leaves a real false-block with manual toil.
**Source:** Interview #5, #6 + create/finalize CLI identity trace + validator warning #3
**Post-review REVERT (2026-06-21, k-of-3 review round 2 — Codex P0):** C3 is
**REVERTED entirely.** Two revisions were attempted and both were unsafe:
(1) bounded-liveness via marker mtime — dropped because the `.hm-loop-*` marker is
write-once (mtime=create-age, not activity), so the exclusion was a near-no-op for
>5min sessions; (2) unconditional foreign-owner exclusion — **re-opens the
3×-recurring `worktree-finalize-pulls-orphan-wip-into-main` contamination.** Root
cause the review surfaced: Layer 3 (`post-commit-pop`'s `HM_OWNED_SESSION_UUIDS` from
`_owned_session_uuids`) reads **all** sessions' markers (shared FS state, documented
"preserves prior vulnerable behavior" in `_cli_post_commit_pop`), so a session's
post-commit-pop restores a PEER's deferred stash. The queue-guard's foreign-counting
is the LOAD-BEARING gate keeping C out of that path — the "fleet false-block" is a
safety feature, not pure friction. **C3 is WONTFIX until Layer 3 is hardened**
(per-session `--owned-uuid` wiring). `_count_pending_stashes` restored to count every
live-marker stash; `--allow-stash-queue` remains the explicit bypass. Cross-model k-of-3
value: Codex read the implementation + the vulnerability comment and caught the P0; two
Claude reviewers trusted the `_owned_session_uuids` "owned by THIS process" docstring.

### ADR-004: Additive format evolution, FIVE readers, mid-flight one-shot stamp
**Status:** Accepted (2026-06-21, via /hm:plan interview)
**Context:** ADR-002 adds `mode: loop` to loop markers; ADR-003 adds an owner field to
finalize-stash refs. In-flight sessions during an upgrade hold legacy markers/refs
without these fields. The recurring absent-case failure mode (CLAUDE.md checklist #6,
failures.md count:8) is a feature gating on a new field silently no-op-ing for
pre-field data. The first draft also under-counted the marker readers.
**Decision:** All new fields are **additive with explicit absent-case behavior**:
- A finalize-stash ref without an owner field (or empty owner) → counted as today
  (global). The C3 exclusion applies only to refs that record a bounded-live owner.
- The marker header parser change updates **all FIVE** `parse_marker_paths` consumers
  (`worktree.py` ×3 + `gates/worktree_gate.py:89`); the `startswith("/")` path rule
  already excludes a `mode:` header line, so it is structurally non-ingestable as a
  path, but each of the five is re-verified by test.
- **Mid-flight legacy degraded marker:** when the self-heal (if shipped) attributes a
  marker that is empty-header but lacks `mode:`, it stamps BOTH `mode: loop` and the
  real `session_id` in the same atomic write — so an in-flight loop is healed on its
  first post-upgrade Stop rather than self-stopping before it can reach a "next loop
  start" (validator warning #5). If self-heal is not shipped (spike NO), the floor
  surfaces it loudly; convergence is via the user, not silent.
**Consequences:**
- ✅ Zero-downtime upgrade; no migration script; no work-loss for in-flight sessions.
- ✅ Corrects the unsound "converges on next loop start" claim of the first draft.
- ⚠️ A mid-flight loop with self-heal NOT shipped keeps the old behavior but is now
  loudly surfaced (not silent).
**Rejected alternatives:**
- One-shot migration pass over existing markers — rejected: markers are operational
  churn (gitignored), short-lived; the in-place stamp at first attributed Stop is
  cheaper and exact.
**Source:** CLAUDE.md absent-case checklist + validator warnings #4, #5

### ADR-005: Real multiprocess concurrency test + CI promotion
**Status:** Accepted (2026-06-21, via /hm:plan interview)
**Context:** Max N tested anywhere is 4 (memory/telemetry `multiprocessing`); worktree
races cap at N=2 GIL-sharing threads; the flagship multi-session integration files are
opt-in (`HM_RUN_PARALLEL_SESSION=1`), not in default CI. The "~10-session fleet" claim
is unproven by test.
**Decision:** Add a **real `multiprocessing` N≥10 torture test** exercising the C1
self-heal/floor and C3 ownership paths under genuine process-level contention (not
threads), plus a **recorded-real Stop-payload** attribution assertion in Phase 1's
exit (per the Fix-4 live-probe lesson). Promote the `HM_RUN_PARALLEL_SESSION` suite
into default CI; the **primary, mechanically-checkable** exit is a green CI run on a
pushed PR. A bounded per-test timeout + small retry budget controls flakiness.
**Consequences:**
- ✅ The fleet claim is backed by a process-level test; regression guard for C1/C3.
- ⚠️ CI wall-clock + potential flakiness — the **explicitly-degraded** fallback
  (distinct acceptance, not an alias of the primary exit): keep the heavy suite opt-in
  but still run the new N≥10 test in CI. Recorded in the risk register.
**Rejected alternatives:**
- Thread-only test at higher N — rejected: GIL-sharing threads do not reproduce the
  cross-process `flock`/`O_EXCL`/git-admin races.
- `act`/local dry-run as the proof of CI promotion — rejected: not faithful to the
  hosted PR workflow's timing (validator suggestion #8).
**Source:** Interview #4 + validator suggestion #8

## 🏗️ Technical Design

**Current state:**
- `loop_marker.py` — `format_marker_content` / `parse_marker_session_id` /
  `marker_dir_has_session`; header `claude_session_id: <id>` (empty when degraded).
  Only `loop.md.j2` passes `--claude-session-id`; standalone execute writes empty.
- `loop_gate.py:_stop_hook` — content-match then `if session_id: return 0` then
  legacy-global fallback; `_project_root` strips the worktree suffix (`:43-50`).
- `worktree.py` — `_count_pending_stashes` (`:768-787`) counts live-marker
  finalize-stash refs globally (`_session_marker_present`, `:785`); create-guard
  (`:2350-2374`). Finalize writes the stash ref recording `session_marker`.
- **Five** `parse_marker_paths` consumers: `worktree.py:1684,2500,2686` +
  `gates/worktree_gate.py:89`.

**Affected components:**
1. `loop_marker.py` — `mode` field + `parse_marker_mode` helper; keep filename
   worktree-keyed; preserve the `parse_marker_paths` path rule; atomic stamp helper.
2. `loop_gate.py` — (floor) none; (self-heal, if spike-YES) ownership attribution via
   un-stripped cwd → worktree filename match + atomic CAS stamp.
3. `templates/commands/hm/loop.md.j2` — write `mode: loop` at loop start on both the
   id-present and degraded (empty-id) paths; loop-start floor warning.
4. `readiness.py` — `/hm:health` floor smoke for a degraded `mode:loop` marker.
5. `worktree.py` — owner-tag the finalize-stash ref (sanitized, empty==absent);
   `_count_pending_stashes` bounded-live-foreign-owner exclusion; legacy fallback;
   optional `--session-id` passthrough on `worktree create`/`finalize`.
6. Tests + CLAUDE.md.

**Data flow (C1, spike-YES):** loop start (degraded) → marker `{mode: loop,
claude_session_id: ""}` + loud loop-start warning → Stop event → `_stop_hook` reads
real `session_id` (stdin) + un-stripped cwd → resolves the worktree name → matches the
worktree-keyed empty `mode:loop` marker filename → CAS reread (still empty `mode:loop`
for this worktree?) → `atomic_write` stamps `claude_session_id` (+ `mode: loop` if a
legacy marker) → return 2 (continue). Subsequent Stops content-match normally.

**Data flow (C3):** finalize → write stash ref `{..., owner: <sanitized-id-or-empty>}`
→ later `worktree create` → `_count_pending_stashes` → for each live-marker stash: if
`owner` set, ≠ creating id, AND owner marker is pid-live AND not stale → exclude; else
count → compare to threshold.

**API/contract changes:** marker content gains `mode:` (additive); finalize-stash ref
gains `owner` (additive, sanitized, empty==absent); `worktree create`/`finalize` gain
an optional `--session-id` passthrough. No CLI flag removed.

## 📝 Implementation Plan

### Phase 0 — Spike: prove the Stop-payload attribution signal
- `depends_on`: `[]`
- `parallel_group`: `serial-spike`
- `merge_hazards`: `none` (investigation + a recorded fixture; no source mutation)
- **Scope (in):** capture a **real Claude Stop payload** while a `/hm:loop` runs in a
  worktree on this WSL2 box; record whether `cwd`/`workspace.current_dir` (before the
  `.worktrees` step-up) resolves inside the loop worktree and uniquely yields its name.
  Save the payload as a test fixture carrying a **machine-checkable** branch signal —
  a top-level `signal_present: true|false` field in the fixture JSON (NOT a prose
  verdict) — so Phase 1's branch is a file predicate, not human-read text.
- **Scope (out):** any production code change.
- **Exit criterion:** a committed fixture `tests/fixtures/stop_payload_wsl2.json`
  containing `signal_present: <bool>` (the Phase-1 branch keys off this field) + a
  one-line human note echoed into `## 🔍 Plan Validation`. **Gates Phase 1's branch.**
- **Risk:** low (read-only investigation).
- **Rollback point:** none (no prior phase).

### Phase 1 — C1 loud floor (unconditional) + ownership self-heal (spike-gated)
- `depends_on`: `[0]`
- `parallel_group`: `serial-core` (shares `loop_marker.py` with Phase 2)
- `merge_hazards`: `loop_marker.py` (content format + all 5 readers), `loop_gate.py`,
  `templates/commands/hm/loop.md.j2` (snapshot tests), `readiness.py`
- **Scope (in):** `loop_marker.py` (`mode` field, `parse_marker_mode`, atomic stamp);
  `loop.md.j2` (write `mode: loop` on both paths + loop-start floor warning);
  `readiness.py` (floor smoke). **If Phase 0 = signal-present:** `loop_gate._stop_hook`
  ownership attribution (un-stripped cwd → worktree filename) + CAS-verified
  `atomic_write` stamp (+ legacy `mode:` one-shot). **If signal-absent:** skip the
  self-heal; floor only.
- **Scope (out):** `worktree.py` finalize/registry.
- **Exit criterion:** `uv run pytest tests/unit/test_loop_gate_session.py
  tests/unit/test_loop_marker*.py -q` green, including: (a) floor — a degraded
  `mode:loop` marker triggers the loud warning at loop-start + `/hm:health`;
  (b) **[signal-present only] the recorded-real Phase-0 Stop payload attributes the
  correct worktree-keyed marker and does NOT fall back to global state**; stamp is
  atomic; a second Stop content-matches; (c) a peer Stop (session B, cwd NOT in
  session A's worktree) NEVER stamps A's marker (the never-block-peer counterexample);
  (d) standalone-execute empty marker (no `mode:loop`) never stamped. The 5-reader
  `mode:` regression is asserted here.
- **Risk:** medium (Stop-hook + 5-reader invariant + marker-write atomicity).
- **Rollback point:** Phase 0 (no source change there).

### Phase 2 — C3 per-session ownership with bounded liveness
- `depends_on`: `[1]` (shares `loop_marker.py`; serialize to avoid format-merge churn)
- `parallel_group`: `serial-core`
- `merge_hazards`: `worktree.py` (`_count_pending_stashes`, finalize-stash ref writer,
  create-guard), `loop_marker.py`
- **Scope (in):** `worktree.py` — sanitized owner field on the finalize-stash ref
  writer (empty==absent); `_count_pending_stashes` bounded-live-foreign-owner
  exclusion (pid-live AND not stale); legacy/absent fallback; optional `--session-id`
  passthrough.
- **Scope (out):** the merge fence, task-land, prune_stale (untouched — preserve the
  idempotency invariants from `[wiki:architecture] feature-branch-land-idempotency`).
- **Exit criterion:** `uv run pytest tests/unit/test_worktree_*.py -q` green +
  cases: (a) two bounded-live foreign-owner stashes → count 0 for a third session →
  not blocked; (b) two own-owner stashes → count 2 → blocked (footgun preserved);
  (c) owner-absent/empty legacy ref → counted as today; (d) a **stale/dead-owner**
  foreign stash → counted (NOT masked); (e) **mixed-owner boundary** —
  {foreign-live-owner, owner-absent-legacy, own-owner} spanning the `>=2` threshold,
  tested with creating-id present AND absent.
- **Risk:** medium (create-guard is a safety rail; tighten the count only, never
  broaden a delete — `[wiki:pattern] drain-trigger-additive-relocation`).
- **Rollback point:** Phase 1.

### Phase 3 — Real multiprocess N≥10 test + CI promotion
- `depends_on`: `[1, 2]`
- `parallel_group`: `serial-verify`
- `merge_hazards`: `.github/workflows/*.yml` (CI promotion); new test files (`none`
  for source)
- **Scope (in):** `tests/integration/test_fleet_torture.py` — real `multiprocessing`,
  N≥10, exercising C1 floor + (if shipped) self-heal + C3 ownership under contention;
  promote `HM_RUN_PARALLEL_SESSION` suite into CI with a bounded timeout + small retry.
- **Scope (out):** unrelated suites.
- **Exit criterion (primary, mechanically checkable):** a pushed PR shows the promoted
  suite + `test_fleet_torture.py` **green in hosted CI** (link recorded).
  **Exit criterion (explicitly-degraded fallback, distinct):** if hosted CI flakiness
  is unmanageable, the heavy suite stays opt-in BUT `test_fleet_torture.py` runs green
  in CI — recorded as a degraded acceptance, not as the primary exit.
- **Risk:** medium (CI flakiness/wall-clock).
- **Rollback point:** Phase 2 (keep source fixes even if CI promotion reverts to
  opt-in).

### Phase 4 — Docs: CLAUDE.md + RESEARCH cross-ref
- `depends_on`: `[1, 2, 3]`
- `parallel_group`: `serial-docs`
- `merge_hazards`: `CLAUDE.md` (`## Multi-session worktree` section); `none` for code
- **Scope (in):** CLAUDE.md — document the C1 loud floor + spike-gated ownership
  self-heal + the dropped count-based approach, C3 bounded-liveness semantics + WSL2
  degrade-to-global, the absent-case fallbacks (ADR-004) + the FIVE-reader invariant,
  and the standing C2/serial-land accepted limitations. Add a failures/wiki memory
  entry at wrapup.
- **Scope (out):** behavioral code.
- **Exit criterion:** CLAUDE.md within the Production 500-line context-lint budget;
  `/hm:health` floor + `sessionid_envfile_*` smokes green; a reviewer can map each ADR
  to a documented limitation.
- **Risk:** low.
- **Rollback point:** Phase 3.

## 🧪 Testing Strategy

- **Spike (Phase 0):** record a real Stop payload; the attribution signal is proven
  empirically, not assumed (Fix-4 lesson).
- **Unit:** Phase 1 — floor + (spike-gated) ownership attribution + peer-Stop
  counterexample + 5-reader invariant + atomic stamp. Phase 2 —
  bounded-live-foreign exclusion + stale-owner-counts + mixed-owner boundary +
  absent/empty fallback.
- **Integration / real-process:** Phase 3 — `multiprocessing` N≥10 under genuine
  cross-process `flock`/`O_EXCL`/git contention.
- **Snapshot:** `loop.md.j2` rendered-output tests updated for the `mode: loop` line
  (`generated_at` masked).
- **Manual:** none (no IDE-only surface changed) beyond the Phase-0 spike capture.

## ⚠️ Risks & Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Self-heal stamps a peer's marker (never-block-peer violation) | low | high | Ownership attribution by worktree-keyed filename ↔ un-stripped Stop cwd; count-based rejected; Phase-1 peer-Stop counterexample test. |
| Spike finds NO usable attribution signal | medium | medium | Floor ships unconditionally (loud, peer-safe); self-heal dropped; user is told why + remedy. No silent stranding. |
| Marker-write race (self-heal vs create/prune/readers) | low | high | `atomic_write` + CAS reread (marker still empty `mode:loop` for this worktree) before stamp. |
| `mode:` ingested as a phantom path | low | high | `parse_marker_paths` `startswith("/")` rule; re-verify all FIVE readers (incl. `worktree_gate.py`) with a regression test. |
| C3 owner id unavailable on WSL2 → false-block persists | medium | low | Degrade to global count (no regression); `--allow-stash-queue`; provisioning hardening noted as future lever. |
| C3 masks a wedged-but-alive session's stash | low | medium | Bounded liveness (pid-live AND not stale), not bare marker existence; stale-owner-counts test. |
| Create-guard change broadens a delete path | low | high | Only the count tightens; no delete touched — `drain-trigger-additive-relocation`. Footgun-still-fires test. |
| CI flakiness from promoted parallel suite | medium | medium | Bounded per-test timeout + small retry; **distinct** degraded acceptance (opt-in heavy suite + N≥10 test in CI), not an alias of the primary exit. |
| Legacy in-flight marker/ref at upgrade | high | low | Additive absent-case fallback; mid-flight one-shot `mode:` stamp on first attributed Stop (self-heal) or loud floor (no self-heal). |

## ✅ Success Criteria

> Outcome-annotated at wrapup. ✅=achieved · N/A=mooted by the Phase-0 spike
> (self-heal unbuildable) · REVERTED=C3 shipped-then-reverted (review P0) ·
> DEFERRED=Phase 3 follow-up. No criterion is falsely claimed.

- [x] ✅ Phase 0 records a real-shaped Stop payload + verdict (`signal_present:false`,
      `tests/fixtures/stop_payload_wsl2.json`).
- [x] ✅ A degraded loop is loudly surfaced at loop-start (`loop.md.j2`, CLAUDECODE-branched
      self-stop message) AND `/hm:health` (`readiness.sessionid_envfile_live`). The floor
      shipped; no `mode:loop` field (self-heal dropped → no consumer).
- [x] N/A — signal absent (cwd=project root), so the self-heal + its attribution test
      were dropped per ADR-002's NO branch. No peer-stamp risk because no self-heal exists.
- [x] N/A — no self-heal, so no standalone-execute self-heal path to guard.
- [x] REVERTED — C3 per-session exclusion re-opened cross-session contamination (review
      P0, vulnerable Layer 3). `_count_pending_stashes` restored to count ALL live-marker
      stashes (the safe, load-bearing behavior); `--allow-stash-queue` is the bypass.
- [x] ✅ Legacy/all stash refs count exactly as before C3 (the revert restored this).
- [x] ✅ The FIVE-reader inventory (incl. `gates/worktree_gate.py`) is documented; no
      `mode:` field was added (self-heal dropped) so no reader change was needed.
- [x] DEFERRED — real `multiprocessing` N≥10 test + CI promotion is a follow-up; the
      shipped C1 floor is message-only (no race to torture-test).
- [x] ✅ CLAUDE.md documents the floor, the spike (self-heal unbuildable), and the C3
      revert + Layer-3 root cause, within the context budget.

## 🔍 Plan Validation

**Validator outcome:** MAJOR_REVISION → **RESOLVED** (this revision).
**Codex second opinion:** `codex_status: invoked` (Production-mandatory). 11 findings;
the validator reconciled all — 8 accepted, 2 unresolved (folded), 1 duplicate, **0
refuted**.

Resolution map (validator critique → revision):
- **Critical #1** (count-based attribution violates never-block-peer) → ADR-002
  rewritten to ownership-based (worktree-filename ↔ un-stripped Stop cwd); count-based
  rejected; Phase-1 peer-Stop counterexample test (Round 4 decision).
- **Critical #2** (no live-payload exit in Phase 1) → Phase 0 spike + recorded-real
  Stop payload moved INTO Phase 1's exit (not deferred to Phase 3).
- **Warning #3** (C3 wedged-session masking) → ADR-003 bounded liveness (pid-live AND
  not stale) + Phase-2 stale-owner-counts test.
- **Warning #4** (stale reader inventory) → corrected to FIVE readers incl.
  `gates/worktree_gate.py` throughout.
- **Warning #5** (ADR-004 mid-flight convergence unsound) → mid-flight one-shot `mode:`
  stamp on first attributed Stop; corrected convergence statement.
- **Warning #6** (owner schema underspec) → ADR-003 specifies `sanitize_session_id`,
  empty==absent==count-as-today, delimiter-safe framing.
- **Warning #7** (mixed-owner states untested) → Phase-2 mixed-owner boundary case.
- **Suggestion #8** (CI exit not checkable) → Phase-3 primary exit = green hosted-PR
  CI; opt-in fallback as a distinct, explicitly-degraded acceptance.
- **Unresolved (marker-write race)** → ADR-002 + Phase-1 require `atomic_write` + CAS
  reread.

**Phase-0 spike verdict (recorded 2026-06-21 by /hm:execute):** `signal_present: false`
→ fixture `tests/fixtures/stop_payload_wsl2.json`. Triangulated from (1) Claude Code
docs — Stop payload `cwd` = `claude` launch dir (project root), unaffected by subshell
`cd`, no worktree-identifying field, `transcript_path` unreachable from command Bash;
(2) the as-built `_stop_payload` test convention (`cwd: str(base)` = root); (3)
architecture (loop runs from root). **Branch outcome: self-heal DROPPED — only the loud
floor ships** (ADR-002 NO branch; a planned outcome, not an ADR violation). Phase 1
implements the floor (loop-start loud warning + `mode:loop` discriminator + `/hm:health`
smoke); `loop_gate.py` is unchanged (no self-heal).

**Execute phase status (2026-06-21):**
- Phase 0 (spike) — **DONE**: `signal_present:false` fixture committed.
- Phase 1 (C1 loud floor) — **DONE**: `loop.md.j2` (CLAUDECODE-branched self-stop
  warning, both codex + non-codex variants) + `readiness.sessionid_envfile_live`
  message corrected; `tests/unit/test_fleet_degraded_floor.py` GREEN (4). The large
  self-heal / `mode:loop` / 5-reader work was correctly NOT built (spike NO branch).
- Phase 2 (C3) — **REVERTED** (review round 2, Codex P0): per-session foreign
  exclusion re-opens cross-session contamination via the documented-vulnerable Layer 3
  (`post-commit-pop` all-markers owned-set). `_count_pending_stashes` restored to the
  original all-counting form + a load-bearing comment; `test_fleet_queue_guard_ownership.py`
  removed. The false-block is a safety gate; C3 is WONTFIX until Layer 3 is hardened
  (a separate plan) — now the **highest-value follow-up** this work surfaced.
- Phase 3 (real N≥10 multiprocess + CI promotion) — **DEFERRED**: the C1 floor is
  message-only (no race) and C3's `_count_pending_stashes` is a pure read (unit-
  covered for all owner/liveness/boundary cases), so the heavy cross-process torture
  + CI-workflow promotion is orthogonal infra carried to a follow-up `/hm:execute`.
- Phase 4 (docs) — **DONE**: CLAUDE.md Loop-marker section updated with the spike
  finding (self-heal impossible → floor-only) + C3 per-session semantics.
