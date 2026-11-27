---
type: baseline-delta
task_slug: spec-owner-boundary
created: 2026-11-27
owns: [surface_baseline]
summary: "SPEC-spec-owner-boundary's shipped-surface growth: the fifth Step 0 skip condition and the Step 2 Boundary rule in /hm:spec"
---

# Baseline delta — PLAN-spec-owner-boundary

The shipped surface **grew** by 622 chars in `spec` (claude) and `hm-spec` (codex). The 2026-11-26
replay bench showed `/hm:spec` asking owners almost nothing on detailed asks (3 of 10 owner-only
facts before code vs 8 for a fixed discipline prompt). The fix is text the model reads at the
spec stage, so it cannot be paid for elsewhere without cutting a rule:

- Step 0: "all four" → "all five" conditions, "(docs count, tests do not)", "CLI-output or
  user-facing message change (a typo fix is not one)", "no **Boundary** left open (Step 2)", "A detailed ask is not a small one; when unsure, interview." (+~235)
- Step 2: the **Boundary** paragraph above the design brief (+~236)

A first draft measured +550 and was trimmed; review fixes added back 57. Revision 2 (+151) makes
the Boundary a question unless the ask states it: the first wording's re-measure showed hm judging
the code settled and writing the boundary down as its own assumption (asked 0 of 3 times).

Measured with the committed generator (`tests/structural/_surface_baseline.py`,
`measure_surface()`) against the frozen baseline. The aggregate also shows `execute`/`hm-execute`
−36 from an earlier change not yet folded, so the aggregate moved +586 per variant.

| variant | command | before (chars) | after | cause |
|---|---|---|---|---|
| claude | `spec` | 8 186 | 8 808 | skip condition + Boundary rule |
| codex | `hm-spec` | 8 277 | 8 899 | same text |

Per ADR-010 the task that moved the surface owns its attribution. Writing it next to the
allowance and the later re-freeze keeps this out of `ratchet-rebaselined-by-its-own-subject`.

## Folded into the baseline from main

PR #83 squash-merged the task as ec2d6209. The PLAN was then marked complete, which expires its
allowance, so the growth was folded on main. The generator re-froze
`tests/structural/surface_baseline.json` at ec2d6209c086: claude 50 645, codex 31 915 (spec
8 186 -> 8 808, hm-spec 8 277 -> 8 899; execute/hm-execute −36 from the earlier unfolded change).
`render_sha` and `payload_digest` moved mechanically with the re-freeze. `_ATOMIC_RATCHET` is
re-measured for spec (7 728 -> 8 350), which left its ±2% band. No bench measurement ran on the
task branch's eval rows, so no `bench_hash` alias is needed.
