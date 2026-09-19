---
type: baseline-delta
task_slug: observed-harness-gaps-salvage
created: 2026-09-19
summary: "Surface growth from salvaging observed-harness-gaps: execute warm tier, plan barrier-index note, review telemetry doc, wrapup main-loop backlog line"
---

# BASELINE-DELTA — observed-harness-gaps-salvage

## 1. Declared while in flight (ADR-009)

Phases 3–5 grow four atomic commands. The growth rides this PLAN's `surface_allowance` and is
folded into `tests/structural/surface_baseline.json` once, in Phase 6, when the allowance is
retired. Section 2 is written then, with the measured per-command attribution and the re-frozen
aggregate for both variants.

## 2. Attribution — retirement (Phase 6, ADR-009)

The allowance block is deleted from `PLAN-observed-harness-gaps-salvage.md` and the growth is
folded into `tests/structural/surface_baseline.json` from **this worktree's render** at base
`555ca933`. The aggregate moves **larger** — claude 434 397 → 436 655 (+2 258), codex
369 446 → 371 718 (+2 272) — and every byte of it is this task's own template content, listed
per key below. This is the subject folding its own measured, allowance-declared growth at
close-out (ADR-010 of PLAN-workflow-step-audit names this as the legitimate re-freeze moment);
it is not `ratchet-rebaselined-by-its-own-subject`, because the growth was declared in the
PLAN's `surface_allowance` in the same change as each template edit (Phases 3–5), bounded by it
while in flight, and only folded here.

| key | before → after | owner / reason |
|---|---|---|
| `execute` chars / round_trips | 49 821 / 17 → 50 505 / 18 (+684, +1) | Phase 3: warm tier loads failure bodies via `hm memory_retrieve` (SPEC S5 / AC-007); the review repair then dropped the now-redundant item-3 wiki skim (review aadf45be) |
| `hm-execute` chars / round_trips | 48 688 / 16 → 49 379 / 17 (+691, +1) | same, Codex arm (`Bash("…")` form) |
| `plan` chars | 66 436 → 66 702 (+266) | Phase 4: `--barrier-index` integer note, every depth (SPEC S7 / AC-011) |
| `hm-plan` chars | 61 614 → 61 880 (+266) | same, Codex arm |
| `review` chars | 87 153 → 87 407 (+254) | Phase 4: telemetry paragraph — `wall_time_ms` optional, never 0 for an unmeasured round (SPEC S6 / AC-010; wording tightened by review dccf4720) |
| `hm-review` chars | 83 556 → 83 810 (+254) | same, Codex arm |
| `wrapup` chars / round_trips | 49 594 / 30 → 50 648 / 31 (+1 054, +1) | Phase 5: main-loop proposal-backlog paragraph + `hm proposals summary` at the head of `Steps 6 → 7.6` (SPEC S2 / AC-003, ADR-006/007) |
| `hm-wrapup` chars / round_trips | 47 806 / 28 → 48 867 / 29 (+1 061, +1) | same, Codex arm |
| `aggregate_chars` | 434 397 / 369 446 → 436 655 / 371 718 | sum of the rows above |
| `render_sha` | `b48bcec4` → `555ca933` | the freeze was taken in this worktree at base 555ca933 (the previous freeze was at b48bcec4) |
| `payload_digest` | recomputed | mechanical — follows the surface map |

Other ratchets moved with the same edits, each in the phase that made the change:

- `_CLAUDE_ROUND_TRIPS`: `execute` 17 → 18 (Phase 3), `wrapup` 30 → 31 (Phase 5).
- `_ATOMIC_RATCHET`: `execute` 48 199 → 49 290 (the review repair's −29 stays inside the band) and `wrapup` 45 646 → 47 413 — both ask@flag_on
  renders left the 2 % band once the allowance was retired; re-based to the landed figure.
- `test_render_wrapup_delegation` line pins: 713/746 → 735/768 (Phase 5).
- `tests/render/test_render_roundtrip_collapse.py` wrapup git-tail call sequence: gains
  `proposals summary` at the head (Phase 5's funded call, asserted in position).
- `tests/structural/autopilot_gate_golden.json`: re-captured with a `rebases` entry; only
  `execute`/`plan`/`review`/`wrapup` moved, in every arm.
- `tests/snapshot/*.expected.yaml`: regenerated in this worktree; only `execute`/`review`/`wrapup`
  command and stage files moved (`plan`'s ledger block does not render in the snapshot
  profiles).
