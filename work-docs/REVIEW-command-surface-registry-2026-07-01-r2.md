---
type: review
task_slug: command-surface-registry
status: APPROVED
created: 2026-07-01
review_round: 2 (deep re-review of committed c2dd9656)
reviewers_invoked: [code-reviewer, codex]
consensus_method: k-of-2 cross-model (deep pass)
drift_verdict:
  result: clean
  scope_violations: []
  scenario_misses: []
  task_slug: command-surface-registry
  computed_at: 2026-07-01
codex_status: invoked
---

## 🎯 Round 2 Summary (deep re-review)

Deep second pass over the already-landed `command-surface-registry` change (net diff
`754415f7..c2dd9656`, src+tests). Grade **A** on the grade gate (0 consensus P0/P1).
Round 1's two findings (spec_inventory `generate-all` omission; one-directional subparser
parity) were confirmed fixed and NOT re-reported. This pass targeted the residual/subtle
class. Two consensus improvements applied (a real CI-hardening gap + a UX correction);
five suspected gaps were actively **refuted** with evidence.

## 🔍 Drift Findings

None. `drift_verdict.result: clean` — all changes in PLAN scope.

## ✅ Consensus Findings (applied)

### P2 — Manual-dispatch parity was one-directional (omission asymmetry)
`tests/unit/test_command_surface_gate.py` — **code-reviewer (P2) + Codex (medium)**, aligned
CONCLUDE. Round 1 made the *subparser* parity bidirectional, but the *manual-dispatch* parity
(`test_tc2_manual_dispatch_registry_matches_source`) stayed registry→source only. A future
manual-dispatch subcommand added in code but omitted from the registry, if it collides with
another module's verb, would false-redirect a valid command at runtime — the exact class
round 1 closed for subparsers. **Both reviewers exhaustively verified NO live trigger today**
(worktree 18==18, and every other manual module's tokens match), so this was a latent
future-proofing hole, not a shipping bug.
- **Fix applied:** replaced with a **bidirectional** AST parity test — a per-entry-function
  scoped scan extracting `<dispatch> ==/!= "lit"` comparison strings + `choices=[...]`
  literals, asserted set-equal to the registry. A novel dispatch shape must extend
  `_is_dispatch_operand` (same maintenance contract as the registry itself).

### P3 — Multi-owner redirect UX (suffix + cli form)
`command_registry.py` — **code-reviewer (P3) + Codex (low)**. (a) A cli-owned verb was
suggested as `python -m harness_maker.cli <verb>` instead of the canonical root form
`python -m harness_maker <verb>`. (b) The same trailing args were appended to every owner
suggestion though flag surfaces differ per module.
- **Fix applied:** `misroute_guard` now emits the root form for the `cli` owner, and appends
  a "flags may differ per target" note when >1 owner is listed. (No correctness change — the
  guard exits before dispatch either way.)

## 📝 Manual-Only / Refuted (evidence)

The deep pass actively refuted five suspected gaps (code-reviewer, with Codex concurrence):
- **Guard placement** — `guard_or_none` is the FIRST argv-inspecting statement in all 19
  wired entries, before argparse and any IO (verified per hunk incl. autopilot.main and
  spec_mutation's deferred import).
- **Import graph** — `command_registry` imports only stdlib (no `harness_maker` imports) → no
  cycle; pure dict construction, no import-time side effects. cli.py's removed imports have
  zero remaining references.
- **No-argv-param entries** — spec_quality/two_pass_review call `guard_or_none()` with
  argv=None → `sys.argv[1:]`, consistent with their own `sys.argv` reads.
- **resolve_owners over `cli`** — `python -m harness_maker.cli verify` is runnable, so no
  broken suggestion (downgraded to the P3 UX item above).
- **Misc** — no off-by-one (exact membership, no fuzzy line-matching), frozenset/set compares
  type-correct, `add_help=False` matches the established autopilot_caps/_ledger convention.

## 🤝 Disagreements

None material. Severity on the manual-dispatch gap: code-reviewer P2 vs Codex medium (→P2) —
agreed P2 (latent, no live trigger).

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| R2 (deep) | A     | 2 (P2 bidirectional manual parity, P3 redirect UX) | 0 | 0 |

Final grade: **A**
Status: **APPROVED**
human_review_needed: false
Note: applied as a follow-up commit on the already-landed feature (no worktree — landed code).
