---
type: plan
task_slug: multisession-fleet-reverify
status: complete
created: 2026-06-21
tags: [harness-maker, plan, concurrency, memory, locking]
research_doc: "[[RESEARCH-multisession-fleet-reverify]]"
interview_rounds: 2
adrs: 5
validator_outcome: NEEDS_REVISION_RESOLVED
summary: "Close H1 for participating writers: flock-locked memory-tier CLI (RMW inside lock)"
---

# PLAN — Close H1: concurrency-safe memory-tier writes

## 🎯 Executive Summary

**What:** Make the plain-markdown memory tiers (`.claude/memory/session/<date>.md`, `wiki.md`, `failures.md`) safe under a 10-20-session fleet by routing every **harness-owned** write through a single **flock-locked Python CLI** that performs read-modify-write *inside* the lock.

**Why:** RESEARCH-multisession-fleet-reverify found H1 — the only **normal-path, no-precondition** data-loss hazard. Today these tiers are written by Claude's `Edit` tool (whole-file RMW, no lock) and by the `flush_session` PreCompact hook (Python RMW, no lock). Concurrent `wrapup` stages clobber each other; the last writer wins and earlier memory entries vanish silently. The structured stores (`semantic`, `profile`) already serialize via `memory/_locking.py`'s `exclusive_lock`; the `.md` tiers were left out.

**Guarantee boundary (honest framing — validator W3/CX1):** advisory flock closes H1 **only for writers that participate** (the re-rendered wrapup template + the `flush_session` hook). A stale-rendered harness (not re-rendered via `/harness-maker:make --update`) or a manual human `Edit` still does unlocked RMW and can clobber a concurrent locked write. This PLAN does **not** add runtime detection of non-participating writers (scoped out per ADR-004 — user declined the `/hm:health` smoke); the render-gate covers new renders only. Stale-render remains the documented-residual H6 in RESEARCH. So the claim is "**close H1 for participating writers**", not "eliminate H1 unconditionally".

**Key decisions:** ADR-001 (locked CLI single path, RMW inside lock), ADR-002 (per-tier lock files), ADR-003 (entry body via stdin/unique-temp, not argv), ADR-004 (scope boundary), ADR-005 (canonical base-rooted lock path shared by CLI + hook).

**Estimated impact:** 1 new module + CLI, 1 hook edit, 1 template rewrite (wrapup Step 5.1/5.2/5.5), unit + subprocess-concurrency + render-gate tests. No change to deliverable/worktree machinery. Out of scope (documented-risk in RESEARCH): H3 same-slug, H4 queue-guard friction, H5 multi-repo, H6 stale-render, H7 legacy-ref pop.

## 📚 Prior Work

- **RESEARCH-multisession-fleet-reverify** — H1 ranked top hazard; structured stores already locked, `.md` tiers not. H6 stale-render is an independent OPEN hazard (relevant to this PLAN's guarantee boundary).
- `[wiki:pattern] merge-fence-wraps-full-critical-section` — concurrency principle: **a lock must wrap the full read-modify-write critical section including setup**; applied here (CLI reads+modifies+writes inside the lock; Claude never reads-then-CLI-writes — that would be TOCTOU).
- `[wiki:pattern] memory-retrieve-hybrid-lexical-claude-rerank` — Python/LLM split (Python = deterministic contract/storage, LLM = judgment/content): the CLI owns lock+dedup+count+marker-placement, Claude owns entry prose.
- `memory/_locking.py` — reentrant `exclusive_lock` (fcntl, per-store `.lock` sentinel; **reentrant counter is thread-local**, flock is **process-scoped** — see ADR-004 test implications; WSL2-supported; no-op+warn on no-fcntl). Reused verbatim.
- `io_utils.atomic_write` — confirmed `os.fsync` on the temp file (io_utils.py:43,55) then `os.replace`; parent-dir is NOT fsync'd (pre-existing, equal for all callers) → guarantees "no partial/torn file", not full power-loss durability (validator CX7).
- wrapup template invariant (2026-05-17 regression): wiki/failures entries MUST land **inside** the `<!-- @hm:user:entries -->` block — EOF-append loses them on next `--update`. The CLI enforces this.

## 🎙️ Interview Transcript

| # | Topic | Category | Question | Choice | → ADR |
|---|-------|----------|----------|--------|-------|
| 1 | Usage profile | Scope | Fleet profile (flag-ON/OFF, single/multi-repo)? | flag-OFF (Side) included → H4/H3 stash paths technically live | (informs scope) |
| 2 | Plan scope | Scope | Which hazards does this PLAN fix? | **H1 only** (memory-tier lock) | ADR-004 |
| 3 | H1 mechanism | Architecture | How to make memory-tier writes safe? | **Locked Python CLI single path** | ADR-001 |
| 4 | Closure boundary | Phasing | What hardening beyond core CLI+wrapup rewrite? | flush_session adopts lock + render-gate test (NOT health-smoke, NOT gated 2-session integration test) | ADR-004 |

**Post-validation resolution (NEEDS_REVISION → resolved, no new user arbitration — mechanical correctness folds):** Codex (invoked) + plan-validator returned 7 warnings/suggestions, all dispositioned **revise**: subprocess-only proof (W1), canonical shared base-rooted lock path (W2 → ADR-005), honest claim wording (W3), malformed fail-closed set (W4), stdin/unique-temp body handoff (CX4), narrowed crash-safety wording (CX7), no-fcntl boundary criterion (CX5). None required architectural arbitration; the one scope-touching item (runtime detection) was already decided in Interview #4 (no `/hm:health` smoke). CLI append-vs-upsert semantics was not asked — code invariants make upsert the dominant answer (append-only would regress the 2026-05-17 marker-loss + duplicate-section bugs).

## 📐 Architecture Decision Records

### ADR-001: Memory-tier writes route through one flock-locked Python CLI (RMW inside the lock)
**Status:** Accepted (2026-06-21, via /hm:plan interview)
**Context:** The `.md` memory tiers are written by Claude `Edit` (whole-file RMW) and the `flush_session` hook, both unlocked → cross-session lost-update (H1). A lock only helps if the *entire* read-modify-write happens inside it; letting Claude read in-context then call a CLI to write is TOCTOU (the read is already stale).
**Decision:** Add `harness_maker.memory_md` exposing a CLI whose every subcommand acquires `exclusive_lock`, then reads → modifies (slug-dedup / count++ / marker placement) → `atomic_write`s the tier file *within* the held lock. Claude generates entry content only.
**Consequences:**
- ✅ Closes H1 **for participating writers** (re-rendered wrapup + flush_session); concurrent participating wrapups serialize on the per-tier lock. (Not unconditional — see the guarantee boundary in the Executive Summary and ADR-004 residual.)
- ✅ Reuses the proven `memory/_locking.py` primitive (consistent with semantic/profile stores).
- ⚠️ Claude no longer edits memory tiers directly — the wrapup template must call the CLI; entry body passed as data (ADR-003).
**Rejected alternatives:**
- Append-only CLI for all three tiers — Rejected: regresses wiki/failures slug-dedup, failures count++, and the `@hm:user:entries` marker discipline (2026-05-17 entry-loss class).
- Advisory lock Claude wraps around `Edit` (lock CLI → Edit → unlock CLI) — Rejected: fragile (Claude may not release); RMW would still straddle the lock boundary (TOCTOU).
**Source:** Interview #3.

### ADR-002: Per-tier lock files, not one memory-wide lock
**Status:** Accepted (2026-06-21)
**Context:** A single wrapup writes all three tiers sequentially; flush_session writes only the session log.
**Decision:** Three lock sentinels — `.claude/memory/.session.lock`, `.wiki.lock`, `.failures.lock` — each guarding its tier, matching `_locking.py`'s per-store `.lock` pattern. The lock is ALWAYS on the separate `.lock` sentinel, **NEVER on the target `.md` file** (locking the target would be unsafe with `atomic_write`'s `os.replace`: a waiter could lock an old unlinked inode or a fresh inode independently — split-inode mutex failure). A Phase-1 test crosses the `os.replace` boundary to lock this invariant against future "simplification" (validator CX3).
**Consequences:**
- ✅ flush_session's session-log append never blocks on a peer's wiki/failures write.
- ✅ Consistent with the lock-sentinel convention; lock files are permanent no-data sentinels (operator-cleaned).
- ⚠️ Two participating wrapups still serialize per-tier (correct — that is the point).
**Rejected alternatives:** single `.memory.lock` — Rejected: serializes all fleet memory writes across tiers, no safety gain.
**Source:** code precedent (common-ground, not asked).

### ADR-003: Entry body passed via stdin or a unique 0600 temp file, never argv or a fixed path
**Status:** Accepted (2026-06-21)
**Context:** Memory entries are multi-line markdown with possible shell metacharacters; argv risks truncation + shell-expansion. A *fixed* staging path (e.g. `/tmp/entry-body`) collides across concurrent sessions and is read pre-lock (the markdown lock does not protect the staging file) — a pre-lock TOCTOU surface (validator CX4).
**Decision:** The CLI reads the body from **stdin** by default, or from `--body-file <path>` where the wrapup template MUST use a **unique** path (`mktemp`, mode 0600) written with the Write tool (verbatim bytes) and cleaned up after. No fixed staging path.
**Consequences:**
- ✅ Multi-line safe; no shell expansion of adversarial entry content; no cross-session staging collision.
- ⚠️ One extra temp-file (or stdin pipe) per memory entry in wrapup.
**Source:** code-convention + validator CX4.

### ADR-004: Scope boundary — flush_session in; health-smoke + gated parallel integration test out
**Status:** Accepted (2026-06-21, via /hm:plan interview)
**Context:** User scoped this PLAN to H1 only and selected flush_session + render-gate as the closure hardenings.
**Decision:** In scope: CLI + wrapup rewrite + flush_session lock adoption + a render-gate test + a **subprocess-based** concurrency proof. Out: `/hm:health` stale-render smoke and the `HM_RUN_PARALLEL_SESSION`-gated two-session integration test.
**Consequences:**
- ✅ Tight, low-risk diff; flush_session inclusion is required for H1 to actually close (it is the second concurrent writer).
- ⚠️ **Accepted residual (stale-render / human Edit):** non-participating writers keep unlocked RMW. No runtime detection ships (user declined the smoke); render-gate covers new renders only; surfaced as documented-risk H6 in RESEARCH.
- ⚠️ **Test-validity constraint (validator W1/CX6/CX9):** because `_locking`'s reentrant counter is **thread-local** and flock is **process-scoped**, a thread-based concurrency test would falsely pass (same-thread nested acquire no-ops, threads share one flock fd). The H1 proof MUST be **subprocess-based** (separate `python -m harness_maker.memory_md` invocations). "Threads" is removed from the test plan.
**Rejected alternatives:** include health-smoke + gated integration test — Rejected: beyond H1 scope per user.
**Source:** Interview #2, #4; validator W1.

### ADR-005: Canonical, base-rooted lock-path derivation shared by the CLI and the hook
**Status:** Accepted (2026-06-21, validator W2/CX2)
**Context:** The CLI takes `--root <dir>`; `flush_session._append_session_log` derives the session dir from its own `cwd` (flush_session.py:50). Flag-on wrapup runs `cd <WT>` while the PreCompact hook fires with cwd = project root and can fire mid-stage while a worktree is active. If one resolves to a worktree's `.claude/memory` and the other to base, they take **different** `.session.lock` files → the exact H1 lost-update the PLAN closes.
**Decision:** `memory_md` exports one canonical `session_lock_path(root) -> Path` (and `wiki_lock_path`/`failures_lock_path`) that **`.resolve()`s** the path (defeats relative/symlink spelling differences). **Session memory always targets the BASE repo `.claude/memory`**, never a worktree copy — session memory is shared project memory committed by wrapup on base; the worktree copy is ephemeral. Both the CLI and `flush_session` import and use this function verbatim; the hook resolves up to base when its cwd is a worktree.
**Consequences:**
- ✅ CLI and hook provably take byte-identical lock paths (Phase-2 unit test asserts it from equivalent-but-differently-spelled roots).
- ⚠️ A compaction checkpoint during a worktree-isolated stage writes to the base session log (correct — that is where wrapup commits from).
**Rejected alternatives:** per-cwd derivation (status quo) — Rejected: silent divergent locks.
**Source:** validator W2.

## 🏗️ Technical Design

**Current state:** `wrapup.md.j2` Step 5.1 (wiki upsert-by-slug inside `@hm:user:entries`), 5.2 (failures upsert + count++), 5.5 (session append) instruct Claude to use `Edit`/`Write` on the tier files. `hooks/flush_session.py:_append_session_log` does an unlocked Python append on compaction. No lock on any `.md` tier.

**Affected components:**
- NEW `src/harness_maker/memory_md.py` — locked CLI + canonical lock-path helpers (ADR-005).
- EDIT `src/harness_maker/hooks/flush_session.py` — wrap `_append_session_log` in `exclusive_lock(session_lock_path(base))`, resolve to base.
- EDIT `src/harness_maker/templates/stages/wrapup.md.j2` — Step 5.1/5.2/5.5 Edit→CLI.
- NEW tests: CLI unit + subprocess-concurrency + malformed fail-closed + os.replace-boundary + render-gate + hook-path-identity.

**Dependencies:** `memory/_locking.py` (`exclusive_lock`), `io_utils.atomic_write`. No new third-party deps.

**Data flow:**
```
wrapup Step 5.x ─Write tool─► mktemp 0600 (unique)  ─or stdin─►  memory_md CLI
                                                                     │ exclusive_lock(<tier>_lock_path(base).resolve())
                                                                     │   read tier .md
                                                                     │   parse @hm:user:entries block (fail-closed if malformed)
                                                                     │   upsert-by-slug / append / count++
                                                                     │   atomic_write  (fsync temp, os.replace)
flush_session hook ──────────────────────────────────────────────────┘ (same session_lock_path(base))
```

**CLI contract (`harness_maker.memory_md`):**
- `append-session --root <dir> [--body-file <p> | stdin]` → locked append to base `session/<date>.md` (header-created if absent).
- `upsert-wiki --root <dir> --slug <s> --category <c> [--body-file <p> | stdin]` → locked insert-or-replace `[wiki:<c>] <s>` inside `@hm:user:entries`.
- `upsert-failure --root <dir> --slug <s> --category <c> [--body-file <p> | stdin]` → locked insert-or-count++ `[fail:<c>] <s> | <date> | count:<N>` inside the block.
- Lock-path helpers `session_lock_path/wiki_lock_path/failures_lock_path` (ADR-005), all `.resolve()`d, base-rooted.
- **Fail-closed set (non-zero exit + verbatim stderr reason; validator W4/CX8):** missing `@hm:user:entries` open OR close marker; >1 `@hm:user:entries` block; non-integer `count:`; duplicate same-slug heading inside the block; entry body literally containing a marker string. Marker-absent-entirely (legacy/empty file) → create the block + warn (the one non-fatal case). Never EOF-append outside the marker.
- On lock-acquire failure → non-zero exit. wrapup template checks exit code (loud, never silent-skip).

## 📝 Implementation Plan

### Phase 1 — `memory_md` locked CLI + unit/concurrency/fail-closed tests
- `depends_on`: []
- `parallel_group`: serial-core
- `merge_hazards`: none (new module + new test file)
- **Scope (in):** `src/harness_maker/memory_md.py`, `tests/unit/test_memory_md.py`. **(out):** template, hook.
- Implement append-session / upsert-wiki / upsert-failure with `exclusive_lock`, canonical resolved lock-paths (ADR-005), marker-block placement, slug-dedup, count++, `atomic_write`, stdin/`--body-file`, fail-closed set, exit codes.
- **TDD (RED first):** append idempotency; upsert replaces-not-duplicates by slug; count++ increments; entry lands inside `@hm:user:entries`; marker-absent creates block (warn, rc=0); each **fail-closed** case → non-zero exit (dup/absent markers, non-int count, dup slug, body-contains-marker); multi-line + metachar body via stdin and via `--body-file` preserved verbatim.
- **os.replace-boundary test (CX3):** two locked operations across an `atomic_write` replace prove the sentinel `.lock` (not the target inode) provides mutual exclusion.
- **Subprocess concurrency proof (ADR-004; W1/CX6/CX9):** N≥8 **separate `subprocess.run` processes** (NOT threads) — mixed writer classes: same-slug upserts, different-slug upserts, append-session vs append-session, append-session vs a simulated flush_session append — barrier-start → assert ALL entries present, counts correct, no lost-update. Plus a **negative test**: an unlocked direct file RMW (simulating a stale Edit) concurrent with the CLI CAN lose an entry → documents the participating-writers boundary.
- **Exit criterion:** `uv run pytest tests/unit/test_memory_md.py -q` green; `uv run mypy --strict src/harness_maker/memory_md.py` clean.
- **Risk:** medium (concurrency + parsing). **Rollback:** revert Phase 1 (nothing depends yet).

### Phase 2 — flush_session adopts the canonical session lock
- `depends_on`: [1]
- `parallel_group`: serial-core
- `merge_hazards`: none
- **Scope (in):** `src/harness_maker/hooks/flush_session.py`, `tests/unit/test_flush_session.py` (extend). **(out):** template.
- Wrap `_append_session_log` in `exclusive_lock(session_lock_path(base))`, importing the helper from `memory_md`; resolve cwd→base when fired inside a worktree (ADR-005). Preserve no-fcntl graceful degrade.
- **Exit criterion:** unit test asserts the hook + CLI compute **byte-identical resolved** `.session.lock` paths from equivalent-but-differently-spelled roots (symlink/relative/worktree-cwd); hook still appends correctly; existing flush_session tests green.
- **Risk:** low. **Rollback:** revert to Phase 1 state.

### Phase 3 — wrapup template rewrite + render-gate
- `depends_on`: [1]
- `parallel_group`: serial-template
- `merge_hazards`: `wrapup.md.j2` + snapshot fixtures (snapshot regen = regenerated-output hazard — serialize).
- **Scope (in):** `templates/stages/wrapup.md.j2` Step 5.1/5.2/5.5, snapshot fixtures, `tests/.../test_memory_md_render_gate.py`. **(out):** other stages.
- Replace Edit/Write-on-tier instructions with: write body to a unique `mktemp` 0600 file (Write tool) **or** pipe via stdin → run the memory_md CLI → check exit code → clean up temp. Keep marker-discipline prose (CLI enforces; prose explains why). Preserve Step 5.6 promotion + receipt.
- **render-gate test** (mirror `test_owned_uuids_render_gate`): rendered wrapup invokes `memory_md` and contains NO instruction to `Edit`/`Write` directly on `wiki.md`/`failures.md`/`session/`.
- Regenerate snapshots; mask `generated_at`.
- **Exit criterion:** render-gate green; `uv run pytest tests/ -q` green; snapshot regen deterministic.
- **Risk:** medium (template + snapshot churn). **Rollback:** revert template + snapshots to Phase 2 state.

## 🧪 Testing Strategy

- **Unit:** CLI subcommands (append/upsert/count/marker/body via stdin+file/exit-codes); each fail-closed case; flush_session locked append; CLI↔hook byte-identical resolved lock path.
- **Concurrency (subprocess, in-process suite — NOT the gated HM_RUN_PARALLEL_SESSION suite):** N≥8 separate processes, mixed writer classes, barrier-start → no lost-update. Negative test: unlocked legacy writer CAN lose an entry (boundary doc).
- **os.replace-boundary:** sentinel lock holds mutual exclusion across atomic-replace.
- **Render-gate:** wrapup uses CLI, no Edit-based tier write.
- **Regression:** full `uv run pytest` + `ruff check` + `ruff format --check` + `mypy --strict`; snapshot regen.

## ⚠️ Risks & Mitigation

| Risk | Sev | Mitigation |
|------|-----|------------|
| TOCTOU if RMW straddles the lock | High | CLI does read+modify+write *inside* the lock (ADR-001); Claude never reads-then-writes. |
| CLI↔hook take different locks (cwd/symlink/worktree) | High | Canonical `.resolve()`d, base-rooted lock path shared by both (ADR-005) + byte-identical-path test. |
| Non-participating writer (stale render / human Edit) clobbers | Med | **Accepted residual** (ADR-004); render-gate for new renders; documented H6; negative test documents it. |
| Malformed tier file → silent wrong-entry overwrite | Med | Enumerated fail-closed set, non-zero exit + reason (W4/CX8); RED test each. |
| Body staging collision / pre-lock TOCTOU | Med | stdin or unique 0600 mktemp, cleanup (ADR-003). |
| CLI failure silently skips an entry | Med | Non-zero exit + template exit-code check (loud). |
| Crash-safety overclaim | Low | `atomic_write` fsyncs temp (confirmed) → "no partial/torn file"; dir not fsync'd → not full power-loss durability (CX7); claim narrowed. |
| no-fcntl platform (true Windows) | Low | `_locking` degrades to no-op+warn → **no mutual exclusion** on that path; N-A for WSL2/Linux/macOS; recorded as a success-criterion boundary (CX5). |
| Snapshot churn breaks unrelated fixtures | Low | Regen + `generated_at` mask; render-gate pins the contract. |

## ✅ Success Criteria

- [x] **Subprocess** N≥8 concurrency test (mixed writers) shows zero lost updates on session + wiki + failures.
- [x] Negative test confirms an unlocked legacy writer CAN lose an entry (participating-writers boundary documented).
- [x] wiki upsert dedups by slug; failures count++ increments; entries land inside `@hm:user:entries`; each fail-closed case exits non-zero.
- [x] CLI and flush_session compute byte-identical resolved `.session.lock` paths; session memory targets base.
- [x] render-gate: rendered wrapup invokes `memory_md`, no Edit-based tier write.
- [x] Guarantee boundary recorded: on no-fcntl platforms mutual exclusion is NOT provided (N-A for WSL2).
- [x] `ruff check` + `ruff format --check` + `mypy --strict` + full `pytest` green.

## 🔍 Plan Validation

**Codex second opinion:** `codex_status: invoked` (Production preset, mandatory gate; gpt-5.5, exit 0, 9 findings). **plan-validator:** `NEEDS_REVISION` → **resolved** (all warnings folded; no critical — the lock primitive is sound and reused correctly).

| Finding | Severity | Disposition | Where folded |
|---------|----------|-------------|--------------|
| W1/CX6/CX9 thread-vs-subprocess proof | warning | revise | ADR-004, Phase 1, Testing |
| W2/CX2 CLI↔hook lock-path identity | warning | revise | **ADR-005** (new), Phase 2 |
| W3/CX1 "close H1" overclaim | warning | revise | Exec Summary guarantee boundary, ADR-001 |
| W4/CX8 malformed fail-closed set | warning | revise | CLI contract, Phase 1 |
| CX3 never-lock-target invariant + replace-boundary test | suggestion | revise | ADR-002, Phase 1 |
| CX4 body staging TOCTOU | suggestion | revise | ADR-003 |
| CX7 crash-safety wording | suggestion | revise | Prior Work, Risks |
| CX5 no-fcntl boundary | suggestion | revise | Risks, Success Criteria |

Clean categories (validator): risk-register, rollback-strategy, missing-interview-rounds, spec-alignment.

## 🚦 Execute Status (2026-06-21)

- **Phase 1 — memory_md locked CLI: DONE.** `src/harness_maker/memory_md.py` + `tests/unit/test_memory_md.py` (21 tests incl. 12-process subprocess concurrency proof, deterministic unlocked-RMW negative, full fail-closed set, os.replace-boundary). GREEN; mypy clean.
- **Phase 2 — flush_session adopts lock: DONE.** `_append_session_log` routes through `memory_md.append_session` (shared base-rooted lock, ADR-005). `tests/unit/test_flush_session.py` extended (base-from-worktree, hook∪CLI coexist one file). GREEN.
- **Phase 3 — wrapup template rewrite + render-gate: DONE.** Step 5.1/5.2/5.5 → `memory_md` CLI; `tests/unit/test_memory_md_render_gate.py` GREEN; 8 snapshots regenerated from base (count:7 trap avoided — regen ran post-finalize from base, not in worktree).
- **Verification:** full `pytest` + `ruff check` + `ruff format --check` + `mypy --strict src/` GREEN from base. Changes staged (not committed — wrapup owns the commit).
