---
type: review
task_slug: fleet-10-20-parallel-safety
status: APPROVED
created: 2026-06-21
reviewers_invoked: [code-reviewer, concurrency-reviewer, codex]
consensus_method: k-of-3 (cross-check)
codex_status: invoked
drift_verdict:
  result: clean
  scope_violations: []
  scenario_misses: []
  task_slug: fleet-10-20-parallel-safety
  computed_at: 2026-06-21
final_grade: A
iterations_used: 3
human_review_needed: true
review_round_2_note: "C3 (Phase 2) REVERTED — Codex P0 found per-session exclusion re-opens cross-session contamination via vulnerable Layer 3. Delivered code = C1 floor only; C3 is a Layer-3-hardening follow-up. See Re-Review section."
---

# REVIEW — fleet-10-20-parallel-safety

## 🎯 Round 1 Summary

- **Reviewers:** code-reviewer (P-tier) + concurrency-reviewer (P-tier) + Codex (k-of-3
  third voter, Production-mandatory). No PR metadata exists (self-authored staged diff),
  so the 2-pass anchoring redaction is N-A — one faithful contextual pass per reviewer.
- **Round-1 grade: B** — one k-of-3 **consensus-passed** finding on the C3 mtime-liveness
  proxy. **Round-2 grade: A** after the auto-fix below.

## 🔍 Drift Findings

`drift_verdict: clean`. Every changed file maps to a PLAN phase:
- `tests/fixtures/stop_payload_wsl2.json` → Phase 0 (spike).
- `loop.md.j2`, `readiness.py`, `test_fleet_degraded_floor.py` → Phase 1 (C1 floor).
- `worktree.py`, `test_fleet_queue_guard_ownership.py` → Phase 2 (C3).
- `CLAUDE.md` → Phase 4 (docs).
- 8 `tests/snapshot/*.expected.yaml` → mechanical consequence of the `loop.md.j2` body
  change (only the `commands/hm/loop.md` `body_sha256` line; verified contained).
- **Intentional non-changes** (not "incomplete phase"): `loop_gate.py` / `loop_marker.py`
  unchanged = the Phase-0 spike NO branch (self-heal dropped). Phase 3 files absent =
  documented deferral. Neither is drift.

## ✅ Consensus Findings

### [P2 → resolved] C3 mtime-liveness is an unsound proxy — `worktree.py` `_is_foreign_*` (k-of-3: concurrency P1, code P2, Codex P2)

**OBSERVE:** `_is_foreign_live_owner` excluded a foreign stash only when
`time.time() - marker.stat().st_mtime <= _PRUNE_GRACE_SECONDS` (300s). **TRACE:** the
`.hm-loop-*` marker is written exactly once at `worktree create` (`worktree.py:349`,
`atomic_write`) and never refreshed during the loop — so its mtime is worktree-**create
age**, not last activity (all three reviewers independently grepped + confirmed this).
**INFER:** any peer session older than 5 minutes — the *normal* state of a multi-iteration
loop or any long-running session, i.e. exactly the 10–20 long-running fleet C3 targets —
has a stale marker mtime, so its legitimate live stash is classified not-live and
**counted**, re-opening the false-block. **CONCLUDE:** the original C3 fix only held for a
peer's first 5 minutes; for its actual target workload it was a near-no-op.

**Severity resolution:** votes 1×P1 (concurrency) + 2×P2 (code, Codex) → majority **P2**
(not data loss / bypassable via `--allow-stash-queue` / degrades to today's behavior).
Per the grade table P2 does not lower the grade, **but the finding was fixed anyway** —
a majority-P2 that makes the fix ineffective for its purpose is a quality defect, not a
grade-arithmetic footnote.

**Auto-fix (Iteration 2):** dropped the mtime/liveness gate entirely; renamed
`_is_foreign_live_owner` → `_is_foreign_owner`; a foreign-owner stash is now excluded
**regardless of marker age**. Rationale: the create-time queue-guard exists for the
SINGLE-session footgun (one session piling its own exec-rev stashes), so a stash owned by
*any* other session is never the creator's footgun and counting it only ever produces a
false-block. Abandoned foreign stashes are reaped by `prune_stale` (runs at create,
*before* the count) — the one layer that can actually act on them; the queue-guard never
could (the creator cannot wrapup another session's stash). This also re-resolves PLAN
validator warning #3 (masking) by ownership instead of liveness. Test
`test_stale_foreign_owner_still_counted` (which encoded the now-revised bounded-liveness)
was flipped to `test_foreign_owner_excluded_regardless_of_age` (asserts exclusion with an
old marker mtime). PLAN ADR-003 + CLAUDE.md updated with the revision.

## ⚠️ Weak Consensus

None.

## 📝 Manual-Only Findings

- **[P3, Codex, won't-fix] `$(pwd)` command-substitution in the loop.md.j2 degraded
  guard.** Pre-existing pattern (`[ "<WT>" = "$(pwd)" ]`) untouched by intent — it is a
  Claude/Codex tool-call string evaluated by the Bash tool at runtime, where `$(pwd)`
  resolving to the command runtime cwd is the intended behavior. Not introduced by this
  diff; out of scope. No action.
- **[suggestion, code-reviewer] codex-variant loop.md.j2 quoting has no render test.**
  The `test_fleet_degraded_floor` fixture renders the non-codex branch only. Both
  reviewers verified the codex `Bash("...")` escaped-double-quote variant is correct by
  inspection. A codex-target render assertion would guard against future regressions —
  optional, deferred (low value: the variant is verified correct now).

## 🤝 Disagreements

Severity split on the consensus finding (concurrency P1 vs code/Codex P2). Resolved to P2
by majority per Step 4c. The split is about *impact framing* (P1 "materially weakens the
fix" vs P2 "degrades to today's behavior, not data loss") — both agree the mtime proxy is
unsound; neither claims data loss. The fix moots the split.

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | B     | —             | 1 (P2 consensus) | — |
| 2         | A     | 1 (drop mtime-liveness) | 0 | 0 |

Final grade: **A**
Iterations used: 2 / 3
Status: **APPROVED**
human_review_needed: false

**Post-fix verification:** `test_fleet_queue_guard_ownership.py` + `test_fleet_degraded_floor.py`
+ worktree queue-guard/stash/prune/session-marker suites GREEN (68 passed, 1 skipped);
`ruff check` + `ruff format --check` + `mypy --strict` clean on changed files. No commit
(wrapup owns it).

---

## Re-Review (Round 2, 2026-06-21) — fresh k-of-3 on the Round-1 auto-fix → **Codex P0** → C3 **REVERTED**

The Round-1 auto-fix (Option A: unconditional foreign-owner exclusion) materially changed
the C3 design and was NOT independently reviewed, so a fresh k-of-3 re-reviewed it.

### [P0, consensus = Codex correct] Foreign-owner exclusion re-opens cross-session contamination

**OBSERVE:** `_count_pending_stashes` excluding FOREIGN live stashes lets session C's
`worktree create` proceed while peers A+B hold deferred finalize stashes. **TRACE:**
`post-commit-pop` (`worktree.py:3202`) globs **all** `.hm-finalize-stash-*` refs and skips a
ref only when its `session_uuid ∉ HM_OWNED_SESSION_UUIDS` (`:3259`). That owned-set comes from
`_owned_session_uuids` (`:216`), whose docstring says "owned by THIS process" but whose
**implementation globs every `.hm-loop-*` marker in the base** — all sessions' UUIDs. The
code's own comment (`:3244-3254`) states this layer "preserves prior (vulnerable) behavior"
and the per-session fix is "a separate follow-up." **INFER:** C's `post-commit-pop` therefore
restores A's/B's deferred stashes (their UUIDs are in the all-markers owned-set, their markers
are present) → the 3×-recurring `worktree-finalize-pulls-orphan-wip-into-main` contamination.
**CONCLUDE:** the queue-guard's foreign-counting is **load-bearing** — it is the operative gate
that kept C out of the vulnerable Layer-3 path. The "fleet false-block" C3 set out to remove
is a **safety feature**, not pure friction.

**Reviewer split (resolved by code, not majority):** Codex **P0**; code-reviewer + concurrency-reviewer
both said *SOUND* (P2 doc-nit only). The two Claude reviewers' "sound" rests on a **false premise** —
they trusted the `_owned_session_uuids` "owned by THIS process" docstring and asserted Layer 3
isolates per-session. Codex read the *implementation* + the explicit vulnerability comment and
was right. When one side's OBSERVE is factually wrong, the consensus is not averaged — verified
against `worktree.py:216,3202,3244-3267` first-hand: **Codex is correct.** (Both Claude reviewers
also independently flagged a real P2 — the docstring over-claimed `prune_stale` reaps marker-present
foreign stashes; moot after revert.)

**Action — REVERT (Iteration 3):** C3 reverted entirely. `_count_pending_stashes` restored to the
original all-counting form + a LOAD-BEARING comment so it is not naively re-attempted;
`_is_foreign_owner` removed; call-site reverted; `test_fleet_queue_guard_ownership.py` removed.
PLAN ADR-003 + CLAUDE.md updated documenting the revert + the Layer-3 root cause.

**Delivered code after revert = C1 floor (Phase 1) + Phase-0 spike fixture + docs only** — all
previously cleared / sound. C3 (Phase 2) is **not shipped**; it is WONTFIX until Layer 3 is
hardened (per-session `--owned-uuid` wiring), now the highest-value follow-up this work surfaced.

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | B     | — | 1 (P2 mtime-liveness) | — |
| 2 (auto-fix) | A | 1 (Option A: drop mtime) | 0 | — |
| 3 (re-review) | A | 1 (**REVERT** Option A — Codex P0) | 0 | 0 |

**Final grade: A** (on the delivered C1-floor-only diff — no P0/P1 remain after revert).
**Status: APPROVED** for what ships, **human_review_needed: true** — the user must know C3 was
attempted and found unsafe; the real fix (Layer-3 hardening) needs a new plan.

**Post-revert verification:** worktree queue-guard/stash/session-marker + fleet floor suites GREEN;
`ruff check` + `mypy --strict` clean. No commit (wrapup owns it).
