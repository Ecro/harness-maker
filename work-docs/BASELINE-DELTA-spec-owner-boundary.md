---
type: baseline-delta
task_slug: spec-owner-boundary
created: 2026-11-27
owns: [surface_baseline]
summary: "SPEC-spec-owner-boundary's shipped-surface growth: the fifth Step 0 skip condition and the Step 2 Boundary rule in /hm:spec"
---

# Baseline delta — PLAN-spec-owner-boundary

The shipped surface **grew** by 471 chars in `spec` (claude) and `hm-spec` (codex). The 2026-11-26
replay bench showed `/hm:spec` asking owners almost nothing on detailed asks (3 of 10 owner-only
facts before code vs 8 for a fixed discipline prompt). The fix is text the model reads at the
spec stage, so it cannot be paid for elsewhere without cutting a rule:

- Step 0: "all four" → "all five" conditions, "(docs count, tests do not)", "CLI-output or
  user-facing message change (a typo fix is not one)", "no open **Boundary** (read the code as
  Step 2 says)", "A detailed ask is not a small one; when unsure, interview." (+~235)
- Step 2: the **Boundary** paragraph above the design brief (+~236)

A first draft measured +550 and was trimmed; review fixes added back 57.

Measured with the committed generator (`tests/structural/_surface_baseline.py`,
`measure_surface()`) against the frozen baseline. The aggregate also shows `execute`/`hm-execute`
−36 from an earlier change not yet folded, so the aggregate moved +435 per variant.

| variant | command | before (chars) | after | cause |
|---|---|---|---|---|
| claude | `spec` | 8 186 | 8 657 | skip condition + Boundary rule |
| codex | `hm-spec` | 8 277 | 8 748 | same text |
