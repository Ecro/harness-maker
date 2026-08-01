---
type: plan
task_slug: autopilot-advance-noop
status: complete
created: 2026-07-31
tags: [harness-maker, plan, python, autopilot, auto-advance, templates, observability]
research_doc: "[[RESEARCH-autopilot-advance-noop]]"
interview_rounds: 4
adrs: 10
validator_outcome: MAJOR_REVISION_RESOLVED
summary: "Autopilot announces but never advances: deterministic status, session-scoped marker, slug propagation, split ledger"
---

# PLAN — autopilot announces the next stage but does not run it

## 🎯 Executive Summary

**TL;DR** — Autopilot is dark. The `.hm-autopilot` marker on disk is 2 days stale, the
picker mistakes its mere existence for "already armed", so every boundary check returns
`kill_switch` and every stage prints its STOP banner. Four independent defects compound;
this PLAN fixes all four at the prompt + CLI layer and, critically, makes the failure
**measurable** so the deliberately-retired enforcement hook can be re-litigated with data
instead of anecdote.

**What:** deterministic `hm autopilot status`, TTL-only stale-marker GC, true
session-scoping of the marker, `task_slug` propagation into the auto-advance `Skill` call,
STOP-vs-advance instruction de-conflict across 7 stage templates, and an
`advance_authorized` / `advance_entered` ledger split carrying `elapsed_s`.

**Why:** the user reports "autopilot으로 다음으로 진행합니다" with no advance, "대부분"
of the time. Reproduced: `hm autopilot_caps boundary --root . --current research` →
`{"proceed": false, "halt_kind": "kill_switch"}` against a marker created 2026-07-29T01:47Z.

**Key decisions:**
- No enforcement hook this round — measure first ([[#adr-001]]).
- GC deletes on **TTL staleness only**, never on session-foreignness ([[#adr-002]],
  [[#adr-008]] — the safety invariant that ADR-007 creates).
- `task_slug` flows stage-terminal → boundary → marker → next stage's `Skill` args
  ([[#adr-003]]).
- Ledger splits authorization from entry; step cap counts entries ([[#adr-004]]).
- Entry is confirmed retroactively by the next stage's own boundary call, with
  `elapsed_s` so the auto-vs-manual threshold is a query, not a constant
  ([[#adr-005]], [[#adr-009]]).
- The unconditional Stage-terminal STOP in all 7 stage bodies becomes conditional
  ([[#adr-006]]).
- The marker becomes session-scoped on `HM_SESSION_ID`, closing the inverse leak
  ([[#adr-007]]).
- Arming refuses to overwrite a live peer's marker, and the picker branches on `reason`
  as well as `active` ([[#adr-010]] — the validator/antigravity convergent finding).

**Estimated impact:** ~6 source modules, 10 templates, 1 rendered-settings surface. Every
stage snapshot hash moves. No user data migration — marker and ledger are both
operational churn (gitignored).

## 📚 Prior Work

- [[RESEARCH-autopilot-advance-noop]] — the four defects and their evidence.
- **`539f05a9` `refactor(autopilot): remove the guard_when axis + autopilot_guard module`
  (2026-07-21)** — the single most important input. `autopilot_guard` was *deliberately*
  retired, so its absence is not a bug to fix by reversal. Its commit message asserts
  "Auto-advance is untouched — it never depended on the guard", which is mechanically true
  and operationally misleading: the guard's Stop-hook half was the only thing that could
  have observed a model stopping mid-pipeline. ADR-001 respects the retirement and adds
  the measurement the commit did not.
- `[wiki:pattern] stop-hook-backstop-stop-hook-active-first` — if the hook is ever revived
  (out of scope here), `stop_hook_active` must be checked FIRST or exit-2 re-fires forever.
  Also: the block reason was deliberately *descriptive* pre-P6 because no chainer existed;
  post-P6 one does, so a revival could finally use an imperative reason.
- `[wiki:pattern] gate-the-one-way-door-before-entering-its-stage` — why
  `_HUMAN_GATED_STAGES={wrapup}` exists. Untouched by this PLAN; the observed
  `gate_blocked` rows for `wrapup` are correct behavior.
- `[fail:design] producer-consumer-timestamp-resolution-mismatch` — the marker
  `created_at` / ledger `ts` resolutions must stay aligned (`isoformat()` both sides).
  ADR-004 adds a third timestamp comparison (`elapsed_s`); it inherits this constraint.
- `[fail:design] agent-command-guard-adjacency-regex-and-static-deny` — the four security
  holes the guard shipped with. Direct evidence for ADR-001's "do not revive casually".
- `[wiki:architecture] guard-when-interactive-scope` — describes `guard_when` as live. It
  is **stale**: `539f05a9` removed the axis end-to-end. Memory correction is a wrapup item.
- CLAUDE.md — `.claude/hooks/hooks.json` is dead in Claude Code (2026-07-17 experiment);
  the three `autopilot_guard` invocations still emitted there are inert but reference a
  deleted module (ADR-008 cleanup).

## 🎙️ Interview Transcript

| # | Topic | Category | Question | Options | Choice | Note | → ADR |
|---|---|---|---|---|---|---|---|
| 1 | Enforcement layer | Architecture | Revive a Stop-hook, or prompt+CLI only? | measure-first / revive advance-only hook / prompt-only no metric | **measure-first** | Respects the deliberate 539f05a9 retirement; hook decision deferred to a follow-up PLAN gated on ledger data | ADR-001 |
| 2 | Stale marker | Contract | Delete on detection, status-only, or rename? | delete + `status` / status-only / rename `.stale` | **delete + `status`** | Picker must branch on a JSON boolean, not on file existence | ADR-002 |
| 3 | Slug to next stage | Contract | Record slug in marker, infer from work-docs, or out of scope? | marker field / infer / skip | **marker field** | `Skill(hm:execute)` with no args stalls; that reads as "did nothing" | ADR-003 |
| 4 | Ledger fidelity | Observability | Split the event, add a flag, or defer? | split authorized/entered / bool field / defer | **split** | append-only JSONL cannot update a row, so a bool flag would never be set | ADR-004 |
| 5 | Who writes `entered` | Architecture | Next stage's boundary, a dedicated CLI line, or task-preflight? | retro-confirm via next boundary / new CLI line / fold into preflight | **retro-confirm** | Zero new prompt surface; a stage that dies mid-body correctly never confirms | ADR-005 |
| 6 | STOP conflict scope | Scope | Partial only, partial + 7 bodies, or restructure the banner? | partial only / partial + 7 bodies / move banner into false-branch | **partial + 7 bodies** | The earlier, stronger, unconditional STOP is the actual conflict; leaving it is leaving the bug | ADR-006 |
| 7 | Inverse leak | Scope | Fix cross-session marker inheritance too? | include / exclude / end interview | **include** | `_current_session_uuid` is project-scoped; both failure directions share one code path | ADR-007 |
| 8 | Slug ingress path | Contract | Terminal passes `--slug` + persist, pure pass-through, or picker asks? | persist / pass-through / picker asks | **persist** | Picker fires before a slug exists; terminal always knows it. Persistence self-heals a stage that omits the flag | ADR-003 |
| 9 | `entered` semantics | Observability | Unconditional, `elapsed_s`, or fixed window? | `elapsed_s` / unconditional / 5-min window | **`elapsed_s`** | No arbitrary constant in code; the auto-vs-manual threshold becomes a query answerable against historical rows | ADR-009 |
| 10 | Persisted slug fallback | Contract | Validator CR3: ADR-003 rejects slug inference, then adopts a fallback with the same failure mode. Keep, drop, or require? | loud+attributable / pure pass-through / `--slug` mandatory | **loud + attributable** | Interview #8 stands. Fallback gains `task_slug_source` + the authorizing stage, so a completed pipeline's slug is not reused and a persisted slug is always announced | ADR-003 (amended) |
| 11 | End-to-end verification | Testing | Validator W10: no phase exit observes the reported symptom. Promote the manual e2e to a gate? | Success Criteria only / Phase 5 exit / ledger-ratio gate | **Success Criteria only** | The manual observation is recorded as a success criterion but does not block a phase. Accepted risk: the suite can go green with the symptom intact (R2 already carries this) | — |

Rounds 1–4 (round 4 = validator follow-up), 11 entries, 0 deferred decisions. The 5-term gate skipped C5 (pipeline
composition — settled by `harness.yaml`), C6/C16 (naming, phasing — trivial),
C8 (backward compat — dictated by CLAUDE.md's absent-case rule), C13 (dead hook lines —
settled by `539f05a9`), C14 (degraded `HM_SESSION_ID` — answered inside ADR-007's option).

## 📐 Architecture Decision Records

### ADR-001: Fix the prompt + CLI layer only; defer the enforcement hook behind measurement
**Status:** Accepted (2026-07-31, via /hm:plan interview)
**Context:** Auto-advance is 100% model compliance and 0% mechanism. The obvious fix — a
Stop-hook that blocks termination while the marker is live — was deliberately deleted on
2026-07-21 (`539f05a9`), and its predecessor shipped four P0-class security holes
(`[fail:design] agent-command-guard-adjacency-regex-and-static-deny`).
**Decision:** This PLAN changes only stage prompts and the `autopilot*` CLI modules. No
hook is added or revived. ADR-004/005/009 make the compliance rate observable so a
follow-up PLAN can decide the hook question on data.
**Consequences:**
- ✅ Does not reverse a deliberate architectural retirement without evidence.
- ✅ Ships a metric that today does not exist in any form.
- ⚠️ If the prompt fixes prove insufficient, autopilot stays partly unreliable until a
  second PLAN lands. Accepted: the ledger will say so within days of use.
**Rejected alternatives:**
- Revive an advance-only Stop-hook now — rejected: re-opens a surface that failed k-of-n
  review, and we cannot yet state what fraction of non-advances it would fix.
- Prompt-only with no ledger work — rejected: reproduces the exact condition that let this
  bug live undetected (the ledger recorded every authorization as a success).
**Source:** Interview #1

### ADR-002: `hm autopilot status` is the sole arbiter of "is autopilot active?"
**Status:** Accepted (2026-07-31, via /hm:plan interview)
**Context:** The picker prose says "if **no** `.hm-autopilot` marker is active yet" but the
CLI exposes only `on`/`off`. With no way to evaluate "active", the model checks for the
file; a stale file therefore suppresses arming for up to forever (nothing deletes it).
**Decision:** Add `hm autopilot status [--root]` printing one JSON line. **This is the
single schema statement for the contract; the API Changes section references it, never
restates it** (validator S2):

```json
{"active": bool,
 "reason": "armed" | "absent" | "foreign" | "stale (gc'd)" | "future-dated" | "gc-failed: <errno>",
 "level": "gated"|"auto_safe"|"full"|null,
 "pipeline": [str]|null,
 "task_slug": str|null,
 "session_scoped": bool}
```

The picker branches on **`active` AND `reason`** — `active: false, reason: "foreign"` means
another live session owns the marker, so the picker must NOT arm (see ADR-010). Every
prose reference to checking the marker file is replaced by this call. `status` invokes the
ADR-008 GC.

**GC failure is never fatal** (validator W5 / codex cx7): `status` suppresses `OSError`
from the unlink (mirroring `write()`'s `contextlib.suppress(OSError)` at
`autopilot.py:163` and `clear()`'s `unlink(missing_ok=True)` at `:177`), computes `active`
regardless, reports `reason: "gc-failed: <errno>"`, and still exits 0. A picker starved of
JSON would revert to guessing at the marker file — the exact failure this ADR exists to
remove, re-entered through its own fix.
**Consequences:**
- ✅ Removes model guesswork from the arm decision — the dominant failure path.
- ✅ Reuses the `autopilot_caps boundary` JSON-out convention the templates already parse.
- ⚠️ One more Bash call at the first eligible stage of a session.
- ⚠️ `reason` is now load-bearing, not diagnostic — the picker's correctness depends on it.
  Phase 4's render-grep gate asserts the `foreign` branch exists in the picker text.
**Rejected alternatives:**
- Status without GC — rejected: the file keeps misleading any future direct reader.
- Rename to `.hm-autopilot.stale` — rejected: nothing would ever collect the renames, and a
  glob-based reader would re-acquire the same confusion.
**Source:** Interview #2

### ADR-003: `task_slug` travels stage-terminal → boundary → marker → next stage's Skill args
**Status:** Accepted (2026-07-31, via /hm:plan interview)
**Context:** The auto-advance block invokes `Skill(hm:<next_stage>)` with no arguments.
Stages that parse `$ARGUMENTS` (e.g. `.claude/commands/hm/execute.md:155`) start blank and
stall asking for a slug — indistinguishable from "announced but did nothing". The picker
cannot supply the slug because it fires before one exists (`/hm:research "<free topic>"`).
**Decision:** `AutopilotMarker` gains `task_slug: str | None = None` and
`task_slug_stage: str | None = None` (the stage whose terminal supplied it). Each stage
terminal passes `--slug <its own slug>` to `autopilot_caps boundary`; boundary persists
both and returns `task_slug` plus **`task_slug_source: "flag" | "persisted" | null`**. The
prompt invokes `Skill(hm:<next_stage>)` with that slug; when `task_slug` is null it invokes
with no argument (unchanged legacy behavior).

**Amended after validator CR3 / codex cx2 (Interview #10).** The original wording made the
persisted fallback *silent*, which reproduces the precise harm this ADR cites when
rejecting slug inference. Three constraints now bound it:
1. **Attributable** — `task_slug_source` distinguishes a flag-supplied slug from a
   persisted one.
2. **Loud** — when `task_slug_source == "persisted"`, the auto-advance block must state
   the slug it is about to pass before invoking `Skill`. A silent fallback is forbidden.
3. **Not reusable across pipelines** — the marker is cleared at `pipeline_complete`,
   `merge_gate`, and cap halts, so a completed pipeline's slug cannot survive into the
   next one. Within one armed session, `task_slug_stage` records provenance so an
   operator reading the marker can see which stage supplied it.

**Slug source mechanism (validator W7 / codex cx1).** The `--slug` value is supplied by
**model substitution of the slug already established for this stage** — the same value the
stage used for its `worktree task-preflight <slug>` call and its output filename. It is
**not** derived by any shell expression in the partial. Rationale: CLAUDE.md §2 records a
measured incident where Claude Code substitutes `$0`–`$9` in slash-command bodies before
the model sees them, silently corrupting `awk '{s+=$1}'` in `/hm:review` and `/hm:plan`.
`tests/structural/test_no_positional_params_in_commands.py` gates that class and **applies
to this new line** — Phase 4 asserts the emitted `--slug` line contains no positional
parameter.
**Consequences:**
- ✅ A stage that forgets `--slug` still advances, but the inherited slug is announced.
- ✅ Absent-case explicit: `None` → no argument, never a silent empty string.
- ⚠️ Marker schema change; `extra="forbid"` means an old marker is still valid (new fields
  are optional), but a *new* marker read by an old harness-maker would be rejected. Accepted:
  the marker is session-scoped operational state with an 18h TTL, not persisted config.
- ⚠️ `autopilot on` does **not** gain `--slug` (validator S1) — it had no caller; the slug
  only ever arrives via a stage terminal.
**Rejected alternatives:**
- Pure pass-through with no marker field — rejected twice (Interview #8, re-tested at #10):
  no recovery for a stage that omits the flag, which reproduces today's argument-less
  `Skill` stall.
- `--slug` mandatory, gate-blocked when absent — rejected at #10: a template bug that drops
  the flag would kill autopilot wholesale and silently, the exact failure shape under repair.
- Infer the slug from the newest `work-docs/PLAN-*.md` — rejected: silently advancing the
  wrong task is worse than not advancing.
- Picker asks for the slug — rejected: at research time neither side knows it.
**Source:** Interview #3, #8, #10

### ADR-004: Split the ledger into `advance_authorized` and `advance_entered`
**Status:** Accepted (2026-07-31, via /hm:plan interview)
**Context:** `autopilot_caps._cmd_boundary` appends `{"event": "advanced", "to": nxt}`
*before* the model does anything, and `count_events(root, "advanced")` feeds the step cap.
The ledger therefore cannot distinguish this bug from correct operation — which is why it
survived. `auto-advance.jsonl` shows `advanced` rows for advances that never happened.
**Decision:** Extend `LedgerEvent` to
`"advanced" | "advance_authorized" | "advance_entered" | "gate_blocked" | "halted_cap"`.
`boundary` writes `advance_authorized` on the proceed path. `advance_entered` is written
per ADR-005. The step cap counts `advance_entered`. The legacy `advanced` value is retained
in the Literal as read-only history and is never written again.

**Legacy-row window rule (validator W9 / codex cx3).** A legacy `advanced` row counts as an
entry **only when it falls OUTSIDE the current marker's window** (`ts < marker.created_at`)
— i.e. for historical continuity in `/hm:metrics` and the `smoke` denominator. Inside the
window the step cap reads **only** the new vocabulary. Without this rule, a marker armed
under old code and still inside its 18h TTL when the new code lands carries both
vocabularies in one window, and the same physical advance counts twice (fails safe — the
cap fires early — but it is exactly the absent-case CLAUDE.md requires be stated).
**Consequences:**
- ✅ "Authorized but never entered" becomes a first-class, countable state.
- ✅ Step cap counts work actually performed, not permission granted.
- ✅ The mid-window upgrade case has a defined answer rather than an emergent one.
- ⚠️ `autopilot_ledger smoke` and `readiness`'s auto-advance signals must learn both names,
  applying the window rule above.
**Rejected alternatives:**
- Add `entered: bool` to the existing row — rejected: the ledger is append-only JSONL; the
  row cannot be updated later, so the flag would be permanently `false`.
- Defer — rejected: ADR-001's whole premise is that the hook decision needs this data.
**Source:** Interview #4

### ADR-005: The next stage's own boundary/gate-blocked call retro-confirms entry
**Status:** Accepted (2026-07-31, via /hm:plan interview)
**Context:** Something must observe that stage N+1 actually started. No stage knows whether
it was auto-entered or user-invoked, and adding a dedicated CLI line to seven prompts taxes
every manual run.
**Decision:** When `autopilot_caps boundary --current X` or `gate-blocked --stage X` runs,
it looks for the earliest unconfirmed `advance_authorized` whose `to == X` within the
current marker's window. If found, it appends `advance_entered` (with `to`, `elapsed_s`)
before doing its own cap/gate work.

**Placement (validator CR1 — critical).** The retro-confirm runs **immediately AFTER the
`active_marker` resolution and BEFORE the cap/gate logic** in both subcommands. It must not
run first: `autopilot_caps.py:158-163` (boundary, `marker is None` → kill_switch) and
`:259-267` (gate-blocked) are deliberate early returns carrying the **P2-5 invariant** —
"a spurious call with no active marker (off / foreign / stale) must not pollute the ledger
or the smoke-check denominator with a phantom event". Confirming before that check would
append rows for every manual, autopilot-off run — polluting the very metric ADR-001 defers
the hook decision to. It is also self-contradictory: "within the current marker's window"
presupposes a marker.
**Consequences:**
- ✅ Zero new prompt surface and zero new Bash calls.
- ✅ A stage that stops mid-body reaches neither call, so it is correctly never confirmed —
  precisely the signal we are missing today.
- ⚠️ Confirmation is deferred to the *end* of stage N+1, so a chain killed mid-stage N+1
  under-reports by one. Accepted: under-reporting biases toward "autopilot is unreliable",
  the safe direction for ADR-001's follow-up decision.
- ⚠️ A user manually invoking stage X after a stalled advance also confirms it. Mitigated
  by ADR-009 rather than prevented.
**Rejected alternatives:**
- Dedicated `autopilot_caps entered --stage X` at each stage start — rejected: 7 prompt
  edits and a Bash call on every manual run, for a signal the boundary call already carries.
- Fold into `worktree task-preflight` — rejected: preflight runs for manual invocations too
  and does not run at all when `feature_branch_workflow` is off, so the metric would be
  config-dependent.
**Source:** Interview #5

### ADR-006: The Stage-terminal STOP becomes conditional in all 7 stage bodies
**Status:** Accepted (2026-07-31, via /hm:plan interview)
**Context:** Every stage body carries an unconditional, emphatic STOP
(`stages/research.md.j2:293`: "Do not proceed to `/hm:spec`, `/hm:plan`, or any other stage
without an explicit user command. This boundary must survive context compaction."). It
appears *before* the auto-advance block, which never claims to override it. A model
resolving that conflict conservatively prints the banner and stops.
**Decision:** (a) The auto-advance partial gains an explicit precedence sentence: on
`proceed: true` it supersedes this stage's Stage-terminal STOP. (b) All 7 stage bodies'
Stage-terminal paragraphs gain the reciprocal exception clause naming the auto-advance
check. Both sides must name each other — a one-sided override is what exists today.
**Consequences:**
- ✅ The contradiction is removed at both ends rather than papered over at one.
- ⚠️ Every stage snapshot hash moves; `tests/` baselines must be re-frozen.
- ⚠️ Still prose. This is the accepted cost of ADR-001.
**Rejected alternatives:**
- Partial only — rejected: leaves the stronger, earlier instruction intact, i.e. leaves
  the bug.
- Move the STOP banner inside the `proceed: false` branch — rejected: entangles the
  banner with loop-mode and Codex branching for a structural gain the explicit precedence
  sentence already delivers.
**Source:** Interview #6

### ADR-007: The marker is keyed on `HM_SESSION_ID`, with the project uuid as degraded fallback
**Status:** Accepted (2026-07-31, via /hm:plan interview)
**Context:** `_current_session_uuid` is project-scoped (`autopilot.py:219` admits it), so
within one project every session sees every other session's marker as its own. The only
real cross-session guard is the 18h TTL. This is the mirror of the reported bug: autopilot
silently *inherited* rather than silently off.
**Decision:** `AutopilotMarker` gains `claude_session_id: str | None = None`, written from
`$HM_SESSION_ID` at arm time (same source `loop_marker.py` uses).

**One-directional rule (validator W8 / codex cx5).** `active_marker` compares session ids
whenever **either** side has one; the project-uuid fallback applies **only when neither**
does. The originally-drafted symmetric rule ("compare only when both are non-empty") let an
id-bearing session inherit a fieldless legacy marker — a direction `loop_marker` explicitly
forbids. CLAUDE.md states that precedent exactly: the session-blind legacy global "is
honored **only when the caller has no id of its own** (`not sid`) — a valid-id session is
never blocked/mis-detected by a peer's global". The symmetric rule would have cited a
precedent that does not support it. The TTL check always applies.
**Consequences:**
- ✅ Both leak directions close in one code path.
- ✅ Genuinely reuses the `loop_marker` rule rather than citing it loosely.
- ⚠️ An in-flight session holding a pre-upgrade (fieldless) marker is re-classified as
  foreign after the upgrade and must re-arm via the picker. Accepted: the marker is
  18h-TTL ephemeral state, so the cost is one prompt.
- ⚠️ In degraded environments (SessionStart hook failure, Cursor, Codex) neither side has
  an id, so behavior is exactly today's — project-scoped + TTL. Surfaced by `status`'s
  `reason` and `session_scoped: false`, not silently.
- ⚠️ Creates the ADR-008 hazard: "foreign" now means "another live session".
**Rejected alternatives:**
- Out of scope — rejected: the GC in ADR-002 has to decide what to do with a foreign
  marker regardless, so the semantics must be settled now.
**Source:** Interview #7

### ADR-008: GC deletes on TTL staleness ONLY — never on session-foreignness
**Status:** Accepted (2026-07-31, derived constraint of ADR-002 + ADR-007)
**Context:** Under the old project-scoped uuid, a "foreign" marker meant a crash leftover
and deleting it was harmless. ADR-007 changes that: foreign now means **another live
session's armed marker**. A GC that deletes anything `active_marker` rejects would disarm a
concurrent session. There is exactly one marker path, so this is not hypothetical.
**Decision:** `gc_stale_marker(project_root)` unlinks the marker **iff** it parses and
`age > TTL`. It then **re-reads the file immediately before the unlink and deletes only if
the bytes are identical to what it judged stale** — otherwise a fresh replacement written
between the judgement and the unlink would be destroyed. A foreign-but-fresh marker is left
untouched and reported by `status` as `active: false, reason: "foreign"`. An unparseable
marker is treated as stale. GC is invoked from `status` and the picker path only — never
from `boundary`.

**Negative age is NOT a delete condition (validator W4 / codex cx6).** `active_marker`
already rejects `age < 0` (`autopilot.py:245`) and that is safe *because rejection is
non-destructive*. Promoting the same predicate to a delete makes a peer's freshly-armed
marker destroyable under clock rollback / NTP step / a differently-skewed host in a shared
tree — reaching the exact outcome this ADR exists to prevent. A future-dated marker is
therefore rejected-but-preserved, `reason: "future-dated"`.
**Consequences:**
- ✅ Concurrent sessions cannot disarm each other through the GC path (the *arming* path is
  closed separately by ADR-010 — GC alone was never sufficient).
- ⚠️ Under ADR-007 two concurrent sessions cannot both be armed via the shared path — the
  second one's `status` reports `foreign` and, per ADR-010, its picker does not arm.
  Accepted for this round (R3); a per-session marker filename is the eventual fix and is
  explicitly out of scope.
**Rejected alternatives:**
- Delete whatever `active_marker` rejects — rejected: silently disarms a peer session.
- Delete on `age < 0` as well — rejected after review: see above.
- Skip GC and rely on `status` alone — rejected by Interview #2.
**Source:** Interview #2 + #7 (derived), amended by validator W4

### ADR-010: Arming refuses to overwrite a live foreign marker; the picker branches on `reason`
**Status:** Accepted (2026-07-31, validator CR2 + antigravity ag1 — convergent finding)
**Context:** ADR-002 said "the picker branches on `active`" while ADR-008's consequence
claimed "the second session's picker does not arm". Those cannot both hold: `status`
returns `active: false` for a foreign-fresh marker, so a picker branching on the boolean
alone **offers arming**. And `autopilot.write()` (`autopilot.py:151-165`) has no ownership
guard — it unconditionally `atomic_write`s a marker stamped with the caller's identity. So
session B's picker would overwrite session A's live marker, and A's next `boundary` call
would judge that marker foreign → `kill_switch` → A's chain dies silently mid-pipeline.
ADR-008's headline "concurrent sessions cannot disarm each other" was false as drafted: it
closed the GC disarm path and left the arm path wide open.
**Decision:** Two changes, both required:
1. `write()` refuses to overwrite a marker that parses, is within the freshness window, and
   whose session identity is not the caller's. It raises a typed error; the CLI prints a
   diagnostic and exits non-zero. An explicit `--force` bypasses (for a user deliberately
   taking over a dead session's marker).
2. The picker branches on `active` **and** `reason`: `foreign` → do not arm, print the
   diagnostic, proceed gated. Phase 4's render-grep gate asserts this branch exists — a
   missing branch is otherwise undetectable on disk.
**Consequences:**
- ✅ Makes ADR-008's invariant actually true.
- ✅ Defense in depth — the prose branch and the code guard fail independently.
- ⚠️ A user whose peer session crashed without clearing the marker must wait out the TTL or
  pass `--force`. Acceptable: `status` names the condition explicitly.
**Rejected alternatives:**
- Picker branch only — rejected: prose is exactly the layer ADR-001 concedes is unreliable.
- `write()` guard only — rejected: the picker would still offer, and the user would see an
  arm attempt fail with no explanation.
**Source:** validator CR2, independently confirmed against `autopilot.py:151-165`; the same
gap was the one finding antigravity surfaced before its payload failed to parse.

### ADR-009: `advance_entered` carries `elapsed_s`; no auto-vs-manual threshold in code
**Status:** Accepted (2026-07-31, via /hm:plan interview)
**Context:** ADR-005's retro-confirmation cannot distinguish an auto-advance from a user
manually invoking the same stage later. A fixed window would bake an arbitrary constant
into code and could not be re-evaluated against historical rows.
**Decision:** `advance_entered` rows carry `elapsed_s` (float seconds between the matching
`advance_authorized` `ts` and the confirmation). No threshold exists in code. Analysis
(`/hm:metrics`, ad-hoc queries) applies whatever cutoff the question needs.
**Consequences:**
- ✅ The auto-vs-manual cutoff stays a query, re-answerable against all past rows.
- ✅ ADR-001's follow-up decision gets a distribution, not a single ratio.
- ⚠️ The step cap counts every `advance_entered` regardless of `elapsed_s`. Correct: a
  manually-resumed stage is still a step in the session.
**Rejected alternatives:**
- Fixed 5-minute window — rejected: misses legitimate auto-entry after a long `execute`,
  and changing the constant invalidates comparison with prior data.
- Unconditional with no timing — rejected: cannot separate "autopilot worked" from "the
  user rescued it", which is the exact question ADR-001 defers.
**Source:** Interview #9

## 🏗️ Technical Design

### Current State

```
picker (step_manifest.md.j2)
   └─ "if no .hm-autopilot marker is active" ── no command exists ──> model guesses
                                                                       (file exists → skip)
autopilot.py        marker{session_uuid(project-scoped), level, pipeline, created_at}
                    active_marker(): foreign|stale → None, file left on disk
                    CLI: on | off                                   ← no status
autopilot_caps.py   boundary --current X
                       ├─ active_marker None → kill_switch
                       ├─ count_events("advanced") → step cap
                       └─ proceed → append "advanced" ── BEFORE the model acts
stage prompt        "Stage terminal … STOP … must survive context compaction"   (line ~293)
                    …
                    auto-advance block → Skill(hm:<next>)             (no args, no override)
                    STOP banner
```

### Affected Components

| Component | Change |
|---|---|
| `src/harness_maker/autopilot.py` | `task_slug` + `task_slug_stage` + `claude_session_id` fields; session-aware `active_marker` (one-directional); `gc_stale_marker`; `set_task_slug`; `write()` ownership guard + `--force`; `status` CLI action |
| `src/harness_maker/autopilot_ledger.py` | `LedgerEvent` += `advance_authorized`, `advance_entered`; `find_unconfirmed_authorization()` |
| `src/harness_maker/autopilot_caps.py` | `boundary --slug`; retro-confirm in both subcommands; step count on `advance_entered`; `task_slug` in JSON |
| `src/harness_maker/command_registry.py` | `autopilot` subcommands += `status` |
| `src/harness_maker/readiness.py` | auto-advance signals read both event names |
| `templates/agents/_partials/step_manifest.md.j2` | picker calls `hm autopilot status` and branches on `active` **and** `reason` (`foreign` → do not arm) |
| `templates/agents/_partials/stage_end_summary.md.j2` | `--slug`; precedence sentence; `Skill(hm:<next> <task_slug>)`; announce a `persisted` slug |
| `templates/stages/*.md.j2` (7) | Stage-terminal STOP gains the auto-advance exception clause |
| `templates/hooks/hooks.json.j2` | drop 3 dead `autopilot_guard` invocations |
| `templates/settings/{Production,Side}.json.j2` | delete the stale `autopilot_guard` prose comments (validator S3) — comments only, no emitted command |

### Dependencies

No new libraries. `HM_SESSION_ID` is already exported by the `sessionid_envfile`
SessionStart hook (`readiness` already smoke-checks its registration).

### Architecture (target)

```
picker ── hm autopilot status ──> {"active": false, "reason": "stale (gc'd)"}
                                    └─ AskUserQuestion → hm autopilot on --level auto_safe
                                         marker{claude_session_id, task_slug: null, …}

stage N terminal
   ├─ gate pending?  ── hm autopilot_caps gate-blocked --stage N
   │                       └─ retro-confirm advance_entered(to=N, elapsed_s)   [ADR-005]
   └─ gate clear     ── hm autopilot_caps boundary --current N --slug <s>
                           ├─ retro-confirm advance_entered(to=N, elapsed_s)   [ADR-005]
                           ├─ persist task_slug into marker                    [ADR-003]
                           ├─ steps = count(advance_entered) since created_at  [ADR-004]
                           └─ proceed → append advance_authorized(to=N+1)
                                        → {"proceed": true, "next_stage": "N+1",
                                           "task_slug": "<s>"}
                                            └─ Skill(hm:N+1, "<s>")            [ADR-003]
```

### Data Flow — `advance_entered` matching (ADR-005)

Given ledger rows scoped to `ts >= marker.created_at`:
1. Collect `advance_authorized` rows in order.
2. Collect `advance_entered` rows in order.
3. An authorization `A(to=X, ts=t)` is *confirmed* iff some `advance_entered(to=X, ts>t)`
   exists that has not already been paired with an earlier authorization for `X`
   (greedy in-order pairing — a stage can be authorized and entered more than once in a
   session, e.g. a review→execute→review cycle).
4. On a call for stage `X`, take the earliest unconfirmed `A(to=X)`; if present, append
   `advance_entered(to=X, elapsed_s=now-A.ts)`.

Greedy in-order pairing is the whole matching rule; no ids are introduced. A repeated
stage therefore pairs oldest-authorization-to-oldest-entry, which is the intended reading.
Step 0 of the whole sequence is the marker resolution — with no live marker there is no
window, so nothing is collected and nothing is appended (ADR-005 placement rule).

### API Changes

```
hm autopilot status [--root PATH]
  → one JSON line; schema is stated ONCE in ADR-002 and not restated here
  exit 0 always (absence is data, not an error; GC failure is reported in `reason`)

hm autopilot on [--level L] [--pipeline P] [--force] [--root PATH]   # --force is new
  → refuses to overwrite a live foreign marker without --force (ADR-010); exit != 0
hm autopilot_caps boundary --current X [--slug S] [--step-cap N] [--time-cap-min M]
  → adds "task_slug" and "task_slug_source" to the existing JSON object
```

`.hm-autopilot` marker JSON gains three optional keys:
`{"session_uuid", "level", "pipeline", "created_at",
  "task_slug"?, "task_slug_stage"?, "claude_session_id"?}`.

### Design Decisions

- Marker schema keeps `extra="forbid"`; both new fields are `str | None = None` so an
  existing marker validates unchanged (ADR-003, CLAUDE.md absent-case rule).
- `elapsed_s` is computed from ISO timestamps produced by the same `isoformat()` source on
  both sides — the `[fail:design] producer-consumer-timestamp-resolution-mismatch`
  constraint carries forward.
- `gc_stale_marker` is a separate function, not folded into `active_marker`, so the
  predicate stays pure (`evaluate_boundary` depends on that purity).
- The rendered `.claude/hooks/hooks.json` stays rendered (its retirement is a separate
  phase per CLAUDE.md); only the dead `autopilot_guard` lines leave it. The
  `render._HARNESS_RETIRED_HOOK_INVOCATIONS` entries **stay** — they are what strips the
  guard from an existing user's `settings.json` on re-render.

## 📝 Implementation Plan

### Phase 1 — Marker schema + session scoping + GC + `status`
- `depends_on`: `[]`
- `parallel_group`: `serial-core`
- `merge_hazards`: `src/harness_maker/autopilot.py` (every later phase reads it);
  `.hm-autopilot` on-disk shape
- **Scope in:** `src/harness_maker/autopilot.py`, `src/harness_maker/command_registry.py`,
  `tests/unit/test_autopilot*.py`
- **Scope out:** templates, `autopilot_caps.py`, ledger
- **Work:** add `task_slug` / `task_slug_stage` / `claude_session_id` optional fields;
  `write()` stamps `HM_SESSION_ID` and gains the ADR-010 ownership guard + `--force`;
  `active_marker` one-directional session comparison (ADR-007) with project-uuid fallback
  only when neither side has an id; `gc_stale_marker` (TTL-only + re-read-before-unlink,
  ADR-008); `set_task_slug`; `status` action + registry entry. **The Typer alias
  `cli.autopilot` does NOT gain `status`** — `status` is dot-form/`hm`-form only; the alias
  stays a backward-compat `on`/`off` shim (validator W6).
- **Exit criterion:** `uv run pytest tests/unit tests/structural -k 'autopilot or registry
  or command_surface' -q` green — deliberately wider than `-k autopilot`, because
  `command_registry.py:144` declares `autopilot` as guarded with subcommands `{on, off}`,
  so `misroute_guard("autopilot", ["status", …])` fires **before** argparse and the CI
  parity test that would catch it contains no "autopilot" in its name (validator W6).
  Plus: `hm autopilot status --root <tmp>` returns `active: false` for (a) absent,
  (b) stale, (c) foreign-fresh, (d) future-dated — with the file deleted **only** in case
  (b) and present in (c) and (d); and `hm autopilot on` against a live foreign marker exits
  non-zero and leaves the file byte-identical.
- **Risk:** medium — ADR-008's asymmetry (reject ≠ delete) is the subtle part, and
  ADR-010's guard is what makes it hold.
- **Rollback:** revert to HEAD; nothing else depends on this yet.

### Phase 2 — Ledger split + entry matching
- `depends_on`: `[]`
- `parallel_group`: `parallel-a` (independent of Phase 1 — different module, no shared symbol)
- `merge_hazards`: `src/harness_maker/autopilot_ledger.py`; `auto-advance.jsonl` reader
  contract shared with `readiness.py`
- **Scope in:** `src/harness_maker/autopilot_ledger.py`, `src/harness_maker/readiness.py`,
  `tests/unit/test_autopilot_ledger*.py`
- **Scope out:** `autopilot_caps.py` call sites (Phase 3)
- **Work:** extend `LedgerEvent`; `find_unconfirmed_authorization(root, to, since)`
  implementing the greedy in-order pairing; teach `smoke` and the `readiness` signals both
  names **with ADR-004's window rule** (legacy `advanced` counts only outside the current
  marker window).
- **Exit criterion:** `uv run pytest tests/unit -k ledger -q` green, including (a) a fixture
  with two authorize→enter cycles for the same stage that pairs oldest-to-oldest, (b) a
  legacy `advanced` row **outside** the window counted as an entry, and (c) a **mixed
  window** fixture — legacy `advanced` and new `advance_authorized`/`advance_entered` rows
  both inside one marker window — asserting the legacy row is NOT counted (validator W9).
- **Risk:** low
- **Rollback:** revert; `Literal` extension is additive.

### Phase 3 — `autopilot_caps` wiring
- `depends_on`: `[1, 2]`
- `parallel_group`: `serial-core`
- `merge_hazards`: `src/harness_maker/autopilot_caps.py`; the boundary JSON contract that
  `stage_end_summary.md.j2` parses
- **Scope in:** `src/harness_maker/autopilot_caps.py`, `tests/unit/test_autopilot_caps*.py`
- **Work:** `--slug`; retro-confirm **immediately after the `active_marker` resolution and
  before the cap/gate logic** in both subcommands (ADR-005 placement — never before the
  marker check, which would regress the P2-5 phantom-row invariant at
  `autopilot_caps.py:158-163` and `:259-267`); persist slug + `task_slug_stage`; count
  `advance_entered`; write `advance_authorized`; add `task_slug` + `task_slug_source` to
  the JSON.
- **Exit criterion:** `uv run pytest tests/unit -k autopilot_caps -q` green, plus:
  (a) an e2e running `boundary --current research --slug s` → `boundary --current spec
  --slug s` asserting the ledger holds exactly `[advance_authorized(to=spec),
  advance_entered(to=spec, elapsed_s>0), advance_authorized(to=plan)]` and that the step cap
  fires on entries; (b) **`boundary --current spec` and `gate-blocked --stage spec` with NO
  live marker each append ZERO ledger lines** (validator CR1 — the P2-5 regression gate);
  (c) `boundary` with `--slug` omitted returns the persisted slug with
  `task_slug_source: "persisted"`.
- **Risk:** medium — this is where the P8 timestamp-resolution class of bug lives.
- **Rollback:** revert Phase 3 only; Phases 1–2 are inert without it.

### Phase 4 — Template changes
- `depends_on`: `[3]`
- `parallel_group`: `serial-templates`
- `merge_hazards`: all 7 `templates/stages/*.md.j2` + both `_partials`; every render
  snapshot baseline
- **Scope in:** `templates/agents/_partials/step_manifest.md.j2`,
  `templates/agents/_partials/stage_end_summary.md.j2`,
  `templates/stages/{research,spec,plan,execute,review,verify,wrapup}.md.j2`,
  `templates/hooks/hooks.json.j2`, `templates/settings/{Production,Side}.json.j2`
- **Work:** picker → `hm autopilot status` + the `reason == "foreign"` branch; terminal →
  `--slug`; precedence sentence; `Skill(hm:<next> <task_slug>)`; announce a `persisted`
  slug; reciprocal exception clause in 7 Stage-terminal paragraphs; delete the 3 dead
  `autopilot_guard` lines and the stale `autopilot_guard` comments in both settings
  templates.
- **Exit criterion:** `uv run pytest tests/unit/test_render* tests/structural -q` green
  after baseline re-freeze, and a render-grep test asserting (a) no rendered command
  contains `hooks.autopilot_guard`, (b) every stage's Stage-terminal paragraph contains the
  auto-advance exception clause, (c) the picker contains `autopilot status` and not a
  file-existence instruction, (d) the picker contains the `foreign` no-arm branch
  (validator CR2 — otherwise undetectable on disk), (e) the emitted `--slug` line contains
  no `$0`–`$9` positional parameter, enforced by the existing
  `tests/structural/test_no_positional_params_in_commands.py` extended to this line
  (validator W7 / CLAUDE.md §2).
- **Risk:** medium — snapshot churn is wide; a missed stage is a silent partial fix, which
  is why (b) is a gate, not a review item.
- **Rollback:** revert Phase 4; the CLI changes are backward compatible with old prompts
  (`--slug` optional, `task_slug` additive in the JSON).

> **Phase status (2026-07-31, /hm:execute):** Phase 1 **DONE** · Phase 2 **DONE** ·
> Phase 3 **DONE** · Phase 4 **DONE** · Phase 5 **BLOCKED** (see the blocker note below).
>
> **Two PLAN corrections found during execution.**
> 1. **ADR-006 says "all 7 stage bodies"; only 4 carry a conflicting terminal STOP** —
>    `research`, `spec`, `plan`, `verify`. `execute` and `review` have no terminal-STOP
>    paragraph at all, and `wrapup`'s STOPs are AC-gate stops inside a stage the chain is
>    structurally forbidden to auto-enter (`_HUMAN_GATED_STAGES`). The render gate asserts
>    the clause on those four and would fail loudly if a fifth ever grows one.
> 2. **The gate caught the fix's own prose.** The first draft of the slug guidance spelled
>    out the positional-parameter tokens literally; `test_no_positional_params_in_commands`
>    failed on it, correctly — the host substitutes those tokens even inside backticks, so
>    the sentence explaining the trap would itself have been mangled. Reworded to describe
>    the tokens rather than quote them.

### Phase 5 — Self-harness re-render + baseline re-freeze
- `depends_on`: `[4]`
- `parallel_group`: `serial-templates`
- `merge_hazards`: `.claude/**` in this repo; `tests/` surface baseline
- **Scope in:** re-render this repo's own harness, re-freeze the surface baseline,
  full-suite run.
- **Exit criterion:** `uv run pytest -q` green (background per project policy), and a live
  `hm autopilot status --root .` on this repo reports `active: false` with the 2026-07-29
  marker **deleted**.
- **Risk:** low
- **Rollback:** revert the render commit.

> **🚧 BLOCKER — the surface-baseline re-freeze cannot happen inside this stage.**
>
> `tests/structural/test_command_size_budget.py::test_aggregate_shipped_surface_does_not_grow`
> and `tests/structural/test_surface_baseline.py::test_the_standalone_generator_agrees_with_the_baseline_in_shape_and_direction`
> are red, with:
>
> ```
> AssertionError: claude: shipped surface grew 6585 chars over the Phase 0 baseline
> (839338 → 845923). A per-command ceiling cannot see this.
> ```
>
> This is the aggregate ratchet doing its job: the picker and the auto-advance partial are
> included by every rendered command, so a per-command-legal addition multiplies across the
> surface. The per-command ceilings were re-baselined with a compaction-first
> justification (see `_ATOMIC_RATCHET`); this total needs the same treatment.
>
> **Why it cannot be done here:** `_surface_baseline.assert_sha_is_durable` refuses to
> freeze against a commit that is not an ancestor of `main`, because `task-land`
> squash-lands `hm/<slug>` and deletes the branch — a baseline frozen on this branch would
> record a SHA that is reachable locally and unreachable in CI. `/hm:execute` also owns no
> commits. So the freeze point does not exist yet, by design.
>
> **Resolution (post-land, one command):** after `/hm:wrapup` squash-lands this task,
> re-freeze from the landed checkout and commit it separately — the repo already has
> precedent (`dfb3caeb chore(tests): re-freeze the surface baseline from the landed
> checkout`):
>
> ```
> uv run python -m tests.structural._surface_baseline
> ```
>
> Nothing else in the suite depends on it, and the two red arms are measurement ratchets
> rather than behavioral assertions.

## 🧪 Testing Strategy

**Unit**
- `active_marker`: matrix of {both ids / marker-only / env-only / neither} × {fresh /
  stale / future-dated}. Only the "neither" column may fall back to project-uuid — the
  three id-bearing columns must compare ids (ADR-007 one-directional rule).
- `gc_stale_marker`: deletes TTL-stale, deletes unparseable, **preserves foreign-fresh**
  (ADR-008 — the single most important assertion in this PLAN), **preserves future-dated**,
  and preserves a file whose bytes changed between judgement and unlink.
- `write()` ownership guard: refuses a live foreign marker, succeeds with `--force`,
  succeeds against an absent / stale / own marker (ADR-010).
- `status` with an unwritable marker directory: still prints valid JSON, exit 0,
  `reason` names the GC failure.
- Marker round-trip with and without the three new optional keys (old marker still loads).
- Ledger pairing: repeated same-stage cycles, legacy row outside the window, **mixed
  window** (legacy + new inside one window → legacy not counted), no-authorization case.
- `boundary`: `task_slug` echo, `task_slug_source` values, persistence when `--slug` omitted
  on a later call, step cap counting entries not authorizations, **zero rows appended when
  no marker is live** (CR1 regression gate).

**Integration**
- e2e chain over a tmp project: arm → `boundary research` → `boundary spec` → assert exact
  ledger sequence and `elapsed_s > 0`. Both sides must use **production defaults** for
  timestamps — the `[fail:design] producer-consumer-timestamp-resolution-mismatch` lesson
  requires the e2e, not a same-fixture unit.
- `gate-blocked` also confirms a pending entry.

**Render / structural**
- Grep gates listed in Phase 4's exit criterion, run over the rendered surface **and** the
  plugin's own `commands/` (CLAUDE.md §2: a gate scoped only to what it fixed lets the same
  defect survive elsewhere).

**Manual (Success Criteria, NOT a phase gate — Interview #11)**
- In a fresh session on this repo: confirm the picker now offers (it currently does not),
  accept, run `/hm:research` → observe an actual `Skill(hm:spec …)` invocation, then
  inspect `auto-advance.jsonl` for exactly one `advance_authorized(to=spec)` and one
  matching `advance_entered(to=spec, elapsed_s>0)`.
- **Accepted risk (R2, restated):** no phase exit criterion observes the reported symptom.
  ADR-006's fix is prose and no automated gate can see its effect, so all five phases can
  go green with autopilot still stalling. The user chose to keep this as a success
  criterion rather than a blocking gate; the ledger split is what will surface it.

## ⚠️ Risks & Mitigation

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R1 | GC deletes a concurrent session's live marker | low | high — silently disarms a peer | ADR-008 restricts GC to `age > TTL` (never negative age) + re-read before unlink; dedicated unit tests are gates |
| R1b | **Arming** overwrites a concurrent session's live marker | medium (was unguarded) | high — peer's chain dies at its next boundary as `kill_switch` | ADR-010: `write()` ownership guard + picker `foreign` branch + Phase 4 render-grep gate. Convergent finding (validator CR2 + antigravity ag1) |
| R2 | Prose fixes are insufficient; autopilot still stalls | **medium** | medium | Explicitly accepted by ADR-001. The ledger split makes it visible within days; follow-up PLAN decides the hook |
| R3 | Two concurrent sessions cannot both arm (ADR-007 consequence) | medium | low | Documented; `status` reports `foreign` explicitly rather than silently. Per-session marker filename is the eventual fix, out of scope |
| R4 | Snapshot re-freeze masks an unintended template change | medium | medium | Phase 4 adds positive render-grep assertions, so re-freeze alone cannot green a missing clause |
| R5 | `elapsed_s` computed across mismatched timestamp resolutions | low | medium | Single `isoformat()` source on both sides; e2e uses production defaults |
| R6 | `HM_SESSION_ID` unavailable (Cursor/Codex/hook failure) reverts to today's leak | **high** in those IDEs | low | Explicit degraded fallback, surfaced in `status.reason`; matches the documented `loop_marker` precedent |
| R7 | Marker written by new code, read by an older harness-maker → validation error | low | low | Marker is 18h-TTL operational state, gitignored; worst case is one lost arm |
| R8 | Retro-confirm check-then-append race double-confirms one authorization (codex cx4) | low | low — one spurious row, cap fires one step early | Accepted under R3: reaching it needs concurrent same-project sessions, which ADR-008/010 already declare unsupported this round. `_append_atomic_line` is per-line atomic; the pairing is not |
| R9 | `set_task_slug` read-modify-write clobbers a marker replaced mid-operation (codex cx8) | very low | low | Accepted under R3. `boundary`'s `active_marker` early return means a foreign marker is never slug-written, leaving only a sub-ms window that additionally requires a concurrent arm — which ADR-010 now blocks |
| R10 | A persisted slug is announced but the user does not read it, and the wrong task advances (validator CR3 residue) | low | medium | ADR-003's three constraints (attributable / loud / not-across-pipelines) reduce but do not eliminate it. Fully closing it needs `--slug` to be mandatory, which Interview #10 rejected as a worse failure mode |

## ✅ Success Criteria

- [x] `hm autopilot status` exists and the picker branches on its `active` **and** `reason`
      fields; `reason: "foreign"` does not arm.
- [x] `autopilot on` refuses to overwrite a live foreign marker without `--force`.
- [x] A TTL-stale marker is deleted on `status`; a foreign-but-fresh and a future-dated
      marker are not.
- [x] `status` prints valid JSON and exits 0 even when the unlink fails.
- [x] Arming records `claude_session_id`; a second session in the same project does not
      inherit it while `HM_SESSION_ID` is available, and an id-bearing session does not
      inherit a fieldless legacy marker.
- [x] `boundary` returns `task_slug` + `task_slug_source` and the auto-advance prompt passes
      the slug to `Skill`, announcing it when the source is `persisted`.
- [x] `boundary` / `gate-blocked` append zero ledger rows when no marker is live.
- [x] `auto-advance.jsonl` contains `advance_authorized` and `advance_entered` rows, the
      latter carrying `elapsed_s`; the step cap counts entries, and a legacy `advanced` row
      inside the current window is not counted.
- [x] **Behavioral (manual, non-gating — Interview #11):** in a fresh session the picker
      offers, and accepting it produces one real `Skill(hm:<next>)` invocation with a
      matching `advance_authorized` / `advance_entered` pair in the ledger.
- [x] All 7 stage bodies' Stage-terminal paragraphs carry the auto-advance exception, and
      the auto-advance partial carries the reciprocal precedence sentence — both enforced
      by a render-grep gate.
- [x] No rendered artifact references `hooks.autopilot_guard`; the retirement entries in
      `render._HARNESS_RETIRED_HOOK_INVOCATIONS` remain.
- [x] Full suite green; this repo's own harness re-rendered.

## 🔍 Plan Validation

**Outcome:** `MAJOR_REVISION` → **MAJOR_REVISION_RESOLVED**. `plan-validator` returned 3
critical, 7 warning, 4 suggestion. All 14 are resolved in this revision — 2 via Interview
round 4 (#10, #11), 12 by direct amendment.

**Cross-model second opinion (Production preset — every enabled model, every plan):**

| Model | Status | Outcome |
|---|---|---|
| `codex` | `invoked` | 8 findings, all `accepted` by the validator (3 reframed, 2 narrowed in severity) |
| `antigravity` | **`failed`** | ⚠️ payload unreadable via stdout (`ValueError`) — the fail-closed adapter returned zero structured findings. The truncated CLI text nonetheless named one concrete gap (ag1), which was relayed as unverified model output and then **independently confirmed against `autopilot.py:151-165`**. Escalated to critical → ADR-010. The verdict does not depend on it |

`antigravity` has no CLI-level schema enforcement, so a non-conforming payload lands as
`failed` by design (warn-and-proceed). This is the H4 silent-degradation surface — worth a
`/hm:health` check, since two consecutive `failed` results would mean the antigravity voter
is effectively absent.

**Critical findings and resolutions:**

| # | Finding | Resolution |
|---|---|---|
| CR1 | Phase 3 placed retro-confirm before the marker check → regresses the P2-5 phantom-row invariant, polluting the metric ADR-001 depends on | ADR-005 gains an explicit placement rule; Phase 3 exit adds a zero-rows-without-marker assertion |
| CR2 | ADR-002 and ADR-008 specified contradictory picker behavior; `write()` has no ownership guard, so arming clobbers a live peer | **ADR-010** (new): `write()` guard + `--force`, picker branches on `reason`, Phase 4 render-grep gate. R1b added |
| CR3 | Persisted slug fallback reproduces the harm ADR-003 cites when rejecting slug inference | Interview #10: persistence kept, fallback made attributable (`task_slug_source`) + loud + non-reusable across pipelines. R10 records the residue |

**Warnings resolved:** W4 (GC negative-age → preserve), W5 (`status` GC failure suppressed,
exit 0 held), W6 (Phase 1 exit widened to registry/structural parity; Typer alias decision
stated), W7 (slug source mechanism named; positional-param gate extended), W8 (ADR-007 made
one-directional to match the cited `loop_marker` precedent), W9 (ADR-004 legacy-row window
rule + mixed-window fixture), W10 (manual e2e promoted to Success Criteria only — Interview
#11, with R2 restated as the accepted cost).

**Suggestions resolved:** S1 (`on --slug` dropped — no caller), S2 (`status` schema stated
once in ADR-002), S3 (stale `autopilot_guard` comments in both settings templates added to
Phase 4 scope), S4 (both races recorded as R8/R9 under R3).

**Not re-run:** the validator's re-run budget is one pass; every critical was resolved by
amendment or by an interview round rather than by accepting risk, so a second pass would
re-read a document whose contradictions are now removed. The residual risks are recorded
explicitly (R2, R3, R8, R9, R10) rather than silently absorbed.
