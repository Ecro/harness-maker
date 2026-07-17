---
type: review
task_slug: permission-deny-and-hooks-wiring
phase: 2
status: APPROVED
created: 2026-07-17
reviewers_invoked: [code-reviewer, codex]
consensus_method: cross-check (K=2 of N=2)
drift_verdict:
  result: clean
  scope_violations: []
  scenario_misses: []
  task_slug: permission-deny-and-hooks-wiring
  computed_at: 2026-07-17T10:10:00Z
human_review_needed: true
---

# REVIEW — permission-deny-and-hooks-wiring **Phase 2**

## 🎯 Summary

**Round 1 grade: B** (P0=0, consensus-passed P1=1) against `grade_threshold: A` → auto-fix.
**Round 2 grade: A.** Status **APPROVED**, `human_review_needed: true`.

The consensus P1 is the interesting one: **Phase 2, as first written, shipped a blocking
gate under the label ADR-006 reserves for non-blocking control flow.** Both voters found it
independently. It is fixed by splitting the staging axis from *module* to *event*.

## 🔍 Drift Findings

**Clean.** Changed: both settings templates, `test_render_settings_hooks.py`, 8 snapshots
(each exactly one `settings.json body_sha256`), and the PLAN. All inside Phase 2's scope.
No repeat of Phase 1's `test_permissions_deny_optout.py` collateral.

## ✅ Consensus Findings

### P1 — `autopilot_guard`'s PreToolUse copies are Stage-3 blockers shipped as Stage 2
`consensus-passed [2/2]` — **codex** (`Production.json.j2:57`) + **code-reviewer**
(`Production.json.j2:53`). Same symbol, same CONCLUDE. **FIXED in round 2.**

ADR-006's own Stage-3 criterion: *"can block ordinary tool calls **and** have never executed
in Claude Code."* `autopilot_guard._pretooluse` returns `allow=False` →
`autopilot_guard.py:330` → exit 2 → the tool call is blocked. Both conjuncts hold.

**code-reviewer's decisive evidence, which the author did not have:** the second conjunct
holds *harder* for `autopilot_guard` than for `permission_gate`. `permission_gate` is live in
Cursor (`cursor/hooks.json.j2:33`) and Codex (`codex/hooks.json.j2:26,39`). **`autopilot_guard`
is wired in NO IDE today** — absent from both. Phase 2's diff would have been **its first
execution as a hook anywhere**, shipped without the live negative control ADR-006 makes an
explicit Stage-3 exit criterion.

**"Only blocks under autopilot" does not rescue it.** With `autonomy.autopilot_persistent:
true` (`models.py:787`), `autopilot_autoarm.py:65` re-arms a fresh marker at **every**
SessionStart — so for that population the PreToolUse block is unconditional in every session.
What they opted into was auto-advance, not "block my `git push` (`autopilot_guard.py:122`),
my `terraform apply` (`:46`), my `rm` with a `$` operand (`:169`)". The escape hatch is
coarse: exit 2 + a stderr line telling the agent to delete the marker (`:258-260`), with no
per-call override — and under `autopilot_persistent` the deletion is undone at the next
SessionStart.

**Not hypothetical for this session:** a live `.hm-autopilot` marker (armed 16:48, 18h TTL)
sits at the project root right now. Had Phase 2's PreToolUse wiring been in the base repo's
`settings.json`, this session would have been blocked.

**Stop-blocking is correctly Stage 2** — both voters agree. It cannot block a tool call, it
is bounded by each module's `stop_hook_active` guard (`loop_gate.py:102`,
`autopilot_guard.py:302`), and the worst case is one extra turn.

**Fix applied (round 2):** the staging axis is now the **event**, not the module. Stage 2 =
the Stop event only. Stage 3 = anything that can block an ordinary tool call — the three
gates **plus** `autopilot_guard`'s two PreToolUse copies. One module, two stages. The
PreToolUse groups were removed from both templates; `test_settings_ships_no_tool_call_blocker_yet`
pins PreToolUse **empty**, which is what keeps Stage 3's negative control from being skipped.
ADR-006 and both template headers were corrected to state the event axis and the reason.

## 📝 Manual-Only Findings

**One P1 survives unverified — it sets `human_review_needed: true`.**

### P1 — `permission-surface-write` matches **READS** of settings.json
`manual-only` — **code-reviewer** (`autopilot_guard.py:53`). Not fixed here; **Phase 3 must
fix it before wiring the PreToolUse copies.**

`autopilot_guard.py:53-59` registers the category `permission-surface-write` as a bare path
regex with **no write/redirect requirement**, despite the comment at `:51` claiming it targets
"a Bash write/redirect". `_bash_hit` (`:231-233`) does `pattern.search(segment)` over every
segment → `evaluate` (`:254`) returns `allow=False` → exit 2.

Concrete: with a marker armed, **`cat .claude/settings.json`** — or `grep hooks
.claude/settings.json`, or `git diff .claude/settings.json` — is **blocked**, with the message
"blocked never-auto op (permission-surface-write)". A read, blocked, under a category name
that actively misdirects diagnosis.

This session ran commands of exactly that shape repeatedly. The only reason nothing broke is
that `autopilot_guard` is not wired into the base repo's `settings.json`. **Phase 3 is the
phase that would make this live.** Fix: require a write/redirect context (`>`, `>>`, `tee`,
`sed -i`, `cp .. <path>`) before matching, or rename the category and accept read-blocking
explicitly — plus a negative-control test for `cat .claude/settings.json` under an armed
marker.

### P2 — `loop_gate`'s Stop hook prints control JSON on stdout while exiting 2
`manual-only` — **code-reviewer** (`loop_gate.py:118`). Either exit 0 with
`{decision:block,reason}` on stdout, or exit 2 with the reason on stderr. Which one Claude
Code honors is **unverified** — it must be checked during Phase 2's live check before the
loop is called fixed.

### P2 — asymmetric `--mode` contract
`manual-only` — **code-reviewer** (`autopilot_guard.py:336`). `autopilot_guard` defaults to
`pretooluse`; `loop_gate` has `required=True` (`:163`). Both are *correct* as wired today, but
the asymmetry means Phase 3's PreToolUse entries will depend on an implicit default. Note the
merge consequence: `_normalize_hm_managed_command` keys on module **plus trailing args**, so
adding an explicit `--mode pretooluse` later is a merge transition needing its own test.

## ⚠️ Cleared by review (recorded so Phase 3 does not re-litigate)

- **`--mode` correctness**: `autopilot_guard` defaults to `pretooluse` (`:336`) so the
  flagless PreToolUse entries would dispatch right; `loop_gate`'s `required=True` (`:163`) is
  satisfied by the Stop entries. **`loop_gate --mode pretooluse` is NOT a gap** in
  settings.json — it exists only because Cursor has no Stop event (`loop_gate.py:144-153` is
  advisory, always exit 0). Claude has Stop; wiring it would add a redundant stderr reminder.
- **Upgrade path is clean**: for a Phase-1 user, PreToolUse/Stop are absent on disk, so
  `_merge_hooks_json` (`render.py:772-821`) takes them from `new_entries` verbatim — no
  duplicate, no drop. A user's own PreToolUse/Bash group has a different `_entry_identity`
  and is preserved alongside; a hand-copied `[permission_gate, autopilot_guard]` group gets
  `autopilot_guard` stripped by `_strip_shipped_commands` while `permission_gate` survives.
- **Tests are not vacuous**: all Stage-2 template assertions fail against Phase-1 templates.
  `test_merge_stage2_to_stage3_group_growth_neither_duplicates_nor_loses` exercises a **real**
  drop path — `_strip_shipped_commands` returning None (`render.py:737`) is the only thing
  removing the superseded group; without it `assert len(groups) == 1` fails and the guard
  fires twice.

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | B     | —             | 1 consensus P1 + 3 manual (1×P1, 2×P2) | — |
| 2         | A     | 4             | 3 manual (1×P1, 2×P2) | 0 |

Round-2 fixes: (1) the event-axis split — PreToolUse groups removed from both templates,
ADR-006 + both template headers corrected; (2) `test_settings_ships_no_tool_call_blocker_yet`
replaces the two matcher tests, pinning PreToolUse empty; (3) Stop timeout 5s → 10s (the 5s
was copied from a template that had never executed; on timeout the hook is cancelled
**fail-open** → the loop silently self-stops at iteration 1 — the exact symptom CLAUDE.md
attributes to `HM_SESSION_ID` degradation, which would have made this bug invisible by
blaming a known one); (4) `test_merge_preserves_both_all_harness_and_mixed_groups_when_template_is_silent`
swapped `autopilot_guard` → `worktree_gate`, since the former is shipped as of Phase 2 and the
docstring's "a module the template does not ship" had become false.

Final grade: **A**
Iterations used: 2 / 3
Status: **APPROVED**
human_review_needed: **true**

⚠️ **Grade A with 1 unverified severe finding (manual-only P1).** The
`permission-surface-write` read-blocking false positive is **not** pre-existing-and-out-of-scope
the way Phase 1's leftovers were — it is dormant only because nothing wires
`autopilot_guard`'s PreToolUse path, and **Phase 3 is the phase that wires it**. It is a
Phase-3 blocker, recorded here because Phase 2's review is where it surfaced.

**Voter pool: 2, not 3.** `antigravity` was not invoked this round — it has failed 2/2 this
session (`agy --print --sandbox … < file` ignores stdin). `codex` required the known
workaround: the recipe resolves `.claude/schemas/…` relative to cwd, and `.claude/` does not
exist inside a task worktree, so it must be given the base repo's absolute path or it exits 1
and is silently skipped. With 2 voices, K=2 means **every** consensus needs unanimity — a
defect either voter misses cannot reach consensus at all.

## 🚧 Follow-ups (unchanged from Phase 1's review, still open)

1. `codex` second opinion is dead on the feature-branch path (`.claude/schemas/…` resolved
   relative to a cwd where `.claude/` does not exist).
2. `antigravity` never reads its prompt (2/2 this session; Production mandates it every review).
3. Consensus filter cannot bridge severity tiers.
4. wrapup destroys deliverables when `work-docs/` is gitignored — **repo side fixed**
   (`91e9de12`); the **stage** still has no guard.
