---
type: plan
task_slug: multisession-marker-scoping
status: complete
created: 2026-08-07
tags: [harness-maker, plan, python, multi-session, hooks, worktree, autopilot]
interview_rounds: 3
adrs: 12
adrs_withdrawn: 1
validator_outcome: MAJOR_REVISION_RESOLVED
validator_passes: 3
second_opinion_passes: 2
summary: "Per-session markers as the single session-identity store, and a gate that protects peers instead of blocking them"
---

# PLAN — multi-session marker scoping

## 🎯 Executive Summary

**TL;DR.** Two Claude sessions in one project is the normal case, and harness-maker is hostile to
it in two opposite ways. Autopilot cannot be armed twice because its marker is a single file. The
write gate blocks peers it should ignore while enforcing nothing for the worktree model actually
in use. Both are marker-scoping defects; the fix is to make **per-session marker files the one
session-identity store** and to point the gate at them.

**What.**
1. `.claude/.hm-autopilot` becomes one file **per session**.
2. `task-create` / `task-preflight` write a per-session **task marker** under a new
   `.hm-task-*` prefix, so the per-task worktree model has a session-attributable record at all.
3. `worktree_gate` resolves the base root correctly, scopes by the caller's session, and enforces
   a new invariant: **do not write into another session's worktree**.

**Why.** Measured live this session:
- `task_create` / `task_preflight` never write a `.hm-loop-*` marker (AST scan), and
  `worktree_gate` reads nothing else — so the per-task model, the default under
  `worktree.enabled: true`, has **zero** write enforcement. Isolation there is prompt-level only.
- A leftover marker from a **dead** session blocked an unrelated peer's every `Write`, `/tmp`
  included. The gate fired for the model not in use and stayed silent for the one that was.
- `autopilot.write` raises `MarkerOwnedByAnotherSessionError` whenever a second session arms, and
  the picker escalates it to the user. With two sessions the answer is always "yes, another
  session is open", so the prompt is noise on the normal path.

**What changed after review.** The first draft of this PLAN was returned `MAJOR_REVISION`: two
second-opinion models raised 19 findings (18 accepted) and `plan-validator` added 5 more. Three
of its ADRs were wrong, not merely incomplete — see **Prior Work → Review corrections**.

## 📚 Prior Work

### Memory entries that govern this work

- **`[fail:design] new-marker-content-field-must-update-every-reader` (count:2).** The second
  instance *was this exact marker*. `autopilot._is_own` is one-directional — foreign whenever
  either side has an id and they differ — so wiring the writer while any reader stays id-less
  does not degrade autopilot, it **turns it off**. Five readers were missed on that cut. Its
  prevention rule (grep the ownership *predicate's* call sites, not the field name; audit both
  the `__main__` and Typer entry points) is what produced the corrected enumeration below, and
  drives ADR-009.
- **`[fail:design] env-var-set-but-not-exported-so-python-never-sees-it` (count:1).**
  `HM_SESSION_ID` is a shell variable; `os.environ.get` is `None` in every subprocess. Python
  takes the id as an argument; a hook takes it from its payload (ADR-005).
- **`[fail:design] runtime-env-gate-dead-on-arrival` (count:2).** A runtime input must be probed
  **in the target execution context**. ADR-005 therefore carries a probe transcript, and ADR-012
  makes the manual two-session check an exit criterion rather than advice.

### Review corrections — what the first draft got wrong

Recorded because the errors are instructive, not to pad the document.

| Draft claim | Reality | Found by |
|---|---|---|
| Gate rule = "inside repo, outside my union → block" | A session with **no** worktree has an empty union, so the rule either blocks every repo write or, bypassed, lets base sessions write into peers' worktrees. The wanted invariant is peer-protection, not self-confinement. | antigravity, validator |
| ADR-006 (fail-open) and ADR-007 (degraded marker constrains id-less callers) coexist | Logically incompatible: fail-open returns before any marker is read, so ADR-007's only population is unreachable. | codex |
| Registry + `claude_session_id` is a sound gate input | `pid=os.getpid()` (`worktree.py:4391`) is the **exited** CLI subprocess, and liveness is "pid alive AND worktree on disk" (`:4104`). The registry cannot be a live-session authority. | codex (confirmed in-session) |
| `marker_path` is the only path consumer | `_is_marker_root` (`autopilot.py:158`) uses the marker as a root sentinel; `gates/permission_gate.py:109` calls `resolve_marker_root`; `worktree.py:113` carries the literal in `_HARNESS_CHURN_FILES`, matched **exactly**, which also seeds gitignore. | codex, validator |
| `autopilot_caps.py` has 2 call sites | **11 across 11 lines** (68/195/227/238/252/312/318/330/394/395/398). | antigravity, validator |
| The consumer list was complete after the pass-1 correction | A **sixth** module was still missing: `hooks/autopilot_autoarm.py` (`:25`, `:75`, `:82-92`) — the SessionStart auto-arm path that actually raises the symptom this PLAN opens with. Third instance of the count:2 class, inside the PLAN that cites it. | validator, pass 3 |
| A predicate-keyed structural test is an adequate guard | It was another hand-written list, and it omitted `write` — the only API the missed module calls. Replaced with an import-graph-derived test. | validator, pass 3 |
| Old readers tolerate the new registry field, so rollback is safe | Only on the read side. `_write_sessions` (`:4010`) is a **whitelist serializer**, so one mutation by an old binary strips the field from every row at once, silently. | validator |
| A structural test on `marker_path` callers proves ownership | There are **zero** `marker_path(` call sites in `autopilot_caps.py` / `cli.py` — they call `active_marker`/`clear`/`touch`. The proposed test cannot see the sites that were missed. | validator |
| Glob GC is a low-blast-radius default | It makes every session an unlink authority over every peer's marker, re-introducing the cross-session deletion ADR-001 exists to remove. | validator |

Related shipped work: PLAN-loop-marker-session-scoping (the per-session filename pattern),
PLAN-layer3-per-session-ownership (per-session ownership without losing a safety property),
PLAN-worktree-base-artifact-pollution (the churn/gitignore contract ADR-011 must honour).

## 🎙️ Interview Transcript

| # | Topic | Category | Question | Choice | Note | → ADR |
|---|-------|----------|----------|--------|------|-------|
| 1 | Gate blast radius | Scope | How far should the gate block? | **repo-only** | `wrapup.md.j2:408` writes a wiki body to a `mktemp -t` path; blocking `/tmp` breaks our own procedure | ADR-004 |
| 2 | Degraded sessions | Failure handling | Autopilot marker with no session id | **shared fallback file** | pid key rejected: reuse would let a new session claim a dead peer's marker | ADR-002 |
| 3 | Legacy registry rows | Contract | Rows without `claude_session_id` | **ignore + heal** | superseded by #10 — the registry left the enforcement path entirely | ADR-008 |
| 4 | Legacy autopilot marker | Contract | Existing single `.hm-autopilot` | **one-shot takeover** | armed state survives upgrade; no permanent dual-format reader | ADR-003 |
| 5 | Gate without an id | Failure handling | Payload lacks `session_id` | **fail-open** | a false block halts work immediately; isolation here was prompt-level to begin with | ADR-006 |
| 6 | Degraded markers | Risk | Whom does an empty-header marker constrain? | **mirror `loop_gate`** | withdrawn in round 3 — see #9 | — |
| 7 | Shipping unit | Phasing | One release or autopilot first? | **all three** | user chose one release over my recommendation to ship autopilot relief early | ADR-009 |
| 8 | Gate invariant | Architecture | Confine me, or protect peers? | **protect peers** | accepts that a drifting agent is no longer confined — the gate's original aim is partly traded away, knowingly | ADR-004 |
| 9 | ADR-006 vs ADR-007 | Contract | Which fires first? | **drop ADR-007** | fail-open is absolute; degraded markers constrain nobody | ADR-006 |
| 10 | Gate authority source | Architecture | What feeds the gate, given the registry cannot? | **`task-create` writes a marker** | removes the registry schema change from the enforcement path entirely | ADR-008, ADR-010 |
| 11 | Marker GC scope | Risk | May a session unlink a peer's marker? | **self-only** | dead sessions' markers persist to TTL; accepted to keep ADR-001's isolation intact | ADR-013 |

Assumptions taken without a round (low blast radius): the per-session filename key is the
sanitized `claude_session_id` via `loop_marker.sanitize_session_id` (no second sanitizer); the
gate reads markers without a lock, since marker writes are atomic and any read failure fails open
under ADR-006.

## 📐 Architecture Decision Records

### ADR-001: Autopilot markers are per-session files
**Status:** Accepted (2026-08-07)
**Context:** `_MARKER_REL = ".claude/.hm-autopilot"` is a single path, so two sessions cannot both
be armed and the second is escalated to the user as a question they cannot usefully answer.
**Decision:** Key the marker **filename** by the sanitized `claude_session_id`, reusing the
`.hm-loop-<key>` pattern. Every consumer moves with it (ADR-009 enumerates them).
**Consequences:**
- ✅ Collisions become impossible, so the ownership question disappears rather than being muted.
- ✅ `--force` narrows to its real purpose: reclaiming a genuinely stale marker.
- ⚠️ N files instead of 1 → GC scope must be decided explicitly (ADR-013) and the churn/gitignore
  contract must move from an exact literal to a glob (ADR-011).
**Rejected alternatives:**
- Suppress the message and auto-`--force` — Rejected: `autopilot.py:663-667` records that a prior
  round tried exactly this and it clobbered live peers.
- Key by `session_uuid` — Rejected: `autopilot.py:34-38` documents it as PROJECT-scoped.
**Source:** Interview premise, rounds 1-3.

### ADR-002: Sessions without an id share one explicitly-named fallback marker
**Status:** Accepted (2026-08-07)
**Context:** Cursor, Codex, and a failed SessionStart hook leave no `claude_session_id`.
**Decision:** All id-less callers share `.claude/.hm-autopilot-degraded` — a name **distinct from
the legacy `.claude/.hm-autopilot`**, which ADR-003 requires to be self-erasing.
**Consequences:**
- ✅ No regression for degraded environments; id-bearing sessions are fully isolated.
- ✅ The compat branch can delete the legacy path without ever deleting a live degraded marker.
- ⚠️ Two id-less sessions still contend — structurally unavoidable without a per-session key.
**Rejected alternatives:**
- Reuse the bare legacy name as the fallback — Rejected: ADR-003's unlink would delete a live
  degraded session's marker on every read (codex 5226a4c2 named this exact collision).
- pid as key — Rejected: reuse produces false ownership.
**Source:** Interview #2, filename fixed in round 3.

### ADR-003: The legacy marker is taken over once, then deleted — with a compare-and-swap
**Status:** Accepted (2026-08-07)
**Context:** Existing projects hold a live `.claude/.hm-autopilot` in the old shape, and an
upgrade is exactly when two sessions are most likely to race on it.
**Decision:** If no per-session marker exists and the legacy file does, evaluate ownership under
today's rules; if ours, rewrite as a per-session marker and unlink the legacy path **only if its
bytes are unchanged since the read** (the `_write_if_unchanged` compare-and-swap already in this
module). Otherwise leave it.
**Consequences:**
- ✅ Armed state survives the upgrade; the compat branch is self-erasing.
- ⚠️ `gc_stale_marker`'s docstring records that a re-read-before-unlink "narrows, and does not
  close" this window. CAS narrows it further but does not close it either; the residual loss is
  one marker, recoverable by re-arming.
**Rejected alternatives:**
- Read → rewrite → unconditional unlink (the first draft) — Rejected: deletes a marker that
  changed between evaluation and deletion.
- Hard cut / indefinite compat — Rejected: one drops autopilot on upgrade, the other keeps two
  formats forever.
**Source:** Interview #4, hardened by codex 1a6dede2.

### ADR-004: The gate protects peers' worktrees; it does not confine the caller
**Status:** Accepted (2026-08-07) — supersedes the first draft's union rule
**Context:** The draft rule ("inside repo, outside my union → block") has no empty-union case. A
session with no worktree has an empty union, so the rule either blocks every repo write or, if
bypassed, lets base sessions write freely into peers' worktrees.
**Decision:** Block a write iff the target is inside **another live session's** worktree.
Everything else is allowed, including the base repo and everything outside the repo.
**The partition is THREE-way, not two.** Every marker falls in exactly one bucket:
| Bucket | Test | Effect |
|---|---|---|
| **mine** | content header == my `session_id` | never blocks me |
| **peer** | content header is a **non-empty** id != mine | blocks me |
| **unattributable** | content header **empty** | **ignored entirely** |

The third bucket is load-bearing and was missing from the previous revision. `worktree.create`
writes a loop marker for every caller, but only `loop.md.j2` passes `--claude-session-id`, so a
standalone `/hm:execute` worktree's marker has an **empty header**. Under a two-way partition
"not mine" means peer, and every standalone execute session would be blocked from **its own**
worktree — a total work stoppage. Ignoring the bucket is the deliberate trade: standalone execute
worktrees get no peer protection, consistent with ADR-006's rule that unattributable state is
never enforced.

**Precedence — own membership wins.** A path may appear in both my markers and a peer's (a
restarted session before its stale marker is taken over; an intentional `--allow-shared-slug`
attachment). The rule is evaluated as *peer-only*: block iff the path is in some peer's set **and
not in mine**. Without this, a session is blocked from its own worktree, which is the loudest
possible false positive and the one a restart makes routine.
**Consequences:**
- ✅ Well-defined for a session with no worktree: nothing to protect against it but peers.
- ✅ `wrapup.md.j2:408`'s `mktemp -t` write keeps working; `/tmp` is never blocked.
- ✅ Cross-session contamination — the property with a three-incident history — is what gets
  enforced.
- ⚠️ **A drifting agent is no longer confined to its own worktree.** The gate's original stated
  purpose ("the technical enforcement layer" for `<WT>` substitution) is partly traded away. The
  user chose this knowingly in round 3; self-confinement is recoverable later as an opt-in.
- ⚠️ Multi-repo loops: a marker may list worktrees in secondary repos (`_read_active_worktrees`
  docstring). Under peer-protection this is no longer a hole — a peer's secondary-repo worktree
  is still a peer worktree and is still protected, regardless of which repo it lives in.
**Rejected alternatives:**
- Self-confinement — Rejected: undefined for base sessions, and it is what broke the draft.
- Dual rule (confine those who have a worktree, protect peers otherwise) — Rejected: doubles the
  branches and makes "my worktree" depend on the identity source that ADR-008 just removed.
**Source:** Interview #8, after antigravity bbe69ead + validator.

### ADR-005: The gate scopes by the PreToolUse payload's `session_id`, after resolving the base root
**Status:** Accepted (2026-08-07)
**Context:** Session-scoping needs the caller's identity inside a hook, and Python cannot read
`HM_SESSION_ID` (shell-scoped, never exported).
**Decision:** Read `session_id` from the PreToolUse payload. **Resolve the base root before
reading any marker**: `_project_root` currently returns the payload `cwd`, so a hook invoked from
`.worktrees/<slug>` treats that worktree as the project root and never finds the base `.claude/`.
Strip `/.worktrees/<name>/` the way `autopilot.resolve_marker_root` already does.
**Evidence — live probe, not code reading.** A temporary dump was inserted into
`worktree_gate.main()`, a real `Write` issued, and the payload captured in this session:
```
keys: [cwd, effort, hook_event_name, permission_mode, prompt_id,
       session_id, tool_input, tool_name, tool_use_id, transcript_path]
session_id == HM_SESSION_ID  (exact match);  `workspace` was NOT present
```
The probe was reverted (clean diff against HEAD). Required by
`runtime-env-gate-dead-on-arrival`, whose lesson is that a reviewer-approved code-reading
argument about a runtime input has been wrong twice.
**Consequences:**
- ✅ Same identity the markers carry; no new identity space.
- ✅ The absent `workspace` key is now a measured fact, so the resolution order is not guesswork.
- ⚠️ An upstream payload change degrades the gate silently. Phase 3 ships a fixture captured from
  this probe.
- ⚠️ **Second silent-degradation path, accepted as risk.** `resolve_marker_root` strips
  `.worktrees` only when the candidate base passes the strict `_is_harness_root`
  (`.claude/harness.yaml` is a file, `autopilot.py:145-155`). On failure it falls through to a
  parent walk whose predicate accepts a bare `.git` — and a git worktree carries a `.git` file —
  so a base **without** `harness.yaml` resolves the root to the worktree itself and the gate
  enforces nothing, silently. Low impact for a rendered harness (`harness.yaml` is always
  present), recorded so a later reader does not rediscover it as a bug.
**Rejected alternatives:**
- `os.environ["HM_SESSION_ID"]` — Rejected: proven `None` in subprocesses.
- Trusting `cwd` as the project root (the draft) — Rejected: codex 5c73c503, same class as the
  `--output-schema` cwd bug this repo already shipped.
**Source:** Pre-exit verification, round 2; base-root half added in round 3.

### ADR-006: The gate fails open when it cannot identify the caller — absolutely
**Status:** Accepted (2026-08-07)
**Context:** Cursor, Codex, or any payload without `session_id`.
**Decision:** Allow the write. This rule fires **before** any marker is read, and no other rule
overrides it.
**Consequences:**
- ✅ No false block — the symptom that started this PLAN.
- ✅ Removes the ADR-006/ADR-007 contradiction by making precedence explicit rather than implied.
- ⚠️ No enforcement in id-less environments, and an id-bearing session will not be constrained by
  an unattributable marker. Accepted: enforcement there is prompt-level today, so this is a floor
  that did not exist rather than a wall removed.
**Rejected alternatives:**
- Fail closed — Rejected: blocks every Write in a Cursor/Codex session while any marker is live.
- Consult degraded markers before falling open (the retained ADR-007) — Rejected in round 3:
  keeps two id-less sessions blocking each other for a protection the user did not want.
**Source:** Interview #5, precedence settled by #9 after codex 3e33eeef.

### ADR-007: *(withdrawn)* Degraded markers constrain nobody
**Status:** Withdrawn (2026-08-07, round 3). Its rule was unreachable under ADR-006 and is not
re-introduced. Number retained so cross-references to the review record stay resolvable.

### ADR-008: Task worktrees get their own per-session marker; the registry stays out of enforcement
**Status:** Accepted (2026-08-07) — supersedes the first draft's registry-field decision
**Context:** The gate needs a session-attributable list of live worktrees. The registry cannot
supply it: `pid=os.getpid()` (`worktree.py:4391`) is the exited CLI subprocess and liveness is
"pid alive AND worktree on disk" (`:4104`), so rows are structurally non-live almost immediately.
**Decision:** `task-create` / `task-preflight` write a per-session **task marker**. The gate reads
markers only. **No `claude_session_id` field is added to `SessionRow`** — the registry keeps its
existing role (claim coordination, drift warnings) and leaves the enforcement path.

**Identity plumbing (required, not incidental).** `task_create()` today accepts only
`session_uuid`, and `_cli_task_create()` mints a random UUID with no `--claude-session-id` flag —
only `task-preflight` receives that identity. Phase 2 therefore **adds `--claude-session-id` to
`task-create` and threads it through `task_create()` and every direct Python caller**. Without
this the marker cannot be named and `task-create` still produces a registry-backed worktree with
no enforceable marker — precisely the gap this ADR claims to close. **Id-less behavior:** write no
task marker at all (not a shared fallback). An unattributable task marker could only ever produce
false peer-blocks, and ADR-006 already makes id-less callers unenforced.

**Argv parsing is part of this plumbing, not a detail.** `_cli_task_create` derives positionals as
`rest = [a for a in args if not a.startswith("--")]` (`worktree.py:5028`) and then takes
`base = Path(rest[1])` (`:5033`). Adding the flag naively leaves its **value** in `rest`, so
`task-create <slug> --claude-session-id abc123` silently resolves the base repo to `./abc123` —
no error, with the marker, registry, and gitignore all following the wrong base. Use the existing
`_flag_value` / `_positionals(args, valued_flags=(...))` helpers (`:5400-5406`, already used by
`task-preflight`). This is the same argv-substitution class this repo has shipped twice.

**Lifecycle — the complete transition set.** Marker removal happens **only jointly with removal of
the worktree the filename names** (ADR-013's task-family rule), so a failed removal leaves a marker
whose path no longer resolves and which the gate already ignores:
| Transition | Marker action |
|---|---|
| `task-create` / `task-preflight` with an id | write / refresh own marker |
| `task-create` / `task-preflight` without an id | no marker |
| `task-land` success | unlink that worktree's marker file after the worktree is removed |
| `task-land` already-landed (idempotent) | unlink if present; no error |
| `cleanup_all` | unlink the marker file of each worktree it actually removed — a whole-file unlink, never a partial rewrite of someone else's file (possible only because ADR-010 keys the filename by worktree, not by session) |
| create rollback / partial land failure | leave the marker; the worktree still exists |
| SIGKILL / manual `git worktree remove` | marker orphaned → recovered by ADR-013 |

Every row is a **whole-file** create or unlink of the marker belonging to **one worktree**. That
property is what makes the table implementable at all, and it comes directly from ADR-010's key
choice — under a session-keyed filename, `task-land` on one of two live tasks and `cleanup_all`
would both have to line-edit a shared (and possibly a peer's) file.
**Consequences:**
- ✅ One identity store instead of two, and it is the one already proven for this purpose.
- ✅ Removes the whitelist-serializer hazard entirely: an old binary rewriting the registry can no
  longer strip the field the gate depends on, because there is no such field.
- ✅ Removes the "legacy row is bricked, not unguarded" failure the draft introduced.
- ⚠️ A worktree created before the upgrade has no task marker until its next preflight, so its
  peers are unprotected against writes into it. Bounded and fail-open — the pre-upgrade state, not
  a regression.
- ⚠️ The `/hm:health` diagnostic value of a session id in the registry is lost. Recoverable later
  as a pure diagnostic if wanted; deliberately not on the enforcement path.
**Rejected alternatives:**
- Registry + `claude_session_id`, trusting id and ignoring pid — Rejected: `reclaim_stale` still
  deletes rows by pid, so the gate's input stays unstable.
- Fix pid liveness first — Rejected: correct but far larger than this PLAN.
**Source:** Interview #10, after codex c943996f.

### ADR-010: Task markers use a distinct `.hm-task-*` prefix, never `.hm-loop-*`
**Status:** Accepted (2026-08-07)
**Context:** ADR-008 introduces a new marker. Reusing the `.hm-loop-` prefix would be the obvious
implementation and is a trap: `loop_gate` (Stop hook) blocks a session from stopping when a
`.hm-loop-*` marker content-matches its `session_id`. A task marker under that prefix would make
**every `/hm:plan` or `/hm:execute` session unable to stop**. `_owned_session_uuids`,
`_count_pending_stashes` (queue-guard), and `_session_worktrees` would also ingest task worktrees
as loop worktrees.
**Decision:** Task markers use `.claude/.hm-task-<worktree-name>` — **keyed by worktree, with the
`claude_session_id:` in the CONTENT header**, exactly mirroring `.hm-loop-{wt_name}`
(`worktree.py:2690`). `worktree_gate` reads both families; nothing else reads `.hm-task-*`.

**Content, byte-for-byte** — identical in shape to a loop marker so `loop_marker.parse_marker_paths`
is the single parser (the `new-marker-content-field-must-update-every-reader` rule):
```
claude_session_id: <sanitized id>
/abs/path/to/.worktrees/<worktree-name>
```
The path line is **required, not decorative**: ADR-004's peer test needs the path, and
`_is_orphan_marker` (`worktree.py:1940-1947`) begins with `bool(refs) and not any(p.exists() …)`,
so a header-only marker is **never** classified as an orphan and Phase 2's `prune_stale` exit
criterion would be unsatisfiable. **Orphan predicate:** `prune_stale` uses a task-specific check —
path line present and its directory gone — and does **not** reuse `_is_orphan_marker`, whose second
clause consults `_marker_has_pending_stash`, a loop/finalize-stash concept with no task-worktree
meaning.

**Why not key the filename by session** (the previous revision's choice): a session routinely holds
two task worktrees — plan on one slug while execute runs on another — and a session-keyed filename
maps both to one file. "Refresh own marker" then either overwrites (silently dropping the other
worktree's protection) or appends, at which point `task-land` on one task must line-edit a shared
file, and `cleanup_all` must partially rewrite a **peer's** file — strictly more dangerous than
the cross-session unlink ADR-013 forbids. Keying by worktree makes every lifecycle transition a
whole-file create or unlink.
**Consequences:**
- ✅ The Stop hook, queue-guard, and Layer-3 ownership are untouched by construction.
- ✅ `.hm-loop-*` keeps its meaning: an autoloop or a legacy `execute-<uuid>` worktree.
- ✅ **Verified sufficient against current code** (codex pass 2, independently re-grepped by the
  validator): every `.hm-loop-*` consumer uses the exact `_LOOP_MARKER_PREFIX`
  (`worktree.py:297, 952, 1956, 2299, 2746`; `gates/worktree_gate.py:82`; `hooks/loop_gate.py:54`).
  The one broader `.claude/.hm-` matcher is `worktree._path_owner:4246`, which classifies a path as
  operational churn — the correct treatment for a task marker anyway.
- ⚠️ Two marker families for the gate to read. Mitigated by one shared parser, per the
  `new-marker-content-field-must-update-every-reader` rule.
- ⚠️ The prefix's safety rests on **every** `.hm-loop-*` reader staying exact-prefix. Phase 2's
  structural test therefore enumerates them all — `marker_dir_has_session`,
  `loop_marker.MARKER_GLOB`, the two `_read_active_worktrees`, `_marker_referenced_paths`,
  `_session_worktrees`, reconciliation cleanup, marker pruning, gitignore maintenance, and
  loop-mode detection — and fails if any widens to `.hm-*`. A later shared-helper refactor is the
  realistic way this protection is lost.
**Rejected alternatives:**
- Reuse `.hm-loop-*` — Rejected for the self-stop defect above. Not raised by either model or the
  validator; found while implementing interview #10's choice.
**Source:** Round 3 design work.

### ADR-011: The marker literal becomes a churn/gitignore GLOB
**Status:** Accepted (2026-08-07)
**Context:** `worktree.py:113` carries `.claude/.hm-autopilot` in `_HARNESS_CHURN_FILES`, matched
**exactly (`==`)**. Per-session filenames stop matching. The two tuples are NOT interchangeable:
`_HARNESS_CHURN_GLOBS` (`:118-120`) is documented in its own comment as **gitignore-only**, and the
dirt predicate `_is_harness_artifact` (`:609-613`) consults exactly `_HARNESS_ARTIFACT_PREFIXES`,
`_HARNESS_CHURN_DIRS`, and `_HARNESS_CHURN_FILES` — **never the globs**.
**Decision:** Make **both** edits:
1. **Dirt filter** — add `.claude/.hm-autopilot` and `.claude/.hm-task-` to
   `_HARNESS_ARTIFACT_PREFIXES` (`:544`), which is prefix-matched and therefore covers every
   per-session filename.
2. **Gitignore** — add `.claude/.hm-autopilot*` and `.claude/.hm-task-*` to
   `_HARNESS_CHURN_GLOBS`, and remove the now-dead exact literal from `_HARNESS_CHURN_FILES`.
   The autopilot glob has **no hyphen before the `*`** deliberately: `.hm-autopilot-*` would stop
   gitignoring the bare legacy `.claude/.hm-autopilot`, which ADR-003 keeps alive until takeover.
**Consequences:**
- ✅ Markers stay non-dirt for **finalize**, which is the consumer that actually matters: without
  edit 1 every live per-session marker becomes user dirt and `worktree finalize` sweeps it into
  the finalize stash — silently disarming autopilot, and growing the stash queue that Layer 1
  guards. That is a regression in the 5-layer defense, introduced by a change meant to prevent
  marker drift.
- ✅ Markers stay git-ignored.
- ⚠️ A prefix is coarser than a literal; scoped to the two `.hm-autopilot` / `.hm-task-` shapes.
**Rejected alternatives:**
- Globs alone (the previous revision) — Rejected: `_HARNESS_CHURN_GLOBS` never reaches the dirt
  filter, so this was the regression above wearing the costume of a fix.
- Enumerate each session's file — Rejected: unbounded and unknowable at write time.
**Correction to this ADR's earlier rationale:** it claimed unmatched markers would block parallel
`worktree create` via the dirty-base guard. False — `_is_create_guard_harness_artifact:897`
already forgives every `.claude/` path. The affected guard is **finalize**, not create, and the
earlier Phase 1 exit test (which asserted the create guard) could not have detected the defect.
**Source:** validator critical finding, pass 1; corrected after pass 2.

### ADR-012: The manual two-session check is an exit criterion, not advice
**Status:** Accepted (2026-08-07)
**Context:** The draft called the check mandatory in prose while no phase required it. An
unenforced verification is advisory, which is the shape of the count:2 failure this PLAN cites.
**Decision:** Phase 3 cannot close until the four observables below are produced by two live
sessions: both arm autopilot; neither blocks the other's write; a write into a peer's worktree is
blocked; `/tmp` is never blocked.
**Consequences:**
- ✅ The only check that exercises the real payload is enforced.
- ⚠️ Phase 3 cannot close in CI alone. Intended.
**Source:** validator warning.

### ADR-013: A session may unlink only its own marker
**Status:** Accepted (2026-08-07)
**Context:** `gc_stale_marker`'s restraints ("foreignness is not a criterion, in either
direction") were argued for a single shared file. Applied over a glob, they make every session an
unlink authority over every peer's marker.
**Decision — scoped per marker family, because the two families are keyed differently.**
- **Autopilot markers** (filename **is** the session key): a session unlinks only its own key. A
  peer never deletes another's marker. This is the rule that keeps ADR-001's isolation intact.
- **Task markers** (filename is the **worktree** name; ownership lives in the content header):
  "own key" is not a well-formed notion, so the rule is instead **deletion only jointly with the
  worktree the filename names**, by whichever session removed that worktree. `cleanup_all`
  (`worktree.py:2413-2429`) is session-blind by design — a deliberate operator sweep over every
  worktree — and is therefore permitted to unlink the markers of worktrees it removed, peer-owned
  or not. Deleting a task marker while its worktree still exists is forbidden to everyone.

An earlier revision stated the self-only rule over "the caller's own key" for both families. That
was coherent only while the task filename was session-keyed, which pass-2 finding 3 removed — and
it left ADR-008's `cleanup_all` row in direct contradiction with this ADR's headline sentence.

**Autopilot markers and task markers recover differently, because only one of them has a TTL.**
The 18h TTL belongs to the autopilot marker; **loop/task marker content carries no timestamp at
all** (only `claude_session_id` and paths). An earlier revision of this ADR claimed foreign task
markers "expire by TTL" — that was false, and it mattered: a crashed session leaves its persistent
task worktree on disk, so its marker would stay effective forever and lock the restarted session
out of its own work.
- **Autopilot marker:** stale-by-TTL, GC'd by its owner only; a foreign stale marker is inert.
- **Task marker:** recovered by **takeover, not expiry**. `task-preflight` already claims/reclaims
  the registry row for a slug; it additionally **rewrites the task marker for that worktree with
  the claiming session's id**. A restarted session reclaiming its own task therefore owns the
  marker again in one step, and ADR-004's own-membership-wins precedence covers the window before
  it. A marker whose worktree no longer exists is ignored by the gate (existing `is_dir()` filter).
  **`prune_stale` must be extended to sweep `.hm-task-*`** — it currently globs
  `_LOOP_MARKER_PREFIX` only (`worktree.py:2299`), so an earlier revision's claim that orphans are
  "reaped by `prune_stale`" was false. That is the same defect class as the TTL claim it replaced —
  citing a mechanism scoped to a different prefix — caught one revision later, one line over. The
  sweep is in Phase 2's scope and exit criterion, not an assumption.
**Consequences:**
- ✅ ADR-001's isolation is not reversed through the GC door.
- ✅ Orphan recovery has a named mechanism instead of an appeal to a TTL that does not exist.
- ⚠️ A worktree abandoned and never re-claimed keeps a foreign marker until `prune_stale` removes
  the worktree. Inert for everyone except a session that wants to write **into** that worktree
  without claiming it — which is the case this gate exists to block.
**Rejected alternatives:**
- Glob-all with a liveness check — Rejected: the liveness signal is the pid ADR-008 just
  established as unreliable.
- Add a timestamp + TTL to task markers — Rejected for this release: it introduces clock-skew
  semantics to a file four other subsystems read, and takeover-on-claim solves the actual case.
**Source:** Interview #11, after validator.

### ADR-009: One release; the autopilot writer and every consumer in one commit
**Status:** Accepted (2026-08-07)
**Context:** The user chose a single release. Memory records that a partial marker migration is
worse than not starting: `_is_own` is one-directional, so a writer ahead of its readers turns
autopilot off rather than degrading it.
**Decision:** All changes ship in one release. Phase 1 lands the autopilot writer and **every**
consumer in one commit. The corrected consumer set:
- `autopilot.py` — `write`, `clear`, `load`, `gc_stale_marker`, `touch`, `set_task_slug`,
  `active_marker`, `effective_level`, `status`, plus `_is_marker_root` (`:158`, marker-as-root
  sentinel) and the gitignore seed (`:273`), plus the dot-form `off` at `:739`.
- `autopilot_caps.py` — **11 call sites across 11 lines**: 68, 195, 227, 238, 252, 312, 318, 330,
  394, 395, 398 (`active_marker`, `set_task_slug`, `resolve_marker_root`, `touch`, `clear`).
- `cli.py` — the Typer autopilot surface, including `clear` at `:2475`.
- `gates/permission_gate.py:109` — a separate module calling `resolve_marker_root`.
- `hooks/autopilot_autoarm.py` — imports `autopilot` at `:25`, calls `autopilot.write(...)` at
  `:75`, and carries an `except autopilot.MarkerOwnedByAnotherSessionError:` branch at `:82-92`
  that declines to arm. **This is the SessionStart auto-arm path for every
  `autonomy.autopilot_persistent: true` harness — i.e. the code that actually produces the symptom
  this PLAN opens with.** ADR-001 makes that refusal branch dead for id-bearing sessions: it must
  be reduced to the ADR-002 degraded-fallback case and its log line rewritten, or two
  auto-arming sessions still fail Success Criterion #1 for the one configuration that arms without
  a picker.
- `worktree.py:113` — the churn/gitignore literal (ADR-011).

**This list is no longer the mitigation.** It was missed once here (`autopilot_autoarm.py`, found
at validator pass 3) and twice before in the memory entry above — three instances of one class,
each time because the guard was another hand-written list. The mitigation is now the
import-graph test in the Testing Strategy; this enumeration is the implementation *aid*, and the
test is what fails when it is wrong.
**Consequences:**
- ✅ No intermediate state where autopilot is silently dead.
- ⚠️ The autopilot relief waits on gate work. Accepted by the user; recorded because I
  recommended shipping it first.
**Rejected alternatives:**
- Autopilot as its own release (my recommendation) — Rejected by the user.
**Source:** Interview #7; enumeration corrected after review.

## 🚫 Non-Goals

- **Bash-driven writes stay ungated.** `>`, `sed -i`, `python -c` bypass the gate by design;
  `permission_gate` owns dangerous-Bash vetting.
- **Out-of-repo writes stay allowed** (ADR-004), including `/tmp`.
- **Self-confinement is not restored** this release (ADR-004's accepted trade).
- **No registry schema change** (ADR-008), and no fix to registry pid liveness.
- **No in-repo allowlist** — no Write/Edit-tool base write has been observed that needs one.

## 🏗️ Technical Design

**Current state.** `autopilot.py` resolves one constant path, consumed by the 11+ sites above and
by a second module (`permission_gate`). `worktree.py` writes registry rows for task worktrees and
no marker. `gates/worktree_gate.py` globs `.hm-loop-*`, unions every path, and blocks anything
outside the union — session-blind, and rooted at the payload `cwd`.

**Target.** One identity — the Claude `session_id` — keys three things that already exist in
shape: the autopilot marker filename, a new task marker filename, and the gate's view of who owns
what. Nothing new is persisted beyond the task marker; the id simply stops being dropped.

**Data flow (gate, after).** payload → `session_id` (absent → **allow**, ADR-006) → `cwd` →
strip `/.worktrees/<name>/` → base root → read `.hm-loop-*` + `.hm-task-*` → partition into mine
vs peers by content header → target inside **a peer's** worktree → block; else allow.

**API changes.** `autopilot.marker_path` gains a session-key parameter; `worktree` gains task
marker write/remove. All internal — no user-facing config key changes.

## 📝 Implementation Plan

### Phase 1 — Autopilot markers become per-session
- `depends_on`: []
- `parallel_group`: serial-marker
- `merge_hazards`: `autopilot.py` rewritten across every consumer; `_is_own` semantics shared with
  `autopilot_caps`, `cli.py`, and `permission_gate`; `worktree.py:113` churn literal.
- **Scope (in):** the full ADR-009 consumer list, ADR-002's fallback name, ADR-003's CAS takeover,
  ADR-011's churn/gitignore glob, ADR-013's self-only GC, tests.
- **Scope (out):** rendered picker prose (Phase 4).
- **Exit criterion:** the **full** `uv run pytest tests/ -q` green. Not a `-k` filter: `-k` matches
  test and file NAMES, and the tests that would catch a break in `_is_harness_artifact` live in
  finalize/worktree-named files that no autopilot-shaped keyword selects — re-creating the
  "the test that would have caught it was never selected" failure this PLAN's Prior Work cites at
  count:2. The suite is ~6 minutes; the filter buys nothing. **Plus** two bespoke assertions: two
  distinct session ids arm in one project and both report `active: true`; and a per-session marker
  is git-ignored **and is not dirt under `_is_harness_artifact`** (the finalize filter — the create
  guard forgives all of `.claude/` and therefore cannot detect this).
- **Risk:** high — this predicate's reader enumeration has failed twice.
- **Rollback:** revert; the legacy path still exists at that commit.

### Phase 2 — Task worktrees get a per-session marker
- `depends_on`: [1]  *(Phase 1 owns the churn/gitignore glob tuple; two phases editing the same
  constant with no edge between them is how one silently overwrites the other)*
- `parallel_group`: serial-taskmarker
- `merge_hazards`: `worktree.py` task lifecycle (`task_create`, `task_preflight`, `task_land`,
  `cleanup_all`, create-rollback paths) **and** the churn tuple Phase 1 migrated.
- **Scope (in):** the `--claude-session-id` plumbing through `task-create` (ADR-008 — the marker
  cannot be named without it), `.claude/.hm-task-<key>` writes, the full lifecycle transition
  table from ADR-008, takeover-on-claim (ADR-013), **extending `prune_stale`'s marker sweep to
  `.hm-task-*`** (ADR-013 — it globs `.hm-loop-*` only today), extending Phase 1's dirt-filter
  prefix and gitignore glob to the task family, the exact-prefix structural test from ADR-010,
  tests.
- **Scope (out):** any `SessionRow` change; any gate behavior.
- **Exit criterion:** the full `uv run pytest tests/ -q` green (same reasoning as Phase 1),
  **including**: a task marker does **not** make `loop_gate` block the session's Stop and does
  **not** enter `_owned_session_uuids` (the ADR-010 trap, asserted rather than assumed); one
  session holding **two** task worktrees keeps both protected (the collision that killed the
  session-keyed filename); and `prune_stale` removes an orphan `.hm-task-*` whose worktree is gone.
- **Risk:** medium — new file in a directory several subsystems glob.
- **Rollback:** revert; the gate degrades to reading `.hm-loop-*` only, i.e. today's behavior.

### Phase 3 — The gate protects peers and scopes by session
- `depends_on`: [1, 2]  *(the gate CODE needs only Phase 2 — it never reads autopilot markers, and
  the first draft's edge was rightly called false. But this phase's blocking exit criterion is the
  ADR-012 two-session check, whose first observable is "both sessions arm autopilot", which is
  Phase 1's feature. Declaring `[2]` alone made the phase unable to satisfy its own exit criterion
  — codex pass 2. The edge is verification-driven, and labelled as such so a later reader does not
  delete it as redundant.)*
- `parallel_group`: serial-gate
- `merge_hazards`: `gates/worktree_gate.py` rewritten; behavior asserted by hook wiring tests.
- **Scope (in):** base-root resolution (ADR-005), payload `session_id`, peer-protection invariant
  (ADR-004), absolute fail-open (ADR-006), both marker families, the captured payload fixture.
- **Scope (out):** `permission_gate`; Bash writes.
- **Exit criterion:** the full `uv run pytest tests/ -q` green with a branch test each for:
  peer worktree blocked; base write allowed; `/tmp` allowed; no `session_id` allows; hook invoked
  **from inside a worktree** still finds the base markers; and an **empty-header** loop marker
  neither blocks its own session nor anyone else (ADR-004's third bucket — the case whose omission
  would have blocked every standalone `/hm:execute` session from its own worktree). **Plus the ADR-012 manual check**, which
  this phase cannot close without: two live sessions, both arm autopilot, neither blocks the
  other, a write into a peer's worktree is blocked, `/tmp` is never blocked.
- **Risk:** high — a wrong branch blocks all writes for a user.
- **Rollback:** revert to Phase 2; the gate returns to today's behavior.

### Phase 4 — Docs, rendered prose, CHANGELOG
- `depends_on`: [1, 2, 3]
- `parallel_group`: serial-docs
- `merge_hazards`: `CLAUDE.md` and the shipped command surface are ratchet-guarded
  (`tests/structural/test_surface_baseline.py`) — compact, never re-baseline.
- **Scope (in):** CLAUDE.md multi-session section, the autopilot picker prose (the ownership
  question is now the rare path), `worktree_gate`'s docstring (it currently calls itself "the
  technical enforcement layer", true only of the legacy loop model), CHANGELOG.
- **Exit criterion:** `uv run pytest tests/structural -q` green with no baseline raise.
- **Risk:** low.
- **Rollback:** revert; docs only.

## 🧪 Testing Strategy

- **Unit.** Two-session arming; per-session GC touching only its own key; CAS takeover with a
  byte-change between read and unlink; each gate branch driven through `main()` via **stdin with a
  realistic payload**, never by calling helpers — the probe showed the payload carries fields the
  helpers never see.
- **Structural — derived from the import graph, never from a list in this document.** The
  recurring failure across three validator passes and two prior PLANs is *enumeration
  completeness*, and every mitigation tried so far has been another hand-written list, which fails
  the same way. The test therefore **discovers** its own subjects: walk `src/harness_maker/`, collect
  every module that imports `harness_maker.autopilot` (AST, not grep), and for each one assert that
  every call into the marker API — `write`, `load`, `status`, `clear`, `touch`, `set_task_slug`,
  `active_marker`, `effective_level`, `gc_stale_marker`, `marker_path`, `resolve_marker_root` —
  passes a session key. A new consumer added later is in the test's subject set the moment it
  imports the module, with no edit to this PLAN or to the test.
  - The predicate set above deliberately includes `write`, `load`, `status`, and `gc_stale_marker`.
    An earlier revision omitted them, and `write` is the **only** API the module that was missed
    (`hooks/autopilot_autoarm.py`) calls — so the mitigation was blind to precisely the gap it
    existed to catch.
  - Plus a test asserting the marker prefixes are in **`_HARNESS_ARTIFACT_PREFIXES`** (the tuple
    the dirt filter reads) as well as in the gitignore globs — asserting only the globs would
    certify the exact broken state ADR-011 documents.
  - Plus the ADR-010 exact-prefix test (no `.hm-loop-*` reader may widen to `.hm-*`).
- **Integration.** Gate run as a subprocess against a real tmp project with markers on disk,
  asserting exit 0/2, including an invocation whose `cwd` is inside `.worktrees/<slug>`.
- **Manual (ADR-012, blocking).** The four two-session observables in Phase 3's exit criterion.

## ⚠️ Risks & Mitigation

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| A consumer is missed → autopilot silently off | **High** (three instances of this exact class so far, one of them found inside this PLAN) | High | The **import-graph structural test** — the guard no longer depends on any list a human wrote. ADR-009's enumeration is an implementation aid, not the mitigation. Plus the atomic commit (ADR-009) |
| Per-session markers counted as user dirt → parallel `create` blocked | Medium | High | ADR-011 glob + a Phase 1 test asserting the create guard ignores them |
| Task marker mistaken for a loop marker → sessions cannot stop | Medium | High | ADR-010 distinct prefix + a Phase 2 test asserting `loop_gate` and `_owned_session_uuids` ignore it |
| Gate over-blocks → user cannot write | Low | High | Absolute fail-open, peer-only invariant, per-branch tests, ADR-012 manual gate |
| Gate rooted at the worktree → reads no markers, enforces nothing | Medium | Medium | ADR-005 base-root strip + an integration test whose `cwd` is inside a worktree |
| Payload shape changes upstream | Low | Medium | Fixture from the live probe; degrades to allow, never to block |
| Surface ratchet trips on Phase 4 | Medium | Low | Compact first; never re-baseline the ratchet this change trips |

## ✅ Success Criteria

- [x] Two sessions in one project can both hold `autopilot status → active: true`.
- [x] The "another session" prompt does not appear on the normal two-session path.
- [x] A write into another session's worktree is blocked.
- [x] A peer's marker never blocks a base write, and `/tmp` is never blocked.
- [x] A session with no worktree is never blocked anywhere in the repo.
- [x] A task marker does not stop a session from stopping, and does not enter loop ownership sets.
- [x] Per-session markers are git-ignored and are not counted as dirt by the create guard.
- [x] GC unlinks only the caller's own marker.
- [x] No runtime input is trusted without a probe transcript in its ADR.

> **Post-review reality check (2026-08-07).** The boxes above are ticked to mean *the phase that
> owned each criterion was implemented*, **not** that every criterion holds in production. Review
> closed at grade **B / CHANGES_REQUESTED** with `human_review_needed: true`
> (`work-docs/REVIEW-multisession-marker-scoping-2026-08-07.md`). A consensus-passed **P1 remains
> open**: the marker takeover performed by `task_preflight` is **unbounded** — `reclaim_stale`
> drops a peer's registry row because the recorded pid is the already-exited `uv run` subprocess,
> so `_foreign_live_rows` is always empty and two concurrent sessions on the same slug evict each
> other. Every criterion whose truth depends on stable marker ownership is therefore **NOT
> satisfied** in the concurrent case — specifically:
> - "A write into another session's worktree is blocked" — holds only until the peer's preflight
>   flips the header; then it blocks the *wrong* session, in a flip-flop rather than a resolution.
> - "A session with no worktree is never blocked anywhere in the repo" and "Two sessions can both
>   hold `autopilot status → active: true`" — unaffected by CR-2, satisfied as written.
>
> Also open and **manual-only**: a degraded (empty `$HM_SESSION_ID`) resume is still locked out,
> plus three P2s. See the REVIEW's open-findings section before treating this PLAN as closed.

## 🔍 Plan Validation

**Pass 1 — `MAJOR_REVISION`** (`plan-validator`, run-id `msms-20260807-1`). Cross-model second
opinion ran both enabled models; both `invoked`. 19 findings, 18 `accepted`, 1 `duplicate`;
validator added 5 critiques (1 critical, 3 warnings, 1 suggestion).

Resolution: three ADRs were replaced rather than patched — ADR-004 (union rule → peer protection,
interview #8), ADR-006/007 (contradiction → fail-open absolute, #9), ADR-008 (registry field →
task marker, #10) — and ADR-011/012/013 were added from the validator's findings. ADR-010 came
from implementing #10 and was raised by no reviewer. Consumer enumeration corrected from 2 to 11
call sites plus two previously unnamed modules.

**Pass 2 — second opinion.** `codex` `invoked` (7 findings, 4 × P1, all accepted and resolved
below). **`antigravity` `failed`** — `payload unreadable via stdout: ValueError: expected exactly
one JSON payload in antigravity output, found 0; CLI said <<<<empty>>>>`. Treat pass 2 as
**Claude + codex only**; antigravity cast no vote and its silence is not agreement. (The reason
string names the rule because of the 0.49.1 diagnostic fix landed earlier the same day; before it,
this would have read only `ValueError`, leaving parser-strictness and an empty CLI reply
indistinguishable. Here it settles the question: agy produced nothing.)

Pass-2 resolutions: ADR-004 gained an explicit own-membership-wins precedence; ADR-008 gained the
`--claude-session-id` plumbing for `task-create` (without which the marker cannot be named at all)
plus the complete lifecycle transition table; ADR-013's false "task markers expire by TTL" claim
was replaced with takeover-on-claim, since loop/task marker content carries no timestamp; ADR-010
gained the exact-prefix reader enumeration; Phase 2 now depends on Phase 1 for the shared churn
tuple; Phase 3's dependency was restored to `[1, 2]` because its own manual exit criterion
requires Phase 1's feature.

**Pass 2 — validator: `MAJOR_REVISION`** (run-id `msms-20260807-1`, pass 2). Three criticals, all
verified against source: ADR-011 moved the marker to a **gitignore-only** tuple the dirt filter
never reads (so finalize would have stashed live markers) and its stated rationale named the wrong
guard; ADR-004's mine/peer partition had no bucket for the **empty-header** markers every
standalone `/hm:execute` worktree writes, which would have blocked those sessions from their own
work; and ADR-010's session-keyed task filename collides when one session holds two task
worktrees, making ADR-008's transition table unimplementable. Plus: ADR-013's replacement orphan
mechanism (`prune_stale`) globs `.hm-loop-*` only — the same "cite a mechanism scoped to a
different prefix" defect as the TTL claim it had just replaced; Phase 1's `-k` filter could not
select the tests that matter; and three citation errors.

All seven resolved: ADR-011 now specifies both edits (`_HARNESS_ARTIFACT_PREFIXES` for dirt,
globs for gitignore) and carries an explicit correction of its own earlier rationale; ADR-004
states a three-way partition; ADR-010 keys the filename by worktree with the session id in the
content header, mirroring `.hm-loop-{wt_name}`, which makes every ADR-008 transition a whole-file
unlink; `prune_stale`'s `.hm-task-*` sweep is in Phase 2's scope and exit criterion; all three
phases run the full suite; citations corrected.

**Pass 3 — validator: `MAJOR_REVISION`** (exceeds the stage's "re-run once only" rule by explicit
user decision). Five of the seven pass-2 findings verified **RESOLVED and source-accurate**; zero
new design faults. What remained was one class: **enumeration completeness**.
- CRITICAL: a **sixth** consumer, `hooks/autopilot_autoarm.py` (`:25`, `:75`, `:82-92`) — the
  SessionStart auto-arm path whose `MarkerOwnedByAnotherSessionError` branch is what actually
  produces this PLAN's opening symptom for `autopilot_persistent` harnesses. The structural test
  designated as the mitigation omitted `write`, the only API that module calls.
- Two warnings **created by the pass-2 fix**: the task marker's content schema was unspecified
  (and `_is_orphan_marker`'s `bool(refs)` clause makes a header-only marker permanently non-orphan,
  so Phase 2's own exit criterion was unsatisfiable), and ADR-013's "self-only key" invariant
  became undefined once the filename stopped being the session key, putting ADR-008's `cleanup_all`
  row in contradiction with it.
- One warning: `_cli_task_create`'s `startswith("--")` positional filter would swallow the flag
  value as `base_dir`.

All resolved. **The structural change this pass forced is the important one:** the mitigation for
the enumeration class is no longer a list in this document. It is an **import-graph-derived test**
that discovers every module importing `harness_maker.autopilot` and asserts each marker-API call
passes a session key. Three instances of this failure class have now been fixed by writing a better
list, and all three lists were wrong; a guard the author cannot forget to update is the only form
that has not already failed.

## 🚧 Execution status (`/hm:execute`, 2026-08-07)

| Phase | Status | Notes |
|---|---|---|
| 1 — autopilot per-session markers | **done** | full `pytest tests/ -q` green (`rc=0`) |
| 2 — task worktree markers | **done** | verified in the combined P2–P4 full-suite run |
| 3 — gate peer-protection | **done** | ADR-012 manual two-session check **NOT run** — see below |
| 4 — docs / prose / CHANGELOG | **done** | `pytest tests/structural -q` green, ratchet not re-baselined |

**Deviations, stated rather than absorbed.**

1. **ADR-012's manual two-session check has not been performed.** Phase 3's exit criterion
   says the phase "cannot close" without four observables from two live sessions (both arm;
   neither blocks the other's write; a write into a peer's worktree is blocked; `/tmp` is
   never blocked). Everything except "two live Claude sessions" is covered by automated
   tests, including a subprocess-level gate invocation from inside a worktree. The manual
   check is the only thing that exercises the real PreToolUse payload end to end, and
   ADR-012 exists precisely because an unenforced verification is advisory. **Phase 3 is
   therefore implementation-complete but not exit-criterion-complete**, and this is the one
   item to run before this work is treated as landed.
2. **The full suite ran three times, not four.** Phase 1 alone (green), then (2, 3, 4)
   together — that run was **red** on 10 tests, all downstream artifact drift from the
   template + gitignore changes: an equality line-count pin on the wrapup render (restored
   by reflowing the picker prose rather than moving the pin) and the eight synthesize
   snapshots (regenerated; the diff is `content_hash`/`sha256` lines only, and the fixtures
   were grepped for a leaked worktree path — none). A third full run confirms green. The
   phases in the second group were verified together rather than individually; every phase's
   own bespoke assertions ran when it was written.
3. **ADR-005 is implemented locally, not by calling `autopilot.resolve_marker_root`.** The
   gate fires on every `Write`/`Edit`, and importing `autopilot` pulls in pydantic plus the
   5k-line `worktree` module on that latency path. `gates/worktree_gate._strip_worktree`
   duplicates the strip + parent walk using only the stdlib, and
   `tests/structural/test_gate_base_root_parity.py` is the anti-drift guard — it asserts the
   two agree on the worktree branch, the harness-root branch, the subdirectory branch, and
   the no-`harness.yaml` degradation ADR-005 records as accepted risk.
4. **`resolve_marker_root` is NOT in the import-graph test's keyed set.** ADR-009's predicate
   list names it, but it resolves a project ROOT and takes no marker key, so "assert it is
   passed a session key" is unimplementable. `test_resolve_marker_root_stays_key_free` pins
   the exclusion as an assertion rather than leaving it an omission.
5. **`status` gained a `degraded-idless` diagnostic that ADR-001 would otherwise have
   deleted.** With per-session filenames an id-less caller reading a project where an
   id-bearing marker exists simply finds nothing at its own key. Reporting plain `absent`
   there would erase the documented WSL2 signal, so `_some_id_bearing_marker` restores the
   label. It is read-only (ADR-013 restricts unlinking, not looking) and nothing branches on
   it — `active` is `false` either way.

**Phase D.5 — newly-reachable window (the repair-only step).** This work is a defect repair,
so the green gates above measure the coverage that existed *before* it.

- *Window opened.* Before this change exactly one `.hm-autopilot` file could exist and no
  `.hm-task-*` file could. Newly reachable: **N>1 marker files coexisting** in one
  `.claude/`; a filename **derived from an external string** (`session_id`); the **legacy
  file coexisting** with a per-session one; and, for the gate, a **payload-identified**
  caller partitioning markers three ways instead of unioning them.
- *Tests entering it, in this commit.* `test_two_sessions_arm_in_one_project` and
  `test_two_autoarm_sessionstarts_both_arm` (N>1, and the autoarm path that has no picker in
  front of it); `test_gc_unlinks_only_the_callers_own_marker` and
  `test_clear_removes_only_the_callers_marker` (N>1 with a destructive op);
  `test_a_session_id_cannot_collide_with_the_degraded_name` (hostile external string);
  `test_legacy_takeover_never_clobbers_an_existing_per_session_marker` (coexistence);
  `test_two_task_worktrees_in_one_session_are_both_marked`;
  `test_empty_header_marker_never_blocks_anyone` and
  `test_own_membership_wins_over_a_peer_claim` (the two gate buckets that are work stoppages
  rather than missed blocks, and the two an inverted implementation passes without).
- *Absent case* (the repo's most-recurring class, count:8). Both features activate on an
  optional input. `session_id` absent → `.hm-autopilot-degraded` (ADR-002, covered) and **no**
  task marker at all (ADR-008, covered by `test_task_create_without_an_id_writes_no_marker`);
  a marker written *before* this change → one-shot CAS takeover (ADR-003, covered both ways).
  The gate's absent case is ADR-006's absolute fail-open, covered in-process and as a
  subprocess.

**Validation closed here by user decision.** The remaining risk is not that the design is wrong —
pass 3 found no design fault — but that some enumeration is still incomplete, which is precisely
what the import-graph gate converts from a review problem into a test failure at execute time.
