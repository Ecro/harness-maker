---
type: research
task_slug: autopilot-advance-noop
status: complete
created: 2026-07-31
tags: [harness-maker, research, autopilot, auto-advance, templates, hooks]
mtime_warn_days: 7
libs_fetched: []
sources: []
related_docs: [[[PLAN-human-bottleneck-auto-advance]], [[RESEARCH-autopilot-invocation-and-marker-fix]]]
summary: "Autopilot announces the advance but stops: stale-marker suppresses the picker, no Stop-hook backstop, contradictory stage-terminal STOP"
---

# RESEARCH — autopilot announces the next stage but does not run it

## 🎯 Recommended Direction

The "autopilot으로 다음으로 진행합니다" line is emitted by a **prose instruction the
model is free to ignore**, and three independent defects make ignoring it the normal
outcome rather than the rare one. Fix them as one bundle, in this order of leverage:

1. **Stale-marker suppression of the picker** (`.claude/.hm-autopilot` from
   2026-07-29T01:47Z is still on disk on 2026-07-31; `active_marker` rejects it as
   outside the 18h TTL but *nothing deletes it*). The picker's arm condition is
   "if **no** `.hm-autopilot` marker is active yet" — with no deterministic command
   to evaluate "active", the model checks for the file, finds it, and skips arming.
   Every subsequent boundary check then returns `kill_switch`. Verified live:
   `hm autopilot_caps boundary --root . --current research` →
   `{"proceed": false, "halt_kind": "kill_switch", …}`.
2. **No enforcement layer.** `templates/hooks/hooks.json.j2` and
   `templates/settings/Production.json.j2` both reference
   `harness_maker.hooks.autopilot_guard` — **that module does not exist**
   (`src/harness_maker/hooks/` contains only `autopilot_autoarm`, `flush_session`,
   `loop_gate`, `post_write_reminder`, `sessionid_envfile`, `sessionstart_drift`).
   The rendered `.claude/settings.json` wires only `autopilot_autoarm`. So the
   Stop-hook backstop the code comments repeatedly assume ("the Stop-hook backstop
   keeps blocking termination", `autopilot_caps.py:191`) is not present in any IDE.
   Auto-advance is 100% model compliance, 0% mechanism.
3. **A directly contradictory instruction earlier in the same prompt.** Every stage
   body carries a **Stage terminal** paragraph — e.g. `stages/research.md.j2:293`:
   "then **STOP**. Do not proceed to `/hm:spec`, `/hm:plan`, or any other stage
   without an explicit user command. This boundary must survive context compaction."
   It is unconditional, emphatic, and appears *before* the auto-advance block, which
   never claims to override it. When the model resolves the conflict conservatively
   it prints the banner and stops — exactly the reported symptom.

Main impact is **user-facing workflow value** (autopilot is the feature; it is
effectively dark), with a maintainer-visible correctness bug in the ledger.

## 🔍 Refinement Decisions

Discovery lens: **Technical architecture / implementation** (codebase-internal
audit) plus **Risk / compliance** for the ledger-integrity finding. `--deep` was not
set; the topic was already specific ("autopilot prints but does not advance").

## 🛠️ Approaches Found

### A1 — Make "is autopilot active?" a deterministic command + GC the marker (RECOMMENDED)

| Field | Content |
|-------|---------|
| Approach | Add `hm autopilot status` (JSON: `active`, `reason`, `level`, `pipeline`), have `active_marker` **unlink** a stale/foreign marker it rejects, and rewrite the picker to branch on that command instead of on the model's guess |
| Assumption | The picker's mis-read is the dominant arm-failure path; the model reliably follows a command whose output is an explicit boolean |
| Evidence | `autopilot.py` CLI exposes only `on`/`off` — no `status` (`main()` `choices=["on","off"]`). `active_marker` (`autopilot.py:245`) returns `None` for a stale marker but never deletes it; the live marker on disk is 2 days old and still present. Picker prose in the rendered stage supplies no check command |
| Trade-off | Deleting on read makes `active_marker` impure (currently a pure predicate) — put the unlink in a separate `gc_stale_marker()` called by the picker/status path, not inside the predicate |
| Compatibility | Additive CLI subcommand; matches the existing `autopilot_caps boundary` JSON-out convention the template already parses |
| Risk | low |

### A2 — Ship the missing `autopilot_guard` Stop-hook

| Field | Content |
|-------|---------|
| Approach | Implement `harness_maker.hooks.autopilot_guard --mode stop-hook`: on Stop, if a live marker exists and the current stage's gate is clear, block termination and re-inject "advance to `<next>`" |
| Assumption | A Stop-hook can meaningfully re-drive the session — Claude Code's Stop hook can return a block decision with a reason |
| Evidence | Three templates already reference the module and one settings comment even cites `autopilot_guard.py:330 → exit 2`, i.e. it existed at review time and was never landed. `.claude/hooks/hooks.json` (the dead path, CLAUDE.md 2026-07-17) is where two of the three references live — even if the module existed, those two wirings would be inert in Claude Code |
| Trade-off | Stop-hook `cwd` is the project root and the payload carries no worktree identity (same limitation documented for `loop_gate` in CLAUDE.md) — the guard cannot attribute a worktree-scoped stage; it can only act on base-root marker state |
| Compatibility | Must be wired into `.claude/settings.json` (`hooks` key), **not** `.claude/hooks/hooks.json` |
| Risk | medium — a buggy Stop-hook that blocks unconditionally is a hard-to-escape loop; needs the kill switch checked first |

### A3 — Remove the instruction conflict (prompt-only, cheapest)

| Field | Content |
|-------|---------|
| Approach | Make the Stage-terminal paragraph conditional: "…then **STOP** — **unless the auto-advance check below returned `proceed: true`**", and move the auto-advance block *after* the STOP banner text or fold the banner into the `proceed: false` branch |
| Assumption | Recency + explicit precedence is enough to flip model behavior most of the time |
| Evidence | 7 stage templates carry the unconditional STOP (`grep "Stage terminal"`); the auto-advance partial (`agents/_partials/stage_end_summary.md.j2`) says "instead of printing the STOP banner" but never addresses the earlier prohibition |
| Trade-off | Still prose-only — no mechanism. Improves the odds, does not make it deterministic |
| Compatibility | Pure template edit; every snapshot/render hash moves |
| Risk | low |

### A4 — Fix the ledger's advance-vs-intent conflation (independent, do regardless)

| Field | Content |
|-------|---------|
| Approach | Split `advanced` into `advance_authorized` (written by `boundary`) and `advance_entered` (written by the next stage's preamble when it actually starts) |
| Assumption | The step cap should count stages *run*, not stages *authorized* |
| Evidence | `autopilot_caps._cmd_boundary:221` appends `{"event":"advanced","to":nxt}` **before** the model does anything; `count_events(root, "advanced")` feeds the step cap. `auto-advance.jsonl` therefore shows `advanced` rows for advances that may never have happened — the ledger cannot distinguish the reported failure from success, which is why the bug went unmeasured |
| Trade-off | Two events instead of one; `/hm:health`'s smoke check and the step-cap arithmetic both need updating |
| Compatibility | Ledger is append-only JSONL with a `Literal` event vocabulary (`autopilot_ledger.LedgerEvent`) — extend the Literal, keep `advanced` readable for history |
| Risk | low |

## ⚠️ Pitfalls

- **`.claude/hooks/hooks.json` is dead in Claude Code** (CLAUDE.md, confirmed by
  controlled experiment 2026-07-17). Two of the three `autopilot_guard` wirings live
  there. Re-landing the guard without moving it to `.claude/settings.json.hooks`
  reproduces the same silent no-op.
- **`_current_session_uuid` is project-scoped, not session-scoped.** `active_marker`'s
  docstring admits it (`autopilot.py:219`): within one project the uuid is stable, so
  the *only* real cross-session guard is the 18h TTL. A marker armed in session A is
  "yours" in session B for 18 hours. That is the mirror failure of the stale-marker
  bug — autopilot silently *inherited*, not silently off — and any fix must handle
  both directions.
- **`autopilot_persistent: false`** (this repo's `.claude/harness.yaml:185`) means
  `autopilot_autoarm` is a no-op every session, so arming depends entirely on the
  picker. The picker is the single point of failure and it has no deterministic check.
- **`Skill(hm:<next_stage>)` carries no arguments.** The advance block names no slug,
  so a stage that parses `$ARGUMENTS` (e.g. `.claude/commands/hm/execute.md:155`)
  starts blank. Even a compliant model may then stall asking for the slug — which
  reads to the user as "announced but did nothing".
- **Gates are STOP-biased by design.** `plan`'s gate stops on any pending
  `AskUserQuestion` round and `review`'s stops on `CHANGES_REQUESTED` — both are the
  common case. Some observed non-advances are correct behavior; the ledger's
  `gate_blocked` rows (2026-07-21, -26, -27, -29) are legitimate. Do not "fix" these.

## ❓ Open Questions

1. **Is A2 (Stop-hook guard) wanted at all, or is the enforcement gap acceptable?**
   The `REVIEW-autopilot-guard-interactive-scope-2026-07-18.md` history suggests the
   guard was deliberately parked. If it stays parked, the template references must be
   deleted — a reference to a non-existent module is worse than no reference.
2. **Should a stale marker be deleted on detection, or left for forensics?** A1
   assumes delete; the alternative is a `.hm-autopilot.stale` rename.
3. **Does the picker's arm condition need a slug carried into the pipeline?** i.e.
   should the marker record the task slug so `Skill(hm:execute)` can be given one?
4. **Which stages may legitimately auto-advance?** With `plan` and `review` both
   STOP-biased, the practical chain is `research → spec → plan`(stop) and
   `execute → review`(stop). Is a 2-stage chain worth the machinery?
5. Ledger split (A4) changes the step-cap denominator — is any existing harness
   relying on the current count?

## 📚 Sources

No external sources. All evidence is codebase-internal and reproducible:

- `src/harness_maker/autopilot.py` (`active_marker`, `main` CLI surface, `_MARKER_TTL_HOURS`)
- `src/harness_maker/autopilot_caps.py` (`_cmd_boundary`, `_HUMAN_GATED_STAGES`)
- `src/harness_maker/autopilot_ledger.py` (`LedgerEvent`, `count_events`)
- `src/harness_maker/hooks/` directory listing (no `autopilot_guard.py`)
- `src/harness_maker/templates/agents/_partials/stage_end_summary.md.j2`
- `src/harness_maker/templates/stages/*.md.j2` (`Stage terminal`, `summary_autopilot_gate`)
- `src/harness_maker/templates/hooks/hooks.json.j2`, `templates/settings/Production.json.j2`
- `.claude/.hm-autopilot`, `.claude/harness.yaml`, `.claude/settings.json`,
  `.claude/observability/auto-advance.jsonl`
- Live run: `hm autopilot_caps boundary --root . --current research` → `kill_switch`

## 🔗 Related Internal Docs

- [[PLAN-human-bottleneck-auto-advance]] — the originating plan (ADR-002 merge-gate,
  ADR-005 live auto-advance, ADR-006 pipeline end, ADR-007 caps, ADR-009 ledger)
- [[RESEARCH-autopilot-invocation-and-marker-fix]] — the prior systemic invocation
  audit; its canonical-`hm` fix has landed (the boundary command runs cleanly today),
  but its items 3 and 4 (authoritative marker reference for the LLM; marker resolved
  at project root) are the direct ancestors of this finding
- [[REVIEW-autopilot-guard-interactive-scope-2026-07-18]] — why `autopilot_guard`
  was scoped down; likely explains why the module was never landed
- [[REVIEW-human-bottleneck-auto-advance-p6-2026-06-20]] — the P6 stage-terminal
  review, where the STOP-vs-advance conflict should have surfaced
