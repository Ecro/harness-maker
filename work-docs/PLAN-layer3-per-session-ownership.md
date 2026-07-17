---
type: plan
task_slug: layer3-per-session-ownership
status: complete
created: 2026-06-21
tags: [harness-maker, plan, git-worktree, concurrency, multisession, post-commit-pop]
interview_rounds: 1
adrs: 5
validator_outcome: MAJOR_REVISION_RESOLVED
summary: "post-commit-pop owns refs by the session's EXECUTE-worktree uuid (not wrapup <WT>); fail-safe-skip on empty; producer-gated; C3 deferred."
---

# PLAN — Harden Layer 3 per-session ownership

## 🎯 Executive Summary

**What:** Make Layer 3 of the cross-session worktree defense genuinely *per-session*.
`post-commit-pop` restores a deferred finalize-stash iff its `session_uuid` is in
`HM_OWNED_SESSION_UUIDS`, but today that env is sourced from `owned-uuids`
(`_owned_session_uuids`), which globs **all** sessions' `.hm-loop-*` markers. So a
session's `post-commit-pop` restores a PEER's deferred stash → the 3×-recurring
`worktree-finalize-pulls-orphan-wip-into-main` contamination (the P0 that forced the
revert of PLAN-fleet-10-20-parallel-safety's C3; "Layer 3 wiring gap, follow-up task #14").

**Why now:** the contamination path is open today and is the precondition for safely
re-enabling the per-session queue-guard (C3, a separate fast-follow).

**Key decisions (revised post-validator MAJOR_REVISION):**
- **Identity = the session's EXECUTE-worktree uuid, carried by the LLM** (ADR-001). The
  finalize-stash ref a session must pop was written by *its own* `execute-<uuid12>-<ts>`
  worktree (only the legacy stash path writes refs; flag-on task worktrees route to
  `_finalize_commit_not_stash` and write none). At wrapup that execute worktree is already
  removed, and the wrapup-time `<WT>` is the WRONG worktree (a flag-on `hm/<slug>` task dir
  with no uuid, or absent on flag-off). So the owned id is NOT `wt-uuid <wrapup-WT>`; it is
  `wt-uuid <execute-worktree-path>` — the `execute-<uuid>-<ts>` path the session saw in the
  **execute Step 0** output, carried in the conversation. `wt-uuid` is a pure string parse
  (works after the dir is gone).
- **Consumer fail-safe (ADR-003):** a `session_uuid`-bearing ref not in the owned-set is
  SKIPPED, **including on an empty set** (one-line guard drop at `worktree.py:3224`).
- **Safety is producer-gated, not consumer-proven (ADR-005):** `post-commit-pop` still pops
  any ref whose uuid IS in the supplied set, so the guarantee is only **"the SHIPPED
  templates can only under-pop"** — a render/grep gate proves no rendered command sources
  `HM_OWNED_SESSION_UUIDS` from `owned-uuids`, and `owned-uuids` is loudly deprecated.
- **Scope = Layer 3 only** (ADR-002); C3 re-enablement is a fast-follow.
- **`owned-uuids` deprecated** (ADR-004); legacy no-`session_uuid` refs are bounded
  pre-upgrade because the ref writer derives the uuid from the always-uuid'd dirname —
  proven by a test.

**Estimated impact:** `worktree.py` (`wt-uuid` CLI + one-line `post-commit-pop` guard fix +
`owned-uuids` loud-deprecate) + 2 templates under `src/harness_maker/templates/stages/` +
snapshot updates + a render-grep gate + new unit + real multi-session tests + CLAUDE.md.

## 📚 Prior Work

- `[[fail:design worktree-finalize-pulls-orphan-wip-into-main]]` (count:3) — the
  contamination this closes; a 4th recurrence = a layer regressed.
- `[[wiki:pattern cross-session-worktree-defense-5-layer]]` — names this "Layer 3 wiring
  gap (follow-up task #14)".
- `[[wiki:gotcha orphan-stash-registration-drain-manual]]` — empty owned-set + absent
  markers skip; manual drain is the canonical path for stranded refs.
- `[[wiki:gotcha owned-session-uuids-is-all-markers-not-per-session]]` + `[[fail:design
  friction-looking-guard-was-load-bearing-safety]]` — the diagnosis.
- `[[fail:test snapshot-regen-inside-worktree]]` (count:7) — regen with the canonical pin.

## 🎙️ Interview Transcript

| # | Topic | Category | Question | Choice | Note | → ADR |
|---|-------|----------|----------|--------|------|-------|
| 1 | Identity source | Architecture | How does post-commit-pop learn "my" worktree uuid on WSL2? | LLM-known worktree uuid — **refined post-validator to the EXECUTE worktree uuid** | command-Bash can't read its session id; wrapup `<WT>` is the wrong worktree | ADR-001 |
| 2 | Scope | Scope | Fix Layer 3 only, or also re-enable C3? | **Layer 3 only** (C3 = fast-follow) | Smallest, verifiable first | ADR-002 |

Validator MAJOR_REVISION (2 critical + 4 warning + 1 suggestion; 7 Codex findings, 6
accepted) resolved in this revision — see `## 🔍 Plan Validation`. Defensible defaults
(not asked): fail-safe consume-side (ADR-003); producer-gate (ADR-005); legacy-ref
boundedness proven by a writer test (ADR-004).

## 📐 Architecture Decision Records

### ADR-001: Identity = the session's EXECUTE-worktree uuid (LLM-carried), not the wrapup `<WT>`
**Status:** Accepted (2026-06-21, via /hm:plan interview #1 + validator critical #1)
**Context:** `post-commit-pop` must restore only the refs THIS session deferred. Those refs
are written only by the legacy stash path, each carrying its `execute-<uuid12>-<ts>`
worktree uuid (flag-on task worktrees route to `_finalize_commit_not_stash` — no ref).
WSL2 command-Bash cannot read its own session id. **Validator critical:** the `<WT>` the
wrapup template has is NOT that execute worktree — flag-on it is `hm/<slug>` (no uuid),
flag-off there is no `<WT>` at all — so `wt-uuid <wrapup-WT>` would source the wrong/empty
id and fail-safe-skip the session's OWN stash (a regression vs today's all-markers which at
least pops it).
**Decision:** Two sources, primary machine-derived + LLM fallback (only the legacy stash
path writes refs — this whole ADR is flag-OFF; on `feature_branch_workflow` there is no
stash ref and the owned-set is empty by design):
1. **Primary — a slug-keyed crumb (survives session boundaries).** Execute's stage-only
   finalize, which already knows its own `execute-<uuid>-<ts>` `<WT>` and writes the stash
   ref, ALSO appends that uuid to `.claude/.hm-owned-uuids-<slug>` (gitignored churn). Wrapup
   reads `HM_OWNED_SESSION_UUIDS` from this crumb **by its own `<slug>` arg** (machine-derived,
   so a **standalone / recovered / post-`/compact` `/hm:wrapup <slug>`** works without any
   conversation memory), and deletes the crumb after a successful pop. Slug-keying is
   per-task: distinct-slug peers write distinct crumbs; a same-slug collision (blocked by
   SharedSlug on flag-on; a user footgun on flag-off) is last-writer-wins → at worst strands
   one owner's stash (fail-safe), never pops a peer.
2. **Fallback — the LLM-known execute path.** When the crumb is absent (pre-upgrade, or a
   hand-run wrapup), the template lets the LLM pass `wt-uuid <the execute-<uuid>-<ts> path it
   created this session>` (the execute Step 0 token), comma-joined. `wt-uuid` is a pure
   string parse (works after the dir is gone).
3. **Absent-case (both unavailable):** empty owned-set → ADR-003 fail-safe-skip (own stash
   preserved, NO peer pop) + a **loud** "owned-set empty — your deferred stash is preserved,
   run the manual drain" stderr (so the stranded ref is visible, not silent — CLAUDE.md
   absent-case checklist #1).
**Consequences:**
- ✅ Auto-pop works on the standalone/recovery wrapup (the headline interruption-survival
  case) via the slug crumb — not just same-conversation wrapup.
- ✅ Sources the uuid that matches the deferred refs; never pops a peer.
- ⚠️ Adds a small gitignored crumb format (slug-keyed); its absent case is defined + loud.
**Rejected alternatives:**
- LLM-conversation-memory only (prior revision) — the validator-found standalone-wrapup gap:
  owner's own stash silently stranded on every recovered wrapup.
- `wt-uuid <wrapup-WT>` — wrong/empty worktree (flag-on slug / flag-off none).
- Per-session ledger keyed by session id / SessionStart registry — need the unreliable WSL2
  env-file channel that is the root problem (slug-keying sidesteps it).
**Source:** Interview #1 + validator critical #1 + 2nd-pass warning (absent-case)

### ADR-002: Scope = Layer 3 only; C3 re-enablement is a fast-follow
**Status:** Accepted (2026-06-21, via /hm:plan interview)
**Context:** With Layer 3 per-session-safe, the reverted C3 becomes safe to re-apply, but
bundling doubles blast radius and couples two reviews.
**Decision:** This plan fixes Layer 3 only; C3 re-enablement is a separate fast-follow once
the Phase-3 test proves per-session ownership.
**Consequences:** ✅ small, independently verifiable. ⚠️ the fleet false-block remains until
the follow-up; `--allow-stash-queue` is the interim escape.
**Rejected alternatives:** Layer 3 + C3 together — rejected: larger, C3's safety only argued.
**Source:** Interview #2

### ADR-003: Consumer fail-safe = skip uuid'd refs not in the owned-set, INCLUDING empty
**Status:** Accepted (2026-06-21, defaults + code re-read)
**Context:** `post-commit-pop:3224` is `if owned_uuids and ref_session_uuid and
ref_session_uuid not in owned_uuids: continue`. The `owned_uuids and` term means an EMPTY
set short-circuits strict mode OFF → falls to the `:3238` marker-exists accept → POPS any
live-marker ref (vulnerable when the LLM passes nothing).
**Decision:** Drop the `owned_uuids and` term → `if ref_session_uuid and ref_session_uuid
not in owned_uuids: continue`. A uuid'd ref is skipped whenever its uuid is not owned,
empty set included. Legacy no-uuid refs still fall to the bounded marker accept (ADR-004).
**Consequences:** ✅ empty/unknown owned-set is genuinely fail-safe. ⚠️ a legit owner who
didn't pass its uuid won't auto-pop its own stash → surfaced by the "stale ref … preserved"
stderr; manual drain documented.
**Rejected alternatives:** keep the short-circuit (source-only fix) — leaves the empty case
popping peers.
**Source:** `worktree.py:3224` re-read + Codex/validator

### ADR-004: `owned-uuids` deprecated; legacy-ref boundedness PROVEN, not asserted
**Status:** Accepted (2026-06-21, defaults + writer re-read)
**Context:** `_owned_session_uuids` (all-markers) is the vulnerable source. The legacy
no-`session_uuid` marker-accept is a contamination hole IF a current writer can emit a
no-uuid ref.
**Decision:** (a) `owned-uuids` CLI kept for back-compat but emits a loud stderr "diagnostic
only — NOT a per-session ownership set; do not feed to post-commit-pop" on every call, and
no template sources from it. (b) **Prove the legacy hole is bounded:** the ref writer
`_write_stash_ref_file` already derives `effective_uuid = session_uuid or
_extract_uuid_from_wt_name(wt_name) or _current_session_uuid(base)` (`worktree.py:~1413`), so
a standard `execute-<uuid>-<ts>` worktree ALWAYS stamps a uuid — a Phase-1 test locks this,
making "legacy = pre-upgrade only" checkable rather than asserted.
**Consequences:** ✅ no live no-uuid writer; the marker accept only ever sees genuinely old
refs. ⚠️ a hypothetical non-uuid worktree name would still fall through — out of scope
(create() only emits uuid names; covered by the writer test).
**Rejected alternatives:** delete `owned-uuids` — deferred (deprecate-then-remove).
**Source:** writer re-read + Codex/validator

### ADR-005: Safety is producer-gated — narrow the guarantee + a render/grep gate
**Status:** Accepted (2026-06-21, via validator critical #2 + Codex #1)
**Context:** `post-commit-pop` pops any ref whose uuid IS in the supplied set; it cannot
distinguish a correct single-owner set from an overbroad `{A,B}`. So the safety depends on
the PRODUCER (templates) supplying only the own uuid. An OLD deployed harness whose rendered
`commands/hm/wrapup.md` still sources `owned-uuids` keeps contaminating until re-rendered.
**Decision:** State the guarantee precisely — **"the SHIPPED (re-rendered) templates can only
under-pop"** — and enforce it with a **render/grep gate**: a test that fails if any rendered
`commands/hm/*.md` assigns `HM_OWNED_SESSION_UUIDS` from `owned-uuids`. Add a migration note:
existing user harnesses must run `/harness-maker:make --update` to re-render; `/hm:health`
flags a stale render that still sources `owned-uuids`.
**Consequences:** ✅ a future template regression is caught at render-test time. ⚠️
not-yet-re-rendered harnesses keep the old behavior — inherent to any template change,
surfaced by `/hm:health` + the migration note.
**Rejected alternatives:** claim consumer-side safety — false; rejected.
**Source:** validator critical #2 + Codex #1

## 🏗️ Technical Design

**Current state:**
- `post-commit-pop` (`worktree.py:3202`) globs ALL `.hm-finalize-stash-*` refs; skip guard
  `:3224` (`owned_uuids and …`) + `:3238` marker-accept pop.
- `HM_OWNED_SESSION_UUIDS` set by `src/harness_maker/templates/stages/execute.md.j2:365/369`
  AND `…/wrapup.md.j2:380/384` from `$(worktree owned-uuids "$(pwd)")` (all-markers).
- Ref writer `_write_stash_ref_file` (`:1350`) derives the uuid from the dirname (`:~1413`).
- `_extract_uuid_from_wt_name` / `_WT_NAME_RE` (`:187`) require a `-<uuid12>-` segment.

**Affected components:**
1. `worktree.py` — `_cli_wt_uuid` + `wt-uuid` dispatch (pure parse, stderr-warn on empty);
   `post-commit-pop` `:3224` guard drop; `owned-uuids` loud-deprecate.
2. `src/harness_maker/templates/stages/execute.md.j2` + `…/wrapup.md.j2` — source
   `HM_OWNED_SESSION_UUIDS` from `wt-uuid <execute-worktree-path>` (prose: the
   `execute-<uuid>-<ts>` from execute Step 0, NOT the task `<WT>`), both codex + non-codex.
3. Snapshot baselines + a new render-grep gate test.
4. New unit + integration tests + CLAUDE.md.

**Data flow (fixed):** execute creates `…/execute-<U>-<ts>` (Step 0 prints it) → stage-only
finalize defers ref `{session_uuid: U}`, writes crumb `.hm-owned-uuids-<slug>=U`, removes the
worktree → wrapup `<slug>`: `HM_OWNED_SESSION_UUIDS="$(owned-crumb-read <base> <slug>)"`=U
(works even in a fresh/recovered session) → globs refs → peer ref `{V≠U}` skipped
(preserved); own ref `{U}` popped; crumb cleared. Empty set (no crumb + no LLM path) → all
uuid'd refs preserved + loud stderr.

**API/contract changes:** new `worktree wt-uuid <path-or-name>` (additive). The
`HM_OWNED_SESSION_UUIDS` env contract is unchanged (CSV of owned uuids) — only its producer.
Consume side changes one guard line (ADR-003).

## 📝 Implementation Plan

### Phase 1 — `wt-uuid` CLI + post-commit-pop empty-set fix + writer-uuid proof
- `depends_on`: `[]`
- `parallel_group`: `serial-core`
- `merge_hazards`: `worktree.py` (CLI + guard + deprecate — one file)
- **Scope (in):** `worktree.py` — (a) `_cli_wt_uuid(args)`: parse each `<path-or-name>` via
  `_extract_uuid_from_wt_name(Path(arg).name)`, print CSV of non-empty uuids (exit 0), emit
  a one-line stderr warning per unparseable arg (keep empty stdout); wire `wt-uuid` into
  dispatch + usage. (b) Drop the `owned_uuids and` term at `:3224`. (c) `owned-uuids`
  loud-deprecate stderr. (d) **slug-crumb helpers**: `owned-crumb-add <base> <slug> <uuid>`
  (atomic append to `.claude/.hm-owned-uuids-<slug>`, dedup) called by stage-only finalize;
  `owned-crumb-read <base> <slug>` (CSV, empty if absent) for the templates;
  `owned-crumb-clear <base> <slug>` after a successful pop. Add the crumb glob to the
  `_HARNESS_CHURN_PREFIXES` gitignore set.
- **Scope (out):** templates (Phase 2); the pop/cleanup body.
- **Exit criterion:** `uv run pytest tests/unit/test_worktree_wt_uuid.py
  tests/unit/test_worktree_post_commit_pop_ownership.py -q` green —
  `wt-uuid` of `execute-deadbeef1234-…` → `deadbeef1234`; of `.worktrees/myslug` → empty
  (+ stderr warn); multi-arg → CSV; non-existent path OK. post-commit-pop unit: a uuid'd ref
  with EMPTY `HM_OWNED_SESSION_UUIDS` is SKIPPED (preserved); a legacy no-uuid ref + present
  marker still pops; **`_write_stash_ref_file('execute-<u>-<ts>')` always stamps a non-empty
  `session_uuid`** (ADR-004 boundedness proof).
- **Risk:** medium (guard drop touches a data-loss branch).
- **Rollback point:** none.

### Phase 2 — Rewire both templates to the execute-worktree uuid + render-grep gate
- `depends_on`: `[1]`
- `parallel_group`: `serial-core`
- `merge_hazards`: `src/harness_maker/templates/stages/execute.md.j2`,
  `…/wrapup.md.j2` (snapshot baselines), `worktree.py` (deprecate note)
- **Scope (in):** execute's stage-only finalize call site → `owned-crumb-add <base> <slug>
  <execute-uuid>` (the slug from the stage context). Both templates' post-commit-pop line →
  `HM_OWNED_SESSION_UUIDS="$(… owned-crumb-read <base> <slug>)"` (machine-derived, works
  standalone); prose adds the LLM fallback "if the crumb is empty, pass `wt-uuid <the
  execute-<uuid>-<ts> path you created>`" + the flag-on note "**on
  `feature_branch_workflow` there is no stash ref → owned-set empty by design; execute Step 0
  there prints a `hm/<slug>` task path, not `execute-<uuid>`**" (validator suggestion); both
  codex + non-codex variants; `owned-crumb-clear` after pop. Regenerate snapshots with the
  canonical pin (`[[fail:test snapshot-regen-inside-worktree]]`).
- **Scope (out):** post-commit-pop body.
- **Exit criterion:** snapshot tests green; **render-grep gate** (new
  `tests/unit/test_owned_uuids_render_gate.py`): rendered `commands/hm/{execute,wrapup}.md`
  contain `wt-uuid` and **no** `HM_OWNED_SESSION_UUIDS=…owned-uuids` (ADR-005, both variants).
- **Risk:** medium (template + snapshot-regen footgun).
- **Rollback point:** Phase 1.

### Phase 3 — Real multi-session contamination regression (consumer)
- `depends_on`: `[1, 2]`
- `parallel_group`: `serial-verify`
- `merge_hazards`: new test file (`none` for source)
- **Scope (in):** `tests/integration/test_layer3_per_session_pop.py` — (a) sessions A,B each
  with a distinct-uuid ref + live marker; `post-commit-pop` as A (`HM_OWNED_SESSION_UUIDS=<A>`)
  → A popped, **B's ref + stash PRESERVED** (the contamination regression guard). (b) EMPTY
  owned-set → both preserved (ADR-003). (c) **multi-owned-ref**: A owns 2 uuid'd refs + B
  owns 1, `HM_OWNED_SESSION_UUIDS=<A1>,<A2>` → both A popped, B preserved (CSV path).
  (d) **standalone wrapup via crumb**: write `.claude/.hm-owned-uuids-<slug>` = A's uuid,
  `owned-crumb-read` → A's set with NO conversation memory → A popped, B preserved, crumb
  cleared (the validator absent-case fix — auto-pop works on recovery). (e) **crumb absent →
  stranded-not-popped**: no crumb + empty env → A's own ref PRESERVED (fail-safe), B
  preserved, loud stderr emitted (no silent strand, no peer pop).
- **Scope (out):** producer/render checks (those are Phase-2's render-grep gate, NOT here —
  with `{A,B}` the consumer correctly pops both; producer safety is the render gate).
- **Exit criterion:** `INTEGRATION=1 uv run pytest tests/integration/test_layer3_per_session_pop.py -q`
  green; the B-preservation + empty-set + multi-ref assertions all hold.
- **Risk:** medium (real git stash fixtures).
- **Rollback point:** Phase 2.

### Phase 4 — Docs: CLAUDE.md Layer-3 status + migration + C3 fast-follow
- `depends_on`: `[1, 2, 3]`
- `parallel_group`: `serial-docs`
- `merge_hazards`: `CLAUDE.md`; `none` for code
- **Scope (in):** Multi-session section — Layer 3 now sources ownership from the session's
  execute-worktree uuid (not all-markers); the guarantee is "shipped templates under-pop";
  the **migration note** (old harnesses must `/harness-maker:make --update`; `/hm:health`
  flags a stale render still sourcing `owned-uuids`); revise the load-bearing-foreign-counting
  note to "C3 re-enablement is now the unblocked fast-follow"; memory entry at wrapup.
- **Scope (out):** behavioral code.
- **Exit criterion:** CLAUDE.md within budget; `/hm:health` guardrails smokes green; each ADR
  maps to the doc.
- **Risk:** low.
- **Rollback point:** Phase 3.

## 🧪 Testing Strategy

- **Unit:** Phase 1 — `wt-uuid` parse (valid/slug-empty+warn/multi/non-existent); the
  post-commit-pop empty-set skip; the writer-always-stamps-uuid proof.
- **Render/grep:** Phase 2 — both templates source `wt-uuid`, never `owned-uuids` (ADR-005).
- **Integration:** Phase 3 — peer preserved / owner popped / empty preserves / multi-ref CSV.
- **Manual:** none.

## ⚠️ Risks & Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| LLM substitutes the wrong worktree (task `<WT>` not execute `<WT>`) | medium | low | Fail-safe (ADR-003): `wt-uuid` of a slug name → empty + stderr warn → skips own ref (WIP preserved, manual drain). Template prose pins the execute-`<uuid>` token. |
| Stale rendered harness still sources `owned-uuids` (overbroad set) | medium | high (contamination) | ADR-005 render-grep gate (no shipped path); migration note + `/hm:health` stale-render flag; `owned-uuids` loud-deprecate stderr. |
| Legacy no-uuid ref still pops on marker-presence | low | low | ADR-004 writer-uuid proof test: current writer always stamps a uuid from the dirname → bounded to genuine pre-upgrade refs. |
| Owner's own stash stranded (uuid not passed) | low | low | "stale ref … preserved" stderr surfaced in wrapup prose; manual drain documented. |
| Snapshot-regen contamination | medium | medium | Canonical `HM_MAIN_CHECKOUT_PATH` pin; assert only the two template hashes change. |
| Multi-worktree CSV parse bug | low | low | Phase-3 multi-owned-ref case exercises the CSV end-to-end. |

## ✅ Success Criteria

- [x] `worktree wt-uuid <path-or-name>` returns the uuid for `execute-<uuid>-<ts>` (works for a
      non-existent path); empty + stderr warn for a non-uuid (slug) name; CSV for multiple.
- [x] `post-commit-pop` SKIPs a `session_uuid`-bearing ref on an EMPTY `HM_OWNED_SESSION_UUIDS`
      (the ADR-003 guard drop); legacy no-uuid refs still pop on marker-presence.
- [x] The ref writer always stamps a non-empty `session_uuid` for a standard worktree name
      (ADR-004 boundedness proof).
- [x] Both templates source `HM_OWNED_SESSION_UUIDS` from the slug crumb (`owned-crumb-read`,
      LLM `wt-uuid` fallback), NOT `owned-uuids`; a render-grep gate fails if any rendered
      command sources `owned-uuids`.
- [x] A standalone/recovered `/hm:wrapup <slug>` (no conversation memory) auto-pops the
      owner's stash via the slug crumb; with no crumb, the own stash is preserved + a loud
      stderr fires (no silent strand, no peer pop).
- [x] A real test proves a PEER's stash is PRESERVED while the OWNER's is popped; empty-set
      preserves all; a multi-owned-ref (A:2, B:1) case pops both A and preserves B.
- [x] `owned-uuids` carries a loud-deprecate stderr; CLAUDE.md documents the per-session
      sourcing, the "shipped-templates-under-pop" guarantee, the re-render migration, and the
      C3 fast-follow.

## 🚧 Execute Status (2026-06-21)

- **Phase 1 — DONE (GREEN).** `worktree.py`: `wt-uuid` CLI + `owned-crumb-add/read/clear`
  helpers + CLI + dispatch; the **`owned_uuids and` guard dropped at `:3224`** (empty
  owned-set now fail-safe-SKIPs a uuid'd ref — the core safety change); `owned-uuids`
  loud-deprecate. Tests: `tests/unit/test_worktree_layer3_ownership.py` (9, incl. the
  ADR-004 writer-uuid proof) GREEN; the 3 existing post-commit-pop tests updated to the
  new per-session contract (owner passes its own uuid via `HM_OWNED_SESSION_UUIDS`; the
  multi-repo cases read the union of the deferred refs' `session_uuid`s). ruff/format/mypy
  clean; broad worktree suite no regression.
- **Phase 2 — DONE (GREEN).** `execute.md.j2` + `wrapup.md.j2` rewired: post-commit-pop
  sources `HM_OWNED_SESSION_UUIDS` from `owned-crumb-read "$(pwd)" <slug>` (not
  `owned-uuids`); execute's finalize records the owned uuid via `owned-crumb-add … $(wt-uuid
  <WT>)`; wrapup clears the crumb after a successful pop. Render-grep gate
  `tests/unit/test_owned_uuids_render_gate.py` (3) GREEN. Snapshots regenerated (canonical
  pin) — only the execute/wrapup-fused commands' hashes changed (verified: no plan/health/
  spec/research contamination).
- **Phase 3 — DONE (GREEN).** `tests/unit/test_worktree_layer3_pop_isolation.py` (3, real
  git): a foreign-uuid live ref+stash is PRESERVED (contamination guard); an empty owned-set
  fail-safe-SKIPs a uuid'd ref (the guard-drop); the crumb feeds the owned-set per task. The
  owner-pops-with-its-own-uuid path is covered by the updated `test_worktree_stash.py`.
- **Phase 4 — DONE.** CLAUDE.md updated: Layer 3 is now per-session (crumb-sourced), the
  empty-set fail-safe, the producer render-gate + re-render migration, `owned-uuids`
  deprecation, and "C3 re-enablement is the unblocked fast-follow".
- **Verification:** full unit suite + ruff/format/mypy clean; worked **in-cwd** (no worktree)
  because Phase 1's changes were staged-not-committed in the base — a fresh worktree from
  HEAD would have lacked them (precedent: `[[in-cwd-no-isolation-due-to-concurrent-base]]`).
  No commit (wrapup owns it).

## 🔍 Plan Validation

**Validator outcome:** MAJOR_REVISION → **RESOLVED** (this revision).
**Codex second opinion:** `codex_status: invoked`. 7 findings; validator reconciled all
(6 accepted, 1 duplicate, 0 refuted).

Resolution map:
- **Critical #1 (validator-found: wrapup `<WT>` is the wrong worktree)** → ADR-001 re-pinned
  the owned id to the **execute-worktree uuid** (carried from execute Step 0), with a
  slug-name-returns-empty test + template prose.
- **Critical #2 / Codex #1 (overstated claim, producer-dependent)** → ADR-005: narrowed to
  "shipped templates under-pop" + render-grep gate + migration note + `owned-uuids`
  loud-deprecate.
- **Warning / Codex #2 (legacy boundedness asserted)** → ADR-004 + Phase-1 writer-uuid proof
  test (the writer derives the uuid from the dirname).
- **Warning / Codex #5 (Phase-3 criterion not checkable)** → split: consumer integration test
  (Phase 3) vs render-grep gate (Phase 2).
- **Warning / Codex #4 (multi-worktree undertested)** → Phase-3 multi-owned-ref case.
- **Warning (wrong template paths)** → corrected to `src/harness_maker/templates/stages/…`
  throughout.
- **Suggestion / Codex #3,#6,#7 (weak operator signal)** → `wt-uuid` stderr warning on empty;
  wrapup prose surfaces the "stale ref preserved" recovery line.

**2nd pass (re-validation): MAJOR_REVISION → NEEDS_REVISION** — all 7 prior items confirmed
resolved; 1 new warning + 1 suggestion, both resolved in THIS revision:
- **Warning (absent-case: standalone/recovered wrapup has no execute path in conversation →
  owner's own stash silently stranded)** → ADR-001 made the **slug-keyed crumb** the PRIMARY
  machine-derived source (works without conversation memory), LLM path a fallback, and the
  both-absent case loud (not silent) + a Phase-3 standalone + stranded-not-popped test.
- **Suggestion (flag-on prose mismatch: execute prints a slug path there, no stash ref)** →
  Phase-2 prose scopes the execute-`<uuid>` token to flag-OFF; flag-on owned-set is empty by
  design. **Net: no peer is ever popped (the contamination is closed); the residual is a
  fail-safe under-pop, now machine-recovered via the crumb.**
